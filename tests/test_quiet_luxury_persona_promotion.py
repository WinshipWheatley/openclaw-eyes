from __future__ import annotations

from pathlib import Path


DOCTRINE_PATH = Path("docs/doctrine/CLARA_CASSANDRA_QUIET_LUXURY.md")
CRITIC_DIMENSIONS = {
    "understatement",
    "no_false_intimacy",
    "easy_to_decline",
    "screenshot_test",
    "severity_integrity",
    "lowest_intensity_tone",
    "organized_not_stranger",
    "persona_fidelity",
    "client_surface_clean",
}


def test_signed_design_doc_is_the_single_machine_readable_canon() -> None:
    from quiet_luxury_doctrine import load_quiet_luxury_contract

    contract = load_quiet_luxury_contract()
    text = DOCTRINE_PATH.read_text(encoding="utf-8")

    assert contract["schema_version"] == "quiet_luxury_persona_contract_v1"
    assert contract["doctrine_ref"] == "quiet_luxury:clara_cassandra:v1"
    assert contract["canonical_external_name"] == "Clara Reid"
    assert contract["flows"]["clara"] == ["Recognize", "Clarify", "Guide", "Confirm"]
    assert contract["progressive_disclosure"] == ["Velvet", "Concierge", "Steel"]
    assert set(contract["critic_dimensions"]) == CRITIC_DIMENSIONS
    assert "SYSTEM-QUIET-LUXURY-DOCTRINE-SOURCE.md" in text
    assert "Status: ACTIVE - operator first-class pass granted" in text
    assert 'Operator first-class pass signature: Telegram msg 1833 "Do it"' in text
    assert "Clara Ried" not in text


def test_terminology_is_context_sensitive_and_preserves_severity_and_money_truth() -> None:
    from openclaw_terminology_adapter import translate_terms

    assert translate_terms(
        "BLOCKED_PENDING_APPROVAL",
        target_layer="client",
        context="client_correspondence",
    ) == "Pending final confirmation"
    assert translate_terms(
        "FAILED_SEND",
        target_layer="client",
        context="client_correspondence",
    ).startswith("FAILED_SEND:")
    assert translate_terms(
        "Project price is $4,800.",
        target_layer="client",
        context="proposal_pricing",
    ) == "Project price is Project investment: $4,800 / Total price: $4,800."
    assert translate_terms(
        "Invoice total is $100.",
        target_layer="client",
        context="invoice_total",
    ) == "Invoice total is $100."


def test_renderer_keeps_critical_truth_in_velvet_and_steel() -> None:
    from openclaw_lux_renderer import render_packet_result

    rendered = render_packet_result(
        {
            "summary": "Delivery needs attention.",
            "facts": ["FAILED_SEND", "2026-07-17", "$100"],
            "recommended_move": "Verify the recipient before retrying.",
        },
        target_agent="maestro",
    )

    assert rendered.sections == ("Velvet", "Concierge", "Steel")
    assert "FAILED_SEND" in rendered.text
    assert "2026-07-17" in rendered.text
    assert "$100" in rendered.text
    assert rendered.machine_proof()["severity_integrity_passed"] is True


def test_clara_critic_enforces_named_dimensions_and_concierge_flow() -> None:
    from quiet_luxury_doctrine import evaluate_quiet_luxury_copy

    good = evaluate_quiet_luxury_copy(
        "clara",
        (
            "Hi Megan,\n\n"
            "Attached is Invoice 2026-1004 for the July 2026 monthly speaker rental, totaling $100.\n\n"
            "Could you send me a quick note once the invoice is in your accounting queue? "
            "That helps me know it landed and keeps our records straight.\n\n"
            "Warmly,\nClara Reid"
        ),
        surface="client_email",
    )
    bad = evaluate_quiet_luxury_copy(
        "clara",
        "I hope your week is going well! I'm happy to help with anything else.",
        surface="client_email",
    )

    assert set(good["dimensions"]) == CRITIC_DIMENSIONS
    assert all(score == 1.0 for score in good["dimensions"].values())
    assert good["flow"] == {
        "Recognize": True,
        "Clarify": True,
        "Guide": True,
        "Confirm": True,
    }
    assert bad["passed"] is False
    assert bad["dimensions"]["no_false_intimacy"] == 0.0
    assert bad["dimensions"]["lowest_intensity_tone"] == 0.0


def test_client_surface_term_guard_uses_token_boundaries() -> None:
    from quiet_luxury_doctrine import evaluate_quiet_luxury_copy

    result = evaluate_quiet_luxury_copy(
        "clara",
        "No mischief here; the invoice details are in order.",
    )

    assert result["dimensions"]["client_surface_clean"] == 1.0
