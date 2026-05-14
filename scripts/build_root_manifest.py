#!/usr/bin/env python3
"""Build a safe metadata root manifest for explicit OpenClaw roots."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mac_mirror_atlas import build_root_manifest, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an explicit-root metadata manifest with no raw file bodies."
    )
    parser.add_argument("--root-id", required=True, help="Root id to record in the manifest.")
    parser.add_argument("--root", required=True, help="Explicit local root path to scan.")
    parser.add_argument("--root-kind", required=True, help="Root kind label.")
    parser.add_argument("--host-kind", required=True, help="Host kind label, such as mac.")
    parser.add_argument("--owner-scope", required=True, help="Owner scope label.")
    parser.add_argument("--output", required=True, help="Manifest output path.")
    parser.add_argument("--machine-label", help="Optional local machine label.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_root_manifest(
        root=args.root,
        root_id=args.root_id,
        root_kind=args.root_kind,
        host_kind=args.host_kind,
        owner_scope=args.owner_scope,
        output=args.output,
        machine_label=args.machine_label,
    )
    payload = {
        "root_id": result.manifest["root_id"],
        "root_kind": result.manifest["root_kind"],
        "host_kind": result.manifest["host_kind"],
        "absolute_root": result.manifest["absolute_root"],
        "output": result.output_path,
        "path_count": result.path_count,
        "hashed_count": result.hashed_count,
        "no_go_count": result.no_go_count,
        "raw_file_bodies_included": False,
    }
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print("Root Manifest v0")
        print("")
        print(f"Root: `{payload['root_id']}` ({payload['root_kind']}, {payload['host_kind']})")
        print(f"Absolute root: `{payload['absolute_root']}`")
        print(f"Output: `{payload['output']}`")
        print(f"Paths: {payload['path_count']}")
        print(f"Hashed safe files: {payload['hashed_count']}")
        print(f"No-go metadata rows: {payload['no_go_count']}")
        print("Raw file bodies included: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
