# Package Compiler Contract v0

Status:
- Deterministic metadata-only package compiler skeleton.
- Backend/read-model contract only; no live runner, model call, agent launch, or app UI lane.

## What Is A Package?
- The model is the actor.
- The agent is the character/persona.
- The package is the script, context, tools, clearance, steps, boundaries, and proof requirements.
- The actor does not decide its own authority, context, plugins, clearance, or mission.

## How Packages Are Compiled
- Compile from lane type, read-model/evidence inputs, actor/workbench metadata, agent character, clearance, allowed/forbidden capabilities, steps, stop conditions, confidence/detour state, proof requirements, receipt requirements, authority boundary, and workspace/chat target.

## Deterministic Fields
- `package_id`, `package_type`, `source_lane_id`, `source_lane_type`, `steel_thread_template_id`, `target_workbench_or_actor_host`, `actor_model_candidate`, `agent_character`, `context_included`, `context_excluded`, `evidence_refs`, `read_model_refs`, `allowed_plugins_or_capabilities`, `forbidden_plugins_or_capabilities`, `security_clearance`, `authority_boundary`, `steps`, `stop_conditions`, `proof_requirements`, `receipt_requirements`, `confidence_state`, `confidence_inputs`, `detour_options`, `current_availability`, `failure_reset_behavior`, `quiet_condition`, `human_confirmation_required`.

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
- Package schema fields, package type, source lane, steel-thread template, actor/workbench target, agent character, included/excluded context, confidence/detour state, authority boundary, and receipt requirements.
- Mission Control can show the future chat/workspace target without launching it.

## Next Safe Lane
- Mission Control Package Preview Readback Surface v0
