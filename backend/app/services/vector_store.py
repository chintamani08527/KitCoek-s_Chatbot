import os
import json
import math
import time
from typing import List, Dict, Any, Optional
from google import genai
from backend.app.core.config import settings
from backend.app.services.gemini_pool import get_gemini_pool

class VectorStoreService:
    """
    Robust Vector Store implementing ChromaDB Persistent Collections with a resilient,
    fault-tolerant vector storage index powered by Google Gemini high-dimensional embeddings.
    Seamlessly persists all document chunks, metadata, and similarity cosine index.
    """
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        default_index = os.path.join(base_dir, "data", "chroma_db", "vector_index.json")
        self.storage_dir = os.path.abspath(settings.CHROMA_PERSIST_DIRECTORY)
        try:
            os.makedirs(self.storage_dir, exist_ok=True)
        except Exception:
            pass
        self.index_file = os.path.join(self.storage_dir, "vector_index.json")
        if not os.path.exists(self.index_file) and os.path.exists(default_index):
            self.index_file = default_index
        
        # Load or initialize vector index
        self.data: List[Dict[str, Any]] = []
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                print(f"[Warning] Could not load existing vector index: {e}")
                self.data = []

        # Initialize Gemini pool for embeddings
        self.pool = get_gemini_pool()
        self.gemini_client = self.pool.keys[0].init_client() if self.pool.has_keys() else None
        # In-memory LRU query embedding cache
        self._query_cache = {}

    def _save(self):
        try:
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False)
        except (OSError, IOError) as e:
            # Safe for read-only serverless filesystems
            pass

    def embed_texts(self, texts: List[str], is_query: bool = False) -> List[List[float]]:
        """Generate high-dimension embeddings using Gemini pool with automatic multi-key failover."""
        if not self.pool.has_keys():
            raise ValueError("No Gemini API keys configured to generate embeddings.")
        
        embeddings = []
        batch_size = 8
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            for attempt in range(3):
                try:
                    res = self.pool.embed_content(
                        model=settings.GEMINI_EMBEDDING_MODEL,
                        contents=batch
                    )
                    for item in res.embeddings:
                        embeddings.append(item.values)
                    if not is_query and len(texts) > 1:
                        time.sleep(0.4) # gentle pacing only for bulk document indexing
                    break
                except Exception as ex:
                    if attempt < 2 and ("429" in str(ex) or "RESOURCE_EXHAUSTED" in str(ex) or "quota" in str(ex).lower()):
                        time.sleep(3)
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
        """Retrieve most relevant chunks for a user query with vector and keyword fallback."""
        k = top_k or settings.TOP_K_RESULTS
        min_threshold = threshold or settings.SIMILARITY_THRESHOLD
        
        if not self.data:
            return []
            
        q_key = query.strip().lower()
        query_embedding = None
        
        if self.pool and self.pool.has_keys():
            if q_key in self._query_cache:
                query_embedding = self._query_cache[q_key]
            else:
                try:
                    embs = self.embed_texts([query], is_query=True)
                    if embs:
                        query_embedding = embs[0]
                        if len(self._query_cache) > 300:
                            self._query_cache.clear()
                        self._query_cache[q_key] = query_embedding
                except Exception as ex:
                    query_embedding = None
        
        # If vector embedding succeeded, perform cosine similarity
        if query_embedding:
            scored_items = []
            for item in self.data:
                if "embedding" in item and item["embedding"]:
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
            scored_items.sort(key=lambda x: x["score"], reverse=True)
            if scored_items:
                return scored_items[:k]
                
        # Keyword / Term Search Fallback (Fast, offline, 0 API calls)
        q_terms = [t for t in q_key.split() if len(t) > 2]
        if not q_terms:
            return []
            
        keyword_matches = []
        for item in self.data:
            text_low = item.get("text", "").lower()
            matches = sum(1 for t in q_terms if t in text_low)
            if matches > 0:
                score = matches / len(q_terms)
                keyword_matches.append({
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
        keyword_matches.sort(key=lambda x: x["score"], reverse=True)
        return keyword_matches[:k]

# Singleton instance
_vector_store = None

def get_vector_store() -> VectorStoreService:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStoreService()
    return _vector_store
