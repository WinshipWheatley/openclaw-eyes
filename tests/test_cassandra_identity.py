"""
test_cassandra_identity.py

Focused tests for cassandra_identity.py — the contact identity resolution module
extracted from cassandra_brain.py.
"""

import json
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_nicknames(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def _base_nicknames():
    return {
        "_note": "test fixture",
        "dad": {
            "name": "Henry Wheatley",
            "tier": "inner_circle",
            "telegram_chat_id": "12345",
            "pinned_email": "dad@example.com",
            "pinned_phone": None,
            "pinned_whatsapp": None,
        },
        "mom": {
            "name": "Susan Wheatley",
            "tier": "inner_circle",
            "telegram_chat_id": None,
            "pinned_email": "mom@example.com",
            "pinned_phone": "+15551234567",
            "pinned_whatsapp": None,
        },
        "draper": {
            "name": "John Draper",
            "aliases": ["captain crunch"],
            "tier": "inner_circle",
            "telegram_chat_id": "67890",
            "pinned_email": "draper@example.com",
            "pinned_phone": None,
            "pinned_whatsapp": "+15559876543",
        },
    }


# ── _load_nicknames ──────────────────────────────────────────────────────────

class TestLoadNicknames:
    def test_loads_and_lowercases_keys(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, {"Dad": "Henry", "_note": "skip"})
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        result = identity._load_nicknames()
        assert "dad" in result
        assert "_note" not in result

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", tmp_path / "nope.json")
        assert identity._load_nicknames() == {}


# ── _normalize_contact_entry ─────────────────────────────────────────────────

class TestNormalizeContactEntry:
    def test_string_entry(self):
        from cassandra_identity import _normalize_contact_entry
        entry = _normalize_contact_entry("dad", "Henry Wheatley")
        assert entry["nickname"] == "dad"
        assert entry["display_name"] == "Henry Wheatley"
        assert "henry wheatley" in entry["sender_names"]

    def test_dict_entry_with_pins(self):
        from cassandra_identity import _normalize_contact_entry
        raw = {
            "name": "Henry Wheatley",
            "telegram_chat_id": "12345",
            "pinned_email": "Dad@Example.com",
            "pinned_phone": "+15551234567",
        }
        entry = _normalize_contact_entry("dad", raw)
        assert entry["display_name"] == "Henry Wheatley"
        assert "12345" in entry["chat_ids"]
        assert entry["pinned_email"] == "dad@example.com"
        assert entry["pinned_phone"] == "+15551234567"

    def test_aliases_included(self):
        from cassandra_identity import _normalize_contact_entry
        raw = {"name": "John", "aliases": ["Captain Crunch", "JD"]}
        entry = _normalize_contact_entry("draper", raw)
        assert "captain crunch" in entry["sender_names"]
        assert "jd" in entry["sender_names"]

    def test_tier_defaults_to_inner_circle(self):
        from cassandra_identity import _normalize_contact_entry
        entry = _normalize_contact_entry("bob", "Bob Smith")
        assert entry["tier"] == "inner_circle"


# ── _find_designated_contact ─────────────────────────────────────────────────

class TestFindDesignatedContact:
    def test_find_by_name(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        result = identity._find_designated_contact(sender_name="Henry Wheatley")
        assert result is not None
        assert result["nickname"] == "dad"

    def test_find_by_chat_id(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        result = identity._find_designated_contact(sender_chat_id="67890")
        assert result is not None
        assert result["nickname"] == "draper"

    def test_not_found_returns_none(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        assert identity._find_designated_contact(sender_name="Nobody") is None


# ── find_contact_by_nickname ─────────────────────────────────────────────────

class TestFindContactByNickname:
    def test_found(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        result = identity.find_contact_by_nickname("Dad")
        assert result is not None
        assert result["nickname"] == "dad"

    def test_not_found(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        assert identity.find_contact_by_nickname("ghost") is None


# ── is_designated_contact_sender ─────────────────────────────────────────────

class TestIsDesignatedContactSender:
    def test_true_by_name(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        assert identity.is_designated_contact_sender(sender_name="Henry Wheatley") is True

    def test_false_for_unknown(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        assert identity.is_designated_contact_sender(sender_name="Random Person") is False


# ── is_pinned_on_channel ─────────────────────────────────────────────────────

class TestIsPinnedOnChannel:
    def test_telegram_pinned(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        assert identity.is_pinned_on_channel("dad", "telegram") is True

    def test_email_pinned(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        assert identity.is_pinned_on_channel("dad", "email") is True

    def test_not_pinned(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        assert identity.is_pinned_on_channel("dad", "whatsapp") is False

    def test_unknown_nickname(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        assert identity.is_pinned_on_channel("ghost", "email") is False


# ── verify_sender_on_channel ─────────────────────────────────────────────────

class TestVerifySenderOnChannel:
    def test_telegram_verified(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        result = identity.verify_sender_on_channel("Henry Wheatley", "12345", "telegram")
        assert result is not None
        assert result["nickname"] == "dad"

    def test_telegram_wrong_chat_id(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        assert identity.verify_sender_on_channel("Henry Wheatley", "99999", "telegram") is None

    def test_email_verified_by_pin(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        result = identity.verify_sender_on_channel("Henry Wheatley", "dad@example.com", "email")
        assert result is not None
        assert result["nickname"] == "dad"

    def test_email_wrong_sender_id(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        assert identity.verify_sender_on_channel("Henry Wheatley", "wrong@example.com", "email") is None

    def test_unknown_sender(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        assert identity.verify_sender_on_channel("Nobody", None, "email") is None

    def test_phone_verified(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        result = identity.verify_sender_on_channel("Susan Wheatley", "+15551234567", "sms")
        assert result is not None
        assert result["nickname"] == "mom"

    def test_whatsapp_verified(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)
        result = identity.verify_sender_on_channel("John Draper", "+15559876543", "whatsapp")
        assert result is not None
        assert result["nickname"] == "draper"


# ── Brain re-export smoke tests ──────────────────────────────────────────────

class TestBrainReExportSmoke:
    def test_brain_re_exports_identity_functions(self, tmp_path, monkeypatch):
        import cassandra_identity as identity
        import cassandra_brain as brain
        p = tmp_path / "nicknames.json"
        _write_nicknames(p, _base_nicknames())
        monkeypatch.setattr(identity, "_NICKNAMES_PATH", p)

        # Verify brain re-exports work
        assert brain._load_nicknames() == identity._load_nicknames()
        assert brain._find_designated_contact(sender_name="Henry Wheatley") is not None
        assert brain.find_contact_by_nickname("dad") is not None
        assert brain.is_designated_contact_sender(sender_name="Henry Wheatley") is True
        assert brain.is_pinned_on_channel("dad", "email") is True
        assert brain.verify_sender_on_channel("Henry Wheatley", "12345", "telegram") is not None
