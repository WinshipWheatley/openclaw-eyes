#!/usr/bin/env python3
"""Phase-C conductor gate hook.

Writes one idempotent Phase-C writeback receipt for a green gate-release marker.
This script is a bounded hook target; it does not run a gate, start services,
deploy, merge, restart, send externally, or access private roots.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phase_c_conductor_foundation import (  # noqa: E402
    DEFAULT_ORCHESTRATION_ROOT,
    stable_json,
    write_phase_c_gate_hook_checkoff_receipt,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a Phase-C gate-hook checkoff receipt.")
    parser.add_argument("--orchestration-root", default=DEFAULT_ORCHESTRATION_ROOT.as_posix())
    parser.add_argument("--gate-release-marker", required=True)
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--format", choices=("json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = write_phase_c_gate_hook_checkoff_receipt(
        orchestration_root=args.orchestration_root,
        gate_release_marker=args.gate_release_marker,
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"Phase-C gate hook: {result['status']}")
        if result.get("receipt_path"):
            print(f"- Receipt: `{result['receipt_path']}`")
        if result.get("writeback_ref"):
            print(f"- Writeback: `{result['writeback_ref']}`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
