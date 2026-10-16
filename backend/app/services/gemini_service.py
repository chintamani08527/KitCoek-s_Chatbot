import json
import re
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types
from backend.app.core.config import settings
from backend.app.services.gemini_pool import get_gemini_pool

class GeminiService:
    def __init__(self):
        self.pool = get_gemini_pool()
        self.api_key = settings.GEMINI_API_KEY
        self.client = self.pool.keys[0].init_client() if self.pool.has_keys() else None

    def is_configured(self) -> bool:
        return self.pool.has_keys()

    def classify_query(self, query: str) -> Dict[str, Any]:
        """
        Classifies query into:
        - category: 'academic', 'navigation', 'clubs', 'general_college', 'out_of_scope'
        - is_relevant: bool
        """
        q_lower = query.lower()

        # Fast heuristic for unrelated out-of-scope queries to save network calls
        unrelated_topics = [
            "recipe", "cake", "bake", "cook", "movie", "film", "actor", "bitcoin", "crypto",
            "stock market", "football", "cricket match", "weather in", "song", "lyrics", "game"
        ]
        if any(topic in q_lower for topic in unrelated_topics):
            # Double check it doesn't mention college
            if not any(c in q_lower for c in ["kit", "college", "campus", "engineering", "dept", "exam"]):
                return {"category": "out_of_scope", "is_relevant": False}

        # Academic priority indicators (timetable, syllabus, notes, results, portal, attendance)
        academic_priority = [
            "timetable", "time table", "schedule", "syllabus", "curriculum", "unit", "course",
            "notes", "handwritten", "result", "results", "marks", "grade", "sgpa", "cgpa",
            "portal", "lms", "vmedulife", "fee", "fees", "admission", "scholarship", "exam", "examination",
            "attendance", "absent", "present", "my learnings", "start learning", "academic planning",
            "answer sheet review", "appeals", "paper seeing", "view result", "daily attendance", "monthly attendance"
        ]
        is_academic_doc_query = any(kw in q_lower for kw in academic_priority)

        # Physical location / classroom / map keywords
        classroom_codes = [
            "cbcr", "cscr", "mccr", "bshcr", "csamcr", "csdscr", "etcr", "btcr", "eecr", "cvcr"
        ]
        physical_nav_keywords = [
            "campus map", "aerial map", "campus layout", "how to reach", "directions to",
            "where is classroom", "where is lab", "where is room", "where is building",
            "where is the library", "where is the canteen", "where is imer", "where is mechanical building",
            "which floor", "which building", "room location", "lab location", "building location"
        ]
        is_room_code = any(code in q_lower for code in classroom_codes)
        is_nav_explicit = is_room_code or any(kw in q_lower for kw in physical_nav_keywords) or (
            ("where is" in q_lower or "how to reach" in q_lower or "location of" in q_lower) and
            any(place in q_lower for place in ["library", "canteen", "imer", "mechanical", "biotechnology", "auditorium", "seminar hall", "entrance", "office", "classroom", "lab", "building"])
        )

        # Only classify as navigation if it is genuinely a physical classroom or map navigation query and NOT just a syllabus/timetable document query
        if is_nav_explicit and not (is_academic_doc_query and not is_room_code and "map" not in q_lower):
            return {"category": "navigation", "is_relevant": True}

        # Student Clubs
        club_keywords = [
            "club", "clubs", "iste", "e-cell", "ecell", "mavericks", "sdc", "amateur writers",
            "ebsb", "cultural club", "aura", "shourya", "wdgec", "women development", "rotaract",
            "swe", "www", "walk with world", "ncc", "nss", "lead india", "petrichor", "induction",
            "sip", "student activities", "hackathon", "meraki", "gathering", "annual gathering", "cultural fest", "reels", "pioneer", "vidman", "prarambha", "mesa", "cesa", "elesa", "assets", "acses", "cabssa", "bytearq", "codewizard", "battle of wits", "civil safari", "tech-negotia", "tech negotia", "departmental club", "departmental clubs", "student association", "student associations"
        ]
        if any(w in q_lower for w in club_keywords):
            return {"category": "clubs", "is_relevant": True}

        college_keywords = [
            "kit", "kitcoek", "syllabus", "subject", "semester", "sem", "nep", "exam", "course",
            "unit", "notes", "passing", "grade", "credits", "result", "results", "marks", "prn", "admission", "fee",
            "scholarship", "hostel", "mess", "faculty", "hod", "department", "attendance", "placement", "rules",
            "portal", "student portal", "lms", "vmedulife", "sgpa", "cgpa", "studentsummary",
            "timetable", "time table", "schedule", "sps", "statistical methods", "handwritten notes", "handwritten", "variance"
        ]
        if any(w in q_lower for w in college_keywords) or is_academic_doc_query:
            return {"category": "academic", "is_relevant": True}

        # Check if greeting or introduction
        greetings = ["hi", "hello", "hey", "who are you", "what can you do", "help", "good morning", "good evening"]
        if any(q_lower.startswith(g) or q_lower == g for g in greetings):
            return {"category": "general_college", "is_relevant": True}

        return {"category": "academic", "is_relevant": True}

    def generate_rag_answer(
        self,
        query: str,
        context_chunks: List[str],
        location_data: Optional[Dict[str, Any]] = None,
        club_data: Optional[Dict[str, Any]] = None,
        clubs_directory: Optional[List[Dict[str, Any]]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Generate grounded RAG answer using official college documents, campus locations,
        and official Student Clubs reports (AY 2025–26).
        Follows strict grounding: never invents facts, syllabus, coordinators, or room numbers.
        """
        if not self.is_configured():
            if club_data:
                name = club_data.get("name")
                desc = club_data.get("description", "")
                coord = club_data.get("faculty_coordinator") or "Check official website"
                pdf = club_data.get("pdf_url")
                pdf_link = f'<p><a href="{pdf}" target="_blank">📄 View Official 2025–26 Report (PDF)</a></p>' if pdf else ""
                return {
                    "answer": f"<p><strong>{name}</strong> ({club_data.get('category')}):</p><p>{desc}</p><p><strong>Faculty Coordinator:</strong> {coord}</p>{pdf_link}",
                    "follow_up_questions": ["What activities does this club organize?", "How do I join this club?"]
                }
            elif context_chunks:
                joined = "\n\n".join(context_chunks[:2])
                return {
                    "answer": f"<p>{joined[:600]}...</p>",
                    "follow_up_questions": ["Where can I view the full syllabus?", "What are the passing criteria?"]
                }
            elif location_data:
                return {
                    "answer": f"<p><strong>{location_data.get('name')}</strong> is located in the <strong>{location_data.get('building')}</strong> on the <strong>{location_data.get('floor')}</strong> (Room: {location_data.get('room_number', 'N/A')}).</p><p>Landmark: {location_data.get('landmark', 'Main Campus')}</p>",
                    "follow_up_questions": ["Where is CBCR?", "How do I reach the Library?"]
                }
            else:
                return {
                    "answer": "<p>Official records for this are not currently available in my knowledge base. Please check with your department or student section.</p>",
                    "follow_up_questions": []
                }

        context_str = ""
        if context_chunks:
            context_str += "=== OFFICIAL COLLEGE DOCUMENTS & CLUB REPORTS CONTEXT ===\n"
            for i, chunk in enumerate(context_chunks):
                context_str += f"[Extract {i+1}]:\n{chunk}\n\n"
        if club_data:
            context_str += "=== OFFICIAL KITCOEK STUDENT CLUB VERIFIED RECORD ===\n"
            context_str += json.dumps(club_data, indent=2) + "\n\n"
        if clubs_directory:
            context_str += "=== OFFICIAL KITCOEK STUDENT CLUBS DIRECTORY (18 CLUBS) ===\n"
            context_str += json.dumps(clubs_directory, indent=2) + "\n\n"
        if location_data:
            context_str += "=== CAMPUS LOCATION DATABASE ===\n"
            context_str += json.dumps(location_data, indent=2) + "\n\n"

        system_instruction = """You are the official AI Assistant for KITCOEK (Kolhapur Institute of Technology's College of Engineering, Kolhapur).
Core Directives:
1. ONLY answer questions regarding KITCOEK campus, student academics (syllabus, NEP-2020, subjects, exams), campus locations, and official Student Clubs.
2. Official Student Clubs: KITCOEK has 18 official student clubs and activity groups:
   - Technical: ISTE, Team Mavericks, Student Developers Club (SDC), Society of Women Engineers (SWE)
   - Entrepreneurship: E-Cell KITCoEK
   - Cultural: Cultural Club, Ek Bharat Shreshtha Bharat (EBSB)
   - Creative: Amateur Writers Club, AURA — The Art Club
   - Leadership: Shourya Team KIT, National Cadet Corps (NCC), Lead India
   - Social Service: National Service Scheme (NSS), Rotaract Club of KIT Sunshine
   - Environment: Petrichor — Green Club
   - Student Development: Walk With World (WWW), Women Development and Gender Equality Cell, Student Induction Program (SIP)
3. For Club recommendations:
   - Coding, Web & AI -> SDC, Team Mavericks, ISTE
   - Entrepreneurship & Startups -> E-Cell KITCoEK
   - Public Speaking, Soft Skills, MUN -> Walk With World (WWW), Amateur Writers Club
   - Defense Services (Armed Forces/SSB) -> NCC (1 MAH ARTY BTY), Shourya Team KIT
   - Social Work & Community Welfare -> NSS, Rotaract Club
   - Arts, Sketching, Decor -> AURA — The Art Club
   - Performing Arts, Music, Dance, Meraki -> Cultural Club
   - Civil Services (UPSC/MPSC) -> Lead India
   - Environment & Green Campus -> Petrichor — Green Club
   - Women in Tech & Gender Equity -> SWE, Women Development Cell
4. GROUNDING IS STRICT: Use the provided context as authority for club facts, coordinators, office-bearers, events, and room numbers. Never invent office-bearers or dates.
5. If the user asks for report, coordinators, or activities, provide exact facts and include clickable links: <a href="PDF_URL" target="_blank">📄 View Official Report (PDF)</a> and official page link <a href="https://www.kitcoek.in/studentClubs" target="_blank">Official Clubs Directory</a>.
6. STUDENT PORTAL, RESULTS, ATTENDANCE, AND LMS (VMEDULIFE):
   When the student asks about examination results, paper seeing / review appeals, checking attendance, syllabus, or teacher notes on VMedulife / Student Portal:
   - ALWAYS provide the official KITCOEK vMedulife Student Portal login link: <a href="https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur" target="_blank">🔗 KITCOEK Student Portal (vMedulife)</a>
   
   - FOR CHECKING RESULTS & ANSWER SHEET REVIEWS / APPEALS:
     Instruct the student with these exact numbered steps:
     1. Open the portal link: <a href="https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur" target="_blank">KITCoEK VMedulife Portal</a>.
     2. If prompted, log in with your student account credentials (PRN and password).
     3. Open <strong>Assessment</strong> (or <strong>Exam Forms</strong>, depending on your portal).
     4. Select <strong>Result → Result</strong> (or if paper is displayed, click on <strong>Answer Sheet Review and Appeals</strong>).
     5. Select the relevant <strong>Academic Year</strong> and click <strong>Apply</strong>, if prompted.
     6. Find your semester's result and click <strong>VIEW</strong>.

   - FOR CHECKING SYLLABUS OR NOTES UPLOADED BY TEACHERS ("MY LEARNINGS"):
     Instruct the student with these exact numbered steps:
     1. Open the KITCoEK VMedulife website (<a href="https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur" target="_blank">KITCoEK VMedulife Portal</a>) and log in using your student credentials.
     2. On the dashboard, click <strong>Academic Planning</strong>.
     3. Select <strong>Start Learning</strong>.
     4. Open <strong>My Learnings</strong>.
     5. You should now be able to see the learning materials or courses assigned to you.
     6. Click the relevant subject or learning item to open it.
     (Also provide the direct Google Drive backup link for offline/handwritten subject notes: <a href="https://drive.google.com/drive/folders/1_1mxw4T2BNFCYFOoolsfAmZi8zWvv1Hy" target="_blank">📁 View All Subject Notes in Drive</a>).

   - FOR CHECKING ATTENDANCE (DAILY, WEEKLY, MONTHLY):
     Instruct the student with these exact numbered steps:
     1. Open the KITCoEK VMedulife website (<a href="https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur" target="_blank">KITCoEK VMedulife Portal</a>) and log in with your student ID and password.
     2. Go to <strong>Academic Planning</strong>.
     3. Look for the <strong>Attendance</strong> option.
     4. Open the attendance section.
     5. Choose the attendance view you want:
        - <strong>Daily Attendance</strong> – to check attendance for a particular day.
        - <strong>Weekly Attendance</strong> – to check attendance for a week.
        - <strong>Monthly Attendance</strong> – to check attendance for a month.
     6. Select the required date, week, or month, if prompted.
     7. View your attendance details, including the classes attended and absent, if displayed.
7. STUDENT NOTES & TIMETABLES (PUBLIC GOOGLE DRIVE REPOSITORY):
   When the student asks about subject notes, handwritten notes, study materials, or timetables / class schedules:
   - For NOTES queries:
     * DIRECTLY provide the specific PDF links:
       - Statistical Methods (Unit 4: Analysis of Variance): <a href="https://drive.google.com/file/d/1Iw8r8ht5fseg3yeCWbjCXsr_J7a4nQYZ/view" target="_blank">📄 Statistical Methods - Unit 4: Analysis of Variance (PDF)</a>
       - SPS (Unit 3 Notes): <a href="https://drive.google.com/file/d/1DCB3nY6wc5BF3QJHxMDCOeZtsVIWsC2f/view" target="_blank">📄 SPS - Unit 3 Notes (PDF)</a>
       - Browse All Subject Notes in Drive: <a href="https://drive.google.com/drive/folders/1_1mxw4T2BNFCYFOoolsfAmZi8zWvv1Hy" target="_blank">📁 View All Subject Notes in Drive</a>
   - For TIMETABLE queries:
     * SYSTEMATIC DEPARTMENT TIMETABLES:
       Provide a concise, helpful overview (2-3 sentences) confirming the class timetable and academic years/batches covered for the requested department (BSH for F.Y. B.Tech / AIML for SY, TY, Final Year / CSBS).
       DO NOT include URLs, raw Google Drive links, or <a> anchor tags in your text reply, because an interactive systematic timetable card with 1-click access buttons is automatically displayed directly below your answer.
8. OFFICIAL NOTICE BOARD & ACADEMIC CALENDARS (https://www.kitcoek.in/notice):
   When the student asks about Mid Semester Examinations (MSE), exam timetables, ESE exams, academic calendars, re-examinations, hall tickets, paper seeing / grievances, or the latest campus announcements:
   - Cite the exact circular title, date, and link directly to the official notice PDF on the KITCOEK Notice Board whenever relevant.
   - Mention that live official notices and circulars are accessible on: <a href="https://www.kitcoek.in/notice" target="_blank">📌 KITCOEK Official Notice Board (kitcoek.in/notice)</a>
   - For ACADEMIC CALENDARS:
     * Academic Year 2026–27 (Odd Sem) - S.Y., T.Y. & Final Year B.Tech: <a href="https://www.kitcoek.in/documents/academics/academic-calender/Academic26_27/SY-TY-BTECH_ACADEMIC%20CALENDAR_2026-27_ODD%20SEM.pdf" target="_blank">📅 Academic Calendar 2026–27 (SY, TY, Final Year B.Tech) [PDF]</a>
        - Commencement of Academic Sem-I: 14th July, 2026
        - S.Y. B.Tech Induction Program: 21st to 26th July, 2026
        - ISE-I Marks Submission: 05th September, 2026
        - Mid Semester Examination (MSE): 08th to 13th September, 2026
        - MSE Result Declaration: 24th September, 2026
        - KIT PBL Day: 05th November, 2026
        - End of Academic Activities (Regular): 14th November, 2026
        - Remedial Classes: 17th to 20th November, 2026 (End of Academic Activities: 20th Nov)
        - Submission of ISE-II Marks & Final Defaulters / Detained List: 18th November, 2026
        - Freezing of Attendance & Marks: 20th November, 2026
        - End Semester Examination (Lab POE/OE): 25th November to 03rd December, 2026
        - Smart India Hackathon (SIH 2026 Probable): 08th–09th December, 2026
        - End Semester Examination (Theory ESE): 15th December, 2026 to 10th January, 2027
        - Commencement of Even Semester (Sem-II): 19th January, 2027
        - ESE Result Declaration (Probable): 30th January, 2027
        - Total Instruction Days: 83 Days
     * Academic Year 2026–27 (Odd Sem) - F.Y. B.Tech & F.Y. M.Tech: <a href="https://www.kitcoek.in/documents/academics/academic-calender/Academic26_27/FYBTech_FYMTech_Academic%20Calendar_2026-27%20Odd%20Sem.pdf" target="_blank">📅 Academic Calendar 2026–27 (FY B.Tech & M.Tech) [PDF]</a>
        - Student Induction Program (SIP): Phase-I (25–30 Aug 2026), Phase-II (01–06 Sept 2026), Phase-III (08–13 Sept 2026)
        - Commencement of Academic Sem-I (Odd Sem): 01st September, 2026
        - ISE-I Marks Submission: 17th October, 2026
        - Mid Semester Examination (MSE): 24th to 31st October, 2026
        - MSE Result Declaration: 14th November, 2026
        - Smart India Hackathon (SIH 2026 Probable): 08th–09th December, 2026
        - KIT PBL Day: 16th December, 2026 | End of Academic Activities: 19th December, 2026
        - Submission of ISE-II Marks & Final Defaulters / Detained List: 22nd December, 2026
        - Freezing of Attendance & Marks: 23rd December, 2026
        - End Semester Examination (Lab POE/OE): 26th to 30th December, 2026
        - End Semester Examination (Theory ESE): 01st to 12th January, 2027
        - Commencement of Even Semester (Sem-II): 15th January, 2027
        - ESE Result Declaration: 30th January, 2027
        - Total Instruction Days: 96 Days
     * Academic Year 2026–27 (Odd Sem) - S.Y. M.Tech: <a href="https://www.kitcoek.in/documents/academics/academic-calender/Academic26_27/SYMTECH_ACADEMIC%20CALENDAR_2026-27_ODD%20SEM.pdf" target="_blank">📅 Academic Calendar 2026–27 (SY M.Tech) [PDF]</a>
     * Academic Year 2025–26 (Even Sem) - All UG & PG: <a href="https://www.kitcoek.in/documents/academics/academic-calender/Academic25_26/Revised_Academic_Calendar_2025-26_Even_Sem_UG_PG.pdf" target="_blank">📅 Revised Academic Calendar 2025–26 (Even Sem) [PDF]</a>
     * Academic Year 2025–26 (Odd Sem) - S.Y., T.Y. & Final Year B.Tech: <a href="https://www.kitcoek.in/documents/academics/academic-calender/Academic25_26/Academic%20Calendar_SY-TY-Final%20Year%20BTech_2025-26_Odd%20Sem.pdf" target="_blank">📅 Academic Calendar 2025–26 (Odd Sem) [PDF]</a>
   - For MSE (Mid Semester Examinations) & Exam Circulars:
     * Use the provided live notice context from kitcoek.in/notice to give exact dates, circular numbers, and direct PDF download links.
9. CAMPUS LOCATIONS & ABBREVIATIONS:
   - In the IMER Building on the Third Floor, **CBCR** stands for **Computer Science and Business Systems (CSBS)** Classrooms (CBCR 01, CBCR 02, CBCR 03, CBCR 04, CBCR 05).
   - IMER Building Floor Allocation:
     * Ground Floor: ETCR 04 (MBA)
     * First Floor: CSAMCR 01 (CSE AIML), CSDSCR 01 (CSE Data Science), ETCR 03
     * Second Floor: CSAMCR 02, 03, 04 (CSE AIML), CSDSCR 02, 03 (CSE Data Science)
     * Third Floor: CBCR 01, CBCR 02, CBCR 03, CBCR 04, CBCR 05 (Computer Science and Business Systems / CSBS)
10. MERAKI — FLAGSHIP ANNUAL CULTURAL FESTIVAL & GATHERING:
    Meraki is KITCOEK's premier annual cultural gathering and campus festival, organized by the Cultural Club (Cultural Committee).
    When asked about Meraki, gathering, cultural events, or videos/reels:
    - Describe Meraki as the flagship annual cultural gathering featuring mega dance competitions, musical concerts, drama, fashion shows, and campus celebrations.
    - Mention that students can watch the official reels and festival highlights below.
    - DO NOT list individual reel links or URLs in your text reply; a dedicated interactive Instagram Reels card with direct watch buttons is automatically appended below your answer.
11. DEPARTMENTAL CLUBS & STUDENT ASSOCIATIONS (PIONEER 2025):
    Every engineering department at KITCoEK has an active departmental student association:
    - Mechanical Engineering: MESA (Mechanical Engineering Students' Association) — PIONEER 2025 Flagship Event: 'Battle of Wits', CAD competitions, mechanical project exhibitions, manufacturing workshops.
    - Civil Engineering: CESA (Civil Engineering Students' Association) — PIONEER 2025 Flagship Event: 'Civil Safari', surveying contests, structural bridge design, green construction.
    - Electrical Engineering: ELESA (Electrical Engineering Students' Association) — PIONEER 2025 Flagship Event: 'Dive in Circuit 3.0', circuit troubleshooting, EV technologies, automation.
    - Electronics & Telecom (ENTC): ASSETS (Association of Students of Electronics & Telecommunication) — Embedded systems, IoT, Arduino/sensors, robotics, telecom competitions.
    - Computer Science & Engineering (CSE): ACSES (Association of Computer Science & Engineering Students) — PIONEER 2025 Flagship Event: 'CodeWizard', competitive coding, web development (official portal: acses-kitcoek.web.app).
    - CSBS: CABSSA (Computer Science and Business Systems Student Association) — PIONEER 2025 Flagship Event: 'Tech-Negotia 2.0', techno-business case studies, enterprise problem-solving.
    - CSBS Technical Wing: Bytearq — Coding sprints, open-source web development, collaborative hackathon preparation.
    When asked about any departmental club, explain its role, department, PIONEER event, skills gained, and student benefits. Mention that students can explore them in the Student Clubs section.
12. OFFICIAL ONLINE SYLLABUS & NEP-2020 CURRICULUM (https://www.kitcoek.in/online-syllabus):
    KITCOEK provides fully autonomous National Education Policy (NEP 2020) curriculums for all engineering departments.
    When a student asks about syllabus, NEP structure, subjects, or academic curriculum (especially for CSBS - Computer Science & Business Systems):
    - Reassure the student that the syllabus strictly complies with the official KITCoEK 2023 [NEP-2020] Scheme published on the college portal: <a href="https://www.kitcoek.in/online-syllabus" target="_blank">🌐 KITCoEK Online Syllabus Portal</a>.
    - FOR CSBS (Computer Science and Business Systems):
      * Describe the core program: an industry-oriented 4-year B.Tech developed in synergy with TCS, blending core computer engineering with Business 4.0, analytics, and enterprise management.
      * Highlight key focus areas: Core Algorithms & Computing, Data Science & Machine Learning, Enterprise Architecture, Financial & Marketing Strategy, and emerging specialization tracks (AR/VR, Metaverse, Honors & Multidisciplinary Minor).
      * DO NOT output duplicate raw PDF download links or repeat the year-by-year syllabus lists in your text reply; a dedicated interactive Official Syllabus Card with verified direct download buttons for the All-Years Curriculum Structure, F.Y., S.Y., T.Y., Final Year, Honors, MDM, and Exit Courses is automatically attached right below your answer.
13. Format your answer in clean HTML suitable for the chat bubble (use <p>, <ul>, <li>, <strong>, <em>, <a>).
14. Provide 2 to 3 relevant follow-up questions related to KITCOEK.

Output format (respond ONLY with valid JSON):
{
  "answer": "<p>HTML answer...</p>",
  "follow_up_questions": ["Question 1", "Question 2"]
}
"""

        user_prompt = f"""Context:
{context_str if context_str else "No specific document match found in knowledge base."}

Student Query: {query}
"""

        try:
            models_to_try = [settings.GEMINI_MODEL, "gemini-3.5-flash-lite", "gemini-3.8-flash"]
            last_err = None
            response = None
            
            for m in models_to_try:
                try:
                    response = self.pool.generate_content(
                        model=m,
                        contents=[
                            {"role": "user", "parts": [{"text": system_instruction + "\n\n" + user_prompt}]}
                        ],
                        config=types.GenerateContentConfig(
                            temperature=0.2,
                            response_mime_type="application/json"
                        )
                    )
                    if response and response.text:
                        break
                except Exception as ex:
                    last_err = ex
                    continue

            if not response or not response.text:
                raise last_err or Exception("No response generated")

            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)
                raw_text = raw_text.strip()
            
            data = None
            try:
                data = json.loads(raw_text, strict=False)
            except Exception:
                pass

            if not isinstance(data, dict) or "answer" not in data:
                # Regex fallback extraction when Gemini generates unescaped quotes or invalid JSON
                ans = ""
                fqs = []
                ans_match = re.search(r'"answer"\s*:\s*"(.*?)(?:"\s*,\s*"follow_up_questions"|"\s*\}\s*$)', raw_text, re.DOTALL)
                if ans_match:
                    ans = ans_match.group(1).replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\/', '/')
                else:
                    cleaned = raw_text
                    cleaned = re.sub(r'^\s*\{\s*"answer"\s*:\s*"?', '', cleaned)
                    cleaned = re.sub(r'"?\s*,\s*"follow_up_questions"[\s\S]*$', '', cleaned)
                    cleaned = re.sub(r'"?\s*\}\s*$', '', cleaned)
                    ans = cleaned

                fqs_match = re.search(r'"follow_up_questions"\s*:\s*\[([\s\S]*?)\]', raw_text)
                if fqs_match:
                    items = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', fqs_match.group(1))
                    fqs = [it.replace('\\"', '"').strip() for it in items if len(it.strip()) > 3]

                data = {
                    "answer": ans,
                    "follow_up_questions": fqs
                }

            # Final sanity cleanup: Guarantee NO raw JSON syntax leaks into answer
            ans_clean = str(data.get("answer", "<p>No response generated.</p>")).strip()
            ans_clean = re.sub(r'",\s*"follow_up_questions"[\s\S]*$', '', ans_clean)
            ans_clean = re.sub(r'^\s*\{\s*"answer"\s*:\s*"', '', ans_clean)
            ans_clean = re.sub(r'"\s*\}\s*$', '', ans_clean).strip()

            return {
                "answer": ans_clean,
                "follow_up_questions": data.get("follow_up_questions") if isinstance(data.get("follow_up_questions"), list) else []
            }
        except Exception as e:
            print(f"[Error] Gemini API generation error: {e}")
            if context_chunks:
                return {
                    "answer": f"<p>{context_chunks[0][:400]}...</p>",
                    "follow_up_questions": ["Where can I view the full syllabus?", "What are the passing criteria?"]
                }
            return {
                "answer": "<p>Official records for this are not currently available in my knowledge base. Please check with your department or student section.</p>",
                "follow_up_questions": []
            }


_gemini_service = None

def get_gemini_service() -> GeminiService:
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
