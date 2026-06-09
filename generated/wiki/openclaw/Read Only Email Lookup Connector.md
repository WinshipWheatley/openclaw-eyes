# Read Only Email Lookup Connector

Status: `OPENCLAW_READ_ONLY_EMAIL_LOOKUP_CONNECTOR_READY`

Defines the governed boundary for `read_only_email_lookup`.

## Current Behavior
- Production lookup requires scoped authority and an external read-only credential setup.
- Missing credentials become a structured setup requirement, not generic failure.
- `test_dry_run` records the query shape without real email access.
- `test_live` can use local fixture evidence but does not become production proof.
- Evidence summaries are redacted and raw bodies are unavailable by default.

## Required Scope
- `https://www.googleapis.com/auth/gmail.readonly`

## Denied
- Send, draft/compose, delete, archive, mark read/unread, label mutation, Gmail UI/browser, Coupa, paid, ledger, workbook/PDF, push/merge, model/tool expansion, and repo secrets.

## Existing Broker Candidate
- Classification: `RESTRICTABLE_BROKER`
- Candidate: `/home/openclaw/google_broker_readonly_wrapper.py`
- Live bridge allowed: `False`
- Fixture/readback mode may be used for test-only redacted evidence.
- Production live bridge remains disabled until denied scopes and repo-local credential paths are removed.
