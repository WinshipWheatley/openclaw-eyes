#!/usr/bin/env python3
"""Plan a local bundle blueprint from a pain point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bundle_blueprint_planner import plan_bundle_blueprint, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan a local OpenClaw bundle blueprint.")
    parser.add_argument("--pain-point", required=True, help="Pain point text. Stored only as hash/category in output.")
    parser.add_argument(
        "--target-context",
        choices=("personal", "friend", "company", "client", "internal_test"),
        default="internal_test",
    )
    parser.add_argument("--bundle-name", help="Optional manifest display name.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def _format_operator(manifest: dict) -> str:
    selected = ", ".join(item["module_id"] for item in manifest["selected_modules"]) or "none"
    blocked = ", ".join(item["module_id"] for item in manifest["blocked_modules"]) or "none"
    missing = ", ".join(manifest["missing_modules"]) or "none"
    return "\n".join(
        [
            "Bundle Blueprint Planner v0",
            "",
            f"Bundle: `{manifest['bundle_id']}`",
            f"Target context: `{manifest['target_context']}`",
            f"Category: `{manifest['pain_point_category']}`",
            f"Selected modules: {selected}",
            f"Blocked modules: {blocked}",
            f"Missing modules: {missing}",
            f"Local-only required: `{str(manifest['sensitive_data_policy']['local_only_required']).lower()}`",
            f"GitHub packaging allowed: `{str(manifest['github_packaging_allowed']).lower()}`",
            f"Deployment allowed: `{str(manifest['deployment_allowed']).lower()}`",
            f"Runtime authority: `{str(manifest['runtime_authority']).lower()}`",
            "",
            "Boundary:",
            "- Local planning manifest only; no repo creation, deployment, send, API call, model call, or runtime activation.",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    manifest = plan_bundle_blueprint(
        pain_point=args.pain_point,
        target_context=args.target_context,
        bundle_name=args.bundle_name,
    )
    if args.format == "json":
        print(stable_json(manifest), end="")
    else:
        print(_format_operator(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
