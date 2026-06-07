"""Local LM proof-to-response preflight receipts V0.

Collects preflight receipts that can be recorded before live/local model
invocation. This module only reads existing generated read models and writes
generated read-model/wiki/SQLite artifacts. It does not invoke a model, connect
to a runtime, send prompts or proof bundles, start services, spawn workers,
open browser/Gmail/Coupa, mutate ledgers/workbooks, export PDFs, mark paid,
submit, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import local_lm_pilot_harness_selection_packet as harness_selection
import local_lm_runtime_discovery
import proof_to_response_runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Local LM Proof Response Preflight Receipts.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/local_lm_proof_response_preflight_receipts.sqlite")

SCHEMA_VERSION = "local_lm_proof_response_preflight_receipts_v0"
READ_MODEL_ID = "local_lm_proof_response_preflight_receipts"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_PREFLIGHT_RECEIPTS_READY"
NOT_READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_PREFLIGHT_RECEIPTS_NOT_READY"

PILOT_LANE = "finance/capital_hilton"
PILOT_QUESTION = "What should I do here?"

PRECONDITIONS = {
    "local_lm_runtime_discovery": {
        "filename": "local_lm_runtime_discovery.json",
        "accepted_statuses": ("LOCAL_LM_RUNTIME_DISCOVERY_READY",),
    },
    "local_lm_proof_response_pilot_plan": {
        "filename": "local_lm_proof_to_response_pilot_plan.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_PILOT_PLAN_READY",),
    },
    "local_lm_pilot_harness_selection_packet": {
        "filename": "local_lm_pilot_harness_selection_packet.json",
        "accepted_statuses": ("LOCAL_LM_PILOT_HARNESS_SELECTION_PACKET_READY",),
    },
    "proof_bundle_redaction_hardening": {
        "filename": "proof_bundle_redaction_policy.json",
        "accepted_statuses": ("PROOF_BUNDLE_REDACTION_HARDENING_READY",),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": "proof_bundle_builder_redaction_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY",),
    },
    "proof_to_response_runtime": {
        "filename": "proof_to_response_runtime_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_RUNTIME_READY",),
    },
    "proof_to_response_shadow_pilot_runtime": {
        "filename": "proof_to_response_runtime_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_RUNTIME_READY",),
        "active_candidate_source": proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
    },
}

PREFLIGHT_RECEIPT_SPECS = {
    "local_runtime_discovery_receipt": {
        "source_ref": "generated/read_models/local_lm_runtime_discovery.json",
        "proof_summary": "Runtime discovery read model exists and confirms ready_for_pilot=false.",
    },
    "candidate_harness_selected_receipt": {
        "source_ref": "generated/read_models/local_lm_pilot_harness_selection_packet.json",
        "proof_summary": "Harness selection packet identifies the review candidate and keeps invocation blocked.",
    },
    "no_external_provider_receipt": {
        "source_ref": "generated/read_models/local_lm_runtime_discovery.json",
        "proof_summary": "External provider remains blocked; no endpoint or provider call is allowed.",
    },
    "no_tool_authority_receipt": {
        "source_ref": "generated/read_models/local_lm_pilot_harness_selection_packet.json",
        "proof_summary": "Tool authority is false in the harness selection and discovery boundaries.",
    },
    "no_memory_promotion_receipt": {
        "source_ref": "generated/read_models/local_lm_harness_inventory_receipts.json",
        "proof_summary": "Memory promotion remains blocked until explicit receipts exist.",
    },
    "redacted_proof_bundle_policy_receipt": {
        "source_ref": "generated/read_models/proof_bundle_redaction_policy.json",
        "proof_summary": "Redaction policy is ready and forbids raw sensitive details.",
    },
    "verifier_required_receipt": {
        "source_ref": "generated/read_models/proof_to_response_runtime_status.json",
        "proof_summary": "Proof-to-response runtime is ready and verifier-gated.",
    },
    "business_action_block_receipt": {
        "source_ref": "generated/read_models/local_lm_pilot_harness_selection_packet.json",
        "proof_summary": "Business action authority is false; no ledger, paid, email, Coupa, or workbook action is allowed.",
    },
}

RECEIPTS_MUST_REMAIN_MISSING = (
    "operator_approval_receipt",
    "model_invocation_boundary_receipt",
    "verifier_pass_fail_receipt",
    "published_response_hash_receipt",
)

ALLOWED_NEXT_DECISIONS = (
    "approve_read_only_model_inventory",
    "approve_one_time_local_lm_pilot_after_model_selection",
    "request_more_detail",
    "reject_for_now",
)

BLOCKED_ACTIONS = (
    "model_invocation",
    "runtime_connection",
    "prompt_send",
    "proof_bundle_send",
    "service_start_or_stop",
    "worker_spawn",
    "external_provider_call",
    "tool_authority",
    "memory_promotion",
    "email_send",
    "browser_gmail_coupa_access",
    "ledger_mutation",
    "workbook_mutation",
    "pdf_export",
    "paid_marking",
    "submit",
    "git_push",
)

AUTHORITY_BOUNDARY = {
    "ready_for_live_invocation": False,
    "invocation_allowed": False,
    "proof_response_pilot_allowed": False,
    "protected_actions_allowed": False,
    "authority_granted": False,
    "authority_grant_allowed": False,
    "model_invocation_allowed": False,
    "live_lm_invocation_allowed": False,
    "external_llm_allowed": False,
    "external_provider_connect_allowed": False,
    "local_model_runtime_allowed": False,
    "tool_authority_allowed": False,
    "tool_execution_allowed": False,
    "memory_write_access": False,
    "memory_promotion_allowed": False,
    "worker_spawn_allowed": False,
    "business_action_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "git_push_allowed": False,
}

IMPLEMENTATION_BOUNDARY = {
    "model_invoked": False,
    "runtime_connected": False,
    "local_model_runtime_connected": False,
    "external_llm_invoked": False,
    "external_provider_connected": False,
    "prompt_sent_to_model": False,
    "proof_bundle_sent_to_model": False,
    "service_started_or_stopped": False,
    "worker_spawn_performed": False,
    "tool_execution_performed": False,
    "memory_promotion_performed": False,
    "business_action_performed": False,
    "email_send_performed": False,
    "browser_opened": False,
    "gmail_opened": False,
    "coupa_opened": False,
    "ledger_mutation_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "paid_marking_performed": False,
    "submit_performed": False,
    "git_push_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(harness_selection.UNSAFE_TRUE_KEYS)
    | set(local_lm_runtime_discovery.UNSAFE_TRUE_KEYS)
    | set(proof_to_response_runtime.UNSAFE_TRUE_KEYS)
    | {
        "ready_for_live_invocation",
        "invocation_allowed",
        "approved",
        "operator_approval_present",
        "model_invoked",
        "runtime_connected",
        "external_provider_used",
        "tool_authority",
        "business_action_authority",
        "proof_bundle_visible_to_model",
        "paid",
        "sent",
        "submitted",
        "executed",
    }
)


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
        ready = observed in accepted
        row = {
            "precondition_ref": ref,
            "source_ref": f"generated/read_models/{filename}",
            "observed_status": observed,
            "accepted_statuses": accepted,
            "ready": ready,
        }
        active_candidate_source = spec.get("active_candidate_source")
        if active_candidate_source:
            observed_source = str(payload.get("active_candidate_source") or "")
            row["observed_active_candidate_source"] = observed_source
            row["accepted_active_candidate_source"] = str(active_candidate_source)
            row["ready"] = ready and observed_source == str(active_candidate_source)
        rows.append(row)
    return rows


def _source_hash(read_model_root: Path, source_ref: str) -> str:
    path = _rooted(read_model_root) / source_ref.removeprefix("generated/read_models/")
    payload = _load_json(path)
    return _content_hash(payload) if payload else ""


def _selection_packet(read_model_root: Path) -> dict[str, Any]:
    payload = _load_json(_rooted(read_model_root) / "local_lm_pilot_harness_selection_packet.json")
    packet = payload.get("selection_packet")
    return dict(packet) if isinstance(packet, Mapping) else {}


def _runtime_discovery(read_model_root: Path) -> dict[str, Any]:
    return _load_json(_rooted(read_model_root) / "local_lm_runtime_discovery.json")


def selected_harness_ref(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> str:
    packet = _selection_packet(read_model_root)
    runtime = _runtime_discovery(read_model_root)
    return str(packet.get("selected_harness_ref") or runtime.get("recommended_candidate_ref") or "local_llm_shadow_mode")


def selected_runtime_ref(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> str:
    packet = _selection_packet(read_model_root)
    runtime_ref = str(packet.get("selected_runtime_ref") or "")
    return runtime_ref or "none_connected_review_only"


def selected_model_ref(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> str | None:
    packet = _selection_packet(read_model_root)
    model_ref = str(packet.get("selected_model_ref") or "")
    if not model_ref or model_ref == "not_selected_pending_operator_review":
        return None
    return model_ref


def receipt_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT, *, generated_at: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    generated_at = generated_at or utc_now()
    root = _rooted(read_model_root)
    present: list[dict[str, Any]] = []
    for receipt_ref, spec in PREFLIGHT_RECEIPT_SPECS.items():
        source_ref = str(spec["source_ref"])
        present.append(
            {
                "receipt_id": f"preflight:{receipt_ref}",
                "receipt_ref": receipt_ref,
                "receipt_status": "present",
                "created_at": generated_at,
                "source_ref": source_ref,
                "source_hash": _source_hash(root, source_ref),
                "proof_summary": str(spec["proof_summary"]),
                "model_invoked": False,
                "runtime_connected": False,
                "business_action_performed": False,
            }
        )
    missing = [
        {
            "receipt_id": f"preflight_missing:{receipt_ref}",
            "receipt_ref": receipt_ref,
            "receipt_status": "missing",
            "created_at": generated_at,
            "source_ref": "",
            "source_hash": "",
            "proof_summary": _missing_receipt_reason(receipt_ref),
            "model_invoked": False,
            "runtime_connected": False,
            "business_action_performed": False,
        }
        for receipt_ref in RECEIPTS_MUST_REMAIN_MISSING
    ]
    return present, missing


def _missing_receipt_reason(receipt_ref: str) -> str:
    reasons = {
        "operator_approval_receipt": "Explicit operator approval has not been recorded.",
        "model_invocation_boundary_receipt": "Exact runtime/model invocation boundary is not yet selected and receipted.",
        "verifier_pass_fail_receipt": "No live model draft has been produced, so no verifier pass/fail receipt exists.",
        "published_response_hash_receipt": "No live model draft has been published, so no response hash receipt exists.",
    }
    return reasons.get(receipt_ref, "Receipt remains missing before live invocation.")


def ready_for_operator_decision(present: list[Mapping[str, Any]], missing: list[Mapping[str, Any]], preconditions: list[Mapping[str, Any]]) -> bool:
    required_present = set(PREFLIGHT_RECEIPT_SPECS)
    observed_present = {str(row.get("receipt_ref")) for row in present if row.get("receipt_status") == "present"}
    observed_missing = {str(row.get("receipt_ref")) for row in missing if row.get("receipt_status") == "missing"}
    return (
        all(row.get("ready") is True for row in preconditions)
        and required_present <= observed_present
        and set(RECEIPTS_MUST_REMAIN_MISSING) <= observed_missing
    )


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    present, missing = receipt_rows(read_model_root, generated_at=generated_at)
    operator_ready = ready_for_operator_decision(present, missing, preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if operator_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Collect preflight receipts available before any local LM proof-to-response invocation.",
        "ready_for_operator_decision": operator_ready,
        "ready_for_live_invocation": False,
        "selected_harness_ref": selected_harness_ref(read_model_root),
        "selected_runtime_ref": selected_runtime_ref(read_model_root),
        "selected_model_ref": selected_model_ref(read_model_root),
        "pilot_lane": PILOT_LANE,
        "pilot_question": PILOT_QUESTION,
        "receipts_present": present,
        "receipts_missing": missing,
        "allowed_next_decisions": list(ALLOWED_NEXT_DECISIONS),
        "blocked_actions": list(BLOCKED_ACTIONS),
        "preconditions": preconditions,
        "sqlite_ref": _rooted(sqlite_path).as_posix(),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "machine_proof": {
            "preflight_only": True,
            "model_invoked": False,
            "runtime_connected": False,
            "prompt_sent_to_model": False,
            "proof_bundle_sent_to_model": False,
            "external_provider_used": False,
            "tool_authority": False,
            "business_action_authority": False,
            "operator_approval_present": False,
            "unsafe_true_grants_absent": True,
        },
        "source_content_hashes": {
            "preconditions": _content_hash(preconditions),
            "receipts_present": _content_hash(present),
            "receipts_missing": _content_hash(missing),
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
        payload["ready_for_operator_decision"] = False
    payload["content_hash"] = _content_hash({key: value for key, value in payload.items() if key != "content_hash"})
    return payload


def sqlite_schema() -> str:
    return """
