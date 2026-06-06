"""Validate local Codex skill metadata in the active plugin cache.

This is a deterministic preflight for cached skill metadata. The cache is not
source of truth; failing results should be fixed upstream or by refreshing the
cache source, not by treating cache edits as permanent repo repairs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from skill_loader import load_skills
from skill_vetter import DEFAULT_RULESET, vet_skills


DEFAULT_SKILLS_PATH = Path(".codex/plugins/cache")
DEFAULT_INCLUDE_PATTERNS = ("**/SKILL.md",)


def check_skill_metadata(
    skills_path: Path = DEFAULT_SKILLS_PATH,
    *,
    max_description_bytes: int = int(DEFAULT_RULESET["max_description_bytes"]),
    include_patterns: tuple[str, ...] = DEFAULT_INCLUDE_PATTERNS,
) -> dict[str, Any]:
    loaded = load_skills(
        str(skills_path),
        include_patterns=include_patterns,
        strict_mode=False,
    )
    vetted = vet_skills(
        loaded["skills"],
        ruleset={"max_description_bytes": max_description_bytes},
        strict_mode=False,
    )
    too_long = [
        {
            "skill_id": result["skill_id"],
            "reasons": [
                reason
                for reason in result["reasons"]
                if reason["code"] == "DESCRIPTION_TOO_LONG"
            ],
        }
        for result in vetted["results"]
        if any(reason["code"] == "DESCRIPTION_TOO_LONG" for reason in result["reasons"])
    ]
    status = "pass" if not loaded["errors"] and not too_long else "fail"
    return {
        "status": status,
        "skills_path": str(skills_path),
        "max_description_bytes": max_description_bytes,
        "loaded_summary": loaded["summary"],
        "vetter_summary": vetted["summary"],
        "loader_errors": loaded["errors"],
        "description_too_long": too_long,
        "cache_is_source_of_truth": False,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check active Codex skill metadata byte limits.")
    parser.add_argument("--skills-path", "--root", dest="skills_path", type=Path, default=DEFAULT_SKILLS_PATH)
    parser.add_argument("--max-description-bytes", type=int, default=int(DEFAULT_RULESET["max_description_bytes"]))
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument(
        "--no-codex-cache",
        action="store_true",
        help="Compatibility no-op: the checker uses the explicit --root/--skills-path when provided.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    result = check_skill_metadata(
        args.skills_path,
        max_description_bytes=args.max_description_bytes,
    )
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"{result['status']}: checked {result['loaded_summary']['loaded']} skills; "
            f"{len(result['description_too_long'])} over {result['max_description_bytes']} bytes"
        )
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
