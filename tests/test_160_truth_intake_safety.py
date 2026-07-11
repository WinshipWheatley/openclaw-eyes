from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

import openclaw_request_processor as processor
import operator_truth_store as truth_store


FIXED_NOW = "2026-07-11T16:00:00+00:00"
E1_QUESTION = "that $1,095 from Live Arts — which gigs was that actually for?"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_store(path: Path, entities: dict[str, dict] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": truth_store.STORE_VERSION,
                "entities": entities or {},
                "seeded_sources": {},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _response(
    message: str,
    *,
    request_type: str = "CHAT",
    internal_status: str = "RESPONSE_READY",
    detail_disclosure: dict | None = None,
) -> processor.OpenClawResponseForMac:
    return processor.OpenClawResponseForMac(
        source_request_id=f"task160_{request_type.lower()}_{internal_status.lower()}",
        source_request_filename="mission_control_chat_request_task160.json",
        workflow_ref="task160_fixture",
        request_type=request_type,
        internal_status=internal_status,
        operator_headline=message,
        operator_message=message,
        what_happened=("A bounded fixture response was assembled.",),
        why_it_happened="The task 160 acceptance fixture selected this response family.",
        how_to_fix="Ask for a fresh bounded readback if needed.",
        visible_cards=({"title": "Task 160 fixture", "summary": "Bounded fixture."},),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason="fixture_blocked" if internal_status.startswith("BLOCKED") else None,
        detail_disclosure=detail_disclosure or {},
        readback_files=(),
        next_safe_move="Review the bounded response.",
    )


@pytest.mark.parametrize(
    "question",
    (
        E1_QUESTION,
        "Live Arts owes us $1,095, right?",
        "Did Capital Hilton receive the $2,000 check?",
        "What did St Anne's pay on invoice 2026-1001",
        "Capital Hilton current truth: was the $2,000 payment received?",
        "Correction — Live Arts owes $1,095 or was that already paid?",
        "I'm wondering whether Live Arts owes us $1,095",
        "I am wondering if Live Arts owes us $1,095",
        "I wonder whether Live Arts owes us $1,095",
    ),
)
def test_question_shaped_truth_is_rejected_at_persistence_boundary(
    tmp_path: Path,
    question: str,
) -> None:
    store_path = tmp_path / "operator_truth_store.json"
    truth_store.upsert_operator_truth(
        "live_arts_md",
        "Live Arts MD owes $1,095 for completed production work.",
        source_surface="fixture",
        source_text="Live Arts current truth: owes $1,095.",
        path=store_path,
    )
    before = _sha256(store_path)

    records = truth_store.capture_operator_truth_from_text(
        question,
        source_surface="operator_maestro_chat",
        path=store_path,
    )

    assert records == []
    assert _sha256(store_path) == before
    valid, reason = truth_store.validate_operator_truth_value(question, source_text=question)
    assert valid is False
    assert reason == "question_shaped_text"


@pytest.mark.parametrize(
    "question",
    (
        "Actually Live Arts has the $1,095 — tell me which gigs it covered",
        "Show me which gigs the Live Arts $1,095 covered",
        "Remind me what Capital Hilton paid on the $2,000 invoice",
        "I wonder which Live Arts gigs the $1,095 covered",
        "I'm wondering whether Live Arts owes us $1,095",
        "I am wondering if Live Arts owes us $1,095",
        "I wonder whether Live Arts owes us $1,095",
        "Will Capital Hilton cut a $2,000 check on July 15",
    ),
)
def test_direct_upsert_rejects_question_and_question_request_shapes(
    tmp_path: Path,
    question: str,
) -> None:
    store_path = tmp_path / "operator_truth_store.json"

    with pytest.raises(ValueError, match="question_shaped_text"):
        truth_store.upsert_operator_truth(
            "live_arts_md" if "live arts" in question.lower() else "capital_hilton",
            question,
            source_surface="operator_maestro_chat",
            source_text=question,
            path=store_path,
        )

    assert not store_path.exists()


def test_declarative_future_will_cut_statement_remains_valid(tmp_path: Path) -> None:
    statement = "Will cut a $2,000 check for Capital Hilton on July 15, 2026."

    record = truth_store.upsert_operator_truth(
        "capital_hilton",
        statement,
        source_surface="operator_maestro_chat",
        source_text=statement,
        path=tmp_path / "operator_truth_store.json",
    )

    assert record["value"] == statement
    assert record["write_receipt"]["status"] == "committed"


@pytest.mark.parametrize(
    ("statement", "entity_key", "expected_value"),
    (
        (
            "Capital Hilton current truth: $2000 received through Coupa; check July 1, 2026.",
            "capital_hilton",
            "$2000 received through Coupa; check July 1, 2026.",
        ),
        ("St Anne's current truth: all paid up.", "st_annes", "all paid up."),
        (
            "Actually, Capital Hilton owes $2,000 and the payment is not received.",
            "capital_hilton",
            "Actually, Capital Hilton owes $2,000 and the payment is not received.",
        ),
        (
            "Correction: Live Arts MD owes $1,095 for completed production work.",
            "live_arts_md",
            "Correction: Live Arts MD owes $1,095 for completed production work.",
        ),
        (
            "The truth is St Anne's invoice 2026-1001 is paid up.",
            "st_annes",
            "The truth is St Anne's invoice 2026-1001 is paid up.",
        ),
        (
            "Live Arts MD current status: invoice $1,095 is unpaid.",
            "live_arts_md",
            "invoice $1,095 is unpaid.",
        ),
    ),
)
def test_task_136_statement_and_correction_shapes_still_commit_exactly(
    tmp_path: Path,
    statement: str,
    entity_key: str,
    expected_value: str,
) -> None:
    store_path = tmp_path / "operator_truth_store.json"

    records = truth_store.capture_operator_truth_from_text(
        statement,
        source_surface="operator_maestro_chat",
        source_ref="task160-valid-statement",
        at=FIXED_NOW,
        path=store_path,
    )

    assert len(records) == 1
    assert records[0]["entity_key"] == entity_key
    assert records[0]["value"] == expected_value
    receipt = records[0]["write_receipt"]
    assert receipt["status"] == "committed"
    assert receipt["file_mutation_performed"] is True
    assert receipt["business_state_mutation_performed"] is True
    stored = truth_store.load_operator_truth_store(store_path, ensure_seed=False)["entities"][entity_key]
    assert stored["value"] == expected_value
    assert stored["source_text_hash"] == hashlib.sha256(statement.encode("utf-8")).hexdigest()


def test_poisoned_live_arts_record_is_ineligible_then_quarantined_and_repaired(tmp_path: Path) -> None:
    store_path = tmp_path / "operator_truth_store.json"
    quarantine_path = tmp_path / "operator_truth_store.quarantine.json"
    poison = {
        "entity_key": "live_arts_md",
        "label": "Live Arts MD",
        "value": E1_QUESTION,
        "provenance": "operator_corrected",
        "at": "2026-07-10T18:57:24+00:00",
        "source_surface": "mac_probe",
        "source_ref": "E1",
        "source_text_hash": hashlib.sha256(E1_QUESTION.encode("utf-8")).hexdigest(),
        "precedence": 100,
        "pii_tier": "LIGHT",
    }
    _write_store(store_path, {"live_arts_md": poison})

    assert truth_store.find_operator_truth_for_text("What is up with Live Arts?", path=store_path) is None
    assert E1_QUESTION not in truth_store.format_operator_truth_context("Live Arts", path=store_path)

    receipt = truth_store.quarantine_unsafe_operator_truth_records(
        path=store_path,
        quarantine_path=quarantine_path,
        source_ref="incident:2026-07-11",
        at=FIXED_NOW,
    )

    assert receipt["status"] == "quarantined"
    assert receipt["entity_keys"] == ["live_arts_md"]
    assert "live_arts_md" not in truth_store.load_operator_truth_store(store_path, ensure_seed=False)["entities"]
    quarantine = json.loads(quarantine_path.read_text(encoding="utf-8"))
    assert quarantine["records"][0]["record"]["value"] == E1_QUESTION
    assert quarantine["receipts"][0]["receipt_id"] == receipt["receipt_id"]

    repair = truth_store.repair_quarantined_operator_truth(
        "live_arts_md",
        "Live Arts MD owes $1,095 for completed production work; gig allocation is not yet recorded.",
        source_surface="operator_repair",
        source_text="Correction: Live Arts MD owes $1,095; gig allocation is not yet recorded.",
        path=store_path,
        quarantine_path=quarantine_path,
        at="2026-07-11T16:05:00+00:00",
    )

    assert repair["status"] == "repaired"
    assert repair["quarantine_receipt_id"] == receipt["receipt_id"]
    match = truth_store.find_operator_truth_for_text("What is up with Live Arts?", path=store_path)
    assert match is not None
    assert "$1,095" in match[1]["value"]
    quarantine = json.loads(quarantine_path.read_text(encoding="utf-8"))
    assert quarantine["repair_receipts"][0]["receipt_id"] == repair["receipt_id"]


def test_corrupt_quarantine_fails_closed_without_overwrite(tmp_path: Path) -> None:
    store_path = tmp_path / "operator_truth_store.json"
    quarantine_path = tmp_path / "operator_truth_store.quarantine.json"
    poison = {
        "entity_key": "live_arts_md",
        "label": "Live Arts MD",
        "value": E1_QUESTION,
        "provenance": "operator_corrected",
        "source_text_hash": hashlib.sha256(E1_QUESTION.encode()).hexdigest(),
        "precedence": 100,
    }
    _write_store(store_path, {"live_arts_md": poison})
    quarantine_path.write_text("{corrupt-json", encoding="utf-8")
    store_before = _sha256(store_path)
    quarantine_before = quarantine_path.read_bytes()

    with pytest.raises(truth_store.OperatorTruthQuarantineIntegrityError):
        truth_store.quarantine_unsafe_operator_truth_records(
            path=store_path,
            quarantine_path=quarantine_path,
            at=FIXED_NOW,
        )

    assert _sha256(store_path) == store_before
    assert quarantine_path.read_bytes() == quarantine_before


def test_quarantine_persists_pending_receipt_before_live_removal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "operator_truth_store.json"
    quarantine_path = tmp_path / "operator_truth_store.quarantine.json"
    poison = {
        "entity_key": "live_arts_md",
        "label": "Live Arts MD",
        "value": E1_QUESTION,
        "provenance": "operator_corrected",
        "precedence": 100,
    }
    _write_store(store_path, {"live_arts_md": poison})
    store_before = _sha256(store_path)
    monkeypatch.setattr(
        truth_store,
        "save_operator_truth_store",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("simulated live-store failure")),
    )

    with pytest.raises(OSError, match="simulated live-store failure"):
        truth_store.quarantine_unsafe_operator_truth_records(
            path=store_path,
            quarantine_path=quarantine_path,
            at=FIXED_NOW,
        )

    archive = json.loads(quarantine_path.read_text(encoding="utf-8"))
    assert archive["records"][0]["record"]["value"] == E1_QUESTION
    assert archive["receipts"][0]["status"] == "pending"
    assert _sha256(store_path) == store_before


