# June 1 2026 Client Work Harvest

Status: `INVOICE_STEEL_THREAD_HARVEST_REGISTRY_READY`

This page consolidates the June 1 client-work harvest into reusable OpenClaw rails. It records what happened, what OpenClaw learned, what can be reused, and what remains operator-assisted.

## Completed Client Work

- St. Anne's May 2026 invoice: manual send out of band ingested; paid remains false; ledger remains untouched.
- Capital Hilton invoice: May 29 corrected, PDF exported, Coupa submitted and observed as `Processing`, and email to Annette recorded as operator-assisted.
- Capital Hilton fight-weekend proposal: proposal draft and PDF were sent to Lawrence for client review; proposal is not accepted and finance handoff is disabled.
- Live Arts: corrected PDF artifact pattern records an operator-approved one-page artifact while no-send, no-ledger, no-paid gates remain closed.

## What OpenClaw Learned

- Operator-approved PDF artifacts need their own approved state, distinct from candidate lineage and email attachment authority.
- Manual sends can be ingested as out-of-band truth without claiming OpenClaw performed the send.
- Codex Desktop, Excel GUI, Coupa browser, and Gmail can be recorded as operator-assist providers without confusing them for autonomous OpenClaw actions.
- Business Development proposals need their own lifecycle before Finance.
- St. Anne's monthly service events should be record-only during the month and rolled up at month end after operator review.

## What Should Become Reusable

- Approved PDF artifact promotion with rejected-candidate lineage.
- Manual send receipt ingestion.
- Operator-assisted Coupa PO invoice workflow.
- Excel GUI print-to-PDF fallback with artifact proof.
- Gmail draft replacement and final send gate receipts.
- Business Development proposal lifecycle.
- Monthly work-log to invoice-package rollup.
- Client-work closeout snapshots for durable business truth.

## What Remains Manual Or Operator-Assisted

- Telegram/Cassandra intake is not live-connected.
- Excel workbook write and PDF export require staged approval or a hardened receipt-driven provider.
- Coupa requires login/MFA, Remit-To decision, invoice-number normalization, and final submit gate.
- Gmail requires draft review, attachment proof, and final send gate.
- Proposal acceptance requires a separate acceptance receipt.
- Ledger and paid state remain separate from all invoice/proposal evidence.

## Next Developer Priorities

- Build receipt-driven workbook patch and PDF export rails.
- Implement a work-log event intake and month rollup for St. Anne's.
- Formalize proposal acceptance receipts and finance handoff eligibility.
- Harden operator-assist provider receipts across Codex Desktop, Excel GUI, Coupa, and Gmail.
- Add bridge-visible registry cards for reusable client-work patterns.
- Keep ledger and paid mutation behind separate explicit authority.

## Primary Artifacts

- `generated/read_models/client_work_closeout_2026_06_01.json`
- `generated/read_models/invoice_steel_thread_harvest_registry.json`
- `generated/read_models/st_annes_monthly_work_log_contract.json`
- `generated/read_models/capital_hilton_coupa_workflow_harvest.json`
- `generated/read_models/business_development_proposal_lane_registry.json`
- `generated/read_models/operator_assist_provider_registry.json`
