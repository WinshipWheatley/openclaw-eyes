# LM2 Structured Output Retry Approval Packet

Status: `LM2_STRUCTURED_OUTPUT_RETRY_APPROVAL_PACKET_READY`
Packet status: `pending_operator_review`

This packet is not approval and does not run LM2. It prepares a review-only operator decision for one future room-backed LM2 retry with structured-output enforcement.

## Prior Attempt

- Prior attempt: `generated/read_models/lm2_room_backed_worker_one_time_pilot.json`
- Failure class: `non_json_model_output`
- Retry reason: `structured_output_required`

## Retry Scope

- Worker class: `lm2_bounded_worker`
- Runtime: `ollama`
- Model: `qwen3:8b-q4_K_M`
- Lane: `finance/capital_hilton`
- Question: What should I do here?
- Structured output required: `true`

## Structured Output Requirements

- JSON-only response
- no markdown
- no code fences
- no prose outside JSON
- one valid JSON example included in prompt
- schema adapter runs before verifier
- verifier remains the publish gate

## Operator Decision Options

- `approve_one_time_room_backed_lm2_structured_output_retry`
- `request_more_detail`
- `choose_different_model`
- `reject_for_now`

## Rules

- This packet is not approval.
- This packet does not run LM2.
- invocation_allowed=false.
- worker_spawn_allowed=false.
- proof_bundle_allowed=false.
- No protected business action.
- No external provider.
- No tool authority.
