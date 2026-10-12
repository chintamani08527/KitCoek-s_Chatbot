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
import uuid
import os

router = APIRouter()

def format_club_dict(club: StudentClub) -> dict:
    return {
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
        "pdf_url": club.pdf_url
    }

@router.post("/chat", response_model=ChatResponse)
def handle_chat(req: ChatRequest, db: Session = Depends(get_db)):
    gemini = get_gemini_service()
    vs = get_vector_store()
    
    query = req.message.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
        
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

    # 2. Location retrieval if navigational
    matched_loc_data = None
    map_url = None
    if category == "navigation" or any(kw in query.lower() for kw in ["where", "location", "floor", "room", "building", "cbcr", "library", "canteen", "mccr", "cscr", "bshcr", "csamcr", "csdscr", "etcr", "btcr", "eecr", "cvcr"]):
        locations = db.query(CampusLocation).all()
        q_clean = query.lower().replace("-", " ")
        q_tokens = [t for t in q_clean.split() if len(t) >= 3]
        for loc in locations:
            loc_name_lower = loc.name.lower()
            loc_rooms_lower = (loc.room_number or "").lower().replace("-", " ")
            if any(tok in loc_name_lower or tok in loc_rooms_lower for tok in q_tokens if tok not in ["where", "what", "which", "floor", "room", "located", "hall"]):
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

    # 3. Student Clubs matching & context retrieval
    matched_club_data = None
    clubs_dir_summary = None
    q_low = query.lower()
    
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
                club_terms.extend(["cultural club", "meraki", "cultural committee"])
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

    # 4. RAG Retrieval from Vector Store
    retrieved_chunks = vs.search(query, top_k=5, threshold=0.30)
    context_texts = [r["chunk_text"] for r in retrieved_chunks]
    
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
    
    return ChatResponse(
        reply=rag_result["answer"],
        category=category,
        sources=citations,
        follow_up_questions=rag_result.get("follow_up_questions", []),
        map_url=map_url,
        location_details=matched_loc_data,
        club_details=matched_club_data
    )

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


