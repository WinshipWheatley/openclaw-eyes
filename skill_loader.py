"""
Load skill definition files and return deterministic normalized records.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import fnmatch
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Sequence

import yaml

DEFAULT_INCLUDE_PATTERNS = ("*.md", "SKILL.md", "**/SKILL.md")
DEFAULT_EXCLUDE_PATTERNS: tuple[str, ...] = ()
REQUIRED_FIELDS = ("name", "description", "content")
DEFAULT_CATALOG_PATH = Path("/home/openclaw/system_catalog.sqlite3")
VALID_SKILL_AUTHORITIES = frozenset({"advisory_only", "references_gated_action"})
REQUIRED_RUNTIME_FIELDS = (
    "owner_agent",
    "triggers",
    "tools",
    "authority",
    "capability_needed",
    "tiers",
)
REQUIRED_TIERS = ("simple", "rich")

_SKILLS_SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
    skill_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    owner_agent TEXT NOT NULL,
    triggers_json TEXT NOT NULL,
    tools_json TEXT NOT NULL,
    authority TEXT NOT NULL,
    capability_needed TEXT NOT NULL,
    tiers_json TEXT NOT NULL,
    tier_simple TEXT NOT NULL,
    tier_rich TEXT NOT NULL,
    source_path TEXT NOT NULL,
    content TEXT NOT NULL,
    validation_status TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_skills_owner_agent ON skills(owner_agent);
CREATE INDEX IF NOT EXISTS idx_skills_authority ON skills(authority);
"""


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
    catalog_path: str | Path | None = None,
    persist_catalog: bool = False,
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

    result = _build_result(skills, errors, skipped)
    if catalog_path is None and not persist_catalog:
        return result

    resolved_catalog_path = Path(catalog_path or DEFAULT_CATALOG_PATH).expanduser()
    runtime_errors = _runtime_validation_errors(skills, catalog_path=resolved_catalog_path)
    runtime_failed_paths = {
        error["path"]
        for error in runtime_errors
        if error.get("path") and not str(error.get("path")).startswith("<")
    }
    runtime_failed_count = len(runtime_failed_paths) or len(runtime_errors)
    catalog_written = 0
    if runtime_errors:
        result = _build_result(skills, [*errors, *runtime_errors], skipped)
        result["catalog_path"] = resolved_catalog_path.as_posix()
        result["summary"]["runtime_validation_failed"] = runtime_failed_count
        result["summary"]["catalog_written"] = 0
        if strict_mode:
            first_reason = runtime_errors[0]["reason"]
            raise SkillLoaderError(
                f"skill runtime validation failed for {runtime_failed_count} skill(s): {first_reason}",
                result,
            )
        return result

    if persist_catalog:
        catalog_written = persist_skills_catalog(skills, catalog_path=resolved_catalog_path)

    result["catalog_path"] = resolved_catalog_path.as_posix()
    result["summary"]["runtime_validation_failed"] = 0
    result["summary"]["catalog_written"] = catalog_written
    return result


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


def _skill_metadata(skill: dict[str, Any]) -> dict[str, Any]:
    metadata = skill.get("metadata")
    return dict(metadata) if isinstance(metadata, dict) else {}


def _coerce_text_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _coerce_tiers(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        tier: str(value.get(tier) or "").strip()
        for tier in REQUIRED_TIERS
        if str(value.get(tier) or "").strip()
    }


def _runtime_record(skill: dict[str, Any]) -> dict[str, Any]:
    metadata = _skill_metadata(skill)
    return {
        "skill_id": str(skill.get("id") or "").strip(),
        "name": str(skill.get("name") or "").strip(),
        "description": str(skill.get("description") or "").strip(),
        "source_path": str(skill.get("source_path") or "").strip(),
        "content": str(skill.get("content") or "").strip(),
        "owner_agent": str(metadata.get("owner_agent") or "").strip().lower(),
        "triggers": _coerce_text_list(metadata.get("triggers")),
        "tools": _coerce_text_list(metadata.get("tools")),
        "authority": str(metadata.get("authority") or "").strip(),
        "capability_needed": str(metadata.get("capability_needed") or "").strip(),
        "tiers": _coerce_tiers(metadata.get("tiers")),
    }


def _valid_owner_agents(catalog_path: Path | None = None) -> set[str]:
    valid: set[str] = set()
    try:
        from agent_lane_registry import DEFAULT_AGENT_LANE_SEEDS

        valid.update(seed.agent_id.lower() for seed in DEFAULT_AGENT_LANE_SEEDS)
    except Exception:
        pass

    if catalog_path and catalog_path.exists():
        con: sqlite3.Connection | None = None
        try:
            con = sqlite3.connect(f"file:{catalog_path.as_posix()}?mode=ro", uri=True)
            rows = con.execute("SELECT agent_id FROM agent_lanes").fetchall()
            valid.update(str(row[0]).lower() for row in rows if row and row[0])
        except sqlite3.Error:
            pass
        finally:
            if con is not None:
                con.close()
    return valid


def _valid_runtime_tools() -> set[str]:
    valid: set[str] = set()
    try:
        from openclaw_system_knowledge_registry import ORBIT_BRAIN_ROUTE_RECORDS

        valid.update(
            str(record.get("brain_id") or "").strip()
            for record in ORBIT_BRAIN_ROUTE_RECORDS
            if str(record.get("brain_id") or "").strip()
        )
    except Exception:
        pass

    read_model_root = Path("generated/read_models")
    if read_model_root.exists():
        for path in read_model_root.glob("*.json"):
            valid.add(path.name)
            valid.add(path.stem)
    return valid


