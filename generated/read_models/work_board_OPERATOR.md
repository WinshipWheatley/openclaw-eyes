# OpenClaw Work Board Read-Model v0

What this is:
- A generated read-model over local `work_board_*` control-plane cards.

What this is not:
- It is not execution, approval, agent activation, model calling, external API access, or file operations.

Summary:
- Boards: 1.
- Cards: 49.
- By column: completed_with_receipt=2, deferred=6, needs_review=13, pending_approval=1, planned=2, routed=25.
- By agent: cassandra=6, chief=19, guardian=6, hermes=5, niles=7, report_bridge=6.
- Needs review: 13.
- Pending approval: 1.
- Blocked: 0.
- Completed with receipt: 2.

Latest cards:
- `wbcard_fa9a45158142a80a29f3` routed intent_record:smoke_intent_b22a88b9b050ac5a2fdf - Intent: Chief, organize my Markdown files.
- `wbcard_f9c01faf01dce9dc4b86` deferred dropped_intent:dropintent_a4b178ac6fb4e77ac7ec - Report Bridge Sample Package v0
- `wbcard_f660382b106d8d458b75` needs_review intent_record:smoke_intent_0ce738e5f095b6bc4c26 - Intent: Hermes, synthesize current posture.
- `wbcard_f505bb8374d8e82f7d12` deferred dropped_intent:dropintent_129e9fe879dad60c5396 - Legacy GitHub Repo Intake v0.1
- `wbcard_e1cec09634845d7b6948` needs_review intent_record:smoke_intent_9f092a78fb1e6ea1cb7b - Intent: Niles, do something with that new Logic file.
- `wbcard_dbdd86caf0498e5dc45b` routed intent_record:smoke_intent_34a6da8e7782a10a062a - Intent: Cassandra, summarize what changed.
- `wbcard_db6710857b8516367cd8` routed intent_record:smoke_intent_74aed714113f66fc0e71 - Intent: Guardian, is this safe?
- `wbcard_d873c2e1bbe5c4a16d05` routed intent_record:smoke_intent_09cf36bc8867efef2796 - Intent: Guardian, is this safe?
- `wbcard_d6314b07e757923e0036` deferred dropped_intent:dropintent_16f18d33bd951b7a776e - Automatic file watcher daemon
- `wbcard_c94a2a64506de82675e5` needs_review intent_record:smoke_intent_877940d749502402c8f4 - Intent: Hermes, synthesize current posture.

Top next safe moves:
- Do you want Mission Control to draft action request files into the E-drive inbox next? Suggested lane: Mission Control Action Request Writer v0.
- Do you want to build recent-file context resolution over File Event Queue metadata? Suggested lane: Recent File Context Resolver v0.
- Resolve recent file-event metadata and draft a metadata-only plan; do not open private/raw file bodies or edit files.
- Resolve recent file-event metadata and draft a metadata-only plan; do not open private/raw file bodies or edit files.
- Ask the operator for a clearer target agent, file, world, or allowed action; do not execute anything.
- Ask the operator for a clearer target agent, file, world, or allowed action; do not execute anything.
- Ask the operator for a clearer target agent, file, world, or allowed action; do not execute anything.
- Resolve recent file-event metadata and draft a metadata-only plan; do not open private/raw file bodies or edit files.
- Ask the operator for a clearer target agent, file, world, or allowed action; do not execute anything.
- Resolve recent file-event metadata and draft a metadata-only plan; do not open private/raw file bodies or edit files.

Authority boundary:
- `direct_execution_allowed`: `false`.
- `arbitrary_shell_allowed`: `false`.
- `auto_approval_allowed`: `false`.
- `auto_execute_allowed`: `false`.
- `agent_activation_allowed`: `false`.
- `model_call_allowed`: `false`.
- `tool_execution_allowed`: `false`.
- `network_authority`: `false`.
- `no_go_raw_access_allowed`: `false`.
- `file_move_allowed`: `false`.
- `file_delete_allowed`: `false`.
- `client_deployment_allowed`: `false`.
