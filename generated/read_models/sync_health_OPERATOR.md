# OpenClaw Sync Health

Trust status: `trusted`
Mirror status: `ok`
Display status: `current`
Lifecycle state: `trusted_current`
Operator action required: `false`
Next expected actor: `none`

Mirror counts:
- canonical_expected=297
- observed=298
- missing_expected=0
- extra=1
- hash_mismatch=0
- matched_hash=290

App-visible stable map:
- map_status: `map_current`
- map_generation_id: `map_fa2eb18cb51aaf46e523`
- bundle_hash: `sha256:f1c56ecc5e39a3b58a0f78f094a9a94ffc35fac10539324f74c4c6353a75d491`
- app_visible: `true`
- receipt_matches_pc_bundle: `true`
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
- next expected actor: `none`
- next: none

Raw read-model mirror detail:
- raw_mirror_status: `raw_mirror_current`
- raw_mirror_blocks_app_visible_map: `false`

Check Transmission display:
- lamp_state: `QUIET`
- headline: Stable map bundle current
- summary: Mission Control can trust the app-facing map bundle; raw read-model differences stay in proof/detail.

Raw read-model mirror proof/detail recommendation:
- kind: `none`
- display status: `current`
- next expected actor: `none`
- lifecycle state: `trusted_current`
- operator action required: `false`
- next: No sync repair is needed; volatile PC proof surfaces are newer than the Mac manifest but the imported mirror content is current.
- app can request bounded Mac sync marker: `false`

Proof:
- Mac heartbeat: `idle` at `2026-05-23T20:25:42+00:00`
- Mac completion: `synced` at `2026-05-23T20:20:41+00:00`
- PC import: `skipped_unchanged` at `2026-05-23T20:21:25+00:00`
- Windows task log present: `true`

Extra files:
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
