# St. Anne's Artifact Locator and Truth-Drift Design

Date: 2026-07-16

## Problem

The June 2026 St. Anne's workbook is the invoice-content source of truth and
contains seven $125 services totaling $875. The derived work-log read model
reports zero business-confirmed events. The existing invoice response therefore
describes the work-log state accurately but does not disclose the more important
workbook-to-mirror drift.

The operator also needs a reusable way to locate the correct invoice PDF by
client and service period, verify its workbook provenance, collapse duplicate
copies by content hash, and exclude quarantined variants.

## Chosen Approach

Use a deterministic, manifest-first locator and a read-only reconciliation
preview. The workbook remains authoritative for invoice content. Work-log and
SQLite data remain one-way mirrors and are never allowed to overwrite workbook
facts.

Two rejected approaches are:

- Broad filesystem scan plus automatic synchronization. It is fast to prototype
  but has weak provenance and could turn stale copies into business truth.
- PDF text or OCR as invoice truth. It is useful as a verification fallback but
  loses workbook sheet, formula, and cell provenance.

## Components

### Deterministic artifact locator

The locator accepts normalized `client_ref` and `service_period`. It searches
only configured invoice artifact roots and Mac handoff roots. It prefers package
directories with `invoice_manifest.json`, rejects paths under
`.openclaw_scope_quarantine`, validates client and period fields, verifies the
declared workbook and PDF hashes, and groups byte-identical PDFs under one
canonical candidate.

The result is a local-only receipt containing candidate identity, canonical
paths, duplicate paths, manifest provenance, workbook source sheet, invoice
number, amount, status, and send-receipt presence. It does not open providers,
send files, or grant attachment authority.

### Agentic miss fallback

If deterministic roots contain no valid candidate, a bounded local model may
rank already-enumerated metadata-only misses and suggest additional allowlisted
subpaths. It may not widen roots, read arbitrary user directories, accept a
quarantined candidate, or override failed hash/provenance checks. Deterministic
verification remains the final decision maker.

### Workbook-to-worklog drift detector

The reconciler reads the canonical manifest and workbook in read-only mode,
selects the declared service-period sheet, extracts the invoice number, line
items, dates, descriptions, quantities/rates, and label-anchored total, then
compares those facts with the existing St. Anne's hygiene/work-log read models.

It emits a drift receipt with:

- workbook line-item count and total;
- mirrored business-confirmed event count;
- matched and unmatched facts;
- `DRIFT_DETECTED`, `IN_SYNC`, or `SOURCE_UNAVAILABLE` status;
- one next safe action;
- false authority/performed flags.

The first version stages a reconciliation proposal only. A later, separately
gated operator action can confirm that the workbook is right and materialize
derived work-log events. No automatic workbook, SQLite, ledger, paid-state, or
send mutation is permitted.

### Operator response

When drift is present, the St. Anne's response says the dry-run passed and
nothing was sent, then names both truths: the workbook has seven June services
for $875 while the work-log mirror has zero confirmed events. The missing item
becomes `Reconcile workbook billables into the work-log mirror`, not `enter
billable sessions`.

## Failure Handling

- Missing or malformed manifest: candidate is invalid, with a reason.
- Hash mismatch: candidate is invalid and never canonical.
- Missing workbook or declared sheet: reconciliation fails closed.
- Workbook parse failure: no facts are inferred from the PDF.
- Multiple non-identical valid candidates: return `AMBIGUOUS`, never pick by
  modification time alone.
- Missing work-log read model: report mirror unavailable rather than zero.

## Tests

- Locate June by client and period from a manifest-backed handoff.
- Exclude quarantine paths.
- Collapse identical PDF copies by SHA-256.
- Reject manifest hash mismatch and ambiguous non-identical candidates.
- Read the declared June workbook sheet and extract seven services totaling
  $875 without mutation.
- Detect seven workbook services versus zero mirror events.
- Render exact operator message with dry-run, no-send, and drift facts.
- Assert all external-action and mutation proof flags remain false.

## Promotion Gate

Promotion requires focused locator/reconciler tests, the owning workflow suites,
the canonical composition gate, a local exact-message replay, and Fable
concurrence. Live attachment delivery and any mirror mutation remain outside
this change.
