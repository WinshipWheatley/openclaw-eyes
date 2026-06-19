"""Maestro front-door adapter for Cassandra specialist answers.

The adapter is intentionally narrow. It gates intent before calling
``cassandra_brain.handle`` so send/reply/action/Gmail-shaped text stays on the
existing staging/refusal route and never reaches Cassandra's side-effectful
handler through this front-door path.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence


MAC_RENDER_HINT = "COMPACT_WITH_DISCLOSURE"
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


def _default_handle(text: str, session: dict[str, Any] | None = None) -> Sequence[str]:
    from cassandra_brain import handle as cassandra_handle

    return cassandra_handle(text, session)


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


def classify_frontdoor_intent(text: str) -> tuple[str, bool, str]:
    normalized = _normalize(text)
    if not normalized:
        return ("empty", False, "empty_text")
    if _is_send_or_reply_intent(normalized):
        return ("send_reply_email_action", False, "send_reply_email_action_intent_routes_to_staging")
    if _is_inbox_metadata_intent(normalized):
        return ("inbox_gmail_metadata", False, "gmail_metadata_queries_use_existing_staging_path_for_truthful_proof")
    if _is_workflow_or_business_action_intent(normalized):
        return ("workflow_or_business_action", False, "workflow_or_business_action_routes_to_staging")
    if _is_date_awareness_intent(normalized):
        return ("date_awareness", True, "")
    if _is_system_knowledge_intent(normalized):
        return ("system_knowledge", True, "")
    return ("unapproved_conversation", False, "conversation_not_in_curated_safe_subset")


def answer_frontdoor_chat(
    text: str,
    *,
    session: Mapping[str, Any] | None = None,
    handle_fn: HandleFn | None = None,
) -> MaestroCassandraResult:
    intent_class, allowed, reason = classify_frontdoor_intent(text)
    forwarded_session = filtered_session(session)
    if not allowed:
        return MaestroCassandraResult(
            status="ROUTE_TO_STAGING",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            route_to_staging_reason=reason,
            session_forwarded=forwarded_session,
            machine_proof=_adapter_machine_proof(handle_called=False),
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

    replies = list((handle_fn or _default_handle)(text, forwarded_session))
    plain_summary = _plain_summary(replies)
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
        "email_send_performed": False,
        "telegram_send_triggered": False,
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


def _is_inbox_metadata_intent(text: str) -> bool:
    return bool(
        re.search(r"\b(gmail|inbox|unread|email metadata|new emails?|recent emails?)\b", text)
        and not _is_send_or_reply_intent(text)
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
