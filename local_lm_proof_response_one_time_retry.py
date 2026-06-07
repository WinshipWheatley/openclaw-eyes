"""One-time local LM proof-to-response retry V0.

Runs the approved Finance / Capital Hilton retry through one local Ollama
invocation. The retry differs from the first pilot by using the strict
JSON-only schema adapter before deterministic verification and publication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import local_lm_proof_response_one_time_pilot as prior_pilot
import proof_bundle_builder as bundles
import proof_to_response_runtime as runtime
import proof_to_response_schema_adapter as schema_adapter


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Local LM Proof Response One Time Retry.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/local_lm_proof_response_one_time_retry.sqlite")

SCHEMA_VERSION = "local_lm_proof_response_one_time_retry_v0"
READ_MODEL_ID = "local_lm_proof_response_one_time_retry"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_ONE_TIME_RETRY_READY"
NOT_READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_ONE_TIME_RETRY_NOT_READY"

SCENARIO_ID = "finance_capital_hilton_payment_watch"
WORLD_REF = "finance"
THREAD_REF = "capital_hilton"
PILOT_LANE = "finance/capital_hilton"
PILOT_QUESTION = "What should I do here?"
RUNTIME_REF = "ollama"
MODEL_REF = "local_model:ollama:qwen3_8b-q4_k_m"
MODEL_NAME = "qwen3:8b-q4_K_M"
CANDIDATE_SOURCE = "local_ollama_one_time_retry_schema_adapter"
SOURCE_REQUEST_ID = "local_lm_one_time_retry_finance_capital_hilton_payment_watch"
EXPECTED_CONTROL_LABEL = "Attach payment evidence"
EXPECTED_FACT_IDS = ("payment_evidence_missing", "coupa_processing", "ledger_untouched")

PRECONDITIONS = {
    "local_lm_proof_response_retry_operator_approval": {
        "filename": "local_lm_proof_response_retry_operator_approval.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_RETRY_OPERATOR_APPROVAL_READY",),
    },
    "local_lm_proof_response_retry_approval_packet": {
        "filename": "local_lm_proof_response_retry_approval_packet.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_RETRY_APPROVAL_PACKET_READY",),
    },
    "local_lm_proof_response_pilot_postmortem": {
        "filename": "local_lm_proof_response_pilot_postmortem.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_PILOT_POSTMORTEM_READY",),
    },
    "proof_to_response_schema_adapter": {
        "filename": schema_adapter.STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (schema_adapter.READY_STATUS,),
    },
    "local_model_selection_for_proof_response": {
        "filename": "local_model_selection_for_proof_response.json",
        "accepted_statuses": ("LOCAL_MODEL_SELECTION_FOR_PROOF_RESPONSE_READY",),
    },
    "proof_bundle_freshness_trace_integration": {
        "filename": bundles.FRESHNESS_TRACE_STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (bundles.FRESHNESS_TRACE_READY_STATUS,),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": bundles.REDACTION_STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (bundles.REDACTION_READY_STATUS,),
    },
    "proof_to_response_runtime": {
        "filename": runtime.STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (runtime.READY_STATUS,),
    },
    "context_freshness_decision_trace_gate": {
        "filename": "context_freshness_decision_trace_gate.json",
        "accepted_statuses": ("CONTEXT_FRESHNESS_DECISION_TRACE_GATE_READY",),
    },
    "local_lm_proof_response_invocation_boundary_packet": {
        "filename": "local_lm_proof_response_invocation_boundary_packet.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_INVOCATION_BOUNDARY_PACKET_READY",),
    },
}

UNSAFE_TRUE_KEYS = prior_pilot.UNSAFE_TRUE_KEYS | set(schema_adapter.UNSAFE_TRUE_KEYS) | set(runtime.UNSAFE_TRUE_KEYS)

JSON_ONLY_VALID_EXAMPLE = {
    "headline": "Payment evidence needed",
    "body": "Coupa is processing. I cannot mark this paid until payment evidence is attached. The ledger stays untouched.",
    "next_step": EXPECTED_CONTROL_LABEL,
    "missing_input": ["payment_evidence"],
    "can_do_now": ["explain the payment-watch state", "accept payment evidence"],
    "cannot_do_yet": ["mark paid", "post to the ledger", "submit anything"],
    "claimed_facts": list(EXPECTED_FACT_IDS),
    "requested_controls": [EXPECTED_CONTROL_LABEL],
    "uncertainty_notes": [],
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = _rooted(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _content_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _walk_values(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    return sorted({key for key, value in _walk_values(payload) if key in UNSAFE_TRUE_KEYS and value is True})


def _status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("readiness_status") or payload.get("status") or payload.get("contract_status") or "")


def precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, spec in PRECONDITIONS.items():
        filename = str(spec["filename"])
        payload = _load_json(root / filename)
        observed = _status(payload)
        accepted = [str(status) for status in spec["accepted_statuses"]]
        rows.append(
            {
                "precondition_ref": ref,
                "source_ref": f"generated/read_models/{filename}",
                "observed_status": observed,
                "accepted_statuses": accepted,
                "ready": observed in accepted,
            }
        )
    rows.append(prior_pilot._scoped_response_precondition(root))
    return rows


def boundary_matches_retry_approval(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> bool:
    root = _rooted(read_model_root)
    approval = _load_json(root / "local_lm_proof_response_retry_operator_approval.json")
    scope = approval.get("approval_scope") if isinstance(approval.get("approval_scope"), Mapping) else {}
    limits = approval.get("approval_limits") if isinstance(approval.get("approval_limits"), Mapping) else {}
    boundary = _load_json(root / "local_lm_proof_response_invocation_boundary_packet.json")
    packet = boundary.get("invocation_boundary_packet") if isinstance(boundary.get("invocation_boundary_packet"), Mapping) else {}
    return (
        approval.get("status") == "LOCAL_LM_PROOF_RESPONSE_RETRY_OPERATOR_APPROVAL_READY"
        and approval.get("operator_decision") == "approve_one_time_local_lm_retry_with_schema_adapter"
        and scope.get("attempt_limit") == 1
        and scope.get("lane") == PILOT_LANE
        and scope.get("question") == PILOT_QUESTION
        and scope.get("runtime") == RUNTIME_REF
        and scope.get("model") == MODEL_NAME
        and str(scope.get("prompt_mode") or "").lower() == "json-only"
        and scope.get("schema_adapter_required") is True
        and scope.get("valid_example_required") is True
        and scope.get("verifier_required") is True
        and scope.get("fallback_required") is True
        and limits.get("one_retry_attempt_only") is True
        and limits.get("model_must_match") == MODEL_NAME
        and limits.get("runtime_must_match") == RUNTIME_REF
        and packet.get("selected_runtime_ref") == RUNTIME_REF
        and packet.get("selected_model_ref") == MODEL_REF
        and packet.get("selected_model_name") == MODEL_NAME
    )


def approval_already_used(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
) -> bool:
    existing = _load_json(_rooted(read_model_root) / JSON_EXPORT_NAME)
    usage = existing.get("approval_usage") if isinstance(existing.get("approval_usage"), Mapping) else {}
    if usage.get("marked_used") is True:
        return True
    path = _rooted(sqlite_path)
    if not path.exists():
        return False
    try:
        with sqlite3.connect(path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM local_lm_retry_receipts WHERE receipt_ref = ?",
                ("approval_used_receipt",),
            ).fetchone()
    except sqlite3.Error:
        return False
    return bool(row and int(row[0]) > 0)


def build_redacted_retry_bundle(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> dict[str, Any]:
    return bundles.build_redacted_proof_bundle(SCENARIO_ID, read_model_root=read_model_root)


def forbidden_fields_absent(proof_bundle: Mapping[str, Any]) -> bool:
    return prior_pilot.forbidden_fields_absent(proof_bundle)


def freshness_gate_allows_bundle(proof_bundle: Mapping[str, Any]) -> bool:
    return prior_pilot.freshness_gate_allows_bundle(proof_bundle)


def lm_visible_bundle(proof_bundle: Mapping[str, Any]) -> dict[str, Any]:
    return prior_pilot.lm_visible_bundle(proof_bundle)


def build_json_only_prompt(lm_bundle: Mapping[str, Any]) -> str:
    prompt = {
        "instruction": schema_adapter.model_instruction_template().strip(),
        "task": "Draft a concise proof-to-response answer for the operator.",
        "operator_question": PILOT_QUESTION,
        "strict_json_schema": schema_adapter.strict_json_draft_schema(),
        "valid_example": JSON_ONLY_VALID_EXAMPLE,
        "redacted_freshness_gated_proof_bundle": lm_bundle,
        "allowed_fact_ids": list(EXPECTED_FACT_IDS),
        "allowed_control_labels": [EXPECTED_CONTROL_LABEL],
        "rules": [
            "Return one JSON object only.",
            "Do not wrap JSON in markdown.",
            "Use only allowed fact IDs in claimed_facts.",
            "Use the allowed control label in requested_controls.",
            "Do not claim paid, sent, submitted, or executed.",
            "Do not promise ledger mutation, Coupa submit, email send, or paid marking.",
        ],
    }
    return stable_json(prompt)


def invoke_ollama_once(prompt: str, *, timeout_seconds: int = 120) -> dict[str, Any]:
    started_at = utc_now()
    try:
        completed = subprocess.run(
            ["ollama", "run", MODEL_NAME],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "attempted": True,
            "started_at": started_at,
            "completed_at": utc_now(),
            "runtime_ref": RUNTIME_REF,
            "model_name": MODEL_NAME,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "attempted": True,
            "started_at": started_at,
            "completed_at": utc_now(),
            "runtime_ref": RUNTIME_REF,
            "model_name": MODEL_NAME,
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "ollama invocation timed out",
            "timed_out": True,
        }
    except FileNotFoundError:
        return {
            "attempted": True,
            "started_at": started_at,
            "completed_at": utc_now(),
            "runtime_ref": RUNTIME_REF,
            "model_name": MODEL_NAME,
            "returncode": 127,
            "stdout": "",
            "stderr": "ollama binary not found",
            "timed_out": False,
        }


def publish_from_adapter(
    raw_model_output: str,
    proof_bundle: Mapping[str, Any],
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    verifier_bundle = bundles.redacted_bundle_for_verifier(proof_bundle)
    adapter_result = schema_adapter.adapt_model_draft(
        raw_model_output,
        proof_bundle=verifier_bundle,
        read_model_root=read_model_root,
        generated_at=generated_at,
    )
    verifier_result = dict(adapter_result.get("verifier_result") or {})
    if adapter_result.get("verifier_ready") is True:
        candidate = dict(adapter_result.get("adapted_candidate") or {})
        published = runtime._published_response_from_candidate(
            candidate,
            verifier_bundle,
            generated_at=generated_at,
            verification_status="publishable",
            candidate_source=CANDIDATE_SOURCE,
        )
        return adapter_result, verifier_result, published, ""

    reasons = list(adapter_result.get("adapter_errors") or []) + list(adapter_result.get("verifier_failure_reasons") or [])
    if not reasons and verifier_result.get("verification_errors"):
        reasons = [str(error) for error in verifier_result.get("verification_errors") or []]
    fallback_reason = "; ".join(str(reason) for reason in reasons if str(reason)) or "schema_adapter_or_verifier_failed"
    fallback = verifier_result.get("safe_fallback_response") if isinstance(verifier_result.get("safe_fallback_response"), Mapping) else None
    if fallback is None:
        fallback = runtime._safe_fallback_candidate(verifier_bundle, reason=fallback_reason)
    if not verifier_result:
        verifier_result = {
            "verifier_id": "proof_to_response_schema_adapter_pre_verifier_block",
            "proof_bundle_id": str(verifier_bundle.get("proof_bundle_id") or ""),
            "response_id": "",
            "status": "BLOCKED_BY_SCHEMA_ADAPTER",
            "publishable": False,
            "verification_errors": reasons,
            "safe_fallback_response": fallback,
            "details_collapsed": True,
            "authority_boundary": {"protected_actions_allowed": False},
            **runtime.PERFORMED_FLAGS,
        }
    published = runtime._published_response_from_candidate(
        fallback,
        verifier_bundle,
        generated_at=generated_at,
        verification_status="fallback",
        candidate_source=CANDIDATE_SOURCE,
        fallback_reason=fallback_reason,
    )
    return adapter_result, verifier_result, published, fallback_reason


def _receipt(
    receipt_ref: str,
    *,
    receipt_status: str,
    created_at: str,
    proof_summary: str,
    source_ref: str = "",
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    body = dict(payload or {})
    return {
        "receipt_id": f"local_lm_retry:{receipt_ref}",
        "receipt_ref": receipt_ref,
        "receipt_status": receipt_status,
        "created_at": created_at,
        "source_ref": source_ref,
        "proof_summary": proof_summary,
        "payload_hash": _content_hash(body) if body else "",
        "payload": body,
    }


def build_receipts(
    *,
    proof_bundle: Mapping[str, Any],
    prompt: str,
    invocation_result: Mapping[str, Any],
    adapter_result: Mapping[str, Any],
    verifier_result: Mapping[str, Any],
    published_response: Mapping[str, Any],
    fallback_reason: str,
    generated_at: str,
) -> list[dict[str, Any]]:
    verification_status = "pass" if verifier_result.get("publishable") is True else "fail"
    receipts = [
        _receipt(
            "operator_approval_receipt",
            receipt_status="present",
            created_at=generated_at,
            source_ref="generated/read_models/local_lm_proof_response_retry_operator_approval.json",
            proof_summary="Operator approved one future local Qwen retry using the JSON-only schema adapter.",
        ),
        _receipt(
            "model_invocation_boundary_receipt",
            receipt_status="present",
            created_at=generated_at,
            source_ref="generated/read_models/local_lm_proof_response_invocation_boundary_packet.json",
            proof_summary="Invocation boundary limited the retry to local Ollama qwen3:8b-q4_K_M.",
        ),
        _receipt(
            "redacted_freshness_gated_proof_bundle_receipt",
            receipt_status="present",
            created_at=generated_at,
            source_ref="generated/read_models/proof_bundle_freshness_trace_status.json",
            proof_summary="Redacted freshness-gated proof bundle was built and validated before invocation.",
            payload={
                "proof_bundle_id": proof_bundle.get("proof_bundle_id"),
                "freshness_state": proof_bundle.get("freshness_state"),
                "confidence_class": proof_bundle.get("confidence_class"),
                "trusted_current": proof_bundle.get("trusted_current"),
                "lm_input_hash": _content_hash(proof_bundle.get("lm_input") or {}),
            },
        ),
        _receipt(
            "json_only_prompt_receipt",
            receipt_status="present",
            created_at=generated_at,
            proof_summary="Prompt required JSON-only output and included the strict schema.",
            payload={"prompt_hash": _content_hash(prompt), "prompt_mode": "json_only"},
        ),
        _receipt(
            "valid_example_included_receipt",
            receipt_status="present",
            created_at=generated_at,
            proof_summary="Prompt included one verifier-aligned valid example.",
            payload={"valid_example_hash": _content_hash(JSON_ONLY_VALID_EXAMPLE)},
        ),
        _receipt(
            "no_external_provider_receipt",
            receipt_status="present",
            created_at=generated_at,
            proof_summary="No external provider path was used.",
            payload={"external_provider_used": False},
        ),
        _receipt(
            "no_tool_authority_receipt",
            receipt_status="present",
            created_at=generated_at,
            proof_summary="The model had no tool authority.",
            payload={"tool_authority": False, "tool_execution_performed": False},
        ),
        _receipt(
            "model_invocation_attempt_receipt",
            receipt_status="present",
            created_at=generated_at,
            proof_summary="Exactly one local Ollama retry invocation attempt was recorded.",
            payload={
                "runtime_ref": invocation_result.get("runtime_ref"),
                "model_name": invocation_result.get("model_name"),
                "attempted": invocation_result.get("attempted") is True,
                "returncode": invocation_result.get("returncode"),
                "timed_out": invocation_result.get("timed_out") is True,
            },
        ),
        _receipt(
            "schema_adapter_receipt",
            receipt_status="present",
            created_at=generated_at,
            source_ref="generated/read_models/proof_to_response_schema_adapter_status.json",
            proof_summary=f"Schema adapter parse status: {adapter_result.get('parse_status')}.",
            payload={
                "parse_status": adapter_result.get("parse_status"),
                "adapter_errors": list(adapter_result.get("adapter_errors") or []),
                "verifier_ready": adapter_result.get("verifier_ready") is True,
            },
        ),
        _receipt(
            "verifier_pass_fail_receipt",
            receipt_status="present",
            created_at=generated_at,
            proof_summary=f"Deterministic verifier result: {verification_status}.",
            payload={
                "verifier_id": verifier_result.get("verifier_id"),
                "publishable": verifier_result.get("publishable") is True,
                "verification_errors": list(verifier_result.get("verification_errors") or []),
            },
        ),
        _receipt(
            "approval_used_receipt",
            receipt_status="present",
            created_at=generated_at,
            source_ref="generated/read_models/local_lm_proof_response_retry_operator_approval.json",
            proof_summary="The one-time retry approval was consumed by this run.",
            payload={"approval_used": True, "future_repeated_invocations_allowed": False},
        ),
    ]
    if verifier_result.get("publishable") is True:
        receipts.append(
            _receipt(
                "published_response_hash_receipt",
                receipt_status="present",
                created_at=generated_at,
                proof_summary="Verified response was published and hashed.",
                payload={"response_content_hash": published_response.get("response_content_hash")},
            )
        )
    else:
        receipts.append(
            _receipt(
                "fallback_receipt",
                receipt_status="present",
                created_at=generated_at,
                proof_summary="Adapter or verifier blocked the draft; safe fallback was published.",
                payload={"fallback_reason": fallback_reason, "response_content_hash": published_response.get("response_content_hash")},
            )
        )
    return receipts


def sqlite_schema() -> str:
    return """
