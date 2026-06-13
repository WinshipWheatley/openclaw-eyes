import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import assignment_loop_contract
import codex_work_package_lifecycle as lifecycle
import lm2_openai_first_worker_proof as openai_proof
import openclaw_agent_role_registry as roles
import provider_access_catalog


FIXED_NOW = "2026-06-13T18:00:00+00:00"


def _assignment(owner_agent: str = "cassandra") -> dict:
    assignment = assignment_loop_contract.build_assignment_loop(
        requested_by="chief",
        owner_agent=owner_agent,
        worker_type="openai_codex_cli",
        goal="Return a bounded advisory result for the owner agent.",
        sources=["codex_work_package_lifecycle.py", "openclaw_agent_role_registry.py"],
        standard="Return structured JSON only.",
        proof_required=["package receipt", "validation receipt"],
        stop_condition="Stop after structured result; do not mutate runtime.",
        current_status="active",
        created_at_utc=FIXED_NOW,
    )
    assignment["expected_output_schema"] = openai_proof.OPENAI_CODEX_CLI_DRY_RUN_RESULT_SCHEMA
    return assignment


def _fake_observation(stdout: str, *, ok: bool = True) -> dict:
    return {
        "ok": ok,
        "returncode": 0 if ok else 1,
        "stdout_first_line": stdout.splitlines()[0] if stdout.splitlines() else "",
        "stderr_first_line": "",
        "stdout_line_count": len(stdout.splitlines()),
        "stderr_line_count": 0,
        "_stdout": stdout,
        "_stderr": "",
        "raw_output_stored": False,
    }


def _fake_codex_observations() -> dict:
    exec_help = """Run Codex non-interactively
Arguments:
  [PROMPT] instructions are read from stdin
Options:
  --output-schema <FILE>
  -o, --output-last-message <FILE>
  -C, --cd <DIR>
  -s, --sandbox <SANDBOX_MODE> [possible values: read-only, workspace-write, danger-full-access]
  -a, --ask-for-approval <APPROVAL_POLICY> [possible values: never]
  --ephemeral
  --ignore-rules
  --skip-git-repo-check
  --json
"""
    root_help = """Codex CLI
Commands:
  exec            Run Codex non-interactively
Options:
  -m, --model <MODEL>
  -s, --sandbox <SANDBOX_MODE> [possible values: read-only]
  -a, --ask-for-approval <APPROVAL_POLICY> [possible values: never]
"""
    return {
        "codex_which": _fake_observation("/usr/bin/codex\n"),
        "codex_version": _fake_observation("codex-cli 0.139.0\n"),
        "codex_help": _fake_observation(root_help),
        "codex_exec_help": _fake_observation(exec_help),
    }


def _safe_codex_mode() -> dict:
    return openai_proof.inspect_codex_cli(observations=_fake_codex_observations())


def test_agent_role_cards_exist_for_required_agents():
    payload = roles.build_registry(generated_at=FIXED_NOW)

    assert payload["status"] == roles.STATUS_READY
    assert set(roles.REQUIRED_AGENT_IDS).issubset(payload["role_cards"])
    for agent_id in roles.REQUIRED_AGENT_IDS:
        card = payload["role_cards"][agent_id]
        assert card["schema_version"] == roles.SCHEMA_VERSION
        assert card["agent_role_ref"] == f"agent_role_card:{agent_id}"
        assert card["package_context_summary"]
        assert card["full_context_refs"]
        assert card["authority_boundary"]["tool_authority_granted"] is False


def test_compact_role_card_included_in_lm2_package(tmp_path):
    result = lifecycle.create_worker_package_from_assignment_loop(
        _assignment("cassandra"),
        worker_kind="openai_codex_cli",
        dispatch_mode="subscription_cli_candidate",
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "packages",
        generated_at=FIXED_NOW,
    )
    package = result["package_state"]["package_json"]

    assert package["requested_by_agent"] == "chief"
    assert package["owner_agent"] == "cassandra"
    assert package["agent_role_ref"] == "agent_role_card:cassandra"
    assert package["role_context_strategy"] == "compact_role_card"
    assert package["agent_role_card"]["display_name"] == "Cassandra"
    assert package["agent_role_summary"].startswith("Act for Cassandra")
    assert ".claude/commands/cassandra.md" in package["full_agent_context_refs"]
    assert package["role_context_inlined_full_docs"] is False


