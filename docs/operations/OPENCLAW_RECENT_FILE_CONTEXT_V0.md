# OpenClaw Recent File Context v0

Status: implemented backend substrate.

Recent File Context resolves phrases like "that new file" against File Event Queue metadata. It is a metadata resolver, not file ingestion or execution.

## Source

- Reads `file_event_observations`, `file_event_queue`, `file_event_classification_hints`, and optional Markdown Atlas links.
- Writes only `recent_file_*` tables in `.openclaw/business_ops/ledger.sqlite`.
- Exports:
  - `generated/read_models/recent_file_context.json`
  - `generated/read_models/recent_file_context_OPERATOR.md`

## Tables

- `recent_file_context_runs`
- `recent_file_candidates`
- `recent_file_aliases`
- `recent_file_resolution_queries`
- `recent_file_context_links`
- `recent_file_rejections`

## Commands

Build candidates:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_recent_file_context.py --format operator
```

Query reports:

```bash
python3 scripts/query_recent_file_context.py --report summary --format operator
python3 scripts/query_recent_file_context.py --report recent --format operator
python3 scripts/query_recent_file_context.py --report unresolved --format operator
```

Resolve a phrase:

```bash
python3 scripts/query_recent_file_context.py --resolve "that new file" --format operator
python3 scripts/query_recent_file_context.py --resolve "the new Logic file" --format operator
```

Export read-model:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/export_recent_file_context_read_model.py --format operator
```

## Boundary

- No raw private file body reads.
- No file moves, deletes, renames, or edits.
- No runtime, agent, model, network, or tool authority.
- Logic/audio/video/report-package candidates are metadata-only unless later explicitly approved through a separate lane.
- Ambiguous file references require operator review.
