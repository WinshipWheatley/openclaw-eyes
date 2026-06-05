# Operator Controller Event Router

Status: `OPERATOR_CONTROLLER_EVENT_ROUTER_READY`

This router maps verified generic Mission Control controller events into existing safe backend routes.
It is a controller layer, not a business executor.

## Rules

- Verified first-class operator envelope required.
- Incoming authority_granted, gate_decision_ref, and approval_receipt_ref are backend-only and rejected or ignored.
- authority_requested does not imply authority_granted.
- Unknown events fail closed.
- Missing deterministic action payload returns Needs verification.
- Every route emits a receipt/ref and dynamic card response.
- No live external provider action and no business execution.
- Protected actions are staged for approval/gate review or blocked; never directly sent, submitted, posted, marked paid, merged, or pushed.

## Routes

- `ask_why` -> `system_question_answer.contextual_answer`: contextual answer only; no package staging unless explicitly required
- `open_lane` -> `operator_action_payloads.navigate`: navigation card/action only
- `attach_proof` -> `evidence_intake.record_candidate_evidence`: candidate evidence only; no paid or ledger mutation
- `approve|deny` -> `workroom_review_decision_consumer or approval_request_queue.stage_only`: decision/staging receipt only; no business execution
- `request_rework|mark_informational` -> `workroom_review_decision_consumer.record_decision_only`: review decision receipt only; no merge or push
- `do_it` -> `operator_action_payloads deterministic safe route`: safe internal route or protected action staged/blocked
- `show_details` -> `dynamic_card_packet.proof_drawer`: proof/details card only

## Latest Receipt

- Receipt: `operator_controller_event_router:ff7083dae54fc611`
- Event: `ask_why`
- Status: `ROUTED`
- Backend route: `system_question_answer.contextual_answer`
- Route ref: `system_question_answer:contextual_lane_answer`

## Safety Boundary

- No email/Gmail/browser/Coupa/portal submit.
- No ledger or workbook mutation.
- No PDF export or paid marking.
- No merge, push, worker spawn, external LLM, or local model runtime.
- Incoming `authority_requested` is only a request; incoming `authority_granted` is rejected or ignored.
