"""Convert Zendesk article HTML into clean, citation-ready Markdown."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from markdownify import MarkdownConverter
from slugify import slugify

from .zendesk import RawArticle

# Elements that are never article content (nav, ads, scripts, tracking).
_NOISE_SELECTORS = [
    "script", "style", "noscript", "nav", "header", "footer", "aside", "form",
    "[role=navigation]", ".breadcrumbs", ".article-votes", ".article-share",
    ".article-subscribe", ".recent-articles", ".related-articles",
    "[class*=promo]", "[class*=banner]", "[class*=advert]", "[id*=advert]",
]


class _Converter(MarkdownConverter):
    """markdownify with fenced code blocks and language hints preserved."""

    def convert_pre(self, el, text, parent_tags=None):
        code = el.find("code")
        lang = ""
        if code is not None:
            for cls in code.get("class", []):
                if cls.startswith(("language-", "lang-")):
                    lang = cls.split("-", 1)[1]
                    break
        body = (code or el).get_text()
        return f"\n```{lang}\n{body.rstrip()}\n```\n"


@dataclass(frozen=True)
class MarkdownArticle:
    id: int
    slug: str
    title: str
    html_url: str
    content_hash: str
    markdown: str  # full file content incl. front matter


def _absolutize(soup: BeautifulSoup, base_url: str) -> None:
    for tag, attr in (("a", "href"), ("img", "src"), ("iframe", "src")):
        for el in soup.find_all(tag):
            val = el.get(attr)
            if val and not val.startswith(("http://", "https://", "mailto:", "#", "data:")):
                el[attr] = urljoin(base_url, val)


def _embeds_to_links(soup: BeautifulSoup) -> None:
    """Replace iframe/video embeds with a Markdown link so video how-tos survive."""
    for el in soup.find_all(["iframe", "video", "embed"]):
        src = el.get("src")
        if not src:
            source = el.find("source")
            src = source.get("src") if source else None
        if src:
            a = soup.new_tag("a", href=src)
            a.string = "Embedded video"
            el.replace_with(a)
        else:
            el.decompose()


def html_to_markdown(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for sel in _NOISE_SELECTORS:
        for el in soup.select(sel):
            el.decompose()
    _absolutize(soup, base_url)
    _embeds_to_links(soup)
    md = _Converter(heading_style="ATX", bullets="-", escape_underscores=False).convert_soup(soup)
    return _tidy(md)


def _tidy(md: str) -> str:
    md = md.replace("\r\n", "\n").replace("\r", "\n")  # Zendesk bodies carry CRLF
    md = md.replace("\xa0", " ").replace("​", "")
    md = "\n".join(line.rstrip() for line in md.splitlines())
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


def content_hash(title: str, body_md: str) -> str:
    """Hash of what the bot actually reads. Metadata like updated_at is excluded
    on purpose: Zendesk bumps updated_at for label/position edits that change nothing."""
    return hashlib.sha256(f"{title}\n{body_md}".encode("utf-8")).hexdigest()[:32]


def make_slug(title: str, article_id: int) -> str:
    s = slugify(title, max_length=80) or "article"
    return f"{s}-{article_id}"


def render(article: RawArticle, base_url: str) -> MarkdownArticle:
    body_md = html_to_markdown(article.body_html, base_url)
    h = content_hash(article.title, body_md)
    front = (
        "---\n"
        f"title: {article.title!r}\n"
        f"article_id: {article.id}\n"
        f"section: {article.section!r}\n"
        f"source_url: {article.html_url}\n"
        f"updated_at: {article.updated_at}\n"
        f"content_hash: {h}\n"
        "---\n\n"
        # Plain-text line that survives chunking so the bot can cite it.
        f"Article URL: {article.html_url}\n\n"
        f"# {article.title}\n\n"
    )
    return MarkdownArticle(
        id=article.id,
        slug=make_slug(article.title, article.id),
        title=article.title,
        html_url=article.html_url,
        content_hash=h,
        markdown=front + body_md,
    )
