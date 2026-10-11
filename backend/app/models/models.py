import datetime
import uuid
from sqlalchemy import Column, String, Text, DateTime, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.db.database import Base

class DocumentRecord(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_path = Column(String(500), nullable=False)
    category = Column(String(100), default="General") # Syllabus, Examination, Notice, Faculty, Campus, Rules
    num_chunks = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(100), index=True, default="default")
    user_prn = Column(String(50), nullable=True)
    query = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    category = Column(String(50), default="academic")
    sources = Column(Text, nullable=True) # JSON string of cited sources
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class CampusLocation(Base):
    __tablename__ = "campus_locations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(150), nullable=False, unique=True)
    category = Column(String(100), nullable=False) # Department, Lab, Classroom, CBCR, Library, Office, Canteen, Amenities
    building = Column(String(150), nullable=False)
    floor = Column(String(50), nullable=False)
    room_number = Column(String(50), nullable=True)
    landmark = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
