import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import openclaw_service_keeper as keeper


FIXED_NOW = "2026-05-31T04:05:00+00:00"


class FakeSystemctl:
    def __init__(self, states: dict[str, tuple[str, str]], *, fail_start: bool = False):
        self.states = dict(states)
        self.fail_start = fail_start
        self.commands: list[list[str]] = []

    def __call__(self, args: list[str]) -> keeper.CommandResult:
        self.commands.append(args)
        if args[:3] == ["systemctl", "--user", "show"]:
            unit = args[3]
            active, sub = self.states.get(unit, ("not-found", "dead"))
            load = "not-found" if active == "not-found" else "loaded"
            return keeper.CommandResult(
                0,
                f"LoadState={load}\nActiveState={active}\nSubState={sub}\nFragmentPath=/tmp/{unit}\n",
                "",
            )
        if args[:3] == ["systemctl", "--user", "start"]:
            unit = args[3]
            if self.fail_start:
                return keeper.CommandResult(1, "", "start failed")
            self.states[unit] = ("active", "running" if unit.endswith(".service") else "waiting")
            return keeper.CommandResult(0, "", "")
        return keeper.CommandResult(1, "", "unexpected command")


def test_keeper_refuses_non_allowlisted_unit():
    fake = FakeSystemctl({})
    result = keeper.check_and_start_unit(
        "openclaw-gateway.service",
        runner=fake,
        generated_at=FIXED_NOW,
    )

    assert result["status"] == "NOT_ALLOWLISTED"
    assert fake.commands == []


def test_keeper_starts_inactive_allowlisted_unit_in_mock_mode():
    fake = FakeSystemctl({"openclaw-request-response.service": ("inactive", "dead")})
    result = keeper.check_and_start_unit(
        "openclaw-request-response.service",
        runner=fake,
        generated_at=FIXED_NOW,
    )

    assert result["status"] == "STARTED_INACTIVE_UNIT"
    assert result["started"] is True
    assert ["systemctl", "--user", "start", "openclaw-request-response.service"] in fake.commands


def test_keeper_does_nothing_for_active_unit():
    fake = FakeSystemctl({"openclaw-change-sentinel.timer": ("active", "waiting")})
    result = keeper.check_and_start_unit(
        "openclaw-change-sentinel.timer",
        runner=fake,
        generated_at=FIXED_NOW,
    )

    assert result["status"] == "NO_ACTION_REQUIRED"
    assert not any(command[:3] == ["systemctl", "--user", "start"] for command in fake.commands)


def test_keeper_records_start_failed_if_systemctl_fails():
    fake = FakeSystemctl({"openclaw-request-response.service": ("inactive", "dead")}, fail_start=True)
    result = keeper.check_and_start_unit(
        "openclaw-request-response.service",
        runner=fake,
        generated_at=FIXED_NOW,
    )

    assert result["status"] == "START_FAILED"
    assert result["started"] is False
    assert "start failed" in result["error_message"]


def test_keeper_writes_operator_status(tmp_path):
    fake = FakeSystemctl(
        {
            "openclaw-request-response.service": ("active", "running"),
            "openclaw-change-sentinel.timer": ("active", "waiting"),
        }
    )
    payload = keeper.build_service_keeper_status(runner=fake, generated_at=FIXED_NOW)
    json_path, operator_path = keeper.write_service_keeper_status(
        payload,
        read_model_root=tmp_path,
    )

    assert payload["run_status"] == "NO_ACTION_REQUIRED"
    assert payload["action_count"] == 0
    assert json.loads(json_path.read_text(encoding="utf-8"))["schema_version"] == "openclaw_service_keeper_status_v0"
    assert "OpenClaw Service Keeper" in operator_path.read_text(encoding="utf-8")


def test_keeper_source_does_not_call_forbidden_live_surfaces():
    text = Path("scripts/openclaw_service_keeper.py").read_text(encoding="utf-8").lower()
    forbidden = [
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
        "mission_control_capture_requests",
        "mission_control_responses",
        "shell=True",
    ]
    for forbidden_text in forbidden:
        assert forbidden_text not in text
