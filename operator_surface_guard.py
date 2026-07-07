"""Operator Surface Guard — runtime enforcement for the Persona Voice / Comedy doctrine.

Grounds:
  - master_voice.sh voice-layer leak guard (inline Python, 2026-06-22): raw JSON / receipts /
    stack traces refused at the operator surface.
  - agent_voice_response_layer.py constraint NO_JARGON_IN_ELIWINSHIP: no raw JSON keys, file
    paths, hashes, class names, or rail jargon in ELIWINSHIP-audience text.
  - SYSTEM-READY-PERSONA-VOICE-COMEDY-PACKET-DOCTRINE.md:
      Zero-Error Gate: if error_flags > 0 or a process hangs, comedic_intent hard-locked False.
      Golden Ratio: ~10-15% chance of comedy on a successful pass; jokes must stay surprising.
      Funny ranking (least → most): Guardian < Chief < Cassandra < Hermes < Maestro < Niles.

Contract:
  - DETERMINISTIC. No LLM calls. No external I/O. No side effects.
  - Import-safe in OPENCLAW_TEST_MODE=1 / OPENCLAW_SEND_HOLD=1.
  - All public functions return plain dicts (JSON-serialisable) with a machine_proof block.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Constants — grounded in the doctrine and the existing voice layer
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "operator_surface_guard_v0"
CONTRACT_STATUS = "DETERMINISTIC_OPERATOR_SURFACE_GUARD_NO_EXECUTION"

# Funny ranking from the doctrine (least funny to most funny).
# Guardians never emit comedy.
FUNNY_RANKING: dict[str, int] = {
    "GUARDIAN": 0,
    "CHIEF": 1,
    "CASSANDRA": 2,
    "HERMES": 3,
    "MAESTRO": 4,
    "NILES": 5,
    "OPENCLAW_SYSTEM": 0,  # system voice = never funny
    "UNKNOWN": 0,
}

# Minimum comedy rank needed to be eligible at all.
# Guardian and system voices (rank 0) can never emit comedy.
COMEDY_RANK_FLOOR = 1

# Golden Ratio: 10–15% base chance, seeded deterministically from content hash so tests
# are repeatable. The caller controls the random seed by passing payload_hash.
COMEDY_BASE_CHANCE = 0.12  # 12% — mid-range of the 10–15% doctrine window

_STATUS_SURFACE_PHRASES = {
    "open_not_paid": "check expected, not yet paid",
    "needs_reconcile": "needs your reconcile",
    "needs_operator_review": "needs operator review",
    "pending_approval": "needs approval",
    "approval_required": "needs approval",
    "open": "open",
    "routed": "routed",
    "rejected": "rejected",
    "paid": "paid",
    "settled": "settled",
    "invoice_due": "invoice due",
    "not_tracked": "not tracked",
    "needs_review": "needs review",
}

_MONTH_NAMES = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

_BARE_MONTH_CODE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_BARE_MONTH_CODE_IN_TEXT_RE = re.compile(r"\b\d{4}-(?:0[1-9]|1[0-2])(?!-\d)\b")
_SURFACE_STATUS_TOKEN_RE = re.compile(
    r"\b(open_not_paid|needs_reconcile|needs_operator_review|pending_approval|approval_required)\b"
)
_MONEY_DASH_RE = re.compile(
    r"\b(still owes\s+\$[0-9][0-9,]*(?:\.\d{2})?)\s+-\s+"
    r"(needs your reconcile|check expected, not yet paid)\b",
    re.IGNORECASE,
)

_ACTOR_LABELS = {
    "chief": "Chief",
    "cassandra": "Cassandra",
    "guardian": "Guardian",
    "niles": "Niles",
    "hermes": "Hermes",
    "report_bridge": "Report Bridge",
    "operator": "Operator",
    "unrouted": "Operator",
}

_INTENT_VERBS = {
    "file_context_request": "review",
    "markdown_reorg_request": "organize",
    "read_model_refresh_request": "refresh",
    "report_bridge_request": "review",
    "safety_review_request": "review",
    "communication_summary_request": "summarize",
    "music_project_request": "review",
    "project_capsule_request": "review",
    "status_orientation_request": "review",
    "unknown_review": "clarify",
}

_INTENT_OBJECTS = {
    "markdown_reorg_request": "Markdown files",
    "read_model_refresh_request": "read-model mirror",
    "report_bridge_request": "Report Bridge package",
    "safety_review_request": "safety question",
    "communication_summary_request": "status summary",
    "music_project_request": "music project",
    "project_capsule_request": "project capsule",
    "status_orientation_request": "current status",
    "unknown_review": "unclear request",
}


# ---------------------------------------------------------------------------
# Operator decision/status wording
# ---------------------------------------------------------------------------

def operator_surface_value(value: Any) -> str:
    """Return the operator-facing spelling for machine statuses and month codes."""
    text = str(value or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in _STATUS_SURFACE_PHRASES:
        return _STATUS_SURFACE_PHRASES[lowered]
    month_match = _BARE_MONTH_CODE_RE.fullmatch(text)
    if month_match:
        return _MONTH_NAMES[int(month_match.group(1))]
    if "_" in text:
        return text.replace("_", " ")
    return text


def render_operator_money_status_line(*, entity: Any, amount: Any, status: Any) -> str:
    """Render a money/status item without leaking raw status tokens."""
    entity_text = str(entity or "Unknown client").strip() or "Unknown client"
    amount_text = str(amount or "amount unverified").strip() or "amount unverified"
    return f"{entity_text} still owes {amount_text} — {operator_surface_value(status)}"


def operator_surface_text(value: Any) -> str:
    """Humanize known machine status tokens and bare month codes inside text."""
    text = str(value or "").strip()
    if not text:
        return ""
    text = _SURFACE_STATUS_TOKEN_RE.sub(lambda match: operator_surface_value(match.group(0)), text)
    text = _BARE_MONTH_CODE_IN_TEXT_RE.sub(lambda match: operator_surface_value(match.group(0)), text)
    text = _MONEY_DASH_RE.sub(lambda match: f"{match.group(1)} — {match.group(2)}", text)
    return text


def _actor_label(actor: Any) -> str:
    normalized = str(actor or "operator").strip().lower().replace(" ", "_")
    return _ACTOR_LABELS.get(normalized, normalized.replace("_", " ").title() or "Operator")


def _intent_object_from_text(raw_text: str, intent_category: str) -> str:
    lowered = raw_text.lower()
    if "logic" in lowered:
        return "new Logic file" if "new" in lowered else "Logic file"
    if "markdown" in lowered:
        return "new Markdown file" if "new" in lowered and "file" in lowered else "Markdown files"
    if "report bridge" in lowered and ("read-model" in lowered or "read model" in lowered):
        return "Report Bridge read-model"
    if "read-model" in lowered or "read model" in lowered:
        return "read-model mirror"
    return _INTENT_OBJECTS.get(intent_category, "request")


def _intent_status_phrase(status: Any) -> str:
    normalized = str(status or "").strip().lower()
    if normalized == "routed":
        return "is routed"
    if normalized == "rejected":
        return "was rejected"
    phrase = operator_surface_value(normalized)
    return phrase if phrase.startswith(("is ", "was ", "needs ")) else f"is {phrase}"


def refine_operator_intent_surface(
    *,
    raw_text: Any,
    actor: Any,
    intent_category: Any,
    status: Any,
    as_of: Any,
) -> dict[str, Any]:
    """Return refined intent metadata for operator surfaces.

    The raw intake stays only in provenance fields. ``operator_display`` is
    deterministic and built from refined actor/object/status fields.
    """
    raw = re.sub(r"\s+", " ", str(raw_text or "").replace("\x00", "")).strip()
    category = str(intent_category or "unknown_review").strip()
    actor_label = _actor_label(actor)
    status_token = str(status or "needs_operator_review").strip() or "needs_operator_review"
    verb = _INTENT_VERBS.get(category, "review")
    obj = _intent_object_from_text(raw, category)
    status_phrase = _intent_status_phrase(status_token)
    raw_hash = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()
    needs_review = status_token == "needs_operator_review"
    return {
        "refined_actor": actor_label,
        "refined_verb": verb,
        "refined_object": obj,
        "refined_status": status_token,
        "refined_as_of": str(as_of or ""),
        "provenance_raw": raw,
        "provenance_raw_sha256": raw_hash,
        "needs_operator_review": 1 if needs_review else 0,
        "refinement_status": "needs_operator_review" if needs_review else "structured",
        "operator_display": f"{actor_label} request about {obj} {status_phrase}.",
    }


# ---------------------------------------------------------------------------
# Machine-contract leak detection (extends master_voice.sh guard)
# ---------------------------------------------------------------------------

# Raw JSON heuristic — same as master_voice.sh: >=2 "key": value hits = machine contract.
_JSON_KEY_RE = re.compile(r'"[A-Za-z_][A-Za-z0-9_]*"\s*:')

# Class names and field names that must never reach an ELIWINSHIP surface.
# Drawn from agent_voice_response_layer.py constraint NO_JARGON_IN_ELIWINSHIP:
#   "ELIWINSHIP wording avoids raw JSON keys, file paths, hashes, class names, and rail jargon."
_CLASS_NAME_RE = re.compile(
    r"\b(?:"
    r"OpenClawResponseForMac"
    r"|VoiceBoundResponsePacket"
    r"|AgentVoiceProfile"
    r"|AgentVibeProfile"
    r"|VoiceTransformConstraint"
    r"|AgentVoiceSelectionPolicy"
    r"|AgentVoiceResponseLayer"
    r"|ModelSelectionPolicy"
    r")\b"
)

# Internal field / receipt patterns from master_voice.sh:
_RECEIPT_FIELD_RE = re.compile(
    r"content_hash=|request_id=|source_request_id=|internal_status="
)

# Stack trace marker (same as master_voice.sh):
_STACK_TRACE = "Traceback (most recent call last)"

# File-path leakage (absolute paths should not reach the operator in ELIWINSHIP mode).
_ABSOLUTE_PATH_RE = re.compile(r"(?:/home/|/mnt/|C:\\|D:\\|E:\\)[A-Za-z0-9_./ \\-]{6,}")

# Hash leakage: sha256/sha1 hex strings of 16+ chars.
_HASH_RE = re.compile(r"\b[0-9a-f]{16,64}\b")


@dataclass(frozen=True)
class LeakCheckResult:
    is_leak: bool
    reasons: tuple[str, ...]
    machine_proof: dict[str, bool]


def check_machine_contract_leak(text: str, audience: str = "ELIWINSHIP") -> LeakCheckResult:
    """Return True if ``text`` contains machine-contract language.

    Extends the master_voice.sh inline guard with additional class-name,
    file-path, and hash checks from the NO_JARGON_IN_ELIWINSHIP constraint.

    Behaviour:
      - ELIWINSHIP audience: full check (the strict gate).
      - TECHNICAL / DEBUG audiences: only checks stack traces and raw JSON
        bodies (class names, hashes, paths are acceptable for technical views).
    """
    reasons: list[str] = []

    # Always blocked regardless of audience
    if text.strip().startswith(("{", "[")):
        reasons.append("text_starts_with_json_structure")
    json_key_hits = len(_JSON_KEY_RE.findall(text))
    if json_key_hits >= 2:
        reasons.append(f"json_key_pattern_count={json_key_hits}")
    if _STACK_TRACE in text:
        reasons.append("stack_trace_present")
    if _RECEIPT_FIELD_RE.search(text):
        reasons.append("receipt_field_pattern_present")

    # ELIWINSHIP-only checks
    if audience == "ELIWINSHIP":
        if _CLASS_NAME_RE.search(text):
            reasons.append("class_name_present_in_eliwinship")
        if _ABSOLUTE_PATH_RE.search(text):
            reasons.append("absolute_path_present_in_eliwinship")
        if _HASH_RE.search(text):
            reasons.append("hash_string_present_in_eliwinship")

    is_leak = len(reasons) > 0
    return LeakCheckResult(
        is_leak=is_leak,
        reasons=tuple(reasons),
        machine_proof={
            "tts_live_connection_performed": False,
            "message_send_performed": False,
            "external_action_performed": False,
            "check_performed": True,
        },
    )


# ---------------------------------------------------------------------------
# Zero-Error Gate + Comedy Intent Gate
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ComedyGateResult:
    """Result of the comedy intent gate.

    ``comedy_eligible`` is True only when ALL of:
      1. error_flags == 0 (Zero-Error Gate)
      2. no process_hung flag
      3. agent is not high-risk / proof-gated
      4. agent humor rank >= COMEDY_RANK_FLOOR
      5. golden_ratio roll passes (seeded by payload hash for determinism)
    """
    comedy_eligible: bool
    comedy_hard_locked: bool       # True when zero-error gate fires
    kill_switch_reason: str        # why it's locked, or "" if open
    agent_humor_rank: int
    golden_ratio_passed: bool
    machine_proof: dict[str, bool]


def _stable_hash_int(text: str) -> int:
    """Deterministic integer from text content for golden-ratio gate."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def check_comedy_gate(
    *,
    agent_role: str,
    error_flags: int = 0,
    process_hung: bool = False,
    high_risk_context: bool = False,
    payload_hash: str = "",
) -> ComedyGateResult:
    """Evaluate whether a comedy line may be emitted for this agent + context.

    This is deterministic: given the same inputs (including payload_hash) the
    result is always the same.  The ``payload_hash`` seeds the golden-ratio
    roll — pass a stable string (e.g. a content hash of the response packet)
    so the same packet always gets the same comedy decision.

    Zero-Error Gate (doctrine): if error_flags > 0 or process_hung,
    comedic_intent is hard-locked False. No exceptions.
    """
    # --- Zero-Error Gate ---
    if error_flags > 0 or process_hung:
        reason = (
            "process_hung=True" if process_hung else f"error_flags={error_flags}"
        )
        return ComedyGateResult(
            comedy_eligible=False,
            comedy_hard_locked=True,
            kill_switch_reason=reason,
            agent_humor_rank=FUNNY_RANKING.get(agent_role.upper(), 0),
            golden_ratio_passed=False,
            machine_proof={
                "comedy_model_call_performed": False,
                "comedy_external_action_performed": False,
                "zero_error_gate_enforced": True,
                "check_performed": True,
            },
        )

    # --- High-risk context suppresses comedy ---
    if high_risk_context:
        return ComedyGateResult(
            comedy_eligible=False,
            comedy_hard_locked=True,
            kill_switch_reason="high_risk_context=True",
            agent_humor_rank=FUNNY_RANKING.get(agent_role.upper(), 0),
            golden_ratio_passed=False,
            machine_proof={
                "comedy_model_call_performed": False,
                "comedy_external_action_performed": False,
                "zero_error_gate_enforced": False,
                "check_performed": True,
            },
        )

    humor_rank = FUNNY_RANKING.get(agent_role.upper(), 0)

    # --- Agent humor rank floor ---
    if humor_rank < COMEDY_RANK_FLOOR:
        return ComedyGateResult(
            comedy_eligible=False,
            comedy_hard_locked=False,
            kill_switch_reason=f"agent_humor_rank={humor_rank} below floor={COMEDY_RANK_FLOOR}",
            agent_humor_rank=humor_rank,
            golden_ratio_passed=False,
            machine_proof={
                "comedy_model_call_performed": False,
                "comedy_external_action_performed": False,
                "zero_error_gate_enforced": False,
                "check_performed": True,
            },
        )

    # --- Golden Ratio (10–15% base chance) ---
    # Scale threshold by humor rank so funnier agents get more shots:
    #   rank 1 (Chief)    → 12% base
    #   rank 5 (Niles)    → 12% × (5/1) capped at 60%
    # Then cap at a doctrine-sensible ceiling so jokes never become noise.
    MAX_CHANCE = 0.60
    rank_scaled = min(COMEDY_BASE_CHANCE * humor_rank, MAX_CHANCE)

    seed_int = _stable_hash_int(payload_hash or agent_role)
    # Map to [0.0, 1.0)
    normalized = (seed_int % 10_000) / 10_000.0
    golden_ratio_passed = normalized < rank_scaled

    return ComedyGateResult(
        comedy_eligible=golden_ratio_passed,
        comedy_hard_locked=False,
        kill_switch_reason="" if golden_ratio_passed else "golden_ratio_not_passed",
        agent_humor_rank=humor_rank,
        golden_ratio_passed=golden_ratio_passed,
        machine_proof={
            "comedy_model_call_performed": False,
            "comedy_external_action_performed": False,
            "zero_error_gate_enforced": False,
            "check_performed": True,
        },
    )


