#!/usr/bin/env python3
"""Check SKILL.md metadata against Codex-compatible limits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CODEX_CURATED_ROOT = Path.home() / ".codex" / "plugins" / "cache" / "openai-curated"
ARTIFACT_VERSION = "skill_metadata_preflight_v0"
DEFAULT_MAX_DESCRIPTION_BYTES = 1024
SKIP_DIRS = frozenset({".git", "__pycache__", ".pytest_cache"})


def stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


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
    max_description_bytes: int = DEFAULT_MAX_DESCRIPTION_BYTES,
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


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check SKILL.md metadata byte limits.")
    parser.add_argument(
        "--root",
        action="append",
        type=Path,
        help="Additional root or SKILL.md file to scan. Can be repeated.",
    )
    parser.add_argument(
        "--codex-curated-root",
        type=Path,
        default=DEFAULT_CODEX_CURATED_ROOT,
        help="Codex curated plugin cache root to scan.",
    )
    parser.add_argument(
        "--no-codex-cache",
        action="store_true",
        help="Only scan explicit roots and the OpenClaw repo root.",
    )
    parser.add_argument(
        "--max-description-bytes",
        type=int,
        default=DEFAULT_MAX_DESCRIPTION_BYTES,
        help="Maximum allowed UTF-8 bytes for frontmatter description.",
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    roots = [ROOT]
    if not args.no_codex_cache:
        roots.append(args.codex_curated_root)
    if args.root:
        roots.extend(args.root)

    report = build_skill_metadata_report(
        roots=roots,
        max_description_bytes=args.max_description_bytes,
    )
    if args.format == "json":
        print(stable_json(report), end="")
    else:
        print(format_operator_report(report))
    return 1 if report["issue_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
