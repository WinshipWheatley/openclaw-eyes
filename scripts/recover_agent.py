#!/usr/bin/env python3
"""Run a bounded OpenClaw agent recovery action only when policy allows it."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_presence import AGENT_CONFIGS, format_agent_recovery_result, recover_agent, stable_json
from business_ops_ledger import DEFAULT_DB_PATH


AGENTS = tuple(config.agent_id for config in AGENT_CONFIGS)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recover one OpenClaw agent if fixed policy allows it.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--agent", choices=AGENTS, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Report what would happen without executing. Default.")
    mode.add_argument("--execute", action="store_true", help="Execute only if all policy and safety gates pass.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = recover_agent(
        agent_id=args.agent,
        db_path=args.db,
        execute=bool(args.execute),
        refresh_presence=True,
        refresh_after=bool(args.execute),
    )
    payload = {
        "agent_id": result.agent_id,
        "status": result.status,
        "dry_run": result.dry_run,
        "action_id": result.action_id,
        "attempted": result.attempted,
        "exit_code": result.exit_code,
        "receipt_id": result.receipt_id,
        "blocker": result.blocker,
        "summary": result.summary,
    }
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_agent_recovery_result(result))
    return 0 if result.status in {"dry_run_available", "succeeded", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
