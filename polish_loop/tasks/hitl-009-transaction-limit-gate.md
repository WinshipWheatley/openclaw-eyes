title: hitl-009-transaction-limit-gate
goal: Add transaction-limit guard to auto-deny or super-flag high-dollar payment actions.

Description:
Introduce payment safety logic that compares requested amounts against configurable thresholds, auto-denies over hard limit, and marks near-limit or policy-sensitive requests with a Super-Flag escalation state.

Verification:
- Payments above hard limit are denied automatically with clear reason code.
- Payments in super-flag range are not auto-executed and are escalated.
- Payments below threshold continue through normal approval flow.
