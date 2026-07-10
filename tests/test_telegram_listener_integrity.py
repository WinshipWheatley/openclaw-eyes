from __future__ import annotations

import asyncio
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from telegram_listener_integrity import (
    BotIdentityVerificationError,
    clear_legacy_token_warnings_for_tests,
    install_identity_preflight,
    resolve_role_bot_token,
    resolve_role_bot_token_env,
    run_verified_polling,
)


@pytest.fixture(autouse=True)
def _reset_warning_once_state():
    clear_legacy_token_warnings_for_tests()


@pytest.mark.parametrize(
    ("role", "canonical", "legacy"),
    (
        ("chief", "CHIEF_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"),
        ("niles", "NILES_BOT_TOKEN", "PRODUCER_BOT_TOKEN"),
    ),
)
def test_role_token_prefers_canonical_and_legacy_fallback_is_loud_and_token_free(
    role: str,
    canonical: str,
    legacy: str,
) -> None:
    messages: list[str] = []
    environ = {canonical: "canonical-secret", legacy: "legacy-secret"}

    assert resolve_role_bot_token(role, environ=environ, warn=messages.append) == "canonical-secret"
    assert resolve_role_bot_token_env(role, environ=environ, warn=messages.append) == canonical
    assert messages == []

    environ.pop(canonical)
    assert resolve_role_bot_token(role, environ=environ, warn=messages.append) == "legacy-secret"
    assert resolve_role_bot_token_env(role, environ=environ, warn=messages.append) == legacy
    warning = "\n".join(messages)
    assert "LOUD WARNING" in warning
    assert warning.count("LOUD WARNING") == 1
    assert role in warning.lower()
    assert canonical in warning
    assert legacy in warning
    assert "legacy-secret" not in warning
    assert "canonical-secret" not in warning


@pytest.mark.parametrize(
    ("role", "canonical", "wrong_env"),
    (
        ("maestro", "MAESTRO_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"),
        ("cassandra", "CASSANDRA_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"),
        ("guardian", "GUARDIAN_BOT_TOKEN", "CHIEF_BOT_TOKEN"),
        ("hermes", "HERMES_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"),
    ),
)
def test_roles_without_approved_legacy_fallback_fail_closed(role: str, canonical: str, wrong_env: str) -> None:
    with pytest.raises(RuntimeError, match=canonical):
        resolve_role_bot_token(role, environ={wrong_env: "wrong"})


