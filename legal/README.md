# OpenClaw Legal Module Index

OpenClaw Legal is a local-first legal workflow foundation, not a finished legal AI product. The current v0 spine proves deterministic local matter handling, source ingestion, extraction, search, report export, and review packet export without LLM, cloud, API, or network calls in the legal v0 spine.

## Workflow Spine

Matter workspace -> source registration -> TXT/MD/PDF text-layer extraction -> local search -> Markdown search report -> review packet export.

## Current Modules

- `legal/matter_workspace.py`: creates local matter containers with `manifest.json`, append-only `audit.jsonl`, required folders, and SHA-256 source registration.
- `legal/local_ingestion.py`: extracts UTF-8 text from registered `.txt`, `.md`, and text-layer `.pdf` sources into local `extracted/` artifacts.
- `legal/local_search.py`: performs deterministic case-insensitive literal search over extracted text artifacts.
- `legal/search_report.py`: exports Markdown search reports under each matter workspace `exports/` folder.
- `legal/review_packet.py`: exports buyer-legible review packet folders with manifest, audit, extracted artifacts, metadata, and selected Markdown reports.
- `legal/deployment_profile.py`: defines a portable local-first deployment profile schema and validation helpers. It is not an installer.
- `legal/cli.py`: provides machine-readable CLI commands for matter creation, source registration, extraction, search, reports, review packets, and default profiles.
- `scripts/demo_legal_matter_workflow.py`: runs the end-to-end local demo workflow with sample `.txt` and `.md` sources.

## Demo

```bash
python3 scripts/demo_legal_matter_workflow.py /tmp/openclaw_legal_demo_workflow
```

For CLI usage, see `legal/CLI_DEMO_WALKTHROUGH.md`.

## Tests

```bash
pytest -q tests/test_legal_cli.py tests/test_review_packet.py tests/test_pdf_ingestion.py tests/test_deployment_profile.py tests/test_legal_demo_workflow.py tests/test_search_report.py tests/test_local_search.py tests/test_local_ingestion.py tests/test_matter_workspace.py
```

## Safety Boundaries

- Local-first artifacts and processing.
- No LLM calls in the legal v0 spine.
- No cloud, API, or network calls in the legal v0 spine.
- No autonomous sending.
- No Cassandra, Chief, Guardian, Gmail, Calendar, Drive, dashboard, launcher, or runtime wiring yet.
- No legal advice.
- Source-grounded local artifacts only.

## Not Built Yet

- OCR or scanned-PDF recognition.
- DOCX parsing.
- Audio/video transcription integration.
- LLM summaries or legal analysis.
- Legal advice.
- Embeddings or vector database search.
- Dashboards or UI.
- Installer or deployment runtime activation.
- Gmail, Calendar, or Drive wiring.

## Notes

This package was built incrementally through small legal v0 commits. The current goal is a clean, productizable foundation that future law-office deployments can enable, disable, rename, or extend without coupling the legal module to a personal OpenClaw instance.
