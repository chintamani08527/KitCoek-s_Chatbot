from typing import List, Optional, Any
from pydantic import BaseModel

class SourceCitation(BaseModel):
    document_name: str
    category: str
    chunk_text: str
    score: Optional[float] = None

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    student_prn: Optional[str] = None
    student_name: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    category: str # "academic", "navigation", "out_of_scope", "general"
    sources: List[SourceCitation] = []
    follow_up_questions: List[str] = []
    map_url: Optional[str] = None
    location_details: Optional[dict] = None

class LocationCreate(BaseModel):
    name: str
    category: str
    building: str
    floor: str
    room_number: Optional[str] = None
    landmark: Optional[str] = None
    description: Optional[str] = None

class LocationResponse(BaseModel):
    id: str
    name: str
    category: str
    building: str
    floor: str
    room_number: Optional[str] = None
    landmark: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True

class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    category: str
    num_chunks: int
    created_at: Any

    class Config:
        from_attributes = True
