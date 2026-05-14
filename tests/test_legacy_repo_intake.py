import json
import sqlite3
from pathlib import Path

from legacy_repo_intake import (
    PLACEHOLDER_ROOT_ID,
    build_legacy_repo_intake_report,
    legacy_repo_intake_table_names,
    register_placeholder_legacy_repo,
)
from scripts.query_legacy_repo_intake import main as query_main
from scripts.register_legacy_repo_intake import main as register_main


def _row(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def test_schema_initializes(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    assert {
        "legacy_repo_intake_runs",
        "legacy_repo_intake_roots",
        "legacy_repo_intake_risks",
    } <= set(legacy_repo_intake_table_names(db_path))


def test_placeholder_root_is_registered_non_canonical_and_bridged_to_corpus_roots(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    result = register_placeholder_legacy_repo(db_path=db_path, run_id="legacy_fixture")

    assert result.root_id == PLACEHOLDER_ROOT_ID
    assert result.root_count == 1
    assert result.imported_count == 0
    assert result.promoted_count == 0
    root = _row(
        db_path,
        """
SELECT root_kind, owner_scope, canonical_status, import_status, lineage_source
FROM corpus_roots
WHERE root_id = ?
""",
        (PLACEHOLDER_ROOT_ID,),
    )
    assert root == (
        "legacy_git_repo",
        "internal_platform",
        "non_canonical_until_promoted",
        "not_imported",
        "legacy_external_repo",
    )
    flags = _row(
        db_path,
        """
SELECT network_access_attempted, git_clone_attempted, file_import_attempted,
       truth_promotion_attempted, runtime_authority
FROM legacy_repo_intake_runs
WHERE run_id = 'legacy_fixture'
""",
    )
    assert flags == (0, 0, 0, 0, 0)


def test_reports_work(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"

    exit_code = register_main(
        ["--db", str(db_path), "--run-id", "legacy_fixture", "--format", "json"]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["run"]["root_count"] == 1

    report = build_legacy_repo_intake_report(
        db_path=db_path,
        run_id="legacy_fixture",
        section="promotion-candidates",
    )
    assert report["items"][0]["root_id"] == PLACEHOLDER_ROOT_ID

    risk_exit = query_main(
        [
            "--db",
            str(db_path),
            "--run-id",
            "legacy_fixture",
            "--report",
            "risks",
            "--format",
            "operator",
        ]
    )
    assert risk_exit == 0
    assert "sensitive_history" in capsys.readouterr().out


def test_legacy_sources_have_no_external_or_import_behavior():
    source_files = [
        Path("legacy_repo_intake.py"),
        Path("scripts/register_legacy_repo_intake.py"),
        Path("scripts/query_legacy_repo_intake.py"),
    ]
    forbidden = [
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "paramiko",
        "rsync",
        "scp ",
        "ssh ",
        "docker",
        "ollama",
        "pip install",
        "npm install",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text
