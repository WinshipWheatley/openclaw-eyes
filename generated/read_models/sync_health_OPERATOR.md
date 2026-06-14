# OpenClaw Sync Health

Trust status: `trusted`
Mirror status: `ok`
Display status: `current`
Lifecycle state: `trusted_current`
Operator action required: `false`
Next expected actor: `none`

Mirror counts:
- canonical_expected=325
- observed=327
- missing_expected=0
- extra=2
- hash_mismatch=0
- matched_hash=318
- expected_set_basis=mac_sync_latest_safe_selector
- extra_file_handling=review_only_nonblocking

App-visible stable map:
- map_status: `map_hash_mismatch`
- map_generation_id: `map_026ef93525eeecb84798`
- bundle_hash: `sha256:334659e94b5f815635e0d4fc82fb5bb4b6a1a379da2ab80c6e4a560ea2fdde9b`
- app_visible: `false`
- receipt_matches_pc_bundle: `false`
- agent_dossier_cards: `12` at `agent_council.agent_dossier_cards`
- agent_dossier_cards_path_status: `accepted_canonical_nested_path`
- package_preview_summary: `true` count=`8`
- tool_adapter_receipt_summary: `true` count=`12`
- capital_hilton_summary: `true` missing_proof=`10` protected_proof=`true`
- capital_hilton_protected_proof_intake: `true` proof_items=`10` missing_proof=`10` protected_proof=`true` candidate_facts_proven=`false`
- capital_hilton_authority_flags_false: `true`
- security_audit_readiness: `true` ready_for_pass=`true` approval=`false` action_authority=`false`
- security_coverage_gaps: `5` parked_breadcrumbs=`15`
- security_pass: `true` completed=`true` read_only=`true` preview=`true` action_authority=`false`
- security_pass_worker_orphan_chief_hermes: worker=`true` orphaned=`true` chief_hermes=`true`
- post_security_governance_batch: `true` parked_capital=`true` security_delta=`true` attention_promotion=`true` chief_cross_off=`true`
- front-door operator action required: `false`
- next expected actor: `mac_map_import_agent`
- next: re-import stable map bundle through the normal map sync lifecycle

Raw read-model mirror detail:
- raw_mirror_status: `raw_mirror_current`
- raw_mirror_blocks_app_visible_map: `false`

Check Transmission display:
- lamp_state: `ON`
- headline: Stable map bundle hash mismatch
- summary: Mac map receipt or files do not match the current PC bundle hash.

Recommended fix:
- kind: `none`
- display status: `current`
- next expected actor: `none`
- lifecycle state: `trusted_current`
- operator action required: `false`
- next: No sync repair is needed; volatile PC proof surfaces are newer than the Mac manifest but the imported mirror content is current.
- app can request bounded Mac sync marker: `false`

Proof:
- Mac heartbeat: `idle` at `2026-06-12T03:28:20+00:00`
- Mac completion: `synced` at `2026-06-12T02:08:11+00:00`
- PC import: `skipped_unchanged` at `2026-06-12T02:09:57+00:00`
- Windows task log present: `true`

Extra files:
- `chat_readback_card_mirror.json`
- `openclaw_map_receipt.json`

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
