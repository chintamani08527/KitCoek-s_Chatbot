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

import re

def linkify_urls(html: str) -> str:
    """Safely converts plain text URLs into styled clickable <a> tags without affecting existing <a> links."""
    if not html:
        return html
    tokens = re.split(r'(<a\s+[^>]*>.*?</a>)', html, flags=re.DOTALL | re.IGNORECASE)
    res = []
    for t in tokens:
        if t.lower().startswith('<a'):
            res.append(t)
        else:
            def repl(m):
                url = m.group(1).rstrip('.,;:)]>')
                is_pdf = '.pdf' in url.lower()
                label = '📄 Download Syllabus PDF ↗' if is_pdf else f'{url} ↗'
                return f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="chat-inline-link">{label}</a>'
            t_sub = re.sub(r'(https?://[^\s<>"]+)', repl, t)
            res.append(t_sub)
    return ''.join(res)

CSE_SYLLABUS_DATA = {
    "department": "Computer Science & Engineering (CSE)",
    "portal_url": "https://www.kitcoek.in/online-syllabus",
    "scheme": "2023 [NEP-2020] & Autonomy Scheme",
    "structure_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/Structure4Web_AY2324.pdf",
    "years": [
        {
            "year": "Complete CSE Curriculum Structure",
            "tag": "All-Year Structure",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/Structure4Web_AY2324.pdf",
            "description": "Complete credit system, course codes, POs, and teaching evaluation scheme for CSE."
        },
        {
            "year": "Second Year (S.Y. B.Tech CSE)",
            "tag": "2023 [NEP-2020]",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/SY-CSE-AY-2022-23-Syllabus%20-%20updatged_CO_PO.pdf",
            "description": "Discrete Mathematical Structures, Data Structures and Algorithms, OOP (Java/C++), Computer Organization & Architecture, Digital Systems."
        },
        {
            "year": "Third Year (T.Y. B.Tech CSE)",
            "tag": "2023 [NEP-2020]",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/TY-CSE-Syllabus-AY-2023-24%20-%20updated%20copy%2025.pdf",
            "description": "Database Management Systems (DBMS), Design & Analysis of Algorithms (DAA), Operating Systems, Software Engineering, AI & ML, Computer Networks."
        },
        {
            "year": "Final Year B.Tech CSE",
            "tag": "Autonomy Scheme",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/2017-FinalYear_Old_syllabus.pdf",
            "description": "Distributed Systems, Cloud Computing, Big Data Analytics, Information Security, Capstone Project Phase I & II."
        }
    ]
}

AIML_SYLLABUS_DATA = {
    "department": "CSE (Artificial Intelligence & Machine Learning)",
    "portal_url": "https://www.kitcoek.in/online-syllabus",
    "scheme": "2023 [NEP-2020] Scheme",
    "years": [
        {
            "year": "Second Year (S.Y. CSE-AIML)",
            "tag": "Sem 3 & 4",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/2.CSE%20AIML%20SY%20Syllabus%20Sem%203%20to%20Sem%204.pdf",
            "description": "Data Structures with Python, Mathematical Foundations of AI, OOP, Computer Architecture, Probability & Statistics for AI."
        },
        {
            "year": "Third Year (T.Y. CSE-AIML)",
            "tag": "Sem 5",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/TY%20CSE(AIML)_syllabus_SEM-V_WEBSITE%20COPY_17%20JUNE%2023.pdf",
            "description": "Machine Learning Algorithms, Deep Learning Foundations, Natural Language Processing, Computer Vision, AI Ethics."
        },
        {
            "year": "Honors Specialization in Cyber Security",
            "tag": "Honors Degree",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/B-Tech%20(Hons-)%20CSE(AIML)_Cyber%20Security%20Structure.pdf",
            "description": "Complete 20-credit B.Tech Honors curriculum structure and syllabus for Cyber Security specialization."
        }
    ]
}

DS_SYLLABUS_DATA = {
    "department": "CSE (Data Science - DS)",
    "portal_url": "https://www.kitcoek.in/online-syllabus",
    "scheme": "2023 [NEP-2020] Scheme",
    "years": [
        {
            "year": "Second Year (S.Y. CSE-DS)",
            "tag": "Sem 3 & 4",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/SYCSE-DS-Syllabus-28-09-22.pdf",
            "description": "Foundations of Data Science, Data Structures, Computational Statistics, DBMS, R/Python Programming."
        },
        {
            "year": "Third Year (T.Y. CSE-DS)",
            "tag": "Sem 5 & 6",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/TYCSE(DS)_syllabus_SEM-V_VI_WEBSITE%20COPY_17%20JUNE%2023.pdf",
            "description": "Big Data Technologies, Predictive Analytics, Applied Machine Learning, Data Visualization & Mining."
        },
        {
            "year": "Honors in Cyber Security for Data Science",
            "tag": "Honors Degree",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/B-%20Tech%20(Hons-)%20Computer%20Science%20and%20Engineering%20(Data%20Science)%20with%20specialization%20in%20cyber%20security.pdf",
            "description": "B.Tech Honors curriculum specializing in Data Science & Cyber Security."
        }
    ]
}

FY_SYLLABUS_DATA = {
    "department": "First Year Engineering (F.Y. B.Tech - All Branches)",
    "portal_url": "https://www.kitcoek.in/online-syllabus",
    "scheme": "2023 [NEP-2020] Scheme",
    "years": [
        {
            "year": "Circuit Branches (CSE, AIML, DS, ENTC, Electrical)",
            "tag": "NEP-2020 Syllabus",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/FY%20B%20Tech%20Circuit%20Branch_Final%20Structure%20%26%20Syllabus%20New.pdf",
            "description": "Engineering Mathematics-I & II, Physics/Chemistry, Basic Electrical, Programming for Problem Solving (C/Python), Basic Electronics."
        },
        {
            "year": "Core Branches (Biotech, Civil, Civil-Env, Mechanical)",
            "tag": "NEP-2020 Syllabus",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/FY%20B%20Tech%20Core%20Branch_Final%20Structure%20%26%20Syllabus%20New.pdf",
            "description": "Engineering Mechanics, Basic Mechanical Systems, Workshop Practices, Engineering Materials, Chemistry for Engineers."
        },
        {
            "year": "UG Academic Rules & Regulations (NEP-2020)",
            "tag": "Official Policy",
            "pdf_url": "https://www.kitcoek.in/documents/academics/importantDocuments/UG%20ACADEMIC%20RULES%20AND%20REGULATIONS_NEP%202020.pdf",
            "description": "Official autonomous academic ordinances, grading rules, credit system, examination guidelines."
        }
    ]
}

