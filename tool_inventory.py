"""Local Tool Inventory v0 for OpenClaw.

This module records observed, already-installed local tools into the existing
Business Ops ledger under a separate ``tool_inventory_*`` namespace. Probes are
metadata-only, allowlisted, bounded, and never install, upgrade, clone, start
servers, run models, run containers, contact hosts, or activate OpenClaw
runtime behavior.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import shutil
import sqlite3
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger


TOOL_INVENTORY_VERSION = "local_tool_inventory_v0"
DEFAULT_ROOT_ID = "pc_wsl_home_openclaw"
DEFAULT_HOST_KIND = "pc_wsl"
DEFAULT_ROOT = Path("/home/openclaw")
DEFAULT_TIMEOUT_SECONDS = 5
MAX_CAPTURE_CHARS = 4000

TOOL_CATEGORIES = {
    "sqlite",
    "python",
    "node",
    "git",
    "package_manager",
    "local_llm",
    "ai_dev",
    "container",
    "deployment",
    "security_scanning",
    "secrets_management",
    "file_sync",
    "remote_access",
    "observability",
    "client_app_backend",
    "project_template",
    "reproducible_environment",
    "editor_agent",
    "unknown",
}

HIGH_RISK_CATEGORIES = {
    "local_llm",
    "container",
    "deployment",
    "secrets_management",
    "remote_access",
}

FORBIDDEN_COMMAND_TOKENS = {
    "install",
    "upgrade",
    "remove",
    "uninstall",
    "clone",
    "pull",
    "push",
    "run",
    "serve",
    "server",
    "start",
    "up",
    "apply",
    "exec",
    "ssh",
    "scp",
    "rsync",
    "playbook",
}


@dataclass(frozen=True)
class ToolSpec:
    tool_id: str
    observed_name: str
    canonical_name: str
    category: str
    executable_names: tuple[str, ...]
    version_args: tuple[str, ...]
    package_manager_hint: str
    relevance_label: str
    architecture_fit: str
    risk_level: str
    notes: str
    requires_operator_review: bool = False
    version_timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    requires_success_for_detection: bool = False


@dataclass(frozen=True)
class ToolCommand:
    command_id: str
    args: tuple[str, ...]
    timeout_seconds: int
    allowed_executable_names: tuple[str, ...]


@dataclass(frozen=True)
class ProbeResult:
    attempted: bool
    succeeded: bool
    timed_out: bool
    returncode: int | None
    stdout: str
    stderr: str
    error: str | None = None


@dataclass(frozen=True)
class ToolInventoryResult:
    run_id: str
    db_path: str
    root_id: str
    observed_count: int
    detected_count: int
    not_detected_count: int
    counts: dict[str, dict[str, int]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256(
        "\0".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _trim(value: str | None) -> str:
    if not value:
        return ""
    return value[:MAX_CAPTURE_CHARS]


def _version_text(result: ProbeResult) -> str | None:
    combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
    for line in combined.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:500]
    return None


def _command_text(args: Iterable[str]) -> str:
    return shlex.join(tuple(args))


def _spec(
    tool_id: str,
    observed_name: str,
    category: str,
    executable_names: tuple[str, ...],
    version_args: tuple[str, ...] = ("__EXECUTABLE__", "--version"),
    *,
    canonical_name: str | None = None,
    package_manager_hint: str = "unknown",
    relevance_label: str = "future_review",
    architecture_fit: str = "future_integration_possible",
    risk_level: str = "low",
    notes: str = "Observed metadata only; not approved or integrated.",
    requires_operator_review: bool | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    requires_success_for_detection: bool = False,
) -> ToolSpec:
    if category not in TOOL_CATEGORIES:
        raise ValueError(f"unknown tool category: {category}")
    review = category in HIGH_RISK_CATEGORIES if requires_operator_review is None else requires_operator_review
    return ToolSpec(
        tool_id=tool_id,
        observed_name=observed_name,
        canonical_name=canonical_name or tool_id,
        category=category,
        executable_names=executable_names,
        version_args=version_args,
        package_manager_hint=package_manager_hint,
        relevance_label=relevance_label,
        architecture_fit=architecture_fit,
        risk_level=risk_level,
        notes=notes,
        requires_operator_review=review,
        version_timeout_seconds=timeout,
        requires_success_for_detection=requires_success_for_detection,
    )


DEFAULT_TOOL_SPECS: tuple[ToolSpec, ...] = (
    _spec("python3", "python3", "python", ("python3",), package_manager_hint="system_or_pyenv", relevance_label="core_local_first", architecture_fit="local_first_foundation"),
    _spec("pip", "pip", "package_manager", ("pip", "pip3"), package_manager_hint="python", relevance_label="core_local_first", architecture_fit="local_package_metadata"),
    _spec("pipx", "pipx", "package_manager", ("pipx",), package_manager_hint="python", relevance_label="core_local_first", architecture_fit="local_package_metadata"),
    _spec("uv", "uv", "package_manager", ("uv",), package_manager_hint="python", relevance_label="future_review", architecture_fit="reproducible_environment"),
    _spec("poetry", "poetry", "package_manager", ("poetry",), package_manager_hint="python", relevance_label="future_review", architecture_fit="reproducible_environment"),
    _spec("node", "node", "node", ("node",), version_args=("__EXECUTABLE__", "--version"), package_manager_hint="node", relevance_label="core_local_first", architecture_fit="client_app_backend"),
    _spec("npm", "npm", "package_manager", ("npm",), package_manager_hint="node", relevance_label="core_local_first", architecture_fit="client_app_backend"),
    _spec("pnpm", "pnpm", "package_manager", ("pnpm",), package_manager_hint="node", relevance_label="future_review", architecture_fit="client_app_backend"),
    _spec("yarn", "yarn", "package_manager", ("yarn",), package_manager_hint="node", relevance_label="future_review", architecture_fit="client_app_backend"),
    _spec("git", "git", "git", ("git",), package_manager_hint="system", relevance_label="core_local_first", architecture_fit="source_control"),
    _spec("gh", "gh", "git", ("gh",), package_manager_hint="system_or_gh", relevance_label="future_review", architecture_fit="github_metadata_only", risk_level="medium", requires_operator_review=True),
    _spec("make", "make", "reproducible_environment", ("make",), package_manager_hint="system", relevance_label="core_local_first", architecture_fit="local_build_utility"),
    _spec("jq", "jq", "unknown", ("jq",), package_manager_hint="system", relevance_label="core_local_first", architecture_fit="local_metadata_utility"),
    _spec("rg", "rg", "unknown", ("rg", "ripgrep"), package_manager_hint="system_or_cargo", relevance_label="core_local_first", architecture_fit="local_metadata_utility"),
    _spec("fd", "fd", "unknown", ("fd", "fdfind"), package_manager_hint="system_or_cargo", relevance_label="core_local_first", architecture_fit="local_metadata_utility"),
    _spec("sqlite3", "sqlite3", "sqlite", ("sqlite3",), package_manager_hint="system", relevance_label="core_local_first", architecture_fit="evidence_substrate"),
    _spec("datasette", "datasette", "sqlite", ("datasette",), package_manager_hint="python", relevance_label="future_review", architecture_fit="sqlite_inspection_surface", risk_level="medium"),
    _spec("sqlite_utils", "sqlite-utils", "sqlite", ("sqlite-utils",), package_manager_hint="python", relevance_label="future_review", architecture_fit="sqlite_maintenance_utility"),
    _spec("litestream", "litestream", "sqlite", ("litestream",), version_args=("__EXECUTABLE__", "version"), package_manager_hint="system", relevance_label="future_review", architecture_fit="sqlite_replication_candidate", risk_level="medium", requires_operator_review=True),
    _spec("ollama", "ollama", "local_llm", ("ollama",), package_manager_hint="system_or_vendor", relevance_label="future_review", architecture_fit="requires_sandbox_before_agent_use", risk_level="high", notes="Detection only. No model pull, model run, daemon start, or agent authorization."),
    _spec("llama_cli", "llama-cli", "local_llm", ("llama-cli",), package_manager_hint="system_or_source_build", relevance_label="future_review", architecture_fit="requires_sandbox_before_agent_use", risk_level="high", notes="Detection only. No model execution or agent authorization."),
    _spec("llama_cpp", "llama.cpp", "local_llm", ("llama.cpp",), package_manager_hint="system_or_source_build", relevance_label="future_review", architecture_fit="requires_sandbox_before_agent_use", risk_level="high", notes="Detection only. No model execution or agent authorization."),
    _spec("llm", "llm", "local_llm", ("llm",), package_manager_hint="python", relevance_label="future_review", architecture_fit="requires_sandbox_before_agent_use", risk_level="high", notes="Detection only. No model execution or external provider authorization."),
    _spec("docker", "docker", "container", ("docker",), package_manager_hint="system_or_vendor", relevance_label="future_review", architecture_fit="requires_operator_sandbox_policy", risk_level="high", notes="Detection only. No containers are run."),
    _spec("docker_compose", "docker compose", "container", ("docker",), version_args=("__EXECUTABLE__", "compose", "version"), package_manager_hint="docker_plugin", relevance_label="future_review", architecture_fit="requires_operator_sandbox_policy", risk_level="high", notes="Detection only. No compose project is started.", requires_success_for_detection=True),
    _spec("podman", "podman", "container", ("podman",), package_manager_hint="system", relevance_label="future_review", architecture_fit="requires_operator_sandbox_policy", risk_level="high", notes="Detection only. No containers are run."),
    _spec("kubectl", "kubectl", "deployment", ("kubectl",), version_args=("__EXECUTABLE__", "version", "--client"), package_manager_hint="system_or_kubernetes", relevance_label="future_review", architecture_fit="remote_cluster_tool_requires_review", risk_level="high", notes="Client version only. No cluster operation is authorized."),
    _spec("helm", "helm", "deployment", ("helm",), version_args=("__EXECUTABLE__", "version", "--short"), package_manager_hint="system_or_kubernetes", relevance_label="future_review", architecture_fit="remote_cluster_tool_requires_review", risk_level="high", notes="Version only. No cluster operation is authorized."),
    _spec("caddy", "caddy", "deployment", ("caddy",), version_args=("__EXECUTABLE__", "version"), package_manager_hint="system", relevance_label="future_review", architecture_fit="server_tool_requires_review", risk_level="high", notes="Version only. No server is started."),
    _spec("coolify", "coolify", "deployment", ("coolify",), package_manager_hint="unknown", relevance_label="future_review", architecture_fit="deployment_tool_requires_review", risk_level="high"),
    _spec("dokku", "dokku", "deployment", ("dokku",), version_args=("__EXECUTABLE__", "version"), package_manager_hint="system", relevance_label="future_review", architecture_fit="deployment_tool_requires_review", risk_level="high"),
    _spec("ansible", "ansible", "deployment", ("ansible",), package_manager_hint="python_or_system", relevance_label="future_review", architecture_fit="remote_management_requires_review", risk_level="high", notes="Version only. No inventory, host contact, or playbook execution is authorized."),
    _spec("trivy", "trivy", "security_scanning", ("trivy",), package_manager_hint="system", relevance_label="future_review", architecture_fit="security_scan_tool_requires_scope", risk_level="medium", requires_operator_review=True),
    _spec("syft", "syft", "security_scanning", ("syft",), version_args=("__EXECUTABLE__", "version"), package_manager_hint="system", relevance_label="future_review", architecture_fit="security_scan_tool_requires_scope", risk_level="medium", requires_operator_review=True),
    _spec("grype", "grype", "security_scanning", ("grype",), version_args=("__EXECUTABLE__", "version"), package_manager_hint="system", relevance_label="future_review", architecture_fit="security_scan_tool_requires_scope", risk_level="medium", requires_operator_review=True),
    _spec("sops", "sops", "secrets_management", ("sops",), package_manager_hint="system", relevance_label="future_review", architecture_fit="secret_tool_requires_policy", risk_level="high", notes="Version only. No secret files are read or written."),
    _spec("age", "age", "secrets_management", ("age",), package_manager_hint="system", relevance_label="future_review", architecture_fit="secret_tool_requires_policy", risk_level="high", notes="Version only. No secret files are read or written."),
    _spec("openbao", "openbao", "secrets_management", ("openbao",), version_args=("__EXECUTABLE__", "version"), package_manager_hint="system_or_vendor", relevance_label="future_review", architecture_fit="secret_tool_requires_policy", risk_level="high", notes="Version only. No secret store is contacted."),
    _spec("vault", "vault", "secrets_management", ("vault",), version_args=("__EXECUTABLE__", "version"), package_manager_hint="system_or_vendor", relevance_label="future_review", architecture_fit="secret_tool_requires_policy", risk_level="high", notes="Version only. No secret store is contacted."),
    _spec("syncthing", "syncthing", "file_sync", ("syncthing",), package_manager_hint="system", relevance_label="future_review", architecture_fit="sync_tool_requires_review", risk_level="medium", requires_operator_review=True, notes="Version only. No sync daemon is started."),
    _spec("tailscale", "tailscale", "remote_access", ("tailscale",), version_args=("__EXECUTABLE__", "version"), package_manager_hint="system_or_vendor", relevance_label="future_review", architecture_fit="remote_access_requires_review", risk_level="high", notes="Version only. No remote access is initiated."),
    _spec("wireguard", "wireguard", "remote_access", ("wireguard",), package_manager_hint="system", relevance_label="future_review", architecture_fit="remote_access_requires_review", risk_level="high", notes="Version only. No tunnel is initiated."),
    _spec("wg", "wg", "remote_access", ("wg",), package_manager_hint="system", relevance_label="future_review", architecture_fit="remote_access_requires_review", risk_level="high", notes="Version only. No tunnel is initiated."),
    _spec("headscale", "headscale", "remote_access", ("headscale",), version_args=("__EXECUTABLE__", "version"), package_manager_hint="system_or_vendor", relevance_label="future_review", architecture_fit="remote_access_requires_review", risk_level="high", notes="Version only. No remote access is initiated."),
    _spec("meshcentral", "meshcentral", "remote_access", ("meshcentral",), package_manager_hint="node_or_system", relevance_label="future_review", architecture_fit="remote_access_requires_review", risk_level="high", notes="Version only. No remote access is initiated."),
    _spec("pocketbase", "pocketbase", "client_app_backend", ("pocketbase",), package_manager_hint="system_or_binary", relevance_label="future_review", architecture_fit="client_capsule_backend_candidate", risk_level="medium", requires_operator_review=True),
    _spec("directus", "directus", "client_app_backend", ("directus",), package_manager_hint="node", relevance_label="future_review", architecture_fit="client_capsule_backend_candidate", risk_level="medium", requires_operator_review=True),
    _spec("appwrite", "appwrite", "client_app_backend", ("appwrite",), package_manager_hint="system_or_node", relevance_label="future_review", architecture_fit="client_capsule_backend_candidate", risk_level="medium", requires_operator_review=True),
    _spec("appsmith", "appsmith", "client_app_backend", ("appsmith",), package_manager_hint="system_or_node", relevance_label="future_review", architecture_fit="client_capsule_backend_candidate", risk_level="medium", requires_operator_review=True),
    _spec("copier", "copier", "project_template", ("copier",), package_manager_hint="python", relevance_label="future_review", architecture_fit="project_template_candidate"),
    _spec("cookiecutter", "cookiecutter", "project_template", ("cookiecutter",), package_manager_hint="python", relevance_label="future_review", architecture_fit="project_template_candidate"),
    _spec("devbox", "devbox", "reproducible_environment", ("devbox",), version_args=("__EXECUTABLE__", "version"), package_manager_hint="nix", relevance_label="future_review", architecture_fit="reproducible_environment_candidate", risk_level="medium", requires_operator_review=True),
    _spec("nix", "nix", "reproducible_environment", ("nix",), version_args=("__EXECUTABLE__", "--version"), package_manager_hint="nix", relevance_label="future_review", architecture_fit="reproducible_environment_candidate", risk_level="medium", requires_operator_review=True),
    _spec("prometheus", "prometheus", "observability", ("prometheus",), package_manager_hint="system", relevance_label="future_review", architecture_fit="observability_candidate", risk_level="medium", requires_operator_review=True, notes="Version only. No server is started."),
    _spec("grafana", "grafana", "observability", ("grafana",), package_manager_hint="system", relevance_label="future_review", architecture_fit="observability_candidate", risk_level="medium", requires_operator_review=True, notes="Version only. No server is started."),
    _spec("loki", "loki", "observability", ("loki",), package_manager_hint="system", relevance_label="future_review", architecture_fit="observability_candidate", risk_level="medium", requires_operator_review=True, notes="Version only. No service is started."),
    _spec("netdata", "netdata", "observability", ("netdata",), version_args=("__EXECUTABLE__", "-v"), package_manager_hint="system", relevance_label="future_review", architecture_fit="observability_candidate", risk_level="medium", requires_operator_review=True, notes="Version only. No daemon is started."),
    _spec("uptime_kuma", "uptime-kuma", "observability", ("uptime-kuma",), package_manager_hint="node_or_system", relevance_label="future_review", architecture_fit="observability_candidate", risk_level="medium", requires_operator_review=True, notes="Version only. No service is started."),
    _spec("codex", "codex", "editor_agent", ("codex",), package_manager_hint="node_or_binary", relevance_label="future_review", architecture_fit="editor_agent_tool_observed", risk_level="medium", requires_operator_review=True),
    _spec("claude", "claude", "editor_agent", ("claude",), package_manager_hint="node_or_binary", relevance_label="future_review", architecture_fit="editor_agent_tool_observed", risk_level="medium", requires_operator_review=True),
    _spec("aider", "aider", "editor_agent", ("aider",), package_manager_hint="python", relevance_label="future_review", architecture_fit="editor_agent_tool_observed", risk_level="medium", requires_operator_review=True),
    _spec("cursor", "cursor", "editor_agent", ("cursor",), package_manager_hint="system_or_app", relevance_label="future_review", architecture_fit="editor_agent_tool_observed", risk_level="medium", requires_operator_review=True),
    _spec("code", "code", "editor_agent", ("code",), package_manager_hint="system_or_app", relevance_label="future_review", architecture_fit="editor_agent_tool_observed", risk_level="medium", requires_operator_review=True),
)


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS tool_inventory_runs (
  run_id TEXT PRIMARY KEY,
  inventory_version TEXT NOT NULL,
  root_id TEXT NOT NULL,
  host_kind TEXT NOT NULL,
  absolute_root TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  observed_count INTEGER NOT NULL DEFAULT 0,
  detected_count INTEGER NOT NULL DEFAULT 0,
  not_detected_count INTEGER NOT NULL DEFAULT 0,
  probe_count INTEGER NOT NULL DEFAULT 0,
  install_action_taken INTEGER NOT NULL DEFAULT 0,
  integration_action_taken INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  network_access_attempted INTEGER NOT NULL DEFAULT 0,
  daemon_started INTEGER NOT NULL DEFAULT 0,
  model_execution_attempted INTEGER NOT NULL DEFAULT 0,
  container_execution_attempted INTEGER NOT NULL DEFAULT 0,
  remote_access_attempted INTEGER NOT NULL DEFAULT 0,
  source_basis_json TEXT NOT NULL,
  notes TEXT
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS tool_observations (
  observation_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  tool_id TEXT NOT NULL,
  observed_name TEXT NOT NULL,
  canonical_name TEXT NOT NULL,
  category TEXT NOT NULL,
  detected INTEGER NOT NULL,
  executable_path TEXT,
  version_text TEXT,
  version_command_used TEXT,
  version_probe_status TEXT NOT NULL,
  version_exit_code INTEGER,
  version_timed_out INTEGER NOT NULL DEFAULT 0,
  package_manager_hint TEXT NOT NULL,
  host_root_id TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  relevance_label TEXT NOT NULL,
  architecture_fit TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  integration_status TEXT NOT NULL,
  install_status TEXT NOT NULL,
  action_status TEXT NOT NULL,
  notes TEXT,
  requires_operator_review INTEGER NOT NULL,
  raw_sensitive_data_stored INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (run_id) REFERENCES tool_inventory_runs(run_id) ON DELETE CASCADE,
  UNIQUE(run_id, tool_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS tool_observation_labels (
  label_id TEXT PRIMARY KEY,
  observation_id TEXT NOT NULL,
  label_name TEXT NOT NULL,
  label_value TEXT NOT NULL,
  label_basis TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (observation_id) REFERENCES tool_observations(observation_id) ON DELETE CASCADE,
  UNIQUE(observation_id, label_name, label_value, label_basis)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS tool_install_locations (
  location_id TEXT PRIMARY KEY,
  observation_id TEXT NOT NULL,
  tool_id TEXT NOT NULL,
  executable_path TEXT NOT NULL,
  path_resolution_method TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  FOREIGN KEY (observation_id) REFERENCES tool_observations(observation_id) ON DELETE CASCADE,
  UNIQUE(observation_id, executable_path)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS tool_version_observations (
  version_observation_id TEXT PRIMARY KEY,
  observation_id TEXT NOT NULL,
  tool_id TEXT NOT NULL,
  command_used TEXT NOT NULL,
  succeeded INTEGER NOT NULL,
  timed_out INTEGER NOT NULL,
  returncode INTEGER,
  stdout_excerpt TEXT,
  stderr_excerpt TEXT,
  version_text TEXT,
  observed_at TEXT NOT NULL,
  FOREIGN KEY (observation_id) REFERENCES tool_observations(observation_id) ON DELETE CASCADE,
  UNIQUE(observation_id, command_used)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS tool_runtime_boundaries (
  boundary_id TEXT PRIMARY KEY,
  observation_id TEXT NOT NULL,
  tool_id TEXT NOT NULL,
  boundary_type TEXT NOT NULL,
  boundary_text TEXT NOT NULL,
  enforced_by_inventory INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  FOREIGN KEY (observation_id) REFERENCES tool_observations(observation_id) ON DELETE CASCADE,
  UNIQUE(observation_id, boundary_type)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS tool_future_candidates (
  candidate_id TEXT PRIMARY KEY,
  observation_id TEXT NOT NULL,
  tool_id TEXT NOT NULL,
  candidate_scope TEXT NOT NULL,
  candidate_status TEXT NOT NULL,
  candidate_basis TEXT NOT NULL,
  requires_operator_review INTEGER NOT NULL,
  action_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (observation_id) REFERENCES tool_observations(observation_id) ON DELETE CASCADE,
  UNIQUE(observation_id, candidate_scope)
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_tool_observations_run ON tool_observations(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_tool_observations_detected ON tool_observations(run_id, detected)",
        "CREATE INDEX IF NOT EXISTS idx_tool_observations_category ON tool_observations(run_id, category)",
        "CREATE INDEX IF NOT EXISTS idx_tool_observations_risk ON tool_observations(run_id, risk_level)",
        "CREATE INDEX IF NOT EXISTS idx_tool_future_candidates_run ON tool_future_candidates(candidate_status)",
    )


def init_tool_inventory_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    db_parent = Path(path).parent
    if db_parent and not db_parent.exists():
        db_parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def tool_inventory_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_tool_inventory_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'tool_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _resolve_executable(
    spec: ToolSpec,
    executable_resolver: Callable[[str], str | None],
) -> tuple[str | None, str | None]:
    for name in spec.executable_names:
        resolved = executable_resolver(name)
        if resolved:
            return str(resolved), name
    return None, None


def _build_tool_command(spec: ToolSpec, executable_path: str) -> ToolCommand:
    args = tuple(executable_path if arg == "__EXECUTABLE__" else arg for arg in spec.version_args)
    return ToolCommand(
        command_id=f"{spec.tool_id}:version",
        args=args,
        timeout_seconds=spec.version_timeout_seconds,
        allowed_executable_names=spec.executable_names,
    )


def _validate_tool_command(command: ToolCommand) -> None:
    if not command.args:
        raise ValueError("empty command is not allowed")
    executable = Path(command.args[0]).name
    if executable not in command.allowed_executable_names:
        raise ValueError(f"command executable is not allowlisted: {executable}")
    for arg in command.args:
        lowered = arg.strip().lower()
        if lowered in FORBIDDEN_COMMAND_TOKENS:
            raise ValueError(f"forbidden command token in probe: {arg}")


def run_allowed_command(command: ToolCommand) -> ProbeResult:
    """Run one allowlisted, bounded metadata probe.

    This function intentionally accepts a structured ``ToolCommand`` rather
    than arbitrary user command text.
    """
    _validate_tool_command(command)
    try:
        completed = subprocess.run(
            list(command.args),
            capture_output=True,
            text=True,
            timeout=command.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return ProbeResult(
            attempted=True,
            succeeded=False,
            timed_out=True,
            returncode=None,
            stdout=_trim(stdout),
            stderr=_trim(stderr),
            error="timeout",
        )
    except OSError as exc:
        return ProbeResult(
            attempted=True,
            succeeded=False,
            timed_out=False,
            returncode=None,
            stdout="",
            stderr="",
            error=f"{type(exc).__name__}: {exc}",
        )

    return ProbeResult(
        attempted=True,
        succeeded=completed.returncode == 0,
        timed_out=False,
        returncode=completed.returncode,
        stdout=_trim(completed.stdout),
        stderr=_trim(completed.stderr),
    )


def _boundary_text(spec: ToolSpec) -> str:
    if spec.category == "local_llm":
        return "Observed local LLM tooling does not authorize model pulls, model execution, daemon starts, or agent use."
    if spec.category == "container":
        return "Observed container tooling does not authorize container builds, pulls, runs, compose starts, or daemon changes."
    if spec.category == "deployment":
        return "Observed deployment tooling does not authorize remote, cluster, host, server, or playbook actions."
    if spec.category == "remote_access":
        return "Observed remote-access tooling does not authorize tunnels, remote sessions, host contact, or credential use."
    if spec.category == "secrets_management":
        return "Observed secrets tooling does not authorize reading, decrypting, writing, or syncing secret material."
    if spec.category == "observability":
        return "Observed observability tooling does not authorize starting services, scraping targets, or opening dashboards."
    if spec.category == "security_scanning":
        return "Observed security tooling does not authorize filesystem, image, dependency, or network scans without a bounded future lane."
    return "Observed installation metadata does not imply approval, integration, runtime authority, or future use."


def _label_pairs(spec: ToolSpec, detected: bool) -> tuple[tuple[str, str, str], ...]:
    return (
        ("category", spec.category, "tool_inventory_spec"),
        ("risk_level", spec.risk_level, "tool_inventory_spec"),
        ("relevance_label", spec.relevance_label, "tool_inventory_spec"),
        ("architecture_fit", spec.architecture_fit, "tool_inventory_spec"),
        ("install_status", "observed_installed" if detected else "not_detected", "path_probe"),
        ("integration_status", "not_integrated", "inventory_doctrine"),
        ("action_status", "no_action_taken", "inventory_doctrine"),
    )


def _latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id
FROM tool_inventory_runs
ORDER BY completed_at DESC, started_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row[0] if row else None


def _delete_run(conn: sqlite3.Connection, run_id: str) -> None:
    conn.execute(
        """
