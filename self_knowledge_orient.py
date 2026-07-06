"""Authorized self-orientation access to the local self-knowledge ledger.

This module is intentionally local and read-only. It exposes no server,
network listener, external model path, or mutation path. The root command is:

    python -m self_knowledge_orient --level high

Callers must be inside an authorized local OpenClaw context. The authorization
check is explicit and injectable so future Guardian-granted, time-windowed
off-site contexts can snap into the same API without rewriting the orienter.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import platform
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_LEDGER_PATH = ROOT / ".openclaw" / "business_ops" / "ledger.sqlite"
GRAPH_NODE_TABLE = "knowledge_system_nodes"
GRAPH_EDGE_TABLE = "knowledge_system_edges"
VALID_LEVELS = ("high", "medium", "deep")
ALLOWED_NETWORK_CONTEXTS = frozenset({"local_process", "local_network", "operator_runtime"})


@dataclass(frozen=True)
class OrientationContext:
    """Principal + context + optional time window for orientation access."""

    principal: str
    machine_id: str
    network_context: str
    local_process: bool = True
    expires_at: str | None = None
    grant_source: str = "local_runtime_default"
    os_user: str | None = None
    external_model_context: bool = False


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str
    policy: str = "self_knowledge_orientation_authorization_v1"


Authorizer = Callable[[OrientationContext], AuthorizationDecision | bool]


def _split_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _allowed_principals() -> set[str]:
    configured = set(_split_csv(os.environ.get("OPENCLAW_ORIENT_ALLOWED_PRINCIPALS")))
    if configured:
        return configured
    current_user = getpass.getuser()
    return {current_user, os.environ.get("USER", ""), "openclaw"} - {""}


def _parse_expires_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)


def authorize_orientation_context(context: OrientationContext) -> AuthorizationDecision:
    """Default allowlist policy for local authorized OpenClaw orientation."""

    if context.external_model_context:
        return AuthorizationDecision(False, "external_model_context_denied")
    if not context.local_process:
        return AuthorizationDecision(False, "not_a_local_process")
    if context.network_context not in ALLOWED_NETWORK_CONTEXTS:
        return AuthorizationDecision(False, "network_context_not_authorized")
    if context.principal not in _allowed_principals():
        return AuthorizationDecision(False, "principal_not_authorized")
    if context.os_user and context.principal != context.os_user:
        return AuthorizationDecision(False, "principal_does_not_match_os_user")

    expires_at = _parse_expires_at(context.expires_at)
    if expires_at is not None and expires_at <= datetime.now(UTC):
        return AuthorizationDecision(False, "authorization_window_expired")

    return AuthorizationDecision(True, "authorized_local_operator_context")


def current_orientation_context(
    *,
    principal: str | None = None,
    network_context: str | None = None,
    expires_at: str | None = None,
) -> OrientationContext:
    os_user = getpass.getuser()
    context_name = network_context or os.environ.get("OPENCLAW_ORIENT_NETWORK_CONTEXT") or "local_process"
    return OrientationContext(
        principal=principal or os.environ.get("OPENCLAW_ORIENT_PRINCIPAL") or os_user,
        machine_id=os.environ.get("OPENCLAW_MACHINE_ID") or platform.node() or "unknown-machine",
        network_context=context_name,
        local_process=context_name in ALLOWED_NETWORK_CONTEXTS,
        expires_at=expires_at or os.environ.get("OPENCLAW_ORIENT_EXPIRES_AT"),
        grant_source=os.environ.get("OPENCLAW_ORIENT_GRANT_SOURCE") or "local_runtime_default",
        os_user=os_user,
        external_model_context=os.environ.get("OPENCLAW_ORIENT_EXTERNAL_MODEL_CONTEXT") == "1",
    )


def _normalize_authorization(decision: AuthorizationDecision | bool) -> AuthorizationDecision:
    if isinstance(decision, AuthorizationDecision):
        return decision
    return AuthorizationDecision(bool(decision), "custom_authorizer")


def _assert_authorized(context: OrientationContext, authorizer: Authorizer | None) -> AuthorizationDecision:
    decision = _normalize_authorization((authorizer or authorize_orientation_context)(context))
    if not decision.allowed:
        raise PermissionError(f"self-knowledge orientation denied: {decision.reason}")
    return decision


def _source_envelope(ledger_path: Path) -> dict[str, Any]:
    return {
        "ledger_path": ledger_path.as_posix(),
        "node_table": GRAPH_NODE_TABLE,
        "edge_table": GRAPH_EDGE_TABLE,
        "read_only": True,
    }


def _authority_boundary() -> dict[str, bool]:
    return {
        "read_only": True,
        "local_only": True,
        "network_endpoint": False,
        "ledger_mutation": False,
        "runtime_mutation": False,
        "external_call": False,
        "external_model_packet_allowed": False,
        "send_or_payment_allowed": False,
    }


def _auth_envelope(context: OrientationContext, decision: AuthorizationDecision) -> dict[str, Any]:
    return {
        "policy": decision.policy,
        "reason": decision.reason,
        "principal": context.principal,
        "machine_id": context.machine_id,
        "network_context": context.network_context,
        "grant_source": context.grant_source,
        "expires_at": context.expires_at,
    }


def _base_envelope(
    *,
    level: str,
    ledger_path: Path,
    context: OrientationContext,
    decision: AuthorizationDecision,
    status: str,
) -> dict[str, Any]:
    return {
        "schema_version": "self_knowledge_orientation_v1",
        "status": status,
        "level": level,
        "single_source_of_truth": "self_knowledge_ledger",
        "source": _source_envelope(ledger_path),
        "authority_boundary": _authority_boundary(),
        "authorization": _auth_envelope(context, decision),
    }


def _not_yet_crawled(
    *,
    level: str,
    ledger_path: Path,
    context: OrientationContext,
    decision: AuthorizationDecision,
    reason: str,
) -> dict[str, Any]:
    payload = _base_envelope(
        level=level,
        ledger_path=ledger_path,
        context=context,
        decision=decision,
        status="not_yet_crawled",
    )
    payload.update(
        {
            "message": f"Self-knowledge graph not yet crawled into the ledger ({reason}).",
            "map": {},
        }
    )
    return payload


def _sqlite_read_uri(path: Path) -> str:
    return f"file:{path.resolve().as_posix()}?mode=ro"


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    }


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
    for key in ("health_status", "activation_state", "last_seen_at", "last_verified_at"):
        if row[key] is not None:
            payload.setdefault(key, row[key])
    return payload


def _read_graph(ledger_path: Path, *, owner_scope: str | None = None) -> tuple[str, str, dict[str, dict[str, Any]], list[dict[str, str]]]:
    if not ledger_path.exists():
        return "not_yet_crawled", "ledger_missing", {}, []

    try:
        with sqlite3.connect(_sqlite_read_uri(ledger_path), uri=True) as conn:
            conn.row_factory = sqlite3.Row
            tables = _table_names(conn)
            if GRAPH_NODE_TABLE not in tables or GRAPH_EDGE_TABLE not in tables:
                return "not_yet_crawled", "graph_tables_missing", {}, []

            node_sql = f'SELECT * FROM "{GRAPH_NODE_TABLE}"'
            node_args: tuple[Any, ...] = ()
            if owner_scope:
                node_sql += " WHERE owner_scope = ?"
                node_args = (owner_scope,)
            nodes = {
                row["node_id"]: _decode_payload(row)
                for row in conn.execute(node_sql, node_args)
            }

            edge_sql = f'SELECT * FROM "{GRAPH_EDGE_TABLE}"'
            edge_args: tuple[Any, ...] = ()
            if owner_scope:
                edge_sql += " WHERE owner_scope = ?"
                edge_args = (owner_scope,)
            edges = [
                {
                    "source": row["source_node_id"],
                    "target": row["target_node_id"],
                    "relation": row["relation"],
                    "owner_scope": row["owner_scope"],
                }
                for row in conn.execute(edge_sql, edge_args)
            ]
    except sqlite3.Error as exc:
        return "not_yet_crawled", f"ledger_unreadable:{type(exc).__name__}", {}, []

    if not nodes:
        return "not_yet_crawled", "graph_empty", {}, []
    return "ok", "graph_loaded", nodes, edges


def _count_kind(nodes: Mapping[str, Mapping[str, Any]], kind: str) -> int:
    return sum(1 for node in nodes.values() if node.get("kind") == kind)


def _count_by(nodes: Mapping[str, Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in nodes.values():
        value = str(node.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _nodes_of_kind(nodes: Mapping[str, Mapping[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [dict(node) for node in nodes.values() if node.get("kind") == kind]


def _node_label(node: Mapping[str, Any]) -> str:
    return str(node.get("display_name") or node.get("name") or node.get("unit") or node.get("id") or "")


def _health_rollup(nodes: Mapping[str, Mapping[str, Any]]) -> str:
    rollups = _nodes_of_kind(nodes, "health_rollup")
    if rollups:
        state = str(rollups[0].get("activation_state") or "")
        if state:
            return state
    failed = sum(
        1
        for node in nodes.values()
        if node.get("kind") == "service" and node.get("health_status") == "failed"
    )
    return f"{failed}_red" if failed else "green"


def _graph_anomalies(nodes: Mapping[str, Mapping[str, Any]]) -> list[str]:
    anomalies: list[str] = []
    for node in nodes.values():
        kind = node.get("kind")
        label = _node_label(node)
        if kind == "service" and node.get("health_status") == "failed":
            anomalies.append(f"{label} = FAILED")
        if kind == "worktree" and node.get("detached"):
            anomalies.append(f"{label} detached HEAD")
        if kind == "worktree" and int(node.get("dirty") or 0) > 0:
            anomalies.append(f"{label} DIRTY:{node.get('dirty')}")
        if kind == "ollama_model" and node.get("health_status") == "retired":
            anomalies.append(f"{label} retired but present on disk")
    return sorted(dict.fromkeys(anomalies))


def _source_of_truth(nodes: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    for node in nodes.values():
        if node.get("kind") == "sqlite_db" and node.get("role") == "source_of_truth":
            return {
                "path": node.get("path"),
                "size_bytes": node.get("size_bytes"),
                "role": "source_of_truth",
            }
    return {}


def _brief_agent(node: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        "name": node.get("name") or str(node.get("id") or "").removeprefix("agent:"),
        "role": node.get("role"),
        "entry": node.get("entry"),
        "state": node.get("activation_state"),
    }
    if node.get("alias"):
        result["alias"] = node.get("alias")
    if node.get("model"):
        result["model"] = node.get("model")
    if node.get("voice"):
        result["voice"] = node.get("voice")
    return {key: value for key, value in result.items() if value not in (None, "")}


def _high_map(nodes: Mapping[str, Mapping[str, Any]], edges: list[dict[str, str]]) -> dict[str, Any]:
    machines = sorted(_nodes_of_kind(nodes, "machine"), key=_node_label)
    agents = sorted(_nodes_of_kind(nodes, "agent"), key=lambda node: str(node.get("name") or node.get("id")))
    key_services = sorted(
        _nodes_of_kind(nodes, "service"),
        key=lambda node: (0 if node.get("health_status") == "failed" else 1, _node_label(node)),
    )[:8]
    counts = {
        "machine_count": _count_kind(nodes, "machine"),
        "repo_count": _count_kind(nodes, "repo"),
        "worktree_count": _count_kind(nodes, "worktree"),
        "nested_repo_count": _count_kind(nodes, "nested_repo"),
        "openclaw_instance_count": _count_kind(nodes, "openclaw_instance"),
        "agent_count": _count_kind(nodes, "agent"),
        "sidecar_count": _count_kind(nodes, "sidecar"),
        "service_count": _count_kind(nodes, "service"),
        "timer_count": _count_kind(nodes, "timer"),
        "cron_count": _count_kind(nodes, "cron"),
        "windows_task_count": _count_kind(nodes, "windows_task"),
        "ollama_model_count": _count_kind(nodes, "ollama_model"),
        "port_count": _count_kind(nodes, "port"),
        "sqlite_db_count": _count_kind(nodes, "sqlite_db"),
        "edge_count": len(edges),
    }
    health = _health_rollup(nodes)
    return {
        "health": health,
        "one_liner": (
            f"{counts['machine_count']} machines; {counts['agent_count']} agents; "
            f"{counts['service_count']} services; {health}; {counts['worktree_count']} worktrees."
        ),
        "counts": counts,
        "machines": [
            {
                "id": node.get("id"),
                "role": node.get("role") or node.get("display_name"),
                "state": node.get("activation_state"),
                "evidence": node.get("evidence_status"),
            }
            for node in machines
        ],
        "agents": [_brief_agent(node) for node in agents],
        "key_services": [
            {
                "id": node.get("id"),
                "unit": node.get("unit") or node.get("display_name"),
                "state": node.get("activation_state"),
                "health_status": node.get("health_status"),
            }
            for node in key_services
        ],
        "anomalies": _graph_anomalies(nodes),
        "source_of_truth": _source_of_truth(nodes),
        "degraded": next(
            (
                node.get("degraded")
                for node in _nodes_of_kind(nodes, "health_rollup")
                if isinstance(node.get("degraded"), list)
            ),
            [],
        ),
        "health_counts": _count_by(nodes, "health_status"),
        "activation_states": _count_by(nodes, "activation_state"),
    }


def _brief_node(node: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    result = {"id": node.get("id"), "kind": node.get("kind")}
    for key in keys:
        if key in node:
            result[key] = node[key]
    if "health_status" in node:
        result["health_status"] = node["health_status"]
    if "activation_state" in node:
        result["activation_state"] = node["activation_state"]
    return result


def _medium_map(nodes: Mapping[str, Mapping[str, Any]], *, owner_scope: str | None = None) -> dict[str, Any]:
    machines: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for node in nodes.values():
        machine = str(node.get("owner_scope") or owner_scope or "unknown")
        if owner_scope and machine != owner_scope:
            continue
        bucket = machines.setdefault(
            machine,
            {
                "repos": [],
                "worktrees": [],
                "nested_repos": [],
                "services": [],
                "timers": [],
                "cron": [],
                "windows_tasks": [],
                "ports": [],
                "ollama_models": [],
                "sqlite_dbs": [],
                "agents": [],
                "sidecars": [],
                "health_rollups": [],
                "openclaw_instances": [],
            },
        )
        kind = node.get("kind")
        if kind == "repo":
            bucket["repos"].append(_brief_node(node, ("path", "branch", "head_commit")))
        elif kind == "worktree":
            bucket["worktrees"].append(
                _brief_node(node, ("worktree_path", "repo_path", "branch", "head_commit", "dirty"))
            )
        elif kind == "service":
            bucket["services"].append(_brief_node(node, ("unit", "load", "active", "sub")))
        elif kind == "nested_repo":
            bucket["nested_repos"].append(_brief_node(node, ("path", "branch", "head_commit", "dirty", "remote")))
        elif kind == "timer":
            bucket["timers"].append(_brief_node(node, ("unit", "activation_state")))
        elif kind == "cron":
            bucket["cron"].append(_brief_node(node, ("key_facts", "activation_state")))
        elif kind == "windows_task":
            bucket["windows_tasks"].append(_brief_node(node, ("display_name", "activation_state", "key_facts")))
        elif kind == "port":
            bucket["ports"].append(_brief_node(node, ("local_address_port", "process", "activation_state")))
        elif kind == "ollama_model":
            bucket["ollama_models"].append(_brief_node(node, ("model_name", "activation_state", "key_facts")))
        elif kind == "sqlite_db":
            bucket["sqlite_dbs"].append(_brief_node(node, ("path", "role", "size_bytes")))
        elif kind == "agent":
            bucket["agents"].append(_brief_agent(node))
        elif kind == "sidecar":
            bucket["sidecars"].append(_brief_node(node, ("path", "state", "evidence_status")))
        elif kind == "health_rollup":
            bucket["health_rollups"].append(_brief_node(node, ("failed_services", "degraded", "activation_state")))
        elif kind == "openclaw_instance":
            bucket["openclaw_instances"].append(_brief_node(node, ("root_path", "activity_status")))

    for bucket in machines.values():
        for key, rows in bucket.items():
            bucket[key] = sorted(
                rows,
                key=lambda row: str(
                    row.get("path")
                    or row.get("worktree_path")
                    or row.get("unit")
                    or row.get("local_address_port")
                    or row.get("name")
                    or row.get("root_path")
                    or row.get("id")
                ),
            )
    return {"machines": dict(sorted(machines.items()))}


def _neighbor_ids(edges: list[dict[str, str]], node_id: str) -> set[str]:
    neighbors: set[str] = set()
    for edge in edges:
        if edge.get("source") == node_id:
            neighbors.add(str(edge.get("target") or ""))
        if edge.get("target") == node_id:
            neighbors.add(str(edge.get("source") or ""))
    neighbors.discard("")
    return neighbors


def _deep_map(
    nodes: Mapping[str, Mapping[str, Any]],
    edges: list[dict[str, str]],
    *,
    node_id: str | None = None,
) -> dict[str, Any]:
    if node_id:
        incident = [
            dict(edge)
            for edge in edges
            if edge.get("source") == node_id or edge.get("target") == node_id
        ]
        neighbors = [
            dict(nodes[nid])
            for nid in sorted(_neighbor_ids(edges, node_id))
            if nid in nodes
        ]
        return {
            "node": dict(nodes[node_id]) if node_id in nodes else None,
            "neighbors": neighbors,
            "edges": incident,
        }
    return {
        "nodes": [dict(nodes[node_id]) for node_id in sorted(nodes)],
        "edges": sorted(edges, key=lambda edge: (edge["source"], edge["target"], edge["relation"])),
    }


def orient(
    level: str = "high",
    *,
    ledger_path: str | Path | None = None,
    context: OrientationContext | None = None,
    authorizer: Authorizer | None = None,
    owner_scope: str | None = None,
    node_id: str | None = None,
) -> dict[str, Any]:
    """Return the system map at high, medium, or deep resolution."""

    level_key = str(level or "high").lower()
    if level_key not in VALID_LEVELS:
        raise ValueError(f"unknown orientation level: {level!r}")

    auth_context = context or current_orientation_context()
    decision = _assert_authorized(auth_context, authorizer)
    ledger = Path(ledger_path or os.environ.get("OPENCLAW_SELF_KNOWLEDGE_LEDGER") or DEFAULT_LEDGER_PATH)
    status, reason, nodes, edges = _read_graph(ledger, owner_scope=owner_scope)
    if status != "ok":
        return _not_yet_crawled(
            level=level_key,
            ledger_path=ledger,
            context=auth_context,
            decision=decision,
            reason=reason,
        )

    if level_key == "high":
        system_map = _high_map(nodes, edges)
    elif level_key == "medium":
        system_map = _medium_map(nodes, owner_scope=owner_scope)
    else:
        system_map = _deep_map(nodes, edges, node_id=node_id)

    from self_knowledge_completeness import build_graph_coverage_section

    coverage = build_graph_coverage_section(nodes)
    if isinstance(system_map, dict):
        system_map["coverage"] = coverage

    payload = _base_envelope(
        level=level_key,
        ledger_path=ledger,
        context=auth_context,
        decision=decision,
        status="ok",
    )
    payload.update(
        {
            "message": "Self-knowledge orientation loaded from the local ledger.",
            "map": system_map,
            "coverage": coverage,
        }
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Orient from the authorized local self-knowledge ledger.")
    parser.add_argument("--level", choices=VALID_LEVELS, default="high")
    parser.add_argument("--ledger-path", help="SQLite ledger path. Defaults to OPENCLAW_SELF_KNOWLEDGE_LEDGER or local business ledger.")
    parser.add_argument("--owner-scope", help="Optional machine/owner scope, such as pc or mac.")
    parser.add_argument("--node-id", help="Optional deep-level node id to inspect.")
    parser.add_argument("--principal", help="Authorized principal. Defaults to current OS user.")
    parser.add_argument("--network-context", choices=sorted(ALLOWED_NETWORK_CONTEXTS), default=None)
    parser.add_argument("--expires-at", help="Optional authorization expiry timestamp for future time-windowed grants.")
    args = parser.parse_args(argv)

    context = current_orientation_context(
        principal=args.principal,
        network_context=args.network_context,
        expires_at=args.expires_at,
    )
    try:
        payload = orient(
            level=args.level,
            ledger_path=args.ledger_path,
            context=context,
            owner_scope=args.owner_scope,
            node_id=args.node_id,
        )
    except PermissionError as exc:
        print(json.dumps({"status": "unauthorized", "reason": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 2

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
