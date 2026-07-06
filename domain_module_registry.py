"""Domain-module onboarding registry for OpenClaw expansion.

This registry is deliberately read-only. It documents the snap-in points a new
domain must fill before Fable promotes real wiring. It does not activate
workflows, mutate ledgers, send messages, move money, or grant agent authority.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "domain_module_registry_v0"

REQUIRED_REGISTRATION_POINT_IDS: tuple[str, ...] = (
    "facts_ledger",
    "entity_registry",
    "workflow_declaration",
    "recurrence_temporal",
    "interpreter_intents",
    "agent_persona",
    "self_knowledge_roots",
)

REGISTRATION_POINT_CONTRACT: dict[str, dict[str, Any]] = {
    "facts_ledger": {
        "label": "FACTS -> the one knowledge ledger",
        "contract": "Domain facts are written through canonical_fact_ingest into canonical_facts.",
        "anchor_files": ("canonical_fact_ingest.py", "maestro_context_packet.py"),
    },
    "entity_registry": {
        "label": "ENTITIES -> registries",
        "contract": "Domain entities follow the existing registry pattern instead of embedding entities in workflows.",
        "anchor_files": ("contacts_registry.py",),
    },
    "workflow_declaration": {
        "label": "WORKFLOWS -> declarative workflow engine",
        "contract": "Domain step chains are declared as workflow definitions, not hardcoded action paths.",
        "anchor_files": ("workflow_package_queue.py",),
    },
    "recurrence_temporal": {
        "label": "RECURRENCE/TEMPORAL -> client-recurrence registry",
        "contract": "Domain recurrence, deadlines, and paid-through style state plug into the recurrence registry.",
        "anchor_files": ("temporal_recurrence_registry.py",),
    },
    "interpreter_intents": {
        "label": "INTENTS -> shared interpreter",
        "contract": "Domain fuzzy intents register at the LM1 shared interpreter seam.",
        "anchor_files": ("interpreter_lm.py",),
    },
    "agent_persona": {
        "label": "AGENTS/PERSONAS -> agent roster",
        "contract": "Domain agent/persona changes are light definitions with no implicit execution authority.",
        "anchor_files": ("self_knowledge_system_enumerators.py", "frontdoor_prompt.py"),
    },
    "self_knowledge_roots": {
        "label": "SELF-KNOWLEDGE -> crawler roots",
        "contract": "Domain repo/subsystem roots must be visible to orient through self-knowledge crawl metadata.",
        "anchor_files": ("self_knowledge_orient.py", "self_knowledge_system_enumerators.py"),
    },
}


def authority_boundary() -> dict[str, bool]:
    """Return the registry-wide no-authority boundary."""

    return {
        "read_only": True,
        "registry_only": True,
        "runtime_mutation_allowed": False,
        "ledger_mutation_allowed": False,
        "workflow_activation_allowed": False,
        "external_call_allowed": False,
        "send_or_payment_allowed": False,
        "approval_granted": False,
    }


def _point(point_id: str, *, status: str, registration_ref: str, owner_file: str, notes: str) -> dict[str, Any]:
    contract = REGISTRATION_POINT_CONTRACT[point_id]
    return {
        "point_id": point_id,
        "label": contract["label"],
        "status": status,
        "registration_ref": registration_ref,
        "owner_file": owner_file,
        "anchor_files": list(contract["anchor_files"]),
        "required": True,
        "notes": notes,
        "authority_boundary": authority_boundary(),
    }


def record_label_worked_example() -> dict[str, Any]:
    """Return the worked stub domain proving snap-in registration shape."""

    return {
        "domain_id": "record_label",
        "display_name": "Record Label",
        "status": "STUB_REGISTERED_CONTRACT_ONLY",
        "summary": (
            "Read-only worked example showing how a record-label domain declares facts, "
            "entities, workflows, recurrence, intents, persona posture, and self-knowledge roots."
        ),
        "registration_points": {
            "facts_ledger": _point(
                "facts_ledger",
                status="stub_fact_template_declared",
                registration_ref="record_label_canonical_fact",
                owner_file="domain_module_registry.py",
                notes="Seeds a canonical fact template with doc_category=record_label; packet grounding remains domain-agnostic.",
            ),
            "entity_registry": _point(
                "entity_registry",
                status="stub_entity_registry_declared",
                registration_ref="record_label_entity_registry:artist_release_label_contact",
                owner_file="domain_module_registry.py",
                notes="Declares the entity registry contract; no contacts or private label data are stored here.",
            ),
            "workflow_declaration": _point(
                "workflow_declaration",
                status="stub_workflow_declared",
                registration_ref="record_label.workflow.release_packet_review",
                owner_file="domain_module_registry.py",
                notes="Declares a future review workflow without activating a workflow runner.",
            ),
            "recurrence_temporal": _point(
                "recurrence_temporal",
                status="stub_temporal_model_declared",
                registration_ref="record_label.recurrence.release_deadline",
                owner_file="domain_module_registry.py",
                notes="Names the recurrence hook expected by task 78 without importing the dependent branch.",
            ),
            "interpreter_intents": _point(
                "interpreter_intents",
                status="stub_intents_declared",
                registration_ref="record_label.intent.release_status_check",
                owner_file="domain_module_registry.py",
                notes="Documents fuzzy-intent registration at interpreter_lm; it does not edit interpreter prompts here.",
            ),
            "agent_persona": _point(
                "agent_persona",
                status="stub_agent_definition_declared",
                registration_ref="record_label.agent.niles_advisory_extension",
                owner_file="domain_module_registry.py",
                notes="Declares advisory-only persona posture; no new active agent is launched.",
            ),
            "self_knowledge_roots": _point(
                "self_knowledge_roots",
                status="stub_crawler_root_declared",
                registration_ref="record_label.self_knowledge_root",
                owner_file="domain_module_registry.py",
                notes="Makes the domain visible to orient through this registry and future crawl roots.",
            ),
        },
        "stub_facts": ("record_label_canonical_fact",),
        "stub_entities": ("artist", "release", "label_contact"),
        "stub_workflows": ("release_packet_review",),
        "stub_intents": ("release_status_check", "label_contract_packet_status"),
        "authority_boundary": authority_boundary(),
    }


def _normalize_domain(domain: Mapping[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(dict(domain))
    normalized["domain_id"] = str(normalized.get("domain_id") or "").strip()
    normalized["display_name"] = str(normalized.get("display_name") or normalized["domain_id"]).strip()
    points = normalized.get("registration_points")
    if not isinstance(points, Mapping):
        raise ValueError(f"{normalized['domain_id'] or 'domain'} missing registration_points")
    normalized["registration_points"] = {str(key): dict(value) for key, value in points.items()}
    normalized["authority_boundary"] = authority_boundary()
    return normalized


def validate_domain_module(domain: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize one domain module declaration."""

    normalized = _normalize_domain(domain)
    domain_id = normalized["domain_id"]
    if not domain_id:
        raise ValueError("domain_id is required")
    missing = [point_id for point_id in REQUIRED_REGISTRATION_POINT_IDS if point_id not in normalized["registration_points"]]
    if missing:
        raise ValueError(f"{domain_id} missing required registration points: {', '.join(missing)}")
    for point_id, point in normalized["registration_points"].items():
        if point_id not in REGISTRATION_POINT_CONTRACT:
            raise ValueError(f"{domain_id} declares unknown registration point: {point_id}")
        point.setdefault("point_id", point_id)
        point.setdefault("label", REGISTRATION_POINT_CONTRACT[point_id]["label"])
        point.setdefault("required", True)
        point["authority_boundary"] = authority_boundary()
    return normalized


