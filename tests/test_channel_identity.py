"""
Unit tests for channel-specific identity pinning schema extension.
Tests: is_pinned_on_channel(), verify_sender_on_channel(), and _normalize_contact_entry()
channel pin fields. Also verifies no regression in is_designated_contact_sender().
"""

import json
import sys
import os
import importlib
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cassandra_brain
import cassandra_identity
from cassandra_brain import _find_designated_contact


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_nicknames(**overrides):
    """Return a minimal nicknames dict; overrides replace individual entries."""
    base = {
        "_note": "test",
        "dad": {
            "name": "Henry Winship Wheatley III",
            "tier": "inner_circle",
            "telegram_chat_id": None,
            "pinned_email": None,
            "pinned_phone": None,
            "pinned_whatsapp": None,
        },
        "mom": {
            "name": "Susan Elizabeth Wheatley",
            "tier": "inner_circle",
            "telegram_chat_id": None,
            "pinned_email": None,
            "pinned_phone": None,
            "pinned_whatsapp": None,
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# _normalize_contact_entry — pin fields
# ---------------------------------------------------------------------------

class TestNormalizeContactEntryPinFields(unittest.TestCase):

    def test_null_pins_in_raw_produce_none_in_entry(self):
        raw = {"name": "Henry W", "tier": "inner_circle",
               "pinned_email": None, "pinned_phone": None, "pinned_whatsapp": None}
        entry = cassandra_brain._normalize_contact_entry("dad", raw)
        self.assertIsNone(entry["pinned_email"])
        self.assertIsNone(entry["pinned_phone"])
        self.assertIsNone(entry["pinned_whatsapp"])

    def test_string_pins_in_raw_are_normalized_for_email(self):
        raw = {"name": "Henry W", "tier": "inner_circle",
               "pinned_email": " Dad@Example.com ",
               "pinned_phone": "+15551234567",
               "pinned_whatsapp": "+15551234567"}
        entry = cassandra_brain._normalize_contact_entry("dad", raw)
        self.assertEqual(entry["pinned_email"], "dad@example.com")
        self.assertEqual(entry["pinned_phone"], "+15551234567")
        self.assertEqual(entry["pinned_whatsapp"], "+15551234567")

    def test_non_string_pin_values_become_none(self):
        raw = {"name": "Henry W", "tier": "inner_circle",
               "pinned_email": 12345,
               "pinned_phone": True,
               "pinned_whatsapp": ["oops"]}
        entry = cassandra_brain._normalize_contact_entry("dad", raw)
        self.assertIsNone(entry["pinned_email"])
        self.assertIsNone(entry["pinned_phone"])
        self.assertIsNone(entry["pinned_whatsapp"])

    def test_missing_pin_fields_produce_none(self):
        raw = {"name": "Henry W", "tier": "inner_circle"}
        entry = cassandra_brain._normalize_contact_entry("dad", raw)
        self.assertIsNone(entry["pinned_email"])
        self.assertIsNone(entry["pinned_phone"])
        self.assertIsNone(entry["pinned_whatsapp"])

    def test_partial_pins_preserved_and_missing_are_none(self):
        # Only email is set; phone and whatsapp are None — spec test 1.2
        raw = {"name": "Bob W", "tier": "inner_circle",
               "pinned_email": "bob@example.com",
               "pinned_phone": None,
               "pinned_whatsapp": None}
        entry = cassandra_brain._normalize_contact_entry("bob", raw)
        self.assertEqual(entry["pinned_email"], "bob@example.com")
        self.assertIsNone(entry["pinned_phone"])
        self.assertIsNone(entry["pinned_whatsapp"])

    def test_existing_fields_still_present(self):
        raw = {"name": "Henry W", "tier": "inner_circle", "telegram_chat_id": 999}
        entry = cassandra_brain._normalize_contact_entry("dad", raw)
        self.assertIn("dad", entry["sender_names"])
        self.assertIn("999", entry["chat_ids"])
        self.assertEqual(entry["tier"], "inner_circle")


# ---------------------------------------------------------------------------
# is_pinned_on_channel
# ---------------------------------------------------------------------------

class TestIsPinnedOnChannel(unittest.TestCase):

    def _patch(self, nicknames):
        return patch.object(cassandra_identity, "_load_nicknames", return_value={
            k: v for k, v in nicknames.items() if not k.startswith("_")
        })

    def test_returns_false_all_channels_when_no_pins_set(self):
        nicks = _make_nicknames()
        with self._patch(nicks):
            for channel in ("telegram", "email", "sms", "phone", "whatsapp"):
                self.assertFalse(
                    cassandra_brain.is_pinned_on_channel("dad", channel),
                    f"Expected False for channel={channel} with no pin set",
                )

    def test_telegram_true_when_chat_id_set(self):
        nicks = _make_nicknames(dad={
            "name": "Henry W", "tier": "inner_circle", "telegram_chat_id": 111222333,
            "pinned_email": None, "pinned_phone": None, "pinned_whatsapp": None,
        })
        with self._patch(nicks):
            self.assertTrue(cassandra_brain.is_pinned_on_channel("dad", "telegram"))

    def test_email_true_when_pinned_email_set(self):
        nicks = _make_nicknames(dad={
            "name": "Henry W", "tier": "inner_circle",
            "telegram_chat_id": None, "pinned_email": "dad@example.com",
            "pinned_phone": None, "pinned_whatsapp": None,
        })
        with self._patch(nicks):
            self.assertTrue(cassandra_brain.is_pinned_on_channel("dad", "email"))
            self.assertFalse(cassandra_brain.is_pinned_on_channel("dad", "sms"))

    def test_sms_and_phone_aliases_both_work(self):
        nicks = _make_nicknames(dad={
            "name": "Henry W", "tier": "inner_circle",
            "telegram_chat_id": None, "pinned_email": None,
            "pinned_phone": "+15551234567", "pinned_whatsapp": None,
        })
        with self._patch(nicks):
            self.assertTrue(cassandra_brain.is_pinned_on_channel("dad", "sms"))
            self.assertTrue(cassandra_brain.is_pinned_on_channel("dad", "phone"))

    def test_whatsapp_true_when_set(self):
        nicks = _make_nicknames(dad={
            "name": "Henry W", "tier": "inner_circle",
            "telegram_chat_id": None, "pinned_email": None,
            "pinned_phone": None, "pinned_whatsapp": "+15559876543",
        })
        with self._patch(nicks):
            self.assertTrue(cassandra_brain.is_pinned_on_channel("dad", "whatsapp"))

    def test_unknown_nickname_returns_false(self):
        nicks = _make_nicknames()
        with self._patch(nicks):
            self.assertFalse(cassandra_brain.is_pinned_on_channel("ghost", "email"))

    def test_unknown_channel_returns_false(self):
        nicks = _make_nicknames(dad={
            "name": "Henry W", "tier": "inner_circle",
            "pinned_email": "x@example.com", "pinned_phone": None, "pinned_whatsapp": None,
        })
        with self._patch(nicks):
            self.assertFalse(cassandra_brain.is_pinned_on_channel("dad", "fax"))


# ---------------------------------------------------------------------------
# verify_sender_on_channel
# ---------------------------------------------------------------------------

class TestVerifySenderOnChannel(unittest.TestCase):

    def _patch(self, nicknames):
        return patch.object(cassandra_identity, "_load_nicknames", return_value={
            k: v for k, v in nicknames.items() if not k.startswith("_")
        })

    def _dad_with(self, **pins):
        base = {"name": "Henry Winship Wheatley III", "tier": "inner_circle",
                "telegram_chat_id": None, "pinned_email": None,
                "pinned_phone": None, "pinned_whatsapp": None}
        base.update(pins)
        return _make_nicknames(dad=base)

    def test_returns_none_when_no_contact_found(self):
        with self._patch(_make_nicknames()):
            result = cassandra_brain.verify_sender_on_channel("nobody", None, "email")
        self.assertIsNone(result)

    def test_returns_none_for_known_name_unpinned_channel(self):
        # Name matches but email pin is null — must refuse
        with self._patch(_make_nicknames()):
            result = cassandra_brain.verify_sender_on_channel(
                "Henry Winship Wheatley III", None, "email"
            )
        self.assertIsNone(result)

    def test_returns_contact_when_name_matches_and_channel_pinned(self):
        nicks = self._dad_with(pinned_email="dad@example.com")
        with self._patch(nicks):
            result = cassandra_brain.verify_sender_on_channel(
                "Henry Winship Wheatley III", "dad@example.com", "email"
            )
        self.assertIsNotNone(result)
        self.assertEqual(result["nickname"], "dad")

    def test_returns_none_when_sender_id_does_not_match_email_pin(self):
        nicks = self._dad_with(pinned_email="dad@example.com")
        with self._patch(nicks):
            result = cassandra_brain.verify_sender_on_channel(
                "Henry Winship Wheatley III", "impostor@evil.com", "email"
            )
        self.assertIsNone(result)

    def test_email_comparison_is_case_insensitive(self):
        nicks = self._dad_with(pinned_email="Dad@Example.com")
        with self._patch(nicks):
            result = cassandra_brain.verify_sender_on_channel(
                "Henry Winship Wheatley III", "dad@example.com", "email"
            )
        self.assertIsNotNone(result)

    def test_email_comparison_ignores_sender_whitespace(self):
        nicks = self._dad_with(pinned_email="dad@example.com")
        with self._patch(nicks):
            result = cassandra_brain.verify_sender_on_channel(
                "Henry Winship Wheatley III", "  DAD@example.com  ", "email"
            )
        self.assertIsNotNone(result)

    def test_returns_contact_when_sms_pin_matches(self):
        nicks = self._dad_with(pinned_phone="+15551234567")
        with self._patch(nicks):
            result = cassandra_brain.verify_sender_on_channel(
                "Henry Winship Wheatley III", "+15551234567", "sms"
            )
        self.assertIsNotNone(result)

    def test_returns_none_when_sms_pin_mismatch(self):
        nicks = self._dad_with(pinned_phone="+15551234567")
        with self._patch(nicks):
            result = cassandra_brain.verify_sender_on_channel(
                "Henry Winship Wheatley III", "+19999999999", "sms"
            )
        self.assertIsNone(result)

    def test_returns_contact_when_whatsapp_pin_matches(self):
        nicks = self._dad_with(pinned_whatsapp="+15551234567")
        with self._patch(nicks):
            result = cassandra_brain.verify_sender_on_channel(
                "Henry Winship Wheatley III", "+15551234567", "whatsapp"
            )
        self.assertIsNotNone(result)

    def test_telegram_channel_uses_chat_id_not_pin_fields(self):
        nicks = _make_nicknames(dad={
            "name": "Henry Winship Wheatley III", "tier": "inner_circle",
            "telegram_chat_id": 111222333,
            "pinned_email": None, "pinned_phone": None, "pinned_whatsapp": None,
        })
        with self._patch(nicks):
            result = cassandra_brain.verify_sender_on_channel(
                None, "111222333", "telegram"
            )
        self.assertIsNotNone(result)
        self.assertEqual(result["nickname"], "dad")

    def test_telegram_unpinned_returns_none(self):
        # telegram_chat_id is null — not pinned
        with self._patch(_make_nicknames()):
            result = cassandra_brain.verify_sender_on_channel(
                "Henry Winship Wheatley III", None, "telegram"
            )
        self.assertIsNone(result)

    def test_returns_contact_name_match_no_sender_id(self):
        # sender_id=None on pinned channel — name match alone is sufficient — spec test 3.2
        nicks = self._dad_with(pinned_email="dad@example.com")
        with self._patch(nicks):
            result = cassandra_brain.verify_sender_on_channel(
                "Henry Winship Wheatley III", None, "email"
            )
        self.assertIsNotNone(result)
        self.assertEqual(result["nickname"], "dad")


# ---------------------------------------------------------------------------
# Regression — existing is_designated_contact_sender
# ---------------------------------------------------------------------------

class TestRegressionIsDesignatedContactSender(unittest.TestCase):

    def _patch(self, nicknames):
        return patch.object(cassandra_identity, "_load_nicknames", return_value={
            k: v for k, v in nicknames.items() if not k.startswith("_")
        })

    def test_returns_true_for_known_name(self):
        with self._patch(_make_nicknames()):
            self.assertTrue(
                cassandra_brain.is_designated_contact_sender(
                    sender_name="Henry Winship Wheatley III"
                )
            )

    def test_returns_false_for_unknown_name(self):
        with self._patch(_make_nicknames()):
            self.assertFalse(
                cassandra_brain.is_designated_contact_sender(sender_name="Random Person")
            )

    def test_returns_true_for_known_chat_id(self):
        nicks = _make_nicknames(dad={
            "name": "Henry Winship Wheatley III", "tier": "inner_circle",
            "telegram_chat_id": 999888777,
        })
        with self._patch(nicks):
            self.assertTrue(
                cassandra_brain.is_designated_contact_sender(sender_chat_id=999888777)
            )

    def test_find_designated_contact_by_name(self):
        # spec test 4.2 — _find_designated_contact by name directly
        with self._patch(_make_nicknames()):
            result = _find_designated_contact(sender_name="Henry Winship Wheatley III")
        self.assertIsNotNone(result)
        self.assertEqual(result["nickname"], "dad")

    def test_find_designated_contact_by_chat_id(self):
        # spec test 4.3 — _find_designated_contact by chat_id directly
        nicks = _make_nicknames(dad={
            "name": "Henry Winship Wheatley III", "tier": "inner_circle",
            "telegram_chat_id": 999888777,
        })
        with self._patch(nicks):
            result = _find_designated_contact(sender_chat_id=999888777)
        self.assertIsNotNone(result)
        self.assertEqual(result["nickname"], "dad")

    def test_new_pin_fields_do_not_break_existing_function(self):
        # Schema now includes pin fields — function must still work identically
        nicks = _make_nicknames(dad={
            "name": "Henry Winship Wheatley III", "tier": "inner_circle",
            "telegram_chat_id": None,
            "pinned_email": "dad@example.com",
            "pinned_phone": "+15551234567",
            "pinned_whatsapp": None,
        })
        with self._patch(nicks):
            self.assertTrue(
                cassandra_brain.is_designated_contact_sender(
                    sender_name="Henry Winship Wheatley III"
                )
            )


if __name__ == "__main__":
    unittest.main()
