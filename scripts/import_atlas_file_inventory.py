#!/usr/bin/env python3
"""Import filesystem atlas metadata into business_ops_ledger.file_inventory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas_ledger_projection import record_atlas_file_inventory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import atlas metadata rows into file_inventory.")
    parser.add_argument("--atlas-path", default=None)
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--max-records", type=int, default=None)
    args = parser.parse_args(argv)
    result = record_atlas_file_inventory(
        atlas_path=args.atlas_path,
        db_path=args.db_path,
        max_records=args.max_records,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["records_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
