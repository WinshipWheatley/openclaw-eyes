"""SQLite-backed capability registry, resolution, and build provenance.

This module is deterministic and non-executing. It records what capability
contracts and fixtures exist, why a request should reuse, mature, build, block,
or resolve conflict, and how future packages can plan against that inventory.
It does not access Gmail/Coupa/browser, send, submit, mark paid, mutate ledgers,
run models, or enable production behavior.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import openclaw_plugin_contract


ROOT = Path(__file__).resolve().parent
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/capability_registry_build_provenance.sqlite")

SCHEMA_VERSION = "capability_registry_build_provenance_v0"
CAPABILITY_RESOLUTION_EVENT_SCHEMA = "CAPABILITY_RESOLUTION_EVENT_V0"
CAPABILITY_PACKAGE_PLAN_SCHEMA = "CAPABILITY_PACKAGE_PLAN_V0"
CAPABILITY_BUILD_RECEIPT_SCHEMA = "CAPABILITY_BUILD_RECEIPT_V0"

MATURITY_STATUSES = (
    "missing",
    "concept_only",
    "contract_fixture",
    "deterministic_stub",
    "test_fixture_ready",
    "shadow_ready",
    "live_read_ready",
    "live_write_ready",
    "production_ready",
    "deprecated",
    "blocked",
    "conflict",
)

PROTECTED_MATURITIES = {"live_write_ready", "production_ready"}

DEFAULT_DENIED_ACTIONS = (
    "live_gmail_access",
    "open_gmail_ui",
    "open_browser",
    "send_email",
    "coupa_access",
    "coupa_submit",
    "mark_paid",
    "mutate_ledger",
    "mutate_workbook",
    "export_pdf",
    "run_excel",
    "trust_raw_authority_granted",
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _short_hash(*parts: Any, length: int = 16) -> str:
    digest = hashlib.sha256()
    for part in parts:
        if isinstance(part, (dict, list, tuple)):
            value = json.dumps(part, sort_keys=True, ensure_ascii=True)
        else:
            value = str(part)
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:length]


def _json(value: Any) -> str:
    return stable_json(value).strip()


def _loads(value: Any) -> Any:
    if value in (None, ""):
        return None
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return None


def connect(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> sqlite3.Connection:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS capability_registry (
          capability_id TEXT PRIMARY KEY,
          capability_label TEXT NOT NULL,
          capability_kind TEXT NOT NULL,
          current_maturity TEXT NOT NULL,
          current_status TEXT NOT NULL,
          plugin_contract_ref TEXT NOT NULL DEFAULT '',
          primary_descriptor_ref TEXT NOT NULL DEFAULT '',
          summary TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deprecated_by_capability_id TEXT
        );

        CREATE TABLE IF NOT EXISTS capability_implementations (
          implementation_id TEXT PRIMARY KEY,
          capability_id TEXT NOT NULL,
          implementation_kind TEXT NOT NULL,
          path_ref TEXT NOT NULL,
          entrypoint_ref TEXT,
          test_refs TEXT NOT NULL DEFAULT '[]',
          run_modes_supported TEXT NOT NULL DEFAULT '[]',
          authority_profile_ref TEXT,
          hash_or_fingerprint TEXT,
          maturity TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS capability_resolution_events (
          resolution_id TEXT PRIMARY KEY,
          requested_intent TEXT NOT NULL,
          requested_capability_id TEXT NOT NULL,
          lane_context TEXT NOT NULL,
          discovered_capabilities TEXT NOT NULL,
          discovered_implementations TEXT NOT NULL,
          selected_resolution TEXT NOT NULL,
          rationale TEXT NOT NULL,
          maturity_gaps TEXT NOT NULL,
          safe_next_step TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS capability_build_requests (
          build_request_id TEXT PRIMARY KEY,
          capability_id TEXT NOT NULL,
          source_gap_id TEXT,
          source_resolution_id TEXT,
          requested_by_context TEXT NOT NULL,
          build_goal TEXT NOT NULL,
          allowed_build_actions TEXT NOT NULL,
          denied_build_actions TEXT NOT NULL,
          allowed_paths_or_repo_scope TEXT NOT NULL,
          test_mode_required INTEGER NOT NULL DEFAULT 1,
          production_enablement_allowed INTEGER NOT NULL DEFAULT 0,
          live_data_access_allowed INTEGER NOT NULL DEFAULT 0,
          external_services_allowed INTEGER NOT NULL DEFAULT 0,
          required_tests TEXT NOT NULL,
          required_receipts TEXT NOT NULL,
          required_review TEXT NOT NULL,
          operator_confirmation_required INTEGER NOT NULL DEFAULT 1,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          expires_at TEXT
        );

        CREATE TABLE IF NOT EXISTS capability_build_receipts (
          receipt_id TEXT PRIMARY KEY,
          build_request_id TEXT NOT NULL,
          capability_id TEXT NOT NULL,
          commit_hash TEXT,
          changed_files TEXT NOT NULL,
          tests_run TEXT NOT NULL,
          validation_results TEXT NOT NULL,
          unsafe_scan_summary TEXT NOT NULL,
          verifier_receipts TEXT NOT NULL,
          result_status TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS capability_package_targets (
          target_id TEXT PRIMARY KEY,
          capability_id TEXT NOT NULL,
          target_kind TEXT NOT NULL,
          descriptor_ref TEXT NOT NULL,
          package_status TEXT NOT NULL,
          compatibility_notes TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS capability_dependencies (
          capability_id TEXT NOT NULL,
          depends_on_capability_id TEXT NOT NULL,
          dependency_reason TEXT NOT NULL,
          required_maturity TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY (capability_id, depends_on_capability_id)
        );
        """
    )


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for key in (
        "test_refs",
        "run_modes_supported",
        "lane_context",
        "discovered_capabilities",
        "discovered_implementations",
        "maturity_gaps",
        "requested_by_context",
        "allowed_build_actions",
        "denied_build_actions",
        "allowed_paths_or_repo_scope",
        "required_tests",
        "required_receipts",
        "changed_files",
        "tests_run",
        "validation_results",
        "unsafe_scan_summary",
        "verifier_receipts",
    ):
        if key in result:
            result[key] = _loads(result[key]) or []
    for key in ("test_mode_required", "production_enablement_allowed", "live_data_access_allowed", "external_services_allowed", "operator_confirmation_required"):
        if key in result:
            result[key] = bool(result[key])
    return result


