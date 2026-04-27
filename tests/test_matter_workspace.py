from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legal.matter_workspace import (
    REQUIRED_DIRECTORIES,
    create_matter_workspace,
    import_staging_sources,
    load_matter_workspace,
    register_source,
)
from legal.path_guard import PRODUCT_REPO_ROOT, LegalPathError


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_audit(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_matter_creation_writes_valid_manifest(tmp_path: Path) -> None:
    root = tmp_path / "matter-001"

    workspace = create_matter_workspace(
        root,
        matter_id="matter-001",
        display_name="Example Matter",
        created_at="2026-04-23T12:00:00Z",
    )

    assert workspace.matter_id == "matter-001"
    assert workspace.display_name == "Example Matter"
    assert workspace.root_path == str(root)
    manifest = _read_json(root / "manifest.json")
    assert manifest == {
        "matter_id": "matter-001",
        "display_name": "Example Matter",
        "created_at": "2026-04-23T12:00:00Z",
        "root_path": str(root),
        "sources": [],
    }
    assert load_matter_workspace(root) == workspace


def test_create_rejects_matter_workspace_under_product_repo() -> None:
    root = PRODUCT_REPO_ROOT / "legal-forbidden-matter"

    with pytest.raises(LegalPathError, match="outside product repo"):
        create_matter_workspace(root, "matter", "Matter")

    assert not root.exists()


def test_create_allows_synthetic_temp_matter_workspace(tmp_path: Path) -> None:
    root = tmp_path / "synthetic-matter"

    workspace = create_matter_workspace(root, "matter", "Matter")

    assert workspace.root_path == str(root)
    assert (root / "manifest.json").is_file()


def test_create_allows_matter_workspace_under_approved_vault_root(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "legal-vault"
    root = vault / "matter"

    workspace = create_matter_workspace(
        root,
        "matter",
        "Matter",
        allowed_vault_roots=[vault],
    )

    assert workspace.root_path == str(root)
    assert workspace.allowed_vault_roots == (str(vault),)
    assert (root / "manifest.json").is_file()


def test_create_rejects_vault_root_under_product_repo(tmp_path: Path) -> None:
    vault = PRODUCT_REPO_ROOT / "legal-forbidden-vault"
    root = tmp_path / "matter"

    with pytest.raises(LegalPathError, match="vault root must be outside product repo"):
        create_matter_workspace(
            root,
            "matter",
            "Matter",
            allowed_vault_roots=[vault],
        )


def test_create_rejects_matter_root_outside_approved_vault_root(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "legal-vault"
    root = tmp_path / "outside" / "matter"

    with pytest.raises(LegalPathError, match="approved legal vault root"):
        create_matter_workspace(
            root,
            "matter",
            "Matter",
            allowed_vault_roots=[vault],
        )


def test_create_rejects_symlink_vault_root_into_product_repo(tmp_path: Path) -> None:
    vault = tmp_path / "vault-link"
    vault.symlink_to(PRODUCT_REPO_ROOT, target_is_directory=True)
    root = vault / "legal-forbidden-matter"

    with pytest.raises(LegalPathError, match="vault root must be outside product repo"):
        create_matter_workspace(
            root,
            "matter",
            "Matter",
            allowed_vault_roots=[vault],
        )

    assert not (PRODUCT_REPO_ROOT / "legal-forbidden-matter").exists()


def test_create_rejects_symlink_traversal_into_product_repo(tmp_path: Path) -> None:
    repo_link = tmp_path / "repo-link"
    repo_link.symlink_to(PRODUCT_REPO_ROOT, target_is_directory=True)
    root = repo_link / "legal-forbidden-matter"

    with pytest.raises(LegalPathError, match="outside product repo"):
        create_matter_workspace(root, "matter", "Matter")

    assert not (PRODUCT_REPO_ROOT / "legal-forbidden-matter").exists()


def test_required_folders_and_audit_file_exist(tmp_path: Path) -> None:
    root = tmp_path / "matter"

    create_matter_workspace(root, "matter", "Matter")

    assert (root / "manifest.json").is_file()
    assert (root / "audit.jsonl").is_file()
    for directory in REQUIRED_DIRECTORIES:
        assert (root / directory).is_dir()


def test_source_registration_copies_file_and_preserves_original(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "source.txt"
    source.write_text("original evidence\n", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")

    entry = register_source(root, source)

    stored = Path(entry["stored_path"])
    assert entry["original_filename"] == "source.txt"
    assert entry["file_type"] == "text/plain"
    assert stored.is_file()
    assert stored.read_text(encoding="utf-8") == "original evidence\n"
    assert source.read_text(encoding="utf-8") == "original evidence\n"
    assert stored != source
    manifest = _read_json(root / "manifest.json")
    assert manifest["sources"] == [entry]


def test_import_staging_rejects_staging_dir_inside_product_repo(
    tmp_path: Path,
) -> None:
    product_root = tmp_path / "repo"
    product_root.mkdir()
    vault = tmp_path / "legal-vault"
    root = vault / "matter"
    staging = product_root / "staging"
    staging.mkdir()
    create_matter_workspace(root, "matter", "Matter", allowed_vault_roots=[vault])

    with patch("legal.matter_workspace.PRODUCT_REPO_ROOT", product_root):
        with pytest.raises(LegalPathError, match="staging dir must be outside"):
            import_staging_sources(
                root,
                staging,
                lane="synthetic",
                allowed_vault_roots=[vault],
            )


def test_import_staging_rejects_symlink_escape(tmp_path: Path) -> None:
    vault = tmp_path / "legal-vault"
    root = vault / "matter"
    staging = tmp_path / "staging"
    outside = tmp_path / "outside.txt"
    staging.mkdir()
    outside.write_text("outside", encoding="utf-8")
    (staging / "outside-link.txt").symlink_to(outside)
    create_matter_workspace(root, "matter", "Matter", allowed_vault_roots=[vault])

    with pytest.raises(LegalPathError, match="escapes"):
        import_staging_sources(
            root,
            staging,
            lane="synthetic",
            allowed_vault_roots=[vault],
        )


def test_import_staging_skips_directories(tmp_path: Path) -> None:
    vault = tmp_path / "legal-vault"
    root = vault / "matter"
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "nested").mkdir()
    (staging / "source.txt").write_text("source", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter", allowed_vault_roots=[vault])

    result = import_staging_sources(
        root,
        staging,
        lane="synthetic",
        allowed_vault_roots=[vault],
    )

    assert result["source_count_imported"] == 1
    assert result["skipped_directory_count"] == 1
    assert result["staging_dir_present"] is True
    assert "staging_dir" not in result
    manifest = _read_json(root / "manifest.json")
    assert [source["original_filename"] for source in manifest["sources"]] == [
        "source.txt"
    ]


def test_real_matter_import_rejects_marked_synthetic_fixture_pack(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "legal-vault"
    root = vault / "matter"
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / ".openclaw-synthetic-fixture-pack").write_text("", encoding="utf-8")
    (staging / "source.txt").write_text("source", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter", allowed_vault_roots=[vault])

    with pytest.raises(ValueError, match="synthetic fixture pack"):
        import_staging_sources(
            root,
            staging,
            lane="real-matter",
            allowed_vault_roots=[vault],
        )

    assert _read_json(root / "manifest.json")["sources"] == []


def test_stable_sha256_and_source_id_for_same_content(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    first = tmp_path / "first.txt"
    second = tmp_path / "renamed.txt"
    first.write_text("same bytes", encoding="utf-8")
    second.write_text("same bytes", encoding="utf-8")
    workspace = create_matter_workspace(root, "matter", "Matter")

    first_entry = workspace.register_source(first)
    second_entry = workspace.register_source(second)

    assert first_entry == second_entry
    assert first_entry["source_id"].startswith("src_")
    assert len(first_entry["sha256"]) == 64
    assert first_entry["source_id"] == f"src_{first_entry['sha256'][:12]}"
    manifest = _read_json(root / "manifest.json")
    assert len(manifest["sources"]) == 1


def test_source_id_collision_extends_prefix_for_distinct_content(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "source.txt"
    source.write_text("new content", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    digest = "abcdef1234569" + "0" * 51
    manifest = _read_json(root / "manifest.json")
    manifest["sources"].append(
        {
            "source_id": "src_abcdef123456",
            "original_filename": "existing.txt",
            "stored_path": str(root / "sources" / "src_abcdef123456.txt"),
            "sha256": "abcdef1234568" + "0" * 51,
            "file_type": "text/plain",
            "added_at": "2026-04-23T12:00:00Z",
        }
    )
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with patch("legal.matter_workspace._sha256_file", return_value=digest):
        entry = register_source(root, source)

    assert entry["source_id"] == "src_abcdef1234569"
    manifest = _read_json(root / "manifest.json")
    assert {source["source_id"] for source in manifest["sources"]} == {
        "src_abcdef123456",
        "src_abcdef1234569",
    }


def test_audit_log_appends_jsonl_entries(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "source.txt"
    source.write_text("evidence", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    initial_audit = (root / "audit.jsonl").read_text(encoding="utf-8")

    entry = register_source(root, source)

    final_audit = (root / "audit.jsonl").read_text(encoding="utf-8")
    assert final_audit.startswith(initial_audit)
    events = _read_audit(root / "audit.jsonl")
    assert [event["event"] for event in events] == [
        "matter_created",
        "source_registered",
    ]
    assert events[1]["source_id"] == entry["source_id"]


def test_two_matter_workspaces_are_isolated(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    source = tmp_path / "source.txt"
    source.write_text("shared source", encoding="utf-8")
    create_matter_workspace(first_root, "first", "First")
    create_matter_workspace(second_root, "second", "Second")

    first_entry = register_source(first_root, source)
    second_entry = register_source(second_root, source)

    assert Path(first_entry["stored_path"]).is_relative_to(first_root)
    assert Path(second_entry["stored_path"]).is_relative_to(second_root)
    assert _read_json(first_root / "manifest.json")["matter_id"] == "first"
    assert _read_json(second_root / "manifest.json")["matter_id"] == "second"
    assert _read_audit(first_root / "audit.jsonl") != _read_audit(
        second_root / "audit.jsonl"
    )


def test_no_network_calls_during_create_or_register(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "source.txt"
    source.write_text("offline only", encoding="utf-8")

    with patch.object(socket, "create_connection", side_effect=AssertionError):
        create_matter_workspace(root, "matter", "Matter")
        register_source(root, source)


def test_create_refuses_to_overwrite_existing_manifest(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    create_matter_workspace(root, "matter", "Matter")

    with pytest.raises(FileExistsError):
        create_matter_workspace(root, "matter", "Matter")
