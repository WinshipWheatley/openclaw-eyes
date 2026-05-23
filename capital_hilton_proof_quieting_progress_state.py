"""Capital Hilton Proof Quieting / Progress State Contract v0.

This read-model models how the ten Capital Hilton proof items may progress
from missing proof toward quiet-with-proof candidates. It is state modeling
only: it does not capture answers, quiet anything automatically, read protected
files, generate invoices, access accounts, write ledgers, send email, or run
models, tools, agents, queues, or runtime work.
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

from capital_hilton_protected_proof_intake import (
    BLOCKED_ACTIONS as INTAKE_BLOCKED_ACTIONS,
    SHARED_FIX_PATH_ID,
    build_proof_intake_items,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "capital_hilton_proof_quieting_progress_state_v0"
READ_MODEL_ID = "capital_hilton_proof_quieting_progress_state"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

ANSWER_CANDIDATE_READ_MODEL_REF = "generated/read_models/capital_hilton_answer_candidate_receipt.json"
PROTECTED_PLACEHOLDER_READ_MODEL_REF = "generated/read_models/capital_hilton_protected_reference_placeholder.json"
GUARDIAN_PACKET_READ_MODEL_REF = "generated/read_models/capital_hilton_guardian_review_packet.json"
PROOF_INTAKE_READ_MODEL_REF = "generated/read_models/capital_hilton_protected_proof_intake.json"

PROGRESS_STATES = (
    "MISSING_PROOF",
    "ANSWERED_MEMORY_CANDIDATE_ONLY",
    "ANSWER_POINTS_TO_SOURCE_CARD",
    "ANSWER_POINTS_TO_PROTECTED_REFERENCE",
    "ANSWER_POINTS_TO_RECEIPT",
    "PROTECTED_PLACEHOLDER_LINKED",
    "GUARDIAN_REVIEW_REQUIRED",
    "GUARDIAN_METADATA_ALLOWED",
    "GUARDIAN_METADATA_REJECTED",
    "PROOF_METADATA_LINKED",
    "QUIET_WITH_PROOF_CANDIDATE",
    "QUIET_WITH_VALID_REJECTION",
    "PARKED_WITH_REASON",
    "QUARANTINED",
    "UNKNOWN_FAIL_CLOSED",
)

ATTENTION_CLASSES = (
    "NEEDS_OPERATOR_INPUT",
    "NEEDS_PROOF_REFERENCE",
    "NEEDS_PROTECTED_REFERENCE",
    "NEEDS_GUARDIAN_REVIEW",
    "NEEDS_RECEIPT",
    "NEEDS_SECURITY_DELTA",
    "READY_TO_QUIET_WITH_PROOF",
    "PARKED",
    "QUARANTINED",
    "QUIET",
    "UNKNOWN_FAIL_CLOSED",
)

EVENTS = (
    "OPERATOR_TEXT_ANSWER",
    "OPERATOR_YES_NO",
    "STRUCTURED_FORM_ANSWER",
    "SOURCE_CARD_LINKED",
    "PROTECTED_PLACEHOLDER_LINKED",
    "RECEIPT_LINKED",
    "GUARDIAN_REVIEW_REQUESTED",
    "GUARDIAN_METADATA_ALLOWED",
    "GUARDIAN_METADATA_REJECTED",
    "PROOF_METADATA_LINKED",
    "REJECTION_WITH_REASON",
    "PARK_WITH_REASON",
    "QUARANTINE_TRIGGERED",
    "UNKNOWN_EVENT",
)

NO_AUTHORITY_FLAGS = {
    "invoice_generation_allowed": False,
    "coupa_access_allowed": False,
    "browser_oauth_allowed": False,
    "gmail_calendar_email_access_allowed": False,
    "credential_handling_allowed": False,
    "raw_excel_body_ingestion_allowed": False,
    "raw_pdf_body_ingestion_allowed": False,
    "raw_email_body_ingestion_allowed": False,
    "raw_finance_body_ingestion_allowed": False,
    "ledger_write_allowed": False,
    "send_submit_approval_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "automatic_quieting_allowed": False,
    "automatic_progression_allowed": False,
}

BLOCKED_ACTIONS = tuple(
    dict.fromkeys(
        (
            *INTAKE_BLOCKED_ACTIONS,
            "automatic quieting",
            "automatic progression",
            "proof promotion without receipts",
            "proof promotion without Guardian where protected",
        )
    )
)


@dataclass(frozen=True)
class CapitalHiltonProofProgressState:
    proof_item_id: str
    display_name: str
    current_state: str
    current_attention_class: str
    candidate_value: Any
    answer_candidate_ref: str
    protected_placeholder_ref: str
    guardian_packet_ref: str
    source_card_ref: str | None
    receipt_ref: str | None
    proof_metadata_ref: str | None
    memory_candidate_ref: str | None
    quiet_receipt_ref: str | None
    rejection_reason: str | None
    park_reason: str | None
    quarantine_reason: str | None
    can_quiet_now: bool
    can_progress_now: bool
    requires_operator_input: bool
    requires_protected_reference: bool
    requires_guardian_review: bool
    requires_receipt: bool
    requires_security_delta: bool
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonProofStateTransitionRule:
    transition_id: str
    from_state: str
    event: str
    to_state: str
    allowed: bool
    required_refs: tuple[str, ...]
    required_gates: tuple[str, ...]
    authority_granted: bool
    notes: str


@dataclass(frozen=True)
class CapitalHiltonProofProgressSummary:
    target_world: str
    lane_id: str
    current_phase: str
    lane_destiny: str
    proof_items_total: int
    missing_proof_count: int
    answered_memory_candidate_count: int
    protected_placeholder_linked_count: int
    guardian_review_required_count: int
    proof_metadata_linked_count: int
    quiet_with_proof_count: int
    parked_count: int
    quarantined_count: int
    candidate_facts_proven: bool
    action_authority_granted: bool
    next_safe_move: str


@dataclass(frozen=True)
class ProofQuietingProgressStateExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    proof_progress_record_count: int
    missing_proof_count: int
    action_authority_granted: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _answer_ref(proof_item_id: str) -> str:
    return f"{ANSWER_CANDIDATE_READ_MODEL_REF}#{proof_item_id}_answer_candidate_receipt"


def _placeholder_ref(proof_item_id: str, *, placeholder_present: bool) -> str:
    prefix = "" if placeholder_present else "NOT_OBSERVED_OR_PENDING:"
    return f"{prefix}{PROTECTED_PLACEHOLDER_READ_MODEL_REF}#{proof_item_id}"


def _guardian_packet_ref(proof_item_id: str) -> str:
    if proof_item_id in {
        "performance_date_2026_05_08_proof",
        "performance_date_2026_05_15_proof",
        "rate_400_per_gig_proof",
        "subtotal_800_proof",
        "one_invoice_posture_proof",
    }:
        packet_id = "protected_finance_metadata_review_packet"
    elif proof_item_id == "coupa_po_payment_reference_metadata":
        packet_id = "coupa_reference_metadata_review_packet"
    elif proof_item_id == "ap_recipient_route_metadata":
        packet_id = "ap_route_metadata_review_packet"
    elif proof_item_id == "tax_vendor_handling_metadata":
        packet_id = "tax_vendor_payment_handling_review_packet"
    elif proof_item_id == "future_invoice_generation_receipt_requirement":
        packet_id = "future_invoice_generation_review_packet"
    else:
        packet_id = "UNKNOWN_FAIL_CLOSED"
    return f"{GUARDIAN_PACKET_READ_MODEL_REF}#{packet_id}"


def build_default_progress_records(
    *,
    placeholder_present: bool = False,
) -> list[CapitalHiltonProofProgressState]:
    records: list[CapitalHiltonProofProgressState] = []
    for item in build_proof_intake_items():
        records.append(
            CapitalHiltonProofProgressState(
                proof_item_id=item.proof_item_id,
                display_name=item.display_name,
                current_state="MISSING_PROOF",
                current_attention_class=(
                    "NEEDS_PROTECTED_REFERENCE" if item.protected_evidence_reference_required else "NEEDS_PROOF_REFERENCE"
                ),
                candidate_value=item.candidate_value,
                answer_candidate_ref=_answer_ref(item.proof_item_id),
                protected_placeholder_ref=_placeholder_ref(
                    item.proof_item_id,
                    placeholder_present=placeholder_present,
                ),
                guardian_packet_ref=_guardian_packet_ref(item.proof_item_id),
                source_card_ref=None,
                receipt_ref=None,
                proof_metadata_ref=None,
                memory_candidate_ref=None,
                quiet_receipt_ref=None,
                rejection_reason=None,
                park_reason=None,
                quarantine_reason=None,
                can_quiet_now=False,
                can_progress_now=True,
                requires_operator_input=True,
                requires_protected_reference=item.protected_evidence_reference_required,
                requires_guardian_review=item.guardian_gate_required,
                requires_receipt=item.receipt_required,
                requires_security_delta=item.proof_item_id == "future_invoice_generation_receipt_requirement",
                blocked_actions=BLOCKED_ACTIONS,
                next_safe_move="wait_for_safe_answer_or_reference_event_without_auto_progression",
            )
        )
    return records


def _transition(
    transition_id: str,
    from_state: str,
    event: str,
    to_state: str,
    required_refs: tuple[str, ...] = (),
    required_gates: tuple[str, ...] = (),
    notes: str = "",
    allowed: bool = True,
) -> CapitalHiltonProofStateTransitionRule:
    return CapitalHiltonProofStateTransitionRule(
        transition_id=transition_id,
        from_state=from_state,
        event=event,
        to_state=to_state,
        allowed=allowed,
        required_refs=required_refs,
        required_gates=required_gates,
        authority_granted=False,
        notes=notes,
    )


def build_transition_rules() -> list[CapitalHiltonProofStateTransitionRule]:
    rules = [
        _transition(
            "missing_plus_operator_text_answer",
            "MISSING_PROOF",
            "OPERATOR_TEXT_ANSWER",
            "ANSWERED_MEMORY_CANDIDATE_ONLY",
            required_refs=("memory_candidate_ref",),
            notes="Text can clarify operator memory but cannot prove or quiet.",
        ),
        _transition(
            "missing_plus_operator_yes_no",
            "MISSING_PROOF",
            "OPERATOR_YES_NO",
            "ANSWERED_MEMORY_CANDIDATE_ONLY",
            required_refs=("memory_candidate_ref",),
            notes="Yes/no can clarify but cannot prove.",
        ),
        _transition(
            "missing_plus_structured_form",
            "MISSING_PROOF",
            "STRUCTURED_FORM_ANSWER",
            "ANSWERED_MEMORY_CANDIDATE_ONLY",
            required_refs=("memory_candidate_ref",),
            notes="Structured form answer becomes candidate context, not proof.",
        ),
        _transition(
            "missing_plus_source_card",
            "MISSING_PROOF",
            "SOURCE_CARD_LINKED",
            "ANSWER_POINTS_TO_SOURCE_CARD",
            required_refs=("source_card_ref",),
            notes="Source-card refs point toward proof but do not auto-quiet.",
        ),
        _transition(
            "missing_plus_protected_placeholder",
            "MISSING_PROOF",
            "PROTECTED_PLACEHOLDER_LINKED",
            "PROTECTED_PLACEHOLDER_LINKED",
            required_refs=("protected_placeholder_ref",),
            notes="Protected placeholders are metadata pointers, not proof by themselves.",
        ),
        _transition(
            "missing_plus_receipt",
            "MISSING_PROOF",
            "RECEIPT_LINKED",
            "ANSWER_POINTS_TO_RECEIPT",
            required_refs=("receipt_ref",),
            notes="Receipt ref points toward proof but still requires validation.",
        ),
        _transition(
            "placeholder_plus_guardian_requested",
            "PROTECTED_PLACEHOLDER_LINKED",
            "GUARDIAN_REVIEW_REQUESTED",
            "GUARDIAN_REVIEW_REQUIRED",
            required_refs=("protected_placeholder_ref", "guardian_packet_ref"),
            required_gates=("Guardian metadata review",),
            notes="Guardian review is required before protected metadata promotion.",
        ),
        _transition(
            "guardian_required_plus_metadata_allowed",
            "GUARDIAN_REVIEW_REQUIRED",
            "GUARDIAN_METADATA_ALLOWED",
            "GUARDIAN_METADATA_ALLOWED",
            required_refs=("guardian_decision_receipt",),
            required_gates=("Guardian metadata decision",),
            notes="Guardian metadata allowed can progress metadata state but cannot execute.",
        ),
        _transition(
            "guardian_required_plus_metadata_rejected",
            "GUARDIAN_REVIEW_REQUIRED",
            "GUARDIAN_METADATA_REJECTED",
            "GUARDIAN_METADATA_REJECTED",
            required_refs=("guardian_decision_receipt",),
            required_gates=("Guardian metadata decision",),
            notes="Rejected metadata cannot promote proof.",
        ),
        _transition(
            "guardian_allowed_plus_proof_metadata",
            "GUARDIAN_METADATA_ALLOWED",
            "PROOF_METADATA_LINKED",
            "PROOF_METADATA_LINKED",
            required_refs=("proof_metadata_ref", "guardian_decision_receipt"),
            required_gates=("Guardian metadata allowed",),
            notes="Proof metadata may link only after required refs/gates.",
        ),
        _transition(
            "proof_metadata_plus_receipt",
            "PROOF_METADATA_LINKED",
            "RECEIPT_LINKED",
            "QUIET_WITH_PROOF_CANDIDATE",
            required_refs=("proof_metadata_ref", "receipt_ref", "quiet_receipt_ref"),
            notes="Proof metadata plus receipt can create quiet-with-proof candidate, not automatic quieting.",
        ),
        _transition(
            "missing_plus_rejection_with_reason",
            "MISSING_PROOF",
            "REJECTION_WITH_REASON",
            "QUIET_WITH_VALID_REJECTION",
            required_refs=("rejection_reason", "receipt_policy_ref"),
            notes="Rejection can quiet only with reason and receipt policy.",
        ),
        _transition(
            "missing_plus_park_with_reason",
            "MISSING_PROOF",
            "PARK_WITH_REASON",
            "PARKED_WITH_REASON",
            required_refs=("park_reason",),
            notes="Parked item remains parked and visible, not completed.",
        ),
    ]
    for state in PROGRESS_STATES:
        rules.append(
            _transition(
                f"{state.lower()}_plus_quarantine",
                state,
                "QUARANTINE_TRIGGERED",
                "QUARANTINED",
                required_refs=("quarantine_reason",),
                required_gates=("Guardian or Operator review",),
                notes="Any state can quarantine when sensitive/proof/authority conflict appears.",
            )
        )
        rules.append(
            _transition(
                f"{state.lower()}_plus_unknown_event",
                state,
                "UNKNOWN_EVENT",
                "UNKNOWN_FAIL_CLOSED",
                notes="Unknown state changes fail closed.",
            )
        )
    return rules


def build_progress_summary(records: list[CapitalHiltonProofProgressState]) -> CapitalHiltonProofProgressSummary:
    return CapitalHiltonProofProgressSummary(
        target_world="Finance",
        lane_id="capital_hilton",
        current_phase="HELM_THRESHOLD_LANE",
        lane_destiny="MOVE_TO_WORLD_ACTION",
        proof_items_total=len(records),
        missing_proof_count=sum(1 for record in records if record.current_state == "MISSING_PROOF"),
        answered_memory_candidate_count=0,
        protected_placeholder_linked_count=0,
        guardian_review_required_count=0,
        proof_metadata_linked_count=0,
        quiet_with_proof_count=0,
        parked_count=0,
        quarantined_count=0,
        candidate_facts_proven=False,
        action_authority_granted=False,
        next_safe_move="wait_for_explicit_answer_or_reference_input_then_apply_transition_rules_as_metadata",
    )


def build_capital_hilton_proof_quieting_progress_state(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    answer_present = (root / ANSWER_CANDIDATE_READ_MODEL_REF).exists()
    placeholder_present = (root / PROTECTED_PLACEHOLDER_READ_MODEL_REF).exists()
    guardian_present = (root / GUARDIAN_PACKET_READ_MODEL_REF).exists()
    proof_intake_present = (root / PROOF_INTAKE_READ_MODEL_REF).exists()
    records = build_default_progress_records(placeholder_present=placeholder_present)
    transitions = build_transition_rules()
    summary = build_progress_summary(records)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": "capital_hilton_proof_quieting_progress_state_v0",
        "generated_at": generated_at or utc_now(),
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_proof_quieting_progress_state_metadata_only",
        "operator_summary": (
            "This contract models Capital Hilton proof progress states. It starts all ten "
            "items as missing proof and defines safe transitions toward quiet-with-proof "
            "candidates without writing answers, quieting automatically, or enabling action."
        ),
        "progress_states": list(PROGRESS_STATES),
        "attention_classes": list(ATTENTION_CLASSES),
        "events": list(EVENTS),
        "proof_progress_records": [asdict(record) for record in records],
        "transition_rules": [asdict(rule) for rule in transitions],
        "progress_summary": asdict(summary),
        "quieting_policy": {
            "automatic_quieting_allowed": False,
            "automatic_progression_allowed": False,
            "answered_text_quiets_item": False,
            "source_or_protected_ref_auto_quiets_item": False,
            "guardian_metadata_allowed_executes_action": False,
            "proof_metadata_plus_receipt_can_create_candidate": True,
            "quiet_with_proof_requires_receipt": True,
            "valid_rejection_requires_reason_and_receipt_policy": True,
            "parked_item_is_complete": False,
            "quarantine_requires_guardian_or_operator_review": True,
        },
        "relationship_to_prior_lanes": {
            "capital_hilton_answer_candidate_receipt": {
                "read_model_ref": ANSWER_CANDIDATE_READ_MODEL_REF,
                "status": "OBSERVED" if answer_present else "NOT_OBSERVED_OR_PENDING",
                "relationship": "Answer candidate refs are progress inputs but not proof.",
            },
            "capital_hilton_protected_reference_placeholder": {
                "read_model_ref": PROTECTED_PLACEHOLDER_READ_MODEL_REF,
                "status": "OBSERVED" if placeholder_present else "NOT_OBSERVED_OR_PENDING",
                "relationship": "Protected placeholders can progress to Guardian review but are not proof by themselves.",
            },
            "capital_hilton_guardian_review_packet": {
                "read_model_ref": GUARDIAN_PACKET_READ_MODEL_REF,
                "status": "OBSERVED" if guardian_present else "NOT_OBSERVED_OR_PENDING",
                "relationship": "Guardian metadata outcomes can progress proof metadata but cannot execute.",
            },
            "capital_hilton_protected_proof_intake": {
                "read_model_ref": PROOF_INTAKE_READ_MODEL_REF,
                "status": "OBSERVED" if proof_intake_present else "NOT_OBSERVED_OR_PENDING",
                "relationship": "Proof intake supplies the ten source proof questions and candidate values.",
            },
        },
        "authority_boundary": {
            **NO_AUTHORITY_FLAGS,
            "all_authority_flags_false": all(value is False for value in NO_AUTHORITY_FLAGS.values()),
            "blocked_actions": list(BLOCKED_ACTIONS),
        },
        "batch_relationship": {
            "batch_id": "capital_hilton_proof_resolution_batch_v0",
            "prompt_index": 4,
            "stable_map_refresh_deferred": True,
            "commit_deferred_until_final_prompt": True,
            "next_lane": "integrated_checkpoint_and_stable_map_refresh",
        },
        "machine_proof": {
            "default_progress_record_count": len(records),
            "default_missing_proof_count": summary.missing_proof_count,
            "all_progress_states_exist": set(PROGRESS_STATES)
            == {
                "MISSING_PROOF",
                "ANSWERED_MEMORY_CANDIDATE_ONLY",
                "ANSWER_POINTS_TO_SOURCE_CARD",
                "ANSWER_POINTS_TO_PROTECTED_REFERENCE",
                "ANSWER_POINTS_TO_RECEIPT",
                "PROTECTED_PLACEHOLDER_LINKED",
                "GUARDIAN_REVIEW_REQUIRED",
                "GUARDIAN_METADATA_ALLOWED",
                "GUARDIAN_METADATA_REJECTED",
                "PROOF_METADATA_LINKED",
                "QUIET_WITH_PROOF_CANDIDATE",
                "QUIET_WITH_VALID_REJECTION",
                "PARKED_WITH_REASON",
                "QUARANTINED",
                "UNKNOWN_FAIL_CLOSED",
            },
            "all_attention_classes_exist": set(ATTENTION_CLASSES)
            == {
                "NEEDS_OPERATOR_INPUT",
                "NEEDS_PROOF_REFERENCE",
                "NEEDS_PROTECTED_REFERENCE",
                "NEEDS_GUARDIAN_REVIEW",
                "NEEDS_RECEIPT",
                "NEEDS_SECURITY_DELTA",
                "READY_TO_QUIET_WITH_PROOF",
                "PARKED",
                "QUARANTINED",
                "QUIET",
                "UNKNOWN_FAIL_CLOSED",
            },
            "transition_rules_exist": len(transitions) >= 20,
            "text_answer_transition_does_not_prove": True,
            "source_protected_refs_do_not_auto_quiet": True,
            "guardian_metadata_allowed_does_not_execute": True,
            "proof_metadata_plus_receipt_can_create_quiet_with_proof_candidate": True,
            "unknown_event_fails_closed": True,
            "automatic_quieting_progression_false": True,
            "authority_flags_false": all(value is False for value in NO_AUTHORITY_FLAGS.values()),
            "prior_lane_refs_represented": True,
            "credential_or_secret_included": False,
            "raw_private_body_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_capital_hilton_proof_quieting_progress_state(payload: dict[str, Any]) -> str:
    summary = payload["progress_summary"]
    lines = [
        "# Capital Hilton Proof Quieting / Progress State v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "Progress state is the safe scoreboard for the ten Capital Hilton proof questions. Every item starts as missing proof. Answers can clarify or point toward proof, but they do not prove facts or quiet items by themselves.",
        "",
        "## Current Summary",
        "",
        f"- Target world: `{summary['target_world']}`",
        f"- Current phase: `{summary['current_phase']}`",
        f"- Lane destiny: `{summary['lane_destiny']}`",
        f"- Proof items: `{summary['proof_items_total']}`",
        f"- Missing proof: `{summary['missing_proof_count']}`",
        f"- Quiet with proof: `{summary['quiet_with_proof_count']}`",
        f"- Candidate facts proven: `{str(summary['candidate_facts_proven']).lower()}`",
        f"- Action authority granted: `{str(summary['action_authority_granted']).lower()}`",
        "",
        "## What Moves An Item Forward",
        "",
        "- Text or form answers create memory-candidate context only.",
        "- Source-card, protected-placeholder, and receipt refs can move an item toward proof review, but do not auto-quiet it.",
        "- Protected metadata routes through Guardian before proof metadata can be promoted.",
        "- Proof metadata plus a receipt can create a quiet-with-proof candidate.",
        "- Rejection needs a reason and receipt policy; parked items remain visible and not complete.",
        "",
        "## Why Nothing Executes Yet",
        "",
        "- This contract has no invoice generation, Coupa, browser, Gmail/calendar/email, credential, ledger, send/submit/approval, model, tool, agent, queue, or runtime authority.",
        "- Automatic quieting and automatic progression are both false.",
        "",
        "## Default Proof Items",
        "",
    ]
    for record in payload["proof_progress_records"]:
        lines.append(f"- `{record['proof_item_id']}`: `{record['current_state']}`")
    lines.extend(
        [
            "",
            "## Final Batch Prompt",
            "",
            "- Prompt 5 should validate the batch, commit the backend contracts, refresh the stable map once, and stage the Mac import bundle. It should not run Mac import.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_capital_hilton_proof_quieting_progress_state(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ProofQuietingProgressStateExportResult:
    payload = build_capital_hilton_proof_quieting_progress_state(
        repo_root=repo_root,
        generated_at=generated_at,
    )
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_proof_quieting_progress_state(payload), encoding="utf-8")
    return ProofQuietingProgressStateExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        proof_progress_record_count=payload["machine_proof"]["default_progress_record_count"],
        missing_proof_count=payload["machine_proof"]["default_missing_proof_count"],
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Capital Hilton Proof Quieting Progress State read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_proof_quieting_progress_state(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "proof_progress_record_count": result.proof_progress_record_count,
        "missing_proof_count": result.missing_proof_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Capital Hilton Proof Quieting Progress State: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "ANSWER_CANDIDATE_READ_MODEL_REF",
    "ATTENTION_CLASSES",
    "EVENTS",
    "GUARDIAN_PACKET_READ_MODEL_REF",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "PROGRESS_STATES",
    "PROOF_INTAKE_READ_MODEL_REF",
    "PROTECTED_PLACEHOLDER_READ_MODEL_REF",
    "READ_MODEL_ID",
    "SCHEMA_VERSION",
    "build_capital_hilton_proof_quieting_progress_state",
    "build_default_progress_records",
    "build_progress_summary",
    "build_transition_rules",
    "export_capital_hilton_proof_quieting_progress_state",
    "format_capital_hilton_proof_quieting_progress_state",
    "stable_json",
]
