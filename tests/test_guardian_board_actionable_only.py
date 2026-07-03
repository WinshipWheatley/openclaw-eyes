"""The board surfaces only ACTIONABLE approvals (chief pending file), never the
observational guardian_hitl shadow dual-writes (which have no live executor / dead buttons).
Regression: a shadow record was surfaced with YES/NO buttons that record_decision rejects."""

import json
import sqlite3
from pathlib import Path

import guardian_approval_notifier as gan


def _ledger_with_shadow(tmp_path):
    db = tmp_path / "ledger.sqlite"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE guardian_hitl_approval_requests (approval_id TEXT, source_surface_id TEXT, "
              "action_summary_label TEXT, risk_tier TEXT, status TEXT, requested_at TEXT, expires_at TEXT)")
    c.execute("INSERT INTO guardian_hitl_approval_requests VALUES "
              "('SHDW1','chief_approval_brain','Chief approval request','tier_2','request_shadow_created','', '2099-01-01T00:00:00+00:00')")
    c.commit(); c.close()
    return db


def test_observational_shadow_excluded_from_board(tmp_path):
    pending = gan._pending_for_board(tmp_path / "none.json", _ledger_with_shadow(tmp_path))
    assert pending == []   # the observational shadow is NOT an actionable board item


def test_real_chief_pending_still_surfaced(tmp_path):
    pf = tmp_path / "approval_pending.json"
    pf.write_text(json.dumps({"id": "R1", "requester": "Cassandra", "tier": 2, "status": "pending",
                              "action": "Send invoice email", "approval_context": {"to": "x@y.com"}}))
    pending = gan._pending_for_board(pf, _ledger_with_shadow(tmp_path))
    assert len(pending) == 1 and pending[0]["id"] == "R1"
