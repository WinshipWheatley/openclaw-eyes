import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gate_chain_harness
import guardian_output_gate
import guardian_trust_ramp_simulator as simulator
import intent_ingest_gate
import role_package_gate


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def _run(tmp_path: Path, *, live_receipts=()) -> dict:
    return simulator.run_trust_ramp(
        db_path=tmp_path / "guardian_trust_ramp_simulator.sqlite",
        gate_chain_db_path=tmp_path / "gate_chain_harness.sqlite",
        generated_at=FIXED_NOW,
        live_receipts=live_receipts,
        persist=True,
    )


def _scenario(payload: dict, scenario_id: str) -> dict:
    return next(result for result in payload["scenario_results"] if result["scenario_id"] == scenario_id)


def test_trust_ramp_uses_gate_chain_harness_and_persists_isolated_sqlite(tmp_path):
    payload = _run(tmp_path)

    assert payload["baseline_gate_chain_input"]["used_as_input"] is True
    assert payload["baseline_gate_chain_input"]["summary"]["failed"] == 0
    assert payload["score"]["scenario_count"] >= 10
    assert payload["machine_proof"]["simulation_only"] is True
    assert payload["machine_proof"]["production_business_ops_ledger_touched"] is False
    assert payload["machine_proof"]["live_authority_granted"] is False

    db_path = Path(payload["isolated_sqlite"]["db_path"])
    assert db_path.exists()
    assert db_path != simulator.BUSINESS_OPS_LEDGER_PATH
    with sqlite3.connect(db_path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        count = conn.execute("SELECT COUNT(*) FROM trust_ramp_scenario_results").fetchone()[0]
    assert tables == {"trust_ramp_runs", "trust_ramp_scenario_results"}
    assert count == payload["score"]["scenario_count"]


def test_capital_hilton_suite_scores_level4_candidate_but_active_level1_without_live_receipts(tmp_path):
    payload = _run(tmp_path)
    score = payload["score"]

    assert payload["suite_id"] == "capital_hilton_invoice_package_send_fixture"
    assert score["candidate_trust_level"] == 4
    assert score["candidate_trust_statement"] == "Level 4-ready candidate from simulation only."
    assert score["active_trust_level"] == 1
    assert score["active_trust_statement"] == "Active trust is limited by live receipt evidence; simulation alone does not promote authority."
    assert set(score["promotion_requirements_remaining"]) == set(simulator.LIVE_RECEIPTS_REQUIRED_FOR_ACTIVE_LEVEL_4)
    assert score["false_pass_count"] == 0
    assert score["false_block_rate"] == 0.0


def test_unverified_live_receipts_do_not_promote_active_level4(tmp_path):
    without_receipts = _run(tmp_path / "without")
    with_unverified_receipts = _run(tmp_path / "with", live_receipts=simulator.LIVE_RECEIPTS_REQUIRED_FOR_ACTIVE_LEVEL_4)

    assert without_receipts["score"]["active_trust_level"] == 1
    assert with_unverified_receipts["score"]["candidate_trust_level"] == 4
    assert with_unverified_receipts["score"]["active_trust_level"] == 1
    assert set(with_unverified_receipts["score"]["promotion_requirements_remaining"]) == set(simulator.LIVE_RECEIPTS_REQUIRED_FOR_ACTIVE_LEVEL_4)
    assert set(with_unverified_receipts["score"]["unverified_live_receipts_supplied"]) == set(simulator.LIVE_RECEIPTS_REQUIRED_FOR_ACTIVE_LEVEL_4)
    assert with_unverified_receipts["machine_proof"]["live_authority_granted"] is False


def test_dangerous_scenarios_remain_blocked_or_context_gated(tmp_path):
    payload = _run(tmp_path)

    expected = {
        "wrong_client": intent_ingest_gate.NEEDS_CONTEXT,
        "stale_workbook": intent_ingest_gate.LOW_CONFIDENCE,
        "wrong_total": intent_ingest_gate.LOW_CONFIDENCE,
        "missing_po_reference": intent_ingest_gate.BLOCKED_AUTHORITY,
        "duplicate_send": intent_ingest_gate.BLOCKED_AUTHORITY,
        "missing_approval": intent_ingest_gate.BLOCKED_AUTHORITY,
        "unauthorized_sent_claim": guardian_output_gate.BLOCKED_FORBIDDEN_CLAIM,
        "changed_recipient": intent_ingest_gate.BLOCKED_AUTHORITY,
        "external_action_requested_without_authority": guardian_output_gate.BLOCKED_FORBIDDEN_TOOL,
    }
    for scenario_id, expected_outcome in expected.items():
        result = _scenario(payload, scenario_id)
        assert result["actual_outcome"] == expected_outcome
        assert result["false_pass"] is False
        assert result["blocked_as_expected"] is True

    assert payload["score"]["false_pass_count"] == 0
    assert "wrong_client" in payload["score"]["blocked_risk_classes"]
    assert "external_action_requested_without_authority" in payload["score"]["blocked_risk_classes"]


def test_routine_scenarios_are_guardian_clearable_candidates_only(tmp_path):
    payload = _run(tmp_path)

    for scenario_id in ("correct_client_invoice_recipient_attachment", "routine_delivery_review_packet"):
        result = _scenario(payload, scenario_id)
        assert result["actual_outcome"] == gate_chain_harness.SCOPED_RESPONSE_READY
        assert result["gate2_result"] == intent_ingest_gate.ACCEPTED_INTENT
        assert result["gate3_status"] == role_package_gate.PACKAGE_COMPILED
        assert result["gate4_verdict"] == guardian_output_gate.VALIDATED
        assert result["guardian_clearable_candidate"] is True
        assert result["requires_human_approval"] is True

    assert set(payload["score"]["routine_guardian_clearable_candidates"]) == {
        "correct_client_invoice_recipient_attachment",
        "routine_delivery_review_packet",
    }


def test_no_execution_or_live_authority_flags_are_true(tmp_path):
    payload = _run(tmp_path)

    proof = payload["machine_proof"]
    for key in (
        "lm_call_performed",
        "model_call_performed",
        "agent_dispatch_performed",
        "worker_dispatch_performed",
        "workflow_execution_performed",
        "tool_execution_performed",
        "external_action_performed",
        "workbook_body_read_performed",
        "spreadsheet_cell_read_performed",
        "email_send_performed",
        "gmail_send_performed",
        "coupa_access_performed",
        "browser_access_performed",
        "send_submit_performed",
        "approval_execution_performed",
        "ledger_posting_performed",
    ):
        assert proof[key] is False
    assert proof["all_live_authority_false"] is True
    assert all(result["no_execution_proof"]["workflow_execution_performed"] is False for result in payload["scenario_results"])


def test_exported_readmodel_parses(tmp_path):
    payload = _run(tmp_path)
    json_path, operator_path = simulator.write_exports(payload, tmp_path / "read_models")

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == simulator.READ_MODEL_ID
    assert parsed["score"]["candidate_trust_level"] == 4
    assert parsed["score"]["active_trust_level"] == 1
    assert parsed["machine_proof"]["candidate_trust_level_is_not_active_authority"] is True
    assert "Candidate trust is simulation proof only" in operator_path.read_text(encoding="utf-8")
