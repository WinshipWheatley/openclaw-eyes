"""Local LM pilot harness selection packet V0.

Review-only packet identifying the exact local harness/model candidate for the
one-time proof-to-response pilot. This module does not invoke models, connect
model runtimes, start services, spawn workers, send email, open browser/Gmail/
Coupa, mutate ledgers or workbooks, export PDFs, mark paid, submit, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import local_lm_harness_inventory_receipts as harness_inventory
import proof_bundle_redaction_policy as redaction_policy
import proof_to_response_runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Local LM Pilot Harness Selection Packet.md")

SCHEMA_VERSION = "local_lm_pilot_harness_selection_packet_v0"
READ_MODEL_ID = "local_lm_pilot_harness_selection_packet"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LOCAL_LM_PILOT_HARNESS_SELECTION_PACKET_READY"
NOT_READY_STATUS = "LOCAL_LM_PILOT_HARNESS_SELECTION_PACKET_NOT_READY"
PACKET_STATUS = "pending_operator_review"
PACKET_ID = "local_lm_pilot_harness_selection_packet:finance_capital_hilton:v0"

DEFAULT_SELECTED_HARNESS_REF = "local_llm_shadow_mode"
DEFAULT_SELECTED_MODEL_REF = "not_selected_pending_operator_review"
DEFAULT_PROOF_BUNDLE_REF = "redacted_proof_bundle:finance_capital_hilton_payment_watch"
DEFAULT_REDACTION_POLICY_REF = "generated/read_models/proof_bundle_redaction_policy.json"
DEFAULT_VERIFIER_REF = "proof_to_response_verifier.py#proof_to_response_verifier_v0"

PRECONDITIONS = {
    "local_lm_proof_response_pilot_approval_brief": {
        "filename": "local_lm_proof_response_pilot_approval_brief.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_PILOT_APPROVAL_BRIEF_READY",),
    },
    "local_lm_harness_inventory_receipts": {
        "filename": "local_lm_harness_inventory_receipts.json",
        "accepted_statuses": ("LOCAL_LM_HARNESS_INVENTORY_RECEIPTS_READY",),
    },
    "local_lm_proof_response_readiness_gate": {
        "filename": "local_lm_proof_to_response_readiness_gate.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_READINESS_GATE_READY",),
    },
    "proof_bundle_redaction_hardening": {
        "filename": "proof_bundle_redaction_policy.json",
        "accepted_statuses": ("PROOF_BUNDLE_REDACTION_HARDENING_READY",),
    },
    "proof_to_response_shadow_pilot_runtime": {
        "filename": "proof_to_response_runtime_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_RUNTIME_READY",),
        "active_candidate_source": proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
    },
}

AUTHORITY_BOUNDARY = {
    "selection_packet_is_approval": False,
    "invocation_allowed": False,
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
    "ledger_posting_allowed": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "workbook_body_read_allowed": False,
    "pdf_export_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
}

IMPLEMENTATION_BOUNDARY = {
    "model_invoked": False,
    "runtime_connected": False,
    "local_model_runtime_connected": False,
    "external_llm_invoked": False,
    "external_provider_connected": False,
    "service_started": False,
    "worker_spawn_performed": False,
    "tool_execution_performed": False,
    "memory_write_performed": False,
    "business_action_performed": False,
    "email_send_performed": False,
    "gmail_opened": False,
    "browser_opened": False,
    "coupa_opened": False,
    "portal_submit_performed": False,
    "ledger_mutation_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "paid_marking_performed": False,
    "git_push_performed": False,
    "merge_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(harness_inventory.UNSAFE_TRUE_KEYS)
    | set(proof_to_response_runtime.UNSAFE_TRUE_KEYS)
    | {
        "approved",
        "approval_granted",
        "operator_approved",
        "approved_for_live_invocation",
        "ready_for_live_invocation",
        "live_invocation_ready",
        "proof_to_response_allowed",
        "external_provider_used",
        "tool_access",
        "business_action_authority",
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
        active_candidate_source = spec.get("active_candidate_source")
        row = {
            "precondition_ref": ref,
            "source_ref": f"generated/read_models/{filename}",
            "observed_status": observed,
            "accepted_statuses": accepted,
            "ready": ready,
        }
        if active_candidate_source:
            observed_source = str(payload.get("active_candidate_source") or payload.get("candidate_source") or "")
            row["observed_active_candidate_source"] = observed_source
            row["accepted_active_candidate_source"] = str(active_candidate_source)
            row["ready"] = ready and observed_source == str(active_candidate_source)
        rows.append(row)
    return rows


def _brief_payload(read_model_root: Path) -> dict[str, Any]:
    return _load_json(_rooted(read_model_root) / "local_lm_proof_response_pilot_approval_brief.json")


def _inventory_payload(read_model_root: Path) -> dict[str, Any]:
    return _load_json(_rooted(read_model_root) / "local_lm_harness_inventory_receipts.json")


def _approval_packet_payload(read_model_root: Path) -> dict[str, Any]:
    return _load_json(_rooted(read_model_root) / "local_lm_proof_response_pilot_approval_packet.json")


def _selected_harness_ref(brief: Mapping[str, Any], approval_packet: Mapping[str, Any]) -> str:
    nested = approval_packet.get("approval_packet") if isinstance(approval_packet.get("approval_packet"), Mapping) else {}
    return str(
        brief.get("candidate_harness_ref")
        or nested.get("candidate_harness_ref")
        or DEFAULT_SELECTED_HARNESS_REF
    )


def _selected_model_ref(brief: Mapping[str, Any], approval_packet: Mapping[str, Any]) -> str:
    nested = approval_packet.get("approval_packet") if isinstance(approval_packet.get("approval_packet"), Mapping) else {}
    model_ref = str(brief.get("candidate_model_ref") or nested.get("candidate_model_ref") or "")
    return model_ref or DEFAULT_SELECTED_MODEL_REF


def _selected_candidate(inventory: Mapping[str, Any], harness_ref: str) -> dict[str, Any]:
    for candidate in inventory.get("harness_candidates") or []:
        if isinstance(candidate, Mapping) and candidate.get("harness_ref") == harness_ref:
            return dict(candidate)
    return {
        "harness_ref": harness_ref,
        "present": "unknown",
        "invocation_allowed": False,
        "proof_to_response_allowed": False,
        "live_invocation_ready": False,
        "data_classes_allowed": list(harness_inventory.DATA_CLASSES_ALLOWED_BASE),
        "data_classes_forbidden": list(harness_inventory.DATA_CLASSES_FORBIDDEN_BASE),
        "missing_receipts": list(harness_inventory.REQUIRED_RECEIPTS_BEFORE_LIVE),
        "required_operator_approval": "explicit_operator_approval_required",
        "required_verifier": "proof_to_response_verifier",
        "required_redaction": True,
        "reason_not_live": "selected_harness_not_found_in_inventory",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _runtime_present_value(candidate: Mapping[str, Any]) -> bool | str:
    present = candidate.get("present")
    if present is True or str(present).lower() == "true":
        return True
    if present is False or str(present).lower() == "false":
        return False
    return "unknown"


def _local_only(harness_ref: str) -> bool:
    return harness_ref in {
        "local_llm_shadow_mode",
        "future_local_open_model",
        "hermes_sidecar_candidate",
        "codex_desktop_operator_assist",
    }


def _allowed_inputs(brief: Mapping[str, Any], approval_packet: Mapping[str, Any]) -> list[str]:
    answers = brief.get("brief_answers") if isinstance(brief.get("brief_answers"), Mapping) else {}
    visible = answers.get("proof_bundle_model_would_see") if isinstance(answers.get("proof_bundle_model_would_see"), Mapping) else {}
    fields = visible.get("allowed_fields")
    if isinstance(fields, list) and fields:
        return [str(field) for field in fields if str(field)]
    nested = approval_packet.get("approval_packet") if isinstance(approval_packet.get("approval_packet"), Mapping) else {}
    rows = nested.get("allowed_lm_inputs")
    if isinstance(rows, list):
        return [str(row.get("field_ref")) for row in rows if isinstance(row, Mapping) and row.get("field_ref")]
    return list(redaction_policy.ALLOWED_FIELD_REASONS)


def _forbidden_inputs(brief: Mapping[str, Any], approval_packet: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[str]:
    nested = approval_packet.get("approval_packet") if isinstance(approval_packet.get("approval_packet"), Mapping) else {}
    values: list[str] = []
    for source in (
        nested.get("forbidden_lm_inputs"),
        candidate.get("data_classes_forbidden"),
        redaction_policy.FORBIDDEN_MATERIAL_CLASSES,
    ):
        if isinstance(source, list) or isinstance(source, tuple):
            values.extend(str(item) for item in source if str(item))
    answers = brief.get("brief_answers") if isinstance(brief.get("brief_answers"), Mapping) else {}
    hidden = answers.get("what_model_would_not_see")
    if isinstance(hidden, list):
        values.extend(str(item) for item in hidden if str(item))
    return list(dict.fromkeys(values))


def _proof_bundle_ref(brief: Mapping[str, Any], approval_packet: Mapping[str, Any]) -> str:
    nested = approval_packet.get("approval_packet") if isinstance(approval_packet.get("approval_packet"), Mapping) else {}
    summary = nested.get("proof_bundle_summary") if isinstance(nested.get("proof_bundle_summary"), Mapping) else {}
    return str(summary.get("proof_bundle_ref") or DEFAULT_PROOF_BUNDLE_REF)


def _redaction_policy_ref(approval_packet: Mapping[str, Any]) -> str:
    nested = approval_packet.get("approval_packet") if isinstance(approval_packet.get("approval_packet"), Mapping) else {}
    return str(nested.get("redaction_policy_ref") or DEFAULT_REDACTION_POLICY_REF)


def _verifier_ref(approval_packet: Mapping[str, Any]) -> str:
    nested = approval_packet.get("approval_packet") if isinstance(approval_packet.get("approval_packet"), Mapping) else {}
    return str(nested.get("verifier_ref") or DEFAULT_VERIFIER_REF)


def operator_decision_options() -> list[dict[str, Any]]:
    return [
        {
            "option_ref": "select_local_llm_shadow_mode_for_one_time_pilot_review",
            "label": "Select local shadow harness",
            "effect": "Records the harness/model candidate for review only; it does not allow invocation.",
            "grants_invocation_now": False,
            "review_only": True,
        },
        {
            "option_ref": "request_more_detail",
            "label": "Request more detail",
            "effect": "Ask for more harness, runtime, redaction, or receipt detail before selection.",
            "grants_invocation_now": False,
            "review_only": True,
        },
        {
            "option_ref": "reject_for_now",
            "label": "Reject for now",
            "effect": "Keep local/live LM invocation blocked.",
            "grants_invocation_now": False,
            "review_only": True,
        },
    ]


def build_selection_packet(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    root = _rooted(read_model_root)
    brief = _brief_payload(root)
    inventory = _inventory_payload(root)
    approval_packet = _approval_packet_payload(root)
    selected_harness_ref = _selected_harness_ref(brief, approval_packet)
    selected_model_ref = _selected_model_ref(brief, approval_packet)
    candidate = _selected_candidate(inventory, selected_harness_ref)
    missing_receipts = [str(item) for item in candidate.get("missing_receipts") or [] if str(item)]
    runtime_present = _runtime_present_value(candidate)
    local_only = _local_only(selected_harness_ref)
    return {
        "packet_id": PACKET_ID,
        "status": PACKET_STATUS,
        "generated_at": generated_at,
        "selected_harness_ref": selected_harness_ref,
        "selected_model_ref": selected_model_ref,
        "selected_runtime_ref": "none_connected_review_only",
        "local_only": local_only,
        "external_provider_used": False,
        "runtime_present": runtime_present,
        "invocation_allowed": False,
        "proof_bundle_ref": _proof_bundle_ref(brief, approval_packet),
        "redaction_policy_ref": _redaction_policy_ref(approval_packet),
        "verifier_ref": _verifier_ref(approval_packet),
        "allowed_inputs": _allowed_inputs(brief, approval_packet),
        "forbidden_inputs": _forbidden_inputs(brief, approval_packet, candidate),
        "tool_access": False,
        "memory_write_access": False,
        "business_action_authority": False,
        "missing_receipts": missing_receipts,
        "operator_decision_options": operator_decision_options(),
        "harness_candidate": {
            "harness_ref": selected_harness_ref,
            "present": runtime_present,
            "reason_not_live": str(candidate.get("reason_not_live") or ""),
            "required_operator_approval": str(candidate.get("required_operator_approval") or "explicit_operator_approval_required"),
            "required_verifier": str(candidate.get("required_verifier") or "proof_to_response_verifier"),
            "required_redaction": candidate.get("required_redaction") is True,
            "proof_to_response_allowed": False,
            "live_invocation_ready": False,
        },
        "answers": {
            "which_harness_would_be_used": selected_harness_ref,
            "is_it_local_only": local_only,
            "is_any_external_provider_involved": False,
            "what_model_runtime_would_be_called": selected_model_ref,
            "is_runtime_currently_installed_or_present": runtime_present,
            "what_proof_bundle_would_be_sent": _proof_bundle_ref(brief, approval_packet),
            "what_redaction_policy_applies": _redaction_policy_ref(approval_packet),
            "what_tool_access_model_has": "none",
            "what_memory_write_access_model_has": "none",
            "what_receipts_are_still_missing": missing_receipts,
        },
        "plain_status": (
            "No suitable live local runtime is confirmed present yet; "
            f"`{selected_harness_ref}` is a review candidate only until receipts and explicit approval exist."
        ),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
    }


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    selection_packet = build_selection_packet(read_model_root=read_model_root, generated_at=generated_at)
    all_ready = all(row.get("ready") is True for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Review-only selection of the local harness/model candidate for a one-time proof-to-response pilot.",
        "selection_packet": selection_packet,
        "preconditions": preconditions,
        "source_refs": [
            "generated/read_models/local_lm_proof_response_pilot_approval_brief.json",
            "generated/read_models/local_lm_harness_inventory_receipts.json",
            "generated/read_models/local_lm_proof_to_response_readiness_gate.json",
            "generated/read_models/proof_bundle_redaction_policy.json",
            "generated/read_models/proof_to_response_runtime_status.json",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "machine_proof": {
            "review_only": True,
            "packet_pending_operator_review": True,
            "approved": False,
            "invocation_allowed": False,
            "model_invoked": False,
            "runtime_connected": False,
            "external_provider_used": False,
            "tool_access": False,
            "memory_write_access": False,
            "business_action_authority": False,
            "unsafe_true_grants_absent": True,
        },
        "source_content_hashes": {
            "selection_packet": _content_hash(selection_packet),
            "preconditions": _content_hash(preconditions),
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    payload["content_hash"] = _content_hash({key: value for key, value in payload.items() if key != "content_hash"})
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    packet = read_model.get("selection_packet") if isinstance(read_model.get("selection_packet"), Mapping) else {}
    answers = packet.get("answers") if isinstance(packet.get("answers"), Mapping) else {}
    lines = [
        "# Local LM Pilot Harness Selection Packet",
        "",
        f"Status: {read_model.get('status')}",
        f"Packet status: {packet.get('status')}",
        "",
        "This is review-only. It does not invoke a model, connect a runtime, start a service, or grant authority.",
        "",
        "## Selection",
        "",
        f"- Harness: `{packet.get('selected_harness_ref')}`",
        f"- Model/runtime: `{packet.get('selected_model_ref')}`",
        f"- Local only: `{str(packet.get('local_only')).lower()}`",
        f"- External provider used: `{str(packet.get('external_provider_used')).lower()}`",
        f"- Runtime present: `{packet.get('runtime_present')}`",
        f"- Invocation allowed: `{str(packet.get('invocation_allowed')).lower()}`",
        "",
        "## Proof Input",
        "",
        f"- Proof bundle: `{packet.get('proof_bundle_ref')}`",
        f"- Redaction policy: `{packet.get('redaction_policy_ref')}`",
        f"- Verifier: `{packet.get('verifier_ref')}`",
        f"- Allowed inputs: `{packet.get('allowed_inputs')}`",
        "",
        "## No Access",
        "",
        "- Tool access: `false`",
        "- Memory write access: `false`",
        "- Business action authority: `false`",
        "- Browser/Gmail/Coupa/ledger/workbook/PDF/paid marking: blocked",
        "",
        "## Missing Receipts",
        "",
    ]
    for receipt in packet.get("missing_receipts") or []:
        lines.append(f"- `{receipt}`")
    lines.extend(
        [
            "",
            "## Plain Status",
            "",
            str(packet.get("plain_status") or ""),
            "",
            "## Operator Decision Options",
            "",
        ]
    )
    for option in packet.get("operator_decision_options") or []:
        if isinstance(option, Mapping):
            lines.append(f"- `{option.get('option_ref')}`: {option.get('effect')}")
    lines.extend(
        [
            "",
            "## Answers",
            "",
            f"- Which harness would be used? `{answers.get('which_harness_would_be_used')}`",
            f"- Is it local only? `{str(answers.get('is_it_local_only')).lower()}`",
            f"- Is any external provider involved? `{str(answers.get('is_any_external_provider_involved')).lower()}`",
            f"- What model/runtime would be called? `{answers.get('what_model_runtime_would_be_called')}`",
            f"- Is that runtime currently installed/present? `{answers.get('is_runtime_currently_installed_or_present')}`",
            f"- What proof bundle would be sent? `{answers.get('what_proof_bundle_would_be_sent')}`",
            f"- What redaction policy applies? `{answers.get('what_redaction_policy_applies')}`",
            f"- What tool access does the model have? `{answers.get('what_tool_access_model_has')}`",
            f"- What memory write access does the model have? `{answers.get('what_memory_write_access_model_has')}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_local_lm_pilot_harness_selection_packet(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
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
        "packet_status": str(read_model.get("selection_packet", {}).get("status") or ""),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Local LM Pilot Harness Selection Packet V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    bridge_root = Path(args.bridge_root) if args.bridge_root else None
    result = export_local_lm_pilot_harness_selection_packet(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=bridge_root,
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
