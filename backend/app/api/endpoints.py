import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.models.models import DocumentRecord, ChatHistory, CampusLocation, StudentClub
from backend.app.schemas.schemas import (
    ChatRequest, ChatResponse, SourceCitation,
    LocationCreate, LocationResponse, DocumentResponse,
    StudentClubResponse, ClubCategorySummary
)
from backend.app.services.vector_store import get_vector_store
from backend.app.services.gemini_service import get_gemini_service
from backend.app.services.document_processor import extract_text_from_file, chunk_text
from backend.app.services.notice_service import notice_service
import uuid
import os

router = APIRouter()

MERAKI_REELS = [
    {"title": "Meraki Flagship Gathering Highlights", "url": "https://www.instagram.com/reel/DdTvWmjMfM0", "tag": "Reel 1"},
    {"title": "Meraki Cultural Performances & Dance", "url": "https://www.instagram.com/reel/DUxDO-CEZxu", "tag": "Reel 2"},
    {"title": "Meraki Campus Celebrations & Vibes", "url": "https://www.instagram.com/reel/DU5NbRZDP7W", "tag": "Reel 3"},
    {"title": "Meraki Grand Stage Gathering", "url": "https://www.instagram.com/reel/DVNPAWGCMNK", "tag": "Reel 4"},
    {"title": "Meraki Annual Gathering Celebration", "url": "https://www.instagram.com/reel/DVH9-UiiEoj", "tag": "Reel 5"}
]

CSBS_SYLLABUS_DATA = {
    "department": "Computer Science and Business Systems (CSBS)",
    "portal_url": "https://www.kitcoek.in/online-syllabus",
    "scheme": "2023 [NEP-2020] Scheme",
    "structure_url": "https://kitcoek.s3.amazonaws.com/syllabus/CSBS_ALL_Year%20Structure.pdf",
    "years": [
        {
            "year": "All-Year Curriculum Structure",
            "tag": "NEP-2020 Scheme",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/CSBS_ALL_Year%20Structure.pdf",
            "description": "Complete 4-year, 8-semester credit system, course codes, teaching & evaluation schemes."
        },
        {
            "year": "First Year (F.Y. B.Tech CSBS)",
            "tag": "2023 [NEP-2020]",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/FY%20Syllabus.pdf",
            "exit_courses_url": "https://kitcoek.s3.amazonaws.com/syllabus/exit%20courses_syllabus%20with%20stamp.pdf",
            "description": "Fundamentals of Computer Science, Discrete Mathematics, Electrical Principles, Physics for Computing Science, Statistics & Probability, Business Communication & Value Science."
        },
        {
            "year": "Second Year (S.Y. B.Tech CSBS)",
            "tag": "2023 [NEP-2020]",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/SY%20Syllabus.pdf",
            "honours_url": "https://kitcoek.s3.amazonaws.com/syllabus/Honours%20Syllabus.pdf",
            "mdm_url": "https://kitcoek.s3.amazonaws.com/syllabus/MDM_SYLLABUS_FINAL.pdf",
            "ar_vr_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/Emerging%20trend%20Syllabus%20with%20Stamp.pdf",
            "description": "Formal Language & Automata Theory, Computer Organization, Computational Statistics, OOP (Java/C++), Operating Systems, DBMS, Software Engineering, Marketing, Cost Accounting."
        },
        {
            "year": "Third Year (T.Y. B.Tech CSBS)",
            "tag": "2023 [NEP-2020]",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/TY%20Syllabus.pdf",
            "honours_url": "https://kitcoek.s3.amazonaws.com/syllabus/Honours%20Syllabus.pdf",
            "mdm_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/MDM_SYLLABUS_FINAL.pdf",
            "ar_vr_url": "https://kitcoek.s3.amazonaws.com/syllabus/AR%20VR%20syllabus.pdf",
            "description": "Design & Analysis of Algorithms (DAA), Compiler Design, Business Strategy, Computer Networks, Machine Learning, Information Security, Consumer Behaviour."
        },
        {
            "year": "Final Year (Final Year B.Tech CSBS)",
            "tag": "2023 [NEP-2020]",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/FINAL%20YEAR%20SYLLABUS.pdf",
            "honours_url": "https://kitcoek.s3.amazonaws.com/syllabus/Honours%20Syllabus.pdf",
            "mdm_url": "https://kitcoek.s3.amazonaws.com/syllabus/MDM_SYLLABUS_FINAL.pdf",
            "description": "Cloud Computing, Software Testing & QA, Financial Management, Professional Electives (Deep Learning, IoT, Image Processing), Capstone Project / Industry Internship."
        }
    ]
}

