"""Systemwide operator context switchboard v0.

The switchboard runs before an active task consumes free-form operator text.
It is deterministic, local-only, and delegates supported low-risk work to the
existing Universal Intake and guided-review session machinery.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassandra_guided_review import (
    classify_conversation_permission_boundary,
    get_active_guided_review_context,
    is_data_room_guided_review_start_request,
    resolve_guided_review_topic,
    set_guided_review_context_status,
)
from cassandra_review_coach import coach_command
from operator_universal_intake import (
    is_universal_operator_intake_candidate,
    try_process_surface_operator_intake,
)


SCHEMA_VERSION = "OPERATOR_CONTEXT_SWITCHBOARD_DECISION_V0"
ACTIVE_CONTEXTS_SCHEMA_VERSION = "operator_active_contexts_read_model_v0"
STATUS_NOTE_SCHEMA_VERSION = "OPERATOR_STATUS_NOTE_RECEIPT_V0"
ALBUM_REQUEST_SCHEMA_VERSION = "NILES_ALBUM_PROGRESSION_REQUEST_RECEIPT_V0"

DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_REVIEW_ROOT = Path("/tmp/openclaw-mission-control/operator_skill_factory_v0")
DEFAULT_SWITCHBOARD_RECEIPT_ROOT = Path("/tmp/openclaw-mission-control/operator_context_switchboard_v0/receipts")
DEFAULT_OPERATOR_INTAKE_RECEIPT_ROOT = Path("/tmp/openclaw-mission-control/operator_universal_intake_v0/receipts")
READ_MODEL_NAME = "operator_active_contexts.json"

DECISIONS = {
    "current_task_continue",
    "current_task_control",
    "new_task_interrupt",
    "new_task_stage",
    "approval_passthrough",
    "clarification_needed",
    "resume_task",
    "unsupported_but_logged",
}

CURRENT_TASK_ACTIONS = {"continue", "pause", "resume", "leave_active", "close", "none"}

DEFAULT_SAFETY_FLAGS = {
    "external_calls_performed": False,
    "runtime_policy_changed": False,
    "approval_created": False,
    "invoice_marked_paid": False,
    "medical_advice_given": False,
    "tax_or_legal_advice_given": False,
    "daws_or_media_mutated": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rooted(path: str | Path | None, default: Path) -> Path:
    if path is None:
        path = default
    path = Path(path)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def _load_json(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")
    return path


def _text_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _short_hash(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()[:16]


def _normalize(text: str) -> str:
    lowered = str(text or "").lower()
    lowered = lowered.replace("?", " ").replace("!", " ")
    return " ".join(re.sub(r"[^a-z0-9'$.:_-]+", " ", lowered).split())


def _parse_utc(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _display_topic(context: Mapping[str, Any] | None) -> str:
    if not context:
        return "current task"
    return str(context.get("topic_display_name") or context.get("topic") or "current task")


def _active_context_id(context: Mapping[str, Any] | None) -> str:
    if not context:
        return ""
    return str(context.get("active_context_id") or "")


def _decision_id(raw_text: str, created_at: str, surface: str) -> str:
    seed = f"{surface}\n{created_at}\n{raw_text}"
    return f"operator_context_switchboard:{_short_hash(seed)}"


def _receipt_ref(path: Path) -> str:
    return f"{path.as_posix()}#receipt"


def _safety_flags(extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    flags = dict(DEFAULT_SAFETY_FLAGS)
    if extra:
        flags.update({key: bool(value) for key, value in extra.items() if key in flags})
    return flags


def _confidence_value(value: Any, fallback: float = 0.88) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    label = str(value or "").strip().lower()
    if label == "high":
        return 0.9
    if label == "medium":
        return 0.74
    if label == "low":
        return 0.45
    try:
        return float(label)
    except ValueError:
        return fallback


def _guardian_or_exact_send_reply(text: str) -> bool:
    normalized = _normalize(text)
    if re.fullmatch(r"(?:yes|no):[a-z0-9_.:-]+", normalized):
        return True
    terms = (
        "approve exact send request",
        "approve the exact send request",
        "exact send request",
        "exact_send_authority_request",
        "send authority request",
        "prepare the send authority",
        "draft is approved",
        "draft approved",
        "approved with this exact text",
        "operator_action_approval_request",
        "guardian approval",
        "guardian decision",
        "approve button callback",
        "deny button callback",
    )
    return any(term in normalized for term in terms)


def _pending_reply(text: str, active_context: Mapping[str, Any] | None) -> bool:
    if not active_context:
        return False
    pending = active_context.get("pending_interaction")
    if not isinstance(pending, Mapping) or not pending:
        return False
    normalized = _normalize(text).strip(". ")
    return normalized in {
        "yes",
        "yes switch",
        "switch",
        "yes switch to payment privacy",
        "no",
        "cancel",
        "never mind",
        "nevermind",
        "record it here",
        "put it here",
        "use it here",
        "here",
    }


def _pending_switchboard_clarification(contexts: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    for context in reversed(list(contexts)):
        if str(context.get("context_type") or "") != "switchboard_clarification":
            continue
        if str(context.get("status") or "") != "pending":
            continue
        pending = context.get("pending_interaction")
        if isinstance(pending, Mapping) and pending.get("clarification_type") == "current_or_new_task":
            return context
    return None


def _clarification_resolution(text: str) -> str:
    normalized = _normalize(text).strip(". ")
    current_terms = {
        "current",
        "current question",
        "this question",
        "the current question",
        "stay here",
        "keep it here",
        "review question",
        "data room question",
    }
    new_task_terms = {
        "new",
        "new task",
        "a new task",
        "route it as a new task",
        "separate task",
        "something new",
    }
    if normalized in current_terms:
        return "current_question"
    if normalized in new_task_terms:
        return "new_task"
    return ""


def _current_task_control(text: str) -> str:
    command = coach_command(text)
    if command:
        return command
    normalized = _normalize(text).strip(". ")
    if normalized in {
        "why",
        "recommend",
        "what do you recommend",
        "examples",
        "use your recommendation",
        "skip",
        "defer",
        "revise previous",
        "summarize",
        "summary",
        "done",
        "next",
        "next question",
    }:
        return normalized
    return ""


def _resume_command(text: str) -> bool:
    normalized = _normalize(text).strip(". ")
    if is_data_room_guided_review_start_request(text):
        return True
    if normalized in {"continue", "resume", "keep going", "next question", "back to the questions"}:
        return True
    return any(
        phrase in normalized
        for phrase in (
            "resume data room",
            "continue data room",
            "back to data room",
            "finish that review",
            "finish this review",
            "continue album",
            "continue niles",
            "back to niles",
            "back to album",
        )
    )


def _ambiguous_command(text: str) -> bool:
    normalized = _normalize(text).strip(". ")
    return normalized in {
        "that thing",
        "this thing",
        "handle that thing",
        "handle this thing",
        "handle this",
        "handle that",
        "do it",
        "do that",
        "do this",
    }


def _health_or_status_note(text: str, active_context: Mapping[str, Any] | None = None) -> bool:
    normalized = _normalize(text)
    if "system health" in normalized or "health check" in normalized:
        return False
    explicit_marker = any(
        normalized.startswith(marker)
        for marker in (
            "health update:",
            "status note:",
            "wellbeing update:",
            "well being update:",
            "operator status:",
        )
    )
    if active_context:
        return explicit_marker
    return any(
        phrase in normalized
        for phrase in (
            "health update",
            "wellbeing update",
            "well being update",
            "operator status",
            "status note",
            "i slept",
            "slept badly",
            "slept poorly",
            "feel off",
            "feeling off",
            "low energy",
            "exhausted",
            "tired today",
            "rough sleep",
            "put this there if you can find it",
        )
    )


def _status_tags(text: str) -> list[str]:
    normalized = _normalize(text)
    tags: list[str] = []
    if any(term in normalized for term in ("sleep", "slept", "rough sleep")):
        tags.append("sleep")
    if any(term in normalized for term in ("energy", "exhausted", "tired", "fatigue")):
        tags.append("energy")
    if any(term in normalized for term in ("feel off", "feeling off", "mood")):
        tags.append("mood")
    return tags


def _album_request(text: str) -> bool:
    normalized = _normalize(text).strip(". ")
    if normalized == "album":
        return True
    return any(term in normalized for term in ("album progression", "album tracker", "album csv", "progression csv"))


def _is_external_lane_passthrough(text: str) -> bool:
    return is_universal_operator_intake_candidate(text)


def _context_read_model_path(read_model_root: str | Path | None) -> Path:
    return _rooted(read_model_root, DEFAULT_READ_MODEL_ROOT) / READ_MODEL_NAME


def _active_context_stack_from_read_model(read_model_root: str | Path | None) -> list[dict[str, Any]]:
    payload = _load_json(_context_read_model_path(read_model_root))
    contexts = payload.get("active_contexts")
    if not isinstance(contexts, list):
        return []
    return [dict(item) for item in contexts if isinstance(item, Mapping)]


def _context_semantic_key(context: Mapping[str, Any]) -> str:
    context_type = str(context.get("context_type") or "")
    topic = str(context.get("topic") or "")
    owner_agent = str(context.get("owner_agent") or "")
    if context_type and topic and owner_agent:
        return f"{context_type}\0{topic}\0{owner_agent}"
    return ""


def _context_expired(context: Mapping[str, Any], generated_at: str) -> bool:
    if str(context.get("context_type") or "") != "operator_status_note":
        return False
    if str(context.get("status") or "") != "completed":
        return False
    generated = _parse_utc(generated_at)
    last_turn = _parse_utc(context.get("last_turn_at_utc"))
    if generated is None or last_turn is None:
        return False
    return generated - last_turn >= timedelta(hours=24)


def _dedupe_contexts(contexts: Sequence[Mapping[str, Any]], generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    indexes: dict[str, int] = {}
    for context in contexts:
        row = dict(context)
        if _context_expired(row, generated_at):
            continue
        key = _context_semantic_key(row) or str(row.get("active_context_id") or "")
        if key and key in indexes:
            rows[indexes[key]] = row
            continue
        if key:
            indexes[key] = len(rows)
        rows.append(row)
    return rows


def _upsert_context(contexts: list[dict[str, Any]], context: Mapping[str, Any]) -> list[dict[str, Any]]:
    context_id = str(context.get("active_context_id") or "")
    semantic_key = _context_semantic_key(context)
    if not context_id and not semantic_key:
        return contexts
    updated = False
    rows: list[dict[str, Any]] = []
    for item in contexts:
        item_id = str(item.get("active_context_id") or "")
        item_key = _context_semantic_key(item)
        if (context_id and item_id == context_id) or (semantic_key and item_key == semantic_key):
            rows.append(dict(context))
            updated = True
        else:
            rows.append(item)
    if not updated:
        rows.append(dict(context))
    return rows


def _watch_item_for_context(context: Mapping[str, Any]) -> dict[str, Any] | None:
    context_type = str(context.get("context_type") or "")
    context_id = str(context.get("active_context_id") or "")
    if not context_id or context_type == "guided_review_session":
        return None
    if context_type == "operator_status_note":
        return {
            "item_id": f"operator_context:{context_id}",
            "lane": "chief_runtime",
            "urgency": "info",
            "plain_line": "Operator status note logged. No medical advice or external action taken.",
            "source_receipt_ref": str(context.get("source_session_ref") or ""),
            "one_next_safe_action": "Keep this as a local status note unless Winship asks for a scoped next step.",
            "push_class": "info",
            "state": {
                "context_type": context_type,
                "status": str(context.get("status") or "completed"),
                "resume_context_ref": str(context.get("resume_context_ref") or ""),
                "medical_advice_given": False,
                "external_calls_performed": False,
            },
        }
    if context_type == "niles_album_progression":
        return {
            "item_id": f"operator_context:{context_id}",
            "lane": "niles_creative",
            "urgency": "watch",
            "plain_line": "Niles album progression staged. No DAW, media, or CSV mutation performed.",
            "source_receipt_ref": str(context.get("source_session_ref") or ""),
            "one_next_safe_action": "Resume the staged Niles album/progression request from a bounded local work packet.",
            "push_class": "info",
            "state": {
                "context_type": context_type,
                "status": str(context.get("status") or "active"),
                "resume_context_ref": str(context.get("resume_context_ref") or ""),
                "daws_or_media_mutated": False,
                "csv_mutated": False,
            },
        }
    return None


def write_operator_active_contexts_read_model(
    contexts: Sequence[Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]] | None = None,
    *,
    read_model_root: str | Path | None = None,
    generated_at_utc: str | None = None,
) -> Path:
    generated_at = generated_at_utc or utc_now()
    context_rows = _dedupe_contexts(contexts, generated_at)
    decision_rows = [dict(item) for item in decisions or []][-50:]
    watch_items = [
        item
        for item in (_watch_item_for_context(context) for context in context_rows)
        if item is not None and item.get("source_receipt_ref")
    ]
    payload = {
        "schema_version": ACTIVE_CONTEXTS_SCHEMA_VERSION,
        "generated_at": generated_at,
        "active_contexts": context_rows,
        "decisions": decision_rows,
        "watch_desk_items": watch_items,
        "authority_boundary": {
            "external_calls_performed": False,
            "runtime_policy_changed": False,
            "approval_created": False,
            "invoice_marked_paid": False,
            "medical_advice_given": False,
            "tax_or_legal_advice_given": False,
            "daws_or_media_mutated": False,
        },
    }
    return _write_json(_context_read_model_path(read_model_root), payload)


def _refresh_watch_desk(read_model_root: str | Path | None, generated_at: str) -> dict[str, Any]:
    try:
        from watch_desk_feed import export_watch_desk_feed

        root = _rooted(read_model_root, DEFAULT_READ_MODEL_ROOT)
        return export_watch_desk_feed(
            read_model_root=root,
            export_root=root,
            generated_at=generated_at,
        )
    except Exception as exc:
        return {
            "read_model_path": "",
            "item_count": 0,
            "new_push_candidate_count": 0,
            "live_push_allowed": False,
            "refresh_error": type(exc).__name__,
        }


def _base_decision(
    *,
    raw_text: str,
    surface: str,
    source_agent: str,
    created_at: str,
    active_contexts: Sequence[Mapping[str, Any]],
    current_context_id: str,
    detected_intent: str,
    detected_lane: str,
    detected_action_type: str,
    confidence: float,
    decision: str,
    routed_to_agent: str,
    routed_to_lane: str,
    current_task_action: str,
    handoff_reason: str,
    operator_visible_reply: str,
    receipt_refs: Sequence[str] | None = None,
    watch_desk_refs: Sequence[str] | None = None,
    safety_flags: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if decision not in DECISIONS:
        raise ValueError(f"unsupported switchboard decision: {decision}")
    if current_task_action not in CURRENT_TASK_ACTIONS:
        raise ValueError(f"unsupported current task action: {current_task_action}")
    return {
        "schema_version": SCHEMA_VERSION,
        "decision_id": _decision_id(raw_text, created_at, surface),
        "created_at_utc": created_at,
        "surface": surface,
        "source_agent": source_agent,
        "raw_text_hash": _text_hash(raw_text),
        "active_contexts": [dict(item) for item in active_contexts],
        "current_context_id": current_context_id,
        "detected_intent": detected_intent,
        "detected_lane": detected_lane,
        "detected_action_type": detected_action_type,
        "confidence": confidence,
        "decision": decision,
        "routed_to_agent": routed_to_agent,
        "routed_to_lane": routed_to_lane,
        "current_task_action": current_task_action,
        "handoff_reason": handoff_reason,
        "operator_visible_reply": operator_visible_reply,
        "receipt_refs": list(receipt_refs or []),
        "watch_desk_refs": list(watch_desk_refs or []),
        "safety_flags": _safety_flags(safety_flags),
    }


def _guided_review_should_own(
    raw_text: str,
    active_context: Mapping[str, Any] | None,
    context_stack: Sequence[Mapping[str, Any]],
) -> bool:
    normalized = _normalize(raw_text).strip(". ")
    if not normalized:
        return False
    if is_data_room_guided_review_start_request(raw_text):
        return True
    if _ambiguous_command(raw_text) or _resume_command(raw_text):
        return False
    resolution = resolve_guided_review_topic(raw_text, active_session_context=active_context or context_stack)
    return bool(resolution.get("should_start_session"))


def _session_question_preview(active_context: Mapping[str, Any] | None) -> str:
    if not active_context:
        return ""
    session_ref = str(active_context.get("source_session_ref") or "")
    if not session_ref:
        return ""
    session_path = Path(session_ref.split("#", 1)[0])
    session = _load_json(session_path)
    questions = session.get("question_queue")
    current_question_id = str(active_context.get("current_question_id") or session.get("current_question_id") or "")
    if not isinstance(questions, list) or not current_question_id:
        return ""
    for question in questions:
        if not isinstance(question, Mapping):
            continue
        if str(question.get("question_id") or "") != current_question_id:
            continue
        text = " ".join(str(question.get("question_text") or "").split())
        return text[:140]
    return ""


def _breadcrumb(active_context: Mapping[str, Any] | None) -> str:
    if not active_context:
        return ""
    preview = _session_question_preview(active_context)
    if preview:
        return f" Back to Data Room: {preview}"
    return " Back to Data Room: say 'continue Data Room' when ready."


def _conversation_permission_boundary_reply(active_context: Mapping[str, Any] | None) -> str:
    return (
        "I can treat this chat as the conversation source for this lane, but that is not a Data Room answer "
        "and it does not change runtime policy or grant external-action permission."
    ) + _breadcrumb(active_context)


def _context_by_resume_command(
    raw_text: str,
    active_context: Mapping[str, Any] | None,
    context_stack: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    normalized = _normalize(raw_text).strip(". ")
    niles_requested = normalized in {"continue album", "back to niles", "continue niles", "back to album"} or any(
        phrase in normalized
        for phrase in (
            "continue album",
            "back to niles",
            "continue niles",
            "back to album",
        )
    )
    data_room_requested = normalized in {"continue", "resume", "keep going", "next question", "back to the questions"} or any(
        phrase in normalized
        for phrase in (
            "resume data room",
            "continue data room",
            "back to data room",
            "finish that review",
            "finish this review",
        )
    )
    if niles_requested:
        for context in reversed(list(context_stack)):
            if str(context.get("context_type") or "") == "niles_album_progression":
                return context
    if data_room_requested:
        return active_context
    return active_context


def _intake_reply(intake: Mapping[str, Any], active_context: Mapping[str, Any] | None) -> str:
    action_type = str(intake.get("action_type") or "")
    event = intake.get("event") if isinstance(intake.get("event"), Mapping) else {}
    fields = {}
    parsed = event.get("parsed") if isinstance(event.get("parsed"), Mapping) else {}
    if isinstance(parsed.get("fields"), Mapping):
        fields = dict(parsed["fields"])
    if action_type == "income_payment_log":
        amount = fields.get("amount")
        payer = str(fields.get("payer") or "the payer")
        amount_text = f"${amount:,.0f}" if isinstance(amount, (int, float)) and not isinstance(amount, bool) else "that income"
        return (
            f"Logged the {amount_text} {payer} income note. "
            "I did not mark any invoice paid."
        ) + _breadcrumb(active_context)
    if action_type == "agent_lane_request":
        routed_to = str(intake.get("routed_to_agent") or intake.get("inferred_owner_agent") or "")
        if routed_to == "chief":
            return "Routed that to Chief/system review." + _breadcrumb(active_context)
    return str(intake.get("reply") or intake.get("reply_text") or "Logged.") + _breadcrumb(active_context)


def _write_status_note_receipt(
    raw_text: str,
    *,
    surface: str,
    created_at: str,
    active_context: Mapping[str, Any] | None,
    receipt_root: str | Path | None,
) -> tuple[dict[str, Any], str]:
    root = _rooted(receipt_root, DEFAULT_SWITCHBOARD_RECEIPT_ROOT)
    receipt_id = f"operator_status_note:{_short_hash(raw_text + created_at)}"
    excerpt = " ".join(raw_text.strip().split())[:240]
    payload = {
        "schema_version": STATUS_NOTE_SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "note_type": "operator_status_note",
        "operator_reported_text_excerpt": excerpt,
        "operator_reported_text_hash": _text_hash(raw_text),
        "tags": _status_tags(raw_text),
        "created_at_utc": created_at,
        "source_surface": surface,
        "active_context_interrupted": active_context is not None,
        "resume_context_ref": _active_context_id(active_context),
        "medical_advice_given": False,
        "external_calls_performed": False,
        "approval_created": False,
        "runtime_policy_changed": False,
    }
    path = _write_json(root / f"{receipt_id.replace(':', '_')}.json", payload)
    return payload, _receipt_ref(path)


def _write_album_request_receipt(
    raw_text: str,
    *,
    surface: str,
    created_at: str,
    active_context: Mapping[str, Any] | None,
    receipt_root: str | Path | None,
) -> tuple[dict[str, Any], str]:
    root = _rooted(receipt_root, DEFAULT_SWITCHBOARD_RECEIPT_ROOT)
    receipt_id = f"niles_album_progression:{_short_hash(raw_text + created_at)}"
    payload = {
        "schema_version": ALBUM_REQUEST_SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "action_type": "niles_album_progression",
        "owner_agent": "niles",
        "owner_lane": "niles_creative",
        "request_text_hash": _text_hash(raw_text),
        "request_text_excerpt": " ".join(raw_text.strip().split())[:160],
        "created_at_utc": created_at,
        "source_surface": surface,
        "active_context_interrupted": active_context is not None,
        "resume_context_ref": _active_context_id(active_context),
        "local_receipt_only": True,
        "daw_action_taken": False,
        "daws_or_media_mutated": False,
        "media_or_session_mutated": False,
        "csv_mutated": False,
        "external_calls_performed": False,
        "approval_created": False,
    }
    path = _write_json(root / f"{receipt_id.replace(':', '_')}.json", payload)
    return payload, _receipt_ref(path)


def _append_decision_to_read_model(
    decision: Mapping[str, Any],
    *,
    read_model_root: str | Path | None,
    contexts: Sequence[Mapping[str, Any]],
    generated_at_utc: str,
) -> Path:
    previous = _load_json(_context_read_model_path(read_model_root))
    old_decisions = previous.get("decisions") if isinstance(previous.get("decisions"), list) else []
    decisions = [dict(item) for item in old_decisions if isinstance(item, Mapping)] + [dict(decision)]
    return write_operator_active_contexts_read_model(
        contexts,
        decisions,
        read_model_root=read_model_root,
        generated_at_utc=generated_at_utc,
    )


def _pause_active_context(
    active_context: Mapping[str, Any] | None,
    *,
    review_root: str | Path | None,
    read_model_root: str | Path | None,
    interrupted_by_ref: str,
    generated_at_utc: str,
) -> dict[str, Any] | None:
    if not active_context:
        return None
    if str(active_context.get("context_type") or "") != "guided_review_session":
        return None
    return set_guided_review_context_status(
        "paused",
        review_root=review_root,
        read_model_root=read_model_root,
        interrupted_by_ref=interrupted_by_ref,
        generated_at_utc=generated_at_utc,
    )


def _resume_active_context(
    active_context: Mapping[str, Any] | None,
    *,
    review_root: str | Path | None,
    read_model_root: str | Path | None,
    generated_at_utc: str,
) -> dict[str, Any] | None:
    if not active_context:
        return None
    if str(active_context.get("context_type") or "") != "guided_review_session":
        return None
    return set_guided_review_context_status(
        "active",
        review_root=review_root,
        read_model_root=read_model_root,
        generated_at_utc=generated_at_utc,
    )


def process_operator_context_switchboard_message(
    raw_text: str,
    *,
    surface: str,
    source_agent: str = "cassandra",
    operator: str = "Winship",
    review_root: str | Path | None = None,
    read_model_root: str | Path | None = None,
    receipt_root: str | Path | None = None,
    operator_intake_receipt_root: str | Path | None = None,
    received_at_utc: str | None = None,
    operator_timezone: str | None = None,
) -> dict[str, Any] | None:
    """Apply the switchboard before an active task captures the message."""

    if not raw_text or not raw_text.strip():
        return None

    created_at = received_at_utc or utc_now()
    active_context = get_active_guided_review_context(review_root=review_root)
    context_stack = _active_context_stack_from_read_model(read_model_root)
    active_contexts = context_stack
    if active_context:
        active_contexts = _upsert_context(context_stack, active_context)
    current_context_id = _active_context_id(active_context)

    if not active_context and not _guardian_or_exact_send_reply(raw_text):
        return None

    if _guided_review_should_own(raw_text, active_context, active_contexts):
        return None

    pending_clarification = _pending_switchboard_clarification(active_contexts)
    if pending_clarification:
        resolution = _clarification_resolution(raw_text)
        completed_context = dict(pending_clarification)
        completed_context["status"] = "completed"
        completed_context["last_turn_at_utc"] = created_at
        active_contexts = _upsert_context(active_contexts, completed_context)
        active_owner = str((active_context or {}).get("owner_agent") or "cassandra")
        active_lane = str((active_context or {}).get("context_type") or "guided_review_session")
        if resolution == "current_question":
            decision = _base_decision(
                raw_text=raw_text,
                surface=surface,
                source_agent=source_agent,
                created_at=created_at,
                active_contexts=active_contexts,
                current_context_id=current_context_id,
                detected_intent="switchboard_clarification_reply",
                detected_lane=active_owner,
                detected_action_type="resolve_current_question",
                confidence=0.94,
                decision="current_task_control",
                routed_to_agent=active_owner,
                routed_to_lane=active_lane,
                current_task_action="leave_active",
                handoff_reason="Resolved ambiguous operator instruction back to the current task without recording the resolution as an answer.",
                operator_visible_reply=f"Okay, staying with the current {_display_topic(active_context)} question.",
            )
        elif resolution == "new_task":
            decision = _base_decision(
                raw_text=raw_text,
                surface=surface,
                source_agent=source_agent,
                created_at=created_at,
                active_contexts=active_contexts,
                current_context_id=current_context_id,
                detected_intent="switchboard_clarification_reply",
                detected_lane="operator_context_switchboard",
                detected_action_type="resolve_new_task",
                confidence=0.94,
                decision="clarification_needed",
                routed_to_agent="cassandra",
                routed_to_lane="operator_context_switchboard",
                current_task_action="leave_active",
                handoff_reason="Resolved ambiguous operator instruction as a separate task request before active-review answer capture.",
                operator_visible_reply="Okay. What new task should I route?",
            )
        else:
            completed_context["status"] = "pending"
            active_contexts = _upsert_context(active_contexts, completed_context)
            decision = _base_decision(
                raw_text=raw_text,
                surface=surface,
                source_agent=source_agent,
                created_at=created_at,
                active_contexts=active_contexts,
                current_context_id=current_context_id,
                detected_intent="switchboard_clarification_reply",
                detected_lane="operator_context_switchboard",
                detected_action_type="clarification_unresolved",
                confidence=0.7,
                decision="clarification_needed",
                routed_to_agent="cassandra",
                routed_to_lane="operator_context_switchboard",
                current_task_action="leave_active",
                handoff_reason="Clarification reply did not resolve current task vs new task.",
                operator_visible_reply=f"Please say 'current question' or 'new task' so I do not record that into {_display_topic(active_context)}.",
            )
        _append_decision_to_read_model(decision, read_model_root=read_model_root, contexts=active_contexts, generated_at_utc=created_at)
        _refresh_watch_desk(read_model_root, created_at)
        return decision

    guided_resolution = resolve_guided_review_topic(raw_text, active_session_context=active_context or active_contexts)
    if (
        guided_resolution.get("clarification_question")
        and not _ambiguous_command(raw_text)
        and not _is_external_lane_passthrough(raw_text)
    ):
        decision = _base_decision(
            raw_text=raw_text,
            surface=surface,
            source_agent=source_agent,
            created_at=created_at,
            active_contexts=active_contexts,
            current_context_id=current_context_id,
            detected_intent="guided_review_topic_clarification",
            detected_lane="guided_review_session",
            detected_action_type="clarify_guided_review_topic",
            confidence=_confidence_value(guided_resolution.get("confidence"), 0.74),
            decision="clarification_needed",
            routed_to_agent="cassandra",
            routed_to_lane="guided_review_session",
            current_task_action="leave_active",
            handoff_reason="Vague review request should clarify the guided-review topic instead of routing to a new system task.",
            operator_visible_reply=str(guided_resolution.get("clarification_question") or "Which review should we use?"),
        )
        _append_decision_to_read_model(decision, read_model_root=read_model_root, contexts=active_contexts, generated_at_utc=created_at)
        _refresh_watch_desk(read_model_root, created_at)
        return decision

    if _guardian_or_exact_send_reply(raw_text):
        return _base_decision(
            raw_text=raw_text,
            surface=surface,
            source_agent=source_agent,
            created_at=created_at,
            active_contexts=active_contexts,
            current_context_id=current_context_id,
            detected_intent="approval_reply",
            detected_lane="guardian_approval",
            detected_action_type="approval_passthrough",
            confidence=1.0,
            decision="approval_passthrough",
            routed_to_agent="guardian",
            routed_to_lane="guardian_approval",
            current_task_action="leave_active",
            handoff_reason="Guardian/HITL/exact-send reply must not be captured by active tasks.",
            operator_visible_reply="",
        )

    permission_boundary = classify_conversation_permission_boundary(raw_text)
    if permission_boundary:
        decision = _base_decision(
            raw_text=raw_text,
            surface=surface,
            source_agent=source_agent,
            created_at=created_at,
            active_contexts=active_contexts,
            current_context_id=current_context_id,
            detected_intent="conversation_permission_boundary",
            detected_lane=str(active_context.get("owner_agent") or "cassandra"),
            detected_action_type="conversation_permission_boundary",
            confidence=0.92,
            decision="current_task_control",
            routed_to_agent=str(active_context.get("owner_agent") or "cassandra"),
            routed_to_lane=str(active_context.get("context_type") or "guided_review_session"),
            current_task_action="leave_active",
            handoff_reason=(
                "Conversation source/permission statements are boundary context, not active-review answers "
                "or external-action approvals."
            ),
            operator_visible_reply=_conversation_permission_boundary_reply(active_context),
            safety_flags={
                "external_calls_performed": False,
                "runtime_policy_changed": False,
                "approval_created": False,
            },
        )
        _append_decision_to_read_model(decision, read_model_root=read_model_root, contexts=active_contexts, generated_at_utc=created_at)
        _refresh_watch_desk(read_model_root, created_at)
        return decision

    if _pending_reply(raw_text, active_context):
        return _base_decision(
            raw_text=raw_text,
            surface=surface,
            source_agent=source_agent,
            created_at=created_at,
            active_contexts=active_contexts,
            current_context_id=current_context_id,
            detected_intent="pending_interaction_reply",
            detected_lane=str(active_context.get("owner_agent") or "cassandra"),
            detected_action_type="guided_review_pending_interaction",
            confidence=0.98,
            decision="current_task_continue",
            routed_to_agent=str(active_context.get("owner_agent") or "cassandra"),
            routed_to_lane=str(active_context.get("context_type") or "guided_review_session"),
            current_task_action="continue",
            handoff_reason="Active pending interaction replies belong to the pending task turn.",
            operator_visible_reply="",
        )

    control = _current_task_control(raw_text)
    if control:
        return _base_decision(
            raw_text=raw_text,
            surface=surface,
            source_agent=source_agent,
            created_at=created_at,
            active_contexts=active_contexts,
            current_context_id=current_context_id,
            detected_intent="current_task_control",
            detected_lane=str(active_context.get("owner_agent") or "cassandra"),
            detected_action_type=control,
            confidence=0.96,
            decision="current_task_control",
            routed_to_agent=str(active_context.get("owner_agent") or "cassandra"),
            routed_to_lane=str(active_context.get("context_type") or "guided_review_session"),
            current_task_action="continue",
            handoff_reason="Explicit task-control command should stay with the active task.",
            operator_visible_reply="",
        )

    if _resume_command(raw_text):
        resume_target = _context_by_resume_command(raw_text, active_context, active_contexts)
        resumed = None
        if str((resume_target or {}).get("context_type") or "") == "guided_review_session":
            resumed = _resume_active_context(
                active_context,
                review_root=review_root,
                read_model_root=read_model_root,
                generated_at_utc=created_at,
            )
            if resumed:
                active_context = resumed
                resume_target = resumed
                active_contexts = _upsert_context(active_contexts, resumed)
        elif resume_target:
            resume_target = dict(resume_target)
            resume_target["status"] = "active"
            resume_target["last_turn_at_utc"] = created_at
            active_contexts = _upsert_context(active_contexts, resume_target)
        decision = _base_decision(
            raw_text=raw_text,
            surface=surface,
            source_agent=source_agent,
            created_at=created_at,
            active_contexts=active_contexts,
            current_context_id=_active_context_id(resume_target),
            detected_intent="resume_task",
            detected_lane=str((resume_target or {}).get("owner_agent") or "cassandra"),
            detected_action_type="resume_active_context",
            confidence=0.95,
            decision="resume_task",
            routed_to_agent=str((resume_target or {}).get("owner_agent") or "cassandra"),
            routed_to_lane=str((resume_target or {}).get("context_type") or "guided_review_session"),
            current_task_action="resume",
            handoff_reason="Operator explicitly asked to resume a prior task.",
            operator_visible_reply=(
                "Continuing Niles album/progression. No DAW, media, or CSV changes."
                if str((resume_target or {}).get("context_type") or "") == "niles_album_progression"
                else f"Continuing {_display_topic(resume_target)}."
            ),
        )
        _append_decision_to_read_model(decision, read_model_root=read_model_root, contexts=active_contexts, generated_at_utc=created_at)
        _refresh_watch_desk(read_model_root, created_at)
        return decision

    if _health_or_status_note(raw_text, active_context):
        receipt, receipt_ref = _write_status_note_receipt(
            raw_text,
            surface=surface,
            created_at=created_at,
            active_context=active_context,
            receipt_root=receipt_root,
        )
        paused = _pause_active_context(
            active_context,
            review_root=review_root,
            read_model_root=read_model_root,
            interrupted_by_ref=receipt_ref,
            generated_at_utc=created_at,
        )
        if paused:
            active_context = paused
            active_contexts = _upsert_context(active_contexts, paused)
        status_context = {
            "active_context_id": str(receipt["receipt_id"]),
            "context_type": "operator_status_note",
            "owner_agent": "cassandra",
            "topic": "operator_status_note",
            "status": "completed",
            "last_turn_at_utc": created_at,
            "resume_phrase": "continue Data Room",
            "source_session_ref": receipt_ref,
            "current_question_id": "",
            "interrupted_by_refs": [],
            "resume_context_ref": _active_context_id(active_context),
            "resume_suggestion": "Say 'continue Data Room' when ready.",
        }
        active_contexts = _upsert_context(active_contexts, status_context)
        watch_ref = f"operator_context:{status_context['active_context_id']}"
        reply = "Logged that as an operator status note. No medical advice or external action taken." + _breadcrumb(active_context)
        decision = _base_decision(
            raw_text=raw_text,
            surface=surface,
            source_agent=source_agent,
            created_at=created_at,
            active_contexts=active_contexts,
            current_context_id=_active_context_id(active_context),
            detected_intent="operator_status_note",
            detected_lane="chief_runtime",
            detected_action_type="operator_status_note",
            confidence=0.9,
            decision="new_task_interrupt",
            routed_to_agent="cassandra",
            routed_to_lane="operator_status_note",
            current_task_action="pause",
            handoff_reason="Health/status update is unrelated to the active guided-review answer.",
            operator_visible_reply=reply,
            receipt_refs=[receipt_ref],
            watch_desk_refs=[f"guided_review:{active_context.get('review_session_id', '')}", watch_ref],
        )
        _append_decision_to_read_model(decision, read_model_root=read_model_root, contexts=active_contexts, generated_at_utc=created_at)
        _refresh_watch_desk(read_model_root, created_at)
        return decision

    if _album_request(raw_text):
        receipt, receipt_ref = _write_album_request_receipt(
            raw_text,
            surface=surface,
            created_at=created_at,
            active_context=active_context,
            receipt_root=receipt_root,
        )
        paused = _pause_active_context(
            active_context,
            review_root=review_root,
            read_model_root=read_model_root,
            interrupted_by_ref=receipt_ref,
            generated_at_utc=created_at,
        )
        if paused:
            active_context = paused
            active_contexts = _upsert_context(active_contexts, paused)
        album_context = {
            "active_context_id": str(receipt["receipt_id"]),
            "context_type": "niles_album_progression",
            "owner_agent": "niles",
            "topic": "album_progression",
            "status": "active",
            "last_turn_at_utc": created_at,
            "resume_phrase": "continue album",
            "source_session_ref": receipt_ref,
            "current_question_id": "",
            "interrupted_by_refs": [],
            "resume_context_ref": _active_context_id(active_context),
            "resume_suggestion": "Say 'continue album' to pick up the tracker request.",
        }
        active_contexts = _upsert_context(active_contexts, album_context)
        watch_ref = f"operator_context:{album_context['active_context_id']}"
        reply = "Staged album progression for Niles. No DAW, media, or CSV changes." + _breadcrumb(active_context)
        decision = _base_decision(
            raw_text=raw_text,
            surface=surface,
            source_agent=source_agent,
            created_at=created_at,
            active_contexts=active_contexts,
            current_context_id=_active_context_id(active_context),
            detected_intent="album_progression_request",
            detected_lane="niles_creative",
            detected_action_type="niles_album_progression",
            confidence=0.9,
            decision="new_task_stage",
            routed_to_agent="niles",
            routed_to_lane="niles_creative",
            current_task_action="pause",
            handoff_reason="Album/progression belongs to the Niles creative lane, not the active review answer.",
            operator_visible_reply=reply,
            receipt_refs=[receipt_ref],
            watch_desk_refs=[f"guided_review:{active_context.get('review_session_id', '')}", watch_ref],
            safety_flags={"daws_or_media_mutated": False},
        )
        _append_decision_to_read_model(decision, read_model_root=read_model_root, contexts=active_contexts, generated_at_utc=created_at)
        _refresh_watch_desk(read_model_root, created_at)
        return decision

    if _is_external_lane_passthrough(raw_text):
        intake = try_process_surface_operator_intake(
            raw_text,
            surface=surface,
            operator=operator,
            received_at_utc=created_at,
            operator_timezone=operator_timezone,
            receiving_agent_id=source_agent,
            read_model_root=_rooted(read_model_root, DEFAULT_READ_MODEL_ROOT),
            receipt_root=_rooted(operator_intake_receipt_root, DEFAULT_OPERATOR_INTAKE_RECEIPT_ROOT),
        )
        if intake is not None:
            receipt_refs = [str(ref) for ref in intake.get("receipt_refs", [])]
            interrupted_ref = receipt_refs[0] if receipt_refs else str(intake.get("intake_id") or "")
            paused = _pause_active_context(
                active_context,
                review_root=review_root,
                read_model_root=read_model_root,
                interrupted_by_ref=interrupted_ref,
                generated_at_utc=created_at,
            )
            if paused:
                active_context = paused
                active_contexts = _upsert_context(active_contexts, paused)
            reply = _intake_reply(intake, active_context)
            decision_name = "new_task_stage" if str(intake.get("action_type") or "") == "agent_lane_request" else "new_task_interrupt"
            routed_to_agent = str(intake.get("routed_to_agent") or intake.get("inferred_owner_agent") or "cassandra")
            routed_to_lane = str(intake.get("inferred_owner_lane") or intake.get("lane") or "")
            decision = _base_decision(
                raw_text=raw_text,
                surface=surface,
                source_agent=source_agent,
                created_at=created_at,
                active_contexts=active_contexts,
                current_context_id=_active_context_id(active_context),
                detected_intent=str(intake.get("action_type") or ""),
                detected_lane=routed_to_lane,
                detected_action_type=str(intake.get("action_type") or ""),
                confidence=_confidence_value(intake.get("route_confidence"), 0.88),
                decision=decision_name,
                routed_to_agent=routed_to_agent,
                routed_to_lane=routed_to_lane,
                current_task_action="pause",
                handoff_reason="Clear off-topic operator message routed through Universal Intake before review answer capture.",
                operator_visible_reply=reply,
                receipt_refs=receipt_refs,
                watch_desk_refs=[f"guided_review:{active_context.get('review_session_id', '')}"]
                + [str(ref) for ref in intake.get("watch_desk_refs", [])],
                safety_flags={
                    "external_calls_performed": bool(intake.get("external_calls_performed")),
                    "approval_created": bool(intake.get("approval_created", False)),
                },
            )
            _append_decision_to_read_model(decision, read_model_root=read_model_root, contexts=active_contexts, generated_at_utc=created_at)
            _refresh_watch_desk(read_model_root, created_at)
            return decision

    if _ambiguous_command(raw_text):
        reply = f"Is that about the current {_display_topic(active_context)} question, or a new task?"
        clarification_context = {
            "active_context_id": f"switchboard_clarification:{_short_hash(current_context_id + raw_text)}",
            "context_type": "switchboard_clarification",
            "owner_agent": "cassandra",
            "topic": "current_or_new_task",
            "status": "pending",
            "last_turn_at_utc": created_at,
            "resume_phrase": "",
            "source_session_ref": "",
            "current_question_id": str((active_context or {}).get("current_question_id") or ""),
            "interrupted_by_refs": [],
            "resume_context_ref": current_context_id,
            "pending_interaction": {
                "clarification_type": "current_or_new_task",
                "prompt": reply,
                "source_context_ref": current_context_id,
            },
            "resume_suggestion": "Say 'current question' or 'new task'.",
        }
        active_contexts = _upsert_context(active_contexts, clarification_context)
        decision = _base_decision(
            raw_text=raw_text,
            surface=surface,
            source_agent=source_agent,
            created_at=created_at,
            active_contexts=active_contexts,
            current_context_id=current_context_id,
            detected_intent="ambiguous_operator_request",
            detected_lane=str(active_context.get("owner_agent") or "cassandra"),
            detected_action_type="clarify_current_or_new_task",
            confidence=0.72,
            decision="clarification_needed",
            routed_to_agent=str(active_context.get("owner_agent") or "cassandra"),
            routed_to_lane=str(active_context.get("context_type") or "guided_review_session"),
            current_task_action="leave_active",
            handoff_reason="Ambiguous instruction should not be recorded as an answer.",
            operator_visible_reply=reply,
        )
        _append_decision_to_read_model(decision, read_model_root=read_model_root, contexts=active_contexts, generated_at_utc=created_at)
        _refresh_watch_desk(read_model_root, created_at)
        return decision

    return _base_decision(
        raw_text=raw_text,
        surface=surface,
        source_agent=source_agent,
        created_at=created_at,
        active_contexts=active_contexts,
        current_context_id=current_context_id,
        detected_intent="active_task_answer_candidate",
        detected_lane=str(active_context.get("owner_agent") or "cassandra"),
        detected_action_type="guided_review_answer_candidate",
        confidence=0.62,
        decision="current_task_continue",
        routed_to_agent=str(active_context.get("owner_agent") or "cassandra"),
        routed_to_lane=str(active_context.get("context_type") or "guided_review_session"),
        current_task_action="continue",
        handoff_reason="No switchboard interrupt detected; active task may consume the message.",
        operator_visible_reply="",
    )


__all__ = [
    "ACTIVE_CONTEXTS_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "process_operator_context_switchboard_message",
    "write_operator_active_contexts_read_model",
]
