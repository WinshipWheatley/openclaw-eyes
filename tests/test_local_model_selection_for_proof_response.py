import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_model_selection_for_proof_response as selection
import proof_to_response_runtime


FIXED_NOW = "2026-06-07T10:10:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _model(name: str, size: str) -> dict:
    slug = name.replace(":", "_").replace("/", "_").lower()
    return {
        "model_ref": f"local_model:ollama:{slug}",
        "runtime_ref": "ollama",
        "model_name": name,
        "model_family": name.split(":", 1)[0],
        "size_or_parameters": size,
        "local_only": True,
        "present": True,
        "invocation_allowed": False,
        "proof_bundle_allowed": False,
        "selected_for_pilot": False,
        "source": "ollama list",
        "missing_receipts": [
            "operator_approval_receipt",
            "model_invocation_boundary_receipt",
            "verifier_pass_fail_receipt",
            "published_response_hash_receipt",
        ],
    }


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / "local_model_list_inventory.json",
        {
            "status": "LOCAL_MODEL_LIST_INVENTORY_READY",
            "external_provider_used": False,
            "models_found_count": 4,
            "discovered_models": [
                _model("qwen3:4b", "2.5 GB; parameters 4b"),
                _model("qwen3:8b-q4_K_M", "5.2 GB; parameters 8b"),
                _model("mistral-small:latest", "14 GB"),
                _model("nemotron-3-nano:30b", "24 GB; parameters 30b"),
            ],
        },
    )
    _write_json(root / "model_catalog_inventory.json", {"status": "MODEL_CATALOG_INVENTORY_READY"})
    _write_json(root / "local_lm_runtime_discovery.json", {"status": "LOCAL_LM_RUNTIME_DISCOVERY_READY"})
    _write_json(
        root / "local_lm_proof_response_preflight_receipts.json",
        {
            "status": "LOCAL_LM_PROOF_RESPONSE_PREFLIGHT_RECEIPTS_READY",
            "pilot_lane": "finance/capital_hilton",
            "pilot_question": "What should I do here?",
        },
    )
    _write_json(
        root / "local_lm_proof_to_response_pilot_plan.json",
        {
            "status": "LOCAL_LM_PROOF_RESPONSE_PILOT_PLAN_READY",
            "first_pilot_lane": {"lane_ref": "finance/capital_hilton"},
        },
    )
    _write_json(root / "proof_bundle_builder_redaction_status.json", {"status": "PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY"})
    _write_json(root / proof_to_response_runtime.STATUS_JSON_EXPORT_NAME, {"status": proof_to_response_runtime.READY_STATUS})
    return root


def _read_model(tmp_path: Path) -> dict:
    return selection.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)


def _packet(read_model: dict) -> dict:
    return read_model["selection_packet"]


def test_exactly_one_model_is_recommended(tmp_path):
    read_model = _read_model(tmp_path)
    packet = _packet(read_model)
    selected = [row for row in packet["candidate_models"] if row["selected_for_review"] is True]

    assert read_model["status"] == selection.READY_STATUS
    assert packet["status"] == "pending_operator_review"
    assert packet["recommended_model_ref"] == "local_model:ollama:qwen3_8b-q4_k_m"
    assert packet["recommended_model_name"] == "qwen3:8b-q4_K_M"
    assert packet["recommended_runtime_ref"] == "ollama"
    assert len(selected) == 1
    assert selected[0]["model_name"] == "qwen3:8b-q4_K_M"


def test_invocation_allowed_false_for_all_models(tmp_path):
    packet = _packet(_read_model(tmp_path))

    assert packet["ready_for_invocation"] is False
    assert packet["authority_boundary"]["invocation_allowed"] is False
    for row in packet["candidate_models"]:
        assert row["invocation_allowed"] is False
        assert row["authority_boundary"]["model_invocation_allowed"] is False


def test_proof_bundle_allowed_false_for_all_models(tmp_path):
    packet = _packet(_read_model(tmp_path))

    assert packet["proof_bundle_allowed"] is False
    assert packet["authority_boundary"]["proof_bundle_allowed"] is False
    for row in packet["candidate_models"]:
        assert row["proof_bundle_allowed"] is False
        assert "operator_approval_receipt" in row["missing_receipts"]
        assert "model_invocation_boundary_receipt" in row["missing_receipts"]


def test_external_provider_used_false(tmp_path):
    read_model = _read_model(tmp_path)
    packet = _packet(read_model)

    assert packet["external_provider_used"] is False
    assert read_model["machine_proof"]["external_provider_used"] is False
    assert packet["authority_boundary"]["external_provider_connect_allowed"] is False


def test_verifier_mandatory(tmp_path):
    packet = _packet(_read_model(tmp_path))

    assert packet["verifier_mandatory"] is True
    assert packet["selection_criteria"]["verifier_mandatory"] is True
    assert "verifier_pass_fail_receipt" in packet["candidate_models"][0]["missing_receipts"]


def test_first_pilot_lane_remains_finance_capital_hilton(tmp_path):
    packet = _packet(_read_model(tmp_path))
    lane = packet["first_pilot_lane"]

    assert lane["lane"] == "finance/capital_hilton"
    assert lane["world_ref"] == "finance"
    assert lane["thread_ref"] == "capital_hilton"
    assert lane["question"] == "What should I do here?"


def test_no_tool_memory_business_authority(tmp_path):
    packet = _packet(_read_model(tmp_path))

    assert packet["authority_boundary"]["tool_authority"] is False
    assert packet["authority_boundary"]["memory_write_authority"] is False
    assert packet["authority_boundary"]["business_action_authority"] is False
    assert packet["implementation_boundary"]["tool_execution_performed"] is False
    assert packet["implementation_boundary"]["memory_write_performed"] is False
    assert packet["implementation_boundary"]["business_action_performed"] is False


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert selection.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_no_suitable_model_path_is_review_ready(tmp_path):
    root = _fixture_root(tmp_path)
    payload = json.loads((root / "local_model_list_inventory.json").read_text(encoding="utf-8"))
    payload["discovered_models"] = []
    payload["models_found_count"] = 0
    _write_json(root / "local_model_list_inventory.json", payload)

    read_model = selection.build_read_model(read_model_root=root, generated_at=FIXED_NOW)
    packet = read_model["selection_packet"]

    assert read_model["status"] == selection.READY_STATUS
    assert packet["recommended_model_ref"] == ""
    assert packet["no_suitable_model"] is True
    assert packet["ready_for_invocation"] is False
    assert packet["proof_bundle_allowed"] is False


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = selection.export_local_model_selection_for_proof_response(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Local Model Selection For Proof Response.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == selection.READY_STATUS
    assert result["packet_status"] == "pending_operator_review"
    assert result["recommended_model_ref"] == "local_model:ollama:qwen3_8b-q4_k_m"
    assert result["recommended_runtime_ref"] == "ollama"
    assert result["ready_for_invocation"] == "false"
    assert result["proof_bundle_allowed"] == "false"
    assert local == bridge
    assert selection.unsafe_true_grants(local) == []
    assert wiki.startswith("# Local Model Selection For Proof Response")
