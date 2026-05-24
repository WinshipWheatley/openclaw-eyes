import json
import re
from pathlib import Path

import operator_question_assist_scope_expansion_contract as contract
from scripts.export_operator_question_assist_scope_expansion_contract import main as export_main


FIXED_NOW = "2026-05-24T12:00:00+00:00"


def _build() -> dict:
    return contract.build_operator_question_assist_scope_expansion_contract(generated_at=FIXED_NOW)


def _assists(payload: dict) -> dict:
    return payload["question_assists_by_id"]


def _paths(payload: dict) -> dict:
    return payload["workflow_paths_by_id"]


def _hints(payload: dict) -> dict:
    return payload["domain_familiarity_hints_by_id"]


def _missions(payload: dict) -> dict:
    return payload["scope_expansion_missions_by_id"]


def _behaviors(payload: dict) -> dict:
    return payload["agent_behaviors_by_id"]


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == contract.CONTRACT_STATUS
    assert first["north_star"] == "OpenClaw turns unfamiliar work into navigable missions."
    assert first["doctrine"]["systems_engineering_not_vibes"] is True
    assert first["doctrine"]["question_help_is_not_passive_tooltip"] is True
    assert first["doctrine"]["no_live_execution"] is True
    assert first["hard_rule"]["does_not_call_agents_or_models"] is True
    assert first["hard_rule"]["does_not_execute_tools"] is True
    assert first["hard_rule"]["does_not_write_receipts"] is True
    assert first["hard_rule"]["does_not_mutate_workflow_state"] is True
    assert first["hard_rule"]["may_grant_authority"] is False


def test_models_and_required_fields_exist():
    payload = _build()

    assert payload["machine_proof"]["operator_question_assist_model_present"] is True
    assert payload["machine_proof"]["operator_domain_familiarity_hint_model_present"] is True
    assert payload["machine_proof"]["operator_scope_expansion_mission_model_present"] is True
    assert payload["machine_proof"]["question_assist_workflow_path_model_present"] is True
    assert payload["machine_proof"]["agent_question_assist_behavior_model_present"] is True
    assert payload["operator_question_assist_schema"]["required_fields"] == list(contract.REQUIRED_QUESTION_ASSIST_FIELDS)
    assert payload["operator_domain_familiarity_hint_schema"]["required_fields"] == list(
        contract.REQUIRED_DOMAIN_HINT_FIELDS
    )
    assert payload["operator_scope_expansion_mission_schema"]["required_fields"] == list(
        contract.REQUIRED_SCOPE_MISSION_FIELDS
    )
    assert payload["question_assist_workflow_path_schema"]["required_fields"] == list(
        contract.REQUIRED_WORKFLOW_PATH_FIELDS
    )
    assert payload["agent_question_assist_behavior_schema"]["required_fields"] == list(
        contract.REQUIRED_AGENT_BEHAVIOR_FIELDS
    )
    assert set(payload["path_types"]) == set(contract.PATH_TYPES)
    assert set(payload["surfaces"]) == set(contract.SURFACES)


def test_capital_hilton_po_coupa_help_explains_terms_and_paths():
    payload = _build()
    assist = _assists(payload)["capital_hilton_po_coupa_question_assist"]

    terms = {item["term"]: item for item in assist["domain_terms"]}
    assert "PO" in terms
    assert terms["PO"]["precise_term"] == "purchase order"
    assert terms["PO"]["plain_explanation"]
    assert "Coupa" in terms
    assert "PO" in assist["plain_language_explanation"]
    assert "Coupa" in assist["plain_language_explanation"]
    assert "payment delay" in assist["why_this_matters"]
    assert "I do not know yet" in assist["valid_answer_types"]
    assert "Create PO/reference discovery path" in assist["if_you_dont_know_options"]
    assert "capital_hilton_create_po_guided_capture_path" in assist["guided_capture_options"]
    assert payload["machine_proof"]["capital_hilton_po_coupa_help_present"] is True


