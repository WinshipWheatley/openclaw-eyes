"""Durable, prompt-free packet-quality telemetry for external work turns."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_LEDGER_PATH = Path("/home/openclaw/.openclaw/business_ops/ledger.sqlite")
PACKET_AID_BUILDER_VERSION = "external_brain_packet_aid_v2"
PACKET_CRITIQUE_SCHEMA_VERSION = "packet_critique_v1"
_BUILDER_CONFIG = {
    "schema_version": "external_brain_packet_aid_config_v2",
    "operator_prompt_position": "first_verbatim",
    "packet_position": "second_labeled_aid",
    "packet_critique_schema": PACKET_CRITIQUE_SCHEMA_VERSION,
    "work_lane_rule": "one_capability_tier_above_nominal",
}
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}(?!\d)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: object) -> str:
    return "sha256:" + hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _safe_text(value: object, *, limit: int = 600) -> str:
    text = " ".join(str(value or "").split())
    text = _EMAIL_RE.sub("[email]", text)
    text = _PHONE_RE.sub("[phone]", text)
    return text[:limit]


def _safe_items(value: object, *, limit: int = 8) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [_safe_text(item, limit=300) for item in list(value)[:limit] if _safe_text(item, limit=300)]


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    _ensure_schema(connection)
    return connection


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS packet_quality_reports (
            report_id TEXT PRIMARY KEY,
            observed_at TEXT NOT NULL,
            turn_ref_hash TEXT NOT NULL UNIQUE,
            task_class TEXT NOT NULL,
            task_difficulty TEXT NOT NULL,
            nominal_lane_id TEXT NOT NULL,
            work_lane_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            packet_id TEXT NOT NULL,
            packet_hash TEXT NOT NULL,
            built_at TEXT NOT NULL,
            builder_name TEXT NOT NULL,
            builder_version TEXT NOT NULL,
            builder_config_hash TEXT NOT NULL,
            critique_schema_version TEXT NOT NULL,
            critique_summary TEXT NOT NULL,
            quality_score INTEGER NOT NULL CHECK (quality_score BETWEEN 0 AND 100),
            missing_json TEXT NOT NULL,
            noise_json TEXT NOT NULL,
            mis_scoped_json TEXT NOT NULL,
            improvement_items_json TEXT NOT NULL,
            grounded_in_turn_json TEXT NOT NULL,
            work_validation_passed INTEGER,
            work_validator_ref TEXT NOT NULL DEFAULT '',
            validated_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS packet_builder_versions (
            builder_version TEXT PRIMARY KEY,
            builder_config_hash TEXT NOT NULL,
            implementation_ref TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'observed'
        );

        CREATE TABLE IF NOT EXISTS packet_builder_quality_observations (
            observation_id TEXT PRIMARY KEY,
            observed_at TEXT NOT NULL,
            builder_version TEXT NOT NULL,
            builder_config_hash TEXT NOT NULL,
            quality_score INTEGER NOT NULL CHECK (quality_score BETWEEN 0 AND 100),
            work_validation_passed INTEGER,
            FOREIGN KEY (builder_version) REFERENCES packet_builder_versions(builder_version)
        );

        CREATE INDEX IF NOT EXISTS packet_quality_task_class_idx
            ON packet_quality_reports(task_class, nominal_lane_id, work_lane_id, observed_at);
        CREATE INDEX IF NOT EXISTS packet_builder_observation_idx
            ON packet_builder_quality_observations(builder_version, observed_at);
        """
    )