def test_full_context_refs_are_referenced_not_inlined_by_default(tmp_path):
    result = lifecycle.create_worker_package_from_assignment_loop(
        _assignment("niles"),
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "packages",
        generated_at=FIXED_NOW,
    )
    package = result["package_state"]["package_json"]
    prompt = Path(result["package_files"]["prompt_path"]).read_text(encoding="utf-8")

    assert package["agent_role_card"]["display_name"] == "Niles"
    assert package["full_agent_context_refs"]
    assert package["role_context_inlined_full_docs"] is False
    assert "Full role context refs:" in prompt
    assert "## Agent role" in prompt
    assert "Niles" in prompt
    assert "## Hard Boundaries" not in prompt


def test_cli_native_slash_agents_are_optional_and_subagents_metadata_only():
    card = roles.compact_role_card("chief", updated_at_utc=FIXED_NOW)

    assert card["native_agent_command_policy"]["slash_agent_command_required"] is False
    assert card["native_agent_command_policy"]["slash_agent_command_allowed_only_if_proven"] is True
    assert card["subagent_policy"]["extra_authority_granted"] is False
    assert card["subagent_policy"]["worker_run_manager_tracks_parent_only_v0"] is True


def test_openai_codex_cli_worker_kind_exists():
    assert "openai_codex_cli" in lifecycle.ALLOWED_WORKER_KINDS
    assert "claude" not in lifecycle.ALLOWED_WORKER_KINDS
    assert "opus" not in lifecycle.ALLOWED_WORKER_KINDS


def test_codex_cli_mode_detection_uses_safe_noninteractive_controls():
    mode = openai_proof.inspect_codex_cli(observations=_fake_codex_observations())

    assert mode["safe_noninteractive_mode_available"] is True
    assert mode["features"]["noninteractive_supported"] is True
    assert mode["features"]["accepts_stdin"] is True
    assert mode["features"]["supports_subprocess_stdout_capture"] is True
    assert mode["features"]["supports_sandbox_read_only"] is True
    assert mode["features"]["supports_approval_never"] is True
    assert mode["approval_flag"]["safe_flag"] == ["-a", "never"]
    assert mode["approval_flag"]["short_flag_valid"] is True
    assert mode["features"]["auth_store_inspected"] is False


def test_codex_cli_command_builder_uses_verified_short_approval_flag(tmp_path):
    command = openai_proof.codex_cli_dry_run_command(
        scratch_dir=tmp_path / "scratch",
        schema_path=tmp_path / "schema.json",
        output_path=tmp_path / "result.json",
    )

    assert "--ask-for-approval" not in command
    assert command[command.index("-a") + 1] == "never"
    assert command.index("-a") < command.index("exec")
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert command[command.index("--cd") + 1] == str(tmp_path / "scratch")


def test_codex_cli_worker_command_resolves_service_safe_absolute_path(tmp_path, monkeypatch):
    fake_codex = tmp_path / ".nvm" / "versions" / "node" / "v99" / "bin" / "codex"
    fake_codex.parent.mkdir(parents=True)
    fake_codex.write_text("#!/usr/bin/env node\n", encoding="utf-8")
    monkeypatch.delenv(openai_proof.CODEX_CLI_ENV_VAR, raising=False)
    monkeypatch.setattr(openai_proof.shutil, "which", lambda _name: "")
    monkeypatch.setattr(openai_proof.Path, "home", lambda: tmp_path)

    command = openai_proof.codex_cli_worker_command(
        scratch_dir=tmp_path / "scratch",
        schema_path=tmp_path / "schema.json",
        output_path=tmp_path / "result.json",
    )

    assert command[0] == str(fake_codex)
    assert command[command.index("-a") + 1] == "never"


def test_codex_cli_worker_command_honors_explicit_env_path(tmp_path, monkeypatch):
    configured = tmp_path / "bin" / "codex"
    configured.parent.mkdir(parents=True)
    configured.write_text("#!/usr/bin/env node\n", encoding="utf-8")
    monkeypatch.setenv(openai_proof.CODEX_CLI_ENV_VAR, str(configured))

    command = openai_proof.codex_cli_worker_command(
        scratch_dir=tmp_path / "scratch",
        schema_path=tmp_path / "schema.json",
        output_path=tmp_path / "result.json",
    )

    assert command[0] == str(configured)


