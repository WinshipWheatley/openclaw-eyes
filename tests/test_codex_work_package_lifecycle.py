import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import codex_work_package_lifecycle as lifecycle
import make_it_so_objective_loop as make_loop
import operator_conversation_router
import scripts.openclaw_run as openclaw_run
import assignment_loop_contract


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


def _minimal_package(tmp_path, *, package_id="codex_work_package:test"):
    package = {
        "schema_version": "CODEX_WORK_PACKAGE_V0",
        "package_id": package_id,
        "objective_id": "operator_objective:test",
        "capability_id": "test_capability",
        "run_mode": "test_dry_run",
        "created_at": FIXED_NOW,
        "worktree_root": "/home/openclaw",
        "allowed_file_paths": ["read_only_email_lookup_connector.py"],
        "denied_file_paths": [".chief.env", ".google-secrets/"],
        "denied_commands": list(lifecycle.DENIED_COMMAND_PHRASES),
        "allowed_commands": ["python3 -m py_compile read_only_email_lookup_connector.py"],
        "validation_commands": ["python3 -m py_compile read_only_email_lookup_connector.py"],
        "unsafe_scan": "required",
        "authority_boundary": dict(lifecycle.AUTHORITY_BOUNDARY),
    }
    objective = {
        "objective_id": "operator_objective:test",
        "operator_goal_text": "Fixture worker lifecycle package.",
        "requested_outcome": "Prove manual dispatch and ingest lifecycle.",
    }
    authority_grant = {"grant_id": "authority_grant:test"}
    lifecycle.queue_codex_work_package(
        package,
        objective=objective,
        authority_grant=authority_grant,
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "work_packages",
        generated_at=FIXED_NOW,
    )
    return package, authority_grant


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


def test_default_package_root_is_durable_system_knowledge():
    assert lifecycle.DEFAULT_PACKAGE_ROOT == Path("generated/system_knowledge/work_packages")
    assert str(lifecycle.DEFAULT_PACKAGE_ROOT).startswith("generated/system_knowledge")


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


def test_dispatch_records_claim_and_updates_package_state(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)
    package_id = grant["codex_work_package"]["package_id"]

    result = lifecycle.record_dispatch(
        package_id,
        "pc_codex",
        "chief",
        "Manual handoff to PC Codex.",
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        generated_at=FIXED_NOW,
    )
    con = sqlite3.connect(tmp_path / "codex_work_package_lifecycle.sqlite")
    try:
        row = con.execute("select claim_json from package_claims where package_id = ?", (package_id,)).fetchone()
    finally:
        con.close()

    assert result["status"] == "dispatch_recorded"
    assert result["package_claim"]["worker_kind"] == "pc_codex"
    assert result["package_claim"]["model_invoked"] is False
    assert result["package_claim"]["external_api_called"] is False
    assert result["package_state"]["state"] == lifecycle.STATE_CLAIMED
    assert row is not None
    assert json.loads(row[0])["dispatched_by"] == "chief"


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


def test_worker_package_sizing_marks_tiny_package_cli_allowed(tmp_path):
    assignment = assignment_loop_contract.build_assignment_loop(
        requested_by="chief",
        owner_agent="chief",
        worker_type="openai_codex_cli",
        goal="Summarize the canonical LM2 worker spine status.",
        sources=[
            "generated/read_models/lm2_worker_spine_status.json",
            "generated/system_knowledge/worker_spine_consolidation/lm2_canonical_worker_spine_v0.json",
        ],
        standard="Return concise read-only JSON.",
        permission_boundary={"worker_time_budget_seconds": 90, "max_sources_per_worker_run": 6},
        proof_required=["source manifest", "validation receipt"],
        stop_condition="Stop after one read-only result.",
        current_status="active",
        created_at_utc=FIXED_NOW,
    )
    result = lifecycle.create_worker_package_from_assignment_loop(
        assignment,
        worker_kind="openai_codex_cli",
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "work_packages",
        generated_at=FIXED_NOW,
    )
    package = result["package_state"]["package_json"]

    assert package["estimated_source_count"] == 2
    assert package["package_size_class"] == "tiny"
    assert package["split_recommended"] is False
    assert package["cli_dispatch_allowed"] is True
    assert package["worker_time_budget_seconds"] == 90