def seed_fixture_capabilities(*, conn: sqlite3.Connection, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    descriptors = openclaw_plugin_contract.fixture_descriptors()
    seeded: list[str] = []
    for capability_id, descriptor in descriptors.items():
        label = str(descriptor.get("plugin_label") or capability_id)
        conn.execute(
            """
            INSERT OR IGNORE INTO capability_registry
              (capability_id, capability_label, capability_kind, current_maturity, current_status,
               plugin_contract_ref, primary_descriptor_ref, summary, created_at, updated_at, deprecated_by_capability_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                capability_id,
                label,
                "plugin_contract_fixture",
                "contract_fixture",
                "available_for_resolution_not_live",
                "openclaw_plugin_contract.py",
                f"openclaw_plugin_contract.fixture_descriptors:{capability_id}",
                "Seeded from OPENCLAW_PLUGIN_CONTRACT_V0 fixture descriptor.",
                generated_at,
                generated_at,
            ),
        )
        implementation_id = f"implementation:{_short_hash(capability_id, 'plugin_contract_fixture')}"
        conn.execute(
            """
            INSERT OR IGNORE INTO capability_implementations
              (implementation_id, capability_id, implementation_kind, path_ref, entrypoint_ref, test_refs,
               run_modes_supported, authority_profile_ref, hash_or_fingerprint, maturity, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                implementation_id,
                capability_id,
                "plugin_contract",
                "openclaw_plugin_contract.py",
                "fixture_descriptors",
                _json(["tests/test_openclaw_plugin_contract.py"]),
                _json(["fixture", "test"]),
                str((descriptor.get("required_authority") or {}).get("authority_profile_ref") or ""),
                f"sha256:{hashlib.sha256(stable_json(descriptor).encode('utf-8')).hexdigest()}",
                "contract_fixture",
                "available_for_resolution_not_live",
                generated_at,
                generated_at,
            ),
        )
        for target_kind in descriptor.get("package_targets") or []:
            conn.execute(
                """
                INSERT OR IGNORE INTO capability_package_targets
                  (target_id, capability_id, target_kind, descriptor_ref, package_status, compatibility_notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"target:{_short_hash(capability_id, target_kind)}",
                    capability_id,
                    str(target_kind),
                    f"openclaw_plugin_contract.fixture_descriptors:{capability_id}",
                    "planned_not_built",
                    "Fixture descriptor only; no production package created.",
                    generated_at,
                    generated_at,
                ),
            )
        seeded.append(capability_id)
    return {"seeded_capability_ids": sorted(seeded), "seeded_at": generated_at}


def fetch_capability(conn: sqlite3.Connection, capability_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM capability_registry WHERE capability_id = ?", (capability_id,)).fetchone()
    return _row_dict(row) if row else None


def fetch_implementations(conn: sqlite3.Connection, capability_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM capability_implementations WHERE capability_id = ? ORDER BY maturity DESC, implementation_kind, path_ref",
        (capability_id,),
    ).fetchall()
    return [_row_dict(row) for row in rows]


def _overlapping_capabilities(conn: sqlite3.Connection, capability_id: str, label: str = "") -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM capability_registry").fetchall()
    requested_tail = capability_id.rsplit(".", 1)[-1].replace("_", " ").lower()
    label_norm = label.strip().lower()
    matches: list[dict[str, Any]] = []
    for row in rows:
        item = _row_dict(row)
        item_label = str(item.get("capability_label") or "").lower()
        item_tail = str(item.get("capability_id") or "").rsplit(".", 1)[-1].replace("_", " ").lower()
        if item["capability_id"] == capability_id:
            matches.append(item)
        elif label_norm and item_label == label_norm:
            matches.append(item)
        elif requested_tail and requested_tail == item_tail:
            matches.append(item)
    return matches


def resolve_capability(
    capability_id: str,
    *,
    requested_intent: str = "",
    lane_context: Mapping[str, Any] | None = None,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    persist: bool = True,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    lane = dict(lane_context or {})
    with connect(sqlite_path) as conn:
        seed_fixture_capabilities(conn=conn, generated_at=generated_at)
        capability = fetch_capability(conn, capability_id)
        implementations = fetch_implementations(conn, capability_id) if capability else []
        overlaps = _overlapping_capabilities(conn, capability_id)
        conflict = len({item["capability_id"] for item in overlaps}) > 1
        if conflict:
            selected = "conflict"
            rationale = "Multiple overlapping capability records exist; consolidate or choose one before building."
            maturity_gaps = ["capability_identity_conflict"]
            safe_next_step = "Review overlapping capability records."
        elif not capability:
            selected = "build_new"
            rationale = "No registered capability or implementation was found."
            maturity_gaps = ["capability_missing"]
            safe_next_step = "Create a scoped build request for a new test/shadow capability."
        elif capability["current_maturity"] in {"blocked", "deprecated"}:
            selected = "blocked"
            rationale = f"Capability exists but status is {capability['current_maturity']}."
            maturity_gaps = [capability["current_maturity"]]
            safe_next_step = "Resolve the blocked or deprecated capability state."
        elif capability["current_maturity"] in PROTECTED_MATURITIES:
            selected = "reuse"
            rationale = "Capability is mature enough to reuse if current request authority also exists."
            maturity_gaps = []
            safe_next_step = "Check request-specific live authority before use."
        else:
            selected = "mature_existing"
            rationale = "Capability exists as descriptor/stub/test fixture but is not mature enough for live execution."
            maturity_gaps = [f"current_maturity:{capability['current_maturity']}", "live_authority_not_granted"]
            safe_next_step = "Create a build request to mature the existing capability in test/shadow mode."
        resolution_id = f"capability_resolution:{_short_hash(capability_id, requested_intent, lane, generated_at)}"
        event = {
            "schema_version": CAPABILITY_RESOLUTION_EVENT_SCHEMA,
            "resolution_id": resolution_id,
            "requested_intent": requested_intent,
            "requested_capability_id": capability_id,
            "lane_context": lane,
            "discovered_capabilities": overlaps if overlaps else ([capability] if capability else []),
            "discovered_implementations": implementations,
            "selected_resolution": selected,
            "rationale": rationale,
            "maturity_gaps": maturity_gaps,
            "safe_next_step": safe_next_step,
            "created_at": generated_at,
        }
        if persist:
            conn.execute(
                """
                INSERT OR REPLACE INTO capability_resolution_events
                  (resolution_id, requested_intent, requested_capability_id, lane_context,
                   discovered_capabilities, discovered_implementations, selected_resolution,
                   rationale, maturity_gaps, safe_next_step, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolution_id,
                    requested_intent,
                    capability_id,
                    _json(lane),
                    _json(event["discovered_capabilities"]),
                    _json(implementations),
                    selected,
                    rationale,
                    _json(maturity_gaps),
                    safe_next_step,
                    generated_at,
                ),
            )
        return event


def persist_build_request(
    build_request: Mapping[str, Any],
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    status: str = "pending_review",
) -> dict[str, Any]:
    with connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO capability_build_requests
              (build_request_id, capability_id, source_gap_id, source_resolution_id, requested_by_context,
               build_goal, allowed_build_actions, denied_build_actions, allowed_paths_or_repo_scope,
               test_mode_required, production_enablement_allowed, live_data_access_allowed, external_services_allowed,
               required_tests, required_receipts, required_review, operator_confirmation_required, status, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(build_request.get("request_id") or build_request.get("build_request_id") or ""),
                str(build_request.get("capability_id") or ""),
                str(build_request.get("source_gap_id") or build_request.get("prior_capability_gap_id") or ""),
                str(build_request.get("source_resolution_id") or ""),
                _json(build_request.get("requested_by_context") or {}),
                str(build_request.get("build_goal") or ""),
                _json(build_request.get("allowed_build_actions") or []),
                _json(build_request.get("denied_build_actions") or []),
                _json(build_request.get("allowed_paths_or_repo_scope") or []),
                1 if build_request.get("test_mode_required", True) else 0,
                1 if build_request.get("production_enablement_allowed") is True else 0,
                1 if build_request.get("live_data_access_allowed") is True else 0,
                1 if build_request.get("external_services_allowed") is True else 0,
                _json(build_request.get("required_tests") or []),
                _json(build_request.get("required_receipts") or []),
                str(build_request.get("required_review") or ""),
                1 if build_request.get("operator_confirmation_required", True) else 0,
                status,
                str(build_request.get("created_at") or utc_now()),
                str(build_request.get("expires_at") or ""),
            ),
        )
    return {"stored": True, "build_request_id": str(build_request.get("request_id") or ""), "status": status}


