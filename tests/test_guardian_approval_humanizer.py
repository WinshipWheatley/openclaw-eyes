"""Guardian approvals read like a human wrote them, not a machine contract.

Operator ask 2026-07-03: "his last message is too machine-contract-y ... I need a human
ELI5 so I can digest what it's asking and not just throw my hands up and hit approve."
The humanizer states, in plain English: what this is, what happens if you approve, what
happens if you deny, and the risk — with NO raw JSON, field names, hashes, or IDs (beyond
a short ref). Facts are extracted deterministically so the humanization can never
misrepresent what's actually being approved.
"""

import guardian_approval_humanizer as gah


def _email_approval():
    return {
        "id": "AB12CD34", "requester": "Cassandra", "tier": 2, "risk_tier": "tier_2",
        "action": "Send invoice email to Capital Hilton",
        "approval_context": {
            "action_label": "gmail send", "to": "ap@capitalhilton.com",
            "subject": "Invoice — June performance", "draft_preview": "Hi, attached is the invoice...",
        },
    }


def _build_approval():
    return {
        "approval_id": "T-9910", "source_surface_id": "hermes_fleet_loop",
        "action_summary_label": "Hermes wants to add a retry to the polish runner",
        "risk_tier": "tier_1", "status": "request_shadow_created",
    }


def test_email_approval_is_plain_english_no_machine_contract():
    h = gah.humanize_approval(_email_approval())
    text = h["headline"] + " " + h["plain"]
    assert "email" in text.lower()
    assert "Capital Hilton" in text or "capitalhilton" in text.lower()
    # no machine artifacts anywhere in the human message
    for artifact in ("action_label", "approval_context", "risk_tier", "{", "}", "tier_2", "sha256"):
        assert artifact not in (h["headline"] + h["plain"] + h["if_approve"] + h["if_deny"] + h["risk"])
    assert h["if_approve"] and h["if_deny"]


def test_email_approve_deny_are_concrete():
    h = gah.humanize_approval(_email_approval())
    assert "send" in h["if_approve"].lower()
    assert "won't" in h["if_deny"].lower() or "not" in h["if_deny"].lower()


def test_build_request_humanized():
    h = gah.humanize_approval(_build_approval())
    text = (h["headline"] + " " + h["plain"]).lower()
    assert "build" in text or "add" in text or "change" in text
    assert "hermes" in text
    assert "code" in h["if_approve"].lower() or "build" in h["if_approve"].lower()


def test_generic_approval_never_leaks_raw_fields():
    approval = {"id": "X1", "action": "Do the thing", "requester": "chief", "tier": 2}
    h = gah.humanize_approval(approval)
    assert "Do the thing" in (h["headline"] + h["plain"])
    assert "{" not in h["plain"] and "}" not in h["plain"]


def test_risk_is_stated_in_plain_words():
    h = gah.humanize_approval(_email_approval())
    # tier_2 -> a plain risk sentence, not the token
    assert h["risk"]
    assert "tier_2" not in h["risk"]


def test_short_ref_present_for_traceability():
    h = gah.humanize_approval(_email_approval())
    # a short ref is fine (so operator/Fable can trace it) but not a long hash
    assert h["ref"] == "AB12CD34"


def test_render_telegram_is_clean_and_has_no_json():
    h = gah.humanize_approval(_email_approval())
    msg = gah.render_operator_message(h)
    assert "Cassandra" in msg
    assert '"' not in msg or msg.count('"') < 4   # no JSON-ish key quoting
    assert "approval_context" not in msg
