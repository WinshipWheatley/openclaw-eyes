"""Regression tests for brain/CHAT continuity-identity stamping.

BUG (fixed here): Maestro brain/CHAT responses were emitted WITHOUT
conversation_id / turn_id / operator_id / agent_id / thread_id, so the
continuity capsule + downstream correlation were starved even when the message
reached the brain. The previous conversation_id stamp lived only inside the
continuity write-back block (flag-gated AND requiring a non-empty minted
conversation_id AND a loaded capsule).

These tests prove the bug cannot recur:
  - A CHAT response always carries conversation_id + turn_id + operator_id +
    agent_id + thread_id (acceptance criterion 1).
  - The brain card's machine_proof carries the SAME conversation_id (+ turn_id)
    as the receipt correlation (criterion 2).
  - conversation_id is STABLE across a synthetic follow-up in the same
    conversation; turn_id differs per message (criterion 3).
  - Missing conversation context → a deterministic SAFE FALLBACK id, marked
    conversation_id_source="fallback" (criterion 4).
  - An explicitly-minted conversation_id is preserved (not overwritten).
  - NON-CHAT responses are returned UNCHANGED (no new fields) — flag-off
    byte-identity for the non-brain path is preserved.

All SYNTHETIC. No real LM/token/network/action call. Continuity flag NOT
required (the stamp is flag-independent by design).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_request_processor as processor
from openclaw_request_processor import OpenClawResponseForMac


_EXPECTED_IDS = ("conversation_id", "turn_id", "operator_id", "agent_id", "thread_id")


def _maestro_request(*, conversation_id: str | None = None, request_id: str = "req_1") -> dict[str, Any]:
    """A maestro frontdoor request shaped like the live listener output."""
    req: dict[str, Any] = {
        "request_id": request_id,
        "source_request_id": request_id,
        "source_channel": "maestro_listener",
        "active_surface_ref": "operator_maestro_chat",
        "thread_ref": "operator_maestro_chat",
        "current_thread_ref": "operator_maestro_chat",
        "active_entity_ref": "operator_maestro_chat",
        "telegram_chat_ref": "sha256:chat_stable_anchor",
        "speaker": "Winship",
        "actor": "operator_winship",
        "operator_text": "hey whats going on",
    }
    if conversation_id is not None:
        req["conversation_id"] = conversation_id
    return req


def _chat_response(detail: dict[str, Any] | None = None) -> OpenClawResponseForMac:
    """A minimal CHAT (brain) response with a dynamic card carrying machine_proof."""
    card = {
        "schema_version": "maestro_frontdoor_answer_card_v0",
        "proof": {"proof_refs": [], "machine_proof": {"text_response_only": True}},
    }
    base_detail = {"dynamic_card_response": card}
    if detail:
        base_detail.update(detail)
    return OpenClawResponseForMac(
        source_request_id="req_1",
        source_request_filename="req.json",
        workflow_ref="general/operator_maestro_chat",
        request_type="CHAT",
        internal_status="RESPONSE_READY",
        operator_headline="On track.",
        operator_message="On track.",
        what_happened=(),
        why_it_happened="",
        how_to_fix="",
        visible_cards=(card,),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None,
        detail_disclosure=base_detail,
        readback_files=(),
        next_safe_move="",
    )


def _workflow_response() -> OpenClawResponseForMac:
    """A non-CHAT (workflow) response — must be left UNCHANGED by the stamper."""
    return OpenClawResponseForMac(
        source_request_id="req_w",
        source_request_filename="req.json",
        workflow_ref="general/wf",
        request_type="WORKFLOW_PACKAGE_REQUEST",
        internal_status="RESPONSE_READY",
        operator_headline="Workflow staged",
        operator_message="Saved for review.",
        what_happened=(),
        why_it_happened="",
        how_to_fix="",
        visible_cards=(),
        cards_available=False,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None,
        detail_disclosure={"workflow_package_staged": True},
        readback_files=(),
        next_safe_move="",
    )


# ---------------------------------------------------------------------------
# Helper unit behavior
# ---------------------------------------------------------------------------

class TestContinuityIdentityHelpers:
    def test_explicit_conversation_id_preserved(self):
        ids = processor._continuity_identity_for_request(
            _maestro_request(conversation_id="conv_minted_abc")
        )
        assert ids["conversation_id"] == "conv_minted_abc"
        assert ids["conversation_id_source"] == "minted"

    def test_fallback_id_when_missing(self):
        ids = processor._continuity_identity_for_request(_maestro_request())
        assert ids["conversation_id"].startswith("conv_fallback_")
        assert ids["conversation_id_source"] == "fallback"

    def test_fallback_stable_across_followup_same_conversation(self):
        """conversation_id is the SAME for two turns in the same conversation;
        turn_id differs per message (request_id)."""
        ids1 = processor._continuity_identity_for_request(_maestro_request(request_id="req_1"))
        ids2 = processor._continuity_identity_for_request(_maestro_request(request_id="req_2"))
        assert ids1["conversation_id"] == ids2["conversation_id"]
        assert ids1["turn_id"] != ids2["turn_id"]

    def test_all_five_identifiers_present(self):
        ids = processor._continuity_identity_for_request(_maestro_request())
        for key in _EXPECTED_IDS:
            assert ids.get(key), f"{key} must be present and non-empty"
        assert ids["agent_id"] == "maestro"
        assert ids["operator_id"] == "operator_winship"
        assert ids["thread_id"] == "operator_maestro_chat"

    def test_operator_id_fallback_to_operator(self):
        req = _maestro_request()
        req.pop("actor"); req.pop("speaker")
        ids = processor._continuity_identity_for_request(req)
        assert ids["operator_id"] == "operator"

    def test_turn_id_unique_on_degraded_input_without_request_id(self):
        """Even with NO request_id/source_request_id, two turns in the same
        conversation get DISTINCT turn_ids (via payload_hash/created_at anchor),
        while conversation_id stays stable. Hardens the audit's degraded-input note."""
        base = _maestro_request()
        base.pop("request_id"); base.pop("source_request_id", None)
        m1 = dict(base, payload_hash="hash_turn_1")
        m2 = dict(base, payload_hash="hash_turn_2")
        i1 = processor._continuity_identity_for_request(m1)
        i2 = processor._continuity_identity_for_request(m2)
        assert i1["conversation_id"] == i2["conversation_id"]  # same conversation
        assert i1["turn_id"] != i2["turn_id"]  # distinct turns


