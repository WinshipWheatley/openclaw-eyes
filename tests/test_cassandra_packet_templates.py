import json
from pathlib import Path

TEMPLATES = [
    "templates/agent/cassandra_email_triage_packet_template.json",
    "templates/agent/cassandra_outreach_draft_packet_template.json",
    "templates/agent/cassandra_pii_handling_packet_template.json",
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

def test_cassandra_packet_templates_exist():
    for template_path in TEMPLATES:
        assert Path(template_path).exists(), f"Template {template_path} is missing."

def test_cassandra_packet_templates_valid_json():
    for template_path in TEMPLATES:
        with open(template_path, "r") as f:
            data = json.load(f)
            assert isinstance(data, dict), f"Template {template_path} must be a JSON object."

def test_cassandra_packet_templates_mandatory_fields():
    for template_path in TEMPLATES:
        with open(template_path, "r") as f:
            data = json.load(f)
            for field in MANDATORY_FIELDS:
                assert field in data, f"Field '{field}' is missing from {template_path}."

def test_cassandra_packet_templates_types_match():
    expected_types = {
        "templates/agent/cassandra_email_triage_packet_template.json": "cassandra.email_triage_packet",
        "templates/agent/cassandra_outreach_draft_packet_template.json": "cassandra.outreach_draft_packet",
        "templates/agent/cassandra_pii_handling_packet_template.json": "cassandra.pii_handling_packet",
    }
    for template_path, expected_type in expected_types.items():
        with open(template_path, "r") as f:
            data = json.load(f)
            assert data["packet_type"] == expected_type, f"Wrong packet_type in {template_path}."

def test_cassandra_packet_templates_safety_boundaries():
    for template_path in TEMPLATES:
        with open(template_path, "r") as f:
            data = json.load(f)
            blocked = data.get("blocked_actions", [])
            allowed = data.get("allowed_actions", [])
            
            # None of these templates should allow sending
            assert "send" not in allowed, f"{template_path} must not allow 'send'."
            
            # Triage and Outreach explicitly block send
            if "triage" in template_path or "outreach" in template_path:
                assert "send" in blocked, f"{template_path} must explicitly block 'send'."
            
            # PII must block raw exposure
            if "pii" in template_path:
                assert "expose_raw_pii_to_external_model" in blocked, f"{template_path} must block raw PII exposure."
