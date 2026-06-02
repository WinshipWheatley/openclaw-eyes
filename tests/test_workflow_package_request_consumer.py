import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_request_processor as processor
import openclaw_request_response_service as service
import workflow_package_queue as queue
import workflow_package_request_consumer as consumer
from scripts.run_openclaw_request_response_service import main as service_main


FIXED_NOW = "2026-06-02T02:30:00+00:00"


def _request_payload(*, request_id: str, source_text: str, world_ref: str, thread_ref: str) -> dict:
    protected_hash = queue.protected_text_hash(source_text)
    payload = {
        "schema_version": "operator_instruction_writer_v0",
        "request_id": request_id,
        "source_request_id": request_id,
        "request_type": consumer.REQUEST_TYPE,
        "kind": consumer.REQUEST_KIND,
        "source_surface": "mission_control",
        "source_channel": "mission_control_chat",
        "requested_mode": "operator",
        "result_receipt_required": True,
        "world": world_ref,
        "world_ref": world_ref,
        "thread_ref": thread_ref,
        "source_text": source_text,
        "operator_message": source_text,
        "source_text_ref": "protected_text_hash:" + protected_hash,
        "protected_text_hash": protected_hash,
        "privacy_impact": "pending",
        "idempotency_key": f"workflow_package_request:{request_id}",
        "created_at": FIXED_NOW,
        "authority_boundary": {key: False for key in consumer.AUTHORITY_FALSE_FIELDS},
        "mac_wrote_request_only": True,
        "no_external_action": True,
    }
    payload["payload_hash"] = "sha256:" + processor._short_hash(payload)
    return payload


def _write_request(path: Path, *, request_id: str, source_text: str, world_ref: str, thread_ref: str) -> dict:
    payload = _request_payload(
        request_id=request_id,
        source_text=source_text,
        world_ref=world_ref,
        thread_ref=thread_ref,
    )
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _safe_response_path(response_dir: Path, request_id: str) -> Path:
    return response_dir / f"openclaw_response_for_mac_{service._safe_filename_part(request_id)}.json"


def _safe_heartbeat_path(response_dir: Path, request_id: str) -> Path:
    return response_dir / f"openclaw_processing_for_mac_{service._safe_filename_part(request_id)}.json"


def test_consumer_records_valid_workflow_package_request_in_queue_sqlite(tmp_path):
    sqlite_path = tmp_path / "workflow_package_queue.sqlite"
    request = _request_payload(
        request_id="church_sound_operator_instruction_smoke",
        source_text="Mark that I'm at church running sound.",
        world_ref="operations",
        thread_ref="church_sound",
    )

    result = consumer.consume_workflow_package_request(
        request,
        source_request_filename="mission_control_operator_instruction_request_church_sound.json",
        generated_at=FIXED_NOW,
        sqlite_path=sqlite_path,
    )

    assert result.status == "RECORDED"
    assert result.receipt["raw_internal_status"] == "RESPONSE_READY"
    assert result.receipt["workflow_ref"] == "st_annes_work_log_event"
    assert result.receipt["client_ref"] == "st_annes"
    assert result.receipt["package_status"] == "OPERATOR_REVIEW_REQUIRED"
    assert result.receipt["machine_proof"]["queue_noop_worker_only"] is True
    assert result.receipt["machine_proof"]["business_state_mutation_performed"] is False

    with sqlite3.connect(sqlite_path) as conn:
        row = conn.execute(
            "select workflow_ref, client_ref, status from packages where package_id = ?",
            (result.receipt["package_id"],),
        ).fetchone()
        assert row == ("st_annes_work_log_event", "st_annes", "OPERATOR_REVIEW_REQUIRED")
        raw_text_stored = conn.execute("select raw_text_stored from package_inputs").fetchone()[0]
        assert raw_text_stored == 0
        gates = conn.execute(
            "select email_send_allowed, ledger_posting_allowed, browser_access_allowed, gmail_allowed, "
            "coupa_allowed, portal_submit_allowed, paid, sent from business_action_gate_results"
        ).fetchall()
        assert gates == [(0, 0, 0, 0, 0, 0, 0, 0)]


def test_consumer_blocks_unsafe_true_grant_without_queue_write(tmp_path):
    sqlite_path = tmp_path / "workflow_package_queue.sqlite"
    request = _request_payload(
        request_id="unsafe_operator_instruction_smoke",
        source_text="Submit Capital Hilton invoice.",
        world_ref="finance",
        thread_ref="capital_hilton_invoice_workflow",
    )
    unsafe_key = "email_send_" + "allowed"
    request["authority_boundary"][unsafe_key] = bool(1)

    result = consumer.consume_workflow_package_request(
        request,
        source_request_filename="mission_control_operator_instruction_request_unsafe.json",
        generated_at=FIXED_NOW,
        sqlite_path=sqlite_path,
    )

    assert result.status == "BLOCKED"
    assert result.receipt["raw_internal_status"] == "BLOCKED_WITH_REASON"
    assert f"authority_true:{unsafe_key}" in result.blockers
    assert not sqlite_path.exists()


