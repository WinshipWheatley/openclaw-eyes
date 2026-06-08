import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import context_compaction_preview_policy as policy
import context_freshness_decision_trace_gate as freshness_gate


FIXED_NOW = "2026-06-08T10:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    statuses = {
        "proof_bundle_redaction_policy.json": "PROOF_BUNDLE_REDACTION_HARDENING_READY",
        "proof_bundle_freshness_trace_status.json": "PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY",
        freshness_gate.JSON_EXPORT_NAME: freshness_gate.READY_STATUS,
        "operator_session_timeline.json": "OPERATOR_SESSION_TIMELINE_READY",
        "universal_receipt_envelope_status.json": "UNIVERSAL_RECEIPT_ENVELOPE_READY",
        "agent_response_voice_modes.json": "AGENT_RESPONSE_VOICE_MODES_READY",
        "retrospective_harness_learning_seed.json": "RETROSPECTIVE_HARNESS_LEARNING_SEED_READY",
    }
    for filename, status in statuses.items():
        _write_json(root / filename, {"status": status})
    return root


def _read_model(tmp_path: Path) -> dict:
    return policy.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)


def _scenario(read_model: dict, scenario_ref: str) -> dict:
    return next(row for row in read_model["required_scenarios"] if row["scenario_ref"] == scenario_ref)


def test_large_artifact_policy_returns_preview_ref_not_full_dump(tmp_path):
    read_model = _read_model(tmp_path)
    scenario = _scenario(read_model, "large_server_error_log")
    preview = scenario["preview_policy"]

    assert read_model["status"] == policy.READY_STATUS
    assert preview["preview_first"] is True
    assert preview["preview_max_lines"] == 20
    assert preview["full_dump_embedded"] is False
    assert preview["full_artifact_referenced"] is True
    assert "tier_5_full_artifact_or_log_reference" in scenario["context_tiers_used"]


def test_raw_ocr_artifact_text_excluded_by_default(tmp_path):
    read_model = _read_model(tmp_path)
    forbidden = set(read_model["agent_visible_context_policy"]["forbidden_by_default"])

    assert "raw_ocr_artifact_text" in forbidden
    assert read_model["authority_boundary"]["raw_artifact_text_allowed_by_default"] is False
    assert read_model["machine_proof"]["raw_ocr_artifact_text_excluded_by_default"] is True


def test_full_chat_history_excluded(tmp_path):
    read_model = _read_model(tmp_path)
    forbidden = set(read_model["agent_visible_context_policy"]["forbidden_by_default"])

    assert "full_chat_history_dumps" in forbidden
    assert read_model["authority_boundary"]["full_history_dump_allowed"] is False
    assert read_model["machine_proof"]["full_chat_history_excluded"] is True


def test_stale_summary_cannot_appear_as_current_context(tmp_path):
    read_model = _read_model(tmp_path)
    scenario = _scenario(read_model, "build_review_history")

    assert "Stale summaries are demoted." in read_model["compaction_rules"]
    assert "Superseded receipts remain historical, not current truth." in read_model["compaction_rules"]
    assert scenario["preview_policy"]["active_context"] is False
    assert scenario["preview_policy"]["stale_context_entered_as_current_truth"] is False
    assert read_model["authority_boundary"]["stale_context_current_truth_allowed"] is False


def test_decision_trace_summary_is_included_when_relevant(tmp_path):
    read_model = _read_model(tmp_path)
    scenario = _scenario(read_model, "local_lm_non_json_postmortem")

    assert "relevant_decision_trace_summary" in read_model["agent_visible_context_policy"]["allowed"]
    assert "tier_3_decision_trace_summary" in scenario["context_tiers_used"]
    assert scenario["preview_policy"]["decision_trace_summary_visible"] is True
    assert "fallback receipt" in scenario["agent_visible_summary"]


def test_niles_creative_bundle_excludes_finance_proof(tmp_path):
    scenario = _scenario(_read_model(tmp_path), "niles_creative_mapping")

    assert scenario["preview_policy"]["creative_context_allowed"] is True
    assert scenario["preview_policy"]["unrelated_finance_proof_excluded"] is True
    assert scenario["preview_policy"]["private_finance_proof_included"] is False
    assert "unrelated_finance_proof" in scenario["forbidden_material_excluded"]


def test_developer_proof_hidden_by_default(tmp_path):
    read_model = _read_model(tmp_path)
    tier = next(row for row in read_model["context_tiers"] if row["tier_ref"] == "tier_6_developer_proof_only")
    large_log = _scenario(read_model, "large_server_error_log")
    remote = _scenario(read_model, "remote_desktop_trace_log_leak")

    assert tier["agent_visible_by_default"] is False
    assert tier["full_body_policy"] == "hidden_by_default"
    assert large_log["preview_policy"]["developer_proof_hidden_by_default"] is True
    assert remote["preview_policy"]["developer_proof_hidden_by_default"] is True
    assert read_model["machine_proof"]["developer_proof_hidden_by_default"] is True


def test_resource_leak_context_does_not_grant_cleanup_authority(tmp_path):
    read_model = _read_model(tmp_path)
    scenario = _scenario(read_model, "remote_desktop_trace_log_leak")

    assert scenario["preview_policy"]["resource_summary_visible"] is True
    assert scenario["preview_policy"]["raw_trace_log_embedded"] is False
    assert scenario["preview_policy"]["broad_temp_file_delete_authority"] is False
    assert scenario["authority_boundary"]["cleanup_authority_granted"] is False
    assert read_model["authority_boundary"]["cleanup_authority_granted"] is False
    assert read_model["machine_proof"]["resource_cleanup_authority_absent"] is True


def test_all_required_tiers_present(tmp_path):
    read_model = _read_model(tmp_path)
    observed = {row["tier_ref"] for row in read_model["context_tiers"]}

    assert observed == set(policy.CONTEXT_TIER_REFS)
    assert read_model["machine_proof"]["all_required_tiers_present"] is True


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert policy.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = policy.export_context_compaction_preview_policy(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Context Compaction Preview Policy.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == policy.READY_STATUS
    assert local == bridge
    assert policy.unsafe_true_grants(local) == []
    assert wiki.startswith("# Context Compaction Preview Policy")
