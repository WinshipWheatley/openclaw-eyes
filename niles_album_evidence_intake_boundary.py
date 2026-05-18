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


def _empty_pending_template() -> dict[str, Any]:
    return {
        "template_id": "niles_album_metadata_empty_pending_template_v0",
        "template_status": "empty_pending_no_real_metadata_recorded",
        "synthetic_or_test": False,
        "operator_supplied": False,
        "no_external_action": True,
        "metadata_records": [
            {
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
            }
        ],
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
            }
        ],
    }


def build_niles_album_evidence_intake_boundary(*, generated_at: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "boundary_id": "niles_album_evidence_intake_boundary",
        "workflow_domain": "music_art",
        "workflow_name": "Niles album progress review",
        "boundary_status": "contract_ready_no_real_metadata_recorded",
        "purpose": "Define the safe metadata-only path before Niles album/session status can become governed evidence.",
        "allowed_metadata_types": list(ALLOWED_METADATA_TYPES),
        "blocked_evidence_types": list(BLOCKED_EVIDENCE_TYPES),
        "operator_supplied_metadata_packet_shape": {
            "packet_kind": "niles_album_operator_metadata_packet",
            "schema_hint": "metadata_only_no_raw_audio_or_daw_contents",
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
        "first_safe_next_step": "Operator fills a metadata-only Niles album packet from this template; OpenClaw can then record metadata evidence in a later explicit intake lane.",
        "real_album_metadata_recorded": False,
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
        "authority_boundary": dict(NO_AUTHORITY_FLAGS),
        "receipt_proof_status": {
            "read_model_written": True,
            "operator_packet_written": True,
            "real_metadata_recorded": False,
            "external_action_taken": False,
        },
        "next_recommended_lane": "Niles Album Operator Metadata Intake v0",
        **NO_AUTHORITY_FLAGS,
    }


def format_niles_album_evidence_intake_boundary(payload: dict[str, Any]) -> str:
    lines = [
        "# Niles Album Evidence Intake Boundary v0",
        "",
        "Status:",
        f"- Boundary status: `{payload['boundary_status']}`.",
        "- Metadata-only intake contract added: `true`.",
        "- Real album metadata recorded: `false`.",
        "- Unknown album state remains unknown: `true`.",
        "- Raw audio ingest allowed: `false`.",
        "- DAW session content ingest allowed: `false`.",
        "- Broad private drive scan allowed: `false`.",
        "",
        "## Allowed Metadata Types",
    ]
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
    generated_at: str | None = None,
) -> NilesAlbumEvidenceIntakeBoundaryResult:
    payload = build_niles_album_evidence_intake_boundary(generated_at=generated_at)
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
        real_album_metadata_recorded=False,
        runtime_authority_added=False,
        send_or_submit_authority_added=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Niles album evidence intake boundary.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_niles_album_evidence_intake_boundary(export_root=args.export_root)
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        payload = build_niles_album_evidence_intake_boundary()
        print(format_niles_album_evidence_intake_boundary(payload), end="")
    return 0


__all__ = [
    "ALLOWED_METADATA_TYPES",
    "BLOCKED_EVIDENCE_TYPES",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_niles_album_evidence_intake_boundary",
    "export_niles_album_evidence_intake_boundary",
    "format_niles_album_evidence_intake_boundary",
    "main",
]
