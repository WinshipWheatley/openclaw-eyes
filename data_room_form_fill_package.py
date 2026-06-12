"""Data Room form-fill package and manual ChatGPT lane helpers.

This module packages an existing Cassandra guided-review session into a
paste-ready, redacted form-fill prompt. It never calls a model and never creates
confirmed reference data. Imported turn results are advisory unless Winship has
confirmed them and the result names source refs for the affected question.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import cassandra_guided_review as guided


PACKAGE_SCHEMA_VERSION = "DATA_ROOM_FORM_FILL_PACKAGE_V0"
PROMPT_SCHEMA_VERSION = "CHATGPT55_FORM_FILL_PROMPT_V0"
TURN_RESULT_SCHEMA_VERSION = "DATA_ROOM_FORM_FILL_TURN_RESULT_V0"
STATE_SCHEMA_VERSION = "DATA_ROOM_FORM_FILL_STATE_V0"
TURN_LOG_SCHEMA_VERSION = "DATA_ROOM_FORM_FILL_TURN_LOG_ENTRY_V0"

DEFAULT_FORM_FILL_ROOT = guided.DEFAULT_REVIEW_ROOT / "data_room_form_fill"
DEFAULT_DURABLE_FORM_FILL_ROOT = guided.DEFAULT_DURABLE_REVIEW_ROOT / "data_room_form_fill"

EXPECTED_PACKAGE_REPLY = (
    "I packaged the Data Room form for ChatGPT 5.5. It includes the current question, "
    "progress, safety rules, and output schema. Paste this prompt into ChatGPT, then "
    "bring the structured result back here."
)

TURN_SAFETY_FLAGS = {
    "authoritative": False,
    "runtime_policy_changed": False,
    "confirmed_reference_data_created": False,
    "tax_or_legal_advice_given": False,
    "medical_advice_given": False,
    "external_action_performed": False,
}

OPERATOR_INTENTS = {
    "explain",
    "recommend",
    "thought_dump",
    "answer_candidate",
    "confirm",
    "revise",
    "skip",
    "defer",
    "summary",
    "done",
}

QUESTION_STATUSES = {
    "unanswered",
    "candidate_pending",
    "answered",
    "skipped",
    "deferred",
    "needs_source",
}

CONFIDENCE_VALUES = {"high", "medium", "low", ""}

FORBIDDEN_SOURCE_TERMS = (
    "credential",
    "credentials",
    "password",
    "private_key",
    "secret",
    "secrets",
    "token",
    "tokens",
    "api_key",
    "gmail_body",
    "email_body",
    "raw_workbook",
    "raw_document",
)

FORBIDDEN_TEXT_PATTERNS = (
    r"\b\d{3}-\d{2}-\d{4}\b",
    r"\b\d{2}-\d{7}\b",
    r"\b\d{9,}\b",
)


class FormFillValidationError(ValueError):
    """Raised when a manual form-fill turn result is not ingestible."""


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    blob = "\0".join(str(part) for part in parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "data_room_form_fill"


def _rooted(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else guided.ROOT / path


def _form_fill_root(root: str | Path | None) -> Path:
    return _rooted(root or DEFAULT_FORM_FILL_ROOT)


def _durable_form_fill_root(root: str | Path | None) -> Path:
    return _rooted(root or DEFAULT_DURABLE_FORM_FILL_ROOT)


def _package_filename(session_id: str) -> str:
    return f"data_room_form_fill_package_{_safe_filename(session_id)}.json"


def _prompt_filename(session_id: str) -> str:
    return f"chatgpt55_form_fill_prompt_{_safe_filename(session_id)}.md"


def _state_filename(session_id: str) -> str:
    return f"data_room_form_fill_state_{_safe_filename(session_id)}.json"


def _turn_log_filename(session_id: str) -> str:
    return f"data_room_form_fill_turn_log_{_safe_filename(session_id)}.jsonl"


def _artifact_paths(root: Path, session_id: str) -> dict[str, Path]:
    return {
        "package_path": root / _package_filename(session_id),
        "prompt_path": root / _prompt_filename(session_id),
        "state_path": root / _state_filename(session_id),
        "turn_log_path": root / _turn_log_filename(session_id),
    }


def _redact_text(value: Any) -> tuple[str, bool]:
    redacted, sensitive = guided._redact_sensitive_text(str(value or ""))
    for pattern in FORBIDDEN_TEXT_PATTERNS:
        new_value = re.sub(pattern, "[REDACTED_SENSITIVE_DETAIL]", redacted)
        if new_value != redacted:
            sensitive = True
            redacted = new_value
    return redacted, sensitive


def _safe_text(value: Any) -> str:
    return _redact_text(value)[0]


def _safe_list(values: Any) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    safe: list[str] = []
    for value in values:
        text = _safe_text(value)
        if _looks_like_forbidden_source(text):
            safe.append("[REDACTED_SOURCE_REF]")
        elif text:
            safe.append(text)
    return safe


def _looks_like_forbidden_source(value: str) -> bool:
    lowered = value.lower().replace("\\", "/")
    return any(term in lowered for term in FORBIDDEN_SOURCE_TERMS)


def _question_summary(question: Mapping[str, Any]) -> dict[str, Any]:
    source_refs = _safe_list(question.get("source_record_ids") or question.get("affected_records") or [])
    return {
        "question_id": str(question.get("question_id") or ""),
        "category": _safe_text(question.get("category") or ""),
        "question_text": _safe_text(question.get("question_text") or ""),
        "context_summary": _safe_text(question.get("context_summary") or ""),
        "source_record_ids": source_refs,
        "proposed_options": _safe_list(question.get("proposed_options") or []),
        "risk_if_wrong": _safe_text(question.get("risk_if_wrong") or ""),
        "recommended_action": _safe_text(question.get("recommended_action") or ""),
        "answer_status": _safe_text(question.get("answer_status") or "unanswered"),
        "selected_option_id": _safe_text(question.get("selected_option_id") or ""),
        "answer_text": _safe_text(question.get("answer_text") or ""),
        "normalized_answer": _safe_text(question.get("normalized_answer") or ""),
        "authoritative": False,
    }


def _answer_summary(answer: Mapping[str, Any]) -> dict[str, Any]:
    source_refs = _safe_list(answer.get("affected_record_ids") or answer.get("source_refs") or [])
    return {
        "answer_id": str(answer.get("answer_id") or ""),
        "question_id": str(answer.get("question_id") or ""),
        "question_category": _safe_text(answer.get("question_category") or ""),
        "normalized_answer": _safe_text(answer.get("normalized_answer") or ""),
        "selected_option_id": _safe_text(answer.get("selected_option_id") or ""),
        "source_refs": source_refs,
        "receipt_ref": _safe_text(answer.get("receipt_ref") or ""),
        "needs_professional_review": bool(answer.get("needs_professional_review")),
        "authoritative": False,
        "runtime_policy_changed": False,
    }


def _current_question(session: Mapping[str, Any]) -> dict[str, Any]:
    question_id = str(session.get("current_question_id") or "")
    question = guided._question_by_id(session, question_id) if question_id else None
    return _question_summary(question or {}) if question else {}


def _coach_pack_summary(session: Mapping[str, Any]) -> dict[str, Any]:
    question_id = str(session.get("current_question_id") or "")
    question = guided._question_by_id(session, question_id) if question_id else None
    if not question:
        return {}
    card = question.get("coach_card") if isinstance(question, Mapping) else {}
    if not isinstance(card, Mapping) or card.get("schema_version") != "REVIEW_COACH_CARD_V0":
        session_copy = dict(session)
        card = guided._coach_card_for_question(session_copy, question)
    return {
        "question_id": question_id,
        "category": _safe_text(card.get("category") or question.get("category") or ""),
        "plain_context": _safe_text(card.get("plain_context") or ""),
        "recommended_default": _safe_text(card.get("recommended_default") or ""),
        "why_it_matters": _safe_text(card.get("why_it_matters") or ""),
        "examples": _safe_list(card.get("examples") or []),
        "professional_review_flags": _professional_flags_for(card),
        "authoritative": False,
    }


def _professional_flags_for(payload: Mapping[str, Any]) -> list[str]:
    flags: list[str] = []
    if payload.get("cpa_review_recommended"):
        flags.append("cpa_review_recommended")
    if payload.get("legal_review_recommended"):
        flags.append("legal_review_recommended")
    for flag in payload.get("professional_review_flags") or []:
        text = _safe_text(flag)
        if text and text not in flags:
            flags.append(text)
    return flags


def _recent_turns(session: Mapping[str, Any], *, limit: int = 8) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for item in session.get("coach_interactions") or []:
        if not isinstance(item, Mapping):
            continue
        turns.append(
            {
                "kind": "coach_interaction",
                "command": _safe_text(item.get("command") or ""),
                "question_id": _safe_text(item.get("question_id") or ""),
                "selected_option_id": _safe_text(item.get("selected_option_id") or ""),
                "answer_recorded": bool(item.get("answer_recorded")),
                "created_at_utc": _safe_text(item.get("created_at_utc") or ""),
                "authoritative": False,
                "runtime_policy_changed": False,
            }
        )
    for answer in guided._active_answer_records(session):
        turns.append(
            {
                "kind": "provisional_answer",
                "question_id": _safe_text(answer.get("question_id") or ""),
                "normalized_answer": _safe_text(answer.get("normalized_answer") or ""),
                "receipt_ref": _safe_text(answer.get("receipt_ref") or ""),
                "created_at_utc": _safe_text(answer.get("created_at_utc") or ""),
                "authoritative": False,
                "runtime_policy_changed": False,
            }
        )
    return turns[-limit:]


def _prior_chat_log_summary(session: Mapping[str, Any]) -> str:
    progress = guided._progress(session)
    active_answers = guided._active_answer_records(session)
    pending = session.get("pending_interaction")
    parts = [
        (
            f"{progress['answered']} answered, {progress['skipped']} skipped, "
            f"{progress['deferred']} deferred, {progress['remaining']} remaining."
        )
    ]
    if active_answers:
        latest = active_answers[-1]
        parts.append(
            "Latest provisional answer: "
            f"{_safe_text(latest.get('question_id'))} -> {_safe_text(latest.get('normalized_answer'))}."
        )
    if isinstance(pending, Mapping) and pending.get("kind"):
        parts.append(f"Pending interaction: {_safe_text(pending.get('kind'))}.")
    return " ".join(parts)


def expected_turn_result_schema() -> dict[str, Any]:
    return {
        "schema_version": TURN_RESULT_SCHEMA_VERSION,
        "package_id": "",
        "review_session_id": "",
        "turn_id": "",
        "assistant_reply": "",
        "operator_intent": "explain|recommend|thought_dump|answer_candidate|confirm|revise|skip|defer|summary|done",
        "question_id": "",
        "question_status": "unanswered|candidate_pending|answered|skipped|deferred|needs_source",
        "proposed_answer": {
            "plain_english": "",
            "normalized_decision": "",
            "confidence": "high|medium|low",
            "conditions": [],
            "caveats": [],
            "professional_review_flags": [],
        },
        "requires_winship_confirmation": True,
        "confirmed_by_winship": False,
        "questions_updated": [],
        "chat_log_summary_update": "",
        "next_question_id": "",
        "done_criteria_met": False,
        "safety_flags": dict(TURN_SAFETY_FLAGS),
    }


def _source_refs_for_result(result: Mapping[str, Any], question_id: str) -> list[str]:
    refs: list[str] = []
    for item in result.get("questions_updated") or []:
        if not isinstance(item, Mapping):
            continue
        item_question = str(item.get("question_id") or question_id)
        if item_question != question_id:
            continue
        refs.extend(_safe_list(item.get("source_refs") or item.get("source_record_ids") or []))
    return [ref for ref in refs if ref]


def _question_ids(session: Mapping[str, Any]) -> set[str]:
    return {
        str(question.get("question_id") or "")
        for question in session.get("question_queue") or []
        if isinstance(question, Mapping) and question.get("question_id")
    }


def _done_criteria(session: Mapping[str, Any]) -> dict[str, Any]:
    progress = guided._progress(session)
    active_answers = guided._active_answer_records(session)
    answers_by_question = {
        str(answer.get("question_id") or ""): answer
        for answer in active_answers
        if str(answer.get("question_id") or "")
    }
    all_answered_items_have_source_refs = True
    missing_source_questions: list[str] = []
    for question_id in session.get("answered_questions") or []:
        answer = answers_by_question.get(str(question_id), {})
        source_refs = answer.get("affected_record_ids") or answer.get("source_refs") or []
        if not source_refs:
            all_answered_items_have_source_refs = False
            missing_source_questions.append(str(question_id))
    pending = session.get("pending_interaction")
    pending_candidates_resolved = not (isinstance(pending, Mapping) and bool(pending.get("kind")))
    no_safety_flags_violated = True
    no_confirmed_reference_data_exists = True
    every_question_resolved = progress["remaining"] == 0
    promotion_prompt_can_be_generated = (
        every_question_resolved and all_answered_items_have_source_refs and pending_candidates_resolved
    )
    done = (
        every_question_resolved
        and all_answered_items_have_source_refs
        and pending_candidates_resolved
        and no_safety_flags_violated
        and promotion_prompt_can_be_generated
        and no_confirmed_reference_data_exists
    )
    return {
        "every_question_answered_skipped_or_deferred": every_question_resolved,
        "all_answered_items_have_question_id_and_source_refs": all_answered_items_have_source_refs,
        "pending_candidates_resolved": pending_candidates_resolved,
        "no_safety_flags_violated": no_safety_flags_violated,
        "promotion_prompt_can_be_generated": promotion_prompt_can_be_generated,
        "confirmed_reference_data_exists": False,
        "hydration_remains_separate": True,
        "missing_source_questions": missing_source_questions,
        "done": done,
    }


def _professional_review_flags(session: Mapping[str, Any]) -> dict[str, Any]:
    flagged_questions: list[str] = []
    flagged_answers: list[str] = []
    for question in session.get("question_queue") or []:
        if not isinstance(question, Mapping):
            continue
        if question.get("needs_professional_review") or question.get("cpa_review_recommended") or question.get("legal_review_recommended"):
            flagged_questions.append(str(question.get("question_id") or ""))
    for answer in guided._active_answer_records(session):
        if answer.get("needs_professional_review") or answer.get("cpa_review_recommended") or answer.get("legal_review_recommended"):
            flagged_answers.append(str(answer.get("answer_id") or answer.get("question_id") or ""))
    return {
        "cpa_or_legal_review_possible": bool(flagged_questions or flagged_answers),
        "flagged_questions": flagged_questions,
        "flagged_answers": flagged_answers,
        "tax_or_legal_advice_given": False,
        "medical_advice_given": False,
    }


def _load_active_session(review_root: str | Path | None) -> dict[str, Any]:
    session = guided._find_active_session(guided._review_root(review_root))
    if not session:
        raise ValueError("no active Data Room guided review session")
    return session


def build_data_room_form_fill_package(
    session: Mapping[str, Any] | None = None,
    *,
    review_root: str | Path | None = None,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build a redacted package for manual ChatGPT 5.5 form-fill assistance."""

    session = dict(session or _load_active_session(review_root))
    created = created_at_utc or guided.utc_now()
    session_id = str(session.get("review_session_id") or "")
    current_question_id = str(session.get("current_question_id") or "")
    progress = guided._progress(session)
    form_questions = [_question_summary(question) for question in session.get("question_queue") or [] if isinstance(question, Mapping)]
    package_id = "data_room_form_fill_package:" + _short_hash(session_id, current_question_id, created, len(form_questions))
    answered_ids = [str(qid) for qid in session.get("answered_questions") or []]
    skipped_ids = [str(qid) for qid in session.get("skipped_questions") or []]
    deferred_ids = [str(qid) for qid in session.get("deferred_questions") or []]
    questions_by_id = {question["question_id"]: question for question in form_questions}
    return {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "package_id": package_id,
        "created_at_utc": created,
        "review_session_id": session_id,
        "current_question_id": current_question_id,
        "current_question_index": progress["current_number"],
        "total_questions": progress["total"],
        "form_title": _safe_text(session.get("topic_display_name") or "OpenClaw Data Room setup form"),
        "form_goal": (
            "Help Winship complete the provisional Data Room setup review conversationally. "
            "ChatGPT proposes patches only; Cassandra/OpenClaw records deterministic state after confirmation."
        ),
        "form_questions": form_questions,
        "answered_questions": [questions_by_id[qid] for qid in answered_ids if qid in questions_by_id],
        "skipped_questions": [questions_by_id[qid] for qid in skipped_ids if qid in questions_by_id],
        "deferred_questions": [questions_by_id[qid] for qid in deferred_ids if qid in questions_by_id],
        "unresolved_questions": [
            questions_by_id[qid]
            for qid in session.get("unresolved_questions") or []
            if str(qid) in questions_by_id
        ],
        "current_question": _current_question(session),
        "prior_chat_log_summary": _prior_chat_log_summary(session),
        "recent_turns": _recent_turns(session),
        "coach_pack_summary": _coach_pack_summary(session),
        "safety_boundaries": {
            "no_model_call_made_by_openclaw": True,
            "chatgpt55_manual_lane_only": True,
            "chatgpt_mutates_openclaw": False,
            "confirmed_reference_data_created": False,
            "runtime_policy_changed": False,
            "external_action_performed": False,
            "guardian_approval_created": False,
            "email_or_gmail_draft_created": False,
            "invoice_ledger_workbook_pdf_coupa_bank_mutated": False,
            "tax_legal_medical_advice_allowed": False,
            "authority_boundary": dict(guided.AUTHORITY_BOUNDARY),
        },
        "professional_review_flags": _professional_review_flags(session),
        "expected_output_schema": expected_turn_result_schema(),
        "done_criteria": _done_criteria(session),
        "stop_condition": (
            "Stop after producing a structured turn result. Do not claim the form is finalized, "
            "confirmed, promoted, hydrated, or imported."
        ),
    }


