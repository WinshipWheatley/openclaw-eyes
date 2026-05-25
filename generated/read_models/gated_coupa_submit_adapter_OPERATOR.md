# Gated Coupa Submit Adapter

## Summary
OpenClaw now has a gated Coupa submit readiness rail. It can prove why a submit is blocked or dry-run ready, but it does not open Coupa, open a browser, reveal secrets, or submit.

## Capital Hilton
- Missing PO status: SUBMIT_BLOCKED_MISSING_PO
- Missing PO fix: Provide, attach, or confirm the Coupa PO/reference as a protected/source ref, then rerun the submit readiness check.
- Dry-run status: SUBMIT_DRY_RUN_READY
- Dry-run message: OpenClaw dry-ran the Capital Hilton Coupa submit package. All modeled proof, secret, and approval refs are present, but nothing was opened, submitted, or called.
- Provider missing status: SUBMIT_BLOCKED_MISSING_PROVIDER
- Provider missing fix: Connect a future gated Coupa/browser adapter after exact approvals, protected secret refs, and proof rails are complete.

## Blockers
- GENERIC_APPROVAL_USED: Generic approval is blocked for Coupa submit.
- EXACT_APPROVAL_MISSING: Exact approval is missing.
- GUARDIAN_APPROVAL_MISSING: Guardian approval is missing.
- PO_REFERENCE_MISSING: Coupa PO/reference is missing.
- PO_REFERENCE_UNCONFIRMED: Coupa PO/reference must be confirmed.
- INVOICE_VALUES_MISSING: Invoice values are missing.
- VALUE_MISMATCH: Invoice value mismatch blocks submit.
- ARTIFACT_REF_MISSING: Invoice artifact ref is missing.
- ARTIFACT_HASH_MISSING: Artifact hash/fingerprint is missing.
- SECRET_REF_MISSING: Protected secret ref is missing.
- PROVIDER_ADAPTER_MISSING: Provider adapter is missing.
- RAW_CREDENTIAL_INCLUDED: Raw credential is blocked.
- RAW_PO_EXPOSED: Raw PO/reference exposure is blocked.
- BROWSER_ATTEMPTED_WITHOUT_GATES: Browser attempt without gates is blocked.
- SUBMIT_ATTEMPTED_WITHOUT_GATES: Submit attempted without gates.
- PROVIDER_CALLED_IN_TEST: Provider calls are blocked in tests.
- EXTERNAL_ACTION_ATTEMPTED: External action is blocked.
- UNKNOWN_FAIL_CLOSED: Unknown state fails closed.

## Boundary
No Coupa access, no Coupa submit, no browser, no portal login, no provider call, no secret reveal, no payment action, no external action, no workflow run, no agent dispatch, no credential handling, no raw credential, no raw-body ingestion.
