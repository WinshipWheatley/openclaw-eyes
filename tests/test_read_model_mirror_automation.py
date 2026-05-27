import json
from pathlib import Path

import pytest

from corpus_atlas import run_corpus_atlas
from generated_read_model_files import (
    HELM_DECLUTTER_BRIDGE_READ_MODEL_FILES,
    MISSION_CONTROL_CAPTURE_INTAKE_READ_MODEL_FILES,
    MISSION_CONTROL_REVIEW_PACKET_READ_MODEL_FILES,
)
from read_model_shuttle import DEFAULT_RETURNED_MANIFEST_PATH, build_mac_generated_read_model_manifest
from scripts.import_latest_mac_read_model_mirror import (
    CRITICAL_READ_MODEL_FILES,
    critical_files_from_manifest,
    import_latest_mac_read_model_mirror,
    parse_args as parse_import_args,
)
from scripts.mac_sync_generated_read_models import (
    KEY_READ_MODEL_FILES,
    MAC_SHARE_ROOT,
    sync_generated_read_models,
)


def _write(path: Path, text: str = "{}\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo_fixture(tmp_path: Path) -> Path:
    repo = tmp_path / "openclaw"
    read_models = repo / "generated" / "read_models"
    read_models.mkdir(parents=True)
    for name in (
        "source_inventory.json",
        "helm_state.json",
        "operator_actions.json",
        "agent_lanes.json",
        "project_capsules.json",
        "report_bridge.json",
        "context_selection.json",
        "context_selection_OPERATOR.md",
        "generated_current_state.md",
        "source_inventory.operator.txt",
        *HELM_DECLUTTER_BRIDGE_READ_MODEL_FILES,
        *MISSION_CONTROL_REVIEW_PACKET_READ_MODEL_FILES,
        *MISSION_CONTROL_CAPTURE_INTAKE_READ_MODEL_FILES,
    ):
        _write(read_models / name, f"{name}\n")
    _write(read_models / "mac_generated_read_models_manifest.json", "{}\n")
    _write(read_models / "ledger.sqlite", "not a read model\n")
    _write(read_models / "secret_token.json", "{}\n")
    _write(read_models / ".hidden.json", "{}\n")
    _write(read_models / "scratch.tmp", "tmp\n")
    _write(read_models / "nested" / "nested.json", "{}\n")
    return repo


def test_mac_sync_selects_safe_generated_read_models_only_without_share(tmp_path):
    repo = _repo_fixture(tmp_path)
    destination = tmp_path / "mac_generated"
    local_manifest = tmp_path / "desktop" / "mac_generated_read_models_manifest.json"
    missing_share = tmp_path / "missing_share"

    report = sync_generated_read_models(
        repo_root=repo,
        destination_root=destination,
        local_manifest_path=local_manifest,
        share_root=missing_share,
        platform_name="Darwin",
    )

    copied = {item["relative_path"] for item in report["copied_files"]}
    assert {"operator_actions.json", "agent_lanes.json", "context_selection.json"} <= copied
    assert "mac_generated_read_models_manifest.json" not in copied
    assert "ledger.sqlite" not in copied
    assert "secret_token.json" not in copied
    assert ".hidden.json" not in copied
    assert "scratch.tmp" not in copied
    assert "nested/nested.json" not in copied
    assert local_manifest.is_file()
    assert report["pc_drop_written"] is False
    assert report["share_mounted"] is False
    for name in KEY_READ_MODEL_FILES:
        assert report["key_files_present"][name] is True


def test_mac_sync_can_require_share_or_write_report_when_share_exists(tmp_path):
    repo = _repo_fixture(tmp_path)
    destination = tmp_path / "mac_generated"
    local_manifest = tmp_path / "desktop" / "mac_generated_read_models_manifest.json"

    with pytest.raises(RuntimeError, match="required Mac share is not mounted"):
        sync_generated_read_models(
            repo_root=repo,
            destination_root=destination,
            local_manifest_path=local_manifest,
            share_root=tmp_path / "missing_share",
            require_share=True,
            platform_name="Darwin",
        )

    share = tmp_path / "openclaw_e"
    share.mkdir()
    report = sync_generated_read_models(
        repo_root=repo,
        destination_root=destination,
        local_manifest_path=local_manifest,
        share_root=share,
        require_share=True,
        platform_name="Darwin",
    )

    assert report["pc_drop_written"] is True
    assert (share / "mac_generated_read_models_manifest.json").is_file()
    assert (share / "shuttle" / "from_mac" / "read_model_sync_latest.json").is_file()
    dropped_report = json.loads(
        (share / "shuttle" / "from_mac" / "read_model_sync_latest.json").read_text(encoding="utf-8")
    )
    assert dropped_report["manifest_sha256"] == report["manifest_sha256"]


def test_mac_sync_rejects_non_mac_platform(tmp_path):
    repo = _repo_fixture(tmp_path)

    with pytest.raises(RuntimeError, match="must run on macOS"):
        sync_generated_read_models(
            repo_root=repo,
            destination_root=tmp_path / "mac_generated",
            local_manifest_path=tmp_path / "manifest.json",
            share_root=tmp_path / "share",
            platform_name="Linux",
        )


def test_pc_import_helper_defaults_to_e_drive_not_c_drive():
    args = parse_import_args([])

    assert args.manifest == DEFAULT_RETURNED_MANIFEST_PATH.as_posix()
    assert args.manifest == "/mnt/e/openclaw/mac_generated_read_models_manifest.json"
    assert not args.manifest.startswith("/mnt/c/openclaw")
    assert MAC_SHARE_ROOT.as_posix() == "/Volumes/openclaw_e"


def test_pc_import_helper_imports_fixture_manifest_and_reports_critical_files(tmp_path):
    pc_root = tmp_path / "pc_openclaw"
    _write(pc_root / "generated" / "read_models" / "source_inventory.json", '{"same": true}\n')
    db_path = tmp_path / "ledger.sqlite"
    run_corpus_atlas(db_path=db_path, root=pc_root, run_id="pc_run")

    mac_root = tmp_path / "mac_generated"
    _write(mac_root / "source_inventory.json", '{"same": true}\n')
    for name in CRITICAL_READ_MODEL_FILES:
        _write(mac_root / name, f"{name}\n")
    manifest = tmp_path / "e" / "openclaw" / "mac_generated_read_models_manifest.json"
    build_mac_generated_read_model_manifest(
        destination_root=mac_root,
        output=manifest,
        generated_at="2026-05-15T12:00:00+00:00",
    )

    critical = critical_files_from_manifest(manifest)
    assert all(critical.values())

    payload = import_latest_mac_read_model_mirror(
        manifest=manifest,
        db_path=db_path,
        import_manifest_path=tmp_path / "import_manifests" / "mac_generated_read_models_manifest.json",
        run_id="latest_import_fixture",
    )

    assert payload["root_id"] == "mac_generated_read_models"
    assert payload["path_count"] >= len(CRITICAL_READ_MODEL_FILES)
    assert payload["matched_mirror_candidates"] >= 1
    assert all(payload["critical_files"].values())
    assert payload["raw_file_bodies_imported"] is False
    assert payload["canonical_truth_promoted"] is False


def test_mirror_automation_sources_have_no_c_drive_remote_or_destructive_defaults():
    paths = [
        Path("scripts/mac_sync_generated_read_models.py"),
        Path("scripts/import_latest_mac_read_model_mirror.py"),
        Path("docs/operations/OPENCLAW_READ_MODEL_MIRROR_AUTOMATION_V0.md"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)

    forbidden = [
        "/mnt/c/openclaw",
        "c:\\openclaw",
        "rsync ",
        "scp ",
        "ssh ",
        "launchctl",
        "/library/launchagents",
        "~/library/launchagents",
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
