"""The Guardian approval chat always resolves to a clean state the operator can trust:
either ACTIVE approvals that need him, or a single green checkmark meaning "all clear."
Stale/superseded approvals are retired so he never scrolls past a dead one.

Operator ask 2026-07-03: human messages + buttons; green checkmark is the LAST thing when
nothing's pending; a superseded/changed approval retires the older one.
"""

from pathlib import Path

import guardian_approval_board as board


class FakeOps:
    """Records Telegram send/edit/delete; assigns incrementing message ids."""
    def __init__(self):
        self.sent = {}      # message_id -> {"text", "buttons", "deleted"}
        self._next = 100

    def send(self, text, buttons=None):
        mid = self._next; self._next += 1
        self.sent[mid] = {"text": text, "buttons": buttons, "deleted": False}
        return mid

    def edit(self, message_id, text, buttons=None):
        if message_id in self.sent:
            self.sent[message_id].update({"text": text, "buttons": buttons})

    def delete(self, message_id):
        if message_id in self.sent:
            self.sent[message_id]["deleted"] = True

    def live(self):
        return {m: v for m, v in self.sent.items() if not v["deleted"]}


def _approval(aid, action, supersede_key=None, requester="Cassandra"):
    return {"id": aid, "requester": requester, "tier": 2, "action": action,
            "supersede_key": supersede_key or aid}


def test_pending_approval_sent_humanized_with_buttons(tmp_path):
    ops = FakeOps()
    a = _approval("A1", "Send invoice email to Capital Hilton")
    s = board.sync_board([a], ops=ops, state_db=tmp_path / "b.sqlite")
    assert s["active"] == 1
    (mid, msg), = ops.live().items() if len(ops.live()) == 1 else [(None, None)]
    assert "email" in msg["text"].lower() and "{" not in msg["text"]
    labels = [b["text"] for row in msg["buttons"]["inline_keyboard"] for b in row]
    assert any("approve" in l.lower() for l in labels) and any("deny" in l.lower() for l in labels)


def test_green_checkmark_is_last_when_nothing_pending(tmp_path):
    ops = FakeOps()
    board.sync_board([_approval("A1", "Send email")], ops=ops, state_db=tmp_path / "b.sqlite")
    # approval resolved -> next sweep has no pending
    s = board.sync_board([], ops=ops, state_db=tmp_path / "b.sqlite")
    assert s["active"] == 0
    live = list(ops.live().values())
    # The old request remains as a clean terminal record, and the checkmark is last.
    assert len(live) == 2
    assert any(item["text"] == "⏰ Expired" and item["buttons"] is None for item in live)
    assert "✅" in live[-1]["text"]
    assert "clear" in live[-1]["text"].lower()


def test_resolved_approval_message_is_retired(tmp_path):
    ops = FakeOps()
    board.sync_board([_approval("A1", "Send email")], ops=ops, state_db=tmp_path / "b.sqlite")
    a1_mid = next(iter(ops.sent))
    board.sync_board([], ops=ops, state_db=tmp_path / "b.sqlite")
    # The same message becomes a token-free terminal record with no keyboard.
    assert ops.sent[a1_mid]["text"] == "⏰ Expired"
    assert ops.sent[a1_mid]["buttons"] is None


def test_superseded_approval_retires_the_older(tmp_path):
    ops = FakeOps()
    db = tmp_path / "b.sqlite"
    board.sync_board([_approval("A1", "Send invoice for $500", supersede_key="hilton-invoice")],
                     ops=ops, state_db=db)
    old_mid = next(iter(ops.sent))
    # a new approval, SAME supersede_key, changed content -> old must retire, new appears
    board.sync_board([_approval("A2", "Send invoice for $2000", supersede_key="hilton-invoice")],
                     ops=ops, state_db=db)
    assert ops.sent[old_mid]["deleted"] or "supersed" in ops.sent[old_mid]["text"].lower()
    live_texts = " ".join(v["text"] for v in ops.live().values())
    assert "2000" in live_texts and "500" not in live_texts


def test_no_duplicate_checkmark_when_already_clear(tmp_path):
    ops = FakeOps()
    db = tmp_path / "b.sqlite"
    board.sync_board([], ops=ops, state_db=db)     # already clear -> one checkmark
    board.sync_board([], ops=ops, state_db=db)     # still clear -> must NOT stack a second
    checkmarks = [v for v in ops.live().values() if "✅" in v["text"]]
    assert len(checkmarks) == 1


def test_new_approval_removes_the_stale_checkmark(tmp_path):
    ops = FakeOps()
    db = tmp_path / "b.sqlite"
    board.sync_board([], ops=ops, state_db=db)     # checkmark posted
    board.sync_board([_approval("A1", "Send email")], ops=ops, state_db=db)  # now something pending
    # the "all clear" checkmark must be gone so it doesn't lie
    live = ops.live().values()
    assert not any("✅" in v["text"] and "clear" in v["text"].lower() for v in live)
