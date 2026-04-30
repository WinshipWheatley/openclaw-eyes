import ast
import builtins
import inspect
import sys

import pytest

import expert_escalation_packet as packet_module
from expert_escalation_packet import (
    REQUIRED_SENSITIVITY_ATTESTATIONS,
    build_expert_escalation_packet,
    check_expert_escalation_packet,
    render_expert_prompt,
)


def _attestation() -> dict[str, bool]:
    return {key: True for key in REQUIRED_SENSITIVITY_ATTESTATIONS}


def _valid_packet(**overrides):
    packet = build_expert_escalation_packet(
        packet_id="expert-20260430-synthetic-review",
        created_at="2026-04-30T12:00:00Z",
        operator_request_summary="Review a synthetic public parser helper.",
        task_type="code_review",
        data_classification="synthetic_public",
        cloud_allowed=True,
        sensitivity_attestation=_attestation(),
        allowed_paths=("expert_escalation_packet.py", "tests/test_expert_escalation_packet.py"),
        forbidden_paths=("private-vaults", "secret-env-files", "gmail-bodies"),
        prompt="Review this synthetic public parser helper and return risks plus focused test ideas.",
        expected_outputs=("risk_summary", "test_suggestions"),
    )
    for key, value in overrides.items():
        if key == "execution_policy":
            merged = dict(packet["execution_policy"])
            merged.update(value)
            packet[key] = merged
        elif key == "sensitivity_attestation":
            merged = dict(packet["sensitivity_attestation"])
            merged.update(value)
            packet[key] = merged
        else:
            packet[key] = value
    return packet


def test_valid_synthetic_public_expert_packet_passes():
    result = check_expert_escalation_packet(_valid_packet())

    assert result.passed is True
    assert result.violations == []
    assert result.recommended_action == "pass"


def test_valid_packet_does_not_require_specific_model_or_tool_name():
    packet = _valid_packet()

    result = check_expert_escalation_packet(packet)

    assert result.passed is True
    assert packet["execution_policy"]["runner_class"] == "external_expert"
    assert packet["execution_policy"]["preferred_lane"] == "code_review"
    assert "runner" not in packet["execution_policy"]
    assert "candidate_runner" not in packet["execution_policy"]
    assert "codex" not in repr(packet).lower()


def test_optional_candidate_runner_can_be_codex_without_schema_being_codex_specific():
    packet = _valid_packet(execution_policy={"candidate_runner": "codex"})

    result = check_expert_escalation_packet(packet)

    assert result.passed is True
    assert packet["execution_policy"]["runner_class"] == "external_expert"
    assert packet["execution_policy"]["candidate_runner"] == "codex"
    assert packet["execution_policy"] != {"runner": "codex"}


def test_missing_explicit_cloud_allowance_fails():
    packet = _valid_packet(cloud_allowed=False)

    result = check_expert_escalation_packet(packet)

    assert result.passed is False
    assert result.recommended_action == "reject"
    assert "missing_explicit_cloud_allowed" in result.violations


def test_unknown_data_classification_fails():
    packet = _valid_packet(data_classification="internal_sensitive")

    result = check_expert_escalation_packet(packet)

    assert result.passed is False
    assert "unknown_data_classification:internal_sensitive" in result.violations


def test_unknown_task_type_fails():
    packet = _valid_packet(task_type="model_name_selection")

    result = check_expert_escalation_packet(packet)

    assert result.passed is False
    assert "unknown_task_type:model_name_selection" in result.violations


@pytest.mark.parametrize(
    "marker",
    [
        ".env",
        "api key",
        "OAuth token material",
        "private vault",
        "PII vault",
        "private logs",
        "$100",
    ],
)
def test_protected_markers_fail(marker):
    packet = _valid_packet(prompt=f"Review synthetic code only. Do not include {marker}.")

    result = check_expert_escalation_packet(packet)

    assert result.passed is False
    assert result.recommended_action == "reject"
    assert any(
        violation.startswith("protected_marker:") or violation == "protected_pattern:money_amount"
        for violation in result.violations
    )


