from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from self_knowledge_crawler import crawl_filesystem, diff_filesystem_against_ledger  # noqa: E402


def test_crawl_filesystem_records_real_file_metadata(tmp_path):
    source = tmp_path / "repo"
    source.mkdir()
    tracked = source / "agent.py"
    tracked.write_text("print('hello')\n")

    crumbs = crawl_filesystem(source)

    assert crumbs == [
        {
            "kind": "file",
            "path": str(tracked),
            "relative_path": "agent.py",
            "size_bytes": tracked.stat().st_size,
            "sha256": "03e693d9f2f687e0f40e36a8df7fcb4d1c22974012b7c2a55c000eb30f305824",
        }
    ]


def test_crawl_filesystem_skips_secret_and_generated_dirs(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".chief.env").write_text("TOKEN=secret")
    (root / ".chief.env.bak").write_text("TOKEN=secret")
    (root / ".claude.json.tmp").write_text("{}")
    (root / ".openclaw" / "state").mkdir(parents=True)
    (root / ".openclaw" / "state" / "private.json").write_text("{}")
    (root / "FinancePrivate").mkdir()
    (root / "FinancePrivate" / "bank.txt").write_text("vault")
    (root / "generated" / "read_models").mkdir(parents=True)
    (root / "generated" / "read_models" / "state.json").write_text("{}")
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("# ok\n")

    crumbs = crawl_filesystem(root)

    assert [c["relative_path"] for c in crumbs] == ["src/main.py"]


def test_diff_filesystem_against_ledger_reports_unknown_files(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    known = root / "known.py"
    unknown = root / "unknown.py"
    known.write_text("# known\n")
    unknown.write_text("# unknown\n")

    ledger = tmp_path / "ledger.sqlite"
    with sqlite3.connect(ledger) as conn:
        conn.execute("CREATE TABLE file_inventory (path TEXT)")
        conn.execute("INSERT INTO file_inventory(path) VALUES (?)", (str(known),))

    result = diff_filesystem_against_ledger(root, ledger)

    assert result["status"] == "gaps_found"
    assert result["counts"] == {"filesystem_files": 2, "ledger_known_paths": 1, "unknown_files": 1}
    assert [gap["relative_path"] for gap in result["unknown_files"]] == ["unknown.py"]


def test_diff_handles_missing_ledger_as_unknown_not_green(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "thing.py").write_text("# thing\n")

    result = diff_filesystem_against_ledger(root, tmp_path / "missing.sqlite")

    assert result["status"] == "ledger_unavailable"
    assert result["counts"]["unknown_files"] == 1
    assert result["unknown_files"][0]["relative_path"] == "thing.py"


def test_crawl_filesystem_honors_max_files_budget(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    for idx in range(5):
        (root / f"{idx}.py").write_text(f"# {idx}\n")

    crumbs = crawl_filesystem(root, max_files=2)

    assert len(crumbs) == 2
    assert [c["relative_path"] for c in crumbs] == ["0.py", "1.py"]
