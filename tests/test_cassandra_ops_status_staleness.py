"""Tests for the Cassandra ops-status staleness rule (task 143, CLASS #4).

Live evidence (pass-1): Cassandra's orientation reply presented a 55-day-stale
Operator/GENERATED_CURRENT_STATE.md as "now". business_ops_intent.py already classifies
bare "status" correctly (bounded fallback) -- the bug is that _build_ops_status_packet had
no staleness check on the doc content it reads. These tests pin the fix: a doc whose latest
embedded date is past the SLA is never presented as current.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cassandra_brain


def _iso(d: date) -> str:
    return d.isoformat()


class TestMarkdownDocLatestDate:
    def test_finds_latest_of_several_embedded_dates(self):
        content = "- 2026-05-10 22:37 [PASS] foo\n- 2026-05-13 19:01 [PASS] bar\n- 2026-04-01 [PASS] old"
        assert cassandra_brain._markdown_doc_latest_date(content) == date(2026, 5, 13)

    def test_no_embedded_dates_returns_none(self):
        assert cassandra_brain._markdown_doc_latest_date("no dates here") is None

    def test_ignores_malformed_date_like_tokens(self):
        content = "2026-13-99 is not a real date, but 2026-06-01 is"
        assert cassandra_brain._markdown_doc_latest_date(content) == date(2026, 6, 1)


class TestOperatorDocIsStale:
    def test_recent_date_is_not_stale(self):
        recent = _iso(date.today() - timedelta(days=1))
        assert cassandra_brain._operator_doc_is_stale(f"- {recent} [PASS] fresh") is False

    def test_old_date_is_stale(self):
        old = _iso(date.today() - timedelta(days=cassandra_brain.OPS_ORIENTATION_STALE_SLA_DAYS + 1))
        assert cassandra_brain._operator_doc_is_stale(f"- {old} [PASS] old") is True

    def test_exactly_at_sla_boundary_is_not_stale(self):
        boundary = _iso(date.today() - timedelta(days=cassandra_brain.OPS_ORIENTATION_STALE_SLA_DAYS))
        assert cassandra_brain._operator_doc_is_stale(f"- {boundary} [PASS] boundary") is False

    def test_missing_date_fails_open_not_stale(self):
        assert cassandra_brain._operator_doc_is_stale("no dates in this doc at all") is False


class TestBuildOpsStatusPacketStaleness:
    def _write_docs(self, tmp_path, *, current_state_date: str, next_actions_date: str):
        operator_dir = tmp_path / "Operator"
        operator_dir.mkdir(parents=True, exist_ok=True)
        (operator_dir / "GENERATED_CURRENT_STATE.md").write_text(
            "## Active Lane\nDoing the thing.\n\n"
            "## Confirmed System State\n- Something confirmed.\n\n"
            f"- {current_state_date} [PASS] some_receipt\n",
            encoding="utf-8",
        )
        (operator_dir / "GENERATED_NEXT_ACTIONS.md").write_text(
            "## Next Safe Move\nDo the next thing.\n\n"
            "## Unsafe Beyond\nDon't do the risky thing.\n\n"
            f"- {next_actions_date} [PASS] some_other_receipt\n",
            encoding="utf-8",
        )

    def test_fresh_doc_reports_ready_with_doc_content(self, tmp_path, monkeypatch):
        recent = _iso(date.today() - timedelta(days=1))
        self._write_docs(tmp_path, current_state_date=recent, next_actions_date=recent)
        monkeypatch.chdir(tmp_path)

        packet = cassandra_brain._build_ops_status_packet("status?")

        assert packet["status"] == "ready"
        assert packet["current_documented_lane"] == "Doing the thing."

    def test_stale_doc_with_no_snapshot_fallback_refuses_honestly(self, tmp_path, monkeypatch):
        old = _iso(date.today() - timedelta(days=cassandra_brain.OPS_ORIENTATION_STALE_SLA_DAYS + 30))
        self._write_docs(tmp_path, current_state_date=old, next_actions_date=old)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "scripts.orientation_snapshot.get_orientation_snapshot",
            lambda: (_ for _ in ()).throw(Exception("snapshot unavailable")),
        )

        packet = cassandra_brain._build_ops_status_packet("status?")

        assert packet["status"] == "stale_surfaces"
        assert "stale" in packet["safe_operator_reply"].lower()
        assert "generate_operator_status.py --write" in packet["safe_operator_reply"]

    def test_stale_doc_with_working_snapshot_uses_snapshot_values_not_stale_doc(self, tmp_path, monkeypatch):
        old = _iso(date.today() - timedelta(days=cassandra_brain.OPS_ORIENTATION_STALE_SLA_DAYS + 30))
        self._write_docs(tmp_path, current_state_date=old, next_actions_date=old)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "scripts.orientation_snapshot.get_orientation_snapshot",
            lambda: {"active_lane": "Fresh lane from snapshot", "next_safe_move": "Fresh next move"},
        )

        packet = cassandra_brain._build_ops_status_packet("status?")

        assert packet["status"] == "ready"
        assert packet["current_documented_lane"] == "Fresh lane from snapshot"
        assert packet["raw_next_safe_move"] == "Fresh next move"
        assert packet["current_documented_lane"] != "Doing the thing."

    def test_stale_doc_response_never_claims_stale_content_as_ready_status(self, tmp_path, monkeypatch):
        """The exact live bug: a stale doc must never silently flow through as 'ready'/'now'
        when nothing fresher is available."""
        old = _iso(date.today() - timedelta(days=60))
        self._write_docs(tmp_path, current_state_date=old, next_actions_date=old)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "scripts.orientation_snapshot.get_orientation_snapshot",
            lambda: {},
        )

        packet = cassandra_brain._build_ops_status_packet("status?")
        reply = cassandra_brain._format_ops_status_fallback(packet)

        assert packet["status"] != "ready"
        assert "Doing the thing." not in reply
