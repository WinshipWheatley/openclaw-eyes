"""Tool Intake Registry v0 candidate policy overlay for OpenClaw.

This module records non-authorizing candidate policy metadata for external
tools in the existing Business Ops ledger under a separate ``tool_intake_*``
namespace. It links to Local Tool Inventory observations where possible. It
does not execute tools, install packages, contact networks, clone repositories,
activate runtime behavior, or approve integrations.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger


TOOL_INTAKE_VERSION = "tool_intake_registry_v0"

CANDIDATE_STATUSES = {
    "candidate",
    "sandbox_later",
    "approved_later",
    "rejected",
    "deferred",
    "observed_only",
}
INSTALL_STATUSES = {"observed_installed", "not_detected", "unknown"}
INTEGRATION_STATUSES = {"not_integrated"}
APPROVAL_STATUSES = {"not_approved"}
FIT_LEVELS = {"high", "medium", "low", "unknown"}
RISK_LEVELS = {"low", "medium", "high"}
DATA_ACCESS_RISKS = {"none", "low", "medium", "high", "unknown"}
SOURCE_BASES = {
    "operator_seeded",
    "local_inventory_detected",
    "local_inventory_not_detected",
}
CANDIDATE_CATEGORIES = {
    "sqlite_exploration",
    "sqlite_backup",
    "sqlite_vector_search",
    "file_sync",
    "project_template",
    "reproducible_environment",
    "deployment",
    "self_hosted_git",
    "observability",
    "security_scanning",
    "secrets_management",
    "remote_access",
    "client_app_backend",
    "internal_app_builder",
    "ai_retrieval",
    "local_llm",
}


@dataclass(frozen=True)
class CandidateSeed:
    tool_id: str
    name: str
    category: str
    candidate_status: str
    architecture_fit: str
    risk_level: str
    data_access_risk: str
    local_first_fit: str
    client_capsule_fit: str
    evidence_fit: str
    openclaw_use_case: str
    notes: str
    inventory_tool_id: str | None = None


@dataclass(frozen=True)
class ToolIntakeResult:
    run_id: str
    db_path: str
    candidate_count: int
    linked_inventory_count: int
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


def _seed(
    tool_id: str,
    name: str,
    category: str,
    candidate_status: str,
    architecture_fit: str,
    risk_level: str,
    *,
    data_access_risk: str = "unknown",
    local_first_fit: str = "medium",
    client_capsule_fit: str = "unknown",
    evidence_fit: str = "medium",
    use_case: str,
    notes: str = "Candidate metadata only. Candidate does not mean approved.",
    inventory_tool_id: str | None = None,
) -> CandidateSeed:
    if category not in CANDIDATE_CATEGORIES:
        raise ValueError(f"unknown category: {category}")
    if candidate_status not in CANDIDATE_STATUSES:
        raise ValueError(f"unknown candidate status: {candidate_status}")
    if architecture_fit not in FIT_LEVELS:
        raise ValueError(f"unknown architecture fit: {architecture_fit}")
    if risk_level not in RISK_LEVELS:
        raise ValueError(f"unknown risk level: {risk_level}")
    if data_access_risk not in DATA_ACCESS_RISKS:
        raise ValueError(f"unknown data access risk: {data_access_risk}")
    return CandidateSeed(
        tool_id=tool_id,
        name=name,
        category=category,
        candidate_status=candidate_status,
        architecture_fit=architecture_fit,
        risk_level=risk_level,
        data_access_risk=data_access_risk,
        local_first_fit=local_first_fit,
        client_capsule_fit=client_capsule_fit,
        evidence_fit=evidence_fit,
        openclaw_use_case=use_case,
        notes=notes,
        inventory_tool_id=inventory_tool_id or tool_id,
    )


DEFAULT_CANDIDATE_SEEDS: tuple[CandidateSeed, ...] = (
    _seed("datasette", "Datasette", "sqlite_exploration", "candidate", "high", "medium", data_access_risk="low", local_first_fit="high", evidence_fit="high", use_case="Inspect OpenClaw SQLite read models and ledgers in a bounded future review surface."),
    _seed("sqlite_utils", "sqlite-utils", "sqlite_exploration", "candidate", "high", "low", data_access_risk="low", local_first_fit="high", evidence_fit="high", use_case="Small SQLite maintenance and metadata utility candidate.", inventory_tool_id="sqlite_utils"),
    _seed("sqlite3", "sqlite3", "sqlite_exploration", "candidate", "high", "low", data_access_risk="low", local_first_fit="high", evidence_fit="high", use_case="SQLite CLI inspection candidate if present; Python stdlib SQLite remains sufficient when absent."),
    _seed("litestream", "Litestream", "sqlite_backup", "candidate", "high", "medium", data_access_risk="medium", local_first_fit="high", evidence_fit="medium", use_case="Future SQLite backup/replication candidate after explicit backup policy."),
    _seed("sqlite_vec", "sqlite-vec", "sqlite_vector_search", "deferred", "medium", "medium", data_access_risk="medium", local_first_fit="high", evidence_fit="high", use_case="Potential local vector search extension for bounded evidence retrieval.", inventory_tool_id=None),
    _seed("syncthing", "Syncthing", "file_sync", "sandbox_later", "medium", "medium", data_access_risk="medium", local_first_fit="high", client_capsule_fit="medium", evidence_fit="low", use_case="Future root/mirror sync candidate after private-boundary and conflict policy."),
    _seed("copier", "Copier", "project_template", "candidate", "high", "low", data_access_risk="none", local_first_fit="high", client_capsule_fit="high", evidence_fit="low", use_case="Client/project capsule template generation candidate."),
    _seed("cookiecutter", "Cookiecutter", "project_template", "candidate", "medium", "low", data_access_risk="none", local_first_fit="high", client_capsule_fit="medium", evidence_fit="low", use_case="Project template generation candidate."),
    _seed("devbox", "Devbox", "reproducible_environment", "candidate", "high", "medium", data_access_risk="low", local_first_fit="high", client_capsule_fit="medium", evidence_fit="low", use_case="Reproducible local environment candidate for bounded project capsules."),
    _seed("caddy", "Caddy", "deployment", "sandbox_later", "medium", "medium", data_access_risk="medium", local_first_fit="medium", client_capsule_fit="medium", evidence_fit="low", use_case="Future local/reverse-proxy deployment candidate after explicit server policy."),
    _seed("coolify", "Coolify", "deployment", "deferred", "medium", "high", data_access_risk="high", local_first_fit="low", client_capsule_fit="medium", evidence_fit="low", use_case="Deferred deployment control surface candidate."),
    _seed("dokku", "Dokku", "deployment", "deferred", "medium", "medium", data_access_risk="medium", local_first_fit="medium", client_capsule_fit="medium", evidence_fit="low", use_case="Deferred lightweight deployment platform candidate."),
    _seed("ansible", "Ansible", "deployment", "deferred", "medium", "high", data_access_risk="high", local_first_fit="medium", client_capsule_fit="low", evidence_fit="low", use_case="Deferred remote-management candidate; no host contact authorized."),
    _seed("docker", "Docker", "deployment", "observed_only", "medium", "high", data_access_risk="medium", local_first_fit="medium", client_capsule_fit="medium", evidence_fit="low", use_case="Observed container substrate only; no image pulls, builds, runs, or compose starts authorized."),
    _seed("gitea", "Gitea", "self_hosted_git", "deferred", "medium", "medium", data_access_risk="medium", local_first_fit="medium", client_capsule_fit="low", evidence_fit="low", use_case="Deferred self-hosted Git review surface candidate.", inventory_tool_id=None),
    _seed("forgejo", "Forgejo", "self_hosted_git", "deferred", "medium", "medium", data_access_risk="medium", local_first_fit="medium", client_capsule_fit="low", evidence_fit="low", use_case="Deferred self-hosted Git review surface candidate.", inventory_tool_id=None),
    _seed("opentelemetry", "OpenTelemetry", "observability", "deferred", "medium", "medium", data_access_risk="medium", local_first_fit="medium", client_capsule_fit="medium", evidence_fit="medium", use_case="Deferred telemetry standard candidate for future explicit observability lanes.", inventory_tool_id=None),
    _seed("prometheus", "Prometheus", "observability", "deferred", "medium", "medium", data_access_risk="medium", local_first_fit="medium", client_capsule_fit="medium", evidence_fit="medium", use_case="Deferred metrics candidate; no scraping or service start authorized."),
    _seed("grafana", "Grafana", "observability", "deferred", "medium", "medium", data_access_risk="medium", local_first_fit="medium", client_capsule_fit="medium", evidence_fit="low", use_case="Deferred dashboard candidate; no service start authorized."),
    _seed("loki", "Loki", "observability", "deferred", "medium", "medium", data_access_risk="medium", local_first_fit="medium", client_capsule_fit="medium", evidence_fit="medium", use_case="Deferred log aggregation candidate; no service start authorized."),
    _seed("netdata", "Netdata", "observability", "sandbox_later", "medium", "medium", data_access_risk="medium", local_first_fit="medium", client_capsule_fit="low", evidence_fit="medium", use_case="Future local observability sandbox candidate; no daemon start authorized."),
    _seed("uptime_kuma", "Uptime Kuma", "observability", "sandbox_later", "medium", "medium", data_access_risk="medium", local_first_fit="medium", client_capsule_fit="medium", evidence_fit="low", use_case="Future uptime/status sandbox candidate; no service start authorized."),
    _seed("trivy", "Trivy", "security_scanning", "candidate", "high", "medium", data_access_risk="medium", local_first_fit="high", client_capsule_fit="medium", evidence_fit="high", use_case="Future bounded security scan/SBOM evidence candidate."),
    _seed("syft", "Syft", "security_scanning", "candidate", "high", "medium", data_access_risk="medium", local_first_fit="high", client_capsule_fit="medium", evidence_fit="high", use_case="Future bounded SBOM evidence candidate."),
    _seed("grype", "Grype", "security_scanning", "candidate", "high", "medium", data_access_risk="medium", local_first_fit="high", client_capsule_fit="medium", evidence_fit="high", use_case="Future bounded vulnerability evidence candidate."),
    _seed("sops", "SOPS", "secrets_management", "deferred", "medium", "high", data_access_risk="high", local_first_fit="medium", client_capsule_fit="low", evidence_fit="low", use_case="Deferred secrets workflow candidate; no secret read/write/decrypt authorized."),
    _seed("age", "age", "secrets_management", "deferred", "medium", "medium", data_access_risk="high", local_first_fit="medium", client_capsule_fit="low", evidence_fit="low", use_case="Deferred encryption primitive candidate; no secret material access authorized."),
    _seed("openbao", "OpenBao", "secrets_management", "deferred", "low", "high", data_access_risk="high", local_first_fit="low", client_capsule_fit="low", evidence_fit="low", use_case="Deferred secrets service candidate; no store contact authorized."),
    _seed("wireguard", "WireGuard", "remote_access", "deferred", "medium", "high", data_access_risk="high", local_first_fit="medium", client_capsule_fit="low", evidence_fit="low", use_case="Deferred remote-access candidate; no tunnel start authorized."),
    _seed("headscale", "Headscale", "remote_access", "deferred", "low", "high", data_access_risk="high", local_first_fit="low", client_capsule_fit="low", evidence_fit="low", use_case="Deferred coordination server candidate; no remote access authorized."),
    _seed("meshcentral", "MeshCentral", "remote_access", "deferred", "low", "high", data_access_risk="high", local_first_fit="low", client_capsule_fit="low", evidence_fit="low", use_case="Deferred remote management candidate; no remote access authorized."),
    _seed("pocketbase", "PocketBase", "client_app_backend", "candidate", "high", "medium", data_access_risk="medium", local_first_fit="high", client_capsule_fit="high", evidence_fit="medium", use_case="Client capsule/internal app backend candidate."),
    _seed("directus", "Directus", "client_app_backend", "deferred", "medium", "medium", data_access_risk="medium", local_first_fit="medium", client_capsule_fit="medium", evidence_fit="medium", use_case="Deferred client app backend/content API candidate."),
    _seed("appwrite", "Appwrite", "client_app_backend", "deferred", "medium", "medium", data_access_risk="medium", local_first_fit="medium", client_capsule_fit="medium", evidence_fit="low", use_case="Deferred client app backend platform candidate."),
    _seed("appsmith", "Appsmith", "internal_app_builder", "deferred", "medium", "medium", data_access_risk="medium", local_first_fit="medium", client_capsule_fit="medium", evidence_fit="low", use_case="Deferred internal app builder candidate."),
    _seed("haystack", "Haystack", "ai_retrieval", "deferred", "medium", "medium", data_access_risk="medium", local_first_fit="medium", client_capsule_fit="low", evidence_fit="high", use_case="Deferred AI retrieval framework candidate for future Evidence Kettle experiments.", inventory_tool_id=None),
    _seed("llamaindex", "LlamaIndex", "ai_retrieval", "deferred", "medium", "medium", data_access_risk="medium", local_first_fit="medium", client_capsule_fit="low", evidence_fit="high", use_case="Deferred AI retrieval framework candidate for future Evidence Kettle experiments.", inventory_tool_id=None),
    _seed("ollama", "Ollama", "local_llm", "observed_only", "medium", "high", data_access_risk="medium", local_first_fit="high", client_capsule_fit="low", evidence_fit="medium", use_case="Observed local model runner candidate; no model list, pull, run, or agent use authorized."),
    _seed("llama_cpp", "llama.cpp", "local_llm", "sandbox_later", "medium", "medium", data_access_risk="medium", local_first_fit="high", client_capsule_fit="low", evidence_fit="medium", use_case="Future local model sandbox candidate; no model execution authorized.", inventory_tool_id="llama_cpp"),
)


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS tool_intake_runs (
  run_id TEXT PRIMARY KEY,
  intake_version TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  candidate_count INTEGER NOT NULL DEFAULT 0,
  linked_inventory_count INTEGER NOT NULL DEFAULT 0,
  install_action_taken INTEGER NOT NULL DEFAULT 0,
  integration_action_taken INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  network_access_attempted INTEGER NOT NULL DEFAULT 0,
  tool_execution_attempted INTEGER NOT NULL DEFAULT 0,
  source_basis_json TEXT NOT NULL,
  notes TEXT
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS tool_candidates (
  candidate_id TEXT PRIMARY KEY,
  tool_id TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  candidate_status TEXT NOT NULL,
  install_status TEXT NOT NULL,
  integration_status TEXT NOT NULL,
  approval_status TEXT NOT NULL,
  architecture_fit TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  data_access_risk TEXT NOT NULL,
  local_first_fit TEXT NOT NULL,
  client_capsule_fit TEXT NOT NULL,
  evidence_fit TEXT NOT NULL,
  openclaw_use_case TEXT NOT NULL,
  notes TEXT NOT NULL,
  source_basis TEXT NOT NULL,
  inventory_observation_id TEXT,
  inventory_run_id TEXT,
  official_url TEXT,
  license TEXT,
  install_command TEXT,
  requires_operator_review INTEGER NOT NULL,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  integration_authority INTEGER NOT NULL DEFAULT 0,
  install_authority INTEGER NOT NULL DEFAULT 0,
  tool_execution_authority INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (inventory_observation_id) REFERENCES tool_observations(observation_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS tool_candidate_labels (
  label_id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL,
  label_name TEXT NOT NULL,
  label_value TEXT NOT NULL,
  label_basis TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (candidate_id) REFERENCES tool_candidates(candidate_id) ON DELETE CASCADE,
  UNIQUE(candidate_id, label_name, label_value, label_basis)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS tool_candidate_use_cases (
  use_case_id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL,
  use_case_label TEXT NOT NULL,
  use_case_text TEXT NOT NULL,
  fit_level TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (candidate_id) REFERENCES tool_candidates(candidate_id) ON DELETE CASCADE,
  UNIQUE(candidate_id, use_case_label)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS tool_candidate_risks (
  risk_id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL,
  risk_type TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  risk_text TEXT NOT NULL,
  mitigation_status TEXT NOT NULL,
  requires_operator_review INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (candidate_id) REFERENCES tool_candidates(candidate_id) ON DELETE CASCADE,
  UNIQUE(candidate_id, risk_type)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS tool_candidate_inventory_links (
  link_id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL,
  observation_id TEXT NOT NULL,
  inventory_run_id TEXT NOT NULL,
  link_basis TEXT NOT NULL,
  install_status_at_link TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (candidate_id) REFERENCES tool_candidates(candidate_id) ON DELETE CASCADE,
  FOREIGN KEY (observation_id) REFERENCES tool_observations(observation_id),
  UNIQUE(candidate_id, observation_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS tool_candidate_status_history (
  history_id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  candidate_status TEXT NOT NULL,
  approval_status TEXT NOT NULL,
  integration_status TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (candidate_id) REFERENCES tool_candidates(candidate_id) ON DELETE CASCADE,
  FOREIGN KEY (run_id) REFERENCES tool_intake_runs(run_id) ON DELETE CASCADE,
  UNIQUE(candidate_id, run_id, candidate_status)
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_tool_candidates_category ON tool_candidates(category)",
        "CREATE INDEX IF NOT EXISTS idx_tool_candidates_status ON tool_candidates(candidate_status)",
        "CREATE INDEX IF NOT EXISTS idx_tool_candidates_risk ON tool_candidates(risk_level)",
        "CREATE INDEX IF NOT EXISTS idx_tool_candidates_install ON tool_candidates(install_status)",
        "CREATE INDEX IF NOT EXISTS idx_tool_candidate_links_observation ON tool_candidate_inventory_links(observation_id)",
    )


def init_tool_intake_schema(db_path: str | Path | None = None) -> str:
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


def tool_intake_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_tool_intake_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type='table' AND name LIKE 'tool_intake_%'
   OR type='table' AND name LIKE 'tool_candidate%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _latest_inventory_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id
FROM tool_inventory_runs
ORDER BY completed_at DESC, started_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row[0] if row else None


def _inventory_observations(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    try:
        latest_run_id = _latest_inventory_run_id(conn)
    except sqlite3.OperationalError:
        return {}
    if not latest_run_id:
        return {}
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
SELECT observation_id, run_id, tool_id, install_status, detected, category, risk_level
FROM tool_observations
WHERE run_id = ?
""".strip(),
        (latest_run_id,),
    ).fetchall()
    return {row["tool_id"]: row for row in rows}


