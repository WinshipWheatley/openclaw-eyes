"""Shared refusal-first guard for every OpenClaw agent pipeline (task 141).

ONE module, tapped at all six pipelines' FIRST touch point — before any model
call, intake, clarify session, or staging. Three refusal classes:

- money_movement   : money-movement verbs (send/pay/transfer/...) + an amount
- destructive_scope: destructive verbs (delete/wipe/reset/purge/...) + scope
                     words naming real committed/external state
- gate_bypass      : blanket approvals, dispatch-all, disable/skip/bypass gate

Doctrine (Operator/to-codex/141-refusal-first-fleetwide.md):
- Telegram remains an untrusted surface: it can request, never authorize.
- Refusals are instant (deterministic text, no model, no timeout possible),
  render in the agent's own voice, name the gate and the legitimate path, and
  log a refusal receipt.
- Blast-radius guard-rails: destructive matching requires object-scope, never
  verb-alone. Delete/wipe/reset against an agent's own ephemeral, in-domain
  surface (an unsent draft, a console scene/session/take) is normal handling
  and MUST NOT refuse — only verb + scope words naming committed/external
  state (financial records, logs, git branches, the console itself, approval
  queues, "everything") refuse here.

The reference refusal voice is Hermes' live denial ("cannot send messages,
trigger payments, or move money from this surface... can only be staged for an
operator-controlled review path... SEND_HOLD remains in force."). Each agent
renders the same doctrine in its own voice via packet_engine.PERSONA_CORES
when importable, else via the per-agent template dict below.

This module is deterministic and text-only: it never dispatches agents, sends
messages, moves money, mutates ledgers, or calls a model. Its only side effect
is an append-only refusal receipt (fail-open).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

GUARD_VERSION = "operator_refusal_guard_v1"
REFUSAL_INTENT = "operator_refusal_guard"
RECEIPT_TYPE = "operator_refusal_receipt"

DEFAULT_RECEIPT_PATH = Path(__file__).resolve().parent / "generated" / "receipts" / "operator_refusal_receipts.jsonl"
RECEIPT_PATH_ENV = "OPENCLAW_REFUSAL_RECEIPT_PATH"

REASON_MONEY = "money_movement"
REASON_DESTRUCTIVE = "destructive_scope"
REASON_GATE_BYPASS = "gate_bypass"

GATE_FOR_REASON = {
    REASON_MONEY: "SEND_HOLD + Guardian money gate",
    REASON_DESTRUCTIVE: "Guardian deletion gate + SEND_HOLD",
    REASON_GATE_BYPASS: "operator approval gate + SEND_HOLD",
}

# ── Persona source: packet_engine.PERSONA_CORES when importable ──────────────
try:  # pragma: no cover - exercised via reload in tests
    from packet_engine import PERSONA_CORES as _PERSONA_CORES  # type: ignore
    _PERSONA_SOURCE = "packet_engine:persona_core_registry"
except Exception:  # packet_engine is a gitignored runtime module; fail open
    _PERSONA_CORES = None
    _PERSONA_SOURCE = "operator_refusal_guard:template_dict"

if not isinstance(_PERSONA_CORES, Mapping):
    _PERSONA_CORES = None
    _PERSONA_SOURCE = "operator_refusal_guard:template_dict"


# ═════════════════════════════ classification ════════════════════════════════

def _normalize(text: str) -> str:
    return " ".join(str(text or "").lower().replace("’", "'").split())


# Money movement: an active verb that moves money PLUS an explicit amount.
_MONEY_VERB_RE = re.compile(
    r"\b(send|sends|sending|sent|pay|pays|paying|transfer|transfers|transferring|"
    r"wire|wires|wiring|zelle|venmo|paypal|remit|remits|disburse|disburses)\b"
)
_MONEY_AMOUNT_RE = re.compile(
    r"(\$\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?\s?(?:dollars|bucks|usd)\b)"
)
# Sending a DOCUMENT that mentions an amount (an invoice, a bill, a statement)
# is the normal staged workflow, not money movement — it must flow to the
# existing SEND_HOLD review path, never trip this guard.
_MONEY_DOCUMENT_OBJECT_RE = re.compile(
    r"\b(invoices?|bills?|quotes?|estimates?|statements?|receipts?|reminders?|nudges?|drafts?|work\s+logs?)\b"
)

# Destructive: verb + committed/external scope. Verb-alone never refuses.
_DESTRUCTIVE_VERB_RE = re.compile(
    r"\b(delete|deletes|deleting|wipe|wipes|wiping|erase|erases|erasing|"
    r"purge|purges|purging|reset|resets|resetting|destroy|destroys|destroying|"
    r"nuke|nukes|nuking)\b|\brm\s+-rf\b"
)
# Ephemeral, in-domain, reversible surfaces the agent operationally owns
# (unsent drafts, console scenes/sessions/takes, previews, test messages).
# These phrases are stripped BEFORE scope matching so "wipe the X32 scene"
# reads as scene-handling, while "wipe the X32" still names the console.
_EPHEMERAL_PHRASE_RE = re.compile(
    r"(?:\b(?:x-?32|console|board|mixer|desk|daw|the|that|this|these|those|my|our|"
    r"a|an|old|stale|latest|last|current|all|every|unsent|pending|staged|scratch|test)\s+)*"
    r"\b(?:drafts?|scenes?|sessions?|takes?|previews?|snapshots?|presets?|test\s+messages?)\b"
)
_DESTRUCTIVE_SCOPE_RE = re.compile(
    r"\b(invoices?|invoice\s+records?|financial\s+records?|finances|receivables?|"
    r"ledgers?|workbooks?|billing|records|receipts?|payments?|"
    r"logs?|log\s+files?|branch(?:es)?|git|repos?|repositor(?:y|ies)|"
    r"database(?:s)?|db|sqlite|tables?|"
    r"emails?|inbox|sent\s+mail|messages?|threads?|calendar|events?|contacts?|registry|"
    r"approvals?|approval\s+queue|gates?|"
    r"x-?32|console|board|mixer|mixing\s+desk|desk|scenes?|show\s+files?|snapshots?|patch(?:es)?\s+list|album|masters?|stems?|sessions?|takes?|"
    r"backups?|history|memory|state|everything|all\s+of\s+it|it\s+all)\b"
)

# Gate bypass: blanket approvals / dispatch-all / disabling or skipping gates.
_BLANKET_APPROVAL_RE = re.compile(
    r"\b(approve|approving|authorize|authorizing|green-?light|sign\s+off\s+on|"
    r"dispatch|dispatching)\b[^.!?\n]{0,60}?\b(everything|every\s+\w+|all\b|blanket|the\s+whole|entire)"
)
_AUTO_APPROVE_RE = re.compile(
    r"\b(auto-?approve|blanket\s+approvals?|pre-?approve|approve\s+by\s+default|"
    r"(?:stop|quit|don'?t)\s+asking\s+for\s+approval)\b"
)
_GATE_OFF_RE = re.compile(
    r"\b(disable|disabling|skip|skipping|bypass|bypassing|turn\s+off|shut\s+off|"
    r"lift|suspend|suspending|pause|pausing|ignore|ignoring|override|overriding|remove)\b"
    r"[^.!?\n]{0,60}?\b(gates?|guardrails?|approvals?|approval\s+gates?|"
    r"send[\s_-]?hold|review\s+path|safety\s+checks?|guardian)\b"
)


def _match_money_movement(normalized: str) -> tuple[str, ...]:
    verb = _MONEY_VERB_RE.search(normalized)
    amount = _MONEY_AMOUNT_RE.search(normalized)
    if not verb or not amount:
        return ()
    if _MONEY_DOCUMENT_OBJECT_RE.search(normalized):
        # "send the $1,095 invoice to Megan" = staged document workflow.
        return ()
    return (verb.group(0), amount.group(0))


def _match_destructive_scope(normalized: str) -> tuple[str, ...]:
    verb = _DESTRUCTIVE_VERB_RE.search(normalized)
    if not verb:
        return ()
    # Strip ephemeral in-domain objects first (guard-rail: object-scope, not
    # verb-alone; drafts/scenes/sessions/takes are normal handling).
    remainder = _EPHEMERAL_PHRASE_RE.sub(" ", normalized)
    scope = _DESTRUCTIVE_SCOPE_RE.search(remainder)
    if not scope:
        return ()
    return (verb.group(0), scope.group(0))


def _match_gate_bypass(normalized: str) -> tuple[str, ...]:
    for pattern in (_BLANKET_APPROVAL_RE, _AUTO_APPROVE_RE, _GATE_OFF_RE):
        found = pattern.search(normalized)
        if found:
            groups = tuple(g for g in found.groups() if g) or (found.group(0),)
            return tuple(str(g).strip() for g in groups)
    return ()


# ═════════════════════════════ voice templates ═══════════════════════════════
# Authored to match packet_engine.PERSONA_CORES voice charters. Hermes'
# money_movement entry is the verbatim live reference denial (the class #2
# template). These double as the fallback dict when packet_engine is absent.

REFUSAL_TEMPLATES: dict[str, dict[str, tuple[str, ...]]] = {
    "maestro": {
        REASON_MONEY: (
            "Not from here. Telegram can request, never authorize — and moving money is the hardest line we keep.",
            "Maestro cannot send, pay, or transfer money from this surface.",
            "A money move can only be staged for an operator-controlled review path, with Guardian on the gate and your explicit approval.",
            "No payment was staged and no money moved. SEND_HOLD remains in force.",
        ),
        REASON_DESTRUCTIVE: (
            "Stopping that one before it starts.",
            "Maestro cannot delete, wipe, or reset committed records from this surface.",
            "A destructive change can only be staged for an operator-controlled review path behind Guardian's deletion gate.",
            "Nothing was deleted or altered. SEND_HOLD remains in force.",
        ),
        REASON_GATE_BYPASS: (
            "That's a no — blanket approvals never run, on any surface.",
            "Maestro cannot approve everything, dispatch all, or switch off a gate from this surface.",
            "Each pending item needs its own explicit decision from you on the approval gate.",
            "Nothing was approved or dispatched. The approval gate holds and SEND_HOLD remains in force.",
        ),
    },
    "chief": {
        REASON_MONEY: (
            "No. That moves money, and money does not move from this channel.",
            "Chief cannot send, pay, or transfer funds from this surface.",
            "The bounded path: it gets staged for an operator-controlled review path with Guardian's approval on record.",
            "No money moved, no ledger touched, nothing staged. SEND_HOLD remains in force.",
        ),
        REASON_DESTRUCTIVE: (
            "No. That deletes committed state, and committed state stays put without a gate.",
            "Chief cannot delete, wipe, or reset records, logs, or branches from this surface.",
            "Destructive work goes through an operator-controlled review path behind Guardian's deletion gate — with a receipt.",
            "Nothing was deleted. SEND_HOLD remains in force.",
        ),
        REASON_GATE_BYPASS: (
            "No. Gates stay on — that is the whole point of gates.",
            "Chief cannot approve everything, dispatch all, or disable a gate from this surface.",
            "Every pending item takes its own explicit operator decision on the approval gate.",
            "Nothing was approved. The approval gate holds and SEND_HOLD remains in force.",
        ),
    },
    "cassandra": {
        REASON_MONEY: (
            "I have to decline this one — warmly, but firmly.",
            "Clara cannot send, pay, or transfer money from this surface; Cassandra's desk stages, it never spends.",
            "A payment can only be staged for an operator-controlled review path with Guardian's gate and your explicit approval.",
            "No payment was staged and no money moved. SEND_HOLD remains in force.",
        ),
        REASON_DESTRUCTIVE: (
            "I'm going to stop rather than run that one.",
            "Cassandra cannot delete invoices or any committed financial records from this surface — those are the books, not a draft.",
            "If records truly need to go, that flows through an operator-controlled review path behind Guardian's deletion gate.",
            "Nothing was deleted. Your records are exactly as they were, and SEND_HOLD remains in force.",
        ),
        REASON_GATE_BYPASS: (
            "I can't wave everything through — that's not a favor I'm able to do.",
            "Cassandra cannot blanket-approve, dispatch all, or set aside a gate from this surface.",
            "Each item earns its own explicit decision from you on the approval gate.",
            "Nothing was approved. The approval gate holds and SEND_HOLD remains in force.",
        ),
    },
    "niles": {
        REASON_MONEY: (
            "Hard stop on that one — money doesn't move from the studio chair.",
            "Niles cannot send, pay, or transfer money from this surface.",
            "It can only be staged for an operator-controlled review path with Guardian on the gate.",
            "No payment staged, nothing moved. SEND_HOLD remains in force.",
        ),
        REASON_DESTRUCTIVE: (
            "Hard stop — that erases real state, and we don't torch the rig from a text.",
            "Niles cannot wipe the console, delete records, or reset committed state from this surface.",
            "A full wipe or delete goes through an operator-controlled review path behind Guardian's deletion gate — scene and session housekeeping I can still do the normal way.",
            "Nothing was wiped. The desk is exactly as you left it, and SEND_HOLD remains in force.",
        ),
        REASON_GATE_BYPASS: (
            "Can't run the table like that — every cue gets called on its own.",
            "Niles cannot approve everything, dispatch all, or skip a gate from this surface.",
            "Each item takes its own explicit operator decision on the approval gate.",
            "Nothing was approved. The approval gate holds and SEND_HOLD remains in force.",
        ),
    },
    "guardian": {
        REASON_MONEY: (
            "No.",
            "Guardian does not move money, and this surface cannot authorize it — Telegram can request, never authorize.",
            "A payment can only be staged for an operator-controlled review path with an explicit operator approval on the money gate.",
            "No payment was staged and no money moved. SEND_HOLD remains in force.",
        ),
        REASON_DESTRUCTIVE: (
            "No.",
            "Guardian blocks deletion of committed records, logs, and branches from this surface, in plain English.",
            "Destructive changes require the operator-controlled review path through the deletion gate, with proof and explicit approval.",
            "Nothing was deleted. SEND_HOLD remains in force.",
        ),
        REASON_GATE_BYPASS: (
            "No. Blanket approvals never run.",
            "Guardian does not approve everything, dispatch all, or stand down a gate — this surface can request, never authorize.",
            "Each pending item requires its own explicit operator decision on the approval gate.",
            "Nothing was approved. The approval gate holds and SEND_HOLD remains in force.",
        ),
    },
    "hermes": {
        REASON_MONEY: (
            # Verbatim live reference denial — the class #2 template.
            "Hermes cannot send messages, trigger payments, or move money from this surface.",
            "This request is denied for live action and can only be staged for an operator-controlled review path.",
            "No external send, payment, ledger mutation, route receipt, service start, or agent dispatch occurred.",
            "SEND_HOLD remains in force.",
        ),
        REASON_DESTRUCTIVE: (
            "Denied. Hermes cannot delete, wipe, or reset system or business state from this surface.",
            "Destructive changes can only be staged for an operator-controlled review path behind Guardian's deletion gate.",
            "No deletion, mutation, or dispatch occurred.",
            "SEND_HOLD remains in force.",
        ),
        REASON_GATE_BYPASS: (
            "Denied. Hermes cannot approve items, bypass gates, or dispatch work from this surface.",
            "Approvals stay item-by-item on the operator-controlled review path — the approval gate does not lift from here.",
            "No approval, dispatch, or gate change occurred.",
            "SEND_HOLD remains in force.",
        ),
    },
}

# Neutral fallback for agents outside the six-core roster.
_GENERIC_TEMPLATES: dict[str, tuple[str, ...]] = {
    REASON_MONEY: (
        "OpenClaw cannot send, pay, or transfer money from this surface — Telegram can request, never authorize.",
        "A payment can only be staged for an operator-controlled review path with Guardian's approval.",
        "No payment was staged and no money moved. SEND_HOLD remains in force.",
    ),
    REASON_DESTRUCTIVE: (
        "OpenClaw cannot delete, wipe, or reset committed records from this surface.",
        "Destructive changes go through an operator-controlled review path behind Guardian's deletion gate.",
        "Nothing was deleted. SEND_HOLD remains in force.",
    ),
    REASON_GATE_BYPASS: (
        "OpenClaw cannot approve everything, dispatch all, or disable a gate from this surface.",
        "Each pending item requires its own explicit operator decision on the approval gate.",
        "Nothing was approved. SEND_HOLD remains in force.",
    ),
}


def _persona_core_for(agent: str) -> Mapping[str, Any] | None:
    if _PERSONA_CORES is None:
        return None
    core = _PERSONA_CORES.get(agent)
    return core if isinstance(core, Mapping) else None


def render_refusal_text(agent: str, reason_class: str) -> str:
    """Render the refusal in the agent's own voice.

    The per-agent templates are authored against packet_engine.PERSONA_CORES'
    voice charters (Hermes = the verbatim reference denial); when the persona
    registry is importable it is consulted so an agent outside the template
    dict but inside PERSONA_CORES still gets a named, non-generic close.
    """
    agent_key = str(agent or "").strip().lower()
    templates = REFUSAL_TEMPLATES.get(agent_key)
    if templates and reason_class in templates:
        return "\n".join(templates[reason_class])
    core = _persona_core_for(agent_key)
    lines = list(_GENERIC_TEMPLATES.get(reason_class, _GENERIC_TEMPLATES[REASON_GATE_BYPASS]))
    if core:
        display = str(core.get("agent") or agent_key).capitalize()
        lines = [line.replace("OpenClaw", display, 1) for line in lines]
    return "\n".join(lines)


# ═════════════════════════════ decision + receipts ═══════════════════════════


@dataclass(frozen=True)
class RefusalDecision:
    agent: str
    surface: str
    reason_class: str
    gate: str
    matched: tuple[str, ...]
    refusal_text: str
    receipt: dict[str, Any] = field(default_factory=dict)


def evaluate_operator_refusal(
    text: str,
    *,
    agent: str,
    surface: str = "",
) -> RefusalDecision | None:
    """Pure classification + rendering. No I/O, no model, instant.

    Returns None when the text is NOT a refusal-class ask (the normal
    pipeline continues untouched — fail-open by construction).
    """
    normalized = _normalize(text)
    if not normalized:
        return None

    matched: tuple[str, ...] = ()
    reason_class = ""
    for candidate_class, matcher in (
        (REASON_MONEY, _match_money_movement),
        (REASON_DESTRUCTIVE, _match_destructive_scope),
        (REASON_GATE_BYPASS, _match_gate_bypass),
    ):
        matched = matcher(normalized)
        if matched:
            reason_class = candidate_class
            break
    if not reason_class:
        return None

    agent_key = str(agent or "").strip().lower() or "unknown"
    gate = GATE_FOR_REASON[reason_class]
    refusal_text = render_refusal_text(agent_key, reason_class)
    receipt = {
        "receipt_type": RECEIPT_TYPE,
        "guard_version": GUARD_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "agent": agent_key,
        "surface": str(surface or ""),
        "reason_class": reason_class,
        "gate": gate,
        "matched": list(matched),
        "text_sha256": hashlib.sha256(str(text or "").encode("utf-8")).hexdigest(),
        "persona_source": _PERSONA_SOURCE,
        "model_called": False,
        "staged": False,
        "external_action_performed": False,
    }
    return RefusalDecision(
        agent=agent_key,
        surface=str(surface or ""),
        reason_class=reason_class,
        gate=gate,
        matched=matched,
        refusal_text=refusal_text,
        receipt=receipt,
    )


def _receipt_path() -> Path:
    override = os.environ.get(RECEIPT_PATH_ENV, "").strip()
    return Path(override) if override else DEFAULT_RECEIPT_PATH


def log_refusal_receipt(decision: RefusalDecision) -> Path | None:
    """Append-only JSONL refusal receipt. Fail-open: never raises."""
    try:
        path = _receipt_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(decision.receipt, ensure_ascii=True, sort_keys=True) + "\n")
        return path
    except Exception:
        return None


def refusal_reply_for_text(
    text: str,
    *,
    agent: str,
    surface: str = "",
) -> str | None:
    """The one-call pipeline tap: classify, render, receipt.

    Returns the agent-voiced refusal text, or None to let the normal pipeline
    continue. Never raises (a broken guard must not take a listener down).
    """
    try:
        decision = evaluate_operator_refusal(text, agent=agent, surface=surface)
    except Exception:
        return None
    if decision is None:
        return None
    log_refusal_receipt(decision)
    return decision.refusal_text
