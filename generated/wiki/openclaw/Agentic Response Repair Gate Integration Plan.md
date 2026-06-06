# Agentic Response Repair Gate Integration Plan

Status: AGENTIC_RESPONSE_REPAIR_GATE_INTEGRATION_PLAN_READY

This plan integrates the proof-to-response LM shadow harness, self-heal repair doctrine, and Goldilocks gate calibration into the next safe OpenClaw runtime build.

## Executive Summary

- summary: The next build should integrate a verifier-only response harness. It lets OpenClaw speak in concise agent text while receipts, proof bundles, gates, and verifier outcomes remain the source of truth.
- next safe build: verifier-only response harness

## Integrated Chain

- controller event or objective advance
- bounded proof bundle from receipts/cards/gates/meters/session timeline
- draft response from deterministic oracle now; future LM phrasing later
- deterministic verifier blocks unsupported facts, authority, protected promises, jargon, and overlong text
- self-heal repair proposal when blocker is repairable
- Goldilocks gate level determines readback, plan, stage, safe internal work, or approval preparation
- Mission Control renders concise agent response first, one control, meters, and collapsed details
- receipt records response/verifier/repair outcome

## Deterministic Vs Agentic Split

- stays deterministic: truth, receipts, authority, gate decisions, proof refs, lifecycle, protected action blocks, source hashes, verification status
- becomes agentic: phrasing, prioritization, diagnosis, repair proposal, next-step explanation, missing-proof explanation, contextual helpfulness, what can be done now reasoning

## Self-heal Flow

