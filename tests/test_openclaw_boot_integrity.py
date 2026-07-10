from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import textwrap

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK = REPO_ROOT / "scripts" / "openclaw_boot_check.sh"
ENABLE = REPO_ROOT / "scripts" / "openclaw_boot_enable.sh"
UNIT = REPO_ROOT / "systemd" / "user" / "openclaw-boot-assert.service.in"
WINDOWS_HOOK = REPO_ROOT / "scripts" / "windows" / "openclaw_boot_check.bat"
RUNBOOK = REPO_ROOT / "docs" / "operations" / "OPENCLAW_BOOT_INTEGRITY.md"


def _executable(path: Path, source: str) -> Path:
    path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8", newline="\n")
    path.chmod(0o755)
    return path


def _fake_systemctl(
    tmp_path: Path,
    *,
    down_unit: str = "",
    down_stays: bool = False,
    disabled_unit: str = "",
    extra_failure: str = "",
) -> Path:
    return _executable(
        tmp_path / "systemctl",
        f"""
        #!/usr/bin/env bash
        set -eu
        printf '%s\n' "$*" >> "{tmp_path / 'systemctl.calls'}"
        args=" $* "
        if [[ "$args" == *" --failed "* ]]; then
          printf '%s\n' 'getty@tty1.service loaded failed failed Getty on tty1'
          {f"printf '%s\\n' '{extra_failure} loaded failed failed injected'" if extra_failure else ":"}
          exit 0
        fi
        if [[ "$args" == *" is-enabled "* ]]; then
          unit="${{@: -1}}"
          if [[ -n "{disabled_unit}" && "$unit" == "{disabled_unit}" ]]; then
            printf '%s\n' disabled
            exit 1
          fi
          printf '%s\n' enabled
          exit 0
        fi
        if [[ "$args" == *" is-active "* ]]; then
          unit="${{@: -1}}"
          if [[ -n "{down_unit}" && "$unit" == "{down_unit}" && ( "{str(down_stays).lower()}" == true || ! -e "{tmp_path / 'started'}.$unit" ) ]]; then
            printf '%s\n' inactive
            exit 3
          fi
          printf '%s\n' active
          exit 0
        fi
        if [[ "$args" == *" start "* ]]; then
          unit="${{@: -1}}"
          : > "{tmp_path / 'started'}.$unit"
          exit 0
        fi
        printf '%s\n' "unexpected systemctl call: $*" >&2
        exit 64
        """,
    )


def _fake_loginctl(tmp_path: Path, *, linger: str = "yes") -> Path:
    return _executable(
        tmp_path / "loginctl",
        f"""
        #!/usr/bin/env bash
        printf '%s\n' "$*" >> "{tmp_path / 'loginctl.calls'}"
        printf '%s\n' {linger}
        """,
    )


def _fake_curl(tmp_path: Path, *, succeeds: bool) -> Path:
    return _executable(
        tmp_path / "curl",
        f"""
        #!/usr/bin/env bash
        printf '%s\n' "$*" >> "{tmp_path / 'curl.calls'}"
        {"printf '%s\\n' '{\"models\":[]}'" if succeeds else "exit 7"}
        """,
    )


def _fake_voice(tmp_path: Path) -> Path:
    return _executable(
        tmp_path / "voice",
        f"""
        #!/usr/bin/env bash
        cat >> "{tmp_path / 'voice.messages'}"
        printf '\n---\n' >> "{tmp_path / 'voice.messages'}"
        """,
    )


def _fake_ps(tmp_path: Path, output: str = "") -> Path:
    return _executable(
        tmp_path / "ps",
        f"""
        #!/usr/bin/env bash
        cat <<'EOF'
        {output}
        EOF
        """,
    )


