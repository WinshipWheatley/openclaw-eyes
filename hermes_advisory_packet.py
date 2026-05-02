from __future__ import annotations

"""Pure static contract helpers for Hermes advisory packets and memos."""

import re
from typing import Any, Mapping, Sequence


HERMES_ADVISORY_PACKET_TYPE = "hermes.advisory_packet"
HERMES_ADVISORY_SCHEMA_VERSION = 1
HERMES_AUTHORITY_LEVEL = "advisory_only"
HERMES_OUTPUT_KIND = "non_canonical_advisory_memo"
HERMES_PROMOTION_REQUIRED = "explicit_human_or_chief_controlled_promotion"

NON_CANONICAL_NOTICE = (
    "Non-canonical advisory memo. Hermes made no decisions, executed no commands, "
    "and made no canonical writes."
)

REQUIRED_WITHHELD_SURFACES = (
    "runtime_state",
    "logs",
    "secrets",
    "vaults",
    "legal_private_or_private_matter_data",
    "gmail_bodies",
    "queues",
    "live_services",
    "installed_user_units",
    "provider_or_model_execution",
    "canonical_write_surfaces",
)

FALSE_PERMISSION_FIELDS = (
    "execution_allowed",
    "canonical_write_allowed",
    "queue_mutation_allowed",
    "approval_authority_allowed",
    "provider_fallback_allowed",
    "live_service_inspection_allowed",
    "private_data_allowed",
)

REQUIRED_PACKET_FIELDS = (
    "packet_id",
    "purpose",
    "source_set_name",
    "allowed_read_surfaces",
    "withheld_surfaces",
    "sensitive_data_policy",
    "authority_level",
    *FALSE_PERMISSION_FIELDS,
    "output_kind",
    "promotion_required",
)

REQUIRED_MEMO_FIELDS = (
    "observations",
    "risks",
    "suggested_next_slices",
    "evidence_refs",
    "assumptions",
    "withheld_surfaces",
    "non_canonical_notice",
    "commands_executed",
    "decisions_made",
    "canonical_writes_made",
)

_PACKET_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,120}$")
_PROTECTED_ALLOWED_SURFACE_MARKERS = (
    "hermes_home",
    "runtime_state",
    "runtime state",
    "session",
    "state db",
    "log",
    "secret",
    "vault",
    "legal",
    "private matter",
    "gmail",
    "cpa",
    "music law",
    "publishing",
    ".mcp.json",
    "installed user unit",
    "live service",
)
_BROAD_SURFACE_VALUES = frozenset({"/", ".", "*", "repo", "repository", "/home/openclaw"})
_FORBIDDEN_MEMO_CLAIM_PATTERNS = (
    re.compile(r"\bi\s+(?:decided|approved|authorized|executed|ran|wrote|updated)\b", re.IGNORECASE),
    re.compile(r"\bhermes\s+(?:decided|approved|authorized|executed|ran|wrote|updated)\b", re.IGNORECASE),
    re.compile(r"\b(?:decision|approval)\s+(?:is|was)\s+(?:made|granted|final)\b", re.IGNORECASE),
    re.compile(r"\b(?:command|shell|systemctl|service)\s+(?:was\s+)?(?:executed|run|started|restarted|stopped)\b", re.IGNORECASE),
    re.compile(r"\bcanonical\s+(?:doc|write|update|state)\s+(?:was\s+)?(?:written|updated|made|changed)\b", re.IGNORECASE),
    re.compile(r"\b(?:queued|mutated queue|provider fallback|live service inspection)\b", re.IGNORECASE),
)


def _as_string(value: object) -> str:
    return " ".join(str(value or "").split())


def _string_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [_as_string(item) for item in value if _as_string(item)]


def _unique_violations(violations: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(item for item in violations if item))


def _check_result(violations: Sequence[str]) -> dict[str, Any]:
    unique = _unique_violations(violations)
    return {
        "passed": not unique,
        "violations": unique,
        "recommended_action": "pass" if not unique else "reject",
    }


