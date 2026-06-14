# Conversational Workflow Router Readback v0

ELIOPERATOR: This readback is for the Mac chat surface. It shows what OpenClaw understood, what is proposed, what is missing, and what stays locked. It does not execute anything.

- Route mode: `REQUEST_ROUTED`.
- Parse status: `ROUTED_DRAFT_READY`.
- Source request: `/mnt/e/openclaw/mission_control_capture_requests/inbox/mission_control_chat_request_capital_hilton_invoice_workflow_1779667089053_da4719d0757a.json`.

## Cards

### OpenClaw understood
- Goal: prepare the Capital Hilton invoice workflow.
- Invoice basis: 4 dates at $400 each appear to be the working basis.
- Companion invoice: generate a Winship-branded Excel/PDF invoice.
- Destination/contact: Annette appears to be the email/payment follow-up contact.
- Official payment rail: Coupa supplier portal invoice from PO.
- Records: save the generated invoice with today's date for future invoice range tracking.
- Still missing: confirmed Coupa PO/reference, final artifact, approval/send gates.
- External actions: locked.

### Proposed workflow
- 1. Confirm captured dates/rate.
- 2. Generate or update Winship-branded Excel/PDF invoice.
- 3. Confirm/discover Coupa PO/reference.
- 4. Prepare Coupa supplier portal invoice path.
- 5. Prepare email draft to Annette with PDF attached.
- 6. Request Guardian approval.
- 7. Send/submit only after gates.
- 8. Save dated invoice artifact.
- 9. Record proof and last invoice date.
- 10. Track payment state.

### What still needs to be confirmed
- Exact Coupa PO/reference.
- Whether Annette is confirmed as the correct contact.
- Whether the final invoice artifact exists and has a hash.
- Whether Guardian approval exists.
- Whether send/submit receipts exist.

### What is not happening yet
- No email sent.
- No Coupa access.
- No browser opened.
- No invoice submitted.
- No approval requested.
- No payment state changed.

## Operator Choices

- Looks right: available now.
- Edit understanding: available now.
- Store as procedure later: future rail needed.
- Prepare package later: future rail needed.
- Cancel: available now.

## Boundary

- No live LM/model parser was used.
- No agent dispatch, workflow run, procedure memory write, Cassandra draft, or Guardian approval occurred.
- No email, Coupa, browser, invoice generation, attachment, approval request, send, submit, or payment-state change occurred.
- No credentials, raw bodies, network, Mac sync/import, Swift change, or push occurred.

Next safe move: Show cards to the operator and ask whether the understanding looks right.
