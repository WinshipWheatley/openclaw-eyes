import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import codex_work_package_lifecycle as lifecycle
import make_it_so_objective_loop as make_loop
import operator_conversation_router


FIXED_NOW = "2026-06-09T14:00:00+00:00"


def _start_and_grant(tmp_path):
    db = tmp_path / "make_it_so.sqlite"
    first = make_loop.start_email_lookup_objective(
        "Have we received any emails from Annette?",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )
    grant = make_loop.handle_make_it_so_grant(
        "Make it so.",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )
    return first, grant, db


def _valid_result(package, grant, **extra):
    validation_commands = list(package.get("validation_commands") or ["python3 -m py_compile make_it_so_objective_loop.py"])
    result = {
        "schema_version": lifecycle.PACKAGE_RESULT_SCHEMA,
        "package_id": package["package_id"],
        "worker_kind": "manual_codex_handoff",
        "status": "completed",
        "authority_grant_ref": grant["grant_id"],
        "files_changed": ["read_only_email_lookup_connector.py", "tests/test_read_only_email_lookup_connector.py"],
        "commands_run": validation_commands,
        "validation_run": validation_commands,
        "unsafe_scan_summary": {"passed": True, "hits": []},
        "commit_hash": "",
        "blocker_summary": "",
        "receipt_refs": ["fixture:worker_result"],
        "submitted_at": FIXED_NOW,
        "denied_actions_reported": [],
        "introduced_strings": [],
        "capability_status": "production_ready",
    }
    result.update(extra)
    return result


def test_make_it_so_grant_queues_codex_work_package(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)

    lifecycle_bundle = grant["codex_work_package_lifecycle"]
    assert lifecycle_bundle["package_state"]["schema_version"] == lifecycle.PACKAGE_STATE_SCHEMA
    assert lifecycle_bundle["package_state"]["state"] == lifecycle.STATE_AWAITING_WORKER_BRIDGE
    assert lifecycle_bundle["package_queue"]["schema_version"] == lifecycle.PACKAGE_QUEUE_SCHEMA
    assert grant["codex_work_package"]["package_id"] in lifecycle_bundle["package_queue"]["package_refs"]


