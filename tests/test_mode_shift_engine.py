from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

from form_review_sweep import (
    READ_MODEL_NAME,
    build_form_review_recommendations,
    export_form_review_recommendations,
)
from mode_shift_ledger import (
    init_mode_shift_ledger,
    query_mode_shifts,
    seed_mode_shift_ledger,
)
from read_model_auto_refresh import READ_MODEL_REFRESH_REGISTRY


def test_mode_shift_ledger_seeds_design_doc_shifts(tmp_path: Path):
    db_path = tmp_path / "ledger.sqlite"

    seed_mode_shift_ledger(db_path=db_path)
    rows = query_mode_shifts(db_path=db_path)

    assert len(rows) == 5
    by_structure = {row["structure_ref"]: row for row in rows}
    assert "gate-per-task->batch-gate" in by_structure
    assert "instance->class fixing" in by_structure
    assert {row["outcome"]["verdict"] for row in rows} == {"positive"}
    assert all(row["raw_sensitive_data_stored"] is False for row in rows)
    assert all(row["execution_allowed"] is False for row in rows)


def test_form_review_recommends_loosen_for_ritual_no_info_fixture(tmp_path: Path):
    db_path = tmp_path / "ledger.sqlite"
    fixture = {
        "structure_ref": "fixture:ritual_form",
        "display_name": "Ritual Form",
        "signals": {
            "ritual_repeats_without_new_info": 4,
            "new_information_count": 0,
            "cost_score": 8,
            "yield_score": 1,
        },
        "evidence_refs": ["SUPERB-BATTERY:ritual-form-no-new-info"],
    }

    payload = build_form_review_recommendations(
        repo_root=tmp_path,
        db_path=db_path,
        structure_fixtures=[fixture],
        generated_at="2026-07-07T16:00:00+00:00",
    )

    rec = payload["recommendations"][0]
    assert rec["recommended_shift"] == "LOOSEN"
    assert rec["ladder_stage"] == "RECOMMENDATION"
    assert "ritual repeats without new information" in " ".join(rec["trap_signals"])
    assert "SUPERB-BATTERY:ritual-form-no-new-info" in rec["evidence_refs"]
    assert "Ritual Form: loosen recommended" in rec["operator_line"]
    assert payload["machine_proof"]["shift_executed"] is False
    assert payload["machine_proof"]["live_structure_mutation_allowed"] is False


def test_form_review_recommends_freeze_for_three_repeated_positive_pattern(tmp_path: Path):
    fixture = {
        "structure_ref": "fixture:repeated_pattern",
        "display_name": "Repeated Good Pattern",
        "signals": {
            "fluid_pattern_repetition_count": 3,
            "positive_outcome_count": 3,
        },
        "evidence_refs": ["mode_shift_ledger:positive-pattern-1"],
    }

    payload = build_form_review_recommendations(
        repo_root=tmp_path,
        db_path=tmp_path / "ledger.sqlite",
        structure_fixtures=[fixture],
        generated_at="2026-07-07T16:00:00+00:00",
    )

    rec = payload["recommendations"][0]
    assert rec["recommended_shift"] == "FREEZE"
    assert "fluid pattern repeated 3+ times with good outcomes" in " ".join(rec["leverage_signals"])
    assert "Repeated Good Pattern: freeze recommended" in rec["operator_line"]
    assert rec["recommended_next_step"] == "Draft a validator, battery item, doctrine fact, or exemplar; do not execute it."


def test_form_review_export_is_prepare_only_and_does_not_mutate_fixture(tmp_path: Path):
    db_path = tmp_path / "ledger.sqlite"
    read_model_root = tmp_path / "generated" / "read_models"
    fixture = {
        "structure_ref": "fixture:immutable",
        "display_name": "Immutable Fixture",
        "signals": {"ritual_repeats_without_new_info": 3, "new_information_count": 0},
        "evidence_refs": ["fixture:evidence"],
    }
    before = copy.deepcopy(fixture)

    result = export_form_review_recommendations(
        repo_root=tmp_path,
        db_path=db_path,
        read_model_root=read_model_root,
        structure_fixtures=[fixture],
        generated_at="2026-07-07T16:00:00+00:00",
    )

    assert fixture == before
    output_path = read_model_root / READ_MODEL_NAME
    assert result["json_path"] == output_path.as_posix()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["read_model_id"] == "form_review_recommendations"
    assert payload["recommendations"][0]["structure_ref"] == "fixture:immutable"
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM mode_shift_ledger").fetchone()[0] == 5


def test_form_review_read_model_is_refresh_registered():
    entry = READ_MODEL_REFRESH_REGISTRY[READ_MODEL_NAME]

    assert entry["refreshable"] is True
    assert entry["steps"][0]["args"] == ["form_review_sweep.py", "--once"]
    assert "prepare-only" in entry["reason"]
