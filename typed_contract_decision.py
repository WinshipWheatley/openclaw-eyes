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
import queue
import re
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping


SCHEMA_VERSION = "typed_contract_decision_v1"
SEMANTIC_VOTE_ENV = "OPENCLAW_CONTRACT_VOTE_ADAPTERS"
SEMANTIC_VOTE_TIMEOUT_ENV = "OPENCLAW_CONTRACT_VOTE_TIMEOUT_SECONDS"
CONTRACT_RECEIPT_DB_ENV = "OPENCLAW_CONTRACT_RECEIPT_DB"
DEFAULT_SEMANTIC_TIMEOUT_SECONDS = 5.0
SEMANTIC_CONFIDENCE_THRESHOLD = 0.72
MAX_CONTRACT_PRESERVE_RECEIPTS = 4096
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
    session_owner_handles_unknown: bool = False

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
    model_called: bool | None
    semantic_vote_status: str
    confidence: float
    model_call_status: str = ""
    authority_granted: bool = False
    session_preserved: bool = False
    receipt_pointer: str = ""
    receipt_persisted: bool = False
    receipt_persistence_status: str = "not_applicable"
    elapsed_ms: float = 0.0
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not self.model_call_status:
            payload.pop("model_call_status", None)
        return payload


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
    re.compile(r"\bwhat(?:'?s|\s+is)?\s+(?:ur|u\s*r)\s+(?:whole\s+)?(?:job|role|deal|thing|purpose)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+(?:it\s+is\s+)?you\s+(?:actually\s+)?(?:handle|cover|take\s+care\s+of)\b", re.IGNORECASE),
)
_IDENTITY_ASK_PREAMBLE_RE = re.compile(
    r"^\s*(?:(?:okay|ok|well|so|please|anyway|hey|hi|wait(?:\s+so)?|"
    r"hold\s+up|real\s+quick|by\s+the\s+way|btw)\b[\s,:;.!?—-]*)*"
    r"(?:(?:cassandra|clara|maestro|chief|guardian|niles|hermes)\b[\s,:;.!?—-]*)?",
    re.IGNORECASE,
)
_DIRECT_IDENTITY_ASK_RE = re.compile(
    r"^(?:"
    r"what(?:'?s|\s+is)\s+your\s+(?:name|job|role|deal|purpose)\b|"
    r"what\s+(?:do|are)\s+you\s+(?:do|for)\b|"
    r"what\s+you(?:'re|\s+are)\s+(?:for|here\s+for)\b|"
    r"what(?:'?s|\s+is)?\s+(?:ur|u\s*r)\s+(?:whole\s+)?"
    r"(?:job|role|deal|thing|purpose)\b|"
    r"are\s+you\s+(?:an?\s+)?(?:bot|ai|robot|human|person)\b|"
    r"are\s+you\s+real\b|what\s+kind\s+of\s+(?:assistant|bot)\b|"
    r"introduce\s+yourself\b|tell\s+me\s+about\s+yourself\b|"
    r"in\s+plain\s+english.{0,45}(?:your\s+role|what\s+you\s+do)\b"
    r")",
    re.IGNORECASE,
)
_DIRECT_WHO_IDENTITY_ASK_RE = re.compile(
    r"^who\s+(?:is\s+this|(?:(?:tf|the\s+heck|exactly|really)\s+)*are\s+you|"
    r"am\s+i\s+(?:(?:even|actually|exactly|really)\s+)*"
    r"(?:talking|speaking|chatting)\s+(?:to|with))"
    r"(?:\s*,?\s*(?:exactly|anyway|then|again|really|though|even))*\s*[?!.]*$",
    re.IGNORECASE,
)
_IDENTITY_REQUEST_LEAD_RE = re.compile(
    r"^(?:(?:tell|remind|explain)\s+me(?:\s+again)?|"
    r"(?:can|could|would)\s+you\s+(?:tell|remind|explain)\s+me|"
    r"walk\s+me\s+through)\s+",
    re.IGNORECASE,
)
_IDENTITY_MODAL_LEAD_RE = re.compile(
    r"^(?:can|could|would)\s+you\s+",
    re.IGNORECASE,
)
_IDENTITY_REQUEST_FILLER_RE = re.compile(
    r"^(?:(?:please|just|briefly|quickly|kindly)\s+)*",
    re.IGNORECASE,
)
_IDENTITY_HANDLE_CLAUSE_RE = re.compile(
    r"^what\s+(?:it\s+is\s+)?you\s+(?:actually\s+)?"
    r"(?:handle|cover|take\s+care\s+of)\b",
    re.IGNORECASE,
)
_IDENTITY_HANDLE_ALLOWED_TAIL_RE = re.compile(
    r"^\s*(?:(?:around\s+here|here|day[- ]to[- ]day)|"
    r"(?:for|in|on|within|at|as)\s+(?:me|us|you|"
    r"billing|payments?|invoices?|clients?|openclaw|cassandra|"
    r"this\s+(?:team|system|review|role)|the\s+(?:team|system)))?"
    r"(?:\s*,?\s*(?:exactly|anyway|again|really))*"
    r"(?:\s*,?\s*(?:if\s+anything|if\s+you\s+don'?t\s+mind|"
    r"because\s+i\s+forgot|please))?\s*[?!.]*$",
    re.IGNORECASE,
)
_TERMINAL_WHAT_ARE_YOU_RE = re.compile(
    r"^what\s+are\s+you(?:\s+(?:exactly|anyway|then|again|really|though))*\s*[?!.]*$",
    re.IGNORECASE,
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
        # Hermetic default under pytest: ten thousand legacy tests must never
        # depend on a live local model (2026-07-10 gate: default-ON turned
        # scripted wizard answers into preserve-session replies). Tests that
        # exercise the vote set OPENCLAW_CONTRACT_VOTE_ADAPTERS or pass the
        # enabled flag/fixtures explicitly. Production (no pytest) keeps the
        # adapter's explicit default.
        if "PYTEST_CURRENT_TEST" in env:
            return False
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
    model_called: bool | None,
    model_call_status: str | None = None,
    vote_status: str = "not_requested",
    confidence: float = 1.0,
    session_preserved: bool = False,
    receipt_pointer: str = "",
    started: float,
) -> ContractReceipt:
    decision_id = _decision_id(text, context, label)
    if action is DecisionAction.PRESERVE_SESSION and receipt_pointer.startswith("contract:"):
        # A preserve reply exposes ``receipt_pointer`` to the caller.  Keep the
        # durable primary key identical to that pointer even when the
        # deterministic label that failed was STATUS or ROUTE_INSTRUCTION.
        decision_id = receipt_pointer
    return ContractReceipt(
        decision_id=decision_id,
        label=label.value,
        action=action.value,
        precedence=_PRECEDENCE[label],
        source=source,
        reason=reason,
        model_called=model_called,
        semantic_vote_status=vote_status,
        confidence=confidence,
        model_call_status=model_call_status or "",
        authority_granted=False,
        session_preserved=session_preserved,
        receipt_pointer=receipt_pointer,
        elapsed_ms=round((time.monotonic() - started) * 1000.0, 3),
    )


