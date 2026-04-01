title: hitl-006-dashboard-ui
profile: architect
goal: Build HITL Approval Dashboard UI for viewing pending actions and approving/denying them quickly.
scope:
- Create dashboard view showing pending actions with status filters and age indicators.
- Add detail pane with payload preview, source agent, risk label, and audit trail.
- Add Approve and Deny controls wired to approval service API.
- Add optimistic UI updates with failure rollback and clear error states.
- If using React, place UI in isolated app/module and integrate with existing auth/session assumptions.
- If not using React in current stack, provide equivalent Python-served UI first and keep API contract React-ready.
success:
- User can approve/deny pending actions from dashboard without touching raw files.
- UI reflects state transitions in near real-time.
- Failures are visible and recoverable.
verification: |
  python3 -c "print('dashboard task scaffolded')"
depends_on: hitl-003-future-action-queue-api
notes: |
  Keep this compatible with current OpenClaw runtime first; React implementation can be layered if infrastructure is ready.
