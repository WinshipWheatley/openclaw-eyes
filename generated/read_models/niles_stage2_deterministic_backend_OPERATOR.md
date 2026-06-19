# Niles Stage 2 Deterministic Backend v0

Status:
- Stage 2 status: `blocked_needs_governed_operator_metadata`.
- Evaluated records: `0`.
- Review-ready records: `0`.
- Blocked records: `0`.
- Album state confirmed: `false`.
- Runtime authority added: `false`.
- Send/submit authority added: `false`.
- Approval authority added: `false`.

## Deterministic Pipeline
- `input_normalize`
- `evidence_classify`
- `weighted_score`
- `gate_evaluate`
- `hard_flag_block`

## Evaluations
- No governed operator metadata records are present.

## Authority Boundary
- `stage2_backend_only` = `true`
- `deterministic_backend` = `true`
- `metadata_only` = `true`
- `review_only` = `true`
- `taste_calibration_complete` = `false`
- `album_state_confirmed` = `false`
- `raw_audio_ingest_allowed` = `false`
- `daw_session_content_ingest_allowed` = `false`
- `broad_private_drive_scan_allowed` = `false`
- `logic_or_ableton_open_allowed` = `false`
- `daw_automation_allowed` = `false`
- `audio_file_mutation_allowed` = `false`
- `finder_file_operation_allowed` = `false`
- `repo_b_runtime_allowed` = `false`
- `runtime_authority_added` = `false`
- `tool_execution_authority_added` = `false`
- `model_execution_authority_added` = `false`
- `send_or_submit_authority_added` = `false`
- `approval_authority_added` = `false`
- `mission_control_app_changed` = `false`

## Next Safe Move
- Collect governed operator metadata through the Niles album evidence intake boundary.
