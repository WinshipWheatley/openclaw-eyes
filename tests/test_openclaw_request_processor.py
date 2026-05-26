import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import conversational_workflow_router_intake as chat_intake
import openclaw_request_processor as processor
import operator_file_metadata_intake as file_intake
from scripts.process_openclaw_requests import main as process_main


FIXED_NOW = "2026-05-25T16:00:00+00:00"


def _write_chat_request(path: Path, *, created_at: str = FIXED_NOW) -> dict:
    request = chat_intake.make_capital_hilton_fixture_request(created_at=created_at)
    path.write_text(chat_intake.stable_json(request), encoding="utf-8")
    return request


def _write_capital_hilton_status_request(path: Path, *, message: str, created_at: str = FIXED_NOW) -> dict:
    request = chat_intake.make_capital_hilton_fixture_request(created_at=created_at)
    request.update(
        {
            "request_id": "mission_control_chat_request_capital_hilton_status_fixture",
            "workflow_ref": "capital_hilton_invoice_workflow",
            "operator_message": message,
            "sanitized_message_summary": message,
            "idempotency_key": "mc_chat_capital_hilton_invoice_status_fixture",
        }
    )
    request["payload_hash"] = chat_intake.compute_request_payload_hash(request)
    path.write_text(chat_intake.stable_json(request), encoding="utf-8")
    return request


def _write_file_request(path: Path, *, fixture: str = "spreadsheet", created_at: str = FIXED_NOW) -> dict:
    request = file_intake.make_fixture_request(fixture, created_at=created_at)
    path.write_text(file_intake.stable_json(request), encoding="utf-8")
    return request


def _write_future_request(path: Path) -> dict:
    request = {
        "request_id": "future_context_request_001",
        "workflow_ref": "workflow_build_openclaw_context",
        "idempotency_key": "future-context-idempotency-001",
        "payload_hash": "sha256:futurecontext001",
        "authority_boundary": {
            "live_model_call_allowed": False,
            "live_agent_dispatch_allowed": False,
            "live_external_action_allowed": False,
            "credential_handling_allowed": False,
            "raw_body_ingestion_allowed": False,
        },
        "created_at": FIXED_NOW,
    }
    path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return request


def _read_response(export_root: Path) -> dict:
    return json.loads((export_root / processor.RESPONSE_JSON_EXPORT_NAME).read_text(encoding="utf-8"))


def _read_status(export_root: Path) -> dict:
    return json.loads((export_root / processor.STATUS_JSON_EXPORT_NAME).read_text(encoding="utf-8"))


def _sentence_count(text: str) -> int:
    return len([part for part in re.split(r"[.!?]+", text) if part.strip()])


def _assert_eliwinship_safe(text: str) -> None:
    assert _sentence_count(text) <= 3
    assert not re.search(r"(^|\s)(/[A-Za-z0-9_.-]+)+", text)
    assert not re.search(r"sha256:[0-9a-f]{16,}|\\b[0-9a-f]{32,}\\b", text.lower())
    forbidden = (
        "source_request_id",
        "operator_message",
        "raw_internal_status",
        "capital_hilton_invoice_operator_readback",
        "workflow_execution_package_compiler",
        "gated_email_send_adapter",
        "coupa_supplier_portal_package_compiler",
    )
    lowered = text.lower()
    for token in forbidden:
        assert token not in lowered


def _assert_cockpit_copy_safe(response: dict) -> None:
    assert len(response["headline"].split()) <= 6
    assert len(response["eliwinship"].split()) <= 40
    assert len(response["next_action"].split()) <= 12
    assert response["next_action"].startswith("Next: ")
    assert len(response["missing_items_short"]) <= 3
    for field in ("headline", "eliwinship", "next_action"):
        _assert_eliwinship_safe(response[field])


def _assert_spoken_packet_safe(packet: dict) -> None:
    script = packet["spoken_script"]
    assert script
    assert len(script.split()) <= 40
    assert not re.search(r"(^|\s)(/[A-Za-z0-9_.-]+)+", script)
    assert not re.search(r"sha256:[0-9a-f]{16,}|\b[0-9a-f]{32,}\b", script.lower())
    assert not re.search(r"(^|\s)[#*`>-]", script)
    forbidden_terms = (
        "source_request_id",
        "operator_message",
        "raw_internal_status",
        "capital_hilton_invoice_operator_readback",
        "gated_email_send_adapter",
        "coupa_supplier_portal_package_compiler",
    )
    lowered = script.lower()
    for term in forbidden_terms:
        assert term not in lowered
    assert packet["cloud_synthesis_allowed"] is False
    assert packet["local_playback_preferred"] is True
    assert packet["provider_policy"]["preferred_provider_family"] == "MAC_SYSTEM_TTS"
    assert packet["provider_policy"]["cloud_synthesis_allowed"] is False
    assert packet["provider_policy"]["cloud_transcription_allowed"] is False


