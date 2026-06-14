import json
import re
from pathlib import Path

import shipyard_sovereignty_covenant_contract as covenant
from scripts.export_shipyard_sovereignty_covenant_contract import main as export_main


FIXED_NOW = "2026-05-24T22:15:00+00:00"


def _build() -> dict:
    return covenant.build_shipyard_sovereignty_covenant_contract(generated_at=FIXED_NOW)


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert covenant.stable_json(first) == covenant.stable_json(second)
    assert first["schema_version"] == covenant.SCHEMA_VERSION
    assert first["read_model_id"] == covenant.READ_MODEL_ID
    assert first["contract_status"] == covenant.CONTRACT_STATUS
    assert first["machine_proof"]["all_live_authority_flags_false"] is True
    assert first["machine_proof"]["legal_claim_created"] is False


def test_required_models_exist():
    payload = _build()
    proof = payload["machine_proof"]
    schemas = payload["model_schemas"]

    assert proof["shipyard_sovereignty_covenant_model_present"] is True
    assert proof["shipyard_phase_model_present"] is True
    assert proof["shipyard_mission_dna_model_present"] is True
    assert proof["commercial_mission_boundary_model_present"] is True
    assert proof["creator_boundedness_policy_model_present"] is True
    assert proof["shipyard_capture_risk_model_present"] is True
    assert proof["last_clean_state_recovery_root_model_present"] is True
    assert proof["fleet_metamorphosis_fail_safe_model_present"] is True
    assert proof["fleet_mutual_aid_module_economy_model_present"] is True
    assert proof["shipyard_vs_ship_boundary_model_present"] is True
    assert proof["covenant_builder_blocker_model_present"] is True
    assert proof["covenant_elioperator_report_model_present"] is True
    assert schemas["shipyard_sovereignty_covenant"]["required_fields"] == list(
        covenant.REQUIRED_COVENANT_FIELDS
    )
    assert schemas["shipyard_phase_model"]["required_fields"] == list(covenant.REQUIRED_PHASE_MODEL_FIELDS)
    assert schemas["covenant_builder_blocker"]["required_fields"] == list(covenant.REQUIRED_BLOCKER_FIELDS)


def test_shipyard_doctrine_and_mission_dna_exist():
    payload = _build()
    cov = payload["shipyard_sovereignty_covenant"]
    dna = payload["shipyard_mission_dna"]

    assert payload["machine_proof"]["shipyard_doctrine_exists"] is True
    assert "capital must not own the mission" in cov["capital_boundary"].lower()
    assert "founder" in cov["creator_boundary"].lower()
    for value in covenant.MISSION_VALUES:
        assert value in dna["values"]
    assert "local-first" in dna["local_first_posture"]
    assert "Shipyard builds ships" in dna["shipyard_vs_ship_boundary"]


def test_phase_model_is_pre_fleet_and_not_armed():
    payload = _build()
    phase = payload["shipyard_phase_model"]

    assert payload["machine_proof"]["phase_model_exists"] is True
    assert phase["current_phase"] == "CATERPILLAR_BUILD_PHASE"
    assert payload["machine_proof"]["current_phase_is_pre_fleet"] is True
    assert phase["butterfly_laws_currently_armed"] is False
    assert phase["pre_fleet_activation_blocked"] is True
    assert phase["fleet_establishment_required"] is True
    assert phase["legal_review_required"] is True
    assert phase["explicit_founder_operator_arming_required"] is True
    assert phase["last_clean_state_required"] is True
    assert phase["private_data_exclusion_required"] is True
    assert set(covenant.SHIPYARD_PHASES) == {item["phase"] for item in phase["phases"]}
    assert payload["machine_proof"]["all_required_phases_present"] is True


