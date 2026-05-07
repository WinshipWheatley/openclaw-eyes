# Live Arts Invoice Reconciliation Breadcrumb

## 1. Purpose
This document captures the current Live Arts / speaker-rental / service-work invoice reconciliation situation. It serves as a product-design stress test for the future Cassandra "chase money" / Invoice Artifact v0 lane. This is a pointer document to ensure future OpenClaw work can build toward handling this complexity safely.

## 2. Product Principle: Build for Messy Reconciliation
If OpenClaw/Cassandra can handle this messy invoice/reconciliation case, simple invoices become easy. Simple invoices just need client, date, service, rate, total, due date, and payment method. The Live Arts case is hard because it includes:
- Ambiguous payment allocation
- Mixed categories (rental, tech services, live music, access/let-in, file/export errand, all-day event support)
- Missing dates/details
- Relationship-sensitive tone
- Payer/contact mismatch
- Unpaid recurring rental
- Unclear rate policy
- Prior deposits that should not be blindly credited
- Approval-before-send needs
- Draft vs. actual invoice separation

## 3. Why this matters for Cassandra / Chase-Money Lane
- Cassandra chase-money lane should eventually distinguish invoice categories (rental, tech services, live music, access/let-in, file/export errands, all-day event support).
- System should track:
  - Client / payer profile
  - Contact persons vs check/payment authority
  - Event/date
  - Service category
  - Rate basis
  - Known deposits
  - Payment allocation status
  - Ambiguity / unresolved classification
  - Relationship sensitivity
  - Approval-before-send
  - Invoice artifacts
  - Payment follow-up history
- System should not automatically send anything.
- System should generate drafts/reconciliation packets first.
- Existing prior payments should be allowed to remain "unallocated pending clarification."
- System should help prevent scope creep by identifying when a short-call minimum is being used for extended work.
- Actor Registry / context export work matters here because Cassandra or another billing actor should only receive scoped, approved, non-sensitive context and should produce receipts/drafts, not actions.

## 4. Current Factual Working Ledger
- **Speaker rental**:
  - $100/month.
  - Speakers are still at The Studio / Live Arts Maryland, available for use.
  - No explicit cancellation after Mar. 5, 2025.
  - Billing cycle around the 16th.
  - Current rough draft uses July 16, 2025 – May 16, 2026 (10 months × $100/month = $1,000).
- **Known 2025 deposits (unallocated pending clarification)**:
  - $300 deposited Mar. 11, 2025
  - $450 deposited May 9, 2025
  - $750 deposited Jul. 15, 2025
- Operator reports zero deposits in at least the last 8 months.
- **Service items currently known**:
  - Papa Rapper event sound services: $125
  - St. Anne’s at The Studio (Jan. 23) live music / tech services: $125
  - Tech service (Feb. 18): $125
  - Additional prior service work (date/details pending): $125
  - Studio access / let-in for recital group (Apr. 25): $50
  - Piano recital support (Apr. 26, 8:15 AM–4:00 PM): $300
  - Laptop pickup, transport, and file export support (May 6): $125
  - Maryland Hall orchestra concert support: date/details pending, TBD
  - Talent Machine all-day support: date/details pending, TBD
- **Service total (excluding TBD)**: $975
- **Important rate insight**:
  - $125 should be treated as a short-call/service minimum, not an all-day event rate.
  - Simple access / let-in may be $50.
  - Extended or all-day support needs a separate rate or negotiated event fee.

## 5. Rough Draft Invoice A: Speaker Rental
**ROUGH DRAFT — DO NOT SEND WITHOUT OPERATOR REVIEW**