DELETE FROM tool_future_candidates
WHERE observation_id IN (SELECT observation_id FROM tool_observations WHERE run_id = ?)
""".strip(),
        (run_id,),
    )
    conn.execute(
        """
DELETE FROM tool_runtime_boundaries
WHERE observation_id IN (SELECT observation_id FROM tool_observations WHERE run_id = ?)
""".strip(),
        (run_id,),
    )
    conn.execute(
        """
DELETE FROM tool_version_observations
WHERE observation_id IN (SELECT observation_id FROM tool_observations WHERE run_id = ?)
""".strip(),
        (run_id,),
    )
    conn.execute(
        """
DELETE FROM tool_install_locations
WHERE observation_id IN (SELECT observation_id FROM tool_observations WHERE run_id = ?)
""".strip(),
        (run_id,),
    )
    conn.execute(
        """
DELETE FROM tool_observation_labels
WHERE observation_id IN (SELECT observation_id FROM tool_observations WHERE run_id = ?)
""".strip(),
        (run_id,),
    )
    conn.execute("DELETE FROM tool_observations WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM tool_inventory_runs WHERE run_id = ?", (run_id,))


def run_tool_inventory(
    db_path: str | Path | None = None,
    *,
    root: str | Path = DEFAULT_ROOT,
    root_id: str = DEFAULT_ROOT_ID,
    host_kind: str = DEFAULT_HOST_KIND,
    run_id: str | None = None,
    tool_specs: Iterable[ToolSpec] = DEFAULT_TOOL_SPECS,
    executable_resolver: Callable[[str], str | None] = shutil.which,
    command_runner: Callable[[ToolCommand], ProbeResult] = run_allowed_command,
) -> ToolInventoryResult:
    path = init_tool_inventory_schema(db_path)
    specs = tuple(tool_specs)
    started_at = utc_now()
    resolved_run_id = run_id or _row_id("toolrun", started_at, root_id, len(specs))

    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        _delete_run(conn, resolved_run_id)
        conn.execute(
            """
