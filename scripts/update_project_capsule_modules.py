#!/usr/bin/env python3
"""Select planning-safe modules for a Project Capsule v0 row."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from module_registry import build_module_registry_report, seed_module_registry, stable_json
from project_capsule import (
    DEFAULT_SELECTED_MODULES,
    DEMO_PROJECT_ID,
    create_demo_project_capsule,
    format_project_capsule_detail,
    get_project_capsule,
    link_project_capsule_modules,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select Project Capsule v0 planning-safe modules.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--project-id", default=DEMO_PROJECT_ID, help="Project capsule id.")
    parser.add_argument("--ensure-demo", action="store_true", help="Create demo capsule before linking.")
    parser.add_argument("--module", action="append", dest="modules", help="Module id to select. May repeat.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.ensure_demo:
        create_demo_project_capsule(db_path=args.db)
    seed_module_registry(db_path=args.db)
    selected = tuple(args.modules) if args.modules else DEFAULT_SELECTED_MODULES
    result = link_project_capsule_modules(
        db_path=args.db,
        project_id=args.project_id,
        module_ids=selected,
    )
    capsule = get_project_capsule(db_path=args.db, project_id=args.project_id)
    module_report = build_module_registry_report(db_path=args.db, section="dependencies")
    payload = {
        "project_id": result.project_id,
        "selected_module_count": result.selected_module_count,
        "runtime_authority": result.runtime_authority,
        "activation_count": result.activation_count,
        "selected_modules": capsule["modules"] if capsule else [],
        "module_dependencies": module_report.get("dependencies", []),
    }
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_project_capsule_detail(capsule))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
