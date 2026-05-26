# Scoped Context Package Compiler Contract v0

ELIOPERATOR: Agents get scoped packages, not raw thread sludge.

## What This Enables

Each package carries current coordinates, relevant slice summaries, refs, known/missing/blocked items, backend choices, worker surface, adapter lists, authority boundaries, and exclusions.

## What This Does Not Do Yet

It does not dispatch agents, call models, run retrieval, ingest transcripts/files, reveal secrets, or execute workflows.

## Packages

- context_package_mac_codex_chat_surface: agent=CHIEF model=OPENAI_CODEX worker=MAC_CODEX_WORKER at build/mission_control/chat_surface
- context_package_pc_codex_chat_request_processor: agent=CHIEF model=OPENAI_CODEX worker=PC_CODEX_WORKER at build/openclaw/backend/chat_router
- context_package_gemini_agy_card_contract_audit: agent=HERMES model=GEMINI_AGY worker=GEMINI_AGY_ADVISORY_WORKER at build/mission_control/chat_surface
- context_package_niles_x32_routing: agent=NILES model=LOCAL_OLLAMA worker=LOCAL_OLLAMA_INTERPRETER at music/live_music/x32/routing
- context_package_cassandra_capital_hilton_invoice: agent=CASSANDRA model=OPENAI_GPT worker=PC_CODEX_WORKER at finance/capital_hilton/invoices
- context_package_guardian_approval_boundary: agent=GUARDIAN model=LOCAL_OLLAMA worker=MANUAL_OPERATOR at finance/capital_hilton/invoices
- context_package_visual_invoice_workflow: agent=CHIEF model=FUTURE_PROVIDER worker=MAC_CODEX_WORKER at finance/capital_hilton/invoices
- context_package_ambiguous_keep_going: agent=UNKNOWN_FAIL_CLOSED model=UNKNOWN_FAIL_CLOSED worker=UNKNOWN_FAIL_CLOSED at unknown

## Exclusions

- CHAT_TRANSCRIPT_BODY: RAW_TRANSCRIPT_EXCLUDED
- FILE_BODY: RAW_FILE_BODY_EXCLUDED
- SECRET_VALUE: SECRET_VALUE_EXCLUDED
- CLIENT_PRIVATE_SCOPE: CROSS_CLIENT_SCOPE_EXCLUDED
- AUTHORITY: PRIVACY_BOUNDARY_EXCLUDED
- AUTHORITY: PRIVACY_BOUNDARY_EXCLUDED
- AUTHORITY: PRIVACY_BOUNDARY_EXCLUDED
- CHAT_THREAD_SUMMARY: LOW_RELEVANCE_EXCLUDED
- LOW_RELEVANCE_CONTEXT: TOKEN_BUDGET_EXCLUDED

## Visual Artifact Needs

- visual_need_mac_chat_surface_review: needed=True truth_refs=2
- visual_need_capital_hilton_invoice_workflow: needed=True truth_refs=2
- visual_need_none_gemini_audit: needed=False truth_refs=1

## Boundary

No live context package dispatch, agent dispatch, model call, workflow run, live memory retrieval, raw transcript ingestion, raw file body ingestion, secret reveal, visual artifact spawn, external action, credential handling, raw-body ingestion, Mac sync/import, Swift change, or push was added.

Next safe move: Export package examples and keep them ready-not-dispatched until a future approved agent rail exists.
