#!/usr/bin/env python3
"""Export Operator Action Path v0 as generated read-model files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from operator_action import export_operator_actions_read_model, format_export_summary, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export helm-gated operator action posture as generated read-model files."
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument(
        "--export-root",
        default="generated/read_models",
        help="Export root. Defaults to generated/read_models.",
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_operator_actions_read_model(
        db_path=args.db,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        print(format_export_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
