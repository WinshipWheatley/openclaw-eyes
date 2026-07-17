from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import business_ops_ledger
import capability_ledger_reconciler as reconciler
import activation_gate_register


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


def test_macsol_markdown_adapter_preserves_runtime_verdicts_and_bridge_health(tmp_path: Path) -> None:
    report = tmp_path / "MACSOL-CENSUS-MAC-RESULT-20260717.md"
    report.write_text(
        """# MacSol Mac census result - 2026-07-17

**Snapshot:** 2026-07-17 11:18 EDT on macOS.

### B. Runtime versus activation register

| Exact path / activation | Ground truth | State | Grade | Verdict |
|---|---|---|---|---|
| `/Users/example/Library/LaunchAgents/com.openclaw.read-model-sync.plist` | `RunAtLoad=true`, `StartInterval=300`; log activity through 11:09 EDT says exit 0. | RUNNING (scheduled) | Confirmed | WIRE-IN |
| `/Applications/OpenClaw.app` | Old app; no current owner or runtime proof. | STALE | Confirmed installed; runtime Unknown | ARCHIVE |

### C. Built-but-dark capability surfaces

| Exact path / capability | Ground truth | State | Grade | Verdict |
|---|---|---|---|---|
| `/Applications/OBS.app` | OBS is installed; no OpenClaw runtime proof. | BUILT-NOT-WIRED | Confirmed | ARCHIVE the integration claim |

## 3. Bridge health

| Check | Result | Grade |
|---|---|---|
| Mount | `/Volumes/openclaw_e` is mounted as SMBFS. Capacity is 931 GiB total, 845 GiB used, 86 GiB free (91% used). | Confirmed snapshot |
""",
        encoding="utf-8",
    )

    inventory = reconciler.load_mac_inventory(report, observed_at=OBSERVED_AT)

    assert inventory["observed_at"] == "2026-07-17T11:18:00-04:00"
    assert inventory["source_sha256"].startswith("sha256:")
    assert inventory["bridge_health"] == {
        "free_gib": 86,
        "mount_present": True,
        "total_gib": 931,
        "used_gib": 845,
        "used_percent": 91,
    }
    rows = {row["capability_id"]: row for row in inventory["capabilities"]}
    runtime = rows["runtime.launchd.com.openclaw.read-model-sync"]
    assert runtime["artifact_present"] is True
    assert runtime["configured"] is True
    assert runtime["runtime_confirmed"] is True
    assert runtime["authority_granted"] is None
    assert runtime["observed_decision"] == "WIRE_IN"
    assert len(rows) == 3
    assert sorted(row["observed_decision"] for row in rows.values()) == ["ARCHIVE", "ARCHIVE", "WIRE_IN"]


def test_confirm_is_atomic_append_on_change_and_idempotent(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "ledger.sqlite")
    register = _register(tmp_path / "register.json")
    receipt = tmp_path / "receipt.json"
    attention = tmp_path / "attention.json"

    first = reconciler.reconcile_capabilities(
        register_path=register,
        ledger_path=ledger,
        pc_inventory=_pc_inventory(),
        mac_inventory=_mac_inventory(),
        observed_at=OBSERVED_AT,
        confirm=True,
        receipt_path=receipt,
        attention_path=attention,
    )

    assert first["status"] == "CONFIRMED"
    assert first["changed_count"] == 7
    assert first["decision_count"] == 7
    assert first["idempotent_replay"] is False
    assert receipt.is_file()
    assert attention.is_file()
    with sqlite3.connect(ledger) as conn:
        assert conn.execute("SELECT count(*) FROM capability_activations").fetchone()[0] == 7
        assert conn.execute("SELECT count(*) FROM capability_reconciliation_runs").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM capability_decisions").fetchone()[0] == 7
        assert conn.execute("SELECT count(*) FROM events WHERE event_type='capability_reconciliation'").fetchone()[0] == 1
        packet = conn.execute(
            "SELECT execution_authority, action_status FROM packets WHERE packet_id=?",
            (first["packet_id"],),
        ).fetchone()
        assert packet == (0, "mirror_recorded")

    second = reconciler.reconcile_capabilities(
        register_path=register,
        ledger_path=ledger,
        pc_inventory=_pc_inventory(),
        mac_inventory=_mac_inventory(),
        observed_at=OBSERVED_AT,
        confirm=True,
        receipt_path=receipt,
        attention_path=attention,
    )
    assert second["status"] == "IDEMPOTENT_REPLAY"
    assert second["changed_count"] == 0
    assert second["decision_count"] == 0
    assert second["idempotent_replay"] is True
    with sqlite3.connect(ledger) as conn:
        assert conn.execute("SELECT count(*) FROM capability_reconciliation_runs").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM capability_decisions").fetchone()[0] == 7

    changed_inventory = _pc_inventory()
    changed_inventory["systemd"][0] = {
        **changed_inventory["systemd"][0],
        "runtime_confirmed": False,
        "runtime_state": "dark",
    }
    changed = reconciler.reconcile_capabilities(
        register_path=register,
        ledger_path=ledger,
        pc_inventory=changed_inventory,
        mac_inventory=_mac_inventory(),
        observed_at=OBSERVED_AT,
        confirm=True,
        receipt_path=receipt,
        attention_path=attention,
    )
    assert changed["status"] == "CONFIRMED"
    assert changed["changed_count"] == 1
    assert changed["decision_count"] == 1
    with sqlite3.connect(ledger) as conn:
        row = conn.execute(
            "SELECT runtime_state, drift_codes_json FROM capability_activations "
            "WHERE capability_id='demo_service' AND machine='pc'"
        ).fetchone()
        assert row == ("dark", '["REGISTERED_RUNTIME_DARK"]')
        assert conn.execute("SELECT count(*) FROM capability_decisions").fetchone()[0] == 8


