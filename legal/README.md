# OpenClaw Legal Module Index

OpenClaw Legal is a local-first legal workflow foundation, not a finished legal AI product. The current v0 spine proves deterministic local matter handling, source ingestion, extraction, search, report export, review packet export, support diagnostics, and Alternative Methods metadata without LLM, cloud, API, or network calls in the legal v0 spine.

## Workflow Spine

Matter workspace -> source registration -> staging import -> TXT/MD/PDF text-layer extraction -> local image OCR prototype where local Tesseract is available -> local search -> Markdown search report -> review packet export -> sanitized support packet -> Alternative Methods metadata.

## Current Modules

- `legal/matter_workspace.py`: creates local matter containers with `manifest.json`, append-only `audit.jsonl`, required folders, and SHA-256 source registration.
- `legal/path_guard.py`: enforces matter/vault path boundaries so matter data stays outside the product repo and, when configured, inside approved vault roots.
- `legal/local_ingestion.py`: extracts UTF-8 text from registered `.txt`, `.md`, and text-layer `.pdf` sources into local `extracted/` artifacts. It also includes a local image OCR prototype for `.png`, `.jpg`, and `.jpeg` sources using an installed local Tesseract CLI when available.
- `legal/local_search.py`: performs deterministic case-insensitive literal search over extracted text artifacts.
- `legal/search_report.py`: exports Markdown search reports under each matter workspace `exports/` folder.
- `legal/review_packet.py`: exports buyer-legible review packet folders with manifest, audit, extracted artifacts, metadata, and selected Markdown reports.
- `legal/support_packet.py`: exports sanitized support diagnostics that exclude source files, extracted text, private paths, sensitive filenames, review packet contents, attorney notes, and raw audit logs.
- `legal/alternative_methods.py`: returns sanitized local-first next-action metadata for unsupported, failed, or no-text sources.
- `legal/local_capability_policy.py`: records local capability states for extraction and OCR-related handling without installing tools or escalating externally.
- `legal/deployment_profile.py`: defines a portable local-first deployment profile schema and validation helpers. It is not an installer.
- `legal/cli.py`: provides machine-readable CLI commands for matter creation, source registration, staging import, extraction, search, reports, review packets, sanitized support packets, Alternative Methods metadata, and default profiles.
- `scripts/demo_legal_matter_workflow.py`: runs the end-to-end local demo workflow with sample `.txt` and `.md` sources.

## Prototype / Spike Surfaces

- Local image OCR prototype: `.png`, `.jpg`, and `.jpeg` sources can use an installed local Tesseract CLI when available. If Tesseract is missing or OCR fails, the system records safe unsupported, failed, or no-text status and keeps support packets sanitized.
- Legal Console spike: `apps/legal-console-spike/` exists as a bounded desktop-console prototype. It is not a sellable product UI, not production software, and not wired to live Legal processing.

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
- No live bridge/run/reset/dummy-file wiring in the Legal Console spike.
- No legal advice.
- No automated privilege-decision engine.
- No attorney replacement.
- No cloud LLM matter processing.
- Source-grounded local artifacts only.

## Still Not Built / Roadmap Only

- Scanned-PDF OCR.
- Video/audio OCR or transcription.
- Cloud OCR.
- LLM OCR cleanup.
- Production OCR packaging.
- Any guarantee that OCR is installed, calibrated, or available on firm machines.
- DOCX parsing.
- LLM summaries or legal analysis.
- Legal advice.
- Embeddings or vector database search.
- A production desktop-console product, production installer, matter selection, processing queue, ETA, Connect workflow, update manager, or real-matter GUI workflow.
- Installer or deployment runtime activation.
- Gmail, Calendar, or Drive wiring.

## Notes

This package was built incrementally through small legal v0 commits. The current goal is a clean, productizable foundation that future law-office deployments can enable, disable, rename, or extend without coupling the legal module to a personal OpenClaw instance.
