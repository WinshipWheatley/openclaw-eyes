#!/usr/bin/env python3
"""Check Telegram Agent Intake readiness without Telegram network access."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from telegram_agent_intake import check_telegram_agent_intake, format_telegram_intake_check_result, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Telegram Agent Intake readiness.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Optional deterministic run id.")
    parser.add_argument("--no-dry-run-proof", action="store_true", help="Skip synthetic local route proof.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = check_telegram_agent_intake(
        db_path=args.db,
        run_id=args.run_id,
        create_dry_run_proof=not args.no_dry_run_proof,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(format_telegram_intake_check_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