def _base_env(
    tmp_path: Path,
    *,
    bus_up: bool = True,
    mount_up: bool = True,
    ollama_up: bool = True,
    down_unit: str = "",
    down_stays: bool = False,
    disabled_unit: str = "",
    extra_failure: str = "",
    ps_output: str = "",
) -> dict[str, str]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    bus = tmp_path / "system_bus_socket"
    mount = tmp_path / "e_mount"
    if bus_up:
        bus.touch()
    if mount_up:
        mount.mkdir()
    boot_id = tmp_path / "boot_id"
    boot_id.write_text("boot-fixture-001\n", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "OPENCLAW_BOOT_SYSTEMCTL": str(
                _fake_systemctl(
                    tmp_path,
                    down_unit=down_unit,
                    down_stays=down_stays,
                    disabled_unit=disabled_unit,
                    extra_failure=extra_failure,
                )
            ),
            "OPENCLAW_BOOT_LOGINCTL": str(_fake_loginctl(tmp_path)),
            "OPENCLAW_BOOT_CURL": str(_fake_curl(tmp_path, succeeds=ollama_up)),
            "OPENCLAW_BOOT_VOICE": str(_fake_voice(tmp_path)),
            "OPENCLAW_BOOT_PS": str(_fake_ps(tmp_path, ps_output)),
            "OPENCLAW_BOOT_SYSTEM_BUS": str(bus),
            "OPENCLAW_BOOT_MOUNT": str(mount),
            "OPENCLAW_BOOT_MARKER": str(tmp_path / "boot.marker"),
            "OPENCLAW_BOOT_STATE_DIR": str(tmp_path / "state"),
            "OPENCLAW_BOOT_BOOT_ID": str(boot_id),
            "OPENCLAW_BOOT_CONFLICT_LOG_DIR": str(tmp_path / "logs"),
            "OPENCLAW_BOOT_MAX_ATTEMPTS": "2",
            "OPENCLAW_BOOT_WAIT_BUDGET_SECONDS": "5",
            "OPENCLAW_BOOT_RETRY_SECONDS": "0",
            "OPENCLAW_BOOT_CONFLICT_WINDOW_SECONDS": "0",
            "OPENCLAW_BOOT_SYSTEMD_NOTIFY_GRACE": "0",
        }
    )
    (tmp_path / "logs").mkdir(exist_ok=True)
    return env


def _run(script: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )


def test_enablement_assert_is_verify_only_and_idempotent(tmp_path: Path) -> None:
    env = _base_env(tmp_path)

    first = _run(ENABLE, env)
    second = _run(ENABLE, env)

    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert "linger" in first.stdout
    assert "ollama.service" in first.stdout
    assert "openclaw-boot-assert.service" in first.stdout
    assert "chief-worker.service" in first.stdout
    assert "guardian-approval-notifier.timer" in first.stdout
    assert "openclaw-stack.target" in first.stdout
    assert "SUMMARY drift=0 unknown=0" in first.stdout
    calls = (tmp_path / "systemctl.calls").read_text(encoding="utf-8").splitlines()
    assert calls
    assert all(" start " not in f" {call} " for call in calls)
    assert all(" restart " not in f" {call} " for call in calls)
    assert all(not (" enable " in f" {call} " and " is-enabled " not in f" {call} ") for call in calls)


def test_enablement_dead_bus_is_unknown_not_false_disabled(tmp_path: Path) -> None:
    env = _base_env(tmp_path, bus_up=False)

    result = _run(ENABLE, env)

    assert result.returncode == 2
    assert "system-dbus" in result.stdout
    assert "BUS_UNAVAILABLE" in result.stdout
    assert "UNKNOWN" in result.stdout
    assert "systemctl --user enable" not in result.stdout
    assert not (tmp_path / "systemctl.calls").exists()


def test_enablement_assert_reports_real_drift_without_applying_it(tmp_path: Path) -> None:
    env = _base_env(tmp_path, disabled_unit="chief-worker.service")

    result = _run(ENABLE, env)

    assert result.returncode == 1
    assert "chief-worker.service" in result.stdout
    assert "disabled" in result.stdout
    assert "DRIFT" in result.stdout
    assert "systemctl --user enable chief-worker.service" in result.stdout
    calls = (tmp_path / "systemctl.calls").read_text(encoding="utf-8").splitlines()
    assert all(not call.startswith("--user enable ") for call in calls)


def test_all_green_reports_exact_contract_once_per_boot(tmp_path: Path) -> None:
    env = _base_env(tmp_path)

    first = _run(CHECK, env, "--source", "windows-task")
    second = _run(CHECK, env, "--source", "windows-task")

    assert first.returncode == second.returncode == 0
    expected = "Fleet up after restart: 10/10 services, ollama warm, timers armed."
    assert expected in first.stdout
    marker = (tmp_path / "boot.marker").read_text(encoding="utf-8")
    assert "STATUS=GREEN" in marker
    messages = (tmp_path / "voice.messages").read_text(encoding="utf-8")
    assert messages.count(expected) == 1


