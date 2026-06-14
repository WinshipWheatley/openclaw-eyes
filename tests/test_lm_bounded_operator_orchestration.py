import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lm_bounded_operator_orchestration as orchestration


FIXED_NOW = "2026-06-04T01:10:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_boundary(**overrides):
    boundary = dict(orchestration.AUTHORITY_BOUNDARY)
    boundary.update(overrides)
    return boundary


def _action(
    action_id: str,
    *,
    label: str,
    action_type: str = "navigate",
    target_world_ref: str = "system",
    target_thread_ref: str = "operator",
    enabled: bool = True,
    business_action: bool = False,
    payload: dict | None = None,
    authority_boundary: dict | None = None,
) -> dict:
    return {
        "action_id": action_id,
        "action_type": action_type,
        "authority_boundary": authority_boundary or _safe_boundary(),
        "business_action": business_action,
        "disabled_reason": None if enabled else "Disabled in fixture.",
        "enabled": enabled,
        "label": label,
        "payload": payload or {},
        "proof_refs": [f"generated/read_models/{action_id}.json"],
        "safe_to_render_button": True,
        "target_thread_ref": target_thread_ref,
        "target_world_ref": target_world_ref,
    }


def _packet(packet_id: str, *, completed: bool = False, informational: bool = False) -> dict:
    status = "REVIEW_PACKET_READY"
    if completed:
        status = "OPERATOR_REVIEW_RECORDED"
    if informational:
        status = "INFORMATIONAL_REVIEW_CLOSED"
    return {
        "review_packet_id": packet_id,
        "channel_ref": "build_openclaw_backend",
        "status": status,
        "completed": completed,
        "operator_decision_required": not completed and not informational,
    }


def _fixture_root(
    tmp_path: Path,
    *,
    actions: list[dict] | None = None,
    packets: list[dict] | None = None,
    invoice_overrides: dict | None = None,
) -> Path:
    root = tmp_path / "generated" / "read_models"
    default_actions = [
        _action(
            "capital_hilton.payment.open_finance",
            label="Open Finance / Capital Hilton",
            target_world_ref="finance",
            target_thread_ref="capital_hilton",
            payload={"payload_ref": "generated/read_models/capital_hilton_invoice_operator_run_status.json"},
        ),
        _action(
            "capital_hilton.payment.record_proof",
            label="Record payment proof",
            action_type="record_payment_proof_intake",
            target_world_ref="finance",
            target_thread_ref="capital_hilton",
            enabled=False,
            payload={"requires_payment_evidence": True, "ledger_mutation_allowed": False},
        ),
        _action(
            "capital_hilton.proposal.stage_followup",
            label="Stage proposal follow-up",
            action_type="stage_package_request",
            target_world_ref="business_development",
            target_thread_ref="capital_hilton",
            payload={
                "requested_mode": "dry_run_package_only",
                "target_agent_refs": ["cassandra", "clara"],
                "email_send_allowed": False,
            },
        ),
        _action(
            "chief_diagnostic.open",
            label="Open Chief diagnostic",
            target_world_ref="system",
            target_thread_ref="chief_diagnostic",
            payload={"repair_authority": False, "no_repair_authority": True},
        ),
        _action(
            "client_invoice_workbook.register",
            label="Register workbook",
            action_type="workbook_registration",
            target_world_ref="finance",
            target_thread_ref="capital_hilton",
            payload={
                "request_type": "WORKBOOK_REGISTRATION_REQUEST_V0",
                "workbook_body_read_allowed": False,
                "spreadsheet_cell_read_allowed": False,
                "no_workbook_mutation": True,
            },
        ),
        _action(
            "helm_question.safe_next.ask",
            label="What is safe next?",
            action_type="system_question",
            target_world_ref="system",
            target_thread_ref="guardian",
        ),
        _action(
            "helm_question.hardwired_vs_spawned.ask",
            label="What is the difference between Chief and a spawned worker?",
            action_type="system_question",
            target_world_ref="system",
            target_thread_ref="architecture",
        ),
        _action(
            "review_packet.review_packet_unresolved.open",
            label="Open review packet",
            target_world_ref="build",
            target_thread_ref="build_openclaw_backend",
        ),
        _action(
            "review_packet.review_packet_resolved.open",
            label="Open review packet",
            target_world_ref="build",
            target_thread_ref="build_openclaw_backend",
        ),
    ]
    _write_json(
        root / "operator_action_payloads.json",
        {
            "status": "OPERATOR_ACTION_PAYLOADS_READY",
            "action_payloads": actions if actions is not None else default_actions,
        },
    )
    _write_json(root / "workflow_composer_latest.json", {"status": "WORKFLOW_COMPOSER_READY"})
    _write_json(root / "harness_provider_selection_registry.json", {"status": "HARNESS_PROVIDER_SELECTION_READY"})
    _write_json(
        root / "evidence_confidence_scoring.json",
        {
            "status": "EVIDENCE_CONFIDENCE_SCORING_READY",
            "facts": [
                {
                    "fact_ref": "fact:capital_hilton_invoice_processing",
                    "confidence_score": 0.75,
                }
            ],
        },
    )
    _write_json(root / "gate_decision_ledger.json", {"status": "GATE_DECISION_LEDGER_READY"})
    _write_json(
        root / "track_a_workroom_backbone_status.json",
        {
            "status": "TRACK_A_WORKROOM_BACKBONE_READY",
            "phases": [
                {
                    "phase": "operator_next_decision_workrooms",
                    "status": "OPERATOR_NEXT_DECISION_WORKROOMS_READY",
                }
            ],
        },
    )
    invoice = {
        "status": "CAPITAL_HILTON_OPERATOR_RUN_RECORDED",
        "coupa_submitted": True,
        "coupa_submission_recorded": True,
        "coupa_submission_status": "processing",
        "coupa_status_observed": "Processing",
        "payment_received_recorded": False,
        "paid": False,
        "ledger_mutation_performed": False,
    }
    invoice.update(invoice_overrides or {})
    _write_json(root / "capital_hilton_invoice_operator_run_status.json", invoice)
    _write_json(
        root / "capital_hilton_business_development_proposal.json",
        {
            "client_ref": "capital_hilton",
            "client_review_pending": True,
            "email_send_allowed": False,
            "finance_handoff_allowed": False,
            "paid": False,
        },
    )
    _write_json(root / "operator_next_decision.json", {"status": "READY"})
    _write_json(root / "workroom_wip_limits.json", {"status": "WORKROOM_WIP_LIMITS_READY"})
    _write_json(root / "openclaw_operating_picture_latest.json", {"status": "OPENCLAW_OPERATING_PICTURE_READY"})
    _write_json(
        root / "workroom_review_packet_index.json",
        {
            "status": "WORKROOM_REVIEW_PACKET_INDEX_READY",
            "packets": packets if packets is not None else [_packet("review_packet:unresolved")],
        },
    )
    return root


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def test_capital_hilton_submitted_state_rejects_start_coupa_proof_step(tmp_path):
    payload = orchestration.build_orchestration(
        read_model_root=_fixture_root(tmp_path),
        scenario_ref="capital_hilton_payment_watch",
        generated_at=FIXED_NOW,
    )

    rejected = {row["action_id"]: row for row in payload["rejected_actions"]}

    assert "capital_hilton.coupa.start_proof_step" in rejected
    assert rejected["capital_hilton.coupa.start_proof_step"]["rejection_reason"] == (
        "contradicts_submitted_processing_receipt"
    )