def test_codex_cli_worker_timeout_returns_blocked_envelope(tmp_path, monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], timeout=1, output="", stderr="")

    monkeypatch.setattr(openai_proof.subprocess, "run", raise_timeout)
    result = openai_proof.run_codex_cli_worker(
        prompt="Return JSON.",
        response_schema=openai_proof.tiny_readonly_review_result_json_schema(),
        scratch_dir=tmp_path / "scratch",
        output_dir=tmp_path / "results",
        result_prefix="timeout_fixture",
        timeout_seconds=1,
    )

    assert result["status"] == "timeout_with_no_result"
    assert result["returncode"] == 124
    assert result["result_file_exists"] is False
    assert result["elapsed_seconds"] >= 0
    assert Path(result["stdout_path"]).exists()
    assert Path(result["stderr_path"]).read_text(encoding="utf-8") == "timeout"


def test_codex_cli_worker_timeout_preserves_redacted_partial_output(tmp_path, monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            args[0],
            timeout=1,
            output='{"status":"partial"} token=abc123',
            stderr="still working",
        )

    monkeypatch.setattr(openai_proof.subprocess, "run", raise_timeout)
    result = openai_proof.run_codex_cli_worker(
        prompt="Return JSON.",
        response_schema=openai_proof.tiny_readonly_review_result_json_schema(),
        scratch_dir=tmp_path / "scratch",
        output_dir=tmp_path / "results",
        result_prefix="partial_fixture",
        timeout_seconds=1,
    )

    assert result["status"] == "timeout_with_partial_result"
    assert result["returncode"] == 124
    assert "token=[REDACTED]" in result["stdout_excerpt"]
    assert "abc123" not in result["stdout_excerpt"]


def test_dry_run_output_schema_uses_codex_compatible_typed_enums():
    schema = openai_proof.dry_run_result_json_schema()

    expected = {
        "schema_version": [openai_proof.OPENAI_CODEX_CLI_DRY_RUN_RESULT_SCHEMA],
        "status": ["ready"],
        "worker": ["openai_codex_cli"],
        "message": ["ready"],
        "model_or_cli_used": ["codex"],
    }
    for field, enum_value in expected.items():
        assert schema["properties"][field]["type"] == "string"
        assert schema["properties"][field]["enum"] == enum_value
        assert "const" not in schema["properties"][field]


def test_codex_response_schema_validator_blocks_const_and_missing_type():
    valid = openai_proof.validate_codex_response_schema()
    invalid_schema = openai_proof.dry_run_result_json_schema()
    invalid_schema["properties"]["message"] = {"const": "ready"}

    invalid = openai_proof.validate_codex_response_schema(invalid_schema)

    assert valid["valid"] is True
    assert valid["message_property"]["type"] == "string"
    assert valid["message_property"]["enum"] == ["ready"]
    assert invalid["valid"] is False
    assert "required_property_type_missing:message" in invalid["errors"]
    assert "unsupported_const_keyword:message" in invalid["errors"]


def test_bad_long_approval_flag_after_exec_is_not_used_in_retry_command(tmp_path):
    previous_bad_command = ["codex", "exec", "--ask-for-approval", "never"]
    retry_command = openai_proof.codex_cli_dry_run_command(
        scratch_dir=tmp_path / "scratch",
        schema_path=tmp_path / "schema.json",
        output_path=tmp_path / "result.json",
    )

    assert previous_bad_command.index("--ask-for-approval") > previous_bad_command.index("exec")
    assert "--ask-for-approval" not in retry_command
    assert retry_command.index("-a") < retry_command.index("exec")


def test_previous_blocked_attempt_is_preserved(tmp_path):
    previous = {
        "status": "OPENCLAW_LM2_OPENAI_FIRST_WORKER_BLOCKED",
        "package_id": "codex_work_package:previous",
        "dispatch_result": {"package_claim": {"claim_id": "codex_work_package_claim:previous"}},
        "ingest_result": {
            "package_result": {"result_id": "codex_work_package_result:previous"},
            "validation_receipt": {"validation_id": "codex_work_package_validation:previous"},
        },
        "watch_desk_ref": "codex_work_package:previous",
        "exact_blocker": "error: unexpected argument '--ask-for-approval' found",
    }
    path = tmp_path / "previous.json"
    path.write_text(json.dumps(previous), encoding="utf-8")

    preserved = openai_proof.previous_openai_first_worker_attempt(path)

    assert preserved["preserved"] is True
    assert preserved["package_id"] == "codex_work_package:previous"
    assert preserved["claim_ref"] == "codex_work_package_claim:previous"
    assert preserved["result_ref"] == "codex_work_package_result:previous"
    assert preserved["validation_ref"] == "codex_work_package_validation:previous"