BIOTECH_SYLLABUS_DATA = {
    "department": "Biotechnology Engineering",
    "portal_url": "https://www.kitcoek.in/online-syllabus",
    "scheme": "Cycle-2 Autonomy & NEP Scheme",
    "years": [
        {
            "year": "Second Year (S.Y. B.Tech Biotech)",
            "tag": "S.Y. Syllabus",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/SY%20BTech%20syllabus%20contents%202022-23.pdf",
            "description": "Biochemistry, Cell Biology, Microbiology, Bioprocess Principles, Fluid Flow Operations."
        },
        {
            "year": "Third Year (T.Y. B.Tech Biotech)",
            "tag": "T.Y. Syllabus",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/TY%20BTech%20syllabus%20contents%202023-24.pdf",
            "description": "Molecular Biology, Genetic Engineering, Immunology, Bioreactor Design, Heat & Mass Transfer."
        },
        {
            "year": "Biotech Autonomy 2nd Cycle Structure",
            "tag": "Structure & Credits",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/Autonomy%202nd%20Cycle%20Structure%20Biotech%20%20wef%202022-23.pdf",
            "description": "Complete 4-year credit structure and semester-wise evaluation scheme for Biotechnology."
        }
    ]
}

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

MECHANICAL_SYLLABUS_DATA = {
    "department": "Department of Mechanical Engineering",
    "portal_url": "https://www.kitcoek.in/online-syllabus",
    "scheme": "2023 [NEP-2020] & Autonomy Scheme",
    "structure_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/Mech%20Structure.pdf",
    "years": [
        {
            "year": "S.Y. B.Tech Mechanical Structure",
            "tag": "NEP Structure",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/Mech%20Structure.pdf",
            "description": "Thermodynamics, Fluid Mechanics, Material Science & Metallurgy, Manufacturing Processes, Kinematics of Machines."
        },
        {
            "year": "T.Y. B.Tech Mechanical Structure (NEP-2020)",
            "tag": "NEP-2020 T.Y.",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/MECH_DEPT_TY%20B%20Tech%20_STRUCTURE%20as%20per%20NEP2020_compressed.pdf",
            "description": "Heat Transfer, Machine Design, Turbo Machinery, Mechatronics, Operations Research."
        },
        {
            "year": "Final Year B.Tech Mechanical Structure (NEP)",
            "tag": "NEP Final Year",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/FINAL%20YEAR%20BTECH%20MECHANICAL%20STRUCTURE_WEF%20AY%202024-25_compressed.pdf",
            "description": "Refrigeration & Air Conditioning, CAD/CAM/CAE, Automobile Engineering, Industrial Engineering, Capstone Project."
        },
        {
            "year": "Final Year Mechanical Autonomous Structure",
            "tag": "Cycle-2 Scheme",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/REVISED_Final%20Year%20BTECH%20Mechanical%20Autonomous%20Structure.pdf",
            "description": "Complete 160-credit autonomous final year curriculum structure."
        },
        {
            "year": "F.Y. B.Tech Core Branches (Mech/Civil/Biotech)",
            "tag": "F.Y. NEP Syllabus",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/FY%20B%20Tech%20Core%20Branch_Final%20Structure%20%26%20Syllabus%20New.pdf",
            "description": "Engineering Mechanics, Basic Mechanical Systems, Workshop Practices, Engineering Materials."
        }
    ]
}

ELECTRICAL_SYLLABUS_DATA = {
    "department": "Department of Electrical Engineering",
    "portal_url": "https://www.kitcoek.in/online-syllabus",
    "scheme": "2023 [NEP-2020] & Autonomy Scheme",
    "structure_url": "https://kitcoek.s3.amazonaws.com/syllabus/NEP%20STRUCTURE%20ELECTRICAL%20ENGG.pdf",
    "years": [
        {
            "year": "NEP Electrical Engineering Complete Structure",
            "tag": "NEP-2020 Structure",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/NEP%20STRUCTURE%20ELECTRICAL%20ENGG.pdf",
            "description": "Complete semester-wise credit system, course codes, ISE/MSE/ESE evaluation schemes for Electrical Engineering."
        },
        {
            "year": "B.Tech Honors: Electric Vehicles (EV) Syllabus",
            "tag": "Honors: Electric Vehicles",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/UELHN0351and%20UELHN451_Final%20After%20Bos%20meeting_19-5-2024.pdf",
            "description": "EV Powertrain Design, Battery Management Systems (BMS), Electric Drives & Control."
        },
        {
            "year": "B.Tech Honors: Electric Vehicles (EV) Structure",
            "tag": "Honors EV Structure",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/B.Tech%20Honors%20Electric%20Vehicles-Structure-Under%20NEP%202020.pdf",
            "description": "Complete 20-credit B.Tech Honors curriculum structure in Electric Vehicles under NEP-2020."
        },
        {
            "year": "S.Y. to Final Year Electrical Cycle-2 Structure",
            "tag": "Cycle-2 Autonomy",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/Revised_Structure_S.Y%20to%20Final%20Year%20B.Tech-Electrical%20Engineering%20w.e.f%202022-23.pdf",
            "description": "Electrical Machines, Power Systems, Control Systems, Power Electronics, Renewable Energy Systems."
        },
        {
            "year": "Final Year B.Tech Electrical Syllabus",
            "tag": "Final Year Syllabus",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/%28Final%20B.%20Tech-Syllabus%29%28%20Cycle-2%29-Electrical%20Engineering_compressed.pdf",
            "description": "High Voltage Engineering, Smart Grid, Switchgear & Protection, Electrical Drives, Capstone Project."
        },
        {
            "year": "Electrical NEP Exit Course Syllabus (SY)",
            "tag": "NEP Exit Certification",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/Electrical%20Engineering_NEP_Exit%20Course%20SY_compressed_compressed%20%282%29%20%281%29.pdf",
            "description": "NEP-2020 Diploma / Certificate in Electrical Engineering exit course curriculum."
        }
    ]
}

