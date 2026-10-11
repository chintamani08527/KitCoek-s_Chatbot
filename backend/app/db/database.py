import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.core.config import settings

database_url = settings.DATABASE_URL

# Handle SQLite vs PostgreSQL arguments
connect_args = {}
if database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    # Ensure directory exists for sqlite
    db_file = database_url.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(os.path.abspath(db_file)), exist_ok=True)

try:
    engine = create_engine(database_url, connect_args=connect_args)
    # Test connection
    with engine.connect() as conn:
        pass
except Exception as e:
    # Graceful fallback to SQLite if PostgreSQL fails to connect
    print(f"[Warning] Failed to connect to {database_url}: {e}. Falling back to SQLite.")
    fallback_url = "sqlite:///./backend/data/kitcoek.db"
    os.makedirs("./backend/data", exist_ok=True)
    engine = create_engine(fallback_url, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
