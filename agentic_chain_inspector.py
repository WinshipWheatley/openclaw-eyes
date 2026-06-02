"""Agentic Chain Inspector V0.

Read-only inspector for OpenClaw's message -> gate -> package -> worker ->
receipt chain and local SQLite fragmentation. It does not consolidate SQLite,
run loops, spawn agents, call providers, send email, open browser/Gmail/Coupa,
mutate ledgers/workbooks, export PDFs, submit portals, or mark paid/sent.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Agentic Chain Inspector.md")
DEFAULT_INSPECTOR_SQLITE_PATH = Path("generated/system_knowledge/agentic_chain_inspector.sqlite")

SCHEMA_VERSION = "agentic_chain_inspector_v0"
READ_MODEL_ID = "agentic_chain_inspector"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
CONTRACT_STATUS = "AGENTIC_CHAIN_INSPECTOR_READY"

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "sent": False,
    "paid": False,
}

DEFAULT_SQLITE_ROOTS = (
    Path("generated/system_knowledge"),
    Path(".openclaw"),
    Path("/mnt/e/openclaw/generated/system_knowledge"),
    Path("/mnt/e/openclaw/.openclaw"),
)

GATE_BLUEPRINT = (
    {
        "sequence": 1,
        "gate_id": "human_message",
        "gate_name": "Human message",
        "posture": "live",
        "owning_files": (
            "workflow_package_request_consumer.py",
            "cassandra_telegram_dryrun_inbox.py",
            "openclaw_request_processor.py",
            "openclaw_request_response_service.py",
        ),
        "sqlite_tables": ("package_inputs",),
        "tests": (
            "tests/test_workflow_package_request_consumer.py",
            "tests/test_cassandra_telegram_dryrun_inbox.py",
        ),
    },
    {
        "sequence": 2,
        "gate_id": "privacy_pii_gate",
        "gate_name": "PII/privacy gate",
        "posture": "dry-run",
        "owning_files": ("workflow_package_queue.py", "workflow_package_request_consumer.py"),
        "sqlite_tables": ("privacy_gate_results",),
        "tests": ("tests/test_workflow_package_queue.py",),
    },
    {
        "sequence": 3,
        "gate_id": "intent_lm_gate",
        "gate_name": "Intent/LM gate",
        "posture": "dry-run",
        "owning_files": (
            "workflow_package_queue.py",
            "intent_ingest_gate.py",
            "role_package_gate.py",
            "system_question_answer.py",
        ),
        "sqlite_tables": ("intent_classification_results",),
        "tests": ("tests/test_workflow_package_queue.py", "tests/test_system_question_answer.py"),
    },
    {
        "sequence": 4,
        "gate_id": "sqlite_package_gate",
        "gate_name": "SQLite/package gate",
        "posture": "dry-run",
        "owning_files": ("workflow_package_queue.py", "openclaw_lm_child_package_gate.py"),
        "sqlite_tables": ("packages", "package_inputs"),
        "tests": ("tests/test_workflow_package_queue.py", "tests/test_openclaw_lm_child_package_gate.py"),
    },
    {
        "sequence": 5,
        "gate_id": "workflow_package_compiler",
        "gate_name": "Workflow package compiler",
        "posture": "dry-run",
        "owning_files": ("workflow_package_queue.py", "role_package_gate.py"),
        "sqlite_tables": ("packages",),
        "tests": ("tests/test_workflow_package_queue.py", "tests/test_role_package_gate.py"),
    },
    {
        "sequence": 6,
        "gate_id": "capability_provider_gate",
        "gate_name": "Capability/provider gate",
        "posture": "dry-run",
        "owning_files": (
            "workflow_package_queue.py",
            "operator_assist_provider_registry.py",
            "automation_permission_registry.py",
        ),
        "sqlite_tables": ("capability_gate_results",),
        "tests": ("tests/test_workflow_package_queue.py",),
    },
    {
        "sequence": 7,
        "gate_id": "lm2_child_cage",
        "gate_name": "LM2/child cage",
        "posture": "contract-only",
        "owning_files": ("openclaw_lm_child_package_gate.py", "role_package_gate.py", "live_lm_activation_requirements.py"),
        "sqlite_tables": ("lm_packages", "child_package_requests", "package_gate_decisions"),
        "tests": ("tests/test_openclaw_lm_child_package_gate.py", "tests/test_role_package_gate.py"),
    },
    {
        "sequence": 8,
        "gate_id": "worker",
        "gate_name": "Worker",
        "posture": "dry-run",
        "owning_files": ("workflow_package_queue.py", "chief_offline_worker_adapter.py", "cassandra_clara_offline_worker_adapter.py"),
        "sqlite_tables": ("worker_assignments", "worker_results"),
        "tests": ("tests/test_workflow_package_queue.py",),
    },
    {
        "sequence": 9,
        "gate_id": "result_receipt",
        "gate_name": "Result receipt",
        "posture": "dry-run",
        "owning_files": ("workflow_package_queue.py", "workflow_package_request_consumer.py", "cassandra_telegram_dryrun_inbox.py"),
        "sqlite_tables": ("worker_results",),
        "tests": ("tests/test_workflow_package_request_consumer.py", "tests/test_cassandra_telegram_dryrun_inbox.py"),
    },
    {
        "sequence": 10,
        "gate_id": "operator_review_gate",
        "gate_name": "Operator review gate",
        "posture": "live",
        "owning_files": ("workflow_package_queue.py", "st_annes_work_log_review.py"),
        "sqlite_tables": ("operator_review_receipts", "review_actions"),
        "tests": ("tests/test_workflow_package_queue.py", "tests/test_st_annes_work_log_review.py"),
    },
    {
        "sequence": 11,
        "gate_id": "business_action_gate",
        "gate_name": "Business action gate",
        "posture": "dry-run",
        "owning_files": ("workflow_package_queue.py", "guardian_protected_access_gate_spec.py"),
        "sqlite_tables": ("business_action_gate_results",),
        "tests": ("tests/test_workflow_package_queue.py",),
    },
    {
        "sequence": 12,
        "gate_id": "final_read_model_ui_response",
        "gate_name": "Final read model/UI response",
        "posture": "live",
        "owning_files": (
            "workflow_package_request_consumer.py",
            "operator_human_readability_surface.py",
            "operator_conversation_journal.py",
        ),
        "sqlite_tables": ("journal_entries", "operator_action_events"),
        "tests": (
            "tests/test_workflow_package_request_consumer.py",
            "tests/test_operator_human_readability_surface.py",
        ),
    },
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _path_exists(path: str) -> bool:
    return _rooted(Path(path)).exists()


def _iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="seconds")


def _readable_sqlite_metadata(path: Path) -> dict[str, Any]:
    uri = "file:" + path.as_posix() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        tables = [str(row[0]) for row in rows]
        row_counts: dict[str, int | str] = {}
        schema_columns: dict[str, list[str]] = {}
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            try:
                row_counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0])
            except sqlite3.DatabaseError as exc:
                row_counts[table] = f"unavailable:{exc.__class__.__name__}"
            try:
                schema_columns[table] = [
                    str(col[1])
                    for col in conn.execute(f"PRAGMA table_info({quoted})").fetchall()
                ]
            except sqlite3.DatabaseError:
                schema_columns[table] = []
        return {
            "tables": tables,
            "row_counts": row_counts,
            "schema_columns": schema_columns,
            "open_status": "ok",
            "error": "",
        }
    finally:
        conn.close()


def infer_purpose(path: Path, tables: Iterable[str]) -> str:
    text = path.as_posix().lower()
    table_text = " ".join(tables).lower()
    if "ledger" in text:
        return "business ledger or test ledger"
    if "workflow_package_queue" in text or "packages" in table_text:
        return "workflow package queue and gate registry"
    if "operator_conversation_journal" in text or "journal" in table_text:
        return "operator conversation or event journal"
    if "operator_action" in text:
        return "operator action event journal"
    if "test_harness" in text or "pytest" in text:
        return "test harness or pytest fixture database"
    if "token_vault" in text:
        return "privacy token vault"
    if "invoice" in text:
        return "invoice status or invoice review evidence"
    if "lm_child" in text or "delegated_package" in text or "shadow_lm" in text or "lm_shadow" in text:
        return "LM/child package gate test or contract state"
    if "sentinel" in text or "health" in text or "service" in text:
        return "system health, sentinel, or service status"
    if "memory" in text:
        return "agent memory store"
    return "local OpenClaw system knowledge"


def canonical_guess(path: Path) -> str:
    text = path.as_posix().lower()
    if ".openclaw/business_ops/ledger.sqlite" in text:
        return "business_ledger_canonical_never_mix"
    if ".openclaw/privacy/token_vault.sqlite" in text:
        return "privacy_vault_canonical_isolated"
    if "workflow_package_queue.sqlite" in text:
        return "canonical_candidate_for_package_queue"
    if "operator_conversation_journal.sqlite" in text:
        return "canonical_candidate_for_operator_conversation_history"
    if ".openclaw/tmp/" in text or "pytest" in text:
        return "noncanonical_test_or_tmp_artifact"
    if "generated/system_knowledge" in text:
        return "read_model_evidence_or_contract_state"
    if ".openclaw/test_harness" in text:
        return "test_harness_state_keep_isolated"
    return "noncanonical_or_unknown"


def consolidation_risk(path: Path, purpose: str, tables: Iterable[str]) -> str:
    text = path.as_posix().lower()
    table_text = " ".join(tables).lower()
    if "ledger" in text:
        return "never_mix_business_ledger"
    if ".openclaw/tmp/" in text or "pytest" in text:
        return "low_ignore_tmp_test_artifact"
    if "package" in text or "packages" in table_text or "gate" in text:
        return "high_duplicate_package_or_gate_concept"
    if "journal" in purpose or "event" in purpose or "sentinel" in text:
        return "medium_duplicate_event_or_status_store"
    if "test_harness" in text:
        return "medium_test_harness_keep_isolated"
    if "token_vault" in text:
        return "never_mix_privacy_vault"
    return "medium_unknown_until_owner_named"


def root_group_for_path(path: Path) -> str:
    text = path.as_posix()
    if text.startswith("/mnt/e/openclaw/generated/system_knowledge"):
        return "bridge_generated_system_knowledge"
    if text.startswith("/mnt/e/openclaw/.openclaw"):
        return "bridge_openclaw_state"
    if text.startswith(str((ROOT / "generated/system_knowledge").as_posix())) or text.startswith("generated/system_knowledge"):
        return "generated_system_knowledge"
    if text.startswith(str((ROOT / ".openclaw").as_posix())) or text.startswith(".openclaw"):
        return "openclaw_state"
    return "other_known_system_path"


def discover_sqlite_paths(sqlite_roots: Iterable[Path] = DEFAULT_SQLITE_ROOTS) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    for root in sqlite_roots:
        resolved = _rooted(root)
        if not resolved.exists():
            continue
        for path in sorted(resolved.rglob("*.sqlite")):
            if path.is_file():
                key = path.resolve().as_posix()
                if key not in seen:
                    seen.add(key)
                    paths.append(path)
    return paths


def inspect_sqlite_databases(sqlite_roots: Iterable[Path] = DEFAULT_SQLITE_ROOTS) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for path in discover_sqlite_paths(sqlite_roots):
        stat = path.stat()
        tables: list[str] = []
        row_counts: dict[str, int | str] = {}
        schema_columns: dict[str, list[str]] = {}
        open_status = "ok"
        error = ""
        try:
            metadata = _readable_sqlite_metadata(path)
            tables = list(metadata["tables"])
            row_counts = dict(metadata["row_counts"])
            schema_columns = dict(metadata["schema_columns"])
        except sqlite3.DatabaseError as exc:
            open_status = "error"
            error = f"{exc.__class__.__name__}: {exc}"
        purpose = infer_purpose(path, tables)
        inventory.append(
            {
                "path": path.as_posix(),
                "root_group": root_group_for_path(path),
                "purpose": purpose,
                "tables": tables,
                "row_counts": row_counts,
                "schema_columns": schema_columns,
                "last_modified": _iso_from_timestamp(stat.st_mtime),
                "size_bytes": stat.st_size,
                "canonical_noncanonical_guess": canonical_guess(path),
                "consolidation_risk": consolidation_risk(path, purpose, tables),
                "open_status": open_status,
                "error": error,
            }
        )
    return inventory


def sqlite_table_index(sqlite_inventory: list[Mapping[str, Any]]) -> set[str]:
    tables: set[str] = set()
    for item in sqlite_inventory:
        for table in item.get("tables") or []:
            tables.add(str(table))
    return tables


def build_gate_chain(sqlite_inventory: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    tables = sqlite_table_index(sqlite_inventory)
    chain: list[dict[str, Any]] = []
    for gate in GATE_BLUEPRINT:
        owning_files = list(gate["owning_files"])
        test_files = list(gate["tests"])
        sqlite_tables = list(gate["sqlite_tables"])
        chain.append(
            {
                "sequence": gate["sequence"],
                "gate_id": gate["gate_id"],
                "gate_name": gate["gate_name"],
                "exists": any(_path_exists(path) for path in owning_files),
                "posture": gate["posture"],
                "owning_files": owning_files,
                "sqlite_tracked": any(table in tables for table in sqlite_tables),
                "sqlite_tables": sqlite_tables,
                "tests_present": any(_path_exists(path) for path in test_files),
                "test_files": test_files,
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            }
        )
    return chain


def fragmentation_risks(sqlite_inventory: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    package_paths = [
        str(item["path"])
        for item in sqlite_inventory
        if "package" in str(item.get("purpose", "")).lower()
        or "package" in str(item.get("path", "")).lower()
        or any("package" in str(table).lower() for table in item.get("tables") or [])
    ]
    journal_paths = [
        str(item["path"])
        for item in sqlite_inventory
        if any(term in str(item.get("purpose", "")).lower() for term in ("journal", "event", "sentinel", "status"))
    ]
    request_response_paths = [
        str(item["path"])
        for item in sqlite_inventory
        if any(term in str(item.get("path", "")).lower() for term in ("request", "response", "invoice_review_state"))
    ]
    generated_status_paths = [
        str(item["path"])
        for item in sqlite_inventory
        if "generated/system_knowledge" in str(item.get("path", "")).lower()
    ]
    test_harness_paths = [
        str(item["path"])
        for item in sqlite_inventory
        if any(term in str(item.get("path", "")).lower() for term in ("test_harness", "pytest", "/tmp/"))
    ]
    ledger_paths = [
        str(item["path"])
        for item in sqlite_inventory
        if "ledger" in str(item.get("path", "")).lower()
    ]
    return [
        {
            "risk_id": "duplicate_package_concepts",
            "severity": "high",
            "summary": "Package, gate, and delegated/LM package concepts exist in multiple SQLite stores and generated contracts.",
            "affected_path_count": len(package_paths),
            "sample_paths": package_paths[:20],
        },
        {
            "risk_id": "duplicate_event_journals",
            "severity": "medium",
            "summary": "Operator events, conversation history, sentinels, and service status stores can drift if treated as separate truth stores.",
            "affected_path_count": len(journal_paths),
            "sample_paths": journal_paths[:20],
        },
        {
            "risk_id": "request_response_status_stores",
            "severity": "medium",
            "summary": "Request/response and review status appears across bridge files, package queue state, and invoice-review state.",
            "affected_path_count": len(request_response_paths),
            "sample_paths": request_response_paths[:20],
        },
        {
            "risk_id": "generated_status_dbs",
            "severity": "medium",
            "summary": "Generated system-knowledge databases should remain read-model/evidence stores until canonical ownership is declared.",
            "affected_path_count": len(generated_status_paths),
            "sample_paths": generated_status_paths[:20],
        },
        {
            "risk_id": "test_harness_dbs",
            "severity": "low",
            "summary": "Test harness and pytest databases are numerous and should be excluded from production consolidation.",
            "affected_path_count": len(test_harness_paths),
            "sample_paths": test_harness_paths[:20],
        },
        {
            "risk_id": "business_ledger_exclusion",
            "severity": "critical",
            "summary": "Business ledger databases must not be mixed with package, test, or agent-state consolidation.",
            "affected_path_count": len(ledger_paths),
            "sample_paths": ledger_paths[:20],
        },
    ]


def recommendations(sqlite_inventory: list[Mapping[str, Any]]) -> list[dict[str, str]]:
    del sqlite_inventory
    return [
        {
            "recommendation_id": "consolidate_package_event_index_first",
            "category": "consolidate_first",
            "recommendation": "Create a single package-event index that references workflow_package_queue, request/response receipts, and operator_conversation_journal without moving business ledger data.",
        },
        {
            "recommendation_id": "leave_business_ledger_isolated",
            "category": "leave_isolated",
            "recommendation": "Keep .openclaw/business_ops/ledger.sqlite and all ledger backups out of package/agent consolidation.",
        },
        {
            "recommendation_id": "leave_token_vault_isolated",
            "category": "leave_isolated",
            "recommendation": "Keep token_vault and privacy stores isolated; reference only protected hashes or token refs.",
        },
        {
            "recommendation_id": "keep_test_harness_as_evidence",
            "category": "read_only_evidence",
            "recommendation": "Treat .openclaw/test_harness and .openclaw/tmp pytest databases as read-only evidence or disposable fixtures, not production truth.",
        },
        {
            "recommendation_id": "do_not_consolidate_generated_status_before_owner_map",
            "category": "defer",
            "recommendation": "Do not merge generated status databases until each has a declared canonical owner and migration target.",
        },
        {
            "recommendation_id": "never_mix_ledger_with_agent_memory",
            "category": "never_mix",
            "recommendation": "Never mix business ledger truth with agent memory, package queues, test harnesses, or generated read-model status stores.",
        },
    ]


def build_read_model(
    *,
    sqlite_roots: Iterable[Path] = DEFAULT_SQLITE_ROOTS,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    sqlite_inventory = inspect_sqlite_databases(sqlite_roots)
    gate_chain = build_gate_chain(sqlite_inventory)
    risks = fragmentation_risks(sqlite_inventory)
    recs = recommendations(sqlite_inventory)
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": CONTRACT_STATUS,
        "purpose": "Read-only map of OpenClaw's agentic message/gate/package/worker/receipt chain and SQLite inventory.",
        "mode": "read_only_inventory",
        "sqlite_roots_scanned": [_rooted(path).as_posix() for path in sqlite_roots if _rooted(path).exists()],
        "gate_chain": gate_chain,
        "sqlite_inventory_count": len(sqlite_inventory),
        "sqlite_inventory": sqlite_inventory,
        "fragmentation_risks": risks,
        "recommendations": recs,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "read_only_inventory": True,
            "sqlite_consolidation_performed": False,
            "sqlite_mutation_performed_except_inspector_db": False,
            "gate_count": len(gate_chain),
            "sqlite_inventory_count": len(sqlite_inventory),
            "fragmentation_risk_count": len(risks),
            "recommendation_count": len(recs),
            "email_send_performed": False,
            "ledger_mutation_performed": False,
            "browser_access_performed": False,
            "gmail_access_performed": False,
            "coupa_access_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "agents_spawned": False,
            "loops_run": False,
            "authority_flags_all_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "unsafe_true_grants_absent": True,
        },
    }


def inspector_sqlite_schema() -> str:
    return """