- doctrine: no_black_box_repairs
- steps: name blocker, cite proof, state what can be done now, state what cannot be done yet, ask for the smallest manual operator step if required, stage repair package, validate, record receipt
- repair paths: {'repair_ref': 'self_heal:mac_controller_response_stale_after_lane_switch', 'name_blocker': 'Mac controller response is stale because the request/card scope does not match the active lane.', 'proof_refs': ['generated/read_models/operator_controller_design_brief.json', 'generated/read_models/dynamic_card_packet_latest.json', 'generated/read_models/proof_to_response_tdd_spec.json'], 'what_can_be_done_now': ['stage a scoped renderer fix', 'prepare release validation and smoke checks'], 'what_cannot_be_done_yet': ['claim fixed', 'rewrite lane state without receipt', 'restart services'], 'smallest_operator_step': "{'expected_receipt': 'scoped renderer package receipt plus release validation receipt', 'forbidden_broad_ask': ['grant broad system authority', 'provide credentials', 'give full disk access', 'approve unrelated cleanup', 'approve protected business action'], 'manual_required': False, 'reason': 'The safe next move is an internal scoped renderer package.', 'smallest_action': 'No manual action is required unless Winship wants to choose a different active lane.'}", 'stage_repair_package': 'Stage scoped renderer fix', 'validation': ['unit-test stale request/card scope mismatch', 'run release validation for the renderer package', 'run Mac controller smoke with active lane switch'], 'receipt_required': "{'plain_rule': 'Do not claim repair/update success until validation passes and a receipt is recorded.', 'receipt_required': True, 'required_receipt_refs': ['receipt:scoped_renderer_package_staged', 'receipt:release_validation_passed', 'receipt:mac_controller_smoke_passed'], 'success_claim_allowed_without_receipt': False, 'success_claim_requires_states': ['validation_passed', 'receipt_recorded'], 'validation_required': True}", 'authority_boundary': {'protected_actions_allowed': False}}, {'repair_ref': 'self_heal:evidence_picker_path_leaked_into_composer', 'name_blocker': 'Evidence picker proof file path was routed as chat input into the workflow composer.', 'proof_refs': ['generated/read_models/operator_controller_event_router_status.json', 'generated/read_models/evidence_intake_status.json', 'generated/read_models/workflow_composer_latest.json'], 'what_can_be_done_now': ['stage evidence-picker isolation', 'add route tests'], 'what_cannot_be_done_yet': ['stage a workflow package from the proof path', 'read proof file bodies', 'submit anything'], 'smallest_operator_step': "{'expected_receipt': 'evidence picker isolation package receipt and route test receipt', 'forbidden_broad_ask': ['grant broad system authority', 'provide credentials', 'give full disk access', 'approve unrelated cleanup', 'approve protected business action'], 'manual_required': False, 'reason': 'The safe fix is an internal event-route boundary package.', 'smallest_action': 'No manual action is required; the route isolation package can be staged internally.'}", 'stage_repair_package': 'Isolate evidence picker from composer', 'validation': ['simulate evidence picker path selection', 'assert composer receives no chat body from the proof path', 'assert evidence intake receives only a proof reference envelope'], 'receipt_required': "{'plain_rule': 'Do not claim repair/update success until validation passes and a receipt is recorded.', 'receipt_required': True, 'required_receipt_refs': ['receipt:evidence_picker_isolation_package_staged', 'receipt:evidence_route_test_passed'], 'success_claim_allowed_without_receipt': False, 'success_claim_requires_states': ['validation_passed', 'receipt_recorded'], 'validation_required': True}", 'authority_boundary': {'protected_actions_allowed': False}}, {'repair_ref': 'self_heal:excel_export_blocked_by_file_access', 'name_blocker': 'Excel file access is blocked, so workbook cells and PDF export are not available.', 'proof_refs': ['generated/read_models/client_invoice_workbook_registry.json', 'generated/read_models/protected_evidence_reference_receipt.json', 'generated/read_models/universal_receipt_envelope_contract.json'], 'what_can_be_done_now': ['record the access blocker', 'prepare the workbook access proof request'], 'what_cannot_be_done_yet': ['read workbook cells', 'export PDF', 'mutate workbook', 'mark paid'], 'smallest_operator_step': "{'expected_receipt': 'file-access proof receipt for the selected workbook reference', 'forbidden_broad_ask': ['grant broad system authority', 'provide credentials', 'give full disk access', 'approve unrelated cleanup', 'approve protected business action'], 'manual_required': True, 'reason': 'OpenClaw cannot prove workbook access from the current state.', 'smallest_action': 'Grant access to the named workbook or choose a different workbook reference.'}", 'stage_repair_package': 'Provide workbook access proof or choose another workbook', 'validation': ['wait for file-access proof receipt', 'validate the selected workbook reference matches the proof', 'only after proof, allow a separate export package to validate workbook read and PDF export gates'], 'receipt_required': "{'plain_rule': 'Do not claim repair/update success until validation passes and a receipt is recorded.', 'receipt_required': True, 'required_receipt_refs': ['receipt:file_access_proof_recorded', 'receipt:workbook_reference_validated', 'receipt:export_gate_validated'], 'success_claim_allowed_without_receipt': False, 'success_claim_requires_states': ['validation_passed', 'receipt_recorded'], 'validation_required': True}", 'authority_boundary': {'protected_actions_allowed': False}}, {'repair_ref': 'self_heal:remote_desktop_trace_log_leak', 'name_blocker': 'Remote Desktop trace logs are filling C:, but cleanup must be targeted and receipt-backed.', 'proof_refs': ['generated/read_models/openclaw_service_keeper_status.json', 'generated/read_models/sync_health.json', 'generated/read_models/universal_receipt_envelope_contract.json'], 'what_can_be_done_now': ['stage targeted trace-log cleanup', 'stage tracing-disable package', 'prepare validation'], 'what_cannot_be_done_yet': ['delete unknown temp files', 'delete active swap/vhdx', 'change tracing without package receipt'], 'smallest_operator_step': "{'expected_receipt': 'targeted cleanup or tracing-disable receipt plus validation receipt', 'forbidden_broad_ask': ['grant broad system authority', 'provide credentials', 'give full disk access', 'approve unrelated cleanup', 'approve protected business action'], 'manual_required': True, 'reason': 'Deleting files or changing tracing settings crosses a protected system-change gate.', 'smallest_action': 'Approve one named trace-log cleanup package or one named tracing-disable package.'}", 'stage_repair_package': 'Choose targeted trace cleanup or disable tracing package', 'validation': ['inventory only named Remote Desktop trace-log paths', 'prove targets are inactive and inside the package target set', 'record before/after free-space and tracing-state receipts'], 'receipt_required': "{'plain_rule': 'Do not claim repair/update success until validation passes and a receipt is recorded.', 'receipt_required': True, 'required_receipt_refs': ['receipt:rdp_trace_cleanup_package_approved', 'receipt:trace_targets_validated_inactive', 'receipt:cleanup_or_disable_validation_passed'], 'success_claim_allowed_without_receipt': False, 'success_claim_requires_states': ['validation_passed', 'receipt_recorded'], 'validation_required': True}", 'authority_boundary': {'protected_actions_allowed': False}}, {'repair_ref': 'self_heal:missing_proof_for_payment', 'name_blocker': 'Payment evidence is missing, so paid state and ledger mutation are blocked.', 'proof_refs': ['generated/read_models/capital_hilton_invoice_operator_run_status.json', 'generated/read_models/proof_meter_normalization.json', 'generated/read_models/universal_receipt_envelope_contract.json'], 'what_can_be_done_now': ['hold payment watch', 'ask for proof', 'show the blocked gate'], 'what_cannot_be_done_yet': ['mark paid', 'mutate ledger', 'submit Coupa', 'send email'], 'smallest_operator_step': "{'expected_receipt': 'payment evidence receipt bound to the invoice/payment thread', 'forbidden_broad_ask': ['grant broad system authority', 'provide credentials', 'give full disk access', 'approve unrelated cleanup', 'approve protected business action'], 'manual_required': True, 'reason': 'Guardian/Chief cannot prove paid state without evidence.', 'smallest_action': 'Attach payment evidence.'}", 'stage_repair_package': 'Attach payment proof', 'validation': ['validate attached proof is payment evidence', 'bind proof to the invoice/payment thread', 'only after validation, require a separate receipt for any paid-state or ledger update'], 'receipt_required': "{'plain_rule': 'Do not claim repair/update success until validation passes and a receipt is recorded.', 'receipt_required': True, 'required_receipt_refs': ['receipt:payment_evidence_attached', 'receipt:payment_evidence_validated', 'receipt:paid_state_update_if_later_authorized'], 'success_claim_allowed_without_receipt': False, 'success_claim_requires_states': ['validation_passed', 'receipt_recorded'], 'validation_required': True}", 'authority_boundary': {'protected_actions_allowed': False}}

