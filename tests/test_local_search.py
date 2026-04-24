from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legal.local_ingestion import extract_source_text
from legal.local_search import SearchMetadataError, search_extracted_text
from legal.matter_workspace import create_matter_workspace, register_source


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


def test_searches_extracted_txt_content(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "evidence.txt"
    source.write_text("The contract mentions venue and payment.", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    metadata = _register_and_extract(root, source)

    results = search_extracted_text(root, "venue")

    assert len(results) == 1
    assert results[0]["source_id"] == metadata["source_id"]
    assert results[0]["match_count"] == 1
    assert results[0]["snippets"] == [
        "The contract mentions venue and payment."
    ]


def test_search_is_case_insensitive(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "note.md"
    source.write_text("Client discussed Settlement posture.", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    _register_and_extract(root, source)

    results = search_extracted_text(root, "settlement")

    assert len(results) == 1
    assert results[0]["match_count"] == 1


def test_empty_results_append_audit_entry(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "evidence.txt"
    source.write_text("No relevant term here.", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    _register_and_extract(root, source)
    initial_audit = (root / "audit.jsonl").read_text(encoding="utf-8")

    results = search_extracted_text(root, "missing")

    assert results == []
    final_audit = (root / "audit.jsonl").read_text(encoding="utf-8")
    assert final_audit.startswith(initial_audit)
    events = _read_audit(root / "audit.jsonl")
    assert events[-1]["event"] == "extracted_text_searched"
    assert events[-1]["query"] == "missing"
    assert events[-1]["result_count"] == 0


def test_missing_extracted_folder_returns_empty_results(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    create_matter_workspace(root, "matter", "Matter")

    results = search_extracted_text(root, "anything")

    assert results == []
    assert not (root / "extracted").exists()


def test_result_metadata_includes_citation_fields(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "record.txt"
    source.write_text("Find this citation term.", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    metadata = _register_and_extract(root, source)

    result = search_extracted_text(root, "citation")[0]

    assert result["source_id"] == metadata["source_id"]
    assert result["original_filename"] == metadata["original_filename"]
    assert result["sha256"] == metadata["sha256"]
    assert result["extracted_path"] == metadata["extracted_path"]
    assert result["metadata_path"] == metadata["metadata_path"]


def test_snippets_are_deterministic_and_bounded(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "long.txt"
    source.write_text("0123456789TARGETabcdefghij", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    _register_and_extract(root, source)

    first = search_extracted_text(root, "target", snippet_chars=3)
    second = search_extracted_text(root, "target", snippet_chars=3)

    assert first[0]["snippets"] == ["789TARGETabc"]
    assert second[0]["snippets"] == first[0]["snippets"]
    assert len(first[0]["snippets"][0]) <= len("target") + 6


def test_max_results_limits_result_objects_not_snippets(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    first = tmp_path / "a.txt"
    second = tmp_path / "b.txt"
    first.write_text("term term term", encoding="utf-8")
    second.write_text("term", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    first_metadata = _register_and_extract(root, first)
    _register_and_extract(root, second)

    results = search_extracted_text(root, "term", max_results=1)

    assert len(results) == 1
    assert results[0]["source_id"] == first_metadata["source_id"]
    assert results[0]["match_count"] == 3
    assert len(results[0]["snippets"]) == 3


def test_search_rejects_empty_or_whitespace_query(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    create_matter_workspace(root, "matter", "Matter")

    with pytest.raises(ValueError, match="query must not be empty"):
        search_extracted_text(root, "")
    with pytest.raises(ValueError, match="query must not be empty"):
        search_extracted_text(root, "   ")


def test_missing_metadata_raises_clear_error(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "evidence.txt"
    source.write_text("needle", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    metadata = _register_and_extract(root, source)
    Path(metadata["metadata_path"]).unlink()

    with pytest.raises(SearchMetadataError, match="missing extracted metadata"):
        search_extracted_text(root, "needle")


def test_corrupt_metadata_raises_clear_error(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "evidence.txt"
    source.write_text("needle", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    metadata = _register_and_extract(root, source)
    Path(metadata["metadata_path"]).write_text("{not json", encoding="utf-8")

    with pytest.raises(SearchMetadataError, match="corrupt extracted metadata"):
        search_extracted_text(root, "needle")


def test_metadata_missing_required_field_raises_clear_error(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "evidence.txt"
    source.write_text("needle", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    metadata = _register_and_extract(root, source)
    payload = _read_json(Path(metadata["metadata_path"]))
    payload.pop("sha256")
    Path(metadata["metadata_path"]).write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SearchMetadataError, match="metadata missing required fields"):
        search_extracted_text(root, "needle")


def test_no_network_calls_during_search(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "offline.txt"
    source.write_text("offline query", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    _register_and_extract(root, source)

    with patch.object(socket, "create_connection", side_effect=AssertionError):
        search_extracted_text(root, "query")
