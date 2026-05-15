# Read-Model Index

Selected read-model files copied into `selected_read_models/`:
- `generated_current_state.md` (12400 bytes, human_operator_summary)
- `generated_next_actions.md` (1481 bytes, human_operator_summary)
- `agent_runtime_readiness_OPERATOR.md` (2216 bytes, human_operator_summary)
- `agent_runtime_readiness.json` (7791 bytes, selected_machine_state_json)
- `intent_router_OPERATOR.md` (1721 bytes, human_operator_summary)
- `intent_router.json` (4878 bytes, selected_machine_state_json)
- `agent_lanes_OPERATOR.md` (2009 bytes, human_operator_summary)
- `agent_lanes.json` (23683 bytes, selected_machine_state_json)
- `operator_actions_OPERATOR.md` (2306 bytes, human_operator_summary)
- `operator_actions.json` (5332 bytes, selected_machine_state_json)
- `agent_work_packets.json` (2801 bytes, selected_machine_state_json)
- `agent_work_packets_OPERATOR.md` (840 bytes, human_operator_summary)
- `artifact_registry.operator.txt` (1425 bytes, human_operator_summary)
- `context_selection.json` (5124 bytes, selected_machine_state_json)
- `context_selection_OPERATOR.md` (1812 bytes, human_operator_summary)
- `dropped_intents.json` (14607 bytes, selected_machine_state_json)
- `dropped_intents_OPERATOR.md` (1728 bytes, human_operator_summary)
- `evidence_freshness.operator.txt` (1148 bytes, human_operator_summary)
- `helm_state.operator.txt` (1978 bytes, human_operator_summary)
- `markdown_evidence.json` (15212 bytes, selected_machine_state_json)
- `markdown_evidence_OPERATOR.md` (760 bytes, human_operator_summary)
- `project_capsules.json` (19452 bytes, selected_machine_state_json)
- `project_capsules_OPERATOR.md` (1103 bytes, human_operator_summary)
- `recent_file_context.json` (8520 bytes, selected_machine_state_json)
- `recent_file_context_OPERATOR.md` (961 bytes, human_operator_summary)
- `report_bridge.json` (2996 bytes, selected_machine_state_json)
- `report_bridge_OPERATOR.md` (1263 bytes, human_operator_summary)
- `runtime_activation_gate.operator.txt` (1015 bytes, human_operator_summary)
- `source_inventory.operator.txt` (1413 bytes, human_operator_summary)
- `tool_intake_OPERATOR.md` (3802 bytes, human_operator_summary)
- `tool_inventory_OPERATOR.md` (2149 bytes, human_operator_summary)
- `world_domain_registry.operator.txt` (1347 bytes, human_operator_summary)
- `world_status.operator.txt` (963 bytes, human_operator_summary)

Available safe generated read-model files not copied into this focused pack:
- `artifact_registry.json`
- `evidence_freshness.json`
- `helm_state.json`
- `runtime_activation_gate.json`
- `source_inventory.json`
- `tool_intake.json`
- `tool_inventory.json`
- `world_domain_registry.json`
- `world_status.json`

Selection policy:
- Human/operator Markdown and text companions are included dynamically.
- JSON inclusion is limited to selected machine-state surfaces.
- Manifests, SQLite files, temp files, hidden files, and no-go/private path hints are excluded.