def contract_receipt_db_path(*, environ: Mapping[str, str] | None = None) -> Path:
    """Return the token-free preserve-receipt sink path.

    Deployments may override the file location, while the default remains in
    the generated receipt tree and therefore outside source-controlled state.
    """

    env = environ if environ is not None else os.environ
    configured = str(env.get(CONTRACT_RECEIPT_DB_ENV, "") or "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parent / "generated" / "receipts" / "typed_contract_receipts.sqlite3"


def _ensure_contract_receipt_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS contract_preserve_receipts (
            decision_id TEXT PRIMARY KEY,
            schema_version TEXT NOT NULL,
            label TEXT NOT NULL,
            action TEXT NOT NULL CHECK (action = 'preserve_session'),
            precedence INTEGER NOT NULL,
            source TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            model_called INTEGER NOT NULL,
            semantic_vote_status TEXT NOT NULL,
            confidence REAL NOT NULL,
            created_at_epoch_ms INTEGER NOT NULL
        )
        """
    )


def _persist_contract_preserve_receipt(receipt: ContractReceipt) -> ContractReceipt:
    """Persist one bounded, idempotent preserve receipt without request data."""

    if (
        receipt.action != DecisionAction.PRESERVE_SESSION.value
        or not receipt.session_preserved
        or not receipt.receipt_pointer.startswith("contract:")
        or receipt.decision_id != receipt.receipt_pointer
    ):
        return receipt

    try:
        path = contract_receipt_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        desired_model_called = -1 if receipt.model_called is None else int(receipt.model_called)
        with sqlite3.connect(str(path), timeout=0.25) as connection:
            connection.execute("PRAGMA busy_timeout = 250")
            _ensure_contract_receipt_schema(connection)
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO contract_preserve_receipts (
                    decision_id,
                    schema_version,
                    label,
                    action,
                    precedence,
                    source,
                    reason_code,
                    model_called,
                    semantic_vote_status,
                    confidence,
                    created_at_epoch_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.decision_id,
                    receipt.schema_version,
                    receipt.label,
                    receipt.action,
                    receipt.precedence,
                    receipt.source,
                    receipt.reason,
                    desired_model_called,
                    receipt.semantic_vote_status,
                    receipt.confidence,
                    int(time.time() * 1000),
                ),
            )
            if cursor.rowcount == 1:
                status = "inserted"
            else:
                existing = connection.execute(
                    """
                    SELECT schema_version, label, action, precedence, source,
                           reason_code, model_called, semantic_vote_status, confidence
                    FROM contract_preserve_receipts
                    WHERE decision_id = ?
                    """,
                    (receipt.decision_id,),
                ).fetchone()
                desired_identity = (
                    receipt.schema_version,
                    receipt.label,
                    receipt.action,
                    receipt.precedence,
                    receipt.source,
                    receipt.reason,
                    receipt.semantic_vote_status,
                    receipt.confidence,
                )
                existing_identity = (
                    existing[0],
                    existing[1],
                    existing[2],
                    existing[3],
                    existing[4],
                    existing[5],
                    existing[7],
                    existing[8],
                ) if existing is not None else ()
                existing_model_called = existing[6] if existing is not None else None
                if existing_identity != desired_identity:
                    return replace(
                        receipt,
                        receipt_persisted=False,
                        receipt_persistence_status="conflict:receipt_identity_mismatch",
                    )
                if existing_model_called == desired_model_called:
                    status = "already_present"
                elif (
                    desired_model_called == -1
                    and existing_model_called == 0
                    and receipt.source == "adapter_error"
                    and receipt.semantic_vote_status.startswith("error_")
                ):
                    corrected = connection.execute(
                        """
                        UPDATE contract_preserve_receipts
                        SET model_called = -1
                        WHERE decision_id = ? AND model_called = 0
                        """,
                        (receipt.decision_id,),
                    )
                    if corrected.rowcount != 1:
                        return replace(
                            receipt,
                            receipt_persisted=False,
                            receipt_persistence_status="conflict:legacy_unknown_correction_failed",
                        )
                    status = "corrected_legacy_unknown"
                else:
                    return replace(
                        receipt,
                        receipt_persisted=False,
                        receipt_persistence_status="conflict:model_call_state_mismatch",
                    )
            # Keep the newest bounded set.  No message, token, session
            # snapshot, exception detail, or arbitrary context enters this
            # table; only the typed receipt fields above are retained.
            limit = max(1, int(MAX_CONTRACT_PRESERVE_RECEIPTS))
            connection.execute(
                """
                DELETE FROM contract_preserve_receipts
                WHERE rowid IN (
                    SELECT rowid
                    FROM contract_preserve_receipts
                    ORDER BY rowid DESC
                    LIMIT -1 OFFSET ?
                )
                """,
                (limit,),
            )
        return replace(receipt, receipt_persisted=True, receipt_persistence_status=status)
    except Exception as exc:
        # Preserve still fails closed if the evidence sink is unavailable; the
        # typed receipt exposes only the exception class, never its message.
        return replace(
            receipt,
            receipt_persisted=False,
            receipt_persistence_status=f"error:{type(exc).__name__}",
        )


def resolve_contract_receipt(
    decision_id: str,
    *,
    path: str | os.PathLike[str] | None = None,
) -> dict[str, Any] | None:
    """Resolve a durable preserve pointer without creating or mutating state."""

    pointer = str(decision_id or "")
    if not pointer.startswith("contract:"):
        return None
    db_path = Path(path) if path is not None else contract_receipt_db_path()
    if not db_path.is_file():
        return None
    try:
        with sqlite3.connect(str(db_path), timeout=0.25) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT decision_id, schema_version, label, action, precedence,
                       source, reason_code, model_called,
                       semantic_vote_status, confidence, created_at_epoch_ms
                FROM contract_preserve_receipts
                WHERE decision_id = ?
                """,
                (pointer,),
            ).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    payload = dict(row)
    if payload.get("model_called") == -1:
        payload["model_called"] = None
    return payload


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
    model_called: bool | None,
    model_call_status: str | None = None,
    vote_status: str = "not_requested",
    confidence: float = 1.0,
    session_preserved: bool = False,
    receipt_pointer: str = "",
    started: float,
) -> ContractDecision:
    receipt = _receipt(
        text=text,
        context=context,
        label=label,
        action=action,
        source=source,
        reason=reason,
        model_called=model_called,
        model_call_status=model_call_status,
        vote_status=vote_status,
        confidence=confidence,
        session_preserved=session_preserved,
        receipt_pointer=receipt_pointer,
        started=started,
    )
    receipt = _persist_contract_preserve_receipt(receipt)
    return ContractDecision(
        label=label,
        matches=matches or (label,),
        action=action,
        reply=reply,
        context=context,
        receipt=receipt,
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
    try:
        from money_truth import classify_money_question

        if classify_money_question(normalized) == "payment_arrival_verify":
            return True
    except Exception:
        pass
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


def _is_explicit_identity_ask(text: str) -> bool:
    """True when an identity-shaped phrase is actually posed as an ask.

    Broad identity phrases remain valuable on an open channel, but the same
    words can appear inside a rich wizard answer (for example, a policy sentence
    explaining what an agent handles).  At an owner-declared active session we
    require conversational ask posture before interrupting that owner.
    """

    raw = " ".join(str(text or "").strip().split())
    candidate = _IDENTITY_ASK_PREAMBLE_RE.sub("", raw, count=1)
    modal = _IDENTITY_MODAL_LEAD_RE.match(candidate)
    if modal:
        candidate = candidate[modal.end():]
    candidate = _IDENTITY_REQUEST_FILLER_RE.sub("", candidate, count=1)

    def _direct_clause(value: str) -> bool:
        return bool(
            _DIRECT_IDENTITY_ASK_RE.search(value)
            or _DIRECT_WHO_IDENTITY_ASK_RE.search(value)
            or _TERMINAL_WHAT_ARE_YOU_RE.search(value)
        )

    if _direct_clause(candidate):
        return True

    # "what [it is] you handle" is deliberately broad in OPEN-channel
    # identity matching, but is also ordinary prose inside a wizard answer.
    # In a rich session it is an identity interruption only when directly
    # requested or when the bare clause is punctuated as a question.
    lead = _IDENTITY_REQUEST_LEAD_RE.match(candidate)
    ask_clause = candidate[lead.end():] if lead else candidate
    if lead and _direct_clause(ask_clause):
        return True
    handle_match = _IDENTITY_HANDLE_CLAUSE_RE.search(ask_clause)
    if not handle_match:
        return False
    tail = ask_clause[handle_match.end():]
    if not _IDENTITY_HANDLE_ALLOWED_TAIL_RE.fullmatch(tail):
        return False
    return lead is not None or ask_clause.rstrip().endswith("?")


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

    # A raw ``status`` noun is not enough to claim the fleet-status contract.
    # Named client/project asks (live regression: ``Capital Hilton status``)
    # belong to their grounded business owner, even when they do not also say
    # invoice/payment.  Keep only bare status idioms and explicit
    # agent/system-posture subjects here; the remaining humanized idioms below
    # (``how are things on your end`` / ``what's happening``) stay valid.
    if _STATUS_PATTERNS[0].search(normalized):
        stripped = normalized.lower().rstrip("?!. ")
        bare_status = {
            "status",
            "status update",
            "status check",
            "status please",
            "quick status",
            "whats the status",
            "what's the status",
            "what is the status",
            "give me a status",
            "give me a status update",
        }
        if stripped in bare_status:
            return True
        explicit_posture_subject = re.search(
            r"(?:\b(?:you|your|system|fleet|agents?|services?|operations?|side|end|"
            r"chief|maestro|cassandra|clara|guardian|niles|hermes)\b.{0,45}"
            r"\b(?:status|state|posture)\b|"
            r"\b(?:status|state|posture)\b.{0,45}\b(?:you|your|system|fleet|agents?|services?)\b)",
            normalized,
            re.IGNORECASE,
        )
        if explicit_posture_subject:
            return True
        return False
    return any(pattern.search(normalized) for pattern in _STATUS_PATTERNS[1:])


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


def _bounded_adapter_error_type(error_type: str) -> str:
    bounded = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(error_type or "")).strip("._-")[:64]
    return bounded or "ContractError"


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

    bounded_error_type = _bounded_adapter_error_type(error_type)
    started = time.monotonic()
    decision_id = _decision_id(text, context, ContractLabel.UNRESOLVED)
    reply = f"{_preserve_reply(context)} Receipt: {decision_id}."
    decision = _make_decision(
        text=text,
        context=context,
        label=ContractLabel.UNRESOLVED,
        action=DecisionAction.PRESERVE_SESSION,
        reply=reply,
        source="adapter_error",
        reason=f"active_session_contract_error:{bounded_error_type}",
        model_called=None,
        model_call_status="unknown",
        vote_status="error_preserved",
        confidence=0.0,
        session_preserved=True,
        receipt_pointer=decision_id,
        started=started,
    )
    if decision.receipt.receipt_persisted:
        return decision
    # A pointer is public only when it resolves. Preserve the fail-closed
    # session reply, but do not advertise an evidence location that was never
    # committed.
    return replace(
        decision,
        reply=_preserve_reply(context),
        receipt=replace(decision.receipt, receipt_pointer=""),
    )