CREATE TABLE IF NOT EXISTS gate_chain (
  gate_id TEXT PRIMARY KEY,
  sequence INTEGER NOT NULL,
  gate_name TEXT NOT NULL,
  exists_flag INTEGER NOT NULL,
  posture TEXT NOT NULL,
  owning_files_json TEXT NOT NULL,
  sqlite_tracked INTEGER NOT NULL,
  tests_present INTEGER NOT NULL,
  authority_boundary_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS database_inventory (
  path TEXT PRIMARY KEY,
  root_group TEXT NOT NULL,
  purpose TEXT NOT NULL,
  tables_json TEXT NOT NULL,
  row_counts_json TEXT NOT NULL,
  last_modified TEXT NOT NULL,
  canonical_noncanonical_guess TEXT NOT NULL,
  consolidation_risk TEXT NOT NULL,
  open_status TEXT NOT NULL,
  error TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fragmentation_risks (
  risk_id TEXT PRIMARY KEY,
  severity TEXT NOT NULL,
  summary TEXT NOT NULL,
  affected_path_count INTEGER NOT NULL,
  sample_paths_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recommendations (
  recommendation_id TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  recommendation TEXT NOT NULL
);
""".strip() + "\n"


def write_inspector_sqlite(sqlite_path: Path, read_model: Mapping[str, Any]) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.executescript(inspector_sqlite_schema())
        conn.execute("DELETE FROM gate_chain")
        conn.execute("DELETE FROM database_inventory")
        conn.execute("DELETE FROM fragmentation_risks")
        conn.execute("DELETE FROM recommendations")
        for gate in read_model["gate_chain"]:
            conn.execute(
                """
                INSERT INTO gate_chain (
                  gate_id, sequence, gate_name, exists_flag, posture, owning_files_json,
                  sqlite_tracked, tests_present, authority_boundary_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    gate["gate_id"],
                    int(gate["sequence"]),
                    gate["gate_name"],
                    int(bool(gate["exists"])),
                    gate["posture"],
                    stable_json(gate["owning_files"]),
                    int(bool(gate["sqlite_tracked"])),
                    int(bool(gate["tests_present"])),
                    stable_json(gate["authority_boundary"]),
                ),
            )
        for item in read_model["sqlite_inventory"]:
            conn.execute(
                """
                INSERT INTO database_inventory (
                  path, root_group, purpose, tables_json, row_counts_json, last_modified,
                  canonical_noncanonical_guess, consolidation_risk, open_status, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["path"],
                    item["root_group"],
                    item["purpose"],
                    stable_json(item["tables"]),
                    stable_json(item["row_counts"]),
                    item["last_modified"],
                    item["canonical_noncanonical_guess"],
                    item["consolidation_risk"],
                    item["open_status"],
                    item["error"],
                ),
            )
        for risk in read_model["fragmentation_risks"]:
            conn.execute(
                """
                INSERT INTO fragmentation_risks (
                  risk_id, severity, summary, affected_path_count, sample_paths_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    risk["risk_id"],
                    risk["severity"],
                    risk["summary"],
                    int(risk["affected_path_count"]),
                    stable_json(risk["sample_paths"]),
                ),
            )
        for rec in read_model["recommendations"]:
            conn.execute(
                "INSERT INTO recommendations (recommendation_id, category, recommendation) VALUES (?, ?, ?)",
                (rec["recommendation_id"], rec["category"], rec["recommendation"]),
            )
        conn.commit()
    finally:
        conn.close()


def build_wiki(read_model: Mapping[str, Any], inspector_sqlite_path: Path) -> str:
    lines = [
        "# Agentic Chain Inspector",
        "",
        f"Status: `{CONTRACT_STATUS}`",
        "",
        "This is a read-only map of OpenClaw's message -> gate -> package -> worker -> receipt chain plus a SQLite inventory. It does not consolidate databases.",
        "",
        f"SQLite DBs inventoried: `{read_model['sqlite_inventory_count']}`",
        f"Inspector SQLite: `{_rooted(inspector_sqlite_path).as_posix()}`",
        "",
        "## Gate Chain",
        "",
    ]
    for gate in read_model["gate_chain"]:
        lines.append(
            f"{gate['sequence']}. `{gate['gate_id']}` - {gate['posture']}, exists={gate['exists']}, sqlite_tracked={gate['sqlite_tracked']}, tests={gate['tests_present']}"
        )
    lines.extend(["", "## Top Fragmentation Risks", ""])
    for risk in read_model["fragmentation_risks"]:
        lines.append(
            f"- `{risk['risk_id']}` ({risk['severity']}): {risk['summary']} Affected paths: {risk['affected_path_count']}."
        )
    lines.extend(["", "## Recommendations", ""])
    for rec in read_model["recommendations"]:
        lines.append(f"- `{rec['category']}`: {rec['recommendation']}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No SQLite consolidation.",
            "- No business ledger mutation.",
            "- No email, browser, Gmail, Coupa, workbook, PDF, submit, paid, agent spawn, or loop execution.",
            "- The business ledger must remain excluded from agent/package/test consolidation.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_agentic_chain_inspector(
    *,
    sqlite_roots: Iterable[Path] = DEFAULT_SQLITE_ROOTS,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    inspector_sqlite_path: Path = DEFAULT_INSPECTOR_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(sqlite_roots=sqlite_roots, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    local_path = export_root / JSON_EXPORT_NAME
    local_path.write_text(stable_json(read_model), encoding="utf-8")

    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_file = bridge_export_root / JSON_EXPORT_NAME
        bridge_file.write_text(stable_json(read_model), encoding="utf-8")
        bridge_path = bridge_file.as_posix()

    write_inspector_sqlite(inspector_sqlite_path, read_model)

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model, inspector_sqlite_path), encoding="utf-8")
    return {
        "status": CONTRACT_STATUS,
        "read_model_path": local_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
        "inspector_sqlite_path": _rooted(inspector_sqlite_path).as_posix(),
        "sqlite_inventory_count": str(read_model["sqlite_inventory_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Agentic Chain Inspector V0.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--inspector-sqlite-path", default=str(DEFAULT_INSPECTOR_SQLITE_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--sqlite-root", action="append", dest="sqlite_roots")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    sqlite_roots = tuple(Path(item) for item in args.sqlite_roots) if args.sqlite_roots else DEFAULT_SQLITE_ROOTS
    result = export_agentic_chain_inspector(
        sqlite_roots=sqlite_roots,
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        inspector_sqlite_path=Path(args.inspector_sqlite_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