def test_repair_persists_pending_intent_before_truth_upsert(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "operator_truth_store.json"
    quarantine_path = tmp_path / "operator_truth_store.quarantine.json"
    poison = {
        "entity_key": "live_arts_md",
        "label": "Live Arts MD",
        "value": E1_QUESTION,
        "provenance": "operator_corrected",
        "precedence": 100,
    }
    _write_store(store_path, {"live_arts_md": poison})
    truth_store.quarantine_unsafe_operator_truth_records(
        path=store_path,
        quarantine_path=quarantine_path,
        at=FIXED_NOW,
    )
    monkeypatch.setattr(
        truth_store,
        "upsert_operator_truth",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("simulated repair failure")),
    )

    with pytest.raises(OSError, match="simulated repair failure"):
        truth_store.repair_quarantined_operator_truth(
            "live_arts_md",
            "Live Arts MD owes $1,095 for completed production work.",
            source_surface="operator_repair",
            source_text="Correction: Live Arts MD owes $1,095 for completed production work.",
            path=store_path,
            quarantine_path=quarantine_path,
            at="2026-07-11T16:05:00+00:00",
        )

    archive = json.loads(quarantine_path.read_text(encoding="utf-8"))
    pending = archive["repair_receipts"][-1]
    assert pending["status"] == "pending"
    assert pending["intended_value_hash"]
    assert "live_arts_md" not in truth_store.load_operator_truth_store(
        store_path, ensure_seed=False
    )["entities"]


