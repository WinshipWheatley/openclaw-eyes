# OpenClaw Legal v0 Checkpoint

## Current State

OpenClaw Legal v0 is a local-first legal workflow foundation. It is not a finished legal AI product.

Current workflow spine:

Matter workspace -> source registration -> TXT/MD/PDF text-layer extract-all -> local search -> Markdown report -> review packet export -> CLI -> deployment profile -> demo fixture -> docs.

## Latest Proof

Command:

```bash
pytest -q tests/test_legal_cli.py tests/test_review_packet.py tests/test_pdf_ingestion.py tests/test_deployment_profile.py tests/test_legal_demo_workflow.py tests/test_search_report.py tests/test_local_search.py tests/test_local_ingestion.py tests/test_matter_workspace.py
```

Result:

```text
80 passed in 0.69s
```

## Important Commits

- `af4fc31 feat(legal): add extract-all cli`
- `42fbe12 docs(legal): refresh cli demo docs`

## Safety Boundaries

- No LLM calls.
- No cloud, API, or network calls.
- No legal advice.
- No autonomous sending.
- No runtime or agent wiring.

## Still Not Built

- OCR or scanned-PDF recognition.
- LLM summaries or legal analysis.
- Embeddings or vector database search.
- Dashboards or UI.
- Gmail, Calendar, or Drive wiring.
- Installer or runtime deployment activation.

## Recommended Next Steps

1. Run the CLI walkthrough once from `legal/CLI_DEMO_WALKTHROUGH.md` using `/tmp`.
2. Create a buyer-facing sample review packet.
3. Consider `.eml` email ingestion v0 or batch source-add next.
