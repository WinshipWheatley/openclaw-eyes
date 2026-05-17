import json
from pathlib import Path

import active_machinery_classification_orchestrator as orch
from scripts.build_active_machinery_classification_orchestrator import main as cli_main


FIXED_NOW = "2026-05-17T12:00:00+00:00"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _sample_root(tmp_path: Path) -> Path:
    root = tmp_path / "openclaw"
    root.mkdir()
    blocked = "BLOCKED" + "_FIXTURE"
    _write(root / "safe.py", "def ok():\n    return True\n")
    _write(root / "scripts" / "export_demo.py", "#!/usr/bin/env python3\nprint('not executed')\n")
    _write(root / "docs" / "operations" / "OPENCLAW_TEST_DOC.md", "# Test doc\n")
    _write(root / "generated" / "read_models" / "demo.json", json.dumps({"ok": True}))
    _write(root / ".chief.env", f"{blocked}_ENV_VALUE\n")
    _write(root / ".mcp.json", "{\"tool\": \"" + blocked + "_CONFIG\"}\n")
    _write(root / "private" / "secret.txt", f"{blocked}_PRIVATE\n")
    _write(root / "logs" / "telegram.log", f"{blocked}_LOG\n")
    _write(root / "large.py", "x = 1\n" * 1000)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    (root / "escape_link.py").symlink_to(outside)
    _write(
        root / "generated" / "read_models" / "source_inventory.json",
        json.dumps(
            {
                "records": [
                    {
                        "path": "safe.py",
                        "source_class": "source_code",
                        "reason_included": "test source inventory",
                        "blocked_reason": "",
                    },
                    {
                        "path": ".chief.env",
                        "source_class": "blocked_no_go_example",
                        "reason_included": "blocked fixture",
                        "blocked_reason": "credential file is blocked",
                    },
                    {
                        "path": ".mcp.json",
                        "source_class": "hidden_tool_config",
                        "reason_included": "hidden config fixture",
                        "blocked_reason": "",
                    },
                    {
                        "path": "private/secret.txt",
                        "source_class": "blocked_no_go_example",
                        "reason_included": "blocked fixture",
                        "blocked_reason": "private file is blocked",
                    },
                    {
                        "path": "logs/telegram.log",
                        "source_class": "blocked_no_go_example",
                        "reason_included": "blocked fixture",
                        "blocked_reason": "raw log is blocked",
                    },
                    {
                        "path": "large.py",
                        "source_class": "source_code",
                        "reason_included": "large fixture",
                        "blocked_reason": "",
                    },
                    {
                        "path": "escape_link.py",
                        "source_class": "source_code",
                        "reason_included": "symlink fixture",
                        "blocked_reason": "",
                    },
                ]
            }
        ),
    )
    _write(
        root / ".gitignore",
        "\n".join(
            [
                "*",
                "!safe.py",
                "!.mcp.json",
                "!scripts/",
                "!scripts/*.py",
                "!docs/operations/",
                "!docs/operations/*.md",
                "!generated/read_models/",
                "!generated/read_models/*.json",
            ]
        )
        + "\n",
    )
    return root


def _by_path(payload):
    return {item["relative_path"]: item for item in payload["candidates"]}


def test_privacy_dry_run_blocks_no_go_private_raw_logs_symlink_and_large_files(tmp_path):
    root = _sample_root(tmp_path)
    dry_run = orch.build_privacy_inclusion_dry_run(
        repo_root=root,
        generated_at=FIXED_NOW,
        safe_header_max_bytes=100,
        include_repo_b_reference=True,
    )
    by_path = _by_path(dry_run)

    assert by_path[".chief.env"]["eligibility"] == "blocked_no_go"
    assert by_path[".mcp.json"]["eligibility"] == "blocked_no_go"
    assert by_path["private/secret.txt"]["eligibility"] == "blocked_no_go"
    assert by_path["logs/telegram.log"]["eligibility"] == "blocked_no_go"
    assert by_path["escape_link.py"]["eligibility"] == "blocked_no_go"
    assert by_path["large.py"]["eligibility"] == "operator_review"
    assert by_path["large.py"]["header_read_allowed"] is False
    assert by_path["generated/read_models/demo.json"]["eligibility"] == "generated_artifact"
    assert by_path["generated/read_models/demo.json"]["header_read_allowed"] is True
    assert any(item["repo_role"] == "pre_split_capability_tree_reference_only" for item in dry_run["candidates"])
    assert dry_run["boundaries"]["raw_private_content_read"] is False
    assert dry_run["boundaries"]["repo_b_executed"] is False


