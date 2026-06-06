"""
Validate normalized skill records and emit deterministic per-skill results.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

DEFAULT_RULESET = {
    "min_description_length": 20,
    "max_description_bytes": 1024,
    "min_content_words": 12,
}
VALID_STATUSES = frozenset({"pass", "fail"})


class SkillVetterError(Exception):
    """Raised when vetting fails in strict mode."""

    def __init__(self, message: str, result: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.result = result


def vet_skills(
    skills: list[dict[str, Any]],
    ruleset: dict[str, Any] | None = None,
    strict_mode: bool = False,
) -> dict[str, Any]:
    if not isinstance(skills, list):
        error = _error("INVALID_SKILLS_INPUT", "skills must be provided as a list of normalized skill records")
        output = _result_with_errors([], [error])
        if strict_mode:
            raise SkillVetterError(error["message"], output)
        return output

    if ruleset is not None and not isinstance(ruleset, dict):
        error = _error("INVALID_RULESET", "ruleset must be a JSON object when provided")
        output = _result_with_errors([], [error])
        if strict_mode:
            raise SkillVetterError(error["message"], output)
        return output

    effective_rules = dict(DEFAULT_RULESET)
    if ruleset:
        effective_rules.update(ruleset)
        if "max_description_bytes" not in ruleset and "max_description_length" in ruleset:
            effective_rules["max_description_bytes"] = ruleset["max_description_length"]
    try:
        effective_rules = _normalize_ruleset(effective_rules)
    except SkillVetterError as exc:
        output = _result_with_errors([], [_error("INVALID_RULESET", str(exc))])
        if strict_mode:
            raise SkillVetterError(str(exc), output) from exc
        return output

    results = [_vet_one_skill(index, skill, effective_rules) for index, skill in enumerate(skills)]
    output = _result_with_errors(results, [])
    failed = output["summary"]["failed"]

    if strict_mode and failed > 0:
        raise SkillVetterError(
            f"skill vetting failed for {failed} skill(s)",
            output,
        )

    return output


def _vet_one_skill(index: int, skill: dict[str, Any], ruleset: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(skill, dict):
        skill_id = f"<index:{index}>"
        return {
            "skill_id": skill_id,
            "status": "fail",
            "reasons": [
                _reason(
                    "INVALID_SKILL_RECORD",
                    "skill record must be an object with normalized skill fields",
                )
            ],
        }

    skill_id = str(skill.get("id") or f"<index:{index}>")
    reasons: list[dict[str, str]] = []

    name = _coerce_text(skill.get("name"))
    description = _coerce_text(skill.get("description"))
    content = _coerce_text(skill.get("content"))

    if not skill.get("id"):
        reasons.append(_reason("MISSING_SKILL_ID", "skill is missing id"))
    if not name:
        reasons.append(_reason("MISSING_NAME", "skill is missing name"))
    if not description:
        reasons.append(_reason("MISSING_DESCRIPTION", "skill is missing description"))
    if not content:
        reasons.append(_reason("MISSING_CONTENT", "skill is missing content"))

    if description and len(description) < int(ruleset["min_description_length"]):
        reasons.append(
            _reason(
                "DESCRIPTION_TOO_SHORT",
                f"description must be at least {int(ruleset['min_description_length'])} characters",
            )
        )
    if description and len(description.encode("utf-8")) > int(ruleset["max_description_bytes"]):
        reasons.append(
            _reason(
                "DESCRIPTION_TOO_LONG",
                f"description must be at most {int(ruleset['max_description_bytes'])} UTF-8 bytes",
            )
        )
    if content and len(content.split()) < int(ruleset["min_content_words"]):
        reasons.append(
            _reason(
                "CONTENT_TOO_SHORT",
                f"content must contain at least {int(ruleset['min_content_words'])} words",
            )
        )

    return {
        "skill_id": skill_id,
        "status": "fail" if reasons else "pass",
        "reasons": reasons,
    }


def _reason(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _coerce_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _normalize_ruleset(ruleset: dict[str, Any]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for field_name in ("min_description_length", "max_description_bytes", "min_content_words"):
        raw_value = ruleset.get(field_name, DEFAULT_RULESET[field_name])
        try:
            coerced = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise SkillVetterError(f"{field_name} must be an integer") from exc
        if coerced < 0:
            raise SkillVetterError(f"{field_name} must be >= 0")
        normalized[field_name] = coerced
    return normalized


def _result_with_errors(
    results: list[dict[str, Any]],
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    ordered_results = list(results)
    ordered_errors = sorted(errors, key=lambda error: (error["code"], error["message"]))
    passed = sum(1 for result in ordered_results if result["status"] == "pass")
    failed = sum(1 for result in ordered_results if result["status"] == "fail")

    for result in ordered_results:
        if result["status"] not in VALID_STATUSES:
            raise SkillVetterError(f"unsupported skill status: {result['status']}")

    response = {
        "results": ordered_results,
        "summary": {
            "total": len(ordered_results),
            "passed": passed,
            "failed": failed,
        },
    }
    if ordered_errors:
        response["errors"] = ordered_errors
    return response


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vet normalized skill records.")
    parser.add_argument(
        "skills_json",
        nargs="?",
        help="JSON file containing a skill list or an object with a `skills` field",
    )
    parser.add_argument(
        "--skills-json",
        dest="skills_json_flag",
        help="JSON file containing a skill list or an object with a `skills` field",
    )
    parser.add_argument(
        "--strict",
        dest="strict_mode",
        action="store_true",
        help="Exit with failure if any skill fails vetting.",
    )
    parser.add_argument(
        "--strict-mode",
        dest="strict_mode_value",
        nargs="?",
        const="true",
        help="Explicit strict mode toggle. Accepts true/false.",
    )
    parser.add_argument(
        "--ruleset",
        help="Optional JSON object with ruleset overrides.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    skills_json = args.skills_json_flag or args.skills_json

    if not skills_json:
        raise SystemExit("skill_vetter requires skills_json or --skills-json")

    strict_mode = args.strict_mode or _parse_optional_bool(args.strict_mode_value, flag_name="--strict-mode")

    payload = json.loads(Path(skills_json).read_text(encoding="utf-8"))
    skills = payload["skills"] if isinstance(payload, dict) and "skills" in payload else payload
    ruleset = json.loads(args.ruleset) if args.ruleset else None

    try:
        result = vet_skills(skills=skills, ruleset=ruleset, strict_mode=strict_mode)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except SkillVetterError as exc:
        if exc.result is not None:
            print(json.dumps(exc.result, indent=2, sort_keys=True))
        else:
            print(
                json.dumps(
                    _result_with_errors([], [_error("VETTER_ERROR", str(exc))]),
                    indent=2,
                    sort_keys=True,
                )
            )
        return 1


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
