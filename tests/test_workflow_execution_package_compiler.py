import json
import re
from pathlib import Path

import workflow_execution_package_compiler as compiler
from scripts.export_workflow_execution_package_compiler import main as export_main


FIXED_NOW = "2026-05-25T05:00:00+00:00"


def _build() -> dict:
    return compiler.build_workflow_execution_package_compiler(generated_at=FIXED_NOW)


def test_required_models_exist_and_payload_is_deterministic():
    first = _build()
    second = _build()

    assert compiler.stable_json(first) == compiler.stable_json(second)
    assert first["schema_version"] == compiler.SCHEMA_VERSION
    assert first["read_model_id"] == compiler.READ_MODEL_ID
    proof = first["machine_proof"]
    assert proof["workflow_execution_package_compiler_model_present"] is True
    assert proof["workflow_execution_readiness_model_present"] is True
    assert proof["worker_execution_package_plan_model_present"] is True
    assert proof["workflow_execution_package_chain_model_present"] is True
    assert proof["workflow_missing_piece_navigator_model_present"] is True
    assert proof["workflow_execution_package_blocker_model_present"] is True
    assert proof["workflow_execution_package_elioperator_report_model_present"] is True


def test_required_field_lists_exist():
    payload = _build()
    schemas = payload["model_schemas"]

    assert schemas["workflow_execution_package_compiler"]["required_fields"] == list(compiler.REQUIRED_COMPILER_FIELDS)
    assert schemas["workflow_execution_readiness"]["required_fields"] == list(compiler.REQUIRED_READINESS_FIELDS)
    assert schemas["worker_execution_package_plan"]["required_fields"] == list(compiler.REQUIRED_PACKAGE_PLAN_FIELDS)
    assert schemas["workflow_execution_package_chain"]["required_fields"] == list(compiler.REQUIRED_CHAIN_FIELDS)
    assert schemas["workflow_missing_piece_navigator"]["required_fields"] == list(compiler.REQUIRED_NAVIGATOR_FIELDS)
    assert schemas["workflow_execution_package_blocker"]["required_fields"] == list(compiler.REQUIRED_BLOCKER_FIELDS)
    assert schemas["workflow_execution_package_elioperator_report"]["required_fields"] == list(compiler.REQUIRED_REPORT_FIELDS)


def test_enums_exist():
    payload = _build()

    assert payload["machine_proof"]["supported_workflow_types_present"] is True
    assert payload["machine_proof"]["readiness_statuses_present"] is True
    assert payload["machine_proof"]["package_types_present"] is True
    for workflow_type in ["invoice_delivery_workflow", "system_debug_workflow", "unknown_needs_framing"]:
        assert workflow_type in payload["supported_workflow_types"]
    for status in ["NOT_READY_MISSING_INPUTS", "PACKAGES_COMPILED_NOT_EXECUTABLE", "COMPLETION_BLOCKED_MISSING_PROOF"]:
        assert status in payload["readiness_statuses"]
    for package_type in compiler.PACKAGE_TYPES:
        assert package_type in payload["package_types"]


def test_capital_hilton_readiness_known_missing_blocked_items():
    payload = _build()
    readiness = payload["workflow_execution_readiness"]

    assert payload["machine_proof"]["capital_hilton_readiness_example_exists"] is True
    assert readiness["workflow_type"] == "invoice_delivery_workflow"
    assert readiness["client_ref"] == "Capital Hilton"
    assert readiness["readiness_status"] == "NOT_READY_MISSING_INPUTS"
    assert payload["machine_proof"]["capital_hilton_known_items_modeled"] is True
    assert "4 performance dates captured" in readiness["known_facts"]
    assert "$400/show" in readiness["known_facts"]
    assert "$1,600 basis" in readiness["known_facts"]
    assert "invoice preview exists" in readiness["known_facts"]
    assert payload["machine_proof"]["capital_hilton_missing_items_modeled"] is True
    assert "exact Coupa PO/reference" in readiness["missing_inputs"]
    assert "confirmation Annette is correct contact" in readiness["missing_inputs"]
    assert "final Winship-branded Excel/PDF artifact/hash" in readiness["missing_inputs"]
    assert payload["machine_proof"]["capital_hilton_blocked_items_modeled"] is True
    assert "email send" in readiness["blocked_items"]
    assert "Coupa access/submit" in readiness["blocked_items"]
    assert "browser automation" in readiness["blocked_items"]


def test_expected_package_plans_exist_with_authority_boundaries():
    payload = _build()
    plans = payload["worker_execution_package_plans_by_id"]
    package_types = {plan["package_type"] for plan in plans.values()}

    assert payload["machine_proof"]["expected_package_types_exist"] is True
    for expected in compiler.PACKAGE_TYPES[:-1]:
        assert expected in package_types

    pc = plans["package_plan_capital_hilton_pc_backend_validation"]
    mac = plans["package_plan_capital_hilton_mac_artifact_prep"]
    draft = plans["package_plan_capital_hilton_drafting_agent"]
    guardian = plans["package_plan_capital_hilton_guardian_approval"]

    assert pc["target_worker_type"] == "PC_CODEX"
    assert pc["target_machine"] == "PC_WSL"
    assert pc["package_status"] == "PACKAGE_PLAN_READY_NOT_EXECUTABLE"
    assert mac["target_worker_type"] == "MAC_CODEX"
    assert mac["target_machine"] == "MAC"
    assert "send email" in mac["forbidden_actions"]
    assert draft["target_worker_type"] == "CASSANDRA"
    assert "send" in draft["forbidden_actions"]
    assert guardian["target_worker_type"] == "GUARDIAN"
    assert "request live approval now" in guardian["forbidden_actions"]

    for plan in plans.values():
        assert not any(plan["authority_boundary"].values()), plan["package_plan_id"]


