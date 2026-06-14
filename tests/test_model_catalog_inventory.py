import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import model_catalog_inventory as catalog


FIXED_NOW = "2026-06-07T06:35:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / "local_lm_runtime_discovery.json",
        {
            "status": "LOCAL_LM_RUNTIME_DISCOVERY_READY",
            "runtime_candidates": [
                {
                    "runtime_ref": "ollama",
                    "present": True,
                    "already_running": True,
                    "invocation_allowed": False,
                    "proof_response_pilot_allowed": False,
                    "privacy_risk": "local runtime present but blocked",
                    "missing_receipts": ["operator_approval_receipt", "model_invocation_boundary_receipt"],
                },
                {
                    "runtime_ref": "local_llm_shadow_mode",
                    "present": True,
                    "already_running": "unknown",
                    "invocation_allowed": False,
                    "proof_response_pilot_allowed": False,
                    "missing_receipts": ["operator_approval_receipt"],
                },
            ],
        },
    )
    _write_json(root / "local_lm_proof_response_preflight_receipts.json", {"status": "LOCAL_LM_PROOF_RESPONSE_PREFLIGHT_RECEIPTS_READY"})
    _write_json(root / "local_lm_harness_inventory_receipts.json", {"status": "LOCAL_LM_HARNESS_INVENTORY_RECEIPTS_READY"})
    _write_json(
        root / "harness_provider_selection_registry.json",
        {
            "status": "HARNESS_PROVIDER_SELECTION_READY",
            "provider_classes": [
                "codex_desktop_operator_assist",
                "local_llm_shadow_mode",
                "future_local_open_model",
                "external_llm_blocked_by_default",
            ],
        },
    )
    _write_json(root / "provider_policy_registry.json", {"status": "PROVIDER_POLICY_REGISTRY_READY", "known": ["openai", "gemini", "claude"]})
    _write_json(root / "operator_assist_provider_registry.json", {"status": "OPERATOR_ASSIST_PROVIDER_REGISTRY_READY", "providers": ["mac_codex_desktop_operator_assist"]})
    _write_json(root / "proof_bundle_redaction_policy.json", {"status": "PROOF_BUNDLE_REDACTION_HARDENING_READY"})
    _write_json(root / "proof_bundle_builder_redaction_status.json", {"status": "PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY"})
    _write_json(root / "goldilocks_gate_calibration.json", {"status": "GOLDILOCKS_GATE_CALIBRATION_READY"})
    _write_json(root / "local_lm_proof_to_response_readiness_gate.json", {"status": "LOCAL_LM_PROOF_RESPONSE_READINESS_GATE_READY"})
    _write_json(root / "local_lm_proof_response_pilot_approval_packet.json", {"status": "LOCAL_LM_PROOF_RESPONSE_PILOT_APPROVAL_PACKET_READY"})
    return root


def _read_model(tmp_path: Path) -> dict:
    return catalog.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)


def test_inventory_includes_local_and_external_buckets(tmp_path):
    read_model = _read_model(tmp_path)
    classes = {row["candidate_class"] for row in read_model["model_candidates"]}

    assert read_model["status"] == catalog.READY_STATUS
    assert "local_runtime_installed" in classes
    assert "local_sidecar_harness" in classes
    assert "operator_assist_harness" in classes
    assert "external_provider_catalog" in classes
    assert "blocked_unknown_or_future" in classes
    assert read_model["summary"]["local_candidates"] > 0
    assert read_model["summary"]["external_catalog_candidates"] >= 8


def test_no_candidate_has_invocation_allowed_true(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["summary"]["candidates_currently_invocation_allowed"] == 0
    assert all(row["invocation_allowed"] is False for row in read_model["model_candidates"])


def test_no_candidate_has_proof_bundle_allowed_true(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["summary"]["candidates_proof_bundle_allowed"] == 0
    assert all(row["proof_bundle_allowed"] is False for row in read_model["model_candidates"])


def test_external_providers_are_blocked_by_default(tmp_path):
    read_model = _read_model(tmp_path)
    external = [row for row in read_model["model_candidates"] if row["candidate_class"] == "external_provider_catalog"]

    assert external
    for row in external:
        assert row["locality"] == "external"
        assert row["external_provider_used"] is False
        assert row["invocation_allowed"] is False
        assert row["proof_bundle_allowed"] is False
        assert "external_provider_exception_gate_receipt" in row["missing_receipts"]
        assert "private_finance_or_client_proof" in row["data_classes_forbidden"]


def test_local_model_presence_does_not_grant_proof_access(tmp_path):
    read_model = _read_model(tmp_path)
    ollama = next(row for row in read_model["model_candidates"] if row["provider_or_runtime"] == "ollama")

    assert ollama["present"] is True
    assert ollama["running"] is True
    assert ollama["proof_bundle_allowed"] is False
    assert ollama["invocation_allowed"] is False


def test_tool_memory_business_authority_false_for_all(tmp_path):
    read_model = _read_model(tmp_path)

    for row in read_model["model_candidates"]:
        assert row["tool_authority"] is False
        assert row["memory_write_authority"] is False
        assert row["business_action_authority"] is False
        assert row["authority_boundary"]["tool_authority"] is False
        assert row["authority_boundary"]["business_action_authority"] is False


def test_missing_receipts_listed_for_every_candidate(tmp_path):
    read_model = _read_model(tmp_path)

    for row in read_model["model_candidates"]:
        assert row["missing_receipts"]
        assert "operator_approval_receipt" in row["missing_receipts"]


def test_summary_required_decision_options(tmp_path):
    read_model = _read_model(tmp_path)
    summary = read_model["summary"]

    assert summary["recommended_next_decision"] == "select_model_for_review"
    assert set(summary["recommended_decision_options"]) == {
        "select_model_for_review",
        "request_external_catalog_research",
        "stay_shadow_only",
        "reject_for_now",
    }


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert catalog.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = catalog.export_model_catalog_inventory(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Model Catalog Inventory.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == catalog.READY_STATUS
    assert result["candidates_currently_invocation_allowed"] == "0"
    assert result["candidates_proof_bundle_allowed"] == "0"
    assert local == bridge
    assert catalog.unsafe_true_grants(local) == []
    assert wiki.startswith("# Model Catalog Inventory")
