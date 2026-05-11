import pytest
from cassandra_listener import _extract_producer_payload

def test_extract_producer_payload():
    assert _extract_producer_payload("/producer help") == "help"
    assert _extract_producer_payload("producer: test me") == "test me"
    assert _extract_producer_payload("other command") is None
    assert _extract_producer_payload("/producer ") == ""