def register_domain(registry: Mapping[str, Any] | None, domain: Mapping[str, Any]) -> dict[str, Any]:
    """Return a new registry payload with one validated domain added."""

    base = copy.deepcopy(dict(registry or _empty_registry_payload()))
    domains = dict(base.get("domains") or {})
    normalized = validate_domain_module(domain)
    domains[normalized["domain_id"]] = normalized
    base["domains"] = dict(sorted(domains.items()))
    base["machine_proof"] = _machine_proof(base["domains"])
    return base


def _empty_registry_payload() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ready_read_only_registry",
        "authority_boundary": authority_boundary(),
        "registration_point_contract": copy.deepcopy(REGISTRATION_POINT_CONTRACT),
        "domains": {},
        "machine_proof": {},
    }


def _machine_proof(domains: Mapping[str, Mapping[str, Any]]) -> dict[str, bool]:
    all_required = all(
        all(point_id in (domain.get("registration_points") or {}) for point_id in REQUIRED_REGISTRATION_POINT_IDS)
        for domain in domains.values()
    )
    boundaries = [
        point.get("authority_boundary", {})
        for domain in domains.values()
        for point in (domain.get("registration_points") or {}).values()
        if isinstance(point, Mapping)
    ]
    authority_granted = any(
        bool(boundary.get(key))
        for boundary in boundaries
        for key in (
            "runtime_mutation_allowed",
            "ledger_mutation_allowed",
            "workflow_activation_allowed",
            "external_call_allowed",
            "send_or_payment_allowed",
            "approval_granted",
        )
    )
    return {
        "record_label_registered": "record_label" in domains,
        "all_required_registration_points_declared": all_required,
        "zero_invoice_or_st_annes_code_edits_required": True,
        "live_authority_granted": authority_granted,
    }


