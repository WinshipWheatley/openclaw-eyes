from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import self_knowledge_orient as orient  # noqa: E402
from openclaw_estate_node_registry import REQUIRED_NODE_FIELDS  # noqa: E402
from self_knowledge_graph_writer import (  # noqa: E402
    GRAPH_EDGE_TABLE,
    GRAPH_NODE_TABLE,
    build_graph_write_plan,
    collect_system_inventory,
    write_graph_to_ledger,
)
from self_knowledge_ledger_gap_writer import ACTIVATION_TABLE  # noqa: E402
from self_knowledge_scheduler import run_scheduled_crawl  # noqa: E402


def _ctx() -> orient.OrientationContext:
    return orient.OrientationContext(
        principal="openclaw",
        machine_id="pc",
        network_context="local_process",
        local_process=True,
    )


def _seed_nonempty_ledger(ledger: Path) -> None:
    with sqlite3.connect(ledger) as conn:
        conn.execute("CREATE TABLE file_inventory (path TEXT)")


def _inventory(root: Path, ledger: Path) -> dict[str, object]:
    worktree = root.parent / "codex-71"
    hermes = root / "sidecars" / "hermes"
    return {
        "git_estate": {
            "status": "ok",
            "rows": [
                {
                    "kind": "repo",
                    "path": str(root),
                    "branch": "main",
                    "head_commit": "abc1234",
                    "dirty_count": 0,
                    "remote": "github.com/WinshipWheatley/openclaw-eyes.git",
                },
                {
                    "kind": "worktree",
                    "path": str(worktree),
                    "repo_path": str(root),
                    "branch": "codex/71-rebase-64-onto-current-main",
                    "head_commit": "def5678",
                    "dirty_count": 2,
                    "detached": False,
                },
                {
                    "kind": "nested_repo",
                    "path": str(hermes),
                    "branch": "main",
                    "head_commit": "fedcba9",
                    "dirty_count": 1,
                    "remote": "NousResearch/hermes-agent",
                },
            ],
        },
        "systemd_user_services": {
            "status": "ok",
            "rows": [
                {
                    "unit": "maestro-listener.service",
                    "load": "loaded",
                    "active": "active",
                    "sub": "running",
                    "description": "Maestro listener",
                },
                {
                    "unit": "openclaw-read-model-auto-refresh.service",
                    "load": "loaded",
                    "active": "failed",
                    "sub": "failed",
                    "description": "Read model refresh",
                },
            ],
        },
        "systemd_user_timers": {
            "status": "ok",
            "rows": [{"unit": "self-knowledge-crawl.timer", "next": "Mon", "left": "1m"}],
        },
        "user_crontab": {"status": "ok", "rows": ["*/5 * * * * /home/openclaw/polish_loop.sh"]},
        "listening_ports": {
            "status": "ok",
            "rows": [
                {
                    "state": "LISTEN",
                    "local_address_port": "127.0.0.1:11434",
                    "peer_address_port": "0.0.0.0:*",
                    "process": 'users:(("ollama",pid=11434,fd=3))',
                },
                {
                    "state": "LISTEN",
                    "local_address_port": "127.0.0.1:8771",
                    "peer_address_port": "0.0.0.0:*",
                    "process": 'users:(("kokoro",pid=8771,fd=3))',
                },
            ],
        },
        "ollama_models": {
            "status": "ok",
            "rows": [
                {"name": "qwen3:8b-q4_K_M", "size": "5.2 GB", "loaded": False, "tier": "interactive"},
                {"name": "gemma4:26b", "size": "17 GB", "loaded": False, "retired": True},
            ],
        },
        "sqlite_databases": {
            "status": "ok",
            "rows": [
                {
                    "path": str(ledger),
                    "relative_path": ".openclaw/business_ops/ledger.sqlite",
                    "size_bytes": 663_000_000,
                    "modified_at": "2026-07-05T12:00:00+00:00",
                }
            ],
        },
        "mac_bridge": {
            "status": "ok",
            "rows": [
                {
                    "machine": "MAC",
                    "bridge_path": "/mnt/e/openclaw/codex_mac_bridge",
                    "last_traffic": "2026-07-05T14:13:00+00:00",
                    "workspace": "/Users/hwinshipwheatley/Documents/Invoices/openclaw_invoice_workspace",
                }
            ],
        },
        "windows_tasks": {
            "status": "ok",
            "rows": [{"name": "OpenClawReadModelImport", "state": "Ready", "schedule": "5m"}],
        },
    }


def _node_payloads(ledger: Path) -> dict[str, dict[str, object]]:
    with sqlite3.connect(ledger) as conn:
        rows = conn.execute(f'SELECT node_id, payload_json FROM "{GRAPH_NODE_TABLE}"').fetchall()
    return {node_id: json.loads(payload) for node_id, payload in rows}


