import json
import sqlite3
from pathlib import Path

from corpus_atlas import run_corpus_atlas
from generated_read_model_files import (
    CRITICAL_GENERATED_READ_MODEL_FILES,
    MISSION_CONTROL_CAPTURE_INTAKE_READ_MODEL_FILES,
    MISSION_CONTROL_REVIEW_PACKET_READ_MODEL_FILES,
    canonical_generated_read_model_expected_files,
)
from read_model_shuttle import (
    DEFAULT_FROM_MAC_SEARCH_ROOTS,
    DEFAULT_CAPTURE_REQUEST_OUTBOX_MAC_PATH,
    DEFAULT_CAPTURE_REQUEST_OUTBOX_PC_PATH,
    DEFAULT_RETURNED_MANIFEST_PATH,
    DEFAULT_TO_MAC_ROOT,
    DEFAULT_TRANSFER_ROOT,
    NO_AUTHORITY_FLAGS,
    approved_capture_request_outbox_contract,
    build_mac_generated_read_model_manifest,
    import_mac_read_model_shuttle,
    mac_apply_script,
    prepare_mac_read_model_shuttle,
)
from scripts.import_latest_mac_read_model_mirror import CRITICAL_READ_MODEL_FILES
from scripts.mac_sync_generated_read_models import KEY_READ_MODEL_FILES


def _write(path: Path, text: str = "{}\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_model_source(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    root.mkdir(parents=True)
    for name in (
        "source_inventory.json",
        "helm_state.json",
        "world_domain_registry.json",
        "world_status.json",
        "artifact_registry.json",
        "runtime_activation_gate.json",
        "evidence_freshness.json",
        "tool_inventory.json",
        "tool_inventory_OPERATOR.md",
        "tool_intake.json",
        "tool_intake_OPERATOR.md",
        "context_selection.json",
        "context_selection_OPERATOR.md",
        "generated_current_state.md",
        "generated_next_actions.md",
        "artifact_registry.operator.txt",
    ):
        _write(root / name, f"{name}\n")
    _write(root / "mac_generated_read_models_manifest.json", "{}\n")
    _write(root / "make_winship_life_easier_batch_manifest.json", '{"safe": true}\n')
    _write(root / "make_winship_life_easier_batch_manifest_OPERATOR.md", "# Safe generated manifest\n")
    _write(root / "capital_hilton_proof_resolution_batch_manifest.json", '{"safe": true}\n')
    _write(root / "openclaw_work_terrain_reconciliation_batch_manifest.json", '{"safe": true}\n')
    _write(root / "mission_control_capture_request_intake.json", '{"safe": true}\n')
    _write(root / "mission_control_capture_request_intake_OPERATOR.md", "# Safe capture intake\n")
    _write(root / "private_manifest.json", "{}\n")
    _write(root / "ledger.sqlite", "not a read model\n")
    _write(root / "secret_token.json", "{}\n")
    _write(root / ".hidden.json", "{}\n")
    (root / "nested").mkdir()
    _write(root / "nested" / "nested.json", "{}\n")
    return root


def test_prepare_creates_package_manifest_readme_and_apply_script(tmp_path):
    source = _read_model_source(tmp_path)
    output_root = tmp_path / "to_mac"

    result = prepare_mac_read_model_shuttle(
        source_root=source,
        output_root=output_root,
        generated_at="2026-05-14T13:00:00+00:00",
    )
    package = Path(result.package_path)

    assert package.is_dir()
    assert (package / "payload" / "generated_read_models").is_dir()
    assert (package / "shuttle_manifest.json").is_file()
    assert (package / "MISSION_CONTROL_CAPTURE_OUTBOX_CONTRACT.json").is_file()
    assert (package / "APPLY_ON_MAC.sh").is_file()
    assert (package / "README.md").is_file()
    assert result.file_count >= 15


def test_default_transfer_paths_use_e_drive_not_c_drive():
    assert DEFAULT_TRANSFER_ROOT.as_posix() == "/mnt/e/openclaw"
    assert DEFAULT_TO_MAC_ROOT.as_posix() == "/mnt/e/openclaw/shuttle/to_mac"
    assert DEFAULT_RETURNED_MANIFEST_PATH.as_posix() == "/mnt/e/openclaw/mac_generated_read_models_manifest.json"
    assert DEFAULT_CAPTURE_REQUEST_OUTBOX_PC_PATH.as_posix() == "/mnt/e/openclaw/mission_control_capture_requests/inbox"
    assert DEFAULT_CAPTURE_REQUEST_OUTBOX_MAC_PATH == "/Volumes/openclaw_e/mission_control_capture_requests/inbox"
    assert "/mnt/e/openclaw/shuttle/from_mac" in {
        path.as_posix() for path in DEFAULT_FROM_MAC_SEARCH_ROOTS
    }
    assert all(
        not path.as_posix().startswith("/mnt/" + "c/openclaw")
        for path in DEFAULT_FROM_MAC_SEARCH_ROOTS
    )


def test_package_manifest_lists_sizes_hashes_and_no_authority_flags(tmp_path):
    source = _read_model_source(tmp_path)
    result = prepare_mac_read_model_shuttle(
        source_root=source,
        output_root=tmp_path / "to_mac",
        generated_at="2026-05-14T13:00:00+00:00",
    )
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))

    assert manifest["shuttle_manifest_version"] == "openclaw.read_model_shuttle.v0"
    assert manifest["file_count"] == len(manifest["files"])
    assert manifest["total_bytes"] == sum(item["size_bytes"] for item in manifest["files"])
    for item in manifest["files"]:
        assert item["relative_path"]
        assert item["size_bytes"] > 0
        assert len(item["sha256"]) == 64
        assert item["hash_algorithm"] == "sha256"
    for key, value in NO_AUTHORITY_FLAGS.items():
        assert manifest[key] is value is False
        assert manifest["no_authority_flags"][key] is False


