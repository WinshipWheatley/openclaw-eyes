from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import hitl_notification_service as notify


@pytest.fixture(autouse=True)
def _no_runtime_env_file(monkeypatch):
    # The test owns its complete environment fixture and never reads .chief.env.
    monkeypatch.setitem(sys.modules, "chief_env", SimpleNamespace(load_env=lambda: None))
    monkeypatch.setattr(notify, "_NOTIFY_SECRET_WARNING_EMITTED", False)


def test_dedicated_hitl_secret_is_used_without_rendering_value(monkeypatch, capsys) -> None:
    monkeypatch.setenv("HITL_NOTIFY_SECRET", "fixture-dedicated-hmac-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "must-not-be-used")

    assert notify._notify_secret() == b"fixture-dedicated-hmac-secret"

    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "fixture-dedicated-hmac-secret" not in output
    assert "must-not-be-used" not in output


def test_generic_bot_token_never_becomes_hmac_secret_and_failure_is_token_free(monkeypatch, capsys) -> None:
    monkeypatch.delenv("HITL_NOTIFY_SECRET", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "generic-transport-secret")

    with pytest.raises(notify.HitlNotificationConfigurationError, match="HITL_NOTIFY_SECRET"):
        notify._notify_secret()
    with pytest.raises(notify.HitlNotificationConfigurationError):
        notify._notify_secret()

    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert output.count("LOUD CONFIGURATION ERROR") == 1
    assert "generic-transport-secret" not in output
    assert "hitl-default-secret" not in output


def test_validation_fails_closed_when_signing_secret_is_unavailable(monkeypatch) -> None:
    monkeypatch.delenv("HITL_NOTIFY_SECRET", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "generic-transport-secret")
    future = 4_102_444_800

    result = notify.validate_token(f"action-1.Y.{future}.deadbeefdead")

    assert result == {
        "ok": False,
        "action_id": "action-1",
        "decision": "Y",
        "error": "hitl_notify_secret_unavailable",
    }


@pytest.mark.parametrize(
    "transport_env",
    ("GUARDIAN_BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "PRODUCER_BOT_TOKEN"),
)
def test_hitl_secret_equal_to_transport_token_is_rejected_without_value_leak(
    monkeypatch,
    capsys,
    transport_env: str,
) -> None:
    monkeypatch.setenv("HITL_NOTIFY_SECRET", "shared-secret-must-be-rejected")
    monkeypatch.setenv(transport_env, "shared-secret-must-be-rejected")

    with pytest.raises(notify.HitlNotificationConfigurationError, match="distinct"):
        notify._notify_secret()

    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "shared-secret-must-be-rejected" not in output
    assert "LOUD CONFIGURATION ERROR" in output


def test_secure_drop_has_dedicated_hitl_secret_slot() -> None:
    import secure_drop

    slot = secure_drop.default_slots()["hitl_notify_secret"]
    assert slot.key == "HITL_NOTIFY_SECRET"
    assert slot.restart_services == ("chief-listener", "chief-guardian-listener")


def test_repo_wide_generic_bot_token_usage_matches_narrow_semantic_allowlist() -> None:
    root = Path(__file__).resolve().parents[1]
    suffixes = (".py", ".sh", ".service.in", ".env.example")
    excluded_roots = {"Operator", "docs", "generated", "reports", "tests", ".git"}
    violations: list[str] = []

    for path in root.rglob("*"):
        if not path.is_file() or not any(path.name.endswith(suffix) for suffix in suffixes):
            continue
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in excluded_roots:
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if "TELEGRAM_BOT_TOKEN" not in line and "PRODUCER_BOT_TOKEN" not in line:
                continue
            allowed = False
            if relative.as_posix() == "telegram_listener_integrity.py":
                allowed = (
                    'RoleBotTokenSpec("chief", "CHIEF_BOT_TOKEN", ("TELEGRAM_BOT_TOKEN",))' in line
                    or 'RoleBotTokenSpec("niles", "NILES_BOT_TOKEN", ("PRODUCER_BOT_TOKEN",))' in line
                    or "vendored Hermes adapter expects TELEGRAM_BOT_TOKEN" in line
                )
            elif relative.as_posix() == "scripts/run_openclaw_hermes_gateway.py":
                allowed = (
                    "reads generic TELEGRAM_BOT_TOKEN" in line
                    or '["TELEGRAM_BOT_TOKEN"] = token' in line
                )
            elif relative.name.startswith("expert_"):
                allowed = "_TELEGRAM_BOT_TOKEN_PATTERN" in line
            elif relative.as_posix() == "scripts/run_producer_listener.sh":
                allowed = "LOUD WARNING" in line or "NILES_BOT_TOKEN" in line
            elif relative.as_posix() == "hitl_notification_service.py":
                allowed = line.strip() in {'"TELEGRAM_BOT_TOKEN",', '"PRODUCER_BOT_TOKEN",'}
            if not allowed:
                violations.append(f"{relative}:{line_number}:{line.strip()}")

    assert violations == []