def render_chatgpt55_form_fill_prompt(package: Mapping[str, Any]) -> str:
    """Render a paste-ready prompt for manual ChatGPT 5.5 use."""

    current = package.get("current_question") if isinstance(package.get("current_question"), Mapping) else {}
    schema_text = stable_json(package.get("expected_output_schema") or expected_turn_result_schema()).rstrip()
    package_text = stable_json(package).rstrip()
    return f"""# {PROMPT_SCHEMA_VERSION}

You are helping Winship complete an OpenClaw Data Room setup form.

Your job:
- Have a natural conversation.
- Help him understand each question.
- Make conservative recommendations when asked.
- Process messy thoughts and propose clean form patches.
- Support ELI5, analogies, examples, "what would a normal small business do?", "ask me a better question", summaries, and "what is left?".

Rules:
- You do not mutate OpenClaw.
- You do not create confirmed data.
- You do not send email, submit anything, touch ledgers, touch invoices, touch workbooks, touch PDFs, touch Coupa, or perform external actions.
- You do not give tax, legal, or medical advice.
- You propose form patches only.
- Cassandra/OpenClaw records only after Winship confirms.
- Keep raw private details out of your answer. Do not ask for bank/routing/account values, SSNs, EINs, credentials, tokens, raw emails, raw documents, or workbook bodies.

Current form:
- Title: {package.get("form_title", "")}
- Progress: question {package.get("current_question_index", 0)} of {package.get("total_questions", 0)}
- Current question id: {package.get("current_question_id", "")}
- Current question: {current.get("question_text", "")}

After each meaningful turn, return only JSON matching this schema:
{schema_text}

Done criteria:
- Every question is answered, skipped, or deferred.
- Every answered item has a question_id and source refs.
- Pending candidates are resolved.
- No safety flags are violated.
- A later promotion prompt can be generated by OpenClaw.
- No confirmed reference data is created here.
- Hydration remains a separate later step.

Form package:
{package_text}
"""