TIMETABLES_DATA = {
    "title": "KITCOEK Systematic Department Timetables",
    "drive_folder_url": "https://drive.google.com/drive/folders/1Pi-i10qYtu9LQkhzhIMXQOtOa8LLCKZT",
    "departments": [
        {
            "id": "bsh",
            "code": "BSH",
            "name": "Basic Sciences & Humanities (BSH)",
            "years": "First Year (F.Y. B.Tech)",
            "url": "https://drive.google.com/drive/folders/1Pi-i10qYtu9LQkhzhIMXQOtOa8LLCKZT",
            "badge": "F.Y. B.Tech",
            "icon": "🎓",
            "description": "First Year engineering lecture & practical schedules across all divisions."
        },
        {
            "id": "aiml",
            "code": "AIML",
            "name": "Artificial Intelligence & Machine Learning (AIML)",
            "years": "S.Y., T.Y., & Final Year",
            "url": "https://drive.google.com/drive/folders/1Pi-i10qYtu9LQkhzhIMXQOtOa8LLCKZT",
            "badge": "SY • TY • Final Year",
            "icon": "🤖",
            "description": "S.Y., T.Y., and Final Year class schedules, lecture timings & lab batches."
        },
        {
            "id": "csbs",
            "code": "CSBS",
            "name": "Computer Science & Business Systems (CSBS)",
            "years": "S.Y., T.Y., & Final Year",
            "url": "https://drive.google.com/file/d/1Yr3fsic12RvEHj1pZzGjgeFl3yDTO0O3/view",
            "badge": "SY • TY • Final Year",
            "icon": "💼",
            "description": "Verified semester schedule & classroom lecture allocations for CSBS."
        }
    ]
}

def format_club_dict(club: StudentClub) -> dict:
    d = {
        "id": club.id,
        "name": club.name,
        "abbr": club.abbr,
        "category": club.category,
        "tagline": club.tagline,
        "establishment_year": club.establishment_year,
        "description": club.description,
        "objectives": json.loads(club.objectives) if club.objectives and club.objectives.startswith("[") else club.objectives,
        "major_activities": json.loads(club.major_activities) if club.major_activities and club.major_activities.startswith("[") else club.major_activities,
        "skills_developed": json.loads(club.skills_developed) if club.skills_developed and club.skills_developed.startswith("[") else club.skills_developed,
        "eligibility": club.eligibility,
        "faculty_coordinator": club.faculty_coordinator,
        "student_coordinators": club.student_coordinators,
        "achievements": club.achievements,
        "academic_year": club.academic_year,
        "source_url": club.source_url,
        "pdf_url": club.pdf_url,
        "department": getattr(club, "department", None),
        "website_url": getattr(club, "website_url", None)
    }
    if club.id == "cultural_club":
        d["meraki_reels"] = MERAKI_REELS
    return d

# In-memory response cache for frequent / repeated student questions
_chat_cache = {}

