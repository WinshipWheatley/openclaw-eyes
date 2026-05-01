from __future__ import annotations

"""Deterministic local-only review bundles for expert approval packets."""

import re
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from expert_approval_packet import (
    EXPERT_APPROVAL_PACKET_SCHEMA_VERSION,
    EXPERT_APPROVAL_PACKET_TYPE,
    FORBIDDEN_ACTIONS,
    PROTECTED_DATA_MARKERS,
    REQUIRED_HUMAN_ACKNOWLEDGEMENTS,
)


EXPERT_APPROVAL_REVIEW_BUNDLE_SCHEMA_VERSION = 1
EXPERT_APPROVAL_REVIEW_BUNDLE_TYPE = "external_expert.approval_review_bundle"

_SUMMARY_LIMIT = 360
_TITLE_LIMIT = 120
_STAGED_SUMMARY_LIMIT = 240
_TEXT_VALUE_LIMIT = 240
_LIST_LIMIT = 16
_AUDIT_REF_KEY_LIMIT = 24
_MARKDOWN_LIMIT = 3600
_SAFE_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,240}$")
_MONEY_AMOUNT_PATTERN = re.compile(
    r"\$\s*\d|\b\d+(?:\.\d+)?\s*(?:dollars?|usd|bucks?)\b",
    re.IGNORECASE,
)
_ABSOLUTE_PATH_PATTERN = re.compile(r"(?:^|\s)(?:/home/openclaw|/mnt/c|~[/\\])", re.IGNORECASE)
_TELEGRAM_BOT_TOKEN_PATTERN = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")
_SHA256_HASH_PATTERN = re.compile(r"sha256:[0-9a-fA-F]{32,}")

_NEXT_ALLOWED_READY = "manual_operator_review_and_acknowledgement"
_NEXT_ALLOWED_REPAIR = "repair_approval_packet_and_rerun_checks"
_REDACTED_TEXT = "Redacted pending sanitized approval packet repair."


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def _string_list(value: object, *, limit: int = _LIST_LIMIT) -> list[str]:
    items = [str(item).strip() for item in _as_list(value) if str(item).strip()]
    return items[:limit]


def _unique_violations(violations: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(violation for violation in violations if violation))


def _bounded_text(value: object, *, limit: int, fallback: str) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        text = fallback
    if _text_has_private_marker(text):
        text = _REDACTED_TEXT
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _text_has_private_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in PROTECTED_DATA_MARKERS) or bool(
        _MONEY_AMOUNT_PATTERN.search(value)
        or _ABSOLUTE_PATH_PATTERN.search(value)
        or _TELEGRAM_BOT_TOKEN_PATTERN.search(value)
    )


def _protected_text_violations(value: str) -> list[str]:
    violations: list[str] = []
    lowered = value.lower()
    for marker in sorted(PROTECTED_DATA_MARKERS, key=len, reverse=True):
        if marker in lowered:
            violations.append(f"protected_marker:{marker}")
    if _MONEY_AMOUNT_PATTERN.search(value):
        violations.append("protected_pattern:money_amount")
    if _ABSOLUTE_PATH_PATTERN.search(value):
        violations.append("absolute_private_path")
    if _TELEGRAM_BOT_TOKEN_PATTERN.search(value):
        violations.append("telegram_bot_token")
    return violations


def _approval_check_violations(approval_packet: Mapping[str, Any]) -> list[str]:
    check_payload = approval_packet.get("approval_packet_check")
    if not isinstance(check_payload, Mapping):
        return ["missing_approval_packet_check"]
    if check_payload.get("passed") is True:
        return []
    return ["approval_packet_check_failed"] + _string_list(check_payload.get("violations"), limit=32)


def _unsafe_ref(value: str) -> bool:
    return (
        not value
        or value.startswith(("/", "~"))
        or "\\" in value
        or ".." in value.split("/")
        or not _SAFE_REF_PATTERN.fullmatch(value)
    )


