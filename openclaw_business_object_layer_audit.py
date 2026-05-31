"""OpenClaw Business-Object Implementation Layer Audit.

This export is a deterministic read-only audit over current local registries,
read-models, generated wiki pages, and source/test evidence. It does not use a
prior audit as source truth, and it does not start services, launch Chief, call
an LM, open email/browser/Coupa, read workbooks, export PDFs, mutate ledgers, or
push.
"""

from __future__ import annotations

import argparse
import glob
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_SYSTEM_KNOWLEDGE_ROOT = Path("generated/system_knowledge")
DEFAULT_WIKI_ROOT = Path("generated/wiki/openclaw")

SCHEMA_VERSION = "openclaw_business_object_layer_audit_v0"
READ_MODEL_VERSION = "openclaw_business_object_layer_audit_read_model_v0"
JSON_EXPORT_NAME = "openclaw_business_object_layer_audit.json"
OPERATOR_EXPORT_NAME = "openclaw_business_object_layer_audit_OPERATOR.md"
SQLITE_EXPORT_NAME = "openclaw_business_object_layer_audit.sqlite"

SCORE_CATEGORIES = (
    "Workflow Design",
    "Data Access",
    "Authority",
    "Evals",
    "Audit Trails & Recovery",
    "Business Object Proximity",
)

BUSINESS_OBJECT_NAMES = (
    "Live Arts invoice",
    "Live Arts PDF artifact",
    "Live Arts payment watch",
    "Capital Hilton invoice",
    "Clara draft",
    "client comms thread",
    "Guardian approval",
    "Mac edge job package",
    "Mac Excel helper/proposed helper",
    "Access Broker",
    "service supervision",
    "reference resolver",
    "change sentinel",
    "estate topology registry",
    "context wiki",
    "openclaw-eyes registry branch",
)

