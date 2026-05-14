#!/usr/bin/env python3
"""Prepare a Windows-accessible Mac read-model shuttle package."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from corpus_atlas import stable_json
from read_model_shuttle import (
    DEFAULT_SOURCE_ROOT,
    DEFAULT_TO_MAC_ROOT,
    format_prepare_result,
    prepare_mac_read_model_shuttle,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a generated read-model shuttle package for Mac transfer."
    )
    parser.add_argument(
        "--source-root",
        default=DEFAULT_SOURCE_ROOT.as_posix(),
        help="Generated read-model source root. Defaults to generated/read_models.",
    )
    parser.add_argument(
        "--output-root",
        default=DEFAULT_TO_MAC_ROOT.as_posix(),
        help="Package output root. Defaults to /mnt/e/openclaw/shuttle/to_mac.",
    )
    parser.add_argument("--package-name", help="Optional package folder name.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = prepare_mac_read_model_shuttle(
        source_root=args.source_root,
        output_root=args.output_root,
        package_name=args.package_name,
    )
    payload = {
        "package_path": result.package_path,
        "manifest_path": result.manifest_path,
        "file_count": result.file_count,
        "total_bytes": result.total_bytes,
        "copied_files": list(result.copied_files),
        "runtime_authority": False,
        "backend_execution_allowed": False,
        "agent_activation_allowed": False,
        "tool_execution_allowed": False,
        "model_execution_allowed": False,
        "container_execution_allowed": False,
        "network_authority": False,
        "truth_promotion_allowed": False,
    }
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_prepare_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
