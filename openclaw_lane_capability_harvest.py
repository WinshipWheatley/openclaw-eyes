"""OpenClaw Lane Capability Harvest Registry v0.

Deterministic read-only registry for tracking what workflow lanes prove, which
reusable capabilities they harvest, and what Hermes should recommend building
next. This module reads local source/read-model evidence and writes JSON,
operator Markdown, SQLite, schema SQL, and seed SQL. It does not start services,
call an LM, launch Chief, access email/Gmail/browser/Coupa, read workbook cells,
export PDFs, mutate ledgers, mutate production state, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_SYSTEM_KNOWLEDGE_ROOT = Path("generated/system_knowledge")
DEFAULT_WIKI_ROOT = Path("generated/wiki/openclaw")

SCHEMA_VERSION = "openclaw_lane_capability_harvest_v0"
READ_MODEL_VERSION = "openclaw_lane_capability_harvest_read_model_v0"
READ_MODEL_ID = "openclaw_lane_capability_harvest"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
SQLITE_EXPORT_NAME = f"{READ_MODEL_ID}.sqlite"
SCHEMA_EXPORT_NAME = f"{READ_MODEL_ID}_SCHEMA.sql"
SEED_EXPORT_NAME = f"{READ_MODEL_ID}_SEED.sql"

LANE_STATUSES = (
    "PROVEN",
    "ACTIVE_STEEL_THREAD",
    "PARTIAL",
    "PLANNED",
    "BLOCKED",
    "UNKNOWN",
)

CAPABILITY_TYPES = (
    "WORKFLOW_RAIL",
    "EVENT_BRIDGE_ACTION",
    "AUTHORITY_PROFILE",
    "PROOF_RECEIPT",
    "PAYMENT_WATCH",
    "ARTIFACT_POLICY",
    "UI_PATTERN",
    "SERVICE_PATTERN",
    "DATA_ACCESS_PATTERN",
    "EVAL_PATTERN",
    "RECOVERY_PATTERN",
)

CAPABILITY_STATUSES = (
    "PROVEN",
    "PARTIAL",
    "PLANNED",
    "BLOCKED",
    "UNKNOWN",
)

DEPENDENCY_TYPES = (
    "REQUIRED",
    "OPTIONAL",
    "BLOCKED_BY",
    "REPLACES",
    "EXTENDS",
)

REUSE_PLAN_STATUSES = (
    "READY_TO_REUSE",
    "NEEDS_ADAPTER",
    "BLOCKED",
    "PLANNED",
    "UNKNOWN",
)

REQUIRED_SQLITE_TABLES = (
    "lane",
    "harvested_capability",
    "capability_dependency",
    "lane_reuse_plan",
    "next_lane_candidate",
    "hermes_recommendation",
    "capability_gap",
)

INPUT_SPECS = (
    ("live_arts_bundle", "generated/read_models/live_arts_md_invoice_review_bundle.json", True, "json"),
    ("capital_hilton_bundle", "generated/read_models/invoice_review_bundle.json", True, "json"),
    ("simple_invoice_event_bridge_rail_registry", "generated/read_models/simple_invoice_event_bridge_rail_registry.json", False, "json"),
    ("event_bridge_contract", "generated/read_models/openclaw_event_bridge_contract.json", False, "json"),
    ("authority_semantics_registry", "generated/read_models/openclaw_authority_semantics_registry.json", False, "json"),
    ("business_object_layer_audit", "generated/read_models/openclaw_business_object_layer_audit.json", False, "json"),
    ("estate_topology_registry", "generated/read_models/openclaw_estate_topology_registry.json", False, "json"),
    ("context_wiki_index", "generated/read_models/openclaw_context_wiki_index.json", False, "json"),
    ("client_invoice_workflow_framework", "generated/read_models/client_invoice_workflow_framework.json", False, "json"),
    ("context_wiki_pages", "generated/wiki/openclaw", False, "path"),
    ("live_arts_bundle_source", "live_arts_md_invoice_review_bundle.py", False, "path"),
    ("simple_invoice_workflow_builder_source", "simple_invoice_workflow_builder.py", False, "path"),
    ("simple_invoice_workflow_fixtures_source", "simple_invoice_workflow_fixtures.py", False, "path"),
    ("client_invoice_workflow_framework_source", "client_invoice_workflow_framework.py", False, "path"),
    ("event_bridge_adapter_source", "openclaw_event_bridge_adapter.py", False, "path"),
    ("request_router_source", "openclaw_request_router.py", False, "path"),
    ("invoice_review_action_request_handler_source", "invoice_review_action_request_handler.py", False, "path"),
    ("clara_invoice_email_draft_package_source", "clara_invoice_email_draft_package.py", False, "path"),
    ("capital_hilton_delivery_steel_thread", "generated/read_models/capital_hilton_invoice_delivery_steel_thread.json", False, "json"),
    ("capital_hilton_review_packet_approval", "generated/read_models/capital_hilton_review_packet_approval.json", False, "json"),
)

DO_NOT_WORK_NOW = (
    "generic Telegram polish before object rails are stable",
    "ledger posting before proof and approval gates are proven",
    "remote Mac or cloud relay before the local bridge/helper path is stable",
    "generic AI chat upgrades without a bounded business object",
)

NO_AUTHORITY_FLAGS = {
    "metadata_only": True,
    "read_model_only": True,
    "sqlite_registry_only": True,
    "deterministic_registry_only": True,
    "services_started": False,
    "chief_launched": False,
    "lm_called": False,
    "email_accessed": False,
    "gmail_accessed": False,
    "browser_accessed": False,
    "coupa_accessed": False,
    "workbook_cells_read": False,
    "pdf_generated_or_exported": False,
    "ledger_mutated": False,
    "production_state_mutated": False,
    "git_push_performed": False,
}


@dataclass(frozen=True)
class LaneCapabilityHarvestExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    sqlite_path: str
    schema_sql_path: str
    seed_sql_path: str
    lane_count: int
    harvested_capability_count: int
    hermes_recommended_next_lane: str
    readiness: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _rooted(path: str | Path, *, root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(root) / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _manifest_path(path_value: str, *, read_model_root: str | Path, wiki_root: str | Path) -> Path:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    read_root = _rooted(read_model_root)
    wiki = _rooted(wiki_root)
    if path_value.startswith("generated/read_models/"):
        return read_root / path_value.removeprefix("generated/read_models/")
    if path_value.startswith("generated/wiki/openclaw"):
        suffix = path_value.removeprefix("generated/wiki/openclaw").lstrip("/")
        return wiki / suffix
    return _rooted(path_value)


def _source_manifest(
    *,
    read_model_root: str | Path,
    wiki_root: str | Path,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    manifest: list[dict[str, Any]] = []
    payloads: dict[str, dict[str, Any]] = {}
    for input_ref, path_value, required, input_kind in INPUT_SPECS:
        path = _manifest_path(path_value, read_model_root=read_model_root, wiki_root=wiki_root)
        status = "PRESENT" if path.exists() else ("MISSING" if required else "UNKNOWN")
        sha256 = ""
        schema = ""
        if path.is_file():
            sha256 = _sha256_file(path)
            if input_kind == "json":
                payload = _read_json(path)
                payloads[input_ref] = payload
                schema = str(payload.get("schema_version", ""))
                if not payload:
                    status = "BAD_JSON"
        elif input_kind == "json":
            payloads[input_ref] = {}
        manifest.append(
            {
                "input_ref": input_ref,
                "path": path_value,
                "resolved_path": _display_path(path),
                "required": required,
                "input_kind": input_kind,
                "status": status,
                "sha256": sha256,
                "schema_version": schema,
            }
        )
    return manifest, payloads


def _nested(payload: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _status_or_unknown(status: str, *, allowed: tuple[str, ...]) -> str:
    return status if status in allowed else "UNKNOWN"


def _json_list(items: tuple[str, ...] | list[str]) -> str:
    return stable_json(list(items)).strip()


def _lane_rows(
    payloads: Mapping[str, dict[str, Any]],
    *,
    lane_status_overrides: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    overrides = dict(lane_status_overrides or {})
    live = payloads.get("live_arts_bundle", {})
    capital = payloads.get("capital_hilton_bundle", {})
    rail = payloads.get("simple_invoice_event_bridge_rail_registry", {})
    framework = payloads.get("client_invoice_workflow_framework", {})
    live_bundle = _nested(live, "live_arts_md_bundle", default={})
    capital_bundle = _nested(capital, "capital_hilton_bundle", default={})
    live_selected = bool(_nested(live_bundle, "candidate_selection_rail", "selected_invoice_summary", default=""))
    live_pdf_ready = bool(_nested(live_bundle, "invoice_artifact", "pdf_export_package", "request_payload_ready", default=False)) or bool(
        _nested(live_bundle, "actionable_blockers", default=[])
    )
    live_status = "ACTIVE_STEEL_THREAD" if live and (live_selected or live_pdf_ready) else ("UNKNOWN" if not live else "PARTIAL")
    capital_status = "PARTIAL" if capital else "UNKNOWN"
    st_annes_registered = "invoice_review_action_request.st_annes" in {
        str(item) for item in rail.get("registered_simple_invoice_prepare_handlers", [])
    }
    framework_text = stable_json(framework) if framework else ""
    st_annes_no_coupa = "st_annes_has_no_coupa_by_default" in framework_text or "St. Anne's" in framework_text
    st_annes_status = "PARTIAL" if st_annes_registered or st_annes_no_coupa else "PLANNED"
    rows = [
        {
            "lane_ref": "live_arts_md_invoice_lane",
            "lane_name": "Live Arts MD invoice lane",
            "business_object_type": "invoice",
            "client_ref": "live_arts_md",
            "workflow_ref": "live_arts_md_invoice_workflow",
            "status": _status_or_unknown(overrides.get("live_arts_md_invoice_lane", live_status), allowed=LANE_STATUSES),
            "current_stage": "Selected invoice and scoped PDF package are present; proof, approval, send, and payment remain gated.",
            "canonical_owner_repo": "/home/openclaw PC_BACKEND",
            "source_refs": _json_list(
                [
                    "generated/read_models/live_arts_md_invoice_review_bundle.json",
                    "live_arts_md_invoice_review_bundle.py",
                    "simple_invoice_event_bridge_rail_registry.py",
                ]
            ),
            "operator_summary": "Current mini steel thread for simple invoice state, Event Bridge action, PDF package, manual proof, payment watch, and authority boundary.",
            "developer_summary": "Reuse the selected-invoice state path, scoped artifact package, Event Bridge action shape, and no-authority guard pattern.",
        },
        {
            "lane_ref": "capital_hilton_invoice_lane",
            "lane_name": "Capital Hilton invoice lane",
            "business_object_type": "complex_invoice",
            "client_ref": "capital_hilton",
            "workflow_ref": "capital_hilton_invoice_workflow",
            "status": _status_or_unknown(overrides.get("capital_hilton_invoice_lane", capital_status), allowed=LANE_STATUSES),
            "current_stage": "Complex invoice rail is partially modeled and blocked on invoice selection, supplier portal/Coupa proof, artifact, and approval gates.",
            "canonical_owner_repo": "/home/openclaw PC_BACKEND",
            "source_refs": _json_list(
                [
                    "generated/read_models/invoice_review_bundle.json",
                    "generated/read_models/capital_hilton_invoice_delivery_steel_thread.json",
                    "capital_hilton_invoice_delivery_steel_thread.py",
                ]
            ),
            "operator_summary": "Next lane should reuse invoice rails while adding supplier portal proof, PO/Coupa posture, multi-invoice review, and approval complexity.",
            "developer_summary": "Keep supplier portal and Coupa capabilities as extensions, not defaults for simple invoice lanes.",
        },
        {
            "lane_ref": "st_annes_invoice_lane",
            "lane_name": "St. Anne's invoice lane",
            "business_object_type": "simple_invoice",
            "client_ref": "st_annes",
            "workflow_ref": "st_annes_invoice_workflow",
            "status": _status_or_unknown(overrides.get("st_annes_invoice_lane", st_annes_status), allowed=LANE_STATUSES),
            "current_stage": "Planned simple-invoice generalization with fixtures and Event Bridge handler evidence, but no completed business lane.",
            "canonical_owner_repo": "/home/openclaw PC_BACKEND",
            "source_refs": _json_list(
                [
                    "simple_invoice_workflow_fixtures.py",
                    "client_invoice_workflow_framework.py",
                    "generated/read_models/simple_invoice_event_bridge_rail_registry.json",
                    "generated/read_models/openclaw_event_bridge_contract.json",
                ]
            ),
            "operator_summary": "After Capital Hilton, prove the simple invoice rail generalizes without inheriting Coupa, supplier portal, or PO blockers.",
            "developer_summary": "Use the same simple rail and explicitly exclude Capital Hilton-specific portal/PO extensions.",
        },
    ]
    return rows


def _capability_row(
    *,
    capability_ref: str,
    capability_name: str,
    capability_type: str,
    produced_by_lane: str,
    status: str,
    reusable: bool,
    reusable_by: list[str],
    not_reusable_by: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    tests_refs: list[str] | None = None,
    risk_notes: str = "",
) -> dict[str, Any]:
    return {
        "capability_ref": capability_ref,
        "capability_name": capability_name,
        "capability_type": _status_or_unknown(capability_type, allowed=CAPABILITY_TYPES),
        "produced_by_lane": produced_by_lane,
        "status": _status_or_unknown(status, allowed=CAPABILITY_STATUSES),
        "reusable": reusable,
        "reusable_by": _json_list(reusable_by),
        "not_reusable_by": _json_list(not_reusable_by or []),
        "evidence_refs": _json_list(evidence_refs or []),
        "tests_refs": _json_list(tests_refs or []),
        "risk_notes": risk_notes,
    }


def _harvested_capability_rows(payloads: Mapping[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rail_present = bool(payloads.get("simple_invoice_event_bridge_rail_registry"))
    event_bridge_present = bool(payloads.get("event_bridge_contract"))
    authority_present = bool(payloads.get("authority_semantics_registry"))
    live_present = bool(payloads.get("live_arts_bundle"))
    capital_present = bool(payloads.get("capital_hilton_bundle"))
    return [
        _capability_row(
            capability_ref="capability:simple_invoice_rail",
            capability_name="Simple invoice rail",
            capability_type="WORKFLOW_RAIL",
            produced_by_lane="live_arts_md_invoice_lane",
            status="PROVEN" if rail_present else "UNKNOWN",
            reusable=True,
            reusable_by=["capital_hilton_invoice_lane", "st_annes_invoice_lane", "recurring_invoice_workflow"],
            evidence_refs=["generated/read_models/simple_invoice_event_bridge_rail_registry.json", "client_invoice_workflow_framework.py"],
            tests_refs=["tests/test_simple_invoice_event_bridge_rail_registry.py", "tests/test_client_invoice_workflow_framework.py"],
            risk_notes="Simple clients must not inherit Coupa, PO, or supplier portal blockers by default.",
        ),
        _capability_row(
            capability_ref="capability:invoice_candidate_selection",
            capability_name="Invoice candidate selection and collapse",
            capability_type="WORKFLOW_RAIL",
            produced_by_lane="live_arts_md_invoice_lane",
            status="PROVEN" if live_present else "UNKNOWN",
            reusable=True,
            reusable_by=["st_annes_invoice_lane", "recurring_invoice_workflow"],
            evidence_refs=["generated/read_models/live_arts_md_invoice_review_bundle.json"],
            tests_refs=["tests/test_simple_invoice_event_bridge_rail_registry.py"],
        ),
        _capability_row(
            capability_ref="capability:selected_invoice_summary_state",
            capability_name="Selected invoice summary state",
            capability_type="DATA_ACCESS_PATTERN",
            produced_by_lane="live_arts_md_invoice_lane",
            status="PROVEN" if live_present else "UNKNOWN",
            reusable=True,
            reusable_by=["st_annes_invoice_lane", "capital_hilton_invoice_lane"],
            evidence_refs=["generated/read_models/live_arts_md_invoice_review_bundle.json"],
            tests_refs=["tests/test_openclaw_business_object_layer_audit.py"],
        ),
        _capability_row(
            capability_ref="capability:event_bridge_prepare_pdf_action",
            capability_name="Event Bridge Prepare PDF action",
            capability_type="EVENT_BRIDGE_ACTION",
            produced_by_lane="live_arts_md_invoice_lane",
            status="PARTIAL" if event_bridge_present else "UNKNOWN",
            reusable=True,
            reusable_by=["st_annes_invoice_lane", "capital_hilton_invoice_lane", "Telegram compact invoice action"],
            evidence_refs=["generated/read_models/openclaw_event_bridge_contract.json", "openclaw_event_bridge_adapter.py"],
            tests_refs=["tests/test_openclaw_event_bridge_contract.py"],
            risk_notes="Must keep authority_boundary false-valued and no-authority guards in the allowed guard fields.",
        ),
        _capability_row(
            capability_ref="capability:pdf_artifact_package",
            capability_name="Scoped PDF artifact package",
            capability_type="ARTIFACT_POLICY",
            produced_by_lane="live_arts_md_invoice_lane",
            status="PARTIAL" if live_present else "UNKNOWN",
            reusable=True,
            reusable_by=["st_annes_invoice_lane", "capital_hilton_invoice_lane"],
            evidence_refs=["generated/read_models/live_arts_md_invoice_review_bundle.json"],
            tests_refs=["tests/test_openclaw_business_object_layer_audit.py"],
            risk_notes="Reusable package policy is present; Mac Excel export/helper path remains separately gated.",
        ),
        _capability_row(
            capability_ref="capability:manual_send_proof",
            capability_name="Manual send proof receipt",
            capability_type="PROOF_RECEIPT",
            produced_by_lane="live_arts_md_invoice_lane",
            status="PARTIAL" if live_present else "UNKNOWN",
            reusable=True,
            reusable_by=["st_annes_invoice_lane", "client_comms_follow_up"],
            evidence_refs=["generated/read_models/live_arts_md_invoice_review_bundle.json"],
            risk_notes="Proof capture is required before send/payment claims; no email sending authority is implied.",
        ),
        _capability_row(
            capability_ref="capability:payment_watch",
            capability_name="Read-only payment watch",
            capability_type="PAYMENT_WATCH",
            produced_by_lane="live_arts_md_invoice_lane",
            status="PARTIAL" if live_present else "UNKNOWN",
            reusable=True,
            reusable_by=["st_annes_invoice_lane", "payment_proof_intake_lane", "ledger_handoff_readiness_lane"],
            evidence_refs=["generated/read_models/live_arts_md_invoice_review_bundle.json"],
            risk_notes="Payment watch is readiness-only until proof/ledger gates are explicit.",
        ),
        _capability_row(
            capability_ref="capability:authority_boundary",
            capability_name="No-authority invoice boundary",
            capability_type="AUTHORITY_PROFILE",
            produced_by_lane="live_arts_md_invoice_lane",
            status="PARTIAL" if authority_present or event_bridge_present else "UNKNOWN",
            reusable=True,
            reusable_by=["capital_hilton_invoice_lane", "st_annes_invoice_lane", "payment_proof_intake_lane"],
            evidence_refs=["generated/read_models/openclaw_authority_semantics_registry.json", "generated/read_models/openclaw_event_bridge_contract.json"],
            tests_refs=["tests/test_openclaw_event_bridge_contract.py"],
        ),
        _capability_row(
            capability_ref="capability:mac_pc_bridge_response",
            capability_name="Mac/PC bridge scoped response",
            capability_type="SERVICE_PATTERN",
            produced_by_lane="live_arts_md_invoice_lane",
            status="PARTIAL" if event_bridge_present else "UNKNOWN",
            reusable=True,
            reusable_by=["capital_hilton_invoice_lane", "st_annes_invoice_lane", "Mac Excel helper/export execution"],
            evidence_refs=["openclaw_request_response_service.py", "generated/read_models/openclaw_event_bridge_contract.json"],
        ),
        _capability_row(
            capability_ref="capability:supplier_portal_proof",
            capability_name="Supplier portal proof intake",
            capability_type="PROOF_RECEIPT",
            produced_by_lane="capital_hilton_invoice_lane",
            status="PARTIAL" if capital_present else "UNKNOWN",
            reusable=True,
            reusable_by=["complex_invoice_lanes"],
            not_reusable_by=["live_arts_md_invoice_lane", "st_annes_invoice_lane"],
            evidence_refs=["generated/read_models/invoice_review_bundle.json", "capital_hilton_protected_proof_intake.py"],
            risk_notes="Proof intake is reusable; actual portal access/submission remains blocked without explicit authority.",
        ),
        _capability_row(
            capability_ref="capability:coupa_po_extension",
            capability_name="Coupa/PO extension",
            capability_type="DATA_ACCESS_PATTERN",
            produced_by_lane="capital_hilton_invoice_lane",
            status="PLANNED" if capital_present else "UNKNOWN",
            reusable=True,
            reusable_by=["complex_invoice_lanes"],
            not_reusable_by=["live_arts_md_invoice_lane", "st_annes_invoice_lane"],
            evidence_refs=["generated/read_models/invoice_review_bundle.json", "capital_hilton_coupa_po_retrieval_automation_candidate.py"],
            risk_notes="Must remain a protected extension, never the default simple-invoice rail.",
        ),
        _capability_row(
            capability_ref="capability:multi_invoice_review",
            capability_name="Multi-invoice review and selection",
            capability_type="WORKFLOW_RAIL",
            produced_by_lane="capital_hilton_invoice_lane",
            status="PARTIAL" if capital_present else "UNKNOWN",
            reusable=True,
            reusable_by=["complex_invoice_lanes"],
            not_reusable_by=["single_invoice_simple_lanes"],
            evidence_refs=["generated/read_models/invoice_review_bundle.json"],
        ),
        _capability_row(
            capability_ref="capability:guardian_approval_gates",
            capability_name="Guardian approval gates",
            capability_type="UI_PATTERN",
            produced_by_lane="capital_hilton_invoice_lane",
            status="PARTIAL" if capital_present else "UNKNOWN",
            reusable=True,
            reusable_by=["capital_hilton_invoice_lane", "client_comms_follow_up", "ledger_handoff_readiness_lane"],
            evidence_refs=["generated/read_models/invoice_review_bundle.json", "generated/read_models/capital_hilton_review_packet_approval.json"],
        ),
        _capability_row(
            capability_ref="capability:st_annes_simple_generalization",
            capability_name="St. Anne's simple invoice generalization",
            capability_type="WORKFLOW_RAIL",
            produced_by_lane="st_annes_invoice_lane",
            status="PLANNED" if rail_present else "UNKNOWN",
            reusable=True,
            reusable_by=["future_simple_invoice_lanes"],
            not_reusable_by=["coupa_supplier_portal_extensions"],
            evidence_refs=["simple_invoice_workflow_fixtures.py", "generated/read_models/simple_invoice_event_bridge_rail_registry.json"],
            tests_refs=["tests/test_simple_invoice_event_bridge_rail_registry.py", "tests/test_client_invoice_workflow_framework.py"],
            risk_notes="Should prove generalization without importing Capital Hilton portal/PO complexity.",
        ),
    ]


def _capability_dependencies() -> list[dict[str, Any]]:
    rows = [
        ("dependency:selected_summary_requires_candidate_selection", "capability:selected_invoice_summary_state", "capability:invoice_candidate_selection", "REQUIRED", "Selected summary must be derived from a confirmed candidate receipt/state."),
        ("dependency:pdf_package_requires_selected_summary", "capability:pdf_artifact_package", "capability:selected_invoice_summary_state", "REQUIRED", "Scoped artifact package requires invoice id, sheet, and selected summary."),
        ("dependency:prepare_pdf_extends_event_bridge", "capability:pdf_artifact_package", "capability:event_bridge_prepare_pdf_action", "EXTENDS", "The package is delivered through the Event Bridge action contract."),
        ("dependency:payment_watch_requires_send_proof", "capability:payment_watch", "capability:manual_send_proof", "BLOCKED_BY", "Payment watch becomes meaningful only after manual send or send receipt."),
        ("dependency:capital_coupa_extends_simple_invoice", "capability:coupa_po_extension", "capability:simple_invoice_rail", "EXTENDS", "Capital Hilton adds portal/PO posture on top of invoice rails."),
        ("dependency:portal_proof_requires_authority", "capability:supplier_portal_proof", "capability:authority_boundary", "REQUIRED", "Portal proof must remain receipt-only until explicit authority exists."),
        ("dependency:guardian_gates_require_proof", "capability:guardian_approval_gates", "capability:supplier_portal_proof", "OPTIONAL", "Capital Hilton approval quality improves after portal/proof evidence is captured."),
        ("dependency:st_annes_replaces_capital_extensions", "capability:st_annes_simple_generalization", "capability:coupa_po_extension", "REPLACES", "St. Anne's should prove the simple lane does not inherit Coupa/PO extension."),
    ]
    return [
        {
            "dependency_ref": ref,
            "capability_ref": cap,
            "depends_on_capability_ref": depends,
            "dependency_type": _status_or_unknown(dep_type, allowed=DEPENDENCY_TYPES),
            "notes": notes,
        }
        for ref, cap, depends, dep_type, notes in rows
    ]


def _reuse_plans() -> list[dict[str, Any]]:
    return [
        {
            "reuse_plan_ref": "reuse:live_arts_to_capital_hilton",
            "source_lane_ref": "live_arts_md_invoice_lane",
            "target_lane_ref": "capital_hilton_invoice_lane",
            "reused_capabilities": _json_list(["capability:simple_invoice_rail", "capability:event_bridge_prepare_pdf_action", "capability:authority_boundary", "capability:manual_send_proof"]),
            "new_capabilities_to_add": _json_list(["capability:supplier_portal_proof", "capability:coupa_po_extension", "capability:multi_invoice_review", "capability:guardian_approval_gates"]),
            "blocked_capabilities": _json_list(["live Coupa submit", "ledger posting", "email send"]),
            "expected_tests": _json_list(["tests/test_capital_hilton_protected_proof_intake.py", "tests/test_capital_hilton_review_packet_approval.py"]),
            "status": "NEEDS_ADAPTER",
        },
        {
            "reuse_plan_ref": "reuse:live_arts_to_st_annes",
            "source_lane_ref": "live_arts_md_invoice_lane",
            "target_lane_ref": "st_annes_invoice_lane",
            "reused_capabilities": _json_list(["capability:simple_invoice_rail", "capability:event_bridge_prepare_pdf_action", "capability:invoice_candidate_selection", "capability:pdf_artifact_package", "capability:payment_watch"]),
            "new_capabilities_to_add": _json_list(["capability:st_annes_simple_generalization", "client-specific workbook/profile adapter"]),
            "blocked_capabilities": _json_list(["Coupa", "supplier portal", "purchase order blockers"]),
            "expected_tests": _json_list(["tests/test_simple_invoice_event_bridge_rail_registry.py", "tests/test_client_invoice_workflow_framework.py"]),
            "status": "PLANNED",
        },
        {
            "reuse_plan_ref": "reuse:invoice_sequence_to_payment_proof_intake",
            "source_lane_ref": "st_annes_invoice_lane",
            "target_lane_ref": "payment_proof_intake_lane",
            "reused_capabilities": _json_list(["capability:payment_watch", "capability:manual_send_proof", "capability:authority_boundary"]),
            "new_capabilities_to_add": _json_list(["payment proof intake receipt"]),
            "blocked_capabilities": _json_list(["ledger posting"]),
            "expected_tests": _json_list(["future:test_payment_proof_intake_registry"]),
            "status": "PLANNED",
        },
    ]


def _next_lane_candidates() -> list[dict[str, Any]]:
    candidates = [
        ("payment_proof_intake_lane", "payment proof intake", "payment_proof", "Reuses invoice proof/payment watch and adds one receipt intake for payment evidence.", ["payment_watch", "manual_send_proof", "authority_boundary"], ["payment proof receipt intake"], 2, 9, 2, "High leverage after invoices because it turns sent invoices into tracked receivables.", 1, "local deterministic codex", ["invoice steel-thread sequence proven"], ["do not post ledger", "do not access bank without explicit authority"], "PLANNED"),
        ("ledger_handoff_readiness_lane", "ledger handoff readiness", "ledger_readiness", "Reuses proof/approval/payment evidence to prepare a no-post ledger handoff.", ["payment_watch", "proof_receipts", "guardian_approval_gates"], ["ledger handoff readiness packet"], 3, 8, 4, "Useful after payment proof exists, but posting remains out of scope.", 2, "local deterministic codex", ["payment proof intake proven", "approval gates proven"], ["do not post ledger"], "PLANNED"),
        ("client_comms_follow_up_lane", "client comms follow-up", "client_comms", "Reuses Clara draft/proof/approval shape and adds follow-up scheduling/readiness.", ["manual_send_proof", "guardian_approval_gates", "clara_draft"], ["follow-up readiness receipt"], 4, 7, 3, "Good adjacent lane once send/proof rails are stable.", 3, "local deterministic codex", ["manual proof capture proven"], ["do not send email"], "PLANNED"),
        ("recurring_invoice_workflow_lane", "recurring invoice workflow", "recurring_invoice", "Reuses simple invoice rail and adds recurrence policy.", ["simple_invoice_rail", "candidate_selection", "payment_watch"], ["recurrence policy"], 5, 7, 4, "Useful after St. Anne's proves simple-lane generalization.", 4, "local deterministic codex", ["St. Anne's lane proven"], ["do not infer workbook data"], "PLANNED"),
        ("estimate_quote_workflow_lane", "estimate/quote workflow", "estimate_quote", "Reuses approval/proof shape but adds a new pre-invoice object.", ["guardian_approval_gates", "client_comms"], ["quote lifecycle"], 6, 5, 4, "Later adjacent business object after receivable rails are stable.", 5, "local deterministic codex", ["invoice rails stable"], ["do not send quotes"], "PLANNED"),
        ("gig_settlement_packet_lane", "gig settlement packet", "settlement_packet", "Reuses proof packet and adds settlement summary object.", ["proof_receipts", "payment_watch"], ["settlement packet"], 6, 5, 4, "Useful for performance workflows after invoice rails.", 6, "local deterministic codex", ["payment proof intake proven"], ["do not mutate ledger"], "PLANNED"),
        ("contract_proof_packet_lane", "contract/proof packet workflow", "contract_packet", "Reuses proof/approval packet machinery for contract evidence.", ["proof_receipts", "guardian_approval_gates"], ["contract packet policy"], 6, 4, 5, "Park until invoice proof patterns are stable.", 7, "local deterministic codex", ["proof packet evals"], ["do not sign contracts"], "PLANNED"),
        ("telegram_compact_invoice_action_lane", "Telegram compact invoice action", "compact_surface", "Reuses Event Bridge action but adds compact UI surface.", ["event_bridge_prepare_pdf_action", "authority_boundary"], ["compact invoice command"], 7, 4, 5, "Do not prioritize before object rails are proven.", 8, "local deterministic codex", ["invoice lanes proven"], ["do not do generic Telegram polish"], "PLANNED"),
        ("mac_excel_helper_export_execution_lane", "Mac Excel helper/export execution", "mac_helper", "Targets unresolved Mac-local export helper capability.", ["pdf_artifact_package", "mac_pc_bridge_response"], ["Mac local helper worker"], 7, 5, 6, "Important only when explicitly targeting the Mac permission/helper problem.", 9, "mac bounded implementation package", ["local bridge stable", "helper architecture approved"], ["do not remote/cloud relay first"], "PLANNED"),
        ("service_supervision_recovery_action_lane", "service supervision recovery action", "service_supervision", "Reuses service supervision and keeper patterns for recovery receipts.", ["service supervision", "change sentinel"], ["recovery action receipt"], 5, 6, 3, "Infrastructure-adjacent; keep behind business-object rail work.", 10, "local deterministic codex", ["current service keeper stable"], ["do not run proofs or Chief from keeper"], "PLANNED"),
    ]
    return [
        {
            "candidate_ref": ref,
            "lane_name": name,
            "business_object_type": business_type,
            "reason_to_build": reason,
            "capabilities_reused": _json_list(reused),
            "capabilities_added": _json_list(added),
            "novelty_score": novelty,
            "reuse_score": reuse,
            "risk_score": risk,
            "expected_leverage": leverage,
            "recommended_order": order,
            "preferred_model": model,
            "prerequisites": _json_list(prerequisites),
            "do_not_do": _json_list(do_not_do),
            "status": status,
        }
        for ref, name, business_type, reason, reused, added, novelty, reuse, risk, leverage, order, model, prerequisites, do_not_do, status in candidates
    ]


def _all_invoice_lanes_proven(lanes: list[dict[str, Any]]) -> bool:
    needed = {
        "live_arts_md_invoice_lane",
        "capital_hilton_invoice_lane",
        "st_annes_invoice_lane",
    }
    return all(row["status"] == "PROVEN" for row in lanes if row["lane_ref"] in needed) and needed.issubset(
        {row["lane_ref"] for row in lanes}
    )


def _hermes_recommendation(
    lanes: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    all_proven = _all_invoice_lanes_proven(lanes)
    if not all_proven:
        statuses = {row["lane_ref"]: row["status"] for row in lanes}
        return {
            "recommendation_ref": "hermes_recommendation:finish_invoice_steel_thread_sequence",
            "generated_at": generated_at,
            "recommended_next_lane": "finish_invoice_steel_thread_sequence",
            "reason": "Live Arts, Capital Hilton, and St. Anne's are not all proven. Finish the invoice steel-thread sequence before opening a new adjacent lane.",
            "evidence_refs": _json_list(["generated/read_models/live_arts_md_invoice_review_bundle.json", "generated/read_models/invoice_review_bundle.json", "generated/read_models/simple_invoice_event_bridge_rail_registry.json"]),
            "required_preconditions": _json_list(["Live Arts PDF/proof/payment gates stable", "Capital Hilton supplier portal/Coupa/approval extension proven", "St. Anne's simple invoice generalization proven"]),
            "expected_new_capability": "completed reusable invoice steel-thread sequence",
            "expected_reused_capabilities": _json_list(["simple invoice rail", "Event Bridge Prepare PDF action", "proof receipts", "authority boundary", "payment watch"]),
            "confidence": "HIGH" if statuses.get("live_arts_md_invoice_lane") != "UNKNOWN" else "MEDIUM",
            "operator_copy": "Hermes should keep the build order on Live Arts -> Capital Hilton -> St. Anne's until those lanes prove the reusable invoice rail.",
            "chief_build_task_ref": "chief_build_task:finish_invoice_steel_thread_sequence",
        }
    chosen = sorted(candidates, key=lambda row: (row["recommended_order"], -row["reuse_score"], row["risk_score"]))[0]
    return {
        "recommendation_ref": "hermes_recommendation:payment_proof_intake_after_invoice_sequence",
        "generated_at": generated_at,
        "recommended_next_lane": chosen["candidate_ref"],
        "reason": "All three invoice lanes are proven; payment proof intake reuses the most invoice proof/payment infrastructure while adding one bounded adjacent capability.",
        "evidence_refs": _json_list(["openclaw_lane_capability_harvest.json#next_lane_candidate:payment_proof_intake_lane"]),
        "required_preconditions": chosen["prerequisites"],
        "expected_new_capability": "payment proof receipt intake",
        "expected_reused_capabilities": chosen["capabilities_reused"],
        "confidence": "MEDIUM_HIGH",
        "operator_copy": "Hermes should recommend payment proof intake next, not ledger posting or generic chat polish.",
        "chief_build_task_ref": "chief_build_task:build_payment_proof_intake_registry",
    }


def _capability_gaps(lanes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    all_proven = _all_invoice_lanes_proven(lanes)
    return [
        {
            "gap_ref": "gap:invoice_steel_thread_not_all_proven",
            "gap_name": "Invoice steel-thread sequence not all proven",
            "affected_lanes": _json_list(["live_arts_md_invoice_lane", "capital_hilton_invoice_lane", "st_annes_invoice_lane"]),
            "missing_capability": "three-lane invoice generalization proof",
            "why_it_matters": "Hermes should not select the next business lane until the reusable invoice rail survives simple, complex, and second-simple cases.",
            "severity": "HIGH" if not all_proven else "RESOLVED",
            "suggested_fix": "Finish Live Arts, then Capital Hilton, then St. Anne's with proof receipts and tests.",
            "target_repo": "/home/openclaw",
            "preferred_model": "local deterministic codex",
            "status": "OPEN" if not all_proven else "RESOLVED",
        },
        {
            "gap_ref": "gap:mac_excel_helper_export_execution",
            "gap_name": "Mac Excel helper/export execution unresolved",
            "affected_lanes": _json_list(["live_arts_md_invoice_lane", "st_annes_invoice_lane"]),
            "missing_capability": "Mac-local helper/permission architecture for Excel PDF export",
            "why_it_matters": "PDF artifact packages remain candidates until a valid local export receipt exists.",
            "severity": "HIGH",
            "suggested_fix": "Build a bounded Mac helper work package after local bridge/schema stability is proven.",
            "target_repo": "Mac app/helper repo",
            "preferred_model": "bounded Mac implementation package",
            "status": "OPEN",
        },
        {
            "gap_ref": "gap:capital_hilton_supplier_portal_proof",
            "gap_name": "Capital Hilton supplier portal/Coupa proof extension",
            "affected_lanes": _json_list(["capital_hilton_invoice_lane"]),
            "missing_capability": "supplier portal proof and PO/Coupa posture without submit authority",
            "why_it_matters": "Capital Hilton is the intended complex-invoice proof of reuse plus one hard extension.",
            "severity": "HIGH",
            "suggested_fix": "Keep Coupa/portal as protected proof intake first; do not build submit automation.",
            "target_repo": "/home/openclaw",
            "preferred_model": "local deterministic codex",
            "status": "OPEN",
        },
        {
            "gap_ref": "gap:lane_reuse_evals",
            "gap_name": "Lane reuse eval coverage",
            "affected_lanes": _json_list(["all_invoice_lanes", "future_lanes"]),
            "missing_capability": "eval pattern proving reused capability does not import lane-specific blockers",
            "why_it_matters": "St. Anne's must prove that simple invoice rails do not inherit Capital Hilton Coupa/PO complexity.",
            "severity": "MEDIUM",
            "suggested_fix": "Add fixture tests per lane reuse plan before promoting capability status to PROVEN.",
            "target_repo": "/home/openclaw",
            "preferred_model": "local deterministic codex",
            "status": "OPEN",
        },
        {
            "gap_ref": "gap:ledger_handoff_readiness_not_posting",
            "gap_name": "Ledger handoff readiness is not ledger posting",
            "affected_lanes": _json_list(["ledger_handoff_readiness_lane", "payment_proof_intake_lane"]),
            "missing_capability": "no-post ledger handoff packet after proof/approval",
            "why_it_matters": "Posting must stay blocked until proof, approval, and authority are proven.",
            "severity": "MEDIUM",
            "suggested_fix": "Build readiness-only handoff after payment proof intake, not before.",
            "target_repo": "/home/openclaw",
            "preferred_model": "local deterministic codex",
            "status": "PLANNED",
        },
    ]


def build_lane_capability_harvest(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    system_knowledge_root: str | Path = DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
    wiki_root: str | Path = DEFAULT_WIKI_ROOT,
    generated_at: str | None = None,
    lane_status_overrides: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    input_manifest, payloads = _source_manifest(read_model_root=read_model_root, wiki_root=wiki_root)
    lanes = _lane_rows(payloads, lane_status_overrides=lane_status_overrides)
    capabilities = _harvested_capability_rows(payloads)
    dependencies = _capability_dependencies()
    reuse_plans = _reuse_plans()
    candidates = _next_lane_candidates()
    recommendation = _hermes_recommendation(lanes, candidates, generated_at=generated)
    gaps = _capability_gaps(lanes)
    missing_inputs = [row["input_ref"] for row in input_manifest if row["required"] and row["status"] != "PRESENT"]
    readiness = "READY_FOR_PLANNING_NOT_EXECUTION" if not missing_inputs else "NOT_READY_MISSING_REQUIRED_INPUT"
    confidence = "HIGH" if not missing_inputs else "MEDIUM"
    return {
        "schema_version": READ_MODEL_VERSION,
        "contract_schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated,
        "read_model_id": READ_MODEL_ID,
        "purpose": "Query lane proof, reusable capabilities, and Hermes next build recommendation without live automation.",
        "core_doctrine": "Every lane should solve its business object and harvest at least one reusable capability for future lanes.",
        "readiness": readiness,
        "confidence": confidence,
        "input_manifest": input_manifest,
        "missing_inputs": missing_inputs,
        "lanes": lanes,
        "harvested_capabilities": capabilities,
        "capability_dependencies": dependencies,
        "reuse_plans": reuse_plans,
        "next_lane_candidates": candidates,
        "hermes_recommendation": recommendation,
        "top_gaps": gaps,
        "do_not_work_now": list(DO_NOT_WORK_NOW),
        "source_refs": [row["path"] for row in input_manifest if row["status"] == "PRESENT"],
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def operator_markdown(read_model: Mapping[str, Any]) -> str:
    recommendation = dict(read_model.get("hermes_recommendation", {}))
    lanes = {row["lane_ref"]: row for row in read_model.get("lanes", [])}
    capabilities = read_model.get("harvested_capabilities", [])
    live_caps = [row["capability_name"] for row in capabilities if row.get("produced_by_lane") == "live_arts_md_invoice_lane"]
    capital_reuse = next((row for row in read_model.get("reuse_plans", []) if row.get("target_lane_ref") == "capital_hilton_invoice_lane"), {})
    st_annes_reuse = next((row for row in read_model.get("reuse_plans", []) if row.get("target_lane_ref") == "st_annes_invoice_lane"), {})
    lines = [
        "# OpenClaw Lane Capability Harvest",
        "",
        f"- Readiness: `{read_model.get('readiness', 'UNKNOWN')}`",
        f"- Confidence: `{read_model.get('confidence', 'UNKNOWN')}`",
        f"- Hermes recommendation: `{recommendation.get('recommended_next_lane', 'UNKNOWN')}`",
        f"- Chief build task: `{recommendation.get('chief_build_task_ref', '')}`",
        "",
        "## What Live Arts Taught OpenClaw",
        "",
        f"Live Arts status: `{lanes.get('live_arts_md_invoice_lane', {}).get('status', 'UNKNOWN')}`.",
        "Harvested capabilities: " + ", ".join(live_caps) + ".",
        "",
        "## What Capital Hilton Should Reuse",
        "",
        f"Capital Hilton status: `{lanes.get('capital_hilton_invoice_lane', {}).get('status', 'UNKNOWN')}`.",
        f"Reuse: `{capital_reuse.get('reused_capabilities', '[]')}`.",
        "Add only the complex extensions: supplier portal proof, Coupa/PO posture, multi-invoice review, and approval gates.",
        "",
        "## What St. Anne's Should Reuse",
        "",
        f"St. Anne's status: `{lanes.get('st_annes_invoice_lane', {}).get('status', 'UNKNOWN')}`.",
        f"Reuse: `{st_annes_reuse.get('reused_capabilities', '[]')}`.",
        "Do not inherit Coupa, supplier portal, or PO blockers.",
        "",
        "## After The Three Invoice Lanes",
        "",
        "If Live Arts, Capital Hilton, and St. Anne's are all proven, the next adjacent lane should be payment proof intake.",
        "",
        "## Hermes Next",
        "",
        recommendation.get("operator_copy", ""),
        "",
        "## Chief Next",
        "",
        recommendation.get("chief_build_task_ref", ""),
        "",
        "## Do Not Work Now",
        "",
    ]
    for item in read_model.get("do_not_work_now", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Boundary", ""])
    lines.append("This registry is planning/read-model only. It performs no service start, LM call, Chief launch, email/Gmail/browser/Coupa access, workbook cell read, PDF export, ledger mutation, production mutation, or push.")
    lines.append("")
    return "\n".join(lines)


def sqlite_schema_sql() -> str:
    return """CREATE TABLE lane (
  lane_ref TEXT PRIMARY KEY,
  lane_name TEXT,
  business_object_type TEXT,
  client_ref TEXT,
  workflow_ref TEXT,
  status TEXT,
  current_stage TEXT,
  canonical_owner_repo TEXT,
  source_refs TEXT,
  operator_summary TEXT,
  developer_summary TEXT
);

