# Gated Email Send Adapter

## Summary
OpenClaw now has a gated email send readiness rail. It can prove why a send is blocked or dry-run ready, but it does not send or call providers.

## Capital Hilton
- Missing approval status: SEND_BLOCKED_MISSING_GATES
- Missing approval fix: Create the Guardian approval packet and exact operator approval receipt for this package, then rerun the send readiness check.
- Dry-run status: SEND_DRY_RUN_READY
- Dry-run message: OpenClaw dry-ran the Capital Hilton email send package. All modeled approval and proof refs are present, but nothing was sent and no provider was called.
- Provider missing status: SEND_BLOCKED_MISSING_PROVIDER
- Provider missing fix: Connect a future gated provider adapter after exact approvals and proof rails are complete.

## Blockers
- GENERIC_APPROVAL_USED: Generic approval is blocked for email send.
- EXACT_APPROVAL_MISSING: Exact approval is missing.
- GUARDIAN_APPROVAL_MISSING: Guardian approval is missing.
- RECIPIENT_UNCONFIRMED: Recipient must be confirmed.
- DRAFT_NOT_REVIEWED: Draft must be reviewed.
- ATTACHMENT_REF_MISSING: Attachment ref is missing.
- ATTACHMENT_HASH_MISSING: Attachment hash/fingerprint is missing.
- PROVIDER_ADAPTER_MISSING: Provider adapter is missing.
- CREDENTIAL_REF_MISSING: Provider credential ref is missing.
- RAW_EMAIL_ADDRESS_EXPOSED: Raw email address exposure is blocked.
- RAW_ATTACHMENT_BODY_INCLUDED: Raw attachment body is blocked.
- SEND_ATTEMPTED_WITHOUT_GATES: Send attempted without gates.
- SEND_PROVIDER_CALLED_IN_TEST: Provider calls are blocked in tests.
- EXTERNAL_ACTION_ATTEMPTED: External action is blocked.
- UNKNOWN_FAIL_CLOSED: Unknown state fails closed.

## Boundary
No email send, no Gmail send, no Mail send, no SMTP send, no provider send call, no attachment send, no external action, no workflow run, no agent dispatch, no credential handling, no raw attachment body, no raw-body ingestion.
