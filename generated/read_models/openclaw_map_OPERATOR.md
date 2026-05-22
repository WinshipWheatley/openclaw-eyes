# OpenClaw Stable Map Bundle

## What Mission Control Should Read

- Map generation: `map_fbda77b8af4e9c796c03`
- Bundle hash: `sha256:d54194ee82f05e41724f26bb3def93f048f4552e6ff40914cfdf6227445bdb39`
- Stable files: `openclaw_map_snapshot.json`, `openclaw_map_manifest.json`, `openclaw_map_OPERATOR.md`
- Raw generated read-models remain proof/detail, not the front-door app dependency.

## Current Sync Truth

- Raw canonical expected: `247`
- Raw observed: `218`
- Raw missing expected: `29`
- Raw hash mismatch: `4`
- Raw lifecycle: `actionable_sync_failure`
- Check Transmission source: `sync_health controls Check Transmission freshness; taxonomy must not override fresher proof`

## Threshold Map Included

- Capital Hilton route: `MOVE_TO_WORLD_ACTION` -> `Finance`
- System Awareness lane: `READY_FOR_SECURITY_AUDIT`
- Cue/autonomy remains future-gated and is not active authority.

## Agent Council / Dossier Summary

- Cards available: `12`
- Featured agents: `cassandra, chief, guardian, hermes, niles, struna`
- System-loop cards: `agentic_loop, cue_parser_brain_dump_parser, repo_b_planner_builder_orchestrator, package_compiler, model_router, tool_plugin_registry`
- Future-gated cards: `12`
- Cassandra, Chief, Guardian, Hermes, Niles, and Struna are available as read-only dossier cards.
- Agentic Loop, Cue Parser / Brain Dump Parser, Repo B Planner / Builder / Orchestrator, Package Compiler, Model Router, and Tool / Plugin Registry are available as system-loop cards.
- Cards are preview/readback only; live chat, agent activation, model launch, tool execution, credentials, browser/OAuth, Gmail/calendar/Coupa/Telegram, send/submit/approval, and raw private context remain blocked.
- Mission Control should render a selected dossier card, roster rail, permission chips, strengths, missing proof, operator questions, and package preview route without adding a new per-contract file dependency.

## Package Preview Receipt Summary

- Summary present: `true`
- Contract: `package_preview_receipt_contract` / `package_preview_receipt_contract_v0`
- Receipt types: `14`
- Preview states: `19`
- Example preview cards: `8`
- Mission Control can render package preview cards for Cassandra Capital Hilton, Chief Check Engine, Guardian Protected Evidence, Niles / Struna, Hermes, Codex, Gemini / Antigravity, and Agentic Loop Classification.
- Package preview remains display-only: dispatch, model calls, tool execution, agent activation, queue execution, account access, send/submit/approval, raw body inclusion, and canonical memory writes are blocked.

## Tool Adapter Receipt Summary

- Summary present: `true`
- Contract: `tool_adapter_receipt_contract` / `tool_adapter_receipt_contract_v0`
- Receipt types: `15`
- Receipt states: `20`
- Capability classes: `20`
- Adapter receipt cards: `12`
- Allowed read-only: `1`
- Preview/receipt-only: `3`
- Blocked or future-gated: `8`
- Mission Control can render adapter receipt cards for the stable map reader, package preview exporter, Codex verifier, Cassandra/Capital Hilton proof adapter, Guardian gate, Chief harness, browser/OAuth, Gmail/calendar, Coupa, Telegram, Repo B planner/builder, and memory candidate writer.
- Live tool execution, network/account/browser access, send/submit/approval, command execution, model calls, agent activation, and queue execution remain false.

## Capital Hilton Proof Metadata Summary

- Summary present: `true`
- Phase: `HELM_THRESHOLD_LANE`
- Target world: `Finance`
- Lane destiny: `MOVE_TO_WORLD_ACTION`
- Missing proof count: `10`
- Protected proof required: `true`
- Candidate facts are displayed as candidate/not machine-proven. Operator memory can clarify them, but it does not become proof by itself.
- Missing proof includes performance date, rate, subtotal, Coupa/PO/payment, Excel/workbook, invoice source card, AP route, Guardian gate, operator confirmation, and future invoice generation receipt metadata.
- Cassandra may review metadata and proof gaps; Guardian must gate protected proof; Finance World remains a preview-only target until proof and security are complete.
- Coupa, browser/OAuth/account access, credentials, Gmail/calendar/email account access, Excel raw body ingestion, raw finance bodies, invoice generation, send/submit/approval, model calls, agent activation, tool execution, queue execution, and runtime dispatch remain blocked.
- Next safe move: Capture operator answers as Memory Candidate Receipts and then build protected proof metadata references; do not access Coupa, Excel, Gmail, browser, or accounts.

