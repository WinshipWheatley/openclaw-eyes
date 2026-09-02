"""The egress grader must see what the tokenizer sees.

Before this change the per-fact external projection graded reader-visible content
with keyword cues only. A fact carrying a phone number, a street address, a client
name, a bare dollar figure or a long identifier, but none of the cue words, graded
PUBLIC and crossed the external-brain boundary verbatim.

Two layers now apply:
* `detect_pii_tier` lifts the tier for content the tokenizer cannot redact
  (street addresses, listed names, bare 7-8 or 14+ digit runs, bare money). Emails,
  phones, cards and labelled accounts are already tokenized at every tier by the
  front door, so they do not change the tier there.
* `content_may_cross_public` is the projection's verdict: nothing that any token
  pattern, org name, money figure, long number, address or listed name would touch
  may cross, because the projection never tokenizes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import openclaw_request_processor as orp
from protected_generate import (
    HIGH,
    LIGHT,
    MAX,
    MED,
    PII_NAME_LIST_ENV,
    PUBLIC,
    content_may_cross_public,
    detect_pii_tier,
)


@pytest.mark.parametrize(
    ("text", "tier", "may_cross"),
    [
        ("Dispatch is not delivery. A signal emitted is not a signal received.", PUBLIC, True),
        ("Blue Weather is at the follow_up phase; The Future is version locked.", PUBLIC, True),
        ("Yacht rock and soft rock lane, fifteen songs, blocks of consecutive nights.", PUBLIC, True),
        ("Full rig is $1,125 a night and the acoustic set stays at 400 dollars.", LIGHT, False),
        ("Megan prefers Tuesday load-ins at 412 Oak St.", MED, False),
        ("The confirmation is 30000143 on the check stub.", HIGH, False),
        # Nine-digit and ten-to-thirteen-digit runs are already redacted at every tier
        # (SSN and phone patterns), so the tier does not move; crossing is refused.
        ("The confirmation is 300001431 on the check stub.", PUBLIC, False),
        ("The confirmation is 3000014313 on the check stub.", PUBLIC, False),
        ("Discovery set lives under /mnt/e/OpenClawLegalPrivate/matter", MAX, False),
        # Already redacted by the always-on token patterns at the front door, so the
        # tier does not move; the projection still refuses them.
        ("Reach the accountant at accounts@example.org before Friday.", PUBLIC, False),
        ("Call 443 758 4913 when the truck arrives.", PUBLIC, False),
        ("Card on file 4111 1111 1111 1111 expires next year.", PUBLIC, False),
        ("Routing number 021000021 goes on the direct deposit form.", PUBLIC, False),
        ("Booked through Capital Hilton for the fall run.", PUBLIC, False),
    ],
)
def test_visible_content_decides_tier_and_crossing(text: str, tier: str, may_cross: bool) -> None:
    assert detect_pii_tier(text, None) == tier
    assert content_may_cross_public(text) is may_cross


def test_keyword_cue_never_lowers_an_unredactable_floor() -> None:
    # "invoice" alone is MED; a bare 8-digit run in the same sentence is HIGH.
    assert detect_pii_tier("invoice reference 30000143 is attached", None) == HIGH
    # "paid" alone is LIGHT; a street address in the same sentence is MED.
    assert detect_pii_tier("paid at 412 Oak St on Tuesday", None) == MED


def test_keyword_cue_still_acts_as_a_floor() -> None:
    assert detect_pii_tier("The tax id is on file.", None) == HIGH
    assert detect_pii_tier("Put it on the calendar for the meeting.", None) == MED
    assert detect_pii_tier("It was paid last week.", None) == LIGHT


def test_labelled_account_stays_light_because_it_is_tokenized() -> None:
    # Matches the front-door contract: the number is redacted by the ACCOUNT token
    # pattern at every tier, so the finance keyword alone sets the tier.
    text = "In finance context, check the ledger account 123456789012 against Capital Hilton."
    assert detect_pii_tier(text, None) == LIGHT
    assert content_may_cross_public(text) is False


def test_packet_privacy_tiers_still_win() -> None:
    packet = {"privacy": {"tiers_present": ["MAX"]}, "packet_text": "harmless"}
    assert detect_pii_tier("harmless", packet) == MAX


def test_operator_name_list_is_optional_and_out_of_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sentence = "Annette said the PO will post on Thursday."
    monkeypatch.delenv(PII_NAME_LIST_ENV, raising=False)
    assert detect_pii_tier(sentence, None) == PUBLIC
    assert content_may_cross_public(sentence) is True

    names = tmp_path / "names.txt"
    names.write_text("# people who must never cross in the clear\nAnnette\n\n", encoding="utf-8")
    monkeypatch.setenv(PII_NAME_LIST_ENV, str(names))
    assert detect_pii_tier(sentence, None) == MED
    assert content_may_cross_public(sentence) is False

    monkeypatch.setenv(PII_NAME_LIST_ENV, str(tmp_path / "missing.txt"))
    assert detect_pii_tier(sentence, None) == PUBLIC


def _project(value: str) -> dict:
    fact = {
        "fact_id": "product_artifact:abc123",
        "provenance": "governed_product_artifact",
        "source_ref": "fleet_coord/PRODUCT/PRODUCT-PUBLIC-BRIEF-20260728.md",
        "freshness": {"sha256": "sha256:4270f9b4db346afaaed6a7beb", "as_of": "2026-07-28T00:00:00Z"},
        "pii_tier": "PUBLIC",
        "topic": "product_artifact",
        "label": "note",
        "value": value,
    }
    return orp._lm1_interpreter_context_packet({"facts": [fact], "packet_id": "p"})


@pytest.mark.parametrize(
    "value",
    [
        "Megan prefers Tuesday load-ins at 412 Oak St.",
        "Call 443 758 4913 when the truck arrives.",
        "Routing number 021000021 goes on the direct deposit form.",
        "Reach the accountant at accounts@example.org before Friday.",
        "Booked through Capital Hilton for the fall run.",
        "Full rig is $1,125 a night.",
    ],
)
def test_projection_blocks_content_the_keywords_missed(value: str) -> None:
    projected = _project(value)
    assert not projected.get("facts"), value
    assert value not in str(projected)


def test_projection_still_passes_clean_public_content() -> None:
    value = "Dispatch is not delivery. A signal emitted is not a signal received."
    projected = _project(value)
    assert projected.get("facts"), "a clean PUBLIC fact was blocked"
    assert value in str(projected)