CIVIL_SYLLABUS_DATA = {
    "department": "Department of Civil & Environmental Engineering",
    "portal_url": "https://www.kitcoek.in/online-syllabus",
    "scheme": "2023 [NEP-2020] & Autonomy Scheme",
    "structure_url": "https://kitcoek.s3.amazonaws.com/syllabus/13.05.2026_B.Tech.%20Civil%20Engineering-Structure%20%28NEP2020%29after%20BoS.pdf",
    "years": [
        {
            "year": "Civil Engineering NEP-2020 Complete Structure",
            "tag": "NEP-2020 Structure",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/13.05.2026_B.Tech.%20Civil%20Engineering-Structure%20%28NEP2020%29after%20BoS.pdf",
            "description": "Complete autonomous structure approved after Board of Studies (BoS)."
        },
        {
            "year": "Second Year (S.Y. B.Tech Civil) Syllabus",
            "tag": "S.Y. NEP Syllabus",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/16.04.2026_S.Y.B.Tech%20Civil%20Engineering%20Syllabus%20%28NEP2020%29.pdf",
            "description": "Surveying, Strength of Materials, Fluid Mechanics, Building Construction & Planning, Concrete Technology."
        },
        {
            "year": "Third Year (T.Y. B.Tech Civil) Syllabus",
            "tag": "T.Y. NEP Syllabus",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/16.04.2026_T.Y.B.Tech%20Syllabus%20%28NEP2020%29%20%281%29.pdf",
            "description": "Structural Analysis, Geotechnical Engineering, Environmental Engineering, Transportation Engineering, Design of Steel Structures."
        },
        {
            "year": "Final Year B.Tech Civil Engineering Syllabus",
            "tag": "Final Year NEP",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/30.07.2026_Final%20Year%20B.Tech%20Civil%20Engineering_Syllabus%20%28NEP2020%29%20after%20BoS.pdf",
            "description": "Design of Concrete Structures, Water Resources Engineering, Construction Management, Quantity Surveying & Valuation, Capstone Project."
        },
        {
            "year": "Civil Honors (Strategic Civil Infrastructure)",
            "tag": "Honors Specialization",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/HONORS%20%28STRATEGIC%20CIVIL%20INFRASTRUCTURE%29_Syllabus%20%28NEP2020%29.pdf",
            "description": "Strategic Infrastructure Planning, Smart Cities, Advanced Highway Technology."
        },
        {
            "year": "Civil Emerging Minor (Lean Technology)",
            "tag": "Emerging Minor",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/EMERGING%20SPECIALIZATION%20MINOR%20%28LEAN%20TECHNOLOGY%29_Syllabus%20%28NEP2020%29.pdf",
            "description": "Lean Construction Management, BIM, Green Building Technology."
        }
    ]
}

ETC_SYLLABUS_DATA = {
    "department": "Department of Electronics & Telecommunication Engineering (ETC / ENTC)",
    "portal_url": "https://www.kitcoek.in/online-syllabus",
    "scheme": "2023 [NEP-2020] & Autonomy Scheme",
    "structure_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/FINAL-NEP-STructure.pdf",
    "years": [
        {
            "year": "ETC NEP-2020 Complete Structure",
            "tag": "NEP-2020 Structure",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/FINAL-NEP-STructure.pdf",
            "description": "Complete credit system, evaluation scheme, and course matrix for ETC."
        },
        {
            "year": "Second Year (S.Y. B.Tech ETC) Syllabus",
            "tag": "S.Y. NEP Syllabus",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/NEP%20STructure%2B%20SY%20Syllabus_compressed.pdf",
            "description": "Electronic Devices & Circuits, Signals & Systems, Digital Logic Design, Network Theory, Analog Circuits."
        },
        {
            "year": "Third Year (T.Y. B.Tech ETC) Syllabus",
            "tag": "T.Y. NEP Syllabus",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/NEP%2BThird%20Year_compressed.pdf",
            "description": "Microcontrollers & Embedded Systems, Digital Signal Processing (DSP), Electromagnetic Waves, Analog & Digital Communication."
        },
        {
            "year": "Final Year B.Tech ETC Syllabus",
            "tag": "Final Year NEP",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/NEP%20structure%2BFinal%20Year%20Syllabus_compressed.pdf",
            "description": "VLSI Design, Microwave & Antenna Theory, Optical Fiber Communication, Wireless Cellular Networks, Capstone Project."
        },
        {
            "year": "B.Tech Honors in Internet of Things (IoT)",
            "tag": "Honors: IoT Specialization",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/structure%20and%20syllabus%20of%20Btech%20%28Hons%29.%20of%20ETC%20DEPT.pdf",
            "description": "Complete IoT Architecture, Sensor Interfacing, Embedded Linux, Cloud Computing for IoT."
        },
        {
            "year": "Circuit Branches First Year Structure",
            "tag": "F.Y. Circuit Branches",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/FY%20B%20Tech%20Circuit%20Branch_Final%20Structure%20%26%20Syllabus%20New.pdf",
            "description": "First Year curriculum for CSE, AIML, DS, ETC, Electrical branches."
        }
    ]
}

