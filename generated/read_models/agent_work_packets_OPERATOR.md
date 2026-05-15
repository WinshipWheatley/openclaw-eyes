# Agent Work Packets Read-Model v0

What this is:
- A generated read-model over bounded `agent_work_packet_*` planning packets.

What this is not:
- It is not execution, agent activation, model calling, action creation, or approval.

Summary:
- Packets: 1.
- By agent: chief=1.
- By status: draft=1.
- By category: markdown_reorg_request=1.

Latest packet:
- Packet: `agent_work_packet_sample_markdown_reorg`.
- Agent/lane: `chief` / `system_orchestration`.
- Goal: Propose a Markdown organization/reorg plan without moving files.
- Execution allowed: `false`.

Authority boundary:
- execution_allowed=false; agent_activation_allowed=false; model_call_allowed=false.
- tool_execution_allowed=false; network_authority=false; approval_bypass_allowed=false.
- file_move_allowed=false; file_delete_allowed=false; truth_promotion_allowed=false.