def _state_payload(package: Mapping[str, Any], *, paths: Mapping[str, Path]) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "package_id": package.get("package_id", ""),
        "review_session_id": package.get("review_session_id", ""),
        "created_at_utc": package.get("created_at_utc", ""),
        "current_question_id": package.get("current_question_id", ""),
        "done_criteria": dict(package.get("done_criteria") or {}),
        "artifact_refs": {key: path.as_posix() for key, path in paths.items()},
        "confirmed_reference_data_created": False,
        "runtime_policy_changed": False,
        "external_action_performed": False,
    }


def write_data_room_form_fill_package(
    package: Mapping[str, Any],
    *,
    output_root: str | Path | None = None,
) -> dict[str, str]:
    """Write package, state, and turn-log shell under one output root."""

    session_id = str(package.get("review_session_id") or "")
    if not session_id:
        raise ValueError("package missing review_session_id")
    root = _form_fill_root(output_root)
    root.mkdir(parents=True, exist_ok=True)
    paths = _artifact_paths(root, session_id)
    paths["package_path"].write_text(stable_json(package), encoding="utf-8")
    paths["state_path"].write_text(stable_json(_state_payload(package, paths=paths)), encoding="utf-8")
    paths["turn_log_path"].touch(exist_ok=True)
    return {key: path.as_posix() for key, path in paths.items() if key != "prompt_path"}


