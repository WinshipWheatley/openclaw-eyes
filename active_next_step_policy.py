"""OpenClaw Active Next Step Policy V0.

Normalizes next-step text into one active, receipt-backed contract. This
module does not execute protected actions, call models, send email, open
Gmail/browser/Coupa, mutate production records, push, merge, or trust raw
authority grants.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Active Next Step Policy.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/active_next_step_policy.sqlite")

SCHEMA_VERSION = "active_next_step_policy_v0"
READ_MODEL_ID = "active_next_step_policy"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "OPENCLAW_ACTIVE_NEXT_STEP_POLICY_READY"

NEXT_STEP_SCHEMA = "OPERATOR_NEXT_STEP_V0"
STATUS_RECEIPT_SCHEMA = "NEXT_STEP_STATUS_RECEIPT_V0"
RESOLUTION_POLICY_SCHEMA = "NEXT_STEP_RESOLUTION_POLICY_V0"

NEXT_STEP_KINDS = (
    "execute_now",
    "request_authority",
    "compile_grant",
    "queue_work_package",
    "pick_up_work_package",
    "configure_connector",
    "run_test_adapter",
    "create_test_artifact",
    "draft_only",
    "provide_proof",
    "verify_evidence",
    "resolve_human_blocker",
    "activate_capability",
    "schedule_or_monitor",
    "no_safe_action_available",
)

ACTORS = ("openclaw", "operator", "codex_worker", "backend", "connector", "external_party")
ACTIONABILITY = (
    "executable_now",
    "needs_operator_authority",
    "needs_human_setup",
    "needs_worker_pickup",
    "needs_external_event",
    "blocked_no_safe_path",
)

DENIED_ACTIONS = [
    "send_email",
    "delete_email",
    "archive_email",
    "mark_email_read",
    "open_gmail_ui",
    "open_browser",
    "coupa_submit",
    "mark_paid",
    "mutate_ledger",
    "mutate_workbook",
    "export_pdf",
    "git_push",
    "git_merge",
    "spawn_worker",
    "invoke_external_model",
    "lm2_tool_expansion",
    "store_secret_in_repo",
]

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "gmail_allowed": False,
    "gmail_ui_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "worker_spawn_allowed": False,
    "external_model_allowed": False,
    "lm2_tool_expansion_allowed": False,
    "authority_granted_from_raw_text_allowed": False,
    "sent": False,
    "paid": False,
}

RESOLUTION_INTENT_PHRASES = (
    "do that",
    "do the next step",
    "yes",
    "go ahead",
    "proceed",
    "ok do that",
    "okay do that",
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _short_hash(*parts: Any, length: int = 16) -> str:
    digest = hashlib.sha256()
    for part in parts:
        if isinstance(part, (dict, list, tuple)):
            value = json.dumps(part, sort_keys=True, ensure_ascii=False)
        else:
            value = str(part)
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:length]


def _expires_at(generated_at: str) -> str:
    return (datetime.fromisoformat(generated_at) + timedelta(hours=4)).isoformat(timespec="seconds")


def _lane_from_request(request: Mapping[str, Any]) -> dict[str, str]:
    return {
        "target_world_ref": str(request.get("current_world_ref") or request.get("target_world_ref") or ""),
        "target_thread_ref": str(request.get("current_thread_ref") or request.get("target_thread_ref") or ""),
        "target_project_ref": str(request.get("target_project_ref") or request.get("target_client_ref") or ""),
    }


def _lane_key(lane: Mapping[str, Any]) -> str:
    return stable_json(
        {
            "target_world_ref": str(lane.get("target_world_ref") or ""),
            "target_thread_ref": str(lane.get("target_thread_ref") or ""),
            "target_project_ref": str(lane.get("target_project_ref") or ""),
        }
    ).strip()


def _run_mode(route_result: Mapping[str, Any], generated_at: str) -> str:
    context = route_result.get("run_mode_context") if isinstance(route_result.get("run_mode_context"), Mapping) else {}
    return str(context.get("run_mode") or route_result.get("run_mode") or "production")


def build_next_step(
    *,
    source_state: str,
    next_step_kind: str,
    actor: str,
    actionability: str,
    lane: Mapping[str, Any],
    run_mode: str,
    label: str,
    human_summary: str,
    exact_operator_input_needed: str,
    expected_result: str,
    objective_id: str = "",
    required_authority_ref: str = "",
    required_capability_id: str = "",
    related_package_id: str = "",
    blocker_id: str = "",
    receipt_ref: str = "",
    denied_actions: Sequence[str] = DENIED_ACTIONS,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    kind = next_step_kind if next_step_kind in NEXT_STEP_KINDS else "no_safe_action_available"
    actor_value = actor if actor in ACTORS else "openclaw"
    actionability_value = actionability if actionability in ACTIONABILITY else "blocked_no_safe_path"
    step_seed = {
        "source_state": source_state,
        "objective_id": objective_id,
        "capability_id": required_capability_id,
        "package_id": related_package_id,
        "lane": dict(lane),
        "kind": kind,
    }
    return {
        "schema_version": NEXT_STEP_SCHEMA,
        "next_step_id": f"operator_next_step:{_short_hash(step_seed)}",
        "objective_id": objective_id,
        "lane": dict(lane),
        "run_mode": run_mode,
        "label": label,
        "human_summary": human_summary,
        "next_step_kind": kind,
        "actor": actor_value,
        "actionability": actionability_value,
        "required_authority_ref": required_authority_ref,
        "required_capability_id": required_capability_id,
        "related_package_id": related_package_id,
        "blocker_id": blocker_id,
        "exact_operator_input_needed": exact_operator_input_needed,
        "expected_result": expected_result,
        "denied_actions": list(denied_actions),
        "receipt_ref": receipt_ref or f"operator_next_step_receipt:{_short_hash(step_seed, generated_at)}",
        "expires_at": _expires_at(generated_at) if actionability_value in {"needs_operator_authority", "needs_worker_pickup"} else "",
        "source_state": source_state,
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_status_receipt(next_step: Mapping[str, Any], *, status: str = "proposed", generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "schema_version": STATUS_RECEIPT_SCHEMA,
        "next_step_id": str(next_step.get("next_step_id") or ""),
        "status": status,
        "objective_id": str(next_step.get("objective_id") or ""),
        "package_id": str(next_step.get("related_package_id") or ""),
        "capability_id": str(next_step.get("required_capability_id") or ""),
        "run_mode": str(next_step.get("run_mode") or "production"),
        "created_at": generated_at,
        "updated_at": generated_at,
        "receipt_ref": str(next_step.get("receipt_ref") or f"next_step_status_receipt:{_short_hash(next_step, status, generated_at)}"),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def resolution_policies(*, generated_at: str | None = None) -> list[dict[str, Any]]:
    generated_at = generated_at or utc_now()
    rows = [
        ("capability_gap", "request_authority", "operator", "Grant scoped Make-It-So authority.", "Make it so for this lane."),
        ("authority_request", "request_authority", "operator", "Grant the active authority request.", "Make it so."),
        ("authority_grant", "pick_up_work_package", "codex_worker", "Pick up the queued bounded package.", "Run or configure the approved Codex worker bridge."),
        ("package_queued", "pick_up_work_package", "codex_worker", "Pick up the queued bounded package.", "Run or configure the approved Codex worker bridge."),
        ("worker_bridge_missing", "pick_up_work_package", "codex_worker", "Use the manual handoff or configure an approved bridge.", "Pick up the named package."),
        ("test_adapter_missing", "run_test_adapter", "operator", "Configure the missing test adapter.", "Configure the missing test adapter/transport."),
        ("human_setup_required", "configure_connector", "operator", "Configure the exact missing connector.", "Configure the connector outside the repo."),
        ("proof_missing", "provide_proof", "operator", "Provide the named proof item.", "Attach exact proof."),
        ("external_wait", "schedule_or_monitor", "openclaw", "Create a verification checkpoint or draft.", "Prepare a follow-up or checkpoint."),
        ("production_rejection", "resolve_human_blocker", "operator", "Resolve the named production rejection.", "Provide allowed production proof."),
    ]
    return [
        {
            "schema_version": RESOLUTION_POLICY_SCHEMA,
            "policy_id": f"next_step_resolution_policy:{source}",
            "source_state": source,
            "next_step_kind": kind,
            "actor": actor,
            "human_summary_template": summary,
            "exact_operator_input_template": exact,
            "denied_actions": list(DENIED_ACTIONS),
            "created_at": generated_at,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
        for source, kind, actor, summary, exact in rows
    ]


def _make_it_so_next_step(route_result: Mapping[str, Any], request: Mapping[str, Any], generated_at: str) -> dict[str, Any] | None:
    payload = route_result.get("make_it_so_objective") if isinstance(route_result.get("make_it_so_objective"), Mapping) else {}
    if not payload:
        return None
    lane = _lane_from_request(request)
    run_mode = _run_mode(route_result, generated_at)
    status = str(payload.get("response_status") or route_result.get("route_status") or "")
    objective = payload.get("objective_request") if isinstance(payload.get("objective_request"), Mapping) else {}
    blocker = payload.get("objective_blocker") if isinstance(payload.get("objective_blocker"), Mapping) else {}
    capability_id = str(objective.get("capability_id") or blocker.get("capability_id") or "read_only_email_lookup")
    objective_id = str(objective.get("objective_id") or "")
    make_request = payload.get("make_it_so_authority_request") if isinstance(payload.get("make_it_so_authority_request"), Mapping) else {}
    if status == "MAKE_IT_SO_AUTHORITY_REQUEST_READY":
        return build_next_step(
            source_state="authority_request",
            next_step_kind="request_authority",
            actor="operator",
            actionability="needs_operator_authority",
            lane=lane,
            run_mode=run_mode,
            label="Grant Make-It-So authority for read-only email lookup",
            human_summary="OpenClaw needs scoped Make-It-So authority before it can build/test the missing read-only email lookup capability.",
            exact_operator_input_needed="Make it so for read-only email lookup in this Finance lane.",
            expected_result="A scoped Make-It-So grant, enablement plan, and bounded Codex work package are created.",
            objective_id=objective_id,
            required_authority_ref=str(make_request.get("request_id") or ""),
            required_capability_id=capability_id,
            blocker_id=str(blocker.get("blocker_id") or ""),
            generated_at=generated_at,
        )
    lifecycle = payload.get("codex_work_package_lifecycle") if isinstance(payload.get("codex_work_package_lifecycle"), Mapping) else {}
    state = lifecycle.get("package_state") if isinstance(lifecycle.get("package_state"), Mapping) else {}
    latest_result = lifecycle.get("latest_package_result") if isinstance(lifecycle.get("latest_package_result"), Mapping) else {}
    activation = lifecycle.get("latest_activation_decision") if isinstance(lifecycle.get("latest_activation_decision"), Mapping) else {}
    package = payload.get("codex_work_package") if isinstance(payload.get("codex_work_package"), Mapping) else {}
    package_id = str(package.get("package_id") or state.get("package_id") or latest_result.get("package_id") or "")
    if (
        str(latest_result.get("capability_status") or "") == "human_setup_required"
        or str(latest_result.get("blocker_kind") or "") == "missing_read_only_email_connector"
        or (state.get("state") == "validation_passed" and activation.get("decision") == "blocked" and activation.get("production_ready") is False)
    ):
        return build_next_step(
            source_state="human_setup_required",
            next_step_kind="configure_connector",
            actor="operator",
            actionability="needs_human_setup",
            lane=lane,
            run_mode=run_mode,
            label="Configure the read-only email connector",
            human_summary="The package validated, but production activation is blocked until a safe read-only email connector or credential exists.",
            exact_operator_input_needed="Configure a safe read-only email connector or OS/keychain-backed credential outside the repo; do not store secrets in the repo.",
            expected_result="Connector setup exists outside the repo and a follow-up package can validate read-only lookup without send/delete/archive/mark-read authority.",
            objective_id=objective_id,
            required_capability_id=capability_id,
            related_package_id=package_id,
            blocker_id=str(latest_result.get("blocker_kind") or blocker.get("blocker_id") or "missing_read_only_email_connector"),
            generated_at=generated_at,
        )
    if status == "MAKE_IT_SO_GRANT_COMPILED" or state.get("state") == "awaiting_worker_bridge":
        return build_next_step(
            source_state="worker_bridge_missing",
            next_step_kind="pick_up_work_package",
            actor="codex_worker",
            actionability="needs_worker_pickup",
            lane=lane,
            run_mode=run_mode,
            label="Pick up the bounded Codex package",
            human_summary="The scoped package is queued; the next active step is to run or configure the approved Codex worker bridge for that package.",
            exact_operator_input_needed=f"Configure or run the approved Codex worker bridge for package {package_id}.",
            expected_result="The package result is submitted and lifecycle ingestion records validation or one true blocker.",
            objective_id=objective_id,
            required_capability_id=capability_id,
            related_package_id=package_id,
            blocker_id=str(state.get("blocker_ref") or ""),
            generated_at=generated_at,
        )
    if status == "CAPABILITY_ALREADY_APPROVED":
        return build_next_step(
            source_state="capability_ready",
            next_step_kind="verify_evidence",
            actor="connector",
            actionability="executable_now",
            lane=lane,
            run_mode=run_mode,
            label="Run scoped read-only lookup",
            human_summary="The capability is approved for this scope; the next step is a scoped evidence lookup with receipts.",
            exact_operator_input_needed="Run the scoped read-only email lookup for this lane.",
            expected_result="Evidence-backed answer or precise missing-proof result.",
            objective_id=objective_id,
            required_capability_id=capability_id,
            generated_at=generated_at,
        )
    if status == "OBJECTIVE_STATUS_READY":
        return build_next_step(
            source_state="make_it_so_objective",
            next_step_kind="request_authority",
            actor="operator",
            actionability="needs_operator_authority",
            lane=lane,
            run_mode=run_mode,
            label="Grant Make-It-So authority for read-only email lookup",
            human_summary="The objective is already recorded; grant the active scoped authority request or review the package lifecycle.",
            exact_operator_input_needed="Make it so for read-only email lookup in this Finance lane.",
            expected_result="A bounded package is queued or its current lifecycle blocker is shown.",
            objective_id=objective_id,
            required_capability_id=capability_id,
            blocker_id=str(blocker.get("blocker_id") or ""),
            generated_at=generated_at,
        )
    return None


def _capability_next_step(route_result: Mapping[str, Any], request: Mapping[str, Any], generated_at: str) -> dict[str, Any] | None:
    payload = route_result.get("capability_authority") if isinstance(route_result.get("capability_authority"), Mapping) else {}
    gap = payload.get("capability_gap") if isinstance(payload.get("capability_gap"), Mapping) else {}
    auth = payload.get("operator_authority_request") if isinstance(payload.get("operator_authority_request"), Mapping) else {}
    if not gap and not auth:
        return None
    lane = _lane_from_request(request)
    capability_id = str(gap.get("capability_id") or auth.get("requested_capability_id") or "read_only_email_lookup")
    return build_next_step(
        source_state="capability_gap",
        next_step_kind="request_authority",
        actor="operator",
        actionability="needs_operator_authority",
        lane=lane,
        run_mode=_run_mode(route_result, generated_at),
        label="Grant scoped read-only email lookup authority",
        human_summary="OpenClaw needs a scoped authority request before it can use or build this capability.",
        exact_operator_input_needed="Grant read-only email lookup for this lane only.",
        expected_result="A verifier-readable scoped authority grant is compiled; denied actions remain denied.",
        required_authority_ref=str(auth.get("request_id") or ""),
        required_capability_id=capability_id,
        blocker_id=str(gap.get("gap_id") or ""),
        generated_at=generated_at,
    )


def _proof_response_next_step(route_result: Mapping[str, Any], request: Mapping[str, Any], generated_at: str) -> dict[str, Any] | None:
    response = route_result.get("proof_response") if isinstance(route_result.get("proof_response"), Mapping) else {}
    display = route_result.get("operator_display") if isinstance(route_result.get("operator_display"), Mapping) else {}
    lane = _lane_from_request(request)
    text = " ".join(
        [str(request.get("operator_text") or ""), str(response.get("next_step") or ""), str(display.get("next_safe_action") or "")]
    ).lower()
    if "attach" in text and ("proof" in text or "payment evidence" in text):
        return build_next_step(
            source_state="proof_missing",
            next_step_kind="provide_proof",
            actor="operator",
            actionability="needs_human_setup",
            lane=lane,
            run_mode=_run_mode(route_result, generated_at),
            label="Attach payment evidence",
            human_summary="Payment or ledger advancement needs proof, not a draft or generated summary.",
            exact_operator_input_needed="Attach bank, check, remittance, or email acknowledgment evidence that directly proves payment status.",
            expected_result="Evidence is recorded as candidate/payment-processing proof; paid and ledger truth remain gated until verified.",
            required_capability_id="payment_proof_review",
            generated_at=generated_at,
        )
    if "wait" in text or "payment" in text:
        return build_next_step(
            source_state="external_wait",
            next_step_kind="schedule_or_monitor",
            actor="openclaw",
            actionability="needs_external_event",
            lane=lane,
            run_mode=_run_mode(route_result, generated_at),
            label="Prepare a verification checkpoint",
            human_summary="The external party may still need time, but OpenClaw can prepare the follow-up/checkpoint instead of leaving a passive wait.",
            exact_operator_input_needed="Choose a follow-up checkpoint or attach payment proof when it arrives.",
            expected_result="A draft/checklist or proof request is ready without marking paid or touching the ledger.",
            required_capability_id="payment_watch",
            generated_at=generated_at,
        )
    return None


def _draft_next_step(route_result: Mapping[str, Any], request: Mapping[str, Any], generated_at: str) -> dict[str, Any] | None:
    if "draft_only" not in str(route_result.get("backend_route") or ""):
        return None
    return build_next_step(
        source_state="draft_only",
        next_step_kind="draft_only",
        actor="openclaw",
        actionability="executable_now",
        lane=_lane_from_request(request),
        run_mode=_run_mode(route_result, generated_at),
        label="Draft the follow-up for review",
        human_summary="OpenClaw can prepare the follow-up text without sending email or checking Gmail.",
        exact_operator_input_needed="Ask OpenClaw to draft the question for review; sending remains separately gated.",
        expected_result="Draft-only follow-up text is staged for operator review.",
        required_capability_id="draft_followup",
        generated_at=generated_at,
    )


def _test_adapter_next_step(route_result: Mapping[str, Any], request: Mapping[str, Any], generated_at: str) -> dict[str, Any] | None:
    receipt = route_result.get("test_effect_receipt") if isinstance(route_result.get("test_effect_receipt"), Mapping) else {}
    if not receipt:
        return None
    status = str(receipt.get("status") or "")
    if status in {"TEST_ADAPTER_MISSING", "BLOCKED_BY_RUN_MODE", "BLOCKED_BY_AUTHORITY"}:
        return build_next_step(
            source_state="test_adapter_missing",
            next_step_kind="run_test_adapter",
            actor="operator",
            actionability="needs_human_setup",
            lane=_lane_from_request(request),
            run_mode=_run_mode(route_result, generated_at),
            label="Configure the test adapter or authority",
            human_summary="The requested test effect needs the missing adapter, run mode, or test authority before execution.",
            exact_operator_input_needed="Enter test mode and configure the missing test adapter/transport with no production secrets in repo.",
            expected_result="A test receipt is produced, or a precise adapter-missing receipt is recorded.",
            blocker_id=status,
            generated_at=generated_at,
        )
    return build_next_step(
        source_state="test_effect",
        next_step_kind="create_test_artifact",
        actor="backend",
        actionability="executable_now",
        lane=_lane_from_request(request),
        run_mode=_run_mode(route_result, generated_at),
        label="Review the test receipt",
        human_summary="The test effect produced a receipt that can prove test behavior only.",
        exact_operator_input_needed="Review the test receipt; do not use it as production proof.",
        expected_result="Test-only receipt is kept separate from production truth.",
        receipt_ref=str(receipt.get("receipt_id") or ""),
        generated_at=generated_at,
    )


def _no_active_next_step(request: Mapping[str, Any], route_result: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    return build_next_step(
        source_state="no_active_next_step",
        next_step_kind="no_safe_action_available",
        actor="operator",
        actionability="blocked_no_safe_path",
        lane=_lane_from_request(request),
        run_mode=_run_mode(route_result, generated_at),
        label="Name the objective and scope",
        human_summary="There is no active next step to resolve, so OpenClaw will not infer authority from a vague command.",
        exact_operator_input_needed="Name the lane, objective, or blocked capability you want to advance.",
        expected_result="A scoped objective or authority request can be created without broad authority.",
        generated_at=generated_at,
    )


def next_step_for_route(route_result: Mapping[str, Any], request: Mapping[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    for builder in (_make_it_so_next_step, _capability_next_step, _draft_next_step, _test_adapter_next_step, _proof_response_next_step):
        step = builder(route_result, request, generated_at)
        if step:
            return step
    return _no_active_next_step(request, route_result, generated_at)


def _connect(sqlite_path: Path) -> sqlite3.Connection:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS active_next_steps (
          next_step_id TEXT PRIMARY KEY,
          lane_key TEXT NOT NULL,
          source_state TEXT NOT NULL,
          next_step_kind TEXT NOT NULL,
          actionability TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          step_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS next_step_status_receipts (
          receipt_ref TEXT PRIMARY KEY,
          next_step_id TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          receipt_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS next_step_policy_contract (
          read_model_id TEXT PRIMARY KEY,
          generated_at TEXT NOT NULL,
          status TEXT NOT NULL,
          payload_json TEXT NOT NULL
        );
        """
    )
    return conn


