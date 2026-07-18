from __future__ import annotations

import json
from types import SimpleNamespace

import protected_generate as pg
from context_source import make_ledger_provenance
from protected_generate import protected_generate_with_receipt


def test_advisory_fallback_uses_guardian_pending_action_without_claiming_execution():
    answer = pg._fallback_grounded_answer(
        "Maestro, what do you think the next correct step is?",
        {
            "facts": [
                {
                    "topic": "pending_operator_action",
                    "label": "Current Guardian approval waiting for the operator",
                    "value": "Action 5FF438AC is WAITING_FOR_APPROVAL and has not executed.",
                    "source_ref": "hitl_pending_store:5FF438AC",
                }
            ]
        },
    )

    assert "Guardian action 5FF438AC" in answer
    assert "next correct step" in answer
    assert "Nothing has been sent" in answer
    assert "approve that one action" in answer
    assert "approved" not in answer.lower()


def test_advisory_send_recommendation_is_discarded_while_send_hold_active(tmp_path):
    outcome = protected_generate_with_receipt(
        "Maestro, what do you think the next correct step is?",
        context_packet={
            "facts": [
                {
                    "topic": "current_guardian_action",
                    "label": "Current Guardian decision with execution unproven",
                    "value": "Action 5FF438AC records APPROVED; execution is not proven.",
                    "source_ref": "hitl_pending_store:5FF438AC",
                    "provenance": "guardian_pending_action_owner",
                    "ledger_provenance": make_ledger_provenance(
                        source_table="packet_builder_context",
                        source_id="current_guardian_action:5FF438AC",
                    ),
                    "decision_status": "APPROVED",
                }
            ]
        },
        generator_fn=lambda _prompt, **_kwargs: "Fix that draft and send it off.",
        audit_log_path=tmp_path / "advisory-send-hold.jsonl",
        allow_live_model=False,
        front_door_profile=True,
        agent="maestro",
    )

    assert outcome.receipt["model_fallback_reason"] == "advisory_send_hold_conflict"
    assert outcome.receipt["model_output_delivered"] is False
    assert "advisory_recommended_send_while_send_hold_active" in outcome.receipt["validation_reasons"]
    assert "does not prove execution" in outcome.text
    assert "not send from this advisory" in outcome.text


def test_advisory_generic_answer_is_discarded_when_current_guardian_state_exists(tmp_path):
    fact = {
        "topic": "current_guardian_action",
        "label": "Current Guardian decision with execution unproven",
        "value": "Action 5FF438AC records APPROVED; execution is not proven.",
        "source_ref": "hitl_pending_store:5FF438AC",
        "provenance": "guardian_pending_action_owner",
        "ledger_provenance": make_ledger_provenance(
            source_table="packet_builder_context",
            source_id="current_guardian_action:5FF438AC",
        ),
        "decision_status": "APPROVED",
    }
    outcome = protected_generate_with_receipt(
        "Maestro, what do you think the next correct step is?",
        context_packet={"facts": [fact]},
        generator_fn=lambda _prompt, **_kwargs: "Keep things moving and stay focused.",
        audit_log_path=tmp_path / "advisory-generic.jsonl",
        allow_live_model=False,
        front_door_profile=True,
        agent="maestro",
    )

    assert outcome.receipt["model_fallback_reason"] == "advisory_current_state_omitted"
    assert outcome.receipt["model_output_delivered"] is False
    assert "advisory_omitted_current_guardian_action_state" in outcome.receipt["validation_reasons"]
    assert "Guardian action 5FF438AC" in outcome.text
    assert "does not prove execution" in outcome.text