### Capital Hilton Candidate Facts

- `completed_performance_dates`: `['2026-05-08', '2026-05-15 (operator said this was yesterday relative to May 16, 2026)']` -> `CANDIDATE_FACT_NOT_PROVEN`
- `service_performance_description`: `None` -> `MISSING_PROOF`
- `rate`: `$400 per gig` -> `CANDIDATE_FACT_NOT_PROVEN`
- `subtotal`: `$800 for the two completed governed service-date facts, before any older/upcoming gig review` -> `CANDIDATE_FACT_NOT_PROVEN`
- `customer_client_identity`: `Capital Hilton` -> `METADATA_CONTEXT_NOT_FINAL_INVOICE_PROOF`
- `invoice_recipient_or_ap_route`: `True` -> `CANDIDATE_FACT_NOT_PROVEN`
- `po_coupa_reference`: `must_confirm_po_and_credit_in_coupa_before_final_submission` -> `CANDIDATE_FACT_NOT_PROVEN`
- `excel_workbook_reference`: `workbook metadata/reference mentioned; raw cells not read` -> `CANDIDATE_FACT_NOT_PROVEN`
- `payment_status_reference`: `None` -> `MISSING_PROOF`
- `tax_vendor_payment_handling_assumptions`: `None` -> `MISSING_PROOF`
- `invoice_shape_one_invoice_posture`: `one invoice for 2026-05-15 and 2026-05-08; operator also wants 2026-05-22 upcoming gig and older gigs reviewed for inclusion if applicable` -> `CANDIDATE_FACT_NOT_PROVEN`
- `final_invoice_packet_requirement`: `future final invoice packet required after security audit` -> `METADATA_CONTEXT_NOT_FINAL_INVOICE_PROOF`

### Capital Hilton Operator Memory Questions

- `memory_only_clarification`: Do you remember whether the Capital Hilton invoice should cover both 2026-05-08 and 2026-05-15 on one invoice?
- `proof_needed`: Do you remember whether $400/gig is the correct rate for both dates?
- `protected_proof_needed`: Is there a Coupa PO number or payment reference that should exist?
- `proof_needed`: Is the proof source likely Coupa, Excel, email, a PDF, a calendar entry, or a packet already in OpenClaw?
- `world_transition_needed`: Should the invoice go through Coupa only, email/AP contact, or another payment route?
- `security_gate_needed`: Is there any protected client material that must be represented only as metadata?
- `world_transition_needed`: What would convince you the invoice is ready to move from helm threshold lane into Finance World action?

## What Mission Control Can Render Next

- Package Preview surface: preview cards, included/excluded context summaries, missing proof, gates, receipts, stop conditions, and future dispatch blockers.
- Tool Adapter Receipt surface: requested adapter, package, actor, capability requested/granted/blocked, gates, blocked reasons, and output receipt shape.
- Agent Council can link dossier cards to package/tool summaries through this stable map snapshot without new per-file app dependencies.

## What Remains Blocked / Future-Gated

- No live dispatch, model launch, tool execution, browser/OAuth/account access, Gmail/calendar/Coupa/Telegram controls, credentials, send/submit/approval, planner/builder/queue/autonomy, arbitrary commands, or raw private context.
- Package and adapter records are proof/display surfaces only; they do not create authority.

## What This Fixes

- Adding a new backend read-model may update the map content or raw proof count, but it should not require a new Mission Control entitlement or app-facing file path.
- Mission Control can fail closed on the stable map if the map receipt is stale without treating the whole raw terrain as absent.

## Boundary

- Metadata/read-model contract only.
- No model calls, agent activation, browser/OAuth/account access, send/submit/approval, remount, repair, delete, file move, network operation, or C-drive artifact write.