def test_shard_generation_reads_only_safe_headers_and_has_required_shape(tmp_path):
    root = _sample_root(tmp_path)
    dry_run = orch.build_privacy_inclusion_dry_run(
        repo_root=root,
        generated_at=FIXED_NOW,
        safe_header_max_bytes=100,
    )
    shards = orch.build_shards_from_dry_run(dry_run, shard_size=2, header_line_limit=2)

    assert shards
    for shard in shards:
        assert shard["schema_version"] == orch.SHARD_SCHEMA_VERSION
        assert shard["body_read_allowed"] is False
        assert shard["no_execution"] is True
        for item in shard["items"]:
            assert set(
                [
                    "repo_root",
                    "repo_role",
                    "relative_path",
                    "content_header_excerpt",
                    "header_lines_read",
                    "body_read_allowed",
                    "why_included",
                    "no_execution",
                ]
            ) <= set(item)
            assert item["body_read_allowed"] is False
            assert item["no_execution"] is True
            assert "BLOCKED" + "_FIXTURE" not in item["content_header_excerpt"]
            assert item["relative_path"] != "large.py"
            assert item["relative_path"] != "escape_link.py"


def test_run_all_writes_shards_mock_aggregation_read_models_and_prompt(tmp_path):
    root = _sample_root(tmp_path)
    output_root = tmp_path / "generated" / "audit_shards" / "active_machinery_v0"
    read_model_root = tmp_path / "generated" / "read_models"
    prompt_path = tmp_path / "docs" / "operations" / "ACTIVE_MACHINERY_CLASSIFICATION_WORKER_PROMPT_V0.md"

    summary = orch.run_all(
        repo_root=root,
        output_root=output_root,
        read_model_root=read_model_root,
        worker_prompt_path=prompt_path,
        generated_at=FIXED_NOW,
    )

    assert summary["llm_calls_made"] is False
    assert summary["raw_private_content_read"] is False
    assert summary["repo_b_executed"] is False
    assert summary["shards_ready_for_gemini"] is True
    assert (output_root / "privacy_inclusion_dry_run.json").is_file()
    assert (output_root / "shard_manifest.json").is_file()
    assert list((output_root / "shards").glob("*.json"))
    assert list((output_root / "mock_worker_outputs").glob("*.json"))
    assert (read_model_root / "active_machinery_classification_orchestrator.json").is_file()
    assert (read_model_root / "active_machinery_classification_orchestrator_OPERATOR.md").is_file()
    prompt = prompt_path.read_text(encoding="utf-8")
    assert "Return JSON only" in prompt
    assert "Do not execute scripts" in prompt
    assert "raw Telegram logs" in prompt
    payload = json.loads((read_model_root / "active_machinery_classification_orchestrator.json").read_text())
    assert "generated_read_model_artifact" in payload["groups"]
    assert "canonical_doctrine_docs" in payload["groups"]
    assert payload["groups"]["legacy_reference_only"]["count"] == 1
    assert "unknown_operator_review" in payload["groups"]


def test_cli_all_outputs_json_summary(tmp_path, capsys):
    root = _sample_root(tmp_path)
    output_root = tmp_path / "shards"
    read_model_root = tmp_path / "read_models"

    exit_code = cli_main(
        [
            "--mode",
            "all",
            "--repo-root",
            root.as_posix(),
            "--output-root",
            output_root.as_posix(),
            "--read-model-root",
            read_model_root.as_posix(),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == orch.SCHEMA_VERSION
    assert payload["shards_ready_for_gemini"] is True
    assert payload["llm_calls_made"] is False


def test_orchestrator_sources_do_not_call_llms_network_subprocess_or_shell():
    source_files = [
        Path("active_machinery_classification_orchestrator.py"),
        Path("scripts/build_active_machinery_classification_orchestrator.py"),
    ]
    forbidden = [
        "import subprocess",
        "subprocess.",
        "os.system",
        "shell=True",
        "eval(",
        "import requests",
        "import httpx",
        "urllib.request",
        "generativeai",
        "openai",
        "anthropic",
        "socket.",
        "smtplib",
        "send_message",
        "reply_text",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token.lower() not in text
