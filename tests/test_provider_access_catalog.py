import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import provider_access_catalog as catalog


FIXED_NOW = "2026-06-13T12:00:00+00:00"


def _obs(stdout: str = "", *, ok: bool = True, command: list[str] | None = None) -> dict:
    return {
        "command": command or ["tool", "--help"],
        "command_kind": "help_or_inventory",
        "returncode": 0 if ok else 1,
        "ok": ok,
        "timed_out": False,
        "error": "",
        "stdout_first_line": stdout.splitlines()[0] if stdout.splitlines() else "",
        "stderr_first_line": "",
        "stdout_line_count": len(stdout.splitlines()),
        "stderr_line_count": 0,
        "secret_value_patterns_redacted": 0,
        "raw_output_stored": False,
        "_stdout": stdout,
        "_stderr": "",
    }


def _fake_observations() -> dict[str, dict]:
    codex_help = """Codex CLI
Commands:
  exec            Run Codex non-interactively
Options:
  -m, --model <MODEL>
  -s, --sandbox <SANDBOX_MODE>
  -C, --cd <DIR>
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
  --model <model> Provide an alias for the latest model, e.g. fable, opus, sonnet
  -p, --print Print response and exit
  --output-format <format> choices: text, json, stream-json
  --json-schema <schema> JSON Schema for structured output validation
  --tools <tools...> Specify tools. Use "" to disable all tools.
  --bare skip hooks, plugin sync, keychain reads, and auto-discovery
"""
    ollama_list = """NAME                 ID              SIZE      MODIFIED
qwen3:8b-q4_K_M      500a1f067a9f    5.2 GB    7 weeks ago
mistral-small:latest 8039dd90c113    14 GB     7 weeks ago
"""
    return {
        "codex_which": _obs("/usr/bin/codex\n", command=["which", "codex"]),
        "codex_version": _obs("codex-cli 0.139.0\n", command=["codex", "--version"]),
        "codex_help": _obs(codex_help, command=["codex", "--help"]),
        "codex_exec_help": _obs(codex_exec_help, command=["codex", "exec", "--help"]),
        "codex_app_server_help": _obs("app-server help\n", command=["codex", "app-server", "--help"]),
        "codex_remote_control_help": _obs("remote-control help\n", command=["codex", "remote-control", "--help"]),
        "gemini_which": _obs("/usr/bin/gemini\n", command=["which", "gemini"]),
        "gemini_version": _obs("0.44.1\n", command=["gemini", "--version"]),
        "gemini_help": _obs(gemini_help, command=["gemini", "--help"]),
        "agy_which": _obs("/usr/bin/agy\n", command=["which", "agy"]),
        "agy_version": _obs("1.0.8\n", command=["agy", "--version"]),
        "agy_help": _obs(agy_help, command=["agy", "--help"]),
        "claude_which": _obs("/usr/bin/claude\n", command=["which", "claude"]),
        "claude_version": _obs("2.1.174 (Claude Code)\n", command=["claude", "--version"]),
        "claude_help": _obs(claude_help, command=["claude", "--help"]),
        "ollama_which": _obs("/usr/bin/ollama\n", command=["which", "ollama"]),
        "ollama_list": _obs(ollama_list, command=["ollama", "list"]),
    }


def _payload() -> dict:
    return catalog.build_provider_access_catalog(observations=_fake_observations(), generated_at=FIXED_NOW)


def _record(payload: dict, provider: str) -> dict:
    matches = [row for row in payload["provider_access_modes"] if row["provider"] == provider]
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


def test_parser_handles_fake_cli_help_outputs():
    codex = catalog.parse_cli_help(
        "codex",
        "Run Codex non-interactively. Read from stdin. --json --output-schema <FILE> -m, --model -C, --cd",
    )
    claude = catalog.parse_cli_help(
        "claude",
        'Use -p/--print for non-interactive output. --output-format json --json-schema --tools "" to disable all tools --bare --model',
    )

    assert codex["noninteractive_supported"] is True
    assert codex["accepts_stdin"] is True
    assert codex["supports_json_output"] is True
    assert codex["supports_working_directory"] is True
    assert claude["supports_no_tools_mode"] is True
    assert claude["supports_no_file_access_mode"] is True