def test_graph_writer_persists_real_node_edge_tables_and_orient_reads_them(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    ledger = tmp_path / "ledger.sqlite"
    _seed_nonempty_ledger(ledger)

    result = write_graph_to_ledger(
        root,
        ledger,
        confirm=True,
        inventory=_inventory(root, ledger),
        now="2026-07-05T12:00:00+00:00",
    )

    assert result["status"] == "written"
    assert result["node_count"] >= 20
    assert result["edge_count"] >= 10

    payloads = _node_payloads(ledger)
    for node_id, payload in payloads.items():
        missing = [field for field in REQUIRED_NODE_FIELDS if field not in payload]
        assert not missing, f"{node_id} missing registry fields: {missing}"

    high = orient.orient(level="high", ledger_path=ledger, context=_ctx())
    assert high["status"] == "ok"
    assert high["map"]["health"] == "1_red"
    assert high["map"]["counts"]["machine_count"] == 2
    assert high["map"]["counts"]["worktree_count"] == 1
    assert high["map"]["counts"]["nested_repo_count"] == 1
    assert high["map"]["counts"]["agent_count"] == 6
    assert {agent["name"] for agent in high["map"]["agents"]} == {
        "maestro",
        "cassandra",
        "chief",
        "niles",
        "guardian",
        "hermes",
    }
    assert any("openclaw-read-model-auto-refresh.service" in item for item in high["map"]["anomalies"])

    medium = orient.orient(level="medium", ledger_path=ledger, context=_ctx(), owner_scope="PC")
    assert medium["map"]["machines"]["PC"]["worktrees"][0]["branch"] == (
        "codex/71-rebase-64-onto-current-main"
    )
    assert medium["map"]["machines"]["PC"]["nested_repos"][0]["path"].endswith("sidecars/hermes")
    assert medium["map"]["machines"]["PC"]["ports"][0]["local_address_port"] == "127.0.0.1:11434"

    deep = orient.orient(level="deep", ledger_path=ledger, context=_ctx(), node_id="agent:maestro")
    assert deep["map"]["node"]["kind"] == "agent"
    assert any(edge["relation"] == "served_by" for edge in deep["map"]["edges"])


def test_graph_writer_dry_run_does_not_create_ledger_tables(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    ledger = tmp_path / "ledger.sqlite"

    result = write_graph_to_ledger(
        root,
        ledger,
        confirm=False,
        inventory=_inventory(root, ledger),
        now="2026-07-05T12:00:00+00:00",
    )

    assert result["status"] == "dry_run"
    assert result["plan"]["node_count"] >= 20
    assert not ledger.exists()


def test_scheduled_crawl_writes_activation_and_rich_graph_in_same_confirmed_run(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_text("# a\n", encoding="utf-8")
    ledger = tmp_path / "ledger.sqlite"
    _seed_nonempty_ledger(ledger)

    monkeypatch.setattr(
        "self_knowledge_graph_writer.collect_system_inventory",
        lambda _root: _inventory(root, ledger),
    )

    result = run_scheduled_crawl(
        root,
        lease_db_path=tmp_path / "leases.sqlite",
        state_db_path=tmp_path / "state.sqlite",
        ledger_path=ledger,
        confirm_ledger_write=True,
        write_inventory_graph=True,
        write_activation_record=True,
        owner_scope="PC",
    )

    assert result["status"] == "completed"
    assert result["ledger_gap_write"]["status"] == "written"
    assert result["inventory_graph_write"]["status"] == "written"
    assert result["activation_record_write"]["status"] == "written"
    assert result["activation_record"]["ledger_write_confirmed"] is True
    assert result["activation_record"]["inventory_graph_write_confirmed"] is True

    with sqlite3.connect(ledger) as conn:
        assert conn.execute(f'SELECT COUNT(*) FROM "{GRAPH_NODE_TABLE}"').fetchone()[0] >= 20
        assert conn.execute(f'SELECT COUNT(*) FROM "{GRAPH_EDGE_TABLE}"').fetchone()[0] >= 10
        assert conn.execute(f'SELECT COUNT(*) FROM "{ACTIVATION_TABLE}"').fetchone()[0] == 1

    high = orient.orient(level="high", ledger_path=ledger, context=_ctx())
    assert high["status"] == "ok"
    assert high["map"]["counts"]["agent_count"] == 6


def test_collect_system_inventory_includes_rich_runtime_sources(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("self_knowledge_system_enumerators.enumerate_processes", lambda **_: {"status": "ok", "rows": []})
    monkeypatch.setattr("self_knowledge_system_enumerators.enumerate_user_crontab", lambda **_: {"status": "ok", "rows": []})
    monkeypatch.setattr("self_knowledge_system_enumerators.enumerate_systemd_user_services", lambda **_: {"status": "ok", "rows": []})
    monkeypatch.setattr("self_knowledge_system_enumerators.enumerate_listening_ports", lambda **_: {"status": "ok", "rows": []})
    monkeypatch.setattr("self_knowledge_system_enumerators.enumerate_sqlite_databases", lambda *_: {"status": "ok", "rows": []})
    monkeypatch.setattr("self_knowledge_system_enumerators.enumerate_git_estate", lambda *_args, **_kwargs: {"status": "ok", "rows": []})
    monkeypatch.setattr("self_knowledge_system_enumerators.enumerate_systemd_user_timers", lambda **_: {"status": "ok", "rows": []})
    monkeypatch.setattr("self_knowledge_system_enumerators.enumerate_ollama_models", lambda **_: {"status": "ok", "rows": []})
    monkeypatch.setattr("self_knowledge_system_enumerators.enumerate_windows_tasks", lambda **_: {"status": "ok", "rows": []})
    monkeypatch.setattr("self_knowledge_system_enumerators.enumerate_mac_bridge", lambda: {"status": "ok", "rows": []})

    inventory = collect_system_inventory(tmp_path)

    assert {"git_estate", "systemd_user_timers", "ollama_models", "windows_tasks", "mac_bridge"} <= set(inventory)
    assert build_graph_write_plan(tmp_path, tmp_path / "ledger.sqlite", inventory=inventory)["node_count"] >= 10
