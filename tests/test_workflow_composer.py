import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import workflow_composer as composer


FIXED_NOW = "2026-06-03T22:30:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
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
    _write_json(root / "track_b_governance_memory_cutover_status.json", {"status": "TRACK_B_GOVERNANCE_MEMORY_CUTOVER_READY"})
    _write_json(root / "chief_build_backlog.json", {"status": "CHIEF_BUILD_BACKLOG_READY"})
    _write_json(root / "agent_handoff_registry.json", {"status": "AGENT_HANDOFF_REGISTRY_READY"})
    _write_json(root / "worker_package_staging_status.json", {"status": "WORKER_PACKAGE_STAGING_READY"})
    return root


def _blocked_actions(plan: dict) -> set[str]:
    blocked: set[str] = set()
    for step in plan["steps"]:
        blocked.update(step["blocked_actions"])
    for gate in plan["guardian_gates"]:
        blocked.update(gate["blocked_actions"])
        blocked.add(gate["protected_action"])
    return blocked


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def test_st_annes_invoice_workflow_blocks_excel_and_send_gates():
    plan = composer.build_workflow_plan(
        operator_goal="Get St. Anne's monthly invoice workflow ready.",
        desired_outcome="Ready for operator review.",
        privacy_class="client_finance",
        generated_at=FIXED_NOW,
    )

    assert plan["safe_to_stage"] is True
    assert plan["safe_to_execute"] is False
    assert len(plan["steps"]) >= 4
    assert plan["work_in_progress_risk"] == "medium"

    blocked = _blocked_actions(plan)
    assert "send_email" in blocked
    assert "mutate_workbook" in blocked
    assert "run_excel_automation" in blocked
    assert "export_pdf" in blocked
    assert any(gate["protected_action"] == "send_email" for gate in plan["guardian_gates"])
    assert any(gate["protected_action"] == "mutate_workbook" for gate in plan["guardian_gates"])


def test_helm_ux_routes_hermes_chief_mac_codex_without_execution():
    plan = composer.build_workflow_plan(
        operator_goal="Improve Helm so it feels less noisy.",
        desired_outcome="A Mac UI packet preview.",
        privacy_class="internal_system",
        generated_at=FIXED_NOW,
    )

    owners = [step["owner"] for step in plan["steps"]]
    assert owners == ["hermes", "chief", "mac_codex"]
    assert plan["steps"][2]["package_type"] == "mac_codex_helm_ui_worker_packet_preview"
    assert "MAC_CODEX" in plan["speaker_summary"]["chief"]
    assert plan["safe_to_execute"] is False
    assert plan["machine_proof"]["worker_spawn_performed"] is False
    assert plan["machine_proof"]["worker_execution_performed"] is False
    blocked = _blocked_actions(plan)
    assert "run_worker" in blocked
    assert "push_git" in blocked


def test_capital_hilton_proposal_routes_cassandra_clara_and_blocks_send():
    plan = composer.build_workflow_plan(
        operator_goal="Follow up on Capital Hilton proposal.",
        desired_outcome="Proposal follow-up for internal review.",
        privacy_class="client_business_development",
        generated_at=FIXED_NOW,
    )

    assert "cassandra" in [step["owner"] for step in plan["steps"]]
    assert any("Clara" in step["plain_summary"] for step in plan["steps"])
    assert any("cassandra_clara" in step["package_type"] for step in plan["steps"])
    assert plan["safe_to_execute"] is False
    blocked = _blocked_actions(plan)
    assert "send_email" in blocked
    assert "open_gmail" in blocked
    assert "perform_business_action" in blocked


def test_sleep_question_blocks_send_coupa_ledger_workbook_and_workers():
    plan = composer.build_workflow_plan(
        operator_goal="Can this run while I sleep?",
        desired_outcome="Know what is safe unattended.",
        urgency="overnight",
        privacy_class="mixed",
        generated_at=FIXED_NOW,
    )

    assert plan["work_in_progress_risk"] == "high"
    assert plan["safe_to_execute"] is False
    assert "unattended" in plan["speaker_summary"]["cassandra"].lower()
    blocked = _blocked_actions(plan)
    for action in {
        "send_email",
        "open_coupa",
        "mutate_ledger",
        "mutate_workbook",
        "run_worker",
        "run_child_agent",
        "launch_agent_loop",
        "call_external_llm",
    }:
        assert action in blocked


def test_no_unsafe_authority_grants_across_contract_and_examples(tmp_path):
    contract = composer.build_contract_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)
    latest = composer.build_latest_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    unsafe_keys = composer.UNSAFE_TRUE_KEYS
    for payload in (contract, latest):
        assert not [key for key, value in _walk_values(payload) if key in unsafe_keys and value is True]
        assert composer.unsafe_true_grants(payload) == []

    assert latest["status"] == composer.READY_STATUS
    assert latest["machine_proof"]["all_example_plans_safe_to_execute_false"] is True
    assert latest["machine_proof"]["no_worker_spawn_or_execution"] is True
    for plan in latest["example_plans"]:
        assert plan["safe_to_execute"] is False
        assert plan["machine_proof"]["unsafe_true_grants_absent"] is True
        assert plan["likely_bottlenecks"]


def test_json_parse_local_and_bridge(tmp_path):
    result = composer.export_workflow_composer(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Workflow Composer.md",
        generated_at=FIXED_NOW,
    )

    contract = json.loads(Path(result["contract_path"]).read_text(encoding="utf-8"))
    latest = json.loads(Path(result["latest_path"]).read_text(encoding="utf-8"))
    bridge_contract = json.loads(Path(result["bridge_contract_path"]).read_text(encoding="utf-8"))
    bridge_latest = json.loads(Path(result["bridge_latest_path"]).read_text(encoding="utf-8"))

    assert contract == bridge_contract
    assert latest == bridge_latest
    assert contract["status"] == composer.READY_STATUS
    assert latest["status"] == composer.READY_STATUS
    assert latest["example_plan_count"] == 5
    assert Path(result["wiki_path"]).exists()