def _review_required(seed: CandidateSeed) -> bool:
    return (
        seed.risk_level == "high"
        or seed.data_access_risk == "high"
        or seed.category in {"remote_access", "secrets_management"}
        or seed.candidate_status in {"sandbox_later", "approved_later"}
    )


def _source_basis(row: sqlite3.Row | None) -> str:
    if row is None:
        return "operator_seeded"
    return "local_inventory_detected" if row["install_status"] == "observed_installed" else "local_inventory_not_detected"


def _install_status(row: sqlite3.Row | None) -> str:
    if row is None:
        return "unknown"
    status = row["install_status"]
    if status in INSTALL_STATUSES:
        return status
    return "unknown"


def _validate_seed(seed: CandidateSeed) -> None:
    if seed.category not in CANDIDATE_CATEGORIES:
        raise ValueError(f"bad category: {seed.tool_id}")
    if seed.candidate_status not in CANDIDATE_STATUSES:
        raise ValueError(f"bad candidate status: {seed.tool_id}")
    if seed.architecture_fit not in FIT_LEVELS:
        raise ValueError(f"bad architecture fit: {seed.tool_id}")
    if seed.risk_level not in RISK_LEVELS:
        raise ValueError(f"bad risk level: {seed.tool_id}")
    if seed.data_access_risk not in DATA_ACCESS_RISKS:
        raise ValueError(f"bad data access risk: {seed.tool_id}")
    for fit in (seed.local_first_fit, seed.client_capsule_fit, seed.evidence_fit):
        if fit not in FIT_LEVELS:
            raise ValueError(f"bad fit level: {seed.tool_id}")


