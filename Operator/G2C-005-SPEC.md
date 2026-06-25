# Task G2C-005: Implement JSON Serialization

## Acceptance Criteria
**Version / Hash:** 20260625-G2C005-v1

1. **Scope:** Pure deterministic JSON serialization layer for `GigRecord`, `WorkSessionRecord`, `InvoiceRecord`, and `ExpectedReceivableRecord`.
2. **Deterministic Output:** Must use deterministic sorted keys and compact separators (`separators=(',', ':')`).
3. **Encoding:** UTF-8 with `ensure_ascii=False`.
4. **Envelopes:** Stable record-type and schema-version envelopes are required.
5. **Coverage:** Every declared field, including optional fields as JSON null, must be serialized.
6. **Exclusions:** No volatile timestamps, random values, or environment metadata. No SQLite, filesystem persistence, workbook, email, Telegram, payment, bank, materialization, or networking behavior.
7. **Strict Deserialization:** Must deserialize safely into only the four approved record classes. Reject unknown record types, unknown schema versions, unknown payload fields, missing fields, duplicate JSON keys, and unsupported Python objects (e.g., NaN and Infinity).
8. **Validation:** Domain validation must execute during deserialization.
9. **Tests:** Stable golden JSON or SHA-256 tests must exist for every record type.
10. **Target Files:**
    - `ar_gig_to_cash_serialization.py`
    - `tests/test_ar_gig_to_cash_serialization.py`
