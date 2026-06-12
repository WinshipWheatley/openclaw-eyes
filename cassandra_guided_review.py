"""Cassandra guided review sessions.

This module runs local, metadata-only review sessions over existing promotion
review artifacts. It records operator answers and receipts, but never promotes
reference data, changes runtime policy, creates approvals, or touches external
systems.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_REVIEW_ROOT = Path("/tmp/openclaw-mission-control/operator_skill_factory_v0")
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_PROMOTION_REVIEW_PATH = DEFAULT_REVIEW_ROOT / "openclaw_data_room_promotion_review_v0.json"
DEFAULT_RECEIPT_DIR_NAME = "data_room_guided_review_receipts"

SESSION_SCHEMA_VERSION = "REVIEW_SESSION_V0"
QUESTION_SCHEMA_VERSION = "REVIEW_QUESTION_V0"
ANSWER_SCHEMA_VERSION = "REVIEW_ANSWER_V0"
READ_MODEL_SCHEMA_VERSION = "guided_review_sessions_read_model_v0"
READ_MODEL_NAME = "guided_review_sessions.json"

SESSION_PREFIX = "data_room_guided_review_session"
PROMPT_PREFIX = "data_room_confirmed_reference_promotion_prompt"
ACTIVE_INDEX_NAME = "data_room_guided_review_active_session.json"

AUTHORITY_BOUNDARY = {
    "authoritative": False,
    "runtime_policy_changed": False,
    "confirmed_reference_data_generated": False,
    "external_calls_performed": False,
    "approval_created": False,
    "email_sent": False,
    "gmail_draft_created": False,
    "invoice_or_ledger_mutated": False,
    "workbook_pdf_coupa_bank_mutated": False,
    "tax_or_legal_advice_given": False,
}

CONTROL_WORDS = {"skip", "defer", "done", "summarize", "summary", "next", "next question", "revise previous"}

EXCLUDED_ROUTE_TERMS = (
    "approve exact send request",
    "approve the exact send request",
    "exact send request",
    "send authority request",
    "prepare the send authority",
    "draft is approved",
    "draft approved",
    "approved with this exact text",
    "operator_action_approval_request",
    "guardian approval",
    "guardian decision",
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rooted(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return ROOT / path


def _short_hash(*parts: object) -> str:
    blob = "\0".join(str(part) for part in parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def _load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected object JSON at {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")
    return path


def _review_root(root: str | Path | None) -> Path:
    return _rooted(root or DEFAULT_REVIEW_ROOT)


def _read_model_root(root: str | Path | None) -> Path:
    return _rooted(root or DEFAULT_READ_MODEL_ROOT)


def _promotion_path(path: str | Path | None) -> Path:
    return _rooted(path or DEFAULT_PROMOTION_REVIEW_PATH)


def _session_path(review_root: Path, session_id: str) -> Path:
    return review_root / f"{SESSION_PREFIX}_{_safe_filename(session_id)}.json"


def _operator_path(review_root: Path, session_id: str) -> Path:
    return review_root / f"{SESSION_PREFIX}_{_safe_filename(session_id)}_OPERATOR.md"


def _prompt_path(review_root: Path, session_id: str) -> Path:
    return review_root / f"{PROMPT_PREFIX}_{_safe_filename(session_id)}.md"


def _active_index_path(review_root: Path) -> Path:
    return review_root / ACTIVE_INDEX_NAME


def _receipt_root(review_root: Path, receipt_root: str | Path | None = None) -> Path:
    return _rooted(receipt_root) if receipt_root else review_root / DEFAULT_RECEIPT_DIR_NAME


def _relative_or_absolute(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _control_text(text: str) -> str:
    lowered = " ".join(text.strip().lower().split())
    lowered = lowered.strip(" .!?")
    if lowered in {"summary", "summarize", "summarise"}:
        return "summarize"
    if lowered in {"done", "finish", "complete", "that's all", "thats all"}:
        return "done"
    if lowered in {"skip", "skip this", "skip question"}:
        return "skip"
    if lowered in {"defer", "defer this", "defer question"}:
        return "defer"
    if lowered in {"next", "next question"}:
        return "next question"
    if lowered in {"revise previous", "revise last", "change previous", "change last"}:
        return "revise previous"
    return ""


def _excluded_route_text(text: str) -> bool:
    lowered = " ".join(text.lower().split())
    return any(term in lowered for term in EXCLUDED_ROUTE_TERMS)


def _start_topic(text: str) -> str:
    lowered = " ".join(text.lower().split()).strip(" .!?")
    if _excluded_route_text(lowered):
        return ""
    if "data room" in lowered and any(term in lowered for term in ("go over", "review", "finish", "questions")):
        return "data_room"
    if "clara reid" in lowered and any(term in lowered for term in ("go over", "review", "rules")):
        return "clara_reid_rules"
    if "invoice policy" in lowered and any(term in lowered for term in ("go over", "review", "finish")):
        return "invoice_policy"
    return ""


def _load_session(review_root: Path, session_id: str) -> dict[str, Any] | None:
    path = _session_path(review_root, session_id)
    if not path.is_file():
        return None
    payload = _load_json(path)
    if payload.get("schema_version") != SESSION_SCHEMA_VERSION:
        return None
    return payload


def _find_active_session(review_root: Path) -> dict[str, Any] | None:
    index_path = _active_index_path(review_root)
    if index_path.is_file():
        try:
            index = _load_json(index_path)
            session_id = str(index.get("review_session_id") or "")
            if session_id:
                session = _load_session(review_root, session_id)
                if session and session.get("status") in {"active", "paused"}:
                    return session
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    for path in sorted(review_root.glob(f"{SESSION_PREFIX}_*.json"), reverse=True):
        if path.name.endswith("_OPERATOR.md") or path.name == ACTIVE_INDEX_NAME:
            continue
        try:
            session = _load_json(path)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if session.get("schema_version") == SESSION_SCHEMA_VERSION and session.get("status") in {"active", "paused"}:
            return session
    return None


def has_active_guided_review_session(*, review_root: str | Path | None = None) -> bool:
    return _find_active_session(_review_root(review_root)) is not None


def is_guided_review_message(text: str, *, review_root: str | Path | None = None) -> bool:
    if not text or not text.strip() or _excluded_route_text(text):
        return False
    if _start_topic(text):
        return True
    active = _find_active_session(_review_root(review_root))
    if not active:
        return False
    if _control_text(text):
        return True
    # Active sessions treat ordinary operator text as an answer.
    return True


def _redact_sensitive_text(text: str) -> tuple[str, bool]:
    redacted = str(text)
    patterns = [
        r"\b\d{3}-\d{2}-\d{4}\b",
        r"\b\d{2}-\d{7}\b",
        r"\b\d{9,}\b",
    ]
    sensitive = False
    for pattern in patterns:
        new_value = re.sub(pattern, "[REDACTED_SENSITIVE_DETAIL]", redacted)
        if new_value != redacted:
            sensitive = True
            redacted = new_value
    return redacted, sensitive


def _normalize_answer(text: str, question: Mapping[str, Any]) -> tuple[str, str, bool]:
    redacted, sensitive = _redact_sensitive_text(text)
    cleaned = " ".join(redacted.strip().split())
    lowered = cleaned.lower()
    if lowered in {"yes", "confirm", "confirmed", "looks good", "approve"}:
        return "confirmed_as_proposed", "high", sensitive
    if lowered in {"no", "reject", "rejected", "do not import"}:
        return "rejected_by_operator", "high", sensitive
    if "not sure" in lowered or "maybe" in lowered or "source" in lowered:
        return f"needs_followup: {cleaned}", "medium", sensitive
    if "direct deposit" in lowered:
        return f"manual_approval_only: {cleaned}", "medium", sensitive
    if "follow" in lowered and "original invoice" in lowered:
        return f"followups_allowed_original_invoices_not_confirmed: {cleaned}", "medium", sensitive
    return cleaned, "medium", sensitive


def _category_for_record(record: Mapping[str, Any]) -> str:
    text = " ".join(
        str(record.get(key) or "")
        for key in ("record_id", "provisional_fact", "proposed_promoted_value", "review_category")
    ).lower()
    if any(term in text for term in ("direct deposit", "payment privacy", "home address", "public phone", "bank account", "routing number", "tax identifiers", "ssn", "ein", "tokens", "credentials", "secrets", "payment_policy")):
        return "payment privacy"
    if "clara" in text:
        return "Clara Reid use"
    if "niles" in text:
        return "Niles public technical-director use"
    if "log rhythm" in text:
        return "Log Rhythm exclusion"
    if any(term in text for term in ("identity", "winship", "sender", "persona")):
        return "identity/persona policy"
    if any(term in text for term in ("rate", "$500", "$125", "$62.50", "speaker rental", "a/v")):
        return "rates"
    if any(term in text for term in ("client", "payer", "capital hilton", "statler", "live arts", "st. anne", "annapolis choral", "annette", "will")):
        return "clients/payers"
    if "venue" in text or "mileage" in text:
        return "venues"
    if any(term in text for term in ("invoice", "payee", "numbering", "filename", "terms", "status")):
        return "invoice numbering/payee policy"
    if "expense" in text:
        return "expense categories"
    if str(record.get("review_category") or "") == "do_not_import":
        return "do-not-import rules"
    return "data room review"


def _priority_for_record(record: Mapping[str, Any]) -> int:
    category = _category_for_record(record)
    order = {
        "payment privacy": 10,
        "identity/persona policy": 20,
        "Clara Reid use": 21,
        "Niles public technical-director use": 22,
        "Log Rhythm exclusion": 23,
        "rates": 30,
        "clients/payers": 40,
        "invoice numbering/payee policy": 50,
        "expense categories": 60,
        "venues": 70,
        "do-not-import rules": 80,
        "data room review": 90,
    }
    return order.get(category, 90)


def _recommended_action(value: Any) -> str:
    action = str(value or "defer").strip().lower().replace(" ", "_")
    if action == "source needed":
        action = "source_needed"
    return action if action in {"confirm", "revise", "reject", "source_needed", "defer"} else "defer"


def _question_text(record: Mapping[str, Any]) -> str:
    category = str(record.get("review_category") or "")
    fact = str(record.get("provisional_fact") or "").lstrip("* ").strip()
    proposed = str(record.get("proposed_promoted_value") or "").lstrip("* ").strip()
    if category == "confirm_ready":
        return f"Can I treat this as confirm-ready for the later promotion packet: {proposed}"
    if category == "needs_correction":
        return f"How should this be revised before promotion: {fact}"
    if category == "needs_source":
        return f"What source or exact operator statement should support this before promotion: {fact}"
    if category == "do_not_import":
        return f"Confirm this remains blocked from active import: {fact}"
    if category == "policy_decision":
        if proposed and fact and fact.lower() not in proposed.lower():
            return f"{proposed} Context: {fact}"
        return proposed or fact
    return proposed or fact


def _topic_matches(record: Mapping[str, Any], topic: str) -> bool:
    if topic in {"", "data_room"}:
        return True
    text = " ".join(
        str(record.get(key) or "")
        for key in ("record_id", "provisional_fact", "proposed_promoted_value", "review_category")
    ).lower()
    if topic == "clara_reid_rules":
        return "clara" in text
    if topic == "invoice_policy":
        return any(term in text for term in ("invoice", "payee", "payment", "zelle", "direct deposit", "terms", "numbering", "status"))
    return True


def build_data_room_review_questions(
    promotion_review: Mapping[str, Any],
    *,
    topic: str = "data_room",
) -> list[dict[str, Any]]:
    records = promotion_review.get("review_records")
    if not isinstance(records, list):
        records = []
    questions: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping) or not _topic_matches(record, topic):
            continue
        record_id = str(record.get("record_id") or f"record:{index}")
        category = _category_for_record(record)
        question_id = f"review_question:{_short_hash(topic, record_id, record.get('provisional_fact', ''))}"
        questions.append(
            {
                "schema_version": QUESTION_SCHEMA_VERSION,
                "question_id": question_id,
                "category": category,
                "priority": _priority_for_record(record),
                "question_text": _question_text(record),
                "context_summary": str(record.get("provisional_fact") or "").lstrip("* ").strip(),
                "source_record_ids": [record_id],
                "proposed_options": _proposed_options_for(record),
                "risk_if_wrong": str(record.get("risk_if_wrong") or ""),
                "recommended_action": _recommended_action(record.get("recommended_action")),
                "answer_status": "unanswered",
                "answer_text": "",
                "normalized_answer": "",
                "affected_records": [record_id],
                "authoritative": False,
            }
        )
    return sorted(questions, key=lambda q: (int(q["priority"]), q["category"], q["question_id"]))


def _proposed_options_for(record: Mapping[str, Any]) -> list[str]:
    category = str(record.get("review_category") or "")
    action = _recommended_action(record.get("recommended_action"))
    if category == "confirm_ready":
        return ["confirm", "revise", "defer"]
    if category == "needs_source":
        return ["source needed", "provide source", "defer"]
    if category == "do_not_import":
        return ["reject/import blocked", "defer", "revise wording"]
    if action == "revise":
        return ["revise", "defer", "reject"]
    return [action.replace("_", " "), "revise", "defer"]


def create_data_room_review_session(
    *,
    topic: str = "data_room",
    operator: str = "Winship",
    surface: str = "telegram",
    review_root: str | Path | None = None,
    promotion_review_path: str | Path | None = None,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    root = _review_root(review_root)
    promotion_path = _promotion_path(promotion_review_path)
    promotion = _load_json(promotion_path)
    created = created_at_utc or utc_now()
    questions = build_data_room_review_questions(promotion, topic=topic)
    session_id = "data_room_review:" + _short_hash(topic, operator, created, len(questions))
    source_refs = [str(promotion_path)]
    source_refs.extend(str(ref) for ref in promotion.get("source_artifacts", []) if str(ref))
    current_question_id = questions[0]["question_id"] if questions else ""
    session = {
        "schema_version": SESSION_SCHEMA_VERSION,
        "review_session_id": session_id,
        "topic": topic,
        "source_artifact_refs": sorted(set(source_refs)),
        "created_at_utc": created,
        "updated_at_utc": created,
        "operator": operator,
        "surface": surface,
        "status": "active" if questions else "blocked",
        "question_queue": questions,
        "current_question_id": current_question_id,
        "answered_questions": [],
        "skipped_questions": [],
        "deferred_questions": [],
        "unresolved_questions": [q["question_id"] for q in questions],
        "answer_records": [],
        "generated_prompt_refs": [],
        "receipt_refs": [],
        "watch_desk_refs": [],
        "authoritative": False,
        "runtime_policy_changed": False,
    }
    _persist_session(session, review_root=root)
    return session


def _question_by_id(session: Mapping[str, Any], question_id: str) -> dict[str, Any] | None:
    for question in session.get("question_queue", []):
        if isinstance(question, Mapping) and question.get("question_id") == question_id:
            return dict(question)
    return None


def _question_index(session: Mapping[str, Any], question_id: str) -> int:
    for index, question in enumerate(session.get("question_queue", [])):
        if isinstance(question, Mapping) and question.get("question_id") == question_id:
            return index
    return -1


def _replace_question(session: dict[str, Any], updated: Mapping[str, Any]) -> None:
    queue = list(session.get("question_queue", []))
    for index, question in enumerate(queue):
        if isinstance(question, Mapping) and question.get("question_id") == updated.get("question_id"):
            queue[index] = dict(updated)
            session["question_queue"] = queue
            return


def _next_unanswered_question_id(session: Mapping[str, Any], *, after_question_id: str = "") -> str:
    queue = [q for q in session.get("question_queue", []) if isinstance(q, Mapping)]
    start = 0
    if after_question_id:
        current_index = _question_index(session, after_question_id)
        start = current_index + 1 if current_index >= 0 else 0
    for question in queue[start:]:
        if question.get("answer_status") == "unanswered":
            return str(question.get("question_id") or "")
    for question in queue:
        if question.get("answer_status") == "unanswered":
            return str(question.get("question_id") or "")
    return ""


def _refresh_session_lists(session: dict[str, Any]) -> None:
    answered: list[str] = []
    skipped: list[str] = []
    deferred: list[str] = []
    unresolved: list[str] = []
    for question in session.get("question_queue", []):
        if not isinstance(question, Mapping):
            continue
        question_id = str(question.get("question_id") or "")
        status = str(question.get("answer_status") or "unanswered")
        if status == "answered":
            answered.append(question_id)
        elif status == "skipped":
            skipped.append(question_id)
            unresolved.append(question_id)
        elif status == "deferred":
            deferred.append(question_id)
            unresolved.append(question_id)
        else:
            unresolved.append(question_id)
    session["answered_questions"] = answered
    session["skipped_questions"] = skipped
    session["deferred_questions"] = deferred
    session["unresolved_questions"] = unresolved


def _progress(session: Mapping[str, Any]) -> dict[str, int]:
    total = len([q for q in session.get("question_queue", []) if isinstance(q, Mapping)])
    answered = len(session.get("answered_questions", []))
    skipped = len(session.get("skipped_questions", []))
    deferred = len(session.get("deferred_questions", []))
    remaining = max(total - answered - skipped - deferred, 0)
    current_index = _question_index(session, str(session.get("current_question_id") or ""))
    return {
        "total": total,
        "answered": answered,
        "skipped": skipped,
        "deferred": deferred,
        "remaining": remaining,
        "current_number": current_index + 1 if current_index >= 0 else 0,
    }


def _progress_line(session: Mapping[str, Any]) -> str:
    progress = _progress(session)
    return (
        f"{progress['answered']} answered, {progress['deferred']} deferred, "
        f"{progress['skipped']} skipped, {progress['remaining']} remaining."
    )


def _format_question_reply(session: Mapping[str, Any], *, prefix: str = "") -> str:
    question_id = str(session.get("current_question_id") or "")
    question = _question_by_id(session, question_id)
    if not question:
        return "No active question is available. Say done to generate the promotion prompt."
    progress = _progress(session)
    lead = f"{prefix}\n\n" if prefix else ""
    return (
        f"{lead}Question {progress['current_number']} of {progress['total']} — "
        f"{question['category']}: {question['question_text']}\n"
        "Reply with an answer, skip, defer, summarize, or done."
    )


def _session_summary_reply(session: Mapping[str, Any]) -> str:
    return f"Data Room review progress: {_progress_line(session)}"


def _answer_id(session_id: str, question_id: str, answer_text: str, created_at: str) -> str:
    return "review_answer:" + _short_hash(session_id, question_id, answer_text, created_at)


def _write_answer_receipt(
    answer: Mapping[str, Any],
    *,
    review_root: Path,
    receipt_root: str | Path | None = None,
) -> str:
    root = _receipt_root(review_root, receipt_root)
    filename = f"{_safe_filename(str(answer['answer_id']))}_receipt.json"
    path = root / filename
    receipt = {
        "schema_version": "REVIEW_ANSWER_RECEIPT_V0",
        "review_session_id": answer["review_session_id"],
        "question_id": answer["question_id"],
        "answer_id": answer["answer_id"],
        "normalized_answer": answer["normalized_answer"],
        "affected_records": answer["affected_record_ids"],
        "authoritative": False,
        "runtime_policy_changed": False,
        "external_calls_performed": False,
        "approval_created": False,
        "invoice_or_ledger_mutated": False,
        "sensitive_detail_redacted": bool(answer.get("sensitive_detail_redacted")),
        "created_at_utc": answer["created_at_utc"],
    }
    _write_json(path, receipt)
    return f"{path.as_posix()}#receipt"


def _apply_answer(
    session: dict[str, Any],
    answer_text: str,
    *,
    surface: str,
    review_root: Path,
    receipt_root: str | Path | None,
    now: str,
) -> None:
    question_id = str(session.get("current_question_id") or "")
    question = _question_by_id(session, question_id)
    if not question:
        return
    normalized, confidence, sensitive = _normalize_answer(answer_text, question)
    redacted_raw, _ = _redact_sensitive_text(answer_text)
    answer = {
        "schema_version": ANSWER_SCHEMA_VERSION,
        "answer_id": _answer_id(session["review_session_id"], question_id, redacted_raw, now),
        "review_session_id": session["review_session_id"],
        "question_id": question_id,
        "raw_answer_text": redacted_raw,
        "normalized_answer": normalized,
        "affected_record_ids": list(question.get("affected_records") or question.get("source_record_ids") or []),
        "confidence": confidence,
        "needs_followup": normalized.startswith("needs_followup:"),
        "created_at_utc": now,
        "source_surface": surface,
        "authoritative": False,
        "review_status": "answered_pending_promotion",
        "runtime_policy_changed": False,
        "sensitive_detail_redacted": sensitive,
    }
    receipt_ref = _write_answer_receipt(answer, review_root=review_root, receipt_root=receipt_root)
    answer["receipt_ref"] = receipt_ref
    question["answer_status"] = "answered"
    question["answer_text"] = redacted_raw
    question["normalized_answer"] = normalized
    question["authoritative"] = False
    _replace_question(session, question)
    session.setdefault("answer_records", []).append(answer)
    session.setdefault("receipt_refs", []).append(receipt_ref)
    session["current_question_id"] = _next_unanswered_question_id(session, after_question_id=question_id)
    _refresh_session_lists(session)


def _mark_current_question(
    session: dict[str, Any],
    *,
    status: str,
    now: str,
) -> None:
    question_id = str(session.get("current_question_id") or "")
    question = _question_by_id(session, question_id)
    if not question:
        return
    question["answer_status"] = status
    question["answer_text"] = ""
    question["normalized_answer"] = status
    question["authoritative"] = False
    _replace_question(session, question)
    session["current_question_id"] = _next_unanswered_question_id(session, after_question_id=question_id)
    session["updated_at_utc"] = now
    _refresh_session_lists(session)


def _persist_session(
    session: Mapping[str, Any],
    *,
    review_root: Path,
) -> Path:
    path = _session_path(review_root, str(session["review_session_id"]))
    _write_json(path, session)
    if session.get("status") in {"active", "paused"}:
        _write_json(
            _active_index_path(review_root),
            {
                "schema_version": "guided_review_active_session_index_v0",
                "review_session_id": session["review_session_id"],
                "session_path": path.as_posix(),
                "updated_at_utc": session.get("updated_at_utc"),
                "authoritative": False,
                "runtime_policy_changed": False,
            },
        )
    return path


def _write_operator_summary(session: Mapping[str, Any], *, review_root: Path) -> str:
    path = _operator_path(review_root, str(session["review_session_id"]))
    progress = _progress(session)
    lines = [
        f"# Data Room Guided Review Session {session['review_session_id']}",
        "",
        "Every item remains provisional until Winship explicitly runs a later promotion task.",
        "",
        f"- Status: {session['status']}",
        f"- Answered: {progress['answered']}",
        f"- Deferred: {progress['deferred']}",
        f"- Skipped: {progress['skipped']}",
        f"- Remaining: {progress['remaining']}",
        f"- Authoritative: false",
        f"- Runtime policy changed: false",
        "",
        "## Answers",
    ]
    if session.get("answer_records"):
        for answer in session["answer_records"]:
            lines.append(f"- * {answer['question_id']}: {answer['normalized_answer']}")
    else:
        lines.append("- * No answers recorded.")
    lines.extend(["", "## Unresolved Questions"])
    unresolved = set(session.get("unresolved_questions", []))
    for question in session.get("question_queue", []):
        if isinstance(question, Mapping) and question.get("question_id") in unresolved:
            lines.append(f"- * {question['question_id']}: {question['question_text']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path.as_posix()


def _write_promotion_prompt(session: Mapping[str, Any], *, review_root: Path) -> str:
    session_path = _session_path(review_root, str(session["review_session_id"]))
    path = _prompt_path(review_root, str(session["review_session_id"]))
    promotion_refs = [ref for ref in session.get("source_artifact_refs", []) if "promotion_review" in str(ref)]
    promotion_ref = promotion_refs[0] if promotion_refs else "openclaw_data_room_promotion_review_v0.json"
    prompt = f"""Task: OPENCLAW_DATA_ROOM_CONFIRMED_REFERENCE_PROMOTION_V0

