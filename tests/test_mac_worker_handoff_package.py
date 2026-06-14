import json
from pathlib import Path

import mac_worker_handoff_package as handoff


FIXED_NOW = "2026-05-25T18:30:00+00:00"


def _request(request_id: str, message: str, **extra):
    payload = {
        "request_id": request_id,
        "workflow_ref": "mac_worker_handoff_fixture",
        "world_ref": "openclaw",
        "lane_ref": "mac_worker_handoff_v0",
        "operator_message": message,
        "sanitized_message_summary": message,
        "authority_boundary": dict(handoff.AUTHORITY_BOUNDARY),
    }
    payload.update(extra)
    return payload


def test_models_and_export_read_model_exist(tmp_path):
    payload = handoff.build_read_model(generated_at=FIXED_NOW)
    json_path, operator_path = handoff.write_exports(payload, tmp_path)

    assert "handoff_id" in payload["mac_worker_handoff_package_model_fields"]
    assert "blocker_type" in payload["mac_worker_handoff_blocker_model_fields"]
    assert payload["handoff_output_path"] == "/mnt/e/openclaw/mission_control_handoffs/to_mac"
    assert payload["mac_visible_path"] == "/Volumes/openclaw_e/mission_control_handoffs/to_mac"
    assert json.loads(json_path.read_text(encoding="utf-8"))["read_model_id"] == handoff.READ_MODEL_ID
    assert "PC-to-Mac Worker Handoff Package" in operator_path.read_text(encoding="utf-8")
    assert payload["machine_proof"]["all_live_authority_false"] is True


def test_mac_ui_fixture_writes_bounded_handoff_package(tmp_path):
    request = _request("mac_ui_fixture", "Make the chat response look better on Mac.")
    payload = handoff.build_handoff_payload_from_request(
        request,
        source_request_filename="mission_control_chat_request_mac_ui.json",
        created_at=FIXED_NOW,
    )
    output_path = handoff.write_handoff_package(payload, tmp_path)
    written = json.loads(output_path.read_text(encoding="utf-8"))
    package = written["handoff_package"]

    assert output_path == tmp_path / "mac_worker_handoff_mac_ui_fixture.json"
    assert package["requested_worker"] == "MAC_CODEX"
    assert package["target_surface"] == "mission_control_mac_app"
    assert package["response_expected"] is True
    assert "xcodebuild build" in package["validation_expectations"]
    assert "focused app tests" in package["validation_expectations"]
    assert "screenshot if UI-visible" in package["validation_expectations"]
    assert all(value is False for value in package["authority_boundary"].values())
    assert written["terminal"] is False


def test_xcode_build_and_visual_workspace_examples_are_packages():
    xcode_payload = handoff.build_handoff_payload_from_request(
        _request("xcode_fixture", "Check if the Mac app builds."),
        source_request_filename="mission_control_chat_request_xcode.json",
        created_at=FIXED_NOW,
    )
    visual_payload = handoff.build_handoff_payload_from_request(
        _request("visual_fixture", "Show me the invoice workspace visually."),
        source_request_filename="mission_control_chat_request_visual.json",
        created_at=FIXED_NOW,
    )

    assert xcode_payload["handoff_package"]["requested_worker"] == "MAC_XCODE_BUILD"
    assert xcode_payload["handoff_package"]["target_surface"] == "xcode"
    assert "xcodebuild build" in xcode_payload["handoff_package"]["validation_expectations"]
    assert visual_payload["handoff_package"]["requested_worker"] == "MAC_VISUAL_WORKSPACE"
    assert visual_payload["handoff_package"]["target_surface"] == "mac_visual_workspace"
    assert "source refs only" in visual_payload["handoff_package"]["validation_expectations"]


def test_mail_send_request_blocks_without_handoff_package():
    payload = handoff.build_handoff_payload_from_request(
        _request("mail_send_fixture", "Open Mail and send the invoice."),
        source_request_filename="mission_control_chat_request_mail_send.json",
        created_at=FIXED_NOW,
    )
    blocker_types = {blocker["blocker_type"] for blocker in payload["blockers"]}

    assert payload["handoff_package"] is None
    assert {"APP_AUTOMATION_REQUESTED", "EXTERNAL_ACTION_REQUESTED"}.issubset(blocker_types)
    assert all(blocker["fail_closed"] is True for blocker in payload["blockers"])


def test_unknown_mac_worker_blocks_fail_closed():
    payload = handoff.build_handoff_payload_from_request(
        _request("unknown_fixture", "Do the thing on the other side."),
        source_request_filename="mission_control_chat_request_unknown.json",
        created_at=FIXED_NOW,
    )
    blocker_types = {blocker["blocker_type"] for blocker in payload["blockers"]}

    assert payload["handoff_package"] is None
    assert "UNKNOWN_MAC_WORKER" in blocker_types
    assert "MISSING_TARGET_SURFACE" in blocker_types


def test_audio_playback_handoff_uses_spoken_packet_ref_only():
    payload = handoff.build_handoff_payload_from_request(
        _request(
            "audio_fixture",
            "Read this response aloud.",
            spoken_response_packet_ref="spoken_response_packet_ref:latest",
        ),
        source_request_filename="mission_control_chat_request_audio.json",
        created_at=FIXED_NOW,
    )
    package = payload["handoff_package"]

    assert package["requested_worker"] == "MAC_AUDIO_PLAYBACK"
    assert package["target_surface"] == "mac_chat"
    assert "native Mac playback only" in package["validation_expectations"]
    assert "no microphone" in package["validation_expectations"]
    assert "no cloud synthesis/transcription" in package["validation_expectations"]
    assert "spoken_response_packet_ref:latest" in package["source_refs"]
    assert package["authority_boundary"]["live_speech_synthesis_allowed"] is False


def test_raw_private_body_and_credentials_block():
    payload = handoff.build_handoff_payload_from_request(
        _request(
            "unsafe_fixture",
            "Check the Mac app layout.",
            raw_body="private body should never be packaged",
            password="not allowed",
        ),
        source_request_filename="mission_control_chat_request_unsafe.json",
        created_at=FIXED_NOW,
    )
    blocker_types = {blocker["blocker_type"] for blocker in payload["blockers"]}

    assert payload["handoff_package"] is None
    assert "RAW_PRIVATE_BODY_INCLUDED" in blocker_types
    assert "CREDENTIAL_INCLUDED" in blocker_types
    assert payload["machine_proof"]["raw_body_ingestion_performed"] is False
    assert payload["machine_proof"]["credential_handling_performed"] is False