def synthetic_adapter_error_decision(
    text: str,
    *,
    context: ContractContext,
    error_type: str = "ContractError",
) -> ContractDecision:
    """Return a bounded decision when an adapter raises before returning one.

    Inactive adapters may continue through their established owner, but the
    fail-open is explicit. Active sessions retain the existing fail-closed
    preserve path. Exception messages and raw request text never enter the
    receipt.
    """

    if context.active_session:
        return preserve_session_on_error(text, context=context, error_type=error_type)
    receipt = ContractReceipt(
        decision_id=_decision_id(text, context, ContractLabel.UNRESOLVED),
        label=ContractLabel.UNRESOLVED.value,
        action=DecisionAction.PASS_THROUGH.value,
        precedence=_PRECEDENCE[ContractLabel.UNRESOLVED],
        source="adapter_error",
        reason=f"inactive_contract_error:{_bounded_adapter_error_type(error_type)}",
        model_called=None,
        semantic_vote_status="error_fail_open",
        confidence=0.0,
        model_call_status="unknown",
        elapsed_ms=0.0,
    )
    return ContractDecision(
        label=ContractLabel.UNRESOLVED,
        matches=(ContractLabel.UNRESOLVED,),
        action=DecisionAction.PASS_THROUGH,
        reply=None,
        context=context,
        receipt=receipt,
    )


