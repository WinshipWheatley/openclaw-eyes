# Mission Control Read-Model Refresh v0 Prompt

You are working on the Mac Mission Control app in Xcode.

Goal:
Display newer OpenClaw generated read-model surfaces as read-only operator views.

Read only from:
- `~/openclaw_generated_read_models/context_selection.json`
- `~/openclaw_generated_read_models/project_capsules.json`
- `~/openclaw_generated_read_models/tool_inventory.json`
- `~/openclaw_generated_read_models/tool_intake.json`

Add read-only surfaces:
- Context Packet posture
- Project Capsule overview
- Tool posture
- Candidate policy overlay

Hard constraints:
- No backend execution.
- No network calls.
- No writes.
- No action buttons.
- No runtime activation.
- No agent activation.
- No tool activation or tool execution.
- No Docker/Ollama execution.
- No fake live health.
- Preserve the existing read-only helm overview.
- Read generated files only.

Authority posture to display:
- `runtime_authority=false`
- `backend_execution_allowed=false`
- `agent_activation_allowed=false`
- `tool_execution_allowed=false`
- `network_authority=false`
- `truth_promotion_allowed=false`

Implementation notes:
- Treat missing files as an unavailable read-model state, not an app failure.
- Do not infer approval, health, deployment readiness, or live backend status from generated read-model presence.
- Context packets are selected evidence/context, not truth promotion.
- Project capsules are planning contracts, not client deployment authority.
