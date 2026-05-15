# OpenClaw Finance Invoice Helper Reconciliation v0

Finance Invoice Helper Reconciliation maps Repo B finance/invoice candidates into the current OpenClaw governed workflow.

It exists to reduce operator burden around real invoice and receivable work. The operator should not have to remember which old billing, invoice, CPA, finance, or budget helpers existed in Repo B, nor guess which parts are reusable and which parts are unsafe. This lane makes that map queryable and proposes the first safe Finance World workflow.

## Source

- Canonical core repo: `/home/openclaw`
- Non-canonical Repo B path: `/home/openclaw_external/openclaw-runtime`
- Expected Repo B remote: `WinshipWheatley/openclaw-runtime`
- Repo B posture: `non_canonical_legacy`
- Import posture: `metadata_scanned_only` or `safe_source_reviewed`

Repo B finance code is not run, imported, promoted, or trusted as financial truth.

## Reviewed Candidates

The lane safely reviews bounded source for the known finance helpers when present:

- `chief_billing_brain.py`
- `chief_invoice_brain.py`
- `chief_financial_brain.py`
- `chief_cpa_brain.py`
- `budget_tracker.py`

It also carries forward Repo B Runtime Intake finance candidates as metadata-only rows.

For each candidate it records:

- purpose
- expected inputs
- expected outputs
- external service references
- file I/O posture
- sensitive data risk
- direct execution risk
- reusable business logic
- obsolete or unsafe assumptions
- current OpenClaw architecture mapping
- future home
- reuse policy
- risk level
- burden-reduction category

No full raw source bodies, finance records, bank data, tax documents, legal/client raw data, secrets, tokens, or credential files are stored.

## Classification

Capability kinds:

- `invoice_drafting`
- `billing_tracking`
- `receivable_tracking`
- `budget_tracking`
- `cpa_tax_support`
- `evidence_gathering`
- `client_payment_status`
- `reimbursement_tracking`
- `ledger_reconciliation`
- `email_draft_support`
- `report_generation`
- `unknown`

Future homes:

- `finance_world_core`
- `business_ops_module`
- `evidence_helper`
- `invoice_helper`
- `cpa_support_reference`
- `project_capsule_candidate`
- `client_template_candidate`
- `reference_only_legacy`
- `blocked_no_go`
- `unknown_review`

Reuse policies:

- `candidate_to_port`
- `candidate_to_wrap`
- `reference_only`
- `blocked_no_go`
- `needs_operator_review`
- `current_equivalent_exists`
- `superseded_candidate`

Risk reasons include direct writes, external sends, env references, payment/bank adjacency, tax sensitivity, client sensitivity, missing receipt paths, broad scans, stale architecture, and unknown.

## First Safe Workflow Proposal

The first proposed Finance lane is:

`Finance Invoice Helper v0 - Invoice/Receivables Evidence Packet Builder`

Purpose:

- collect operator-provided invoice/receivable facts
- link only approved evidence
- produce a reviewable checklist and draft work packet
- surface the next safe finance move in Work Board/Mission Control later

Allowed evidence:

- operator-provided client/project and service metadata
- approved receipt or note references
- bounded approved excerpts
- manually supplied payment confirmation metadata
- existing safe OpenClaw read-model metadata

Disallowed evidence/actions:

- raw bank portal scraping
- unapproved tax/legal/client raw documents
- secrets, env files, and private roots
- automatic email sends
- invoice finalization for sending
- financial truth claims without evidence
- ledger modifications

Outputs are proposal-only:

- Finance Work Board card
- evidence requirements checklist
- draft invoice context packet
- draft follow-up context packet
- approval-gated next safe move

## Work Board Linkage

If enabled, the builder creates metadata-only Work Board cards:

- Review Repo B finance helpers
- Build Finance Invoice Helper v0 proposal
- Review receivables evidence requirements

These cards are planning/control-plane metadata only. They do not create operator actions, approve work, execute code, send email, write invoices, or modify ledgers.

## Commands

Build reconciliation:

```bash
python3 scripts/build_finance_invoice_reconciliation.py --format operator
```

Query:

```bash
python3 scripts/query_finance_invoice_reconciliation.py --report summary --format operator
python3 scripts/query_finance_invoice_reconciliation.py --report candidates --format operator
python3 scripts/query_finance_invoice_reconciliation.py --report risks --format operator
python3 scripts/query_finance_invoice_reconciliation.py --report workflow --format operator
python3 scripts/query_finance_invoice_reconciliation.py --capability invoice_drafting --format operator
python3 scripts/query_finance_invoice_reconciliation.py --capability receivable_tracking --format operator
```

Export read-model:

```bash
python3 scripts/export_finance_invoice_reconciliation_read_model.py --format operator
```

Generated read-models:

- `generated/read_models/finance_invoice_reconciliation.json`
- `generated/read_models/finance_invoice_reconciliation_OPERATOR.md`

## Authority Boundary

- `finance_execution_allowed=false`
- `invoice_send_allowed=false`
- `email_send_allowed=false`
- `bank_access_allowed=false`
- `tax_filing_allowed=false`
- `external_api_allowed=false`
- `raw_private_ingest_allowed=false`
- `operator_approval_required=true`
- `financial_truth_claimed=false`

## How This Makes the Operator Freer

This lane turns old finance helper code into a concise decision map. It separates reusable invoice/receivable patterns from unsafe direct sends, writes, stale paths, model calls, and tax/client-sensitive assumptions.

The useful next step is not abstract finance infrastructure. It is a bounded Finance Invoice Evidence Packet lane where the operator can provide one real receivable target, OpenClaw can gather approved context, and the system can produce a reviewable draft packet without leaking private data or taking real-world financial action.
