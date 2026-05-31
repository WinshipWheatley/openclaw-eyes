# OpenClaw Business-Object Layer Audit

- Readiness: READY_FOR_BUILD_PLANNING_NOT_EXECUTION
- Freshness: FRESH for 60 minutes
- Overall score: 3.67 / 5.0
- Business objects: 16
- Top gaps: 13

## External Registry Input
- Status: EXTERNAL_REGISTRY_MATERIALIZED
- Source: openclaw-eyes main 1a6b7b0b463968f3161e048bd7936dc06505a3bb
- Role: canonical_owner=openclaw-eyes; local_role=READ_ONLY_EXTERNAL_INPUT

## Freshness
- Required input hashes are recorded and currently matched at export time.
## Scores
- Workflow Design: 4.0 / 5.0 (STRONG_WITH_STALE_HANDOFFS)
- Data Access: 3.5 / 5.0 (GOOD_LOCAL_READ_MODELS_BRIDGE_PARTIAL)
- Authority: 4.5 / 5.0 (STRONG_DEFAULT_DENY)
- Evals: 2.5 / 5.0 (FOCUSED_TESTS_PRESENT_END_TO_END_GAPS)
- Audit Trails & Recovery: 4.0 / 5.0 (GOOD_RECEIPTS_AND_MONITORS_STALE_VIEWS)
- Business Object Proximity: 3.5 / 5.0 (LIVE_ARTS_CLOSE_CAPITAL_HILTON_FARTHER)

## Stale Claims Corrected
- live_arts_candidate_unselected: 2026-1001 — June 2026 Speaker Rental — $900
- pdf_package_missing_fields: pdf_export_package has invoice_id=2026-1001, selected_sheet_label=June 2026 Speaker Rental, output_bridge_path=/mnt/e/openclaw/artifacts/invoice_workbooks/live_arts_md/2026-1001/Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental.pdf.
- openclaw_eyes_registry_external_input: openclaw-eyes system knowledge registry is canonical on main and imported as READ_ONLY_EXTERNAL_INPUT from commit 1a6b7b0b463968f3161e048bd7936dc06505a3bb.
- request_response_unstable: Service supervision reports READY and request-response ExecStart includes --watch-seconds 21600; core status={'last_keeper_action': 'NO_ACTION_REQUIRED', 'request_response_active': True, 'request_response_sub_state': 'running', 'sentinel_timer_active': True, 'sentinel_timer_sub_state': 'waiting', 'service_keeper_timer_active': True, 'service_keeper_timer_sub_state': 'waiting', 'unresolved_supervision_risks': []}.
- mac_export_completed: Live Arts backend PDF package is ready, but actual Mac export completion and selected artifact attachment are not confirmed.
- ledger_ready: Ledger posting remains blocked/disallowed until send proof, payment confirmation, and explicit ledger receipts exist.

## Top Gaps
- 1. mac_helper_permission_architecture: Mac Excel helper / Access Broker permission path is unresolved; in-app Excel automation is blocked.
- 2. live_arts_pdf_export_completion: Live Arts PDF package is ready, but selected_invoice_pdf_export_completed_candidate is missing.
- 3. live_arts_attachment_ready: Live Arts attachment_ready remains false until valid export and operator review receipts exist.
- 4. live_arts_manual_send_proof: Manual send metadata exists, but proof screenshot/ref is missing and file-backed proof is false.
- 5. live_arts_recipient_confirmation: Dane/Draper/Earnie email details are not confirmed; Winship copy is known only.
- 6. guardian_approval_not_created: Guardian approval request is required but not created/ready for Live Arts.
- 7. clara_final_draft_blocked: Clara drafts are preview/draft-only and not send-ready.
- 8. payment_watch_readiness_only: Payment watch is readiness-only until send/manual-send proof exists; no bank read or ledger match has run.
- 9. ledger_posting_blocked: Ledger posting remains explicitly disallowed and must stay parked until proof chain exists.
- 10. hermes_handoff_stale: Hermes/Chief still list invoice candidate selection as blocking despite Live Arts confirmed selection.
- 11. estate_bridge_mirror_missing: Reference resolver marks estate topology read-model bridge mirror as MISSING.
- 12. capital_hilton_selection_and_coupa: Capital Hilton still needs invoice record/period selection, Coupa proof, recipients, and artifact linkage.
- 13. business_object_evals_missing: End-to-end business-object evals are missing for Mac helper, result intake, attachment promotion, proof, payment, and Capital Hilton.

## Build Order
### now
- Reconcile stale Hermes/Chief Live Arts blockers against the confirmed 2026-1001 bundle state.
- Build or verify Mac helper/Access Broker permission path for scoped Excel PDF export.
- Add end-to-end evals for Mac result intake and attachment promotion without executing Excel/PDF.
### next
- After Mac export succeeds, ingest result candidate and keep artifact OPERATOR_REVIEW_REQUIRED until reviewed.
- Confirm Live Arts recipients and Guardian/operator approval gates.
- Capture manual-send proof if manual send already happened, then activate payment watch readiness only.
- Repair estate topology bridge mirror and Mac bridge permission representation.
### later
- Advance Capital Hilton invoice selection/Coupa proof/artifact linkage rails.
- Decide Mac app remote/backup strategy and runtime actor canonical home.
### parked
- Ledger posting automation.
- Live email/Gmail/browser/Coupa execution.
- Broad LM summarization or Chief launch.

Boundary: deterministic read-model audit only; no live business action performed.