def _insert_label(
    conn: sqlite3.Connection,
    *,
    candidate_id: str,
    name: str,
    value: str,
    basis: str,
    created_at: str,
) -> None:
    conn.execute(
        """
INSERT INTO tool_candidate_labels (
  label_id, candidate_id, label_name, label_value, label_basis, created_at
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(candidate_id, label_name, label_value, label_basis) DO UPDATE SET
  created_at = excluded.created_at
""".strip(),
        (
            _row_id("tcandlabel", candidate_id, name, value, basis),
            candidate_id,
            name,
            value,
            basis,
            created_at,
        ),
    )


def _insert_child_rows(
    conn: sqlite3.Connection,
    *,
    seed: CandidateSeed,
    candidate_id: str,
    run_id: str,
    inventory_row: sqlite3.Row | None,
    source_basis: str,
    install_status: str,
    review_required: bool,
    now: str,
) -> None:
    for name, value, basis in (
        ("category", seed.category, "tool_intake_seed"),
        ("candidate_status", seed.candidate_status, "tool_intake_seed"),
        ("risk_level", seed.risk_level, "tool_intake_seed"),
        ("architecture_fit", seed.architecture_fit, "tool_intake_seed"),
        ("source_basis", source_basis, "tool_intake_linker"),
        ("install_status", install_status, "tool_intake_linker"),
        ("approval_status", "not_approved", "tool_intake_doctrine"),
        ("integration_status", "not_integrated", "tool_intake_doctrine"),
    ):
        _insert_label(
            conn,
            candidate_id=candidate_id,
            name=name,
            value=value,
            basis=basis,
            created_at=now,
        )

    conn.execute(
        """
INSERT INTO tool_candidate_use_cases (
  use_case_id, candidate_id, use_case_label, use_case_text, fit_level, created_at
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(candidate_id, use_case_label) DO UPDATE SET
  use_case_text = excluded.use_case_text,
  fit_level = excluded.fit_level,
  created_at = excluded.created_at
""".strip(),
        (
            _row_id("tcanduse", candidate_id, "openclaw_primary"),
            candidate_id,
            "openclaw_primary",
            seed.openclaw_use_case,
            seed.architecture_fit,
            now,
        ),
    )

    conn.execute(
        """
INSERT INTO tool_candidate_risks (
  risk_id, candidate_id, risk_type, risk_level, risk_text,
  mitigation_status, requires_operator_review, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(candidate_id, risk_type) DO UPDATE SET
  risk_level = excluded.risk_level,
  risk_text = excluded.risk_text,
  mitigation_status = excluded.mitigation_status,
  requires_operator_review = excluded.requires_operator_review,
  created_at = excluded.created_at
""".strip(),
        (
            _row_id("tcandrisk", candidate_id, "authority_boundary"),
            candidate_id,
            "authority_boundary",
            seed.risk_level,
            "Candidate record only; no execution, install, approval, integration, network, model, container, remote, or runtime authority.",
            "blocked_pending_operator_review",
            1 if review_required else 0,
            now,
        ),
    )

    if inventory_row is not None:
        conn.execute(
            """
INSERT INTO tool_candidate_inventory_links (
  link_id, candidate_id, observation_id, inventory_run_id, link_basis,
  install_status_at_link, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(candidate_id, observation_id) DO UPDATE SET
  link_basis = excluded.link_basis,
  install_status_at_link = excluded.install_status_at_link,
  created_at = excluded.created_at
""".strip(),
            (
                _row_id("tcandlink", candidate_id, inventory_row["observation_id"]),
                candidate_id,
                inventory_row["observation_id"],
                inventory_row["run_id"],
                source_basis,
                install_status,
                now,
            ),
        )

    conn.execute(
        """
INSERT INTO tool_candidate_status_history (
  history_id, candidate_id, run_id, candidate_status, approval_status,
  integration_status, reason, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(candidate_id, run_id, candidate_status) DO UPDATE SET
  approval_status = excluded.approval_status,
  integration_status = excluded.integration_status,
  reason = excluded.reason,
  created_at = excluded.created_at
""".strip(),
        (
            _row_id("tcandhist", candidate_id, run_id, seed.candidate_status),
            candidate_id,
            run_id,
            seed.candidate_status,
            "not_approved",
            "not_integrated",
            "Seeded as non-authorizing policy overlay.",
            now,
        ),
    )


