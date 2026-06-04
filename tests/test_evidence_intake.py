import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import evidence_intake as intake
import verified_operator_envelope as envelope


FIXED_NOW = "2026-06-04T17:30:00+00:00"


def _artifact(tmp_path: Path) -> Path:
    path = tmp_path / "payment_processing_invoice_2026-1001.png"
    path.write_bytes(b"fake screenshot bytes for invoice 2026-1001 payment processing")
    return path


def _request(tmp_path: Path, *, note: str | None = None):
    artifact = _artifact(tmp_path)
    payload = {
        "request_type": intake.REQUEST_TYPE,
        "source_surface": "mission_control",
        "current_world_ref": "finance",
        "current_thread_ref": "capital_hilton",
        "claimed_client_ref": "capital_hilton",
        "claimed_workflow_ref": "capital_hilton_payment_watch",
        "artifact_path": str(artifact),
        "artifact_kind": "screenshot",
        "operator_note": note or "Screenshot shows payment processing for invoice 2026-1001.",
        "privacy_class": "financial_sensitive",
        "intended_use": "payment_proof",
        "authority_boundary": dict(intake.AUTHORITY_BOUNDARY),
    }
    return envelope.attach_verified_operator_envelope(
        payload,
        operator_ref="operator:winship",
        app_instance_ref="mission_control:pc",
        device_ref="device:pc",
        session_ref="session:evidence-test",
        created_at=FIXED_NOW,
    )


def _sqlite_count(path: Path, table: str) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def _assert_no_unsafe_true(payload):
    assert intake.unsafe_true_grants(payload) == []


def test_payment_screenshot_classified_financial_sensitive_local_only(tmp_path):
    request = _request(tmp_path)

    record = intake.build_intake_record(request, generated_at=FIXED_NOW)

    assert record["status"] == "EVIDENCE_INTAKE_READY"
    assert record["privacy"]["privacy_class"] == "financial_sensitive"
    assert record["privacy"]["processing_location"] == "local_only"
    assert record["privacy"]["external_provider_policy"] == "external_provider_blocked"
    assert record["privacy"]["tokenization_required"] is True
    assert record["privacy"]["raw_ocr_text_stored"] is False
    _assert_no_unsafe_true(record)


def test_missing_operator_verification_blocks_recording(tmp_path):
    request = _request(tmp_path)
    request["operator_envelope"].pop("app_instance_ref")
    request["operator_envelope"].pop("device_ref")
    request["operator_envelope"]["operator_verified"] = False
    request["operator_envelope"]["request_hash"] = envelope.compute_request_hash(request)

    record = intake.record_evidence_intake(
        request,
        sqlite_path=tmp_path / "evidence_intake.sqlite",
        artifact_lineage_sqlite_path=tmp_path / "artifact_lineage.sqlite",
        generated_at=FIXED_NOW,
    )

    assert record["status"] == "OPERATOR_VERIFICATION_REQUIRED"
    assert record["evidence_status"] == "NOT_RECORDED"
    assert not (tmp_path / "evidence_intake.sqlite").exists()


def test_payment_processing_evidence_does_not_mark_paid_or_mutate_ledger(tmp_path):
    request = _request(tmp_path)

    record = intake.record_evidence_intake(
        request,
        sqlite_path=tmp_path / "evidence_intake.sqlite",
        artifact_lineage_sqlite_path=tmp_path / "artifact_lineage.sqlite",
        generated_at=FIXED_NOW,
    )

    assert record["evidence_status"] == "CANDIDATE_EVIDENCE_RECORDED"
    assert record["payment"]["payment_state"] == "payment_processing_evidence_received"
    assert record["payment"]["paid"] is False
    assert record["payment"]["paid_truth_status"] == "NOT_PAID_PROOF"
    assert record["authority_boundary"]["ledger_mutation_allowed"] is False
    assert record["machine_proof"]["ledger_mutation_performed"] is False
    assert record["machine_proof"]["paid_marking_performed"] is False
    _assert_no_unsafe_true(record)


