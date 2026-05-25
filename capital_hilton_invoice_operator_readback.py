"""Capital Hilton Invoice Operator Readback Aggregator v0.

This deterministic read-model rolls the Capital Hilton invoice workflow rails
into one operator-facing status. It summarizes existing package, draft,
submit, dry-run, completion, file-source, secret, and approval rails.

It does not execute workflows, send email, access Mail/Gmail, access Coupa,
open browsers, reveal secrets, execute approvals, write payment tracking,
write completion state, perform external actions, ingest raw bodies, mutate
Mission Control Swift, run Mac sync/import, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-25T00:00:00+00:00"

SCHEMA_VERSION = "capital_hilton_invoice_operator_readback_v0"
READ_MODEL_ID = "capital_hilton_invoice_operator_readback"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_CAPITAL_HILTON_OPERATOR_READBACK_NO_EXECUTION"

WORKFLOW_REF = "capital_hilton_invoice_workflow"
CLIENT_REF = "client_ref:capital_hilton"
TENANT_REF = "tenant_ref:winship"

RAIL_NAMES = (
    "DELIVERY_FACTS",
    "INVOICE_ARTIFACT",
    "EMAIL_DRAFT",
    "EMAIL_SEND",
    "COUPA_PACKAGE",
    "COUPA_SUBMIT",
    "RUN_PACKAGE",
    "DRY_RUN",
    "COMPLETION_PROOF",
    "GUARDIAN_APPROVAL",
    "SECRET_REF",
    "FILE_SOURCE_REFS",
)

BLOCKER_TYPES = (
    "COMPLETION_CLAIM_WITHOUT_PROOF",
    "SEND_READY_WITHOUT_APPROVAL",
    "COUPA_READY_WITHOUT_APPROVAL",
    "RUN_READY_WITHOUT_EXECUTION_GATE",
    "MISSING_REQUIRED_RAIL",
    "STALE_READMODEL",
    "CONTRADICTORY_RAIL_STATUS",
    "RAW_PRIVATE_BODY_EXPOSED",
    "EXTERNAL_ACTION_ATTEMPTED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_workflow_run_allowed": False,
    "live_email_send_allowed": False,
    "live_mail_send_allowed": False,
    "live_gmail_send_allowed": False,
    "live_coupa_access_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_browser_allowed": False,
    "live_secret_reveal_allowed": False,
    "live_approval_execution_allowed": False,
    "live_payment_tracking_write_allowed": False,
    "live_completion_write_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_provider_call_allowed": False,
    "live_file_mutation_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

SOURCE_READMODEL_FILES = {
    "DELIVERY_FACTS": "workflow_execution_package_compiler.json",
    "INVOICE_ARTIFACT": "invoice_artifact_readback.json",
    "EMAIL_DRAFT": "gated_email_draft_adapter.json",
    "EMAIL_SEND": "gated_email_send_adapter.json",
    "COUPA_PACKAGE": "coupa_supplier_portal_package_compiler.json",
    "COUPA_SUBMIT": "gated_coupa_submit_adapter.json",
    "RUN_PACKAGE": "invoice_delivery_run_package_assembler.json",
    "DRY_RUN": "invoice_delivery_dry_run_harness.json",
    "COMPLETION_PROOF": "invoice_delivery_completion_proof_aggregator.json",
    "GUARDIAN_APPROVAL": "guardian_approval_request_wrapper.json",
    "SECRET_REF": "protected_secret_intake_contract.json",
    "FILE_SOURCE_REFS": "operator_file_metadata_readback.json",
}

CURRENT_MISSING_ITEMS = (
    "confirmed Coupa PO/reference",
    "protected Coupa credential ref for any future portal login",
    "Guardian and exact operator approval receipts for send and submit",
    "future email send receipt and attachment proof",
    "future Coupa submit receipt and confirmation proof",
    "future payment tracking or local completion receipt if required",
    "future gated provider adapters before execution",
)

CURRENT_BLOCKED_ITEMS = (
    "email send",
    "Mail/Gmail send",
    "Coupa access and submit",
    "browser automation",
    "workflow run",
    "approval execution",
    "payment tracking write",
    "completion claim",
    "external action",
)

CURRENT_READY_ITEMS = (
    "delivery basis is modeled for four Capital Hilton performance dates at $400/show",
    "bounded invoice artifact and hash refs are available when the artifact builder readback is current",
    "local email draft artifact is available for review when the draft adapter readback is current",
    "file source refs and package rails are available for review",
)


@dataclass(frozen=True)
class CapitalHiltonInvoiceOperatorReadbackAggregator:
    aggregator_id: str
    doctrine: tuple[str, ...]
    source_readmodels: tuple[str, ...]
    status_policy: tuple[str, ...]
    readiness_policy: tuple[str, ...]
    proof_policy: tuple[str, ...]
    operator_message_policy: tuple[str, ...]
    mac_chat_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonInvoiceUnifiedStatus:
    status_id: str
    workflow_ref: str
    client_ref: str
    tenant_ref: str
    headline: str
    plain_status: str
    ready_items: tuple[str, ...]
    missing_items: tuple[str, ...]
    blocked_items: tuple[str, ...]
    proof_items: tuple[str, ...]
    package_items: tuple[str, ...]
    next_safe_move: str
    can_mark_invoice_sent: bool
    can_send_email: bool
    can_submit_coupa: bool
    can_run_workflow: bool
    completion_label_status: str


@dataclass(frozen=True)
class InvoiceWorkflowRailSummary:
    rail_id: str
    rail_name: str
    source_readmodel_ref: str
    rail_status: str
    ready: bool
    missing: tuple[str, ...]
    blocked: tuple[str, ...]
    proof_status: str
    how_to_fix: str
    next_safe_move: str


@dataclass(frozen=True)
class OperatorChatResponse:
    response_id: str
    source_status_ref: str
    operator_headline: str
    operator_message: str
    concise_summary: str
    what_is_ready: tuple[str, ...]
    what_is_missing: tuple[str, ...]
    what_is_blocked: tuple[str, ...]
    how_to_fix: str
    next_safe_move: str
    detail_refs: tuple[str, ...]
    mac_chat_render_hint: str


@dataclass(frozen=True)
class InvoiceStatusBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:16]}"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def _source_ref(readmodel_root: Path, rail_name: str) -> str:
    filename = SOURCE_READMODEL_FILES[rail_name]
    path = readmodel_root / filename
    return str(path) if path.exists() else f"missing:{path}"


def _nested_get(payload: dict[str, Any] | None, *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def _example_get(payload: dict[str, Any] | None, example: str, section: str, field: str) -> Any:
    return _nested_get(payload, "examples", example, section, field)


def _tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return (str(value),)


def load_source_readmodels(readmodel_root: Path = DEFAULT_EXPORT_ROOT) -> dict[str, dict[str, Any] | None]:
    return {
        rail_name: _read_json(readmodel_root / filename)
        for rail_name, filename in SOURCE_READMODEL_FILES.items()
    }


def build_aggregator(readmodel_root: Path = DEFAULT_EXPORT_ROOT) -> CapitalHiltonInvoiceOperatorReadbackAggregator:
    return CapitalHiltonInvoiceOperatorReadbackAggregator(
        aggregator_id="capital_hilton_invoice_operator_readback_aggregator_v0",
        doctrine=(
            "Summarize existing Capital Hilton invoice rails only.",
            "Do not create receipts, approvals, packages, drafts, submissions, sends, or completion writes.",
            "Never claim sent, submitted, or complete without completion proof aggregator support.",
            "Operator chat receives a concise human status with refs for details.",
        ),
        source_readmodels=tuple(_source_ref(readmodel_root, rail) for rail in RAIL_NAMES),
        status_policy=(
            "Current status is fail-closed when any required rail is missing or blocked.",
            "Package readiness is not execution authority.",
            "Dry-run readiness is not completion proof.",
            "Fixture completion may prove the display shape but does not change current state.",
        ),
        readiness_policy=(
            "Ready means reviewable or proof-modeled, not executable.",
            "Email send and Coupa submit remain false unless their gated adapters and approvals prove readiness.",
            "Workflow run remains false in this lane.",
        ),
        proof_policy=(
            "INVOICE SENT requires final email send and attachment proof receipts.",
            "INVOICE SENT AND RECORDED requires all configured completion receipts.",
            "Missing receipts are listed as missing; this lane does not infer them.",
        ),
        operator_message_policy=(
            "Plain language first; machine refs are detail_refs.",
            "Blocked and missing states include how_to_fix.",
            "Messages must state that nothing was sent, submitted, opened, approved, or marked complete.",
        ),
        mac_chat_policy=(
            "Output is shaped for one chat status card.",
            "operator_headline and operator_message are directly displayable.",
            "detail_refs point to underlying readmodels for drilldown.",
        ),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Confirm PO/reference and protected refs, then create approval receipts before any future gated send or submit adapter can act.",
    )


def build_rail_summaries(
    source_readmodels: dict[str, dict[str, Any] | None],
    readmodel_root: Path = DEFAULT_EXPORT_ROOT,
) -> tuple[InvoiceWorkflowRailSummary, ...]:
    rows: list[InvoiceWorkflowRailSummary] = []
    for rail_name in RAIL_NAMES:
        data = source_readmodels.get(rail_name)
        ref = _source_ref(readmodel_root, rail_name)
        if data is None:
            rows.append(
                InvoiceWorkflowRailSummary(
                    rail_id=f"rail_{rail_name.lower()}",
                    rail_name=rail_name,
                    source_readmodel_ref=ref,
                    rail_status="MISSING_REQUIRED_RAIL",
                    ready=False,
                    missing=(SOURCE_READMODEL_FILES[rail_name],),
                    blocked=("operator status cannot trust this rail until the readmodel is regenerated",),
                    proof_status="missing",
                    how_to_fix=f"Regenerate {SOURCE_READMODEL_FILES[rail_name]} and rerun the Capital Hilton operator readback.",
                    next_safe_move=f"Regenerate {SOURCE_READMODEL_FILES[rail_name]}.",
                )
            )
            continue

        if rail_name == "DELIVERY_FACTS":
            status = data.get("contract_status", "DELIVERY_FACTS_MODELED")
            row = InvoiceWorkflowRailSummary(
                "rail_delivery_facts",
                rail_name,
                ref,
                str(status),
                True,
                (),
                ("execution remains locked",),
                "delivery basis modeled from workflow package readback",
                "Use package refs for review; do not execute.",
                "Keep building proof and approval rails.",
            )
        elif rail_name == "INVOICE_ARTIFACT":
            status = str(_nested_get(data, "readback", "status") or "UNKNOWN_FAIL_CLOSED")
            missing = _tuple(_nested_get(data, "readback", "missing_items"))
            row = InvoiceWorkflowRailSummary(
                "rail_invoice_artifact",
                rail_name,
                ref,
                status,
                status in {"ARTIFACT_READY", "ARTIFACT_METADATA_READY"},
                missing,
                _tuple(_nested_get(data, "readback", "blocked_actions")),
                "artifact/hash refs available" if status == "ARTIFACT_READY" else "artifact proof not ready",
                str(_nested_get(data, "readback", "how_to_fix") or "Generate or verify the bounded invoice artifact and hash."),
                str(data.get("next_safe_move", "Pass attachment refs to email/Coupa package rails.")),
            )
        elif rail_name == "EMAIL_DRAFT":
            status = str(_example_get(data, "capital_hilton_local_eml_draft_artifact", "readback", "status") or "UNKNOWN_FAIL_CLOSED")
            row = InvoiceWorkflowRailSummary(
                "rail_email_draft",
                rail_name,
                ref,
                status,
                status in {"LOCAL_DRAFT_ARTIFACT_READY", "METADATA_DRAFT_READY", "DRAFT_READY_FOR_REVIEW"},
                (),
                ("send remains locked",),
                "draft review artifact modeled",
                "Review the draft; do not send.",
                str(data.get("next_safe_move", "Review draft and keep send locked.")),
            )
        elif rail_name == "EMAIL_SEND":
            status = str(_example_get(data, "capital_hilton_send_blocked_missing_approval", "readiness_readback", "status") or "SEND_BLOCKED_MISSING_GATES")
            missing = _tuple(_example_get(data, "capital_hilton_send_blocked_missing_approval", "gate_check", "missing_gates"))
            row = InvoiceWorkflowRailSummary(
                "rail_email_send",
                rail_name,
                ref,
                status,
                False,
                missing or ("Guardian approval ref", "exact operator approval receipt ref"),
                ("email send", "provider send call", "attachment send"),
                "send receipt absent",
                str(_example_get(data, "capital_hilton_send_blocked_missing_approval", "readiness_readback", "how_to_fix") or "Create Guardian approval and exact operator approval receipt before send."),
                str(data.get("next_safe_move", "Resolve missing email send gates.")),
            )
        elif rail_name == "COUPA_PACKAGE":
            status = str(_example_get(data, "capital_hilton_missing_po", "readback", "status") or "NOT_READY_MISSING_PO")
            row = InvoiceWorkflowRailSummary(
                "rail_coupa_package",
                rail_name,
                ref,
                status,
                False,
                ("confirmed Coupa PO/reference",),
                ("Coupa access", "Coupa submit", "browser"),
                "package shape exists but official PO/reference is not confirmed in current status",
                str(_example_get(data, "capital_hilton_missing_po", "readback", "how_to_fix") or "Provide, attach, or confirm the Coupa PO/reference."),
                str(data.get("next_safe_move", "Resolve missing PO/secret/approval proof refs.")),
            )
        elif rail_name == "COUPA_SUBMIT":
            status = str(_example_get(data, "capital_hilton_submit_blocked_missing_po", "readiness_readback", "status") or "SUBMIT_BLOCKED_MISSING_PO")
            missing = _tuple(_example_get(data, "capital_hilton_submit_blocked_missing_po", "gate_check", "missing_gates"))
            row = InvoiceWorkflowRailSummary(
                "rail_coupa_submit",
                rail_name,
                ref,
                status,
                False,
                missing or ("confirmed Coupa PO/reference", "protected Coupa credential/secret ref", "Guardian approval ref"),
                ("Coupa access", "Coupa submit", "browser", "portal login"),
                "submit receipt absent",
                str(_example_get(data, "capital_hilton_submit_blocked_missing_po", "readiness_readback", "how_to_fix") or "Confirm PO/reference and approval gates before any future submit adapter."),
                str(data.get("next_safe_move", "Resolve missing Coupa submit gates.")),
            )
        elif rail_name == "RUN_PACKAGE":
            status = str(_example_get(data, "capital_hilton_not_ready", "run_package", "readiness_status") or "NOT_READY_MISSING_INPUTS")
            row = InvoiceWorkflowRailSummary(
                "rail_run_package",
                rail_name,
                ref,
                status,
                False,
                ("approval receipts", "proof receipts", "future execution adapters"),
                ("workflow run", "agent dispatch", "completion claim"),
                "run package is not execution authority",
                str(_example_get(data, "capital_hilton_not_ready", "readiness_readback", "how_to_fix") or "Resolve missing run package inputs and keep execution locked."),
                str(data.get("next_safe_move", "Resolve missing package/proof refs.")),
            )
        elif rail_name == "DRY_RUN":
            status = str(_example_get(data, "capital_hilton_current_not_ready", "readback", "status") or "DRY_RUN_BLOCKED_MISSING_INPUTS")
            row = InvoiceWorkflowRailSummary(
                "rail_dry_run",
                rail_name,
                ref,
                status,
                False,
                ("proof receipts", "approval receipts", "future adapters"),
                ("dry-run external action", "completion claim"),
                "dry-run reports blocked/missing states only",
                str(_example_get(data, "capital_hilton_current_not_ready", "readback", "how_to_fix") or "Resolve dry-run missing inputs."),
                str(data.get("next_safe_move", "Use dry-run report to choose the next missing rail.")),
            )
        elif rail_name == "COMPLETION_PROOF":
            status = str(_example_get(data, "capital_hilton_not_complete", "readback", "status") or "COMPLETION_BLOCKED_NO_RECEIPTS")
            missing = _tuple(_example_get(data, "capital_hilton_not_complete", "proof_set", "missing_receipts"))
            row = InvoiceWorkflowRailSummary(
                "rail_completion_proof",
                rail_name,
                ref,
                status,
                False,
                missing or ("EMAIL_SEND_RECEIPT", "COUPA_SUBMIT_RECEIPT", "OPERATOR_APPROVAL_RECEIPT"),
                ("INVOICE SENT claim", "completion write"),
                "completion proof receipts missing",
                str(_example_get(data, "capital_hilton_not_complete", "readback", "how_to_fix") or "Attach final proof receipts before marking completion."),
                str(data.get("next_safe_move", "Attach real completion receipts and rerun proof aggregation.")),
            )
        elif rail_name == "GUARDIAN_APPROVAL":
            status = str(_example_get(data, "capital_hilton_email_approval", "readback", "status") or "UNKNOWN_FAIL_CLOSED")
            row = InvoiceWorkflowRailSummary(
                "rail_guardian_approval",
                rail_name,
                ref,
                status,
                status == "APPROVAL_PACKET_READY",
                ("exact operator approval receipt",),
                ("approval execution", "action authorization"),
                "review packet exists; approval receipt is still separate",
                "Create exact operator approval receipt only through the future gated approval lane.",
                str(data.get("next_safe_move", "Use Guardian packet for review only.")),
            )
        elif rail_name == "SECRET_REF":
            row = InvoiceWorkflowRailSummary(
                "rail_secret_ref",
                rail_name,
                ref,
                str(data.get("contract_status", "DETERMINISTIC_CONTRACT_ONLY_PROTECTED_SECRET_INTAKE")),
                False,
                ("protected Coupa credential ref for future portal access",),
                ("secret reveal", "credential handling"),
                "protected secret intake contract exists; no live secret ref is consumed here",
                "Use the protected secret intake flow later; never paste raw credentials into chat.",
                "Keep secrets as protected refs only.",
            )
        else:
            status = str(_nested_get(data, "metadata_readback", "status") or data.get("contract_status", "SOURCE_REFS_MODELED"))
            row = InvoiceWorkflowRailSummary(
                "rail_file_source_refs",
                rail_name,
                ref,
                status,
                True,
                (),
                ("file body ingestion", "OCR", "raw content parsing"),
                "metadata/source refs available without file body ingestion",
                "Use source refs only; do not read raw file bodies.",
                "Reference safe source refs for drilldown.",
            )
        rows.append(row)
    return tuple(rows)


def _detail_refs(rails: tuple[InvoiceWorkflowRailSummary, ...]) -> tuple[str, ...]:
    return tuple(row.source_readmodel_ref for row in rails)


def build_unified_status(
    rails: tuple[InvoiceWorkflowRailSummary, ...],
    *,
    scenario: str = "current",
    completion_confirmed: bool = False,
) -> CapitalHiltonInvoiceUnifiedStatus:
    if completion_confirmed:
        return CapitalHiltonInvoiceUnifiedStatus(
            status_id=f"capital_hilton_unified_status_{scenario}",
            workflow_ref=WORKFLOW_REF,
            client_ref=CLIENT_REF,
            tenant_ref=TENANT_REF,
            headline="INVOICE SENT AND RECORDED",
            plain_status="The complete fixture has all required proof refs. This aggregator did not send, submit, open, approve, or record anything.",
            ready_items=(
                "email send receipt and attachment proof are present in the fixture",
                "Coupa submit and confirmation proof are present in the fixture",
                "invoice artifact/hash, Guardian approval, operator approval, local record, and payment tracking proofs are present in the fixture",
            ),
            missing_items=(),
            blocked_items=("no new action performed by this aggregator",),
            proof_items=(
                "EMAIL_SEND_RECEIPT",
                "EMAIL_ATTACHMENT_PROOF",
                "COUPA_SUBMIT_RECEIPT",
                "COUPA_CONFIRMATION_PROOF",
                "INVOICE_ARTIFACT_HASH_PROOF",
                "GUARDIAN_APPROVAL_RECEIPT",
                "OPERATOR_APPROVAL_RECEIPT",
            ),
            package_items=_detail_refs(rails),
            next_safe_move="Preserve proof refs and show the proof-backed completion readback only.",
            can_mark_invoice_sent=True,
            can_send_email=False,
            can_submit_coupa=False,
            can_run_workflow=False,
            completion_label_status="COMPLETION_CONFIRMED_FIXTURE_ONLY",
        )

    missing = tuple(dict.fromkeys(CURRENT_MISSING_ITEMS + tuple(item for rail in rails for item in rail.missing if item)))
    blocked = tuple(dict.fromkeys(CURRENT_BLOCKED_ITEMS + tuple(item for rail in rails for item in rail.blocked if item)))
    ready = tuple(dict.fromkeys(CURRENT_READY_ITEMS + tuple(f"{rail.rail_name}: {rail.rail_status}" for rail in rails if rail.ready)))
    proof_items = (
        "invoice artifact/hash proof may be available from the artifact rail",
        "completion proof aggregator currently blocks INVOICE SENT because final receipts are missing",
        "send and submit receipts are absent in current status",
    )
    return CapitalHiltonInvoiceUnifiedStatus(
        status_id=f"capital_hilton_unified_status_{scenario}",
        workflow_ref=WORKFLOW_REF,
        client_ref=CLIENT_REF,
        tenant_ref=TENANT_REF,
        headline="Capital Hilton invoice workflow is not ready yet",
        plain_status=(
            "Capital Hilton invoice is not ready to run yet. OpenClaw has the delivery basis, "
            "but still needs confirmed PO/reference, protected refs, approval receipts, and final send/submit proof. "
            "Nothing has been sent, submitted, opened, approved, or marked complete."
        ),
        ready_items=ready,
        missing_items=missing,
        blocked_items=blocked,
        proof_items=proof_items,
        package_items=_detail_refs(rails),
        next_safe_move="Confirm the Coupa PO/reference, then create Guardian and exact operator approval receipts before any future gated send or submit adapter can act.",
        can_mark_invoice_sent=False,
        can_send_email=False,
        can_submit_coupa=False,
        can_run_workflow=False,
        completion_label_status="BLOCKED_MISSING_RECEIPTS",
    )


def build_chat_response(
    unified_status: CapitalHiltonInvoiceUnifiedStatus,
    rails: tuple[InvoiceWorkflowRailSummary, ...],
    *,
    response_id_suffix: str = "current",
) -> OperatorChatResponse:
    missing_preview = ", ".join(unified_status.missing_items[:4])
    blocked_preview = ", ".join(unified_status.blocked_items[:4])
    if unified_status.can_mark_invoice_sent:
        message = (
            "INVOICE SENT AND RECORDED. Proofs show email, attachment, Coupa, artifact, approval, "
            "local record, and payment tracking receipts in the fixture. This aggregator performed no action."
        )
        how_to_fix = "No fix for the fixture; preserve proof refs."
    else:
        message = (
            "Capital Hilton invoice is not ready to run yet. OpenClaw has the delivery basis, "
            f"but still needs {missing_preview}. Nothing has been sent, submitted, opened, approved, or marked complete."
        )
        how_to_fix = (
            "Confirm the Coupa PO/reference, verify protected refs, then create Guardian and exact operator approval receipts. "
            "After future gated send/submit lanes produce receipts, rerun completion proof aggregation."
        )
    return OperatorChatResponse(
        response_id=f"capital_hilton_operator_chat_response_{response_id_suffix}",
        source_status_ref=unified_status.status_id,
        operator_headline=unified_status.headline,
        operator_message=message,
        concise_summary=(
            "Draft/artifact review can continue, but send, Coupa submit, workflow run, and INVOICE SENT remain locked."
            if not unified_status.can_mark_invoice_sent
            else "Fixture completion is proof-backed; no live action was performed."
        ),
        what_is_ready=unified_status.ready_items[:5],
        what_is_missing=unified_status.missing_items[:7],
        what_is_blocked=unified_status.blocked_items[:8],
        how_to_fix=how_to_fix,
        next_safe_move=unified_status.next_safe_move,
        detail_refs=_detail_refs(rails),
        mac_chat_render_hint="single_concise_status_card_with_detail_refs",
    )


def build_blockers() -> tuple[InvoiceStatusBlocker, ...]:
    return (
        InvoiceStatusBlocker("invoice_status_blocker_completion_without_proof", "COMPLETION_CLAIM_WITHOUT_PROOF", "INVOICE SENT is requested without completion proof receipts.", "critical", "Completion cannot be displayed without proof receipts.", True, "Attach send/attachment/submit/approval/local-record receipts first."),
        InvoiceStatusBlocker("invoice_status_blocker_send_without_approval", "SEND_READY_WITHOUT_APPROVAL", "Email send readiness appears without Guardian and exact operator approval receipts.", "critical", "Send remains locked until approval receipts exist.", True, "Create Guardian packet and exact operator approval receipt."),
        InvoiceStatusBlocker("invoice_status_blocker_coupa_without_approval", "COUPA_READY_WITHOUT_APPROVAL", "Coupa submit readiness appears without Guardian and exact operator approval receipts.", "critical", "Coupa submit remains locked until approval receipts exist.", True, "Create Guardian packet and exact operator approval receipt."),
        InvoiceStatusBlocker("invoice_status_blocker_run_without_gate", "RUN_READY_WITHOUT_EXECUTION_GATE", "Run package appears ready without execution gate receipts.", "critical", "Workflow run is not authorized in this lane.", True, "Keep execution locked and return readback only."),
        InvoiceStatusBlocker("invoice_status_blocker_missing_required_rail", "MISSING_REQUIRED_RAIL", "A required rail readmodel is unavailable.", "high", "Operator status is incomplete until the rail is regenerated.", True, "Regenerate the missing readmodel and rerun this aggregator."),
        InvoiceStatusBlocker("invoice_status_blocker_stale_readmodel", "STALE_READMODEL", "A source readmodel is stale for the current workflow state.", "medium", "Stale status must not drive execution.", True, "Refresh source rails before acting."),
        InvoiceStatusBlocker("invoice_status_blocker_contradiction", "CONTRADICTORY_RAIL_STATUS", "One rail says ready while a gated adapter or proof rail says blocked.", "high", "Contradictory rails fail closed.", True, "Trust proof/gate blockers and rerun source rails."),
        InvoiceStatusBlocker("invoice_status_blocker_raw_body", "RAW_PRIVATE_BODY_EXPOSED", "Raw private body appears in operator readback.", "critical", "Raw body exposure is blocked.", True, "Use refs and safe summaries only."),
        InvoiceStatusBlocker("invoice_status_blocker_external_action", "EXTERNAL_ACTION_ATTEMPTED", "Aggregator attempts send, submit, browser, payment, workflow, approval, or completion action.", "critical", "External action is blocked.", True, "Return operator readback only."),
        InvoiceStatusBlocker("invoice_status_blocker_unknown", "UNKNOWN_FAIL_CLOSED", "Unknown operator status state.", "high", "Unknown state fails closed.", True, "Ask for scoped rail readmodels."),
    )


def _model_schema(cls: type[Any]) -> dict[str, tuple[str, ...]]:
    return {cls.__name__: tuple(field.name for field in fields(cls))}


def _base_bundle(
    rails: tuple[InvoiceWorkflowRailSummary, ...],
    *,
    scenario: str,
    completion_confirmed: bool = False,
) -> dict[str, Any]:
    unified_status = build_unified_status(rails, scenario=scenario, completion_confirmed=completion_confirmed)
    chat_response = build_chat_response(unified_status, rails, response_id_suffix=scenario)
    return {
        "unified_status": asdict(unified_status),
        "rail_summaries": tuple(asdict(rail) for rail in rails),
        "chat_response": asdict(chat_response),
    }


def build_examples(rails: tuple[InvoiceWorkflowRailSummary, ...]) -> dict[str, Any]:
    current = _base_bundle(rails, scenario="current_not_ready")

    draft_ready = _base_bundle(rails, scenario="email_draft_ready_send_blocked")
    draft_ready["unified_status"]["headline"] = "Email draft is ready for review, but sending is locked"
    draft_ready["chat_response"]["operator_headline"] = draft_ready["unified_status"]["headline"]
    draft_ready["chat_response"]["operator_message"] = "The email draft is ready for review, but sending is still locked. Guardian approval, exact operator approval, provider gate, and final send receipt are still missing."

    coupa_blocked = _base_bundle(rails, scenario="coupa_package_submit_blocked")
    coupa_blocked["unified_status"]["headline"] = "Coupa package exists, but submit is blocked"
    coupa_blocked["chat_response"]["operator_headline"] = coupa_blocked["unified_status"]["headline"]
    coupa_blocked["chat_response"]["operator_message"] = "The Coupa package shape can be reviewed, but Coupa access and submit are blocked until PO/reference, protected refs, approvals, and a future gated provider adapter exist."

    completion_blocked = _base_bundle(rails, scenario="completion_proof_blocked")
    completion_blocked["unified_status"]["headline"] = "OpenClaw cannot mark INVOICE SENT yet"
    completion_blocked["chat_response"]["operator_headline"] = completion_blocked["unified_status"]["headline"]
    completion_blocked["chat_response"]["operator_message"] = "OpenClaw cannot mark INVOICE SENT yet because the required proof receipts are missing. Nothing new was sent, submitted, opened, approved, or recorded by this check."

    complete = _base_bundle(rails, scenario="fully_complete_fixture", completion_confirmed=True)

    false_claim = _base_bundle(rails, scenario="false_invoice_sent_claim_blocked")
    false_claim["unified_status"]["headline"] = "INVOICE SENT claim blocked"
    false_claim["unified_status"]["blocked_items"] = tuple(
        dict.fromkeys(tuple(false_claim["unified_status"]["blocked_items"]) + ("INVOICE SENT without proof receipts",))
    )
    false_claim["chat_response"]["operator_headline"] = false_claim["unified_status"]["headline"]
    false_claim["chat_response"]["operator_message"] = "OpenClaw cannot mark INVOICE SENT yet because no email send receipt and attachment proof are present."

    return {
        "current_capital_hilton_not_ready": current,
        "email_draft_ready_send_blocked": draft_ready,
        "coupa_package_submit_blocked": coupa_blocked,
        "completion_proof_blocked": completion_blocked,
        "fully_complete_fixture": complete,
        "false_invoice_sent_claim_blocked": false_claim,
    }


def build_payload(
    generated_at: str = DEFAULT_GENERATED_AT,
    *,
    readmodel_root: Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    source_readmodels = load_source_readmodels(readmodel_root)
    aggregator = build_aggregator(readmodel_root)
    rails = build_rail_summaries(source_readmodels, readmodel_root)
    unified_status = build_unified_status(rails)
    chat_response = build_chat_response(unified_status, rails)
    blockers = build_blockers()
    examples = build_examples(rails)
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "workflow_ref": WORKFLOW_REF,
        "client_ref": CLIENT_REF,
        "tenant_ref": TENANT_REF,
        "rail_names": RAIL_NAMES,
        "blocker_types": BLOCKER_TYPES,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "model_schemas": {
            **_model_schema(CapitalHiltonInvoiceOperatorReadbackAggregator),
            **_model_schema(CapitalHiltonInvoiceUnifiedStatus),
            **_model_schema(InvoiceWorkflowRailSummary),
            **_model_schema(OperatorChatResponse),
            **_model_schema(InvoiceStatusBlocker),
        },
        "aggregator": asdict(aggregator),
        "unified_status": asdict(unified_status),
        "rail_summaries": tuple(asdict(rail) for rail in rails),
        "chat_response": asdict(chat_response),
        "invoice_status_blockers": tuple(asdict(blocker) for blocker in blockers),
        "examples": examples,
        "mac_response_preview": {
            "request_type": "CAPITAL_HILTON_INVOICE_STATUS_READBACK",
            "internal_status": unified_status.completion_label_status,
            "operator_headline": chat_response.operator_headline,
            "operator_message": chat_response.operator_message,
            "what_happened": "OpenClaw aggregated existing Capital Hilton invoice workflow rail readmodels into one status.",
            "why_it_happened": "The operator needs one chat-facing status instead of inspecting separate readmodels.",
            "how_to_fix": chat_response.how_to_fix,
            "next_safe_move": chat_response.next_safe_move,
            "readback_files": (str(readmodel_root / JSON_EXPORT_NAME),),
            "terminal": True,
        },
        "operator_summary": (
            "Capital Hilton invoice workflow is summarized into one human readback. "
            "The current status is not ready: send, Coupa submit, workflow run, and INVOICE SENT remain locked."
        ),
        "machine_proof": {
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "workflow_run_performed": False,
            "email_send_performed": False,
            "mail_send_performed": False,
            "gmail_send_performed": False,
            "coupa_access_performed": False,
            "coupa_submit_performed": False,
            "browser_access_performed": False,
            "secret_reveal_performed": False,
            "approval_execution_performed": False,
            "payment_tracking_write_performed": False,
            "completion_write_performed": False,
            "external_action_performed": False,
            "credential_handling_performed": False,
            "raw_body_ingestion_performed": False,
            "mac_sync_import_performed": False,
            "swift_change_performed": False,
            "git_push_performed": False,
        },
        "next_safe_move": unified_status.next_safe_move,
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    status = payload["unified_status"]
    chat = payload["chat_response"]
    lines = [
        "# Capital Hilton Invoice Operator Readback",
        "",
        "## Status",
        chat["operator_message"],
        "",
        "## Ready",
    ]
    for item in chat["what_is_ready"]:
        lines.append(f"- {item}")
    lines += ["", "## Missing"]
    for item in chat["what_is_missing"]:
        lines.append(f"- {item}")
    lines += ["", "## Blocked"]
    for item in chat["what_is_blocked"]:
        lines.append(f"- {item}")
    lines += [
        "",
        "## Can Mark Invoice Sent",
        f"- {status['can_mark_invoice_sent']}",
        "",
        "## How To Fix",
        chat["how_to_fix"],
        "",
        "## Detail Refs",
    ]
    for ref in chat["detail_refs"]:
        lines.append(f"- {ref}")
    lines += [
        "",
        "## Boundary",
        "No workflow run, no email send, no Mail/Gmail send, no Coupa access/submit, no browser, no secret reveal, no approval execution, no payment tracking write, no completion write, no external action, no credential handling, no raw-body ingestion.",
    ]
    return "\n".join(lines) + "\n"


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def _summary(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> dict[str, Any]:
    status = payload["unified_status"]
    return {
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "headline": status["headline"],
        "can_mark_invoice_sent": status["can_mark_invoice_sent"],
        "can_send_email": status["can_send_email"],
        "can_submit_coupa": status["can_submit_coupa"],
        "can_run_workflow": status["can_run_workflow"],
        "rail_count": len(payload["rail_summaries"]),
        "blocker_count": len(payload["invoice_status_blockers"]),
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "json_export": str(export_root / JSON_EXPORT_NAME),
        "operator_export": str(export_root / OPERATOR_EXPORT_NAME),
    }


def build_and_export(
    *,
    generated_at: str = DEFAULT_GENERATED_AT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    readmodel_root: Path = DEFAULT_EXPORT_ROOT,
    format_name: str = "summary",
) -> dict[str, Any]:
    payload = build_payload(generated_at=generated_at, readmodel_root=readmodel_root)
    write_exports(payload, export_root)
    return payload if format_name == "json" else _summary(payload, export_root)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Capital Hilton invoice operator readback.")
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--readmodel-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_and_export(
        generated_at=args.generated_at,
        export_root=Path(args.export_root),
        readmodel_root=Path(args.readmodel_root),
        format_name=args.format,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