def _assert_visual_package_safe(package: dict) -> None:
    text = json.dumps(package, sort_keys=True).lower()
    assert package
    assert package["provider_policy"]["cloud_generation_allowed"] is False
    assert package["provider_policy"]["local_asset_preferred"] is True
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)
    assert not re.search(r"sha256:[0-9a-f]{16,}|\b[0-9a-f]{32,}\b", text)
    assert not re.search(r"(^|\s)(/[A-Za-z0-9_.-]+)+", text)
    assert "actual secret" not in text
    assert "raw private body" not in text
    assert "credential value" not in text
    assert package["visual_event_type"] not in {"SUCCESS_CONFIRMED", "COMPLETION_CONFIRMED"}


def _assert_taste_guardrails_pass(response: dict) -> None:
    taste = response["taste_guardrails"]
    assert taste["taste_passed"] is True
    assert taste["field_limits_passed"] is True
    assert taste["machine_sludge_filtered"] is True
    assert taste["bad_phrase_blockers_passed"] is True
    assert taste["agent_voice_rules_passed"] is True
    assert taste["duplicate_sentence_reduction_passed"] is True
    assert not taste["taste_errors"]
    assert response["machine_proof"]["response_taste_guardrails_present"] is True
    assert response["machine_proof"]["response_taste_passed"] is True


def _minimal_response(message: str, *, request_type: str = "CHAT", workflow_ref: str = "workflow_fixture") -> processor.OpenClawResponseForMac:
    return processor.OpenClawResponseForMac(
        source_request_id="voice_selection_fixture",
        source_request_filename="mission_control_chat_request_voice_selection_fixture.json",
        workflow_ref=workflow_ref,
        request_type=request_type,
        internal_status="RESPONSE_READY",
        operator_headline=message.split(".", 1)[0],
        operator_message=message,
        what_happened=("Fixture response only.",),
        why_it_happened=message,
        how_to_fix="Use deterministic voice metadata only.",
        visible_cards=(),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None,
        detail_disclosure={},
        readback_files=(),
        next_safe_move="Review the voice metadata.",
    )


