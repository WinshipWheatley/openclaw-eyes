import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import provider_access_auth_status as auth_status
import provider_access_catalog as access_catalog


FIXED_NOW = "2026-06-13T12:00:00+00:00"


def _obs(stdout: str = "", *, ok: bool = True, command: list[str] | None = None) -> dict:
    return auth_status._observation(
        command_id="fake",
        command=command or ["tool", "status"],
        returncode=0 if ok else 1,
        stdout=stdout,
    )


def _fake_observations(
    *,
    codex_status: str = "Logged in with ChatGPT Pro subscription as winship@example.test\n",
    claude_status: str = '{"authenticated": true, "account": "winship@example.test"}\n',
) -> dict[str, dict]:
    codex_help = """Codex CLI
Commands:
  exec            Run Codex non-interactively
  login           Manage login
Options:
  -m, --model <MODEL>
"""
    codex_exec_help = """Run Codex non-interactively
Arguments:
  [PROMPT] instructions are read from stdin
Options:
  --output-schema <FILE>
  --json
  -o, --output-last-message <FILE>
"""
    gemini_help = """Gemini CLI - Defaults to interactive mode. Use -p/--prompt for non-interactive (headless) mode.
Options:
  -m, --model
  -p, --prompt Run in non-interactive mode. Appended to input on stdin.
  -s, --sandbox Run in sandbox?
  -o, --output-format choices: text, json, stream-json
"""
    agy_help = """Usage of agy:
  --model Model for the current CLI session
  --print Run a single prompt non-interactively and print the response
  --print-timeout Timeout for print mode wait
  --sandbox Run in a sandbox with terminal restrictions enabled
"""
    claude_help = """Claude Code - starts an interactive session by default, use -p/--print for non-interactive output
Options:
  --model <model>
  -p, --print Print response and exit
  --output-format <format> choices: text, json, stream-json
  --json-schema <schema>
  --tools <tools...> Use "" to disable all tools.
  --bare skip hooks, plugin sync, keychain reads, and auto-discovery
"""
    ollama_list = """NAME                 ID              SIZE      MODIFIED
qwen3:8b-q4_K_M      500a1f067a9f    5.2 GB    7 weeks ago
"""
    return {
        "codex_which": _obs("/usr/bin/codex\n", command=["which", "codex"]),
        "codex_version": _obs("codex-cli 0.139.0\n", command=["codex", "--version"]),
        "codex_help": _obs(codex_help, command=["codex", "--help"]),
        "codex_exec_help": _obs(codex_exec_help, command=["codex", "exec", "--help"]),
        "codex_login_help": _obs("Manage login\nCommands:\n  status Show login status\n", command=["codex", "login", "--help"]),
        "codex_login_status_help": _obs("Show login status\n", command=["codex", "login", "status", "--help"]),
        "codex_login_status": _obs(codex_status, command=["codex", "login", "status"]),
        "gemini_which": _obs("/usr/bin/gemini\n", command=["which", "gemini"]),
        "gemini_version": _obs("0.44.1\n", command=["gemini", "--version"]),
        "gemini_help": _obs(gemini_help, command=["gemini", "--help"]),
        "agy_which": _obs("/usr/bin/agy\n", command=["which", "agy"]),
        "agy_version": _obs("1.0.8\n", command=["agy", "--version"]),
        "agy_help": _obs(agy_help, command=["agy", "--help"]),
        "claude_which": _obs("/usr/bin/claude\n", command=["which", "claude"]),
        "claude_version": _obs("2.1.174 (Claude Code)\n", command=["claude", "--version"]),
        "claude_help": _obs(claude_help, command=["claude", "--help"]),
        "claude_auth_help": _obs("Commands:\n  status Show authentication status\n", command=["claude", "auth", "--help"]),
        "claude_auth_status_help": _obs("Show authentication status\n  --json\n", command=["claude", "auth", "status", "--help"]),
        "claude_auth_status": _obs(claude_status, command=["claude", "auth", "status", "--json"]),
        "ollama_which": _obs("/usr/bin/ollama\n", command=["which", "ollama"]),
        "ollama_list": _obs(ollama_list, command=["ollama", "list"]),
    }


