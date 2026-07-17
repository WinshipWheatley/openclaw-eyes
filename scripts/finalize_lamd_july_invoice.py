#!/usr/bin/env python3
"""Run the W1 LAMD July verification/finalization owner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import invoice_w1_owner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--expected-source-sha256")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    result = invoice_w1_owner.run_lamd_july_finalization(
        source_path=[Path(item) for item in args.source],
        package_dir=Path(args.package_dir),
        receipt_path=Path(args.receipt),
        expected_source_sha256=args.expected_source_sha256,
        confirm=args.confirm,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] in {"DRY_RUN_READY", "PUBLISHED_VERIFIED", "IDEMPOTENT_REPLAY"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
