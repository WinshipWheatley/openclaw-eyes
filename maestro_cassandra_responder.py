"""Maestro front-door adapter for Cassandra specialist answers.

The adapter is intentionally narrow. It gates intent before calling
``cassandra_brain.handle`` so send/reply/action/Gmail-shaped text stays on the
existing staging/refusal route and never reaches Cassandra's side-effectful
handler through this front-door path.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence


# ── Conversation-continuity flag (ADDITIVE, default OFF) ──────────────────────
def _continuity_enabled() -> bool:
    """Return True only when OPENCLAW_CONTINUITY_CAPSULE is "1" or "true"."""
    return os.environ.get("OPENCLAW_CONTINUITY_CAPSULE", "0").lower() in ("1", "true")


MAC_RENDER_HINT = "COMPACT_WITH_DISCLOSURE"
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
CAPABILITY_INDEX_READ_MODEL = "openclaw_capability_index.json"
AGENT_PRESENCE_READ_MODEL = "agent_presence.json"
CHIEF_STATUS_READ_MODEL = "chief_status_rail.json"
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
        return "maestro_cassandra_responder.truthful_status_capability_readback"
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


def classify_frontdoor_intent(text: str) -> tuple[str, bool, str]:
    normalized = _normalize(text)
    if not normalized:
        return ("empty", False, "empty_text")
    if _is_hermes_truthful_intent(normalized):
        return ("hermes_truthful_advisory", True, "")
    if _is_operator_truth_correction_intent(text):
        return ("operator_truth_correction", True, "")
    if _is_operator_truth_query_intent(normalized):
        return ("operator_truth_query", True, "")
    if _is_send_or_reply_intent(normalized):
        return ("send_reply_email_action", False, "send_reply_email_action_intent_routes_to_staging")
    if _is_inbox_metadata_intent(normalized):
        return ("inbox_gmail_metadata", False, "gmail_metadata_queries_use_existing_staging_path_for_truthful_proof")
    if _is_calendar_or_briefing_intent(normalized):
        return ("calendar_or_briefing", False, "calendar_or_briefing_routes_to_staging")
    ledger_resolution = _ledger_resolution_for_text(normalized)
    if ledger_resolution.get("status") == "NEEDS_CLARIFICATION":
        return ("ledger_reference_clarification", True, "")
    if ledger_resolution.get("status") == "RESOLVED" and ledger_resolution.get("blocked_action_requested") is not True:
        return ("maestro_brain_freeform", True, "")
    if _is_workflow_or_business_action_intent(normalized):
        return ("workflow_or_business_action", False, "workflow_or_business_action_routes_to_staging")
    if _is_date_awareness_intent(normalized):
        return ("date_awareness", True, "")
    if _is_status_capability_intent(normalized):
        return ("status_capability_readback", True, "")
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

    if intent_class == "people_reference_query":
        return _answer_people_query(
            text,
            session=session,
            source_surface=source_surface,
            forwarded_session=forwarded_session,
            protected_generate_fn=protected_generate_fn,
            _capsule=_capsule,
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
) -> MaestroCassandraResult:
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
    )
    proof = {
        **dict(fallback.machine_proof or {}),
        "people_reference_query_performed": True,
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
    try:
        from maestro_context_packet import build_maestro_context_packet

        # ── CONTINUITY CAPSULE threading (flag-gated, ADDITIVE) ──────────────
        # When ON and a capsule is provided, pass it to build_maestro_context_packet
        # so it can populate packet_entity_aliases + packet_source_revision (Edit 2).
        # When OFF or no capsule: call is identical to pre-edit (capsule=None default).
        _capsule_arg = _capsule if _continuity_enabled() else None
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
    answer_text = _strip_internal_state_leaks(answer_text) or (
        "I don't have that in the current Maestro packet."
    )
    # NOTE: jargon teaching + comedy-as-diagnostic + claim detection were CONSOLIDATED into the
    # single author-aware operator-surface pipeline (_enrich_operator_surface in
    # openclaw_request_processor) so EVERY agent voice gets them on the FINAL operator_message —
    # not just this Maestro brain path. They no longer run here (would double-process the surface).
    # Live dankifier hook: score the packet just used + queue grounded gaps, so the system
    # gets danker the more it's used. Never blocks or alters the answer (already finalized
    # above) — observe_packet_dankness swallows all errors; enrichment runs in a separate drain.
    try:
        from packet_dankness_critic import observe_packet_dankness

        observe_packet_dankness(context_packet, text, "maestro")
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
            "protected_generate_called": True,
            "maestro_context_packet_used": True,
            "context_packet_id": str(context_packet.get("packet_id") or ""),
            "proof_refs": proof_refs,
            "source_truth_refs": proof_refs,
            "protected_generate_receipt_id": str(receipt.get("receipt_id") or ""),
            "protected_generate_audit_ref": str(receipt.get("audit_ref") or ""),
            "protected_generate_decision": str(receipt.get("decision") or ""),
            "model_call_performed": bool(receipt.get("model_call_performed", True)),
            "external_llm_invoked": bool(receipt.get("external_llm_invoked", False)),
            "local_model_invoked": bool(receipt.get("local_model_invoked", False)),
            "send_hold_boundary_visible": True,
            "claims_trace_to_packet": True,
            # Interpreter-LM traceability (advisory only — None/empty when off):
            "interpreter_fact_selection_applied": list(_fact_selection or []),
            "interpreter_fact_selection_used": bool(_fact_selection),
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
