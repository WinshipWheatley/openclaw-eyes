"""Local LM harness inventory receipts.

Read-only inventory and receipt planning for a future proof-to-response local
model pilot. This module inspects existing read models and local config paths
only. It does not invoke models, connect runtimes, start services, spawn
workers, run tools, or perform business actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import local_lm_proof_to_response_readiness_gate as readiness_gate
import proof_to_response_runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Local LM Harness Inventory Receipts.md")

SCHEMA_VERSION = "local_lm_harness_inventory_receipts_v0"
READ_MODEL_ID = "local_lm_harness_inventory_receipts"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LOCAL_LM_HARNESS_INVENTORY_RECEIPTS_READY"
NOT_READY_STATUS = "LOCAL_LM_HARNESS_INVENTORY_RECEIPTS_NOT_READY"

HARNESS_REFS = (
    "local_llm_shadow_mode",
    "future_local_open_model",
    "codex_desktop_operator_assist",
    "hermes_sidecar_candidate",
    "external_llm_blocked_by_default",
)

REQUIRED_PRECONDITIONS = {
    "local_lm_proof_to_response_readiness_gate": {
        "filename": "local_lm_proof_to_response_readiness_gate.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_READINESS_GATE_READY",),
    },
    "proof_to_response_runtime": {
        "filename": "proof_to_response_runtime_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_RUNTIME_READY",),
    },
    "harness_provider_selection": {
        "filename": "harness_provider_selection_registry.json",
        "accepted_statuses": ("HARNESS_PROVIDER_SELECTION_READY",),
    },
    "goldilocks_gate_calibration": {
        "filename": "goldilocks_gate_calibration.json",
        "accepted_statuses": ("GOLDILOCKS_GATE_CALIBRATION_READY",),
    },
}

INSPECTED_READ_MODELS = (
    "local_lm_proof_to_response_readiness_gate.json",
    "harness_provider_selection_registry.json",
    "proof_to_response_lm_shadow_pilot.json",
    "proof_to_response_runtime_status.json",
    "proof_to_response_latest.json",
    "goldilocks_gate_calibration.json",
    "hermes_sidecar_inventory.json",
    "openclaw_hermes_sidecar.json",
    "operator_assist_provider_registry.json",
    "provider_policy_registry.json",
)

KNOWN_LOCAL_HARNESS_PATHS = (
    "openclaw_hermes_sidecar.py",
    "scripts/export_openclaw_hermes_sidecar.py",
    "systemd/user/hermes-gateway.service.in",
    "generated/system_knowledge/openclaw_hermes_sidecar.sqlite",
    "sidecars/hermes",
    "sidecars/gbrain_upstream",
)

REQUIRED_RECEIPTS_BEFORE_LIVE = (
    "proof_bundle_redaction_receipt",
    "model_invocation_boundary_receipt",
    "no_external_provider_receipt",
    "no_tool_authority_receipt",
    "no_memory_promotion_receipt",
    "verifier_pass_fail_receipt",
    "published_response_hash_receipt",
    "operator_approval_receipt",
)

FIRST_SAFE_PILOT_SCOPE = readiness_gate.ALLOWED_FIRST_PILOT_SCOPE

AUTHORITY_BOUNDARY = {
    "model_invocation_allowed": False,
    "live_lm_invocation_allowed": False,
    "external_llm_allowed": False,
    "external_provider_connect_allowed": False,
    "local_model_runtime_allowed": False,
    "codex_desktop_operator_assist_allowed": False,
    "hermes_sidecar_invocation_allowed": False,
    "tool_authority_allowed": False,
    "tool_execution_allowed": False,
    "worker_spawn_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "memory_promotion_allowed": False,
    "business_action_allowed": False,
    "authority_grant_allowed": False,
    "protected_actions_allowed": False,
    "credential_use_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
}

IMPLEMENTATION_BOUNDARY = {
    "model_invoked": False,
    "runtime_connected": False,
    "local_model_runtime_connected": False,
    "external_provider_connected": False,
    "external_llm_invoked": False,
    "codex_desktop_operator_assist_invoked": False,
    "hermes_sidecar_invoked": False,
    "tool_execution_performed": False,
    "worker_spawn_performed": False,
    "browser_opened": False,
    "gmail_opened": False,
    "coupa_opened": False,
    "portal_submit_performed": False,
    "ledger_mutation_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "paid_marking_performed": False,
    "memory_promotion_performed": False,
    "business_action_performed": False,
    "authority_grant_performed": False,
    "git_push_performed": False,
    "merge_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(readiness_gate.UNSAFE_TRUE_KEYS)
    | set(proof_to_response_runtime.UNSAFE_TRUE_KEYS)
    | {
        "invocation_allowed",
        "proof_to_response_allowed",
        "live_invocation_ready",
        "external_provider_call_allowed",
        "tool_authority_granted",
        "authority_granted",
        "paid",
        "sent",
        "submitted",
        "executed",
    }
)

DATA_CLASSES_ALLOWED_BASE = (
    "bounded_proof_bundle_refs",
    "receipt_refs",
    "proof_meter_values",
    "redacted_read_model_summaries",
    "gate_decision_refs",
    "dynamic_card_support_refs",
)

DATA_CLASSES_FORBIDDEN_BASE = (
    "raw_sensitive_details",
    "operator_envelope_secret_material",
    "device_verification_material",
    "session_verification_material",
    "credentials_or_tokens",
    "raw_bank_details_unredacted",
    "raw_prompt_dumps",
    "source_workbook_bodies",
    "browser_session_state",
    "gmail_message_bodies",
    "coupa_session_data",
    "external_provider_call",
    "tool_authority",
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str, *, root: Path = ROOT) -> Path:
    path = Path(path)
    return path if path.is_absolute() else root / path


def _load_json(path: Path) -> dict[str, Any]:
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


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


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
    return str(payload.get("status") or payload.get("contract_status") or payload.get("readiness_status") or "")


def _shadow_runtime_row(read_model_root: Path) -> dict[str, Any]:
    runtime_status = _load_json(read_model_root / proof_to_response_runtime.STATUS_JSON_EXPORT_NAME)
    latest = _load_json(read_model_root / proof_to_response_runtime.LATEST_JSON_EXPORT_NAME)
    active_source = str(runtime_status.get("active_candidate_source") or latest.get("candidate_source") or "")
    ready = (
        runtime_status.get("status") == proof_to_response_runtime.READY_STATUS
        and active_source == proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT
        and bool(runtime_status.get("source_request_id") or latest.get("source_request_id"))
        and bool(runtime_status.get("world_ref") or latest.get("world_ref"))
        and bool(runtime_status.get("thread_ref") or latest.get("thread_ref"))
    )
    return {
        "precondition_ref": "proof_to_response_shadow_pilot_runtime",
        "source_ref": "generated/read_models/proof_to_response_runtime_status.json",
        "observed_status": "PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_READY" if ready else "PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_NOT_READY",
        "accepted_statuses": ["PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_READY"],
        "ready": ready,
        "active_candidate_source": active_source,
    }


def precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows = [_shadow_runtime_row(root)]
    for ref, spec in REQUIRED_PRECONDITIONS.items():
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
    return rows


def source_inventory(read_model_root: Path = DEFAULT_READ_MODEL_ROOT, repo_root: Path = ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    repo = _rooted(repo_root)
    rows: list[dict[str, Any]] = []
    for filename in INSPECTED_READ_MODELS:
        path = root / filename
        payload = _load_json(path)
        rows.append(
            {
                "source_ref": f"generated/read_models/{filename}",
                "present": path.exists(),
                "read_only_inspected": path.exists(),
                "status": _status(payload),
                "schema_version": str(payload.get("schema_version") or ""),
                "content_hash": _file_hash(path) if path.is_file() else "",
            }
        )
    for rel_path in KNOWN_LOCAL_HARNESS_PATHS:
        path = repo / rel_path
        rows.append(
            {
                "source_ref": rel_path,
                "present": path.exists(),
                "read_only_inspected": path.exists(),
                "status": "PRESENT" if path.exists() else "ABSENT",
                "schema_version": "",
                "content_hash": _file_hash(path) if path.is_file() else "",
            }
        )
    return rows


def _source_present(sources: list[dict[str, Any]], source_ref: str) -> bool:
    return any(row.get("source_ref") == source_ref and row.get("present") is True for row in sources)


def _registered_for_proof_to_response(read_model_root: Path) -> bool:
    registry = _load_json(read_model_root / "harness_provider_selection_registry.json")
    text = stable_json(registry).lower()
    return "hermes_sidecar_candidate" in text and "proof_to_response" in text


def _base_candidate(
    *,
    harness_ref: str,
    present: str,
    reason_not_live: str,
    missing_receipts: list[str] | None = None,
    data_classes_allowed: list[str] | None = None,
    data_classes_forbidden: list[str] | None = None,
    required_operator_approval: str = "explicit_operator_approval_required",
) -> dict[str, Any]:
    missing = list(REQUIRED_RECEIPTS_BEFORE_LIVE if missing_receipts is None else missing_receipts)
    return {
        "harness_ref": harness_ref,
        "present": present,
        "invocation_allowed": False,
        "proof_to_response_allowed": False,
        "live_invocation_ready": False,
        "data_classes_allowed": list(data_classes_allowed or DATA_CLASSES_ALLOWED_BASE),
        "data_classes_forbidden": list(data_classes_forbidden or DATA_CLASSES_FORBIDDEN_BASE),
        "missing_receipts": missing,
        "required_operator_approval": required_operator_approval,
        "required_verifier": "proof_to_response_verifier",
        "required_redaction": True,
        "first_safe_pilot_scope": list(FIRST_SAFE_PILOT_SCOPE),
        "reason_not_live": reason_not_live,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def harness_candidates(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    repo_root: Path = ROOT,
    sources: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows = sources or source_inventory(read_model_root=root, repo_root=repo_root)
    hermes_present = any(
        _source_present(rows, ref)
        for ref in (
            "generated/read_models/hermes_sidecar_inventory.json",
            "generated/read_models/openclaw_hermes_sidecar.json",
            "openclaw_hermes_sidecar.py",
            "sidecars/hermes",
        )
    )
    hermes_registered = _registered_for_proof_to_response(root)
    hermes_missing = list(REQUIRED_RECEIPTS_BEFORE_LIVE)
    if not hermes_registered:
        hermes_missing.append("explicit_hermes_proof_to_response_registration")

    return [
        _base_candidate(
            harness_ref="local_llm_shadow_mode",
            present="unknown",
            reason_not_live="shadow_mode_inventory_only_no_runtime_boundary_receipt",
        ),
        _base_candidate(
            harness_ref="future_local_open_model",
            present="unknown",
            reason_not_live="future_model_not_selected_or_approved",
            missing_receipts=list(REQUIRED_RECEIPTS_BEFORE_LIVE) + ["approved_local_model_identity_receipt"],
        ),
        _base_candidate(
            harness_ref="codex_desktop_operator_assist",
            present="unknown",
            reason_not_live="codex_desktop_operator_assist_requires_explicit_gate_approval",
            missing_receipts=list(REQUIRED_RECEIPTS_BEFORE_LIVE) + ["codex_desktop_operator_assist_scope_receipt"],
        ),
        _base_candidate(
            harness_ref="hermes_sidecar_candidate",
            present="true" if hermes_present else "false",
            reason_not_live="hermes_sidecar_not_explicitly_registered_for_proof_to_response" if not hermes_registered else "missing_live_pilot_receipts",
            missing_receipts=hermes_missing,
        ),
        _base_candidate(
            harness_ref="external_llm_blocked_by_default",
            present="unknown",
            reason_not_live="external_provider_blocked_by_default",
            missing_receipts=list(REQUIRED_RECEIPTS_BEFORE_LIVE) + ["new_external_provider_exception_gate"],
            data_classes_allowed=[],
            data_classes_forbidden=list(DATA_CLASSES_FORBIDDEN_BASE)
            + [
                "private_client_data",
                "financial_sensitive_local_only_data",
                "proof_bundle_contents",
            ],
            required_operator_approval="not_available_without_new_external_provider_exception_gate",
        ),
    ]


def required_receipt_rows() -> list[dict[str, Any]]:
    descriptions = {
        "proof_bundle_redaction_receipt": "Shows the bundle excludes secrets, raw bank details, raw prompt dumps, workbook bodies, and unredacted sensitive details.",
        "model_invocation_boundary_receipt": "Shows invocation is limited to proof-to-response drafting and cannot call tools or external systems.",
        "no_external_provider_receipt": "Shows the candidate path does not connect to OpenAI, Anthropic, browser-backed providers, or other external LLMs.",
        "no_tool_authority_receipt": "Shows the model path has no tool authority and no protected action authority.",
        "no_memory_promotion_receipt": "Shows draft text cannot promote memory, evidence, or summaries to business truth.",
        "verifier_pass_fail_receipt": "Records deterministic verifier pass/fail and failure reason before publication.",
        "published_response_hash_receipt": "Records the hash of the published response or safe fallback.",
        "operator_approval_receipt": "Records explicit operator approval for the exact local-only harness and pilot scope.",
    }
    return [
        {
            "receipt_ref": receipt_ref,
            "required_before_live": True,
            "present": False,
            "description": descriptions[receipt_ref],
        }
        for receipt_ref in REQUIRED_RECEIPTS_BEFORE_LIVE
    ]


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    repo_root: Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    root = _rooted(read_model_root)
    repo = _rooted(repo_root)
    preconditions = precondition_rows(root)
    sources = source_inventory(read_model_root=root, repo_root=repo)
    candidates = harness_candidates(read_model_root=root, repo_root=repo, sources=sources)
    all_preconditions_ready = all(row.get("ready") is True for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all_preconditions_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Inventory local/model/harness options and define receipts required before any live local proof-to-response LM pilot.",
        "doctrine": [
            "This is read-only inventory and receipt planning.",
            "No model is invoked.",
            "No model runtime is connected or started.",
            "No worker is spawned.",
            "No candidate is live-invocation ready by default.",
            "Proof-to-response drafts require redaction, verifier receipts, hashes, and explicit operator approval before live pilot use.",
        ],
        "preconditions": preconditions,
        "inspected_sources": sources,
        "harness_candidates": candidates,
        "required_receipts_before_live": required_receipt_rows(),
        "first_safe_pilot_scope": list(FIRST_SAFE_PILOT_SCOPE),
        "readiness_decision": {
            "ready_for_live_local_lm_pilot": False,
            "live_candidate_selected": "",
            "blockers": [
                "operator_approval_receipt_missing",
                "proof_bundle_redaction_receipt_missing",
                "model_invocation_boundary_receipt_missing",
                "no_external_provider_receipt_missing",
                "no_tool_authority_receipt_missing",
                "verifier_pass_fail_receipt_missing",
            ],
            "next_safe_action": "Collect non-invocation boundary receipts and choose a local-only shadow harness candidate for explicit approval.",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "machine_proof": {
            "read_only_inventory": True,
            "model_invoked": False,
            "runtime_connected": False,
            "local_model_runtime_connected": False,
            "external_provider_connected": False,
            "worker_spawn_performed": False,
            "tool_execution_performed": False,
            "business_action_performed": False,
            "unsafe_true_grants": [],
            "unsafe_true_grants_absent": True,
        },
        "source_content_hashes": {
            "preconditions": _content_hash(preconditions),
            "harness_candidates": _content_hash(candidates),
            "required_receipts_before_live": _content_hash(required_receipt_rows()),
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    decision = read_model.get("readiness_decision") if isinstance(read_model.get("readiness_decision"), Mapping) else {}
    lines = [
        "# Local LM Harness Inventory Receipts",
        "",
        f"Status: {read_model.get('status')}",
        f"Ready for live local LM pilot: `{str(decision.get('ready_for_live_local_lm_pilot')).lower()}`",
        "",
        "This inventory records local/model/harness candidates for a future proof-to-response pilot. It is not a runtime approval and does not invoke or connect any model.",
        "",
        "## Candidates",
        "",
    ]
    for row in read_model.get("harness_candidates") or []:
        lines.append(
            f"- `{row.get('harness_ref')}`: present `{row.get('present')}`, live `{str(row.get('live_invocation_ready')).lower()}`, reason `{row.get('reason_not_live')}`"
        )
    lines.extend(["", "## Receipts Required Before Live Pilot", ""])
    for row in read_model.get("required_receipts_before_live") or []:
        lines.append(f"- `{row.get('receipt_ref')}`")
    lines.extend(["", "## First Safe Pilot Scope", ""])
    for item in read_model.get("first_safe_pilot_scope") or []:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "## Blocked By Default",
            "",
            "- External LLM/provider calls",
            "- Tool authority",
            "- Browser, Gmail, Coupa, portal submit",
            "- Ledger/workbook mutation, PDF export, paid marking",
            "- Worker spawn and memory promotion to truth",
            "",
            "## Decision",
            "",
            f"- Blockers: `{decision.get('blockers')}`",
            f"- Next safe action: {decision.get('next_safe_action')}",
            "",
        ]
    )
    return "\n".join(lines)


def export_local_lm_harness_inventory_receipts(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    repo_root: Path = ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, repo_root=repo_root, generated_at=generated_at)
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
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": wiki_path.as_posix(),
        "ready_for_live_local_lm_pilot": str(read_model["readiness_decision"]["ready_for_live_local_lm_pilot"]).lower(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Local LM Harness Inventory Receipts V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    bridge_root = Path(args.bridge_root) if args.bridge_root else None
    result = export_local_lm_harness_inventory_receipts(
        read_model_root=Path(args.read_model_root),
        repo_root=Path(args.repo_root),
        export_root=Path(args.export_root),
        bridge_root=bridge_root,
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
