"""SQLite Consolidation Plan V0.

Builds a safe, planning-only consolidation plan from the SQLite governance
registry and canonical state map. It does not open, mutate, move, delete, or
consolidate existing SQLite databases.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/SQLite Consolidation Plan.md")

SCHEMA_VERSION = "sqlite_consolidation_plan_v0"
READ_MODEL_ID = "sqlite_consolidation_plan"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
PLAN_STATUS = "SQLITE_CONSOLIDATION_PLAN_READY"
PLAN_NOT_READY_STATUS = "SQLITE_CONSOLIDATION_PLAN_NOT_READY"

SOURCE_FILES = {
    "sqlite_governance_registry": "sqlite_governance_registry.json",
    "canonical_state_map": "canonical_state_map.json",
    "agentic_chain_inspector": "agentic_chain_inspector.json",
    "package_event_index": "package_event_index.json",
}

PRECONDITION_STATUSES = {
    "sqlite_governance_registry": "SQLITE_GOVERNANCE_REGISTRY_READY",
    "canonical_state_map": "CANONICAL_STATE_MAP_READY",
}

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "database_delete_allowed": False,
    "database_move_allowed": False,
    "database_migration_allowed": False,
    "sqlite_consolidation_allowed": False,
    "sent": False,
    "paid": False,
}

MIGRATION_REQUIREMENTS = (
    "backup",
    "schema_diff",
    "row_count_proof",
    "checksum_or_sample_row_proof",
    "rollback_plan",
    "focused_tests",
    "no_business_ledger_mixing",
    "operator_approval",
)

NEVER_CONSOLIDATE_RULES = (
    "Never consolidate ledger into package DB.",
    "Never consolidate secrets/tokens into read models.",
    "Never consolidate raw prompt bodies into operator journal.",
    "Never consolidate test harness into canonical state.",
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _source_ref(filename: str) -> str:
    return f"generated/read_models/{filename}"


def _sources(read_model_root: Path) -> dict[str, dict[str, Any]]:
    root = _rooted(read_model_root)
    result: dict[str, dict[str, Any]] = {}
    for source_id, filename in SOURCE_FILES.items():
        path = root / filename
        payload = _load_json(path)
        result[source_id] = {
            "source_id": source_id,
            "source_ref": _source_ref(filename),
            "path": path.as_posix(),
            "exists": path.exists(),
            "status": str(payload.get("status") or ""),
            "read_model_id": str(payload.get("read_model_id") or ""),
            "schema_version": str(payload.get("schema_version") or ""),
            "generated_at": str(payload.get("generated_at") or ""),
            "payload": payload,
        }
    return result


def _preconditions(sources: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_id, required in PRECONDITION_STATUSES.items():
        observed = str(sources[source_id].get("status") or "")
        rows.append(
            {
                "precondition_ref": source_id,
                "required_status": required,
                "observed_status": observed,
                "ready": observed == required,
                "source_ref": str(sources[source_id]["source_ref"]),
            }
        )
    return rows


def _compact_db(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "db_ref": str(item.get("db_ref") or ""),
        "path": str(item.get("path") or ""),
        "classification": str(item.get("classification") or ""),
        "owner_lane": str(item.get("owner_lane") or ""),
        "consolidation_risk": str(item.get("consolidation_risk") or ""),
        "canonical_truth_allowed": bool(item.get("canonical_truth_allowed")),
        "consolidation_candidate": bool(item.get("consolidation_candidate")),
        "reason": "",
    }


def _matching(databases: Iterable[Mapping[str, Any]], predicate) -> list[dict[str, Any]]:
    return [_compact_db(item) for item in databases if predicate(item)]


def _with_reason(items: list[dict[str, Any]], reason: str, *, limit: int | None = None) -> list[dict[str, Any]]:
    rows = items if limit is None else items[:limit]
    return [{**item, "reason": reason} for item in rows]


def build_do_not_touch(databases: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    protected_ledgers = _matching(databases, lambda item: item.get("classification") == "protected_business_ledger")
    legacy_archives = _matching(databases, lambda item: item.get("classification") == "legacy_archive")
    unknown = _matching(databases, lambda item: item.get("classification") == "unknown_needs_review")
    token_secret_credential_stores = _matching(
        databases,
        lambda item: any(
            term in f"{item.get('path') or ''} {item.get('purpose') or ''} {item.get('owner_lane') or ''}".lower()
            for term in ("token", "secret", "credential", "vault")
        ),
    )
    protected_evidence = _matching(
        databases,
        lambda item: item.get("owner_lane") == "privacy"
        or "token_vault" in str(item.get("path") or "").lower()
        or "protected" in str(item.get("path") or "").lower(),
    )
    return [
        {
            "category": "protected_business_ledger",
            "policy": "do_not_touch",
            "reason": "Business ledger and ledger-shaped databases are protected; consolidation risk is forbidden.",
            "count": len(protected_ledgers),
            "databases": _with_reason(protected_ledgers, "protected business ledger", limit=25),
        },
        {
            "category": "legacy_archives",
            "policy": "do_not_touch",
            "reason": "Archives/backups remain historical evidence until separately reviewed.",
            "count": len(legacy_archives),
            "databases": _with_reason(legacy_archives, "legacy archive", limit=25),
        },
        {
            "category": "unknown_needs_review",
            "policy": "do_not_touch",
            "reason": "Unknown ownership defaults to no writes and manual review.",
            "count": len(unknown),
            "databases": _with_reason(unknown, "unknown owner or truth posture", limit=25),
        },
        {
            "category": "protected_evidence",
            "policy": "do_not_touch",
            "reason": "Privacy/protected evidence such as token vaults must never enter read-model consolidation.",
            "count": len(protected_evidence),
            "databases": _with_reason(protected_evidence, "protected evidence or token/privacy store", limit=25),
        },
        {
            "category": "token_secret_credential_stores",
            "policy": "do_not_touch",
            "reason": "Token, secret, credential, and vault stores must not enter read-model or workflow consolidation.",
            "count": len(token_secret_credential_stores),
            "databases": _with_reason(token_secret_credential_stores, "token/secret/credential/vault store", limit=25),
        },
    ]


def build_keep_isolated(databases: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    test_harness = _matching(databases, lambda item: item.get("classification") == "test_harness")
    generated_status = _matching(databases, lambda item: item.get("classification") == "generated_status")
    generated_proof = _matching(databases, lambda item: item.get("classification") == "generated_evidence")
    dry_run_warmup = _matching(
        databases,
        lambda item: any(
            term in f"{item.get('path') or ''} {item.get('purpose') or ''}".lower()
            for term in ("dry_run", "dry-run", "warmup", "smoke")
        ),
    )
    one_off = [
        item
        for item in generated_proof
        if item["owner_lane"] in {"unknown_review", "system_health", "agentic_chain_inspector", "sqlite_governance"}
        or any(term in item["path"].lower() for term in ("proof", "audit", "resolver", "harvest", "sidecar"))
    ]
    return [
        {
            "category": "test_harness",
            "policy": "keep_isolated",
            "reason": "Test harness and pytest databases cannot become canonical truth.",
            "count": len(test_harness),
            "databases": _with_reason(test_harness, "test fixture or simulation state", limit=25),
        },
        {
            "category": "generated_proof_status_dbs",
            "policy": "keep_isolated",
            "reason": "Generated proof/status stores are evidence unless a future owner map proves otherwise.",
            "count": len(generated_status) + len(generated_proof),
            "databases": _with_reason(generated_status + generated_proof, "generated proof/status evidence", limit=30),
        },
        {
            "category": "one_off_read_model_proof_dbs",
            "policy": "keep_isolated",
            "reason": "One-off proof/read-model databases should stay as source evidence, not merged into canonical workflow state.",
            "count": len(one_off),
            "databases": _with_reason(one_off, "one-off read-model/proof database", limit=30),
        },
        {
            "category": "dry_run_warmup_dbs",
            "policy": "keep_isolated",
            "reason": "Dry-run, smoke, and warmup databases are validation artifacts, not canonical state.",
            "count": len(dry_run_warmup),
            "databases": _with_reason(dry_run_warmup, "dry-run/warmup/smoke database", limit=30),
        },
    ]


def _candidate(source: str, concept: str, sources: list[str], plan: str, risk: str, blockers: list[str]) -> dict[str, Any]:
    return {
        "candidate_ref": source,
        "concept": concept,
        "source_refs": sources,
        "recommended_plan": plan,
        "risk": risk,
        "blocked_until": blockers,
        "migration_allowed_now": False,
    }


def build_consolidation_candidates(
    *,
    databases: list[Mapping[str, Any]],
    canonical_state_map: Mapping[str, Any],
    package_event_index: Mapping[str, Any],
) -> list[dict[str, Any]]:
    by_owner = {}
    for item in databases:
        by_owner.setdefault(str(item.get("owner_lane") or ""), []).append(str(item.get("path") or ""))
    source_systems = package_event_index.get("source_systems") if isinstance(package_event_index.get("source_systems"), Mapping) else {}
    workflow_sqlite = ""
    journal_sqlite = ""
    if isinstance(source_systems, Mapping):
        workflow_sqlite = str((source_systems.get("workflow_package_queue_sqlite") or {}).get("path") or "")
        journal_sqlite = str((source_systems.get("operator_conversation_journal_sqlite") or {}).get("path") or "")
    domains = {
        str(domain.get("domain_ref")): domain
        for domain in canonical_state_map.get("domains", [])
        if isinstance(domain, Mapping)
    }
    package_ref = (domains.get("package_queue") or {}).get("canonical_source", {}).get("source_ref", "")
    request_ref = (domains.get("request_response") or {}).get("canonical_source", {}).get("source_ref", "")
    conversation_ref = (domains.get("conversation_journal") or {}).get("canonical_source", {}).get("source_ref", "")
    work_log_ref = (domains.get("st_annes_work_log") or {}).get("canonical_source", {}).get("source_ref", "")
    common_blockers = [
        "backup",
        "schema_diff",
        "row_count_proof",
        "rollback_plan",
        "test_coverage",
        "no_business_ledger_mixing",
        "operator_approval",
    ]
    return [
        _candidate(
            "package_queue_event_concepts",
            "Package queue package/gate/event concepts",
            [str(package_ref), "generated/read_models/package_event_index.json", workflow_sqlite],
            "Create a read-only package_event_overlay view/index plan over package queue and package_event_index refs; do not migrate source DB rows.",
            "medium",
            common_blockers,
        ),
        _candidate(
            "request_response_index_concepts",
            "Mission Control request/response index concepts",
            [str(request_ref), "generated/read_models/package_event_index.json"],
            "Use package_event_index as the first overlay; add derived views/indexes only after proving request/response refs and counts.",
            "low",
            common_blockers,
        ),
        _candidate(
            "operator_conversation_index_concepts",
            "Operator conversation index concepts",
            [str(conversation_ref), journal_sqlite],
            "Create a derived index that joins journal entry refs to package_event_index refs; keep journal as canonical history.",
            "medium",
            common_blockers,
        ),
        _candidate(
            "work_log_staging_if_safe",
            "St. Anne's work-log staging indexes if safe",
            [str(work_log_ref), *by_owner.get("invoice_operations", [])],
            "Keep staged work logs isolated until operator confirmation; future overlay may expose package/work-log staging indexes without workbook mutation.",
            "medium",
            [*common_blockers, "operator_confirmation_for_invoice_inclusion"],
        ),
    ]


def build_migration_requirements() -> list[dict[str, str]]:
    descriptions = {
        "backup": "Create verified backups of every source database before any future write.",
        "schema_diff": "Compare schemas and table contracts before creating any overlay or migration target.",
        "row_count_proof": "Record pre/post row counts for every affected table.",
        "checksum_or_sample_row_proof": "Record checksums or sample-row proof for every affected table before and after any future write.",
        "rollback_plan": "Document exact rollback steps and owners before changes.",
        "focused_tests": "Add focused tests for joins, refs, permissions, and forbidden state mixing.",
        "no_business_ledger_mixing": "Prove protected ledger databases are excluded from package/agent/read-model stores.",
        "operator_approval": "Require explicit operator approval for any database write, index, view, migration, move, or delete.",
    }
    return [
        {
            "requirement_ref": requirement,
            "required_before_consolidation": "yes",
            "description": descriptions[requirement],
        }
        for requirement in MIGRATION_REQUIREMENTS
    ]


def build_read_model(*, read_model_root: Path = DEFAULT_READ_MODEL_ROOT, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    sources = _sources(read_model_root)
    preconditions = _preconditions(sources)
    registry = sources["sqlite_governance_registry"]["payload"]
    canonical = sources["canonical_state_map"]["payload"]
    inspector = sources["agentic_chain_inspector"]["payload"]
    package_index = sources["package_event_index"]["payload"]
    databases = registry.get("databases") if isinstance(registry.get("databases"), list) else []
    do_not_touch = build_do_not_touch(databases)
    keep_isolated = build_keep_isolated(databases)
    candidates = build_consolidation_candidates(
        databases=databases,
        canonical_state_map=canonical,
        package_event_index=package_index,
    )
    ready = all(item["ready"] for item in preconditions) and all(sources[key]["exists"] for key in SOURCE_FILES)
    risk_counts = Counter(str(item.get("consolidation_risk") or "") for item in databases)
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": PLAN_STATUS if ready else PLAN_NOT_READY_STATUS,
        "purpose": "Planning-only SQLite consolidation plan based on governance registry, canonical state map, agentic chain inspector, and package event index.",
        "mode": "plan_only_no_migration",
        "preconditions": preconditions,
        "source_refs": {
            source_id: {
                "source_ref": str(source["source_ref"]),
                "status": str(source["status"]),
                "exists": bool(source["exists"]),
            }
            for source_id, source in sources.items()
        },
        "registry_summary": {
            "database_count": registry.get("database_count"),
            "classification_counts": registry.get("classification_counts", {}),
            "consolidation_candidate_count": registry.get("consolidation_candidate_count"),
            "unknown_review_count": registry.get("unknown_review_count"),
            "risk_counts": dict(risk_counts),
        },
        "canonical_domain_refs": [
            str(domain.get("domain_ref"))
            for domain in canonical.get("domains", [])
            if isinstance(domain, Mapping)
        ],
        "agentic_chain_risk_refs": [
            {
                "risk_id": str(risk.get("risk_id") or ""),
                "severity": str(risk.get("severity") or ""),
                "affected_path_count": risk.get("affected_path_count"),
            }
            for risk in inspector.get("fragmentation_risks", [])
            if isinstance(risk, Mapping)
        ],
        "do_not_touch_databases": do_not_touch,
        "keep_isolated_databases": keep_isolated,
        "consolidation_candidates": candidates,
        "recommended_first_low_risk_move": {
            "move_ref": "read_only_views_and_indexes_overlay",
            "summary": "Create views/indexes over existing package/event/journal refs, not a data migration; use package_event_index as the cross-reference layer.",
            "plan_only": True,
            "write_allowed_now": False,
            "notes": [
                "This task does not create the views or indexes.",
                "Do not migrate source DBs.",
                "Do not alter ledger.",
                "Use package_event_index as the cross-reference layer between package queue, request/response, and operator conversation refs.",
                "If indexes/views are written inside existing databases later, that still requires operator approval.",
                "A detached generated overlay/read-model is lower risk than altering canonical source databases.",
            ],
        },
        "migration_requirements_before_any_consolidation": build_migration_requirements(),
        "never_consolidate": list(NEVER_CONSOLIDATE_RULES),
        "unknown_db_policy": {
            "classification": "unknown_needs_review",
            "policy": "read_only_review_required",
            "writable_by_automation": False,
            "delete_allowed": False,
            "migration_allowed": False,
            "required_next_packet": "classification_packet_later",
            "notes": [
                "Unknown DBs stay read-only.",
                "No deletion.",
                "No migration.",
                "Require a classification packet before any future consolidation decision.",
            ],
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "plan_only": True,
            "preconditions_ready": all(item["ready"] for item in preconditions),
            "existing_database_mutation_performed": False,
            "database_consolidation_performed": False,
            "database_move_performed": False,
            "database_delete_performed": False,
            "database_migration_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "unsafe_true_grants_absent": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# SQLite Consolidation Plan",
        "",
        f"Status: `{read_model['status']}`",
        "",
        "This is a planning-only consolidation map. It does not migrate, move, delete, or mutate existing databases.",
        "",
        "## Do Not Touch",
        "",
    ]
    for bucket in read_model["do_not_touch_databases"]:
        lines.append(f"- `{bucket['category']}`: {bucket['count']} DBs. {bucket['reason']}")
    lines.extend(["", "## Keep Isolated", ""])
    for bucket in read_model["keep_isolated_databases"]:
        lines.append(f"- `{bucket['category']}`: {bucket['count']} DBs. {bucket['reason']}")
    lines.extend(["", "## Consolidation Candidates", ""])
    for candidate in read_model["consolidation_candidates"]:
        lines.append(f"- `{candidate['candidate_ref']}` ({candidate['risk']}): {candidate['recommended_plan']}")
    lines.extend(
        [
            "",
            "## Recommended First Low-Risk Move",
            "",
            f"{read_model['recommended_first_low_risk_move']['summary']} This remains plan-only here.",
            "",
            "## Migration Requirements",
            "",
        ]
    )
    for requirement in read_model["migration_requirements_before_any_consolidation"]:
        lines.append(f"- `{requirement['requirement_ref']}`: {requirement['description']}")
    lines.extend(["", "## Never Consolidate", ""])
    for rule in read_model["never_consolidate"]:
        lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No database consolidation, move, delete, migration, or existing DB mutation.",
            "- No ledger, workbook, email, Gmail, browser, Coupa, paid marking, submit, or push.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_sqlite_consolidation_plan(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
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

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model["status"]),
        "read_model_path": local_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
        "candidate_count": str(len(read_model["consolidation_candidates"])),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export SQLite Consolidation Plan V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_sqlite_consolidation_plan(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == PLAN_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