def _packet_violations(approval_packet: Mapping[str, Any] | object) -> list[str]:
    if not isinstance(approval_packet, Mapping):
        return ["approval_packet_must_be_object"]

    violations: list[str] = []
    required_fields = (
        "packet_type",
        "schema_version",
        "created_at",
        "packet_id",
        "task_title",
        "task_summary",
        "provider_plan_hash",
        "manifest_hash",
        "forbidden_actions",
        "required_human_acknowledgements",
        "execution_allowed",
        "provider_call_allowed",
        "telegram_return_allowed",
        "approval_request_allowed",
        "requires_human_review",
        "next_allowed_action",
        "audit_refs",
        "source_artifact_refs",
    )
    if approval_packet.get("passed") is not True:
        violations.append("approval_packet_not_passed")
    for field in required_fields:
        if field not in approval_packet:
            violations.append(f"missing_required_field:{field}")

    if approval_packet.get("packet_type") != EXPERT_APPROVAL_PACKET_TYPE:
        violations.append("invalid_packet_type")
    if approval_packet.get("schema_version") != EXPERT_APPROVAL_PACKET_SCHEMA_VERSION:
        violations.append("invalid_schema_version")
    if not str(approval_packet.get("packet_id") or "").strip():
        violations.append("missing_packet_id")
    if not str(approval_packet.get("provider_plan_hash") or "").strip():
        violations.append("missing_provider_plan_hash")
    if not str(approval_packet.get("manifest_hash") or "").strip():
        violations.append("missing_manifest_hash")

    violations.extend(_approval_check_violations(approval_packet))

    if approval_packet.get("execution_allowed") is not False:
        violations.append("execution_allowed")
    if approval_packet.get("provider_call_allowed") is not False:
        violations.append("provider_call_allowed")
    if approval_packet.get("telegram_return_allowed") is not False:
        violations.append("telegram_return_allowed")
    if approval_packet.get("approval_request_allowed") is not False:
        violations.append("approval_request_allowed")
    if approval_packet.get("requires_human_review") is not True:
        violations.append("human_review_not_required")

    forbidden_actions = _string_list(approval_packet.get("forbidden_actions"), limit=64)
    for action in FORBIDDEN_ACTIONS:
        if action not in forbidden_actions:
            violations.append(f"missing_forbidden_action:{action}")
    acknowledgements = _string_list(approval_packet.get("required_human_acknowledgements"), limit=64)
    for acknowledgement in REQUIRED_HUMAN_ACKNOWLEDGEMENTS:
        if acknowledgement not in acknowledgements:
            violations.append(f"missing_required_acknowledgement:{acknowledgement}")

    source_refs = _string_list(approval_packet.get("source_artifact_refs"), limit=64)
    for source_ref in source_refs:
        if _unsafe_ref(source_ref):
            violations.append("unsafe_source_artifact_ref")
            break

    staged_summary = approval_packet.get("staged_artifact_summary")
    staged_summary_text = ""
    if isinstance(staged_summary, Mapping):
        staged_summary_text = str(staged_summary.get("summary") or "")

    scan_text = " ".join(
        str(part or "")
        for part in (
            approval_packet.get("task_title"),
            approval_packet.get("task_summary"),
            approval_packet.get("risk_sensitivity_class"),
            approval_packet.get("provider_plan_hash"),
            approval_packet.get("manifest_hash"),
            staged_summary_text,
        )
    )
    violations.extend(_protected_text_violations(scan_text))
    return _unique_violations(violations)


def _short_hash(value: object) -> str:
    text = str(value or "").strip()
    if not text or _text_has_private_marker(text):
        return ""
    if len(text) <= 24:
        return text
    if text.startswith("sha256:") and len(text) > 22:
        return f"sha256:{text[7:15]}...{text[-8:]}"
    return f"{text[:10]}...{text[-8:]}"


def _safe_scalar(value: object, *, limit: int = _TEXT_VALUE_LIMIT) -> str:
    return _bounded_text(value, limit=limit, fallback="")