def test_synthetic_codex_result_schema_can_be_adapted_and_ingested(tmp_path):
    package_result = openai_proof.create_synthetic_codex_package(
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "packages",
        generated_at=FIXED_NOW,
    )
    state = package_result["package_state"]
    dry_result = {
        "schema_version": openai_proof.OPENAI_CODEX_CLI_DRY_RUN_RESULT_SCHEMA,
        "status": "ready",
        "worker": "openai_codex_cli",
        "message": "ready",
        "model_or_cli_used": "codex",
        "subagents_used": False,
        "execution_attempted": False,
        "runtime_mutation_performed": False,
        "external_business_action_performed": False,
        "confirmed_reference_data_created": False,
        "hydration_run": False,
    }
    adapted = openai_proof.adapt_codex_dry_run_result(dry_result, package_state=state, generated_at=FIXED_NOW)
    ingested = lifecycle.ingest_worker_result(
        adapted["adapted"],
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        generated_at=FIXED_NOW,
    )
    read_model = lifecycle.build_read_model(
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "packages",
        generated_at=FIXED_NOW,
    )

    assert adapted["status"] == "adapted"
    assert ingested["validation_receipt"]["validation_status"] == "validation_passed"
    assert ingested["package_state"]["state"] == lifecycle.STATE_VALIDATION_PASSED
    assert read_model["watch_desk_items"]
    assert read_model["watch_desk_items"][0]["state"]["owner_agent"] == "chief"
    assert read_model["watch_desk_items"][0]["push_allowed"] is False


def test_tiny_readonly_review_result_can_be_adapted_and_ingested(tmp_path):
    package_result = lifecycle.create_worker_package_from_assignment_loop(
        _assignment("chief"),
        worker_kind="openai_codex_cli",
        dispatch_mode="subscription_cli_candidate",
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "packages",
        generated_at=FIXED_NOW,
    )
    state = package_result["package_state"]
    tiny_result = {
        "schema_version": openai_proof.TINY_READONLY_REVIEW_RESULT_SCHEMA,
        "status": "ready",
        "worker": "openai_codex_cli",
        "summary": "The canonical LM2 worker spine exists.",
        "files_reviewed": ["generated/read_models/lm2_worker_spine_status.json"],
        "next_safe_action": "Keep Worker Run Manager as the canonical path.",
        "execution_attempted": False,
        "runtime_mutation_performed": False,
        "external_business_action_performed": False,
        "confirmed_reference_data_created": False,
        "hydration_run": False,
    }
    adapted = openai_proof.adapt_tiny_readonly_review_result(tiny_result, package_state=state, generated_at=FIXED_NOW)
    ingested = lifecycle.ingest_worker_result(
        adapted["adapted"],
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        generated_at=FIXED_NOW,
    )

    assert adapted["status"] == "adapted"
    assert ingested["validation_receipt"]["validation_status"] == "validation_passed"
    assert ingested["package_state"]["state"] == lifecycle.STATE_VALIDATION_PASSED


def test_bad_synthetic_codex_result_fails_closed(tmp_path):
    package_result = openai_proof.create_synthetic_codex_package(
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "packages",
        generated_at=FIXED_NOW,
    )
    state = package_result["package_state"]
    adapted = openai_proof.adapt_codex_dry_run_result(
        {
            "schema_version": openai_proof.OPENAI_CODEX_CLI_DRY_RUN_RESULT_SCHEMA,
            "status": "ready",
            "worker": "openai_codex_cli",
            "message": "ready",
            "model_or_cli_used": "codex",
            "subagents_used": True,
            "execution_attempted": False,
            "runtime_mutation_performed": False,
            "external_business_action_performed": False,
            "confirmed_reference_data_created": False,
            "hydration_run": False,
        },
        package_state=state,
        generated_at=FIXED_NOW,
    )

    assert adapted["status"] == "blocked_invalid_openai_codex_cli_dry_run_result"
    assert "subagents_used_must_be_false" in adapted["errors"]


