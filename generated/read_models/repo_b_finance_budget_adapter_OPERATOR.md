# Repo B Finance Budget Adapter

Repo B finance logic is useful, but the safe v0 path is a rebuilt deterministic subset in Repo A, not live Repo B execution.

Posture: REBUILD_SMALL_SUBSET_IN_REPO_A

Safe capabilities:
- finance_capability_show_budget_calculation
- finance_capability_expense_category_mapping
- finance_capability_capital_hilton_invoice_summary
- finance_capability_payment_tracking_summary
- finance_capability_tax_category_hint
- finance_capability_client_job_finance_summary
- finance_capability_report_formatting

Blocked capabilities:
- bank/external account access
- payment execution
- tax filing
- credential handling
- raw private ledger exposure
- professional tax/legal advice claims

Examples:
- Show budget: green zone.
- Expense category: software.
- Capital Hilton: 4 dates at $400, subtotal $1600; payment/send state unverified.
- Tax category hint: Bookkeeping hint: software/subscription expense category. Not tax advice.
- Unsafe bank/payment action: blocked.

Boundary:
- No bank access, payment execution, tax filing, external account access, invoice/email send, Coupa access, credential handling, raw private ledger exposure, professional advice claim, external action, Mac sync/import, Swift change, or push.

Next safe move: Use safe fixture helpers now; later connect them to Repo A receipts/readbacks instead of raw ledgers.
