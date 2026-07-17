"""One-way capability/register/runtime mirror into the business-ops ledger.

The reconciler is metadata-only. It cannot activate services, mutate the
Activation Gate Register, grant authority, send externally, move money, or
delete anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import business_ops_ledger


SCHEMA_VERSION = "capability_ledger_reconciler_v1"
DEFAULT_REGISTER_PATH = Path("workspaces/openclaw_program/activation_gate_register.json")
DEFAULT_LEDGER_PATH = Path(".openclaw/business_ops/ledger.sqlite")
DEFAULT_MAC_REPORT_PATH = Path(
    "/mnt/e/openclaw/codex_mac_bridge/from-codex-mac-desktop/"
    "MACSOL-CENSUS-MAC-RESULT-20260717.md"
)
DEFAULT_RECEIPT_PATH = Path("generated/system_knowledge/capability_ledger_reconciler_receipt.json")
DEFAULT_ATTENTION_PATH = Path("generated/read_models/capability_ledger_drift_attention.json")
RUNTIME_STATES = ("running", "dark", "not_applicable", "unknown")
DRIFT_CODES = (
    "REGISTERED_CODE_MISSING",
    "REGISTERED_RUNTIME_DARK",
    "RUNTIME_UNREGISTERED",
    "LEDGER_STALE",
    "MACHINE_INVENTORY_STALE",
)
FILE_INVENTORY_MAX_AGE_SECONDS = 24 * 60 * 60
MACHINE_INVENTORY_MAX_AGE_SECONDS = 24 * 60 * 60
_UNIT_RE = re.compile(r"\b([A-Za-z0-9@_.-]+\.(?:service|timer))\b")
_MAC_LABEL_RE = re.compile(r"\b(com\.openclaw\.[A-Za-z0-9_.-]+)")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _parse_time(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_stale(value: str | None, now: str, max_age_seconds: int) -> bool:
    observed = _parse_time(value)
    current = _parse_time(now)
    if observed is None or current is None:
        return True
    return (current - observed).total_seconds() > max_age_seconds


def _bool_int(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def ensure_capability_ledger_schema(conn: sqlite3.Connection) -> None:
    """Create the additive current mirror and append-only batch receipt table."""

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS capability_activations (
            capability_id TEXT NOT NULL,
            machine TEXT NOT NULL CHECK(machine IN ('pc','mac')),
            display_name TEXT NOT NULL,
            artifact_present INTEGER CHECK(artifact_present IN (0,1) OR artifact_present IS NULL),
            configured INTEGER CHECK(configured IN (0,1) OR configured IS NULL),
            runtime_confirmed INTEGER CHECK(runtime_confirmed IN (0,1) OR runtime_confirmed IS NULL),
            authority_granted INTEGER CHECK(authority_granted IN (0,1) OR authority_granted IS NULL),
            owner TEXT NOT NULL,
            last_seen TEXT,
            observed_at TEXT NOT NULL,
            register_stage TEXT NOT NULL,
            runtime_state TEXT NOT NULL CHECK(runtime_state IN ('running','dark','not_applicable','unknown')),
            machine_applicability TEXT NOT NULL,
            observed_decision TEXT,
            evidence_refs_json TEXT NOT NULL,
            health_json TEXT NOT NULL DEFAULT '{}',
            drift_codes_json TEXT NOT NULL,
            drift_flag INTEGER NOT NULL CHECK(drift_flag IN (0,1)),
            state_fingerprint TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            batch_id TEXT NOT NULL,
            PRIMARY KEY (capability_id, machine)
        );
        CREATE INDEX IF NOT EXISTS idx_capability_activations_runtime
          ON capability_activations(machine, runtime_state, drift_flag);
        CREATE TABLE IF NOT EXISTS capability_reconciliation_runs (
            batch_id TEXT PRIMARY KEY,
            observed_at TEXT NOT NULL,
            source_fingerprint TEXT NOT NULL,
            activation_count INTEGER NOT NULL,
            changed_count INTEGER NOT NULL,
            decision_count INTEGER NOT NULL,
            drift_count INTEGER NOT NULL,
            status TEXT NOT NULL,
            receipt_json TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        );
        """
    )


def _markdown_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _plain_markdown(value: str) -> str:
    return " ".join(value.replace("`", "").replace("**", "").split())


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return text[:48] or "observed-capability"


def _mac_snapshot(text: str, fallback: str) -> str:
    match = re.search(
        r"Snapshot:\*\*\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+(EDT|EST|UTC)",
        text,
    )
    if not match:
        return fallback
    offset = {"EDT": "-04:00", "EST": "-05:00", "UTC": "+00:00"}[match.group(3)]
    return f"{match.group(1)}T{match.group(2)}:00{offset}"


def _mac_table_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    section = ""
    headers: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("### "):
            section = _plain_markdown(line[4:])
            headers = []
            continue
        if not line.startswith("|") or not section[:1] in {"A", "B", "C"}:
            continue
        cells = _markdown_cells(line)
        if cells and all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if not headers:
            headers = cells
            continue
        if len(cells) != len(headers):
            continue
        row = dict(zip(headers, cells))
        row["_section"] = section
        rows.append(row)
    return rows


