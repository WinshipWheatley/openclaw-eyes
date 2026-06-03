# Spawned Worker Package Lifecycle

Status: `SPAWNED_WORKER_PACKAGE_LIFECYCLE_READY`

This contract defines a PR-like lifecycle for bounded worker outputs from PC_CODEX and MAC_CODEX. It does not spawn workers, run child agents, push, or grant tool authority.

## Lifecycle States

- `PACKAGE_STAGED`: A package exists locally and is ready for assignment review.
- `WORKER_ASSIGNED`: A bounded worker_ref is assigned, but no worker has been run by this lifecycle.
- `WORKER_RUNNING`: A separate approved process reports worker execution in progress.
- `RESULT_READY`: Worker output exists and is ready to shape into a review packet.
- `REVIEW_PACKET_READY`: A PR-like review packet is available for operator review.
- `OPERATOR_APPROVED`: The operator approved the review packet for merge or recording.
- `MERGED_OR_RECORDED`: The approved work was merged or recorded with proof refs.
- `REWORK_REQUIRED`: The review packet needs revision before approval.
- `BLOCKED_BY_GATE`: A safety, authority, missing-proof, or package gate blocks progress.

## Review Packet

Required fields:

- `package_id`
- `worker_ref`
- `channel_ref`
- `files_changed`
- `tests_run`
- `receipts`
- `screenshots`
- `proof_refs`
- `unsafe_scan_result`
- `human_summary`
- `next_safe_action`

## Authority

- Worker does not inherit speaker authority.
- speaker_ref does not grant tools.
- All business actions remain gated.
- No child spawning unless LM2 cage/Guardian allows.
- Review packet readiness is not approval.
- Operator approval is required before merge or recorded completion.

## Boundary

- No worker spawn.
- No child agents.
- No git push.
- No email send.
- No Gmail/browser/Coupa access.
- No ledger or workbook mutation.
- No PDF export.
- No submit or mark-paid.
- Review packet readiness is not approval.