def persist_next_step(next_step: Mapping[str, Any], receipt: Mapping[str, Any], *, sqlite_path: Path) -> None:
    lane = next_step.get("lane") if isinstance(next_step.get("lane"), Mapping) else {}
    with _connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO active_next_steps
            (next_step_id, lane_key, source_state, next_step_kind, actionability, status, created_at, updated_at, step_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(next_step["next_step_id"]),
                _lane_key(lane),
                str(next_step.get("source_state") or ""),
                str(next_step.get("next_step_kind") or ""),
                str(next_step.get("actionability") or ""),
                str(receipt.get("status") or "proposed"),
                str(next_step.get("created_at") or receipt.get("created_at") or utc_now()),
                str(receipt.get("updated_at") or receipt.get("created_at") or utc_now()),
                stable_json(next_step),
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO next_step_status_receipts
            (receipt_ref, next_step_id, status, created_at, receipt_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(receipt["receipt_ref"]),
                str(receipt["next_step_id"]),
                str(receipt["status"]),
                str(receipt["created_at"]),
                stable_json(receipt),
            ),
        )
        conn.commit()


def load_active_next_step(sqlite_path: Path, *, world_ref: str, thread_ref: str, project_ref: str = "") -> dict[str, Any]:
    lane = {"target_world_ref": world_ref, "target_thread_ref": thread_ref, "target_project_ref": project_ref}
    with _connect(sqlite_path) as conn:
        row = conn.execute(
            """
            SELECT step_json FROM active_next_steps
            WHERE lane_key = ? AND status IN ('proposed', 'queued', 'executing')
            ORDER BY updated_at DESC LIMIT 1
            """,
            (_lane_key(lane),),
        ).fetchone()
    return json.loads(row["step_json"]) if row else {}


