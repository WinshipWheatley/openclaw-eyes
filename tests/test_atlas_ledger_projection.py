import json
import sqlite3
from pathlib import Path

from atlas_ledger_projection import record_atlas_file_inventory


def test_record_atlas_file_inventory_records_directory_and_priority_file_metadata(tmp_path: Path):
    atlas_path = tmp_path / "atlas.json"
    db_path = tmp_path / "ledger.sqlite"
    atlas_path.write_text(
        json.dumps(
            {
                "run": {"run_id": "run_fixture", "generated_at": "2026-06-14T00:00:00+00:00"},
                "roots": [{"root_id": "pc_live_repo", "path": "/home/openclaw"}],
                "directories": [
                    {
                        "run_id": "run_fixture",
                        "root_id": "pc_live_repo",
                        "machine": "pc",
                        "path": "/home/openclaw",
                        "name": "openclaw",
                        "category": "repo_root",
                        "blocked_reason": "",
                        "direct_file_count": 3,
                        "direct_dir_count": 2,
                        "direct_size_bytes": 120,
                    },
                    {
                        "run_id": "run_fixture",
                        "root_id": "pc_live_repo",
                        "machine": "pc",
                        "path": "/home/openclaw/.codex",
                        "name": ".codex",
                        "category": "protected_or_sensitive",
                        "blocked_reason": "sensitive_marker",
                        "direct_file_count": 0,
                        "direct_dir_count": 0,
                        "direct_size_bytes": 0,
                    },
                ],
                "priority_files": [
                    {
                        "run_id": "run_fixture",
                        "root_id": "pc_live_repo",
                        "machine": "pc",
                        "path": "/home/openclaw/chief_compose.py",
                        "name": "chief_compose.py",
                        "category": "priority_source_file",
                        "direct_size_bytes": 4096,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = record_atlas_file_inventory(atlas_path=atlas_path, db_path=db_path)

    assert result["metadata_only"] is True
    assert result["file_body_reads"] is False
    assert result["cleanup_authority_granted"] is False
    assert result["records_attempted"] == 3
    assert result["records_recorded"] == 3
    assert result["records_failed"] == 0

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT file_name, file_type_guess, ingest_eligibility, exclusion_reason FROM file_inventory ORDER BY file_name"
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        (".codex", "directory", "excluded", "sensitive_marker"),
        ("chief_compose.py", "py", "eligible_metadata_only", None),
        ("openclaw", "directory", "eligible_metadata_only", None),
    ]
