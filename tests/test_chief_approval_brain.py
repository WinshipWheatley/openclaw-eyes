import json
import os
import sys
from datetime import datetime, timedelta


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _write_pending(path, *, status="pending", requested_at=None, approval_id="ABCD", options=2):
    if requested_at is None:
        requested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path.write_text(
        json.dumps(
            {
                "status": status,
                "requested_at": requested_at,
                "id": approval_id,
                "options": options,
            }
        ),
        encoding="utf-8",
    )


class TestPendingApprovalState:
    def test_non_pending_reports_no_active_approval(self, monkeypatch, tmp_path):
        import chief_approval_brain as approval_brain

        pending_path = tmp_path / "approval_pending.json"
        monkeypatch.setattr(approval_brain, "PENDING_FILE", pending_path, raising=False)
        _write_pending(pending_path, status="decided")

        assert approval_brain.has_pending_approval() is False
        assert approval_brain.get_pending_id() == ""
        assert approval_brain.get_pending_info() == ("", 2)

    def test_stale_pending_is_cleared_for_all_read_helpers(self, monkeypatch, tmp_path):
        import chief_approval_brain as approval_brain

        pending_path = tmp_path / "approval_pending.json"
        monkeypatch.setattr(approval_brain, "PENDING_FILE", pending_path, raising=False)
        stale_requested_at = (datetime.now() - timedelta(seconds=approval_brain.TIMEOUT + 60)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        _write_pending(pending_path, requested_at=stale_requested_at, approval_id="WXYZ", options=3)

        assert approval_brain.has_pending_approval() is False
        assert approval_brain.get_pending_id() == ""
        assert approval_brain.get_pending_info() == ("", 2)
        assert json.loads(pending_path.read_text(encoding="utf-8")) == {}

    def test_fresh_pending_returns_active_approval_data(self, monkeypatch, tmp_path):
        import chief_approval_brain as approval_brain

        pending_path = tmp_path / "approval_pending.json"
        monkeypatch.setattr(approval_brain, "PENDING_FILE", pending_path, raising=False)
        _write_pending(pending_path, approval_id="LIVE", options=3)

        assert approval_brain.has_pending_approval() is True
        assert approval_brain.get_pending_id() == "LIVE"
        assert approval_brain.get_pending_info() == ("LIVE", 3)
