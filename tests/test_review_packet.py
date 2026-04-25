from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legal.local_ingestion import extract_source_text
from legal.matter_workspace import create_matter_workspace, register_source
from legal.path_guard import LegalPathError
from legal.review_packet import export_review_packet
from legal.search_report import export_search_report


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_audit(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _matter_with_extracted_source(root: Path, tmp_path: Path) -> dict:
    source = tmp_path / "source.txt"
    source.write_text("settlement packet text", encoding="utf-8")
    create_matter_workspace(root, "matter-001", "Matter")
    registered = register_source(root, source)
    return extract_source_text(root, registered["source_id"])


def test_review_packet_folder_created_under_exports(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    _matter_with_extracted_source(root, tmp_path)

    result = export_review_packet(root)

    packet_path = Path(result["packet_path"])
    assert packet_path.parent == root / "exports"
    assert packet_path.name == "review-packet-matter-001"
    assert packet_path.is_dir()


def test_packet_contains_manifest_and_audit_copies(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    _matter_with_extracted_source(root, tmp_path)

    result = export_review_packet(root)

    packet_path = Path(result["packet_path"])
    assert _read_json(packet_path / "manifest.json") == _read_json(root / "manifest.json")
    packet_audit = _read_audit(packet_path / "audit.jsonl")
    root_events = _read_audit(root / "audit.jsonl")
    assert [event["event"] for event in packet_audit] == [
        "matter_created",
        "source_registered",
        "source_text_extracted",
    ]
    assert root_events[-1]["event"] == "review_packet_exported"


def test_packet_contains_extracted_text_and_metadata(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    metadata = _matter_with_extracted_source(root, tmp_path)

    result = export_review_packet(root)

    packet_path = Path(result["packet_path"])
    extracted_name = Path(metadata["extracted_path"]).name
    metadata_name = Path(metadata["metadata_path"]).name
    assert (packet_path / "extracted" / extracted_name).read_text(
        encoding="utf-8"
    ) == "settlement packet text"
    assert _read_json(packet_path / "extracted" / metadata_name)["source_id"] == metadata[
        "source_id"
    ]


def test_packet_contains_markdown_reports_when_enabled(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    _matter_with_extracted_source(root, tmp_path)
    report = export_search_report(root, "settlement", report_name="settlement-report")

    result = export_review_packet(root, include_reports=True)

    packet_path = Path(result["packet_path"])
    report_copy = packet_path / "reports" / Path(report["report_path"]).name
    assert report_copy.is_file()
    assert "settlement packet text" in report_copy.read_text(encoding="utf-8")
    assert result["report_count"] == 1


def test_include_reports_false_excludes_reports(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    _matter_with_extracted_source(root, tmp_path)
    export_search_report(root, "settlement", report_name="settlement-report")

    result = export_review_packet(root, include_reports=False)

    packet_path = Path(result["packet_path"])
    assert not (packet_path / "reports").exists()
    assert result["report_count"] == 0


def test_packet_manifest_has_counts_and_matter_id(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    _matter_with_extracted_source(root, tmp_path)
    export_search_report(root, "settlement", report_name="settlement-report")

    result = export_review_packet(root)

    packet_manifest = _read_json(Path(result["packet_path"]) / "packet_manifest.json")
    assert packet_manifest == result
    assert packet_manifest["matter_id"] == "matter-001"
    assert packet_manifest["source_count"] == 1
    assert packet_manifest["extracted_count"] == 2
    assert packet_manifest["report_count"] == 1
    assert "manifest.json" in packet_manifest["included_files"]
    assert "audit.jsonl" in packet_manifest["included_files"]
    assert "packet_manifest.json" in packet_manifest["included_files"]


def test_packet_name_sanitization_prevents_path_traversal(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    _matter_with_extracted_source(root, tmp_path)

    result = export_review_packet(root, packet_name="../Buyer Packet")

    packet_path = Path(result["packet_path"])
    assert packet_path.parent == root / "exports"
    assert packet_path.name == "review-packet-buyer-packet"


def test_audit_entry_appended_for_packet_export(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    _matter_with_extracted_source(root, tmp_path)
    initial_audit = (root / "audit.jsonl").read_text(encoding="utf-8")

    result = export_review_packet(root)

    final_audit = (root / "audit.jsonl").read_text(encoding="utf-8")
    assert final_audit.startswith(initial_audit)
    events = _read_audit(root / "audit.jsonl")
    assert events[-1]["event"] == "review_packet_exported"
    assert events[-1]["packet_path"] == result["packet_path"]
    assert events[-1]["included_file_count"] == result["included_file_count"]


def test_review_packet_export_does_not_mutate_manifest(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    _matter_with_extracted_source(root, tmp_path)
    manifest_before = _read_json(root / "manifest.json")

    export_review_packet(root)

    assert _read_json(root / "manifest.json") == manifest_before


def test_tampered_manifest_stored_path_outside_root_blocks_review_packet(
    tmp_path: Path,
) -> None:
    root = tmp_path / "matter"
    _matter_with_extracted_source(root, tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    manifest_path = root / "manifest.json"
    manifest = _read_json(manifest_path)
    manifest["sources"][0]["stored_path"] = str(outside)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(LegalPathError, match="stored_path.*escapes"):
        export_review_packet(root)


def test_no_network_calls_during_review_packet_export(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    _matter_with_extracted_source(root, tmp_path)

    with patch.object(socket, "create_connection", side_effect=AssertionError):
        export_review_packet(root)
