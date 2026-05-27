import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import read_model_mirror_visibility as mirror


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def test_read_model_visibility_tracks_readiness_refs_without_claiming_mac_sync():
    payload = mirror.build_payload(generated_at=FIXED_NOW)

    refs = {item["read_model_ref"] for item in payload["visibility_records"]}
    assert "generated/read_models/lm_readiness_dashboard.json" in refs
    assert "generated/read_models/operator_readiness_surface.json" in refs
    assert "generated/read_models/floor_gap_reconciliation.json" in refs
    assert payload["mirror_policy"]["new_sync_system_allowed"] is False
    assert payload["mirror_policy"]["mac_visible_guaranteed_by_this_contract"] is False
    assert payload["machine_proof"]["mac_visible_guaranteed"] is False


def test_read_model_visibility_does_not_publish_or_sync():
    payload = mirror.build_payload(generated_at=FIXED_NOW)
    proof = payload["machine_proof"]

    assert proof["new_sync_system_created"] is False
    assert proof["response_publication_performed"] is False
    assert proof["network_performed"] is False
    assert proof["tool_execution_performed"] is False
    assert proof["external_action_performed"] is False
    assert proof["all_live_authority_false"] is True


def test_read_model_visibility_export_parses(tmp_path):
    payload = mirror.build_payload(generated_at=FIXED_NOW)
    json_path, operator_path = mirror.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == mirror.READ_MODEL_ID
    assert parsed["machine_proof"]["visibility_record_count"] >= 10
    assert "proof only" in operator_path.read_text(encoding="utf-8")