def test_package_excludes_non_read_model_and_no_go_files(tmp_path):
    source = _read_model_source(tmp_path)
    result = prepare_mac_read_model_shuttle(
        source_root=source,
        output_root=tmp_path / "to_mac",
        generated_at="2026-05-14T13:00:00+00:00",
    )
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    names = {item["relative_path"] for item in manifest["files"]}

    assert "source_inventory.json" in names
    assert "context_selection.json" in names
    assert "context_selection_OPERATOR.md" in names
    assert "make_winship_life_easier_batch_manifest.json" in names
    assert "make_winship_life_easier_batch_manifest_OPERATOR.md" in names
    assert "capital_hilton_proof_resolution_batch_manifest.json" in names
    assert "openclaw_work_terrain_reconciliation_batch_manifest.json" in names
    assert "mission_control_capture_request_intake.json" in names
    assert "mission_control_capture_request_intake_OPERATOR.md" in names
    assert "mac_generated_read_models_manifest.json" not in names
    assert "private_manifest.json" not in names
    assert "ledger.sqlite" not in names
    assert "secret_token.json" not in names
    assert ".hidden.json" not in names
    assert "nested/nested.json" not in names


def test_generated_apply_script_has_no_remote_or_destructive_commands():
    text = mac_apply_script().lower()

    forbidden_tokens = [
        "rsync ",
        "scp ",
        "ssh ",
        "git commit",
        "git push",
        "rm ",
        "rm -",
        "unlink",
        "rmdir",
        "docker",
        "ollama",
    ]
    for token in forbidden_tokens:
        assert token not in text
    assert "cp " in text
    assert "mac_generated_read_models_manifest.json" in text
    assert "mission_control_capture_request_intake.json" in text


def test_portable_mac_manifest_logic_produces_importable_manifest(tmp_path):
    mac_root = tmp_path / "mac_generated"
    _write(mac_root / "source_inventory.json", '{"same": true}\n')
    _write(mac_root / "context_selection.json", '{"context": true}\n')
    _write(mac_root / "context_selection_OPERATOR.md", "# context\n")
    manifest_path = tmp_path / "mac_generated_read_models_manifest.json"

    manifest = build_mac_generated_read_model_manifest(
        destination_root=mac_root,
        output=manifest_path,
        generated_at="2026-05-14T13:00:00+00:00",
    )

    assert manifest["manifest_schema_version"] == "openclaw.root_manifest.v0"
    assert manifest["root_id"] == "mac_generated_read_models"
    by_path = {record["relative_path"]: record for record in manifest["path_records"]}
    assert by_path["context_selection.json"]["content_hash"]
    assert by_path["context_selection.json"]["evidence_category"] == "context_gate"


def test_capital_hilton_review_packet_files_are_mirror_expected_and_keyed():
    expected = set(canonical_generated_read_model_expected_files())

    for name in MISSION_CONTROL_REVIEW_PACKET_READ_MODEL_FILES:
        assert name in expected
        assert name in CRITICAL_GENERATED_READ_MODEL_FILES
        assert name in KEY_READ_MODEL_FILES
        assert name in CRITICAL_READ_MODEL_FILES

    assert "invoice_review_bundle.json" in MISSION_CONTROL_REVIEW_PACKET_READ_MODEL_FILES


def test_mission_control_capture_intake_files_are_mirror_expected_and_keyed():
    expected = set(canonical_generated_read_model_expected_files())

    for name in MISSION_CONTROL_CAPTURE_INTAKE_READ_MODEL_FILES:
        assert name in expected
        assert name in CRITICAL_GENERATED_READ_MODEL_FILES
        assert name in KEY_READ_MODEL_FILES
        assert name in CRITICAL_READ_MODEL_FILES


