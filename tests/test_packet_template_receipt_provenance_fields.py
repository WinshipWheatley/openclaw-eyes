import json
import os
from pathlib import Path
import pytest

TEMPLATES_DIR = Path("templates/agent")
PRODUCER_TEMPLATES_DIR = Path("templates/producer")

def get_all_templates():
    templates = list(TEMPLATES_DIR.glob("*.json"))
    if PRODUCER_TEMPLATES_DIR.exists():
        templates.extend(list(PRODUCER_TEMPLATES_DIR.glob("*.json")))
    return sorted(templates)

@pytest.mark.parametrize("template_path", get_all_templates())
def test_template_has_required_fields(template_path):
    """
    Every packet template JSON object must include:
    - packet_type
    - packet_id
    - contract_version
    - input_evidence
    - required_receipts
    - provenance_refs
    - boundary_notes
    """
    with open(template_path, 'r') as f:
        data = json.load(f)

    # Naming synonyms for legacy/universal templates
    is_action_intent = template_path.name == "action_intent_packet_template.json"
    is_agent_intake = template_path.name == "agent_intake_packet_template.json"
    is_producer_review = template_path.name == "producer_review_template.json"

    # Define synonyms for action_intent as requested
    field_map = {
        "packet_type": ["packet_type"],
        "packet_id": ["packet_id"],
        "contract_version": ["contract_version"],
        "required_receipts": ["required_receipts"],
        "provenance_refs": ["provenance_refs"],
        "input_evidence": ["input_evidence"],
        "boundary_notes": ["boundary_notes"]
    }

    if is_action_intent:
        field_map["packet_type"].append("action_type")
        field_map["packet_id"].append("action_id")
        field_map["required_receipts"].append("expected_receipts") # Legacy synonym allowed per task
        field_map["required_receipts"].append("evidence_required_before_execution")

    if is_agent_intake:
        field_map["packet_type"].append("agent_lane")
        field_map["input_evidence"].append("raw_user_text")
        field_map["required_receipts"].append("evidence_required")
        field_map["provenance_refs"].append("provided_context_refs")

    if is_producer_review:
        field_map["contract_version"].append("producer_contract_version")
        field_map["packet_id"].append("review_id")

    # Check for required fields or their synonyms
    for field, synonyms in field_map.items():
        # Handle contract_version specifically since it was outside the loop
        if field == "contract_version":
            found = any(syn in data for syn in synonyms)
            assert found, f"Template {template_path.name} is missing contract_version (checked: {synonyms})"
            continue

        found = any(syn in data for syn in synonyms)
        assert found, f"Template {template_path.name} is missing required field: {field} (checked synonyms: {synonyms})"

    # required_receipts (or synonym) must be a list
    receipt_field = next((syn for syn in field_map["required_receipts"] if syn in data), "required_receipts")
    assert isinstance(data[receipt_field], list), f"Template {template_path.name}: {receipt_field} must be a list"

    # provenance_refs (or synonym) must be a list
    provenance_field = next((syn for syn in field_map["provenance_refs"] if syn in data), "provenance_refs")
    assert isinstance(data[provenance_field], list), f"Template {template_path.name}: {provenance_field} must be a list"

def test_specific_templates_have_non_empty_receipts():
    """
    For templates whose packet_type or filename implies an approval/decision/receipt/action side-effect,
    required_receipts must not be empty.
    """
    targets = {
        "chief_approval_decision_packet_template.json": "required_receipts",
        "guardian_approval_decision_packet_template.json": "required_receipts",
        "guardian_approval_request_packet_template.json": "required_receipts",
        "cassandra_outreach_draft_packet_template.json": "required_receipts",
        "cassandra_pii_handling_packet_template.json": "required_receipts",
        "action_intent_packet_template.json": "expected_receipts" # Legacy synonym
    }

    for filename, field_name in targets.items():
        path = TEMPLATES_DIR / filename
        if not path.exists():
            continue

        with open(path, 'r') as f:
            data = json.load(f)

        assert len(data[field_name]) > 0, f"Template {filename} must have at least one {field_name}"

def test_advisory_and_intake_templates_posture():
    """
    For advisory-only templates, required_receipts may be empty, but boundary_notes or output
    must clearly indicate advisory/non-canonical/no runtime authority.
    """
    # Hermes templates
    hermes_files = list(TEMPLATES_DIR.glob("hermes_*.json"))
    for path in hermes_files:
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Check boundary_notes or output for advisory keywords
        combined_text = (data.get("boundary_notes", "") + str(data.get("output", ""))).lower()
        advisory_keywords = ["advisory", "non-canonical", "no runtime authority", "proposal"]
        assert any(kw in combined_text for kw in advisory_keywords), \
            f"Hermes template {path.name} must declare advisory/non-canonical status in boundary_notes or output"

    # Intake/Suggestion templates
    intake_files = [
        TEMPLATES_DIR / "agent_intake_packet_template.json",
        TEMPLATES_DIR / "action_intent_packet_template.json"
    ]
    for path in intake_files:
        if not path.exists():
            continue
        with open(path, 'r') as f:
            data = json.load(f)
        
        # If required_receipts is empty, blocked_actions/boundary_notes must clarify no authority
        if len(data.get("required_receipts", [])) == 0:
            combined_text = (data.get("boundary_notes", "") + str(data.get("blocked_actions", ""))).lower()
            authority_guards = ["no execution", "no mutation", "approval required", "not authorize"]
            assert any(kw in combined_text for kw in authority_guards), \
                f"Intake/Intent template {path.name} with empty receipts must declare lack of execution authority"
