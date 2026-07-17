from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import business_ops_ledger
import capability_ledger_reconciler as reconciler


OBSERVED_AT = "2026-07-17T16:30:00+00:00"


def _register(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "capabilities": [
                    {
                        "capability_id": "demo_service",
                        "display_name": "Demo service",
                        "gate_stage": "operator_approved_live",
                        "owner": "Chief",
                        "last_verified_at": "2026-07-17T16:00:00+00:00",
                        "source_files": ["demo_service.py"],
                        "flag_or_config": ["demo.service"],
                        "live_production_state": "enabled_verified",
                        "live_state": {
                            "status": "enabled_verified",
                            "findings": [
                                {
                                    "source_ref": "/home/openclaw/.config/systemd/user/demo.service.d/live.conf"
                                }
                            ],
                        },
                        "canary_status": "deployed owner-process canary passed",
                    },
                    {
                        "capability_id": "demo_library",
                        "display_name": "Demo library",
                        "gate_stage": "canary",
                        "owner": "Sol",
                        "last_verified_at": "2026-07-17T15:00:00+00:00",
                        "source_files": ["demo_library.py"],
                        "flag_or_config": ["metadata-only module"],
                        "live_production_state": "not_applicable",
                        "live_state": {"status": "not_applicable", "findings": []},
                        "canary_status": "focused tests passed",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _ledger(path: Path) -> Path:
    business_ops_ledger.init_business_ops_ledger(str(path))
    conn = sqlite3.connect(path)
    try:
        conn.executemany(
            """
            INSERT INTO file_inventory (
                file_id, root_id, absolute_path, relative_path, file_name,
                size_bytes, modified_at, discovered_at, ingest_eligibility
            ) VALUES (?, 'pc_live_repo', ?, ?, ?, 100, ?, ?, 'eligible_metadata_only')
            """,
            [
                (
                    "file-demo-service",
                    "/home/openclaw/demo_service.py",
                    "demo_service.py",
                    "demo_service.py",
                    OBSERVED_AT,
                    OBSERVED_AT,
                ),
                (
                    "file-demo-library",
                    "/home/openclaw/demo_library.py",
                    "demo_library.py",
                    "demo_library.py",
                    OBSERVED_AT,
                    OBSERVED_AT,
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return path


def _pc_inventory() -> dict:
    return {
        "machine": "pc",
        "observed_at": OBSERVED_AT,
        "systemd": [
            {
                "unit": "demo.service",
                "description": "Demo owner",
                "configured": True,
                "runtime_confirmed": True,
                "runtime_state": "running",
                "last_seen": "2026-07-17T16:29:00+00:00",
                "process_basenames": ["demo_service.py"],
            },
            {
                "unit": "unregistered.service",
                "description": "Unregistered owner",
                "configured": True,
                "runtime_confirmed": True,
                "runtime_state": "running",
                "last_seen": "2026-07-17T16:28:00+00:00",
                "process_basenames": ["unregistered.py"],
            },
        ],
        "cron": [],
        "listener_processes": [],
        "errors": [],
    }


def _mac_inventory() -> dict:
    return {
        "machine": "mac",
        "observed_at": "2026-07-17T15:18:00+00:00",
        "source_ref": "MACSOL-CENSUS-MAC-RESULT-20260717.md",
        "capabilities": [
            {
                "capability_id": "runtime.launchd.com.openclaw.read-model-sync",
                "display_name": "com.openclaw.read-model-sync",
                "artifact_present": True,
                "configured": True,
                "runtime_confirmed": True,
                "authority_granted": None,
                "owner": "MacSol / unregistered",
                "last_seen": "2026-07-17T15:09:00+00:00",
                "register_stage": "unregistered",
                "runtime_state": "running",
                "machine_applicability": "applicable",
                "observed_decision": "WIRE_IN",
                "evidence_refs": ["mac-census:runtime:read-model-sync"],
            }
        ],
        "bridge_health": {
            "mount_present": True,
            "total_gib": 931,
            "used_gib": 845,
            "free_gib": 86,
            "used_percent": 91,
        },
        "errors": [],
    }


def test_additive_schema_keeps_activation_dimensions_separate(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "ledger.sqlite")
    conn = sqlite3.connect(ledger)
    try:
        reconciler.ensure_capability_ledger_schema(conn)
        columns = {
            row[1]: {"type": row[2], "notnull": row[3], "pk": row[5]}
            for row in conn.execute("PRAGMA table_info(capability_activations)")
        }
    finally:
        conn.close()

    for name in (
        "artifact_present",
        "configured",
        "runtime_confirmed",
        "authority_granted",
        "last_seen",
        "owner",
        "runtime_state",
        "machine_applicability",
        "drift_codes_json",
    ):
        assert name in columns
    assert columns["capability_id"]["pk"] == 1
    assert columns["machine"]["pk"] == 2


def test_dry_run_builds_two_machine_mirror_without_writing(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "ledger.sqlite")
    register = _register(tmp_path / "register.json")

    result = reconciler.reconcile_capabilities(
        register_path=register,
        ledger_path=ledger,
        pc_inventory=_pc_inventory(),
        mac_inventory=_mac_inventory(),
        observed_at=OBSERVED_AT,
        confirm=False,
    )

    assert result["status"] == "DRY_RUN_CONFIRM_REQUIRED"
    assert result["machine_counts"] == {"mac": 4, "pc": 3}
    rows = {(row["capability_id"], row["machine"]): row for row in result["activations"]}
    active = rows[("demo_service", "pc")]
    assert active["artifact_present"] is True
    assert active["configured"] is True
    assert active["runtime_confirmed"] is True
    assert active["authority_granted"] is True
    assert active["runtime_state"] == "running"
    assert active["drift_codes"] == []

    library = rows[("demo_library", "pc")]
    assert library["artifact_present"] is True
    assert library["configured"] is False
    assert library["runtime_confirmed"] is None
    assert library["authority_granted"] is False
    assert library["runtime_state"] == "not_applicable"

    unregistered = rows[("runtime.systemd.unregistered.service", "pc")]
    assert unregistered["runtime_confirmed"] is True
    assert unregistered["authority_granted"] is None
    assert unregistered["drift_codes"] == ["RUNTIME_UNREGISTERED"]

    mac_runtime = rows[("runtime.launchd.com.openclaw.read-model-sync", "mac")]
    assert mac_runtime["artifact_present"] is True
    assert mac_runtime["configured"] is True
    assert mac_runtime["runtime_confirmed"] is True
    assert mac_runtime["authority_granted"] is None

    bridge = rows[("runtime.bridge.openclaw-e", "mac")]
    assert bridge["runtime_state"] == "running"
    assert bridge["health"]["free_gib"] == 86
    assert bridge["health"]["used_percent"] == 91

    with sqlite3.connect(ledger) as conn:
        assert conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='capability_activations'"
        ).fetchone()[0] == 0
