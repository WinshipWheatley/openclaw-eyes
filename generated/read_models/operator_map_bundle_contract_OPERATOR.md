# Operator Map Bundle Contract v0

## Summary

Mission Control should consume a stable map snapshot instead of treating the full generated read-model file set as the app contract.

## Path Audit

- Repo A generated source: `/home/openclaw/generated/read_models`
- Returned Mac manifest: `/mnt/e/openclaw/mac_generated_read_models_manifest.json`
- E-drive shuttle export path: `/mnt/e/openclaw/shuttle/to_mac`
- Mac expected mount path: `/Volumes/openclaw_e`
- Mac local mirror path: `/Users/hwinshipwheatley/openclaw_generated_read_models`
- Sync request marker: `/mnt/e/openclaw/shuttle/to_mac/read_model_sync_required.json`
- Mac completion marker: `/mnt/e/openclaw/shuttle/from_mac/read_model_sync_completed.json`
- PC import/readback state: `/home/openclaw/.openclaw/state/read_model_import_agent_state.json`
- Threshold break classification: `pc_proof_or_hash_readback_stale_after_manifest`
- Threshold break reason: The returned Mac manifest has the threshold files, but PC sync health still sees missing or hash-mismatched canonical files.

## Stable App Contract

- Snapshot: `openclaw_map_snapshot.json`
- Manifest: `openclaw_map_manifest.json`
- Operator digest: `openclaw_map_OPERATOR.md`
- Map generation: `map_f47cef0e17a00622c5a2`
- Bundle hash: `sha256:f6c9dbcdc5a014714f2fd24a0cdc8a3a855112995297a024eee3bdb1c46a661e`
- Stable app-facing file count: `3`

## Sync Health Split

- Raw read-model count remains proof/detail.
- Map generation/receipt agreement becomes the app-visible Check Transmission source truth once Mac implements the stable reader.
- Current map receipt validation: `map_generation_pending_mac_import`

## Mac-Side Change Required

- Read `/Users/hwinshipwheatley/openclaw_generated_read_models/openclaw_map_manifest.json`.
- Read `/Users/hwinshipwheatley/openclaw_generated_read_models/openclaw_map_snapshot.json`.
- Optionally show `/Users/hwinshipwheatley/openclaw_generated_read_models/openclaw_map_OPERATOR.md`.
- Entitle those stable paths once; do not add a new entitlement for every future proof-detail read-model.
- If missing, fail closed as map unavailable; if stale, show map sync pending.

## Boundary

- `agent_activation_allowed` = `False`
- `browser_oauth_account_access_allowed` = `False`
- `cleanup_remount_repair_allowed` = `False`
- `credentials_included` = `False`
- `external_model_api_allowed` = `False`
- `file_delete_allowed` = `False`
- `file_move_allowed` = `False`
- `gmail_calendar_coupa_telegram_allowed` = `False`
- `map_snapshot_only` = `True`
- `metadata_only` = `True`
- `mission_control_app_changed` = `False`
- `model_execution_allowed` = `False`
- `network_operation_allowed` = `False`
- `pc_c_drive_artifact_write_allowed` = `False`
- `planner_builder_queue_allowed` = `False`
- `raw_private_bodies_included` = `False`
- `read_model_only` = `True`
- `runtime_activation_allowed` = `False`
- `secrets_included` = `False`
- `send_submit_approval_allowed` = `False`
- `tool_plugin_execution_allowed` = `False`
