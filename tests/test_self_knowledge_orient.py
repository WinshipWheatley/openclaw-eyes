from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import self_knowledge_orient as orient  # noqa: E402


def _ctx(**overrides):
    data = {
        "principal": "openclaw",
        "machine_id": "pc",
        "network_context": "local_process",
        "local_process": True,
    }
    data.update(overrides)
    return orient.OrientationContext(**data)


def _seed_graph_ledger(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            'CREATE TABLE knowledge_system_nodes ('
            'node_id TEXT PRIMARY KEY, kind TEXT NOT NULL, owner_scope TEXT NOT NULL, '
            'health_status TEXT, activation_state TEXT, last_seen_at TEXT, last_verified_at TEXT, '
            'payload_json TEXT NOT NULL, _fold_source TEXT NOT NULL, _fold_at TEXT NOT NULL)'
        )
        conn.execute(
            'CREATE TABLE knowledge_system_edges ('
            'source_node_id TEXT NOT NULL, target_node_id TEXT NOT NULL, relation TEXT NOT NULL, '
            'owner_scope TEXT NOT NULL, _fold_source TEXT NOT NULL, _fold_at TEXT NOT NULL)'
        )
        nodes = {
            "machine:pc": {"id": "machine:pc", "kind": "machine", "owner_scope": "pc", "health_status": "ok"},
            "repo:/home/openclaw": {
                "id": "repo:/home/openclaw",
                "kind": "repo",
                "owner_scope": "pc",
                "path": "/home/openclaw",
                "branch": "main",
                "health_status": "ok",
            },
            "worktree:/tmp/codex-62": {
                "id": "worktree:/tmp/codex-62",
                "kind": "worktree",
                "owner_scope": "pc",
                "worktree_path": "/tmp/codex-62",
                "repo_path": "/home/openclaw",
                "branch": "codex/62-self-knowledge-orientation-cheatcode",
                "dirty": False,
                "health_status": "ok",
            },
            "openclaw_instance:/tmp/codex-62": {
                "id": "openclaw_instance:/tmp/codex-62",
                "kind": "openclaw_instance",
                "owner_scope": "pc",
                "root_path": "/tmp/codex-62",
                "activity_status": "test",
                "health_status": "ok",
            },
            "service:pc:self-knowledge-crawl.timer": {
                "id": "service:pc:self-knowledge-crawl.timer",
                "kind": "service",
                "owner_scope": "pc",
                "unit": "self-knowledge-crawl.timer",
                "activation_state": "inactive",
                "health_status": "disabled",
            },
        }
        for node_id, payload in nodes.items():
            conn.execute(
                "INSERT INTO knowledge_system_nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    node_id,
                    payload["kind"],
                    payload["owner_scope"],
                    payload.get("health_status"),
                    payload.get("activation_state"),
                    "2026-07-05T12:00:00+00:00",
                    "2026-07-05T12:00:00+00:00",
                    json.dumps(payload, sort_keys=True),
                    "self_knowledge_inventory_graph:pc",
                    "2026-07-05T12:00:00+00:00",
                ),
            )
        edges = [
            ("machine:pc", "repo:/home/openclaw", "contains"),
            ("machine:pc", "worktree:/tmp/codex-62", "contains"),
            ("worktree:/tmp/codex-62", "repo:/home/openclaw", "branch-of"),
            ("worktree:/tmp/codex-62", "openclaw_instance:/tmp/codex-62", "has-state"),
            ("machine:pc", "service:pc:self-knowledge-crawl.timer", "runs"),
        ]
        for source, target, relation in edges:
            conn.execute(
                "INSERT INTO knowledge_system_edges VALUES (?, ?, ?, ?, ?, ?)",
                (source, target, relation, "pc", "self_knowledge_inventory_graph:pc", "2026-07-05T12:00:00+00:00"),
            )


