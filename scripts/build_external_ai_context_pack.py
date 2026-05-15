#!/usr/bin/env python3
"""Build External AI Context Packager v0 source packs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from external_ai_context_packager import (
    DEFAULT_PACK_ID,
    SUPPORTED_PROFILES,
    build_external_ai_context_pack,
    format_build_result,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an External AI Context Pack v0.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--profile", choices=tuple(sorted(SUPPORTED_PROFILES)), default="chatgpt_project")
    parser.add_argument("--world", default="build", help="World/domain focus.")
    parser.add_argument("--focus", default=DEFAULT_PACK_ID, help="Task focus / pack id.")
    parser.add_argument("--export-root", default="generated/context_packs", help="Context pack export root.")
    parser.add_argument("--read-model-root", default="generated/read_models", help="Generated read-model source root.")
    parser.add_argument("--run-id", help="Optional deterministic run id.")
    parser.add_argument("--no-zip", action="store_true", help="Do not create local ZIP archive.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_external_ai_context_pack(
        db_path=args.db,
        profile=args.profile,
        world=args.world,
        focus=args.focus,
        export_root=args.export_root,
        read_model_root=args.read_model_root,
        create_zip=not args.no_zip,
        run_id=args.run_id,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(format_build_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
