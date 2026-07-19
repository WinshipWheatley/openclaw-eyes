"""Shared, read-only agent introspection classification and turn self-facts.

This module grants no authority and performs no model, workflow, ledger, send,
or external action by itself.  It only classifies self-queries and normalizes a
closed subset of already-produced machine proof for packet delivery.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
import json
import re
from typing import Any, Mapping, Sequence


TURN_SELF_FACTS_SCHEMA_VERSION = "turn_self_facts_v1"
TURN_SELF_FACTS_SOURCE_REF = "machine_proof:turn_self_facts_v1"
TURN_SELF_FACT_FIELDS = (
    "agent",
    "source_request_id",
    "turn_receipt_id",
    "model_id",
    "lane_id",
    "backend_class",
    "hardware_class",
    "selection_reason",
    "last_action_receipt_ptr",
)


@dataclass(frozen=True)
class AgentIntrospectionMatch:
    """A precise read-only self-query match."""

    kind: str
    evidence: tuple[str, ...]


_BUSINESS_OBJECT_RE = re.compile(
    r"\b(?:invoice|invoices|payment|payments|receivable|receivables|client|"
    r"email|ledger|album|song|mix|coupa|gmail|check|checks)\b",
    re.IGNORECASE,
)

_MODEL_PATTERNS = (
    re.compile(
        r"\b(?:what|which)\s+(?:language\s+)?model\b.{0,100}\b(?:you|your|answer|response|turn)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:what|which)\s+brain\b.{0,100}\b(?:you|your|answer|response|turn)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:you|your)\b.{0,100}\b(?:model|brain|lane|backend|hardware)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:model|brain|lane|backend|hardware)\b.{0,100}\b(?:you|your)\b",
        re.IGNORECASE,
    ),
)
_RECENT_ACTION_PATTERNS = (
    re.compile(r"\bwhat\s+did\s+you\s+(?:just|last)\s+do\b", re.IGNORECASE),
    re.compile(
        r"\b(?:your|you)\b.{0,100}\b(?:last|recent)\s+(?:action|receipt|move)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:last|recent)\s+(?:action|receipt|move)\b.{0,100}\b(?:your|you)\b",
        re.IGNORECASE,
    ),
)
_ROUTING_PATTERNS = (
    re.compile(
        r"\bhow\s+do\s+you\s+decide\b.{0,140}\b(?:task|yours|agent|route|handoff|belongs)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwhat(?:'s|\s+is)\s+your\s+(?:routing|handoff|ownership)\s+rule\b",
        re.IGNORECASE,
    ),
)
_ADVISORY_PATTERNS = (
    re.compile(r"\bwhat\s+do\s+you\s+think\b", re.IGNORECASE),
    re.compile(
        r"\bwhat(?:'s|\s+is)\s+(?:your|the)\s+next\s+(?:step|move)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bwould\s+you\s+(?:like|recommend|prefer)\b", re.IGNORECASE),
)
_STATUS_PATTERNS = (
    re.compile(
        r"\bwhat(?:'s|\s+is)\s+your\s+(?:own\s+)?(?:service\s+)?(?:status|health|lane)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bhow\s+are\s+you\b.{0,80}\b(?:running|working|holding\s+up)\b",
        re.IGNORECASE,
    ),
)
_KNOWLEDGE_PATTERNS = (
    re.compile(
        r"\bwhat\s+do\s+you\s+have\b.{0,80}\b(?:packet|context|record|receipt)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwhat\s+do\s+you\s+have\s+in\s+your\s+packet\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdo\s+you\s+(?:know|have\s+(?:anything|context|records?))\b.{0,120}\b(?:about|on)\b",
        re.IGNORECASE,
    ),
)


def _pattern_evidence(text: str, patterns: Sequence[re.Pattern[str]]) -> tuple[str, ...]:
    return tuple(pattern.pattern for pattern in patterns if pattern.search(text))


def classify_agent_introspection(
    text: str,
    *,
    addressed_agent: str = "",
) -> AgentIntrospectionMatch | None:
    """Return a precision-biased self-query match or ``None``.

    Business/domain capability questions deliberately fall through to their
    established owners.  ``addressed_agent`` permits direct questions such as
    "Which brain answered that turn?" on an already identity-bound surface.
    """

    candidate = " ".join(str(text or "").split()).strip()
    if not candidate:
        return None

    for kind, patterns in (
        ("model_brain", _MODEL_PATTERNS),
        ("recent_action", _RECENT_ACTION_PATTERNS),
        ("routing_rule", _ROUTING_PATTERNS),
        ("advisory", _ADVISORY_PATTERNS),
        ("status_health", _STATUS_PATTERNS),
        ("knowledge_packet", _KNOWLEDGE_PATTERNS),
    ):
        evidence = _pattern_evidence(candidate, patterns)
        if evidence:
            return AgentIntrospectionMatch(kind=kind, evidence=evidence)

    if addressed_agent and re.search(
        r"\bwhich\s+brain\s+answered\b.{0,80}\b(?:turn|response|message)\b",
        candidate,
        re.IGNORECASE,
    ):
        return AgentIntrospectionMatch(
            kind="model_brain",
            evidence=("identity_bound_surface_brain_question",),
        )

    if re.search(r"\bwhat\s+can\s+you\s+do\b", candidate, re.IGNORECASE):
        if _BUSINESS_OBJECT_RE.search(candidate):
            return None
        return AgentIntrospectionMatch(
            kind="capability",
            evidence=("self_capability",),
        )
    return None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _route_views(
    route_receipt: Mapping[str, Any] | None,
    session: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any], ...]:
    explicit = _mapping(route_receipt)
    explicit_external = _mapping(
        explicit.get("external_brain_route_receipt")
        or explicit.get("external_brain")
    )
    session_map = _mapping(session)
    reused = _mapping(session_map.get("lm1_reused_model_receipt"))
    reused_external = _mapping(
        reused.get("external_brain_route_receipt")
        or reused.get("external_brain")
    )
    return tuple(
        view
        for view in (explicit, explicit_external, reused, reused_external)
        if view
    )


def _first_from_views(views: Sequence[Mapping[str, Any]], *keys: str) -> str:
    for view in views:
        value = _first_text(*(view.get(key) for key in keys))
        if value:
            return value
    return ""


def normalize_turn_self_facts(
    *,
    agent: str,
    source_request_id: str = "",
    session: Mapping[str, Any] | None = None,
    route_receipt: Mapping[str, Any] | None = None,
    last_action_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize an allowlisted, closed set of current-turn self facts."""

    session_map = _mapping(session)
    local_binding = _mapping(session_map.get("local_model_binding"))
    views = _route_views(route_receipt, session_map)

    normalized_agent = str(agent or "").strip().lower()
    normalized_source_request_id = _first_text(
        source_request_id,
        _first_from_views(views, "source_request_id", "request_hash"),
        session_map.get("source_request_id"),
        session_map.get("source_message_id"),
    )
    turn_receipt_id = _first_text(
        _first_from_views(
            views,
            "turn_id_hash",
            "receipt_id",
            "model_call_id_hash",
        )
    )
    model_id = _first_text(
        _first_from_views(
            views,
            "binding_model_id",
            "model_selected",
            "model_id",
            "model",
        ),
        local_binding.get("model"),
        local_binding.get("model_id"),
    )
    lane_id = _first_text(
        _first_from_views(
            views,
            "effective_lane_id",
            "lane_id",
            "candidate_lane_id",
            "lane",
        ),
        local_binding.get("lane"),
        local_binding.get("lane_id"),
    )
    selection_reason = _first_text(
        _first_from_views(
            views,
            "effort_reason",
            "selection_reason",
            "fallback_reason",
            "policy_reason",
        ),
        local_binding.get("binding_reason"),
        local_binding.get("reason"),
    )

    external_turn = any(
        view.get("external_turn_performed") is True
        or view.get("external_llm_invoked") is True
        or str(view.get("response_source") or "") == "external_brain"
        for view in views
    )
    local_turn = any(
        view.get("local_model_invoked") is True
        or str(view.get("response_source") or "") == "local_fallback"
        or str(view.get("effective_lane_id") or "") == "local_safe_lane"
        for view in views
    ) or lane_id == "local_safe_lane"
    if external_turn:
        backend_class = "external_brain"
        hardware_class = "provider_managed_external"
    elif local_turn or local_binding:
        backend_class = "local_ollama"
        hardware_class = _first_text(
            _first_from_views(views, "hardware_class", "accelerator_class"),
            local_binding.get("hardware_class"),
        ) or "unknown"
    else:
        backend_class = "unknown"
        hardware_class = "unknown"

    last_action = _mapping(last_action_receipt)
    last_action_receipt_ptr = _first_text(
        last_action.get("receipt_pointer"),
        last_action.get("receipt_ptr"),
        last_action.get("receipt_id"),
    )
    facts: dict[str, Any] = {
        "schema_version": TURN_SELF_FACTS_SCHEMA_VERSION,
        "agent": normalized_agent,
        "source_request_id": normalized_source_request_id,
        "turn_receipt_id": turn_receipt_id,
        "model_id": model_id,
        "lane_id": lane_id,
        "backend_class": backend_class,
        "hardware_class": hardware_class,
        "selection_reason": selection_reason,
        "last_action_receipt_ptr": last_action_receipt_ptr,
    }
    known_fields: list[str] = []
    unknown_fields: list[str] = []
    for field in TURN_SELF_FACT_FIELDS:
        value = facts[field]
        if value and value != "unknown":
            known_fields.append(field)
        else:
            unknown_fields.append(field)
    facts["known_fields"] = known_fields
    facts["unknown_fields"] = unknown_fields
    return facts


