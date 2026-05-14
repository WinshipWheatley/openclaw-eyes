#!/usr/bin/env python3
"""Query Local Tool Inventory v0 rows from the Business Ops ledger."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from tool_inventory import (
    build_tool_inventory_report,
    format_tool_inventory_report,
    query_tool_inventory_report_section,
    stable_json,
)


REPORT_SECTIONS = (
    "summary",
    "detected",
    "category",
    "high-risk",
    "future-candidates",
    "not-detected",
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Local Tool Inventory v0 reports.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Tool inventory run id. Defaults to latest.")
    parser.add_argument(
        "--report",
        choices=REPORT_SECTIONS,
        default="summary",
        help="Report section to emit.",
    )
    parser.add_argument("--category", help="Category for --report category.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def _format_item(item: dict) -> str:
    version = f" :: {item['version_text']}" if item.get("version_text") else ""
    path = item.get("executable_path") or "not found"
    review = " review" if item.get("requires_operator_review") else ""
    if "candidate_scope" in item:
        return (
            f"- {item['tool_id']} ({item['category']}, {item['risk_level']}{review}) "
            f"{path} -> {item['candidate_scope']} [{item['candidate_status']}]"
        )
    return (
        f"- {item['tool_id']} ({item['category']}, {item['install_status']}, "
        f"{item['risk_level']}{review}) {path}{version}"
    )


def _format_section(payload: dict) -> str:
    if payload.get("status") == "no_runs":
        return "Local Tool Inventory v0\n\nNo tool inventory runs are recorded."
    if payload.get("section") == "summary":
        return format_tool_inventory_report(payload)
    lines = [
        f"Local Tool Inventory v0 - {payload['section']}",
        "",
        f"Run: `{payload['run_id']}`",
        "",
        "Items:",
    ]
    items = payload.get("items") or []
    if not items:
        lines.append("- none")
        return "\n".join(lines)
    for item in items:
        lines.append(_format_item(item))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.report == "summary":
        payload = build_tool_inventory_report(db_path=args.db, run_id=args.run_id)
    else:
        payload = query_tool_inventory_report_section(
            db_path=args.db,
            run_id=args.run_id,
            section=args.report,
            category=args.category,
        )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(_format_section(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
