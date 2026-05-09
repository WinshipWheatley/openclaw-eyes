"""Operator Prompt/Handoff Generator v0.

This module turns operator intent plus bounded evidence references into a
structured worker handoff and paste-ready prompt text.

It is deterministic, local-only, and non-executing:
- no provider/model calls
- no embeddings
- no SQLite
- no runtime/service inspection
- no MCP/shared-memory calls or writes
- no filesystem mutation
- no external sends

Core rule:
Intent selects evidence.
Evidence grounds response.
Covenant governs power.
Operator keeps authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Sequence

from operator_evidence_bridge import (
    RESTRICTED_BRIDGE_DOMAIN_IDS,
    OperatorEvidenceBridgeResult,
    bridge_operator_request,
)
from operator_intent_core import OperatorIntentFrame


WORKER_PROFILES = (
    "gemini_planning",
    "codex_implementation",
    "gemini_review",
    "codex_review",
)

AUTHORITY_BANNER = (
    "Generated prompt/handoff is non-authorizing support material. "
    "It grants no execution authority. Natural language, receipts, evidence "
    "packets, and generated prompts are not approval. Evidence grounds the "
    "response; an Operator Action Covenant governs power; the operator keeps "
    "authority."
)

MAC_WATCH_SUPPORT_BANNER = (
    "Evidence Packet v0 / Mac Watch material is support material only. "
    "It is not canonical repo authority and must not be modified, moved, "
    "renamed, deleted, or treated as permission."
)

RECEIPT_NON_AUTHORITY_STATEMENT = (
    "Receipts are proof snapshots, not approval and not execution authority."
)

DEFAULT_FORBIDDEN_LANES = (
    "live runtime launch",
    "process/service inspection",
    "service/systemd/launchctl mutation",
    "provider/model/API calls",
    "MCP calls or shared/hidden memory writes",
    "embeddings",
    "SQLite/database persistence",
    "private roots, legal/client folders, invoice/finance roots, secrets, env files, credentials, or tokens",
    "external sends",
    "UI/dashboard/app work",
    "Packet 08 creation",
    "commits or pushes unless separately and explicitly authorized",
    "destructive filesystem operations",
)

DEFAULT_STOP_CONDITIONS = (
    "Stop if evidence is missing, stale, contradictory, or insufficient for the requested worker task.",
    "Stop if the task would cross a restricted lane or require private/sensitive access.",
    "Stop if implementation scope expands beyond the named likely files.",
    "Stop if validation cannot be run or produces failures that change the risk posture.",
    "Stop if a prompt, receipt, evidence packet, or model recommendation is being treated as approval.",
)

BASE_CANONICAL_FILES = (
    "Operator/04_ANTI_DRIFT_RULES.md",
    "Operator/07_AUTHORITY_AND_COVENANT_RULES.md",
    "operator_intent_core.py",
    "operator_action_covenant.py",
    "operator_evidence_bridge.py",
)

PROFILE_CANONICAL_FILES = {
    "gemini_planning": (
        "scripts/evidence_packet_generator.py",
        "scripts/openclaw_receipts.py",
    ),
    "codex_implementation": (
        "operator_prompt_handoff_generator.py",
        "tests/test_operator_prompt_handoff_generator.py",
        "scripts/openclaw_receipts.py",
        "tests/test_openclaw_receipts.py",
    ),
    "gemini_review": (
        "scripts/evidence_packet_generator.py",
        "scripts/openclaw_receipts.py",
        "tests/test_openclaw_receipts.py",
    ),
    "codex_review": (
        "operator_prompt_handoff_generator.py",
        "tests/test_operator_prompt_handoff_generator.py",
        "scripts/openclaw_receipts.py",
        "tests/test_openclaw_receipts.py",
    ),
}

PROFILE_IMPLEMENTATION_BOUNDARIES = {
    "gemini_planning": (
        "Planning/review only. Do not mutate repo files, do not approve execution, "
        "and do not convert support material into canonical authority. Return "
        "READY/NOT_READY-style planning findings only."
    ),
    "codex_implementation": (
        "Bounded repo mutation only inside the named likely files. Produce a "
        "reviewable diff and focused tests. Do not commit, push, call providers, "
        "launch runtime services, inspect process state, use MCP, use embeddings, "
        "use SQLite, access private roots, or send external messages."
    ),
    "gemini_review": (
        "Architecture/scope/risk review only. Return READY/NOT_READY-style "
        "findings with evidence references. Do not authorize execution."
    ),
    "codex_review": (
        "Diff/test/boundary review only. Inspect changed behavior and validation "
        "posture. Do not stage, commit, push, or broaden implementation scope."
    ),
}

PROFILE_VALIDATION_COMMANDS = {
    "gemini_planning": (
        "Review supplied evidence references only; do not run commands unless separately authorized in the operator environment.",
    ),
    "codex_implementation": (
        "python3 -m py_compile operator_prompt_handoff_generator.py operator_intent_core.py operator_action_covenant.py operator_evidence_bridge.py scripts/openclaw_receipts.py",
        "PYTHONPATH=. pytest tests/test_operator_prompt_handoff_generator.py -q",
        "PYTHONPATH=. pytest tests/test_openclaw_receipts.py -q",
        "./scripts/openclaw_receipts.py repo-check",
        "./scripts/openclaw_receipts.py operator-harness-status",
        "./scripts/openclaw_receipts.py operator-intent-core-status",
        "./scripts/openclaw_receipts.py operator-action-covenant-status",
        "git diff --check",
        "git diff --name-only",
    ),
    "gemini_review": (
        "Review supplied evidence references and validation outputs only; do not run provider/runtime/MCP actions from repo code.",
    ),
    "codex_review": (
        "PYTHONPATH=. pytest tests/test_operator_prompt_handoff_generator.py -q",
        "PYTHONPATH=. pytest tests/test_openclaw_receipts.py -q",
        "git diff --check",
        "git diff --name-only",
    ),
}

PROFILE_INSTRUCTIONS = {
    "gemini_planning": (
        "Use the evidence to clarify plan, risk, scope, and next safe action. "
        "Separate canonical repo authority from Mac Watch support material. "
        "Return concise planning findings and identify any missing evidence."
    ),
    "codex_implementation": (
        "Implement only the bounded slice described by this handoff. Keep changes "
        "small enough to review but complete enough to prove behavior with tests. "
        "If the task needs more authority, stop and report the covenant gap."
    ),
    "gemini_review": (
        "Review architecture alignment, scope risk, authority boundaries, and "
        "whether the evidence supports the proposed next move. Return findings "
        "instead of execution approval."
    ),
    "codex_review": (
        "Review the dirty diff and tests for correctness, boundary leaks, missing "
        "validation, and commit readiness. Do not commit or stage changes."
    ),
}

DEFAULT_LIKELY_FILES_BY_PROFILE = {
    "gemini_planning": (),
    "codex_implementation": (
        "operator_prompt_handoff_generator.py",
        "tests/test_operator_prompt_handoff_generator.py",
    ),
    "gemini_review": (),
    "codex_review": (
        "operator_prompt_handoff_generator.py",
        "tests/test_operator_prompt_handoff_generator.py",
    ),
}


@dataclass(frozen=True)
class EvidenceReference:
    source_type: str
    reference: str
    title: str = ""
    authority_role: str = "evidence"
    freshness: str = ""
    needs_deeper_review: bool = False


@dataclass(frozen=True)
class OperatorPromptHandoff:
    target_worker_profile: str
    status: str
    classified_intent: str
    bridge_domain: str
    request_category: str
    authority_banner: str
    canonical_files_to_read: tuple[str, ...]
    canonical_evidence_references: tuple[EvidenceReference, ...]
    mac_watch_support_material: tuple[EvidenceReference, ...]
    implementation_boundary: str
    likely_files_to_change: tuple[str, ...]
    validation_commands: tuple[str, ...]
    forbidden_lanes: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    covenant_posture: str
    no_execution_authority_statement: str
    prompt_text: str


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _validate_worker_profile(profile: str) -> str:
    normalized = str(profile).strip()
    if normalized not in WORKER_PROFILES:
        allowed = ", ".join(WORKER_PROFILES)
        raise ValueError(
            f"unknown target_worker_profile: {profile!r}; expected one of {allowed}"
        )
    return normalized


def _reference_source_type(reference: str) -> str:
    lowered = reference.lower()
    if lowered.startswith("operator/"):
        return "canonical_repo"
    if lowered.startswith("scripts/") or lowered.startswith("tests/"):
        return "canonical_repo"
    if reference.endswith(".py") or reference.endswith(".md"):
        return "canonical_repo"
    if "packet 07" in lowered or "active_handoff" in lowered:
        return "canonical_repo"
    if "receipt" in lowered or "repo-check" in lowered or "status" in lowered:
        return "proof_snapshot"
    return "explicit_reference"


def _coerce_evidence_reference(
    value: EvidenceReference | Mapping[str, object] | str,
) -> EvidenceReference:
    if isinstance(value, EvidenceReference):
        return value

    if isinstance(value, str):
        reference = value.strip()
        return EvidenceReference(
            source_type=_reference_source_type(reference),
            reference=reference,
            authority_role="explicit_evidence_reference",
        )

    reference = str(
        value.get("reference") or value.get("source_path") or value.get("path") or ""
    ).strip()
    if not reference:
        raise ValueError("evidence reference mapping must include reference, source_path, or path")

    source_type = str(value.get("source_type") or _reference_source_type(reference)).strip()
    title = str(value.get("title") or value.get("first_heading") or "").strip()
    authority_role = str(value.get("authority_role") or "explicit_evidence_reference").strip()
    freshness = str(value.get("freshness") or value.get("freshness_class") or "").strip()
    needs_deeper_review = bool(value.get("needs_deeper_review", False))

    return EvidenceReference(
        source_type=source_type,
        reference=reference,
        title=title,
        authority_role=authority_role,
        freshness=freshness,
        needs_deeper_review=needs_deeper_review,
    )


def _evidence_from_packet(
    evidence_packet: Mapping[str, object] | None,
) -> tuple[EvidenceReference, ...]:
    if evidence_packet is None:
        return ()

    files = evidence_packet.get("files", ())
    if not isinstance(files, Sequence) or isinstance(files, (str, bytes)):
        return ()

    references: list[EvidenceReference] = []
    for item in files:
        if not isinstance(item, Mapping):
            continue
        source_path = str(item.get("source_path") or "").strip()
        if not source_path:
            continue
        references.append(
            EvidenceReference(
                source_type="mac_watch_support",
                reference=source_path,
                title=str(item.get("title") or "").strip(),
                authority_role="support_material_only_not_canonical",
                freshness=str(item.get("freshness_class") or "").strip(),
                needs_deeper_review=bool(item.get("needs_deeper_review", False)),
            )
        )
    return tuple(references)


def _normalize_evidence(
    *,
    evidence_packet: Mapping[str, object] | None,
    evidence_references: Sequence[EvidenceReference | Mapping[str, object] | str] | None,
) -> tuple[EvidenceReference, ...]:
    packet_refs = _evidence_from_packet(evidence_packet)
    explicit_refs = tuple(
        _coerce_evidence_reference(item)
        for item in (evidence_references or ())
    )

    seen: set[tuple[str, str]] = set()
    normalized: list[EvidenceReference] = []
    for reference in packet_refs + explicit_refs:
        key = (reference.source_type, reference.reference)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(reference)
    return tuple(normalized)


def _split_evidence(
    references: Sequence[EvidenceReference],
) -> tuple[tuple[EvidenceReference, ...], tuple[EvidenceReference, ...]]:
    canonical: list[EvidenceReference] = []
    mac_watch: list[EvidenceReference] = []
    for reference in references:
        if reference.source_type == "mac_watch_support":
            mac_watch.append(reference)
        else:
            canonical.append(reference)
    return tuple(canonical), tuple(mac_watch)


def _canonical_files_for_profile(profile: str) -> tuple[str, ...]:
    return _dedupe(BASE_CANONICAL_FILES + PROFILE_CANONICAL_FILES[profile])


def _intent_from_frame_or_bridge(
    *,
    operator_text: str | None,
    intent_frame: OperatorIntentFrame | None,
) -> tuple[str, str, str, str, OperatorEvidenceBridgeResult]:
    text = operator_text if operator_text is not None else ""
    if not text and intent_frame is not None:
        text = intent_frame.intent_name

    bridge = bridge_operator_request(text)
    if intent_frame is None:
        return (
            bridge.inferred_intent,
            bridge.bridge_domain,
            bridge.request_category,
            bridge.covenant_posture,
            bridge,
        )

    return (
        intent_frame.intent_name,
        bridge.bridge_domain,
        intent_frame.request_category,
        bridge.covenant_posture,
        bridge,
    )


def _is_restricted(bridge: OperatorEvidenceBridgeResult) -> bool:
    return bridge.restricted_block or bridge.bridge_domain in RESTRICTED_BRIDGE_DOMAIN_IDS


def _status_for(
    *,
    profile: str,
    has_evidence: bool,
    restricted: bool,
) -> str:
    if restricted:
        return "blocked_covenant_required"
    if not has_evidence:
        if profile == "codex_implementation":
            return "needs_evidence_implementation_blocked"
        return "needs_evidence"
    return "ready_non_authorizing"


def _render_evidence_lines(
    canonical: Sequence[EvidenceReference],
    mac_watch: Sequence[EvidenceReference],
) -> tuple[str, ...]:
    lines: list[str] = []

    lines.append("Canonical repo evidence / proof snapshots:")
    if canonical:
        for reference in canonical:
            suffix_parts = []
            if reference.title:
                suffix_parts.append(f"title={reference.title}")
            if reference.freshness:
                suffix_parts.append(f"freshness={reference.freshness}")
            if reference.needs_deeper_review:
                suffix_parts.append("needs_deeper_review=True")
            suffix = f" ({'; '.join(suffix_parts)})" if suffix_parts else ""
            lines.append(
                f"- {reference.reference} [{reference.source_type}; {reference.authority_role}]{suffix}"
            )
    else:
        lines.append("- none supplied")

    lines.append("Mac Watch / Evidence Packet v0 support material:")
    if mac_watch:
        for reference in mac_watch:
            suffix_parts = []
            if reference.title:
                suffix_parts.append(f"title={reference.title}")
            if reference.freshness:
                suffix_parts.append(f"freshness={reference.freshness}")
            if reference.needs_deeper_review:
                suffix_parts.append("needs_deeper_review=True")
            suffix = f" ({'; '.join(suffix_parts)})" if suffix_parts else ""
            lines.append(
                f"- {reference.reference} [support_material_only_not_canonical]{suffix}"
            )
    else:
        lines.append("- none supplied")

    return tuple(lines)


def _render_prompt_text(
    *,
    profile: str,
    status: str,
    operator_text: str,
    classified_intent: str,
    bridge_domain: str,
    request_category: str,
    canonical_files_to_read: Sequence[str],
    canonical_evidence: Sequence[EvidenceReference],
    mac_watch_support: Sequence[EvidenceReference],
    implementation_boundary: str,
    likely_files_to_change: Sequence[str],
    validation_commands: Sequence[str],
    forbidden_lanes: Sequence[str],
    stop_conditions: Sequence[str],
    covenant_posture: str,
    bridge: OperatorEvidenceBridgeResult,
) -> str:
    lines: list[str] = [
        "OPERATOR PROMPT/HANDOFF v0",
        "",
        "AUTHORITY BANNER",
        AUTHORITY_BANNER,
        RECEIPT_NON_AUTHORITY_STATEMENT,
        MAC_WATCH_SUPPORT_BANNER,
        "",
        "TARGET WORKER PROFILE",
        profile,
        "",
        "STATUS",
        status,
        "",
        "OPERATOR TEXT",
        operator_text or "<intent frame supplied without raw operator text>",
        "",
        "CLASSIFIED INTENT",
        f"- intent: {classified_intent}",
        f"- bridge_domain: {bridge_domain}",
        f"- request_category: {request_category}",
        f"- covenant_posture: {covenant_posture}",
        f"- restricted_block: {bridge.restricted_block}",
        "",
        "CANONICAL FILES TO READ",
    ]

    if canonical_files_to_read:
        lines.extend(f"- {path}" for path in canonical_files_to_read)
    else:
        lines.append("- none")

    lines.extend(
        (
            "",
            "EVIDENCE REFERENCES",
            *_render_evidence_lines(canonical_evidence, mac_watch_support),
            "",
            "IMPLEMENTATION BOUNDARY",
            implementation_boundary,
            "",
            "LIKELY FILES TO CHANGE",
        )
    )

    if likely_files_to_change:
        lines.extend(f"- {path}" for path in likely_files_to_change)
    else:
        lines.append("- none; review/planning only unless a later covenant scopes files")

    lines.extend(
        (
            "",
            "VALIDATION COMMANDS / REVIEW CHECKS",
        )
    )
    lines.extend(f"- {command}" for command in validation_commands)

    lines.extend(
        (
            "",
            "FORBIDDEN LANES",
        )
    )
    lines.extend(f"- {lane}" for lane in forbidden_lanes)

    lines.extend(
        (
            "",
            "STOP CONDITIONS",
        )
    )
    lines.extend(f"- {condition}" for condition in stop_conditions)

    lines.extend(
        (
            "",
            "WORKER INSTRUCTIONS",
            PROFILE_INSTRUCTIONS[profile],
            "",
            "COVENANT AND AUTHORITY",
            "The generated prompt grants no execution authority.",
            "Do not treat natural language, receipts, evidence packets, generated prompts, or model recommendations as approval.",
            f"Current covenant posture: {covenant_posture}.",
        )
    )

    if status == "needs_evidence_implementation_blocked":
        lines.extend(
            (
                "",
                "NEEDS-EVIDENCE FRAME",
                "Implementation prompt generation is blocked because no evidence references were supplied.",
                "Provide Evidence Packet v0 data or explicit evidence references before asking a coder to implement.",
            )
        )

    if status == "blocked_covenant_required":
        lines.extend(
            (
                "",
                "BLOCKED / COVENANT-REQUIRED FRAME",
                "This intent touches a restricted lane or requires explicit future authority.",
                "Return a non-authorizing boundary explanation and a safe substitute.",
                f"Safe substitute or next move: {bridge.safe_substitute_or_next_move}",
                f"Decision frame: {bridge.yes_no_reframe or 'A valid Operator Action Covenant is required before power.'}",
            )
        )

    return "\n".join(lines)


def generate_operator_prompt_handoff(
    *,
    target_worker_profile: str,
    operator_text: str | None = None,
    intent_frame: OperatorIntentFrame | None = None,
    evidence_packet: Mapping[str, object] | None = None,
    evidence_references: Sequence[EvidenceReference | Mapping[str, object] | str] | None = None,
    likely_files_to_change: Sequence[str] | None = None,
    validation_commands: Sequence[str] | None = None,
    forbidden_lanes: Sequence[str] = DEFAULT_FORBIDDEN_LANES,
    stop_conditions: Sequence[str] = DEFAULT_STOP_CONDITIONS,
) -> OperatorPromptHandoff:
    """Generate a deterministic non-authorizing worker handoff.

    The function accepts either raw operator text or a pre-classified intent
    frame. It never executes commands, reads files, calls providers, calls MCP,
    uses embeddings, uses SQLite, or mutates state.
    """
    profile = _validate_worker_profile(target_worker_profile)
    raw_text = str(operator_text or "").strip()

    classified_intent, bridge_domain, request_category, covenant_posture, bridge = (
        _intent_from_frame_or_bridge(
            operator_text=raw_text,
            intent_frame=intent_frame,
        )
    )

    evidence = _normalize_evidence(
        evidence_packet=evidence_packet,
        evidence_references=evidence_references,
    )
    canonical_evidence, mac_watch_support = _split_evidence(evidence)
    has_evidence = bool(evidence)
    restricted = _is_restricted(bridge)
    status = _status_for(
        profile=profile,
        has_evidence=has_evidence,
        restricted=restricted,
    )

    if restricted:
        covenant_posture = (
            f"{covenant_posture}; restricted lane remains non-authorizing and "
            "requires a future explicit Operator Action Covenant before power"
        )

    canonical_files_to_read = _canonical_files_for_profile(profile)
    likely_files = _dedupe(
        tuple(likely_files_to_change)
        if likely_files_to_change is not None
        else DEFAULT_LIKELY_FILES_BY_PROFILE[profile]
    )
    validation = _dedupe(
        tuple(validation_commands)
        if validation_commands is not None
        else PROFILE_VALIDATION_COMMANDS[profile]
    )
    forbidden = _dedupe(tuple(forbidden_lanes))
    stops = _dedupe(tuple(stop_conditions))
    implementation_boundary = PROFILE_IMPLEMENTATION_BOUNDARIES[profile]
    no_authority = "The generated prompt grants no execution authority."

    prompt_text = _render_prompt_text(
        profile=profile,
        status=status,
        operator_text=raw_text,
        classified_intent=classified_intent,
        bridge_domain=bridge_domain,
        request_category=request_category,
        canonical_files_to_read=canonical_files_to_read,
        canonical_evidence=canonical_evidence,
        mac_watch_support=mac_watch_support,
        implementation_boundary=implementation_boundary,
        likely_files_to_change=likely_files,
        validation_commands=validation,
        forbidden_lanes=forbidden,
        stop_conditions=stops,
        covenant_posture=covenant_posture,
        bridge=bridge,
    )

    return OperatorPromptHandoff(
        target_worker_profile=profile,
        status=status,
        classified_intent=classified_intent,
        bridge_domain=bridge_domain,
        request_category=request_category,
        authority_banner=AUTHORITY_BANNER,
        canonical_files_to_read=canonical_files_to_read,
        canonical_evidence_references=canonical_evidence,
        mac_watch_support_material=mac_watch_support,
        implementation_boundary=implementation_boundary,
        likely_files_to_change=likely_files,
        validation_commands=validation,
        forbidden_lanes=forbidden,
        stop_conditions=stops,
        covenant_posture=covenant_posture,
        no_execution_authority_statement=no_authority,
        prompt_text=prompt_text,
    )


def handoff_to_dict(handoff: OperatorPromptHandoff) -> dict[str, object]:
    """Return a plain deterministic dictionary for tests, receipts, or JSON."""
    return asdict(handoff)


def operator_handoff_generator_status() -> dict[str, object]:
    """Return static read-only status for future receipt integration."""
    checks = {
        "worker_profiles_present": WORKER_PROFILES
        == (
            "gemini_planning",
            "codex_implementation",
            "gemini_review",
            "codex_review",
        ),
        "authority_banner_non_authorizing": "grants no execution authority" in AUTHORITY_BANNER,
        "receipts_not_approval": "proof snapshots, not approval" in RECEIPT_NON_AUTHORITY_STATEMENT,
        "mac_watch_support_not_canonical": "support material only" in MAC_WATCH_SUPPORT_BANNER,
        "forbidden_runtime_provider_mcp_sqlite_embeddings_named": all(
            phrase in " ".join(DEFAULT_FORBIDDEN_LANES)
            for phrase in (
                "provider/model/API calls",
                "MCP calls",
                "embeddings",
                "SQLite",
                "live runtime launch",
            )
        ),
        "implementation_profile_has_validation": bool(PROFILE_VALIDATION_COMMANDS["codex_implementation"]),
        "stop_conditions_present": bool(DEFAULT_STOP_CONDITIONS),
    }
    return {
        "receipt_type": "openclaw.operator_handoff_generator_status",
        "mode": "read-only/static-generator-proof/no-execution",
        "authority_note": AUTHORITY_BANNER,
        "worker_profiles": WORKER_PROFILES,
        "execution_authority_granted": False,
        "provider_or_model_called": False,
        "runtime_launched": False,
        "process_state_inspected": False,
        "mcp_called": False,
        "hidden_memory_write_used": False,
        "sqlite_used": False,
        "embeddings_used": False,
        "external_send_used": False,
        "checks": checks,
        "passed": all(checks.values()),
    }
