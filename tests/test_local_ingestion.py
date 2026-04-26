from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legal.local_ingestion import (
    ExtractionError,
    extract_all_supported_sources,
    extract_source_text,
)
from legal.matter_workspace import create_matter_workspace, register_source
from legal.path_guard import LegalPathError


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_audit(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_extracts_txt_source_text(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "evidence.txt"
    source.write_text("plain text evidence\n", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)

    result = extract_source_text(root, registered["source_id"])

    assert result["status"] == "extracted"
    assert Path(result["extracted_path"]).read_text(encoding="utf-8") == (
        "plain text evidence\n"
    )


def test_extracts_md_source_text(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "timeline.md"
    source.write_text("# Timeline\n\n- Event one\n", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)

    result = extract_source_text(root, registered["source_id"])

    assert result["status"] == "extracted"
    assert Path(result["extracted_path"]).read_text(encoding="utf-8") == (
        "# Timeline\n\n- Event one\n"
    )


def test_writes_extracted_artifact_and_metadata(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "memo.txt"
    source.write_text("citation source", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)

    result = extract_source_text(root, registered["source_id"])

    extracted_path = root / "extracted" / f"{registered['source_id']}.txt"
    metadata_path = root / "extracted" / f"{registered['source_id']}.json"
    assert result["extracted_path"] == str(extracted_path)
    assert result["metadata_path"] == str(metadata_path)
    assert extracted_path.read_text(encoding="utf-8") == "citation source"
    assert _read_json(metadata_path) == result
    manifest = _read_json(root / "manifest.json")
    assert manifest["sources"][0]["extraction_status"] == "extracted"
    assert manifest["sources"][0]["extraction_extractor"] == "local_text_v0"


def test_metadata_links_back_to_registered_source(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "record.txt"
    source.write_text("record", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)

    result = extract_source_text(root, registered["source_id"])

    assert result["source_id"] == registered["source_id"]
    assert result["original_filename"] == registered["original_filename"]
    assert result["sha256"] == registered["sha256"]
    assert result["stored_path"] == registered["stored_path"]
    assert result["extractor"] == "local_text_v0"


def test_audit_entries_are_appended_for_success(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "record.txt"
    source.write_text("record", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)
    initial_audit = (root / "audit.jsonl").read_text(encoding="utf-8")

    result = extract_source_text(root, registered["source_id"])

    final_audit = (root / "audit.jsonl").read_text(encoding="utf-8")
    assert final_audit.startswith(initial_audit)
    events = _read_audit(root / "audit.jsonl")
    assert events[-1]["event"] == "source_text_extracted"
    assert events[-1]["source_id"] == registered["source_id"]
    assert events[-1]["extracted_path"] == result["extracted_path"]


def test_unsupported_file_appends_audit_without_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "scan.bin"
    source.write_bytes(b"unsupported")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)

    result = extract_source_text(root, registered["source_id"])

    assert result["status"] == "unsupported"
    assert result["source_id"] == registered["source_id"]
    assert not (root / "extracted").exists()
    events = _read_audit(root / "audit.jsonl")
    assert events[-1]["event"] == "source_extraction_unsupported"
    assert events[-1]["source_id"] == registered["source_id"]


def test_tampered_manifest_stored_path_outside_matter_root_is_rejected(
    tmp_path: Path,
) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "source.txt"
    outside = tmp_path / "outside.txt"
    source.write_text("inside matter source", encoding="utf-8")
    outside.write_text("outside matter source", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)
    manifest_path = root / "manifest.json"
    manifest = _read_json(manifest_path)
    manifest["sources"][0]["stored_path"] = str(outside)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(LegalPathError, match="stored_path.*escapes"):
        extract_source_text(root, registered["source_id"])


def test_missing_source_id_raises_clear_key_error(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    create_matter_workspace(root, "matter", "Matter")

    with pytest.raises(KeyError, match="source_id not found"):
        extract_source_text(root, "src_missing")


def test_invalid_utf8_raises_clear_extraction_error(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "bad.txt"
    source.write_bytes(b"\xff\xfe\xfa")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)

    with pytest.raises(ExtractionError, match="not valid UTF-8"):
        extract_source_text(root, registered["source_id"])


def test_extract_all_supported_sources_returns_each_result(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    txt = tmp_path / "one.txt"
    md = tmp_path / "two.md"
    unsupported = tmp_path / "three.bin"
    txt.write_text("one", encoding="utf-8")
    md.write_text("two", encoding="utf-8")
    unsupported.write_bytes(b"unsupported")
    create_matter_workspace(root, "matter", "Matter")
    txt_entry = register_source(root, txt)
    md_entry = register_source(root, md)
    unsupported_entry = register_source(root, unsupported)

    results = extract_all_supported_sources(root)

    assert [result["source_id"] for result in results] == [
        txt_entry["source_id"],
        md_entry["source_id"],
        unsupported_entry["source_id"],
    ]
    assert [result["status"] for result in results] == [
        "extracted",
        "extracted",
        "unsupported",
    ]


def test_no_network_calls_during_extraction(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "offline.txt"
    source.write_text("offline only", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)

    with patch.object(socket, "create_connection", side_effect=AssertionError):
        extract_source_text(root, registered["source_id"])
