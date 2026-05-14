import json
import sqlite3
from pathlib import Path

from corpus_atlas import run_corpus_atlas
from read_model_shuttle import (
    NO_AUTHORITY_FLAGS,
    build_mac_generated_read_model_manifest,
    import_mac_read_model_shuttle,
    mac_apply_script,
    prepare_mac_read_model_shuttle,
)


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
    assert (package / "APPLY_ON_MAC.sh").is_file()
    assert (package / "README.md").is_file()
    assert result.file_count >= 15


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
    assert "mac_generated_read_models_manifest.json" not in names
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
