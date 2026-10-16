import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
import json
import uuid
from backend.app.core.config import settings
from backend.app.api.endpoints import router as api_router
from backend.app.db.database import engine, Base, SessionLocal
from backend.app.models.models import CampusLocation, StudentClub

# Create tables
Base.metadata.create_all(bind=engine)

def auto_seed_database_if_needed():
    try:
        db = SessionLocal()
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Check campus locations
        if db.query(CampusLocation).count() == 0:
            loc_file = os.path.join(base_dir, "data", "maps", "campus_locations.json")
            if os.path.exists(loc_file):
                with open(loc_file, "r", encoding="utf-8") as f:
                    for loc in json.load(f):
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

        # Check student clubs
        if db.query(StudentClub).count() == 0:
            clubs_file = os.path.join(base_dir, "data", "clubs", "kitcoek_clubs.json")
            if os.path.exists(clubs_file):
                with open(clubs_file, "r", encoding="utf-8") as f:
                    for c in json.load(f):
                        club = StudentClub(
                            id=c["id"],
                            name=c["name"],
                            abbr=c.get("abbr"),
                            category=c["category"],
                            tagline=c.get("tagline"),
                            establishment_year=c.get("establishment_year"),
                            description=c["description"],
                            objectives=json.dumps(c.get("objectives", [])) if isinstance(c.get("objectives"), list) else c.get("objectives"),
                            major_activities=json.dumps(c.get("major_activities", [])) if isinstance(c.get("major_activities"), list) else c.get("major_activities"),
                            skills_developed=json.dumps(c.get("skills_developed", [])) if isinstance(c.get("skills_developed"), list) else c.get("skills_developed"),
                            eligibility=c.get("eligibility"),
                            faculty_coordinator=c.get("faculty_coordinator"),
                            student_coordinators=c.get("student_coordinators"),
                            achievements=c.get("achievements"),
                            academic_year=c.get("academic_year", "2025–26"),
                            source_url=c.get("source_url"),
                            pdf_url=c.get("pdf_url"),
                            department=c.get("department"),
                            website_url=c.get("website_url")
                        )
                        db.add(club)
                db.commit()
        db.close()
    except Exception as e:
        print(f"[Warning] Auto-seed error: {e}")

auto_seed_database_if_needed()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Official KITCOEK AI Assistant Backend API with RAG, Gemini 3.8, and Campus Navigation",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware to allow frontend connectivity
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Vercel internal rewrite path restoration middleware
@app.middleware("http")
async def restore_vercel_path(request, call_next):
    matched_path = request.headers.get("x-matched-path")
    if matched_path and request.scope.get("path") in ("/api/index.py", "/index.py", "/api/index", "/api", "/api/"):
        request.scope["path"] = matched_path
    return await call_next(request)

# API routes (support both /api/* and direct /* for Vercel compatibility)
app.include_router(api_router, prefix="/api")
app.include_router(api_router)

from fastapi import Request
@app.get("/api/debug-info")
@app.get("/debug-info")
def debug_info(request: Request):
    return {
        "scope_path": request.scope.get("path"),
        "headers": {k: v for k, v in request.headers.items() if not k.lower().startswith("authorization")}
    }

# Map endpoint
@app.get("/api/locations/map")
@app.get("/locations/map")
def get_campus_map():
    map_jpg = "./backend/data/maps/campus_map.jpg"
    if os.path.exists(map_jpg):
        return FileResponse(map_jpg, media_type="image/jpeg", filename="kitcoek_campus_map.jpg")
    map_path = "./backend/data/maps/campus_map.svg"
    if os.path.exists(map_path):
        return FileResponse(map_path, media_type="image/svg+xml")
    return {"error": "Campus map not found"}

@app.get("/campus_map.jpg")
def serve_campus_map_direct():
    if os.path.exists("./campus_map.jpg"):
        return FileResponse("./campus_map.jpg", media_type="image/jpeg")
    map_jpg = "./backend/data/maps/campus_map.jpg"
    if os.path.exists(map_jpg):
        return FileResponse(map_jpg, media_type="image/jpeg")
    return {"error": "Campus map not found"}

# Health check endpoint (aliased for both /api/health and /health)
@app.get("/api/health")
@app.get("/health")
def health_check():
    from backend.app.services.gemini_service import get_gemini_service
    gemini = get_gemini_service()
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "database": settings.DATABASE_URL.split("///")[0],
        "gemini_configured": gemini.is_configured(),
        "model": settings.GEMINI_MODEL
    }

# Mount static frontend root files for single-origin serving if opened directly
if os.path.exists("./style.css"):
    NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}

    @app.get("/")
    def serve_index():
        return FileResponse("index.html", headers=NO_CACHE)
    
    @app.get("/style.css")
    def serve_css():
        return FileResponse("style.css", media_type="text/css", headers=NO_CACHE)

    @app.get("/script.js")
    def serve_js():
        return FileResponse("script.js", media_type="application/javascript", headers=NO_CACHE)

    @app.get("/favicon.ico")
    def serve_favicon():
        if os.path.exists("favicon.ico"):
            return FileResponse("favicon.ico", media_type="image/x-icon")
        return {"error": "Favicon not found"}

    @app.get("/kit-emblem.png")
    def serve_kit_emblem():
        return FileResponse("kit-emblem.png", media_type="image/png")

    @app.get("/kit-logo.png")
    def serve_kit_logo():
        return FileResponse("kit-logo.png", media_type="image/png")

    @app.get("/kit-logo-banner.png")
    def serve_kit_logo_banner():
        return FileResponse("kit-logo-banner.png", media_type="image/png")

    @app.get("/kit-emblem-raw.png")
    def serve_kit_emblem_raw():
        return FileResponse("kit-emblem-raw.png", media_type="image/png")

    @app.get("/login.html")
    @app.get("/Login.html")
    def serve_login():
        return RedirectResponse(url="/")

