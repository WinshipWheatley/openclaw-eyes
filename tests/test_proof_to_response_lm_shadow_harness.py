import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import proof_to_response_lm_shadow_harness as harness


FIXED_NOW = "2026-06-06T14:00:00+00:00"


def test_shadow_harness_contract_and_status_are_ready():
    contract = harness.build_contract_read_model(generated_at=FIXED_NOW)
    status = harness.build_status_read_model(generated_at=FIXED_NOW)

    assert contract["status"] == harness.READY_STATUS
    assert status["status"] == harness.READY_STATUS
    assert contract["contract"]["lm_response_is_not_truth"] is True
    assert contract["authority_boundary"]["model_invocation_allowed"] is False
    assert status["machine_proof"]["all_shadow_drafts_verified"] is True
    assert status["machine_proof"]["unsafe_true_grants_absent"] is True


def test_shadow_harness_supported_scenarios_verify_publishable():
    status = harness.build_status_read_model(generated_at=FIXED_NOW)

    assert len(status["shadow_runs"]) == 6
    for run in status["shadow_runs"]:
        assert run["verifier_result"]["publishable"] is True
        assert run["verifier_result"]["verification_errors"] == []
        assert run["lm_shadow_response"]["proof_bundle_id"] == run["proof_bundle"]["proof_bundle_id"]


def test_shadow_harness_external_and_local_runtime_remain_blocked():
    contract = harness.build_contract_read_model(generated_at=FIXED_NOW)
    status = harness.build_status_read_model(generated_at=FIXED_NOW)

    assert contract["authority_boundary"]["external_provider_connect_allowed"] is False
    assert contract["authority_boundary"]["local_model_runtime_allowed"] is False
    assert status["implementation_boundary"]["live_lm_invoked"] is False
    assert status["implementation_boundary"]["local_model_runtime_connected"] is False
    assert status["implementation_boundary"]["worker_spawn_performed"] is False


def test_shadow_harness_export_round_trips_local_and_bridge(tmp_path):
    bridge_root = tmp_path / "bridge"
    result = harness.export_proof_to_response_lm_shadow_harness(
        read_model_root=ROOT / "generated/read_models",
        export_root=tmp_path / "read_models",
        bridge_export_root=bridge_root,
        wiki_path=tmp_path / "Proof To Response LM Shadow Harness.md",
        generated_at=FIXED_NOW,
    )

    contract = json.loads(Path(result["contract_path"]).read_text(encoding="utf-8"))
    status = json.loads(Path(result["status_path"]).read_text(encoding="utf-8"))
    bridge_contract = json.loads(Path(result["bridge_contract_path"]).read_text(encoding="utf-8"))
    bridge_status = json.loads(Path(result["bridge_status_path"]).read_text(encoding="utf-8"))

    assert result["status"] == harness.READY_STATUS
    assert contract == bridge_contract
    assert status == bridge_status
    assert status["status"] == harness.READY_STATUS
    assert Path(result["wiki_path"]).read_text(encoding="utf-8").startswith("# Proof To Response LM Shadow Harness")
