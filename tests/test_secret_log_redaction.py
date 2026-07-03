from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest


TELEGRAM_TOKEN = "123456789:AA" + ("a" * 34)
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
TELEGRAM_TOKEN_RE = re.compile(r"\d{8,10}:AA[\w-]{30,}")


def _assert_no_telegram_secret(text: str) -> None:
    assert TELEGRAM_TOKEN not in text
    assert TELEGRAM_TOKEN_RE.search(text) is None


def test_redact_secrets_redacts_token_urls_and_common_api_keys() -> None:
    from secret_log_redaction import redact_secrets

    openai_key = "sk-proj-" + ("b" * 32)
    google_key = "AIza" + ("C" * 35)
    github_key = "ghp_" + ("D" * 36)
    text = f"failed {TELEGRAM_URL} keys {openai_key} {google_key} {github_key}"

    redacted = redact_secrets(text)

    _assert_no_telegram_secret(redacted)
    assert "bot123456789:[REDACTED]/sendMessage" in redacted
    assert openai_key not in redacted
    assert google_key not in redacted
    assert github_key not in redacted
    assert redacted.count("REDACTED") == 4
    assert redact_secrets("ordinary status update") == "ordinary status update"


def test_scrub_log_file_redacts_three_token_shapes_and_returns_count(tmp_path: Path) -> None:
    from secret_log_redaction import scrub_log_file

    log_path = tmp_path / "sender.out"
    openai_key = "sk-" + ("e" * 40)
    github_key = "ghp_" + ("F" * 36)
    log_path.write_text(
        f"voice failed {TELEGRAM_URL}\nopenai={openai_key}\ngithub={github_key}\n",
        encoding="utf-8",
    )

    count = scrub_log_file(log_path)
    scrubbed = log_path.read_text(encoding="utf-8")

    assert count == 3
    _assert_no_telegram_secret(scrubbed)
    assert openai_key not in scrubbed
    assert github_key not in scrubbed
    assert scrubbed.count("REDACTED") == 3


def test_agent_voice_send_failure_logs_and_raises_only_redacted_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import agent_voice_sender

    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"ogg fixture")
    monkeypatch.setenv("MAESTRO_BOT_TOKEN", TELEGRAM_TOKEN)
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "42")

    def fail_post(*args, **kwargs):
        raise RuntimeError(f"boom while posting {TELEGRAM_URL}")

    monkeypatch.setattr(agent_voice_sender.requests, "post", fail_post)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(RuntimeError) as exc:
            agent_voice_sender._send_telegram_voice_note("maestro", str(audio_path))

    _assert_no_telegram_secret(str(exc.value))
    _assert_no_telegram_secret(caplog.text)
    assert "123456789:[REDACTED]" in str(exc.value)
    assert "123456789:[REDACTED]" in caplog.text


def test_guardian_send_failure_logs_and_raises_only_redacted_message(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import chief_guardian_sender

    monkeypatch.setattr(chief_guardian_sender.chief_env, "load_env", lambda: None)
    monkeypatch.setenv("GUARDIAN_BOT_TOKEN", TELEGRAM_TOKEN)
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "42")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    def fail_post(*args, **kwargs):
        raise RuntimeError(f"guardian send failed at {TELEGRAM_URL}")

    monkeypatch.setattr(chief_guardian_sender.requests, "post", fail_post)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(RuntimeError) as exc:
            chief_guardian_sender.send_approval("Approve this", reply_markup={"inline_keyboard": []})

    _assert_no_telegram_secret(str(exc.value))
    _assert_no_telegram_secret(caplog.text)
    assert "123456789:[REDACTED]" in str(exc.value)
    assert "123456789:[REDACTED]" in caplog.text


def test_master_voice_error_paths_use_redactor_instead_of_raw_exception_prints() -> None:
    source = Path("master_voice.sh").read_text(encoding="utf-8")

    assert "redact_with_python" in source
    assert "VOICE_CURL_ERR" in source
    assert "redact_secrets(str(e))" in source
    assert 'print(f"text {i+1} FAILED:",e)' not in source