def test_newest_chat_request_is_selected(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    old_path = inbox / "mission_control_chat_request_old.json"
    new_path = inbox / "mission_control_chat_request_new.json"
    _write_chat_request(old_path)
    _write_chat_request(new_path)
    os.utime(old_path, (1, 1))
    os.utime(new_path, (2, 2))

    assert processor.select_newest_request(inbox) == new_path


def test_newest_file_request_is_selected(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    old_path = inbox / "mission_control_file_intake_request_old.json"
    new_path = inbox / "mission_control_file_intake_request_new.json"
    _write_file_request(old_path)
    _write_file_request(new_path, fixture="album")
    os.utime(old_path, (1, 1))
    os.utime(new_path, (2, 2))

    assert processor.select_newest_request(inbox) == new_path


def test_request_classifier_selects_chat_file_and_unknown():
    assert processor.classify_request_filename("mission_control_chat_request_001.json").request_family == "CHAT"
    assert processor.classify_request_filename("mission_control_file_intake_request_001.json").request_family == "FILE_METADATA"
    assert (
        processor.classify_request_filename("mission_control_context_request_001.json").request_family
        == "CONTEXT_ATTACHMENT_FUTURE"
    )
    assert processor.classify_request_filename("random.json").request_family == "UNKNOWN_FAIL_CLOSED"


def test_file_argument_processes_specific_chat_request(tmp_path, capsys):
    request_path = tmp_path / "mission_control_chat_request_capital_hilton.json"
    request = _write_chat_request(request_path)
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)
    status = _read_status(export_root)

    assert response["source_request_id"] == request["request_id"]
    assert response["request_type"] == "CHAT"
    assert response["internal_status"] == "RESPONSE_READY"
    assert response["operator_headline"] == "I found the PC readback"
    assert "Here's what OpenClaw understood" in response["operator_message"]
    assert response["response_kind"] == "CHAT_READBACK"
    assert response["response_author"] == "OPENCLAW_SYSTEM"
    assert response["voice_profile_ref"] == "voice:system:neutral"
    assert response["vibe_profile_ref"] == "vibe:system:neutral"
    assert response["voice_applied"] is True
    assert response["vibe_applied"] is True
    assert "spoken_response_packet" in response
    _assert_spoken_packet_safe(response["spoken_response_packet"])
    assert response["audience_mode"] == "ELIWINSHIP"
    assert response["display_mode"] == "COMPACT_CHAT"
    assert response["headline"]
    assert response["eliwinship"]
    assert "RESPONSE_READY" not in response["operator_headline"]
    assert "RESPONSE_READY" not in response["operator_message"]
    assert response["cards_available"] is True
    assert response["card_mirror_refs"]
    assert response["worker_route_refs"]
    assert response["context_package_refs"]
    assert status["processor_status"]["terminal_result"] == "RESPONSE_READY"
    assert status["processor_status"]["request_classification"]["request_family"] == "CHAT"


def test_file_argument_processes_specific_file_request(tmp_path, capsys):
    request_path = tmp_path / "mission_control_file_intake_request_spreadsheet.json"
    request = _write_file_request(request_path)
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["source_request_id"] == request["request_id"]
    assert response["request_type"] == "FILE_METADATA"
    assert response["internal_status"] == "RESPONSE_READY"
    assert response["operator_headline"] == "File reference captured"
    assert response["response_kind"] == "FILE_METADATA_READBACK"
    assert response["response_author"] == "OPENCLAW_SYSTEM"
    assert response["voice_profile_ref"] == "voice:system:neutral"
    assert response["vibe_profile_ref"] == "vibe:system:neutral"
    assert response["voice_selection_reason"] == "file intake / source reference status"
    assert response["headline"] == "File reference captured"
    assert response["eliwinship"] == (
        "OpenClaw captured the file reference. The body was not read. You can use it later as source context."
    )
    assert response["next_action"] == "Next: Choose how to use this source."
    spoken = response["spoken_response_packet"]
    _assert_spoken_packet_safe(spoken)
    assert spoken["response_author"] == "OPENCLAW_SYSTEM"
    assert spoken["voice_profile_ref"] == "voice:system:neutral"
    assert spoken["spoken_script"] == "File reference captured. The body was not read. Choose whether to use it as source context."
    assert spoken["provider_policy"]["preferred_provider_family"] == "MAC_SYSTEM_TTS"
    assert spoken["privacy_class"] in {"SOURCE_REFERENCE_METADATA", "CLIENT_PAYMENT_CONTEXT"}
    visual = response["visual_event_package"]
    _assert_visual_package_safe(visual)
    assert visual["visual_event_type"] == "FILE_REFERENCE_CAPTURED"
    assert visual["truth_state"] == "FILE_REFERENCE_CAPTURED"
    assert visual["metaphor_style"] == "source_object_into_folder"
    assert "file reference captured" in visual["allowed_visual_facts"]
    assert "file body not read" in visual["allowed_visual_facts"]
    assert "file analyzed" in visual["forbidden_visual_claims"]
    assert "file body read" in visual["forbidden_visual_claims"]
    assert visual["provider_policy"]["preferred_provider_family"] == "STATIC_VISUAL_CARD"
    _assert_taste_guardrails_pass(response)
    _assert_cockpit_copy_safe(response)
    assert "Capital Hilton invoice.xlsx" in response["operator_message"]
    assert "RESPONSE_READY" not in response["operator_message"]
    assert response["file_readback_refs"]


def test_capital_hilton_status_query_routes_to_unified_operator_readback(tmp_path, capsys):
    request_path = tmp_path / "mission_control_chat_request_capital_hilton_status.json"
    request = _write_capital_hilton_status_request(
        request_path,
        message="what's the Capital Hilton invoice status?",
    )
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)
    status = _read_status(export_root)

    assert response["source_request_id"] == request["request_id"]
    assert response["request_type"] == "CHAT"
    assert response["internal_status"] == "RESPONSE_READY"
    assert response["operator_headline"] == "Capital Hilton invoice workflow is not ready yet"
    assert response["response_author"] == "CHIEF"
    assert response["voice_profile_ref"] == "voice:chief:operational"
    assert response["vibe_profile_ref"] == "vibe:chief:command_center"
    assert response["voice_applied"] is True
    assert response["vibe_applied"] is True
    assert response["voice_selection_reason"] == "finance workflow status / readiness / blocker summary"
    assert response["high_risk_override_applied"] is False
    assert response["headline"] == "Capital Hilton invoice is blocked"
    assert response["response_kind"] == "CAPITAL_HILTON_INVOICE_STATUS"
    assert response["audience_mode"] == "ELIWINSHIP"
    assert response["display_mode"] == "COMPACT_CHAT"
    assert response["mac_render_hint"] == "COMPACT_WITH_DISCLOSURE"
    assert response["one_line_answer"] == (
        "OpenClaw has the delivery basis, but the workflow is locked because required approvals and proofs are missing."
    )
    assert response["eliwinship"] == (
        "The invoice basis and draft rails exist. "
        "The workflow is blocked until the Coupa PO/reference and approval receipts are confirmed. "
        "Nothing can send or submit yet."
    )
    _assert_eliwinship_safe(response["eliwinship"])
    assert response["primary_status"] == "Locked until proof and approval receipts exist"
    assert response["primary_blocker"] == "Missing confirmed Coupa PO/reference"
    assert response["next_action"] == "Next: Confirm the Coupa PO/reference."
    assert isinstance(response["missing_items_short"], list)
    assert response["missing_items_short"] == [
        "Confirmed Coupa PO/reference",
        "Guardian and operator approval receipts",
        "Email send receipt and attachment proof",
    ]
    spoken = response["spoken_response_packet"]
    _assert_spoken_packet_safe(spoken)
    assert spoken["response_author"] == "CHIEF"
    assert spoken["voice_profile_ref"] == "voice:chief:operational"
    assert spoken["vibe_profile_ref"] == "vibe:chief:command_center"
    assert spoken["spoken_script"] == (
        "Capital Hilton invoice is blocked. The invoice basis exists, but the Coupa PO reference and approval receipts are still missing. Nothing can send or submit yet."
    )
    assert spoken["spoken_summary"] == "Invoice blocked. Confirm the Coupa PO reference."
    assert spoken["voice_direction"] == "operational_crisp"
    assert spoken["pronunciation_hints"]["Coupa"] == "coo pah"
    assert spoken["provider_policy"]["sensitive_context"] is True
    assert spoken["provider_policy"]["preferred_provider_family"] == "MAC_SYSTEM_TTS"
    assert spoken["cloud_synthesis_allowed"] is False
    assert spoken["privacy_class"] == "CLIENT_PAYMENT_CONTEXT"
    assert "sent" not in spoken["spoken_script"].lower()
    assert "submitted" not in spoken["spoken_script"].lower()
    assert "complete" not in spoken["spoken_script"].lower()
    visual = response["visual_event_package"]
    _assert_visual_package_safe(visual)
    assert visual["visual_event_type"] == "BLOCKED_MISSING_INPUT"
    assert visual["truth_state"] == "BLOCKED_MISSING_INPUT"
    assert visual["metaphor_style"] == "bowling_single_pin_left"
    assert "invoice basis exists" in visual["allowed_visual_facts"]
    assert "Coupa PO/reference missing" in visual["allowed_visual_facts"]
    assert "invoice sent" in visual["forbidden_visual_claims"]
    assert "Coupa invoice submitted" in visual["forbidden_visual_claims"]
    assert "payment updated" in visual["forbidden_visual_claims"]
    assert "approval complete" in visual["forbidden_visual_claims"]
    assert visual["provider_policy"]["preferred_provider_family"] == "MAC_ANIMATION_NATIVE"
    assert visual["provider_policy"]["cloud_generation_allowed"] is False
    assert visual["provider_policy"]["local_asset_preferred"] is True
    _assert_taste_guardrails_pass(response)
    _assert_cockpit_copy_safe(response)
    assert "four Capital Hilton performance dates at $1,600 total" in response["detail_summary"]
    assert response["proof_refs"]
    assert all(ref.startswith("generated/read_models/") for ref in response["proof_refs"])
    assert all("/tmp/" not in ref for ref in response["proof_refs"])
    assert response["raw_internal_status"] == response["internal_status"]
    assert "Capital Hilton invoice is not ready" in response["operator_message"]
    assert "Nothing has been sent, submitted, opened, approved, or marked complete" in response["operator_message"]
    assert "RESPONSE_READY" not in response["operator_message"]
    assert response["detail_disclosure"]["selected_readback_ref"].endswith("capital_hilton_invoice_operator_readback.json")
    assert response["detail_disclosure"]["can_mark_invoice_sent"] is False
    assert any(path.endswith("capital_hilton_invoice_operator_readback.json") for path in response["readback_files"])
    assert status["processor_status"]["selected_rail"] == "capital_hilton_invoice_operator_readback"


