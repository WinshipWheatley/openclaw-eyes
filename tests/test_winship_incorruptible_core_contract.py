import json
import re
from pathlib import Path

import winship_incorruptible_core_contract as core
from scripts.export_winship_incorruptible_core_contract import main as export_main


FIXED_NOW = "2026-05-24T23:00:00+00:00"


def _build() -> dict:
    return core.build_winship_incorruptible_core_contract(generated_at=FIXED_NOW)


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert core.stable_json(first) == core.stable_json(second)
    assert first["schema_version"] == core.SCHEMA_VERSION
    assert first["read_model_id"] == core.READ_MODEL_ID
    assert first["contract_status"] == core.CONTRACT_STATUS
    assert first["machine_proof"]["all_live_authority_flags_false"] is True
    assert first["machine_proof"]["legal_claim_created"] is False


def test_required_models_exist():
    payload = _build()
    proof = payload["machine_proof"]
    schemas = payload["model_schemas"]

    assert proof["winship_incorruptible_core_contract_model_present"] is True
    assert proof["protective_force_boundary_model_present"] is True
    assert proof["anti_skynet_boundary_model_present"] is True
    assert proof["defensive_use_classification_model_present"] is True
    assert proof["public_sector_military_adjacent_policy_model_present"] is True
    assert proof["beneficial_output_gate_model_present"] is True
    assert proof["incorruptible_core_tradeoff_model_present"] is True
    assert proof["ship_level_non_bypassable_boundary_model_present"] is True
    assert proof["shipyard_anti_capture_alignment_model_present"] is True
    assert proof["builder_blockers_model_present"] is True
    assert proof["elioperator_report_model_present"] is True
    assert schemas["winship_incorruptible_core_contract"]["required_fields"] == list(
        core.REQUIRED_CORE_CONTRACT_FIELDS
    )
    assert schemas["protective_force_boundary"]["required_fields"] == list(
        core.REQUIRED_PROTECTIVE_FORCE_FIELDS
    )
    assert schemas["winship_incorruptible_core_builder_blocker"]["required_fields"] == list(
        core.REQUIRED_BUILDER_BLOCKER_FIELDS
    )


def test_protective_force_boundary_exists_with_allowed_and_forbidden_modes():
    payload = _build()
    boundary = payload["protective_force_boundary"]

    for mode in core.ALLOWED_FORCE_MODES:
        assert mode in boundary["allowed_force_modes"]
    for mode in core.FORBIDDEN_FORCE_MODES:
        assert mode in boundary["forbidden_force_modes"]
    assert "PROTECT_CIVILIANS" in boundary["allowed_force_modes"]
    assert "WEAPON_OPTIMIZATION" in boundary["forbidden_force_modes"]
    assert "EXPLOIT_GENERATION" in boundary["forbidden_force_modes"]
    assert payload["machine_proof"]["all_allowed_force_modes_present"] is True
    assert payload["machine_proof"]["all_forbidden_force_modes_present"] is True


def test_anti_skynet_boundary_exists_and_blocks_becoming_the_harm():
    payload = _build()
    boundary = payload["anti_skynet_boundary"]

    assert "must not become" in boundary["doctrine"]
    assert boundary["autonomous_harm_forbidden"] is True
    assert boundary["surveillance_abuse_forbidden"] is True
    assert boundary["manipulation_forbidden"] is True
    assert "document" in boundary["allowed_response_postures"]
    assert "warn" in boundary["allowed_response_postures"]
    assert "exploit generation" in boundary["blocked_response_postures"]
    assert payload["machine_proof"]["anti_skynet_boundary_exists"] is True


def test_defensive_use_classifications_exist_for_allowed_blocked_and_ambiguous_cases():
    payload = _build()
    classifications = payload["defensive_use_classifications_by_id"]

    assert classifications["classification_public_infrastructure_defense"]["classification_result"] == (
        "ALLOWED_WITH_REVIEW"
    )
    assert classifications["classification_humanitarian_logistics"]["classification_result"] == (
        "ALLOWED_PROTECTIVE"
    )
    assert classifications["classification_evidence_preservation"]["classification_result"] == (
        "ALLOWED_WITH_REVIEW"
    )
    assert classifications["classification_blocked_offensive_targeting"]["classification_result"] == (
        "BLOCKED_AGGRESSION"
    )
    assert classifications["classification_blocked_civilian_surveillance"]["classification_result"] == (
        "BLOCKED_SURVEILLANCE_ABUSE"
    )
    assert classifications["classification_defensive_ambiguity"]["classification_result"] == (
        "NARROW_OUTPUT_ONLY"
    )


def test_public_sector_military_adjacent_policy_exists_and_requires_review():
    payload = _build()
    policy = payload["public_sector_military_adjacent_policy"]

    assert "hardening systems against attack" in policy["allowed_public_sector_uses"]
    assert "civilian harm reduction" in policy["allowed_military_adjacent_uses"]
    assert "offensive targeting" in policy["prohibited_uses"]
    assert "weapon optimization" in policy["prohibited_uses"]
    assert "legal review for public-sector or force-adjacent deployment" in policy["review_requirements"]
    assert payload["machine_proof"]["public_sector_review_required"] is True
    assert payload["machine_proof"]["military_adjacent_review_posture_present"] is True


