# Operator Controller Protocol

Status: `OPERATOR_CONTROLLER_PROTOCOL_READY`

This protocol lets Mission Control, iPad, and iPhone send verified controller events into OpenClaw.
It verifies operator/app/device/session identity and request integrity, then maps the event to a deterministic backend contract.

## Authority

- `authority_requested` is allowed on incoming events.
- `authority_granted` is backend-only and is not trusted from incoming events.
- LMs may summarize and choose candidate routes from the protocol, but cannot create verification or grant authority.

## Event Types

- `chat_goal` -> `openclaw_request_processor.contextual_goal_or_workflow_composer`; receipt required: `false`; dynamic card required: `true`
- `do_it` -> `operator_action_payload_gate.contextual_safe_action`; receipt required: `true`; dynamic card required: `true`
- `approve` -> `workroom_review_decision_or_guardian_approval_queue`; receipt required: `true`; dynamic card required: `true`
- `deny` -> `workroom_review_decision_or_approval_request_queue`; receipt required: `true`; dynamic card required: `true`
- `attach_proof` -> `evidence_intake.record_candidate_evidence`; receipt required: `true`; dynamic card required: `true`
- `ask_why` -> `system_question_answer.contextual_answer`; receipt required: `false`; dynamic card required: `true`
- `open_lane` -> `operator_action_payloads.navigate`; receipt required: `false`; dynamic card required: `true`
- `stage_plan` -> `workflow_composer_or_workflow_package_request_consumer.stage_only`; receipt required: `true`; dynamic card required: `true`
- `continue` -> `operator_action_payload_gate.continue_safe_local_flow`; receipt required: `true`; dynamic card required: `true`
- `request_rework` -> `workroom_review_decision_consumer.request_rework`; receipt required: `true`; dynamic card required: `true`
- `mark_informational` -> `workroom_review_decision_consumer.mark_informational`; receipt required: `true`; dynamic card required: `true`
- `stop_hold_cancel` -> `approval_request_queue_or_workroom_review_decision_consumer.stop_hold_cancel`; receipt required: `true`; dynamic card required: `true`
- `show_details` -> `dynamic_card_packet.proof_drawer`; receipt required: `false`; dynamic card required: `true`

## Examples

- `attach_proof` / `Verified proof attachment to evidence intake` -> `generated/read_models/evidence_intake_contract.json`; authority granted: `[]`
- `do_it` / `Finance / Capital Hilton payment watch` -> `generated/read_models/system_question_answer_contract.json`; authority granted: `[]`
- `approve` / `Build review packet decision recording only` -> `generated/read_models/workroom_review_decision_contract.json`; authority granted: `[]`
- `stage_plan` / `Business Development follow-up staging only` -> `generated/read_models/capital_hilton_business_development_proposal.json`; authority granted: `[]`
- `approve` / `Guardian approval decision recording only` -> `generated/read_models/approval_request_queue.json`; authority granted: `[]`

## Safety

Email, Gmail, browser, Coupa, ledger, workbook, PDF, paid, submit, push, worker, provider, and business-action authority remain false in this protocol.