def test_poisoned_record_never_enters_rich_packet_or_outranks_receivable_truth(tmp_path: Path) -> None:
    import maestro_context_packet

    store_path = tmp_path / "operator_truth_store.json"
    poison = {
        "entity_key": "live_arts_md",
        "label": "Live Arts MD",
        "value": E1_QUESTION,
        "provenance": "operator_corrected",
        "at": "2026-07-10T18:57:24+00:00",
        "precedence": 100,
        "source_surface": "mac_probe",
    }
    _write_store(store_path, {"live_arts_md": poison})
    read_models = tmp_path / "read_models"
    read_models.mkdir()
    source_receivables = Path("generated/read_models/receivables_month_bounded.json")
    (read_models / source_receivables.name).write_bytes(source_receivables.read_bytes())

    packet = maestro_context_packet.build_maestro_context_packet(
        question="what does Live Arts owe right now?",
        read_model_root=read_models,
        operator_truth_store_path=store_path,
        require_real_truth=False,
    )
    serialized = json.dumps(packet, sort_keys=True)

    assert E1_QUESTION not in serialized
    assert not any(
        fact.get("topic") == "operator_truth" and fact.get("entity_key") == "live_arts_md"
        for fact in packet["facts"]
    )
    assert any(
        "Live Arts" in str(fact.get("value") or "")
        and fact.get("topic") != "operator_truth"
        for fact in packet["facts"]
    )


def test_truth_write_success_and_aggregate_effect_proof_derive_from_commit_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from maestro_cassandra_responder import answer_frontdoor_chat

    store_path = tmp_path / "operator_truth_store.json"
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_STORE", str(store_path))
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_SEED", str(tmp_path / "missing-seed.md"))

    result = answer_frontdoor_chat(
        "Capital Hilton current truth: $2000 received through Coupa; check July 1, 2026.",
        source_surface="operator_maestro_chat",
    )

    proof = dict(result.machine_proof or {})
    receipt = proof["operator_truth_write_receipts"][0]
    assert receipt["status"] == "committed"
    assert proof["operator_truth_store_written"] is True
    assert proof["file_mutation_performed"] is True
    assert proof["business_state_mutation_performed"] is True
    assert "updated" in result.plain_summary.lower()

    response = replace(
        _response(
            result.plain_summary,
            detail_disclosure={"maestro_cassandra_responder": result.to_dict()},
        ),
        readback_files=("generated/read_models/operator_truth_write_receipt.json",),
    )
    payload, status = processor.build_payloads(response, generated_at=FIXED_NOW)

    assert payload["machine_proof"]["operator_truth_write_committed"] is True
    assert payload["machine_proof"]["file_mutation_performed"] is True
    assert payload["machine_proof"]["business_state_mutation_performed"] is True
    assert status["machine_proof"]["operator_truth_write_committed"] is True


def test_real_frontdoor_truth_write_supplies_guardian_proof_without_substitution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import maestro_listener

    store_path = tmp_path / "operator_truth_store.json"
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_STORE", str(store_path))
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_SEED", str(tmp_path / "missing-seed.md"))
    request = maestro_listener.build_operator_maestro_chat_request(
        "Capital Hilton current truth: $2000 received through Coupa; check July 1, 2026.",
        message_id="16001",
        chat_id=160,
        created_at=FIXED_NOW,
    )
    request_path = tmp_path / "mission_control_operator_instruction_request_maestro_telegram_16001.json"
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at=FIXED_NOW,
        duplicate_check=False,
    )
    payload, status = processor.build_payloads(response, generated_at=FIXED_NOW)

    assert "guardian_publication_enforcement" not in payload
    assert payload["machine_proof"]["operator_truth_write_committed"] is True
    assert payload["machine_proof"]["file_mutation_performed"] is True
    assert status["machine_proof"]["guardian_output_gate_passed"] is True
    assert any(ref.startswith("operator_truth_write_receipt:") for ref in payload["proof_refs"])


