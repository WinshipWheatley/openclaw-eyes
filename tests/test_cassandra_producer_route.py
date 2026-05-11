import pytest
from scripts.producer_telegram_route import extract_producer_payload

def test_extract_producer_payload():
    assert extract_producer_payload("/producer help") == "help"
    assert extract_producer_payload("producer: test me") == "test me"
    assert extract_producer_payload("other command") is None
    assert extract_producer_payload("/producer ") == ""
