"""The agent_lanes table, made real — and deliberately empty of secrets.

`tests/test_t016_synthetic_e2e.py` has asserted for months that
`agent_lanes.telegram_bot_username` holds `@openclaw_cassandra_bot`. No production
CREATE TABLE ever existed, so the contract was true only inside a fixture. That gap
is why identity fell back to human search over display names, and why a message for
Cassandra reached a person named Carter.

This materialises the schema and seeds it from `agent_telegram_identity`, so there
is exactly one place a username is written down.

**No token, secret, or credential is stored, read, or referenced here.** The bot
tokens live in the environment and are none of this module's business. A username is
public — it is what a stranger sees in a chat header — and that is precisely why it
is safe to keep as declarative config and unsafe to guess at runtime.

**Verification state is separate from declaration.** A seeded row is a *claim* that
`@openclaw_cassandra_bot` is Cassandra. Only a live check against Telegram can turn
that into a fact, and that check needs a token, so it is the operator's to run. Rows
therefore carry `verified_at`, empty until then, and `resolve_lane` refuses an
unverified row when `require_verified=True`. Fail closed: declaring is not proving.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from agent_telegram_identity import AGENT_IDENTITIES, normalize_agent, normalize_username

SCHEMA_VERSION = "agent_lanes_v1"

DEFAULT_REGISTRY_PATH = Path("/home/openclaw/.openclaw/agent_lanes.sqlite")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agent_lanes (
    agent_id                TEXT PRIMARY KEY,
    role                    TEXT NOT NULL,
    telegram_bot_username   TEXT NOT NULL UNIQUE,
    telegram_display_name   TEXT NOT NULL DEFAULT '',
    telegram_chat_id        TEXT NOT NULL DEFAULT '',
    verified_at             TEXT NOT NULL DEFAULT '',
    schema_version          TEXT NOT NULL
);
"""

UNVERIFIED = "lane_declared_but_not_live_verified"
NO_ROW = "no_lane_row_for_agent"
NO_CHAT_ID = "lane_has_no_chat_id"


class LaneRegistryError(RuntimeError):
    """Programmer error only; a refused lane is a Lane result, not an exception."""


@dataclass(frozen=True)
class Lane:
    ok: bool
    reason: str
    agent_id: str = ""
    username: str = ""
    chat_id: str = ""
    verified_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": self.ok,
            "reason": self.reason,
            "agent_id": self.agent_id,
            "telegram_bot_username": self.username,
            "telegram_chat_id": self.chat_id,
            "verified_at": self.verified_at,
        }


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    target = Path(path) if path else DEFAULT_REGISTRY_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def seed_rows(conn: sqlite3.Connection, *, identities: Mapping[str, Mapping[str, str]] | None = None) -> int:
    """Write one row per registered agent. Idempotent; never clears verification.

    Usernames come from ``agent_telegram_identity`` and nowhere else, so the seed
    cannot disagree with the resolver that consumes it.
    """

    table = identities or AGENT_IDENTITIES
    ensure_schema(conn)
    written = 0
    for agent, row in table.items():
        conn.execute(
            """INSERT INTO agent_lanes
                   (agent_id, role, telegram_bot_username, schema_version)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(agent_id) DO UPDATE SET
                   role = excluded.role,
                   telegram_bot_username = excluded.telegram_bot_username,
                   schema_version = excluded.schema_version""",
            (normalize_agent(agent), row["role"], normalize_username(row["username"]), SCHEMA_VERSION),
        )
        written += 1
    conn.commit()
    return written


def resolve_lane(
    conn: sqlite3.Connection,
    agent: str,
    *,
    require_verified: bool = True,
) -> Lane:
    """The runtime lookup. Refuses an unverified lane by default.

    ``require_verified=False`` exists for reporting and tests, never for sending.
    """

    key = normalize_agent(agent)
    cur = conn.execute(
        "SELECT agent_id, telegram_bot_username, telegram_chat_id, verified_at "
        "FROM agent_lanes WHERE agent_id = ?",
        (key,),
    )
    row = cur.fetchone()
    if row is None:
        return Lane(False, NO_ROW, agent_id=key)

    username = str(row["telegram_bot_username"] or "")
    chat_id = str(row["telegram_chat_id"] or "")
    verified_at = str(row["verified_at"] or "")

    if require_verified and not verified_at:
        return Lane(False, UNVERIFIED, agent_id=key, username=username, chat_id=chat_id)
    if not chat_id:
        return Lane(False, NO_CHAT_ID, agent_id=key, username=username, verified_at=verified_at)
    return Lane(True, "resolved", agent_id=key, username=username,
                chat_id=chat_id, verified_at=verified_at)


def record_live_verification(
    conn: sqlite3.Connection, agent: str, *, chat_id: str, username: str, verified_at: str
) -> None:
    """Called only after a real Telegram check. Requires the username to match.

    This is the one transition from claim to fact, so it refuses to record a
    verification for a username the registry does not declare.
    """

    key = normalize_agent(agent)
    declared = normalize_username(AGENT_IDENTITIES.get(key, {}).get("username", ""))
    if not declared or normalize_username(username) != declared:
        raise LaneRegistryError(
            f"refusing to verify {key} as {username!r}: registry declares {declared!r}"
        )
    if not str(chat_id).strip():
        raise LaneRegistryError("refusing to verify a lane with no chat_id")
    conn.execute(
        "UPDATE agent_lanes SET telegram_chat_id = ?, verified_at = ? WHERE agent_id = ?",
        (str(chat_id).strip(), str(verified_at).strip(), key),
    )
    conn.commit()


def lane_report(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    ensure_schema(conn)
    return [
        dict(resolve_lane(conn, agent, require_verified=False).to_dict())
        for agent in sorted(AGENT_IDENTITIES)
    ]


__all__ = [
    "DEFAULT_REGISTRY_PATH",
    "Lane",
    "LaneRegistryError",
    "NO_CHAT_ID",
    "NO_ROW",
    "SCHEMA_SQL",
    "SCHEMA_VERSION",
    "UNVERIFIED",
    "connect",
    "ensure_schema",
    "lane_report",
    "record_live_verification",
    "resolve_lane",
    "seed_rows",
]