NO_AUTHORITY_FLAGS = {
    "metadata_only": True,
    "read_model_only": True,
    "sqlite_registry_only": True,
    "services_started": False,
    "services_restarted": False,
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
class BusinessObjectLayerAuditExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    sqlite_path: str
    score_count: int
    business_object_count: int
    gap_count: int
    missing_eval_count: int
    readiness: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


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


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _nested(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _existing(path: str | Path) -> bool:
    return _rooted(path).exists()


def collect_inputs(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    wiki_root: str | Path = DEFAULT_WIKI_ROOT,
) -> dict[str, Any]:
    read_root = _rooted(read_model_root)
    wiki = _rooted(wiki_root)
    hermes_paths = sorted(read_root.glob("hermes_*.json"))
    wiki_paths = sorted(wiki.glob("*.md")) if wiki.exists() else []
    source_evidence = {
        "context_wiki_compiler": _existing("openclaw_context_wiki_compiler.py"),
        "context_wiki_tests": _existing("tests/test_openclaw_context_wiki_compiler.py"),
        "service_supervision_source": _existing("openclaw_service_supervision.py"),
        "service_keeper_source": _existing("scripts/openclaw_service_keeper.py"),
        "request_response_service_template": _existing("systemd/user/openclaw-request-response.service.in"),
        "reference_resolver_source": _existing("openclaw_reference_resolver.py"),
        "change_sentinel_source": _existing("openclaw_change_sentinel.py"),
        "estate_topology_source": _existing("openclaw_estate_topology_registry.py"),
    }
    return {
        "read_model_root": read_root,
        "wiki_root": wiki,
        "estate": _read_json(read_root / "openclaw_estate_topology_registry.json"),
        "resolver": _read_json(read_root / "openclaw_reference_resolver.json"),
        "sentinel": _read_json(read_root / "openclaw_change_sentinel.json"),
        "wiki_index": _read_json(read_root / "openclaw_context_wiki_index.json"),
        "live_arts": _read_json(read_root / "live_arts_md_invoice_review_bundle.json"),
        "capital_hilton": _read_json(read_root / "invoice_review_bundle.json"),
        "purpose_charter": _read_json(read_root / "purpose_bound_automation_charter.json"),
        "service_supervision": _read_json(read_root / "openclaw_service_supervision.json"),
        "hermes": {path.name: _read_json(path) for path in hermes_paths},
        "wiki_pages": [_display_path(path) for path in wiki_paths],
        "source_evidence": source_evidence,
    }


def _source_ref(path: str, note: str = "") -> dict[str, str]:
    return {"path": path, "note": note}


def _live_bundle(inputs: dict[str, Any]) -> dict[str, Any]:
    return inputs["live_arts"].get("live_arts_md_bundle", {})


def _capital_bundle(inputs: dict[str, Any]) -> dict[str, Any]:
    return inputs["capital_hilton"].get("capital_hilton_bundle", {})


def _truth_area(inputs: dict[str, Any], area_id: str) -> dict[str, Any]:
    for area in inputs["estate"].get("source_of_truth_areas", []):
        if area.get("area_id") == area_id:
            return area
    return {}


def _branch_ref(inputs: dict[str, Any], target_ref: str) -> dict[str, Any]:
    for branch in inputs["resolver"].get("git_branch_refs", []):
        if branch.get("target_ref") == target_ref:
            return branch
    return {}


def _resolution(inputs: dict[str, Any], target_ref: str) -> dict[str, Any]:
    for item in inputs["resolver"].get("reference_resolutions", []):
        if item.get("target_ref") == target_ref:
            return item
    return {}


def _top_action_refs(inputs: dict[str, Any]) -> list[str]:
    actions = inputs["wiki_index"].get("top_next_actions", [])
    return [str(item) for item in actions if item]


def build_scorecard(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    live = _live_bundle(inputs)
    capital = _capital_bundle(inputs)
    pdf = _nested(live, "invoice_artifact", "pdf_export_package", default={}) or {}
    service = inputs["service_supervision"]
    resolver = inputs["resolver"]
    sentinel = inputs["sentinel"]
    wiki = inputs["wiki_index"]

    scores = [
        {
            "category": "Workflow Design",
            "score": 4.0,
            "max_score": 5.0,
            "status": "STRONG_WITH_STALE_HANDOFFS",
            "rationale": "Live Arts and Capital Hilton have explicit rails, blockers, receipts, and safe actions, but Hermes/Chief still contains stale Live Arts candidate-selection blockers.",
            "source_refs": [
                _source_ref("generated/read_models/live_arts_md_invoice_review_bundle.json", "Selected invoice and PDF package rails."),
                _source_ref("generated/read_models/invoice_review_bundle.json", "Capital Hilton blocker and receipt rails."),
                _source_ref("generated/read_models/hermes_mission_sentinel.json", "Stale candidate blocker still present."),
            ],
        },
        {
            "category": "Data Access",
            "score": 3.5,
            "max_score": 5.0,
            "status": "GOOD_LOCAL_READ_MODELS_BRIDGE_PARTIAL",
            "rationale": "Registries, resolver, wiki, invoice bundles, and supervision read-models exist; bridge mirror and Mac-local paths remain unavailable or partial.",
            "source_refs": [
                _source_ref("generated/read_models/openclaw_reference_resolver.json", f"Resolver drift_count={resolver.get('drift_count', 'unknown')}."),
                _source_ref("generated/read_models/openclaw_context_wiki_index.json", f"Wiki pages={len(wiki.get('pages', []))}."),
            ],
        },
        {
            "category": "Authority",
            "score": 4.5,
            "max_score": 5.0,
            "status": "STRONG_DEFAULT_DENY",
            "rationale": "Business read-models and supervision carry no-live-action flags; Mac export package is scoped and no ledger/email/browser/workbook-cell authority is granted.",
            "source_refs": [
                _source_ref("generated/read_models/live_arts_md_invoice_review_bundle.json", f"Mac package no_email={pdf.get('no_email_send')} no_ledger={pdf.get('no_ledger_post')}."),
                _source_ref("generated/read_models/openclaw_service_supervision.json", f"Startup readiness={service.get('startup_readiness')}."),
            ],
        },
        {
            "category": "Evals",
            "score": 2.5,
            "max_score": 5.0,
            "status": "FOCUSED_TESTS_PRESENT_END_TO_END_GAPS",
            "rationale": "Registry and monitor tests exist, but business-object end-to-end evals for Mac helper, PDF result intake, attachment promotion, manual proof, payment watch, and Capital Hilton proof are still missing.",
            "source_refs": [
                _source_ref("tests/test_openclaw_context_wiki_compiler.py", "Wiki compiler tests exist."),
                _source_ref("tests/test_openclaw_service_supervision.py", "Service supervision tests exist."),
            ],
        },
        {
            "category": "Audit Trails & Recovery",
            "score": 4.0,
            "max_score": 5.0,
            "status": "GOOD_RECEIPTS_AND_MONITORS_STALE_VIEWS",
            "rationale": "Reference resolver, sentinel, service supervision, receipts, and invalid artifact guardrails are strong; stale Hermes/wiki claims and missing bridge mirror still need recovery paths.",
            "source_refs": [
                _source_ref("generated/read_models/openclaw_change_sentinel.json", f"Sentinel run_status={sentinel.get('run_status')}."),
                _source_ref("generated/read_models/live_arts_md_invoice_review_bundle.json", "Invalid PDF placeholders are explicitly not trusted."),
            ],
        },
        {
            "category": "Business Object Proximity",
            "score": 3.5,
            "max_score": 5.0,
            "status": "LIVE_ARTS_CLOSE_CAPITAL_HILTON_FARTHER",
            "rationale": "Live Arts has selected invoice and a scoped Mac PDF package ready, but attachment, recipient, approval, proof, payment, and ledger states remain gated; Capital Hilton is still selection/proof blocked.",
            "source_refs": [
                _source_ref("generated/read_models/live_arts_md_invoice_review_bundle.json", f"PDF package status={pdf.get('status')}."),
                _source_ref("generated/read_models/invoice_review_bundle.json", f"Capital Hilton status={capital.get('status')}."),
            ],
        },
    ]
    return scores


def build_business_object_inventory(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    live = _live_bundle(inputs)
    capital = _capital_bundle(inputs)
    pdf = _nested(live, "invoice_artifact", "pdf_export_package", default={}) or {}
    guardrails = _nested(live, "invoice_artifact", "known_artifact_guardrails", default={}) or {}
    service = inputs["service_supervision"]
    review_branch = _branch_ref(inputs, "openclaw_eyes_registry_review_branch")
    estate_mirror = _resolution(inputs, "estate_topology_registry_read_model_mirror")
    context_area = _truth_area(inputs, "evidence_grounded_context_registry")
    mac_edge = _truth_area(inputs, "mac_excel_edge_worker")
    access_broker = _truth_area(inputs, "access_broker")
    request_response = next(
        (
            row
            for row in service.get("supervised_units", [])
            if row.get("unit_name") == "openclaw-request-response.service"
        ),
        {},
    )

    inventory = [
        {
            "object_name": "Live Arts invoice",
            "implementation_status": "SELECTED_NOT_SEND_READY",
            "business_object_proximity": "HIGH",
            "current_fact": _nested(live, "candidate_selection_rail", "selected_invoice_summary", default=""),
            "blockers": [
                "attachment_ready=false",
                "recipient confirmation pending",
                "Guardian/operator approval missing",
                "send proof missing",
            ],
            "next_safe_action": "Finish artifact proof path before recipient/Guardian/send-readiness promotion.",
            "source_refs": [_source_ref("generated/read_models/live_arts_md_invoice_review_bundle.json")],
        },
        {
            "object_name": "Live Arts PDF artifact",
            "implementation_status": "PACKAGE_READY_EXPORT_NOT_CONFIRMED",
            "business_object_proximity": "HIGH",
            "current_fact": f"{pdf.get('status', 'UNKNOWN')} for invoice {pdf.get('invoice_id', '')}",
            "blockers": [
                "actual Mac export completion receipt missing",
                "attachment_ready=false",
                "operator review after export required",
            ],
            "next_safe_action": "Resolve Mac helper/permission path, then ingest selected_invoice_pdf_export_completed_candidate.",
            "source_refs": [_source_ref("generated/read_models/live_arts_md_invoice_review_bundle.json", "pdf_export_package")],
        },
        {
            "object_name": "Live Arts payment watch",
            "implementation_status": _nested(live, "payment_watch", "payment_watch_status", default="UNKNOWN"),
            "business_object_proximity": "MEDIUM",
            "current_fact": f"ledger_match={_nested(live, 'payment_watch', 'ledger_match_status', default='UNKNOWN')}; bank_read={_nested(live, 'payment_watch', 'bank_ledger_read_performed', default='UNKNOWN')}",
            "blockers": ["manual send proof missing", "bank/payment confirmation missing", "ledger posting disallowed"],
            "next_safe_action": "Keep readiness-only until manual/send proof exists.",
            "source_refs": [_source_ref("generated/read_models/live_arts_md_invoice_review_bundle.json", "payment_watch")],
        },
        {
            "object_name": "Capital Hilton invoice",
            "implementation_status": capital.get("status", "UNKNOWN"),
            "business_object_proximity": "MEDIUM_LOW",
            "current_fact": _nested(capital, "invoice_selection", "operator_question", default=""),
            "blockers": capital.get("missing_receipts", [])[:8],
            "next_safe_action": "Confirm invoice record/period and Coupa proof before attachment or send readiness.",
            "source_refs": [_source_ref("generated/read_models/invoice_review_bundle.json")],
        },
        {
            "object_name": "Clara draft",
            "implementation_status": _nested(live, "clara_invoice_email_draft_package", "draft_status", default="UNKNOWN"),
            "business_object_proximity": "MEDIUM",
            "current_fact": "Live Arts and Capital Hilton drafts are draft-only / not send-ready.",
            "blockers": _nested(live, "clara_invoice_email_draft_package", "missing_prerequisites", default=[]),
            "next_safe_action": "Promote only after attachment, recipient, draft receipt, Guardian/operator approvals.",
            "source_refs": [
                _source_ref("generated/read_models/live_arts_md_invoice_review_bundle.json", "clara draft"),
                _source_ref("generated/read_models/invoice_review_bundle.json", "Capital Hilton clara draft"),
            ],
        },
        {
            "object_name": "client comms thread",
            "implementation_status": _nested(live, "client_comms_thread", "thread_watch_status", default="UNKNOWN"),
            "business_object_proximity": "MEDIUM",
            "current_fact": _nested(live, "client_comms_thread", "thread_ref", default=""),
            "blockers": ["thread watch blocked until sent receipt", "no Gmail draft/send performed"],
            "next_safe_action": "Keep thread watch future-gated until send receipt exists.",
            "source_refs": [_source_ref("generated/read_models/live_arts_md_invoice_review_bundle.json", "client_comms_thread")],
        },
        {
            "object_name": "Guardian approval",
            "implementation_status": _nested(capital, "guardian_approval_request", "status", default=_nested(live, "client_comms_thread", "guardian_approval_request_status", default="NOT_CREATED")),
            "business_object_proximity": "MEDIUM",
            "current_fact": "Guardian approval is required and not a send authority by itself.",
            "blockers": ["attachment readiness", "recipient confirmation", "operator approval/send receipts"],
            "next_safe_action": "Create request only after prerequisites are true.",
            "source_refs": [
                _source_ref("generated/read_models/live_arts_md_invoice_review_bundle.json"),
                _source_ref("generated/read_models/invoice_review_bundle.json"),
            ],
        },
        {
            "object_name": "Mac edge job package",
            "implementation_status": pdf.get("status", "UNKNOWN"),
            "business_object_proximity": "HIGH",
            "current_fact": f"execution_venue={pdf.get('execution_venue')}; required_capability={pdf.get('required_capability')}; no_workbook_cell_read={pdf.get('no_workbook_cell_read')}",
            "blockers": ["Mac export not completed", "result receipt missing", "helper/permission architecture unresolved"],
            "next_safe_action": "Mac emits scoped result only after local helper succeeds.",
            "source_refs": [_source_ref("generated/read_models/live_arts_md_invoice_review_bundle.json", "Mac edge job package")],
        },
        {
            "object_name": "Mac Excel helper/proposed helper",
            "implementation_status": "HELPER_ARCHITECTURE_RECOMMENDED",
            "business_object_proximity": "MEDIUM",
            "current_fact": mac_edge.get("ownership_rule", "Mac-local helper belongs with Mac app/helper architecture."),
            "blockers": ["in-app Excel Automation blocked", "file/folder and Apple Events permission shape unresolved"],
            "next_safe_action": "Implement/verify helper architecture on Mac; PC only emits packages.",
            "source_refs": [_source_ref("generated/read_models/openclaw_estate_topology_registry.json", "mac_excel_edge_worker")],
        },
        {
            "object_name": "Access Broker",
            "implementation_status": access_broker.get("status", "PARTIAL"),
            "business_object_proximity": "MEDIUM",
            "current_fact": access_broker.get("ownership_rule", ""),
            "blockers": ["split Mac UI/backend policy not fully implemented", "Mac permission failures still modeled as partial"],
            "next_safe_action": "Define helper permission repair path without collapsing ownership boundaries.",
            "source_refs": [_source_ref("generated/read_models/openclaw_estate_topology_registry.json", "access_broker")],
        },
        {
            "object_name": "service supervision",
            "implementation_status": service.get("startup_readiness", "UNKNOWN"),
            "business_object_proximity": "INFRA_HIGH",
            "current_fact": f"request-response={request_response.get('active_state')}/{request_response.get('sub_state')}; watch={request_response.get('timer_settings', {}).get('ExecStart', '')}",
            "blockers": service.get("core_monitor_status", {}).get("unresolved_supervision_risks", []),
            "next_safe_action": "Keep observing; keeper may start inactive allowlisted units only.",
            "source_refs": [_source_ref("generated/read_models/openclaw_service_supervision.json")],
        },
        {
            "object_name": "reference resolver",
            "implementation_status": review_branch.get("resolution_status", "UNKNOWN"),
            "business_object_proximity": "INFRA_HIGH",
            "current_fact": f"review branch remote={review_branch.get('remote_status')}; local={review_branch.get('local_status')}; mac={review_branch.get('mac_mirror_status')}",
            "blockers": ["Mac local path unreachable from PC", f"estate mirror={estate_mirror.get('resolved_status', 'UNKNOWN')}"],
            "next_safe_action": "Use resolver output for volatile refs; do not copy branch heads into source truth.",
            "source_refs": [_source_ref("generated/read_models/openclaw_reference_resolver.json")],
        },
        {
            "object_name": "change sentinel",
            "implementation_status": inputs["sentinel"].get("run_status", "UNKNOWN"),
            "business_object_proximity": "INFRA_MEDIUM",
            "current_fact": f"material_changes={inputs['sentinel'].get('material_change_count')}; timer observed={service.get('core_monitor_status', {}).get('sentinel_timer_active')}",
            "blockers": [],
            "next_safe_action": "Observe only; do not make sentinel start services directly.",
            "source_refs": [
                _source_ref("generated/read_models/openclaw_change_sentinel.json"),
                _source_ref("generated/read_models/openclaw_service_supervision.json"),
            ],
        },
        {
            "object_name": "estate topology registry",
            "implementation_status": "PRESENT_WITH_CANONICALITY_CONFLICT",
            "business_object_proximity": "INFRA_HIGH",
            "current_fact": f"machines={inputs['estate'].get('machine_count')}; working_copies={inputs['estate'].get('repo_working_copy_count')}; context_registry_area={context_area.get('current_state', '')}",
            "blockers": ["openclaw-eyes registry branch canonicality must be corrected to pending review unless merge evidence is explicit", "bridge mirror missing"],
            "next_safe_action": "Refresh topology to keep review branch as PENDING_REVIEW until canonical merge is proven.",
            "source_refs": [_source_ref("generated/read_models/openclaw_estate_topology_registry.json")],
        },
        {
            "object_name": "context wiki",
            "implementation_status": "PRESENT_GENERATED_VIEW",
            "business_object_proximity": "INFRA_MEDIUM",
            "current_fact": f"pages={len(inputs['wiki_pages'])}; contradictions={inputs['wiki_index'].get('contradiction_count')}",
            "blockers": inputs["wiki_index"].get("missing_inputs", []),
            "next_safe_action": "Fix upstream registries/read-models, then regenerate; do not edit wiki as source truth.",
            "source_refs": [
                _source_ref("generated/read_models/openclaw_context_wiki_index.json"),
                _source_ref("generated/wiki/openclaw/"),
            ],
        },
        {
            "object_name": "openclaw-eyes registry branch",
            "implementation_status": "PRESENT_ON_REVIEW_BRANCH_PENDING_REVIEW",
            "business_object_proximity": "INFRA_HIGH",
            "current_fact": f"branch={review_branch.get('branch')}; remote_status={review_branch.get('remote_status')}; head={review_branch.get('current_head_commit')}",
            "blockers": ["current estate/wiki generated state also claims CANONICAL_ON_MAIN; audit treats that as stale/conflicting until canonical merge is confirmed"],
            "next_safe_action": "Keep source truth as repo/branch ref and generated current_head_commit only.",
            "source_refs": [
                _source_ref("generated/read_models/openclaw_reference_resolver.json"),
                _source_ref("generated/read_models/openclaw_estate_topology_registry.json"),
            ],
        },
    ]
    return inventory


def build_stale_claim_corrections(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    live = _live_bundle(inputs)
    pdf = _nested(live, "invoice_artifact", "pdf_export_package", default={}) or {}
    service = inputs["service_supervision"]
    hermes = inputs["hermes"].get("hermes_mission_sentinel.json", {})
    corrections = [
        {
            "claim_ref": "live_arts_candidate_unselected",
            "stale_or_conflicting_claim": "Hermes/Chief still says the Live Arts invoice candidate is not selected.",
            "corrected_current_claim": _nested(live, "candidate_selection_rail", "selected_invoice_summary", default="Live Arts selection is confirmed."),
            "correction_status": "CORRECTED_IN_AUDIT_SOURCE_STILL_STALE",
            "source_refs": [
                _source_ref("generated/read_models/live_arts_md_invoice_review_bundle.json"),
                _source_ref("generated/read_models/hermes_mission_sentinel.json", f"current_blockers={hermes.get('current_blockers', [])}"),
            ],
        },
        {
            "claim_ref": "pdf_package_missing_fields",
            "stale_or_conflicting_claim": "Wiki contradiction says the PDF export package is missing invoice_id, selected_sheet_label, and output_bridge_path.",
            "corrected_current_claim": f"pdf_export_package has invoice_id={pdf.get('invoice_id')}, selected_sheet_label={pdf.get('selected_sheet_label')}, output_bridge_path={pdf.get('output_bridge_path')}.",
            "correction_status": "CORRECTED_IN_AUDIT_SOURCE_STILL_STALE",
            "source_refs": [_source_ref("generated/read_models/live_arts_md_invoice_review_bundle.json", "invoice_artifact.pdf_export_package")],
        },
        {
            "claim_ref": "openclaw_eyes_registry_canonical_main",
            "stale_or_conflicting_claim": "Current estate/wiki generated state claims the system knowledge registry is canonical on openclaw-eyes main.",
            "corrected_current_claim": "Treat openclaw-eyes system knowledge registry as PRESENT_ON_REVIEW_BRANCH / PENDING_REVIEW until merge/canonical evidence is deliberately recorded.",
            "correction_status": "CONFLICT_RECORDED_UPSTREAM_REFRESH_REQUIRED",
            "source_refs": [
                _source_ref("generated/read_models/openclaw_estate_topology_registry.json"),
                _source_ref("generated/read_models/openclaw_reference_resolver.json"),
            ],
        },
        {
            "claim_ref": "request_response_unstable",
            "stale_or_conflicting_claim": "Request-response service restart churn is still the current blocker.",
            "corrected_current_claim": f"Service supervision reports READY and request-response ExecStart includes --watch-seconds 21600; core status={service.get('core_monitor_status', {})}.",
            "correction_status": "CORRECTED",
            "source_refs": [_source_ref("generated/read_models/openclaw_service_supervision.json")],
        },
        {
            "claim_ref": "mac_export_completed",
            "stale_or_conflicting_claim": "A ready Mac package or existing desktop PDF is proof of completed selected-invoice export.",
            "corrected_current_claim": "Live Arts backend PDF package is ready, but actual Mac export completion and selected artifact attachment are not confirmed.",
            "correction_status": "CORRECTED",
            "source_refs": [_source_ref("generated/read_models/live_arts_md_invoice_review_bundle.json")],
        },
        {
            "claim_ref": "ledger_ready",
            "stale_or_conflicting_claim": "Ledger posting can proceed after invoice package readiness.",
            "corrected_current_claim": "Ledger posting remains blocked/disallowed until send proof, payment confirmation, and explicit ledger receipts exist.",
            "correction_status": "CORRECTED",
            "source_refs": [_source_ref("generated/read_models/live_arts_md_invoice_review_bundle.json", "payment_watch")],
        },
    ]
    return corrections


def build_top_gaps(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    gaps = [
        ("mac_helper_permission_architecture", "Mac Excel helper / Access Broker permission path is unresolved; in-app Excel automation is blocked.", "HIGH", "MAC_APP", "Now"),
        ("live_arts_pdf_export_completion", "Live Arts PDF package is ready, but selected_invoice_pdf_export_completed_candidate is missing.", "HIGH", "MAC_APP+PC_BACKEND", "Now"),
        ("live_arts_attachment_ready", "Live Arts attachment_ready remains false until valid export and operator review receipts exist.", "HIGH", "PC_BACKEND", "Now"),
        ("live_arts_manual_send_proof", "Manual send metadata exists, but proof screenshot/ref is missing and file-backed proof is false.", "HIGH", "OPERATOR_PROOF", "Next"),
        ("live_arts_recipient_confirmation", "Dane/Draper/Earnie email details are not confirmed; Winship copy is known only.", "HIGH", "PC_BACKEND", "Next"),
        ("guardian_approval_not_created", "Guardian approval request is required but not created/ready for Live Arts.", "HIGH", "PC_BACKEND", "Next"),
        ("clara_final_draft_blocked", "Clara drafts are preview/draft-only and not send-ready.", "MEDIUM", "PC_BACKEND", "Next"),
        ("payment_watch_readiness_only", "Payment watch is readiness-only until send/manual-send proof exists; no bank read or ledger match has run.", "MEDIUM", "PC_BACKEND", "Next"),
        ("ledger_posting_blocked", "Ledger posting remains explicitly disallowed and must stay parked until proof chain exists.", "HIGH", "LEDGER", "Parked"),
        ("hermes_handoff_stale", "Hermes/Chief still list invoice candidate selection as blocking despite Live Arts confirmed selection.", "MEDIUM", "PC_BACKEND", "Now"),
        ("openclaw_eyes_registry_branch_conflict", "Topology/wiki claim canonical-on-main while current target posture is review branch pending review.", "MEDIUM", "PC_BACKEND", "Now"),
        ("estate_bridge_mirror_missing", "Reference resolver marks estate topology read-model bridge mirror as MISSING.", "MEDIUM", "BRIDGE_TRANSPORT", "Next"),
        ("context_wiki_missing_system_registry", "Context wiki reports missing generated/system_knowledge/openclaw_system_knowledge_registry.* input.", "MEDIUM", "PC_BACKEND", "Later"),
        ("capital_hilton_selection_and_coupa", "Capital Hilton still needs invoice record/period selection, Coupa proof, recipients, and artifact linkage.", "MEDIUM", "PC_BACKEND", "Later"),
        ("business_object_evals_missing", "End-to-end business-object evals are missing for Mac helper, result intake, attachment promotion, proof, payment, and Capital Hilton.", "HIGH", "PC_BACKEND", "Now"),
    ]
    return [
        {
            "rank": index,
            "gap_ref": gap_ref,
            "gap": gap,
            "severity": severity,
            "owner_hint": owner,
            "build_bucket": bucket,
        }
        for index, (gap_ref, gap, severity, owner, bucket) in enumerate(gaps, start=1)
    ]


def build_build_order(inputs: dict[str, Any], gaps: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    return {
        "now": [
            {"task": "Reconcile stale Hermes/Chief Live Arts blockers against the confirmed 2026-1001 bundle state.", "reason": "Avoid sending Chief after already-solved candidate selection work."},
            {"task": "Correct openclaw-eyes registry branch canonicality back to review-branch pending review unless merge evidence is explicit.", "reason": "Stop source-truth drift in topology/wiki outputs."},
            {"task": "Build or verify Mac helper/Access Broker permission path for scoped Excel PDF export.", "reason": "This is the current blocker before Live Arts PDF export retry."},
            {"task": "Add end-to-end evals for Mac result intake and attachment promotion without executing Excel/PDF.", "reason": "The backend needs proof that selected_invoice_pdf_export_completed_candidate promotes safely."},
        ],
        "next": [
            {"task": "After Mac export succeeds, ingest result candidate and keep artifact OPERATOR_REVIEW_REQUIRED until reviewed.", "reason": "Attachment readiness must remain receipt-gated."},
            {"task": "Confirm Live Arts recipients and Guardian/operator approval gates.", "reason": "Clara/send readiness is blocked by recipient and approval receipts."},
            {"task": "Capture manual-send proof if manual send already happened, then activate payment watch readiness only.", "reason": "Payment watch cannot become real until send proof exists."},
            {"task": "Repair estate topology bridge mirror and Mac bridge permission representation.", "reason": "Resolver reports missing bridge mirror and Mac bridge unavailable."},
        ],
        "later": [
            {"task": "Refresh/install canonical system knowledge registry inputs for the context wiki.", "reason": "Wiki reports the system knowledge registry input missing."},
            {"task": "Advance Capital Hilton invoice selection/Coupa proof/artifact linkage rails.", "reason": "Capital Hilton remains farther from business-object execution than Live Arts."},
            {"task": "Decide Mac app remote/backup strategy and runtime actor canonical home.", "reason": "Topology known unknowns still affect repo ownership."},
        ],
        "parked": [
            {"task": "Ledger posting automation.", "reason": "Explicitly blocked until sent/payment/ledger receipts exist."},
            {"task": "Live email/Gmail/browser/Coupa execution.", "reason": "Outside this audit and still receipt/authority gated."},
            {"task": "Broad LM summarization or Chief launch.", "reason": "This audit is deterministic and read-only."},
        ],
    }


def build_missing_evals() -> list[dict[str, str]]:
    evals = [
        ("mac_pdf_helper_no_cell_read_eval", "Mock Mac helper package proves no workbook cell read, no workbook mutation, scoped output only."),
        ("selected_pdf_result_intake_eval", "Synthetic selected_invoice_pdf_export_completed_candidate promotes a candidate artifact without marking attachment_ready prematurely."),
        ("invalid_pdf_guardrail_eval", "7-page desktop PDF and 14-byte bridge placeholder never become selected invoice proof."),
        ("manual_send_proof_promotion_eval", "Manual-send proof receipt moves proof state without claiming OpenClaw sent email."),
        ("payment_watch_activation_eval", "Payment watch stays readiness-only until send/manual-send proof exists."),
        ("recipient_guardian_clara_gate_eval", "Recipient confirmation and Guardian approval are required before Clara final draft/send readiness."),
        ("capital_hilton_selection_coupa_eval", "Capital Hilton invoice period/Coupa proof/artifact linkage receipt flow blocks approval until complete."),
        ("hermes_stale_blocker_regression_eval", "Hermes/Chief handoff cannot keep obsolete candidate-selection blockers after bundle selection is confirmed."),
        ("registry_canonicality_eval", "Topology registry cannot mark review branch canonical on main without explicit merge/canonical evidence."),
        ("service_supervision_reboot_smoke", "Reboot/linger/timer behavior verified in a controlled reboot smoke, not only live status."),
    ]
    return [
        {"eval_ref": ref, "missing_eval": text, "status": "MISSING"}
        for ref, text in evals
    ]


def build_hermes_chief_implications(inputs: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "implication_ref": "do_not_launch_chief_from_audit",
            "summary": "Chief must not be launched by this audit; any Chief work should be a bounded build task with tests only.",
            "source_ref": "Boundary for this task",
        },
        {
            "implication_ref": "drop_stale_candidate_selection_task",
            "summary": "Hermes/Chief should stop treating Live Arts invoice candidate selection as unresolved; 2026-1001 is confirmed in the bundle.",
            "source_ref": "generated/read_models/live_arts_md_invoice_review_bundle.json",
        },
        {
            "implication_ref": "prioritize_mac_helper_and_result_intake",
            "summary": "The next real build pressure is Mac helper/permission architecture plus backend result intake/attachment promotion, not invoice selection.",
            "source_ref": "generated/read_models/live_arts_md_invoice_review_bundle.json",
        },
        {
            "implication_ref": "keep_business_execution_blocked",
            "summary": "Hermes may summarize and Chief may build tests/code, but no email, PDF export, Coupa, workbook, ledger, or production action is authorized here.",
            "source_ref": "generated/read_models/purpose_bound_automation_charter.json",
        },
    ]


def _prior_audit_paths(read_model_root: str | Path) -> list[str]:
    root = _rooted(read_model_root)
    paths = sorted(glob.glob(str(root / "*business*object*audit*.json")))
    return [_display_path(path) for path in paths if not path.endswith(JSON_EXPORT_NAME)]


def build_openclaw_business_object_layer_audit(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    wiki_root: str | Path = DEFAULT_WIKI_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    inputs = collect_inputs(read_model_root=read_model_root, wiki_root=wiki_root)
    scorecard = build_scorecard(inputs)
    inventory = build_business_object_inventory(inputs)
    corrections = build_stale_claim_corrections(inputs)
    gaps = build_top_gaps(inputs)
    build_order = build_build_order(inputs, gaps)
    missing_evals = build_missing_evals()
    hermes_implications = build_hermes_chief_implications(inputs)
    overall = round(sum(row["score"] for row in scorecard) / len(scorecard), 2)
    readiness = "READY_FOR_BUILD_PLANNING_NOT_EXECUTION"
    return {
        "schema_version": READ_MODEL_VERSION,
        "contract_schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated,
        "purpose": "Refresh the business-object implementation layer audit from current registries/read-models without live actions.",
        "source_truth_policy": {
            "prior_audit_used_as_source_truth": False,
            "prior_audit_paths_compared": _prior_audit_paths(read_model_root),
            "current_registries_and_read_models_are_inputs": True,
            "generated_wiki_is_view_only": True,
        },
        "readiness": readiness,
        "overall_score": overall,
        "scorecard": scorecard,
        "business_objects": inventory,
        "business_object_names_required": list(BUSINESS_OBJECT_NAMES),
        "stale_claims_corrected": corrections,
        "top_gaps": gaps,
        "build_order": build_order,
        "missing_evals": missing_evals,
        "hermes_chief_implications": hermes_implications,
        "input_sources": {
            "read_models": [
                "generated/read_models/openclaw_estate_topology_registry.json",
                "generated/read_models/openclaw_reference_resolver.json",
                "generated/read_models/openclaw_change_sentinel.json",
                "generated/read_models/openclaw_context_wiki_index.json",
                "generated/read_models/live_arts_md_invoice_review_bundle.json",
                "generated/read_models/invoice_review_bundle.json",
                "generated/read_models/purpose_bound_automation_charter.json",
                "generated/read_models/openclaw_service_supervision.json",
                *[f"generated/read_models/{name}" for name in sorted(inputs["hermes"].keys())],
            ],
            "wiki_pages": inputs["wiki_pages"],
            "source_evidence": inputs["source_evidence"],
        },
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def sqlite_schema_sql() -> str:
    return """CREATE TABLE audit_run (
    run_ref TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    readiness TEXT NOT NULL,
    overall_score REAL NOT NULL,
    business_object_count INTEGER NOT NULL,
    gap_count INTEGER NOT NULL,
    missing_eval_count INTEGER NOT NULL
);

CREATE TABLE scorecard (
    category TEXT PRIMARY KEY,
    score REAL NOT NULL,
    max_score REAL NOT NULL,
    status TEXT NOT NULL,
    rationale TEXT NOT NULL,
    source_refs_json TEXT NOT NULL
);

CREATE TABLE business_object (
    object_name TEXT PRIMARY KEY,
    implementation_status TEXT NOT NULL,
    business_object_proximity TEXT NOT NULL,
    current_fact TEXT NOT NULL,
    blockers_json TEXT NOT NULL,
    next_safe_action TEXT NOT NULL,
    source_refs_json TEXT NOT NULL
);

CREATE TABLE stale_claim_correction (
    claim_ref TEXT PRIMARY KEY,
    stale_or_conflicting_claim TEXT NOT NULL,
    corrected_current_claim TEXT NOT NULL,
    correction_status TEXT NOT NULL,
    source_refs_json TEXT NOT NULL
);

CREATE TABLE top_gap (
    rank INTEGER PRIMARY KEY,
    gap_ref TEXT NOT NULL,
    gap TEXT NOT NULL,
    severity TEXT NOT NULL,
    owner_hint TEXT NOT NULL,
    build_bucket TEXT NOT NULL
);

CREATE TABLE build_order (
    bucket TEXT NOT NULL,
    rank INTEGER NOT NULL,
    task TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (bucket, rank)
);

CREATE TABLE missing_eval (
    eval_ref TEXT PRIMARY KEY,
    missing_eval TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE hermes_chief_implication (
    implication_ref TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    source_ref TEXT NOT NULL
);
"""


def _write_sqlite(path: str | Path, payload: dict[str, Any]) -> None:
    sqlite_path = Path(path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    if sqlite_path.exists():
        sqlite_path.unlink()
    connection = sqlite3.connect(sqlite_path)
    try:
        connection.executescript(sqlite_schema_sql())
        connection.execute(
            "INSERT INTO audit_run VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "openclaw_business_object_layer_audit_run",
                payload["generated_at"],
                payload["readiness"],
                payload["overall_score"],
                len(payload["business_objects"]),
                len(payload["top_gaps"]),
                len(payload["missing_evals"]),
            ),
        )
        for row in payload["scorecard"]:
            connection.execute(
                "INSERT INTO scorecard VALUES (?, ?, ?, ?, ?, ?)",
                (
                    row["category"],
                    row["score"],
                    row["max_score"],
                    row["status"],
                    row["rationale"],
                    stable_json(row["source_refs"]).strip(),
                ),
            )
        for row in payload["business_objects"]:
            connection.execute(
                "INSERT INTO business_object VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    row["object_name"],
                    row["implementation_status"],
                    row["business_object_proximity"],
                    str(row["current_fact"]),
                    stable_json(row["blockers"]).strip(),
                    row["next_safe_action"],
                    stable_json(row["source_refs"]).strip(),
                ),
            )
        for row in payload["stale_claims_corrected"]:
            connection.execute(
                "INSERT INTO stale_claim_correction VALUES (?, ?, ?, ?, ?)",
                (
                    row["claim_ref"],
                    row["stale_or_conflicting_claim"],
                    row["corrected_current_claim"],
                    row["correction_status"],
                    stable_json(row["source_refs"]).strip(),
                ),
            )
        for row in payload["top_gaps"]:
            connection.execute(
                "INSERT INTO top_gap VALUES (?, ?, ?, ?, ?, ?)",
                (
                    row["rank"],
                    row["gap_ref"],
                    row["gap"],
                    row["severity"],
                    row["owner_hint"],
                    row["build_bucket"],
                ),
            )
        for bucket, rows in payload["build_order"].items():
            for rank, row in enumerate(rows, start=1):
                connection.execute(
                    "INSERT INTO build_order VALUES (?, ?, ?, ?)",
                    (bucket, rank, row["task"], row["reason"]),
                )
        for row in payload["missing_evals"]:
            connection.execute(
                "INSERT INTO missing_eval VALUES (?, ?, ?)",
                (row["eval_ref"], row["missing_eval"], row["status"]),
            )
        for row in payload["hermes_chief_implications"]:
            connection.execute(
                "INSERT INTO hermes_chief_implication VALUES (?, ?, ?)",
                (row["implication_ref"], row["summary"], row["source_ref"]),
            )
        connection.commit()
    finally:
        connection.close()


def render_operator_summary(payload: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw Business-Object Layer Audit",
        "",
        f"- Readiness: {payload['readiness']}",
        f"- Overall score: {payload['overall_score']} / 5.0",
        f"- Business objects: {len(payload['business_objects'])}",
        f"- Top gaps: {len(payload['top_gaps'])}",
        "",
        "## Scores",
    ]
    for row in payload["scorecard"]:
        lines.append(f"- {row['category']}: {row['score']} / {row['max_score']} ({row['status']})")
    lines.extend(["", "## Stale Claims Corrected"])
    for row in payload["stale_claims_corrected"]:
        lines.append(f"- {row['claim_ref']}: {row['corrected_current_claim']}")
    lines.extend(["", "## Top Gaps"])
    for row in payload["top_gaps"][:15]:
        lines.append(f"- {row['rank']}. {row['gap_ref']}: {row['gap']}")
    lines.extend(["", "## Build Order"])
    for bucket in ("now", "next", "later", "parked"):
        lines.append(f"### {bucket}")
        for item in payload["build_order"][bucket]:
            lines.append(f"- {item['task']}")
    lines.extend(["", "Boundary: deterministic read-model audit only; no live business action performed."])
    return "\n".join(lines) + "\n"


def export_openclaw_business_object_layer_audit(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    system_knowledge_root: str | Path = DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
    wiki_root: str | Path = DEFAULT_WIKI_ROOT,
    generated_at: str | None = None,
) -> BusinessObjectLayerAuditExportResult:
    read_root = _rooted(read_model_root)
    system_root = _rooted(system_knowledge_root)
    read_root.mkdir(parents=True, exist_ok=True)
    system_root.mkdir(parents=True, exist_ok=True)
    payload = build_openclaw_business_object_layer_audit(
        read_model_root=read_root,
        wiki_root=wiki_root,
        generated_at=generated_at,
    )
    json_path = read_root / JSON_EXPORT_NAME
    operator_path = read_root / OPERATOR_EXPORT_NAME
    sqlite_path = system_root / SQLITE_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(render_operator_summary(payload), encoding="utf-8")
    _write_sqlite(sqlite_path, payload)
    return BusinessObjectLayerAuditExportResult(
        schema_version=READ_MODEL_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        sqlite_path=_display_path(sqlite_path),
        score_count=len(payload["scorecard"]),
        business_object_count=len(payload["business_objects"]),
        gap_count=len(payload["top_gaps"]),
        missing_eval_count=len(payload["missing_evals"]),
        readiness=payload["readiness"],
    )


def _print_result(result: BusinessObjectLayerAuditExportResult, fmt: str, read_model_root: str | Path) -> None:
    if fmt == "json":
        payload = json.loads((_rooted(read_model_root) / JSON_EXPORT_NAME).read_text(encoding="utf-8"))
        print(stable_json(payload), end="")
    elif fmt == "operator":
        print((_rooted(read_model_root) / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    else:
        print(
            "OpenClaw business-object layer audit: "
            f"{result.readiness}; score_count={result.score_count}; "
            f"objects={result.business_object_count}; gaps={result.gap_count}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--system-knowledge-root", default=str(DEFAULT_SYSTEM_KNOWLEDGE_ROOT))
    parser.add_argument("--wiki-root", default=str(DEFAULT_WIKI_ROOT))
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    args = parser.parse_args(argv)
    result = export_openclaw_business_object_layer_audit(
        read_model_root=args.read_model_root,
        system_knowledge_root=args.system_knowledge_root,
        wiki_root=args.wiki_root,
        generated_at=args.generated_at,
    )
    _print_result(result, args.format, args.read_model_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
