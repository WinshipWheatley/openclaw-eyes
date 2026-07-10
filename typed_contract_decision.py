"""Fleet-wide typed contract decision layer.

This module is deliberately a *decision contract*, not a claim that OpenClaw has
one physical router.  Each live surface calls :func:`decide_contract` before its
own session/intake fallback and then renders or stages the returned typed action.

Safety invariants:

* deterministic refusal and authority tokens outrank every other label;
* specific business domains outrank generic conversational status;
* the optional semantic vote may select only non-authority labels;
* an uncertain vote at an active session boundary preserves the session without
  mutating or advancing it;
* deterministic answers are returned directly, so they never incur a second
  model call.

``interpreter_lm`` is intentionally not imported here.  It retains its separate
LM1 seat; this classifier uses the shared adaptive model/slot/fit-wall path only
when an adapter explicitly enables the optional vote.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping


SCHEMA_VERSION = "typed_contract_decision_v1"
SEMANTIC_VOTE_ENV = "OPENCLAW_CONTRACT_VOTE_ADAPTERS"
SEMANTIC_VOTE_TIMEOUT_ENV = "OPENCLAW_CONTRACT_VOTE_TIMEOUT_SECONDS"
DEFAULT_SEMANTIC_TIMEOUT_SECONDS = 5.0
SEMANTIC_CONFIDENCE_THRESHOLD = 0.72
_CASSANDRA_TELEGRAM_SURFACES = frozenset(
    {"telegram", "cassandra_telegram", "cassandra_brain.handle"}
)


class ContractLabel(str, Enum):
    REFUSAL = "refusal"
    AUTHORITY_TOKEN = "authority_token"
    PAYMENT_ARRIVAL = "payment_arrival"
    MONEY_READ = "money_read"
    FINALIZED_INVOICE_REVIEW = "finalized_invoice_review"
    STATUS = "status"
    IDENTITY = "identity"
    LOW_COHERENCE = "low_coherence"
    ROUTE_INSTRUCTION = "route_instruction"
    GUARDIAN_GATE_NARRATION = "guardian_gate_narration"
    SESSION_RELEVANT = "session_relevant"
    UNRESOLVED = "unresolved"


class DecisionAction(str, Enum):
    DIRECT_ANSWER = "direct_answer"
    PASS_THROUGH = "pass_through"
    STAGE_HANDOFF = "stage_handoff"
    CAPTURE_SESSION = "capture_session"
    PRESERVE_SESSION = "preserve_session"


@dataclass(frozen=True)
class ContractContext:
    agent: str
    surface: str
    source_message_id: str = ""
    active_session: bool = False
    session_kind: str = ""
    session_field: str = ""
    authority_pending: bool = False
    session_snapshot: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        # Never serialize arbitrary session values.  They may contain paths,
        # contact details, or draft content; receipts need shape, not payload.
        snapshot = self.session_snapshot if isinstance(self.session_snapshot, Mapping) else {}
        return {
            "agent": self.agent,
            "surface": self.surface,
            "source_message_id": self.source_message_id,
            "active_session": self.active_session,
            "session_kind": self.session_kind,
            "session_field": self.session_field,
            "authority_pending": self.authority_pending,
            "session_status": str(snapshot.get("status") or ""),
            "session_workflow": str(snapshot.get("active_workflow") or ""),
        }


@dataclass(frozen=True)
class ContractReceipt:
    decision_id: str
    label: str
    action: str
    precedence: int
    source: str
    reason: str
    model_called: bool
    semantic_vote_status: str
    confidence: float
    authority_granted: bool = False
    session_preserved: bool = False
    receipt_pointer: str = ""
    elapsed_ms: float = 0.0
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContractDecision:
    label: ContractLabel
    matches: tuple[ContractLabel, ...]
    action: DecisionAction
    reply: str | None
    context: ContractContext
    receipt: ContractReceipt

    @property
    def handled(self) -> bool:
        return self.action in {
            DecisionAction.DIRECT_ANSWER,
            DecisionAction.STAGE_HANDOFF,
            DecisionAction.PRESERVE_SESSION,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label.value,
            "matches": [label.value for label in self.matches],
            "action": self.action.value,
            "reply": self.reply,
            "context": self.context.to_dict(),
            "receipt": self.receipt.to_dict(),
        }


@dataclass(frozen=True)
class HandoffResult:
    reply: str
    receipt_pointer: str
    package_id: str


StatusRenderer = Callable[[], str]
HandoffStager = Callable[[str, ContractContext], HandoffResult]
AdaptiveCall = Callable[..., str]
SessionAnswerPredicate = Callable[[str], bool]


_AUTHORITY_CODE_RE = re.compile(
    r"^[A-Z0-9]{4}\s+(?:1|2|3|YES|NO|APPROVE|DENY)(?:\b|\s*-)", re.IGNORECASE
)
_PAYMENT_NOUN_RE = re.compile(r"\b(?:payment|check|cheque|deposit|paid|remittance)\b", re.IGNORECASE)
_PAYMENT_STATE_RE = re.compile(
    r"\b(?:arriv(?:e|ed)|come\s+through|came\s+through|clear(?:ed)?|land(?:ed)?|received|"
    r"show(?:ed)?\s+up|status|where\s+(?:is|are|does)|did\s+we\s+get|have\s+we\s+got)\b",
    re.IGNORECASE,
)
_INVOICE_RE = re.compile(r"\b(?:invoice|bill)\b", re.IGNORECASE)
_FINALIZED_REVIEW_RE = re.compile(
    r"\b(?:prep|prepare|get|make|surface|pull\s+up|show)\b.{0,90}"
    r"\b(?:ready|review|look\s+(?:it\s+)?over|final(?:ized)?)\b|"
    r"\b(?:ready|final(?:ized)?)\b.{0,60}\b(?:review|look\s+(?:it\s+)?over)\b",
    re.IGNORECASE,
)
_LIVE_ARTS_RE = re.compile(r"\blive\s+arts(?:\s+maryland)?\b", re.IGNORECASE)
_HANDOFF_RE = re.compile(
    r"\b(?:hand(?:off|\s+off|\s+it|\s+this)|route|stage|pass)\b|"
    r"\bget\s+(?:it|this)\s+(?:over\s+)?to\b|"
    r"\b(?:right\s+agent|which\s+agent|out\s+the\s+door|needs?\s+to\s+(?:go\s+out|be\s+handled))\b",
    re.IGNORECASE,
)
_ADVISORY_SEND_RE = re.compile(
    r"^\s*(?:should|could|would)\s+i\b|\b(?:is\s+it\s+safe|do\s+you\s+think)\b",
    re.IGNORECASE,
)
_CASSANDRA_NUDGE_RE = re.compile(
    r"\b(?:draft|write|prepare|stage)\b.{0,100}\b(?:nudge|follow[- ]?up|reminder)\b|"
    r"\b(?:nudge|follow[- ]?up|reminder)\b.{0,100}\b(?:biggest|largest|whoever|who\s+owes|outstanding)\b",
    re.IGNORECASE,
)
_GUARDIAN_NARRATION_RE = re.compile(
    r"(?:walk\s+me\s+through|explain|what\s+happens|how\s+(?:does|do)|safeguards?|gate\s+chain)"
    r".{0,180}(?:cassandra|clara).{0,100}(?:send|invoice)|"
    r"(?:cassandra|clara).{0,100}(?:send|invoice).{0,180}(?:approval|guard|lock|happen)",
    re.IGNORECASE | re.DOTALL,
)
_STATUS_PATTERNS = (
    re.compile(r"\b(?:status|state|posture)\b", re.IGNORECASE),
    re.compile(r"\bhow\s+(?:are|is).{0,35}(?:things|everything|your\s+(?:end|side))\b", re.IGNORECASE),
    re.compile(r"\b(?:what(?:'s|\s+is)\s+happening|how\s+things\s+look|where\s+do\s+things\s+stand)\b", re.IGNORECASE),
    re.compile(r"\byou\s+good\b", re.IGNORECASE),
)
_IDENTITY_PATTERNS = (
    re.compile(r"\bwho\s+(?:are\s+you|am\s+i\s+(?:talking|speaking)\s+to)\b", re.IGNORECASE),
    re.compile(r"\bwhat(?:'s|\s+is)\s+your\s+(?:job|role|deal|purpose)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+(?:do|are)\s+you\s+(?:do|for)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+you(?:'re|\s+are)\s+(?:for|here\s+for)\b", re.IGNORECASE),
    re.compile(r"\bin\s+plain\s+english.{0,45}\b(?:your\s+role|what\s+you\s+do)\b", re.IGNORECASE),
)
_SAFE_VOTE_LABELS = frozenset(
    {
        ContractLabel.STATUS,
        ContractLabel.IDENTITY,
        ContractLabel.LOW_COHERENCE,
        ContractLabel.ROUTE_INSTRUCTION,
        ContractLabel.GUARDIAN_GATE_NARRATION,
        ContractLabel.SESSION_RELEVANT,
        ContractLabel.UNRESOLVED,
    }
)
_PRECEDENCE = {
    ContractLabel.REFUSAL: 0,
    ContractLabel.AUTHORITY_TOKEN: 0,
    ContractLabel.PAYMENT_ARRIVAL: 10,
    ContractLabel.MONEY_READ: 10,
    ContractLabel.FINALIZED_INVOICE_REVIEW: 10,
    ContractLabel.STATUS: 20,
    ContractLabel.IDENTITY: 20,
    ContractLabel.LOW_COHERENCE: 20,
    ContractLabel.ROUTE_INSTRUCTION: 20,
    ContractLabel.GUARDIAN_GATE_NARRATION: 20,
    ContractLabel.SESSION_RELEVANT: 30,
    ContractLabel.UNRESOLVED: 40,
}


def semantic_vote_enabled_for_adapter(
    adapter: str,
    *,
    default: bool = False,
    environ: Mapping[str, str] | None = None,
) -> bool:
    env = environ if environ is not None else os.environ
    if SEMANTIC_VOTE_ENV not in env:
        # Production defaults are chosen explicitly by each adapter.  Active
        # session boundaries pass default=True so uncertainty cannot fall back
        # to greedy legacy capture even when no deployment env is present.
        return bool(default)
    raw = str(env.get(SEMANTIC_VOTE_ENV, "") or "").strip().lower()
    if raw in {"", "0", "false", "off", "none", "disabled"}:
        return False
    selected = {
        item.strip().lower()
        for item in raw.split(",")
        if item.strip()
    }
    key = str(adapter or "").strip().lower()
    return "all" in selected or "*" in selected or key in selected


def semantic_vote_timeout_seconds(*, environ: Mapping[str, str] | None = None) -> float:
    env = environ if environ is not None else os.environ
    try:
        value = float(str(env.get(SEMANTIC_VOTE_TIMEOUT_ENV, "") or ""))
    except ValueError:
        return DEFAULT_SEMANTIC_TIMEOUT_SECONDS
    return value if 0 < value <= 10 else DEFAULT_SEMANTIC_TIMEOUT_SECONDS


def active_session_from_mapping(session: Mapping[str, Any] | None) -> bool:
    if not isinstance(session, Mapping) or not session:
        return False
    if str(session.get("status") or "").lower() in {"active", "paused", "waiting"}:
        return True
    if session.get("active") is True:
        return True
    return bool(
        session.get("active_workflow")
        or session.get("current_question_id")
        or session.get("pending_field")
        or session.get("pending_interaction")
    )


def surface_scope_matches(stored_surface: str, incoming_surface: str) -> bool:
    """Compare session surfaces while preserving real transport aliases.

    Cassandra's guided-review API stores ``telegram`` while the listener and
    direct brain adapter identify the same lane as ``cassandra_telegram`` and
    ``cassandra_brain.handle``.  Those are one channel; named foreign surfaces
    such as Maestro remain distinct.
    """

    stored = str(stored_surface or "").strip().lower()
    incoming = str(incoming_surface or "").strip().lower()
    if not stored or not incoming:
        return True
    if stored in _CASSANDRA_TELEGRAM_SURFACES:
        stored = "cassandra_telegram"
    if incoming in _CASSANDRA_TELEGRAM_SURFACES:
        incoming = "cassandra_telegram"
    return stored == incoming


def _normalize(text: str) -> str:
    return " ".join(str(text or "").strip().replace("’", "'").split())


def _decision_id(text: str, context: ContractContext, label: ContractLabel) -> str:
    material = "\u241f".join(
        (
            context.agent,
            context.surface,
            context.source_message_id,
            label.value,
            _normalize(text).lower(),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]
    # Segmented opaque ID stays deterministic/correlatable without presenting
    # a long raw hash that the operator-surface leak guard correctly blocks.
    return "contract:" + "-".join(digest[index : index + 4] for index in range(0, 20, 4))


def _receipt(
    *,
    text: str,
    context: ContractContext,
    label: ContractLabel,
    action: DecisionAction,
    source: str,
    reason: str,
    model_called: bool,
    vote_status: str = "not_requested",
    confidence: float = 1.0,
    session_preserved: bool = False,
    receipt_pointer: str = "",
    started: float,
) -> ContractReceipt:
    return ContractReceipt(
        decision_id=_decision_id(text, context, label),
        label=label.value,
        action=action.value,
        precedence=_PRECEDENCE[label],
        source=source,
        reason=reason,
        model_called=model_called,
        semantic_vote_status=vote_status,
        confidence=confidence,
        authority_granted=False,
        session_preserved=session_preserved,
        receipt_pointer=receipt_pointer,
        elapsed_ms=round((time.monotonic() - started) * 1000.0, 3),
    )


def _make_decision(
    *,
    text: str,
    context: ContractContext,
    label: ContractLabel,
    matches: tuple[ContractLabel, ...] | None = None,
    action: DecisionAction,
    reply: str | None,
    source: str,
    reason: str,
    model_called: bool,
    vote_status: str = "not_requested",
    confidence: float = 1.0,
    session_preserved: bool = False,
    receipt_pointer: str = "",
    started: float,
) -> ContractDecision:
    return ContractDecision(
        label=label,
        matches=matches or (label,),
        action=action,
        reply=reply,
        context=context,
        receipt=_receipt(
            text=text,
            context=context,
            label=label,
            action=action,
            source=source,
            reason=reason,
            model_called=model_called,
            vote_status=vote_status,
            confidence=confidence,
            session_preserved=session_preserved,
            receipt_pointer=receipt_pointer,
            started=started,
        ),
    )


def _refusal_reply(text: str, context: ContractContext) -> str | None:
    try:
        from operator_refusal_guard import refusal_reply_for_text

        return refusal_reply_for_text(text, agent=context.agent, surface=context.surface)
    except Exception:
        return None


def _is_authority_token(text: str, context: ContractContext) -> bool:
    normalized = _normalize(text)
    if _AUTHORITY_CODE_RE.match(normalized):
        return True
    return context.authority_pending and normalized.upper() in {
        "1",
        "2",
        "3",
        "YES",
        "NO",
        "APPROVE",
        "DENY",
    }


def _is_payment_arrival(text: str) -> bool:
    normalized = _normalize(text)
    if _PAYMENT_NOUN_RE.search(normalized) and _PAYMENT_STATE_RE.search(normalized):
        return True
    # Invoice state/status belongs to the invoice/payment domain even when it
    # is phrased as a read or mutation.  This branch intentionally delegates;
    # the generic fleet-status renderer must never answer about an invoice.
    return bool(
        re.search(r"\b(?:status|state)\b", normalized, re.IGNORECASE)
        and _INVOICE_RE.search(normalized)
    )


def _is_money_read(text: str) -> bool:
    try:
        from money_truth import classify_money_question

        if classify_money_question(text) == "money_read":
            return True
    except Exception:
        pass
    normalized = _normalize(text).lower()
    return bool(
        re.search(r"\b(?:who|what|how\s+much|which).{0,70}\b(?:owe|owed|outstanding|receivable|invoice balance)\b", normalized)
        or re.search(r"\b(?:money|receivables?|invoices?).{0,45}\b(?:owed|outstanding|due)\b", normalized)
    )


def _is_finalized_invoice_review(text: str) -> bool:
    normalized = _normalize(text)
    return bool(_INVOICE_RE.search(normalized) and _FINALIZED_REVIEW_RE.search(normalized))


def _is_identity(text: str) -> bool:
    try:
        from protected_generate import is_identity_question

        if is_identity_question(text):
            return True
    except Exception:
        pass
    return any(pattern.search(text) for pattern in _IDENTITY_PATTERNS)


def _low_coherence_candidate(text: str) -> str:
    # Human wrappers around a quoted/noisy payload are grammatical; classify the
    # payload, not the polite scaffolding (the live regression sentinel).
    quoted = re.findall(r'["“](.*?)["”]', str(text or ""))
    if quoted:
        return max(quoted, key=len)
    wrapper = re.search(
        r"(?:what\s+do\s+you\s+make\s+of|make\s+sense\s+of|decode|interpret)\s+(.+?)[?!\.]*$",
        str(text or ""),
        re.IGNORECASE,
    )
    return wrapper.group(1) if wrapper else str(text or "")


def _is_low_coherence(text: str) -> bool:
    candidate = _low_coherence_candidate(text)
    words = re.findall(r"[a-z']+", candidate.lower())
    # The generic coherence guard can reject short but perfectly grammatical
    # policy answers (live example: "Direct deposit stays manual approval
    # only.").  Require it to respect a compact relational/action grammar;
    # keyword-shaped nonsense such as "blorp fizzle invoice quantum" still
    # has no such connective and remains low-coherence.
    if len(words) >= 4 and any(
        word in {
            "am",
            "are",
            "can",
            "does",
            "is",
            "keep",
            "keeps",
            "manual",
            "only",
            "should",
            "stay",
            "stays",
            "was",
            "were",
            "will",
        }
        for word in words
    ):
        return False
    try:
        from protected_generate import is_low_coherence_text

        return bool(is_low_coherence_text(candidate))
    except Exception:
        return len(words) >= 3 and sum(len(word) >= 6 for word in words) >= 2


def _is_live_arts_route(text: str) -> bool:
    normalized = _normalize(text)
    if not (_LIVE_ARTS_RE.search(normalized) and _INVOICE_RE.search(normalized)):
        return False
    if _is_finalized_invoice_review(normalized):
        return False
    if _ADVISORY_SEND_RE.search(normalized):
        return False
    return bool(_HANDOFF_RE.search(normalized))


def _is_cassandra_nudge_route(text: str) -> bool:
    normalized = _normalize(text)
    return bool(
        _CASSANDRA_NUDGE_RE.search(normalized)
        and re.search(r"\b(?:biggest|largest|whoever|who\s+owes|outstanding)\b", normalized, re.IGNORECASE)
    )


def _is_guardian_narration(text: str) -> bool:
    return bool(_GUARDIAN_NARRATION_RE.search(_normalize(text)))


def _is_status(text: str) -> bool:
    normalized = _normalize(text)
    # "Status" is overloaded.  Business-object state belongs to its domain,
    # and status mutations belong to the existing action/authority paths.
    if re.search(
        r"\b(?:invoice|bill|billing|payment|check|cheque|deposit|remittance|receivable|ledger)\b",
        normalized,
        re.IGNORECASE,
    ):
        return False
    if re.match(r"^\s*(?:update|set|change|mark|move)\b", normalized, re.IGNORECASE):
        return False
    return any(pattern.search(normalized) for pattern in _STATUS_PATTERNS)


def _identity_reply(agent: str) -> str:
    try:
        from protected_generate import identity_persona_reply

        return str(identity_persona_reply(agent))
    except Exception:
        return f"I'm {agent.title()}, the {agent.title()} lane in OpenClaw."


def _low_coherence_reply(agent: str) -> str:
    try:
        from protected_generate import low_coherence_reply_line

        return str(low_coherence_reply_line(agent))
    except Exception:
        return "I can't make a reliable request out of that yet. Say it another way and I’ll take another pass."


def guardian_gate_narration_reply() -> str:
    return (
        "There are two separate gates. First, Cassandra asks for up-front Guardian approval on the exact invoice "
        "and proposed recipient; that approval only authorizes a reviewed attempt. The dispatch-time SEND_HOLD "
        "check then runs again and enforces the recipient lock before any delivery can leave the system. If either "
        "layer is missing or mismatched, the send stays blocked. Nothing was sent or authorized by this explanation."
    )


def _render_money_read(agent: str, text: str) -> str:
    try:
        from money_truth import render_money_answer

        answer = str(render_money_answer(agent, question=text))
        if str(agent or "").lower() == "niles":
            try:
                from money_truth import route_line

                return f"{route_line('niles')} {answer}".strip()
            except Exception:
                pass
        return answer
    except TypeError:
        try:
            return str(render_money_answer(agent))
        except Exception:
            pass
    except Exception:
        pass
    return "The shared receivables read-model is unavailable right now. I am not claiming the balance is zero."


def _preserve_reply(context: ContractContext) -> str:
    kind = context.session_kind.replace("_", " ").strip() or "workflow"
    return (
        f"I’m not confident that answers the open {kind} step, so I left the open {kind} step unchanged. "
        "Rephrase the answer, or explicitly ask to leave that workflow."
    )


def _preserve_reply_with_receipt(text: str, context: ContractContext) -> tuple[str, str]:
    pointer = _decision_id(text, context, ContractLabel.UNRESOLVED)
    return f"{_preserve_reply(context)} Receipt: {pointer}.", pointer


def preserve_session_on_error(
    text: str,
    *,
    context: ContractContext,
    error_type: str = "ContractError",
) -> ContractDecision:
    """Fail closed at an already-known active session boundary.

    Adapters use this only after they have established that a session is active
    and the contract machinery itself raises.  The receipt exposes no raw text,
    exception detail, path, or credential.
    """

    started = time.monotonic()
    decision_id = _decision_id(text, context, ContractLabel.UNRESOLVED)
    reply = f"{_preserve_reply(context)} Receipt: {decision_id}."
    return _make_decision(
        text=text,
        context=context,
        label=ContractLabel.UNRESOLVED,
        action=DecisionAction.PRESERVE_SESSION,
        reply=reply,
        source="adapter_error",
        reason=f"active_session_contract_error:{error_type}",
        model_called=False,
        vote_status="error_preserved",
        confidence=0.0,
        session_preserved=True,
        receipt_pointer=decision_id,
        started=started,
    )


def _semantic_prompt(text: str, context: ContractContext) -> str:
    labels = ", ".join(
        label.value
        for label in (
            ContractLabel.STATUS,
            ContractLabel.IDENTITY,
            ContractLabel.LOW_COHERENCE,
            ContractLabel.ROUTE_INSTRUCTION,
            ContractLabel.GUARDIAN_GATE_NARRATION,
            ContractLabel.SESSION_RELEVANT,
            ContractLabel.UNRESOLVED,
        )
    )
    return (
        "Classify a non-authority conversational message. Return exactly one JSON object and no prose: "
        '{"label":"<label>","confidence":0.0,"session_relevant":false}. '
        f"Allowed labels only: {labels}. Never infer, grant, or describe an approval, authorization, send, delete, "
        "payment, or money-movement decision. A route_instruction label identifies a request to stage/handoff work; "
        "it does not authorize execution.\n"
        f"Agent: {context.agent}\nSurface: {context.surface}\n"
        f"Active session: {str(context.active_session).lower()}\nSession kind: {context.session_kind or 'none'}\n"
        f"Message: {text}"
    )


def _parse_semantic_vote(raw: str) -> tuple[ContractLabel, float, bool] | None:
    try:
        payload = json.loads(str(raw or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or set(payload) != {"label", "confidence", "session_relevant"}:
        return None
    try:
        label = ContractLabel(str(payload["label"]))
        confidence = float(payload["confidence"])
    except (TypeError, ValueError):
        return None
    if label not in _SAFE_VOTE_LABELS or not (0.0 <= confidence <= 1.0):
        return None
    if not isinstance(payload["session_relevant"], bool):
        return None
    if label is ContractLabel.SESSION_RELEVANT and payload["session_relevant"] is not True:
        return None
    return label, confidence, bool(payload["session_relevant"])


def _call_semantic_vote(
    text: str,
    context: ContractContext,
    *,
    adaptive_call_fn: AdaptiveCall | None,
    timeout_seconds: float,
) -> tuple[tuple[ContractLabel, float, bool] | None, str]:
    if adaptive_call_fn is None:
        from adaptive_model_call import adaptive_model_call as adaptive_call_fn

    # One end-to-end budget split between slot contention and model work.  The
    # prior same-value/same-value shape could consume roughly 2x the advertised
    # timeout (5s waiting + 5s model).  Default 5s is now 2s slot + 3s model.
    slot_wait_seconds = min(2.0, max(0.001, timeout_seconds * 0.4))
    model_timeout_seconds = max(0.001, timeout_seconds - slot_wait_seconds)
    try:
        raw = adaptive_call_fn(
            _semantic_prompt(text, context),
            task_class="contract_semantic_vote",
            lane="frontdoor",
            timeout=model_timeout_seconds,
            attempts=1,
            think=False,
            num_predict=80,
            retry=False,
            model_slot_max_wait_seconds=slot_wait_seconds,
        )
    except Exception as exc:
        return None, f"error:{type(exc).__name__}"
    parsed = _parse_semantic_vote(str(raw or ""))
    if parsed is None:
        return None, "timeout_or_invalid" if not str(raw or "").strip() else "invalid"
    if parsed[1] < SEMANTIC_CONFIDENCE_THRESHOLD:
        return None, "below_threshold"
    return parsed, "accepted"


def _render_label(
    label: ContractLabel,
    *,
    text: str,
    context: ContractContext,
    status_renderer: StatusRenderer | None,
    handoff_stager: HandoffStager | None,
) -> tuple[DecisionAction, str | None, str, str]:
    if label is ContractLabel.MONEY_READ:
        return DecisionAction.DIRECT_ANSWER, _render_money_read(context.agent, text), "money_truth_direct", ""
    if label is ContractLabel.STATUS:
        if status_renderer is None:
            if context.active_session:
                reply, pointer = _preserve_reply_with_receipt(text, context)
                return DecisionAction.PRESERVE_SESSION, reply, "status_renderer_not_bound_preserved", pointer
            return DecisionAction.PASS_THROUGH, None, "status_renderer_not_bound", ""
        try:
            reply = str(status_renderer() or "").strip()
        except Exception as exc:
            if context.active_session:
                preserved, pointer = _preserve_reply_with_receipt(text, context)
                return (
                    DecisionAction.PRESERVE_SESSION,
                    preserved,
                    f"status_renderer_error_preserved:{type(exc).__name__}",
                    pointer,
                )
            reply = ""
        if not reply:
            if context.active_session:
                preserved, pointer = _preserve_reply_with_receipt(text, context)
                return DecisionAction.PRESERVE_SESSION, preserved, "status_renderer_empty_preserved", pointer
            return DecisionAction.PASS_THROUGH, None, "status_renderer_unavailable", ""
        return DecisionAction.DIRECT_ANSWER, reply, "status_renderer", ""
    if label is ContractLabel.IDENTITY:
        return DecisionAction.DIRECT_ANSWER, _identity_reply(context.agent), "persona_core", ""
    if label is ContractLabel.LOW_COHERENCE:
        return DecisionAction.DIRECT_ANSWER, _low_coherence_reply(context.agent), "coherence_guard", ""
    if label is ContractLabel.GUARDIAN_GATE_NARRATION:
        return DecisionAction.DIRECT_ANSWER, guardian_gate_narration_reply(), "two_layer_gate_renderer", ""
    if label is ContractLabel.ROUTE_INSTRUCTION:
        if handoff_stager is None:
            if context.active_session:
                preserved, pointer = _preserve_reply_with_receipt(text, context)
                return DecisionAction.PRESERVE_SESSION, preserved, "handoff_stager_not_bound_preserved", pointer
            return DecisionAction.PASS_THROUGH, None, "handoff_stager_not_bound", ""
        try:
            staged = handoff_stager(text, context)
        except Exception as exc:
            if context.active_session:
                preserved, pointer = _preserve_reply_with_receipt(text, context)
                return (
                    DecisionAction.PRESERVE_SESSION,
                    preserved,
                    f"handoff_stage_error_preserved:{type(exc).__name__}",
                    pointer,
                )
            return (
                DecisionAction.DIRECT_ANSWER,
                "I couldn't stage the Cassandra handoff. Nothing was sent, posted, or changed.",
                f"handoff_stage_error:{type(exc).__name__}",
                "",
            )
        return DecisionAction.STAGE_HANDOFF, staged.reply, "bounded_handoff_staged", staged.receipt_pointer
    if label is ContractLabel.SESSION_RELEVANT:
        return DecisionAction.CAPTURE_SESSION, None, "session_answer", ""
    return DecisionAction.PASS_THROUGH, None, "current_router_fallback", ""


def decide_contract(
    text: str,
    *,
    context: ContractContext,
    status_renderer: StatusRenderer | None = None,
    handoff_stager: HandoffStager | None = None,
    semantic_vote_enabled: bool = False,
    adaptive_call_fn: AdaptiveCall | None = None,
    semantic_timeout_seconds: float | None = None,
    session_answer_predicate: SessionAnswerPredicate | None = None,
) -> ContractDecision:
    """Return one explicit contract decision without mutating caller state."""

    started = time.monotonic()
    raw = str(text or "")

    refusal = _refusal_reply(raw, context)
    if refusal is not None:
        return _make_decision(
            text=raw,
            context=context,
            label=ContractLabel.REFUSAL,
            action=DecisionAction.DIRECT_ANSWER,
            reply=refusal,
            source="deterministic",
            reason="operator_refusal_guard",
            model_called=False,
            started=started,
        )

    if _is_authority_token(raw, context):
        return _make_decision(
            text=raw,
            context=context,
            label=ContractLabel.AUTHORITY_TOKEN,
            action=DecisionAction.PASS_THROUGH,
            reply=None,
            source="deterministic",
            reason="authority_parser_owns_token",
            model_called=False,
            started=started,
        )

    # Collect ordered matches rather than discarding a safe second clause.  The
    # primary label remains the highest-precedence match, while ``matches`` is
    # the explicit compound contract consumed by adapters and receipts.
    domain_matches: list[ContractLabel] = []
    if _is_payment_arrival(raw):
        domain_matches.append(ContractLabel.PAYMENT_ARRIVAL)
    if _is_money_read(raw):
        domain_matches.append(ContractLabel.MONEY_READ)
    if _is_finalized_invoice_review(raw):
        domain_matches.append(ContractLabel.FINALIZED_INVOICE_REVIEW)

    safe_matches: list[ContractLabel] = []
    # Low coherence dominates keyword-shaped safe matches: "invoice" inside
    # nonsense is not a route/status instruction.  Refusal/authority were
    # already resolved above, and specific domains require coherent shapes.
    _identity_match = _is_identity(raw)
    if _is_low_coherence(raw) and not _identity_match:
        safe_matches.append(ContractLabel.LOW_COHERENCE)
    else:
        # Short, legitimate identity asks (for example "introduce yourself")
        # can look low-coherence to a generic gibberish heuristic.  Identity is
        # the more specific safe contract and must win that collision, while a
        # real status+identity compound still retains both safe clauses.
        if _is_status(raw):
            safe_matches.append(ContractLabel.STATUS)
        if _identity_match:
            safe_matches.append(ContractLabel.IDENTITY)
        if _is_live_arts_route(raw) or _is_cassandra_nudge_route(raw):
            safe_matches.append(ContractLabel.ROUTE_INSTRUCTION)
        if _is_guardian_narration(raw):
            safe_matches.append(ContractLabel.GUARDIAN_GATE_NARRATION)

    ordered_matches = tuple(domain_matches + safe_matches)
    if ordered_matches:
        # Payment-arrival and finalized-artifact handling belong to their
        # domain adapters (155 and 152 respectively).  Preserve every matched
        # clause in the receipt, but do not absorb those production seams here.
        delegated = {
            ContractLabel.PAYMENT_ARRIVAL,
            ContractLabel.FINALIZED_INVOICE_REVIEW,
        }
        if any(label in delegated for label in domain_matches):
            primary = domain_matches[0]
            if len(domain_matches) > 1:
                reason = "compound_specific_domain_adapter_sequence"
            elif primary is ContractLabel.PAYMENT_ARRIVAL:
                reason = "specific_payment_arrival_route"
            else:
                reason = "finalized_artifact_adapter_owns_route"
            return _make_decision(
                text=raw,
                context=context,
                label=primary,
                matches=ordered_matches,
                action=DecisionAction.PASS_THROUGH,
                reply=None,
                source="deterministic",
                reason=reason,
                model_called=False,
                started=started,
            )

        replies: list[str] = []
        reasons: list[str] = []
        pointer = ""
        aggregate_action = DecisionAction.PASS_THROUGH
        for label in ordered_matches:
            action, clause_reply, clause_reason, clause_pointer = _render_label(
                label,
                text=raw,
                context=context,
                status_renderer=status_renderer,
                handoff_stager=handoff_stager,
            )
            reasons.append(f"{label.value}:{clause_reason}")
            if clause_reply and clause_reply not in replies:
                replies.append(clause_reply)
            if clause_pointer:
                pointer = clause_pointer
            if action is DecisionAction.STAGE_HANDOFF:
                aggregate_action = DecisionAction.STAGE_HANDOFF
            elif action is DecisionAction.PRESERVE_SESSION:
                aggregate_action = DecisionAction.PRESERVE_SESSION
                # An unavailable deterministic renderer at an active boundary
                # is uncertainty.  Preserve immediately; do not let a later
                # clause reopen legacy capture or model work.
                break
            elif action is DecisionAction.DIRECT_ANSWER and aggregate_action is DecisionAction.PASS_THROUGH:
                aggregate_action = DecisionAction.DIRECT_ANSWER
        return _make_decision(
            text=raw,
            context=context,
            label=ordered_matches[0],
            matches=ordered_matches,
            action=aggregate_action,
            reply="\n\n".join(replies) if replies else None,
            source="deterministic",
            reason=";".join(reasons),
            model_called=False,
            session_preserved=aggregate_action is DecisionAction.PRESERVE_SESSION,
            receipt_pointer=pointer,
            started=started,
        )

    if context.active_session and session_answer_predicate is not None:
        try:
            answers_pending = bool(session_answer_predicate(raw))
        except Exception:
            answers_pending = False
        if answers_pending:
            return _make_decision(
                text=raw,
                context=context,
                label=ContractLabel.SESSION_RELEVANT,
                action=DecisionAction.CAPTURE_SESSION,
                reply=None,
                source="deterministic",
                reason="session_answer_predicate",
                model_called=False,
                started=started,
            )

    if semantic_vote_enabled:
        timeout = semantic_timeout_seconds if semantic_timeout_seconds is not None else semantic_vote_timeout_seconds()
        parsed, vote_status = _call_semantic_vote(
            raw,
            context,
            adaptive_call_fn=adaptive_call_fn,
            timeout_seconds=timeout,
        )
        if parsed is not None:
            label, confidence, session_relevant = parsed
            if label is ContractLabel.SESSION_RELEVANT and not context.active_session:
                parsed = None
                vote_status = "session_label_without_session"
            elif label is ContractLabel.UNRESOLVED:
                # An explicit model uncertainty is still uncertainty.  At an
                # active session boundary that means PRESERVE, never greedy
                # pass-through/capture.
                parsed = None
                vote_status = "accepted_unresolved"
            else:
                action, reply, reason, pointer = _render_label(
                    label,
                    text=raw,
                    context=context,
                    status_renderer=status_renderer,
                    handoff_stager=handoff_stager,
                )
                return _make_decision(
                    text=raw,
                    context=context,
                    label=label,
                    action=action,
                    reply=reply,
                    source="semantic_vote",
                    reason=reason,
                    model_called=True,
                    vote_status=vote_status,
                    confidence=confidence,
                    session_preserved=action is DecisionAction.PRESERVE_SESSION,
                    receipt_pointer=pointer,
                    started=started,
                )

        if context.active_session:
            _preserve_pointer = _decision_id(raw, context, ContractLabel.UNRESOLVED)
            return _make_decision(
                text=raw,
                context=context,
                label=ContractLabel.UNRESOLVED,
                action=DecisionAction.PRESERVE_SESSION,
                reply=f"{_preserve_reply(context)} Receipt: {_preserve_pointer}.",
                source="semantic_vote",
                reason="uncertain_active_session_preserved",
                model_called=True,
                vote_status=vote_status,
                confidence=0.0,
                session_preserved=True,
                receipt_pointer=_preserve_pointer,
                started=started,
            )
        return _make_decision(
            text=raw,
            context=context,
            label=ContractLabel.UNRESOLVED,
            action=DecisionAction.PASS_THROUGH,
            reply=None,
            source="semantic_vote",
            reason="uncertain_outside_session_fail_open",
            model_called=True,
            vote_status=vote_status,
            confidence=0.0,
            started=started,
        )

    if context.active_session:
        pointer = _decision_id(raw, context, ContractLabel.UNRESOLVED)
        return _make_decision(
            text=raw,
            context=context,
            label=ContractLabel.UNRESOLVED,
            action=DecisionAction.PRESERVE_SESSION,
            reply=f"{_preserve_reply(context)} Receipt: {pointer}.",
            source="fallback",
            reason="optional_vote_disabled_active_session_preserved",
            model_called=False,
            vote_status="disabled",
            confidence=0.0,
            session_preserved=True,
            receipt_pointer=pointer,
            started=started,
        )

    return _make_decision(
        text=raw,
        context=context,
        label=ContractLabel.UNRESOLVED,
        action=DecisionAction.PASS_THROUGH,
        reply=None,
        source="fallback",
        reason="optional_vote_disabled",
        model_called=False,
        vote_status="disabled",
        confidence=0.0,
        started=started,
    )


__all__ = [
    "ContractContext",
    "ContractDecision",
    "ContractLabel",
    "ContractReceipt",
    "DecisionAction",
    "HandoffResult",
    "active_session_from_mapping",
    "decide_contract",
    "guardian_gate_narration_reply",
    "preserve_session_on_error",
    "semantic_vote_enabled_for_adapter",
    "semantic_vote_timeout_seconds",
    "surface_scope_matches",
]
