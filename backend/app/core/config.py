import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "KITCOEK AI Assistant"
    APP_VERSION: str = "1.0.0"
    
    # Google Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_EMBEDDING_MODEL: str = "models/gemini-embedding-001"
    
    # Database
    DATABASE_URL: str = "sqlite:///./backend/data/kitcoek.db"
    
    # ChromaDB & Vector Store
    CHROMA_PERSIST_DIRECTORY: str = "./backend/data/chroma_db"
    
    # Retrieval
    TOP_K_RESULTS: int = 4
    SIMILARITY_THRESHOLD: float = 0.35
    
    # Admin / uploads
    UPLOAD_DIR: str = "./backend/data/documents/uploads"
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