GENERAL_SYLLABUS_DATA = {
    "department": "KITCOEK Online Syllabus Directory (All Departments)",
    "portal_url": "https://www.kitcoek.in/online-syllabus",
    "scheme": "2023 [NEP-2020] & Autonomy Scheme",
    "structure_url": "https://www.kitcoek.in/online-syllabus",
    "years": [
        {
            "year": "First Year Circuit Branches (CSE, AIML, DS, ETC, EE)",
            "tag": "Circuit FY",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/FY%20B%20Tech%20Circuit%20Branch_Final%20Structure%20%26%20Syllabus%20New.pdf",
            "description": "F.Y. B.Tech NEP-2020 structure for circuit engineering programs."
        },
        {
            "year": "First Year Core Branches (Mech, Civil, Biotech)",
            "tag": "Core FY",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/FY%20B%20Tech%20Core%20Branch_Final%20Structure%20%26%20Syllabus%20New.pdf",
            "description": "F.Y. B.Tech NEP-2020 structure for core engineering programs."
        },
        {
            "year": "Mechanical Engineering S.Y. Structure",
            "tag": "Mechanical",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/Mech%20Structure.pdf",
            "description": "Official Mechanical Engineering autonomous curriculum structure."
        },
        {
            "year": "Electrical Engineering NEP Complete Structure",
            "tag": "Electrical",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/NEP%20STRUCTURE%20ELECTRICAL%20ENGG.pdf",
            "description": "Official Electrical Engineering NEP-2020 curriculum structure."
        },
        {
            "year": "Civil Engineering NEP Complete Structure",
            "tag": "Civil",
            "pdf_url": "https://kitcoek.s3.amazonaws.com/syllabus/13.05.2026_B.Tech.%20Civil%20Engineering-Structure%20%28NEP2020%29after%20BoS.pdf",
            "description": "Official Civil Engineering NEP-2020 curriculum structure."
        },
        {
            "year": "ETC Engineering NEP Complete Structure",
            "tag": "ETC / ENTC",
            "pdf_url": "https://kitcoek.s3.ap-south-1.amazonaws.com/syllabus/FINAL-NEP-STructure.pdf",
            "description": "Official Electronics & Telecommunication Engineering structure."
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

OFFICIAL_CUTOFF_DATA = {
    "title": "KITCoEK Official Admission & Cutoff Directory",
    "portal_url": "https://www.kitcoek.in/admission-undergraduate",
    "apply_url": "https://www.kitcoek.in/apply-admission",
    "academic_year": "2025–26 & 2026–27",
    "dte_code": "6267",
    "items": [
        {
            "title": "F.Y. B.Tech General Cutoff Sheet",
            "category": "First Year (FE)",
            "url": "https://www.kitcoek.in/documents/admission/2025_26/FY%20General%20Cutoff-2024-25.jpeg",
            "type": "General Cutoff Sheet"
        },
        {
            "title": "F.Y. B.Tech Ladies Cutoff Sheet",
            "category": "First Year (FE)",
            "url": "https://www.kitcoek.in/documents/admission/2025_26/FY%20Ladies%20Cutoff-2024-25.jpeg",
            "type": "Ladies Cutoff Sheet"
        },
        {
            "title": "Direct Second Year (DSY) General Cutoff PDF",
            "category": "Direct Second Year (DSE)",
            "url": "https://www.kitcoek.in/documents/admission/2026_27/dsy/DSY.B.Tech%20General%20Seat%20Type%20Wise%20Cut%20Off%202025-26.pdf",
            "type": "Official PDF"
        },
        {
            "title": "Direct Second Year (DSY) Ladies Cutoff PDF",
            "category": "Direct Second Year (DSE)",
            "url": "https://www.kitcoek.in/documents/admission/2026_27/dsy/DSY%20B.Tech%20Ladies%20Seat%20Type%20Wise%20Cut%20Off%20A.Y.%202025-26.pdf",
            "type": "Official PDF"
        },
        {
            "title": "KIT Choice Codes (DTE Code 6267)",
            "category": "CAP Process",
            "url": "https://www.kitcoek.in/documents/admission/2025_26/Choice%20code.jpeg",
            "type": "Choice Code Chart"
        },
        {
            "title": "List of Required Documents (FY)",
            "category": "Documents",
            "url": "https://www.kitcoek.in/documents/admission/2025_26/FY_List_of_Required_Documents.jpeg",
            "type": "Document Checklist"
        },
        {
            "title": "List of Required Documents (DSY)",
            "category": "Documents",
            "url": "https://www.kitcoek.in/documents/admission/2025_26/DSY_List_of_Required_Documents.jpeg",
            "type": "Document Checklist"
        },
        {
            "title": "KIT Merit Scholarship Details",
            "category": "Scholarships",
            "url": "https://www.kitcoek.in/documents/admission/2025_26/KIT%20Merit%20Scholarship.jpeg",
            "type": "Scholarship Details"
        }
    ]
}

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
            "<p>⚠️ <strong>Out of Context Query:</strong> I am the dedicated <strong>KITCOEK AI Assistant</strong>, "
            "designed exclusively to assist with <strong>KITCoEK Kolhapur</strong> campus information, engineering academics, "
            "NEP-2020 syllabus, class timetables, examinations, VMedulife portal, campus navigation, and official Student Clubs.</p>"
            "<p>Your question appears to be outside the scope of college-related topics. Please ask a question related to KITCOEK!</p>"
        )
        return ChatResponse(
            reply=out_msg,
            category="out_of_scope",
            sources=[],
            follow_up_questions=[
                "What engineering branches are offered at KIT?",
                "What student clubs are available?",
                "How to check attendance in VMedulife?",
                "Show BSH First Year timetable"
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
        "portal", "lms", "vmedulife", "admission", "scholarship", "fee", "fees",
        "cutoff", "cut off", "cut-off", "cutoffs", "cut offs", "merit list"
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
    
    is_academic_doc_query = (
        any(kw in q_low for kw in [
            "attendance", "attendence", "attandance", "atendance", "attandence", "attendece", "attendace",
            "absent", "present", "defaulter", "defaulters", "detained", "75%",
            "vmedulife", "vmedu", "portal", "lms", "studentsummary",
            "result", "results", "marks", "grade", "grades", "sgpa", "cgpa", "marksheet", "mark sheet",
            "answer sheet", "paper seeing", "review and appeals", "check result", "see result", "view result",
            "notes in vmedulife", "vmedulife notes", "study material in vmedulife", "my learnings", "start learning",
            "academic planning", "syllabus", "curriculum", "timetable", "time table", "academic calendar", "calendar",
            "admission", "admissions", "cutoff", "cutoffs", "cut off", "merit list"
        ])
        or ("attend" in q_low and not any(x in q_low for x in ["attention", "attendee"]))
    )

    is_general_clubs_query = any(w in q_low for w in [
        "what student clubs", "student clubs are available", "what clubs are available", "clubs are available",
        "what clubs", "which clubs", "all clubs", "list of clubs", "list all clubs", "clubs list", "club list",
        "clubs available", "clubs are there", "available clubs", "student clubs", "student club",
        "show clubs", "how many clubs", "tell me about clubs", "clubs in kit", "clubs at kit", "join a club", "clubs present",
        "extracurricular", "student activities", "which club can i join"
    ]) or q_low.strip() in ["club", "clubs", "all clubs", "student clubs", "student club"]

    club_keywords = [
        "club", "clubs", "iste", "e-cell", "ecell", "mavericks", "sdc", "amateur writers",
        "ebsb", "cultural club", "aura", "shourya", "wdgec", "women development", "rotaract",
        "swe", "walk with world", "ncc", "nss", "lead india", "petrichor", "meraki",
        "gathering", "annual gathering", "cultural fest", "pioneer", "vidman", "prarambha",
        "mesa", "cesa", "elesa", "assets", "acses", "cabssa", "bytearq", "codewizard",
        "battle of wits", "civil safari", "tech-negotia", "tech negotia", "departmental club",
        "departmental clubs", "student association", "student associations"
    ]

    has_explicit_club_mention = any(re.search(r'\b' + re.escape(kw) + r'\b', q_low) for kw in ["club", "clubs", "association", "associations"])
    has_specific_club_name = any(re.search(r'\b' + re.escape(kw) + r'\b', q_low) for kw in club_keywords if kw not in ["club", "clubs"])

    is_club_intent = (
        is_general_clubs_query
        or (category == "clubs" and not is_academic_doc_query)
        or (has_specific_club_name and not is_academic_doc_query)
        or (has_explicit_club_mention and not (is_academic_doc_query and "club" not in q_low and "clubs" not in q_low))
    )

    if is_club_intent:
        category = "clubs"
        all_clubs = db.query(StudentClub).all()
        
        # Only check for a specific single club if NOT a general clubs query
        if not is_general_clubs_query:
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

                if any(re.search(r'\b' + re.escape(term) + r'\b', q_low) if len(term) <= 4 else term in q_low for term in club_terms):
                    matched_club_data = format_club_dict(club)
                    break

        # If general club query or no specific club matched, provide the complete directory
        if is_general_clubs_query or (not matched_club_data and any(w in q_low for w in ["club", "clubs", "all clubs", "activities"])):
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

    is_result_intent = (
        any(kw in q_low for kw in [
            "result", "results", "marks", "grade", "grades", "sgpa", "cgpa", "marksheet", "mark sheet",
            "answer sheet", "paper seeing", "review and appeals", "check result", "see result", "view result",
            "exam result", "examination result", "mse result", "ese result", "revaluation", "grievance", "paper review"
        ])
        or (any(r in q_low for r in ["result", "results", "marks", "grades"]) and any(p in q_low for p in ["vmedulife", "portal", "lms", "check", "see", "view"]))
    )
    is_vmedu_notes_intent = (
        any(kw in q_low for kw in [
            "my learnings", "start learning", "learning material", "uploaded by teacher", "teacher notes", "teacher note",
            "vm notes", "vmedulife notes", "syllabus on vmedulife", "course material", "study material uploaded",
            "notes in vmedulife", "notes on vmedulife", "notes from vmedulife", "study material in vmedulife",
            "study materials in vmedulife", "lecture notes in vmedulife", "vmedulife study material",
            "download notes in vmedulife", "find notes in vmedulife", "access notes in vmedulife"
        ])
        or (any(n in q_low for n in ["note", "notes", "material", "materials", "ppt", "slides", "learning"]) and any(p in q_low for p in ["vmedulife", "portal", "lms"]))
    )
    is_attendance_intent = (
        any(kw in q_low for kw in [
            "attendance", "attendence", "attandance", "atendance", "attandence", "attendece", "attendace",
            "daily attendance", "weekly attendance", "monthly attendance",
            "absent", "present", "check attendance", "attendance percentage", "classes attended",
            "defaulter", "defaulters", "detained", "75% attendance", "75 % attendance", "minimum attendance",
            "track attendance", "see attendance", "view attendance", "attendance record", "attendance portal",
            "were to attend", "where to attend"
        ])
        or ("attend" in q_low and not any(x in q_low for x in ["attention", "attendee"]))
    )
    is_generic_portal_intent = any(kw in q_low for kw in [
        "portal", "student portal", "lms", "vmedulife", "vmedu", "hall ticket", "admit card", "studentsummary", "erp portal"
    ])

    if is_result_intent:
        portal_url = "https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur"
        category = "academic"
        vmedulife_guide = {
            "type": "result",
            "title": "Steps to Check Result & Answer Sheet Reviews on VMedulife",
            "portal_url": portal_url,
            "steps": [
                "Open the official KITCoEK VMedulife portal link: https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur",
                "If prompted, log in with your student account credentials (PRN and password).",
                "Open Assessment (or Exam Forms, depending on your portal).",
                "Select Result -> Result (or if paper is displayed, click on Answer Sheet Review and Appeals).",
                "Select the relevant Academic Year and click Apply, if prompted.",
                "Find your semester's result and click VIEW to see your subject marks, credits, and grades."
            ]
        }
    elif is_vmedu_notes_intent:
        portal_url = "https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur"
        notes_url = "https://drive.google.com/drive/folders/1_1mxw4T2BNFCYFOoolsfAmZi8zWvv1Hy"
        category = "academic"
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
                "Click the relevant subject or learning item to open, view, or download lecture notes and PPTs."
            ]
        }
    elif is_attendance_intent:
        portal_url = "https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur"
        category = "academic"
        vmedulife_guide = {
            "type": "attendance",
            "title": "Steps to Check Attendance on KITCoEK VMedulife",
            "portal_url": portal_url,
            "steps": [
                "Open the KITCoEK VMedulife website (https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur) and log in with your student ID (PRN) and password.",
                "Go to Academic Planning on the left navigation dashboard.",
                "Look for and click on the Attendance option.",
                "Open the attendance section.",
                "Choose the attendance view you want: Daily Attendance, Weekly Attendance, or Monthly Attendance.",
                "Select the required date, week, or month, if prompted.",
                "Review your attendance records, lecture-by-lecture presence, and cumulative percentage (ensure you maintain >= 75% for exam eligibility)."
            ]
        }
    elif is_generic_portal_intent:
        portal_url = "https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur"
        category = "academic"
        vmedulife_guide = {
            "type": "portal",
            "title": "KITCoEK Official Student Portal (vMedulife ERP & LMS)",
            "portal_url": portal_url,
            "steps": [
                "Open the official KITCoEK VMedulife portal link: https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur",
                "Log in using your student credentials (PRN and password).",
                "To check Attendance: Go to Academic Planning -> Attendance.",
                "To access Course Notes: Go to Academic Planning -> Start Learning -> My Learnings.",
                "To view Exam Results: Go to Assessment -> Result -> Result."
            ]
        }

    if vmedulife_guide or is_result_intent or is_vmedu_notes_intent or is_attendance_intent or is_generic_portal_intent:
        category = "academic"
        clubs_dir_summary = None
        matched_club_data = None

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

        if matched_dept_id != "all":
            depts_to_show = [d for d in TIMETABLES_DATA["departments"] if d["id"] == matched_dept_id]
            title_text = f"KITCOEK {matched_dept_id.upper()} Department Timetable"
        else:
            depts_to_show = TIMETABLES_DATA["departments"]
            title_text = TIMETABLES_DATA["title"]

        timetable_details = {
            "requested_dept": matched_dept_id,
            "title": title_text,
            "drive_folder_url": TIMETABLES_DATA["drive_folder_url"],
            "departments": [
                {
                    **d,
                    "is_matched": True
                }
                for d in depts_to_show
            ]
        }

    # 3.7 Official Notice Board & Academic Calendars detection (https://www.kitcoek.in/notice)
    matched_notices = None
    matched_cals = None
    notice_board_url = None

    is_calendar_intent = any(kw in q_low for kw in [
        "academic calendar", "calendar", "calender", "term calendar", "semester calendar", "academic schedule"
    ]) or (
        any(w in q_low for w in ["calendar", "calender"]) and any(y in q_low for y in ["2026", "2027", "2025", "odd", "even", "sem", "academic", "term"])
    )

    is_notice_specific = any(kw in q_low for kw in [
        "notice", "notices", "circular", "circulars", "mse", "midsem", "mid sem", "mid semester",
        "ese exam", "makeup exam", "re-mse", "re exam", "re-exam", "backlog", "back log",
        "hall ticket", "admit card", "paper seeing", "grievance", "exam schedule",
        "exam notice", "latest news", "announcement", "announcements"
    ])

    is_exam_timetable_intent = any(k in q_low for k in ["exam notice", "exam circular", "exam timetable", "exam schedule", "mse timetable", "ese timetable", "re-mse"])

    is_pure_calendar_intent = is_calendar_intent and not (
        any(kw in q_low for kw in ["notice", "notices", "circular", "circulars", "announcement", "announcements"])
    )

    is_pure_portal_guide = bool(vmedulife_guide) and not any(k in q_low for k in [
        "notice", "circular", "calendar", "calender", "timetable", "time table", "mse", "ese", "schedule", "latest"
    ])

    if not is_pure_portal_guide:
        if is_pure_calendar_intent:
            # Academic Calendar specifically requested without notice circulars
            notice_board_url = "https://www.kitcoek.in/notice"
            category = "academic" if category not in ["clubs", "navigation"] else category
            matched_cals = notice_service.get_academic_calendars(year_query=query)
            matched_notices = None  # Explicitly suppress generic notices card when user specifically asks for Academic Calendar
        elif is_notice_specific or is_exam_timetable_intent or is_calendar_intent:
            notice_board_url = "https://www.kitcoek.in/notice"
            category = "notices" if category not in ["clubs", "navigation"] else category

            if is_calendar_intent:
                matched_cals = notice_service.get_academic_calendars(year_query=query)

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

    # 3.9 Official KITCOEK Online Syllabus & Department NEP-2020 detection (https://www.kitcoek.in/online-syllabus)
    matched_syllabus = None
    is_syllabus_intent = any(w in q_low for w in [
        "syllabus", "curriculum", "subject", "subjects", "course structure", "course scheme"
    ]) or ("online syllabus" in q_low)

    if is_syllabus_intent:
        if any(w in q_low for w in ["csbs", "business systems", "computer science and business"]):
            matched_syllabus = CSBS_SYLLABUS_DATA
        elif any(w in q_low for w in ["aiml", "ai & ml", "artificial intelligence"]):
            matched_syllabus = AIML_SYLLABUS_DATA
        elif any(w in q_low for w in ["ds", "data science", "aids"]):
            matched_syllabus = DS_SYLLABUS_DATA
        elif any(w in q_low for w in ["mechanical", "mech", "mccr"]):
            matched_syllabus = MECHANICAL_SYLLABUS_DATA
        elif any(w in q_low for w in ["electrical", "elect", "ele", "eecr"]):
            matched_syllabus = ELECTRICAL_SYLLABUS_DATA
        elif any(w in q_low for w in ["civil", "environmental", "cvcr"]):
            matched_syllabus = CIVIL_SYLLABUS_DATA
        elif any(w in q_low for w in ["etc", "entc", "electronics & telecomm", "electronics and telecomm", "telecom", "etcr"]):
            matched_syllabus = ETC_SYLLABUS_DATA
        elif any(w in q_low for w in ["biotech", "biotechnology", "btcr"]):
            matched_syllabus = BIOTECH_SYLLABUS_DATA
        elif any(w in q_low for w in ["fy", "first year", "f.y.", "bsh", "circuit branch", "core branch"]):
            matched_syllabus = FY_SYLLABUS_DATA
        elif any(w in q_low for w in ["cse", "computer science", "cscr"]):
            matched_syllabus = CSE_SYLLABUS_DATA
        else:
            # Default for general syllabus query
            matched_syllabus = GENERAL_SYLLABUS_DATA

        category = "academic" if category not in ["navigation", "clubs"] else category

    # 3.10 Official Cutoffs & Admission Portal detection (https://www.kitcoek.in/admission-undergraduate)
    cutoff_details = None
    is_cutoff_intent = any(kw in q_low for kw in [
        "cut off", "cutoff", "cut-off", "cutoffs", "cut offs", "cut-offs",
        "merit list", "merit lists", "cap round", "cap cutoff", "cet cutoff", "jee cutoff",
        "dse cutoff", "dsy cutoff", "fe cutoff", "first year cutoff",
        "what is the cutoff", "give me cut off", "give me cutoff", "cutoff list", "cut off list",
        "branch cutoff", "closing rank", "closing marks", "percentile required"
    ]) or (
        ("cut" in q_low and "off" in q_low) and any(w in q_low for w in ["list", "rank", "mark", "marks", "percentile", "score", "give", "show", "what", "how", "details"])
    )

    if is_cutoff_intent:
        cutoff_details = OFFICIAL_CUTOFF_DATA
        category = "academic" if category not in ["navigation", "clubs"] else category

    # 4. RAG Retrieval from Vector Store
    retrieved_chunks = vs.search(query, top_k=5, threshold=0.30)
    context_texts = [r["chunk_text"] for r in retrieved_chunks]

    # Prepend official Cutoff & Admission context if matched
    if cutoff_details:
        cutoff_ctx = [
            "OFFICIAL KITCOEK ADMISSION & CUTOFF DIRECTORY (Source: https://www.kitcoek.in/admission-undergraduate):",
            "Institute Name: Kolhapur Institute of Technology's College of Engineering (Autonomous), Kolhapur.",
            "DTE Choice Code: 6267.",
            "1. First Year B.Tech (F.Y. B.Tech / FE) Cutoffs:",
            "   - General Seat Type Cutoff Sheet: https://www.kitcoek.in/documents/admission/2025_26/FY%20General%20Cutoff-2024-25.jpeg",
            "   - Ladies Seat Type Cutoff Sheet: https://www.kitcoek.in/documents/admission/2025_26/FY%20Ladies%20Cutoff-2024-25.jpeg",
            "   - Indicative Branch Percentiles: CSE (93–94%+), CSE AIML (90–92%+), CSBS (88–90%+), ETC (85–88%+), Electrical & Mechanical (75–85%+), Civil & Biotech (70–80%+).",
            "2. Direct Second Year (D.S.Y. / DSE) Diploma Cutoffs (AY 2025–26 Official Record):",
            "   - Computer Science & Engineering (CSE): 93.65% (Top Merit No. 795)",
            "   - CSE (AI & ML): 92.88% (Merit No. 1200)",
            "   - CS & Business Systems (CSBS): 92.06% (Merit No. 1715)",
            "   - Electrical Engineering: 93.11% (Merit No. 1063)",
            "   - Civil Engineering: 92.84% (Merit No. 1227)",
            "   - Mechanical Engineering: 92.46% (Merit No. 1458)",
            "   - Electronics & Telecommunication (ETC): 92.47% (Merit No. 1438)",
            "   - Biotechnology: 75.66%",
            "   - DSY General Cutoff PDF: https://www.kitcoek.in/documents/admission/2026_27/dsy/DSY.B.Tech%20General%20Seat%20Type%20Wise%20Cut%20Off%202025-26.pdf",
            "   - DSY Ladies Cutoff PDF: https://www.kitcoek.in/documents/admission/2026_27/dsy/DSY%20B.Tech%20Ladies%20Seat%20Type%20Wise%20Cut%20Off%20A.Y.%202025-26.pdf",
            "3. Official Portals & Contact:",
            "   - Undergraduate Admission Portal: https://www.kitcoek.in/admission-undergraduate",
            "   - Online Admission Application / Inquiry: https://www.kitcoek.in/apply-admission",
            "   - Choice Codes: https://www.kitcoek.in/documents/admission/2025_26/Choice%20code.jpeg",
            "   - Required Documents List: https://www.kitcoek.in/documents/admission/2025_26/FY_List_of_Required_Documents.jpeg",
            "   - Admission Cell Email: admissions@kitcoek.in | Phone: +91-7769001199",
            "DIRECTIVE: Provide a thorough, well-formatted response with the official cutoff details for both First Year and Direct Second Year B.Tech, include direct links to the official sheets and PDFs hosted on kitcoek.in, mention DTE Choice Code 6267, and link to the official admission portal (https://www.kitcoek.in/admission-undergraduate)."
        ]
        context_texts.insert(0, "\n".join(cutoff_ctx))

    # Prepend official Student Clubs directory context if general clubs query
    if clubs_dir_summary:
        club_lines = [
            "OFFICIAL KITCOEK STUDENT CLUBS DIRECTORY (A.Y. 2025–26) — ALL 25 ACTIVE CLUBS:",
            "Technical Clubs: ISTE Student Chapter, Student Developers Club (SDC), Team Mavericks, Society of Women Engineers (SWE).",
            "Entrepreneurship: E-Cell KITCoEK.",
            "Cultural & Creative Arts: Cultural Club (Meraki annual gathering), AURA — The Art Club, Amateur Writers Club (AWC), Ek Bharat Shreshtha Bharat (EBSB).",
            "Leadership & Defense: Shourya Team KIT, National Cadet Corps (NCC 1 MAH ARTY BTY), Lead India (UPSC/MPSC).",
            "Social Service & Environment: National Service Scheme (NSS), Rotaract Club of KIT Sunshine, Petrichor — Green Club.",
            "Student Development: Walk With World (WWW), Women Development and Gender Equality Cell (WDGEC), Student Induction Program (SIP).",
            "Departmental Associations: ACSES (CSE), CABSSA & Bytearq (CSBS), MESA (Mechanical), ELESA (Electrical), ASSETS (ETC), CESA (Civil).",
            "DIRECTIVE: Present a structured, categorized directory listing of all 25 official student clubs at KITCOEK across Technical, Cultural, Leadership, Social, Environment, Student Development, and Departmental. DO NOT just show a single club profile unless specifically asked for."
        ]
        context_texts.insert(0, "\n".join(club_lines))

    # Prepend official syllabus context if matched
    if matched_syllabus:
        dept_name = matched_syllabus.get("department", "KITCOEK")
        syl_lines = [
            f"OFFICIAL KITCOEK ONLINE SYLLABUS DIRECTORY — {dept_name.upper()} NEP-2020 CURRICULUM (Source: https://www.kitcoek.in/online-syllabus):",
            f"College Scheme: {matched_syllabus.get('scheme', '2023 [NEP-2020] Scheme')}.",
            f"Department: {dept_name}.",
            "DIRECT OFFICIAL AWS S3 SYLLABUS PDF DOWNLOAD LINKS:"
        ]
        for y in matched_syllabus.get("years", []):
            syl_lines.append(f"- {y.get('year')}: {y.get('pdf_url')} | Description: {y.get('description')}")
        syl_lines.append("DIRECTIVE: Confirm the official syllabus for this department. Highlight key subjects and direct official PDF links. Note that verified download buttons are also displayed in the interactive syllabus card below.")
        context_texts.insert(0, "\n".join(syl_lines))

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
            "DIRECTIVE: Give a polite, concise overview (2-3 sentences max) confirming the class timetable and target academic years/batches (BSH for F.Y. / AIML for SY, TY, Final Year / CSBS). DO NOT output any URLs, Google Drive links, or <a> anchor tags in your text response, because an interactive 1-click timetable card is automatically displayed directly below your answer."
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
        guide_lines = [
            f"OFFICIAL KITCOEK VMEDULIFE GUIDE ({vmedulife_guide['title']}):",
            f"Portal URL: {vmedulife_guide.get('portal_url', 'https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur')}",
            "Step-by-step instructions:"
        ]
        for idx, s in enumerate(vmedulife_guide["steps"], start=1):
            guide_lines.append(f"{idx}. {s}")
        guide_lines.append("DIRECTIVE: Answer the student's question clearly, warmly, and politely with structured step-by-step instructions. Link to <a href='https://portal.vmedulife.com/public/auth/#/login/kit-kolhapur' target='_blank'>KITCoEK VMedulife Student Portal ↗</a>. DO NOT output irrelevant club reports, activity descriptions, or unconnected faculty names.")
        # Filter out irrelevant club chunks when query is specifically about portal/attendance/notes/result
        context_texts = [c for c in context_texts if "REPORT (2025" not in c and "Official Report" not in c and "Activity Report" not in c and "officer making" not in c.lower()]
        context_texts.insert(0, "\n".join(guide_lines))

    # Prepend official academic calendar or notice context if matched
    if matched_cals and not matched_notices:
        cal_ctx = [
            "OFFICIAL KITCOEK ACADEMIC CALENDARS (AY 2026–27 & 2025–26):",
            "The institute has officially released Academic Calendars for Autonomous Engineering programmes.",
            "Key Academic Milestones for AY 2026–27 (Odd Semester):",
            "1. S.Y., T.Y. & Final Year B.Tech:",
            "   - Term Commencement: 14th July, 2026",
            "   - S.Y. Induction: 21st to 26th July, 2026",
            "   - Mid-Semester Examination (MSE): 08th to 13th September, 2026 (Result: 24th Sept)",
            "   - KIT PBL Day: 05th November, 2026",
            "   - End of Regular Academic Term: 14th November, 2026 (Remedial Classes: 17th–20th Nov)",
            "   - End Semester Examination (Lab POE): 25th November to 03rd December, 2026",
            "   - End Semester Examination (Theory ESE): 15th December, 2026 to 10th January, 2027",
            "   - Even Semester Commencement: 19th January, 2027",
            "2. First Year (F.Y. B.Tech & F.Y. M.Tech):",
            "   - Student Induction Program (SIP): Phase-I (25–30 Aug), Phase-II (01–06 Sept), Phase-III (08–13 Sept 2026)",
            "   - Term Commencement: 01st September, 2026",
            "   - Mid-Semester Examination (MSE): 24th to 31st October, 2026 (Result: 14th Nov)",
            "   - End Semester Examination (Theory ESE): 01st to 12th January, 2027",
            "   - Even Semester Commencement: 15th January, 2027",
            "DIRECTIVE: Present a clean, well-structured overview of the key semester dates and milestones (Commencement, MSE, ESE, and Even Sem start). DO NOT output any URLs, raw PDF links, or <a> anchor tags in your text response, because a dedicated interactive Academic Calendar card with 1-click PDF download buttons is automatically displayed directly below your answer."
        ]
        context_texts.insert(0, "\n".join(cal_ctx))
    elif matched_notices or matched_cals:
        notice_ctx_lines = ["Official KITCOEK Notice Board & Academic Calendar Data (Source: https://www.kitcoek.in/notice):"]
        if matched_cals:
            notice_ctx_lines.append("Official Academic Calendars:")
            for cal in matched_cals:
                notice_ctx_lines.append(f"- {cal['title']} ({cal['academic_year']}, {cal['term']})")
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
    try:
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
    except Exception as dbe:
        print(f"[Warning] Chat history save skipped: {dbe}")
        try:
            db.rollback()
        except Exception:
            pass
    
    resp = ChatResponse(
        reply=linkify_urls(rag_result["answer"]),
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
        csbs_syllabus=matched_syllabus,
        syllabus_details=matched_syllabus,
        cutoff_details=cutoff_details,
        clubs_directory=clubs_dir_summary
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


