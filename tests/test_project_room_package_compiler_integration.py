import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import workflow_package_queue as queue


FIXED_NOW = "2026-06-08T12:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    for spec in queue.PROJECT_ROOM_COMPILER_PRECONDITIONS.values():
        _write_json(root / spec["filename"], {"status": spec["accepted_statuses"][0]})
    return root


def _project_refs(ref: str) -> dict:
    return {
        "project_room_id": f"project_room:{ref}",
        "source_inventory_ref": f"source_inventory:{ref}",
        "conflict_log_ref": f"conflict_log:{ref}",
        "missing_context_ref": f"missing_context:{ref}",
        "duplicate_report_ref": f"duplicate_report:{ref}",
        "decision_trace_ref": f"decision_trace:{ref}",
        "freshness_gate_ref": "generated/read_models/context_freshness_decision_trace_gate.json",
        "compaction_policy_ref": "generated/read_models/context_compaction_preview_policy.json",
    }


def _read_model(tmp_path: Path) -> dict:
    return queue.build_project_room_package_compiler_integration_read_model(
        read_model_root=_fixture_root(tmp_path),
        generated_at=FIXED_NOW,
    )


def _example(read_model: dict, example_ref: str) -> dict:
    return next(row for row in read_model["required_examples"] if row["example_ref"] == example_ref)


def test_serious_synthesis_package_blocked_without_source_inventory():
    gate = queue.compile_project_room_package_gate(
        {"package_ref": "test:serious_without_inventory", "package_type": "serious_synthesis"}
    )

    assert gate["project_room_required"] is True
    assert gate["project_room_ready"] is False
    assert gate["synthesis_allowed"] is False
    assert "source_inventory_missing" in gate["blockers"]
    assert gate["next_safe_action"] == "Build the project room source inventory before synthesis."


def test_missing_context_blocks_supported_claim():
    gate = queue.compile_project_room_package_gate(
        {
            "package_ref": "test:missing_context",
            "package_type": "serious_synthesis",
            **_project_refs("missing_context"),
            "source_inventory_exists": True,
            "duplicate_report_exists": True,
            "decision_trace_exists": True,
            "missing_context_blocks_supported_claim": True,
        }
    )

    assert gate["synthesis_allowed"] is False
    assert "missing_context_blocks_supported_claim" in gate["blockers"]
    assert gate["next_safe_action"] == "Name the missing context and avoid unsupported factual claims."


def test_unresolved_conflict_blocks_synthesis():
    gate = queue.compile_project_room_package_gate(
        {
            "package_ref": "test:conflict",
            "package_type": "client/business_draft",
            "uses_multiple_sources": True,
            **_project_refs("conflict"),
            "source_inventory_exists": True,
            "duplicate_report_exists": True,
            "decision_trace_exists": True,
            "unresolved_critical_conflict": True,
        }
    )

    assert gate["project_room_required"] is True
    assert gate["synthesis_allowed"] is False
    assert "unresolved_critical_conflict" in gate["blockers"]
    assert gate["next_safe_action"] == "Surface the conflict and request an operator decision."


def test_duplicate_version_family_requires_duplicate_report():
    refs = _project_refs("duplicate_family")
    refs.pop("duplicate_report_ref")
    gate = queue.compile_project_room_package_gate(
        {
            "package_ref": "test:duplicate_family",
            "package_type": "serious_synthesis",
            **refs,
            "source_inventory_exists": True,
            "decision_trace_exists": True,
            "version_families_exist": True,
        }
    )

    assert gate["synthesis_allowed"] is False
    assert "duplicate_report_ref" in gate["missing_project_room_refs"]
    assert "duplicate_report_missing" in gate["blockers"]
    assert gate["next_safe_action"] == "Create the duplicate/version report before weighting sources."


