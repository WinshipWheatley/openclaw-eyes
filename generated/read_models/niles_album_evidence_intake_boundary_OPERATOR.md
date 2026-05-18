# Niles Album Evidence Intake Boundary v0

Status:
- Boundary status: `contract_ready_no_real_metadata_recorded`.
- Metadata-only intake contract added: `true`.
- Real album metadata recorded: `false`.
- Metadata records: `0`.
- Unknown album state remains unknown: `true`.
- Raw audio ingest allowed: `false`.
- DAW session content ingest allowed: `false`.
- Broad private drive scan allowed: `false`.

## Metadata Intake Command
- `python3 scripts/export_niles_album_evidence_intake_boundary.py --metadata-input-json <path>`

## Recorded Operator Metadata
- None recorded. Empty/pending template only.

## Allowed Metadata Types
- `album_project_name`: Operator-supplied album/project label; not inferred from folders. Policy: operator_supplied_label_or_null.
- `song_title`: Operator-supplied song title or working title. Policy: operator_supplied_label_or_null.
- `song_id_or_stable_operator_label`: A stable operator label that can survive title changes. Policy: operator_supplied_stable_label_or_null.
- `track_status_label`: Status label supplied by the operator, such as idea, tracking, editing, mixing, review, parked, or done. Policy: operator_supplied_enum_or_null.
- `production_stage_label`: Production-stage label supplied by the operator; not derived from DAW/session inspection. Policy: operator_supplied_enum_or_null.
- `source_reference_path_label`: A path label or human reference for where evidence lives; the path is not opened or scanned by this contract. Policy: operator_supplied_reference_label_or_null.
- `daw_session_existence_flag`: Operator-supplied yes/no/unknown flag that a DAW session exists; no DAW content is read. Policy: operator_supplied_boolean_or_null.
- `last_known_operator_update`: Operator-supplied last-known status update date or short note. Policy: operator_supplied_date_or_text_or_null.
- `blocker_labels`: Operator-supplied blocker labels; no private notes or lyrics. Policy: operator_supplied_list_or_empty.
- `next_safe_move_labels`: Operator-supplied next safe move labels for Niles to review later. Policy: operator_supplied_list_or_empty.
- `confidence`: Confidence in the metadata supplied, not confidence in raw audio/session contents. Policy: operator_supplied_low_medium_high_or_null.
- `evidence_status`: Evidence posture for metadata only; it does not certify audio/session truth. Policy: operator_supplied_pending_review_confirmed_or_stale.

## Blocked Evidence Types
- `raw_audio`
- `daw_session_contents`
- `stems_mixes_masters`
- `broad_folder_scans`
- `private_drive_crawl`
- `inferred_song_status_without_evidence`
- `automatic_file_mutation`
- `unapproved_lyrics_ingest`
- `unapproved_private_notes_ingest`
- `repo_b_runtime_execution`

## First Safe Metadata Packet Shape
- Empty/pending template is included in JSON under `operator_supplied_metadata_packet_shape.empty_pending_template`.
- Synthetic/test example is included in JSON and explicitly marked `synthetic_or_test=true`.

## Proof Requirements
- Operator supplies metadata-only packet with at least album_project_name or stable song label.
- Every metadata record declares evidence_status and confidence.
- Any source reference is a label/reference only and is not opened or scanned by OpenClaw.
- Raw audio, DAW session contents, stems, mixes, masters, lyrics, and private notes remain outside normal read-models.
- A later Niles review packet consumes only governed metadata, not raw files.

## Authority Boundary
- `metadata_only_intake_contract` = `true`
- `real_album_metadata_recorded` = `false`
- `raw_audio_ingest_allowed` = `false`
- `daw_session_content_ingest_allowed` = `false`
- `broad_private_drive_scan_allowed` = `false`
- `daw_automation_allowed` = `false`
- `audio_file_mutation_allowed` = `false`
- `finder_file_operation_allowed` = `false`
- `repo_b_authority_allowed` = `false`
- `runtime_authority_added` = `false`
- `tool_execution_authority_added` = `false`
- `model_execution_authority_added` = `false`
- `send_or_submit_authority_added` = `false`
- `mission_control_app_changed` = `false`

## Next Recommended Lane
- Niles Album Review Packet Metadata Consumption v0
