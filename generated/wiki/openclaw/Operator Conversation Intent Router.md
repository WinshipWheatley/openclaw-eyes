# Operator Conversation Intent Router

Status: `OPERATOR_CONVERSATION_INTENT_ROUTER_READY`

Routes Finance / Capital Hilton lane-local composer questions to distinct text-first proof-to-response answers.

## Intent Classes

- `payment_watch_next_step` -> `finance_capital_hilton_payment_watch`
- `paid_or_ledger_blocker` -> `finance_capital_hilton_payment_watch`
- `attach_proof_hypothetical` -> `finance_capital_hilton_attach_proof_explanation`
- `handle_it_or_continue_boundary` -> `finance_capital_hilton_handle_boundary`
- `package_context_explanation` -> `finance_capital_hilton_package_context`
- `allowed_scope_explanation` -> `finance_capital_hilton_allowed_scope`
- `forbidden_scope_explanation` -> `finance_capital_hilton_forbidden_scope`
- `freshness_uncertainty_explanation` -> `finance_capital_hilton_freshness_uncertainty`
- `decision_trace_explanation` -> `finance_capital_hilton_decision_trace`
- `fallback_lane_answer` -> `finance_capital_hilton_fallback_lane_answer`

## Rules

- Fresh LM2-backed payment-watch text may be reused only for payment_watch_next_step and paid_or_ledger_blocker when scoped.
- Package, allowed-scope, forbidden-scope, freshness, and decision-trace questions use specialized deterministic proof-to-response scenarios.
- No WORKFLOW_PACKAGE_REQUEST_V0 path is emitted from lane-local chat_goal questions.
- No model invocation, worker spawn, prompt send, proof-bundle send, protected action, paid marking, ledger mutation, or business execution occurs.

## Sample Responses

- `payment_watch_next_step`: Payment evidence needed -> Attach payment evidence.
- `paid_or_ledger_blocker`: Payment evidence needed -> Attach payment evidence.
- `attach_proof_hypothetical`: Proof can be recorded -> Attach payment evidence.
- `handle_it_or_continue_boundary`: I can handle the safe part -> Attach payment evidence.
- `package_context_explanation`: LM2 would get bounded context -> No worker action is needed unless you approve a bounded worker run.
- `allowed_scope_explanation`: Allowed: explain and collect proof -> Attach payment evidence.
- `forbidden_scope_explanation`: Protected actions stay blocked -> Attach payment evidence.
- `freshness_uncertainty_explanation`: Evidence is the uncertainty -> Attach payment evidence.
- `decision_trace_explanation`: Payment watch is still active -> Attach payment evidence.
- `fallback_lane_answer`: Payment watch is the safe lane -> Show details.