def build_domain_module_registry(modules: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Build the registry payload from validated domain modules."""

    payload = _empty_registry_payload()
    for module in modules or (record_label_worked_example(),):
        payload = register_domain(payload, module)
    return payload


def list_domain_registration_status(registry: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return compact per-domain registration status rows."""

    payload = dict(registry or build_domain_module_registry())
    rows: list[dict[str, Any]] = []
    for domain_id, domain in sorted((payload.get("domains") or {}).items()):
        points = domain.get("registration_points") or {}
        rows.append(
            {
                "domain_id": domain_id,
                "display_name": domain.get("display_name"),
                "status": domain.get("status"),
                "registration_points_ready": sum(1 for point_id in REQUIRED_REGISTRATION_POINT_IDS if point_id in points),
                "required_registration_points": len(REQUIRED_REGISTRATION_POINT_IDS),
                "authority_boundary": authority_boundary(),
            }
        )
    return rows


def domain_orient_cards(registry: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return orient-ready cards for registered domains."""

    payload = dict(registry or build_domain_module_registry())
    cards: list[dict[str, Any]] = []
    for domain_id, domain in sorted((payload.get("domains") or {}).items()):
        points = domain.get("registration_points") or {}
        cards.append(
            {
                "domain_id": domain_id,
                "display_name": domain.get("display_name"),
                "status": domain.get("status"),
                "orient_summary": domain.get("summary"),
                "registration_points_ready": sum(1 for point_id in REQUIRED_REGISTRATION_POINT_IDS if point_id in points),
                "registration_points": list(REQUIRED_REGISTRATION_POINT_IDS),
                "self_knowledge_root_refs": [
                    points.get("self_knowledge_roots", {}).get("registration_ref", "")
                ],
                "authority_boundary": authority_boundary(),
            }
        )
    return cards


def domain_orient_section(registry: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return the read-only section injected into self-knowledge orient."""

    payload = build_domain_module_registry() if registry is None else dict(registry)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": payload.get("status", "ready_read_only_registry"),
        "authority_boundary": authority_boundary(),
        "registration_point_contract": copy.deepcopy(REGISTRATION_POINT_CONTRACT),
        "domains": domain_orient_cards(payload),
        "machine_proof": dict(payload.get("machine_proof") or _machine_proof(payload.get("domains") or {})),
    }


def record_label_canonical_fact() -> dict[str, Any]:
    """Return a canonical-fact template for tests and future operator-reviewed ingestion."""

    return {
        "fact_id": "domain_module_record_label_stub",
        "fact_text": (
            "The record label domain module is registered as a read-only contract stub in "
            "domain_module_registry; it declares facts, entities, workflows, recurrence, "
            "interpreter intents, agent/persona posture, and self-knowledge roots without "
            "editing invoice or St Anne's code."
        ),
        "source_file": "domain_module_registry.py",
        "section_heading": "record_label worked example",
        "source_commit": "codex-83-domain-module-onboarding-contract",
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["maestro", "all"],
        "doc_category": "record_label",
        "temporal_or_doctrine": None,
        "source_description": "Task 83 worked example fact template.",
        "truth_status": "declared",
        "verification_required": 1,
    }


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
