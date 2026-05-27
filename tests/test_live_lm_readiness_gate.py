import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import live_lm_readiness_gate as gate


def test_lm1_shadow_ready_but_live_call_not_allowed():
    decision = gate.check_readiness({"request_id": "test_lm1_shadow", "lane": "LM1", "target_mode": "shadow"})

    assert decision["outcome"] == gate.LM1_SHADOW_READY
    assert decision["fixture_shadow_allowed"] is True
    assert decision["live_lm_call_allowed"] is False
    assert decision["default_active_state"] == "NOT_ACTIVE"


def test_readiness_gate_blocks_live_lm_if_model_policy_missing():
    decision = gate.check_readiness(
        {
            "request_id": "test_missing_policy",
            "lane": "LM1",
            "target_mode": "live",
            "model_policy_available": False,
            "receipt_policy_available": True,
            "explicit_enablement_present": True,
        }
    )

    assert decision["outcome"] == gate.BLOCKED_POLICY_GAP
    assert "MODEL_POLICY_MISSING" in decision["blocked_reasons"]


def test_readiness_gate_blocks_live_lm_if_tokenization_required_but_absent():
    decision = gate.check_readiness(
        {
            "request_id": "test_missing_tokenization",
            "lane": "LM2",
            "target_mode": "live",
            "tokenization_required": True,
            "tokenization_applied": False,
            "receipt_policy_available": True,
            "explicit_enablement_present": True,
        }
    )

    assert decision["outcome"] == gate.BLOCKED_TOKENIZATION_GAP
    assert "TOKENIZATION_REQUIRED_BUT_ABSENT" in decision["blocked_reasons"]


def test_default_live_state_remains_not_active_without_receipts():
    decision = gate.check_readiness({"request_id": "test_live_default", "lane": "LM1", "target_mode": "live"})

    assert decision["outcome"] == gate.BLOCKED_RECEIPT_GAP
    assert decision["default_active_state"] == "NOT_ACTIVE"


def test_exported_readmodel_parses(tmp_path):
    payload = gate.build_payload()
    json_path, operator_path = gate.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == gate.READ_MODEL_ID
    assert parsed["machine_proof"]["missing_model_policy_blocks"] is True
    assert parsed["machine_proof"]["missing_tokenization_blocks"] is True
    assert "NOT_ACTIVE" in operator_path.read_text(encoding="utf-8")
