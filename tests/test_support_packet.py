from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legal.local_ingestion import extract_source_text
from legal.matter_workspace import create_matter_workspace, register_source
from legal.review_packet import export_review_packet
from legal.support_packet import export_support_packet
from scripts.demo_legal_mock_discovery import _write_no_text_pdf


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_support_packet_is_created_for_synthetic_matter(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "client-secret-facts.txt"
    source.write_text("privileged settlement content", encoding="utf-8")
    create_matter_workspace(root, "matter-001", "Private Client Matter")
    registered = register_source(root, source)
    extract_source_text(root, registered["source_id"])

    packet = export_support_packet(root)

    packet_path = Path(packet["packet_path"])
    assert packet["artifact_type"] == "sanitized_support_packet"
    assert packet["content_excluded"] is True
    assert packet_path == root / "support" / "support-packet-latest" / "support_packet.json"
    saved_packet = _read_json(packet_path)
    assert saved_packet["artifact_type"] == "sanitized_support_packet"
    assert "packet_path" not in saved_packet


def test_support_packet_excludes_source_and_extracted_content(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "client-secret-facts.txt"
    sensitive_text = "Jane Client privileged settlement content"
    source.write_text(sensitive_text, encoding="utf-8")
    create_matter_workspace(root, "matter-001", "Jane Client Matter")
    registered = register_source(root, source)
    extract_source_text(root, registered["source_id"])

    packet = export_support_packet(root)
    packet_text = Path(packet["packet_path"]).read_text(encoding="utf-8")

    assert sensitive_text not in packet_text
    assert "Jane Client" not in packet_text
    assert "privileged settlement content" not in packet_text


def test_support_packet_excludes_sensitive_filename_and_private_paths(
    tmp_path: Path,
) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "Jane_Client_Settlement_Strategy.txt"
    source.write_text("diagnostic content must not leak", encoding="utf-8")
    create_matter_workspace(root, "matter-001", "Sensitive Matter")
    registered = register_source(root, source)
    extract_source_text(root, registered["source_id"])

    packet = export_support_packet(root)
    packet_text = Path(packet["packet_path"]).read_text(encoding="utf-8")

    assert "Jane_Client_Settlement_Strategy" not in packet_text
    assert str(root) not in packet_text
    assert str(source) not in packet_text
    assert packet["private_paths_excluded"] is True


def test_support_packet_includes_status_counts_and_diagnostics(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    supported = tmp_path / "evidence.txt"
    unsupported = tmp_path / "scan.bin"
    supported.write_text("searchable text", encoding="utf-8")
    unsupported.write_bytes(b"unsupported bytes")
    create_matter_workspace(root, "matter-001", "Matter")
    supported_entry = register_source(root, supported)
    unsupported_entry = register_source(root, unsupported)
    extract_source_text(root, supported_entry["source_id"])
    extract_source_text(root, unsupported_entry["source_id"])

    packet = export_support_packet(root)

    assert packet["matter"]["source_count"] == 2
    assert packet["diagnostics"]["source_status_counts"]["extracted"] == 1
    assert packet["diagnostics"]["source_status_counts"]["unsupported"] == 1
    assert packet["diagnostics"]["file_extensions"] == [".bin", ".txt"]
    assert packet["diagnostics"]["file_size_ranges"]["0-10KB"] == 2
    assert packet["diagnostics"]["extractors"] == ["local_text_v0"]
    assert len(packet["diagnostics"]["redacted_status_summaries"]) == 2


def test_support_packet_reports_failed_extraction_from_manifest_status(
    tmp_path: Path,
) -> None:
    root = tmp_path / "matter"
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    create_matter_workspace(root, "matter-001", "Matter")
    registered = register_source(root, pdf)

    with patch(
        "legal.local_ingestion._pdf_to_text",
        return_value={"ok": False, "error": "synthetic pdf failure"},
    ):
        result = extract_source_text(root, registered["source_id"])
    packet = export_support_packet(root)

    assert result["status"] == "failed"
    assert packet["diagnostics"]["source_status_counts"]["failed"] == 1
    assert packet["diagnostics"]["source_status_counts"]["pending"] == 0
    assert packet["diagnostics"]["extractors"] == ["pdftotext_v0"]
    assert packet["diagnostics"]["redacted_status_summaries"][0]["status"] == "failed"


def test_support_packet_reports_no_text_pdf_from_manifest_status(
    tmp_path: Path,
) -> None:
    root = tmp_path / "matter"
    pdf = tmp_path / "image-only.pdf"
    _write_no_text_pdf(pdf)
    create_matter_workspace(root, "matter-001", "Matter")
    registered = register_source(root, pdf)

    result = extract_source_text(root, registered["source_id"])
    packet = export_support_packet(root)

    assert result["status"] == "no_text"
    assert packet["diagnostics"]["source_status_counts"]["no_text"] == 1
    assert packet["diagnostics"]["source_status_counts"]["failed"] == 0
    summary = packet["diagnostics"]["redacted_status_summaries"][0]
    assert summary["status"] == "no_text"
    assert summary["reason_category"] == "no_extractable_text"


def test_support_packet_distinguishes_itself_from_review_packets(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "source.txt"
    source.write_text("review packet may contain content", encoding="utf-8")
    create_matter_workspace(root, "matter-001", "Matter")
    registered = register_source(root, source)
    extract_source_text(root, registered["source_id"])

    review_packet = export_review_packet(root)
    support_packet = export_support_packet(root)

    assert review_packet["packet_path"] != support_packet["packet_path"]
    assert support_packet["artifact_type"] == "sanitized_support_packet"
    assert "included_files" not in support_packet
    assert support_packet["exclusions"]["review_packets"] == "excluded"
