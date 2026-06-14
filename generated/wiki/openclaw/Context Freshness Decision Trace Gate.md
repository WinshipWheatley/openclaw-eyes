# Context Freshness Decision Trace Gate

Status: CONTEXT_FRESHNESS_DECISION_TRACE_GATE_READY

This is a contract gate for future LM proof bundles. It blocks stale, superseded, test-only, generated-only, and untraceable context from being treated as current truth.

## Summary

- Contexts total: `9`
- Allowed for LM bundle: `4`
- Blocked or historical: `5`
- Stale or superseded: `2`

## Rules

- Current receipts beat generated summaries.
- Superseded receipts cannot enter proof bundles as current truth.
- Generated summaries cannot override receipts.
- Candidate/operator-reported evidence must be labeled as such.
- Test-only evidence cannot be primary truth.
- Stale sources produce Needs verification, not confident response text.
- Prior attempts and rejections are included when relevant.
- Operator memory is not canonical truth unless promoted.
- If no current proof exists, proof bundle builder blocks or marks context unknown.
- The LM must not receive stale context as if current.

## Gate Rows

- `context:finance:capital_hilton:payment_watch`: freshness `current`, confidence `receipt_backed`, allowed `true`. Current receipt says Coupa is processing, payment evidence is missing, paid marking is not proven, and ledger remains untouched.
- `context:finance:live_arts_md:payment_evidence`: freshness `current`, confidence `operator_reported_candidate`, allowed `true`. Evidence intake recorded candidate payment-processing evidence; it is not paid truth.
- `context:build:review_packet:informational_resolved`: freshness `historical`, confidence `historical_resolved`, allowed `false`. Review packet was marked informational/resolved and must not appear as active ready-for-review.
- `context:business_development:capital_hilton:followup`: freshness `current`, confidence `receipt_backed`, allowed `true`. Latest proposal receipt supports follow-up staging; no send authority exists.
- `context:finance:capital_hilton:superseded_payment_source`: freshness `superseded`, confidence `stale`, allowed `false`. Superseded receipt is retained for history only and cannot enter the LM bundle as current truth.
- `context:system:stale_or_unknown_source`: freshness `stale`, confidence `unknown`, allowed `false`. Untraceable stale source must produce Needs verification instead of confident response text.
- `context:finance:capital_hilton:generated_summary_conflict`: freshness `current`, confidence `receipt_backed`, allowed `true`. A generated summary conflicted with the current receipt; receipt truth wins and the summary claim is blocked.
- `context:test_only:evidence_fixture`: freshness `unknown`, confidence `test_only`, allowed `false`. Test-only evidence may validate UI/test behavior but cannot be primary truth for LM proof bundles.
- `context:memory:unpromoted_operator_memory`: freshness `unknown`, confidence `unpromoted_memory`, allowed `false`. Unpromoted memory can inform review only after promotion; it cannot become canonical truth in a proof bundle.
