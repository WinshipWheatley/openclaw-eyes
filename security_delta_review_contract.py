"""Security Delta Review Contract v0.

This read-model defines how future additions are checked against the existing
Security Pass baseline. It does not rerun the full pass, grant live authority,
execute changes, launch tools/models/agents, create queues, mutate app/backend
state, promote stable-map state, activate detected capabilities, or perform any
external account/network action.
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

SCHEMA_VERSION = "security_delta_review_contract_v0"
READ_MODEL_ID = "security_delta_review_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

SECURITY_DELTA_CLASSES = (
    "NO_DELTA_REQUIRED",
    "READ_ONLY_DELTA",
    "PREVIEW_SURFACE_DELTA",
    "METADATA_ONLY_DELTA",
    "PACKAGE_PREVIEW_DELTA",
    "MEMORY_CANDIDATE_DELTA",
    "OPERATOR_CAPTURE_DELTA",
    "WORLD_PREVIEW_DELTA",
    "STABLE_MAP_SURFACE_DELTA",
    "TOOL_ADAPTER_DELTA",
    "MODEL_ROUTING_DELTA",
    "ACCOUNT_ACCESS_DELTA",
    "SEND_SUBMIT_APPROVAL_DELTA",
    "QUEUE_AUTONOMY_DELTA",
    "RUNTIME_EXECUTION_DELTA",
    "EXTERNAL_DEPENDENCY_DELTA",
    "FINANCIAL_AUTHORITY_DELTA",
    "SECURITY_REPASS_REQUIRED",
    "UNKNOWN_FAIL_CLOSED",
)

DECISION_OUTCOMES = (
    "ALLOWED_UNDER_EXISTING_SECURITY_CLASS",
    "ALLOWED_READ_ONLY",
    "ALLOWED_PREVIEW_ONLY",
    "ALLOWED_METADATA_ONLY",
    "ALLOWED_CAPTURE_ONLY",
    "REQUIRES_OPERATOR_APPROVAL",
    "REQUIRES_GUARDIAN_GATE",
    "REQUIRES_HERMES_REVIEW",
    "REQUIRES_CHIEF_RECONCILIATION",
    "REQUIRES_SECURITY_DELTA_REVIEW",
    "REQUIRES_SECURITY_REPASS",
    "FUTURE_GATED",
    "BLOCKED_AUTHORITY",
    "BLOCKED_SENSITIVE",
    "BLOCKED_CREDENTIAL",
    "BLOCKED_ACCOUNT",
    "BLOCKED_NETWORK",
    "BLOCKED_EXECUTION",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_RECORD_FIELDS = (
    "delta_id",
    "item_name",
    "source_ref",
    "change_type",
    "affected_surface",
    "affected_world",
    "affected_actor",
    "affected_package_type",
    "affected_tool_adapter",
    "risk_class",
    "matches_existing_security_class",
    "required_review_type",
    "guardian_gate_required",
    "operator_approval_required",
    "hermes_review_recommended",
    "chief_reconciliation_recommended",
    "stable_map_update_required",
    "app_surface_update_required",
    "authority_change_requested",
    "authority_change_allowed",
    "decision",
    "blocked_actions",
    "future_gated_actions",
    "proof_requirements",
    "receipt_requirements",
    "next_safe_move",
)

NO_LIVE_AUTHORITY_FLAGS = {
    "live_execution_allowed": False,
    "model_api_execution_allowed": False,
    "actor_agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_autonomy_execution_allowed": False,
    "runtime_execution_allowed": False,
    "browser_oauth_account_access_allowed": False,
    "gmail_calendar_coupa_telegram_access_allowed": False,
    "financial_payment_account_access_allowed": False,
    "credential_handling_allowed": False,
    "send_submit_approval_allowed": False,
    "invoice_generation_allowed": False,
    "ledger_write_allowed": False,
    "email_dispatch_allowed": False,
    "network_operation_allowed": False,
    "stable_map_auto_promotion_allowed": False,
    "detected_capability_auto_activation_allowed": False,
    "app_backend_mutation_allowed": False,
}

COMMON_BLOCKED_ACTIONS = (
    "live execution",
    "tool execution",
    "model/API execution",
    "agent activation",
    "queue/autonomy execution",
    "account access",
    "credential handling",
    "network operation",
    "send/submit/approval",
    "automatic stable-map promotion",
)


@dataclass(frozen=True)
class SecurityDeltaReviewRecord:
    delta_id: str
    item_name: str
    source_ref: str
    change_type: str
    affected_surface: str
    affected_world: str
    affected_actor: str
    affected_package_type: str
    affected_tool_adapter: str
    risk_class: str
    matches_existing_security_class: bool
    required_review_type: str
    guardian_gate_required: bool
    operator_approval_required: bool
    hermes_review_recommended: bool
    chief_reconciliation_recommended: bool
    stable_map_update_required: bool
    app_surface_update_required: bool
    authority_change_requested: bool
    authority_change_allowed: bool
    decision: str
    blocked_actions: tuple[str, ...]
    future_gated_actions: tuple[str, ...]
    proof_requirements: tuple[str, ...]
    receipt_requirements: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class SecurityDeltaExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    delta_class_count: int
    decision_outcome_count: int
    default_example_count: int
    action_authority_granted: bool
    security_repass_examples_count: int


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _generated_at(value: str | None) -> str:
    return value or datetime.now(timezone.utc).isoformat(timespec="seconds")


def _record(
    delta_id: str,
    *,
    item_name: str,
    change_type: str,
    affected_surface: str,
    risk_class: str,
    decision: str,
    required_review_type: str,
    matches_existing_security_class: bool,
    blocked_actions: tuple[str, ...],
    next_safe_move: str,
    source_ref: str = "post_security_governance_batch_v0",
    affected_world: str = "none",
    affected_actor: str = "none",
    affected_package_type: str = "none",
    affected_tool_adapter: str = "none",
    guardian_gate_required: bool = False,
    operator_approval_required: bool = False,
    hermes_review_recommended: bool = False,
    chief_reconciliation_recommended: bool = False,
    stable_map_update_required: bool = False,
    app_surface_update_required: bool = False,
    authority_change_requested: bool = False,
    authority_change_allowed: bool = False,
    future_gated_actions: tuple[str, ...] = (),
    proof_requirements: tuple[str, ...] = (),
    receipt_requirements: tuple[str, ...] = (),
) -> SecurityDeltaReviewRecord:
    return SecurityDeltaReviewRecord(
        delta_id=delta_id,
        item_name=item_name,
        source_ref=source_ref,
        change_type=change_type,
        affected_surface=affected_surface,
        affected_world=affected_world,
        affected_actor=affected_actor,
        affected_package_type=affected_package_type,
        affected_tool_adapter=affected_tool_adapter,
        risk_class=risk_class,
        matches_existing_security_class=matches_existing_security_class,
        required_review_type=required_review_type,
        guardian_gate_required=guardian_gate_required,
        operator_approval_required=operator_approval_required,
        hermes_review_recommended=hermes_review_recommended,
        chief_reconciliation_recommended=chief_reconciliation_recommended,
        stable_map_update_required=stable_map_update_required,
        app_surface_update_required=app_surface_update_required,
        authority_change_requested=authority_change_requested,
        authority_change_allowed=authority_change_allowed,
        decision=decision,
        blocked_actions=blocked_actions,
        future_gated_actions=future_gated_actions,
        proof_requirements=proof_requirements,
        receipt_requirements=receipt_requirements,
        next_safe_move=next_safe_move,
    )


def default_security_delta_review_records() -> tuple[SecurityDeltaReviewRecord, ...]:
    return (
        _record(
            "new_read_only_mission_control_card",
            item_name="New Read-Only Mission Control Card",
            change_type="READ_ONLY_DELTA",
            affected_surface="Mission Control card",
            risk_class="LOW",
            decision="ALLOWED_READ_ONLY",
            required_review_type="existing_security_class",
            matches_existing_security_class=True,
            app_surface_update_required=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            proof_requirements=("stable-map source section already exists",),
            receipt_requirements=("app change receipt in later UI lane",),
            next_safe_move="Allow as read-only UI work in a later Mac lane with no execution controls.",
        ),
        _record(
            "new_preview_surface_from_stable_map",
            item_name="New Preview Surface From Stable Map",
            change_type="PREVIEW_SURFACE_DELTA",
            affected_surface="stable-map preview surface",
            risk_class="LOW",
            decision="ALLOWED_PREVIEW_ONLY",
            required_review_type="existing_security_class",
            matches_existing_security_class=True,
            app_surface_update_required=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS + ("direct packet dependency", "live controls"),
            proof_requirements=("stable-map summary exists",),
            receipt_requirements=("preview surface receipt in later UI lane",),
            next_safe_move="Use stable-map data only; do not add direct packet dependency or live controls.",
        ),
        _record(
            "new_package_preview_type",
            item_name="New Package Preview Type",
            change_type="PACKAGE_PREVIEW_DELTA",
            affected_surface="package preview",
            affected_package_type="new_preview_class",
            risk_class="MEDIUM",
            decision="REQUIRES_SECURITY_DELTA_REVIEW",
            required_review_type="security_delta_review",
            matches_existing_security_class=False,
            chief_reconciliation_recommended=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS + ("package dispatch",),
            proof_requirements=("package preview schema", "receipt requirements", "blocked authority list"),
            receipt_requirements=("package preview receipt contract update",),
            next_safe_move="Run bounded delta review before surfacing the new preview type.",
        ),
        _record(
            "new_memory_candidate_capture_surface",
            item_name="New Memory Candidate Capture Surface",
            change_type="MEMORY_CANDIDATE_DELTA",
            affected_surface="operator memory candidate capture",
            risk_class="MEDIUM",
            decision="ALLOWED_CAPTURE_ONLY",
            required_review_type="existing_capture_class_with_delta_check",
            matches_existing_security_class=True,
            operator_approval_required=True,
            app_surface_update_required=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS + ("operator answers as proof", "automatic promotion"),
            proof_requirements=("memory candidate receipt schema",),
            receipt_requirements=("memory candidate receipt",),
            next_safe_move="Capture as memory candidate only; never treat operator answer as proof.",
        ),
        _record(
            "new_operator_answer_popup",
            item_name="New Operator Answer Popup",
            change_type="OPERATOR_CAPTURE_DELTA",
            affected_surface="structured answer capture",
            risk_class="MEDIUM",
            decision="REQUIRES_SECURITY_DELTA_REVIEW",
            required_review_type="security_delta_review",
            matches_existing_security_class=False,
            operator_approval_required=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS + ("send/submit/approval", "proof by statement alone"),
            proof_requirements=("question schema", "quieting rules", "proof still required label"),
            receipt_requirements=("memory candidate receipt",),
            next_safe_move="Review capture semantics before UI implementation; answers remain non-proof.",
        ),
        _record(
            "new_markdown_visibility_surface",
            item_name="New Markdown Visibility Surface",
            change_type="METADATA_ONLY_DELTA",
            affected_surface="Markdown Atlas metadata panel",
            risk_class="LOW",
            decision="ALLOWED_METADATA_ONLY",
            required_review_type="existing_metadata_class",
            matches_existing_security_class=True,
            app_surface_update_required=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS + ("broad body ingestion", "file moves", "stale doctrine promotion"),
            proof_requirements=("Markdown Atlas metadata readback",),
            receipt_requirements=("metadata-only visibility receipt",),
            next_safe_move="Surface metadata only; do not inspect broad bodies or move files.",
        ),
        _record(
            "new_browser_oauth_coupa_adapter",
            item_name="New Browser/OAuth/Coupa Adapter",
            change_type="ACCOUNT_ACCESS_DELTA",
            affected_surface="account adapter",
            affected_world="Finance",
            affected_tool_adapter="browser_oauth_coupa",
            risk_class="HIGH",
            decision="REQUIRES_SECURITY_REPASS",
            required_review_type="security_repass",
            matches_existing_security_class=False,
            guardian_gate_required=True,
            operator_approval_required=True,
            authority_change_requested=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS + ("browser/OAuth/account authority", "credential handling", "Coupa access"),
            future_gated_actions=("protected account broker", "credential policy", "Guardian approval"),
            proof_requirements=("account access policy", "credential handling policy", "protected access broker"),
            receipt_requirements=("security repass receipt",),
            next_safe_move="Keep blocked until a future security repass explicitly defines account authority.",
        ),
        _record(
            "new_gmail_calendar_adapter",
            item_name="New Gmail/Calendar Adapter",
            change_type="ACCOUNT_ACCESS_DELTA",
            affected_surface="communication account adapter",
            affected_tool_adapter="gmail_calendar",
            risk_class="HIGH",
            decision="REQUIRES_SECURITY_REPASS",
            required_review_type="security_repass",
            matches_existing_security_class=False,
            guardian_gate_required=True,
            operator_approval_required=True,
            authority_change_requested=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS + ("raw body access", "send/mutation authority", "account access"),
            future_gated_actions=("account access policy", "raw body redaction", "send approval gate"),
            proof_requirements=("email/calendar data policy", "send/submit approval boundary"),
            receipt_requirements=("security repass receipt",),
            next_safe_move="Keep blocked until security repass defines account and send boundaries.",
        ),
        _record(
            "new_invoice_generation_or_ledger_write",
            item_name="New Invoice Generation Or Ledger Write",
            change_type="FINANCIAL_AUTHORITY_DELTA",
            affected_surface="Finance action tool",
            affected_world="Finance",
            affected_tool_adapter="invoice_ledger",
            risk_class="HIGH",
            decision="REQUIRES_SECURITY_REPASS",
            required_review_type="security_repass",
            matches_existing_security_class=False,
            guardian_gate_required=True,
            operator_approval_required=True,
            authority_change_requested=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS + ("invoice generation", "ledger write", "financial movement"),
            future_gated_actions=("invoice calculator", "idempotency receipt", "ledger readback receipt"),
            proof_requirements=("financial authority policy", "invoice math contract", "ledger write adapter receipt"),
            receipt_requirements=("security repass receipt",),
            next_safe_move="Keep financial action blocked; model only as future-gated contract work.",
        ),
        _record(
            "new_queue_autonomy_lane",
            item_name="New Queue Autonomy Lane",
            change_type="QUEUE_AUTONOMY_DELTA",
            affected_surface="planner/builder queue",
            risk_class="HIGH",
            decision="REQUIRES_SECURITY_REPASS",
            required_review_type="security_repass",
            matches_existing_security_class=False,
            guardian_gate_required=True,
            operator_approval_required=True,
            authority_change_requested=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS + ("unattended execution", "planner/builder execution", "automatic queueing"),
            future_gated_actions=("queue doctrine", "conflict locks", "FULL_TRUST_CLEARANCE task class approval"),
            proof_requirements=("queue authority policy", "Chief verification path", "rollback/recovery rules"),
            receipt_requirements=("security repass receipt",),
            next_safe_move="Keep parked until queue/autonomy authority is explicitly defined by repass.",
        ),
        _record(
            "new_runtime_agent_activation",
            item_name="New Runtime Agent Activation",
            change_type="RUNTIME_EXECUTION_DELTA",
            affected_surface="live actor runtime",
            affected_actor="Chief/Cassandra/Niles",
            risk_class="HIGH",
            decision="REQUIRES_SECURITY_REPASS",
            required_review_type="security_repass",
            matches_existing_security_class=False,
            guardian_gate_required=True,
            operator_approval_required=True,
            authority_change_requested=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS + ("live agent activation", "self-authority", "runtime dispatch"),
            future_gated_actions=("actor runtime policy", "model routing policy", "tool posture policy"),
            proof_requirements=("actor authority contract", "model/tool boundary receipt"),
            receipt_requirements=("security repass receipt",),
            next_safe_move="Keep runtime activation blocked until repass defines actor authority.",
        ),
        _record(
            "external_open_source_dependency_recommendation",
            item_name="External Open-Source Dependency Recommendation",
            change_type="EXTERNAL_DEPENDENCY_DELTA",
            affected_surface="Hermes architecture recommendation",
            risk_class="MEDIUM",
            decision="REQUIRES_HERMES_REVIEW",
            required_review_type="hermes_review_then_operator_approval",
            matches_existing_security_class=False,
            hermes_review_recommended=True,
            operator_approval_required=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS + ("dependency adoption", "network/API use", "credential use"),
            future_gated_actions=("license review", "security review", "privacy/data-flow review", "operator approval"),
            proof_requirements=("source trust review", "license review", "maintenance/activity review", "local compatibility review"),
            receipt_requirements=("Hermes recommendation receipt", "operator approval receipt before adoption"),
            next_safe_move="Treat as advisory only; do not adopt or fetch external dependency in this lane.",
        ),
        _record(
            "new_stable_map_summary_only",
            item_name="New Stable Map Summary Only",
            change_type="STABLE_MAP_SURFACE_DELTA",
            affected_surface="stable map summary",
            risk_class="LOW",
            decision="ALLOWED_UNDER_EXISTING_SECURITY_CLASS",
            required_review_type="existing_stable_map_surface_class",
            matches_existing_security_class=True,
            stable_map_update_required=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS + ("stable map as source truth", "app execution authority"),
            proof_requirements=("source read-model ref", "operator digest ref", "not source truth label"),
            receipt_requirements=("stable map refresh receipt in later lane"),
            next_safe_move="Allow summary-only stable-map inclusion in a later refresh; stable map remains app-facing reflection.",
        ),
        _record(
            "new_world_preview_surface",
            item_name="New World Preview Surface",
            change_type="WORLD_PREVIEW_DELTA",
            affected_surface="world preview",
            affected_world="Music/Art or Finance",
            risk_class="LOW",
            decision="ALLOWED_PREVIEW_ONLY",
            required_review_type="existing_world_preview_class",
            matches_existing_security_class=True,
            app_surface_update_required=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS + ("domain action", "account access", "send/submit/approval"),
            proof_requirements=("stable-map world summary", "blocked action labels"),
            receipt_requirements=("world preview receipt in later UI lane"),
            next_safe_move="Allow read-only world preview; do not add domain actions.",
        ),
    )


def _all_live_authority_false() -> bool:
    return all(value is False for value in NO_LIVE_AUTHORITY_FLAGS.values())


def build_security_delta_review_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    del repo_root
    records = [asdict(item) for item in default_security_delta_review_records()]
    records_by_id = {item["delta_id"]: item for item in records}
    repass_count = sum(1 for item in records if item["decision"] == "REQUIRES_SECURITY_REPASS")
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": "security_delta_review_contract_v0",
        "generated_at": _generated_at(generated_at),
        "contract_status": "DETERMINISTIC_NON_EXECUTING_SECURITY_DELTA_REVIEW",
        "core_doctrine": {
            "full_security_pass_establishes_security_law": True,
            "security_delta_review_checks_new_item_against_that_law": True,
            "security_repass_required_only_when_law_or_major_authority_boundary_changes": True,
            "security_delta_review_grants_live_authority": False,
            "stable_map_is_source_truth": False,
            "stable_map_is_app_facing_reflection": True,
        },
        "security_delta_classes": list(SECURITY_DELTA_CLASSES),
        "decision_outcomes": list(DECISION_OUTCOMES),
        "security_delta_review_record_schema": {
            "structure": "SecurityDeltaReviewRecord",
            "required_fields": list(REQUIRED_RECORD_FIELDS),
            "unknown_or_missing_decision_result": "UNKNOWN_FAIL_CLOSED",
        },
        "authority_boundary": dict(NO_LIVE_AUTHORITY_FLAGS),
        "allowed_recommendations": [
            "allowed under existing class",
            "requires Guardian gate",
            "requires Operator approval",
            "requires Hermes review",
            "requires Chief reconciliation",
            "future-gated",
            "blocked",
            "security repass required",
        ],
        "must_not": [
            "execute changes",
            "grant live authority",
            "launch tools/models/agents",
            "create queues",
            "mutate app/backend",
            "promote stable-map state automatically",
            "activate detected capabilities",
            "perform external account/network actions",
        ],
        "default_examples": records,
        "default_examples_by_id": records_by_id,
        "operator_answer_rule": {
            "operator_answers_become": "MEMORY_CANDIDATE_RECEIPT",
            "operator_answers_are_proof": False,
            "automatic_truth_promotion_allowed": False,
        },
        "stable_map_rule": {
            "summary_deltas_allowed_under_existing_security_class": True,
            "stable_map_is_source_truth": False,
            "stable_map_auto_promotion_allowed": False,
            "source_read_model_ref_required": True,
            "receipt_ref_required_for_refresh": True,
        },
        "machine_proof": {
            "all_delta_classes_present": set(SECURITY_DELTA_CLASSES)
            == {
                "NO_DELTA_REQUIRED",
                "READ_ONLY_DELTA",
                "PREVIEW_SURFACE_DELTA",
                "METADATA_ONLY_DELTA",
                "PACKAGE_PREVIEW_DELTA",
                "MEMORY_CANDIDATE_DELTA",
                "OPERATOR_CAPTURE_DELTA",
                "WORLD_PREVIEW_DELTA",
                "STABLE_MAP_SURFACE_DELTA",
                "TOOL_ADAPTER_DELTA",
                "MODEL_ROUTING_DELTA",
                "ACCOUNT_ACCESS_DELTA",
                "SEND_SUBMIT_APPROVAL_DELTA",
                "QUEUE_AUTONOMY_DELTA",
                "RUNTIME_EXECUTION_DELTA",
                "EXTERNAL_DEPENDENCY_DELTA",
                "FINANCIAL_AUTHORITY_DELTA",
                "SECURITY_REPASS_REQUIRED",
                "UNKNOWN_FAIL_CLOSED",
            },
            "all_decision_outcomes_present": set(DECISION_OUTCOMES)
            == {
                "ALLOWED_UNDER_EXISTING_SECURITY_CLASS",
                "ALLOWED_READ_ONLY",
                "ALLOWED_PREVIEW_ONLY",
                "ALLOWED_METADATA_ONLY",
                "ALLOWED_CAPTURE_ONLY",
                "REQUIRES_OPERATOR_APPROVAL",
                "REQUIRES_GUARDIAN_GATE",
                "REQUIRES_HERMES_REVIEW",
                "REQUIRES_CHIEF_RECONCILIATION",
                "REQUIRES_SECURITY_DELTA_REVIEW",
                "REQUIRES_SECURITY_REPASS",
                "FUTURE_GATED",
                "BLOCKED_AUTHORITY",
                "BLOCKED_SENSITIVE",
                "BLOCKED_CREDENTIAL",
                "BLOCKED_ACCOUNT",
                "BLOCKED_NETWORK",
                "BLOCKED_EXECUTION",
                "UNKNOWN_FAIL_CLOSED",
            },
            "default_example_count": len(records),
            "security_repass_examples_count": repass_count,
            "all_live_authority_flags_false": _all_live_authority_false(),
            "action_authority_granted": False,
            "execution_authority_granted": False,
            "auto_promotion_allowed": False,
            "auto_queueing_allowed": False,
            "stable_map_is_source_truth": False,
            "operator_answers_are_not_proof": True,
            "credentials_or_secrets_included": False,
            "raw_private_bodies_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    proof = payload["machine_proof"]
    lines = [
        "# Security Delta Review Contract v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "The full Security Pass is the baseline law. A Security Delta Review is the smaller check for a new item: does it fit an existing approved read-only, preview, metadata, capture, world-preview, or stable-map class, or does it ask for new authority? If it asks for account, financial, runtime, queue, model, tool, send, or credential authority, it needs a repass or stays blocked.",
        "",
        "## Delta Classes",
        "",
    ]
    for delta_class in payload["security_delta_classes"]:
        lines.append(f"- `{delta_class}`")
    lines.extend(["", "## Decision Outcomes", ""])
    for outcome in payload["decision_outcomes"]:
        lines.append(f"- `{outcome}`")
    lines.extend(["", "## Default Examples", ""])
    for record in payload["default_examples"]:
        lines.append(
            f"- `{record['delta_id']}`: `{record['change_type']}` -> `{record['decision']}`. "
            f"Next: {record['next_safe_move']}"
        )
    lines.extend(
        [
            "",
            "## Authority Boundary",
            "",
            "- Delta review can recommend, block, future-gate, or require review.",
            "- Delta review cannot execute, launch, queue, mutate app/backend, promote the stable map automatically, activate detected capabilities, or touch external accounts/network.",
            "- Operator answers remain memory candidates, not proof.",
            "- Stable-map summary deltas remain app-facing reflections, not source truth.",
            "",
            "## Machine Proof",
            "",
            f"- Default example count: `{proof['default_example_count']}`.",
            f"- Security repass examples: `{proof['security_repass_examples_count']}`.",
            f"- All live authority flags false: `{str(proof['all_live_authority_flags_false']).lower()}`.",
            f"- Action authority granted: `{str(proof['action_authority_granted']).lower()}`.",
            f"- Auto-promotion allowed: `{str(proof['auto_promotion_allowed']).lower()}`.",
            f"- Operator answers are not proof: `{str(proof['operator_answers_are_not_proof']).lower()}`.",
            f"- Content hash: `{proof['content_hash']}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_security_delta_review_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> SecurityDeltaExportResult:
    payload = build_security_delta_review_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return SecurityDeltaExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        delta_class_count=len(payload["security_delta_classes"]),
        decision_outcome_count=len(payload["decision_outcomes"]),
        default_example_count=len(payload["default_examples"]),
        action_authority_granted=False,
        security_repass_examples_count=payload["machine_proof"]["security_repass_examples_count"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the Security Delta Review Contract v0 read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_security_delta_review_contract(repo_root=args.repo_root, export_root=args.export_root)
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "delta_class_count": result.delta_class_count,
        "decision_outcome_count": result.decision_outcome_count,
        "default_example_count": result.default_example_count,
        "security_repass_examples_count": result.security_repass_examples_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print("Security Delta Review Contract exported")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "DECISION_OUTCOMES",
    "NO_LIVE_AUTHORITY_FLAGS",
    "READ_MODEL_ID",
    "REQUIRED_RECORD_FIELDS",
    "SCHEMA_VERSION",
    "SECURITY_DELTA_CLASSES",
    "SecurityDeltaReviewRecord",
    "build_security_delta_review_contract",
    "default_security_delta_review_records",
    "export_security_delta_review_contract",
    "format_operator_markdown",
    "stable_json",
]
