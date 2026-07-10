from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

import invoice_cockpit_ops as cockpit_ops
import invoice_cockpit_session as cockpit_session
import invoice_generator
import invoice_send_workflow as workflow
import typed_contract_decision as contract
from clarify_session_contract import stamp_clarify_session
from origin_bound_output import OriginBoundOutput, OriginDeliveryTracker, OutputOrigin


ROOT = Path(__file__).resolve().parents[1]
FINALIZED_PDF = ROOT / "state" / "invoices" / "WL-2026-0009__St_Annes.pdf"
COUNTER = ROOT / "state" / "invoices" / "tracker" / "invoice_counter_2026.txt"
INCOMING_RECEIPT = ROOT / "state" / "invoice_cockpit" / "incoming" / "st-annes.json"
JUNE_PDF = ROOT / "state" / "invoice_cockpit" / "incoming" / "st_annes_june.pdf"
EXPECTED_SHA256 = "0d1ebb2f6eb74f488e8c5d6e40e4c48907001eacea1a6851f297f3ef00a7041b"


@pytest.fixture(autouse=True)
def _listener_import_environment(monkeypatch):
    monkeypatch.setenv("CASSANDRA_BOT_TOKEN", "task152-test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "4242")


def _origin() -> OutputOrigin:
    return OutputOrigin(
        surface="cassandra_telegram",
        bot_identity="cassandra",
        chat_id="4242",
        source_message_id="152-acceptance",
        audience="operator",
    )


def _forbidden(name: str):
    def fail(*_args, **_kwargs):
        raise AssertionError(f"forbidden path ran: {name}")

    return fail


@pytest.fixture
def finalized_environment(monkeypatch):
    assert FINALIZED_PDF.is_file()
    assert FINALIZED_PDF.stat().st_size == 2720
    assert hashlib.sha256(FINALIZED_PDF.read_bytes()).hexdigest() == EXPECTED_SHA256
    assert COUNTER.is_file()
    assert INCOMING_RECEIPT.is_file()
    assert JUNE_PDF.is_file()

    monkeypatch.setenv("OPENCLAW_INVOICES_DIR", str(FINALIZED_PDF.parent))
    monkeypatch.setenv("OPENCLAW_INVOICE_TRACKER_DIR", str(COUNTER.parent))
    monkeypatch.setenv("OPENCLAW_INVOICE_COCKPIT_INCOMING_DIR", str(INCOMING_RECEIPT.parent))
    monkeypatch.setattr(cockpit_ops, "_load_real_invoice_receipt", _forbidden("June receipt loader"))
    monkeypatch.setattr(invoice_generator, "get_next_invoice_number", _forbidden("counter allocator"))
    monkeypatch.setattr(invoice_generator, "generate_invoice_pdf", _forbidden("PDF generator"))
    monkeypatch.setattr(cockpit_ops.RealCockpitOps, "prepare_invoice", _forbidden("legacy prepare_invoice"))
    monkeypatch.setattr(
        cockpit_ops.RealCockpitOps,
        "finalized_review_attachment",
        _forbidden("legacy finalized_review_attachment"),
    )
    monkeypatch.setattr(cockpit_ops.RealCockpitOps, "send_email", _forbidden("send_email"))
    monkeypatch.setattr(
        cockpit_ops.RealCockpitOps,
        "clara_draft_and_guardian",
        _forbidden("draft/broker/Guardian path"),
    )
    return {
        "counter": COUNTER.read_bytes(),
        "invoice_listing": tuple(sorted(path.name for path in FINALIZED_PDF.parent.iterdir())),
        "incoming_receipt": INCOMING_RECEIPT.read_bytes(),
        "june_pdf_sha256": hashlib.sha256(JUNE_PDF.read_bytes()).hexdigest(),
    }


def _assert_runtime_unchanged(before: dict[str, object]) -> None:
    assert COUNTER.read_bytes() == before["counter"]
    assert tuple(sorted(path.name for path in FINALIZED_PDF.parent.iterdir())) == before["invoice_listing"]
    assert INCOMING_RECEIPT.read_bytes() == before["incoming_receipt"]
    assert hashlib.sha256(JUNE_PDF.read_bytes()).hexdigest() == before["june_pdf_sha256"]


def _write_rates_promotion(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "OPENCLAW_DATA_ROOM_PROMOTION_REVIEW_V0",
                "authoritative": False,
                "source_artifacts": ["fixture://task152"],
                "review_records": [
                    {
                        "record_id": "rate:live_arts_multiple_services",
                        "provisional_marker": "*",
                        "authoritative": False,
                        "promotion_requires_winship_confirmation": True,
                        "review_category": "needs_correction",
                        "provisional_fact": "* Live Arts rates need review.",
                        "proposed_promoted_value": "* Confirm the rate and client mapping.",
                        "confidence": "medium",
                        "source": "fixture://task152#rate",
                        "risk_if_wrong": "Wrong rate could create a wrong invoice.",
                        "recommended_action": "revise",
                    },
                    {
                        "record_id": "client:capital_hilton",
                        "provisional_marker": "*",
                        "authoritative": False,
                        "promotion_requires_winship_confirmation": True,
                        "review_category": "needs_source",
                        "provisional_fact": "* Capital Hilton client details need review.",
                        "proposed_promoted_value": "* Confirm the client mapping.",
                        "confidence": "medium",
                        "source": "fixture://task152#client",
                        "risk_if_wrong": "Wrong client data could route an invoice incorrectly.",
                        "recommended_action": "source needed",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_real_ops_selects_existing_finalized_wl_artifact_without_generation(finalized_environment):
    data, pdf_path, digest = cockpit_ops.RealCockpitOps(origin=_origin()).prepare_existing_finalized_invoice(
        {"client_ref": "st_annes", "display_name": "St Anne's"},
        requested_period="2026-07",
    )

    assert Path(pdf_path).resolve() == FINALIZED_PDF.resolve()
    assert Path(pdf_path).read_bytes() == FINALIZED_PDF.read_bytes()
    assert digest == EXPECTED_SHA256
    assert data["invoice_number"] == "WL-2026-0009"
    assert data["invoice_status"] == "issued"
    assert data["requested_period"] == "2026-07"
    assert data["source"] == "existing_finalized_artifact"
    assert data["invoice_number"] != "3"
    assert Path(pdf_path).resolve() != JUNE_PDF.resolve()
    _assert_runtime_unchanged(finalized_environment)


@pytest.mark.parametrize(
    ("prompt", "period"),
    (
        ("get the St Anne's July invoice ready for my review", "2026-07"),
        ("prep the St Anne's July invoice so I can look it over", "2026-07"),
        ("Can you prepare the July invoice for St Anne’s and get it ready for my review?", "2026-07"),
        ("Please pull up St. Anne's July invoice so I can review the final copy.", "2026-07"),
        ("prep the st. anne's July invoice for my review", "2026-07"),
        ("surface the finalized St Anne's invoice", None),
        (
            "did St Anne's pay us, and if not can you get their invoice ready for my review while you're at it?",
            None,
        ),
    ),
)
def test_review_phrasings_bypass_interpreter_and_emit_one_existing_document(
    prompt,
    period,
    finalized_environment,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        cockpit_session,
        "_interpreter_invoice_trigger",
        _forbidden("interpreter before finalized-review contract"),
    )
    store = cockpit_ops.JsonSessionStore(tmp_path / "session.json")
    ops = cockpit_ops.RealCockpitOps(origin=_origin())

    result = cockpit_session.handle_invoice_cockpit_message(
        prompt,
        ops=ops,
        store=store,
        surface="cassandra_telegram",
    )

    assert result["handled"] is True
    assert result["stage"] == workflow.AWAITING_INVOICE_APPROVAL
    assert result["requested_period"] == period
    state = store.load()
    assert state is not None
    assert state["stage"] == workflow.AWAITING_INVOICE_APPROVAL
    assert state["artifact_reused"] is True
    assert state["pdf_path"] == str(FINALIZED_PDF.resolve())
    assert state["attachment_sha256"] == EXPECTED_SHA256
    assert state["invoice_data"]["invoice_number"] == "WL-2026-0009"
    assert len(result["origin_outputs"]) == 1
    output = result["origin_outputs"][0]
    assert output.kind == "document"
    assert Path(output.document_path).resolve() == FINALIZED_PDF.resolve()
    assert "WL-2026-0009" in output.visible_text()
    assert "Nothing was sent" in output.visible_text()
    assert "draft" not in output.visible_text().lower()
    _assert_runtime_unchanged(finalized_environment)


def test_specific_finalized_review_supersedes_an_active_cockpit_session(
    finalized_environment,
    tmp_path,
):
    store = cockpit_ops.JsonSessionStore(tmp_path / "session.json")
    old_state, _ = workflow.start_invoice_send(
        "Old Client",
        {"client_name": "Old Client", "invoice_number": "OLD-DRAFT"},
        "/tmp/old-draft.pdf",
        "oldhash",
    )
    stamp_clarify_session(old_state, surface="cassandra_telegram")
    store.save(old_state)

    result = cockpit_session.handle_invoice_cockpit_message(
        "get the St Anne's July invoice ready for my review",
        ops=cockpit_ops.RealCockpitOps(origin=_origin()),
        store=store,
        surface="cassandra_telegram",
    )

    assert result["handled"] is True
    assert result["stage"] == workflow.AWAITING_INVOICE_APPROVAL
    new_state = store.load()
    assert new_state["artifact_reused"] is True
    assert new_state["invoice_data"]["invoice_number"] == "WL-2026-0009"
    assert new_state["pdf_path"] == str(FINALIZED_PDF.resolve())
    assert len(result["origin_outputs"]) == 1


def test_failed_supersession_preserves_the_previous_active_session(monkeypatch, tmp_path):
    store = cockpit_ops.JsonSessionStore(tmp_path / "session.json")
    old_state, _ = workflow.start_invoice_send(
        "Old Client",
        {"client_name": "Old Client", "invoice_number": "OLD-DRAFT"},
        "/tmp/old-draft.pdf",
        "oldhash",
    )
    stamp_clarify_session(old_state, surface="cassandra_telegram")
    store.save(old_state)
    before = store.path.read_bytes()
    empty = tmp_path / "empty-invoices"
    empty.mkdir()
    monkeypatch.setenv("OPENCLAW_INVOICES_DIR", str(empty))

    result = cockpit_session.handle_invoice_cockpit_message(
        "get the St Anne's July invoice ready for my review",
        ops=cockpit_ops.RealCockpitOps(origin=_origin()),
        store=store,
        surface="cassandra_telegram",
    )

    assert result["handled"] is True
    assert result["error"] == "could not surface the existing finalized invoice"
    assert store.path.read_bytes() == before


def test_cross_surface_finalized_request_does_not_replace_another_surface_session(tmp_path):
    store = cockpit_ops.JsonSessionStore(tmp_path / "session.json")
    old_state, _ = workflow.start_invoice_send(
        "Maestro Client",
        {"client_name": "Maestro Client", "invoice_number": "MAESTRO-DRAFT"},
        "/tmp/maestro-draft.pdf",
        "oldhash",
    )
    stamp_clarify_session(old_state, surface="maestro")
    store.save(old_state)
    before = store.path.read_bytes()

    result = cockpit_session.handle_invoice_cockpit_message(
        "get the St Anne's July invoice ready for my review",
        ops=cockpit_ops.RealCockpitOps(origin=_origin()),
        store=store,
        surface="cassandra_telegram",
    )

    assert result["handled"] is False
    assert result["pass_through_reason"] == "surface_mismatch"
    assert store.path.read_bytes() == before


@pytest.mark.parametrize(
    "near_miss",
    (
        "review my rates and clients",
        "review the St Anne's client rates",
        "what is the status of the St Anne's invoice?",
        "did you get the St Anne's invoice yet?",
        "get me the St Anne's invoice status; then review my rates",
    ),
)
def test_rates_client_and_status_near_misses_do_not_claim_finalized_artifact(
    near_miss,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(cockpit_session, "_interpreter_invoice_trigger", lambda _text: cockpit_session._INTERPRETER_NO_TRIGGER)
    result = cockpit_session.handle_invoice_cockpit_message(
        near_miss,
        ops=cockpit_ops.RealCockpitOps(origin=_origin()),
        store=cockpit_ops.JsonSessionStore(tmp_path / "session.json"),
        surface="cassandra_telegram",
    )
    assert result["handled"] is False


def test_invoice_bound_month_beats_earlier_payment_month():
    request = cockpit_session._detect_finalized_artifact_review(
        "Compare the May payment, then get the St Anne's July invoice ready for my review"
    )
    assert request is not None
    assert request["requested_period"] == "2026-07"


@pytest.mark.parametrize("verb", ("prep", "prepare", "get", "make", "surface", "pull up", "show"))
def test_typed_finalized_language_has_a_real_cockpit_owner(verb):
    prompt = f"{verb} the finalized St Anne's invoice"
    decision = contract.decide_contract(
        prompt,
        context=contract.ContractContext(agent="cassandra", surface="cassandra_telegram"),
        semantic_vote_enabled=False,
    )
    assert decision.label is contract.ContractLabel.FINALIZED_INVOICE_REVIEW
    assert decision.action is contract.DecisionAction.PASS_THROUGH
    assert cockpit_session._detect_finalized_artifact_review(prompt) is not None


@pytest.mark.parametrize(
    "prompt",
    (
        "prepare the St Anne's invoice as finalized",
        "get the St Anne's invoice finalized",
        "show me the St Anne's invoice final",
    ),
)
def test_typed_post_invoice_final_language_has_a_real_cockpit_owner(prompt):
    decision = contract.decide_contract(
        prompt,
        context=contract.ContractContext(agent="cassandra", surface="cassandra_telegram"),
        semantic_vote_enabled=False,
    )
    assert decision.label is contract.ContractLabel.FINALIZED_INVOICE_REVIEW
    assert decision.action is contract.DecisionAction.PASS_THROUGH
    assert cockpit_session._detect_finalized_artifact_review(prompt) is not None


def test_requested_month_filters_a_newer_same_client_artifact(monkeypatch, tmp_path):
    july = tmp_path / "WL-2026-0009__St_Annes.pdf"
    august = tmp_path / "WL-2026-0010__St_Annes.pdf"
    july.write_bytes(b"july-finalized")
    august.write_bytes(b"august-finalized")
    monkeypatch.setenv("OPENCLAW_INVOICES_DIR", str(tmp_path))
    monkeypatch.setattr(
        cockpit_ops,
        "_finalized_pdf_issue_period",
        lambda path: ("2026-07", "2026-07-07") if path.name == july.name else ("2026-08", "2026-08-01"),
    )

    data, selected, digest = cockpit_ops.RealCockpitOps(origin=_origin()).prepare_existing_finalized_invoice(
        {"client_ref": "st_annes", "display_name": "St Anne's"},
        requested_period="2026-07",
    )

    assert Path(selected) == july
    assert data["invoice_number"] == "WL-2026-0009"
    assert data["issue_date"] == "2026-07-07"
    assert digest == hashlib.sha256(b"july-finalized").hexdigest()


def test_review_my_rates_and_clients_still_reaches_existing_wizard_owner(monkeypatch, tmp_path):
    import cassandra_listener

    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        cassandra_listener,
        "cassandra_handle",
        lambda text, meta: calls.append((text, meta)) or ["RATES-CLIENTS-WIZARD"],
    )
    replies = asyncio.run(
        cassandra_listener._run_cassandra_handle_async(
            "review my rates and clients",
            {
                "surface": "cassandra_telegram",
                "bot_identity": "cassandra",
                "sender_chat_id": 4242,
                "source_message_id": "152-rates-near-miss",
                "source_user_label": "operator",
                "invoice_cockpit_session_path": str(tmp_path / "session.json"),
                "guided_review_root": str(tmp_path / "guided"),
            },
        )
    )

    assert replies == ["RATES-CLIENTS-WIZARD"]
    assert len(calls) == 1


def test_real_rates_clients_guided_review_still_opens(tmp_path):
    import cassandra_guided_review as guided

    promotion = _write_rates_promotion(tmp_path / "promotion_review.json")
    result = guided.process_guided_review_message(
        "review my rates and clients",
        surface="telegram",
        review_root=tmp_path / "guided",
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
        promotion_review_path=promotion,
        generated_at_utc="2026-07-10T03:00:00+00:00",
    )

    assert result is not None and result["handled"] is True
    session = json.loads(Path(result["artifact_refs"]["session_json"]).read_text(encoding="utf-8"))
    assert session["topic"] == guided.TOPIC_RATES_CLIENTS_VENUES
    assert session["status"] == "active"
    assert result["current_question_id"]


def test_listener_to_real_brain_opens_rates_clients_wizard(tmp_path):
    import cassandra_guided_review as guided
    import cassandra_listener

    promotion = _write_rates_promotion(tmp_path / "promotion_review.json")
    review_root = tmp_path / "guided"
    replies = asyncio.run(
        cassandra_listener._run_cassandra_handle_async(
            "review my rates and clients",
            {
                "surface": "cassandra_telegram",
                "bot_identity": "cassandra",
                "sender_chat_id": 4242,
                "source_message_id": "152-real-rates-wizard",
                "source_user_label": "operator",
                "invoice_cockpit_session_path": str(tmp_path / "cockpit-session.json"),
                "guided_review_root": str(review_root),
                "guided_review_read_model_root": str(tmp_path / "read_models"),
                "guided_review_receipt_root": str(tmp_path / "receipts"),
                "guided_review_promotion_review_path": str(promotion),
                "received_at_utc": "2026-07-10T03:00:00+00:00",
            },
        )
    )

    assert len(replies) == 1
    assert "review" in replies[0].lower()
    sessions = list(review_root.glob("*.json"))
    assert sessions
    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in sessions]
    active = [payload for payload in payloads if payload.get("status") == "active"]
    assert active and active[0]["topic"] == guided.TOPIC_RATES_CLIENTS_VENUES


def test_missing_finalized_artifact_becomes_one_honest_origin_bound_line(
    monkeypatch,
    tmp_path,
):
    import cassandra_listener

    empty_invoices = tmp_path / "empty-invoices"
    empty_invoices.mkdir()
    monkeypatch.setenv("OPENCLAW_INVOICES_DIR", str(empty_invoices))
    origin = _origin()
    outputs = cassandra_listener._try_invoice_cockpit(
        "get the St Anne's July invoice ready for my review",
        {
            "surface": origin.surface,
            "bot_identity": origin.bot_identity,
            "sender_chat_id": int(origin.chat_id),
            "source_message_id": origin.source_message_id,
            "source_user_label": origin.audience,
        },
        ops=cockpit_ops.RealCockpitOps(origin=origin),
        store=cockpit_ops.JsonSessionStore(tmp_path / "session.json"),
    )

    assert outputs is not None and len(outputs) == 1
    output = outputs[0]
    assert isinstance(output, OriginBoundOutput)
    assert output.kind == "text"
    assert "couldn't prepare that invoice for review" in output.visible_text()
    assert "Nothing was sent" in output.visible_text()
    assert output.receipt_pointer in output.visible_text()
    assert "FileNotFoundError" not in output.visible_text()
    assert not (tmp_path / "session.json").exists()


def test_origin_adapter_delivers_finalized_document_once_on_helper_replay(
    finalized_environment,
    tmp_path,
):
    import cassandra_listener

    origin = _origin()
    result = cockpit_session.handle_invoice_cockpit_message(
        "Can you prepare the July invoice for St Anne’s and get it ready for my review?",
        ops=cockpit_ops.RealCockpitOps(origin=origin),
        store=cockpit_ops.JsonSessionStore(tmp_path / "session.json"),
        surface="cassandra_telegram",
    )
    output = result["origin_outputs"][0]
    tracker = OriginDeliveryTracker()
    documents: list[tuple[str, str]] = []
    texts: list[str] = []

    async def send_text(text, reply_markup=None):
        texts.append(text)

    async def send_document(path, caption):
        documents.append((path, caption))

    async def deliver_twice():
        first = await cassandra_listener._dispatch_origin_bound_output(
            output,
            bound_origin=origin,
            send_text=send_text,
            send_document=send_document,
            tracker=tracker,
        )
        second = await cassandra_listener._dispatch_origin_bound_output(
            output,
            bound_origin=origin,
            send_text=send_text,
            send_document=send_document,
            tracker=tracker,
        )
        return first, second

    assert asyncio.run(deliver_twice()) == (True, False)
    assert documents == [(str(FINALIZED_PDF), output.visible_text())]
    assert texts == []
    _assert_runtime_unchanged(finalized_environment)


def test_task151_compound_seam_runs_money_and_real_artifact_once(
    finalized_environment,
    monkeypatch,
    tmp_path,
):
    import cassandra_listener
    import money_truth

    monkeypatch.setattr(money_truth, "render_money_answer", lambda *_a, **_k: "MONEY-TRUTH")
    replies = asyncio.run(
        cassandra_listener._run_cassandra_handle_async(
            "did St Anne's pay us, and if not can you get their invoice ready for my review while you're at it?",
            {
                "surface": "cassandra_telegram",
                "bot_identity": "cassandra",
                "sender_chat_id": 4242,
                "source_message_id": "152-compound",
                "source_user_label": "operator",
                "invoice_cockpit_session_path": str(tmp_path / "session.json"),
            },
        )
    )

    assert len(replies) == 2
    assert replies[0] == "MONEY-TRUTH"
    assert isinstance(replies[1], OriginBoundOutput)
    assert replies[1].kind == "document"
    assert Path(replies[1].document_path).resolve() == FINALIZED_PDF.resolve()
    _assert_runtime_unchanged(finalized_environment)
