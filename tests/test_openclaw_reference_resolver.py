import json
import re
import sqlite3
import subprocess
from pathlib import Path

import openclaw_estate_topology_registry as estate_registry
import openclaw_reference_resolver as resolver
from scripts.export_openclaw_reference_resolver import main as export_main


FIXED_NOW = "2026-05-30T23:30:00+00:00"


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _init_repo(path: Path, *, branch: str = "main") -> Path:
    path.mkdir(parents=True)
    _git(path, "init")
    _git(path, "config", "user.email", "openclaw@example.invalid")
    _git(path, "config", "user.name", "OpenClaw Test")
    (path / "README.md").write_text("one\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "initial")
    _git(path, "branch", "-M", branch)
    return path


def _branch_target(repo: Path, *, branch: str = "main") -> resolver.ReferenceTargetSpec:
    return resolver.ReferenceTargetSpec(
        target_ref=resolver.OPENCLAW_EYES_REGISTRY_REVIEW_BRANCH_TARGET_REF,
        target_type="GIT_BRANCH",
        repo_ref="openclaw-eyes",
        local_path=repo.as_posix(),
        remote_url="",
        branch=branch,
        canonical_input={
            "repo_ref": "openclaw-eyes",
            "branch": branch,
        },
        refresh_policy="ON_EXPORT",
        owner_component="openclaw_estate_topology_registry",
    )


def _resolution_by_target(payload: dict, target_ref: str) -> dict:
    return {
        row["target_ref"]: row for row in payload["reference_resolutions"]
    }[target_ref]


def test_sqlite_tables_exist_after_export(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    read_root = tmp_path / "generated" / "read_models"
    system_root = tmp_path / "generated" / "system_knowledge"

    resolver.export_openclaw_reference_resolver(
        read_model_root=read_root,
        system_knowledge_root=system_root,
        generated_at=FIXED_NOW,
        reference_targets=(_branch_target(repo),),
        reference_dependencies=(),
    )

    connection = sqlite3.connect(system_root / resolver.SQLITE_EXPORT_NAME)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert "reference_target" in tables
        assert "reference_resolution" in tables
        assert set(resolver.REQUIRED_SQLITE_TABLES).issubset(tables)
    finally:
        connection.close()


def test_seed_target_records_openclaw_eyes_branch_as_canonical_ref():
    target = resolver.reference_target_record(resolver.DEFAULT_REFERENCE_TARGETS[0])
    canonical = json.loads(target["canonical_input_json"])

    assert target["target_ref"] == "openclaw_eyes_registry_review_branch"
    assert target["target_type"] == "GIT_BRANCH"
    assert target["repo_ref"] == "openclaw-eyes"
    assert target["local_path"] == "/home/openclaw"
    assert target["remote_url"] == "git@github.com:WinshipWheatley/openclaw-eyes.git"
    assert target["branch"] == "codex/system-knowledge-registry-v0-local"
    assert target["mac_mirror_path"] == "/Users/hwinshipwheatley/Eyes"
    assert canonical == {
        "branch": "codex/system-knowledge-registry-v0-local",
        "repo_ref": "openclaw-eyes",
        "remote_url": "git@github.com:WinshipWheatley/openclaw-eyes.git",
    }


def test_seed_target_records_openclaw_eyes_main_as_remote_only_canonical_probe():
    targets = {target.target_ref: target for target in resolver.DEFAULT_REFERENCE_TARGETS}
    target = resolver.reference_target_record(
        targets[resolver.OPENCLAW_EYES_MAIN_BRANCH_TARGET_REF]
    )
    canonical = json.loads(target["canonical_input_json"])
    dependency_targets = {
        dependency.target_ref for dependency in resolver.DEFAULT_REFERENCE_DEPENDENCIES
    }

    assert target["target_ref"] == "openclaw_eyes_main_branch"
    assert target["target_type"] == "GIT_BRANCH"
    assert target["repo_ref"] == "openclaw-eyes-main"
    assert target["local_path"] == ""
    assert target["remote_url"] == "git@github.com:WinshipWheatley/openclaw-eyes.git"
    assert target["branch"] == "main"
    assert canonical == {
        "branch": "main",
        "repo_ref": "openclaw-eyes",
        "remote_url": "git@github.com:WinshipWheatley/openclaw-eyes.git",
    }
    assert resolver.OPENCLAW_EYES_MAIN_BRANCH_TARGET_REF in dependency_targets


def test_generated_output_contains_resolved_current_head_commit(tmp_path):
    repo = _init_repo(tmp_path / "repo", branch="codex/system-knowledge-registry-v0-local")
    expected = _git(repo, "rev-parse", "codex/system-knowledge-registry-v0-local")

    payload = resolver.build_openclaw_reference_resolver(
        generated_at=FIXED_NOW,
        reference_targets=(_branch_target(repo, branch="codex/system-knowledge-registry-v0-local"),),
        reference_dependencies=(),
    )
    row = _resolution_by_target(payload, resolver.OPENCLAW_EYES_REGISTRY_REVIEW_BRANCH_TARGET_REF)
    resolved_json = json.loads(row["resolved_json"])

    assert row["resolved_status"] == "RESOLVED_LOCAL"
    assert row["resolved_value"] == expected
    assert resolved_json["current_head_commit"] == expected
    assert resolved_json["resolution_source"] == "local_working_copy"


def test_source_registry_does_not_hardcode_stale_commit_as_canonical_fact():
    estate_source = Path("openclaw_estate_topology_registry.py").read_text(encoding="utf-8")
    resolver_source = Path("openclaw_reference_resolver.py").read_text(encoding="utf-8")

    hardcoded_review_commit = re.compile(r"(review_commit|commit_ref)=\"[a-f0-9]{40}\"")
    assert hardcoded_review_commit.search(estate_source) is None
    assert hardcoded_review_commit.search(resolver_source) is None


def test_mac_only_local_path_becomes_local_path_unreachable_from_pc():
    target = resolver.ReferenceTargetSpec(
        target_ref="mac_only_branch",
        target_type="GIT_BRANCH",
        repo_ref="openclaw-eyes",
        local_path="/Users/hwinshipwheatley/Eyes",
        branch="codex/system-knowledge-registry-v0-local",
        owner_component="test",
    )

    payload = resolver.build_openclaw_reference_resolver(
        generated_at=FIXED_NOW,
        reference_targets=(target,),
        reference_dependencies=(),
    )
    row = _resolution_by_target(payload, "mac_only_branch")
    resolved_json = json.loads(row["resolved_json"])

    assert row["resolved_status"] == "LOCAL_PATH_UNREACHABLE"
    assert row["resolved_value"] == ""
    assert resolved_json["local_status"] == "LOCAL_PATH_UNREACHABLE"
    assert "local path" in row["error_message"].lower()


def test_remote_branch_resolution_uses_read_only_remote_ref(tmp_path):
    repo = _init_repo(tmp_path / "remote", branch="review")
    expected = _git(repo, "rev-parse", "review")
    target = resolver.ReferenceTargetSpec(
        target_ref="remote_branch",
        target_type="GIT_BRANCH",
        repo_ref="openclaw-eyes",
        local_path="",
        remote_url=repo.as_posix(),
        branch="review",
        canonical_input={
            "repo_ref": "openclaw-eyes",
            "remote_url": repo.as_posix(),
            "branch": "review",
        },
        owner_component="test",
    )

    payload = resolver.build_openclaw_reference_resolver(
        generated_at=FIXED_NOW,
        reference_targets=(target,),
        reference_dependencies=(),
    )
    row = _resolution_by_target(payload, "remote_branch")
    resolved_json = json.loads(row["resolved_json"])

    assert row["resolved_status"] == "RESOLVED_REMOTE"
    assert row["resolved_value"] == expected
    assert resolved_json["resolution_source"] == "configured_remote"
    assert resolved_json["remote_status"] == "RESOLVED_REMOTE"


def test_local_and_remote_resolutions_are_distinguished(tmp_path):
    local_repo = _init_repo(tmp_path / "local", branch="review")
    remote_repo = _init_repo(tmp_path / "remote", branch="review")
    local_target = resolver.ReferenceTargetSpec(
        target_ref="local_branch",
        target_type="GIT_BRANCH",
        repo_ref="openclaw-eyes",
        local_path=local_repo.as_posix(),
        branch="review",
        owner_component="test",
    )
    remote_target = resolver.ReferenceTargetSpec(
        target_ref="remote_branch",
        target_type="GIT_BRANCH",
        repo_ref="openclaw-eyes",
        remote_url=remote_repo.as_posix(),
        branch="review",
        owner_component="test",
    )

    payload = resolver.build_openclaw_reference_resolver(
        generated_at=FIXED_NOW,
        reference_targets=(local_target, remote_target),
        reference_dependencies=(),
    )

    assert _resolution_by_target(payload, "local_branch")["resolved_status"] == "RESOLVED_LOCAL"
    assert _resolution_by_target(payload, "remote_branch")["resolved_status"] == "RESOLVED_REMOTE"


def test_unavailable_remote_becomes_remote_unavailable_not_invented(tmp_path):
    missing_remote = tmp_path / "missing-remote"
    target = resolver.ReferenceTargetSpec(
        target_ref="missing_remote_branch",
        target_type="GIT_BRANCH",
        repo_ref="openclaw-eyes",
        local_path="",
        remote_url=missing_remote.as_posix(),
        branch="review",
        owner_component="test",
    )

    payload = resolver.build_openclaw_reference_resolver(
        generated_at=FIXED_NOW,
        reference_targets=(target,),
        reference_dependencies=(),
    )
    row = _resolution_by_target(payload, "missing_remote_branch")

    assert row["resolved_status"] == "REMOTE_UNAVAILABLE"
    assert row["resolved_value"] == ""
    assert "configured_remote" in row["error_message"]


def test_existing_local_worktree_missing_branch_is_unreachable_not_path_unreachable(tmp_path):
    repo = _init_repo(tmp_path / "repo")

    payload = resolver.build_openclaw_reference_resolver(
        generated_at=FIXED_NOW,
        reference_targets=(_branch_target(repo, branch="missing-branch"),),
        reference_dependencies=(),
    )
    row = _resolution_by_target(payload, resolver.OPENCLAW_EYES_REGISTRY_REVIEW_BRANCH_TARGET_REF)
    resolved_json = json.loads(row["resolved_json"])

    assert row["resolved_status"] == "UNREACHABLE"
    assert resolved_json["local_status"] == "UNREACHABLE"
    assert row["resolved_value"] == ""


def test_dirty_repo_becomes_dirty(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    (repo / "untracked.txt").write_text("dirty\n", encoding="utf-8")

    payload = resolver.build_openclaw_reference_resolver(
        generated_at=FIXED_NOW,
        reference_targets=(_branch_target(repo),),
        reference_dependencies=(),
    )
    row = _resolution_by_target(payload, resolver.OPENCLAW_EYES_REGISTRY_REVIEW_BRANCH_TARGET_REF)

    assert row["resolved_status"] == "RESOLVED_LOCAL"
    assert row["dirty_status"] == "DIRTY"
    assert row["resolved_value"] == _git(repo, "rev-parse", "main")


def test_source_bridge_hash_mismatch_becomes_drift(tmp_path):
    source = tmp_path / "source.json"
    bridge = tmp_path / "bridge.json"
    source.write_text('{"ok": true}\n', encoding="utf-8")
    bridge.write_text('{"ok": false}\n', encoding="utf-8")
    target = resolver.ReferenceTargetSpec(
        target_ref="mirror_pair",
        target_type="READ_MODEL_MIRROR",
        source_path=source.as_posix(),
        bridge_path=bridge.as_posix(),
        owner_component="test",
    )

    payload = resolver.build_openclaw_reference_resolver(
        generated_at=FIXED_NOW,
        reference_targets=(target,),
        reference_dependencies=(),
    )
    row = _resolution_by_target(payload, "mirror_pair")

    assert row["resolved_status"] == "DRIFT"
    assert payload["drift_count"] == 1
    assert payload["drift_events"][0]["target_ref"] == "mirror_pair"


def test_estate_topology_registry_consumes_resolver_output(tmp_path):
    repo = _init_repo(tmp_path / "repo", branch="codex/system-knowledge-registry-v0-local")
    first_commit = _git(repo, "rev-parse", "codex/system-knowledge-registry-v0-local")
    resolver_payload = resolver.build_openclaw_reference_resolver(
        generated_at=FIXED_NOW,
        reference_targets=(_branch_target(repo, branch="codex/system-knowledge-registry-v0-local"),),
        reference_dependencies=(),
    )

    estate_payload = estate_registry.build_openclaw_estate_topology_registry(
        generated_at=FIXED_NOW,
        reference_resolver_payload=resolver_payload,
    )
    area = {
        row["area_id"]: row for row in estate_payload["source_of_truth_areas"]
    }["evidence_grounded_context_registry"]

    assert area["review_branch"] == "codex/system-knowledge-registry-v0-local"
    assert area["review_commit"] == first_commit
    assert area["status"] == "PRESENT_ON_REVIEW_BRANCH"


def test_changing_mocked_branch_head_changes_generated_output(tmp_path):
    repo = _init_repo(tmp_path / "repo", branch="codex/system-knowledge-registry-v0-local")
    target = resolver.ReferenceTargetSpec(
        target_ref=resolver.OPENCLAW_EYES_REGISTRY_REVIEW_BRANCH_TARGET_REF,
        target_type="GIT_BRANCH",
        repo_ref="openclaw-eyes",
        local_path="",
        remote_url=repo.as_posix(),
        branch="codex/system-knowledge-registry-v0-local",
        canonical_input={
            "repo_ref": "openclaw-eyes",
            "remote_url": repo.as_posix(),
            "branch": "codex/system-knowledge-registry-v0-local",
        },
        refresh_policy="ON_EXPORT",
        owner_component="openclaw_estate_topology_registry",
    )

    first = resolver.build_openclaw_reference_resolver(
        generated_at=FIXED_NOW,
        reference_targets=(target,),
        reference_dependencies=(),
    )
    first_commit = _resolution_by_target(
        first, resolver.OPENCLAW_EYES_REGISTRY_REVIEW_BRANCH_TARGET_REF
    )["resolved_value"]

    (repo / "README.md").write_text("two\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "second")

    second = resolver.build_openclaw_reference_resolver(
        generated_at=FIXED_NOW,
        reference_targets=(target,),
        reference_dependencies=(),
    )
    second_commit = _resolution_by_target(
        second, resolver.OPENCLAW_EYES_REGISTRY_REVIEW_BRANCH_TARGET_REF
    )["resolved_value"]

    assert first_commit != second_commit
    assert second_commit == _git(repo, "rev-parse", "codex/system-knowledge-registry-v0-local")


def test_export_writes_json_operator_sqlite_schema_seed_and_cli_outputs(tmp_path, capsys):
    repo = _init_repo(tmp_path / "repo")
    read_root = tmp_path / "generated" / "read_models"
    system_root = tmp_path / "generated" / "system_knowledge"
    result = resolver.export_openclaw_reference_resolver(
        read_model_root=read_root,
        system_knowledge_root=system_root,
        generated_at=FIXED_NOW,
        reference_targets=(_branch_target(repo),),
        reference_dependencies=(),
    )

    assert result.target_count == 1
    assert result.resolution_count == 1
    assert (read_root / resolver.JSON_EXPORT_NAME).exists()
    assert (read_root / resolver.OPERATOR_EXPORT_NAME).exists()
    assert (system_root / resolver.SQLITE_EXPORT_NAME).exists()
    assert (system_root / resolver.SCHEMA_EXPORT_NAME).exists()
    assert (system_root / resolver.SEED_EXPORT_NAME).exists()
    assert "CREATE TABLE reference_target" in (system_root / resolver.SCHEMA_EXPORT_NAME).read_text(
        encoding="utf-8"
    )
    assert "INSERT INTO reference_target" in (system_root / resolver.SEED_EXPORT_NAME).read_text(
        encoding="utf-8"
    )

    assert export_main(
        [
            "--read-model-root",
            str(read_root),
            "--system-knowledge-root",
            str(system_root),
            "--format",
            "json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == resolver.READ_MODEL_VERSION


def test_source_does_not_call_forbidden_live_surfaces():
    source_files = [
        Path("openclaw_reference_resolver.py"),
        Path("scripts/export_openclaw_reference_resolver.py"),
    ]
    forbidden = [
        "git push",
        "git fetch",
        "git pull",
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
        "systemctl",
        "launchctl",
        "shell=True",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for forbidden_text in forbidden:
            assert forbidden_text not in text

    payload = resolver.build_openclaw_reference_resolver(
        generated_at=FIXED_NOW,
        reference_targets=(),
        reference_dependencies=(),
    )
    for key, expected in resolver.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
