#!/usr/bin/env python3
"""Export the live rig read model and the proposed X32 .scn artifact (artifact only; no hardware)."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import live_rig


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the live rig read model and proposed X32 scene.")
    parser.add_argument("--config", default=str(live_rig.DEFAULT_CONFIG_PATH))
    parser.add_argument("--today", default=None, help="ISO date override (tests).")
    parser.add_argument("--export-root", default=str(live_rig.DEFAULT_EXPORT_ROOT))
    parser.add_argument("--artifact-root", default=str(live_rig.DEFAULT_ARTIFACT_ROOT))
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    today = date.fromisoformat(args.today) if args.today else None
    summary = live_rig.export_live_rig(config_path=args.config, export_root=args.export_root, artifact_root=args.artifact_root, today=today)
    if args.format == "json":
        print(live_rig.stable_json(summary), end="")
    else:
        print("Live Rig Export v0")
        print("")
        print(f"JSON: `{summary['json_path']}`")
        print(f"Operator: `{summary['operator_path']}`")
        print(f"Scene: `{summary['scene_path']}`  Channels: `{summary['channel_count']}`  Open loops: `{summary['open_loop_count']}`")
        if summary["uncategorized_channels"]:
            print(f"Uncategorized channels (set color by hand): {', '.join(summary['uncategorized_channels'])}")
        print("")
        print("Boundary: artifact only; the operator loads the scene on the console.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
