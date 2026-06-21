from __future__ import annotations

import json
import time
from pathlib import Path


def _truth_store(monkeypatch, tmp_path: Path) -> Path:
    store_path = tmp_path / "operator_truth_store.json"
    seed_path = tmp_path / "OPERATOR-TRUTH-20260619-evening.md"
    seed_path.write_text(
        "\n".join(
            [
                "# operator truth seed",
                "Capital Hilton: $2000 received; July 1 check; $400 gigs; next Friday.",
                "St Anne's all paid up.",
                "Live Arts MD owes for Draper follow-up work.",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_STORE", str(store_path))
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_SEED", str(seed_path))
    return store_path


def _read_models(tmp_path: Path) -> Path:
    root = tmp_path / "read_models"
    root.mkdir()
    (root / "agent_presence.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-20T10:00:00+00:00",
                "agents": [
                    {"agent_id": "cassandra", "display_name": "Cassandra", "actual_state": "online"},
                    {"agent_id": "chief", "display_name": "Chief", "actual_state": "online"},
                ],
                "next_safe_move": "Review the Maestro packet before any runtime action.",
            }
        ),
        encoding="utf-8",
    )
    (root / "openclaw_capability_index.json").write_text(
        json.dumps(
            {
                "generic_capabilities": [
                    {
                        "capability_id": "request_processing",
                        "capability_name": "Bounded request processor",
                        "capability_status": "LIVE_IMPLEMENTED",
                    },
                    {
                        "capability_id": "invoice_readback",
                        "capability_name": "Invoice status readback",
                        "capability_status": "READ_MODEL_ONLY",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (root / "chief_status_rail.json").write_text(
        json.dumps({"chief_current_status": "safe_status_read_model_only"}),
        encoding="utf-8",
    )
    (root / "openclaw_change_sentinel.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-20T10:01:00+00:00",
                "hermes_summary": {"what_changed": "No material change.", "what_to_do_next": "Continue."},
            }
        ),
        encoding="utf-8",
    )
    (root / "finance_invoice_reconciliation.json").write_text(
        json.dumps(
            {
                "counts": {"finance_candidate_count": 3, "high_risk_count": 1},
                "first_safe_workflow_proposal": {
                    "operator_summary": "Draft invoice context packets are ready; sending remains blocked."
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "cassandra_email_calendar_delta_detangle.json").write_text(
        json.dumps(
            {
                "calendar_operator_context": {
                    "google_apple_calendar_merged_context_recorded": True,
                    "live_calendar_access_enabled": False,
                },
                "classification_counts": {"DRAFT_PREVIEW_ONLY": 1, "EMAIL_SEND_BLOCKED": 1},
                "upcoming_calendar_events": [
                    {
                        "title": "Call with Capital Hilton",
                        "start": "2026-06-20T11:00:00-04:00",
                        "end": "2026-06-20T11:30:00-04:00",
                        "location": "phone",
                    },
                    {
                        "summary": "Rehearsal",
                        "date": "2026-06-20",
                        "start_time": "19:00",
                        "end_time": "21:00",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return root


def test_maestro_context_packet_uses_operator_truth_and_read_models(monkeypatch, tmp_path: Path) -> None:
    store_path = _truth_store(monkeypatch, tmp_path)
    read_model_root = _read_models(tmp_path)

    from maestro_context_packet import build_maestro_context_packet, format_maestro_context_packet

    packet = build_maestro_context_packet(
        question="What should I know about invoices and next Friday?",
        read_model_root=read_model_root,
        operator_truth_store_path=store_path,
        require_real_truth=True,
    )
    text = format_maestro_context_packet(packet)

    assert packet["status"] == "READY"
    assert set(packet["privacy"]["tiers_present"]) >= {"LIGHT", "PUBLIC"}
    assert "Capital Hilton" in text
    assert "$2000 was received through Coupa" in text
    assert "St Anne's" in text
    assert "All paid up" in text
    assert "Live Arts MD owes" in text
    assert "2026-06-26" in text
    assert "generated/read_models/agent_presence.json" in packet["source_refs"]
    assert packet["machine_proof"]["operator_truth_store_used"] is True
    assert packet["machine_proof"]["read_model_count"] >= 4


def test_maestro_context_packet_includes_calendar_events_for_day_questions(monkeypatch, tmp_path: Path) -> None:
    store_path = _truth_store(monkeypatch, tmp_path)
    read_model_root = _read_models(tmp_path)

    from maestro_context_packet import build_maestro_context_packet, format_maestro_context_packet

    packet = build_maestro_context_packet(
        question="what does my day look like?",
        read_model_root=read_model_root,
        operator_truth_store_path=store_path,
        require_real_truth=True,
    )
    text = format_maestro_context_packet(packet)
    calendar_facts = [fact for fact in packet["facts"] if fact.get("topic") == "calendar_day"]

    assert calendar_facts
    assert "Call with Capital Hilton" in text
    assert "Rehearsal" in text
    assert "2026-06-20T11:00:00-04:00" in text
    assert any("Call with Capital Hilton" in item for item in packet["actionable"]["upcoming_commitments"])
    assert packet["bounds"]["outbound_send_allowed"] is False
    assert packet["bounds"]["money_movement_allowed"] is False


def test_packet_trim_question_relevant(monkeypatch, tmp_path: Path) -> None:
    store_path = _truth_store(monkeypatch, tmp_path)
    read_model_root = _read_models(tmp_path)

    from maestro_context_packet import SCHEMA_VERSION, build_maestro_context_packet

    packet = build_maestro_context_packet(
        question="what gigs do I have?",
        read_model_root=read_model_root,
        operator_truth_store_path=store_path,
        require_real_truth=True,
    )

    scores = packet["machine_proof"]["fact_relevance_scores"]
    assert packet["schema_version"] == SCHEMA_VERSION
    assert packet["bounds"]["send_hold_absolute"] is True
    assert packet["privacy"]["send_hold_active"] is True
    assert packet["machine_proof"]["question_relevant_fact_trim_applied"] is True
    assert packet["machine_proof"]["fact_count_before_question_trim"] > len(packet["facts"])
    assert len(packet["facts"]) <= 8
    assert all(scores[fact["fact_id"]] > 0 for fact in packet["facts"])
    assert len(packet["packet_text"].encode("utf-8")) < 2000


def test_stub_truth_root_is_rejected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_TEST_STORE", str(tmp_path / "empty_truth.json"))
    empty_root = tmp_path / "empty_read_models"
    empty_root.mkdir()

    from maestro_context_packet import MaestroContextPacketError, build_maestro_context_packet

    try:
        build_maestro_context_packet(read_model_root=empty_root, require_real_truth=True)
    except MaestroContextPacketError as exc:
        assert "real truth inputs" in str(exc)
    else:
        raise AssertionError("stub truth root must fail closed")


def test_ledger_reference_resolves_only_with_finance_context() -> None:
    from maestro_context_packet import resolve_ledger_reference

    ambiguous = resolve_ledger_reference("check the ledger")
    assert ambiguous["status"] == "NEEDS_CLARIFICATION"

    resolved = resolve_ledger_reference("in finance context, check the ledger against invoices")
    assert resolved["status"] == "RESOLVED"
    assert resolved["referent"] == "bank_finance_ledger"
    assert resolved["pii_tier"] == "LIGHT"
    assert resolved["processing_allowed"] is True
    assert resolved["action_allowed"] is False


def test_protected_generate_blocks_raw_legal_and_processes_light_ledger(tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_generator(prompt: str, **_kwargs) -> str:
        calls.append(prompt)
        return "I can see the Capital Hilton ledger readback and the $2000 item. SEND_HOLD stays active."

    from protected_generate import protected_generate_with_receipt

    legal = protected_generate_with_receipt(
        "Review /mnt/c/OpenClawLegalPrivate/legal discovery for the case.",
        context_packet={"privacy": {"legal_discovery_fully_tokenized": False}},
        generator_fn=fake_generator,
        audit_log_path=tmp_path / "audit.jsonl",
    )
    assert legal.status == "BLOCKED"
    assert legal.receipt["model_call_performed"] is False
    assert calls == []

    tokenized_legal = protected_generate_with_receipt(
        "Review [LEGAL_DOC_1] for the case.",
        context_packet={
            "privacy": {"tiers_present": ["MAX"], "legal_discovery_fully_tokenized": True},
            "facts": [{"label": "[LEGAL_ENTITY_1]", "value": "[LEGAL_DOC_1]"}],
        },
        generator_fn=fake_generator,
        audit_log_path=tmp_path / "audit.jsonl",
    )
    assert tokenized_legal.status == "ANSWER_READY"
    assert tokenized_legal.receipt["pii_tier"] == "MAX"
    assert tokenized_legal.receipt["model_call_performed"] is True

    ledger = protected_generate_with_receipt(
        "In finance context, check the ledger account 123456789012 against Capital Hilton.",
        context_packet={"facts": [{"label": "Capital Hilton", "value": "$2000 received"}]},
        generator_fn=fake_generator,
        audit_log_path=tmp_path / "audit.jsonl",
    )
    assert ledger.status == "ANSWER_READY"
    assert ledger.receipt["pii_tier"] == "LIGHT"
    assert ledger.receipt["tokenization_applied"] is True
    assert ledger.receipt["external_llm_invoked"] is False
    assert "123456789012" not in calls[-1]
    assert "Capital Hilton" in ledger.text
    audit_text = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert audit_text.count("\n") == 3
    assert "123456789012" not in audit_text
    assert "OpenClawLegalPrivate" not in audit_text


def test_missing_answer_in_packet_says_do_not_have_it(tmp_path: Path) -> None:
    from protected_generate import protected_generate_with_receipt

    outcome = protected_generate_with_receipt(
        "What is my passport number?",
        context_packet={"facts": [{"label": "Capital Hilton", "value": "$2000 received"}]},
        audit_log_path=tmp_path / "audit.jsonl",
        allow_live_model=False,
    )

    assert outcome.status == "ANSWER_READY"
    assert "I don't have that" in outcome.text
    assert outcome.receipt["model_call_performed"] is False


def test_fallback_capital_hilton_status_is_concise_and_question_targeted(tmp_path: Path) -> None:
    from protected_generate import protected_generate_with_receipt

    outcome = protected_generate_with_receipt(
        "what is my Capital Hilton status?",
        context_packet={
            "packet_id": "packet:test:capital_hilton_concise",
            "facts": [
                {
                    "topic": "operator_truth",
                    "label": "Capital Hilton",
                    "value": "$2000 received through Coupa; July 1 check expected; $400 gigs; next Friday.",
                },
                {
                    "topic": "capability",
                    "label": "Truthful capability posture",
                    "value": "4 live-implemented rails and 6 safe readback/non-executing rails.",
                },
                {
                    "topic": "email_calendar",
                    "label": "Email and calendar bounded posture",
                    "value": "Calendar merged-context recorded: True. Live calendar access enabled: False.",
                },
                {"topic": "operator_truth", "label": "St Anne's", "value": "All paid up."},
            ],
        },
        audit_log_path=tmp_path / "audit.jsonl",
        allow_live_model=False,
    )

    text = outcome.text
    assert outcome.status == "ANSWER_READY"
    assert "Capital Hilton" in text
    assert "$2000" in text
    assert "July 1 check expected" in text
    assert "$400 gigs" in text
    assert "live-implemented" not in text
    assert "Calendar merged-context" not in text
    assert "St Anne" not in text
    assert "next Friday" not in text
    assert "SEND_HOLD" not in text
    assert text.count(".") <= 3
    assert outcome.receipt["model_call_performed"] is False


def test_fallback_day_question_uses_calendar_events_not_posture(tmp_path: Path) -> None:
    from protected_generate import protected_generate_with_receipt

    outcome = protected_generate_with_receipt(
        "what does my day look like?",
        context_packet={
            "packet_id": "packet:test:calendar_day",
            "facts": [
                {
                    "topic": "calendar_day",
                    "label": "Upcoming calendar commitments",
                    "value": "2026-06-20T11:00:00-04:00-2026-06-20T11:30:00-04:00 - Call with Capital Hilton - phone; 2026-06-20 - Rehearsal - 19:00-21:00.",
                },
                {
                    "topic": "email_calendar",
                    "label": "Email and calendar bounded posture",
                    "value": "Calendar merged-context recorded: True. Live calendar access enabled: False.",
                },
            ],
        },
        audit_log_path=tmp_path / "audit.jsonl",
        allow_live_model=False,
    )

    text = outcome.text
    assert outcome.status == "ANSWER_READY"
    assert "Call with Capital Hilton" in text
    assert "Rehearsal" in text
    assert "Calendar merged-context" not in text
    assert "Live calendar access" not in text
    assert outcome.receipt["model_call_performed"] is False


def test_protected_generate_falls_back_after_fast_local_budget(monkeypatch, tmp_path: Path) -> None:
    from protected_generate import protected_generate_with_receipt

    calls: list[dict] = []

    def fake_ollama(prompt: str, *, timeout: float, task_class: str, attempts: int | None = None, **_kwargs) -> str:
        calls.append(
            {
                "timeout": timeout,
                "task_class": task_class,
                "attempts": attempts,
                "prompt_has_capital_hilton": "Capital Hilton" in prompt,
            }
        )
        time.sleep(0.01)
        return ""

    import chief_llm

    monkeypatch.delenv("OPENCLAW_TEST_MODE", raising=False)
    monkeypatch.delenv("OPENCLAW_FREEFORM_CLOUD", raising=False)
    monkeypatch.setenv("OPENCLAW_MAESTRO_BRAIN_LIVE", "1")
    monkeypatch.setenv("OPENCLAW_PROTECTED_GENERATE_LOCAL_TIMEOUT", "0.05")
    monkeypatch.setenv("OPENCLAW_PROTECTED_GENERATE_LOCAL_ATTEMPTS", "1")
    monkeypatch.setattr(chief_llm, "ollama_call", fake_ollama)
    monkeypatch.setattr(chief_llm, "ollama_is_unreachable", lambda **_kwargs: False)

    outcome = protected_generate_with_receipt(
        "What is the Capital Hilton status?",
        context_packet={
            "packet_id": "packet:test:capital_hilton",
            "facts": [
                {
                    "label": "Capital Hilton status",
                    "value": "$2000 received through Coupa; July 1 check expected.",
                }
            ],
        },
        audit_log_path=tmp_path / "audit.jsonl",
    )

    assert outcome.status == "ANSWER_READY"
    assert "Capital Hilton status" in outcome.text
    assert "July 1 check expected" in outcome.text
    assert calls == [
        {
            "timeout": 0.05,
            "task_class": "chief_user_reply",
            "attempts": 1,
            "prompt_has_capital_hilton": True,
        }
    ]
    assert outcome.receipt["model_call_performed"] is False
    assert outcome.receipt["local_model_invoked"] is False
    assert outcome.receipt["deterministic_fallback_used"] is True
    assert outcome.receipt["local_timeout_seconds"] == 0.05
    assert outcome.receipt["local_model_attempts"] == 1


def test_protected_generate_short_circuits_when_no_external_model_and_ollama_unreachable(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from protected_generate import protected_generate_with_receipt

    import chief_llm

    monkeypatch.delenv("OPENCLAW_TEST_MODE", raising=False)
    monkeypatch.delenv("OPENCLAW_CASSANDRA_EXTERNAL_MODEL", raising=False)
    monkeypatch.delenv("CASSANDRA_EXTERNAL_MODEL", raising=False)
    monkeypatch.delenv("OPENCLAW_EXTERNAL_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.setenv("OPENCLAW_MAESTRO_BRAIN_LIVE", "1")
    monkeypatch.setenv("OPENCLAW_PROTECTED_GENERATE_OLLAMA_PROBE_TIMEOUT", "0.01")
    monkeypatch.setattr(chief_llm, "_configured_openrouter_model", lambda: "")
    monkeypatch.setattr(chief_llm, "ollama_is_unreachable", lambda **_kwargs: True)
    monkeypatch.setattr(
        chief_llm,
        "ollama_call",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("local model must be skipped")),
    )

    outcome = protected_generate_with_receipt(
        "What is the Capital Hilton status?",
        context_packet={
            "packet_id": "packet:test:capital_hilton_shortcircuit",
            "facts": [
                {
                    "label": "Capital Hilton status",
                    "value": "$2000 received through Coupa; July 1 check expected.",
                }
            ],
        },
        audit_log_path=tmp_path / "audit.jsonl",
    )

    assert outcome.status == "ANSWER_READY"
    assert "Capital Hilton status" in outcome.text
    assert "July 1 check expected" in outcome.text
    assert outcome.receipt["route"] == "grounded_fallback_no_external_model_ollama_unreachable"
    assert outcome.receipt["external_model_configured"] is False
    assert outcome.receipt["ollama_unreachable_shortcircuit"] is True
    assert outcome.receipt["ollama_probe_timeout_seconds"] == 0.01
    assert outcome.receipt["model_call_performed"] is False
    assert outcome.receipt["local_model_invoked"] is False
    assert outcome.receipt["external_llm_invoked"] is False
    assert outcome.receipt["deterministic_fallback_used"] is True


def test_maestro_freeform_uses_protected_generate_without_touching_deterministic_paths(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store_path = _truth_store(monkeypatch, tmp_path)
    read_model_root = _read_models(tmp_path)
    calls: list[dict] = []

    def fake_protected(question: str, *, context_packet: dict, **_kwargs):
        calls.append({"question": question, "packet_id": context_packet["packet_id"]})
        return "I would focus on Capital Hilton first, then Live Arts MD. SEND_HOLD remains active."

    from maestro_cassandra_responder import answer_frontdoor_chat, external_llm_invoked_for_result

    date_result = answer_frontdoor_chat("what is today's date?", session={"read_model_root": str(read_model_root)})
    assert external_llm_invoked_for_result(date_result) is False
    assert calls == []

    result = answer_frontdoor_chat(
        "What should I focus on next across my business life?",
        session={"read_model_root": str(read_model_root), "operator_truth_store_path": str(store_path)},
        protected_generate_fn=fake_protected,
    )

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "maestro_brain_freeform"
    assert result.allowed_to_call_handle is False
    assert result.machine_proof["protected_generate_called"] is True
    assert result.machine_proof["maestro_context_packet_used"] is True
    assert result.machine_proof["email_send_performed"] is False
    assert result.machine_proof["ledger_mutation_performed"] is False
    assert "I would focus" in result.plain_summary
    assert calls and calls[0]["question"].startswith("What should I focus")


def test_business_status_question_routes_to_maestro_brain_not_status_readback(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store_path = _truth_store(monkeypatch, tmp_path)
    read_model_root = _read_models(tmp_path)
    calls: list[str] = []

    def fake_protected(question: str, *, context_packet: dict, **_kwargs):
        calls.append(question)
        return {
            "text": "Capital Hilton packet answer: $2000 received through Coupa; July 1 check expected. SEND_HOLD remains active.",
            "receipt": {
                "receipt_id": "receipt:test:capital_hilton_status",
                "decision": "INJECTED_PROTECTED_GENERATE",
                "model_call_performed": False,
                "external_llm_invoked": False,
                "local_model_invoked": False,
            },
        }

    from maestro_cassandra_responder import answer_frontdoor_chat

    result = answer_frontdoor_chat(
        "what's Winship's day / Capital Hilton status?",
        session={"read_model_root": str(read_model_root), "operator_truth_store_path": str(store_path)},
        protected_generate_fn=fake_protected,
    )

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "maestro_brain_freeform"
    assert result.allowed_to_call_handle is False
    assert result.machine_proof["protected_generate_called"] is True
    assert result.machine_proof["maestro_context_packet_used"] is True
    assert result.machine_proof["status_capability_readback_performed"] is False
    assert "Capital Hilton packet answer" in result.plain_summary
    assert calls == ["what's Winship's day / Capital Hilton status?"]


def test_request_processor_disclosure_tracks_protected_model_path(monkeypatch, tmp_path: Path) -> None:
    import openclaw_request_processor as processor
    from maestro_cassandra_responder import MaestroCassandraResult

    def fake_answer_frontdoor_chat(*_args, **_kwargs) -> MaestroCassandraResult:
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class="maestro_brain_freeform",
            allowed_to_call_handle=False,
            one_line_answer="I have a packet-grounded answer.",
            plain_summary="I have a packet-grounded answer. SEND_HOLD remains active.",
            machine_proof={
                "protected_generate_called": True,
                "maestro_context_packet_used": True,
                "model_call_performed": True,
                "external_llm_invoked": False,
                "local_model_invoked": True,
                "email_send_performed": False,
                "ledger_mutation_performed": False,
            },
        )

    monkeypatch.setattr(processor.maestro_cassandra_responder, "answer_frontdoor_chat", fake_answer_frontdoor_chat)
    raw_request = {
        "kind": "OPERATOR_INSTRUCTION_PACKAGE_REQUEST",
        "active_surface_ref": "operator_maestro_chat",
        "operator_text": "What should I focus on?",
        "authority_boundary": {"send": False, "spend": False, "execute": False},
        "request_id": "req_maestro_brain_test",
    }

    response = processor._process_maestro_frontdoor_operator_instruction(
        tmp_path / "request.json",
        raw_request,
        classification=processor.classify_request_filename(None),
        route_decision={},
    )

    assert response is not None
    detail = response.detail_disclosure
    assert detail["model_or_worker_response_adapter_called"] is True
    assert detail["external_llm_invoked"] is False
    assert detail["local_model_runtime_connected"] is True
    assert any("local_model_invoked=True" in item for item in response.what_happened)
    assert detail["ledger_mutation_performed"] is False


def test_fallback_gig_day_intent_routes_to_calendar_not_finance_collision(tmp_path: Path) -> None:
    # 000h: "$400 gigs" contains "gig" and "next Friday" contains "day" (fri-DAY), so a
    # finance fact otherwise out-scores the real calendar. gig/day questions must route
    # to the calendar_day fact, never to Capital Hilton finance vocabulary.
    from protected_generate import protected_generate_with_receipt

    packet = {
        "packet_id": "packet:test:gig_day_collision",
        "facts": [
            {
                "topic": "operator_truth",
                "label": "Capital Hilton",
                "value": "$2000 received through Coupa; July 1 check expected; $400 gigs; next Friday.",
            },
            {
                "topic": "calendar_day",
                "label": "Upcoming calendar commitments",
                "value": "2026-06-26 - Rehearsal at St Anne's - 19:00; 2026-06-27 - Wedding reception set - 20:00.",
            },
        ],
    }

    for question in ("how many gigs do I have?", "when is my next gig?", "what does my day look like?"):
        outcome = protected_generate_with_receipt(
            question,
            context_packet=packet,
            audit_log_path=tmp_path / "audit.jsonl",
            allow_live_model=False,
        )
        assert outcome.status == "ANSWER_READY"
        assert "Rehearsal" in outcome.text or "Wedding reception" in outcome.text, f"{question} -> {outcome.text}"
        assert "Coupa" not in outcome.text, f"{question} leaked finance -> {outcome.text}"
        assert "July 1 check" not in outcome.text, f"{question} leaked finance -> {outcome.text}"
        assert outcome.receipt["model_call_performed"] is False


def test_fallback_gig_day_intent_is_honest_when_no_calendar_fact(tmp_path: Path) -> None:
    # 000h: schedule intent with no calendar fact answers honestly instead of falling
    # back to the finance vocabulary collision.
    from protected_generate import protected_generate_with_receipt

    outcome = protected_generate_with_receipt(
        "how many gigs do I have?",
        context_packet={
            "packet_id": "packet:test:gig_no_calendar",
            "facts": [
                {
                    "topic": "operator_truth",
                    "label": "Capital Hilton",
                    "value": "$2000 received through Coupa; July 1 check expected; $400 gigs; next Friday.",
                }
            ],
        },
        audit_log_path=tmp_path / "audit.jsonl",
        allow_live_model=False,
    )

    assert outcome.status == "ANSWER_READY"
    assert "I don't have that" in outcome.text
    assert "Coupa" not in outcome.text
    assert "Capital Hilton" not in outcome.text
    assert outcome.receipt["model_call_performed"] is False


def test_fallback_named_entity_and_domain_routing_unchanged_by_000h(tmp_path: Path) -> None:
    # 000h must not touch non-schedule routing: named entities + domain queries still work.
    from protected_generate import protected_generate_with_receipt

    packet = {
        "packet_id": "packet:test:routing_regression",
        "facts": [
            {
                "topic": "operator_truth",
                "label": "Capital Hilton",
                "value": "$2000 received through Coupa; July 1 check expected.",
            },
            {"topic": "operator_truth", "label": "St Anne's", "value": "All paid up."},
            {
                "topic": "invoice_status",
                "label": "Open invoices",
                "value": "3 finance candidates; 1 high risk; sending blocked.",
            },
        ],
    }

    def answer(question: str) -> str:
        return protected_generate_with_receipt(
            question,
            context_packet=packet,
            audit_log_path=tmp_path / "audit.jsonl",
            allow_live_model=False,
        ).text

    assert "Capital Hilton" in answer("what is my Capital Hilton status?")
    assert "All paid up" in answer("what's the status of St Anne's?")
    assert "finance candidates" in answer("what invoices are open?")