```text
INVOICE — SPEAKER RENTAL

From:
Winship Wheatley / Winship Live
443-758-4913
winshiplive@gmail.com

To:
Live Arts Maryland / The Studio
Attn: Dane Krich / Draper

Invoice Date: May 6, 2026
Invoice #: WL-2026-SR-001
Due: Upon receipt

Description:
Speaker system rental for The Studio / Live Arts Maryland

Billing period:
July 16, 2025 – May 16, 2026

Rate:
$100/month

Quantity:
10 months

Total due:
$1,000.00

Notes:
The speakers have remained at The Studio and available for use during this period. Prior 2025 payments are currently left unallocated pending clarification from Live Arts Maryland regarding which payments applied to speaker rental versus tech/service work.

Payment:
Zelle: 443-758-4913
[Add check/ACH details if desired]
```

## 6. Rough Draft Invoice B: Service Work Reconciliation
**ROUGH DRAFT — DO NOT SEND WITHOUT OPERATOR REVIEW**

```text
INVOICE — SERVICE WORK RECONCILIATION

From:
Winship Wheatley / Winship Live
443-758-4913
winshiplive@gmail.com

To:
Live Arts Maryland / The Studio
Attn: Dane Krich / Draper

Invoice Date: May 6, 2026
Invoice #: WL-2026-SVC-001
Due: Upon receipt

Line items:
- Papa Rapper event — sound services — $125.00
- St. Anne’s at The Studio — January 23 — live music / tech services — $125.00
- Tech service — February 18 — $125.00
- Additional prior service work — date/details pending confirmation — $125.00
- Studio access / let-in for recital group — April 25 — $50.00
- Piano recital support — April 26, 8:15 AM–4:00 PM — extended event support — $300.00
- Laptop pickup, transport, and file export support — May 6 — $125.00
- Maryland Hall orchestra concert support — date/details pending confirmation — TBD
- Talent Machine all-day support — date/details pending confirmation — TBD

Current total due, excluding TBD items:
$975.00

Notes:
This invoice is a reconciliation of outstanding service work based on current records. Some dates/details remain pending confirmation, and it can be reconciled against Live Arts Maryland’s records if anything has already been allocated differently.

Going forward, rates should be clarified before each event so expectations are clean on both sides. The $125 service rate should be treated as a short-call/service minimum, not an all-day event rate.

Payment:
Zelle: 443-758-4913
[Add check/ACH details if desired]
```

## 7. Ambiguities / Operator Follow-Up Needed
- Clarify 2025 deposits allocation.
- Confirm exact dates/details for "additional prior service work."
- Confirm dates/details for Maryland Hall orchestra concert support.
- Confirm dates/details for Talent Machine all-day support.
- Discuss and agree on going-forward rate policies for short-call vs. extended/all-day event support.
- Present these drafts as a reconciliation tool to establish a baseline before formal invoicing.

## 8. Existing Invoice Tool Reality Check
- Existing invoice/billing tools appear to exist (`chief_invoice_brain.py`, `invoice_generator.py`, `chief_billing_brain.py`, `invoice_tracker.csv`).
- However, they are **not safe** for unattended real invoice generation:
  - `reportlab` missing from active `.venv`.
  - `requests` missing from active `.venv`.
  - `chief_invoice_brain.py` misparsed “Tomorrow” as `deposit_amount`, causing `ValueError`.
- The current safe path for real invoices is manual/semi-manual drafting with operator review.

## 9. Future Invoice Artifact v0 / Billing Bridge Implications
- A future repo lane should be built for "Invoice Artifact v0 / Billing Bridge", but **only after** current backend/source-set work is clean.
- This lane must incorporate the "messy reconciliation" principles and relationship-sensitive design described above.

## 10. Hard Boundaries
- Do not inspect private roots, email files, Gmail APIs, calendar APIs, credentials, env files, `.chief.env`, API keys, tokens, or private client/legal data.
- Do not create actual invoices as final artifacts from the system yet.
- Do not send emails automatically.
- Do not install missing dependencies.
- Do not run `chief_invoice_brain.py` in its current state.
- Do not modify existing invoice/billing code.

## 11. Next Safe Action
The next safe action is to keep this document as a planning breadcrumb, manually share these drafts with the client to establish a reconciliation baseline, and keep future Cassandra "chase money" development strictly separate until the core backend data contract and actor registry are fully stabilized and clean.
