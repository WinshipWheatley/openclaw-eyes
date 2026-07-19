from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "systemd" / "user" / "openclaw-fleet-wake-v2b@.service.in"
PATH_UNIT = ROOT / "systemd" / "user" / "openclaw-fleet-wake-v2b@.path.in"
RUNBOOK = ROOT / "docs" / "operations" / "FLEET_WAKE_NOTIFY_V2B.md"


def test_service_is_finite_and_path_is_event_driven() -> None:
    service = SERVICE.read_text(encoding="utf-8")
    path_unit = PATH_UNIT.read_text(encoding="utf-8")

    assert "fleet_coordination_watcher.py --once" in service
    assert "--settle-seconds 5" in service
    assert "TimeoutStartSec=35min" in service
    assert "Restart=" not in service
    assert "PathChanged=@INBOUND_DIR@" in path_unit
    assert "PathChanged=@WAKE_DIR@" in path_unit
    assert "OnUnitActiveSec" not in path_unit
    assert "OnCalendar" not in path_unit
    assert "Timer" not in path_unit


def test_runbook_has_each_seat_bootstrap_and_exact_rollback() -> None:
    source = RUNBOOK.read_text(encoding="utf-8")

    for seat in (
        "PC-Sol",
        "Mac-Sol-Desktop",
        "Mac-Sol-VSCode",
        "Mac-Fable",
        "Gemini",
        "Opus",
    ):
        assert f"## {seat}" in source
    assert "019f7780-d5f8-76b0-9dde-ead4bf0735f4" in source
    assert "/Volumes/openclaw_e" in source
    assert "midturn: unsupported" in source
    assert "no model polling" in source.lower()
    assert "no model heartbeat" in source.lower()
    assert "mid-turn activation is blocked" in source
    assert "systemctl --user disable --now 'openclaw-fleet-wake-v2b@PC-Sol.path'" in source
    assert "Installation is not performed by this build" in source


def test_production_delivery_has_no_abort_or_process_kill_path() -> None:
    sources = "\n".join(
        (ROOT / name).read_text(encoding="utf-8")
        for name in (
            "codex_app_server_control.py",
            "fleet_coordination_watcher.py",
            "codex_note_event_wake.py",
        )
    )

    assert "turn/" + "interrupt" not in sources
    assert ".kill(" not in sources
    assert ".terminate(" not in sources


def test_build_did_not_install_the_new_units() -> None:
    installed = Path.home() / ".config" / "systemd" / "user"

    assert not (installed / "openclaw-fleet-wake-v2b@.service").exists()
    assert not (installed / "openclaw-fleet-wake-v2b@PC-Sol.path").exists()