def test_capture_outbox_contract_is_bounded_and_visible_in_package(tmp_path):
    source = _read_model_source(tmp_path)
    result = prepare_mac_read_model_shuttle(
        source_root=source,
        output_root=tmp_path / "to_mac",
        generated_at="2026-05-24T13:00:00+00:00",
    )
    package = Path(result.package_path)
    marker = json.loads(Path(result.outbox_marker_path).read_text(encoding="utf-8"))
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))

    assert marker == approved_capture_request_outbox_contract()
    assert marker["pc_outbox_path"] == "/mnt/e/openclaw/mission_control_capture_requests/inbox"
    assert marker["mac_visible_outbox_path"] == "/Volumes/openclaw_e/mission_control_capture_requests/inbox"
    assert marker["request_file_pattern"] == "mission_control_capture_request_*.json"
    assert marker["mac_may_write_arbitrary_files"] is False
    assert marker["backend_validates_before_write"] is True
    assert marker["network_required"] is False
    assert marker["backend_execution_allowed"] is False
    assert marker["tool_execution_allowed"] is False
    assert marker["model_execution_allowed"] is False
    assert marker["allowed_schema_files"] == list(MISSION_CONTROL_CAPTURE_INTAKE_READ_MODEL_FILES)
    assert manifest["approved_outbox_contracts"] == [marker]
    assert manifest["approved_capture_request_outbox_marker"] == "MISSION_CONTROL_CAPTURE_OUTBOX_CONTRACT.json"
    assert (package / "MISSION_CONTROL_CAPTURE_OUTBOX_CONTRACT.json").is_file()


def test_consolidation_batch_manifests_are_mirror_expected():
    expected = set(canonical_generated_read_model_expected_files())

    for name in [
        "make_winship_life_easier_batch_manifest.json",
        "make_winship_life_easier_batch_manifest_OPERATOR.md",
        "capital_hilton_proof_resolution_batch_manifest.json",
        "capital_hilton_proof_resolution_batch_manifest_OPERATOR.md",
        "openclaw_work_terrain_reconciliation_batch_manifest.json",
        "openclaw_work_terrain_reconciliation_batch_manifest_OPERATOR.md",
    ]:
        assert name in expected


def test_capital_hilton_review_packet_manifest_category(tmp_path):
    mac_root = tmp_path / "mac_generated"
    for name in MISSION_CONTROL_REVIEW_PACKET_READ_MODEL_FILES:
        _write(mac_root / name, f"{name}\n")
    for name in MISSION_CONTROL_CAPTURE_INTAKE_READ_MODEL_FILES:
        _write(mac_root / name, f"{name}\n")
    manifest_path = tmp_path / "mac_generated_read_models_manifest.json"

    manifest = build_mac_generated_read_model_manifest(
        destination_root=mac_root,
        output=manifest_path,
        generated_at="2026-05-17T14:00:00+00:00",
    )

    by_path = {record["relative_path"]: record for record in manifest["path_records"]}
    for name in MISSION_CONTROL_REVIEW_PACKET_READ_MODEL_FILES:
        assert by_path[name]["content_hash"]
        assert by_path[name]["evidence_category"] == "operator_review_packet"
    for name in MISSION_CONTROL_CAPTURE_INTAKE_READ_MODEL_FILES:
        assert by_path[name]["content_hash"]
        assert by_path[name]["evidence_category"] == "mission_control_capture_intake"


def test_import_script_logic_imports_fixture_manifest_without_moving_files(tmp_path):
    pc_root = tmp_path / "pc_openclaw"
    _write(pc_root / "generated" / "read_models" / "source_inventory.json", '{"same": true}\n')
    db_path = tmp_path / "ledger.sqlite"
    run_corpus_atlas(db_path=db_path, root=pc_root, run_id="pc_run")

    package = tmp_path / "returned_package"
    mac_root = tmp_path / "mac_generated"
    _write(mac_root / "source_inventory.json", '{"same": true}\n')
    _write(mac_root / "context_selection.json", '{"context": true}\n')
    returned_manifest = package / "mac_generated_read_models_manifest.json"
    build_mac_generated_read_model_manifest(
        destination_root=mac_root,
        output=returned_manifest,
        generated_at="2026-05-14T13:00:00+00:00",
    )

    result = import_mac_read_model_shuttle(
        package=package,
        db_path=db_path,
        import_manifest_path=tmp_path / "import_manifests" / "mac_generated_read_models_manifest.json",
        run_id="shuttle_import_fixture",
    )

    assert returned_manifest.is_file()
    assert Path(result.copied_manifest_path).is_file()
    assert result.root_id == "mac_generated_read_models"
    assert result.path_count >= 2
    assert result.matched_mirror_candidates >= 1
    rows = sqlite3.connect(db_path).execute(
        "SELECT COUNT(*) FROM corpus_paths WHERE root_id = 'mac_generated_read_models'"
    ).fetchone()
    assert rows[0] >= 2


def test_shuttle_sources_have_no_forbidden_external_or_destructive_behavior():
    paths = [
        Path("read_model_shuttle.py"),
        Path("scripts/prepare_mac_read_model_shuttle.py"),
        Path("scripts/import_mac_read_model_shuttle.py"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)

    forbidden = [
        "import subprocess",
        "shell=true",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "import paramiko",
        '["rsync"',
        '["scp"',
        '["ssh"',
        "git commit",
        "git push",
        ".unlink(",
        ".remove(",
        ".rmdir(",
        "docker run",
        "ollama run",
        "ollama pull",
    ]
    for token in forbidden:
        assert token not in text
