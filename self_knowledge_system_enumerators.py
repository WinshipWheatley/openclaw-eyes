"""Read-only system enumerators for the perpetual self-knowledge engine.

Each enumerator is independently try/except-guarded and returns either
``{"status": "ok", "rows": [...]}`` or an honest
``{"status": "unavailable", "reason": "..."}`` — never a false green. Rows are
plain dicts/strings suitable for future ledger folding (see
`self_knowledge_ledger_gap_writer.py` for the fold-and-backup pattern these
would eventually feed).

Nothing here mutates system state: every enumerator either shells out to a
read-only inspection command (ps / crontab -l / systemctl --user list-units /
ss -tlnp) or walks the filesystem read-only looking for on-disk sqlite files.
"""

from __future__ import annotations

import os
import subprocess
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

DEFAULT_TIMEOUT_SECONDS = 10

_DB_EXCLUDED_NAMES = {
    ".git",
    ".openclaw",
    ".chief.env",
    ".google-secrets",
    "LegalPrivate",
    "FinancePrivate",
    "MusicLawPrivate",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "chief_env",
    ".venv",
    "node_modules",
}
# Deliberately does NOT exclude "generated" — the task explicitly wants
# on-disk databases under generated/ included, unlike the base crumb crawler.
_DB_EXCLUDED_PARTS = {"worktrees", "sidecars"}
_DB_SUFFIXES = (".sqlite", ".sqlite3", ".db")
_GIT_SCAN_EXCLUDED_PARTS = {
    ".git",
    ".openclaw",
    ".chief.env",
    ".google-secrets",
    "LegalPrivate",
    "FinancePrivate",
    "MusicLawPrivate",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "chief_env",
    ".venv",
    "node_modules",
}


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _is_db_excluded(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    parts = set(rel.parts)
    if path.name in _DB_EXCLUDED_NAMES:
        return True
    if parts & _DB_EXCLUDED_NAMES:
        return True
    if parts & _DB_EXCLUDED_PARTS:
        return True
    return False


def _run(cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _roots(roots: Iterable[str | Path] | str | Path | None, fallback: str | Path) -> tuple[Path, ...]:
    if roots is None:
        values: Iterable[str | Path] = (fallback,)
    elif isinstance(roots, (str, Path)):
        values = (roots,)
    else:
        values = roots
    resolved: list[Path] = []
    for value in values:
        try:
            path = Path(value).resolve()
        except OSError:
            continue
        if path.exists() and path not in resolved:
            resolved.append(path)
    return tuple(resolved)


def _is_git_scan_excluded(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    parts = set(rel.parts)
    if path.name in _GIT_SCAN_EXCLUDED_PARTS:
        return True
    if parts & _GIT_SCAN_EXCLUDED_PARTS:
        return True
    return False


def _git_output(repo: str | Path, args: list[str], *, timeout: int) -> str | None:
    try:
        proc = _run(["git", "-C", str(repo), *args], timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return str(proc.stdout or "").strip()


def _git_branch(repo: str | Path, *, timeout: int) -> str | None:
    branch = _git_output(repo, ["rev-parse", "--abbrev-ref", "HEAD"], timeout=timeout)
    if not branch:
        return None
    return None if branch == "HEAD" else branch


def _git_head(repo: str | Path, *, timeout: int) -> str | None:
    return _git_output(repo, ["rev-parse", "HEAD"], timeout=timeout)


def _git_dirty(repo: str | Path, *, timeout: int) -> bool | None:
    status = _git_output(repo, ["status", "--porcelain"], timeout=timeout)
    if status is None:
        return None
    return bool(status.strip())


def _git_toplevel(repo: str | Path, *, timeout: int) -> str:
    top = _git_output(repo, ["rev-parse", "--show-toplevel"], timeout=timeout)
    try:
        return str(Path(top or repo).resolve())
    except OSError:
        return str(repo)


def _git_row(path: Path, *, owner_scope: str, timeout: int, now_iso: str) -> dict[str, Any]:
    dirty = _git_dirty(path, timeout=timeout)
    return {
        "node_id": f"repo:{path.resolve()}",
        "kind": "git_repo",
        "owner_scope": owner_scope,
        "path": str(path.resolve()),
        "branch": _git_branch(path, timeout=timeout),
        "head_commit": _git_head(path, timeout=timeout),
        "dirty": bool(dirty),
        "dirty_status": "unknown" if dirty is None else ("dirty" if dirty else "clean"),
        "last_seen_at": now_iso,
        "last_verified_at": now_iso,
    }


def enumerate_processes(*, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Enumerate running processes via `ps`."""
    try:
        proc = _run(["ps", "-eo", "pid,ppid,user,comm,args", "--no-headers"], timeout=timeout)
    except FileNotFoundError as exc:
        return {"status": "unavailable", "reason": f"ps_not_found:{exc}"}
    except subprocess.TimeoutExpired as exc:
        return {"status": "unavailable", "reason": f"timeout:{exc}"}
    except OSError as exc:
        return {"status": "unavailable", "reason": f"os_error:{exc}"}

    if proc.returncode != 0:
        return {"status": "unavailable", "reason": f"ps_exit_{proc.returncode}:{proc.stderr.strip()}"}

    rows: list[dict[str, str]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or line.upper().startswith("PID "):
            continue
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        pid, ppid, user, comm, args = parts
        rows.append({"pid": pid, "ppid": ppid, "user": user, "comm": comm, "args": args})
    return {"status": "ok", "rows": rows}


def enumerate_user_crontab(*, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Enumerate the current user's crontab entries via `crontab -l`."""
    try:
        proc = _run(["crontab", "-l"], timeout=timeout)
    except FileNotFoundError as exc:
        return {"status": "unavailable", "reason": f"crontab_not_found:{exc}"}
    except subprocess.TimeoutExpired as exc:
        return {"status": "unavailable", "reason": f"timeout:{exc}"}
    except OSError as exc:
        return {"status": "unavailable", "reason": f"os_error:{exc}"}

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        if "no crontab" in stderr.lower():
            return {"status": "ok", "rows": []}
        return {"status": "unavailable", "reason": f"crontab_exit_{proc.returncode}:{stderr}"}

    rows = [
        line.strip()
        for line in proc.stdout.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return {"status": "ok", "rows": rows}


def enumerate_systemd_user_services(*, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Enumerate systemd --user services via `systemctl --user list-units`."""
    try:
        proc = _run(
            ["systemctl", "--user", "list-units", "--type=service", "--no-legend", "--plain"],
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return {"status": "unavailable", "reason": f"systemctl_not_found:{exc}"}
    except subprocess.TimeoutExpired as exc:
        return {"status": "unavailable", "reason": f"timeout:{exc}"}
    except OSError as exc:
        return {"status": "unavailable", "reason": f"os_error:{exc}"}

    if proc.returncode != 0:
        return {
            "status": "unavailable",
            "reason": f"systemctl_exit_{proc.returncode}:{(proc.stderr or '').strip()}",
        }

    rows: list[dict[str, str]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        unit, load, active, sub = parts[0], parts[1], parts[2], parts[3]
        description = parts[4] if len(parts) > 4 else ""
        rows.append(
            {
                "unit": unit,
                "load": load,
                "active": active,
                "sub": sub,
                "description": description,
            }
        )
    return {"status": "ok", "rows": rows}


def enumerate_listening_ports(*, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Enumerate listening TCP ports via `ss -tlnp`."""
    try:
        proc = _run(["ss", "-tlnp"], timeout=timeout)
    except FileNotFoundError as exc:
        return {"status": "unavailable", "reason": f"ss_not_found:{exc}"}
    except subprocess.TimeoutExpired as exc:
        return {"status": "unavailable", "reason": f"timeout:{exc}"}
    except OSError as exc:
        return {"status": "unavailable", "reason": f"os_error:{exc}"}

    if proc.returncode != 0:
        return {"status": "unavailable", "reason": f"ss_exit_{proc.returncode}:{(proc.stderr or '').strip()}"}

    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if lines and lines[0].strip().split(None, 1)[0].lower() in {"netid", "state"}:
        lines = lines[1:]  # drop the header row

    # `ss -tlnp` columns (no Netid by default): State Recv-Q Send-Q
    # "Local Address:Port" "Peer Address:Port" [Process]. Process, when
    # present, is a single whitespace-free token (e.g. users:(("x",pid=1,...))).
    rows: list[dict[str, str]] = []
    for line in lines:
        parts = line.split(None, 5)
        if len(parts) < 5:
            continue
        state, recv_q, send_q, local, peer = parts[:5]
        process = parts[5] if len(parts) > 5 else ""
        rows.append(
            {
                "state": state,
                "recv_q": recv_q,
                "send_q": send_q,
                "local_address_port": local,
                "peer_address_port": peer,
                "process": process,
            }
        )
    return {"status": "ok", "rows": rows}


def enumerate_sqlite_databases(
    root: str | Path,
    *,
    max_results: int = 500,
) -> dict[str, Any]:
    """Bounded read-only glob for on-disk sqlite databases under `root`
    (including `generated/`, unlike the base crumb crawler's default
    exclusions — this enumerator exists specifically to find them)."""
    try:
        root_path = Path(root).resolve()
        if not root_path.exists():
            return {"status": "unavailable", "reason": f"root_not_found:{root_path}"}

        rows: list[dict[str, Any]] = []
        for dirpath, dirnames, filenames in os.walk(root_path):
            current_dir = Path(dirpath)
            dirnames[:] = [
                name
                for name in sorted(dirnames)
                if not _is_db_excluded(current_dir / name, root_path)
            ]
            for name in sorted(filenames):
                if not name.endswith(_DB_SUFFIXES):
                    continue
                path = current_dir / name
                if _is_db_excluded(path, root_path):
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                rows.append(
                    {
                        "path": str(path),
                        "relative_path": path.relative_to(root_path).as_posix(),
                        "size_bytes": stat.st_size,
                        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                    }
                )
                if len(rows) >= max(0, int(max_results)):
                    return {"status": "ok", "rows": rows}
        return {"status": "ok", "rows": rows}
    except OSError as exc:
        return {"status": "unavailable", "reason": f"os_error:{exc}"}


def enumerate_git_repos(
    roots: Iterable[str | Path] | str | Path,
    *,
    owner_scope: str = "pc",
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_results: int = 1000,
) -> dict[str, Any]:
    """Find git repositories and worktrees under the supplied OpenClaw roots."""

    now_iso = _utc_now_iso()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        for root_path in _roots(roots, "."):
            for dirpath, dirnames, _filenames in os.walk(root_path):
                current_dir = Path(dirpath)
                dirnames[:] = [
                    name
                    for name in sorted(dirnames)
                    if not _is_git_scan_excluded(current_dir / name, root_path)
                ]
                git_marker = current_dir / ".git"
                if not git_marker.exists():
                    continue
                repo_path = Path(_git_toplevel(current_dir, timeout=timeout)).resolve()
                key = str(repo_path)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(_git_row(repo_path, owner_scope=owner_scope, timeout=timeout, now_iso=now_iso))
                if len(rows) >= max(0, int(max_results)):
                    return {"status": "ok", "rows": rows}
        return {"status": "ok", "rows": rows}
    except OSError as exc:
        return {"status": "unavailable", "reason": f"os_error:{exc}", "rows": rows}


def _parse_worktree_porcelain(stdout: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in str(stdout or "").splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                items.append(current)
                current = {}
            continue
        if line.startswith("worktree "):
            if current:
                items.append(current)
            current = {"worktree_path": line.split(" ", 1)[1]}
        elif line.startswith("HEAD "):
            current["head_commit"] = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            branch = line.split(" ", 1)[1]
            current["branch"] = branch.removeprefix("refs/heads/")
        elif line == "detached":
            current["branch"] = None  # type: ignore[assignment]
        elif line == "bare":
            current["bare"] = "true"
    if current:
        items.append(current)
    return items


def enumerate_worktrees(
    repos: Iterable[str | Path] | str | Path,
    *,
    owner_scope: str = "pc",
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run `git worktree list --porcelain` for each repo and return rows."""

    now_iso = _utc_now_iso()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for repo in _roots(repos, "."):
        output = _git_output(repo, ["worktree", "list", "--porcelain"], timeout=timeout)
        if output is None:
            continue
        controller_repo = str(repo.resolve())
        for item in _parse_worktree_porcelain(output):
            raw_path = item.get("worktree_path")
            if not raw_path:
                continue
            worktree_path = Path(raw_path).resolve()
            key = str(worktree_path)
            if key in seen:
                continue
            seen.add(key)
            dirty = _git_dirty(worktree_path, timeout=timeout)
            rows.append(
                {
                    "node_id": f"worktree:{worktree_path}",
                    "kind": "git_worktree",
                    "owner_scope": owner_scope,
                    "repo_path": controller_repo,
                    "worktree_path": key,
                    "branch": item.get("branch"),
                    "head_commit": item.get("head_commit") or _git_head(worktree_path, timeout=timeout),
                    "dirty": bool(dirty),
                    "dirty_status": "unknown" if dirty is None else ("dirty" if dirty else "clean"),
                    "last_seen_at": now_iso,
                    "last_verified_at": now_iso,
                }
            )
    return {"status": "ok", "rows": rows}


def enumerate_openclaw_states(
    roots: Iterable[str | Path] | str | Path,
    *,
    owner_scope: str = "pc",
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    active_paths: Iterable[str | Path] | None = None,
) -> dict[str, Any]:
    """Report OpenClaw instance state for supplied root/worktree paths."""

    now_iso = _utc_now_iso()
    active = {str(Path(path).resolve()) for path in (active_paths or ())}
    rows: list[dict[str, Any]] = []
    for root in _roots(roots, "."):
        dirty = _git_dirty(root, timeout=timeout)
        health = "unknown" if dirty is None else ("dirty" if dirty else "clean")
        root_path = str(root.resolve())
        rows.append(
            {
                "node_id": f"openclaw_instance:{root_path}",
                "kind": "openclaw_instance",
                "owner_scope": owner_scope,
                "root_path": root_path,
                "branch": _git_branch(root, timeout=timeout),
                "head_commit": _git_head(root, timeout=timeout),
                "dirty": bool(dirty),
                "health_status": health,
                "activity_status": "active" if root_path in active else "idle",
                "last_seen_at": now_iso,
                "last_verified_at": now_iso,
            }
        )
    return {"status": "ok", "rows": rows}


def _add_node(nodes: dict[str, dict[str, Any]], node_id: str, kind: str, **fields: Any) -> None:
    existing = nodes.get(node_id, {})
    merged = {"id": node_id, "kind": kind}
    merged.update(existing)
    merged.update({key: value for key, value in fields.items() if value is not None})
    nodes[node_id] = merged


def _add_edge(edges: list[dict[str, str]], source: str, target: str, relation: str) -> None:
    edge = {"source": source, "target": target, "relation": relation}
    if edge not in edges:
        edges.append(edge)


def build_system_inventory_graph(system_state: Mapping[str, Any], *, owner_scope: str = "pc") -> dict[str, Any]:
    """Build connected metadata graph nodes and edges from enumerator output."""

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []
    machine_id = f"machine:{owner_scope}"
    _add_node(nodes, machine_id, "machine", owner_scope=owner_scope)

    for row in (system_state.get("git_repos") or {}).get("rows", ()):
        if not isinstance(row, Mapping):
            continue
        repo_path = str(row.get("path") or "")
        if not repo_path:
            continue
        repo_id = f"repo:{repo_path}"
        fields = dict(row)
        fields.pop("kind", None)
        fields.pop("node_id", None)
        _add_node(nodes, repo_id, "repo", **fields)
        _add_edge(edges, machine_id, repo_id, "contains")
        _add_edge(edges, repo_id, machine_id, "runs-on")

    for row in (system_state.get("worktrees") or {}).get("rows", ()):
        if not isinstance(row, Mapping):
            continue
        worktree_path = str(row.get("worktree_path") or "")
        repo_path = str(row.get("repo_path") or "")
        if not worktree_path:
            continue
        worktree_id = f"worktree:{worktree_path}"
        repo_id = f"repo:{repo_path}" if repo_path else ""
        fields = dict(row)
        fields.pop("kind", None)
        fields.pop("node_id", None)
        _add_node(nodes, worktree_id, "worktree", **fields)
        _add_edge(edges, machine_id, worktree_id, "contains")
        if repo_id:
            _add_edge(edges, repo_id, worktree_id, "contains")
            _add_edge(edges, worktree_id, repo_id, "branch-of")

    for row in (system_state.get("openclaw_states") or {}).get("rows", ()):
        if not isinstance(row, Mapping):
            continue
        root_path = str(row.get("root_path") or "")
        if not root_path:
            continue
        instance_id = f"openclaw_instance:{root_path}"
        fields = dict(row)
        fields.pop("kind", None)
        fields.pop("node_id", None)
        _add_node(nodes, instance_id, "openclaw_instance", **fields)
        _add_edge(edges, machine_id, instance_id, "contains")
        _add_edge(edges, instance_id, machine_id, "runs-on")
        worktree_id = f"worktree:{root_path}"
        if worktree_id in nodes:
            _add_edge(edges, worktree_id, instance_id, "has-state")
        repo_id = f"repo:{root_path}"
        if repo_id in nodes:
            _add_edge(edges, instance_id, repo_id, "state-of")

    for row in (system_state.get("systemd_user_services") or {}).get("rows", ()):
        if not isinstance(row, Mapping):
            continue
        unit = str(row.get("unit") or "")
        if not unit:
            continue
        service_id = f"service:{owner_scope}:{unit}"
        _add_node(nodes, service_id, "service", owner_scope=owner_scope, activation_state=row.get("active"), **dict(row))
        _add_edge(edges, machine_id, service_id, "runs")
        for instance_id, node in nodes.items():
            if node.get("kind") == "openclaw_instance":
                _add_edge(edges, instance_id, service_id, "depends-on")

    return {
        "schema_version": "self_knowledge_inventory_graph_v1",
        "owner_scope": owner_scope,
        "nodes": nodes,
        "edges": edges,
    }


def _neighbor_ids(graph: Mapping[str, Any], node_id: str) -> set[str]:
    neighbors: set[str] = set()
    for edge in graph.get("edges", ()):
        if edge.get("source") == node_id:
            neighbors.add(str(edge.get("target")))
        if edge.get("target") == node_id:
            neighbors.add(str(edge.get("source")))
    neighbors.discard("")
    return neighbors


def reachable_node_ids(graph: Mapping[str, Any], start_node_id: str) -> set[str]:
    """Return all nodes reachable by walking graph edges as an undirected graph."""

    nodes = graph.get("nodes", {})
    if start_node_id not in nodes:
        return set()
    seen = {start_node_id}
    queue: deque[str] = deque([start_node_id])
    while queue:
        current = queue.popleft()
        for neighbor in _neighbor_ids(graph, current):
            if neighbor in nodes and neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return seen


def query_system_inventory(
    graph: Mapping[str, Any],
    *,
    resolution: str,
    owner_scope: str | None = None,
    node_id: str | None = None,
) -> dict[str, Any]:
    """Answer high/medium/deep self-knowledge inventory queries."""

    nodes: Mapping[str, Mapping[str, Any]] = graph.get("nodes", {})
    edges = graph.get("edges", ())
    resolution_key = str(resolution or "").lower()
    if resolution_key == "high":
        return {
            "resolution": "high",
            "machine_count": sum(1 for node in nodes.values() if node.get("kind") == "machine"),
            "repo_count": sum(1 for node in nodes.values() if node.get("kind") == "repo"),
            "worktree_count": sum(1 for node in nodes.values() if node.get("kind") == "worktree"),
            "openclaw_instance_count": sum(1 for node in nodes.values() if node.get("kind") == "openclaw_instance"),
            "service_count": sum(1 for node in nodes.values() if node.get("kind") == "service"),
            "edge_count": len(tuple(edges)),
        }
    if resolution_key == "medium":
        machines: dict[str, dict[str, list[str]]] = {}
        for node in nodes.values():
            machine_scope = str(node.get("owner_scope") or owner_scope or graph.get("owner_scope") or "pc")
            if owner_scope is not None and machine_scope != owner_scope:
                continue
            machines.setdefault(machine_scope, {"repos": [], "worktrees": [], "services": [], "openclaw_instances": []})
            kind = node.get("kind")
            if kind == "repo" and node.get("path"):
                machines[machine_scope]["repos"].append(str(node["path"]))
            elif kind == "worktree" and node.get("worktree_path"):
                machines[machine_scope]["worktrees"].append(str(node["worktree_path"]))
            elif kind == "service" and node.get("unit"):
                machines[machine_scope]["services"].append(str(node["unit"]))
            elif kind == "openclaw_instance" and node.get("root_path"):
                machines[machine_scope]["openclaw_instances"].append(str(node["root_path"]))
        for machine in machines.values():
            for key in machine:
                machine[key] = sorted(set(machine[key]))
        return {"resolution": "medium", "machines": machines}
    if resolution_key == "deep":
        if not node_id or node_id not in nodes:
            return {"resolution": "deep", "node": None, "neighbors": [], "edges": []}
        neighbor_ids = _neighbor_ids(graph, node_id)
        incident_edges = [
            dict(edge)
            for edge in edges
            if edge.get("source") == node_id or edge.get("target") == node_id
        ]
        return {
            "resolution": "deep",
            "node": dict(nodes[node_id]),
            "neighbors": [dict(nodes[nid]) for nid in sorted(neighbor_ids) if nid in nodes],
            "edges": incident_edges,
        }
    raise ValueError(f"unknown resolution: {resolution!r}")


def enumerate_system_state(
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    repo_root: str | Path = ".",
    roots: Iterable[str | Path] | str | Path | None = None,
    owner_scope: str = "pc",
) -> dict[str, Any]:
    """Convenience aggregator: run every enumerator and collect the results.

    Each key fails independently — one enumerator being unavailable never
    prevents the others from reporting.
    """
    scan_roots = _roots(roots, repo_root)
    git_repos = enumerate_git_repos(scan_roots, owner_scope=owner_scope, timeout=timeout)
    worktrees = enumerate_worktrees(
        tuple(row["path"] for row in git_repos.get("rows", ()) if row.get("path")),
        owner_scope=owner_scope,
        timeout=timeout,
    )
    openclaw_roots = tuple(
        row["worktree_path"] for row in worktrees.get("rows", ()) if row.get("worktree_path")
    ) or scan_roots
    state = {
        "processes": enumerate_processes(timeout=timeout),
        "user_crontab": enumerate_user_crontab(timeout=timeout),
        "systemd_user_services": enumerate_systemd_user_services(timeout=timeout),
        "listening_ports": enumerate_listening_ports(timeout=timeout),
        "sqlite_databases": enumerate_sqlite_databases(repo_root),
        "git_repos": git_repos,
        "worktrees": worktrees,
        "openclaw_states": enumerate_openclaw_states(openclaw_roots, owner_scope=owner_scope, timeout=timeout),
    }
    state["inventory_graph"] = build_system_inventory_graph(state, owner_scope=owner_scope)
    return state


__all__ = [
    "build_system_inventory_graph",
    "enumerate_git_repos",
    "enumerate_openclaw_states",
    "enumerate_processes",
    "enumerate_user_crontab",
    "enumerate_systemd_user_services",
    "enumerate_listening_ports",
    "enumerate_sqlite_databases",
    "enumerate_system_state",
    "enumerate_worktrees",
    "query_system_inventory",
    "reachable_node_ids",
]
