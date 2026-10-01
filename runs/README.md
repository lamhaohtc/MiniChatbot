# Real run logs

Gemini File Search (the active provider):

| File | What it shows |
|---|---|
| `01-initial-load.log` | Empty store -> 413 added (3 came from a trial run). One article failed: it carried a 125 KB inline base64 image on one line, which the whitespace chunker rejects. |
| `02-data-uri-fix-added-one.log` | After the cleaner learned to drop data-URI images, the same article uploads: `added=1`, store at 416 files / 1012 chunks. |
| `03-no-changes.log` | Same corpus again -> `skipped=416`, nothing uploaded, 18 s. |
| `04-one-article-updated.log` | A document replaced remotely with a stale hash -> `updated=1`: old document deleted, new one indexed as 3 chunks. |
| `last_run.json` | Machine-readable summary written by every run. |

`openai/` holds the equivalent three runs from the OpenAI vector-store adapter, kept because the
adapter is still supported behind `AI_PROVIDER=openai`. Its first log predates the chunk-count fix.
