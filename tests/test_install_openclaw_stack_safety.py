from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "scripts" / "install_openclaw_stack.sh"
FREEZE_DOC = REPO_ROOT / "docs" / "operations" / "OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md"
REQUEST_RESPONSE_UNIT = REPO_ROOT / "systemd" / "user" / "openclaw-request-response.service.in"
GUARDIAN_UNIT = REPO_ROOT / "systemd" / "user" / "chief-guardian-listener.service.in"
CASSANDRA_WATCHER_UNIT = REPO_ROOT / "systemd" / "user" / "cassandra-watcher.service.in"


def _installer_text() -> str:
    return INSTALLER.read_text(encoding="utf-8")


def _freeze_text() -> str:
    return FREEZE_DOC.read_text(encoding="utf-8")


def test_default_and_explicit_dry_run_are_non_mutating_report_modes():
    source = _installer_text()

    assert "if (($# == 0)); then" in source
    assert "dry_run=1" in source
    assert "--dry-run" in source
    assert "report_plan" in source
    assert "No files will be written and no service commands will be run." in source
    assert "if (( dry_run )); then" in source
    assert "report_plan\n    exit 0" in source
    assert "--dry-run cannot be combined with --apply, --enable, or --start" in source


def test_unknown_flags_fail_closed_with_usage():
    source = _installer_text()

    assert "ERROR: unknown argument:" in source
    assert "usage >&2" in source
    assert "exit 2" in source
    assert "Unknown or ambiguous flag combinations fail closed." in source


def test_apply_gates_rendering_and_daemon_reload():
    source = _installer_text()

    assert "--apply     Render/install repo-owned units and run systemctl --user daemon-reload only." in source
    assert "apply_changes=1" in source
    assert "if (( dry_run )); then" in source
    assert source.index("if (( dry_run )); then") < source.index("mkdir -p \"${USER_UNIT_DIR}\"")
    assert source.index("if (( dry_run )); then") < source.index("\nsystemctl --user daemon-reload")
    assert "Ran systemctl --user daemon-reload after rendering repo-owned units." in source


def test_enable_requires_apply_and_is_constrained_to_repo_owned_openclaw_services():
    source = _installer_text()

    assert "if (( enable_units && ! apply_changes )); then" in source
    assert "ERROR: --enable requires --apply." in source
    assert "repo_owned_service_names=()" in source
    assert '[[ "${unit_name}" == *.service && "${unit_name}" != "hermes-gateway.service" ]]' in source
    assert "for service_name in \"${repo_owned_service_names[@]}\"; do" in source
    assert "systemctl --user enable \"${service_name}\"" in source
    assert "Enabled repo-owned service:" in source


def test_start_requires_apply_and_enable_and_targets_only_stack_target():
    source = _installer_text()

    assert "TARGET_NAME=\"openclaw-stack.target\"" in source
    assert "if (( start_target && (! apply_changes || ! enable_units) )); then" in source
    assert "ERROR: --start requires --apply and --enable." in source
    assert "systemctl --user enable --now \"${TARGET_NAME}\"" in source
    assert "Enabled and started only %s." in source
    assert re.search(r"systemctl --user (restart|start) ", source) is None


def test_broad_enablement_of_every_installed_user_service_is_absent():
    source = _installer_text()

    forbidden_patterns = (
        "find \"${USER_UNIT_DIR}\" -maxdepth 1 -name \"*.service\" -exec systemctl --user enable",
        "find ${USER_UNIT_DIR} -maxdepth 1 -name '*.service' -exec systemctl --user enable",
        "systemctl --user enable {} +",
    )
    for pattern in forbidden_patterns:
        assert pattern not in source
    assert "repo_owned_service_names" in source


def test_hermes_behavior_is_not_broadened_by_stack_installer():
    source = _installer_text()

    assert "hermes-gateway.service" in source
    assert "Hermes gateway remains managed by scripts/install_hermes_gateway_service.sh" in source
    assert '"${unit_name}" != "hermes-gateway.service"' in source
    assert "systemctl --user restart" not in source


@pytest.mark.parametrize("unit", (GUARDIAN_UNIT, CASSANDRA_WATCHER_UNIT))
def test_voice_capable_guardian_and_cassandra_watcher_are_cpu_pinned(unit: Path):
    source = unit.read_text(encoding="utf-8")

    assert source.count("Environment=CUDA_VISIBLE_DEVICES=") == 1


def test_legacy_launchers_remain_slice_4_out_of_scope():
    freeze = _freeze_text()
    source = _installer_text()

    assert "Slice 4: deprecate or guard legacy launch scripts." in freeze
    for script_name in ("scripts/start_all.sh", "start_chief.sh", "start_openclaw_brains.sh"):
        assert script_name in freeze
        assert script_name not in source


def test_request_response_service_template_is_bounded_and_operator_activated():
    source = REQUEST_RESPONSE_UNIT.read_text(encoding="utf-8")

    assert "scripts/run_openclaw_request_response_service.py" in source
    assert "--watch-seconds 21600" in source
    assert "--watch-seconds 300" not in source
    assert "--max-requests 100" in source
    assert "ConditionPathIsDirectory=/mnt/e/openclaw/mission_control_capture_requests/inbox" in source
    assert "ConditionPathIsDirectory=/mnt/e/openclaw/mission_control_responses/to_mac" in source
    assert "NoNewPrivileges=true" in source
    assert "WantedBy=openclaw-stack.target" in source
    assert "Gmail" not in source
    assert "Coupa" not in source
