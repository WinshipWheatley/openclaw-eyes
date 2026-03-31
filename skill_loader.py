"""
Load skill definition files and return deterministic normalized records.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
import fnmatch
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

DEFAULT_INCLUDE_PATTERNS = ("*.md", "SKILL.md", "**/SKILL.md")
DEFAULT_EXCLUDE_PATTERNS: tuple[str, ...] = ()
REQUIRED_FIELDS = ("name", "description", "content")


class SkillLoaderError(Exception):
    """Raised when skill loading fails in strict mode."""

    def __init__(self, message: str, result: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.result = result


def _sort_mapping(value: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key in sorted(value):
        item = value[key]
        if isinstance(item, dict):
            normalized[key] = _sort_mapping(item)
            continue
        if isinstance(item, list):
            normalized[key] = [_normalize_metadata_value(entry) for entry in item]
            continue
        normalized[key] = _normalize_metadata_value(item)
    return normalized


def _normalize_metadata_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _sort_mapping(value)
    if isinstance(value, list):
        return [_normalize_metadata_value(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def load_skills(
    skills_path: str,
    include_patterns: Iterable[str] | None = None,
    exclude_patterns: Iterable[str] | None = None,
    strict_mode: bool = False,
) -> dict[str, Any]:
    """
    Load skill definition files from a directory or a single file.

    Returns a structured result with `skills`, `errors`, and `summary`.
    In strict mode, invalid files still produce a full deterministic error set,
    but the overall run exits via SkillLoaderError.
    """

    root = Path(skills_path).expanduser().resolve()
    include = _normalize_patterns(include_patterns, DEFAULT_INCLUDE_PATTERNS)
    exclude = _normalize_patterns(exclude_patterns, DEFAULT_EXCLUDE_PATTERNS)

    if not root.exists():
        error = {
            "path": str(root),
            "reason": f"skills_path does not exist: {root}",
        }
        if strict_mode:
            raise SkillLoaderError(error["reason"], _result_with_error(error))
        return _result_with_error(error)

    candidates, skipped = _collect_candidate_files(root, include, exclude)
    skills: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for candidate, relative_path in candidates:
        try:
            skills.append(_load_skill_file(candidate, relative_path))
        except SkillLoaderError as exc:
            errors.append({"path": relative_path, "reason": str(exc)})

    if strict_mode and errors:
        first_reason = errors[0]["reason"]
        raise SkillLoaderError(
            f"skill loading failed for {len(errors)} file(s): {first_reason}",
            _build_result(skills, errors, skipped),
        )

    return _build_result(skills, errors, skipped)


def _normalize_patterns(
    patterns: Iterable[str] | None,
    default_patterns: tuple[str, ...],
) -> tuple[str, ...]:
    if patterns is None:
        return default_patterns

    normalized = tuple(pattern.strip() for pattern in patterns if pattern and pattern.strip())
    if normalized:
        return normalized
    if default_patterns:
        return default_patterns
    return ()


def _collect_candidate_files(
    root: Path,
    include_patterns: tuple[str, ...],
    exclude_patterns: tuple[str, ...],
) -> tuple[list[tuple[Path, str]], int]:
    if root.is_file():
        relative_path = Path(root.name)
        if _matches_any(relative_path, include_patterns) and not _matches_any(relative_path, exclude_patterns):
            return [(root, relative_path.as_posix())], 0
        return [], 1

    included: list[tuple[Path, Path]] = []
    for pattern in include_patterns:
        for match in root.glob(pattern):
            if not match.is_file():
                continue
            relative = match.relative_to(root)
            resolved = match.resolve()
            included.append((resolved, relative))

    deduped_candidates: dict[Path, Path] = {}
    for resolved, relative in included:
        deduped_candidates[relative] = resolved

    kept = [
        (resolved, relative.as_posix())
        for relative, resolved in sorted(deduped_candidates.items(), key=lambda item: item[0].as_posix())
        if not _matches_any(relative, exclude_patterns)
    ]
    skipped = len(deduped_candidates) - len(kept)
    return kept, skipped


def _matches_any(path: Path, patterns: tuple[str, ...]) -> bool:
    posix_path = path.as_posix()
    for pattern in patterns:
        normalized_pattern = pattern.strip()
        fallback_pattern = normalized_pattern[3:] if normalized_pattern.startswith("**/") else normalized_pattern

        if (
            path.match(normalized_pattern)
            or path.match(fallback_pattern)
            or fnmatch.fnmatch(posix_path, normalized_pattern)
            or fnmatch.fnmatch(posix_path, fallback_pattern)
            or fnmatch.fnmatch(path.name, normalized_pattern)
            or fnmatch.fnmatch(path.name, fallback_pattern)
        ):
            return True
    return False


def _load_skill_file(file_path: Path, relative_path: str) -> dict[str, Any]:
    try:
        raw_content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkillLoaderError(f"failed to read file: {exc}") from exc

    frontmatter, body, parse_error = _parse_frontmatter(raw_content)
    if parse_error:
        raise SkillLoaderError(f"invalid frontmatter: {parse_error}")

    name = _coerce_required_text(frontmatter.get("name"))
    description = _coerce_required_text(frontmatter.get("description"))
    content = body.strip()

    field_values = {
        "name": name,
        "description": description,
        "content": content,
    }
    missing_fields = [field_name for field_name in REQUIRED_FIELDS if not field_values[field_name]]
    if missing_fields:
        raise SkillLoaderError(f"missing required fields: {', '.join(missing_fields)}")

    skill = {
        "id": _generate_skill_id(relative_path, frontmatter),
        "name": name,
        "description": description,
        "source_path": relative_path,
        "content": content,
    }

    metadata = {
        key: value
        for key, value in frontmatter.items()
        if key not in frozenset({"id", "name", "description"})
    }
    if metadata:
        skill["metadata"] = _sort_mapping(metadata)

    return skill


def _coerce_required_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str, str | None]:
    if content.startswith("\ufeff"):
        content = content.lstrip("\ufeff")

    if not content.startswith("---"):
        return {}, content, None

    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, content, None

    closing_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing_index = index
            break

    if closing_index is None:
        return {}, content, "unterminated frontmatter"

    frontmatter_block = "\n".join(lines[1:closing_index])
    body = "\n".join(lines[closing_index + 1 :])

    try:
        parsed = yaml.safe_load(frontmatter_block) or {}
        if not isinstance(parsed, dict):
            return {}, content, "frontmatter must be a mapping"
        return parsed, body, None
    except yaml.YAMLError as exc:
        return {}, content, str(exc).splitlines()[0]


def _generate_skill_id(relative_path: str, frontmatter: dict[str, Any]) -> str:
    explicit_id = frontmatter.get("id")
    if explicit_id is not None:
        normalized_id = str(explicit_id).strip()
        if normalized_id:
            return normalized_id
    return Path(relative_path).with_suffix("").as_posix().replace("/", ".").strip(".")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load and validate skill definition files.")
    parser.add_argument("skills_path", nargs="?", help="Root directory or file path to scan for skills")
    parser.add_argument("--skills-path", dest="skills_path_flag", help="Root directory or file path to scan for skills")
    parser.add_argument(
        "--include",
        "--include-patterns",
        dest="include_patterns",
        action="append",
        help="Glob pattern to include. Can be repeated.",
    )
    parser.add_argument(
        "--exclude",
        "--exclude-patterns",
        dest="exclude_patterns",
        action="append",
        help="Glob pattern to exclude. Can be repeated.",
    )
    parser.add_argument(
        "--strict",
        dest="strict_mode",
        action="store_true",
        help="Exit with failure if any invalid skill is found.",
    )
    parser.add_argument(
        "--strict-mode",
        dest="strict_mode_value",
        nargs="?",
        const="true",
        help="Explicit strict mode toggle. Accepts true/false.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    skills_path = args.skills_path_flag or args.skills_path
    if not skills_path:
        raise SystemExit("skill_loader requires skills_path or --skills-path")

    strict_mode = args.strict_mode or _parse_optional_bool(args.strict_mode_value, flag_name="--strict-mode")

    try:
        result = load_skills(
            skills_path,
            include_patterns=args.include_patterns,
            exclude_patterns=args.exclude_patterns,
            strict_mode=strict_mode,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except SkillLoaderError as exc:
        if exc.result is not None:
            print(json.dumps(exc.result, indent=2, sort_keys=True))
        else:
            print(
                json.dumps(
                    _result_with_error({"path": skills_path, "reason": str(exc)}),
                    indent=2,
                    sort_keys=True,
                )
            )
        return 1


def _build_result(
    skills: list[dict[str, Any]],
    errors: list[dict[str, str]],
    skipped: int,
) -> dict[str, Any]:
    ordered_skills = sorted(skills, key=lambda skill: skill["source_path"])
    ordered_errors = sorted(errors, key=lambda error: (error["path"], error["reason"]))
    return {
        "skills": ordered_skills,
        "errors": ordered_errors,
        "summary": {
            "loaded": len(ordered_skills),
            "failed": len(ordered_errors),
            "skipped": skipped,
        },
    }


def _result_with_error(error: dict[str, str]) -> dict[str, Any]:
    return _build_result([], [error], 0)


def _parse_optional_bool(value: str | None, flag_name: str) -> bool:
    if value is None:
        return False

    normalized = value.strip().lower()
    if normalized in frozenset({"true", "1", "yes", "y", "on", "t"}):
        return True
    if normalized in frozenset({"false", "0", "no", "n", "off", "f"}):
        return False
    raise SystemExit(f"{flag_name} must be one of: true, false, 1, 0, yes, no, on, off")


if __name__ == "__main__":
    raise SystemExit(main())