def _runtime_validation_errors(
    skills: list[dict[str, Any]],
    *,
    catalog_path: Path | None,
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    owner_agents = _valid_owner_agents(catalog_path)
    tools = _valid_runtime_tools()

    try:
        from skill_vetter import vet_skills

        vetting = vet_skills(skills, strict_mode=False)
        for result in vetting.get("results", []):
            if result.get("status") == "fail":
                reasons = ",".join(str(reason.get("code") or "") for reason in result.get("reasons", []))
                errors.append({
                    "path": str(result.get("skill_id") or "<unknown>"),
                    "reason": f"VETTER_FAILED:{reasons}",
                })
    except Exception as exc:
        errors.append({"path": "<skill_vetter>", "reason": f"VETTER_ERROR:{type(exc).__name__}"})

    for skill in skills:
        record = _runtime_record(skill)
        missing = [
            field
            for field in REQUIRED_RUNTIME_FIELDS
            if not record.get(field)
        ]
        if missing:
            errors.append({
                "path": record["source_path"] or record["skill_id"] or "<unknown>",
                "reason": f"MISSING_RUNTIME_FIELDS:{','.join(missing)}",
            })
            continue

        missing_tiers = [tier for tier in REQUIRED_TIERS if not record["tiers"].get(tier)]
        if missing_tiers:
            errors.append({
                "path": record["source_path"] or record["skill_id"],
                "reason": f"MISSING_TIERS:{','.join(missing_tiers)}",
            })

        if record["authority"] not in VALID_SKILL_AUTHORITIES:
            errors.append({
                "path": record["source_path"] or record["skill_id"],
                "reason": f"INVALID_AUTHORITY:{record['authority']}",
            })

        if record["owner_agent"] not in owner_agents:
            errors.append({
                "path": record["source_path"] or record["skill_id"],
                "reason": f"UNKNOWN_OWNER_AGENT:{record['owner_agent']}",
            })

        unknown_tools = [tool for tool in record["tools"] if tool not in tools]
        if unknown_tools:
            errors.append({
                "path": record["source_path"] or record["skill_id"],
                "reason": f"UNKNOWN_TOOL:{','.join(sorted(unknown_tools))}",
            })

    return sorted(errors, key=lambda error: (error["path"], error["reason"]))


def init_skills_catalog_schema(con: sqlite3.Connection) -> None:
    con.executescript(_SKILLS_SCHEMA)


def persist_skills_catalog(
    skills: list[dict[str, Any]],
    *,
    catalog_path: str | Path = DEFAULT_CATALOG_PATH,
) -> int:
    target = Path(catalog_path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(target)
    try:
        init_skills_catalog_schema(con)
        updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        written = 0
        for skill in skills:
            record = _runtime_record(skill)
            tiers_json = json.dumps(record["tiers"], sort_keys=True, ensure_ascii=True)
            triggers_json = json.dumps(record["triggers"], sort_keys=True, ensure_ascii=True)
            tools_json = json.dumps(record["tools"], sort_keys=True, ensure_ascii=True)
            con.execute(
                """INSERT OR REPLACE INTO skills(
                       skill_id, name, description, owner_agent, triggers_json,
                       tools_json, authority, capability_needed, tiers_json,
                       tier_simple, tier_rich, source_path, content,
                       validation_status, updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record["skill_id"],
                    record["name"],
                    record["description"],
                    record["owner_agent"],
                    triggers_json,
                    tools_json,
                    record["authority"],
                    record["capability_needed"],
                    tiers_json,
                    record["tiers"]["simple"],
                    record["tiers"]["rich"],
                    record["source_path"],
                    record["content"],
                    "pass",
                    updated_at,
                ),
            )
            written += 1
        con.commit()
        return written
    finally:
        con.close()


def load_registered_skills(catalog_path: str | Path = DEFAULT_CATALOG_PATH) -> list[dict[str, Any]]:
    target = Path(catalog_path).expanduser()
    if not target.exists():
        return []
    con: sqlite3.Connection | None = None
    try:
        con = sqlite3.connect(f"file:{target.as_posix()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """SELECT skill_id, name, description, owner_agent, triggers_json, tools_json,
                      authority, capability_needed, tiers_json, source_path, content,
                      validation_status, updated_at
               FROM skills
               WHERE validation_status = 'pass'
               ORDER BY skill_id"""
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        if con is not None:
            con.close()

    skills: list[dict[str, Any]] = []
    for row in rows:
        try:
            triggers = json.loads(row["triggers_json"] or "[]")
            tools = json.loads(row["tools_json"] or "[]")
            tiers = json.loads(row["tiers_json"] or "{}")
        except json.JSONDecodeError:
            continue
        skills.append(
            {
                "skill_id": row["skill_id"],
                "id": row["skill_id"],
                "name": row["name"],
                "description": row["description"],
                "owner_agent": row["owner_agent"],
                "triggers": triggers if isinstance(triggers, list) else [],
                "tools": tools if isinstance(tools, list) else [],
                "authority": row["authority"],
                "capability_needed": row["capability_needed"],
                "tiers": tiers if isinstance(tiers, dict) else {},
                "source_path": row["source_path"],
                "content": row["content"],
                "validation_status": row["validation_status"],
                "updated_at": row["updated_at"],
            }
        )
    return skills


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
    parser.add_argument(
        "--catalog-path",
        default=None,
        help="SQLite system catalog path for invocable skill validation/persistence.",
    )
    parser.add_argument(
        "--persist-catalog",
        "--write-catalog",
        dest="persist_catalog",
        action="store_true",
        help="Persist validated invocable skill records to the system catalog skills table.",
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
            catalog_path=args.catalog_path,
            persist_catalog=args.persist_catalog,
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