def _safe_json_value(value: object, *, depth: int = 0) -> Any:
    if depth >= 3:
        return "..."
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in list(value.items())[:_AUDIT_REF_KEY_LIMIT]:
            safe_key = _safe_scalar(key, limit=80)
            if safe_key:
                result[safe_key] = _safe_json_value(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [_safe_json_value(item, depth=depth + 1) for item in list(value)[:_LIST_LIMIT]]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return _safe_scalar(value)


def _operator_summary(approval_packet: Mapping[str, Any] | object) -> dict[str, Any]:
    if not isinstance(approval_packet, Mapping):
        return {
            "task_title": "Missing approval packet.",
            "task_summary": "No approval packet was provided for review.",
            "risk_sensitivity_class": "unknown_review_required",
            "staged_artifact_summary": "Missing staged artifact summary.",
        }
    staged_summary = approval_packet.get("staged_artifact_summary")
    staged_summary_text = ""
    if isinstance(staged_summary, Mapping):
        staged_summary_text = staged_summary.get("summary")
    return {
        "task_title": _bounded_text(
            approval_packet.get("task_title"),
            limit=_TITLE_LIMIT,
            fallback="Expert approval packet requires operator review.",
        ),
        "task_summary": _bounded_text(
            approval_packet.get("task_summary"),
            limit=_SUMMARY_LIMIT,
            fallback="No sanitized task summary was available.",
        ),
        "risk_sensitivity_class": _bounded_text(
            approval_packet.get("risk_sensitivity_class"),
            limit=80,
            fallback="unknown_review_required",
        ),
        "staged_artifact_summary": _bounded_text(
            staged_summary_text,
            limit=_STAGED_SUMMARY_LIMIT,
            fallback="No staged artifact summary was available.",
        ),
    }


def _risk_summary(approval_packet: Mapping[str, Any] | object, violations: Sequence[str]) -> dict[str, Any]:
    staged_passed = False
    approval_passed = False
    if isinstance(approval_packet, Mapping):
        approval_passed = approval_packet.get("passed") is True
        staged_summary = approval_packet.get("staged_artifact_summary")
        if isinstance(staged_summary, Mapping):
            staged_passed = staged_summary.get("passed") is True
    return {
        "approval_packet_passed": approval_passed,
        "staged_artifact_passed": staged_passed,
        "requires_human_review": True,
        "violation_count": len(violations),
        "violations": list(violations)[:_LIST_LIMIT],
        "recommended_action": _NEXT_ALLOWED_READY if not violations else _NEXT_ALLOWED_REPAIR,
    }


def build_expert_approval_review_bundle(
    approval_packet: Mapping[str, Any] | object,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic local operator-review bundle with no approval delivery."""
    bundle_created_at = created_at or _utc_now()
    violations = _packet_violations(approval_packet)
    ready = not violations
    packet_id = str(approval_packet.get("packet_id") or "") if isinstance(approval_packet, Mapping) else ""
    provider_plan_hash = str(approval_packet.get("provider_plan_hash") or "") if isinstance(approval_packet, Mapping) else ""
    manifest_hash = str(approval_packet.get("manifest_hash") or "") if isinstance(approval_packet, Mapping) else ""
    forbidden_actions = _string_list(approval_packet.get("forbidden_actions"), limit=64) if isinstance(approval_packet, Mapping) else []
    acknowledgements = _string_list(approval_packet.get("required_human_acknowledgements"), limit=64) if isinstance(approval_packet, Mapping) else []
    source_refs = _string_list(approval_packet.get("source_artifact_refs"), limit=64) if isinstance(approval_packet, Mapping) else []
    audit_refs = _safe_json_value(approval_packet.get("audit_refs")) if isinstance(approval_packet, Mapping) else {}

    bundle: dict[str, Any] = {
        "bundle_type": EXPERT_APPROVAL_REVIEW_BUNDLE_TYPE,
        "schema_version": EXPERT_APPROVAL_REVIEW_BUNDLE_SCHEMA_VERSION,
        "created_at": bundle_created_at,
        "packet_id": packet_id,
        "review_status": "ready_for_operator_review" if ready else "blocked_pending_packet_repair",
        "operator_summary": _operator_summary(approval_packet),
        "hash_summary": {
            "provider_plan_hash": provider_plan_hash if not _text_has_private_marker(provider_plan_hash) else "",
            "provider_plan_hash_short": _short_hash(provider_plan_hash),
            "manifest_hash": manifest_hash if not _text_has_private_marker(manifest_hash) else "",
            "manifest_hash_short": _short_hash(manifest_hash),
        },
        "risk_summary": _risk_summary(approval_packet, violations),
        "required_human_acknowledgements": acknowledgements,
        "forbidden_actions": forbidden_actions,
        "next_allowed_action": _NEXT_ALLOWED_READY if ready else _NEXT_ALLOWED_REPAIR,
        "approval_phrase_suggestion": (
            "I have reviewed this local bundle and understand it authorizes no execution, provider call, delivery, or live Guardian request."
            if ready
            else ""
        ),
        "manual_review_instruction": (
            "Repair the sanitized approval packet and rerun local checks before any separate approval slice."
            if not ready
            else ""
        ),
        "execution_allowed": False,
        "provider_call_allowed": False,
        "telegram_send_allowed": False,
        "guardian_live_request_allowed": False,
        "requires_human_review": True,
        "source_artifact_refs": source_refs,
        "audit_refs": audit_refs,
    }
    return bundle


def _redact_private_markers(value: str) -> str:
    redacted = str(value or "")
    for marker in sorted(PROTECTED_DATA_MARKERS, key=len, reverse=True):
        redacted = re.sub(re.escape(marker), "[redacted]", redacted, flags=re.IGNORECASE)
    redacted = _MONEY_AMOUNT_PATTERN.sub("[redacted]", redacted)
    redacted = _ABSOLUTE_PATH_PATTERN.sub(" [redacted-path]", redacted)
    redacted = _TELEGRAM_BOT_TOKEN_PATTERN.sub("[redacted-token]", redacted)
    redacted = _SHA256_HASH_PATTERN.sub(lambda match: _short_hash(match.group(0)), redacted)
    return redacted


def _markdown_text(value: object, *, limit: int = _TEXT_VALUE_LIMIT) -> str:
    text = _bounded_text(_redact_private_markers(str(value or "")), limit=limit, fallback="")
    replacements = {
        "`": "'",
        "<": "&lt;",
        ">": "&gt;",
        "|": "\\|",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _markdown_list(items: Sequence[object], *, limit: int = _LIST_LIMIT) -> list[str]:
    safe_items = [_markdown_text(item, limit=160) for item in list(items)[:limit]]
    return [item for item in safe_items if item]


def render_expert_approval_review_bundle_markdown(review_bundle: Mapping[str, Any] | object) -> str:
    """Render a bounded Markdown string; this never writes or sends the bundle."""
    if not isinstance(review_bundle, Mapping):
        review_bundle = build_expert_approval_review_bundle(None, created_at="unknown")

    operator_summary = review_bundle.get("operator_summary") if isinstance(review_bundle.get("operator_summary"), Mapping) else {}
    hash_summary = review_bundle.get("hash_summary") if isinstance(review_bundle.get("hash_summary"), Mapping) else {}
    risk_summary = review_bundle.get("risk_summary") if isinstance(review_bundle.get("risk_summary"), Mapping) else {}
    acknowledgements = _markdown_list(_as_list(review_bundle.get("required_human_acknowledgements")))
    forbidden_actions = _markdown_list(_as_list(review_bundle.get("forbidden_actions")))
    source_refs = _markdown_list(_as_list(review_bundle.get("source_artifact_refs")))
    violations = _markdown_list(_as_list(risk_summary.get("violations")))

    lines = [
        "# Expert Approval Review Bundle",
        "",
        f"- Bundle type: {_markdown_text(review_bundle.get('bundle_type'), limit=120)}",
        f"- Schema version: {_markdown_text(review_bundle.get('schema_version'), limit=20)}",
        f"- Created at: {_markdown_text(review_bundle.get('created_at'), limit=80)}",
        f"- Packet ID: {_markdown_text(review_bundle.get('packet_id'), limit=120)}",
        f"- Review status: {_markdown_text(review_bundle.get('review_status'), limit=80)}",
        f"- Next allowed action: {_markdown_text(review_bundle.get('next_allowed_action'), limit=120)}",
        f"- Execution allowed: {review_bundle.get('execution_allowed') is True}",
        f"- Provider call allowed: {review_bundle.get('provider_call_allowed') is True}",
        f"- Telegram send allowed: {review_bundle.get('telegram_send_allowed') is True}",
        f"- Guardian live request allowed: {review_bundle.get('guardian_live_request_allowed') is True}",
        "",
        "## Operator Summary",
        "",
        f"- Title: {_markdown_text(operator_summary.get('task_title'), limit=_TITLE_LIMIT)}",
        f"- Task summary: {_markdown_text(operator_summary.get('task_summary'), limit=_SUMMARY_LIMIT)}",
        f"- Risk sensitivity: {_markdown_text(operator_summary.get('risk_sensitivity_class'), limit=80)}",
        f"- Staged artifact: {_markdown_text(operator_summary.get('staged_artifact_summary'), limit=_STAGED_SUMMARY_LIMIT)}",
        "",
        "## Hash Summary",
        "",
        f"- Provider plan hash: {_markdown_text(hash_summary.get('provider_plan_hash_short'), limit=80)}",
        f"- Manifest hash: {_markdown_text(hash_summary.get('manifest_hash_short'), limit=80)}",
        "",
        "## Risk Summary",
        "",
        f"- Approval packet passed: {risk_summary.get('approval_packet_passed') is True}",
        f"- Staged artifact passed: {risk_summary.get('staged_artifact_passed') is True}",
        f"- Violation count: {_markdown_text(risk_summary.get('violation_count'), limit=20)}",
    ]
    if violations:
        lines.extend(["- Violations:"] + [f"  - {violation}" for violation in violations])
    lines.extend(["", "## Required Human Acknowledgements", ""])
    lines.extend([f"- {acknowledgement}" for acknowledgement in acknowledgements] or ["- None provided"])
    lines.extend(["", "## Forbidden Actions", ""])
    lines.extend([f"- {action}" for action in forbidden_actions] or ["- None provided"])
    lines.extend(["", "## Source Artifact Refs", ""])
    lines.extend([f"- {source_ref}" for source_ref in source_refs] or ["- None provided"])

    instruction = review_bundle.get("approval_phrase_suggestion") or review_bundle.get("manual_review_instruction")
    lines.extend(["", "## Manual Review", "", f"- {_markdown_text(instruction, limit=280)}"])

    markdown = "\n".join(lines).strip() + "\n"
    if len(markdown) <= _MARKDOWN_LIMIT:
        return markdown
    return markdown[: max(0, _MARKDOWN_LIMIT - 4)].rstrip() + "...\n"