def test_capital_hilton_payment_watch_recommended(tmp_path):
    payload = orchestration.build_latest_read_model(
        read_model_root=_fixture_root(tmp_path),
        generated_at=FIXED_NOW,
    )

    assert payload["status"] == "READY"
    assert payload["readiness_status"] == orchestration.READY_STATUS
    assert payload["lm_recommended_action"]["action_id"] == "capital_hilton.payment.open_finance"
    assert payload["lm_recommended_action"]["label"] == "Open Finance / Capital Hilton"
    assert payload["operator_display"]["human_copy"] == orchestration.CAPITAL_HILTON_HUMAN_COPY


def test_lm_selected_action_must_exist_in_operator_action_payloads(tmp_path):
    root = _fixture_root(tmp_path)
    payload = orchestration.build_latest_read_model(read_model_root=root, generated_at=FIXED_NOW)
    action_payloads = json.loads((root / "operator_action_payloads.json").read_text(encoding="utf-8"))
    action_ids = {action["action_id"] for action in action_payloads["action_payloads"]}

    assert payload["lm_recommended_action"]["action_id"] in action_ids
    assert payload["deterministic_validation"]["selected_action_exists_in_payloads"] is True
    assert payload["deterministic_validation"]["selected_action_allowed"] is True


def test_lm_cannot_introduce_new_business_action(tmp_path):
    root = _fixture_root(tmp_path)
    action_payloads = json.loads((root / "operator_action_payloads.json").read_text(encoding="utf-8"))[
        "action_payloads"
    ]

    unknown = orchestration.validate_lm_recommendation(
        {"action_id": "capital_hilton.send_email_now"},
        action_payloads,
    )
    unsafe_existing = orchestration.validate_lm_recommendation(
        {"action_id": "unsafe.business.action"},
        [
            *action_payloads,
            _action(
                "unsafe.business.action",
                label="Unsafe business action",
                business_action=True,
                authority_boundary=_safe_boundary(business_action_allowed=True),
            ),
        ],
    )

    assert unknown["valid"] is False
    assert unknown["new_business_action_introduced"] is True
    assert "unknown_action_payload" in unknown["reject_reasons"]
    assert unsafe_existing["valid"] is False
    assert "business_action_not_allowed" in unsafe_existing["reject_reasons"]
    assert "unsafe_authority_true" in unsafe_existing["reject_reasons"]


