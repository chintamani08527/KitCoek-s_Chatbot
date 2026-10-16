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

        # Fast heuristic for unrelated out-of-scope queries (celebrities, movies, politics, recipes, sports outside college, etc.)
        unrelated_topics = [
            "salman khan", "shah rukh", "srk", "sharukh", "akshay kumar", "deepika", "katrina", "alia bhatt", "ranbir",
            "amitabh", "hollywood", "bollywood", "actor", "actress", "celebrity", "celebrities",
            "movie", "movies", "film", "films", "cinema", "box office", "netflix", "song", "songs", "lyrics", "singer",
            "recipe", "recipes", "cake", "bake", "cook", "cooking", "pizza", "burger", "biryani", "pasta", "tea recipe",
            "cricket match", "ipl", "virat kohli", "rohit sharma", "dhoni", "football", "messi", "ronaldo", "fifa", "premier league",
            "bitcoin", "crypto", "cryptocurrency", "stock market", "trading", "share market", "forex",
            "weather in", "weather today", "tell me a joke", "tell a joke", "joke", "jokes",
            "write a poem", "sing a song", "flirt", "who is the prime minister", "narendra modi", "donald trump", "biden", "putin",
            "capital of", "president of", "population of", "prime minister of", "cm of", "chief minister of",
            "who is elon musk", "bill gates", "mark zuckerberg", "sundar pichai"
        ]
        if any(topic in q_lower for topic in unrelated_topics):
            # Double check it doesn't mention college
            if not any(c in q_lower for c in ["kit", "college", "campus", "engineering", "dept", "exam"]):
                return {"category": "out_of_scope", "is_relevant": False}

        # Academic priority indicators (timetable, syllabus, notes, results, portal, attendance)
        academic_priority = [
            "timetable", "time table", "schedule", "syllabus", "curriculum", "unit", "course",
            "notes", "handwritten", "result", "results", "marks", "grade", "sgpa", "cgpa", "marksheet", "mark sheet",
            "portal", "lms", "vmedulife", "vmedu", "fee", "fees", "admission", "scholarship", "exam", "examination",
            "attendance", "attendence", "attandance", "atendance", "attandence", "attendece", "attendace",
            "absent", "present", "my learnings", "start learning", "academic planning",
            "notes in vmedulife", "vmedulife notes", "study material in vmedulife",
            "answer sheet review", "appeals", "paper seeing", "view result", "check result", "see result",
            "daily attendance", "monthly attendance", "weekly attendance", "defaulter", "defaulters", "75%"
        ]
        is_academic_doc_query = any(kw in q_lower for kw in academic_priority) or ("attend" in q_lower and "attention" not in q_lower)

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
            any(place in q_lower for place in ["library", "canteen", "imer", "mechanical", "biotechnology", "auditorium", "seminar hall", "entrance", "office", "classroom", "lab", "building", "hostel", "workshop"])
        )

        # Only classify as navigation if it is genuinely a physical classroom or map navigation query and NOT just a syllabus/timetable document query
        if is_nav_explicit and not (is_academic_doc_query and not is_room_code and "map" not in q_lower):
            return {"category": "navigation", "is_relevant": True}

        # Student Clubs (only if not an academic/portal query)
        club_keywords = [
            "club", "clubs", "iste", "e-cell", "ecell", "mavericks", "sdc", "amateur writers",
            "ebsb", "cultural club", "aura", "shourya", "wdgec", "women development", "rotaract",
            "swe", "www", "walk with world", "ncc", "nss", "lead india", "petrichor", "induction",
            "sip", "student activities", "hackathon", "meraki", "gathering", "annual gathering", "cultural fest", "reels", "pioneer", "vidman", "prarambha", "mesa", "cesa", "elesa", "assets", "acses", "cabssa", "bytearq", "codewizard", "battle of wits", "civil safari", "tech-negotia", "tech negotia", "departmental club", "departmental clubs", "student association", "student associations"
        ]
        if any(w in q_lower for w in club_keywords) and not is_academic_doc_query:
            return {"category": "clubs", "is_relevant": True}

        # Cutoff, Admission & Merit List detection
        is_cutoff_query = any(k in q_lower for k in [
            "cut off", "cutoff", "cut-off", "cutoffs", "cut offs", "cut-offs",
            "merit list", "merit lists", "cap round", "cap cutoff", "cet cutoff", "jee cutoff",
            "fe cutoff", "dse cutoff", "dsy cutoff", "seat matrix", "choice code", "choice codes"
        ]) or (
            ("cut" in q_lower and "off" in q_lower) and any(w in q_lower for w in ["list", "rank", "mark", "marks", "percentile", "score", "give", "show", "what", "how", "details"])
        )
        if is_cutoff_query:
            return {"category": "academic", "is_relevant": True}

        college_keywords = [
            "kit", "kitcoek", "kitcoe", "kolhapur", "gokul shirgaon", "college", "campus", "institute", "engineering",
            "cse", "csbs", "aiml", "data science", "aids", "etc", "entc", "telecommunication", "mechanical", "electrical", "civil", "environmental", "biotech", "biotechnology", "bsh", "mtech", "btech", "m.tech", "b.tech", "mba", "imer",
            "syllabus", "curriculum", "subject", "subjects", "semester", "sem", "nep", "nep-2020", "nep2020", "autonomy", "autonomous", "scheme",
            "unit", "notes", "handwritten", "pyq", "question paper", "question papers", "passing", "grade", "grades", "credits", "result", "results", "marks", "marksheet", "mark sheet", "prn",
            "admission", "admissions", "cutoff", "cutoffs", "cut off", "cut-off", "cut offs", "cut-offs", "merit list", "merit lists", "seat matrix", "choice code", "choice codes", "cap round", "cap 1", "cap 2", "cap 3", "acap", "dse", "dsy", "direct second year", "first year cutoff", "fe cutoff", "lateral entry", "cet cell", "dte code", "6267", "mht cet", "jee", "fee", "fees",
            "scholarship", "ebc", "freeship", "mahadbt", "hostel", "mess", "canteen", "library", "reading room", "workshop", "auditorium", "seminar hall",
            "faculty", "teacher", "teachers", "professor", "professors", "prof", "hod", "principal", "director", "department", "departments",
            "attendance", "attendence", "attandance", "placement", "placements", "package", "packages", "highest package", "average package", "lpa", "tpo", "internship", "internships", "rules", "regulations", "ordinance",
            "portal", "student portal", "lms", "vmedulife", "vmedu", "sgpa", "cgpa", "studentsummary", "hall ticket", "admit card",
            "timetable", "time table", "schedule", "sps", "statistical methods", "variance", "academic calendar", "calendar", "calender", "notice", "circular",
            "meraki", "pioneer", "gathering", "annual gathering", "bus", "transport", "wifi", "bonafide", "id card", "leaving certificate", "alumni", "shivaji university",
            "gym", "gymkhana", "ground", "sports", "dress code", "uniform"
        ]
        if any(w in q_lower for w in college_keywords) or is_academic_doc_query:
            return {"category": "academic", "is_relevant": True}

        # Check if greeting or conversational intro
        greetings = [
            "hi", "hello", "hey", "hii", "heyy", "who are you", "what can you do", "help",
            "about yourself", "good morning", "good afternoon", "good evening", "namaste",
            "thank you", "thanks", "bye", "goodbye"
        ]
        words = set(re.findall(r'\b\w+\b', q_lower))
        is_greeting = any(q_lower.startswith(g) or q_lower == g for g in greetings) or any(w in words for w in ["hi", "hello", "hey", "hii", "heyy", "thanks", "thankyou"])
        if is_greeting:
            return {"category": "general_college", "is_relevant": True}

        # STRICT SCOPE ENFORCEMENT:
        # If query has no college keyword, navigation keyword, club keyword, or greeting, it is strictly OUT OF SCOPE.
        return {"category": "out_of_scope", "is_relevant": False}

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
        has_valid_aiza_key = any(
            isinstance(getattr(k, "key", None), str) and k.key.startswith("AIza")
            for k in getattr(self.pool, "keys", [])
        )
        if not self.is_configured() or not has_valid_aiza_key:
            return self._generate_smart_fallback(query, context_chunks, location_data, club_data, clubs_directory)

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
1. STRICT SCOPE & OUT-OF-CONTEXT ENFORCEMENT:
   You are exclusively the official AI Assistant for KITCOEK (Kolhapur Institute of Technology's College of Engineering, Kolhapur).
   - ONLY answer questions directly pertaining to KITCOEK campus, engineering academics (syllabus, NEP-2020, subjects, exams, marks, results), college admissions & cutoffs (CAP rounds, MHT-CET/JEE percentile cutoffs, DSE diploma percentage cutoffs, choice codes, DTE code 6267), campus facilities & room navigation, student clubs, timetables, and the VMedulife portal.
   - If the user asks ANY question outside the college context (e.g., celebrities, actors like Salman Khan, Bollywood/Hollywood movies, politics, national/world leaders, general cricket/sports outside college, cooking recipes, general jokes, non-college stories, general homework/coding unrelated to college courses):
     YOU MUST DECLINE AND RESPOND WITH:
     "<p>⚠️ <strong>Out of Context Query:</strong> I am the dedicated <strong>KITCOEK AI Assistant</strong>, designed exclusively to answer questions about <strong>KITCoEK Kolhapur</strong> campus, admissions, engineering syllabus, timetables, examinations, VMedulife portal, and official Student Clubs.</p><p>Your question appears to be outside the scope of college-related topics. Please ask a question related to KITCOEK!</p>"
   - NEVER answer non-college trivia, celebrity biographies, or general world questions.
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
            return self._generate_smart_fallback(query, context_chunks, location_data, club_data, clubs_directory)

    def _generate_smart_fallback(
        self,
        query: str,
        context_chunks: List[str],
        location_data: Optional[Dict[str, Any]] = None,
        club_data: Optional[Dict[str, Any]] = None,
        clubs_directory: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        q_low = query.strip().lower()
        words = set(re.findall(r'\b\w+\b', q_low))
        # 0. Strict Scope Check: If query is out of college context, decline immediately!
        classification = self.classify_query(query)
        if not classification.get("is_relevant", True):
            return {
                "answer": (
                    "<p>⚠️ <strong>Out of Context Query:</strong> I am the dedicated <strong>KITCOEK AI Assistant</strong>, "
                    "designed exclusively to assist with <strong>KITCoEK Kolhapur</strong> campus information, engineering academics, "
                    "NEP-2020 syllabus, class timetables, examinations, VMedulife portal, campus navigation, and official Student Clubs.</p>"
                    "<p>Your question appears to be outside the scope of college-related topics. Please ask a question related to KITCOEK!</p>"
                ),
                "follow_up_questions": [
                    "What engineering branches are offered at KIT?",
                    "What student clubs are available?",
                    "How to check attendance in VMedulife?",
                    "Show BSH First Year timetable"
                ]
            }

        # 1. Greetings & Welcome
        greetings = ["hi", "hello", "hey", "hola", "namaste", "good morning", "good afternoon", "good evening", "greetings", "hii", "heyy"]
        if any(w in words for w in greetings) or q_low in greetings or q_low.startswith("hello") or q_low.startswith("hi "):
            return {
                "answer": (
                    "<p>Hello! 👋 Welcome to the official <strong>KITCOEK AI Campus Assistant</strong>.</p>"
                    "<p>I am here to help you navigate <strong>Kolhapur Institute of Technology's College of Engineering (Autonomous)</strong>. You can ask me about:</p>"
                    "<ul>"
                    "<li>🗺️ <strong>Campus Navigation:</strong> Classrooms, labs, seminar halls, library &amp; departments.</li>"
                    "<li>🏛️ <strong>Student Clubs:</strong> 25 technical, cultural, sports &amp; social clubs (ISTE, E-Cell, MESA, ACSES...).</li>"
                    "<li>📚 <strong>Curriculum &amp; Syllabus:</strong> Official CSBS &amp; NEP-2020 syllabus PDFs for FY, SY, TY &amp; Final Year.</li>"
                    "<li>📅 <strong>Class Timetables:</strong> Systematic Google Drive schedules for BSH, AIML, CSBS &amp; other departments.</li>"
                    "<li>🎓 <strong>VMedulife Student Portal:</strong> Step-by-step guides for attendance tracking and study notes.</li>"
                    "<li>🎭 <strong>Meraki Cultural Festival:</strong> Official gathering details &amp; campus Instagram reels.</li>"
                    "</ul>"
                    "<p>What would you like to explore?</p>"
                ),
                "follow_up_questions": [
                    "Where is ETC Seminar Hall?",
                    "Show me BSH First Year timetable",
                    "Tell me about ISTE club",
                    "CSBS NEP-2020 syllabus"
                ]
            }

        # 2. Identity & Purpose
        if any(kw in q_low for kw in ["who are you", "what can you do", "help", "what is your name", "what do you do", "about you", "features"]):
            return {
                "answer": (
                    "<p>I am the <strong>KITCOEK AI Campus Assistant</strong>, an autonomous student guidance and campus intelligence assistant for "
                    "<strong>KIT's College of Engineering (Autonomous), Kolhapur</strong>.</p>"
                    "<p>I provide verified answers using official college records, campus mapping, NEP-2020 autonomous schemes, and student club archives.</p>"
                    "<p>Feel free to type any query or click one of the suggested topics below!</p>"
                ),
                "follow_up_questions": [
                    "Where is Central Library?",
                    "Browse all 25 Student Clubs",
                    "AIML department timetable",
                    "How to check attendance in VMedulife?"
                ]
            }

        # 3. Location / Navigation Match
        if location_data:
            name = location_data.get("name", "Campus Location")
            bldg = location_data.get("building", "Main Campus")
            floor = location_data.get("floor", "Ground Floor")
            room = location_data.get("room_number", "")
            landmark = location_data.get("landmark", "Central Campus")
            desc = location_data.get("description", "")
            return {
                "answer": (
                    f"<p><strong>{name}</strong> is situated in the <strong>{bldg}</strong> on the <strong>{floor}</strong>"
                    + (f" (Room / Block: <strong>{room}</strong>)." if room else ".")
                    + f"</p><p>📍 <strong>Landmark:</strong> {landmark}</p>"
                    + (f"<p>{desc}</p>" if desc else "")
                    + "<p>An aerial campus navigation card is displayed below with direct map zoom.</p>"
                ),
                "follow_up_questions": [
                    "Where is Central Library?",
                    "Where is CBCR?",
                    "Show aerial campus map"
                ]
            }

        # 4. Student Club Match
        if club_data:
            name = club_data.get("name", "Student Club")
            abbr = club_data.get("abbr", "")
            cat = club_data.get("category", "Student Association")
            desc = club_data.get("description", "")
            coord = club_data.get("faculty_coordinator", "Department Faculty")
            stu_coords = club_data.get("student_coordinators", "")
            pdf = club_data.get("pdf_url", "")
            pdf_link = f'<p><a href="{pdf}" target="_blank" rel="noopener noreferrer">📄 View Official 2025–26 Report (PDF) ↗</a></p>' if pdf else ""
            return {
                "answer": (
                    f"<p><strong>{name}</strong> {f'({abbr})' if abbr else ''} — <em>{cat} Club</em></p>"
                    f"<p>{desc}</p>"
                    f"<p><strong>Faculty Coordinator:</strong> {coord}</p>"
                    + (f"<p><strong>Student Coordinators:</strong> {stu_coords}</p>" if stu_coords else "")
                    + pdf_link
                ),
                "follow_up_questions": [
                    f"What activities does {abbr or name} conduct?",
                    "Show all Technical clubs",
                    "How do I join a club?"
                ]
            }

        # 5. College Overview / About KIT
        if any(kw in q_low for kw in ["about kit", "about college", "kitcoek", "kolhapur institute of technology", "autonomous", "history of kit"]):
            return {
                "answer": (
                    "<p><strong>Kolhapur Institute of Technology's College of Engineering (Autonomous), Kolhapur</strong> (KITCoEK) was established in 1983 "
                    "and is one of Western Maharashtra's premier autonomous engineering institutions.</p>"
                    "<ul>"
                    "<li><strong>Accreditation:</strong> NAAC 'A+' Grade with 3.33 CGPA, NBA Accredited engineering programs.</li>"
                    "<li><strong>Autonomous Status:</strong> Affiliated with Shivaji University, Kolhapur; autonomous curriculum aligned with NEP-2020.</li>"
                    "<li><strong>Campus Location:</strong> Gokul Shirgaon, Kolhapur, Maharashtra 416234.</li>"
                    "<li><strong>Official Portal:</strong> <a href='https://www.kitcoek.in' target='_blank'>kitcoek.in ↗</a></li>"
                    "</ul>"
                ),
                "follow_up_questions": [
                    "What engineering branches are offered?",
                    "CSBS NEP-2020 syllabus",
                    "Where is the Library?"
                ]
            }

        # 6.0 Admissions & Cutoffs
        is_cutoff_req = any(kw in q_low for kw in [
            "cutoff", "cut off", "cut-off", "cutoffs", "cut offs", "cut-offs",
            "merit list", "cap round", "cap cutoff", "cet cutoff", "jee cutoff",
            "dse cutoff", "dsy cutoff", "fe cutoff", "choice code"
        ]) or (
            ("cut" in q_low and "off" in q_low) and any(w in q_low for w in ["list", "rank", "mark", "marks", "percentile", "score", "give", "show", "what", "how", "details"])
        )
        if is_cutoff_req:
            return {
                "answer": (
                    "<p><strong>KITCOEK Official Admission &amp; Cutoff Lists (DTE Code: 6267):</strong></p>"
                    "<p>Admissions to <strong>KIT's College of Engineering (Autonomous), Kolhapur</strong> are conducted through the Maharashtra State CET Cell Centralized Admission Process (CAP Rounds) and Autonomous Institute Level seats based on MHT-CET, JEE Main, and Diploma percentages.</p>"
                    "<p><strong>1. First Year B.Tech (F.Y. B.Tech / FE) Cutoffs:</strong></p>"
                    "<ul>"
                    "<li><strong>General Seat Type Cutoffs:</strong> <a href='https://www.kitcoek.in/documents/admission/2025_26/FY%20General%20Cutoff-2024-25.jpeg' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 View FY General Cutoff Sheet ↗</a></li>"
                    "<li><strong>Ladies Seat Type Cutoffs:</strong> <a href='https://www.kitcoek.in/documents/admission/2025_26/FY%20Ladies%20Cutoff-2024-25.jpeg' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 View FY Ladies Cutoff Sheet ↗</a></li>"
                    "<li><strong>Indicative Percentiles:</strong> CSE (93–94%+), CSE AIML (90–92%+), CSBS (88–90%+), ETC (85–88%+), Electrical &amp; Mechanical (75–85%+), Civil &amp; Biotech (70–80%+).</li>"
                    "</ul>"
                    "<p><strong>2. Direct Second Year (D.S.Y. / DSE) Diploma Cutoffs (AY 2025–26 Official Record):</strong></p>"
                    "<ul>"
                    "<li><strong>Computer Science &amp; Engineering (CSE):</strong> 93.65% (Top Merit No. 795)</li>"
                    "<li><strong>CSE (AI &amp; ML):</strong> 92.88% (Merit No. 1200)</li>"
                    "<li><strong>CS &amp; Business Systems (CSBS):</strong> 92.06% (Merit No. 1715)</li>"
                    "<li><strong>Electrical Engineering:</strong> 93.11% (Merit No. 1063)</li>"
                    "<li><strong>Civil Engineering:</strong> 92.84% (Merit No. 1227)</li>"
                    "<li><strong>Mechanical Engineering:</strong> 92.46% (Merit No. 1458)</li>"
                    "<li><strong>Electronics &amp; Telecommunication (ETC):</strong> 92.47% (Merit No. 1438)</li>"
                    "<li><strong>Biotechnology:</strong> 75.66%</li>"
                    "<li><strong>Official PDF:</strong> <a href='https://www.kitcoek.in/documents/admission/2026_27/dsy/DSY.B.Tech%20General%20Seat%20Type%20Wise%20Cut%20Off%202025-26.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Download DSY General Cutoff PDF ↗</a> | <a href='https://www.kitcoek.in/documents/admission/2026_27/dsy/DSY%20B.Tech%20Ladies%20Seat%20Type%20Wise%20Cut%20Off%20A.Y.%202025-26.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Download DSY Ladies Cutoff PDF ↗</a></li>"
                    "</ul>"
                    "<p><strong>Official Admission Portals &amp; Helpline:</strong></p>"
                    "<ul>"
                    "<li><strong>Undergraduate Admission Portal:</strong> <a href='https://www.kitcoek.in/admission-undergraduate' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>kitcoek.in/admission-undergraduate ↗</a></li>"
                    "<li><strong>Online Admission Application:</strong> <a href='https://www.kitcoek.in/apply-admission' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>kitcoek.in/apply-admission ↗</a></li>"
                    "<li><strong>Admission Cell Contact:</strong> <a href='mailto:admissions@kitcoek.in'>admissions@kitcoek.in</a> | Phone: <strong>+91-7769001199</strong></li>"
                    "</ul>"
                ),
                "follow_up_questions": [
                    "What documents are required for admission?",
                    "What are the KIT choice codes?",
                    "What is the fee structure for First Year?",
                    "CSBS NEP-2020 syllabus"
                ]
            }

        # 6. Admissions & Departments
        if any(kw in q_low for kw in ["admission", "eligibility", "branches", "departments", "courses", "mht cet", "jee"]):
            return {
                "answer": (
                    "<p><strong>KITCOEK Admissions &amp; Academic Programs:</strong></p>"
                    "<p>KIT offers 4-year undergraduate B.Tech and postgraduate M.Tech degrees across major engineering disciplines under the NEP-2020 Autonomous curriculum:</p>"
                    "<ul>"
                    "<li>Computer Science &amp; Engineering (CSE)</li>"
                    "<li>Computer Science &amp; Business Systems (CSBS)</li>"
                    "<li>Artificial Intelligence &amp; Machine Learning (AIML)</li>"
                    "<li>Artificial Intelligence &amp; Data Science (AIDS)</li>"
                    "<li>Electronics &amp; Telecommunication (ETC)</li>"
                    "<li>Electrical Engineering</li>"
                    "<li>Mechanical Engineering</li>"
                    "<li>Civil &amp; Environmental Engineering</li>"
                    "<li>Biotechnology</li>"
                    "</ul>"
                    "<p>Admissions are conducted through Maharashtra State CET Cell (CAP Rounds) based on MHT-CET and JEE Main scores. Visit <a href='https://www.kitcoek.in' target='_blank'>kitcoek.in ↗</a> for cutoff details.</p>"
                ),
                "follow_up_questions": [
                    "CSBS NEP-2020 syllabus",
                    "AIML department timetable",
                    "Where is Central Library?"
                ]
            }

        # 6.1 VMedulife Attendance Tracking
        is_attendance_query = (
            any(w in q_low for w in [
                "attendance", "attendence", "attandance", "atendance", "attandence", "attendece", "attendace",
                "absent", "present", "defaulter", "defaulters", "detained", "75%", "bunk", "check attendance",
                "daily attendance", "weekly attendance", "monthly attendance"
            ])
            or ("attend" in q_low and not any(x in q_low for x in ["attention", "attendee"]))
        )
        if is_attendance_query:
            return {
                "answer": (
                    "<p><strong>How to Check Student Attendance on KITCoEK VMedulife Portal:</strong></p>"
                    "<p>KITCOEK tracks all lecture and laboratory attendance through the official <strong>vMedulife Student Portal</strong>:</p>"
                    "<ol>"
                    "<li><strong>Login:</strong> Open the <a href='https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>KITCoEK VMedulife Portal ↗</a> and sign in with your Student ID (PRN) and password.</li>"
                    "<li><strong>Academic Planning:</strong> On the left dashboard navigation menu, click on <strong>Academic Planning</strong>.</li>"
                    "<li><strong>Attendance Section:</strong> Click on the <strong>Attendance</strong> option.</li>"
                    "<li><strong>Select View Mode:</strong> Choose between:"
                    "<ul>"
                    "<li><strong>Daily Attendance:</strong> View lecture-by-lecture presence for any specific date.</li>"
                    "<li><strong>Weekly Attendance:</strong> Summary of sessions attended across the week.</li>"
                    "<li><strong>Monthly Attendance:</strong> Monthly aggregate and cumulative attendance percentage.</li>"
                    "</ul></li>"
                    "<li><strong>Verify Eligibility:</strong> Check your cumulative percentage. As per autonomous college regulations, students must maintain at least <strong>75% attendance</strong> in each course to remain eligible for End Semester Examinations (ESE).</li>"
                    "</ol>"
                    "<p>A direct 1-click access card to the student portal is also displayed below.</p>"
                ),
                "follow_up_questions": [
                    "How to check results in VMedulife?",
                    "How to access notes in VMedulife?",
                    "Show academic calendar 2026-27",
                    "BSH first year time table"
                ]
            }

        # 6.2 VMedulife Notes & My Learnings
        is_vmedu_notes_query = (
            any(w in q_low for w in [
                "my learnings", "start learning", "learning material", "teacher notes", "teacher note",
                "vm notes", "vmedulife notes", "notes in vmedulife", "notes on vmedulife", "study material in vmedulife",
                "lecture notes in vmedulife", "vmedulife study material", "download notes in vmedulife"
            ])
            or (any(n in q_low for n in ["note", "notes", "material", "materials", "ppt", "slides", "learning"]) and any(p in q_low for p in ["vmedulife", "portal", "lms"]))
        )
        if is_vmedu_notes_query:
            return {
                "answer": (
                    "<p><strong>How to Access Teacher Notes &amp; Course Materials on VMedulife ('My Learnings'):</strong></p>"
                    "<p>Faculty members regularly upload lecture notes, unit PPTs, and study materials on the vMedulife LMS:</p>"
                    "<ol>"
                    "<li><strong>Login:</strong> Go to the official <a href='https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>KITCoEK VMedulife Portal ↗</a> and log in with your PRN and password.</li>"
                    "<li><strong>Academic Planning:</strong> On the dashboard menu, click on <strong>Academic Planning</strong>.</li>"
                    "<li><strong>Start Learning:</strong> Click on <strong>Start Learning</strong>.</li>"
                    "<li><strong>My Learnings:</strong> Select <strong>My Learnings</strong> to view all enrolled courses and subjects.</li>"
                    "<li><strong>Download Notes:</strong> Click on your subject/course to view, read, or download the uploaded unit lecture notes, presentations, and reference documents.</li>"
                    "</ol>"
                    "<p>Additionally, verified departmental handwritten notes (Statistical Methods Unit 4, SPS Unit 3, etc.) are available on the <a href='https://drive.google.com/drive/folders/1_1mxw4T2BNFCYFOoolsfAmZi8zWvv1Hy' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📁 KITCOEK Subject Notes Google Drive Folder ↗</a>.</p>"
                ),
                "follow_up_questions": [
                    "How to check attendance in VMedulife?",
                    "How to check exam results in VMedulife?",
                    "Statistical Methods Unit 4 notes",
                    "CSBS syllabus"
                ]
            }

        # 6.3 Examination Results, Marks & Grade Cards
        is_result_query = any(w in q_low for w in [
            "result", "results", "mark", "marks", "grade", "grades", "sgpa", "cgpa", "marksheet", "mark sheet",
            "answer sheet", "paper seeing", "review and appeals", "check result", "see result", "view result",
            "exam result", "examination result", "mse result", "ese result", "revaluation", "grievance"
        ])
        if is_result_query:
            return {
                "answer": (
                    "<p><strong>How to Check Examination Results &amp; Marks on KITCoEK VMedulife:</strong></p>"
                    "<p>Official autonomous semester results, marks, and SGPA/CGPA grade sheets are published on the vMedulife student portal:</p>"
                    "<ol>"
                    "<li><strong>Open Portal:</strong> Navigate to the <a href='https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>KITCoEK VMedulife Portal ↗</a>.</li>"
                    "<li><strong>Student Login:</strong> Log in using your Student ID (PRN) and password.</li>"
                    "<li><strong>Assessment / Exam Forms:</strong> On the dashboard, navigate to <strong>Assessment</strong> (or <strong>Exam Forms</strong>).</li>"
                    "<li><strong>View Result:</strong> Select <strong>Result → Result</strong> (or for paper seeing and marks verification, click on <strong>Answer Sheet Review and Appeals</strong>).</li>"
                    "<li><strong>Apply &amp; View:</strong> Select the relevant <strong>Academic Year</strong> and <strong>Semester Term</strong>, then click <strong>Apply / View</strong>. Your complete grade sheet with subject-wise marks and credits will appear.</li>"
                    "</ol>"
                    "<p>For official re-examination schedules, MSE/ESE result notifications, and circulars, you can also check the <a href='https://www.kitcoek.in/notice' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📌 KITCOEK Notice Board (kitcoek.in/notice) ↗</a>.</p>"
                ),
                "follow_up_questions": [
                    "When will MSE results be declared?",
                    "How to check attendance in VMedulife?",
                    "How to check notes in VMedulife?",
                    "Show academic calendar 2026-27"
                ]
            }

        # 6.4 General Student Portal (vMedulife ERP)
        is_portal_query = any(w in q_low for w in ["vmedulife", "student portal", "lms", "vmedu", "erp portal", "hall ticket", "admit card"])
        if is_portal_query:
            return {
                "answer": (
                    "<p><strong>KITCoEK Official Student Portal (vMedulife ERP &amp; LMS):</strong></p>"
                    "<p>The vMedulife portal is the central digital academic platform for all KITCOEK students:</p>"
                    "<ul>"
                    "<li><strong>Direct Portal Login:</strong> <a href='https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>portal.vmedulife.com/public/auth/#/login/kit-kolhapur ↗</a></li>"
                    "<li><strong>Attendance Tracking:</strong> Go to <em>Academic Planning → Attendance</em> (Daily, Weekly, Monthly views).</li>"
                    "<li><strong>Course Notes &amp; LMS:</strong> Go to <em>Academic Planning → Start Learning → My Learnings</em>.</li>"
                    "<li><strong>Exam Results &amp; Grades:</strong> Go to <em>Assessment → Result → Result</em> (SGPA, CGPA, Answer Sheet Reviews).</li>"
                    "<li><strong>Hall Tickets &amp; Exam Forms:</strong> Download MSE / ESE hall tickets prior to examinations.</li>"
                    "</ul>"
                ),
                "follow_up_questions": [
                    "How to check attendance in VMedulife?",
                    "How to access notes in VMedulife?",
                    "How to check exam results in VMedulife?",
                    "Show academic calendar 2026-27"
                ]
            }

        # 6.5 Syllabus & Curriculum Queries
        if any(kw in q_low for kw in ["syllabus", "curriculum", "subject", "subjects", "course structure", "course scheme", "exit courses"]):
            if any(w in q_low for w in ["csbs", "business systems", "computer science and business"]):
                return {
                    "answer": (
                        "<p><strong>Department of Computer Science &amp; Business Systems (CSBS) — Official 2023 [NEP-2020] Curriculum:</strong></p>"
                        "<p>CSBS integrates core computing with enterprise technology, data analytics, and business management:</p>"
                        "<ul>"
                        "<li><strong>All-Year Curriculum Structure:</strong> <a href='https://kitcoek.s3.amazonaws.com/syllabus/CSBS_ALL_Year%20Structure.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Full CSBS 4-Year Structure (PDF) ↗</a></li>"
                        "<li><strong>First Year (F.Y. B.Tech CSBS):</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/FY%20Syllabus.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 F.Y. CSBS Syllabus PDF ↗</a></li>"
                        "<li><strong>Second Year (S.Y. B.Tech CSBS):</strong> <a href='https://kitcoek.s3.amazonaws.com/syllabus/SY%20Syllabus.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 S.Y. CSBS Syllabus PDF ↗</a></li>"
                        "<li><strong>Third Year (T.Y. B.Tech CSBS):</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/TY%20Syllabus.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 T.Y. CSBS Syllabus PDF ↗</a></li>"
                        "<li><strong>Final Year B.Tech CSBS:</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/FINAL%20YEAR%20SYLLABUS.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Final Year CSBS Syllabus PDF ↗</a></li>"
                        "</ul>"
                        "<p>Click any document above to download, or use the interactive download cards below.</p>"
                    ),
                    "follow_up_questions": [
                        "Show me CSBS timetable",
                        "Tell me about CABSSA club",
                        "Where is CBCR classroom?"
                    ]
                }
            elif any(w in q_low for w in ["aiml", "ai & ml", "artificial intelligence"]):
                return {
                    "answer": (
                        "<p><strong>Department of CSE (Artificial Intelligence &amp; Machine Learning) — NEP-2020 Syllabus:</strong></p>"
                        "<ul>"
                        "<li><strong>Second Year (S.Y. Sem 3 &amp; 4):</strong> <a href='https://kitcoek.s3.amazonaws.com/syllabus/2.CSE%20AIML%20SY%20Syllabus%20Sem%203%20to%20Sem%204.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 S.Y. AIML Syllabus PDF ↗</a></li>"
                        "<li><strong>Third Year (T.Y. Sem 5):</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/TY%20CSE(AIML)_syllabus_SEM-V_WEBSITE%20COPY_17%20JUNE%2023.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 T.Y. AIML Syllabus PDF ↗</a></li>"
                        "<li><strong>Honors in Cyber Security:</strong> <a href='https://kitcoek.s3.amazonaws.com/syllabus/B-Tech%20(Hons-)%20CSE(AIML)_Cyber%20Security%20Structure.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Cyber Security Honors Structure ↗</a></li>"
                        "</ul>"
                        "<p>Click any link to download the official PDF directly.</p>"
                    ),
                    "follow_up_questions": [
                        "AIML department timetable",
                        "Where is CSAMCR classroom?",
                        "Tell me about ACSES club"
                    ]
                }
            elif any(w in q_low for w in ["ds", "data science", "aids"]):
                return {
                    "answer": (
                        "<p><strong>Department of CSE (Data Science) — NEP-2020 Syllabus:</strong></p>"
                        "<ul>"
                        "<li><strong>Second Year (S.Y. Sem 3 &amp; 4):</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/SYCSE-DS-Syllabus-28-09-22.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 S.Y. Data Science Syllabus PDF ↗</a></li>"
                        "<li><strong>Third Year (T.Y. Sem 5 &amp; 6):</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/TYCSE(DS)_syllabus_SEM-V_VI_WEBSITE%20COPY_17%20JUNE%2023.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 T.Y. Data Science Syllabus PDF ↗</a></li>"
                        "<li><strong>Honors in Cyber Security:</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/B-%20Tech%20(Hons-)%20Computer%20Science%20and%20Engineering%20(Data%20Science)%20with%20specialization%20in%20cyber%20security.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Honors Specialization Syllabus ↗</a></li>"
                        "</ul>"
                    ),
                    "follow_up_questions": [
                        "Where is CSDSCR classroom?",
                        "Tell me about ACSES club",
                        "Show me BSH First Year timetable"
                    ]
                }
            elif any(w in q_low for w in ["fy", "first year", "f.y.", "bsh", "circuit", "core branch"]):
                return {
                    "answer": (
                        "<p><strong>First Year Engineering (F.Y. B.Tech) — NEP-2020 Syllabus &amp; Structure:</strong></p>"
                        "<ul>"
                        "<li><strong>Circuit Branches (CSE, AIML, DS, ENTC, Electrical):</strong> <a href='https://kitcoek.s3.amazonaws.com/syllabus/FY%20B%20Tech%20Circuit%20Branch_Final%20Structure%20%26%20Syllabus%20New.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Circuit Branches Structure &amp; Syllabus ↗</a></li>"
                        "<li><strong>Core Branches (Biotech, Civil, Mechanical):</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/FY%20B%20Tech%20Core%20Branch_Final%20Structure%20%26%20Syllabus%20New.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Core Branches Structure &amp; Syllabus ↗</a></li>"
                        "<li><strong>UG Academic Rules &amp; Regulations:</strong> <a href='https://www.kitcoek.in/documents/academics/importantDocuments/UG%20ACADEMIC%20RULES%20AND%20REGULATIONS_NEP%202020.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 NEP-2020 Academic Ordinances ↗</a></li>"
                        "</ul>"
                    ),
                    "follow_up_questions": [
                        "Show me BSH First Year timetable",
                        "Where is Central Library?",
                        "How to check attendance in vmedulife"
                    ]
                }
            elif any(w in q_low for w in ["mechanical", "mech", "mccr"]):
                return {
                    "answer": (
                        "<p><strong>Department of Mechanical Engineering — Official NEP-2020 &amp; Autonomous Syllabus:</strong></p>"
                        "<p>Official curriculum documents for Mechanical Engineering sourced directly from <a href='https://www.kitcoek.in/online-syllabus' target='_blank' rel='noopener noreferrer'>kitcoek.in/online-syllabus ↗</a>:</p>"
                        "<ul>"
                        "<li><strong>Second Year (S.Y. B.Tech Mechanical):</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/Mech%20Structure.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 S.Y. Mechanical Structure PDF ↗</a><br><em>Key Subjects: Engineering Thermodynamics, Fluid Mechanics, Strength of Materials, Material Science &amp; Metallurgy, Manufacturing Processes.</em></li>"
                        "<li><strong>Third Year (T.Y. B.Tech Mechanical):</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/MECH_DEPT_TY%20B%20Tech%20_STRUCTURE%20as%20per%20NEP2020_compressed.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 T.Y. Mechanical NEP Structure PDF ↗</a><br><em>Key Subjects: Heat &amp; Mass Transfer, Theory of Machines, Machine Design, Metrology &amp; Quality Control, Turbo Machinery.</em></li>"
                        "<li><strong>Final Year B.Tech Mechanical (NEP-2020 Scheme):</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/FINAL%20YEAR%20BTECH%20MECHANICAL%20STRUCTURE_WEF%20AY%202024-25_compressed.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Final Year NEP Structure PDF ↗</a><br><em>Key Subjects: CAD/CAM/CAE, Industrial Automation, Finite Element Analysis (FEA), Operations Research, Capstone Project.</em></li>"
                        "<li><strong>Final Year Autonomous Structure (Cycle-2):</strong> <a href='https://kitcoek.s3.amazonaws.com/syllabus/REVISED_Final%20Year%20BTECH%20Mechanical%20Autonomous%20Structure.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Autonomous Final Year Structure PDF ↗</a></li>"
                        "<li><strong>First Year Core Engineering Foundation:</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/FY%20B%20Tech%20Core%20Branch_Final%20Structure%20%26%20Syllabus%20New.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Core Branches F.Y. Syllabus PDF ↗</a></li>"
                        "</ul>"
                        "<p>Direct 1-click download buttons are also available in the interactive syllabus card below.</p>"
                    ),
                    "follow_up_questions": [
                        "Tell me about MESA club",
                        "Where is Mechanical Workshop?",
                        "Where is MCCR classroom?"
                    ]
                }
            elif any(w in q_low for w in ["electrical", "elect", "ele", "eecr"]):
                return {
                    "answer": (
                        "<p><strong>Department of Electrical Engineering — Official NEP-2020 &amp; Autonomous Syllabus:</strong></p>"
                        "<p>Official curriculum documents for Electrical Engineering sourced directly from <a href='https://www.kitcoek.in/online-syllabus' target='_blank' rel='noopener noreferrer'>kitcoek.in/online-syllabus ↗</a>:</p>"
                        "<ul>"
                        "<li><strong>Electrical NEP Complete Structure:</strong> <a href='https://kitcoek.s3.amazonaws.com/syllabus/NEP%20STRUCTURE%20ELECTRICAL%20ENGG.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Electrical NEP Complete Structure PDF ↗</a></li>"
                        "<li><strong>Honors in Electric Vehicles (EV):</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/UELHN0351and%20UELHN451-Electric%20Vehicles_compressed.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Electric Vehicles Honors Syllabus PDF ↗</a></li>"
                        "<li><strong>Electric Vehicles Honors Structure:</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/B.Tech%20Honors%20Electric%20Vehicles_structure.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 EV Honors Structure PDF ↗</a></li>"
                        "<li><strong>S.Y. to Final Year Cycle-2 Structure:</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/Revised_Structure_S.Y%20to%20Final%20Year%20B.Tech-Electrical%20Engineering%20w.e.f%202022-23.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 S.Y. to Final Year Structure PDF ↗</a><br><em>Key Subjects: Electrical Machines, Power Systems, Control Systems, Power Electronics, Renewable Energy Systems.</em></li>"
                        "<li><strong>Final Year B.Tech Electrical Syllabus:</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/%28Final%20B.%20Tech-Syllabus%29%28%20Cycle-2%29-Electrical%20Engineering_compressed.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Final Year Electrical Syllabus PDF ↗</a><br><em>Key Subjects: High Voltage Engineering, Smart Grid, Switchgear &amp; Protection, Electrical Drives, Capstone Project.</em></li>"
                        "<li><strong>Electrical NEP Exit Course Syllabus (SY):</strong> <a href='https://kitcoek.s3.amazonaws.com/syllabus/Electrical%20Engineering_NEP%20Exit%20Course%20SY_compressed_compressed%20%282%29%20%281%29.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Electrical NEP Exit Course PDF ↗</a></li>"
                        "</ul>"
                        "<p>Direct download buttons are also available in the interactive syllabus card below.</p>"
                    ),
                    "follow_up_questions": [
                        "Tell me about EESA club",
                        "Where is Electrical Lab?",
                        "Where is EECR classroom?"
                    ]
                }
            elif any(w in q_low for w in ["civil", "environmental", "cvcr"]):
                return {
                    "answer": (
                        "<p><strong>Department of Civil &amp; Environmental Engineering — Official NEP-2020 Syllabus:</strong></p>"
                        "<p>Official curriculum documents for Civil Engineering sourced directly from <a href='https://www.kitcoek.in/online-syllabus' target='_blank' rel='noopener noreferrer'>kitcoek.in/online-syllabus ↗</a>:</p>"
                        "<ul>"
                        "<li><strong>Civil Engineering NEP Complete Structure:</strong> <a href='https://kitcoek.s3.amazonaws.com/syllabus/13.05.2026_B.Tech.%20Civil%20Engineering-Structure%20%28NEP2020%29after%20BoS.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Civil BoS Approved NEP Structure PDF ↗</a></li>"
                        "<li><strong>Second Year (S.Y. B.Tech Civil):</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/16.04.2026_S.Y.B.Tech%20Civil%20Engineering%20Syllabus%20%28NEP2020%29.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 S.Y. Civil Syllabus PDF ↗</a><br><em>Key Subjects: Surveying, Strength of Materials, Fluid Mechanics, Building Construction &amp; Planning, Concrete Technology.</em></li>"
                        "<li><strong>Third Year (T.Y. B.Tech Civil):</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/16.04.2026_T.Y.B.Tech%20Syllabus%20%28NEP2020%29%20%281%29.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 T.Y. Civil Syllabus PDF ↗</a><br><em>Key Subjects: Structural Analysis, Geotechnical Engineering, Environmental Engineering, Transportation Engineering, Design of Steel Structures.</em></li>"
                        "<li><strong>Final Year B.Tech Civil Engineering:</strong> <a href='https://kitcoek.s3.amazonaws.com/syllabus/30.07.2026_Final%20Year%20B.Tech%20Civil%20Engineering_Syllabus%20%28NEP2020%29%20after%20BoS.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Final Year Civil Syllabus PDF ↗</a><br><em>Key Subjects: Design of Concrete Structures, Water Resources Engineering, Construction Management, Quantity Surveying &amp; Valuation, Capstone Project.</em></li>"
                        "<li><strong>Civil Honors (Strategic Civil Infrastructure):</strong> <a href='https://kitcoek.s3.amazonaws.com/syllabus/HONORS%20%28STRATEGIC%20CIVIL%20INFRASTRUCTURE%29_Syllabus%20%28NEP2020%29.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Strategic Civil Infrastructure Honors PDF ↗</a></li>"
                        "<li><strong>Civil Emerging Minor (Lean Technology):</strong> <a href='https://kitcoek.s3.amazonaws.com/syllabus/EMERGING%20SPECIALIZATION%20MINOR%20%28LEAN%20TECHNOLOGY%29_Syllabus%20%28NEP2020%29.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Lean Technology Minor PDF ↗</a></li>"
                        "</ul>"
                        "<p>Direct download buttons are also available in the interactive syllabus card below.</p>"
                    ),
                    "follow_up_questions": [
                        "Tell me about CESA club",
                        "Where is Environmental Lab?",
                        "Where is CVCR classroom?"
                    ]
                }
            elif any(w in q_low for w in ["etc", "entc", "telecom", "etcr", "electronics & telecomm", "electronics and telecomm"]):
                return {
                    "answer": (
                        "<p><strong>Department of Electronics &amp; Telecommunication Engineering (ETC / ENTC) — Official NEP-2020 Syllabus:</strong></p>"
                        "<p>Official curriculum documents for ETC Engineering sourced directly from <a href='https://www.kitcoek.in/online-syllabus' target='_blank' rel='noopener noreferrer'>kitcoek.in/online-syllabus ↗</a>:</p>"
                        "<ul>"
                        "<li><strong>ETC NEP Complete Structure:</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/FINAL-NEP-STructure.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 ETC NEP Complete Structure PDF ↗</a></li>"
                        "<li><strong>Second Year (S.Y. B.Tech ETC):</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/NEP%20STructure%2B%20SY%20Syllabus_compressed.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 S.Y. ETC Syllabus PDF ↗</a><br><em>Key Subjects: Electronic Devices &amp; Circuits, Signals &amp; Systems, Digital Logic Design, Network Theory, Analog Circuits.</em></li>"
                        "<li><strong>Third Year (T.Y. B.Tech ETC):</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/NEP%2BThird%20Year_compressed.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 T.Y. ETC Syllabus PDF ↗</a><br><em>Key Subjects: Microcontrollers &amp; Embedded Systems, Digital Signal Processing (DSP), Electromagnetic Waves, Analog &amp; Digital Communication.</em></li>"
                        "<li><strong>Final Year B.Tech ETC:</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/NEP%20structure%2BFinal%20Year%20Syllabus_compressed.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Final Year ETC Syllabus PDF ↗</a><br><em>Key Subjects: VLSI Design, Microwave &amp; Antenna Theory, Optical Fiber Communication, Wireless Cellular Networks, Capstone Project.</em></li>"
                        "<li><strong>B.Tech Honors in Internet of Things (IoT):</strong> <a href='https://kitcoek.s3.amazonaws.com/syllabus/structure%20and%20syllabus%20of%20Btech%20%28Hons%29.%20of%20ETC%20DEPT.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Honors IoT Specialization Structure &amp; Syllabus PDF ↗</a></li>"
                        "</ul>"
                        "<p>Direct download buttons are also available in the interactive syllabus card below.</p>"
                    ),
                    "follow_up_questions": [
                        "Tell me about ELECSA club",
                        "Where is ETC Seminar Hall?",
                        "Where is ETCR classroom?"
                    ]
                }
            elif any(w in q_low for w in ["biotech", "biotechnology"]):
                return {
                    "answer": (
                        "<p><strong>Department of Biotechnology Engineering — Syllabus:</strong></p>"
                        "<ul>"
                        "<li><strong>Second Year (S.Y. B.Tech Biotech):</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/SY%20BTech%20syllabus%20contents%202022-23.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 S.Y. Biotech Syllabus PDF ↗</a></li>"
                        "<li><strong>Third Year (T.Y. B.Tech Biotech):</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/TY%20BTech%20syllabus%20contents%202023-24.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 T.Y. Biotech Syllabus PDF ↗</a></li>"
                        "<li><strong>Biotechnology 2nd Cycle Structure:</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/Autonomy%202nd%20Cycle%20Structure%20Biotech%20%20wef%202022-23.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Biotech Structure &amp; Scheme ↗</a></li>"
                        "</ul>"
                    ),
                    "follow_up_questions": [
                        "Where is Biotechnology Lab?",
                        "Tell me about ISTE club",
                        "Show me BSH First Year timetable"
                    ]
                }
            elif any(w in q_low for w in ["cse", "computer science", "cscr"]):
                return {
                    "answer": (
                        "<p><strong>Department of Computer Science &amp; Engineering (CSE) — Syllabus &amp; Curriculum:</strong></p>"
                        "<p>The CSE curriculum is autonomous and aligned with the official 2023 [NEP-2020] Scheme.</p>"
                        "<ul>"
                        "<li><strong>Second Year (S.Y. B.Tech CSE):</strong> <a href='https://kitcoek.s3.amazonaws.com/syllabus/SY-CSE-AY-2022-23-Syllabus%20-%20updatged_CO_PO.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 S.Y. CSE Syllabus PDF ↗</a><br><em>Key Subjects: Discrete Mathematics, Data Structures &amp; Algorithms, OOP with Java/C++, Computer Organization &amp; Architecture.</em></li>"
                        "<li><strong>Third Year (T.Y. B.Tech CSE):</strong> <a href='https://kitcoek.s3.amazonaws.com/syllabus/TY-CSE-Syllabus-AY-2023-24%20-%20updated%20copy%2025.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 T.Y. CSE Syllabus PDF ↗</a><br><em>Key Subjects: DBMS, Design &amp; Analysis of Algorithms, Operating Systems, Machine Learning, Computer Networks.</em></li>"
                        "<li><strong>Final Year B.Tech CSE:</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/2017-FinalYear_Old_syllabus.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Final Year CSE Syllabus PDF ↗</a><br><em>Key Subjects: Cloud Computing, Distributed Systems, Information Security, Capstone Project.</em></li>"
                        "<li><strong>Complete Curriculum Structure:</strong> <a href='https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/Structure4Web_AY2324.pdf' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>📄 Full CSE Structure (PDF) ↗</a></li>"
                        "</ul>"
                        "<p>Direct download buttons are also available in the interactive syllabus card below.</p>"
                    ),
                    "follow_up_questions": [
                        "Show me AIML syllabus",
                        "Show me CSBS syllabus",
                        "BSH first year time table",
                        "Where is Central Library?"
                    ]
                }
            else:
                # General institute syllabus directory
                return {
                    "answer": (
                        "<p><strong>Official KITCOEK Online Syllabus Directory:</strong></p>"
                        "<p>KITCOEK provides official autonomous NEP-2020 curriculum structures and syllabi for all departments at <a href='https://www.kitcoek.in/online-syllabus' target='_blank' rel='noopener noreferrer' class='chat-inline-link'>kitcoek.in/online-syllabus ↗</a>.</p>"
                        "<p>Select your branch to view detailed subjects and download official PDFs:</p>"
                        "<ul>"
                        "<li><strong>Computer Science (CSE):</strong> Ask <em>\"CSE syllabus\"</em> for S.Y., T.Y., and Final Year.</li>"
                        "<li><strong>CSBS:</strong> Ask <em>\"CSBS syllabus\"</em> for 4-year curriculum.</li>"
                        "<li><strong>AIML:</strong> Ask <em>\"AIML syllabus\"</em> for S.Y. &amp; T.Y. schemes.</li>"
                        "<li><strong>Data Science (DS):</strong> Ask <em>\"Data Science syllabus\"</em> for S.Y. &amp; T.Y. schemes.</li>"
                        "<li><strong>Mechanical:</strong> Ask <em>\"Mechanical syllabus\"</em> for S.Y., T.Y. &amp; Final Year NEP.</li>"
                        "<li><strong>Electrical:</strong> Ask <em>\"Electrical syllabus\"</em> for NEP structure &amp; EV Honors.</li>"
                        "<li><strong>Civil:</strong> Ask <em>\"Civil syllabus\"</em> for BoS approved NEP structure.</li>"
                        "<li><strong>ETC / ENTC:</strong> Ask <em>\"ETC syllabus\"</em> for NEP structure &amp; IoT Honors.</li>"
                        "<li><strong>Biotechnology:</strong> Ask <em>\"Biotech syllabus\"</em> for S.Y. &amp; T.Y. schemes.</li>"
                        "<li><strong>First Year:</strong> Ask <em>\"First Year syllabus\"</em> for Circuit &amp; Core branches.</li>"
                        "</ul>"
                        "<p>Direct download buttons for key structures are also available in the interactive card below.</p>"
                    ),
                    "follow_up_questions": [
                        "Show me Mechanical syllabus",
                        "Show me Electrical syllabus",
                        "Show me Civil syllabus",
                        "Show me ETC syllabus"
                    ]
                }

        # 7. Document RAG chunks synthesis
        if context_chunks:
            # Filter out club activity report chunks if query is not explicitly asking about clubs
            valid_chunks = context_chunks
            is_club_q = any(k in q_low for k in ["club", "iste", "ecell", "mesa", "cesa", "elesa", "assets", "acses", "cabssa", "meraki", "gathering", "nss", "ncc", "shourya", "rotaract", "swe", "www"])
            if not is_club_q:
                valid_chunks = [c for c in context_chunks if "OFFICIAL ACTIVITY REPORT" not in c and "officer making" not in c.lower() and "Activity Report" not in c]

            clean_chunks = []
            for c in valid_chunks[:3]:
                clean = re.sub(r'===.*?===', '', c).strip()
                clean = re.sub(r'\[Extract \d+\]:', '', clean).strip()
                if clean and len(clean) > 30:
                    clean_chunks.append(clean)
            
            if clean_chunks:
                first = clean_chunks[0]
                paragraphs = [p.strip() for p in first.split("\n") if p.strip()]
                linkified_paragraphs = []
                for p in paragraphs[:5]:
                    def repl_link(m):
                        url = m.group(1).rstrip('.,;:)]>')
                        is_pdf = '.pdf' in url.lower()
                        lbl = '📄 Download Syllabus PDF ↗' if is_pdf else f'{url} ↗'
                        return f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="chat-inline-link">{lbl}</a>'
                    p_linked = re.sub(r'(https?://[^\s<>"]+)', repl_link, p)
                    linkified_paragraphs.append(f"<p>{p_linked}</p>")
                formatted = "".join(linkified_paragraphs)
                return {
                    "answer": formatted,
                    "follow_up_questions": [
                        "Where can I view more details?",
                        "Contact student section",
                        "View official notices"
                    ]
                }

        # 8. Polite general guidance fallback
        return {
            "answer": (
                "<p>I searched the official <strong>KITCoEK Knowledge Base</strong> for your query, but could not find a direct matching record.</p>"
                "<p>You can try asking in a different way or check out one of the direct sections below:</p>"
                "<ul>"
                "<li>🗺️ <strong>Campus Navigation:</strong> <em>\"Where is [room / lab / department]?\"</em></li>"
                "<li>📚 <strong>Syllabus:</strong> <em>\"Give me CSBS syllabus\"</em></li>"
                "<li>📅 <strong>Timetables:</strong> <em>\"BSH First Year timetable\"</em> or <em>\"AIML timetable\"</em></li>"
                "<li>🏛️ <strong>Clubs:</strong> <em>\"Tell me about ISTE / E-Cell / Cultural club\"</em></li>"
                "<li>🎓 <strong>VMedulife:</strong> <em>\"How to check attendance in VMedulife?\"</em></li>"
                "</ul>"
                "<p>You can also check the official institute portal at <a href='https://www.kitcoek.in' target='_blank'>kitcoek.in ↗</a>.</p>"
            ),
            "follow_up_questions": [
                "Where is ETC Seminar Hall?",
                "Give me CSBS syllabus link",
                "BSH first year time table",
                "Tell me about ISTE club"
            ]
        }


_gemini_service = None

def get_gemini_service() -> GeminiService:
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
