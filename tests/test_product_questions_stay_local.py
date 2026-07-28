"""PRODUCT-grounded turns stay on-box. The external projection is untouched.

The governed artifacts grade LIGHT — client names, figures, operator identity — so
_lm1_interpreter_context_packet correctly refuses to send them to the external brain,
which then answers "no public facts suitable for this model lane". The evidence was
never missing; it was deliberately withheld from an external model.

The fix is to keep those turns local, NOT to weaken the projection. Nothing here
reclassifies a fact, touches detect_pii_tier, or changes a tier.
"""

from __future__ import annotations

import inspect
import json

import pytest

import openclaw_request_processor as orp
import protected_generate as pg

PRODUCT_FACT = {
    "topic": "product_artifact",
    "label": "Product thesis — Gaps",
    "value": "Blocking v1: agent identity first.",
    "source_ref": "fleet_coord/PRODUCT/PRODUCT-THESIS-PROVABLE-DELEGATION-20260728.md",
    "pii_tier": "PUBLIC",
    "freshness": {"sha256": "sha256:4270f9b4"},
}
ORDINARY = {
    "topic": "read_model", "label": "Board", "value": "x",
    "source_ref": "generated/read_models/work_board.json", "pii_tier": "PUBLIC",
}


# ───────────────────────────── the router keeps product turns local

def test_product_facts_route_local() -> None:
    assert pg._product_grounded_question("q", {"facts": [PRODUCT_FACT]}) is True


def test_product_source_refs_route_local() -> None:
    assert pg._product_grounded_question(
        "q", {"source_refs": ["fleet_coord/PRODUCT/PRODUCT-THESIS.md"]}
    ) is True


def test_ordinary_turns_are_unaffected() -> None:
    """NON-VACUITY: a router that keeps everything local disables the external brain."""

    assert pg._product_grounded_question("q", {"facts": [ORDINARY],
                                               "source_refs": ["generated/read_models/a.json"]}) is False


@pytest.mark.parametrize("bad", [None, {}, "text", 42, {"facts": "nope"}])
def test_a_bad_packet_shape_never_breaks_routing(bad) -> None:
    assert pg._product_grounded_question("q", bad) is False


def test_the_router_is_wired_into_the_external_gate() -> None:
    src = inspect.getsource(pg)
    i = src.index("if (\n            _external_brain_router_enabled()")
    assert "_product_grounded_question(operator_prompt, packet)" in src[i: i + 320], (
        "the external gate does not consult the product router"
    )


# ──────────────────── the external projection is NOT weakened

def test_light_facts_still_never_cross_the_external_projection() -> None:
    """THE SAFETY REGRESSION. A LIGHT-detected fact must still be dropped."""

    # Realistic content: the governed artifacts carry client names and figures, which
    # is exactly why they grade LIGHT. A sanitised fixture would prove nothing.
    light = dict(PRODUCT_FACT, value=(
        "LAMD monthly speaker rental for Megan Rivas is $100.00, due on receipt; "
        "winshiplive@gmail.com is the operator account."
    ))
    from protected_generate import detect_pii_tier

    assert detect_pii_tier(json.dumps(light, sort_keys=True, default=str), None) != "PUBLIC", (
        "fixture is not actually LIGHT — the test would prove nothing"
    )
    projected = orp._lm1_interpreter_context_packet({"facts": [light], "packet_id": "p"})
    assert light["value"] not in json.dumps(projected), (
        "a LIGHT product fact reached the external-safe projection"
    )


def test_the_projection_still_filters_on_detected_tier() -> None:
    """The tier check must remain — this is the guard, not the bug."""

    src = inspect.getsource(orp._lm1_interpreter_context_packet)
    assert "detect_pii_tier" in src
    assert 'fact_tier != "PUBLIC"' in src and "continue" in src


def test_nothing_reclassifies_a_fact_tier() -> None:
    """No commit of mine may set a tier to PUBLIC to get past the projection."""

    # Code lines only. My own docstring names detect_pii_tier while explaining why it
    # must not be touched — a substring scan flags the explanation, which is the third
    # such false failure tonight.
    src = inspect.getsource(pg._product_grounded_question)
    body = src.split('"""')[-1]
    for forbidden in ("pii_tier", "detect_pii_tier"):
        assert forbidden not in body, f"the router touches {forbidden}"


def test_a_genuinely_public_fact_still_projects() -> None:
    """NON-VACUITY on the safety side: the projection is a filter, not a wall."""

    public = {"topic": "read_model", "label": "Count", "value": "7",
              "source_ref": "generated/read_models/work_board.json", "pii_tier": "PUBLIC"}
    projected = orp._lm1_interpreter_context_packet({"facts": [public], "packet_id": "p"})
    assert projected.get("facts"), "the projection dropped a genuinely public fact"
