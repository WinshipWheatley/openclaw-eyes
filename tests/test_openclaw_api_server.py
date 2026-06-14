import sys
import types

import pytest

import openclaw_api_server as api
from chief_compose import compose
from compose_contract import ComposeResult, GateState


def _stub_chief_router(monkeypatch, *, intent="communication_summary_request", reply="[stubbed read-only reply]"):
    stub = types.ModuleType("chief_router")
    stub.route_message = lambda text: {"intent": intent, "reply": reply}
    monkeypatch.setitem(sys.modules, "chief_router", stub)


def test_verify_bearer_header():
    assert api.verify_bearer_header("Bearer abc", "abc") is True
    assert api.verify_bearer_header("Bearer wrong", "abc") is False
    assert api.verify_bearer_header(None, "abc") is False
    assert api.verify_bearer_header("Bearer abc", None) is False


def test_api_render_hides_unknown_review_from_primary_intent():
    result = ComposeResult.pending(
        intent="unknown_review",
        packet_id="packet_fixture",
        surface="unknown_review",
        segments=["Draft a bounded plan for unknown_review."],
    )

    payload = api.render_api_compose_result(result)

    assert payload["intent"] == "needs_clarification"
    assert payload["meta"]["debug_intent"] == "unknown_review"
    assert "unknown_review" not in " ".join(payload["segments"])
    assert "Nothing has been sent yet." in payload["segments"]


def test_api_render_enforces_pending_copy_and_button_label():
    result = ComposeResult.pending(
        intent="invoice_send",
        packet_id="packet_fixture",
        surface="invoice_send",
        segments=["Prepare an invoice-send approval card."],
    )

    payload = api.render_api_compose_result(result)

    assert "Nothing has been sent yet." in payload["segments"]
    assert payload["pending_approval"]["preview"]["button_label"] == "Approve invoice send"


def test_pending_packets_and_approve_stale_hash_use_packet_state(tmp_path, monkeypatch):
    _stub_chief_router(monkeypatch)
    db_path = tmp_path / "ledger.sqlite"
    result = compose(
        "send the Capital Hilton invoice for 4200 dollars",
        source_kind="mission_control",
        source_channel="api_test",
        requested_by="winship",
        db_path=str(db_path),
    )

    packets = api.list_pending_packets(db_path=db_path)
    assert packets[0]["packet_id"] == result.packet_id
    assert packets[0]["surface"] == "invoice_send"
    assert packets[0]["preview"]["packet_hash"]

    receipt = api.approve_packet(
        result.packet_id,
        surface="invoice_send",
        expected_packet_hash="stale",
        db_path=db_path,
    )
    assert receipt["ok"] is False
    assert "stale-hash" in receipt["detail"]


def test_file_reference_records_metadata_only(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    source = tmp_path / "operator_note.txt"
    source.write_text("metadata fixture", encoding="utf-8")

    result = api.register_file_reference(
        path_ref=str(source),
        display_name="operator_note.txt",
        intended_use="test intake",
        db_path=db_path,
    )

    assert result["acknowledged"] is True
    assert result["exists"] is True
    assert result["metadata_only"] is True
    assert result["stored_ref"].startswith("file_inventory:")


def test_create_app_reports_missing_dependency_when_fastapi_absent():
    if api.FASTAPI_AVAILABLE:
        pytest.skip("FastAPI installed in this environment")
    with pytest.raises(RuntimeError, match="FastAPI runtime is not installed"):
        api.create_app()
