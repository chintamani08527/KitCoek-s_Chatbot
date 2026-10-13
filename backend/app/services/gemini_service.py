import json
import re
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types
from backend.app.core.config import settings

class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.client = None
        if self.api_key and self.api_key.strip() and self.api_key != "your_gemini_api_key_here":
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[Warning] Failed to initialize Gemini Client: {e}")

    def is_configured(self) -> bool:
        return self.client is not None

    def classify_query(self, query: str) -> Dict[str, Any]:
        """
        Classifies query into:
        - category: 'academic', 'navigation', 'rules', 'general_college', 'out_of_scope'
        - is_relevant: bool
        """
        nav_keywords = [
            "where is", "how to reach", "location of", "direction", "floor", "building",
            "room", "classroom", "lab", "cbcr", "canteen", "library location", "office location",
            "department location", "where can i find"
        ]
        q_lower = query.lower()
        if any(kw in q_lower for kw in nav_keywords):
            return {"category": "navigation", "is_relevant": True}

        # Fast heuristic for unrelated out-of-scope queries to save network calls
        unrelated_topics = [
            "recipe", "cake", "bake", "cook", "movie", "film", "actor", "bitcoin", "crypto",
            "stock market", "football", "cricket match", "weather in", "song", "lyrics", "game"
        ]
        if any(topic in q_lower for topic in unrelated_topics):
            # Double check it doesn't mention college
            if not any(c in q_lower for c in ["kit", "college", "campus", "engineering", "dept", "exam"]):
                return {"category": "out_of_scope", "is_relevant": False}

        club_keywords = [
            "club", "clubs", "iste", "e-cell", "ecell", "mavericks", "sdc", "amateur writers",
            "ebsb", "cultural club", "aura", "shourya", "wdgec", "women development", "rotaract",
            "swe", "www", "walk with world", "ncc", "nss", "lead india", "petrichor", "induction",
            "sip", "student activities", "hackathon", "meraki", "pioneer", "vidman", "prarambha"
        ]
        if any(w in q_lower for w in club_keywords):
            return {"category": "clubs", "is_relevant": True}

        college_keywords = [
            "kit", "kitcoek", "syllabus", "subject", "semester", "sem", "nep", "exam", "course",
            "unit", "notes", "passing", "grade", "credits", "result", "results", "marks", "prn", "admission", "fee",
            "scholarship", "hostel", "mess", "faculty", "hod", "department", "lab", "classroom",
            "cbcr", "cscr", "mccr", "library", "canteen", "attendance", "placement", "rules",
            "portal", "student portal", "lms", "vmedulife", "sgpa", "cgpa", "studentsummary",
            "timetable", "time table", "schedule", "sps", "statistical methods", "handwritten notes", "handwritten", "variance"
        ]
        if any(w in q_lower for w in college_keywords):
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
6. STUDENT PORTAL, RESULTS, AND LMS:
   When the student asks about examination results, marks, semester grades (SGPA/CGPA), student portal, ERP, or LMS (Learning Management System):
   - ALWAYS provide the official KITCOEK vMedulife Student Portal login link: <a href="https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur" target="_blank">🔗 KITCOEK Student Portal (vMedulife)</a>
   - Provide related context:
     * vMedulife is KITCOEK's centralized student ERP and LMS platform.
     * Students can log in using their PRN and portal password to view semester examination results & grade cards, internal assessment marks (ISE/MSE/ESE), daily attendance records, and exam hall tickets.
     * Through the LMS module, students can access subject learning resources, lecture notes, syllabus materials, and assignment submissions.
7. STUDENT NOTES & TIMETABLES (PUBLIC GOOGLE DRIVE REPOSITORY):
   When the student asks about subject notes, handwritten notes, study materials, or timetables / class schedules:
   - For NOTES queries:
     * DIRECTLY provide the specific PDF links:
       - Statistical Methods (Unit 4: Analysis of Variance): <a href="https://drive.google.com/file/d/1Iw8r8ht5fseg3yeCWbjCXsr_J7a4nQYZ/view" target="_blank">📄 Statistical Methods - Unit 4: Analysis of Variance (PDF)</a>
       - SPS (Unit 3 Notes): <a href="https://drive.google.com/file/d/1DCB3nY6wc5BF3QJHxMDCOeZtsVIWsC2f/view" target="_blank">📄 SPS - Unit 3 Notes (PDF)</a>
       - Browse All Subject Notes in Drive: <a href="https://drive.google.com/drive/folders/1_1mxw4T2BNFCYFOoolsfAmZi8zWvv1Hy" target="_blank">📁 View All Subject Notes in Drive</a>
   - For TIMETABLE queries:
     * DIRECTLY provide the department timetable file link:
       - CSBS Department Timetable (SY, TY, Final Year): <a href="https://drive.google.com/file/d/1Yr3fsic12RvEHj1pZzGjgeFl3yDTO0O3/view" target="_blank">📅 CSBS Timetable (SY, TY, Final Year)</a>
       - Browse All Department Timetables in Drive: <a href="https://drive.google.com/drive/folders/1Pi-i10qYtu9LQkhzhIMXQOtOa8LLCKZT" target="_blank">📁 View All Department Timetables in Drive</a>
8. CAMPUS LOCATIONS & ABBREVIATIONS:
   - In the IMER Building on the Third Floor, **CBCR** stands for **Computer Science and Business Systems (CSBS)** Classrooms (CBCR 01, CBCR 02, CBCR 03, CBCR 04, CBCR 05).
   - IMER Building Floor Allocation:
     * Ground Floor: ETCR 04 (MBA)
     * First Floor: CSAMCR 01 (CSE AIML), CSDSCR 01 (CSE Data Science), ETCR 03
     * Second Floor: CSAMCR 02, 03, 04 (CSE AIML), CSDSCR 02, 03 (CSE Data Science)
     * Third Floor: CBCR 01, CBCR 02, CBCR 03, CBCR 04, CBCR 05 (Computer Science and Business Systems / CSBS)
9. Format your answer in clean HTML suitable for the chat bubble (use <p>, <ul>, <li>, <strong>, <em>, <a>).
10. Provide 2 to 3 relevant follow-up questions related to KITCOEK.

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
                    response = self.client.models.generate_content(
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

            data = json.loads(response.text.strip())
            return {
                "answer": data.get("answer", "<p>No response generated.</p>"),
                "follow_up_questions": data.get("follow_up_questions", [])
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
