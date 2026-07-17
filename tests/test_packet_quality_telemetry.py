from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import packet_quality_telemetry as telemetry


def _critique(score: int, summary: str = "Packet supported the turn.") -> dict:
    return {
        "summary": summary,
        "quality_score": score,
        "missing": ["one missing source"] if score < 80 else [],
        "noise": [],
        "mis_scoped": [],
        "improvement_items": ["add the missing source"] if score < 80 else [],
        "grounded_in_turn": ["the answer had to state one fact was unavailable"],
    }


def test_packet_provenance_records_when_and_how_without_raw_prompt() -> None:
    packet = {
        "schema_version": "maestro_context_packet_v0",
        "packet_id": "packet:test:1",
        "generated_at": "2026-07-17T12:00:00+00:00",
        "machine_proof": {"packet_compiler": "maestro_context_packet.build_maestro_context_packet"},
        "facts": [{"topic": "status", "source_ref": "read_model:test"}],
    }

    provenance = telemetry.build_packet_provenance(packet)

    assert provenance["packet_id"] == "packet:test:1"
    assert provenance["built_at"] == "2026-07-17T12:00:00+00:00"
    assert provenance["builder_name"] == "maestro_context_packet.build_maestro_context_packet"
    assert provenance["builder_version"] == telemetry.PACKET_AID_BUILDER_VERSION
    assert provenance["builder_config_hash"].startswith("sha256:")
    assert provenance["packet_hash"].startswith("sha256:")
    assert "operator prompt" not in json.dumps(provenance).lower()


def test_quality_report_lands_in_business_ledger_and_can_be_validated(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.sqlite"
    provenance = telemetry.build_packet_provenance(
        {"packet_id": "packet:test:2", "generated_at": "2026-07-17T12:01:00+00:00", "facts": []}
    )

    receipt = telemetry.record_packet_quality_report(
        db_path=db_path,
        turn_ref_hash="sha256:turn",
        task_class="standard_advisory_response",
        task_difficulty="mid",
        nominal_lane_id="mid_lane",
        work_lane_id="hard_lane",
        model_id="model-id",
        provenance=provenance,
        critique=_critique(88),
    )
    validation = telemetry.record_work_validation(
        db_path=db_path,
        report_id=receipt["report_id"],
        passed=True,
        validator_ref="live:public-canary-exact-output",
    )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = dict(conn.execute("SELECT * FROM packet_quality_reports").fetchone())
    conn.close()
    assert row["packet_id"] == "packet:test:2"
    assert row["nominal_lane_id"] == "mid_lane"
    assert row["work_lane_id"] == "hard_lane"
    assert row["quality_score"] == 88
    assert row["work_validation_passed"] == 1
    assert row["work_validator_ref"] == "live:public-canary-exact-output"
    assert validation["validated"] is True
    assert "prompt" not in row
    assert "answer" not in row


def test_graduation_requires_validated_work_not_self_score_alone(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.sqlite"
    for index in range(3):
        provenance = telemetry.build_packet_provenance(
            {"packet_id": f"packet:test:{index}", "generated_at": "2026-07-17T12:00:00+00:00"}
        )
        receipt = telemetry.record_packet_quality_report(
            db_path=db_path,
            turn_ref_hash=f"sha256:turn-{index}",
            task_class="invoice_copy",
            task_difficulty="mid",
            nominal_lane_id="mid_lane",
            work_lane_id="hard_lane",
            model_id="model-id",
            provenance=provenance,
            critique=_critique(95),
        )
        if index < 2:
            telemetry.record_work_validation(
                db_path=db_path,
                report_id=receipt["report_id"],
                passed=True,
                validator_ref=f"validator:{index}",
            )

    held = telemetry.graduation_snapshot(
        db_path=db_path,
        task_class="invoice_copy",
        candidate_lane_id="mid_lane",
        min_validated_samples=3,
    )
    assert held["status"] == "hold_insufficient_validated_samples"

    conn = sqlite3.connect(db_path)
    last_report = conn.execute(
        "SELECT report_id FROM packet_quality_reports "
        "WHERE work_validation_passed IS NULL ORDER BY observed_at DESC LIMIT 1"
    ).fetchone()[0]
    conn.close()
    telemetry.record_work_validation(
        db_path=db_path,
        report_id=last_report,
        passed=True,
        validator_ref="validator:2",
    )
    ready = telemetry.graduation_snapshot(
        db_path=db_path,
        task_class="invoice_copy",
        candidate_lane_id="mid_lane",
        min_validated_samples=3,
    )
    assert ready["status"] == "eligible_for_candidate_trials"
    assert ready["validated_pass_rate"] == 1.0


def test_builder_regression_names_the_last_working_version(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.sqlite"
    telemetry.record_builder_observation(
        db_path=db_path,
        builder_version="builder-v1",
        builder_config_hash="sha256:config-v1",
        quality_score=92,
        work_validation_passed=True,
    )
    telemetry.mark_builder_known_good(db_path=db_path, builder_version="builder-v1")
    for score in (70, 68, 72):
        telemetry.record_builder_observation(
            db_path=db_path,
            builder_version="builder-v2",
            builder_config_hash="sha256:config-v2",
            quality_score=score,
            work_validation_passed=True,
        )

    regression = telemetry.assess_builder_regression(
        db_path=db_path,
        builder_version="builder-v2",
        min_samples=3,
        max_score_drop=10,
    )

    assert regression["regression_detected"] is True
    assert regression["revert_to_builder_version"] == "builder-v1"
    assert regression["current_config_hash"] == "sha256:config-v2"
