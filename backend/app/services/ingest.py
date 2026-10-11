import os
import json
import uuid
from backend.app.db.database import SessionLocal, engine, Base
from backend.app.models.models import DocumentRecord, CampusLocation
from backend.app.services.document_processor import extract_text_from_file, chunk_text
from backend.app.services.vector_store import get_vector_store

def init_database_and_ingest():
    print("[1/4] Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    vs = get_vector_store()

    # Ingest campus locations
    print("[2/4] Ingesting structured campus location data...")
    loc_file = "./backend/data/maps/campus_locations.json"
    if os.path.exists(loc_file):
        with open(loc_file, "r", encoding="utf-8") as f:
            locations = json.load(f)
            for loc in locations:
                existing = db.query(CampusLocation).filter(CampusLocation.name == loc["name"]).first()
                if not existing:
                    db_loc = CampusLocation(
                        id=str(uuid.uuid4()),
                        name=loc["name"],
                        category=loc["category"],
                        building=loc["building"],
                        floor=loc["floor"],
                        room_number=loc.get("room_number"),
                        landmark=loc.get("landmark"),
                        description=loc.get("description")
                    )
                    db.add(db_loc)
        db.commit()
        print("Campus locations loaded.")

    # Ingest official documents
    print("[3/4] Ingesting official college documents into vector store...")
    docs_dir = "./backend/data/documents"
    for fname in os.listdir(docs_dir):
        fpath = os.path.join(docs_dir, fname)
        if os.path.isfile(fpath) and fname.endswith((".txt", ".pdf", ".docx", ".pptx")):
            existing_doc = db.query(DocumentRecord).filter(DocumentRecord.filename == fname).first()
            category = "Syllabus" if "syllabus" in fname.lower() else "Campus"
            
            print(f"Processing: {fname}...")
            text = extract_text_from_file(fpath)
            chunks = chunk_text(text, chunk_size=450, overlap=60)
            
            doc_id = existing_doc.id if existing_doc else str(uuid.uuid4())
            if not existing_doc:
                db_doc = DocumentRecord(
                    id=doc_id,
                    filename=fname,
                    file_type=os.path.splitext(fname)[1],
                    file_path=fpath,
                    category=category,
                    num_chunks=len(chunks)
                )
                db.add(db_doc)
                db.commit()
            
            # Index into vector store
            vs.delete_document(doc_id)
            indexed_count = vs.add_chunks(doc_id, fname, category, chunks)
            print(f"Indexed {indexed_count} chunks for {fname}.")

    db.close()
    print("[4/4] Knowledge base ingestion complete!")

if __name__ == "__main__":
    init_database_and_ingest()
