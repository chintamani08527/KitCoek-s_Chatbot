import os
import time
import logging
from typing import List, Optional, Any
from google import genai
from google.genai import types
from google.genai.errors import ServerError, ClientError
from dotenv import load_dotenv
from backend.app.core.config import settings

load_dotenv()
logger = logging.getLogger(__name__)

class GeminiKey:
    def __init__(self, key: str, index: int or str):
        self.key = key
        self.index = index
        self.client: Optional[genai.Client] = None
        self.is_active = True
        self.fail_count = 0
        self.cooldown_until = 0.0
        self.last_used = 0.0

    def init_client(self) -> genai.Client:
        if not self.client:
            self.client = genai.Client(api_key=self.key)
        return self.client


class GeminiPool:
    def __init__(self):
        self.keys: List[GeminiKey] = []
        self._load_keys()
        self.current_index = 0
        self.cooldown_seconds = 60

    def _load_keys(self):
        self.keys = []
        seen_keys = set()

        # 1. Check numbered keys: GEMINI_API_KEY_1 to GEMINI_API_KEY_10
        for i in range(1, 11):
            key_val = os.getenv(f"GEMINI_API_KEY_{i}")
            if key_val and key_val.strip() and key_val.strip() not in seen_keys:
                self.keys.append(GeminiKey(key_val.strip(), i))
                seen_keys.add(key_val.strip())

        # 2. Check any other GEMINI_API_KEY_* variables in env
        for k, v in os.environ.items():
            if k.startswith("GEMINI_API_KEY_") and v and v.strip() and v.strip() not in seen_keys:
                idx = k.replace("GEMINI_API_KEY_", "")
                self.keys.append(GeminiKey(v.strip(), idx))
                seen_keys.add(v.strip())

        # 3. Check standard GEMINI_API_KEY (from config or env)
        standard_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        if standard_key and standard_key.strip() and standard_key.strip() not in seen_keys and standard_key != "your_gemini_api_key_here":
            self.keys.append(GeminiKey(standard_key.strip(), "default"))
            seen_keys.add(standard_key.strip())

        if self.keys:
            logger.info(f"[GeminiPool] Initialized with {len(self.keys)} API key(s): {[k.index for k in self.keys]}")
        else:
            logger.warning("[GeminiPool] No Gemini API keys found in environment.")

    def reload_keys(self):
        """Reload keys if .env has been updated during runtime."""
        load_dotenv(override=True)
        self._load_keys()

    def has_keys(self) -> bool:
        return len(self.keys) > 0

    def _get_next_available_key(self) -> Optional[GeminiKey]:
        if not self.keys:
            return None
            
        now = time.time()
        for _ in range(len(self.keys)):
            k = self.keys[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.keys)
            
            # Check if cooldown has expired
            if k.cooldown_until and now >= k.cooldown_until:
                k.is_active = True
                k.cooldown_until = 0.0
                k.fail_count = 0
                
            if k.is_active:
                return k
                
        # If all keys are in cooldown, reset the oldest one as fallback
        oldest_key = min(self.keys, key=lambda x: x.cooldown_until)
        oldest_key.is_active = True
        return oldest_key

    def mark_key_failed(self, key: GeminiKey, reason: str = ""):
        key.fail_count += 1
        key.is_active = False
        key.cooldown_until = time.time() + self.cooldown_seconds
        print(f"[GeminiPool] Key {key.index} marked inactive for {self.cooldown_seconds}s. Reason: {reason}")
        logger.warning(f"[GeminiPool] Key {key.index} marked inactive. Cooldown until {key.cooldown_until}. Reason: {reason}")

    def generate_content(
        self,
        model: str,
        contents: Any,
        config: Optional[types.GenerateContentConfig] = None
    ) -> Any:
        """Synchronous generate_content with automatic key failover on 429/500/503 errors."""
        if not self.keys:
            raise RuntimeError("No Gemini API keys configured in GeminiPool.")

        last_error = None
        for attempt in range(len(self.keys)):
            key = self._get_next_available_key()
            if not key:
                break
                
            client = key.init_client()
            key.last_used = time.time()
            
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config
                )
                return response
            except (ServerError, ClientError) as e:
                err_str = str(e).lower()
                code = getattr(e, "code", None)
                if code in (429, 500, 503) or "429" in err_str or "quota" in err_str or "exhausted" in err_str or "unavailable" in err_str:
                    self.mark_key_failed(key, reason=f"HTTP {code} / Quota or Server Error")
                    last_error = e
                    continue
                # For non-transient errors (e.g. invalid arguments), don't failover
                raise e
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str or "exhausted" in err_str:
                    self.mark_key_failed(key, reason="Quota exhausted")
                    last_error = e
                    continue
                self.mark_key_failed(key, reason=str(e))
                last_error = e
                continue

        if last_error:
            raise last_error
        raise RuntimeError("All Gemini API keys failed after multiple failover attempts.")

    def embed_content(
        self,
        model: str,
        contents: Any
    ) -> Any:
        """Embed content with automatic key failover on 429 quota exhaustion."""
        if not self.keys:
            raise RuntimeError("No Gemini API keys configured in GeminiPool.")

        last_error = None
        for attempt in range(len(self.keys)):
            key = self._get_next_available_key()
            if not key:
                break
                
            client = key.init_client()
            key.last_used = time.time()
            
            try:
                response = client.models.embed_content(
                    model=model,
                    contents=contents
                )
                return response
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str or "exhausted" in err_str or "resource_exhausted" in err_str:
                    self.mark_key_failed(key, reason="Embedding quota exhausted (429)")
                    last_error = e
                    continue
                raise e

        if last_error:
            raise last_error
        raise RuntimeError("All Gemini API keys failed for embeddings after failover attempts.")


# Global Singleton
_gemini_pool = None

def get_gemini_pool() -> GeminiPool:
    global _gemini_pool
    if _gemini_pool is None:
        _gemini_pool = GeminiPool()
    return _gemini_pool
