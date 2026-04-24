#!/usr/bin/env python3
"""Deterministic local demo for the OpenClaw Legal workflow spine."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.local_ingestion import extract_source_text
from legal.local_search import search_extracted_text
from legal.matter_workspace import create_matter_workspace, register_source
from legal.search_report import export_search_report


QUERY = "settlement"


def run_demo_workflow(output_root: str | Path) -> dict[str, Any]:
    """Create a local demo matter and run registration through report export."""

    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    source_dir = output / "sample_sources"
    source_dir.mkdir(exist_ok=True)
    matter_root = output / "demo_matter"

    first_source = source_dir / "engagement_notes.txt"
    second_source = source_dir / "case_timeline.md"
    first_source.write_text(
        "Client asked counsel to evaluate settlement posture before mediation.\n",
        encoding="utf-8",
    )
    second_source.write_text(
        "# Case Timeline\n\n- Settlement demand received after discovery.\n",
        encoding="utf-8",
    )

    create_matter_workspace(
        matter_root,
        matter_id="demo-matter",
        display_name="Demo Matter",
        created_at="2026-04-23T12:00:00Z",
    )
    registered_sources = [
        register_source(matter_root, first_source),
        register_source(matter_root, second_source),
    ]
    extracted = [
        extract_source_text(matter_root, source["source_id"])
        for source in registered_sources
    ]
    search_results = search_extracted_text(matter_root, QUERY)
    report = export_search_report(
        matter_root,
        QUERY,
        report_name="demo-settlement-search.md",
    )
    audit_events = _audit_events(matter_root / "audit.jsonl")

    return {
        "matter_root": str(matter_root),
        "report_path": report["report_path"],
        "result_count": len(search_results),
        "audit_events": audit_events,
        "source_ids": [source["source_id"] for source in registered_sources],
        "extracted_paths": [item["extracted_path"] for item in extracted],
    }


def _audit_events(audit_path: Path) -> list[str]:
    events = []
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line)["event"])
    return events


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: demo_legal_matter_workflow.py OUTPUT_ROOT", file=sys.stderr)
        return 2
    result = run_demo_workflow(argv[1])
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

