"""Persist the real self-knowledge structural graph into the knowledge ledger.

This is the missing bridge between the read-only system enumerators and
``self_knowledge_orient``. It creates and folds into the graph tables the
orienter already reads:

* ``knowledge_system_nodes``
* ``knowledge_system_edges``

Safety model matches ``self_knowledge_ledger_gap_writer``:

* dry-run by default, no ledger write;
* ``confirm=True`` requires an existing ledger file, takes a verified backup,
  then writes;
* idempotent: deletes only rows with this writer's fold source before insert.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

import self_knowledge_system_enumerators as sen
from openclaw_estate_node_registry import REQUIRED_NODE_FIELDS
from self_knowledge_ledger_gap_writer import ensure_ledger_backup

GRAPH_NODE_TABLE = "knowledge_system_nodes"
GRAPH_EDGE_TABLE = "knowledge_system_edges"
FOLD_SOURCE = "self_knowledge_inventory_graph:PC"

AGENTS: tuple[dict[str, Any], ...] = (
    {
        "name": "maestro",
        "role": "front-door",
        "entry": "maestro_listener.py(+responder)",
        "model": "qwen3:8b-q4_K_M",
        "service": "maestro-listener.service",
    },
    {
        "name": "cassandra",
        "alias": "Clara Reid",
        "role": "exec-assistant/AR",
        "entry": "maestro_cassandra_responder.py",
        "model": "qwen3:8b",
        "service": "cassandra-telegram.service",
    },
    {
        "name": "chief",
        "role": "orchestrator/brain hub",
        "entry": "chief_listener.py",
        "model": "qwen3:8b-q4_K_M",
        "service": "chief-listener.service",
    },
    {
        "name": "niles",
        "role": "producer(tier-1,no send)",
        "entry": "producer_listener.py",
        "model": "",
        "service": "niles-listener.service",
    },
    {
        "name": "guardian",
        "role": "HITL gate",
        "entry": "authority_gate.py",
        "model": "",
        "service": "",
    },
    {
        "name": "hermes",
        "role": "sidecar telegram gateway",
        "entry": "sidecars/hermes",
        "model": "qwen3:4b",
        "service": "hermes-gateway.service",
        "voice": "am_echo@8771",
    },
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _slug(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").casefold()).strip("-") or "unknown"


def _node_path_id(prefix: str, path: object) -> str:
    return f"{prefix}:{Path(str(path)).as_posix()}"


def _hash_id(prefix: str, value: object) -> str:
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}:{digest}"


def _scope(value: object = "PC") -> str:
    text = str(value or "PC").strip()
    return text.upper() if text.lower() in {"pc", "mac"} else text


def _estate_defaults(
    *,
    node_id: str,
    display_name: str,
    node_type: str,
    path: str = "",
    evidence_status: str = "observed",
) -> dict[str, Any]:
    known_paths = [{"path_kind": node_type, "path": path, "status": "known"}] if path else []
    return {
        "node_id": node_id,
        "display_name": display_name,
        "node_type": node_type,
        "known_paths": known_paths,
        "operating_system": "unknown",
        "hardware_class": "unknown",
        "mobility_class": "unknown",
        "authority_level": "self_knowledge_read_only",
        "canonicality": "observed_runtime_graph",
        "suited_work": [],
        "blocked_work": ["send_or_payment_execution", "secret_access", "ledger_mutation"],
        "allowed_access_patterns": [
            {"access_pattern": "local_read_only_orientation", "allowed": True, "boundary": "self_knowledge"}
        ],
        "sync_or_bridge_surfaces": [],
        "promotion_required_for_authority": "graph observation grants no runtime authority",
        "evidence_status": evidence_status,
        "operator_notes": "",
    }


def _payload(
    *,
    node_id: str,
    kind: str,
    display_name: str,
    owner_scope: str = "PC",
    path: str = "",
    state: str = "",
    health_status: str = "ok",
    activation_state: str = "",
    evidence_status: str = "observed",
    source_probe: str = "",
    as_of: str,
    key_facts: Mapping[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload = _estate_defaults(
        node_id=node_id,
        display_name=display_name,
        node_type=kind,
        path=path,
        evidence_status=evidence_status,
    )
    payload.update(
        {
            "id": node_id,
            "kind": kind,
            "owner_scope": owner_scope,
            "machine": owner_scope,
            "path": path,
            "state": state or activation_state or health_status,
            "health_status": health_status,
            "activation_state": activation_state,
            "evidence_status": evidence_status,
            "source_probe": source_probe,
            "as_of": as_of,
            "key_facts": dict(key_facts or {}),
        }
    )
    payload.update(extra)
    missing = [field for field in REQUIRED_NODE_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"node payload missing registry fields: {', '.join(missing)}")
    return payload


def _row(payload: Mapping[str, Any], *, fold_at: str) -> dict[str, Any]:
    return {
        "node_id": str(payload["id"]),
        "kind": str(payload["kind"]),
        "owner_scope": str(payload.get("owner_scope") or "PC"),
        "health_status": payload.get("health_status"),
        "activation_state": payload.get("activation_state"),
        "last_seen_at": payload.get("as_of") or fold_at,
        "last_verified_at": fold_at,
        "payload_json": json.dumps(dict(payload), sort_keys=True),
        "_fold_source": FOLD_SOURCE,
        "_fold_at": fold_at,
    }


def _edge(
    source: str,
    target: str,
    relation: str,
    *,
    owner_scope: str = "PC",
    fold_at: str,
) -> dict[str, str]:
    return {
        "source_node_id": source,
        "target_node_id": target,
        "relation": relation,
        "owner_scope": owner_scope,
        "_fold_source": FOLD_SOURCE,
        "_fold_at": fold_at,
    }


def collect_system_inventory(root: str | Path, *, timeout: int = sen.DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Run all read-only enumerators needed by the graph writer."""

    root_path = Path(root)
    inventory = sen.enumerate_system_state(timeout=timeout, repo_root=root_path)
    inventory["git_estate"] = sen.enumerate_git_estate(root_path, timeout=timeout)
    inventory["systemd_user_timers"] = sen.enumerate_systemd_user_timers(timeout=timeout)
    inventory["ollama_models"] = sen.enumerate_ollama_models(timeout=timeout)
    inventory["windows_tasks"] = sen.enumerate_windows_tasks(timeout=timeout)
    inventory["mac_bridge"] = sen.enumerate_mac_bridge()
    return inventory


