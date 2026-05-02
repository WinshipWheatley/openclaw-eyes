import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_CONFIG = REPO_ROOT / ".mcp.json"
PROFILE_DOC = REPO_ROOT / "docs" / "operations" / "MCP_PROGRESSIVE_DISCOVERY_PROFILES.md"

REQUIRED_PROFILES = {
    "default-docs-read",
    "repo-source-read-unlocked",
    "runtime-artifact-read-unlocked",
    "shared-vault-operator-approved",
    "hermes-gateway-advisory",
    "trusted-local-dev",
}

ALLOWED_DEFAULT_FILESYSTEM_ROOTS = {
    "/home/openclaw/docs/operations",
    "/home/openclaw/docs/specs",
}

FORBIDDEN_DEFAULT_FILESYSTEM_TARGETS = {
    "repo root": "/home/openclaw",
    "repo source": "/home/openclaw/chief_llm.py",
    "repo tests": "/home/openclaw/tests",
    "shared vault": "/mnt/c/OpenClawShared/openclaw-vault",
    "log root": "/mnt/c/OpenClaw/logs",
    "legal private root": "/mnt/c/OpenClawLegalPrivate",
    "hermes runtime home": "/home/openclaw/sidecars/hermes_home",
    "hermes sessions": "/home/openclaw/sidecars/hermes_home/sessions",
    "hermes state database": "/home/openclaw/sidecars/hermes_home/state.db",
    "hermes state directory": "/home/openclaw/sidecars/hermes_home/state",
}

REQUIRED_CONTRACT_FIELDS = {
    "allowed roots/tools",
    "withheld surfaces",
    "unlock trigger",
    "approval/policy/verifier gate",
    "reveal/unlock artifact",
}

FORBIDDEN_TOOL_DISCLOSURE_TOKENS = {
    "apply_patch",
    "codex",
    "drive",
    "exec",
    "gemini",
    "gmail",
    "kimi",
    "messages_send",
    "openai",
    "openrouter",
    "patch",
    "plugin",
    "plugins",
    "process",
    "provider",
    "send_message",
    "shell",
    "skill_view",
    "skills_list",
    "sms",
    "smtp",
    "subprocess",
    "telegram",
    "terminal",
    "tool_discovery",
    "write",
    "write_file",
    "write-file",
    "mcp_tool",
}


def _load_mcp_config() -> dict:
    return json.loads(MCP_CONFIG.read_text(encoding="utf-8"))


def _all_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _all_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_strings(item)


def _configured_filesystem_roots() -> list[str]:
    config = _load_mcp_config()
    servers = config.get("mcpServers", {})
    roots: list[str] = []

    for server in servers.values():
        args = server.get("args", [])
        if not isinstance(args, list):
            continue
        for arg in args:
            if isinstance(arg, str) and (arg.startswith("/") or arg.startswith("~")):
                roots.append(arg)

    return roots


def _configured_server_names() -> set[str]:
    config = _load_mcp_config()
    servers = config.get("mcpServers", {})
    return set(servers)


def _flattened_config_text() -> str:
    return "\n".join(_all_strings(_load_mcp_config())).lower()


def _normalize(path: str) -> str:
    return path.rstrip("/") or "/"


def _root_exposes_target(root: str, target: str) -> bool:
    root = _normalize(root)
    target = _normalize(target)
    return target == root or target.startswith(f"{root}/")


def _any_configured_root_exposes(target: str) -> bool:
    return any(_root_exposes_target(root, target) for root in _configured_filesystem_roots())


def test_profile_doc_names_required_profiles_and_contract_fields():
    text = PROFILE_DOC.read_text(encoding="utf-8")
    lowered = text.lower()

    for profile in REQUIRED_PROFILES:
        assert f"`{profile}`" in text
    for field in REQUIRED_CONTRACT_FIELDS:
        assert field in lowered


def test_default_filesystem_roots_are_docs_only():
    assert set(_configured_filesystem_roots()) == ALLOWED_DEFAULT_FILESYSTEM_ROOTS


def test_default_profile_only_configures_filesystem_server():
    assert _configured_server_names() == {"filesystem"}


def test_default_profile_does_not_expose_forbidden_filesystem_targets():
    exposed = {
        label: target
        for label, target in FORBIDDEN_DEFAULT_FILESYSTEM_TARGETS.items()
        if _any_configured_root_exposes(target)
    }

    assert exposed == {}


def test_default_profile_does_not_include_shared_vault_root():
    assert not _any_configured_root_exposes("/mnt/c/OpenClawShared/openclaw-vault")


def test_default_profile_does_not_include_log_root():
    assert not _any_configured_root_exposes("/mnt/c/OpenClaw/logs")


def test_default_profile_does_not_include_legal_private_root():
    assert not _any_configured_root_exposes("/mnt/c/OpenClawLegalPrivate")


def test_default_profile_does_not_expose_hermes_session_or_state_homes():
    sensitive_targets = [
        "/home/openclaw/sidecars/hermes_home",
        "/home/openclaw/sidecars/hermes_home/sessions",
        "/home/openclaw/sidecars/hermes_home/state.db",
        "/home/openclaw/sidecars/hermes_home/state",
    ]

    exposed = [target for target in sensitive_targets if _any_configured_root_exposes(target)]

    assert exposed == []


def test_default_profile_does_not_disclose_side_effect_or_provider_tools():
    flattened_config = _flattened_config_text()

    disclosed = sorted(
        token for token in FORBIDDEN_TOOL_DISCLOSURE_TOKENS
        if token in flattened_config
    )

    assert disclosed == []
