import json
import os
from pathlib import Path

def test_agent_intake_action_contract_files_exist():
    doc_path = Path("docs/operations/OPENCLAW_AGENT_INTAKE_AND_ACTION_INTENT_CONTRACT_V0.md")
    intake_path = Path("templates/agent/agent_intake_packet_template.json")
    action_path = Path("templates/agent/action_intent_packet_template.json")

    assert doc_path.exists(), "Contract doc must exist"
    assert intake_path.exists(), "Intake template must exist"
    assert action_path.exists(), "Action template must exist"

def test_templates_parse_and_have_safe_defaults():
    intake_path = Path("templates/agent/agent_intake_packet_template.json")
    action_path = Path("templates/agent/action_intent_packet_template.json")

    with open(intake_path, 'r') as f:
        intake_data = json.load(f)
    with open(action_path, 'r') as f:
        action_data = json.load(f)

    assert intake_data.get("no_side_effects") is True, "Intake must have no_side_effects = true"
    assert action_data.get("human_confirmation_required") is True, "Action must require human confirmation"
    assert action_data.get("no_execution_without_approval") is True, "Action must not execute without approval"

def test_doc_content_rules():
    doc_path = Path("docs/operations/OPENCLAW_AGENT_INTAKE_AND_ACTION_INTENT_CONTRACT_V0.md")
    content = doc_path.read_text().lower()

    # Rule 2: unification, not rebuild
    assert "unification, not rebuild" in content, "Must include unification phrase"

    # Rule 7: evidence/live-claim rule
    assert "evidence" in content and "receipt" in content and "claim" in content, "Must include evidence/live-claim rule"

    # Rule 9: Producer mention
    assert "producer is now a concrete early implementation" in content or "producer is" in content, "Must mention Producer as early implementation"

    # Rule 10: Boundaries (cannot execute directly)
    assert "not imply cassandra or producer can execute tools directly" in content, "Must not imply direct execution authority"
