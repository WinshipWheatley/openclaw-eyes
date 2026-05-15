# External AI Context Packs Read-Model v0

What this is:
- A generated read-model over safe context-pack exports for external AI projects/sessions and local agents.

What this is not:
- It is not upload automation, browser automation, network access, agent activation, or execution.

Summary:
- Packs: 1.
- Latest safety status: `safe_for_manual_upload_review`.
- Supported profiles: chatgpt_project, claude_project, codex_session, gemini_session, generic_zip, local_agent.

Latest pack:
- Pack: `mission_control_current`.
- Profile: `chatgpt_project`.
- Output: `generated/context_packs/mission_control_current`.
- Files: 42 source_files=41.
- ZIP: `generated/context_packs/mission_control_current/OpenClaw_ContextPack_mission_control_current.zip`.
- Raw private included: `false`.
- No-go included: `false`.
- Secrets included: `false`.

Upload posture:
- Manual upload only. Start with 00_START_HERE.md, MANIFEST.json, CURRENT_STATE.md, and SAFETY_BOUNDARIES.md; upload selected_read_models in small batches.

Authority boundary:
- `external_upload_allowed`: `false`.
- `browser_automation_allowed`: `false`.
- `network_authority`: `false`.
- `raw_private_included`: `false`.
- `no_go_included`: `false`.
- `secrets_included`: `false`.
- `agent_activation_allowed`: `false`.
- `action_auto_execute_allowed`: `false`.
