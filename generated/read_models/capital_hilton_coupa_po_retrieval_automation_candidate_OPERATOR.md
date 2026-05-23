# Capital Hilton Coupa / PO Retrieval Automation Candidate v0

## ELIWINSHIP Summary

Manual lookup is the fallback, not the goal. This contract says the Capital Hilton Coupa / PO lookup should be treated as a future governed automation candidate, while keeping all live access blocked right now.

## What The Candidate Is

- `capital_hilton_coupa_po_reference_retrieval`: retrieve or confirm safe Coupa / PO / payment-reference metadata for `coupa_po_payment_reference_metadata`.
- Current status: `BLOCKED_PENDING_PROTECTED_ACCESS_BROKER` at `STAGE_0_MANUAL_INSTRUCTIONS`.
- Automation goal: future read-only lookup with protected metadata receipts, no credential exposure, no raw portal contents, and no mutation.

## Manual Fallback

- Winship can still manually log in and copy only safe metadata, or confirm no reference exists.
- That manual answer still needs proof metadata, receipts, and Guardian review before it can quiet the proof item.

## Future Trial Ladder

- `manual_reference_capture`: Manual fallback while automation is not authorized.
- `guided_manual_readback`: System gives instructions and captures safe operator-entered metadata.
- `supervised_browser_navigation_preview`: Future supervised navigation shape with operator watching.
- `read_only_lookup_dry_run`: Future proof that portal navigation can find a reference without mutation.
- `protected_credential_broker_trial`: Future high-security broker use without raw credential exposure.
- `autonomous_read_only_retrieval`: Future target: governed read-only retrieval with receipts and stop controls.
- `submission_or_invoice_action`: Explicitly blocked action class in this contract.

## Required Gates Before Automation

- `security_delta_for_external_portal`: `NOT_SATISFIED_CURRENTLY`
- `protected_access_broker_gate`: `NOT_SATISFIED_CURRENTLY`
- `credential_handling_gate`: `NOT_SATISFIED_CURRENTLY`
- `browser_automation_sandbox_gate`: `NOT_SATISFIED_CURRENTLY`
- `read_only_lookup_contract_gate`: `NOT_SATISFIED_CURRENTLY`
- `portal_terms_compliance_gate`: `NOT_SATISFIED_CURRENTLY`
- `guardian_metadata_review_gate`: `NOT_SATISFIED_CURRENTLY`
- `operator_authorization_gate`: `NOT_SATISFIED_CURRENTLY`
- `receipt_and_rollback_gate`: `NOT_SATISFIED_CURRENTLY`
- `no_submission_mutation_gate`: `NOT_SATISFIED_CURRENTLY`

## Stop Conditions

- Login challenge, missing credentials, layout changes, unexpected account pages, submit/mutation controls, raw sensitive data, ambiguous PO/reference, duplicate risk, terms uncertainty, Guardian quarantine, or operator cancellation all stop the workflow and require receipts.

## What Is Blocked Now

- Coupa access, browser automation, network operation, credential handling, portal login/read/write, invoice generation, invoice submission, payment mutation, ledger write, email send, model/tool/agent/queue/runtime execution.

## Why This Helps The Invoice Workflow

- The system can build toward a governed read-only lookup instead of telling Winship to manually log in forever. The next safe move is to define the security delta, protected access broker, read-only lookup receipt, Guardian review, and rollback requirements.