def write_data_room_form_fill_prompt(
    package: Mapping[str, Any],
    prompt: str | None = None,
    *,
    output_root: str | Path | None = None,
) -> str:
    session_id = str(package.get("review_session_id") or "")
    if not session_id:
        raise ValueError("package missing review_session_id")
    root = _form_fill_root(output_root)
    root.mkdir(parents=True, exist_ok=True)
    path = _artifact_paths(root, session_id)["prompt_path"]
    path.write_text(prompt or render_chatgpt55_form_fill_prompt(package), encoding="utf-8")
    return path.as_posix()


def write_data_room_form_fill_artifacts(
    package: Mapping[str, Any],
    *,
    prompt: str | None = None,
    output_root: str | Path | None = None,
    durable_root: str | Path | None = None,
) -> dict[str, Any]:
    """Write temp and durable copies of the package and prompt."""

    rendered_prompt = prompt or render_chatgpt55_form_fill_prompt(package)
    primary_refs = write_data_room_form_fill_package(package, output_root=output_root)
    primary_refs["prompt_path"] = write_data_room_form_fill_prompt(package, rendered_prompt, output_root=output_root)

    durable_refs = write_data_room_form_fill_package(package, output_root=_durable_form_fill_root(durable_root))
    durable_refs["prompt_path"] = write_data_room_form_fill_prompt(
        package,
        rendered_prompt,
        output_root=_durable_form_fill_root(durable_root),
    )
    return {
        "schema_version": "DATA_ROOM_FORM_FILL_ARTIFACT_REFS_V0",
        "package_id": package.get("package_id", ""),
        "review_session_id": package.get("review_session_id", ""),
        "primary": primary_refs,
        "durable": durable_refs,
        "operator_openable_copy": {},
        "external_model_invoked": False,
        "confirmed_reference_data_created": False,
        "runtime_policy_changed": False,
    }