@router.post("/chat", response_model=ChatResponse)
def handle_chat(req: ChatRequest, db: Session = Depends(get_db)):
    gemini = get_gemini_service()
    vs = get_vector_store()
    
    query = req.message.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
        
    q_key = query.lower()
    if q_key in _chat_cache:
        return _chat_cache[q_key]
        
    # 1. Query Classification and scope check
    classification = gemini.classify_query(query)
    category = classification.get("category", "academic")
    is_relevant = classification.get("is_relevant", True)
    
    if not is_relevant:
        out_msg = (
            "<p>I am the official <strong>KITCOEK AI Assistant</strong>. "
            "I can only help you with questions related to KITCOEK campus, engineering academics, "
            "NEP-2020 syllabus, subjects, examinations, campus locations, and official Student Clubs. "
            "Please ask a question about KITCOEK.</p>"
        )
        return ChatResponse(
            reply=out_msg,
            category="out_of_scope",
            sources=[],
            follow_up_questions=[
                "What student clubs are available at KIT?",
                "Which clubs are related to coding and AI?",
                "What is the NEP-2020 syllabus for CSE?"
            ]
        )

    # 2. Location retrieval strictly for classrooms, physical facilities, and map navigation
    matched_loc_data = None
    map_url = None
    q_low = query.lower()

    # Check if query is primarily about documents/schedules rather than physical rooms
    is_doc_or_academic_query = any(k in q_low for k in [
        "timetable", "time table", "schedule", "syllabus", "curriculum", "unit",
        "notes", "handwritten", "result", "results", "marks", "grade", "grades",
        "portal", "lms", "vmedulife", "admission", "scholarship", "fee", "fees"
    ])

    classroom_codes = [
        "cbcr", "cscr", "mccr", "bshcr", "csamcr", "csdscr", "etcr", "btcr", "eecr", "cvcr"
    ]
    has_classroom_code = any(code in q_low for code in classroom_codes)
    has_map_or_nav_keyword = any(k in q_low for k in [
        "campus map", "aerial map", "map", "layout", "classroom", "class room",
        "where is classroom", "where is room", "which floor", "which building",
        "how to reach", "directions to", "where is the library", "where is the canteen"
    ])

    # Only look up locations if user explicitly asks about a room code, physical navigation, or map,
    # and NOT for purely document/academic requests (unless a room code is mentioned)
    should_check_location = (has_classroom_code or has_map_or_nav_keyword or category == "navigation") and not (
        is_doc_or_academic_query and not has_classroom_code and "map" not in q_low
    )

    if should_check_location:
        locations = db.query(CampusLocation).all()
        q_clean = q_low.replace("-", " ")
        q_tokens = [t for t in q_clean.split() if len(t) >= 3]
        
        # Stop words that should NEVER trigger a location match by themselves
        loc_stopwords = {
            "where", "what", "which", "floor", "room", "located", "hall",
            "department", "dept", "find", "can", "show", "tell", "give",
            "please", "about", "the", "for", "and", "syllabus", "timetable",
            "schedule", "notes", "result", "results", "portal", "help",
            "engineering", "college", "campus"
        }

        for loc in locations:
            loc_name_lower = loc.name.lower()
            loc_rooms_lower = (loc.room_number or "").lower().replace("-", " ")
            
            # 1. Direct classroom code match
            direct_code_match = any(code in q_low for code in classroom_codes if code in loc_rooms_lower or code in loc_name_lower)
            
            # 2. Key facility match (library, canteen, imer, auditorium, seminar hall, etc.)
            facility_match = any(
                fac in q_low and fac in loc_name_lower
                for fac in ["library", "canteen", "imer", "biotechnology", "seminar hall", "civil model", "geotech", "transportation"]
            )
            if "mechanical" in q_low and "mechanical" in loc_name_lower:
                if any(w in q_low for w in ["building", "lab", "laboratory", "mccr", "room", "floor", "where"]):
                    facility_match = True

            # 3. Meaningful token match
            meaningful_tokens = [tok for tok in q_tokens if tok not in loc_stopwords]
            token_match = any(tok in loc_rooms_lower or (len(tok) >= 4 and tok in loc_name_lower and tok not in ["science", "computer", "systems", "building"]) for tok in meaningful_tokens)

            if direct_code_match or facility_match or token_match:
                matched_loc_data = {
                    "name": loc.name,
                    "category": loc.category,
                    "building": loc.building,
                    "floor": loc.floor,
                    "room_number": loc.room_number,
                    "landmark": loc.landmark,
                    "description": loc.description
                }
                map_url = "/api/locations/map"
                break

        if not matched_loc_data and (
            any(k in q_low for k in ["campus map", "aerial map", "layout map", "the map", "show map", "open map", "view map"])
            or q_low.strip() in ["map", "campus map", "aerial map"]
        ):
            map_url = "/api/locations/map"
            matched_loc_data = {
                "name": "KITCoEK Campus Aerial Layout Map",
                "category": "Navigation",
                "building": "Campus Layout",
                "floor": "All Blocks & Wings",
                "room_number": None,
                "landmark": "North Wing, South Wing, IMER, Mechanical, Library, Biotech & Canteen",
                "description": "Official aerial photo layout of the KITCoEK campus showing all academic buildings, departments, and classroom blocks."
            }

    # 3. Student Clubs matching & context retrieval
    matched_club_data = None
    clubs_dir_summary = None
    
    is_club_intent = category == "clubs" or any(kw in q_low for kw in [
        "club", "clubs", "iste", "e-cell", "ecell", "mavericks", "sdc", "amateur", "writers",
        "ebsb", "cultural", "aura", "shourya", "wdgec", "women development", "rotaract",
        "swe", "www", "walk with world", "ncc", "nss", "lead india", "petrichor", "induction",
        "sip", "coding", "entrepreneurship", "art", "dance", "drama", "debate", "mun"
    ])

    if is_club_intent:
        category = "clubs"
        all_clubs = db.query(StudentClub).all()
        
        # Check if a specific club is directly targeted
        for club in all_clubs:
            club_terms = [
                club.id,
                club.name.lower(),
                (club.abbr or "").lower(),
                club.id.replace("_", " ")
            ]
            if club.id == "e_cell":
                club_terms.extend(["e-cell", "ecell", "entrepreneurship cell"])
            elif club.id == "iste":
                club_terms.extend(["iste", "technical education"])
            elif club.id == "sdc":
                club_terms.extend(["sdc", "developer", "developers club"])
            elif club.id == "team_mavericks":
                club_terms.extend(["maverick", "mavericks"])
            elif club.id == "amateur_writers":
                club_terms.extend(["amateur", "writers club", "awc"])
            elif club.id == "aura":
                club_terms.extend(["aura", "art club"])
            elif club.id == "cultural_club":
                club_terms.extend(["cultural club", "meraki", "cultural committee", "gathering", "annual gathering", "cultural fest", "reels", "insta reels"])
            elif club.id == "ncc":
                club_terms.extend(["ncc", "cadet", "cadets", "1 mah arty"])
            elif club.id == "nss":
                club_terms.extend(["nss", "national service scheme"])
            elif club.id == "rotaract":
                club_terms.extend(["rotaract", "sunshine"])
            elif club.id == "swe":
                club_terms.extend(["swe", "society of women engineers"])
            elif club.id == "www":
                club_terms.extend(["www", "walk with world", "sprinters"])
            elif club.id == "shourya":
                club_terms.extend(["shourya", "officer making"])
            elif club.id == "petrichor":
                club_terms.extend(["petrichor", "green club", "unicef"])
            elif club.id == "lead_india":
                club_terms.extend(["lead india", "upsc", "mpsc", "vidman"])
            elif club.id == "women_dev_cell":
                club_terms.extend(["women development", "gender equality", "wdgec"])
            elif club.id == "fy_induction":
                club_terms.extend(["induction", "sip", "first year induction"])
            elif club.id == "mesa":
                club_terms.extend(["mesa", "mechanical engineering students association", "battle of wits", "mechanical club"])
            elif club.id == "cesa":
                club_terms.extend(["cesa", "civil engineering students association", "civil safari", "civil club"])
            elif club.id == "elesa":
                club_terms.extend(["elesa", "electrical engineering students association", "dive in circuit", "electrical club"])
            elif club.id == "assets":
                club_terms.extend(["assets", "assets club", "entc club", "electronics and telecommunication", "telecom club"])
            elif club.id == "acses":
                club_terms.extend(["acses", "association of computer science", "codewizard", "cse club", "computer science club"])
            elif club.id == "cabssa":
                club_terms.extend(["cabssa", "tech negotia", "tech-negotia", "csbs club", "computer science and business systems"])
            elif club.id == "bytearq":
                club_terms.extend(["bytearq", "byteark", "byte arq", "csbs coding club", "csbs technical wing"])

            if any(term in q_low for term in club_terms if len(term) >= 3):
                matched_club_data = format_club_dict(club)
                break

        # If asking general questions (e.g. list all, count, recommendations), provide complete directory
        if any(w in q_low for w in ["list", "all", "how many", "which club", "recommend", "join", "categories", "options"]):
            clubs_dir_summary = [
                {
                    "id": c.id,
                    "name": c.name,
                    "abbr": c.abbr,
                    "category": c.category,
                    "tagline": c.tagline,
                    "coordinator": c.faculty_coordinator,
                    "pdf_url": c.pdf_url
                }
                for c in all_clubs
            ]

    # 3.5 Student Portal, Results, Notes (My Learnings) & Attendance detection (VMedulife)
    portal_url = None
    vmedulife_guide = None

    is_result_intent = any(kw in q_low for kw in [
        "result", "results", "marks", "grade", "grades", "sgpa", "cgpa", "marksheet",
        "answer sheet", "paper seeing", "review and appeals", "check result", "see result", "view result"
    ])
    is_vmedu_notes_intent = any(kw in q_low for kw in [
        "my learnings", "start learning", "learning material", "uploaded by teacher", "teacher notes",
        "vm notes", "vmedulife notes", "syllabus on vmedulife", "course material", "study material uploaded"
    ])
    is_attendance_intent = any(kw in q_low for kw in [
        "attendance", "daily attendance", "weekly attendance", "monthly attendance",
        "absent", "present", "check attendance", "attendance percentage", "classes attended"
    ])
    is_generic_portal_intent = any(kw in q_low for kw in [
        "portal", "student portal", "lms", "vmedulife", "hall ticket", "admit card", "studentsummary"
    ])

    if is_result_intent:
        portal_url = "https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur"
        vmedulife_guide = {
            "type": "result",
            "title": "Steps to Check Result & Answer Sheet Reviews on VMedulife",
            "portal_url": portal_url,
            "steps": [
                "Open the official KITCoEK VMedulife portal link: https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur",
                "If prompted, log in with your student account credentials (PRN and password).",
                "Open Assessment (or Exam Forms, depending on your portal).",
                "Select Result → Result (or if paper is displayed, click on Answer Sheet Review and Appeals).",
                "Select the relevant Academic Year and click Apply, if prompted.",
                "Find your semester's result and click VIEW."
            ]
        }
    elif is_vmedu_notes_intent:
        portal_url = "https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur"
        vmedulife_guide = {
            "type": "notes",
            "title": "Steps to Access 'My Learnings' (Syllabus & Teacher Notes) on VMedulife",
            "portal_url": portal_url,
            "steps": [
                "Open the KITCoEK VMedulife website (https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur) and log in using your student credentials.",
                "On the dashboard, click Academic Planning.",
                "Select Start Learning.",
                "Open My Learnings.",
                "You should now be able to see the learning materials or courses assigned to you.",
                "Click the relevant subject or learning item to open it."
            ]
        }
    elif is_attendance_intent:
        portal_url = "https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur"
        vmedulife_guide = {
            "type": "attendance",
            "title": "Steps to Check Attendance on KITCoEK VMedulife",
            "portal_url": portal_url,
            "steps": [
                "Open the KITCoEK VMedulife website (https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur) and log in with your student ID (PRN) and password.",
                "Go to Academic Planning.",
                "Look for the Attendance option.",
                "Open the attendance section.",
                "Choose the attendance view you want: Daily Attendance, Weekly Attendance, or Monthly Attendance.",
                "Select the required date, week, or month, if prompted.",
                "View your attendance details, including the classes attended and absent, if displayed."
            ]
        }
    elif is_generic_portal_intent:
        portal_url = "https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur"

    # 3.6 Student Notes & Timetables detection
    notes_url = None
    is_notes_intent = any(kw in q_low for kw in [
        "note", "notes", "handwritten", "study material", "unit 4", "unit 3", "variance", "sps", "statistical methods"
    ])
    if is_notes_intent:
        if "statistical" in q_low or "variance" in q_low:
            notes_url = "https://drive.google.com/file/d/1Iw8r8ht5fseg3yeCWbjCXsr_J7a4nQYZ/view"
        elif "sps" in q_low:
            notes_url = "https://drive.google.com/file/d/1DCB3nY6wc5BF3QJHxMDCOeZtsVIWsC2f/view"
        else:
            notes_url = "https://drive.google.com/drive/folders/1_1mxw4T2BNFCYFOoolsfAmZi8zWvv1Hy"

    timetable_url = None
    timetable_details = None
    is_timetable_intent = any(kw in q_low for kw in [
        "timetable", "time table", "time-table", "class schedule", "lecture schedule",
        "class timing", "lecture timing", "bsh schedule", "aiml schedule", "csbs schedule",
        "department timetable", "class timetable", "sy timetable", "ty timetable"
    ]) or (
        any(k in q_low for k in ["bsh", "aiml", "csbs"]) and any(w in q_low for w in ["timing", "schedule", "classes", "lecture", "slot", "slots"])
    )
    if is_timetable_intent:
        category = "academic" if category not in ["navigation", "clubs"] else category
        
        is_bsh = any(k in q_low for k in ["bsh", "basic science", "humanities", "first year", "fy", "f.y", "f.e", "fe"])
        is_aiml = any(k in q_low for k in ["aiml", "ai ml", "ai & ml", "ai and ml", "artificial intelligence", "machine learning"])
        is_csbs = any(k in q_low for k in ["csbs", "computer science and business", "business systems"])
        
        matched_dept_id = "all"
        if is_bsh and not is_aiml and not is_csbs:
            matched_dept_id = "bsh"
            timetable_url = "https://drive.google.com/drive/folders/1Pi-i10qYtu9LQkhzhIMXQOtOa8LLCKZT"
        elif is_aiml and not is_bsh and not is_csbs:
            matched_dept_id = "aiml"
            timetable_url = "https://drive.google.com/drive/folders/1Pi-i10qYtu9LQkhzhIMXQOtOa8LLCKZT"
        elif is_csbs and not is_bsh and not is_aiml:
            matched_dept_id = "csbs"
            timetable_url = "https://drive.google.com/file/d/1Yr3fsic12RvEHj1pZzGjgeFl3yDTO0O3/view"
        else:
            timetable_url = "https://drive.google.com/drive/folders/1Pi-i10qYtu9LQkhzhIMXQOtOa8LLCKZT"

        timetable_details = {
            "requested_dept": matched_dept_id,
            "title": TIMETABLES_DATA["title"],
            "drive_folder_url": TIMETABLES_DATA["drive_folder_url"],
            "departments": [
                {
                    **d,
                    "is_matched": (matched_dept_id == d["id"]) or (matched_dept_id == "all")
                }
                for d in TIMETABLES_DATA["departments"]
            ]
        }

    # 3.7 Official Notice Board & Academic Calendars detection (https://www.kitcoek.in/notice)
    matched_notices = None
    matched_cals = None
    notice_board_url = None

    is_notice_intent = any(kw in q_low for kw in [
        "notice", "notices", "circular", "circulars", "mse", "midsem", "mid sem", "mid semester",
        "academic calendar", "calendar", "calender", "term calendar", "semester calendar",
        "ese exam", "makeup exam", "re-mse", "re exam", "re-exam", "backlog", "back log",
        "hall ticket", "admit card", "paper seeing", "grievance", "exam schedule",
        "commencement", "exam notice", "latest news", "announcement", "announcements"
    ])

    is_pure_portal_guide = bool(vmedulife_guide) and not any(k in q_low for k in [
        "notice", "circular", "calendar", "calender", "timetable", "time table", "mse", "ese", "schedule", "latest"
    ])

    if not is_pure_portal_guide and (is_notice_intent or any(k in q_low for k in ["exam notice", "exam circular", "exam timetable", "exam schedule", "timetable", "time table"])):
        notice_board_url = "https://www.kitcoek.in/notice"
        category = "notices" if is_notice_intent and category not in ["clubs", "navigation"] else category

        # Check if academic calendar specifically requested
        if any(w in q_low for w in ["calendar", "calender", "academic calendar", "term", "academic year", "commencement"]):
            matched_cals = notice_service.get_academic_calendars()

        # Search relevant notices from live kitcoek notice API
        found_notices = notice_service.search_notices(query, limit=5)
        if not found_notices and any(w in q_low for w in ["notice", "notices", "latest", "circular", "announcement", "news"]):
            found_notices = notice_service.get_latest_notices(limit=5)

        if found_notices:
            matched_notices = [
                {
                    "title": n.get("title") or n.get("fileName"),
                    "description": n.get("description"),
                    "date": notice_service.parse_notice_date(n),
                    "file_url": n.get("fileUrl"),
                    "file_name": n.get("fileName")
                }
                for n in found_notices
            ]

    # 3.8 Meraki Flagship Gathering & Instagram Reels detection
    meraki_reels = None
    is_meraki_intent = any(kw in q_low for kw in [
        "meraki", "gathering", "annual gathering", "cultural gathering", "cultural fest",
        "meraki reel", "meraki reels", "gathering reel", "gathering reels", "insta reel", "insta reels",
        "instagram reel", "instagram reels", "meraki video", "meraki videos"
    ])
    if is_meraki_intent:
        meraki_reels = MERAKI_REELS
        category = "clubs" if category not in ["navigation"] else category

    # 3.9 Official KITCOEK Online Syllabus & CSBS NEP-2020 detection (https://www.kitcoek.in/online-syllabus)
    csbs_syllabus = None
    is_csbs_syllabus_intent = (
        ("csbs" in q_low or "computer science and business" in q_low or "business systems" in q_low)
        and any(w in q_low for w in [
            "syllabus", "curriculum", "subject", "subjects", "nep", "course", "courses",
            "online syllabus", "structure", "scheme", "sem", "semester", "fy", "sy", "ty", "final year"
        ])
    ) or (
        any(w in q_low for w in ["online syllabus", "kitcoek.in/online-syllabus"])
        and any(w in q_low for w in ["csbs", "computer science and business"])
    )

    if is_csbs_syllabus_intent:
        csbs_syllabus = CSBS_SYLLABUS_DATA
        category = "academic" if category not in ["navigation", "clubs"] else category

    # 4. RAG Retrieval from Vector Store
    retrieved_chunks = vs.search(query, top_k=5, threshold=0.30)
    context_texts = [r["chunk_text"] for r in retrieved_chunks]

    # Prepend official CSBS NEP-2020 syllabus context if matched
    if csbs_syllabus:
        syllabus_ctx = [
            "OFFICIAL KITCOEK ONLINE SYLLABUS DIRECTORY — CSBS NEP-2020 CURRICULUM (Source: https://www.kitcoek.in/online-syllabus):",
            "College Scheme: 2023 [NEP-2020] Scheme (National Education Policy 2020 Autonomous Scheme).",
            "Department: Computer Science and Business Systems (CSBS).",
            "DIRECT OFFICIAL AWS S3 SYLLABUS PDF DOWNLOAD LINKS:",
            "- All-Year Curriculum Structure (NEP-2020): https://kitcoek.s3.amazonaws.com/syllabus/CSBS_ALL_Year%20Structure.pdf",
            "- First Year (F.Y. B.Tech CSBS): https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/FY%20Syllabus.pdf | Exit Courses: https://kitcoek.s3.amazonaws.com/syllabus/exit%20courses_syllabus%20with%20stamp.pdf",
            "- Second Year (S.Y. B.Tech CSBS): https://kitcoek.s3.amazonaws.com/syllabus/SY%20Syllabus.pdf | Honours: https://kitcoek.s3.amazonaws.com/syllabus/Honours%20Syllabus.pdf | MDM: https://kitcoek.s3.amazonaws.com/syllabus/MDM_SYLLABUS_FINAL.pdf | AR-VR: https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/Emerging%20trend%20Syllabus%20with%20Stamp.pdf",
            "- Third Year (T.Y. B.Tech CSBS): https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/TY%20Syllabus.pdf | Honours: https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/Honours%20Syllabus.pdf | MDM: https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/MDM_SYLLABUS_FINAL.pdf | AR-VR: https://kitcoek.s3.amazonaws.com/syllabus/AR%20VR%20syllabus.pdf",
            "- Final Year (Final Year B.Tech CSBS): https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/FINAL%20YEAR%20SYLLABUS.pdf | Honours: https://kitcoek.s3.amazonaws.com/syllabus/Honours%20Syllabus.pdf | MDM: https://kitcoek.s3.amazonaws.com/syllabus/MDM_SYLLABUS_FINAL.pdf",
            "Key Subjects Breakdown:",
            "  * F.Y. (Sem I & II): Fundamentals of Computer Science, Discrete Mathematics, Principles of Electrical Engineering, Physics for Computing Science, Statistics & Probability, Business Communication & Value Science, Data Structures & Algorithms, Economics.",
            "  * S.Y. (Sem III & IV): Formal Language & Automata Theory, Computer Organization & Architecture, Computational Statistics, Object Oriented Programming (Java/C++), Operating Systems, Database Management Systems, Software Engineering, Fundamentals of Marketing, Financial & Cost Accounting.",
            "  * T.Y. (Sem V & VI): Design & Analysis of Algorithms, Compiler Design, Business Strategy, Computer Networks, Machine Learning, Information Security, Consumer Behaviour.",
            "  * Final Year (Sem VII & VIII): Cloud Computing, Software Testing & Quality Assurance, Financial Management, Deep Learning, IoT, Capstone Projects & Full Semester Industry Internship.",
            "DIRECTIVE: Give a concise, helpful overview confirming that the CSBS syllabus strictly complies with the official KITCoEK 2023 [NEP-2020] Scheme from kitcoek.in/online-syllabus. Highlight the program's blend of core computer science, Business 4.0, analytics, and management. DO NOT output a bullet list of PDF links or repeat the year-by-year syllabus lists in your text, because a dedicated interactive card with verified download buttons for All-Year Structure, FY, SY, TY, Final Year, Honors, and MDM is automatically appended below your answer."
        ]
        context_texts.insert(0, "\n".join(syllabus_ctx))

    # Prepend official Systematic Department Timetable context if matched
    if timetable_details:
        tt_ctx = [
            "OFFICIAL KITCOEK DEPARTMENT TIMETABLE DIRECTORY (Systematic Google Drive Repository):",
            "The institute maintains systematic class timetables for all departments hosted on the official Google Drive repository.",
            "1. BSH Department (Basic Sciences & Humanities / First Year F.Y. B.Tech):",
            "   - Target Academic Year: First Year (F.Y. B.Tech) - All Divisions & Practical Batches.",
            "   - Google Drive Folder Link: https://drive.google.com/drive/folders/1Pi-i10qYtu9LQkhzhIMXQOtOa8LLCKZT",
            "2. AIML Department (Artificial Intelligence & Machine Learning):",
            "   - Target Academic Years: Second Year (S.Y.), Third Year (T.Y.), and Final Year B.Tech.",
            "   - Google Drive Folder Link: https://drive.google.com/drive/folders/1Pi-i10qYtu9LQkhzhIMXQOtOa8LLCKZT",
            "3. CSBS Department (Computer Science & Business Systems):",
            "   - Target Academic Years: Second Year (S.Y.), Third Year (T.Y.), and Final Year B.Tech.",
            "   - Direct Timetable File Link: https://drive.google.com/file/d/1Yr3fsic12RvEHj1pZzGjgeFl3yDTO0O3/view",
            "4. Master All Departments Timetable Folder:",
            "   - Google Drive Folder: https://drive.google.com/drive/folders/1Pi-i10qYtu9LQkhzhIMXQOtOa8LLCKZT",
            "DIRECTIVE: Give a polite, clear response confirming timetable availability for the requested department (BSH for F.Y. / AIML for SY, TY, Final Year / CSBS). Provide a clear explanation of what is included. DO NOT list repetitive bullet points of Google Drive links in your text, because an interactive 1-click timetable card is automatically appended below your answer."
        ]
        context_texts.insert(0, "\n".join(tt_ctx))

    # Prepend official Meraki context if matched
    if meraki_reels:
        reels_ctx = [
            "OFFICIAL MERAKI FLAGSHIP GATHERING INFO (KITCOEK Cultural Committee):",
            "Meraki is KITCOEK's premier annual cultural gathering featuring grand stage dance competitions, musical concerts, drama, fashion shows, and campus celebrations.",
            "DIRECTIVE: Give an engaging overview of the Meraki festival. Do NOT output a bullet list of reel links or URLs in your text reply, because a dedicated interactive card with direct watch buttons for all 5 official reels will be automatically displayed."
        ]
        context_texts.insert(0, "\n".join(reels_ctx))

    # Prepend official VMedulife guide if matched
    if vmedulife_guide:
        guide_lines = [f"OFFICIAL KITCOEK VMEDULIFE GUIDE ({vmedulife_guide['title']}):"]
        for idx, s in enumerate(vmedulife_guide["steps"], start=1):
            guide_lines.append(f"{idx}. {s}")
        context_texts.insert(0, "\n".join(guide_lines))

    # Prepend official notice context if matched
    if matched_notices or matched_cals:
        notice_ctx_lines = ["Official KITCOEK Notice Board & Academic Calendar Data (Source: https://www.kitcoek.in/notice):"]
        if matched_cals:
            notice_ctx_lines.append("Official Academic Calendars:")
            for cal in matched_cals:
                notice_ctx_lines.append(f"- {cal['title']} ({cal['academic_year']}, {cal['term']}): {cal['pdf_url']}")
        if matched_notices:
            notice_ctx_lines.append("Latest Relevant Notices & Circulars from Notice Board:")
            for n in matched_notices:
                notice_ctx_lines.append(f"- [{n['date']}] {n['title']} (Direct PDF Download: {n['file_url']})")
        context_texts.insert(0, "\n".join(notice_ctx_lines))
    
    # 5. Generate Grounded Answer via Gemini
    rag_result = gemini.generate_rag_answer(
        query=query,
        context_chunks=context_texts,
        location_data=matched_loc_data,
        club_data=matched_club_data,
        clubs_directory=clubs_dir_summary
    )
    
    # Format source citations
    citations = [
        SourceCitation(
            document_name=r["document_name"],
            category=r["category"],
            chunk_text=r["chunk_text"],
            score=r["score"]
        )
        for r in retrieved_chunks
    ]
    
    # 6. Persist Chat History in DB
    history_entry = ChatHistory(
        id=str(uuid.uuid4()),
        session_id=req.session_id or "default",
        user_prn=req.student_prn,
        query=query,
        response=rag_result["answer"],
        category=category,
        sources=json.dumps([c.dict() for c in citations]) if citations else None
    )
    db.add(history_entry)
    db.commit()
    
    resp = ChatResponse(
        reply=rag_result["answer"],
        category=category,
        sources=[],
        follow_up_questions=rag_result.get("follow_up_questions", []),
        map_url=map_url,
        location_details=matched_loc_data,
        club_details=matched_club_data,
        portal_url=portal_url,
        notes_url=notes_url,
        timetable_url=timetable_url,
        timetable_details=timetable_details,
        notices_details=matched_notices,
        notice_board_url=notice_board_url,
        academic_calendars=matched_cals,
        vmedulife_guide=vmedulife_guide,
        meraki_reels=meraki_reels,
        csbs_syllabus=csbs_syllabus
    )
    if len(_chat_cache) > 200:
        _chat_cache.clear()
    _chat_cache[q_key] = resp
    return resp

