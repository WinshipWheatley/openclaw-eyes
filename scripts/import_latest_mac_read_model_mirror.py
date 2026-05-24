#!/usr/bin/env python3
"""Import the latest Mac generated-read-model mirror manifest from E-drive."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from corpus_atlas import stable_json
from generated_read_model_files import (
    MISSION_CONTROL_CAPTURE_INTAKE_READ_MODEL_FILES,
    MISSION_CONTROL_REVIEW_PACKET_READ_MODEL_FILES,
)
from mac_mirror_atlas import format_mac_mirror_report
from read_model_shuttle import (
    DEFAULT_IMPORT_MANIFEST_PATH,
    DEFAULT_RETURNED_MANIFEST_PATH,
    import_mac_read_model_shuttle,
)


CRITICAL_READ_MODEL_FILES = (
    "operator_actions.json",
    "agent_lanes.json",
    "project_capsules.json",
    "report_bridge.json",
    "context_selection.json",
    *MISSION_CONTROL_REVIEW_PACKET_READ_MODEL_FILES,
    *MISSION_CONTROL_CAPTURE_INTAKE_READ_MODEL_FILES,
)


def critical_files_from_manifest(manifest_path: str | Path) -> dict[str, bool]:
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    observed = {
        record.get("relative_path")
        for record in manifest.get("path_records", [])
        if isinstance(record, dict)
    }
    return {name: name in observed for name in CRITICAL_READ_MODEL_FILES}


def import_latest_mac_read_model_mirror(
    *,
    manifest: str | Path = DEFAULT_RETURNED_MANIFEST_PATH,
    db_path: str | Path = DEFAULT_DB_PATH,
    import_manifest_path: str | Path = DEFAULT_IMPORT_MANIFEST_PATH,
    run_id: str | None = None,
) -> dict[str, Any]:
    manifest_path = Path(manifest)
    if not manifest_path.is_file():
        raise RuntimeError(f"Mac generated-read-model manifest does not exist: {manifest_path}")
    critical_files = critical_files_from_manifest(manifest_path)
    result = import_mac_read_model_shuttle(
        manifest=manifest_path,
        db_path=db_path,
        import_manifest_path=import_manifest_path,
        run_id=run_id,
    )
    mirror_report = result.reports["generated_read_model_mirror"]
    mismatch_report = result.reports["mirror_mismatches"]
    mac_roots_report = result.reports["mac_roots"]
    return {
        "import_version": "read_model_mirror_automation_v0",
        "manifest_path": result.manifest_path,
        "copied_manifest_path": result.copied_manifest_path,
        "import_run_id": result.import_run_id,
        "root_id": result.root_id,
        "path_count": result.path_count,
        "hashed_count": result.hashed_count,
        "no_go_count": result.no_go_count,
        "matched_mirror_candidates": result.matched_mirror_candidates,
        "mismatched_mirror_candidates": result.mismatched_mirror_candidates,
        "critical_files": critical_files,
        "generated_read_model_mirror": mirror_report,
        "mirror_mismatches": mismatch_report,
        "mac_roots": mac_roots_report,
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


def format_latest_import_report(payload: dict[str, Any]) -> str:
    critical_lines = [
        f"- {name}: {'present' if present else 'missing'}"
        for name, present in sorted(payload["critical_files"].items())
    ]
    lines = [
        "Latest Mac Read-Model Mirror Import v0",
        "",
        f"Manifest: `{payload['manifest_path']}`",
        f"Copied manifest: `{payload['copied_manifest_path']}`",
        f"Import run: `{payload['import_run_id']}`",
        f"Root: `{payload['root_id']}`",
        f"Paths imported: {payload['path_count']}",
        f"Hashed safe files: {payload['hashed_count']}",
        f"No-go rows: {payload['no_go_count']}",
        f"Mirror matches: {payload['matched_mirror_candidates']}",
        f"Mirror mismatches: {payload['mismatched_mirror_candidates']}",
        "",
        "Critical files:",
        *critical_lines,
        "",
        "Generated read-model mirror:",
        format_mac_mirror_report(payload["generated_read_model_mirror"]),
        "",
        "Mirror mismatches:",
        format_mac_mirror_report(payload["mirror_mismatches"]),
        "",
        "Mac roots:",
        format_mac_mirror_report(payload["mac_roots"]),
        "",
        "Boundary:",
        "- Imported manifest metadata only; no source edits, commits, Mission Control changes, runtime activation, agents, Docker, Ollama, SSH, SCP, rsync, or truth promotion.",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import /mnt/e/openclaw/mac_generated_read_models_manifest.json and report mirror health."
    )
    parser.add_argument(
        "--manifest",
        default=DEFAULT_RETURNED_MANIFEST_PATH.as_posix(),
        help="Returned Mac generated-read-model manifest. Defaults to /mnt/e/openclaw/mac_generated_read_models_manifest.json.",
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument(
        "--import-manifest-path",
        default=DEFAULT_IMPORT_MANIFEST_PATH.as_posix(),
        help="Destination import manifest path.",
    )
    parser.add_argument("--run-id", help="Optional deterministic Corpus Atlas import run id.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = import_latest_mac_read_model_mirror(
        manifest=args.manifest,
        db_path=args.db,
        import_manifest_path=args.import_manifest_path,
        run_id=args.run_id,
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_latest_import_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