def test_raw_probe_paths_and_namespace_are_ignored_and_rederived(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from maestro_cassandra_responder import session_from_request
    from probe_state_contract import validate_bound_probe_session

    probe_root = tmp_path / "probe-root"
    production = tmp_path / "production-truth.json"
    _write_store(production)
    monkeypatch.setenv("OPENCLAW_PROBE_STATE_ROOT", str(probe_root))
    request = {
        "probe_marker": "TASK160_PROBE",
        "run_mode": "test_dry_run",
        "test_run_id": "task160-run",
        "probe_state_namespace": "../../spoofed",
        "operator_truth_store_path": str(production),
        "recurrence_rule_db_path": str(tmp_path / "production-recurrence.sqlite3"),
        "session": {
            "workflow_package_sqlite_path": str(tmp_path / "production-workflow.sqlite3"),
            "guided_review_root": str(tmp_path / "production-guided"),
        },
    }

    session = session_from_request(request)

    assert validate_bound_probe_session(session) is True
    assert session["probe_state_namespace"] != "../../spoofed"
    assert session["operator_truth_store_path"] != str(production)
    assert all(Path(session[key]).is_relative_to(probe_root) for key in (
        "operator_truth_store_path",
        "recurrence_rule_db_path",
        "workflow_package_sqlite_path",
        "guided_review_root",
    ))


def test_marker_only_probe_binding_is_stable_across_frontdoor_rebind(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from maestro_cassandra_responder import answer_frontdoor_chat, session_from_request
    from probe_state_contract import bind_probe_state_session, validate_bound_probe_session

    probe_root = tmp_path / "probe-root"
    monkeypatch.setenv("OPENCLAW_PROBE_STATE_ROOT", str(probe_root))
    session = session_from_request(
        {
            "probe_marker": "TASK160_MARKER_ONLY",
            "run_mode": "test_dry_run",
        }
    )
    namespace = session["probe_state_namespace"]
    test_run_id = session["test_run_id"]
    truth_path = session["operator_truth_store_path"]

    rebound = bind_probe_state_session(session, session)
    result = answer_frontdoor_chat(
        "Correction: Live Arts MD owes $1,095 for completed production work.",
        source_surface="mac_probe_replay",
        session=session,
    )

    assert validate_bound_probe_session(session) is True
    assert validate_bound_probe_session(rebound) is True
    assert rebound["probe_state_namespace"] == namespace
    assert rebound["test_run_id"] == test_run_id
    assert rebound["operator_truth_store_path"] == truth_path
    assert result.session_forwarded["probe_state_namespace"] == namespace
    assert result.session_forwarded["test_run_id"] == test_run_id
    assert result.session_forwarded["operator_truth_store_path"] == truth_path
    assert result.machine_proof["probe_state_isolated"] is True
    assert Path(truth_path).exists()


def test_probe_people_and_brain_snapshot_cannot_read_production_only_truth(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import cassandra_brain
    import maestro_cassandra_responder as responder
    from maestro_cassandra_responder import answer_frontdoor_chat, session_from_request

    production_truth = tmp_path / "production" / "operator_truth_store.json"
    probe_root = tmp_path / "probe-root"
    sentinel = "Live Arts MD owes $9,999 PRODUCTION-ONLY-SENTINEL."
    _write_store(production_truth)
    truth_store.upsert_operator_truth(
        "live_arts_md",
        sentinel,
        source_surface="production_fixture",
        source_text="Live Arts MD current truth is the production-only fixture.",
        path=production_truth,
    )
    production_before = _sha256(production_truth)
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_STORE", str(production_truth))
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_SEED", str(tmp_path / "missing-seed.md"))
    monkeypatch.setenv("OPENCLAW_PROBE_STATE_ROOT", str(probe_root))
    monkeypatch.setattr(responder, "_answer_people_query_from_contacts_registry", lambda _text: None)
    session = session_from_request(
        {
            "probe_marker": "TASK160_READ_ISOLATION",
            "run_mode": "test_dry_run",
            "test_run_id": "task160-read-isolation",
        }
    )

    people = answer_frontdoor_chat(
        "Who should I contact about Live Arts MD?",
        source_surface="mac_probe_replay",
        session=session,
        protected_generate_fn=lambda _text, **_kwargs: {
            "text": "No probe-scoped people fact is recorded.",
            "receipt": {
                "status": "ANSWER_READY",
                "external_llm_invoked": False,
                "local_model_invoked": False,
                "model_call_performed": False,
            },
        },
    )
    override = cassandra_brain._get_session_fact_override(
        "Live Arts MD current status",
        dict(cassandra_brain._DEFAULT_STATE),
        session=session,
    )
    snapshot = cassandra_brain.build_context_snapshot(
        dict(cassandra_brain._DEFAULT_STATE),
        session=session,
    )

    assert people.intent_class == "people_reference_query"
    assert people.machine_proof["operator_truth_record_found"] is False
    assert "PRODUCTION-ONLY-SENTINEL" not in people.plain_summary
    assert override is None
    assert "PRODUCTION-ONLY-SENTINEL" not in snapshot
    assert _sha256(production_truth) == production_before


def test_inactive_request_cannot_inject_internal_state_paths_or_namespace(tmp_path: Path) -> None:
    from maestro_cassandra_responder import session_from_request

    injected = str(tmp_path / "production-state.json")
    session = session_from_request(
        {
            "operator_truth_store_path": injected,
            "recurrence_rule_db_path": injected,
            "workflow_package_sqlite_path": injected,
            "guided_review_root": injected,
            "proposal_ledger_path": injected,
            "probe_state_namespace": "spoofed",
            "session": {"operator_truth_store_path": injected},
        }
    )

    assert "operator_truth_store_path" not in session
    assert "recurrence_rule_db_path" not in session
    assert "workflow_package_sqlite_path" not in session
    assert "guided_review_root" not in session
    assert "proposal_ledger_path" not in session
    assert "probe_state_namespace" not in session


def test_invalid_probe_root_aliases_fail_closed_before_truth_access(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from maestro_cassandra_responder import answer_frontdoor_chat, session_from_request

    production = tmp_path / "production-truth.json"
    _write_store(production)
    before = _sha256(production)
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_STORE", str(production))
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_SEED", str(tmp_path / "missing-seed.md"))
    monkeypatch.setenv("OPENCLAW_PROBE_STATE_ROOT", "/home/openclaw/not-a-temp-probe-root")
    session = session_from_request(
        {
            "test_marker": "TASK160_ALIAS_PROBE",
            "requested_run_mode": "test_dry_run",
            "probe_run_id": "alias-run",
            "operator_truth_store_path": str(production),
        }
    )

    result = answer_frontdoor_chat(
        "Correction: Live Arts MD owes $1,095 for completed production work.",
        source_surface="mac_probe_replay",
        session=session,
    )

    assert result.intent_class == "probe_state_binding_blocked"
    assert result.machine_proof["probe_state_binding_failed"] is True
    assert result.machine_proof["probe_state_isolated"] is False
    assert result.machine_proof["production_state_allowed"] is False
    assert result.machine_proof["typed_contract_decision"]["source"] == "first_touch"
    assert result.machine_proof["typed_contract_decision"]["action"] == "pass_through"
    assert _sha256(production) == before


def test_real_generic_workflow_envelope_uses_probe_sqlite_not_owner_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import maestro_listener
    import sqlite3
    import workflow_package_request_consumer
    from maestro_cassandra_responder import session_from_request

    probe_root = tmp_path / "probe-root"
    production_db = tmp_path / "production-workflow.sqlite3"
    sqlite3.connect(production_db).close()
    before = _sha256(production_db)
    monkeypatch.setenv("OPENCLAW_PROBE_STATE_ROOT", str(probe_root))
    monkeypatch.setattr(workflow_package_request_consumer, "default_sqlite_path", lambda: production_db)
    request = maestro_listener.build_operator_maestro_chat_request(
        "Follow up on the Capital Hilton proposal.",
        message_id="16002",
        chat_id=160,
        created_at=FIXED_NOW,
    )
    request.update(
        {
            "active_surface_ref": "operator_cassandra_chat",
            "thread_ref": "operator_cassandra_chat",
            "current_thread_ref": "operator_cassandra_chat",
            "test_marker": "TASK160_WORKFLOW_PROBE",
            "requested_run_mode": "test_dry_run",
            "probe_run_id": "workflow-probe-run",
            "workflow_package_sqlite_path": str(production_db),
        }
    )
    request["payload_hash"] = maestro_listener._content_hash(request)
    request_path = tmp_path / "mission_control_operator_instruction_request_cassandra_probe_16002.json"
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at=FIXED_NOW,
        duplicate_check=False,
    )
    session = session_from_request(request)

    assert response.internal_status == "RESPONSE_READY"
    assert Path(session["workflow_package_sqlite_path"]).exists()
    assert _sha256(production_db) == before


def test_invalid_probe_root_blocks_generic_workflow_before_default_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import maestro_listener
    import sqlite3
    import workflow_package_request_consumer

    production_db = tmp_path / "production-workflow.sqlite3"
    sqlite3.connect(production_db).close()
    before = _sha256(production_db)
    monkeypatch.setenv("OPENCLAW_PROBE_STATE_ROOT", "/home/openclaw/not-temporary")
    monkeypatch.setattr(workflow_package_request_consumer, "default_sqlite_path", lambda: production_db)
    request = maestro_listener.build_operator_maestro_chat_request(
        "Follow up on the Capital Hilton proposal.",
        message_id="16004",
        chat_id=160,
        created_at=FIXED_NOW,
    )
    request.update(
        {
            "active_surface_ref": "operator_cassandra_chat",
            "thread_ref": "operator_cassandra_chat",
            "current_thread_ref": "operator_cassandra_chat",
            "test_marker": "TASK160_INVALID_ROOT",
            "requested_run_mode": "test_dry_run",
            "probe_run_id": "invalid-root-run",
        }
    )
    request["payload_hash"] = maestro_listener._content_hash(request)
    request_path = tmp_path / "mission_control_operator_instruction_request_cassandra_probe_16004.json"
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at=FIXED_NOW,
        duplicate_check=False,
    )

    assert response.internal_status == "BLOCKED_WITH_REASON"
    assert response.detail_disclosure["probe_state_contract"]["status"] == "blocked"
    assert _sha256(production_db) == before


def test_real_recurrence_envelope_uses_probe_db_not_owner_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import maestro_listener
    import recurrence_rule_store
    import sqlite3
    from maestro_cassandra_responder import session_from_request

    probe_root = tmp_path / "probe-root"
    production_db = tmp_path / "production-recurrence.sqlite3"
    sqlite3.connect(production_db).close()
    before = _sha256(production_db)
    monkeypatch.setenv("OPENCLAW_PROBE_STATE_ROOT", str(probe_root))
    monkeypatch.setattr(recurrence_rule_store, "DEFAULT_DB_PATH", production_db)
    request = maestro_listener.build_operator_maestro_chat_request(
        "Live Arts invoices go out on the first of every month",
        message_id="16003",
        chat_id=160,
        created_at=FIXED_NOW,
    )
    request.update(
        {
            "probe_marker": "TASK160_RECURRENCE_PROBE",
            "run_mode": "test_dry_run",
            "test_run_id": "recurrence-probe-run",
            "recurrence_rule_db_path": str(production_db),
        }
    )
    request["payload_hash"] = maestro_listener._content_hash(request)
    request_path = tmp_path / "mission_control_operator_instruction_request_maestro_probe_16003.json"
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at=FIXED_NOW,
        duplicate_check=False,
    )
    session = session_from_request(request)

    assert response.detail_disclosure["maestro_cassandra_responder"]["intent_class"] == "recurrence_rule_statement"
    assert Path(session["recurrence_rule_db_path"]).exists()
    assert _sha256(production_db) == before


@pytest.mark.parametrize(
    ("request_type", "internal_status"),
    (
        ("CHAT", "RESPONSE_READY"),
        ("STATUS", "RESPONSE_READY"),
        ("WORKFLOW_PACKAGE_REQUEST", "RESPONSE_READY"),
        ("REFUSAL", "RESPONSE_READY"),
        ("BLOCKED", "BLOCKED_WITH_REASON"),
    ),
)
def test_guardian_deny_substitutes_bounded_non_silent_reply_for_every_family(
    request_type: str,
    internal_status: str,
) -> None:
    denied_candidate = f"DENIED-CANDIDATE-{request_type} /mnt/private/task160-secret"
    response = _response(
        denied_candidate,
        request_type=request_type,
        internal_status=internal_status,
    )

    payload, status = processor.build_payloads(response, generated_at=FIXED_NOW)
    serialized = processor.stable_json(payload)

    assert denied_candidate not in serialized
    assert payload["operator_message"]
    assert len(payload["operator_message"]) <= 240
    assert "Nothing was sent, changed, or executed" in payload["operator_message"]
    assert payload["internal_status"] == "BLOCKED_WITH_REASON"
    assert payload["response_author"] == "GUARDIAN"
    enforcement = payload["guardian_publication_enforcement"]
    assert enforcement["substituted"] is True
    assert enforcement["original_output_publish_allowed"] is False
    assert payload["machine_proof"]["guardian_denial_substituted"] is True
    assert payload["machine_proof"]["guardian_output_gate_passed"] is True
    assert status["machine_proof"]["guardian_denial_substituted"] is True


@pytest.mark.parametrize("request_type", ("CHAT", "STATUS", "WORKFLOW_PACKAGE_REQUEST", "REFUSAL", "BLOCKED"))
def test_guardian_substitution_does_not_fire_for_allowed_candidate(request_type: str) -> None:
    allowed = f"Bounded {request_type.lower()} response. Nothing changed."

    payload, status = processor.build_payloads(
        _response(allowed, request_type=request_type),
        generated_at=FIXED_NOW,
    )

    assert payload["operator_message"] == allowed
    assert "guardian_publication_enforcement" not in payload
    assert payload["machine_proof"]["guardian_denial_substituted"] is False
    assert status["machine_proof"]["guardian_denial_substituted"] is False


@pytest.mark.parametrize(
    "claim",
    (
        "The invoice was approved.",
        "This request is now authorized.",
        "Everything is approved.",
        "The operator approved it.",
        "Contract approved.",
        "Workbook approved.",
    ),
)
def test_guardian_still_denies_proofless_approval_execution_claims(claim: str) -> None:
    payload, _status = processor.build_payloads(_response(claim), generated_at=FIXED_NOW)

    assert payload["internal_status"] == "BLOCKED_WITH_REASON"
    assert payload["response_author"] == "GUARDIAN"
    assert payload["guardian_publication_enforcement"]["substituted"] is True
    assert payload["guardian_publication_enforcement"]["original_output_publish_allowed"] is False


def test_local_artifact_proof_does_not_authorize_invoice_approval_claim() -> None:
    response = replace(
        _response("The invoice was approved."),
        readback_files=("generated/read_models/local_artifact_reference.json",),
    )

    payload, _status = processor.build_payloads(response, generated_at=FIXED_NOW)

    assert payload["guardian_publication_enforcement"]["substituted"] is True


@pytest.mark.parametrize(
    ("request_type", "message", "proof_refs"),
    (
        ("CHAT", "I checked the approved inbox; no request is waiting.", ()),
        (
            "STATUS",
            "St. Anne's April 2026 receivable is paid.",
            (
                "generated/read_models/receivables_month_bounded.json",
                "receivables_row:st_annes:2026-04:settled",
            ),
        ),
        ("WORKFLOW_PACKAGE_REQUEST", "The approved contract is available for bounded review.", ()),
        ("REFUSAL", "No. That request was not approved, and nothing ran.", ()),
        ("BLOCKED", "The local status was last updated from a committed readback.", ("generated/read_models/status.json",)),
    ),
)
def test_real_response_vocabulary_does_not_trigger_false_guardian_substitution(
    request_type: str,
    message: str,
    proof_refs: tuple[str, ...],
) -> None:
    response = _response(message, request_type=request_type)
    if proof_refs:
        response = replace(response, readback_files=proof_refs)

    payload, status = processor.build_payloads(response, generated_at=FIXED_NOW)

    assert payload["operator_message"] == message
    assert "guardian_publication_enforcement" not in payload
    assert status["machine_proof"]["guardian_denial_substituted"] is False


@pytest.mark.parametrize(
    ("message", "proof_refs"),
    (
        (
            "Capital Hilton June 2026 receivable is paid.",
            (
                "generated/read_models/receivables_month_bounded.json",
                "receivables_row:capital_hilton:2026-06:settled",
            ),
        ),
        (
            "St. Anne's April 2026 receivable is paid.",
            ("generated/read_models/receivables_month_bounded.json",),
        ),
        (
            "St. Anne's April 2026 receivable is paid. OpenClaw paid the invoice.",
            (
                "generated/read_models/receivables_month_bounded.json",
                "receivables_row:st_annes:2026-04:settled",
            ),
        ),
    ),
)
def test_paid_status_requires_a_matching_settled_row_and_no_action_claim(
    message: str,
    proof_refs: tuple[str, ...],
) -> None:
    response = replace(_response(message), readback_files=proof_refs)

    payload, _status = processor.build_payloads(response, generated_at=FIXED_NOW)

    assert payload["guardian_publication_enforcement"]["substituted"] is True


def test_real_money_owner_to_processor_to_guardian_carries_settled_row_proof(
    tmp_path: Path,
) -> None:
    import maestro_listener

    question = "Which St Anne's receivables were paid in April 2026?"
    request = maestro_listener.build_operator_maestro_chat_request(
        question,
        message_id="task160-settled-row",
        chat_id=160,
        created_at=FIXED_NOW,
    )
    request_path = tmp_path / "mission_control_operator_instruction_request_task160_settled.json"
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at=FIXED_NOW,
        duplicate_check=False,
    )

    assert response.operator_message == (
        "St. Anne's April 2026 settled — paid; don't chase. (as of 2026-07-08)"
    )
    assert response.detail_disclosure["maestro_cassandra_responder"]["intent_class"] == "money_read"
    assert "receivables_row:st_annes:2026-04:settled" in response.readback_files
    assert (
        "receivables_row:st_annes:2026-04:settled"
        in response.detail_disclosure["maestro_cassandra_responder"]["machine_proof"]["read_model_refs"]
    )

    payload, status = processor.build_payloads(response, generated_at=FIXED_NOW)

    assert payload["operator_message"] == response.operator_message
    assert "guardian_publication_enforcement" not in payload
    assert payload["guardian_output_gate"]["validation_result"]["output_publish_allowed"] is True
    assert status["machine_proof"]["guardian_denial_substituted"] is False


