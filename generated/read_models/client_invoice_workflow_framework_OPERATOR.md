# Client Invoice Workflow Framework

Status: COMPOSABLE_CLIENT_INVOICE_WORKFLOW_FRAMEWORK_NO_ACTIONS
Reusable rails: 13
Capital Hilton: complex Coupa + Excel + Clara + approval + payment watch recipe.
St. Anne's: no Coupa or PO rail unless configured.
Live Arts MD: no Coupa or PO rail unless configured.
Capital Hilton blocked without send receipt: true
Non-Coupa placeholders can complete without Coupa: true

Receipt rules:
- A draft is not sent.
- A generated invoice is not submitted.
- A portal draft is not portal-submitted.
- Guardian approval is not execution.
- Email sent is not payment.
- Payment detected is not ledger-posted.
- Ledger-ready is not tax-filed.
- A selected rail is complete only when that rail's required receipts exist.

No workbook reads, Coupa access, email send, ledger posting, or production mutation authority is enabled.
