import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import request_response_bridge_readiness as bridge


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def test_bridge_readiness_summarizes_scoped_response_contract():
    payload = bridge.build_payload(generated_at=FIXED_NOW)
    contract = payload["bridge_contract"]

    assert contract["service_template_present"] is True
    assert contract["approved_inbox_ref"].endswith("/mission_control_capture_requests/inbox")
    assert contract["response_output_ref"].endswith("/mission_control_responses/to_mac")
    assert contract["scoped_response_filename_contract"] == "openclaw_response_for_mac_<source_request_id>.json"
    assert payload["safe_delivery_policy"]["arbitrary_destination_allowed"] is False
    assert payload["safe_delivery_policy"]["lm_inferred_routing_allowed"] is False


def test_bridge_readiness_does_not_start_or_process_anything():
    payload = bridge.build_payload(generated_at=FIXED_NOW)
    proof = payload["machine_proof"]

    assert proof["service_started_by_this_readmodel"] is False
    assert proof["request_processed_by_this_readmodel"] is False
    assert proof["model_call_performed"] is False
    assert proof["tool_execution_performed"] is False
    assert proof["external_action_performed"] is False
    assert proof["all_live_authority_false"] is True


def test_bridge_exported_readmodel_parses(tmp_path):
    payload = bridge.build_payload(generated_at=FIXED_NOW)
    json_path, operator_path = bridge.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == bridge.READ_MODEL_ID
    assert "This is visibility only" in operator_path.read_text(encoding="utf-8")
