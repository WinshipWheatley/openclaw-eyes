#!/usr/bin/env python3
"""Export Guardian/HITL dual-write compatibility read-models."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from guardian_hitl_dual_write_compatibility import (
    build_guardian_hitl_dual_write_read_model,
    export_guardian_hitl_dual_write_read_model,
    format_guardian_hitl_dual_write_read_model,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Guardian/HITL dual-write compatibility read-models."
    )
    parser.add_argument(
        "--export-root",
        default="generated/read_models",
        help="Read-model export root.",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Optional SQLite ledger path.",
    )
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_guardian_hitl_dual_write_read_model(
        export_root=args.export_root,
        db_path=args.db_path,
    )
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        read_model = build_guardian_hitl_dual_write_read_model(db_path=args.db_path)
        print(format_guardian_hitl_dual_write_read_model(read_model), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