def test_rate_confirmation_help_separates_confirmation_from_external_proof():
    payload = _build()
    assist = _assists(payload)["capital_hilton_rate_confirmation_question_assist"]
    path = _paths(payload)["rate_proof_discovery_path"]

    assert "$400 per gig" in assist["question_text"]
    assert "operator confirmation is not the same as outside proof" in assist["why_this_matters"]
    assert "create rate proof discovery path" in assist["if_you_dont_know_options"]
    assert path["creates_discovery_substep"] is True
    assert path["creates_agent_packet_candidate"] is True
    assert payload["machine_proof"]["rate_confirmation_help_present"] is True


def test_legal_contract_help_has_no_legal_advice_authority():
    payload = _build()
    assist = _assists(payload)["legal_contract_domain_question_assist"]
    path = _paths(payload)["legal_guardian_review_path"]

    assert assist["world"] == "Legal/Guardian"
    assert "does not provide legal advice" in assist["plain_language_explanation"]
    assert "park for lawyer review" in assist["valid_answer_types"]
    assert path["path_type"] == "ESCALATE_TO_GUARDIAN"
    assert path["creates_block_draft_intent"] is True
    assert payload["authority_boundary"]["legal_advice_authority"] is False
    assert payload["machine_proof"]["legal_contract_help_present"] is True


def test_chief_build_troubleshooting_help_uses_signal_path_without_repair():
    payload = _build()
    assist = _assists(payload)["chief_build_troubleshooting_question_assist"]
    behavior = _behaviors(payload)["chief_build_question_behavior"]

    assert assist["question_text"] == "What is blocking the build?"
    assert "signal-path" in assist["plain_language_explanation"]
    assert "no shell or broad scan is granted" in assist["proof_or_evidence_needed"]
    assert "repair executed" in behavior["blocked_response_shapes"]
    assert "shell output from new command" in behavior["blocked_response_shapes"]
    assert payload["machine_proof"]["chief_build_troubleshooting_help_present"] is True


def test_new_workflow_scope_expansion_mission_exists():
    payload = _build()
    assist = _assists(payload)["monthly_client_recap_scope_question_assist"]
    mission = _missions(payload)["monthly_client_recap_scope_expansion_mission"]
    path = _paths(payload)["client_recap_scope_block_draft_path"]

    assert assist["question_text"] == "Can we set up a monthly client recap?"
    assert "This is a new mission" in assist["plain_language_explanation"]
    assert "client" in mission["mission_blocks"]
    assert "send approval" in mission["mission_blocks"]
    assert "approval bus before send" in mission["safety_gates"]
    assert path["creates_block_draft_intent"] is True
    assert payload["machine_proof"]["new_workflow_scope_expansion_present"] is True


def test_telegram_agent_help_is_not_passive_only():
    payload = _build()
    assist = _assists(payload)["telegram_po_meaning_question_assist"]
    behavior = _behaviors(payload)["cassandra_telegram_po_help_behavior"]
    path = _paths(payload)["telegram_find_po_path"]

    assert assist["question_text"] == "What does PO mean here?"
    assert {"Find PO", "Look in existing packets", "Ask AP/contact later", "Park this"} <= set(
        assist["valid_answer_types"]
    )
    assert "passive lecture only" in behavior["blocked_response_shapes"]
    assert path["creates_discovery_substep"] is True
    assert path["creates_agent_packet_candidate"] is True
    assert payload["machine_proof"]["telegram_agent_help_present"] is True


def test_help_paths_become_workflow_discovery_guided_capture_options():
    payload = _build()
    paths = list(payload["workflow_paths"])

    assert payload["question_assist_workflow_path_schema"]["help_paths_are_selectable_workflow_paths"] is True
    assert any(path["creates_discovery_substep"] for path in paths)
    assert any(path["creates_guided_capture_path"] for path in paths)
    assert any(path["creates_block_draft_intent"] for path in paths)
    assert any(path["creates_agent_packet_candidate"] for path in paths)
    assert payload["machine_proof"]["help_paths_become_workflow_options"] is True
    assert payload["machine_proof"]["guided_capture_option_present"] is True
    assert payload["machine_proof"]["discovery_option_present"] is True


