import json
import re
from pathlib import Path

import conversational_workflow_memory_contract as memory
from scripts.export_conversational_workflow_memory_contract import main as export_main


FIXED_NOW = "2026-05-24T23:45:00+00:00"


def _build() -> dict:
    return memory.build_conversational_workflow_memory_contract(generated_at=FIXED_NOW)


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert memory.stable_json(first) == memory.stable_json(second)
    assert first["schema_version"] == memory.SCHEMA_VERSION
    assert first["read_model_id"] == memory.READ_MODEL_ID
    assert first["contract_status"] == memory.CONTRACT_STATUS
    assert first["machine_proof"]["all_live_authority_flags_false"] is True
    assert first["machine_proof"]["external_action_performed"] is False


def test_required_models_exist():
    payload = _build()
    proof = payload["machine_proof"]
    schemas = payload["model_schemas"]

    assert proof["conversational_workflow_intake_model_present"] is True
    assert proof["workflow_block_chain_proposal_model_present"] is True
    assert proof["stored_workflow_procedure_model_present"] is True
    assert proof["governed_workflow_run_plan_model_present"] is True
    assert proof["workflow_role_routing_plan_model_present"] is True
    assert proof["artifact_and_proof_plan_model_present"] is True
    assert proof["completion_readback_contract_model_present"] is True
    assert proof["builder_blockers_model_present"] is True
    assert proof["elioperator_report_model_present"] is True
    assert schemas["conversational_workflow_intake"]["required_fields"] == list(memory.REQUIRED_INTAKE_FIELDS)
    assert schemas["workflow_block_chain_proposal"]["required_fields"] == list(memory.REQUIRED_PROPOSAL_FIELDS)
    assert schemas["stored_workflow_procedure"]["required_fields"] == list(memory.REQUIRED_PROCEDURE_FIELDS)


def test_generic_workflow_examples_exist_and_are_review_gated():
    payload = _build()
    examples = payload["examples"]

    assert payload["machine_proof"]["generic_workflow_example_present"] is True
    assert payload["machine_proof"]["generic_stored_procedure_example_present"] is True
    assert payload["machine_proof"]["generic_governed_run_example_present"] is True
    assert examples["generic_workflow_intake"]["operator_review_required"] is True
    assert examples["generic_workflow_intake"]["narrative_treated_as_truth"] is False
    assert examples["generic_stored_procedure"]["reusable_not_authority"] is True
    assert examples["generic_do_it_run_request"]["external_action_performed"] is False


def test_generic_intake_proposal_procedure_run_are_not_authority():
    payload = _build()
    intake = payload["conversational_workflow_intake"]
    proposal = payload["workflow_block_chain_proposal"]
    procedure = payload["stored_workflow_procedure"]
    run = payload["governed_workflow_run_plan"]

    assert intake["raw_narrative_allowed_in_normal_read_model"] is False
    assert intake["operator_review_required"] is True
    assert proposal["review_status"] == "OPERATOR_REVIEW_REQUIRED"
    assert procedure["authority_boundaries"]["stored_procedure_is_external_authority"] is False
    assert procedure["authority_boundaries"]["stored_procedure_can_send_or_submit"] is False
    assert run["current_state"] == "OPERATOR_REVIEW_REQUIRED"
    assert payload["machine_proof"]["narrative_is_not_treated_as_truth"] is True
    assert payload["machine_proof"]["procedure_memory_is_not_authority"] is True


def test_role_routing_exists_and_is_generic():
    payload = _build()
    routing = payload["workflow_role_routing_plan"]
    roles = {role["role"] for role in routing["roles"]}

    for role in memory.GENERIC_REQUIRED_ROLES:
        assert role in roles
    assert routing["no_hardcoded_persona_requirement"] is True
    assert "Cassandra" in routing["actor_candidates"]
    assert "Guardian" in routing["actor_candidates"]
    assert payload["machine_proof"]["all_generic_roles_present"] is True
    assert payload["machine_proof"]["persona_hardcoding_blocked"] is True


def test_artifact_proof_plan_and_completion_contract_block_fake_completion():
    payload = _build()
    proof_plan = payload["artifact_and_proof_plan"]
    completion = payload["completion_readback_contract"]

    assert "artifact hash receipts" in proof_plan["missing_proofs"]
    assert "approval receipts" in proof_plan["missing_proofs"]
    assert completion["status_label"] == "FUTURE_TARGET_NOT_CURRENT_FACT"
    assert "No approval or external result receipts exist." in completion["unresolved_items"]
    assert payload["machine_proof"]["fake_completion_blocked"] is True


