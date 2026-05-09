"""Natural-language Operator Question Response Path v0.

This module is the static, non-live connector between normal operator phrasing
and the existing Operator Harness primitives:

intent -> evidence -> covenant posture -> direct answer or worker handoff.

It is designed for future Cassandra/Chief user-facing surfaces, but it wires no
runtime listener, no Telegram, no provider/model calls, no MCP, no persistence,
no receipt execution, no filesystem reads, and no external sends.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Sequence

from operator_evidence_bridge import (
    RESTRICTED_BRIDGE_DOMAIN_IDS,
    OperatorEvidenceBridgeResult,
    bridge_operator_request,
)
from operator_intent_core import (
    OperatorIntentFrame,
    classify_and_frame_operator_intent,
)
from operator_prompt_handoff_generator import (
    EvidenceReference,
    OperatorPromptHandoff,
    generate_operator_prompt_handoff,
)


RESPONSE_MODES = (
    "direct_answer",
    "worker_handoff",
    "blocked_boundary",
    "needs_evidence",
)

QUESTION_RESPONSE_STATUSES = (
    "answered_non_authorizing",
    "worker_handoff_ready",
    "needs_evidence_for_worker_handoff",
    "blocked_covenant_required",
)

DIRECT_ANSWER_INTENTS = (
    "status_brief",
    "next_safe_action",
    "tired_tell_me_what_matters",
    "activation_readiness_question",
    "stop_or_wait_instruction",
)

HANDOFF_INTENTS = (
    "codex_prompt_request",
    "gemini_review_request",
    "commit_review_request",
    "handoff_request",
)

DEFAULT_FOLLOW_UP_OPTIONS = (
    "Give me the short status.",
    "Name the next safe move.",
    "Generate a bounded worker handoff.",
    "Frame the missing Covenant before power.",
)

NO_EXECUTION_AUTHORITY_STATEMENT = "This response grants no execution authority."

RECEIPT_NON_EXECUTION_STATEMENT = (
    "Evidence and receipts ground the answer; they are not approval."
)

COVENANT_POWER_STATEMENT = (
    "An Operator Action Covenant is required before authority-bearing action."
)

FORBIDDEN_RESPONSE_PATH_CROSSINGS = (
    "live runtime launch",
    "assistant daemon/listener wiring",
    "Telegram or external-send wiring",
    "provider/model/API call",
    "MCP call or hidden/shared-memory write",
    "process/service scan",
    "systemd/launchctl/service mutation",
    "SQLite/database persistence",
    "embeddings",
    "private-root/legal/invoice/finance/secrets access",
    "Mac Watch source-file mutation",
    "commit, push, or destructive operation",
)


@dataclass(frozen=True)
class OperatorQuestionResponse:
    original_text: str
    status: str
    response_mode: str
    classified_intent: str
    bridge_domain: str
    request_category: str
    covenant_posture: str
    human_response: str
    evidence_surfaces: tuple[str, ...]
    forbidden_lanes: tuple[str, ...]
    follow_up_options: tuple[str, ...]
    no_execution_authority_statement: str
    receipt_non_execution_statement: str
    worker_handoff: OperatorPromptHandoff | None = None
    execution_authority_granted: bool = False
    receipts_executed: bool = False
    provider_or_model_called: bool = False
    runtime_launched: bool = False
    process_state_inspected: bool = False
    mcp_called: bool = False
    hidden_memory_write_used: bool = False
    persistence_used: bool = False
    external_send_used: bool = False


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _has_evidence(
    *,
    evidence_packet: Mapping[str, object] | None,
    evidence_references: Sequence[EvidenceReference | Mapping[str, object] | str] | None,
) -> bool:
    if evidence_references:
        return True
    if not evidence_packet:
        return False
    files = evidence_packet.get("files", ())
    return isinstance(files, Sequence) and not isinstance(files, (str, bytes)) and bool(files)


def _profile_for_bridge_domain(bridge_domain: str) -> str:
    if bridge_domain == "codex_coder_routing":
        return "codex_implementation"
    if bridge_domain == "gemini_planning_architecture_routing":
        return "gemini_planning"
    if bridge_domain == "commit_push_remote_mutation":
        return "codex_review"
    return "gemini_planning"


def _restricted(bridge: OperatorEvidenceBridgeResult) -> bool:
    return bridge.restricted_block or bridge.bridge_domain in RESTRICTED_BRIDGE_DOMAIN_IDS


def _domain_from_safe_frame(
    frame: OperatorIntentFrame,
) -> tuple[str, str, tuple[str, ...]]:
    if frame.intent_name == "tired_tell_me_what_matters":
        return (
            "operator_relief",
            "not_required_read_only_status",
            frame.evidence_surfaces,
        )
    if frame.intent_name in {"status_brief", "next_safe_action"}:
        return (
            "status_orientation",
            "not_required_read_only_status",
            frame.evidence_surfaces,
        )
    if frame.intent_name == "activation_readiness_question":
        return (
            "forward_motion_readiness",
            "readiness_only_not_approval",
            frame.evidence_surfaces,
        )
    if frame.intent_name == "stop_or_wait_instruction":
        return (
            "stop_wait_hold",
            "not_required_stop",
            frame.evidence_surfaces,
        )
    if frame.intent_name == "codex_prompt_request":
        return (
            "codex_coder_routing",
            "not_required_draft_or_review",
            frame.evidence_surfaces,
        )
    if frame.intent_name == "gemini_review_request":
        return (
            "gemini_planning_architecture_routing",
            "not_required_draft_or_review",
            frame.evidence_surfaces,
        )
    if frame.intent_name == "handoff_request":
        return (
            "handoff_packet_continuity",
            "draft_only_or_scoped_mutation_required",
            frame.evidence_surfaces,
        )
    if frame.intent_name == "commit_review_request":
        return (
            "commit_push_remote_mutation",
            "not_required_review_only",
            frame.evidence_surfaces,
        )
    return (
        "unsafe_ambiguous_handle_it",
        "clarification_required",
        frame.evidence_surfaces,
    )


def _resolved_frame_and_bridge(
    operator_text: str,
) -> tuple[OperatorIntentFrame, OperatorEvidenceBridgeResult, str, str, tuple[str, ...]]:
    frame = classify_and_frame_operator_intent(operator_text)
    bridge = bridge_operator_request(operator_text)

    if (
        bridge.restricted_block is False
        and bridge.bridge_domain == "unsafe_ambiguous_handle_it"
        and frame.intent_name != "unsafe_or_ambiguous_action"
        and frame.request_category in {"read_only_status", "prompt_generation", "review", "stop"}
    ):
        bridge_domain, covenant_posture, evidence = _domain_from_safe_frame(frame)
        return frame, bridge, bridge_domain, covenant_posture, _dedupe(evidence)

    return (
        frame,
        bridge,
        bridge.bridge_domain,
        bridge.covenant_posture,
        _dedupe(bridge.approved_evidence_surfaces),
    )


def _should_generate_handoff(
    *,
    frame: OperatorIntentFrame,
    bridge_domain: str,
    generate_worker_handoff: bool,
    target_worker_profile: str | None,
) -> bool:
    if generate_worker_handoff or target_worker_profile:
        return True
    if frame.intent_name in HANDOFF_INTENTS:
        return True
    return bridge_domain in {
        "codex_coder_routing",
        "gemini_planning_architecture_routing",
        "handoff_packet_continuity",
    }


def _status_and_mode(
    *,
    restricted: bool,
    wants_handoff: bool,
    has_evidence: bool,
) -> tuple[str, str]:
    if restricted:
        return "blocked_covenant_required", "blocked_boundary"
    if wants_handoff and not has_evidence:
        return "needs_evidence_for_worker_handoff", "needs_evidence"
    if wants_handoff:
        return "worker_handoff_ready", "worker_handoff"
    return "answered_non_authorizing", "direct_answer"


def _format_evidence(evidence_surfaces: Sequence[str]) -> str:
    if not evidence_surfaces:
        return "no evidence surfaces selected yet"
    return "; ".join(evidence_surfaces[:4])


def _human_response(
    *,
    operator_text: str,
    status: str,
    response_mode: str,
    frame: OperatorIntentFrame,
    bridge: OperatorEvidenceBridgeResult,
    bridge_domain: str,
    covenant_posture: str,
    evidence_surfaces: Sequence[str],
) -> str:
    evidence = _format_evidence(evidence_surfaces)

    if status == "blocked_covenant_required":
        return (
            "I can’t do that from natural language alone. "
            f"This touches `{bridge_domain}` and remains blocked/non-authorizing. "
            f"Safe next move: {bridge.safe_substitute_or_next_move}. "
            f"Covenant posture: {covenant_posture}. "
            f"{COVENANT_POWER_STATEMENT}"
        )

    if status == "needs_evidence_for_worker_handoff":
        return (
            "I can prepare that worker handoff, but I need grounding evidence first. "
            f"Intent: {frame.intent_name}. Evidence to supply or verify: {evidence}. "
            f"{NO_EXECUTION_AUTHORITY_STATEMENT}"
        )

    if response_mode == "worker_handoff":
        return (
            "I prepared a bounded, non-authorizing worker handoff. "
            f"Intent: {frame.intent_name}. Domain: {bridge_domain}. "
            f"Covenant posture: {covenant_posture}. "
            f"{NO_EXECUTION_AUTHORITY_STATEMENT}"
        )

    if frame.intent_name == "tired_tell_me_what_matters":
        return (
            "Cut the noise: this is a read-only orientation request. "
            f"Use evidence: {evidence}. "
            "What matters: state, risk, next safe move, and hard gates. "
            f"Covenant posture: {covenant_posture}. "
            f"{NO_EXECUTION_AUTHORITY_STATEMENT}"
        )

    if frame.intent_name == "next_safe_action":
        return (
            "You’re asking for the next safe move. "
            "Current posture: read-only and non-authorizing. "
            f"Use evidence: {evidence}. "
            "Next safe move: review the current Operator Harness state, name one "
            "small stabilization slice, and stop before mutation, runtime, provider, "
            "MCP, private-root, external-send, commit, or push gates. "
            f"Covenant posture: {covenant_posture}."
        )

    if frame.intent_name == "status_brief":
        return (
            "You’re asking for status. "
            f"Use evidence: {evidence}. "
            "Answer with repo/packet posture, changed surface, validation posture, "
            "next visible lane, and blocked gates. "
            f"Covenant posture: {covenant_posture}."
        )

    if frame.intent_name == "activation_readiness_question":
        return (
            "You’re asking about readiness, not granting approval. "
            f"Use evidence: {evidence}. "
            "Separate dry-run readiness from authority to act, then name the next gate. "
            f"Covenant posture: {covenant_posture}."
        )

    if frame.intent_name == "stop_or_wait_instruction":
        return (
            "Stopping optional forward motion. Preserve state and report the last "
            "safe point plus the pending next step. No Covenant is needed to stop."
        )

    return (
        f"I understand this as `{frame.intent_name}`. "
        f"Recommended frame: {frame.recommended_response_frame} "
        f"Evidence: {evidence}. Covenant posture: {covenant_posture}. "
        f"{NO_EXECUTION_AUTHORITY_STATEMENT}"
    )


def respond_to_operator_question(
    operator_text: str,
    *,
    target_worker_profile: str | None = None,
    generate_worker_handoff: bool = False,
    evidence_packet: Mapping[str, object] | None = None,
    evidence_references: Sequence[EvidenceReference | Mapping[str, object] | str] | None = None,
    likely_files_to_change: Sequence[str] | None = None,
    validation_commands: Sequence[str] | None = None,
) -> OperatorQuestionResponse:
    """Return a concise, non-authorizing answer path for natural language.

    This is a pure local planner/formatter. It does not execute receipts,
    inspect runtime/process state, call providers, call MCP, read files, persist
    state, mutate files, or send anything.
    """
    text = str(operator_text or "").strip()
    frame, bridge, bridge_domain, covenant_posture, evidence_surfaces = (
        _resolved_frame_and_bridge(text)
    )
    is_restricted = _restricted(bridge) or bridge_domain in RESTRICTED_BRIDGE_DOMAIN_IDS
    wants_handoff = _should_generate_handoff(
        frame=frame,
        bridge_domain=bridge_domain,
        generate_worker_handoff=generate_worker_handoff,
        target_worker_profile=target_worker_profile,
    )
    evidence_available = _has_evidence(
        evidence_packet=evidence_packet,
        evidence_references=evidence_references,
    )
    status, response_mode = _status_and_mode(
        restricted=is_restricted,
        wants_handoff=wants_handoff,
        has_evidence=evidence_available,
    )

    worker_handoff: OperatorPromptHandoff | None = None
    if response_mode == "worker_handoff":
        profile = target_worker_profile or _profile_for_bridge_domain(bridge_domain)
        worker_handoff = generate_operator_prompt_handoff(
            target_worker_profile=profile,
            operator_text=text,
            evidence_packet=evidence_packet,
            evidence_references=evidence_references,
            likely_files_to_change=likely_files_to_change,
            validation_commands=validation_commands,
        )

    human = _human_response(
        operator_text=text,
        status=status,
        response_mode=response_mode,
        frame=frame,
        bridge=bridge,
        bridge_domain=bridge_domain,
        covenant_posture=covenant_posture,
        evidence_surfaces=evidence_surfaces,
    )

    return OperatorQuestionResponse(
        original_text=text,
        status=status,
        response_mode=response_mode,
        classified_intent=frame.intent_name,
        bridge_domain=bridge_domain,
        request_category=frame.request_category,
        covenant_posture=covenant_posture,
        human_response=human,
        evidence_surfaces=evidence_surfaces,
        forbidden_lanes=_dedupe(FORBIDDEN_RESPONSE_PATH_CROSSINGS),
        follow_up_options=DEFAULT_FOLLOW_UP_OPTIONS,
        no_execution_authority_statement=NO_EXECUTION_AUTHORITY_STATEMENT,
        receipt_non_execution_statement=RECEIPT_NON_EXECUTION_STATEMENT,
        worker_handoff=worker_handoff,
    )


def question_response_to_dict(response: OperatorQuestionResponse) -> dict[str, object]:
    """Return a plain deterministic dictionary for tests, receipts, or JSON."""
    return asdict(response)


def operator_question_response_status() -> dict[str, object]:
    """Return static proof that this response path is non-live and non-executing."""
    checks = {
        "statuses_present": QUESTION_RESPONSE_STATUSES
        == (
            "answered_non_authorizing",
            "worker_handoff_ready",
            "needs_evidence_for_worker_handoff",
            "blocked_covenant_required",
        ),
        "response_modes_present": RESPONSE_MODES
        == (
            "direct_answer",
            "worker_handoff",
            "blocked_boundary",
            "needs_evidence",
        ),
        "normal_language_direct_intents_present": all(
            intent in DIRECT_ANSWER_INTENTS
            for intent in (
                "status_brief",
                "next_safe_action",
                "tired_tell_me_what_matters",
            )
        ),
        "handoff_intents_present": all(
            intent in HANDOFF_INTENTS
            for intent in (
                "codex_prompt_request",
                "gemini_review_request",
                "handoff_request",
            )
        ),
        "forbidden_crossings_named": all(
            phrase in " ".join(FORBIDDEN_RESPONSE_PATH_CROSSINGS)
            for phrase in (
                "live runtime launch",
                "provider/model/API call",
                "MCP call",
                "private-root",
                "external-send",
            )
        ),
        "authority_statement_non_authorizing": (
            "grants no execution authority" in NO_EXECUTION_AUTHORITY_STATEMENT
        ),
        "receipts_not_approval": "not approval" in RECEIPT_NON_EXECUTION_STATEMENT,
    }
    return {
        "receipt_type": "openclaw.operator_question_response_status",
        "mode": "read-only/static-natural-language-response-path/no-execution",
        "authority_note": (
            "Normal operator language can be classified and answered, but this "
            "path grants no execution authority and wires no live surfaces."
        ),
        "execution_authority_granted": False,
        "receipts_executed": False,
        "provider_or_model_called": False,
        "runtime_launched": False,
        "process_state_inspected": False,
        "mcp_called": False,
        "hidden_memory_write_used": False,
        "persistence_used": False,
        "external_send_used": False,
        "statuses": QUESTION_RESPONSE_STATUSES,
        "response_modes": RESPONSE_MODES,
        "checks": checks,
        "passed": all(checks.values()),
    }
