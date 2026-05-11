import json
from pathlib import Path
import pytest
import hermes_advisory_packet as contract

TEMPLATES_DIR = Path("templates/agent")
HERMES_ADVISORY_PACKET_TEMPLATE = TEMPLATES_DIR / "hermes_advisory_packet_template.json"
HERMES_ADVISORY_OUTPUT_MEMO_TEMPLATE = TEMPLATES_DIR / "hermes_advisory_output_memo_template.json"

MANDATORY_SHARED_FIELDS = [
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
    "boundary_notes"
]

@pytest.fixture
def advisory_packet():
    with open(HERMES_ADVISORY_PACKET_TEMPLATE, "r") as f:
        return json.load(f)

@pytest.fixture
def output_memo():
    with open(HERMES_ADVISORY_OUTPUT_MEMO_TEMPLATE, "r") as f:
        return json.load(f)

def test_templates_exist():
    assert HERMES_ADVISORY_PACKET_TEMPLATE.exists()
    assert HERMES_ADVISORY_OUTPUT_MEMO_TEMPLATE.exists()

def test_advisory_packet_structure(advisory_packet):
    for field in MANDATORY_SHARED_FIELDS:
        assert field in advisory_packet
    
    assert advisory_packet["packet_type"] == "hermes.advisory_packet"
    assert advisory_packet["status"] == "BUILT_BEHAVIOR_FORMALIZED_ADVISORY_NOT_RUNTIME_AUTHORITY"
    assert advisory_packet["owner_lane"] == "hermes_advisory"
    
    # Verify authority level and non-execution in output
    out = advisory_packet["output"]
    assert out["authority_level"] == contract.HERMES_AUTHORITY_LEVEL
    assert out["execution_allowed"] is False
    assert out["canonical_write_allowed"] is False
    assert out["queue_mutation_allowed"] is False
    assert out["approval_authority_allowed"] is False
    
    # Verify blocked actions
    blocked = advisory_packet["blocked_actions"]
    assert "mutate_canonical_state" in blocked
    assert "execute_runtime_action" in blocked
    assert "approve_action" in blocked
    assert "override_chief_or_guardian" in blocked

def test_output_memo_structure(output_memo):
    for field in MANDATORY_SHARED_FIELDS:
        assert field in output_memo
        
    assert output_memo["packet_type"] == "hermes.advisory_output_memo"
    assert output_memo["status"] == "BUILT_BEHAVIOR_FORMALIZED_ADVISORY_NOT_RUNTIME_AUTHORITY"
    assert output_memo["owner_lane"] == "hermes_advisory"
    
    # Verify advisory notice and non-execution in output
    out = output_memo["output"]
    assert out["non_canonical_notice"] == contract.NON_CANONICAL_NOTICE
    assert out["commands_executed"] is False
    assert out["decisions_made"] is False
    assert out["canonical_writes_made"] is False
    assert out["authority_level"] == contract.HERMES_AUTHORITY_LEVEL

    # Verify blocked actions
    blocked = output_memo["blocked_actions"]
    assert "mutate_runtime" in blocked
    assert "approve_or_deny" in blocked
    assert "bypass_operator_or_chief" in blocked

def test_templates_align_with_contract_required_fields(advisory_packet, output_memo):
    # Flatten JSON structure to check if all contract-required keys are present somewhere
    # Note: Template groups them into input_evidence/output, but contract expects them flat.
    
    packet_all_keys = set(advisory_packet.keys()) | set(advisory_packet["input_evidence"].keys()) | set(advisory_packet["output"].keys())
    for field in contract.REQUIRED_PACKET_FIELDS:
        # Created_at and packet_id are top level in template, others might be in groups
        assert field in packet_all_keys or field in advisory_packet

    memo_all_keys = set(output_memo.keys()) | set(output_memo["output"].keys()) | set(output_memo["input_evidence"].keys())
    for field in contract.REQUIRED_MEMO_FIELDS:
        assert field in memo_all_keys or field in output_memo