@pytest.mark.parametrize(
    "marker",
    [
        "Legal matter data",
        "CPA tax packet",
        "Music Law contract",
        "Publishing catalog royalties",
        "Gmail private correspondence",
        "client matter",
    ],
)
def test_professional_and_private_markers_fail(marker):
    packet = _valid_packet(operator_request_summary=f"Review {marker}.")

    result = check_expert_escalation_packet(packet)

    assert result.passed is False
    assert any(violation.startswith("protected_marker:") for violation in result.violations)


def test_absolute_private_paths_and_path_traversal_fail():
    packet = _valid_packet(
        prompt="Review synthetic code near /mnt/c/OpenClawLegalPrivate/demo.",
        allowed_paths=["../secret.txt"],
    )

    result = check_expert_escalation_packet(packet)

    assert result.passed is False
    assert "path_traversal:allowed_paths" in result.violations
    assert "path_traversal:packet_body" in result.violations
    assert "absolute_private_path" in result.violations


def test_hermes_may_execute_true_fails():
    packet = _valid_packet(execution_policy={"hermes_may_execute": True})

    result = check_expert_escalation_packet(packet)

    assert result.passed is False
    assert "hermes_may_execute_not_false" in result.violations


@pytest.mark.parametrize(
    ("prompt", "expected_violation"),
    [
        ("Hermes should run Codex now with codex exec and then report back.", "model_runner_launch_instruction"),
        ("Hermes should run any external runner now.", "model_runner_launch_instruction"),
        ("Hermes should launch external runner now.", "model_runner_launch_instruction"),
        ("Use the terminal to start a cloud model runner.", "model_runner_launch_instruction"),
    ],
)
def test_packet_asking_hermes_to_run_model_or_external_runner_fails(prompt, expected_violation):
    packet = _valid_packet(prompt=prompt)

    result = check_expert_escalation_packet(packet)

    assert result.passed is False
    assert expected_violation in result.violations


def test_telegram_send_and_chat_secret_data_fails():
    packet = _valid_packet(
        prompt="After review, send the result to Telegram.",
        return_route={"chat_id": "123456789", "bot_token": "123456789:ABCDEFGHIJKLMNOPQRSTUVWX"},
    )

    result = check_expert_escalation_packet(packet)

    assert result.passed is False
    assert "telegram_send_instruction" in result.violations
    assert "raw_telegram_field:chat_id" in result.violations
    assert "raw_telegram_chat_id" in result.violations
    assert "raw_telegram_field:bot_token" in result.violations
    assert "telegram_bot_token" in result.violations


def test_render_expert_prompt_emits_sanitized_prompt_text_only():
    packet = _valid_packet()

    rendered = render_expert_prompt(packet)

    assert rendered == packet["prompt"]
    assert packet["packet_id"] not in rendered
    assert packet["operator_request_summary"] not in rendered
    assert packet["execution_policy"]["runner_class"] not in rendered


def test_render_expert_prompt_refuses_invalid_packet():
    packet = _valid_packet(prompt="Use /mnt/c/OpenClawLegalPrivate/demo as input.")

    with pytest.raises(ValueError, match="unsafe expert escalation packet"):
        render_expert_prompt(packet)


def test_checker_does_not_import_or_call_external_surfaces(monkeypatch):
    source = inspect.getsource(packet_module)
    tree = ast.parse(source)
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])

    assert imported_modules <= {"__future__", "dataclasses", "datetime", "re", "typing"}

    forbidden_modules = {
        "chief_notify",
        "chief_sender",
        "cloud",
        "codex",
        "gateway",
        "hermes_cli",
        "openai",
        "requests",
        "runner_profiles",
        "runner_registry",
        "run_agent",
        "service",
        "subprocess",
        "telegram",
        "urllib",
    }
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        assert name.split(".")[0] not in forbidden_modules
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    packet = _valid_packet()

    assert check_expert_escalation_packet(packet).passed is True
    assert render_expert_prompt(packet) == packet["prompt"]
    assert "expert_escalation_packet" in sys.modules