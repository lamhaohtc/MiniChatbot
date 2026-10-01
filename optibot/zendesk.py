"""Read articles from a public Zendesk Help Center via its REST API."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterator

import httpx

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RawArticle:
    id: int
    title: str
    body_html: str
    html_url: str
    section: str
    updated_at: str
    edited_at: str


class ZendeskClient:
    def __init__(self, base_url: str, locale: str, timeout: float = 30.0):
        self.base_url = base_url
        self.locale = locale
        self._http = httpx.Client(timeout=timeout, headers={"User-Agent": "kb-sync/1.0"})

    def _paginate(self, url: str) -> Iterator[dict]:
        """Follow Zendesk `next_page` links, yielding one page JSON at a time."""
        while url:
            resp = self._http.get(url)
            resp.raise_for_status()
            page = resp.json()
            yield page
            url = page.get("next_page")

    def sections(self) -> dict[int, str]:
        url = f"{self.base_url}/api/v2/help_center/{self.locale}/sections.json?per_page=100"
        out: dict[int, str] = {}
        for page in self._paginate(url):
            for s in page.get("sections", []):
                out[s["id"]] = s.get("name", "")
        return out

    def articles(self, limit: int = 0) -> list[RawArticle]:
        """Return published, non-empty articles. `limit=0` means all."""
        sections = self.sections()
        url = f"{self.base_url}/api/v2/help_center/{self.locale}/articles.json?per_page=100"
        out: list[RawArticle] = []
        skipped = 0
        for page in self._paginate(url):
            for a in page.get("articles", []):
                body = a.get("body") or ""
                if a.get("draft") or len(body.strip()) < 80:
                    skipped += 1
                    continue
                out.append(
                    RawArticle(
                        id=int(a["id"]),
                        title=(a.get("title") or "").strip(),
                        body_html=body,
                        html_url=a.get("html_url") or "",
                        section=sections.get(a.get("section_id"), ""),
                        updated_at=a.get("updated_at") or "",
                        edited_at=a.get("edited_at") or "",
                    )
                )
                if limit and len(out) >= limit:
                    log.info("fetched %d articles (limit reached), skipped %d drafts/empty", len(out), skipped)
                    return out
        log.info("fetched %d articles, skipped %d drafts/empty", len(out), skipped)
        return out
