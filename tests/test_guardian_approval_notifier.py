"""Guardian approval notifier — every pending approval reaches the operator's
Telegram (operator directive 2026-07-02: "guardian should send me an approval
request via telegram to allow any action").

Chief-tier pending entries get live YES:{id}/NO:{id} buttons (the exact tokens
chief_guardian_listener.record_decision validates). Shadow-only requests from
other surfaces get an informational alert (no dead-end buttons). Dedupe via a
local state DB; a failed send is NOT marked notified (retries next cycle).
"""

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import guardian_approval_notifier as gan


def _pending_file(tmp_path: Path, *, status="pending", approval_id="AB12CD34") -> Path:
    p = tmp_path / "approval_pending.json"
    p.write_text(json.dumps({
        "id": approval_id,
        "action": "Send the Capital Hilton invoice email",
        "requester": "Cassandra",
        "requested_at": "2026-07-02 15:00:00",
        "status": status,
        "options": 2,
        "tier": 2,
        "hash": "FEEDBEEF0001",
        "approval_context": {},
    }), encoding="utf-8")
    return p


def _ledger(tmp_path: Path, rows=()) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "ledger.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS guardian_hitl_approval_requests ("
        "approval_id TEXT, source_surface_id TEXT, action_summary_label TEXT,"
        "risk_tier TEXT, status TEXT, requested_at TEXT, expires_at TEXT)"
    )
    conn.execute("DELETE FROM guardian_hitl_approval_requests")
    conn.executemany(
        "INSERT INTO guardian_hitl_approval_requests VALUES (?,?,?,?,?,?,?)", rows
    )
    conn.commit()
    conn.close()
    return db_path


class _Sender:
    def __init__(self, explode=False):
        self.calls = []
        self.explode = explode

    def __call__(self, message, reply_markup=None):
        if self.explode:
            raise RuntimeError("bot down")
        self.calls.append({"message": message, "reply_markup": reply_markup})


def _future() -> str:
    return (datetime.now(UTC) + timedelta(hours=6)).isoformat()


def _past() -> str:
    return (datetime.now(UTC) - timedelta(hours=6)).isoformat()


def test_pending_chief_approval_notifies_with_live_buttons(tmp_path: Path):
    sender = _Sender()
    summary = gan.run_once(
        pending_file=_pending_file(tmp_path),
        ledger_path=_ledger(tmp_path),
        state_db=tmp_path / "state.sqlite",
        sender=sender,
    )
    assert summary["notified"] == 1
    call = sender.calls[0]
    assert "Capital Hilton" in call["message"]
    buttons = [b["callback_data"] for row in call["reply_markup"]["inline_keyboard"] for b in row]
    assert "YES:AB12CD34" in buttons and "NO:AB12CD34" in buttons

    # Second run: deduped, nothing sent.
    summary2 = gan.run_once(
        pending_file=_pending_file(tmp_path),
        ledger_path=_ledger(tmp_path),
        state_db=tmp_path / "state.sqlite",
        sender=sender,
    )
    assert summary2["notified"] == 0 and len(sender.calls) == 1


def test_decided_entry_not_notified(tmp_path: Path):
    sender = _Sender()
    summary = gan.run_once(
        pending_file=_pending_file(tmp_path, status="decided"),
        ledger_path=_ledger(tmp_path),
        state_db=tmp_path / "state.sqlite",
        sender=sender,
    )
    assert summary["notified"] == 0 and not sender.calls


def test_shadow_only_request_gets_info_alert_without_buttons(tmp_path: Path):
    rows = [("SHDW0001", "guardian_hitl_cassandra_proposal_shadow", "Cassandra outbound proposal",
             "tier_2", "cassandra_proposal_shadow_created", _past(), _future())]
    sender = _Sender()
    summary = gan.run_once(
        pending_file=tmp_path / "missing.json",
        ledger_path=_ledger(tmp_path, rows),
        state_db=tmp_path / "state.sqlite",
        sender=sender,
    )
    assert summary["notified"] == 1
    call = sender.calls[0]
    assert call["reply_markup"] is None
    assert "Cassandra outbound proposal" in call["message"]
    # dedupe on rerun
    gan.run_once(
        pending_file=tmp_path / "missing.json",
        ledger_path=_ledger(tmp_path, rows),
        state_db=tmp_path / "state.sqlite",
        sender=sender,
    )
    assert len(sender.calls) == 1


def test_shadow_of_active_chief_approval_is_skipped(tmp_path: Path):
    rows = [("AB12CD34", "chief_approval_brain", "Chief approval request",
             "tier_2", "request_shadow_created", _past(), _future())]
    sender = _Sender()
    summary = gan.run_once(
        pending_file=_pending_file(tmp_path),
        ledger_path=_ledger(tmp_path, rows),
        state_db=tmp_path / "state.sqlite",
        sender=sender,
    )
    # one chief notification (buttons), no duplicate info alert for its shadow
    assert summary["notified"] == 1 and len(sender.calls) == 1
    assert sender.calls[0]["reply_markup"] is not None


def test_expired_shadow_skipped(tmp_path: Path):
    rows = [("OLD00001", "guardian_hitl_cassandra_proposal_shadow", "Stale proposal",
             "tier_2", "cassandra_proposal_shadow_created", _past(), _past())]
    sender = _Sender()
    summary = gan.run_once(
        pending_file=tmp_path / "missing.json",
        ledger_path=_ledger(tmp_path, rows),
        state_db=tmp_path / "state.sqlite",
        sender=sender,
    )
    assert summary["notified"] == 0 and not sender.calls


def test_failed_send_is_retried_next_cycle(tmp_path: Path):
    exploding = _Sender(explode=True)
    summary = gan.run_once(
        pending_file=_pending_file(tmp_path),
        ledger_path=_ledger(tmp_path),
        state_db=tmp_path / "state.sqlite",
        sender=exploding,
    )
    assert summary["notified"] == 0 and summary["errors"]

    ok = _Sender()
    summary2 = gan.run_once(
        pending_file=_pending_file(tmp_path),
        ledger_path=_ledger(tmp_path),
        state_db=tmp_path / "state.sqlite",
        sender=ok,
    )
    assert summary2["notified"] == 1 and len(ok.calls) == 1
