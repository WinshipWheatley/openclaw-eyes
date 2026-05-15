# OpenClaw File Event Queue v0

## Purpose

File Event Queue v0 is a poll/snapshot layer for noticing file changes in explicit OpenClaw roots. It records metadata changes into the Business Ops ledger so later lanes can classify, ingest, or route files without relying on a manual rescan button.

It is not a daemon, not deep ingestion, not an action executor, and not a broad drive scanner.

## Allowed Roots

Default allowed roots:

- `/home/openclaw`
- `/mnt/e/openclaw`

Rejected broad roots include `/`, `/home`, `/mnt`, `/mnt/c`, `/mnt/e`, and empty paths.

## Ledger Tables

The queue uses a separated `file_event_*` namespace in `.openclaw/business_ops/ledger.sqlite`:

- `file_event_runs`
- `file_event_snapshots`
- `file_event_observations`
- `file_event_queue`
- `file_event_path_aliases`
- `file_event_classification_hints`

## Safety Posture

- Raw file bodies are not stored.
- No-go and sensitive paths are metadata-only and not hashed.
- Safe hashes are limited to small allowlisted file kinds under the max hash threshold.
- Audio, video, Logic projects, caches, logs, private boundaries, and no-go paths are metadata-only.
- Move detection is advisory only and uses matching safe hash plus size.
- No files are moved, deleted, renamed, reorganized, or executed.
- Runtime, agent, tool, Docker/Ollama, network, file-move, and file-delete authority remain false.

## Commands

Build a snapshot:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_file_event_snapshot.py --root /home/openclaw --format operator
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_file_event_snapshot.py --root /mnt/e/openclaw --format operator
```

Query reports:

```bash
python3 scripts/query_file_event_queue.py --report summary --format operator
python3 scripts/query_file_event_queue.py --report recent --format operator
python3 scripts/query_file_event_queue.py --report queued --format operator
python3 scripts/query_file_event_queue.py --report possible-moves --format operator
python3 scripts/query_file_event_queue.py --report no-go --format operator
python3 scripts/query_file_event_queue.py --report by-kind --kind markdown_doc --format operator
python3 scripts/query_file_event_queue.py --report by-kind --kind logic_project --format operator
```

## File Kind Hints

Initial hints include:

- `markdown_doc`
- `logic_project`
- `audio_file`
- `video_file`
- `image_file`
- `source_code`
- `generated_read_model`
- `report_bridge_package`
- `unknown`

Hints are routing metadata, not truth promotion.

## Next Safe Extension

The next lane can connect queued metadata events to Corpus Atlas or Markdown Knowledge Atlas rebuild requests through Operator Action Path approval. It should still require explicit approval before any backend work executes.

