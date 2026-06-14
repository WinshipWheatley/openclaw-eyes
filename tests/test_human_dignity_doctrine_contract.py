import json
import re
import sys
from dataclasses import fields
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import human_dignity_doctrine_contract as dignity
from scripts.export_human_dignity_doctrine_contract import main as export_main


FIXED_NOW = "2026-05-25T23:59:00+00:00"


def test_required_models_have_required_fields():
    expected = {
        "HumanDignityDoctrineContract": (
            "contract_id",
            "doctrine",
            "source_inspiration",
            "operational_principles",
            "decision_policy",
            "prohibited_system_patterns",
            "required_design_patterns",
            "agent_behavior_policy",
            "automation_policy",
            "labor_and_prosperity_policy",
            "authority_boundary",
            "next_safe_move",
        ),
        "OperationalPrinciple": (
            "principle_id",
            "name",
            "plain_definition",
            "openclaw_translation",
            "required_behavior",
            "forbidden_behavior",
            "example",
            "next_safe_move",
        ),
        "HumanDignityDecisionCheck": (
            "check_id",
            "decision_type",
            "affected_people",
            "dignity_risk",
            "common_good_risk",
            "power_concentration_risk",
            "vulnerable_party_risk",
            "labor_impact_risk",
            "human_review_required",
            "blocked_until",
            "next_safe_move",
        ),
        "ProhibitedSystemPattern": (
            "pattern_id",
            "pattern_name",
            "description",
            "why_blocked",
            "detection_hint",
            "elioperator_warning",
            "next_safe_move",
        ),
        "RequiredDesignPattern": (
            "pattern_id",
            "pattern_name",
            "description",
            "where_it_applies",
            "required_output",
            "test_hint",
            "next_safe_move",
        ),
        "AgentDoctrineApplication": (
            "agent_role",
            "dignity_obligation",
            "common_good_obligation",
            "forbidden_agent_behavior",
            "required_agent_behavior",
            "example_good",
            "example_bad",
            "next_safe_move",
        ),
        "HumanDignityReadback": (
            "readback_id",
            "status",
            "operator_headline",
            "operator_message",
            "doctrine_summary",
            "design_implications",
            "blocked_patterns",
            "next_safe_move",
        ),
    }
    classes = {
        "HumanDignityDoctrineContract": dignity.HumanDignityDoctrineContract,
        "OperationalPrinciple": dignity.OperationalPrinciple,
        "HumanDignityDecisionCheck": dignity.HumanDignityDecisionCheck,
        "ProhibitedSystemPattern": dignity.ProhibitedSystemPattern,
        "RequiredDesignPattern": dignity.RequiredDesignPattern,
        "AgentDoctrineApplication": dignity.AgentDoctrineApplication,
        "HumanDignityReadback": dignity.HumanDignityReadback,
    }
    for name, required_fields in expected.items():
        assert tuple(field.name for field in fields(classes[name])) == required_fields


def test_payload_contains_required_principles_patterns_and_checks():
    payload = dignity.build_payload(generated_at=FIXED_NOW)

    assert {item["principle_id"] for item in payload["operational_principles"]} == set(dignity.PRINCIPLE_IDS)
    assert {item["pattern_id"] for item in payload["prohibited_system_patterns"]} == set(dignity.PROHIBITED_PATTERN_IDS)
    assert {item["pattern_id"] for item in payload["required_design_patterns"]} == set(dignity.REQUIRED_DESIGN_PATTERN_IDS)
    assert {item["decision_type"] for item in payload["decision_checks"]} == set(dignity.DECISION_TYPES)
    assert payload["machine_proof"]["all_required_principles_present"] is True
    assert payload["machine_proof"]["all_required_prohibited_patterns_present"] is True
    assert payload["machine_proof"]["all_required_design_patterns_present"] is True
    assert payload["machine_proof"]["all_required_decision_types_present"] is True


def test_agent_applications_exist_for_required_roles():
    payload = dignity.build_payload(generated_at=FIXED_NOW)

    applications = {item["agent_role"]: item for item in payload["agent_applications"]}

    assert set(applications) == set(dignity.AGENT_ROLES)
    assert "automation purely because it is efficient" in applications["Chief"]["example_bad"]
    assert "recipients as message targets" in applications["Cassandra"]["example_bad"]
    assert "humane next step" in applications["Guardian"]["example_bad"]
    assert "output metrics" in applications["Niles"]["example_good"]
    assert "claims it executed the fix" in applications["Hermes"]["example_bad"]
    assert "Codex" not in applications
    assert payload["machine_proof"]["all_required_agent_applications_present"] is True


