"""Niles Stage 2 deterministic backend v0.

Consumes the existing Niles metadata-only intake shape and produces an
explainable, review-only decision packet. It normalizes operator metadata,
classifies evidence posture, calculates transparent weights, applies gates and
hard flags, and keeps all execution authority disabled.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from niles_album_evidence_intake_boundary import ALLOWED_FIELD_NAMES, BLOCKED_INPUT_KEYS


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "niles_stage2_deterministic_backend_v0"
JSON_EXPORT_NAME = "niles_stage2_deterministic_backend.json"
OPERATOR_EXPORT_NAME = "niles_stage2_deterministic_backend_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
INTAKE_BOUNDARY_PATH = Path("generated/read_models/niles_album_evidence_intake_boundary.json")

WEIGHT_RUBRIC = {
    "identity": 25,
    "album_project": 10,
    "track_status": 15,
    "production_stage": 10,
    "evidence_status": 15,
    "confidence": 10,
    "source_reference": 5,
    "blockers_or_next_moves": 10,
}

CONFIDENCE_POINTS = {
    "high": 10,
    "medium": 7,
    "low": 3,
    "unknown": 0,
    "": 0,
}

NO_AUTHORITY_FLAGS = {
    "stage2_backend_only": True,
    "deterministic_backend": True,
    "metadata_only": True,
    "review_only": True,
    "taste_calibration_complete": False,
    "album_state_confirmed": False,
    "raw_audio_ingest_allowed": False,
    "daw_session_content_ingest_allowed": False,
    "broad_private_drive_scan_allowed": False,
    "logic_or_ableton_open_allowed": False,
    "daw_automation_allowed": False,
    "audio_file_mutation_allowed": False,
    "finder_file_operation_allowed": False,
    "repo_b_runtime_allowed": False,
    "runtime_authority_added": False,
    "tool_execution_authority_added": False,
    "model_execution_authority_added": False,
    "send_or_submit_authority_added": False,
    "approval_authority_added": False,
    "mission_control_app_changed": False,
}


@dataclass(frozen=True)
class NilesStage2DeterministicBackendResult:
    schema_version: str
    stage2_status: str
    json_path: str
    operator_path: str
    evaluated_record_count: int
    review_ready_count: int
    blocked_record_count: int
    runtime_authority_added: bool
    send_or_submit_authority_added: bool
    approval_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rooted(repo_root: str | Path, path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_json_if_present(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _metadata_records_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("recorded_operator_metadata"), list):
            records = payload["recorded_operator_metadata"]
        elif isinstance(payload.get("metadata_records"), list):
            records = payload["metadata_records"]
        else:
            records = [payload]
    elif isinstance(payload, list):
        records = payload
    else:
        return []
    return [record for record in records if isinstance(record, dict)]


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _list_of_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip())
    return normalized


def _bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _present(value: Any) -> bool:
    return value not in (None, "", [], {})


def normalize_stage2_input_record(record: dict[str, Any], *, index: int) -> dict[str, Any]:
    blocked_input_keys = sorted(set(record).intersection(BLOCKED_INPUT_KEYS))
    blocker_labels = _list_of_strings(record.get("blocker_labels"))
    next_safe_move_labels = _list_of_strings(record.get("next_safe_move_labels"))
    hard_flags: list[str] = []
    if blocked_input_keys:
        hard_flags.append("blocked_input_keys_present")
    if record.get("operator_supplied") is not True:
        hard_flags.append("operator_supplied_flag_missing")
    if record.get("no_external_action") is not True:
        hard_flags.append("external_action_not_explicitly_blocked")
    if record.get("metadata_only") is False:
        hard_flags.append("metadata_only_boundary_missing")
    for key in (
        "raw_audio_stored",
        "daw_session_contents_stored",
        "file_opened_or_scanned",
        "runtime_authority_added",
        "tool_execution_authority_added",
        "model_execution_authority_added",
        "send_or_submit_authority_added",
        "approval_authority_added",
    ):
        if record.get(key) is True:
            hard_flags.append(f"{key}_true")
    normalized = {
        "record_id": f"niles_stage2_input_{index + 1:03d}",
        "album_project_name": _string_or_none(record.get("album_project_name")),
        "song_title": _string_or_none(record.get("song_title")),
        "song_id_or_stable_operator_label": _string_or_none(record.get("song_id_or_stable_operator_label")),
        "track_status_label": _string_or_none(record.get("track_status_label")),
        "production_stage_label": _string_or_none(record.get("production_stage_label")),
        "source_reference_path_label": _string_or_none(record.get("source_reference_path_label")),
        "daw_session_existence_flag": _bool_or_none(record.get("daw_session_existence_flag")),
        "last_known_operator_update": _string_or_none(record.get("last_known_operator_update")),
        "blocker_labels": blocker_labels,
        "next_safe_move_labels": next_safe_move_labels,
        "confidence": (_string_or_none(record.get("confidence")) or "unknown").lower(),
        "evidence_status": _string_or_none(record.get("evidence_status")) or "operator_supplied_metadata_evidence",
        "operator_supplied": record.get("operator_supplied") is True,
        "no_external_action": record.get("no_external_action") is True,
        "metadata_only": record.get("metadata_only", True) is True,
        "blocked_input_keys": blocked_input_keys,
        "hard_flags": sorted(dict.fromkeys(hard_flags)),
        "allowed_field_names": list(ALLOWED_FIELD_NAMES),
        "dropped_untrusted_keys": sorted(set(record) - set(ALLOWED_FIELD_NAMES) - set(blocked_input_keys)),
    }
    normalized["input_label"] = (
        normalized["song_title"]
        or normalized["song_id_or_stable_operator_label"]
        or normalized["album_project_name"]
        or normalized["record_id"]
    )
    return normalized


def classify_stage2_evidence(record: dict[str, Any]) -> dict[str, Any]:
    identity_present = bool(record.get("song_title") or record.get("song_id_or_stable_operator_label"))
    missing = [
        key
        for key in (
            "album_project_name",
            "song_title",
            "song_id_or_stable_operator_label",
            "track_status_label",
            "production_stage_label",
            "evidence_status",
            "confidence",
        )
        if (
            (key in {"song_title", "song_id_or_stable_operator_label"} and not identity_present)
            or (
                key not in {"song_title", "song_id_or_stable_operator_label"}
                and (not _present(record.get(key)) or record.get(key) == "unknown")
            )
        )
    ]
    evidence_status = str(record.get("evidence_status") or "").lower()
    if record["hard_flags"]:
        evidence_class = "blocked_unsafe_or_unauthorized_input"
    elif "synthetic" in evidence_status:
        evidence_class = "synthetic_test_only_not_real_metadata"
    elif "unknown" in evidence_status or missing:
        evidence_class = "partial_operator_metadata_evidence"
    else:
        evidence_class = "operator_supplied_metadata_evidence"
    return {
        "evidence_class": evidence_class,
        "identity_present": identity_present,
        "missing_or_unknown_fields": missing,
        "operator_metadata_treated_as_evidence_not_truth": True,
        "unknown_fields_not_treated_as_confirmed": True,
        "album_state_confirmed": False,
        "safe_for_review_scoring": not record["hard_flags"],
    }


def weighted_stage2_score(record: dict[str, Any], classification: dict[str, Any]) -> dict[str, Any]:
    confidence = str(record.get("confidence") or "").lower()
    score_parts = [
        {
            "component": "identity",
            "points": WEIGHT_RUBRIC["identity"] if classification["identity_present"] else 0,
            "max_points": WEIGHT_RUBRIC["identity"],
        },
        {
            "component": "album_project",
            "points": WEIGHT_RUBRIC["album_project"] if record.get("album_project_name") else 0,
            "max_points": WEIGHT_RUBRIC["album_project"],
        },
        {
            "component": "track_status",
            "points": WEIGHT_RUBRIC["track_status"] if record.get("track_status_label") else 0,
            "max_points": WEIGHT_RUBRIC["track_status"],
        },
        {
            "component": "production_stage",
            "points": WEIGHT_RUBRIC["production_stage"] if record.get("production_stage_label") else 0,
            "max_points": WEIGHT_RUBRIC["production_stage"],
        },
        {
            "component": "evidence_status",
            "points": WEIGHT_RUBRIC["evidence_status"]
            if record.get("evidence_status") and "unknown" not in str(record.get("evidence_status")).lower()
            else 5,
            "max_points": WEIGHT_RUBRIC["evidence_status"],
        },
        {
            "component": "confidence",
            "points": CONFIDENCE_POINTS.get(confidence, 0),
            "max_points": WEIGHT_RUBRIC["confidence"],
        },
        {
            "component": "source_reference",
            "points": WEIGHT_RUBRIC["source_reference"] if record.get("source_reference_path_label") else 0,
            "max_points": WEIGHT_RUBRIC["source_reference"],
        },
        {
            "component": "blockers_or_next_moves",
            "points": WEIGHT_RUBRIC["blockers_or_next_moves"]
            if record.get("blocker_labels") or record.get("next_safe_move_labels")
            else 0,
            "max_points": WEIGHT_RUBRIC["blockers_or_next_moves"],
        },
    ]
    raw_score = sum(part["points"] for part in score_parts)
    if record["hard_flags"]:
        score = 0
    elif classification["evidence_class"] == "synthetic_test_only_not_real_metadata":
        score = min(raw_score, 40)
    else:
        score = raw_score
    band = "high" if score >= 70 else "medium" if score >= 45 else "low"
    return {
        "score": score,
        "score_band": band,
        "max_score": 100,
        "score_parts": score_parts,
        "score_is_review_readiness_not_taste_or_truth": True,
    }


def apply_stage2_gates(
    record: dict[str, Any],
    classification: dict[str, Any],
    score: dict[str, Any],
) -> dict[str, Any]:
    if record["hard_flags"]:
        status = "blocked_hard_flags_present"
        review_allowed = False
    elif not classification["identity_present"]:
        status = "blocked_missing_song_identity"
        review_allowed = False
    elif classification["evidence_class"] == "synthetic_test_only_not_real_metadata":
        status = "synthetic_review_only_not_real_metadata"
        review_allowed = False
    elif score["score"] < 50:
        status = "needs_more_operator_metadata"
        review_allowed = False
    else:
        status = "ready_for_niles_metadata_only_review"
        review_allowed = True
    return {
        "gate_status": status,
        "metadata_review_allowed": review_allowed,
        "runtime_execution_allowed": False,
        "daw_or_file_action_allowed": False,
        "send_or_submit_allowed": False,
        "approval_granted": False,
        "requires_master_taste_calibration_later": True,
    }


def _evaluate_record(record: dict[str, Any], *, index: int) -> dict[str, Any]:
    normalized = normalize_stage2_input_record(record, index=index)
    classification = classify_stage2_evidence(normalized)
    score = weighted_stage2_score(normalized, classification)
    gates = apply_stage2_gates(normalized, classification, score)
    return {
        "evaluation_id": f"niles_stage2_evaluation_{index + 1:03d}",
        "normalized_input": normalized,
        "evidence_classification": classification,
        "weighted_score": score,
        "gates": gates,
        "hard_flags": normalized["hard_flags"],
    }


def _stage2_status(evaluations: list[dict[str, Any]]) -> str:
    if not evaluations:
        return "blocked_needs_governed_operator_metadata"
    if any(item["gates"]["gate_status"] == "blocked_hard_flags_present" for item in evaluations):
        return "blocked_hard_flags_present"
    if any(item["gates"]["metadata_review_allowed"] for item in evaluations):
        return "ready_for_metadata_only_review"
    return "partial_needs_more_operator_metadata"


def build_niles_stage2_deterministic_backend(
    *,
    repo_root: str | Path = ROOT,
    metadata_input_json: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    input_source_path = Path(metadata_input_json) if metadata_input_json else root / INTAKE_BOUNDARY_PATH
    input_payload = _read_json(input_source_path) if metadata_input_json else _read_json_if_present(input_source_path)
    raw_records = _metadata_records_from_payload(input_payload)
    evaluations = [_evaluate_record(record, index=index) for index, record in enumerate(raw_records)]
    review_ready_count = sum(1 for item in evaluations if item["gates"]["metadata_review_allowed"])
    blocked_record_count = sum(1 for item in evaluations if item["hard_flags"])
    status = _stage2_status(evaluations)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "stage2_id": "niles_stage2_deterministic_backend",
        "workflow_domain": "music_art",
        "workflow_name": "Niles album progress review",
        "stage2_status": status,
        "stage2_pipeline": [
            "input_normalize",
            "evidence_classify",
            "weighted_score",
            "gate_evaluate",
            "hard_flag_block",
        ],
        "input_source": {
            "source_path": _display_path(input_source_path),
            "source_present": bool(input_payload),
            "source_schema_version": input_payload.get("schema_version") if isinstance(input_payload, dict) else None,
            "source_is_metadata_only": True,
        },
        "weight_rubric": dict(WEIGHT_RUBRIC),
        "evaluated_record_count": len(evaluations),
        "review_ready_count": review_ready_count,
        "blocked_record_count": blocked_record_count,
        "evaluations": evaluations,
        "next_safe_move": "Collect governed operator metadata through the Niles album evidence intake boundary."
        if not evaluations
        else "Review ready rows manually; fill missing fields through metadata-only intake before any taste calibration.",
        "machine_proof": {
            "deterministic_backend_used": True,
            "input_normalize_performed": True,
            "evidence_classify_performed": True,
            "weighted_score_performed": True,
            "gate_evaluate_performed": True,
            "hard_flags_checked": True,
            "album_state_confirmed": False,
            "runtime_authority_added": False,
            "send_or_submit_authority_added": False,
            "approval_authority_added": False,
        },
        "authority_boundary": dict(NO_AUTHORITY_FLAGS),
        "receipt_proof_status": {
            "read_model_written": True,
            "operator_packet_written": True,
            "external_action_taken": False,
            "runtime_execution_triggered": False,
            "real_audio_or_daw_content_read": False,
        },
        **NO_AUTHORITY_FLAGS,
    }


def format_niles_stage2_deterministic_backend(payload: dict[str, Any]) -> str:
    lines = [
        "# Niles Stage 2 Deterministic Backend v0",
        "",
        "Status:",
        f"- Stage 2 status: `{payload['stage2_status']}`.",
        f"- Evaluated records: `{payload['evaluated_record_count']}`.",
        f"- Review-ready records: `{payload['review_ready_count']}`.",
        f"- Blocked records: `{payload['blocked_record_count']}`.",
        "- Album state confirmed: `false`.",
        "- Runtime authority added: `false`.",
        "- Send/submit authority added: `false`.",
        "- Approval authority added: `false`.",
        "",
        "## Deterministic Pipeline",
    ]
    lines.extend(f"- `{step}`" for step in payload["stage2_pipeline"])
    lines.extend(["", "## Evaluations"])
    if not payload["evaluations"]:
        lines.append("- No governed operator metadata records are present.")
    for item in payload["evaluations"]:
        normalized = item["normalized_input"]
        lines.append(
            f"- `{item['evaluation_id']}` `{normalized['input_label']}`: "
            f"gate=`{item['gates']['gate_status']}`, score=`{item['weighted_score']['score']}`/"
            f"{item['weighted_score']['max_score']}, evidence=`{item['evidence_classification']['evidence_class']}`."
        )
    lines.extend(["", "## Authority Boundary"])
    for key, value in payload["authority_boundary"].items():
        lines.append(f"- `{key}` = `{str(value).lower()}`")
    lines.extend(["", "## Next Safe Move", f"- {payload['next_safe_move']}", ""])
    return "\n".join(lines)


def export_niles_stage2_deterministic_backend(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    metadata_input_json: str | Path | None = None,
    generated_at: str | None = None,
) -> NilesStage2DeterministicBackendResult:
    payload = build_niles_stage2_deterministic_backend(
        repo_root=repo_root,
        metadata_input_json=metadata_input_json,
        generated_at=generated_at,
    )
    root = _rooted(repo_root, export_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_niles_stage2_deterministic_backend(payload), encoding="utf-8")
    return NilesStage2DeterministicBackendResult(
        schema_version=SCHEMA_VERSION,
        stage2_status=payload["stage2_status"],
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        evaluated_record_count=payload["evaluated_record_count"],
        review_ready_count=payload["review_ready_count"],
        blocked_record_count=payload["blocked_record_count"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
        approval_authority_added=payload["approval_authority_added"],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Niles Stage 2 deterministic backend read-model.")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--metadata-input-json", default=None)
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)
    result = export_niles_stage2_deterministic_backend(
        repo_root=args.repo_root,
        export_root=args.export_root,
        metadata_input_json=args.metadata_input_json,
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(
            f"{result.stage2_status}; records={result.evaluated_record_count}; "
            f"ready={result.review_ready_count}; blocked={result.blocked_record_count}; "
            f"runtime_authority_added={str(result.runtime_authority_added).lower()}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
