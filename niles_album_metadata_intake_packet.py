"""Niles album metadata intake packet/template v0.

Publishes a deterministic operator-facing template for supplying governed
album/song metadata to Niles. The template contains placeholders only. It does
not scan drives, ingest raw audio, read DAW sessions, mutate files, run Repo B,
or grant runtime/send/approval authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from niles_album_evidence_intake_boundary import ALLOWED_FIELD_NAMES, ALLOWED_METADATA_TYPES


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "niles_album_metadata_intake_packet_v0"
JSON_EXPORT_NAME = "niles_album_metadata_intake_packet.json"
OPERATOR_EXPORT_NAME = "niles_album_metadata_intake_packet_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

MINIMUM_USEFUL_FIELDS = (
    "song_title",
    "song_id_or_stable_operator_label",
    "blocker_labels",
)

OPTIONAL_FIELDS = (
    "album_project_name",
    "track_status_label",
    "production_stage_label",
    "source_reference_path_label",
    "daw_session_existence_flag",
    "last_known_operator_update",
    "next_safe_move_labels",
    "confidence",
    "evidence_status",
)

NO_AUTHORITY_FLAGS = {
    "metadata_intake_packet_only": True,
    "review_only": True,
    "template_only": True,
    "real_album_metadata_recorded": False,
    "raw_audio_ingest_allowed": False,
    "daw_session_content_ingest_allowed": False,
    "broad_private_drive_scan_allowed": False,
    "daw_automation_allowed": False,
    "audio_file_mutation_allowed": False,
    "logic_or_ableton_open_allowed": False,
    "finder_file_operation_allowed": False,
    "repo_b_authority_allowed": False,
    "runtime_authority_added": False,
    "tool_execution_authority_added": False,
    "model_execution_authority_added": False,
    "send_or_submit_authority_added": False,
    "approval_authority_added": False,
    "mission_control_app_changed": False,
}


@dataclass(frozen=True)
class NilesAlbumMetadataIntakePacketResult:
    schema_version: str
    intake_packet_status: str
    json_path: str
    operator_path: str
    allowed_field_count: int
    minimum_useful_field_count: int
    real_album_metadata_recorded: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool
    approval_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _placeholder_record() -> dict[str, Any]:
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
        "evidence_status": "operator_supplied_pending_review",
        "operator_supplied": True,
        "no_external_action": True,
    }


def _placeholder_packet() -> dict[str, Any]:
    return {
        "packet_label": "niles_album_metadata_operator_input_template_v0",
        "template_uses_placeholders_not_facts": True,
        "metadata_records": [_placeholder_record()],
    }


def build_niles_album_metadata_intake_packet(*, generated_at: str | None = None) -> dict[str, Any]:
    allowed_fields = list(ALLOWED_FIELD_NAMES)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "packet_id": "niles_album_metadata_intake_packet",
        "workflow_domain": "music_art",
        "workflow_name": "Niles album progress review",
        "intake_packet_status": "template_ready_no_real_metadata_recorded",
        "real_album_metadata_recorded": False,
        "metadata_record_count": 0,
        "template_uses_placeholders_not_facts": True,
        "operator_metadata_treated_as_evidence_not_truth": True,
        "unknown_fields_not_treated_as_confirmed": True,
        "allowed_fields": allowed_fields,
        "allowed_metadata_types": list(ALLOWED_METADATA_TYPES),
        "minimum_useful_fields": list(MINIMUM_USEFUL_FIELDS),
        "minimum_useful_rule": "Provide song_title or song_id_or_stable_operator_label; blocker labels are useful even when status/stage remain unknown.",
        "optional_fields": list(OPTIONAL_FIELDS),
        "operator_facing_input_template": _placeholder_packet(),
        "allowed_input_posture": [
            "operator-supplied metadata only",
            "stable operator labels",
            "high-level status labels",
            "high-level blocker labels",
            "high-level next-safe-move labels",
            "safe source reference labels, not raw private paths unless a later protected path policy explicitly permits them",
        ],
        "forbidden_boundaries": {
            "raw_audio_ingest": "forbidden",
            "daw_session_content_ingest": "forbidden",
            "broad_private_drive_scan": "forbidden",
            "daw_automation": "forbidden",
            "audio_or_session_file_mutation": "forbidden",
            "metadata_as_final_truth": "forbidden",
            "repo_b_runtime_execution": "forbidden",
        },
        "backend_flow": [
            {
                "step": 1,
                "operator_action": "Fill a copy of operator_facing_input_template with governed metadata labels.",
                "authority": "operator_metadata_only",
            },
            {
                "step": 2,
                "operator_action": "Pass that JSON to scripts/export_niles_album_evidence_intake_boundary.py --metadata-input-json <path>.",
                "authority": "documented_command_path_only_not_executed_by_this_packet",
            },
            {
                "step": 3,
                "operator_action": "Regenerate Niles review packet so it consumes the intake state.",
                "authority": "read_model_consumption_only",
            },
            {
                "step": 4,
                "operator_action": "Regenerate Niles matrix review so rows appear from governed metadata.",
                "authority": "read_model_consumption_only",
            },
            {
                "step": 5,
                "operator_action": "Sync generated read-models for Mission Control to show the updated state later.",
                "authority": "sync_marker_or_existing_sync_flow_only",
            },
        ],
        "current_no_real_metadata_state": {
            "real_album_metadata_recorded": False,
            "metadata_record_count": 0,
            "review_packet_status_before_metadata": "blocked_needs_governed_album_evidence",
            "matrix_status_before_metadata": "blocked_needs_governed_album_metadata",
        },
        "next_safe_operator_action": "Fill the placeholder metadata packet with governed album/song labels, not raw audio or DAW/session content.",
        "authority_boundary": dict(NO_AUTHORITY_FLAGS),
        "receipt_proof_status": {
            "read_model_written": True,
            "operator_packet_written": True,
            "external_action_taken": False,
            "real_metadata_recorded": False,
            "template_contains_real_album_claims": False,
            "mission_control_app_changed": False,
        },
        "next_recommended_lane": "Niles Governed Metadata Fill v0",
        **NO_AUTHORITY_FLAGS,
    }
    return payload


def format_niles_album_metadata_intake_packet(payload: dict[str, Any]) -> str:
    template = stable_json(payload["operator_facing_input_template"]).rstrip()
    lines = [
        "# Niles Album Metadata Intake Packet v0",
        "",
        "Status:",
        f"- Intake packet status: `{payload['intake_packet_status']}`.",
        "- Template uses placeholders, not album facts: `true`.",
        "- Real album metadata recorded: `false`.",
        "- Metadata record count: `0`.",
        "- Operator metadata is evidence, not final truth: `true`.",
        "- Raw audio ingest allowed: `false`.",
        "- DAW session content ingest allowed: `false`.",
        "- Broad private drive scan allowed: `false`.",
        "- DAW automation added: `false`.",
        "- Audio/session file mutation added: `false`.",
        "- Runtime authority added: `false`.",
        "- Send/submit authority added: `false`.",
        "- Approval authority added: `false`.",
        "",
        "## Allowed Fields",
        "- " + ", ".join(payload["allowed_fields"]) + ".",
        "",
        "## Minimum Useful Fields",
        "- " + ", ".join(payload["minimum_useful_fields"]) + ".",
        f"- {payload['minimum_useful_rule']}",
        "",
        "## Optional Fields",
        "- " + ", ".join(payload["optional_fields"]) + ".",
        "",
        "## Operator Input Template",
        "```json",
        template,
        "```",
        "",
        "## Allowed Input Posture",
    ]
    lines.extend(f"- {item}." for item in payload["allowed_input_posture"])
    lines.extend(
        [
            "",
            "## Forbidden Boundaries",
        ]
    )
    lines.extend(f"- {key}: `{value}`." for key, value in payload["forbidden_boundaries"].items())
    lines.extend(
        [
            "",
            "## Existing Backend Flow",
        ]
    )
    for step in payload["backend_flow"]:
        lines.append(f"- Step {step['step']}: {step['operator_action']} ({step['authority']}).")
    lines.extend(
        [
            "",
            "## Next Safe Operator Action",
            f"- {payload['next_safe_operator_action']}",
        ]
    )
    return "\n".join(lines) + "\n"


def export_niles_album_metadata_intake_packet(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> NilesAlbumMetadataIntakePacketResult:
    root = Path(repo_root)
    out_dir = root / export_root
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_niles_album_metadata_intake_packet(generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_niles_album_metadata_intake_packet(payload), encoding="utf-8")
    return NilesAlbumMetadataIntakePacketResult(
        schema_version=SCHEMA_VERSION,
        intake_packet_status=payload["intake_packet_status"],
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        allowed_field_count=len(payload["allowed_fields"]),
        minimum_useful_field_count=len(payload["minimum_useful_fields"]),
        real_album_metadata_recorded=payload["real_album_metadata_recorded"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
        approval_authority_added=payload["approval_authority_added"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Niles album metadata intake packet/template.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root to write generated read-models.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Read-model export directory.")
    parser.add_argument("--format", choices=("json", "operator"), default="operator", help="Print result format.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    result = export_niles_album_metadata_intake_packet(repo_root=args.repo_root, export_root=args.export_root)
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(
            f"Niles album metadata intake packet exported: {result.json_path} and {result.operator_path} "
            f"({result.intake_packet_status}; allowed_fields={result.allowed_field_count})."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
