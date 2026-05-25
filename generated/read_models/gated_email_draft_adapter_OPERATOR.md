# Gated Email Draft Adapter

## Summary
OpenClaw can prepare Capital Hilton email draft metadata and a bounded local .eml review artifact. Nothing is sent, no live Gmail/Mail draft is created, and future send remains separately gated.

## Capital Hilton Local Draft
- Status: LOCAL_DRAFT_ARTIFACT_READY
- Message: OpenClaw prepared the Capital Hilton email draft package for review. Nothing has been sent. The draft still needs future approval and send receipts before a future send adapter can be approved.
- Recipient: recipient_ref:annette_capital_hilton_candidate
- Attachment: email_attachment_ref:capital_hilton_pdf_2026-05-25
- Next: Review the local .eml artifact and keep send gates locked.

## Metadata Draft
- Status: METADATA_DRAFT_READY
- Message: OpenClaw prepared the Capital Hilton email draft metadata for review. Nothing has been sent or created in Gmail/Mail.

## Local Artifacts
- bounded_local_eml_ref:generated/email_drafts/gated_email_draft_adapter_v0/CAPITAL_HILTON_INVOICE_FOLLOWUP_REVIEW_DRAFT_2026-05-25.eml sha256:54256e1bf630486c37860b097cf56dfac4a208bb9f30eae6f3d4b276aba7537a

## Blocked
- SEND_ATTEMPTED: Email send is blocked.
- RECIPIENT_MISSING: Recipient ref is missing.
- DRAFT_BODY_MISSING: Draft body is missing.
- ATTACHMENT_REF_MISSING: Attachment ref is missing.
- ATTACHMENT_HASH_MISSING: Attachment hash/fingerprint is missing.
- PROVIDER_ADAPTER_MISSING: Live draft provider is unavailable.
- APPROVAL_MISSING: Approval is missing.
- RAW_EMAIL_ADDRESS_EXPOSED: Raw email address exposure is blocked.
- RAW_ATTACHMENT_BODY_INCLUDED: Raw attachment body is blocked.
- GMAIL_SEND_ATTEMPTED: Gmail send is blocked.
- MAIL_SEND_ATTEMPTED: Mail send is blocked.
- EXTERNAL_ACTION_ATTEMPTED: External action is blocked.
- UNKNOWN_FAIL_CLOSED: Unknown draft adapter state fails closed.

## Boundary
No email send, no Gmail send, no Mail send, no attachment send, no Coupa access, no browser, no approval execution, no workflow run, no agent dispatch, no external action, no credential handling, no raw attachment body, no raw-body ingestion.
