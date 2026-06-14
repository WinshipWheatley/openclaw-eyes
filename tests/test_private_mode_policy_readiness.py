import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import private_mode_policy_readiness as private_mode


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def test_private_mode_policy_defines_states_but_stays_inactive():
    payload = private_mode.build_payload(generated_at=FIXED_NOW)
    states = {item["state_name"]: item for item in payload["state_machine"]["states"]}

    assert payload["active_state"] == "standard"
    assert payload["private_mode_active"] is False
    assert payload["strict_private_mode_active"] is False
    assert {"standard", "private", "strict_private"} == set(states)
    assert states["strict_private"]["local_only_required"] is True
    assert states["private"]["tokenization_required"] is True


def test_private_mode_policy_changes_package_effects_not_authority():
    payload = private_mode.build_payload(generated_at=FIXED_NOW)
    proof = payload["machine_proof"]

    assert payload["package_effect_summary"]["raw_values_included"] is False
    assert payload["package_effect_summary"]["model_may_see_raw_values"] is False
    assert proof["all_states_block_raw_model_values"] is True
    assert proof["strict_private_requires_local_only"] is True
    assert proof["live_model_call_performed"] is False
    assert proof["tool_execution_performed"] is False
    assert proof["all_live_authority_false"] is True


def test_private_mode_policy_export_parses(tmp_path):
    payload = private_mode.build_payload(generated_at=FIXED_NOW)
    json_path, operator_path = private_mode.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == private_mode.READ_MODEL_ID
    assert parsed["machine_proof"]["private_mode_policy_exported"] is True
    assert "backend policy shape only" in operator_path.read_text(encoding="utf-8")
