import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import harness_provider_selection_registry as registry


FIXED_NOW = "2026-06-04T00:15:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path, *, optional_ready: bool = False) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "operator_assist_provider_registry.json", {"status": "OPERATOR_ASSIST_PROVIDER_REGISTRY_READY"})
    _write_json(root / "local_llm_intent_privacy_upgrade_plan.json", {"status": "LOCAL_LLM_INTENT_PRIVACY_PLAN_READY"})
    if optional_ready:
        _write_json(root / "worker_sandbox_policy.json", {"status": "WORKER_SANDBOX_POLICY_READY"})
        _write_json(root / "sleep_safe_automation_registry.json", {"status": "SLEEP_SAFE_AUTOMATION_REGISTRY_READY"})
    return root


def _selection(payload: dict, outcome_ref: str) -> dict:
    matches = [row for row in payload["example_selections"] if row["outcome_ref"] == outcome_ref]
    assert len(matches) == 1
    return matches[0]


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def test_private_workbook_workflow_selects_local_or_mac_helper_not_external_llm():
    selection = registry.select_provider_for_outcome(
        outcome_ref="private_workbook_workflow",
        outcome_label="Review private invoice workbook workflow.",
        data_sensitivity="private_client_invoice_workbook",
        local_file_access_needed=True,
        gui_needed=True,
        target_platform="mac",
    )

    assert selection["selected_provider_class"] == "mac_codex_ui_worker"
    assert selection["safe_to_invoke_model_now"] is False
    assert selection["safe_to_connect_provider_now"] is False
    rejected = {row["provider_class"]: row for row in selection["rejected_provider_classes"]}
    assert "external_llm_blocked_by_default" in rejected
    assert "local_or_private_data" in rejected["external_llm_blocked_by_default"]["reject_reasons"]


def test_backend_code_task_selects_pc_codex_worker():
    selection = registry.select_provider_for_outcome(
        outcome_ref="backend_code_task",
        outcome_label="Implement backend read-model change.",
        data_sensitivity="proprietary_local_code",
        local_file_access_needed=True,
        code_generation_needed=True,
        target_platform="pc_backend",
    )

    assert selection["selected_provider_class"] == "pc_codex_backend_worker"
    assert selection["gate_required_before_use"] is True
    assert selection["safe_to_run_codex_automation_now"] is False
    assert selection["provider_choice_grants_authority"] is False


def test_ui_task_selects_mac_codex_worker():
    selection = registry.select_provider_for_outcome(
        outcome_ref="ui_task",
        outcome_label="Improve Mission Control UI.",
        data_sensitivity="internal_ui_code",
        local_file_access_needed=True,
        gui_needed=True,
        code_generation_needed=True,
        target_platform="mac_ui",
    )

    assert selection["selected_provider_class"] == "mac_codex_ui_worker"
    assert selection["gate_required_before_use"] is True
    assert selection["safe_to_run_codex_automation_now"] is False


def test_coupa_selects_operator_assist_not_unattended():
    selection = registry.select_provider_for_outcome(
        outcome_ref="coupa_operator_assist",
        outcome_label="Submit invoice through Coupa.",
        data_sensitivity="private_client_invoice_portal",
        gui_needed=True,
        coupa_browser_needed=True,
        unattended_requested=True,
        target_platform="browser_coupa",
    )

    assert selection["selected_provider_class"] == "browser_coupa_operator_assist"
    assert selection["unattended_eligible"] is False
    assert selection["blocked_by_default"] is True
    assert selection["safe_to_connect_provider_now"] is False


def test_external_llm_blocked_by_default():
    selection = registry.select_provider_for_outcome(
        outcome_ref="external_llm_request",
        outcome_label="Ask external LLM to reason over local client files.",
        data_sensitivity="private_client_files",
        local_file_access_needed=True,
        external_llm_requested=True,
    )

    assert selection["selected_provider_class"] == "external_llm_blocked_by_default"
    assert selection["usable_now"] is False
    assert selection["blocked_by_default"] is True
    assert selection["gate_required_before_use"] is True
    assert selection["safe_to_invoke_model_now"] is False


def test_registry_contains_all_provider_classes_and_examples(tmp_path):
    payload = registry.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    assert payload["status"] == registry.READY_STATUS
    assert {row["provider_class"] for row in payload["provider_classes"]} == set(registry.PROVIDER_CLASSES)
    assert _selection(payload, "private_workbook_workflow")["selected_provider_class"] == "mac_codex_ui_worker"
    assert _selection(payload, "backend_code_task")["selected_provider_class"] == "pc_codex_backend_worker"
    assert _selection(payload, "ui_task")["selected_provider_class"] == "mac_codex_ui_worker"
    assert _selection(payload, "coupa_operator_assist")["selected_provider_class"] == "browser_coupa_operator_assist"
    assert _selection(payload, "external_llm_request")["selected_provider_class"] == "external_llm_blocked_by_default"
    optional = {row["precondition_ref"]: row for row in payload["preconditions"]}
    assert optional["worker_sandbox_policy"]["ready"] is True
    assert optional["worker_sandbox_policy"]["present"] is False


def test_no_unsafe_grants(tmp_path):
    payload = registry.build_read_model(read_model_root=_fixture_root(tmp_path, optional_ready=True), generated_at=FIXED_NOW)

    assert registry.unsafe_true_grants(payload) == []
    assert not [key for key, value in _walk_values(payload) if key in registry.UNSAFE_TRUE_KEYS and value is True]
    assert payload["machine_proof"]["models_invoked"] is False
    assert payload["machine_proof"]["external_provider_connected"] is False
    assert payload["machine_proof"]["codex_automation_run"] is False
    assert payload["machine_proof"]["git_push_performed"] is False


def test_export_writes_local_bridge_equal_and_wiki(tmp_path):
    result = registry.export_harness_provider_selection_registry(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Harness Provider Selection Registry.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert local == bridge
    assert local["status"] == registry.READY_STATUS
    assert "No model invocation." in wiki
