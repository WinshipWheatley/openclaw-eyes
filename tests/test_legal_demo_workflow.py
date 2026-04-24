from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.demo_legal_matter_workflow import QUERY, run_demo_workflow


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_audit(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_demo_legal_matter_workflow_end_to_end(tmp_path: Path) -> None:
    result = run_demo_workflow(tmp_path)

    matter_root = Path(result["matter_root"])
    report_path = Path(result["report_path"])
    manifest = _read_json(matter_root / "manifest.json")
    audit_entries = _read_audit(matter_root / "audit.jsonl")
    report = report_path.read_text(encoding="utf-8")

    assert matter_root.is_dir()
    assert manifest["matter_id"] == "demo-matter"
    assert len(manifest["sources"]) == 2
    assert len(result["source_ids"]) == 2
    assert result["result_count"] == 2

    for extracted_path in result["extracted_paths"]:
        assert Path(extracted_path).is_file()

    assert report_path.parent == matter_root / "exports"
    assert report_path.is_file()
    assert f"- Query: `{QUERY}`" in report

    for source in manifest["sources"]:
        assert source["source_id"] in report
        assert source["original_filename"] in report
        assert source["sha256"] in report
    assert "settlement posture before mediation" in report
    assert "Settlement demand received" in report

    events = [entry["event"] for entry in audit_entries]
    assert result["audit_events"] == events
    assert "matter_created" in events
    assert events.count("source_registered") == 2
    assert events.count("source_text_extracted") == 2
    assert events.count("extracted_text_searched") == 2
    assert events[-1] == "search_report_exported"
