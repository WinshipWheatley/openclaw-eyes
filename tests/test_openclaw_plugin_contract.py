import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_plugin_contract as contract


def test_plugin_contract_validator_fixtures_pass():
    result = contract.validate_fixture_descriptors()

    assert result["valid"] is True
    assert result["validated_plugin_ids"] == sorted(contract.FIXTURE_PLUGIN_IDS)
    assert all(not errors for errors in result["errors"].values())


def test_plugin_contract_fails_without_denied_actions():
    descriptor = copy.deepcopy(contract.fixture_descriptors()["openclaw.read_only_email_lookup"])
    descriptor["denied_actions"] = []

    assert "denied_actions must be explicit and non-empty" in contract.validate_descriptor(descriptor)


def test_plugin_contract_fails_without_required_authority():
    descriptor = copy.deepcopy(contract.fixture_descriptors()["openclaw.follow_up_draft_generator"])
    descriptor.pop("required_authority")

    errors = contract.validate_descriptor(descriptor)
    assert "missing required field: required_authority" in errors
    assert "required_authority must be present" in errors


def test_plugin_contract_fails_if_production_side_effects_allowed():
    descriptor = copy.deepcopy(contract.fixture_descriptors()["openclaw.contact_identity_extraction"])
    descriptor["production_behavior"]["side_effects_default_denied"] = False
    descriptor["production_behavior"]["production_side_effects_allowed"] = True

    errors = contract.validate_descriptor(descriptor)
    assert "production side effects must default denied" in errors
    assert "production side effects must not be allowed in fixtures" in errors


def test_plugin_contract_fails_without_receipts_verifier_redaction_or_freshness():
    descriptor = copy.deepcopy(contract.fixture_descriptors()["openclaw.payment_uncertainty_summarizer"])
    descriptor["receipt_requirements"] = []
    descriptor["verifier_rules"] = []
    descriptor["redaction_policy"] = {}
    descriptor["freshness_policy"] = {}

    errors = contract.validate_descriptor(descriptor)
    assert "receipt_requirements is required" in errors
    assert "verifier_rules is required" in errors
    assert "redaction_policy is required" in errors
    assert "freshness_policy is required" in errors


def test_plugin_contract_fails_if_raw_authority_granted_is_trusted():
    descriptor = copy.deepcopy(contract.fixture_descriptors()["openclaw.verifier_proof_checker"])
    descriptor["required_authority"]["raw_authority_granted_trusted"] = True

    assert "raw_authority_granted_trusted must be false" in contract.validate_descriptor(descriptor)
