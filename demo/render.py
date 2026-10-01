"""Render the Part 1 walkthrough video from REAL command output and page captures.

Every terminal step below runs the actual command now and shows its real stdout.
Browser steps use headless-Edge captures taken from the running app and GitHub.
    .venv/Scripts/python demo/render.py   -> artifacts/demo.mp4
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
FRAMES = ROOT / "artifacts" / "frames"
OUT = ROOT / "artifacts" / "demo.mp4"
W, H = 1920, 1080
BG, PANEL, INK, DIM, ACCENT, CMD = "#0b1220", "#111a2e", "#e5e7eb", "#94a3b8", "#2dd4bf", "#fde68a"
MONO = ImageFont.truetype("C:/Windows/Fonts/CascadiaMono.ttf", 26)
MONO_S = ImageFont.truetype("C:/Windows/Fonts/CascadiaMono.ttf", 22)
UI = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 30)
UI_B = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 44)
UI_H = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 64)

frames: list[tuple[Path, float]] = []
_n = 0


def save(img: Image.Image, seconds: float) -> None:
    global _n
    _n += 1
    p = FRAMES / f"f{_n:04d}.png"
    img.save(p)
    frames.append((p, seconds))


def run(cmd: list[str], cwd: Path = ROOT) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout + ("\n" + r.stderr if r.stderr.strip() else "")).strip("\n")
    return out + f"\n[exit code {r.returncode}]"


def card(title: str, lines: list[str], seconds: float, big: bool = False) -> None:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 18, H], fill=ACCENT)
    y = 300 if big else 120
    d.text((120, y), title, font=UI_H if big else UI_B, fill=INK)
    y += 110 if big else 80
    for ln in lines:
        for part in textwrap.wrap(ln, 95) or [""]:
            d.text((120, y), part, font=UI, fill=DIM)
            y += 46
        y += 10
    save(img, seconds)


def terminal(step: str, caption: str, cmd_shown: str, output: str, hold: float, reveal_lines: int = 6) -> None:
    lines: list[str] = []
    for raw in output.splitlines():
        lines.extend(textwrap.wrap(raw, 122, replace_whitespace=False, drop_whitespace=False) or [""])
    lines = lines[:30]

    def draw(n: int) -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W, 96], fill=PANEL)
        d.text((40, 22), step, font=UI_B, fill=INK)
        d.text((40, 110), caption, font=UI, fill=DIM)
        d.rectangle([40, 170, W - 40, H - 40], fill=PANEL, outline="#1f2a44")
        d.text((64, 190), "PS> " + cmd_shown, font=MONO, fill=CMD)
        y = 236
        for ln in lines[:n]:
            d.text((64, y), ln, font=MONO, fill=INK)
            y += 30
        return img

    save(draw(0), 1.2)
    shown = 0
    while shown < len(lines):
        shown = min(len(lines), shown + reveal_lines)
        save(draw(shown), 0.5)
    save(draw(len(lines)), hold)


def page(step: str, caption: str, png: Path, seconds: float) -> None:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 96], fill=PANEL)
    d.text((40, 22), step, font=UI_B, fill=INK)
    d.text((40, 110), caption, font=UI, fill=DIM)
    shot = Image.open(png).convert("RGB")
    box_w, box_h = W - 80, H - 200
    shot.thumbnail((box_w, box_h))
    img.paste(shot, (40 + (box_w - shot.width) // 2, 170))
    save(img, seconds)


def main() -> int:
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True)

    card("kb-sync — OptiBot mini-clone", [
        "Scrape the OptiSigns help center → clean Markdown → diff against a Gemini File Search store → upload only the delta.",
        "One command, runs once, exits 0. Scheduled daily on GitHub Actions.",
        "github.com/lamhaohtc/MiniChatbot",
    ], 7, big=True)

    terminal("1 · Scrape and clean", "Zendesk Help Center API with pagination; HTML → Markdown with nav stripped, absolute links, fenced code, an Article URL line per file.",
             "python main.py --scrape-only", run([PY, "main.py", "--scrape-only"]), 7)
    doc = (ROOT / "docs" / "how-to-use-youtube-with-optisigns-360051014713.md").read_text(encoding="utf-8").splitlines()[:26]
    terminal("1 · Scrape and clean", "One of the 416 generated files: front matter, the citation line, headings and links preserved.",
             "Get-Content docs/how-to-use-youtube-with-optisigns-360051014713.md -TotalCount 26", "\n".join(doc), 12, reveal_lines=9)

    terminal("2 · Tests", "28 unit tests: Markdown cleaning, chunk maths, delta planning, orchestration with a fake store.",
             "python -m pytest -q --disable-warnings", run([PY, "-m", "pytest", "-q", "--disable-warnings"]), 6)

    card("3 · Sync state lives in the store, not on disk", [
        "Each uploaded document carries custom_metadata: article_id, content_hash, slug, source_url.",
        "A fresh container lists the store, rebuilds the manifest, and compares content hashes of the rendered Markdown.",
        "added = new · updated = hash differs (delete + re-upload) · skipped = same · removed = unpublished.",
        "Chunking: Gemini white-space strategy, 400 tokens / 80 overlap, counted locally because the API exposes no chunk count.",
    ], 14)
    src = (ROOT / "optibot" / "store_gemini.py").read_text(encoding="utf-8").splitlines()
    snippet = [l for l in src if any(k in l for k in ("custom_metadata", "content_hash", "article_id", "def list_remote", "def upload", "def delete"))][:14]
    terminal("3 · Sync state lives in the store", "optibot/store_gemini.py — the metadata written on upload and read back on every run.",
             "Select-String optibot/store_gemini.py -Pattern 'custom_metadata|content_hash|article_id'", "\n".join(l.strip() for l in snippet), 10, reveal_lines=7)

    terminal("4 · Run the daily job now", "Re-scrape all 416 articles, diff against the store, upload only the delta. The SUMMARY line is what the daily log shows.",
             "python main.py", run([PY, "main.py"]), 12)

    terminal("5 · Real run logs committed in runs/", "Initial load: 413 added, one failed on a 125 KB inline base64 image; the cleaner now drops those.",
             "Get-Content runs/01-initial-load.log -Tail 3", "\n".join((ROOT / "runs" / "01-initial-load.log").read_text(encoding="utf-8").splitlines()[-3:]), 9)
    terminal("5 · Real run logs committed in runs/", "A document replaced remotely with a stale hash → updated=1: old document deleted, new one indexed as 3 chunks.",
             "Get-Content runs/04-one-article-updated.log", (ROOT / "runs" / "04-one-article-updated.log").read_text(encoding="utf-8"), 10)

    terminal("6 · Docker: runs once and exits 0", "docker run --rm --env-file .env kb-sync",
             "docker run --rm --env-file .env kb-sync", run(["docker", "run", "--rm", "--env-file", ".env", "kb-sync"]), 10)

    page("7 · The assistant", "Verbatim system prompt from the brief + Gemini file_search over the store. Five steps, Article URL cited from chunk metadata.",
         ROOT / "screenshots" / "youtube-answer.png", 18)
    page("8 · Daily schedule on GitHub Actions", "0 3 * * * UTC. Latest cloud run: success, skipped=416, run-summary artefact attached.",
         ROOT / "artifacts" / "shot-actions.png", 12)

    card("Done", [
        "416 articles · 1 012 chunks · delta-only daily sync · grounded answers with cited Article URLs.",
        "Repo: github.com/lamhaohtc/MiniChatbot — README covers setup, local run, chunking and delta strategy, job logs, screenshot.",
    ], 8, big=True)

    lst = FRAMES / "list.txt"
    with lst.open("w", encoding="utf-8") as f:
        for p, s in frames:
            f.write(f"file '{p.name}'\nduration {s}\n")
        f.write(f"file '{frames[-1][0].name}'\n")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
           "-vf", "fps=10,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "20", str(OUT)]
    subprocess.run(cmd, check=True, cwd=FRAMES)
    total = sum(s for _, s in frames)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB, {len(frames)} frames, ~{total:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