def test_beneficial_output_gate_allows_protective_and_blocks_harmful():
    payload = _build()
    gates = payload["beneficial_output_gates_by_id"]

    assert gates["gate_public_infrastructure_defense"]["decision"] == "ALLOW_WITH_REVIEW"
    assert gates["gate_blocked_targeting"]["decision"] == "REFUSE_HARMFUL"
    assert gates["gate_defensive_ambiguity"]["decision"] == "NARROW_TO_SAFE_OUTPUT"
    assert "ELIOPERATOR" in gates["gate_blocked_targeting"]["elioperator_warning"]


def test_incorruptible_core_tradeoff_exists():
    payload = _build()
    tradeoff = payload["incorruptible_core_tradeoff"]

    assert tradeoff["offensive_power_reduced"] is True
    assert tradeoff["protective_power_preserved"] is True
    assert "Reducing offensive power is intentional" in tradeoff["reason"]
    assert payload["machine_proof"]["offensive_power_reduced_by_design"] is True
    assert payload["machine_proof"]["protective_power_preserved"] is True


def test_ship_level_non_bypassable_boundary_blocks_powerful_actor_override():
    payload = _build()
    boundary = payload["ship_level_non_bypassable_boundary"]

    assert "No captain, client, government, founder" in boundary["ship_level_rule"]
    assert "block autonomous harm" in boundary["non_bypassable_requirements"]
    assert "not a bypass" in boundary["government_override_limits"]
    assert "cannot override" in boundary["founder_override_limits"]
    assert boundary["guardian_review_required"] is True
    assert payload["machine_proof"]["non_bypassable_boundary_blocks_powerful_actor_override"] is True


def test_shipyard_anti_capture_alignment_references_covenant_and_has_no_live_trigger():
    payload = _build()
    alignment = payload["shipyard_anti_capture_alignment"]

    assert alignment["shipyard_covenant_ref"] == "shipyard_sovereignty_covenant_contract_v0"
    assert alignment["fleet_established_required"] is True
    assert "no attack or retaliation" in alignment["trust_migration_concept"]
    assert "Private captain/client data" in alignment["private_data_protection"]
    for value in alignment["live_trigger_authority"].values():
        assert value is False
    assert payload["machine_proof"]["shipyard_corruption_alignment_exists"] is True


def test_builder_blockers_exist_and_fail_closed():
    payload = _build()
    blockers = payload["builder_blockers_by_id"]
    blocker_types = {blocker["blocker_type"] for blocker in blockers.values()}

    for expected in core.CORE_BLOCKER_TYPES:
        if expected != "UNKNOWN_FAIL_CLOSED":
            assert expected in blocker_types
    assert blockers["blocker_aggression_engine_risk"]["blocker_type"] == "AGGRESSION_ENGINE_RISK"
    assert blockers["blocker_surveillance_abuse_risk"]["blocker_type"] == "SURVEILLANCE_ABUSE_RISK"
    assert blockers["blocker_founder_override_core_boundary"]["blocker_type"] == (
        "FOUNDER_OVERRIDE_OF_CORE_BOUNDARY"
    )
    for blocker in blockers.values():
        assert blocker["fail_closed"] is True
        assert "ELIOPERATOR" in blocker["elioperator_warning"]


def test_required_examples_exist():
    payload = _build()
    examples = payload["examples"]

    for key in [
        "public_infrastructure_defense",
        "humanitarian_logistics",
        "evidence_preservation",
        "blocked_targeting",
        "blocked_surveillance",
        "defensive_ambiguity",
        "anti_skynet",
        "founder_government_override",
        "shipyard_corruption_alignment",
    ]:
        assert key in examples
    assert examples["public_infrastructure_defense"]["offensive_targeting_allowed"] is False
    assert examples["evidence_preservation"]["raw_protected_body_allowed"] is False
    assert examples["blocked_targeting"]["decision"] == "REFUSE_HARMFUL"
    assert examples["defensive_ambiguity"]["decision"] == "NARROW_TO_SAFE_OUTPUT"
    assert examples["founder_government_override"]["review_required"] is True
    assert examples["shipyard_corruption_alignment"]["live_trigger_today"] is False


def test_elioperator_report_exists_and_is_precise():
    payload = _build()
    report = payload["elioperator_report"]

    assert report["plain_summary"]
    assert "offensive targeting" in report["what_this_blocks"]
    assert "hardening" in report["what_this_allows"]
    assert "Reducing offensive power is intentional" in report["why_offensive_power_is_limited"]
    assert "not a military automation lane" in core.format_operator_markdown(payload)


def test_authority_boundary_all_live_flags_false():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    for value in payload["authority_boundary"].values():
        assert value is False
    for value in payload["winship_incorruptible_core_contract"]["live_enforcement_authority"].values():
        assert value is False


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


def test_generated_outputs_have_no_operational_weapon_cyber_or_surveillance_instructions(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    combined = (
        (export_root / "winship_incorruptible_core_contract.json").read_text(encoding="utf-8").lower()
        + "\n"
        + (export_root / "winship_incorruptible_core_contract_OPERATOR.md").read_text(encoding="utf-8").lower()
    )
    operational_patterns = [
        r"step\\s*1\\s*:",
        r"how to exploit",
        r"exploit code",
        r"payload to",
        r"weapon design",
        r"surveillance procedure",
        r"select targets by",
        r"bypass approval by",
    ]
    for pattern in operational_patterns:
        assert not re.search(pattern, combined)


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "winship_incorruptible_core_contract.py",
            "scripts/export_winship_incorruptible_core_contract.py",
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
