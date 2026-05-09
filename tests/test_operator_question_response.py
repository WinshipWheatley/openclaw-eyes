from __future__ import annotations

import ast
import inspect

import operator_question_response as response_path


def _evidence_packet() -> dict[str, object]:
    return {
        "topic": "operator question response path",
        "banner": "Mac Watch support material only. Not canonical repo authority.",
        "files": [
            {
                "source_path": "Docs/Planning/Operator Watch.md",
                "title": "Operator Watch",
                "tags": ["operator", "response"],
                "authority_guess": "support",
                "freshness_class": "recent",
                "needs_deeper_review": False,
                "content": "support material",
            }
        ],
    }


def _explicit_evidence() -> tuple[str, ...]:
    return (
        "Operator/04_ANTI_DRIFT_RULES.md",
        "Operator/07_AUTHORITY_AND_COVENANT_RULES.md",
        "./scripts/openclaw_receipts.py repo-check receipt",
    )


def test_what_should_we_do_next_maps_to_concise_non_authorizing_answer():
    response = response_path.respond_to_operator_question("What should we do next?")

    assert response.status == "answered_non_authorizing"
    assert response.response_mode == "direct_answer"
    assert response.classified_intent == "next_safe_action"
    assert response.bridge_domain == "status_orientation"
    assert response.request_category == "read_only_status"
    assert response.covenant_posture == "not_required_read_only_status"
    assert response.worker_handoff is None
    assert response.execution_authority_granted is False
    assert "read-only and non-authorizing" in response.human_response
    assert "Next safe move" in response.human_response
    assert "stop before mutation" in response.human_response


def test_overwhelmed_operator_gets_relief_frame_not_machine_contract_noise():
    response = response_path.respond_to_operator_question(
        "I’m overwhelmed. Tell me what matters."
    )

    assert response.status == "answered_non_authorizing"
    assert response.response_mode == "direct_answer"
    assert response.classified_intent == "tired_tell_me_what_matters"
    assert response.bridge_domain == "operator_relief"
    assert response.request_category == "read_only_status"
    assert response.covenant_posture == "not_required_read_only_status"
    assert "Cut the noise" in response.human_response
    assert "state, risk, next safe move, and hard gates" in response.human_response
    assert "This response grants no execution authority." in response.human_response


def test_next_safe_move_question_uses_direct_answer_path():
    response = response_path.respond_to_operator_question("What’s the next safe move?")

    assert response.status == "answered_non_authorizing"
    assert response.response_mode == "direct_answer"
    assert response.classified_intent == "next_safe_action"
    assert response.bridge_domain == "status_orientation"
    assert response.worker_handoff is None
    assert response.receipts_executed is False
    assert response.provider_or_model_called is False
    assert response.runtime_launched is False
    assert response.mcp_called is False


def test_codex_prompt_request_without_evidence_is_blocked_before_worker_handoff():
    response = response_path.respond_to_operator_question("send that to Codex")

    assert response.status == "needs_evidence_for_worker_handoff"
    assert response.response_mode == "needs_evidence"
    assert response.classified_intent == "codex_prompt_request"
    assert response.bridge_domain == "codex_coder_routing"
    assert response.worker_handoff is None
    assert "need grounding evidence first" in response.human_response
    assert response.execution_authority_granted is False


def test_codex_prompt_request_with_evidence_generates_bounded_worker_handoff():
    response = response_path.respond_to_operator_question(
        "send that to Codex",
        evidence_packet=_evidence_packet(),
        evidence_references=_explicit_evidence(),
    )

    assert response.status == "worker_handoff_ready"
    assert response.response_mode == "worker_handoff"
    assert response.classified_intent == "codex_prompt_request"
    assert response.bridge_domain == "codex_coder_routing"
    assert response.worker_handoff is not None
    assert response.worker_handoff.target_worker_profile == "codex_implementation"
    assert response.worker_handoff.status == "ready_non_authorizing"
    assert "The generated prompt grants no execution authority." in (
        response.worker_handoff.prompt_text
    )
    assert "bounded, non-authorizing worker handoff" in response.human_response


