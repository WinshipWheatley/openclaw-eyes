from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_self_knowledge_scheduled_crawl as cli  # noqa: E402


def test_main_prints_completed_json_for_empty_lease_db(tmp_path, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_text("# a\n")

    rc = cli.main(
        [
            "--root",
            str(root),
            "--lease-db-path",
            str(tmp_path / "leases.sqlite"),
            "--state-db-path",
            str(tmp_path / "state.sqlite"),
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert payload["files_visited"] == 1