def insert_build_receipt(
    *,
    build_request_id: str,
    capability_id: str,
    changed_files: Sequence[str],
    tests_run: Sequence[str],
    validation_results: Mapping[str, Any],
    unsafe_scan_summary: Mapping[str, Any],
    verifier_receipts: Sequence[str] = (),
    commit_hash: str = "",
    result_status: str = "validated",
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    receipt_id = f"capability_build_receipt:{_short_hash(build_request_id, capability_id, changed_files, tests_run, generated_at)}"
    with connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO capability_build_receipts
              (receipt_id, build_request_id, capability_id, commit_hash, changed_files, tests_run,
               validation_results, unsafe_scan_summary, verifier_receipts, result_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_id,
                build_request_id,
                capability_id,
                commit_hash,
                _json(list(changed_files)),
                _json(list(tests_run)),
                _json(dict(validation_results)),
                _json(dict(unsafe_scan_summary)),
                _json(list(verifier_receipts)),
                result_status,
                generated_at,
            ),
        )
    return {
        "schema_version": CAPABILITY_BUILD_RECEIPT_SCHEMA,
        "receipt_id": receipt_id,
        "build_request_id": build_request_id,
        "capability_id": capability_id,
        "result_status": result_status,
        "created_at": generated_at,
    }


def build_package_plan(
    *,
    requested_objective: str,
    required_capabilities: Sequence[str],
    lane_context: Mapping[str, Any] | None = None,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    selected_implementations: list[dict[str, Any]] = []
    missing: list[str] = []
    maturity_rows: list[dict[str, Any]] = []
    for capability_id in required_capabilities:
        resolution = resolve_capability(
            capability_id,
            requested_intent=requested_objective,
            lane_context=lane_context or {},
            sqlite_path=sqlite_path,
            persist=True,
            generated_at=generated_at,
        )
        implementations = resolution["discovered_implementations"]
        if implementations:
            selected_implementations.append(implementations[0])
        if resolution["selected_resolution"] == "build_new":
            missing.append(capability_id)
        maturity_rows.append(
            {
                "capability_id": capability_id,
                "selected_resolution": resolution["selected_resolution"],
                "maturity_gaps": resolution["maturity_gaps"],
                "safe_next_step": resolution["safe_next_step"],
            }
        )
    return {
        "schema_version": CAPABILITY_PACKAGE_PLAN_SCHEMA,
        "requested_objective": requested_objective,
        "required_capabilities": list(required_capabilities),
        "selected_implementations": selected_implementations,
        "maturity_status": maturity_rows,
        "denied_actions": list(DEFAULT_DENIED_ACTIONS),
        "authority_required": ["scoped authority per capability before live use"],
        "redaction_policy_refs": ["proof_bundle_redaction_policy_v0"],
        "freshness_policy_refs": ["OPENCLAW_PLUGIN_CONTRACT_V0.freshness_policy"],
        "receipt_requirements": ["capability_resolution_event", "capability_build_request_or_reuse_receipt"],
        "missing_capabilities": missing,
        "recommended_next_safe_step": "Mature existing fixture capabilities before any live access request." if not missing else "Create scoped build requests for missing capabilities.",
        "execution_performed": False,
        "created_at": generated_at,
    }


def latest_resolution_events(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> list[dict[str, Any]]:
    with connect(sqlite_path) as conn:
        rows = conn.execute("SELECT * FROM capability_resolution_events ORDER BY created_at DESC, resolution_id DESC").fetchall()
        return [_row_dict(row) for row in rows]


def latest_build_requests(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> list[dict[str, Any]]:
    with connect(sqlite_path) as conn:
        rows = conn.execute("SELECT * FROM capability_build_requests ORDER BY created_at DESC, build_request_id DESC").fetchall()
        return [_row_dict(row) for row in rows]
