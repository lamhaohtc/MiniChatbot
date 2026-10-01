"""OpenAI vector store adapter.

The vector store is the single source of truth for sync state: every file
carries `attributes` (article_id, content_hash, slug, ...). A fresh container
rebuilds the manifest by listing the store, so no local state is needed.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from openai import OpenAI

from .markdown import MarkdownArticle

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RemoteFile:
    file_id: str
    article_id: int
    content_hash: str
    slug: str


class VectorStoreClient:
    def __init__(self, api_key: str, chunk_max_tokens: int, chunk_overlap_tokens: int):
        self.client = OpenAI(api_key=api_key)
        self.chunking = {
            "type": "static",
            "static": {
                "max_chunk_size_tokens": chunk_max_tokens,
                "chunk_overlap_tokens": chunk_overlap_tokens,
            },
        }

    # -- store lifecycle ---------------------------------------------------
    def ensure_store(self, store_id: str, name: str) -> str:
        if store_id:
            self.client.vector_stores.retrieve(store_id)
            return store_id
        for vs in self.client.vector_stores.list(limit=100):
            if vs.name == name:
                log.info("reusing vector store %s (%s)", vs.id, name)
                return vs.id
        vs = self.client.vector_stores.create(name=name)
        log.info("created vector store %s (%s) -- set VECTOR_STORE_ID=%s", vs.id, name, vs.id)
        return vs.id

    # -- manifest ------------------------------------------------------------
    def list_remote(self, store_id: str) -> dict[int, RemoteFile]:
        out: dict[int, RemoteFile] = {}
        for f in self.client.vector_stores.files.list(vector_store_id=store_id, limit=100):
            attrs = f.attributes or {}
            if "article_id" not in attrs:
                continue  # not managed by this job
            out[int(attrs["article_id"])] = RemoteFile(
                file_id=f.id,
                article_id=int(attrs["article_id"]),
                content_hash=str(attrs.get("content_hash", "")),
                slug=str(attrs.get("slug", "")),
            )
        return out

    # -- mutations -----------------------------------------------------------
    def upload(self, store_id: str, art: MarkdownArticle) -> tuple[str, int]:
        """Upload one article; returns (file_id, chunk_count)."""
        buf = io.BytesIO(art.markdown.encode("utf-8"))
        buf.name = f"{art.slug}.md"
        file = self.client.files.create(file=buf, purpose="assistants")
        vsf = self.client.vector_stores.files.create_and_poll(
            vector_store_id=store_id,
            file_id=file.id,
            attributes={
                "article_id": art.id,
                "content_hash": art.content_hash,
                "slug": art.slug,
                "title": art.title[:512],
                "source_url": art.html_url[:512],
            },
            chunking_strategy=self.chunking,
        )
        if vsf.status != "completed":
            raise RuntimeError(f"vector store file {file.id} ended in status {vsf.status}: {vsf.last_error}")
        return file.id, self.count_chunks(store_id, file.id)

    def delete(self, store_id: str, file_id: str) -> None:
        # Remove from the store first, then delete the underlying file so
        # storage does not accumulate across daily runs.
        try:
            self.client.vector_stores.files.delete(file_id=file_id, vector_store_id=store_id)
        finally:
            try:
                self.client.files.delete(file_id)
            except Exception as exc:  # noqa: BLE001 - best effort cleanup
                log.warning("could not delete file %s: %s", file_id, exc)

    def count_chunks(self, store_id: str, file_id: str) -> int:
        """The API has no chunk counter; count the parsed chunks it exposes."""
        n = 0
        for _ in self.client.vector_stores.files.content(file_id=file_id, vector_store_id=store_id):
            n += 1
        return n
