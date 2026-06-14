import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import chief_offline_worker_adapter as chief
import guardian_output_gate
import repoa_worker_boundary_harness as harness
import role_package_gate


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def test_chief_offline_worker_path_writes_sqlite_receipt(tmp_path):
    db_path = tmp_path / "repoa_worker_boundary.sqlite"
    result = harness.run_chief_status_worker_path(
        source_request_id="chief_worker_path_test_request",
        receipt_db_path=db_path,
        created_at=FIXED_NOW,
    )
    role_package = result["role_package"]
    worker_result = result["worker_result"]
    validation = result["guardian_validation"]["validation_result"]
    receipt = result["sqlite_receipt"]

    assert result["package_result"]["package_status"] == role_package_gate.PACKAGE_COMPILED
    assert role_package["role_identity"] == "CHIEF"
    assert role_package["task"] == "status_or_next_safe_move"
    assert role_package["tool_policy"]["allowed_tools"] == ()
    assert role_package["authority_policy"]["tool_authority_granted"] is False
    assert role_package["authority_policy"]["external_action_authority_granted"] is False
    assert role_package["authority_policy"]["send_submit_authority_granted"] is False
    assert worker_result["worker_adapter_id"] == chief.ADAPTER_ID
    assert worker_result["action_taken"] == "none"
    assert worker_result["external_action"] is False
    assert worker_result["authority_used"] is False
    assert validation["verdict"] == guardian_output_gate.VALIDATED
    assert validation["output_publish_allowed"] is True
    assert receipt["receipt_id"].startswith("repoa_worker_receipt:")
    assert receipt["validation_verdict"] == guardian_output_gate.VALIDATED

    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM repoa_worker_run_receipts").fetchall()

    assert len(rows) == 1
    row = rows[0]
    payload = json.loads(row["payload_json"])
    assert row["receipt_id"] == receipt["receipt_id"]
    assert row["source_request_id"] == "chief_worker_path_test_request"
    assert row["worker_adapter_id"] == chief.ADAPTER_ID
    assert row["role_family"] == "CHIEF"
    assert row["selected_voice"] == "CHIEF"
    assert row["validation_verdict"] == guardian_output_gate.VALIDATED
    assert row["action_taken"] == "none"
    assert row["external_action"] == 0
    assert row["authority_used"] == 0
    assert payload["action_taken"] == "none"
    assert payload["role_family"] == "CHIEF"
    assert payload["selected_voice"] == "CHIEF"
    assert payload["external_action"] is False
    assert payload["authority_used"] is False
    assert result["machine_proof"]["gate2_ingest_used"] is True
    assert result["machine_proof"]["gate3_package_used"] is True
    assert result["machine_proof"]["chief_offline_worker_called"] is True
    assert result["machine_proof"]["guardian_output_gate_used"] is True
    assert result["machine_proof"]["sqlite_receipt_written"] is True


def test_chief_adapter_rejects_wrong_role_or_authority_package():
    package_flow = harness.build_chief_status_role_package(source_request_id="chief_worker_reject_test")
    package = dict(package_flow["role_package"])

    wrong_role = {**package, "role_identity": "CASSANDRA"}
    try:
        chief.run_chief_offline_worker(wrong_role)
    except ValueError as exc:
        assert "not Chief" in str(exc)
    else:
        raise AssertionError("wrong-role package should be rejected")

    authority_policy = dict(package["authority_policy"])
    authority_boundary = dict(authority_policy["authority_boundary"])
    authority_boundary["live_tool_execution_allowed"] = True
    authority_policy["authority_boundary"] = authority_boundary
    authority_package = {**package, "authority_policy": authority_policy}
    try:
        chief.run_chief_offline_worker(authority_package)
    except ValueError as exc:
        assert "live authority" in str(exc)
    else:
        raise AssertionError("authority-bearing package should be rejected")


def test_receipt_recording_requires_guardian_validated_no_action_result(tmp_path):
    package_flow = harness.build_chief_status_role_package(source_request_id="chief_worker_block_test")
    package = package_flow["role_package"]
    worker_result = chief.run_chief_offline_worker(package)
    validation = harness.validate_worker_result(worker_result, package)["validation_result"]

    blocked_result = {**worker_result, "external_action": True}
    try:
        harness.record_worker_receipt(
            role_package=package,
            worker_result=blocked_result,
            validation_result=validation,
            db_path=tmp_path / "blocked.sqlite",
            created_at=FIXED_NOW,
        )
    except ValueError as exc:
        assert "authority or external action" in str(exc)
    else:
        raise AssertionError("external-action worker result should not get a receipt")

    blocked_validation = {**validation, "verdict": guardian_output_gate.BLOCKED_AUTHORITY}
    try:
        harness.record_worker_receipt(
            role_package=package,
            worker_result=worker_result,
            validation_result=blocked_validation,
            db_path=tmp_path / "blocked.sqlite",
            created_at=FIXED_NOW,
        )
    except ValueError as exc:
        assert "pass Guardian" in str(exc)
    else:
        raise AssertionError("Guardian-blocked worker result should not get a receipt")


def test_worker_path_does_not_enable_external_or_production_authority(tmp_path):
    result = harness.run_chief_status_worker_path(receipt_db_path=tmp_path / "receipts.sqlite", created_at=FIXED_NOW)
    proof = result["machine_proof"]

    assert proof["repo_b_runtime_started"] is False
    assert proof["live_model_call_performed"] is False
    assert proof["tool_execution_performed"] is False
    assert proof["external_action_performed"] is False
    assert proof["send_submit_performed"] is False
    assert proof["production_state_mutation_performed"] is False
    assert proof["all_live_authority_false"] is True
