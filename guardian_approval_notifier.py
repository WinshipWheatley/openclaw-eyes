"""Guardian approval notifier — push every pending approval to the operator's Telegram.

Operator directive 2026-07-02: "guardian should send me an approval request via
telegram to allow any action." chief_approval_brain already pushes its own
requests at creation; this sweeper is the GUARANTEE layer: it watches the
canonical pending sources and notifies anything unnotified (e.g. a request
created while the bot was down, or filed by a surface that never pushes).

- Chief single-flight pending file → live YES:{id}/NO:{id} buttons (the exact
  callback tokens chief_guardian_listener.record_decision validates).
- Shadow/observational requests (guardian_hitl_approval_requests) → an
  informational alert WITHOUT buttons (no dead-end keyboards for token families
  the listener does not handle) naming the source surface.
- Dedupe via a local state DB; a failed send is NOT marked notified, so it
  retries next cycle. Never mutates any authority store.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from guardian_approval_ui import (
    APPROVE_BUTTON_TEXT,
    DENY_BUTTON_TEXT,
    fallback_lines,
)

DEFAULT_PENDING_FILE = Path("/mnt/c/OpenClaw/logs/approval_pending.json")
DEFAULT_LEDGER = Path("/home/openclaw/.openclaw/business_ops/ledger.sqlite")
DEFAULT_STATE_DB = Path("/home/openclaw/.openclaw/guardian/approval_notifier_state.sqlite")

_SHADOW_PENDING_STATUSES = (
    "request_shadow_created",
    "cassandra_proposal_shadow_created",
)


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_ts(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _state_conn(state_db: Path) -> sqlite3.Connection:
    state_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(state_db)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS notified_approvals ("
        "notify_key TEXT PRIMARY KEY, source TEXT NOT NULL, notified_at TEXT NOT NULL)"
    )
    return conn


def _already_notified(conn: sqlite3.Connection, notify_key: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM notified_approvals WHERE notify_key=?", (notify_key,)
    ).fetchone()
    return row is not None


def _mark_notified(conn: sqlite3.Connection, notify_key: str, source: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO notified_approvals (notify_key, source, notified_at) VALUES (?,?,?)",
        (notify_key, source, _now().isoformat()),
    )
    conn.commit()


def _load_chief_pending(pending_file: Path) -> dict[str, Any] | None:
    try:
        if not pending_file.exists():
            return None
        data = json.loads(pending_file.read_text(encoding="utf-8") or "{}")
    except Exception:
        return None
    if not isinstance(data, dict) or not data.get("id"):
        return None
    if str(data.get("status") or "").strip().lower() != "pending":
        return None
    return data


def _chief_keyboard(approval_id: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": APPROVE_BUTTON_TEXT, "callback_data": f"YES:{approval_id}"},
                {"text": DENY_BUTTON_TEXT, "callback_data": f"NO:{approval_id}"},
            ],
            [
                {"text": "Delay 5m", "callback_data": f"DELAY:{approval_id}"},
                {"text": "Why now?", "callback_data": f"WHY:{approval_id}"},
            ],
        ]
    }


def _load_shadow_pending(ledger_path: Path) -> list[dict[str, Any]]:
    try:
        conn = sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    try:
        placeholders = ",".join("?" for _ in _SHADOW_PENDING_STATUSES)
        rows = conn.execute(
            "SELECT approval_id, source_surface_id, action_summary_label, risk_tier, "
            "status, requested_at, expires_at FROM guardian_hitl_approval_requests "
            f"WHERE status IN ({placeholders})",
            _SHADOW_PENDING_STATUSES,
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    now = _now()
    pending = []
    for approval_id, surface, label, tier, status, requested_at, expires_at in rows:
        expires = _parse_ts(expires_at)
        if expires is not None and expires <= now:
            continue
        pending.append(
            {
                "approval_id": str(approval_id or ""),
                "surface": str(surface or "unknown_surface"),
                "label": str(label or "Approval request"),
                "tier": str(tier or ""),
                "status": str(status or ""),
                "requested_at": str(requested_at or ""),
            }
        )
    return pending


DEFAULT_BOARD_DB = Path("/home/openclaw/.openclaw/guardian/approval_board_state.sqlite")


def _pending_for_board(pending_file: Path, ledger_path: Path) -> list[dict[str, Any]]:
    """Assemble the current pending-approval set in the shape the board humanizer expects.
    supersede_key groups approvals so a changed re-issue retires the older one."""
    out: list[dict[str, Any]] = []
    chief = _load_chief_pending(pending_file)
    if chief is not None:
        ctx = chief.get("approval_context") if isinstance(chief.get("approval_context"), dict) else {}
        action = str(chief.get("action") or "")
        out.append({
            "id": str(chief.get("id")),
            "requester": str(chief.get("requester") or "the system"),
            "tier": chief.get("tier"),
            "action": action,
            "approval_context": ctx,
            # same requester+action-intent re-issued => supersede the prior one
            "supersede_key": f"chief:{chief.get('requester')}:{action[:40]}",
        })
    # NOTE: guardian_hitl "*_shadow_created" records are OBSERVATIONAL dual-writes of legacy
    # approvals — they have NO live YES/NO executor (record_decision validates against the
    # chief pending file, which these are not in). Surfacing them on the board would give the
    # operator dead approve/deny buttons. So the board carries only ACTIONABLE approvals: the
    # chief single-flight pending file (real YES/NO), plus (future) build-PROPOSED tasks.
    del ledger_path  # observational shadows intentionally excluded from the actionable board
    return out


def run_board(
    *,
    pending_file: str | Path = DEFAULT_PENDING_FILE,
    ledger_path: str | Path = DEFAULT_LEDGER,
    board_db: str | Path = DEFAULT_BOARD_DB,
    ops: Any | None = None,
) -> dict[str, Any]:
    """Reconcile the human-readable Guardian approval BOARD (humanized messages + buttons,
    green checkmark when clear, stale/superseded retired). This is the timer entry point."""
    from guardian_approval_board import sync_board
    if ops is None:
        from guardian_telegram_ops import GuardianTelegramOps
        ops = GuardianTelegramOps()
    pending = _pending_for_board(Path(pending_file), Path(ledger_path))
    return sync_board(pending, ops=ops, state_db=board_db)


def _default_sender(message: str, reply_markup: dict | None = None) -> None:
    from chief_guardian_sender import send_approval

    send_approval(message, reply_markup=reply_markup)


def run_once(
    *,
    pending_file: str | Path = DEFAULT_PENDING_FILE,
    ledger_path: str | Path = DEFAULT_LEDGER,
    state_db: str | Path = DEFAULT_STATE_DB,
    sender: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    sender = sender or _default_sender
    conn = _state_conn(Path(state_db))
    notified = 0
    skipped = 0
    errors: list[str] = []
    chief_ids: set[str] = set()
    try:
        chief = _load_chief_pending(Path(pending_file))
        if chief is not None:
            approval_id = str(chief["id"])
            chief_ids.add(approval_id)
            notify_key = f"chief:{approval_id}:{chief.get('hash') or chief.get('requested_at') or ''}"
            if _already_notified(conn, notify_key):
                skipped += 1
            else:
                message = (
                    "GUARDIAN APPROVAL NEEDED\n"
                    f"Action: {str(chief.get('action') or '')[:400]}\n"
                    f"Requester: {chief.get('requester') or 'unknown'} | Tier: {chief.get('tier')}\n"
                    f"Requested: {chief.get('requested_at')}\n"
                    f"ID: {approval_id}\n\n"
                    + "\n".join(fallback_lines(approval_id))
                )
                try:
                    sender(message, reply_markup=_chief_keyboard(approval_id))
                    _mark_notified(conn, notify_key, "chief_pending_file")
                    notified += 1
                except Exception as exc:
                    errors.append(f"chief:{approval_id}:{type(exc).__name__}")

        for shadow in _load_shadow_pending(Path(ledger_path)):
            approval_id = shadow["approval_id"]
            if not approval_id or approval_id in chief_ids:
                skipped += 1
                continue
            notify_key = f"shadow:{approval_id}:{shadow['requested_at']}"
            if _already_notified(conn, notify_key):
                skipped += 1
                continue
            message = (
                "GUARDIAN: approval waiting (no live buttons for this surface yet)\n"
                f"What: {shadow['label'][:300]}\n"
                f"Surface: {shadow['surface']} | Tier: {shadow['tier']} | Status: {shadow['status']}\n"
                f"ID: {approval_id} | Requested: {shadow['requested_at']}\n"
                "Approve/deny at the keyboard or tell Fable via this channel."
            )
            try:
                sender(message, reply_markup=None)
                _mark_notified(conn, notify_key, shadow["surface"])
                notified += 1
            except Exception as exc:
                errors.append(f"shadow:{approval_id}:{type(exc).__name__}")
    finally:
        conn.close()
    return {"notified": notified, "skipped": skipped, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sweep pending approvals to operator Telegram.")
    parser.add_argument("--once", action="store_true", help="run one sweep (timer entry point)")
    parser.add_argument("--board", action="store_true", help="reconcile the human approval board (humanized + checkmark + supersede)")
    parser.add_argument("--pending-file", default=str(DEFAULT_PENDING_FILE))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--state-db", default=str(DEFAULT_STATE_DB))
    args = parser.parse_args(argv)
    if getattr(args, "board", False):
        summary = run_board(pending_file=args.pending_file, ledger_path=args.ledger)
    else:
        summary = run_once(
            pending_file=args.pending_file, ledger_path=args.ledger, state_db=args.state_db
        )
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
