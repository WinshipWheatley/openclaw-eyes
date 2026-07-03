"""run_board assembles real pending sources into the humanized board (integration)."""

import json
import sqlite3
from pathlib import Path

import guardian_approval_notifier as gan


class FakeOps:
    def __init__(self): self.sent = {}; self._n = 1
    def send(self, text, buttons=None):
        m = self._n; self._n += 1; self.sent[m] = {"text": text, "buttons": buttons, "deleted": False}; return m
    def edit(self, message_id, text, buttons=None):
        if message_id in self.sent: self.sent[message_id]["text"] = text
    def delete(self, message_id):
        if message_id in self.sent: self.sent[message_id]["deleted"] = True
    def live(self): return [v for v in self.sent.values() if not v["deleted"]]


def _ledger(tmp_path):
    db = tmp_path / "ledger.sqlite"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE guardian_hitl_approval_requests (approval_id TEXT, source_surface_id TEXT, "
              "action_summary_label TEXT, risk_tier TEXT, status TEXT, requested_at TEXT, expires_at TEXT)")
    c.commit(); c.close()
    return db


def test_run_board_humanizes_chief_pending(tmp_path):
    pf = tmp_path / "approval_pending.json"
    pf.write_text(json.dumps({
        "id": "Z9", "requester": "Cassandra", "tier": 2, "status": "pending",
        "action": "Send invoice email to Capital Hilton",
        "approval_context": {"to": "ap@capitalhilton.com", "subject": "June invoice"},
    }))
    ops = FakeOps()
    s = gan.run_board(pending_file=pf, ledger_path=_ledger(tmp_path),
                      board_db=tmp_path / "board.sqlite", ops=ops)
    assert s["active"] == 1
    msg = ops.live()[0]
    assert "email" in msg["text"].lower() and "capitalhilton" in msg["text"].lower()
    assert "{" not in msg["text"] and "approval_context" not in msg["text"]
    labels = [b["callback_data"] for row in msg["buttons"]["inline_keyboard"] for b in row]
    assert "YES:Z9" in labels and "NO:Z9" in labels


def test_run_board_posts_checkmark_when_empty(tmp_path):
    ops = FakeOps()
    s = gan.run_board(pending_file=tmp_path / "none.json", ledger_path=_ledger(tmp_path),
                      board_db=tmp_path / "board.sqlite", ops=ops)
    assert s["active"] == 0
    assert any("✅" in v["text"] for v in ops.live())
