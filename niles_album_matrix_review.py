"""Niles album matrix review read-model v0.

Builds a deterministic song-by-song review matrix from governed
operator-supplied album metadata. This read-model does not inspect private
music folders, open DAWs, ingest raw audio, mutate files, run Repo B, or grant
runtime/send/approval authority.
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
SCHEMA_VERSION = "niles_album_matrix_review_v0"
JSON_EXPORT_NAME = "niles_album_matrix_review.json"
OPERATOR_EXPORT_NAME = "niles_album_matrix_review_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
INTAKE_BOUNDARY_PATH = Path("generated/read_models/niles_album_evidence_intake_boundary.json")

MATRIX_VALUE_FIELDS = (
    "album_project_name",
    "song_title",
    "song_id_or_stable_operator_label",
    "track_status_label",
    "production_stage_label",
    "confidence",
    "evidence_status",
)

NO_AUTHORITY_FLAGS = {
    "review_only": True,
    "matrix_read_model_only": True,
    "daw_automation_allowed": False,
    "audio_file_mutation_allowed": False,
    "broad_private_drive_scan_allowed": False,
    "raw_audio_ingest_allowed": False,
    "daw_session_content_ingest_allowed": False,
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
class NilesAlbumMatrixReviewResult:
    schema_version: str
    matrix_status: str
    json_path: str
    operator_path: str
    metadata_record_count: int
    row_count: int
    real_album_metadata_recorded: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool
    approval_authority_added: bool


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


def _read_json_if_present(path: str | Path) -> dict[str, Any]:
    target = _rooted(path)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _metadata_present(value: Any) -> bool:
    return value not in (None, "", [], {})


def _metadata_label(record: dict[str, Any], index: int) -> str:
    return (
        record.get("song_title")
        or record.get("song_id_or_stable_operator_label")
        or record.get("album_project_name")
        or f"operator_metadata_row_{index + 1:03d}"
    )


def _missing_fields(record: dict[str, Any]) -> list[str]:
    return [key for key in MATRIX_VALUE_FIELDS if not _metadata_present(record.get(key))]


def _review_readiness_status(record: dict[str, Any], missing_fields: list[str]) -> str:
    if not _metadata_present(record.get("song_title")) and not _metadata_present(
        record.get("song_id_or_stable_operator_label")
    ):
        return "blocked_missing_song_or_stable_label"
    if missing_fields:
        return "partial_metadata_review_ready"
    if record.get("blocker_labels"):
        return "review_ready_with_operator_blockers"
    return "review_ready_from_governed_operator_metadata"


def _matrix_row(record: dict[str, Any], index: int) -> dict[str, Any]:
    missing = _missing_fields(record)
    blocker_labels = record.get("blocker_labels", [])
    next_safe_move_labels = record.get("next_safe_move_labels", [])
    if not isinstance(blocker_labels, list):
        blocker_labels = []
    if not isinstance(next_safe_move_labels, list):
        next_safe_move_labels = []
    return {
        "row_id": f"niles_album_matrix_row_{index + 1:03d}",
        "row_label": _metadata_label(record, index),
        "album_project_name": record.get("album_project_name"),
        "song_title": record.get("song_title"),
        "song_id_or_stable_operator_label": record.get("song_id_or_stable_operator_label"),
        "track_status_label": record.get("track_status_label"),
        "production_stage_label": record.get("production_stage_label"),
        "source_reference_path_label": record.get("source_reference_path_label"),
        "daw_session_existence_flag": record.get("daw_session_existence_flag"),
        "last_known_operator_update": record.get("last_known_operator_update"),
        "blocker_labels": blocker_labels,
        "next_safe_move_labels": next_safe_move_labels,
        "confidence": record.get("confidence"),
        "evidence_status": record.get("evidence_status"),
        "missing_fields": missing,
        "review_readiness_status": _review_readiness_status(record, missing),
        "partial_metadata_supported": bool(missing),
        "metadata_evidence_posture": "operator_supplied_metadata_evidence_not_album_truth",
        "operator_supplied": record.get("operator_supplied") is True,
        "metadata_only": record.get("metadata_only", True) is True,
        "album_state_confirmed": False,
        "raw_audio_stored": False,
        "daw_session_contents_stored": False,
        "file_opened_or_scanned": False,
    }


def _operator_metadata_records(intake_boundary: dict[str, Any]) -> list[dict[str, Any]]:
    records = intake_boundary.get("recorded_operator_metadata", [])
    if not isinstance(records, list):
        return []
    return [
        record
        for record in records
        if isinstance(record, dict)
        and record.get("operator_supplied") is True
        and record.get("metadata_only") is True
    ]


def _missing_field_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = sorted({field for row in rows for field in row["missing_fields"]})
    return {
        "missing_fields_present": bool(fields),
        "missing_fields": fields,
        "unknown_fields_not_treated_as_confirmed": True,
    }


def build_niles_album_matrix_review(*, repo_root: str | Path = ROOT, generated_at: str | None = None) -> dict[str, Any]:
    root = Path(repo_root)
    intake_path = root / INTAKE_BOUNDARY_PATH
    intake_boundary = _read_json_if_present(intake_path)
    intake_status = intake_boundary.get("operator_metadata_intake_status", {}) if intake_boundary else {}
    records = _operator_metadata_records(intake_boundary)
    rows = [_matrix_row(record, index) for index, record in enumerate(records)]
    metadata_record_count = len(rows)
    metadata_consumed = bool(rows)
    matrix_status = (
        "ready_for_review_from_governed_operator_metadata"
        if metadata_consumed
        else "blocked_needs_governed_album_metadata"
    )
    next_safe_move = (
        "Review governed operator metadata rows manually and fill missing fields through metadata-only intake."
        if metadata_consumed
        else "Provide governed operator metadata through the Niles album evidence intake boundary; do not scan audio/session folders."
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "matrix_id": "niles_album_matrix_review",
        "workflow_domain": "music_art",
        "workflow_name": "Niles album progress review",
        "matrix_status": matrix_status,
        "review_only": True,
        "governed_operator_metadata_only": True,
        "metadata_consumed": metadata_consumed,
        "real_album_metadata_recorded": metadata_consumed,
        "metadata_record_count": metadata_record_count,
        "row_count": len(rows),
        "rows": rows,
        "empty_reason": None if rows else "No governed operator-supplied album metadata records are present.",
        "next_safe_move": next_safe_move,
        "missing_or_unknown_summary": _missing_field_summary(rows),
        "evidence_posture": {
            "operator_metadata_treated_as_evidence_not_truth": True,
            "unknown_fields_not_treated_as_confirmed": True,
            "album_state_confirmed": False,
            "review_readiness_is_not_release_or_audio_truth": True,
        },
        "source_evidence": {
            "source_id": "niles_album_evidence_intake_boundary",
            "source_path": INTAKE_BOUNDARY_PATH.as_posix(),
            "source_present": bool(intake_boundary),
            "source_payload_kind": intake_boundary.get("schema_version", "unknown"),
            "source_role": "metadata-only evidence intake boundary contract",
            "truth_status": "governed_read_model_evidence_not_truth",
            "source_promoted_to_truth": False,
            "metadata_record_count_reported_by_source": intake_status.get("metadata_record_count", 0),
            "partial_metadata_intake_supported": intake_status.get("partial_metadata_intake_supported", True),
        },
        "operator_input_needed": [
            "Governed album/project metadata labels",
            "Song title or stable operator song label",
            "Track and production status labels when known",
            "Blocker labels and next safe move labels when known",
            "Confidence and evidence status labels",
        ],
        "forbidden_boundaries": dict(NO_AUTHORITY_FLAGS),
        "authority_boundary": dict(NO_AUTHORITY_FLAGS),
        "receipt_proof_status": {
            "read_model_written": True,
            "operator_packet_written": True,
            "external_action_taken": False,
            "real_metadata_recorded": metadata_consumed,
            "mission_control_app_changed": False,
        },
        "next_recommended_lane": "Niles Album Metadata Intake Packet v0"
        if not metadata_consumed
        else "Niles Album Matrix Operator Review v0",
        **NO_AUTHORITY_FLAGS,
    }
    return payload


def format_niles_album_matrix_review(payload: dict[str, Any]) -> str:
    lines = [
        "# Niles Album Matrix Review v0",
        "",
        "Status:",
        f"- Matrix status: `{payload['matrix_status']}`.",
        "- Review only: `true`.",
        f"- Operator metadata consumed: `{str(payload['metadata_consumed']).lower()}`.",
        f"- Real album metadata recorded: `{str(payload['real_album_metadata_recorded']).lower()}`.",
        f"- Metadata record count: `{payload['metadata_record_count']}`.",
        f"- Matrix rows: `{payload['row_count']}`.",
        "- Album state confirmed: `false`.",
        "- Raw audio ingest allowed: `false`.",
        "- DAW session content ingest allowed: `false`.",
        "- Broad private drive scan allowed: `false`.",
        "- DAW automation added: `false`.",
        "- Audio file mutation added: `false`.",
        "- Runtime authority added: `false`.",
        "- Send/submit authority added: `false`.",
        "- Approval authority added: `false`.",
        "",
        "## What The Matrix Knows",
    ]
    if payload["rows"]:
        for row in payload["rows"]:
            lines.append(
                f"- `{row['row_id']}` {row['row_label']}: album={row.get('album_project_name') or '[unknown]'}; "
                f"song={row.get('song_title') or row.get('song_id_or_stable_operator_label') or '[unknown]'}; "
                f"track_status={row.get('track_status_label') or '[unknown]'}; "
                f"production_stage={row.get('production_stage_label') or '[unknown]'}; "
                f"confidence={row.get('confidence') or '[unknown]'}; evidence={row.get('evidence_status') or '[unknown]'}; "
                f"readiness={row['review_readiness_status']}."
            )
            if row["blocker_labels"]:
                lines.append(f"  - Blockers: {', '.join(row['blocker_labels'])}.")
            if row["next_safe_move_labels"]:
                lines.append(f"  - Next safe moves: {', '.join(row['next_safe_move_labels'])}.")
            if row["missing_fields"]:
                lines.append(f"  - Missing/unknown fields: {', '.join(row['missing_fields'])}.")
    else:
        lines.append("- No governed operator metadata rows are available.")
    lines.extend(
        [
            "",
            "## What Remains Unknown",
        ]
    )
    missing_fields = payload["missing_or_unknown_summary"]["missing_fields"]
    if missing_fields:
        lines.append(f"- Missing fields across current rows: {', '.join(missing_fields)}.")
    else:
        lines.append("- Album/song/project fields remain unknown until operator metadata is supplied.")
    lines.extend(
        [
            "- Unknown fields are not treated as confirmed.",
            "- Operator metadata is evidence, not final album/session truth.",
            "",
            "## Next Input Needed",
            f"- {payload['next_safe_move']}",
            "",
            "## Why Raw Audio / DAW Scanning Remains Blocked",
            "- This matrix is review-only and metadata-only.",
            "- Raw audio, DAW session contents, broad drive scans, automation, and file mutation remain forbidden boundaries.",
            "",
            "## Authority Boundary",
            "- Backend execution authority added: `false`.",
            "- Runtime/tool/model authority added: `false`.",
            "- Send/submit authority added: `false`.",
            "- Approval authority added: `false`.",
            "- Mission Control app changed: `false`.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_niles_album_matrix_review(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> NilesAlbumMatrixReviewResult:
    root = Path(repo_root)
    out_dir = root / export_root
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_niles_album_matrix_review(repo_root=root, generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_niles_album_matrix_review(payload), encoding="utf-8")
    return NilesAlbumMatrixReviewResult(
        schema_version=SCHEMA_VERSION,
        matrix_status=payload["matrix_status"],
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        metadata_record_count=payload["metadata_record_count"],
        row_count=payload["row_count"],
        real_album_metadata_recorded=payload["real_album_metadata_recorded"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
        approval_authority_added=payload["approval_authority_added"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Niles album matrix review read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root to read generated evidence from.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Read-model export directory.")
    parser.add_argument("--format", choices=("json", "operator"), default="operator", help="Print result format.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    result = export_niles_album_matrix_review(repo_root=args.repo_root, export_root=args.export_root)
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(
            f"Niles album matrix review exported: {result.json_path} and {result.operator_path} "
            f"({result.matrix_status}; rows={result.row_count})."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
