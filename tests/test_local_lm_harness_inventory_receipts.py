import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_lm_harness_inventory_receipts as inventory


FIXED_NOW = "2026-06-07T01:05:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "local_lm_proof_to_response_readiness_gate.json", {"status": "LOCAL_LM_PROOF_RESPONSE_READINESS_GATE_READY"})
    _write_json(root / "harness_provider_selection_registry.json", {"status": "HARNESS_PROVIDER_SELECTION_READY"})
    _write_json(root / "proof_to_response_lm_shadow_pilot.json", {"status": "PROOF_TO_RESPONSE_LM_SHADOW_PILOT_READY"})
    _write_json(
        root / "proof_to_response_runtime_status.json",
        {
            "status": "PROOF_TO_RESPONSE_RUNTIME_READY",
            "active_candidate_source": "shadow_pilot_candidate",
            "source_request_id": "fixture_shadow_request",
            "world_ref": "finance",
            "thread_ref": "capital_hilton",
        },
    )
    _write_json(
        root / "proof_to_response_latest.json",
        {
            "status": "PROOF_TO_RESPONSE_RUNTIME_READY",
            "candidate_source": "shadow_pilot_candidate",
            "source_request_id": "fixture_shadow_request",
            "world_ref": "finance",
            "thread_ref": "capital_hilton",
        },
    )
    _write_json(root / "goldilocks_gate_calibration.json", {"status": "GOLDILOCKS_GATE_CALIBRATION_READY"})
    return root


def _candidates(read_model: dict) -> dict:
    return {row["harness_ref"]: row for row in read_model["harness_candidates"]}


def test_no_candidate_is_live_invocation_ready_by_default(tmp_path):
    read_model = inventory.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        repo_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    for candidate in read_model["harness_candidates"]:
        assert candidate["invocation_allowed"] is False
        assert candidate["proof_to_response_allowed"] is False
        assert candidate["live_invocation_ready"] is False
        assert candidate["reason_not_live"]


def test_external_llm_remains_blocked(tmp_path):
    read_model = inventory.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        repo_root=tmp_path,
        generated_at=FIXED_NOW,
    )
    external = _candidates(read_model)["external_llm_blocked_by_default"]

    assert external["present"] == "unknown"
    assert external["invocation_allowed"] is False
    assert external["reason_not_live"] == "external_provider_blocked_by_default"
    assert "external_provider_call" in external["data_classes_forbidden"]


def test_hermes_sidecar_remains_blocked_unless_explicitly_registered(tmp_path):
    root = _fixture_root(tmp_path)
    _write_json(root / "hermes_sidecar_inventory.json", {"status": "HERMES_SIDECAR_INVENTORY_READY"})
    (tmp_path / "sidecars" / "hermes").mkdir(parents=True)

    read_model = inventory.build_read_model(
        read_model_root=root,
        repo_root=tmp_path,
        generated_at=FIXED_NOW,
    )
    hermes = _candidates(read_model)["hermes_sidecar_candidate"]

    assert hermes["present"] == "true"
    assert hermes["invocation_allowed"] is False
    assert hermes["proof_to_response_allowed"] is False
    assert "explicit_hermes_proof_to_response_registration" in hermes["missing_receipts"]


def test_local_model_candidates_require_redaction_and_verifier_receipts(tmp_path):
    read_model = inventory.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        repo_root=tmp_path,
        generated_at=FIXED_NOW,
    )
    candidates = _candidates(read_model)

    for ref in ("local_llm_shadow_mode", "future_local_open_model", "codex_desktop_operator_assist"):
        row = candidates[ref]
        assert row["required_redaction"] is True
        assert row["required_verifier"] == "proof_to_response_verifier"
        assert "proof_bundle_redaction_receipt" in row["missing_receipts"]
        assert "verifier_pass_fail_receipt" in row["missing_receipts"]


def test_no_tool_authority_is_granted(tmp_path):
    read_model = inventory.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        repo_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert read_model["authority_boundary"]["tool_authority_allowed"] is False
    assert read_model["authority_boundary"]["tool_execution_allowed"] is False
    for candidate in read_model["harness_candidates"]:
        assert candidate["authority_boundary"]["tool_authority_allowed"] is False
        assert candidate["authority_boundary"]["protected_actions_allowed"] is False


def test_no_unsafe_true_grants(tmp_path):
    read_model = inventory.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        repo_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    assert read_model["status"] == inventory.READY_STATUS
    assert inventory.unsafe_true_grants(read_model) == []
    assert read_model["machine_proof"]["model_invoked"] is False
    assert read_model["machine_proof"]["runtime_connected"] is False
    assert read_model["machine_proof"]["worker_spawn_performed"] is False


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = inventory.export_local_lm_harness_inventory_receipts(
        read_model_root=_fixture_root(tmp_path),
        repo_root=tmp_path,
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Local LM Harness Inventory Receipts.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == inventory.READY_STATUS
    assert local == bridge
    assert inventory.unsafe_true_grants(local) == []
    assert wiki.startswith("# Local LM Harness Inventory Receipts")
