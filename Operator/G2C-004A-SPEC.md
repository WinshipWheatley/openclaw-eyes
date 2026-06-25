# Task G2C-004A: ExpectedReceivableRecord Contract Correction

## Acceptance Criteria
**Version / Hash:** 20260624-G2C004A-v1

1. **Required Fields:** `receivable_id`, `receivable_version_id`, `invoice_id`, `invoice_version_id`, `counterparty_ref`, `lifecycle_state`, `expected_minor_units`, `currency_iso`, `due_date_iso`, `recognized_utc_iso`, `idempotency_key`, `source_ref`.
2. **Optional Fields:** `supersedes_receivable_version_id`, `resolution_ref`.
3. **Lifecycle States:** Exactly `open`, `disputed`, `satisfied`, `written_off`, `cancelled`.
4. **Resolution Requirement:** Terminal states (`satisfied`, `written_off`, `cancelled`) require a non-empty `resolution_ref`.
5. **Amount Validation:** `type(expected_minor_units) is int` and value > 0.
6. **Currency Validation:** Exactly three uppercase letters.
7. **Date Validation:** Strict ISO parsing for `due_date_iso` and `recognized_utc_iso`. `recognized_utc_iso` must be timezone-aware (UTC).
8. **Immutability & Constraints:** Backward-only supersession. Exact linkage to invoice version. No stored partially_paid or overdue state. No payment/workbook logic.

## Target Files
- `ar_expected_receivable_record.py`
- `tests/test_ar_expected_receivable_record.py`
