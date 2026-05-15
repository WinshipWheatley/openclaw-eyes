# Context Selection Read-Model v0

What this is:
- A generated read-model over `context_selection_*` SQLite packet rows.
- It exposes bounded context-packet posture for operators, agents, and Mission Control.

What this is not:
- It is not generic RAG, vector search, model execution, tool execution, runtime activation, or truth promotion.
- It does not include private/no-go raw content and does not approve any action.

Latest packet summary:
- Latest run: `ctx_2026_05_14_build_mission_control_prompt_v0`.
- Latest packet: `ctxpacket_dc4aa1c1c9f43fbe6753`.
- Selected items: 60.
- Excluded records: 200.
- No-go/blocked/sensitive exclusions: 754.
- Worlds represented: build=12, cross_world=48.
- Evidence labels: future_gated_capability=12, generated_read_model_fact=40, unsupported_claim=8.
- Evidence categories: artifact_registry=4, evidence_freshness=10, helm_state=3, operator_status=4, runtime_gate=31, unsupported_capability=8.

Packet artifacts:
- JSON: `generated/context_packets/context_packet_latest.json`.
- Operator markdown: `generated/context_packets/context_packet_latest.md`.

Authority boundary:
- Context packets are selected evidence and bounded reasoning context, not truth promotion.
- runtime_authority=false; agent_activation_allowed=false; backend_execution_allowed=false.
- model_call_allowed=false; vector_search_allowed=false; tool_execution_allowed=false.
- docker_execution_allowed=false; ollama_execution_allowed=false; network_authority=false.
- truth_promotion_allowed=false.

Known safe packet categories:
- runtime_gate, future_gated_capability, tool_posture, generated_read_model_fact.

Next safe move:
- Use this read-model as an inspection surface; any synthesis, write-back, promotion, app wiring, runtime action, model call, or tool use needs a separate scoped lane.