def test_raw_sensitive_detail_is_not_promoted_to_memory(tmp_path):
    request = _request(
        tmp_path,
        note="Screenshot shows payment processing for invoice 2026-1001, bank account 123456789 and routing 011000015.",
    )

    record = intake.record_evidence_intake(
        request,
        sqlite_path=tmp_path / "evidence_intake.sqlite",
        artifact_lineage_sqlite_path=tmp_path / "artifact_lineage.sqlite",
        generated_at=FIXED_NOW,
    )

    rendered = json.dumps(record, sort_keys=True)
    assert "123456789" not in rendered
    assert "011000015" not in rendered
    assert record["operator_note"]["raw_note_stored_in_general_memory"] is False
    assert record["machine_proof"]["raw_ocr_text_stored"] is False
    assert record["machine_proof"]["raw_sensitive_detail_promoted_to_memory"] is False
    assert record["machine_proof"]["general_memory_promotion_allowed"] is False


def test_artifact_hash_and_lineage_rows_created(tmp_path):
    request = _request(tmp_path)
    evidence_db = tmp_path / "evidence_intake.sqlite"
    lineage_db = tmp_path / "artifact_lineage.sqlite"

    record = intake.record_evidence_intake(
        request,
        sqlite_path=evidence_db,
        artifact_lineage_sqlite_path=lineage_db,
        generated_at=FIXED_NOW,
    )

    assert record["artifact"]["sha256"].startswith("sha256:")
    assert _sqlite_count(evidence_db, "evidence_intake_records") == 1
    assert _sqlite_count(lineage_db, "artifact_lineage") == 1

    conn = sqlite3.connect(evidence_db)
    try:
        row = conn.execute(
            """
            SELECT artifact_sha256, evidence_status, paid, ledger_mutation_performed,
                   raw_ocr_text_stored, general_memory_promotion_allowed
            FROM evidence_intake_records
            """
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == record["artifact"]["sha256"]
    assert row[1] == "CANDIDATE_EVIDENCE_RECORDED"
    assert row[2:] == (0, 0, 0, 0)


def test_dynamic_human_card_created(tmp_path):
    request = _request(tmp_path)

    record = intake.build_intake_record(request, generated_at=FIXED_NOW)
    card = record["dynamic_card"]

    assert card["headline"] == "Payment proof received"
    assert card["summary"] == (
        "This appears to show payment processing for invoice 2026-1001. "
        "Ledger remains untouched until payment is confirmed."
    )
    assert card["status_label"] == "Processing evidence"
    assert card["trust_state"] == "candidate_evidence"
    assert [action["label"] for action in card["actions"]] == [
        "Attach to lane",
        "Ask what this means",
        "Mark as test",
        "Show details",
    ]
    assert all(action["business_action"] is False for action in card["actions"])
    assert card["authority_boundary"]["paid"] is False
    assert card["authority_boundary"]["ledger_mutation_allowed"] is False
    _assert_no_unsafe_true(card)


def test_export_writes_json_bridge_sqlite_and_wiki(tmp_path):
    result = intake.export_evidence_intake(
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Evidence Intake.md",
        sqlite_path=tmp_path / "system_knowledge" / "evidence_intake.sqlite",
        artifact_lineage_sqlite_path=tmp_path / "system_knowledge" / "artifact_lineage.sqlite",
        generated_at=FIXED_NOW,
    )

    contract = json.loads(Path(result["contract_read_model_path"]).read_text(encoding="utf-8"))
    status = json.loads(Path(result["status_read_model_path"]).read_text(encoding="utf-8"))
    bridge_contract = json.loads(Path(result["bridge_contract_read_model_path"]).read_text(encoding="utf-8"))
    bridge_status = json.loads(Path(result["bridge_status_read_model_path"]).read_text(encoding="utf-8"))

    assert contract == bridge_contract
    assert status == bridge_status
    assert contract["status"] == "EVIDENCE_INTAKE_READY"
    assert status["status"] == "EVIDENCE_INTAKE_READY"
    assert status["latest_record"]["payment"]["paid"] is False
    assert _sqlite_count(Path(result["sqlite_path"]), "evidence_intake_records") == 1
    assert Path(result["wiki_path"]).exists()
    _assert_no_unsafe_true(contract)
    _assert_no_unsafe_true(status)