def test_pc_collector_keeps_only_safe_openclaw_metadata(monkeypatch) -> None:
    outputs = iter(
        [
            (
                0,
                "openclaw-demo.service loaded active running OpenClaw demo owner\n"
                "dbus.service loaded active running D-Bus User Message Bus\n",
                "",
            ),
            (0, "openclaw-demo.service enabled enabled\ndbus.service static -\n", ""),
            (0, " 123 /usr/bin/python /home/openclaw/demo_listener.py --secret hidden\n", ""),
            (
                0,
                "*/30 * * * * /home/openclaw/chief_env/bin/python /home/openclaw/scripts/refresh_ledger_knowledge.py --confirm\n",
                "",
            ),
        ]
    )
    monkeypatch.setattr(reconciler, "_run_readonly", lambda _command: next(outputs))

    inventory = reconciler.collect_pc_runtime(observed_at=OBSERVED_AT)

    assert [row["unit"] for row in inventory["systemd"]] == ["openclaw-demo.service"]
    assert inventory["systemd"][0]["runtime_confirmed"] is True
    assert inventory["listener_processes"] == [
        {
            "script_basename": "demo_listener.py",
            "runtime_confirmed": True,
            "last_seen": OBSERVED_AT,
            "evidence_ref": "process-script:demo_listener.py",
        }
    ]
    assert len(inventory["cron"]) == 1
    cron = inventory["cron"][0]
    assert len(cron["command_hash"]) == 20
    assert all("--secret" not in ref and "hidden" not in ref for ref in cron["evidence_refs"])


def test_stale_file_inventory_is_unknown_not_false_missing(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "ledger.sqlite")
    with sqlite3.connect(ledger) as conn:
        conn.execute("UPDATE file_inventory SET discovered_at='2026-06-14T00:00:00+00:00'")
        conn.commit()
    result = reconciler.reconcile_capabilities(
        register_path=_register(tmp_path / "register.json"),
        ledger_path=ledger,
        pc_inventory=_pc_inventory(),
        mac_inventory=_mac_inventory(),
        observed_at=OBSERVED_AT,
    )
    row = next(
        item
        for item in result["activations"]
        if item["capability_id"] == "demo_service" and item["machine"] == "pc"
    )
    assert row["artifact_present"] is None
    assert row["drift_codes"] == ["LEDGER_STALE"]


def test_confirm_rolls_back_mirror_packet_and_decisions_together(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "ledger.sqlite")
    with sqlite3.connect(ledger) as conn:
        conn.execute(
            """
            CREATE TRIGGER inject_capability_decision_failure
            BEFORE INSERT ON capability_decisions
            BEGIN
              SELECT RAISE(ABORT, 'injected decision failure');
            END
            """
        )
        conn.commit()

    try:
        reconciler.reconcile_capabilities(
            register_path=_register(tmp_path / "register.json"),
            ledger_path=ledger,
            pc_inventory=_pc_inventory(),
            mac_inventory=_mac_inventory(),
            observed_at=OBSERVED_AT,
            confirm=True,
            receipt_path=tmp_path / "receipt.json",
            attention_path=tmp_path / "attention.json",
        )
    except sqlite3.IntegrityError as exc:
        assert "injected decision failure" in str(exc)
    else:
        raise AssertionError("injected transaction failure did not abort")

    with sqlite3.connect(ledger) as conn:
        assert conn.execute("SELECT count(*) FROM capability_activations").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM capability_reconciliation_runs").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM capability_decisions").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM events WHERE event_type='capability_reconciliation'").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM packets WHERE intent_name='capability_reconciliation'").fetchone()[0] == 0


def test_reconciler_self_registers_on_existing_refresh_owner() -> None:
    payload = activation_gate_register.build_activation_gate_register()
    row = next(
        item
        for item in payload["capabilities"]
        if item["capability_id"] == "capability_ledger_reconciler"
    )
    assert row["gate_stage"] == "operator_approved_live"
    assert row["activation_allowed_now"] is False
    assert "refresh_ledger_knowledge.py --confirm" in " ".join(row["flag_or_config"])
    assert "capability_ledger_reconciler.py" in row["source_files"]
    assert "tests/test_capability_ledger_reconciler.py" in row["tests"]


def test_unset_live_variable_does_not_inherit_all_inspected_services() -> None:
    capability = {
        "capability_id": "intentionally_off_demo",
        "display_name": "Intentionally off demo",
        "gate_stage": "intentionally_off",
        "owner": "Guardian",
        "last_verified_at": OBSERVED_AT,
        "source_files": [],
        "flag_or_config": ["OPENCLAW_INTENTIONALLY_OFF_DEMO"],
        "live_production_state": "unset_default_off",
        "live_state": {
            "status": "unset_default_off",
            "findings": [
                {
                    "source_type": "reconciliation_summary",
                    "redacted_value_category": "unset",
                    "source_ref": "/home/openclaw/.config/systemd/user/demo.service",
                }
            ],
        },
        "canary_status": "not run",
    }
    row = reconciler._registered_pc_row(
        capability,
        inventory=_pc_inventory(),
        file_inventory={"available": False, "stale": False},
        observed_at=OBSERVED_AT,
    )
    assert row["configured"] is False
    assert row["runtime_confirmed"] is False
    assert row["runtime_state"] == "dark"
    assert "systemd:demo.service" not in row["evidence_refs"]