def emergency_adapter_error_decision(
    text: str,
    *,
    context: ContractContext,
    error_type: str = "ContractError",
    factory_error_type: str = "ReceiptFactoryError",
) -> ContractDecision:
    """Build a non-persisting last-resort receipt if the primary factory fails."""

    active = context.active_session
    decision_id = _decision_id(text, context, ContractLabel.UNRESOLVED)
    action = DecisionAction.PRESERVE_SESSION if active else DecisionAction.PASS_THROUGH
    receipt = ContractReceipt(
        decision_id=decision_id,
        label=ContractLabel.UNRESOLVED.value,
        action=action.value,
        precedence=_PRECEDENCE[ContractLabel.UNRESOLVED],
        source="adapter_error",
        reason=(
            f"{'active' if active else 'inactive'}_contract_error_emergency:"
            f"{_bounded_adapter_error_type(error_type)}:factory:"
            f"{_bounded_adapter_error_type(factory_error_type)}"
        ),
        model_called=None,
        semantic_vote_status=("error_emergency_preserved" if active else "error_emergency_fail_open"),
        confidence=0.0,
        model_call_status="unknown",
        session_preserved=active,
        receipt_pointer="",
        receipt_persisted=False,
        receipt_persistence_status="emergency_not_persisted",
        elapsed_ms=0.0,
    )
    return ContractDecision(
        label=ContractLabel.UNRESOLVED,
        matches=(ContractLabel.UNRESOLVED,),
        action=action,
        reply=(_preserve_reply(context) if active else None),
        context=context,
        receipt=receipt,
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
        "Classify a non-authority conversational message. Your reply MUST begin with the character { — "
        "no reasoning, no steps, no prose before or after. Return exactly one JSON object: "
        '{"label":"<label>","confidence":0.0,"session_relevant":false}. '
        "Label meanings: status=asking how things/the system are going right now; "
        "identity=asking who you are, your role, job, or what you handle; "
        "low_coherence=nonsense or garbled text with no real request; "
        "route_instruction=asking to route/stage/hand work to the right agent; "
        "guardian_gate_narration=asking how the send/approval/invoice gates work; "
        "session_relevant=directly answers the currently pending workflow question; "
        "unresolved=none of these clearly fits. "
        f"Allowed labels only: {labels}. Never infer, grant, or describe an approval, authorization, send, delete, "
        "payment, or money-movement decision. A route_instruction label identifies a request to stage/handoff work; "
        "it does not authorize execution.\n"
        f"Agent: {context.agent}\nSurface: {context.surface}\n"
        f"Active session: {str(context.active_session).lower()}\nSession kind: {context.session_kind or 'none'}\n"
        f"Message: {text}"
    )


