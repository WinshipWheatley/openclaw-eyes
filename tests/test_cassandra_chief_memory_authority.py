import json
import sqlite3
from pathlib import Path

from cassandra_chief_memory_authority import (
    ALLOWED_FATES,
    DRY_RUN_JSON_EXPORT_NAME,
    DRY_RUN_OPERATOR_EXPORT_NAME,
    NO_AUTHORITY_FLAGS,
    OPERATOR_REVIEW_EXPORT_NAME,
    REQUIRED_AUTHORITY_COLUMNS,
    STRUCTURED_IMPORT_PLAN_JSON_EXPORT_NAME,
    STRUCTURED_IMPORT_PLAN_OPERATOR_EXPORT_NAME,
    TABLE_NAMES,
    build_cassandra_chief_memory_authority_read_model,
    build_cassandra_chief_memory_dry_run,
    build_cassandra_chief_structured_import_plan,
    cassandra_chief_memory_table_names,
    export_cassandra_chief_memory_authority_read_model,
    format_cassandra_chief_memory_operator_review,
    format_cassandra_chief_structured_import_plan,
    init_cassandra_chief_memory_authority_schema,
)
from scripts.export_cassandra_chief_memory_authority_read_model import main as export_main
from scripts.query_cassandra_chief_memory_authority import main as query_main


FIXED_NOW = "2026-05-16T12:00:00+00:00"


