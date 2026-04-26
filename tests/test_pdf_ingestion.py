from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legal.local_ingestion import extract_source_text
from legal.local_search import search_extracted_text
from legal.matter_workspace import create_matter_workspace, register_source


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_audit(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_text_layer_pdf(path: Path, text: str) -> None:
    content = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET"
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            "3 0 obj\n"
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\n"
            "endobj\n"
        ),
        "4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        f"5 0 obj\n<< /Length {len(content)} >>\nstream\n{content}\nendstream\nendobj\n",
    ]
    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf.encode("latin-1")))
        pdf += obj
    xref_offset = len(pdf.encode("latin-1"))
    pdf += "xref\n0 6\n0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n"
    pdf += (
        "trailer\n<< /Size 6 /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )
    path.write_bytes(pdf.encode("latin-1"))


def test_extracts_text_from_text_layer_pdf(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    pdf = tmp_path / "contract.pdf"
    _write_text_layer_pdf(pdf, "Settlement PDF Text")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, pdf)

    result = extract_source_text(root, registered["source_id"])

    assert result["status"] == "extracted"
    assert result["extractor"] == "pdftotext_v0"
    assert "Settlement PDF Text" in Path(result["extracted_path"]).read_text(
        encoding="utf-8"
    )


def test_pdf_extracted_artifact_and_metadata(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    pdf = tmp_path / "record.pdf"
    _write_text_layer_pdf(pdf, "PDF citation source")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, pdf)

    result = extract_source_text(root, registered["source_id"])

    extracted_path = root / "extracted" / f"{registered['source_id']}.txt"
    metadata_path = root / "extracted" / f"{registered['source_id']}.json"
    assert result["source_id"] == registered["source_id"]
    assert result["original_filename"] == "record.pdf"
    assert result["sha256"] == registered["sha256"]
    assert result["file_type"] == "application/pdf"
    assert result["extracted_path"] == str(extracted_path)
    assert result["metadata_path"] == str(metadata_path)
    assert result["chars"] > 0
    assert _read_json(metadata_path) == result
    manifest = _read_json(root / "manifest.json")
    assert manifest["sources"][0]["extraction_status"] == "extracted"
    assert manifest["sources"][0]["extraction_extractor"] == "pdftotext_v0"


def test_pdf_extraction_appends_audit_entry(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    pdf = tmp_path / "record.pdf"
    _write_text_layer_pdf(pdf, "Audit PDF Text")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, pdf)
    initial_audit = (root / "audit.jsonl").read_text(encoding="utf-8")

    result = extract_source_text(root, registered["source_id"])

    final_audit = (root / "audit.jsonl").read_text(encoding="utf-8")
    assert final_audit.startswith(initial_audit)
    events = _read_audit(root / "audit.jsonl")
    assert events[-1]["event"] == "source_text_extracted"
    assert events[-1]["extractor"] == "pdftotext_v0"
    assert events[-1]["source_id"] == registered["source_id"]
    assert events[-1]["extracted_path"] == result["extracted_path"]


def test_no_text_pdf_returns_status_without_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    pdf = tmp_path / "blank.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, pdf)

    with patch(
        "legal.local_ingestion._pdf_to_text",
        return_value={"ok": True, "text": "", "pages": 0, "chars": 0},
    ):
        result = extract_source_text(root, registered["source_id"])

    assert result["status"] == "no_text"
    assert result["reason"] == "PDF has no extractable text layer"
    assert not (root / "extracted").exists()
    events = _read_audit(root / "audit.jsonl")
    assert events[-1]["event"] == "source_extraction_no_text"
    assert events[-1]["source_id"] == registered["source_id"]


def test_corrupt_pdf_returns_failed_status_without_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    pdf = tmp_path / "corrupt.pdf"
    pdf.write_bytes(b"not a real pdf")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, pdf)

    result = extract_source_text(root, registered["source_id"])

    assert result["status"] == "failed"
    assert "pdftotext" in result["reason"].lower() or "syntax" in result["reason"].lower()
    assert not (root / "extracted").exists()
    events = _read_audit(root / "audit.jsonl")
    assert events[-1]["event"] == "source_extraction_failed"
    assert events[-1]["source_id"] == registered["source_id"]


def test_pdf_helper_unavailable_returns_failed_status(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    pdf = tmp_path / "record.pdf"
    _write_text_layer_pdf(pdf, "PDF helper unavailable")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, pdf)

    with patch(
        "legal.local_ingestion._pdf_to_text",
        return_value={
            "ok": False,
            "error": "PDF text extraction helper unavailable: missing helper",
        },
    ):
        result = extract_source_text(root, registered["source_id"])

    assert result["status"] == "failed"
    assert "helper unavailable" in result["reason"]
    assert not (root / "extracted").exists()


def test_local_search_finds_text_extracted_from_pdf(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    pdf = tmp_path / "contract.pdf"
    _write_text_layer_pdf(pdf, "Settlement clause searchable")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, pdf)
    extract_source_text(root, registered["source_id"])

    results = search_extracted_text(root, "settlement")

    assert len(results) == 1
    assert results[0]["source_id"] == registered["source_id"]
    assert "Settlement clause searchable" in results[0]["snippets"][0]


def test_no_network_calls_during_pdf_extraction(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    pdf = tmp_path / "record.pdf"
    _write_text_layer_pdf(pdf, "Offline PDF")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, pdf)

    with patch.object(socket, "create_connection", side_effect=AssertionError):
        extract_source_text(root, registered["source_id"])