def _mac_decision(verdict: str) -> str:
    folded = verdict.casefold()
    if "archive" in folded:
        return "ARCHIVE"
    if "fix before" in folded and "activate" in folded:
        return "FIX_BEFORE_ACTIVATE"
    if "wire-in" in folded or "wire in" in folded:
        return "WIRE_IN"
    if "activate" in folded:
        return "ACTIVATE"
    return "REVIEW"


def _mac_row_from_table(row: Mapping[str, str], *, snapshot: str) -> dict[str, Any]:
    source = _plain_markdown(
        row.get("Exact path / activation")
        or row.get("Exact path / capability")
        or row.get("Exact path")
        or ""
    )
    capability = _plain_markdown(row.get("Capability") or "")
    ground = _plain_markdown(row.get("Ground truth") or row.get("Local branch / base; behind/ahead; merge state") or "")
    state = _plain_markdown(row.get("State") or "").upper()
    grade = _plain_markdown(row.get("Grade") or "")
    verdict = _plain_markdown(row.get("Verdict") or "")
    label_match = _MAC_LABEL_RE.search(source)
    if label_match:
        display = label_match.group(1).removesuffix(".plist")
        capability_id = f"runtime.launchd.{display}"
    else:
        display = capability or Path(source.split(" and ", 1)[0]).name or "Mac census capability"
        basis = {"section": row.get("_section"), "source": source, "capability": capability}
        capability_id = f"mac.census.{_slug(display)}.{_sha256(basis)[:10]}"

    unknown_runtime = "unknown" in f"{grade} {ground}".casefold()
    if state.startswith("RUNNING"):
        configured: bool | None = True
        runtime_confirmed: bool | None = True
        runtime_state = "running"
    elif state.startswith("BUILT-NOT-WIRED"):
        configured = False
        runtime_confirmed = False
        runtime_state = "dark"
    elif state.startswith("WIRED-BUT-OFF"):
        configured = True
        runtime_confirmed = None if unknown_runtime else False
        runtime_state = "unknown" if runtime_confirmed is None else "dark"
    elif state.startswith("STALE"):
        configured = True if any(token in ground.casefold() for token in ("plist", "installed", "configuration")) else None
        runtime_confirmed = None if unknown_runtime else False
        runtime_state = "unknown" if runtime_confirmed is None else "dark"
    else:
        configured = None
        runtime_confirmed = None
        runtime_state = "unknown"
    artifact_present = False if "missing" in f"{source} {ground}".casefold() else True
    authority_granted = False if any(
        token in f"{ground} {verdict}".casefold()
        for token in ("do not activate", "no activation", "approval", "authority unknown")
    ) else None
    evidence_id = _sha256({"section": row.get("_section"), "source": source, "state": state})[:16]
    return {
        "capability_id": capability_id,
        "display_name": display,
        "artifact_present": artifact_present,
        "configured": configured,
        "runtime_confirmed": runtime_confirmed,
        "authority_granted": authority_granted,
        "owner": "MacSol census / unregistered",
        "last_seen": snapshot,
        "register_stage": "unregistered",
        "runtime_state": runtime_state,
        "machine_applicability": "applicable",
        "observed_decision": _mac_decision(verdict),
        "evidence_refs": [f"mac-census:{_slug(str(row.get('_section') or 'inventory'))}:{evidence_id}"],
    }


def load_mac_inventory(path: str | Path, *, observed_at: str) -> dict[str, Any]:
    """Load a future JSON emitter or the current bounded MacSol Markdown report."""

    source = Path(path)
    if not source.is_file():
        return {
            "machine": "mac",
            "observed_at": observed_at,
            "source_ref": source.name,
            "capabilities": [],
            "bridge_health": {},
            "errors": ["MISSING_MAC_INVENTORY"],
        }
    raw = source.read_bytes()
    source_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
    if source.suffix.casefold() == ".json":
        payload = json.loads(raw.decode("utf-8"))
        result = dict(payload)
        result.setdefault("machine", "mac")
        result.setdefault("observed_at", observed_at)
        result.setdefault("capabilities", [])
        result.setdefault("bridge_health", {})
        result.setdefault("errors", [])
        result["source_ref"] = source.name
        result["source_sha256"] = source_hash
        return result

    text = raw.decode("utf-8")
    snapshot = _mac_snapshot(text, observed_at)
    by_id: dict[str, dict[str, Any]] = {}
    for table_row in _mac_table_rows(text):
        item = _mac_row_from_table(table_row, snapshot=snapshot)
        by_id[item["capability_id"]] = item
    health: dict[str, Any] = {}
    capacity = re.search(
        r"(\d+)\s+GiB total,\s*(\d+)\s+GiB used,\s*(\d+)(?:-\d+)?\s+GiB free\s*\((\d+)% used\)",
        text,
    )
    if capacity:
        health = {
            "mount_present": "/Volumes/openclaw_e" in text and "mounted" in text,
            "total_gib": int(capacity.group(1)),
            "used_gib": int(capacity.group(2)),
            "free_gib": int(capacity.group(3)),
            "used_percent": int(capacity.group(4)),
        }
    errors = [] if by_id else ["MAC_INVENTORY_TABLES_NOT_PARSED"]
    return {
        "machine": "mac",
        "observed_at": snapshot,
        "source_ref": source.name,
        "source_sha256": source_hash,
        "capabilities": [by_id[key] for key in sorted(by_id)],
        "bridge_health": health,
        "errors": errors,
    }