def test_capital_hilton_mark_invoice_sent_question_returns_false_without_proof(tmp_path, capsys):
    request_path = tmp_path / "mission_control_chat_request_capital_hilton_sent_status.json"
    _write_capital_hilton_status_request(
        request_path,
        message="can we mark invoice sent?",
    )
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["operator_headline"] == "Capital Hilton invoice workflow is not ready yet"
    assert response["headline"] == "Capital Hilton invoice is blocked"
    assert response["response_author"] == "CHIEF"
    assert response["detail_disclosure"]["can_mark_invoice_sent"] is False
    assert response["primary_blocker"] == "Missing confirmed Coupa PO/reference"
    assert response["visual_event_package"]["visual_event_type"] == "BLOCKED_MISSING_INPUT"
    assert response["visual_event_package"]["metaphor_style"] != "perfect_game_sweep"
    assert response["machine_proof"]["visual_false_success_claim_blocked"] is True
    assert "approval receipts" in response["how_to_fix"]
    assert "INVOICE SENT" not in response["operator_headline"]
    assert response["machine_proof"]["external_action_performed"] is False


def test_voice_selection_fixtures_cover_cassandra_guardian_and_niles_override():
    cassandra = _minimal_response("The draft is ready for review, but I do not have send authority.")
    cassandra_layered = processor._layered_response_fields(cassandra, created_at=FIXED_NOW)
    cassandra_voice = processor._voice_authorship_fields(cassandra, cassandra_layered)

    guardian = _minimal_response("Blocked. This action needs a specific approval packet and proof refs before it can proceed.")
    guardian_layered = processor._layered_response_fields(guardian, created_at=FIXED_NOW)
    guardian_voice = processor._voice_authorship_fields(guardian, guardian_layered)

    niles_risky = _minimal_response("Niles, help with the X32 show file and use the secret to submit the payment action.")
    niles_layered = processor._layered_response_fields(niles_risky, created_at=FIXED_NOW)
    niles_voice = processor._voice_authorship_fields(niles_risky, niles_layered)

    codex = _minimal_response("Build lane passed locally. Tests passed. No push occurred.")
    codex_layered = processor._layered_response_fields(codex, created_at=FIXED_NOW)
    codex_voice = processor._voice_authorship_fields(codex, codex_layered)

    hermes = _minimal_response("Hermes audit ready.")
    hermes_layered = processor._layered_response_fields(hermes, created_at=FIXED_NOW)
    hermes_voice = processor._voice_authorship_fields(hermes, hermes_layered)

    assert cassandra_voice["response_author"] == "CASSANDRA"
    assert cassandra_voice["selected_model_backend"] == "GPT"
    assert cassandra_voice["voice_profile_ref"] == "voice:cassandra:communications"
    assert cassandra_voice["high_risk_override_applied"] is False
    assert guardian_voice["response_author"] == "GUARDIAN"
    assert guardian_voice["selected_model_backend"] == "LOCAL_OLLAMA"
    assert guardian_voice["voice_profile_ref"] == "voice:guardian:proof_gate"
    assert niles_voice["response_author"] == "GUARDIAN"
    assert niles_voice["vibe_profile_ref"] == "vibe:guardian:strict_proof"
    assert niles_voice["high_risk_override_applied"] is True
    assert codex_voice["response_author"] == "CHIEF"
    assert codex_voice["selected_model_backend"] == "CODEX"
    assert codex_voice["selected_worker_type"] == "PC_CODEX"
    assert "Chief remains the agent" in codex_voice["model_selection_reason"]
    assert hermes_voice["response_author"] == "HERMES"
    assert hermes_voice["voice_profile_ref"] == "voice:hermes:audit"
    assert hermes_voice["selected_model_backend"] == "GEMINI_AGY"


