from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import operator_extension_simulator as simulator


def test_status_orientation_phrases_do_not_require_covenant_or_authority():
    for phrase in (
        "where are we",
        "are we good",
        "what changed",
        "what needs my attention",
    ):
        sim = simulator.simulate_operator_extension_request(phrase)

        assert sim.execution_authority is False
        assert sim.covenant_required is False
        assert sim.restricted_block is False
        assert sim.request_category == "read_only_status"
        assert "No Covenant needed" in sim.operator_facing_summary


def test_tired_operator_relief_produces_concise_practical_framing():
    sim = simulator.simulate_operator_extension_request("I’m tired, tell me what matters")

    assert sim.inferred_intent == "tired_tell_me_what_matters"
    assert sim.request_category == "read_only_status"
    assert "Protect attention" in sim.recommended_response_frame
    assert "only what matters" in sim.operator_facing_summary
    assert len(sim.operator_facing_summary) < 100


def test_codex_coder_and_gemini_second_opinion_route_differently():
    codex = simulator.simulate_operator_extension_request("give this to the coder")
    gemini = simulator.simulate_operator_extension_request("get a second opinion")

    assert codex.inferred_intent == "codex_prompt_request"
    assert codex.tool_route == "codex_bounded_repo_prompt"
    assert "artifact preparation" in codex.operator_facing_summary
    assert gemini.inferred_intent == "gemini_review_request"
    assert gemini.tool_route == "gemini_architecture_scope_review"
    assert "review thinking" in gemini.operator_facing_summary
    assert codex.tool_route != gemini.tool_route


def test_commit_review_and_handoff_phrases_remain_review_or_draft_class():
    commit_review = simulator.simulate_operator_extension_request(
        "is this ready to commit"
    )
    handoff = simulator.simulate_operator_extension_request("prepare the next chat")

    assert commit_review.request_category == "review"
    assert commit_review.covenant_required is False
    assert "No commit authority is implied" in commit_review.operator_facing_summary
    assert handoff.request_category == "prompt_generation"
    assert handoff.covenant_required is False
    assert "handoff preparation" in handoff.operator_facing_summary


def test_send_that_to_codex_is_artifact_preparation_not_external_send():
    sim = simulator.simulate_operator_extension_request("send that to Codex")

    assert sim.inferred_intent == "codex_prompt_request"
    assert sim.request_category == "prompt_generation"
    assert sim.restricted_block is False
    assert sim.covenant_required is False
    assert "not an external send" in sim.operator_facing_summary


def test_agent_proposals_are_handled_without_becoming_authority():
    commit = simulator.simulate_operator_extension_request("I recommend committing this")
    handoff = simulator.simulate_operator_extension_request("I can update the handoff")

    assert commit.input_source_guess == "agent_proposal"
    assert commit.execution_authority is False
    assert commit.covenant_required is True
    assert commit.covenant_allowed_in_v0 is True
    assert commit.suggested_covenant is not None
    assert commit.suggested_covenant.authority_level == "bounded_repo_mutation"
    assert handoff.input_source_guess == "agent_proposal"
    assert handoff.suggested_covenant is not None
    assert handoff.suggested_covenant.authority_level == "bounded_repo_mutation"


def test_approval_sensitive_phrases_cannot_approve_without_pending_covenant():
    for phrase in ("go ahead", "do it", "handle it", "ship it"):
        sim = simulator.simulate_operator_extension_request(phrase)

        assert sim.execution_authority is False
        assert sim.covenant_required is True
        assert sim.covenant_allowed_in_v0 is False
        assert sim.suggested_covenant is None
        assert sim.yes_no_reframe
        assert sim.covenant_decision_reasons == ("no_pending_covenant",)


def test_do_the_next_thing_recommends_safe_framing_without_authority():
    sim = simulator.simulate_operator_extension_request("do the next thing")

    assert sim.inferred_intent == "next_safe_action"
    assert sim.execution_authority is False
    assert sim.covenant_required is True
    assert "not executable by itself" in sim.operator_facing_summary
    assert "next safe action" in sim.yes_no_reframe


def test_can_we_move_forward_routes_to_readiness_next_safe_action():
    sim = simulator.simulate_operator_extension_request("can we move forward")

    assert sim.inferred_intent == "activation_readiness_question"
    assert sim.execution_authority is False
    assert sim.covenant_required is False
    assert sim.follow_up_required is True
    assert "readiness" in sim.operator_facing_summary.lower()
    assert "Covenant" in sim.yes_no_reframe


def test_restricted_phrases_are_blocked_and_not_given_approvable_covenants():
    for phrase in (
        "launch it",
        "activate it",
        "start the runtime",
        "write to MCP memory",
        "call the provider",
        "use the API",
        "send the invoice",
        "reconcile billing",
        "touch legal files",
        "read private root",
        "send the email",
        "delete the files",
        "create Packet 08",
    ):
        sim = simulator.simulate_operator_extension_request(phrase)

        assert sim.execution_authority is False
        assert sim.restricted_block is True
        assert sim.covenant_required is True
        assert sim.covenant_allowed_in_v0 is False
        assert sim.suggested_covenant is None
        assert sim.restricted_domains
        assert "Blocked in v0" in sim.operator_facing_summary


def test_safe_illustrative_covenant_is_suggested_only_for_allowed_categories():
    allowed = simulator.simulate_operator_extension_request("I can update the handoff")
    restricted = simulator.simulate_operator_extension_request("write to MCP memory")

    assert allowed.suggested_covenant is not None
    assert allowed.suggested_covenant.authority_level == "bounded_repo_mutation"
    assert allowed.suggested_covenant.restricted_domains == ()
    assert restricted.suggested_covenant is None
    assert restricted.covenant_allowed_in_v0 is False


def test_renderer_includes_intent_authority_covenant_reframe_and_summary():
    sim = simulator.simulate_operator_extension_request("go ahead")
    rendered = simulator.render_operator_extension_simulation(sim)

    assert "OPERATOR EXTENSION SIMULATION" in rendered
    assert "Intent: approval_required_action" in rendered
    assert "Authority: execution_authority=False" in rendered
    assert "Covenant: required=True" in rendered
    assert "Reframe:" in rendered
    assert "Summary:" in rendered


def test_batch_simulation_preserves_order():
    sims = simulator.simulate_operator_extension_requests(
        ["where are we", "launch it", "ask Gemini"]
    )

    assert [sim.original_text for sim in sims] == [
        "where are we",
        "launch it",
        "ask Gemini",
    ]
    assert [sim.inferred_intent for sim in sims] == [
        "status_brief",
        "approval_required_action",
        "gemini_review_request",
    ]


def test_module_imports_only_safe_local_shared_modules_and_stdlib():
    source = inspect.getsource(simulator)
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
        "datetime",
        "operator_action_covenant",
        "operator_intent_core",
        "typing",
    }
    assert called_names.isdisjoint(
        {
            "connect",
            "open",
            "read_text",
            "write_text",
            "run",
            "check_call",
            "check_output",
            "popen",
            "system",
            "urlopen",
        }
    )