def _rows(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _columns(db_path: Path, table_name: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    finally:
        conn.close()


def _defaults(db_path: Path, table_name: str) -> dict[str, str | None]:
    conn = sqlite3.connect(db_path)
    try:
        return {
            row[1]: row[4]
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
    finally:
        conn.close()


def test_schema_initializes_with_required_memory_authority_tables_and_columns(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    init_cassandra_chief_memory_authority_schema(db_path)
    tables = set(cassandra_chief_memory_table_names(db_path))

    assert set(TABLE_NAMES) <= tables
    for table_name in TABLE_NAMES:
        columns = _columns(db_path, table_name)
        if table_name == "cassandra_chief_memory_dry_run_reviews":
            assert {
                "data_import_allowed",
                "raw_file_ingest_allowed",
                "old_files_are_truth",
                "repo_b_execution_allowed",
                "send_allowed",
                "runtime_authority",
            } <= columns
            continue
        assert REQUIRED_AUTHORITY_COLUMNS <= columns


def test_source_catalog_rows_are_metadata_only_and_use_allowed_fates(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    read_model = build_cassandra_chief_memory_authority_read_model(
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    rows = _rows(db_path, "SELECT * FROM cassandra_chief_memory_sources")

    assert read_model["source_count"] == 15
    assert {row["recommended_fate"] for row in rows} <= ALLOWED_FATES
    assert {row["source_hash"] for row in rows} == {None}
    assert {row["source_hash_kind"] for row in rows} == {None}
    assert all(row["source_path_hash"] for row in rows)
    assert all(row["raw_content_read"] == 0 for row in rows)
    assert all(row["raw_content_imported"] == 0 for row in rows)
    assert all(row["import_allowed_in_prompt_2"] == 0 for row in rows)
    assert all(row["old_files_are_truth"] == 0 for row in rows)
    assert all(row["no_send_authority"] == 1 for row in rows)
    assert all(row["no_runtime_authority"] == 1 for row in rows)
    assert all(row["approval_required"] == 1 for row in rows)


def test_no_send_and_no_runtime_authority_default_true(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    init_cassandra_chief_memory_authority_schema(db_path)

    for table_name in (
        "cassandra_chief_memory_sources",
        "cassandra_chief_memory_entities",
        "cassandra_chief_memory_email_permissions",
        "cassandra_chief_legacy_approval_refs",
    ):
        defaults = _defaults(db_path, table_name)
        assert defaults["no_send_authority"] == "1"
        assert defaults["no_runtime_authority"] == "1"
        assert defaults["approval_required"] == "1"


def test_old_hitl_json_and_volatile_residue_are_not_authority(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    dry_run = build_cassandra_chief_memory_dry_run(db_path=db_path, generated_at=FIXED_NOW)
    by_category = {item["category"]: item for item in dry_run["sources"]}

    old_hitl = by_category["old HITL JSON/JSONL state"]
    assert old_hitl["recommended_fate"] == "block_no_go"
    assert old_hitl["evidence_status"] == "blocked"
    assert old_hitl["no_send_authority"] is True
    assert old_hitl["no_runtime_authority"] is True
    assert "cannot approve" in old_hitl["allowed_agent_use"]
    assert dry_run["old_hitl_json_active_approval_authority"] is False

    agent_presence = by_category["dirty generated agent_presence snapshots"]
    assert agent_presence["recommended_fate"] == "defer_operator_review"
    assert agent_presence["evidence_status"] == "deprecated"
    assert agent_presence["old_files_are_truth"] is False

    polish_tasks = by_category["untracked polish_loop Cassandra failure tasks"]
    assert polish_tasks["recommended_fate"] == "delete_local_residue"
    assert polish_tasks["source_type"] == "local_residue_reference"
    assert polish_tasks["raw_content_read"] is False


def test_dry_run_flags_prohibit_import_raw_ingest_and_old_file_truth(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    dry_run = build_cassandra_chief_memory_dry_run(db_path=db_path, generated_at=FIXED_NOW)

    assert dry_run["data_import_allowed"] is False
    assert dry_run["raw_file_ingest_allowed"] is False
    assert dry_run["old_files_are_truth"] is False
    assert dry_run["repo_b_execution_allowed"] is False
    assert dry_run["runtime_authority"] is False
    assert dry_run["send_allowed"] is False
    assert dry_run["raw_private_data_imported"] is False
    assert all(source["source_hash"] is None for source in dry_run["sources"])
    assert all(source["raw_content_read"] is False for source in dry_run["sources"])
    assert all(source["raw_content_imported"] is False for source in dry_run["sources"])


def test_operator_review_packet_contains_five_buckets_and_boundary_language(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    dry_run = build_cassandra_chief_memory_dry_run(db_path=db_path, generated_at=FIXED_NOW)

    review = format_cassandra_chief_memory_operator_review(dry_run)

    assert "1. Safe to structure later" in review
    assert "2. Keep as evidence source only" in review
    assert "3. Block / do not trust" in review
    assert "4. Delete local residue candidate" in review
    assert "5. Needs operator decision" in review
    assert "No raw data was imported." in review
    assert "Old files are not truth." in review
    assert "Cassandra/Chief cannot use these as authority yet." in review


def test_export_and_query_scripts_write_expected_generated_outputs(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"

    summary = export_cassandra_chief_memory_authority_read_model(
        db_path=db_path,
        export_root=export_root,
    )
    dry_run_payload = json.loads((export_root / DRY_RUN_JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    assert summary["source_count"] == 15
    assert summary["data_import_allowed"] is False
    assert dry_run_payload["schema_version"] == "cassandra_chief_memory_dry_run_v0"
    assert dry_run_payload["source_count"] == 15
    assert (export_root / DRY_RUN_OPERATOR_EXPORT_NAME).is_file()
    assert (export_root / OPERATOR_REVIEW_EXPORT_NAME).is_file()
    assert (export_root / STRUCTURED_IMPORT_PLAN_JSON_EXPORT_NAME).is_file()
    assert (export_root / STRUCTURED_IMPORT_PLAN_OPERATOR_EXPORT_NAME).is_file()

    assert export_main(
        [
            "--db",
            str(db_path),
            "--export-root",
            str(export_root),
            "--format",
            "json",
        ]
    ) == 0
    assert '"data_import_allowed": false' in capsys.readouterr().out

    assert query_main(["--db", str(db_path), "--report", "review", "--format", "operator"]) == 0
    assert "Cassandra/Chief Memory Operator Review Packet v0" in capsys.readouterr().out


def test_structured_import_plan_is_review_only_and_has_six_buckets(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    plan = build_cassandra_chief_structured_import_plan(
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    rendered = format_cassandra_chief_structured_import_plan(plan)

    assert plan["schema_version"] == "cassandra_chief_structured_import_plan_v0"
    assert plan["data_imported"] is False
    assert plan["raw_content_read"] is False
    assert plan["old_files_are_truth"] is False
    assert plan["operator_approval_required_before_import"] is True
    assert plan["repo_b_execution_allowed"] is False
    assert plan["category_count"] == 15
    assert all(item["import_allowed_now"] is False for item in plan["categories"])
    assert all(item["raw_content_allowed"] is False for item in plan["categories"])
    assert all(item["approval_required_before_import"] is True for item in plan["categories"])

    assert "1. Safe to import structured facts later" in rendered
    assert "2. Register as evidence source only" in rendered
    assert "3. Summarize/extract only" in rendered
    assert "4. Block / do not trust" in rendered
    assert "5. Delete local residue candidate" in rendered
    assert "6. Needs operator decision" in rendered


def test_structured_import_plan_blocks_old_hitl_delete_and_agent_presence_truth(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    plan = build_cassandra_chief_structured_import_plan(
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    by_name = {item["display_name"]: item for item in plan["categories"]}

    old_hitl = by_name["old HITL JSON/JSONL state"]
    assert old_hitl["recommended_fate"] == "block_no_go"
    assert old_hitl["active_approval_authority"] is False
    assert "old HITL authority" in old_hitl["what_would_not_be_imported"]

    polish_tasks = by_name["untracked polish_loop Cassandra failure tasks"]
    assert polish_tasks["recommended_fate"] == "delete_local_residue"
    assert polish_tasks["auto_delete_allowed"] is False
    assert "No file body and no automatic deletion." == polish_tasks["what_would_not_be_imported"]

    agent_presence = by_name["dirty generated agent_presence snapshots"]
    assert agent_presence["recommended_fate"] == "defer_operator_review"
    assert agent_presence["old_files_are_truth"] is False
    assert "canonical" not in agent_presence["next_safe_move"].lower()


def test_generated_outputs_do_not_expose_no_go_roots_or_raw_private_content(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"

    export_cassandra_chief_memory_authority_read_model(db_path=db_path, export_root=export_root)
    rendered = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            export_root / DRY_RUN_JSON_EXPORT_NAME,
            export_root / DRY_RUN_OPERATOR_EXPORT_NAME,
            export_root / OPERATOR_REVIEW_EXPORT_NAME,
            export_root / STRUCTURED_IMPORT_PLAN_JSON_EXPORT_NAME,
            export_root / STRUCTURED_IMPORT_PLAN_OPERATOR_EXPORT_NAME,
        )
    )

    assert "/mnt/c/OpenClaw" not in rendered
    assert "/mnt/c/OpenClawShared" not in rendered
    assert "spreadsheet cells" in rendered
    assert "raw data was imported" in rendered
    assert "redacted://" in rendered


def test_new_memory_sources_have_no_repo_b_network_subprocess_or_send_behavior():
    source_files = [
        Path("cassandra_chief_memory_authority.py"),
        Path("scripts/export_cassandra_chief_memory_authority_read_model.py"),
        Path("scripts/query_cassandra_chief_memory_authority.py"),
    ]
    forbidden = [
        "/home/openclaw_external/openclaw-runtime",
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "send_message",
        "reply_text",
        "smtplib",
        "shell=True",
        "eval(",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for token in forbidden:
            assert token.lower() not in lowered

    assert all(value is False for value in NO_AUTHORITY_FLAGS.values() if isinstance(value, bool))