def test_response_taste_bad_phrase_fixtures_are_marked_invalid():
    bad_payload = {
        "headline": "Looks ready to send",
        "one_line_answer": "This is basically sent.",
        "eliwinship": "Don't worry about the gate. I fixed it.",
        "primary_status": "RESPONSE_READY",
        "primary_blocker": "None",
        "next_action": "Next: Deployed.",
        "response_author": "CHIEF",
        "spoken_response_packet": {"spoken_script": "It is 100% correct and flawless."},
        "high_risk_override_applied": False,
    }
    taste = processor._response_taste_guardrails(bad_payload)

    assert taste["taste_passed"] is False
    assert "ready to send" in taste["bad_phrase_blockers"]
    assert "basically sent" in taste["bad_phrase_blockers"]
    assert "deployed" in taste["bad_phrase_blockers"]
    assert "100% correct" in taste["bad_phrase_blockers"]
    assert any(error.startswith("BAD_PHRASE:") for error in taste["taste_errors"])
    assert any(error.startswith("INTERNAL_STATUS:") for error in taste["taste_errors"])


def test_agent_specific_taste_rules_cover_cassandra_guardian_hermes_and_chief():
    cassandra = _minimal_response("Cassandra draft review is ready. Send authority remains locked.")
    cassandra_payload, _ = processor.build_payloads(cassandra, generated_at=FIXED_NOW)
    assert cassandra_payload["response_author"] == "CASSANDRA"
    _assert_taste_guardrails_pass(cassandra_payload)
    cassandra_bad = dict(cassandra_payload)
    cassandra_bad["eliwinship"] = "I sent it to Annette."
    cassandra_taste = processor._response_taste_guardrails(cassandra_bad)
    assert cassandra_taste["taste_passed"] is False
    assert any(error.startswith("CASSANDRA_FORBIDDEN:") for error in cassandra_taste["taste_errors"])

    guardian = _minimal_response("Blocked. This action needs a specific approval packet and proof refs before it can proceed.")
    guardian_payload, _ = processor.build_payloads(guardian, generated_at=FIXED_NOW)
    assert guardian_payload["response_author"] == "GUARDIAN"
    _assert_taste_guardrails_pass(guardian_payload)
    guardian_bad = dict(guardian_payload)
    guardian_bad["eliwinship"] = "Panic. This is a catastrophe."
    guardian_taste = processor._response_taste_guardrails(guardian_bad)
    assert any(error.startswith("GUARDIAN_FORBIDDEN:") for error in guardian_taste["taste_errors"])

    codex = _minimal_response("Build lane passed locally. Tests passed. No push occurred.")
    codex_payload, _ = processor.build_payloads(codex, generated_at=FIXED_NOW)
    assert codex_payload["response_author"] == "CHIEF"
    assert codex_payload["agent_role"] == "CHIEF"
    assert codex_payload["selected_model_backend"] == "CODEX"
    assert codex_payload["selected_worker_type"] == "PC_CODEX"
    _assert_taste_guardrails_pass(codex_payload)
    codex_bad = dict(codex_payload)
    codex_bad["eliwinship"] = "Deployed."
    codex_taste = processor._response_taste_guardrails(codex_bad)
    assert "deployed" in codex_taste["bad_phrase_blockers"]

    hermes = _minimal_response("Hermes audit ready.")
    hermes_payload, _ = processor.build_payloads(hermes, generated_at=FIXED_NOW)
    assert hermes_payload["response_author"] == "HERMES"
    assert hermes_payload["selected_model_backend"] == "GEMINI_AGY"
    _assert_taste_guardrails_pass(hermes_payload)
    hermes_bad = dict(hermes_payload)
    hermes_bad["eliwinship"] = "I approved the architecture and replace Guardian."
    hermes_taste = processor._response_taste_guardrails(hermes_bad)
    assert any(error.startswith("HERMES_FORBIDDEN:") for error in hermes_taste["taste_errors"])

    chief = _minimal_response("Capital Hilton is blocked by missing approval receipts.", workflow_ref="capital_hilton_invoice_workflow")
    chief_payload, _ = processor.build_payloads(chief, generated_at=FIXED_NOW)
    chief_bad = dict(chief_payload)
    chief_bad["response_author"] = "CHIEF"
    chief_bad["eliwinship"] = "You got this, this is awesome."
    chief_taste = processor._response_taste_guardrails(chief_bad)
    assert any(error.startswith("CHIEF_FORBIDDEN:") for error in chief_taste["taste_errors"])


