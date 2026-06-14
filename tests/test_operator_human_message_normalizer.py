import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_human_message_normalizer import is_low_signal_address_prefix, normalize_human_text


def test_normalize_human_text_repairs_common_operator_typos():
    text = "plz maek a test calndr event; wat hapens if I attch prof?"

    normalized = normalize_human_text(text)

    assert "please make a test calendar event" in normalized
    assert "what happens if i attach proof" in normalized


def test_low_signal_comma_prefixes_are_not_agent_names():
    assert is_low_signal_address_prefix("ok") is True
    assert is_low_signal_address_prefix("idk") is True
    assert is_low_signal_address_prefix("honestly") is True
    assert is_low_signal_address_prefix("Zephyr") is False