@pytest.mark.parametrize(
    ("message", "proof_ref"),
    (
        ("I paid it.", "generated/read_models/receivables_month_bounded.json"),
        ("Capital Hilton is paid.", "generated/read_models/status.json"),
        ("We marked the invoice paid.", "generated/read_models/receivables_month_bounded.json"),
        ("Invoice is paid.", "generated/read_models/receivables_month_bounded.json"),
        (
            "Capital Hilton is paid per ledger. OpenClaw paid the invoice.",
            "generated/read_models/receivables_month_bounded.json",
        ),
    ),
)
def test_paid_action_or_unrelated_proof_remains_guardian_denied(
    message: str,
    proof_ref: str,
) -> None:
    response = replace(_response(message), readback_files=(proof_ref,))

    payload, _status = processor.build_payloads(response, generated_at=FIXED_NOW)

    assert payload["guardian_publication_enforcement"]["substituted"] is True


def test_post_write_guardian_deny_preserves_truthful_effect_receipt(tmp_path: Path) -> None:
    committed = truth_store.upsert_operator_truth(
        "live_arts_md",
        "Live Arts MD owes $1,095 for completed production work.",
        source_surface="fixture",
        source_text="Correction: Live Arts MD owes $1,095 for completed production work.",
        path=tmp_path / "truth.json",
    )["write_receipt"]
    denied_candidate = "Truth updated; inspect /mnt/private/task160-denied-candidate"
    response = replace(
        _response(
            denied_candidate,
            detail_disclosure={
                "maestro_cassandra_responder": {
                    "machine_proof": {"operator_truth_write_receipts": [committed]}
                }
            },
        ),
        readback_files=(committed["receipt_id"],),
    )

    payload, status = processor.build_payloads(response, generated_at=FIXED_NOW)
    serialized = processor.stable_json(payload)

    assert denied_candidate not in serialized
    assert "truth-store update committed" in payload["operator_message"]
    assert "Nothing was sent, changed, or executed" not in payload["operator_message"]
    assert payload["guardian_publication_enforcement"]["file_mutation_performed"] is True
    assert payload["detail_disclosure"]["operator_truth_effect_receipts"][0]["receipt_id"] == committed["receipt_id"]
    assert status["machine_proof"]["operator_truth_write_committed"] is True
    assert status["machine_proof"]["file_mutation_performed"] is True


