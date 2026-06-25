"""
conversation_capsule.py

Standalone durable-memory module for OpenClaw conversation continuity.

Provides a per-conversation capsule store keyed by a composite of
(operator_id, agent_id, conversation_id, channel_id, thread_id?).
Each capsule is a JSON artifact written with atomic-replace + fsync
discipline (modelled on cassandra_brain.save_state).

Usage
-----
    import conversation_capsule as cc

    store = cc.ConversationCapsuleStore()
    conv_id = cc.mint_conversation_id(
        channel_id="telegram_123",
        chat_id="chat_456",
        first_seen_iso="2026-06-25T09:00:00Z",
    )
    capsule = store.load("op1", "maestro", conv_id, "telegram_123")
    if capsule is None:
        capsule = cc.Capsule.cold_start(
            agent_id="maestro",
            operator_id="op1",
            conversation_id=conv_id,
            channel_id="telegram_123",
        )
    # ... populate / mutate capsule fields at turn-start ...
    store.write("op1", "maestro", conv_id, "telegram_123", capsule)

Public API
----------
ConversationCapsuleStore(store_dir, recent_messages_max)
    .load(operator_id, agent_id, conversation_id, channel_id,
          thread_id=None) -> Capsule | None
    .write(operator_id, agent_id, conversation_id, channel_id,
           capsule, thread_id=None) -> None
    .supersede(operator_id, agent_id, conversation_id, channel_id,
               thread_id=None, new_capsule=None) -> Capsule

Capsule (dataclass)
    .to_dict() -> dict
    .from_dict(d) -> Capsule               [classmethod]
    .cold_start(...) -> Capsule            [classmethod]
    .is_superseded() -> bool
    .is_stale(max_age_seconds) -> bool

mint_conversation_id(channel_id, chat_id, first_seen_iso) -> str   [pure]
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Default store location ────────────────────────────────────────────────────

_DEFAULT_STORE_DIR: str = "/home/openclaw/state/conversation_capsules"

# ── Banned raw-body field names (PII / legal-evidence guard) ──────────────────
#
# The capsule schema uses *ref* fields (tokenised identifiers / metadata
# pointers), never raw transcript bodies or legal-sealed content.
# _validate_no_raw_bodies() is called on every write to enforce this.
# Extend this set if the schema grows new ref fields that could be confused
# with raw bodies.

_BANNED_RAW_BODY_KEYS: frozenset = frozenset(
    {
        "raw_body",
        "transcript_body",
        "legal_evidence_body",
        "raw_legal",
        "full_transcript",
        "email_body",
        "message_body",
    }
)


# ── Capsule dataclass ─────────────────────────────────────────────────────────


@dataclass
class Capsule:
    """
    A durable per-conversation memory capsule.

    Field groups mirror CONVERSATION_CONTINUITY_CONTRACT §Capsule contents:

      identity    — who the agent is and its relationship to the operator
      live_state  — current projects, decisions, commitments, open loops, etc.
      context     — recent messages (last-N window), distilled memories, facts
      provenance  — versioning, timestamps, supersession pointer

    All list-of-message fields carry *refs* (tokenised identifiers or metadata
    pointers), never raw PII or legal-sealed content.  The PII guard in
    ConversationCapsuleStore.write() enforces this at the store boundary.
    """

    # ── Identity ──────────────────────────────────────────────────────────────

    agent_id: str = ""
    """Stable identifier of the agent (e.g. 'maestro', 'cassandra')."""

    agent_role: str = ""
    """Human-readable role description."""

    operator_id: str = ""
    """Stable identifier of the operator this capsule belongs to."""

    operator_relationship: str = ""
    """Qualitative description of the working relationship and trust context."""

    operator_preferences: Dict[str, Any] = field(default_factory=dict)
    """Structured operator preferences (style, delivery, pace, etc.) as key→value."""

    communication_style: str = ""
    """Preferred communication register (e.g. 'direct', 'warm-professional')."""

    # ── Composite key fields (stored for reconstruction) ─────────────────────

    conversation_id: str = ""
    channel_id: str = ""
    thread_id: Optional[str] = None

    # ── Live state ────────────────────────────────────────────────────────────

    current_projects: List[str] = field(default_factory=list)
    """Short slugs or ref tokens for active projects."""

    goals: List[str] = field(default_factory=list)
    """Current operator goals (concise statements, no raw body)."""

    decisions: List[str] = field(default_factory=list)
    """Decisions that have been reached and logged."""

    commitments: List[str] = field(default_factory=list)
    """Commitments made by the agent to the operator."""

    pending_actions: List[str] = field(default_factory=list)
    """Actions that are pending execution or operator approval."""

    open_loops: List[str] = field(default_factory=list)
    """Items started but not yet resolved."""

    unresolved_questions: List[str] = field(default_factory=list)
    """Questions that remain open between the agent and the operator."""

    prior_corrections: List[str] = field(default_factory=list)
    """Important corrections the operator made in prior turns (ref or summary)."""

    active_authority_scope: List[str] = field(default_factory=list)
    """Currently active authority grants (token refs, not raw secrets)."""

    # ── Context ───────────────────────────────────────────────────────────────

    recent_messages: List[Dict[str, Any]] = field(default_factory=list)
    """
    Sliding window of recent message metadata.

    Each entry: {"role": str, "ref": str, "summary": str, "ts": str}.
    The "ref" is a content-addressed token — NOT the raw message body.
    Maximum N entries is enforced by ConversationCapsuleStore.write().
    """

    distilled_memories: List[str] = field(default_factory=list)
    """Durable compressed memories distilled from prior conversation spans."""

    current_facts: List[str] = field(default_factory=list)
    """Domain facts that are currently known to be true."""

    current_unknowns: List[str] = field(default_factory=list)
    """Domain unknowns that should guide the agent's information-seeking."""

    current_risks: List[str] = field(default_factory=list)
    """Risks that are currently active or worth flagging."""

    # ── Provenance ────────────────────────────────────────────────────────────

    latest_package_refs: List[str] = field(default_factory=list)
    """
    Ref tokens of the most recently approved context packages (Maestro packet
    hash, etc.).  Not the package body.
    """

    recent_receipt_refs: List[str] = field(default_factory=list)
    """Ref tokens of recent action receipts (correlation ids, not raw content)."""

    capsule_version: int = 1
    """Monotonically increasing version counter; bumped by supersede()."""

    last_interaction_at: str = ""
    """ISO-8601 UTC timestamp of the most recent turn that wrote this capsule."""

    superseded_by: Optional[str] = None
    """
    If set, this capsule has been superseded.

    The value is a human-readable label describing the replacement (typically
    the new conversation_id or a version tag).  ConversationCapsuleStore.load()
    will never silently return a superseded capsule — callers receive None and
    must explicitly load the replacement.

    Superseded capsules are archived to <key>.superseded.<version>.json files;
    the canonical path always holds the current (non-superseded) capsule.
    """

    # ── Constructors ──────────────────────────────────────────────────────────

    @classmethod
    def cold_start(
        cls,
        agent_id: str,
        operator_id: str,
        conversation_id: str,
        channel_id: str,
        thread_id: Optional[str] = None,
        agent_role: str = "",
        operator_relationship: str = "",
        operator_preferences: Optional[Dict[str, Any]] = None,
        communication_style: str = "",
        active_authority_scope: Optional[List[str]] = None,
    ) -> "Capsule":
        """
        Create a blank capsule for a conversation with no prior history.

        This is the correct entry-point for cold-start reconstruction
        (CONVERSATION_CONTINUITY_CONTRACT §Cold-start reconstruction test).
        All list fields start empty; callers populate them from durable stores
        (canonical facts, authority registry, operator preference stores, etc.).
        """
        return cls(
            agent_id=agent_id,
            operator_id=operator_id,
            conversation_id=conversation_id,
            channel_id=channel_id,
            thread_id=thread_id,
            agent_role=agent_role,
            operator_relationship=operator_relationship,
            operator_preferences=dict(operator_preferences or {}),
            communication_style=communication_style,
            active_authority_scope=list(active_authority_scope or []),
            last_interaction_at=_utc_now_iso(),
            capsule_version=1,
        )

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-round-trippable dict representation of this capsule."""
        return {
            # identity
            "agent_id": self.agent_id,
            "agent_role": self.agent_role,
            "operator_id": self.operator_id,
            "operator_relationship": self.operator_relationship,
            "operator_preferences": dict(self.operator_preferences),
            "communication_style": self.communication_style,
            # composite key
            "conversation_id": self.conversation_id,
            "channel_id": self.channel_id,
            "thread_id": self.thread_id,
            # live state
            "current_projects": list(self.current_projects),
            "goals": list(self.goals),
            "decisions": list(self.decisions),
            "commitments": list(self.commitments),
            "pending_actions": list(self.pending_actions),
            "open_loops": list(self.open_loops),
            "unresolved_questions": list(self.unresolved_questions),
            "prior_corrections": list(self.prior_corrections),
            "active_authority_scope": list(self.active_authority_scope),
            # context
            "recent_messages": [dict(m) for m in self.recent_messages],
            "distilled_memories": list(self.distilled_memories),
            "current_facts": list(self.current_facts),
            "current_unknowns": list(self.current_unknowns),
            "current_risks": list(self.current_risks),
            # provenance
            "latest_package_refs": list(self.latest_package_refs),
            "recent_receipt_refs": list(self.recent_receipt_refs),
            "capsule_version": self.capsule_version,
            "last_interaction_at": self.last_interaction_at,
            "superseded_by": self.superseded_by,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Capsule":
        """Reconstruct a Capsule from a dict (e.g. loaded from JSON on disk)."""
        return cls(
            # identity
            agent_id=d.get("agent_id", ""),
            agent_role=d.get("agent_role", ""),
            operator_id=d.get("operator_id", ""),
            operator_relationship=d.get("operator_relationship", ""),
            operator_preferences=dict(d.get("operator_preferences", {})),
            communication_style=d.get("communication_style", ""),
            # composite key
            conversation_id=d.get("conversation_id", ""),
            channel_id=d.get("channel_id", ""),
            thread_id=d.get("thread_id", None),
            # live state
            current_projects=list(d.get("current_projects", [])),
            goals=list(d.get("goals", [])),
            decisions=list(d.get("decisions", [])),
            commitments=list(d.get("commitments", [])),
            pending_actions=list(d.get("pending_actions", [])),
            open_loops=list(d.get("open_loops", [])),
            unresolved_questions=list(d.get("unresolved_questions", [])),
            prior_corrections=list(d.get("prior_corrections", [])),
            active_authority_scope=list(d.get("active_authority_scope", [])),
            # context
            recent_messages=[dict(m) for m in d.get("recent_messages", [])],
            distilled_memories=list(d.get("distilled_memories", [])),
            current_facts=list(d.get("current_facts", [])),
            current_unknowns=list(d.get("current_unknowns", [])),
            current_risks=list(d.get("current_risks", [])),
            # provenance
            latest_package_refs=list(d.get("latest_package_refs", [])),
            recent_receipt_refs=list(d.get("recent_receipt_refs", [])),
            capsule_version=int(d.get("capsule_version", 1)),
            last_interaction_at=d.get("last_interaction_at", ""),
            superseded_by=d.get("superseded_by", None),
        )

    # ── Freshness helpers ─────────────────────────────────────────────────────

    def is_superseded(self) -> bool:
        """Return True if this capsule has been superseded by another."""
        return self.superseded_by is not None

    def is_stale(self, max_age_seconds: float = 3600.0) -> bool:
        """
        Return True if the capsule has not been updated within max_age_seconds.

        A superseded capsule is always considered stale regardless of age.
        """
        if self.is_superseded():
            return True
        if not self.last_interaction_at:
            return True
        try:
            last = datetime.fromisoformat(
                self.last_interaction_at.replace("Z", "+00:00")
            )
            age = (datetime.now(timezone.utc) - last).total_seconds()
            return age > max_age_seconds
        except (ValueError, TypeError):
            return True


# ── Key construction helpers ──────────────────────────────────────────────────


def _safe_slug(value: str, max_len: int = 24) -> str:
    """
    Reduce an arbitrary string to a filesystem-safe slug.

    Keeps alphanumerics, hyphens, and underscores; replaces everything else
    with underscores; truncates to max_len.
    """
    slug = re.sub(r"[^A-Za-z0-9_\-]", "_", value)
    return slug[:max_len]


def _build_key(
    operator_id: str,
    agent_id: str,
    conversation_id: str,
    channel_id: str,
    thread_id: Optional[str] = None,
) -> str:
    """
    Build a filesystem-safe composite key string for the given dimensions.

    The key is deterministic for the same inputs and safe for use as a
    filename stem.  A SHA-256 suffix disambiguates collisions that could
    arise from slug truncation.
    """
    raw = f"{operator_id}|{agent_id}|{conversation_id}|{channel_id}"
    if thread_id:
        raw += f"|{thread_id}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    # Human-readable prefix for debuggability.
    prefix = "__".join(
        [
            _safe_slug(agent_id),
            _safe_slug(channel_id),
            _safe_slug(conversation_id),
        ]
    )
    return f"{prefix}__{digest}"


# ── Pure conversation-id factory ──────────────────────────────────────────────


def mint_conversation_id(
    channel_id: str,
    chat_id: str,
    first_seen_iso: str,
) -> str:
    """
    Derive a stable, deterministic conversation identifier.

    The result is a hex string (SHA-1) derived solely from
    (channel_id, chat_id, first_seen_iso).  The same inputs always produce
    the same id — no time calls or random elements are used inside this
    function.

    Parameters
    ----------
    channel_id      : Platform channel identifier (e.g. 'telegram_123').
    chat_id         : Provider-level chat/room id (e.g. 'chat_456').
    first_seen_iso  : ISO-8601 timestamp string of the first message in this
                      conversation (caller supplies; do NOT use datetime.now()).

    Returns
    -------
    str : Deterministic conversation id prefixed 'conv_'.
    """
    raw = f"{channel_id}|{chat_id}|{first_seen_iso}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return f"conv_{digest}"


# ── Store ─────────────────────────────────────────────────────────────────────


class ConversationCapsuleStore:
    """
    Durable, file-backed store for Capsule objects.

    Layout
    ------
    Each active capsule is stored as:
        <store_dir>/<composite-key>.json

    When supersede() is called the old capsule (with superseded_by set) is
    archived to:
        <store_dir>/<composite-key>.superseded.<old-version>.json

    and the new capsule (with bumped capsule_version, superseded_by=None) is
    written to the canonical path.  load() always reads the canonical path and
    returns None if its superseded_by field is set.

    Write discipline (mirrors cassandra_brain.save_state)
    ------------------------------------------------------
    1. Write JSON to a .tmp sidecar.
    2. flush() + fsync() to guarantee durability.
    3. os.replace() the .tmp onto the canonical path (POSIX-atomic rename).

    Thread safety
    -------------
    A per-key lock serialises concurrent writes from multiple threads.
    Cross-process safety relies on os.replace() being an atomic rename on
    the same filesystem.

    Parameters
    ----------
    store_dir : str
        Directory where capsule JSON files are stored.  Injected for
        testability; defaults to /home/openclaw/state/conversation_capsules.
    recent_messages_max : int
        Maximum number of recent_messages entries retained on write.
        Older entries are dropped (FIFO) to bound capsule size.
    """

    def __init__(
        self,
        store_dir: str = _DEFAULT_STORE_DIR,
        recent_messages_max: int = 20,
    ) -> None:
        self._store_dir = Path(store_dir)
        self._recent_messages_max = recent_messages_max
        self._key_locks: Dict[str, threading.Lock] = {}
        self._registry_lock = threading.Lock()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _lock_for(self, key: str) -> threading.Lock:
        """Return (creating if needed) the per-key write lock."""
        with self._registry_lock:
            if key not in self._key_locks:
                self._key_locks[key] = threading.Lock()
            return self._key_locks[key]

    def _path_for(self, key: str) -> Path:
        """Return the canonical capsule path for a key."""
        return self._store_dir / f"{key}.json"

    def _archive_path_for(self, key: str, old_version: int) -> Path:
        """Return the archive (superseded) path for a given version."""
        return self._store_dir / f"{key}.superseded.{old_version}.json"

    def _ensure_store_dir(self) -> None:
        self._store_dir.mkdir(parents=True, exist_ok=True)

    def _compute_key(
        self,
        operator_id: str,
        agent_id: str,
        conversation_id: str,
        channel_id: str,
        thread_id: Optional[str],
    ) -> str:
        return _build_key(
            operator_id, agent_id, conversation_id, channel_id, thread_id
        )

    def _atomic_write(self, path: Path, data: dict) -> None:
        """Write data as JSON to path atomically (tmp → fsync → replace)."""
        tmp_path = path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)

    # ── Public API ────────────────────────────────────────────────────────────

    def load(
        self,
        operator_id: str,
        agent_id: str,
        conversation_id: str,
        channel_id: str,
        thread_id: Optional[str] = None,
    ) -> Optional[Capsule]:
        """
        Load the active capsule for the given composite key, or return None.

        Returns None when:
          - No capsule file exists for the key.
          - The file is unreadable or corrupt.
          - The capsule's superseded_by field is set (it has been superseded).

        A superseded capsule is NEVER silently returned as current.
        """
        key = self._compute_key(
            operator_id, agent_id, conversation_id, channel_id, thread_id
        )
        path = self._path_for(key)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None
        capsule = Capsule.from_dict(data)
        if capsule.is_superseded():
            # The canonical file was left with superseded_by set — this should
            # not happen in normal operation (supersede() always writes the
            # replacement to the canonical path), but guard here defensively.
            return None
        return capsule

    def write(
        self,
        operator_id: str,
        agent_id: str,
        conversation_id: str,
        channel_id: str,
        capsule: Capsule,
        thread_id: Optional[str] = None,
    ) -> None:
        """
        Atomically persist the capsule to disk.

        Raises
        ------
        ValueError
            If the capsule dict contains a banned raw-body key (PII guard).
        """
        _validate_no_raw_bodies(capsule)

        # Trim recent_messages to the configured sliding window.
        if len(capsule.recent_messages) > self._recent_messages_max:
            capsule.recent_messages = capsule.recent_messages[
                -self._recent_messages_max :
            ]

        key = self._compute_key(
            operator_id, agent_id, conversation_id, channel_id, thread_id
        )
        path = self._path_for(key)

        with self._lock_for(key):
            self._ensure_store_dir()
            self._atomic_write(path, capsule.to_dict())

    def supersede(
        self,
        operator_id: str,
        agent_id: str,
        conversation_id: str,
        channel_id: str,
        thread_id: Optional[str] = None,
        new_capsule: Optional[Capsule] = None,
    ) -> Capsule:
        """
        Retire the current capsule and write a replacement with bumped version.

        Supersession model
        ------------------
        1. Read the current canonical capsule.
        2. Set its superseded_by to a version label and archive it atomically
           to <key>.superseded.<old-version>.json (preserving the audit trail).
        3. Construct the replacement capsule (new_capsule or a cold-start clone
           of the old identity fields) with capsule_version = old + 1 and
           superseded_by = None.
        4. Write the replacement to the canonical path atomically.
        5. Return the replacement.

        The canonical path always holds the *current* (non-superseded) capsule;
        load() at the same key immediately returns the replacement.

        If no capsule exists at the key yet, a cold-start capsule is created
        and written directly (nothing to supersede).

        Parameters
        ----------
        new_capsule : Capsule, optional
            Caller-supplied replacement.  If None, a clone of the existing
            capsule's identity fields is created with all live-state cleared
            and the version bumped.  new_capsule.superseded_by must be None;
            it will be enforced.

        Returns
        -------
        Capsule : The new active capsule.
        """
        key = self._compute_key(
            operator_id, agent_id, conversation_id, channel_id, thread_id
        )

        with self._lock_for(key):
            self._ensure_store_dir()

            path = self._path_for(key)

            # Load existing (may be None if store is fresh).
            old: Optional[Capsule] = None
            if path.exists():
                try:
                    with path.open("r", encoding="utf-8") as f:
                        old = Capsule.from_dict(json.load(f))
                except (OSError, json.JSONDecodeError):
                    old = None

            old_version = old.capsule_version if old is not None else 0
            new_version = old_version + 1

            # Build replacement label for the superseded_by field.
            version_label = f"{conversation_id}:v{new_version}"

            # Build the replacement capsule.
            if new_capsule is None:
                if old is not None:
                    replacement = Capsule(
                        agent_id=old.agent_id,
                        agent_role=old.agent_role,
                        operator_id=old.operator_id,
                        operator_relationship=old.operator_relationship,
                        operator_preferences=dict(old.operator_preferences),
                        communication_style=old.communication_style,
                        conversation_id=old.conversation_id,
                        channel_id=old.channel_id,
                        thread_id=old.thread_id,
                        active_authority_scope=list(old.active_authority_scope),
                    )
                else:
                    replacement = Capsule.cold_start(
                        agent_id=agent_id,
                        operator_id=operator_id,
                        conversation_id=conversation_id,
                        channel_id=channel_id,
                        thread_id=thread_id,
                    )
            else:
                replacement = new_capsule

            # Enforce: the replacement must not carry a superseded_by marker.
            replacement.superseded_by = None
            replacement.capsule_version = new_version
            replacement.last_interaction_at = _utc_now_iso()

            # Archive the old capsule (with superseded_by set).
            if old is not None:
                old.superseded_by = version_label
                archive_path = self._archive_path_for(key, old_version)
                self._atomic_write(archive_path, old.to_dict())

            # Write replacement to canonical path.
            _validate_no_raw_bodies(replacement)
            if len(replacement.recent_messages) > self._recent_messages_max:
                replacement.recent_messages = replacement.recent_messages[
                    -self._recent_messages_max :
                ]
            self._atomic_write(path, replacement.to_dict())

        return replacement


# ── PII / raw-body guard ──────────────────────────────────────────────────────


def _validate_no_raw_bodies(capsule: Capsule) -> None:
    """
    Raise ValueError if the capsule dict contains a banned raw-body key.

    This is a schema-boundary guard, not a cryptographic proof.  It prevents
    accidental writes of raw PII or legal-evidence bodies into the capsule
    store.  Both the top-level dict and each recent_messages entry are checked.
    """
    d = capsule.to_dict()
    bad = _BANNED_RAW_BODY_KEYS & set(d.keys())
    if bad:
        raise ValueError(
            f"Capsule contains banned raw-body fields: {sorted(bad)}. "
            "Store only tokenised refs or metadata in capsules."
        )
    for msg in d.get("recent_messages", []):
        bad_msg = _BANNED_RAW_BODY_KEYS & set(msg.keys())
        if bad_msg:
            raise ValueError(
                f"recent_messages entry contains banned raw-body fields: "
                f"{sorted(bad_msg)}.  Use 'ref' + 'summary' fields; never "
                "store the raw body."
            )


# ── Internal utilities ────────────────────────────────────────────────────────


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with 'Z' suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