def seed_tool_intake_registry(
    db_path: str | Path | None = None,
    *,
    run_id: str | None = None,
    candidate_seeds: Iterable[CandidateSeed] = DEFAULT_CANDIDATE_SEEDS,
) -> ToolIntakeResult:
    path = init_tool_intake_schema(db_path)
    seeds = tuple(candidate_seeds)
    started_at = utc_now()
    resolved_run_id = run_id or _row_id("toolintake", started_at, len(seeds))
    now = utc_now()

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        inventory = _inventory_observations(conn)
        conn.execute("DELETE FROM tool_intake_runs WHERE run_id = ?", (resolved_run_id,))
        conn.execute(
            """
INSERT INTO tool_intake_runs (
  run_id, intake_version, started_at, source_basis_json, notes
) VALUES (?, ?, ?, ?, ?)
""".strip(),
            (
                resolved_run_id,
                TOOL_INTAKE_VERSION,
                started_at,
                stable_json(
                    {
                        "candidate_seed_count": len(seeds),
                        "operator_seeded": True,
                        "inventory_linking": "latest_tool_inventory_run_when_present",
                        "external_calls": False,
                        "subprocess": False,
                        "installs": False,
                        "runtime_activation": False,
                    }
                ),
                "Candidate does not mean approved; installed does not mean integrated.",
            ),
        )

        linked_count = 0
        seen_ids: set[str] = set()
        for seed in seeds:
            _validate_seed(seed)
            if seed.tool_id in seen_ids:
                raise ValueError(f"duplicate candidate seed: {seed.tool_id}")
            seen_ids.add(seed.tool_id)
            inventory_row = inventory.get(seed.inventory_tool_id or seed.tool_id)
            if inventory_row is not None:
                linked_count += 1
            source_basis = _source_basis(inventory_row)
            install_status = _install_status(inventory_row)
            review_required = _review_required(seed)
            candidate_id = _row_id("tcand", seed.tool_id)

            existing = conn.execute(
                "SELECT created_at FROM tool_candidates WHERE tool_id = ?",
                (seed.tool_id,),
            ).fetchone()
            created_at = existing["created_at"] if existing else now
            conn.execute(
                """
INSERT INTO tool_candidates (
  candidate_id, tool_id, name, category, candidate_status, install_status,
  integration_status, approval_status, architecture_fit, risk_level,
  data_access_risk, local_first_fit, client_capsule_fit, evidence_fit,
  openclaw_use_case, notes, source_basis, inventory_observation_id,
  inventory_run_id, official_url, license, install_command,
  requires_operator_review, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(tool_id) DO UPDATE SET
  name = excluded.name,
  category = excluded.category,
  candidate_status = excluded.candidate_status,
  install_status = excluded.install_status,
  integration_status = excluded.integration_status,
  approval_status = excluded.approval_status,
  architecture_fit = excluded.architecture_fit,
  risk_level = excluded.risk_level,
  data_access_risk = excluded.data_access_risk,
  local_first_fit = excluded.local_first_fit,
  client_capsule_fit = excluded.client_capsule_fit,
  evidence_fit = excluded.evidence_fit,
  openclaw_use_case = excluded.openclaw_use_case,
  notes = excluded.notes,
  source_basis = excluded.source_basis,
  inventory_observation_id = excluded.inventory_observation_id,
  inventory_run_id = excluded.inventory_run_id,
  official_url = excluded.official_url,
  license = excluded.license,
  install_command = excluded.install_command,
  requires_operator_review = excluded.requires_operator_review,
  updated_at = excluded.updated_at
""".strip(),
                (
                    candidate_id,
                    seed.tool_id,
                    seed.name,
                    seed.category,
                    seed.candidate_status,
                    install_status,
                    "not_integrated",
                    "not_approved",
                    seed.architecture_fit,
                    seed.risk_level,
                    seed.data_access_risk,
                    seed.local_first_fit,
                    seed.client_capsule_fit,
                    seed.evidence_fit,
                    seed.openclaw_use_case,
                    seed.notes,
                    source_basis,
                    inventory_row["observation_id"] if inventory_row is not None else None,
                    inventory_row["run_id"] if inventory_row is not None else None,
                    None,
                    None,
                    None,
                    1 if review_required else 0,
                    created_at,
                    now,
                ),
            )
            _insert_child_rows(
                conn,
                seed=seed,
                candidate_id=candidate_id,
                run_id=resolved_run_id,
                inventory_row=inventory_row,
                source_basis=source_basis,
                install_status=install_status,
                review_required=review_required,
                now=now,
            )

        rows = conn.execute("SELECT * FROM tool_candidates").fetchall()
        counts = {
            "category": dict(sorted(Counter(row["category"] for row in rows).items())),
            "candidate_status": dict(
                sorted(Counter(row["candidate_status"] for row in rows).items())
            ),
            "install_status": dict(
                sorted(Counter(row["install_status"] for row in rows).items())
            ),
            "risk_level": dict(sorted(Counter(row["risk_level"] for row in rows).items())),
        }
        conn.execute(
            """
UPDATE tool_intake_runs
SET completed_at = ?,
    candidate_count = ?,
    linked_inventory_count = ?
WHERE run_id = ?
""".strip(),
            (utc_now(), len(rows), linked_count, resolved_run_id),
        )
        conn.commit()
        return ToolIntakeResult(
            run_id=resolved_run_id,
            db_path=path,
            candidate_count=len(rows),
            linked_inventory_count=linked_count,
            counts=counts,
        )
    finally:
        conn.close()