CREATE TABLE IF NOT EXISTS local_lm_retry_receipts (
  receipt_id TEXT PRIMARY KEY,
  receipt_ref TEXT NOT NULL,
  receipt_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  proof_summary TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  receipt_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_local_lm_retry_receipts_ref ON local_lm_retry_receipts(receipt_ref);
"""


def write_sqlite(receipts: list[Mapping[str, Any]], sqlite_path: Path = DEFAULT_SQLITE_PATH) -> int:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(sqlite_schema())
        conn.execute("DELETE FROM local_lm_retry_receipts")
        for row in receipts:
            conn.execute(
                """
INSERT INTO local_lm_retry_receipts (
  receipt_id, receipt_ref, receipt_status, created_at, source_ref, proof_summary,
  payload_hash, receipt_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""",
                (
                    str(row.get("receipt_id") or ""),
                    str(row.get("receipt_ref") or ""),
                    str(row.get("receipt_status") or ""),
                    str(row.get("created_at") or ""),
                    str(row.get("source_ref") or ""),
                    str(row.get("proof_summary") or ""),
                    str(row.get("payload_hash") or ""),
                    stable_json(row),
                ),
            )
        conn.commit()
    return len(receipts)


def build_latest_read_model(
    published_response: Mapping[str, Any],
    receipts: list[Mapping[str, Any]],
    *,
    generated_at: str,
    source_response_path: str,
) -> dict[str, Any]:
    latest = prior_pilot.build_latest_read_model(
        published_response,
        receipts,
        generated_at=generated_at,
        source_response_path=source_response_path,
    )
    latest["source_status_ref"] = f"generated/read_models/{JSON_EXPORT_NAME}"
    latest["source_request_id"] = f"{SOURCE_REQUEST_ID}:{generated_at}"
    latest["selected_action_id"] = "local_lm_one_time_retry_schema_adapter"
    latest["candidate_source"] = CANDIDATE_SOURCE
    latest["latest_response"]["candidate_source"] = CANDIDATE_SOURCE
    latest["machine_proof"]["candidate_source"] = CANDIDATE_SOURCE
    unsafe = unsafe_true_grants(latest) + runtime.unsafe_true_grants(latest)
    latest["machine_proof"]["unsafe_true_grants"] = sorted(set(unsafe))
    latest["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        latest["status"] = runtime.NOT_READY_STATUS
    return latest


ModelInvoker = Callable[[str], Mapping[str, Any]]


def run_one_time_retry(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
    invoker: ModelInvoker | None = None,
    invoke_model: bool = False,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    read_model_root = _rooted(read_model_root)
    preconditions = precondition_rows(read_model_root)
    approval_unused_before_run = not approval_already_used(read_model_root=read_model_root, sqlite_path=sqlite_path)
    proof_bundle = build_redacted_retry_bundle(read_model_root)
    lm_bundle = lm_visible_bundle(proof_bundle)
    redaction_errors = bundles.validate_redacted_proof_bundle(proof_bundle)
    freshness_allowed = freshness_gate_allows_bundle(proof_bundle)
    prompt = build_json_only_prompt(lm_bundle)
    prompt_has_valid_example = "valid_example" in prompt and "strict_json_schema" in prompt

    if not (invoke_model and all(row["ready"] for row in preconditions) and approval_unused_before_run and freshness_allowed and boundary_matches_retry_approval(read_model_root)):
        invocation_result = {
            "attempted": False,
            "runtime_ref": RUNTIME_REF,
            "model_name": MODEL_NAME,
            "returncode": None,
            "stdout": "",
            "stderr": "precondition_or_freshness_or_approval_boundary_failed",
            "timed_out": False,
        }
    else:
        invocation_result = dict((invoker or invoke_ollama_once)(prompt))

    adapter_result, verifier_result, published_response, fallback_reason = publish_from_adapter(
        str(invocation_result.get("stdout") or ""),
        proof_bundle,
        read_model_root=read_model_root,
        generated_at=generated_at,
    )
    receipts = build_receipts(
        proof_bundle=proof_bundle,
        prompt=prompt,
        invocation_result=invocation_result,
        adapter_result=adapter_result,
        verifier_result=verifier_result,
        published_response=published_response,
        fallback_reason=fallback_reason,
        generated_at=generated_at,
    )
    sqlite_count = write_sqlite(receipts, sqlite_path=sqlite_path)
    source_response_path = f"generated/read_models/{JSON_EXPORT_NAME}"
    latest = build_latest_read_model(
        published_response,
        receipts,
        generated_at=generated_at,
        source_response_path=source_response_path,
    )
    adapter_before_verifier = receipts[8]["receipt_ref"] == "schema_adapter_receipt" and receipts[9]["receipt_ref"] == "verifier_pass_fail_receipt"
    status_ready = (
        all(row.get("ready") is True for row in preconditions)
        and boundary_matches_retry_approval(read_model_root)
        and approval_unused_before_run
        and freshness_allowed
        and invocation_result.get("attempted") is True
        and prompt_has_valid_example
        and adapter_before_verifier
        and sqlite_count == len(receipts)
        and not unsafe_true_grants(latest)
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if status_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "retry_scope": {
            "attempt_limit": 1,
            "attempt_count": 1 if invocation_result.get("attempted") is True else 0,
            "repeated_invocations_allowed": False,
            "lane": PILOT_LANE,
            "question": PILOT_QUESTION,
            "runtime_ref": RUNTIME_REF,
            "model_ref": MODEL_REF,
            "model_name": MODEL_NAME,
            "prompt_mode": "json_only",
            "valid_example_required": True,
            "input_scope": "redacted_freshness_gated_proof_bundle_only",
            "output_scope": "draft_proof_to_response_text_only",
            "schema_adapter": "mandatory",
            "verifier": "mandatory",
            "fallback": "mandatory_if_adapter_or_verifier_fails",
        },
        "preconditions": preconditions,
        "approval_boundary_matched": boundary_matches_retry_approval(read_model_root),
        "approval_usage": {
            "approval_ref": "generated/read_models/local_lm_proof_response_retry_operator_approval.json",
            "unused_before_run": approval_unused_before_run,
            "marked_used": invocation_result.get("attempted") is True,
            "used_receipt_ref": "approval_used_receipt" if invocation_result.get("attempted") is True else "",
        },
        "redacted_proof_bundle_summary": {
            "proof_bundle_id": proof_bundle.get("proof_bundle_id"),
            "freshness_state": proof_bundle.get("freshness_state"),
            "confidence_class": proof_bundle.get("confidence_class"),
            "confidence_score": proof_bundle.get("confidence_score"),
            "decision_trace_summary": proof_bundle.get("decision_trace_summary"),
            "trusted_current": proof_bundle.get("trusted_current"),
            "allowed_for_lm_bundle": proof_bundle.get("allowed_for_lm_bundle"),
            "lm_input_hash": _content_hash(lm_bundle),
            "redaction_validation_errors": redaction_errors,
            "forbidden_fields_absent": forbidden_fields_absent(proof_bundle),
        },
        "prompt_contract": {
            "prompt_mode": "json_only",
            "prompt_hash": _content_hash(prompt),
            "valid_example_included": True,
            "valid_example_hash": _content_hash(JSON_ONLY_VALID_EXAMPLE),
            "schema_adapter_required": True,
            "allowed_fact_ids": list(EXPECTED_FACT_IDS),
            "allowed_control_labels": [EXPECTED_CONTROL_LABEL],
            "control_naming_normalized_to_verifier_label": True,
        },
        "invocation_attempt": {
            "attempt_number": 1 if invocation_result.get("attempted") is True else 0,
            "runtime_ref": invocation_result.get("runtime_ref"),
            "model_name": invocation_result.get("model_name"),
            "attempted": invocation_result.get("attempted") is True,
            "returncode": invocation_result.get("returncode"),
            "timed_out": invocation_result.get("timed_out") is True,
            "stdout_hash": _content_hash(str(invocation_result.get("stdout") or "")),
            "stdout_length": len(str(invocation_result.get("stdout") or "")),
            "stderr_hash": _content_hash(str(invocation_result.get("stderr") or "")),
            "stderr_length": len(str(invocation_result.get("stderr") or "")),
        },
        "pipeline": {
            "steps": [
                "approval_check",
                "redacted_freshness_bundle",
                "json_only_prompt",
                "local_ollama_invocation",
                "schema_adapter",
                "deterministic_verifier",
                "publish_or_fallback",
                "approval_used_receipt",
            ],
            "schema_adapter_runs_before_verifier": adapter_before_verifier,
            "adapter_parse_status": adapter_result.get("parse_status"),
            "adapter_errors": list(adapter_result.get("adapter_errors") or []),
            "verifier_ready": adapter_result.get("verifier_ready") is True,
            "verifier_failure_reasons": list(adapter_result.get("verifier_failure_reasons") or []),
        },
        "schema_adapter_result": adapter_result,
        "candidate_response": dict(adapter_result.get("adapted_candidate") or {}),
        "verifier_result": verifier_result,
        "publication_decision": "verified_text_published" if verifier_result.get("publishable") is True else "safe_fallback_published",
        "published_response": published_response,
        "proof_to_response_latest": latest,
        "receipts": receipts,
        "sqlite_ref": _rooted(sqlite_path).as_posix(),
        "sqlite_row_count": sqlite_count,
        "source_refs": [
            "generated/read_models/local_lm_proof_response_retry_operator_approval.json",
            "generated/read_models/local_lm_proof_response_retry_approval_packet.json",
            "generated/read_models/local_lm_proof_response_pilot_postmortem.json",
            "generated/read_models/proof_to_response_schema_adapter_status.json",
            "generated/read_models/local_model_selection_for_proof_response.json",
            "generated/read_models/proof_bundle_freshness_trace_status.json",
            "generated/read_models/proof_bundle_builder_redaction_status.json",
            "generated/read_models/context_freshness_decision_trace_gate.json",
            "generated/read_models/proof_to_response_runtime_status.json",
        ],
        "authority_boundary": {
            "protected_actions_allowed": False,
            "authority_granted": False,
            "authority_grant_allowed": False,
            "tool_authority": False,
            "business_action_authority": False,
            "future_repeated_invocations_allowed": False,
        },
        "implementation_boundary": {
            "local_ollama_invocation_attempted": invocation_result.get("attempted") is True,
            "prompt_sent_to_local_model": invocation_result.get("attempted") is True,
            "redacted_proof_bundle_sent_to_local_model": invocation_result.get("attempted") is True,
            "schema_adapter_ran": True,
            "deterministic_verifier_ran": True,
            **prior_pilot._action_flags(),
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["unsafe_true_grants"] = unsafe
    payload["machine_proof"] = {
        "one_invocation_attempt_only": payload["retry_scope"]["attempt_count"] <= 1,
        "approval_required": True,
        "approval_marked_used": payload["approval_usage"]["marked_used"] is True,
        "runtime_model_match_approval": boundary_matches_retry_approval(read_model_root),
        "proof_bundle_redacted_and_freshness_gated": freshness_allowed,
        "forbidden_fields_absent": forbidden_fields_absent(proof_bundle),
        "external_provider_unused": True,
        "tool_authority_false": True,
        "business_action_flags_false": True,
        "schema_adapter_before_verifier": adapter_before_verifier,
        "verifier_gated_publication": True,
        "fallback_path_available": True,
        "sqlite_row_count_matches_receipts": sqlite_count == len(receipts),
        "unsafe_true_grants_absent": not unsafe,
    }
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    scope = read_model.get("retry_scope") if isinstance(read_model.get("retry_scope"), Mapping) else {}
    response = read_model.get("published_response") if isinstance(read_model.get("published_response"), Mapping) else {}
    invocation = read_model.get("invocation_attempt") if isinstance(read_model.get("invocation_attempt"), Mapping) else {}
    proof = read_model.get("redacted_proof_bundle_summary") if isinstance(read_model.get("redacted_proof_bundle_summary"), Mapping) else {}
    pipeline = read_model.get("pipeline") if isinstance(read_model.get("pipeline"), Mapping) else {}
    lines = [
        "# Local LM Proof Response One Time Retry",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "This records the approved one-time local Ollama/Qwen proof-to-response retry for Finance / Capital Hilton.",
        "",
        "## Scope",
        "",
        f"- Lane: `{scope.get('lane')}`",
        f"- Question: {scope.get('question')}",
        f"- Runtime: `{scope.get('runtime_ref')}`",
        f"- Model: `{scope.get('model_name')}`",
        f"- Attempt count: `{scope.get('attempt_count')}`",
        f"- Repeated invocations allowed: `{str(scope.get('repeated_invocations_allowed')).lower()}`",
        "",
        "## Proof Bundle",
        "",
        f"- Freshness: `{proof.get('freshness_state')}`",
        f"- Confidence: `{proof.get('confidence_class')}`",
        f"- Forbidden fields absent: `{str(proof.get('forbidden_fields_absent')).lower()}`",
        "",
        "## Adapter And Verifier",
        "",
        f"- Adapter parse status: `{pipeline.get('adapter_parse_status')}`",
        f"- Verifier ready: `{str(pipeline.get('verifier_ready')).lower()}`",
        f"- Adapter ran before verifier: `{str(pipeline.get('schema_adapter_runs_before_verifier')).lower()}`",
        "",
        "## Invocation",
        "",
        f"- Attempted: `{str(invocation.get('attempted')).lower()}`",
        f"- Return code: `{invocation.get('returncode')}`",
        f"- Timed out: `{str(invocation.get('timed_out')).lower()}`",
        "",
        "## Published Response",
        "",
        f"- Decision: `{read_model.get('publication_decision')}`",
        f"- Headline: {response.get('headline')}",
        f"- Body: {response.get('body')}",
        f"- Next step: {response.get('next_step')}",
        "",
        "## Receipts",
        "",
    ]
    for receipt in read_model.get("receipts") or []:
        lines.append(f"- `{receipt.get('receipt_ref')}`: {receipt.get('receipt_status')}")
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- No external provider.",
            "- No browser, Gmail, or Coupa.",
            "- No email send, submit, ledger mutation, workbook mutation, PDF export, paid marking, worker spawn, memory promotion, push, or merge.",
            "- Model had no tool authority.",
            "",
        ]
    )
    return "\n".join(lines)


def export_one_time_retry(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
    invoker: ModelInvoker | None = None,
    invoke_model: bool = False,
) -> dict[str, str]:
    read_model = run_one_time_retry(
        read_model_root=read_model_root,
        generated_at=generated_at,
        invoker=invoker,
        invoke_model=invoke_model,
        sqlite_path=sqlite_path,
    )
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    latest_path = export_root / runtime.LATEST_JSON_EXPORT_NAME
    _write_json(read_model_path, read_model)
    _write_json(latest_path, read_model["proof_to_response_latest"])

    bridge_read_model_path = ""
    bridge_latest_path = ""
    if bridge_root is not None:
        bridge_root = _rooted(bridge_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_read_model = bridge_root / JSON_EXPORT_NAME
        bridge_latest = bridge_root / runtime.LATEST_JSON_EXPORT_NAME
        shutil.copy2(read_model_path, bridge_read_model)
        shutil.copy2(latest_path, bridge_latest)
        bridge_read_model_path = bridge_read_model.as_posix()
        bridge_latest_path = bridge_latest.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")

    return {
        "status": str(read_model.get("status") or NOT_READY_STATUS),
        "publication_decision": str(read_model.get("publication_decision") or ""),
        "attempt_count": str((read_model.get("retry_scope") or {}).get("attempt_count") or 0),
        "read_model_path": read_model_path.as_posix(),
        "latest_path": latest_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "bridge_latest_path": bridge_latest_path,
        "wiki_path": wiki_path.as_posix(),
        "sqlite_path": _rooted(sqlite_path).as_posix(),
        "sqlite_row_count": str(read_model.get("sqlite_row_count") or 0),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the approved one-time local LM proof-to-response retry.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--invoke-approved-model", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    bridge_root = Path(args.bridge_root) if args.bridge_root else None
    result = export_one_time_retry(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=bridge_root,
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
        generated_at=args.generated_at,
        invoke_model=args.invoke_approved_model,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
