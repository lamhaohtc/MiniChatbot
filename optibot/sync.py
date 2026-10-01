"""Delta computation (pure) and the sync orchestration that applies it."""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from .markdown import MarkdownArticle
from .store import RemoteFile, VectorStoreClient

log = logging.getLogger(__name__)


@dataclass
class SyncPlan:
    added: list[MarkdownArticle] = field(default_factory=list)
    updated: list[tuple[MarkdownArticle, RemoteFile]] = field(default_factory=list)
    skipped: list[MarkdownArticle] = field(default_factory=list)
    removed: list[RemoteFile] = field(default_factory=list)


def plan_sync(local: list[MarkdownArticle], remote: dict[int, RemoteFile]) -> SyncPlan:
    """Decide what to do purely from content hashes.

    added   : article exists locally, not in the store
    updated : in both, but content hash differs
    skipped : in both, same hash -> nothing to upload
    removed : in the store but no longer published
    """
    plan = SyncPlan()
    seen: set[int] = set()
    for art in local:
        seen.add(art.id)
        rf = remote.get(art.id)
        if rf is None:
            plan.added.append(art)
        elif rf.content_hash != art.content_hash:
            plan.updated.append((art, rf))
        else:
            plan.skipped.append(art)
    plan.removed = [rf for aid, rf in remote.items() if aid not in seen]
    return plan


@dataclass
class SyncResult:
    added: int
    updated: int
    skipped: int
    removed: int
    files_embedded: int
    chunks_embedded: int
    failed: int
    store_files: int      # files in the store after this run
    store_chunks: int     # chunks in the store after this run (computed)
    duration_s: float
    vector_store_id: str

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def write_docs(articles: list[MarkdownArticle], docs_dir: Path) -> None:
    docs_dir.mkdir(parents=True, exist_ok=True)
    for art in articles:
        # newline="\n" keeps output byte-identical across Windows and Linux runs
        (docs_dir / f"{art.slug}.md").write_text(art.markdown, encoding="utf-8", newline="\n")
    manifest = {str(a.id): {"slug": a.slug, "hash": a.content_hash, "url": a.html_url} for a in articles}
    (docs_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info("wrote %d markdown files to %s", len(articles), docs_dir)


def apply_plan(store: VectorStoreClient, store_id: str, plan: SyncPlan, concurrency: int) -> SyncResult:
    t0 = time.time()
    files = chunks = failed = 0

    # Deletions first: removed articles, and the stale copy of each updated one.
    for rf in plan.removed:
        store.delete(store_id, rf.file_id)
        log.info("removed  %s (article %s)", rf.slug, rf.article_id)
    for _art, rf in plan.updated:
        store.delete(store_id, rf.file_id)

    to_upload = [("added", a) for a in plan.added] + [("updated", a) for a, _ in plan.updated]
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = {pool.submit(store.upload, store_id, a): (kind, a) for kind, a in to_upload}
        for fut in as_completed(futs):
            kind, art = futs[fut]
            try:
                file_id, n = fut.result()
            except Exception as exc:  # noqa: BLE001 - keep going, report at end
                failed += 1
                log.error("%-8s %s FAILED: %s", kind, art.slug, exc)
                continue
            files += 1
            chunks += n
            log.info("%-8s %s -> %s (%d chunks)", kind, art.slug, file_id, n)

    # Whole-store totals, so every daily log states the corpus size, not just the delta.
    in_store = plan.skipped + [a for a in plan.added] + [a for a, _ in plan.updated]
    store_chunks = sum(store.count_chunks(a.markdown) for a in in_store)

    return SyncResult(
        added=len(plan.added),
        updated=len(plan.updated),
        skipped=len(plan.skipped),
        removed=len(plan.removed),
        files_embedded=files,
        chunks_embedded=chunks,
        failed=failed,
        store_files=len(in_store) - failed,
        store_chunks=store_chunks,
        duration_s=round(time.time() - t0, 1),
        vector_store_id=store_id,
    )