def test_advisory_current_decision_requires_concrete_verify_step(tmp_path):
    fact = {
        "topic": "current_guardian_action",
        "label": "Current Guardian decision with execution unproven",
        "value": "Action 5FF438AC records APPROVED; execution is not proven.",
        "source_ref": "hitl_pending_store:5FF438AC",
        "provenance": "guardian_pending_action_owner",
        "ledger_provenance": make_ledger_provenance(
            source_table="packet_builder_context",
            source_id="current_guardian_action:5FF438AC",
        ),
        "decision_status": "APPROVED",
    }
    outcome = protected_generate_with_receipt(
        "Maestro, what do you think the next correct step is?",
        context_packet={"facts": [fact]},
        generator_fn=lambda _prompt, **_kwargs: (
            "A decision is recorded, but execution hasn't proven yet. SEND_HOLD remains."
        ),
        audit_log_path=tmp_path / "advisory-incomplete-step.jsonl",
        allow_live_model=False,
        front_door_profile=True,
        agent="maestro",
    )

    assert outcome.receipt["model_fallback_reason"] == "advisory_current_state_omitted"
    assert "advisory_omitted_current_guardian_action_state" in outcome.receipt["validation_reasons"]
    assert "verify the signed action and current authority" in outcome.text


def test_advisory_current_state_gets_one_bounded_same_model_repair(tmp_path):
    fact = {
        "topic": "current_guardian_action",
        "label": "Current Guardian decision with execution unproven",
        "value": "Action 5FF438AC records APPROVED; execution is not proven.",
        "source_ref": "hitl_pending_store:5FF438AC",
        "provenance": "guardian_pending_action_owner",
        "ledger_provenance": make_ledger_provenance(
            source_table="packet_builder_context",
            source_id="current_guardian_action:5FF438AC",
        ),
        "decision_status": "APPROVED",
    }
    outputs = iter(
        [
            "Keep things moving and stay focused.",
            (
                "A decision is recorded, but execution is not proven. SEND_HOLD remains; "
                "the next step is to verify the signed action and current authority."
            ),
        ]
    )
    calls = []

    def generator(prompt, **_kwargs):
        calls.append(prompt)
        return next(outputs)

    outcome = protected_generate_with_receipt(
        "Maestro, what do you think the next correct step is?",
        context_packet={"facts": [fact]},
        generator_fn=generator,
        audit_log_path=tmp_path / "advisory-repair.jsonl",
        allow_live_model=False,
        front_door_profile=True,
        agent="maestro",
    )

    assert len(calls) == 2
    assert "ADVISORY REPAIR PASS" in calls[1]
    assert outcome.receipt["model_fallback_reason"] == "model_ok"
    assert outcome.receipt["model_output_delivered"] is True
    assert outcome.receipt["advisory_repair_attempted"] is True
    assert outcome.receipt["advisory_repair_succeeded"] is True
    assert outcome.text.startswith("A decision is recorded")


def test_advisory_overloaded_approved_word_is_rephrased_under_send_hold(tmp_path):
    fact = {
        "topic": "current_guardian_action",
        "label": "Current Guardian decision with execution unproven",
        "value": "Action 5FF438AC records APPROVED; execution is not proven.",
        "source_ref": "hitl_pending_store:5FF438AC",
        "provenance": "guardian_pending_action_owner",
        "ledger_provenance": make_ledger_provenance(
            source_table="packet_builder_context",
            source_id="current_guardian_action:5FF438AC",
        ),
        "decision_status": "APPROVED",
    }
    outcome = protected_generate_with_receipt(
        "Maestro, what do you think the next correct step is?",
        context_packet={"facts": [fact]},
        generator_fn=lambda _prompt, **_kwargs: (
            "Guardian action 5FF438AC is approved, but execution is not proven and SEND_HOLD remains."
        ),
        audit_log_path=tmp_path / "advisory-approved-word.jsonl",
        allow_live_model=False,
        front_door_profile=True,
        agent="maestro",
    )

    assert outcome.receipt["model_fallback_reason"] == "advisory_approval_wording_conflict"
    assert "advisory_used_overloaded_approved_word" in outcome.receipt["validation_reasons"]
    assert "approved" not in outcome.text.lower()
    assert "has a recorded decision" in outcome.text


