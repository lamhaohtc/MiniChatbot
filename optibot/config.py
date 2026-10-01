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
    openai_api_key: str
    vector_store_id: str
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

    @classmethod
    def from_env(cls) -> "Settings":
        # The brief's docker example uses API_KEY; accept it as an alias.
        key = os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY") or ""
        max_tokens = _int("CHUNK_MAX_TOKENS", 800)
        overlap = _int("CHUNK_OVERLAP_TOKENS", 400)
        if overlap > max_tokens // 2:
            raise ValueError("CHUNK_OVERLAP_TOKENS must be <= half of CHUNK_MAX_TOKENS")
        return cls(
            openai_api_key=key.strip(),
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