def test_activation_and_release_authority_are_false():
    payload = _build()
    phase = payload["shipyard_phase_model"]
    authority = payload["authority_boundary"]

    assert phase["live_open_source_release_allowed"] is False
    assert phase["live_license_change_allowed"] is False
    assert phase["live_fork_trigger_allowed"] is False
    assert phase["live_covenant_enforcement_allowed"] is False
    assert payload["machine_proof"]["live_open_source_release_allowed"] is False
    assert payload["machine_proof"]["live_license_change_allowed"] is False
    assert payload["machine_proof"]["live_fork_trigger_allowed"] is False
    assert payload["machine_proof"]["live_governance_action_allowed"] is False
    for value in authority.values():
        assert value is False


def test_private_data_release_is_forbidden():
    payload = _build()
    boundary = payload["shipyard_sovereignty_covenant"]["private_data_boundary"]
    recovery = payload["last_clean_state_recovery_root"]

    assert boundary["release_or_fork_private_material_allowed"] is False
    assert boundary["private_data_exclusion_required"] is True
    for material in covenant.PRIVATE_DATA_FORBIDDEN_MATERIAL:
        assert material in boundary["forbidden_material"]
        assert material in recovery["private_data_exclusion"]
    assert payload["machine_proof"]["private_data_release_explicitly_forbidden"] is True


def test_commercial_boundary_allows_mission_aligned_commerce_and_refuses_harmful_work():
    payload = _build()
    boundary = payload["commercial_mission_boundary"]

    assert boundary["commercial_operation_allowed"] is True
    assert boundary["capital_use_allowed"] is True
    assert boundary["capital_capture_forbidden"] is True
    assert "not treated as greed" in boundary["private_operator_work_policy"]
    assert "refused" in boundary["harmful_work_refusal_policy"]
    assert payload["machine_proof"]["commercial_operation_allowed_while_mission_aligned"] is True
    assert payload["machine_proof"]["harmful_work_refused_not_taxed"] is True


def test_creator_boundedness_and_founder_override_risk_exist():
    payload = _build()
    policy = payload["creator_boundedness_policy"]

    assert policy["founder_not_above_covenant"] is True
    assert "mission preservation" in policy["elioperator_warning"]
    assert "selling control in a way that violates mission" in policy["prohibited_founder_actions"]
    assert "weakening safety gates to satisfy powerful customers" in policy["prohibited_founder_actions"]
    assert payload["machine_proof"]["creator_boundedness_exists"] is True
    assert payload["machine_proof"]["founder_override_risk_modeled"] is True


def test_capture_risk_examples_and_premature_trigger_exist():
    payload = _build()
    risks = payload["capture_risks_by_id"]
    examples = payload["examples"]

    assert risks["risk_capital_capture"]["risk_type"] == "CAPITAL_CAPTURE"
    assert risks["risk_founder_compromise"]["risk_type"] == "FOUNDER_COMPROMISE"
    assert risks["risk_private_data_release"]["risk_type"] == "PRIVACY_EXPLOITATION"
    assert risks["risk_safety_gate_bypass"]["risk_type"] == "SAFETY_GATE_BYPASS"
    assert risks["risk_premature_butterfly_trigger"]["risk_type"] == "PREMATURE_BUTTERFLY_TRIGGER"
    assert examples["premature_butterfly_trigger"]["blocked"] is True
    assert examples["premature_butterfly_trigger"]["live_release_or_fork_allowed"] is False
    assert payload["machine_proof"]["premature_butterfly_trigger_example_exists"] is True


def test_last_clean_state_recovery_root_is_concept_only():
    payload = _build()
    recovery = payload["last_clean_state_recovery_root"]

    assert recovery["last_verified_uncompromised_state_ref"] == "future_required_not_available_now"
    assert recovery["legal_review_required"] is True
    assert "No actual release or escrow occurs here." in recovery["release_or_escrow_policy"]
    assert "private data excluded" in recovery["clean_state_requirements"]
    for value in recovery["current_live_authority"].values():
        assert value is False


