#!/usr/bin/env python3
"""Export Guardian/HITL surface disposition read-models."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from guardian_hitl_surface_disposition import (
    build_guardian_hitl_surface_disposition,
    export_guardian_hitl_surface_disposition,
    format_guardian_hitl_surface_disposition,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Guardian/HITL surface disposition read-models."
    )
    parser.add_argument(
        "--export-root",
        default="generated/read_models",
        help="Read-model export root.",
    )
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_guardian_hitl_surface_disposition(export_root=args.export_root)
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        payload = build_guardian_hitl_surface_disposition()
        print(format_guardian_hitl_surface_disposition(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
