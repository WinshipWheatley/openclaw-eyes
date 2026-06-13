"""OpenAI/Codex first-worker proof for the LM2 canonical spine.

This module uses the existing Assignment Loop and Codex Work Package Lifecycle
spine. It does not create another worker registry, router, approval system, or
dashboard. Codex CLI execution is opt-in through ``run_codex_dry_run=True`` and
is limited to one synthetic no-op prompt.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import assignment_loop_contract
import codex_work_package_lifecycle as lifecycle
import openclaw_agent_role_registry


ROOT = Path(__file__).resolve().parent

SCHEMA_VERSION = "LM2_OPENAI_FIRST_WORKER_PROOF_V0"
OPENAI_CODEX_CLI_DRY_RUN_RESULT_SCHEMA = "OPENAI_CODEX_CLI_DRY_RUN_RESULT_V0"

STATUS_READY = "OPENCLAW_LM2_OPENAI_FIRST_WORKER_AND_AGENT_ROLE_CONTEXT_READY"
STATUS_PARTIAL = "OPENCLAW_LM2_OPENAI_FIRST_WORKER_AND_AGENT_ROLE_CONTEXT_PARTIAL"
STATUS_BLOCKED_MODE = "OPENCLAW_LM2_OPENAI_FIRST_WORKER_BLOCKED_CODEX_CLI_MODE"
STATUS_BLOCKED = "OPENCLAW_LM2_OPENAI_FIRST_WORKER_BLOCKED"

DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/LM2 OpenAI First Worker Proof.md")
JSON_EXPORT_NAME = "lm2_openai_first_worker_proof.json"

AUTHORITY_BOUNDARY = {
    "direct_openai_api_call_performed": False,
    "model_output_runtime_mutation_allowed": False,
    "model_output_business_mutation_allowed": False,
    "external_business_action_performed": False,
    "runtime_mutation_performed": False,
    "confirmed_reference_data_created": False,
    "hydration_run": False,
    "guardian_approval_created": False,
    "desktop_gui_automation_performed": False,
    "secret_inspection_performed": False,
    "claude_fable_used": False,
    "gemini_agy_ollama_generation_used": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _safe_command_observation(command_id: str, command: Sequence[str], *, timeout_seconds: int = 8) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            list(command),
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        return {
            "command_id": command_id,
            "command": list(command),
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout_first_line": next((line.strip() for line in stdout.splitlines() if line.strip()), ""),
            "stderr_first_line": next((line.strip() for line in stderr.splitlines() if line.strip()), ""),
            "stdout_line_count": len(stdout.splitlines()),
            "stderr_line_count": len(stderr.splitlines()),
            "_stdout": stdout,
            "_stderr": stderr,
            "raw_output_stored": False,
        }
    except FileNotFoundError as exc:
        return {
            "command_id": command_id,
            "command": list(command),
            "ok": False,
            "returncode": 127,
            "stdout_first_line": "",
            "stderr_first_line": str(exc),
            "stdout_line_count": 0,
            "stderr_line_count": 1,
            "_stdout": "",
            "_stderr": "",
            "raw_output_stored": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "command_id": command_id,
            "command": list(command),
            "ok": False,
            "returncode": 124,
            "stdout_first_line": "",
            "stderr_first_line": "timeout",
            "stdout_line_count": 0,
            "stderr_line_count": 1,
            "_stdout": "",
            "_stderr": "",
            "raw_output_stored": False,
        }


def _public_observation(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not str(key).startswith("_")}


def inspect_codex_cli(*, observations: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    observations = dict(
        observations
        or {
            "codex_which": _safe_command_observation("codex_which", ["which", "codex"]),
            "codex_version": _safe_command_observation("codex_version", ["codex", "--version"]),
            "codex_help": _safe_command_observation("codex_help", ["codex", "--help"]),
            "codex_exec_help": _safe_command_observation("codex_exec_help", ["codex", "exec", "--help"]),
        }
    )
    help_text = "\n".join(
        str(observations.get(command_id, {}).get("_stdout") or "")
        for command_id in ("codex_help", "codex_exec_help")
    ).lower()
    exec_help = str(observations.get("codex_exec_help", {}).get("_stdout") or "").lower()
    features = {
        "installed": bool(observations.get("codex_which", {}).get("ok")),
        "version": str(observations.get("codex_version", {}).get("stdout_first_line") or ""),
        "noninteractive_supported": "run codex non-interactively" in exec_help or "non-interactively" in exec_help,
        "accepts_stdin": "stdin" in exec_help,
        "supports_output_schema": "--output-schema" in exec_help,
        "supports_output_last_message": "--output-last-message" in exec_help,
        "supports_json_events": "--json" in exec_help,
        "supports_working_directory": "--cd" in exec_help,
        "supports_sandbox_read_only": "--sandbox" in help_text and "read-only" in help_text,
        "supports_approval_never": "--ask-for-approval" in help_text and "never" in help_text,
        "supports_ephemeral": "--ephemeral" in exec_help,
        "supports_ignore_rules": "--ignore-rules" in exec_help,
        "supports_skip_git_repo_check": "--skip-git-repo-check" in exec_help,
        "supports_model_selection": "--model" in help_text,
        "supports_no_tools_mode": "no tools" in exec_help or "disable all tools" in exec_help,
        "auth_subscription_proven": False,
        "auth_store_inspected": False,
    }
    required = (
        "installed",
        "noninteractive_supported",
        "accepts_stdin",
        "supports_output_schema",
        "supports_output_last_message",
        "supports_working_directory",
        "supports_sandbox_read_only",
        "supports_approval_never",
        "supports_ephemeral",
    )
    missing = [key for key in required if not features[key]]
    return {
        "schema_version": "CODEX_CLI_MODE_INSPECTION_V0",
        "cli_path": str(shutil.which("codex") or ""),
        "features": features,
        "safe_noninteractive_mode_available": not missing,
        "missing_safe_mode_features": missing,
        "safe_mode_notes": [
            "Use codex exec with stdin, --output-schema, --output-last-message, --cd scratch, --ephemeral, --sandbox read-only, and --ask-for-approval never.",
            "No native no-tools mode was assumed; the dry run uses an empty scratch directory and no private/business context.",
            "Subscription backing remains unproven because auth stores were not inspected.",
        ],
        "command_observations": [_public_observation(row) for _, row in sorted(observations.items())],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def dry_run_result_json_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "status",
            "worker",
            "message",
            "model_or_cli_used",
            "subagents_used",
            "execution_attempted",
            "runtime_mutation_performed",
            "external_business_action_performed",
            "confirmed_reference_data_created",
            "hydration_run",
        ],
        "properties": {
            "schema_version": {"const": OPENAI_CODEX_CLI_DRY_RUN_RESULT_SCHEMA},
            "status": {"const": "ready"},
            "worker": {"const": "openai_codex_cli"},
            "message": {"const": "ready"},
            "model_or_cli_used": {"const": "codex"},
            "subagents_used": {"type": "boolean"},
            "execution_attempted": {"type": "boolean"},
            "runtime_mutation_performed": {"type": "boolean"},
            "external_business_action_performed": {"type": "boolean"},
            "confirmed_reference_data_created": {"type": "boolean"},
            "hydration_run": {"type": "boolean"},
        },
    }


def build_synthetic_assignment_loop(*, created_at_utc: str | None = None) -> dict[str, Any]:
    created_at_utc = created_at_utc or utc_now()
    assignment = assignment_loop_contract.build_assignment_loop(
        requested_by="chief",
        owner_agent="chief",
        worker_type="openai_codex_cli",
        goal="Prove OpenAI/Codex CLI can receive an LM2 package and return a structured no-op worker result.",
        sources=[
            "codex_work_package_lifecycle.py",
            "openclaw_agent_role_registry.py",
            "lm2_openai_first_worker_proof.py",
        ],
        standard=f"Return {OPENAI_CODEX_CLI_DRY_RUN_RESULT_SCHEMA} only; no repo edits, no file inspection, no private data.",
        permission_boundary={
            "model_output_runtime_mutation_allowed": False,
            "model_output_business_mutation_allowed": False,
            "guardian_approval_created_by_assignment_loop": False,
            "external_api_allowed": False,
            "secret_inspection_allowed": False,
        },
        proof_required=[
            "Codex CLI mode inspection",
            "package dispatch claim",
            "synthetic dry-run result file",
            "validation receipt",
            "Watch Desk projection",
        ],
        stop_condition="Stop after one structured no-op result; do not edit files, inspect private data, call business systems, or repeat invocation.",
        current_status="active",
        created_at_utc=created_at_utc,
    )
    assignment["expected_output_schema"] = OPENAI_CODEX_CLI_DRY_RUN_RESULT_SCHEMA
    assignment["role_context_strategy"] = "compact_role_card"
    return assignment


def create_synthetic_codex_package(
    *,
    sqlite_path: Path,
    package_root: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return lifecycle.create_worker_package_from_assignment_loop(
        build_synthetic_assignment_loop(created_at_utc=generated_at),
        worker_kind="openai_codex_cli",
        dispatch_mode="subscription_cli_candidate",
        sqlite_path=sqlite_path,
        package_root=package_root,
        generated_at=generated_at,
    )


def _validate_dry_run_payload(payload: Mapping[str, Any]) -> list[str]:
    expected_false = [
        "subagents_used",
        "execution_attempted",
        "runtime_mutation_performed",
        "external_business_action_performed",
        "confirmed_reference_data_created",
        "hydration_run",
    ]
    errors = []
    if payload.get("schema_version") != OPENAI_CODEX_CLI_DRY_RUN_RESULT_SCHEMA:
        errors.append("schema_version_mismatch")
    if payload.get("status") != "ready":
        errors.append("status_not_ready")
    if payload.get("worker") != "openai_codex_cli":
        errors.append("worker_mismatch")
    if payload.get("message") != "ready":
        errors.append("message_mismatch")
    if payload.get("model_or_cli_used") != "codex":
        errors.append("model_or_cli_used_mismatch")
    for key in expected_false:
        if payload.get(key) is not False:
            errors.append(f"{key}_must_be_false")
    return errors


def adapt_codex_dry_run_result(
    payload: Mapping[str, Any],
    *,
    package_state: Mapping[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    errors = _validate_dry_run_payload(payload)
    if errors:
        return {
            "status": "blocked_invalid_openai_codex_cli_dry_run_result",
            "errors": errors,
            "adapted": None,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
    return {
        "status": "adapted",
        "errors": [],
        "adapted": {
            "schema_version": lifecycle.PACKAGE_RESULT_SCHEMA,
            "package_id": str(package_state.get("package_id") or ""),
            "worker_kind": "openai_codex_cli",
            "status": "completed",
            "authority_grant_ref": str(package_state.get("authority_grant_ref") or ""),
            "files_changed": [],
            "commands_run": ["codex exec bounded synthetic dry run"],
            "validation_run": ["git diff --check"],
            "unsafe_scan_summary": {"passed": True, "hits": []},
            "commit_hash": "",
            "blocker_summary": "",
            "receipt_refs": ["openai_codex_cli_dry_run:synthetic_noop"],
            "submitted_at": generated_at,
            "denied_actions_reported": [],
            "introduced_strings": [],
            "capability_status": "test_dry_run_ready",
            "openai_codex_cli_dry_run_result": dict(payload),
            "model_or_cli_used": "codex",
            "subagents_used": False,
            "runtime_mutation_performed": False,
            "external_business_action_performed": False,
            "confirmed_reference_data_created": False,
            "hydration_run": False,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def codex_dry_run_prompt() -> str:
    expected = {
        "schema_version": OPENAI_CODEX_CLI_DRY_RUN_RESULT_SCHEMA,
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
    return (
        "You are running a synthetic OpenClaw LM2 worker dry run.\n"
        "Do not inspect files. Do not edit files. Do not run shell commands. Do not call tools. "
        "Do not use private or business data. Return only JSON matching the provided schema.\n"
        "Return exactly this object with no markdown:\n"
        f"{stable_json(expected)}"
    )


def run_codex_cli_dry_run(
    *,
    scratch_dir: Path,
    output_dir: Path,
    timeout_seconds: int = 90,
) -> dict[str, Any]:
    scratch_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    schema_path = output_dir / "openai_codex_cli_dry_run_schema.json"
    prompt_path = output_dir / "openai_codex_cli_dry_run_prompt.txt"
    output_path = output_dir / "openai_codex_cli_dry_run_result.json"
    _write_json(schema_path, dry_run_result_json_schema())
    _write_text(prompt_path, codex_dry_run_prompt())
    command = [
        "codex",
        "exec",
        "--ephemeral",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--cd",
        str(scratch_dir),
        "--sandbox",
        "read-only",
        "-a",
        "never",
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(output_path),
        "--color",
        "never",
        "-",
    ]
    try:
        completed = subprocess.run(
            command,
            input=prompt_path.read_text(encoding="utf-8"),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "codex_cli_timeout",
            "command": command[:],
            "returncode": 124,
            "output_path": output_path.as_posix(),
            "stdout_line_count": 0,
            "stderr_line_count": 1,
            "raw_result_text": "",
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
    raw_result_text = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    return {
        "status": "codex_cli_completed" if completed.returncode == 0 else "codex_cli_failed",
        "command": command[:],
        "returncode": completed.returncode,
        "output_path": output_path.as_posix(),
        "schema_path": schema_path.as_posix(),
        "prompt_path": prompt_path.as_posix(),
        "stdout_line_count": len((completed.stdout or "").splitlines()),
        "stderr_line_count": len((completed.stderr or "").splitlines()),
        "stdout_first_line": next((line.strip() for line in (completed.stdout or "").splitlines() if line.strip()), ""),
        "stderr_first_line": next((line.strip() for line in (completed.stderr or "").splitlines() if line.strip()), ""),
        "raw_result_text": raw_result_text,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def execute_openai_first_worker_proof(
    *,
    run_codex_dry_run: bool,
    sqlite_path: Path,
    package_root: Path,
    scratch_dir: Path,
    role_export_root: Path = openclaw_agent_role_registry.DEFAULT_EXPORT_ROOT,
    role_bridge_root: Path | None = openclaw_agent_role_registry.DEFAULT_BRIDGE_ROOT,
    role_system_knowledge_root: Path = openclaw_agent_role_registry.DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    mode = inspect_codex_cli()
    role_export = openclaw_agent_role_registry.export_agent_role_registry(
        export_root=role_export_root,
        bridge_root=role_bridge_root,
        system_knowledge_root=role_system_knowledge_root,
        generated_at=generated_at,
    )
    package_result = create_synthetic_codex_package(
        sqlite_path=sqlite_path,
        package_root=package_root,
        generated_at=generated_at,
    )
    package_state = package_result["package_state"]
    package_id = str(package_state["package_id"])
    dispatch = lifecycle.record_dispatch(
        package_id,
        "openai_codex_cli",
        "chief",
        "Synthetic OpenAI/Codex CLI no-op worker dry run.",
        sqlite_path=sqlite_path,
        package_root=package_root,
        generated_at=generated_at,
        mark_in_progress=True,
    )
    read_model_before = lifecycle.build_read_model(sqlite_path=sqlite_path, package_root=package_root, generated_at=generated_at)
    run_result: dict[str, Any] = {}
    adapter_result: dict[str, Any] = {}
    ingest_result: dict[str, Any] = {}
    status = STATUS_PARTIAL
    if not mode["safe_noninteractive_mode_available"]:
        status = STATUS_BLOCKED_MODE
    elif not run_codex_dry_run:
        status = STATUS_PARTIAL
    else:
        result_dir = Path(str(package_state.get("package_files", {}).get("result_inbox_path") or package_root / "results"))
        run_result = run_codex_cli_dry_run(scratch_dir=scratch_dir, output_dir=result_dir)
        parsed, reason = lifecycle.parse_worker_result_text(str(run_result.get("raw_result_text") or ""))
        if run_result.get("returncode") != 0:
            ingest_result = lifecycle.reject_worker_result(package_id, "codex_cli_nonzero", sqlite_path=sqlite_path, generated_at=generated_at)
            status = STATUS_BLOCKED
        elif parsed is None:
            ingest_result = lifecycle.reject_worker_result(package_id, reason, sqlite_path=sqlite_path, generated_at=generated_at)
            status = STATUS_BLOCKED
        else:
            adapter_result = adapt_codex_dry_run_result(parsed, package_state=package_state, generated_at=generated_at)
            if adapter_result.get("status") != "adapted":
                ingest_result = lifecycle.reject_worker_result(
                    package_id,
                    "openai_codex_cli_dry_run_adapter_failed",
                    sqlite_path=sqlite_path,
                    generated_at=generated_at,
                )
                status = STATUS_BLOCKED
            else:
                ingest_result = lifecycle.ingest_worker_result(
                    adapter_result["adapted"],
                    sqlite_path=sqlite_path,
                    generated_at=generated_at,
                )
                status = (
                    STATUS_READY
                    if ingest_result["package_state"]["state"] == lifecycle.STATE_VALIDATION_PASSED
                    else STATUS_BLOCKED
                )
    lifecycle_read_model = lifecycle.build_read_model(sqlite_path=sqlite_path, package_root=package_root, generated_at=generated_at)
    latest_summary = next(
        (row for row in lifecycle_read_model.get("package_summaries", []) if row.get("package_id") == package_id),
        {},
    )
    watch_item = next(
        (row for row in lifecycle_read_model.get("watch_desk_items", []) if row.get("package_id") == package_id),
        {},
    )
    validation_errors = []
    validation_receipt = ingest_result.get("validation_receipt") if isinstance(ingest_result, Mapping) else {}
    if isinstance(validation_receipt, Mapping) and isinstance(validation_receipt.get("validation_errors"), list):
        validation_errors = [str(error) for error in validation_receipt["validation_errors"]]
    exact_blocker = str(run_result.get("stderr_first_line") or (validation_errors[0] if validation_errors else ""))
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generated_at": generated_at,
        "codex_cli_mode": mode,
        "role_registry_export": role_export,
        "package_id": package_id,
        "assignment_loop_ref": package_state["package_json"].get("assignment_loop_ref"),
        "package_state": package_state,
        "package_role_context": {
            "requested_by_agent": package_state["package_json"].get("requested_by_agent"),
            "owner_agent": package_state["package_json"].get("owner_agent"),
            "agent_role_ref": package_state["package_json"].get("agent_role_ref"),
            "agent_role_summary": package_state["package_json"].get("agent_role_summary"),
            "role_context_strategy": package_state["package_json"].get("role_context_strategy"),
            "full_agent_context_refs": package_state["package_json"].get("full_agent_context_refs"),
            "full_docs_inlined": package_state["package_json"].get("role_context_inlined_full_docs"),
        },
        "dispatch_result": dispatch,
        "codex_dry_run_requested": bool(run_codex_dry_run),
        "codex_dry_run_executed": bool(run_result),
        "codex_dry_run_result": {key: value for key, value in run_result.items() if key != "raw_result_text"},
        "adapter_result": adapter_result,
        "ingest_result": ingest_result,
        "lifecycle_summary_before": {
            "package_count": len(read_model_before.get("package_ids", [])),
            "watch_desk_item_count": len(read_model_before.get("watch_desk_items", [])),
        },
        "lifecycle_summary_after": latest_summary,
        "watch_desk_ref": watch_item.get("item_id", ""),
        "codex_worker_run_manager_ready": status == STATUS_READY,
        "subscription_backing_proven": False,
        "api_billing_used": "unknown_not_proven",
        "direct_openai_api_call_used": False,
        "claude_fable_used": False,
        "gemini_agy_ollama_generation_used": False,
        "desktop_gui_automation_used": False,
        "exact_blocker": exact_blocker,
        "next_safe_action": (
            "Request operator approval for one retry using the corrected short approval flag '-a never'."
            if status == STATUS_BLOCKED and run_result
            else "Review Codex CLI mode before any worker invocation."
            if status == STATUS_BLOCKED_MODE
            else "Review lifecycle status."
        ),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def render_wiki(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# LM2 OpenAI First Worker Proof",
            "",
            f"Status: `{payload.get('status')}`",
            "",
            f"Package: `{payload.get('package_id')}`",
            f"Codex dry run executed: `{payload.get('codex_dry_run_executed')}`",
            f"Codex Worker Run Manager ready: `{payload.get('codex_worker_run_manager_ready')}`",
            f"Subscription backing proven: `{payload.get('subscription_backing_proven')}`",
            f"API billing used: `{payload.get('api_billing_used')}`",
            "",
            "The proof uses the existing `codex_work_package_lifecycle.py` SQLite spine and `scripts/openclaw_run.py` compatible lifecycle. It does not create a new worker registry or router.",
            "",
        ]
    )


def export_openai_first_worker_proof(
    *,
    payload: Mapping[str, Any],
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
) -> dict[str, str]:
    export_root = _rooted(export_root)
    read_model_path = export_root / JSON_EXPORT_NAME
    wiki = _rooted(wiki_path)
    _write_json(read_model_path, payload)
    _write_text(wiki, render_wiki(payload))
    bridge_path = ""
    if bridge_root is not None:
        bridge = Path(bridge_root)
        bridge.mkdir(parents=True, exist_ok=True)
        bridge_target = bridge / JSON_EXPORT_NAME
        shutil.copy2(read_model_path, bridge_target)
        bridge_path = bridge_target.as_posix()
    return {
        "status": str(payload.get("status") or ""),
        "read_model_path": read_model_path.as_posix(),
        "bridge_path": bridge_path,
        "wiki_path": wiki.as_posix(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run/export the LM2 OpenAI first worker proof.")
    parser.add_argument("--run-codex-dry-run", action="store_true")
    parser.add_argument("--sqlite-path", default=str(Path("/tmp/openclaw-mission-control/lm2_openai_first_worker/codex_work_package_lifecycle.sqlite")))
    parser.add_argument("--package-root", default=str(Path("/tmp/openclaw-mission-control/lm2_openai_first_worker/packages")))
    parser.add_argument("--scratch-dir", default=str(Path("/tmp/openclaw-mission-control/lm2_openai_first_worker/scratch")))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    args = parser.parse_args(list(argv) if argv is not None else None)
    payload = execute_openai_first_worker_proof(
        run_codex_dry_run=bool(args.run_codex_dry_run),
        sqlite_path=Path(args.sqlite_path),
        package_root=Path(args.package_root),
        scratch_dir=Path(args.scratch_dir),
        role_export_root=Path(args.export_root),
        role_bridge_root=Path(args.bridge_root) if args.bridge_root else None,
        role_system_knowledge_root=openclaw_agent_role_registry.DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
    )
    result = export_openai_first_worker_proof(
        payload=payload,
        export_root=Path(args.export_root),
        bridge_root=Path(args.bridge_root) if args.bridge_root else None,
        wiki_path=Path(args.wiki_path),
    )
    print(stable_json(result), end="")
    return 0 if payload["status"] in {STATUS_READY, STATUS_PARTIAL, STATUS_BLOCKED_MODE} else 1


if __name__ == "__main__":
    raise SystemExit(main())
