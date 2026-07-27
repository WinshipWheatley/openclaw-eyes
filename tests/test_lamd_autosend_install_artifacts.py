from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shipped_scope_template_is_unarmed_and_operator_stopped() -> None:
    payload = json.loads(
        (ROOT / "config/lamd_autosend_scope.unarmed.json").read_text(encoding="utf-8")
    )
    assert payload == {
        "schema_version": "lamd_autosend_scope_v1",
        "armed": False,
        "operator_stop": True,
        "client_ref": "live_arts_md",
        "stream": "speaker_rental",
        "amount_minor_units": 10000,
        "currency": "USD",
        "recipient": "Accountant@liveartsmd.org",
        "cadence_day": 16,
        "standing_authority_ref": "operator-terminal-grant:lamd-monthly-autosend:2026-07-18",
        "authority_source_ref": "/home/openclaw/Operator/to-codex/OPUS-ARM-LAMD-MONTHLY-AUTOSEND-20260718.md",
    }


def test_service_is_exact_runner_only_and_timer_is_daily_persistent() -> None:
    service = (ROOT / "systemd/system/openclaw-lamd-monthly-autosend.service.in").read_text()
    timer = (ROOT / "systemd/system/openclaw-lamd-monthly-autosend.timer").read_text()
    assert "User=openclaw" in service
    assert "lamd_monthly_autosend_runner.py --execute" in service
    assert "OPENCLAW_ATTACHMENT_ALLOWED_DIRS=/mnt/e/openclaw/artifacts/invoice_workbooks/live_arts_md" in service
    assert "NoNewPrivileges=true" in service
    assert "Type=oneshot" in service
    assert "OnCalendar=*-*-* 09:00:00 America/New_York" in timer
    assert "Persistent=true" in timer
    assert "Unit=openclaw-lamd-monthly-autosend.service" in timer


def test_units_writing_under_run_declare_runtimedirectory() -> None:
    """A unit that needs a /run path must create it, because /run is tmpfs.

    Class-level guard, not a spot fix. /run is wiped on every boot, so an
    install-time mkdir survives only until the first reboot. After that,
    ProtectSystem=strict cannot set up ReadWritePaths for a path that no longer
    exists and the unit dies 226/NAMESPACE on every start. With Restart=on-failure
    that is a silent permanent crash loop: the brake broker logged 35,744 restarts
    in a single boot on 2026-07-26 while appearing merely "activating", so nothing
    ever surfaced it. Any unit naming a /run path under ReadWritePaths must also
    declare RuntimeDirectory so systemd recreates it at every start.
    """
    offenders = []
    for unit in sorted((ROOT / "systemd/system").glob("*.in")):
        text = unit.read_text(encoding="utf-8")
        rw_lines = [
            line
            for line in text.splitlines()
            if line.startswith("ReadWritePaths=") and "/run/" in line
        ]
        if not rw_lines:
            continue
        if "RuntimeDirectory=" not in text:
            offenders.append(unit.name)
    assert not offenders, (
        "these units reference a /run path but never create it, so they break on "
        f"the first reboot: {offenders}"
    )


def test_brake_unit_recreates_its_runtime_dir_every_boot() -> None:
    unit = (ROOT / "systemd/system/openclaw-lamd-autosend-brake.service.in").read_text()
    assert "RuntimeDirectory=openclaw-authority" in unit
    # 0755 is the installer's own declared contract for this directory; the socket
    # itself is separately root:<socket-gid> 0660 inside it.
    assert "RuntimeDirectoryMode=0755" in unit
    # openclaw-contained-observe.service also writes under /run/openclaw-authority,
    # so the directory must outlive a stop of this unit.
    assert "RuntimeDirectoryPreserve=yes" in unit
    installer = (ROOT / "scripts/install_lamd_autosend_brake_linux.sh").read_text()
    assert "install -d -o root -g root -m 0755 \"$run_root\"" in installer


def test_installer_installs_but_does_not_enable_monthly_timer() -> None:
    installer = (ROOT / "scripts/install_lamd_autosend_brake_linux.sh").read_text()
    assert "lamd_autosend_scope.unarmed.json" in installer
    assert "openclaw-lamd-monthly-autosend.service" in installer
    assert "openclaw-lamd-monthly-autosend.timer" in installer
    assert "enable --now openclaw-lamd-autosend-brake.service" in installer
    assert "enable --now openclaw-lamd-monthly-autosend.timer" not in installer
