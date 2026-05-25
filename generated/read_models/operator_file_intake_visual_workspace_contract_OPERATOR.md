# Operator File Intake + Visual Workspace Contract

Status: DETERMINISTIC_NON_EXECUTING_FILE_INTAKE_VISUAL_WORKSPACE_CONTRACT

## ELIOPERATOR

This lets OpenClaw turn operator materials into governed source refs and visual workspace requests.

What this enables:
- Operators can attach or reference source material, ask to see work visually, and let the router choose the right visual, backend, proof, or app-boundary worker package.

What this does not do yet:
- It does not ingest raw bodies, automate apps, mutate files, capture screens, send email, export, publish, call models, dispatch agents, or access external systems.

How it works:
- Files become source refs with safe labels, privacy class, sensitivity class, extraction status, and fingerprint policy. Normal read-models do not include full private paths or raw bodies.
- A chat request can ask for a workspace mode. The workspace binds source refs, related notes, proof refs, task status, warnings, and next actions into a compact visual plan.
- App targets and command summaries can be modeled, but live automation and mutation remain false until a future approved adapter has explicit scope, confirmation, backup or receipt posture, and readback.
- Agents see source refs, safe labels, summaries, allowed extracts, and proof posture. Raw private bodies stay out of LLM context by default.
- Mac visual/app work routes to MAC_CODEX, backend source/proof packaging routes to PC_CODEX, protected proof routes to GUARDIAN, design audit routes to GEMINI_AGY, and communications drafting routes to CASSANDRA when gated.

Example readbacks:
- Album workspace: show the spreadsheet and related song notes as read-only source refs.
- Invoice workspace: show invoice packet status, proof refs, missing items, and locked send/submit actions.
- Protected proof: show safe proof refs while raw bodies stay hidden.
- App boundary: Logic can be modeled as a visual/app request, but mutation and export remain gated.
- Unsafe automation: Mail send is blocked until a governed email/approval adapter exists.

Current examples present:
- album_spreadsheet_song_doc
- capital_hilton_invoice_workspace
- legal_contract_review_workspace
- video_edit_review_workspace
- live_show_planning_workspace
- client_delivery_workspace
- bug_debug_workspace
- protected_proof_workspace
- invoice_artifact_source
- screenshot_proof
- app_automation_request
- unsafe_automation_blocker
- visual_mode_transition

Authority boundary:
- live_file_ingestion_allowed: False
- live_raw_body_extraction_allowed: False
- live_app_automation_allowed: False
- live_file_mutation_allowed: False
- live_external_app_control_allowed: False
- live_email_send_allowed: False
- live_project_edit_allowed: False
- live_screenshot_capture_allowed: False
- live_screen_recording_allowed: False
- live_export_allowed: False
- live_publish_allowed: False
- live_agent_dispatch_allowed: False
- live_model_call_allowed: False
- live_external_action_allowed: False
- credential_handling_allowed: False
- raw_body_ingestion_allowed: False
- network_allowed: False
- mac_sync_import_allowed: False
- mission_control_swift_change_allowed: False
- git_push_pull_fetch_allowed: False

Next safe move: Use this contract to build future intake packets and visual workspace mirrors without live ingestion or automation.