CREATE TABLE harvested_capability (
  capability_ref TEXT PRIMARY KEY,
  capability_name TEXT,
  capability_type TEXT,
  produced_by_lane TEXT,
  status TEXT,
  reusable INTEGER,
  reusable_by TEXT,
  not_reusable_by TEXT,
  evidence_refs TEXT,
  tests_refs TEXT,
  risk_notes TEXT
);

CREATE TABLE capability_dependency (
  dependency_ref TEXT PRIMARY KEY,
  capability_ref TEXT,
  depends_on_capability_ref TEXT,
  dependency_type TEXT,
  notes TEXT
);

CREATE TABLE lane_reuse_plan (
  reuse_plan_ref TEXT PRIMARY KEY,
  source_lane_ref TEXT,
  target_lane_ref TEXT,
  reused_capabilities TEXT,
  new_capabilities_to_add TEXT,
  blocked_capabilities TEXT,
  expected_tests TEXT,
  status TEXT
);

CREATE TABLE next_lane_candidate (
  candidate_ref TEXT PRIMARY KEY,
  lane_name TEXT,
  business_object_type TEXT,
  reason_to_build TEXT,
  capabilities_reused TEXT,
  capabilities_added TEXT,
  novelty_score INTEGER,
  reuse_score INTEGER,
  risk_score INTEGER,
  expected_leverage TEXT,
  recommended_order INTEGER,
  preferred_model TEXT,
  prerequisites TEXT,
  do_not_do TEXT,
  status TEXT
);

