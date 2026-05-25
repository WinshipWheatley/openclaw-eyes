# Chat Workflow Run State + Visual Event Feed v0

ELIOPERATOR: Chat can show workflow progress only when backend readback supports it.

- Phase: `MISSING_INFO_NEEDED`.
- Workflow: `invoice_delivery_workflow`.
- Client: `capital_hilton`.
- Truth status: `DRAFT_UNDERSTANDING_NOT_TRUTH`.
- External actions locked: `True`.

## What This Enables

The operator can see what was captured, what is missing, what is locked, and what proof is required next.

## Current State

Known:
- 4 dates at $400 each working basis
- Excel/PDF companion invoice desired
- Annette contact candidate
- Coupa/PO payment rail candidate
- invoice should be saved for records

Missing:
- exact Coupa PO/reference
- confirmation Annette is correct contact
- final invoice artifact/hash
- Guardian approval
- send/submit receipts

Locked:
- email send
- Coupa access/submit
- browser
- approval request
- invoice generation
- attachment
- payment state update

## Visual Events

### Understanding captured
- I got the readback. OpenClaw understands the Capital Hilton invoice workflow draft.
- The invoice workflow draft is captured for operator review.

### Needs input
- To make this runnable, I still need the Coupa PO/reference, Annette confirmation, final invoice artifact, and Guardian approval.
- The workflow is not runnable until the missing pieces are proven.
- Missing: exact Coupa PO/reference
- Missing: confirmation Annette is correct contact
- Missing: final invoice artifact/hash
- Missing: Guardian approval
- Missing: send/submit receipts

### Execution locked
- Nothing external can happen yet. No email, Coupa, browser, approval, or payment update is active.
- External work is locked behind proof and approval gates.
- Locked: email send
- Locked: Coupa access/submit
- Locked: browser
- Locked: approval request
- Locked: invoice generation
- Locked: attachment
- Locked: payment state update

### INVOICE SENT
- This completion target is blocked until proof receipts exist.
- Future completion target only; do not render as achieved.
- Missing: Guardian approval receipt
- Missing: email send receipt
- Missing: Coupa submit/verification receipt if required
- Missing: dated invoice artifact/hash
- Missing: payment tracking update receipt
- Locked: Proof receipts do not exist yet.

## Completion Target

- Headline: INVOICE SENT
- Allowed now: `False`.
- Blocked reason: Proof receipts do not exist yet.

## Boundary

- This read-model does not run a workflow, create a package, dispatch an agent, call a model, request approval, draft or send email, access Coupa, open a browser, generate an invoice, create an attachment, or update payment tracking.
- Completion remains blocked until proof receipts exist.

Next safe move: Show the visual events to the operator and ask whether the understanding looks right.
