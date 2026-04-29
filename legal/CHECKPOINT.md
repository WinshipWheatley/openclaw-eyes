# OpenClaw Legal v0 Checkpoint

## Historical status

This file is a historical early Legal v0 checkpoint. It has been superseded by later Legal safety/product slices and should not be treated as current repo truth.

Use the Legal chat handoff and git history for current-state orientation before planning or implementation. The proof below records what had passed at this checkpoint, not the latest proof across the current repository.

## Current State

OpenClaw Legal v0 is a local-first legal workflow foundation. It is not a finished legal AI product.

Current workflow spine:

Matter workspace -> source registration -> TXT/MD/PDF text-layer extract-all -> local search -> Markdown report -> review packet export -> CLI -> deployment profile -> demo fixture -> docs.

## Historical Proof

The "Latest Proof" for this checkpoint is historical. It is preserved here because it documents the early v0 baseline.

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

## Still Not Built At This Historical Checkpoint

This list means not built when this checkpoint was written unless a later Legal handoff or commit history says otherwise.

- OCR or scanned-PDF recognition.
- LLM summaries or legal analysis.
- Embeddings or vector database search.
- Dashboards or UI.
- Gmail, Calendar, or Drive wiring.
- Installer or runtime deployment activation.

## Historical Recommended Next Steps

These were the recommended next steps at this checkpoint. They are preserved for history, not as current marching orders.

1. Run the CLI walkthrough once from `legal/CLI_DEMO_WALKTHROUGH.md` using `/tmp`.
2. Create a buyer-facing sample review packet.
3. Consider `.eml` email ingestion v0 or batch source-add next.
