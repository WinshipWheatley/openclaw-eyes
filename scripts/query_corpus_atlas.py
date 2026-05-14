#!/usr/bin/env python3
"""Query/report Corpus Atlas v0.5 rows from the existing ledger."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from corpus_atlas import (
    DEFAULT_DB_PATH,
    build_atlas_report,
    format_atlas_report,
    query_report_section,
    stable_json,
)


REPORT_SECTIONS = (
    "summary",
    "top-level",
    "no-go",
    "generated-read-models",
    "stale",
    "world-bound",
    "reorg",
    "ingestion",
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Corpus Atlas v0.5 reports.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Optional atlas run id. Defaults to latest run.")
    parser.add_argument(
        "--report",
        choices=REPORT_SECTIONS,
        default="summary",
        help="Report section to emit.",
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def _format_section(payload: dict) -> str:
    if payload.get("status") == "no_runs":
        return "Corpus Atlas v0.5\n\nNo atlas runs are recorded."
    if "items" not in payload:
        report = build_atlas_report(run_id=payload["run"]["run_id"])
        return format_atlas_report(report)
    lines = [
        f"Corpus Atlas v0.5 - {payload['section']}",
        "",
        f"Run: `{payload['run_id']}`",
        "",
        "Items:",
    ]
    if not payload["items"]:
        lines.append("- none")
        return "\n".join(lines)
    for item in payload["items"]:
        lines.append(
            "- "
            + item["relative_path"].replace("\n", "\\n")
            + f" ({item['source_role']}, {item['freshness_label']}, "
            + f"{item['sensitivity_label']}, {item['raw_content_eligibility']}, "
            + f"{item['world_binding']}, {item['reorg_bucket']})"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.report == "summary" and args.format == "operator":
        report = build_atlas_report(db_path=args.db, run_id=args.run_id)
        print(format_atlas_report(report))
        return 0

    payload = query_report_section(db_path=args.db, run_id=args.run_id, section=args.report)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(_format_section(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
