"""Completeness reconciliation for the self-knowledge graph.

The graph crawler cannot prove its own coverage. This module compares graph
nodes against independent, injectable ground-truths and a curated anchor
manifest, then emits a deterministic JSON/text report.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import self_knowledge_system_enumerators as sen
from self_knowledge_graph_writer import AGENTS, GRAPH_EDGE_TABLE, GRAPH_NODE_TABLE

SCHEMA_VERSION = "self_knowledge_completeness_report_v1"
MANIFEST_VERSION = "self_knowledge_expected_anchor_manifest_v1"


@dataclass(frozen=True)
class ExpectedAnchor:
    id: str
    kind: str
    label: str
    required: bool = True


def expected_anchor_manifest(*, root: str | Path | None = None) -> tuple[ExpectedAnchor, ...]:
    anchors: list[ExpectedAnchor] = [
        ExpectedAnchor("machine:PC", "machine", "PC backend machine"),
        ExpectedAnchor("machine:MAC", "machine", "Mac bridge machine"),
    ]
    anchors.extend(
        ExpectedAnchor(f"agent:{agent['name']}", "agent", str(agent["name"]))
        for agent in AGENTS
    )
    anchors.extend(
        (
            ExpectedAnchor("sidecar:hermes", "sidecar", "Hermes sidecar"),
            ExpectedAnchor("sidecar:gbrain", "sidecar", "gbrain sidecar"),
            ExpectedAnchor("sidecar:niles_home", "sidecar", "niles_home sidecar"),
        )
    )
    if root is not None:
        root_path = Path(root).resolve()
        anchors.append(ExpectedAnchor(f"repo:{root_path}", "repo", "primary OpenClaw repo"))
    return tuple(anchors)


def _sqlite_read_uri(path: Path) -> str:
    return f"file:{path.resolve().as_posix()}?mode=ro"


def _decode_payload(row: sqlite3.Row) -> dict[str, Any]:
    try:
        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            payload = {}
    except (TypeError, json.JSONDecodeError):
        payload = {}
    payload.setdefault("id", row["node_id"])
    payload.setdefault("kind", row["kind"])
    payload.setdefault("owner_scope", row["owner_scope"])
    if row["last_seen_at"] is not None:
        payload.setdefault("as_of", row["last_seen_at"])
    if row["last_verified_at"] is not None:
        payload.setdefault("last_verified_at", row["last_verified_at"])
    return payload


def read_graph_nodes(ledger_path: str | Path) -> dict[str, dict[str, Any]]:
    ledger = Path(ledger_path)
    if not ledger.exists():
        return {}
    try:
        with sqlite3.connect(_sqlite_read_uri(ledger), uri=True) as conn:
            conn.row_factory = sqlite3.Row
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            if GRAPH_NODE_TABLE not in tables:
                return {}
            return {
                row["node_id"]: _decode_payload(row)
                for row in conn.execute(f'SELECT * FROM "{GRAPH_NODE_TABLE}"')
            }
    except sqlite3.Error:
        return {}


def collect_completeness_inventory(root: str | Path) -> dict[str, Any]:
    root_path = Path(root)
    return {
        "git_estate": sen.enumerate_git_estate(root_path),
        "systemd_user_services": sen.enumerate_systemd_user_services(),
        "mac_bridge": sen.enumerate_mac_bridge(),
    }


def _rows(inventory: Mapping[str, Any] | None, key: str) -> list[dict[str, Any]]:
    value = (inventory or {}).get(key)
    if not isinstance(value, Mapping) or value.get("status") != "ok":
        return []
    raw_rows = value.get("rows")
    if not isinstance(raw_rows, list):
        return []
    return [dict(row) for row in raw_rows if isinstance(row, Mapping)]


def _gap(gap_id: str, kind: str, expected_id: str, reason: str) -> dict[str, str]:
    return {
        "id": gap_id,
        "kind": kind,
        "expected_id": expected_id,
        "reason": reason,
    }


def _anchor_section(
    nodes: Mapping[str, Mapping[str, Any]],
    anchors: Iterable[ExpectedAnchor],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    anchor_list = tuple(anchors)
    missing = [anchor.id for anchor in anchor_list if anchor.required and anchor.id not in nodes]
    gaps = [
        _gap(f"missing_anchor:{anchor.id}", "anchor", anchor.id, f"{anchor.label} is absent from graph")
        for anchor in anchor_list
        if anchor.required and anchor.id not in nodes
    ]
    return (
        {
            "manifest_version": MANIFEST_VERSION,
            "expected": len([anchor for anchor in anchor_list if anchor.required]),
            "found": len([anchor for anchor in anchor_list if anchor.required and anchor.id in nodes]),
            "missing": missing,
        },
        gaps,
    )


def _domain_section(
    *,
    name: str,
    expected_ids: Iterable[str],
    nodes: Mapping[str, Mapping[str, Any]],
    reason: str,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    expected = tuple(dict.fromkeys(str(item) for item in expected_ids if item))
    missing = [node_id for node_id in expected if node_id not in nodes]
    matched = len(expected) - len(missing)
    gaps = [
        _gap(f"{name}_missing:{node_id}", name, node_id, reason)
        for node_id in missing
    ]
    return (
        {
            "expected": len(expected),
            "matched": matched,
            "missing": missing,
        },
        gaps,
    )


def _freshness_section(nodes: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    values: list[str] = []
    missing: list[str] = []
    for node_id, node in nodes.items():
        value = node.get("last_crawled_at") or node.get("as_of") or node.get("last_seen_at")
        if value:
            values.append(str(value))
        else:
            missing.append(node_id)
    values.sort()
    return {
        "oldest_last_crawled_at": values[0] if values else None,
        "newest_last_crawled_at": values[-1] if values else None,
        "nodes_missing_freshness": sorted(missing),
    }


def _depth_section(nodes: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in nodes.values():
        depth = str(node.get("depth_level") or node.get("crawl_depth") or "shallow")
        counts[depth] = counts.get(depth, 0) + 1
    return dict(sorted(counts.items()))


def _expected_from_inventory(inventory: Mapping[str, Any] | None) -> dict[str, tuple[str, ...]]:
    git_rows = _rows(inventory, "git_estate")
    service_rows = _rows(inventory, "systemd_user_services")
    mac_rows = _rows(inventory, "mac_bridge")
    return {
        "repos": tuple(
            f"repo:{row.get('path')}"
            for row in git_rows
            if str(row.get("kind") or "") == "repo" and row.get("path")
        ),
        "worktrees": tuple(
            f"worktree:{row.get('path')}"
            for row in git_rows
            if str(row.get("kind") or "") == "worktree" and row.get("path")
        ),
        "services": tuple(
            f"service:PC:{row.get('unit')}"
            for row in service_rows
            if row.get("unit")
        ),
        "agents": tuple(f"agent:{agent['name']}" for agent in AGENTS),
        "mac_bridge": tuple("machine:MAC" for _row in mac_rows[:1]),
    }


def build_graph_coverage_section(
    nodes: Mapping[str, Mapping[str, Any]],
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    anchors, anchor_gaps = _anchor_section(nodes, expected_anchor_manifest(root=root))
    return {
        "status": "complete" if not anchor_gaps else "gaps_found",
        "anchors": anchors,
        "freshness": _freshness_section(nodes),
        "depth": _depth_section(nodes),
        "gaps": anchor_gaps,
    }


def build_completeness_report(
    ledger_path: str | Path,
    *,
    root: str | Path | None = None,
    inventory: Mapping[str, Any] | None = None,
    now: str | None = None,
    anchors: Iterable[ExpectedAnchor] | None = None,
) -> dict[str, Any]:
    nodes = read_graph_nodes(ledger_path)
    if inventory is None and root is not None:
        inventory = collect_completeness_inventory(root)

    expected = _expected_from_inventory(inventory)
    anchor_section, gaps = _anchor_section(
        nodes,
        anchors if anchors is not None else expected_anchor_manifest(root=root),
    )
    domains: dict[str, dict[str, Any]] = {}
    for name, ids, reason in (
        ("repos", expected["repos"], "git repo observed independently but missing from graph"),
        ("worktrees", expected["worktrees"], "git worktree observed independently but missing from graph"),
        ("services", expected["services"], "systemd service observed independently but missing from graph"),
        ("agents", expected["agents"], "agent roster entry missing from graph"),
        ("mac_bridge", expected["mac_bridge"], "Mac bridge observed independently but missing from graph"),
    ):
        section, domain_gaps = _domain_section(name=name, expected_ids=ids, nodes=nodes, reason=reason)
        domains[name] = section
        gaps.extend(domain_gaps)

    gaps = sorted(gaps, key=lambda gap_item: gap_item["id"])
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now,
        "status": "complete" if not gaps else "gaps_found",
        "ledger_path": str(Path(ledger_path)),
        "anchors": anchor_section,
        "domains": domains,
        "freshness": _freshness_section(nodes),
        "depth": _depth_section(nodes),
        "gaps": gaps,
    }
    report["human_summary"] = render_completeness_report_text(report)
    return report


def render_completeness_report_text(report: Mapping[str, Any]) -> str:
    anchors = report.get("anchors") if isinstance(report.get("anchors"), Mapping) else {}
    domains = report.get("domains") if isinstance(report.get("domains"), Mapping) else {}

    def _domain_text(name: str) -> str:
        domain = domains.get(name) if isinstance(domains.get(name), Mapping) else {}
        return f"{name} {domain.get('matched', 0)}/{domain.get('expected', 0)} match"

    gaps = report.get("gaps") if isinstance(report.get("gaps"), list) else []
    gap_ids = [str(gap.get("id")) for gap in gaps if isinstance(gap, Mapping)]
    gap_text = ", ".join(gap_ids) if gap_ids else "none"
    return (
        f"{anchors.get('found', 0)}/{anchors.get('expected', 0)} anchors found; "
        f"{_domain_text('worktrees')}; {_domain_text('services')}; {_domain_text('agents')}; "
        f"GAPS: {gap_text}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile self-knowledge graph completeness.")
    parser.add_argument("--ledger-path", required=True)
    parser.add_argument("--root", default=None)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args(argv)
    report = build_completeness_report(args.ledger_path, root=args.root)
    if args.format == "text":
        print(render_completeness_report_text(report))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] in {"complete", "gaps_found"} else 1


__all__ = [
    "ExpectedAnchor",
    "build_completeness_report",
    "build_graph_coverage_section",
    "collect_completeness_inventory",
    "expected_anchor_manifest",
    "read_graph_nodes",
    "render_completeness_report_text",
]


if __name__ == "__main__":
    raise SystemExit(main())
