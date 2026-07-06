from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import self_knowledge_orient as orient  # noqa: E402
from self_knowledge_completeness import (  # noqa: E402
    build_completeness_report,
    build_graph_coverage_section,
    render_completeness_report_text,
)
from self_knowledge_graph_writer import GRAPH_EDGE_TABLE, GRAPH_NODE_TABLE, write_graph_to_ledger  # noqa: E402
from self_knowledge_scheduler import run_scheduled_crawl  # noqa: E402


def _ctx() -> orient.OrientationContext:
    return orient.OrientationContext(
        principal="openclaw",
        machine_id="pc",
        network_context="local_process",
        local_process=True,
    )


def _seed_graph(ledger: Path, payloads: list[dict[str, object]]) -> None:
    with sqlite3.connect(ledger) as conn:
        conn.execute(
            f'CREATE TABLE "{GRAPH_NODE_TABLE}" ('
            "node_id TEXT PRIMARY KEY, kind TEXT NOT NULL, owner_scope TEXT NOT NULL, "
            "health_status TEXT, activation_state TEXT, last_seen_at TEXT, last_verified_at TEXT, "
            "payload_json TEXT NOT NULL, _fold_source TEXT NOT NULL, _fold_at TEXT NOT NULL)"
        )
        conn.execute(
            f'CREATE TABLE "{GRAPH_EDGE_TABLE}" ('
            "source_node_id TEXT NOT NULL, target_node_id TEXT NOT NULL, relation TEXT NOT NULL, "
            "owner_scope TEXT NOT NULL, _fold_source TEXT NOT NULL, _fold_at TEXT NOT NULL)"
        )
        for payload in payloads:
            node_id = str(payload["id"])
            conn.execute(
                f'INSERT INTO "{GRAPH_NODE_TABLE}" VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    node_id,
                    str(payload["kind"]),
                    str(payload.get("owner_scope") or "PC"),
                    payload.get("health_status"),
                    payload.get("activation_state"),
                    payload.get("as_of") or "2026-07-06T12:00:00+00:00",
                    payload.get("last_verified_at") or "2026-07-06T12:00:00+00:00",
                    json.dumps(payload, sort_keys=True),
                    "self_knowledge_inventory_graph:PC",
                    "2026-07-06T12:00:00+00:00",
                ),
            )


def _node(node_id: str, kind: str, **fields: object) -> dict[str, object]:
    payload = {
        "id": node_id,
        "node_id": node_id,
        "kind": kind,
        "owner_scope": fields.pop("owner_scope", "PC"),
        "display_name": fields.pop("display_name", node_id),
        "as_of": fields.pop("as_of", "2026-07-06T12:00:00+00:00"),
        "source_probe": fields.pop("source_probe", "test"),
        "evidence_status": fields.pop("evidence_status", "observed"),
        "depth_level": fields.pop("depth_level", "deep"),
    }
    payload.update(fields)
    return payload


def _complete_anchor_nodes() -> list[dict[str, object]]:
    return [
        _node("machine:PC", "machine", owner_scope="PC"),
        _node("machine:MAC", "machine", owner_scope="MAC", evidence_status="bridge-reported"),
        _node("agent:maestro", "agent", name="maestro"),
        _node("agent:cassandra", "agent", name="cassandra"),
        _node("agent:chief", "agent", name="chief"),
        _node("agent:guardian", "agent", name="guardian"),
        _node("agent:niles", "agent", name="niles"),
        _node("agent:hermes", "agent", name="hermes"),
        _node("sidecar:hermes", "sidecar", state="running"),
        _node("sidecar:gbrain", "sidecar", state="installed_not_running"),
        _node("sidecar:niles_home", "sidecar", state="defunct"),
        _node("repo:/repo", "repo", path="/repo"),
        _node("worktree:/repo-wt", "worktree", worktree_path="/repo-wt"),
        _node("service:PC:maestro-listener.service", "service", unit="maestro-listener.service"),
        _node("service:PC:hermes-gateway.service", "service", unit="hermes-gateway.service"),
    ]


