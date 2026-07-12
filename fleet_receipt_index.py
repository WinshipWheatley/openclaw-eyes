"""Durable, chat-bound index for human-safe operator receipt retrieval.

Receipt providers own their raw references and machine truth.  This module owns
only the fact that a particular receipt was successfully delivered through a
particular conversational binding.  Failed sends never create an index row.
Raw provider references stay in SQLite/machine disclosure and are never
rendered into operator text.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "fleet_receipt_index_v1"
HUMAN_RECEIPT_LOOKUP_HINT = "Say “show receipt” for the delivery record."
DEFAULT_SQLITE_PATH = (
    Path(__file__).resolve().parent
    / "generated"
    / "receipts"
    / "fleet_receipt_index.sqlite3"
)


class ReceiptProvider(str, Enum):
    WORKFLOW = "workflow"
    TYPED_CONTRACT = "typed_contract"
    ORIGIN_OUTPUT = "origin_output"
    PROPOSAL_FACTORY = "proposal_factory"


class ReceiptIndexUnavailable(RuntimeError):
    """The durable index could not be read safely.

    This deliberately carries no database path or provider detail.  Callers
    can fail closed with one operator-safe no-action response without turning
    storage failure into a misleading "not found" result.
    """


PROVIDER_BACKENDS: Mapping[str, str] = {
    ReceiptProvider.WORKFLOW.value: "workflow_package_queue",
    ReceiptProvider.TYPED_CONTRACT.value: "typed_contract_decision",
    ReceiptProvider.ORIGIN_OUTPUT.value: "origin_bound_output",
    ReceiptProvider.PROPOSAL_FACTORY.value: "proposal_factory_truth",
}
SUPPORTED_PROVIDERS = frozenset(PROVIDER_BACKENDS)

_ALIAS_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_ALIAS_RE = re.compile(r"^R-[2-9A-HJKMNP-Z]{6,12}$", re.IGNORECASE)
_SHOW_RECEIPT_RE = re.compile(
    r"^\s*(?:please\s+)?(?:"
    r"(?:show|open|pull\s+up)\s+(?:me\s+)?(?:the\s+)?receipt"
    r"|what(?:'s|\s+is)\s+(?:the\s+)?receipt"
    r")"
    r"(?:\s+(?P<alias>R-[2-9A-HJKMNP-Z]{6,12}))?"
    r"\s*[?.!]*\s*$",
    re.IGNORECASE,
)
_RAW_VISIBLE_RECEIPT_RE = re.compile(r"(?:^|\s)Receipt\s*:\s*\S+", re.IGNORECASE)
_VISIBLE_LOOKUP_HINT_RE = re.compile(
    r"(?:^|\s)Say\s+[‘’“”\"']?show\s+receipt[‘’“”\"']?\s+"
    r"for\s+the\s+(?:delivery|decision)\s+record\.?",
    re.IGNORECASE,
)

_NOT_FOUND_TEXT = (
    "I couldn't find a delivered receipt bound to this chat or replied-to message."
)
_CROSS_CHAT_DENIED_TEXT = (
    "That receipt isn't available from this chat. Reply in the original chat "
    "or use its original message."
)
_MAX_ALIAS_ATTEMPTS = 128
_MAX_PUBLIC_FIELD_LENGTH = 240
_MAX_NO_ACTION_FACTS = 5
_MAX_CLARIFICATION_CANDIDATES = 5


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def render_receipt_safe_visible_text(
    text: Any,
    *,
    raw_ref: str = "",
    advertise: bool = False,
) -> str:
    """Remove machine refs/dead hints and optionally append one verified hint."""

    original = str(text or "")
    body = _RAW_VISIBLE_RECEIPT_RE.sub("", original)
    pointer = str(raw_ref or "").strip()
    if pointer:
        body = re.sub(re.escape(pointer), "", body, flags=re.IGNORECASE)
    body = _VISIBLE_LOOKUP_HINT_RE.sub("", body)
    changed = body != original
    if changed:
        body = "\n".join(
            line.rstrip()
            for line in body.splitlines()
            if line.strip(" .")
        ).strip()
    if advertise:
        separator = "\n" if "\n" in body else " "
        body = (
            f"{body}{separator}{HUMAN_RECEIPT_LOOKUP_HINT}"
            if body
            else HUMAN_RECEIPT_LOOKUP_HINT
        )
    return body


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _timestamp(value: Any, *, field_name: str) -> str:
    cleaned = _clean(value)
    if not cleaned:
        raise ValueError(f"{field_name} is required")
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def _provider_value(provider: str | ReceiptProvider) -> str:
    value = provider.value if isinstance(provider, ReceiptProvider) else _clean(provider).lower()
    if value not in SUPPORTED_PROVIDERS:
        raise ValueError(f"unsupported receipt provider: {value or '<empty>'}")
    return value


def _operator_safe_text(value: Any, *, field_name: str, required: bool = True) -> str:
    cleaned = _clean(value)
    if required and not cleaned:
        raise ValueError(f"{field_name} is required")
    if not cleaned:
        return ""
    if len(cleaned) > _MAX_PUBLIC_FIELD_LENGTH:
        raise ValueError(f"{field_name} exceeds the bounded public length")
    try:
        from operator_surface_guard import check_operator_surface

        verdict = check_operator_surface(cleaned, agent_role="OPENCLAW_SYSTEM")
    except Exception as exc:
        raise ValueError(f"{field_name} could not be validated for the operator surface") from exc
    if not verdict.safe_for_operator:
        raise ValueError(f"{field_name} is not safe for the operator surface")
    return cleaned


@dataclass(frozen=True, slots=True)
class ReceiptDescriptor:
    """Machine descriptor supplied by one of the four closed providers."""

    provider: str
    raw_ref: str
    what_happened: str
    status: str
    occurred_at: str
    authority_summary: str
    no_action_facts: tuple[str, ...]
    durable: bool = True
    owning_backend: str = field(init=False)

    def __post_init__(self) -> None:
        provider = _provider_value(self.provider)
        owning_backend = PROVIDER_BACKENDS[provider]
        raw_ref = _clean(self.raw_ref)
        if not raw_ref:
            raise ValueError("raw_ref is required")
        if len(raw_ref) > 1024:
            raise ValueError("raw_ref exceeds the bounded machine length")
        if not isinstance(self.durable, bool):
            raise ValueError("durable must be a boolean")

        unvalidated_public_values = (
            _clean(self.what_happened),
            _clean(self.status),
            _clean(self.authority_summary),
            *(_clean(item) for item in self.no_action_facts),
        )
        if any(
            raw_ref.casefold() in item.casefold()
            for item in unvalidated_public_values
            if item
        ):
            raise ValueError("raw receipt reference cannot appear in public summary fields")
        if any(
            owning_backend.casefold() in item.casefold()
            for item in unvalidated_public_values
            if item
        ):
            raise ValueError("owning backend cannot appear in public summary fields")

        happened = _operator_safe_text(self.what_happened, field_name="what_happened")
        status = _operator_safe_text(self.status, field_name="status")
        authority = _operator_safe_text(
            self.authority_summary,
            field_name="authority_summary",
        )
        facts = tuple(
            _operator_safe_text(item, field_name="no_action_fact")
            for item in self.no_action_facts
            if _clean(item)
        )
        if not facts:
            raise ValueError("at least one no_action_fact is required")
        if len(facts) > _MAX_NO_ACTION_FACTS:
            raise ValueError("too many no_action_facts")

        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "raw_ref", raw_ref)
        object.__setattr__(self, "what_happened", happened)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "occurred_at", _timestamp(self.occurred_at, field_name="occurred_at"))
        object.__setattr__(self, "authority_summary", authority)
        object.__setattr__(self, "no_action_facts", facts)
        object.__setattr__(self, "durable", self.durable)
        object.__setattr__(self, "owning_backend", owning_backend)


@dataclass(frozen=True, slots=True)
class RegistrationResult:
    outcome: str
    registered: bool
    alias: str


@dataclass(frozen=True, slots=True)
class ReceiptRequest:
    alias: str = ""


@dataclass(frozen=True, slots=True)
class ReceiptResolution:
    outcome: str
    text: str
    aliases: tuple[str, ...] = ()


def build_receipt_descriptor(
    *,
    provider: str | ReceiptProvider,
    raw_ref: str,
    what_happened: str,
    status: str,
    occurred_at: str,
    authority_summary: str,
    no_action_facts: Iterable[str],
    durable: bool = True,
) -> ReceiptDescriptor:
    return ReceiptDescriptor(
        provider=_provider_value(provider),
        raw_ref=raw_ref,
        what_happened=what_happened,
        status=status,
        occurred_at=occurred_at,
        authority_summary=authority_summary,
        no_action_facts=tuple(no_action_facts),
        durable=durable,
    )


def machine_receipt_disclosure(descriptor: ReceiptDescriptor) -> dict[str, Any]:
    """Return machine-only truth.  There is deliberately no request/prompt field."""

    return {
        "schema_version": SCHEMA_VERSION,
        "provider": descriptor.provider,
        "owning_backend": descriptor.owning_backend,
        "raw_ref": descriptor.raw_ref,
        "what_happened": descriptor.what_happened,
        "status": descriptor.status,
        "occurred_at": descriptor.occurred_at,
        "authority_summary": descriptor.authority_summary,
        "no_action_facts": list(descriptor.no_action_facts),
        "provider_receipt_durable": descriptor.durable,
    }


def human_receipt_hint(descriptor: ReceiptDescriptor) -> str:
    """Advertise retrieval only when the provider pointer is already durable."""

    if not descriptor.durable:
        return ""
    return HUMAN_RECEIPT_LOOKUP_HINT


def _binding_value(value: Any, *, field_name: str) -> str:
    cleaned = _clean(value)
    if not cleaned:
        raise ValueError(f"{field_name} is required")
    if len(cleaned) > 256:
        raise ValueError(f"{field_name} exceeds the bounded identifier length")
    return cleaned


def _delivery_key(
    descriptor: ReceiptDescriptor,
    *,
    surface: str,
    bot_identity: str,
    chat_id: str,
    source_message_id: str,
    delivered_message_id: str,
) -> str:
    material = json.dumps(
        {
            "provider": descriptor.provider,
            "raw_ref": descriptor.raw_ref,
            "surface": surface,
            "bot_identity": bot_identity,
            "chat_id": chat_id,
            "source_message_id": source_message_id,
            "delivered_message_id": delivered_message_id,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _base_human(value: int, width: int) -> str:
    base = len(_ALIAS_ALPHABET)
    chars: list[str] = []
    for _ in range(width):
        value, remainder = divmod(value, base)
        chars.append(_ALIAS_ALPHABET[remainder])
    return "".join(reversed(chars))


def _alias_candidate(delivery_key: str, attempt: int) -> str:
    digest = hashlib.sha256(f"{delivery_key}:{attempt}".encode("utf-8")).digest()
    width = min(6 + max(0, int(attempt)) // 16, 12)
    return "R-" + _base_human(int.from_bytes(digest, "big"), width)


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=1.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 1000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS fleet_receipt_deliveries (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          delivery_key TEXT NOT NULL UNIQUE,
          alias TEXT NOT NULL COLLATE NOCASE UNIQUE,
          provider TEXT NOT NULL CHECK (
            provider IN ('workflow', 'typed_contract', 'origin_output', 'proposal_factory')
          ),
          owning_backend TEXT NOT NULL CHECK (
            (provider='workflow' AND owning_backend='workflow_package_queue') OR
            (provider='typed_contract' AND owning_backend='typed_contract_decision') OR
            (provider='origin_output' AND owning_backend='origin_bound_output') OR
            (provider='proposal_factory' AND owning_backend='proposal_factory_truth')
          ),
          raw_ref TEXT NOT NULL,
          surface TEXT NOT NULL,
          bot_identity TEXT NOT NULL,
          chat_id TEXT NOT NULL,
          source_message_id TEXT NOT NULL,
          delivered_message_id TEXT NOT NULL,
          delivered_at TEXT NOT NULL,
          what_happened TEXT NOT NULL,
          status TEXT NOT NULL,
          occurred_at TEXT NOT NULL,
          authority_summary TEXT NOT NULL,
          no_action_facts_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_fleet_receipt_reply_binding
          ON fleet_receipt_deliveries (
            surface, bot_identity, chat_id, delivered_message_id
          );
        CREATE INDEX IF NOT EXISTS idx_fleet_receipt_chat_binding
          ON fleet_receipt_deliveries (
            surface, bot_identity, chat_id, delivered_at, id
          );
        """
    )
    connection.commit()
    return connection


