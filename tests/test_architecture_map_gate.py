import pytest
from architecture_map_gate import evaluate_architecture_request, architecture_map_gate_status, ArchitectureGateResult

def test_rebuild_compiled_knowledge_substrate():
    request = "Rebuild the compiled knowledge substrate"
    result = evaluate_architecture_request(request)
    assert result.gate_decision == "already_built_review_required"
    assert result.already_built_risk is True
    assert result.execution_authority_granted is False
    assert result.active_plugin_claimed is False

def test_ready_for_bounded_architecture_slice():
    request = "Design the next small architecture slice for Map Room query"
    result = evaluate_architecture_request(request)
    assert result.gate_decision == "ready_for_bounded_architecture_slice"
    assert result.ready_for_bounded_slice is True
    assert result.execution_authority_granted is False

def test_prior_art_check_required():
    request = "Build a new dashboard from scratch"
    result = evaluate_architecture_request(request)
    assert result.gate_decision == "prior_art_check_required"
    assert result.needs_prior_art_check is True
    assert "prior-art check" in result.decision_reason.lower()

def test_blocked_sensitive_boundary():
    request = "Move files in OpenClawLegalPrivate"
    result = evaluate_architecture_request(request)
    assert result.gate_decision == "blocked_sensitive_boundary"
    assert result.blocked is True
    assert result.sensitive_boundary_risk is True

def test_too_broad_manual_review():
    request = "Plan architecture, cleanup files, and commit it"
    result = evaluate_architecture_request(request)
    assert result.gate_decision == "too_broad_manual_review"
    assert result.too_broad is True
    assert "multiple plugin domains" in result.decision_reason.lower()

def test_where_is_mac_eyes_too_broad():
    # "Where is" (map room query) + "can I move it" (cleanup)
    request = "Where is mac_eyes and can I move it?"
    result = evaluate_architecture_request(request)
    assert result.gate_decision in {
        "too_broad_manual_review",
        "blocked_sensitive_boundary",
        "unknown_manual_review",
    }
    assert result.cleanup_allowed is False if hasattr(result, "cleanup_allowed") else result.execution_authority_granted is False

def test_unknown_manual_review():
    request = "Some totally unrelated thing"
    result = evaluate_architecture_request(request)
    assert result.gate_decision == "unknown_manual_review"
    assert "unknown task type" in result.decision_reason.lower()

def test_architecture_map_gate_status():
    status = architecture_map_gate_status()
    assert status["status"] == "implemented_substrate"
    assert status["read_only"] is True
    assert status["no_active_plugin"] is True
    assert status["no_runtime"] is True
    assert status["no_provider"] is True

def test_implemented_substrate_not_active_plugin():
    status = architecture_map_gate_status()
    # Prove implemented substrate != active plugin
    assert status["status"] == "implemented_substrate"
    assert status["no_active_plugin"] is True

    # Prove no execution authority
    assert "grants no execution authority" in status["authority_note"]

    # Result from evaluation also confirms
    result = evaluate_architecture_request("Design architecture slice")
    assert result.active_plugin_claimed is False
    assert result.execution_authority_granted is False

def test_no_forbidden_imports():
    import ast
    from pathlib import Path

    tree = ast.parse(Path("architecture_map_gate.py").read_text())
    imported_modules = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])

    forbidden = {"requests", "sqlite3", "subprocess", "socket", "http", "urllib"}
    assert imported_modules.isdisjoint(forbidden)

def test_result_structure():
    request = "Design architecture slice"
    result = evaluate_architecture_request(request)
    assert isinstance(result, ArchitectureGateResult)
    assert result.request_text == request
    assert isinstance(result.required_maps_checked, list)
    assert isinstance(result.forbidden_actions, list)

