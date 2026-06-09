"""OpenClaw Make It So Objective Loop V0.

Turns repeat capability blockers into scoped objective enablement work. This
module does not execute protected production actions, spawn workers, push/merge,
invoke models, open Gmail/browser/Coupa, or trust raw authority grants.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import capability_authority_loop
import global_run_mode_context
import test_effect_adapters


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Make It So Objective Loop.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/make_it_so_objective_loop.sqlite")

SCHEMA_VERSION = "make_it_so_objective_loop_v0"
READ_MODEL_ID = "make_it_so_objective_loop"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "OPENCLAW_MAKE_IT_SO_OBJECTIVE_LOOP_READY"

OBJECTIVE_REQUEST_SCHEMA = "OPERATOR_OBJECTIVE_REQUEST_V0"
OBJECTIVE_CAPABILITY_REQUIREMENT_SCHEMA = "OBJECTIVE_CAPABILITY_REQUIREMENT_V0"
OBJECTIVE_BLOCKER_SCHEMA = "OBJECTIVE_BLOCKER_V0"
MAKE_AUTHORITY_REQUEST_SCHEMA = "MAKE_IT_SO_AUTHORITY_REQUEST_V0"
MAKE_AUTHORITY_GRANT_SCHEMA = "MAKE_IT_SO_AUTHORITY_GRANT_V0"
ENABLEMENT_PLAN_SCHEMA = "CAPABILITY_ENABLEMENT_PLAN_V0"
CAPABILITY_REGISTRY_SCHEMA = "OPERATOR_CAPABILITY_REGISTRY_V0"
CODEX_WORK_PACKAGE_SCHEMA = "CODEX_WORK_PACKAGE_V0"
EXECUTION_RECEIPT_SCHEMA = "OBJECTIVE_EXECUTION_RECEIPT_V0"

READ_ONLY_EMAIL_LOOKUP = capability_authority_loop.READ_ONLY_EMAIL_LOOKUP

STATUS_AWAITING_AUTHORITY = "awaiting_make_it_so_authority"
STATUS_HUMAN_SETUP_REQUIRED = "human_setup_required"
STATUS_TEST_PASSED = "test_passed"
STATUS_ACTIVE = "active"

GRANT_PHRASES = (
    "make it so",
    "do it",
    "set it up",
    "ok, grant that",
    "grant you access",
    "grant that",
    "grant it",
    "yes, grant",
    "yes, build it",
    "yes, activate it for this lane",
    "go ahead",
)

DENIED_ACTIONS = (
    "send_email",
    "delete_email",
    "archive_email",
    "mark_email_read",
    "open_gmail_ui",
    "open_browser",
    "coupa_submit",
    "mark_paid",
    "mutate_ledger",
    "mutate_workbook",
    "export_pdf",
    "git_push",
    "git_merge",
    "spawn_worker",
    "invoke_external_model",
    "lm2_tool_expansion",
    "store_secret_in_repo",
)

ALLOWED_ENABLEMENT_ACTIONS = (
    "inspect_local_contracts",
    "create_enablement_plan",
    "create_bounded_codex_work_package",
    "run_test_effect_adapters",
    "write_receipts",
    "update_operator_capability_registry",
    "report_true_human_blocker_once",
)

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "gmail_allowed": False,
    "gmail_ui_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "worker_spawn_allowed": False,
    "external_model_allowed": False,
    "lm2_tool_expansion_allowed": False,
    "authority_granted_from_raw_text_allowed": False,
    "sent": False,
    "paid": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _short_hash(*parts: Any, length: int = 16) -> str:
    digest = hashlib.sha256()
    for part in parts:
        if isinstance(part, (dict, list, tuple)):
            value = json.dumps(part, sort_keys=True, ensure_ascii=False)
        else:
            value = str(part)
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:length]


def _scope(world_ref: str, thread_ref: str, project_ref: str = "") -> dict[str, str]:
    return {
        "target_world_ref": str(world_ref or ""),
        "target_thread_ref": str(thread_ref or ""),
        "target_project_ref": str(project_ref or ""),
    }


def objective_id_for(capability_id: str, scope: Mapping[str, Any], requested_outcome: str = "") -> str:
    return f"operator_objective:{_short_hash(capability_id, scope, requested_outcome or capability_id)}"


def _expires_at(generated_at: str) -> str:
    return (datetime.fromisoformat(generated_at) + timedelta(hours=8)).isoformat(timespec="seconds")


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS objectives (
          objective_id TEXT PRIMARY KEY,
          capability_id TEXT NOT NULL,
          scope_key TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          objective_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS blockers (
          blocker_id TEXT PRIMARY KEY,
          objective_id TEXT NOT NULL,
          blocker_kind TEXT NOT NULL,
          already_explained INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          blocker_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS make_it_so_authority_requests (
          request_id TEXT PRIMARY KEY,
          objective_id TEXT NOT NULL,
          capability_id TEXT NOT NULL,
          scope_key TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          request_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS make_it_so_authority_grants (
          grant_id TEXT PRIMARY KEY,
          request_id TEXT NOT NULL,
          objective_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          grant_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS enablement_plans (
          plan_id TEXT PRIMARY KEY,
          objective_id TEXT NOT NULL,
          capability_id TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          plan_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS capability_registry (
          capability_id TEXT NOT NULL,
          scope_key TEXT NOT NULL,
          status TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          registry_json TEXT NOT NULL,
          PRIMARY KEY (capability_id, scope_key)
        );

        CREATE TABLE IF NOT EXISTS codex_work_packages (
          package_id TEXT PRIMARY KEY,
          objective_id TEXT NOT NULL,
          capability_id TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          package_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS objective_execution_receipts (
          receipt_id TEXT PRIMARY KEY,
          objective_id TEXT NOT NULL,
          capability_id TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          receipt_json TEXT NOT NULL
        );
        """
    )


