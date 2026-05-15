#!/usr/bin/env python3
"""Build the Agent Presence v0 snapshot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_presence import build_agent_presence_snapshot, stable_json
from business_ops_ledger import DEFAULT_DB_PATH


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check OpenClaw agent presence.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_agent_presence_snapshot(db_path=args.db)
    payload = {
        "status": "ok",
        "run_id": result.run_id,
        "agent_count": result.agent_count,
        "expected_online_count": result.expected_online_count,
        "online_count": result.online_count,
        "offline_unexpected_count": result.offline_unexpected_count,
        "degraded_count": result.degraded_count,
        "unknown_count": result.unknown_count,
    }
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print("Agent Presence Check v0")
        print("")
        print(f"Run: `{result.run_id}`")
        print(f"Agents: {result.agent_count}")
        print(f"Expected online: {result.expected_online_count}")
        print(f"Online: {result.online_count}")
        print(f"Unexpected offline/degraded/unknown: {result.offline_unexpected_count}")
        print("")
        print("Boundary:")
        print("- Presence check only; no Telegram API, message send, secret read, service restart, or agent activation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
