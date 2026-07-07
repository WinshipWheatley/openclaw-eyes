"""Packet coverage contract and matrix builder for front-door question classes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from read_model_freshness_audit import audit_read_models


SCHEMA_VERSION = "packet_coverage_matrix_v1"
DEFAULT_AGENTS = ("maestro", "chief", "niles", "guardian", "cassandra", "hermes")
QUESTION_CLASSES = (
    "plate_orient_me",
    "money_owed_invoice_status",
    "gig_schedule",
    "contacts_whos_who",
    "agent_system_status",
    "how_to_advice",
    "drafting",
)


@dataclass(frozen=True)
class RequiredSection:
    section_id: str
    fact_topics: tuple[str, ...]
    source_names: tuple[str, ...]
    freshness_sla_days: int = 14
    data_source: str = "read_model"


QUESTION_COVERAGE_CONTRACT: dict[str, tuple[RequiredSection, ...]] = {
    "plate_orient_me": (
        RequiredSection(
            "attention",
            ("operator_attention",),
            (
                "operator_attention_delivery_contract.json",
                "helm_operator_attention_package.json",
                "autonomous_followup_watch_attention.json",
            ),
        ),
        RequiredSection(
            "month_bounded_receivables",
            ("receivable_month_bounded", "receivable_attention", "receivable_temporal_state", "money_not_tracked"),
            ("receivables_month_bounded.json", "st_annes_receivable_state.json"),
            data_source="read_model_or_ledger",
        ),
        RequiredSection(
            "upcoming_gigs",
            ("calendar_day", "niles_gig_context", "gig_schedule"),
            ("cassandra_email_calendar_delta_detangle.json", "*gig*.json", "*schedule*.json"),
        ),
    ),
    "money_owed_invoice_status": (
        RequiredSection(
            "structured_receivables",
            ("receivable_month_bounded", "receivable_temporal_state", "receivable_attention", "money_not_tracked"),
            ("receivables_month_bounded.json", "st_annes_receivable_state.json"),
            data_source="ledger_or_read_model",
        ),
        RequiredSection(
            "finance_invoice_posture",
            ("finance_invoice_reconciliation", "invoice_status"),
            ("finance_invoice_reconciliation.json", "capital_hilton_invoice_operator_run_status.json"),
        ),
    ),
    "gig_schedule": (
        RequiredSection("calendar", ("calendar_day",), ("cassandra_email_calendar_delta_detangle.json",)),
        RequiredSection("gig_read_models", ("niles_gig_context", "gig_schedule"), ("*gig*.json", "*schedule*.json")),
    ),
    "contacts_whos_who": (
        RequiredSection("contacts_registry", ("contacts_registry",), ("contacts_registry",), data_source="contacts.sqlite3"),
    ),
    "agent_system_status": (
        RequiredSection("agent_presence", ("agent_presence",), ("agent_presence.json",)),
        RequiredSection("chief_status", ("chief",), ("chief_status_rail.json",)),
    ),
    "how_to_advice": (
        RequiredSection("capabilities", ("capability",), ("openclaw_capability_index.json",)),
        RequiredSection("safe_context", ("operator_truth", "answer_scope"), ("operator_truth_store",), data_source="ledger"),
    ),
    "drafting": (
        RequiredSection("drafting_posture", ("email_calendar",), ("cassandra_email_calendar_delta_detangle.json",)),
        RequiredSection(
            "client_billing_context",
            ("client_billing_channel", "finance_invoice_reconciliation"),
            ("client_invoice_workflow_framework.json", "finance_invoice_reconciliation.json"),
        ),
    ),
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def evaluate_packet_coverage(
    packet: Mapping[str, Any],
    *,
    question_class: str,
    read_model_root: str | Path,
    today: date | None = None,
) -> dict[str, Any]:
    if question_class not in QUESTION_COVERAGE_CONTRACT:
        raise ValueError(f"unknown question_class: {question_class}")
    root = Path(read_model_root)
    facts = [fact for fact in packet.get("facts", ()) if isinstance(fact, Mapping)]
    sections = [
        _evaluate_required_section(section, facts=facts, read_model_root=root, today=today)
        for section in QUESTION_COVERAGE_CONTRACT[question_class]
    ]
    covered = all(section["covered"] for section in sections)
    sources_fresh = all(section["sources_fresh"] for section in sections)
    return {
        "question_class": question_class,
        "covered": covered,
        "sources_fresh": sources_fresh,
        "sections": sections,
        "missing_sections": [section["section_id"] for section in sections if not section["covered"]],
        "stale_sources": sorted(
            {
                name
                for section in sections
                for name, status in section["source_statuses"].items()
                if status.get("freshness_status") == "stale"
            }
        ),
    }


def build_packet_coverage_matrix(
    *,
    read_model_root: str | Path,
    packets_by_agent: Mapping[str, Mapping[str, Any]] | None = None,
    agents: Sequence[str] = DEFAULT_AGENTS,
    today: date | None = None,
) -> dict[str, Any]:
    root = Path(read_model_root)
    today_value = today or date.today()
    packets = dict(packets_by_agent or {})
    coverage: list[dict[str, Any]] = []
    for agent in agents:
        packet = packets.get(agent) or packets.get("maestro") or {}
        for question_class in QUESTION_CLASSES:
            report = evaluate_packet_coverage(
                packet,
                question_class=question_class,
                read_model_root=root,
                today=today_value,
            )
            source_statuses = {
                source: status
                for section in report["sections"]
                for source, status in section["source_statuses"].items()
            }
            coverage.append(
                {
                    "agent": agent,
                    "question_class": question_class,
                    "covered": report["covered"],
                    "sources_fresh": report["sources_fresh"],
                    "missing_sections": report["missing_sections"],
                    "stale_sources": report["stale_sources"],
                    "source_statuses": source_statuses,
                    "last_verified": today_value.isoformat(),
                    "sections": report["sections"],
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "read_model_root": root.as_posix(),
        "question_classes": list(QUESTION_CLASSES),
        "agents": list(agents),
        "coverage": coverage,
        "summary": {
            "row_count": len(coverage),
            "covered_count": sum(1 for row in coverage if row["covered"]),
            "sources_fresh_count": sum(1 for row in coverage if row["sources_fresh"]),
        },
    }


def _evaluate_required_section(
    section: RequiredSection,
    *,
    facts: Sequence[Mapping[str, Any]],
    read_model_root: Path,
    today: date | None,
) -> dict[str, Any]:
    matched_facts = [
        fact
        for fact in facts
        if str(fact.get("topic") or "") in section.fact_topics
    ]
    matched_sources = _source_names_from_facts(matched_facts)
    source_names = sorted(set(_expand_source_names(section.source_names, read_model_root)) | set(matched_sources))
    source_statuses = _source_statuses(source_names, read_model_root=read_model_root, today=today, stale_after_days=section.freshness_sla_days)
    return {
        "section_id": section.section_id,
        "data_source": section.data_source,
        "required_fact_topics": list(section.fact_topics),
        "required_sources": list(section.source_names),
        "matched_fact_count": len(matched_facts),
        "matched_sources": matched_sources,
        "covered": bool(matched_facts),
        "freshness_sla_days": section.freshness_sla_days,
        "sources_fresh": all(
            status.get("freshness_status") in {"fresh", "not_applicable"}
            for status in source_statuses.values()
        ),
        "source_statuses": source_statuses,
    }


def _source_names_from_facts(facts: Sequence[Mapping[str, Any]]) -> list[str]:
    names: list[str] = []
    for fact in facts:
        ref = str(fact.get("source_ref") or "")
        if ref.startswith("generated/read_models/"):
            names.append(Path(ref).name)
        elif ref.startswith("contacts_registry:"):
            names.append("contacts_registry")
        elif ref.startswith("gig_to_cash:"):
            names.append("gig_to_cash")
        elif ref:
            name = Path(ref).name
            if name.endswith(".json"):
                names.append(name)
    return sorted(dict.fromkeys(names))


def _expand_source_names(source_names: Sequence[str], read_model_root: Path) -> list[str]:
    expanded: list[str] = []
    for name in source_names:
        if "*" in name:
            expanded.extend(path.name for path in read_model_root.glob(name))
        else:
            expanded.append(name)
    return sorted(dict.fromkeys(expanded))


def _source_statuses(
    source_names: Sequence[str],
    *,
    read_model_root: Path,
    today: date | None,
    stale_after_days: int,
) -> dict[str, dict[str, Any]]:
    json_names = [name for name in source_names if name.endswith(".json")]
    statuses: dict[str, dict[str, Any]] = {}
    if json_names:
        audit = audit_read_models(
            json_names,
            read_model_root=read_model_root,
            today=today,
            stale_after_days=stale_after_days,
        )
        statuses.update({item["name"]: item for item in audit["items"]})
    for name in source_names:
        if name not in statuses:
            statuses[name] = {
                "name": name,
                "freshness_status": "not_applicable",
                "age_days": None,
                "timestamp": "",
            }
    return statuses
