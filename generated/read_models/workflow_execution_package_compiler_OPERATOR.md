# Workflow Execution Package Compiler v0

ELIOPERATOR: This turns 'make it happen' into a governed package plan. It does not execute anything.

## What This Enables

OpenClaw can show what is known, what is missing, which worker packages are needed, and what proof is required before completion.

## What This Does Not Do Yet

It does not run packages, dispatch agents, send email, access Coupa, open a browser, generate invoices, request approvals, attach files, or update payment tracking.

## Capital Hilton Readiness

I can plan the Capital Hilton invoice workflow, but it is not runnable yet. The PO/reference, contact confirmation, artifact hash, approval, and receipts are still missing.

## Missing Now

- exact Coupa PO/reference
- confirmation Annette is correct contact
- final Winship-branded Excel/PDF artifact/hash
- Guardian approval
- send/submit receipts

## Blocked

- email send
- Coupa access/submit
- browser automation
- approval request
- invoice generation if artifact rail not ready
- attachment if artifact hash missing
- payment tracking update

## Package Chain

- PC_BACKEND_VALIDATION_PACKAGE: Confirm current dates/rate/subtotal and missing delivery facts from deterministic read-models. (`PACKAGE_PLAN_READY_NOT_EXECUTABLE`)
- MAC_ARTIFACT_PREP_PACKAGE: Prepare or verify the Winship-branded Excel/PDF invoice artifact when an approved Mac artifact rail exists. (`BLOCKED_MISSING_INPUT`)
- PROTECTED_EVIDENCE_PACKAGE: Reference proof/source metadata without exposing private bodies. (`PACKAGE_PLAN_READY_NOT_EXECUTABLE`)
- DRAFTING_AGENT_PACKAGE: Prepare future email draft language to Annette with an artifact reference. (`BLOCKED_MISSING_INPUT`)
- GUARDIAN_APPROVAL_PACKAGE: Request approval before any future external send or submit adapter runs. (`BLOCKED_PENDING_APPROVAL`)
- POST_OFFICE_HANDOFF_PACKAGE: Route package/readback metadata through the cross-surface handoff registry when future handoff is approved. (`PACKAGE_PLAN_READY_NOT_EXECUTABLE`)
- FINAL_READBACK_PACKAGE: Produce the completion proof card only after required receipts exist. (`BLOCKED_PENDING_PROOF`)

## Gates

- operator confirms missing facts
- artifact hash exists before attachment
- Guardian approval before external send/submit
- Coupa PO/reference proof before Coupa submit
- send/submit receipts before completion

## Future Completion Target

- Headline: INVOICE SENT
- Completion allowed now: `False`
- Blocked reason: Proof receipts do not exist yet.

Proof required before completion:

- Coupa invoice generated/submitted from PO, if required and proven.
- Email sent to Annette with Winship-branded Excel/PDF invoice attached.
- Invoice artifact saved with today's date.
- Last invoice date recorded for future invoice range.
- Send/submit receipts attached.
- Payment tracking state updated.

## Boundary

No package execution, agent dispatch, tool execution, workflow run, email draft/send, Coupa access/submit, browser, invoice generation, attachment, approval request, payment tracking write, external action, credential handling, raw-body ingestion, Mac sync/import, Swift change, or push was added.

Next safe move: Show readiness, missing pieces, and package plan chain to the operator before any future package send.
