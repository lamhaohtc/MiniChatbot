"""Tiny local chat UI for OptiBot (stdlib only). Same grounding as ask.py.

    python serve.py            # then open http://127.0.0.1:8765
"""
from __future__ import annotations

import html
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

from ask import ask_gemini, ask_openai
from optibot.config import Settings

PAGE = """<!doctype html><meta charset="utf-8"><title>OptiBot mini-clone</title>
<style>
 body{font:15px/1.5 system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;color:#1f2937}
 h1{font-size:20px;margin:0 0 4px} .sub{color:#6b7280;margin:0 0 20px;font-size:13px}
 form{display:flex;gap:8px} input{flex:1;padding:10px;border:1px solid #d1d5db;border-radius:8px;font-size:15px}
 button{padding:10px 16px;border:0;border-radius:8px;background:#14b8a6;color:#fff;font-weight:600}
 .q{margin-top:24px;color:#6b7280} .a{background:#f3f4f6;border-radius:12px;padding:6px 16px;margin-top:8px}
 .a p{margin:8px 0} .a ul{margin:8px 0;padding-left:22px} .a a{color:#0f766e;word-break:break-all}
 .src{margin-top:12px;font-size:13px} .src a{display:block;color:#0f766e}
</style>
<h1>OptiBot mini-clone</h1>
<p class="sub">Answers only from the uploaded help-center docs · provider: %(provider)s · model: %(model)s</p>
<form method="post"><input name="q" value="%(q)s" placeholder="Ask a question, e.g. How do I add a YouTube video?" autofocus><button>Ask</button></form>
%(body)s"""


_BOLD = re.compile(r"\*\*(.+?)\*\*")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_BARE_URL = re.compile(r"(?<![\"(>])(https?://[^\s<)]+)")


def md_to_html(text: str) -> str:
    """Just enough Markdown for chat answers: paragraphs, bullets, bold, links."""
    def inline(s: str) -> str:
        s = html.escape(s)
        s = _LINK.sub(r'<a href="\2" target="_blank">\1</a>', s)
        s = _BARE_URL.sub(r'<a href="\1" target="_blank">\1</a>', s)
        return _BOLD.sub(r"<b>\1</b>", s)

    out: list[str] = []
    in_list = False
    for line in text.strip().splitlines():
        stripped = line.strip()
        if stripped[:2] in ("* ", "- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(stripped[2:])}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if stripped:
            out.append(f"<p>{inline(stripped)}</p>")
    if in_list:
        out.append("</ul>")
    return "".join(out)


class Handler(BaseHTTPRequestHandler):
    cfg = Settings.from_env()

    def _render(self, q: str = "", body: str = "") -> None:
        out = PAGE % {"provider": self.cfg.provider, "model": (self.cfg.gemini_model.split(",")[0] if self.cfg.provider == "gemini" else self.cfg.openai_model), "q": html.escape(q), "body": body}
        data = out.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        self._render()

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        q = parse_qs(self.rfile.read(length).decode("utf-8")).get("q", [""])[0].strip()
        if not q:
            return self._render()
        answer, cited = (ask_gemini if self.cfg.provider == "gemini" else ask_openai)(self.cfg, q)
        srcs = "".join(f'<a href="{html.escape(u)}" target="_blank">Article URL: {html.escape(u)}</a>' for u in cited[:3])
        body = f'<div class="q">You: {html.escape(q)}</div><div class="a">{md_to_html(answer)}</div>'
        body += f'<div class="src"><b>Sources retrieved</b>{srcs}</div>' if srcs else ""
        self._render(q, body)

    def log_message(self, fmt: str, *args) -> None:  # quieter console
        sys.stdout.write("%s %s\n" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    if not Handler.cfg.api_key or not Handler.cfg.vector_store_id:
        print(json.dumps({"error": f"set {Handler.cfg.api_key_var} and VECTOR_STORE_ID first"}))
        sys.exit(2)
    print("OptiBot UI at http://127.0.0.1:8765  (Ctrl+C to stop)")
    HTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