def test_file_argument_accepts_mac_metadata_hash_contract(tmp_path, capsys):
    request_path = tmp_path / "mission_control_file_intake_request_1779734559852_99bd5e3900cf.json"
    request = file_intake.make_fixture_request("spreadsheet", created_at=FIXED_NOW)
    mac_hash = "99bd5e3900cfa89068e5c26aeeb6ea7b7b1164d1a62949c77f2ee3399de149d2"
    request.update(
        {
            "request_id": f"capital_hilton_file_metadata_1779734559852_{mac_hash[:12]}",
            "idempotency_key": f"mission_control_file_metadata:{request['workflow_ref']}:1779734559852:{mac_hash[:20]}",
            "payload_hash": mac_hash,
        }
    )
    request_path.write_text(file_intake.stable_json(request), encoding="utf-8")
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["source_request_id"] == request["request_id"]
    assert response["request_type"] == "FILE_METADATA"
    assert response["internal_status"] == "RESPONSE_READY"
    assert response["operator_headline"] == "File reference captured"
    assert response["blocked_reason"] is None


def test_future_context_request_is_blocked_with_missing_rail(tmp_path, capsys):
    request_path = tmp_path / "mission_control_context_request_build.json"
    request = _write_future_request(request_path)
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["source_request_id"] == request["request_id"]
    assert response["request_type"] == "CONTEXT_ATTACHMENT_FUTURE"
    assert response["internal_status"] == "BLOCKED_WITH_REASON"
    assert "rail" in response["operator_message"]
    assert "Missing rail" in response["blocked_reason"]
    assert "add the specific deterministic adapter" in response["how_to_fix"]