def _run_readonly(command: Sequence[str]) -> tuple[int, str, str]:
    completed = subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.returncode, completed.stdout, completed.stderr


def _openclaw_runtime_text(value: str) -> bool:
    folded = value.casefold()
    return any(
        token in folded
        for token in (
            "openclaw",
            "cassandra",
            "chief",
            "guardian",
            "hermes",
            "maestro",
            "niles",
            "clara",
            "invoice",
            "gpu-model",
            "ollama",
        )
    )


def _parse_systemd_list_units(output: str) -> dict[str, dict[str, Any]]:
    units: dict[str, dict[str, Any]] = {}
    for line in output.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        unit, _load, active, sub = parts[:4]
        description = parts[4] if len(parts) == 5 else unit
        if not _openclaw_runtime_text(f"{unit} {description}"):
            continue
        units[unit] = {
            "unit": unit,
            "description": description,
            "configured": None,
            "runtime_confirmed": active == "active",
            "runtime_state": "running" if active == "active" else "dark",
            "active_state": active,
            "sub_state": sub,
            "process_basenames": [],
        }
    return units


def _parse_systemd_unit_files(output: str) -> dict[str, str]:
    states: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and _openclaw_runtime_text(parts[0]):
            states[parts[0]] = parts[1]
    return states


def _parse_crontab(output: str, *, observed_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ("=" in line and len(line.split()) == 1):
            continue
        parts = line.split(None, 5)
        if len(parts) < 6 or not _openclaw_runtime_text(line):
            continue
        command = parts[5]
        command_hash = hashlib.sha256(command.encode("utf-8")).hexdigest()[:20]
        safe_paths = sorted(
            set(
                re.findall(
                    r"/home/openclaw/[A-Za-z0-9_.@/+:-]+",
                    command,
                )
            )
        )
        rows.append(
            {
                "command_hash": command_hash,
                "display_name": Path(safe_paths[-1]).name if safe_paths else "OpenClaw scheduled job",
                "owner": "OpenClaw user crontab",
                "artifact_present": any(Path(path).exists() for path in safe_paths) if safe_paths else None,
                "runtime_confirmed": None,
                "runtime_state": "unknown",
                "last_seen": observed_at,
                "evidence_refs": [f"cron:sha256:{command_hash}"] + [f"script:{path}" for path in safe_paths],
            }
        )
    return rows


def _parse_listener_processes(output: str, *, observed_at: str) -> list[dict[str, Any]]:
    by_script: dict[str, dict[str, Any]] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or "/home/openclaw" not in line or not _openclaw_runtime_text(line):
            continue
        script_matches = re.findall(r"/home/openclaw/[A-Za-z0-9_.@/+:-]+", line)
        if not script_matches:
            continue
        script = Path(script_matches[-1]).name
        if not script:
            continue
        by_script[script] = {
            "script_basename": script,
            "runtime_confirmed": True,
            "last_seen": observed_at,
            "evidence_ref": f"process-script:{script}",
        }
    return [by_script[key] for key in sorted(by_script)]


def collect_pc_runtime(*, observed_at: str) -> dict[str, Any]:
    """Collect bounded, metadata-only systemd, cron, and listener process state."""

    errors: list[str] = []
    rc, stdout, _stderr = _run_readonly(
        ("systemctl", "--user", "list-units", "--type=service", "--type=timer", "--all", "--no-legend", "--plain")
    )
    if rc != 0:
        errors.append("SYSTEMD_LIST_UNITS_FAILED")
        units: dict[str, dict[str, Any]] = {}
    else:
        units = _parse_systemd_list_units(stdout)
    rc, stdout, _stderr = _run_readonly(
        ("systemctl", "--user", "list-unit-files", "--type=service", "--type=timer", "--no-legend", "--plain")
    )
    if rc != 0:
        errors.append("SYSTEMD_LIST_UNIT_FILES_FAILED")
        unit_files: dict[str, str] = {}
    else:
        unit_files = _parse_systemd_unit_files(stdout)
    for unit, state in unit_files.items():
        item = units.setdefault(
            unit,
            {
                "unit": unit,
                "description": unit,
                "runtime_confirmed": False,
                "runtime_state": "dark",
                "active_state": "inactive",
                "sub_state": "unknown",
                "process_basenames": [],
            },
        )
        item["configured"] = state not in {"disabled", "masked", "bad"}
        item["unit_file_state"] = state

    rc, stdout, _stderr = _run_readonly(("ps", "-eo", "pid=,args="))
    listeners = _parse_listener_processes(stdout, observed_at=observed_at) if rc == 0 else []
    if rc != 0:
        errors.append("LISTENER_PROCESS_LIST_FAILED")
    scripts = [item["script_basename"] for item in listeners]
    for item in units.values():
        item["process_basenames"] = scripts if item.get("runtime_confirmed") else []
        item["last_seen"] = observed_at

    rc, stdout, stderr = _run_readonly(("crontab", "-l"))
    if rc == 0:
        cron = _parse_crontab(stdout, observed_at=observed_at)
    elif "no crontab" in stderr.casefold():
        cron = []
    else:
        cron = []
        errors.append("CRONTAB_READ_FAILED")
    return {
        "machine": "pc",
        "observed_at": observed_at,
        "systemd": [units[key] for key in sorted(units)],
        "cron": cron,
        "listener_processes": listeners,
        "errors": errors,
    }


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _file_inventory_state(ledger_path: Path, *, observed_at: str) -> dict[str, Any]:
    state: dict[str, Any] = {
        "available": False,
        "stale": True,
        "last_seen": None,
        "relative_paths": set(),
        "absolute_paths": set(),
    }
    if not ledger_path.is_file():
        return state
    conn = sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True)
    try:
        if not _table_exists(conn, "file_inventory"):
            return state
        state["available"] = True
        row = conn.execute("SELECT max(discovered_at) FROM file_inventory").fetchone()
        state["last_seen"] = str(row[0]) if row and row[0] is not None else None
        state["stale"] = _is_stale(
            state["last_seen"], observed_at, FILE_INVENTORY_MAX_AGE_SECONDS
        )
        if not state["stale"]:
            for relative_path, absolute_path in conn.execute(
                "SELECT relative_path, absolute_path FROM file_inventory"
            ):
                state["relative_paths"].add(str(relative_path).lstrip("./"))
                state["absolute_paths"].add(str(absolute_path))
    finally:
        conn.close()
    return state


