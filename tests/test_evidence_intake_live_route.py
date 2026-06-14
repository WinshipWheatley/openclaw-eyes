import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import evidence_intake
import first_class_operator_envelope as authority_envelope
import openclaw_request_processor as processor
import openclaw_request_response_service as service
import verified_operator_envelope as operator_envelope


FIXED_NOW = "2026-06-04T20:00:00+00:00"


def _response_path(response_dir: Path, request_id: str) -> Path:
    return response_dir / f"openclaw_response_for_mac_{service._safe_filename_part(request_id)}.json"


def _configure_evidence_paths(monkeypatch, tmp_path: Path) -> dict[str, Path]:
    paths = {
        "evidence_db": tmp_path / "system_knowledge" / "evidence_intake.sqlite",
        "lineage_db": tmp_path / "system_knowledge" / "artifact_lineage_registry.sqlite",
        "bridge": tmp_path / "bridge_read_models",
        "wiki": tmp_path / "wiki" / "Evidence Intake.md",
    }
    monkeypatch.setattr(evidence_intake, "DEFAULT_SQLITE_PATH", paths["evidence_db"])
    monkeypatch.setattr(evidence_intake, "DEFAULT_ARTIFACT_LINEAGE_SQLITE_PATH", paths["lineage_db"])
    monkeypatch.setattr(evidence_intake, "DEFAULT_BRIDGE_ROOT", paths["bridge"])
    monkeypatch.setattr(evidence_intake, "DEFAULT_WIKI_PATH", paths["wiki"])
    return paths


def _valid_request(tmp_path: Path, *, request_id: str = "evidence_intake_live_route_valid") -> dict:
    artifact = tmp_path / "live_arts_payment_processing_invoice_2026-1001.png"
    artifact.write_bytes(b"live arts md payment processing proof screenshot")
    payload = {
        "request_id": request_id,
        "request_type": evidence_intake.REQUEST_TYPE,
        "original_request_type": evidence_intake.REQUEST_TYPE,
        "source_surface": "mission_control",
        "current_world_ref": "finance",
        "current_thread_ref": "live_arts_md",
        "claimed_client_ref": "live_arts_md",
        "claimed_workflow_ref": "live_arts_md_payment_watch",
        "artifact_path": artifact.as_posix(),
        "artifact_hash_allowed": True,
        "artifact_kind": "screenshot",
        "operator_note": "Live Arts MD payment processing proof for invoice 2026-1001.",
        "privacy_class": "financial_sensitive",
        "intended_use": "payment_proof",
        "authority_boundary": dict(evidence_intake.AUTHORITY_BOUNDARY),
    }
    request = operator_envelope.attach_verified_operator_envelope(
        payload,
        operator_ref="operator:winship",
        app_instance_ref="mission_control:mac",
        device_ref="device:macbook",
        session_ref="session:evidence-live-route",
        created_at=FIXED_NOW,
    )
    request = authority_envelope.attach_verified_authority_envelope(
        request,
        operator_ref="operator:winship",
        app_instance_ref="mission_control:mac",
        device_ref="device:macbook",
        device_class="mac",
        session_ref="session:evidence-live-route",
        source_surface="dropzone",
        current_world_ref="finance",
        current_thread_ref="live_arts_md",
        active_entity_ref="dynamic_card.finance.live_arts_md.evidence_intake.payment_processing",
        controller_action_type="attach_proof",
        authority_requested=[],
        created_at=FIXED_NOW,
    )
    request["operator_envelope"]["request_hash"] = operator_envelope.compute_request_hash(request)
    request["operator_authority_envelope"]["request_hash"] = authority_envelope.compute_request_hash(request)
    return request


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sqlite_row(path: Path) -> tuple:
    conn = sqlite3.connect(path)
    try:
        return conn.execute(
            """
            SELECT current_thread_ref, claimed_client_ref, privacy_class, processing_location,
                   external_provider_policy, tokenization_required, evidence_status,
                   payment_state, paid, ledger_mutation_performed, raw_ocr_text_stored,
                   general_memory_promotion_allowed
            FROM evidence_intake_records
            """
        ).fetchone()
    finally:
        conn.close()


