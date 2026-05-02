from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATHS = {
    "start_all": REPO_ROOT / "scripts" / "start_all.sh",
    "start_chief": REPO_ROOT / "start_chief.sh",
    "start_openclaw_brains": REPO_ROOT / "start_openclaw_brains.sh",
}
INSTALLER_PATHS = (
    REPO_ROOT / "scripts" / "install_openclaw_stack.sh",
    REPO_ROOT / "scripts" / "install_hermes_gateway_service.sh",
)
VALIDATION_MAP = REPO_ROOT / "docs" / "testing" / "VALIDATION_MAP.md"


def _script_text(name: str) -> str:
    return SCRIPT_PATHS[name].read_text(encoding="utf-8")


def test_legacy_launchers_default_to_report_only_dry_run():
    for source in (_script_text(name) for name in SCRIPT_PATHS):
        assert "if (($# == 0)); then" in source
        assert "dry_run=1" in source
        assert "--dry-run" in source
        assert "report_refusal" in source
        assert "No live" in source
        assert "if (( dry_run )); then" in source
        assert re.search(r"report_refusal\s+exit 0", source)


def test_legacy_launchers_fail_closed_on_unknown_flags():
    for source in (_script_text(name) for name in SCRIPT_PATHS):
        assert "ERROR: unknown argument:" in source
        assert "usage >&2" in source
        assert "exit 2" in source


def test_mode_validation_precedes_any_reported_refusal():
    for source in (_script_text(name) for name in SCRIPT_PATHS):
        assert source.index("while (($#)); do") < source.index("report_refusal()")


def test_start_all_refuses_full_stack_restart_without_preserved_live_path():
    source = _script_text("start_all")

    assert "Slice 4 legacy launcher refusal: scripts/start_all.sh" in source
    assert "broad restart of openclaw-stack.target" in source
    assert "No live execution flags are available for this script in Slice 4" in source
    assert "later explicit ownership decision" in source
    assert "systemctl" not in source
    assert "ps aux" not in source
    assert "bash \"${REPO_ROOT}/start_openclaw_brains.sh\"" not in source
    assert "REPO_ROOT=" not in source


def test_start_chief_refuses_private_and_duplicate_runtime_surfaces():
    source = _script_text("start_chief")

    assert "Slice 4 legacy launcher refusal: start_chief.sh" in source
    assert "private environment loading" in source
    assert "process termination of systemd-owned listeners/workers" in source
    assert "unmanaged duplicate listener/worker startup" in source
    assert "No live execution flags are available for this script in Slice 4" in source
    assert "later explicit ownership decision" in source

    for forbidden in (
        ".chief.env",
        "/mnt/c/OpenClaw/logs",
        "GUARDIAN_BOT_TOKEN",
        "chief_guardian_listener.py",
        "pkill",
        "nohup",
        "setsid",
        "source ",
        "runner_registry.py",
    ):
        assert forbidden not in source


def test_start_openclaw_brains_refuses_legacy_poller_mutation_until_slice_8():
    source = _script_text("start_openclaw_brains")

    assert "Slice 4 legacy launcher refusal: start_openclaw_brains.sh" in source
    assert "poller ownership is deferred to Slice 8" in source
    assert "Slice 8 decides" in source
    assert "No live poller execution flags are available for this script in Slice 4" in source
    assert "pkill" not in source
    assert "setsid" not in source
    assert "source " not in source
    assert "/tmp/chief_album_brain.log" not in source
    assert "/tmp/chief_billing_brain.log" not in source


def test_installers_remain_out_of_scope_for_legacy_launcher_hardening():
    for path in INSTALLER_PATHS:
        source = path.read_text(encoding="utf-8")
        assert "Slice 4 legacy launcher refusal" not in source
        assert "start_chief.sh" not in source
        assert "start_openclaw_brains.sh" not in source


def test_validation_map_indexes_legacy_launcher_safety_test():
    source = VALIDATION_MAP.read_text(encoding="utf-8")

    assert "scripts/start_all.sh" in source
    assert "start_chief.sh" in source
    assert "start_openclaw_brains.sh" in source
    assert "tests/test_legacy_launch_script_safety.py" in source