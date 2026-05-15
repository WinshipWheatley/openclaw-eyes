import ast
import sqlite3
from pathlib import Path

import pytest

from repo_b_runtime_intake import (
    NO_AUTHORITY_FLAGS,
    build_repo_b_runtime_intake,
    build_repo_b_runtime_intake_report,
    export_repo_b_runtime_intake_read_model,
    repo_b_runtime_intake_table_names,
)
from scripts.build_repo_b_runtime_intake import main as build_main
from scripts.export_repo_b_runtime_intake_read_model import main as export_main
from scripts.query_repo_b_runtime_intake import main as query_main


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_repo_b(tmp_path: Path) -> Path:
    root = tmp_path / "openclaw-runtime"
    root.mkdir()
    _write(
        root / "chief_listener.py",
        "import os\nimport subprocess\n# TELEGRAM listener metadata\nprint('not run in tests')\n",
    )
    _write(root / "cassandra_listener.py", "# cassandra telegram listener\nsend_message = None\n")
    _write(root / "chief_guardian_listener.py", "# guardian safety listener\n")
    _write(root / "chief_billing_brain.py", "# would be sensitive if read\n")
    _write(root / "chief_invoice_brain.py", "# invoice helper\n")
    _write(root / "chief_album_brain.py", "# album helper\n")
    _write(root / "chief_album_mixer.py", "# mixer helper\n")
    _write(root / "chief_website_coordinator.py", "# website client candidate\n")
    _write(root / "hitl_flowchart_gen.py", "# hitl flowchart\n")
    _write(root / "pii_vault.py", "SECRET_SHOULD_NOT_BE_READ\n")
    _write(
        root / "start_chief.sh",
        "#!/usr/bin/env bash\nnohup python3 chief_listener.py &\npython3 cassandra_listener.py\n",
    )
    _write(
        root / "start_openclaw_brains.sh",
        "#!/usr/bin/env bash\npython3 chief_worker.py &\npython3 chief_memory_worker.py\n",
    )
    _write(root / "chief_worker.py", "# worker\n")
    _write(root / "chief_memory_worker.py", "# memory worker\n")
    _write(root / "CLAUDE.md", "# Legacy notes\n")
    _write(root / "CURRENT_STATE.md", "# Current State\n")
    _write(root / "polish_loop" / "orchestrator.py", "# orchestrator\n")
    _write(root / "tests" / "test_cassandra.py", "def test_fixture():\n    assert True\n")
    _write(root / ".env", "TOKEN=do-not-read\n")
    _write(root / "secrets" / "token.txt", "do-not-read\n")
    return root