def build_packet_provenance(packet: Mapping[str, Any]) -> dict[str, str]:
    """Describe the exact packet delivery recipe without storing operator text."""

    machine_proof = packet.get("machine_proof")
    proof = machine_proof if isinstance(machine_proof, Mapping) else {}
    receipt = packet.get("packet_engine_receipt")
    engine_receipt = receipt if isinstance(receipt, Mapping) else {}
    builder_name = str(
        proof.get("packet_compiler")
        or engine_receipt.get("builder_ref")
        or packet.get("schema_version")
        or "unknown_packet_builder"
    )
    packet_json = _stable_json(dict(packet))
    config_payload = {
        **_BUILDER_CONFIG,
        "source_schema_version": str(packet.get("schema_version") or "unknown"),
        "source_builder": builder_name,
    }
    return {
        "schema_version": "packet_build_provenance_v1",
        "packet_id": str(packet.get("packet_id") or _sha256(packet_json)[:32]),
        "packet_hash": _sha256(packet_json),
        "built_at": str(packet.get("generated_at") or "unknown"),
        "observed_at": _now(),
        "builder_name": builder_name,
        "builder_version": PACKET_AID_BUILDER_VERSION,
        "builder_config_hash": _sha256(_stable_json(config_payload)),
        "implementation_ref": (
            "packet_quality_telemetry.build_packet_provenance@"
            + PACKET_AID_BUILDER_VERSION
        ),
    }


def _normalized_critique(critique: Mapping[str, Any]) -> dict[str, Any]:
    try:
        score = int(critique.get("quality_score"))
    except (TypeError, ValueError) as exc:
        raise ValueError("packet critique quality_score must be an integer") from exc
    if not 0 <= score <= 100:
        raise ValueError("packet critique quality_score must be between 0 and 100")
    summary = _safe_text(critique.get("summary"), limit=600)
    if not summary:
        raise ValueError("packet critique summary is required")
    return {
        "summary": summary,
        "quality_score": score,
        "missing": _safe_items(critique.get("missing")),
        "noise": _safe_items(critique.get("noise")),
        "mis_scoped": _safe_items(critique.get("mis_scoped")),
        "improvement_items": _safe_items(critique.get("improvement_items")),
        "grounded_in_turn": _safe_items(critique.get("grounded_in_turn")),
    }


def _upsert_builder_version(connection: sqlite3.Connection, provenance: Mapping[str, Any]) -> None:
    moment = _now()
    connection.execute(
        """
        INSERT INTO packet_builder_versions (
            builder_version, builder_config_hash, implementation_ref,
            first_seen_at, last_seen_at, status
        ) VALUES (?, ?, ?, ?, ?, 'observed')
        ON CONFLICT(builder_version) DO UPDATE SET
            builder_config_hash = excluded.builder_config_hash,
            implementation_ref = excluded.implementation_ref,
            last_seen_at = excluded.last_seen_at
        """,
        (
            str(provenance.get("builder_version") or ""),
            str(provenance.get("builder_config_hash") or ""),
            str(provenance.get("implementation_ref") or ""),
            moment,
            moment,
        ),
    )


