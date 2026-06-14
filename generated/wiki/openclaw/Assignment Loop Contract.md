# Assignment Loop Contract

Status: `OPENCLAW_ASSIGNMENT_LOOP_CONTRACT_READY`

Every Codex/Gemini/Fable/local-worker task is framed as a bounded job.

## Required Fields

- `assignment_id`
- `requested_by`
- `owner_agent`
- `worker_type`
- `goal`
- `sources`
- `standard`
- `permission_boundary`
- `proof_required`
- `stop_condition`
- `current_status`
- `receipts`
- `watch_desk_refs`
- `operator_next_action`
- `safety_flags`

## Phases

intake -> package -> dispatch -> work -> verify -> summarize -> next_action -> archive

## Doctrine

- Model output is advisory until deterministic verification and receipts exist.
- No model output directly mutates runtime policy or business state.
- Guardian/HITL remains the existing approval path and is not replaced by assignments.
- Watch Desk may display assignments but does not approve or execute them.
- Parking-lot items may attach to active assignments without marking them ready.
- READY requires proof refs or receipts.

## Existing Systems Reused

- `model_work_package_router.py`
- worker package staging and spawned worker lifecycle read models
- Watch Desk feed items
- Operator Context Switchboard
- Guardian/HITL approval spine
- receipts/read models
- `agent_lane_registry.py`

This contract does not create a new approval system, dashboard, model call, or runtime mutation path.
