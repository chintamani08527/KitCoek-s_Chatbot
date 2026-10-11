import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.models.models import DocumentRecord, ChatHistory, CampusLocation
from backend.app.schemas.schemas import (
    ChatRequest, ChatResponse, SourceCitation,
    LocationCreate, LocationResponse, DocumentResponse
)
from backend.app.services.vector_store import get_vector_store
from backend.app.services.gemini_service import get_gemini_service
from backend.app.services.document_processor import extract_text_from_file, chunk_text
import uuid
import os

router = APIRouter()

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
            "NEP-2020 syllabus, subjects, examinations, campus locations, and college notices. "
            "Please ask a question about KITCOEK.</p>"
        )
        return ChatResponse(
            reply=out_msg,
            category="out_of_scope",
            sources=[],
            follow_up_questions=[
                "What is the NEP-2020 syllabus for CSE?",
                "Where is the Central Library located?",
                "What are the passing rules for autonomous exams?"
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

    # 3. RAG Retrieval from Vector Store
    retrieved_chunks = vs.search(query, top_k=4, threshold=0.35)
    context_texts = [r["chunk_text"] for r in retrieved_chunks]
    
    # 4. Generate Answer via Gemini with Strict Grounding
    rag_result = gemini.generate_rag_answer(
        query=query,
        context_chunks=context_texts,
        location_data=matched_loc_data
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
    
    # 5. Persist Chat History in DB
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
        location_details=matched_loc_data
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
