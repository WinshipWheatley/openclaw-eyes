import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_model_list_inventory as inventory


FIXED_NOW = "2026-06-07T08:10:00+00:00"
OLLAMA_LIST_FIXTURE = """NAME                    ID              SIZE      MODIFIED
qwen3:8b-q4_K_M         500a1f067a9f    5.2 GB    6 weeks ago
mistral-small:latest    8039dd90c113    14 GB     7 weeks ago
"""


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "model_catalog_inventory.json", {"status": "MODEL_CATALOG_INVENTORY_READY"})
    _write_json(root / "local_lm_runtime_discovery.json", {"status": "LOCAL_LM_RUNTIME_DISCOVERY_READY"})
    _write_json(root / "local_lm_model_selection_review_packet.json", {"status": "LOCAL_LM_MODEL_SELECTION_REVIEW_READY"})
    _write_json(root / "local_lm_proof_response_preflight_receipts.json", {"status": "LOCAL_LM_PROOF_RESPONSE_PREFLIGHT_RECEIPTS_READY"})
    _write_json(root / "proof_bundle_builder_redaction_status.json", {"status": "PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY"})
    return root


def _read_model(tmp_path: Path) -> dict:
    return inventory.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        generated_at=FIXED_NOW,
        ollama_list_output=OLLAMA_LIST_FIXTURE,
    )


def test_model_invocation_performed_false(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["status"] == inventory.READY_STATUS
    assert read_model["model_invocation_performed"] is False
    assert read_model["implementation_boundary"]["model_invocation_performed"] is False
    assert read_model["machine_proof"]["model_invocation_performed"] is False


def test_prompt_sent_false(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["prompt_sent"] is False
    assert read_model["implementation_boundary"]["prompt_sent"] is False
    assert read_model["machine_proof"]["prompt_sent"] is False


def test_proof_bundle_sent_false(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["proof_bundle_sent"] is False
    assert read_model["implementation_boundary"]["proof_bundle_sent"] is False
    assert read_model["machine_proof"]["proof_bundle_sent"] is False


def test_external_provider_used_false(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["external_provider_used"] is False
    assert read_model["authority_boundary"]["external_provider_connect_allowed"] is False
    assert read_model["machine_proof"]["external_provider_used"] is False


def test_secrets_read_false(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["secrets_read"] is False
    assert read_model["implementation_boundary"]["secrets_read"] is False
    assert read_model["machine_proof"]["secrets_read"] is False


def test_all_discovered_models_have_invocation_allowed_false(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["models_found_count"] == 2
    assert read_model["recommended_next_decision"] == "select_one_local_model_for_pilot_review"
    for row in read_model["discovered_models"]:
        assert row["runtime_ref"] == "ollama"
        assert row["local_only"] is True
        assert row["present"] is True
        assert row["invocation_allowed"] is False
        assert row["authority_boundary"]["invocation_allowed"] is False
        assert row["selected_for_pilot"] is False


def test_all_discovered_models_have_proof_bundle_allowed_false(tmp_path):
    read_model = _read_model(tmp_path)

    for row in read_model["discovered_models"]:
        assert row["proof_bundle_allowed"] is False
        assert row["authority_boundary"]["proof_bundle_allowed"] is False
        assert "operator_approval_receipt" in row["missing_receipts"]
        assert "model_invocation_boundary_receipt" in row["missing_receipts"]


def test_model_metadata_parsed_without_inference(tmp_path):
    read_model = _read_model(tmp_path)
    qwen = read_model["discovered_models"][0]
    mistral = read_model["discovered_models"][1]

    assert qwen["model_name"] == "qwen3:8b-q4_K_M"
    assert qwen["model_family"] == "qwen3"
    assert qwen["size_or_parameters"] == "5.2 GB; parameters 8b"
    assert qwen["source"] == "ollama list"
    assert mistral["model_name"] == "mistral-small:latest"
    assert mistral["size_or_parameters"] == "14 GB"
    assert read_model["command_results"][0]["command"] == "ollama list"
    assert read_model["command_results"][0]["fixture_input"] is True


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert inventory.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = inventory.export_local_model_list_inventory(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Local Model List Inventory.md",
        generated_at=FIXED_NOW,
        ollama_list_output=OLLAMA_LIST_FIXTURE,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == inventory.READY_STATUS
    assert result["models_found_count"] == "2"
    assert result["model_invocation_performed"] == "false"
    assert result["prompt_sent"] == "false"
    assert result["proof_bundle_sent"] == "false"
    assert result["external_provider_used"] == "false"
    assert result["secrets_read"] == "false"
    assert local == bridge
    assert inventory.unsafe_true_grants(local) == []
    assert wiki.startswith("# Local Model List Inventory")