def _artifact_presence(
    source_files: Sequence[Any], file_inventory: Mapping[str, Any]
) -> bool | None:
    sources = [str(value).lstrip("./") for value in source_files if str(value).strip()]
    if not sources:
        return None
    if not file_inventory.get("available") or file_inventory.get("stale"):
        return None
    relative = set(file_inventory.get("relative_paths") or ())
    absolute = set(file_inventory.get("absolute_paths") or ())
    return all(
        source in relative
        or source in absolute
        or f"/home/openclaw/{source}" in absolute
        for source in sources
    )


def _unit_refs(capability: Mapping[str, Any]) -> set[str]:
    values = list(capability.get("flag_or_config") or ())
    live_state = capability.get("live_state") or {}
    if isinstance(live_state, Mapping):
        for finding in live_state.get("findings") or ():
            if isinstance(finding, Mapping):
                values.append(finding.get("source_ref"))
    return {match.group(1) for value in values for match in _UNIT_RE.finditer(str(value or ""))}


def _registered_pc_row(
    capability: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
    file_inventory: Mapping[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    units = {str(item.get("unit")): item for item in inventory.get("systemd") or ()}
    unit_refs = _unit_refs(capability)
    matched = [units[name] for name in sorted(unit_refs) if name in units]
    gate_stage = str(capability.get("gate_stage") or "unknown")
    live_state = str(capability.get("live_production_state") or "unknown")
    canary = str(capability.get("canary_status") or "").casefold()
    configured = gate_stage == "operator_approved_live"
    authority_granted = gate_stage == "operator_approved_live"
    if matched:
        runtime_confirmed = any(item.get("runtime_confirmed") is True for item in matched)
        runtime_state = "running" if runtime_confirmed else (
            "dark" if any(item.get("runtime_confirmed") is False for item in matched) else "unknown"
        )
        applicability = "applicable"
        last_seen = max(
            (str(item.get("last_seen") or "") for item in matched),
            default=str(capability.get("last_verified_at") or ""),
        )
    elif live_state == "enabled_verified" or (
        gate_stage == "operator_approved_live"
        and any(token in canary for token in ("deployed", "production", "active"))
    ):
        runtime_confirmed = True
        runtime_state = "running"
        applicability = "embedded_or_verified_owner_path"
        last_seen = str(capability.get("last_verified_at") or observed_at)
    elif live_state in {"set_false", "unset_default_off", "disabled_verified"}:
        runtime_confirmed = False
        runtime_state = "dark"
        applicability = "applicable"
        last_seen = str(capability.get("last_verified_at") or observed_at)
    else:
        runtime_confirmed = None
        runtime_state = "not_applicable"
        applicability = "not_applicable"
        last_seen = str(capability.get("last_verified_at") or observed_at)

    artifact_present = _artifact_presence(capability.get("source_files") or (), file_inventory)
    drift_codes: list[str] = []
    if artifact_present is False:
        drift_codes.append("REGISTERED_CODE_MISSING")
    elif artifact_present is None and capability.get("source_files") and file_inventory.get("stale"):
        drift_codes.append("LEDGER_STALE")
    if gate_stage == "operator_approved_live" and runtime_confirmed is False:
        drift_codes.append("REGISTERED_RUNTIME_DARK")
    evidence_refs = ["activation_gate_register.json"]
    evidence_refs.extend(f"systemd:{item['unit']}" for item in matched)
    if artifact_present is not None:
        evidence_refs.append("ledger:file_inventory")
    elif file_inventory.get("stale"):
        evidence_refs.append("ledger:file_inventory:stale")
    return {
        "capability_id": str(capability["capability_id"]),
        "display_name": str(capability.get("display_name") or capability["capability_id"]),
        "machine": "pc",
        "artifact_present": artifact_present,
        "configured": configured,
        "runtime_confirmed": runtime_confirmed,
        "authority_granted": authority_granted,
        "owner": str(capability.get("owner") or "unassigned"),
        "last_seen": last_seen or None,
        "observed_at": str(inventory.get("observed_at") or observed_at),
        "register_stage": gate_stage,
        "runtime_state": runtime_state,
        "machine_applicability": applicability,
        "observed_decision": f"MIRROR_{gate_stage.upper()}",
        "evidence_refs": sorted(set(evidence_refs)),
        "health": {},
        "drift_codes": sorted(set(drift_codes)),
    }


def _registered_mac_row(
    capability: Mapping[str, Any], *, inventory: Mapping[str, Any], observed_at: str
) -> dict[str, Any]:
    inventory_seen = str(inventory.get("observed_at") or "")
    stale = bool(inventory.get("errors")) or _is_stale(
        inventory_seen, observed_at, MACHINE_INVENTORY_MAX_AGE_SECONDS
    )
    return {
        "capability_id": str(capability["capability_id"]),
        "display_name": str(capability.get("display_name") or capability["capability_id"]),
        "machine": "mac",
        "artifact_present": None,
        "configured": None,
        "runtime_confirmed": None,
        "authority_granted": None,
        "owner": str(capability.get("owner") or "unassigned"),
        "last_seen": inventory_seen or None,
        "observed_at": inventory_seen or observed_at,
        "register_stage": str(capability.get("gate_stage") or "unknown"),
        "runtime_state": "unknown",
        "machine_applicability": "unknown",
        "observed_decision": "MIRROR_MAC_UNKNOWN",
        "evidence_refs": [str(inventory.get("source_ref") or "mac-inventory:unavailable")],
        "health": {},
        "drift_codes": ["MACHINE_INVENTORY_STALE"] if stale else [],
    }


def _unregistered_pc_rows(
    inventory: Mapping[str, Any], registered_units: set[str], *, observed_at: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in inventory.get("systemd") or ():
        unit = str(item.get("unit") or "").strip()
        if not unit or unit in registered_units:
            continue
        running = item.get("runtime_confirmed") is True
        rows.append(
            {
                "capability_id": f"runtime.systemd.{unit}",
                "display_name": str(item.get("description") or unit),
                "machine": "pc",
                "artifact_present": True if item.get("configured") else None,
                "configured": item.get("configured"),
                "runtime_confirmed": item.get("runtime_confirmed"),
                "authority_granted": None,
                "owner": str(item.get("description") or "unregistered systemd owner"),
                "last_seen": str(item.get("last_seen") or inventory.get("observed_at") or observed_at),
                "observed_at": str(inventory.get("observed_at") or observed_at),
                "register_stage": "unregistered",
                "runtime_state": str(item.get("runtime_state") or ("running" if running else "unknown")),
                "machine_applicability": "applicable",
                "observed_decision": "OBSERVED_RUNNING_UNREGISTERED" if running else "OBSERVED_UNREGISTERED",
                "evidence_refs": [f"systemd:{unit}"],
                "health": {},
                "drift_codes": ["RUNTIME_UNREGISTERED"] if running else [],
            }
        )
    for item in inventory.get("cron") or ():
        cron_hash = str(item.get("command_hash") or "").strip()
        if not cron_hash:
            continue
        rows.append(
            {
                "capability_id": f"runtime.cron.{cron_hash}",
                "display_name": str(item.get("display_name") or "Scheduled cron owner"),
                "machine": "pc",
                "artifact_present": item.get("artifact_present"),
                "configured": True,
                "runtime_confirmed": item.get("runtime_confirmed"),
                "authority_granted": None,
                "owner": str(item.get("owner") or "unregistered cron owner"),
                "last_seen": str(item.get("last_seen") or inventory.get("observed_at") or observed_at),
                "observed_at": str(inventory.get("observed_at") or observed_at),
                "register_stage": "unregistered",
                "runtime_state": str(item.get("runtime_state") or "unknown"),
                "machine_applicability": "applicable",
                "observed_decision": "OBSERVED_CONFIGURED_UNREGISTERED",
                "evidence_refs": list(item.get("evidence_refs") or [f"cron:{cron_hash}"]),
                "health": {},
                "drift_codes": ["RUNTIME_UNREGISTERED"],
            }
        )
    return rows


def _mac_inventory_rows(inventory: Mapping[str, Any], *, observed_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    inventory_seen = str(inventory.get("observed_at") or observed_at)
    for item in inventory.get("capabilities") or ():
        row = dict(item)
        row.update(
            {
                "machine": "mac",
                "observed_at": inventory_seen,
                "health": dict(item.get("health") or {}),
                "evidence_refs": list(item.get("evidence_refs") or [inventory.get("source_ref")]),
                "drift_codes": list(item.get("drift_codes") or ()),
            }
        )
        if row.get("register_stage") == "unregistered" and row.get("runtime_confirmed") is True:
            row["drift_codes"] = sorted(set(row["drift_codes"] + ["RUNTIME_UNREGISTERED"]))
        rows.append(row)
    health = dict(inventory.get("bridge_health") or {})
    if health:
        mounted = health.get("mount_present") is True
        rows.append(
            {
                "capability_id": "runtime.bridge.openclaw-e",
                "display_name": "OpenClaw E bridge mount",
                "machine": "mac",
                "artifact_present": mounted,
                "configured": True,
                "runtime_confirmed": mounted,
                "authority_granted": None,
                "owner": "MacSol / bridge",
                "last_seen": inventory_seen,
                "observed_at": inventory_seen,
                "register_stage": "unregistered",
                "runtime_state": "running" if mounted else "dark",
                "machine_applicability": "applicable",
                "observed_decision": "WIRE_IN",
                "evidence_refs": [str(inventory.get("source_ref") or "mac-inventory") + "#bridge-health"],
                "health": health,
                "drift_codes": ["RUNTIME_UNREGISTERED"] if mounted else [],
            }
        )
    return rows


def _finalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(row)
    state = str(item.get("runtime_state") or "unknown")
    if state not in RUNTIME_STATES:
        state = "unknown"
    item["runtime_state"] = state
    item["drift_codes"] = sorted(
        code for code in set(item.get("drift_codes") or ()) if code in DRIFT_CODES
    )
    item["drift_flag"] = bool(item["drift_codes"])
    item["evidence_refs"] = sorted(str(value) for value in item.get("evidence_refs") or () if value)
    item["health"] = dict(item.get("health") or {})
    fingerprint_basis = {
        key: item.get(key)
        for key in (
            "capability_id",
            "machine",
            "display_name",
            "artifact_present",
            "configured",
            "runtime_confirmed",
            "authority_granted",
            "owner",
            "register_stage",
            "runtime_state",
            "machine_applicability",
            "observed_decision",
            "evidence_refs",
            "health",
            "drift_codes",
        )
    }
    item["state_fingerprint"] = "sha256:" + _sha256(fingerprint_basis)
    return item


def _atomic_json_write(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)


def _attention_payload(rows: Sequence[Mapping[str, Any]], *, observed_at: str, batch_id: str) -> dict[str, Any]:
    drift = [
        {
            "capability_id": row["capability_id"],
            "machine": row["machine"],
            "display_name": row["display_name"],
            "drift_codes": list(row["drift_codes"]),
            "runtime_state": row["runtime_state"],
            "owner": row["owner"],
        }
        for row in rows
        if row["drift_flag"]
    ]
    bridge_health = [
        {
            "capability_id": row["capability_id"],
            "machine": row["machine"],
            "health": dict(row["health"]),
            "attention_reasons": ["BRIDGE_SPACE_HIGH"]
            if int((row.get("health") or {}).get("used_percent") or 0) >= 90
            else [],
        }
        for row in rows
        if row.get("health")
    ]
    return {
        "schema_version": "capability_ledger_drift_attention_v1",
        "read_model_id": "capability_ledger_drift_attention",
        "status": "ATTENTION_REQUIRED" if drift or any(item["attention_reasons"] for item in bridge_health) else "CURRENT",
        "generated_at": observed_at,
        "batch_id": batch_id,
        "drift_count": len(drift),
        "drift": drift,
        "bridge_health": bridge_health,
        "machine_proof": {
            "ledger_only_projection": True,
            "register_mutated": False,
            "runtime_mutated": False,
            "external_send_performed": False,
        },
    }


def _projection_receipt(result: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "schema_version",
        "status",
        "observed_at",
        "source_fingerprint",
        "batch_id",
        "packet_id",
        "machine_counts",
        "activation_count",
        "drift_count",
        "changed_count",
        "decision_count",
        "idempotent_replay",
        "authority_boundary",
    )
    return {key: result.get(key) for key in keys}


def _persist_batch(
    *,
    ledger_path: Path,
    rows: Sequence[Mapping[str, Any]],
    source_fingerprint: str,
    observed_at: str,
) -> dict[str, Any]:
    business_ops_ledger.init_business_ops_ledger(str(ledger_path))
    conn = sqlite3.connect(ledger_path, timeout=60)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=60000")
        ensure_capability_ledger_schema(conn)
        conn.commit()
        existing = {
            (str(row["capability_id"]), str(row["machine"])): str(row["state_fingerprint"])
            for row in conn.execute(
                "SELECT capability_id, machine, state_fingerprint FROM capability_activations"
            )
        }
        changed = [
            row
            for row in rows
            if existing.get((str(row["capability_id"]), str(row["machine"])))
            != row["state_fingerprint"]
        ]
        base_batch_id = f"capability-reconcile:{source_fingerprint.split(':', 1)[-1][:24]}"
        existing_run = conn.execute(
            "SELECT batch_id, receipt_json FROM capability_reconciliation_runs WHERE batch_id=?",
            (base_batch_id,),
        ).fetchone()
        if not changed and existing_run is not None:
            return {
                "status": "IDEMPOTENT_REPLAY",
                "batch_id": str(existing_run["batch_id"]),
                "packet_id": str(existing_run["batch_id"]),
                "changed_count": 0,
                "decision_count": 0,
                "idempotent_replay": True,
            }
        batch_id = base_batch_id
        if existing_run is not None:
            prior_fingerprint = _sha256(sorted(existing.items()))[:10]
            batch_id = f"{base_batch_id}:repair:{prior_fingerprint}"
        drift_count = sum(1 for row in rows if row["drift_flag"])
        packet_safe = {
            "schema_version": SCHEMA_VERSION,
            "batch_id": batch_id,
            "activation_count": len(rows),
            "changed_count": len(changed),
            "drift_count": drift_count,
            "machines": dict(sorted(Counter(str(row["machine"]) for row in rows).items())),
            "metadata_only": True,
            "register_writeback": False,
            "runtime_activation": False,
        }
        receipt = {
            **packet_safe,
            "packet_id": batch_id,
            "source_fingerprint": source_fingerprint,
            "observed_at": observed_at,
            "decision_count": len(changed),
            "status": "CONFIRMED",
            "authority_boundary": {
                "ledger_mirror_write_performed": True,
                "register_mutated": False,
                "service_or_cron_mutated": False,
                "runtime_activation_performed": False,
                "authority_granted": False,
                "external_send_performed": False,
                "money_moved": False,
                "delete_performed": False,
            },
        }
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO events (
                event_id, ts, event_type, actor, prompt_hash,
                operator_visible_summary, raw_sensitive_data_stored, replay_safe
            ) VALUES (?, ?, 'capability_reconciliation', 'capability_ledger_reconciler', ?, ?, 0, 1)
            """,
            (
                batch_id,
                observed_at,
                source_fingerprint,
                f"Mirrored {len(rows)} capability-machine rows; {drift_count} carry deterministic drift.",
            ),
        )
        conn.execute(
            """
            INSERT INTO packets (
                packet_id, event_id, intent_name, request_category, actor_name,
                execution_authority, approval_required, approval_tier, action_status,
                packet_json_safe
            ) VALUES (?, ?, 'capability_reconciliation', 'metadata_mirror',
                      'capability_ledger_reconciler', 0, 0, NULL, 'mirror_recorded', ?)
            """,
            (batch_id, batch_id, _stable_json(packet_safe)),
        )
        for row in changed:
            conn.execute(
                """
                INSERT INTO capability_activations (
                    capability_id, machine, display_name, artifact_present, configured,
                    runtime_confirmed, authority_granted, owner, last_seen, observed_at,
                    register_stage, runtime_state, machine_applicability, observed_decision,
                    evidence_refs_json, health_json, drift_codes_json, drift_flag,
                    state_fingerprint, recorded_at, batch_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(capability_id, machine) DO UPDATE SET
                    display_name=excluded.display_name,
                    artifact_present=excluded.artifact_present,
                    configured=excluded.configured,
                    runtime_confirmed=excluded.runtime_confirmed,
                    authority_granted=excluded.authority_granted,
                    owner=excluded.owner,
                    last_seen=excluded.last_seen,
                    observed_at=excluded.observed_at,
                    register_stage=excluded.register_stage,
                    runtime_state=excluded.runtime_state,
                    machine_applicability=excluded.machine_applicability,
                    observed_decision=excluded.observed_decision,
                    evidence_refs_json=excluded.evidence_refs_json,
                    health_json=excluded.health_json,
                    drift_codes_json=excluded.drift_codes_json,
                    drift_flag=excluded.drift_flag,
                    state_fingerprint=excluded.state_fingerprint,
                    recorded_at=excluded.recorded_at,
                    batch_id=excluded.batch_id
                """,
                (
                    row["capability_id"],
                    row["machine"],
                    row["display_name"],
                    _bool_int(row.get("artifact_present")),
                    _bool_int(row.get("configured")),
                    _bool_int(row.get("runtime_confirmed")),
                    _bool_int(row.get("authority_granted")),
                    row["owner"],
                    row.get("last_seen"),
                    row["observed_at"],
                    row["register_stage"],
                    row["runtime_state"],
                    row["machine_applicability"],
                    row.get("observed_decision"),
                    _stable_json(row["evidence_refs"]),
                    _stable_json(row["health"]),
                    _stable_json(row["drift_codes"]),
                    _bool_int(bool(row["drift_flag"])),
                    row["state_fingerprint"],
                    observed_at,
                    batch_id,
                ),
            )
            conn.execute(
                """
                INSERT INTO capability_decisions (packet_id, capability_name, decision, reason)
                VALUES (?, ?, ?, ?)
                """,
                (
                    batch_id,
                    f"{row['capability_id']}@{row['machine']}",
                    row.get("observed_decision") or "MIRROR_STATE_CHANGED",
                    _stable_json(
                        {
                            "artifact_present": row.get("artifact_present"),
                            "configured": row.get("configured"),
                            "runtime_confirmed": row.get("runtime_confirmed"),
                            "authority_granted": row.get("authority_granted"),
                            "register_stage": row["register_stage"],
                            "runtime_state": row["runtime_state"],
                            "drift_codes": row["drift_codes"],
                        }
                    ),
                ),
            )
        conn.execute(
            """
            INSERT INTO operator_explanations (event_id, packet_id, summary, safe_for_telegram)
            VALUES (?, ?, ?, 1)
            """,
            (
                batch_id,
                batch_id,
                f"Capability mirror refreshed: {len(rows)} rows, {len(changed)} changed, {drift_count} drifted.",
            ),
        )
        conn.execute(
            """
            INSERT INTO capability_reconciliation_runs (
                batch_id, observed_at, source_fingerprint, activation_count,
                changed_count, decision_count, drift_count, status, receipt_json, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'CONFIRMED', ?, ?)
            """,
            (
                batch_id,
                observed_at,
                source_fingerprint,
                len(rows),
                len(changed),
                len(changed),
                drift_count,
                _stable_json(receipt),
                observed_at,
            ),
        )
        conn.commit()
        return {
            "status": "CONFIRMED",
            "batch_id": batch_id,
            "packet_id": batch_id,
            "changed_count": len(changed),
            "decision_count": len(changed),
            "idempotent_replay": False,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reconcile_capabilities(
    *,
    register_path: str | Path = DEFAULT_REGISTER_PATH,
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
    pc_inventory: Mapping[str, Any] | None = None,
    mac_inventory: Mapping[str, Any] | None = None,
    mac_inventory_path: str | Path = DEFAULT_MAC_REPORT_PATH,
    observed_at: str | None = None,
    confirm: bool = False,
    receipt_path: str | Path = DEFAULT_RECEIPT_PATH,
    attention_path: str | Path = DEFAULT_ATTENTION_PATH,
) -> dict[str, Any]:
    observed_at = observed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    pc_inventory = dict(pc_inventory or collect_pc_runtime(observed_at=observed_at))
    mac_inventory = dict(
        mac_inventory or load_mac_inventory(mac_inventory_path, observed_at=observed_at)
    )
    register_file = Path(register_path)
    ledger_file = Path(ledger_path)
    register = json.loads(register_file.read_text(encoding="utf-8"))
    capabilities = list(register.get("capabilities") or ())
    file_inventory = _file_inventory_state(ledger_file, observed_at=observed_at)
    registered_units = set().union(*(_unit_refs(item) for item in capabilities)) if capabilities else set()

    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for capability in capabilities:
        for row in (
            _registered_pc_row(
                capability,
                inventory=pc_inventory,
                file_inventory=file_inventory,
                observed_at=observed_at,
            ),
            _registered_mac_row(capability, inventory=mac_inventory, observed_at=observed_at),
        ):
            rows[(row["capability_id"], row["machine"])] = _finalize_row(row)
    for row in _unregistered_pc_rows(pc_inventory, registered_units, observed_at=observed_at):
        rows[(row["capability_id"], row["machine"])] = _finalize_row(row)
    for row in _mac_inventory_rows(mac_inventory, observed_at=observed_at):
        key = (str(row["capability_id"]), "mac")
        rows[key] = _finalize_row({**rows.get(key, {}), **row})

    activations = [rows[key] for key in sorted(rows)]
    machine_counts = dict(sorted(Counter(row["machine"] for row in activations).items()))
    source_fingerprint = "sha256:" + _sha256(
        {
            "register": register,
            "file_inventory_last_seen": file_inventory.get("last_seen"),
            "states": [row["state_fingerprint"] for row in activations],
        }
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "DRY_RUN_CONFIRM_REQUIRED",
        "observed_at": observed_at,
        "source_fingerprint": source_fingerprint,
        "machine_counts": machine_counts,
        "activation_count": len(activations),
        "drift_count": sum(1 for row in activations if row["drift_flag"]),
        "activations": activations,
        "authority_boundary": {
            "ledger_mirror_write_performed": False,
            "activation_performed": False,
            "register_mutated": False,
            "service_mutated": False,
            "external_send_performed": False,
            "money_moved": False,
            "delete_performed": False,
        },
    }
    if confirm:
        persisted = _persist_batch(
            ledger_path=ledger_file,
            rows=activations,
            source_fingerprint=source_fingerprint,
            observed_at=observed_at,
        )
        result.update(persisted)
        result["authority_boundary"] = {
            "ledger_mirror_write_performed": not bool(persisted["idempotent_replay"]),
            "activation_performed": False,
            "register_mutated": False,
            "service_mutated": False,
            "external_send_performed": False,
            "money_moved": False,
            "delete_performed": False,
        }
        _atomic_json_write(receipt_path, _projection_receipt(result))
        _atomic_json_write(
            attention_path,
            _attention_payload(activations, observed_at=observed_at, batch_id=result["batch_id"]),
        )
    return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mirror capability/register/runtime state into the business ledger.")
    parser.add_argument("--register", default=str(DEFAULT_REGISTER_PATH))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER_PATH))
    parser.add_argument("--mac-inventory", default=str(DEFAULT_MAC_REPORT_PATH))
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT_PATH))
    parser.add_argument("--attention", default=str(DEFAULT_ATTENTION_PATH))
    parser.add_argument("--observed-at")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--once", action="store_true", help="Compatibility marker for scheduled one-shot invocation.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = reconcile_capabilities(
        register_path=args.register,
        ledger_path=args.ledger,
        mac_inventory_path=args.mac_inventory,
        observed_at=args.observed_at,
        confirm=bool(args.confirm),
        receipt_path=args.receipt,
        attention_path=args.attention,
    )
    display = {key: value for key, value in result.items() if key != "activations"}
    display["activation_preview_count"] = len(result.get("activations") or ())
    print(json.dumps(display, indent=2, sort_keys=True))
    return 0


__all__ = [
    "DEFAULT_ATTENTION_PATH",
    "DEFAULT_LEDGER_PATH",
    "DEFAULT_MAC_REPORT_PATH",
    "DEFAULT_RECEIPT_PATH",
    "DEFAULT_REGISTER_PATH",
    "DRIFT_CODES",
    "RUNTIME_STATES",
    "collect_pc_runtime",
    "ensure_capability_ledger_schema",
    "load_mac_inventory",
    "main",
    "reconcile_capabilities",
]


if __name__ == "__main__":
    raise SystemExit(main())
