"""Gemini File Search adapter (the Gemini equivalent of an OpenAI vector store).

Each document carries `custom_metadata` (article_id, content_hash, slug, ...), so the
store itself is the sync state: a fresh container rebuilds the manifest by listing
documents, and no local state is needed.
"""
from __future__ import annotations

import io
import logging
import time

from google.genai import Client, types

from .base import RemoteFile
from .chunking import chunks_for_tokens
from .markdown import MarkdownArticle

log = logging.getLogger(__name__)


def _meta(doc: types.Document) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in doc.custom_metadata or []:
        if m.string_value is not None:
            out[m.key] = m.string_value
        elif m.numeric_value is not None:
            out[m.key] = str(int(m.numeric_value))
    return out


class GeminiStoreClient:
    def __init__(self, api_key: str, chunk_max_tokens: int, chunk_overlap_tokens: int):
        self.client = Client(api_key=api_key)
        self.max_tokens = chunk_max_tokens
        self.overlap = chunk_overlap_tokens
        self.chunking = {
            "white_space_config": {
                "max_tokens_per_chunk": chunk_max_tokens,
                "max_overlap_tokens": chunk_overlap_tokens,
            }
        }

    # -- store lifecycle ---------------------------------------------------
    def ensure_store(self, store_id: str, name: str) -> str:
        if store_id:
            self.client.file_search_stores.get(name=store_id)
            return store_id
        for s in self.client.file_search_stores.list():
            if s.display_name == name:
                log.info("reusing file search store %s (%s)", s.name, name)
                return s.name
        s = self.client.file_search_stores.create(config={"display_name": name})
        log.info("created file search store %s (%s) -- set VECTOR_STORE_ID=%s", s.name, name, s.name)
        return s.name

    # -- manifest ------------------------------------------------------------
    def list_remote(self, store_id: str) -> dict[int, RemoteFile]:
        out: dict[int, RemoteFile] = {}
        # The API caps page_size at 20; the pager follows next-page tokens itself.
        for doc in self.client.file_search_stores.documents.list(parent=store_id, config={"page_size": 20}):
            meta = _meta(doc)
            if "article_id" not in meta:
                continue  # not managed by this job
            out[int(meta["article_id"])] = RemoteFile(
                file_id=doc.name,
                article_id=int(meta["article_id"]),
                content_hash=meta.get("content_hash", ""),
                slug=meta.get("slug", ""),
            )
        return out

    # -- mutations -----------------------------------------------------------
    def upload(self, store_id: str, art: MarkdownArticle) -> tuple[str, int]:
        """Upload one article; returns (document_name, chunk_count)."""
        buf = io.BytesIO(art.markdown.encode("utf-8"))
        op = self.client.file_search_stores.upload_to_file_search_store(
            file_search_store_name=store_id,
            file=buf,
            config={
                "mime_type": "text/markdown",
                "display_name": f"{art.slug}.md",
                "custom_metadata": [
                    {"key": "article_id", "string_value": str(art.id)},
                    {"key": "content_hash", "string_value": art.content_hash},
                    {"key": "slug", "string_value": art.slug},
                    {"key": "title", "string_value": art.title[:500]},
                    {"key": "source_url", "string_value": art.html_url[:500]},
                ],
                "chunking_config": self.chunking,
            },
        )
        deadline = time.time() + 300
        while not op.done:
            if time.time() > deadline:
                raise TimeoutError(f"indexing {art.slug} did not finish in 300 s")
            time.sleep(2)
            op = self.client.operations.get(op)
        if op.error:
            raise RuntimeError(f"indexing {art.slug} failed: {op.error}")
        doc_name = op.response.document_name if op.response else ""
        return doc_name, self.count_chunks(art.markdown)

    def delete(self, store_id: str, file_id: str) -> None:
        self.client.file_search_stores.documents.delete(name=file_id, config={"force": True})

    def count_chunks(self, text: str) -> int:
        """Gemini's white-space chunker counts whitespace-delimited tokens; the API
        reports no chunk count, so the same sliding window is replicated locally."""
        return chunks_for_tokens(len(text.split()), self.max_tokens, self.overlap)