def test_package_chain_dependencies_and_gates_exist():
    payload = _build()
    chain = payload["workflow_execution_package_chain"]

    assert payload["machine_proof"]["package_chain_exists"] is True
    assert "package_plan_capital_hilton_pc_backend_validation" in chain["packages"]
    assert "package_plan_capital_hilton_final_readback" in chain["packages"]
    assert any(dep["package"] == "package_plan_capital_hilton_guardian_approval" for dep in chain["dependencies"])
    assert "Guardian approval before external send/submit" in chain["gates"]
    assert "Coupa PO/reference proof before Coupa submit" in chain["gates"]
    assert "send/submit receipts before completion" in chain["gates"]
    assert "INVOICE SENT can appear only after required send/submit/artifact/payment receipts exist." == chain["final_completion_condition"]


def test_missing_piece_navigator_exists_for_operator_walkthrough():
    payload = _build()
    navigators = payload["workflow_missing_piece_navigators_by_id"]

    assert payload["machine_proof"]["missing_piece_navigator_exists"] is True
    po = navigators["navigator_capital_hilton_coupa_po_reference"]
    contact = navigators["navigator_capital_hilton_contact_confirmation"]
    artifact = navigators["navigator_capital_hilton_artifact_hash"]

    assert po["missing_piece"] == "exact Coupa PO/reference"
    assert "What Coupa PO/reference" in po["next_question"]
    assert po["can_be_discovered_by_agent"] is False
    assert contact["missing_piece"] == "confirmation Annette is correct contact"
    assert artifact["missing_piece"] == "final Winship-branded Excel/PDF artifact/hash"


def test_future_completion_target_blocked_without_proof():
    payload = _build()
    completion = payload["capital_hilton_example"]["future_completion_target"]

    assert payload["machine_proof"]["completion_target_blocked_without_proof"] is True
    assert completion["headline"] == "INVOICE SENT"
    assert completion["completion_allowed"] is False
    assert completion["future_target_only"] is True
    assert completion["blocked_reason"] == "Proof receipts do not exist yet."
    assert "Email sent to Annette with Winship-branded Excel/PDF invoice attached." in completion["proof_bullets"]


def test_blockers_exist_and_fail_closed():
    payload = _build()
    blockers = payload["workflow_execution_package_blockers_by_id"]
    blocker_types = {blocker["blocker_type"] for blocker in blockers.values()}

    assert payload["machine_proof"]["blockers_present"] is True
    for expected in compiler.BLOCKER_TYPES:
        assert expected in blocker_types
    assert blockers["workflow_execution_package_blocker_completion_without_proof"]["fail_closed"] is True
    assert blockers["workflow_execution_package_blocker_external_action_attempted"]["fail_closed"] is True
    assert blockers["workflow_execution_package_blocker_unknown_fail_closed"]["severity"] == "CRITICAL"


def test_no_live_execution_dispatch_or_external_authority():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    assert payload["machine_proof"]["external_action_performed"] is False
    assert payload["machine_proof"]["agent_dispatch_performed"] is False
    assert payload["machine_proof"]["workflow_run_performed"] is False
    assert payload["machine_proof"]["tool_execution_performed"] is False
    for key, value in payload["authority_boundary"].items():
        assert value is False, key


def test_elioperator_report_explains_make_it_happen_without_execution():
    payload = _build()
    report = payload["workflow_execution_package_elioperator_report"]

    assert report["plain_summary"] == "This turns 'make it happen' into a governed package plan, not execution."
    assert "does not run packages" in report["what_this_does_not_do_yet"]
    assert "email send" in report["what_gets_gated"]
    assert "Coupa submit" in report["what_gets_gated"]
    assert report["next_safe_move"].startswith("Ask for the PO/reference")


def test_export_writes_parseable_outputs(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))

    assert summary["workflow_type"] == "invoice_delivery_workflow"
    assert summary["expected_package_types_exist"] is True
    assert summary["completion_target_blocked_without_proof"] is True
    assert data["machine_proof"]["all_live_authority_flags_false"] is True
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


def test_no_raw_pii_or_private_bodies_in_generated_outputs(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))
    combined = json_path.read_text(encoding="utf-8") + "\n" + operator_path.read_text(encoding="utf-8")

    assert data["machine_proof"]["credentials_or_secrets_included"] is False
    assert data["machine_proof"]["raw_private_bodies_included"] is False
    assert data["machine_proof"]["raw_pii_in_packages"] is False
    assert "@" not in combined
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "access_token" not in combined.lower()
    assert "raw email body:" not in combined.lower()
    assert "private key" not in combined.lower()


def test_source_does_not_import_network_or_runtime_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "workflow_execution_package_compiler.py",
            "scripts/export_workflow_execution_package_compiler.py",
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
        "codex exec",
        "openai",
        "ollama_call(",
    ]
    for token in forbidden:
        assert token not in source
