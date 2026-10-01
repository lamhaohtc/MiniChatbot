from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    return int(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    provider: str                 # "gemini" or "openai"
    gemini_api_key: str
    gemini_model: str             # comma-separated; later entries are fallbacks on 503/404
    openai_api_key: str
    openai_model: str
    vector_store_id: str          # Gemini: fileSearchStores/...  OpenAI: vs_...
    vector_store_name: str
    zendesk_base_url: str
    zendesk_locale: str
    max_articles: int
    docs_dir: Path
    artifacts_dir: Path
    chunk_max_tokens: int
    chunk_overlap_tokens: int
    upload_concurrency: int
    log_level: str

    @property
    def api_key(self) -> str:
        return self.gemini_api_key if self.provider == "gemini" else self.openai_api_key

    @property
    def api_key_var(self) -> str:
        return "GEMINI_API_KEY" if self.provider == "gemini" else "OPENAI_API_KEY"

    @classmethod
    def from_env(cls) -> "Settings":
        provider = (os.getenv("AI_PROVIDER") or "gemini").strip().lower()
        if provider not in ("gemini", "openai"):
            raise ValueError("AI_PROVIDER must be 'gemini' or 'openai'")
        # The brief's docker example uses API_KEY; accept it as an alias for the active provider.
        alias = os.getenv("API_KEY", "")
        gemini_key = os.getenv("GEMINI_API_KEY") or (alias if provider == "gemini" else "")
        openai_key = os.getenv("OPENAI_API_KEY") or (alias if provider == "openai" else "")
        max_tokens = _int("CHUNK_MAX_TOKENS", 800 if provider == "openai" else 400)
        overlap = _int("CHUNK_OVERLAP_TOKENS", 400 if provider == "openai" else 80)
        if overlap > max_tokens // 2:
            raise ValueError("CHUNK_OVERLAP_TOKENS must be <= half of CHUNK_MAX_TOKENS")
        return cls(
            provider=provider,
            gemini_api_key=gemini_key.strip(),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash,gemini-3.7-flash,gemini-3.5-flash,gemini-3-flash-preview").strip(),
            openai_api_key=openai_key.strip(),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
            vector_store_id=os.getenv("VECTOR_STORE_ID", "").strip(),
            vector_store_name=os.getenv("VECTOR_STORE_NAME", "optibot-kb").strip(),
            zendesk_base_url=os.getenv("ZENDESK_BASE_URL", "https://support.optisigns.com").rstrip("/"),
            zendesk_locale=os.getenv("ZENDESK_LOCALE", "en-us"),
            max_articles=_int("MAX_ARTICLES", 0),
            docs_dir=Path(os.getenv("DOCS_DIR", "docs")),
            artifacts_dir=Path(os.getenv("ARTIFACTS_DIR", "artifacts")),
            chunk_max_tokens=max_tokens,
            chunk_overlap_tokens=overlap,
            upload_concurrency=max(1, _int("UPLOAD_CONCURRENCY", 4)),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
