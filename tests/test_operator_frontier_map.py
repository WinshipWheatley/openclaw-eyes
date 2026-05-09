from __future__ import annotations

import ast
import inspect

import operator_frontier_map as frontier


def test_frontier_map_reports_built_compiled_substrate_territory():
    status = frontier.operator_frontier_map_status()
    built = {item.item_id: item for item in status.built}

    assert status.passed is True
    assert status.receipt_type == "openclaw.operator_frontier_map_status"
    assert status.lane == "compiled_knowledge_substrate"
    assert set(built) == {
        "north_star_spec_exists",
        "fixture_contract_exists",
        "lifecycle_states_modeled",
        "answer_packet_exists",
        "truth_boundary_behaviors_exist",
        "static_status_function_exists",
    }
    assert built["north_star_spec_exists"].state == "built"
    assert "COMPILED_KNOWLEDGE_SUBSTRATE_NORTH_STAR.md" in built[
        "north_star_spec_exists"
    ].evidence[0]
    assert "compiled_knowledge_substrate.py" in built["fixture_contract_exists"].evidence
    assert "AnswerPacket" in built["answer_packet_exists"].evidence
    assert "compiled_knowledge_substrate_status" in built[
        "static_status_function_exists"
    ].evidence


def test_frontier_map_reports_partial_pending_territory():
    status = frontier.operator_frontier_map_status()
    partial = {item.item_id: item for item in status.partially_built}

    assert set(partial) == {
        "receipt_command_may_be_missing",
        "context_export_integration_pending",
        "operator_question_response_substrate_consumption_unproven",
    }
    assert partial["receipt_command_may_be_missing"].state == "partial"
    assert "operator-frontier-map-status" in partial[
        "receipt_command_may_be_missing"
    ].evidence[0]
    assert "backend_knowledge_packet.py" in partial[
        "context_export_integration_pending"
    ].evidence
    assert "operator_question_response.py" in partial[
        "operator_question_response_substrate_consumption_unproven"
    ].evidence


def test_frontier_map_reports_not_built_future_gated_territory():
    status = frontier.operator_frontier_map_status()
    not_built = {item.item_id: item for item in status.not_built}

    assert set(not_built) == {
        "sqlite_authority_spine",
        "ingestion",
        "embeddings_vector_retrieval",
        "pageindex_tree_retrieval",
        "graph_engine",
        "provider_model_calls",
        "mcp_integration",
        "runtime_cassandra_chief_telegram_live_wiring",
        "private_root_legal_invoice_finance_traversal",
    }
    assert all(item.state == "not_built" for item in not_built.values())
    assert status.sqlite_used is False
    assert status.ingestion_used is False
    assert status.embeddings_used is False
    assert status.vector_retrieval_used is False
    assert status.pageindex_or_tree_retrieval_used is False
    assert status.graph_engine_used is False
    assert status.provider_or_model_called is False
    assert status.mcp_called is False
    assert status.private_root_access_used is False
    assert status.runtime_or_process_inspection_used is False
    assert status.cassandra_chief_telegram_wired is False


def test_duplicate_work_detection_blocks_rebuilding_fixture_contract():
    finding = frontier.evaluate_frontier_task("Build the compiled knowledge substrate.")

    assert finding.duplicate_risk is True
    assert finding.finding_code == "duplicate_fixture_contract_exists"
    assert "compiled_knowledge_substrate.py fixture-only contract" in finding.already_built
    assert "Do not rebuild the fixture contract" in finding.recommendation
    assert "choose one narrow pending edge" in finding.prerequisite_to_finish_first


def test_status_embeds_duplicate_work_detection_for_proposed_task():
    status = frontier.operator_frontier_map_status(
        "Please build the compiled knowledge substrate from scratch."
    )

    assert status.duplicate_work_finding.duplicate_risk is True
    assert status.duplicate_work_finding.finding_code == (
        "duplicate_fixture_contract_exists"
    )
    assert status.execution_authority_granted is False


