#!/usr/bin/env python3
"""Write one validated v2 fleet WAKE record."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fleet_coordination_contracts import PRIORITIES, URGENT_REASONS, write_wake_ping


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wake-dir",
        type=Path,
        default=Path("/mnt/e/openclaw/fleet_coord/WAKE"),
    )
    parser.add_argument("--from-seat", required=True)
    parser.add_argument("--to-seat", required=True)
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--priority", choices=sorted(PRIORITIES), default="normal")
    parser.add_argument("--urgent-reason", choices=sorted(URGENT_REASONS))
    parser.add_argument("--needs-human-kick", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    written = write_wake_ping(
        wake_dir=args.wake_dir,
        from_seat=args.from_seat,
        to_seat=args.to_seat,
        mission_id=args.mission_id,
        reference_path=args.file,
        priority=args.priority,
        urgent_reason=args.urgent_reason,
        needs_human_kick=args.needs_human_kick,
    )
    print(written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