def test_fleet_metamorphosis_fail_safe_is_nonviolent_and_unarmed():
    payload = _build()
    fail_safe = payload["fleet_metamorphosis_fail_safe"]

    assert "field of butterflies" in fail_safe["metaphor"]
    assert "not attack" in fail_safe["capture_response"]
    assert "no violence, hacking, or retaliation" in fail_safe["corrupted_shipyard_handling"].lower()
    assert "This is not military" in fail_safe["non_military_framing"]
    assert "BUTTERFLY_LAWS_ARMED_PHASE" in fail_safe["phase_prerequisites"]
    assert "butterfly laws are not armed" in fail_safe["next_safe_move"]


def test_mutual_aid_module_economy_preserves_consent_and_private_boundary():
    payload = _build()
    economy = payload["fleet_mutual_aid_module_economy"]

    assert economy["captain_consent_required"] is True
    assert economy["contribution_receipts_required"] is True
    assert "No hidden extraction" in economy["private_boundary"]
    assert "private" in economy["shared_output_policy"]
    assert "declined" in economy["shared_output_policy"]


def test_shipyard_vs_ship_boundary_exists():
    payload = _build()
    boundary = payload["shipyard_vs_ship_boundary"]

    assert "app/workflow generators" in boundary["shipyard_internal_capabilities"]
    assert "Work Terrain and Build Cue" in boundary["shipyard_internal_capabilities"]
    assert "local ledger/receipt store" in boundary["winship_capabilities"]
    assert "protected evidence refs" in boundary["winship_capabilities"]
    assert "full Shipyard commissioning machinery" in boundary["forbidden_to_ship"]
    assert "not the whole Shipyard" in boundary["shipyard_ip_boundary"]


def test_builder_blockers_exist_and_fail_closed():
    payload = _build()
    blockers = payload["builder_blockers_by_id"]
    blocker_types = {blocker["blocker_type"] for blocker in blockers.values()}

    for expected in covenant.COVENANT_BLOCKER_TYPES:
        if expected != "UNKNOWN_FAIL_CLOSED":
            assert expected in blocker_types
    assert blockers["blocker_private_data_release_risk"]["blocker_type"] == "PRIVATE_DATA_RELEASE_RISK"
    assert blockers["blocker_premature_butterfly_trigger"]["blocker_type"] == "PREMATURE_BUTTERFLY_TRIGGER"
    assert blockers["blocker_harmful_work_accepted_for_money"]["blocker_type"] == (
        "HARMFUL_WORK_ACCEPTED_FOR_MONEY"
    )
    for blocker in blockers.values():
        assert blocker["fail_closed"] is True
        assert "ELIOPERATOR" in blocker["elioperator_warning"]


def test_required_examples_exist():
    payload = _build()
    examples = payload["examples"]

    for key in [
        "the_winchie",
        "normal_private_captain_mission",
        "fleet_backed_module",
        "high_margin_commercial_mission",
        "premature_butterfly_trigger",
        "capture_event_after_fleet_established",
        "founder_compromise",
        "corrupted_shipyard",
    ]:
        assert key in examples
    assert examples["the_winchie"]["butterfly_trigger_allowed"] is False
    assert examples["normal_private_captain_mission"]["judged_as_greed"] is False
    assert examples["fleet_backed_module"]["consent_required"] is True
    assert examples["corrupted_shipyard"]["attack_or_retaliation"] is False


def test_elioperator_report_exists_and_is_precise():
    payload = _build()
    report = payload["elioperator_report"]

    assert report["plain_summary"]
    assert "No open-source release." in report["what_this_does_not_do_yet"]
    assert "No license change." in report["what_this_does_not_do_yet"]
    assert "not a legal release mechanism" not in report["plain_summary"].lower()
    assert "The Winchie alone is not enough" in report["why_butterfly_laws_are_not_armed_yet"]
    assert "Money can fund useful capability" in report["why_commercial_operation_is_allowed"]


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


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "shipyard_sovereignty_covenant_contract.py",
            "scripts/export_shipyard_sovereignty_covenant_contract.py",
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