def record_packet_quality_report(
    *,
    db_path: str | Path = DEFAULT_LEDGER_PATH,
    turn_ref_hash: str,
    task_class: str,
    task_difficulty: str,
    nominal_lane_id: str,
    work_lane_id: str,
    model_id: str,
    provenance: Mapping[str, Any],
    critique: Mapping[str, Any],
) -> dict[str, Any]:
    """Store one critique without the raw prompt, packet body, or answer."""

    normalized = _normalized_critique(critique)
    report_id = _sha256(
        "|".join(
            (
                str(turn_ref_hash),
                str(provenance.get("packet_hash") or ""),
                str(provenance.get("builder_version") or ""),
            )
        )
    )[:39]
    with _connect(db_path) as connection:
        _upsert_builder_version(connection, provenance)
        connection.execute(
            """
            INSERT OR IGNORE INTO packet_quality_reports (
                report_id, observed_at, turn_ref_hash, task_class, task_difficulty,
                nominal_lane_id, work_lane_id, model_id, packet_id, packet_hash,
                built_at, builder_name, builder_version, builder_config_hash,
                critique_schema_version, critique_summary, quality_score,
                missing_json, noise_json, mis_scoped_json, improvement_items_json,
                grounded_in_turn_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                _now(),
                str(turn_ref_hash),
                _safe_text(task_class, limit=120),
                _safe_text(task_difficulty, limit=60),
                str(nominal_lane_id),
                str(work_lane_id),
                _safe_text(model_id, limit=120),
                str(provenance.get("packet_id") or ""),
                str(provenance.get("packet_hash") or ""),
                str(provenance.get("built_at") or ""),
                str(provenance.get("builder_name") or ""),
                str(provenance.get("builder_version") or ""),
                str(provenance.get("builder_config_hash") or ""),
                PACKET_CRITIQUE_SCHEMA_VERSION,
                normalized["summary"],
                normalized["quality_score"],
                _stable_json(normalized["missing"]),
                _stable_json(normalized["noise"]),
                _stable_json(normalized["mis_scoped"]),
                _stable_json(normalized["improvement_items"]),
                _stable_json(normalized["grounded_in_turn"]),
            ),
        )
        row = connection.execute(
            "SELECT report_id FROM packet_quality_reports WHERE turn_ref_hash = ?",
            (str(turn_ref_hash),),
        ).fetchone()
    return {
        "schema_version": "packet_quality_report_receipt_v1",
        "status": "recorded",
        "report_id": str(row["report_id"] if row else report_id),
        "quality_score": normalized["quality_score"],
        "builder_version": str(provenance.get("builder_version") or ""),
        "builder_config_hash": str(provenance.get("builder_config_hash") or ""),
        "packet_hash": str(provenance.get("packet_hash") or ""),
    }


def record_work_validation(
    *,
    db_path: str | Path = DEFAULT_LEDGER_PATH,
    report_id: str,
    passed: bool,
    validator_ref: str,
) -> dict[str, Any]:
    if not str(validator_ref or "").strip():
        raise ValueError("validator_ref is required")
    with _connect(db_path) as connection:
        report = connection.execute(
            """
            SELECT builder_version, builder_config_hash, quality_score
            FROM packet_quality_reports WHERE report_id = ?
            """,
            (str(report_id),),
        ).fetchone()
        if report is None:
            raise ValueError("unknown packet quality report")
        cursor = connection.execute(
            """
            UPDATE packet_quality_reports
            SET work_validation_passed = ?, work_validator_ref = ?, validated_at = ?
            WHERE report_id = ?
            """,
            (1 if passed else 0, _safe_text(validator_ref, limit=240), _now(), str(report_id)),
        )
        if cursor.rowcount != 1:
            raise ValueError("unknown packet quality report")
        moment = _now()
        observation_id = _sha256(
            f"{report_id}|{report['builder_version']}|{validator_ref}|{moment}"
        )[:39]
        connection.execute(
            """
            INSERT INTO packet_builder_quality_observations (
                observation_id, observed_at, builder_version, builder_config_hash,
                quality_score, work_validation_passed
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                observation_id,
                moment,
                str(report["builder_version"]),
                str(report["builder_config_hash"]),
                int(report["quality_score"]),
                1 if passed else 0,
            ),
        )
    return {"report_id": str(report_id), "validated": True, "passed": bool(passed)}