def _closed_turn_self_facts(facts: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": TURN_SELF_FACTS_SCHEMA_VERSION,
        **{field: facts.get(field, "") for field in TURN_SELF_FACT_FIELDS},
        "known_fields": list(facts.get("known_fields") or ()),
        "unknown_fields": list(facts.get("unknown_fields") or ()),
    }


def inject_turn_self_facts(
    packet: Mapping[str, Any],
    facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Copy a packet and append the closed self-facts section."""

    result = copy.deepcopy(dict(packet))
    normalized = _closed_turn_self_facts(facts)
    result["turn_self_facts"] = normalized
    result["facts"] = [
        *list(result.get("facts") or ()),
        {
            "fact_id": f"turn_self_facts:{normalized['agent']}",
            "topic": "agent_introspection",
            "label": "Current turn self facts",
            "value": json.dumps(normalized, sort_keys=True, ensure_ascii=True),
            "source_ref": TURN_SELF_FACTS_SOURCE_REF,
            "pii_tier": "PUBLIC",
        },
    ]
    result["packet_text"] = "\n".join(
        part
        for part in (
            str(result.get("packet_text") or "").strip(),
            "TURN SELF FACTS (machine proof; do not infer missing values):",
            json.dumps(normalized, sort_keys=True, ensure_ascii=True),
        )
        if part
    )
    source_refs = [
        *(str(ref) for ref in result.get("source_refs", ()) if str(ref).strip()),
        TURN_SELF_FACTS_SOURCE_REF,
    ]
    result["source_refs"] = tuple(dict.fromkeys(source_refs))
    return result


__all__ = [
    "AgentIntrospectionMatch",
    "TURN_SELF_FACTS_SCHEMA_VERSION",
    "TURN_SELF_FACTS_SOURCE_REF",
    "classify_agent_introspection",
    "inject_turn_self_facts",
    "normalize_turn_self_facts",
]
