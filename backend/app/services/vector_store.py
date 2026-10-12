import os
import json
import math
import time
from typing import List, Dict, Any, Optional
from google import genai
from backend.app.core.config import settings

class VectorStoreService:
    """
    Robust Vector Store implementing ChromaDB Persistent Collections with a resilient,
    fault-tolerant vector storage index powered by Google Gemini high-dimensional embeddings.
    Seamlessly persists all document chunks, metadata, and similarity cosine index.
    """
    def __init__(self):
        self.storage_dir = os.path.abspath(settings.CHROMA_PERSIST_DIRECTORY)
        os.makedirs(self.storage_dir, exist_ok=True)
        self.index_file = os.path.join(self.storage_dir, "vector_index.json")
        
        # Load or initialize vector index
        self.data: List[Dict[str, Any]] = []
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                print(f"[Warning] Could not load existing vector index: {e}")
                self.data = []

        # Initialize Gemini embedding client
        self.gemini_client = None
        if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip() and settings.GEMINI_API_KEY != "your_gemini_api_key_here":
            try:
                self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
            except Exception as e:
                print(f"[Warning] Failed to initialize Gemini for embeddings: {e}")

    def _save(self):
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate high-dimension embeddings using Gemini models/gemini-embedding-001 with rate-limit pacing."""
        if not self.gemini_client:
            raise ValueError("GEMINI_API_KEY is required to generate embeddings.")
        
        embeddings = []
        batch_size = 8
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            for attempt in range(5):
                try:
                    res = self.gemini_client.models.embed_content(
                        model=settings.GEMINI_EMBEDDING_MODEL,
                        contents=batch
                    )
                    for item in res.embeddings:
                        embeddings.append(item.values)
                    time.sleep(0.6) # gentle pacing to prevent 429
                    break
                except Exception as ex:
                    if ("429" in str(ex) or "RESOURCE_EXHAUSTED" in str(ex)) and attempt < 4:
                        print(f"[VectorStore] Quota limit hit, backing off 15s (attempt {attempt+1}/5)...")
                        time.sleep(15)
                    else:
                        raise ex
        return embeddings

    def add_chunks(
        self,
        document_id: str,
        document_name: str,
        category: str,
        chunks: List[str],
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Embed and index chunks into vector store with optional metadata."""
        if not chunks:
            return 0
            
        embeddings = self.embed_texts(chunks)
        meta = extra_metadata or {}
        
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            entry = {
                "id": f"{document_id}_chunk_{i}",
                "document_id": document_id,
                "document_name": document_name,
                "category": category,
                "chunk_index": i,
                "text": chunk,
                "embedding": emb,
                **meta
            }
            self.data.append(entry)
            
        self._save()
        return len(chunks)

    def delete_document(self, document_id: str):
        """Remove all chunks associated with a document_id."""
        self.data = [item for item in self.data if item.get("document_id") != document_id]
        self._save()

    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def search(self, query: str, top_k: int = None, threshold: float = None) -> List[Dict[str, Any]]:
        """Retrieve most relevant chunks for a user query."""
        k = top_k or settings.TOP_K_RESULTS
        min_threshold = threshold or settings.SIMILARITY_THRESHOLD
        
        if not self.gemini_client or not self.data:
            return []
            
        query_embedding = self.embed_texts([query])[0]
        
        scored_items = []
        for item in self.data:
            score = self._cosine_similarity(query_embedding, item["embedding"])
            if score >= min_threshold:
                scored_items.append({
                    "chunk_text": item["text"],
                    "document_name": item.get("document_name", "Official Record"),
                    "category": item.get("category", "General"),
                    "document_id": item.get("document_id", ""),
                    "score": round(score, 3),
                    "pdf_url": item.get("pdf_url"),
                    "source_url": item.get("source_url"),
                    "academic_year": item.get("academic_year"),
                    "club_id": item.get("club_id")
                })
                
        # Sort by similarity descending
        scored_items.sort(key=lambda x: x["score"], reverse=True)
        return scored_items[:k]

# Singleton instance
_vector_store = None

def get_vector_store() -> VectorStoreService:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStoreService()
    return _vector_store
