from __future__ import annotations

from datetime import datetime, timezone

from clara_invoice_copy_composer import compose_invoice_copy


ASK = "Punch up the July Live Arts invoice email in Clara's voice."
CLOSING_ASK = "Could you send me a quick note once the invoice is in your accounting queue?"
CLOSING_WHY = "That helps me know it landed and keeps our records straight."
SIGNOFF = "Warmly,\nClara Reid"


def _packet() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "packet_id": "clara-test-packet",
        "facts": [
            {
                "fact_id": "invoice",
                "topic": "invoice",
                "value": "Invoice 2026-1004 is for July 2026 and $100.",
                "source_ref": "fixture:invoice",
                "provenance": "fixture",
                "freshness": {"as_of": now, "source_ref": "fixture:invoice"},
            },
            {
                "fact_id": "recipient",
                "topic": "recipient",
                "value": "Megan Rivas receives the invoice in the accountant inbox.",
                "source_ref": "fixture:recipient",
                "provenance": "fixture",
                "freshness": {"as_of": now, "source_ref": "fixture:recipient"},
            },
            {
                "fact_id": "attachment",
                "topic": "attachment",
                "value": "The validated PDF is attached.",
                "source_ref": "fixture:attachment",
                "provenance": "fixture",
                "freshness": {"as_of": now, "source_ref": "fixture:attachment"},
            },
            {
                "fact_id": "milestone",
                "topic": "workflow",
                "value": "Ask for a note when it reaches the accounting queue.",
                "source_ref": "fixture:milestone",
                "provenance": "fixture",
                "freshness": {"as_of": now, "source_ref": "fixture:milestone"},
            },
        ],
    }


def _contract() -> dict:
    return {
        "client_ref": "live_arts_md",
        "workflow_ref": "live_arts_md_invoice_workflow",
        "greeting": "Hi Megan,",
        "canonical_subject": "2026-1004: July 2026 Monthly Speaker Rental Invoice",
        "canonical_signoff": SIGNOFF,
        "required_subject_atoms": ("2026-1004",),
        "required_body_atoms": (
            "July 2026",
            "$100",
        ),
        "exactly_once_body_atoms": (
            "Hi Megan,",
            CLOSING_ASK,
            CLOSING_WHY,
        ),
        "forbidden_claims": ("already sent",),
        "copy_fact_citations": ("fixture:invoice", "fixture:recipient", "fixture:attachment"),
    }


def test_compose_rejects_machine_copy_and_selects_voice_conformant_take() -> None:
    outputs = iter(
        (
            {
                "text": '{"subject":"Invoice 2026-1004","body":"Hi Megan,\\n\\nThe packet and artifact hash are approved.\\n\\n'
                + CLOSING_ASK
                + " "
                + CLOSING_WHY
                + '\\n\\nWarmly,\\nClara Reid"}',
                "model": "fixture-small",
            },
            {
                "text": '{"subject":"Live Arts MD invoice 2026-1004 - July 2026","body":"Hi Megan,\\n\\nI have Winship\'s July 2026 speaker rental invoice for $100 attached. It was a pleasure getting this month\'s details together for you.\\n\\n'
                + CLOSING_ASK
                + " "
                + CLOSING_WHY
                + '\\n\\nWarmly,\\nClara Reid"}',
                "model": "fixture-small",
            },
            {
                "text": '{"subject":"Invoice 2026-1004","body":"Hi Megan,\\n\\nAttached is Invoice 2026-1004 for the July 2026 monthly speaker rental, totaling $100.\\n\\n'
                + CLOSING_ASK
                + " "
                + CLOSING_WHY
                + '\\n\\nWarmly,\\nClara Reid"}',
                "model": "fixture-small",
            },
        )
    )

    result = compose_invoice_copy(
        ASK,
        _packet(),
        _contract(),
        generator_fn=lambda _prompt: next(outputs),
    )

    assert result["selected_attempt"] == 3
    assert result["selected_model"] == "fixture-small"
    assert result["subject"] == "2026-1004: July 2026 Monthly Speaker Rental Invoice"
    assert result["attempts"][0]["accepted"] is False
    assert any("forbidden_claim:packet" in reason for reason in result["attempts"][0]["violations"])
    assert any(
        "voice:persona_fidelity_anti_pattern:" in reason
        for reason in result["attempts"][1]["violations"]
    )
    assert result["voice_conformance"]["passed"] is True
    assert result["critic_score"]["overall"] == 1.0
    assert result["critic_score"]["client_surface_clean"] == 1.0
    assert result["critic_score"]["persona_fidelity"] == 1.0
    assert result["packet_score"]["overall"] == 1.0
    assert result["authority_boundary"]["email_send_performed"] is False
