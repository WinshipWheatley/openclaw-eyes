"""Safe subscription CLI auth status probe.

This module runs only local CLI version/help/auth-status inventory commands.
It does not invoke models, send prompts, inspect auth token stores, read
credential files, call provider APIs, automate desktop apps, or mutate runtime
state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import provider_access_catalog as access_catalog


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Subscription Backed LM Access.md")

SCHEMA_VERSION = "PROVIDER_ACCESS_AUTH_STATUS_V0"
READ_MODEL_ID = "provider_access_auth_status"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "OPENCLAW_SUBSCRIPTION_CLI_AUTH_STATUS_PROBE_READY"
PARTIAL_STATUS = "OPENCLAW_SUBSCRIPTION_CLI_AUTH_STATUS_PROBE_PARTIAL"

AUTH_STATUS_VALUES = {
    "authenticated_subscription",
    "authenticated_unknown_billing",
    "api_key_configured",
    "installed_not_authenticated",
    "unknown",
    "blocked",
}

SAFE_AUTH_PROBE_COMMANDS: dict[str, list[str]] = {
    "codex_which": ["which", "codex"],
    "codex_version": ["codex", "--version"],
    "codex_help": ["codex", "--help"],
    "codex_exec_help": ["codex", "exec", "--help"],
    "codex_login_help": ["codex", "login", "--help"],
    "codex_login_status_help": ["codex", "login", "status", "--help"],
    "codex_login_status": ["codex", "login", "status"],
    "gemini_which": ["which", "gemini"],
    "gemini_version": ["gemini", "--version"],
    "gemini_help": ["gemini", "--help"],
    "agy_which": ["which", "agy"],
    "agy_version": ["agy", "--version"],
    "agy_help": ["agy", "--help"],
    "claude_which": ["which", "claude"],
    "claude_version": ["claude", "--version"],
    "claude_help": ["claude", "--help"],
    "claude_auth_help": ["claude", "auth", "--help"],
    "claude_auth_status_help": ["claude", "auth", "status", "--help"],
    "claude_auth_status": ["claude", "auth", "status", "--json"],
    "ollama_which": ["which", "ollama"],
    "ollama_list": ["ollama", "list"],
}

AUTHORITY_BOUNDARY = {
    "model_invocation_performed": False,
    "generation_probe_performed": False,
    "prompt_sent": False,
    "proof_bundle_sent": False,
    "api_key_billing_call_performed": False,
    "paid_api_endpoint_called": False,
    "auth_store_inspected": False,
    "credential_value_read": False,
    "credential_value_logged": False,
    "auth_token_store_read": False,
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
    "credential_value_logged",
}

SECRET_VALUE_PATTERN = re.compile(
    r"(?i)(api[_-]?key|token|secret|credential|password|private[_-]?key)\s*[:=]\s*([^\s]+)"
)
LONG_SECRET_PATTERN = re.compile(r"(?i)\b(sk-[A-Za-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{12,})\b")
EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")


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


def _content_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def redact_probe_text(value: str) -> tuple[str, dict[str, int]]:
    counts = {"credential_value_patterns": 0, "long_secret_patterns": 0, "account_identifiers": 0}

    def _replace_key_value(match: re.Match[str]) -> str:
        counts["credential_value_patterns"] += 1
        return f"{match.group(1)}=<redacted>"

    redacted = SECRET_VALUE_PATTERN.sub(_replace_key_value, value)
    redacted, long_secret_count = LONG_SECRET_PATTERN.subn("<redacted-secret>", redacted)
    redacted, account_count = EMAIL_PATTERN.subn("<redacted-account>", redacted)
    counts["long_secret_patterns"] += long_secret_count
    counts["account_identifiers"] += account_count
    return redacted, counts


def _first_nonempty_line(value: str) -> str:
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:240]
    return ""


def _merge_counts(*counts: Mapping[str, int]) -> dict[str, int]:
    merged = {"credential_value_patterns": 0, "long_secret_patterns": 0, "account_identifiers": 0}
    for row in counts:
        for key in merged:
            merged[key] += int(row.get(key, 0))
    return merged


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
    stdout_redacted, stdout_counts = redact_probe_text(stdout)
    stderr_redacted, stderr_counts = redact_probe_text(stderr)
    redactions = _merge_counts(stdout_counts, stderr_counts)
    return {
        "command_id": command_id,
        "command": list(command),
        "command_kind": "safe_auth_or_help_probe",
        "returncode": int(returncode),
        "ok": returncode == 0 and not timed_out and not error,
        "timed_out": bool(timed_out),
        "error": str(error or ""),
        "stdout_first_line": _first_nonempty_line(stdout_redacted),
        "stderr_first_line": _first_nonempty_line(stderr_redacted),
        "stdout_line_count": len(stdout.splitlines()),
        "stderr_line_count": len(stderr.splitlines()),
        "redactions": redactions,
        "raw_output_stored": False,
        "_stdout": stdout_redacted,
        "_stderr": stderr_redacted,
    }


def run_safe_auth_probe_command(
    command_id: str,
    command: Sequence[str],
    *,
    timeout_seconds: int = 8,
) -> dict[str, Any]:
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


def collect_safe_auth_observations() -> dict[str, dict[str, Any]]:
    return {
        command_id: run_safe_auth_probe_command(command_id, command)
        for command_id, command in SAFE_AUTH_PROBE_COMMANDS.items()
    }


def _raw_output(observations: Mapping[str, Mapping[str, Any]], command_id: str) -> str:
    row = observations.get(command_id, {})
    parts = [value for value in (row.get("_stdout", ""), row.get("_stderr", "")) if isinstance(value, str) and value]
    return "\n".join(parts)


def _command_ok(observations: Mapping[str, Mapping[str, Any]], command_id: str) -> bool:
    return bool(observations.get(command_id, {}).get("ok"))


def _installed(observations: Mapping[str, Mapping[str, Any]], command_id: str) -> bool:
    return _command_ok(observations, command_id) and bool(_raw_output(observations, command_id).strip())


def _version(observations: Mapping[str, Mapping[str, Any]], command_id: str) -> str:
    return str(observations.get(command_id, {}).get("stdout_first_line") or "")


def _parse_json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def classify_auth_output(
    *,
    tool_name: str,
    installed: bool,
    status_command_observation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not installed:
        return {
            "auth_status": "blocked",
            "subscription_backed": False,
            "api_billing_required": "unknown",
            "subscription_backing_proven": False,
            "api_key_configured": False,
            "auth_probe_supported": False,
            "classification_reason": "CLI is not installed.",
        }

    if not status_command_observation:
        return {
            "auth_status": "unknown",
            "subscription_backed": "unknown",
            "api_billing_required": "unknown",
            "subscription_backing_proven": False,
            "api_key_configured": False,
            "auth_probe_supported": False,
            "classification_reason": "No safe documented auth status command was available in CLI help.",
        }

    stdout = str(status_command_observation.get("_stdout") or "")
    stderr = str(status_command_observation.get("_stderr") or "")
    combined = "\n".join(part for part in (stdout, stderr) if part).strip()
    text = combined.lower()
    parsed = _parse_json_object(combined)
    parsed_text = json.dumps(parsed, sort_keys=True).lower() if parsed else ""
    check_text = "\n".join(part for part in (text, parsed_text) if part)

    if any(phrase in check_text for phrase in ("not logged in", "not authenticated", "not signed in", "login required")):
        return {
            "auth_status": "installed_not_authenticated",
            "subscription_backed": False,
            "api_billing_required": "unknown",
            "subscription_backing_proven": False,
            "api_key_configured": False,
            "auth_probe_supported": True,
            "classification_reason": "Status output indicates the CLI is not signed in.",
        }

    api_key_terms = ("api key", "apikey", "api_key", "anthropic_auth_token", "openai_api_key")
    if any(term in check_text for term in api_key_terms):
        return {
            "auth_status": "api_key_configured",
            "subscription_backed": False,
            "api_billing_required": True,
            "subscription_backing_proven": False,
            "api_key_configured": True,
            "auth_probe_supported": True,
            "classification_reason": "Status output indicates API-key or token-backed auth rather than subscription-backed CLI use.",
        }

    subscription_terms = ("subscription", "chatgpt plus", "chatgpt pro", "team plan", "enterprise", "max plan")
    authenticated_terms = ("logged in", "signed in", "authenticated", '"isloggedin": true', '"authenticated": true')
    if any(term in check_text for term in subscription_terms):
        return {
            "auth_status": "authenticated_subscription",
            "subscription_backed": True,
            "api_billing_required": False,
            "subscription_backing_proven": True,
            "api_key_configured": False,
            "auth_probe_supported": True,
            "classification_reason": "Status output explicitly indicates subscription or ChatGPT subscription-plan backed access.",
        }

    if any(term in check_text for term in authenticated_terms):
        return {
            "auth_status": "authenticated_unknown_billing",
            "subscription_backed": "unknown",
            "api_billing_required": "unknown",
            "subscription_backing_proven": False,
            "api_key_configured": False,
            "auth_probe_supported": True,
            "classification_reason": "Status output indicates authentication but does not prove whether billing is subscription-backed or API-key backed.",
        }

    if status_command_observation.get("ok"):
        return {
            "auth_status": "unknown",
            "subscription_backed": "unknown",
            "api_billing_required": "unknown",
            "subscription_backing_proven": False,
            "api_key_configured": False,
            "auth_probe_supported": True,
            "classification_reason": "Status command returned successfully but did not expose a conclusive auth/billing mode.",
        }

    return {
        "auth_status": "unknown",
        "subscription_backed": "unknown",
        "api_billing_required": "unknown",
        "subscription_backing_proven": False,
        "api_key_configured": False,
        "auth_probe_supported": True,
        "classification_reason": "Status command did not complete successfully; auth/billing mode remains unknown.",
    }


def _features(observations: Mapping[str, Mapping[str, Any]], tool_name: str, *command_ids: str) -> dict[str, bool]:
    merged = [
        access_catalog.parse_cli_help(tool_name, _raw_output(observations, command_id))
        for command_id in command_ids
    ]
    return access_catalog._merge_features(*merged)


def _tool_record(
    *,
    provider: str,
    tool_name: str,
    installed: bool,
    version: str,
    features: Mapping[str, bool],
    auth: Mapping[str, Any],
    status_probe_command_id: str | None,
    manual_only: bool,
    recommended_use_if_ready: str,
    unknown_next_probe: str,
    local_runtime: bool = False,
    local_models: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    auth_status = str(auth.get("auth_status", "unknown"))
    subscription_proven = bool(auth.get("subscription_backing_proven", False))
    worker_candidate = bool(installed and features.get("noninteractive_supported", False))
    if local_runtime:
        worker_candidate = bool(installed and local_models)
    worker_ready = bool(worker_candidate and subscription_proven)
    if local_runtime:
        worker_ready = False
    return {
        "provider": provider,
        "tool_name": tool_name,
        "installed": bool(installed),
        "version": version,
        "auth_status": auth_status,
        "subscription_backed": auth.get("subscription_backed", "unknown"),
        "subscription_backing_proven": subscription_proven,
        "api_billing_required": auth.get("api_billing_required", "unknown"),
        "api_key_configured": bool(auth.get("api_key_configured", False)),
        "status_probe_command_id": status_probe_command_id,
        "auth_probe_supported": bool(auth.get("auth_probe_supported", False)),
        "classification_reason": auth.get("classification_reason", ""),
        "noninteractive_mode_supported": bool(features.get("noninteractive_supported", False)),
        "stdin_prompt_input_supported": bool(features.get("accepts_stdin", False)),
        "prompt_file_package_input_supported": bool(features.get("accepts_prompt_file", False)),
        "json_report_output_supported": bool(features.get("supports_json_output", False)),
        "model_selection_supported": bool(features.get("supports_model_selection", False)),
        "no_tools_no_file_access_supported": bool(
            features.get("supports_no_tools_mode", False) or features.get("supports_no_file_access_mode", False)
        ),
        "timeout_supported": bool(features.get("supports_timeout", False)),
        "worker_run_manager_candidate": worker_candidate,
        "worker_run_manager_ready": worker_ready,
        "live_conversation_candidate": False,
        "manual_only": bool(manual_only or not worker_ready),
        "recommended_use_if_ready": recommended_use_if_ready,
        "next_safe_probe_or_action": "" if worker_ready else unknown_next_probe,
        "local_models": [dict(row) for row in local_models],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "tools_allowed": False,
        "execution_allowed": False,
        "desktop_app_control": False,
        "api_billing_preferred": False,
    }


def build_auth_status_records(observations: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    codex_auth = classify_auth_output(
        tool_name="codex",
        installed=_installed(observations, "codex_which"),
        status_command_observation=observations.get("codex_login_status"),
    )
    claude_auth = classify_auth_output(
        tool_name="claude",
        installed=_installed(observations, "claude_which"),
        status_command_observation=observations.get("claude_auth_status"),
    )
    gemini_auth = classify_auth_output(
        tool_name="gemini",
        installed=_installed(observations, "gemini_which"),
        status_command_observation=None,
    )
    agy_auth = classify_auth_output(
        tool_name="agy",
        installed=_installed(observations, "agy_which"),
        status_command_observation=None,
    )
    ollama_models = (
        access_catalog.parse_ollama_models(_raw_output(observations, "ollama_list"))
        if _command_ok(observations, "ollama_list")
        else []
    )
    ollama_auth = {
        "auth_status": "unknown",
        "subscription_backed": False,
        "api_billing_required": False,
        "subscription_backing_proven": False,
        "api_key_configured": False,
        "auth_probe_supported": False,
        "classification_reason": "Ollama is local runtime inventory, not subscription-backed CLI auth.",
    }
    return [
        _tool_record(
            provider="openai_codex_cli",
            tool_name="codex",
            installed=_installed(observations, "codex_which"),
            version=_version(observations, "codex_version"),
            features=_features(observations, "codex", "codex_help", "codex_exec_help"),
            auth=codex_auth,
            status_probe_command_id="codex_login_status",
            manual_only=False,
            recommended_use_if_ready="repo_code_worker",
            unknown_next_probe="operator-approved bounded dry-run only after subscription backing is proven",
        ),
        _tool_record(
            provider="google_gemini_cli",
            tool_name="gemini",
            installed=_installed(observations, "gemini_which"),
            version=_version(observations, "gemini_version"),
            features=_features(observations, "gemini", "gemini_help"),
            auth=gemini_auth,
            status_probe_command_id=None,
            manual_only=True,
            recommended_use_if_ready="advisory_form_fill",
            unknown_next_probe="find a documented safe Gemini CLI auth/status command or keep manual/API routes separate",
        ),
        _tool_record(
            provider="google_antigravity_cli",
            tool_name="agy",
            installed=_installed(observations, "agy_which"),
            version=_version(observations, "agy_version"),
            features=_features(observations, "agy", "agy_help"),
            auth=agy_auth,
            status_probe_command_id=None,
            manual_only=True,
            recommended_use_if_ready="architecture_review",
            unknown_next_probe="find a documented safe Antigravity auth/status command and prove no broad workspace/tool access",
        ),
        _tool_record(
            provider="anthropic_claude_cli",
            tool_name="claude",
            installed=_installed(observations, "claude_which"),
            version=_version(observations, "claude_version"),
            features=_features(observations, "claude", "claude_help"),
            auth=claude_auth,
            status_probe_command_id="claude_auth_status",
            manual_only=False,
            recommended_use_if_ready="review_worker",
            unknown_next_probe="prove Claude auth plan/billing mode without API-key generation or token output",
        ),
        _tool_record(
            provider="local_ollama_runtime",
            tool_name="ollama",
            installed=_installed(observations, "ollama_which"),
            version="",
            features={},
            auth=ollama_auth,
            status_probe_command_id="ollama_list",
            manual_only=True,
            recommended_use_if_ready="local_redaction_after_invocation_approval",
            unknown_next_probe="operator-approved local invocation boundary before any model run",
            local_runtime=True,
            local_models=ollama_models,
        ),
    ]


def _public_observations(observations: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for command_id, observation in sorted(observations.items()):
        rows.append({key: value for key, value in observation.items() if not key.startswith("_")})
    return rows


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


def _status(records: Sequence[Mapping[str, Any]], observations: Mapping[str, Mapping[str, Any]]) -> str:
    if not observations:
        return PARTIAL_STATUS
    if not records:
        return PARTIAL_STATUS
    if any(row.get("timed_out") for row in observations.values()):
        return PARTIAL_STATUS
    return READY_STATUS


def build_provider_access_auth_status(
    *,
    observations: Mapping[str, Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    observations = dict(observations or collect_safe_auth_observations())
    records = build_auth_status_records(observations)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": _status(records, observations),
        "goal": "Safely prove local CLI auth/subscription status without API-key billing or generation probes.",
        "records": records,
        "worker_run_manager_ready": [row["provider"] for row in records if row.get("worker_run_manager_ready")],
        "worker_run_manager_candidates": [row["provider"] for row in records if row.get("worker_run_manager_candidate")],
        "live_conversation_candidates": [row["provider"] for row in records if row.get("live_conversation_candidate")],
        "manual_only": [row["provider"] for row in records if row.get("manual_only")],
        "api_billing_required": [
            row["provider"] for row in records if row.get("api_billing_required") is True
        ],
        "unknowns": [
            {
                "provider": row["provider"],
                "reason": row.get("classification_reason", ""),
                "next_safe_probe_or_action": row.get("next_safe_probe_or_action", ""),
            }
            for row in records
            if row.get("auth_status") == "unknown" or row.get("subscription_backing_proven") is False
        ],
        "policy": {
            "prefer_subscription_backed_cli_app_lanes_over_api_key_billing_when_proven": True,
            "api_key_routes_are_fallback_not_preferred": True,
            "desktop_gui_automation_disallowed": True,
            "chatgpt_app_web_manual_only_until_supported_bridge": True,
            "no_generation_probe_by_default": True,
            "worker_run_manager_requires_auth_subscription_or_separate_local_invocation_boundary": True,
        },
        "command_observations": _public_observations(observations),
        "machine_proof": {
            "safe_probe_command_count": len(observations),
            "model_invocation_performed": False,
            "generation_probe_performed": False,
            "prompt_sent": False,
            "proof_bundle_sent": False,
            "api_key_billing_call_performed": False,
            "auth_store_inspected": False,
            "credential_value_read": False,
            "credential_value_logged": False,
            "raw_output_stored": False,
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


def _access_mode_for_auth(row: Mapping[str, Any], current_access_mode: str) -> str:
    if current_access_mode == "local_runtime":
        return current_access_mode
    status = row.get("auth_status")
    if status == "authenticated_subscription":
        return "cli_authenticated_subscription"
    if status == "authenticated_unknown_billing":
        return "cli_authenticated_billing_unknown"
    if status == "api_key_configured":
        return "cli_api_key_configured"
    if status == "installed_not_authenticated":
        return "cli_installed_not_authenticated"
    if row.get("installed"):
        return "cli_installed_auth_unknown"
    return current_access_mode


def merge_auth_status_into_catalog(
    catalog_payload: Mapping[str, Any],
    auth_payload: Mapping[str, Any],
) -> dict[str, Any]:
    merged = json.loads(stable_json(catalog_payload))
    auth_by_provider = {row["provider"]: row for row in auth_payload.get("records", [])}
    for record in merged.get("provider_access_modes", []):
        auth = auth_by_provider.get(record.get("provider"))
        if not auth:
            continue
        record["auth_status"] = auth["auth_status"]
        record["subscription_backed"] = auth["subscription_backed"]
        record["api_billing_required"] = auth["api_billing_required"]
        record["access_mode"] = _access_mode_for_auth(auth, str(record.get("access_mode", "")))
        record["worker_run_manager_ready"] = bool(auth.get("worker_run_manager_ready"))
        record["can_be_worker_run_manager_provider"] = bool(auth.get("worker_run_manager_candidate"))
        record["can_be_live_conversation_provider"] = bool(auth.get("live_conversation_candidate"))
        record["next_probe_required"] = auth.get("next_safe_probe_or_action") or record.get("next_probe_required", "")
        record["auth_status_probe_ref"] = READ_MODEL_ID
        record["auth_status_classification_reason"] = auth.get("classification_reason", "")
    records = merged.get("provider_access_modes", [])
    merged["router_policy_recommendation"]["subscription_backing_proven_for"] = [
        row["provider"] for row in records if row.get("subscription_backed") is True
    ]
    merged["router_policy_recommendation"]["subscription_backing_unproven_for"] = [
        row["provider"]
        for row in records
        if row.get("installed") is True and row.get("subscription_backed") == "unknown"
    ]
    merged["router_policy_recommendation"]["preferred_order"] = access_catalog.preferred_access_order(records)
    merged["worker_run_manager_integration"]["ready_worker_providers"] = [
        row["provider"] for row in records if row.get("worker_run_manager_ready") is True
    ]
    merged["worker_run_manager_integration"]["worker_candidates"] = [
        {
            "provider": row["provider"],
            "tool_name": row["tool_name"],
            "recommended_use": row["recommended_use"],
            "worker_run_manager_ready": row.get("worker_run_manager_ready", False),
            "worker_run_manager_mapping": row["worker_run_manager_mapping"],
            "next_probe_required": row["next_probe_required"],
        }
        for row in records
        if row.get("can_be_worker_run_manager_provider")
    ]
    merged["machine_proof"]["auth_status_probe_ref"] = READ_MODEL_ID
    merged["machine_proof"]["model_invocation_performed"] = False
    merged["machine_proof"]["generation_probe_performed"] = False
    merged["machine_proof"]["prompt_sent"] = False
    merged["machine_proof"]["proof_bundle_sent"] = False
    merged["machine_proof"]["auth_store_inspected"] = False
    merged["machine_proof"]["credential_values_logged"] = False
    merged["machine_proof"]["unsafe_true_grants"] = access_catalog.unsafe_true_grants(merged)
    merged["machine_proof"]["content_hash"] = access_catalog._content_hash(merged)
    return merged


def render_auth_status_markdown(payload: Mapping[str, Any]) -> str:
    def _display(value: Any) -> str:
        text = str(value if value is not None else "").strip()
        return text or "none"

    lines = [
        "# Subscription Backed LM Access",
        "",
        f"Status: {payload.get('status')}",
        "",
        "This probe used only local version/help/auth-status inventory commands. It did not invoke models, send prompts, inspect auth stores, print credentials, automate desktop apps, or mutate runtime state.",
        "",
        "## Summary",
        f"- Worker Run Manager ready: {', '.join(payload.get('worker_run_manager_ready') or ['none'])}",
        f"- Worker Run Manager candidates: {', '.join(payload.get('worker_run_manager_candidates') or ['none'])}",
        f"- Live conversation candidates: {', '.join(payload.get('live_conversation_candidates') or ['none'])}",
        f"- Manual-only until proven: {', '.join(payload.get('manual_only') or ['none'])}",
        f"- API billing required: {', '.join(payload.get('api_billing_required') or ['none'])}",
        "",
        "## CLI Status",
    ]
    for row in payload.get("records", []):
        lines.extend(
            [
                f"- {row.get('provider')}",
                f"  - installed: {row.get('installed')}",
                f"  - version: {_display(row.get('version'))}",
                f"  - auth_status: {row.get('auth_status')}",
                f"  - subscription_backed: {row.get('subscription_backed')}",
                f"  - api_billing_required: {row.get('api_billing_required')}",
                f"  - worker_candidate: {row.get('worker_run_manager_candidate')}",
                f"  - worker_ready: {row.get('worker_run_manager_ready')}",
                f"  - live_conversation_candidate: {row.get('live_conversation_candidate')}",
                f"  - manual_only: {row.get('manual_only')}",
                f"  - reason: {row.get('classification_reason')}",
                f"  - next: {row.get('next_safe_probe_or_action') or 'none'}",
            ]
        )
    lines.extend(
        [
            "",
            "## Policy",
            "- Prefer subscription-backed CLI/app lanes over API-key billing only after subscription backing is proven.",
            "- API-key routes are fallback, not preferred.",
            "- Desktop GUI and browser automation remain disallowed.",
            "- ChatGPT app/web remains manual-only until a supported bridge is proven.",
            "- Worker Run Manager dispatch requires either proven subscription-backed CLI auth or a separate local invocation boundary.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_provider_access_auth_status(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    observations: Mapping[str, Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
    update_catalog: bool = True,
) -> dict[str, Any]:
    payload = build_provider_access_auth_status(observations=observations, generated_at=generated_at)
    export_root = _rooted(export_root)
    wiki_path = _rooted(wiki_path)
    auth_path = export_root / JSON_EXPORT_NAME
    _write_json(auth_path, payload)
    _write_text(wiki_path, render_auth_status_markdown(payload))
    result = {
        "status": payload["status"],
        "auth_status_path": str(auth_path),
        "wiki_path": str(wiki_path),
        "content_hash": payload["machine_proof"]["content_hash"],
    }
    if update_catalog:
        catalog_payload = access_catalog.build_provider_access_catalog(generated_at=generated_at)
        merged_catalog = merge_auth_status_into_catalog(catalog_payload, payload)
        catalog_path = export_root / access_catalog.JSON_EXPORT_NAME
        operator_path = export_root / access_catalog.OPERATOR_EXPORT_NAME
        _write_json(catalog_path, merged_catalog)
        operator_text = access_catalog.render_operator_markdown(merged_catalog)
        _write_text(operator_path, operator_text)
        result.update(
            {
                "catalog_path": str(catalog_path),
                "operator_path": str(operator_path),
                "catalog_content_hash": merged_catalog["machine_proof"]["content_hash"],
            }
        )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export safe subscription CLI auth status probe.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--no-update-catalog", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = export_provider_access_auth_status(
        export_root=Path(args.export_root),
        wiki_path=Path(args.wiki_path),
        update_catalog=not args.no_update_catalog,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
