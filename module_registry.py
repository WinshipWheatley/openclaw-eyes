"""Module / Capability Registry v0 for OpenClaw planning.

This module records reusable OpenClaw capabilities in the Business Ops ledger
under a separate ``module_registry_*`` namespace. It is a planning registry
only and grants no runtime, tool, deployment, network, model, or agent
authority.
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


MODULE_REGISTRY_VERSION = "module_registry_v0"
APPROVED_MODULE_READ_MODEL_VERSION = "approved_module_registry_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
APPROVED_JSON_EXPORT_NAME = "approved_module_registry.json"
APPROVED_OPERATOR_EXPORT_NAME = "approved_module_registry_OPERATOR.md"

APPROVED_MODULE_STATUSES = {"approved", "draft", "blocked", "deprecated"}
MODULE_STATUSES = {"available_planning", "experimental", "future_gated", "deprecated"} | APPROVED_MODULE_STATUSES
AUTHORITY_LEVELS = {"read_only", "metadata_only", "planning_only", "future_gated"}
RISK_LEVELS = {"low", "medium", "high"}
CLIENT_SUITABILITY = {"high", "medium", "low", "unknown"}


@dataclass(frozen=True)
class ModuleSeed:
    module_id: str
    name: str
    category: str
    status: str
    authority_level: str
    risk_level: str
    client_capsule_suitability: str
    description: str
    required_inputs: tuple[str, ...]
    generated_outputs: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    runtime_authority_required: bool = False
    operator_review_required: bool = False
    version: str = "0.1.0"
    display_name: str | None = None
    world: str | None = None
    capabilities: tuple[str, ...] = ()
    optional_inputs: tuple[str, ...] = ()
    sensitive_input_policy: str = "metadata_only_no_private_raw_input"
    no_go_data_classes: tuple[str, ...] = (
        "credentials",
        "tokens",
        "raw_private_data",
        "raw_client_data",
    )
    allowed_authority_level: str | None = None
    tests_required: tuple[str, ...] = ()
    client_safe: bool | None = None
    core_only: bool = False
    report_bridge_summary_allowed: bool = True
    evidence_basis: str = "seeded_from_repo_a_stage_2_migration_spec"
    runtime_authority: bool = False


@dataclass(frozen=True)
class ModuleRegistryResult:
    run_id: str
    db_path: str
    module_count: int
    dependency_count: int


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256(
        "\0".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()
    return f"{prefix}_{digest[:20]}"


DEFAULT_MODULE_SEEDS: tuple[ModuleSeed, ...] = (
    ModuleSeed(
        "corpus_atlas",
        "Corpus Atlas",
        "metadata_substrate",
        "available_planning",
        "metadata_only",
        "low",
        "high",
        "Metadata, freshness, sensitivity, and multi-root location atlas.",
        ("filesystem metadata", "generated read-model seed signals"),
        ("corpus_* SQLite rows", "generated/corpus_atlas reports"),
    ),
    ModuleSeed(
        "evidence_kettle",
        "Evidence Kettle",
        "evidence_substrate",
        "available_planning",
        "metadata_only",
        "low",
        "high",
        "Bounded generated read-model and receipt summary evidence substrate.",
        ("corpus atlas eligibility labels", "generated read-model exports"),
        ("evidence_* SQLite rows", "read_model_snapshots"),
        ("corpus_atlas",),
    ),
    ModuleSeed(
        "tool_inventory",
        "Local Tool Inventory",
        "tool_posture",
        "available_planning",
        "metadata_only",
        "medium",
        "medium",
        "Observed installed local-tool metadata with no tool authority.",
        ("allowlisted local metadata probes",),
        ("tool_inventory_* SQLite rows", "generated/read_models/tool_inventory.json"),
    ),
    ModuleSeed(
        "tool_intake",
        "Tool Intake Registry",
        "tool_policy",
        "available_planning",
        "planning_only",
        "medium",
        "high",
        "Candidate tool policy overlay linked to inventory observations.",
        ("operator seeded candidate set", "local tool inventory rows"),
        ("tool_intake_* SQLite rows", "generated/read_models/tool_intake.json"),
        ("tool_inventory",),
    ),
    ModuleSeed(
        "context_selection",
        "Context Selection",
        "context_packet",
        "available_planning",
        "read_only",
        "low",
        "high",
        "Deterministic evidence-grounded context packet compiler.",
        ("evidence items", "read-model snapshots", "tool posture read-models"),
        ("context_selection_* SQLite rows", "generated/context_packets", "generated/read_models/context_selection.json"),
        ("evidence_kettle", "tool_inventory", "tool_intake"),
    ),
    ModuleSeed(
        "read_model_shuttle",
        "Cross-Machine Read-Model Shuttle",
        "sync_planning",
        "available_planning",
        "metadata_only",
        "medium",
        "medium",
        "Safe package-and-manifest flow for PC-to-Mac generated read-model mirroring.",
        ("generated/read_models exports", "operator-transferred manifests"),
        ("shuttle packages", "Mac mirror manifest imports"),
        ("mac_mirror_atlas",),
    ),
    ModuleSeed(
        "mac_mirror_atlas",
        "Mac Mirror Atlas",
        "mirror_mapping",
        "available_planning",
        "metadata_only",
        "medium",
        "medium",
        "Manifest-based Mac root mapping without direct crawl or remote access.",
        ("explicit metadata manifests",),
        ("corpus_roots Mac root rows", "corpus mirror candidates"),
        ("corpus_atlas",),
    ),
    ModuleSeed(
        "project_capsule",
        "Project Capsule",
        "client_project_planning",
        "available_planning",
        "planning_only",
        "low",
        "high",
        "Synthetic project/client starter contract and generated template layer.",
        ("operator project intent", "tool policy", "context posture"),
        ("project_capsule_* SQLite rows", "generated/read_models/project_capsules.json", "generated/project_capsules demo template"),
        ("tool_intake", "context_selection"),
    ),
    ModuleSeed(
        "mission_control_read_only_helm",
        "Mission Control Read-Only Helm",
        "operator_ui",
        "future_gated",
        "read_only",
        "medium",
        "medium",
        "Mac app read-only generated read-model inspection surface.",
        ("generated read-model mirror files",),
        ("read-only helm overview",),
        ("read_model_shuttle", "context_selection", "tool_inventory", "tool_intake", "project_capsule"),
        operator_review_required=True,
        core_only=True,
        report_bridge_summary_allowed=True,
    ),
    ModuleSeed(
        "chief_intent_routing",
        "Chief Intent Routing",
        "intake_spine",
        "approved",
        "planning_only",
        "low",
        "high",
        "Deterministic operator intent capture and route projection into governed records.",
        ("operator text metadata", "source metadata"),
        ("intent_records", "intent_router read-model rows"),
        ("context_selection",),
        version="0.1.0",
        display_name="Chief Intent Routing",
        world="operations",
        capabilities=("deterministic_intent_routing", "work_board_projection_candidate"),
        sensitive_input_policy="stores bounded preview and hash only; no raw private body authority",
        no_go_data_classes=("credentials", "tokens", "raw_private_data", "raw_client_data", "raw_logs"),
        allowed_authority_level="planning_only",
        tests_required=("tests/test_intent_router.py", "tests/test_governed_intake_spine.py"),
        client_safe=True,
        report_bridge_summary_allowed=True,
        evidence_basis="Repo A intent_router.py is implemented and non-executing.",
    ),
    ModuleSeed(
        "cassandra_clara_fact_intake",
        "Cassandra / Clara Fact Intake",
        "operator_comms",
        "draft",
        "metadata_only",
        "medium",
        "high",
        "Receive-only fact intake for Cassandra/Clara into governed storage and work packets.",
        ("operator-authored fact text metadata", "source metadata"),
        ("telegram_agent_update_records", "intent_records"),
        ("chief_intent_routing",),
        version="0.1.0",
        display_name="Cassandra / Clara Fact Intake",
        world="communications",
        capabilities=("receive_only_fact_intake", "finance_fact_route_candidate"),
        sensitive_input_policy="hash and bounded excerpt only; raw Telegram payload and client private data are blocked",
        no_go_data_classes=("telegram_tokens", "chat_ids", "raw_client_data", "bank_data", "spreadsheet_cells"),
        allowed_authority_level="metadata_only",
        tests_required=("tests/test_telegram_agent_intake.py", "tests/test_governed_intake_spine.py"),
        client_safe=True,
        report_bridge_summary_allowed=True,
        evidence_basis="Repo A Cassandra intake is governed; live reply/send remains blocked.",
    ),
    ModuleSeed(
        "guardian_hitl_gate",
        "Guardian HITL Gate",
        "approval_safety",
        "draft",
        "planning_only",
        "medium",
        "high",
        "Receipt-backed human-in-the-loop approval posture for future action payloads.",
        ("immutable action metadata", "operator approval decision"),
        ("operator_action_* rows", "HITL pending records"),
        version="0.1.0",
        display_name="Guardian HITL Gate",
        world="security",
        capabilities=("approval_gate", "second_factor_policy_candidate"),
        sensitive_input_policy="approval payloads must be sanitized immutable metadata; no raw shell strings",
        no_go_data_classes=("raw_shell", "credentials", "tokens", "raw_private_data", "raw_client_data"),
        allowed_authority_level="planning_only",
        tests_required=("tests/test_operator_action_inbox.py", "tests/test_operator_action.py"),
        client_safe=True,
        report_bridge_summary_allowed=True,
        evidence_basis="Repo A has operator action and HITL primitives; consolidation remains future work.",
    ),
    ModuleSeed(
        "niles_album_matrix",
        "Niles Album Matrix",
        "music_art",
        "draft",
        "planning_only",
        "medium",
        "high",
        "Governed music-art production matrix and readiness packet concept.",
        ("album/project metadata",),
        ("future niles_album_matrix rows",),
        version="0.1.0",
        display_name="Niles Album Matrix",
        world="music_art",
        capabilities=("album_progress_tracking", "production_readiness_drafts"),
        sensitive_input_policy="metadata-only until music/session private-content boundaries are approved",
        no_go_data_classes=("raw_daw_sessions", "unreleased_private_audio", "contracts", "credentials"),
        allowed_authority_level="planning_only",
        tests_required=("future tests/test_niles_album_matrix.py",),
        client_safe=True,
        report_bridge_summary_allowed=True,
        evidence_basis="Repo B album matrix concepts are useful but CSV/write behavior is blocked.",
    ),
    ModuleSeed(
        "hermes_next_lane_advisory",
        "Hermes Next Lane Advisory",
        "advisory_synthesis",
        "draft",
        "read_only",
        "low",
        "high",
        "Non-canonical advisory sorting for next safe lanes and readiness metrics.",
        ("sanitized read-model summaries", "Work Board metadata"),
        ("advisory next-lane notes",),
        ("work_board",),
        version="0.1.0",
        display_name="Hermes Next Lane Advisory",
        world="operations",
        capabilities=("readiness_metrics", "next_lane_sorting"),
        sensitive_input_policy="read-model summaries only; no private raw content",
        no_go_data_classes=("raw_private_data", "raw_client_data", "credentials", "tokens"),
        allowed_authority_level="read_only",
        tests_required=("future tests/test_hermes_next_lane_advisory.py",),
        client_safe=True,
        report_bridge_summary_allowed=True,
        evidence_basis="Repo B reflection concepts are useful only as non-authorizing advisory logic.",
    ),
    ModuleSeed(
        "planner_runner_registry",
        "Planner Runner Registry",
        "build_planning",
        "blocked",
        "future_gated",
        "high",
        "medium",
        "Runner registry and task tiering concept without runner launch authority.",
        ("Work Board metadata",),
        ("future runner registry metadata",),
        ("agent_work_packet", "work_board"),
        operator_review_required=True,
        version="0.1.0",
        display_name="Planner Runner Registry",
        world="build",
        capabilities=("task_tiering", "proof_requirement_catalog"),
        sensitive_input_policy="metadata-only; never includes command execution or runner launch payloads",
        no_go_data_classes=("raw_shell", "arbitrary_commands", "credentials", "tokens", "raw_private_data"),
        allowed_authority_level="future_gated",
        tests_required=("future tests/test_planner_runner_registry.py",),
        client_safe=False,
        core_only=True,
        report_bridge_summary_allowed=False,
        evidence_basis="Repo B watcher/loop concepts are blocked until a future explicit lane.",
    ),
    ModuleSeed(
        "report_bridge_sanitized_summary",
        "Report Bridge Sanitized Summary",
        "report_bridge",
        "approved",
        "metadata_only",
        "low",
        "high",
        "Sanitized status/proof/version/health package import and visibility.",
        ("sanitized report bridge manifest", "safe read-model/report files"),
        ("report_bridge_* rows", "generated/read_models/report_bridge.json"),
        version="0.1.0",
        display_name="Report Bridge Sanitized Summary",
        world="operations",
        capabilities=("sanitized_status_import", "client_safe_summary_visibility"),
        sensitive_input_policy="reject raw bodies and client data by default",
        no_go_data_classes=("raw_client_data", "raw_private_bodies", "credentials", "tokens", "bank_data"),
        allowed_authority_level="metadata_only",
        tests_required=("tests/test_report_bridge.py",),
        client_safe=True,
        report_bridge_summary_allowed=True,
        evidence_basis="Repo A report_bridge.py is implemented and rejects raw bodies/client data by default.",
    ),
    ModuleSeed(
        "project_capsule_bundle_blueprint",
        "Project Capsule Bundle Blueprint",
        "client_project_planning",
        "draft",
        "planning_only",
        "low",
        "high",
        "Local-first client/project bundle manifest planning without repo creation or deployment.",
        ("structured pain point metadata", "approved module registry"),
        ("local bundle manifest dictionary", "bundle blueprint read-model"),
        ("project_capsule", "report_bridge_sanitized_summary"),
        version="0.1.0",
        display_name="Project Capsule Bundle Blueprint",
        world="business_development",
        capabilities=("bundle_manifest_planning", "module_selection"),
        sensitive_input_policy="pain points are reduced to hashes/categories; private details stay local",
        no_go_data_classes=("raw_client_data", "credentials", "tokens", "bank_data", "private_legal_tax_finance"),
        allowed_authority_level="planning_only",
        tests_required=("tests/test_bundle_blueprint_planner.py",),
        client_safe=True,
        report_bridge_summary_allowed=True,
        evidence_basis=(
            "Stage 2 implements a deterministic advisory planner; project_capsule.py remains "
            "stored capsule authority; no GitHub packaging or deployment authority."
        ),
    ),
)


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS module_registry_runs (
  run_id TEXT PRIMARY KEY,
  registry_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  module_count INTEGER NOT NULL DEFAULT 0,
  dependency_count INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  activation_allowed INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  source_basis_json TEXT NOT NULL,
  notes TEXT
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS module_registry_modules (
  module_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  version TEXT NOT NULL DEFAULT '0.1.0',
  display_name TEXT,
  category TEXT NOT NULL,
  world TEXT,
  status TEXT NOT NULL,
  authority_level TEXT NOT NULL,
  allowed_authority_level TEXT,
  risk_level TEXT NOT NULL,
  client_capsule_suitability TEXT NOT NULL,
  client_safe INTEGER NOT NULL DEFAULT 0,
  core_only INTEGER NOT NULL DEFAULT 0,
  report_bridge_summary_allowed INTEGER NOT NULL DEFAULT 1,
  runtime_authority_required INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  operator_review_required INTEGER NOT NULL DEFAULT 0,
  description TEXT NOT NULL,
  capabilities_json TEXT NOT NULL DEFAULT '[]',
  optional_inputs_json TEXT NOT NULL DEFAULT '[]',
  sensitive_input_policy TEXT NOT NULL DEFAULT 'metadata_only_no_private_raw_input',
  no_go_data_classes_json TEXT NOT NULL DEFAULT '[]',
  tests_required_json TEXT NOT NULL DEFAULT '[]',
  evidence_basis TEXT NOT NULL DEFAULT 'seeded_from_repo_a_stage_2_migration_spec',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  run_id TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES module_registry_runs(run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS module_registry_required_inputs (
  input_id TEXT PRIMARY KEY,
  module_id TEXT NOT NULL,
  input_name TEXT NOT NULL,
  required INTEGER NOT NULL DEFAULT 1,
  notes TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (module_id) REFERENCES module_registry_modules(module_id) ON DELETE CASCADE,
  UNIQUE(module_id, input_name)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS module_registry_generated_outputs (
  output_id TEXT PRIMARY KEY,
  module_id TEXT NOT NULL,
  output_name TEXT NOT NULL,
  output_kind TEXT NOT NULL,
  notes TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (module_id) REFERENCES module_registry_modules(module_id) ON DELETE CASCADE,
  UNIQUE(module_id, output_name)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS module_registry_dependencies (
  dependency_id TEXT PRIMARY KEY,
  module_id TEXT NOT NULL,
  depends_on_module_id TEXT NOT NULL,
  dependency_kind TEXT NOT NULL,
  required INTEGER NOT NULL DEFAULT 1,
  notes TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (module_id) REFERENCES module_registry_modules(module_id) ON DELETE CASCADE,
  UNIQUE(module_id, depends_on_module_id, dependency_kind)
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_module_registry_modules_category ON module_registry_modules(category)",
        "CREATE INDEX IF NOT EXISTS idx_module_registry_modules_status ON module_registry_modules(status)",
    )


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _run_migrations(conn: sqlite3.Connection) -> None:
    for column, definition in (
        ("version", "TEXT NOT NULL DEFAULT '0.1.0'"),
        ("display_name", "TEXT"),
        ("world", "TEXT"),
        ("allowed_authority_level", "TEXT"),
        ("client_safe", "INTEGER NOT NULL DEFAULT 0"),
        ("core_only", "INTEGER NOT NULL DEFAULT 0"),
        ("report_bridge_summary_allowed", "INTEGER NOT NULL DEFAULT 1"),
        ("runtime_authority", "INTEGER NOT NULL DEFAULT 0"),
        ("capabilities_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("optional_inputs_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("sensitive_input_policy", "TEXT NOT NULL DEFAULT 'metadata_only_no_private_raw_input'"),
        ("no_go_data_classes_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("tests_required_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("evidence_basis", "TEXT NOT NULL DEFAULT 'seeded_from_repo_a_stage_2_migration_spec'"),
    ):
        _ensure_column(conn, "module_registry_modules", column, definition)


def init_module_registry_schema(db_path: str | Path | None = None) -> str:
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
        _run_migrations(conn)
        conn.commit()
    finally:
        conn.close()
    return path


def module_registry_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_module_registry_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'module_registry_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _validate_seed(seed: ModuleSeed) -> None:
    if seed.status not in MODULE_STATUSES:
        raise ValueError(f"bad module status: {seed.module_id}")
    if seed.authority_level not in AUTHORITY_LEVELS:
        raise ValueError(f"bad authority level: {seed.module_id}")
    if seed.risk_level not in RISK_LEVELS:
        raise ValueError(f"bad risk level: {seed.module_id}")
    if seed.client_capsule_suitability not in CLIENT_SUITABILITY:
        raise ValueError(f"bad client capsule suitability: {seed.module_id}")
    if seed.allowed_authority_level and seed.allowed_authority_level not in AUTHORITY_LEVELS:
        raise ValueError(f"bad allowed authority level: {seed.module_id}")
    if seed.runtime_authority_required or seed.runtime_authority:
        raise ValueError(f"Module Registry v0 does not allow runtime-authority modules: {seed.module_id}")


def _json_tuple(values: tuple[str, ...]) -> str:
    return stable_json(list(values))


def _seed_display_name(seed: ModuleSeed) -> str:
    return seed.display_name or seed.name


def _seed_world(seed: ModuleSeed) -> str:
    return seed.world or seed.category


def _seed_allowed_authority(seed: ModuleSeed) -> str:
    return seed.allowed_authority_level or seed.authority_level


def _seed_client_safe(seed: ModuleSeed) -> bool:
    if seed.client_safe is not None:
        return seed.client_safe
    return seed.client_capsule_suitability in {"high", "medium"} and seed.risk_level != "high"


def seed_module_registry(
    db_path: str | Path | None = None,
    *,
    run_id: str | None = None,
    module_seeds: Iterable[ModuleSeed] = DEFAULT_MODULE_SEEDS,
) -> ModuleRegistryResult:
    path = init_module_registry_schema(db_path)
    seeds = tuple(module_seeds)
    now = utc_now()
    resolved_run_id = run_id or _row_id("modrun", now, len(seeds))
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
INSERT INTO module_registry_runs (
  run_id, registry_version, created_at, source_basis_json, notes
) VALUES (?, ?, ?, ?, ?)
ON CONFLICT(run_id) DO UPDATE SET
  registry_version = excluded.registry_version,
  source_basis_json = excluded.source_basis_json,
  notes = excluded.notes
""".strip(),
            (
                resolved_run_id,
                MODULE_REGISTRY_VERSION,
                now,
                stable_json(
                    {
                        "seeded_modules": len(seeds),
                        "runtime_authority": False,
                        "activation": False,
                        "tool_execution": False,
                    }
                ),
                "Planning registry only; modules selected here are not activated.",
            ),
        )

        seen: set[str] = set()
        for seed in seeds:
            _validate_seed(seed)
            if seed.module_id in seen:
                raise ValueError(f"duplicate module seed: {seed.module_id}")
            seen.add(seed.module_id)
            existing = conn.execute(
                "SELECT created_at FROM module_registry_modules WHERE module_id = ?",
                (seed.module_id,),
            ).fetchone()
            created_at = existing["created_at"] if existing else now
            conn.execute(
                """
INSERT INTO module_registry_modules (
  module_id, name, version, display_name, category, world, status,
  authority_level, allowed_authority_level, risk_level,
  client_capsule_suitability, client_safe, core_only,
  report_bridge_summary_allowed, runtime_authority_required,
  runtime_authority, operator_review_required, description,
  capabilities_json, optional_inputs_json, sensitive_input_policy,
  no_go_data_classes_json, tests_required_json, evidence_basis,
  created_at, updated_at, run_id
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(module_id) DO UPDATE SET
  name = excluded.name,
  version = excluded.version,
  display_name = excluded.display_name,
  category = excluded.category,
  world = excluded.world,
  status = excluded.status,
  authority_level = excluded.authority_level,
  allowed_authority_level = excluded.allowed_authority_level,
  risk_level = excluded.risk_level,
  client_capsule_suitability = excluded.client_capsule_suitability,
  client_safe = excluded.client_safe,
  core_only = excluded.core_only,
  report_bridge_summary_allowed = excluded.report_bridge_summary_allowed,
  runtime_authority_required = excluded.runtime_authority_required,
  runtime_authority = excluded.runtime_authority,
  operator_review_required = excluded.operator_review_required,
  description = excluded.description,
  capabilities_json = excluded.capabilities_json,
  optional_inputs_json = excluded.optional_inputs_json,
  sensitive_input_policy = excluded.sensitive_input_policy,
  no_go_data_classes_json = excluded.no_go_data_classes_json,
  tests_required_json = excluded.tests_required_json,
  evidence_basis = excluded.evidence_basis,
  updated_at = excluded.updated_at,
  run_id = excluded.run_id
""".strip(),
                (
                    seed.module_id,
                    seed.name,
                    seed.version,
                    _seed_display_name(seed),
                    seed.category,
                    _seed_world(seed),
                    seed.status,
                    seed.authority_level,
                    _seed_allowed_authority(seed),
                    seed.risk_level,
                    seed.client_capsule_suitability,
                    1 if _seed_client_safe(seed) else 0,
                    1 if seed.core_only else 0,
                    1 if seed.report_bridge_summary_allowed else 0,
                    1 if seed.runtime_authority_required else 0,
                    1 if seed.runtime_authority else 0,
                    1 if seed.operator_review_required else 0,
                    seed.description,
                    _json_tuple(seed.capabilities),
                    _json_tuple(seed.optional_inputs),
                    seed.sensitive_input_policy,
                    _json_tuple(seed.no_go_data_classes),
                    _json_tuple(seed.tests_required),
                    seed.evidence_basis,
                    created_at,
                    now,
                    resolved_run_id,
                ),
            )
            conn.execute("DELETE FROM module_registry_required_inputs WHERE module_id = ?", (seed.module_id,))
            conn.execute("DELETE FROM module_registry_generated_outputs WHERE module_id = ?", (seed.module_id,))
            conn.execute("DELETE FROM module_registry_dependencies WHERE module_id = ?", (seed.module_id,))
            for input_name in seed.required_inputs:
                conn.execute(
                    """
INSERT INTO module_registry_required_inputs (
  input_id, module_id, input_name, required, notes, created_at
) VALUES (?, ?, ?, 1, 'Planning input metadata only.', ?)
""".strip(),
                    (_row_id("modinput", seed.module_id, input_name), seed.module_id, input_name, now),
                )
            for output_name in seed.generated_outputs:
                output_kind = "generated_read_model" if "generated/read_models" in output_name else "sqlite_or_generated_artifact"
                conn.execute(
                    """
INSERT INTO module_registry_generated_outputs (
  output_id, module_id, output_name, output_kind, notes, created_at
) VALUES (?, ?, ?, ?, 'Generated or ledger output metadata only.', ?)
""".strip(),
                    (
                        _row_id("modoutput", seed.module_id, output_name),
                        seed.module_id,
                        output_name,
                        output_kind,
                        now,
                    ),
                )
            for depends_on in seed.dependencies:
                conn.execute(
                    """
INSERT INTO module_registry_dependencies (
  dependency_id, module_id, depends_on_module_id, dependency_kind, required, notes, created_at
) VALUES (?, ?, ?, 'planning_dependency', 1, 'Selected for planning context; no activation implied.', ?)
""".strip(),
                    (_row_id("moddep", seed.module_id, depends_on), seed.module_id, depends_on, now),
                )

        rows = conn.execute("SELECT * FROM module_registry_modules").fetchall()
        dependency_count = conn.execute("SELECT COUNT(*) FROM module_registry_dependencies").fetchone()[0]
        conn.execute(
            """
UPDATE module_registry_runs
SET completed_at = ?, module_count = ?, dependency_count = ?
WHERE run_id = ?
""".strip(),
            (utc_now(), len(rows), dependency_count, resolved_run_id),
        )
        conn.commit()
        return ModuleRegistryResult(
            run_id=resolved_run_id,
            db_path=path,
            module_count=len(rows),
            dependency_count=dependency_count,
        )
    finally:
        conn.close()


