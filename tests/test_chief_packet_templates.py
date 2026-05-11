import json
from pathlib import Path

TEMPLATES = [
    "templates/agent/chief_action_intent_evaluation_packet_template.json",
    "templates/agent/chief_approval_decision_packet_template.json",
    "templates/agent/chief_acceptance_verdict_packet_template.json",
    "templates/agent/chief_routing_decision_packet_template.json",
]

MANDATORY_FIELDS = [
    "contract_version",
    "packet_type",
    "packet_id",
    "created_at",
    "source_basis",
    "status",
    "owner_lane",
    "input_evidence",
    "output",
    "allowed_actions",
    "blocked_actions",
    "required_receipts",
    "provenance_refs",
    "boundary_notes",
]

def test_chief_packet_templates_exist():
    for template_path in TEMPLATES:
        assert Path(template_path).exists(), f"Template {template_path} is missing."

def test_chief_packet_templates_valid_json():
    for template_path in TEMPLATES:
        with open(template_path, "r") as f:
            data = json.load(f)
            assert isinstance(data, dict), f"Template {template_path} must be a JSON object."

def test_chief_packet_templates_mandatory_fields():
    for template_path in TEMPLATES:
        with open(template_path, "r") as f:
            data = json.load(f)
            for field in MANDATORY_FIELDS:
                assert field in data, f"Field '{field}' is missing from {template_path}."

def test_chief_packet_templates_types_match():
    expected_types = {
        "templates/agent/chief_action_intent_evaluation_packet_template.json": "chief.action_intent_evaluation_packet",
        "templates/agent/chief_approval_decision_packet_template.json": "chief.approval_decision_packet",
        "templates/agent/chief_acceptance_verdict_packet_template.json": "chief.acceptance_verdict_packet",
        "templates/agent/chief_routing_decision_packet_template.json": "chief.routing_decision_packet",
    }
    for template_path, expected_type in expected_types.items():
        with open(template_path, "r") as f:
            data = json.load(f)
            assert data["packet_type"] == expected_type, f"Wrong packet_type in {template_path}."

def test_chief_packet_templates_safety_boundaries():
    for template_path in TEMPLATES:
        with open(template_path, "r") as f:
            data = json.load(f)
            blocked = data.get("blocked_actions", [])
            
            # Universal Chief blocks or template-specific equivalents
            assert "llm_override_policy" in blocked, f"{template_path} must block llm_override_policy"
            
            has_guardian_block = (
                "bypass_guardian_for_tier_2" in blocked or 
                "override_guardian_operator_or_proof_requirements" in blocked
            )
            assert has_guardian_block, f"{template_path} is missing Guardian bypass safety blocks."

def test_chief_approval_specific_blocks():
    path = "templates/agent/chief_approval_decision_packet_template.json"
    with open(path, "r") as f:
        data = json.load(f)
    blocked = data.get("blocked_actions", [])
    required_receipts = data.get("required_receipts", [])
    
    assert "bypass_guardian_for_tier_2" in blocked
    assert "approve_without_receipt" in blocked
    assert "approval_log_entry" in required_receipts

def test_chief_acceptance_verdict_values():
    path = "templates/agent/chief_acceptance_verdict_packet_template.json"
    with open(path, "r") as f:
        data = json.load(f)
    boundary_notes = data.get("boundary_notes", "")
    assert "APPROVE" in boundary_notes
    assert "REWORK" in boundary_notes
    assert "INSUFFICIENT_EVIDENCE" in boundary_notes

def test_no_template_allows_bypassing_guardian():
    for template_path in TEMPLATES:
        with open(template_path, "r") as f:
            data = json.load(f)
            allowed = data.get("allowed_actions", [])
            assert "bypass_guardian" not in str(allowed).lower()