def resolution_intent(text: str) -> bool:
    lowered = str(text or "").strip().lower().rstrip(".!?")
    return any(lowered == phrase or lowered.startswith(f"{phrase} ") for phrase in RESOLUTION_INTENT_PHRASES)


def attach_next_step(
    route_result: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
    sqlite_path: Path | None = None,
    generated_at: str | None = None,
    status: str = "proposed",
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    result = dict(route_result)
    next_step = next_step_for_route(result, request, generated_at=generated_at)
    receipt = build_status_receipt(next_step, status=status, generated_at=generated_at)
    result["primary_next_step"] = next_step
    result["next_step_status_receipt"] = receipt
    machine = dict(result.get("machine_proof") or {})
    machine.update(
        {
            "primary_next_step_emitted": True,
            "primary_next_step_kind": next_step["next_step_kind"],
            "passive_only_next_step": False,
            "raw_authority_granted_trusted": False,
        }
    )
    result["machine_proof"] = machine
    if sqlite_path is not None:
        persist_next_step(next_step, receipt, sqlite_path=sqlite_path)
    return result


def build_read_model(*, sqlite_path: Path = DEFAULT_SQLITE_PATH, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    with _connect(sqlite_path) as conn:
        rows = conn.execute("SELECT step_json FROM active_next_steps ORDER BY updated_at DESC LIMIT 20").fetchall()
        receipt_rows = conn.execute("SELECT receipt_json FROM next_step_status_receipts ORDER BY created_at DESC LIMIT 20").fetchall()
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "contracts": [NEXT_STEP_SCHEMA, STATUS_RECEIPT_SCHEMA, RESOLUTION_POLICY_SCHEMA],
        "resolution_policies": resolution_policies(generated_at=generated_at),
        "recent_next_steps": [json.loads(row["step_json"]) for row in rows],
        "recent_status_receipts": [json.loads(row["receipt_json"]) for row in receipt_rows],
        "invalid_passive_next_steps": ["wait", "check later", "sit tight", "unavailable"],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_wiki(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# Active Next Step Policy",
            "",
            f"Status: `{payload['status']}`",
            "",
            "Every blocked or incomplete operator objective should expose one structured active next step.",
            "",
            "- Passive-only waits are not valid next steps.",
            "- Protected actions remain denied.",
            "- Authority, package, proof, connector, and test-adapter states resolve to explicit next-step contracts.",
            "",
        ]
    )


def export_active_next_step_policy(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    payload = build_read_model(sqlite_path=sqlite_path, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    read_model_path.write_text(stable_json(payload), encoding="utf-8")
    wiki = _rooted(wiki_path)
    wiki.parent.mkdir(parents=True, exist_ok=True)
    wiki.write_text(build_wiki(payload), encoding="utf-8")
    with _connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO next_step_policy_contract
            (read_model_id, generated_at, status, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (READ_MODEL_ID, str(payload.get("generated_at") or ""), str(payload.get("status") or ""), stable_json(payload)),
        )
        conn.commit()
    bridge_path = ""
    if bridge_root is not None:
        bridge = Path(bridge_root)
        bridge.mkdir(parents=True, exist_ok=True)
        target = bridge / JSON_EXPORT_NAME
        shutil.copy2(read_model_path, target)
        bridge_path = target.as_posix()
    return {
        "status": str(payload["status"]),
        "read_model_path": read_model_path.as_posix(),
        "bridge_path": bridge_path,
        "wiki_path": wiki.as_posix(),
        "sqlite_path": _rooted(sqlite_path).as_posix(),
    }


def main() -> None:
    result = export_active_next_step_policy()
    print(stable_json(result))


if __name__ == "__main__":
    main()