def test_domain_familiarity_hint_is_compact_non_patronizing_and_on_demand():
    payload = _build()
    hint = _hints(payload)["winship_compact_domain_familiarity_hint"]

    assert "music production" in hint["strong_domains"]
    assert "finance/AP/Coupa" in hint["context_dependent_domains"]
    assert "studio signal-flow analogy" in hint["preferred_explanation_modes"]
    assert "do not patronize" in hint["support_style"]
    assert hint["include_by_default"] is True
    assert len(hint["compact_summary"]) <= 240
    assert hint["deeper_support_available"] is True
    assert "Request only when" in hint["deeper_support_trigger"]
    assert "not a personal dossier" in hint["privacy_boundary"]
    assert payload["machine_proof"]["domain_familiarity_hint_compact"] is True
    assert payload["machine_proof"]["deeper_support_packet_optional_on_demand"] is True


def test_agents_cannot_commit_truth_or_execute():
    payload = _build()

    for behavior in payload["agent_behaviors"]:
        assert "truth commit" in behavior["blocked_response_shapes"]
        assert any("execut" in item for item in behavior["blocked_response_shapes"])
        assert "choices" in " ".join(behavior["allowed_response_shapes"]) or "briefing" in " ".join(
            behavior["allowed_response_shapes"]
        )
    assert payload["agent_question_assist_behavior_schema"]["agents_do_not_commit_truth_or_execute_action"] is True
    assert payload["machine_proof"]["agents_cannot_commit_truth_or_execute"] is True


def test_all_authority_flags_false_and_no_private_bodies():
    payload = _build()

    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert payload["machine_proof"]["credentials_or_secrets_included"] is False
    assert payload["machine_proof"]["raw_private_bodies_included"] is False
    for value in payload["authority_boundary"].values():
        assert value is False
    for collection in ("question_assists", "workflow_paths"):
        for item in payload[collection]:
            for value in item["authority_boundary"].values():
                assert value is False


def test_relationships_to_existing_contracts_are_represented():
    payload = _build()

    expected = {
        "workflow_block_intent_live_draft_contract",
        "agent_execution_packet_compiler_contract",
        "agent_conversation_handoff_step_packet_contract",
        "bridge_routing_operator_attention_contract",
        "operator_solve_path_decision_node_contract",
        "guided_capture_protected_evidence_path_contract",
        "work_terrain_surface_map_build_cue_scout",
        "work_terrain_build_cue_reconciliation_queue",
    }
    assert expected <= set(payload["relationship_refs"])


def test_operator_markdown_contains_required_phrases():
    payload = _build()
    markdown = contract.format_operator_question_assist_markdown(payload)

    assert "OpenClaw turns unfamiliar work into navigable missions." in markdown
    assert "A calm ship that expands what the captain can responsibly attempt." in markdown
    assert "not just a tooltip" in markdown
    assert "no live authority" in markdown.lower()


def test_exporter_writes_json_and_operator_markdown(tmp_path):
    export_root = tmp_path / "read_models"
    result = contract.export_operator_question_assist_scope_expansion_contract(
        repo_root=Path.cwd(),
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    json_path = Path(result.json_path)
    operator_path = Path(result.operator_path)
    assert json_path.exists()
    assert operator_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == contract.SCHEMA_VERSION
    assert result.action_authority_granted is False


def test_script_main_summary_exports_default_read_model(capsys):
    assert export_main(["--format", "summary", "--generated-at", FIXED_NOW]) == 0
    out = capsys.readouterr().out

    assert f"schema_version={contract.SCHEMA_VERSION}" in out
    assert "question_assist_count=6" in out
    assert "action_authority_granted=false" in out
    payload = json.loads(Path("generated/read_models/operator_question_assist_scope_expansion_contract.json").read_text())
    assert payload["schema_version"] == contract.SCHEMA_VERSION


def test_no_raw_secret_like_values_in_payload():
    payload_text = contract.stable_json(_build())

    suspicious = re.compile(r"(AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|xox[baprs]-|AIza[0-9A-Za-z_-]{35})")
    assert suspicious.search(payload_text) is None
