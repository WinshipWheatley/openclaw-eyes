"""The external projection grades what a reader sees, not the envelope around it.

It serialized the whole fact — fact_id, source_ref path, provenance, freshness.sha256
— and graded that. The envelope alone reads LIGHT, so EVERY fact was blocked whatever
it said, and the external lane honestly reported no public facts because by that
measure nothing ever was. A clean fact about nothing was refused identically to a
private one.

This narrows what is measured, never how strictly. Private content is still blocked.
"""

from __future__ import annotations

import inspect
import json

import openclaw_request_processor as orp
from protected_generate import detect_pii_tier

ENVELOPE = {
    "fact_id": "product_artifact:abc123",
    "provenance": "governed_product_artifact",
    "source_ref": "fleet_coord/PRODUCT/PRODUCT-PUBLIC-BRIEF-20260728.md",
    "freshness": {"sha256": "sha256:4270f9b4db346afaaed6a7beb", "as_of": "2026-07-28T00:00:00Z"},
    "pii_tier": "PUBLIC",
    "topic": "product_artifact",
}
PUBLIC_FACT = dict(ENVELOPE, label="Public brief — delivery proof",
                   value="Dispatch is not delivery. A signal emitted is not a signal received.")
PRIVATE_FACT = dict(ENVELOPE, label="Monthly rental",
                    value=("Megan Rivas owes $100.00 to winshiplive@gmail.com for the "
                           "July speaker rental."))


def _project(fact):
    return orp._lm1_interpreter_context_packet({"facts": [fact], "packet_id": "p"})


def test_a_clean_public_fact_crosses_with_normal_metadata() -> None:
    """THE BUG: identical metadata used to block this outright."""

    projected = _project(PUBLIC_FACT)
    assert projected.get("facts"), "a PUBLIC-content fact was blocked by its envelope"
    assert PUBLIC_FACT["value"] in json.dumps(projected)


def test_provenance_survives_the_crossing() -> None:
    """Tiering stops deciding privacy; it must not stop carrying audit."""

    fact = _project(PUBLIC_FACT)["facts"][0]
    assert fact["source_ref"] == ENVELOPE["source_ref"]
    assert fact["provenance"] == ENVELOPE["provenance"]
    assert fact["fact_id"] == ENVELOPE["fact_id"]


def test_a_realistic_private_fact_is_still_blocked() -> None:
    """THE SAFETY REGRESSION. Same envelope, private content."""

    assert detect_pii_tier(PRIVATE_FACT["value"], None) != "PUBLIC", (
        "fixture is not actually private — the test would prove nothing"
    )
    projected = _project(PRIVATE_FACT)
    assert PRIVATE_FACT["value"] not in json.dumps(projected)
    assert not projected.get("facts"), "a private fact crossed the external projection"


def test_only_reader_visible_fields_are_graded() -> None:
    src = inspect.getsource(orp._lm1_interpreter_context_packet)
    i = src.index("detect_pii_tier(")
    window = src[i: i + 320]
    assert '"label", "value", "topic"' in window
    assert "json.dumps(dict(fact)" not in window, "the envelope is graded again"


def test_the_tier_check_itself_is_unchanged() -> None:
    """Still refuses anything above PUBLIC, still fails closed on error."""

    src = inspect.getsource(orp._lm1_interpreter_context_packet)
    assert 'fact_tier != "PUBLIC"' in src and "continue" in src
    assert 'fact_tier = "HIGH"' in src, "the fail-closed default was removed"


def test_no_authority_field_is_introduced() -> None:
    fact = _project(PUBLIC_FACT)["facts"][0]
    for forbidden in ("authority", "allowed", "approved", "send", "grant"):
        assert not any(forbidden in k.lower() for k in fact), f"{forbidden} appeared"


def test_the_declared_tier_gate_still_applies() -> None:
    """A fact declaring a non-PUBLIC tier is dropped before content is even graded."""

    assert not _project(dict(PUBLIC_FACT, pii_tier="HIGH")).get("facts")


def test_the_public_brief_crosses_end_to_end() -> None:
    """The governed PUBLIC artifact reaching the external-safe packet."""

    import pytest

    import maestro_context_packet as mcp

    try:
        packet = mcp.build_maestro_context_packet(
            question="what is the owner-first product hypothesis, smallest v1, and top blocker?"
        )
    except mcp.MaestroContextPacketError:
        pytest.skip("sandbox blocks real truth inputs — verified out-of-band instead")
    projected = orp._lm1_interpreter_context_packet(packet)
    refs = [f.get("source_ref", "") for f in projected.get("facts", ())]
    assert any("PRODUCT-PUBLIC-BRIEF" in r for r in refs), "the public brief did not cross"
    for fact in projected.get("facts", ()):
        assert detect_pii_tier(str(fact.get("value") or ""), None) == "PUBLIC", (
            f"non-public content crossed: {fact.get('source_ref')}"
        )
