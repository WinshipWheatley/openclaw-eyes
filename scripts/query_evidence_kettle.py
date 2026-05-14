#!/usr/bin/env python3
"""Query Evidence Kettle v0.1 rows from the existing ledger."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from evidence_kettle import (
    build_evidence_report,
    format_evidence_report,
    query_evidence_report_section,
    stable_json,
)


REPORT_SECTIONS = (
    "summary",
    "world",
    "category",
    "read-models",
    "future-gated",
    "unsupported",
    "runtime-gate",
    "next-safe-move",
    "receipts",
    "sources",
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Evidence Kettle v0.1 reports.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Evidence ingestion run id. Defaults to latest.")
    parser.add_argument(
        "--report",
        choices=REPORT_SECTIONS,
        default="summary",
        help="Report section to emit.",
    )
    parser.add_argument("--world", help="World id for --report world.")
    parser.add_argument("--category", help="Evidence category for --report category.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def _format_section(payload: dict) -> str:
    if payload.get("status") == "no_runs":
        return "Evidence Kettle v0.1\n\nNo evidence ingestion runs are recorded."
    if payload.get("section") == "summary":
        return format_evidence_report(payload)
    lines = [
        f"Evidence Kettle v0.1 - {payload['section']}",
        "",
        f"Run: `{payload['ingestion_run_id']}`",
        "",
        "Items:",
    ]
    items = payload.get("items") or []
    if not items:
        lines.append("- none")
        return "\n".join(lines)
    for item in items:
        if "relative_path" in item:
            lines.append(
                "- "
                + item["relative_path"].replace("\n", "\\n")
                + f" ({item.get('file_format')}, {item.get('read_model_version')})"
            )
            continue
        if "source_id" in item and "evidence_key" not in item:
            lines.append(
                "- "
                + item["source_path"].replace("\n", "\\n")
                + f" ({item['source_type']}, {item['ingestion_eligibility']})"
            )
            continue
        world_suffix = f", {item.get('world_id')}" if item.get("world_id") else ""
        lines.append(
            "- "
            + item["source_path"].replace("\n", "\\n")
            + f" :: {item['evidence_label']} / {item['evidence_category']} / "
            + f"{item['evidence_key']}{world_suffix}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.report == "summary":
        payload = build_evidence_report(db_path=args.db, ingestion_run_id=args.run_id)
    else:
        payload = query_evidence_report_section(
            db_path=args.db,
            ingestion_run_id=args.run_id,
            section=args.report,
            world=args.world,
            category=args.category,
        )
    if args.format == "json":
        print(stable_json(payload), end="")
    elif args.report == "summary":
        print(format_evidence_report(payload))
    else:
        print(_format_section(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
