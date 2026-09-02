#!/usr/bin/env python3
"""Land a gig from one sentence into the local Gig-to-Cash ledger. Dry-run unless --apply."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gig_ledger_bridge as bridge


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Land a gig sentence as ledger facts (gig, draft invoice, open receivable).")
    parser.add_argument("text", help='e.g. "Dane asked me to play Oct 17 at 49 West for $500"')
    parser.add_argument("--apply", action="store_true", help="Write to the ledger. Without it, nothing is written.")
    parser.add_argument("--db", default=str(bridge.DEFAULT_DB_PATH))
    parser.add_argument("--client", default=None, help="Money client ref when no contact is on file (e.g. 49_west).")
    parser.add_argument("--client-name", default=None, help="Display name for a new client ref.")
    parser.add_argument("--amount", default=None, help="Dollars, overrides the sentence and the default rate.")
    parser.add_argument("--terms-days", type=int, default=0, help="Days after the service date the cash is due (default: due on the night).")
    parser.add_argument("--now", default=None, help="ISO datetime override (tests).")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    now = None
    if args.now:
        now = datetime.fromisoformat(args.now)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
    result = bridge.land_gig(
        args.text,
        db_path=args.db,
        apply=args.apply,
        now=now,
        client_ref=args.client,
        client_name=args.client_name,
        amount_dollars=args.amount,
        terms_days=args.terms_days,
    )
    if args.format == "json":
        print(bridge.stable_json(result), end="")
    else:
        print(bridge.format_operator_markdown(result), end="")
    return 0 if result.get("status") in {"dry_run", "landed", "already_landed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
