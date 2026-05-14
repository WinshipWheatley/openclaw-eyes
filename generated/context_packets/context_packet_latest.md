# Context Selection Knowledge Packet v0

Evidence:
- Packet `ctxpacket_dc4aa1c1c9f43fbe6753` selected 60 bounded evidence items.
- Query: `{
  "category": null,
  "limit": 60,
  "task": "prepare Mission Control frontend prompt",
  "task_category_hints": [
    "runtime_gate",
    "helm_state",
    "world_registry",
    "world_status",
    "artifact_registry",
    "source_inventory",
    "evidence_freshness",
    "operator_status",
    "unsupported_capability",
    "future_gated_capability",
    "generated_read_model_fact"
  ],
  "world": "build"
}`.
- Evidence labels: future_gated_capability=12, generated_read_model_fact=40, unsupported_claim=8.
- Evidence categories: artifact_registry=4, evidence_freshness=10, helm_state=3, operator_status=4, runtime_gate=31, unsupported_capability=8.
- World bindings: build, cross_world.

Selected items:
- generated/read_models/helm_state.json :: future_gated_capability / runtime_gate / missing_prerequisite:dry_run_proof
- generated/read_models/runtime_activation_gate.json :: future_gated_capability / runtime_gate / missing_prerequisite:dry_run_proof
- generated/read_models/helm_state.json :: future_gated_capability / runtime_gate / missing_prerequisite:explicit_operator_approval
- generated/read_models/runtime_activation_gate.json :: future_gated_capability / runtime_gate / missing_prerequisite:explicit_operator_approval
- generated/read_models/helm_state.json :: future_gated_capability / runtime_gate / missing_prerequisite:logging_receipt_path
- generated/read_models/runtime_activation_gate.json :: future_gated_capability / runtime_gate / missing_prerequisite:logging_receipt_path
- generated/read_models/helm_state.json :: future_gated_capability / runtime_gate / missing_prerequisite:module_manifest_validation
- generated/read_models/runtime_activation_gate.json :: future_gated_capability / runtime_gate / missing_prerequisite:module_manifest_validation
- generated/read_models/helm_state.json :: future_gated_capability / runtime_gate / missing_prerequisite:rollback_plan
- generated/read_models/runtime_activation_gate.json :: future_gated_capability / runtime_gate / missing_prerequisite:rollback_plan
- generated/read_models/helm_state.json :: future_gated_capability / runtime_gate / missing_prerequisite:runtime_boundary_declaration
- generated/read_models/runtime_activation_gate.json :: future_gated_capability / runtime_gate / missing_prerequisite:runtime_boundary_declaration
- generated/read_models/helm_state.json :: unsupported_claim / unsupported_capability / agent_presence_supported
- generated/read_models/world_domain_registry.json :: unsupported_claim / unsupported_capability / agent_presence_supported
- generated/read_models/world_status.json :: unsupported_claim / unsupported_capability / agent_presence_supported
- generated/read_models/world_domain_registry.json :: unsupported_claim / unsupported_capability / dynamic_world_state
- generated/read_models/world_status.json :: unsupported_claim / unsupported_capability / dynamic_world_state
- generated/read_models/helm_state.json :: unsupported_claim / unsupported_capability / strategic_gravity_supported
- generated/read_models/world_domain_registry.json :: unsupported_claim / unsupported_capability / strategic_gravity_supported
- generated/read_models/world_status.json :: unsupported_claim / unsupported_capability / strategic_gravity_supported

Future/unsupported facts:
- generated/read_models/helm_state.json :: future_gated_capability / missing_prerequisite:dry_run_proof
- generated/read_models/runtime_activation_gate.json :: future_gated_capability / missing_prerequisite:dry_run_proof
- generated/read_models/helm_state.json :: future_gated_capability / missing_prerequisite:explicit_operator_approval
- generated/read_models/runtime_activation_gate.json :: future_gated_capability / missing_prerequisite:explicit_operator_approval
- generated/read_models/helm_state.json :: future_gated_capability / missing_prerequisite:logging_receipt_path
- generated/read_models/runtime_activation_gate.json :: future_gated_capability / missing_prerequisite:logging_receipt_path
- generated/read_models/helm_state.json :: future_gated_capability / missing_prerequisite:module_manifest_validation
- generated/read_models/runtime_activation_gate.json :: future_gated_capability / missing_prerequisite:module_manifest_validation
- generated/read_models/helm_state.json :: future_gated_capability / missing_prerequisite:rollback_plan
- generated/read_models/runtime_activation_gate.json :: future_gated_capability / missing_prerequisite:rollback_plan
- generated/read_models/helm_state.json :: future_gated_capability / missing_prerequisite:runtime_boundary_declaration
- generated/read_models/runtime_activation_gate.json :: future_gated_capability / missing_prerequisite:runtime_boundary_declaration

Next safe moves:
- generated/read_models/helm_state.json :: Generated helm state names the next safe move.
- generated/read_models/runtime_activation_gate.json :: Runtime gate names the next safe move.

Boundary:
- This is selected evidence and bounded context, not truth promotion.
- Unknown, needs-review, sensitive, blocked, and no-go material is excluded.
- Receipt summaries remain metadata only; raw private/no-go bodies are not included.
- No generic RAG, vector search, embeddings, model calls, tool execution, network calls, or runtime activation are used.

Blocked:
- Excluded records recorded: 200.
- No-go exclusion count: 754.
- runtime_authority=false; model_execution_allowed=false; container_execution_allowed=false; remote_access_allowed=false.

Next safe move:
- Use this packet as reasoning context only; any synthesis, write-back, promotion, runtime action, or tool use needs a separate scoped lane.
