import json
import re
from pathlib import Path

import worker_routing_intelligence as routing
from scripts.export_worker_routing_intelligence import main as export_main


FIXED_NOW = "2026-05-25T10:00:00+00:00"


def _build() -> dict:
    return routing.build_worker_routing_intelligence(generated_at=FIXED_NOW)


def test_required_models_exist_and_payload_is_deterministic():
    first = _build()
    second = _build()

    assert routing.stable_json(first) == routing.stable_json(second)
    assert first["schema_version"] == routing.SCHEMA_VERSION
    assert first["read_model_id"] == routing.READ_MODEL_ID
    proof = first["machine_proof"]
    assert proof["worker_routing_intelligence_model_present"] is True
    assert proof["worker_route_decision_model_present"] is True
    assert proof["worker_routing_rule_model_present"] is True
    assert proof["worker_package_recommendation_model_present"] is True
    assert proof["worker_routing_blocker_model_present"] is True


def test_required_field_lists_exist():
    payload = _build()
    schemas = payload["model_schemas"]

    assert schemas["worker_routing_intelligence"]["required_fields"] == list(routing.REQUIRED_INTELLIGENCE_FIELDS)
    assert schemas["worker_route_decision"]["required_fields"] == list(routing.REQUIRED_DECISION_FIELDS)
    assert schemas["worker_routing_rule"]["required_fields"] == list(routing.REQUIRED_RULE_FIELDS)
    assert schemas["worker_package_recommendation"]["required_fields"] == list(routing.REQUIRED_RECOMMENDATION_FIELDS)
    assert schemas["worker_routing_blocker"]["required_fields"] == list(routing.REQUIRED_BLOCKER_FIELDS)


def test_supported_workers_and_machines_exist():
    payload = _build()

    assert payload["machine_proof"]["supported_workers_present"] is True
    assert payload["machine_proof"]["machines_present"] is True
    for worker in ["MAC_CODEX", "PC_CODEX", "GEMINI_AGY", "LOCAL_OLLAMA", "GUARDIAN", "CASSANDRA", "UNKNOWN_NEEDS_ROUTING"]:
        assert worker in payload["supported_workers"]
    for machine in ["MAC", "PC_WSL", "LOCAL_ONLY", "EXTERNAL_MODEL", "UNKNOWN"]:
        assert machine in payload["machines"]


def test_mac_codex_ui_example_routes_correctly():
    payload = _build()
    decision = payload["examples"]["mac_codex_ui"]["route_decision"]
    recommendation = payload["examples"]["mac_codex_ui"]["package_recommendation"]

    assert payload["machine_proof"]["mac_codex_ui_routes_correctly"] is True
    assert decision["selected_worker_type"] == "MAC_CODEX"
    assert decision["selected_machine"] == "MAC"
    assert decision["task_type"] == "SWIFTUI_APP_UI"
    assert decision["confidence"] == "HIGH"
    assert recommendation["package_type"] == "MAC_WORKER_PACKAGE"
    assert "Mac app surface" in recommendation["context_needed"]


def test_mac_codex_apple_app_integration_routes_correctly():
    payload = _build()
    example = payload["examples"]["mac_codex_apple_app_integration"]
    decision = example["route_decision"]
    rule = payload["worker_routing_rules_by_id"]["rule_mac_codex_mac_app"]

    assert payload["machine_proof"]["apple_app_integration_routes_correctly"] is True
    assert decision["selected_worker_type"] == "MAC_CODEX"
    assert decision["selected_machine"] == "MAC"
    assert decision["task_type"] == "APPLE_APP_INTEGRATION_SCOUT_OR_UI"
    assert "DAW/media-app mutation without explicit approval/backup/receipt posture" in rule["forbidden_actions"]


def test_mac_codex_mail_boundary_blocks_send():
    payload = _build()
    example = payload["examples"]["mac_codex_mail_boundary"]
    decision = example["route_decision"]

    assert payload["machine_proof"]["mac_mail_boundary_blocks_send"] is True
    assert decision["selected_worker_type"] == "MAC_CODEX"
    assert decision["task_type"] == "MAC_MAIL_BOUNDARY_REVIEW"
    assert "AUTHORITY_TOO_BROAD" in example["active_blockers"]
    assert "EXTERNAL_ACTION_INCLUDED" in example["active_blockers"]
    assert "live send/submit" in payload["worker_routing_rules_by_id"]["rule_mac_codex_mac_app"]["forbidden_actions"]


def test_pc_codex_backend_example_routes_correctly():
    payload = _build()
    decision = payload["examples"]["pc_codex_backend"]["route_decision"]
    recommendation = payload["examples"]["pc_codex_backend"]["package_recommendation"]

    assert payload["machine_proof"]["pc_codex_backend_routes_correctly"] is True
    assert decision["selected_worker_type"] == "PC_CODEX"
    assert decision["selected_machine"] == "PC_WSL"
    assert decision["task_type"] == "BACKEND_READMODEL"
    assert recommendation["package_type"] == "PC_WORKER_PACKAGE"
    assert "Repo A file scope" in recommendation["context_needed"]