class _FakeBot:
    def __init__(self, *, username: str = "Chief_Status_Bot", bot_id: int = 4101, error: Exception | None = None):
        self.username = username
        self.bot_id = bot_id
        self.error = error
        self.calls = 0

    async def get_me(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return SimpleNamespace(username=self.username, id=self.bot_id)


def test_identity_preflight_normalizes_username_and_checks_optional_safe_id() -> None:
    logs: list[str] = []
    bot = _FakeBot(username="Chief_Status_Bot", bot_id=4101)
    app = SimpleNamespace(bot=bot, post_init=None)
    env = {
        "CHIEF_EXPECTED_BOT_USERNAME": "@chief_status_bot",
        "CHIEF_EXPECTED_BOT_ID": "4101",
    }

    install_identity_preflight(app, "chief", environ=env, log=logs.append)
    asyncio.run(app.post_init(app))

    assert bot.calls == 1
    assert any("identity verified" in line.lower() for line in logs)
    assert any("@chief_status_bot" in line.lower() for line in logs)


@pytest.mark.parametrize(
    "environ",
    (
        {},
        {"CHIEF_EXPECTED_BOT_USERNAME": "@chief_status_bot", "CHIEF_EXPECTED_BOT_ID": "99"},
        {"CHIEF_EXPECTED_BOT_USERNAME": "@different_bot"},
    ),
)
def test_identity_missing_or_mismatch_refuses_before_original_post_init(environ: dict[str, str]) -> None:
    logs: list[str] = []
    original_calls: list[str] = []

    async def original_post_init(_application) -> None:
        original_calls.append("original")

    app = SimpleNamespace(
        bot=_FakeBot(username="Chief_Status_Bot", bot_id=4101),
        post_init=original_post_init,
    )
    install_identity_preflight(app, "chief", environ=environ, log=logs.append)

    with pytest.raises(BotIdentityVerificationError):
        asyncio.run(app.post_init(app))

    assert original_calls == []
    safe_log = "\n".join(logs)
    assert "chief" in safe_log.lower()
    assert "refusing" in safe_log.lower()


def test_identity_get_me_failure_never_logs_token_or_url() -> None:
    token = "123456:SUPER_SECRET_TOKEN_MATERIAL"
    logs: list[str] = []
    app = SimpleNamespace(
        bot=_FakeBot(error=RuntimeError(f"request failed for https://api.telegram.org/bot{token}/getMe")),
        post_init=None,
    )
    install_identity_preflight(
        app,
        "chief",
        environ={"CHIEF_EXPECTED_BOT_USERNAME": "chief_status_bot"},
        log=logs.append,
    )

    with pytest.raises(BotIdentityVerificationError):
        asyncio.run(app.post_init(app))

    safe_log = "\n".join(logs)
    assert token not in safe_log
    assert "api.telegram.org" not in safe_log
    assert "RuntimeError" in safe_log


def test_mismatch_causes_zero_start_polling() -> None:
    calls: list[str] = []

    class Updater:
        async def start_polling(self) -> None:
            calls.append("start_polling")

        async def stop(self) -> None:
            calls.append("stop_polling")

    class App:
        updater = Updater()
        bot = _FakeBot(username="maestro_bot", bot_id=1)
        post_init = None
        running = False

        async def initialize(self) -> None:
            calls.append("initialize")

        async def start(self) -> None:
            calls.append("start")

        async def stop(self) -> None:
            calls.append("stop")

        async def shutdown(self) -> None:
            calls.append("shutdown")

    with pytest.raises(BotIdentityVerificationError):
        asyncio.run(
            run_verified_polling(
                App(),
                "chief",
                stop_event=asyncio.Event(),
                environ={"CHIEF_EXPECTED_BOT_USERNAME": "chief_bot"},
            )
        )

    assert "start_polling" not in calls
    assert calls == ["initialize", "shutdown"]


def test_all_polling_adapters_install_identity_preflight_before_polling() -> None:
    expected = {
        "maestro_listener.py": "maestro",
        "chief_listener.py": "chief",
        "cassandra_listener.py": "cassandra",
        "chief_guardian_listener.py": "guardian",
        "producer_listener.py": "niles",
    }
    for path, role in expected.items():
        source = open(path, encoding="utf-8").read()
        assert f'install_identity_preflight(application, "{role}")' in source
        assert f'run_verified_polling(application, "{role}"' in source


def test_hermes_launcher_preflights_then_explicitly_remaps_for_vendor() -> None:
    source = open("scripts/run_openclaw_hermes_gateway.py", encoding="utf-8").read()

    assert "preflight_hermes_bot_identity" in source
    assert 'resolve_role_bot_token("hermes"' in source
    assert 'os.environ["TELEGRAM_BOT_TOKEN"] = token' in source
    assert source.index("preflight_hermes_bot_identity") < source.index("run_gateway(")


def test_hermes_preflight_requires_canonical_token_and_remaps_only_after_getme(monkeypatch) -> None:
    from scripts import run_openclaw_hermes_gateway as launcher

    env = {
        "HERMES_BOT_TOKEN": "hermes-secret",
        "HERMES_EXPECTED_BOT_USERNAME": "@hermes_public_bot",
        "TELEGRAM_BOT_TOKEN": "wrong-generic-secret",
    }
    calls: list[str] = []

    def fetch(url: str):
        calls.append(url)
        assert "hermes-secret" in url
        return {"ok": True, "result": {"username": "Hermes_Public_Bot", "id": 8801}}

    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    launcher.preflight_hermes_bot_identity(environ=env, fetch_json=fetch)

    assert len(calls) == 1
    assert env["TELEGRAM_BOT_TOKEN"] == "hermes-secret"
    assert os.environ["TELEGRAM_BOT_TOKEN"] == "hermes-secret"

    with pytest.raises(RuntimeError, match="HERMES_BOT_TOKEN"):
        launcher.preflight_hermes_bot_identity(
            environ={
                "TELEGRAM_BOT_TOKEN": "generic-only",
                "HERMES_EXPECTED_BOT_USERNAME": "hermes_public_bot",
            },
            fetch_json=fetch,
        )


def test_secure_drop_provisions_distinct_maestro_chief_and_niles_slots() -> None:
    import secure_drop

    slots = secure_drop.default_slots()
    assert slots["maestro_bot_token"].key == "MAESTRO_BOT_TOKEN"
    assert slots["chief_bot_token"].key == "CHIEF_BOT_TOKEN"
    assert slots["niles_bot_token"].key == "NILES_BOT_TOKEN"
    assert len({slots[name].key for name in ("maestro_bot_token", "chief_bot_token", "niles_bot_token")}) == 3


def test_namespace_sweep_has_no_unapproved_generic_role_fallbacks() -> None:
    source_by_path = {
        path: open(path, encoding="utf-8").read()
        for path in (
            "maestro_listener.py",
            "agent_voice_sender.py",
            "producer_listener.py",
            "chief_sender.py",
            "chief_notify.py",
            "chief_guardian_sender.py",
            "chief_morning_push.py",
            "secure_drop.py",
        )
    }

    assert "TELEGRAM_BOT_TOKEN" not in source_by_path["maestro_listener.py"]
    assert "TELEGRAM_BOT_TOKEN" not in source_by_path["agent_voice_sender.py"]
    assert "TELEGRAM_BOT_TOKEN" not in source_by_path["producer_listener.py"]
    assert 'resolve_role_bot_token("chief")' in source_by_path["chief_sender.py"]
    assert 'resolve_role_bot_token("chief")' in source_by_path["chief_notify.py"]
    assert 'resolve_role_bot_token("chief")' in source_by_path["chief_guardian_sender.py"]
    assert '"CHIEF_BOT_TOKEN" not in os.environ' in source_by_path["chief_morning_push.py"]
    assert 'key="MAESTRO_BOT_TOKEN"' in source_by_path["secure_drop.py"]
    assert 'key="CHIEF_BOT_TOKEN"' in source_by_path["secure_drop.py"]
    assert 'key="NILES_BOT_TOKEN"' in source_by_path["secure_drop.py"]


def test_niles_launcher_exports_plain_env_assignments_to_exec(tmp_path: Path) -> None:
    (tmp_path / ".chief.env").write_text(
        "NILES_BOT_TOKEN=fixture-niles-token\n"
        "NILES_EXPECTED_BOT_USERNAME=fixture_niles_bot\n"
        "TELEGRAM_AUTHORIZED_USER_ID=123\n",
        encoding="utf-8",
    )
    receipt = tmp_path / "fake-exec-receipt"
    fake_python = tmp_path / "fake-python"
    fake_python.write_text(
        "#!/bin/bash\n"
        "set -e\n"
        "test \"${NILES_BOT_TOKEN:-}\" = fixture-niles-token\n"
        "test \"${NILES_EXPECTED_BOT_USERNAME:-}\" = fixture_niles_bot\n"
        "test \"${TELEGRAM_AUTHORIZED_USER_ID:-}\" = 123\n"
        "printf ok > \"${FAKE_EXEC_RECEIPT}\"\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "OPENCLAW_NILES_REPO_ROOT": str(tmp_path),
            "OPENCLAW_NILES_LISTENER_PYTHON": str(fake_python),
            "FAKE_EXEC_RECEIPT": str(receipt),
        }
    )
    for name in (
        "NILES_BOT_TOKEN",
        "NILES_EXPECTED_BOT_USERNAME",
        "TELEGRAM_AUTHORIZED_USER_ID",
        "PRODUCER_BOT_TOKEN",
        "PRODUCER_AUTHORIZED_USER_ID",
    ):
        env.pop(name, None)

    completed = subprocess.run(
        ["bash", "scripts/run_producer_listener.sh"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert receipt.read_text(encoding="utf-8") == "ok"
    assert "fixture-niles-token" not in completed.stdout
    assert "fixture-niles-token" not in completed.stderr
