"""Operator Extension Simulation Harness v0.

This module joins natural language, Operator Intent Core, and Action Covenant
posture into a deterministic local simulation. It frames what the system should
say next; it never executes, persists, calls providers, touches runtime, or
grants authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from operator_action_covenant import (
    AuthorityLevel,
    OperatorActionCovenant,
    can_operator_confirmation_approve,
    create_action_covenant,
)
from operator_intent_core import (
    FORBIDDEN_ACTIONS as INTENT_CORE_FORBIDDEN_ACTIONS,
    classify_operator_intent,
    frame_operator_intent,
)


USES_OPERATOR_INTENT_CORE = True
USES_OPERATOR_ACTION_COVENANT = True

INPUT_SOURCES = (
    "operator_speech",
    "agent_proposal",
    "system_action_description",
    "unknown",
)

STATUS_ORIENTATION_PHRASES = (
    "where are we",
    "what's next",
    "what should i do",
    "i'm tired tell me what matters",
    "tell me what matters",
    "are we good",
    "what changed",
    "what needs my attention",
)

DRAFT_REVIEW_HANDOFF_PHRASES = (
    "send that to codex",
    "give this to the coder",
    "make a prompt for the next worker",
    "ask gemini",
    "get a second opinion",
    "review this for commit",
    "is this ready to commit",
    "make a handoff",
    "prepare the next chat",
    "this is ready to push",
    "i recommend committing this",
    "i can update the handoff",
)

APPROVAL_SENSITIVE_PHRASES = (
    "can i push",
    "go ahead",
    "do it",
    "do the next thing",
    "can we move forward",
    "handle it",
    "take care of that",
    "make it happen",
    "proceed",
    "ship it",
)

RESTRICTED_PHRASES = (
    "launch it",
    "activate it",
    "start the runtime",
    "write to mcp memory",
    "call the provider",
    "use the api",
    "send the invoice",
    "reconcile billing",
    "touch legal files",
    "read private root",
    "send the email",
    "delete the files",
    "create packet 08",
)

NO_LIVE_AUTHORITY = (
    "live runtime launch",
    "MCP call or write",
    "provider/model/API call",
    "invoice, money, legal, private-root, or sensitive-data action",
    "external send",
    "destructive filesystem operation",
    "hidden memory write",
    "Packet 08 creation",
)

SIMULATOR_EVIDENCE = (
    "operator_intent_core.py",
    "operator_action_covenant.py",
    "OPERATOR_EXTENSION_MANIFESTO.md",
    "./scripts/openclaw_receipts.py operator-intent-core-status",
    "./scripts/openclaw_receipts.py operator-action-covenant-status",
)

_FIXED_COVENANT_EXPIRY = datetime(2099, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class OperatorExtensionSimulation:
    original_text: str
    input_source_guess: str
    inferred_intent: str
    intent_core_intent: str
    request_category: str
    recommended_response_frame: str
    execution_authority: bool
    covenant_required: bool
    covenant_allowed_in_v0: bool
    suggested_covenant: OperatorActionCovenant | None
    restricted_block: bool
    restricted_domains: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    follow_up_required: bool
    yes_no_reframe: str
    operator_facing_summary: str
    tool_route: str
    covenant_decision_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Meaning:
    inferred_intent: str
    request_category: str
    response_frame: str
    summary: str
    tool_route: str = "operator_response"
    covenant_required: bool = False
    covenant_allowed_in_v0: bool = False
    suggested_authority_level: str = ""
    suggested_risk_level: str = ""
    suggested_action: str = ""
    rollback_plan: str = ""
    restricted_block: bool = False
    restricted_domains: tuple[str, ...] = ()
    follow_up_required: bool = False
    yes_no_reframe: str = ""


def _normalize(text: str) -> str:
    lowered = text.lower().strip()
    lowered = lowered.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    chars = []
    for char in lowered:
        if char.isalnum() or char in {"'", " "}:
            chars.append(char)
        else:
            chars.append(" ")
    return " ".join("".join(chars).split())


def _contains_any(normalized: str, phrases: Sequence[str]) -> str:
    for phrase in phrases:
        candidate = _normalize(phrase)
        if candidate and candidate in normalized:
            return phrase
    return ""


def _guess_input_source(normalized: str) -> str:
    if not normalized:
        return "unknown"
    if normalized.startswith(
        (
            "i recommend",
            "i can",
            "i suggest",
            "this is ready",
            "recommend ",
            "proposal ",
        )
    ):
        return "agent_proposal"
    if normalized.startswith(
        (
            "send invoice",
            "send the invoice",
            "write mcp",
            "write to mcp",
            "launch runtime",
            "start runtime",
            "start the runtime",
            "create draft",
            "delete files",
            "delete the files",
            "call provider",
            "call the provider",
            "use api",
            "use the api",
            "reconcile billing",
            "touch legal",
            "read private",
            "create packet 08",
        )
    ):
        return "system_action_description"
    return "operator_speech"


def _base_meaning(text: str, normalized: str) -> _Meaning:
    if not normalized:
        return _Meaning(
            inferred_intent="unsafe_or_ambiguous_action",
            request_category="unsafe_or_ambiguous",
            response_frame="Ask for the smallest concrete action before any gate is crossed.",
            summary="I need a specific action before I can frame the safe next move.",
            follow_up_required=True,
            yes_no_reframe="Name the exact action, evidence, boundary, and rollback you want evaluated.",
        )

    restricted = _restricted_meaning(normalized)
    if restricted is not None:
        return restricted

    draft_or_review = _draft_review_meaning(normalized)
    if draft_or_review is not None:
        return draft_or_review

    status = _status_meaning(normalized)
    if status is not None:
        return status

    approval = _approval_meaning(normalized)
    if approval is not None:
        return approval

    core_intent = classify_operator_intent(text)
    core_frame = frame_operator_intent(core_intent)
    return _Meaning(
        inferred_intent=core_intent.name,
        request_category=core_frame.request_category,
        response_frame=core_frame.recommended_response_frame,
        summary="I can frame the likely next safe move, but I will not treat this as permission.",
        tool_route=core_frame.tool_route,
        follow_up_required=core_frame.follow_up_required,
        yes_no_reframe=(
            "Do you want a status brief, a prompt draft, or a specific Action Covenant?"
            if core_frame.follow_up_required
            else ""
        ),
    )


def _status_meaning(normalized: str) -> _Meaning | None:
    if _contains_any(
        normalized,
        (
            "i'm tired tell me what matters",
            "im tired tell me what matters",
            "tell me what matters",
            "what needs my attention",
        ),
    ):
        return _Meaning(
            inferred_intent="tired_tell_me_what_matters",
            request_category="read_only_status",
            response_frame="Protect attention: state, risk, next safe move, and hard gates only.",
            summary="This is operator relief. I can tell you only what matters. No Covenant needed.",
            follow_up_required=False,
        )
    if _contains_any(normalized, ("where are we", "what changed", "are we good", "status")):
        return _Meaning(
            inferred_intent="status_brief",
            request_category="read_only_status",
            response_frame="Give a compact status brief and name the next safe lane.",
            summary="This is a read-only/status request. No Covenant needed.",
            follow_up_required=False,
        )
    if _contains_any(normalized, ("what's next", "whats next", "what should i do")):
        return _Meaning(
            inferred_intent="next_safe_action",
            request_category="read_only_status",
            response_frame="Name the next safe move and the gate before anything state-changing.",
            summary="I can propose the next safe action. I will not act from this alone.",
            follow_up_required=False,
        )
    return None


def _draft_review_meaning(normalized: str) -> _Meaning | None:
    if _contains_any(normalized, ("send that to codex", "give this to the coder")):
        return _Meaning(
            inferred_intent="codex_prompt_request",
            request_category="prompt_generation",
            response_frame="Prepare a Codex-ready artifact with scope, files, tests, and boundaries.",
            summary="I will treat this as artifact preparation, not an external send.",
            tool_route="codex_bounded_repo_prompt",
            follow_up_required=False,
        )
    if _contains_any(normalized, ("make a prompt for the next worker",)):
        return _Meaning(
            inferred_intent="codex_prompt_request",
            request_category="prompt_generation",
            response_frame="Prepare the next-worker prompt with exact scope and validation.",
            summary="This is prompt preparation. No Covenant needed unless the prompt asks for mutation.",
            tool_route="codex_bounded_repo_prompt",
            follow_up_required=False,
        )
    if _contains_any(normalized, ("ask gemini", "get a second opinion")):
        return _Meaning(
            inferred_intent="gemini_review_request",
            request_category="prompt_generation",
            response_frame="Prepare an architecture/scope/risk review prompt; model advice is not authority.",
            summary="This routes to review thinking, not repo mutation or approval.",
            tool_route="gemini_architecture_scope_review",
            follow_up_required=False,
        )
    if _contains_any(normalized, ("review this for commit", "is this ready to commit")):
        return _Meaning(
            inferred_intent="commit_review_request",
            request_category="review",
            response_frame="Review the diff and tests; return READY_TO_COMMIT or NOT_READY.",
            summary="This is commit-readiness review. No commit authority is implied.",
            tool_route="codex_diff_commit_readiness_review",
            follow_up_required=False,
        )
    if _contains_any(normalized, ("make a handoff", "prepare the next chat")):
        return _Meaning(
            inferred_intent="handoff_request",
            request_category="prompt_generation",
            response_frame="Draft a concise train-log handoff with validation and gates.",
            summary="This is handoff preparation. Writing it still needs scoped repo authority.",
            tool_route="operator_handoff_draft",
            follow_up_required=False,
        )
    if _contains_any(normalized, ("i can update the handoff",)):
        return _Meaning(
            inferred_intent="handoff_request",
            request_category="bounded_repo_mutation",
            response_frame="Convert the proposal into a bounded handoff-edit Covenant before writing.",
            summary="This changes repo docs. A bounded Covenant can be proposed before the hand moves.",
            tool_route="operator_handoff_draft",
            covenant_required=True,
            covenant_allowed_in_v0=True,
            suggested_authority_level=AuthorityLevel.BOUNDED_REPO_MUTATION.value,
            suggested_risk_level="medium",
            suggested_action="update the Packet 07 active handoff with a scoped train-log note",
            rollback_plan="discard the handoff diff or revert only the scoped handoff edit before commit",
            follow_up_required=True,
            yes_no_reframe=(
                "Approve a scoped handoff update with receipt evidence and rollback?"
            ),
        )
    if _contains_any(normalized, ("i recommend committing this", "commit this", "commit it")):
        return _Meaning(
            inferred_intent="commit_review_request",
            request_category="bounded_repo_mutation",
            response_frame="Require READY_TO_COMMIT evidence, exact scope, and rollback before local commit.",
            summary="This proposes a local repo mutation. It needs a Covenant; the phrase is not approval.",
            tool_route="codex_commit_mechanics",
            covenant_required=True,
            covenant_allowed_in_v0=True,
            suggested_authority_level=AuthorityLevel.BOUNDED_REPO_MUTATION.value,
            suggested_risk_level="medium",
            suggested_action="commit the reviewed scoped diff after READY_TO_COMMIT validation",
            rollback_plan="use a follow-up revert commit or stop before push if review fails",
            follow_up_required=True,
            yes_no_reframe=(
                "Approve committing the reviewed scoped diff after tests and READY_TO_COMMIT?"
            ),
        )
    if _contains_any(normalized, ("this is ready to push",)):
        return _Meaning(
            inferred_intent="push_confirmation_context",
            request_category="restricted",
            response_frame="Separate local readiness from remote mutation; push remains external authority.",
            summary="Ready-to-push language is not push authority. External/remote action is blocked in v0.",
            tool_route="operator_external_send_gate",
            covenant_required=True,
            covenant_allowed_in_v0=False,
            restricted_block=True,
            restricted_domains=("external sends",),
            follow_up_required=True,
            yes_no_reframe="Do you want a final local readiness brief before a separate push gate?",
        )
    return None


def _approval_meaning(normalized: str) -> _Meaning | None:
    if _contains_any(normalized, ("can we move forward",)):
        return _Meaning(
            inferred_intent="activation_readiness_question",
            request_category="approval_sensitive",
            response_frame="Answer readiness and blockers; create a Covenant only if the next move changes state.",
            summary="Likely readiness. I can name blockers and the next safe move; readiness is not approval.",
            tool_route="activation_readiness_review",
            covenant_required=False,
            follow_up_required=True,
            yes_no_reframe=(
                "Do you want a readiness brief, or a Covenant for one specific bounded action?"
            ),
        )
    if _contains_any(normalized, ("do the next thing",)):
        return _Meaning(
            inferred_intent="next_safe_action",
            request_category="approval_sensitive",
            response_frame="Propose the next safe action or draft a Covenant for a named bounded action.",
            summary="This is not executable by itself. I can frame the next move, but I cannot act from that phrase alone.",
            covenant_required=True,
            covenant_allowed_in_v0=False,
            follow_up_required=True,
            yes_no_reframe=(
                "Do you want the next safe action only, or a Covenant for a specific state-changing action?"
            ),
        )
    if _contains_any(
        normalized,
        (
            "go ahead",
            "do it",
            "handle it",
            "handle that",
            "take care of that",
            "make it happen",
            "proceed",
            "ship it",
        ),
    ):
        decision = can_operator_confirmation_approve(None, normalized)
        return _Meaning(
            inferred_intent="approval_required_action",
            request_category="approval_sensitive",
            response_frame="Look for a specific pending Covenant; without one, reframe as a yes/no decision.",
            summary=(
                "This asks for power. I do not see a pending Covenant in this v0 simulation, so I will not guess approval."
            ),
            tool_route="approval_gate_required",
            covenant_required=True,
            covenant_allowed_in_v0=False,
            follow_up_required=True,
            yes_no_reframe=(
                "Approve [specific action] with [evidence], [boundaries], [rollback], and [expiry]?"
            ),
        )
    if _contains_any(normalized, ("can i push",)):
        return _Meaning(
            inferred_intent="push_confirmation_context",
            request_category="restricted",
            response_frame="Give local readiness context; pushing is external/remote mutation and separately gated.",
            summary="I can brief push readiness, but I cannot authorize or perform the push in v0.",
            tool_route="operator_external_send_gate",
            covenant_required=True,
            covenant_allowed_in_v0=False,
            restricted_block=True,
            restricted_domains=("external sends",),
            follow_up_required=True,
            yes_no_reframe="Do you want a final local push-readiness checklist before a separate approval gate?",
        )
    return None


def _restricted_meaning(normalized: str) -> _Meaning | None:
    restricted_rules: tuple[tuple[tuple[str, ...], tuple[str, ...], str], ...] = (
        (("launch it", "activate it", "start the runtime"), ("live runtime launch",), "runtime activation"),
        (("write to mcp memory", "write mcp memory"), ("MCP writes/shared memory",), "MCP/shared-memory write"),
        (("call the provider", "call provider", "use the api", "use api"), ("provider/model/API calls",), "provider/API call"),
        (("send the invoice", "send invoice", "reconcile billing"), ("invoice generation/reconciliation/sending",), "invoice/billing action"),
        (("touch legal files", "read private root"), ("legal/private-root/sensitive-data access",), "legal/private-root action"),
        (("send the email", "send email"), ("external sends",), "external send"),
        (("delete the files", "delete files"), ("destructive filesystem operations",), "destructive filesystem action"),
        (("create packet 08",), ("Packet 08 creation",), "Packet 08 creation"),
    )
    for phrases, domains, label in restricted_rules:
        if _contains_any(normalized, phrases):
            substitute = _safe_substitute_for(domains)
            return _Meaning(
                inferred_intent="approval_required_action",
                request_category="restricted",
                response_frame=(
                    f"Block {label}; offer {substitute} instead of live action."
                ),
                summary=(
                    f"Blocked in v0: {label} is restricted. I can prepare {substitute}, not execute it."
                ),
                tool_route="approval_gate_required",
                covenant_required=True,
                covenant_allowed_in_v0=False,
                restricted_block=True,
                restricted_domains=domains,
                follow_up_required=True,
                yes_no_reframe=f"Do you want {substitute} for this restricted lane?",
            )
    return None


def _safe_substitute_for(domains: tuple[str, ...]) -> str:
    if "live runtime launch" in domains:
        return "a runtime dry-run readiness review"
    if "MCP writes/shared memory" in domains:
        return "an MCP shared-memory gate review"
    if "provider/model/API calls" in domains:
        return "a provider-call approval packet skeleton"
    if "invoice generation/reconciliation/sending" in domains:
        return "a draft-only billing evidence plan"
    if "legal/private-root/sensitive-data access" in domains:
        return "a metadata-only boundary review"
    if "external sends" in domains:
        return "a draft-only send checklist"
    if "destructive filesystem operations" in domains:
        return "a reversible cleanup proposal"
    if "Packet 08 creation" in domains:
        return "a Packet 08 blueprint review note"
    return "a static readiness review"


def _suggest_covenant(meaning: _Meaning) -> OperatorActionCovenant | None:
    if not meaning.covenant_allowed_in_v0 or meaning.restricted_block:
        return None
    if meaning.suggested_authority_level not in {
        AuthorityLevel.DRAFT_OR_PROPOSAL.value,
        AuthorityLevel.BOUNDED_REPO_MUTATION.value,
    }:
        return None
    return create_action_covenant(
        requested_action=meaning.suggested_action,
        risk_level=meaning.suggested_risk_level,
        authority_level=meaning.suggested_authority_level,
        evidence_basis=SIMULATOR_EVIDENCE,
        forbidden_boundaries_checked=NO_LIVE_AUTHORITY,
        rollback_plan=meaning.rollback_plan,
        expires_at=_FIXED_COVENANT_EXPIRY,
    )


def simulate_operator_extension_request(text: str) -> OperatorExtensionSimulation:
    """Simulate how OpenClaw should frame a request without taking action."""
    normalized = _normalize(text)
    source = _guess_input_source(normalized)
    intent = classify_operator_intent(text)
    intent_frame = frame_operator_intent(intent)
    meaning = _base_meaning(text, normalized)
    suggested = _suggest_covenant(meaning)
    decision_reasons: tuple[str, ...] = ()
    if meaning.covenant_required and suggested is None:
        decision_reasons = can_operator_confirmation_approve(None, text).reasons
    forbidden = tuple(dict.fromkeys(INTENT_CORE_FORBIDDEN_ACTIONS + NO_LIVE_AUTHORITY))

    return OperatorExtensionSimulation(
        original_text=text,
        input_source_guess=source,
        inferred_intent=meaning.inferred_intent,
        intent_core_intent=intent_frame.intent_name,
        request_category=meaning.request_category,
        recommended_response_frame=meaning.response_frame,
        execution_authority=False,
        covenant_required=meaning.covenant_required,
        covenant_allowed_in_v0=meaning.covenant_allowed_in_v0,
        suggested_covenant=suggested,
        restricted_block=meaning.restricted_block,
        restricted_domains=meaning.restricted_domains,
        forbidden_actions=forbidden,
        follow_up_required=meaning.follow_up_required,
        yes_no_reframe=meaning.yes_no_reframe,
        operator_facing_summary=meaning.summary,
        tool_route=meaning.tool_route,
        covenant_decision_reasons=decision_reasons,
    )


def simulate_operator_extension_requests(
    texts: Sequence[str],
) -> tuple[OperatorExtensionSimulation, ...]:
    """Simulate several requests in order without shared state."""
    return tuple(simulate_operator_extension_request(text) for text in texts)


def render_operator_extension_simulation(
    simulation: OperatorExtensionSimulation,
) -> str:
    """Render a compact operator-facing simulation receipt."""
    covenant_posture = "not_needed"
    if simulation.covenant_required:
        covenant_posture = (
            "allowed_in_v0" if simulation.covenant_allowed_in_v0 else "blocked_or_missing"
        )
    lines = [
        "OPERATOR EXTENSION SIMULATION",
        f"Input: {simulation.original_text}",
        f"Source guess: {simulation.input_source_guess}",
        f"Intent: {simulation.inferred_intent}",
        f"Category: {simulation.request_category}",
        f"Authority: execution_authority={simulation.execution_authority}",
        f"Covenant: required={simulation.covenant_required}, posture={covenant_posture}",
        f"Restricted: {simulation.restricted_block}",
    ]
    if simulation.yes_no_reframe:
        lines.append(f"Reframe: {simulation.yes_no_reframe}")
    if simulation.suggested_covenant is not None:
        lines.append(
            "Suggested Covenant: "
            f"{simulation.suggested_covenant.authority_level} / "
            f"{simulation.suggested_covenant.confirmation_phrase}"
        )
    lines.append(f"Summary: {simulation.operator_facing_summary}")
    return "\n".join(lines)


def simulation_phrase_matrix() -> tuple[tuple[str, str], ...]:
    """Return required simulator phrase coverage for receipts and tests."""
    return (
        ("where are we", "status_brief"),
        ("what needs my attention", "tired_tell_me_what_matters"),
        ("I'm tired, tell me what matters", "tired_tell_me_what_matters"),
        ("send that to Codex", "codex_prompt_request"),
        ("give this to the coder", "codex_prompt_request"),
        ("ask Gemini", "gemini_review_request"),
        ("get a second opinion", "gemini_review_request"),
        ("review this for commit", "commit_review_request"),
        ("I recommend committing this", "commit_review_request"),
        ("I can update the handoff", "handoff_request"),
        ("can I push", "push_confirmation_context"),
        ("do the next thing", "next_safe_action"),
        ("go ahead", "approval_required_action"),
        ("ship it", "approval_required_action"),
        ("launch it", "approval_required_action"),
        ("write to MCP memory", "approval_required_action"),
        ("send the invoice", "approval_required_action"),
        ("touch legal files", "approval_required_action"),
        ("delete the files", "approval_required_action"),
        ("create Packet 08", "approval_required_action"),
    )
