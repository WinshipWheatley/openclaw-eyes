# Self Heal Repair Doctrine

Status: SELF_HEAL_REPAIR_DOCTRINE_READY

Self Heal Repair Doctrine V0 defines how OpenClaw diagnoses blockers, plans safe repairs, stages safe internal packages, and asks Winship only for the smallest required manual action.

It is doctrine/contract/test work only. It does not execute live repairs.

## Core Doctrine

- If OpenClaw detects a blocker, stale state, failed validation, missing proof, broken route, UI inconsistency, permissions issue, or workflow break, it names the blocker in human language.
- Every blocker claim cites the proof/source that proves it.
- The response states what OpenClaw can safely do now.
- The response states what OpenClaw cannot do yet.
- If manual work is unavoidable, the response asks Winship for the smallest required action.
- The response produces or points to the next repair/update package.
- No repair/update success claim is allowed without validation and receipt.

## Repair Package States

- `detected`
- `diagnosed`
- `repair_plan_ready`
- `safe_internal_repair_ready`
- `operator_action_required`
- `repair_staged`
- `validation_required`
- `validation_passed`
- `validation_failed`
- `receipt_recorded`
- `blocked_by_gate`

## Required Fields

- `repair_ref`
- `blocker_summary`
- `proof_refs`
- `affected_surface`
- `affected_route`
- `affected_world_thread`
- `severity`
- `safe_internal_actions`
- `forbidden_actions`
- `required_operator_action`
- `validation_plan`
- `rollback_plan`
- `receipt_requirement`
- `dynamic_response_copy`
- `proof_meter_updates`

## Scenario Contracts

- `mac_controller_response_stale_after_lane_switch`: `repair_plan_ready` - Mac controller response is stale -> Stage scoped renderer fix
- `evidence_picker_path_leaked_into_composer`: `safe_internal_repair_ready` - Proof path leaked into composer -> Isolate evidence picker from composer
- `excel_export_blocked_by_file_access`: `operator_action_required` - Excel file access is blocked -> Provide workbook access proof or choose another workbook
- `remote_desktop_trace_log_leak`: `operator_action_required` - Remote Desktop trace logs are filling C: -> Choose targeted trace cleanup or disable tracing package
- `missing_proof_for_payment`: `operator_action_required` - Payment evidence is missing -> Attach payment proof

## Guardrails

- Self-heal may diagnose and plan.
- Self-heal may stage safe internal repair packages.
- Self-heal cannot cross protected gates.
- Manual work must be explained plainly.
- No black-box repair claims.
- Every fix requires validation and receipt.
- No live repair execution, repair loops, service restart, worker spawn, model call, email send, browser/Gmail/Coupa opening, ledger/workbook mutation, PDF export, paid marking, submit, push, or protected authority grant.

## Proof

- Preconditions ready: `true`
- Scenario count: `5`
- Package validation errors: `0`
- Unsafe true grants absent: `true`
- Repair success requires validation and receipt: `true`