## Gate Calibration Summary

- source ref: generated/read_models/goldilocks_gate_calibration.json
- goldilocks zone: {"core_rule": "Authority must be specific, scoped, receipted, and proven; generated language never creates truth or authority.", "freedom_for": ["planning", "drafting", "local inspection", "staging", "repair proposals", "proof collection", "review packets", "safe local deterministic checks", "repo patch/test/commit when package grants it"], "strict_gates_for": ["external effects", "money", "sending", "submission", "ledger", "credentials", "source workbook mutation", "push/merge", "live provider/tool expansion", "live workers or loops"]}
- agents may: inspect local proof, draft, stage, patch code, run safe tests, prepare approval package, prepare review packet, explain next step
- agents may not: execute protected external action, invent truth, grant authority, bypass Guardian, promote memory to truth, submit/send/post/mark paid/push
- recommended gate level for next build: safe_internal_work for local repo integration; stage/prepare_approval for business surfaces

## Next Build Recommendation

- choice: verifier-only response harness
- why: It puts proof bundles and deterministic verification in the response path before any live LM/runtime expansion, so Mission Control can receive concise agent text while truth and authority stay deterministic.
- not chosen yet: local LM shadow response pilot, self-heal repair package route, Goldilocks gate-level integration as live authority

## Tests Required Before Live Lm

- proof bundle redaction tests
- verifier publish/block tests
- self-heal no-black-box repair tests
- Goldilocks gate regression tests
- Mac response-first rendering smoke
- unsafe true-grant scan
- receipt and source-hash grounding tests
- protected action negative tests

## Risks

- A polished response can sound like truth unless every factual claim remains verifier-backed.
- Repair proposals can be mistaken for repair success unless validation and receipts are visible.
- Gate labels that are too strict make agents useless; labels that are too loose imply protected authority.
- Mac UI may regress into card-deck-first rendering unless response-first tests exist.
- Live LM/runtime expansion before verifier parity would create truth and authority ambiguity.

## Final Recommendation

- recommendation: Ship the verifier-only response harness before local LM shadow response pilot or repair-route execution.
- reason: It preserves deterministic truth and authority while making the operator experience response-first and agentic.

## Proof

- Preconditions ready: `true`
- Unsafe true grants absent: `true`
- First sequence step count: `5`