INSERT INTO tool_inventory_runs (
  run_id, inventory_version, root_id, host_kind, absolute_root, started_at,
  source_basis_json, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
            (
                resolved_run_id,
                TOOL_INVENTORY_VERSION,
                root_id,
                host_kind,
                str(root),
                started_at,
                stable_json(
                    {
                        "probe_policy": "allowlisted path and version metadata only",
                        "tool_count": len(specs),
                        "network_calls": False,
                        "install_actions": False,
                        "runtime_activation": False,
                    }
                ),
                "Installed does not mean approved; detected does not mean integrated; available does not mean authorized.",
            ),
        )

        observed_rows: list[dict[str, Any]] = []
        probe_count = 0
        for spec in specs:
            executable_path, resolved_name = _resolve_executable(spec, executable_resolver)
            probe = ProbeResult(False, False, False, None, "", "", None)
            version_command_used = None
            if executable_path:
                command = _build_tool_command(spec, executable_path)
                _validate_tool_command(command)
                version_command_used = _command_text(command.args)
                probe_count += 1
                probe = command_runner(command)

            detected = bool(executable_path)
            if spec.requires_success_for_detection:
                detected = bool(executable_path and probe.succeeded)
            install_status = "observed_installed" if detected else "not_detected"
            version_probe_status = "not_attempted"
            if probe.attempted:
                if probe.timed_out:
                    version_probe_status = "timed_out"
                elif probe.succeeded:
                    version_probe_status = "succeeded"
                else:
                    version_probe_status = "failed"

            observation_id = _row_id("toolobs", resolved_run_id, spec.tool_id)
            observed_at = utc_now()
            version_text = _version_text(probe)
            review_required = 1 if (spec.requires_operator_review or spec.risk_level == "high") else 0
            conn.execute(
                """
INSERT INTO tool_observations (
  observation_id, run_id, tool_id, observed_name, canonical_name, category,
  detected, executable_path, version_text, version_command_used,
  version_probe_status, version_exit_code, version_timed_out,
  package_manager_hint, host_root_id, observed_at, relevance_label,
  architecture_fit, risk_level, integration_status, install_status,
  action_status, notes, requires_operator_review
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
                (
                    observation_id,
                    resolved_run_id,
                    spec.tool_id,
                    spec.observed_name,
                    spec.canonical_name,
                    spec.category,
                    1 if detected else 0,
                    executable_path if detected else None,
                    version_text,
                    version_command_used,
                    version_probe_status,
                    probe.returncode,
                    1 if probe.timed_out else 0,
                    spec.package_manager_hint,
                    root_id,
                    observed_at,
                    spec.relevance_label,
                    spec.architecture_fit,
                    spec.risk_level,
                    "not_integrated",
                    install_status,
                    "no_action_taken",
                    spec.notes,
                    review_required,
                ),
            )

            for label_name, label_value, label_basis in _label_pairs(spec, detected):
                conn.execute(
                    """
INSERT INTO tool_observation_labels (
  label_id, observation_id, label_name, label_value, label_basis, created_at
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(observation_id, label_name, label_value, label_basis) DO UPDATE SET
  created_at = excluded.created_at
""".strip(),
                    (
                        _row_id("toollabel", observation_id, label_name, label_value, label_basis),
                        observation_id,
                        label_name,
                        label_value,
                        label_basis,
                        observed_at,
                    ),
                )

            if executable_path and detected:
                conn.execute(
                    """
INSERT INTO tool_install_locations (
  location_id, observation_id, tool_id, executable_path, path_resolution_method, observed_at
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(observation_id, executable_path) DO UPDATE SET
  observed_at = excluded.observed_at
""".strip(),
                    (
                        _row_id("toolloc", observation_id, executable_path),
                        observation_id,
                        spec.tool_id,
                        executable_path,
                        f"shutil.which:{resolved_name}",
                        observed_at,
                    ),
                )

            if probe.attempted and version_command_used:
                conn.execute(
                    """
INSERT INTO tool_version_observations (
  version_observation_id, observation_id, tool_id, command_used, succeeded,
  timed_out, returncode, stdout_excerpt, stderr_excerpt, version_text, observed_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(observation_id, command_used) DO UPDATE SET
  succeeded = excluded.succeeded,
  timed_out = excluded.timed_out,
  returncode = excluded.returncode,
  stdout_excerpt = excluded.stdout_excerpt,
  stderr_excerpt = excluded.stderr_excerpt,
  version_text = excluded.version_text,
  observed_at = excluded.observed_at
""".strip(),
                    (
                        _row_id("toolver", observation_id, version_command_used),
                        observation_id,
                        spec.tool_id,
                        version_command_used,
                        1 if probe.succeeded else 0,
                        1 if probe.timed_out else 0,
                        probe.returncode,
                        probe.stdout,
                        probe.stderr,
                        version_text,
                        observed_at,
                    ),
                )

            conn.execute(
                """
INSERT INTO tool_runtime_boundaries (
  boundary_id, observation_id, tool_id, boundary_type, boundary_text,
  enforced_by_inventory, created_at
) VALUES (?, ?, ?, ?, ?, 1, ?)
ON CONFLICT(observation_id, boundary_type) DO UPDATE SET
  boundary_text = excluded.boundary_text,
  created_at = excluded.created_at
""".strip(),
                (
                    _row_id("toolboundary", observation_id, "authority"),
                    observation_id,
                    spec.tool_id,
                    "authority",
                    _boundary_text(spec),
                    observed_at,
                ),
            )

            if detected and spec.relevance_label != "safe_to_ignore":
                conn.execute(
                    """
INSERT INTO tool_future_candidates (
  candidate_id, observation_id, tool_id, candidate_scope, candidate_status,
  candidate_basis, requires_operator_review, action_status, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(observation_id, candidate_scope) DO UPDATE SET
  candidate_status = excluded.candidate_status,
  candidate_basis = excluded.candidate_basis,
  requires_operator_review = excluded.requires_operator_review,
  action_status = excluded.action_status,
  created_at = excluded.created_at
""".strip(),
                    (
                        _row_id("toolcandidate", observation_id, spec.architecture_fit),
                        observation_id,
                        spec.tool_id,
                        spec.architecture_fit,
                        "observed_only_not_approved",
                        "Installed metadata suggests a future review surface; no integration action taken.",
                        review_required,
                        "no_action_taken",
                        observed_at,
                    ),
                )

            observed_rows.append(
                {
                    "category": spec.category,
                    "detected": detected,
                    "install_status": install_status,
                    "risk_level": spec.risk_level,
                    "requires_operator_review": bool(review_required),
                }
            )

        completed_at = utc_now()
        detected_count = sum(1 for row in observed_rows if row["detected"])
        not_detected_count = len(observed_rows) - detected_count
        conn.execute(
            """
UPDATE tool_inventory_runs
SET completed_at = ?,
    observed_count = ?,
    detected_count = ?,
    not_detected_count = ?,
    probe_count = ?
WHERE run_id = ?
""".strip(),
            (
                completed_at,
                len(observed_rows),
                detected_count,
                not_detected_count,
                probe_count,
                resolved_run_id,
            ),
        )
        conn.commit()
        counts = {
            "category": dict(sorted(Counter(row["category"] for row in observed_rows).items())),
            "detected_by_category": dict(
                sorted(Counter(row["category"] for row in observed_rows if row["detected"]).items())
            ),
            "install_status": dict(sorted(Counter(row["install_status"] for row in observed_rows).items())),
            "risk_level": dict(sorted(Counter(row["risk_level"] for row in observed_rows).items())),
        }
        return ToolInventoryResult(
            run_id=resolved_run_id,
            db_path=path,
            root_id=root_id,
            observed_count=len(observed_rows),
            detected_count=detected_count,
            not_detected_count=not_detected_count,
            counts=counts,
        )
    finally:
        conn.close()


def build_tool_inventory_report(
    db_path: str | Path | None = None,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    path = init_tool_inventory_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_run_id = run_id or _latest_run_id(conn)
        if not resolved_run_id:
            return {"status": "no_runs", "section": "summary"}
        run = conn.execute(
            "SELECT * FROM tool_inventory_runs WHERE run_id = ?", (resolved_run_id,)
        ).fetchone()
        count_rows = {
            "category": conn.execute(
                """
SELECT category, COUNT(*) AS count
FROM tool_observations
WHERE run_id = ?
GROUP BY category
ORDER BY category
""".strip(),
                (resolved_run_id,),
            ).fetchall(),
            "detected_by_category": conn.execute(
                """
SELECT category, COUNT(*) AS count
FROM tool_observations
WHERE run_id = ? AND detected = 1
GROUP BY category
ORDER BY category
""".strip(),
                (resolved_run_id,),
            ).fetchall(),
            "install_status": conn.execute(
                """
SELECT install_status, COUNT(*) AS count
FROM tool_observations
WHERE run_id = ?
GROUP BY install_status
ORDER BY install_status
""".strip(),
                (resolved_run_id,),
            ).fetchall(),
            "risk_level": conn.execute(
                """
SELECT risk_level, COUNT(*) AS count
FROM tool_observations
WHERE run_id = ?
GROUP BY risk_level
ORDER BY risk_level
""".strip(),
                (resolved_run_id,),
            ).fetchall(),
        }
        samples = conn.execute(
            """
SELECT tool_id, observed_name, category, executable_path, version_text, risk_level,
       requires_operator_review
FROM tool_observations
WHERE run_id = ? AND detected = 1
ORDER BY category, tool_id
LIMIT 30
""".strip(),
            (resolved_run_id,),
        ).fetchall()
        return {
            "status": "ok",
            "section": "summary",
            "run_id": resolved_run_id,
            "run": dict(run),
            "counts": {
                key: {row[0]: row[1] for row in rows}
                for key, rows in count_rows.items()
            },
            "detected_samples": [dict(row) for row in samples],
        }
    finally:
        conn.close()


def query_tool_inventory_report_section(
    db_path: str | Path | None = None,
    *,
    run_id: str | None = None,
    section: str = "summary",
    category: str | None = None,
) -> dict[str, Any]:
    if section == "summary":
        return build_tool_inventory_report(db_path=db_path, run_id=run_id)
    path = init_tool_inventory_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_run_id = run_id or _latest_run_id(conn)
        if not resolved_run_id:
            return {"status": "no_runs", "section": section, "items": []}

        params: list[Any] = [resolved_run_id]
        where = "run_id = ?"
        if section == "detected":
            where += " AND detected = 1"
        elif section == "not-detected":
            where += " AND detected = 0"
        elif section == "category":
            where += " AND category = ?"
            params.append(category or "")
        elif section == "high-risk":
            where += " AND detected = 1 AND risk_level IN ('high','critical')"
        elif section == "future-candidates":
            rows = conn.execute(
                """
SELECT o.tool_id, o.observed_name, o.category, o.executable_path, o.version_text,
       o.risk_level, o.requires_operator_review, c.candidate_scope,
       c.candidate_status, c.candidate_basis, c.action_status
FROM tool_future_candidates c
JOIN tool_observations o ON o.observation_id = c.observation_id
WHERE o.run_id = ?
ORDER BY o.category, o.tool_id
""".strip(),
                (resolved_run_id,),
            ).fetchall()
            return {
                "status": "ok",
                "section": section,
                "run_id": resolved_run_id,
                "items": [dict(row) for row in rows],
            }
        else:
            raise ValueError(f"unknown report section: {section}")

        rows = conn.execute(
            f"""
SELECT tool_id, observed_name, canonical_name, category, detected,
       executable_path, version_text, version_command_used, version_probe_status,
       package_manager_hint, relevance_label, architecture_fit, risk_level,
       integration_status, install_status, action_status, notes,
       requires_operator_review
FROM tool_observations
WHERE {where}
ORDER BY category, tool_id
""".strip(),
            params,
        ).fetchall()
        return {
            "status": "ok",
            "section": section,
            "run_id": resolved_run_id,
            "category": category,
            "items": [dict(row) for row in rows],
        }
    finally:
        conn.close()


def format_tool_inventory_report(report: dict[str, Any]) -> str:
    if report.get("status") == "no_runs":
        return "Local Tool Inventory v0\n\nNo tool inventory runs are recorded."
    run = report["run"]
    lines = [
        "Local Tool Inventory v0",
        "",
        f"Run: `{report['run_id']}`",
        f"Observed tools: {run['observed_count']}",
        f"Detected: {run['detected_count']}",
        f"Not detected: {run['not_detected_count']}",
        f"Install action taken: {bool(run['install_action_taken'])}",
        f"Integration action taken: {bool(run['integration_action_taken'])}",
        f"Runtime authority: {bool(run['runtime_authority'])}",
        f"Network access attempted: {bool(run['network_access_attempted'])}",
        "",
        "Counts:",
    ]
    for count_name, counts in report["counts"].items():
        rendered = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        lines.append(f"- {count_name}: {rendered or 'none'}")
    lines.extend(["", "Detected sample:"])
    samples = report.get("detected_samples") or []
    if not samples:
        lines.append("- none")
    for item in samples:
        version = f" :: {item['version_text']}" if item.get("version_text") else ""
        review = " review" if item.get("requires_operator_review") else ""
        lines.append(
            f"- {item['tool_id']} ({item['category']}, {item['risk_level']}{review}) "
            f"{item.get('executable_path') or ''}{version}"
        )
    return "\n".join(lines)
