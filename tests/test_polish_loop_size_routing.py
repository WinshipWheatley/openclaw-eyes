from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polish_loop.task_routing import ROUTING_SCHEMA_VERSION, classify_task_routing


def _small_payload(**overrides):
    payload = {
        "task_type": "polish_loop_repair",
        "goal": "Add one synthetic unit test for the queue parser.",
        "scope": ["Update one parser edge case."],
        "success_criteria": ["The parser returns the expected synthetic row."],
        "allowed_files": ["tests/test_queue_parser.py"],
        "forbidden_files": ["workspaces/openclaw_program/generated_read_models"],
        "allowed_actions": ["edit allowed test file", "run focused pytest"],
        "forbidden_actions": ["no production systems", "no external actions", "no credentials"],
        "tests_to_run": ["/home/openclaw/.venv/bin/python -m pytest tests/test_queue_parser.py -q"],
        "stop_conditions": ["stop if production access would be needed"],
    }
    payload.update(overrides)
    return payload


def test_small_well_scoped_task_routes_ready():
    routing = classify_task_routing(_small_payload())

    assert routing["schema_version"] == ROUTING_SCHEMA_VERSION
    assert routing["size_class"] == "small"
    assert routing["readiness"] == "ready"
    assert routing["risk_flags"] == []
    assert routing["target_runner_tier"] == "quick"
    assert routing["minimum_model_tier"] == "small"
    assert routing["local_model_allowed"] is True
    assert routing["cloud_allowed"] is False
    assert routing["decomposition_required"] is False
    assert routing["allowed_files"] == ["tests/test_queue_parser.py"]
    assert routing["tests_to_run"] == [
        "/home/openclaw/.venv/bin/python -m pytest tests/test_queue_parser.py -q"
    ]


def test_oversized_task_routes_to_holding_with_decomposition():
    payload = _small_payload(
        goal="Rework the full Polish Loop dispatch stack.",
        scope=[f"Implement subsystem step {index}" for index in range(7)],
        success_criteria=[f"Acceptance check {index}" for index in range(2)],
        allowed_files=[f"polish_loop/module_{index}.py" for index in range(8)],
        tests_to_run=[f"test command {index}" for index in range(8)],
    )

    routing = classify_task_routing(payload)

    assert routing["size_class"] == "large"
    assert routing["readiness"] == "holding"
    assert routing["holding_reason"] == "large_requires_decomposition"
    assert routing["decomposition_required"] is True
    assert routing["target_runner_tier"] == "architect"
    assert routing["minimum_model_tier"] == "large"
    assert routing["local_model_allowed"] is False


def test_ambiguous_unknown_size_or_risk_routes_to_holding():
    routing = classify_task_routing({"goal": "Fix the thing when you get there."})

    assert routing["size_class"] == "unknown"
    assert routing["readiness"] == "holding"
    assert "unknown" in routing["risk_flags"]
    assert "needs_human_classification" in routing["holding_reason"]
    assert routing["local_model_allowed"] is False
    assert routing["token_budget"] == 0


def test_sensitive_legal_financial_external_credential_and_production_tasks_never_ready():
    risky_payloads = [
        ("sensitive", "Read raw text-message evidence from the private vault."),
        ("legal", "Ingest legal sealed evidence for attorney review."),
        ("financial", "Mutate banking and invoice records."),
        ("external_action", "Send Telegram delivery for a live action."),
        ("credential", "Open .chief.env and rotate an API key token."),
        ("production_mutation", "Restart systemd and update a production database."),
    ]

    for expected_flag, goal in risky_payloads:
        routing = classify_task_routing(_small_payload(goal=goal))
        assert expected_flag in routing["risk_flags"]
        assert routing["readiness"] == "blocked"
        assert routing["local_model_allowed"] is False
        assert routing["decomposition_required"] is False


def test_large_or_architect_tasks_never_allow_small_local_model():
    large = classify_task_routing(
        _small_payload(
            allowed_files=[f"polish_loop/file_{index}.py" for index in range(7)],
            tests_to_run=[f"pytest test_{index}.py" for index in range(7)],
        )
    )
    architect = classify_task_routing(
        _small_payload(
            allowed_files=[f"polish_loop/file_{index}.py" for index in range(12)],
            tests_to_run=[f"pytest test_{index}.py" for index in range(12)],
            scope=[f"Step {index}" for index in range(16)],
        )
    )

    assert large["size_class"] == "large"
    assert large["minimum_model_tier"] == "large"
    assert large["local_model_allowed"] is False
    assert architect["size_class"] == "architect"
    assert architect["minimum_model_tier"] == "architect"
    assert architect["local_model_allowed"] is False


def test_classifier_output_is_deterministic_for_identical_input():
    payload = _small_payload(
        scope=["touch routing module", "add tests", "run focused pytest"],
        allowed_files=["polish_loop/task_routing.py", "tests/test_polish_loop_size_routing.py"],
    )

    assert classify_task_routing(payload) == classify_task_routing(payload)
