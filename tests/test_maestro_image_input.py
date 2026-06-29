from __future__ import annotations

from pathlib import Path

import maestro_listener


def test_image_attachment_request_carries_hash_and_ocr_text(tmp_path: Path) -> None:
    image = tmp_path / "check.png"
    image.write_bytes(b"fake image bytes")

    request = maestro_listener.build_operator_maestro_image_request(
        image,
        caption="Reynolds Tavern check",
        message_id="photo_1",
        chat_id=123,
        mime_type="image/png",
        ocr_fn=lambda path: {
            "ok": True,
            "text": "Reynolds Tavern\nAmount $500.00\nDate 2026-06-27",
            "confidence": "normal",
        },
    )

    assert request["request_type"] == "WORKFLOW_PACKAGE_REQUEST_V0"
    assert request["image_input_received"] is True
    assert request["image_ocr"]["method"] == "tesseract"
    assert request["image_ocr"]["ok"] is True
    assert "Reynolds Tavern" in request["operator_message"]
    assert "Amount $500.00" in request["source_text"]
    assert request["attachments"][0]["sha256"]
    assert request["attachments"][0]["local_path"] == str(image)
    assert request["attachments"][0]["mime"] == "image/png"
    assert request["attachments"][0]["caption"] == "Reynolds Tavern check"
    assert request["raw_image_body_shared_with_model"] is False
    assert request["authority_boundary"]["live_attachment_allowed"] is False
