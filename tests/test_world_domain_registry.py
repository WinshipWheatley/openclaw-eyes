import json

from scripts.build_world_domain_registry import (
    ALLOWED_SIGNAL_TYPES,
    EXPECTED_WORLD_IDS,
    READ_MODEL_VERSION,
    build_world_domain_registry,
    format_operator_world_domain_registry,
    main,
)


REQUIRED_WORLD_FIELDS = {
    "world_id",
    "label",
    "purpose",
    "examples_of_work",
    "allowed_signal_types",
    "signal_vocabulary_only",
    "authority_boundary",
    "runtime_authority",
    "activation_allowed",
    "backend_execution",
    "current_status_source",
    "dynamic_status_supported",
    "strategic_gravity_supported",
    "agent_presence_supported",
    "evidence_refs",
    "claims_not_made",
}


def _registry():
    return build_world_domain_registry()


def _payload_text(payload):
    return json.dumps(payload, sort_keys=True).lower()


def test_json_output_has_required_top_level_fields():
    payload = _registry()

    assert payload["read_model_version"] == READ_MODEL_VERSION
    assert payload["mode"] == "deterministic_registry"
    for key in [
        "runtime_authority",
        "activation_allowed",
        "backend_execution",
        "dynamic_world_state",
        "strategic_gravity_supported",
        "agent_presence_supported",
        "allowed_signal_types",
        "worlds",
        "claims_not_made",
    ]:
        assert key in payload


def test_expected_v0_worlds_are_present_in_stable_order():
    payload = _registry()

    assert [world["world_id"] for world in payload["worlds"]] == list(EXPECTED_WORLD_IDS)


def test_each_world_has_required_fields_and_examples():
    payload = _registry()

    for world in payload["worlds"]:
        assert REQUIRED_WORLD_FIELDS <= set(world)
        assert world["label"]
        assert world["purpose"]
        assert world["examples_of_work"]
        assert world["authority_boundary"]
        assert isinstance(world["evidence_refs"], list)


def test_authority_and_execution_flags_are_false_for_registry_and_worlds():
    payload = _registry()

    assert payload["runtime_authority"] is False
    assert payload["activation_allowed"] is False
    assert payload["backend_execution"] is False
    assert payload["dynamic_world_state"] is False
    assert payload["strategic_gravity_supported"] is False
    assert payload["agent_presence_supported"] is False

    for world in payload["worlds"]:
        assert world["runtime_authority"] is False
        assert world["activation_allowed"] is False
        assert world["backend_execution"] is False


def test_dynamic_status_gravity_and_agent_presence_are_not_supported_per_world():
    payload = _registry()

    for world in payload["worlds"]:
        assert world["current_status_source"] == "registry_only"
        assert world["dynamic_status_supported"] is False
        assert world["strategic_gravity_supported"] is False
        assert world["agent_presence_supported"] is False


def test_allowed_signal_types_are_vocabulary_only_not_active_claims():
    payload = _registry()

    assert payload["allowed_signal_types"] == list(ALLOWED_SIGNAL_TYPES)
    assert payload["signal_vocabulary_only"] is True
    assert payload["active_signal_claims"] == []
    assert payload["current_status_source"] == "registry_only"

    for world in payload["worlds"]:
        assert world["allowed_signal_types"] == list(ALLOWED_SIGNAL_TYPES)
        assert world["signal_vocabulary_only"] is True
        assert world["current_status_source"] == "registry_only"


def test_operator_output_uses_cockpit_grammar():
    output = format_operator_world_domain_registry(_registry())

    assert "World / Domain Registry v0" in output
    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output
    assert output.index("Evidence:") < output.index("Boundary:")
    assert output.index("Boundary:") < output.index("Blocked:")
    assert output.index("Blocked:") < output.index("Next safe move:")
    assert '"worlds"' not in output


def test_output_does_not_claim_live_world_status_or_activation():
    payload = _registry()
    text = _payload_text(payload) + "\n" + format_operator_world_domain_registry(payload).lower()

    for forbidden in [
        "world status is live",
        "dynamic world status is supported",
        "agents are active",
        "agent presence is implemented",
        "strategic gravity scoring is implemented",
        "runtime activation is allowed",
        "customer deployment active",
        "external tools active",
        "healthy",
        "all systems nominal",
        "heartbeat",
    ]:
        assert forbidden not in text

    assert "world_status_claims" in payload["claims_not_made"]
    assert "strategic_gravity_scoring" in payload["claims_not_made"]
    assert "runtime_activation_authority" in payload["claims_not_made"]


def test_cli_json_output_is_machine_readable(capsys):
    exit_code = main(["--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["read_model_version"] == READ_MODEL_VERSION
    assert [world["world_id"] for world in payload["worlds"]] == list(EXPECTED_WORLD_IDS)
    assert payload["runtime_authority"] is False
    assert payload["dynamic_world_state"] is False


def test_cli_operator_output(capsys):
    exit_code = main(["--format", "operator"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "World / Domain Registry v0" in output
    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output