def test_reality_harness_v0():
    # 1. “Rebuild the whole Map Room and plugin system from scratch”
    # Expected: already_built_review_required or too_broad_manual_review, not ready.
    request = "Rebuild the whole Map Room and plugin system from scratch"
    result = evaluate_architecture_request(request)
    assert result.gate_decision in ("already_built_review_required", "too_broad_manual_review")
    assert result.ready_for_bounded_slice is False

    # 2. “Create a small receipt/docs integration for Architecture & Map Gate”
    # Expected: ready_for_bounded_architecture_slice or architecture_map_gate/manual review; not prior-art, not sensitive.
    request = "Create a small receipt/docs integration for Architecture & Map Gate"
    result = evaluate_architecture_request(request)
    assert result.needs_prior_art_check is False
    assert result.blocked is False
    assert result.ready_for_bounded_slice is True or "manual_review" in result.gate_decision

    # 3. “Build a new internal dashboard app for OpenClaw”
    # Expected: prior_art_check_required.
    request = "Build a new internal dashboard app for OpenClaw"
    result = evaluate_architecture_request(request)
    assert result.gate_decision == "prior_art_check_required"
    assert result.needs_prior_art_check is True

    # 4. “Clean up mac_eyes and OpenClaw_Watch folders”
    # Expected: blocked or too_broad/manual review; never ready.
    request = "Clean up mac_eyes and OpenClaw_Watch folders"
    result = evaluate_architecture_request(request)
    # mac_eyes is sensitive, so it should be blocked
    assert result.blocked is True or "manual_review" in result.gate_decision
    assert result.ready_for_bounded_slice is False

    # 5. “Find where Right now.md is generated and whether it is safe to move”
    # Expected: map/file territory manual review or blocked; never ready.
    request = "Find where Right now.md is generated and whether it is safe to move"
    result = evaluate_architecture_request(request)
    assert result.ready_for_bounded_slice is False
    assert "too_broad" in result.gate_decision or "manual_review" in result.gate_decision or result.blocked is True

    # 6. “Design a local specialist model router domain”
    # Expected: ready_for_bounded_architecture_slice or architecture_map_gate; not active plugin, no execution authority.
    request = "Design a local specialist model router domain"
    result = evaluate_architecture_request(request)
    assert result.gate_decision == "ready_for_bounded_architecture_slice"
    assert result.execution_authority_granted is False
    assert result.active_plugin_claimed is False

    # 7. “Commit all current work and push”
    # Expected: receipt/completion/manual review, not architecture ready.
    request = "Commit all current work and push"
    result = evaluate_architecture_request(request)
    assert result.ready_for_bounded_slice is False
    assert result.matched_plugin_domain_id != "architecture_map_gate" or "manual_review" in result.gate_decision

def test_pass2_false_green_light_hardening():
    # “Rebuild OpenClaw from scratch”
    request = "Rebuild OpenClaw from scratch"
    result = evaluate_architecture_request(request)
    assert result.ready_for_bounded_slice is False
    assert result.gate_decision in ("already_built_review_required", "prior_art_check_required", "too_broad_manual_review")

    # “Clean up all folders and commit the changes”
    request = "Clean up all folders and commit the changes"
    result = evaluate_architecture_request(request)
    assert result.ready_for_bounded_slice is False
    assert result.gate_decision in ("too_broad_manual_review", "blocked_sensitive_boundary", "unknown_manual_review")

    # “Build a dashboard and wire it to Cassandra”
    request = "Build a dashboard and wire it to Cassandra"
    result = evaluate_architecture_request(request)
    assert result.ready_for_bounded_slice is False
    assert result.gate_decision in ("prior_art_check_required", "too_broad_manual_review")

    # “Move Right now.md into a cleaner folder”
    request = "Move Right now.md into a cleaner folder"
    result = evaluate_architecture_request(request)
    assert result.ready_for_bounded_slice is False
    # This task is about moving/cleanup, not architecture design
    assert result.gate_decision in ("too_broad_manual_review", "unknown_manual_review")

    # “Give Cassandra access to OpenClawLegalPrivate”
    request = "Give Cassandra access to OpenClawLegalPrivate"
    result = evaluate_architecture_request(request)
    assert result.ready_for_bounded_slice is False
    assert result.gate_decision == "blocked_sensitive_boundary"
    assert result.blocked is True

    # “Install an existing dashboard tool and connect it”
    request = "Install an existing dashboard tool and connect it"
    result = evaluate_architecture_request(request)
    assert result.ready_for_bounded_slice is False
    # "Install" is not "Design/Plan"
    assert result.gate_decision in ("prior_art_check_required", "too_broad_manual_review", "unknown_manual_review")

    # “Create plugins, hooks, MCP, and scripts for everything”
    request = "Create plugins, hooks, MCP, and scripts for everything"
    result = evaluate_architecture_request(request)
    assert result.ready_for_bounded_slice is False
    assert result.gate_decision == "too_broad_manual_review"

def test_pass3_operator_usefulness():
    # “Design the next small architecture slice for local specialist model router”
    request = "Design the next small architecture slice for local specialist model router"
    result = evaluate_architecture_request(request)
    assert result.ready_for_bounded_slice is True
    assert "planning" in result.next_safe_step.lower()
    assert "no implementation or execution authority" in result.next_safe_step.lower()

    # “Plan a read-only receipt integration for the architecture gate”
    # This is multi-domain (architecture + receipt), so it stays manual review per rules.
    request = "Plan a read-only receipt integration for the architecture gate"
    result = evaluate_architecture_request(request)
    assert result.ready_for_bounded_slice is False
    assert result.gate_decision == "too_broad_manual_review"

    # “Create a bounded test-only hardening pass for map room query”
    # This is multi-domain (test/receipt + map room query), so it stays manual review.
    request = "Create a bounded test-only hardening pass for map room query"
    result = evaluate_architecture_request(request)
    assert result.ready_for_bounded_slice is False
    assert result.gate_decision == "too_broad_manual_review"
