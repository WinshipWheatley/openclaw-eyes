import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import guardian_output_gate
import intent_ingest_gate
import reality_bounce_harness as harness


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def _receipt_rows(db_path: Path) -> list[sqlite3.Row]:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM repoa_worker_run_receipts ORDER BY source_request_id").fetchall()


def _receipt_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        exists = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='repoa_worker_run_receipts'"
        ).fetchone()[0]
        if not exists:
            return 0
        return conn.execute("SELECT COUNT(*) FROM repoa_worker_run_receipts").fetchone()[0]


def test_arbitrary_status_text_routes_to_chief_and_writes_receipt(tmp_path):
    db_path = tmp_path / "reality_bounce.sqlite"
    payload = harness.run_text(
        "what's next for Capital Hilton?",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    result = payload["result"]

    assert result["status"] == harness.STATUS_ACCEPTED_WITH_RECEIPT
    assert result["selected_role_family"] == "CHIEF"
    assert result["selected_voice"] == "CHIEF"
    assert result["worker_fixture_used"].endswith("local_status_v0")
    assert result["guardian_result"]["validation_result"]["verdict"] == guardian_output_gate.VALIDATED
    assert result["receipt_written"] is True
    assert payload["machine_proof"]["live_lm1_call_performed"] is False
    assert payload["machine_proof"]["repo_b_runtime_started"] is False

    rows = _receipt_rows(db_path)
    assert len(rows) == 1
    row = rows[0]
    receipt_payload = json.loads(row["payload_json"])
    assert row["source_request_id"] == result["source_request_id"]
    assert row["role_family"] == "CHIEF"
    assert row["selected_voice"] == "CHIEF"
    assert row["validation_verdict"] == guardian_output_gate.VALIDATED
    assert row["external_action"] == 0
    assert row["authority_used"] == 0
    assert receipt_payload["receipt_classification"] == "reality_bounce_fixture"
    assert receipt_payload["production_receipt"] is False


def test_curly_apostrophe_status_text_routes_to_chief(tmp_path):
    db_path = tmp_path / "reality_bounce.sqlite"
    payload = harness.run_text(
        "what\u2019s next for Capital Hilton?",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    result = payload["result"]

    assert result["status"] == harness.STATUS_ACCEPTED_WITH_RECEIPT
    assert result["selected_role_family"] == "CHIEF"
    assert result["selected_voice"] == "CHIEF"
    assert result["receipt_written"] is True
    assert "next safe move for the Capital Hilton invoice" in payload["operator_stdout"]


def test_arbitrary_draft_text_routes_to_clara_and_writes_draft_receipt(tmp_path):
    db_path = tmp_path / "reality_bounce.sqlite"
    payload = harness.run_text(
        "draft a note to Hilton about the invoice package",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    result = payload["result"]
    worker_result = result["worker_result"]

    assert result["status"] == harness.STATUS_ACCEPTED_WITH_RECEIPT
    assert result["selected_role_family"] == "CASSANDRA_CLARA"
    assert result["selected_voice"] == "CLARA"
    assert worker_result["response_kind"] == "draft"
    assert worker_result["send_performed"] is False
    assert worker_result["requested_tool_calls"] == ()
    assert worker_result["requested_external_actions"] == ()
    assert "sent" not in worker_result["draft_text"].lower()
    assert "Hi Capital Hilton team" in payload["operator_stdout"]
    assert "Draft only - nothing was sent" in payload["operator_stdout"]

    rows = _receipt_rows(db_path)
    assert len(rows) == 1
    assert rows[0]["role_family"] == "CASSANDRA_CLARA"
    assert rows[0]["selected_voice"] == "CLARA"
    assert rows[0]["external_action"] == 0
    assert rows[0]["authority_used"] == 0


def test_send_invoice_now_blocks_without_worker_completion_receipt(tmp_path):
    db_path = tmp_path / "reality_bounce.sqlite"
    payload = harness.run_text("send the invoice now", db_path=db_path, generated_at=FIXED_NOW)
    result = payload["result"]

    assert result["status"] == harness.STATUS_BLOCKED
    assert result["gate2_result"]["outcome"] == intent_ingest_gate.BLOCKED_AUTHORITY
    assert result["worker_result"] is None
    assert result["receipt_written"] is False
    assert "approval" in payload["operator_stdout"].lower()
    assert _receipt_count(db_path) == 0


def test_ambiguous_text_returns_clarification_without_worker_receipt(tmp_path):
    db_path = tmp_path / "reality_bounce.sqlite"
    payload = harness.run_text("do the thing", db_path=db_path, generated_at=FIXED_NOW)
    result = payload["result"]

    assert result["status"] == harness.STATUS_CLARIFICATION
    assert result["gate2_result"]["outcome"] == intent_ingest_gate.NEEDS_CLARIFICATION
    assert result["receipt_written"] is False
    assert "what should openclaw work on" in payload["operator_stdout"].lower()
    assert _receipt_count(db_path) == 0


def test_delete_other_from_openclaw_is_supersession_or_clarification_not_physical_delete(tmp_path):
    payload = harness.run_text(
        "delete the other one from OpenClaw",
        db_path=tmp_path / "reality_bounce.sqlite",
        generated_at=FIXED_NOW,
    )
    result = payload["result"]
    accepted = result["gate2_result"].get("accepted_intent") or {}

    assert result["status"] in {harness.STATUS_ACCEPTED_RESPONSE_ONLY, harness.STATUS_CLARIFICATION}
    assert result["worker_result"] is None
    assert result["receipt_written"] is False
    assert result["boundary_flags"]["file_mutation_performed"] is False
    assert "deleted from disk" in payload["operator_stdout"].lower() or result["status"] == harness.STATUS_CLARIFICATION
    if accepted:
        assert accepted["safe_action_type"] == "SUPERSEDE_ACTIVE_REFERENCE_NOT_PHYSICAL_DELETE"
        assert "do not delete any file from disk" in accepted["requested_action"].lower()


def test_unsafe_worker_output_claiming_sent_submitted_paid_is_guardian_blocked(tmp_path):
    payload = harness.unsafe_claim_guardian_fixture(
        db_path=tmp_path / "reality_bounce.sqlite",
        generated_at=FIXED_NOW,
    )

    validation = payload["guardian_result"]["validation_result"]
    assert validation["verdict"] == guardian_output_gate.BLOCKED_FORBIDDEN_CLAIM
    assert validation["output_publish_allowed"] is False
    assert {"sent", "submitted", "paid"}.issubset(set(validation["forbidden_claims"]))
    assert payload["receipt_written"] is False


def test_cli_stdout_is_operator_language_and_not_backend_sludge(tmp_path):
    db_path = tmp_path / "cli_reality_bounce.sqlite"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_reality_bounce.py",
            "draft a note to Hilton about the invoice package",
            "--db-path",
            str(db_path),
            "--generated-at",
            FIXED_NOW,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    stdout = completed.stdout

    assert "Draft prepared" in stdout
    assert "Hi Capital Hilton team" in stdout
    assert "Draft only - nothing was sent" in stdout
    forbidden = ("worker route unavailable", "deterministic worker rule", "Gate 2", "Gate 3", "request contract")
    assert not any(term.lower() in stdout.lower() for term in forbidden)


def test_shadow_lm_mode_falls_back_without_live_model_call(tmp_path):
    payload = harness.run_text(
        "what's next for Capital Hilton?",
        mode="shadow-lm",
        db_path=tmp_path / "reality_bounce.sqlite",
        generated_at=FIXED_NOW,
    )

    assert payload["mode"] == "shadow-lm"
    assert payload["shadow_lm_status"] == "NOT_ACTIVE_FELL_BACK_TO_LOCAL"
    assert payload["machine_proof"]["model_call_performed"] is False
    assert payload["result"]["status"] == harness.STATUS_ACCEPTED_WITH_RECEIPT
