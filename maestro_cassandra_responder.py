"""Maestro front-door adapter for Cassandra specialist answers.

The adapter is intentionally narrow. It gates intent before calling
``cassandra_brain.handle`` so send/reply/action/Gmail-shaped text stays on the
existing staging/refusal route and never reaches Cassandra's side-effectful
handler through this front-door path.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence


# ── Conversation-continuity flag (ADDITIVE, default OFF) ──────────────────────
def _continuity_enabled() -> bool:
    """Return True only when OPENCLAW_CONTINUITY_CAPSULE is "1" or "true"."""
    return os.environ.get("OPENCLAW_CONTINUITY_CAPSULE", "0").lower() in ("1", "true")


def _packet_engine_enabled() -> bool:
    """Return True unless OPENCLAW_PACKET_ENGINE explicitly disables the engine."""
    return os.environ.get("OPENCLAW_PACKET_ENGINE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


MAC_RENDER_HINT = "COMPACT_WITH_DISCLOSURE"
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
CAPABILITY_INDEX_READ_MODEL = "openclaw_capability_index.json"
AGENT_PRESENCE_READ_MODEL = "agent_presence.json"
CHIEF_STATUS_READ_MODEL = "chief_status_rail.json"
SYNC_HEALTH_READ_MODEL = "sync_health.json"
ALLOWED_SESSION_KEYS = (
    "system_knowledge_repo_root",
    "system_knowledge_ledger_path",
    "system_knowledge_atlas_path",
)
SESSION_PATH_KEY_ALIASES = {
    "repo_root": "system_knowledge_repo_root",
    "system_knowledge_repo_root": "system_knowledge_repo_root",
    "ledger_path": "system_knowledge_ledger_path",
    "system_knowledge_ledger_path": "system_knowledge_ledger_path",
    "atlas_path": "system_knowledge_atlas_path",
    "system_knowledge_atlas_path": "system_knowledge_atlas_path",
}
PATH_PREFIX_ALLOWLIST = (
    Path("/home/openclaw").resolve(),
    Path("/mnt/e/openclaw").resolve(),
)
FORBIDDEN_PATH_NAMES = frozenset({".chief.env", ".google-secrets"})
FORBIDDEN_PRIVATE_SUFFIXES = (
    "LegalPrivate",
    "FinancePrivate",
    "MusicLawPrivate",
)


@dataclass(frozen=True)
class MaestroCassandraResult:
    status: str
    intent_class: str
    allowed_to_call_handle: bool
    one_line_answer: str = ""
    plain_summary: str = ""
    mac_render_hint: str = MAC_RENDER_HINT
    route_to_staging_reason: str = ""
    session_forwarded: Mapping[str, Any] | None = None
    machine_proof: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["session_forwarded"] = dict(self.session_forwarded or {})
        payload["machine_proof"] = dict(self.machine_proof or {})
        return payload


HandleFn = Callable[[str, dict[str, Any] | None], Sequence[str]]
ProtectedGenerateFn = Callable[..., Any]
HANDLE_BACKEND_ROUTE = "maestro_cassandra_responder.cassandra_brain.handle"
DATE_BACKEND_ROUTE = "maestro_cassandra_responder.datetime_deterministic"
HERMES_TRUTHFUL_BACKEND_ROUTE = "maestro_cassandra_responder.hermes_truthful_advisory"
HERMES_FALLBACK_AGENT_TARGETS = frozenset(
    {
        "cassandra",
        "chief",
        "guardian",
        "hermes",
        "niles",
        "operator_briefing",
        "operations_router",
        "producer",
        "report_bridge",
    }
)
HERMES_SEND_OR_MONEY_RE = re.compile(
    r"\b(send|email|message|text|telegram|notify|reply|forward|post|deliver|pay|payment|money|wire|ach|transfer|refund|charge)\b"
)
INTERNAL_STATE_LEAK_PATTERNS = (
    re.compile(r"\bInterrupting current task\s*(?:\([^)]*\))?\s*", re.IGNORECASE),
    re.compile(r"\(?(?:iteration|loop)\s+\d+\s*/\s*\d+\)?", re.IGNORECASE),
)
_ANSWER_TOPIC_AMOUNT_RE = re.compile(r"\$[\d,]+(?:\.\d+)?")
_ANSWER_TOPIC_MAX_SENTENCES = 5


def _derived_answer_topic_values(context_packet: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(context_packet, Mapping):
        return ()
    facts = context_packet.get("facts", ())
    if not isinstance(facts, Sequence):
        return ()
    values: list[str] = []
    for fact in facts:
        if not isinstance(fact, Mapping):
            continue
        if str(fact.get("provenance") or "") != "derived_answer_topic":
            continue
        value = str(fact.get("value") or "").strip()
        if value:
            values.append(value)
    return tuple(values)


def _sentence_count(text: str) -> int:
    stripped = str(text or "").strip()
    if not stripped:
        return 0
    return len([part for part in re.split(r"(?<=[.!?])\s+", stripped) if part.strip()])


def _enforce_answer_topic_presentation(answer_text: str, context_packet: Mapping[str, Any] | None) -> str:
    """Anti-launder extension (task 132): when the packet carries a derived answer topic
    (money/plate), the reply must carry the topic's rendered lines VERBATIM -- amounts and
    statuses are never paraphrased. Live evidence (msg 1277): the model re-narrated an
    evidenced $1,095 as "amounts still unverified or unknown", dropping the number. Post-check
    the model's reply against the topic's amount strings and against a concise-reply cap; on
    either mismatch, fall back to the deterministic topic text itself (grounded > eloquent)."""
    topic_values = _derived_answer_topic_values(context_packet)
    if not topic_values:
        return answer_text
    required_amounts = tuple(dict.fromkeys(_ANSWER_TOPIC_AMOUNT_RE.findall(" ".join(topic_values))))
    if not required_amounts:
        return answer_text
    amounts_present = all(amount in answer_text for amount in required_amounts)
    concise_enough = _sentence_count(answer_text) <= _ANSWER_TOPIC_MAX_SENTENCES
    if amounts_present and concise_enough:
        return answer_text
    return " ".join(topic_values)


def _default_handle(text: str, session: dict[str, Any] | None = None) -> Sequence[str]:
    from cassandra_brain import handle as cassandra_handle

    return cassandra_handle(text, session)


def backend_route_for_result(result: MaestroCassandraResult) -> str:
    if result.allowed_to_call_handle:
        return HANDLE_BACKEND_ROUTE
    if result.intent_class == "date_awareness":
        return DATE_BACKEND_ROUTE
    if result.intent_class == "maestro_brain_freeform":
        return "maestro_cassandra_responder.protected_generate"
    if result.intent_class == "status_capability_readback":
        if (result.machine_proof or {}).get("protected_generate_called") is True:
            return "maestro_cassandra_responder.protected_generate.status_capability_context"
        return "maestro_cassandra_responder.truthful_status_capability_readback"
    if result.intent_class == "system_health_readback":
        return "maestro_cassandra_responder.chief_system_health_readback"
    if result.intent_class == "hermes_truthful_advisory":
        return HERMES_TRUTHFUL_BACKEND_ROUTE
    if result.intent_class:
        return f"maestro_cassandra_responder.{result.intent_class}"
    return "maestro_cassandra_responder.intent_gate"


def proof_refs_for_result(result: MaestroCassandraResult, *base_refs: str) -> tuple[str, ...]:
    refs: list[str] = [str(ref) for ref in base_refs if str(ref or "").strip()]
    if result.intent_class:
        refs.append(f"maestro_cassandra_responder:{result.intent_class}")
    proof = result.machine_proof or {}
    for key in ("proof_refs", "read_model_refs", "source_truth_refs"):
        value = proof.get(key)
        if isinstance(value, str) and value.strip():
            refs.append(value.strip())
        elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
            refs.extend(str(item).strip() for item in value if str(item).strip())
    return tuple(dict.fromkeys(refs))


def external_llm_invoked_for_result(result: MaestroCassandraResult) -> bool:
    proof = result.machine_proof or {}
    if "external_llm_invoked" in proof:
        return proof.get("external_llm_invoked") is True
    if proof.get("cassandra_handle_called") is not True:
        return False
    return proof.get("external_llm_invoked") is True


def machine_proof_for_result(result: MaestroCassandraResult) -> dict[str, Any]:
    proof = dict(result.machine_proof or {})
    proof["external_llm_invoked"] = external_llm_invoked_for_result(result)
    return proof


def result_dict_for_receipt(result: MaestroCassandraResult) -> dict[str, Any]:
    payload = result.to_dict()
    payload["machine_proof"] = machine_proof_for_result(result)
    return payload


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _short_hash_for_packet(*parts: Any) -> str:
    return hashlib.sha256(_stable_json(parts).encode("utf-8")).hexdigest()[:16]


def _protected_generate_receipt_machine_proof(receipt: Mapping[str, Any]) -> dict[str, Any]:
    route = str(receipt.get("route") or "").strip()
    model_selected = str(
        receipt.get("model_selected")
        or receipt.get("model_id")
        or receipt.get("model")
        or ""
    ).strip()
    proof: dict[str, Any] = {
        "model_call_performed": bool(receipt.get("model_call_performed", False)),
        "external_llm_invoked": bool(receipt.get("external_llm_invoked", False)),
        "local_model_invoked": bool(receipt.get("local_model_invoked", False)),
        "deterministic_fallback_used": bool(receipt.get("deterministic_fallback_used", False)),
        "model_call_attempted": bool(receipt.get("model_call_attempted", False)),
        "model_output_delivered": bool(receipt.get("model_output_delivered", False)),
        "delivered_response_source": str(receipt.get("delivered_response_source") or ""),
    }
    if route:
        proof["route"] = route
        proof["protected_generate_route"] = route
    if model_selected:
        proof["model_id"] = model_selected
        proof["protected_generate_model_selected"] = model_selected
    fallback_reason = str(receipt.get("model_fallback_reason") or "").strip()
    if fallback_reason:
        proof["model_fallback_reason"] = fallback_reason
    skills_applied = receipt.get("skills_applied")
    if isinstance(skills_applied, Sequence) and not isinstance(skills_applied, (str, bytes)):
        proof["skills_applied"] = [str(skill) for skill in skills_applied if str(skill).strip()]
    skill_receipts = receipt.get("skill_receipts")
    if isinstance(skill_receipts, Sequence) and not isinstance(skill_receipts, (str, bytes)):
        proof["skill_receipts"] = [dict(item) for item in skill_receipts if isinstance(item, Mapping)]
    return proof


def _receipt_or_packet_has_skill(
    skill_id: str,
    *,
    receipt: Mapping[str, Any],
    context_packet: Mapping[str, Any],
) -> bool:
    expected = str(skill_id or "").strip()
    if not expected:
        return False
    skills_applied = receipt.get("skills_applied")
    if isinstance(skills_applied, Sequence) and not isinstance(skills_applied, (str, bytes)):
        if expected in {str(skill).strip() for skill in skills_applied}:
            return True
    for key in ("skill_receipts", "skills"):
        rows = context_packet.get(key)
        if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)):
            for row in rows:
                if isinstance(row, Mapping) and str(row.get("skill_id") or "").strip() == expected:
                    return True
    return False


def _is_conversational_status_capability_prompt(text: str) -> bool:
    capability_phrases = (
        "what can you help me with",
        "what can openclaw help me with",
        "what can you do for me",
        "what can you do",
        "what can openclaw do",
        "what are you capable of",
        "how can you help",
        "how can openclaw help",
    )
    return any(phrase in text for phrase in capability_phrases)
def _path_is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _has_forbidden_path_marker(raw_path: str) -> bool:
    normalized = raw_path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part and part != "."]
    for part in parts:
        if part in FORBIDDEN_PATH_NAMES:
            return True
        if part == "OpenClawLegalPrivate":
            return True
        if any(part.endswith(suffix) for suffix in FORBIDDEN_PRIVATE_SUFFIXES):
            return True
    return False


def _sanitize_session_path(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw or _has_forbidden_path_marker(raw):
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        return None
    try:
        resolved = candidate.resolve(strict=False)
    except OSError:
        return None
    if _has_forbidden_path_marker(str(resolved)):
        return None
    if not any(resolved == root or _path_is_under(resolved, root) for root in PATH_PREFIX_ALLOWLIST):
        return None
    return str(resolved)


def _add_safe_session_value(session: dict[str, Any], key: str, value: Any) -> None:
    canonical_key = SESSION_PATH_KEY_ALIASES.get(key)
    if canonical_key is None or value in ("", None):
        return
    safe_value = _sanitize_session_path(value)
    if safe_value is not None:
        session[canonical_key] = safe_value


def filtered_session(session: Mapping[str, Any] | None = None) -> dict[str, Any]:
    filtered: dict[str, Any] = {}
    if not session:
        return filtered
    for key in ALLOWED_SESSION_KEYS:
        _add_safe_session_value(filtered, key, session.get(key))
    return filtered


def session_from_request(request: Mapping[str, Any]) -> dict[str, Any]:
    session: dict[str, Any] = {}
    for key in SESSION_PATH_KEY_ALIASES:
        _add_safe_session_value(session, key, request.get(key))
    context = request.get("context") if isinstance(request.get("context"), Mapping) else {}
    current_context = request.get("current_context") if isinstance(request.get("current_context"), Mapping) else {}
    for source in (context, current_context):
        for key in SESSION_PATH_KEY_ALIASES:
            _add_safe_session_value(session, key, source.get(key))
    return session


def operator_text_from_request(request: Mapping[str, Any]) -> str:
    text_keys = (
        "operator_text",
        "operatorText",
        "operator_message",
        "operatorMessage",
        "chat_goal",
        "chatGoal",
        "goal_text",
        "goalText",
        "source_text",
        "sourceText",
        "text",
        "message",
    )
    for key in text_keys:
        value = request.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    event = request.get("event") if isinstance(request.get("event"), Mapping) else {}
    for key in text_keys:
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _ledger_resolution_for_text(text: str) -> dict[str, Any]:
    try:
        from maestro_context_packet import resolve_ledger_reference

        return resolve_ledger_reference(text)
    except Exception:
        return {"status": "NO_LEDGER_REFERENCE", "processing_allowed": False, "action_allowed": False}


_TEAM_ROSTER_AGENT_IDS = ("maestro", "chief", "cassandra", "guardian", "niles", "hermes")


def _is_team_roster_intent(text: str) -> bool:
    # The roster/org-chart is enumerable truth — never let the model freestyle it.
    lowered = text
    if "roster" in lowered:
        return True
    team_ref = ("my team" in lowered or "the team" in lowered or "on my team" in lowered
                or "my agents" in lowered or "what agents" in lowered or "which agents" in lowered
                or "who does what" in lowered)
    if team_ref:
        return True
    return False


def build_team_roster_answer(text: str) -> dict[str, Any]:
    """Deterministic team roster from agent_lane_registry seeds (the same source
    that authors doctrine SD-4). The model must never invent teammates."""
    try:
        from agent_lane_registry import DEFAULT_AGENT_LANE_SEEDS
        by_id = {s.agent_id: s for s in DEFAULT_AGENT_LANE_SEEDS}
    except Exception:
        by_id = {}
    lines = []
    for agent_id in _TEAM_ROSTER_AGENT_IDS:
        seed = by_id.get(agent_id)
        if seed is None:
            continue
        summary = str(getattr(seed, "role_summary", "") or "").split(". ")[0].rstrip(".")
        label = str(getattr(seed, "lane_label", "") or "")
        lines.append(f"- {seed.display_name} ({label}): {summary}.")
    if len(lines) < 4:
        # Fail closed to the doctrinal roster rather than a partial/confabulated one.
        lines = [
            "- Maestro (Operator Front Door): your main point of contact; understands intent and routes.",
            "- Chief (System Orchestration): coordinates work, plans, and system repair.",
            "- Cassandra / Clara Reid (Business Ops & Comms): money, invoices, client follow-up.",
            "- Guardian (Safety & Security): approvals, privacy, and the final safety boundary.",
            "- Niles (Music & Art Production): your producer/engineer/creative partner.",
            "- Hermes (Advisory Synthesis): observes the system and advises; no direct authority.",
        ]
    plain = "Your team is six agents:\n" + "\n".join(lines)
    one_line = "Your team: Maestro (front door), Chief (orchestration), Cassandra/Clara (business & money), Guardian (safety), Niles (music), Hermes (advisory)."
    return {
        "one_line_answer": one_line,
        "plain_summary": plain,
        "machine_proof": {
            "team_roster_deterministic": True,
            "team_roster_source": "agent_lane_registry_seeds",
            "model_call_performed": False,
            "agent_count": len(_TEAM_ROSTER_AGENT_IDS),
        },
    }


def classify_frontdoor_intent(text: str) -> tuple[str, bool, str]:
    normalized = _normalize(text)
    if not normalized:
        return ("empty", False, "empty_text")
    if _is_hermes_truthful_intent(normalized):
        return ("hermes_truthful_advisory", True, "")
    if _is_recurrence_rule_statement_intent(text):
        # Task 136b#1 (Fable probe 2026-07-07): a rule-shaped statement -- INCLUDING a
        # correction phrasing with schedule words ("actually St Anne's invoices should go
        # out on the 15th") -- must reach the rule store BEFORE the legacy operator-truth-
        # store intake can claim it. Two intakes competing for the same statement violates
        # the no-leftovers doctrine at the intake layer; checked first, unconditionally.
        return ("recurrence_rule_statement", True, "")
    if _is_operator_truth_correction_intent(text):
        return ("operator_truth_correction", True, "")
    if _is_operator_truth_query_intent(normalized):
        return ("operator_truth_query", True, "")
    if _is_system_health_readback_intent(normalized):
        return ("system_health_readback", True, "")
    if _is_advisory_interrogative_intent(normalized):
        return ("maestro_brain_freeform", True, "")
    if _is_send_or_reply_intent(normalized):
        return ("send_reply_email_action", False, "send_reply_email_action_intent_routes_to_staging")
    if _is_inbox_metadata_intent(normalized):
        return ("inbox_gmail_metadata", False, "gmail_metadata_queries_use_existing_staging_path_for_truthful_proof")
    if _is_calendar_or_briefing_intent(normalized):
        return ("calendar_or_briefing", False, "calendar_or_briefing_routes_to_staging")
    # Task 142: dispatch instructions ("...needs to go out — get it to the right
    # agent") route to staging BEFORE ledger-reference resolution can claim them
    # as freeform — an instruction must never end in the overview digest.
    if _is_dispatch_instruction_intent(normalized) and not _is_general_question_shape(normalized):
        return ("workflow_or_business_action", False, "workflow_or_business_action_routes_to_staging")
    ledger_resolution = _ledger_resolution_for_text(normalized)
    if ledger_resolution.get("status") == "NEEDS_CLARIFICATION":
        return ("ledger_reference_clarification", True, "")
    if ledger_resolution.get("status") == "RESOLVED" and ledger_resolution.get("blocked_action_requested") is not True:
        return ("maestro_brain_freeform", True, "")
    if _is_workflow_or_business_action_intent(normalized) and not _is_general_question_shape(normalized):
        return ("workflow_or_business_action", False, "workflow_or_business_action_routes_to_staging")
    if _is_date_awareness_intent(normalized):
        return ("date_awareness", True, "")
    if _is_status_capability_intent(normalized):
        return ("status_capability_readback", True, "")
    if _is_team_roster_intent(normalized):
        return ("team_roster", True, "")
    if _is_people_intent(normalized):
        return ("people_reference_query", True, "")
    if _is_system_knowledge_intent(normalized):
        return ("system_knowledge", True, "")
    return ("maestro_brain_freeform", True, "")


def _try_calendar(text: str, forwarded_session: Mapping[str, Any]) -> "MaestroCassandraResult | None":
    """Route a calendar READ/CREATE request to the live Google broker. Returns an answer
    result, or None to fall through to staging (briefings, delete, or broker unavailable).
    Delete is Guardian-gated and blocks on approval, so it stays on staging for now."""
    try:
        from calendar_router import detect_calendar_intent, route_calendar
    except Exception:
        return None
    intent = detect_calendar_intent(text)
    if intent is None:
        return None
    if intent == "delete":
        # Async Guardian-gated delete: parse the event, send the operator an approval,
        # reply immediately (the listener's CALDEL callback fires the actual delete).
        try:
            from calendar_router import _default_parse_event
            from calendar_delete_approval import request_calendar_delete

            parsed = _default_parse_event(text) or {}
            if not (parsed.get("title") and parsed.get("start_iso")):
                reply = "Tell me which event (title and time) and I'll send you a Guardian approval to delete it."
            else:
                _res = request_calendar_delete(
                    {"title": parsed["title"], "start_iso": parsed["start_iso"]}, agent="maestro"
                )
                reply = (
                    f"I've sent you a Guardian approval to delete “{parsed['title']}”. "
                    "Approve it and I'll remove it."
                    if _res.get("ok")
                    else f"I couldn't set that delete up ({_res.get('error', '')})."
                )
        except Exception:
            return None
    else:
        try:
            from google_access_broker import call as _broker_execute
            reply = route_calendar(text, agent="maestro", broker_execute=_broker_execute)
        except Exception:
            return None
    if not reply:
        return None
    return MaestroCassandraResult(
        status="ANSWER_READY",
        intent_class="calendar",
        allowed_to_call_handle=False,
        one_line_answer=_one_line_answer(reply),
        plain_summary=reply,
        mac_render_hint=MAC_RENDER_HINT,
        session_forwarded=forwarded_session,
        machine_proof={
            **_adapter_machine_proof(handle_called=False),
            "calendar_broker_called": True,
            "calendar_intent": intent,
            "protected_generate_called": False,
            "external_llm_invoked": False,
        },
    )


def answer_frontdoor_chat(
    text: str,
    *,
    session: Mapping[str, Any] | None = None,
    source_surface: str = "operator_maestro_chat",
    handle_fn: HandleFn | None = None,
    protected_generate_fn: ProtectedGenerateFn | None = None,
    _capsule: Any | None = None,
    agent: str = "maestro",
) -> MaestroCassandraResult:
    # ── Refusal-first guard (task 141) — FIRST tap, before intent
    # classification, workflow-package staging, clarify sessions, or any
    # model call. A refusal returns ANSWER_READY so the processor renders it
    # as the final reply and the staging fallthrough (the pass-1 "$500 send
    # -> gate-smoke diagnostics" path) never runs. Fail-open on guard errors.
    try:
        from operator_refusal_guard import refusal_reply_for_text as _refusal_reply_for_text

        _refusal_text = _refusal_reply_for_text(
            text, agent=agent, surface=source_surface
        )
    except Exception:
        _refusal_text = None
    if _refusal_text is not None:
        _refusal_lines = _refusal_text.splitlines()
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class="operator_refusal_guard",
            allowed_to_call_handle=False,
            one_line_answer=_refusal_lines[0] if _refusal_lines else _refusal_text,
            plain_summary=_refusal_text,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=filtered_session(session),
            machine_proof={
                "cassandra_handle_called": False,
                "model_call_performed": False,
                "external_llm_invoked": False,
                "protected_generate_called": False,
                "maestro_context_packet_used": False,
                "operator_refusal_guard": True,
                "workflow_package_staged": False,
            },
        )

    intent_class, allowed, reason = classify_frontdoor_intent(text)
    forwarded_session = filtered_session(session)
    if intent_class == "calendar_or_briefing":
        _cal = _try_calendar(text, forwarded_session)
        if _cal is not None:
            return _cal
    if not allowed:
        return MaestroCassandraResult(
            status="ROUTE_TO_STAGING",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            route_to_staging_reason=reason,
            session_forwarded=forwarded_session,
            machine_proof=_adapter_machine_proof(handle_called=False),
        )

    if intent_class == "operator_truth_correction":
        from operator_truth_store import capture_operator_truth_from_text

        records = capture_operator_truth_from_text(text, source_surface=source_surface)
        labels = [str(record.get("label") or record.get("entity_key")) for record in records]
        if labels:
            label_text = ", ".join(labels)
            answer = f"Operator truth updated for {label_text}. The shared store now outranks stale finance or reality context."
        else:
            answer = "I did not find a bounded entity correction to store. No action was taken."
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=answer,
            plain_summary=answer,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof={
                **_adapter_machine_proof(handle_called=False),
                "operator_truth_store_written": bool(records),
                "operator_truth_entities": labels,
            },
        )

    if intent_class == "recurrence_rule_statement":
        from recurrence_rule_intake import capture_recurrence_rule_statement
        from recurrence_rule_store import DEFAULT_DB_PATH as _DEFAULT_RULE_DB_PATH
        from recurrence_rule_store import RecurrenceRuleStore

        rule_db_path = (
            (session or {}).get("recurrence_rule_db_path") if isinstance(session, Mapping) else None
        ) or _DEFAULT_RULE_DB_PATH
        with RecurrenceRuleStore(rule_db_path) as store:
            capture = capture_recurrence_rule_statement(text, store=store, source_ref=source_surface)
        if capture is None:
            answer = "I couldn't quite parse that as a recurring rule. No rule was recorded."
            captured = False
            needs_review = False
        else:
            answer = str(capture["reply"])
            captured = capture["status"] == "captured"
            needs_review = capture["status"] == "needs_operator_review"
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=answer,
            plain_summary=answer,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof={
                **_adapter_machine_proof(handle_called=False),
                "recurrence_rule_captured": captured,
                "recurrence_rule_needs_operator_review": needs_review,
                "protected_generate_called": False,
                "external_llm_invoked": False,
                "local_model_invoked": False,
            },
        )

    if intent_class == "operator_truth_query":
        from operator_truth_store import find_operator_truth_for_text

        match = find_operator_truth_for_text(text)
        if match is None:
            answer = "I do not have a matching operator-truth record for that query. No model call was made."
            entity_key = ""
            label = ""
            value = ""
        else:
            entity_key, record = match
            label = str(record.get("label") or entity_key)
            value = " ".join(str(record.get("value") or "").split()).strip()
            answer = f"Yes. The operator truth store has {label}: {value}"
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=_one_line_answer(answer),
            plain_summary=answer,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof={
                **_adapter_machine_proof(handle_called=False),
                "operator_truth_query_performed": True,
                "operator_truth_store_read": True,
                "operator_truth_record_found": match is not None,
                "operator_truth_entity_key": entity_key,
                "operator_truth_label": label,
                "protected_generate_called": False,
                "maestro_context_packet_used": False,
                "external_llm_invoked": False,
            },
        )

    # Date queries are answered deterministically: the current date is a known
    # fact, not something to ask a language model to guess (it hallucinates it).
    if intent_class == "date_awareness":
        from datetime import datetime
        _now = datetime.now()
        _answer = f"Today is {_now.strftime('%Y-%m-%d')} ({_now.strftime('%A')})."
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=_answer,
            plain_summary=_answer,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof=_adapter_machine_proof(handle_called=False),
        )

    if intent_class == "system_health_readback":
        answer = build_chief_system_health_answer(session=session)
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=answer["one_line_answer"],
            plain_summary=answer["plain_summary"],
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof=_adapter_machine_proof(handle_called=False) | answer["machine_proof"],
        )

    if intent_class == "status_capability_readback" and _is_conversational_status_capability_prompt(_normalize(text)):
        return _answer_status_capability_with_brain(
            text,
            session=session,
            source_surface=source_surface,
            forwarded_session=forwarded_session,
            protected_generate_fn=protected_generate_fn,
            agent=agent,
        )

    if intent_class == "status_capability_readback":
        answer = build_truthful_status_capability_answer(
            session=session,
            focus=_status_capability_readback_focus(_normalize(text)),
        )
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=answer["one_line_answer"],
            plain_summary=answer["plain_summary"],
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof=_adapter_machine_proof(handle_called=False) | answer["machine_proof"],
        )

    if intent_class == "team_roster":
        answer = build_team_roster_answer(text)
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=answer["one_line_answer"],
            plain_summary=answer["plain_summary"],
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof=_adapter_machine_proof(handle_called=False) | answer["machine_proof"],
        )

    if intent_class == "people_reference_query":
        return _answer_people_query(
            text,
            session=session,
            source_surface=source_surface,
            forwarded_session=forwarded_session,
            protected_generate_fn=protected_generate_fn,
            _capsule=_capsule,
            agent=agent,
        )

    if intent_class == "hermes_truthful_advisory":
        answer = build_hermes_truthful_advisory_answer(text)
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=answer["one_line_answer"],
            plain_summary=answer["plain_summary"],
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof=_adapter_machine_proof(handle_called=False) | answer["machine_proof"],
        )

    if intent_class == "ledger_reference_clarification":
        answer = (
            "Which ledger do you mean: the bank/finance ledger or a system/control ledger? "
            "I can process a finance-ledger readback through the graded LIGHT gate, but I will not mutate a ledger."
        )
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=_one_line_answer(answer),
            plain_summary=answer,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof={
                **_adapter_machine_proof(handle_called=False),
                "ledger_reference_clarification_performed": True,
                "protected_generate_called": False,
                "maestro_context_packet_used": False,
                "external_llm_invoked": False,
            },
        )

    if intent_class == "maestro_brain_freeform":
        if source_surface != "operator_maestro_chat":
            return MaestroCassandraResult(
                status="ROUTE_TO_STAGING",
                intent_class=intent_class,
                allowed_to_call_handle=False,
                route_to_staging_reason="maestro_brain_freeform_requires_operator_maestro_chat_surface",
                session_forwarded=forwarded_session,
                machine_proof={
                    **_adapter_machine_proof(handle_called=False),
                    "protected_generate_called": False,
                    "maestro_context_packet_used": False,
                    "external_llm_invoked": False,
                },
            )
        return _answer_with_maestro_brain(
            text,
            session=session,
            source_surface=source_surface,
            forwarded_session=forwarded_session,
            protected_generate_fn=protected_generate_fn,
            _capsule=_capsule,
            agent=agent,
        )

    replies = list((handle_fn or _default_handle)(text, forwarded_session))
    plain_summary = _strip_internal_state_leaks(_plain_summary(replies))
    return MaestroCassandraResult(
        status="ANSWER_READY",
        intent_class=intent_class,
        allowed_to_call_handle=True,
        one_line_answer=_one_line_answer(plain_summary),
        plain_summary=plain_summary,
        mac_render_hint=MAC_RENDER_HINT,
        session_forwarded=forwarded_session,
        machine_proof=_adapter_machine_proof(handle_called=True),
    )


def _answer_status_capability_with_brain(
    text: str,
    *,
    session: Mapping[str, Any] | None,
    source_surface: str,
    forwarded_session: Mapping[str, Any],
    protected_generate_fn: ProtectedGenerateFn | None,
    agent: str = "maestro",
) -> MaestroCassandraResult:
    focus = _status_capability_readback_focus(_normalize(text))
    readback = build_truthful_status_capability_answer(session=session, focus=focus)
    base_proof = dict(readback["machine_proof"])
    source_refs = tuple(str(ref) for ref in base_proof.get("source_truth_refs", ()) if str(ref).strip())
    fact_value = str(readback.get("plain_summary") or readback.get("one_line_answer") or "").strip()
    fact = {
        "fact_id": f"status_capability:{_short_hash_for_packet(text, fact_value, source_refs)}",
        "topic": "status_capability",
        "label": "Truthful status and capability readback",
        "value": fact_value,
        "provenance": "generated_read_model_summary",
        "source_ref": ", ".join(source_refs) or CAPABILITY_INDEX_READ_MODEL,
        "pii_tier": "PUBLIC",
    }
    packet_engine_used = False
    packet_engine_fallback_used = False
    packet_engine_receipt: Mapping[str, Any] | None = None
    packet_engine_failure_type = ""
    try:
        from maestro_context_packet import build_maestro_context_packet

        if _packet_engine_enabled():
            try:
                from packet_engine import build_agent_packet

                context_packet = dict(
                    build_agent_packet(
                        agent=agent,
                        question=text,
                        question_class="status_capability_readback",
                        authority={
                            "source_surface": source_surface,
                            "send_hold": True,
                        },
                        session=session,
                        source_surface=source_surface,
                        require_real_truth=True,
                    )
                )
                packet_engine_receipt = dict(context_packet.get("packet_engine_receipt") or {})
                failures = packet_engine_receipt.get("failures") or ()
                if context_packet.get("status") == "PACKET_ENGINE_BUILD_FAILED" or failures:
                    packet_engine_fallback_used = True
                    if failures:
                        first_failure = next(iter(failures), {})
                        if isinstance(first_failure, Mapping):
                            packet_engine_failure_type = str(first_failure.get("type") or "")
                    context_packet = dict(
                        build_maestro_context_packet(
                            question=text,
                            session=session,
                            source_surface=source_surface,
                            require_real_truth=True,
                        )
                    )
                else:
                    packet_engine_used = True
            except Exception as exc:  # noqa: BLE001 - fail open to old packet path
                packet_engine_fallback_used = True
                packet_engine_failure_type = type(exc).__name__
                try:
                    from packet_engine import build_fallback_receipt

                    packet_engine_receipt = build_fallback_receipt(
                        agent=agent,
                        question_class="status_capability_readback",
                        failure=exc,
                    )
                except Exception:  # noqa: BLE001
                    packet_engine_receipt = None
                context_packet = dict(
                    build_maestro_context_packet(
                        question=text,
                        session=session,
                        source_surface=source_surface,
                        require_real_truth=True,
                    )
                )
        else:
            context_packet = dict(
                build_maestro_context_packet(
                    question=text,
                    session=session,
                    source_surface=source_surface,
                    require_real_truth=True,
                )
            )
        facts = [row for row in context_packet.get("facts", ()) if isinstance(row, Mapping)]
        context_packet["facts"] = [fact, *facts]
        refs = list(context_packet.get("source_refs", ()))
        refs.extend(source_refs)
        context_packet["source_refs"] = tuple(dict.fromkeys(str(ref) for ref in refs if str(ref).strip()))
        context_packet["packet_text"] = "\n".join(
            part
            for part in (
                str(context_packet.get("packet_text") or "").strip(),
                "STATUS/CAPABILITY FACTS FOR THIS ANSWER:",
                fact_value,
            )
            if part
        )
        context_packet["status_capability_focus"] = focus
    except Exception:
        context_packet = {
            "schema_version": "status_capability_context_packet_v0",
            "packet_id": f"status_capability_{_short_hash_for_packet(text, fact_value, source_refs)}",
            "question": text,
            "source_surface": source_surface,
            "facts": [fact] if fact_value else [],
            "source_refs": source_refs,
            "packet_text": "\n".join(
                part
                for part in (
                    "STATUS/CAPABILITY FACTS FOR THIS ANSWER:",
                    fact_value,
                )
                if part
            ),
        }

    if protected_generate_fn is None:
        from protected_generate import protected_generate_with_receipt

        outcome = protected_generate_with_receipt(text, context_packet=context_packet, agent=agent)
    else:
        outcome = protected_generate_fn(text, context_packet=context_packet)

    if hasattr(outcome, "text") and hasattr(outcome, "receipt"):
        answer_text = str(outcome.text)
        receipt = dict(outcome.receipt)
    elif isinstance(outcome, Mapping):
        answer_text = str(outcome.get("text") or outcome.get("answer") or "")
        receipt = dict(outcome.get("receipt") or {})
    else:
        answer_text = str(outcome or "")
        receipt = {
            "status": "ANSWER_READY",
            "decision": "INJECTED_PROTECTED_GENERATE",
            "external_llm_invoked": False,
            "local_model_invoked": True,
            "model_call_performed": True,
        }
    if receipt.get("model_call_performed") is not True:
        fallback_readback = str(readback.get("plain_summary") or readback.get("one_line_answer") or "").strip()
        if fallback_readback:
            agent_label = str(agent or "maestro").strip().capitalize()
            answer_text = (
                f"{agent_label} capability/status readback: {fallback_readback}"
                if agent_label.lower() != "maestro"
                else fallback_readback
            )
    answer_text = _strip_internal_state_leaks(answer_text).strip()
    if not answer_text:
        answer_text = str(readback.get("plain_summary") or readback.get("one_line_answer") or "").strip()

    proof_refs = tuple(str(ref) for ref in context_packet.get("source_refs", ()) if str(ref).strip())
    packet_engine_proof: dict[str, Any] = {
        "packet_engine_used": packet_engine_used,
        "packet_engine_fallback_used": packet_engine_fallback_used,
    }
    if packet_engine_receipt:
        packet_engine_proof["packet_engine_receipt_id"] = str(packet_engine_receipt.get("receipt_id") or "")
        packet_engine_proof["packet_engine_receipt_status"] = str(packet_engine_receipt.get("status") or "")
    if packet_engine_failure_type:
        packet_engine_proof["packet_engine_failure_type"] = packet_engine_failure_type
    return MaestroCassandraResult(
        status="ANSWER_READY",
        intent_class="status_capability_readback",
        allowed_to_call_handle=False,
        one_line_answer=_one_line_answer(answer_text),
        plain_summary=answer_text,
        mac_render_hint=MAC_RENDER_HINT,
        session_forwarded=forwarded_session,
        machine_proof={
            **_adapter_machine_proof(handle_called=False),
            **base_proof,
            **_protected_generate_receipt_machine_proof(receipt),
            "protected_generate_called": True,
            "maestro_context_packet_used": True,
            "context_packet_id": str(context_packet.get("packet_id") or ""),
            "status_capability_facts_injected": True,
            "status_capability_readback_performed": False,
            "status_capability_readback_available_as_facts": True,
            "source_truth_refs": proof_refs,
            "protected_generate_receipt_id": str(receipt.get("receipt_id") or ""),
            "protected_generate_audit_ref": str(receipt.get("audit_ref") or ""),
            "protected_generate_decision": str(receipt.get("decision") or ""),
            "send_hold_boundary_visible": True,
            "claims_trace_to_packet": True,
            **packet_engine_proof,
        },
    )


def _adapter_machine_proof(*, handle_called: bool) -> dict[str, Any]:
    return {
        "maestro_cassandra_adapter_invoked": True,
        "cassandra_handle_called": handle_called,
        "intent_gate_before_handle": True,
        "gmail_metadata_queries_route_to_staging": True,
        "send_reply_action_intent_routes_to_staging": True,
        "status_capability_readback_performed": False,
        "capability_index_used": False,
        "agent_presence_used": False,
        "chief_status_rail_used": False,
        "email_send_performed": False,
        "telegram_send_triggered": False,
        "agent_dispatch_performed": False,
        "worker_dispatch_performed": False,
        "gmail_reply_sent": False,
        "gmail_metadata_read_performed": False,
        "browser_access_performed": False,
        "coupa_access_performed": False,
        "portal_submitted": False,
        "ledger_mutation_performed": False,
        "workbook_mutation_performed": False,
        "pdf_export_performed": False,
        "paid_marking_performed": False,
        "runtime_execution_triggered": False,
        "send_authority_added": False,
        "used_ad_hoc_memory_as_authority": False,
        "text_response_only": True,
    }


def _answer_people_query(
    text: str,
    *,
    session: Mapping[str, Any] | None,
    source_surface: str,
    forwarded_session: Mapping[str, Any],
    protected_generate_fn: ProtectedGenerateFn | None,
    _capsule: Any | None = None,
    agent: str = "maestro",
) -> MaestroCassandraResult:
    registry_answer = _answer_people_query_from_contacts_registry(text)
    if registry_answer is not None:
        answer, proof = registry_answer
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class="people_reference_query",
            allowed_to_call_handle=False,
            one_line_answer=_one_line_answer(answer),
            plain_summary=answer,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof={
                **_adapter_machine_proof(handle_called=False),
                **proof,
                "people_reference_query_performed": True,
                "operator_truth_store_read": False,
                "operator_truth_record_found": False,
                "protected_generate_called": False,
                "maestro_context_packet_used": False,
                "external_llm_invoked": False,
            },
        )

    from operator_truth_store import find_operator_truth_for_text

    match = find_operator_truth_for_text(text)
    if match is not None:
        entity_key, record = match
        label = str(record.get("label") or entity_key)
        value = " ".join(str(record.get("value") or "").split()).strip()
        answer = f"{label}: {value}" if value else f"I found {label}, but the truth record has no value."
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class="people_reference_query",
            allowed_to_call_handle=False,
            one_line_answer=_one_line_answer(answer),
            plain_summary=answer,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof={
                **_adapter_machine_proof(handle_called=False),
                "people_reference_query_performed": True,
                "contacts_registry_read": True,
                "contacts_registry_record_found": False,
                "operator_truth_store_read": True,
                "operator_truth_record_found": True,
                "operator_truth_entity_key": entity_key,
                "operator_truth_label": label,
                "protected_generate_called": False,
                "maestro_context_packet_used": False,
                "external_llm_invoked": False,
            },
        )

    fallback = _answer_with_maestro_brain(
        text,
        session=session,
        source_surface=source_surface,
        forwarded_session=forwarded_session,
        protected_generate_fn=protected_generate_fn,
        _capsule=_capsule,
        agent=agent,
    )
    proof = {
        **dict(fallback.machine_proof or {}),
        "people_reference_query_performed": True,
        "contacts_registry_read": True,
        "contacts_registry_record_found": False,
        "operator_truth_store_read": True,
        "operator_truth_record_found": False,
        "people_reference_fell_through_to_protected_generate": bool(
            (fallback.machine_proof or {}).get("protected_generate_called")
        ),
    }
    return MaestroCassandraResult(
        status=fallback.status,
        intent_class="people_reference_query",
        allowed_to_call_handle=False,
        one_line_answer=fallback.one_line_answer,
        plain_summary=fallback.plain_summary,
        mac_render_hint=fallback.mac_render_hint,
        route_to_staging_reason=fallback.route_to_staging_reason,
        session_forwarded=fallback.session_forwarded,
        machine_proof=proof,
    )


def _contacts_db_path() -> str:
    try:
        from contacts_registry import DEFAULT_CONTACTS_DB_PATH

        return os.environ.get("OPENCLAW_CONTACTS_DB_PATH") or DEFAULT_CONTACTS_DB_PATH
    except Exception:
        return os.environ.get("OPENCLAW_CONTACTS_DB_PATH") or ""


def _contact_text_key(value: Any) -> str:
    text = str(value or "").lower().replace("'", "")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _contact_query_client_slugs(text: str, contacts: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    query_key = f" {_contact_text_key(text)} "
    slugs: list[str] = []
    for contact in contacts:
        clients = contact.get("connected_clients") or contact.get("connected_client") or ()
        if isinstance(clients, str):
            clients = (clients,)
        for client in clients:
            slug = str(client or "").strip()
            if not slug:
                continue
            terms = {
                _contact_text_key(slug),
                _contact_text_key(slug.replace("-", " ")),
                _contact_text_key(slug.replace("-", "")),
            }
            if any(term and f" {term} " in query_key for term in terms) and slug not in slugs:
                slugs.append(slug)
    return tuple(slugs)


def _format_contact_for_people_answer(contact: Mapping[str, Any], *, client_slug: str) -> str:
    name = str(contact.get("name") or contact.get("id") or "Contact").strip()
    role = str(contact.get("role") or "contact").strip()
    return f"{name} ({role}; client: {client_slug})"


def _answer_people_query_from_contacts_registry(text: str) -> tuple[str, dict[str, Any]] | None:
    db_path = _contacts_db_path()
    proof: dict[str, Any] = {
        "contacts_registry_read": False,
        "contacts_registry_record_found": False,
        "contacts_registry_ref": f"contacts_registry:{db_path}" if db_path else "contacts_registry",
        "contacts_registry_client_slug": "",
        "contacts_registry_contact_ids": [],
    }
    try:
        from contacts_registry import ContactsRegistry

        registry = ContactsRegistry(db_path, seed=True)
        all_contacts = registry.list_contacts()
        proof["contacts_registry_read"] = True
        slugs = _contact_query_client_slugs(text, all_contacts)
        if not slugs:
            return None
        client_slug = slugs[0]
        contacts = registry.get_contacts_for_client(client_slug)
    except Exception as exc:
        proof["contacts_registry_error"] = str(exc)
        return None

    if not contacts:
        return None

    proof["contacts_registry_record_found"] = True
    proof["contacts_registry_client_slug"] = client_slug
    proof["contacts_registry_contact_ids"] = [str(contact.get("id") or "") for contact in contacts]
    contact_text = "; ".join(
        _format_contact_for_people_answer(contact, client_slug=client_slug)
        for contact in contacts
    )
    answer = f"Contacts registry for {client_slug}: {contact_text}."
    return answer, proof


def _answer_with_maestro_brain(
    text: str,
    *,
    session: Mapping[str, Any] | None,
    source_surface: str,
    forwarded_session: Mapping[str, Any],
    protected_generate_fn: ProtectedGenerateFn | None,
    _capsule: Any | None = None,
    agent: str = "maestro",
) -> MaestroCassandraResult:
    # ── INTERPRETER-LM fact selection bridge (flag-gated, ADDITIVE) ──────────
    # When OPENCLAW_INTERPRETER_LM is on AND the raw session carries an
    # "interpreter_fact_selection" hint (injected upstream by the interpreter
    # divert in openclaw_request_processor), forward it to the packet builder so
    # the interpreter-selected read-models are elevated. When the flag is OFF or
    # no hint is present: _fact_selection stays None → byte-identical pre-edit
    # behaviour. This is advisory-only ordering: it never drops or rewrites facts.
    _fact_selection = None
    try:
        from interpreter_lm import _interpreter_enabled

        if _interpreter_enabled() and isinstance(session, Mapping):
            _raw_selection = session.get("interpreter_fact_selection")
            if isinstance(_raw_selection, (list, tuple)) and _raw_selection:
                _fact_selection = [str(item) for item in _raw_selection if str(item).strip()]
    except Exception:  # noqa: BLE001 — never break the brain path on a hint
        _fact_selection = None
    # ─────────────────────────────────────────────────────────────────────────
    packet_engine_used = False
    packet_engine_fallback_used = False
    packet_engine_receipt: Mapping[str, Any] | None = None
    packet_engine_failure_type = ""
    try:
        from maestro_context_packet import build_maestro_context_packet

        # ── CONTINUITY CAPSULE threading (flag-gated, ADDITIVE) ──────────────
        # When ON and a capsule is provided, pass it to build_maestro_context_packet
        # so it can populate packet_entity_aliases + packet_source_revision (Edit 2).
        # When OFF or no capsule: call is identical to pre-edit (capsule=None default).
        _capsule_arg = _capsule if _continuity_enabled() else None
        if _packet_engine_enabled():
            try:
                from packet_engine import build_agent_packet

                context_packet = build_agent_packet(
                    agent=agent,
                    question=text,
                    question_class="maestro_brain_freeform",
                    authority={
                        "source_surface": source_surface,
                        "send_hold": True,
                    },
                    session=session,
                    source_surface=source_surface,
                    require_real_truth=True,
                    capsule=_capsule_arg,
                    fact_selection=_fact_selection,
                )
                packet_engine_receipt = dict(context_packet.get("packet_engine_receipt") or {})
                failures = packet_engine_receipt.get("failures") or ()
                if context_packet.get("status") == "PACKET_ENGINE_BUILD_FAILED" or failures:
                    packet_engine_fallback_used = True
                    if failures:
                        first_failure = next(iter(failures), {})
                        if isinstance(first_failure, Mapping):
                            packet_engine_failure_type = str(first_failure.get("type") or "")
                    context_packet = build_maestro_context_packet(
                        question=text,
                        session=session,
                        source_surface=source_surface,
                        require_real_truth=True,
                        capsule=_capsule_arg,
                        fact_selection=_fact_selection,
                    )
                else:
                    packet_engine_used = True
            except Exception as exc:  # noqa: BLE001 - fail open to old packet path
                packet_engine_fallback_used = True
                packet_engine_failure_type = type(exc).__name__
                try:
                    from packet_engine import build_fallback_receipt

                    packet_engine_receipt = build_fallback_receipt(
                        agent=agent,
                        question_class="maestro_brain_freeform",
                        failure=exc,
                    )
                except Exception:  # noqa: BLE001
                    packet_engine_receipt = None
                context_packet = build_maestro_context_packet(
                    question=text,
                    session=session,
                    source_surface=source_surface,
                    require_real_truth=True,
                    capsule=_capsule_arg,
                    fact_selection=_fact_selection,
                )
        else:
            context_packet = build_maestro_context_packet(
                question=text,
                session=session,
                source_surface=source_surface,
                require_real_truth=True,
                capsule=_capsule_arg,
                fact_selection=_fact_selection,
            )
    except Exception as exc:
        answer = (
            "I don't have a grounded Maestro packet for that yet. "
            "I will not invent the answer; Chief can review the missing truth input."
        )
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class="maestro_brain_freeform",
            allowed_to_call_handle=False,
            one_line_answer=_one_line_answer(answer),
            plain_summary=answer,
            mac_render_hint=MAC_RENDER_HINT,
            route_to_staging_reason=f"context_packet_unavailable:{type(exc).__name__}",
            session_forwarded=forwarded_session,
            machine_proof={
                **_adapter_machine_proof(handle_called=False),
                "maestro_context_packet_used": False,
                "protected_generate_called": False,
                "context_packet_error": type(exc).__name__,
                "external_llm_invoked": False,
                "local_model_invoked": False,
                "model_call_performed": False,
            },
        )

    # ── PACKET-DELTA hook (flag-gated OPENCLAW_PACKET_DELTA, default off, FAIL-OPEN) ──
    # Integration point for cross-turn fact de-dup, keyed on the capsule's
    # (conversation_id, agent). KEEP OFF on this path — and here's the honest why:
    #   • The front-door local model is STATELESS: protected_generate builds the prompt
    #     fresh from this single packet every call and retains nothing between calls.
    #     So "drop_seen" would STARVE the model of facts it still needs each turn.
    #   • "prioritize" (the safe default) only reorders; build_frontdoor_prompt then
    #     re-ranks facts by relevance tier + lexical overlap, using original order only
    #     as a deep tiebreak — so the reorder is ~a no-op here. The live budgeter is
    #     already the real bloat control.
    # Packet-delta's real payoff is for STATEFUL consumers (sessions/agents that retain
    # prior turns). This hook stays wired (tested, fail-open) for that future; default off.
    try:
        from packet_delta import maybe_apply_packet_delta

        _conv_id = getattr(_capsule, "conversation_id", "") if _capsule is not None else ""
        _delta_agent = getattr(_capsule, "agent_id", "") or "maestro"
        context_packet, _delta_stats = maybe_apply_packet_delta(
            context_packet, conversation_id=_conv_id, agent=_delta_agent,
        )
        if _delta_stats.get("deduped"):
            print(f"[maestro] packet-delta: {_delta_stats}", flush=True)
    except Exception:  # noqa: BLE001 — never break the brain on the delta layer
        pass
    # ─────────────────────────────────────────────────────────────────────────

    if protected_generate_fn is None:
        from protected_generate import protected_generate_with_receipt

        outcome = protected_generate_with_receipt(text, context_packet=context_packet, agent=agent)
    else:
        outcome = protected_generate_fn(text, context_packet=context_packet)

    if hasattr(outcome, "text") and hasattr(outcome, "receipt"):
        answer_text = str(outcome.text)
        receipt = dict(outcome.receipt)
    elif isinstance(outcome, Mapping):
        answer_text = str(outcome.get("text") or outcome.get("answer") or "")
        receipt = dict(outcome.get("receipt") or {})
    else:
        answer_text = str(outcome or "")
        receipt = {
            "status": "ANSWER_READY",
            "decision": "INJECTED_PROTECTED_GENERATE",
            "external_llm_invoked": False,
            "local_model_invoked": True,
            "model_call_performed": True,
        }
    if _receipt_or_packet_has_skill("music_law_advisory", receipt=receipt, context_packet=context_packet):
        try:
            from chief_musiclaw_brain import _ensure_musiclaw_safety

            answer_text = _ensure_musiclaw_safety(answer_text)
        except Exception:
            pass
    answer_text = _strip_internal_state_leaks(answer_text) or (
        "I don't have that in the current Maestro packet."
    )
    answer_text = _enforce_answer_topic_presentation(answer_text, context_packet)
    # ── SELF-IMPROVEMENT LOOP ─────────────────────────────────────────────────
    # If the operator just agreed to an improvement the agent recommended last turn, file it
    # as a REAL build request (-> PROPOSED + Guardian). Otherwise, if they're talking about
    # the agent / its improvements, record the one concrete gap so a "yeah do it" next turn
    # files it. Grounded (only curated gaps file) + fail-open.
    try:
        _conv_id = getattr(_capsule, "conversation_id", "") if _capsule is not None else ""
        if _conv_id:
            from self_improvement_request import maybe_file_on_agreement, record_recommendation

            _filed = maybe_file_on_agreement(_conv_id, text, agent=agent)
            if _filed and _filed.get("filed"):
                answer_text = (answer_text.rstrip() +
                               " — on it; I've put that in, you'll get a Guardian approval to build it.")
            else:
                from social_intent import is_self_referential

                if is_self_referential(text):
                    from self_knowledge import next_improvement

                    _nxt = next_improvement()
                    if _nxt:
                        record_recommendation(_conv_id, _nxt["id"])
    except Exception:
        pass
    # NOTE: jargon teaching + comedy-as-diagnostic + claim detection were CONSOLIDATED into the
    # single author-aware operator-surface pipeline (_enrich_operator_surface in
    # openclaw_request_processor) so EVERY agent voice gets them on the FINAL operator_message —
    # not just this Maestro brain path. They no longer run here (would double-process the surface).
    # Live dankifier hook: score the packet just used + queue grounded gaps, so the system
    # gets danker the more it's used. Never blocks or alters the answer (already finalized
    # above) — observe_packet_dankness swallows all errors; enrichment runs in a separate drain.
    try:
        from packet_dankness_critic import observe_packet_dankness

        # COVERAGE: observe as the ACTUAL agent being answered (was hardcoded "maestro", which made
        # the dankifier loop churn on maestro alone and never enrich the other 5 agents' packets).
        observe_packet_dankness(context_packet, text, agent)
    except Exception:
        pass
    # Defense-in-depth (persona-voice layer): flag if any machine-contract leaked past the
    # strip above. Observability only — never alters or blocks the reply. Surfaces strip gaps.
    try:
        from operator_surface_guard import check_machine_contract_leak

        _leak = check_machine_contract_leak(answer_text, audience="ELIWINSHIP")
        if _leak.is_leak:
            print(f"[maestro] operator-surface leak survived strip: {_leak.reasons}", flush=True)
    except Exception:
        pass
    # (Claim detection now runs centrally in _enrich_operator_surface on the FINAL operator_message
    # for every agent — see the consolidation note above.)
    proof_refs = tuple(str(ref) for ref in context_packet.get("source_refs", ()) if str(ref).strip())
    packet_engine_proof: dict[str, Any] = {
        "packet_engine_used": packet_engine_used,
        "packet_engine_fallback_used": packet_engine_fallback_used,
    }
    if packet_engine_receipt:
        packet_engine_proof["packet_engine_receipt_id"] = str(packet_engine_receipt.get("receipt_id") or "")
        packet_engine_proof["packet_engine_receipt_status"] = str(packet_engine_receipt.get("status") or "")
    if packet_engine_failure_type:
        packet_engine_proof["packet_engine_failure_type"] = packet_engine_failure_type
    return MaestroCassandraResult(
        status="ANSWER_READY",
        intent_class="maestro_brain_freeform",
        allowed_to_call_handle=False,
        one_line_answer=_one_line_answer(answer_text),
        plain_summary=answer_text,
        mac_render_hint=MAC_RENDER_HINT,
        session_forwarded=forwarded_session,
        machine_proof={
            **_adapter_machine_proof(handle_called=False),
            **_protected_generate_receipt_machine_proof(receipt),
            "protected_generate_called": True,
            "maestro_context_packet_used": True,
            "context_packet_id": str(context_packet.get("packet_id") or ""),
            "proof_refs": proof_refs,
            "source_truth_refs": proof_refs,
            "protected_generate_receipt_id": str(receipt.get("receipt_id") or ""),
            "protected_generate_audit_ref": str(receipt.get("audit_ref") or ""),
            "protected_generate_decision": str(receipt.get("decision") or ""),
            "send_hold_boundary_visible": True,
            "claims_trace_to_packet": True,
            # Interpreter-LM traceability (advisory only — None/empty when off):
            "interpreter_fact_selection_applied": list(_fact_selection or []),
            "interpreter_fact_selection_used": bool(_fact_selection),
            **packet_engine_proof,
        },
    )


def build_hermes_truthful_advisory_answer(text: str) -> dict[str, Any]:
    normalized = _normalize(text)
    mode = _hermes_truthful_mode(normalized)
    target = _route_target(normalized)
    target_candidate = _route_target_candidate(normalized)
    base_proof = {
        "hermes_truthful_advisory_performed": True,
        "hermes_reply_mode": mode,
        "hermes_real_agent_bridge_available": False,
        "hermes_route_receipt_written": False,
        "hermes_local_helpers_are_not_agent_bridges": True,
        "hermes_skill_guess_performed": False,
        "hermes_gateway_started": False,
        "agent_dispatch_performed": False,
        "worker_dispatch_performed": False,
        "email_send_performed": False,
        "external_send_performed": False,
        "send_hold_boundary_visible": True,
        "source_truth_refs": (
            ".claude/commands/hermes.md",
            "openclaw_hermes_sidecar.py",
            "templates/agent/hermes_advisory_packet_template.json",
        ),
    }
    if mode == "route_request":
        target_label = target or target_candidate or "the requested agent"
        one_line = f"Hermes cannot route this to {target_label} from this surface."
        detail = (
            "That route target is not a canonical OpenClaw agent route."
            if not target and target_candidate
            else "Hermes is advisory here: it can describe adapter/protocol boundaries and recommend a safe review packet."
        )
        plain = "\n".join(
            [
                one_line,
                detail,
                "No agent handoff ran, no route receipt was written, and no message was sent.",
                "A real handoff needs a sanctioned bridge with a receipt; local helper tools are not agent bridges.",
                "SEND_HOLD remains in force.",
            ]
        )
        base_proof["requested_route_target"] = target_label
        base_proof["requested_route_target_is_canonical_agent"] = bool(target)
    elif mode == "send_money_denial":
        one_line = "Hermes cannot send messages, trigger payments, or move money from this surface."
        plain = "\n".join(
            [
                one_line,
                "This request is denied for live action and can only be staged for an operator-controlled review path.",
                "No external send, payment, ledger mutation, route receipt, service start, or agent dispatch occurred.",
                "SEND_HOLD remains in force.",
            ]
        )
        base_proof["requested_route_target"] = target_candidate or ""
        base_proof["requested_route_target_is_canonical_agent"] = False
    elif mode == "route_inventory":
        one_line = "Hermes has no proven live agent-routing bridge from this surface."
        plain = "\n".join(
            [
                one_line,
                "Real agent bridges available to Hermes here: none proven.",
                "Local helper tools and read-model sidecars may support advisory review, but they are not dispatch routes.",
                "Hermes can recommend or stage an advisory packet; it cannot send, enqueue, start services, or bypass SEND_HOLD.",
                "SEND_HOLD remains in force.",
            ]
        )
    else:
        one_line = "Hermes is an advisory boundary reviewer, not a live routing or send gateway."
        plain = "\n".join(
            [
                one_line,
                "Current scope: adapter/protocol boundary review, bridge posture, connector wrapper readiness, sidecar inventory, and authority-fit checks.",
                "Hard no: no external send, Gmail/Coupa/browser access, ledger/workbook/PDF mutation, service start, model-provider fallback, or agent dispatch from this surface.",
                "Hermes can describe or recommend a bounded review packet; Chief/operator-controlled promotion is required for any action.",
                "SEND_HOLD remains in force.",
            ]
        )
    # Hermes context packet — grounded posture facts (canonical route targets, blocked
    # output kinds, SEND_HOLD posture, authority flags hard-False) from real config.
    # READ-ONLY, additive; adds no send/execute capability. Failures silently skipped.
    try:
        from hermes_context_packet import build_hermes_context_packet
        _hpt = str(build_hermes_context_packet(question=text).get("packet_text") or "").strip()
    except Exception:
        _hpt = ""
    if _hpt:
        if len(_hpt) > 900:  # keep the operator reply under the Telegram cap
            _hpt = _hpt[:900].rstrip() + " …"
        plain = f"{plain}\n\n{_hpt}"
        base_proof["hermes_context_packet_used"] = True
    return {
        "one_line_answer": _one_line_answer(one_line),
        "plain_summary": _strip_internal_state_leaks(plain),
        "machine_proof": base_proof,
    }


def build_truthful_status_capability_answer(
    *,
    session: Mapping[str, Any] | None = None,
    focus: str = "status",
) -> dict[str, Any]:
    root = _read_model_root_from_session(session)
    capability_payload, capability_path = _read_json_read_model(root, CAPABILITY_INDEX_READ_MODEL)
    presence_payload, presence_path = _read_json_read_model(root, AGENT_PRESENCE_READ_MODEL)
    chief_payload, chief_path = _read_json_read_model(root, CHIEF_STATUS_READ_MODEL)
    readback_focus = _normalize_readback_focus(focus)

    capabilities = [
        row
        for row in capability_payload.get("generic_capabilities", ())
        if isinstance(row, Mapping)
    ]
    live_capabilities = [
        row
        for row in capabilities
        if str(row.get("capability_status") or "") == "LIVE_IMPLEMENTED"
    ]
    nonexecuting_capabilities = [
        row
        for row in capabilities
        if str(row.get("capability_status") or "") in {"IMPLEMENTED_NON_EXECUTING", "READ_MODEL_ONLY"}
    ]
    blocked_or_future = [
        row
        for row in capabilities
        if str(row.get("capability_status") or "")
        in {"CONTRACT_ONLY", "FUTURE_GATED", "BLOCKED_UNSAFE", "PROPOSED_CANDIDATE"}
    ]
    agents = [
        row
        for row in presence_payload.get("agents", ())
        if isinstance(row, Mapping)
    ]
    online_agents = [
        row
        for row in agents
        if str(row.get("actual_state") or "").lower() == "online"
    ]
    roster_entries = _agent_roster_entries(agents, limit=8)
    next_safe_move = _next_safe_move(presence_payload, agents)
    proof_refs = tuple(
        path.as_posix()
        for payload, path in (
            (capability_payload, capability_path),
            (presence_payload, presence_path),
            (chief_payload, chief_path),
        )
        if payload
    )

    if not capability_payload:
        one_line = "I cannot truthfully list capabilities yet because the capability index read model is missing."
        plain = "\n".join(
            [
                one_line,
                "",
                "I will not invent a capability list. Ask again after `generated/read_models/openclaw_capability_index.json` is present.",
            ]
        )
    else:
        online_phrase = (
            f"{len(online_agents)} agents are online in the presence read model"
            if presence_payload
            else "agent presence is unverified in this readback"
        )
        live_names = _capability_names(live_capabilities, limit=5)
        nonexec_names = _capability_names(nonexecuting_capabilities, limit=5)
        blocked_names = _capability_names(blocked_or_future, limit=4)
        chief_summary = _chief_status_summary(chief_payload)
        one_line = _status_capability_one_line(
            readback_focus=readback_focus,
            online_phrase=online_phrase,
            live_count=len(live_capabilities),
            nonexecuting_count=len(nonexecuting_capabilities),
            live_names=live_names,
            roster_entries=roster_entries,
            next_safe_move=next_safe_move,
        )
        lines = [
            "Here is the truthful readback from current generated state.",
            "",
            f"- Status: {online_phrase}.",
            f"- Proven live-implemented rails: {_join_names(live_names)}.",
            f"- Safe non-executing readback rails: {_join_names(nonexec_names)}.",
        ]
        if roster_entries:
            lines.append(f"- Agent roster: {_join_names(roster_entries)}.")
        if next_safe_move:
            lines.append(f"- Next safe move: {next_safe_move}.")
        if chief_summary:
            lines.append(f"- Chief: {chief_summary}.")
        if blocked_names:
            lines.append(f"- Not claimed as usable here: {_join_names(blocked_names)}.")
        lines.extend(
            [
                "- From this chat, I can answer status and capability questions from those read models.",
                "- I cannot claim email send, Gmail read, browser/Coupa access, workflow execution, deploy, restart, merge, payment, or ledger mutation from this front door.",
                f"- Proof refs: {_join_names(proof_refs)}.",
            ]
        )
        plain = "\n".join(lines)

    return {
        "one_line_answer": _one_line_answer(one_line),
        "plain_summary": plain,
        "machine_proof": {
            "status_capability_readback_performed": True,
            "readback_focus": readback_focus,
            "capability_index_used": bool(capability_payload),
            "agent_presence_used": bool(presence_payload),
            "agent_roster_summarized": bool(roster_entries),
            "chief_status_rail_used": bool(chief_payload),
            "source_truth_refs": proof_refs,
            "live_implemented_capability_count": len(live_capabilities),
            "nonexecuting_capability_count": len(nonexecuting_capabilities),
            "blocked_or_future_capability_count": len(blocked_or_future),
            "live_implemented_capability_ids": tuple(
                str(row.get("capability_id") or "") for row in live_capabilities
            ),
            "nonexecuting_capability_ids": tuple(
                str(row.get("capability_id") or "") for row in nonexecuting_capabilities
            ),
            "blocked_or_future_capability_ids_not_claimed": tuple(
                str(row.get("capability_id") or "") for row in blocked_or_future
            ),
            "capability_claims_derived_from_read_models": True,
            "unverified_capability_claims_filtered": True,
            "external_send_performed": False,
            "runtime_execution_triggered": False,
        },
    }


def build_chief_system_health_answer(
    *,
    session: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = _read_model_root_from_session(session)
    presence_payload, presence_path = _read_json_read_model(root, AGENT_PRESENCE_READ_MODEL)
    chief_payload, chief_path = _read_json_read_model(root, CHIEF_STATUS_READ_MODEL)
    sync_payload, sync_path = _read_json_read_model(root, SYNC_HEALTH_READ_MODEL)

    agents = [
        row
        for row in presence_payload.get("agents", ())
        if isinstance(row, Mapping)
    ]
    agent_lines: list[str] = []
    online_agents: list[str] = []
    degraded_or_offline: list[str] = []
    for row in agents:
        agent_id = str(row.get("agent_id") or row.get("display_name") or "unknown").strip()
        display = str(row.get("display_name") or agent_id).strip()
        state = str(row.get("actual_state") or "unknown").strip().lower() or "unknown"
        label = agent_id or display
        if state == "online":
            online_agents.append(label)
        elif state != "metadata_available":
            degraded_or_offline.append(f"{label}:{state}")
        agent_lines.append(f"{display}: {state}")

    total_agents = int(presence_payload.get("agent_count") or len(agents) or 0)
    online_count = int(presence_payload.get("online_count") or len(online_agents) or 0)
    chief_status = str(chief_payload.get("chief_current_status") or chief_payload.get("rail_status") or "unknown").strip()
    chief_summary = _chief_status_summary(chief_payload) or "Chief status rail unavailable"
    mirror_status = str(sync_payload.get("mirror_status") or "unknown").strip()
    display_status = str(sync_payload.get("display_status") or "unknown").strip()
    trust_status = str(sync_payload.get("trust_status") or "unknown").strip()
    last_mac = sync_payload.get("last_mac_completion") if isinstance(sync_payload.get("last_mac_completion"), Mapping) else {}
    last_mac_time = str(last_mac.get("time") or "").strip()
    last_mac_status = str(last_mac.get("status") or "").strip()

    source_refs = tuple(
        path.as_posix()
        for payload, path in (
            (presence_payload, presence_path),
            (chief_payload, chief_path),
            (sync_payload, sync_path),
        )
        if payload
    )
    one_line = (
        f"Chief system health: front door={chief_status or 'unknown'}; "
        f"agent response stack={online_count}/{total_agents} online; "
        f"sync mirror={mirror_status}, display={display_status}."
    )
    lines = [
        "Chief system health readback from current read models.",
        f"- Front door: {chief_summary}.",
        f"- Agent response stack: {_join_names(agent_lines)}.",
        f"- Sync: mirror={mirror_status}, display={display_status}, trust={trust_status}.",
    ]
    if last_mac_time:
        lines.append(f"- Last Mac sync: {last_mac_time} ({last_mac_status or 'unknown'}).")
    if degraded_or_offline:
        lines.append(f"- Degraded/offline agents: {_join_names(degraded_or_offline)}.")
    lines.extend(
        [
            "- Sources: " + _join_names(source_refs) + ".",
            "- Boundaries: no model call, no send, no repair, no restart, no dispatch, no ledger mutation.",
        ]
    )
    return {
        "one_line_answer": _one_line_answer(one_line),
        "plain_summary": "\n".join(lines),
        "machine_proof": {
            "system_health_readback_performed": True,
            "agent_presence_used": bool(presence_payload),
            "chief_status_rail_used": bool(chief_payload),
            "sync_health_used": bool(sync_payload),
            "source_truth_refs": source_refs,
            "online_agent_count": online_count,
            "agent_count": total_agents,
            "online_agents": tuple(online_agents),
            "degraded_or_offline_agents": tuple(degraded_or_offline),
            "frontdoor_status": chief_status,
            "sync_mirror_status": mirror_status,
            "sync_display_status": display_status,
            "protected_generate_called": False,
            "model_call_performed": False,
            "local_model_invoked": False,
            "external_llm_invoked": False,
            "maestro_context_packet_used": False,
            "runtime_execution_triggered": False,
            "agent_dispatch_performed": False,
        },
    }


def _read_model_root_from_session(session: Mapping[str, Any] | None) -> Path:
    if isinstance(session, Mapping):
        for key in ("read_model_root", "read_model_root_path", "generated_read_model_root"):
            value = session.get(key)
            if isinstance(value, str) and value.strip():
                return Path(value)
    return DEFAULT_READ_MODEL_ROOT


def _read_json_read_model(root: Path, filename: str) -> tuple[dict[str, Any], Path]:
    path = root / filename
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, path
    return (payload if isinstance(payload, dict) else {}), path


def _capability_names(rows: Sequence[Mapping[str, Any]], *, limit: int) -> tuple[str, ...]:
    names = [
        str(row.get("capability_name") or row.get("capability_id") or "").strip()
        for row in rows
        if str(row.get("capability_name") or row.get("capability_id") or "").strip()
    ]
    return tuple(names[:limit])


def _join_names(names: Sequence[str]) -> str:
    return ", ".join(str(name) for name in names if str(name).strip()) or "none verified"


def _normalize_readback_focus(focus: str) -> str:
    normalized = _normalize(focus).replace("-", "_").replace(" ", "_")
    if normalized in {"capability", "capabilities"}:
        return "capability"
    if normalized in {"agent_roster", "agents", "roster"}:
        return "agent_roster"
    if normalized in {"next_safe_move", "safe_move", "next_move"}:
        return "next_safe_move"
    return "status"


def _agent_roster_entries(rows: Sequence[Mapping[str, Any]], *, limit: int) -> tuple[str, ...]:
    entries: list[str] = []
    for row in rows:
        display = str(row.get("display_name") or row.get("agent_id") or "").strip()
        if not display:
            continue
        state = str(row.get("actual_state") or "unknown").strip() or "unknown"
        lane = str(row.get("lane_id") or "").strip()
        role = str(row.get("role") or row.get("reason") or "").strip()
        details = "; ".join(part for part in (state, lane, role) if part)
        entries.append(f"{display} ({details})" if details else display)
        if len(entries) >= limit:
            break
    return tuple(entries)


def _next_safe_move(
    presence_payload: Mapping[str, Any],
    agents: Sequence[Mapping[str, Any]],
) -> str:
    top_level = str(presence_payload.get("next_safe_move") or "").strip()
    if top_level:
        return top_level.rstrip(".")
    for row in agents:
        move = str(row.get("next_safe_move") or "").strip()
        if move and move.lower() != "no recovery needed.":
            return move.rstrip(".")
    return "Use the readback rails only; no runtime action is authorized from this front door"


def _status_capability_one_line(
    *,
    readback_focus: str,
    online_phrase: str,
    live_count: int,
    nonexecuting_count: int,
    live_names: Sequence[str],
    roster_entries: Sequence[str],
    next_safe_move: str,
) -> str:
    if readback_focus == "agent_roster":
        return f"Agent roster: {_join_names(roster_entries)}."
    if readback_focus == "next_safe_move":
        return f"Next safe move: {next_safe_move}."
    if readback_focus == "capability":
        return (
            f"I can help with truthful readbacks such as {_join_names(live_names)}; "
            "sends, Gmail, calendar, browser, deploy, and workflow actions stay gated."
        )
    return (
        f"OpenClaw status: {online_phrase}; "
        f"{live_count} live-implemented rails and "
        f"{nonexecuting_count} non-executing readback rails are listed."
    )


def _chief_status_summary(payload: Mapping[str, Any]) -> str:
    if not payload:
        return ""
    status = str(payload.get("chief_current_status") or payload.get("rail_status") or "").strip()
    role = payload.get("chief_current_proven_role")
    role_summary = str(role.get("role_summary") or "").strip() if isinstance(role, Mapping) else ""
    if status and role_summary:
        return f"{status}; {role_summary}"
    return status or role_summary


def _plain_summary(replies: Sequence[str]) -> str:
    lines = [str(reply).strip() for reply in replies if str(reply).strip()]
    return "\n".join(lines) or "Maestro did not receive a Cassandra answer."


def _one_line_answer(text: str) -> str:
    first_line = next((line.strip("- ").strip() for line in text.splitlines() if line.strip()), text.strip())
    words = first_line.split()
    if len(words) <= 30:
        return " ".join(words)
    return " ".join(words[:29] + ["..."])


def _normalize(text: str) -> str:
    return " ".join(str(text or "").lower().strip().replace("’", "'").split())


def _is_hermes_addressed(text: str) -> bool:
    return bool(re.search(r"\bhermes\b", text))


def _is_hermes_route_request(text: str) -> bool:
    return bool(
        _is_hermes_addressed(text)
        and re.search(r"\b(?:route|send|handoff|hand off|pass|forward|dispatch)\b.{0,50}\bto\b", text)
    )


def _is_hermes_route_inventory_request(text: str) -> bool:
    inventory_phrases = (
        "what can you route to",
        "who can you route to",
        "what agents can you route to",
        "which agents can you route",
        "route inventory",
        "routing inventory",
        "real agent bridges",
        "agent bridges",
    )
    return _is_hermes_addressed(text) and any(phrase in text for phrase in inventory_phrases)


def _is_hermes_capability_prompt(text: str) -> bool:
    status_readback_phrases = (
        "what's going on",
        "whats going on",
        "what is going on",
        "what's happening",
        "whats happening",
        "what is happening",
    )
    if any(phrase in text for phrase in status_readback_phrases):
        return False
    capability_phrases = (
        "what's your job",
        "whats your job",
        "what is your job",
        "what do you do",
        "what can you do",
        "what are you",
        "what is hermes",
        "who are you",
    )
    return _is_hermes_addressed(text) and any(phrase in text for phrase in capability_phrases)


def _is_hermes_truthful_intent(text: str) -> bool:
    return (
        _is_hermes_route_request(text)
        or _is_hermes_route_inventory_request(text)
        or _is_hermes_capability_prompt(text)
    )


def _hermes_truthful_mode(text: str) -> str:
    if _is_hermes_route_inventory_request(text):
        return "route_inventory"
    if _is_hermes_route_request(text) and _route_target(text):
        return "route_request"
    if _is_hermes_addressed(text) and _is_hermes_send_or_money_action(text):
        return "send_money_denial"
    if _is_hermes_route_request(text):
        return "route_request"
    return "capability"


def _hermes_agent_route_targets() -> frozenset[str]:
    try:
        from agent_lane_registry import DEFAULT_AGENT_LANE_SEEDS

        targets: set[str] = set()
        for seed in DEFAULT_AGENT_LANE_SEEDS:
            targets.add(str(seed.agent_id).strip().lower())
            targets.add(str(seed.display_name).strip().lower().replace(" ", "_"))
            targets.update(str(alias).strip().lower() for alias in seed.aliases)
        return frozenset(target for target in targets if target)
    except Exception:
        return HERMES_FALLBACK_AGENT_TARGETS


def _route_target_candidate(text: str) -> str:
    match = re.search(r"\bto\s+([a-z][a-z0-9_-]{1,40})\b", text)
    if not match:
        return ""
    target = match.group(1).strip().lower()
    if target in {"me", "you", "this", "that", "the"}:
        return ""
    return target


def _route_target(text: str) -> str:
    target = _route_target_candidate(text)
    return target if target in _hermes_agent_route_targets() else ""


def _is_hermes_send_or_money_action(text: str) -> bool:
    return bool(HERMES_SEND_OR_MONEY_RE.search(text))


def _strip_internal_state_leaks(text: str) -> str:
    cleaned = str(text or "")
    for pattern in INTERNAL_STATE_LEAK_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip() or "Maestro response was withheld because it contained internal worker state."


def _is_date_awareness_intent(text: str) -> bool:
    date_phrases = (
        "what's today's date",
        "what is today's date",
        "whats today's date",
        "what day is it",
        "what is the date",
        "current date",
        "today's date",
        "todays date",
        "what's the date",
        "whats the date",
        "the date today",
    )
    return any(phrase in text for phrase in date_phrases)


def _is_system_knowledge_intent(text: str) -> bool:
    direct_phrases = (
        "system knowledge registry",
        "self knowledge registry",
        "self-knowledge registry",
        "system self knowledge",
        "system self-knowledge",
        "what is in orbit",
        "what's in orbit",
        "whats in orbit",
        "floating in orbit",
    )
    if any(phrase in text for phrase in direct_phrases):
        return True
    return (
        any(term in text for term in ("system", "openclaw", "registry"))
        and any(term in text for term in ("shape", "know", "known", "unknown", "capability", "component", "orbit", "orphan"))
    )


def _is_status_capability_intent(text: str) -> bool:
    direct_phrases = (
        "what's going on",
        "whats going on",
        "what is going on",
        "what's happening",
        "whats happening",
        "what is happening",
        "what can you do",
        "what can openclaw do",
        "what are you capable of",
        "what can you do now",
        "what can you do for me",
        "what can you help me with",
        "what can openclaw help me with",
        "what can the agents do",
        "who are the agents",
        "what does each agent do",
        "what does each do",
        "agent roster",
        "agent list",
        "which agents are live",
        "which agents are online",
        "system-wide next safe move",
        "system wide next safe move",
        "next safe move",
        "next safest move",
        "safe next move",
        "status readback",
        "give me a status readback",
        "what is live",
        "what's live",
        "whats live",
        "who is online",
        "agent status",
        "system status",
        "openclaw status",
        "capability status",
    )
    if any(phrase in text for phrase in direct_phrases):
        return True
    return (
        any(term in text for term in ("status", "capability", "capabilities", "online", "blocked", "roster"))
        and any(term in text for term in ("openclaw", "agents", "agent", "you", "can", "do"))
    )


def _is_system_health_readback_intent(text: str) -> bool:
    direct_phrases = (
        "system-health read",
        "system health read",
        "system-health status",
        "system health status",
        "system-health check",
        "system health check",
        "front door and agent response stack",
        "agent response stack",
        "service health",
        "agent/service health",
    )
    if any(phrase in text for phrase in direct_phrases):
        return True
    return (
        any(term in text for term in ("system-health", "system health", "service health", "health read"))
        and any(term in text for term in ("openclaw", "front door", "agent", "agents", "stack"))
    )


def _is_recurrence_rule_statement_intent(text: str) -> bool:
    """Task 136a: 'I send St Anne's a new invoice on the first of every month' is an operator
    STATEMENT of a recurring business rule -- a third category, distinct from both a question
    and an instruction. Checked early, before advisory/action/question classification, so it
    is never mistaken for either."""
    from recurrence_rule_intake import detect_recurrence_rule_statement

    return detect_recurrence_rule_statement(text) is not None


def _status_capability_readback_focus(text: str) -> str:
    if any(
        phrase in text
        for phrase in (
            "who are the agents",
            "agent roster",
            "agent list",
            "what does each agent do",
            "what does each do",
            "which agents",
        )
    ):
        return "agent_roster"
    if any(
        phrase in text
        for phrase in (
            "system-wide next safe move",
            "system wide next safe move",
            "next safe move",
            "next safest move",
            "safe next move",
        )
    ):
        return "next_safe_move"
    if any(
        phrase in text
        for phrase in (
            "what can you help me with",
            "what can you do",
            "what can openclaw do",
            "what are you capable of",
            "capability",
            "capabilities",
        )
    ):
        return "capability"
    return "status"


def _is_people_intent(text: str) -> bool:
    return bool(
        re.search(
            r"\b("
            r"who is|who's|"
            r"who do i talk to|"
            r"contact for|point of contact|who should i contact|"
            r"relationship|team member|person|people"
            r")\b",
            text,
        )
    )


def _is_operator_truth_correction_intent(text: str) -> bool:
    try:
        from operator_truth_store import extract_operator_truth_candidates

        return bool(extract_operator_truth_candidates(text, source_surface="operator_maestro_chat"))
    except Exception:
        return False


def _is_operator_truth_query_intent(text: str) -> bool:
    return bool(
        re.search(
            r"\b("
            r"did you (?:store|save|record|remember)|"
            r"what have you recorded about|"
            r"what (?:did|do) you (?:store|save|record|remember)|"
            r"do you (?:have|remember|know) .* truth|"
            r"is .* (?:in your truth|stored|saved|recorded|remembered)"
            r")\b",
            text,
        )
    )


def _is_inbox_metadata_intent(text: str) -> bool:
    return bool(
        re.search(r"\b(gmail|inbox|unread|email metadata|new emails?|recent emails?)\b", text)
        and not _is_send_or_reply_intent(text)
    )


def _is_calendar_or_briefing_intent(text: str) -> bool:
    return bool(
        re.search(r"\b(calendar|meetings?|schedule|morning briefing|daily briefing|briefing)\b", text)
    )


def _is_send_or_reply_intent(text: str) -> bool:
    return bool(
        re.search(
            r"\b(send|reply|respond|forward|email|mail|message|text|draft|outreach|follow up|follow-up)\b",
            text,
        )
        and re.search(r"\b(to|back|subject|body|them|him|her|client|contact|recipient|draft|send|reply|forward)\b", text)
    )


def _is_advisory_interrogative_intent(text: str) -> bool:
    """True for advice-seeking questions that mention send/pay words without requesting an action."""
    if re.search(r"^\s*(send|reply|respond|forward|email|mail|message|text|draft|pay|submit|approve)\b", text):
        return False
    return bool(
        re.search(
            r"\b("
            r"before i (?:send|pay|reply|respond|forward|email|mail|message|text|submit)|"
            r"what should i (?:check|verify|look for|watch for|do)|"
            r"what do i need to (?:check|verify|look for|watch for)|"
            r"how (?:do|should) i (?:check|verify|make sure|avoid|protect|handle)|"
            r"is it safe to|"
            r"should i (?:send|pay|reply|respond|forward|email|mail|message|text|submit|approve)|"
            r"can i safely"
            r")\b",
            text,
        )
    )


# Task 142: dispatch-instruction shapes. Live pass-2 proof: "the PA rental
# invoice for Live Arts needs to go out — get it to the right agent" carried no
# send-verb the older matchers knew, fell to maestro_brain_freeform, and the
# grounded fallback answered it with a business digest. An instruction that
# hands work to the system must route to staging (the normal instruction path),
# never to the digest. Question shapes are excluded by the same
# _is_general_question_shape override the workflow gate already uses.
_DISPATCH_INSTRUCTION_IDIOMS = (
    "needs to go out",
    "need to go out",
    "needs to be sent",
    "need to be sent",
    "get it to",
    "get this to",
    "get it over to",
    "send it out",
    "hand it off",
    "hand this off",
    "hand it to",
    "route it",
    "route this",
    "make sure it goes out",
)


def _is_dispatch_instruction_intent(text: str) -> bool:
    return any(idiom in text for idiom in _DISPATCH_INSTRUCTION_IDIOMS)


def _is_workflow_or_business_action_intent(text: str) -> bool:
    action_terms = (
        "do it",
        "make it so",
        "approve",
        "deny",
        "submit",
        "pay",
        "mark paid",
        "create invoice",
        "make invoice",
        "generate invoice",
        "open browser",
        "coupa",
        "workbook",
        "spreadsheet",
        "ledger",
        "deploy",
        "restart",
        "merge",
        "push",
        "run the workflow",
        "stage plan",
        "schedule",
        "book",
        "create calendar",
    )
    return any(term in text for term in action_terms)


_GENERAL_QUESTION_OPENERS = (
    "who", "what", "when", "where", "which", "how",
    "does", "did", "is", "are", "can",
)


def _is_general_question_shape(text: str) -> bool:
    """Task 133: a question-shaped text (interrogative opener or trailing '?') must never be
    classified as a business action just because it contains an action-shaped word --
    'did St Anne's pay us?' contains 'pay' but asks about status, not a payment request."""
    normalized = str(text or "").strip()
    if not normalized:
        return False
    if normalized.endswith("?"):
        return True
    first_word = normalized.split(" ", 1)[0].rstrip("?,.!;:")
    return first_word in _GENERAL_QUESTION_OPENERS