def test_capital_hilton_example_exists_with_required_chain_and_procedure():
    payload = _build()
    capital = payload["capital_hilton_example"]

    assert payload["machine_proof"]["capital_hilton_narrative_intake_exists"] is True
    assert payload["machine_proof"]["capital_hilton_block_chain_proposal_exists"] is True
    assert payload["machine_proof"]["capital_hilton_stored_procedure_exists"] is True
    assert payload["machine_proof"]["capital_hilton_governed_run_plan_exists"] is True
    assert capital["stored_procedure"]["procedure_name"] == "How Capital Hilton invoices get paid"
    assert "Annette candidate" in capital["narrative_intake"]["sanitized_summary"]
    assert "official payment rail is Coupa" in capital["narrative_intake"]["sanitized_summary"]


def test_capital_hilton_block_chain_contains_required_steps():
    payload = _build()
    blocks = payload["capital_hilton_example"]["proposed_block_chain"]["proposed_blocks"]
    labels = {block["label"] for block in blocks}

    for label in memory.CAPITAL_HILTON_BLOCK_LABELS:
        assert label in labels
    assert payload["machine_proof"]["capital_hilton_all_required_blocks_present"] is True


def test_capital_hilton_now_do_it_cassandra_guardian_and_invoice_sent_are_future_gated():
    payload = _build()
    capital = payload["capital_hilton_example"]
    run = capital["now_do_it_run_plan"]
    completion = capital["invoice_sent_completion_target"]

    assert run["current_state"] == "OPERATOR_REVIEW_REQUIRED"
    assert "email draft or send" in run["blocked_now"]
    assert "Coupa access or submit" in run["blocked_now"]
    assert capital["cassandra_draft_stage"]["draft_allowed_now"] is False
    assert capital["guardian_approval_stage"]["approval_allowed_now"] is False
    assert completion["headline"] == "INVOICE SENT (future target; not current)"
    assert completion["status_label"] == "FUTURE_TARGET_NOT_CURRENT_FACT"
    assert payload["machine_proof"]["invoice_sent_target_exists"] is True
    assert payload["machine_proof"]["invoice_sent_is_not_current_fact"] is True


def test_capital_hilton_proof_bullets_include_invoice_sent_target_requirements():
    payload = _build()
    bullets = payload["capital_hilton_example"]["invoice_sent_completion_target"]["proof_bullets"]

    assert "Coupa invoice generated/submitted from PO, if required and proven." in bullets
    assert "Email sent to Annette with attached Winship-branded Excel PDF invoice." in bullets
    assert "Winship-branded Excel PDF invoice saved with date." in bullets
    assert "Last invoice sent date recorded for future invoice-range calculation." in bullets
    assert "External send/submit proof receipts attached." in bullets
    assert "Payment tracking state updated." in bullets


def test_builder_blockers_cover_required_fail_closed_cases():
    payload = _build()
    blockers = payload["builder_blockers_by_id"]
    blocker_types = {blocker["blocker_type"] for blocker in blockers.values()}

    for expected in memory.BUILDER_BLOCKER_TYPES:
        assert expected in blocker_types
    for blocker in blockers.values():
        assert blocker["fail_closed"] is True
        assert "ELIOPERATOR" in blocker["elioperator_warning"]
    assert payload["machine_proof"]["fake_completion_blocked"] is True
    assert payload["machine_proof"]["machine_contract_ui_leakage_blocked"] is True


def test_authority_boundary_all_live_flags_false():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key


def test_generated_outputs_have_no_raw_pii_or_secret_like_values(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])

    data = json.loads(json_path.read_text(encoding="utf-8"))
    combined = json_path.read_text(encoding="utf-8") + "\n" + operator_path.read_text(encoding="utf-8")
    assert data["machine_proof"]["credentials_or_secrets_included"] is False
    assert data["machine_proof"]["raw_private_bodies_included"] is False
    assert data["machine_proof"]["raw_sensitive_fixture_values_included"] is False
    assert "@" not in combined
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "PO-" not in combined
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


def test_operator_markdown_is_plain_and_not_machine_contract_ui_leakage():
    payload = _build()
    markdown = memory.format_operator_markdown(payload)

    assert "ELIOPERATOR" in markdown
    assert "operator_review_required" not in markdown
    assert "schema_version" not in markdown
    assert "No live chat parser" in markdown
    assert payload["machine_proof"]["machine_contract_ui_leakage_blocked"] is True


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "conversational_workflow_memory_contract.py",
            "scripts/export_conversational_workflow_memory_contract.py",
        ]
    )
    forbidden = [
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "subprocess.",
        "os.system",
        "smtplib",
        "selenium",
        "playwright",
        "coupa.login",
        "send_message",
        "shell=true",
        "eval(",
    ]
    for token in forbidden:
        assert token not in source