def register_delivered_receipt(
    descriptor: ReceiptDescriptor,
    *,
    surface: str,
    bot_identity: str,
    chat_id: str,
    source_message_id: str,
    delivered_message_id: str,
    delivery_succeeded: bool,
    delivered_at: str | None = None,
    db_path: str | Path = DEFAULT_SQLITE_PATH,
) -> RegistrationResult:
    """Register only a proven successful delivery.

    The two early returns intentionally precede path creation and schema setup.
    A failed send or non-durable provider pointer therefore leaves no index
    artifact at all.
    """

    if delivery_succeeded is not True:
        return RegistrationResult("delivery_not_succeeded", False, "")
    if not descriptor.durable:
        return RegistrationResult("provider_receipt_not_durable", False, "")

    surface_value = _binding_value(surface, field_name="surface")
    bot_value = _binding_value(bot_identity, field_name="bot_identity").lower()
    chat_value = _binding_value(chat_id, field_name="chat_id")
    source_value = _binding_value(source_message_id, field_name="source_message_id")
    delivered_value = _binding_value(
        delivered_message_id,
        field_name="delivered_message_id",
    )
    delivered_timestamp = _timestamp(
        delivered_at or _utc_now(),
        field_name="delivered_at",
    )
    key = _delivery_key(
        descriptor,
        surface=surface_value,
        bot_identity=bot_value,
        chat_id=chat_value,
        source_message_id=source_value,
        delivered_message_id=delivered_value,
    )

    path = Path(db_path)
    with closing(_connect(path)) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT alias FROM fleet_receipt_deliveries WHERE delivery_key=?",
                (key,),
            ).fetchone()
            if existing is not None:
                connection.commit()
                return RegistrationResult("already_registered", False, str(existing["alias"]))

            alias = ""
            for attempt in range(_MAX_ALIAS_ATTEMPTS):
                candidate = _alias_candidate(key, attempt).upper()
                if not _ALIAS_RE.fullmatch(candidate):
                    raise ValueError("alias generator produced an invalid human alias")
                collision = connection.execute(
                    "SELECT delivery_key FROM fleet_receipt_deliveries WHERE alias=? COLLATE NOCASE",
                    (candidate,),
                ).fetchone()
                if collision is None:
                    alias = candidate
                    break
            if not alias:
                raise RuntimeError("unable to allocate a collision-safe receipt alias")

            connection.execute(
                """
                INSERT INTO fleet_receipt_deliveries (
                  delivery_key, alias, provider, owning_backend, raw_ref,
                  surface, bot_identity, chat_id, source_message_id,
                  delivered_message_id, delivered_at, what_happened, status,
                  occurred_at, authority_summary, no_action_facts_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    alias,
                    descriptor.provider,
                    descriptor.owning_backend,
                    descriptor.raw_ref,
                    surface_value,
                    bot_value,
                    chat_value,
                    source_value,
                    delivered_value,
                    delivered_timestamp,
                    descriptor.what_happened,
                    descriptor.status,
                    descriptor.occurred_at,
                    descriptor.authority_summary,
                    json.dumps(
                        descriptor.no_action_facts,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                ),
            )
            connection.commit()
    return RegistrationResult("registered", True, alias)


def _safe_rows(path: Path, sql: str, values: tuple[Any, ...]) -> list[sqlite3.Row]:
    if not path.is_file():
        return []
    try:
        with closing(sqlite3.connect(str(path), timeout=0.5)) as connection:
            connection.row_factory = sqlite3.Row
            return list(connection.execute(sql, values).fetchall())
    except sqlite3.Error as exc:
        raise ReceiptIndexUnavailable("fleet receipt index unavailable") from exc


def _require_operator_safe(text: str, *, context: str) -> None:
    """Validate generated operator text without the guard's fail-open wrapper."""

    try:
        from operator_surface_guard import check_operator_surface

        verdict = check_operator_surface(text, agent_role="OPENCLAW_SYSTEM")
    except Exception as exc:
        raise ValueError(f"{context} could not be validated for the operator surface") from exc
    if not verdict.safe_for_operator:
        raise ValueError(f"{context} is not safe for the operator surface")


def _render_human_receipt(row: Mapping[str, Any]) -> str:
    try:
        no_actions = tuple(json.loads(str(row["no_action_facts_json"])))
    except (KeyError, TypeError, json.JSONDecodeError):
        no_actions = ()
    if not no_actions:
        raise ValueError("receipt row has no bounded no-action facts")

    text = "\n".join(
        (
            f"Receipt {row['alias']}",
            f"What happened: {row['what_happened']}",
            f"Status: {row['status']}",
            f"When: {row['occurred_at']}",
            f"Authority: {row['authority_summary']}",
            "No-action facts: " + " ".join(_clean(item) for item in no_actions),
        )
    )
    raw_ref = str(row.get("raw_ref", "") if isinstance(row, dict) else row["raw_ref"])
    owning_backend = str(
        row.get("owning_backend", "") if isinstance(row, dict) else row["owning_backend"]
    )
    if raw_ref and raw_ref.casefold() in text.casefold():
        raise ValueError("raw receipt reference reached the human renderer")
    if owning_backend and owning_backend.casefold() in text.casefold():
        raise ValueError("owning backend reached the human renderer")

    _require_operator_safe(text, context="human receipt summary")
    return text


def _clarification(rows: list[sqlite3.Row]) -> ReceiptResolution:
    visible_rows = rows[:_MAX_CLARIFICATION_CANDIDATES]
    aliases = tuple(str(row["alias"]) for row in visible_rows)
    lines = [
        "I found several delivered receipts in this chat. The safest lookup is to reply "
        "to the original message, or ask for one of these aliases:"
    ]
    lines.extend(f"- {row['alias']} — {row['what_happened']}" for row in visible_rows)
    if len(rows) > len(visible_rows):
        lines.append("- More delivered records exist; the original message narrows the lookup.")
    text = "\n".join(lines)

    _require_operator_safe(text, context="receipt clarification")
    return ReceiptResolution("clarify", text, aliases)


def resolve_receipt_lookup(
    *,
    surface: str,
    bot_identity: str,
    chat_id: str,
    reply_to_message_id: str = "",
    alias: str = "",
    db_path: str | Path = DEFAULT_SQLITE_PATH,
) -> ReceiptResolution:
    surface_value = _binding_value(surface, field_name="surface")
    bot_value = _binding_value(bot_identity, field_name="bot_identity").lower()
    chat_value = _binding_value(chat_id, field_name="chat_id")
    reply_value = _clean(reply_to_message_id)
    alias_value = _clean(alias).upper()
    path = Path(db_path)

    if alias_value and not _ALIAS_RE.fullmatch(alias_value):
        return ReceiptResolution("not_found", _NOT_FOUND_TEXT)

    base_where = "surface=? AND bot_identity=? AND chat_id=?"
    values: list[Any] = [surface_value, bot_value, chat_value]
    if alias_value:
        base_where += " AND alias=? COLLATE NOCASE"
        values.append(alias_value)
    if reply_value:
        base_where += " AND delivered_message_id=?"
        values.append(reply_value)
    rows = _safe_rows(
        path,
        f"""
        SELECT * FROM fleet_receipt_deliveries
        WHERE {base_where}
        ORDER BY delivered_at DESC, id DESC
        LIMIT {_MAX_CLARIFICATION_CANDIDATES + 1}
        """,
        tuple(values),
    )

    if not rows and alias_value:
        same_binding_alias = _safe_rows(
            path,
            """
            SELECT id FROM fleet_receipt_deliveries
            WHERE surface=? AND bot_identity=? AND chat_id=?
              AND alias=? COLLATE NOCASE
            LIMIT 1
            """,
            (surface_value, bot_value, chat_value, alias_value),
        )
        if same_binding_alias:
            return ReceiptResolution("not_found", _NOT_FOUND_TEXT)
        alias_exists = _safe_rows(
            path,
            "SELECT id FROM fleet_receipt_deliveries WHERE alias=? COLLATE NOCASE LIMIT 1",
            (alias_value,),
        )
        if alias_exists:
            return ReceiptResolution("cross_chat_denied", _CROSS_CHAT_DENIED_TEXT)
    if not rows:
        return ReceiptResolution("not_found", _NOT_FOUND_TEXT)
    if len(rows) > 1:
        return _clarification(rows)
    row = rows[0]
    return ReceiptResolution(
        "found",
        _render_human_receipt(row),
        (str(row["alias"]),),
    )


def parse_receipt_request(text: str) -> ReceiptRequest | None:
    match = _SHOW_RECEIPT_RE.fullmatch(str(text or ""))
    if match is None:
        return None
    alias = _clean(match.group("alias")).upper()
    return ReceiptRequest(alias=alias)


def resolve_receipt_request(
    text: str,
    *,
    surface: str,
    bot_identity: str,
    chat_id: str,
    reply_to_message_id: str = "",
    db_path: str | Path = DEFAULT_SQLITE_PATH,
) -> ReceiptResolution | None:
    request = parse_receipt_request(text)
    if request is None:
        return None
    return resolve_receipt_lookup(
        surface=surface,
        bot_identity=bot_identity,
        chat_id=chat_id,
        reply_to_message_id=reply_to_message_id,
        alias=request.alias,
        db_path=db_path,
    )


class FleetReceiptIndex:
    """Small path-bound facade; every operation reopens durable SQLite state."""

    def __init__(self, db_path: str | Path = DEFAULT_SQLITE_PATH) -> None:
        self.db_path = Path(db_path)

    def register(self, descriptor: ReceiptDescriptor, **delivery: Any) -> RegistrationResult:
        return register_delivered_receipt(
            descriptor,
            db_path=self.db_path,
            **delivery,
        )

    def resolve(self, **query: Any) -> ReceiptResolution:
        return resolve_receipt_lookup(db_path=self.db_path, **query)

    def resolve_request(self, text: str, **query: Any) -> ReceiptResolution | None:
        return resolve_receipt_request(text, db_path=self.db_path, **query)

    def count(self) -> int:
        rows = _safe_rows(
            self.db_path,
            "SELECT COUNT(*) AS receipt_count FROM fleet_receipt_deliveries",
            (),
        )
        return int(rows[0]["receipt_count"]) if rows else 0


__all__ = [
    "DEFAULT_SQLITE_PATH",
    "HUMAN_RECEIPT_LOOKUP_HINT",
    "PROVIDER_BACKENDS",
    "SCHEMA_VERSION",
    "SUPPORTED_PROVIDERS",
    "FleetReceiptIndex",
    "ReceiptDescriptor",
    "ReceiptIndexUnavailable",
    "ReceiptProvider",
    "ReceiptRequest",
    "ReceiptResolution",
    "RegistrationResult",
    "build_receipt_descriptor",
    "human_receipt_hint",
    "machine_receipt_disclosure",
    "parse_receipt_request",
    "register_delivered_receipt",
    "render_receipt_safe_visible_text",
    "resolve_receipt_lookup",
    "resolve_receipt_request",
]
