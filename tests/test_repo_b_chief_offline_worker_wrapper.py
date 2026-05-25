import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import repo_b_chief_offline_worker_wrapper as wrapper
from scripts.export_repo_b_chief_offline_worker_wrapper import main as export_main
from scripts.run_repo_b_chief_offline_worker_wrapper import main as run_main


FIXED_NOW = "2026-05-25T23:30:00+00:00"


def _payload() -> dict:
    return wrapper.build_payload(generated_at=FIXED_NOW)


def test_required_models_exist():
    for name in [
        "RepoBChiefWorkerDecision",
        "ChiefOfflineCapability",
        "ChiefOfflineWorkerRequest",
        "ChiefOfflineWorkerReadback",
        "ChiefOfflineWorkerBlocker",
    ]:
        assert hasattr(wrapper, name)


def test_chief_components_classified():
    payload = _payload()
    decisions = {row["source_module"]: row for row in payload["chief_worker_decisions"]}

    assert decisions["chief_router.py"]["recommended_posture"] == "REBUILD_SMALL_SUBSET_IN_REPO_A"
    assert "local LLM fallback" in decisions["chief_router.py"]["blocked_items"]
    assert decisions["chief_listener.py"]["recommended_posture"] == "UNSAFE_DO_NOT_CONNECT"
    assert "live Telegram listener" in decisions["chief_listener.py"]["blocked_items"]
    assert decisions["chief_session_manager.py"]["recommended_posture"] == "PROMOTE_SELECTED_MODULE"
    assert decisions["chief_queue_brain.py"]["recommended_posture"] == "READBACK_ONLY"
    assert decisions["chief_reporter_brain.py"]["recommended_posture"] == "READBACK_ONLY"
    assert decisions["chief_validator_brain.py"]["recommended_posture"] == "PROMOTE_SELECTED_MODULE"
    assert decisions["chief_watcher_brain.py"]["recommended_posture"] == "REFERENCE_ONLY"
    assert decisions["chief_approval_policy.py"]["recommended_posture"] == "PROMOTE_SELECTED_MODULE"
    assert decisions["queue_balancer.py"]["recommended_posture"] == "REBUILD_SMALL_SUBSET_IN_REPO_A"
    assert decisions["runner_registry.py"]["recommended_posture"] == "REFERENCE_ONLY"
    assert decisions["queue_validator.py"]["recommended_posture"] == "COMPUTE_ONLY"
    assert decisions["chief_worker.py / chief_state_worker.py / chief_memory_worker.py"]["recommended_posture"] == "UNSAFE_DO_NOT_CONNECT"


def test_offline_capabilities_are_safe_and_cover_required_types():
    payload = _payload()
    capability_types = {row["capability_type"] for row in payload["offline_capabilities"]}

    for required in [
        "TASK_CLASSIFICATION",
        "ROUTE_SUGGESTION",
        "QUEUE_STATUS_SUMMARY",
        "WORK_PACKET_SHAPING",
        "NEXT_SAFE_MOVE",
        "BUILD_NOW_VS_HOLD",
        "DIAGNOSTIC_SUMMARY",
        "OPERATOR_BRIEFING",
        "WORKER_RECOMMENDATION",
        "MISSING_INFO_DETECTION",
    ]:
        assert required in capability_types

    for capability in payload["offline_capabilities"]:
        assert capability["deterministic"] is True
        assert capability["external_authority"] is False
        assert capability["queue_mutation_required"] is False
        assert capability["raw_private_data_required"] is False
        assert capability["wrapper_allowed"] is True


def test_route_suggestion_example_exists_and_does_not_dispatch():
    example = _payload()["examples"]["route_suggestion"]

    assert example["request"]["requested_capability"] == "ROUTE_SUGGESTION"
    assert example["readback"]["status"] == "FIXTURE_READBACK_READY"
    assert "live dispatch" in example["readback"]["blocked_actions"]
    assert "worker execution" in example["readback"]["blocked_actions"]
    assert "queue mutation" in example["readback"]["blocked_actions"]


def test_queue_status_example_is_readback_only():
    example = _payload()["examples"]["queue_status_summary"]

    assert example["request"]["requested_capability"] == "QUEUE_STATUS_SUMMARY"
    assert example["readback"]["candidate_route"] == "queue_status_readback_only"
    assert "queue mutation" in example["readback"]["blocked_actions"]
    assert "live queue read" in example["readback"]["blocked_actions"]
    assert "fixture/status-shape readback" in example["readback"]["warnings"][0]


