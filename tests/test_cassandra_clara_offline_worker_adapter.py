import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cassandra_clara_offline_worker_adapter as adapter
import guardian_output_gate
import repoa_worker_boundary_harness as harness
import role_package_gate


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def test_internal_cassandra_fixture_writes_receipt(tmp_path):
    db_path = tmp_path / "repoa_worker_boundary.sqlite"
    result = harness.run_cassandra_clara_worker_path(
        source_request_id="cassandra_internal_fixture_request",
        user_message="What's next for the Capital Hilton invoice?",
        audience="internal",
        receipt_db_path=db_path,
        created_at=FIXED_NOW,
    )
    package = result["role_package"]
    worker_result = result["worker_result"]
    validation = result["guardian_validation"]["validation_result"]
    receipt = result["sqlite_receipt"]

    assert result["package_result"]["package_status"] == role_package_gate.PACKAGE_COMPILED
    assert package["role_family"] == "CASSANDRA_CLARA"
    assert package["internal_role_identity"] == "CASSANDRA"
    assert package["external_voice_identity"] == "CLARA"
    assert package["audience"] == "internal"
    assert package["selected_voice"] == "CASSANDRA"
    assert package["task"] == "comms_draft_or_status"
    assert package["tool_policy"]["allowed_tools"] == ()
    assert package["authority_policy"]["send_submit_authority_granted"] is False
    assert worker_result["response_kind"] == "status"
    assert worker_result["selected_voice"] == "CASSANDRA"
    assert worker_result["status_summary"]
    assert worker_result["draft_text"] == ""
    assert worker_result["action_taken"] == "none"
    assert worker_result["external_action"] is False
    assert worker_result["authority_used"] is False
    assert worker_result["send_performed"] is False
    assert validation["verdict"] == guardian_output_gate.VALIDATED
    assert receipt["role_family"] == "CASSANDRA_CLARA"
    assert receipt["selected_voice"] == "CASSANDRA"

    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM repoa_worker_run_receipts").fetchone()
    payload = json.loads(row["payload_json"])

    assert row["source_request_id"] == "cassandra_internal_fixture_request"
    assert row["role_family"] == "CASSANDRA_CLARA"
    assert row["selected_voice"] == "CASSANDRA"
    assert row["validation_verdict"] == guardian_output_gate.VALIDATED
    assert row["external_action"] == 0
    assert row["authority_used"] == 0
    assert payload["role_family"] == "CASSANDRA_CLARA"
    assert payload["selected_voice"] == "CASSANDRA"


def test_external_clara_fixture_writes_client_safe_draft_receipt(tmp_path):
    db_path = tmp_path / "repoa_worker_boundary.sqlite"
    result = harness.run_cassandra_clara_worker_path(
        source_request_id="clara_external_fixture_request",
        user_message="Draft a note to Hilton about the invoice package.",
        audience="external",
        receipt_db_path=db_path,
        created_at=FIXED_NOW,
    )
    package = result["role_package"]
    worker_result = result["worker_result"]
    validation = result["guardian_validation"]["validation_result"]
    receipt = result["sqlite_receipt"]

    assert package["role_family"] == "CASSANDRA_CLARA"
    assert package["audience"] == "external"
    assert package["selected_voice"] == "CLARA"
    assert worker_result["response_kind"] == "draft"
    assert worker_result["selected_voice"] == "CLARA"
    assert worker_result["draft_text"]
    assert "sent" not in worker_result["draft_text"].lower()
    assert "delivered" not in worker_result["draft_text"].lower()
    assert "submitted" not in worker_result["draft_text"].lower()
    assert worker_result["send_performed"] is False
    assert worker_result["requested_tool_calls"] == ()
    assert worker_result["requested_external_actions"] == ()
    assert validation["verdict"] == guardian_output_gate.VALIDATED
    assert receipt["selected_voice"] == "CLARA"

    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT role_family, selected_voice, validation_verdict FROM repoa_worker_run_receipts").fetchone()

    assert dict(row) == {
        "role_family": "CASSANDRA_CLARA",
        "selected_voice": "CLARA",
        "validation_verdict": guardian_output_gate.VALIDATED,
    }


def test_clara_draft_does_not_claim_sent_delivered_or_submitted():
    package_flow = harness.build_cassandra_clara_role_package(
        source_request_id="clara_claim_scan_fixture",
        user_message="Draft a note to Hilton about the invoice package.",
        audience="external",
    )
    worker_result = adapter.run_cassandra_clara_offline_worker(package_flow["role_package"])
    text = " ".join(
        str(worker_result.get(key) or "")
        for key in ("headline", "one_line_answer", "eliwinship", "status_summary", "draft_text", "next_action")
    ).lower()

    assert "sent the" not in text
    assert "delivered the" not in text
    assert "submitted" not in text
    assert worker_result["send_performed"] is False


def test_send_tool_or_external_action_request_is_blocked_by_guardian():
    package_flow = harness.build_cassandra_clara_role_package(
        source_request_id="clara_blocked_action_fixture",
        user_message="Draft a note to Hilton about the invoice package.",
        audience="external",
    )
    package = package_flow["role_package"]
    worker_result = adapter.run_cassandra_clara_offline_worker(package)
    malicious_result = {
        **worker_result,
        "requested_tool_calls": ("gmail",),
        "requested_external_actions": ("email_send",),
    }
    validation = harness.validate_worker_result(malicious_result, package)["validation_result"]

    assert validation["verdict"] in {
        guardian_output_gate.BLOCKED_AUTHORITY,
        guardian_output_gate.BLOCKED_FORBIDDEN_TOOL,
    }
    assert validation["output_publish_allowed"] is False


def test_cassandra_clara_adapter_rejects_tools_or_authority_package():
    package_flow = harness.build_cassandra_clara_role_package(
        source_request_id="cassandra_clara_reject_fixture",
        user_message="What's next for the Capital Hilton invoice?",
        audience="internal",
    )
    package = dict(package_flow["role_package"])
    tool_policy = dict(package["tool_policy"])
    tool_policy["allowed_tools"] = ("gmail",)
    package_with_tool = {**package, "tool_policy": tool_policy}

    try:
        adapter.run_cassandra_clara_offline_worker(package_with_tool)
    except ValueError as exc:
        assert "allows tools" in str(exc)
    else:
        raise AssertionError("tool-bearing Cassandra/Clara package should be rejected")


def test_cassandra_clara_path_does_not_enable_external_or_production_authority(tmp_path):
    result = harness.run_cassandra_clara_worker_path(
        source_request_id="cassandra_boundary_fixture",
        user_message="What's next for the Capital Hilton invoice?",
        audience="internal",
        receipt_db_path=tmp_path / "receipts.sqlite",
        created_at=FIXED_NOW,
    )
    proof = result["machine_proof"]

    assert proof["repo_b_runtime_started"] is False
    assert proof["live_model_call_performed"] is False
    assert proof["tool_execution_performed"] is False
    assert proof["external_action_performed"] is False
    assert proof["send_submit_performed"] is False
    assert proof["production_state_mutation_performed"] is False
    assert proof["all_live_authority_false"] is True
