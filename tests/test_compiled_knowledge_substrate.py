from __future__ import annotations

import ast
import inspect

import compiled_knowledge_substrate as substrate


def _fixture() -> substrate.CompiledKnowledgeFixture:
    return substrate.fixture_compiled_knowledge_substrate()


def _packet() -> substrate.AnswerPacket:
    return substrate.build_answer_packet("What do we know about fixture catalog context?")


def test_raw_parsed_and_rendered_evidence_are_not_accepted_truth():
    fixture = _fixture()

    assert fixture.raw_sources
    assert fixture.parsed_evidence
    assert fixture.rendered_fragments
    assert all(source.accepted_truth is False for source in fixture.raw_sources)
    assert all(
        evidence.evidence_not_truth is True and evidence.accepted_truth is False
        for evidence in fixture.parsed_evidence
    )
    assert all(
        fragment.shape_preserved is True
        and fragment.rendered_not_truth is True
        and fragment.accepted_truth is False
        for fragment in fixture.rendered_fragments
    )


def test_claims_are_hypotheses_until_operator_promotion_scope_exists():
    fixture = _fixture()
    claims = {claim.claim_id: claim for claim in fixture.claims}
    promotions = {promotion.target_id: promotion for promotion in fixture.promotions}

    assert claims["claim_catalog_admin_candidate"].state == "hypothesis"
    assert claims["claim_catalog_admin_candidate"].accepted_truth is False
    assert claims["claim_catalog_admin_candidate"].current_state_authority is False
    assert "note_promoted_catalog_context" in promotions
    assert promotions["note_promoted_catalog_context"].decision == "accepted"
    assert promotions["note_promoted_catalog_context"].grants_action_authority is False


def test_draft_compiled_notes_are_interpretation_only_not_accepted_truth():
    fixture = _fixture()
    draft_notes = [
        note for note in fixture.compiled_notes if note.note_state == "draft_compiled_note"
    ]

    assert draft_notes
    assert all(note.interpretation_only is True for note in draft_notes)
    assert all(note.accepted_working_context is False for note in draft_notes)
    assert all(note.execution_authority_granted is False for note in draft_notes)


def test_promoted_compiled_notes_are_scoped_source_backed_working_context():
    fixture = _fixture()
    promoted = substrate.promoted_compiled_notes(fixture)

    assert len(promoted) == 1
    note = promoted[0]
    assert note.note_id == "note_promoted_catalog_context"
    assert note.accepted_working_context is True
    assert note.scope == "catalog_administration_orientation_only"
    assert note.source_ids == ("source_ops_memo_2020",)
    assert note.evidence_ids == ("evidence_ops_memo_parsed",)
    assert note.execution_authority_granted is False


def test_rejected_claims_cannot_support_answer_packets():
    packet = _packet()

    assert "claim_rejected_current_royalty_rate" in packet.rejected_claims_excluded
    assert "claim_rejected_current_royalty_rate" not in packet.claim_basis
    assert "rejected" in packet.answer_summary.lower()


def test_historical_claims_are_background_not_current_state_authority():
    fixture = _fixture()
    packet = _packet()
    historical_claim = next(
        claim
        for claim in fixture.claims
        if claim.claim_id == "claim_historical_distribution_rate"
    )

    assert historical_claim.state == "historical"
    assert historical_claim.current_state_authority is False
    assert historical_claim.accepted_truth is False
    assert historical_claim.claim_id in packet.historical_context
    assert historical_claim.claim_id not in packet.claim_basis


def test_sensitive_no_export_records_block_export_and_shape_answer():
    packet = _packet()

    assert packet.export_eligible is False
    assert "claim_sensitive_payment_reference" in packet.sensitive_no_export_material
    assert "source_payment_snapshot_sensitive" in packet.sensitive_no_export_material
    assert packet.export_blockers
    assert any("no_export" in blocker for blocker in packet.export_blockers)
    assert "sensitive material blocks export" in packet.answer_summary


def test_answer_packets_expose_basis_unknowns_promotions_and_covenant_boundaries():
    packet = _packet()
    packet_dict = substrate.answer_packet_to_dict(packet)

    assert packet.source_basis
    assert packet.evidence_basis
    assert packet.rendered_fragment_basis
    assert packet.observation_basis
    assert packet.claim_basis == ("claim_catalog_admin_candidate",)
    assert packet.draft_compiled_note_basis == ("note_draft_cashflow_context",)
    assert packet.promoted_compiled_note_basis == ("note_promoted_catalog_context",)
    assert packet.unknowns
    assert any("unknown" in unknown.lower() for unknown in packet.unknowns)
    assert packet.promotion_state
    assert any(
        promotion.target_id == "note_promoted_catalog_context"
        and promotion.decision == "accepted"
        for promotion in packet.promotion_state
    )
    assert packet.covenant_needed_action_boundaries
    assert any(
        "Operator Action Covenant" in boundary
        for boundary in packet.covenant_needed_action_boundaries
    )
    assert packet.execution_authority_granted is False
    assert packet_dict["execution_authority_granted"] is False


def test_relational_edges_are_fixture_data_only_not_graph_engine_behavior():
    fixture = _fixture()
    packet = _packet()

    assert fixture.relational_edges
    assert all(edge.fixture_data_only is True for edge in fixture.relational_edges)
    assert packet.relational_edges_consulted == tuple(
        edge.edge_id for edge in fixture.relational_edges
    )
    assert packet.graph_engine_used is False
    assert packet.retrieval_mode == "fixture_candidate_selection_only"


def test_status_function_proves_non_live_non_provider_non_storage_behavior():
    report = substrate.compiled_knowledge_substrate_status()

    assert report["passed"] is True
    assert report["receipt_type"] == "openclaw.compiled_knowledge_substrate_status"
    assert report["execution_authority_granted"] is False
    assert report["sqlite_used"] is False
    assert report["sql_ddl_defined"] is False
    assert report["database_file_created"] is False
    assert report["ingestion_used"] is False
    assert report["private_root_access_used"] is False
    assert report["provider_or_model_called"] is False
    assert report["embeddings_used"] is False
    assert report["vector_library_used"] is False
    assert report["mcp_called"] is False
    assert report["hidden_memory_write_used"] is False
    assert report["runtime_launched"] is False
    assert report["process_state_inspected"] is False
    assert report["cassandra_chief_telegram_wired"] is False
    assert report["external_send_used"] is False
    assert report["commit_or_push_used"] is False
    assert report["checks"]["sensitive_material_blocks_export"] is True
    assert report["checks"]["relational_edges_fixture_only"] is True


def test_module_has_no_live_imports_file_io_sqlite_provider_vector_or_mcp_behavior():
    source = inspect.getsource(substrate)
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
