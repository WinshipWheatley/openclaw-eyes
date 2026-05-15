#!/usr/bin/env python3
"""Build a Sync Health ledger snapshot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from sync_health import build_sync_health_snapshot, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Sync Health snapshot.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--manifest", help="Mac generated read-model manifest path.")
    parser.add_argument("--read-model-root", help="Canonical generated read-model root.")
    parser.add_argument("--repo-root", help="Backend repo root for relative generated read-model paths.")
    parser.add_argument("--mac-status", help="Mac sync heartbeat/status marker path.")
    parser.add_argument("--mac-completion", help="Mac sync completion marker path.")
    parser.add_argument("--pc-state", help="PC import agent state path.")
    parser.add_argument("--pc-log", help="PC import task log path.")
    parser.add_argument("--windows-log", help="Windows-side scheduled task log path.")
    parser.add_argument("--request-marker", help="Bounded Mac sync request marker path.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    kwargs = {
        "db_path": args.db,
    }
    optional_paths = {
        "manifest_path": args.manifest,
        "read_model_root": args.read_model_root,
        "repo_root": args.repo_root,
        "mac_status_path": args.mac_status,
        "mac_completion_path": args.mac_completion,
        "pc_import_state_path": args.pc_state,
        "pc_task_log_path": args.pc_log,
        "windows_task_log_path": args.windows_log,
        "request_marker_path": args.request_marker,
    }
    kwargs.update({key: value for key, value in optional_paths.items() if value})
    result = build_sync_health_snapshot(**kwargs)
    payload = {
        "status": "ok",
        "run_id": result.run_id,
        "snapshot_id": result.snapshot_id,
        "trust_status": result.trust_status,
        "mirror_status": result.mirror_status,
        "recommended_fix_kind": result.recommended_fix_kind,
        "db_path": result.db_path,
    }
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print("Sync Health Build v0")
        print("")
        print(f"Run: `{result.run_id}`")
        print(f"Snapshot: `{result.snapshot_id}`")
        print(f"Trust status: `{result.trust_status}`")
        print(f"Mirror status: `{result.mirror_status}`")
        print(f"Recommended fix: `{result.recommended_fix_kind}`")
        print("")
        print("Boundary:")
        print("- Snapshot only; no remote control, arbitrary command, file move/delete, Mission Control change, or sync authority expansion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
