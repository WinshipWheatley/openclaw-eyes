from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legal.alternative_methods import alternative_methods_for_matter
from legal.local_ingestion import extract_source_text
from legal.matter_workspace import create_matter_workspace, register_source
from scripts.demo_legal_mock_discovery import _write_no_text_pdf


def _item_by_status(packet: dict, status: str) -> dict:
    return next(item for item in packet["items"] if item["status"] == status)


def test_unsupported_fake_extension_gets_alternative_methods(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "client-secret-export.weird"
    source.write_bytes(b"synthetic unsupported content")
    create_matter_workspace(root, "matter", "Private Matter")
    registered = register_source(root, source)
    extract_source_text(root, registered["source_id"])

    packet = alternative_methods_for_matter(root)

    assert packet["artifact_type"] == "alternative_methods_v0"
    assert packet["source_count"] == 1
    assert packet["needs_alternative_methods"] == 1
    item = _item_by_status(packet, "unsupported")
    assert item["file_extension"] == ".weird"
    assert item["reason_category"] == "unsupported_file_type"
    assert item["local_capability_state"] == "local_capability_not_attempted"
    assert item["local_capability_kind"] == "unknown_local_handler"
    assert item["request_feature_state"] == "locked"
    assert "try_local_capability" in item["available_actions"]
    assert item["locked_actions"] == ["request_feature"]


def test_failed_pdf_gets_alternative_methods(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)
    with patch(
        "legal.local_ingestion._pdf_to_text",
        return_value={"ok": False, "error": "synthetic pdf failure"},
    ):
        extract_source_text(root, registered["source_id"])

    packet = alternative_methods_for_matter(root)

    item = _item_by_status(packet, "failed")
    assert item["file_extension"] == ".pdf"
    assert item["reason_category"] == "local_extraction_failed"
    assert item["local_capability_state"] == "local_capability_failed_safely"
    assert item["local_capability_kind"] == "pdf_text_extraction"
    assert item["request_feature_state"] == "locked"
    assert item["available_actions"] == [
        "view_technical_details",
        "support_packet_available",
        "ignore_for_now",
    ]
    assert item["locked_actions"] == ["request_feature"]


def test_no_text_pdf_gets_ocr_needed_action(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "image-only.pdf"
    _write_no_text_pdf(source)
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)
    extract_source_text(root, registered["source_id"])

    packet = alternative_methods_for_matter(root)

    item = _item_by_status(packet, "no_text")
    assert item["file_extension"] == ".pdf"
    assert item["reason_category"] == "ocr_module_needed"
    assert item["local_capability_state"] == "local_capability_not_installed"
    assert item["local_capability_kind"] == "ocr"
    assert item["request_feature_state"] == "locked"
    assert item["available_actions"][0] == "ocr_module_needed"
    assert item["locked_actions"] == ["request_feature"]


def test_extracted_files_do_not_need_alternative_methods(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "statement.txt"
    source.write_text("fully extracted synthetic text", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)
    extract_source_text(root, registered["source_id"])

    packet = alternative_methods_for_matter(root)

    assert packet["source_count"] == 1
    assert packet["needs_alternative_methods"] == 0
    assert packet["items"] == []


def test_alternative_methods_excludes_sensitive_data(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "Jane_Client_Privileged_Notes.weird"
    source.write_bytes(b"privileged settlement strategy")
    create_matter_workspace(root, "matter", "Jane Client Matter")
    registered = register_source(root, source)
    extract_source_text(root, registered["source_id"])

    packet_text = json.dumps(alternative_methods_for_matter(root), sort_keys=True)

    assert "Jane_Client_Privileged_Notes" not in packet_text
    assert "Jane Client" not in packet_text
    assert "privileged settlement strategy" not in packet_text
    assert str(root) not in packet_text
    assert str(source) not in packet_text
