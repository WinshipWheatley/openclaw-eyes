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
