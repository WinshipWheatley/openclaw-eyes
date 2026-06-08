import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import context_freshness_decision_trace_gate as freshness_gate
import proof_to_response_runtime
import retrospective_harness_learning_seed as seed


FIXED_NOW = "2026-06-07T18:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    statuses = {
        freshness_gate.JSON_EXPORT_NAME: freshness_gate.READY_STATUS,
        "proof_bundle_freshness_trace_status.json": "PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY",
        "operator_session_timeline.json": "OPERATOR_SESSION_TIMELINE_READY",
        "universal_receipt_envelope_status.json": "UNIVERSAL_RECEIPT_ENVELOPE_READY",
        proof_to_response_runtime.STATUS_JSON_EXPORT_NAME: proof_to_response_runtime.READY_STATUS,
        "proof_to_response_schema_adapter_status.json": "PROOF_TO_RESPONSE_SCHEMA_ADAPTER_READY",
        "local_lm_proof_response_pilot_postmortem.json": "LOCAL_LM_PROOF_RESPONSE_PILOT_POSTMORTEM_READY",
        "self_heal_repair_doctrine.json": "SELF_HEAL_REPAIR_DOCTRINE_READY",
        "goldilocks_gate_calibration.json": "GOLDILOCKS_GATE_CALIBRATION_READY",
    }
    for filename, status in statuses.items():
        _write_json(root / filename, {"status": status})
    return root


def _read_model(tmp_path: Path) -> dict:
    return seed.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        sqlite_path=tmp_path / "retrospective.sqlite",
        generated_at=FIXED_NOW,
    )


def _example(read_model: dict, example_ref: str) -> dict:
    return next(row for row in read_model["required_examples"] if row["example_ref"] == example_ref)


def test_all_required_failure_classes_exist(tmp_path):
    read_model = _read_model(tmp_path)
    observed = {row["failure_class"] for row in read_model["failure_classes"]}

    assert read_model["status"] == seed.READY_STATUS
    assert observed == set(seed.FAILURE_CLASS_REFS)
    assert read_model["machine_proof"]["all_required_failure_classes_present"] is True


def test_qwen_non_json_failure_is_schema_prompt_issue_not_truth_issue(tmp_path):
    example = _example(_read_model(tmp_path), "local_qwen_non_json_failure")

    assert example["failure_class"] == "non_json_model_output"
    assert example["issue_type"] == "schema_prompt_issue"
    assert example["truth_issue"] is False
    assert "schema/prompt issue" in example["lesson"]
    assert "Do not loosen truth or authority checks" in example["lesson"]


def test_wrong_lane_response_is_context_scoping_issue(tmp_path):
    read_model = _read_model(tmp_path)
    payment = _example(read_model, "finance_payment_watch_wrong_coupa_gate_routing")
    linger = _example(read_model, "proof_to_response_wrong_lane_linger")

    assert payment["failure_class"] == "wrong_lane_response"
    assert payment["issue_type"] == "context_scoping_issue"
    assert "scoped too narrowly" in payment["decision_trace"]["why_it_failed"]
    assert linger["failure_class"] == "wrong_lane_response"
    assert linger["issue_type"] == "context_scoping_issue"
    assert "latest" in linger["decision_trace"]["why_it_failed"].lower()


def test_stale_build_review_is_lifecycle_freshness_issue(tmp_path):
    example = _example(_read_model(tmp_path), "stale_build_review_packet_ready_for_review")

    assert example["failure_class"] == "stale_context"
    assert example["issue_type"] == "lifecycle_freshness_issue"
    assert "Lifecycle/freshness" in example["lesson"]
    assert "historical/resolved" in example["decision_trace"]["what_proof_said"]


def test_candidate_harness_updates_are_review_only(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["candidate_harness_updates"]
    assert all(update["operator_review_required"] is True for update in read_model["candidate_harness_updates"])
    assert all(update["auto_apply_allowed"] is False for update in read_model["candidate_harness_updates"])
    assert all(update["candidate_update_auto_applied"] is False for update in read_model["candidate_harness_updates"])
    assert read_model["selection_policy"]["auto_apply_allowed"] is False
    assert read_model["selection_policy"]["operator_review_required"] is True


def test_auto_apply_allowed_false_for_all(tmp_path):
    read_model = _read_model(tmp_path)
    values = [value for key, value in seed._walk_values(read_model) if key == "auto_apply_allowed"]

    assert values
    assert all(value is False for value in values)
    assert read_model["authority_boundary"]["auto_apply_allowed"] is False
    assert read_model["machine_proof"]["all_candidate_updates_auto_apply_false"] is True


def test_required_trajectory_sources_exist(tmp_path):
    read_model = _read_model(tmp_path)
    observed = {source["source_ref"] for source in read_model["trajectory_sources"]}

    assert observed == set(seed.TRAJECTORY_SOURCE_REFS)
    assert read_model["rules"][0] == "This seed does not modify harness behavior automatically."
    assert "Context freshness beats generated summaries." in read_model["rules"]


def test_sqlite_row_count_matches_json(tmp_path):
    sqlite_path = tmp_path / "retrospective.sqlite"
    read_model = seed.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        sqlite_path=sqlite_path,
        generated_at=FIXED_NOW,
    )
    expected = len(read_model["required_examples"]) + len(read_model["candidate_harness_updates"])

    with sqlite3.connect(sqlite_path) as conn:
        actual = conn.execute("SELECT COUNT(*) FROM retrospective_learning_seed_records").fetchone()[0]

    assert actual == expected
    assert read_model["sqlite_summary"]["sqlite_row_count"] == expected
    assert read_model["machine_proof"]["sqlite_row_count_matches_json"] is True


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert seed.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_wiki_and_sqlite(tmp_path):
    result = seed.export_retrospective_harness_learning_seed(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Retrospective Harness Learning Seed.md",
        sqlite_path=tmp_path / "retrospective.sqlite",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == seed.READY_STATUS
    assert local == bridge
    assert seed.unsafe_true_grants(local) == []
    assert wiki.startswith("# Retrospective Harness Learning Seed")
    assert int(result["sqlite_row_count"]) == local["sqlite_summary"]["sqlite_row_count"]