def test_subscription_backed_access_is_preferred_over_api_when_available():
    payload = _payload()
    order = payload["router_policy_recommendation"]["preferred_order"]

    assert order.index("openai_codex_cli") < order.index("api_key_overage_routes")
    assert order.index("google_gemini_cli") < order.index("api_key_overage_routes")
    assert order.index("anthropic_claude_cli") < order.index("api_key_overage_routes")
    assert payload["router_policy_recommendation"]["api_key_routes_not_preferred_by_default"] is True


def test_api_key_route_marked_not_preferred_by_default():
    api = _record(_payload(), "api_key_overage_routes")

    assert api["access_mode"] == "api_key_available_but_not_preferred"
    assert api["api_billing_required"] is True
    assert api["api_billing_preferred"] is False
    assert api["recommended_use"] == "blocked"


def test_desktop_apps_are_manual_unless_supported_bridge_exists():
    payload = _payload()
    codex_desktop = _record(payload, "openai_codex_desktop_app")
    chatgpt = _record(payload, "chatgpt_desktop_app_web")

    assert codex_desktop["access_mode"] == "desktop_app_manual"
    assert codex_desktop["can_be_worker_run_manager_provider"] is False
    assert codex_desktop["can_be_manual_handoff_provider"] is True
    assert chatgpt["access_mode"] == "manual_handoff"
    assert chatgpt["desktop_app_control"] is False


def test_no_generation_probe_by_default():
    payload = _payload()

    assert payload["machine_proof"]["generation_probe_performed"] is False
    assert payload["machine_proof"]["model_invocation_performed"] is False
    assert payload["machine_proof"]["prompt_sent"] is False
    for command in catalog.SAFE_DISCOVERY_COMMANDS.values():
        assert command[-1] in {"codex", "gemini", "agy", "claude", "ollama", "--version", "--help", "list"}


def test_no_secret_values_are_captured_from_command_output():
    redacted = catalog._observation(
        command_id="fake_version",
        command=["fake", "--version"],
        returncode=0,
        stdout="version\nAPI_KEY=super-secret-value\n",
    )
    observations = _fake_observations()
    observations["codex_version"] = redacted
    payload = catalog.build_provider_access_catalog(observations=observations, generated_at=FIXED_NOW)
    blob = json.dumps(payload)

    assert "super-secret-value" not in blob
    row = [item for item in payload["command_observations"] if item.get("command_id") == "fake_version"]
    assert row[0]["secret_value_patterns_redacted"] == 1
    assert payload["machine_proof"]["credential_values_logged"] is False


def test_worker_run_manager_mapping_generated():
    payload = _payload()
    workers = payload["worker_run_manager_integration"]["worker_candidates"]
    providers = {row["provider"] for row in workers}

    assert "openai_codex_cli" in providers
    assert "google_gemini_cli" in providers
    assert "google_antigravity_cli" in providers
    assert "anthropic_claude_cli" in providers
    assert "local_ollama_runtime" in providers
    assert all(row["worker_run_manager_mapping"]["result_can_mutate_runtime_directly"] is False for row in workers)


def test_ollama_models_are_inventory_only():
    local = _record(_payload(), "local_ollama_runtime")

    assert local["access_mode"] == "local_runtime"
    assert local["api_billing_required"] is False
    assert local["local_models"]
    assert all(row["invocation_allowed"] is False for row in local["local_models"])
    assert all(row["proof_bundle_allowed"] is False for row in local["local_models"])


def test_no_unsafe_true_grants():
    payload = _payload()

    assert catalog.unsafe_true_grants(payload) == []
    assert not [key for key, value in _walk_values(payload) if key in catalog.UNSAFE_TRUE_KEYS and value is True]
    assert payload["authority_boundary"]["tool_authority_granted"] is False
    assert payload["authority_boundary"]["business_action_authority_granted"] is False
