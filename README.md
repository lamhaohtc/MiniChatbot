# kb-sync — OptiBot mini-clone

Scrapes the OptiSigns help center, normalises every article to Markdown, and keeps an
OpenAI vector store in sync **by uploading only what changed**. Runs once and exits.

```
Zendesk API ──> docs/<slug>.md ──> diff vs. vector-store attributes ──> upload delta ──> SUMMARY
```

## Setup

```bash
python -m venv .venv && .venv/Scripts/activate      # or source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.sample .env                                  # add OPENAI_API_KEY
```

## Run locally

```bash
python main.py --scrape-only    # 416 articles -> docs/, no key needed (~10 s)
python main.py --dry-run        # show added/updated/skipped/removed, upload nothing
python main.py                  # full sync; prints SUMMARY line and writes artifacts/last_run.json
python ask.py "How do I add a YouTube video?"   # ask the bot from the terminal
pytest                          # 12 unit tests (markdown cleaning + delta logic)
```

Docker (runs once, exits 0):

```bash
docker build -t kb-sync .
docker run --rm -e OPENAI_API_KEY=sk-... -e VECTOR_STORE_ID=vs_... kb-sync
```

First run logs `created vector store vs_... -- set VECTOR_STORE_ID=...`; set that env var so
later runs reuse it. Without it the job finds the store by `VECTOR_STORE_NAME`.

## How it works

- **Scrape** — Zendesk Help Center REST API (`/api/v2/help_center/en-us/articles.json`,
  paginated via `next_page`). Drafts and empty bodies are dropped.
- **Clean** — BeautifulSoup strips nav/ads/scripts, relative links and images are made
  absolute, `<iframe>` embeds become links, `<pre><code>` becomes fenced blocks with the
  language hint. Each file starts with front matter plus a plain `Article URL:` line so
  every chunk the model retrieves can be cited.
- **Chunking** — OpenAI static strategy, 800 tokens max / 400 overlap (the API defaults).
  Help articles are short step lists; 800 tokens keeps a whole procedure in one chunk and
  the 50 % overlap stops a numbered list being cut mid-step. Chunk counts are read back
  from the `/files/{id}/content` endpoint after indexing, not estimated.
- **Delta detection** — the vector store is the only state. Each uploaded file carries
  `attributes` (`article_id`, `content_hash`, `slug`, `source_url`). On every run the job
  lists the store, rebuilds the manifest from those attributes, and compares against a
  SHA-256 of the *rendered Markdown* (title + body). Zendesk's `updated_at` is ignored as
  a signal because it bumps on label/position edits that change no content.
  - `added`   — not in the store → upload
  - `updated` — hash differs → delete old file, upload new
  - `skipped` — same hash → nothing
  - `removed` — unpublished since last run → delete
  This makes a fresh, stateless container (Railway cron, GitHub Actions) idempotent.

## Daily job

Scheduled `0 3 * * *` UTC.

- **Railway** — `railway.json` sets `cronSchedule` and builds from the Dockerfile. Set
  `OPENAI_API_KEY` and `VECTOR_STORE_ID` as service variables.
- **GitHub Actions** fallback — `.github/workflows/daily-sync.yml` runs the same image on the
  same schedule and uploads `artifacts/last_run.json` as a run artefact.

**Job logs:** _<link to Railway deployment logs or the latest Actions run>_

Last run summary (example):

```
SUMMARY added=0 updated=3 skipped=413 removed=0 files_embedded=3 chunks_embedded=11 failed=0 (24.8s)
```

## Assistant

The brief predates OpenAI's sunset of the Assistants API (26 Aug 2026). The equivalent
today is the **Responses API + `file_search`** over the vector store, which is what the
Playground now does and what `ask.py` does programmatically. System prompt is the one from
the brief, verbatim (see `ask.py`).

**Screenshot:** _`screenshots/youtube-answer.png` — Playground answering "How do I add a
YouTube video?" with Article URL citations._

## Layout

```
main.py            entry point: scrape -> diff -> upload, exit 0
ask.py             terminal Q&A against the store (Responses API)
optibot/zendesk.py Help Center client (pagination, draft filter)
optibot/markdown.py HTML -> Markdown, slug, content hash, front matter
optibot/store.py   vector store adapter (attributes, chunking, chunk count)
optibot/sync.py    pure delta planner + applier
tests/             markdown + delta unit tests
docs/              generated Markdown (committed as the scrape artefact)
```
