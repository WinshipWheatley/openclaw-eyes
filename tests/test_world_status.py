import json

from scripts.build_world_domain_registry import EXPECTED_WORLD_IDS
from scripts.build_world_status import (
    READ_MODEL_VERSION,
    build_world_status,
    format_operator_world_status,
    main,
)


REQUIRED_WORLD_FIELDS = {
    "world_id",
    "label",
    "state",
    "state_source",
    "evidence",
    "boundary",
    "blocked",
    "next_safe_move",
    "runtime_authority",
    "activation_allowed",
    "backend_execution",
    "backend_execution_authorized",
    "claims_not_made",
}


def _read_model():
    return build_world_status()


def _payload_text(payload):
    return json.dumps(payload, sort_keys=True).lower()


def test_json_output_has_required_top_level_fields():
    payload = _read_model()

    assert payload["read_model_version"] == READ_MODEL_VERSION
    assert payload["mode"] == "deterministic_registry_status"
    for key in [
        "runtime_authority",
        "activation_allowed",
        "backend_execution",
        "backend_execution_authorized",
        "dynamic_world_state",
        "strategic_gravity_supported",
        "agent_presence_supported",
        "world_count",
        "worlds",
        "claims_not_made",
    ]:
        assert key in payload


def test_expected_worlds_are_present_in_registry_order():
    payload = _read_model()

    assert payload["world_count"] == 8
    assert [world["world_id"] for world in payload["worlds"]] == list(EXPECTED_WORLD_IDS)


def test_every_world_has_required_fields_and_inspect_only_status():
    payload = _read_model()

    for world in payload["worlds"]:
        assert REQUIRED_WORLD_FIELDS <= set(world)
        assert world["label"]
        assert world["state"] in {"inspect_only", "registry_only"}
        assert world["state"] == "inspect_only"
        assert world["state_source"] == "registry_only"
        assert world["evidence"]
        assert world["boundary"]
        assert world["blocked"]
        assert world["next_safe_move"]


def test_authority_and_execution_flags_are_false_for_read_model_and_worlds():
    payload = _read_model()

    assert payload["runtime_authority"] is False
    assert payload["activation_allowed"] is False
    assert payload["backend_execution"] is False
    assert payload["backend_execution_authorized"] is False
    assert payload["dynamic_world_state"] is False
    assert payload["strategic_gravity_supported"] is False
    assert payload["agent_presence_supported"] is False
    for world in payload["worlds"]:
        assert world["runtime_authority"] is False
        assert world["activation_allowed"] is False
        assert world["backend_execution"] is False
        assert world["backend_execution_authorized"] is False


def test_no_world_claims_live_or_dynamic_status():
    payload = _read_model()
    forbidden_states = {"flagged", "glowing", "hot", "critical_consequence"}

    assert {world["state"] for world in payload["worlds"]}.isdisjoint(forbidden_states)
    assert payload["dynamic_world_state"] is False
    assert payload["strategic_gravity_supported"] is False
    assert payload["agent_presence_supported"] is False
    text = _payload_text(payload)
    for forbidden in [
        "world status is live",
        "dynamic status is supported",
        "strategic gravity scoring is implemented",
        "agents are active",
        "live health is checked",
        "runtime healthy",
        "all systems nominal",
        "heartbeat",
    ]:
        assert forbidden not in text


def test_operator_output_uses_required_cockpit_grammar():
    output = format_operator_world_status(_read_model())

    assert "World Status Read-Model v0" in output
    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output
    assert "8 worlds have conservative registry-backed status records" in output
    assert "World status is inspect-only / registry-only" in output
    assert "No dynamic world state, gravity, or agent presence is implemented" in output
    assert "Add evidence freshness / strategic gravity inputs before dynamic attention states" in output
    assert output.index("Evidence:") < output.index("Boundary:")
    assert output.index("Boundary:") < output.index("Blocked:")
    assert output.index("Blocked:") < output.index("Next safe move:")
    assert '"worlds"' not in output


def test_cli_json_output_is_machine_readable(capsys):
    exit_code = main(["--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["read_model_version"] == READ_MODEL_VERSION
    assert payload["world_count"] == 8
    assert payload["runtime_authority"] is False
    assert payload["dynamic_world_state"] is False


def test_cli_operator_output(capsys):
    exit_code = main(["--format", "operator"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "World Status Read-Model v0" in output
    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output