def _extract_first_json_object(raw: str) -> str | None:
    """Return the first balanced {...} substring, or None.

    Live composition truth (2026-07-10): the local model narrates prose
    reasoning around its JSON even with think=False. The vote stays strict on
    keys/labels but must not require the whole reply to be the object.
    """
    text = str(raw or "")
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        escaped = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        start = text.find("{", start + 1)
    return None


def _parse_semantic_vote(raw: str) -> tuple[ContractLabel, float, bool] | None:
    candidate = _extract_first_json_object(raw)
    if candidate is None:
        return None
    try:
        payload = json.loads(candidate)
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
    # One end-to-end budget split between slot contention and model work.  The
    # prior same-value/same-value shape could consume roughly 2x the advertised
    # timeout (5s waiting + 5s model).  The synchronous adaptive implementation
    # also cannot enforce that its own provider returns.  Run it in a daemon
    # worker and enforce the advertised budget at this contract boundary.
    try:
        total_budget_seconds = float(timeout_seconds)
    except (TypeError, ValueError):
        total_budget_seconds = DEFAULT_SEMANTIC_TIMEOUT_SECONDS
    if not 0 < total_budget_seconds <= 10:
        total_budget_seconds = DEFAULT_SEMANTIC_TIMEOUT_SECONDS
    slot_wait_seconds = min(2.0, max(0.001, total_budget_seconds * 0.4))
    model_timeout_seconds = max(0.001, total_budget_seconds - slot_wait_seconds)
    outcomes: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

    def invoke() -> None:
        try:
            call_fn = adaptive_call_fn
            if call_fn is None:
                from adaptive_model_call import adaptive_model_call as call_fn

            raw = call_fn(
                _semantic_prompt(text, context),
                task_class="contract_semantic_vote",
                lane="frontdoor",
                timeout=model_timeout_seconds,
                attempts=1,
                think=False,
                num_predict=160,
                options={"format": "json", "temperature": 0},
                retry=False,
                model_slot_max_wait_seconds=slot_wait_seconds,
            )
            outcome = ("result", raw)
        except Exception as exc:
            outcome = ("error", type(exc).__name__)
        try:
            outcomes.put_nowait(outcome)
        except queue.Full:
            # The caller has already crossed the wall and abandoned the
            # one-result mailbox.  The daemon must never hold process exit.
            return

    deadline = time.monotonic() + total_budget_seconds
    worker = threading.Thread(
        target=invoke,
        name="contract-semantic-vote",
        daemon=True,
    )
    worker.start()
    try:
        outcome_kind, outcome_value = outcomes.get(timeout=max(0.0, deadline - time.monotonic()))
    except queue.Empty:
        return None, "deadline_exceeded"
    if outcome_kind == "error":
        return None, f"error:{outcome_value}"
    raw = outcome_value
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
    if (
        _identity_match
        and context.active_session
        and context.session_owner_handles_unknown
        and not _is_explicit_identity_ask(raw)
    ):
        # Precedence v2 remains intact: the session predicate does not outrank
        # a real IDENTITY ask.  This only prevents a declarative owner answer
        # from being mislabeled as an identity interruption.
        _identity_match = False
    _low_coherence = _is_low_coherence(raw) and not _identity_match
    if _low_coherence and context.active_session and session_answer_predicate is not None:
        # A short in-session command ("why?", "skip", "examples") looks like
        # gibberish to a generic heuristic; the session's own predicate knows
        # its vocabulary and outranks LOW_COHERENCE only (2026-07-10 battery).
        try:
            if bool(session_answer_predicate(raw)):
                _low_coherence = False
        except Exception:
            pass
    if _low_coherence:
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

    if context.active_session and context.session_owner_handles_unknown:
        # The adapter DECLARED its session owner parses unknown text (guided
        # review's wizard has rich command/answer handling of its own).  Greedy
        # capture of CONTRACT-shaped texts is already prevented above, and the
        # vote-uncertain path still preserves per the consensus guard-rail.
        return _make_decision(
            text=raw,
            context=context,
            label=ContractLabel.UNRESOLVED,
            action=DecisionAction.PASS_THROUGH,
            reply=None,
            source="fallback",
            reason="vote_disabled_session_owner_passthrough",
            model_called=False,
            vote_status="disabled",
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
    "CONTRACT_RECEIPT_DB_ENV",
    "ContractContext",
    "ContractDecision",
    "ContractLabel",
    "ContractReceipt",
    "DecisionAction",
    "HandoffResult",
    "active_session_from_mapping",
    "contract_receipt_db_path",
    "decide_contract",
    "emergency_adapter_error_decision",
    "guardian_gate_narration_reply",
    "preserve_session_on_error",
    "resolve_contract_receipt",
    "semantic_vote_enabled_for_adapter",
    "semantic_vote_timeout_seconds",
    "synthetic_adapter_error_decision",
    "surface_scope_matches",
]
