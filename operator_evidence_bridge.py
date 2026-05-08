"""Operator Evidence Bridge v0.

This module connects natural language, Operator Intent Core, approved evidence
surface selection, simulator posture, and Action Covenant posture into one
deterministic response frame. Evidence is selected by name only. The bridge does
not read files, run receipts, call providers, call MCP, persist state, or execute
actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from operator_action_covenant import (
    OperatorActionCovenant,
    can_operator_confirmation_approve,
)
from operator_extension_simulator import (
    OperatorExtensionSimulation,
    simulate_operator_extension_request,
)
from operator_intent_core import classify_operator_intent, frame_operator_intent


USES_OPERATOR_INTENT_CORE = True
USES_OPERATOR_ACTION_COVENANT = True
USES_OPERATOR_EXTENSION_SIMULATOR = True
EVIDENCE_SURFACES_ARE_NAMES_ONLY = True
BRIDGE_NEVER_EXECUTES = True

REQUIRED_BRIDGE_DOMAIN_IDS = (
    "status_orientation",
    "operator_relief",
    "forward_motion_readiness",
    "codex_coder_routing",
    "gemini_planning_architecture_routing",
    "commit_push_remote_mutation",
    "handoff_packet_continuity",
    "approval_action_covenant_power_boundary",
    "runtime_activation_launch",
    "mcp_shared_memory_hidden_authority",
    "invoice_billing_money",
    "legal_private_sensitive",
    "external_sends_communications",
    "destructive_filesystem_broad_traversal",
    "taste_product_feel_beauty",
    "packet_renewal_next_packet",
    "stop_wait_hold",
    "unsafe_ambiguous_handle_it",
    "do_next_continue_keep_going",
)

EXTRA_RESTRICTED_DOMAIN_IDS = (
    "provider_model_api_calls",
)

RESTRICTED_BRIDGE_DOMAIN_IDS = (
    "runtime_activation_launch",
    "mcp_shared_memory_hidden_authority",
    "provider_model_api_calls",
    "invoice_billing_money",
    "legal_private_sensitive",
    "external_sends_communications",
    "destructive_filesystem_broad_traversal",
    "packet_renewal_next_packet",
)

FORBIDDEN_BOUNDARIES = (
    "live runtime launch",
    "process/service scan",
    "service/systemd/launchctl mutation",
    "provider/model/API call",
    "MCP call or write",
    "hidden memory write",
    "invoice generation/reconciliation/sending",
    "legal/private-root/sensitive-data access",
    "external send",
    "destructive filesystem operation",
    "Packet 08 creation",
    "commit or push without separate gate",
)

STATUS_EVIDENCE = (
    "repo-check",
    "packet-status",
    "operator-harness-status",
    "active_handoff",
    "git status/log evidence",
)

RELIEF_EVIDENCE = (
    "operator-harness-status",
    "active_handoff",
    "repo-check",
    "gated-activation-status",
    "runtime-dry-run-readiness",
)

READINESS_EVIDENCE = (
    "packet-status",
    "active_handoff",
    "gated-activation-status",
    "runtime-dry-run-readiness",
    "activation-evidence-status",
    "operator-action-covenant-status",
)

CODEX_EVIDENCE = (
    "Packet 07 File 14",
    "Packet 07 File 06",
    "active_handoff",
    "repo-check",
    "git status/log/diff checks",
    "targeted test receipts",
)

GEMINI_EVIDENCE = (
    "Packet 07 File 14",
    "Packet 07 File 01",
    "Packet 07 File 05",
    "Packet 07 File 24",
    "active_handoff",
    "source rails",
)

COMMIT_PUSH_EVIDENCE = (
    "git status/log/diff checks",
    "targeted test receipts",
    "repo-check",
    "active_handoff",
    "operator-action-covenant-status",
)

HANDOFF_EVIDENCE = (
    "active_handoff",
    "Packet 07 README",
    "recent commits",
    "Packet 07 File 01",
    "Packet 07 File 24",
)

APPROVAL_EVIDENCE = (
    "operator-action-covenant-status",
    "operator-intent-core-status",
    "operator-extension-simulator-status",
    "activation-evidence-status",
)

RUNTIME_EVIDENCE = (
    "runtime-dry-run-readiness",
    "activation-evidence-status",
    "gated-activation-status",
    "Packet 07 File 19",
    "Packet 07 File 20",
    "Packet 07 File 21",
)

MCP_EVIDENCE = (
    "mcp-shared-memory-gate-status",
    "Packet 07 File 22",
)

PROVIDER_EVIDENCE = (
    "operator-action-covenant-status",
    "Packet 07 File 14",
    "gated-activation-status",
)

INVOICE_EVIDENCE = (
    "Packet 07 File 17",
    "operator-action-covenant-status",
    "sensitive-root-contract",
)

LEGAL_EVIDENCE = (
    "Packet 07 File 16",
    "sensitive-root-contract",
    "operator-action-covenant-status",
)

EXTERNAL_SEND_EVIDENCE = (
    "operator-action-covenant-status",
    "Packet 07 File 17",
    "Packet 07 File 06",
)

DESTRUCTIVE_EVIDENCE = (
    "Packet 07 File 10",
    "Packet 07 File 23",
    "operator-action-covenant-status",
)

TASTE_EVIDENCE = (
    "OPERATOR_EXTENSION_MANIFESTO.md",
    "Packet 07 File 05",
    "Packet 07 File 06",
)

PACKET_RENEWAL_EVIDENCE = (
    "Packet 07 File 01",
    "Packet 07 File 24",
    "active_handoff",
    "completed mile markers",
    "receipt coverage",
)

STOP_EVIDENCE = (
    "current task state",
    "active_handoff",
)

AMBIGUOUS_EVIDENCE = (
    "Packet 07 File 01",
    "active_handoff",
    "operator-intent-core-status",
    "operator-extension-simulator-status",
)

DO_NEXT_EVIDENCE = (
    "Packet 07 File 01",
    "active_handoff",
    "operator-harness-status",
    "relevant lane receipts",
)


@dataclass(frozen=True)
class OperatorEvidenceBridgeResult:
    original_text: str
    inferred_intent: str
    intent_core_intent: str
    simulator_intent: str
    bridge_domain: str
    request_category: str
    machine_contract_labels: tuple[str, ...]
    approved_evidence_surfaces: tuple[str, ...]
    response_frame: str
    covenant_posture: str
    forbidden_boundaries: tuple[str, ...]
    safe_substitute_or_next_move: str
    restricted_block: bool
    follow_up_required: bool
    operator_facing_summary: str
    yes_no_reframe: str = ""
    evidence_selection_mode: str = "names_only"
    execution_authority_granted: bool = False
    receipts_executed: bool = False
    shell_commands_executed: bool = False
    runtime_or_external_action_used: bool = False


@dataclass(frozen=True)
class _BridgeMeaning:
    inferred_intent: str
    bridge_domain: str
    request_category: str
    labels: tuple[str, ...]
    evidence: tuple[str, ...]
    response_frame: str
    covenant_posture: str
    next_move: str
    summary: str
    restricted_block: bool = False
    follow_up_required: bool = False
    yes_no_reframe: str = ""
    forbidden_boundaries: tuple[str, ...] = FORBIDDEN_BOUNDARIES


def _normalize(text: str) -> str:
    lowered = text.lower().strip()
    lowered = lowered.replace("\u2019", "'").replace("\u2018", "'")
    lowered = lowered.replace("\u201c", '"').replace("\u201d", '"')
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


def _names_only(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _approval_reframe(action: str = "specific action") -> str:
    return (
        f"Approve [{action}] with [evidence], [boundaries checked], "
        "[rollback], and [expiry]?"
    )


def _restricted_meaning(normalized: str) -> _BridgeMeaning | None:
    restricted_rules: tuple[
        tuple[tuple[str, ...], str, tuple[str, ...], tuple[str, ...], str, str],
        ...
    ] = (
        (
            ("launch it", "activate it", "start the runtime", "launch runtime"),
            "runtime_activation_launch",
            RUNTIME_EVIDENCE,
            ("restricted", "runtime", "readiness_not_authority"),
            "No live launch or process/service mutation. Use dry-run readiness evidence only.",
            "a runtime dry-run readiness review",
        ),
        (
            ("write to mcp memory", "write mcp memory", "make this canonical"),
            "mcp_shared_memory_hidden_authority",
            MCP_EVIDENCE,
            ("restricted", "mcp", "hidden_authority_blocked"),
            "No MCP write, shared-memory write, or hidden canonical memory. Use the MCP gate.",
            "an MCP shared-memory gate review",
        ),
        (
            ("call the provider", "call provider", "use the api", "use api"),
            "provider_model_api_calls",
            PROVIDER_EVIDENCE,
            ("restricted", "provider_api", "model_advice_not_authority"),
            "No provider/model/API call. Use a provider-call approval packet skeleton.",
            "a provider-call approval packet skeleton",
        ),
        (
            ("send the invoice", "send invoice", "reconcile billing", "check receivables"),
            "invoice_billing_money",
            INVOICE_EVIDENCE,
            ("restricted", "money", "draft_only"),
            "No invoice generation, reconciliation, sending, collection, or finance-root access.",
            "a draft-only billing evidence outline",
        ),
        (
            ("touch legal files", "read private root", "private root", "legal files"),
            "legal_private_sensitive",
            LEGAL_EVIDENCE,
            ("restricted", "sensitive", "metadata_only"),
            "No legal/private-root/sensitive-data access. Use sanitized boundary review only.",
            "a metadata-only boundary review",
        ),
        (
            ("send the email", "send email", "notify them", "message them"),
            "external_sends_communications",
            EXTERNAL_SEND_EVIDENCE,
            ("restricted", "external_send", "draft_only"),
            "No external send. Use draft-only communication framing.",
            "a draft-only send checklist",
        ),
        (
            ("delete the files", "delete files", "delete it", "scan the whole drive"),
            "destructive_filesystem_broad_traversal",
            DESTRUCTIVE_EVIDENCE,
            ("restricted", "filesystem", "broad_traversal_blocked"),
            "No delete, destructive filesystem action, broad crawl, or private traversal.",
            "a scoped dry-run cleanup plan",
        ),
        (
            ("create packet 08", "make packet 08", "should we make packet 08"),
            "packet_renewal_next_packet",
            PACKET_RENEWAL_EVIDENCE,
            ("restricted", "packet_renewal", "blueprint_before_mutation"),
            "No Packet 08 creation. Use Packet 07 renewal evidence and blueprint review first.",
            "a Packet 08 blueprint review without creating Packet 08",
        ),
    )
    for phrases, domain, evidence, labels, frame, substitute in restricted_rules:
        if _contains_any(normalized, phrases):
            return _BridgeMeaning(
                inferred_intent="approval_required_action",
                bridge_domain=domain,
                request_category="restricted",
                labels=labels,
                evidence=evidence,
                response_frame=frame,
                covenant_posture="restricted_not_approvable_in_v0",
                next_move=substitute,
                summary=f"Blocked in v0: {frame} I can prepare {substitute}.",
                restricted_block=True,
                follow_up_required=True,
                yes_no_reframe=f"Do you want {substitute}?",
            )
    return None


def _non_restricted_meaning(normalized: str) -> _BridgeMeaning | None:
    if _contains_any(normalized, ("stop", "wait", "hold", "pause", "do not continue")):
        return _BridgeMeaning(
            inferred_intent="stop_or_wait_instruction",
            bridge_domain="stop_wait_hold",
            request_category="stop",
            labels=("stop", "preserve_state", "non_authorizing"),
            evidence=STOP_EVIDENCE,
            response_frame="Preserve state, stop optional forward motion, and report the last safe state.",
            covenant_posture="not_required_stop",
            next_move="hold position and report the last safe state",
            summary="Holding. No Covenant needed to stop; prior momentum is not authority.",
        )
    if _contains_any(normalized, ("i'm tired tell me what matters", "im tired tell me what matters", "tell me what matters", "what needs my attention", "cut the noise")):
        return _BridgeMeaning(
            inferred_intent="tired_tell_me_what_matters",
            bridge_domain="operator_relief",
            request_category="read_only_status",
            labels=("attention_protection", "read_only", "north_star"),
            evidence=RELIEF_EVIDENCE,
            response_frame="Give state, risk, next safe move, and hard gates only.",
            covenant_posture="not_required_read_only_status",
            next_move="summarize what matters and name one safe next move",
            summary="Cut the noise: state, risk, next safe move, hard gates. No Covenant needed.",
        )
    if _contains_any(normalized, ("where are we", "what changed", "what did we just push", "status", "are we good")):
        return _BridgeMeaning(
            inferred_intent="status_brief",
            bridge_domain="status_orientation",
            request_category="read_only_status",
            labels=("orientation", "read_only", "evidence_grounded"),
            evidence=STATUS_EVIDENCE,
            response_frame="Give a compact state brief grounded in approved local evidence names.",
            covenant_posture="not_required_read_only_status",
            next_move="brief repo, packet, handoff, validation posture, and blocked gates",
            summary="This is read-only orientation. No Covenant needed; evidence grounds the answer.",
        )
    if _contains_any(normalized, ("can we move forward", "is the road clear", "what's next", "whats next", "what should i do", "are we blocked")):
        return _BridgeMeaning(
            inferred_intent="activation_readiness_question",
            bridge_domain="forward_motion_readiness",
            request_category="read_only_status",
            labels=("readiness", "readiness_not_approval", "next_safe_action"),
            evidence=READINESS_EVIDENCE,
            response_frame="Separate read-only readiness from authority to act.",
            covenant_posture="readiness_only_not_approval",
            next_move="answer blockers and name the next safe non-mutating move",
            summary="I can answer readiness and blockers. Moving evidence is not moving power.",
            follow_up_required=True,
            yes_no_reframe="Do you want a readiness brief or a Covenant for one named action?",
        )
    if _contains_any(normalized, ("send that to codex", "give this to the coder", "make a prompt for the next worker")):
        return _BridgeMeaning(
            inferred_intent="codex_prompt_request",
            bridge_domain="codex_coder_routing",
            request_category="prompt_generation",
            labels=("codex", "bounded_implementation", "draft_only"),
            evidence=CODEX_EVIDENCE,
            response_frame="Frame Codex for bounded implementation, review, tests, and no broad authority.",
            covenant_posture="not_required_draft_or_review",
            next_move="prepare a bounded implementation artifact without external sending",
            summary="This becomes a Codex-ready artifact, not a send or mutation by itself.",
        )
    if _contains_any(normalized, ("ask gemini", "get a second opinion", "gemini review")):
        return _BridgeMeaning(
            inferred_intent="gemini_review_request",
            bridge_domain="gemini_planning_architecture_routing",
            request_category="prompt_generation",
            labels=("gemini", "architecture_review", "model_advice_not_authority"),
            evidence=GEMINI_EVIDENCE,
            response_frame="Frame Gemini for architecture/risk review and synthesis, not mutation authority.",
            covenant_posture="not_required_draft_or_review",
            next_move="prepare an architecture/risk review prompt; do not call a provider in v0",
            summary="This routes to review thinking. Model output can advise, not crown action.",
        )
    if _contains_any(normalized, ("review this for commit", "is this ready to commit", "commit readiness")):
        return _BridgeMeaning(
            inferred_intent="commit_review_request",
            bridge_domain="commit_push_remote_mutation",
            request_category="review",
            labels=("commit_review", "repo_mutation_sensitive", "review_only"),
            evidence=COMMIT_PUSH_EVIDENCE,
            response_frame="Review diff, tests, and boundaries; do not commit from this question.",
            covenant_posture="not_required_review_only",
            next_move="return READY_TO_COMMIT or NOT_READY with evidence",
            summary="Commit readiness is review. A commit still needs its separate instruction and gate.",
        )
    if _contains_any(normalized, ("i recommend committing this", "commit this", "commit it")):
        return _BridgeMeaning(
            inferred_intent="commit_review_request",
            bridge_domain="commit_push_remote_mutation",
            request_category="approval_sensitive",
            labels=("local_repo_mutation", "covenant_required", "no_push"),
            evidence=COMMIT_PUSH_EVIDENCE,
            response_frame="Treat commit as bounded repo mutation requiring exact scope and review evidence.",
            covenant_posture="bounded_repo_mutation_covenant_required",
            next_move="create a Covenant for the scoped commit only after READY_TO_COMMIT",
            summary="This proposes repo mutation. It can be framed, but not approved by suggestion alone.",
            follow_up_required=True,
            yes_no_reframe="Approve committing the reviewed scoped diff after tests and READY_TO_COMMIT?",
        )
    if _contains_any(normalized, ("can i push", "push it", "this is ready to push")):
        return _BridgeMeaning(
            inferred_intent="push_confirmation_context",
            bridge_domain="commit_push_remote_mutation",
            request_category="restricted",
            labels=("push", "external_remote_mutation", "separate_gate_required"),
            evidence=COMMIT_PUSH_EVIDENCE,
            response_frame="Give local push-readiness context; no automatic push or remote mutation.",
            covenant_posture="restricted_not_approvable_in_v0",
            next_move="prepare a final local readiness checklist before a separate push gate",
            summary="Push is external/remote mutation. I can brief readiness; no automatic push in v0.",
            restricted_block=True,
            follow_up_required=True,
            yes_no_reframe="Do you want a final local push-readiness checklist?",
            forbidden_boundaries=FORBIDDEN_BOUNDARIES + ("external sends",),
        )
    if _contains_any(normalized, ("make a handoff", "prepare the next chat", "don't let the next worker rediscover this", "dont let the next worker rediscover this")):
        return _BridgeMeaning(
            inferred_intent="handoff_request",
            bridge_domain="handoff_packet_continuity",
            request_category="prompt_generation",
            labels=("handoff", "train_log", "continuity"),
            evidence=HANDOFF_EVIDENCE,
            response_frame="Draft/update train-log continuity without making handoff roadmap authority.",
            covenant_posture="draft_only_or_scoped_mutation_required",
            next_move="prepare a concise handoff note; writing it needs scoped repo authority",
            summary="Handoff reduces rediscovery. File 01 stays roadmap authority.",
            follow_up_required=True,
        )
    if _contains_any(normalized, ("go ahead", "do it", "proceed", "ship it", "approve this")):
        return _BridgeMeaning(
            inferred_intent="approval_required_action",
            bridge_domain="approval_action_covenant_power_boundary",
            request_category="approval_sensitive",
            labels=("approval", "covenant_required", "natural_language_not_authority"),
            evidence=APPROVAL_EVIDENCE,
            response_frame="Find a specific pending Covenant; otherwise reframe into an exact yes/no decision.",
            covenant_posture="pending_covenant_required",
            next_move="name the action, evidence, boundaries, rollback, and expiry before approval",
            summary="This asks for power. I will not guess approval without a valid Covenant.",
            follow_up_required=True,
            yes_no_reframe=_approval_reframe(),
        )
    if _contains_any(normalized, ("do the next thing", "continue", "keep going")):
        return _BridgeMeaning(
            inferred_intent="next_safe_action",
            bridge_domain="do_next_continue_keep_going",
            request_category="approval_sensitive",
            labels=("next_safe_action", "proposal_only", "not_execution_authority"),
            evidence=DO_NEXT_EVIDENCE,
            response_frame="Infer the likely next safe lane, then propose before state changes.",
            covenant_posture="proposal_only_until_specific_action",
            next_move="offer the smallest safe next action or draft a Covenant for a named action",
            summary="'Do the next thing' is not execution authority. I can frame the next move.",
            follow_up_required=True,
            yes_no_reframe="Do you want the next safe action only, or a Covenant for one named action?",
        )
    if _contains_any(normalized, ("just handle it", "handle it", "handle that", "take care of that", "make it happen")):
        return _BridgeMeaning(
            inferred_intent="unsafe_or_ambiguous_action",
            bridge_domain="unsafe_ambiguous_handle_it",
            request_category="unsafe_or_ambiguous",
            labels=("ambiguous", "narrow_scope", "no_hidden_authority"),
            evidence=AMBIGUOUS_EVIDENCE,
            response_frame="Narrow ambiguity into the smallest safe next move before any action.",
            covenant_posture="clarification_required",
            next_move="smallest safe next move: ask what exact action and boundary apply",
            summary="That is too wide to become power. I can narrow it, not execute it.",
            follow_up_required=True,
            yes_no_reframe="Do you want a status brief, a prompt draft, or a Covenant for a specific action?",
        )
    if _contains_any(normalized, ("make it sexy", "where is the taste", "corporate sludge", "make it beautiful")):
        return _BridgeMeaning(
            inferred_intent="taste_product_feel_review",
            bridge_domain="taste_product_feel_beauty",
            request_category="review",
            labels=("taste", "operator_experience", "north_star"),
            evidence=TASTE_EVIDENCE,
            response_frame="Review product feel, naming, and operator experience without weakening gates.",
            covenant_posture="not_required_review_only",
            next_move="produce a taste/operator-experience critique or scoped improvement proposal",
            summary="Use the manifesto for taste without weakening gates or inventing authority.",
        )
    if _contains_any(normalized, ("are we done with packet 07", "packet 07 done", "finished packet 07")):
        return _BridgeMeaning(
            inferred_intent="packet_renewal_readiness_question",
            bridge_domain="packet_renewal_next_packet",
            request_category="read_only_status",
            labels=("packet_renewal", "readiness_review", "file01_authority"),
            evidence=PACKET_RENEWAL_EVIDENCE,
            response_frame="Review Packet 07 completion against File 01 and File 24; do not create Packet 08.",
            covenant_posture="readiness_only_not_approval",
            next_move="prepare a renewal readiness/blueprint review",
            summary="I can review Packet 07 readiness. Packet 08 creation remains gated.",
            follow_up_required=True,
            yes_no_reframe="Do you want a Packet 07 renewal readiness review?",
        )
    return None


def _fallback_meaning(text: str, normalized: str) -> _BridgeMeaning:
    intent = classify_operator_intent(text)
    frame = frame_operator_intent(intent)
    if not normalized:
        inferred_intent = "unsafe_or_ambiguous_action"
    else:
        inferred_intent = intent.name
    return _BridgeMeaning(
        inferred_intent=inferred_intent,
        bridge_domain="unsafe_ambiguous_handle_it",
        request_category=frame.request_category,
        labels=("ambiguous", "intent_core_fallback", "no_hidden_authority"),
        evidence=AMBIGUOUS_EVIDENCE,
        response_frame=frame.recommended_response_frame,
        covenant_posture="clarification_required",
        next_move="narrow the request before selecting more evidence or authority",
        summary="I can infer a possible frame, but I need a narrower request before action.",
        follow_up_required=True,
        yes_no_reframe="Should I give status, draft a prompt, or frame a specific Covenant?",
    )


def _bridge_meaning(text: str, normalized: str) -> _BridgeMeaning:
    restricted = _restricted_meaning(normalized)
    if restricted is not None:
        return restricted
    non_restricted = _non_restricted_meaning(normalized)
    if non_restricted is not None:
        return non_restricted
    return _fallback_meaning(text, normalized)


def _pending_covenant_posture(
    *,
    meaning: _BridgeMeaning,
    pending_covenant: OperatorActionCovenant | None,
    text: str,
) -> tuple[str, str]:
    if pending_covenant is None:
        return meaning.covenant_posture, meaning.yes_no_reframe

    decision = can_operator_confirmation_approve(pending_covenant, text)
    if decision.can_approve:
        return (
            "pending_covenant_confirmation_possible_bridge_does_not_execute",
            (
                "This text matches the pending Covenant confirmation. The bridge "
                "still frames only; an executor would need the separate approval path."
            ),
        )
    return (
        "pending_covenant_present_but_not_confirmed",
        meaning.yes_no_reframe or f"Required confirmation: {decision.required_confirmation}",
    )


def bridge_operator_request(
    text: str,
    pending_covenant: OperatorActionCovenant | None = None,
) -> OperatorEvidenceBridgeResult:
    """Select evidence names and frame the safe response without acting."""
    normalized = _normalize(text)
    core_intent = classify_operator_intent(text)
    simulation: OperatorExtensionSimulation = simulate_operator_extension_request(text)
    meaning = _bridge_meaning(text, normalized)
    covenant_posture, reframe = _pending_covenant_posture(
        meaning=meaning,
        pending_covenant=pending_covenant,
        text=text,
    )

    return OperatorEvidenceBridgeResult(
        original_text=text,
        inferred_intent=meaning.inferred_intent,
        intent_core_intent=core_intent.name,
        simulator_intent=simulation.inferred_intent,
        bridge_domain=meaning.bridge_domain,
        request_category=meaning.request_category,
        machine_contract_labels=meaning.labels,
        approved_evidence_surfaces=_names_only(meaning.evidence),
        response_frame=meaning.response_frame,
        covenant_posture=covenant_posture,
        forbidden_boundaries=_names_only(meaning.forbidden_boundaries),
        safe_substitute_or_next_move=meaning.next_move,
        restricted_block=meaning.restricted_block,
        follow_up_required=meaning.follow_up_required,
        operator_facing_summary=meaning.summary,
        yes_no_reframe=reframe,
    )


def bridge_operator_requests(
    texts: Sequence[str],
) -> tuple[OperatorEvidenceBridgeResult, ...]:
    """Bridge several requests in order without shared state."""
    return tuple(bridge_operator_request(text) for text in texts)


def render_operator_evidence_bridge_result(
    result: OperatorEvidenceBridgeResult,
) -> str:
    """Render a compact operator-facing bridge receipt."""
    lines = [
        "OPERATOR EVIDENCE BRIDGE",
        f"Input: {result.original_text}",
        f"Domain: {result.bridge_domain}",
        f"Intent: {result.inferred_intent}",
        f"Category: {result.request_category}",
        f"Evidence surfaces: {', '.join(result.approved_evidence_surfaces)}",
        f"Covenant: {result.covenant_posture}",
        f"Restricted: {result.restricted_block}",
        f"Forbidden boundaries: {', '.join(result.forbidden_boundaries)}",
        f"Next move: {result.safe_substitute_or_next_move}",
    ]
    if result.yes_no_reframe:
        lines.append(f"Decision frame: {result.yes_no_reframe}")
    lines.append(f"Summary: {result.operator_facing_summary}")
    return "\n".join(lines)


def bridge_phrase_matrix() -> tuple[tuple[str, str], ...]:
    """Return natural-language phrase coverage for bridge tests and receipts."""
    return (
        ("where are we", "status_orientation"),
        ("what changed", "status_orientation"),
        ("what did we just push", "status_orientation"),
        ("what needs my attention", "operator_relief"),
        ("I'm tired, tell me what matters", "operator_relief"),
        ("cut the noise", "operator_relief"),
        ("can we move forward", "forward_motion_readiness"),
        ("is the road clear", "forward_motion_readiness"),
        ("send that to Codex", "codex_coder_routing"),
        ("give this to the coder", "codex_coder_routing"),
        ("make a prompt for the next worker", "codex_coder_routing"),
        ("ask Gemini", "gemini_planning_architecture_routing"),
        ("get a second opinion", "gemini_planning_architecture_routing"),
        ("review this for commit", "commit_push_remote_mutation"),
        ("is this ready to commit", "commit_push_remote_mutation"),
        ("I recommend committing this", "commit_push_remote_mutation"),
        ("can I push", "commit_push_remote_mutation"),
        ("push it", "commit_push_remote_mutation"),
        ("make a handoff", "handoff_packet_continuity"),
        ("prepare the next chat", "handoff_packet_continuity"),
        ("don't let the next worker rediscover this", "handoff_packet_continuity"),
        ("go ahead", "approval_action_covenant_power_boundary"),
        ("ship it", "approval_action_covenant_power_boundary"),
        ("launch it", "runtime_activation_launch"),
        ("start the runtime", "runtime_activation_launch"),
        ("write to MCP memory", "mcp_shared_memory_hidden_authority"),
        ("make this canonical", "mcp_shared_memory_hidden_authority"),
        ("call the provider", "provider_model_api_calls"),
        ("use the API", "provider_model_api_calls"),
        ("send the invoice", "invoice_billing_money"),
        ("check receivables", "invoice_billing_money"),
        ("touch legal files", "legal_private_sensitive"),
        ("read private root", "legal_private_sensitive"),
        ("send the email", "external_sends_communications"),
        ("notify them", "external_sends_communications"),
        ("delete it", "destructive_filesystem_broad_traversal"),
        ("scan the whole drive", "destructive_filesystem_broad_traversal"),
        ("make it sexy", "taste_product_feel_beauty"),
        ("where is the taste", "taste_product_feel_beauty"),
        ("this feels like corporate sludge", "taste_product_feel_beauty"),
        ("are we done with Packet 07", "packet_renewal_next_packet"),
        ("should we make Packet 08", "packet_renewal_next_packet"),
        ("stop", "stop_wait_hold"),
        ("wait", "stop_wait_hold"),
        ("hold", "stop_wait_hold"),
        ("just handle it", "unsafe_ambiguous_handle_it"),
        ("handle it", "unsafe_ambiguous_handle_it"),
        ("do the next thing", "do_next_continue_keep_going"),
        ("continue", "do_next_continue_keep_going"),
        ("keep going", "do_next_continue_keep_going"),
    )
