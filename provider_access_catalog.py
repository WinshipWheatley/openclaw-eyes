"""Subscription-backed LM access catalog.

This module audits local LM access paths using safe availability/help
commands only. It does not invoke models, send prompts, read credential
stores, inspect auth token files, call provider APIs, automate desktop apps,
or mutate runtime/business systems.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Subscription Backed LM Access.md")

SCHEMA_VERSION = "PROVIDER_ACCESS_MODE_V0"
READ_MODEL_ID = "provider_access_catalog"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
READY_STATUS = "OPENCLAW_SUBSCRIPTION_BACKED_LM_ACCESS_AUDIT_READY"
PARTIAL_STATUS = "OPENCLAW_SUBSCRIPTION_BACKED_LM_ACCESS_AUDIT_PARTIAL"

SAFE_DISCOVERY_COMMANDS: dict[str, list[str]] = {
    "codex_which": ["which", "codex"],
    "codex_version": ["codex", "--version"],
    "codex_help": ["codex", "--help"],
    "codex_exec_help": ["codex", "exec", "--help"],
    "codex_app_server_help": ["codex", "app-server", "--help"],
    "codex_remote_control_help": ["codex", "remote-control", "--help"],
    "gemini_which": ["which", "gemini"],
    "gemini_version": ["gemini", "--version"],
    "gemini_help": ["gemini", "--help"],
    "agy_which": ["which", "agy"],
    "agy_version": ["agy", "--version"],
    "agy_help": ["agy", "--help"],
    "claude_which": ["which", "claude"],
    "claude_version": ["claude", "--version"],
    "claude_help": ["claude", "--help"],
    "ollama_which": ["which", "ollama"],
    "ollama_list": ["ollama", "list"],
}

GENERATION_COMMAND_MARKERS = (
    " run ",
    " generate ",
    " chat ",
    " prompt ",
    " -p ",
    " --prompt ",
    " exec ",
)

SECRET_VALUE_PATTERN = re.compile(
    r"(?i)(api[_-]?key|token|secret|credential|password|private[_-]?key)\s*[:=]\s*([^\s]+)"
)
LONG_SECRET_PATTERN = re.compile(r"(?i)\b(sk-[A-Za-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{12,})\b")

AUTHORITY_BOUNDARY = {
    "model_invocation_performed": False,
    "generation_probe_performed": False,
    "prompt_sent": False,
    "proof_bundle_sent": False,
    "api_key_billing_call_performed": False,
    "paid_api_endpoint_called": False,
    "auth_store_inspected": False,
    "credential_value_logged": False,
    "desktop_app_automation_performed": False,
    "gui_automation_performed": False,
    "browser_automation_performed": False,
    "runtime_mutation_performed": False,
    "email_send_performed": False,
    "gmail_draft_created": False,
    "business_system_mutation_performed": False,
    "guardian_approval_created": False,
    "worker_spawn_performed": False,
    "git_push_performed": False,
    "tool_authority_granted": False,
    "business_action_authority_granted": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "tools_allowed",
    "execution_allowed",
    "desktop_app_control",
    "api_billing_preferred",
    "auth_token_store_read",
    "credential_value_read",
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


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _redact_text(value: str) -> tuple[str, int]:
    redactions = 0

    def _replace_key_value(match: re.Match[str]) -> str:
        nonlocal redactions
        redactions += 1
        return f"{match.group(1)}=<redacted>"

    redacted = SECRET_VALUE_PATTERN.sub(_replace_key_value, value)
    redacted, long_count = LONG_SECRET_PATTERN.subn("<redacted-secret>", redacted)
    redactions += long_count
    return redacted, redactions


def _first_nonempty_line(value: str) -> str:
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:240]
    return ""


def _observation(
    *,
    command_id: str,
    command: Sequence[str],
    returncode: int,
    stdout: str = "",
    stderr: str = "",
    timed_out: bool = False,
    error: str = "",
) -> dict[str, Any]:
    stdout_redacted, stdout_redactions = _redact_text(stdout)
    stderr_redacted, stderr_redactions = _redact_text(stderr)
    return {
        "command_id": command_id,
        "command": list(command),
        "command_kind": "help_or_inventory",
        "returncode": int(returncode),
        "ok": returncode == 0 and not timed_out and not error,
        "timed_out": bool(timed_out),
        "error": str(error or ""),
        "stdout_first_line": _first_nonempty_line(stdout_redacted),
        "stderr_first_line": _first_nonempty_line(stderr_redacted),
        "stdout_line_count": len(stdout.splitlines()),
        "stderr_line_count": len(stderr.splitlines()),
        "secret_value_patterns_redacted": stdout_redactions + stderr_redactions,
        "raw_output_stored": False,
        "_stdout": stdout_redacted,
        "_stderr": stderr_redacted,
    }


def run_safe_discovery_command(command_id: str, command: Sequence[str], *, timeout_seconds: int = 8) -> dict[str, Any]:
    """Run an approved help/inventory command and keep only sanitized metadata."""

    try:
        completed = subprocess.run(
            list(command),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        return _observation(command_id=command_id, command=command, returncode=127, error=str(exc))
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return _observation(
            command_id=command_id,
            command=command,
            returncode=124,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
        )
    return _observation(
        command_id=command_id,
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def collect_safe_cli_observations() -> dict[str, dict[str, Any]]:
    return {
        command_id: run_safe_discovery_command(command_id, command)
        for command_id, command in SAFE_DISCOVERY_COMMANDS.items()
    }


def _raw_output(observations: Mapping[str, Mapping[str, Any]], command_id: str) -> str:
    row = observations.get(command_id, {})
    stdout = row.get("_stdout", "")
    stderr = row.get("_stderr", "")
    parts = [value for value in (stdout, stderr) if isinstance(value, str) and value]
    return "\n".join(parts)


def _command_ok(observations: Mapping[str, Mapping[str, Any]], command_id: str) -> bool:
    return bool(observations.get(command_id, {}).get("ok"))


def _installed(observations: Mapping[str, Mapping[str, Any]], command_id: str) -> bool:
    return _command_ok(observations, command_id) and bool(_raw_output(observations, command_id).strip())


def _version(observations: Mapping[str, Mapping[str, Any]], command_id: str) -> str:
    return str(observations.get(command_id, {}).get("stdout_first_line") or "")


def parse_cli_help(tool_name: str, help_text: str) -> dict[str, bool]:
    text = help_text.lower()
    return {
        "noninteractive_supported": any(
            phrase in text
            for phrase in (
                "non-interactive",
                "noninteractively",
                "non-interactively",
                "headless",
                "print response and exit",
                "run a single prompt",
                "run codex non-interactively",
            )
        ),
        "accepts_stdin": "stdin" in text or "piped" in text,
        "accepts_prompt_file": "--prompt-file" in text
        or "--system-prompt-file" in text
        or "prompt file" in text,
        "supports_json_output": "--json" in text
        or "output-format" in text
        or "stream-json" in text
        or "json schema" in text
        or "jsonl" in text,
        "supports_model_selection": "--model" in text or "-m, --model" in text,
        "supports_no_tools_mode": "disable all tools" in text or "--tools" in text or "no tools" in text,
        "supports_no_file_access_mode": (
            ("disable all tools" in text or 'tools ""' in text or "--bare" in text)
            and tool_name in {"claude"}
        ),
        "supports_working_directory": "--cd" in text or "--worktree" in text or "--add-dir" in text,
        "supports_timeout": "timeout" in text,
    }


def _merge_features(*feature_sets: Mapping[str, bool]) -> dict[str, bool]:
    keys = {
        "noninteractive_supported",
        "accepts_stdin",
        "accepts_prompt_file",
        "supports_json_output",
        "supports_model_selection",
        "supports_no_tools_mode",
        "supports_no_file_access_mode",
        "supports_working_directory",
        "supports_timeout",
    }
    return {key: any(bool(features.get(key)) for features in feature_sets) for key in keys}


def parse_ollama_models(list_output: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in list_output.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 3:
            continue
        size = " ".join(parts[2:4]) if len(parts) >= 4 else parts[2]
        rows.append(
            {
                "model_ref": f"ollama:{parts[0]}",
                "runtime_ref": "ollama",
                "model_name": parts[0],
                "size_or_parameters": size,
                "local_only": True,
                "present": True,
                "invocation_allowed": False,
                "proof_bundle_allowed": False,
                "selected_for_pilot": False,
                "source": "ollama list",
                "notes": "Listed only; no model invocation or prompt was sent.",
            }
        )
    return rows


def _worker_mapping(
    *,
    worker_kind: str,
    dispatch_method: str,
    expected_output: str,
    proof_requirement: str,
    stop_condition: str,
    automatic_ingest_candidate: bool,
) -> dict[str, Any]:
    return {
        "worker_kind": worker_kind,
        "dispatch_method": dispatch_method,
        "expected_output": expected_output,
        "proof_requirement": proof_requirement,
        "stop_condition": stop_condition,
        "automatic_ingest_candidate": bool(automatic_ingest_candidate),
        "result_can_mutate_runtime_directly": False,
        "guardian_approval_remains_separate": True,
    }


def _record(
    *,
    provider: str,
    access_mode: str,
    tool_name: str,
    installed: bool,
    version: str,
    auth_status: str,
    subscription_backed: bool | str,
    api_billing_required: bool | str,
    features: Mapping[str, bool] | None = None,
    can_be_worker_run_manager_provider: bool = False,
    worker_run_manager_ready: bool = False,
    can_be_live_conversation_provider: bool = False,
    can_be_manual_handoff_provider: bool = False,
    recommended_use: str = "blocked",
    safety_notes: Sequence[str] = (),
    next_probe_required: str = "",
    worker_mapping: Mapping[str, Any] | None = None,
    evidence_refs: Sequence[str] = (),
    local_models: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    features = dict(features or {})
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": provider,
        "access_mode": access_mode,
        "tool_name": tool_name,
        "installed": bool(installed),
        "version": version,
        "auth_status": auth_status,
        "subscription_backed": subscription_backed,
        "api_billing_required": api_billing_required,
        "noninteractive_supported": bool(features.get("noninteractive_supported", False)),
        "accepts_stdin": bool(features.get("accepts_stdin", False)),
        "accepts_prompt_file": bool(features.get("accepts_prompt_file", False)),
        "supports_json_output": bool(features.get("supports_json_output", False)),
        "supports_model_selection": bool(features.get("supports_model_selection", False)),
        "supports_no_tools_mode": bool(features.get("supports_no_tools_mode", False)),
        "supports_no_file_access_mode": bool(features.get("supports_no_file_access_mode", False)),
        "supports_working_directory": bool(features.get("supports_working_directory", False)),
        "supports_timeout": bool(features.get("supports_timeout", False)),
        "can_be_worker_run_manager_provider": bool(can_be_worker_run_manager_provider),
        "worker_run_manager_ready": bool(worker_run_manager_ready),
        "can_be_live_conversation_provider": bool(can_be_live_conversation_provider),
        "can_be_manual_handoff_provider": bool(can_be_manual_handoff_provider),
        "recommended_use": recommended_use,
        "safety_notes": list(safety_notes),
        "next_probe_required": next_probe_required,
        "worker_run_manager_mapping": dict(worker_mapping or {}),
        "evidence_refs": list(evidence_refs),
        "local_models": [dict(row) for row in local_models],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "api_billing_preferred": False,
        "execution_allowed": False,
        "tools_allowed": False,
        "desktop_app_control": False,
    }


def build_provider_records(observations: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    codex_features = _merge_features(
        parse_cli_help("codex", _raw_output(observations, "codex_help")),
        parse_cli_help("codex", _raw_output(observations, "codex_exec_help")),
    )
    gemini_features = parse_cli_help("gemini", _raw_output(observations, "gemini_help"))
    agy_features = parse_cli_help("agy", _raw_output(observations, "agy_help"))
    claude_features = parse_cli_help("claude", _raw_output(observations, "claude_help"))
    ollama_models = parse_ollama_models(_raw_output(observations, "ollama_list")) if _command_ok(observations, "ollama_list") else []

    return [
        _record(
            provider="openai_codex_cli",
            access_mode="cli_installed_auth_unknown" if _installed(observations, "codex_which") else "unavailable",
            tool_name="codex",
            installed=_installed(observations, "codex_which"),
            version=_version(observations, "codex_version"),
            auth_status="unknown",
            subscription_backed="unknown",
            api_billing_required="unknown",
            features=codex_features,
            can_be_worker_run_manager_provider=_installed(observations, "codex_which")
            and bool(codex_features["noninteractive_supported"]),
            can_be_live_conversation_provider=False,
            can_be_manual_handoff_provider=True,
            recommended_use="code_worker" if _installed(observations, "codex_which") else "blocked",
            safety_notes=(
                "CLI is installed and help shows noninteractive exec, stdin input, output schema, JSONL events, model selection, sandbox, working directory, and output-file support.",
                "Authentication and subscription backing were not probed because this audit does not inspect auth stores or run model calls.",
                "Experimental app-server and remote-control help exists, but no daemon was started; treat it as not approved for OpenClaw automation yet.",
            ),
            next_probe_required="operator-approved auth/status probe and one bounded worker package dry run before automated dispatch",
            worker_mapping=_worker_mapping(
                worker_kind="codex_cli_if_available",
                dispatch_method="scripts/openclaw_run.py dispatch <package_id> --worker codex_cli_if_available",
                expected_output="result JSON or output-last-message report file",
                proof_requirement="package claim, command transcript summary, diff/test receipts, unsafe scan",
                stop_condition="stop before push, external business action, or unsupported authority claim",
                automatic_ingest_candidate=True,
            ),
            evidence_refs=("codex --help", "codex exec --help", "codex app-server --help"),
        ),
        _record(
            provider="openai_codex_desktop_app",
            access_mode="desktop_app_manual",
            tool_name="Codex desktop/app",
            installed=False,
            version="",
            auth_status="unknown",
            subscription_backed="unknown",
            api_billing_required="unknown",
            can_be_manual_handoff_provider=True,
            recommended_use="manual_only",
            safety_notes=(
                "No desktop app private state was inspected and no GUI automation was attempted.",
                "Codex app-server help exists in the CLI, but no supported OpenClaw bridge was configured or started in this audit.",
            ),
            next_probe_required="operator review of supported Codex app-server/desktop bridge before any automation",
            worker_mapping=_worker_mapping(
                worker_kind="human",
                dispatch_method="manual handoff with operator-visible package/report",
                expected_output="operator-copied report or PR/diff receipt",
                proof_requirement="operator artifact manifest and package result receipt",
                stop_condition="manual surface only until a supported bridge is approved",
                automatic_ingest_candidate=False,
            ),
            evidence_refs=("codex app-server --help", "codex remote-control --help"),
        ),
        _record(
            provider="chatgpt_desktop_app_web",
            access_mode="manual_handoff",
            tool_name="ChatGPT desktop/app/web",
            installed=False,
            version="",
            auth_status="unknown",
            subscription_backed="unknown",
            api_billing_required=False,
            can_be_manual_handoff_provider=True,
            recommended_use="manual_only",
            safety_notes=(
                "No supported local CLI/API automation bridge for the ChatGPT app was verified.",
                "Do not automate GUI clicking or browser scraping; use manual handoff with synthetic/redacted packages only.",
            ),
            next_probe_required="operator-confirmed supported bridge or keep manual handoff only",
            worker_mapping=_worker_mapping(
                worker_kind="human",
                dispatch_method="manual paste/upload of redacted package by operator",
                expected_output="operator-pasted response captured as candidate text",
                proof_requirement="capture receipt, verifier receipt, no-private-proof receipt",
                stop_condition="candidate text only; verifier decides publishability",
                automatic_ingest_candidate=False,
            ),
        ),
        _record(
            provider="google_gemini_cli",
            access_mode="cli_installed_auth_unknown" if _installed(observations, "gemini_which") else "unavailable",
            tool_name="gemini",
            installed=_installed(observations, "gemini_which"),
            version=_version(observations, "gemini_version"),
            auth_status="unknown",
            subscription_backed="unknown",
            api_billing_required="unknown",
            features=gemini_features,
            can_be_worker_run_manager_provider=_installed(observations, "gemini_which")
            and bool(gemini_features["noninteractive_supported"]),
            recommended_use="form_fill_advisor" if _installed(observations, "gemini_which") else "blocked",
            safety_notes=(
                "CLI is installed and help shows headless prompt mode, stdin append behavior, JSON/stream-json output, model selection, sandbox flag, worktree, and policy controls.",
                "This audit did not prove whether Gemini CLI avoids API-key billing or uses subscription-backed login.",
                "Gemini API-key route remains not preferred; current API route was previously blocked by RESOURCE_EXHAUSTED/prepayment credits depleted.",
            ),
            next_probe_required="operator-approved auth/billing-mode proof before use as a subscription-backed worker",
            worker_mapping=_worker_mapping(
                worker_kind="gemini",
                dispatch_method="scripts/openclaw_run.py dispatch <package_id> --worker gemini",
                expected_output="JSON/report file from headless CLI after operator-approved probe",
                proof_requirement="package claim, no-private-proof receipt, verifier/result receipt",
                stop_condition="stop before API-key fallback, tool use, or business action",
                automatic_ingest_candidate=True,
            ),
            evidence_refs=("gemini --help", "gemini --version"),
        ),
        _record(
            provider="google_antigravity_cli",
            access_mode="cli_installed_auth_unknown" if _installed(observations, "agy_which") else "unavailable",
            tool_name="agy",
            installed=_installed(observations, "agy_which"),
            version=_version(observations, "agy_version"),
            auth_status="unknown",
            subscription_backed="unknown",
            api_billing_required="unknown",
            features=agy_features,
            can_be_worker_run_manager_provider=_installed(observations, "agy_which")
            and bool(agy_features["noninteractive_supported"]),
            recommended_use="architecture_review" if _installed(observations, "agy_which") else "blocked",
            safety_notes=(
                "Antigravity CLI is installed and help shows --print noninteractive mode, --model, --sandbox, add-dir, and print-timeout.",
                "No model list or prompt was run; subscription/auth/billing path remains unproven.",
                "Do not use dangerously-skip-permissions for OpenClaw packages.",
            ),
            next_probe_required="operator-approved auth/billing-mode proof and no-tools/no-file boundary review",
            worker_mapping=_worker_mapping(
                worker_kind="gemini",
                dispatch_method="scripts/openclaw_run.py dispatch <package_id> --worker gemini --note 'Antigravity CLI candidate'",
                expected_output="single printed response captured to report file",
                proof_requirement="package claim, timeout receipt, no unsafe permission receipt",
                stop_condition="stop before broad workspace/tool access or business action",
                automatic_ingest_candidate=True,
            ),
            evidence_refs=("agy --help", "agy --version"),
        ),
        _record(
            provider="anthropic_claude_cli",
            access_mode="cli_installed_auth_unknown" if _installed(observations, "claude_which") else "unavailable",
            tool_name="claude",
            installed=_installed(observations, "claude_which"),
            version=_version(observations, "claude_version"),
            auth_status="unknown",
            subscription_backed="unknown",
            api_billing_required="unknown",
            features=claude_features,
            can_be_worker_run_manager_provider=_installed(observations, "claude_which")
            and bool(claude_features["noninteractive_supported"]),
            recommended_use="architecture_review" if _installed(observations, "claude_which") else "blocked",
            safety_notes=(
                "Claude CLI is installed and help shows --print, output-format json/stream-json, json-schema, model aliases including fable/opus/sonnet, tools control, permission modes, and safe/bare modes.",
                "Fable/Opus/Sonnet are help-listed aliases; Haiku was not observed in local help and is not claimed available.",
                "Authentication/subscription backing was not probed; auth status would require a separately approved safe status check.",
            ),
            next_probe_required="operator-approved claude auth status/proof of subscription mode and one no-tools package smoke",
            worker_mapping=_worker_mapping(
                worker_kind="fable",
                dispatch_method="scripts/openclaw_run.py dispatch <package_id> --worker fable",
                expected_output="json or stream-json review result",
                proof_requirement="package claim, no-tools receipt, verifier/review receipt",
                stop_condition="stop before tool expansion, browser use, or direct runtime mutation",
                automatic_ingest_candidate=True,
            ),
            evidence_refs=("claude --help", "claude --version"),
        ),
        _record(
            provider="local_ollama_runtime",
            access_mode="local_runtime" if _installed(observations, "ollama_which") else "unavailable",
            tool_name="ollama",
            installed=_installed(observations, "ollama_which"),
            version="",
            auth_status="unknown",
            subscription_backed=False,
            api_billing_required=False,
            can_be_worker_run_manager_provider=bool(ollama_models),
            recommended_use="local_redaction" if ollama_models else "blocked",
            safety_notes=(
                "Ollama is local runtime access, not subscription-backed access.",
                "Only 'ollama list' was run; no model was invoked and no prompt/proof bundle was sent.",
                "Local models are suitable first for private classification/redaction and bounded proof-to-response after explicit invocation approval.",
            ),
            next_probe_required="operator-approved local invocation boundary before any model run",
            worker_mapping=_worker_mapping(
                worker_kind="local_script",
                dispatch_method="scripts/openclaw_run.py dispatch <package_id> --worker local_script",
                expected_output="local adapter result file with verifier receipt",
                proof_requirement="model invocation boundary, redaction receipt, verifier pass/fail receipt",
                stop_condition="one approved invocation only; no tools or business action",
                automatic_ingest_candidate=True,
            ),
            evidence_refs=("ollama list",),
            local_models=ollama_models,
        ),
        _record(
            provider="api_key_overage_routes",
            access_mode="api_key_available_but_not_preferred",
            tool_name="provider API keys",
            installed=False,
            version="",
            auth_status="unknown",
            subscription_backed=False,
            api_billing_required=True,
            recommended_use="blocked",
            safety_notes=(
                "API-key billing/credit-pool routes are explicitly not preferred for this task.",
                "Gemini API readiness was previously blocked by RESOURCE_EXHAUSTED/prepayment credits depleted.",
                "Use API routes only when explicitly configured and approved.",
            ),
            next_probe_required="none unless operator explicitly chooses API fallback",
            worker_mapping=_worker_mapping(
                worker_kind="human",
                dispatch_method="do not dispatch by default",
                expected_output="not applicable",
                proof_requirement="explicit operator approval and billing boundary receipt",
                stop_condition="blocked until explicit API fallback decision",
                automatic_ingest_candidate=False,
            ),
        ),
    ]


def preferred_access_order(records: Sequence[Mapping[str, Any]]) -> list[str]:
    subscription_cli = [
        str(record["provider"])
        for record in records
        if (
            record.get("access_mode")
            in {
                "cli_authenticated",
                "cli_authenticated_subscription",
                "cli_authenticated_billing_unknown",
                "cli_installed_auth_unknown",
            }
            and record.get("installed") is True
        )
    ]
    manual = [
        str(record["provider"])
        for record in records
        if record.get("access_mode") in {"desktop_app_manual", "manual_handoff"}
    ]
    local = [str(record["provider"]) for record in records if record.get("access_mode") == "local_runtime"]
    api = [str(record["provider"]) for record in records if record.get("access_mode") == "api_key_available_but_not_preferred"]
    return subscription_cli + manual + local + api


def _walk_values(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    return sorted({key for key, value in _walk_values(payload) if key in UNSAFE_TRUE_KEYS and value is True})


def _public_observations(observations: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for command_id, observation in sorted(observations.items()):
        row = {key: value for key, value in observation.items() if not key.startswith("_")}
        rows.append(dict(row))
    return rows


def _status(records: Sequence[Mapping[str, Any]], observations: Mapping[str, Mapping[str, Any]]) -> str:
    if any(record.get("installed") for record in records):
        return READY_STATUS
    if observations:
        return PARTIAL_STATUS
    return PARTIAL_STATUS


def build_provider_access_catalog(
    *,
    observations: Mapping[str, Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    observations = dict(observations or collect_safe_cli_observations())
    records = build_provider_records(observations)
    worker_records = [record for record in records if record.get("can_be_worker_run_manager_provider")]
    live_records = [record for record in records if record.get("can_be_live_conversation_provider")]
    manual_records = [record for record in records if record.get("can_be_manual_handoff_provider")]
    subscription_proven = [
        str(record["provider"])
        for record in records
        if record.get("subscription_backed") is True and record.get("installed") is True
    ]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": _status(records, observations),
        "goal": "Audit subscription-backed LM access paths without API overage/credit-pool reliance.",
        "catalog_scope": "access_modes_not_model_catalog",
        "provider_access_modes": records,
        "router_policy_recommendation": {
            "preferred_order": preferred_access_order(records),
            "prefer_subscription_backed_cli_or_app_lanes": True,
            "api_key_routes_not_preferred_by_default": True,
            "codex_cli_default_for_repo_code_worker": any(
                record["provider"] == "openai_codex_cli" and record.get("can_be_worker_run_manager_provider")
                for record in records
            ),
            "chatgpt_app_manual_only_without_supported_bridge": True,
            "external_api_routes_require_explicit_approval": True,
            "subscription_backing_proven_for": subscription_proven,
            "subscription_backing_unproven_for": [
                str(record["provider"])
                for record in records
                if record.get("subscription_backed") == "unknown" and record.get("installed")
            ],
        },
        "worker_run_manager_integration": {
            "usable_worker_candidate_count": len(worker_records),
            "worker_candidates": [
                {
                    "provider": record["provider"],
                    "tool_name": record["tool_name"],
                    "recommended_use": record["recommended_use"],
                    "worker_run_manager_mapping": record["worker_run_manager_mapping"],
                    "next_probe_required": record["next_probe_required"],
                }
                for record in worker_records
            ],
            "manual_handoff_candidates": [record["provider"] for record in manual_records],
            "live_conversation_candidates": [record["provider"] for record in live_records],
        },
        "command_observations": _public_observations(observations),
        "machine_proof": {
            "safe_discovery_command_count": len(observations),
            "generation_probe_performed": False,
            "model_invocation_performed": False,
            "prompt_sent": False,
            "proof_bundle_sent": False,
            "api_key_billing_call_performed": False,
            "credential_values_logged": False,
            "auth_store_inspected": False,
            "desktop_app_automation_performed": False,
            "gui_automation_performed": False,
            "browser_automation_performed": False,
            "worker_spawn_performed": False,
            "runtime_mutation_performed": False,
            "authority_boundary_all_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    payload["machine_proof"]["unsafe_true_grants"] = unsafe_true_grants(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def render_operator_markdown(payload: Mapping[str, Any]) -> str:
    records = list(payload.get("provider_access_modes") or [])
    lines = [
        "# Provider Access Catalog",
        "",
        f"Status: {payload.get('status')}",
        "",
        "This is an access-mode audit only. It did not invoke models, send prompts, inspect credential stores, or automate desktop apps.",
        "",
        "## Recommended Order",
    ]
    for provider in payload.get("router_policy_recommendation", {}).get("preferred_order", []):
        lines.append(f"- {provider}")
    lines.extend(["", "## Access Modes"])
    for record in records:
        lines.extend(
            [
                f"- {record.get('provider')}: {record.get('access_mode')}",
                f"  - installed: {record.get('installed')}",
                f"  - auth_status: {record.get('auth_status')}",
                f"  - subscription_backed: {record.get('subscription_backed')}",
                f"  - api_billing_required: {record.get('api_billing_required')}",
                f"  - worker_candidate: {record.get('can_be_worker_run_manager_provider')}",
                f"  - worker_ready: {record.get('worker_run_manager_ready')}",
                f"  - live_conversation_candidate: {record.get('can_be_live_conversation_provider')}",
                f"  - recommended_use: {record.get('recommended_use')}",
                f"  - next_probe_required: {record.get('next_probe_required')}",
            ]
        )
    lines.extend(
        [
            "",
            "## Do Not Automate",
            "- ChatGPT/Codex desktop GUI clicking or browser scraping.",
            "- Provider API-key fallback without explicit approval and billing boundary receipt.",
            "- Tool/file access expansion from a model result.",
            "- Business actions, email sends, Coupa/browser actions, ledger/workbook/PDF mutation, paid marking, or Guardian approvals.",
            "",
            "## Worker Run Manager",
            "Usable CLI candidates should be dispatched through the existing package lifecycle and ingested only from recorded result files. The model result never mutates runtime directly.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_provider_access_catalog(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    observations: Mapping[str, Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_provider_access_catalog(observations=observations, generated_at=generated_at)
    export_root = _rooted(export_root)
    wiki_path = _rooted(wiki_path)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    _write_json(json_path, payload)
    _write_text(operator_path, render_operator_markdown(payload))
    _write_text(wiki_path, render_operator_markdown(payload))
    return {
        "status": payload["status"],
        "read_model_path": str(json_path),
        "operator_path": str(operator_path),
        "wiki_path": str(wiki_path),
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export subscription-backed LM access catalog.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = export_provider_access_catalog(export_root=Path(args.export_root), wiki_path=Path(args.wiki_path))
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
