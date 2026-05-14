#!/usr/bin/env python3
"""Import a returned Mac read-model shuttle manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from corpus_atlas import stable_json
from read_model_shuttle import (
    DEFAULT_IMPORT_MANIFEST_PATH,
    format_import_result,
    import_mac_read_model_shuttle,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import a returned Mac generated-read-model shuttle manifest."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--manifest", help="Returned mac_generated_read_models_manifest.json path.")
    group.add_argument("--package", help="Returned package folder containing the manifest.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument(
        "--import-manifest-path",
        default=DEFAULT_IMPORT_MANIFEST_PATH.as_posix(),
        help="Destination import manifest path.",
    )
    parser.add_argument("--run-id", help="Optional deterministic Corpus Atlas import run id.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = import_mac_read_model_shuttle(
        manifest=args.manifest,
        package=args.package,
        db_path=args.db,
        import_manifest_path=args.import_manifest_path,
        run_id=args.run_id,
    )
    payload = {
        "manifest_path": result.manifest_path,
        "copied_manifest_path": result.copied_manifest_path,
        "import_run_id": result.import_run_id,
        "root_id": result.root_id,
        "path_count": result.path_count,
        "hashed_count": result.hashed_count,
        "no_go_count": result.no_go_count,
        "matched_mirror_candidates": result.matched_mirror_candidates,
        "mismatched_mirror_candidates": result.mismatched_mirror_candidates,
        "reports": result.reports,
        "raw_file_bodies_imported": False,
        "canonical_truth_promoted": False,
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
        print(format_import_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
