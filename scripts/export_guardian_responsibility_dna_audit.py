#!/usr/bin/env python3
"""Export Guardian responsibility/DNA audit read-models."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from guardian_responsibility_dna_audit import (
    build_guardian_responsibility_dna_audit,
    export_guardian_responsibility_dna_audit,
    format_guardian_responsibility_dna_audit,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Guardian responsibility/DNA audit read-models.")
    parser.add_argument("--export-root", default="generated/read_models")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_guardian_responsibility_dna_audit(export_root=args.export_root)
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        print(format_guardian_responsibility_dna_audit(build_guardian_responsibility_dna_audit()), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
