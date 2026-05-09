from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import operator_intent_core as core


def test_required_phrase_to_intent_coverage():
    rows = core.classify_phrase_matrix()

    assert all(row["passed"] for row in rows)
    assert {row["actual_intent"] for row in rows} >= {
        "status_brief",
        "next_safe_action",
        "tired_tell_me_what_matters",
        "codex_prompt_request",
        "gemini_review_request",
        "commit_review_request",
        "push_confirmation_context",
        "handoff_request",
        "activation_readiness_question",
        "approval_required_action",
        "stop_or_wait_instruction",
    }


def test_bounded_worker_prompt_language_maps_to_non_authorizing_handoff_request():
    phrase = "Review the next safe Operator Harness slice and produce the bounded worker prompt"

    intent = core.classify_operator_intent(phrase)
    frame = core.frame_operator_intent(intent)

    assert intent.name == "handoff_request"
    assert intent.request_category == "prompt_generation"
    assert intent.execution_authority is False
    assert frame.intent_name == "handoff_request"
    assert frame.request_category == "prompt_generation"
    assert frame.execution_authority is False
    assert frame.tool_route == "operator_handoff_draft"
    assert frame.current_authority == "classification_and_response_framing_only"


def test_dangerous_phrases_do_not_become_execution_authority():
    for phrase in ("do the next thing", "go ahead", "launch it", "activate it"):
        intent = core.classify_operator_intent(phrase)
        frame = core.frame_operator_intent(intent)

        assert intent.execution_authority is False
        assert frame.execution_authority is False
        assert "live runtime launch" in frame.forbidden_actions

    assert core.frame_operator_intent(
        core.classify_operator_intent("do the next thing")
    ).follow_up_required is True
    assert core.classify_operator_intent("launch it").name == "approval_required_action"


def test_tired_operator_relief_maps_to_short_practical_frame():
    intent = core.classify_operator_intent("I'm tired, tell me what matters")
    frame = core.frame_operator_intent(intent)

    assert intent.name == "tired_tell_me_what_matters"
    assert frame.request_category == "read_only_status"
    assert "Protect attention" in frame.recommended_response_frame
    assert "state, the risk, the next safe move" in frame.recommended_response_frame
    assert frame.execution_authority is False


def test_codex_and_gemini_route_differently():
    codex = core.frame_operator_intent(
        core.classify_operator_intent("send that to Codex")
    )
    gemini = core.frame_operator_intent(core.classify_operator_intent("ask Gemini"))

    assert codex.intent_name == "codex_prompt_request"
    assert codex.tool_route == "codex_bounded_repo_prompt"
    assert "bounded repo work" in codex.recommended_response_frame
    assert gemini.intent_name == "gemini_review_request"
    assert gemini.tool_route == "gemini_architecture_scope_review"
    assert "architecture" in gemini.recommended_response_frame
    assert codex.tool_route != gemini.tool_route


def test_activation_phrases_do_not_authorize_launch():
    for phrase in ("can we move forward", "launch it", "activate it"):
        frame = core.frame_operator_intent(core.classify_operator_intent(phrase))

        assert frame.execution_authority is False
        assert "live runtime launch" in frame.forbidden_actions
        assert any("activation" in surface for surface in frame.evidence_surfaces)


def test_stop_and_wait_classify_as_stop():
    for phrase in ("stop", "wait"):
        intent = core.classify_operator_intent(phrase)
        frame = core.frame_operator_intent(intent)

        assert intent.name == "stop_or_wait_instruction"
        assert frame.request_category == "stop"
        assert frame.execution_authority is False


def test_frames_include_forbidden_actions_evidence_and_follow_up_posture():
    for phrase, _expected in core.sample_phrase_matrix():
        frame = core.classify_and_frame_operator_intent(phrase)

        assert frame.forbidden_actions
        assert frame.evidence_surfaces
        assert isinstance(frame.follow_up_required, bool)
        assert frame.current_authority == "classification_and_response_framing_only"


def test_module_is_surface_neutral_and_importable_without_runtime_dependencies():
    source = inspect.getsource(core)
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

    assert imported_modules <= {"__future__", "dataclasses", "re", "typing"}
    assert "cassandra" not in source.lower()
    assert "telegram" not in source.lower()
    assert "chief_" not in source.lower()
    assert called_names.isdisjoint(
        {
            "connect",
            "open",
            "read_text",
            "run",
            "check_call",
            "check_output",
            "popen",
            "system",
            "urlopen",
        }
    )
