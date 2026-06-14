# Polish Loop Packet Feed Design

## Purpose

Feed the parked polish-loop Builder from `agent_work_packets` without turning
the loop back on yet.

This is a design contract only. It does not start the polish loop, invoke
Ollama, call LM2/qwen, spawn workers, or grant runtime authority.

## Current Substrate

- `agent_work_packets.exact_next_prompt_text` already contains a bounded work
  prompt with allowed and blocked surfaces.
- `build_task.model_class_recommendation` in the system knowledge registry is
  the future model-class hint.
- `polish_loop/orchestrator.py` owns state transitions through `status.json`.
- `polish_loop/local_builder.py` is a local Ollama/tool wrapper, but it is not
  active for this lane.
- `polish_loop/status.json` is currently idle and old; it must stay parked until
  a separate operator approval explicitly activates a run.

## Future Adapter Shape

`agent_work_packet_to_polish_task(packet_id)` should:

1. Read one approved `agent_work_packets` row.
2. Refuse if `execution_allowed=false` unless the future lane is explicitly
   review-only.
3. Read only packet context links marked `allowed_for_packet=true`.
4. Use `exact_next_prompt_text` as the primary task body.
5. Include packet id, source intent id, routed agent/lane, and blocked surfaces.
6. Add `model_class_recommendation` from the registry build-task row if present.
7. Write a bounded `polish_loop/task.md` candidate only under a future approved
   dispatch path.
8. Leave `polish_loop/status.json` unchanged unless the future dispatcher has a
   separate approval receipt.

## Package Fields

Required future package fields:

- `packet_id`
- `source_intent_id`
- `assignment_id` if present
- `routed_agent_id`
- `routed_lane_id`
- `goal`
- `exact_next_prompt_text`
- `allowed_context_refs`
- `blocked_surfaces`
- `model_class_recommendation`
- `validation_command`
- `stop_condition`
- `proof_required`
- `operator_review_required=true`
- `auto_apply_allowed=false`

## Safety Rules

- No packet may grant model/tool/runtime authority by implication.
- Missing context blocks the package; it does not become permission to invent.
- Protected actions still require Guardian/HITL.
- Sends remain blocked while `SEND_HOLD.md` exists.
- The Builder gets a bounded chunk, not a raw repo dump.
- The loop remains parked until an explicit activation lane approves it.

## First Safe Test Later

Use a tiny review-only `agent_work_packet` with:

- no external surfaces
- no private raw bodies
- one source file or generated read model
- one validation command
- one expected `pc_output.md` result

Success means the adapter creates a candidate package and a verifier accepts the
package shape. It does not mean the polish loop ran.

## Do Not Build Yet

Do not start `polish_loop/orchestrator.py`, `local_builder.py`, Ollama, Hermes,
or any worker from this design. The next implementation should be a pure
compiler plus tests.