def test_schema_retry_blocks_before_cli_when_schema_invalid(tmp_path, monkeypatch):
    monkeypatch.setattr(
        openai_proof,
        "validate_codex_response_schema",
        lambda: {
            "schema_version": "CODEX_RESPONSE_SCHEMA_LOCAL_VALIDATION_V0",
            "valid": False,
            "errors": ["unsupported_const_keyword:message"],
            "message_property": {"const": "ready"},
            "required_count": 11,
        },
    )

    def fail_if_inspected():
        raise AssertionError("Codex CLI should not be inspected when schema is invalid")

    monkeypatch.setattr(openai_proof, "inspect_codex_cli", fail_if_inspected)
    payload = openai_proof.execute_openai_first_worker_proof(
        run_codex_dry_run=True,
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "packages",
        scratch_dir=tmp_path / "scratch",
        role_export_root=tmp_path / "read_models",
        role_bridge_root=None,
        role_system_knowledge_root=tmp_path / "agent_roles",
        retry_mode=True,
        schema_retry_mode=True,
        generated_at=FIXED_NOW,
    )

    assert payload["status"] == openai_proof.STATUS_SCHEMA_RETRY_BLOCKED_SCHEMA_INVALID
    assert payload["codex_dry_run_executed"] is False
    assert payload["package_id"] == ""


def test_schema_retry_codex_cli_error_fails_closed(tmp_path, monkeypatch):
    safe_mode = _safe_codex_mode()
    monkeypatch.setattr(openai_proof, "inspect_codex_cli", lambda: safe_mode)
    monkeypatch.setattr(
        openai_proof,
        "run_codex_cli_dry_run",
        lambda **_: {
            "status": "codex_cli_failed",
            "returncode": 2,
            "stdout_line_count": 0,
            "stderr_line_count": 1,
            "stderr_first_line": "schema rejected",
            "raw_result_text": "",
            "authority_boundary": dict(openai_proof.AUTHORITY_BOUNDARY),
        },
    )

    payload = openai_proof.execute_openai_first_worker_proof(
        run_codex_dry_run=True,
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "packages",
        scratch_dir=tmp_path / "scratch",
        role_export_root=tmp_path / "read_models",
        role_bridge_root=None,
        role_system_knowledge_root=tmp_path / "agent_roles",
        retry_mode=True,
        schema_retry_mode=True,
        generated_at=FIXED_NOW,
    )

    assert payload["status"] == openai_proof.STATUS_SCHEMA_RETRY_BLOCKED
    assert payload["codex_dry_run_executed"] is True
    assert payload["ingest_result"]["validation_receipt"]["validation_status"] == "validation_failed"
    assert payload["exact_blocker"] == "schema rejected"


def test_no_disallowed_model_routes_are_used_in_proof_payload(tmp_path):
    payload = openai_proof.execute_openai_first_worker_proof(
        run_codex_dry_run=False,
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "packages",
        scratch_dir=tmp_path / "scratch",
        role_export_root=tmp_path / "read_models",
        role_bridge_root=None,
        role_system_knowledge_root=tmp_path / "agent_roles",
        generated_at=FIXED_NOW,
    )
    assert payload["codex_dry_run_executed"] is False
    assert payload["schema_validation"]["valid"] is True
    assert payload["claude_fable_used"] is False
    assert payload["gemini_agy_ollama_generation_used"] is False
    assert payload["desktop_gui_automation_used"] is False
    assert payload["subscription_backing"] == "unknown_not_proven"
    assert payload["api_billing_used"] == "unknown_via_codex_cli_path"
    assert payload["dispatch_result"]["package_claim"]["worker_kind"] == "openai_codex_cli"
    assert payload["package_state"]["package_json"]["provider_access_metadata"]["worker_kind"] == "openai_codex_cli"
    assert payload["package_state"]["package_json"]["provider_access_metadata"]["provider"] != "anthropic"


def test_provider_catalog_maps_openai_to_codex_worker_kind():
    observations = provider_access_catalog.build_provider_records(
        {
            "codex_which": _fake_observation("/usr/bin/codex\n"),
            "codex_version": _fake_observation("codex-cli 0.139.0\n"),
            "codex_help": _fake_observation("Codex CLI\nCommands:\n  exec Run Codex non-interactively\nOptions:\n  -m, --model <MODEL>\n  -C, --cd <DIR>\n"),
            "codex_exec_help": _fake_observation("Run Codex non-interactively\nstdin\n--json\n--output-schema <FILE>\n"),
        }
    )
    codex = next(row for row in observations if row["provider"] == "openai_codex_cli")

    assert codex["worker_run_manager_mapping"]["worker_kind"] == "openai_codex_cli"
    assert codex["api_billing_required"] == "unknown"
    assert codex["worker_run_manager_mapping"]["result_can_mutate_runtime_directly"] is False
