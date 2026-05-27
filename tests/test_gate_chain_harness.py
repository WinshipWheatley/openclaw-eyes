import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gate_chain_harness as harness
import guardian_output_gate
import intent_ingest_gate
import role_package_gate


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def _run(tmp_path: Path) -> dict:
    return harness.run_harness(
        db_path=tmp_path / "gate_chain_harness.sqlite",
        generated_at=FIXED_NOW,
        persist=True,
    )


def _case(payload: dict, case_id: str) -> dict:
    return next(result for result in payload["case_results"] if result["case_id"] == case_id)


def test_harness_runs_ladder_cases_and_persists_isolated_sqlite(tmp_path):
    payload = _run(tmp_path)

    assert payload["summary"]["total_cases"] >= 15
    assert payload["summary"]["failed"] == 0
    assert payload["summary"]["passed"] == payload["summary"]["total_cases"]
    assert payload["summary"]["packages_compiled"] >= 6
    assert payload["summary"]["guardian_passes"] >= 5
    assert payload["summary"]["guardian_blocks"] >= 3
    assert payload["machine_proof"]["all_live_authority_false"] is True
    assert payload["machine_proof"]["production_business_ops_ledger_touched"] is False

    db_path = Path(payload["isolated_sqlite"]["db_path"])
    assert db_path.exists()
    assert db_path != harness.BUSINESS_OPS_LEDGER_PATH
    with sqlite3.connect(db_path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        count = conn.execute("SELECT COUNT(*) FROM harness_case_results").fetchone()[0]
    assert tables == {"harness_runs", "harness_case_results"}
    assert count == payload["summary"]["total_cases"]


def test_phase_a_gate2_contract_outcomes_cover_core_boundaries(tmp_path):
    payload = _run(tmp_path)

    assert _case(payload, "gibberish_unclear")["actual_outcome"] == intent_ingest_gate.NEEDS_CLARIFICATION
    assert _case(payload, "send_invoice_now")["actual_outcome"] == intent_ingest_gate.BLOCKED_AUTHORITY
    assert _case(payload, "mark_it_paid")["actual_outcome"] == intent_ingest_gate.BLOCKED_AUTHORITY
    assert _case(payload, "wrong_client_scope")["actual_outcome"] == intent_ingest_gate.NEEDS_CONTEXT

    supersede = _case(payload, "delete_other_from_openclaw")
    assert supersede["gate2_result_json"]["outcome"] == intent_ingest_gate.ACCEPTED_INTENT
    accepted = supersede["gate2_result_json"]["accepted_intent"]
    assert accepted["safe_action_type"] == "SUPERSEDE_ACTIVE_REFERENCE_NOT_PHYSICAL_DELETE"
    assert "do not delete any file from disk" in accepted["requested_action"].lower()

    hostile_lm1 = _case(payload, "hostile_lm1_grants_authority")
    assert hostile_lm1["actual_outcome"] == intent_ingest_gate.BLOCKED_AUTHORITY
    assert hostile_lm1["gate2_result_json"]["authority_block"]


def test_phase_b_full_chain_compiles_packages_and_blocks_bad_lm2_output(tmp_path):
    payload = _run(tmp_path)

    safe_status = _case(payload, "next_safe_move_capital_hilton")
    assert safe_status["actual_outcome"] == harness.SCOPED_RESPONSE_READY
    assert safe_status["gate3_package_json"]["package_status"] == role_package_gate.PACKAGE_COMPILED
    package = safe_status["gate3_package_json"]["role_execution_package"]
    assert package["source_request_id"] == safe_status["source_request_id"]
    assert package["output_destination"]["destination_type"] == "MISSION_CONTROL_SCOPED_RESPONSE"
    assert "gmail" in package["tool_policy"]["forbidden_tools"]
    assert "execute_workflow" in package["tool_policy"]["forbidden_actions"]

    sent_claim = _case(payload, "hostile_lm2_sent_claim")
    assert sent_claim["actual_outcome"] == guardian_output_gate.BLOCKED_FORBIDDEN_CLAIM
    assert sent_claim["gate4_result_json"]["validation_result"]["output_publish_allowed"] is False

    ledger_claim = _case(payload, "hostile_lm2_ledger_posted")
    assert ledger_claim["actual_outcome"] == guardian_output_gate.BLOCKED_FORBIDDEN_CLAIM
    assert "posted" in ledger_claim["gate4_result_json"]["validation_result"]["forbidden_claims"]

    tool_request = _case(payload, "hostile_lm2_tool_request")
    assert tool_request["actual_outcome"] == guardian_output_gate.BLOCKED_FORBIDDEN_TOOL
    assert "gmail" in tool_request["gate4_result_json"]["validation_result"]["forbidden_tools"]

    draft = _case(payload, "valid_cassandra_draft")
    assert draft["actual_outcome"] == harness.SCOPED_RESPONSE_READY
    assert draft["gate4_result_json"]["validation_result"]["verdict"] == guardian_output_gate.VALIDATED


def test_phase_c_shadow_lm_readiness_defines_future_interface_without_calling_model(tmp_path):
    payload = _run(tmp_path)
    readiness = payload["phase_c_shadow_lm_readiness"]

    assert readiness["shadow_ready"] is True
    assert readiness["live_lm_call_performed"] is False
    schema = readiness["future_interface"]["required_output_schema"]
    assert "source_request_id" in schema
    assert "inferred_intent_type" in schema
    assert "authority_granted" in schema
    assert "send_submit" in readiness["future_interface"]["forbidden_outputs"]


def test_phase_d_package_readiness_examples_are_bounded_and_guardian_checkable(tmp_path):
    payload = _run(tmp_path)
    examples = payload["phase_d_lm2_package_readiness"]["package_examples"]

    for label in ("chief", "cassandra", "cassandra_clara", "guardian", "niles", "system"):
        example = examples[label]
        assert example["package_status"] == role_package_gate.PACKAGE_COMPILED
        assert example["ready_for_gate4"] is True
        assert example["lm2_call_allowed"] is False
        assert example["tool_authority_granted"] is False
        package = example["package"]["role_execution_package"]
        assert package["output_contract_ref"] == guardian_output_gate.SCHEMA_VERSION
        assert package["tool_policy"]["allowed_tools"] == ()


def test_harness_db_path_is_isolated_from_business_ops_ledger(tmp_path):
    db_path = tmp_path / "gate_chain_harness.sqlite"
    payload = harness.run_harness(db_path=db_path, generated_at=FIXED_NOW, persist=True)

    assert Path(payload["isolated_sqlite"]["db_path"]) == db_path
    assert Path(payload["isolated_sqlite"]["business_ops_ledger_path"]) == harness.BUSINESS_OPS_LEDGER_PATH
    assert payload["isolated_sqlite"]["db_isolated_from_business_ops_ledger"] is True
    assert payload["isolated_sqlite"]["production_tables_touched"] is False


def test_exported_readmodel_parses(tmp_path):
    payload = harness.run_harness(
        db_path=tmp_path / "gate_chain_harness.sqlite",
        generated_at=FIXED_NOW,
        persist=True,
    )
    json_path, operator_path = harness.write_exports(payload, tmp_path / "read_models")

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == harness.READ_MODEL_ID
    assert parsed["summary"]["failed"] == 0
    assert parsed["machine_proof"]["production_business_ops_ledger_touched"] is False
    assert "Harness receipts are isolated" in operator_path.read_text(encoding="utf-8")