def test_forced_second_guardian_deny_uses_last_resort_without_silence_or_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import guardian_output_gate

    real_validate = guardian_output_gate.validate_response_payload

    def always_deny(payload):
        result = real_validate(payload)
        result["validation_result"]["verdict"] = guardian_output_gate.BLOCKED_SCOPE
        result["validation_result"]["output_publish_allowed"] = False
        result["machine_proof"]["output_publish_allowed"] = False
        return result

    monkeypatch.setattr(guardian_output_gate, "validate_response_payload", always_deny)
    denied_candidate = "FORCED-SECOND-DENY-CANDIDATE"

    payload, status = processor.build_payloads(
        _response(denied_candidate),
        generated_at=FIXED_NOW,
    )
    serialized = processor.stable_json(payload)

    assert denied_candidate not in serialized
    assert payload["operator_message"]
    assert payload["internal_status"] == "BLOCKED_WITH_REASON"
    assert payload["response_author"] == "GUARDIAN"
    assert payload["guardian_publication_enforcement"]["last_resort_used"] is True
    assert status["machine_proof"]["guardian_last_resort_blocked_readback"] is True


def test_run_and_write_publishes_substitution_not_denied_candidate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    denied_candidate = "RUN-AND-WRITE-DENIED /mnt/private/do-not-publish-this"
    response = _response(denied_candidate)
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "exports"
    monkeypatch.setattr(processor, "DEFAULT_RESPONSE_DIR", response_dir)
    monkeypatch.setattr(processor, "process_once", lambda **_kwargs: response)

    payload, status, _paths, errors = processor.run_and_write(
        inbox=tmp_path / "inbox",
        request_file=None,
        request_id=None,
        export_root=export_root,
        generated_at=FIXED_NOW,
        response_dir=response_dir,
    )

    assert errors == ()
    publication = status["processor_status"]["mac_response_publication"]
    assert publication["published"] is True
    published = Path(publication["response_file"]).read_text(encoding="utf-8")
    assert denied_candidate not in published
    assert payload["guardian_publication_enforcement"]["substituted"] is True
    assert "Nothing was sent, changed, or executed" in published