def test_package_state_is_persisted(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)
    package_id = grant["codex_work_package"]["package_id"]
    state = lifecycle.load_package_state(package_id, sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite")

    assert state["package_id"] == package_id
    assert state["state"] == lifecycle.STATE_AWAITING_WORKER_BRIDGE


def test_package_state_survives_reload(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)
    package_id = grant["codex_work_package"]["package_id"]

    first = lifecycle.load_package_state(package_id, sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite")
    second = lifecycle.load_package_state(package_id, sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite")
    assert first == second


def test_repeating_original_request_returns_package_lifecycle_status(tmp_path):
    _, grant, db = _start_and_grant(tmp_path)
    repeat = make_loop.start_email_lookup_objective(
        "Have we received any emails from Annette?",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )

    assert repeat["response_status"] == "OBJECTIVE_STATUS_READY"
    assert repeat["codex_work_package_lifecycle"]["package_state"]["package_id"] == grant["codex_work_package"]["package_id"]


def test_package_file_directory_contains_required_files(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)
    package_dir = Path(grant["codex_work_package_lifecycle"]["package_files"]["package_dir"])

    for name in (
        "package.json",
        "prompt.md",
        "expected_result_schema.json",
        "allowed_paths.txt",
        "denied_paths.txt",
        "validation_commands.txt",
        "unsafe_scan.txt",
        "receipts_required.md",
    ):
        assert (package_dir / name).exists(), name


def test_no_worker_bridge_available_creates_awaiting_bridge_blocker_once(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)
    first = grant["codex_work_package_lifecycle"]
    second = lifecycle.load_lifecycle_for_objective(
        grant["codex_work_package"]["objective_id"],
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
    )

    assert first["worker_bridge_status"]["human_setup_required"] is True
    assert first["package_state"]["blocker_ref"]
    assert second["package_state"]["blocker_ref"] == first["package_state"]["blocker_ref"]


def test_manual_handoff_package_is_complete_and_self_contained(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)
    prompt = Path(grant["codex_work_package_lifecycle"]["package_files"]["prompt_path"]).read_text(encoding="utf-8")

    assert "Objective" in prompt
    assert "Allowed files" in prompt
    assert "Denied actions" in prompt
    assert "Return format" in prompt
    assert "Do not push" in prompt


def test_result_ingestion_rejects_unknown_package_id(tmp_path):
    result = lifecycle.ingest_worker_result(
        {"schema_version": lifecycle.PACKAGE_RESULT_SCHEMA, "package_id": "missing", "authority_grant_ref": "grant"},
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        generated_at=FIXED_NOW,
    )

    assert result["package_result"]["status"] == "failed"
    assert result["package_state"]["state"] == lifecycle.STATE_BLOCKED
    assert "unknown_package_id" in result["validation_receipt"]["validation_errors"]


def test_result_ingestion_rejects_authority_mismatch(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)
    package = grant["codex_work_package"]
    result = lifecycle.ingest_worker_result(
        _valid_result(package, {"grant_id": "wrong"}),
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        generated_at=FIXED_NOW,
    )

    assert result["package_state"]["state"] == lifecycle.STATE_VALIDATION_FAILED
    assert "authority_grant_mismatch" in result["validation_receipt"]["validation_errors"]


def test_result_ingestion_rejects_changed_files_outside_allowed_paths(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)
    result = lifecycle.ingest_worker_result(
        _valid_result(grant["codex_work_package"], grant["make_it_so_authority_grant"], files_changed=["/etc/passwd"]),
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        generated_at=FIXED_NOW,
    )

    assert result["package_state"]["state"] == lifecycle.STATE_VALIDATION_FAILED
    assert any("outside_allowed_paths" in item for item in result["validation_receipt"]["validation_errors"])


def test_result_ingestion_rejects_denied_action_reports(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)
    result = lifecycle.ingest_worker_result(
        _valid_result(grant["codex_work_package"], grant["make_it_so_authority_grant"], denied_actions_reported=["send_email"]),
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        generated_at=FIXED_NOW,
    )

    assert "denied_action_reported:send_email" in result["validation_receipt"]["validation_errors"]


def test_result_ingestion_rejects_push_or_merge(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)
    result = lifecycle.ingest_worker_result(
        _valid_result(grant["codex_work_package"], grant["make_it_so_authority_grant"], commands_run=["git push"]),
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        generated_at=FIXED_NOW,
    )

    assert any("denied_command" in item for item in result["validation_receipt"]["validation_errors"])


def test_result_ingestion_rejects_secret_like_strings(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)
    result = lifecycle.ingest_worker_result(
        _valid_result(grant["codex_work_package"], grant["make_it_so_authority_grant"], introduced_strings=["api_key=abc123"]),
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        generated_at=FIXED_NOW,
    )

    assert "secret_like_string_detected" in result["validation_receipt"]["validation_errors"]


def test_validation_passed_result_holds_activation_until_connector_configured(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)
    result = lifecycle.ingest_worker_result(
        _valid_result(grant["codex_work_package"], grant["make_it_so_authority_grant"]),
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        generated_at=FIXED_NOW,
    )

    assert result["package_state"]["state"] == lifecycle.STATE_VALIDATION_PASSED
    assert result["validation_receipt"]["validation_status"] == "validation_passed"
    assert result["activation_decision"]["decision"] == "blocked"
    assert result["activation_decision"]["connector_configured"] is False


def test_activation_decision_requires_tests_scans_and_connector_setup(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)
    failed = lifecycle.ingest_worker_result(
        _valid_result(grant["codex_work_package"], grant["make_it_so_authority_grant"], unsafe_scan_summary={"passed": False, "hits": ["push"]}),
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        generated_at=FIXED_NOW,
    )
    passed = lifecycle.ingest_worker_result(
        _valid_result(grant["codex_work_package"], grant["make_it_so_authority_grant"]),
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        generated_at=FIXED_NOW,
    )

    assert failed["activation_decision"]["decision"] == "blocked"
    assert passed["activation_decision"]["decision"] == "blocked"
    assert passed["activation_decision"]["production_ready"] is False
    assert "connector setup" in passed["activation_decision"]["reason"].lower()


def test_capability_registry_records_human_setup_until_connector_configured(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)
    lifecycle.ingest_worker_result(
        _valid_result(grant["codex_work_package"], grant["make_it_so_authority_grant"]),
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        generated_at=FIXED_NOW,
    )
    con = sqlite3.connect(tmp_path / "codex_work_package_lifecycle.sqlite")
    try:
        row = con.execute("select status from capability_registry where capability_id = ?", ("read_only_email_lookup",)).fetchone()
    finally:
        con.close()
    assert row[0] == "human_setup_required"


def test_read_only_email_lookup_package_does_not_grant_protected_email_or_browser(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)
    package = grant["codex_work_package"]

    assert "send email" in " ".join(package["denied_commands"]).lower()
    assert package["authority_boundary"]["email_send_allowed"] is False
    assert package["authority_boundary"]["gmail_ui_allowed"] is False
    assert package["authority_boundary"]["browser_access_allowed"] is False


def test_build_authority_does_not_grant_data_access_or_test_production(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)
    lifecycle_bundle = grant["codex_work_package_lifecycle"]

    assert lifecycle_bundle["package_state"]["authority_grant_ref"] == grant["make_it_so_authority_grant"]["grant_id"]
    assert lifecycle_bundle["authority_boundary"]["email_send_allowed"] is False
    assert lifecycle_bundle["authority_boundary"]["paid"] is False
    assert "test authority does not become production authority" in json.dumps(grant).lower()


def test_raw_authority_granted_remains_rejected_in_lifecycle_route(tmp_path):
    request = {
        "request_id": "lifecycle_raw_authority",
        "request_type": operator_conversation_router.REQUEST_TYPE,
        "controller_event_type": "chat_goal",
        "operator_text": "Have we received any emails from Annette?",
        "current_world_ref": "finance",
        "current_thread_ref": "capital_hilton",
        "authority_granted": True,
    }
    result = operator_conversation_router.route_conversation_text(
        request,
        sqlite_path=tmp_path / "conversation.sqlite",
        generated_at=FIXED_NOW,
    )

    assert result["route_status"] == "MAKE_IT_SO_AUTHORITY_REQUEST_READY"
    assert result["machine_proof"]["raw_authority_granted_trusted"] is False


def test_workflow_package_request_not_emitted_for_make_it_so_lifecycle(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)

    assert grant["codex_work_package_lifecycle"]["package_state"]["state"] == lifecycle.STATE_AWAITING_WORKER_BRIDGE
    assert "WORKFLOW_PACKAGE_REQUEST_V0" not in json.dumps(grant)
