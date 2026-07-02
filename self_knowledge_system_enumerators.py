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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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


def enumerate_system_state(*, timeout: int = DEFAULT_TIMEOUT_SECONDS, repo_root: str | Path = ".") -> dict[str, Any]:
    """Convenience aggregator: run every enumerator and collect the results.

    Each key fails independently — one enumerator being unavailable never
    prevents the others from reporting.
    """
    return {
        "processes": enumerate_processes(timeout=timeout),
        "user_crontab": enumerate_user_crontab(timeout=timeout),
        "systemd_user_services": enumerate_systemd_user_services(timeout=timeout),
        "listening_ports": enumerate_listening_ports(timeout=timeout),
        "sqlite_databases": enumerate_sqlite_databases(repo_root),
    }


__all__ = [
    "enumerate_processes",
    "enumerate_user_crontab",
    "enumerate_systemd_user_services",
    "enumerate_listening_ports",
    "enumerate_sqlite_databases",
    "enumerate_system_state",
]
