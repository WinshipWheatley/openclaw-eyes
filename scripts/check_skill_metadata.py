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

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from skill_loader import load_skills
from skill_vetter import DEFAULT_RULESET, vet_skills


DEFAULT_SKILLS_PATH = Path(".codex/plugins/cache")
DEFAULT_INCLUDE_PATTERNS = ("**/SKILL.md",)
ARTIFACT_VERSION = "skill_metadata_preflight_v0"
SKIP_DIRS = frozenset({".git", "__pycache__", ".pytest_cache"})


def find_skill_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.name == "SKILL.md" else []

    skill_files: list[Path] = []
    for path in root.rglob("SKILL.md"):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            skill_files.append(path)
    return sorted(skill_files)


def _parse_frontmatter(path: Path) -> tuple[dict[str, Any], str | None]:
    content = path.read_text(encoding="utf-8")
    if content.startswith("\ufeff"):
        content = content.lstrip("\ufeff")
    if not content.startswith("---"):
        return {}, "missing frontmatter"

    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, "missing frontmatter"

    closing_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        return {}, "unterminated frontmatter"

    try:
        parsed = yaml.safe_load("".join(lines[1:closing_index])) or {}
    except yaml.YAMLError as exc:
        return {}, str(exc).splitlines()[0]
    if not isinstance(parsed, dict):
        return {}, "frontmatter must be a mapping"
    return parsed, None


def _path_for_report(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _issue(path: Path, code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {
        "path": _path_for_report(path),
        "code": code,
        "message": message,
        **extra,
    }


def check_skill_file(path: Path, max_description_bytes: int) -> dict[str, Any] | None:
    try:
        frontmatter, parse_error = _parse_frontmatter(path)
    except OSError as exc:
        return _issue(path, "READ_ERROR", f"failed to read SKILL.md: {exc}")

    if parse_error:
        return _issue(path, "INVALID_FRONTMATTER", f"invalid frontmatter: {parse_error}")

    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        return _issue(path, "MISSING_DESCRIPTION", "description is required")

    description_bytes = len(description.encode("utf-8"))
    if description_bytes > max_description_bytes:
        return _issue(
            path,
            "DESCRIPTION_TOO_LONG",
            f"description is {description_bytes} UTF-8 bytes; max is {max_description_bytes}",
            description_bytes=description_bytes,
            max_description_bytes=max_description_bytes,
        )
    return None


def build_skill_metadata_report(
    roots: list[Path],
    max_description_bytes: int = int(DEFAULT_RULESET["max_description_bytes"]),
) -> dict[str, Any]:
    scanned_roots: list[str] = []
    skipped_roots: list[str] = []
    issues: list[dict[str, Any]] = []
    scanned_skill_files = 0

    for root in roots:
        expanded = root.expanduser().resolve()
        if not expanded.exists():
            skipped_roots.append(expanded.as_posix())
            continue
        scanned_roots.append(expanded.as_posix())
        for skill_file in find_skill_files(expanded):
            scanned_skill_files += 1
            issue = check_skill_file(skill_file, max_description_bytes=max_description_bytes)
            if issue:
                issues.append(issue)

    return {
        "artifact_version": ARTIFACT_VERSION,
        "max_description_bytes": max_description_bytes,
        "scanned_roots": scanned_roots,
        "skipped_roots": skipped_roots,
        "scanned_skill_files": scanned_skill_files,
        "issue_count": len(issues),
        "issues": sorted(issues, key=lambda item: (item["path"], item["code"])),
    }


def format_operator_report(report: dict[str, Any]) -> str:
    lines = [
        "Skill Metadata Preflight",
        "",
        "Evidence:",
        (
            f"- Scanned {report['scanned_skill_files']} SKILL.md files across "
            f"{len(report['scanned_roots'])} existing roots."
        ),
        f"- Description ceiling: {report['max_description_bytes']} UTF-8 bytes.",
    ]
    if report["skipped_roots"]:
        lines.append(f"- Skipped missing roots: {len(report['skipped_roots'])}.")

    if report["issue_count"] == 0:
        lines.extend(["", "PASS: no invalid skill metadata found."])
        return "\n".join(lines)

    lines.extend(["", "FAIL: invalid skill metadata found."])
    for issue in report["issues"]:
        lines.append(f"- {issue['path']}: {issue['code']} - {issue['message']}")
    return "\n".join(lines)


def check_skill_metadata(
    skills_path: Path = DEFAULT_SKILLS_PATH,
    *,
    max_description_bytes: int = int(DEFAULT_RULESET["max_description_bytes"]),
    include_patterns: tuple[str, ...] = DEFAULT_INCLUDE_PATTERNS,
) -> dict[str, Any]:
    raw_report = build_skill_metadata_report([skills_path], max_description_bytes=max_description_bytes)
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
    raw_description_issues = [
        issue for issue in raw_report["issues"] if issue["code"] == "DESCRIPTION_TOO_LONG"
    ]
    status = "pass" if not loaded["errors"] and not too_long and not raw_report["issues"] else "fail"
    return {
        "status": status,
        "skills_path": str(skills_path),
        "max_description_bytes": max_description_bytes,
        "loaded_summary": loaded["summary"],
        "vetter_summary": vetted["summary"],
        "loader_errors": loaded["errors"],
        "description_too_long": too_long,
        "raw_frontmatter_report": raw_report,
        "raw_description_issues": raw_description_issues,
        "description_issue_count": max(len(too_long), len(raw_description_issues)),
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
            f"{result['description_issue_count']} over {result['max_description_bytes']} bytes"
        )
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
