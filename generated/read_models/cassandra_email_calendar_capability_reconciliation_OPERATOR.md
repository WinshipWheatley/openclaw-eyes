# Cassandra Email + Calendar Capability Reconciliation v0

Status:
- Reconciliation status: `reconciled_review_only_no_live_authority`.
- Live Gmail/calendar/send/calendar mutation authority enabled: `false`.
- Repo B executed/imported: `false`.
- Generic calendar cleanup started: `false`.

## Operator Meaning
- Cassandra has older email/calendar-related capability evidence, but the safe path is governed draft/review packets before any future action-scoped approval or execution.
- Cassandra may prepare review-only packets later; Guardian remains the specific approval gate.

## Existing Capability Classification
- KEEP_AND_BRIDGE: cassandra_metadata_email_triage, cassandra_send_status_dry_run, cassandra_governed_review_packet_request, guardian_specific_approval_contracts, agent_packet_templates
- KEEP_AS_REFERENCE: cassandra_outreach_draft_era, cassandra_brain_email_calendar_intents, repo_b_runtime_reference
- UNSAFE_OR_BLOCKED: google_access_broker_email_calendar_surface, calendar_source_cleanup
- UNKNOWN_NEEDS_REVIEW: unknown_email_calendar_capability
- SUPERSEDED: none
- NOT_FOUND: none

## Safe Forward Path
- operator_intent: allowed_now=`true`; intent capture only.
- governed_intake: allowed_now=`true`; bounded metadata/context packet only.
- facts_context_read_models: allowed_now=`true`; visibility not execution.
- draft_review_packet: allowed_now=`true`; review-only draft/context; no Gmail draft creation.
- guardian_approval_request: allowed_now=`false`; future specific request only.
- specific_approval_receipt: allowed_now=`false`; future action/scope-bound receipt only.
- gated_send_or_calendar_action: allowed_now=`false`; future executor only after explicit approved item.

## Blocked Now
- `live_gmail_read`
- `gmail_body_read`
- `gmail_draft_creation`
- `email_send_or_reply`
- `google_calendar_read`
- `apple_calendar_read_or_write`
- `calendar_create_update_delete`
- `oauth_or_credential_access`
- `browser_automation`
- `generic_calendar_cleanup`
- `repo_b_runtime_execution`
- `broad_private_content_scraping`

## Calendar Posture
- Calendar cleanup is not started generically.
- Calendar normalization should only happen in a future scoped workflow that needs calendar context.

## Next Safe Lane
- `Cassandra Draft Review Packet v0`
