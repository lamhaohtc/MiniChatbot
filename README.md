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
python main.py --dry-run        # print added/updated/skipped/removed, upload nothing
python main.py                  # full sync; prints SUMMARY and writes artifacts/last_run.json
python ask.py "How do I add a YouTube video?"   # ask the bot from the terminal
pytest                          # 25 unit tests: markdown cleaning, chunk maths, delta logic
```

Docker (runs once, exits 0):

```bash
docker build -t kb-sync .
docker run --rm -e OPENAI_API_KEY=sk-... -e VECTOR_STORE_ID=vs_... kb-sync
```

The first run logs `created vector store vs_... -- set VECTOR_STORE_ID=...`. Set that
variable so later runs reuse it; without it the job finds the store by `VECTOR_STORE_NAME`.

## How it works

- **Scrape** — Zendesk Help Center REST API (`/api/v2/help_center/en-us/articles.json`,
  paginated via `next_page`). Drafts and empty bodies are dropped.
- **Clean** — BeautifulSoup strips nav/ads/scripts; relative links and images are made
  absolute; `<iframe>` embeds become links; `<pre><code>` becomes fenced blocks with the
  language hint. Each file starts with front matter plus a plain `Article URL:` line so
  every retrieved chunk can be cited.
- **Chunking** — OpenAI static strategy, 800 tokens max / 400 overlap (the API defaults).
  Help articles are short step lists; 800 tokens keeps a whole procedure in one chunk and
  the 50 % overlap stops a numbered list being cut mid-step. The API does not expose chunk
  boundaries (the `/files/{id}/content` endpoint returns the parsed text as one item), so
  chunk counts are computed by replicating the same sliding window with `tiktoken`
  (`optibot/chunking.py`). Current store: **416 files, 1 443 chunks**.
- **Delta detection** — the vector store is the only state. Each uploaded file carries
  `attributes` (`article_id`, `content_hash`, `slug`, `source_url`). Every run lists the
  store, rebuilds the manifest from those attributes, and compares against a SHA-256 of the
  *rendered Markdown* (title + body). Zendesk's `updated_at` is ignored as a signal because
  it bumps on label/position edits that change no content.
  - `added`   — not in the store → upload
  - `updated` — hash differs → delete old file, upload new
  - `skipped` — same hash → nothing
  - `removed` — unpublished since last run → delete
  A fresh, stateless container (Railway cron, GitHub Actions) is therefore idempotent.

## Daily job

Scheduled `0 3 * * *` UTC.

- **Railway** — `railway.json` sets `cronSchedule` and builds from the Dockerfile. Set
  `OPENAI_API_KEY` and `VECTOR_STORE_ID` as service variables.
- **GitHub Actions** fallback — `.github/workflows/daily-sync.yml` runs the same image on the
  same schedule and uploads `artifacts/last_run.json` as a run artefact.

**Job logs:** _<link to Railway deployment logs or the latest Actions run>_

Committed run artefacts in [`runs/`](runs/):

```
01-initial-load.log          SUMMARY added=416 updated=0 skipped=0   files_embedded=416 (832.9s)
02-no-changes.log            SUMMARY added=0   updated=0 skipped=416 store_files=416 store_chunks=1443 (14.8s)
03-one-article-updated.log   SUMMARY added=0   updated=1 skipped=415 files_embedded=1 chunks_embedded=4 (23.7s)
```

## Assistant

The brief predates OpenAI's sunset of the Assistants API (26 Aug 2026). The equivalent
today is the **Responses API + `file_search`** over the vector store, which is what the
Playground now does and what `ask.py` does programmatically. The system prompt is the one
from the brief, verbatim (see `ask.py`).

**Screenshot:** _`screenshots/youtube-answer.png` — Playground answering "How do I add a
YouTube video?" with Article URL citations._

## Layout

```
main.py             entry point: scrape -> diff -> upload, exit 0
ask.py              terminal Q&A against the store (Responses API)
optibot/zendesk.py  Help Center client (pagination, draft filter)
optibot/markdown.py HTML -> Markdown, slug, content hash, front matter
optibot/chunking.py local replica of the static chunker, for counts
optibot/store.py    vector store adapter (attributes, chunking, delete)
optibot/sync.py     pure delta planner + applier
tests/              25 unit tests
docs/               generated Markdown (committed as the scrape artefact)
runs/               logs from real runs
```