def _connect(sqlite_path: Path) -> sqlite3.Connection:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _ensure_tables(conn)
    return conn


def _scope_key(scope: Mapping[str, Any]) -> str:
    return stable_json(dict(scope)).strip()


def _insert_json(conn: sqlite3.Connection, table: str, key_field: str, key_value: str, payload: Mapping[str, Any]) -> None:
    now = str(payload.get("created_at") or payload.get("updated_at") or utc_now())
    if table == "objectives":
        conn.execute(
            """
            INSERT OR REPLACE INTO objectives
            (objective_id, capability_id, scope_key, status, created_at, updated_at, objective_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (key_value, payload["capability_id"], _scope_key(payload["lane"]), payload["status"], payload["created_at"], now, stable_json(payload)),
        )
    elif table == "blockers":
        conn.execute(
            """
            INSERT OR REPLACE INTO blockers
            (blocker_id, objective_id, blocker_kind, already_explained, created_at, blocker_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (key_value, payload["objective_id"], payload["blocker_kind"], 1 if payload.get("already_explained") else 0, payload["created_at"], stable_json(payload)),
        )
    elif table == "make_it_so_authority_requests":
        conn.execute(
            """
            INSERT OR REPLACE INTO make_it_so_authority_requests
            (request_id, objective_id, capability_id, scope_key, status, created_at, request_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (key_value, payload["objective_id"], payload["requested_capabilities"][0], _scope_key(payload["max_scope"]), payload.get("status", "pending"), payload["created_at"], stable_json(payload)),
        )
    elif table == "make_it_so_authority_grants":
        conn.execute(
            """
            INSERT OR REPLACE INTO make_it_so_authority_grants
            (grant_id, request_id, objective_id, created_at, grant_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (key_value, payload["request_id"], payload["objective_id"], payload["created_at"], stable_json(payload)),
        )
    elif table == "enablement_plans":
        conn.execute(
            """
            INSERT OR REPLACE INTO enablement_plans
            (plan_id, objective_id, capability_id, status, created_at, plan_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (key_value, payload["objective_id"], payload["capability_id"], payload["current_status"], payload["created_at"], stable_json(payload)),
        )
    elif table == "codex_work_packages":
        conn.execute(
            """
            INSERT OR REPLACE INTO codex_work_packages
            (package_id, objective_id, capability_id, status, created_at, package_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (key_value, payload["objective_id"], payload["capability_id"], payload["expected_status"], payload["created_at"], stable_json(payload)),
        )
    elif table == "objective_execution_receipts":
        conn.execute(
            """
            INSERT OR REPLACE INTO objective_execution_receipts
            (receipt_id, objective_id, capability_id, status, created_at, receipt_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (key_value, payload["objective_id"], payload["capability_id"], payload["status"], payload["created_at"], stable_json(payload)),
        )


def _registry_record(
    *,
    capability_id: str,
    status: str,
    scope: Mapping[str, Any],
    generated_at: str,
    last_test_receipt: str = "",
    last_production_receipt: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": CAPABILITY_REGISTRY_SCHEMA,
        "capability_id": capability_id,
        "status": status,
        "approved_scopes": [dict(scope)] if status not in {"unavailable", "disabled"} else [],
        "allowed_actions": ["read_relevant_email_evidence"] if capability_id == READ_ONLY_EMAIL_LOOKUP and status == "production_ready" else [],
        "denied_actions": list(DENIED_ACTIONS),
        "run_mode_behavior": {
            "production": "requires production capability authority and connector receipts",
            "test_dry_run": "receipts only",
            "test_live": "test adapters only; does not become production authority",
        },
        "required_receipts": ["test_receipt", "verifier_receipt", "activation_receipt"],
        "required_verifier_checks": ["no_unsupported_claims", "no_protected_actions", "scope_matches"],
        "last_test_receipt": last_test_receipt,
        "last_production_receipt": last_production_receipt,
        "revoked_at": "",
        "updated_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _store_registry(conn: sqlite3.Connection, record: Mapping[str, Any], scope: Mapping[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO capability_registry
        (capability_id, scope_key, status, updated_at, registry_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (record["capability_id"], _scope_key(scope), record["status"], record["updated_at"], stable_json(record)),
    )


def _load_registry(conn: sqlite3.Connection, capability_id: str, scope: Mapping[str, Any]) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT registry_json FROM capability_registry WHERE capability_id = ? AND scope_key = ?",
        (capability_id, _scope_key(scope)),
    ).fetchone()
    return json.loads(row["registry_json"]) if row else None


def _load_objective(conn: sqlite3.Connection, capability_id: str, scope: Mapping[str, Any]) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT objective_json FROM objectives WHERE capability_id = ? AND scope_key = ? ORDER BY updated_at DESC LIMIT 1",
        (capability_id, _scope_key(scope)),
    ).fetchone()
    return json.loads(row["objective_json"]) if row else None


def _load_active_make_request(conn: sqlite3.Connection, scope: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    if scope is not None:
        row = conn.execute(
            """
            SELECT request_json FROM make_it_so_authority_requests
            WHERE scope_key = ? AND status = 'pending'
            ORDER BY created_at DESC LIMIT 1
            """,
            (_scope_key(scope),),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT request_json FROM make_it_so_authority_requests
            WHERE status = 'pending'
            ORDER BY created_at DESC LIMIT 1
            """
        ).fetchone()
    return json.loads(row["request_json"]) if row else None


def make_it_so_grant_intent(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    return any(phrase in lowered for phrase in GRANT_PHRASES)


def build_objective_request(
    *,
    operator_goal_text: str,
    requested_outcome: str,
    capability_id: str,
    world_ref: str,
    thread_ref: str,
    project_ref: str = "",
    run_mode_context: Mapping[str, Any] | None = None,
    source_request_ref: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    scope = _scope(world_ref, thread_ref, project_ref)
    run_context = dict(run_mode_context or global_run_mode_context.default_run_mode_context(generated_at=generated_at))
    objective_id = objective_id_for(capability_id, scope, requested_outcome)
    return {
        "schema_version": OBJECTIVE_REQUEST_SCHEMA,
        "objective_id": objective_id,
        "capability_id": capability_id,
        "lane": scope,
        "project_client": project_ref,
        "operator_goal_text": operator_goal_text,
        "requested_outcome": requested_outcome,
        "run_mode": str(run_context.get("run_mode") or global_run_mode_context.PRODUCTION),
        "created_at": generated_at,
        "source_request_ref": source_request_ref,
        "status": STATUS_AWAITING_AUTHORITY,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_requirement(objective: Mapping[str, Any], *, status: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": OBJECTIVE_CAPABILITY_REQUIREMENT_SCHEMA,
        "objective_id": objective["objective_id"],
        "required_capability_id": objective["capability_id"],
        "required_capability_label": "Read-only email lookup" if objective["capability_id"] == READ_ONLY_EMAIL_LOOKUP else objective["capability_id"],
        "reason": reason,
        "status": status,
        "required_authority_kind": "make_it_so_enablement",
        "safe_test_available": True,
        "production_available": status == "available",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_blocker(
    objective: Mapping[str, Any],
    *,
    blocker_kind: str,
    human_summary: str,
    required_next_input: str,
    can_be_solved_by_make_it_so: bool,
    requires_human_secret_or_external_login: bool = False,
    already_explained: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "schema_version": OBJECTIVE_BLOCKER_SCHEMA,
        "blocker_id": f"objective_blocker:{_short_hash(objective['objective_id'], blocker_kind)}",
        "objective_id": objective["objective_id"],
        "blocker_kind": blocker_kind,
        "human_summary": human_summary,
        "required_next_input": required_next_input,
        "can_be_solved_by_make_it_so": can_be_solved_by_make_it_so,
        "requires_human_secret_or_external_login": requires_human_secret_or_external_login,
        "already_explained": already_explained,
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_make_authority_request(objective: Mapping[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "schema_version": MAKE_AUTHORITY_REQUEST_SCHEMA,
        "request_id": f"make_it_so_authority_request:{_short_hash(objective['objective_id'], generated_at)}",
        "objective_id": objective["objective_id"],
        "requested_capabilities": [objective["capability_id"]],
        "allowed_enablement_actions": list(ALLOWED_ENABLEMENT_ACTIONS),
        "denied_actions": list(DENIED_ACTIONS),
        "run_mode_requirements": ["use test_dry_run/test_live for validation", "test authority does not become production authority"],
        "test_requirements": ["test effect receipts", "unsafe scan", "verifier checks"],
        "validation_requirements": ["focused tests pass", "no unsupported claims", "no protected actions"],
        "max_scope": dict(objective["lane"]),
        "human_summary": f"Grant make-it-so authority to build/test/activate {objective['capability_id']} for this scope.",
        "risk_summary": "This allows bounded enablement work only. It does not allow email send, Gmail/browser UI, Coupa, paid marking, ledger/workbook/PDF mutation, push/merge, LM2 expansion, or secret storage.",
        "expires_at": _expires_at(generated_at),
        "requires_explicit_operator_grant": True,
        "status": "pending",
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_make_authority_grant(request: Mapping[str, Any], operator_text: str, *, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "schema_version": MAKE_AUTHORITY_GRANT_SCHEMA,
        "grant_id": f"make_it_so_authority_grant:{_short_hash(request['request_id'], operator_text, generated_at)}",
        "request_id": request["request_id"],
        "objective_id": request["objective_id"],
        "granted_capabilities": list(request.get("requested_capabilities") or []),
        "granted_enablement_actions": list(request.get("allowed_enablement_actions") or []),
        "denied_actions": list(request.get("denied_actions") or DENIED_ACTIONS),
        "scope": dict(request.get("max_scope") or {}),
        "run_mode_requirements": list(request.get("run_mode_requirements") or []),
        "created_at": generated_at,
        "expires_at": str(request.get("expires_at") or ""),
        "receipt_ref": f"make_it_so_authority_receipt:{_short_hash(request['request_id'], generated_at)}",
        "verifier_status": "VERIFIED_MAKE_IT_SO_SCOPE",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_enablement_plan(
    objective: Mapping[str, Any],
    *,
    current_status: str,
    desired_status: str,
    human_blockers: Sequence[Mapping[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    capability_id = str(objective["capability_id"])
    return {
        "schema_version": ENABLEMENT_PLAN_SCHEMA,
        "plan_id": f"capability_enablement_plan:{_short_hash(objective['objective_id'], desired_status)}",
        "objective_id": objective["objective_id"],
        "capability_id": capability_id,
        "current_status": current_status,
        "desired_status": desired_status,
        "steps": [
            "confirm scope",
            "build or configure missing adapter",
            "run test mode validation",
            "write receipts",
            "activate only if verifier passes",
        ],
        "test_mode_steps": ["run test_dry_run fixture", "run test_live only with explicit test authority"],
        "build_steps": ["create bounded Codex work package", "do not execute protected production action"],
        "validation_steps": ["focused pytest", "py_compile", "unsafe scan", "receipt verification"],
        "activation_steps": ["update capability registry only after required receipts exist"],
        "human_blockers": [dict(item) for item in human_blockers],
        "rollback_or_disable_plan": "Disable registry entry or leave unavailable; do not persist secrets in repo.",
        "receipts_required": ["objective_execution_receipt", "test_effect_receipt", "verifier_receipt"],
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_codex_work_package(objective: Mapping[str, Any], grant: Mapping[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "schema_version": CODEX_WORK_PACKAGE_SCHEMA,
        "package_id": f"codex_work_package:{_short_hash(objective['objective_id'], grant.get('grant_id'), generated_at)}",
        "objective_id": objective["objective_id"],
        "capability_id": objective["capability_id"],
        "worktree_root": "/home/openclaw",
        "allowed_file_paths": [
            "make_it_so_objective_loop.py",
            "tests/test_make_it_so_objective_loop.py",
            "generated/read_models/",
            "generated/wiki/openclaw/",
            "generated/system_knowledge/",
        ],
        "denied_file_paths": ["business ledger", "production workbooks", "production PDFs", "credentials", "secrets"],
        "allowed_commands": ["python3 -m pytest focused tests", "python3 -m py_compile changed files", "git diff --check"],
        "denied_commands": ["git push", "git merge", "open browser", "open Gmail", "send email", "submit Coupa", "invoke external model", "spawn worker"],
        "validation_commands": ["pytest", "py_compile", "json parse", "unsafe scan"],
        "unsafe_scan": "required",
        "run_mode": str(objective.get("run_mode") or global_run_mode_context.PRODUCTION),
        "authority_grant_ref": str(grant.get("grant_id") or ""),
        "expected_status": "PACKAGE_STAGED",
        "receipt_ref": f"codex_work_package_receipt:{_short_hash(objective['objective_id'], generated_at)}",
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_execution_receipt(
    objective: Mapping[str, Any],
    *,
    step_id: str,
    status: str,
    capability_id: str,
    artifact_refs: Sequence[str] = (),
    validation_refs: Sequence[str] = (),
    blocked_by: str = "",
    next_safe_step: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "schema_version": EXECUTION_RECEIPT_SCHEMA,
        "receipt_id": f"objective_execution_receipt:{_short_hash(objective['objective_id'], step_id, status, generated_at)}",
        "objective_id": objective["objective_id"],
        "step_id": step_id,
        "status": status,
        "run_mode": str(objective.get("run_mode") or global_run_mode_context.PRODUCTION),
        "capability_id": capability_id,
        "artifact_refs": list(artifact_refs),
        "validation_refs": list(validation_refs),
        "created_at": generated_at,
        "blocked_by": blocked_by,
        "next_safe_step": next_safe_step,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def start_email_lookup_objective(
    operator_text: str,
    *,
    world_ref: str,
    thread_ref: str,
    project_ref: str = "",
    run_mode_context: Mapping[str, Any] | None = None,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    source_request_ref: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    scope = _scope(world_ref, thread_ref, project_ref)
    with _connect(sqlite_path) as conn:
        registry = _load_registry(conn, READ_ONLY_EMAIL_LOOKUP, scope)
        if registry and registry.get("status") in {"production_ready", "test_passed"}:
            receipt_objective = build_objective_request(
                operator_goal_text=operator_text,
                requested_outcome="answer from active read-only email lookup",
                capability_id=READ_ONLY_EMAIL_LOOKUP,
                world_ref=world_ref,
                thread_ref=thread_ref,
                project_ref=project_ref,
                run_mode_context=run_mode_context,
                source_request_ref=source_request_ref,
                generated_at=generated_at,
            )
            return {
                "schema_version": SCHEMA_VERSION,
                "response_status": "CAPABILITY_ALREADY_APPROVED",
                "objective_request": receipt_objective,
                "capability_registry": registry,
                "operator_display": {
                    "speaker_ref": "chief",
                    "headline": "Capability is ready",
                    "plain_summary": "Read-only email lookup is approved for this scope. Route directly to the capability when the connector is active.",
                    "next_safe_action": "Run the scoped read-only lookup.",
                    "proof_refs_collapsed": True,
                },
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            }
        existing = _load_objective(conn, READ_ONLY_EMAIL_LOOKUP, scope)
        if existing:
            blocker = build_blocker(
                existing,
                blocker_kind="missing_capability",
                human_summary="Read-only email lookup is still not active for this scope.",
                required_next_input="Grant make-it-so authority or complete the recorded human setup blocker.",
                can_be_solved_by_make_it_so=True,
                already_explained=True,
                generated_at=generated_at,
            )
            return {
                "schema_version": SCHEMA_VERSION,
                "response_status": "OBJECTIVE_STATUS_READY",
                "objective_request": existing,
                "objective_blocker": blocker,
                "operator_display": {
                    "speaker_ref": "chief",
                    "headline": "Objective still waiting",
                    "plain_summary": "I already recorded the missing read-only email lookup capability for this scope. It is waiting on make-it-so authority or the recorded setup blocker.",
                    "next_safe_action": "Grant make-it-so authority or review the setup blocker.",
                    "proof_refs_collapsed": True,
                },
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            }
        objective = build_objective_request(
            operator_goal_text=operator_text,
            requested_outcome="answer whether relevant email evidence exists",
            capability_id=READ_ONLY_EMAIL_LOOKUP,
            world_ref=world_ref,
            thread_ref=thread_ref,
            project_ref=project_ref,
            run_mode_context=run_mode_context,
            source_request_ref=source_request_ref,
            generated_at=generated_at,
        )
        requirement = build_requirement(objective, status="missing", reason="answer requires scoped read-only email evidence")
        blocker = build_blocker(
            objective,
            blocker_kind="missing_capability",
            human_summary="Read-only email lookup is not active for this scope.",
            required_next_input="Grant make-it-so authority to build/test/activate read-only email lookup.",
            can_be_solved_by_make_it_so=True,
            generated_at=generated_at,
        )
        make_request = build_make_authority_request(objective, generated_at=generated_at)
        _insert_json(conn, "objectives", "objective_id", objective["objective_id"], objective)
        _insert_json(conn, "blockers", "blocker_id", blocker["blocker_id"], blocker)
        _insert_json(conn, "make_it_so_authority_requests", "request_id", make_request["request_id"], make_request)
        _store_registry(conn, _registry_record(capability_id=READ_ONLY_EMAIL_LOOKUP, status="unavailable", scope=scope, generated_at=generated_at), scope)
        conn.commit()
    capability_gap = capability_authority_loop.build_email_lookup_gap_response(
        operator_text,
        world_ref=world_ref,
        thread_ref=thread_ref,
        project_ref=project_ref,
        run_mode_context=run_mode_context,
        generated_at=generated_at,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "response_status": "MAKE_IT_SO_AUTHORITY_REQUEST_READY",
        "objective_request": objective,
        "capability_requirement": requirement,
        "objective_blocker": blocker,
        "make_it_so_authority_request": make_request,
        "capability_authority": capability_gap,
        "operator_display": {
            "speaker_ref": "chief",
            "headline": "Make-it-so authority needed",
            "plain_summary": "I need read-only email lookup to answer that. Grant make-it-so authority to build, test, and activate it for this scope?",
            "next_safe_action": "Say: Make it so.",
            "proof_refs_collapsed": True,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def handle_make_it_so_grant(
    operator_text: str,
    *,
    world_ref: str = "",
    thread_ref: str = "",
    project_ref: str = "",
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    run_mode_context: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    if not make_it_so_grant_intent(operator_text):
        return {
            "schema_version": MAKE_AUTHORITY_GRANT_SCHEMA,
            "response_status": "NOT_MAKE_IT_SO_GRANT_INTENT",
            "authority_grant_created": False,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
    scope = _scope(world_ref, thread_ref, project_ref) if world_ref or thread_ref or project_ref else None
    with _connect(sqlite_path) as conn:
        active = _load_active_make_request(conn, scope)
        if not active:
            return {
                "schema_version": SCHEMA_VERSION,
                "response_status": "NEEDS_ACTIVE_MAKE_IT_SO_REQUEST",
                "authority_grant_created": False,
                "operator_display": {
                    "speaker_ref": "guardian",
                    "headline": "Active objective needed",
                    "plain_summary": "I can only make it so against an active scoped objective request. I will not infer broad authority.",
                    "next_safe_action": "Ask the blocked capability question again in the intended lane.",
                    "proof_refs_collapsed": True,
                },
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            }
        objective_row = conn.execute("SELECT objective_json FROM objectives WHERE objective_id = ?", (active["objective_id"],)).fetchone()
        objective = json.loads(objective_row["objective_json"]) if objective_row else {}
        grant = build_make_authority_grant(active, operator_text, generated_at=generated_at)
        human_blocker = build_blocker(
            objective,
            blocker_kind="missing_connector",
            human_summary="A safe read-only email connector/credential setup is required. I will not store secrets in the repo.",
            required_next_input="Configure a safe read-only email connector or OS/keychain-backed credential outside the repo.",
            can_be_solved_by_make_it_so=False,
            requires_human_secret_or_external_login=True,
            already_explained=False,
            generated_at=generated_at,
        )
        plan = build_enablement_plan(
            objective,
            current_status="adapter_missing",
            desired_status="production_ready",
            human_blockers=[human_blocker],
            generated_at=generated_at,
        )
        package = build_codex_work_package(objective, grant, generated_at=generated_at)
        receipt = build_execution_receipt(
            objective,
            step_id="create_enablement_plan",
            status=STATUS_HUMAN_SETUP_REQUIRED,
            capability_id=objective["capability_id"],
            artifact_refs=[plan["plan_id"], package["package_id"]],
            validation_refs=[],
            blocked_by=human_blocker["blocker_id"],
            next_safe_step=human_blocker["required_next_input"],
            generated_at=generated_at,
        )
        _insert_json(conn, "make_it_so_authority_grants", "grant_id", grant["grant_id"], grant)
        _insert_json(conn, "blockers", "blocker_id", human_blocker["blocker_id"], human_blocker)
        _insert_json(conn, "enablement_plans", "plan_id", plan["plan_id"], plan)
        _insert_json(conn, "codex_work_packages", "package_id", package["package_id"], package)
        _insert_json(conn, "objective_execution_receipts", "receipt_id", receipt["receipt_id"], receipt)
        conn.execute("UPDATE make_it_so_authority_requests SET status = 'granted' WHERE request_id = ?", (active["request_id"],))
        objective["status"] = STATUS_HUMAN_SETUP_REQUIRED
        objective["updated_at"] = generated_at
        _insert_json(conn, "objectives", "objective_id", objective["objective_id"], objective)
        _store_registry(
            conn,
            _registry_record(capability_id=objective["capability_id"], status="build_requested", scope=objective["lane"], generated_at=generated_at),
            objective["lane"],
        )
        conn.commit()
    return {
        "schema_version": SCHEMA_VERSION,
        "response_status": "MAKE_IT_SO_GRANT_COMPILED",
        "make_it_so_authority_grant": grant,
        "capability_enablement_plan": plan,
        "codex_work_package": package,
        "objective_blocker": human_blocker,
        "objective_execution_receipt": receipt,
        "operator_display": {
            "speaker_ref": "chief",
            "headline": "Make-it-so plan created",
            "plain_summary": "I created the scoped enablement plan and bounded Codex work package. The true blocker is safe read-only email connector setup outside the repo.",
            "next_safe_action": human_blocker["required_next_input"],
            "proof_refs_collapsed": True,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def run_test_effect_objective(
    *,
    effect_kind: str,
    target: str,
    source_path: str = "",
    world_ref: str = "test",
    thread_ref: str = "effects",
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    effect_sqlite_path: Path = test_effect_adapters.DEFAULT_SQLITE_PATH,
    workspace_root: Path = test_effect_adapters.DEFAULT_WORKSPACE_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    run_context = global_run_mode_context.context_from_state(
        global_run_mode_context.build_run_mode_state(
            run_mode=global_run_mode_context.TEST_LIVE,
            scope={"scope": "session", "target_world_ref": world_ref, "target_thread_ref": thread_ref},
            generated_at=generated_at,
        ),
        source="make_it_so_objective_loop",
        generated_at=generated_at,
    )
    scope = _scope(world_ref, thread_ref)
    capability_id = f"test_effect:{effect_kind}"
    objective = build_objective_request(
        operator_goal_text=f"Run test effect {effect_kind}",
        requested_outcome=f"prove {effect_kind} test adapter",
        capability_id=capability_id,
        world_ref=world_ref,
        thread_ref=thread_ref,
        run_mode_context=run_context,
        generated_at=generated_at,
    )
    authority = test_effect_adapters.build_test_execution_authority(
        test_run_id=run_context["test_run_id"],
        allowed_effect_kinds=[effect_kind],
        allowlisted_recipients=[test_effect_adapters.ALLOWLISTED_TEST_EMAIL],
        max_external_effects=1,
        generated_at=generated_at,
    )
    effect_request = test_effect_adapters.build_test_effect_request(
        effect_kind=effect_kind,
        run_mode_context=run_context,
        target=target,
        source_path=source_path,
        payload_summary=f"make it so test effect {effect_kind}",
        generated_at=generated_at,
    )
    effect_receipt = test_effect_adapters.execute_test_effect(
        effect_request,
        sqlite_path=effect_sqlite_path,
        workspace_root=workspace_root,
        test_execution_authority=authority,
        generated_at=generated_at,
    )
    status = STATUS_TEST_PASSED if effect_receipt["status"] == test_effect_adapters.TEST_LIVE_EXECUTED else STATUS_HUMAN_SETUP_REQUIRED
    plan = build_enablement_plan(
        objective,
        current_status=status,
        desired_status="test_passed",
        human_blockers=[] if status == STATUS_TEST_PASSED else [build_blocker(objective, blocker_kind="missing_test_adapter", human_summary="Test adapter did not execute.", required_next_input="Review adapter receipt.", can_be_solved_by_make_it_so=True, generated_at=generated_at)],
        generated_at=generated_at,
    )
    receipt = build_execution_receipt(
        objective,
        step_id=f"run_{effect_kind}",
        status=status,
        capability_id=capability_id,
        artifact_refs=[str(effect_receipt.get("artifact_ref") or effect_receipt.get("actual_target") or "")],
        validation_refs=[str(effect_receipt.get("effect_id") or "")],
        next_safe_step="Review test receipt.",
        generated_at=generated_at,
    )
    with _connect(sqlite_path) as conn:
        objective["status"] = status
        _insert_json(conn, "objectives", "objective_id", objective["objective_id"], objective)
        _insert_json(conn, "enablement_plans", "plan_id", plan["plan_id"], plan)
        _insert_json(conn, "objective_execution_receipts", "receipt_id", receipt["receipt_id"], receipt)
        _store_registry(
            conn,
            _registry_record(capability_id=capability_id, status=status, scope=scope, generated_at=generated_at, last_test_receipt=str(effect_receipt.get("effect_id") or "")),
            scope,
        )
        conn.commit()
    return {
        "schema_version": SCHEMA_VERSION,
        "response_status": "TEST_EFFECT_OBJECTIVE_RAN",
        "objective_request": objective,
        "capability_enablement_plan": plan,
        "test_effect_request": effect_request,
        "test_effect_receipt": effect_receipt,
        "objective_execution_receipt": receipt,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_contract_read_model(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "contracts": [
            OBJECTIVE_REQUEST_SCHEMA,
            OBJECTIVE_CAPABILITY_REQUIREMENT_SCHEMA,
            OBJECTIVE_BLOCKER_SCHEMA,
            MAKE_AUTHORITY_REQUEST_SCHEMA,
            MAKE_AUTHORITY_GRANT_SCHEMA,
            ENABLEMENT_PLAN_SCHEMA,
            CAPABILITY_REGISTRY_SCHEMA,
            CODEX_WORK_PACKAGE_SCHEMA,
            EXECUTION_RECEIPT_SCHEMA,
        ],
        "primary_capability_example": READ_ONLY_EMAIL_LOOKUP,
        "policy": [
            "Explain a blocker once, then request scoped make-it-so authority.",
            "Make-it-so authority grants enablement work only, not protected production actions.",
            "True human blockers such as missing connector credentials are recorded once.",
            "Bounded Codex work packages are staged but not executed as workers.",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "email_send_enabled": False,
            "gmail_ui_open_enabled": False,
            "browser_open_enabled": False,
            "coupa_submit_enabled": False,
            "paid_marking_enabled": False,
            "ledger_mutation_enabled": False,
            "workbook_mutation_enabled": False,
            "pdf_export_enabled": False,
            "git_push_enabled": False,
            "merge_enabled": False,
            "worker_spawn_enabled": False,
            "external_model_enabled": False,
            "raw_authority_granted_trusted": False,
        },
    }


def build_wiki(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# Make It So Objective Loop",
            "",
            f"Status: `{payload['status']}`",
            "",
            "Turns missing-capability blockers into scoped make-it-so objectives, grants, plans, bounded Codex work packages, and receipts.",
            "",
            "## Boundary",
            "- Make-it-so enables bounded build/test/activation setup only.",
            "- It does not allow send, Gmail/browser, Coupa, paid, ledger/workbook/PDF mutation, push/merge, worker spawn, or model expansion.",
            "",
        ]
    )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _write_contract_sqlite(sqlite_path: Path, payload: Mapping[str, Any]) -> None:
    with _connect(sqlite_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS make_it_so_objective_loop_contract (
              read_model_id TEXT PRIMARY KEY,
              generated_at TEXT NOT NULL,
              status TEXT NOT NULL,
              payload_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO make_it_so_objective_loop_contract
            (read_model_id, generated_at, status, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (READ_MODEL_ID, str(payload.get("generated_at") or ""), str(payload.get("status") or ""), stable_json(payload)),
        )
        conn.commit()


def export_make_it_so_objective_loop(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    payload = build_contract_read_model(generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    _write_json(read_model_path, payload)
    wiki = _rooted(wiki_path)
    wiki.parent.mkdir(parents=True, exist_ok=True)
    wiki.write_text(build_wiki(payload), encoding="utf-8")
    _write_contract_sqlite(sqlite_path, payload)
    bridge_path = ""
    if bridge_root is not None:
        bridge = Path(bridge_root)
        bridge.mkdir(parents=True, exist_ok=True)
        target = bridge / JSON_EXPORT_NAME
        shutil.copy2(read_model_path, target)
        bridge_path = target.as_posix()
    return {
        "status": str(payload["status"]),
        "read_model_path": read_model_path.as_posix(),
        "bridge_path": bridge_path,
        "wiki_path": wiki.as_posix(),
        "sqlite_path": _rooted(sqlite_path).as_posix(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    args = parser.parse_args()
    result = export_make_it_so_objective_loop(
        export_root=Path(args.export_root),
        bridge_root=Path(args.bridge_root) if args.bridge_root else None,
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
    )
    print(stable_json(result))


if __name__ == "__main__":
    main()
