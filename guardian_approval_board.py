"""Stateful Guardian approval BOARD — the operator's approval chat always resolves to a
state he can trust: active approvals that need him, or a single green checkmark = all clear.

Operator ask 2026-07-03:
- human messages + working approve/deny buttons (via guardian_approval_humanizer);
- when nothing is pending, a green checkmark is the LAST thing so he knows he's not missing one;
- a superseded/changed approval retires the older message (no dead approvals to scroll past).

``ops`` is an injected Telegram interface (send/edit/delete returning message ids), so this
is fully testable without Telegram. The live wiring passes a real bot-API adapter.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Mapping, Protocol

from guardian_approval_ui import APPROVE_BUTTON_TEXT, DENY_BUTTON_TEXT
from guardian_approval_humanizer import humanize_approval, render_operator_message


DEFAULT_STATE_DB = Path("/home/openclaw/.openclaw/guardian/approval_board_state.sqlite")


class TelegramOps(Protocol):
    def send(self, text: str, buttons: dict | None = None) -> int: ...
    def edit(self, message_id: int, text: str, buttons: dict | None = None) -> None: ...
    def delete(self, message_id: int) -> None: ...


# Callback tokens the Guardian listener already validates. Build-lane approvals use
# BUILDOK/BUILDNO (handle_build_approval); everything else uses YES/NO (record_decision).
def _buttons(approval_id: str, *, kind: str = "generic") -> dict:
    if kind == "build":
        return {"inline_keyboard": [[
            {"text": APPROVE_BUTTON_TEXT, "callback_data": f"BUILDOK:{approval_id}"},
            {"text": DENY_BUTTON_TEXT, "callback_data": f"BUILDNO:{approval_id}"},
        ]]}
    return {"inline_keyboard": [[
        {"text": APPROVE_BUTTON_TEXT, "callback_data": f"YES:{approval_id}"},
        {"text": DENY_BUTTON_TEXT, "callback_data": f"NO:{approval_id}"},
    ], [
        {"text": "❔ Why now?", "callback_data": f"WHY:{approval_id}"},
        {"text": "⏳ Later", "callback_data": f"DELAY:{approval_id}"},
    ]]}


def _content_hash(approval: Mapping[str, Any]) -> str:
    basis = "|".join(str(approval.get(k, "")) for k in ("action", "action_summary_label", "target"))
    ctx = approval.get("approval_context")
    if isinstance(ctx, Mapping):
        basis += "|" + "|".join(f"{k}={ctx[k]}" for k in sorted(ctx))
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def _approval_id(approval: Mapping[str, Any]) -> str:
    return str(approval.get("id") or approval.get("approval_id") or "")


def _supersede_key(approval: Mapping[str, Any]) -> str:
    return str(approval.get("supersede_key") or _approval_id(approval))


def _conn(state_db: str | Path) -> sqlite3.Connection:
    path = Path(state_db)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS board_active ("
        "approval_id TEXT PRIMARY KEY, supersede_key TEXT, content_hash TEXT,"
        "message_id INTEGER NOT NULL, sent_at TEXT)"
    )
    conn.execute("CREATE TABLE IF NOT EXISTS board_meta (k TEXT PRIMARY KEY, v TEXT)")
    return conn


def _get_checkmark(conn) -> int | None:
    row = conn.execute("SELECT v FROM board_meta WHERE k='checkmark_mid'").fetchone()
    return int(row[0]) if row and row[0] else None


def _set_checkmark(conn, mid: int | None) -> None:
    if mid is None:
        conn.execute("DELETE FROM board_meta WHERE k='checkmark_mid'")
    else:
        conn.execute("INSERT OR REPLACE INTO board_meta (k, v) VALUES ('checkmark_mid', ?)", (str(mid),))


def mark_resolved(approval_id: str, *, state_db: str | Path = DEFAULT_STATE_DB) -> bool:
    """Stop board reconciliation from overwriting a listener-rendered outcome."""

    if not str(approval_id or ""):
        return False
    conn = _conn(state_db)
    try:
        cursor = conn.execute("DELETE FROM board_active WHERE approval_id=?", (str(approval_id),))
        conn.commit()
        return bool(cursor.rowcount)
    finally:
        conn.close()


def sync_board(
    pending: list[Mapping[str, Any]],
    *,
    ops: TelegramOps,
    state_db: str | Path,
) -> dict[str, Any]:
    """Reconcile the Telegram approval board with the current pending set."""
    conn = _conn(state_db)
    sent = retired = superseded = 0
    try:
        active = {
            r[0]: {"supersede_key": r[1], "content_hash": r[2], "message_id": r[3]}
            for r in conn.execute("SELECT approval_id, supersede_key, content_hash, message_id FROM board_active")
        }
        pending_by_id = {_approval_id(a): a for a in pending if _approval_id(a)}
        pending_keys = {_supersede_key(a) for a in pending_by_id.values()}

        # 1) Retire approvals that are no longer pending (resolved), and supersede-collisions.
        for aid, meta in list(active.items()):
            still_pending = aid in pending_by_id
            key_superseded = (meta["supersede_key"] in pending_keys and aid not in pending_by_id)
            if not still_pending:
                try:
                    if key_superseded:
                        ops.edit(meta["message_id"], "↻ Superseded by a newer request — no action needed.")
                        superseded += 1
                    else:
                        ops.edit(meta["message_id"], "⏰ Expired", buttons=None)
                        retired += 1
                except Exception:
                    pass
                conn.execute("DELETE FROM board_active WHERE approval_id=?", (aid,))
                active.pop(aid, None)

        # 2) Send new pending approvals (and re-send content-changed ones under a new id).
        for aid, approval in pending_by_id.items():
            chash = _content_hash(approval)
            existing = active.get(aid)
            if existing and existing["content_hash"] == chash:
                continue  # already on the board, unchanged
            if existing and existing["content_hash"] != chash:
                try:
                    ops.delete(existing["message_id"])
                except Exception:
                    pass
                conn.execute("DELETE FROM board_active WHERE approval_id=?", (aid,))
            human = humanize_approval(approval)
            text = render_operator_message(human)
            mid = ops.send(text, _buttons(aid, kind=human.get("kind", "generic")))
            conn.execute(
                "INSERT OR REPLACE INTO board_active (approval_id, supersede_key, content_hash, message_id, sent_at)"
                " VALUES (?,?,?,?, datetime('now'))",
                (aid, _supersede_key(approval), chash, int(mid)),
            )
            sent += 1

        # 3) Green checkmark discipline: when nothing is pending, a single ✅ is the last thing;
        #    when something IS pending, no stale checkmark may linger.
        remaining = conn.execute("SELECT COUNT(*) FROM board_active").fetchone()[0]
        checkmark_mid = _get_checkmark(conn)
        if remaining == 0:
            if checkmark_mid is None:
                mid = ops.send("✅ All clear — no approvals waiting.")
                _set_checkmark(conn, mid)
        else:
            if checkmark_mid is not None:
                try:
                    ops.delete(checkmark_mid)
                except Exception:
                    pass
                _set_checkmark(conn, None)

        conn.commit()
        return {"active": remaining, "sent": sent, "retired": retired, "superseded": superseded}
    finally:
        conn.close()


__all__ = ["mark_resolved", "sync_board", "TelegramOps"]
