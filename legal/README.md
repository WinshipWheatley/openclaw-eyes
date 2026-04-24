# OpenClaw Legal Module Index

OpenClaw Legal is a local-first legal workflow foundation, not a finished legal AI product. The current v0 spine proves deterministic local matter handling, source ingestion, search, and report export without LLM, cloud, API, or network calls.

## Workflow Spine

Matter workspace -> source registration -> local ingestion -> local search -> Markdown search report export.

## Current Modules

- `legal/matter_workspace.py`: creates local matter containers with `manifest.json`, append-only `audit.jsonl`, required folders, and SHA-256 source registration.
- `legal/local_ingestion.py`: extracts UTF-8 text from registered `.txt` and `.md` sources into local `extracted/` artifacts.
- `legal/local_search.py`: performs deterministic case-insensitive literal search over extracted text artifacts.
- `legal/search_report.py`: exports Markdown search reports under each matter workspace `exports/` folder.
- `legal/deployment_profile.py`: defines a portable local-first deployment profile schema and validation helpers. It is not an installer.
- `scripts/demo_legal_matter_workflow.py`: runs the end-to-end local demo workflow with sample `.txt` and `.md` sources.

## Demo

```bash
python3 scripts/demo_legal_matter_workflow.py /tmp/openclaw_legal_demo_workflow
```

## Tests

```bash
pytest -q tests/test_deployment_profile.py tests/test_legal_demo_workflow.py tests/test_search_report.py tests/test_local_search.py tests/test_local_ingestion.py tests/test_matter_workspace.py
```

## Safety Boundaries

- No LLM calls.
- No cloud, API, or network calls.
- No autonomous sending.
- No Cassandra, Chief, Guardian, Gmail, Calendar, Drive, dashboard, or launcher wiring yet.
- No legal advice.
- Source-grounded local artifacts only.

## Not Built Yet

- PDF, OCR, or DOCX parsing.
- Audio/video transcription integration.
- Embeddings or vector search.
- LLM summaries.
- Legal advice.
- Dashboards.
- Installer or deployment runtime wiring.
- Gmail, Calendar, or Drive wiring.

## Notes

This package was built incrementally through small legal v0 commits. The current goal is a clean, productizable foundation that future law-office deployments can enable, disable, rename, or extend without coupling the legal module to a personal OpenClaw instance.
