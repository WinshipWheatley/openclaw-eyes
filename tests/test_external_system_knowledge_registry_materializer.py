import json
import sqlite3
import subprocess
from pathlib import Path

import openclaw_external_registry_materializer as materializer
from openclaw_context_wiki_compiler import compile_openclaw_context_wiki
from scripts.import_external_system_knowledge_registry import main as import_main


FIXED_NOW = "2026-05-31T12:00:00+00:00"


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _init_registry_repo(path: Path) -> tuple[Path, str]:
    path.mkdir(parents=True)
    _git(path, "init")
    _git(path, "config", "user.email", "openclaw@example.invalid")
    _git(path, "config", "user.name", "OpenClaw Test")
    _write_json(
        path / "generated/read_models/openclaw_system_knowledge_registry.json",
        {
            "schema_version": "openclaw_system_knowledge_registry_v0",
            "facts": [{"fact_id": "registry_owner", "value": "openclaw-eyes"}],
        },
    )
    (path / "generated/read_models/openclaw_system_knowledge_registry_OPERATOR.md").write_text(
        "# OpenClaw System Knowledge Registry\n\n- Canonical owner: openclaw-eyes\n",
        encoding="utf-8",
    )
    db_path = path / "generated/system_knowledge/openclaw_system_knowledge_registry.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("CREATE TABLE fact (fact_id TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO fact VALUES ('registry_owner', 'openclaw-eyes')")
        connection.commit()
    finally:
        connection.close()
    (path / "generated/system_knowledge/openclaw_system_knowledge_registry_SCHEMA.sql").write_text(
        "CREATE TABLE fact (fact_id TEXT PRIMARY KEY, value TEXT NOT NULL);\n",
        encoding="utf-8",
    )
    (path / "generated/system_knowledge/openclaw_system_knowledge_registry_SEED.sql").write_text(
        "INSERT INTO fact VALUES ('registry_owner', 'openclaw-eyes');\n",
        encoding="utf-8",
    )
    _git(path, "add", ".")
    _git(path, "commit", "-m", "registry artifacts")
    _git(path, "branch", "-M", "main")
    return path, _git(path, "rev-parse", "HEAD")


def _resolver_payload(commit: str) -> dict:
    branch_row = {
        "target_ref": "openclaw_eyes_main_branch",
        "repo_ref": "openclaw-eyes-main",
        "repo_name": "openclaw-eyes-main",
        "local_path": "",
        "remote_url": "git@example.invalid:openclaw-eyes.git",
        "branch": "main",
        "current_head_commit": commit,
        "reachable": True,
        "resolution_status": "RESOLVED_REMOTE",
        "resolution_source": "test_fixture",
        "remote_status": "RESOLVED_REMOTE",
        "dirty_status": "UNKNOWN",
    }
    return {
        "schema_version": "openclaw_reference_resolver_read_model_v0",
        "generated_at": FIXED_NOW,
        "git_branch_refs": [branch_row],
        "reference_resolutions": [
            {
                "target_ref": "openclaw_eyes_main_branch",
                "resolved_status": "RESOLVED_REMOTE",
                "resolved_value": commit,
                "resolved_json": json.dumps(branch_row, sort_keys=True),
            }
        ],
    }


def _materialize(tmp_path: Path) -> tuple[dict, str]:
    source_repo, commit = _init_registry_repo(tmp_path / "source-openclaw-eyes")
    index = materializer.build_external_system_knowledge_registry_index(
        repo_root=tmp_path,
        source_checkout=source_repo,
        reference_resolver_payload=_resolver_payload(commit),
        generated_at=FIXED_NOW,
        allow_network=False,
    )
    return index, commit


def test_materializer_imports_registry_artifacts_from_mocked_checkout(tmp_path):
    index, commit = _materialize(tmp_path)

    assert index["import_status"] == "IMPORTED"
    assert index["source_repo"] == "openclaw-eyes"
    assert index["source_branch"] == "main"
    assert index["source_commit"] == commit
    assert index["canonical_owner"] == "openclaw-eyes"
    assert index["local_role"] == "READ_ONLY_EXTERNAL_INPUT"
    assert index["artifact_count"] == len(materializer.EXPECTED_ARTIFACTS)
    for _artifact_type, _source_rel, output_name in materializer.EXPECTED_ARTIFACTS:
        assert (tmp_path / "generated/external_registries/openclaw-eyes" / output_name).is_file()


def test_imported_artifacts_include_source_commit_and_sha256(tmp_path):
    index, commit = _materialize(tmp_path)

    assert index["resolver_commit"] == commit
    assert index["commit_match"] is True
    assert all(artifact["sha256"].startswith("sha256:") for artifact in index["artifacts"])
    assert all(artifact["cache_path"].startswith("generated/external_registries/openclaw-eyes/") for artifact in index["artifacts"])


def test_home_openclaw_is_not_marked_canonical_owner(tmp_path):
    index, _commit = _materialize(tmp_path)

    assert index["canonical_owner"] == "openclaw-eyes"
    assert index["local_role"] == "READ_ONLY_EXTERNAL_INPUT"
    assert index["canonical_owner"] != "/home/openclaw"
    assert index["canonical_owner_changed"] is False


def test_missing_external_source_is_reported_not_invented(tmp_path):
    index = materializer.build_external_system_knowledge_registry_index(
        repo_root=tmp_path,
        source_checkout=tmp_path / "missing",
        reference_resolver_payload=_resolver_payload("a" * 40),
        generated_at=FIXED_NOW,
        allow_network=False,
    )

    assert index["import_status"] == "UNAVAILABLE"
    assert "not a git checkout" in index["reason"]
    assert index["artifact_count"] == 0
    assert index["artifacts"] == []


def _write_minimal_wiki_inputs(root: Path, commit: str) -> None:
    _write_json(
        root / "generated/read_models/openclaw_estate_topology_registry.json",
        {
            "actual_repos": ["openclaw-eyes"],
            "known_unknowns": [],
            "recommended_actions": [],
            "registry_presence": [
                {
                    "branch_name": "main",
                    "commit_ref": commit,
                    "display_name": "Evidence-Grounded Context Registry",
                    "notes": "Resolved from openclaw-eyes main.",
                    "registry_id": "evidence_grounded_context_registry",
                    "repo_name": "openclaw-eyes",
                    "status": "CANONICAL_ON_MAIN",
                }
            ],
            "topology_summary": {"actual_repos": ["openclaw-eyes"]},
        },
    )
    _write_json(
        root / "generated/read_models/openclaw_reference_resolver.json",
        _resolver_payload(commit),
    )


def test_wiki_compiler_consumes_external_registry_cache_when_present(tmp_path):
    index, commit = _materialize(tmp_path)
    _write_minimal_wiki_inputs(tmp_path, commit)

    summary = compile_openclaw_context_wiki(repo_root=tmp_path, generated_at=FIXED_NOW)
    evidence_page = (
        tmp_path / "generated/wiki/openclaw/Evidence-Grounded Context Registry.md"
    ).read_text(encoding="utf-8")

    assert index["import_status"] == "IMPORTED"
    assert "openclaw-eyes system knowledge registry imported as read-only external input." in evidence_page
    assert "generated/external_registries/openclaw-eyes/openclaw_system_knowledge_registry.sqlite" in summary["source_inputs_used"]


def test_wiki_index_no_longer_marks_system_knowledge_registry_missing_after_import(tmp_path):
    _index, commit = _materialize(tmp_path)
    _write_minimal_wiki_inputs(tmp_path, commit)

    summary = compile_openclaw_context_wiki(repo_root=tmp_path, generated_at=FIXED_NOW)
    missing_paths = {item["path"] for item in summary["index"]["missing_inputs"]}

    assert "generated/system_knowledge/openclaw_system_knowledge_registry.*" not in missing_paths


def test_reference_resolver_commit_and_imported_source_commit_match(tmp_path):
    index, commit = _materialize(tmp_path)

    assert index["resolver_target_ref"] == "openclaw_eyes_main_branch"
    assert index["resolver_commit"] == commit
    assert index["source_commit"] == commit
    assert index["commit_match"] is True


def test_json_parse_and_sqlite_integrity_pass_for_imported_artifacts(tmp_path):
    index, _commit = _materialize(tmp_path)
    artifacts = {artifact["artifact_type"]: artifact for artifact in index["artifacts"]}

    assert artifacts["json"]["json_parse_status"] == "ok"
    assert artifacts["sqlite"]["sqlite_integrity_check"] == "ok"
    sqlite_path = tmp_path / artifacts["sqlite"]["cache_path"]
    connection = sqlite3.connect(sqlite_path)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_import_cli_writes_index_from_mocked_checkout(tmp_path, capsys):
    source_repo, commit = _init_registry_repo(tmp_path / "source-openclaw-eyes")
    resolver_path = tmp_path / "resolver.json"
    _write_json(resolver_path, _resolver_payload(commit))

    assert import_main(
        [
            "--repo",
            "openclaw-eyes",
            "--read-model-root",
            str(tmp_path / "generated/read_models"),
            "--external-registry-root",
            str(tmp_path / "generated/external_registries"),
            "--source-checkout",
            str(source_repo),
            "--reference-resolver-path",
            str(resolver_path),
            "--no-network",
            "--format",
            "json",
        ],
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["source_commit"] == commit
    assert payload["import_status"] == "IMPORTED"


def test_materializer_adds_no_service_lm_or_external_workflow_authority(tmp_path):
    index, _commit = _materialize(tmp_path)

    for key, expected in materializer.NO_AUTHORITY_FLAGS.items():
        assert index[key] is expected
        assert index["boundary_flags"][key] is expected
    source_files = [
        Path("openclaw_external_registry_materializer.py"),
        Path("scripts/import_external_system_knowledge_registry.py"),
    ]
    forbidden = [
        "git push",
        "git pull",
        "openai",
        "anthropic",
        "import requests",
        "import httpx",
        "urllib.request",
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
