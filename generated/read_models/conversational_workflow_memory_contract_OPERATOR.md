# Conversational Workflow Memory Contract v0

ELIOPERATOR: Chat can be the input layer for repeatable workflows. OpenClaw proposes the structure, the operator reviews it, and receipts decide what becomes true.

## What This Enables

The operator can describe a workflow once; OpenClaw proposes blocks, questions, roles, gates, artifacts, and proof requirements.

## Generic Pattern

- Operator explains the workflow.
- OpenClaw proposes blocks, questions, gates, roles, artifacts, and proof requirements.
- Operator confirms or corrects the chain before it becomes procedure memory.
- A later do-it request creates a governed run plan, not instant external action.
- Agents operate through roles, packages, permissions, and gates.
- Completion requires proof receipts.

## Generic Blocks

- Capture the goal: `OPERATOR_REVIEW_REQUIRED`
- Identify inputs and unknowns: `FILLABLE_NOW`
- Prepare required artifacts: `GATED`
- Review drafts or outputs: `GATED`
- Approval gate: `GATED`
- External action if explicitly approved: `BLOCKED`
- Proof-backed completion readback: `BLOCKED`

## Capital Hilton Proof Example

- Procedure: `How Capital Hilton invoices get paid`.
- The Annette / Excel PDF / Coupa PO explanation becomes a candidate chain, not authority.
- Proposed blocks:
- Confirm performance dates: `KNOWN_FROM_LOCAL_RECEIPTS`
- Confirm rate: `KNOWN_FROM_LOCAL_RECEIPTS`
- Generate/update Excel-branded companion invoice PDF: `FUTURE_GATED_STEP`
- Confirm PO/Coupa payment rail: `NEEDS_OPERATOR_CONFIRMATION_OR_PROOF`
- Confirm Coupa supplier-portal invoice from PO: `NEEDS_OPERATOR_CONFIRMATION_OR_PROOF`
- Confirm invoice destination/contact: Annette candidate: `NEEDS_OPERATOR_CONFIRMATION_OR_PROOF`
- Prepare email draft to Annette: `NEEDS_OPERATOR_CONFIRMATION_OR_PROOF`
- Attach Excel-generated PDF invoice: `FUTURE_GATED_STEP`
- Guardian approval request: `FUTURE_GATED_STEP`
- Operator approval: `FUTURE_GATED_STEP`
- Send email: `BLOCKED_EXTERNAL_AUTHORITY`
- Submit/verify Coupa invoice if required and gated: `BLOCKED_EXTERNAL_AUTHORITY`
- Save dated invoice artifact: `FUTURE_GATED_STEP`
- Record sent/payment tracking state: `FUTURE_GATED_STEP`
- Completion proof readback: `FUTURE_TARGET_ONLY`

## Future Completion Target

- Headline: `INVOICE SENT`.
- Status now: future target, not current fact.
- Required proof: email send receipt, Coupa submit or not-required proof, final PDF hash, approval receipts, and payment tracking receipt.

## Boundary

- No live chat parser, model call, procedure write, workflow run, or agent dispatch was added.
- No Cassandra draft or Guardian approval was created.
- No email draft/send, Coupa access/submit, invoice generation, attachment, or payment tracking write occurred.
- No credentials, private bodies, browser, Gmail, Telegram, Mac sync/import, Swift change, network, or push occurred.

Next safe move: Use this read-model as the generic contract; build a future reviewed procedure writer separately.
