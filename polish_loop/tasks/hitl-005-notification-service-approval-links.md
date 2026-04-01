title: hitl-005-notification-service-approval-links
profile: standard
goal: Add Notification Service that sends pending-action summaries with Approve/Deny links or commands to external channels.
scope:
- Implement notification formatter: action summary, risk level, source agent, payload preview.
- Generate approve/deny action links or command tokens (signed/HMAC where applicable).
- Integrate with available outbound channel (Telegram via existing sender, optional webhook/email adapter).
- Add callback handler that validates approval token and updates pending action state.
- Log notification send result and callback decision with action_id traceability.
success:
- Pending actions trigger a notification with actionable approve/deny controls.
- Approval callback updates action status securely.
- Decision path is auditable end-to-end.
verification: |
  python3 -c "print('notification path implemented')"
depends_on: hitl-003-future-action-queue-api
notes: |
  Do not expose raw secrets in URLs; use signed short-lived tokens.
