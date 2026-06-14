import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import verified_operator_envelope as envelope


FIXED_NOW = "2026-06-04T17:00:00+00:00"


def _request():
    payload = {
        "request_type": "EVIDENCE_INTAKE_REQUEST_V0",
        "source_surface": "mission_control",
        "current_world_ref": "finance",
        "current_thread_ref": "capital_hilton",
        "artifact_kind": "screenshot",
        "intended_use": "payment_proof",
    }
    return envelope.attach_verified_operator_envelope(
        payload,
        operator_ref="operator:winship",
        app_instance_ref="mission_control:pc",
        device_ref="device:pc",
        session_ref="session:test",
        created_at=FIXED_NOW,
    )


def test_verified_operator_envelope_accepted():
    request = _request()

    result = envelope.validate_operator_envelope(request)

    assert result["status"] == "OPERATOR_VERIFIED"
    assert result["verified"] is True
    assert result["operator_ref"] == "operator:winship"
    assert result["request_hash_checked"] is True
    assert result["request_hash"] == envelope.compute_request_hash(request)
    assert result["machine_proof"]["missing_fields_were_not_filled"] is True


def test_missing_operator_app_device_verification_blocks():
    request = _request()
    request["operator_envelope"].pop("operator_ref")
    request["operator_envelope"].pop("app_instance_ref")
    request["operator_envelope"].pop("device_ref")
    request["operator_envelope"]["operator_verified"] = False
    request["operator_envelope"]["request_hash"] = envelope.compute_request_hash(request)

    result = envelope.validate_operator_envelope(request)

    assert result["status"] == "OPERATOR_VERIFICATION_REQUIRED"
    assert result["verified"] is False
    assert "operator_ref_missing" in result["blockers"]
    assert "app_instance_ref_missing" in result["blockers"]
    assert "device_ref_missing" in result["blockers"]
    assert "operator_verified_false_or_missing" in result["blockers"]


def test_hash_mismatch_blocks_verified_claim():
    request = _request()
    request["current_thread_ref"] = "wrong_lane_after_hash"

    result = envelope.validate_operator_envelope(request)

    assert result["status"] == "OPERATOR_VERIFICATION_REQUIRED"
    assert "request_hash_mismatch" in result["blockers"]
