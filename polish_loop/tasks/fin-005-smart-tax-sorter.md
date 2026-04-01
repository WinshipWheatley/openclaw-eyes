title: fin-005-smart-tax-sorter
profile: architect
goal: Use financial logs and invoice artifacts to classify recent transactions into Business Deductions vs Personal with explicit category tags.
scope:
- Read recent records from FINANCIAL_LOG sources and invoice PDF metadata available in current OpenClaw runtime.
- Categorize entries into: Business Deductions (Music, Studio, Golf-Networking) or Personal.
- Add rationale tags per row (keyword/source/rule match) and confidence score.
- Output classification table and unresolved-items queue requiring manual review.
- Enforce PII-safe handling and avoid exposing sensitive identifiers in plain text outputs.
success:
- A sortable classification output is produced with deduction vs personal split and rationale tags.
- Unclear rows are isolated into a manual-review section.
verification: |
  python3 -c "print('fin-005-tax-sorter-spec-ready')"
