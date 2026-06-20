from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent_perspective as perspective


def test_required_agents_have_self_identity_and_operator_reference_policy():
    registry = perspective.build_perspective_registry()

    assert registry["machine_proof"]["required_agents_have_self_identity"] is True
    assert registry["machine_proof"]["operator_first_person_blur_allowed"] is False
    assert set(perspective.REQUIRED_AGENT_REFS).issubset(set(registry["agents"]))
    for agent_ref in perspective.REQUIRED_AGENT_REFS:
        policy = registry["agents"][agent_ref]
        assert policy["self_identity"]["display_name"]
        assert '"I", "me", "my"' in policy["first_person_policy"]
        assert "Winship" in policy["operator_reference_policy"]
        assert "never" in policy["forbidden_identity_blur"].lower()


def test_cassandra_prompt_pins_i_to_cassandra_not_operator():
    prompt = perspective.perspective_prompt("cassandra")

    assert "You are Cassandra" in prompt
    assert "refer only to Cassandra" in prompt
    assert "The human operator is Winship" in prompt
    assert "must never use first-person words to mean Winship" in prompt