def test_resolved_review_packet_not_recommended(tmp_path):
    root = _fixture_root(
        tmp_path,
        packets=[_packet("review_packet:resolved", completed=True)],
    )

    payload = orchestration.build_orchestration(
        read_model_root=root,
        scenario_ref="workroom_review",
        target_review_packet_id="review_packet:resolved",
        generated_at=FIXED_NOW,
    )

    assert payload["lm_recommended_action"]["action_id"] != "review_packet.review_packet_resolved.open"
    assert payload["lm_recommended_action"]["action_id"] == "helm_question.safe_next.ask"
    rejected = {row["action_id"]: row for row in payload["rejected_actions"]}
    assert rejected["review_packet.review_packet_resolved.open"]["rejection_reason"] == (
        "resolved_or_closed_review_packet"
    )


def test_check_engine_route_does_not_repair(tmp_path):
    payload = orchestration.build_orchestration(
        read_model_root=_fixture_root(tmp_path),
        scenario_ref="check_engine_diagnostic",
        generated_at=FIXED_NOW,
    )
    action = payload["lm_recommended_action"]

    assert action["action_id"] == "chief_diagnostic.open"
    assert action["action_payload"]["payload"]["repair_authority"] is False
    assert action["action_payload"]["payload"]["no_repair_authority"] is True
    assert payload["machine_proof"]["repair_performed"] is False


def test_business_development_followup_has_no_send_authority(tmp_path):
    payload = orchestration.build_orchestration(
        read_model_root=_fixture_root(tmp_path),
        scenario_ref="business_development_followup",
        generated_at=FIXED_NOW,
    )
    action = payload["lm_recommended_action"]

    assert action["action_id"] == "capital_hilton.proposal.stage_followup"
    assert action["action_payload"]["payload"]["requested_mode"] == "dry_run_package_only"
    assert action["action_payload"]["payload"]["email_send_allowed"] is False
    assert action["action_payload"]["authority_boundary"]["email_send_allowed"] is False
    assert payload["machine_proof"]["email_send_performed"] is False


def test_workbook_registration_does_not_read_workbook_body(tmp_path):
    payload = orchestration.build_orchestration(
        read_model_root=_fixture_root(tmp_path),
        scenario_ref="workbook_registration",
        generated_at=FIXED_NOW,
    )
    action = payload["lm_recommended_action"]

    assert action["action_id"] == "client_invoice_workbook.register"
    assert action["action_payload"]["payload"]["workbook_body_read_allowed"] is False
    assert action["action_payload"]["payload"]["spreadsheet_cell_read_allowed"] is False
    assert action["action_payload"]["payload"]["no_workbook_mutation"] is True
    assert payload["machine_proof"]["workbook_body_read_performed"] is False
    assert payload["machine_proof"]["spreadsheet_cell_read_performed"] is False


def test_unsafe_true_grant_scan_clean(tmp_path):
    payload = orchestration.build_latest_read_model(
        read_model_root=_fixture_root(tmp_path),
        generated_at=FIXED_NOW,
    )

    assert orchestration.unsafe_true_grants(payload) == []
    assert not [
        key
        for key, value in _walk_values(payload)
        if key in orchestration.UNSAFE_TRUE_KEYS and value is True
    ]
    assert payload["machine_proof"]["model_invoked"] is False
    assert payload["machine_proof"]["external_provider_connected"] is False
    assert payload["machine_proof"]["worker_spawn_performed"] is False


def test_export_json_parse_local_and_bridge(tmp_path):
    result = orchestration.export_lm_bounded_operator_orchestration(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "LM Bounded Operator Orchestration.md",
        generated_at=FIXED_NOW,
    )

    contract = json.loads(Path(result["contract_path"]).read_text(encoding="utf-8"))
    latest = json.loads(Path(result["latest_path"]).read_text(encoding="utf-8"))
    bridge_contract = json.loads(Path(result["bridge_contract_path"]).read_text(encoding="utf-8"))
    bridge_latest = json.loads(Path(result["bridge_latest_path"]).read_text(encoding="utf-8"))

    assert contract == bridge_contract
    assert latest == bridge_latest
    assert latest["status"] == "READY"
    assert latest["readiness_status"] == orchestration.READY_STATUS
    assert Path(result["wiki_path"]).exists()