def _walk(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk(value)


def _unsafe_true_grants(payload):
    unsafe = set(evidence_intake.UNSAFE_TRUE_KEYS) | {
        "trusted_for_action",
        "mac_sync_import_run",
        "network_used",
        "model_call_performed",
        "tool_execution_performed",
        "worker_dispatch_performed",
        "workflow_execution_performed",
    }
    return sorted({key for key, value in _walk(payload) if key in unsafe and value is True})


def test_valid_evidence_request_consumed_response_file_written_and_candidate_recorded(tmp_path, monkeypatch):
    paths = _configure_evidence_paths(monkeypatch, tmp_path)
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    request = _valid_request(tmp_path)
    request_path = inbox / "mission_control_evidence_intake_request_live_arts.json"
    _write_json(request_path, request)

    result = service.process_one_pending_request(
        inbox=inbox,
        response_dir=response_dir,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    assert result.service_status == "REQUEST_PROCESSED"
    response_path = _response_path(response_dir, request["request_id"])
    assert response_path.exists()
    response = json.loads(response_path.read_text(encoding="utf-8"))
    assert response["request_type"] == "EVIDENCE_INTAKE_REQUEST"
    assert response["operator_headline"] == "Payment proof received"
    assert response["operator_message"] == (
        "This appears to show payment processing. Ledger remains untouched until payment is confirmed."
    )
    assert response["visible_cards"][0]["headline"] == "Payment proof received"
    assert response["visible_cards"][0]["summary"] == (
        "This appears to show payment processing. Ledger remains untouched until payment is confirmed."
    )
    assert response["visible_cards"][0]["trust_state"] == "operator_reported"
    assert response["detail_disclosure"]["evidence_intake"]["privacy"]["privacy_class"] == "financial_sensitive"
    assert response["detail_disclosure"]["evidence_intake"]["privacy"]["processing_location"] == "local_only"
    assert response["detail_disclosure"]["evidence_intake"]["payment"]["paid"] is False
    assert response["detail_disclosure"]["evidence_intake"]["payment"]["payment_state"] == "payment_processing_evidence_received"
    assert response["machine_proof"]["external_action_performed"] is False
    assert response["machine_proof"]["model_call_performed"] is False
    assert response["machine_proof"]["local_model_call_performed"] is False

    assert _sqlite_row(paths["evidence_db"]) == (
        "live_arts_md",
        "live_arts_md",
        "financial_sensitive",
        "local_only",
        "external_provider_blocked",
        1,
        "CANDIDATE_EVIDENCE_RECORDED",
        "payment_processing_evidence_received",
        0,
        0,
        0,
        0,
    )
    status = json.loads((export_root / "evidence_intake_status.json").read_text(encoding="utf-8"))
    bridge_status = json.loads((paths["bridge"] / "evidence_intake_status.json").read_text(encoding="utf-8"))
    assert status == bridge_status
    assert status["latest_record"]["claimed_client_ref"] == "live_arts_md"
    assert status["latest_record"]["payment"]["paid"] is False
    assert _unsafe_true_grants(response) == []
    assert _unsafe_true_grants(status) == []


def test_generic_filename_evidence_envelope_is_recognized(tmp_path, monkeypatch):
    _configure_evidence_paths(monkeypatch, tmp_path)
    request = _valid_request(tmp_path, request_id="evidence_intake_live_route_generic_filename")
    request_path = tmp_path / "inbox" / "operator_drop_payload.json"
    _write_json(request_path, request)

    assert service.classify_request_path(request_path) == "EVIDENCE_INTAKE_REQUEST"
    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at=FIXED_NOW,
    )

    assert response.internal_status == "RESPONSE_READY"
    assert response.visible_cards[0]["headline"] == "Payment proof received"


def test_missing_operator_envelope_blocks_with_operator_verification_required(tmp_path, monkeypatch):
    paths = _configure_evidence_paths(monkeypatch, tmp_path)
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    request = _valid_request(tmp_path, request_id="evidence_intake_live_route_missing_envelope")
    request.pop("operator_envelope")
    request_path = inbox / "mission_control_evidence_intake_request_missing_envelope.json"
    _write_json(request_path, request)

    result = service.process_one_pending_request(
        inbox=inbox,
        response_dir=response_dir,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    assert result.service_status == "REQUEST_PROCESSED"
    response = json.loads(_response_path(response_dir, request["request_id"]).read_text(encoding="utf-8"))
    assert response["internal_status"] == "BLOCKED_WITH_REASON"
    assert response["blocked_reason"] == "OPERATOR_VERIFICATION_REQUIRED"
    assert response["why_it_happened"] == "OPERATOR_VERIFICATION_REQUIRED"
    assert response["cards_available"] is False
    assert not paths["evidence_db"].exists()
    assert response["detail_disclosure"]["evidence_intake"]["ledger_mutation_performed"] is False
    assert response["detail_disclosure"]["evidence_intake"]["paid_marking_performed"] is False
    assert _unsafe_true_grants(response) == []
