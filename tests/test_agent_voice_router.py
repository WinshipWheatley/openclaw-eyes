import json
from pathlib import Path

import agent_voice_router as router


def test_st_annes_work_log_routes_to_cassandra():
    route = router.route_agent_voice(
        workflow_ref="st_annes_work_log_event",
        package_status="OPERATOR_REVIEW_REQUIRED",
        source_text="Mark that I'm at church running sound.",
    )

    assert route.speaker_ref == "cassandra"
    assert route.voice_mode == "operator_intake"
    assert route.audience == "internal_operator"


def test_capital_hilton_proposal_followup_routes_to_cassandra_internally():
    route = router.route_agent_voice(
        workflow_ref="capital_hilton_proposal_followup",
        package_status="OPERATOR_REVIEW_REQUIRED",
        source_text="Follow up on the Capital Hilton proposal.",
    )

    assert route.speaker_ref == "cassandra"
    assert route.voice_mode == "operator_calm"
    assert route.audience == "internal_operator"


def test_capital_hilton_provider_gate_routes_to_chief():
    route = router.route_agent_voice(
        workflow_ref="capital_hilton_invoice_operator_assist",
        package_status="PROVIDER_GATE_REQUIRED",
        source_text="Submit Capital Hilton invoice.",
    )

    assert route.speaker_ref == "chief"
    assert route.voice_mode == "diagnostic"
    assert route.audience == "internal_operator"


def test_submit_send_ledger_or_coupa_authority_routes_to_guardian():
    route = router.route_agent_voice(
        workflow_ref="capital_hilton_invoice_operator_assist",
        package_status="OPERATOR_REVIEW_REQUIRED",
        source_text="Submit Capital Hilton invoice.",
        authority_boundary={"coupa_submit_allowed": True},
    )

    assert route.speaker_ref == "guardian"
    assert route.voice_mode == "safety_gate"
    assert route.audience == "internal_operator"


def test_architecture_recommendation_routes_to_hermes():
    route = router.route_agent_voice(source_text="What should we build next for reusable lane sequencing?")

    assert route.speaker_ref == "hermes"
    assert route.voice_mode == "recommendation"


def test_music_art_or_studio_context_routes_to_niles():
    route = router.route_agent_voice(source_text="Review the Logic Pro session metadata and art direction.")

    assert route.speaker_ref == "niles"
    assert route.voice_mode == "recommendation"


def test_external_client_facing_draft_routes_to_clara_not_cassandra():
    route = router.route_agent_voice(
        workflow_ref="capital_hilton_proposal_followup",
        source_text="Prepare a client-facing proposal email draft.",
        audience="external_client",
        external_client_facing=True,
    )

    assert route.speaker_ref == "clara"
    assert route.voice_mode == "client_facing"
    assert route.audience == "external_client"


def test_contract_export_writes_json_and_wiki(tmp_path):
    result = router.export_agent_voice_routing(
        export_root=tmp_path / "read_models",
        wiki_path=tmp_path / "wiki" / "Agent Voice Routing.md",
        generated_at="2026-06-02T03:10:00+00:00",
    )

    read_model = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    assert read_model["status"] == router.CONTRACT_STATUS
    assert read_model["operator_response_voice_fields"] == list(router.OPERATOR_RESPONSE_VOICE_FIELDS)
    assert "routing_reason" in read_model["operator_response_voice_fields"]
    assert {item["speaker_ref"] for item in read_model["routed_examples"]} >= {
        "cassandra",
        "chief",
        "guardian",
        "hermes",
        "niles",
        "clara",
    }
    assert Path(result["wiki_path"]).exists()
    assert read_model["authority_boundary"]["email_send_allowed"] is False
