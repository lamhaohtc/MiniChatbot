"""Provider-neutral types. Both store adapters (OpenAI, Gemini) implement KnowledgeStore."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .markdown import MarkdownArticle


@dataclass(frozen=True)
class RemoteFile:
    file_id: str        # provider handle: OpenAI file id, or Gemini document resource name
    article_id: int
    content_hash: str
    slug: str


class KnowledgeStore(Protocol):
    def ensure_store(self, store_id: str, name: str) -> str: ...
    def list_remote(self, store_id: str) -> dict[int, RemoteFile]: ...
    def upload(self, store_id: str, art: MarkdownArticle) -> tuple[str, int]: ...
    def delete(self, store_id: str, file_id: str) -> None: ...
    def count_chunks(self, text: str) -> int: ...
