import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.core.config import settings

database_url = settings.DATABASE_URL
is_vercel = os.environ.get("VERCEL") is not None

# If running on Vercel serverless and using default SQLite, use /tmp (the only writable directory)
if is_vercel and (not database_url or database_url.startswith("sqlite")):
    database_url = "sqlite:////tmp/kitcoek.db"

# Handle SQLite vs PostgreSQL arguments
connect_args = {}
if database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    # Ensure directory exists for sqlite
    db_file = database_url.replace("sqlite:///", "")
    parent_dir = os.path.dirname(os.path.abspath(db_file))
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

try:
    engine = create_engine(database_url, connect_args=connect_args)
    # Test connection
    with engine.connect() as conn:
        pass
except Exception as e:
    # Graceful fallback to SQLite if PostgreSQL fails to connect
    print(f"[Warning] Failed to connect to {database_url}: {e}. Falling back to SQLite.")
    fallback_dir = "/tmp" if is_vercel else "./backend/data"
    os.makedirs(fallback_dir, exist_ok=True)
    fallback_url = f"sqlite:///{fallback_dir}/kitcoek.db"
    engine = create_engine(fallback_url, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