def test_frontdoor_discards_canned_revoice_that_loses_semantic_marker(tmp_path):
    outcome = protected_generate_with_receipt(
        "Rephrase this canned truth in your own natural voice: "
        "The review packet is ready and nothing was changed.",
        context_packet={"facts": []},
        generator_fn=lambda _prompt, **_kwargs: "The packet's ready.",
        audit_log_path=tmp_path / "revoice-drift.jsonl",
        allow_live_model=False,
        front_door_profile=True,
        agent="chief",
    )

    assert outcome.receipt["model_fallback_reason"] == "revoice_semantic_drift"
    assert outcome.receipt["model_output_delivered"] is False
    assert "missing_revoice_marker:review_packet" in outcome.receipt["validation_reasons"]
    assert "missing_revoice_marker:no_change" in outcome.receipt["validation_reasons"]
    assert "couldn't safely revoice" in outcome.text


def test_frontdoor_discards_verbatim_canned_revoice_echo(tmp_path):
    outcome = protected_generate_with_receipt(
        "Rephrase this canned truth in your own natural voice: "
        "The review packet is ready and nothing was changed.",
        context_packet={"facts": []},
        generator_fn=lambda _prompt, **_kwargs: (
            "The review packet is ready, and nothing was changed."
        ),
        audit_log_path=tmp_path / "revoice-verbatim.jsonl",
        allow_live_model=False,
        front_door_profile=True,
        agent="hermes",
    )

    assert outcome.receipt["model_fallback_reason"] == "revoice_semantic_drift"
    assert "revoice_violation:verbatim_source_echo" in outcome.receipt["validation_reasons"]
    assert outcome.receipt["model_output_delivered"] is False


def test_frontdoor_repairs_canned_revoice_once_with_same_generator(tmp_path):
    outputs = iter(
        [
            "The packet's ready.",
            "The review packet's ready. Nothing was touched.",
        ]
    )
    calls = []

    def generator(prompt, **_kwargs):
        calls.append(prompt)
        return next(outputs)

    outcome = protected_generate_with_receipt(
        "Rephrase this canned truth in your own natural voice: "
        "The review packet is ready and nothing was changed.",
        context_packet={"facts": []},
        generator_fn=generator,
        audit_log_path=tmp_path / "revoice-repair.jsonl",
        allow_live_model=False,
        front_door_profile=True,
        agent="chief",
    )

    assert len(calls) == 2
    assert "REPAIR PASS" in calls[1]
    assert outcome.text == "The review packet's ready. Nothing was touched."
    assert outcome.receipt["model_fallback_reason"] == "model_ok"
    assert outcome.receipt["model_output_delivered"] is True
    assert outcome.receipt["revoice_repair_attempted"] is True
    assert outcome.receipt["revoice_repair_succeeded"] is True


def test_maestro_system_prompt_includes_perspective_without_new_authority(tmp_path):
    captured: dict[str, str] = {}

    def generator(system_prompt: str, **_kwargs) -> str:
        captured["system_prompt"] = system_prompt
        return "Winship is the human operator."

    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet={
            "facts": [
                {
                    "topic": "identity",
                    "label": "operator",
                    "value": "Winship is the human operator.",
                }
            ]
        },
        generator_fn=generator,
        audit_log_path=tmp_path / "protected_generate_audit.jsonl",
        allow_live_model=False,
    )

    system_prompt = captured["system_prompt"]
    assert outcome.status == "ANSWER_READY"
    assert outcome.receipt["route"] == "injected_generator"
    assert 'First-person words ("I", "me", "my", "mine", "myself") refer only to Maestro.' in system_prompt
    assert 'The human operator is Winship. Address him as "you" or refer to him as "Winship".' in system_prompt
    assert "Maestro must never use first-person words to mean Winship" in system_prompt
    assert "Never claim send/spend/mutation authority." in system_prompt
    assert "DETERMINISTIC PACKET:" in system_prompt