CREATE TABLE IF NOT EXISTS preflight_receipts (
  receipt_id TEXT PRIMARY KEY,
  receipt_ref TEXT NOT NULL,
  receipt_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  proof_summary TEXT NOT NULL,
  model_invoked INTEGER NOT NULL DEFAULT 0,
  runtime_connected INTEGER NOT NULL DEFAULT 0,
  business_action_performed INTEGER NOT NULL DEFAULT 0,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_preflight_receipts_status ON preflight_receipts(receipt_status);
"""


def write_sqlite(read_model: Mapping[str, Any], sqlite_path: Path = DEFAULT_SQLITE_PATH) -> int:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(read_model.get("receipts_present") or []) + list(read_model.get("receipts_missing") or [])
    with sqlite3.connect(path) as conn:
        conn.executescript(sqlite_schema())
        conn.execute("DELETE FROM preflight_receipts")
        for row in rows:
            conn.execute(
                """
INSERT INTO preflight_receipts (
  receipt_id, receipt_ref, receipt_status, created_at, source_ref, source_hash,
  proof_summary, model_invoked, runtime_connected, business_action_performed,
  payload_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""",
                (
                    str(row.get("receipt_id") or ""),
                    str(row.get("receipt_ref") or ""),
                    str(row.get("receipt_status") or ""),
                    str(row.get("created_at") or ""),
                    str(row.get("source_ref") or ""),
                    str(row.get("source_hash") or ""),
                    str(row.get("proof_summary") or ""),
                    1 if row.get("model_invoked") is True else 0,
                    1 if row.get("runtime_connected") is True else 0,
                    1 if row.get("business_action_performed") is True else 0,
                    stable_json(row),
                ),
            )
        conn.commit()
    return len(rows)


def sqlite_row_count(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> int:
    path = _rooted(sqlite_path)
    if not path.exists():
        return 0
    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT COUNT(*) FROM preflight_receipts").fetchone()
    return int(row[0] if row else 0)


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Local LM Proof Response Preflight Receipts",
        "",
        f"Status: {read_model.get('status')}",
        f"Ready for operator decision: `{str(read_model.get('ready_for_operator_decision')).lower()}`",
        f"Ready for live invocation: `{str(read_model.get('ready_for_live_invocation')).lower()}`",
        "",
        "This packet records only preflight receipts available before live invocation. It does not invoke a model, connect a runtime, send a prompt, send a proof bundle, or grant authority.",
        "",
        "## Pilot",
        "",
        f"- Lane: `{read_model.get('pilot_lane')}`",
        f"- Question: {read_model.get('pilot_question')}",
        f"- Harness: `{read_model.get('selected_harness_ref')}`",
        f"- Runtime: `{read_model.get('selected_runtime_ref')}`",
        f"- Model: `{read_model.get('selected_model_ref')}`",
        "",
        "## Receipts Present",
        "",
    ]
    for row in read_model.get("receipts_present") or []:
        lines.append(f"- `{row.get('receipt_ref')}`: {row.get('proof_summary')}")
    lines.extend(["", "## Receipts Missing", ""])
    for row in read_model.get("receipts_missing") or []:
        lines.append(f"- `{row.get('receipt_ref')}`: {row.get('proof_summary')}")
    lines.extend(["", "## Allowed Next Decisions", ""])
    for decision in read_model.get("allowed_next_decisions") or []:
        lines.append(f"- `{decision}`")
    lines.extend(["", "## Blocked Actions", ""])
    for action in read_model.get("blocked_actions") or []:
        lines.append(f"- `{action}`")
    lines.append("")
    return "\n".join(lines)


def export_local_lm_proof_response_preflight_receipts(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, sqlite_path=sqlite_path, generated_at=generated_at)
    sqlite_count = write_sqlite(read_model, sqlite_path=sqlite_path)
    read_model["sqlite_row_count"] = sqlite_count
    read_model["source_content_hashes"]["sqlite_row_count"] = _content_hash({"sqlite_row_count": sqlite_count})
    read_model["content_hash"] = _content_hash({key: value for key, value in read_model.items() if key != "content_hash"})

    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    _write_json(read_model_path, read_model)

    bridge_read_model_path = ""
    if bridge_root is not None:
        bridge_root = _rooted(bridge_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_root / JSON_EXPORT_NAME
        shutil.copy2(read_model_path, bridge_path)
        bridge_read_model_path = bridge_path.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")

    return {
        "status": str(read_model.get("status") or NOT_READY_STATUS),
        "ready_for_operator_decision": str(read_model.get("ready_for_operator_decision")).lower(),
        "ready_for_live_invocation": str(read_model.get("ready_for_live_invocation")).lower(),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": wiki_path.as_posix(),
        "sqlite_path": _rooted(sqlite_path).as_posix(),
        "sqlite_row_count": str(sqlite_count),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Local LM Proof Response Preflight Receipts V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--generated-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    bridge_root = Path(args.bridge_root) if args.bridge_root else None
    result = export_local_lm_proof_response_preflight_receipts(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=bridge_root,
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
