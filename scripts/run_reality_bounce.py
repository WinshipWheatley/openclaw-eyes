#!/usr/bin/env python3
"""Run arbitrary operator text through the local Reality Bounce chain."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import reality_bounce_harness


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Reality Bounce Harness for one operator message.")
    parser.add_argument("operator_text", help="Operator text to route through the local OpenClaw chain.")
    parser.add_argument("--mode", choices=("local", "shadow-lm"), default="local")
    parser.add_argument("--db-path", type=Path, default=reality_bounce_harness.DEFAULT_DB_PATH)
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--source-request-id", default=None)
    parser.add_argument("--json", action="store_true", help="Print the full machine-readable result.")
    args = parser.parse_args(argv)

    payload = reality_bounce_harness.run_text(
        args.operator_text,
        mode=args.mode,
        db_path=args.db_path,
        generated_at=args.generated_at,
        source_request_id=args.source_request_id,
        persist=True,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(payload["operator_stdout"], end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