def test_worker_package_sizing_recommends_split_for_large_package(tmp_path):
    sources = [f"generated/read_models/source_{index}.json" for index in range(17)]
    assignment = assignment_loop_contract.build_assignment_loop(
        requested_by="chief",
        owner_agent="chief",
        worker_type="openai_codex_cli",
        goal="Review a broad readiness surface.",
        sources=sources,
        standard="Return concise read-only JSON.",
        permission_boundary={"worker_time_budget_seconds": 120, "max_sources_per_worker_run": 6},
        proof_required=["source manifest", "validation receipt"],
        stop_condition="Stop after one read-only result.",
        current_status="active",
        created_at_utc=FIXED_NOW,
    )
    result = lifecycle.create_worker_package_from_assignment_loop(
        assignment,
        worker_kind="openai_codex_cli",
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "work_packages",
        generated_at=FIXED_NOW,
    )
    package = result["package_state"]["package_json"]

    assert package["estimated_source_count"] == 17
    assert package["package_size_class"] == "large"
    assert package["split_recommended"] is True
    assert package["cli_dispatch_allowed"] is False


def test_codex_worker_prompt_requires_blocked_or_partial_json(tmp_path):
    _, grant, _ = _start_and_grant(tmp_path)
    prompt = Path(grant["codex_work_package_lifecycle"]["package_files"]["prompt_path"]).read_text(encoding="utf-8")

    assert "If blocked, return a blocked JSON result." in prompt
    assert "If partial, return a partial JSON result" in prompt
    assert "Never intentionally produce empty output." in prompt
    assert "Do not inspect outside bounded sources." in prompt


def test_result_ingestion_rejects_unknown_package_id(tmp_path):
    result = lifecycle.ingest_worker_result(
        {"schema_version": lifecycle.PACKAGE_RESULT_SCHEMA, "package_id": "missing", "authority_grant_ref": "grant"},
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        generated_at=FIXED_NOW,
    )

    assert result["package_result"]["status"] == "failed"
    assert result["package_state"]["state"] == lifecycle.STATE_BLOCKED
    assert "unknown_package_id" in result["validation_receipt"]["validation_errors"]


def test_malformed_ingest_result_rejected_safely(tmp_path):
    package, _ = _minimal_package(tmp_path)

    result = lifecycle.ingest_worker_result_text(
        package["package_id"],
        "not a JSON result",
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        generated_at=FIXED_NOW,
    )

    assert result["package_result"]["status"] == "result_rejected"
    assert result["package_state"]["state"] == lifecycle.STATE_VALIDATION_FAILED
    assert "worker_result_json_parse_failed" in result["validation_receipt"]["validation_errors"]


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


def test_read_model_projects_dispatch_validation_and_next_action(tmp_path):
    package, grant = _minimal_package(tmp_path)
    lifecycle.record_dispatch(
        package["package_id"],
        "human",
        "Winship",
        "Fixture dispatch.",
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "work_packages",
        generated_at=FIXED_NOW,
    )
    read_model = lifecycle.build_read_model(
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "work_packages",
        generated_at=FIXED_NOW,
    )

    assert package["package_id"] in read_model["package_ids"]
    assert read_model["counts"]["claimed"] == 1
    assert read_model["dispatch_records"][0]["worker_kind"] == "human"
    assert read_model["watch_desk_items"]
    assert read_model["watch_desk_items"][0]["lane"] == "chief_runtime"
    assert read_model["watch_desk_items"][0]["push_allowed"] is False
    assert read_model["machine_proof"]["model_calls_performed"] is False
    assert read_model["machine_proof"]["external_api_calls_performed"] is False
    assert read_model["machine_proof"]["approval_created"] is False
    assert grant["grant_id"] == "authority_grant:test"


