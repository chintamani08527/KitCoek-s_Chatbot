import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from backend.app.core.config import settings
from backend.app.api.endpoints import router as api_router
from backend.app.db.database import engine, Base

# Create tables
Base.metadata.create_all(bind=engine)

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

# API routes
app.include_router(api_router, prefix="/api")

# Map endpoint
@app.get("/api/locations/map")
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
    map_jpg = "./backend/data/maps/campus_map.jpg"
    if os.path.exists(map_jpg):
        return FileResponse(map_jpg, media_type="image/jpeg")
    return {"error": "Campus map not found"}

# Health check endpoint
@app.get("/api/health")
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
    # Serve index.html and assets directly
    @app.get("/")
    def serve_index():
        return FileResponse("index.html")
    
    @app.get("/style.css")
    def serve_css():
        return FileResponse("style.css", media_type="text/css")

    @app.get("/script.js")
    def serve_js():
        return FileResponse("script.js", media_type="application/javascript")

    @app.get("/login.html")
    @app.get("/Login.html")
    def serve_login():
        return RedirectResponse(url="/")