def test_required_examples_exist_and_fail_closed():
    payload = dignity.build_payload(generated_at=FIXED_NOW)
    examples = payload["examples"]

    assert payload["machine_proof"]["automation_example_present"] is True
    assert payload["machine_proof"]["labor_replacement_example_present"] is True
    assert payload["machine_proof"]["private_data_example_present"] is True
    assert payload["machine_proof"]["pricing_access_example_present"] is True
    assert payload["machine_proof"]["capital_hilton_example_present"] is True

    assert examples["automation_decision"]["approved_for_live_action"] is False
    assert "consent" in examples["automation_decision"]["expected"].lower()
    assert examples["worker_replacement_decision"]["approved_for_live_action"] is False
    assert "fair work" in examples["worker_replacement_decision"]["expected"].lower()
    assert examples["private_data_extraction"]["approved_for_live_action"] is False
    assert "raw-body extraction blocked" in examples["private_data_extraction"]["expected"].lower()
    assert examples["product_pricing_access"]["approved_for_live_action"] is False
    assert "elite-user optimization" in examples["product_pricing_access"]["expected"]
    assert examples["capital_hilton_invoice"]["approved_for_live_action"] is False
    assert "no hidden send or submit" in examples["capital_hilton_invoice"]["expected"]


def test_specific_prohibited_patterns_are_blocked():
    payload = dignity.build_payload(generated_at=FIXED_NOW)
    patterns = {item["pattern_id"]: item for item in payload["prohibited_system_patterns"]}

    assert "Hidden monitoring is blocked" in patterns["HIDDEN_SURVEILLANCE"]["elioperator_warning"]
    assert "appeal or reversal path" in patterns["AUTHORITY_WITHOUT_APPEAL"]["elioperator_warning"]
    assert "Profit-only optimization is blocked" in patterns["PROFIT_ONLY_OPTIMIZATION"]["elioperator_warning"]
    assert payload["machine_proof"]["hidden_surveillance_blocked"] is True
    assert payload["machine_proof"]["authority_without_appeal_blocked"] is True
    assert payload["machine_proof"]["profit_only_optimization_blocked"] is True


def test_authority_boundary_all_false_and_no_live_action():
    payload = dignity.build_payload(generated_at=FIXED_NOW)

    for value in payload["authority_boundary"].values():
        assert value is False
    assert payload["machine_proof"]["all_live_authority_false"] is True
    assert payload["machine_proof"]["live_policy_enforcement_mutation_performed"] is False
    assert payload["machine_proof"]["workflow_run_performed"] is False
    assert payload["machine_proof"]["agent_dispatch_performed"] is False
    assert payload["machine_proof"]["external_action_performed"] is False
    assert payload["machine_proof"]["surveillance_performed"] is False
    assert payload["machine_proof"]["pricing_change_performed"] is False
    assert payload["machine_proof"]["labor_decision_performed"] is False
    assert payload["machine_proof"]["credential_handling_performed"] is False
    assert payload["machine_proof"]["raw_body_ingestion_performed"] is False


def test_export_writes_json_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / dignity.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / dignity.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == dignity.READ_MODEL_ID
    assert summary["all_live_authority_false"] is True
    assert summary["sectarian_product_surface"] is False
    assert payload["readback"]["operator_headline"] == "Human dignity governance rail is modeled"
    assert "Human Dignity Doctrine Contract" in operator
    assert "nonsectarian and operational" in operator


def test_generated_outputs_have_no_credentials_secrets_or_private_bodies(tmp_path):
    payload = dignity.build_payload(generated_at=FIXED_NOW)
    dignity.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())
    lowered = text.lower()

    forbidden_literals = (
        "actual secret",
        "credential value",
        "password value",
        "token value",
        "raw private body value",
        "private key value",
    )
    for literal in forbidden_literals:
        assert literal not in lowered
    assert not re.search(r"AKIA[0-9A-Z]{16}", text)
    assert not re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", text)
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)


def test_contract_is_not_theology_or_proselytizing_surface():
    payload = dignity.build_payload(generated_at=FIXED_NOW)
    text = dignity.stable_json(payload)

    assert payload["machine_proof"]["sectarian_product_surface"] is False
    assert payload["machine_proof"]["theology_generation"] is False
    assert "proselytizing" in text
    assert "No sectarian claims" in text
