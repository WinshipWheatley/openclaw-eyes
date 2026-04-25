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
from legal.search_report import export_search_report


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_audit(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _register_and_extract(root: Path, source: Path) -> dict:
    registered = register_source(root, source)
    return extract_source_text(root, registered["source_id"])


def test_exports_report_with_search_results(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "contract.txt"
    source.write_text("The venue clause controls venue.", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    metadata = _register_and_extract(root, source)

    result = export_search_report(root, "venue")

    report = Path(result["report_path"]).read_text(encoding="utf-8")
    assert result["result_count"] == 1
    assert "# Legal Search Report" in report
    assert "- Query: `venue`" in report
    assert f"- Source ID: `{metadata['source_id']}`" in report
    assert "- Match count: 1" not in report
    assert "- Match count: 2" in report


def test_report_lives_under_exports(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "note.txt"
    source.write_text("payment due", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    _register_and_extract(root, source)

    result = export_search_report(root, "payment")

    report_path = Path(result["report_path"])
    assert report_path.parent == root / "exports"
    assert report_path.name == "search-report-payment.md"


def test_report_contains_citation_fields_and_snippets(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "record.md"
    source.write_text("Client discussed settlement posture.", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    metadata = _register_and_extract(root, source)

    result = export_search_report(root, "settlement", snippet_chars=5)

    report = Path(result["report_path"]).read_text(encoding="utf-8")
    assert metadata["source_id"] in report
    assert metadata["original_filename"] in report
    assert metadata["sha256"] in report
    assert "ssed settlement post" in report


def test_zero_result_report_creation(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "record.txt"
    source.write_text("No matching content.", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    _register_and_extract(root, source)

    result = export_search_report(root, "absent")

    report = Path(result["report_path"]).read_text(encoding="utf-8")
    assert result["result_count"] == 0
    assert "- Result count: 0" in report
    assert "No results found." in report


def test_report_name_sanitization_prevents_path_traversal(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "record.txt"
    source.write_text("needle", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    _register_and_extract(root, source)

    result = export_search_report(root, "needle", report_name="../Unsafe Report.md")

    report_path = Path(result["report_path"])
    assert report_path.parent == root / "exports"
    assert report_path.name == "unsafe-report.md"
    assert report_path.exists()


def test_blank_report_name_falls_back_to_query_based_default(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "record.txt"
    source.write_text("venue", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    _register_and_extract(root, source)

    result = export_search_report(root, "venue", report_name="   ")

    assert Path(result["report_path"]).name == "search-report-venue.md"


def test_report_export_and_search_audit_entries_are_appended(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "record.txt"
    source.write_text("payment", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    _register_and_extract(root, source)
    initial_audit = (root / "audit.jsonl").read_text(encoding="utf-8")

    result = export_search_report(root, "payment")

    final_audit = (root / "audit.jsonl").read_text(encoding="utf-8")
    assert final_audit.startswith(initial_audit)
    events = _read_audit(root / "audit.jsonl")
    assert events[-2]["event"] == "extracted_text_searched"
    assert events[-2]["query"] == "payment"
    assert events[-1]["event"] == "search_report_exported"
    assert events[-1]["query"] == "payment"
    assert events[-1]["result_count"] == 1
    assert events[-1]["report_path"] == result["report_path"]


def test_report_export_appends_new_audit_entry_when_overwriting(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "record.txt"
    source.write_text("venue", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    _register_and_extract(root, source)

    first = export_search_report(root, "venue")
    second = export_search_report(root, "venue")

    assert second["report_path"] == first["report_path"]
    events = _read_audit(root / "audit.jsonl")
    assert [event["event"] for event in events[-4:]] == [
        "extracted_text_searched",
        "search_report_exported",
        "extracted_text_searched",
        "search_report_exported",
    ]


def test_report_export_does_not_mutate_manifest(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "record.txt"
    source.write_text("venue", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    _register_and_extract(root, source)
    manifest_before = _read_json(root / "manifest.json")

    export_search_report(root, "venue")

    assert _read_json(root / "manifest.json") == manifest_before


def test_tampered_manifest_stored_path_outside_root_blocks_report(
    tmp_path: Path,
) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "record.txt"
    outside = tmp_path / "outside.txt"
    source.write_text("venue", encoding="utf-8")
    outside.write_text("outside", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    _register_and_extract(root, source)
    manifest_path = root / "manifest.json"
    manifest = _read_json(manifest_path)
    manifest["sources"][0]["stored_path"] = str(outside)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(LegalPathError, match="stored_path.*escapes"):
        export_search_report(root, "venue")


def test_no_network_calls_during_report_export(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "record.txt"
    source.write_text("offline report", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    _register_and_extract(root, source)

    with patch.object(socket, "create_connection", side_effect=AssertionError):
        export_search_report(root, "report")
