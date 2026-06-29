from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import maestro_listener


def test_image_attachment_request_carries_hash_and_real_ocr_text(tmp_path: Path) -> None:
    if not maestro_listener._which("tesseract") or not maestro_listener._which("text2image"):
        pytest.skip("tesseract/text2image not installed")
    text_fixture = tmp_path / "check.txt"
    text_fixture.write_text("Reynolds Tavern\nAmount 500 dollars\n", encoding="utf-8")
    image = tmp_path / "check.png"
    subprocess.run(
        [
            "text2image",
            f"--text={text_fixture}",
            f"--outputbase={tmp_path / 'check'}",
            "--font=DejaVu Sans",
            "--fonts_dir=/usr/share/fonts/truetype/dejavu",
            "--ptsize=24",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    generated = tmp_path / "check.tif"
    assert generated.exists()

    request = maestro_listener.build_operator_maestro_image_request(
        generated,
        caption="Reynolds Tavern check",
        message_id="photo_1",
        chat_id=123,
        mime_type="image/tiff",
    )

    assert request["request_type"] == "WORKFLOW_PACKAGE_REQUEST_V0"
    assert request["image_input_received"] is True
    assert request["image_ocr"]["method"] == "tesseract"
    assert request["image_ocr"]["ok"] is True
    assert "Reynolds Tavern" in request["operator_message"]
    assert "Amount" in request["source_text"]
    assert request["attachments"][0]["sha256"]
    assert request["attachments"][0]["local_path"] == str(generated)
    assert request["attachments"][0]["mime"] == "image/tiff"
    assert request["attachments"][0]["caption"] == "Reynolds Tavern check"
    assert request["raw_image_body_shared_with_model"] is False
    assert request["authority_boundary"]["live_attachment_allowed"] is False


def test_image_ocr_failure_writes_deferred_marker(tmp_path: Path) -> None:
    image = tmp_path / "unreadable.jpg"
    image.write_bytes(b"not an image")
    marker_dir = tmp_path / "pending_vision"

    request = maestro_listener.build_operator_maestro_image_request(
        image,
        caption="Unreadable check",
        message_id="photo_2",
        chat_id=123,
        mime_type="image/jpeg",
        ocr_fn=lambda path: {"ok": False, "error": "tesseract missing"},
        deferred_marker_dir=marker_dir,
    )

    marker_path = Path(request["deferred_marker_path"])
    marker = maestro_listener._read_json_file(marker_path)
    assert request["image_deferred_for_reprocess"] is True
    assert "reprocess when vision's back" in request["operator_reply"]
    assert marker_path.exists()
    assert marker["status"] == "pending_vision_reprocess"
    assert marker["sha256"] == maestro_listener._sha256_file(image)
    assert marker["raw_image_body_shared_with_model"] is False


def test_deferred_image_drain_resolves_marker_and_writes_bridge_request(tmp_path: Path) -> None:
    image = tmp_path / "later.jpg"
    image.write_bytes(b"image bytes")
    marker_dir = tmp_path / "pending_vision"
    written: list[dict] = []

    deferred = maestro_listener.build_operator_maestro_image_request(
        image,
        caption="Later check",
        message_id="photo_3",
        chat_id=123,
        mime_type="image/jpeg",
        ocr_fn=lambda path: {"ok": True, "text": "", "confidence": "low"},
        deferred_marker_dir=marker_dir,
    )

    result = maestro_listener.drain_deferred_image_markers(
        marker_dir=marker_dir,
        ocr_fn=lambda path: {"ok": True, "text": "Later Check Amount 500", "confidence": "normal"},
        write_request_fn=lambda request: written.append(request) or (tmp_path / "request.json"),
    )

    marker = maestro_listener._read_json_file(Path(deferred["deferred_marker_path"]))
    assert result["resolved"] == 1
    assert written[0]["request_type"] == "WORKFLOW_PACKAGE_REQUEST_V0"
    assert "Later Check Amount 500" in written[0]["operator_message"]
    assert marker["status"] == "resolved"
    assert marker["resolved_request_id"] == written[0]["request_id"]


def test_image_request_can_target_non_maestro_agent(tmp_path: Path) -> None:
    image = tmp_path / "agent.jpg"
    image.write_bytes(b"image bytes")

    request = maestro_listener.build_operator_image_request(
        image,
        agent="cassandra",
        caption="Cassandra image",
        message_id="photo_4",
        chat_id=123,
        mime_type="image/jpeg",
        ocr_fn=lambda path: {"ok": True, "text": "Cassandra OCR text", "confidence": "normal"},
    )

    assert request["expected_response_provenance"]["actor"] == "cassandra"
    assert request["lane"] == "telegram_pc_cassandra_listener"
    assert request["request_id"].startswith("cassandra_telegram_")