def test_cli_list_show_dispatch_and_ingest_fixture_result(tmp_path, capsys):
    package, grant = _minimal_package(tmp_path)
    sqlite_path = tmp_path / "codex_work_package_lifecycle.sqlite"
    package_root = tmp_path / "work_packages"

    assert openclaw_run.main(["--sqlite-path", str(sqlite_path), "--package-root", str(package_root), "list"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert package["package_id"] in listed["package_ids"]

    assert openclaw_run.main(["--sqlite-path", str(sqlite_path), "--package-root", str(package_root), "show", package["package_id"]]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["package"]["package_id"] == package["package_id"]

    assert openclaw_run.main([
        "--sqlite-path",
        str(sqlite_path),
        "--package-root",
        str(package_root),
        "dispatch",
        package["package_id"],
        "--worker",
        "local_script",
        "--note",
        "Fixture local script handoff.",
    ]) == 0
    dispatched = json.loads(capsys.readouterr().out)
    assert dispatched["package_state"]["state"] == lifecycle.STATE_CLAIMED

    result_path = tmp_path / "worker_result.json"
    result_path.write_text(
        json.dumps(
            _valid_result(
                package,
                grant,
                worker_kind="local_script",
                files_changed=["read_only_email_lookup_connector.py"],
                commands_run=["python3 -m py_compile read_only_email_lookup_connector.py"],
                validation_run=["python3 -m py_compile read_only_email_lookup_connector.py"],
                capability_status="test_ready",
            )
        ),
        encoding="utf-8",
    )
    assert openclaw_run.main([
        "--sqlite-path",
        str(sqlite_path),
        "--package-root",
        str(package_root),
        "ingest",
        package["package_id"],
        "--file",
        str(result_path),
    ]) == 0
    ingested = json.loads(capsys.readouterr().out)
    assert ingested["validation_receipt"]["validation_status"] == "validation_passed"
    assert ingested["package_state"]["state"] == lifecycle.STATE_VALIDATION_PASSED


def test_cli_script_runs_directly_from_repo_root(tmp_path):
    _minimal_package(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/openclaw_run.py",
            "--sqlite-path",
            str(tmp_path / "codex_work_package_lifecycle.sqlite"),
            "--package-root",
            str(tmp_path / "work_packages"),
            "status",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "OPENCLAW_CODEX_WORK_PACKAGE_LIFECYCLE_READY"
    assert payload["sqlite_path"].endswith("codex_work_package_lifecycle.sqlite")


def test_legacy_tmp_package_file_fallback(tmp_path):
    package, _ = _minimal_package(tmp_path)
    legacy_root = tmp_path / "codex_work_packages"
    lifecycle.queue_codex_work_package(
        package,
        objective={"operator_goal_text": "Legacy package root fixture."},
        authority_grant={"grant_id": "authority_grant:test"},
        sqlite_path=tmp_path / "legacy.sqlite",
        package_root=legacy_root,
        generated_at=FIXED_NOW,
    )

    read_model = lifecycle.build_read_model(
        sqlite_path=tmp_path / "legacy.sqlite",
        package_root=tmp_path / "new_work_packages",
        generated_at=FIXED_NOW,
    )
    summary = read_model["package_summaries"][0]

    assert summary["package_file_status"] == "legacy_tmp_present"
    assert summary["package_json_path"].startswith(str(legacy_root))


def test_package_file_missing_status_does_not_crash(tmp_path):
    db = tmp_path / "missing.sqlite"
    state = {
        "schema_version": lifecycle.PACKAGE_STATE_SCHEMA,
        "package_id": "codex_work_package:missing_file",
        "objective_id": "operator_objective:missing_file",
        "capability_id": "test_capability",
        "state": lifecycle.STATE_CLAIMED,
        "run_mode": "test_dry_run",
        "authority_grant_ref": "authority_grant:missing_file",
        "created_at": FIXED_NOW,
        "updated_at": FIXED_NOW,
        "claimed_by": "human",
        "result_ref": "",
        "validation_ref": "",
        "blocker_ref": "",
        "receipt_ref": "receipt:missing_file",
        "package_files": {"package_json_path": str(tmp_path / "missing" / "package.json")},
        "package_json": {},
        "authority_boundary": dict(lifecycle.AUTHORITY_BOUNDARY),
    }
    with lifecycle._connect(db) as conn:
        lifecycle._store_state(conn, state)
        conn.commit()

    read_model = lifecycle.build_read_model(sqlite_path=db, package_root=tmp_path / "work_packages", generated_at=FIXED_NOW)
    summary = read_model["package_summaries"][0]

    assert summary["state"] == lifecycle.STATE_BLOCKED
    assert summary["package_file_status"] == "package_file_missing"


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
