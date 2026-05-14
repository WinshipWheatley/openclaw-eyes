#!/usr/bin/env python3
"""Import a transferred root manifest into Corpus Atlas tables."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from mac_mirror_atlas import import_root_manifest, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import an explicit metadata manifest into the existing OpenClaw ledger."
    )
    parser.add_argument("--manifest", required=True, help="Manifest JSON path.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Optional deterministic import run id.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = import_root_manifest(
        manifest_path=args.manifest,
        db_path=args.db,
        run_id=args.run_id,
    )
    payload = {
        "run_id": result.run_id,
        "root_id": result.root_id,
        "path_count": result.path_count,
        "hashed_count": result.hashed_count,
        "no_go_count": result.no_go_count,
        "matched_mirror_candidates": result.matched_mirror_candidates,
        "mismatched_mirror_candidates": result.mismatched_mirror_candidates,
        "raw_file_bodies_imported": False,
        "canonical_truth_promoted": False,
    }
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print("Root Manifest Import v0")
        print("")
        print(f"Run: `{payload['run_id']}`")
        print(f"Root: `{payload['root_id']}`")
        print(f"Paths imported: {payload['path_count']}")
        print(f"Hashed safe files: {payload['hashed_count']}")
        print(f"No-go metadata rows: {payload['no_go_count']}")
        print(f"Matched mirrors: {payload['matched_mirror_candidates']}")
        print(f"Mismatched mirrors: {payload['mismatched_mirror_candidates']}")
        print("Raw file bodies imported: false")
        print("Canonical truth promoted: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