def test_probe_marker_and_run_mode_bind_all_state_to_namespaced_temp_stores(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from maestro_cassandra_responder import answer_frontdoor_chat, session_from_request

    probe_root = tmp_path / "probe-state"
    monkeypatch.setenv("OPENCLAW_PROBE_STATE_ROOT", str(probe_root))
    production_truth = tmp_path / "production" / "operator_truth_store.json"
    production_recurrence = tmp_path / "production" / "recurrence.sqlite3"
    production_proposal = tmp_path / "production" / "proposal.json"
    production_guided = tmp_path / "production" / "guided.json"
    production_workflow = tmp_path / "production" / "workflow.sqlite3"
    _write_store(production_truth)
    truth_store.upsert_operator_truth(
        "live_arts_md",
        "Live Arts MD owes $9,999 in the production-only fixture.",
        source_surface="production_fixture",
        source_text="Live Arts current truth: owes $9,999.",
        path=production_truth,
    )
    production_recurrence.write_bytes(b"production-recurrence")
    production_proposal.write_bytes(b"production-proposal")
    production_guided.write_bytes(b"production-guided")
    production_workflow.write_bytes(b"production-workflow")
    before = {
        path.name: _sha256(path)
        for path in (
            production_truth,
            production_recurrence,
            production_proposal,
            production_guided,
            production_workflow,
        )
    }
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_STORE", str(production_truth))
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_SEED", str(tmp_path / "missing-seed.md"))

    session = session_from_request(
        {
            "request_id": "mac-round-e1-fixture",
            "probe_marker": "MAC_ROUND_E1",
            "run_mode": "test_dry_run",
            "test_run_id": "mac-round-41",
        }
    )

    assert session["probe_marker"] == "MAC_ROUND_E1"
    assert session["run_mode"] == "test_dry_run"
    assert session["test_run_id"] == "mac-round-41"
    assert session["probe_state_namespace"]
    for key in (
        "operator_truth_store_path",
        "recurrence_rule_db_path",
        "proposal_ledger_path",
        "guided_review_state_path",
        "guided_review_root",
        "guided_review_read_model_root",
        "guided_review_receipt_root",
        "workflow_package_sqlite_path",
    ):
        assert Path(session[key]).is_relative_to(probe_root)

    result = answer_frontdoor_chat(
        "Correction: Live Arts MD owes $1,095 for completed production work.",
        source_surface="mac_probe_replay",
        session=session,
    )

    assert result.machine_proof["probe_state_isolated"] is True
    assert Path(session["operator_truth_store_path"]).exists()

    query = answer_frontdoor_chat(
        "What have you recorded about Live Arts truth?",
        source_surface="mac_probe_replay",
        session=session,
    )
    assert query.intent_class == "operator_truth_query"
    assert "$1,095" in query.plain_summary
    assert "$9,999" not in query.plain_summary

    recurrence = answer_frontdoor_chat(
        "Live Arts invoices go out on the first of every month",
        source_surface="mac_probe_replay",
        session=session,
    )
    assert recurrence.intent_class == "recurrence_rule_statement"
    assert recurrence.machine_proof["recurrence_rule_captured"] is True
    assert Path(session["recurrence_rule_db_path"]).exists()

    workflow = answer_frontdoor_chat(
        "the PA rental invoice for Live Arts needs to go out — get it to the right agent",
        source_surface="operator_maestro_chat",
        session=session,
    )
    assert workflow.intent_class == "live_arts_invoice_handoff"
    assert workflow.machine_proof["workflow_package_staged"] is True
    assert Path(session["workflow_package_sqlite_path"]).exists()

    import cassandra_guided_review

    production_guided_default = tmp_path / "production-guided-default"
    production_guided_read_models = tmp_path / "production-guided-read-models"
    monkeypatch.setattr(cassandra_guided_review, "DEFAULT_REVIEW_ROOT", production_guided_default)
    monkeypatch.setattr(cassandra_guided_review, "DEFAULT_READ_MODEL_ROOT", production_guided_read_models)

    promotion_review = tmp_path / "probe-promotion-review.json"
    promotion_review.write_text(
        json.dumps(
            {
                "schema_version": "OPENCLAW_DATA_ROOM_PROMOTION_REVIEW_V0",
                "authoritative": False,
                "source_artifacts": ["task160_fixture"],
                "review_records": [
                    {
                        "record_id": "client:live_arts",
                        "provisional_marker": "*",
                        "authoritative": False,
                        "promotion_requires_winship_confirmation": True,
                        "review_category": "needs_correction",
                        "provisional_fact": "* old fixture truth",
                        "proposed_promoted_value": "* corrected fixture truth",
                        "confidence": "medium",
                        "source": "task160_fixture#review_records",
                        "risk_if_wrong": "wrong fixture truth",
                        "recommended_action": "revise",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    guided = cassandra_guided_review.process_guided_review_message(
        "Cassandra, let's go over the Data Room.",
        surface="mac_probe_replay",
        review_root=session["guided_review_root"],
        read_model_root=session["guided_review_read_model_root"],
        receipt_root=session["guided_review_receipt_root"],
        promotion_review_path=promotion_review,
        generated_at_utc=FIXED_NOW,
        run_mode_context={
            "run_mode": "test_dry_run",
            "resolution_status": "resolved",
            "test_run_id": session["test_run_id"],
            "test_marker": session["probe_marker"],
            "live_external_effects_allowed": False,
        },
    )
    assert guided is not None and guided["handled"] is True
    assert any(Path(session["guided_review_root"]).glob("*.json"))
    assert not production_guided_default.exists()
    assert not production_guided_read_models.exists()

    after = {
        path.name: _sha256(path)
        for path in (
            production_truth,
            production_recurrence,
            production_proposal,
            production_guided,
            production_workflow,
        )
    }
    assert after == before

    fixture_before = _sha256(Path(session["operator_truth_store_path"]))
    e1 = answer_frontdoor_chat(
        E1_QUESTION,
        source_surface="mac_probe_replay",
        session=session,
    )
    assert e1.intent_class != "operator_truth_correction"
    assert e1.machine_proof.get("operator_truth_store_written") is not True
    assert _sha256(Path(session["operator_truth_store_path"])) == fixture_before