def test_malformed_json_fails_with_operator_message_and_how_to_fix(tmp_path, capsys):
    request_path = tmp_path / "mission_control_chat_request_malformed.json"
    request_path.write_text("{not json", encoding="utf-8")
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["internal_status"] == "FAILED_WITH_REASON"
    assert response["operator_headline"] == "OpenClaw could not process the request"
    assert "Malformed JSON" in response["why_it_happened"]
    assert "Regenerate the request" in response["how_to_fix"]
    assert "FAILED_WITH_REASON" not in response["operator_message"]


def test_missing_required_field_fails_with_how_to_fix(tmp_path, capsys):
    request_path = tmp_path / "mission_control_chat_request_missing_workflow.json"
    request = chat_intake.make_capital_hilton_fixture_request(created_at=FIXED_NOW)
    del request["workflow_ref"]
    request["payload_hash"] = chat_intake.compute_request_payload_hash(request)
    request_path.write_text(chat_intake.stable_json(request), encoding="utf-8")
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["internal_status"] == "BLOCKED_WITH_REASON"
    assert "Missing required field" in response["why_it_happened"]
    assert "Regenerate or resend" in response["how_to_fix"]
    assert "BLOCKED_WITH_REASON" not in response["operator_message"]


def test_missing_idempotency_fails_with_how_to_fix(tmp_path, capsys):
    request_path = tmp_path / "mission_control_chat_request_missing_idempotency.json"
    request = chat_intake.make_capital_hilton_fixture_request(created_at=FIXED_NOW)
    request["idempotency_key"] = ""
    request["payload_hash"] = chat_intake.compute_request_payload_hash(request)
    request_path.write_text(chat_intake.stable_json(request), encoding="utf-8")
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["internal_status"] == "BLOCKED_WITH_REASON"
    assert "Missing idempotency key" in response["why_it_happened"]
    assert "idempotency_key" in response["how_to_fix"]


