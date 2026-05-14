#!/usr/bin/env python3
"""Query Tool Intake Registry v0 candidate policy rows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from tool_intake import (
    build_tool_intake_report,
    format_tool_intake_report,
    query_tool_intake_report_section,
    stable_json,
)


REPORT_SECTIONS = (
    "summary",
    "category",
    "high-fit",
    "high-risk",
    "sandbox-later",
    "client-capsule",
    "installed-candidates",
    "not-detected-candidates",
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Tool Intake Registry v0 reports.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Tool intake run id. Defaults to latest.")
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
    review = " review" if item.get("requires_operator_review") else ""
    link = " linked" if item.get("inventory_observation_id") else " unlinked"
    return (
        f"- {item['tool_id']} ({item['category']}, {item['candidate_status']}, "
        f"{item['install_status']}, fit={item['architecture_fit']}, "
        f"risk={item['risk_level']}{review},{link})"
    )


def _format_section(payload: dict) -> str:
    if payload.get("status") == "no_runs":
        return "Tool Intake Registry v0\n\nNo tool intake runs are recorded."
    if payload.get("section") == "summary":
        return format_tool_intake_report(payload)
    lines = [
        f"Tool Intake Registry v0 - {payload['section']}",
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
    lines.extend(
        [
            "",
            "Boundary:",
            "- These are non-authorizing candidate policy rows only.",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.report == "summary":
        payload = build_tool_intake_report(db_path=args.db, run_id=args.run_id)
    else:
        payload = query_tool_intake_report_section(
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
