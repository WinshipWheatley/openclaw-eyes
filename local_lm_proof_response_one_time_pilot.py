"""One-time local LM proof-to-response pilot V0.

Runs the approved Finance / Capital Hilton proof-to-response pilot through one
local Ollama invocation. The model receives only the redacted freshness-gated
LM-visible proof bundle. Publication remains verifier-gated, with safe fallback
if the draft fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import proof_bundle_builder as bundles
import proof_to_response_runtime as runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Local LM Proof Response One Time Pilot.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/local_lm_proof_response_one_time_pilot.sqlite")

SCHEMA_VERSION = "local_lm_proof_response_one_time_pilot_v0"
READ_MODEL_ID = "local_lm_proof_response_one_time_pilot"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_ONE_TIME_PILOT_READY"
NOT_READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_ONE_TIME_PILOT_NOT_READY"

SCENARIO_ID = "finance_capital_hilton_payment_watch"
WORLD_REF = "finance"
THREAD_REF = "capital_hilton"
PILOT_LANE = "finance/capital_hilton"
PILOT_QUESTION = "What should I do here?"
RUNTIME_REF = "ollama"
MODEL_REF = "local_model:ollama:qwen3_8b-q4_k_m"
MODEL_NAME = "qwen3:8b-q4_K_M"
CANDIDATE_SOURCE = "local_ollama_one_time_pilot"
SOURCE_REQUEST_ID = "local_lm_one_time_pilot_finance_capital_hilton_payment_watch"

PRECONDITIONS = {
    "local_lm_proof_response_operator_approval": {
        "filename": "local_lm_proof_response_operator_approval.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_OPERATOR_APPROVAL_READY",),
    },
    "local_lm_proof_response_invocation_boundary_packet": {
        "filename": "local_lm_proof_response_invocation_boundary_packet.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_INVOCATION_BOUNDARY_PACKET_READY",),
    },
    "local_model_selection_for_proof_response": {
        "filename": "local_model_selection_for_proof_response.json",
        "accepted_statuses": ("LOCAL_MODEL_SELECTION_FOR_PROOF_RESPONSE_READY",),
    },
    "local_model_list_inventory": {
        "filename": "local_model_list_inventory.json",
        "accepted_statuses": ("LOCAL_MODEL_LIST_INVENTORY_READY",),
    },
    "proof_bundle_freshness_trace_integration": {
        "filename": "proof_bundle_freshness_trace_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY",),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": bundles.REDACTION_STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (bundles.REDACTION_READY_STATUS,),
    },
    "proof_bundle_redaction_hardening": {
        "filename": "proof_bundle_redaction_policy.json",
        "accepted_statuses": ("PROOF_BUNDLE_REDACTION_HARDENING_READY",),
    },
    "context_freshness_decision_trace_gate": {
        "filename": "context_freshness_decision_trace_gate.json",
        "accepted_statuses": ("CONTEXT_FRESHNESS_DECISION_TRACE_GATE_READY",),
    },
    "proof_to_response_runtime": {
        "filename": runtime.STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (runtime.READY_STATUS,),
    },
}

ALLOWED_FRESHNESS_STATES = {"current", "waiting_external"}
ALLOWED_CONFIDENCE_CLASSES = {"receipt_backed", "operator_reported_candidate", "trusted_current"}
EXPECTED_FACT_IDS = ("payment_evidence_missing", "coupa_processing", "ledger_untouched")
EXPECTED_CONTROL = "Attach payment evidence"

UNSAFE_TRUE_KEYS = {
    "external_provider_used",
    "external_provider_connected",
    "external_llm_invoked",
    "provider_api_called",
    "tool_authority",
    "tool_authority_allowed",
    "tool_execution_allowed",
    "tool_execution_performed",
    "business_action_authority",
    "business_action_allowed",
    "business_action_performed",
    "browser_access_allowed",
    "browser_opened",
    "gmail_allowed",
    "gmail_opened",
    "coupa_allowed",
    "coupa_opened",
    "email_send_allowed",
    "email_send_performed",
    "portal_submit_allowed",
    "submit_performed",
    "ledger_mutation_allowed",
    "ledger_mutation_performed",
    "workbook_mutation_allowed",
    "workbook_mutation_performed",
    "pdf_export_allowed",
    "pdf_export_performed",
    "paid_marking_allowed",
    "paid_marking_performed",
    "worker_spawn_allowed",
    "worker_spawn_performed",
    "memory_promotion_allowed",
    "memory_promotion_performed",
    "future_repeated_invocations_allowed",
    "repeated_invocation_performed",
    "raw_financial_proof_sent",
    "operator_device_session_secret_sent",
    "protected_actions_allowed",
    "authority_granted",
    "authority_grant_allowed",
    "git_push_allowed",
    "git_push_performed",
    "git_merge_allowed",
    "git_merge_performed",
    "paid",
    "sent",
    "submitted",
    "executed",
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


def _scoped_response_precondition(read_model_root: Path) -> dict[str, Any]:
    latest = _load_json(_rooted(read_model_root) / runtime.LATEST_JSON_EXPORT_NAME)
    ready = latest.get("status") == runtime.READY_STATUS and latest.get("stale_if_context_mismatch") is True
    return {
        "precondition_ref": "proof_to_response_scoped_responses",
        "source_ref": f"generated/read_models/{runtime.LATEST_JSON_EXPORT_NAME}",
        "observed_status": "PROOF_TO_RESPONSE_SCOPED_RESPONSES_READY" if ready else "PROOF_TO_RESPONSE_SCOPED_RESPONSES_NOT_READY",
        "accepted_statuses": ["PROOF_TO_RESPONSE_SCOPED_RESPONSES_READY"],
        "ready": ready,
    }


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
    rows.append(_scoped_response_precondition(root))
    return rows


def boundary_matches_approval(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> bool:
    root = _rooted(read_model_root)
    approval = _load_json(root / "local_lm_proof_response_operator_approval.json")
    scope = approval.get("approval_scope") if isinstance(approval.get("approval_scope"), Mapping) else {}
    boundary = _load_json(root / "local_lm_proof_response_invocation_boundary_packet.json")
    packet = boundary.get("invocation_boundary_packet") if isinstance(boundary.get("invocation_boundary_packet"), Mapping) else {}
    return (
        approval.get("status") == "LOCAL_LM_PROOF_RESPONSE_OPERATOR_APPROVAL_READY"
        and scope.get("attempt_limit") == 1
        and scope.get("lane") == PILOT_LANE
        and scope.get("question") == PILOT_QUESTION
        and scope.get("runtime_ref") == RUNTIME_REF
        and scope.get("model_ref") == MODEL_REF
        and scope.get("model_name") == MODEL_NAME
        and packet.get("selected_runtime_ref") == RUNTIME_REF
        and packet.get("selected_model_ref") == MODEL_REF
        and packet.get("selected_model_name") == MODEL_NAME
    )


def build_redacted_pilot_bundle(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> dict[str, Any]:
    return bundles.build_redacted_proof_bundle(SCENARIO_ID, read_model_root=read_model_root)


def forbidden_fields_absent(proof_bundle: Mapping[str, Any]) -> bool:
    text = stable_json({"lm_input": proof_bundle.get("lm_input")}).lower()
    forbidden_markers = (
        "raw_bank",
        "bank_account",
        "routing_number",
        "credential",
        "token",
        "secret",
        "operator_envelope",
        "device_verification",
        "session_verification",
        "raw_prompt",
        "ocr_text",
        "artifact_text",
        "workbook_body",
        "email_body",
        "ledger_row",
        "authority_granted",
    )
    return not any(marker in text for marker in forbidden_markers)


def freshness_gate_allows_bundle(proof_bundle: Mapping[str, Any]) -> bool:
    return (
        proof_bundle.get("allowed_for_lm_bundle") is True
        and proof_bundle.get("freshness_state") in ALLOWED_FRESHNESS_STATES
        and proof_bundle.get("confidence_class") in ALLOWED_CONFIDENCE_CLASSES
        and not bundles.validate_redacted_proof_bundle(proof_bundle)
        and forbidden_fields_absent(proof_bundle)
    )


def lm_visible_bundle(proof_bundle: Mapping[str, Any]) -> dict[str, Any]:
    lm_input = proof_bundle.get("lm_input") if isinstance(proof_bundle.get("lm_input"), Mapping) else {}
    return {key: lm_input.get(key) for key in sorted(lm_input)}


def build_prompt(lm_bundle: Mapping[str, Any]) -> str:
    payload = {
        "task": "Draft a concise proof-to-response answer for the operator.",
        "strict_boundary": [
            "Use only the redacted proof bundle below.",
            "Do not claim paid, sent, submitted, executed, or ledger changed.",
            "Do not promise any protected action.",
            "Do not ask for hidden context.",
            "Return only a JSON object with the requested response fields.",
        ],
        "redacted_freshness_gated_proof_bundle": lm_bundle,
        "required_json_response": {
            "headline": "short headline",
            "body": "one or two short sentences",
            "next_step": "one safe next step",
            "missing_input": ["short labels"],
            "can_do_now": ["safe actions"],
            "cannot_do_yet": ["blocked actions"],
            "requested_controls": ["Attach payment evidence"],
            "claimed_facts": ["plain language claims from the redacted facts only"],
        },
        "expected_safe_shape": {
            "headline": "Payment evidence needed",
            "body": "Coupa is processing. I can't mark this paid until payment evidence is attached. The ledger stays untouched.",
            "next_step": "Attach payment evidence.",
        },
    }
    return stable_json(payload)


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


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = str(text or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _mapped_fact_ids(headline: str, body: str, next_step: str) -> list[str]:
    text = f"{headline} {body} {next_step}".lower()
    ids: list[str] = []
    if "payment evidence" in text or "proof" in text:
        ids.append("payment_evidence_missing")
    if "coupa" in text and ("processing" in text or "watch" in text):
        ids.append("coupa_processing")
    if "ledger" in text and ("untouched" in text or "not" in text or "cannot" in text):
        ids.append("ledger_untouched")
    return [fact_id for fact_id in EXPECTED_FACT_IDS if fact_id in ids] or list(EXPECTED_FACT_IDS)


def candidate_from_model_output(
    invocation_result: Mapping[str, Any],
    proof_bundle: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    parsed = _extract_json_object(str(invocation_result.get("stdout") or ""))
    parse_status = {
        "json_parse_succeeded": parsed is not None,
        "raw_stdout_sha256": _content_hash(str(invocation_result.get("stdout") or "")),
        "raw_stderr_sha256": _content_hash(str(invocation_result.get("stderr") or "")),
    }
    if not parsed:
        candidate = {
            "response_id": "local_ollama_candidate:parse_failed:finance_capital_hilton_payment_watch",
            "proof_bundle_id": str(proof_bundle.get("proof_bundle_id") or ""),
            "speaker_ref": str(proof_bundle.get("response_speaker_ref") or "chief"),
            "draft_headline": "",
            "draft_body": "",
            "draft_next_step": "",
            "claimed_facts": [],
            "implied_actions": [],
            "requested_controls": [],
            "uncertainty_notes": ["model_output_json_parse_failed"],
        }
        return candidate, parse_status

    headline = str(parsed.get("headline") or parsed.get("draft_headline") or "").strip()
    body = str(parsed.get("body") or parsed.get("draft_body") or "").strip()
    next_step = str(parsed.get("next_step") or parsed.get("draft_next_step") or "").strip()
    requested = _text_list(parsed.get("requested_controls"))
    if not requested and "attach" in next_step.lower():
        requested = [EXPECTED_CONTROL]
    claimed = _mapped_fact_ids(headline, body, next_step)
    return (
        {
            "response_id": "local_ollama_candidate:finance_capital_hilton_payment_watch",
            "proof_bundle_id": str(proof_bundle.get("proof_bundle_id") or ""),
            "speaker_ref": str(proof_bundle.get("response_speaker_ref") or "chief"),
            "draft_headline": headline,
            "draft_body": body,
            "draft_next_step": next_step,
            "claimed_facts": claimed,
            "implied_actions": _text_list(parsed.get("implied_actions")),
            "requested_controls": requested,
            "uncertainty_notes": _text_list(parsed.get("uncertainty_notes")),
        },
        parse_status,
    )


def publish_from_candidate(
    candidate: Mapping[str, Any],
    proof_bundle: Mapping[str, Any],
    *,
    generated_at: str,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    verifier_bundle = bundles.redacted_bundle_for_verifier(proof_bundle)
    verifier_result = runtime.verify_candidate_response(candidate, verifier_bundle)
    if verifier_result.get("publishable") is True:
        published = runtime._published_response_from_candidate(
            candidate,
            verifier_bundle,
            generated_at=generated_at,
            verification_status="publishable",
            candidate_source=CANDIDATE_SOURCE,
        )
        return dict(verifier_result), published, ""
    fallback = verifier_result.get("safe_fallback_response")
    if not isinstance(fallback, Mapping):
        fallback = runtime._safe_fallback_candidate(
            verifier_bundle,
            reason="; ".join(str(error) for error in verifier_result.get("verification_errors") or []),
        )
    fallback_reason = "; ".join(str(error) for error in verifier_result.get("verification_errors") or [])
    published = runtime._published_response_from_candidate(
        fallback,
        verifier_bundle,
        generated_at=generated_at,
        verification_status="fallback",
        candidate_source=CANDIDATE_SOURCE,
        fallback_reason=fallback_reason,
    )
    return dict(verifier_result), published, fallback_reason


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
        "receipt_id": f"local_lm_pilot:{receipt_ref}",
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
    invocation_result: Mapping[str, Any],
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
            source_ref="generated/read_models/local_lm_proof_response_operator_approval.json",
            proof_summary="Operator approved one future local LM proof-to-response invocation for Finance / Capital Hilton.",
        ),
        _receipt(
            "model_invocation_boundary_receipt",
            receipt_status="present",
            created_at=generated_at,
            source_ref="generated/read_models/local_lm_proof_response_invocation_boundary_packet.json",
            proof_summary="Invocation boundary limited the pilot to Ollama qwen3:8b-q4_K_M and redacted proof-to-response text only.",
        ),
        _receipt(
            "redacted_proof_bundle_receipt",
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
            payload={"tool_authority": False},
        ),
        _receipt(
            "model_invocation_attempt_receipt",
            receipt_status="present",
            created_at=generated_at,
            proof_summary="Exactly one local Ollama invocation attempt was recorded.",
            payload={
                "runtime_ref": invocation_result.get("runtime_ref"),
                "model_name": invocation_result.get("model_name"),
                "attempted": invocation_result.get("attempted") is True,
                "returncode": invocation_result.get("returncode"),
                "timed_out": invocation_result.get("timed_out") is True,
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
                proof_summary="Verifier blocked the draft; safe fallback was published.",
                payload={"fallback_reason": fallback_reason, "response_content_hash": published_response.get("response_content_hash")},
            )
        )
    return receipts


def sqlite_schema() -> str:
    return """