CREATE TABLE hermes_recommendation (
  recommendation_ref TEXT PRIMARY KEY,
  generated_at TEXT,
  recommended_next_lane TEXT,
  reason TEXT,
  evidence_refs TEXT,
  required_preconditions TEXT,
  expected_new_capability TEXT,
  expected_reused_capabilities TEXT,
  confidence TEXT,
  operator_copy TEXT,
  chief_build_task_ref TEXT
);

CREATE TABLE capability_gap (
  gap_ref TEXT PRIMARY KEY,
  gap_name TEXT,
  affected_lanes TEXT,
  missing_capability TEXT,
  why_it_matters TEXT,
  severity TEXT,
  suggested_fix TEXT,
  target_repo TEXT,
  preferred_model TEXT,
  status TEXT
);
"""


def _sql_quote(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _insert_sql(table: str, values: list[object]) -> str:
    return f"INSERT INTO {table} VALUES (" + ", ".join(_sql_quote(value) for value in values) + ");"


def sqlite_seed_sql(read_model: Mapping[str, Any]) -> str:
    lines: list[str] = []
    for row in read_model.get("lanes", []):
        lines.append(_insert_sql("lane", [row[key] for key in ("lane_ref", "lane_name", "business_object_type", "client_ref", "workflow_ref", "status", "current_stage", "canonical_owner_repo", "source_refs", "operator_summary", "developer_summary")]))
    for row in read_model.get("harvested_capabilities", []):
        lines.append(_insert_sql("harvested_capability", [row["capability_ref"], row["capability_name"], row["capability_type"], row["produced_by_lane"], row["status"], bool(row["reusable"]), row["reusable_by"], row["not_reusable_by"], row["evidence_refs"], row["tests_refs"], row["risk_notes"]]))
    for row in read_model.get("capability_dependencies", []):
        lines.append(_insert_sql("capability_dependency", [row["dependency_ref"], row["capability_ref"], row["depends_on_capability_ref"], row["dependency_type"], row["notes"]]))
    for row in read_model.get("reuse_plans", []):
        lines.append(_insert_sql("lane_reuse_plan", [row["reuse_plan_ref"], row["source_lane_ref"], row["target_lane_ref"], row["reused_capabilities"], row["new_capabilities_to_add"], row["blocked_capabilities"], row["expected_tests"], row["status"]]))
    for row in read_model.get("next_lane_candidates", []):
        lines.append(_insert_sql("next_lane_candidate", [row["candidate_ref"], row["lane_name"], row["business_object_type"], row["reason_to_build"], row["capabilities_reused"], row["capabilities_added"], row["novelty_score"], row["reuse_score"], row["risk_score"], row["expected_leverage"], row["recommended_order"], row["preferred_model"], row["prerequisites"], row["do_not_do"], row["status"]]))
    rec = read_model.get("hermes_recommendation", {})
    if rec:
        lines.append(_insert_sql("hermes_recommendation", [rec["recommendation_ref"], rec["generated_at"], rec["recommended_next_lane"], rec["reason"], rec["evidence_refs"], rec["required_preconditions"], rec["expected_new_capability"], rec["expected_reused_capabilities"], rec["confidence"], rec["operator_copy"], rec["chief_build_task_ref"]]))
    for row in read_model.get("top_gaps", []):
        lines.append(_insert_sql("capability_gap", [row["gap_ref"], row["gap_name"], row["affected_lanes"], row["missing_capability"], row["why_it_matters"], row["severity"], row["suggested_fix"], row["target_repo"], row["preferred_model"], row["status"]]))
    return "\n".join(lines) + ("\n" if lines else "")


def create_sqlite_registry(read_model: Mapping[str, Any], sqlite_path: str | Path) -> None:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    try:
        connection.executescript(sqlite_schema_sql())
        for row in read_model.get("lanes", []):
            connection.execute(
                "INSERT INTO lane VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(row[key] for key in ("lane_ref", "lane_name", "business_object_type", "client_ref", "workflow_ref", "status", "current_stage", "canonical_owner_repo", "source_refs", "operator_summary", "developer_summary")),
            )
        for row in read_model.get("harvested_capabilities", []):
            connection.execute(
                "INSERT INTO harvested_capability VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row["capability_ref"], row["capability_name"], row["capability_type"], row["produced_by_lane"], row["status"], 1 if row["reusable"] else 0, row["reusable_by"], row["not_reusable_by"], row["evidence_refs"], row["tests_refs"], row["risk_notes"]),
            )
        for row in read_model.get("capability_dependencies", []):
            connection.execute(
                "INSERT INTO capability_dependency VALUES (?, ?, ?, ?, ?)",
                (row["dependency_ref"], row["capability_ref"], row["depends_on_capability_ref"], row["dependency_type"], row["notes"]),
            )
        for row in read_model.get("reuse_plans", []):
            connection.execute(
                "INSERT INTO lane_reuse_plan VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (row["reuse_plan_ref"], row["source_lane_ref"], row["target_lane_ref"], row["reused_capabilities"], row["new_capabilities_to_add"], row["blocked_capabilities"], row["expected_tests"], row["status"]),
            )
        for row in read_model.get("next_lane_candidates", []):
            connection.execute(
                "INSERT INTO next_lane_candidate VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row["candidate_ref"], row["lane_name"], row["business_object_type"], row["reason_to_build"], row["capabilities_reused"], row["capabilities_added"], row["novelty_score"], row["reuse_score"], row["risk_score"], row["expected_leverage"], row["recommended_order"], row["preferred_model"], row["prerequisites"], row["do_not_do"], row["status"]),
            )
        rec = read_model.get("hermes_recommendation", {})
        if rec:
            connection.execute(
                "INSERT INTO hermes_recommendation VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rec["recommendation_ref"], rec["generated_at"], rec["recommended_next_lane"], rec["reason"], rec["evidence_refs"], rec["required_preconditions"], rec["expected_new_capability"], rec["expected_reused_capabilities"], rec["confidence"], rec["operator_copy"], rec["chief_build_task_ref"]),
            )
        for row in read_model.get("top_gaps", []):
            connection.execute(
                "INSERT INTO capability_gap VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row["gap_ref"], row["gap_name"], row["affected_lanes"], row["missing_capability"], row["why_it_matters"], row["severity"], row["suggested_fix"], row["target_repo"], row["preferred_model"], row["status"]),
            )
        connection.commit()
    finally:
        connection.close()


def export_openclaw_lane_capability_harvest(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    system_knowledge_root: str | Path = DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
    wiki_root: str | Path = DEFAULT_WIKI_ROOT,
    generated_at: str | None = None,
    lane_status_overrides: Mapping[str, str] | None = None,
) -> LaneCapabilityHarvestExportResult:
    read_root = _rooted(read_model_root)
    system_root = _rooted(system_knowledge_root)
    read_model = build_lane_capability_harvest(
        read_model_root=read_model_root,
        system_knowledge_root=system_knowledge_root,
        wiki_root=wiki_root,
        generated_at=generated_at,
        lane_status_overrides=lane_status_overrides,
    )
    json_path = read_root / JSON_EXPORT_NAME
    operator_path = read_root / OPERATOR_EXPORT_NAME
    sqlite_path = system_root / SQLITE_EXPORT_NAME
    schema_path = system_root / SCHEMA_EXPORT_NAME
    seed_path = system_root / SEED_EXPORT_NAME
    _atomic_write_text(json_path, stable_json(read_model))
    _atomic_write_text(operator_path, operator_markdown(read_model))
    _atomic_write_text(schema_path, sqlite_schema_sql())
    _atomic_write_text(seed_path, sqlite_seed_sql(read_model))
    create_sqlite_registry(read_model, sqlite_path)
    return LaneCapabilityHarvestExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        sqlite_path=_display_path(sqlite_path),
        schema_sql_path=_display_path(schema_path),
        seed_sql_path=_display_path(seed_path),
        lane_count=len(read_model["lanes"]),
        harvested_capability_count=len(read_model["harvested_capabilities"]),
        hermes_recommended_next_lane=str(read_model["hermes_recommendation"]["recommended_next_lane"]),
        readiness=str(read_model["readiness"]),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the OpenClaw lane capability harvest registry.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--system-knowledge-root", default=str(DEFAULT_SYSTEM_KNOWLEDGE_ROOT))
    parser.add_argument("--wiki-root", default=str(DEFAULT_WIKI_ROOT))
    parser.add_argument("--generated-at", default="")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)
    result = export_openclaw_lane_capability_harvest(
        read_model_root=args.read_model_root,
        system_knowledge_root=args.system_knowledge_root,
        wiki_root=args.wiki_root,
        generated_at=args.generated_at or None,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(f"json={result.json_path}")
        print(f"operator={result.operator_path}")
        print(f"sqlite={result.sqlite_path}")
        print(f"lanes={result.lane_count}")
        print(f"harvested_capabilities={result.harvested_capability_count}")
        print(f"hermes_recommended_next_lane={result.hermes_recommended_next_lane}")
        print(f"readiness={result.readiness}")
    return 0 if result.readiness.startswith("READY") else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
