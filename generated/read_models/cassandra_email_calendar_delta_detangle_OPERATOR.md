# Cassandra Email Calendar Delta Detangle v0

Status:
- Detangle posture: classification/read-model only.
- Live Gmail/calendar/OAuth/send/draft authority: `false`.
- Telegram notification behavior changed: `false`.
- Calendar cleanup/normalization started: `false`.
- Repo B inspected/executed: `false`.

## ELI5 Summary
- Cassandra can safely represent review-only packets and draft previews from governed read-model facts.
- Gmail access, Gmail draft creation, email send/reply, Google/Apple Calendar access, calendar mutation, OAuth, credentials, and browser/tool bridges are blocked.
- Telegram draft preview behavior is separate from Mission Control visibility; this lane changes neither.
- Calendar cleanup is not happening yet. The merged Google/Apple calendar situation is recorded only as future context.
- A named workflow, protected-access gate, Guardian/security-threshold controls, specific draft/attachment identity, and later approval receipt would be required first.

## Surfaces
- `governed_cassandra_review_packet_path`: `GOVERNED_REVIEW_PACKET_READY`; posture `available_as_review_packet_read_model_only`.
- `cassandra_draft_preview_packet`: `DRAFT_PREVIEW_ONLY`; posture `review_preview_visible_no_gmail_draft`.
- `telegram_operator_notification_path`: `TELEGRAM_NOTIFICATION_SEPARATE`; posture `separate_runtime_surface_unchanged_by_this_lane`.
- `gmail_live_account_access`: `LIVE_GMAIL_BLOCKED`; posture `blocked_no_live_account_access`.
- `email_send_and_gmail_draft_creation`: `EMAIL_SEND_BLOCKED`; posture `blocked_no_draft_no_send`.
- `calendar_discovery_understanding`: `CALENDAR_DISCOVERY_BLOCKED`; posture `blocked_context_recorded_no_live_calendar_read`.
- `calendar_normalization_future`: `CALENDAR_NORMALIZATION_FUTURE`; posture `future_scoped_evidence_normalization_only`.
- `oauth_credential_tool_browser_bridges`: `OAUTH_CREDENTIAL_BLOCKED`; posture `blocked_reference_or_metadata_only`.
- `legacy_repo_b_email_calendar_delta`: `LEGACY_REFERENCE_ONLY`; posture `existing_delta_read_model_reference_only`.
- `unknown_email_calendar_surface`: `UNKNOWN_FAIL_CLOSED`; posture `blocked_until_classified`.

## Classification Counts
- `GOVERNED_REVIEW_PACKET_READY`: 1 primary / 2 labels
- `DRAFT_PREVIEW_ONLY`: 1 primary / 2 labels
- `TELEGRAM_NOTIFICATION_SEPARATE`: 1 primary / 1 labels
- `LIVE_GMAIL_BLOCKED`: 1 primary / 2 labels
- `EMAIL_SEND_BLOCKED`: 1 primary / 2 labels
- `CALENDAR_DISCOVERY_BLOCKED`: 1 primary / 2 labels
- `CALENDAR_NORMALIZATION_FUTURE`: 1 primary / 2 labels
- `OAUTH_CREDENTIAL_BLOCKED`: 1 primary / 4 labels
- `PROTECTED_ACCESS_REQUIRED`: 0 primary / 5 labels
- `SECURITY_THRESHOLD_REQUIRED`: 0 primary / 5 labels
- `LEGACY_REFERENCE_ONLY`: 1 primary / 2 labels
- `UNKNOWN_FAIL_CLOSED`: 1 primary / 1 labels

## Boundaries
- Mission Control visibility is read-model/mirror visibility, not a backend command path.
- Telegram/operator notification remains a separate unchanged runtime path.
- Unknown email/calendar capability fails closed.
- No Gmail, calendar, OAuth, credentials, Telegram send, Gmail draft, email send, browser, tools, agents, or runtime authority was enabled.

Next safe lane: Cassandra Draft Identity Reference Rail v0
