# Universal Receipt Envelope

Status: UNIVERSAL_RECEIPT_ENVELOPE_READY

Universal Receipt Envelope V0 is the shared receipt shape for controller events, packages, evidence, review decisions, approval queues, dynamic cards, memory gates, workflow plans, and future worker result rails.

A receipt records what happened and what did not happen. It is not an approval, not execution proof, and not a source of business truth by itself.

## Doctrine

- Approval receipt is not execution proof.
- Evidence receipt is not paid truth unless payment or ledger evidence exists.
- LM output is not receipt truth.
- Incoming authority_granted is ignored or rejected.
- No business action receipt exists until a future explicit executor gate records one.

## Receipt Types

- `controller_event_received`
- `evidence_recorded`
- `package_staged`
- `package_rejected`
- `review_decision_recorded`
- `approval_recorded`
- `gate_blocked`
- `dynamic_card_emitted`
- `memory_candidate_recorded`
- `workflow_plan_staged`
- `worker_result_recorded_future`

## Required Fields

- `receipt_id`
- `receipt_type`
- `created_at`
- `source_request_id`
- `controller_event_id`
- `operator_envelope_ref`
- `package_id`
- `card_id`
- `world_ref`
- `thread_ref`
- `client_ref`
- `workflow_ref`
- `actor_ref`
- `agent_character`
- `action_taken`
- `action_not_taken`
- `authority_requested`
- `authority_granted`
- `authority_denied`
- `proof_refs`
- `artifact_refs`
- `hash_refs`
- `sqlite_refs`
- `read_model_refs`
- `validation_refs`
- `result_status`
- `business_action_performed`
- `paid_marking_performed`
- `ledger_mutation_performed`
- `email_send_performed`
- `coupa_submit_performed`
- `workbook_mutation_performed`
- `pdf_export_performed`
- `next_safe_action`

## Status Snapshot

- Receipt count: `11`
- SQLite row count: `11`
- SQLite: `/home/openclaw/generated/system_knowledge/universal_receipts.sqlite`
- Unsafe true grants absent: `true`
