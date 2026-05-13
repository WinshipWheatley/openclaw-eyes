import json

from scripts.build_helm_state import (
    READ_MODEL_VERSION,
    STATE_DEFINITIONS,
    build_helm_state,
    format_operator_helm_state,
    main,
)
from scripts.check_runtime_activation_gate import build_activation_gate_report


REQUIRED_STATES = {
    "quiet_helm",
    "flagged_world",
    "glowing_world",
    "hot_world",
    "critical_consequence",
    "ready_world",
    "agent_present",
    "approval_needed",
    "blocked_locked",
    "security_concern",
    "system_fault",
    "stale_evidence",
    "inspect_only",
    "next_safe_move",
}


def _current_status():
    return {
        "checked": True,
        "current": True,
        "status": "current",
        "exit_code": 0,
    }


def _read_model(**overrides):
    return build_helm_state(generated_status=_current_status(), **overrides)


def _payload_text(payload):
    return json.dumps(payload, sort_keys=True).lower()


def test_json_output_has_required_top_level_fields():
    payload = _read_model()

    assert payload["read_model_version"] == READ_MODEL_VERSION
    assert payload["mode"] == "deterministic_read_model"
    for key in [
        "runtime_authority",
        "activation_allowed",
        "backend_execution",
        "helm_state",
        "evidence",
        "boundary",
        "blocked",
        "next_safe_move",
        "worlds",
        "agent_presence",
        "strategic_gravity",
        "world_status_summary",
        "claims_not_made",
    ]:
        assert key in payload

    helm_state = payload["helm_state"]
    assert helm_state["state"]
    assert helm_state["state_family"] in {
        "system_integrity",
        "operational_attention",
        "strategic_gravity",
        "read_only",
    }
    assert helm_state["label"]
    assert helm_state["meaning"]
    assert helm_state["must_never_imply"]


def test_authority_and_execution_flags_are_false():
    payload = _read_model()

    assert payload["runtime_authority"] is False
    assert payload["activation_allowed"] is False
    assert payload["backend_execution"] is False
    assert payload["activation_gate"]["activation_allowed"] is False
    assert payload["activation_gate"]["runtime_authority"] is False


def test_emitted_state_is_inspect_only_for_current_read_only_posture():
    payload = _read_model()

    assert payload["helm_state"]["state"] == "inspect_only"
    assert payload["helm_state"]["state_family"] == "read_only"
    assert "no backend action or activation is authorized" in payload["helm_state"]["meaning"]


def test_stale_generated_status_emits_stale_evidence():
    payload = build_helm_state(
        generated_status={
            "checked": True,
            "current": False,
            "status": "stale_or_missing",
            "exit_code": 1,
        }
    )

    assert payload["helm_state"]["state"] == "stale_evidence"
    assert payload["helm_state"]["state_family"] == "system_integrity"


def test_helm_state_does_not_claim_live_health_or_process_activity():
    payload = _read_model()
    text = _payload_text(payload)

    for forbidden in [
        "all systems nominal",
        "healthy",
        "heartbeat",
        "active process id",
        "runtime ready",
        "runtime-ready",
        "modules active",
        "agent wired",
        "broker connected",
        "customer deployment active",
        "immutable ledger",
    ]:
        assert forbidden not in text

    assert "runtime status has been checked" in text
    assert "process_liveness" in payload["claims_not_made"]


def test_state_definitions_include_required_semantics():
    payload = _read_model()

    assert REQUIRED_STATES <= set(payload["state_definitions"])
    assert REQUIRED_STATES <= set(STATE_DEFINITIONS)
    for state in REQUIRED_STATES:
        definition = payload["state_definitions"][state]
        assert definition["state"] == state
        assert definition["meaning"]
        assert definition["required_evidence"]
        assert definition["must_never_imply"]
        assert definition["state_family"] in {
            "system_integrity",
            "operational_attention",
            "strategic_gravity",
            "read_only",
        }


def test_world_status_summary_is_registry_backed_without_dynamic_claims():
    payload = _read_model()
    summary = payload["world_status_summary"]

    assert payload["worlds"] == []
    assert payload["worlds_model"]["supported"] is True
    assert payload["worlds_model"]["source"] == "world_status_v0"
    assert payload["worlds_model"]["status_mode"] == "inspect_only_registry_backed"
    assert payload["worlds_model"]["dynamic_world_state"] is False
    assert summary["world_count"] == 8
    assert summary["world_status_source"] == "world_status_v0"
    assert summary["status_mode"] == "inspect_only_registry_backed"
    assert summary["state_source"] == "registry_only"
    assert summary["state_counts"] == {"inspect_only": 8}
    assert summary["dynamic_world_state"] is False
    assert summary["strategic_gravity"]["supported"] is False
    assert summary["agent_presence"] == []
    assert summary["registry_backed"] is True
    assert summary["live_health_claimed"] is False


def test_agent_presence_is_not_claimed_live_or_active():
    payload = _read_model()
    text = _payload_text(payload)

    assert payload["agent_presence"] == []
    assert payload["agent_presence_model"]["supported"] is False
    assert payload["agent_presence_model"]["live_agents_claimed"] is False
    assert "active_agent_presence" in payload["claims_not_made"]
    assert "agent wired" not in text
    assert "autonomous execution" in text


def test_strategic_gravity_is_not_supported_in_v0():
    payload = _read_model()

    assert payload["strategic_gravity"] == {
        "supported": False,
        "reason": "not_yet_implemented",
    }
    assert "strategic_gravity_scoring" in payload["claims_not_made"]


def test_operator_output_uses_cockpit_grammar():
    output = format_operator_helm_state(_read_model())

    assert "Helm State Read-Model v0" in output
    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output
    assert output.index("Evidence:") < output.index("Boundary:")
    assert output.index("Boundary:") < output.index("Blocked:")
    assert output.index("Blocked:") < output.index("Next safe move:")
    assert "Emitted helm state is `inspect_only`" in output
    assert "World Status v0 reports 8 registry-backed world records" in output
    assert "`runtime_authority=false`" in output
    assert "`backend_execution=false`" in output
    assert "`activation_allowed=false`" in output
    assert '"helm_state"' not in output


def test_activation_gate_remains_blocked():
    activation_gate = build_activation_gate_report()
    payload = _read_model(activation_gate=activation_gate)

    assert activation_gate["gate_state"] == "blocked_v0_contract"
    assert activation_gate["activation_allowed"] is False
    assert activation_gate["runtime_authority"] is False
    assert payload["activation_gate"]["gate_state"] == "blocked_v0_contract"
    assert payload["activation_allowed"] is False


def test_cli_json_output_is_machine_readable(capsys):
    exit_code = main(["--format", "json", "--skip-generated-status-check"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["read_model_version"] == READ_MODEL_VERSION
    assert payload["helm_state"]["state"] == "inspect_only"
    assert payload["runtime_authority"] is False
    assert payload["activation_allowed"] is False
    assert payload["backend_execution"] is False


def test_cli_operator_output(capsys):
    exit_code = main(["--format", "operator", "--skip-generated-status-check"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Helm State Read-Model v0" in output
    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output
