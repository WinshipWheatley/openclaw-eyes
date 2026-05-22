# Security Delta Review Contract v0

## ELIWINSHIP Summary

The full Security Pass is the baseline law. A Security Delta Review is the smaller check for a new item: does it fit an existing approved read-only, preview, metadata, capture, world-preview, or stable-map class, or does it ask for new authority? If it asks for account, financial, runtime, queue, model, tool, send, or credential authority, it needs a repass or stays blocked.

## Delta Classes

- `NO_DELTA_REQUIRED`
- `READ_ONLY_DELTA`
- `PREVIEW_SURFACE_DELTA`
- `METADATA_ONLY_DELTA`
- `PACKAGE_PREVIEW_DELTA`
- `MEMORY_CANDIDATE_DELTA`
- `OPERATOR_CAPTURE_DELTA`
- `WORLD_PREVIEW_DELTA`
- `STABLE_MAP_SURFACE_DELTA`
- `TOOL_ADAPTER_DELTA`
- `MODEL_ROUTING_DELTA`
- `ACCOUNT_ACCESS_DELTA`
- `SEND_SUBMIT_APPROVAL_DELTA`
- `QUEUE_AUTONOMY_DELTA`
- `RUNTIME_EXECUTION_DELTA`
- `EXTERNAL_DEPENDENCY_DELTA`
- `FINANCIAL_AUTHORITY_DELTA`
- `SECURITY_REPASS_REQUIRED`
- `UNKNOWN_FAIL_CLOSED`

## Decision Outcomes

- `ALLOWED_UNDER_EXISTING_SECURITY_CLASS`
- `ALLOWED_READ_ONLY`
- `ALLOWED_PREVIEW_ONLY`
- `ALLOWED_METADATA_ONLY`
- `ALLOWED_CAPTURE_ONLY`
- `REQUIRES_OPERATOR_APPROVAL`
- `REQUIRES_GUARDIAN_GATE`
- `REQUIRES_HERMES_REVIEW`
- `REQUIRES_CHIEF_RECONCILIATION`
- `REQUIRES_SECURITY_DELTA_REVIEW`
- `REQUIRES_SECURITY_REPASS`
- `FUTURE_GATED`
- `BLOCKED_AUTHORITY`
- `BLOCKED_SENSITIVE`
- `BLOCKED_CREDENTIAL`
- `BLOCKED_ACCOUNT`
- `BLOCKED_NETWORK`
- `BLOCKED_EXECUTION`
- `UNKNOWN_FAIL_CLOSED`

## Default Examples

- `new_read_only_mission_control_card`: `READ_ONLY_DELTA` -> `ALLOWED_READ_ONLY`. Next: Allow as read-only UI work in a later Mac lane with no execution controls.
- `new_preview_surface_from_stable_map`: `PREVIEW_SURFACE_DELTA` -> `ALLOWED_PREVIEW_ONLY`. Next: Use stable-map data only; do not add direct packet dependency or live controls.
- `new_package_preview_type`: `PACKAGE_PREVIEW_DELTA` -> `REQUIRES_SECURITY_DELTA_REVIEW`. Next: Run bounded delta review before surfacing the new preview type.
- `new_memory_candidate_capture_surface`: `MEMORY_CANDIDATE_DELTA` -> `ALLOWED_CAPTURE_ONLY`. Next: Capture as memory candidate only; never treat operator answer as proof.
- `new_operator_answer_popup`: `OPERATOR_CAPTURE_DELTA` -> `REQUIRES_SECURITY_DELTA_REVIEW`. Next: Review capture semantics before UI implementation; answers remain non-proof.
- `new_markdown_visibility_surface`: `METADATA_ONLY_DELTA` -> `ALLOWED_METADATA_ONLY`. Next: Surface metadata only; do not inspect broad bodies or move files.
- `new_browser_oauth_coupa_adapter`: `ACCOUNT_ACCESS_DELTA` -> `REQUIRES_SECURITY_REPASS`. Next: Keep blocked until a future security repass explicitly defines account authority.
- `new_gmail_calendar_adapter`: `ACCOUNT_ACCESS_DELTA` -> `REQUIRES_SECURITY_REPASS`. Next: Keep blocked until security repass defines account and send boundaries.
- `new_invoice_generation_or_ledger_write`: `FINANCIAL_AUTHORITY_DELTA` -> `REQUIRES_SECURITY_REPASS`. Next: Keep financial action blocked; model only as future-gated contract work.
- `new_queue_autonomy_lane`: `QUEUE_AUTONOMY_DELTA` -> `REQUIRES_SECURITY_REPASS`. Next: Keep parked until queue/autonomy authority is explicitly defined by repass.
- `new_runtime_agent_activation`: `RUNTIME_EXECUTION_DELTA` -> `REQUIRES_SECURITY_REPASS`. Next: Keep runtime activation blocked until repass defines actor authority.
- `external_open_source_dependency_recommendation`: `EXTERNAL_DEPENDENCY_DELTA` -> `REQUIRES_HERMES_REVIEW`. Next: Treat as advisory only; do not adopt or fetch external dependency in this lane.
- `new_stable_map_summary_only`: `STABLE_MAP_SURFACE_DELTA` -> `ALLOWED_UNDER_EXISTING_SECURITY_CLASS`. Next: Allow summary-only stable-map inclusion in a later refresh; stable map remains app-facing reflection.
- `new_world_preview_surface`: `WORLD_PREVIEW_DELTA` -> `ALLOWED_PREVIEW_ONLY`. Next: Allow read-only world preview; do not add domain actions.

## Authority Boundary

- Delta review can recommend, block, future-gate, or require review.
- Delta review cannot execute, launch, queue, mutate app/backend, promote the stable map automatically, activate detected capabilities, or touch external accounts/network.
- Operator answers remain memory candidates, not proof.
- Stable-map summary deltas remain app-facing reflections, not source truth.

## Machine Proof

- Default example count: `14`.
- Security repass examples: `5`.
- All live authority flags false: `true`.
- Action authority granted: `false`.
- Auto-promotion allowed: `false`.
- Operator answers are not proof: `true`.
- Content hash: `sha256:80f81252f5c3c0bd9bb3935c901733dc99c79223ae51aa37cdab453597c28216`.
