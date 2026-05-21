# Package Compiler Contract v0

Status:
- Deterministic metadata-only package compiler skeleton with boundary validation.
- Backend/read-model contract only; no live runner, model call, agent launch, or app UI lane.

## What Is A Package?
- The model is the actor.
- The agent is the character/persona.
- The package is the script, context, tools, clearance, steps, boundaries, and proof requirements.
- The actor does not decide its own authority, context, plugins, clearance, or mission.

## How Packages Are Compiled
- Compile from lane type, read-model/evidence inputs, actor/workbench metadata, agent character, clearance, allowed/forbidden capabilities, steps, stop conditions, confidence/detour state, proof requirements, receipt requirements, authority boundary, and workspace/chat target.

## Deterministic Fields
- `package_id`, `package_type`, `source_lane_id`, `source_lane_type`, `steel_thread_template_id`, `target_workbench_or_actor_host`, `actor_model_candidate`, `agent_character`, `allowed_workspace_roots`, `forbidden_paths`, `workspace_scope`, `context_included`, `context_excluded`, `evidence_refs`, `read_model_refs`, `capabilities_requested`, `capability_grants`, `allowed_capabilities`, `forbidden_capabilities`, `allowed_plugins_or_capabilities`, `forbidden_plugins_or_capabilities`, `clearance_level`, `security_clearance`, `authority_level`, `authority_boundary`, `autonomy_level`, `steps`, `stop_conditions`, `failure_stop_conditions`, `validation_requirements`, `required_schema_checks`, `required_file_existence_checks`, `required_hash_or_manifest_checks`, `required_test_results`, `required_exit_codes`, `proof_requirements`, `required_receipts`, `receipt_requirements`, `confidence_state`, `confidence_inputs`, `detour_options`, `permitted_command_classes`, `forbidden_command_classes`, `compile_time_blockers`, `credential_policy`, `storage_policy`, `c_drive_policy`, `no_go_data_policy`, `success_validation`, `boundary_validation`, `current_availability`, `failure_reset_behavior`, `quiet_condition`, `human_confirmation_required`.

## Boundary Validation
- Natural-language claims cannot establish authority, clearance, health, success, or tool access.
- Required boundary fields: `allowed_workspace_roots`, `forbidden_paths`, `allowed_capabilities`, `forbidden_capabilities`, `clearance_level`, `authority_level`, `autonomy_level`, `required_receipts`, `required_schema_checks`, `required_file_existence_checks`, `required_hash_or_manifest_checks`, `permitted_command_classes`, `forbidden_command_classes`, `compile_time_blockers`, `human_confirmation_required`, `credential_policy`, `storage_policy`, `c_drive_policy`, `no_go_data_policy`, `failure_stop_conditions`.
- Enums are defined for authority level, clearance level, autonomy level, capability class, command class, validation requirements, receipts, and failure stop conditions.

## Compile-Time Blockers
- `path_outside_allowed_roots` on `workspace_scope.path_refs`: Package references a path outside allowed workspace roots.
- `forbidden_capability_requested` on `capabilities_requested`: Package requests a capability not explicitly granted.
- `credential_or_secret_requested` on `credential_policy`: Package requests credentials, secrets, tokens, or account sessions.
- `active_external_authority_requested` on `capabilities_requested`: Package requests browser, OAuth, model, agent, account, send, submit, approval, or portal authority.
- `preview_escalated_to_execution` on `authority_level`: Package escalates from preview/read-only posture to write or execution without an approved gate.
- `pc_system_drive_write_requested` on `c_drive_policy`: Package attempts to write OpenClaw artifacts to the PC system drive.
- `missing_receipt_or_proof` on `required_receipts`: Package omits deterministic receipts, schema checks, or proof requirements.
- `success_claim_without_deterministic_validation` on `success_validation`: Package claims success without schema, hash, receipt, test, or exit-code proof.
- `actor_self_assigned_authority` on `authority_boundary`: Package lets the actor/model choose its own clearance, tools, authority, workspace, or success criteria.
- `future_gated_action_made_active` on `current_availability`: Package converts a future-gated action into active launch, dispatch, runtime, or mutation authority.

