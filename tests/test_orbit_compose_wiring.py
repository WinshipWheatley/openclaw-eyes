import importlib
import sys
import types
from pathlib import Path

import pytest

from chief_compose import compose
from compose_contract import GateState
from intent_router import route_operator_intent


TEMP_DB = Path("/tmp/orbit_compose_wiring.sqlite")


@pytest.fixture(autouse=True)
def clean_temp_db():
    try:
        TEMP_DB.unlink()
    except FileNotFoundError:
        pass
    yield
    try:
        TEMP_DB.unlink()
    except FileNotFoundError:
        pass


def test_chief_invoice_brain_is_retired_import_safe_tombstone():
    module = importlib.import_module("chief_invoice_brain")
    source = Path(module.__file__).read_text(encoding="utf-8")

    assert module.RETIRED is True
    assert module.status()["disposition"] == "retired"
    assert module.status()["send_performed"] is False
    assert module.status()["polling_loop_active"] is False
    assert "invoice_send_executor.py" in module.status()["superseded_by"]
    assert module.get_questions("INVOICE") == []
    assert module.handle("INVOICE") == [
        "chief_invoice_brain.py is retired. Use the gated billing/invoice executor path."
    ]
    assert "while True" not in source
    assert "subprocess" not in source
    assert "chief_sender.py" not in source


def test_orbit_router_does_not_import_retired_invoice_brain():
    source = Path("chief_router.py").read_text(encoding="utf-8")

    assert "chief_billing_brain import" in source
    assert "chief_invoice_brain" not in source


def _stub_chief_router(monkeypatch):
    stub = types.ModuleType("chief_router")

    def route_message(text):
        return {"intent": "legacy_orbit_stub", "reply": f"legacy handled: {text[:24]}"}

    stub.route_message = route_message
    monkeypatch.setitem(sys.modules, "chief_router", stub)


@pytest.mark.parametrize(
    ("text", "expected_category", "world_hint"),
    [
        ("what are my music law options for Ten Fingers?", "musiclaw_query", "business_development"),
        ("publishing status for the catalog", "publishing_query", "business_development"),
        ("what did I make this month?", "cpa_query", "finance"),
        ("financial report and outstanding invoices", "financial_report", "finance"),
        ("show analytics for the business", "analytics_report", "operations"),
        ("goal check", "goals_check", "operations"),
        ("momentum report", "momentum_check", "operations"),
        ("reflection report", "reflection_report", "operations"),
        ("system report", "system_report", "operations"),
        ("what's my week on the calendar?", "calendar_query", "communications"),
        ("brand guide for DPR", "brand_guide", "music_art"),
        ("content calendar status", "content_calendar", "music_art"),
        ("scout report", "scout_report", "operations"),
        ("call history", "phone_assist", "communications"),
        ("backup status", "backup_status", "operations"),
        ("album status", "album_request", "music_art"),
        ("brainstorm status", "brainstorm_status", "operations"),
        ("what's queued?", "queue_status", "operations"),
        ("integration proposals", "integration_proposals", "operations"),
        ("trinity check", "trinity_check", "operations"),
        ("what should I post on Instagram?", "marketing_ideas", "music_art"),
    ],
)
def test_orbit_read_only_categories_route_without_approval(text, expected_category, world_hint):
    result = route_operator_intent(
        text=text,
        source_kind="mission_control",
        source_channel="orbit_test",
        requested_by="winship",
        db_path=TEMP_DB,
    )

    assert result.intent_category == expected_category
    assert result.routed_agent_id == "chief"
    assert result.world_hint == world_hint
    assert result.candidate_action_type is None
    assert result.approval_required is False
    assert result.execution_allowed is False
    assert result.action_request_created is False


@pytest.mark.parametrize(
    "text",
    [
        "what are my music law options for Ten Fingers?",
        "publishing status for the catalog",
        "goal check",
        "backup status",
        "what's queued?",
    ],
)
def test_orbit_read_only_compose_uses_legacy_handler_without_packet(monkeypatch, text):
    _stub_chief_router(monkeypatch)

    result = compose(
        text,
        source_kind="mission_control",
        source_channel="orbit_test",
        requested_by="winship",
        db_path=str(TEMP_DB),
    )

    assert result.gate_state is GateState.READ_ONLY
    assert result.packet_id is None
    assert result.pending_approval is None
    assert result.intent == "legacy_orbit_stub"
    assert result.segments == [f"legacy handled: {text[:24]}"]


@pytest.mark.parametrize(
    ("text", "expected_category", "expected_candidate"),
    [
        ("send email to Sally about the Reynolds gig", "email_send", "email_send"),
        ("send a text to Sally about the Reynolds gig", "sms_send", "sms_send"),
        ("log call with Sally about the invoice", "phone_log", "phone_log"),
        ("make a calendar event for the gig", "calendar_create", "calendar_create"),
        ("backup now", "unknown_review", None),
        ("set goal book more gigs", "unknown_review", None),
        ("schedule post DPR reel tomorrow", "unknown_review", None),
        ("approve PROP-20260614-001", "unknown_review", None),
    ],
)
def test_orbit_write_like_phrases_do_not_fast_path(text, expected_category, expected_candidate):
    result = route_operator_intent(
        text=text,
        source_kind="mission_control",
        source_channel="orbit_test",
        requested_by="winship",
        db_path=TEMP_DB,
    )

    assert result.intent_category == expected_category
    assert result.candidate_action_type == expected_candidate
    assert result.approval_required is True
    assert result.execution_allowed is False