# ---------------------------------------------------------------------------
# Combined operator surface check
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OperatorSurfaceCheckResult:
    """Result of a full operator surface check.

    ``safe_for_operator`` is True only when:
      - No machine-contract leak detected for the given audience.
    The comedy gate is independent — it can be eligible even if the text
    is safe (and the caller decides what to do with that eligibility).
    """
    safe_for_operator: bool
    leak_check: LeakCheckResult
    comedy_gate: ComedyGateResult
    schema_version: str
    contract_status: str


def check_operator_surface(
    text: str,
    *,
    agent_role: str = "OPENCLAW_SYSTEM",
    audience: str = "ELIWINSHIP",
    error_flags: int = 0,
    process_hung: bool = False,
    high_risk_context: bool = False,
    payload_hash: str = "",
) -> OperatorSurfaceCheckResult:
    """Run the full operator surface guard: leak check + comedy gate.

    This is the primary entry point.  Returns a fully serialisable result.
    """
    leak = check_machine_contract_leak(text, audience=audience)
    comedy = check_comedy_gate(
        agent_role=agent_role,
        error_flags=error_flags,
        process_hung=process_hung,
        high_risk_context=high_risk_context,
        payload_hash=payload_hash,
    )
    return OperatorSurfaceCheckResult(
        safe_for_operator=not leak.is_leak,
        leak_check=leak,
        comedy_gate=comedy,
        schema_version=SCHEMA_VERSION,
        contract_status=CONTRACT_STATUS,
    )


