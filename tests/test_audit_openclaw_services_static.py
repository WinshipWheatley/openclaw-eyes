from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_openclaw_services.sh"
HERMES_INSTALL_SCRIPT = ROOT / "scripts" / "install_hermes_gateway_service.sh"
REQUEST_RESPONSE_UNIT_TEMPLATE = ROOT / "systemd" / "user" / "openclaw-request-response.service.in"


def test_audit_script_has_valid_bash_syntax() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_hermes_gateway_installer_has_valid_bash_syntax() -> None:
    subprocess.run(["bash", "-n", str(HERMES_INSTALL_SCRIPT)], check=True)


def _executable_lines(source: str) -> list[str]:
    lines: list[str] = []
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def test_audit_script_does_not_execute_service_or_process_mutations() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    command_source = "\n".join(_executable_lines(source))

    forbidden_lifecycle = re.compile(
        r"(^|[;&|({]\s*)systemctl\b[^\n#]*\b"
        r"(start|stop|restart|reload|enable|disable|daemon-reload|reset-failed)\b",
        re.MULTILINE,
    )
    forbidden_commands = re.compile(
        r"(^|[;&|({]\s*)"
        r"(pkill|kill|killall|nohup|journalctl|rm|mv|cp|ln|chmod|chown|tee)\b",
        re.MULTILINE,
    )

    assert not forbidden_lifecycle.search(command_source)
    assert not forbidden_commands.search(command_source)
    assert "systemctl --user list-unit-files" in command_source


def test_hermes_gateway_installer_is_single_unit_and_no_broad_stack_control() -> None:
    source = HERMES_INSTALL_SCRIPT.read_text(encoding="utf-8")
    command_source = "\n".join(_executable_lines(source))

    assert "systemd/user/hermes-gateway.service.in" in source
    assert "${HOME}/.config/systemd/user" in source
    assert "systemctl --user daemon-reload" in command_source
    assert 'systemctl --user restart "${UNIT_NAME}"' in command_source

    assert "for template in" not in command_source
    assert "install_openclaw_stack.sh" not in command_source
    assert "systemctl --user enable" not in command_source
    assert "systemctl --user start" not in command_source
    assert "systemctl --user stop" not in command_source
    assert "systemctl --user disable" not in command_source
    assert "systemctl --user enable --now" not in command_source
    assert "openclaw-stack.target" not in command_source
    assert "chief-" not in command_source
    assert "cassandra-" not in command_source
    assert "guardian" not in command_source.lower()


def test_hermes_gateway_installer_verifies_required_openclaw_flags() -> None:
    source = HERMES_INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert "Environment=HERMES_OPENCLAW_MODE=gateway" in source
    assert "Environment=HERMES_OPENCLAW_GATEWAY=1" in source
    assert "Environment=HERMES_OPENCLAW_DISABLE_EXTERNAL_FALLBACK=1" in source
    assert "verify_required_flags" in source
    assert "grep -Fq" in source


def test_request_response_service_uses_long_bounded_watch_window() -> None:
    source = REQUEST_RESPONSE_UNIT_TEMPLATE.read_text(encoding="utf-8")

    assert "--watch-seconds 21600" in source
    assert "--watch-seconds 300" not in source
    assert "Restart=always" in source
    assert "run_openclaw_request_response_service.py" in source


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _snapshot_tree(root: Path) -> dict[str, tuple[str, bytes | str | None]]:
    snapshot: dict[str, tuple[str, bytes | str | None]] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            snapshot[rel] = ("symlink", os.readlink(path))
        elif path.is_file():
            snapshot[rel] = ("file", path.read_bytes())
        elif path.is_dir():
            snapshot[rel] = ("dir", None)
    return snapshot


