"""Scrape -> Markdown -> diff against the vector store -> upload only the delta.

Runs once and exits 0 on success. Designed to be scheduled daily.
    python main.py                # full sync (needs OPENAI_API_KEY)
    python main.py --scrape-only  # just write docs/, no API key needed
    python main.py --dry-run      # show the delta, upload nothing
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from optibot.config import Settings
from optibot.markdown import render
from optibot.store import VectorStoreClient
from optibot.sync import apply_plan, plan_sync, write_docs
from optibot.zendesk import ZendeskClient


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scrape-only", action="store_true", help="scrape and write Markdown; skip the vector store")
    ap.add_argument("--dry-run", action="store_true", help="compute the delta but upload nothing")
    args = ap.parse_args(argv)

    cfg = Settings.from_env()
    logging.basicConfig(level=cfg.log_level, format="%(asctime)s %(levelname)-5s %(message)s", stream=sys.stdout)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per request is noise
    log = logging.getLogger("main")
    t0 = time.time()

    # 1. Scrape + normalise
    zd = ZendeskClient(cfg.zendesk_base_url, cfg.zendesk_locale)
    raw = zd.articles(limit=cfg.max_articles)
    articles = [render(a, cfg.zendesk_base_url) for a in raw]
    write_docs(articles, cfg.docs_dir)
    if args.scrape_only:
        log.info("SUMMARY scraped=%d (scrape-only) in %.1fs", len(articles), time.time() - t0)
        return 0

    if not cfg.openai_api_key:
        log.error("OPENAI_API_KEY is not set (use --scrape-only to run without it)")
        return 2

    # 2. Diff against the store (state lives in file attributes, not on disk)
    store = VectorStoreClient(cfg.openai_api_key, cfg.chunk_max_tokens, cfg.chunk_overlap_tokens)
    store_id = store.ensure_store(cfg.vector_store_id, cfg.vector_store_name)
    remote = store.list_remote(store_id)
    plan = plan_sync(articles, remote)
    log.info("plan: added=%d updated=%d skipped=%d removed=%d",
             len(plan.added), len(plan.updated), len(plan.skipped), len(plan.removed))
    if args.dry_run:
        log.info("SUMMARY dry-run, nothing uploaded")
        return 0

    # 3. Apply the delta
    result = apply_plan(store, store_id, plan, cfg.upload_concurrency)
    cfg.artifacts_dir.mkdir(parents=True, exist_ok=True)
    summary = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **result.as_dict()}
    (cfg.artifacts_dir / "last_run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info("SUMMARY added=%d updated=%d skipped=%d removed=%d files_embedded=%d chunks_embedded=%d failed=%d (%.1fs)",
             result.added, result.updated, result.skipped, result.removed,
             result.files_embedded, result.chunks_embedded, result.failed, time.time() - t0)
    return 1 if result.failed else 0


if __name__ == "__main__":
    sys.exit(main())