def _inventory_rows(inventory: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    value = inventory.get(key)
    if not isinstance(value, Mapping) or value.get("status") != "ok":
        return []
    rows = value.get("rows")
    return [dict(row) for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _degraded(inventory: Mapping[str, Any]) -> list[str]:
    degraded: list[str] = []
    for key, value in sorted(inventory.items()):
        if isinstance(value, Mapping) and value.get("status") not in {None, "ok"}:
            degraded.append(f"{key}:{value.get('reason') or value.get('status')}")
    return degraded


def _service_health(row: Mapping[str, Any]) -> tuple[str, str]:
    active = _clean(row.get("active")).lower()
    sub = _clean(row.get("sub")).lower()
    if active == "failed" or sub == "failed":
        return "failed", "failed"
    if active == "active" and sub == "running":
        return "ok", "running"
    if active:
        return "unknown", active
    return "unknown", sub or "unknown"


def _sqlite_role(row: Mapping[str, Any]) -> str:
    path = str(row.get("path") or row.get("relative_path") or "").casefold()
    if path.endswith("/.openclaw/business_ops/ledger.sqlite") or path.endswith("ledger.sqlite"):
        return "source_of_truth"
    if "token" in path or "vault" in path:
        return "vault"
    if "memory" in path:
        return "rag"
    if "backup" in path or "debug" in path or "scratch" in path:
        return "scratch"
    if int(row.get("size_bytes") or 0) == 0:
        return "empty"
    return "sqlite_db"


def build_graph_write_plan(
    root: str | Path,
    ledger_path: str | Path,
    *,
    inventory: Mapping[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Return graph rows that would be folded into the ledger."""

    root_path = Path(root).resolve()
    fold_at = now or _utc_now_iso()
    observed = dict(inventory or collect_system_inventory(root_path))
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []

    def add_node(payload: dict[str, Any]) -> None:
        nodes[str(payload["id"])] = payload

    def add_edge(source: str, target: str, relation: str, owner_scope: str = "PC") -> None:
        if source in nodes and target in nodes:
            edges.append(_edge(source, target, relation, owner_scope=owner_scope, fold_at=fold_at))

    pc_id = "machine:PC"
    mac_id = "machine:MAC"
    board_id = "board:E-openclaw"
    add_node(
        _payload(
            node_id=pc_id,
            kind="machine",
            display_name="DESKTOP-HP / WSL2 OpenClaw PC",
            owner_scope="PC",
            health_status="ok",
            activation_state="running",
            evidence_status="observed",
            source_probe="local runtime",
            as_of=fold_at,
            operating_system="linux_wsl_on_pc",
            hardware_class="pc_workstation_wsl",
            mobility_class="stationary_backend",
            authority_level="canonical_backend_read_only_observation",
            canonicality="canonical_current_backend",
        )
    )
    mac_rows = _inventory_rows(observed, "mac_bridge")
    mac_row = mac_rows[0] if mac_rows else {}
    add_node(
        _payload(
            node_id=mac_id,
            kind="machine",
            display_name="Mac bridge node",
            owner_scope="MAC",
            path=str(mac_row.get("workspace") or ""),
            health_status="ok",
            activation_state="bridge-reported" if mac_rows else "declared",
            evidence_status="bridge-reported" if mac_rows else "declared",
            source_probe="bridge:codex_mac_bridge",
            as_of=str(mac_row.get("last_traffic") or fold_at),
            operating_system="macos",
            hardware_class="mac_development_machine",
            mobility_class="operator_mac",
        )
    )
    add_node(
        _payload(
            node_id=board_id,
            kind="board",
            display_name="E:/openclaw bridge board",
            owner_scope="shared",
            path=str(mac_row.get("bridge_path") or "/mnt/e/openclaw"),
            health_status="ok",
            activation_state="bridge",
            evidence_status="bridge-reported" if mac_rows else "declared",
            source_probe="bridge filesystem",
            as_of=str(mac_row.get("last_traffic") or fold_at),
            sync_or_bridge_surfaces=["/mnt/e/openclaw", "codex_mac_bridge"],
        )
    )
    add_edge(board_id, pc_id, "bridges", "shared")
    add_edge(board_id, mac_id, "bridges", "shared")

    repo_ids: dict[str, str] = {}
    has_worktree = False
    for row in _inventory_rows(observed, "git_estate"):
        kind = str(row.get("kind") or "")
        path = str(row.get("path") or "")
        if not path:
            continue
        if kind == "repo":
            node_id = _node_path_id("repo", path)
            repo_ids[path] = node_id
            add_node(
                _payload(
                    node_id=node_id,
                    kind="repo",
                    display_name=Path(path).name or path,
                    owner_scope="PC",
                    path=path,
                    health_status="ok",
                    activation_state="dirty" if int(row.get("dirty_count") or 0) else "clean",
                    evidence_status="observed",
                    source_probe="git worktree list",
                    as_of=fold_at,
                    branch=row.get("branch"),
                    head_commit=row.get("head_commit"),
                    dirty=int(row.get("dirty_count") or 0),
                    remote=row.get("remote"),
                    key_facts={
                        "branch": row.get("branch"),
                        "head": row.get("head_commit"),
                        "dirty": int(row.get("dirty_count") or 0),
                        "remote": row.get("remote"),
                    },
                )
            )
            add_edge(pc_id, node_id, "contains")
        elif kind == "worktree":
            has_worktree = True
            node_id = _node_path_id("worktree", path)
            repo_path = str(row.get("repo_path") or root_path)
            add_node(
                _payload(
                    node_id=node_id,
                    kind="worktree",
                    display_name=Path(path).name or path,
                    owner_scope="PC",
                    path=path,
                    state="detached" if row.get("detached") else (
                        "dirty" if int(row.get("dirty_count") or 0) else "clean"
                    ),
                    health_status="ok",
                    activation_state="dirty" if int(row.get("dirty_count") or 0) else "clean",
                    evidence_status="observed",
                    source_probe="git worktree list",
                    as_of=fold_at,
                    worktree_path=path,
                    repo_path=repo_path,
                    branch=row.get("branch"),
                    head_commit=row.get("head_commit"),
                    dirty=int(row.get("dirty_count") or 0),
                    detached=bool(row.get("detached")),
                    key_facts={
                        "branch": row.get("branch"),
                        "head": row.get("head_commit"),
                        "dirty": int(row.get("dirty_count") or 0),
                        "detached": bool(row.get("detached")),
                    },
                )
            )
            add_edge(pc_id, node_id, "contains")
            repo_node = repo_ids.get(repo_path) or _node_path_id("repo", repo_path)
            add_edge(node_id, repo_node, "worktree_of")
        elif kind == "nested_repo":
            node_id = _node_path_id("nested_repo", path)
            add_node(
                _payload(
                    node_id=node_id,
                    kind="nested_repo",
                    display_name=Path(path).name or path,
                    owner_scope="PC",
                    path=path,
                    health_status="ok",
                    activation_state="dirty" if int(row.get("dirty_count") or 0) else "clean",
                    evidence_status="observed",
                    source_probe="nested .git walk",
                    as_of=fold_at,
                    branch=row.get("branch"),
                    head_commit=row.get("head_commit"),
                    dirty=int(row.get("dirty_count") or 0),
                    remote=row.get("remote"),
                    key_facts={
                        "branch": row.get("branch"),
                        "head": row.get("head_commit"),
                        "dirty": int(row.get("dirty_count") or 0),
                        "remote": row.get("remote"),
                    },
                )
            )
            add_edge(pc_id, node_id, "contains")
            add_edge(node_id, _node_path_id("repo", str(root_path)), "nested_repo_of")

    root_repo_id = repo_ids.get(str(root_path)) or _node_path_id("repo", str(root_path))
    root_worktree_id = _node_path_id("worktree", str(root_path))
    if not has_worktree:
        repo_node = nodes.get(root_repo_id, {})
        add_node(
            _payload(
                node_id=root_worktree_id,
                kind="worktree",
                display_name=root_path.name or str(root_path),
                owner_scope="PC",
                path=str(root_path),
                state=str(repo_node.get("activation_state") or "observed"),
                health_status="ok",
                activation_state=str(repo_node.get("activation_state") or "clean"),
                evidence_status="observed",
                source_probe="scheduled crawl root fallback",
                as_of=fold_at,
                worktree_path=str(root_path),
                repo_path=str(root_path),
                branch=repo_node.get("branch"),
                head_commit=repo_node.get("head_commit"),
                dirty=int(repo_node.get("dirty") or 0),
                detached=False,
                key_facts={
                    "branch": repo_node.get("branch"),
                    "head": repo_node.get("head_commit"),
                    "dirty": int(repo_node.get("dirty") or 0),
                    "fallback": "root_worktree",
                },
            )
        )
        add_edge(pc_id, root_worktree_id, "contains")
        add_edge(root_worktree_id, root_repo_id, "worktree_of")

    root_instance_id = _node_path_id("openclaw_instance", str(root_path))
    add_node(
        _payload(
            node_id=root_instance_id,
            kind="openclaw_instance",
            display_name=root_path.name or str(root_path),
            owner_scope="PC",
            path=str(root_path),
            state="active",
            health_status="ok",
            activation_state="active",
            evidence_status="observed",
            source_probe="scheduled crawl root",
            as_of=fold_at,
            root_path=str(root_path),
            activity_status="active",
        )
    )
    add_edge(pc_id, root_instance_id, "contains")
    add_edge(root_instance_id, pc_id, "runs_on")
    if root_worktree_id in nodes:
        add_edge(root_worktree_id, root_instance_id, "has-state")

    service_ids: dict[str, str] = {}
    failed_services: list[str] = []
    for row in _inventory_rows(observed, "systemd_user_services"):
        unit = str(row.get("unit") or "")
        if not unit:
            continue
        health, activation = _service_health(row)
        if health == "failed":
            failed_services.append(unit)
        node_id = f"service:PC:{unit}"
        service_ids[unit] = node_id
        add_node(
            _payload(
                node_id=node_id,
                kind="service",
                display_name=unit,
                owner_scope="PC",
                health_status=health,
                activation_state=activation,
                evidence_status="observed",
                source_probe="systemctl --user list-units",
                as_of=fold_at,
                unit=unit,
                load=row.get("load"),
                active=row.get("active"),
                sub=row.get("sub"),
                description=row.get("description"),
                key_facts=dict(row),
            )
        )
        add_edge(node_id, pc_id, "runs_on")

    for row in _inventory_rows(observed, "systemd_user_timers"):
        unit = str(row.get("unit") or "")
        if not unit:
            continue
        node_id = f"timer:PC:{unit}"
        add_node(
            _payload(
                node_id=node_id,
                kind="timer",
                display_name=unit,
                owner_scope="PC",
                health_status="ok",
                activation_state="scheduled",
                evidence_status="observed",
                source_probe="systemctl --user list-timers",
                as_of=fold_at,
                unit=unit,
                key_facts=dict(row),
            )
        )
        add_edge(node_id, pc_id, "scheduled_on")

    for idx, row in enumerate(observed.get("user_crontab", {}).get("rows", []) if isinstance(observed.get("user_crontab"), Mapping) else []):
        line = str(row)
        node_id = _hash_id("cron:PC", f"{idx}:{line}")
        add_node(
            _payload(
                node_id=node_id,
                kind="cron",
                display_name=f"cron:{idx}",
                owner_scope="PC",
                health_status="ok",
                activation_state="scheduled",
                evidence_status="observed",
                source_probe="crontab -l",
                as_of=fold_at,
                key_facts={"line": line},
            )
        )
        add_edge(node_id, pc_id, "scheduled_on")

    for row in _inventory_rows(observed, "windows_tasks"):
        name = str(row.get("name") or row.get("TaskName") or "")
        if not name:
            continue
        node_id = f"windows_task:{_slug(name)}"
        add_node(
            _payload(
                node_id=node_id,
                kind="windows_task",
                display_name=name,
                owner_scope="PC",
                health_status="ok",
                activation_state=str(row.get("state") or row.get("Status") or "observed"),
                evidence_status="observed",
                source_probe="schtasks.exe",
                as_of=fold_at,
                key_facts=dict(row),
            )
        )
        add_edge(node_id, pc_id, "scheduled_on")

    for row in _inventory_rows(observed, "listening_ports"):
        local = str(row.get("local_address_port") or "")
        if not local:
            continue
        node_id = f"port:{local}"
        add_node(
            _payload(
                node_id=node_id,
                kind="port",
                display_name=local,
                owner_scope="PC",
                health_status="ok",
                activation_state="listening",
                evidence_status="observed",
                source_probe="ss -tlnp",
                as_of=fold_at,
                local_address_port=local,
                process=row.get("process"),
                key_facts=dict(row),
            )
        )
        add_edge(node_id, pc_id, "listens_on")

    for row in _inventory_rows(observed, "ollama_models"):
        name = str(row.get("name") or "")
        if not name:
            continue
        retired = bool(row.get("retired"))
        node_id = f"model:{name}"
        add_node(
            _payload(
                node_id=node_id,
                kind="ollama_model",
                display_name=name,
                owner_scope="PC",
                health_status="retired" if retired else "ok",
                activation_state="loaded" if row.get("loaded") else "idle",
                evidence_status="observed",
                source_probe="ollama list/ps",
                as_of=fold_at,
                key_facts=dict(row),
                model_name=name,
            )
        )
        add_edge(node_id, pc_id, "available_on")

    for row in _inventory_rows(observed, "sqlite_databases"):
        path = str(row.get("path") or "")
        if not path:
            continue
        role = _sqlite_role(row)
        node_id = _node_path_id("sqlite_db", path)
        add_node(
            _payload(
                node_id=node_id,
                kind="sqlite_db",
                display_name=Path(path).name,
                owner_scope="PC",
                path=path,
                health_status="ok" if role != "empty" else "unknown",
                activation_state=role,
                evidence_status="observed",
                source_probe="sqlite file walk",
                as_of=fold_at,
                role=role,
                size_bytes=row.get("size_bytes"),
                relative_path=row.get("relative_path"),
                key_facts={**dict(row), "role": role},
            )
        )
        add_edge(node_id, pc_id, "stored_on")

    sidecars = (
        ("hermes", root_path / "sidecars" / "hermes", "running"),
        ("gbrain", root_path / "sidecars" / "gbrain_upstream", "installed_not_running"),
        ("niles_home", root_path / "sidecars" / "niles_home", "defunct"),
    )
    for name, path, state in sidecars:
        exists = path.exists()
        node_id = f"sidecar:{name}"
        add_node(
            _payload(
                node_id=node_id,
                kind="sidecar",
                display_name=name,
                owner_scope="PC",
                path=str(path),
                state=state,
                health_status="ok" if exists and state != "defunct" else "unknown",
                activation_state=state,
                evidence_status="observed" if exists else "declared",
                source_probe="sidecars path inventory",
                as_of=fold_at,
                key_facts={"exists": exists, "state": state},
            )
        )
        add_edge(node_id, pc_id, "installed_on")

    for agent in AGENTS:
        name = str(agent["name"])
        node_id = f"agent:{name}"
        service = str(agent.get("service") or "")
        add_node(
            _payload(
                node_id=node_id,
                kind="agent",
                display_name=name,
                owner_scope="PC",
                health_status="ok",
                activation_state="running" if service else "gate",
                evidence_status="observed",
                source_probe="static fleet roster + sysknow ledger contract",
                as_of=fold_at,
                key_facts=dict(agent),
                **agent,
            )
        )
        add_edge(node_id, pc_id, "runs_on")
        if service:
            add_edge(node_id, service_ids.get(service, f"service:PC:{service}"), "served_by")
        model = str(agent.get("model") or "")
        if model and f"model:{model}" in nodes:
            add_edge(node_id, f"model:{model}", "uses_model")

    failed_count = len(failed_services)
    health_id = "health_rollup:PC"
    add_node(
        _payload(
            node_id=health_id,
            kind="health_rollup",
            display_name="PC health rollup",
            owner_scope="PC",
            health_status="failed" if failed_count else "ok",
            activation_state=f"{failed_count}_red" if failed_count else "green",
            evidence_status="observed",
            source_probe="graph health aggregation",
            as_of=fold_at,
            key_facts={"failed_services": failed_services, "degraded": _degraded(observed)},
            failed_services=failed_services,
            degraded=_degraded(observed),
        )
    )
    add_edge(health_id, pc_id, "summarizes")
    for unit in failed_services:
        add_edge(health_id, service_ids.get(unit, f"service:PC:{unit}"), "flags")

    node_rows = [_row(nodes[node_id], fold_at=fold_at) for node_id in sorted(nodes)]
    return {
        "table": GRAPH_NODE_TABLE,
        "edge_table": GRAPH_EDGE_TABLE,
        "fold_source": FOLD_SOURCE,
        "fold_at": fold_at,
        "root": str(root_path),
        "ledger_path": str(Path(ledger_path)),
        "node_count": len(node_rows),
        "edge_count": len(edges),
        "nodes": node_rows,
        "edges": sorted(edges, key=lambda edge: (edge["source_node_id"], edge["target_node_id"], edge["relation"])),
        "degraded": _degraded(observed),
    }


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        f'CREATE TABLE IF NOT EXISTS "{GRAPH_NODE_TABLE}" ('
        "node_id TEXT PRIMARY KEY, kind TEXT NOT NULL, owner_scope TEXT NOT NULL, "
        "health_status TEXT, activation_state TEXT, last_seen_at TEXT, last_verified_at TEXT, "
        "payload_json TEXT NOT NULL, _fold_source TEXT NOT NULL, _fold_at TEXT NOT NULL)"
    )
    conn.execute(
        f'CREATE TABLE IF NOT EXISTS "{GRAPH_EDGE_TABLE}" ('
        "source_node_id TEXT NOT NULL, target_node_id TEXT NOT NULL, relation TEXT NOT NULL, "
        "owner_scope TEXT NOT NULL, _fold_source TEXT NOT NULL, _fold_at TEXT NOT NULL)"
    )


def write_graph_to_ledger(
    root: str | Path,
    ledger_path: str | Path,
    *,
    confirm: bool = False,
    inventory: Mapping[str, Any] | None = None,
    now: str | None = None,
    backup_path: str | Path | None = None,
) -> dict[str, Any]:
    """Dry-run by default; with confirm=True, fold graph rows into the ledger."""

    plan = build_graph_write_plan(root, ledger_path, inventory=inventory, now=now)
    if not confirm:
        return {"status": "dry_run", "plan": plan}

    ledger = Path(ledger_path)
    if not ledger.exists():
        return {"status": "ledger_unavailable", "plan": plan}

    try:
        backup_path = ensure_ledger_backup(ledger, backup_path)
    except (OSError, RuntimeError) as exc:
        return {"status": "backup_verification_failed", "reason": str(exc), "plan": plan}

    with sqlite3.connect(ledger) as conn:
        _ensure_schema(conn)
        conn.execute(f'DELETE FROM "{GRAPH_NODE_TABLE}" WHERE "_fold_source" = ?', (FOLD_SOURCE,))
        conn.execute(f'DELETE FROM "{GRAPH_EDGE_TABLE}" WHERE "_fold_source" = ?', (FOLD_SOURCE,))
        for row in plan["nodes"]:
            conn.execute(
                f'INSERT INTO "{GRAPH_NODE_TABLE}" '
                "(node_id, kind, owner_scope, health_status, activation_state, last_seen_at, "
                "last_verified_at, payload_json, _fold_source, _fold_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["node_id"],
                    row["kind"],
                    row["owner_scope"],
                    row["health_status"],
                    row["activation_state"],
                    row["last_seen_at"],
                    row["last_verified_at"],
                    row["payload_json"],
                    row["_fold_source"],
                    row["_fold_at"],
                ),
            )
        for edge in plan["edges"]:
            conn.execute(
                f'INSERT INTO "{GRAPH_EDGE_TABLE}" '
                "(source_node_id, target_node_id, relation, owner_scope, _fold_source, _fold_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    edge["source_node_id"],
                    edge["target_node_id"],
                    edge["relation"],
                    edge["owner_scope"],
                    edge["_fold_source"],
                    edge["_fold_at"],
                ),
            )
        conn.commit()

    return {
        "status": "written",
        "backup_path": str(backup_path),
        "table": GRAPH_NODE_TABLE,
        "edge_table": GRAPH_EDGE_TABLE,
        "node_count": plan["node_count"],
        "edge_count": plan["edge_count"],
        "fold_source": FOLD_SOURCE,
        "degraded": plan["degraded"],
    }


__all__ = [
    "GRAPH_NODE_TABLE",
    "GRAPH_EDGE_TABLE",
    "FOLD_SOURCE",
    "build_graph_write_plan",
    "collect_system_inventory",
    "write_graph_to_ledger",
]
