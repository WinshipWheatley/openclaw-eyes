from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import operator_evidence_bridge as bridge


def test_every_required_domain_maps_to_expected_bridge_domain():
    expected = dict(bridge.bridge_phrase_matrix())

    for phrase, expected_domain in expected.items():
        result = bridge.bridge_operator_request(phrase)

        assert result.bridge_domain == expected_domain, phrase
        assert result.original_text == phrase
        assert result.approved_evidence_surfaces
        assert result.evidence_selection_mode == "names_only"
        assert result.execution_authority_granted is False


def test_evidence_surfaces_are_selected_by_name_only():
    result = bridge.bridge_operator_request("where are we")

    assert "repo-check" in result.approved_evidence_surfaces
    assert "packet-status" in result.approved_evidence_surfaces
    assert all(not surface.startswith("./scripts/") for surface in result.approved_evidence_surfaces)
    assert result.receipts_executed is False
    assert result.shell_commands_executed is False


def test_status_orientation_has_no_covenant_requirement():
    result = bridge.bridge_operator_request("where are we")

    assert result.bridge_domain == "status_orientation"
    assert result.covenant_posture == "not_required_read_only_status"
    assert result.restricted_block is False
    assert result.follow_up_required is False
    assert "No Covenant needed" in result.operator_facing_summary


def test_operator_relief_summary_is_short_and_practical():
    result = bridge.bridge_operator_request("I'm tired, tell me what matters")

    assert result.bridge_domain == "operator_relief"
    assert "state, risk, next safe move" in result.response_frame
    assert "Cut the noise" in result.operator_facing_summary
    assert len(result.operator_facing_summary) < 130


def test_codex_and_gemini_route_differently():
    codex = bridge.bridge_operator_request("send that to Codex")
    gemini = bridge.bridge_operator_request("ask Gemini")

    assert codex.bridge_domain == "codex_coder_routing"
    assert gemini.bridge_domain == "gemini_planning_architecture_routing"
    assert "Codex" in codex.response_frame
    assert "Gemini" in gemini.response_frame
    assert codex.approved_evidence_surfaces != gemini.approved_evidence_surfaces
    assert "bounded implementation" in codex.safe_substitute_or_next_move
    assert "architecture/risk review" in gemini.safe_substitute_or_next_move


def test_commit_and_push_are_authority_sensitive_and_do_not_push():
    commit_review = bridge.bridge_operator_request("review this for commit")
    push = bridge.bridge_operator_request("can I push")

    assert commit_review.bridge_domain == "commit_push_remote_mutation"
    assert commit_review.covenant_posture == "not_required_review_only"
    assert push.bridge_domain == "commit_push_remote_mutation"
    assert push.covenant_posture == "restricted_not_approvable_in_v0"
    assert push.restricted_block is True
    assert "no automatic push" in push.operator_facing_summary.lower()
    assert "external sends" in push.forbidden_boundaries


def test_handoff_and_packet_continuity_select_train_log_evidence():
    result = bridge.bridge_operator_request("don't let the next worker rediscover this")

    assert result.bridge_domain == "handoff_packet_continuity"
    assert "active_handoff" in result.approved_evidence_surfaces
    assert "Packet 07 README" in result.approved_evidence_surfaces
    assert result.covenant_posture == "draft_only_or_scoped_mutation_required"
    assert "handoff" in result.safe_substitute_or_next_move.lower()


def test_vague_approval_phrases_do_not_authorize():
    for phrase in ("go ahead", "do it", "ship it"):
        result = bridge.bridge_operator_request(phrase)

        assert result.bridge_domain == "approval_action_covenant_power_boundary"
        assert result.execution_authority_granted is False
        assert result.covenant_posture == "pending_covenant_required"
        assert result.yes_no_reframe
        assert "specific action" in result.yes_no_reframe


def test_do_next_thing_does_not_execute_and_reframes():
    result = bridge.bridge_operator_request("do the next thing")

    assert result.bridge_domain == "do_next_continue_keep_going"
    assert result.execution_authority_granted is False
    assert result.covenant_posture == "proposal_only_until_specific_action"
    assert result.follow_up_required is True
    assert "not execution authority" in result.operator_facing_summary


