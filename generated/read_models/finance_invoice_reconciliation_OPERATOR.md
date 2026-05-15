# Finance Invoice Helper Reconciliation v0

## Source
- Repo B path: `/home/openclaw_external/openclaw-runtime`
- Repo B commit: `839e445fc64f181234042b410ecd7b41bb2fe149`
- Canonical status: `non_canonical_legacy`

## Counts
- Finance candidates: 51
- Safe source reviewed: 51
- High-risk candidates: 46
- Blocked/no-go candidates: 0
- Work Board cards: 3

## Top Candidate To Port/Wrap
- `autonomy_mode.py` reuse=candidate_to_port risk=high: Potentially reusable billing_tracking, budget_tracking, email_draft_support concepts after operator review.
- `chief_file_io.py` reuse=candidate_to_port risk=high: Potentially reusable billing_tracking, report_generation concepts after operator review.
- `chief_phone_brain.py` reuse=candidate_to_port risk=high: Potentially reusable billing_tracking, client_payment_status, email_draft_support, evidence_gathering, invoice_drafting, ledger_reconciliation, report_generation concepts after operator review.
- `chief_nli.py` reuse=candidate_to_port risk=low: Potentially reusable billing_tracking, budget_tracking, email_draft_support, ledger_reconciliation concepts after operator review.
- `start_openclaw_brains.sh` reuse=candidate_to_port risk=low: Potentially reusable billing_tracking, evidence_gathering concepts after operator review.

## Reference-Only Items
- `autonomy_qualification.py` risk=high: Potentially reusable budget_tracking, report_generation concepts after operator review.
- `chief_cpa_brain.py` risk=high: Deduction category checklist and CPA evidence prompts as reference-only guarded prompts.
- `polish_loop/tasks/cas-009-morning-sovereign-briefing.md` risk=low: Potentially reusable email_draft_support, evidence_gathering, report_generation concepts after operator review.
- `polish_loop/tasks/hitl-003-future-action-queue-api.md` risk=low: Potentially reusable unknown concepts after operator review.
- `polish_loop/tasks/sys-004-architectural-cleanup.md` risk=low: Potentially reusable evidence_gathering concepts after operator review.

## First Safe Workflow Proposal
- Title: Finance Invoice Helper v0 - Invoice/Receivables Evidence Packet Builder
- Purpose: Turn an operator finance request into a reviewable invoice/receivables evidence packet, checklist, and draft work packet without sending email, scraping banks, or claiming truth.
- Next safe move: Ask the operator for one receivable or invoice target and build a metadata-only evidence packet/work packet before any real invoice work.
- Policy: proposal-only; no invoice send, email send, bank access, tax filing, or financial truth claim.

## Evidence Requirements
- `approved_receipt_or_note` allowed=True: Approved receipt, note, or bounded excerpt that supports the invoice or payment status.
- `operator_invoice_fact` allowed=True: Operator-supplied client/project, service description, amount, and date/range.
- `bank_portal_scrape` allowed=False: Bank or payment-portal scraping is blocked in v0.
- `email_send` allowed=False: Emails may be drafted as context later, but sending is blocked and requires separate approval.
- `tax_or_legal_raw_body` allowed=False: Raw tax/legal/client document bodies are blocked unless a future approved lane explicitly allows a bounded excerpt.

## Work Board Linkage
- `wbcard_0ad11f9f87705b71bed6` planned: Build Finance Invoice Helper v0 proposal
- `wbcard_f2d37b1dce085eda7194` needs_review: Review Repo B finance helpers
- `wbcard_b3403ca433adbd4f8b37` needs_review: Review receivables evidence requirements

## Operator Burden Reduction
- Makes legacy finance helper logic queryable instead of relying on memory.
- Separates useful invoice/receivable patterns from unsafe direct sends, writes, and model calls.
- Defines the first practical finance workflow as an evidence packet/work packet, not a live finance bot.

## Authority Boundary
- `finance_execution_allowed`: `false`.
- `invoice_send_allowed`: `false`.
- `email_send_allowed`: `false`.
- `bank_access_allowed`: `false`.
- `tax_filing_allowed`: `false`.
- `external_api_allowed`: `false`.
- `raw_private_ingest_allowed`: `false`.
- `operator_approval_required`: `true`.
- `financial_truth_claimed`: `false`.