def test_audit_script_reports_expected_read_only_findings(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    template_dir = repo / "systemd" / "user"
    installed_dir = repo / ".config" / "systemd" / "user"
    stack_wants = installed_dir / "openclaw-stack.target.wants"
    default_wants = installed_dir / "default.target.wants"
    timer_wants = installed_dir / "timers.target.wants"

    for directory in (template_dir, installed_dir, stack_wants, default_wants, timer_wants):
        directory.mkdir(parents=True, exist_ok=True)

    _write(
        template_dir / "chief-listener.service.in",
        "[Unit]\nDescription=Chief Listener\n[Service]\nWorkingDirectory=@REPO_ROOT@\n",
    )
    _write(
        installed_dir / "chief-listener.service",
        f"[Unit]\nDescription=Chief Listener\n[Service]\nWorkingDirectory={repo}\n",
    )

    _write(
        template_dir / "hermes-gateway.service.in",
        "[Unit]\nDescription=Hermes Gateway\n[Service]\nWorkingDirectory=@REPO_ROOT@/sidecars/hermes\n",
    )
    _write(
        installed_dir / "hermes-gateway.service",
        f"[Unit]\nDescription=Hermes Gateway\n[Service]\nWorkingDirectory={repo}/different-hermes\n",
    )

    _write(installed_dir / "openclaw-gateway.service", "[Unit]\nDescription=Gateway\n")
    _write(installed_dir / "openclaw-drift-control-scan.service", "[Unit]\nDescription=Drift scan\n")
    _write(installed_dir / "openclaw-drift-control-scan.timer", "[Timer]\nOnCalendar=hourly\n")
    _write(installed_dir / "random-editor.service", "[Unit]\nDescription=Unrelated\n")
    _write(installed_dir / "openclaw-gateway.service.bak", "backup\n")

    for unit in (
        "chief-listener.service",
        "hermes-gateway.service",
        "openclaw-drift-control-scan.timer",
    ):
        os.symlink(installed_dir / unit, stack_wants / unit)
    os.symlink(installed_dir / "openclaw-gateway.service", default_wants / "openclaw-gateway.service")
    os.symlink(
        installed_dir / "openclaw-drift-control-scan.timer",
        timer_wants / "openclaw-drift-control-scan.timer",
    )

    _write(
        repo / ".openclaw" / "cron" / "jobs.json",
        '{"jobs":[{"id":"drift-control-scan","command":"python3 /home/openclaw/drift_control_scanner.py --scan"}]}\n',
    )

    for frozen_path in (
        "scripts/start_all.sh",
        "start_chief.sh",
        "start_openclaw_brains.sh",
        "scripts/install_openclaw_stack.sh",
    ):
        _write(repo / frozen_path, "#!/usr/bin/env bash\n")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_systemctl = fake_bin / "systemctl"
    _write(
        fake_systemctl,
        "#!/usr/bin/env bash\n"
        "if [[ $1 == --user && $2 == list-unit-files ]]; then\n"
        "  printf 'UNIT FILE STATE PRESET\\n'\n"
        "  exit 0\n"
        "fi\n"
        "printf 'unexpected systemctl invocation: %s\\n' \"$*\" >&2\n"
        "exit 42\n",
    )
    fake_systemctl.chmod(fake_systemctl.stat().st_mode | stat.S_IXUSR)

    before = _snapshot_tree(repo)
    env = os.environ.copy()
    env["OPENCLAW_REPO_ROOT"] = str(repo)
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    completed = subprocess.run(
        [str(SCRIPT)],
        check=False,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    output = completed.stdout
    assert "WARN  installed_only openclaw-gateway.service" in output
    assert "WARN  installed_only openclaw-drift-control-scan.service" in output
    assert "WARN  installed_only openclaw-drift-control-scan.timer" in output
    assert "WARN  known_mismatch hermes-gateway.service" in output
    assert "WARN  frozen_control scripts/start_all.sh" in output
    assert "WARN  frozen_control start_chief.sh" in output
    assert "WARN  frozen_control start_openclaw_brains.sh" in output
    assert "WARN  frozen_control scripts/install_openclaw_stack.sh" in output
    assert "WARN  dual_scheduler_risk" in output
    assert "random-editor.service" not in output
    assert _snapshot_tree(repo) == before
