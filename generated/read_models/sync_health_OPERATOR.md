# OpenClaw Sync Health

Trust status: `stale_needs_mac_sync`
Mirror status: `needs_mac_sync`
Display status: `needs_mac_sync`
Lifecycle state: `actionable_sync_failure`
Operator action required: `true`
Next expected actor: `mac_sync_agent`

Mirror counts:
- canonical_expected=247
- observed=218
- missing_expected=29
- extra=0
- hash_mismatch=4
- matched_hash=214

App-visible stable map:
- map_status: `map_generation_pending_mac_import`
- map_generation_id: `map_fbda77b8af4e9c796c03`
- bundle_hash: `sha256:d54194ee82f05e41724f26bb3def93f048f4552e6ff40914cfdf6227445bdb39`
- app_visible: `false`
- receipt_matches_pc_bundle: `false`
- agent_dossier_cards: `12` at `agent_council.agent_dossier_cards`
- agent_dossier_cards_path_status: `accepted_canonical_nested_path`
- package_preview_summary: `true` count=`8`
- tool_adapter_receipt_summary: `true` count=`12`
- front-door operator action required: `false`
- next expected actor: `mac_map_import_agent`
- next: Map generated on PC; waiting for Mac import receipt

Raw read-model mirror detail:
- raw_mirror_status: `raw_mirror_stale_or_mismatched`
- raw_mirror_blocks_app_visible_map: `true`

Check Transmission display:
- lamp_state: `WARNING`
- headline: Stable map bundle pending
- summary: Map generated on PC; waiting for Mac import receipt.

Recommended fix:
- kind: `request_mac_sync`
- display status: `needs_mac_sync`
- next expected actor: `mac_sync_agent`
- lifecycle state: `actionable_sync_failure`
- operator action required: `true`
- next: Request Mac sync through the shared marker and let the Mac LaunchAgent refresh the mirror.
- app can request bounded Mac sync marker: `true`

Proof:
- Mac heartbeat: `idle` at `2026-05-22T04:06:32+00:00`
- Mac completion: `synced` at `2026-05-21T18:25:34+00:00`
- PC import: `skipped_unchanged` at `2026-05-21T18:29:48+00:00`
- Windows task log present: `true`

Stale files:
- `agent_identity_actor_router_contract.json`
- `agent_identity_actor_router_contract_OPERATOR.md`
- `agent_memory_scope_contract.json`
- `agent_memory_scope_contract_OPERATOR.md`
- `agent_package_preview_contract.json`
- `agent_package_preview_contract_OPERATOR.md`
- `agent_platform_alignment.json`
- `agent_platform_alignment_OPERATOR.md`
- `agent_terrain_awareness_readback_contract.json`
- `agent_terrain_awareness_readback_contract_OPERATOR.md`
- `capital_hilton_proof_metadata_packet.json`
- `capital_hilton_proof_metadata_packet_OPERATOR.md`
- `memory_candidate_receipt_contract.json`
- `memory_candidate_receipt_contract_OPERATOR.md`
- `model_selection_policy_contract.json`
- `model_selection_policy_contract_OPERATOR.md`
- `model_selection_receipt_contract.json`
- `model_selection_receipt_contract_OPERATOR.md`
- `openclaw_map_OPERATOR.md`
- `openclaw_map_manifest.json`
- `openclaw_map_snapshot.json`
- `operator_map_bundle_contract.json`
- `operator_map_bundle_contract_OPERATOR.md`
- `operator_threshold_map_contract.json`
- `operator_threshold_map_contract_OPERATOR.md`
- `package_preview_receipt_contract.json`
- `package_preview_receipt_contract_OPERATOR.md`
- `system_health_lights_taxonomy.json`
- `system_health_lights_taxonomy_OPERATOR.md`
- `tool_adapter_receipt_contract.json`
- `tool_adapter_receipt_contract_OPERATOR.md`
- `tool_protocol_adapter_registry_contract.json`
- `tool_protocol_adapter_registry_contract_OPERATOR.md`

No-authority posture:
- `app_direct_execution_allowed`: `false`
- `arbitrary_command_allowed`: `false`
- `remote_control_allowed`: `false`
- `ssh_scp_rsync_allowed`: `false`
- `docker_ollama_allowed`: `false`
- `runtime_activation_allowed`: `false`
- `agent_activation_allowed`: `false`
- `file_delete_allowed`: `false`
- `file_move_allowed`: `false`

Boundary:
- Sync Health is a read-model and ledger snapshot only.
- It does not remote-control Mac or Windows, run arbitrary commands, modify Mission Control, or broaden sync authority.
