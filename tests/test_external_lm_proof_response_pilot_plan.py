import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import external_lm_proof_response_pilot_plan as plan
import proof_to_response_runtime


FIXED_NOW = "2026-06-07T14:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / "model_catalog_inventory.json",
        {
            "status": "MODEL_CATALOG_INVENTORY_READY",
            "model_candidates": [
                {
                    "candidate_ref": "model_candidate:external_provider:openai",
                    "candidate_class": "external_provider_catalog",
                    "provider_or_runtime": "openai",
                    "model_or_harness_name": "OpenAI",
                    "invocation_allowed": False,
                    "proof_bundle_allowed": False,
                },
                {
                    "candidate_ref": "model_candidate:external_provider:anthropic",
                    "candidate_class": "external_provider_catalog",
                    "provider_or_runtime": "anthropic",
                    "model_or_harness_name": "Anthropic",
                    "invocation_allowed": False,
                    "proof_bundle_allowed": False,
                },
            ],
        },
    )
    _write_json(root / "proof_to_response_lm_shadow_pilot.json", {"status": "PROOF_TO_RESPONSE_LM_SHADOW_PILOT_READY"})
    _write_json(root / "proof_bundle_redaction_policy.json", {"status": "PROOF_BUNDLE_REDACTION_HARDENING_READY"})
    _write_json(root / "proof_bundle_builder_redaction_status.json", {"status": "PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY"})
    _write_json(root / "context_freshness_decision_trace_gate.json", {"status": "CONTEXT_FRESHNESS_DECISION_TRACE_GATE_READY"})
    _write_json(root / "proof_bundle_freshness_trace_status.json", {"status": "PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY"})
    _write_json(root / "agent_response_voice_modes.json", {"status": "AGENT_RESPONSE_VOICE_MODES_READY"})
    _write_json(
        root / proof_to_response_runtime.STATUS_JSON_EXPORT_NAME,
        {
            "status": proof_to_response_runtime.READY_STATUS,
            "active_candidate_source": proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
        },
    )
    _write_json(root / "goldilocks_gate_calibration.json", {"status": "GOLDILOCKS_GATE_CALIBRATION_READY"})
    return root


def _read_model(tmp_path: Path) -> dict:
    return plan.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)


def test_private_proof_is_blocked(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["status"] == plan.READY_STATUS
    assert "real_private_finance_proof" in read_model["explicitly_blocked_data"]
    assert "client_payment_documents" in read_model["explicitly_blocked_data"]
    assert read_model["first_safe_pilot_scope"]["private_proof_allowed"] is False
    assert read_model["machine_proof"]["private_proof_blocked"] is True


def test_synthetic_bundle_may_be_proposed_but_not_approved(tmp_path):
    read_model = _read_model(tmp_path)
    policy = read_model["approved_first_test_data_policy"]

    assert "synthetic_proof_bundle" in read_model["approved_first_test_data"]
    assert policy["synthetic_bundle_may_be_proposed"] is True
    assert policy["synthetic_bundle_approved_now"] is False
    assert read_model["first_safe_pilot_scope"]["synthetic_bundle_allowed_now"] is False
    for row in read_model["candidate_external_provider_classes"]:
        assert row["synthetic_bundle_allowed"] is False


def test_external_invocation_allowed_false(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["authority_boundary"]["external_provider_connect_allowed"] is False
    assert read_model["implementation_boundary"]["external_provider_connected"] is False
    for row in read_model["candidate_external_provider_classes"]:
        assert row["invocation_allowed"] is False


def test_private_proof_bundle_allowed_false_for_all_candidates(tmp_path):
    read_model = _read_model(tmp_path)

    for row in read_model["candidate_external_provider_classes"]:
        assert row["proof_bundle_allowed"] is False
        assert row["private_proof_allowed"] is False


def test_verifier_mandatory(tmp_path):
    read_model = _read_model(tmp_path)

    assert "proof_to_response_verifier" in read_model["verifier_requirements"]
    assert "no_unsupported_paid_sent_submitted_executed_claims" in read_model["verifier_requirements"]
    assert "allowed_controls_only" in read_model["verifier_requirements"]
    assert read_model["machine_proof"]["verifier_mandatory"] is True


def test_no_authority_grants(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["authority_boundary"]["authority_granted"] is False
    assert read_model["authority_boundary"]["protected_actions_allowed"] is False
    assert read_model["authority_boundary"]["tool_authority"] is False
    assert read_model["authority_boundary"]["business_action_authority"] is False
    for row in read_model["candidate_external_provider_classes"]:
        assert row["authority_boundary"]["authority_granted"] is False
        assert row["authority_boundary"]["protected_actions_allowed"] is False


def test_operator_approval_required(tmp_path):
    read_model = _read_model(tmp_path)

    assert "operator_approval_receipt" in read_model["receipts_required_before_any_external_test"]
    assert "approve_synthetic_external_llm_quality_test" in read_model["operator_decision_options"]
    assert "approve_manual_external_llm_test_with_synthetic_bundle" in read_model["operator_decision_options"]
    assert read_model["machine_proof"]["operator_approval_required"] is True


def test_external_catalog_candidates_are_included(tmp_path):
    read_model = _read_model(tmp_path)
    refs = {row["provider_ref"] for row in read_model["candidate_external_provider_classes"]}

    assert "external_llm_blocked_by_default" in refs
    assert "manual_paste_test_with_synthetic_bundle" in refs
    assert "approved_api_test_future_gated" in refs
    assert "model_candidate:external_provider:openai" in refs
    assert "model_candidate:external_provider:anthropic" in refs


def test_expected_synthetic_finance_scope(tmp_path):
    scope = _read_model(tmp_path)["first_safe_pilot_scope"]

    assert scope["preferred_scope"] == "synthetic_finance_capital_hilton_payment_watch"
    assert "payment evidence missing" in scope["synthetic_facts"]
    assert "ledger untouched" in scope["synthetic_facts"]
    assert "paid=false" in scope["synthetic_facts"]
    assert scope["expected_external_lm_output"]["next_step"] == "Attach payment evidence."


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert plan.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = plan.export_external_lm_proof_response_pilot_plan(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "External LM Proof Response Pilot Plan.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == plan.READY_STATUS
    assert local == bridge
    assert plan.unsafe_true_grants(local) == []
    assert wiki.startswith("# External LM Proof Response Pilot Plan")
