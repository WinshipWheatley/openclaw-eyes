"""Secure-drop: paste a sensitive value into the vault with zero exposure.

Operator ask 2026-07-02: "anytime the system needs me to drop data in it that
may be sensitive, have a terminal pop up where all I gotta do is copy and paste
into that slot." Hard invariants:
- The secret is read via getpass (never argv, never env, never a normal prompt echo).
- It is written atomically to the target env file, preserving every other line.
- The value NEVER appears in stdout, a log, an exception message, or a return value.
- Unknown slots are rejected (no arbitrary file writes).
"""

import os
import stat
from pathlib import Path

import secure_drop as sd


def _slots(tmp_path: Path):
    env = tmp_path / ".chief.env"
    env.write_text("EXISTING_KEY=keepme\nMAESTRO_BOT_TOKEN=old_value\nOTHER=two\n", encoding="utf-8")
    return {
        "maestro_bot_token": sd.SecretSlot(
            key="MAESTRO_BOT_TOKEN", env_file=env, label="Maestro/billing Telegram bot token",
            restart_services=("maestro-listener",),
        ),
        "new_secret": sd.SecretSlot(key="NEW_SECRET", env_file=env, label="A brand new secret"),
    }


def test_writes_replace_existing_key_preserving_others(tmp_path, monkeypatch):
    slots = _slots(tmp_path)
    monkeypatch.setattr(sd, "_read_secret", lambda prompt: "rotated_token_XYZ")
    result = sd.drop_secret("maestro_bot_token", slots=slots)
    text = slots["maestro_bot_token"].env_file.read_text(encoding="utf-8")
    assert "MAESTRO_BOT_TOKEN=rotated_token_XYZ" in text
    assert "EXISTING_KEY=keepme" in text  # untouched
    assert "OTHER=two" in text
    assert text.count("MAESTRO_BOT_TOKEN=") == 1  # replaced, not appended
    # the receipt must not leak the value
    assert "rotated_token_XYZ" not in str(result)
    assert result["status"] == "written"
    assert result["chars"] == len("rotated_token_XYZ")


def test_appends_new_key(tmp_path, monkeypatch):
    slots = _slots(tmp_path)
    monkeypatch.setattr(sd, "_read_secret", lambda prompt: "abc123")
    sd.drop_secret("new_secret", slots=slots)
    text = slots["new_secret"].env_file.read_text(encoding="utf-8")
    assert "NEW_SECRET=abc123" in text
    assert "MAESTRO_BOT_TOKEN=old_value" in text  # others preserved


def test_unknown_slot_rejected(tmp_path):
    slots = _slots(tmp_path)
    try:
        sd.drop_secret("../../etc/passwd", slots=slots)
        assert False, "unknown slot must raise"
    except KeyError:
        pass


def test_empty_input_is_rejected_not_written(tmp_path, monkeypatch):
    slots = _slots(tmp_path)
    before = slots["maestro_bot_token"].env_file.read_text(encoding="utf-8")
    monkeypatch.setattr(sd, "_read_secret", lambda prompt: "   ")
    result = sd.drop_secret("maestro_bot_token", slots=slots)
    assert result["status"] == "empty_no_change"
    assert slots["maestro_bot_token"].env_file.read_text(encoding="utf-8") == before


def test_env_file_stays_owner_only_perms(tmp_path, monkeypatch):
    slots = _slots(tmp_path)
    monkeypatch.setattr(sd, "_read_secret", lambda prompt: "s3cret")
    sd.drop_secret("maestro_bot_token", slots=slots)
    mode = stat.S_IMODE(os.stat(slots["maestro_bot_token"].env_file).st_mode)
    assert mode & 0o077 == 0, f"env file must be owner-only, got {oct(mode)}"


def test_value_never_in_receipt_or_confirmation(tmp_path, monkeypatch, capsys):
    slots = _slots(tmp_path)
    monkeypatch.setattr(sd, "_read_secret", lambda prompt: "TOPSECRET99")
    result = sd.drop_secret("maestro_bot_token", slots=slots, announce=True)
    out = capsys.readouterr().out
    assert "TOPSECRET99" not in out
    assert "TOPSECRET99" not in str(result)
    # confirmation shows a masked length only
    assert "11" in out or "chars" in out.lower()


def test_default_registry_has_maestro_token_slot():
    reg = sd.default_slots()
    assert "maestro_bot_token" in reg
    assert reg["maestro_bot_token"].key == "MAESTRO_BOT_TOKEN"
    assert reg["chief_bot_token"].key == "CHIEF_BOT_TOKEN"
    assert reg["niles_bot_token"].key == "NILES_BOT_TOKEN"
    assert str(reg["maestro_bot_token"].env_file).endswith(".chief.env")
