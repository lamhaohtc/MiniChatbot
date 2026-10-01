# kb-sync — OptiBot mini-clone

Scrapes the OptiSigns help center, normalises every article to Markdown, and keeps a
Gemini File Search store in sync **by uploading only what changed**. Runs once and exits.
An OpenAI vector-store adapter is included behind a flag.

```
Zendesk API ──> docs/<slug>.md ──> diff vs. per-document metadata ──> upload delta ──> SUMMARY
```

## Setup

```bash
python -m venv .venv && .venv/Scripts/activate      # or source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.sample .env                                  # add GEMINI_API_KEY (aistudio.google.com -> Get API key)
```

## Run locally

```bash
python main.py --scrape-only    # 416 articles -> docs/, no key needed (~10 s)
python main.py --dry-run        # print added/updated/skipped/removed, upload nothing
python main.py                  # full sync; prints SUMMARY and writes artifacts/last_run.json
python ask.py "How do I add a YouTube video?"   # grounded answer + cited Article URLs
python serve.py                 # same thing in a browser at http://127.0.0.1:8765
pytest                          # 28 unit tests: markdown cleaning, chunk maths, delta logic
```

Docker (runs once, exits 0):

```bash
docker build -t kb-sync .
docker run --rm -e GEMINI_API_KEY=AIza... -e VECTOR_STORE_ID=fileSearchStores/... kb-sync
```

The first run logs `created file search store fileSearchStores/... -- set VECTOR_STORE_ID=...`.
Set that variable so later runs reuse it; without it the job finds the store by `VECTOR_STORE_NAME`.

## How it works

- **Scrape** — Zendesk Help Center REST API (`/api/v2/help_center/en-us/articles.json`,
  paginated via `next_page`). Drafts and empty bodies are dropped.
- **Clean** — BeautifulSoup strips nav/ads/scripts; relative links and images are made
  absolute; inline base64 images are dropped (one article carried a 125 KB one on a single
  line); `<iframe>` embeds become links; `<pre><code>` becomes fenced blocks with the
  language hint; CRLF and non-breaking spaces are normalised. Each file starts with front
  matter plus a plain `Article URL:` line so every retrieved chunk can be cited.
- **Chunking** — Gemini's white-space strategy, 400 tokens per chunk with 80 overlap.
  Help articles are short step lists; 400 whitespace tokens is roughly one procedure, and the
  20 % overlap keeps a numbered list from being cut mid-step. The API reports no chunk count,
  so the same sliding window is replicated locally (`optibot/chunking.py`) and logged.
  Current store: **416 files, 1 012 chunks**. (OpenAI adapter: static 800/400 BPE tokens.)
- **Delta detection** — the store is the only state. Each uploaded document carries
  `custom_metadata` (`article_id`, `content_hash`, `slug`, `source_url`). Every run lists the
  store, rebuilds the manifest from that metadata, and compares against a SHA-256 of the
  *rendered Markdown* (title + body). Zendesk's `updated_at` is ignored as a signal because
  it bumps on label/position edits that change no content.
  - `added`   — not in the store → upload
  - `updated` — hash differs → delete old document, upload new
  - `skipped` — same hash → nothing
  - `removed` — unpublished since last run → delete
  A fresh, stateless container (GitHub Actions, Railway) is therefore idempotent.

## Daily job

Scheduled `0 3 * * *` UTC on GitHub Actions (`.github/workflows/daily-sync.yml`): builds the
image, runs it with `GEMINI_API_KEY` and `VECTOR_STORE_ID` from repository secrets, and uploads
`artifacts/last_run.json` as a run artefact. `railway.json` carries the same schedule for Railway.

**Job logs:** [all runs of `daily-sync`](https://github.com/lamhaohtc/MiniChatbot/actions/workflows/daily-sync.yml)

Committed logs from real runs are in [`runs/`](runs/):

```
01-initial-load.log            SUMMARY added=413 ... files_embedded=412 chunks_embedded=989 failed=1
02-data-uri-fix-added-one.log  SUMMARY added=1   ... store_files=416 store_chunks=1012
03-no-changes.log              SUMMARY added=0 updated=0 skipped=416 ... (17.6s)
04-one-article-updated.log     SUMMARY added=0 updated=1 skipped=415 files_embedded=1 chunks_embedded=3
```

## Assistant

The assistant is the verbatim system prompt from the brief plus Gemini's `file_search` tool
over the store (`ask.py`, `serve.py`). Answers are grounded only in retrieved chunks, and the
cited `Article URL:` lines come from each chunk's `source_url` metadata. `GEMINI_MODEL` is a
comma-separated list; later entries are used when a model returns 503 (high demand) or 404.

Sample answer (`runs/ask-youtube.txt`) and screenshot (`screenshots/youtube-answer.png`):
"How do I add a YouTube video?" → five steps, cited
`https://support.optisigns.com/hc/en-us/articles/360051014713-How-to-Use-YouTube-with-OptiSigns`.

## Layout

```
main.py                 entry point: scrape -> diff -> upload, exit 0
ask.py / serve.py       grounded Q&A from the terminal / a local web page
optibot/zendesk.py      Help Center client (pagination, draft filter)
optibot/markdown.py     HTML -> Markdown, slug, content hash, front matter
optibot/chunking.py     local replica of the chunkers, for counts
optibot/base.py         RemoteFile + KnowledgeStore protocol
optibot/store_gemini.py Gemini File Search adapter (default)
optibot/store.py        OpenAI vector store adapter (AI_PROVIDER=openai)
optibot/sync.py         pure delta planner + applier
tests/                  28 unit tests
docs/                   generated Markdown (committed as the scrape artefact)
runs/                   logs from real runs
```