def _record(payload: dict, provider: str) -> dict:
    matches = [row for row in payload["records"] if row["provider"] == provider]
    assert len(matches) == 1
    return matches[0]


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def test_subscription_output_is_classified_and_account_redacted():
    payload = auth_status.build_provider_access_auth_status(
        observations=_fake_observations(),
        generated_at=FIXED_NOW,
    )
    codex = _record(payload, "openai_codex_cli")
    blob = json.dumps(payload)

    assert codex["auth_status"] == "authenticated_subscription"
    assert codex["subscription_backing_proven"] is True
    assert codex["worker_run_manager_ready"] is True
    assert "winship@example.test" not in blob
    assert "<redacted-account>" in blob


def test_authenticated_unknown_billing_is_not_subscription_proven():
    payload = auth_status.build_provider_access_auth_status(
        observations=_fake_observations(codex_status="Logged in as winship@example.test\n"),
        generated_at=FIXED_NOW,
    )
    codex = _record(payload, "openai_codex_cli")

    assert codex["auth_status"] == "authenticated_unknown_billing"
    assert codex["subscription_backing_proven"] is False
    assert codex["worker_run_manager_ready"] is False


def test_api_key_status_is_classified_but_not_preferred():
    payload = auth_status.build_provider_access_auth_status(
        observations=_fake_observations(codex_status="Authenticated with API_KEY=sk-test-value\n"),
        generated_at=FIXED_NOW,
    )
    codex = _record(payload, "openai_codex_cli")
    blob = json.dumps(payload)

    assert codex["auth_status"] == "api_key_configured"
    assert codex["api_billing_required"] is True
    assert codex["subscription_backing_proven"] is False
    assert codex["worker_run_manager_ready"] is False
    assert "sk-test-value" not in blob


def test_not_logged_in_classifies_installed_not_authenticated():
    payload = auth_status.build_provider_access_auth_status(
        observations=_fake_observations(codex_status="Not logged in. Run codex login.\n"),
        generated_at=FIXED_NOW,
    )
    codex = _record(payload, "openai_codex_cli")

    assert codex["auth_status"] == "installed_not_authenticated"
    assert codex["subscription_backing_proven"] is False


def test_gemini_and_antigravity_remain_unknown_without_safe_status_command():
    payload = auth_status.build_provider_access_auth_status(
        observations=_fake_observations(),
        generated_at=FIXED_NOW,
    )
    gemini = _record(payload, "google_gemini_cli")
    agy = _record(payload, "google_antigravity_cli")

    assert gemini["auth_status"] == "unknown"
    assert gemini["auth_probe_supported"] is False
    assert agy["auth_status"] == "unknown"
    assert agy["manual_only"] is True


def test_catalog_merge_updates_auth_and_ready_status():
    auth_payload = auth_status.build_provider_access_auth_status(
        observations=_fake_observations(),
        generated_at=FIXED_NOW,
    )
    catalog_payload = access_catalog.build_provider_access_catalog(
        observations=_fake_observations(),
        generated_at=FIXED_NOW,
    )
    merged = auth_status.merge_auth_status_into_catalog(catalog_payload, auth_payload)
    codex = [row for row in merged["provider_access_modes"] if row["provider"] == "openai_codex_cli"][0]

    assert codex["auth_status"] == "authenticated_subscription"
    assert codex["access_mode"] == "cli_authenticated_subscription"
    assert codex["worker_run_manager_ready"] is True
    assert "openai_codex_cli" in merged["worker_run_manager_integration"]["ready_worker_providers"]


def test_no_generation_probe_and_no_unsafe_true_grants():
    payload = auth_status.build_provider_access_auth_status(
        observations=_fake_observations(),
        generated_at=FIXED_NOW,
    )

    assert payload["machine_proof"]["generation_probe_performed"] is False
    assert payload["machine_proof"]["model_invocation_performed"] is False
    assert payload["machine_proof"]["prompt_sent"] is False
    assert payload["machine_proof"]["proof_bundle_sent"] is False
    assert auth_status.unsafe_true_grants(payload) == []
    assert not [key for key, value in _walk_values(payload) if key in auth_status.UNSAFE_TRUE_KEYS and value is True]
