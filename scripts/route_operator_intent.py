#!/usr/bin/env python3
"""Route a natural-language operator intent without executing anything."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from intent_router import format_route_result, route_operator_intent, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route an OpenClaw operator intent.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--text", required=True, help="Natural-language intent text.")
    parser.add_argument(
        "--source-kind",
        choices=("mission_control", "telegram", "cli", "report_bridge", "future_client_node", "unknown"),
        default="cli",
        help="Intent source kind.",
    )
    parser.add_argument("--source-channel", default="local_terminal", help="Source channel label.")
    parser.add_argument("--source-message-id", help="Source message id, metadata only.")
    parser.add_argument("--source-user-label", help="Source user label, metadata only.")
    parser.add_argument("--requested-by", default="operator", help="Requester label.")
    parser.add_argument("--intent-id", help="Optional deterministic intent id.")
    parser.add_argument("--run-id", help="Optional deterministic run id.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = route_operator_intent(
        text=args.text,
        source_kind=args.source_kind,
        source_channel=args.source_channel,
        source_message_id=args.source_message_id,
        source_user_label=args.source_user_label,
        requested_by=args.requested_by,
        db_path=args.db,
        intent_id=args.intent_id,
        run_id=args.run_id,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(format_route_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