Repo:
 /home/openclaw

Goal:
Promote only Winship-confirmed Data Room reference items from the guided review answer artifact.

Inputs:
- Answer artifact: {session_path.as_posix()}
- Promotion review artifact: {promotion_ref}

Rules:
- Promote only answered/confirmed items with sufficient confidence.
- Keep unresolved, skipped, deferred, source-needed, and ambiguous items provisional.
- Preserve conflicts that Winship did not explicitly resolve.
- Do not import raw bank, routing, account, tax, SSN, EIN, token, credential, OAuth, API key, secret, or private-note material.
- Do not mutate invoices, ledgers, workbooks, PDFs, Coupa, bank records, or external systems.
- Do not send email, create drafts, call Gmail/Google broker/Calendar/Contacts/browser/Apple Mail/DAW/external APIs, or create approvals.
- Do not import Log Rhythm Records into active identity/client/sender/routing logic.
- Do not import direct deposit details unless explicitly approved and still keep any raw details redacted.
- Do not broadly expose home address or phone unless explicitly approved by trust tier.
- Do not give tax/legal advice.

Return:
OPENCLAW_DATA_ROOM_CONFIRMED_REFERENCE_PROMOTION_READY
or
OPENCLAW_DATA_ROOM_CONFIRMED_REFERENCE_PROMOTION_BLOCKED
"""
    path.write_text(prompt, encoding="utf-8")
    return path.as_posix()


def complete_session(session: dict[str, Any], *, review_root: Path, now: str) -> dict[str, Any]:
    session["status"] = "completed"
    session["updated_at_utc"] = now
    _refresh_session_lists(session)
    operator_ref = _write_operator_summary(session, review_root=review_root)
    prompt_ref = _write_promotion_prompt(session, review_root=review_root)
    generated_refs = list(session.get("generated_prompt_refs", []))
    for ref in (operator_ref, prompt_ref):
        if ref not in generated_refs:
            generated_refs.append(ref)
    session["generated_prompt_refs"] = generated_refs
    session["current_question_id"] = ""
    _persist_session(session, review_root=review_root)
    index = _active_index_path(review_root)
    if index.exists():
        try:
            index.unlink()
        except OSError:
            pass
    return session


def _session_read_model_item(session: Mapping[str, Any]) -> dict[str, Any]:
    progress = _progress(session)
    session_id = str(session.get("review_session_id") or "")
    session_ref = _session_path(DEFAULT_REVIEW_ROOT, session_id).as_posix()
    if session.get("session_artifact_ref"):
        session_ref = str(session["session_artifact_ref"])
    status = str(session.get("status") or "active")
    verb = "in progress" if status in {"active", "paused"} else status
    return {
        "item_id": f"guided_review:{session_id}",
        "lane": "chief_runtime",
        "urgency": "needs_operator" if status in {"active", "paused"} else "info",
        "plain_line": (
            f"Data Room review {verb}: {progress['answered']} answered, "
            f"{progress['deferred']} deferred, {progress['remaining']} remaining."
        ),
        "source_receipt_ref": f"{session_ref}#session",
        "one_next_safe_action": "Continue the guided review with Cassandra, or say done to generate the Codex promotion prompt.",
        "push_class": "info",
        "review_session_id": session_id,
        "status": status,
        "answered_count": progress["answered"],
        "deferred_count": progress["deferred"],
        "remaining_count": progress["remaining"],
    }


def write_guided_review_read_model(
    sessions: Sequence[Mapping[str, Any]],
    *,
    read_model_root: str | Path | None = None,
    generated_at_utc: str | None = None,
) -> Path:
    root = _read_model_root(read_model_root)
    root.mkdir(parents=True, exist_ok=True)
    generated_at = generated_at_utc or utc_now()
    session_rows = [dict(session) for session in sessions]
    for session in session_rows:
        if not session.get("session_artifact_ref"):
            session["session_artifact_ref"] = _session_path(
                DEFAULT_REVIEW_ROOT,
                str(session["review_session_id"]),
            ).as_posix()
    payload = {
        "schema_version": READ_MODEL_SCHEMA_VERSION,
        "generated_at": generated_at,
        "session_count": len(session_rows),
        "active_session_count": len([s for s in session_rows if s.get("status") in {"active", "paused"}]),
        "sessions": session_rows,
        "watch_desk_items": [_session_read_model_item(session) for session in session_rows],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    path = root / READ_MODEL_NAME
    path.write_text(stable_json(payload), encoding="utf-8")
    return path


def _refresh_watch_desk(read_model_root: str | Path | None, generated_at: str) -> dict[str, Any]:
    try:
        from watch_desk_feed import export_watch_desk_feed

        return export_watch_desk_feed(
            read_model_root=_read_model_root(read_model_root),
            export_root=_read_model_root(read_model_root),
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


def _artifact_refs(session: Mapping[str, Any], *, review_root: Path, read_model_root: str | Path | None) -> dict[str, Any]:
    session_path = _session_path(review_root, str(session["review_session_id"]))
    return {
        "session_json": session_path.as_posix(),
        "operator_markdown": _operator_path(review_root, str(session["review_session_id"])).as_posix(),
        "promotion_prompt": _prompt_path(review_root, str(session["review_session_id"])).as_posix(),
        "guided_review_read_model": (_read_model_root(read_model_root) / READ_MODEL_NAME).as_posix(),
        "receipts": list(session.get("receipt_refs", [])),
        "generated_prompt_refs": list(session.get("generated_prompt_refs", [])),
    }


def _response(
    *,
    session: Mapping[str, Any],
    reply_text: str,
    review_root: Path,
    read_model_root: str | Path | None,
    watch_refresh: Mapping[str, Any] | None = None,
    handled: bool = True,
) -> dict[str, Any]:
    progress = _progress(session)
    return {
        "schema_version": "guided_review_surface_response_v0",
        "handled": handled,
        "reply_text": reply_text,
        "reply": reply_text,
        "review_session_id": session.get("review_session_id", ""),
        "current_question_id": session.get("current_question_id", ""),
        "progress": progress,
        "status": session.get("status", ""),
        "artifact_refs": _artifact_refs(session, review_root=review_root, read_model_root=read_model_root),
        "receipt_refs": list(session.get("receipt_refs", [])),
        "watch_desk_refs": list(session.get("watch_desk_refs", [])),
        "watch_desk_refresh": dict(watch_refresh or {}),
        "safety_flags": dict(AUTHORITY_BOUNDARY),
        "authoritative": False,
        "runtime_policy_changed": False,
        "external_calls_performed": False,
    }


def process_guided_review_message(
    raw_text: str,
    *,
    surface: str = "telegram",
    operator: str = "Winship",
    review_root: str | Path | None = None,
    read_model_root: str | Path | None = None,
    promotion_review_path: str | Path | None = None,
    receipt_root: str | Path | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any] | None:
    """Process a Cassandra guided-review turn without external side effects."""

    if not raw_text or not raw_text.strip() or _excluded_route_text(raw_text):
        return None
    root = _review_root(review_root)
    now = generated_at_utc or utc_now()
    active = _find_active_session(root)
    topic = _start_topic(raw_text)
    if not active and not topic:
        return None
    if not active:
        try:
            session = create_data_room_review_session(
                topic=topic or "data_room",
                operator=operator,
                surface=surface,
                review_root=root,
                promotion_review_path=promotion_review_path,
                created_at_utc=now,
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            blocked = {
                "schema_version": SESSION_SCHEMA_VERSION,
                "review_session_id": "data_room_review:blocked",
                "topic": topic or "data_room",
                "source_artifact_refs": [str(_promotion_path(promotion_review_path))],
                "created_at_utc": now,
                "updated_at_utc": now,
                "operator": operator,
                "surface": surface,
                "status": "blocked",
                "question_queue": [],
                "current_question_id": "",
                "answered_questions": [],
                "skipped_questions": [],
                "deferred_questions": [],
                "unresolved_questions": [],
                "answer_records": [],
                "generated_prompt_refs": [],
                "receipt_refs": [],
                "watch_desk_refs": [],
                "authoritative": False,
                "runtime_policy_changed": False,
            }
            return _response(
                session=blocked,
                reply_text=f"I could not start the Data Room review because the promotion review artifact is unavailable: {type(exc).__name__}.",
                review_root=root,
                read_model_root=read_model_root,
                handled=True,
            )
        total = len(session["question_queue"])
        intro = (
            f"Cool. I found {total} provisional Data Room review items. I'll walk you through "
            "the highest-impact questions first: identity, payment privacy, rates, clients, "
            "invoice numbering. You can answer, skip, defer, revise, summarize, or say done."
        )
        reply = _format_question_reply(session, prefix=intro)
    else:
        session = dict(active)
        control = _control_text(raw_text)
        if topic:
            reply = _format_question_reply(session, prefix="Continuing the active Data Room review.")
        elif control == "summarize":
            reply = _session_summary_reply(session)
        elif control == "done":
            session = complete_session(session, review_root=root, now=now)
            prompt = _prompt_path(root, str(session["review_session_id"]))
            reply = (
                f"Done. Data Room review closed: {_progress_line(session)} "
                f"I wrote the answer artifact and Codex promotion prompt: {prompt.as_posix()}"
            )
        elif control == "skip" or control == "next question":
            _mark_current_question(session, status="skipped", now=now)
            reply = _format_question_reply(session, prefix="Skipped.")
        elif control == "defer":
            _mark_current_question(session, status="deferred", now=now)
            reply = _format_question_reply(session, prefix="Deferred.")
        elif control == "revise previous":
            reply = "Send the corrected answer now. I will record it against the current question unless you say done."
        else:
            _apply_answer(
                session,
                raw_text,
                surface=surface,
                review_root=root,
                receipt_root=receipt_root,
                now=now,
            )
            if not session.get("current_question_id"):
                session = complete_session(session, review_root=root, now=now)
                reply = (
                    f"Recorded. All questions are answered, skipped, or deferred. "
                    f"I wrote the promotion prompt: {_prompt_path(root, str(session['review_session_id'])).as_posix()}"
                )
            else:
                reply = _format_question_reply(session, prefix="Recorded.")
        session["updated_at_utc"] = now
        _persist_session(session, review_root=root)

    session_path = _persist_session(session, review_root=root)
    session["session_artifact_ref"] = session_path.as_posix()
    write_guided_review_read_model([session], read_model_root=read_model_root, generated_at_utc=now)
    watch_item = _session_read_model_item(session)
    session["watch_desk_refs"] = [watch_item["item_id"]]
    _persist_session(session, review_root=root)
    write_guided_review_read_model([session], read_model_root=read_model_root, generated_at_utc=now)
    watch_refresh = _refresh_watch_desk(read_model_root, now)
    return _response(
        session=session,
        reply_text=reply,
        review_root=root,
        read_model_root=read_model_root,
        watch_refresh=watch_refresh,
        handled=True,
    )


__all__ = [
    "ANSWER_SCHEMA_VERSION",
    "QUESTION_SCHEMA_VERSION",
    "READ_MODEL_NAME",
    "SESSION_SCHEMA_VERSION",
    "build_data_room_review_questions",
    "complete_session",
    "create_data_room_review_session",
    "has_active_guided_review_session",
    "is_guided_review_message",
    "process_guided_review_message",
    "stable_json",
    "write_guided_review_read_model",
]
