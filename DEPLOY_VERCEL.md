# Deploying KITCOEK Campus Assistant on Vercel

This project is configured to deploy directly to **Vercel** with a unified architecture:
- **Frontend**: Static UI (`index.html`, `style.css`, `script.js`, aerial map, and logos) served via Vercel's global CDN.
- **Backend**: FastAPI API served via Vercel Serverless Functions (`api/index.py`) using `@vercel/python`.

---

## 🚀 Quick Deployment via Vercel Web Dashboard (Recommended)

### Step 1: Push Repository to GitHub
Make sure your latest code is pushed to your GitHub repository:
```bash
git push origin main
```

### Step 2: Import into Vercel
1. Go to [https://vercel.com/new](https://vercel.com/new).
2. Select your repository: **`KitCoek-s_Chatbot`**.
3. Under **Framework Preset**, leave it as **Other** (Vercel will automatically read `vercel.json`).
4. Under **Root Directory**, keep it as `./` (Root).

### Step 3: Add Environment Variables in Vercel
Before clicking Deploy, expand **Environment Variables** in the Vercel project settings and add:

| Key | Value (from your `.env`) | Notes |
|---|---|---|
| `GEMINI_API_KEY_1` | `AQ.Ab8RN6I801B4nLnP9b86Ozi_Gc-q8Mwlkhm9bL5zmfHCkyblfw` | Key 1 for pool |
| `GEMINI_API_KEY_2` | `AQ.Ab8RN6JQkUohiPaWbbBEX2qqP6_NekrYdkLASqwAOAhXU5yo5Q` | Key 2 for pool |
| `GEMINI_API_KEY_3` | `AQ.Ab8RN6KxgZwwnBxMSyleKbRYsAA_dVwFEwmACI4a9GQ-eQibFg` | Key 3 for pool |
| `GEMINI_API_KEY_4` | `AQ.Ab8RN6LT8skvFN0DZ9fzzcg0Da5Q2MLVwoxuMAwOpFp7IsY0SQ` | Key 4 for pool |
| `GEMINI_API_KEY` | `AQ.Ab8RN6I801B4nLnP9b86Ozi_Gc-q8Mwlkhm9bL5zmfHCkyblfw` | Default fallback |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Ultra-fast model |
| `GEMINI_EMBEDDING_MODEL` | `models/gemini-embedding-001` | High-accuracy embeddings |
| `DATABASE_URL` | *(Optional)* | Default uses `/tmp/kitcoek.db` with auto-seed. You can also paste a free [Neon](https://neon.tech) or Supabase PostgreSQL connection string for persistent cloud SQL. |

### Step 4: Click "Deploy"
Vercel will install the requirements and launch your website! Once completed, you will receive your live domain (e.g., `https://kitcoek-assistant.vercel.app`).

---

## 💻 Alternative: Deploying via Vercel CLI

If you have `vercel` CLI installed:
```bash
# 1. Login to Vercel
vercel login

# 2. Deploy to Preview
vercel

# 3. Deploy to Production
vercel --prod
```

---

## 🛠️ Architecture Highlights on Vercel
1. **Zero PyTorch Bloat**: Lightweight `requirements.txt` keeps the build under Vercel's 250MB Serverless limits.
2. **Auto-Seeding**: Tables, 30 campus locations, and 25 student clubs auto-seed in <50ms if starting on a fresh container.
3. **Pre-Computed Vector Store**: `vector_index.json` is committed in git, so document RAG works immediately without re-embedding.
4. **Resilient Key Pool**: The 4-key Gemini pool distributes traffic evenly and handles rate limits automatically.