@router.get("/history")
def get_chat_history(session_id: str = "default", db: Session = Depends(get_db)):
    chats = db.query(ChatHistory).filter(ChatHistory.session_id == session_id).order_by(ChatHistory.created_at.desc()).limit(20).all()
    return [
        {
            "id": c.id,
            "query": c.query,
            "response": c.response,
            "category": c.category,
            "created_at": c.created_at.isoformat()
        }
        for c in chats
    ]

# Document Management APIs
@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form("General"),
    db: Session = Depends(get_db)
):
    upload_dir = "./backend/data/documents/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in [".pdf", ".docx", ".doc", ".pptx", ".txt"]:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF, DOCX, PPTX, or TXT.")

    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Process and chunk
    try:
        text = extract_text_from_file(file_path)
        chunks = chunk_text(text, chunk_size=450, overlap=60)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process document: {e}")

    doc_id = str(uuid.uuid4())
    doc_rec = DocumentRecord(
        id=doc_id,
        filename=file.filename,
        file_type=file_ext,
        file_path=file_path,
        category=category,
        num_chunks=len(chunks)
    )
    db.add(doc_rec)
    db.commit()
    db.refresh(doc_rec)

    # Index in vector store
    vs = get_vector_store()
    vs.add_chunks(doc_id, file.filename, category, chunks)

    return doc_rec