# ---------------------------------------------------------------------------
# Stamper applied to responses
# ---------------------------------------------------------------------------

class TestStampContinuityIdentity:
    def test_chat_response_gets_all_ids(self):
        """Acceptance #1: CHAT response detail carries all five identifiers."""
        resp = processor._stamp_continuity_identity(_chat_response(), _maestro_request())
        detail = resp.detail_disclosure
        for key in _EXPECTED_IDS:
            assert detail.get(key), f"{key} missing from CHAT detail_disclosure"
        assert isinstance(detail.get("continuity_identity"), dict)

    def test_machine_proof_carries_same_conversation_id(self):
        """Acceptance #2: brain card machine_proof carries the SAME conversation_id."""
        resp = processor._stamp_continuity_identity(
            _chat_response(), _maestro_request(conversation_id="conv_minted_xyz")
        )
        detail = resp.detail_disclosure
        mp = detail["dynamic_card_response"]["proof"]["machine_proof"]
        assert detail["conversation_id"] == "conv_minted_xyz"
        assert mp["conversation_id"] == "conv_minted_xyz"
        assert mp["turn_id"] == detail["turn_id"]

    def test_fallback_id_when_no_conversation_context(self):
        """Acceptance #4: missing conversation_id → safe fallback, still stamped."""
        resp = processor._stamp_continuity_identity(_chat_response(), _maestro_request())
        detail = resp.detail_disclosure
        assert detail["conversation_id"].startswith("conv_fallback_")
        assert detail["continuity_identity"]["conversation_id_source"] == "fallback"
        # machine_proof still gets the fallback id
        mp = detail["dynamic_card_response"]["proof"]["machine_proof"]
        assert mp["conversation_id"] == detail["conversation_id"]

    def test_followup_preserves_conversation_id(self):
        """Acceptance #3: a synthetic follow-up in the same conversation keeps the
        same conversation_id; turn_id changes."""
        r1 = processor._stamp_continuity_identity(_chat_response(), _maestro_request(request_id="req_1"))
        r2 = processor._stamp_continuity_identity(_chat_response(), _maestro_request(request_id="req_2"))
        assert r1.detail_disclosure["conversation_id"] == r2.detail_disclosure["conversation_id"]
        assert r1.detail_disclosure["turn_id"] != r2.detail_disclosure["turn_id"]

    def test_existing_conversation_id_in_detail_not_clobbered(self):
        """If the continuity write-back already stamped a conversation_id, the
        identity stamper must NOT overwrite it (setdefault)."""
        resp = _chat_response(detail={"conversation_id": "conv_from_writeback"})
        stamped = processor._stamp_continuity_identity(resp, _maestro_request(conversation_id="conv_minted_other"))
        # the pre-existing detail value wins
        assert stamped.detail_disclosure["conversation_id"] == "conv_from_writeback"

    def test_non_chat_response_unchanged(self):
        """NON-CHAT responses are returned byte-identical (no new id fields)."""
        original = _workflow_response()
        stamped = processor._stamp_continuity_identity(original, _maestro_request())
        assert stamped is original  # same object, untouched
        assert "conversation_id" not in stamped.detail_disclosure
        assert set(stamped.detail_disclosure.keys()) == {"workflow_package_staged"}

    def test_stamper_never_raises_on_bad_response(self):
        """The stamper must never raise — returns the response on any error."""
        # detail_disclosure not a dict → still must not raise
        bad = _chat_response()
        object.__setattr__(bad, "detail_disclosure", None)
        out = processor._stamp_continuity_identity(bad, _maestro_request())
        assert out is not None  # returned safely