def test_lm2_worker_package_requires_project_or_proof_room():
    gate = queue.compile_project_room_package_gate(
        {"package_ref": "test:lm2_missing_room", "package_type": "LM2 worker package"}
    )

    assert gate["project_room_required"] is True
    assert gate["proof_bundle_required"] is True
    assert gate["synthesis_allowed"] is False
    assert "source_inventory_missing" in gate["blockers"]
    assert "proof_bundle_missing_or_not_current" in gate["blockers"]
    assert "bounded_objective_missing" in gate["blockers"]
    assert all(value is False for value in gate["lm2_context_protections"].values())


def test_finance_payment_watch_proof_to_response_allowed_without_full_project_room():
    gate = queue.compile_project_room_package_gate(
        {
            "package_ref": "finance:capital_hilton:payment_watch",
            "package_type": "proof_to_response",
            "current_proof_bundle_exists": True,
            "next_safe_action": "Attach payment evidence.",
        }
    )

    assert gate["project_room_required"] is False
    assert gate["proof_bundle_required"] is True
    assert gate["project_room_ready"] is True
    assert gate["synthesis_allowed"] is True
    assert gate["blocked_reason"] == ""
    assert gate["next_safe_action"] == "Attach payment evidence."
    assert gate["authority_boundary"]["paid"] is False
    assert gate["authority_boundary"]["ledger_mutation_allowed"] is False


def test_business_development_draft_requires_project_room_for_proposal_history():
    package = queue.create_package("Follow up on Capital Hilton proposal.", created_at=FIXED_NOW)
    gate = package["project_room_gate_result"]

    assert package["workflow_ref"] == "capital_hilton_proposal_followup"
    assert gate["project_room_required"] is True
    assert gate["source_inventory_exists"] is True
    assert gate["synthesis_allowed"] is False
    assert "unresolved_critical_conflict" in gate["blockers"]
    assert package["business_action_gate_result"]["email_send_allowed"] is False


def test_niles_mapping_blocks_factual_mapping_when_target_missing_but_allows_creative_questions(tmp_path):
    read_model = _read_model(tmp_path)
    example = _example(read_model, "niles_controller_mapping")
    gate = example["compiler_gate"]

    assert gate["synthesis_allowed"] is False
    assert "missing_context_blocks_supported_claim" in gate["blockers"]
    assert example["factual_mapping_allowed"] is False
    assert example["creative_options_allowed"] is True


def test_self_heal_repair_requires_validation_and_rollback_plan():
    missing = queue.compile_project_room_package_gate(
        {
            "package_ref": "test:self_heal_missing_plans",
            "package_type": "code/build/repair",
            **_project_refs("self_heal_missing_plans"),
            "source_inventory_exists": True,
            "duplicate_report_exists": True,
            "decision_trace_exists": True,
        }
    )
    complete = queue.compile_project_room_package_gate(
        {
            "package_ref": "test:self_heal_complete_plans",
            "package_type": "code/build/repair",
            **_project_refs("self_heal_complete_plans"),
            "source_inventory_exists": True,
            "duplicate_report_exists": True,
            "decision_trace_exists": True,
            "validation_plan_ref": "validation_plan:self_heal",
            "rollback_plan_ref": "rollback_plan:self_heal",
        }
    )

    assert missing["synthesis_allowed"] is False
    assert "validation_plan_missing" in missing["blockers"]
    assert "rollback_plan_missing" in missing["blockers"]
    assert complete["synthesis_allowed"] is True


def test_read_model_and_export_include_required_status_fields(tmp_path):
    result = queue.export_project_room_package_compiler_integration(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Project Room Package Compiler Integration.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == queue.PROJECT_ROOM_COMPILER_READY_STATUS
    assert local == bridge
    assert local["package_status_fields"] == [
        "project_room_required",
        "project_room_ready",
        "synthesis_allowed",
        "blocked_reason",
        "next_safe_action",
    ]
    assert "LM2 worker package" in {row["package_type"] for row in local["package_source_requirement_classifications"]}
    assert wiki.startswith("# Project Room Package Compiler Integration")


def test_no_unsafe_true_grants(tmp_path):
    read_model = _read_model(tmp_path)

    assert queue.project_room_compiler_unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True
