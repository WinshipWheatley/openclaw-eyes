#!/usr/bin/env python3
"""Capture or query governed intake spine records."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from governed_intake_spine import (
    build_governed_intake_spine_read_model,
    capture_governed_operator_intake,
    format_governed_intake_spine_read_model,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query or capture governed intake spine records.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--text", help="Optional operator text to capture into governed intake.")
    parser.add_argument("--source-kind", default="cli", help="Intent Router source kind.")
    parser.add_argument("--source-channel", default="governed_intake_spine_cli", help="Source channel label.")
    parser.add_argument("--requested-by", default="operator", help="Requester label.")
    parser.add_argument("--work-packet", action="store_true", help="Create Agent Work Packet if route is fully routed.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def _format_capture(result) -> str:
    return "\n".join(
        [
            "Governed Intake Spine v0",
            "",
            f"Intake: `{result.intake_id}`",
            f"Intent: `{result.intent_id}`",
            f"Status: `{result.route_status}`",
            f"Agent/lane: `{result.routed_agent_id or 'none'}` / `{result.routed_lane_id or 'none'}`",
            f"Category: `{result.intent_category}`",
            f"Work Board card: `{result.work_board_card_id or 'none'}`",
            f"Work packet: `{result.work_packet_id or 'none'}`",
            f"Execution allowed: `{str(result.execution_allowed).lower()}`",
            f"Action created: `{str(result.action_created).lower()}`",
            "",
            "Boundary:",
            "- Deterministic capture only; no send, execution, approval bypass, model call, network call, repo creation, or deployment.",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.text:
        result = capture_governed_operator_intake(
            raw_text=args.text,
            source_kind=args.source_kind,
            source_channel=args.source_channel,
            requested_by=args.requested_by,
            db_path=args.db,
            create_agent_work_packet=args.work_packet,
        )
        if args.format == "json":
            print(stable_json(result.__dict__), end="")
        else:
            print(_format_capture(result))
        return 0

    read_model = build_governed_intake_spine_read_model(db_path=args.db)
    if args.format == "json":
        print(stable_json(read_model), end="")
    else:
        print(format_governed_intake_spine_read_model(read_model), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