def test_pc_codex_package_example_routes_correctly():
    payload = _build()
    decision = payload["examples"]["pc_codex_package"]["route_decision"]

    assert payload["machine_proof"]["pc_codex_package_routes_correctly"] is True
    assert decision["selected_worker_type"] == "PC_CODEX"
    assert decision["selected_machine"] == "PC_WSL"
    assert decision["task_type"] == "SHUTTLE_PACKAGE"
    assert "package/shuttle generation" in payload["worker_routing_rules_by_id"]["rule_pc_codex_repo_a_backend"]["allowed_actions"]


def test_gemini_agy_example_routes_correctly():
    payload = _build()
    decision = payload["examples"]["gemini_agy_audit"]["route_decision"]
    recommendation = payload["examples"]["gemini_agy_audit"]["package_recommendation"]

    assert payload["machine_proof"]["gemini_agy_routes_correctly"] is True
    assert decision["selected_worker_type"] == "GEMINI_AGY"
    assert decision["selected_machine"] == "EXTERNAL_MODEL"
    assert decision["task_type"] == "READ_ONLY_AUDIT"
    assert recommendation["package_type"] == "READ_ONLY_SCOUT_PACKAGE"
    assert "file edits" in payload["worker_routing_rules_by_id"]["rule_gemini_agy_read_only_scout"]["forbidden_actions"]


def test_unknown_request_routes_to_clarification():
    payload = _build()
    example = payload["examples"]["unknown_make_it_better"]
    decision = example["route_decision"]

    assert payload["machine_proof"]["unknown_routes_to_clarification"] is True
    assert decision["selected_worker_type"] == "UNKNOWN_NEEDS_ROUTING"
    assert decision["selected_machine"] == "UNKNOWN"
    assert decision["task_type"] == "UNKNOWN_NEEDS_FRAMING"
    assert "AMBIGUOUS_REQUEST" in example["active_blockers"]
    assert decision["package_required"] is False


def test_wrong_worker_blocker_exists():
    payload = _build()
    example = payload["examples"]["wrong_worker_blocker"]

    assert payload["machine_proof"]["wrong_worker_blocker_exists"] is True
    assert example["attempted_worker_type"] == "PC_CODEX"
    assert example["expected_worker_type"] == "MAC_CODEX"
    assert "WRONG_WORKER_SELECTED" in example["active_blockers"]
    assert "WRONG_MACHINE_SELECTED" in example["active_blockers"]


def test_authority_too_broad_blocker_exists():
    payload = _build()
    example = payload["examples"]["authority_too_broad_blocker"]
    decision = example["route_decision"]

    assert payload["machine_proof"]["authority_too_broad_blocker_exists"] is True
    assert decision["selected_worker_type"] == "MAC_CODEX"
    assert "AUTHORITY_TOO_BROAD" in example["active_blockers"]
    assert "EXTERNAL_ACTION_INCLUDED" in example["active_blockers"]
    assert "Strip that authority" in example["elioperator_warning"]


def test_blockers_exist_and_fail_closed():
    payload = _build()
    blockers = payload["worker_routing_blockers_by_id"]
    blocker_types = {blocker["blocker_type"] for blocker in blockers.values()}

    assert payload["machine_proof"]["blockers_present"] is True
    for expected in routing.BLOCKER_TYPES:
        assert expected in blocker_types
    assert blockers["worker_routing_blocker_wrong_worker_selected"]["fail_closed"] is True
    assert blockers["worker_routing_blocker_unknown_fail_closed"]["severity"] == "CRITICAL"


def test_direct_route_request_function_handles_current_need_examples():
    mac = routing.route_request("Import this Mac readback package")
    pc = routing.route_request("Consume this Mac request and generate the PC-to-Mac package")
    gemini = routing.route_request("What should Codex do next?")

    assert mac.selected_worker_type == "MAC_CODEX"
    assert mac.task_type == "MAC_PACKAGE_IMPORT_RENDER"
    assert pc.selected_worker_type == "PC_CODEX"
    assert pc.task_type == "SHUTTLE_PACKAGE"
    assert gemini.selected_worker_type == "GEMINI_AGY"
    assert gemini.task_type == "READ_ONLY_AUDIT"


def test_all_live_authority_false_and_no_external_action():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    assert payload["machine_proof"]["external_action_performed"] is False
    assert payload["machine_proof"]["auto_dispatch_performed"] is False
    assert payload["machine_proof"]["worker_execution_performed"] is False
    for key, value in payload["authority_boundary"].items():
        assert value is False, key


def test_export_writes_parseable_outputs(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))

    assert summary["mac_codex_ui_routes_correctly"] is True
    assert summary["pc_codex_backend_routes_correctly"] is True
    assert summary["gemini_agy_routes_correctly"] is True
    assert data["machine_proof"]["all_live_authority_flags_false"] is True
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


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
    assert data["machine_proof"]["raw_pii_in_packages"] is False
    assert "@" not in combined
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "credential material" not in combined.lower()
    assert "private key" not in combined.lower()
    assert "raw email body:" not in combined.lower()


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "worker_routing_intelligence.py",
            "scripts/export_worker_routing_intelligence.py",
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