def check_operator_surface_dict(
    text: str,
    *,
    agent_role: str = "OPENCLAW_SYSTEM",
    audience: str = "ELIWINSHIP",
    error_flags: int = 0,
    process_hung: bool = False,
    high_risk_context: bool = False,
    payload_hash: str = "",
) -> dict[str, Any]:
    """Dict-returning wrapper for JSON serialisation."""
    result = check_operator_surface(
        text,
        agent_role=agent_role,
        audience=audience,
        error_flags=error_flags,
        process_hung=process_hung,
        high_risk_context=high_risk_context,
        payload_hash=payload_hash,
    )
    return {
        "safe_for_operator": result.safe_for_operator,
        "schema_version": result.schema_version,
        "contract_status": result.contract_status,
        "leak_check": asdict(result.leak_check),
        "comedy_gate": asdict(result.comedy_gate),
    }


# ---------------------------------------------------------------------------
# Read-model export (follows the OpenClaw pattern)
# ---------------------------------------------------------------------------

def build_contract_read_model(generated_at: str = "2026-06-22T00:00:00+00:00") -> dict[str, Any]:
    """Export a machine-readable contract for the operator surface guard."""
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "operator_surface_guard",
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "doctrine_sources": [
            "master_voice.sh voice-layer leak guard (2026-06-22)",
            "agent_voice_response_layer.py constraint NO_JARGON_IN_ELIWINSHIP",
            "SYSTEM-READY-PERSONA-VOICE-COMEDY-PACKET-DOCTRINE.md Zero-Error Gate",
            "SYSTEM-READY-PERSONA-VOICE-COMEDY-PACKET-DOCTRINE.md Golden Ratio",
            "SYSTEM-READY-PERSONA-VOICE-COMEDY-PACKET-DOCTRINE.md Funny Ranking",
        ],
        "leak_detection_rules": {
            "json_structure_start": "text starts with { or [ = machine contract",
            "json_key_count": ">=2 JSON key patterns (\"key\":) = machine contract",
            "stack_trace": "Traceback (most recent call last) = machine contract",
            "receipt_field_pattern": "content_hash= / request_id= / source_request_id= / internal_status= = machine contract",
            "class_names_eliwinship": "OpenClaw* class names blocked in ELIWINSHIP audience",
            "absolute_paths_eliwinship": "absolute file paths blocked in ELIWINSHIP audience",
            "hash_strings_eliwinship": "hex hashes 16+ chars blocked in ELIWINSHIP audience",
        },
        "comedy_gate_rules": {
            "zero_error_gate": "error_flags>0 or process_hung → comedy_eligible=False (hard lock)",
            "high_risk_suppression": "high_risk_context=True → comedy_eligible=False",
            "rank_floor": f"agent humor rank must be >={COMEDY_RANK_FLOOR} (Guardian=0, locked)",
            "golden_ratio": f"base chance {int(COMEDY_BASE_CHANCE*100)}%, scaled by humor rank, seeded by payload_hash",
        },
        "funny_ranking": FUNNY_RANKING,
        "audience_modes": ["ELIWINSHIP", "TECHNICAL", "DEBUG"],
        "authority_boundary": {
            "tts_live_connection_performed": False,
            "message_send_performed": False,
            "external_action_performed": False,
            "comedy_model_call_performed": False,
            "comedy_external_action_performed": False,
        },
        "machine_proof": {
            "all_authority_false": True,
            "deterministic_pure_functions": True,
            "no_llm_calls": True,
            "no_external_io": True,
            "extends_master_voice_guard": True,
            "zero_error_gate_enforced": True,
            "golden_ratio_seeded_by_payload_hash": True,
        },
        "next_safe_move": (
            "Import operator_surface_guard and call check_operator_surface() before "
            "routing any agent reply to the operator surface or TTS pipeline."
        ),
    }
