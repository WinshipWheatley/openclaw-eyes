import json
import pytest
from pathlib import Path

TEMPLATES = [
    "templates/agent/guardian_approval_request_packet_template.json",
    "templates/agent/guardian_approval_decision_packet_template.json",
]

SHARED_MANDATORY_FIELDS = [
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

def test_guardian_templates_exist():
    for path in TEMPLATES:
        assert Path(path).exists(), f"{path} missing"

def test_guardian_templates_valid_json():
    for path in TEMPLATES:
        content = Path(path).read_text()
        data = json.loads(content)
        assert isinstance(data, dict)

def test_guardian_templates_mandatory_fields():
    for path in TEMPLATES:
        data = json.loads(Path(path).read_text())
        for field in SHARED_MANDATORY_FIELDS:
            assert field in data, f"Field {field} missing in {path}"

def test_guardian_packet_types():
    req = json.loads(Path(TEMPLATES[0]).read_text())
    dec = json.loads(Path(TEMPLATES[1]).read_text())
    assert req["packet_type"] == "guardian.approval_request_packet"
    assert dec["packet_type"] == "guardian.approval_decision_packet"

def test_guardian_authority_boundaries():
    for path in TEMPLATES:
        data = json.loads(Path(path).read_text())
        allowed = data.get("allowed_actions", [])
        blocked = data.get("blocked_actions", [])
        
        # Guardian is a gate, not a planner or executor
        for action in allowed:
            assert "plan" not in action.lower()
            assert "execute" not in action.lower()
            assert "propose" not in action.lower()
            
        assert "bypass_guardian_for_tier_2" in blocked
        assert "llm_override_policy" in blocked

def test_guardian_request_boundaries():
    data = json.loads(Path(TEMPLATES[0]).read_text())
    blocked = data.get("blocked_actions", [])
    assert "include_plaintext_secrets" in blocked
    assert "modify_action_payload" in blocked

def test_guardian_decision_boundaries():
    data = json.loads(Path(TEMPLATES[1]).read_text())
    blocked = data.get("blocked_actions", [])
    receipts = data.get("required_receipts", [])
    notes = data.get("boundary_notes", "")
    
    assert "approval_log_entry" in receipts
    assert "approve_modified_payload" in blocked
    assert "approve_broad_future_class" in blocked
    
    if "YES_FOR_ALL" in notes:
        assert "NOT a blanket future approval" in notes or "not a blanket future approval" in notes
        assert "scope audit" in notes
