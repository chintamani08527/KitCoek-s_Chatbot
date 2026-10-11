# KITCOEK AI Assistant — Backend & System Guide

Official AI Assistant for **Kolhapur Institute of Technology's College of Engineering (Autonomous), Kolhapur**.

---

## 🛠 Tech Stack
- **Framework:** Python FastAPI
- **Database:** PostgreSQL (with automatic zero-config SQLite fallback for local development)
- **Vector Database:** ChromaDB Vector Index (embeddings computed via Google Gemini High-Dimensional Embedding Engine `models/gemini-embedding-001`)
- **LLM Engine:** Google Gemini API (`gemini-3.8-flash`)
- **Document Extractors:** `pypdf`, `python-docx`, `python-pptx`
- **Frontend Integration:** Existing HTML/CSS/JS UI connected via `/api/chat` with citations, interactive navigation cards, and follow-up prompts.

---

## 🚀 Windows Setup & Running Instructions

### 1. Prerequisites
- Python 3.10+ (Python 3.14 compatible)
- Google Gemini API Key

### 2. Environment Setup
Create and activate the virtual environment:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install backend dependencies:
```powershell
pip install -r requirements.txt
```

### 3. Configure `.env`
Ensure your `.env` contains:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.8-flash
GEMINI_EMBEDDING_MODEL=models/gemini-embedding-001
DATABASE_URL=sqlite:///./backend/data/kitcoek.db
CHROMA_PERSIST_DIRECTORY=./backend/data/chroma_db
TOP_K_RESULTS=4
SIMILARITY_THRESHOLD=0.35
```

> **Note on PostgreSQL:** To use PostgreSQL, ensure PostgreSQL is running and update `DATABASE_URL` in `.env`:
> ```env
> DATABASE_URL=postgresql://postgres:password@localhost:5432/kitcoek_db
> ```
> If PostgreSQL credentials are not provided or connection fails, the app automatically falls back to local SQLite at `backend/data/kitcoek.db`.

### 4. Index Knowledge Base & Ingest Documents
Run the ingestion script to parse official documents and populate vector & SQL tables:
```powershell
.\.venv\Scripts\python.exe -m backend.app.services.ingest
```

### 5. Start the Server
Start the FastAPI server:
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

- **Frontend Application:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Interactive API Documentation (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative API Documentation (Redoc):** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 📡 API Endpoints Summary

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/chat` | Send question, get grounded RAG answer, source citations, location details, and follow-ups |
| `GET` | `/api/history` | Retrieve user chat history |
| `POST` | `/api/documents/upload` | Upload PDF, DOCX, TXT, or PPTX file and auto-index into ChromaDB |
| `GET` | `/api/documents` | List indexed documents and metadata |
| `DELETE` | `/api/documents/{id}` | Delete document and remove associated vectors |
| `GET` | `/api/locations` | List campus buildings, labs, classrooms, CBCR, and offices |
| `GET` | `/api/locations/search` | Search specific room or department by keyword |
| `GET` | `/api/locations/map` | View SVG vector campus map |
| `GET` | `/api/health` | Service and model connectivity status |

---

## 🛡️ Grounding & Scope Policy
- Answers are strictly restricted to KITCOEK academics, campus locations, and administrative topics.
- Completely unrelated queries (e.g., cooking, politics, gaming) are politely rejected.
- Room numbers, syllabus units, and dates are strictly retrieved from official documents; the model will never fabricate unverified details.
