"""Canonical State Map V0.

Publishes where OpenClaw truth lives for operator questions. This is a
read-model only map: it does not consolidate databases, move/delete files,
mutate ledgers/workbooks, send mail, open external systems, mark paid, or
submit anything.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Canonical State Map.md")

SCHEMA_VERSION = "canonical_state_map_v0"
READ_MODEL_ID = "canonical_state_map"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
MAP_STATUS = "CANONICAL_STATE_MAP_READY"
MAP_NOT_READY_STATUS = "CANONICAL_STATE_MAP_NOT_READY"

REQUIRED_DOMAIN_REFS = (
    "package_queue",
    "request_response",
    "conversation_journal",
    "st_annes_work_log",
    "st_annes_invoice_status",
    "capital_hilton_invoice_status",
    "capital_hilton_proposal_status",
    "agent_voice_profiles",
    "permission_registry",
    "overnight_workboard",
    "business_ledger",
)

SOURCE_FILES = {
    "sqlite_governance_registry": "sqlite_governance_registry.json",
    "package_event_index": "package_event_index.json",
    "operator_conversation_journal": "operator_conversation_journal.json",
    "workflow_package_queue_contract": "workflow_package_queue_contract.json",
    "st_annes_work_log_events": "st_annes_work_log_events.json",
    "st_annes_invoice_status": "st_annes_invoice_status.json",
    "capital_hilton_invoice_operator_run_status": "capital_hilton_invoice_operator_run_status.json",
    "capital_hilton_business_development_proposal": "capital_hilton_business_development_proposal.json",
    "agent_voice_profiles": "agent_voice_profiles.json",
    "automation_permission_registry": "automation_permission_registry.json",
    "overnight_workboard": "overnight_workboard.json",
}

PRECONDITION_STATUSES = {
    "sqlite_governance_registry": "SQLITE_GOVERNANCE_REGISTRY_READY",
    "package_event_index": "PACKAGE_EVENT_INDEX_READY",
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
    "sqlite_consolidation_allowed": False,
    "sent": False,
    "paid": False,
}


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


def _source_summaries(read_model_root: Path) -> dict[str, dict[str, Any]]:
    root = _rooted(read_model_root)
    summaries: dict[str, dict[str, Any]] = {}
    for source_id, filename in SOURCE_FILES.items():
        path = root / filename
        payload = _load_json(path)
        summaries[source_id] = {
            "source_id": source_id,
            "source_ref": _source_ref(filename),
            "path": path.as_posix(),
            "exists": path.exists(),
            "read_model_id": str(payload.get("read_model_id") or ""),
            "schema_version": str(payload.get("schema_version") or ""),
            "status": str(payload.get("status") or payload.get("invoice_status") or payload.get("proposal_status") or ""),
            "generated_at": str(payload.get("generated_at") or ""),
        }
    return summaries


def _status(source: Mapping[str, Any]) -> str:
    return str(source.get("status") or "")


def _ref(source_id: str, sources: Mapping[str, Mapping[str, Any]], reason: str) -> dict[str, str]:
    source = sources[source_id]
    return {
        "source_ref": str(source["source_ref"]),
        "status": _status(source),
        "reason": reason,
    }


def _canonical(source_id: str, sources: Mapping[str, Mapping[str, Any]], truth_scope: str) -> dict[str, str]:
    source = sources[source_id]
    return {
        "source_ref": str(source["source_ref"]),
        "status": _status(source),
        "truth_scope": truth_scope,
    }


def _write_authority(scope: str, forbidden: list[str]) -> dict[str, Any]:
    return {
        "mode": "no_write_grant_from_this_map",
        "truth_scope": scope,
        "operator_gate_required": True,
        "notes": "This map describes ownership only. It does not authorize mutations.",
        "forbidden_by_default": forbidden,
    }


def _read_authority(scope: str, sources: list[str]) -> dict[str, Any]:
    return {
        "mode": "local_read_model_refs_only",
        "truth_scope": scope,
        "source_refs": sources,
        "notes": "Safe for system_question_answer to cite summarized refs without raw row dumps.",
    }


def _domain(
    *,
    domain_ref: str,
    label: str,
    canonical_source: dict[str, str],
    supporting_sources: list[dict[str, str]],
    evidence_sources: list[dict[str, str]],
    not_truth_sources: list[dict[str, str]],
    write_scope: str,
    read_refs: list[str],
    safe_question_examples: list[str],
    forbidden_mutations: list[str],
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "domain_ref": domain_ref,
        "label": label,
        "canonical_source": canonical_source,
        "supporting_sources": supporting_sources,
        "evidence_sources": evidence_sources,
        "not_truth_sources": not_truth_sources,
        "write_authority": _write_authority(write_scope, forbidden_mutations),
        "read_authority": _read_authority(write_scope, read_refs),
        "safe_question_examples": safe_question_examples,
        "forbidden_mutations": forbidden_mutations,
        "notes": notes or [],
    }


def build_domains(sources: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    package_ref = str(sources["workflow_package_queue_contract"]["source_ref"])
    event_ref = str(sources["package_event_index"]["source_ref"])
    conversation_ref = str(sources["operator_conversation_journal"]["source_ref"])
    work_log_ref = str(sources["st_annes_work_log_events"]["source_ref"])
    st_invoice_ref = str(sources["st_annes_invoice_status"]["source_ref"])
    ch_invoice_ref = str(sources["capital_hilton_invoice_operator_run_status"]["source_ref"])
    proposal_ref = str(sources["capital_hilton_business_development_proposal"]["source_ref"])
    voice_ref = str(sources["agent_voice_profiles"]["source_ref"])
    permission_ref = str(sources["automation_permission_registry"]["source_ref"])
    workboard_ref = str(sources["overnight_workboard"]["source_ref"])
    sqlite_ref = str(sources["sqlite_governance_registry"]["source_ref"])

    return [
        _domain(
            domain_ref="package_queue",
            label="Workflow package queue",
            canonical_source=_canonical(
                "workflow_package_queue_contract",
                sources,
                "Package definitions, package statuses, workflow refs, gate results, worker result receipts.",
            ),
            supporting_sources=[
                _ref("package_event_index", sources, "Indexes package events and request/response refs without mutating package records."),
                _ref("sqlite_governance_registry", sources, "Classifies workflow_package_queue.sqlite as canonical workflow state."),
            ],
            evidence_sources=[_ref("operator_conversation_journal", sources, "Operator-facing summaries link back to package ids.")],
            not_truth_sources=[
                _ref("overnight_workboard", sources, "Planning board can suggest work but cannot change package status."),
                _ref("agent_voice_profiles", sources, "Voice profiles shape speaker copy, not package truth."),
            ],
            write_scope="existing package queue writers only after explicit gate; this map grants no writes",
            read_refs=[package_ref, event_ref, sqlite_ref],
            safe_question_examples=[
                "Why did this package block?",
                "What workflow owns this request?",
                "Which gate stopped this package?",
            ],
            forbidden_mutations=[
                "Do not edit package rows from this map.",
                "Do not mark a package submitted, paid, or sent from an explanation.",
                "Do not consolidate package queue databases.",
            ],
        ),
        _domain(
            domain_ref="request_response",
            label="Mission Control request/response receipts",
            canonical_source=_canonical(
                "package_event_index",
                sources,
                "Request/response linkage, event ids, package ids, response refs, and proof refs.",
            ),
            supporting_sources=[
                _ref("workflow_package_queue_contract", sources, "Package queue provides package status context."),
                _ref("operator_conversation_journal", sources, "Conversation history stores operator-facing response summaries."),
            ],
            evidence_sources=[_ref("sqlite_governance_registry", sources, "Confirms package/event databases remain non-consolidated.")],
            not_truth_sources=[_ref("overnight_workboard", sources, "Planning board does not prove a Mission Control response happened.")],
            write_scope="request/response receipts are readback evidence; this map grants no writes",
            read_refs=[event_ref, package_ref, conversation_ref],
            safe_question_examples=[
                "Where did this response come from?",
                "Which package was this Mission Control answer tied to?",
            ],
            forbidden_mutations=[
                "Do not rewrite request or response receipts.",
                "Do not store raw prompt bodies in this map.",
                "Do not send or resubmit a response.",
            ],
        ),
        _domain(
            domain_ref="conversation_journal",
            label="Operator-facing conversation journal",
            canonical_source=_canonical(
                "operator_conversation_journal",
                sources,
                "Operator-facing history, thread grouping, headlines, summaries, and proof refs.",
            ),
            supporting_sources=[
                _ref("package_event_index", sources, "Provides event/package linkage."),
                _ref("workflow_package_queue_contract", sources, "Provides underlying package status context."),
            ],
            evidence_sources=[_ref("sqlite_governance_registry", sources, "Classifies operator conversation journal as canonical workflow state.")],
            not_truth_sources=[_ref("agent_voice_profiles", sources, "Voice profiles influence display tone, not event history.")],
            write_scope="conversation journal writers only; this map grants no journal writes",
            read_refs=[conversation_ref, event_ref],
            safe_question_examples=[
                "What did OpenClaw tell me last time?",
                "Which thread did this answer appear in?",
            ],
            forbidden_mutations=[
                "Do not edit journal entries from this map.",
                "Do not infer business truth from phrasing alone.",
            ],
        ),
        _domain(
            domain_ref="st_annes_work_log",
            label="St. Anne's work log",
            canonical_source=_canonical(
                "st_annes_work_log_events",
                sources,
                "Staged St. Anne's work-log events, confirmation posture, invoice inclusion status, and source package refs.",
            ),
            supporting_sources=[
                _ref("workflow_package_queue_contract", sources, "Work-log events are package-backed."),
                _ref("sqlite_governance_registry", sources, "Classifies the St. Anne's work-log SQLite/read model as generated evidence unless explicitly confirmed."),
            ],
            evidence_sources=[_ref("operator_conversation_journal", sources, "Operator-facing intake history.")],
            not_truth_sources=[
                _ref("st_annes_invoice_status", sources, "Invoice status summarizes invoice artifact state, not new work-log event truth."),
            ],
            write_scope="St. Anne's work-log intake/review workflow only after operator confirmation",
            read_refs=[work_log_ref, package_ref, conversation_ref],
            safe_question_examples=[
                "What does SQLite know about St. Anne's work logs?",
                "Which St. Anne's events are staged versus confirmed?",
            ],
            forbidden_mutations=[
                "Do not include staged events in invoice truth without operator confirmation.",
                "Do not mutate workbook cells.",
                "Do not send an invoice.",
            ],
        ),
        _domain(
            domain_ref="st_annes_invoice_status",
            label="St. Anne's invoice status",
            canonical_source=_canonical(
                "st_annes_invoice_status",
                sources,
                "Recorded invoice artifact status, manual send posture, payment status, validation refs, and safety flags.",
            ),
            supporting_sources=[
                _ref("st_annes_work_log_events", sources, "Work-log facts support invoice content but do not mark paid."),
                _ref("sqlite_governance_registry", sources, "Keeps invoice status evidence separate from business ledger truth."),
            ],
            evidence_sources=[_ref("operator_conversation_journal", sources, "Operator-facing invoice conversation summaries.")],
            not_truth_sources=[
                _ref("capital_hilton_business_development_proposal", sources, "Proposal status is unrelated to St. Anne's invoice payment truth."),
            ],
            write_scope="invoice status ingest/receipt workflow only; ledger remains isolated",
            read_refs=[st_invoice_ref, work_log_ref],
            safe_question_examples=[
                "Was the St. Anne's invoice sent by OpenClaw?",
                "What is the current St. Anne's invoice payment posture?",
            ],
            forbidden_mutations=[
                "Do not mark paid from invoice artifact existence.",
                "Do not post ledger entries.",
                "Do not export or send PDFs from this map.",
            ],
        ),
        _domain(
            domain_ref="capital_hilton_invoice_status",
            label="Capital Hilton invoice status",
            canonical_source=_canonical(
                "capital_hilton_invoice_operator_run_status",
                sources,
                "Ingested operator run receipt for Coupa submission posture, email recording, invoice ids, proof refs, and paid=false.",
            ),
            supporting_sources=[
                _ref("package_event_index", sources, "Links Capital Hilton package events and gate status."),
                _ref("workflow_package_queue_contract", sources, "Explains provider gate/package block posture."),
                _ref("sqlite_governance_registry", sources, "Keeps Capital Hilton invoice evidence separate from protected ledger truth."),
            ],
            evidence_sources=[_ref("operator_conversation_journal", sources, "Operator-facing Capital Hilton finance thread summaries.")],
            not_truth_sources=[
                _ref("capital_hilton_business_development_proposal", sources, "Proposal send/review status cannot prove invoice submission or payment."),
            ],
            write_scope="operator-run receipt ingest only; this map grants no Coupa, email, ledger, or paid writes",
            read_refs=[ch_invoice_ref, event_ref, package_ref],
            safe_question_examples=[
                "Why did Submit Capital Hilton invoice block?",
                "Did OpenClaw autonomously submit or email the Capital Hilton invoice?",
            ],
            forbidden_mutations=[
                "Do not submit Coupa.",
                "Do not send email.",
                "Do not mark paid from Coupa submission alone.",
                "Do not mutate ledger.",
            ],
        ),
        _domain(
            domain_ref="capital_hilton_proposal_status",
            label="Capital Hilton proposal status",
            canonical_source=_canonical(
                "capital_hilton_business_development_proposal",
                sources,
                "Business Development proposal status, proposal refs, operator-assisted send recording, review posture, and no-finance-handoff flags.",
            ),
            supporting_sources=[
                _ref("operator_conversation_journal", sources, "Business development thread summaries."),
                _ref("package_event_index", sources, "Proposal follow-up package events."),
            ],
            evidence_sources=[_ref("sqlite_governance_registry", sources, "Classifies proposal status as generated evidence, not ledger truth.")],
            not_truth_sources=[
                _ref("capital_hilton_invoice_operator_run_status", sources, "Invoice status does not prove proposal acceptance."),
            ],
            write_scope="proposal read-model ingest only; this map grants no send, acceptance, finance handoff, or ledger write",
            read_refs=[proposal_ref, conversation_ref],
            safe_question_examples=[
                "What is the Capital Hilton proposal status?",
                "Can proposal status create an invoice?",
            ],
            forbidden_mutations=[
                "Do not infer proposal acceptance from send recording.",
                "Do not create finance handoff from proposal status alone.",
                "Do not mark paid.",
            ],
        ),
        _domain(
            domain_ref="agent_voice_profiles",
            label="Agent voice profiles",
            canonical_source=_canonical(
                "agent_voice_profiles",
                sources,
                "Speaker refs, voice profile refs, voice modes, copy rules, and TTS shaping rules.",
            ),
            supporting_sources=[_ref("operator_conversation_journal", sources, "Shows where voice-shaped display was used.")],
            evidence_sources=[_ref("workflow_package_queue_contract", sources, "Package displays carry speaker_ref and voice_profile_ref.")],
            not_truth_sources=[
                _ref("capital_hilton_invoice_operator_run_status", sources, "Business receipts determine business facts, not speaker style."),
            ],
            write_scope="voice profile generator only; this map grants no agent execution",
            read_refs=[voice_ref, package_ref],
            safe_question_examples=[
                "Why did Guardian answer that?",
                "Which voice profile should a system answer use?",
            ],
            forbidden_mutations=[
                "Do not use voice profile as approval.",
                "Do not launch agents or TTS from this map.",
                "Do not send messages.",
            ],
        ),
        _domain(
            domain_ref="permission_registry",
            label="Automation permission registry",
            canonical_source=_canonical(
                "automation_permission_registry",
                sources,
                "Permission posture for Coupa submit, Gmail send, ledger post, paid marking, bridge, package gate, and workbook-related gates.",
            ),
            supporting_sources=[
                _ref("workflow_package_queue_contract", sources, "Packages consume gate posture."),
                _ref("sqlite_governance_registry", sources, "Classifies protected ledger and workflow state isolation."),
            ],
            evidence_sources=[_ref("package_event_index", sources, "Shows package outcomes after permission gates.")],
            not_truth_sources=[
                _ref("overnight_workboard", sources, "Planning workboard can recommend gates but cannot grant them."),
            ],
            write_scope="permission registry generator only; explicit operator approval still required for external actions",
            read_refs=[permission_ref, package_ref, sqlite_ref],
            safe_question_examples=[
                "Can this send email?",
                "Why is Coupa submit blocked?",
            ],
            forbidden_mutations=[
                "Do not convert blocked permissions into approvals.",
                "Do not open Gmail, browser, or Coupa.",
                "Do not post ledger or mark paid.",
            ],
        ),
        _domain(
            domain_ref="overnight_workboard",
            label="Overnight workboard",
            canonical_source=_canonical(
                "overnight_workboard",
                sources,
                "Planning-only work packets, Hermes recommendations, Chief packets, and Guardian gates for operator review.",
            ),
            supporting_sources=[
                _ref("operator_conversation_journal", sources, "Source context for planning summaries."),
                _ref("automation_permission_registry", sources, "Gate posture referenced by planning packets."),
            ],
            evidence_sources=[_ref("sqlite_governance_registry", sources, "Confirms no database consolidation or ledger mixing.")],
            not_truth_sources=[
                _ref("workflow_package_queue_contract", sources, "Workboard plans do not replace package queue truth."),
                _ref("capital_hilton_invoice_operator_run_status", sources, "Workboard does not prove invoice execution."),
            ],
            write_scope="planning read model only; no sleeping loop or unattended execution authority",
            read_refs=[workboard_ref, conversation_ref],
            safe_question_examples=[
                "What is safe next?",
                "Which gates should Guardian keep closed?",
            ],
            forbidden_mutations=[
                "Do not launch loops.",
                "Do not restart services.",
                "Do not push.",
                "Do not execute workboard packets unattended.",
            ],
        ),
        _domain(
            domain_ref="business_ledger",
            label="Protected business ledger",
            canonical_source=_canonical(
                "sqlite_governance_registry",
                sources,
                "Ledger location/classification truth: protected_business_ledger, isolated, consolidation forbidden.",
            ),
            supporting_sources=[
                _ref("st_annes_invoice_status", sources, "Invoice/payment status evidence can support ledger questions but cannot post ledger truth."),
                _ref("capital_hilton_invoice_operator_run_status", sources, "Coupa/email submission evidence can support ledger review but cannot mark paid alone."),
                _ref("capital_hilton_business_development_proposal", sources, "Proposal send status is not payment or ledger truth."),
            ],
            evidence_sources=[_ref("package_event_index", sources, "Links packages to receipts without touching ledger rows.")],
            not_truth_sources=[
                _ref("capital_hilton_business_development_proposal", sources, "Proposal, send, and review posture are not paid truth."),
                _ref("capital_hilton_invoice_operator_run_status", sources, "Coupa submit/email recording alone is not paid truth."),
                _ref("st_annes_invoice_status", sources, "Invoice artifact existence alone is not paid truth."),
            ],
            write_scope="business ledger remains isolated until explicit payment evidence and a separate approved ledger workflow",
            read_refs=[sqlite_ref, st_invoice_ref, ch_invoice_ref, proposal_ref],
            safe_question_examples=[
                "Where does paid truth live?",
                "Can invoice submission mark the ledger paid?",
            ],
            forbidden_mutations=[
                "Do not mutate ledger.",
                "Do not mark paid from proposal send, email send, Coupa submit, or invoice artifact alone.",
                "Do not consolidate ledger with package, agent, or generated evidence databases.",
            ],
            notes=[
                "Paid truth never comes from proposal, send, or Coupa submit alone.",
                "Ledger truth stays isolated until explicit payment evidence.",
            ],
        ),
    ]


def _preconditions(sources: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_id, required in PRECONDITION_STATUSES.items():
        observed = _status(sources[source_id])
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


def build_read_model(*, read_model_root: Path = DEFAULT_READ_MODEL_ROOT, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    sources = _source_summaries(read_model_root)
    preconditions = _preconditions(sources)
    domains = build_domains(sources)
    missing_required_inputs = [
        str(source["source_ref"])
        for source_id, source in sources.items()
        if source_id in SOURCE_FILES and not source["exists"]
    ]
    domains_present = sorted(domain["domain_ref"] for domain in domains) == sorted(REQUIRED_DOMAIN_REFS)
    ready = all(item["ready"] for item in preconditions) and not missing_required_inputs and domains_present
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": MAP_STATUS if ready else MAP_NOT_READY_STATUS,
        "purpose": "Clear source-of-truth map for OpenClaw system questions about packages, work logs, invoices, proposals, gates, receipts, and ledgers.",
        "mode": "read_only_truth_map",
        "preconditions": preconditions,
        "source_summaries": sources,
        "domain_count": len(domains),
        "domains": domains,
        "truth_rules": [
            "Package status truth comes from package queue / package event index.",
            "Operator-facing history comes from conversation journal.",
            "St. Anne's work-log truth comes from St. Anne's work-log DB/read model.",
            "Capital Hilton invoice submission truth comes from ingested operator run receipt/read model.",
            "Proposal status truth comes from Business Development proposal read model.",
            "Paid truth never comes from proposal, send, or Coupa submit alone.",
            "Ledger truth stays isolated until explicit payment evidence.",
        ],
        "missing_required_inputs": missing_required_inputs,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "read_only_truth_map": True,
            "preconditions_ready": all(item["ready"] for item in preconditions),
            "all_required_domains_present": domains_present,
            "database_consolidation_performed": False,
            "database_move_performed": False,
            "database_delete_performed": False,
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
        "# Canonical State Map",
        "",
        f"Status: `{read_model['status']}`",
        "",
        "This map answers where OpenClaw knows facts from. It is read-only and does not grant mutation authority.",
        "",
        "## Domains",
        "",
    ]
    for domain in read_model["domains"]:
        canonical = domain["canonical_source"]
        lines.extend(
            [
                f"### {domain['label']}",
                "",
                f"- Domain: `{domain['domain_ref']}`",
                f"- Canonical source: `{canonical['source_ref']}`",
                f"- Truth scope: {canonical['truth_scope']}",
                f"- Write posture: `{domain['write_authority']['mode']}`",
                "",
            ]
        )
    lines.extend(["## Truth Rules", ""])
    for rule in read_model["truth_rules"]:
        lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No database consolidation, move, delete, or migration.",
            "- No ledger or workbook mutation.",
            "- No Gmail, browser, Coupa, email send, paid marking, submit, or push.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_canonical_state_map(
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
        "domain_count": str(read_model["domain_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Canonical State Map V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_canonical_state_map(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == MAP_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
