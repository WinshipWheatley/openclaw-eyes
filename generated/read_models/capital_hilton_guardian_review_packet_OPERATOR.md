# Capital Hilton Guardian Review Packet v0

## ELIWINSHIP Summary

Guardian is reviewing whether protected Capital Hilton finance metadata is safe to promote as metadata. Guardian is not reviewing raw files, logging into accounts, approving invoices, or approving send/submit actions.

## What Guardian Reviews

- Proof item ids, answer candidate receipt refs, protected placeholder refs, source-card refs, receipt refs, hash/ref placeholders, redacted metadata labels, and operator descriptions as memory candidates.

## What Guardian Cannot Do

- Approve invoice generation.
- Approve send/submit.
- Access Coupa, browser/OAuth, Gmail/calendar/email, or any account.
- Handle credentials or read raw Excel/PDF/email/finance bodies.
- Write ledgers or approve runtime/tool/model/agent/queue execution.

## Default Review Packets

- `protected_finance_metadata_review_packet`: Validate whether protected finance metadata references are safe to promote.
- `coupa_reference_metadata_review_packet`: Classify Coupa/PO/payment reference metadata without any Coupa login, browser, or session access.
- `ap_route_metadata_review_packet`: Classify recipient/route metadata without raw email body access or sending.
- `tax_vendor_payment_handling_review_packet`: Classify sensitive payment, tax, and vendor handling questions as protected metadata only.
- `future_invoice_generation_review_packet`: Define what would be required before invoice generation could ever be reviewed while keeping invoice generation blocked.

## Metadata Outcomes

- Guardian may recommend metadata promotion, metadata rejection, quarantine, operator escalation, more proof, redaction, or fail-closed.
- Guardian approval is not invoice/action approval. Operator final authority and future security gates remain required for any action class.

## Quarantine Triggers

- credential exposure
- raw body attached or referenced as readable
- Coupa/browser/session material appears
- bank/check/remit data not properly protected
- source ref conflicts with proof item
- authority overclaim
- unknown sensitive surface
- missing source/proof refs
- malformed receipt
- unredacted private/customer material
- worker report claims action authority

## Next Backend Batch Lane

- Prompt 4 will model proof quieting and progress state. It still will not quiet items without proof metadata, valid receipt, or valid rejection reason.
