# Real run logs

| File | What it shows |
|---|---|
| `01-initial-load.log` | Empty store -> 416 articles uploaded. Note: this run predates the chunk-count fix, so its `chunks_embedded=416` is really a file count. Correct totals (416 files, 1443 chunks) are in the later runs. |
| `02-no-changes.log` | Same corpus again -> `skipped=416`, nothing uploaded, 15 s. |
| `03-one-article-updated.log` | One remote file marked stale -> `updated=1`, old file deleted, new one embedded as 4 chunks. |
| `last_run.json` | Machine-readable summary written by every run. |
