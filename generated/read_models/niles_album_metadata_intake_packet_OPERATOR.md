# Niles Album Metadata Intake Packet v0

Status:
- Intake packet status: `template_ready_no_real_metadata_recorded`.
- Template uses placeholders, not album facts: `true`.
- Real album metadata recorded: `false`.
- Metadata record count: `0`.
- Operator metadata is evidence, not final truth: `true`.
- Raw audio ingest allowed: `false`.
- DAW session content ingest allowed: `false`.
- Broad private drive scan allowed: `false`.
- DAW automation added: `false`.
- Audio/session file mutation added: `false`.
- Runtime authority added: `false`.
- Send/submit authority added: `false`.
- Approval authority added: `false`.

## Allowed Fields
- album_project_name, song_title, song_id_or_stable_operator_label, track_status_label, production_stage_label, source_reference_path_label, daw_session_existence_flag, last_known_operator_update, blocker_labels, next_safe_move_labels, confidence, evidence_status, operator_supplied, no_external_action.

## Minimum Useful Fields
- song_title, song_id_or_stable_operator_label, blocker_labels.
- Provide song_title or song_id_or_stable_operator_label; blocker labels are useful even when status/stage remain unknown.

## Optional Fields
- album_project_name, track_status_label, production_stage_label, source_reference_path_label, daw_session_existence_flag, last_known_operator_update, next_safe_move_labels, confidence, evidence_status.

## Operator Input Template
```json
{
  "metadata_records": [
    {
      "album_project_name": null,
      "blocker_labels": [],
      "confidence": null,
      "daw_session_existence_flag": null,
      "evidence_status": "operator_supplied_pending_review",
      "last_known_operator_update": null,
      "next_safe_move_labels": [],
      "no_external_action": true,
      "operator_supplied": true,
      "production_stage_label": null,
      "song_id_or_stable_operator_label": null,
      "song_title": null,
      "source_reference_path_label": null,
      "track_status_label": null
    }
  ],
  "packet_label": "niles_album_metadata_operator_input_template_v0",
  "template_uses_placeholders_not_facts": true
}
```

## Allowed Input Posture
- operator-supplied metadata only.
- stable operator labels.
- high-level status labels.
- high-level blocker labels.
- high-level next-safe-move labels.
- safe source reference labels, not raw private paths unless a later protected path policy explicitly permits them.

## Forbidden Boundaries
- raw_audio_ingest: `forbidden`.
- daw_session_content_ingest: `forbidden`.
- broad_private_drive_scan: `forbidden`.
- daw_automation: `forbidden`.
- audio_or_session_file_mutation: `forbidden`.
- metadata_as_final_truth: `forbidden`.
- repo_b_runtime_execution: `forbidden`.

## Existing Backend Flow
- Step 1: Fill a copy of operator_facing_input_template with governed metadata labels. (operator_metadata_only).
- Step 2: Pass that JSON to scripts/export_niles_album_evidence_intake_boundary.py --metadata-input-json <path>. (documented_command_path_only_not_executed_by_this_packet).
- Step 3: Regenerate Niles review packet so it consumes the intake state. (read_model_consumption_only).
- Step 4: Regenerate Niles matrix review so rows appear from governed metadata. (read_model_consumption_only).
- Step 5: Sync generated read-models for Mission Control to show the updated state later. (sync_marker_or_existing_sync_flow_only).

## Next Safe Operator Action
- Fill the placeholder metadata packet with governed album/song labels, not raw audio or DAW/session content.
