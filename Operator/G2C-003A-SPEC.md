# Task G2C-003A: InvoiceRecord Contract Correction

## Acceptance Criteria
**Version / Hash:** 20260624-G2C003A-v1

1. **Lifecycle States:** Must be exactly `draft`, `approved`, `issued`, and `voided`.
2. **Supersession:** No `superseded` state; use `supersedes_invoice_version_id` exclusively.
3. **Date Validation:** Provided ISO dates (`issue_date_iso`, `due_date_iso`) must be strictly parsed (e.g., using `datetime.fromisoformat`).
4. **Temporal Ordering:** `due_date_iso` cannot precede `issue_date_iso`.
5. **Currency Formatting:** `currency_iso` must be exactly three uppercase letters.
6. **Strict Types:** `total_minor_units` must satisfy `type(total) is int`. Booleans and floats must be strictly rejected.
7. **Completeness on Issue:** Approved and issued versions must have an invoice number, issue date, due date, currency, and total.
8. **Immutability:** Existing immutable invoice and version identifiers remain intact. No other domain mappings (payments, banks, workbooks) are added.

## Target Files
- `ar_invoice_record.py`
- `tests/test_ar_invoice_record.py`