def test_runtime_mcp_provider_invoice_legal_private_external_delete_packet08_blocked():
    blocked = (
        ("launch it", "runtime_activation_launch"),
        ("start the runtime", "runtime_activation_launch"),
        ("write to MCP memory", "mcp_shared_memory_hidden_authority"),
        ("call the provider", "provider_model_api_calls"),
        ("send the invoice", "invoice_billing_money"),
        ("check receivables", "invoice_billing_money"),
        ("touch legal files", "legal_private_sensitive"),
        ("read private root", "legal_private_sensitive"),
        ("send the email", "external_sends_communications"),
        ("notify them", "external_sends_communications"),
        ("delete it", "destructive_filesystem_broad_traversal"),
        ("scan the whole drive", "destructive_filesystem_broad_traversal"),
        ("create Packet 08", "packet_renewal_next_packet"),
    )

    for phrase, expected_domain in blocked:
        result = bridge.bridge_operator_request(phrase)

        assert result.bridge_domain == expected_domain, phrase
        assert result.restricted_block is True
        assert result.covenant_posture == "restricted_not_approvable_in_v0"
        assert result.execution_authority_granted is False
        assert "Blocked" in result.operator_facing_summary


def test_taste_phrases_use_manifesto_evidence_without_weakening_gates():
    for phrase in ("make it sexy", "where is the taste", "this feels like corporate sludge"):
        result = bridge.bridge_operator_request(phrase)

        assert result.bridge_domain == "taste_product_feel_beauty"
        assert "OPERATOR_EXTENSION_MANIFESTO.md" in result.approved_evidence_surfaces
        assert result.restricted_block is False
        assert result.covenant_posture == "not_required_review_only"
        assert "without weakening gates" in result.operator_facing_summary


def test_packet_renewal_phrases_do_not_create_packet08():
    result = bridge.bridge_operator_request("should we make Packet 08")

    assert result.bridge_domain == "packet_renewal_next_packet"
    assert result.restricted_block is True
    assert "No Packet 08 creation" in result.response_frame
    assert "blueprint review" in result.safe_substitute_or_next_move


def test_stop_wait_preserves_state():
    for phrase in ("stop", "wait", "hold"):
        result = bridge.bridge_operator_request(phrase)

        assert result.bridge_domain == "stop_wait_hold"
        assert result.covenant_posture == "not_required_stop"
        assert result.follow_up_required is False
        assert "Preserve state" in result.response_frame


def test_unsafe_ambiguous_narrows_or_reframes():
    result = bridge.bridge_operator_request("just handle it")

    assert result.bridge_domain == "unsafe_ambiguous_handle_it"
    assert result.follow_up_required is True
    assert result.yes_no_reframe
    assert "smallest safe next move" in result.safe_substitute_or_next_move
    assert result.execution_authority_granted is False


def test_renderer_includes_domain_evidence_covenant_boundaries_and_next_move():
    result = bridge.bridge_operator_request("go ahead")
    rendered = bridge.render_operator_evidence_bridge_result(result)

    assert "OPERATOR EVIDENCE BRIDGE" in rendered
    assert "Domain: approval_action_covenant_power_boundary" in rendered
    assert "Evidence surfaces:" in rendered
    assert "Covenant: pending_covenant_required" in rendered
    assert "Forbidden boundaries:" in rendered
    assert "Next move:" in rendered
    assert "Summary:" in rendered


def test_batch_bridge_preserves_order():
    results = bridge.bridge_operator_requests(["where are we", "ask Gemini", "launch it"])

    assert [result.original_text for result in results] == [
        "where are we",
        "ask Gemini",
        "launch it",
    ]
    assert [result.bridge_domain for result in results] == [
        "status_orientation",
        "gemini_planning_architecture_routing",
        "runtime_activation_launch",
    ]


def test_module_imports_only_stdlib_and_safe_local_modules():
    source = inspect.getsource(bridge)
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
        "operator_action_covenant",
        "operator_extension_simulator",
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