# ---------------------------------------------------------------------------
# End-to-end through the interpreter brain divert (real CHAT response)
# ---------------------------------------------------------------------------

class TestEndToEndBrainDivertCarriesIds:
    def test_interpreter_brain_divert_response_stampable(self, tmp_path, monkeypatch):
        """A real _try_interpreter_brain_divert CHAT response, once passed through
        the identity stamper, carries all continuity ids in detail + machine_proof.
        This proves the brain/CHAT path the bug affected is now covered."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

        import interpreter_lm
        import maestro_cassandra_responder as maestro

        # Mock the interpreter (BRAIN) and the answering LM — no real tokens.
        def _interp(text, *, session=None, protected_generate_fn=None):
            return interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_BRAIN, fact_selection=[], confidence=0.95,
                reason="conversational",
            )

        def _answer(t, *, session=None, source_surface="operator_maestro_chat", _capsule=None, **kw):
            return maestro.MaestroCassandraResult(
                status="ANSWER_READY", intent_class="maestro_brain_freeform",
                allowed_to_call_handle=False, one_line_answer="On track.",
                plain_summary="On track.", machine_proof={"text_response_only": True},
            )

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _interp)
        monkeypatch.setattr(maestro, "answer_frontdoor_chat", _answer)
        processor._INTERPRETER_RESULT_CACHE.clear()

        from openclaw_request_processor import RequestClassification
        classification = RequestClassification(
            classification_id="c", source_request_filename="req.json",
            request_family="WORKFLOW_PACKAGE_REQUEST",
            selected_rail="WORKFLOW_PACKAGE_REQUEST_CONSUMER",
            classification_reason="t", future_supported=True, next_safe_move="r",
        )

        req = _maestro_request()
        # NO authority_boundary → deterministic gate declines → interpreter diverts
        import json as _json
        req_path = tmp_path / "req.json"
        req_path.write_text(_json.dumps(req), encoding="utf-8")

        resp = processor._try_interpreter_brain_divert(
            req_path, req, classification=classification, route_decision={}, _capsule=None,
        )
        assert resp is not None and resp.request_type == "CHAT"

        # Apply the identity stamper (the wrapper does this in process_request_path).
        stamped = processor._stamp_continuity_identity(resp, req)
        detail = stamped.detail_disclosure
        for key in _EXPECTED_IDS:
            assert detail.get(key), f"{key} missing from brain-divert CHAT response"
        mp = detail["dynamic_card_response"]["proof"]["machine_proof"]
        assert mp["conversation_id"] == detail["conversation_id"]
        # Authority stays locked (no regression to the interpreter contract).
        assert detail["external_actions_locked"] is True
        assert detail["email_send_performed"] is False