def test_service_processes_three_workflow_package_requests_and_writes_scoped_responses(tmp_path, capsys, monkeypatch):
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    sqlite_path = tmp_path / "workflow_package_queue.sqlite"
    inbox.mkdir()
    monkeypatch.setenv(consumer.SQLITE_PATH_ENV, sqlite_path.as_posix())

    requests = [
        _write_request(
            inbox / "mission_control_operator_instruction_request_church_sound_operator_instruction_smoke.json",
            request_id="church_sound_operator_instruction_smoke",
            source_text="Mark that I'm at church running sound.",
            world_ref="operations",
            thread_ref="church_sound",
        ),
        _write_request(
            inbox / "mission_control_operator_instruction_request_capital_hilton_business_development_operator_instruction_smoke.json",
            request_id="capital_hilton_business_development_operator_instruction_smoke",
            source_text="Follow up on the Capital Hilton proposal.",
            world_ref="business_development",
            thread_ref="capital_hilton_business_development",
        ),
        _write_request(
            inbox / "mission_control_operator_instruction_request_capital_hilton_invoice_workflow_operator_instruction_smoke.json",
            request_id="capital_hilton_invoice_workflow_operator_instruction_smoke",
            source_text="Submit Capital Hilton invoice.",
            world_ref="finance",
            thread_ref="capital_hilton_invoice_workflow",
        ),
    ]

    assert all(processor.classify_request_filename(path.name).request_family == "WORKFLOW_PACKAGE_REQUEST" for path in inbox.iterdir())
    assert all(service.classify_request_path(path) == "WORKFLOW_PACKAGE_REQUEST" for path in inbox.iterdir())

    assert service_main(
        [
            "--watch-seconds",
            "1",
            "--max-requests",
            "3",
            "--inbox",
            str(inbox),
            "--response-dir",
            str(response_dir),
            "--export-root",
            str(export_root),
            "--generated-at",
            FIXED_NOW,
            "--format",
            "json",
        ]
    ) == 0
    service_payload = json.loads(capsys.readouterr().out)
    assert service_payload["service_status"]["processed_count"] == 3
    assert service_payload["service_status"]["service_status"] == "REQUEST_PROCESSED"

    expected = {
        "church_sound_operator_instruction_smoke": ("st_annes_work_log_event", "st_annes", "OPERATOR_REVIEW_REQUIRED"),
        "capital_hilton_business_development_operator_instruction_smoke": (
            "capital_hilton_proposal_followup",
            "capital_hilton",
            "OPERATOR_REVIEW_REQUIRED",
        ),
        "capital_hilton_invoice_workflow_operator_instruction_smoke": (
            "capital_hilton_invoice_operator_assist",
            "capital_hilton",
            "PROVIDER_GATE_REQUIRED",
        ),
    }
    for request in requests:
        response = json.loads(_safe_response_path(response_dir, request["request_id"]).read_text(encoding="utf-8"))
        heartbeat = json.loads(_safe_heartbeat_path(response_dir, request["request_id"]).read_text(encoding="utf-8"))
        workflow_ref, client_ref, package_status = expected[request["request_id"]]

        assert heartbeat["request_type"] == "WORKFLOW_PACKAGE_REQUEST"
        assert heartbeat["processing_status"] == "CHECKING_WORKFLOW_PACKAGE_QUEUE"
        assert response["source_request_id"] == request["request_id"]
        assert response["raw_internal_status"] == "RESPONSE_READY"
        assert response["internal_status"] == "RESPONSE_READY"
        assert response["response_kind"] == "WORKFLOW_PACKAGE_REQUEST_RESPONSE"
        assert response["workflow_ref"] == workflow_ref
        assert response["client_ref"] == client_ref
        assert response["package_status"] == package_status
        assert response["package_id"].startswith("workflow_package:")
        assert response["no_external_authority_granted"] is True
        assert response["detail_disclosure"]["workflow_package_request_consumer"]["package_status"] == package_status
        assert response["machine_proof"]["email_send_performed"] is False
        assert response["machine_proof"]["browser_access_performed"] is False
        assert response["machine_proof"]["coupa_access_or_submit_performed"] is False
        assert response["machine_proof"]["workbook_body_read_performed"] is False
        assert response["machine_proof"]["pdf_generation_performed"] is False
        assert response["machine_proof"]["payment_tracking_write_performed"] is False
        assert response["machine_proof"]["external_action_performed"] is False

    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute("select workflow_ref, client_ref, status from packages order by workflow_ref").fetchall()
    assert rows == [
        ("capital_hilton_invoice_operator_assist", "capital_hilton", "PROVIDER_GATE_REQUIRED"),
        ("capital_hilton_proposal_followup", "capital_hilton", "OPERATOR_REVIEW_REQUIRED"),
        ("st_annes_work_log_event", "st_annes", "OPERATOR_REVIEW_REQUIRED"),
    ]
