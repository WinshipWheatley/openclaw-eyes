#!/usr/bin/env python3
"""Render the Data Room confirmed-reference dry-run load plan."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dataroom_clean_load import (
    DEFAULT_CONFIRMED_REFERENCE_PATH,
    DEFAULT_LOAD_PLAN_PATH,
    build_load_plan,
    render_load_plan_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a dry-run canonical_facts load plan for the Data Room confirmed reference."
    )
    parser.add_argument("--source", default=str(DEFAULT_CONFIRMED_REFERENCE_PATH))
    parser.add_argument("--output", default=str(DEFAULT_LOAD_PLAN_PATH))
    parser.add_argument("--db", default=None, help="Optional ledger path for read-only conflict detection.")
    parser.add_argument("--source-commit", default=None)
    parser.add_argument("--json", action="store_true", help="Print the plan JSON to stdout.")
    args = parser.parse_args()

    plan = build_load_plan(
        args.source,
        db_path=args.db,
        source_commit=args.source_commit,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_load_plan_markdown(plan), encoding="utf-8")

    if args.json:
        print(json.dumps(plan.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"Wrote Data Room dry-run load plan: {output}")
        print(f"planned_writes={len(plan.planned_writes)} conflicts={len(plan.conflicts)} gaps={len(plan.gaps)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
