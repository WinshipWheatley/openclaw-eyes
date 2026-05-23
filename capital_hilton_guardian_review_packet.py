"""Capital Hilton Guardian Review Packet Contract v0.

This read-model defines Guardian review packets for Capital Hilton protected
finance proof metadata. Guardian may review metadata posture and recommend
promotion, rejection, quarantine, or operator escalation. Guardian may not read
raw bodies, access accounts, approve invoice generation, approve send/submit,
write ledgers, or activate models, tools, agents, queues, or runtime work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "capital_hilton_guardian_review_packet_v0"
READ_MODEL_ID = "capital_hilton_guardian_review_packet"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

ANSWER_CANDIDATE_READ_MODEL_REF = "generated/read_models/capital_hilton_answer_candidate_receipt.json"
PROTECTED_PLACEHOLDER_READ_MODEL_REF = "generated/read_models/capital_hilton_protected_reference_placeholder.json"
PROTECTED_EVIDENCE_RECEIPT_REF = "generated/read_models/protected_evidence_reference_receipt.json"

REVIEW_STATUSES = (
    "NOT_READY_FOR_GUARDIAN",
    "READY_FOR_GUARDIAN_REVIEW",
    "GUARDIAN_REVIEW_REQUIRED",
    "GUARDIAN_METADATA_ALLOWED",
    "GUARDIAN_METADATA_REJECTED",
    "GUARDIAN_QUARANTINED",
    "OPERATOR_ESCALATION_REQUIRED",
    "UNKNOWN_FAIL_CLOSED",
)

SENSITIVITY_CLASSES = (
    "PROTECTED_FINANCE_METADATA",
    "COUPA_REFERENCE_METADATA",
    "AP_ROUTE_METADATA",
    "TAX_VENDOR_PAYMENT_METADATA",
    "FUTURE_INVOICE_GENERATION_METADATA",
    "UNKNOWN_FAIL_CLOSED",
)

ALLOWED_INPUTS = (
    "proof item id",
    "answer candidate receipt ref",
    "protected placeholder ref",
    "source-card ref",
    "receipt ref",
    "hash/ref placeholder",
    "redacted metadata label",
    "operator-provided description as memory candidate",
)

BLOCKED_INPUTS = (
    "raw Excel body",
    "raw PDF body",
    "raw email body",
    "raw finance/private body",
    "Coupa login/session/browser data",
    "OAuth/session cookies",
    "credentials/API keys/tokens",
    "bank/check/remit data except protected metadata placeholder",
    "customer/private content not required for proof metadata",
    "live account reads",
)

ALLOWED_OUTPUTS = (
    "METADATA_PROMOTION_ALLOWED",
    "METADATA_PROMOTION_REJECTED",
    "QUARANTINE_REQUIRED",
    "OPERATOR_ESCALATION_REQUIRED",
    "NEEDS_MORE_PROOF",
    "NEEDS_REDACTION",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKED_OUTPUTS = (
    "invoice generation approval",
    "send/submit approval",
    "Coupa access approval",
    "browser/account approval",
    "email dispatch approval",
    "credential handling approval",
    "raw body extraction approval",
    "ledger write approval",
    "runtime/tool/model/agent/queue approval",
)

QUARANTINE_TRIGGERS = (
    "credential exposure",
    "raw body attached or referenced as readable",
    "Coupa/browser/session material appears",
    "bank/check/remit data not properly protected",
    "source ref conflicts with proof item",
    "authority overclaim",
    "unknown sensitive surface",
    "missing source/proof refs",
    "malformed receipt",
    "unredacted private/customer material",
    "worker report claims action authority",
)

NO_AUTHORITY_FLAGS = {
    "guardian_can_approve_invoice_generation": False,
    "guardian_can_approve_send_submit": False,
    "guardian_can_access_coupa": False,
    "guardian_can_access_browser_oauth": False,
    "guardian_can_access_gmail_calendar_email": False,
    "guardian_can_handle_credentials": False,
    "guardian_can_read_raw_excel_body": False,
    "guardian_can_read_raw_pdf_body": False,
    "guardian_can_read_raw_email_body": False,
    "guardian_can_read_raw_finance_body": False,
    "guardian_can_write_ledger": False,
    "guardian_can_dispatch_email": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
}


@dataclass(frozen=True)
class CapitalHiltonGuardianReviewPacket:
    guardian_packet_id: str
    display_name: str
    review_status: str
    review_scope: str
    linked_proof_item_ids: tuple[str, ...]
    linked_answer_candidate_refs: tuple[str, ...]
    linked_protected_placeholder_refs: tuple[str, ...]
    sensitivity_class: str
    protected_surfaces: tuple[str, ...]
    allowed_inputs: tuple[str, ...]
    blocked_inputs: tuple[str, ...]
    allowed_outputs: tuple[str, ...]
    blocked_outputs: tuple[str, ...]
    redaction_required: bool
    operator_final_authority_required: bool
    can_approve_metadata_promotion: bool
    can_approve_action: bool
    can_access_accounts: bool
    can_read_raw_bodies: bool
    required_receipts: tuple[str, ...]
    quarantine_triggers: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class GuardianReviewPacketExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    guardian_packet_count: int
    action_authority_granted: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _answer_refs(*proof_item_ids: str) -> tuple[str, ...]:
    return tuple(f"{ANSWER_CANDIDATE_READ_MODEL_REF}#{proof_item_id}_answer_candidate_receipt" for proof_item_id in proof_item_ids)


def _placeholder_refs(*proof_item_ids: str, protected_placeholder_present: bool = False) -> tuple[str, ...]:
    prefix = "" if protected_placeholder_present else "NOT_OBSERVED_OR_PENDING:"
    return tuple(
        f"{prefix}{PROTECTED_PLACEHOLDER_READ_MODEL_REF}#{proof_item_id}"
        for proof_item_id in proof_item_ids
    )


def _packet(
    *,
    guardian_packet_id: str,
    display_name: str,
    review_scope: str,
    linked_proof_item_ids: tuple[str, ...],
    sensitivity_class: str,
    protected_surfaces: tuple[str, ...],
    required_receipts: tuple[str, ...],
    next_safe_move: str,
    can_approve_metadata_promotion: bool = False,
    protected_placeholder_present: bool = False,
) -> CapitalHiltonGuardianReviewPacket:
    return CapitalHiltonGuardianReviewPacket(
        guardian_packet_id=guardian_packet_id,
        display_name=display_name,
        review_status="GUARDIAN_REVIEW_REQUIRED",
        review_scope=review_scope,
        linked_proof_item_ids=linked_proof_item_ids,
        linked_answer_candidate_refs=_answer_refs(*linked_proof_item_ids),
        linked_protected_placeholder_refs=_placeholder_refs(
            *linked_proof_item_ids,
            protected_placeholder_present=protected_placeholder_present,
        ),
        sensitivity_class=sensitivity_class,
        protected_surfaces=protected_surfaces,
        allowed_inputs=ALLOWED_INPUTS,
        blocked_inputs=BLOCKED_INPUTS,
        allowed_outputs=ALLOWED_OUTPUTS,
        blocked_outputs=BLOCKED_OUTPUTS,
        redaction_required=True,
        operator_final_authority_required=True,
        can_approve_metadata_promotion=can_approve_metadata_promotion,
        can_approve_action=False,
        can_access_accounts=False,
        can_read_raw_bodies=False,
        required_receipts=required_receipts,
        quarantine_triggers=QUARANTINE_TRIGGERS,
        next_safe_move=next_safe_move,
    )


def build_guardian_review_packets(
    *,
    protected_placeholder_present: bool = False,
) -> list[CapitalHiltonGuardianReviewPacket]:
    return [
        _packet(
            guardian_packet_id="protected_finance_metadata_review_packet",
            display_name="Protected Finance Metadata Review Packet",
            review_scope="Validate whether protected finance metadata references are safe to promote.",
            linked_proof_item_ids=(
                "performance_date_2026_05_08_proof",
                "performance_date_2026_05_15_proof",
                "rate_400_per_gig_proof",
                "subtotal_800_proof",
                "one_invoice_posture_proof",
            ),
            sensitivity_class="PROTECTED_FINANCE_METADATA",
            protected_surfaces=("performance proof metadata", "rate source metadata", "invoice posture metadata"),
            required_receipts=(
                "answer_candidate_receipt_ref",
                "protected_placeholder_ref",
                "redaction_receipt",
                "metadata_promotion_decision_receipt",
            ),
            next_safe_move="review_metadata_shape_only_and_recommend_promotion_rejection_or_quarantine",
            can_approve_metadata_promotion=True,
            protected_placeholder_present=protected_placeholder_present,
        ),
        _packet(
            guardian_packet_id="coupa_reference_metadata_review_packet",
            display_name="Coupa Reference Metadata Review Packet",
            review_scope="Classify Coupa/PO/payment reference metadata without any Coupa login, browser, or session access.",
            linked_proof_item_ids=("coupa_po_payment_reference_metadata",),
            sensitivity_class="COUPA_REFERENCE_METADATA",
            protected_surfaces=("Coupa reference metadata", "PO/payment reference metadata"),
            required_receipts=(
                "answer_candidate_receipt_ref",
                "protected_placeholder_ref",
                "metadata_only_boundary_receipt",
                "guardian_decision_receipt",
            ),
            next_safe_move="allow_only_redacted_metadata_or_quarantine_if_account_material_appears",
            protected_placeholder_present=protected_placeholder_present,
        ),
        _packet(
            guardian_packet_id="ap_route_metadata_review_packet",
            display_name="AP Route Metadata Review Packet",
            review_scope="Classify recipient/route metadata without raw email body access or sending.",
            linked_proof_item_ids=("ap_recipient_route_metadata",),
            sensitivity_class="AP_ROUTE_METADATA",
            protected_surfaces=("AP route metadata", "email route metadata"),
            required_receipts=(
                "answer_candidate_receipt_ref",
                "protected_placeholder_ref",
                "redaction_receipt",
                "guardian_decision_receipt",
            ),
            next_safe_move="review_route_metadata_only_and_keep_send_submit_blocked",
            protected_placeholder_present=protected_placeholder_present,
        ),
        _packet(
            guardian_packet_id="tax_vendor_payment_handling_review_packet",
            display_name="Tax Vendor Payment Handling Review Packet",
            review_scope="Classify sensitive payment, tax, and vendor handling questions as protected metadata only.",
            linked_proof_item_ids=("tax_vendor_handling_metadata",),
            sensitivity_class="TAX_VENDOR_PAYMENT_METADATA",
            protected_surfaces=("tax metadata", "vendor metadata", "payment handling metadata"),
            required_receipts=(
                "answer_candidate_receipt_ref",
                "protected_placeholder_ref",
                "redaction_receipt",
                "guardian_decision_receipt",
            ),
            next_safe_move="review_metadata_boundary_or_quarantine_if bank_or_tax_body_material appears",
            protected_placeholder_present=protected_placeholder_present,
        ),
        _packet(
            guardian_packet_id="future_invoice_generation_review_packet",
            display_name="Future Invoice Generation Review Packet",
            review_scope="Define what would be required before invoice generation could ever be reviewed while keeping invoice generation blocked.",
            linked_proof_item_ids=("future_invoice_generation_receipt_requirement",),
            sensitivity_class="FUTURE_INVOICE_GENERATION_METADATA",
            protected_surfaces=("future invoice receipt requirements", "blocked action posture"),
            required_receipts=(
                "future_invoice_receipt_contract_ref",
                "security_delta_or_repass_ref",
                "operator_final_authority_ref",
                "guardian_decision_receipt",
            ),
            next_safe_move="park_action_review_until_security_delta_or_repass_and_operator_final_authority_exist",
            protected_placeholder_present=protected_placeholder_present,
        ),
    ]


def build_capital_hilton_guardian_review_packet(
    *,
    generated_at: str | None = None,
    protected_placeholder_present: bool = False,
) -> dict[str, Any]:
    packets = build_guardian_review_packets(protected_placeholder_present=protected_placeholder_present)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": "capital_hilton_guardian_review_packet_v0",
        "generated_at": generated_at or utc_now(),
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_guardian_review_packet_metadata_only",
        "operator_summary": (
            "Guardian review packets define what protected Capital Hilton finance metadata "
            "can be reviewed, what must remain blocked, and what outcomes Guardian may "
            "recommend later. They do not approve invoice generation or live action."
        ),
        "review_statuses": list(REVIEW_STATUSES),
        "sensitivity_classes": list(SENSITIVITY_CLASSES),
        "allowed_inputs": list(ALLOWED_INPUTS),
        "blocked_inputs": list(BLOCKED_INPUTS),
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "blocked_outputs": list(BLOCKED_OUTPUTS),
        "quarantine_triggers": list(QUARANTINE_TRIGGERS),
        "guardian_review_packets": [asdict(packet) for packet in packets],
        "relationship_to_prior_lanes": {
            "capital_hilton_answer_candidate_receipt": {
                "read_model_ref": ANSWER_CANDIDATE_READ_MODEL_REF,
                "status": "OBSERVED_OR_EXPECTED",
                "relationship": "Answer candidates may request Guardian review when they point to protected references.",
            },
            "capital_hilton_protected_reference_placeholder": {
                "read_model_ref": PROTECTED_PLACEHOLDER_READ_MODEL_REF,
                "status": "OBSERVED" if protected_placeholder_present else "NOT_OBSERVED_OR_PENDING",
                "relationship": "Protected placeholders may become ready for Guardian review but are not proof by themselves.",
            },
            "protected_evidence_reference_receipt": {
                "read_model_ref": PROTECTED_EVIDENCE_RECEIPT_REF,
                "status": "OBSERVED_OR_EXPECTED",
                "relationship": "Guardian review packets stay compatible with existing protected evidence receipt patterns.",
            },
        },
        "guardian_rule_summary": {
            "guardian_may_review_metadata_posture_only": True,
            "guardian_may_recommend_metadata_promotion": True,
            "guardian_may_recommend_rejection": True,
            "guardian_may_recommend_quarantine": True,
            "guardian_may_recommend_operator_escalation": True,
            "guardian_may_approve_invoice_generation": False,
            "guardian_may_approve_send_submit": False,
            "guardian_may_access_accounts": False,
            "guardian_may_read_raw_bodies": False,
            "operator_final_authority_required_for_future_action": True,
        },
        "authority_boundary": {
            **NO_AUTHORITY_FLAGS,
            "all_authority_flags_false": all(value is False for value in NO_AUTHORITY_FLAGS.values()),
        },
        "batch_relationship": {
            "batch_id": "capital_hilton_proof_resolution_batch_v0",
            "prompt_index": 3,
            "stable_map_refresh_deferred": True,
            "commit_deferred_until_final_prompt": True,
            "next_lane": "capital_hilton_proof_quieting_progress_state",
        },
        "machine_proof": {
            "default_guardian_packet_count": len(packets),
            "default_guardian_packet_ids": [packet.guardian_packet_id for packet in packets],
            "linked_proof_item_ids_represented": sorted(
                {proof_item_id for packet in packets for proof_item_id in packet.linked_proof_item_ids}
            ),
            "allowed_review_statuses_exist": set(REVIEW_STATUSES)
            == {
                "NOT_READY_FOR_GUARDIAN",
                "READY_FOR_GUARDIAN_REVIEW",
                "GUARDIAN_REVIEW_REQUIRED",
                "GUARDIAN_METADATA_ALLOWED",
                "GUARDIAN_METADATA_REJECTED",
                "GUARDIAN_QUARANTINED",
                "OPERATOR_ESCALATION_REQUIRED",
                "UNKNOWN_FAIL_CLOSED",
            },
            "sensitivity_classes_exist": set(SENSITIVITY_CLASSES)
            == {
                "PROTECTED_FINANCE_METADATA",
                "COUPA_REFERENCE_METADATA",
                "AP_ROUTE_METADATA",
                "TAX_VENDOR_PAYMENT_METADATA",
                "FUTURE_INVOICE_GENERATION_METADATA",
                "UNKNOWN_FAIL_CLOSED",
            },
            "allowed_inputs_metadata_only": True,
            "blocked_inputs_include_raw_bodies_credentials_and_account_material": True,
            "allowed_outputs_metadata_review_only": True,
            "blocked_outputs_include_action_authority": True,
            "quarantine_triggers_exist": len(QUARANTINE_TRIGGERS) >= 10,
            "guardian_cannot_approve_invoice_generation": True,
            "guardian_cannot_approve_send_submit": True,
            "guardian_cannot_access_accounts": True,
            "guardian_cannot_read_raw_bodies": True,
            "prior_lane_refs_represented": True,
            "credential_or_secret_included": False,
            "raw_private_body_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_capital_hilton_guardian_review_packet(payload: dict[str, Any]) -> str:
    lines = [
        "# Capital Hilton Guardian Review Packet v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "Guardian is reviewing whether protected Capital Hilton finance metadata is safe to promote as metadata. Guardian is not reviewing raw files, logging into accounts, approving invoices, or approving send/submit actions.",
        "",
        "## What Guardian Reviews",
        "",
        "- Proof item ids, answer candidate receipt refs, protected placeholder refs, source-card refs, receipt refs, hash/ref placeholders, redacted metadata labels, and operator descriptions as memory candidates.",
        "",
        "## What Guardian Cannot Do",
        "",
        "- Approve invoice generation.",
        "- Approve send/submit.",
        "- Access Coupa, browser/OAuth, Gmail/calendar/email, or any account.",
        "- Handle credentials or read raw Excel/PDF/email/finance bodies.",
        "- Write ledgers or approve runtime/tool/model/agent/queue execution.",
        "",
        "## Default Review Packets",
        "",
    ]
    for packet in payload["guardian_review_packets"]:
        lines.append(f"- `{packet['guardian_packet_id']}`: {packet['review_scope']}")
    lines.extend(
        [
            "",
            "## Metadata Outcomes",
            "",
            "- Guardian may recommend metadata promotion, metadata rejection, quarantine, operator escalation, more proof, redaction, or fail-closed.",
            "- Guardian approval is not invoice/action approval. Operator final authority and future security gates remain required for any action class.",
            "",
            "## Quarantine Triggers",
            "",
        ]
    )
    for trigger in payload["quarantine_triggers"]:
        lines.append(f"- {trigger}")
    lines.extend(
        [
            "",
            "## Next Backend Batch Lane",
            "",
            "- Prompt 4 will model proof quieting and progress state. It still will not quiet items without proof metadata, valid receipt, or valid rejection reason.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_capital_hilton_guardian_review_packet(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> GuardianReviewPacketExportResult:
    protected_placeholder_present = (Path(repo_root) / PROTECTED_PLACEHOLDER_READ_MODEL_REF).exists()
    payload = build_capital_hilton_guardian_review_packet(
        generated_at=generated_at,
        protected_placeholder_present=protected_placeholder_present,
    )
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_guardian_review_packet(payload), encoding="utf-8")
    return GuardianReviewPacketExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        guardian_packet_count=payload["machine_proof"]["default_guardian_packet_count"],
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Capital Hilton Guardian Review Packet read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_guardian_review_packet(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "guardian_packet_count": result.guardian_packet_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Capital Hilton Guardian Review Packet: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "ALLOWED_INPUTS",
    "ALLOWED_OUTPUTS",
    "ANSWER_CANDIDATE_READ_MODEL_REF",
    "BLOCKED_INPUTS",
    "BLOCKED_OUTPUTS",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "PROTECTED_EVIDENCE_RECEIPT_REF",
    "PROTECTED_PLACEHOLDER_READ_MODEL_REF",
    "QUARANTINE_TRIGGERS",
    "READ_MODEL_ID",
    "REVIEW_STATUSES",
    "SCHEMA_VERSION",
    "SENSITIVITY_CLASSES",
    "build_capital_hilton_guardian_review_packet",
    "build_guardian_review_packets",
    "export_capital_hilton_guardian_review_packet",
    "format_capital_hilton_guardian_review_packet",
    "stable_json",
]
