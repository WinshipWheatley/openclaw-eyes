#!/usr/bin/env python3
"""Manual OpenClaw worker-run lifecycle CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import codex_work_package_lifecycle as lifecycle


def _print(payload: object) -> None:
    print(lifecycle.stable_json(payload), end="")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage manual OpenClaw worker package runs.")
    parser.add_argument("--sqlite-path", default=str(lifecycle.DEFAULT_SQLITE_PATH))
    parser.add_argument("--package-root", default=str(lifecycle.DEFAULT_PACKAGE_ROOT))
    parser.add_argument("--export-root", default=str(lifecycle.DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(lifecycle.DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(lifecycle.DEFAULT_WIKI_PATH))
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List worker packages.")

    show_parser = subparsers.add_parser("show", help="Show one worker package.")
    show_parser.add_argument("package_id")

    dispatch_parser = subparsers.add_parser("dispatch", help="Record a manual package dispatch.")
    dispatch_parser.add_argument("package_id")
    dispatch_parser.add_argument("--worker", required=True, choices=lifecycle.ALLOWED_WORKER_KINDS)
    dispatch_parser.add_argument("--by", default="operator")
    dispatch_parser.add_argument("--note", default="")
    dispatch_parser.add_argument("--in-progress", action="store_true")

    ingest_parser = subparsers.add_parser("ingest", help="Ingest a manual worker result.")
    ingest_parser.add_argument("package_id")
    source = ingest_parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file")
    source.add_argument("--stdin", action="store_true")

    subparsers.add_parser("status", help="Export and summarize lifecycle status.")

    args = parser.parse_args(list(argv) if argv is not None else None)
    sqlite_path = Path(args.sqlite_path)
    package_root = Path(args.package_root)

    if args.command == "list":
        read_model = lifecycle.build_read_model(sqlite_path=sqlite_path, package_root=package_root)
        _print(
            {
                "status": read_model["status"],
                "package_ids": read_model["package_ids"],
                "counts": read_model["counts"],
                "next_action": read_model["next_action"],
            }
        )
        return 0

    if args.command == "show":
        read_model = lifecycle.build_read_model(sqlite_path=sqlite_path, package_root=package_root)
        package = next(
            (item for item in read_model["package_summaries"] if item.get("package_id") == args.package_id),
            None,
        )
        if not package:
            _print({"status": "package_not_found", "package_id": args.package_id})
            return 1
        _print({"status": "package_found", "package": package})
        return 0

    if args.command == "dispatch":
        result = lifecycle.record_dispatch(
            args.package_id,
            args.worker,
            args.by,
            args.note,
            sqlite_path=sqlite_path,
            package_root=package_root,
            mark_in_progress=bool(args.in_progress),
        )
        _print(result)
        return 0 if result.get("status") == "dispatch_recorded" else 1

    if args.command == "ingest":
        raw_text = sys.stdin.read() if args.stdin else Path(args.file).read_text(encoding="utf-8")
        result = lifecycle.ingest_worker_result_text(args.package_id, raw_text, sqlite_path=sqlite_path)
        _print(result)
        return 0 if result["package_result"]["status"] != "result_rejected" else 1

    if args.command == "status":
        bridge_root = Path(args.bridge_root) if args.bridge_root else None
        result = lifecycle.export_codex_work_package_lifecycle(
            sqlite_path=sqlite_path,
            package_root=package_root,
            export_root=Path(args.export_root),
            bridge_root=bridge_root,
            wiki_path=Path(args.wiki_path),
        )
        _print(result)
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