def test_work_packet_shaping_example_exists():
    example = _payload()["examples"]["work_packet_shaping"]

    assert example["request"]["requested_capability"] == "WORK_PACKET_SHAPING"
    assert example["readback"]["candidate_route"] == "scoped_context_package_compiler"
    assert "auto task creation" in example["readback"]["blocked_actions"]
    assert any("Repo A package compiler remains authority" in warning for warning in example["readback"]["warnings"])


def test_build_now_vs_hold_example_exists():
    example = _payload()["examples"]["build_now_vs_hold"]

    assert example["request"]["requested_capability"] == "BUILD_NOW_VS_HOLD"
    assert "Build now if bounded and reversible" in example["readback"]["candidate_next_safe_move"]
    assert "autonomous task creation" in example["readback"]["blocked_actions"]


def test_capital_hilton_routing_example_exists():
    example = _payload()["examples"]["capital_hilton_routing"]

    assert example["request"]["folder_ref"] == "finance/capital_hilton/invoices"
    assert example["readback"]["candidate_route"] == "workflow_execution_package_compiler / finance lane"
    assert example["readback"]["candidate_worker"] == "PC_CODEX"
    assert "exact Coupa PO/reference" in example["readback"]["missing_inputs"]
    assert "email send" in example["readback"]["blocked_actions"]
    assert "Coupa access/submit" in example["readback"]["blocked_actions"]


def test_telegram_output_live_dispatch_queue_and_watchdog_blockers_exist():
    payload = _payload()
    blockers = {row["blocker_type"]: row for row in payload["chief_offline_blockers"]}

    assert blockers["TELEGRAM_OUTPUT_ATTEMPTED"]["fail_closed"] is True
    assert blockers["LIVE_DISPATCH_ATTEMPTED"]["fail_closed"] is True
    assert blockers["QUEUE_MUTATION_ATTEMPTED"]["fail_closed"] is True
    assert blockers["WATCHDOG_REPAIR_ATTEMPTED"]["fail_closed"] is True
    assert payload["examples"]["telegram_output_blocker"]["readback"]["status"] == "BLOCKED_LIVE_DISPATCH"
    assert payload["examples"]["watchdog_repair_blocker"]["readback"]["status"] == "BLOCKED_QUEUE_MUTATION"


def test_authority_boundary_all_false():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for key in [
        "repo_b_code_imported",
        "repo_b_runtime_executed",
        "live_chief_dispatch_performed",
        "queue_mutation_performed",
        "telegram_output_performed",
        "listener_started",
        "watchdog_repair_performed",
        "file_repair_performed",
        "worker_execution_performed",
        "model_call_performed",
        "external_action_performed",
        "credential_handling_performed",
        "raw_private_body_exposure",
        "mac_sync_import_performed",
        "swift_change_performed",
        "git_push_performed",
    ]:
        assert payload["machine_proof"][key] is False


def test_export_writes_json_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / wrapper.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / wrapper.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["posture"] == "WRAP_AS_OFFLINE_READBACK_WORKER_WITH_PROMOTED_DETERMINISTIC_SUBSET"
    assert payload["schema_version"] == wrapper.SCHEMA_VERSION
    assert "Repo B Chief Offline Worker Wrapper" in operator
    assert "No live Chief dispatch" in operator


def test_run_fixture_route_suggestion_outputs_selected_readback(tmp_path, capsys):
    assert run_main([
        "--export-root",
        str(tmp_path),
        "--generated-at",
        FIXED_NOW,
        "--fixture",
        "route_suggestion",
        "--format",
        "json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["selected_fixture"] == "route_suggestion"
    assert payload["selected_request"]["requested_capability"] == "ROUTE_SUGGESTION"
    assert payload["selected_readback"]["status"] == "FIXTURE_READBACK_READY"


def test_generated_outputs_have_no_credentials_or_private_bodies(tmp_path):
    payload = wrapper.build_payload(generated_at=FIXED_NOW, selected_fixture="route_suggestion")
    wrapper.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "OPENSSH_PRIVATE_KEY_MARKER" not in text
    assert "GMAIL_PASSWORD_MARKER" not in text
    assert "raw private log body value" not in text.lower()
    assert "telegram bot token value" not in text.lower()
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)


def test_source_does_not_execute_repo_b_chief_or_external_actions():
    source = Path("repo_b_chief_offline_worker_wrapper.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "subprocess.run",
        "from chief_",
        "import chief_",
        "from queue_balancer",
        "import queue_balancer",
        "from runner_registry",
        "import runner_registry",
        "telegram.ext",
        "telegram import",
        "urllib.request",
        "requests.",
        "httpx.",
        "ollama_call",
        "claude_call",
        "os.environ",
        "os.system",
        "shell=true",
    ]
    for token in forbidden:
        assert token not in source
