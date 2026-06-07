"""Local model selection for proof-to-response V0.

Review-only model selection packet using the read-only local model list
inventory. This module reads existing generated read models and writes
generated read-model/wiki artifacts only. It does not invoke a model, send a
prompt, send a proof bundle, connect providers, start/stop services, read
secrets/API keys, spawn workers, mutate business state, export PDFs, mark paid,
submit, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import local_model_list_inventory
import model_catalog_inventory
import proof_to_response_runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Local Model Selection For Proof Response.md")

SCHEMA_VERSION = "local_model_selection_for_proof_response_v0"
READ_MODEL_ID = "local_model_selection_for_proof_response"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LOCAL_MODEL_SELECTION_FOR_PROOF_RESPONSE_READY"
NOT_READY_STATUS = "LOCAL_MODEL_SELECTION_FOR_PROOF_RESPONSE_NOT_READY"
PACKET_STATUS = "pending_operator_review"

PREFERRED_MODEL_NAME = "qwen3:8b-q4_K_M"
FIRST_PILOT_LANE = "finance/capital_hilton"
FIRST_PILOT_WORLD_REF = "finance"
FIRST_PILOT_THREAD_REF = "capital_hilton"
FIRST_PILOT_QUESTION = "What should I do here?"

PRECONDITIONS = {
    "local_model_list_inventory": {
        "filename": "local_model_list_inventory.json",
        "accepted_statuses": ("LOCAL_MODEL_LIST_INVENTORY_READY",),
    },
    "local_lm_proof_response_preflight_receipts": {
        "filename": "local_lm_proof_response_preflight_receipts.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_PREFLIGHT_RECEIPTS_READY",),
    },
    "local_lm_proof_response_pilot_plan": {
        "filename": "local_lm_proof_to_response_pilot_plan.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_PILOT_PLAN_READY",),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": "proof_bundle_builder_redaction_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY",),
    },
    "proof_to_response_runtime": {
        "filename": proof_to_response_runtime.STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (proof_to_response_runtime.READY_STATUS,),
    },
}

REQUIRED_OPERATOR_DECISION_OPTIONS = (
    "approve_model_selection_for_one_time_pilot",
    "choose_different_model",
    "request_more_detail",
    "reject_for_now",
)

DEFAULT_MISSING_RECEIPTS = (
    "operator_approval_receipt",
    "model_invocation_boundary_receipt",
    "verifier_pass_fail_receipt",
    "published_response_hash_receipt",
)

AUTHORITY_BOUNDARY = {
    "model_selection_is_invocation_approval": False,
    "runtime_presence_grants_proof_bundle_permission": False,
    "ready_for_invocation": False,
    "invocation_allowed": False,
    "proof_bundle_allowed": False,
    "protected_actions_allowed": False,
    "authority_granted": False,
    "authority_grant_allowed": False,
    "model_invocation_allowed": False,
    "live_lm_invocation_allowed": False,
    "external_llm_allowed": False,
    "external_provider_connect_allowed": False,
    "provider_key_material_access_allowed": False,
    "tool_authority": False,
    "tool_authority_allowed": False,
    "tool_execution_allowed": False,
    "memory_write_authority": False,
    "memory_write_access": False,
    "memory_promotion_allowed": False,
    "business_action_authority": False,
    "business_action_allowed": False,
    "worker_spawn_allowed": False,
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
    "model_invocation_performed": False,
    "model_invoked": False,
    "prompt_sent": False,
    "prompt_sent_to_model": False,
    "proof_bundle_sent": False,
    "proof_bundle_sent_to_model": False,
    "external_provider_used": False,
    "external_provider_connected": False,
    "provider_api_called": False,
    "secrets_read": False,
    "secret_read": False,
    "api_key_read": False,
    "service_started_or_stopped": False,
    "worker_spawn_performed": False,
    "tool_execution_performed": False,
    "memory_write_performed": False,
    "business_action_performed": False,
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
    | set(local_model_list_inventory.UNSAFE_TRUE_KEYS)
    | set(model_catalog_inventory.UNSAFE_TRUE_KEYS)
    | set(proof_to_response_runtime.UNSAFE_TRUE_KEYS)
    | {
        "selected_for_pilot",
        "approved",
        "operator_approved",
        "invocation_approved",
        "proof_bundle_exposure_approved",
        "live_invocation_ready",
        "external_provider_used",
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


def _model_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    payload = _load_json(_rooted(read_model_root) / "local_model_list_inventory.json")
    rows = payload.get("discovered_models")
    return [dict(row) for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _pilot_lane(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> dict[str, Any]:
    preflight = _load_json(_rooted(read_model_root) / "local_lm_proof_response_preflight_receipts.json")
    plan = _load_json(_rooted(read_model_root) / "local_lm_proof_to_response_pilot_plan.json")
    lane = str(preflight.get("pilot_lane") or FIRST_PILOT_LANE)
    if isinstance(plan.get("first_pilot_lane"), Mapping):
        lane = str(plan["first_pilot_lane"].get("lane_ref") or lane)
    return {
        "lane": lane,
        "world_ref": FIRST_PILOT_WORLD_REF,
        "thread_ref": FIRST_PILOT_THREAD_REF,
        "question": str(preflight.get("pilot_question") or FIRST_PILOT_QUESTION),
        "scenario_ref": "finance_capital_hilton_payment_watch",
    }


def _parameter_billion(model: Mapping[str, Any]) -> float | None:
    haystack = f"{model.get('model_name', '')} {model.get('size_or_parameters', '')}"
    match = re.search(r"(?<![a-zA-Z0-9])(\d+(?:\.\d+)?)b(?![a-zA-Z0-9])", haystack, flags=re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1))


def _score_model(model: Mapping[str, Any]) -> tuple[int, int, int, int, str]:
    name = str(model.get("model_name") or "")
    params = _parameter_billion(model)
    exact_preferred = 1 if name == PREFERRED_MODEL_NAME else 0
    fit_band = 1 if params is not None and 4 <= params <= 12 else 0
    family_fit = 1 if name.startswith("qwen3") else 0
    compact = 1 if params is not None and params <= 12 else 0
    return (exact_preferred, fit_band, family_fit, compact, name)


def select_model(models: list[Mapping[str, Any]]) -> dict[str, Any]:
    eligible = [
        dict(model)
        for model in models
        if model.get("local_only") is True
        and model.get("present") is True
        and str(model.get("runtime_ref") or "")
        and model.get("invocation_allowed") is False
        and model.get("proof_bundle_allowed") is False
    ]
    if not eligible:
        return {}
    return max(eligible, key=_score_model)


def _expected_strengths(model: Mapping[str, Any], selected: bool) -> list[str]:
    name = str(model.get("model_name") or "")
    params = _parameter_billion(model)
    strengths = ["local_only", "installed_present", "no_external_provider", "no_tool_authority"]
    if selected:
        strengths.append("recommended_for_first_finance_payment_watch_review")
    if name.startswith("qwen3"):
        strengths.append("good_general_instruction_following_candidate")
    if params is not None and 4 <= params <= 12:
        strengths.append("balanced_size_for_concise_drafting")
    if params is not None and params > 20:
        strengths.append("higher_capacity_candidate")
    return strengths


def _expected_risks(model: Mapping[str, Any], selected: bool) -> list[str]:
    risks = [
        "model_not_invoked_yet",
        "quality_unverified_until_shadow_pilot",
        "requires_redacted_proof_bundle_only",
        "verifier_must_gate_publication",
        "selection_is_not_invocation_approval",
    ]
    params = _parameter_billion(model)
    if params is not None and params > 12:
        risks.append("larger_operational_footprint_for_first_simple_lane")
    if params is not None and params < 8:
        risks.append("smaller_model_may_be_weaker_for_agent_voice")
    if selected:
        risks.append("still_requires_operator_approval_and_invocation_boundary_receipt")
    return risks


def _reason(model: Mapping[str, Any], selected: bool) -> str:
    name = str(model.get("model_name") or "")
    if selected:
        return (
            f"Selected for review because {name} is installed locally, modestly sized, likely capable enough for concise "
            "proof-to-response drafting, and avoids external providers or tool authority."
        )
    params = _parameter_billion(model)
    if params is not None and params > 12:
        return "Rejected for first review because it has a larger operational footprint than needed for the simple Finance / Capital Hilton lane."
    if params is not None and params < 8:
        return "Rejected for first review because a slightly stronger installed local model is available for concise drafting."
    return f"Rejected for first review because {PREFERRED_MODEL_NAME} is a better balance for the initial proof-to-response lane."


def _candidate_row(model: Mapping[str, Any], selected_ref: str) -> dict[str, Any]:
    model_ref = str(model.get("model_ref") or "")
    selected = model_ref == selected_ref
    return {
        "model_ref": model_ref,
        "runtime_ref": str(model.get("runtime_ref") or ""),
        "model_name": str(model.get("model_name") or ""),
        "selected_for_review": selected,
        "reason_selected_or_rejected": _reason(model, selected),
        "expected_strengths": _expected_strengths(model, selected),
        "expected_risks": _expected_risks(model, selected),
        "missing_receipts": [str(item) for item in model.get("missing_receipts") or DEFAULT_MISSING_RECEIPTS],
        "invocation_allowed": False,
        "proof_bundle_allowed": False,
        "local_only": model.get("local_only") is True,
        "present": model.get("present") is True,
        "source": str(model.get("source") or ""),
        "size_or_parameters": str(model.get("size_or_parameters") or ""),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_selection_packet(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    models = _model_rows(read_model_root)
    selected = select_model(models)
    selected_ref = str(selected.get("model_ref") or "")
    candidates = [_candidate_row(model, selected_ref) for model in models]
    recommended_runtime_ref = str(selected.get("runtime_ref") or "")
    recommended_model_ref = selected_ref
    no_suitable_model = not selected
    return {
        "packet_id": "local_model_selection_for_proof_response:finance_capital_hilton:v0",
        "status": PACKET_STATUS,
        "generated_at": generated_at,
        "recommended_model_ref": recommended_model_ref,
        "recommended_runtime_ref": recommended_runtime_ref,
        "recommended_model_name": str(selected.get("model_name") or ""),
        "no_suitable_model": no_suitable_model,
        "no_suitable_model_reason": "" if selected else "No installed local model met local/present/blocked-authority criteria.",
        "ready_for_invocation": False,
        "proof_bundle_allowed": False,
        "external_provider_used": False,
        "verifier_mandatory": True,
        "first_pilot_lane": _pilot_lane(read_model_root),
        "required_operator_decision": "approve_model_selection_for_one_time_pilot",
        "required_operator_decision_options": list(REQUIRED_OPERATOR_DECISION_OPTIONS),
        "selection_criteria": {
            "local_only": True,
            "installed_present": True,
            "best_fit_for_concise_proof_to_response_drafting": True,
            "low_privacy_risk": True,
            "no_external_provider": True,
            "no_tool_authority": True,
            "no_memory_write_authority": True,
            "verifier_mandatory": True,
            "first_pilot_lane": FIRST_PILOT_LANE,
        },
        "candidate_models": candidates,
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
    packet = build_selection_packet(read_model_root=read_model_root, generated_at=generated_at)
    selected_count = sum(1 for row in packet["candidate_models"] if row.get("selected_for_review") is True)
    packet_valid = selected_count == 1 or packet.get("no_suitable_model") is True
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all(row.get("ready") is True for row in preconditions) and packet_valid else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Recommend one installed local model candidate for proof-to-response pilot review without approving invocation.",
        "selection_packet": packet,
        "preconditions": preconditions,
        "summary": {
            "candidate_count": len(packet["candidate_models"]),
            "selected_for_review_count": selected_count,
            "ready_for_invocation": False,
            "proof_bundle_allowed": False,
            "external_provider_used": False,
            "verifier_mandatory": True,
            "first_pilot_lane": FIRST_PILOT_LANE,
        },
        "source_refs": [
            "generated/read_models/local_model_list_inventory.json",
            "generated/read_models/model_catalog_inventory.json",
            "generated/read_models/local_lm_runtime_discovery.json",
            "generated/read_models/local_lm_proof_response_preflight_receipts.json",
            "generated/read_models/local_lm_proof_to_response_pilot_plan.json",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "machine_proof": {
            "review_only": True,
            "model_invocation_performed": False,
            "prompt_sent": False,
            "proof_bundle_sent": False,
            "external_provider_used": False,
            "secrets_read": False,
            "all_models_invocation_blocked": all(row.get("invocation_allowed") is False for row in packet["candidate_models"]),
            "all_models_proof_bundle_blocked": all(row.get("proof_bundle_allowed") is False for row in packet["candidate_models"]),
            "unsafe_true_grants_absent": True,
        },
        "source_content_hashes": {
            "preconditions": _content_hash(preconditions),
            "selection_packet": _content_hash(packet),
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
    scope = packet.get("first_pilot_lane") if isinstance(packet.get("first_pilot_lane"), Mapping) else {}
    lines = [
        "# Local Model Selection For Proof Response",
        "",
        f"Status: {read_model.get('status')}",
        f"Packet status: {packet.get('status')}",
        "",
        "This is review-only. It does not invoke a model, send a prompt, send a proof bundle, connect an external provider, start or stop services, read secrets, or grant authority.",
        "",
        "## Recommendation",
        "",
        f"- Model: `{packet.get('recommended_model_name')}`",
        f"- Model ref: `{packet.get('recommended_model_ref')}`",
        f"- Runtime: `{packet.get('recommended_runtime_ref')}`",
        f"- Ready for invocation: `{str(packet.get('ready_for_invocation')).lower()}`",
        f"- Proof bundle allowed: `{str(packet.get('proof_bundle_allowed')).lower()}`",
        f"- Required operator decision: `{packet.get('required_operator_decision')}`",
        "",
        "## First Pilot Lane",
        "",
        f"- Lane: `{scope.get('lane')}`",
        f"- Question: {scope.get('question')}",
        "",
        "## Candidates",
        "",
    ]
    for row in packet.get("candidate_models") or []:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"- `{row.get('model_name')}`: selected `{str(row.get('selected_for_review')).lower()}`; "
            f"invocation `{str(row.get('invocation_allowed')).lower()}`; proof `{str(row.get('proof_bundle_allowed')).lower()}`. "
            f"{row.get('reason_selected_or_rejected')}"
        )
    lines.extend(["", "## Decision Options", ""])
    for option in packet.get("required_operator_decision_options") or []:
        lines.append(f"- `{option}`")
    lines.append("")
    return "\n".join(lines)


def export_local_model_selection_for_proof_response(
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
    packet = read_model.get("selection_packet", {})
    return {
        "status": str(read_model.get("status") or NOT_READY_STATUS),
        "packet_status": str(packet.get("status") or ""),
        "recommended_model_ref": str(packet.get("recommended_model_ref") or ""),
        "recommended_runtime_ref": str(packet.get("recommended_runtime_ref") or ""),
        "ready_for_invocation": str(packet.get("ready_for_invocation")).lower(),
        "proof_bundle_allowed": str(packet.get("proof_bundle_allowed")).lower(),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Local Model Selection For Proof Response V0.")
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
    result = export_local_model_selection_for_proof_response(
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