def record_builder_observation(
    *,
    db_path: str | Path = DEFAULT_LEDGER_PATH,
    builder_version: str,
    builder_config_hash: str,
    quality_score: int,
    work_validation_passed: bool | None,
) -> dict[str, Any]:
    score = int(quality_score)
    if not 0 <= score <= 100:
        raise ValueError("quality_score must be between 0 and 100")
    provenance = {
        "builder_version": str(builder_version),
        "builder_config_hash": str(builder_config_hash),
        "implementation_ref": "packet_builder_version_registry",
    }
    moment = _now()
    observation_id = _sha256(f"{builder_version}|{builder_config_hash}|{score}|{moment}")[:39]
    with _connect(db_path) as connection:
        _upsert_builder_version(connection, provenance)
        connection.execute(
            """
            INSERT INTO packet_builder_quality_observations (
                observation_id, observed_at, builder_version, builder_config_hash,
                quality_score, work_validation_passed
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                observation_id,
                moment,
                str(builder_version),
                str(builder_config_hash),
                score,
                None if work_validation_passed is None else (1 if work_validation_passed else 0),
            ),
        )
    return {"observation_id": observation_id, "recorded": True}


def mark_builder_known_good(
    *, db_path: str | Path = DEFAULT_LEDGER_PATH, builder_version: str
) -> None:
    with _connect(db_path) as connection:
        cursor = connection.execute(
            "UPDATE packet_builder_versions SET status = 'known_good' WHERE builder_version = ?",
            (str(builder_version),),
        )
        if cursor.rowcount != 1:
            raise ValueError("unknown builder version")


def assess_builder_regression(
    *,
    db_path: str | Path = DEFAULT_LEDGER_PATH,
    builder_version: str,
    min_samples: int = 5,
    max_score_drop: float = 10.0,
) -> dict[str, Any]:
    with _connect(db_path) as connection:
        current = connection.execute(
            """
            SELECT AVG(quality_score) AS average_score, COUNT(*) AS sample_count,
                   MAX(builder_config_hash) AS config_hash
            FROM packet_builder_quality_observations
            WHERE builder_version = ? AND work_validation_passed = 1
            """,
            (str(builder_version),),
        ).fetchone()
        baseline_version = connection.execute(
            """
            SELECT builder_version FROM packet_builder_versions
            WHERE status = 'known_good' AND builder_version <> ?
            ORDER BY last_seen_at DESC LIMIT 1
            """,
            (str(builder_version),),
        ).fetchone()
        baseline = None
        if baseline_version:
            baseline = connection.execute(
                """
                SELECT AVG(quality_score) AS average_score, COUNT(*) AS sample_count
                FROM packet_builder_quality_observations
                WHERE builder_version = ? AND work_validation_passed = 1
                """,
                (str(baseline_version["builder_version"]),),
            ).fetchone()
    current_count = int(current["sample_count"] or 0)
    current_average = float(current["average_score"] or 0.0)
    baseline_average = float(baseline["average_score"] or 0.0) if baseline else 0.0
    detected = bool(
        baseline_version
        and baseline
        and current_count >= int(min_samples)
        and int(baseline["sample_count"] or 0) > 0
        and baseline_average - current_average >= float(max_score_drop)
    )
    return {
        "schema_version": "packet_builder_regression_v1",
        "builder_version": str(builder_version),
        "current_config_hash": str(current["config_hash"] or ""),
        "sample_count": current_count,
        "average_score": round(current_average, 2),
        "baseline_average_score": round(baseline_average, 2),
        "regression_detected": detected,
        "revert_to_builder_version": (
            str(baseline_version["builder_version"]) if detected and baseline_version else ""
        ),
    }


def graduation_snapshot(
    *,
    db_path: str | Path = DEFAULT_LEDGER_PATH,
    task_class: str,
    candidate_lane_id: str,
    min_validated_samples: int = 5,
) -> dict[str, Any]:
    """Report whether +1-tier evidence is strong enough to start lower-lane trials.

    This never graduates a lane by itself. Deterministic work validation is mandatory,
    and the result is only an evidence packet for a later candidate-lane trial/review.
    """

    with _connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS validated_samples,
                   SUM(CASE WHEN work_validation_passed = 1 THEN 1 ELSE 0 END) AS passed_samples,
                   AVG(CASE WHEN work_validation_passed IS NOT NULL THEN quality_score END) AS average_score
            FROM packet_quality_reports
            WHERE task_class = ? AND nominal_lane_id = ? AND work_validation_passed IS NOT NULL
            """,
            (_safe_text(task_class, limit=120), str(candidate_lane_id)),
        ).fetchone()
    validated = int(row["validated_samples"] or 0)
    passed = int(row["passed_samples"] or 0)
    pass_rate = (passed / validated) if validated else 0.0
    enough = validated >= int(min_validated_samples)
    clean = pass_rate == 1.0
    return {
        "schema_version": "packet_model_graduation_snapshot_v1",
        "task_class": _safe_text(task_class, limit=120),
        "candidate_lane_id": str(candidate_lane_id),
        "validated_samples": validated,
        "validated_pass_rate": round(pass_rate, 4),
        "average_quality_score": round(float(row["average_score"] or 0.0), 2),
        "status": (
            "eligible_for_candidate_trials"
            if enough and clean
            else "hold_insufficient_validated_samples"
            if not enough
            else "hold_work_validation_regression"
        ),
        "automatic_graduation_allowed": False,
    }
