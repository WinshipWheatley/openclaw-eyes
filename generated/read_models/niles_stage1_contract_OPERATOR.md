# Niles Stage 1 Contract v0

Status:
- Contract status: `stage_1_schema_contracts_ready_metadata_only`.
- Stage 1 ready: `true`.
- Scope: schemas/contracts only.
- Metadata only: `true`.
- Taste calibration included: `false`.
- Master taste calibration required later: `true`.
- Raw audio ingest allowed: `false`.
- DAW session content ingest allowed: `false`.
- Broad private drive scan allowed: `false`.
- Audio/session mutation allowed: `false`.
- Release/publish authority added: `false`.
- Runtime/tool/model authority added: `false`.
- Send/submit authority added: `false`.
- Money/payment authority added: `false`.

## Existing Contracts
- `niles_album_evidence_intake_boundary` schema=`niles_album_evidence_intake_boundary_v0` module_present=`true` read_model_present=`true` role=metadata-only evidence boundary and forbidden input contract.
- `niles_album_metadata_intake_packet` schema=`niles_album_metadata_intake_packet_v0` module_present=`true` read_model_present=`true` role=operator-facing metadata placeholder packet.
- `niles_album_review_packet` schema=`niles_album_review_packet_v0` module_present=`true` read_model_present=`true` role=review-only packet from governed evidence.
- `niles_album_matrix_review` schema=`niles_album_matrix_review_v0` module_present=`true` read_model_present=`true` role=metadata-only album matrix review read-model.

## Stage Gates
- `stage_1_schema_contracts` status=`ready` owner=`codex_builder` allowed_now=`true`.
- `stage_2_operator_metadata_fill` status=`future_operator_input_needed` owner=`operator` allowed_now=`false`.
- `stage_3_review_matrix` status=`future_ready_after_stage_2` owner=`niles_review_lane` allowed_now=`false`.
- `stage_4_taste_calibration_master_only` status=`blocked_until_master_calibration` owner=`master` allowed_now=`false`.
- `stage_5_release_publish_future_gate` status=`blocked_future_gate` owner=`master_and_operator` allowed_now=`false`.

## Master Taste Calibration
- Taste calibration is not performed in Stage 1.
- The master owns taste calibration later before any taste-sensitive or release-sensitive claims.

## Blocked Boundaries
- `raw_audio` remains blocked.
- `daw_session_contents` remains blocked.
- `stems_mixes_masters` remains blocked.
- `broad_folder_scans` remains blocked.
- `private_drive_crawl` remains blocked.
- `audio_or_session_file_mutation` remains blocked.
- `logic_or_ableton_automation` remains blocked.
- `repo_b_runtime_execution` remains blocked.
- `model_or_tool_runtime_execution` remains blocked.
- `external_send_or_submit` remains blocked.
- `release_or_publish_action` remains blocked.
- `money_or_payment_action` remains blocked.

## Next Safe Move
- Use the existing Niles metadata intake packet to supply governed metadata labels later; do not provide raw audio, DAW/session contents, or private-drive crawl requests.

## Machine Proof
- Content hash: `a080a9fe468843191d34b0e7fe64a18f985f565837d41a6576faf4a70ba50a08`.
- Source contracts: `4`.
- Missing source contracts: `0`.
- Blocked boundaries: `12`.
