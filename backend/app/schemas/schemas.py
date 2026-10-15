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
    category: str # "academic", "navigation", "clubs", "notices", "out_of_scope", "general"
    sources: List[SourceCitation] = []
    follow_up_questions: List[str] = []
    map_url: Optional[str] = None
    location_details: Optional[dict] = None
    club_details: Optional[dict] = None
    portal_url: Optional[str] = None
    notes_url: Optional[str] = None
    timetable_url: Optional[str] = None
    notices_details: Optional[List[dict]] = None
    notice_board_url: Optional[str] = None
    academic_calendars: Optional[List[dict]] = None

class StudentClubResponse(BaseModel):
    id: str
    name: str
    abbr: Optional[str] = None
    category: str
    tagline: Optional[str] = None
    establishment_year: Optional[str] = None
    description: str
    objectives: Optional[Any] = None
    major_activities: Optional[Any] = None
    skills_developed: Optional[Any] = None
    eligibility: Optional[str] = None
    faculty_coordinator: Optional[str] = None
    student_coordinators: Optional[str] = None
    achievements: Optional[str] = None
    academic_year: str = "2025–26"
    source_url: Optional[str] = None
    pdf_url: Optional[str] = None

    class Config:
        from_attributes = True

class ClubCategorySummary(BaseModel):
    category: str
    count: int

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
