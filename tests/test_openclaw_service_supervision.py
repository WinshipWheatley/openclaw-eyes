import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_service_supervision as supervision
from scripts.export_openclaw_service_supervision import main as export_main


FIXED_NOW = "2026-05-31T04:00:00+00:00"


def _unit(
    name: str,
    *,
    active_state: str = "active",
    sub_state: str = "running",
    enabled: bool = True,
    readiness: str = "READY",
) -> dict:
    return {
        "unit_name": name,
        "unit_kind": "TIMER" if name.endswith(".timer") else "SERVICE",
        "systemd_available": True,
        "load_state": "loaded",
        "active_state": active_state,
        "sub_state": sub_state,
        "unit_file_state": "enabled" if enabled else "static",
        "enabled_status": "enabled" if enabled else "static",
        "enabled": enabled,
        "active": active_state == "active",
        "unit_path": f"/home/openclaw/.config/systemd/user/{name}",
        "last_start_time": "Sun 2026-05-31 04:00:00 EDT",
        "restart_count": "0",
        "exec_main_status": "0",
        "result": "success",
        "timer_settings": {},
        "log_excerpt_summary": "Started test unit.",
        "expected_behavior": "test behavior",
        "startup_readiness": readiness,
        "readiness_reason": "Unit matches expected supervision state.",
        "allowed_supervision_action": "START_IF_INACTIVE_ALLOWLISTED",
        "recommended_operator_action": "No operator action required.",
    }


def _ready_units() -> list[dict]:
    return [
        _unit("openclaw-request-response.service"),
        _unit("openclaw-change-sentinel.timer", sub_state="waiting"),
        _unit("openclaw-change-sentinel.service", active_state="inactive", sub_state="dead", enabled=False),
        _unit("openclaw-service-keeper.timer", sub_state="waiting"),
        _unit("openclaw-service-keeper.service", active_state="inactive", sub_state="dead", enabled=False),
        _unit("openclaw-sleep-resilience.service"),
    ]


def _linger() -> dict:
    return {"user": "openclaw", "linger": "yes", "status": "READY", "error": ""}


def test_supervision_read_model_reports_enabled_active_units(tmp_path):
    payload = supervision.build_openclaw_service_supervision(
        read_model_root=tmp_path,
        generated_at=FIXED_NOW,
        unit_rows=_ready_units(),
        linger_status=_linger(),
    )

    assert payload["startup_readiness"] == "READY"
    assert payload["boot_persistence_state"] == "READY"
    assert payload["core_monitor_status"]["request_response_active"] is True
    assert payload["core_monitor_status"]["sentinel_timer_active"] is True
    assert payload["risk_count"] == 0


def test_supervision_reports_service_keeper_timer_state(tmp_path):
    payload = supervision.build_openclaw_service_supervision(
        read_model_root=tmp_path,
        generated_at=FIXED_NOW,
        unit_rows=_ready_units(),
        linger_status=_linger(),
    )

    assert payload["core_monitor_status"]["service_keeper_timer_active"] is True
    keeper_unit = {
        row["unit_name"]: row for row in payload["supervised_units"]
    }["openclaw-service-keeper.timer"]
    assert keeper_unit["startup_readiness"] == "READY"


def test_supervision_reports_sleep_resilience_service_state(tmp_path):
    payload = supervision.build_openclaw_service_supervision(
        read_model_root=tmp_path,
        generated_at=FIXED_NOW,
        unit_rows=_ready_units(),
        linger_status=_linger(),
    )

    sleep_unit = {
        row["unit_name"]: row for row in payload["supervised_units"]
    }["openclaw-sleep-resilience.service"]
    assert sleep_unit["startup_readiness"] == "READY"


def test_linger_disabled_marks_boot_persistence_risk(tmp_path):
    payload = supervision.build_openclaw_service_supervision(
        read_model_root=tmp_path,
        generated_at=FIXED_NOW,
        unit_rows=_ready_units(),
        linger_status={"user": "openclaw", "linger": "no", "status": "RISK_LINGER_DISABLED", "error": ""},
    )

    assert payload["boot_persistence_state"] == "RISK_LINGER_DISABLED"


def test_export_writes_json_operator_sqlite_schema_seed(tmp_path, capsys):
    read_root = tmp_path / "generated" / "read_models"
    system_root = tmp_path / "generated" / "system_knowledge"
    result = supervision.export_openclaw_service_supervision(
        read_model_root=read_root,
        system_knowledge_root=system_root,
        generated_at=FIXED_NOW,
        unit_rows=_ready_units(),
        linger_status=_linger(),
    )

    json_path = read_root / supervision.JSON_EXPORT_NAME
    sqlite_path = system_root / supervision.SQLITE_EXPORT_NAME
    assert result.startup_readiness == "READY"
    assert json.loads(json_path.read_text(encoding="utf-8"))["schema_version"] == supervision.READ_MODEL_VERSION
    assert (read_root / supervision.OPERATOR_EXPORT_NAME).exists()
    assert (system_root / supervision.SCHEMA_EXPORT_NAME).exists()
    assert (system_root / supervision.SEED_EXPORT_NAME).exists()

    connection = sqlite3.connect(sqlite_path)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert set(supervision.REQUIRED_SQLITE_TABLES).issubset(tables)
    finally:
        connection.close()

    assert export_main(
        [
            "--read-model-root",
            str(read_root),
            "--system-knowledge-root",
            str(system_root),
            "--no-systemd",
            "--format",
            "json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == supervision.READ_MODEL_VERSION


def test_source_does_not_call_forbidden_live_surfaces():
    source_files = [
        Path("openclaw_service_supervision.py"),
        Path("scripts/export_openclaw_service_supervision.py"),
    ]
    forbidden = [
        "systemctl --user start",
        "systemctl --user restart",
        "systemctl --user enable",
        "git push",
        "openai",
        "anthropic",
        "import requests",
        "import httpx",
        "urllib.request",
        "smtplib",
        "selenium",
        "playwright",
        "pyautogui",
        "openpyxl",
        "shell=True",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for forbidden_text in forbidden:
            assert forbidden_text not in text