def test_orient_high_returns_counts_health_and_read_only_boundary(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.sqlite"
    _seed_graph_ledger(ledger)

    payload = orient.orient(level="high", ledger_path=ledger, context=_ctx())

    assert payload["status"] == "ok"
    assert payload["level"] == "high"
    assert payload["single_source_of_truth"] == "self_knowledge_ledger"
    assert payload["source"]["read_only"] is True
    assert payload["authority_boundary"]["local_only"] is True
    assert payload["authority_boundary"]["external_model_packet_allowed"] is False
    assert payload["map"]["counts"] == {
        "machine_count": 1,
        "repo_count": 1,
        "worktree_count": 1,
        "openclaw_instance_count": 1,
        "service_count": 1,
        "edge_count": 5,
    }
    assert payload["map"]["health"]["ok"] == 4
    assert payload["map"]["activation_states"]["inactive"] == 1


def test_orient_medium_groups_repos_worktrees_branches_and_services_by_machine(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.sqlite"
    _seed_graph_ledger(ledger)

    payload = orient.orient(level="medium", ledger_path=ledger, context=_ctx(), owner_scope="pc")
    machine = payload["map"]["machines"]["pc"]

    assert machine["repos"][0]["path"] == "/home/openclaw"
    assert machine["repos"][0]["branch"] == "main"
    assert machine["worktrees"][0]["worktree_path"] == "/tmp/codex-62"
    assert machine["worktrees"][0]["branch"] == "codex/62-self-knowledge-orientation-cheatcode"
    assert machine["services"][0]["unit"] == "self-knowledge-crawl.timer"
    assert machine["services"][0]["activation_state"] == "inactive"
    assert machine["openclaw_instances"][0]["root_path"] == "/tmp/codex-62"


def test_orient_deep_returns_node_state_and_relationship_edges(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.sqlite"
    _seed_graph_ledger(ledger)

    payload = orient.orient(
        level="deep",
        ledger_path=ledger,
        context=_ctx(),
        node_id="worktree:/tmp/codex-62",
    )

    assert payload["map"]["node"]["kind"] == "worktree"
    assert payload["map"]["node"]["branch"] == "codex/62-self-knowledge-orientation-cheatcode"
    assert {node["kind"] for node in payload["map"]["neighbors"]} == {"machine", "openclaw_instance", "repo"}
    assert {edge["relation"] for edge in payload["map"]["edges"]} == {"contains", "branch-of", "has-state"}


def test_missing_data_returns_not_yet_crawled_without_fake_map(tmp_path: Path) -> None:
    payload = orient.orient(level="high", ledger_path=tmp_path / "missing.sqlite", context=_ctx())

    assert payload["status"] == "not_yet_crawled"
    assert payload["map"] == {}
    assert "not yet crawled" in payload["message"].lower()
    assert payload["authority_boundary"]["read_only"] is True


def test_unauthorized_context_is_denied_before_ledger_read(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.sqlite"
    _seed_graph_ledger(ledger)

    with pytest.raises(PermissionError):
        orient.orient(
            level="high",
            ledger_path=ledger,
            context=_ctx(principal="attacker", network_context="offsite", local_process=False),
        )


def test_expired_authorized_context_is_denied(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.sqlite"
    _seed_graph_ledger(ledger)

    with pytest.raises(PermissionError):
        orient.orient(
            level="high",
            ledger_path=ledger,
            context=_ctx(expires_at="2026-01-01T00:00:00+00:00"),
        )


def test_cli_runs_as_authorized_local_json(tmp_path: Path, capsys) -> None:
    ledger = tmp_path / "ledger.sqlite"
    _seed_graph_ledger(ledger)

    assert orient.main(["--level", "high", "--ledger-path", str(ledger), "--principal", "openclaw"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "ok"
    assert payload["level"] == "high"
    assert payload["map"]["counts"]["worktree_count"] == 1


def test_bootstrap_doc_and_first_look_pointers_are_discoverable() -> None:
    root = Path(__file__).resolve().parents[1]

    bootstrap = (root / "SELF-ORIENT.md").read_text(encoding="utf-8")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    runtime = (root / "OPENCLAW_RUNTIME.md").read_text(encoding="utf-8")

    assert "python -m self_knowledge_orient --level high" in bootstrap
    assert "single source" in bootstrap.lower()
    assert "SELF-ORIENT.md" in agents
    assert "self_knowledge_orient" in runtime


def test_source_has_no_network_endpoint_or_external_model_path() -> None:
    source = Path("self_knowledge_orient.py").read_text(encoding="utf-8")
    forbidden = (
        "http.server",
        "socketserver",
        "requests",
        "urllib.request",
        "openai",
        "anthropic",
        "subprocess",
        "smtplib",
        "googleapiclient",
    )

    for fragment in forbidden:
        assert fragment not in source