@router.get("/documents", response_model=List[DocumentResponse])
def list_documents(db: Session = Depends(get_db)):
    return db.query(DocumentRecord).all()

@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(DocumentRecord).filter(DocumentRecord.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # Delete from vector store
    vs = get_vector_store()
    vs.delete_document(doc_id)
    
    # Delete from DB
    db.delete(doc)
    db.commit()
    return {"message": f"Document {doc.filename} deleted successfully"}

# Campus Location APIs
@router.get("/locations", response_model=List[LocationResponse])
def list_locations(category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(CampusLocation)
    if category:
        query = query.filter(CampusLocation.category == category)
    return query.all()

@router.get("/locations/search")
def search_location(query: str, db: Session = Depends(get_db)):
    locations = db.query(CampusLocation).all()
    q = query.lower()
    matches = [
        loc for loc in locations 
        if q in loc.name.lower() or q in loc.category.lower() or q in loc.building.lower() or (loc.room_number and q in loc.room_number.lower())
    ]
    return matches

# Student Clubs APIs
@router.get("/clubs", response_model=List[StudentClubResponse])
def list_clubs(
    category: Optional[str] = None, 
    search: Optional[str] = None, 
    db: Session = Depends(get_db)
):
    query = db.query(StudentClub)
    if category and category.strip() and category != "All":
        query = query.filter(StudentClub.category == category)
    clubs = query.all()
    
    if search:
        s = search.lower().strip()
        clubs = [
            c for c in clubs
            if s in c.name.lower() or 
               (c.abbr and s in c.abbr.lower()) or 
               (c.category and s in c.category.lower()) or
               (c.description and s in c.description.lower()) or
               (c.skills_developed and s in c.skills_developed.lower()) or
               (c.major_activities and s in c.major_activities.lower())
        ]
        
    return [format_club_dict(c) for c in clubs]

@router.get("/clubs/categories", response_model=List[ClubCategorySummary])
def get_club_categories(db: Session = Depends(get_db)):
    clubs = db.query(StudentClub).all()
    from collections import Counter
    counts = Counter(c.category for c in clubs if c.category)
    return [ClubCategorySummary(category=cat, count=cnt) for cat, cnt in counts.items()]

@router.get("/clubs/{club_id}", response_model=StudentClubResponse)
def get_club(club_id: str, db: Session = Depends(get_db)):
    club = db.query(StudentClub).filter(
        (StudentClub.id == club_id) | 
        (StudentClub.abbr.ilike(club_id))
    ).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    return format_club_dict(club)

@router.get("/clubs/{club_id}/pdf")
def get_club_pdf(club_id: str, db: Session = Depends(get_db)):
    club = db.query(StudentClub).filter(
        (StudentClub.id == club_id) | 
        (StudentClub.abbr.ilike(club_id))
    ).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
        
    local_pdf = os.path.join("backend", "data", "documents", "clubs", f"{club.id}.pdf")
    if os.path.exists(local_pdf):
        return FileResponse(local_pdf, media_type="application/pdf", filename=f"{club.id}_report.pdf")
        
    if club.pdf_url:
        return {"pdf_url": club.pdf_url}
        
    raise HTTPException(status_code=404, detail="PDF report not found")

@router.get("/notices")
def get_campus_notices(q: Optional[str] = Query(None, description="Search term for notices"), limit: int = 10):
    """
    Returns notices and timetables from the official KITCOEK Notice Board (https://www.kitcoek.in/notice)
    """
    if q:
        results = notice_service.search_notices(q, limit=limit)
    else:
        results = notice_service.get_latest_notices(limit=limit)
    return {
        "source": "https://www.kitcoek.in/notice",
        "total": len(results),
        "notices": [
            {
                "id": n.get("_id"),
                "title": n.get("title") or n.get("fileName"),
                "description": n.get("description"),
                "date": notice_service.parse_notice_date(n),
                "file_url": n.get("fileUrl"),
                "file_name": n.get("fileName")
            }
            for n in results
        ],
        "academic_calendars": notice_service.get_academic_calendars()
    }


