title: hitl-003-future-action-queue-api
profile: standard
goal: Create API/service endpoints for Cassandra to submit proposed actions that remain WAITING_FOR_APPROVAL until approved/denied by user.
scope:
- Add pending action service methods: create_pending_action, list_pending_actions, get_pending_action, approve_action, deny_action.
- Define validation for required fields: type, payload, recipient, amount (when financial).
- Add endpoint or command interface callable from Cassandra and dashboard layer.
- On approve, hand off to existing execution path with audit stamp (approved_by, approved_at).
- On deny, mark DENIED and store reason.
- Add anti-duplicate idempotency key support for repeated proposals.
success:
- New proposals enter WAITING_FOR_APPROVAL and do not execute immediately.
- Approve/deny transitions work and are logged.
- Duplicate submissions do not create duplicate pending actions.
verification: |
  python3 -c "print('pending queue api wired')"
depends_on: hitl-001-approval-pipeline-foundation
notes: |
  If a web API is added later, keep this service layer reusable beneath HTTP routes.
