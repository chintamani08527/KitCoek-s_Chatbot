# KITCOEK AI Assistant — Frontend

This zip folder contains the complete frontend codebase for the **KITCOEK AI Assistant** web application.

## 📁 Files Included
- **`index.html`**: Direct Chatbot & Campus Assistant interface (no login required; direct access to AI chat, 18 student clubs directory, aerial map, and quick query chips).
- **`style.css`**: Complete responsive layout styling, modern typography, club cards, aerial map lightbox, and modals.
- **`script.js`**: Client-side logic, API calls, chat bubble rendering, speech-to-text voice input, and filter controls.
- **`campus_map.jpg`**: Official aerial layout photo of the KITCoEK campus.

## 🚀 How to Run & Preview
### 1. Standalone / VS Code Live Server
You can open `index.html` directly in any web browser or use the **VS Code Live Server** extension.

### 2. Connected to FastAPI Backend
When running alongside the FastAPI backend (`http://127.0.0.1:8000`), the frontend connects to:
- `POST /api/chat` — AI Assistant query response with RAG grounding
- `GET /api/clubs` — All 18 verified Student Clubs directory
- `GET /api/clubs/categories` — Club categories (Technical, Entrepreneurship, Cultural, Leadership, etc.)
- `GET /api/locations/map` — Campus aerial layout map
