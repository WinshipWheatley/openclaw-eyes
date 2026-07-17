"""One-way capability/register/runtime mirror into the business-ops ledger.

The reconciler is metadata-only. It cannot activate services, mutate the
Activation Gate Register, grant authority, send externally, move money, or
delete anything.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


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


def reconcile_capabilities(
    *,
    register_path: str | Path = DEFAULT_REGISTER_PATH,
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
    pc_inventory: Mapping[str, Any],
    mac_inventory: Mapping[str, Any],
    observed_at: str,
    confirm: bool = False,
    receipt_path: str | Path = DEFAULT_RECEIPT_PATH,
    attention_path: str | Path = DEFAULT_ATTENTION_PATH,
) -> dict[str, Any]:
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
            "pc_inventory": pc_inventory,
            "mac_inventory": mac_inventory,
            "file_inventory_last_seen": file_inventory.get("last_seen"),
            "states": [row["state_fingerprint"] for row in activations],
        }
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "DRY_RUN_CONFIRM_REQUIRED" if not confirm else "CONFIRM_NOT_IMPLEMENTED",
        "observed_at": observed_at,
        "source_fingerprint": source_fingerprint,
        "machine_counts": machine_counts,
        "activation_count": len(activations),
        "drift_count": sum(1 for row in activations if row["drift_flag"]),
        "activations": activations,
        "authority_boundary": {
            "activation_performed": False,
            "register_mutated": False,
            "service_mutated": False,
            "external_send_performed": False,
            "money_moved": False,
            "delete_performed": False,
        },
    }
    return result


__all__ = [
    "DEFAULT_ATTENTION_PATH",
    "DEFAULT_LEDGER_PATH",
    "DEFAULT_MAC_REPORT_PATH",
    "DEFAULT_RECEIPT_PATH",
    "DEFAULT_REGISTER_PATH",
    "DRIFT_CODES",
    "RUNTIME_STATES",
    "ensure_capability_ledger_schema",
    "reconcile_capabilities",
]
