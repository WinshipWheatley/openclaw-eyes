"""Unit tests for file-verify intent detection and handler wiring in cassandra_brain."""
import sys
import types
from unittest.mock import patch

import pytest

sys.path.insert(0, "/home/openclaw")
sys.path.insert(0, "/home/openclaw/tools")  # needed so patch("file_verify.*") can resolve the module

from cassandra_brain import _detect_file_verify_intent, _handle_file_verification_request


# ---------------------------------------------------------------------------
# Intent detection — positive cases
# ---------------------------------------------------------------------------

def test_detect_intent_explicit_path_exists():
    assert _detect_file_verify_intent('Does the file /home/openclaw/test.py exist?') is True

def test_detect_intent_quoted_path_is_there():
    assert _detect_file_verify_intent("Check if '/mnt/c/data/report.pdf' is there") is True

def test_detect_intent_folder():
    assert _detect_file_verify_intent("Is there a folder at /home/openclaw/tools?") is True

def test_detect_intent_verify_path():
    assert _detect_file_verify_intent("Verify the path /tmp/output exists") is True

def test_detect_intent_find_the_file():
    assert _detect_file_verify_intent("Can you find the file '/home/openclaw/start_chief.sh'?") is True


# ---------------------------------------------------------------------------
# Intent detection — negative cases (must NOT match)
# ---------------------------------------------------------------------------

def test_detect_intent_negative_file_invoice():
    assert _detect_file_verify_intent("File the invoice for the Hilton gig") is False

def test_detect_intent_negative_weather():
    assert _detect_file_verify_intent("What's the weather in Annapolis?") is False

def test_detect_intent_negative_path_venue():
    assert _detect_file_verify_intent("The path to the venue is unclear") is False

def test_detect_intent_negative_casual():
    assert _detect_file_verify_intent("Hey Cass, how's it going?") is False

def test_detect_intent_negative_future_action():
    assert _detect_file_verify_intent("Remind me to call Dad tomorrow") is False


# ---------------------------------------------------------------------------
# Handler — successful file check
# ---------------------------------------------------------------------------

def test_handler_file_exists():
    with patch("file_verify.answer_file_verification",
               return_value="Confirmed. /tmp/x.txt exists, and it's a file."):
        result = _handle_file_verification_request("Does /tmp/x.txt exist?")
    assert result == "Confirmed. /tmp/x.txt exists, and it's a file."


# ---------------------------------------------------------------------------
# Handler — not-found check
# ---------------------------------------------------------------------------

def test_handler_file_not_found():
    with patch("file_verify.answer_file_verification",
               return_value="Confirmed. /tmp/nope.txt does not exist from here."):
        result = _handle_file_verification_request("Does /tmp/nope.txt exist?")
    assert result is not None
    assert "does not exist" in result


# ---------------------------------------------------------------------------
# Handler — no path given
# ---------------------------------------------------------------------------

def test_handler_no_path_given():
    with patch("file_verify.answer_file_verification",
               return_value="I can verify a file or path if you give me the exact path."):
        result = _handle_file_verification_request("Does the file exist?")
    assert result is not None
    assert "exact path" in result


# ---------------------------------------------------------------------------
# Handler — tool raises exception
# ---------------------------------------------------------------------------

def test_handler_tool_exception():
    with patch("file_verify.answer_file_verification",
               side_effect=PermissionError("access denied")):
        result = _handle_file_verification_request("Does /tmp/x.txt exist?")
    assert result is not None
    assert "problem" in result or "verify it directly" in result
    assert "exists" not in result.lower()


# ---------------------------------------------------------------------------
# Handler returns None for non-matching input
# ---------------------------------------------------------------------------

def test_handler_returns_none_for_non_match():
    result = _handle_file_verification_request("What's the weather?")
    assert result is None


# ---------------------------------------------------------------------------
# Capability flag
# ---------------------------------------------------------------------------

def test_file_verify_connected_flag():
    from cassandra_capability import FILE_VERIFY_CONNECTED
    assert FILE_VERIFY_CONNECTED is True