## Blocked By Default
- `file_write_scoped`, `test_run`, `build_run`, `git_commit`, `shell_command_scoped`, `app_launch`, `model_call`, `agent_call`, `browser`, `oauth`, `credential_access`, `email_send`, `calendar_mutation`, `coupa_portal`, `telegram_send`, `runtime_activation`, `cleanup_delete`, `remount`, `pc_c_drive_write`.

## Safe Preview Package
- Contains package text, context refs, proof refs, detour options, schema/hash checks, required receipts, and explicit boundary fields.
- Does not contain live launch, dispatch, model/agent/tool calls, account access, send/submit/approval, runtime activation, cleanup, remount, credential handling, or PC system-drive artifact writes.

## Invalid Package Conditions
- Outside allowed workspace roots, forbidden or ungranted capability, credential/secret request, active external authority, preview-to-execution escalation, missing receipt/proof/schema/hash validation, success claim without deterministic proof, actor self-assigned authority, or future-gated action marked active.

## LM-Assisted Fields
- `operator_eli5`, `mission`, `stakes_why_it_matters`, `detour_explanation`, `package_summary`, `prompt_prose`, `risk_explanation`.
- LM-assisted prose cannot add authority, tools, paths, secrets, plugins, or execution steps.

## Package Types
- `check_light_diagnostic_package`: Check-Light Diagnostic Package -> `check_light_lane`.
- `helm_lane_awareness_package`: Helm Lane Awareness Package -> `helm_lane`.
- `world_lane_work_package`: World Lane Work Package -> `world_lane`.
- `design_memory_discovery_package`: Design Memory Discovery Package -> `nested_lane`.
- `bridge_sync_diagnostic_package`: Bridge Sync Diagnostic Package -> `check_light_lane`.
- `workbench_actor_review_package`: Workbench Actor Review Package -> `package_preview_lane`.
- `code_implementation_package`: Code Implementation Package -> `package_preview_lane`.
- `verification_review_package`: Verification Review Package -> `package_preview_lane`.
- `tell_system_whats_missing_package`: Tell System What's Missing Package -> `confidence_detour_lane`.
- `confidence_detour_package`: Confidence Detour Package -> `confidence_detour_lane`.

## Actor / Workbench Routing
- Source registry: `operator_workbench_actor_host_registry`.
- Unknown actor or host fails closed.
- Routes include Codex for scoped implementation, Antigravity/Gemini for bounded verification/review, GPT-5.5 orchestrator for synthesis, and Repo A for deterministic contract/export/test work.

## Preview Only Now
- `preview_only`, `copy_export_only`, `future_gated`.
- Live launch allowed now: `false`.
- Model/agent/tool call from app allowed now: `false`.

## Future-Gated
- Launching a workbench, dispatching to an actor, ingesting returned state, send/submit/approval, browser/account access, and automatic repair remain future-gated.

## Authority Boundary
- No external model APIs, Codex/Antigravity/VS Code agent sessions, Mission Control app mutation, live launch buttons, runtime execution, browser/OAuth/Gmail/calendar/Coupa/Telegram/send/submit/approval authority, automatic repair, system-drive artifact writes, deletes, cleanup, repair, remount, or credential handling.

## Sample Packages
- `sample_check_transmission_diagnostic_package`: Diagnose whether PC proof, Mac manifest, and sync health agree without remounting or repairing anything.
- `sample_mission_control_ui_implementation_package_for_codex`: Implement a scoped Mission Control surface after a future UI lane grants explicit Mac app authority.
- `sample_antigravity_verification_review_package`: Review a bounded contract/read-model change for missing tests, authority creep, and proof gaps.

## What Mission Control Can Render
- Package schema fields, package type, source lane, steel-thread template, actor/workbench target, agent character, included/excluded context, deterministic boundary fields, validation requirements, confidence/detour state, authority boundary, and receipt requirements.
- Mission Control can show the future chat/workspace target without launching it.

## Next Safe Lane
- Mission Control Package Preview Readback Surface v0