def _row(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _rows(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_schema_initializes(tmp_path):
    tables = set(repo_b_runtime_intake_table_names(tmp_path / "ledger.sqlite"))

    assert {
        "repo_b_intake_runs",
        "repo_b_roots",
        "repo_b_runtime_files",
        "repo_b_runtime_signatures",
        "repo_b_agent_surfaces",
        "repo_b_startup_surfaces",
        "repo_b_module_candidates",
        "repo_b_safety_findings",
        "repo_b_reconciliation_recommendations",
        "repo_b_query_receipts",
    } <= tables


def test_synthetic_repo_b_tree_is_inventoried_metadata_only(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_b = _fixture_repo_b(tmp_path)

    result = build_repo_b_runtime_intake(
        db_path=db_path,
        repo_root=repo_b,
        run_id="repo_b_fixture",
        require_expected_remote=False,
    )
    root = _row(db_path, "SELECT * FROM repo_b_roots")
    files = _rows(
        db_path,
        "SELECT relative_path, raw_body_stored, execution_allowed, canonical_status, import_status FROM repo_b_runtime_files",
    )

    assert result.scanned_file_count >= 18
    assert result.python_file_count >= 10
    assert result.shell_script_count == 2
    assert result.markdown_file_count == 2
    assert root["canonical_status"] == "non_canonical_until_promoted"
    assert root["import_status"] == "metadata_scanned_only"
    assert root["execution_allowed"] == 0
    assert all(row["raw_body_stored"] == 0 for row in files)
    assert all(row["execution_allowed"] == 0 for row in files)
    assert all(row["canonical_status"] == "non_canonical_until_promoted" for row in files)


def test_build_is_idempotent_for_same_source_commit(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_b = _fixture_repo_b(tmp_path)

    build_repo_b_runtime_intake(
        db_path=db_path,
        repo_root=repo_b,
        run_id="repo_b_fixture_one",
        require_expected_remote=False,
    )
    first_count = _row(db_path, "SELECT COUNT(*) AS count FROM repo_b_module_candidates")["count"]
    build_repo_b_runtime_intake(
        db_path=db_path,
        repo_root=repo_b,
        run_id="repo_b_fixture_two",
        require_expected_remote=False,
    )
    second_count = _row(db_path, "SELECT COUNT(*) AS count FROM repo_b_module_candidates")["count"]

    assert first_count == second_count


def test_no_go_dirs_env_and_sensitive_files_are_not_raw_read(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_b = _fixture_repo_b(tmp_path)
    build_repo_b_runtime_intake(
        db_path=db_path,
        repo_root=repo_b,
        run_id="repo_b_fixture",
        require_expected_remote=False,
    )

    assert _row(db_path, "SELECT COUNT(*) AS count FROM repo_b_runtime_files WHERE relative_path LIKE 'secrets/%'")["count"] == 0
    env_row = _row(
        db_path,
        "SELECT skipped_no_go, read_for_classification, sha256 FROM repo_b_runtime_files WHERE relative_path = '.env'",
    )
    pii_row = _row(
        db_path,
        "SELECT read_for_classification, sha256 FROM repo_b_runtime_files WHERE relative_path = 'pii_vault.py'",
    )
    no_go_finding = _row(
        db_path,
        "SELECT no_go_content_read FROM repo_b_safety_findings WHERE relative_path = '.env'",
    )

    assert tuple(env_row) == (1, 0, None)
    assert tuple(pii_row) == (0, None)
    assert no_go_finding["no_go_content_read"] == 0


def test_startup_references_and_nohup_are_detected_without_execution(tmp_path, monkeypatch):
    db_path = tmp_path / "ledger.sqlite"
    repo_b = _fixture_repo_b(tmp_path)

    called = {"subprocess": 0}

    def fake_run(args, **kwargs):
        called["subprocess"] += 1
        assert args[0] == "git"

        class Result:
            stdout = "unknown\n"

        return Result()

    monkeypatch.setattr("repo_b_runtime_intake.subprocess.run", fake_run)
    build_repo_b_runtime_intake(
        db_path=db_path,
        repo_root=repo_b,
        run_id="repo_b_fixture",
        require_expected_remote=False,
    )
    startup = _row(
        db_path,
        """
SELECT references_json, referenced_count, nohup_detected,
       background_invocation_detected, legacy_runtime_risk
FROM repo_b_startup_surfaces
WHERE relative_path = 'start_chief.sh'
""",
    )
    references = set(__import__("json").loads(startup["references_json"]))

    assert called["subprocess"] == 3
    assert {"chief_listener.py", "cassandra_listener.py"} <= references
    assert startup["referenced_count"] >= 2
    assert startup["nohup_detected"] == 1
    assert startup["background_invocation_detected"] == 1
    assert startup["legacy_runtime_risk"] == 1


def test_agents_music_finance_hitl_and_client_candidates_classify(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_b = _fixture_repo_b(tmp_path)
    build_repo_b_runtime_intake(
        db_path=db_path,
        repo_root=repo_b,
        run_id="repo_b_fixture",
        require_expected_remote=False,
    )
    surfaces = _rows(db_path, "SELECT agent_id, surface_kind, relative_path FROM repo_b_agent_surfaces")
    surface_pairs = {(row["relative_path"], row["agent_id"], row["surface_kind"]) for row in surfaces}
    finance_count = _row(
        db_path,
        "SELECT COUNT(*) AS count FROM repo_b_module_candidates WHERE burden_reduction = 'reduces_finance_burden'",
    )["count"]
    music_count = _row(
        db_path,
        "SELECT COUNT(*) AS count FROM repo_b_module_candidates WHERE burden_reduction = 'reduces_music_burden'",
    )["count"]
    hitl = _row(
        db_path,
        "SELECT future_architectural_role FROM repo_b_module_candidates WHERE relative_path = 'hitl_flowchart_gen.py'",
    )
    client = _row(
        db_path,
        "SELECT future_architectural_role FROM repo_b_module_candidates WHERE relative_path = 'chief_website_coordinator.py'",
    )

    assert ("cassandra_listener.py", "cassandra", "telegram_listener") in surface_pairs
    assert ("chief_guardian_listener.py", "guardian", "runtime_listener") in surface_pairs
    assert finance_count >= 2
    assert music_count >= 2
    assert hitl["future_architectural_role"] == "security_guardrail_candidate"
    assert client["future_architectural_role"] == "client_template_candidate"


def test_direct_execution_risk_heuristics_work(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_b = _fixture_repo_b(tmp_path)
    build_repo_b_runtime_intake(
        db_path=db_path,
        repo_root=repo_b,
        run_id="repo_b_fixture",
        require_expected_remote=False,
    )
    findings = {
        row["finding_type"]
        for row in _rows(
            db_path,
            "SELECT finding_type FROM repo_b_safety_findings WHERE relative_path = 'chief_listener.py'",
        )
    }
    startup_findings = {
        row["finding_type"]
        for row in _rows(
            db_path,
            "SELECT finding_type FROM repo_b_safety_findings WHERE relative_path = 'start_chief.sh'",
        )
    }

    assert "subprocess_reference" in findings
    assert "telegram_direct" in findings
    assert "nohup_background" in startup_findings
    assert "background_shell_invocation" in startup_findings


def test_reports_scripts_and_read_model_export_work(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    repo_b = _fixture_repo_b(tmp_path)
    export_root = tmp_path / "read_models"

    assert build_main(
        [
            "--db",
            str(db_path),
            "--repo-root",
            str(repo_b),
            "--run-id",
            "repo_b_fixture",
            "--allow-unknown-remote",
            "--format",
            "operator",
        ]
    ) == 0
    build_output = capsys.readouterr().out
    assert "Repo B Runtime Intake v0" in build_output

    assert query_main(["--db", str(db_path), "--report", "startup", "--format", "operator"]) == 0
    query_output = capsys.readouterr().out
    assert "start_chief.sh" in query_output

    assert query_main(["--db", str(db_path), "--agent", "cassandra", "--format", "operator"]) == 0
    agent_output = capsys.readouterr().out
    assert "Report: `agents`" in agent_output
    assert "cassandra_listener.py" in agent_output

    assert export_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "operator"]) == 0
    export_output = capsys.readouterr().out
    assert "repo_b_runtime_intake.json" in export_output
    assert (export_root / "repo_b_runtime_intake.json").exists()
    assert (export_root / "repo_b_runtime_intake_OPERATOR.md").exists()


def test_query_reports_work(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_b = _fixture_repo_b(tmp_path)
    build_repo_b_runtime_intake(
        db_path=db_path,
        repo_root=repo_b,
        run_id="repo_b_fixture",
        require_expected_remote=False,
    )
    for report in [
        "summary",
        "agents",
        "startup",
        "risks",
        "module-candidates",
        "client-candidates",
        "burden-reduction",
        "finance-candidates",
        "music-candidates",
    ]:
        payload = build_repo_b_runtime_intake_report(db_path=db_path, report=report)
        assert payload["status"] == "ok"
        assert isinstance(payload["rows"], list)


def test_repo_b_remains_non_canonical_and_no_authority_flags_false(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_b = _fixture_repo_b(tmp_path)
    build_repo_b_runtime_intake(
        db_path=db_path,
        repo_root=repo_b,
        run_id="repo_b_fixture",
        require_expected_remote=False,
    )
    summary = export_repo_b_runtime_intake_read_model(db_path=db_path, export_root=tmp_path / "read_models")
    root = _row(db_path, "SELECT canonical_status, execution_allowed, promotion_required FROM repo_b_roots")

    assert root["canonical_status"] == "non_canonical_until_promoted"
    assert tuple(root)[1:] == (0, 1)
    assert summary["no_authority_flags"] == NO_AUTHORITY_FLAGS
    assert NO_AUTHORITY_FLAGS["repo_b_execution_allowed"] is False
    assert NO_AUTHORITY_FLAGS["module_promotion_allowed"] is False
    assert NO_AUTHORITY_FLAGS["operator_decision_required"] is True


def test_no_destructive_or_remote_control_behavior_in_module_source():
    tree = ast.parse(Path("repo_b_runtime_intake.py").read_text(encoding="utf-8"))
    forbidden_attrs = {
        ("os", "system"),
        ("shutil", "move"),
        ("shutil", "rmtree"),
    }
    forbidden_names = {"unlink", "remove", "rmdir"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                assert (func.value.id, func.attr) not in forbidden_attrs
                assert func.attr not in forbidden_names
            if isinstance(func, ast.Name):
                assert func.id not in forbidden_names

    source = Path("repo_b_runtime_intake.py").read_text(encoding="utf-8").lower()
    assert "shell=true" not in source
    assert "scp " not in source
    assert "rsync" not in source
    assert "docker" not in source
    assert "ollama" not in source
