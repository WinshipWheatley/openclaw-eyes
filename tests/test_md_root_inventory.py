import json
import sqlite3
from pathlib import Path

import md_root_inventory
from scripts.md_root_inventory import main as root_inventory_main


def _write(path: Path, text: str = "# Doc\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _row(db_path: Path, sql: str, params=()):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    return rows[0] if rows else None


def _rows(db_path: Path, sql: str, params=()):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(sql, params).fetchall()


def _fixture_roots(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "drive"
    _write(root / "README.md")
    _write(root / "nested" / "plan.md")
    _write(root / "legal" / "case.md")
    _write(root / "finance" / "tax.md")
    _write(root / ".git" / "ignored.md")
    missing = tmp_path / "missing"
    return root, missing


def test_schema_initializes_root_inventory_tables(tmp_path):
    db_path = tmp_path / "inventory.sqlite"

    assert md_root_inventory.md_root_inventory_table_names(db_path) == (
        "md_root_inventory_exclusions",
        "md_root_inventory_roots",
        "md_root_inventory_runs",
    )


def test_inventory_counts_allowed_markdown_and_redacts_sensitive_exclusions(tmp_path):
    root, missing = _fixture_roots(tmp_path)
    db_path = tmp_path / "inventory.sqlite"

    result = md_root_inventory.build_root_inventory(
        db_path=db_path,
        roots=[root, missing],
        run_id="inventory_fixture",
    )

    assert result.root_count == 2
    assert result.existing_root_count == 1
    assert result.allowed_markdown_count == 2
    assert result.excluded_path_count >= 3
    assert result.roots[0]["sample_paths"] == ["README.md", "nested/plan.md"]
    assert not any("legal" in path.lower() for item in result.roots for path in item["sample_paths"])
    exclusions = _rows(db_path, "SELECT * FROM md_root_inventory_exclusions")
    assert any(row["sensitive_path_redacted"] == 1 for row in exclusions)
    assert all("case.md" not in row["path"] for row in exclusions)


def test_inventory_records_receipt_without_runtime_or_body_authority(tmp_path):
    root, _missing = _fixture_roots(tmp_path)
    db_path = tmp_path / "inventory.sqlite"

    result = md_root_inventory.build_root_inventory(
        db_path=db_path,
        roots=[root],
        run_id="inventory_receipt",
    )
    row = _row(db_path, "SELECT * FROM md_root_inventory_runs WHERE run_id = ?", (result.run_id,))

    assert row["allowed_markdown_count"] == 2
    assert row["markdown_body_read_allowed"] == 0
    assert row["model_call_allowed"] == 0
    assert row["network_authority"] == 0
    assert row["source_markdown_writeback_allowed"] == 0
    assert row["truth_claimed"] == 0
    assert row["advisory_only"] == 1


def test_cli_json_and_operator_output(tmp_path, capsys):
    root, _missing = _fixture_roots(tmp_path)
    db_path = tmp_path / "inventory.sqlite"

    assert root_inventory_main(
        [
            "--db",
            str(db_path),
            "--run-id",
            "cli_json",
            "--root",
            str(root),
            "--format",
            "json",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["allowed_markdown_count"] == 2
    assert payload["no_authority_flags"]["markdown_body_read_allowed"] is False

    assert root_inventory_main(
        [
            "--db",
            str(db_path),
            "--run-id",
            "cli_operator",
            "--root",
            str(root),
            "--format",
            "operator",
        ]
    ) == 0
    assert "Markdown Root Inventory" in capsys.readouterr().out


def test_source_has_no_body_network_send_delete_move_or_writeback_authority():
    source = Path("md_root_inventory.py").read_text(encoding="utf-8").lower()

    for token in [
        "read_text",
        "read_bytes",
        "open(",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "smtplib",
        "send_message",
        "reply_text",
        "os.system",
        "shell=true",
        ".unlink(",
        ".rename(",
        "shutil.move",
        "shutil.rmtree",
        "write_text",
    ]:
        assert token not in source
    assert md_root_inventory.NO_AUTHORITY_FLAGS["markdown_body_read_allowed"] is False
    assert md_root_inventory.NO_AUTHORITY_FLAGS["source_markdown_writeback_allowed"] is False
    assert md_root_inventory.NO_AUTHORITY_FLAGS["truth_claimed"] is False
