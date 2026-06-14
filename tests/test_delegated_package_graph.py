import json
import sqlite3
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import delegated_package_graph as graph
import guardian_output_gate


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def _parent(delegation_allowed=True):
    return graph.build_capital_hilton_parent_package(
        source_request_id="delegated_package_graph_test_parent",
        delegation_allowed=delegation_allowed,
    )["role_package"]


def test_parent_without_delegation_permission_cannot_spawn_child_package():
    parent = _parent(delegation_allowed=False)
    child = graph.capital_hilton_child_requests(parent)[0]

    result = graph.validate_child_package_request(parent_package=parent, child_request=child)

    assert result.accepted is False
    assert result.verdict == graph.BLOCKED
    assert "Parent package does not allow delegation." in result.blocked_reasons


def test_parent_with_delegation_permission_can_request_allowed_chief_child():
    parent = _parent()
    child = graph.capital_hilton_child_requests(parent)[0]

    result = graph.validate_child_package_request(parent_package=parent, child_request=child)

    assert result.accepted is True
    assert result.verdict == graph.VALIDATED
    assert result.requested_role_family == "CHIEF"


def test_parent_with_delegation_permission_can_request_cassandra_clara_child():
    parent = _parent()
    child = graph.capital_hilton_child_requests(parent)[1]

    result = graph.validate_child_package_request(parent_package=parent, child_request=child)

    assert result.accepted is True
    assert result.verdict == graph.VALIDATED
    assert result.requested_role_family == "CASSANDRA_CLARA"


def test_unlisted_role_is_blocked():
    parent = _parent()
    child = replace(graph.capital_hilton_child_requests(parent)[0], requested_role_family="DATA_ANALYST")

    result = graph.validate_child_package_request(parent_package=parent, child_request=child)

    assert result.accepted is False
    assert "Requested child role is not whitelisted by the parent package." in result.blocked_reasons


def test_child_requesting_send_email_tool_authority_is_blocked():
    parent = _parent()
    child = replace(
        graph.capital_hilton_child_requests(parent)[1],
        requested_tools=("gmail",),
        requested_authority=("send_submit", "email_send"),
    )

    result = graph.validate_child_package_request(parent_package=parent, child_request=child)

    assert result.accepted is False
    assert "Child package requested tools, but parent policy allows no child tools." in result.blocked_reasons
    assert "Child package requested authority, but parent policy allows no child external actions." in result.blocked_reasons
    assert "Child package requested send/tool/external authority that cannot be delegated in v0." in result.blocked_reasons


def test_child_privacy_weaker_than_parent_is_blocked():
    parent = _parent()
    child = replace(graph.capital_hilton_child_requests(parent)[0], privacy_level="low_metadata")

    result = graph.validate_child_package_request(parent_package=parent, child_request=child)

    assert result.accepted is False
    assert "Child privacy level is weaker than the parent package." in result.blocked_reasons


def test_too_many_child_packages_are_blocked():
    parent = _parent()
    children = graph.capital_hilton_child_requests(parent)
    extra = replace(children[0], child_request_id="delegated_child:extra_status")

    results = graph.validate_child_package_requests(parent_package=parent, child_requests=(*children, extra))

    assert all(result.accepted is False for result in results)
    assert all("Requested child package count exceeds parent package limit." in result.blocked_reasons for result in results)


def test_excess_depth_is_blocked():
    parent = _parent()
    child = replace(graph.capital_hilton_child_requests(parent)[0], depth=2)

    result = graph.validate_child_package_request(parent_package=parent, child_request=child)

    assert result.accepted is False
    assert "Requested child package depth exceeds parent package limit." in result.blocked_reasons


def test_parent_cannot_complete_until_child_receipts_exist():
    parent = _parent()
    children = graph.capital_hilton_child_requests(parent)
    validations = graph.validate_child_package_requests(parent_package=parent, child_requests=children)

    result = graph.parent_can_continue(
        parent_package=parent,
        child_validation_results=validations,
        child_receipt_ids=(),
    )

    assert result["can_continue"] is False
    assert result["missing_receipt_count"] == 2
    assert "Parent package is waiting for required child receipts." in result["blocked_reasons"]


def test_capital_hilton_delegated_fixture_writes_linked_child_and_parent_receipts(tmp_path):
    db_path = tmp_path / "delegated_package_graph.sqlite"

    result = graph.run_capital_hilton_delegated_fixture(db_path=db_path, created_at=FIXED_NOW)

    lineage = result["package_lineage"]
    assert len(lineage["child_package_ids"]) == 2
    assert len(lineage["child_receipt_ids"]) == 2
    assert lineage["parent_receipt_id"].startswith("repoa_worker_receipt:")
    assert lineage["final_parent_verdict"] == graph.PARENT_VALIDATED
    assert result["final_parent_guardian_validation"]["validation_result"]["verdict"] == guardian_output_gate.VALIDATED
    assert result["machine_proof"]["child_receipts_written"] is True
    assert result["machine_proof"]["parent_receipt_written"] is True
    assert result["machine_proof"]["external_action_performed"] is False
    assert result["machine_proof"]["send_submit_performed"] is False

    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        receipt_rows = conn.execute(
            "SELECT receipt_id, source_request_id, role_family, validation_verdict, external_action, authority_used "
            "FROM repoa_worker_run_receipts ORDER BY source_request_id"
        ).fetchall()
        graph_row = conn.execute("SELECT * FROM delegated_package_graph_runs").fetchone()

    assert len(receipt_rows) == 3
    assert {row["receipt_id"] for row in receipt_rows}.issuperset(set(lineage["child_receipt_ids"]))
    assert lineage["parent_receipt_id"] in {row["receipt_id"] for row in receipt_rows}
    assert {row["role_family"] for row in receipt_rows} == {"CHIEF", "CASSANDRA_CLARA"}
    assert all(row["validation_verdict"] == guardian_output_gate.VALIDATED for row in receipt_rows)
    assert all(row["external_action"] == 0 for row in receipt_rows)
    assert all(row["authority_used"] == 0 for row in receipt_rows)

    graph_payload = json.loads(graph_row["payload_json"])
    assert graph_payload["parent_package_id"] == lineage["parent_package_id"]
    assert graph_payload["parent_source_request_id"] == lineage["parent_source_request_id"]
    assert graph_payload["child_receipt_ids"] == list(lineage["child_receipt_ids"])
    assert graph_payload["parent_receipt_id"] == lineage["parent_receipt_id"]


def test_final_parent_output_passes_guardian(tmp_path):
    result = graph.run_capital_hilton_delegated_fixture(
        db_path=tmp_path / "delegated_package_graph.sqlite",
        created_at=FIXED_NOW,
    )

    validation = result["final_parent_guardian_validation"]["validation_result"]

    assert validation["verdict"] == guardian_output_gate.VALIDATED
    assert validation["output_publish_allowed"] is True
    assert validation["external_action_allowed"] is False


def test_read_model_export_parses(tmp_path):
    paths = graph.export_read_model(
        export_root=tmp_path,
        db_path=tmp_path / "delegated_package_graph.sqlite",
        generated_at=FIXED_NOW,
    )

    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    operator = paths["operator"].read_text(encoding="utf-8")

    assert payload["read_model_id"] == graph.READ_MODEL_ID
    assert payload["capital_hilton_fixture"]["package_lineage"]["child_receipt_ids"]
    assert "No Repo B runtime started." in operator
