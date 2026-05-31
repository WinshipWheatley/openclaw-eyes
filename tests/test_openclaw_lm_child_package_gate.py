import json
import sqlite3
import sys
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_lm_child_package_gate as gate
from scripts.export_openclaw_lm_child_package_gate import main as export_main


FIXED_NOW = "2026-05-31T22:00:00+00:00"


def _packages() -> dict[str, gate.LMPackage]:
    return {package.package_ref: package for package in gate.seed_lm_packages()}


def _requests() -> dict[str, gate.ChildPackageRequest]:
    return {request.request_ref: request for request in gate.seed_child_package_requests()}


def test_default_package_cannot_spawn_children() -> None:
    parent = gate.default_lm_package()
    request = replace(
        _requests()["child_request:audit_read_only"],
        parent_package_ref=parent.package_ref,
    )

    decision = gate.validate_child_package_request(parent_package=parent, child_request=request)

    assert decision.decision == "BLOCK"
    assert "does not allow child spawning" in decision.reason


def test_allowed_audit_package_can_spawn_one_read_only_child() -> None:
    parent = _packages()["lm_package:audit_child_parent"]
    request = _requests()["child_request:audit_read_only"]

    decision = gate.validate_child_package_request(parent_package=parent, child_request=request)

    assert decision.decision == "ALLOW"
    assert request.requested_authority == ()
    assert request.receipt_required is True
    assert parent.live_action_authority is False


def test_child_requesting_forbidden_file_scope_is_blocked() -> None:
    parent = _packages()["lm_package:audit_child_parent"]
    request = _requests()["child_request:forbidden_file_scope"]

    decision = gate.validate_child_package_request(parent_package=parent, child_request=request)

    assert decision.decision == "BLOCK"
    assert "forbidden file scope" in decision.reason


def test_child_requesting_ledger_email_browser_authority_is_blocked() -> None:
    parent = _packages()["lm_package:audit_child_parent"]
    request = _requests()["child_request:forbidden_live_authority"]

    decision = gate.validate_child_package_request(parent_package=parent, child_request=request)

    assert decision.decision == "AUTHORITY_DENIED"
    assert "ledger_post_allowed" in decision.reason
    assert "email_send_allowed" in decision.reason
    assert "browser_access_allowed" in decision.reason


def test_child_depth_over_max_depth_is_blocked() -> None:
    parent = _packages()["lm_package:audit_child_parent"]
    request = replace(_requests()["child_request:audit_read_only"], requested_depth=2)

    decision = gate.validate_child_package_request(parent_package=parent, child_request=request)

    assert decision.decision == "BLOCK"
    assert "depth exceeds policy max_depth" in decision.reason


def test_max_children_is_enforced() -> None:
    parent = _packages()["lm_package:audit_child_parent"]
    request = _requests()["child_request:audit_read_only"]

    decision = gate.validate_child_package_request(
        parent_package=parent,
        child_request=request,
        sibling_count=2,
    )

    assert decision.decision == "BLOCK"
    assert "count exceeds policy max_children" in decision.reason


def test_guardian_required_package_cannot_proceed_without_guardian_status() -> None:
    parent = _packages()["lm_package:implementation_child_parent"]
    request = _requests()["child_request:implementation_requires_guardian"]

    decision = gate.validate_child_package_request(parent_package=parent, child_request=request)

    assert decision.decision == "REQUIRE_GUARDIAN"
    assert "Guardian approval is required" in decision.reason


def test_child_receipt_required_before_parent_can_close() -> None:
    parent = _packages()["lm_package:audit_child_parent"]

    blocked = gate.parent_close_decision(
        parent_package=parent,
        child_package_refs=("lm_package:child:audit_read_only",),
        receipts=(),
    )
    allowed = gate.parent_close_decision(
        parent_package=parent,
        child_package_refs=("lm_package:child:audit_read_only",),
        receipts=gate.seed_package_receipts(),
    )

    assert blocked.decision == "BLOCK"
    assert "cannot close before child receipts" in blocked.reason
    assert allowed.decision == "ALLOW"


def test_no_live_action_authority_by_default() -> None:
    assert gate.default_lm_package().live_action_authority is False
    payload = gate.build_lm_child_package_gate(generated_at=FIXED_NOW)

    assert payload["default_limits"]["live_action_authority"] is False
    assert all(package["live_action_authority"] is False for package in payload["lm_packages"])
    assert payload["machine_proof"]["child_spawning_enabled"] is False
    assert payload["machine_proof"]["runtime_swarm_enabled"] is False


def test_json_export_parses_and_sqlite_integrity_passes(tmp_path: Path) -> None:
    read_root = tmp_path / "generated" / "read_models"
    system_root = tmp_path / "generated" / "system_knowledge"

    assert export_main(
        [
            "--read-model-root",
            str(read_root),
            "--system-knowledge-root",
            str(system_root),
            "--generated-at",
            FIXED_NOW,
        ]
    ) == 0

    json_path = read_root / gate.JSON_EXPORT_NAME
    operator_path = read_root / gate.OPERATOR_EXPORT_NAME
    sqlite_path = system_root / gate.SQLITE_EXPORT_NAME
    schema_path = system_root / gate.SCHEMA_EXPORT_NAME
    seed_path = system_root / gate.SEED_EXPORT_NAME

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == gate.SCHEMA_VERSION
    assert payload["readiness"] == gate.READINESS
    assert operator_path.exists()
    assert schema_path.exists()
    assert seed_path.exists()

    connection = sqlite3.connect(sqlite_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert set(gate.REQUIRED_SQLITE_TABLES).issubset(tables)
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT COUNT(*) FROM child_spawn_policy").fetchone()[0] >= 5
        assert connection.execute("SELECT COUNT(*) FROM lm_package WHERE live_action_authority = 1").fetchone()[0] == 0
    finally:
        connection.close()