def test_bridge_duplicate_work_detection_warns_about_existing_context_export_bridge():
    finding = frontier.evaluate_frontier_task("Build a bridge for substrate context export.")

    assert finding.duplicate_risk is True
    assert finding.finding_code == "possible_bridge_overlap_review_required"
    assert "backend_knowledge_packet.py" in finding.already_built
    assert "AgentContextExportPacket" in finding.already_built
    assert "reviewing existing backend_knowledge_packet.py" in finding.recommendation
    assert "assemble_agent_context_export" in finding.prerequisite_to_finish_first


def test_sqlite_requests_are_future_gated_not_marked_built():
    finding = frontier.evaluate_frontier_task("Implement the SQLite database authority spine.")

    assert finding.duplicate_risk is False
    assert finding.finding_code == "future_sqlite_spine_blocked_by_prerequisites"
    assert "SQLite authority spine is not built" in finding.recommendation
    assert "before any SQLite schema or runtime work" in finding.prerequisite_to_finish_first


def test_unknown_task_gets_non_duplicate_safe_boundary_response():
    finding = frontier.evaluate_frontier_task("Review the next smallest safe edge.")

    assert finding.duplicate_risk is False
    assert finding.finding_code == "no_duplicate_detected"
    assert "Keep the task bounded" in finding.recommendation
    assert "smallest unfinished edge" in finding.prerequisite_to_finish_first


def test_frontier_map_status_to_dict_is_plain_and_deterministic():
    status = frontier.operator_frontier_map_status("build a bridge")
    first = frontier.frontier_map_status_to_dict(status)
    second = frontier.operator_frontier_map_status_dict("build a bridge")

    assert first == second
    assert first["receipt_type"] == "openclaw.operator_frontier_map_status"
    assert first["duplicate_work_finding"]["duplicate_risk"] is True
    assert first["execution_authority_granted"] is False


def test_frontier_map_status_exposes_next_unfinished_edges_and_forbidden_behaviors():
    status = frontier.operator_frontier_map_status()

    assert status.next_unfinished_edges
    assert any("receipt command" in edge for edge in status.next_unfinished_edges)
    assert any("question-response" in edge for edge in status.next_unfinished_edges)
    assert any("backend_knowledge_packet.py" in edge for edge in status.next_unfinished_edges)
    assert "provider/model/API call" in status.forbidden_live_behaviors
    assert "MCP integration or hidden/shared-memory write" in status.forbidden_live_behaviors
    assert "runtime, service, or process inspection" in status.forbidden_live_behaviors
    assert "commit or push" in status.forbidden_live_behaviors


def test_status_checks_prove_non_live_read_only_frontier_guard():
    report = frontier.operator_frontier_map_status_dict()

    assert report["passed"] is True
    assert report["mode"] == "read-only/static-frontier-map/no-execution"
    assert report["execution_authority_granted"] is False
    assert report["provider_or_model_called"] is False
    assert report["sqlite_used"] is False
    assert report["ingestion_used"] is False
    assert report["embeddings_used"] is False
    assert report["vector_retrieval_used"] is False
    assert report["pageindex_or_tree_retrieval_used"] is False
    assert report["graph_engine_used"] is False
    assert report["mcp_called"] is False
    assert report["private_root_access_used"] is False
    assert report["runtime_or_process_inspection_used"] is False
    assert report["cassandra_chief_telegram_wired"] is False
    assert report["external_send_used"] is False
    assert report["commit_or_push_used"] is False
    assert report["checks"]["duplicate_guard_available"] is True
    assert report["checks"]["bridge_overlap_guard_available"] is True


def test_module_has_no_live_imports_or_runtime_provider_storage_behavior():
    source = inspect.getsource(frontier)
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
        "typing",
    }
    assert imported_modules.isdisjoint(
        {
            "boto3",
            "chromadb",
            "faiss",
            "google",
            "httpx",
            "mcp",
            "numpy",
            "openai",
            "pathlib",
            "pinecone",
            "requests",
            "sentence_transformers",
            "sqlite3",
            "subprocess",
            "torch",
            "transformers",
        }
    )
    assert called_names.isdisjoint(
        {
            "check_call",
            "check_output",
            "connect",
            "execute",
            "exists",
            "from_pretrained",
            "glob",
            "is_dir",
            "is_file",
            "iterdir",
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
            "write_text",
        }
    )
    assert "sqlite3" not in source
    assert "requests" not in source
    assert "subprocess" not in source
