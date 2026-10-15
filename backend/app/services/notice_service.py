import os
import json
import time
import urllib.request
import re
from typing import List, Dict, Optional

class NoticeService:
    API_URL = "https://kitcoekin-backend.vercel.app/api/notices"
    NOTICE_BOARD_URL = "https://www.kitcoek.in/notice"
    LOCAL_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "notices", "kitcoek_notices.json")
    
    _cached_notices: List[Dict] = []
    _last_fetched: float = 0
    _CACHE_TTL: float = 600 # 10 minutes cache

    ACADEMIC_CALENDARS = [
        {
            "title": "Academic Calendar 2026–27 (Odd Semester) — S.Y., T.Y. & Final Year B.Tech",
            "academic_year": "2026–27",
            "term": "Odd Semester",
            "programme": "S.Y., T.Y. & Final Year B.Tech",
            "pdf_url": "https://www.kitcoek.in/documents/academics/academic-calender/Academic26_27/SY-TY-BTECH_ACADEMIC%20CALENDAR_2026-27_ODD%20SEM.pdf"
        },
        {
            "title": "Academic Calendar 2026–27 (Odd Semester) — F.Y. B.Tech & F.Y. M.Tech",
            "academic_year": "2026–27",
            "term": "Odd Semester",
            "programme": "First Year B.Tech & M.Tech",
            "pdf_url": "https://www.kitcoek.in/documents/academics/academic-calender/Academic26_27/FYBTech_FYMTech_Academic%20Calendar_2026-27%20Odd%20Sem.pdf",
            "key_milestones": {
                "induction_program": "Phase-I: 25–30 Aug, Phase-II: 01–06 Sept, Phase-III: 08–13 Sept 2026",
                "commencement": "01st September, 2026",
                "ise_1_marks": "17th October, 2026",
                "mse_exams": "24th to 31st October, 2026",
                "mse_result": "14th November, 2026",
                "sih_hackathon": "08th to 09th December, 2026",
                "kit_pbl_day": "16th December, 2026",
                "academic_ends": "19th December, 2026",
                "ise_2_and_defaulters": "22nd December, 2026",
                "ese_lab_poe": "26th to 30th December, 2026",
                "ese_theory": "01st to 12th January, 2027",
                "even_sem_start": "15th January, 2027",
                "ese_result": "30th January, 2027",
                "total_instruction_days": 96
            }
        },
        {
            "title": "Academic Calendar 2026–27 (Odd Semester) — S.Y. M.Tech",
            "academic_year": "2026–27",
            "term": "Odd Semester",
            "programme": "Second Year M.Tech",
            "pdf_url": "https://www.kitcoek.in/documents/academics/academic-calender/Academic26_27/SYMTECH_ACADEMIC%20CALENDAR_2026-27_ODD%20SEM.pdf"
        },
        {
            "title": "Revised Academic Calendar 2025–26 (Even Semester) — UG & PG",
            "academic_year": "2025–26",
            "term": "Even Semester",
            "programme": "All UG & PG Programmes",
            "pdf_url": "https://www.kitcoek.in/documents/academics/academic-calender/Academic25_26/Revised_Academic_Calendar_2025-26_Even_Sem_UG_PG.pdf"
        },
        {
            "title": "Academic Calendar 2025–26 (Odd Semester) — S.Y., T.Y. & Final Year B.Tech",
            "academic_year": "2025–26",
            "term": "Odd Semester",
            "programme": "S.Y., T.Y. & Final Year B.Tech",
            "pdf_url": "https://www.kitcoek.in/documents/academics/academic-calender/Academic25_26/Academic%20Calendar_SY-TY-Final%20Year%20BTech_2025-26_Odd%20Sem.pdf"
        }
    ]

    @classmethod
    def get_all_notices(cls, force_refresh: bool = False) -> List[Dict]:
        now = time.time()
        if cls._cached_notices and (now - cls._last_fetched < cls._CACHE_TTL) and not force_refresh:
            return cls._cached_notices

        # Try fetching from live KITCOEK API
        try:
            req = urllib.request.Request(cls.API_URL, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) KITCOEK-AI-Assistant"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    if isinstance(data, list) and len(data) > 0:
                        cls._cached_notices = data
                        cls._last_fetched = now
                        # Save local cache asynchronously/safely
                        try:
                            os.makedirs(os.path.dirname(cls.LOCAL_CACHE_PATH), exist_ok=True)
                            with open(cls.LOCAL_CACHE_PATH, "w", encoding="utf-8") as f:
                                json.dump(data, f, indent=2, ensure_ascii=False)
                        except Exception:
                            pass
                        return cls._cached_notices
        except Exception as e:
            print(f"[NoticeService] Live fetch error ({e}), trying local fallback...")

        # Fallback to local cache if live fetch fails or times out
        if not cls._cached_notices and os.path.exists(cls.LOCAL_CACHE_PATH):
            try:
                with open(cls.LOCAL_CACHE_PATH, "r", encoding="utf-8") as f:
                    cls._cached_notices = json.load(f)
                    cls._last_fetched = now
            except Exception as e:
                print(f"[NoticeService] Fallback read error: {e}")

        return cls._cached_notices

    @classmethod
    def parse_notice_date(cls, notice: Dict) -> str:
        d = notice.get("date") or notice.get("createdAt") or "1970-01-01"
        return str(d)[:10]

    @classmethod
    def search_notices(cls, query: str, limit: int = 5) -> List[Dict]:
        notices = cls.get_all_notices()
        if not notices:
            return []

        q_clean = query.lower()
        # Tokenize query
        tokens = [t for t in re.split(r'\W+', q_clean) if len(t) >= 2 and t not in ['the', 'for', 'and', 'what', 'when', 'is', 'are', 'in', 'of']]
        
        # Specific keyword mapping
        mse_keywords = ["mse", "midsem", "mid sem", "mid semester"]
        ese_keywords = ["ese", "endsem", "end sem", "end semester"]
        cal_keywords = ["calendar", "calender", "academic calendar", "commencement"]
        tt_keywords = ["timetable", "time table", "schedule", "date sheet"]

        has_mse = any(k in q_clean for k in mse_keywords)
        has_ese = any(k in q_clean for k in ese_keywords)
        has_cal = any(k in q_clean for k in cal_keywords)
        has_tt = any(k in q_clean for k in tt_keywords)
        has_grievance = "grievance" in q_clean or "paper seeing" in q_clean
        has_hall_ticket = "hall ticket" in q_clean or "admit card" in q_clean
        has_result = "result" in q_clean or "marks" in q_clean or "display" in q_clean

        scored_notices = []
        for n in notices:
            title = (n.get("title") or "").lower()
            desc = (n.get("description") or "").lower()
            fname = (n.get("fileName") or "").lower()
            haystack = f"{title} {desc} {fname}"

            score = 0
            if has_mse and ("mse" in haystack or "mid" in haystack):
                score += 25
            if has_ese and "ese" in haystack:
                score += 20
            if has_cal and ("calendar" in haystack or "commencement" in haystack):
                score += 15
            if has_tt and ("time table" in haystack or "timetable" in haystack or "schedule" in haystack):
                score += 12
            if has_grievance and ("grievance" in haystack or "paper seeing" in haystack):
                score += 20
            if has_hall_ticket and ("hall ticket" in haystack or "admit card" in haystack):
                score += 20
            if has_result and "result" in haystack:
                score += 15

            # Word tokens match
            for t in tokens:
                if t in title:
                    score += 6
                elif t in haystack:
                    score += 3

            # Recency boost so current academic years (2026, 2025) appear ahead of older archives
            notice_date = cls.parse_notice_date(n)
            year = notice_date[:4]
            if year == "2026":
                score += 30
            elif year == "2025":
                score += 15
            elif year == "2024":
                score += 5

            if score > 0:
                scored_notices.append((score, notice_date, n))

        # Sort by score desc, then date desc
        scored_notices.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [item[2] for item in scored_notices[:limit]]

    @classmethod
    def get_latest_notices(cls, limit: int = 5) -> List[Dict]:
        notices = cls.get_all_notices()
        sorted_list = sorted(notices, key=cls.parse_notice_date, reverse=True)
        return sorted_list[:limit]

    @classmethod
    def get_academic_calendars(cls) -> List[Dict]:
        return cls.ACADEMIC_CALENDARS

notice_service = NoticeService()
