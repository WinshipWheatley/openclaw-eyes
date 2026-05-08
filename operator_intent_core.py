"""Surface-neutral Operator Intent Core v0.

This module classifies and frames natural operator language. It is deterministic,
local, and non-executing by design.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence


INTENT_CLASSES = (
    "status_brief",
    "next_safe_action",
    "tired_tell_me_what_matters",
    "codex_prompt_request",
    "gemini_review_request",
    "commit_review_request",
    "push_confirmation_context",
    "handoff_request",
    "activation_readiness_question",
    "approval_required_action",
    "unsafe_or_ambiguous_action",
    "stop_or_wait_instruction",
)

REQUEST_CATEGORIES = (
    "read_only_status",
    "prompt_generation",
    "review",
    "approval_sensitive",
    "unsafe_or_ambiguous",
    "stop",
)

FORBIDDEN_ACTIONS = (
    "live runtime launch",
    "assistant daemon/listener",
    "process or service scan",
    "systemd/launchctl/service mutation",
    "provider/model/API call",
    "MCP call or write",
    "hidden memory write",
    "invoice, money, legal, private-root, or sensitive-data action",
    "external send",
    "commit, push, or destructive operation without its separate gate",
)

COMMON_EVIDENCE_SURFACES = (
    "./scripts/openclaw_receipts.py repo-check",
    "./scripts/openclaw_receipts.py packet-status",
    "./scripts/openclaw_receipts.py operator-harness-status",
)

RUNTIME_EVIDENCE_SURFACES = (
    "./scripts/openclaw_receipts.py gated-activation-status",
    "./scripts/openclaw_receipts.py runtime-dry-run-readiness",
    "./scripts/openclaw_receipts.py activation-evidence-status",
)

PROMPT_EVIDENCE_SURFACES = (
    "./scripts/openclaw_receipts.py prompt-pack-status",
    "Packet 07 File 14 model/tool-specific prompt doctrine",
)


@dataclass(frozen=True)
class OperatorIntent:
    name: str
    confidence: str
    request_category: str
    matched_phrase: str
    original_text: str
    tool_route: str
    execution_authority: bool = False


@dataclass(frozen=True)
class OperatorIntentFrame:
    intent_name: str
    request_category: str
    recommended_response_frame: str
    follow_up_required: bool
    forbidden_actions: tuple[str, ...]
    evidence_surfaces: tuple[str, ...]
    tool_route: str
    current_authority: str
    future_gate: str
    execution_authority: bool = False


@dataclass(frozen=True)
class _Rule:
    intent: str
    request_category: str
    confidence: str
    phrases: tuple[str, ...]
    tool_route: str = "operator_response"


_RULES: tuple[_Rule, ...] = (
    _Rule(
        "stop_or_wait_instruction",
        "stop",
        "exact",
        ("stop", "wait", "pause", "hold", "do not continue"),
    ),
    _Rule(
        "tired_tell_me_what_matters",
        "read_only_status",
        "exact",
        ("i'm tired, tell me what matters", "tell me what matters"),
    ),
    _Rule(
        "codex_prompt_request",
        "prompt_generation",
        "exact",
        ("send that to codex", "give this to codex", "codex should do it"),
        "codex_bounded_repo_prompt",
    ),
    _Rule(
        "gemini_review_request",
        "prompt_generation",
        "exact",
        ("ask gemini", "run it by gemini", "get gemini's take"),
        "gemini_architecture_scope_review",
    ),
    _Rule(
        "commit_review_request",
        "review",
        "exact",
        ("review this for commit", "ready to commit", "commit readiness"),
        "codex_diff_commit_readiness_review",
    ),
    _Rule(
        "push_confirmation_context",
        "approval_sensitive",
        "exact",
        ("can i push", "should we push", "safe to push"),
        "operator_external_send_gate",
    ),
    _Rule(
        "handoff_request",
        "prompt_generation",
        "exact",
        ("make a handoff", "write the handoff", "log this"),
        "operator_handoff_draft",
    ),
    _Rule(
        "approval_required_action",
        "approval_sensitive",
        "exact",
        ("go ahead", "launch it", "activate it", "turn it on", "send it"),
        "approval_gate_required",
    ),
    _Rule(
        "activation_readiness_question",
        "approval_sensitive",
        "exact",
        ("can we move forward", "are we launch-ready", "is activation ready"),
        "activation_readiness_review",
    ),
    _Rule(
        "next_safe_action",
        "read_only_status",
        "exact",
        ("what's next", "what should i do", "do the next thing"),
    ),
    _Rule(
        "status_brief",
        "read_only_status",
        "exact",
        ("where are we", "status", "catch me up", "what changed"),
    ),
    _Rule(
        "unsafe_or_ambiguous_action",
        "unsafe_or_ambiguous",
        "heuristic",
        ("just handle it", "do whatever", "fix everything"),
        "operator_clarification",
    ),
)

_FRAMES = {
    "status_brief": (
        "Give a concise state brief: repo state, active packet, changed files, "
        "receipt posture, next visible lane, and blocked gates."
    ),
    "next_safe_action": (
        "Name the next safe move, explain why it is safe, and state what would "
        "require separate approval before doing more."
    ),
    "tired_tell_me_what_matters": (
        "Protect attention: give only the state, the risk, the next safe move, "
        "and what remains forbidden."
    ),
    "codex_prompt_request": (
        "Frame a Codex prompt for bounded repo work: scope, allowed surfaces, "
        "tests, validation, no broad refactor, and no commit/push unless gated."
    ),
    "gemini_review_request": (
        "Frame a Gemini prompt for architecture, planning, risk, synthesis, or "
        "scope review; model output is advice, not execution approval."
    ),
    "commit_review_request": (
        "Use commit-readiness review: findings first, changed files, tests, "
        "boundary leaks, and READY_TO_COMMIT or NOT_READY."
    ),
    "push_confirmation_context": (
        "Separate local commit readiness from external remote mutation; summarize "
        "required final checks and require explicit push authority."
    ),
    "handoff_request": (
        "Prepare a concise train-log handoff: completed work, validation, next "
        "visible lane, File 01 authority, and gated surfaces."
    ),
    "activation_readiness_question": (
        "Separate readiness evidence from approval; name current authorization "
        "status, dry-run evidence, and the next gate."
    ),
    "approval_required_action": (
        "Do not execute from natural language alone. Name the action-right level, "
        "missing evidence, explicit approval gate, and current non-authority."
    ),
    "unsafe_or_ambiguous_action": (
        "Narrow the request into the smallest safe next move and ask for the "
        "specific scope or approval needed before crossing a gate."
    ),
    "stop_or_wait_instruction": (
        "Stop optional forward motion, preserve the current state, and report the "
        "last safe state plus the pending next step."
    ),
}

_FUTURE_GATES = {
    "status_brief": "Level 1 read-only local evidence gate",
    "next_safe_action": "Level 1 read-only local evidence gate, then tool-specific gate if mutating",
    "tired_tell_me_what_matters": "Level 1 read-only local evidence gate",
    "codex_prompt_request": "Level 2 prompt generation gate; Level 3 for repo mutation",
    "gemini_review_request": "Level 2 prompt generation gate; provider calls need separate policy",
    "commit_review_request": "Level 3 bounded repo review/commit gate",
    "push_confirmation_context": "Level 5 external-send/remote-mutation gate",
    "handoff_request": "Level 2 draft gate; Level 3 if writing repo docs",
    "activation_readiness_question": "activation evidence gate, then future explicit approval",
    "approval_required_action": "explicit action-right approval gate with receipts and rollback",
    "unsafe_or_ambiguous_action": "clarification before any action-right level",
    "stop_or_wait_instruction": "stop condition; no future gate needed to pause",
}


def _normalize(text: str) -> str:
    lowered = text.lower().strip()
    lowered = lowered.replace("’", "'").replace("“", '"').replace("”", '"')
    lowered = re.sub(r"[^a-z0-9'\s-]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _contains_phrase(normalized_text: str, phrase: str) -> bool:
    normalized_phrase = _normalize(phrase)
    return bool(re.search(rf"\b{re.escape(normalized_phrase)}\b", normalized_text))


def classify_operator_intent(text: str) -> OperatorIntent:
    """Classify operator language without executing or reading external state."""
    normalized = _normalize(text)
    if not normalized:
        return OperatorIntent(
            name="unsafe_or_ambiguous_action",
            confidence="ambiguous",
            request_category="unsafe_or_ambiguous",
            matched_phrase="",
            original_text=text,
            tool_route="operator_clarification",
        )

    for rule in _RULES:
        for phrase in rule.phrases:
            if _contains_phrase(normalized, phrase):
                return OperatorIntent(
                    name=rule.intent,
                    confidence=rule.confidence,
                    request_category=rule.request_category,
                    matched_phrase=phrase,
                    original_text=text,
                    tool_route=rule.tool_route,
                )

    if normalized.endswith("?") or normalized.startswith(("what ", "where ", "can we ")):
        return OperatorIntent(
            name="next_safe_action",
            confidence="low",
            request_category="read_only_status",
            matched_phrase="heuristic_question",
            original_text=text,
            tool_route="operator_response",
        )

    return OperatorIntent(
        name="unsafe_or_ambiguous_action",
        confidence="ambiguous",
        request_category="unsafe_or_ambiguous",
        matched_phrase="fallback",
        original_text=text,
        tool_route="operator_clarification",
    )


def _evidence_for(intent: OperatorIntent) -> tuple[str, ...]:
    if intent.name in {"status_brief", "next_safe_action", "tired_tell_me_what_matters"}:
        return COMMON_EVIDENCE_SURFACES
    if intent.name in {"codex_prompt_request", "gemini_review_request", "commit_review_request"}:
        return PROMPT_EVIDENCE_SURFACES + COMMON_EVIDENCE_SURFACES
    if intent.name in {
        "activation_readiness_question",
        "approval_required_action",
        "push_confirmation_context",
    }:
        return RUNTIME_EVIDENCE_SURFACES + COMMON_EVIDENCE_SURFACES
    if intent.name == "handoff_request":
        return (
            "Packet 07 active handoff",
            "Packet 07 File 01 roadmap authority",
        ) + COMMON_EVIDENCE_SURFACES
    return COMMON_EVIDENCE_SURFACES


def _follow_up_required(intent: OperatorIntent) -> bool:
    return intent.name in {
        "approval_required_action",
        "unsafe_or_ambiguous_action",
        "push_confirmation_context",
        "activation_readiness_question",
    } or intent.matched_phrase in {"do the next thing", "go ahead"}


def frame_operator_intent(intent: OperatorIntent) -> OperatorIntentFrame:
    """Return the safe response frame for a classified operator intent."""
    return OperatorIntentFrame(
        intent_name=intent.name,
        request_category=intent.request_category,
        recommended_response_frame=_FRAMES[intent.name],
        follow_up_required=_follow_up_required(intent),
        forbidden_actions=FORBIDDEN_ACTIONS,
        evidence_surfaces=_evidence_for(intent),
        tool_route=intent.tool_route,
        current_authority="classification_and_response_framing_only",
        future_gate=_FUTURE_GATES[intent.name],
        execution_authority=False,
    )


def classify_and_frame_operator_intent(text: str) -> OperatorIntentFrame:
    """Convenience wrapper for consumers that only need the frame."""
    return frame_operator_intent(classify_operator_intent(text))


def sample_phrase_matrix() -> tuple[tuple[str, str], ...]:
    """Return the required v0 phrase coverage as static test/receipt evidence."""
    return (
        ("where are we", "status_brief"),
        ("what's next", "next_safe_action"),
        ("what should I do", "next_safe_action"),
        ("I'm tired, tell me what matters", "tired_tell_me_what_matters"),
        ("tell me what matters", "tired_tell_me_what_matters"),
        ("can we move forward", "activation_readiness_question"),
        ("send that to Codex", "codex_prompt_request"),
        ("ask Gemini", "gemini_review_request"),
        ("review this for commit", "commit_review_request"),
        ("can I push", "push_confirmation_context"),
        ("make a handoff", "handoff_request"),
        ("do the next thing", "next_safe_action"),
        ("go ahead", "approval_required_action"),
        ("launch it", "approval_required_action"),
        ("activate it", "approval_required_action"),
        ("wait", "stop_or_wait_instruction"),
        ("stop", "stop_or_wait_instruction"),
    )


def classify_phrase_matrix(
    phrases: Sequence[tuple[str, str]] | None = None,
) -> tuple[dict[str, object], ...]:
    """Classify the phrase matrix for deterministic receipt/tests."""
    matrix = phrases if phrases is not None else sample_phrase_matrix()
    rows: list[dict[str, object]] = []
    for phrase, expected_intent in matrix:
        intent = classify_operator_intent(phrase)
        frame = frame_operator_intent(intent)
        rows.append(
            {
                "phrase": phrase,
                "expected_intent": expected_intent,
                "actual_intent": intent.name,
                "passed": intent.name == expected_intent,
                "execution_authority": frame.execution_authority,
                "follow_up_required": frame.follow_up_required,
                "tool_route": frame.tool_route,
            }
        )
    return tuple(rows)
