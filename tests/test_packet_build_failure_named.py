"""An empty fallback packet must say why it is empty.

The handler lives in _answer_status_capability_with_brain, not answer_frontdoor_chat —
my first version of this test asserted against the wrong function and passed on the
structural check while missing both content checks.

The final-seam receipt showed the packet reaching the model was 124 characters with
zero facts, so the model answered "packet contents unavailable" — true, and useless.
Every layer above had been repaired and none of it arrived, because
build_maestro_context_packet was raising inside the service and an `except Exception:`
discarded the reason.

The stub stays — a degraded answer beats a dead front door. What must never happen
again is the stub being silent about why it exists.
"""

from __future__ import annotations

import inspect

import pytest

import maestro_cassandra_responder as mcr


def test_the_fallback_records_the_exception_type_and_message() -> None:
    """Structural: the handler must bind and use the exception, not discard it."""

    import ast

    src = inspect.getsource(mcr._answer_status_capability_with_brain)
    tree = ast.parse(src.lstrip())
    bare = [
        h for h in ast.walk(tree)
        if isinstance(h, ast.ExceptHandler)
        and h.name is None
        and any(
            isinstance(n, ast.Dict)
            and any(
                isinstance(k, ast.Constant) and k.value == "schema_version"
                for k in n.keys if k is not None
            )
            for n in ast.walk(h)
        )
    ]
    assert not bare, "the stub-packet handler discards its exception again"


def test_the_stub_carries_a_named_failure_in_its_proof() -> None:
    src = inspect.getsource(mcr._answer_status_capability_with_brain)
    for field in ("packet_build_failed", "packet_build_error_type", "packet_build_error"):
        assert field in src, f"the stub packet no longer carries {field}"


def test_the_packet_text_itself_declares_the_failure() -> None:
    """The model must be able to say WHY, not just that it has nothing."""

    assert "PACKET BUILD FAILED" in inspect.getsource(mcr._answer_status_capability_with_brain)


@pytest.mark.parametrize("raw,expected_absent", [
    ("bot 8615325274:AAH-verylongsecrettokenvaluegoeshere12345 failed", "AAH-verylong"),
    ("token=hunter2supersecret", "hunter2supersecret"),
    ("api_key: abcdef123456789", "abcdef123456789"),
])
def test_the_sanitizer_strips_secret_shaped_text(raw: str, expected_absent: str) -> None:
    cleaned = mcr._sanitize_packet_error(raw)
    assert expected_absent not in cleaned
    assert "<REDACTED>" in cleaned


def test_the_sanitizer_keeps_the_diagnosis() -> None:
    """NON-VACUITY: a redactor that eats the error is as useless as silence."""

    cleaned = mcr._sanitize_packet_error(
        "MaestroContextPacketError: requires real truth inputs: operator truth plus read models"
    )
    assert "requires real truth inputs" in cleaned
    assert "<REDACTED>" not in cleaned


def test_the_sanitizer_bounds_its_output() -> None:
    assert len(mcr._sanitize_packet_error("x" * 5000)) <= 240
