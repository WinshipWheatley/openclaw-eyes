# Niles Stage 1 Schema Contract v0

Status:
- Contract status: `template_ready_schema_only_no_live_authority`.
- Schema count: `6`.
- Stage gate count: `5`.
- Runtime authority added: `false`.
- Practice ledger write allowed: `false`.
- Logic or Ableton open allowed: `false`.
- DAW/session media mutation allowed: `false`.
- Studio control enabled: `false`.
- SEND_HOLD bypass allowed: `false`.
- Taste calibration complete: `false`.

## Schemas
- `niles_operator_interview_memory_v0`: Capture operator-supplied music profile data later, without hidden memory or inference.
- `niles_practice_ledger_event_v0`: Define a future feedback event shape for short daily practice and progression adjustment.
- `niles_adaptive_practice_plan_v0`: Define a short daily routine plan that can knit multiple instruments together.
- `niles_logic_note_update_request_v0`: Define a future dry-run request for writing practice notes into an existing Logic session.
- `niles_studio_control_authority_envelope_v0`: Keep DAW/MIDI/OSC/X32 control separate, gated, and disabled by default.
- `maestro_to_niles_handoff_packet_v0`: Define how Maestro can route music/art context to Niles without activating live tools.

## Covered Instruments
- guitar, piano, drums, voice, tenor_sax.

## Shared, Not Niles-Private
- `operator_interview_to_durable_memory`: Niles uses it for music profile, gear refs, taste refs, and practice constraints.
- `progression_feedback_loop`: Niles uses it for practice metrics, regression rules, and next-plan generation.
- `taste_timed_advice_engine`: Niles uses it for music coaching advice timing after Claude taste calibration.

## Stage Gates
- `stage1_schema_contracts_only`: `ready`.
- `stage2_interview_memory_writer`: `future_blocked`.
- `stage3_practice_ledger_and_adaptive_coach`: `future_blocked`.
- `stage4_logic_note_update_writeback`: `future_blocked`.
- `stage5_studio_control_lane`: `future_blocked`.

## Machine Proof
- All required schema fields present: `true`.
- All authority flags safe: `true`.
- Studio control separate and blocked: `true`.
- Logic note update dry-run only: `true`.
- Templates use placeholders, not facts: `true`.
- Niles uses shared primitives: `true`.
- Content hash: `sha256:bdf166c150e56e0e3cecdf4a055f82a7de70246ba8302f73eae51d6aa59c16c6`.

## Next Safe Operator Action
- Review the Stage 1 schemas, then let Claude/taste calibration fill interview prompts later.
