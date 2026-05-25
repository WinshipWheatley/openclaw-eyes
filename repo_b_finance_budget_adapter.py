"""Repo B CPA / Budget Tracker Promotion Adapter v0.

This deterministic Repo A read-model evaluates Repo B finance modules and
promotes only a small, safe, local-calculation subset. Repo B's budget tracker
contains useful budget-zone and runner allowance logic, but it is tied to state
and log writes. Repo B's CPA brain contains useful category vocabulary and tax
estimate shapes, but it also contains LLM calls, private baseline details, and
ledger writes. This adapter rebuilds the safe deterministic subset in Repo A
and marks unsafe/private/live portions as reference-only or blocked.

It does not access bank accounts, accounting portals, Gmail, Coupa, browser,
credentials, OAuth, external accounts, private ledger bodies, tax filing,
payment execution, invoice/email send, queues, Repo B runtime services, Mission
Control Swift, Mac sync/import, or git push/pull/fetch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-25T00:00:00+00:00"
REPO_B_ROOT = Path("/home/openclaw_external/openclaw-runtime")

SCHEMA_VERSION = "repo_b_finance_budget_adapter_v0"
READ_MODEL_ID = "repo_b_finance_budget_adapter"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_REPO_B_FINANCE_BUDGET_PROMOTION_ADAPTER"

POSTURES = (
    "PROMOTE_SELECTED_MODULE",
    "WRAP_AS_WORKER",
    "REBUILD_SMALL_SUBSET_IN_REPO_A",
    "REFERENCE_ONLY",
    "UNSAFE_DO_NOT_CONNECT",
    "ALREADY_SUPERSEDED",
    "UNKNOWN_NEEDS_DEEPER_REVIEW",
)

CAPABILITY_TYPES = (
    "SHOW_BUDGET_CALCULATION",
    "EXPENSE_CATEGORY_MAPPING",
    "INVOICE_STATUS_SUMMARY",
    "PAYMENT_TRACKING_SUMMARY",
    "TAX_CATEGORY_HINT",
    "CLIENT_JOB_FINANCE_SUMMARY",
    "REPORT_FORMATTING",
    "UNKNOWN",
)

BLOCKER_TYPES = (
    "BANK_ACCESS_ATTEMPTED",
    "PAYMENT_EXECUTION_ATTEMPTED",
    "TAX_FILING_ATTEMPTED",
    "CREDENTIAL_REQUIRED",
    "RAW_PRIVATE_LEDGER_EXPOSED",
    "PROFESSIONAL_ADVICE_CLAIM",
    "BROAD_FILE_SCAN_ATTEMPTED",
    "EXTERNAL_ACTION_ATTEMPTED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_bank_access_allowed": False,
    "live_payment_execution_allowed": False,
    "live_tax_filing_allowed": False,
    "live_external_account_access_allowed": False,
    "live_invoice_send_allowed": False,
    "live_email_send_allowed": False,
    "live_coupa_access_allowed": False,
    "live_financial_state_mutation_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "external_action_allowed": False,
    "network_allowed": False,
    "repo_b_runtime_execution_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

BUDGET_THRESHOLDS = {
    "green": 0.50,
    "yellow": 0.75,
    "orange": 0.90,
    "red": 1.00,
}

TIER_COSTS = {
    "quick": 0.10,
    "surgical": 0.30,
    "standard": 1.50,
    "architect": 4.00,
}

EXPENSE_CATEGORY_KEYWORDS = {
    "software": ("software", "subscription", "plugin", "daw", "hosting", "cloud", "app"),
    "gear": ("gear", "equipment", "microphone", "instrument", "cable", "interface"),
    "music_services": ("mastering", "mixing", "session musician", "distribution", "ascap", "bmi"),
    "meals": ("meal", "coffee", "lunch", "dinner", "restaurant"),
    "professional": ("course", "book", "training", "conference", "education"),
    "marketing": ("ad", "promo", "merch", "flyer", "marketing"),
    "phone": ("phone", "internet", "wifi", "mobile"),
    "legal": ("legal", "lawyer", "attorney", "contract", "accountant", "cpa"),
    "home_studio": ("studio", "rent", "utilities", "home office", "room"),
    "miles": ("miles", "mileage", "parking", "toll", "gas"),
}

TAX_CATEGORY_HINTS = {
    "software": "Bookkeeping hint: software/subscription expense category. Not tax advice.",
    "gear": "Bookkeeping hint: gear/equipment category; treatment may vary by amount and use. Not tax advice.",
    "music_services": "Bookkeeping hint: music services or production services category. Not tax advice.",
    "meals": "Bookkeeping hint: business meal candidate; confirm business purpose and receipt. Not tax advice.",
    "professional": "Bookkeeping hint: professional development category. Not tax advice.",
    "marketing": "Bookkeeping hint: marketing/promotion category. Not tax advice.",
    "phone": "Bookkeeping hint: phone/internet business-use percentage may matter. Not tax advice.",
    "legal": "Bookkeeping hint: legal/professional fees category. Not tax advice.",
    "home_studio": "Bookkeeping hint: home studio/home office category requires careful substantiation. Not tax advice.",
    "miles": "Bookkeeping hint: mileage/travel log category. Not tax advice.",
    "other": "Bookkeeping hint: uncategorized; operator review required. Not tax advice.",
}


@dataclass(frozen=True)
class RepoBFinanceAdapterDecision:
    decision_id: str
    source_module: str
    source_path: str
    apparent_value: str
    dependencies: tuple[str, ...]
    recommended_posture: str
    promotion_scope: tuple[str, ...]
    wrapper_scope: tuple[str, ...]
    blocked_items: tuple[str, ...]
    privacy_boundary: str
    next_safe_move: str


@dataclass(frozen=True)
class FinanceCalculationCapability:
    capability_id: str
    source_module_ref: str
    capability_type: str
    description: str
    inputs_required: tuple[str, ...]
    outputs_produced: tuple[str, ...]
    deterministic: bool
    external_authority: bool
    credential_required: bool
    raw_private_data_required: bool
    promotion_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class PromotedFinanceAdapterPlan:
    plan_id: str
    selected_capabilities: tuple[str, ...]
    excluded_capabilities: tuple[str, ...]
    target_repo_a_module: str
    test_strategy: tuple[str, ...]
    fixture_strategy: tuple[str, ...]
    privacy_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class FinanceAdapterReadback:
    readback_id: str
    posture: str
    safe_capabilities: tuple[str, ...]
    blocked_capabilities: tuple[str, ...]
    recommended_next_lane: str
    operator_summary: str
    next_safe_move: str


@dataclass(frozen=True)
class FinanceAdapterBlocker:
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


def _repo_b_path(filename: str) -> str:
    return str(REPO_B_ROOT / filename)


def budget_zone(spent: float, cap: float) -> str:
    """Pure rebuild of Repo B budget-zone threshold logic."""
    if cap <= 0:
        return "red"
    pct = max(spent, 0) / cap
    zone = "green"
    for name, threshold in sorted(BUDGET_THRESHOLDS.items(), key=lambda item: item[1]):
        if pct >= threshold:
            zone = name
    return zone


def budget_snapshot(spent_by_runner: dict[str, float], caps: dict[str, float], global_cap: float) -> dict[str, Any]:
    """Build a safe fixture budget snapshot without reading Repo B state files."""
    per_runner: dict[str, dict[str, float]] = {}
    for runner, cap in caps.items():
        spent = round(float(spent_by_runner.get(runner, 0)), 4)
        per_runner[runner] = {
            "spent": spent,
            "cap": float(cap),
            "remaining": round(max(0.0, float(cap) - spent), 4),
            "pct": round(spent / float(cap), 4) if cap else 1.0,
        }
    global_spent = round(sum(float(value) for value in spent_by_runner.values()), 4)
    return {
        "per_runner": per_runner,
        "global_spent": global_spent,
        "global_cap": float(global_cap),
        "global_remaining": round(max(0.0, float(global_cap) - global_spent), 4),
        "global_pct": round(global_spent / float(global_cap), 4) if global_cap else 1.0,
        "budget_zone": budget_zone(global_spent, float(global_cap)),
    }


def runner_allowance(snapshot: dict[str, Any], runner: str, model: str, tier: str, *, stuck_loop_count: int = 0) -> dict[str, Any]:
    """Pure runner allowance calculation adapted from Repo B budget tracker."""
    zone = snapshot["budget_zone"]
    remaining_runner = snapshot.get("per_runner", {}).get(runner, {}).get("remaining", 0)
    remaining_global = snapshot.get("global_remaining", 0)
    remaining = min(float(remaining_runner), float(remaining_global))
    estimated = TIER_COSTS.get(tier, TIER_COSTS["standard"])
    if stuck_loop_count >= 3 and runner != "ollama":
        return {
            "allowed": False,
            "max_budget": 0.0,
            "reason": "Stuck-loop safety valve: use local/free runner.",
            "alternative": {"runner": "ollama", "model": "qwen2.5-coder:14b"},
        }
    if zone == "red" and estimated > remaining:
        return {
            "allowed": False,
            "max_budget": 0.0,
            "reason": "Budget red zone: defer or use local/free runner.",
            "alternative": {"runner": "ollama", "model": "qwen2.5-coder:7b"},
        }
    if zone == "orange" and model == "opus" and tier != "architect":
        return {
            "allowed": False,
            "max_budget": 0.0,
            "reason": "Budget orange zone: reserve expensive model for architect tier only.",
            "alternative": {"runner": runner, "model": "sonnet"},
        }
    multiplier = 0.15 if zone == "yellow" and model == "opus" and tier in {"quick", "surgical"} else 0.4
    if zone in {"yellow", "orange", "red"}:
        max_budget = min(max(0.0, remaining * multiplier), estimated * 1.2)
    else:
        max_budget = estimated * 1.5
    return {
        "allowed": True,
        "max_budget": round(max_budget, 2),
        "reason": f"Budget {zone} zone with local fixture numbers.",
    }


def map_expense_category(description: str) -> dict[str, Any]:
    """Small deterministic expense category mapper; no cloud/model calls."""
    text = description.lower()
    for category, keywords in EXPENSE_CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return {
                "category": category,
                "confidence": "medium",
                "source": "repo_a_rebuilt_keyword_mapping",
                "operator_review_required": True,
            }
    return {
        "category": "other",
        "confidence": "low",
        "source": "repo_a_rebuilt_keyword_mapping",
        "operator_review_required": True,
    }


def tax_category_hint(category: str) -> dict[str, Any]:
    normalized = category if category in TAX_CATEGORY_HINTS else "other"
    return {
        "category": normalized,
        "hint": TAX_CATEGORY_HINTS[normalized],
        "professional_advice": False,
        "filing_authority": False,
        "operator_review_required": True,
    }


def capital_hilton_invoice_summary() -> dict[str, Any]:
    return {
        "summary_id": "capital_hilton_invoice_summary_fixture_v0",
        "client_ref": "capital_hilton",
        "known_basis": {
            "performance_date_count": 4,
            "rate_per_date": 400,
            "subtotal": 1600,
            "basis_status": "draft_readback_context_not_completion_truth",
        },
        "payment_tracking_summary": {
            "coupa_po_reference_status": "missing_or_unconfirmed",
            "payment_state": "not_verified",
            "send_or_submit_status": "not_performed",
        },
        "next_safe_move": "Confirm PO/reference, artifact hash, approval, and send/submit receipts before any completion claim.",
    }


def unsafe_action_blocker(action: str) -> FinanceAdapterBlocker:
    lowered = action.lower()
    if "bank" in lowered:
        blocker_type = "BANK_ACCESS_ATTEMPTED"
    elif "payment" in lowered or "pay " in lowered:
        blocker_type = "PAYMENT_EXECUTION_ATTEMPTED"
    elif "tax" in lowered or "file" in lowered:
        blocker_type = "TAX_FILING_ATTEMPTED"
    else:
        blocker_type = "EXTERNAL_ACTION_ATTEMPTED"
    return FinanceAdapterBlocker(
        blocker_id=f"finance_adapter_blocker_{blocker_type.lower()}",
        blocker_type=blocker_type,
        condition=action,
        severity="critical",
        elioperator_warning=f"Blocked unsafe finance action: {action}.",
        fail_closed=True,
        next_safe_move="Keep this lane to local calculations and request a separately approved adapter before any external finance action.",
    )


def build_decisions() -> tuple[RepoBFinanceAdapterDecision, ...]:
    return (
        RepoBFinanceAdapterDecision(
            decision_id="repo_b_finance_decision_budget_tracker",
            source_module="budget_tracker.py",
            source_path=_repo_b_path("budget_tracker.py"),
            apparent_value="Budget-zone thresholds, runner allowance, partial completion strategy, stuck-loop cost safety.",
            dependencies=("json", "local state file", "local spend log", "runner_profiles.py consumer"),
            recommended_posture="REBUILD_SMALL_SUBSET_IN_REPO_A",
            promotion_scope=("budget_zone", "budget_snapshot", "runner_allowance", "fixture-only examples"),
            wrapper_scope=("none in v0", "future compute-only bridge may read sanitized budget receipts if approved"),
            blocked_items=("Repo B state writes", "Repo B spend log writes", "reset/update cap CLI mutation"),
            privacy_boundary="No Repo B budget state file or spend log is read by this adapter.",
            next_safe_move="Use the rebuilt pure functions for safe fixture calculations and add a governed Repo A ledger rail later if needed.",
        ),
        RepoBFinanceAdapterDecision(
            decision_id="repo_b_finance_decision_chief_cpa_brain",
            source_module="chief_cpa_brain.py",
            source_path=_repo_b_path("chief_cpa_brain.py"),
            apparent_value="Expense category vocabulary, income/payment summary shape, quarterly estimate shape, CPA log formatting ideas.",
            dependencies=("chief_llm.py", "billing csv", "expense log json", "CPA markdown log", "private baseline tax context"),
            recommended_posture="REFERENCE_ONLY",
            promotion_scope=("expense category vocabulary", "tax category hint language", "safe invoice/payment summary shape"),
            wrapper_scope=("none in v0", "future compute-only wrapper only after raw ledger body boundary exists"),
            blocked_items=("LLM/cloud formatting", "private baseline tax details", "ledger writes", "tax advisor persona", "raw billing/expense body exposure"),
            privacy_boundary="This adapter does not copy private tax baseline values or ledger rows into generated outputs.",
            next_safe_move="Rebuild small deterministic category and summary helpers in Repo A; keep full CPA brain reference-only.",
        ),
    )


def build_capabilities() -> tuple[FinanceCalculationCapability, ...]:
    return (
        FinanceCalculationCapability(
            capability_id="finance_capability_show_budget_calculation",
            source_module_ref="repo_b_finance_decision_budget_tracker",
            capability_type="SHOW_BUDGET_CALCULATION",
            description="Calculate budget zone, remaining budget, and runner allowance from provided fixture numbers.",
            inputs_required=("spent_by_runner", "caps", "global_cap", "runner", "model", "tier"),
            outputs_produced=("budget_zone", "remaining", "allowance", "alternative"),
            deterministic=True,
            external_authority=False,
            credential_required=False,
            raw_private_data_required=False,
            promotion_allowed=True,
            next_safe_move="Use fixture/test inputs only until a Repo A budget receipt source is approved.",
        ),
        FinanceCalculationCapability(
            capability_id="finance_capability_expense_category_mapping",
            source_module_ref="repo_b_finance_decision_chief_cpa_brain",
            capability_type="EXPENSE_CATEGORY_MAPPING",
            description="Map short expense descriptions to bookkeeping categories with operator review.",
            inputs_required=("safe_expense_description_summary",),
            outputs_produced=("category_hint", "confidence", "operator_review_required"),
            deterministic=True,
            external_authority=False,
            credential_required=False,
            raw_private_data_required=False,
            promotion_allowed=True,
            next_safe_move="Use safe summaries, not raw receipts or ledger bodies.",
        ),
        FinanceCalculationCapability(
            capability_id="finance_capability_capital_hilton_invoice_summary",
            source_module_ref="repo_a_capital_hilton_readbacks",
            capability_type="INVOICE_STATUS_SUMMARY",
            description="Summarize known Capital Hilton dates/rate/subtotal and missing payment/send proof from Repo A readbacks.",
            inputs_required=("workflow_readback_ref", "delivery_fact_refs", "proof_refs"),
            outputs_produced=("known_basis", "payment_state", "missing_proofs"),
            deterministic=True,
            external_authority=False,
            credential_required=False,
            raw_private_data_required=False,
            promotion_allowed=True,
            next_safe_move="Keep summary readback-only; do not send, submit, or mark paid without proof.",
        ),
        FinanceCalculationCapability(
            capability_id="finance_capability_payment_tracking_summary",
            source_module_ref="repo_a_readbacks_only",
            capability_type="PAYMENT_TRACKING_SUMMARY",
            description="Summarize payment tracking state from existing receipts; no bank/payment verification.",
            inputs_required=("payment_tracking_receipt_refs",),
            outputs_produced=("tracking_state_summary", "missing_receipts"),
            deterministic=True,
            external_authority=False,
            credential_required=False,
            raw_private_data_required=False,
            promotion_allowed=True,
            next_safe_move="Label unverified states clearly and require receipts for paid/completed claims.",
        ),
        FinanceCalculationCapability(
            capability_id="finance_capability_tax_category_hint",
            source_module_ref="repo_b_finance_decision_chief_cpa_brain",
            capability_type="TAX_CATEGORY_HINT",
            description="Return bookkeeping category hints with explicit not-tax-advice boundary.",
            inputs_required=("category",),
            outputs_produced=("bookkeeping_hint", "professional_advice_false"),
            deterministic=True,
            external_authority=False,
            credential_required=False,
            raw_private_data_required=False,
            promotion_allowed=True,
            next_safe_move="Keep all tax outputs as category hints and require CPA/operator review.",
        ),
        FinanceCalculationCapability(
            capability_id="finance_capability_client_job_finance_summary",
            source_module_ref="repo_a_receipts_and_readbacks",
            capability_type="CLIENT_JOB_FINANCE_SUMMARY",
            description="Summarize client/job finance records from existing safe readbacks.",
            inputs_required=("client_ref", "job_ref", "receipt_refs"),
            outputs_produced=("safe_summary", "missing_receipts", "blocked_actions"),
            deterministic=True,
            external_authority=False,
            credential_required=False,
            raw_private_data_required=False,
            promotion_allowed=True,
            next_safe_move="Use only tokenized/source refs and aggregate amounts; never dump raw ledger bodies.",
        ),
        FinanceCalculationCapability(
            capability_id="finance_capability_report_formatting",
            source_module_ref="repo_b_finance_decision_chief_cpa_brain",
            capability_type="REPORT_FORMATTING",
            description="Use report shape ideas only; generated reports must avoid raw private ledger bodies.",
            inputs_required=("safe_aggregate_summary",),
            outputs_produced=("operator_readable_summary",),
            deterministic=True,
            external_authority=False,
            credential_required=False,
            raw_private_data_required=False,
            promotion_allowed=True,
            next_safe_move="Format aggregate safe summaries only.",
        ),
    )


def build_plan() -> PromotedFinanceAdapterPlan:
    selected = tuple(cap.capability_id for cap in build_capabilities() if cap.promotion_allowed)
    return PromotedFinanceAdapterPlan(
        plan_id="repo_b_finance_budget_adapter_plan_v0",
        selected_capabilities=selected,
        excluded_capabilities=(
            "Repo B budget state/log mutation",
            "Repo B CPA LLM/cloud parsing and formatting",
            "raw billing CSV / expense JSON body exposure",
            "private tax baseline export",
            "bank/payment/tax filing/account portal access",
        ),
        target_repo_a_module="repo_b_finance_budget_adapter.py",
        test_strategy=(
            "fixture-only show budget calculation",
            "deterministic expense category mapping",
            "Capital Hilton invoice summary fixture",
            "tax category hint not professional advice",
            "unsafe bank/payment/tax actions blocked",
        ),
        fixture_strategy=(
            "Use synthetic budget spend/cap numbers.",
            "Use safe expense description summaries.",
            "Use Capital Hilton readback-level known facts only.",
        ),
        privacy_policy=(
            "No raw private ledger rows in generated outputs.",
            "No private tax baseline values copied from Repo B.",
            "No credentials or account identifiers.",
            "Operator review required for category/tax hints.",
        ),
        authority_boundary=AUTHORITY_BOUNDARY,
        next_safe_move="Adopt the rebuilt subset as the safe Repo A finance helper and add receipt-backed inputs later.",
    )


def build_blockers() -> tuple[FinanceAdapterBlocker, ...]:
    definitions = (
        ("BANK_ACCESS_ATTEMPTED", "A request tried to access bank or external account data."),
        ("PAYMENT_EXECUTION_ATTEMPTED", "A request tried to execute or update payment state externally."),
        ("TAX_FILING_ATTEMPTED", "A request tried to file taxes or submit government forms."),
        ("CREDENTIAL_REQUIRED", "A requested capability required credentials."),
        ("RAW_PRIVATE_LEDGER_EXPOSED", "A package tried to expose raw ledger rows or private financial bodies."),
        ("PROFESSIONAL_ADVICE_CLAIM", "A tax/category hint claimed professional advice authority."),
        ("BROAD_FILE_SCAN_ATTEMPTED", "A request tried to scan broad finance folders."),
        ("EXTERNAL_ACTION_ATTEMPTED", "A request tried to perform an external finance action."),
        ("UNKNOWN_FAIL_CLOSED", "The finance adapter could not prove a safe deterministic boundary."),
    )
    return tuple(
        FinanceAdapterBlocker(
            blocker_id=f"finance_adapter_blocker_{blocker_type.lower()}",
            blocker_type=blocker_type,
            condition=condition,
            severity="critical" if blocker_type != "UNKNOWN_FAIL_CLOSED" else "high",
            elioperator_warning=condition,
            fail_closed=True,
            next_safe_move="Keep this lane to deterministic local calculation and safe aggregate readbacks.",
        )
        for blocker_type, condition in definitions
    )


def build_examples() -> dict[str, Any]:
    snapshot = budget_snapshot(
        {"codex": 2.0, "gemini": 0.25, "ollama": 0.0},
        {"codex": 10.0, "gemini": 5.0, "ollama": 999.0},
        25.0,
    )
    expense = map_expense_category("plugin subscription for mix session")
    tax_hint = tax_category_hint(expense["category"])
    return {
        "show_budget_calculation": {
            "input": {"spent_by_runner": {"codex": 2.0, "gemini": 0.25}, "global_cap": 25.0},
            "snapshot": snapshot,
            "allowance": runner_allowance(snapshot, "codex", "sonnet", "standard"),
            "no_external_authority": True,
        },
        "expense_category_mapping": {
            "input_summary": "plugin subscription for mix session",
            "result": expense,
            "no_tax_advice_claim": True,
        },
        "capital_hilton_invoice_summary": capital_hilton_invoice_summary(),
        "tax_category_hint": tax_hint,
        "unsafe_bank_payment_blocker": asdict(unsafe_action_blocker("open bank portal and pay the bill")),
    }


def build_readback() -> FinanceAdapterReadback:
    safe = tuple(cap.capability_id for cap in build_capabilities() if cap.promotion_allowed)
    blocked = (
        "bank/external account access",
        "payment execution",
        "tax filing",
        "credential handling",
        "raw private ledger exposure",
        "professional tax/legal advice claims",
    )
    return FinanceAdapterReadback(
        readback_id="repo_b_finance_budget_adapter_readback_v0",
        posture="REBUILD_SMALL_SUBSET_IN_REPO_A",
        safe_capabilities=safe,
        blocked_capabilities=blocked,
        recommended_next_lane="receipt_backed_finance_summary_inputs",
        operator_summary="Repo B finance logic is useful, but the safe v0 path is a rebuilt deterministic subset in Repo A, not live Repo B execution.",
        next_safe_move="Use safe fixture helpers now; later connect them to Repo A receipts/readbacks instead of raw ledgers.",
    )


def build_payload(*, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    decisions = build_decisions()
    capabilities = build_capabilities()
    blockers = build_blockers()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "postures": POSTURES,
        "capability_types": CAPABILITY_TYPES,
        "blocker_types": BLOCKER_TYPES,
        "adapter_decisions": tuple(asdict(decision) for decision in decisions),
        "finance_capabilities": tuple(asdict(capability) for capability in capabilities),
        "promoted_finance_adapter_plan": asdict(build_plan()),
        "finance_adapter_readback": asdict(build_readback()),
        "finance_adapter_blockers": tuple(asdict(blocker) for blocker in blockers),
        "examples": build_examples(),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "machine_proof": {
            "decision_model_exists": True,
            "capability_model_exists": True,
            "safe_deterministic_capabilities_identified": all(cap.deterministic and cap.promotion_allowed for cap in capabilities),
            "unsafe_capabilities_blocked": all(blocker.fail_closed for blocker in blockers),
            "show_budget_example_exists": True,
            "expense_category_example_exists": True,
            "capital_hilton_invoice_summary_exists": True,
            "tax_category_hint_not_professional_advice": build_examples()["tax_category_hint"]["professional_advice"] is False,
            "bank_payment_tax_filing_blocked": all(
                key in {blocker.blocker_type for blocker in blockers}
                for key in ("BANK_ACCESS_ATTEMPTED", "PAYMENT_EXECUTION_ATTEMPTED", "TAX_FILING_ATTEMPTED")
            ),
            "repo_b_code_executed": False,
            "bank_access_performed": False,
            "payment_execution_performed": False,
            "tax_filing_performed": False,
            "external_account_access_performed": False,
            "invoice_email_send_performed": False,
            "coupa_access_performed": False,
            "credential_handling_performed": False,
            "raw_private_ledger_exposure": False,
            "professional_advice_claim": False,
            "external_action_performed": False,
            "mac_sync_import_run": False,
            "mission_control_swift_changed": False,
            "git_push_pull_fetch_run": False,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    readback = payload["finance_adapter_readback"]
    examples = payload["examples"]
    lines = [
        "# Repo B Finance Budget Adapter",
        "",
        readback["operator_summary"],
        "",
        f"Posture: {readback['posture']}",
        "",
        "Safe capabilities:",
    ]
    lines.extend(f"- {item}" for item in readback["safe_capabilities"])
    lines.extend(
        [
            "",
            "Blocked capabilities:",
        ]
    )
    lines.extend(f"- {item}" for item in readback["blocked_capabilities"])
    lines.extend(
        [
            "",
            "Examples:",
            f"- Show budget: {examples['show_budget_calculation']['snapshot']['budget_zone']} zone.",
            f"- Expense category: {examples['expense_category_mapping']['result']['category']}.",
            "- Capital Hilton: 4 dates at $400, subtotal $1600; payment/send state unverified.",
            f"- Tax category hint: {examples['tax_category_hint']['hint']}",
            "- Unsafe bank/payment action: blocked.",
            "",
            "Boundary:",
            "- No bank access, payment execution, tax filing, external account access, invoice/email send, Coupa access, credential handling, raw private ledger exposure, professional advice claim, external action, Mac sync/import, Swift change, or push.",
            "",
            f"Next safe move: {readback['next_safe_move']}",
            "",
        ]
    )
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: dict[str, Any], paths: tuple[Path, Path]) -> dict[str, Any]:
    readback = payload["finance_adapter_readback"]
    examples = payload["examples"]
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_status": CONTRACT_STATUS,
        "json_path": paths[0].as_posix(),
        "operator_path": paths[1].as_posix(),
        "posture": readback["posture"],
        "safe_capability_count": len(readback["safe_capabilities"]),
        "blocked_capabilities": readback["blocked_capabilities"],
        "show_budget_zone": examples["show_budget_calculation"]["snapshot"]["budget_zone"],
        "expense_category_example": examples["expense_category_mapping"]["result"]["category"],
        "capital_hilton_subtotal": examples["capital_hilton_invoice_summary"]["known_basis"]["subtotal"],
        "tax_hint_professional_advice": examples["tax_category_hint"]["professional_advice"],
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "next_safe_move": readback["next_safe_move"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Repo B finance budget adapter read-model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    args = parser.parse_args(argv)

    payload = build_payload(generated_at=args.generated_at)
    paths = write_exports(payload, Path(args.export_root))
    output = payload if args.format == "json" else build_summary(payload, paths)
    print(stable_json(output), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
