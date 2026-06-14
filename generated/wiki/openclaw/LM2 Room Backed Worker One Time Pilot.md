# LM2 Room Backed Worker One Time Pilot

Status: `LM2_ROOM_BACKED_WORKER_ONE_TIME_PILOT_READY`

This records one approved room-backed LM2 worker attempt for Finance / Capital Hilton.

## Scope

- Worker class: `lm2_bounded_worker`
- Runtime: `ollama`
- Model: `qwen3:8b-q4_K_M`
- Lane: `finance/capital_hilton`
- Question: What should I do here?
- Attempt count: `1`
- Approval used: `true`

## Invocation

- Attempted: `true`
- Return code: `0`
- Timed out: `false`
- Publication: `safe_fallback_published`

## Published Response

- Headline: Payment evidence needed
- Body: Coupa is processing. I can't mark this paid until payment evidence is attached. The ledger stays untouched.
- Next step: Attach payment evidence.

## Receipts

- `operator_approval_receipt`: present
- `room_backed_package_receipt`: present
- `project_room_readiness_receipt`: present
- `worker_package_boundary_receipt`: present
- `model_invocation_boundary_receipt`: present
- `redacted_proof_bundle_receipt`: present
- `no_external_provider_receipt`: present
- `no_tool_authority_receipt`: present
- `worker_started_receipt`: present
- `model_invocation_attempt_receipt`: present
- `raw_draft_captured_receipt`: present
- `worker_stopped_receipt`: present
- `verifier_pass_fail_receipt`: present
- `fallback_receipt`: present
- `no_business_action_receipt`: present

## Boundaries

- No external provider.
- No model tool authority.
- No browser, Gmail, Coupa, email send, submit, ledger mutation, workbook mutation, PDF export, paid marking, memory promotion, push, or merge.
- Raw finance/private proof and operator/device/session secrets were not sent.