def test_protected_generate_receipt_includes_agent_default_and_override(tmp_path):
    def generator(_system_prompt: str, **_kwargs) -> str:
        return "Grounded answer."

    default_outcome = protected_generate_with_receipt(
        "Say something grounded.",
        context_packet={"facts": [{"topic": "status", "label": "Grounded", "value": "Grounded answer."}]},
        generator_fn=generator,
        audit_log_path=tmp_path / "default.jsonl",
        allow_live_model=False,
    )
    guardian_outcome = protected_generate_with_receipt(
        "Say something grounded.",
        context_packet={"facts": [{"topic": "status", "label": "Grounded", "value": "Grounded answer."}]},
        generator_fn=generator,
        audit_log_path=tmp_path / "guardian.jsonl",
        allow_live_model=False,
        front_door_profile=True,
        agent="guardian",
    )

    assert default_outcome.receipt["agent"] == "maestro"
    assert guardian_outcome.receipt["agent"] == "guardian"


def test_external_brain_shadow_is_absent_by_default(tmp_path):
    outcome = protected_generate_with_receipt(
        "Give me the grounded status.",
        context_packet={"facts": [{"topic": "status", "label": "State", "value": "All local."}]},
        generator_fn=lambda _prompt, **_kwargs: "All local.",
        audit_log_path=tmp_path / "default-off.jsonl",
        allow_live_model=False,
    )

    assert "external_brain_shadow" not in outcome.receipt
    assert outcome.receipt["external_llm_invoked"] is False


def test_external_brain_shadow_receipt_sits_beside_unchanged_local_answer(tmp_path):
    raw_prompt = "Keep this exact marker out of receipts: OPERATOR-RAW-7391."
    outcome = protected_generate_with_receipt(
        raw_prompt,
        context_packet={
            "package_minimized": True,
            "facts": [{"topic": "status", "label": "State", "value": "Local answer."}],
        },
        generator_fn=lambda _prompt, **_kwargs: "Local answer.",
        audit_log_path=tmp_path / "shadow.jsonl",
        allow_live_model=False,
        external_brain_shadow=True,
    )

    shadow = outcome.receipt["external_brain_shadow"]
    assert outcome.text == "Local answer."
    assert outcome.receipt["external_llm_invoked"] is False
    assert shadow["effective_lane_id"] == "local_safe_lane"
    assert shadow["fallback_reason"] == "external_router_default_off"
    assert shadow["mode"] == "shadow_only_no_external_call"
    assert shadow["request_hash"].startswith("sha256:")
    assert "OPERATOR-RAW-7391" not in json.dumps(shadow)


def test_active_external_brain_router_is_wired_into_protected_generate(monkeypatch, tmp_path):
    observed: dict = {}
    monkeypatch.setenv("OPENCLAW_EXTERNAL_BRAIN_ROUTER", "1")

    def fake_external_attempt(**kwargs):
        observed.update(kwargs)
        return SimpleNamespace(
            source="external_brain",
            text="External wired answer.",
            receipt={"schema_version": "external_brain_route_receipt_v1", "request_hash": "sha256:test"},
        )

    monkeypatch.setattr(pg, "_external_brain_live_attempt", fake_external_attempt)
    outcome = protected_generate_with_receipt(
        "My exact live prompt?!",
        context_packet={
            "package_minimized": True,
            "facts": [{"topic": "status", "label": "State", "value": "Public fact."}],
        },
        generator_fn=None,
        audit_log_path=tmp_path / "external-live.jsonl",
        allow_live_model=True,
        front_door_profile=False,
    )

    assert outcome.text == "External wired answer."
    assert outcome.receipt["route"] == "external_brain_router"
    assert outcome.receipt["external_llm_invoked"] is True
    assert outcome.receipt["local_model_invoked"] is False
    assert outcome.receipt["external_brain"]["request_hash"] == "sha256:test"
    assert observed["raw_operator_prompt"] == "My exact live prompt?!"