def _latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id
FROM module_registry_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row["run_id"] if row else None


def _module_rows(conn: sqlite3.Connection, where: str = "1=1", params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
SELECT module_id, name, version, display_name, category, world, status,
       authority_level, allowed_authority_level, risk_level,
       client_capsule_suitability, client_safe, core_only,
       report_bridge_summary_allowed, runtime_authority_required,
       runtime_authority, operator_review_required, description,
       capabilities_json, optional_inputs_json, sensitive_input_policy,
       no_go_data_classes_json, tests_required_json, evidence_basis
FROM module_registry_modules
WHERE {where}
ORDER BY category, module_id
""".strip(),
        params,
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        for json_key, output_key in (
            ("capabilities_json", "capabilities"),
            ("optional_inputs_json", "optional_inputs"),
            ("no_go_data_classes_json", "no_go_data_classes"),
            ("tests_required_json", "tests_required"),
        ):
            try:
                item[output_key] = tuple(json.loads(item.get(json_key) or "[]"))
            except json.JSONDecodeError:
                item[output_key] = ()
        item["client_safe"] = bool(item["client_safe"])
        item["core_only"] = bool(item["core_only"])
        item["report_bridge_summary_allowed"] = bool(item["report_bridge_summary_allowed"])
        item["runtime_authority_required"] = bool(item["runtime_authority_required"])
        item["runtime_authority"] = bool(item["runtime_authority"])
        item["operator_review_required"] = bool(item["operator_review_required"])
        result.append(item)
    return result


def _dependencies(conn: sqlite3.Connection, module_id: str | None = None) -> list[dict[str, Any]]:
    where = "1=1"
    params: tuple[Any, ...] = ()
    if module_id:
        where = "module_id = ?"
        params = (module_id,)
    rows = conn.execute(
        f"""
SELECT module_id, depends_on_module_id, dependency_kind, required, notes
FROM module_registry_dependencies
WHERE {where}
ORDER BY module_id, depends_on_module_id
""".strip(),
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def build_module_registry_report(
    db_path: str | Path | None = None,
    *,
    run_id: str | None = None,
    section: str = "summary",
    category: str | None = None,
) -> dict[str, Any]:
    path = init_module_registry_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_run_id = run_id or _latest_run_id(conn)
        if not resolved_run_id:
            return {"status": "no_runs", "section": section, "items": []}
        run = conn.execute(
            "SELECT * FROM module_registry_runs WHERE run_id = ?",
            (resolved_run_id,),
        ).fetchone()
        if section == "summary":
            modules = _module_rows(conn)
        elif section == "modules":
            modules = _module_rows(conn)
        elif section == "category":
            modules = _module_rows(conn, "category = ?", (category or "",))
        elif section == "client-capsule":
            modules = _module_rows(conn, "client_capsule_suitability IN ('high','medium')")
        elif section == "approved":
            modules = _module_rows(conn, "status IN ('approved','draft','blocked','deprecated')")
        elif section == "dependencies":
            modules = []
        else:
            raise ValueError(f"unknown module registry report: {section}")
        all_rows = _module_rows(conn)
        counts = {
            "category": dict(sorted(Counter(row["category"] for row in all_rows).items())),
            "status": dict(sorted(Counter(row["status"] for row in all_rows).items())),
            "authority_level": dict(sorted(Counter(row["authority_level"] for row in all_rows).items())),
            "client_capsule_suitability": dict(
                sorted(Counter(row["client_capsule_suitability"] for row in all_rows).items())
            ),
            "client_safe": dict(sorted(Counter(str(row["client_safe"]).lower() for row in all_rows).items())),
            "core_only": dict(sorted(Counter(str(row["core_only"]).lower() for row in all_rows).items())),
        }
        return {
            "status": "ok",
            "section": section,
            "run_id": resolved_run_id,
            "run": dict(run),
            "counts": counts,
            "items": modules if section != "dependencies" else _dependencies(conn),
            "dependencies": _dependencies(conn),
        }
    finally:
        conn.close()


def format_module_registry_report(report: dict[str, Any]) -> str:
    if report.get("status") == "no_runs":
        return "Module Registry v0\n\nNo module registry runs are recorded."
    run = report["run"]
    lines = [
        "Module Registry v0",
        "",
        f"Run: `{report['run_id']}`",
        f"Modules: {run['module_count']}",
        f"Dependencies: {run['dependency_count']}",
        f"Runtime authority: {bool(run['runtime_authority'])}",
        f"Activation allowed: {bool(run['activation_allowed'])}",
        "",
        "Counts:",
    ]
    for name, counts in report["counts"].items():
        rendered = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        lines.append(f"- {name}: {rendered or 'none'}")
    lines.append("")
    lines.append("Items:")
    for item in report.get("items") or []:
        if "module_id" in item and "depends_on_module_id" in item:
            lines.append(f"- {item['module_id']} -> {item['depends_on_module_id']} ({item['dependency_kind']})")
        else:
            lines.append(
                f"- {item['module_id']} ({item['category']}, {item['status']}, "
                f"{item['allowed_authority_level'] or item['authority_level']}, "
                f"client_safe={str(item['client_safe']).lower()}, "
                f"core_only={str(item['core_only']).lower()})"
            )
    lines.extend(
        [
            "",
            "Boundary:",
            "- Registry rows are planning metadata only.",
            "- Module selection does not activate modules or grant runtime/tool/network authority.",
        ]
    )
    return "\n".join(lines)


def build_approved_module_registry_read_model(
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    seed_module_registry(db_path=db_path)
    report = build_module_registry_report(db_path=db_path, section="approved")
    items = report.get("items", [])
    return {
        "schema_version": APPROVED_MODULE_READ_MODEL_VERSION,
        "read_model_version": APPROVED_MODULE_READ_MODEL_VERSION,
        "generated_at": utc_now(),
        "source_ledger_namespace": "module_registry_*",
        "module_count": len(items),
        "counts": report.get("counts", {}),
        "modules": [
            {
                "module_id": item["module_id"],
                "version": item["version"],
                "display_name": item["display_name"] or item["name"],
                "category": item["category"],
                "world": item["world"] or item["category"],
                "capabilities": list(item["capabilities"]),
                "required_inputs": [
                    row["input_name"]
                    for row in _module_required_inputs(db_path=db_path, module_id=item["module_id"])
                ],
                "optional_inputs": list(item["optional_inputs"]),
                "sensitive_input_policy": item["sensitive_input_policy"],
                "no_go_data_classes": list(item["no_go_data_classes"]),
                "allowed_authority_level": item["allowed_authority_level"] or item["authority_level"],
                "dependencies": [
                    dep["depends_on_module_id"]
                    for dep in report.get("dependencies", [])
                    if dep["module_id"] == item["module_id"]
                ],
                "tests_required": list(item["tests_required"]),
                "client_safe": item["client_safe"],
                "core_only": item["core_only"],
                "report_bridge_summary_allowed": item["report_bridge_summary_allowed"],
                "status": item["status"],
                "evidence_basis": item["evidence_basis"],
                "runtime_authority": item["runtime_authority"],
                "operator_review_required": item["operator_review_required"],
            }
            for item in items
        ],
        "no_authority_flags": {
            "runtime_authority": False,
            "activation_allowed": False,
            "tool_execution_allowed": False,
            "network_authority": False,
            "external_api_allowed": False,
            "model_call_allowed": False,
            "send_allowed": False,
            "client_deployment_allowed": False,
        },
        "runtime_authority": False,
        "activation_allowed": False,
        "tool_execution_allowed": False,
        "network_authority": False,
        "external_api_allowed": False,
        "model_call_allowed": False,
        "send_allowed": False,
        "client_deployment_allowed": False,
    }


def _module_required_inputs(
    *,
    db_path: str | Path | None = None,
    module_id: str,
) -> list[dict[str, Any]]:
    path = init_module_registry_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return [
            dict(row)
            for row in conn.execute(
                """
SELECT input_name, required, notes
FROM module_registry_required_inputs
WHERE module_id = ?
ORDER BY input_name
""".strip(),
                (module_id,),
            ).fetchall()
        ]
    finally:
        conn.close()


def format_approved_module_registry_read_model(read_model: dict[str, Any]) -> str:
    lines = [
        "# Approved Module Registry Read-Model v0",
        "",
        "What this is:",
        "- A generated read-model over local approved-module planning metadata.",
        "",
        "What this is not:",
        "- It is not runtime activation, deployment, external send, tool execution, model execution, or client data access.",
        "",
        "Summary:",
        f"- Modules: {read_model['module_count']}.",
        "",
        "Modules:",
    ]
    for item in read_model["modules"]:
        lines.append(
            f"- `{item['module_id']}` status=`{item['status']}` authority=`{item['allowed_authority_level']}` "
            f"client_safe=`{str(item['client_safe']).lower()}` core_only=`{str(item['core_only']).lower()}`"
        )
    lines.extend(
        [
            "",
            "Boundary:",
            "- `runtime_authority=false`; `deployment_allowed=false`; `send_allowed=false`.",
            "- Client/project bundles may use these records only as local planning metadata.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_approved_module_registry_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(__file__).resolve().parent / root
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_approved_module_registry_read_model(db_path=db_path)
    json_path = root / APPROVED_JSON_EXPORT_NAME
    operator_path = root / APPROVED_OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_approved_module_registry_read_model(read_model), encoding="utf-8")
    return {
        "export_version": APPROVED_MODULE_READ_MODEL_VERSION,
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "module_count": read_model["module_count"],
        **read_model["no_authority_flags"],
    }