def test_missing_request_yields_operator_message(tmp_path, capsys):
    inbox = tmp_path / "empty_inbox"
    inbox.mkdir()
    export_root = tmp_path / "read_models"

    assert process_main(["--once", "--inbox", str(inbox), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["internal_status"] == "NO_REQUEST_AVAILABLE"
    assert response["operator_headline"] == "No Mac request is waiting"
    assert "did not find a supported Mac chat or file request" in response["operator_message"]
    assert "Send a new message" in response["how_to_fix"]
    assert "NO_REQUEST_AVAILABLE" not in response["operator_message"]


def test_watch_seconds_times_out_with_how_to_fix(tmp_path, capsys):
    inbox = tmp_path / "empty_inbox"
    inbox.mkdir()
    export_root = tmp_path / "read_models"

    assert process_main(["--watch-seconds", "0", "--inbox", str(inbox), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["internal_status"] == "TIMED_OUT_WITH_REASON"
    assert "waited 0 second" in response["operator_message"].lower()
    assert "run with --file" in response["how_to_fix"]


def test_request_id_argument_processes_matching_request(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    request_path = inbox / "mission_control_file_intake_request_spreadsheet.json"
    request = _write_file_request(request_path)
    export_root = tmp_path / "read_models"

    assert process_main(
        [
            "--request-id",
            request["request_id"],
            "--inbox",
            str(inbox),
            "--export-root",
            str(export_root),
            "--generated-at",
            FIXED_NOW,
            "--format",
            "json",
        ]
    ) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["source_request_id"] == request["request_id"]
    assert response["source_request_filename"] == request_path.name
    assert response["operator_headline"] == "File reference captured"


def test_duplicate_noop_includes_existing_readback(tmp_path, capsys):
    request_path = tmp_path / "mission_control_file_intake_request_spreadsheet.json"
    _write_file_request(request_path)
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    capsys.readouterr()
    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["internal_status"] == "DUPLICATE_NOOP_WITH_READBACK"
    assert "already processed this request" in response["operator_message"]
    assert "existing readback" in response["operator_message"]
    assert response["readback_files"]
    assert "DUPLICATE_NOOP_WITH_READBACK" not in response["operator_message"]


def test_blocked_existing_status_is_reprocessed_after_local_fix(tmp_path, capsys):
    request_path = tmp_path / "mission_control_file_intake_request_1779734559852_99bd5e3900cf.json"
    request = file_intake.make_fixture_request("spreadsheet", created_at=FIXED_NOW)
    mac_hash = "99bd5e3900cfa89068e5c26aeeb6ea7b7b1164d1a62949c77f2ee3399de149d2"
    request.update(
        {
            "request_id": f"capital_hilton_file_metadata_1779734559852_{mac_hash[:12]}",
            "idempotency_key": f"mission_control_file_metadata:{request['workflow_ref']}:1779734559852:{mac_hash[:20]}",
            "payload_hash": mac_hash,
        }
    )
    request_path.write_text(file_intake.stable_json(request), encoding="utf-8")
    export_root = tmp_path / "read_models"
    export_root.mkdir()
    (export_root / processor.STATUS_JSON_EXPORT_NAME).write_text(
        json.dumps(
            {
                "processor_status": {
                    "latest_processed_request": {
                        "source_request_id": request["request_id"],
                        "source_request_filename": request_path.name,
                        "workflow_ref": request["workflow_ref"],
                        "request_type": "FILE_METADATA",
                    },
                    "terminal_result": "BLOCKED_WITH_REASON",
                }
            }
        ),
        encoding="utf-8",
    )

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["internal_status"] == "RESPONSE_READY"
    assert response["operator_headline"] == "File reference captured"
    assert response["blocked_reason"] is None


def test_blocked_file_raw_body_has_why_and_how_to_fix(tmp_path, capsys):
    request_path = tmp_path / "mission_control_file_intake_request_raw_body.json"
    _write_file_request(request_path, fixture="raw_body")
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["internal_status"] == "BLOCKED_WITH_REASON"
    assert "raw body content" in response["why_it_happened"].lower()
    assert "metadata-only" in response["how_to_fix"]
    assert response["operator_message"]


def test_processor_does_not_delete_request_or_broad_scan(tmp_path, capsys):
    request_path = tmp_path / "mission_control_file_intake_request_spreadsheet.json"
    _write_file_request(request_path)
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert request_path.exists()
    assert response["machine_proof"]["approved_inbox_only_scanned"] is True
    assert response["machine_proof"]["broad_scan_performed"] is False
    assert response["machine_proof"]["request_deleted_or_mutated"] is False
    assert response["machine_proof"]["infinite_loop_possible"] is False


def test_responder_targets_are_modeled_without_fake_lm_calls(tmp_path, capsys):
    request_path = tmp_path / "mission_control_chat_request_capital_hilton.json"
    _write_chat_request(request_path)
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)
    status = _read_status(export_root)
    targets = status["processor_status"]["responder_targets"]

    assert response["machine_proof"]["deterministic_responder_targets_modeled"] is True
    assert response["machine_proof"]["future_lm_targets_modeled"] is True
    assert response["machine_proof"]["future_lm_targets_not_called"] is True
    assert any(target["target_type"] == "CODEX_RESPONDER_FUTURE" for target in targets)
    for target in targets:
        if target["target_type"].endswith("_FUTURE"):
            assert target["adapter_available"] is False
            assert target["live_call_allowed"] is False


def test_all_external_authority_false_and_no_raw_body_ingestion(tmp_path, capsys):
    request_path = tmp_path / "mission_control_chat_request_capital_hilton.json"
    _write_chat_request(request_path)
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["machine_proof"]["all_live_authority_flags_false"] is True
    assert response["machine_proof"]["workflow_execution_performed"] is False
    assert response["machine_proof"]["model_call_performed"] is False
    assert response["machine_proof"]["tool_execution_performed"] is False
    assert response["machine_proof"]["external_action_performed"] is False
    assert response["machine_proof"]["credential_handling_performed"] is False
    assert response["machine_proof"]["raw_body_ingestion_performed"] is False
    for key, value in response["authority_boundary"].items():
        assert value is False, key


def test_status_and_response_json_are_parseable_and_correlated(tmp_path, capsys):
    request_path = tmp_path / "mission_control_chat_request_capital_hilton.json"
    request = _write_chat_request(request_path)
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    response = _read_response(export_root)
    status = _read_status(export_root)

    assert summary["source_request_id"] == request["request_id"]
    assert response["source_request_id"] == request["request_id"]
    assert status["processor_status"]["latest_processed_request"]["source_request_id"] == request["request_id"]
    assert status["processor_status"]["request_classification"]["request_family"] == "CHAT"
    assert status["processor_status"]["operator_message"] == response["operator_message"]
    assert status["processor_status"]["how_to_fix"] == response["how_to_fix"]
    assert status["machine_proof"]["terminal_quality_passed"] is True
    assert response["machine_proof"]["terminal_quality_passed"] is True


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "openclaw_request_processor.py",
            "scripts/process_openclaw_requests.py",
        ]
    )
    forbidden = [
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "subprocess.",
        "os.system",
        "smtplib",
        "selenium",
        "playwright",
        "send_message",
        "shell=true",
        "eval(",
    ]
    for token in forbidden:
        assert token not in source