def test_active_external_refusal_immediately_continues_existing_local_path(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENCLAW_EXTERNAL_BRAIN_ROUTER", "1")
    monkeypatch.setattr(
        pg,
        "_external_brain_live_attempt",
        lambda **_kwargs: SimpleNamespace(
            source="local_fallback",
            text="",
            receipt={
                "schema_version": "external_brain_route_receipt_v1",
                "fallback_reason": "guardian_approval_required",
            },
        ),
    )
    monkeypatch.setattr(pg, "_call_local_ollama", lambda *_args, **_kwargs: "Existing local answer.")

    outcome = protected_generate_with_receipt(
        "Public status please.",
        context_packet={
            "package_minimized": True,
            "facts": [{"topic": "status", "label": "State", "value": "Public fact."}],
        },
        generator_fn=None,
        audit_log_path=tmp_path / "external-fallback.jsonl",
        allow_live_model=True,
        front_door_profile=False,
    )

    assert outcome.text == "Existing local answer."
    assert outcome.receipt["route"] == "local_ollama"
    assert outcome.receipt["external_llm_invoked"] is False
    assert outcome.receipt["local_model_invoked"] is True
    assert outcome.receipt["external_brain"]["fallback_reason"] == "guardian_approval_required"


from protected_generate import _fallback_grounded_answer


def test_finance_intent_grounded_answer():
    packet = {
        "facts": [
            {
                "topic": "calendar_day",
                "label": "gig count",
                "value": "Two gigs today, neither about invoices.",
            },
            {
                "topic": "finance_candidate_count",
                "label": "candidate noise",
                "value": "A non-authoritative candidate says three invoices might exist.",
            },
            {
                "topic": "finance_invoice_reconciliation",
                "label": "Capital Hilton",
                "value": "Capital Hilton receivable is $2,000 and marked payment received.",
            },
            {
                "topic": "invoice_status",
                "label": "AR status",
                "value": "No unpaid invoices are ready for send or ledger mutation.",
            },
        ]
    }

    answer = _fallback_grounded_answer("what's owed on invoices?", packet)

    assert "Capital Hilton receivable is $2,000" in answer
    assert "No unpaid invoices are ready" in answer
    assert "Two gigs today" not in answer
    assert "non-authoritative candidate" not in answer


def test_payment_status_question_classifies_to_finance_not_contacts():
    """Task 137: "did X pay us?" is a payment-status QUESTION -- 'pay'/'paid' were missing
    from _FINANCE_INTENT_MARKERS, so it fell through to the generic scored-facts path, which
    favored a contacts_registry fact over the actual finance answer."""
    packet = {
        "facts": [
            {
                "topic": "contacts_registry",
                "label": "Draper Carter",
                "value": "Draper Carter is a contacts_registry contact for st-annes; role: St. Anne's primary contact.",
            },
            {
                "topic": "finance_invoice_reconciliation",
                "label": "Current money owed answer topic",
                "value": "St Anne's Apr/May paid; current invoice ready to send once copy is fixed.",
            },
        ]
    }

    answer = _fallback_grounded_answer("did St Anne's pay us?", packet)

    assert "current invoice ready to send once copy is fixed" in answer
    assert "contacts_registry contact" not in answer


from protected_generate import _clean_answer_value


def test_clean_answer_value_preserves_abbreviation_periods():
    """Task 137: the sentence splitter mangled 'St. Anne's primary contact; forwards...'
    into 'St; Anne's primary contact; forwards...' -- treating the 'St.' abbreviation as a
    sentence boundary. Must preserve it while still splitting on the genuine semicolon."""
    value = "St. Anne's primary contact; forwards invoice/payment details to Glen."

    cleaned = _clean_answer_value(value)

    assert "St; Anne's" not in cleaned
    assert cleaned.startswith("St. Anne's primary contact")
    assert "forwards invoice/payment details to Glen" in cleaned


def test_clean_answer_value_still_splits_genuine_sentences():
    value = "First fact here. Second fact here; third clause here."

    cleaned = _clean_answer_value(value)

    assert cleaned == "First fact here; Second fact here; third clause here"


def test_schedule_intent_still_uses_calendar_only():
    packet = {
        "facts": [
            {
                "topic": "finance_invoice_reconciliation",
                "label": "Capital Hilton",
                "value": "Capital Hilton has $400 tied to next Friday gigs.",
            },
            {
                "topic": "calendar_day",
                "label": "today",
                "value": "Two rehearsals and one load-in are on the calendar today.",
            },
        ]
    }

    answer = _fallback_grounded_answer("how many gigs do I have today?", packet)

    assert "Two rehearsals and one load-in" in answer
    assert "Capital Hilton" not in answer
