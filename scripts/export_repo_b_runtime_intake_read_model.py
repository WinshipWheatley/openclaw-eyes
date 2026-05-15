#!/usr/bin/env python3
"""Export Repo B Runtime Intake generated read-model files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from repo_b_runtime_intake import export_repo_b_runtime_intake_read_model, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Repo B Runtime Intake read-model.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--export-root", default="generated/read_models", help="Read-model export root.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_repo_b_runtime_intake_read_model(db_path=args.db, export_root=args.export_root)
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        print("Repo B Runtime Intake Read-Model Export v0")
        print("")
        print(f"JSON: `{summary['json_path']}`")
        print(f"Operator: `{summary['operator_path']}`")
        print(f"Repo B path: `{summary['repo_b_path']}`")
        print(f"Files scanned: {summary['scanned_file_count']}")
        print(f"Startup scripts: {summary['startup_script_count']}")
        print(f"Module candidates: {summary['module_candidate_count']}")
        print("")
        print("Boundary:")
        print("- Export writes generated read-model files only; Repo B remains non-canonical and unexecuted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