def _append_missing_fields(payload: Mapping[str, Any], required_fields: Sequence[str], violations: list[str]) -> None:
    for field in required_fields:
        if field not in payload:
            violations.append(f"missing_required_field:{field}")


def _has_protected_allowed_surface(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _PROTECTED_ALLOWED_SURFACE_MARKERS)


def build_hermes_advisory_packet(
    *,
    packet_id: str,
    purpose: str,
    source_set_name: str,
    allowed_read_surfaces: Sequence[str],
    withheld_surfaces: Sequence[str] = REQUIRED_WITHHELD_SURFACES,
    sensitive_data_policy: str = "repo_docs_and_tests_only_no_private_data",
) -> dict[str, Any]:
    """Build a deterministic packet-in contract for Hermes advisory review."""
    return {
        "packet_type": HERMES_ADVISORY_PACKET_TYPE,
        "schema_version": HERMES_ADVISORY_SCHEMA_VERSION,
        "packet_id": _as_string(packet_id),
        "purpose": _as_string(purpose),
        "source_set_name": _as_string(source_set_name),
        "allowed_read_surfaces": _string_list(list(allowed_read_surfaces)),
        "withheld_surfaces": _string_list(list(withheld_surfaces)),
        "sensitive_data_policy": _as_string(sensitive_data_policy),
        "authority_level": HERMES_AUTHORITY_LEVEL,
        "execution_allowed": False,
        "canonical_write_allowed": False,
        "queue_mutation_allowed": False,
        "approval_authority_allowed": False,
        "provider_fallback_allowed": False,
        "live_service_inspection_allowed": False,
        "private_data_allowed": False,
        "output_kind": HERMES_OUTPUT_KIND,
        "promotion_required": HERMES_PROMOTION_REQUIRED,
    }


def check_hermes_advisory_packet(packet: Mapping[str, Any] | object) -> dict[str, Any]:
    """Validate that a Hermes advisory packet remains packet-in/proposal-out."""
    violations: list[str] = []
    if not isinstance(packet, Mapping):
        return _check_result(["packet_must_be_object"])

    _append_missing_fields(packet, REQUIRED_PACKET_FIELDS, violations)

    if packet.get("packet_type") != HERMES_ADVISORY_PACKET_TYPE:
        violations.append("invalid_packet_type")
    if packet.get("schema_version") != HERMES_ADVISORY_SCHEMA_VERSION:
        violations.append("invalid_schema_version")
    packet_id = _as_string(packet.get("packet_id"))
    if not packet_id or not _PACKET_ID_PATTERN.match(packet_id):
        violations.append("invalid_packet_id")
    if not _as_string(packet.get("purpose")):
        violations.append("missing_purpose")
    if not _as_string(packet.get("source_set_name")):
        violations.append("missing_source_set_name")
    if packet.get("authority_level") != HERMES_AUTHORITY_LEVEL:
        violations.append("authority_not_advisory_only")
    if packet.get("output_kind") != HERMES_OUTPUT_KIND:
        violations.append("invalid_output_kind")
    if packet.get("promotion_required") != HERMES_PROMOTION_REQUIRED:
        violations.append("invalid_promotion_required")

    for field in FALSE_PERMISSION_FIELDS:
        if packet.get(field) is not False:
            violations.append(f"permission_not_false:{field}")

    sensitive_policy = _as_string(packet.get("sensitive_data_policy")).lower()
    if not sensitive_policy:
        violations.append("missing_sensitive_data_policy")
    if "private" in sensitive_policy and "no_private" not in sensitive_policy and "private_data_allowed:false" not in sensitive_policy:
        violations.append("sensitive_data_policy_allows_private_data")

    allowed = _string_list(packet.get("allowed_read_surfaces"))
    if not allowed:
        violations.append("missing_allowed_read_surfaces")
    for surface in allowed:
        if surface.lower() in _BROAD_SURFACE_VALUES:
            violations.append(f"allowed_surface_too_broad:{surface}")
        if _has_protected_allowed_surface(surface):
            violations.append(f"allowed_surface_protected:{surface}")

    withheld = _string_list(packet.get("withheld_surfaces"))
    withheld_set = set(withheld)
    if not withheld:
        violations.append("missing_withheld_surfaces")
    for required in REQUIRED_WITHHELD_SURFACES:
        if required not in withheld_set:
            violations.append(f"missing_withheld_surface:{required}")
    for surface in allowed:
        if surface in withheld_set:
            violations.append(f"allowed_surface_is_withheld:{surface}")

    return _check_result(violations)


