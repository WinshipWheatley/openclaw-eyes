#!/usr/bin/env python3
"""Export the Capital Hilton PO cycle read model; drafts the PO request locally when one is needed."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import capital_hilton_po_cycle as cycle


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the Capital Hilton PO cycle read model.")
    parser.add_argument("--config", default=str(cycle.DEFAULT_CONFIG_PATH))
    parser.add_argument("--today", default=None, help="ISO date override (tests).")
    parser.add_argument("--export-root", default=str(cycle.DEFAULT_EXPORT_ROOT))
    parser.add_argument("--draft-root", default=str(cycle.DEFAULT_DRAFT_ROOT))
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    today = date.fromisoformat(args.today) if args.today else None
    summary = cycle.export_po_cycle(config_path=args.config, export_root=args.export_root, draft_root=args.draft_root, today=today)
    if args.format == "json":
        print(cycle.stable_json(summary), end="")
    else:
        print("Capital Hilton PO Cycle Export v0")
        print("")
        print(f"JSON: `{summary['json_path']}`")
        print(f"Operator: `{summary['operator_path']}`")
        print(f"Needs new PO: `{summary['needs_new_po']}`  Uninvoiced performances: `{summary['uninvoiced_count']}`")
        if summary.get("draft_path"):
            print(f"Draft: `{summary['draft_path']}`")
        print("")
        print("Boundary: prepare-only; the draft is read and sent by the operator; Coupa stays manual.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
