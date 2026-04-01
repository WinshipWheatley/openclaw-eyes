title: hitl-001-approval-pipeline-foundation
profile: architect
goal: Establish the core Human-in-the-Loop approval pipeline so Cassandra can propose actions that remain pending until explicit approve/deny.
scope:
- Define canonical pending action schema fields: action_id, source_agent, action_type, payload, status, requested_at, expires_at, approved_by, approved_at, denied_reason.
- Implement storage helpers under /home/openclaw for pending action create/get/list/update (file-backed JSONL or existing state file style).
- Add status constants: WAITING_FOR_APPROVAL, APPROVED, DENIED, EXPIRED, FAILED.
- Add Cassandra integration point that creates pending actions instead of directly executing external actions.
- Ensure all state transitions are audited to a log file in /mnt/c/OpenClaw/logs/.
- Keep backwards compatibility: if HITL toggle is off, existing behavior can continue.
success:
- Cassandra can create pending actions with status WAITING_FOR_APPROVAL.
- No external execution happens before explicit approval.
- Transition history is persisted and auditable.
verification: |
  python3 -c "import json,glob,os; print('pending_store_ok' if True else 'fail')"
notes: |
  This task is system-foundation. Prefer integrating existing Python services first.
  Do not introduce irreversible external sends in this task.
