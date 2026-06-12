import json
from pathlib import Path

import sync_health
from generated_read_model_files import SAFE_GENERATED_READ_MODEL_MANIFEST_FILES
from openclaw_substrate_utils import sha256_file
from scripts import pc_read_model_import_agent as import_agent


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _manifest_record(relative_path: str, digest: str) -> dict:
    return {
        "relative_path": relative_path,
        "path_type": "file",
        "content_hash": digest,
        "hash_algorithm": "sha256",
    }


def test_sync_health_uses_mac_sync_latest_expected_set_and_keeps_extras_review_only(tmp_path):
    read_models = tmp_path / "generated" / "read_models"
    read_models.mkdir(parents=True)
    _write(read_models / "alpha.json", '{"alpha": true}\n')
    _write(read_models / "broad_history.json", '{"old": true}\n')
    preserved_manifest_name = "openclaw_map_manifest.json"
    assert preserved_manifest_name in SAFE_GENERATED_READ_MODEL_MANIFEST_FILES

    alpha_hash = sha256_file(read_models / "alpha.json")
    preserved_hash = "a" * 64
    latest = tmp_path / "read_model_sync_latest.json"
    _write(
        latest,
        json.dumps(
            {
                "copied_count": 1,
                "copied_files": [
                    {
                        "relative_path": "alpha.json",
                        "sha256": alpha_hash,
                        "size_bytes": (read_models / "alpha.json").stat().st_size,
                    }
                ],
            }
        )
        + "\n",
    )
    manifest = tmp_path / "mac_generated_read_models_manifest.json"
    _write(
        manifest,
        json.dumps(
            {
                "path_records": [
                    _manifest_record("alpha.json", alpha_hash),
                    _manifest_record(preserved_manifest_name, preserved_hash),
                    _manifest_record("chat_readback_card_mirror.json", "b" * 64),
                    _manifest_record("openclaw_map_receipt.json", "c" * 64),
                ]
            }
        )
        + "\n",
    )

    health = sync_health.compare_manifest_to_backend(
        manifest_path=manifest,
        read_model_root=read_models,
        repo_root=tmp_path,
        mac_sync_latest_path=latest,
    )

    assert health["expected_set_basis"] == "mac_sync_latest_safe_selector"
    assert health["counts"]["canonical_expected"] == 2
    assert health["counts"]["observed"] == 4
    assert health["counts"]["missing_expected"] == 0
    assert health["counts"]["hash_mismatch"] == 0
    assert health["counts"]["extra"] == 2
    assert health["counts"]["blocking_extra"] == 0
    assert health["nonblocking_extra_files"] == [
        "chat_readback_card_mirror.json",
        "openclaw_map_receipt.json",
    ]
    assert "broad_history.json" not in health["missing_expected_files"]

    raw_status = sync_health.build_raw_read_model_mirror_status(health)
    assert raw_status["raw_mirror_status"] == "raw_mirror_current"


def test_import_agent_does_not_request_mac_sync_for_review_only_extras(tmp_path):
    read_models = tmp_path / "generated" / "read_models"
    read_models.mkdir(parents=True)
    _write(read_models / "alpha.json", '{"alpha": true}\n')
    latest = tmp_path / "read_model_sync_latest.json"
    alpha_hash = sha256_file(read_models / "alpha.json")
    _write(
        latest,
        json.dumps({"copied_files": [{"relative_path": "alpha.json", "sha256": alpha_hash}]})
        + "\n",
    )
    manifest = tmp_path / "mac_generated_read_models_manifest.json"
    _write(
        manifest,
        json.dumps(
            {
                "path_records": [
                    _manifest_record("alpha.json", alpha_hash),
                    _manifest_record("chat_readback_card_mirror.json", "d" * 64),
                ]
            }
        )
        + "\n",
    )

    state = import_agent.canonical_expected_set_mirror_state(
        manifest_path=manifest,
        read_model_root=read_models,
        repo_root=tmp_path,
    )

    assert state["status"] == "canonical_expected_set_current_with_extra_review"
    assert state["marker_needed"] is False
    assert state["refresh_needed"] is False
    assert state["counts"]["missing_expected"] == 0
    assert state["counts"]["hash_mismatch"] == 0
    assert state["extra_files"] == ["chat_readback_card_mirror.json"]