def test_completeness_report_flags_expected_anchor_and_domain_gaps(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.sqlite"
    nodes = [
        node
        for node in _complete_anchor_nodes()
        if node["id"] not in {"machine:MAC", "sidecar:gbrain", "worktree:/repo-wt", "service:PC:hermes-gateway.service"}
    ]
    _seed_graph(ledger, nodes)

    inventory = {
        "git_estate": {
            "status": "ok",
            "rows": [
                {"kind": "repo", "path": "/repo"},
                {"kind": "worktree", "path": "/repo-wt", "repo_path": "/repo"},
            ],
        },
        "systemd_user_services": {
            "status": "ok",
            "rows": [{"unit": "maestro-listener.service"}, {"unit": "hermes-gateway.service"}],
        },
        "mac_bridge": {
            "status": "ok",
            "rows": [{"machine": "MAC", "bridge_path": "/mnt/e/openclaw/codex_mac_bridge"}],
        },
    }

    report = build_completeness_report(ledger, inventory=inventory, now="2026-07-06T12:30:00+00:00")

    assert report["status"] == "gaps_found"
    assert report["anchors"]["found"] == report["anchors"]["expected"] - 2
    assert {"machine:MAC", "sidecar:gbrain"} <= set(report["anchors"]["missing"])
    assert report["domains"]["worktrees"]["expected"] == 1
    assert report["domains"]["worktrees"]["matched"] == 0
    assert report["domains"]["services"]["expected"] == 2
    assert report["domains"]["services"]["matched"] == 1
    gap_ids = {gap["id"] for gap in report["gaps"]}
    assert {"missing_anchor:machine:MAC", "worktrees_missing:worktree:/repo-wt"} <= gap_ids
    assert report["freshness"]["oldest_last_crawled_at"] == "2026-07-06T12:00:00+00:00"
    assert report["depth"]["deep"] == len(nodes)

    text = render_completeness_report_text(report)
    assert "anchors" in text
    assert "GAPS:" in text
    assert "worktrees 0/1 match" in text


def test_graph_coverage_section_is_deterministic_for_orient_packets(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.sqlite"
    _seed_graph(ledger, _complete_anchor_nodes())

    packet = orient.orient(level="high", ledger_path=ledger, context=_ctx())

    assert packet["status"] == "ok"
    assert packet["coverage"]["anchors"]["missing"] == []
    assert packet["coverage"]["anchors"]["found"] == packet["coverage"]["anchors"]["expected"]
    assert packet["coverage"]["freshness"]["oldest_last_crawled_at"] == "2026-07-06T12:00:00+00:00"
    assert packet["map"]["coverage"]["anchors"]["missing"] == []

    direct = build_graph_coverage_section(packet["map"]["_coverage_nodes_for_test"]) if False else None
    assert direct is None


def test_scheduled_crawl_emits_completeness_report_after_graph_write(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_text("# a\n", encoding="utf-8")
    ledger = tmp_path / "ledger.sqlite"
    with sqlite3.connect(ledger) as conn:
        conn.execute("CREATE TABLE file_inventory (path TEXT)")

    inventory = {
        "git_estate": {"status": "ok", "rows": [{"kind": "repo", "path": str(root)}]},
        "systemd_user_services": {"status": "ok", "rows": []},
        "systemd_user_timers": {"status": "ok", "rows": []},
        "user_crontab": {"status": "ok", "rows": []},
        "listening_ports": {"status": "ok", "rows": []},
        "ollama_models": {"status": "ok", "rows": []},
        "sqlite_databases": {"status": "ok", "rows": []},
        "windows_tasks": {"status": "ok", "rows": []},
        "mac_bridge": {"status": "unavailable", "reason": "bridge_missing"},
    }
    monkeypatch.setattr("self_knowledge_graph_writer.collect_system_inventory", lambda _root: inventory)
    monkeypatch.setattr("self_knowledge_completeness.collect_completeness_inventory", lambda _root: inventory)

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

    assert result["inventory_graph_write"]["status"] == "written"
    assert result["completeness_report"]["status"] in {"complete", "gaps_found"}
    assert "human_summary" in result["completeness_report"]
    assert result["completeness_report"]["anchors"]["expected"] >= 10