def build_hermes_advisory_memo(
    *,
    observations: Sequence[str],
    risks: Sequence[str],
    suggested_next_slices: Sequence[str],
    evidence_refs: Sequence[str],
    assumptions: Sequence[str],
    withheld_surfaces: Sequence[str],
) -> dict[str, Any]:
    """Build a deterministic non-canonical Hermes advisory memo shape."""
    return {
        "output_kind": HERMES_OUTPUT_KIND,
        "authority_level": HERMES_AUTHORITY_LEVEL,
        "observations": _string_list(list(observations)),
        "risks": _string_list(list(risks)),
        "suggested_next_slices": _string_list(list(suggested_next_slices)),
        "evidence_refs": _string_list(list(evidence_refs)),
        "assumptions": _string_list(list(assumptions)),
        "withheld_surfaces": _string_list(list(withheld_surfaces)),
        "non_canonical_notice": NON_CANONICAL_NOTICE,
        "commands_executed": False,
        "decisions_made": False,
        "canonical_writes_made": False,
    }


def _memo_text_fields(memo: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for field in ("observations", "risks", "suggested_next_slices", "evidence_refs", "assumptions"):
        values.extend(_string_list(memo.get(field)))
    return values


def check_hermes_advisory_memo(
    memo: Mapping[str, Any] | object,
    *,
    packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate that a Hermes memo remains non-canonical and side-effect free."""
    violations: list[str] = []
    if not isinstance(memo, Mapping):
        return _check_result(["memo_must_be_object"])

    _append_missing_fields(memo, REQUIRED_MEMO_FIELDS, violations)

    if memo.get("output_kind") not in (None, HERMES_OUTPUT_KIND):
        violations.append("invalid_output_kind")
    if memo.get("authority_level") not in (None, HERMES_AUTHORITY_LEVEL):
        violations.append("authority_not_advisory_only")
    if memo.get("non_canonical_notice") != NON_CANONICAL_NOTICE:
        violations.append("missing_or_invalid_non_canonical_notice")
    if memo.get("commands_executed") is not False:
        violations.append("commands_executed_not_false")
    if memo.get("decisions_made") is not False:
        violations.append("decisions_made_not_false")
    if memo.get("canonical_writes_made") is not False:
        violations.append("canonical_writes_made_not_false")

    for field in ("observations", "risks", "suggested_next_slices", "evidence_refs", "assumptions", "withheld_surfaces"):
        if not _string_list(memo.get(field)):
            violations.append(f"missing_or_empty_memo_field:{field}")

    withheld = set(_string_list(memo.get("withheld_surfaces")))
    if packet is not None:
        packet_check = check_hermes_advisory_packet(packet)
        if not packet_check["passed"]:
            violations.append("source_packet_invalid")
        packet_withheld = set(_string_list(packet.get("withheld_surfaces"))) if isinstance(packet, Mapping) else set()
        for surface in packet_withheld:
            if surface not in withheld:
                violations.append(f"memo_missing_packet_withheld_surface:{surface}")

    for text in _memo_text_fields(memo):
        for pattern in _FORBIDDEN_MEMO_CLAIM_PATTERNS:
            if pattern.search(text):
                violations.append("memo_implies_execution_decision_or_canonical_write")
                break

    return _check_result(violations)