import os
import json
import uuid
from backend.app.db.database import SessionLocal, engine, Base
from backend.app.models.models import DocumentRecord, CampusLocation, StudentClub
from backend.app.services.document_processor import extract_text_from_file, chunk_text
from backend.app.services.vector_store import get_vector_store

def init_database_and_ingest():
    print("[1/5] Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    vs = get_vector_store()

    # Ingest campus locations
    print("[2/5] Ingesting structured campus location data...")
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

    # Ingest student clubs structured data
    print("[3/5] Ingesting structured student clubs...")
    clubs_file = "./backend/data/clubs/kitcoek_clubs.json"
    if os.path.exists(clubs_file):
        with open(clubs_file, "r", encoding="utf-8") as f:
            clubs = json.load(f)
            for c in clubs:
                existing_club = db.query(StudentClub).filter(StudentClub.id == c["id"]).first()
                if not existing_club:
                    existing_club = StudentClub(id=c["id"])
                    db.add(existing_club)
                
                existing_club.name = c["name"]
                existing_club.abbr = c.get("abbr")
                existing_club.category = c["category"]
                existing_club.tagline = c.get("tagline")
                existing_club.establishment_year = c.get("establishment_year")
                existing_club.description = c["description"]
                existing_club.objectives = json.dumps(c.get("objectives", [])) if isinstance(c.get("objectives"), list) else c.get("objectives")
                existing_club.major_activities = json.dumps(c.get("major_activities", [])) if isinstance(c.get("major_activities"), list) else c.get("major_activities")
                existing_club.skills_developed = json.dumps(c.get("skills_developed", [])) if isinstance(c.get("skills_developed"), list) else c.get("skills_developed")
                existing_club.eligibility = c.get("eligibility")
                existing_club.faculty_coordinator = c.get("faculty_coordinator")
                existing_club.student_coordinators = c.get("student_coordinators")
                existing_club.achievements = c.get("achievements")
                existing_club.academic_year = c.get("academic_year", "2025–26")
                existing_club.source_url = c.get("source_url")
                existing_club.pdf_url = c.get("pdf_url")
            db.commit()
            print(f"Loaded {len(clubs)} student clubs into database.")

    # Ingest official college documents
    print("[4/5] Ingesting official college documents into vector store...")
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

    # Ingest student clubs reports into vector store
    print("[5/5] Ingesting student club PDF reports into vector store...")
    clubs_meta_file = "./backend/data/clubs/kitcoek_clubs.json"
    raw_clubs_file = "./backend/data/clubs/raw_clubs_extracted.json"
    
    raw_by_id = {}
    if os.path.exists(raw_clubs_file):
        with open(raw_clubs_file, "r", encoding="utf-8") as f:
            for rc in json.load(f):
                raw_by_id[rc["id"]] = rc

    if os.path.exists(clubs_meta_file):
        with open(clubs_meta_file, "r", encoding="utf-8") as f:
            clubs = json.load(f)
            for c in clubs:
                cid = c["id"]
                cname = c["name"]
                doc_id = f"club_{cid}"
                vs.delete_document(doc_id)
                
                # Chunk 1: Club Identity, Purpose, Coordinators & Objectives
                chunk1 = (
                    f"STUDENT CLUB PROFILE: {cname} ({c.get('abbr', '')})\n"
                    f"Category: {c['category']} | Academic Year: {c.get('academic_year', '2025–26')}\n"
                    f"Tagline: {c.get('tagline', 'N/A')} | Established: {c.get('establishment_year', 'N/A')}\n"
                    f"Faculty Coordinator: {c.get('faculty_coordinator', 'Not published')}\n"
                    f"Student Coordinators / Office-Bearers: {c.get('student_coordinators', 'Not published')}\n\n"
                    f"About the Club:\n{c['description']}\n\n"
                    f"Main Objectives:\n" + "\n".join([f"- {o}" for o in (c.get('objectives') or [])])
                )

                # Chunk 2: Skills, Eligibility, Joining & Major Activities
                chunk2 = (
                    f"{cname} — SKILLS, ELIGIBILITY & KEY ACTIVITIES ({c.get('academic_year', '2025–26')}):\n"
                    f"Skills Students Develop:\n" + ", ".join(c.get('skills_developed') or []) + "\n\n"
                    f"Eligibility & Membership:\n{c.get('eligibility', 'Open to all interested students.')}\n\n"
                    f"Major Events & Activities Conducted:\n" + "\n".join([f"• {a}" for a in (c.get('major_activities') or [])]) + "\n\n"
                    f"Achievements: {c.get('achievements', 'N/A')}\n"
                    f"Official Report Link: {c.get('pdf_url')}\n"
                    f"Official Source URL: {c.get('source_url')}"
                )

                club_chunks = [chunk1, chunk2]

                # Chunk 3+: Add high-signal extracts from actual report pages if available
                if cid in raw_by_id:
                    full_text = raw_by_id[cid].get("full_text", "")
                    # Filter out repetitive headers
                    clean_lines = [l.strip() for l in full_text.split("\n") if len(l.strip()) > 30 and "KIT" not in l and "Page" not in l]
                    if clean_lines:
                        body_excerpt = "\n".join(clean_lines[:45])
                        if len(body_excerpt) > 200:
                            chunk3 = f"{cname} — EXTRACTED OFFICIAL ACTIVITY REPORT ({c.get('academic_year', '2025–26')}):\n{body_excerpt[:1500]}"
                            club_chunks.append(chunk3)

                meta = {
                    "club_id": cid,
                    "club_name": cname,
                    "category": c.get("category", "Student Clubs"),
                    "academic_year": c.get("academic_year", "2025–26"),
                    "pdf_url": c.get("pdf_url"),
                    "source_url": c.get("source_url")
                }
                indexed_count = vs.add_chunks(
                    document_id=doc_id,
                    document_name=f"{cname} Official Report ({c.get('academic_year', '2025–26')})",
                    category="Student Clubs",
                    chunks=club_chunks,
                    extra_metadata=meta
                )
                print(f"Indexed {indexed_count} high-signal chunks for: {cname}")

    db.close()
    print("Knowledge base & Student Clubs ingestion complete!")

if __name__ == "__main__":
    init_database_and_ingest()
