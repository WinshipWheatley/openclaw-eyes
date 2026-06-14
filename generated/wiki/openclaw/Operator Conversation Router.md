# Operator Conversation Router

Status: `OPERATOR_CONVERSATION_ROUTER_READY`

Routes lane-local composer text through controller events and proof-to-response before considering package staging.

## Rules

- Preserve current_world_ref, current_thread_ref, selected_card_id, and selected_action_id.
- Common operator questions route to proof-to-response or deterministic text answers, not workflow packages.
- Only explicit stage/build language or a stage_plan safe next action may suggest staging.
- Missing context returns Needs lane context.
- Stale context returns Needs verification.
- Protected action requests return blocked/proof/approval explanations.
- No models, local runtimes, workers, business actions, sends, submits, ledgers, workbook mutations, paid marking, merge, push, or providers.

## Supported Questions

- What should I do?
- What should I do here?
- Why can't this be marked paid?
- What happens if I attach proof?
- What does this proof mean?
- Can you send the follow-up?
- Can you merge/push this?
- How would you map this controller idea?

## Latest Smoke

- finance/capital_hilton: Proof can be recorded -> Attach payment evidence.
- finance/live_arts_md: Payment proof received -> Verify arrival or attach stronger proof
- build/workrooms: Merge and push blocked -> Open the review packet or request rework.
