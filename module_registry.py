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

MODULE_STATUSES = {"available_planning", "experimental", "future_gated", "deprecated"}
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
  category TEXT NOT NULL,
  status TEXT NOT NULL,
  authority_level TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  client_capsule_suitability TEXT NOT NULL,
  runtime_authority_required INTEGER NOT NULL DEFAULT 0,
  operator_review_required INTEGER NOT NULL DEFAULT 0,
  description TEXT NOT NULL,
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
    if seed.runtime_authority_required:
        raise ValueError(f"Module Registry v0 does not allow runtime-authority modules: {seed.module_id}")


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
  module_id, name, category, status, authority_level, risk_level,
  client_capsule_suitability, runtime_authority_required,
  operator_review_required, description, created_at, updated_at, run_id
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(module_id) DO UPDATE SET
  name = excluded.name,
  category = excluded.category,
  status = excluded.status,
  authority_level = excluded.authority_level,
  risk_level = excluded.risk_level,
  client_capsule_suitability = excluded.client_capsule_suitability,
  runtime_authority_required = excluded.runtime_authority_required,
  operator_review_required = excluded.operator_review_required,
  description = excluded.description,
  updated_at = excluded.updated_at,
  run_id = excluded.run_id
""".strip(),
                (
                    seed.module_id,
                    seed.name,
                    seed.category,
                    seed.status,
                    seed.authority_level,
                    seed.risk_level,
                    seed.client_capsule_suitability,
                    1 if seed.runtime_authority_required else 0,
                    1 if seed.operator_review_required else 0,
                    seed.description,
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
SELECT module_id, name, category, status, authority_level, risk_level,
       client_capsule_suitability, runtime_authority_required,
       operator_review_required, description
FROM module_registry_modules
WHERE {where}
ORDER BY category, module_id
""".strip(),
        params,
    ).fetchall()
    return [dict(row) for row in rows]


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
                f"- {item['module_id']} ({item['category']}, {item['status']}, {item['authority_level']}, suitability={item['client_capsule_suitability']})"
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
