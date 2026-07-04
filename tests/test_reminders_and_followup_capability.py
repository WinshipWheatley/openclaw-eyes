from __future__ import annotations

from pathlib import Path

from client_followup_watch import ClientFollowupWatchStore
from reminders_store import ReminderStore


def test_reminder_persists_and_surfaces_only_when_due(tmp_path: Path) -> None:
    db_path = tmp_path / "reminders.sqlite3"
    store = ReminderStore(str(db_path))
    reminder = store.add_reminder(
        text="remind me to deposit the Capital Hilton check",
        due_at_utc_iso="2026-07-04T21:00:00+00:00",
        created_at_utc_iso="2026-07-04T12:00:00+00:00",
    )

    assert store.due_reminders("2026-07-04T20:59:59+00:00") == []

    reopened = ReminderStore(str(db_path))
    due = reopened.due_reminders("2026-07-04T21:00:00+00:00")

    assert due == [
        {
            "reminder_id": reminder["reminder_id"],
            "text": "remind me to deposit the Capital Hilton check",
            "due_at_utc_iso": "2026-07-04T21:00:00+00:00",
            "created_at_utc_iso": "2026-07-04T12:00:00+00:00",
            "status": "active",
            "surface_only": True,
        }
    ]


def test_followup_watch_no_reply_after_window_proposes_gated_draft(tmp_path: Path) -> None:
    db_path = tmp_path / "followups.sqlite3"
    store = ClientFollowupWatchStore(str(db_path))
    watch = store.add_watch(
        client_ref="st_annes",
        client_name="St. Anne's",
        recipient="draper.carter@gmail.com",
        subject="Invoice ST-ANNES-REAL-2026-06",
        sent_at_utc_iso="2026-07-01T10:00:00+00:00",
        invoice_ref="ST-ANNES-REAL-2026-06",
        days_without_reply=3,
    )

    assert store.due_followup_proposals("2026-07-04T10:00:00+00:00") == []
    proposals = store.due_followup_proposals("2026-07-05T10:00:00+00:00")

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal["schema_version"] == "client_followup_proposal_v0"
    assert proposal["status"] == "FOLLOW_UP_PROPOSAL_READY"
    assert proposal["watch_id"] == watch["watch_id"]
    assert proposal["gated"] is True
    assert proposal["send_performed"] is False
    assert proposal["authority_boundary"]["send_performed"] is False
    assert proposal["authority_boundary"]["send_hold_required"] is True
    assert proposal["approval_request"]["schema_version"] == "OPERATOR_ACTION_APPROVAL_REQUEST_V0"
    assert proposal["approval_request"]["action_type"] == "exact_gmail_send"
    assert proposal["approval_request"]["payload"]["to"] == "draper.carter@gmail.com"
    assert "ST-ANNES-REAL-2026-06" in proposal["draft"]["body"]


def test_followup_watch_reply_seen_closes_watch_and_suppresses_proposal(tmp_path: Path) -> None:
    db_path = tmp_path / "followups.sqlite3"
    store = ClientFollowupWatchStore(str(db_path))
    watch = store.add_watch(
        client_ref="st_annes",
        client_name="St. Anne's",
        recipient="draper.carter@gmail.com",
        subject="Invoice ST-ANNES-REAL-2026-06",
        sent_at_utc_iso="2026-07-01T10:00:00+00:00",
        invoice_ref="ST-ANNES-REAL-2026-06",
        days_without_reply=3,
    )

    closed = store.record_reply_seen(
        watch["watch_id"],
        reply_seen_at_utc_iso="2026-07-03T09:30:00+00:00",
        reply_ref="gmail:reply:123",
    )

    assert closed["status"] == "closed_reply_seen"
    assert closed["reply_ref"] == "gmail:reply:123"
    assert store.due_followup_proposals("2026-07-05T10:00:00+00:00") == []
