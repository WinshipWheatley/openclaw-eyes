"""System Question Answer V0.

Deterministic, local-only answers about OpenClaw state, gates, agents,
packages, and receipts. This module reads local JSON read models, local wiki
files, and SQLite schema/count metadata only. It does not call an external LLM,
spawn child agents, run loops, execute providers, mutate business state, send
email, open browser/Gmail/Coupa, touch workbooks, export PDFs, submit portals,
or mark paid/sent.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_WIKI_ROOT = Path("generated/wiki/openclaw")
DEFAULT_SQLITE_ROOT = Path("generated/system_knowledge")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/System Question Answering.md")

SCHEMA_VERSION = "system_question_answer_v0"
READ_MODEL_ID = "system_question_answer_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
CONTRACT_STATUS = "SYSTEM_QUESTION_ANSWER_V0_READY"
WORKFLOW_REF = "system_question_answer"

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "sent": False,
    "paid": False,
}

SOURCE_SCOPE = {
    "json_read_models": "generated/read_models/*.json",
    "operator_wiki": "generated/wiki/openclaw/*.md",
    "sqlite_metadata_only": "generated/system_knowledge/*.sqlite",
    "operations_docs": "docs/operations/*.md",
    "doctrine_docs": "docs/doctrine/*.md",
}

CORE_SOURCE_REFS = {
    "workflow_package_queue": "generated/read_models/workflow_package_queue_contract.json",
    "automation_permission_registry": "generated/read_models/automation_permission_registry.json",
    "operator_assist_provider_registry": "generated/read_models/operator_assist_provider_registry.json",
    "agent_voice_routing": "generated/read_models/agent_voice_routing_contract.json",
    "agent_voice_profiles": "generated/read_models/agent_voice_profiles.json",
    "operator_conversation_journal": "generated/read_models/operator_conversation_journal.json",
    "overnight_workboard": "generated/read_models/overnight_workboard.json",
    "st_annes_work_log_events": "generated/read_models/st_annes_work_log_events.json",
    "st_annes_monthly_work_log_contract": "generated/read_models/st_annes_monthly_work_log_contract.json",
    "operator_human_readability_surface": "generated/read_models/operator_human_readability_surface.json",
    "openclaw_lm_child_package_gate": "generated/read_models/openclaw_lm_child_package_gate.json",
    "role_package_gate": "generated/read_models/role_package_gate.json",
    "package_event_index": "generated/read_models/package_event_index.json",
    "sqlite_governance_registry": "generated/read_models/sqlite_governance_registry.json",
    "canonical_state_map": "generated/read_models/canonical_state_map.json",
    "sqlite_consolidation_plan": "generated/read_models/sqlite_consolidation_plan.json",
}

EXAMPLE_QUESTIONS = (
    "What is the difference between Chief and a spawned worker?",
    "Why did Submit Capital Hilton invoice block?",
    "Can this send email?",
    "What does SQLite know about St. Anne's work logs?",
    "What is safe next?",
    "What are all these databases?",
    "Which database owns package truth?",
    "Which database owns St. Anne's work logs?",
    "Can we consolidate SQLite?",
    "Is the ledger mixed into this?",
    "What is safe to clean up?",
    "What should never be merged?",
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _normalize(text: str) -> str:
    return " ".join(str(text or "").strip().split())


def _safe_question(question: str, *, max_chars: int = 240) -> str:
    cleaned = _normalize(question)
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 14].rstrip() + " [truncated]"


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _source_ref(filename: str) -> str:
    return f"generated/read_models/{filename}"


def _source_exists(ref: str) -> bool:
    return _rooted(Path(ref)).exists()


def _existing_refs(*refs: str) -> list[str]:
    return [ref for ref in refs if _source_exists(ref)]


def _sqlite_metadata(sqlite_path: Path) -> dict[str, Any]:
    sqlite_path = _rooted(sqlite_path)
    if not sqlite_path.exists():
        return {
            "path": sqlite_path.as_posix(),
            "exists": False,
            "tables": [],
            "table_counts": {},
        }
    conn = sqlite3.connect(sqlite_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        tables = [str(row[0]) for row in rows]
        counts: dict[str, int | str] = {}
        for table in tables:
            try:
                quoted = '"' + table.replace('"', '""') + '"'
                counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0])
            except sqlite3.DatabaseError:
                counts[table] = "unavailable"
        return {
            "path": sqlite_path.as_posix(),
            "exists": True,
            "tables": tables,
            "table_counts": counts,
        }
    finally:
        conn.close()


def _load_sources(read_model_root: Path, sqlite_root: Path) -> dict[str, Any]:
    read_model_root = _rooted(read_model_root)
    sqlite_root = _rooted(sqlite_root)
    return {
        "workflow_package_queue": _load_json_file(read_model_root / "workflow_package_queue_contract.json"),
        "automation_permission_registry": _load_json_file(read_model_root / "automation_permission_registry.json"),
        "operator_assist_provider_registry": _load_json_file(read_model_root / "operator_assist_provider_registry.json"),
        "agent_voice_routing": _load_json_file(read_model_root / "agent_voice_routing_contract.json"),
        "agent_voice_profiles": _load_json_file(read_model_root / "agent_voice_profiles.json"),
        "operator_conversation_journal": _load_json_file(read_model_root / "operator_conversation_journal.json"),
        "overnight_workboard": _load_json_file(read_model_root / "overnight_workboard.json"),
        "st_annes_work_log_events": _load_json_file(read_model_root / "st_annes_work_log_events.json"),
        "st_annes_monthly_work_log_contract": _load_json_file(read_model_root / "st_annes_monthly_work_log_contract.json"),
        "operator_human_readability_surface": _load_json_file(read_model_root / "operator_human_readability_surface.json"),
        "openclaw_lm_child_package_gate": _load_json_file(read_model_root / "openclaw_lm_child_package_gate.json"),
        "role_package_gate": _load_json_file(read_model_root / "role_package_gate.json"),
        "package_event_index": _load_json_file(read_model_root / "package_event_index.json"),
        "sqlite_governance_registry": _load_json_file(read_model_root / "sqlite_governance_registry.json"),
        "canonical_state_map": _load_json_file(read_model_root / "canonical_state_map.json"),
        "sqlite_consolidation_plan": _load_json_file(read_model_root / "sqlite_consolidation_plan.json"),
        "st_annes_work_log_sqlite": _sqlite_metadata(sqlite_root / "st_annes_monthly_work_log.sqlite"),
        "workflow_package_queue_sqlite": _sqlite_metadata(sqlite_root / "workflow_package_queue.sqlite"),
    }


def speaker_for_question(question: str) -> tuple[str, str]:
    text = question.lower()
    safety_terms = (
        "can this send",
        "send email",
        "send authority",
        "email authority",
        "safe next",
        "ledger",
        "ledger mixed",
        "paid",
        "submit allowed",
        "authority",
        "safe to clean",
        "cleanup",
        "clean up",
        "never merge",
        "never be merged",
        "should never be merged",
    )
    diagnostic_terms = (
        "why did",
        "block",
        "blocked",
        "package",
        "gate",
        "sqlite",
        "receipt",
        "proof",
        "request",
        "database",
        "databases",
        "truth",
        "owns",
        "owner",
    )
    architecture_terms = (
        "difference",
        "chief",
        "spawned worker",
        "worker",
        "agent",
        "architecture",
        "system design",
        "lm2",
        "child",
        "consolidate",
        "consolidation",
        "merge",
        "merged",
    )
    if any(term in text for term in safety_terms):
        return "guardian", "safety_gate"
    if any(term in text for term in diagnostic_terms):
        return "chief", "diagnostic"
    if any(term in text for term in architecture_terms):
        return "hermes", "recommendation"
    return "openclaw", "operator_calm"


def _package_by_workflow(queue_payload: Mapping[str, Any], workflow_ref: str) -> dict[str, Any]:
    packages = queue_payload.get("packages")
    if isinstance(packages, list):
        for package in packages:
            if isinstance(package, dict) and package.get("workflow_ref") == workflow_ref:
                return package
    fixtures = queue_payload.get("fixtures_summary")
    if isinstance(fixtures, list):
        for fixture in fixtures:
            if isinstance(fixture, dict) and fixture.get("workflow_ref") == workflow_ref:
                return dict(fixture)
    return {}


def _answer_payload(
    *,
    speaker_ref: str,
    voice_mode: str,
    question: str,
    headline: str,
    plain_summary: str,
    confirmed: list[str],
    inferred: list[str] | None = None,
    unknown: list[str] | None = None,
    next_safe_action: str,
    proof_refs: list[str],
) -> dict[str, Any]:
    return {
        "workflow_ref": WORKFLOW_REF,
        "speaker_ref": speaker_ref,
        "voice_profile_ref": f"agent_voice_profile:{speaker_ref}",
        "voice_mode": voice_mode,
        "question": _safe_question(question),
        "privacy_impact": "local_only",
        "answer": {
            "headline": headline,
            "plain_summary": plain_summary,
            "confirmed": confirmed,
            "inferred": inferred or [],
            "unknown": unknown or [],
            "next_safe_action": next_safe_action,
            "proof_refs": list(dict.fromkeys(proof_refs)),
            "show_machine_details_by_default": False,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "local_only": True,
            "external_llm_called": False,
            "child_agent_spawned": False,
            "live_execution_performed": False,
            "email_send_performed": False,
            "ledger_mutation_performed": False,
            "browser_access_performed": False,
            "gmail_access_performed": False,
            "coupa_access_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "unsafe_true_grants_absent": True,
        },
    }


def _chief_vs_worker_answer(question: str, sources: Mapping[str, Any]) -> dict[str, Any]:
    speaker_ref, voice_mode = "hermes", "recommendation"
    proof_refs = _existing_refs(
        CORE_SOURCE_REFS["agent_voice_routing"],
        CORE_SOURCE_REFS["workflow_package_queue"],
        CORE_SOURCE_REFS["openclaw_lm_child_package_gate"],
        CORE_SOURCE_REFS["role_package_gate"],
        CORE_SOURCE_REFS["overnight_workboard"],
    )
    confirmed = [
        "Chief is a named OpenClaw role for diagnostics, bounded task packaging, and operator-facing status. It shapes plans and copy through local contracts.",
        "A spawned worker is a package-bound execution thread: it should have explicit inputs, allowed actions, blocked actions, receipts, and authority boundaries.",
        "Current LM2 and child-spawning paths are contract or shadow posture here; this answer did not call LM2 or spawn a child worker.",
    ]
    inferred = [
        "Use Chief to explain a gate or package work; use a worker only after a specific gated package authorizes bounded execution.",
    ]
    if sources.get("openclaw_lm_child_package_gate"):
        inferred.append("The child-package gate read model is available as proof, but live child execution remains outside this workflow.")
    return _answer_payload(
        speaker_ref=speaker_ref,
        voice_mode=voice_mode,
        question=question,
        headline="Chief packages work; workers execute packages",
        plain_summary="Chief is a hardwired diagnostic role, while a spawned worker is a bounded package execution thread.",
        confirmed=confirmed,
        inferred=inferred,
        unknown=[],
        next_safe_action="Keep this as explanation only; do not spawn workers without a gated package.",
        proof_refs=proof_refs,
    )


def _capital_hilton_block_answer(question: str, sources: Mapping[str, Any]) -> dict[str, Any]:
    queue_payload = sources.get("workflow_package_queue") if isinstance(sources.get("workflow_package_queue"), dict) else {}
    package = _package_by_workflow(queue_payload, "capital_hilton_invoice_operator_assist")
    capability = package.get("capability_gate_result") if isinstance(package.get("capability_gate_result"), Mapping) else {}
    reason = str(capability.get("reason") or "Operator-assist provider and final Submit gate are not explicitly staged.")
    package_status = str(package.get("status") or "PROVIDER_GATE_REQUIRED")
    proof_refs = _existing_refs(
        CORE_SOURCE_REFS["workflow_package_queue"],
        CORE_SOURCE_REFS["automation_permission_registry"],
        CORE_SOURCE_REFS["operator_assist_provider_registry"],
        CORE_SOURCE_REFS["operator_conversation_journal"],
    )
    return _answer_payload(
        speaker_ref="chief",
        voice_mode="diagnostic",
        question=question,
        headline="Capital Hilton is blocked by provider gates",
        plain_summary="The submit package is blocked because Coupa requires operator assist and a final Submit gate.",
        confirmed=[
            f"The package status is {package_status}.",
            f"The capability gate reason is: {reason}",
            "No Coupa action, portal submit, email send, ledger mutation, or paid marking is authorized by this answer.",
        ],
        inferred=[
            "The gate owner is the capability/provider gate first, then the final business action gate before any live submit.",
        ],
        unknown=[],
        next_safe_action="Stage an operator-assist packet with an explicit final Submit gate if the operator wants to continue later.",
        proof_refs=proof_refs,
    )


def _email_authority_answer(question: str, sources: Mapping[str, Any]) -> dict[str, Any]:
    automation = sources.get("automation_permission_registry") if isinstance(sources.get("automation_permission_registry"), dict) else {}
    statuses = automation.get("permission_statuses") if isinstance(automation.get("permission_statuses"), Mapping) else {}
    gmail_status = str(statuses.get("gmail_send") or "blocked_until_explicit_send_gate")
    proof_refs = _existing_refs(
        CORE_SOURCE_REFS["automation_permission_registry"],
        CORE_SOURCE_REFS["workflow_package_queue"],
        CORE_SOURCE_REFS["operator_assist_provider_registry"],
    )
    return _answer_payload(
        speaker_ref="guardian",
        voice_mode="safety_gate",
        question=question,
        headline="Email send authority is closed",
        plain_summary="No email can be sent unless a separate explicit send gate is recorded.",
        confirmed=[
            f"Gmail/email send is recorded as {gmail_status}.",
            "The default workflow package authority boundary has email_send_allowed=false.",
            "This system question workflow never sends email.",
        ],
        inferred=[
            "A draft or follow-up plan can be staged locally, but sending requires a separate operator-approved send receipt.",
        ],
        unknown=[
            "This question did not identify a specific package or artifact to send.",
        ],
        next_safe_action="Keep the business action gate closed until an explicit send approval exists.",
        proof_refs=proof_refs,
    )


def _domain_by_ref(state_map: Mapping[str, Any], domain_ref: str) -> dict[str, Any]:
    domains = state_map.get("domains")
    if isinstance(domains, list):
        for domain in domains:
            if isinstance(domain, Mapping) and domain.get("domain_ref") == domain_ref:
                return dict(domain)
    return {}


def _dbs_by_owner(
    registry: Mapping[str, Any],
    owner_lane: str,
    *,
    classification: str | None = None,
) -> list[dict[str, Any]]:
    databases = registry.get("databases")
    if not isinstance(databases, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in databases:
        if not isinstance(item, Mapping):
            continue
        if item.get("owner_lane") != owner_lane:
            continue
        if classification is not None and item.get("classification") != classification:
            continue
        rows.append(dict(item))
    return rows


def _classification_summary(registry: Mapping[str, Any]) -> str:
    counts = registry.get("classification_counts")
    if not isinstance(counts, Mapping) or not counts:
        return "classification counts unavailable"
    order = (
        "canonical_workflow_state",
        "generated_evidence",
        "generated_status",
        "test_harness",
        "protected_business_ledger",
        "unknown_needs_review",
    )
    parts = [f"{key}={counts.get(key, 0)}" for key in order if key in counts]
    return ", ".join(parts) if parts else "classification counts unavailable"


def _join_policy_items(items: list[Any], fallback: str) -> str:
    parts = [str(item).strip().rstrip(".") for item in items if str(item).strip()]
    return ", ".join(parts) if parts else fallback


def _database_inventory_answer(question: str, sources: Mapping[str, Any]) -> dict[str, Any]:
    registry = sources.get("sqlite_governance_registry") if isinstance(sources.get("sqlite_governance_registry"), dict) else {}
    database_count = registry.get("database_count", "unknown")
    unknown_count = registry.get("unknown_review_count", "unknown")
    protected_count = registry.get("protected_ledger_count", "unknown")
    proof_refs = _existing_refs(
        CORE_SOURCE_REFS["sqlite_governance_registry"],
        CORE_SOURCE_REFS["canonical_state_map"],
        CORE_SOURCE_REFS["sqlite_consolidation_plan"],
        "generated/read_models/agentic_chain_inspector.json",
    )
    return _answer_payload(
        speaker_ref="chief",
        voice_mode="diagnostic",
        question=question,
        headline="SQLite databases are classified by ownership",
        plain_summary="OpenClaw has workflow state, generated evidence, generated status, test harness, protected ledger, and unknown-review database classes.",
        confirmed=[
            f"The SQLite governance registry currently classifies {database_count} databases.",
            f"Classification counts: {_classification_summary(registry)}.",
            f"Protected ledger entries: {protected_count}; unknown review entries: {unknown_count}.",
            "The canonical state map explains which read model owns each truth domain.",
        ],
        inferred=[
            "The ledger is protected and not part of package consolidation; most entries are not consolidation targets.",
        ],
        unknown=[],
        next_safe_action="Ask for one domain, such as package truth, work logs, ledger, or cleanup posture.",
        proof_refs=proof_refs,
    )


def _package_truth_owner_answer(question: str, sources: Mapping[str, Any]) -> dict[str, Any]:
    registry = sources.get("sqlite_governance_registry") if isinstance(sources.get("sqlite_governance_registry"), dict) else {}
    state_map = sources.get("canonical_state_map") if isinstance(sources.get("canonical_state_map"), dict) else {}
    domain = _domain_by_ref(state_map, "package_queue")
    source = domain.get("canonical_source") if isinstance(domain.get("canonical_source"), Mapping) else {}
    queue_dbs = _dbs_by_owner(registry, "workflow_package_queue", classification="canonical_workflow_state")
    db_path = str(queue_dbs[0].get("path") or "generated/system_knowledge/workflow_package_queue.sqlite") if queue_dbs else "generated/system_knowledge/workflow_package_queue.sqlite"
    proof_refs = _existing_refs(
        CORE_SOURCE_REFS["canonical_state_map"],
        CORE_SOURCE_REFS["sqlite_governance_registry"],
        CORE_SOURCE_REFS["workflow_package_queue"],
        CORE_SOURCE_REFS["package_event_index"],
    )
    proof_refs.append(db_path)
    return _answer_payload(
        speaker_ref="chief",
        voice_mode="diagnostic",
        question=question,
        headline="Package truth lives in the package queue",
        plain_summary="Package status truth comes from the workflow package queue, with the package event index as the request/response index.",
        confirmed=[
            f"Canonical state map source: {source.get('source_ref', CORE_SOURCE_REFS['workflow_package_queue'])}.",
            f"SQLite governance owner lane: workflow_package_queue at {db_path}.",
            "Package status truth comes from package queue / package event index.",
        ],
        inferred=[
            "Mission Control should cite package queue status first, then use package_event_index for response and proof linkage.",
        ],
        unknown=[],
        next_safe_action="Use the package id or workflow_ref to inspect local package proof; do not mutate package rows from an answer.",
        proof_refs=proof_refs,
    )


def _st_annes_work_log_owner_answer(question: str, sources: Mapping[str, Any]) -> dict[str, Any]:
    registry = sources.get("sqlite_governance_registry") if isinstance(sources.get("sqlite_governance_registry"), dict) else {}
    state_map = sources.get("canonical_state_map") if isinstance(sources.get("canonical_state_map"), dict) else {}
    domain = _domain_by_ref(state_map, "st_annes_work_log")
    source = domain.get("canonical_source") if isinstance(domain.get("canonical_source"), Mapping) else {}
    invoice_dbs = _dbs_by_owner(registry, "invoice_operations")
    work_log_db = next(
        (
            str(item.get("path") or "")
            for item in invoice_dbs
            if "st_annes_monthly_work_log.sqlite" in str(item.get("path") or "")
        ),
        "generated/system_knowledge/st_annes_monthly_work_log.sqlite",
    )
    proof_refs = _existing_refs(
        CORE_SOURCE_REFS["canonical_state_map"],
        CORE_SOURCE_REFS["sqlite_governance_registry"],
        CORE_SOURCE_REFS["st_annes_work_log_events"],
        CORE_SOURCE_REFS["st_annes_monthly_work_log_contract"],
    )
    proof_refs.append(work_log_db)
    return _answer_payload(
        speaker_ref="chief",
        voice_mode="diagnostic",
        question=question,
        headline="St Anne's work-log truth has a local owner",
        plain_summary="Operator-facing St Anne's work-log truth comes from the work-log read model, backed by the local staging SQLite database.",
        confirmed=[
            f"Canonical state map source: {source.get('source_ref', CORE_SOURCE_REFS['st_annes_work_log_events'])}.",
            f"St Anne's work-log SQLite staging database: {work_log_db}.",
            "St Anne's staged work logs do not become invoice truth until operator confirmation.",
        ],
        inferred=[
            "Use the read model for plain answers and the SQLite metadata as proof that staging tables exist.",
        ],
        unknown=[],
        next_safe_action="Ask for confirmed versus staged work-log status; do not mutate workbook cells or invoice inclusion from this answer.",
        proof_refs=proof_refs,
    )


def _sqlite_consolidation_answer(question: str, sources: Mapping[str, Any]) -> dict[str, Any]:
    plan = sources.get("sqlite_consolidation_plan") if isinstance(sources.get("sqlite_consolidation_plan"), dict) else {}
    first_move = plan.get("recommended_first_low_risk_move") if isinstance(plan.get("recommended_first_low_risk_move"), Mapping) else {}
    requirements = plan.get("migration_requirements_before_any_consolidation")
    requirement_names = [
        str(item.get("requirement_ref"))
        for item in requirements
        if isinstance(item, Mapping) and item.get("requirement_ref")
    ] if isinstance(requirements, list) else []
    proof_refs = _existing_refs(
        CORE_SOURCE_REFS["sqlite_consolidation_plan"],
        CORE_SOURCE_REFS["sqlite_governance_registry"],
        CORE_SOURCE_REFS["canonical_state_map"],
    )
    return _answer_payload(
        speaker_ref="hermes",
        voice_mode="recommendation",
        question=question,
        headline="SQLite consolidation is plan-only",
        plain_summary="Do not consolidate yet; the safe first move is a package-event-index-backed views/indexes overlay, not migration.",
        confirmed=[
            "The current consolidation plan status is plan-only and migration_allowed_now=false for each candidate.",
            f"First low-risk move: {first_move.get('summary', 'Create views/indexes over existing DB refs, not migration.')}",
            f"Required before any consolidation: {', '.join(requirement_names) if requirement_names else 'backup, schema diff, row-count proof, rollback plan, tests, no ledger mixing, operator approval'}.",
        ],
        inferred=[
            "The package event index and canonical state map are the cross-reference layer before any consolidation attempt.",
        ],
        unknown=[],
        next_safe_action="Review the plan and create a non-mutating overlay design; do not create views, indexes, or migrations yet.",
        proof_refs=proof_refs,
    )


def _ledger_isolation_answer(question: str, sources: Mapping[str, Any]) -> dict[str, Any]:
    registry = sources.get("sqlite_governance_registry") if isinstance(sources.get("sqlite_governance_registry"), dict) else {}
    plan = sources.get("sqlite_consolidation_plan") if isinstance(sources.get("sqlite_consolidation_plan"), dict) else {}
    protected_count = registry.get("protected_ledger_count", "unknown")
    never_rules = plan.get("never_consolidate") if isinstance(plan.get("never_consolidate"), list) else []
    never_summary = _join_policy_items(
        never_rules,
        "ledger into package DB; secrets/tokens into read models; raw prompt bodies into operator journal",
    )
    proof_refs = _existing_refs(
        CORE_SOURCE_REFS["sqlite_governance_registry"],
        CORE_SOURCE_REFS["canonical_state_map"],
        CORE_SOURCE_REFS["sqlite_consolidation_plan"],
        CORE_SOURCE_REFS["package_event_index"],
    )
    return _answer_payload(
        speaker_ref="guardian",
        voice_mode="safety_gate",
        question=question,
        headline="Ledger stays isolated",
        plain_summary="The ledger is not a package/read-model truth store and must not be mixed into SQLite consolidation.",
        confirmed=[
            f"SQLite governance marks {protected_count} ledger-shaped entries as protected_business_ledger.",
            "Business ledger consolidation risk is forbidden.",
            "Paid truth never comes from proposal, email send, manual send, Coupa submit, or invoice artifact alone.",
        ],
        inferred=[
            "Package/event read models may reference ledger exclusion policy, but they must not read, merge, or mutate ledger rows.",
            f"Never-consolidate rules include: {never_summary}.",
        ],
        unknown=[],
        next_safe_action="Keep ledger and protected stores out of package/event consolidation unless a separate approved payment-evidence workflow exists.",
        proof_refs=proof_refs,
    )


def _never_merge_answer(question: str, sources: Mapping[str, Any]) -> dict[str, Any]:
    plan = sources.get("sqlite_consolidation_plan") if isinstance(sources.get("sqlite_consolidation_plan"), dict) else {}
    never_rules = plan.get("never_consolidate") if isinstance(plan.get("never_consolidate"), list) else []
    never_summary = _join_policy_items(
        never_rules,
        "ledger into package DB; secrets/tokens into read models; raw prompt bodies into operator journal; test harness into canonical state",
    )
    do_not_touch = plan.get("do_not_touch_databases") if isinstance(plan.get("do_not_touch_databases"), list) else []
    protected_buckets = [
        str(item.get("category"))
        for item in do_not_touch
        if isinstance(item, Mapping) and item.get("category")
    ]
    proof_refs = _existing_refs(
        CORE_SOURCE_REFS["sqlite_consolidation_plan"],
        CORE_SOURCE_REFS["sqlite_governance_registry"],
        CORE_SOURCE_REFS["canonical_state_map"],
    )
    return _answer_payload(
        speaker_ref="guardian",
        voice_mode="safety_gate",
        question=question,
        headline="Protected stores must never merge",
        plain_summary="Never merge ledgers, secrets, raw prompt bodies, or test harness data into package or read-model state.",
        confirmed=[
            f"Never-consolidate rules: {never_summary}.",
            f"Do-not-touch buckets include: {', '.join(protected_buckets) if protected_buckets else 'protected_business_ledger, legacy_archives, unknown_needs_review, protected_evidence, token_secret_credential_stores'}.",
            "This answer grants no delete, migration, submit, send, ledger, or paid authority.",
        ],
        inferred=[
            "Package/event indexes may reference proof refs, but they must not absorb protected stores or raw prompt bodies.",
        ],
        unknown=[],
        next_safe_action="Keep these stores isolated and require a separate operator-approved classification packet before any future change.",
        proof_refs=proof_refs,
    )


def _safe_cleanup_answer(question: str, sources: Mapping[str, Any]) -> dict[str, Any]:
    plan = sources.get("sqlite_consolidation_plan") if isinstance(sources.get("sqlite_consolidation_plan"), dict) else {}
    do_not_touch = plan.get("do_not_touch_databases") if isinstance(plan.get("do_not_touch_databases"), list) else []
    keep_isolated = plan.get("keep_isolated_databases") if isinstance(plan.get("keep_isolated_databases"), list) else []
    unknown_policy = plan.get("unknown_db_policy") if isinstance(plan.get("unknown_db_policy"), Mapping) else {}
    do_not_summary = ", ".join(
        f"{item.get('category')}={item.get('count')}"
        for item in do_not_touch
        if isinstance(item, Mapping)
    ) or "do-not-touch counts unavailable"
    keep_summary = ", ".join(
        f"{item.get('category')}={item.get('count')}"
        for item in keep_isolated
        if isinstance(item, Mapping)
    ) or "keep-isolated counts unavailable"
    proof_refs = _existing_refs(
        CORE_SOURCE_REFS["sqlite_consolidation_plan"],
        CORE_SOURCE_REFS["sqlite_governance_registry"],
        CORE_SOURCE_REFS["canonical_state_map"],
    )
    return _answer_payload(
        speaker_ref="guardian",
        voice_mode="safety_gate",
        question=question,
        headline="Cleanup is review-only for now",
        plain_summary="Nothing is safe to delete from this answer; safe cleanup means classify, review, and plan non-mutating overlays first.",
        confirmed=[
            f"Do-not-touch buckets: {do_not_summary}.",
            f"Keep-isolated buckets: {keep_summary}.",
            f"Unknown DB policy: {unknown_policy.get('summary', 'unknown_needs_review stays read-only; no deletion or migration is allowed.')}",
            "The consolidation plan does not authorize deletes, moves, migrations, or existing DB mutation.",
        ],
        inferred=[
            "A future cleanup candidate list should exclude ledgers, protected stores, unknown review DBs, test harnesses, and generated proof/status DBs unless separately approved.",
        ],
        unknown=[
            "No database was approved for deletion or migration by this answer.",
        ],
        next_safe_action="Create a review checklist from the plan; do not delete or move any database.",
        proof_refs=proof_refs,
    )


def _sqlite_work_log_answer(question: str, sources: Mapping[str, Any]) -> dict[str, Any]:
    sqlite_meta = sources.get("st_annes_work_log_sqlite") if isinstance(sources.get("st_annes_work_log_sqlite"), dict) else {}
    work_log_read_model = sources.get("st_annes_work_log_events") if isinstance(sources.get("st_annes_work_log_events"), dict) else {}
    table_names = sqlite_meta.get("tables") if isinstance(sqlite_meta.get("tables"), list) else []
    table_counts = sqlite_meta.get("table_counts") if isinstance(sqlite_meta.get("table_counts"), Mapping) else {}
    event_count = work_log_read_model.get("event_count")
    confirmed = [
        f"SQLite metadata path: {sqlite_meta.get('path', 'generated/system_knowledge/st_annes_monthly_work_log.sqlite')}",
        f"SQLite exists: {bool(sqlite_meta.get('exists'))}",
        f"SQLite tables visible: {', '.join(table_names) if table_names else 'none'}",
        f"SQLite table counts: {json.dumps(table_counts, sort_keys=True)}",
        f"Work-log read model event_count: {event_count if event_count is not None else 'unknown'}",
    ]
    proof_refs = _existing_refs(
        CORE_SOURCE_REFS["st_annes_work_log_events"],
        CORE_SOURCE_REFS["st_annes_monthly_work_log_contract"],
    )
    sqlite_path = str(sqlite_meta.get("path") or "")
    if sqlite_path:
        proof_refs.append(sqlite_path)
    return _answer_payload(
        speaker_ref="chief",
        voice_mode="diagnostic",
        question=question,
        headline="SQLite has work-log metadata",
        plain_summary="SQLite can report St. Anne's work-log tables and counts without dumping raw event rows.",
        confirmed=confirmed,
        inferred=[
            "Use the read model for operator-facing status; use SQLite metadata for proof that local staging tables exist.",
        ],
        unknown=[
            "Raw row contents were not read or included because the question did not explicitly request proof-row inspection.",
        ],
        next_safe_action="Open the proof drawer if table names/counts are enough; request a separate whitelisted proof read for row-level details.",
        proof_refs=proof_refs,
    )


def _voice_route_answer(question: str, sources: Mapping[str, Any]) -> dict[str, Any]:
    proof_refs = _existing_refs(
        CORE_SOURCE_REFS["agent_voice_routing"],
        CORE_SOURCE_REFS["agent_voice_profiles"],
    )
    return _answer_payload(
        speaker_ref="hermes",
        voice_mode="recommendation",
        question=question,
        headline="Speaker choice follows deterministic routing",
        plain_summary="Architecture questions route to Hermes, diagnostics to Chief, authority boundaries to Guardian, and neutral status to OpenClaw.",
        confirmed=[
            "Agent voice routing is a local contract, not roleplay or live agent execution.",
            "Package and provider-gate questions use Chief.",
            "Send, ledger, paid, submit, and protected-access questions use Guardian.",
        ],
        inferred=[
            "Use the selected speaker as display/copy context only; it does not grant action authority.",
        ],
        unknown=[],
        next_safe_action="Render the routed speaker in Mission Control while keeping proof collapsed.",
        proof_refs=proof_refs,
    )


def _proof_answer(question: str, sources: Mapping[str, Any]) -> dict[str, Any]:
    proof_refs = _existing_refs(
        CORE_SOURCE_REFS["operator_conversation_journal"],
        CORE_SOURCE_REFS["workflow_package_queue"],
        CORE_SOURCE_REFS["automation_permission_registry"],
        CORE_SOURCE_REFS["operator_human_readability_surface"],
    )
    return _answer_payload(
        speaker_ref="chief",
        voice_mode="diagnostic",
        question=question,
        headline="Proof is in local read models",
        plain_summary="The proof set is local read-model refs, response receipts, and SQLite metadata.",
        confirmed=[
            "Operator conversation history stores proof refs instead of raw request bodies.",
            "Workflow package records store package ids, gate results, and business-action gate status.",
            "Human readability cards keep proof collapsed by default.",
        ],
        inferred=[
            "Use proof refs first; avoid showing raw backend payloads in the primary card.",
        ],
        unknown=[],
        next_safe_action="Open proof/details only for the specific card or package under review.",
        proof_refs=proof_refs,
    )


def _safe_next_answer(question: str, sources: Mapping[str, Any]) -> dict[str, Any]:
    proof_refs = _existing_refs(
        CORE_SOURCE_REFS["workflow_package_queue"],
        CORE_SOURCE_REFS["operator_conversation_journal"],
        CORE_SOURCE_REFS["agent_voice_routing"],
        "generated/read_models/workflow_package_request_consumer_status.json",
    )
    return _answer_payload(
        speaker_ref="openclaw",
        voice_mode="operator_calm",
        question=question,
        headline="Safe next is review, not action",
        plain_summary="The safe next move is to review local proof and keep business-action gates closed.",
        confirmed=[
            "This workflow answers from local read models and SQLite metadata only.",
            "No send, submit, ledger, workbook, PDF, browser, Gmail, Coupa, model, or worker action is authorized here.",
            "Proof refs stay collapsed by default for operator display.",
        ],
        inferred=[
            "Ask for a specific package, gate, client, or receipt when you want the next local proof check.",
        ],
        unknown=[],
        next_safe_action="Pick one proof ref or package id to inspect locally.",
        proof_refs=proof_refs,
    )


def _unknown_answer(question: str, speaker_ref: str, voice_mode: str) -> dict[str, Any]:
    proof_refs = _existing_refs(
        CORE_SOURCE_REFS["operator_human_readability_surface"],
        CORE_SOURCE_REFS["workflow_package_queue"],
        CORE_SOURCE_REFS["agent_voice_routing"],
    )
    return _answer_payload(
        speaker_ref=speaker_ref,
        voice_mode=voice_mode,
        question=question,
        headline="No local answer found",
        plain_summary="I do not have a deterministic local answer for that question yet.",
        confirmed=[
            "The system question workflow stayed local-only.",
            "No external model, provider, agent loop, or business action ran.",
        ],
        inferred=[],
        unknown=[
            "No matching local answer rule was found.",
            "The requested fact may need a new read model, wiki source, or explicit proof ref.",
        ],
        next_safe_action="Ask with a specific package id, gate name, client, or receipt ref.",
        proof_refs=proof_refs,
    )


def answer_system_question(
    question: str,
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    wiki_root: Path = DEFAULT_WIKI_ROOT,
    sqlite_root: Path = DEFAULT_SQLITE_ROOT,
) -> dict[str, Any]:
    del wiki_root  # Reserved for V1 source snippets; V0 answers from read models and SQLite metadata.
    question = _safe_question(question)
    text = question.lower()
    sources = _load_sources(read_model_root, sqlite_root)

    if "all these database" in text or "all these sqlite" in text or (
        "what are" in text and ("databases" in text or "sqlite" in text)
    ):
        return _database_inventory_answer(question, sources)
    if ("never" in text or "should not" in text or "must not" in text) and (
        "merge" in text or "merged" in text or "consolidate" in text or "consolidation" in text
    ):
        return _never_merge_answer(question, sources)
    if "consolidate" in text or "consolidation" in text:
        return _sqlite_consolidation_answer(question, sources)
    if "ledger" in text and ("mixed" in text or "mix" in text or "included" in text or "in this" in text):
        return _ledger_isolation_answer(question, sources)
    if "safe" in text and ("clean up" in text or "cleanup" in text or "delete" in text or "remove" in text):
        return _safe_cleanup_answer(question, sources)
    if ("package truth" in text or ("database" in text and "package" in text and ("own" in text or "truth" in text))):
        return _package_truth_owner_answer(question, sources)
    if "sqlite" in text and ("st. anne" in text or "st anne" in text or "work log" in text or "work logs" in text):
        return _sqlite_work_log_answer(question, sources)
    if (
        ("st. anne" in text or "st anne" in text)
        and ("database" in text or "sqlite" in text or "truth" in text or "own" in text)
        and ("work log" in text or "work logs" in text)
    ):
        return _st_annes_work_log_owner_answer(question, sources)
    if "chief" in text and ("spawned worker" in text or "worker" in text or "child" in text or "lm2" in text):
        return _chief_vs_worker_answer(question, sources)
    if "submit capital hilton invoice" in text and ("block" in text or "why" in text or "gate" in text):
        return _capital_hilton_block_answer(question, sources)
    if "send email" in text or "can this send" in text or "email authority" in text:
        return _email_authority_answer(question, sources)
    if "what is safe next" in text or text.strip() in {"safe next?", "what's safe next?", "whats safe next?"}:
        return _safe_next_answer(question, sources)
    if "which agent should speak" in text or "speaker" in text or "voice" in text:
        return _voice_route_answer(question, sources)
    if "proof" in text or "receipt" in text:
        return _proof_answer(question, sources)

    speaker_ref, voice_mode = speaker_for_question(question)
    return _unknown_answer(question, speaker_ref, voice_mode)


def build_contract_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_root: Path = DEFAULT_SQLITE_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    examples = [
        answer_system_question(
            question,
            read_model_root=read_model_root,
            sqlite_root=sqlite_root,
        )
        for question in EXAMPLE_QUESTIONS
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": CONTRACT_STATUS,
        "workflow_ref": WORKFLOW_REF,
        "purpose": "Local-only system question answering over existing OpenClaw read models, wiki files, and SQLite metadata.",
        "source_scope": dict(SOURCE_SCOPE),
        "source_refs": dict(CORE_SOURCE_REFS),
        "privacy": {
            "privacy_impact": "local_only",
            "raw_long_prompt_bodies_included": False,
            "external_providers_used": False,
            "sqlite_policy": "schema_and_count_metadata_only_unless_explicitly_whitelisted",
        },
        "speaker_routing": {
            "architecture_system_design": "hermes",
            "package_block_gate_diagnostic": "chief",
            "safety_authority": "guardian",
            "neutral_status": "openclaw",
        },
        "answer_shape": {
            "workflow_ref": WORKFLOW_REF,
            "speaker_ref": "hermes|chief|guardian|openclaw",
            "voice_mode": "recommendation|diagnostic|safety_gate|operator_calm",
            "question": "bounded_question_text",
            "answer": [
                "headline",
                "plain_summary",
                "confirmed",
                "inferred",
                "unknown",
                "next_safe_action",
                "proof_refs",
            ],
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        },
        "examples": examples,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "local_only": True,
            "example_count": len(examples),
            "external_llm_called": False,
            "child_agent_spawned": False,
            "chief_cassandra_hermes_guardian_niles_loops_launched": False,
            "loop_control_run": False,
            "email_send_performed": False,
            "ledger_mutation_performed": False,
            "browser_access_performed": False,
            "gmail_access_performed": False,
            "coupa_access_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "authority_flags_all_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "unsafe_true_grants_absent": True,
        },
    }


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# System Question Answering",
        "",
        f"Status: `{CONTRACT_STATUS}`",
        "",
        "This workflow answers local questions about OpenClaw state, gates, agents, packages, receipts, and proof refs.",
        "",
        "It is deterministic and local-only. It does not call an external LLM, spawn agents, run loops, send email, open browser/Gmail/Coupa, mutate ledgers or workbooks, export PDFs, submit portals, or mark paid/sent.",
        "",
        "## Speaker Routing",
        "",
    ]
    for key, value in read_model["speaker_routing"].items():
        lines.append(f"- `{key}` -> `{value}`")
    lines.extend(["", "## Source Scope", ""])
    for key, value in read_model["source_scope"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Example Answers", ""])
    for example in read_model["examples"]:
        answer = example["answer"]
        lines.append(
            f"- {answer['headline']}: {answer['plain_summary']} Next: {answer['next_safe_action']}"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Proof refs should remain collapsed by default.",
            "- SQLite access is schema/count metadata only unless a later workflow explicitly whitelists row-level proof.",
            "- Unknown questions return unknowns and source refs instead of guessing.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_system_question_answer(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_root: Path = DEFAULT_SQLITE_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_contract_read_model(
        read_model_root=read_model_root,
        sqlite_root=sqlite_root,
        generated_at=generated_at,
    )
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
        "status": CONTRACT_STATUS,
        "read_model_path": local_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export System Question Answer V0 contract.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--sqlite-root", default=str(DEFAULT_SQLITE_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--question")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.question:
        payload = answer_system_question(
            args.question,
            read_model_root=Path(args.read_model_root),
            sqlite_root=Path(args.sqlite_root),
        )
        print(stable_json(payload), end="")
        return 0
    result = export_system_question_answer(
        read_model_root=Path(args.read_model_root),
        sqlite_root=Path(args.sqlite_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
