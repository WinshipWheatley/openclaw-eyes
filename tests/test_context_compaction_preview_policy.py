import ast
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import context_compaction_preview_policy as policy


FIXED_NOW = "2026-06-07T18:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    for spec in policy.PRECONDITIONS.values():
        _write_json(root / spec["filename"], {"status": spec["accepted_statuses"][0]})
    return root


def _build(tmp_path: Path) -> dict:
    return policy.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)


def _scenario(read_model: dict, scenario_id: str) -> dict:
    return policy.scenario_by_id(read_model, scenario_id)


def _tier(read_model: dict, tier_ref: str) -> dict:
    matches = [tier for tier in read_model["context_tiers"] if tier["tier_ref"] == tier_ref]
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


def test_large_artifact_policy_returns_preview_ref_not_full_dump(tmp_path):
    scenario = _scenario(_build(tmp_path), "large_server_error_log")
    preview = scenario["agent_visible_context"]["preview"]

    assert "tier_4_preview_snippets" in scenario["selected_tiers"]
    assert "tier_5_full_artifact_or_log_reference" in scenario["selected_tiers"]
    assert preview["preview_text"].startswith("Preview:")
    assert preview["full_artifact_ref"] == preview["artifact_ref"]
    assert len(preview["preview_text"]) <= preview["preview_char_limit"]
    assert preview["full_artifact_embedded"] is False
    assert preview["full_log_embedded"] is False
    assert preview["raw_file_body_embedded"] is False
    assert "full log body" in scenario["excluded_context"]


def test_raw_ocr_and_artifact_text_excluded_by_default(tmp_path):
    read_model = _build(tmp_path)
    raw_policy = read_model["agent_visible_context_policy"]["raw_private_material_policy"]
    postmortem = _scenario(read_model, "local_lm_non_json_postmortem")

    assert raw_policy["raw_ocr_text_embedded"] is False
    assert raw_policy["raw_artifact_text_embedded"] is False
    assert postmortem["policy_flags"]["raw_artifact_text_embedded"] is False
    assert postmortem["policy_flags"]["raw_ocr_text_embedded"] is False
    assert "raw candidate text" in postmortem["excluded_context"]


def test_full_chat_history_excluded(tmp_path):
    read_model = _build(tmp_path)
    forbidden = read_model["agent_visible_context_policy"]["forbidden_by_default"]

    assert "full chat history dumps" in forbidden
    assert read_model["machine_proof"]["full_chat_history_embedded"] is False
    assert _scenario(read_model, "build_review_history")["policy_flags"]["full_chat_history_embedded"] is False


def test_stale_summary_cannot_appear_as_current_context(tmp_path):
    scenario = _scenario(_build(tmp_path), "build_review_history")
    agent_context = scenario["agent_visible_context"]

    assert agent_context["active_context"] == []
    assert agent_context["history"][0]["summary"].startswith("Prior build review packet")
    assert scenario["policy_flags"]["stale_context_as_current_truth"] is False
    assert "stale summary as current truth" in scenario["excluded_context"]


def test_decision_trace_summary_is_included_when_relevant(tmp_path):
    scenario = _scenario(_build(tmp_path), "finance_payment_watch")
    agent_context = scenario["agent_visible_context"]

    assert "tier_3_decision_trace_summary" in scenario["selected_tiers"]
    assert "ledger posting" in agent_context["decision_trace_summary"]
    assert "payment evidence receipt" == agent_context["missing_input"]
    assert "receipt:capital_hilton_payment_watch_current" in agent_context["latest_receipt_refs"]


def test_niles_creative_bundle_excludes_finance_proof(tmp_path):
    scenario = _scenario(_build(tmp_path), "niles_creative_mapping")
    visible = json.dumps(scenario["agent_visible_context"], sort_keys=True).lower()

    assert "creative brief" in scenario["agent_visible_context"]["creative_context"]
    assert "finance proof" in scenario["excluded_context"]
    assert "payment evidence" in scenario["excluded_context"]
    assert "finance proof" not in visible
    assert "payment evidence" not in visible
    assert scenario["policy_flags"]["raw_private_proof_visible"] is False


def test_developer_proof_hidden_by_default(tmp_path):
    read_model = _build(tmp_path)
    tier = _tier(read_model, "tier_6_developer_proof_only")
    scenario = _scenario(read_model, "developer_proof_only")

    assert tier["agent_visible_by_default"] is False
    assert read_model["authority_boundary"]["developer_proof_visible_by_default"] is False
    assert scenario["policy_flags"]["developer_proof_visible_by_default"] is False
    assert "developer proof bodies" in scenario["excluded_context"]


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _build(tmp_path)

    assert policy.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True
    assert not [
        key
        for key, value in _walk_values(read_model)
        if key in policy.UNSAFE_TRUE_KEYS and value is True
    ]


def test_export_writes_local_bridge_equal_and_wiki(tmp_path):
    result = policy.export_context_compaction_preview_policy(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Context Compaction Preview Policy.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == policy.READY_STATUS
    assert local == bridge
    assert local["status"] == policy.READY_STATUS
    assert "Context Compaction Preview Policy" in wiki
    assert "Large artifacts are previewed first" in wiki
    assert policy.unsafe_true_grants(local) == []


def test_missing_precondition_marks_not_ready(tmp_path):
    root = _fixture_root(tmp_path)
    _write_json(root / "proof_bundle_freshness_trace_status.json", {"status": "NOT_READY"})

    read_model = policy.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    assert read_model["status"] == policy.NOT_READY_STATUS
    assert read_model["machine_proof"]["preconditions_ready"] is False
    assert policy.unsafe_true_grants(read_model) == []


def test_source_does_not_import_execution_or_provider_surfaces():
    source = Path("context_compaction_preview_policy.py").read_text(encoding="utf-8").lower()
    forbidden_tokens = [
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "smtplib",
        "selenium",
        "playwright",
        "pyautogui",
        "openpyxl",
        ".chief.env",
        ".google-secrets",
        "ollama",
        "litellm",
    ]
    for token in forbidden_tokens:
        assert token not in source

    tree = ast.parse(Path("context_compaction_preview_policy.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imported <= {"argparse", "hashlib", "json", "shutil"}
