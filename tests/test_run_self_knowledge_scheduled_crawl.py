from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_self_knowledge_scheduled_crawl as cli  # noqa: E402
from self_knowledge_ledger_gap_writer import ACTIVATION_TABLE, GRAPH_NODE_TABLE  # noqa: E402


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


def test_main_can_confirm_write_ledger_graph_and_activation_records(tmp_path, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_text("# a\n")
    ledger = tmp_path / "ledger.sqlite"
    with sqlite3.connect(ledger) as conn:
        conn.execute("CREATE TABLE file_inventory (path TEXT)")

    rc = cli.main(
        [
            "--root",
            str(root),
            "--lease-db-path",
            str(tmp_path / "leases.sqlite"),
            "--state-db-path",
            str(tmp_path / "state.sqlite"),
            "--ledger-path",
            str(ledger),
            "--confirm-ledger-write",
            "--write-inventory-graph",
            "--write-activation-record",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert payload["ledger_gap_write"]["status"] == "written"
    assert payload["inventory_graph_write"]["status"] == "written"
    assert payload["activation_record_write"]["status"] == "written"

    with sqlite3.connect(ledger) as conn:
        assert conn.execute(f'SELECT COUNT(*) FROM "{GRAPH_NODE_TABLE}"').fetchone()[0] >= 2
        assert conn.execute(f'SELECT COUNT(*) FROM "{ACTIVATION_TABLE}"').fetchone()[0] == 1


def test_systemd_service_template_runs_confirmed_ledger_population() -> None:
    template = (
        Path(__file__).resolve().parents[1]
        / "systemd"
        / "user"
        / "self-knowledge-crawl.service.in"
    ).read_text(encoding="utf-8")

    assert "--ledger-path @REPO_ROOT@/.openclaw/business_ops/ledger.sqlite" in template
    assert "--confirm-ledger-write" in template
    assert "--write-inventory-graph" in template
    assert "--write-activation-record" in template
