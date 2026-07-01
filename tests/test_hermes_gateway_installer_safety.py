from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "scripts" / "install_hermes_gateway_service.sh"
TEMPLATE = REPO_ROOT / "systemd" / "user" / "hermes-gateway.service.in"
PRESTART_HELPER = REPO_ROOT / "scripts" / "hermes_prestart_kill.py"
STACK_INSTALLER = REPO_ROOT / "scripts" / "install_openclaw_stack.sh"
LEGACY_LAUNCHERS = (
    REPO_ROOT / "scripts" / "start_all.sh",
    REPO_ROOT / "start_chief.sh",
    REPO_ROOT / "start_openclaw_brains.sh",
)
VALIDATION_MAP = REPO_ROOT / "docs" / "testing" / "VALIDATION_MAP.md"


def _installer_text() -> str:
    return INSTALLER.read_text(encoding="utf-8")


def _template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def test_default_and_explicit_dry_run_are_non_mutating_report_modes():
    source = _installer_text()

    assert "if (($# == 0)); then" in source
    assert "dry_run=1" in source
    assert "--dry-run" in source
    assert "report_plan" in source
    assert "No files will be written and no service commands will be run." in source
    assert "if (( dry_run )); then" in source
    assert re.search(r"report_plan\s+exit 0", source)
    assert "--dry-run cannot be combined with --apply or --restart" in source


def test_unknown_flags_fail_closed_with_usage():
    source = _installer_text()

    assert "ERROR: unknown argument:" in source
    assert "usage >&2" in source
    assert "exit 2" in source
    assert "Unknown\nor ambiguous flag combinations fail closed." in source


def test_apply_gates_install_daemon_reload_and_verification():
    source = _installer_text()

    assert "--apply     Render/install only hermes-gateway.service" in source
    assert "apply_changes=1" in source
    assert "if (( ! apply_changes )); then" in source
    assert "ERROR: --apply is required for Hermes gateway installer mutation." in source
    assert source.index("if (( dry_run )); then") < source.index("if (( ! apply_changes )); then")
    assert source.index("if (( ! apply_changes )); then") < source.index("mkdir -p \"${USER_UNIT_DIR}\"")
    assert source.index("if (( ! apply_changes )); then") < source.index("mktemp \"${USER_UNIT_DIR}/${UNIT_NAME}.tmp.XXXXXX\"")
    assert source.index("if (( ! apply_changes )); then") < source.index("mv \"${tmp_unit}\" \"${INSTALLED_UNIT}\"")
    assert source.index("if (( ! apply_changes )); then") < source.index("\nsystemctl --user daemon-reload")
    assert source.index("if (( ! apply_changes )); then") < source.index("\nverify_required_flags \"${INSTALLED_UNIT}\"")


def test_restart_requires_apply_and_is_constrained_to_hermes_gateway_only():
    source = _installer_text()

    assert "UNIT_NAME=\"hermes-gateway.service\"" in source
    assert "if (( restart_service && ! apply_changes )); then" in source
    assert "ERROR: --restart requires --apply." in source
    assert "systemctl --user restart \"${UNIT_NAME}\"" in source
    assert "Restarting only %s" in source
    assert "openclaw-stack.target" not in source


def test_no_enable_start_or_broad_unit_discovery_exists():
    source = _installer_text()

    assert "--enable" not in source
    assert "--start" not in source
    assert "systemctl --user enable" not in source
    assert "systemctl --user start" not in source
    assert "enable --now" not in source
    assert "find " not in source
    assert "*.service" not in source
    assert "for template in" not in source


def test_installer_renders_only_the_hermes_gateway_template():
    source = _installer_text()

    assert "TEMPLATE_PATH=\"${REPO_ROOT}/systemd/user/hermes-gateway.service.in\"" in source
    assert "UNIT_NAME=\"hermes-gateway.service\"" in source
    assert "INSTALLED_UNIT=\"${USER_UNIT_DIR}/${UNIT_NAME}\"" in source
    assert "Render only systemd/user/hermes-gateway.service.in" in source
    assert "Environment=HERMES_OPENCLAW_MODE=gateway" in source
    assert "Environment=HERMES_OPENCLAW_GATEWAY=1" in source
    assert "Environment=HERMES_OPENCLAW_DISABLE_EXTERNAL_FALLBACK=1" in source


def test_template_enforces_gateway_sidecar_contract():
    source = _template_text()

    assert "Description=OpenClaw Hermes Gateway" in source
    assert "WorkingDirectory=@REPO_ROOT@" in source
    assert "Environment=HERMES_HOME=@REPO_ROOT@/sidecars/hermes_home" in source
    assert "Environment=HERMES_OPENCLAW_MODE=gateway" in source
    assert "Environment=HERMES_OPENCLAW_GATEWAY=1" in source
    assert "Environment=HERMES_OPENCLAW_DISABLE_EXTERNAL_FALLBACK=1" in source
    assert "scripts/run_openclaw_hermes_gateway.py" in source
    assert "run_openclaw_hermes_gateway.py --replace" in source
    assert "provider" not in source.lower()
    assert "gmail" not in source.lower()
    assert "telegram" in source.lower()


def test_template_prestart_helper_is_committed_and_pid_targeted():
    source = _template_text()
    assert "ExecStartPre=-/usr/bin/python3 @REPO_ROOT@/scripts/hermes_prestart_kill.py" in source

    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "scripts/hermes_prestart_kill.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    helper = PRESTART_HELPER.read_text(encoding="utf-8")
    assert 'TARGET_MARKER = "run_openclaw_hermes_gateway.py"' in helper
    assert "gateway.pid" in helper
    assert "TARGET_MARKER not in cmdline" in helper
    assert "os.kill(pid, signal.SIGTERM)" in helper
    assert "subprocess." not in helper
    assert "os.system" not in helper
    assert "pgrep(" not in helper
    assert "pkill(" not in helper


def test_stack_installer_and_legacy_launchers_remain_out_of_scope():
    stack_source = STACK_INSTALLER.read_text(encoding="utf-8")
    assert "Hermes gateway remains managed by scripts/install_hermes_gateway_service.sh" in stack_source
    assert '"${unit_name}" != "hermes-gateway.service"' in stack_source

    for path in LEGACY_LAUNCHERS:
        source = path.read_text(encoding="utf-8")
        assert "install_hermes_gateway_service.sh" not in source
        assert "hermes-gateway.service" not in source


def test_validation_map_indexes_hermes_gateway_installer_safety_test():
    source = VALIDATION_MAP.read_text(encoding="utf-8")

    assert "scripts/install_hermes_gateway_service.sh" in source
    assert "systemd/user/hermes-gateway.service.in" in source
    assert "tests/test_hermes_gateway_installer_safety.py" in source