def _latest_intake_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id
FROM tool_intake_runs
ORDER BY completed_at DESC, started_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row["run_id"] if row else None


def build_tool_intake_report(
    db_path: str | Path | None = None,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    path = init_tool_intake_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_run_id = run_id or _latest_intake_run_id(conn)
        if not resolved_run_id:
            return {"status": "no_runs", "section": "summary"}
        run = conn.execute(
            "SELECT * FROM tool_intake_runs WHERE run_id = ?", (resolved_run_id,)
        ).fetchone()
        count_fields = ("category", "candidate_status", "install_status", "risk_level")
        counts = {}
        for field in count_fields:
            rows = conn.execute(
                f"""
SELECT {field} AS label, COUNT(*) AS count
FROM tool_candidates
GROUP BY {field}
ORDER BY {field}
""".strip()
            ).fetchall()
            counts[field] = {row["label"]: row["count"] for row in rows}
        sample_rows = conn.execute(
            """
SELECT tool_id, name, category, candidate_status, install_status,
       architecture_fit, risk_level, approval_status, integration_status,
       requires_operator_review
FROM tool_candidates
ORDER BY category, tool_id
LIMIT 24
""".strip()
        ).fetchall()
        return {
            "status": "ok",
            "section": "summary",
            "run_id": resolved_run_id,
            "run": dict(run),
            "counts": counts,
            "sample_candidates": [dict(row) for row in sample_rows],
        }
    finally:
        conn.close()


def query_tool_intake_report_section(
    db_path: str | Path | None = None,
    *,
    run_id: str | None = None,
    section: str = "summary",
    category: str | None = None,
) -> dict[str, Any]:
    if section == "summary":
        return build_tool_intake_report(db_path=db_path, run_id=run_id)
    path = init_tool_intake_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_run_id = run_id or _latest_intake_run_id(conn)
        if not resolved_run_id:
            return {"status": "no_runs", "section": section, "items": []}
        where = "1=1"
        params: list[Any] = []
        if section == "category":
            where = "category = ?"
            params.append(category or "")
        elif section == "high-fit":
            where = "architecture_fit = 'high'"
        elif section == "high-risk":
            where = "risk_level = 'high'"
        elif section == "sandbox-later":
            where = "candidate_status = 'sandbox_later'"
        elif section == "client-capsule":
            where = "client_capsule_fit IN ('high','medium')"
        elif section == "installed-candidates":
            where = "install_status = 'observed_installed'"
        elif section == "not-detected-candidates":
            where = "install_status = 'not_detected'"
        else:
            raise ValueError(f"unknown report section: {section}")
        rows = conn.execute(
            f"""
SELECT candidate_id, tool_id, name, category, candidate_status, install_status,
       integration_status, approval_status, architecture_fit, risk_level,
       data_access_risk, local_first_fit, client_capsule_fit, evidence_fit,
       openclaw_use_case, notes, source_basis, inventory_observation_id,
       inventory_run_id, official_url, license, install_command,
       requires_operator_review
FROM tool_candidates
WHERE {where}
ORDER BY
  CASE architecture_fit WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
  CASE risk_level WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
  category,
  tool_id
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


def format_tool_intake_report(report: dict[str, Any]) -> str:
    if report.get("status") == "no_runs":
        return "Tool Intake Registry v0\n\nNo tool intake runs are recorded."
    run = report["run"]
    lines = [
        "Tool Intake Registry v0",
        "",
        f"Run: `{report['run_id']}`",
        f"Candidates: {run['candidate_count']}",
        f"Inventory-linked candidates: {run['linked_inventory_count']}",
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
    lines.extend(["", "Sample candidates:"])
    samples = report.get("sample_candidates") or []
    if not samples:
        lines.append("- none")
    for item in samples:
        review = " review" if item.get("requires_operator_review") else ""
        lines.append(
            f"- {item['tool_id']} ({item['category']}, {item['candidate_status']}, "
            f"{item['install_status']}, fit={item['architecture_fit']}, "
            f"risk={item['risk_level']}{review})"
        )
    lines.extend(
        [
            "",
            "Boundary:",
            "- Candidate does not mean approved; installed does not mean integrated.",
            "- Registry rows do not authorize installs, execution, network calls, runtime activation, or integrations.",
        ]
    )
    return "\n".join(lines)