def load_form_fill_turn_result(source: str | Path | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    path = Path(source)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise FormFillValidationError("turn result must be a JSON object")
    return dict(payload)


def _clean_safety_flags(flags: Mapping[str, Any]) -> bool:
    for key, expected in TURN_SAFETY_FLAGS.items():
        if bool(flags.get(key, False)) != expected:
            return False
    for key, value in flags.items():
        if key not in TURN_SAFETY_FLAGS and bool(value):
            return False
    return True


def validate_form_fill_turn_result(
    result: Mapping[str, Any],
    *,
    package: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if result.get("schema_version") != TURN_RESULT_SCHEMA_VERSION:
        errors.append("invalid_schema_version")
    if result.get("package_id") != package.get("package_id"):
        errors.append("package_id_mismatch")
    if result.get("review_session_id") != package.get("review_session_id"):
        errors.append("review_session_id_mismatch")
    if not result.get("turn_id"):
        errors.append("missing_turn_id")
    intent = str(result.get("operator_intent") or "")
    if intent not in OPERATOR_INTENTS:
        errors.append("invalid_operator_intent")
    status = str(result.get("question_status") or "")
    if status not in QUESTION_STATUSES:
        errors.append("invalid_question_status")
    question_id = str(result.get("question_id") or "")
    valid_question_ids = {str(question.get("question_id") or "") for question in package.get("form_questions") or []}
    if question_id and question_id not in valid_question_ids:
        errors.append("unknown_question_id")
    answer = result.get("proposed_answer")
    if not isinstance(answer, Mapping):
        errors.append("missing_proposed_answer")
    else:
        if str(answer.get("confidence") or "") not in CONFIDENCE_VALUES:
            errors.append("invalid_answer_confidence")
    flags = result.get("safety_flags")
    if not isinstance(flags, Mapping) or not _clean_safety_flags(flags):
        errors.append("safety_flags_not_clean")
    if result.get("confirmed_by_winship") and question_id:
        if not _source_refs_for_result(result, question_id):
            errors.append("confirmed_result_missing_source_refs")
        if not isinstance(answer, Mapping) or not str(answer.get("plain_english") or "").strip():
            errors.append("confirmed_result_missing_plain_answer")
    return {
        "valid": not errors,
        "errors": errors,
        "confirmed_by_winship": bool(result.get("confirmed_by_winship")),
        "can_record_provisional_answer": bool(result.get("confirmed_by_winship")) and not errors,
    }


def _append_turn_log(
    result: Mapping[str, Any],
    *,
    package: Mapping[str, Any],
    output_root: str | Path | None,
    recorded_answer_ref: str = "",
    validation: Mapping[str, Any] | None = None,
) -> str:
    session_id = str(package.get("review_session_id") or "")
    root = _form_fill_root(output_root)
    root.mkdir(parents=True, exist_ok=True)
    path = _artifact_paths(root, session_id)["turn_log_path"]
    entry = {
        "schema_version": TURN_LOG_SCHEMA_VERSION,
        "package_id": package.get("package_id", ""),
        "review_session_id": package.get("review_session_id", ""),
        "turn_id": result.get("turn_id", ""),
        "question_id": result.get("question_id", ""),
        "operator_intent": result.get("operator_intent", ""),
        "question_status": result.get("question_status", ""),
        "assistant_reply": _safe_text(result.get("assistant_reply") or ""),
        "chat_log_summary_update": _safe_text(result.get("chat_log_summary_update") or ""),
        "confirmed_by_winship": bool(result.get("confirmed_by_winship")),
        "recorded_answer_ref": recorded_answer_ref,
        "validation": dict(validation or {}),
        "authoritative": False,
        "runtime_policy_changed": False,
        "confirmed_reference_data_created": False,
        "external_action_performed": False,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
    return path.as_posix()


def ingest_form_fill_turn_result_as_candidate(
    result: Mapping[str, Any],
    *,
    package: Mapping[str, Any],
    review_root: str | Path | None = None,
    read_model_root: str | Path | None = None,
    receipt_root: str | Path | None = None,
    output_root: str | Path | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Store advisory turns or confirmed provisional guided-review answers."""

    loaded = load_form_fill_turn_result(result)
    validation = validate_form_fill_turn_result(loaded, package=package)
    if not validation["valid"]:
        log_path = _append_turn_log(loaded, package=package, output_root=output_root, validation=validation)
        return {
            "schema_version": "DATA_ROOM_FORM_FILL_INGEST_RESULT_V0",
            "accepted": False,
            "recorded_provisional_answer": False,
            "validation": validation,
            "turn_log_path": log_path,
            "confirmed_reference_data_created": False,
            "runtime_policy_changed": False,
            "external_action_performed": False,
        }

    root = guided._review_root(review_root)
    session = guided._load_session(root, str(package.get("review_session_id") or ""))
    if not session:
        raise ValueError("guided review session not found")

    recorded_answer_ref = ""
    if loaded.get("confirmed_by_winship"):
        question_id = str(loaded.get("question_id") or "")
        answer = loaded.get("proposed_answer") if isinstance(loaded.get("proposed_answer"), Mapping) else {}
        source_refs = _source_refs_for_result(loaded, question_id)
        guided._apply_answer(
            session,
            str(answer.get("plain_english") or ""),
            surface="chatgpt55_form_fill_manual",
            review_root=root,
            receipt_root=receipt_root,
            now=generated_at_utc or guided.utc_now(),
            question_id_override=question_id,
            extra_answer_fields={
                "answer_source": "chatgpt55_form_fill_confirmed",
                "form_fill_package_id": str(package.get("package_id") or ""),
                "form_fill_turn_id": str(loaded.get("turn_id") or ""),
                "source_refs": source_refs,
                "affected_record_ids": source_refs,
                "authoritative": False,
                "runtime_policy_changed": False,
                "review_status": "answered_pending_promotion",
                "active_for_promotion": True,
            },
        )
        session["updated_at_utc"] = generated_at_utc or guided.utc_now()
        guided._persist_session(session, review_root=root)
        guided.write_guided_review_read_model([session], read_model_root=read_model_root)
        if session.get("answer_records"):
            latest = session["answer_records"][-1]
            recorded_answer_ref = str(latest.get("receipt_ref") or latest.get("answer_id") or "")

    log_path = _append_turn_log(
        loaded,
        package=package,
        output_root=output_root,
        recorded_answer_ref=recorded_answer_ref,
        validation=validation,
    )
    return {
        "schema_version": "DATA_ROOM_FORM_FILL_INGEST_RESULT_V0",
        "accepted": True,
        "recorded_provisional_answer": bool(recorded_answer_ref),
        "recorded_answer_ref": recorded_answer_ref,
        "validation": validation,
        "turn_log_path": log_path,
        "confirmed_reference_data_created": False,
        "runtime_policy_changed": False,
        "external_action_performed": False,
    }


def is_data_room_form_fill_request(text: str) -> bool:
    normalized = guided._normalize_topic_text(text)
    phrases = (
        "open a chatgpt 5 5 lane for this data room form",
        "open chatgpt 5 5 lane for this data room form",
        "package this data room form for chatgpt",
        "make me the chatgpt form fill prompt",
        "make the chatgpt form fill prompt",
        "chatgpt form fill prompt",
        "chatgpt 5 5 form fill",
    )
    return any(phrase in normalized for phrase in phrases)


__all__ = [
    "EXPECTED_PACKAGE_REPLY",
    "PACKAGE_SCHEMA_VERSION",
    "PROMPT_SCHEMA_VERSION",
    "TURN_RESULT_SCHEMA_VERSION",
    "build_data_room_form_fill_package",
    "expected_turn_result_schema",
    "ingest_form_fill_turn_result_as_candidate",
    "is_data_room_form_fill_request",
    "load_form_fill_turn_result",
    "render_chatgpt55_form_fill_prompt",
    "validate_form_fill_turn_result",
    "write_data_room_form_fill_artifacts",
    "write_data_room_form_fill_package",
    "write_data_room_form_fill_prompt",
]
