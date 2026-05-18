"""Niles album evidence intake boundary v0.

Defines a metadata-only intake contract for future Niles album/project evidence.
This module writes deterministic read-models only. It does not scan drives, read
raw audio, open DAWs, mutate files, run Repo B, or grant runtime/send authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "niles_album_evidence_intake_boundary_v0"
JSON_EXPORT_NAME = "niles_album_evidence_intake_boundary.json"
OPERATOR_EXPORT_NAME = "niles_album_evidence_intake_boundary_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

ALLOWED_FIELD_NAMES = (
    "album_project_name",
    "song_title",
    "song_id_or_stable_operator_label",
    "track_status_label",
    "production_stage_label",
    "source_reference_path_label",
    "daw_session_existence_flag",
    "last_known_operator_update",
    "blocker_labels",
    "next_safe_move_labels",
    "confidence",
    "evidence_status",
    "operator_supplied",
    "no_external_action",
)

ALLOWED_METADATA_TYPES = (
    {
        "field_name": "album_project_name",
        "value_policy": "operator_supplied_label_or_null",
        "description": "Operator-supplied album/project label; not inferred from folders.",
        "metadata_only": True,
    },
    {
        "field_name": "song_title",
        "value_policy": "operator_supplied_label_or_null",
        "description": "Operator-supplied song title or working title.",
        "metadata_only": True,
    },
    {
        "field_name": "song_id_or_stable_operator_label",
        "value_policy": "operator_supplied_stable_label_or_null",
        "description": "A stable operator label that can survive title changes.",
        "metadata_only": True,
    },
    {
        "field_name": "track_status_label",
        "value_policy": "operator_supplied_enum_or_null",
        "description": "Status label supplied by the operator, such as idea, tracking, editing, mixing, review, parked, or done.",
        "metadata_only": True,
    },
    {
        "field_name": "production_stage_label",
        "value_policy": "operator_supplied_enum_or_null",
        "description": "Production-stage label supplied by the operator; not derived from DAW/session inspection.",
        "metadata_only": True,
    },
    {
        "field_name": "source_reference_path_label",
        "value_policy": "operator_supplied_reference_label_or_null",
        "description": "A path label or human reference for where evidence lives; the path is not opened or scanned by this contract.",
        "metadata_only": True,
    },
    {
        "field_name": "daw_session_existence_flag",
        "value_policy": "operator_supplied_boolean_or_null",
        "description": "Operator-supplied yes/no/unknown flag that a DAW session exists; no DAW content is read.",
        "metadata_only": True,
    },
    {
        "field_name": "last_known_operator_update",
        "value_policy": "operator_supplied_date_or_text_or_null",
        "description": "Operator-supplied last-known status update date or short note.",
        "metadata_only": True,
    },
    {
        "field_name": "blocker_labels",
        "value_policy": "operator_supplied_list_or_empty",
        "description": "Operator-supplied blocker labels; no private notes or lyrics.",
        "metadata_only": True,
    },
    {
        "field_name": "next_safe_move_labels",
        "value_policy": "operator_supplied_list_or_empty",
        "description": "Operator-supplied next safe move labels for Niles to review later.",
        "metadata_only": True,
    },
    {
        "field_name": "confidence",
        "value_policy": "operator_supplied_low_medium_high_or_null",
        "description": "Confidence in the metadata supplied, not confidence in raw audio/session contents.",
        "metadata_only": True,
    },
    {
        "field_name": "evidence_status",
        "value_policy": "operator_supplied_pending_review_confirmed_or_stale",
        "description": "Evidence posture for metadata only; it does not certify audio/session truth.",
        "metadata_only": True,
    },
)

BLOCKED_EVIDENCE_TYPES = (
    "raw_audio",
    "daw_session_contents",
    "stems_mixes_masters",
    "broad_folder_scans",
    "private_drive_crawl",
    "inferred_song_status_without_evidence",
    "automatic_file_mutation",
    "unapproved_lyrics_ingest",
    "unapproved_private_notes_ingest",
    "repo_b_runtime_execution",
)

BLOCKED_INPUT_KEYS = (
    "raw_audio",
    "raw_audio_path",
    "audio_file_path",
    "daw_session_contents",
    "logic_session_contents",
    "ableton_session_contents",
    "stem_file",
    "mix_file",
    "master_file",
    "lyrics",
    "private_notes",
    "broad_folder_scan",
    "private_drive_crawl",
    "file_mutation_request",
    "repo_b_runtime_execution",
)

NO_AUTHORITY_FLAGS = {
    "metadata_only_intake_contract": True,
    "real_album_metadata_recorded": False,
    "raw_audio_ingest_allowed": False,
    "daw_session_content_ingest_allowed": False,
    "broad_private_drive_scan_allowed": False,
    "daw_automation_allowed": False,
    "audio_file_mutation_allowed": False,
    "finder_file_operation_allowed": False,
    "repo_b_authority_allowed": False,
    "runtime_authority_added": False,
    "tool_execution_authority_added": False,
    "model_execution_authority_added": False,
    "send_or_submit_authority_added": False,
    "mission_control_app_changed": False,
}


@dataclass(frozen=True)
class NilesAlbumEvidenceIntakeBoundaryResult:
    schema_version: str
    boundary_status: str
    json_path: str
    operator_path: str
    allowed_metadata_type_count: int
    blocked_evidence_type_count: int
    real_album_metadata_recorded: bool
    metadata_record_count: int
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rooted(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _read_json(path: str | Path) -> Any:
    return json.loads(_rooted(path).read_text(encoding="utf-8"))


def _empty_pending_template() -> dict[str, Any]:
    return {
        "template_id": "niles_album_metadata_empty_pending_template_v0",
        "template_status": "empty_pending_no_real_metadata_recorded",
        "synthetic_or_test": False,
        "operator_supplied": False,
        "no_external_action": True,
        "metadata_records": [_empty_metadata_record()],
    }


def _empty_metadata_record() -> dict[str, Any]:
    return {
        "album_project_name": None,
        "song_title": None,
        "song_id_or_stable_operator_label": None,
        "track_status_label": None,
        "production_stage_label": None,
        "source_reference_path_label": None,
        "daw_session_existence_flag": None,
        "last_known_operator_update": None,
        "blocker_labels": [],
        "next_safe_move_labels": [],
        "confidence": None,
        "evidence_status": "pending_not_recorded",
        "operator_supplied": False,
        "no_external_action": True,
    }


def _synthetic_example() -> dict[str, Any]:
    return {
        "template_id": "niles_album_metadata_synthetic_test_example_v0",
        "template_status": "synthetic_example_not_real_metadata",
        "synthetic_or_test": True,
        "operator_supplied": False,
        "no_external_action": True,
        "metadata_records": [
            {
                "album_project_name": "SYNTHETIC TEST ALBUM - not real",
                "song_title": "SYNTHETIC TEST SONG - not real",
                "song_id_or_stable_operator_label": "synthetic_song_001",
                "track_status_label": "mix_review",
                "production_stage_label": "synthetic_demo_stage",
                "source_reference_path_label": "operator://synthetic/local-reference-label-only",
                "daw_session_existence_flag": True,
                "last_known_operator_update": "2026-05-17 synthetic example",
                "blocker_labels": ["synthetic_blocker_missing_mix_notes"],
                "next_safe_move_labels": ["synthetic_next_review_metadata_only"],
                "confidence": "medium",
                "evidence_status": "synthetic_test_only_not_real_evidence",
                "operator_supplied": False,
                "no_external_action": True,
            }
        ],
    }


def _metadata_values_present(record: dict[str, Any]) -> bool:
    for key in ALLOWED_FIELD_NAMES:
        if key in {"operator_supplied", "no_external_action"}:
            continue
        value = record.get(key)
        if value not in (None, "", [], {}):
            return True
    return False


def _normalize_list(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} entries must be strings")
        normalized.append(item.strip())
    return [item for item in normalized if item]


def _safe_string_or_none(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or null")
    text = value.strip()
    return text or None


def _safe_bool_or_none(value: Any, *, field_name: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be true, false, or null")
    return value


def _validate_no_blocked_keys(record: dict[str, Any]) -> None:
    blocked = sorted(set(record).intersection(BLOCKED_INPUT_KEYS))
    if blocked:
        raise ValueError(f"blocked album metadata input keys: {', '.join(blocked)}")
    unknown = sorted(set(record) - set(ALLOWED_FIELD_NAMES))
    if unknown:
        raise ValueError(f"unsupported album metadata input keys: {', '.join(unknown)}")


def _normalize_metadata_record(record: dict[str, Any], *, index: int) -> dict[str, Any] | None:
    _validate_no_blocked_keys(record)
    operator_supplied = record.get("operator_supplied")
    no_external_action = record.get("no_external_action")
    if operator_supplied is not True:
        raise ValueError(f"metadata record {index} requires operator_supplied=true")
    if no_external_action is not True:
        raise ValueError(f"metadata record {index} requires no_external_action=true")
    normalized = {
        "album_project_name": _safe_string_or_none(record.get("album_project_name"), field_name="album_project_name"),
        "song_title": _safe_string_or_none(record.get("song_title"), field_name="song_title"),
        "song_id_or_stable_operator_label": _safe_string_or_none(record.get("song_id_or_stable_operator_label"), field_name="song_id_or_stable_operator_label"),
        "track_status_label": _safe_string_or_none(record.get("track_status_label"), field_name="track_status_label"),
        "production_stage_label": _safe_string_or_none(record.get("production_stage_label"), field_name="production_stage_label"),
        "source_reference_path_label": _safe_string_or_none(record.get("source_reference_path_label"), field_name="source_reference_path_label"),
        "daw_session_existence_flag": _safe_bool_or_none(record.get("daw_session_existence_flag"), field_name="daw_session_existence_flag"),
        "last_known_operator_update": _safe_string_or_none(record.get("last_known_operator_update"), field_name="last_known_operator_update"),
        "blocker_labels": _normalize_list(record.get("blocker_labels"), field_name="blocker_labels"),
        "next_safe_move_labels": _normalize_list(record.get("next_safe_move_labels"), field_name="next_safe_move_labels"),
        "confidence": _safe_string_or_none(record.get("confidence"), field_name="confidence"),
        "evidence_status": _safe_string_or_none(record.get("evidence_status"), field_name="evidence_status") or "operator_supplied_metadata_evidence",
        "operator_supplied": True,
        "no_external_action": True,
        "metadata_only": True,
        "raw_audio_stored": False,
        "daw_session_contents_stored": False,
        "file_opened_or_scanned": False,
        "album_state_confirmed": False,
    }
    if not _metadata_values_present(normalized):
        return None
    return normalized


def load_operator_metadata_input(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = _read_json(path)
    if isinstance(payload, dict):
        records = payload.get("metadata_records", [payload])
    elif isinstance(payload, list):
        records = payload
    else:
        raise ValueError("metadata input must be a JSON object or list")
    if not isinstance(records, list):
        raise ValueError("metadata_records must be a list")
    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"metadata record {index} must be an object")
        item = _normalize_metadata_record(record, index=index)
        if item is not None:
            normalized.append(item)
    return normalized


def build_niles_album_evidence_intake_boundary(
    *,
    metadata_input_json: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    metadata_records = load_operator_metadata_input(metadata_input_json)
    real_metadata_recorded = bool(metadata_records)
    boundary_status = (
        "operator_metadata_recorded_partial_evidence"
        if real_metadata_recorded
        else "contract_ready_no_real_metadata_recorded"
    )
    flags = {**NO_AUTHORITY_FLAGS, "real_album_metadata_recorded": real_metadata_recorded}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "boundary_id": "niles_album_evidence_intake_boundary",
        "workflow_domain": "music_art",
        "workflow_name": "Niles album progress review",
        "boundary_status": boundary_status,
        "purpose": "Define the safe metadata-only path before Niles album/session status can become governed evidence.",
        "allowed_metadata_types": list(ALLOWED_METADATA_TYPES),
        "blocked_evidence_types": list(BLOCKED_EVIDENCE_TYPES),
        "metadata_input_path_supported": True,
        "metadata_input_command": "python3 scripts/export_niles_album_evidence_intake_boundary.py --metadata-input-json <path>",
        "operator_metadata_intake_status": {
            "real_album_metadata_recorded": real_metadata_recorded,
            "metadata_record_count": len(metadata_records),
            "partial_metadata_intake_supported": True,
            "unknown_album_state_not_treated_as_confirmed": True,
            "album_state_confirmed": False,
        },
        "recorded_operator_metadata": metadata_records,
        "pending_or_unknown_album_evidence": [
            "album/source of truth remains incomplete unless operator metadata covers the project scope",
            "missing fields remain null rather than inferred",
            "track status labels are operator-supplied evidence, not final creative truth",
        ],
        "operator_supplied_metadata_packet_shape": {
            "packet_kind": "niles_album_operator_metadata_packet",
            "schema_hint": "metadata_only_no_raw_audio_or_daw_contents",
            "supported_metadata_fields": list(ALLOWED_FIELD_NAMES),
            "required_posture": [
                "operator_supplied=true for real metadata",
                "synthetic_or_test=false for real metadata",
                "no_external_action=true",
                "unknown values stay null",
                "do not paste lyrics, private notes, raw audio bodies, stems, mix files, master files, DAW session contents, credentials, or full private paths",
            ],
            "empty_pending_template": _empty_pending_template(),
            "synthetic_test_example": _synthetic_example(),
        },
        "proof_requirements_before_album_state_can_be_confirmed": [
            "Operator supplies metadata-only packet with at least album_project_name or stable song label.",
            "Every metadata record declares evidence_status and confidence.",
            "Any source reference is a label/reference only and is not opened or scanned by OpenClaw.",
            "Raw audio, DAW session contents, stems, mixes, masters, lyrics, and private notes remain outside normal read-models.",
            "A later Niles review packet consumes only governed metadata, not raw files.",
        ],
        "first_safe_next_step": "Operator fills a metadata-only Niles album packet from this template; OpenClaw can then record metadata evidence in this explicit intake path.",
        "real_album_metadata_recorded": real_metadata_recorded,
        "unknown_album_state_remains_unknown": True,
        "synthetic_examples_labeled": True,
        "source_policy": {
            "allowed_source_types": [
                "operator_supplied_metadata_json",
                "operator_supplied_path_label_without_file_open",
                "governed_repo_a_read_model_reference",
            ],
            "blocked_source_types": list(BLOCKED_EVIDENCE_TYPES),
            "existing_old_docs_files_are_evidence_not_truth": True,
        },
        "authority_boundary": flags,
        "receipt_proof_status": {
            "read_model_written": True,
            "operator_packet_written": True,
            "real_metadata_recorded": real_metadata_recorded,
            "external_action_taken": False,
        },
        "next_recommended_lane": "Niles Album Review Packet Metadata Consumption v0",
        **flags,
    }


def format_niles_album_evidence_intake_boundary(payload: dict[str, Any]) -> str:
    intake = payload["operator_metadata_intake_status"]
    lines = [
        "# Niles Album Evidence Intake Boundary v0",
        "",
        "Status:",
        f"- Boundary status: `{payload['boundary_status']}`.",
        "- Metadata-only intake contract added: `true`.",
        f"- Real album metadata recorded: `{str(intake['real_album_metadata_recorded']).lower()}`.",
        f"- Metadata records: `{intake['metadata_record_count']}`.",
        "- Unknown album state remains unknown: `true`.",
        "- Raw audio ingest allowed: `false`.",
        "- DAW session content ingest allowed: `false`.",
        "- Broad private drive scan allowed: `false`.",
        "",
        "## Metadata Intake Command",
        f"- `{payload['metadata_input_command']}`",
        "",
        "## Recorded Operator Metadata",
    ]
    if payload["recorded_operator_metadata"]:
        for record in payload["recorded_operator_metadata"]:
            label = record.get("song_title") or record.get("song_id_or_stable_operator_label") or record.get("album_project_name") or "metadata record"
            lines.append(
                f"- {label}: status={record.get('track_status_label') or '[unknown]'} stage={record.get('production_stage_label') or '[unknown]'} evidence={record.get('evidence_status')}"
            )
    else:
        lines.append("- None recorded. Empty/pending template only.")
    lines.extend(["", "## Allowed Metadata Types"])
    for item in payload["allowed_metadata_types"]:
        lines.append(f"- `{item['field_name']}`: {item['description']} Policy: {item['value_policy']}.")
    lines.extend(["", "## Blocked Evidence Types"])
    for item in payload["blocked_evidence_types"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## First Safe Metadata Packet Shape"])
    lines.append("- Empty/pending template is included in JSON under `operator_supplied_metadata_packet_shape.empty_pending_template`.")
    lines.append("- Synthetic/test example is included in JSON and explicitly marked `synthetic_or_test=true`.")
    lines.extend(["", "## Proof Requirements"])
    for item in payload["proof_requirements_before_album_state_can_be_confirmed"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Authority Boundary"])
    for key, value in payload["authority_boundary"].items():
        lines.append(f"- `{key}` = `{str(value).lower()}`")
    lines.extend(["", "## Next Recommended Lane", f"- {payload['next_recommended_lane']}", ""])
    return "\n".join(lines)


def export_niles_album_evidence_intake_boundary(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    metadata_input_json: str | Path | None = None,
    generated_at: str | None = None,
) -> NilesAlbumEvidenceIntakeBoundaryResult:
    payload = build_niles_album_evidence_intake_boundary(
        metadata_input_json=metadata_input_json,
        generated_at=generated_at,
    )
    root = _rooted(export_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_niles_album_evidence_intake_boundary(payload), encoding="utf-8")
    return NilesAlbumEvidenceIntakeBoundaryResult(
        schema_version=SCHEMA_VERSION,
        boundary_status=payload["boundary_status"],
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        allowed_metadata_type_count=len(payload["allowed_metadata_types"]),
        blocked_evidence_type_count=len(payload["blocked_evidence_types"]),
        real_album_metadata_recorded=payload["real_album_metadata_recorded"],
        metadata_record_count=len(payload["recorded_operator_metadata"]),
        runtime_authority_added=False,
        send_or_submit_authority_added=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Niles album evidence intake boundary.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--metadata-input-json", default=None)
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_niles_album_evidence_intake_boundary(
        export_root=args.export_root,
        metadata_input_json=args.metadata_input_json,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        payload = build_niles_album_evidence_intake_boundary(metadata_input_json=args.metadata_input_json)
        print(format_niles_album_evidence_intake_boundary(payload), end="")
    return 0


__all__ = [
    "ALLOWED_FIELD_NAMES",
    "ALLOWED_METADATA_TYPES",
    "BLOCKED_EVIDENCE_TYPES",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_niles_album_evidence_intake_boundary",
    "export_niles_album_evidence_intake_boundary",
    "format_niles_album_evidence_intake_boundary",
    "load_operator_metadata_input",
    "main",
]