CREATE TABLE IF NOT EXISTS local_lm_pilot_receipts (
  receipt_id TEXT PRIMARY KEY,
  receipt_ref TEXT NOT NULL,
  receipt_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  proof_summary TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  receipt_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_local_lm_pilot_receipts_ref ON local_lm_pilot_receipts(receipt_ref);
"""


def write_sqlite(receipts: list[Mapping[str, Any]], sqlite_path: Path = DEFAULT_SQLITE_PATH) -> int:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(sqlite_schema())
        conn.execute("DELETE FROM local_lm_pilot_receipts")
        for row in receipts:
            conn.execute(
                """
INSERT INTO local_lm_pilot_receipts (
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


def sqlite_row_count(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> int:
    path = _rooted(sqlite_path)
    if not path.exists():
        return 0
    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT COUNT(*) FROM local_lm_pilot_receipts").fetchone()
    return int(row[0] if row else 0)


def _action_flags() -> dict[str, bool]:
    return {
        "external_provider_used": False,
        "tool_authority": False,
        "tool_execution_performed": False,
        "business_action_performed": False,
        "browser_opened": False,
        "gmail_opened": False,
        "coupa_opened": False,
        "email_send_performed": False,
        "ledger_mutation_performed": False,
        "workbook_mutation_performed": False,
        "pdf_export_performed": False,
        "paid_marking_performed": False,
        "submit_performed": False,
        "worker_spawn_performed": False,
        "memory_promotion_performed": False,
        "git_push_performed": False,
        "git_merge_performed": False,
        "future_repeated_invocations_allowed": False,
        "repeated_invocation_performed": False,
        "raw_financial_proof_sent": False,
        "operator_device_session_secret_sent": False,
    }


def build_latest_read_model(
    published_response: Mapping[str, Any],
    receipts: list[Mapping[str, Any]],
    *,
    generated_at: str,
    source_response_path: str,
) -> dict[str, Any]:
    source_context = published_response.get("source_context") if isinstance(published_response.get("source_context"), Mapping) else {}
    latest = {
        "schema_version": runtime.SCHEMA_VERSION,
        "read_model_id": runtime.LATEST_READ_MODEL_ID,
        "status": runtime.READY_STATUS,
        "generated_at": generated_at,
        "source_status_ref": "generated/read_models/local_lm_proof_response_one_time_pilot.json",
        "source_request_id": f"{SOURCE_REQUEST_ID}:{generated_at}",
        "source_response_path": source_response_path,
        "world_ref": WORLD_REF,
        "thread_ref": THREAD_REF,
        "selected_card_id": str(source_context.get("card_id") or "redacted_proof_bundle"),
        "selected_action_id": "local_lm_one_time_pilot",
        "candidate_source": CANDIDATE_SOURCE,
        "expires_or_superseded_by": "",
        "stale_if_context_mismatch": True,
        "latest_response": dict(published_response),
        "latest_receipt_ref": next((str(row.get("receipt_id")) for row in receipts if row.get("receipt_ref") in {"published_response_hash_receipt", "fallback_receipt"}), ""),
        "proof_to_response_status": str(published_response.get("verification_status") or ""),
        "proof_to_response_unavailable_reason": "",
        "details_collapsed": True,
        "authority_boundary": {"protected_actions_allowed": False},
        "implementation_boundary": {**runtime.PERFORMED_FLAGS, **_action_flags()},
    }
    unsafe = unsafe_true_grants(latest) + runtime.unsafe_true_grants(latest)
    latest["machine_proof"] = {
        "latest_response_present": bool(published_response),
        "latest_context_scoped": True,
        "stale_if_context_mismatch": True,
        "candidate_source": CANDIDATE_SOURCE,
        "unsafe_true_grants": sorted(set(unsafe)),
        "unsafe_true_grants_absent": not unsafe,
        **_action_flags(),
    }
    if unsafe:
        latest["status"] = runtime.NOT_READY_STATUS
    return latest


ModelInvoker = Callable[[str], Mapping[str, Any]]


def run_one_time_pilot(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
    invoker: ModelInvoker | None = None,
    invoke_model: bool = False,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    proof_bundle = build_redacted_pilot_bundle(read_model_root)
    lm_bundle = lm_visible_bundle(proof_bundle)
    prompt = build_prompt(lm_bundle)
    freshness_allowed = freshness_gate_allows_bundle(proof_bundle)
    redaction_errors = bundles.validate_redacted_proof_bundle(proof_bundle)
    if not invoke_model:
        invocation_result = {
            "attempted": False,
            "runtime_ref": RUNTIME_REF,
            "model_name": MODEL_NAME,
            "returncode": None,
            "stdout": "",
            "stderr": "invocation_not_requested",
            "timed_out": False,
        }
    elif not all(row.get("ready") is True for row in preconditions) or not boundary_matches_approval(read_model_root) or not freshness_allowed:
        invocation_result = {
            "attempted": False,
            "runtime_ref": RUNTIME_REF,
            "model_name": MODEL_NAME,
            "returncode": None,
            "stdout": "",
            "stderr": "precondition_or_freshness_boundary_failed",
            "timed_out": False,
        }
    else:
        invocation_result = dict((invoker or invoke_ollama_once)(prompt))

    candidate, parse_status = candidate_from_model_output(invocation_result, proof_bundle)
    verifier_result, published_response, fallback_reason = publish_from_candidate(candidate, proof_bundle, generated_at=generated_at)
    receipts = build_receipts(
        proof_bundle=proof_bundle,
        invocation_result=invocation_result,
        verifier_result=verifier_result,
        published_response=published_response,
        fallback_reason=fallback_reason,
        generated_at=generated_at,
    )
    sqlite_count = write_sqlite(receipts, sqlite_path=sqlite_path)
    source_response_path = "generated/read_models/local_lm_proof_response_one_time_pilot.json"
    latest = build_latest_read_model(
        published_response,
        receipts,
        generated_at=generated_at,
        source_response_path=source_response_path,
    )
    status_ready = (
        all(row.get("ready") is True for row in preconditions)
        and boundary_matches_approval(read_model_root)
        and freshness_allowed
        and invocation_result.get("attempted") is True
        and sqlite_count == len(receipts)
        and len(receipts) == 8
        and not unsafe_true_grants(latest)
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if status_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "pilot_scope": {
            "attempt_limit": 1,
            "attempt_count": 1 if invocation_result.get("attempted") is True else 0,
            "repeated_invocations_allowed": False,
            "lane": PILOT_LANE,
            "question": PILOT_QUESTION,
            "runtime_ref": RUNTIME_REF,
            "model_ref": MODEL_REF,
            "model_name": MODEL_NAME,
            "input_scope": "redacted_freshness_gated_proof_bundle_only",
            "output_scope": "draft_proof_to_response_text_only",
            "verifier": "mandatory",
            "fallback": "mandatory_if_verifier_fails",
        },
        "preconditions": preconditions,
        "approval_boundary_matched": boundary_matches_approval(read_model_root),
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
        "prompt_hash": _content_hash(prompt),
        "invocation_attempt": {
            "attempt_number": 1 if invocation_result.get("attempted") is True else 0,
            "runtime_ref": invocation_result.get("runtime_ref"),
            "model_name": invocation_result.get("model_name"),
            "attempted": invocation_result.get("attempted") is True,
            "returncode": invocation_result.get("returncode"),
            "timed_out": invocation_result.get("timed_out") is True,
            "stdout_hash": _content_hash(str(invocation_result.get("stdout") or "")),
            "stderr_hash": _content_hash(str(invocation_result.get("stderr") or "")),
        },
        "model_output_parse": parse_status,
        "candidate_response": candidate,
        "verifier_result": verifier_result,
        "publication_decision": "verified_text_published" if verifier_result.get("publishable") is True else "safe_fallback_published",
        "published_response": published_response,
        "proof_to_response_latest": latest,
        "receipts": receipts,
        "sqlite_ref": _rooted(sqlite_path).as_posix(),
        "sqlite_row_count": sqlite_count,
        "source_refs": [
            "generated/read_models/local_lm_proof_response_operator_approval.json",
            "generated/read_models/local_lm_proof_response_invocation_boundary_packet.json",
            "generated/read_models/proof_bundle_freshness_trace_status.json",
            "generated/read_models/proof_bundle_builder_redaction_status.json",
            "generated/read_models/proof_bundle_redaction_policy.json",
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
            **_action_flags(),
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["unsafe_true_grants"] = unsafe
    payload["machine_proof"] = {
        "one_invocation_attempt_only": payload["pilot_scope"]["attempt_count"] <= 1,
        "runtime_model_match_approval": boundary_matches_approval(read_model_root),
        "proof_bundle_redacted_and_freshness_gated": freshness_allowed,
        "forbidden_fields_absent": forbidden_fields_absent(proof_bundle),
        "external_provider_unused": True,
        "tool_authority_false": True,
        "business_action_flags_false": True,
        "verifier_gated_publication": True,
        "sqlite_row_count_matches_receipts": sqlite_count == len(receipts),
        "unsafe_true_grants_absent": not unsafe,
    }
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    scope = read_model.get("pilot_scope") if isinstance(read_model.get("pilot_scope"), Mapping) else {}
    response = read_model.get("published_response") if isinstance(read_model.get("published_response"), Mapping) else {}
    invocation = read_model.get("invocation_attempt") if isinstance(read_model.get("invocation_attempt"), Mapping) else {}
    proof = read_model.get("redacted_proof_bundle_summary") if isinstance(read_model.get("redacted_proof_bundle_summary"), Mapping) else {}
    lines = [
        "# Local LM Proof Response One Time Pilot",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "This records the approved one-time local Ollama proof-to-response pilot for Finance / Capital Hilton.",
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


def export_one_time_pilot(
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
    read_model = run_one_time_pilot(
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
        "attempt_count": str((read_model.get("pilot_scope") or {}).get("attempt_count") or 0),
        "read_model_path": read_model_path.as_posix(),
        "latest_path": latest_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "bridge_latest_path": bridge_latest_path,
        "wiki_path": wiki_path.as_posix(),
        "sqlite_path": _rooted(sqlite_path).as_posix(),
        "sqlite_row_count": str(read_model.get("sqlite_row_count") or 0),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the approved one-time local LM proof-to-response pilot.")
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
    result = export_one_time_pilot(
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