def test_concurrent_assertions_still_emit_only_one_boot_message(tmp_path: Path) -> None:
    env = _base_env(tmp_path)
    command = ["bash", str(CHECK), "--source", "user-systemd"]

    first = subprocess.Popen(command, cwd=REPO_ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    second = subprocess.Popen(command, cwd=REPO_ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    first_stdout, first_stderr = first.communicate(timeout=10)
    second_stdout, second_stderr = second.communicate(timeout=10)

    assert first.returncode == second.returncode == 0, first_stderr + second_stderr
    expected = "Fleet up after restart: 10/10 services, ollama warm, timers armed."
    messages = (tmp_path / "voice.messages").read_text(encoding="utf-8")
    assert messages.count(expected) == 1
    assert expected in first_stdout
    assert expected in second_stdout


def test_bus_down_writes_loud_marker_without_touching_units(tmp_path: Path) -> None:
    env = _base_env(tmp_path, bus_up=False)

    result = _run(CHECK, env, "--source", "windows-task")

    assert result.returncode == 2
    assert "RED LINE: WSL system D-Bus is missing" in result.stdout
    assert "wsl --shutdown" in result.stdout
    marker = (tmp_path / "boot.marker").read_text(encoding="utf-8")
    assert "STATUS=RED" in marker
    assert "REMEDY=Run wsl --shutdown from PowerShell once, then reopen Ubuntu-E." in marker
    assert not (tmp_path / "systemctl.calls").exists()


def test_system_bus_is_retried_before_declaring_a_half_boot(tmp_path: Path) -> None:
    env = _base_env(tmp_path, bus_up=False)
    env["OPENCLAW_BOOT_RETRY_SECONDS"] = "1"
    env["OPENCLAW_BOOT_SLEEP"] = str(
        _executable(
            tmp_path / "sleep",
            f"""
            #!/usr/bin/env bash
            : > "{tmp_path / 'system_bus_socket'}"
            """,
        )
    )

    result = _run(CHECK, env)

    assert result.returncode == 0
    assert "Fleet up after restart: 10/10 services" in result.stdout


def test_enabled_but_dead_unit_is_started_never_restarted(tmp_path: Path) -> None:
    env = _base_env(tmp_path, down_unit="chief-listener.service")

    result = _run(CHECK, env)

    assert result.returncode == 0
    calls = (tmp_path / "systemctl.calls").read_text(encoding="utf-8").splitlines()
    assert calls.count("--user --no-block start chief-listener.service") == 1
    assert not any("restart" in call for call in calls)
    assert "Fleet up after restart: 10/10 services" in result.stdout


def test_enabled_auxiliary_worker_also_blocks_green_until_started(tmp_path: Path) -> None:
    env = _base_env(tmp_path, down_unit="chief-worker.service")

    result = _run(CHECK, env)

    assert result.returncode == 0
    calls = (tmp_path / "systemctl.calls").read_text(encoding="utf-8").splitlines()
    assert calls.count("--user --no-block start chief-worker.service") == 1
    assert "Fleet up after restart: 10/10 services" in result.stdout


def test_ollama_down_names_the_failure(tmp_path: Path) -> None:
    env = _base_env(tmp_path, ollama_up=False)

    result = _run(CHECK, env)

    assert result.returncode == 1
    assert "RED LINE: boot integrity incomplete" in result.stdout
    assert "ollama API unavailable" in result.stdout
    assert "Enabled-dead start requests: none." in result.stdout
    assert "STATUS=RED" in (tmp_path / "boot.marker").read_text(encoding="utf-8")


def test_late_bus_and_still_down_service_share_one_bounded_retry_budget(tmp_path: Path) -> None:
    env = _base_env(
        tmp_path,
        bus_up=False,
        down_unit="chief-listener.service",
        down_stays=True,
    )
    env["OPENCLAW_BOOT_MAX_ATTEMPTS"] = "4"
    env["OPENCLAW_BOOT_RETRY_SECONDS"] = "1"
    env["OPENCLAW_BOOT_SLEEP"] = str(
        _executable(
            tmp_path / "bounded-sleep",
            f"""
            #!/usr/bin/env bash
            state="{tmp_path / 'sleep.count'}"
            count=0
            [[ -r "$state" ]] && read -r count < "$state"
            count=$((count + 1))
            printf '%d\n' "$count" > "$state"
            if [[ "$count" == 2 ]]; then
              : > "{tmp_path / 'system_bus_socket'}"
            fi
            """,
        )
    )

    result = _run(CHECK, env)

    assert result.returncode == 1
    assert "chief-listener.service inactive after start request" in result.stdout
    assert (tmp_path / "sleep.count").read_text(encoding="utf-8").strip() == "3"
    calls = (tmp_path / "systemctl.calls").read_text(encoding="utf-8").splitlines()
    assert calls.count("--user is-active chief-listener.service") == 2
    assert calls.count("--user --no-block start chief-listener.service") == 1


def test_getty_tty1_is_benign_but_other_system_failure_is_reported(tmp_path: Path) -> None:
    benign_env = _base_env(tmp_path / "benign")
    benign = _run(CHECK, benign_env)
    assert benign.returncode == 0
    assert "getty@tty1" not in benign.stdout

    failed_root = tmp_path / "failed"
    failed_root.mkdir()
    failed_env = _base_env(failed_root, extra_failure="unexpected.service")
    failed = _run(CHECK, failed_env)
    assert failed.returncode == 1
    assert "system failure unexpected.service" in failed.stdout


def test_duplicate_poller_conflict_growth_and_stale_distro_only_warn(tmp_path: Path) -> None:
    env = _base_env(
        tmp_path,
        ps_output="""
        python -u /home/openclaw/maestro_listener.py
        python -u /home/openclaw/maestro_listener.py
        python -u /home/openclaw/chief_listener.py
        """,
    )
    env["OPENCLAW_BOOT_CONFLICT_COUNTER"] = str(
        _executable(
            tmp_path / "conflicts",
            f"""
            #!/usr/bin/env bash
            state="{tmp_path / 'conflict.state'}"
            if [[ ! -e "$state" ]]; then
              printf '10\n'
              : > "$state"
            else
              printf '11\n'
            fi
            """,
        )
    )

    result = _run(CHECK, env, "--stale-distro-running")

    assert result.returncode == 1
    assert "duplicate poller maestro=2" in result.stdout
    assert "getUpdates conflicts grew 10->11" in result.stdout
    assert 'stale WSL distro "Ubuntu" is running' in result.stdout
    calls = (tmp_path / "systemctl.calls").read_text(encoding="utf-8")
    assert " stop " not in f" {calls} "
    assert " restart " not in f" {calls} "
    assert "kill" not in calls


def test_niles_request_worker_is_not_miscounted_as_a_second_poller(tmp_path: Path) -> None:
    env = _base_env(
        tmp_path,
        ps_output="""
        python -u /home/openclaw/producer_listener.py
        python -u /home/openclaw/scripts/producer_intake.py --request fixture
        """,
    )

    result = _run(CHECK, env)

    assert result.returncode == 0
    assert "duplicate poller" not in result.stdout


def test_unit_windows_hook_and_runbook_keep_the_operator_boundary() -> None:
    unit = UNIT.read_text(encoding="utf-8")
    assert "After=default.target" in unit
    assert "DefaultDependencies=no" in unit
    assert "WantedBy=default.target" in unit
    assert "openclaw_boot_check.sh --source user-systemd" in unit
    assert "SuccessExitStatus=1 2" in unit
    assert "TimeoutStartSec=300" in unit

    batch = WINDOWS_HOOK.read_text(encoding="utf-8")
    assert "wsl.exe -d Ubuntu-E -u openclaw --exec" in batch
    assert "--stale-distro-running" in batch
    forbidden = ("--shutdown", "--terminate", "--unregister")
    assert all(word not in batch for word in forbidden)

    runbook = RUNBOOK.read_text(encoding="utf-8")
    assert "Task Scheduler" in runbook
    assert "At log on" in runbook
    assert "operator keyboard" in runbook.lower()
    assert "wsl --shutdown" in runbook


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck is not installed")
def test_boot_shell_scripts_are_shellcheck_clean() -> None:
    result = subprocess.run(
        ["shellcheck", str(CHECK), str(ENABLE), str(REPO_ROOT / "scripts" / "openclaw_boot_manifest.sh")],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