def test_explicit_worker_handoff_request_uses_requested_profile():
    response = response_path.respond_to_operator_question(
        "Review the current Operator Harness state and recommend the next smallest useful stabilization slice.",
        target_worker_profile="gemini_review",
        generate_worker_handoff=True,
        evidence_packet=_evidence_packet(),
        evidence_references=_explicit_evidence(),
    )

    assert response.status == "worker_handoff_ready"
    assert response.response_mode == "worker_handoff"
    assert response.classified_intent == "next_safe_action"
    assert response.bridge_domain == "status_orientation"
    assert response.worker_handoff is not None
    assert response.worker_handoff.target_worker_profile == "gemini_review"
    assert response.worker_handoff.status == "ready_non_authorizing"
    assert response.worker_handoff.no_execution_authority_statement == (
        "The generated prompt grants no execution authority."
    )


def test_restricted_runtime_request_remains_blocked_and_covenant_required():
    response = response_path.respond_to_operator_question(
        "launch it",
        evidence_packet=_evidence_packet(),
        evidence_references=_explicit_evidence(),
    )

    assert response.status == "blocked_covenant_required"
    assert response.response_mode == "blocked_boundary"
    assert response.bridge_domain == "runtime_activation_launch"
    assert response.worker_handoff is None
    assert response.execution_authority_granted is False
    assert "blocked/non-authorizing" in response.human_response
    assert "Operator Action Covenant is required" in response.human_response
    assert "live runtime launch" in response.forbidden_lanes


def test_stop_instruction_is_direct_and_non_authorizing():
    response = response_path.respond_to_operator_question("stop")

    assert response.status == "answered_non_authorizing"
    assert response.response_mode == "direct_answer"
    assert response.classified_intent == "stop_or_wait_instruction"
    assert response.bridge_domain == "stop_wait_hold"
    assert response.request_category == "stop"
    assert "Stopping optional forward motion" in response.human_response
    assert response.execution_authority_granted is False


def test_question_response_to_dict_is_plain_and_deterministic():
    response = response_path.respond_to_operator_question("What should we do next?")
    first = response_path.question_response_to_dict(response)
    second = response_path.question_response_to_dict(response)

    assert first == second
    assert first["status"] == "answered_non_authorizing"
    assert first["worker_handoff"] is None


def test_status_function_is_static_read_only_and_non_authorizing():
    report = response_path.operator_question_response_status()

    assert report["passed"] is True
    assert report["receipt_type"] == "openclaw.operator_question_response_status"
    assert report["execution_authority_granted"] is False
    assert report["receipts_executed"] is False
    assert report["provider_or_model_called"] is False
    assert report["runtime_launched"] is False
    assert report["process_state_inspected"] is False
    assert report["mcp_called"] is False
    assert report["hidden_memory_write_used"] is False
    assert report["persistence_used"] is False
    assert report["external_send_used"] is False
    assert report["checks"]["normal_language_direct_intents_present"] is True


def test_module_has_no_live_runtime_provider_mcp_persistence_or_filesystem_behavior():
    source = inspect.getsource(response_path)
    tree = ast.parse(source)
    imported_modules = set()
    called_names = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            called = node.func
            if isinstance(called, ast.Name):
                called_names.add(called.id)
            elif isinstance(called, ast.Attribute):
                called_names.add(called.attr)

    assert imported_modules <= {
        "__future__",
        "dataclasses",
        "operator_evidence_bridge",
        "operator_intent_core",
        "operator_prompt_handoff_generator",
        "typing",
    }
    assert called_names.isdisjoint(
        {
            "check_call",
            "check_output",
            "connect",
            "execute",
            "from_pretrained",
            "open",
            "open_url",
            "popen",
            "post",
            "read_text",
            "run",
            "system",
            "urlopen",
            "walk",
            "write",
        }
    )
    assert "sqlite3" not in source
    assert "chromadb" not in source
    assert "requests" not in source
    assert "subprocess" not in source
