"""Model catalog inventory V0.

Discovery/catalog-only inventory of local, sidecar, operator-assist, external,
and future model/harness candidates for OpenClaw proof-to-response and agentic
work. This module reads existing read models and repo metadata only. It does not
invoke models, connect runtimes, start services, send prompts or proof bundles,
call provider APIs, browse, read secrets/API keys, spawn workers, mutate business
state, export PDFs, mark paid, submit, or push.
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
import local_lm_runtime_discovery
import proof_to_response_runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Model Catalog Inventory.md")

SCHEMA_VERSION = "model_catalog_inventory_v0"
READ_MODEL_ID = "model_catalog_inventory"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "MODEL_CATALOG_INVENTORY_READY"
NOT_READY_STATUS = "MODEL_CATALOG_INVENTORY_NOT_READY"

PRECONDITIONS = {
    "local_lm_runtime_discovery": {
        "filename": "local_lm_runtime_discovery.json",
        "accepted_statuses": ("LOCAL_LM_RUNTIME_DISCOVERY_READY",),
    },
    "local_lm_proof_response_preflight_receipts": {
        "filename": "local_lm_proof_response_preflight_receipts.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_PREFLIGHT_RECEIPTS_READY",),
    },
    "local_lm_harness_inventory_receipts": {
        "filename": "local_lm_harness_inventory_receipts.json",
        "accepted_statuses": ("LOCAL_LM_HARNESS_INVENTORY_RECEIPTS_READY",),
    },
    "harness_provider_selection": {
        "filename": "harness_provider_selection_registry.json",
        "accepted_statuses": ("HARNESS_PROVIDER_SELECTION_READY",),
    },
    "proof_bundle_redaction_hardening": {
        "filename": "proof_bundle_redaction_policy.json",
        "accepted_statuses": ("PROOF_BUNDLE_REDACTION_HARDENING_READY",),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": "proof_bundle_builder_redaction_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY",),
    },
    "goldilocks_gate_calibration": {
        "filename": "goldilocks_gate_calibration.json",
        "accepted_statuses": ("GOLDILOCKS_GATE_CALIBRATION_READY",),
    },
}

REQUIRED_MISSING_RECEIPTS = (
    "operator_approval_receipt",
    "model_harness_selected_receipt",
    "model_invocation_boundary_receipt",
    "no_external_provider_receipt",
    "no_tool_authority_receipt",
    "no_memory_promotion_receipt",
    "redacted_proof_bundle_receipt",
    "verifier_pass_fail_receipt",
    "published_response_hash_receipt",
)

AUTHORITY_BOUNDARY = {
    "invocation_allowed": False,
    "proof_bundle_allowed": False,
    "protected_actions_allowed": False,
    "authority_granted": False,
    "authority_grant_allowed": False,
    "model_invocation_allowed": False,
    "live_lm_invocation_allowed": False,
    "external_provider_connect_allowed": False,
    "provider_key_material_access_allowed": False,
    "tool_authority": False,
    "tool_authority_allowed": False,
    "tool_execution_allowed": False,
    "memory_write_authority": False,
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
    "model_invoked": False,
    "runtime_connected": False,
    "external_provider_connected": False,
    "provider_api_called": False,
    "prompt_sent": False,
    "proof_bundle_sent": False,
    "service_started": False,
    "worker_spawn_performed": False,
    "secret_read": False,
    "api_key_read": False,
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
    | set(harness_inventory.UNSAFE_TRUE_KEYS)
    | set(local_lm_runtime_discovery.UNSAFE_TRUE_KEYS)
    | set(proof_to_response_runtime.UNSAFE_TRUE_KEYS)
    | {
        "external_provider_used",
        "configured_provider_approved",
        "proof_response_pilot_allowed",
        "ready_for_live_invocation",
        "approved",
        "paid",
        "sent",
        "submitted",
        "executed",
    }
)

LOCAL_RUNTIME_REFS = {
    "ollama": "Ollama",
    "llama_cpp_or_llama_server": "llama.cpp / llama-server",
    "lm_studio": "LM Studio",
    "local_openai_compatible_server_configs": "Local OpenAI-compatible server",
    "future_local_open_model": "Future local open model",
}

SIDECAR_REFS = {
    "hermes_sidecar": "Hermes sidecar candidate",
    "local_llm_shadow_mode": "local_llm_shadow_mode",
}

OPERATOR_ASSIST_CANDIDATES = (
    ("codex_desktop_operator_assist", "Codex Desktop operator assist", "operator_assist"),
    ("mac_codex", "Mac Codex", "operator_assist"),
    ("pc_codex", "PC Codex", "operator_assist"),
)

EXTERNAL_PROVIDER_FAMILIES = (
    ("openai", "OpenAI", "external", "GPT / Codex family"),
    ("anthropic", "Anthropic", "external", "Claude family"),
    ("google", "Google", "external", "Gemini family"),
    ("mistral", "Mistral", "external", "Mistral family"),
    ("groq", "Groq", "external", "Groq-hosted open model family"),
    ("together", "Together", "external", "Together-hosted open model family"),
    ("openrouter", "OpenRouter", "external", "Router/provider aggregator"),
    ("nvidia_nim", "NVIDIA NIM", "external", "NVIDIA NIM hosted/local-enterprise family"),
)

BLOCKED_UNKNOWN_FUTURE = (
    ("unregistered_provider", "Unregistered provider"),
    ("unverified_model", "Unverified model"),
    ("missing_privacy_policy", "Missing privacy policy"),
    ("missing_receipt_path", "Missing receipt path"),
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


def _runtime_rows(read_model_root: Path) -> list[dict[str, Any]]:
    payload = _load_json(_rooted(read_model_root) / "local_lm_runtime_discovery.json")
    rows = payload.get("runtime_candidates")
    return [dict(row) for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _provider_registry_text(read_model_root: Path) -> str:
    refs = (
        "harness_provider_selection_registry.json",
        "provider_policy_registry.json",
        "operator_assist_provider_registry.json",
        "agent_roster_model_backend_policy.json",
        "agent_voice_response_layer.json",
    )
    chunks: list[str] = []
    root = _rooted(read_model_root)
    for ref in refs:
        path = root / ref
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8", errors="ignore").lower())
    for ref in ("harness_provider_selection_registry.py", "agent_roster_model_backend_policy.py", "agent_voice_response_layer.py"):
        path = ROOT / ref
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8", errors="ignore").lower())
    return "\n".join(chunks)


def _configured_from_catalog_name(text: str, *needles: str) -> bool | str:
    return True if any(needle.lower() in text for needle in needles) else "unknown"


def _base_candidate(
    *,
    candidate_ref: str,
    provider_or_runtime: str,
    model_or_harness_name: str,
    candidate_class: str,
    locality: str,
    present: bool | str = "unknown",
    configured: bool | str = "unknown",
    running: bool | str = "unknown",
    model_family: str = "",
    data_classes_allowed: list[str] | None = None,
    data_classes_forbidden: list[str] | None = None,
    privacy_risk: str = "",
    best_fit_use_cases: list[str] | None = None,
    forbidden_use_cases: list[str] | None = None,
    missing_receipts: list[str] | None = None,
    next_required_decision: str = "select_model_for_review",
) -> dict[str, Any]:
    return {
        "candidate_ref": candidate_ref,
        "candidate_class": candidate_class,
        "provider_or_runtime": provider_or_runtime,
        "model_or_harness_name": model_or_harness_name,
        "model_family": model_family,
        "locality": locality,
        "present": present,
        "configured": configured,
        "running": running,
        "invocation_allowed": False,
        "proof_bundle_allowed": False,
        "external_provider_used": False,
        "data_classes_allowed": list(data_classes_allowed or []),
        "data_classes_forbidden": list(data_classes_forbidden or _default_forbidden_classes(locality)),
        "privacy_risk": privacy_risk or _default_privacy_risk(locality),
        "tool_authority": False,
        "memory_write_authority": False,
        "business_action_authority": False,
        "best_fit_use_cases": list(best_fit_use_cases or _default_best_fit(locality)),
        "forbidden_use_cases": list(forbidden_use_cases or _default_forbidden_use_cases(locality)),
        "missing_receipts": list(missing_receipts or REQUIRED_MISSING_RECEIPTS),
        "next_required_decision": next_required_decision,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _default_forbidden_classes(locality: str) -> list[str]:
    common = [
        "credentials_or_tokens",
        "operator_device_session_secrets",
        "raw_prompt_dumps",
        "hidden_machine_contracts",
        "tool_authority",
    ]
    if locality == "external":
        return common + ["private_finance_or_client_proof", "raw_bank_details", "proof_bundle_contents_without_exception_gate"]
    if locality in {"local", "sidecar"}:
        return common + ["raw_bank_details_unredacted", "source_workbook_bodies", "raw_artifact_ocr_text_without_redaction"]
    return common + ["private_proof_without_receipts"]


def _default_privacy_risk(locality: str) -> str:
    if locality == "external":
        return "External providers are blocked by default for private proof; provider metadata only."
    if locality in {"local", "sidecar"}:
        return "Locality reduces egress risk but does not grant proof exposure or authority."
    if locality == "operator_assist":
        return "Operator-assist harness needs explicit scope and cannot receive proof bundles by inventory alone."
    return "Unknown provider/model lacks privacy policy, receipt path, and authority boundary."


def _default_best_fit(locality: str) -> list[str]:
    if locality in {"local", "sidecar"}:
        return ["private_finance_client_proof_after_approval", "proof_to_response_drafting_after_verifier_gate"]
    if locality == "operator_assist":
        return ["code_or_operator_assist_after_scope_gate", "review_packet_generation_after_receipts"]
    if locality == "external":
        return ["non_private_catalog_metadata_only", "future_public_or_redacted_tasks_after_exception_gate"]
    return ["none_until_registered"]


def _default_forbidden_use_cases(locality: str) -> list[str]:
    base = ["business_execution", "tool_use", "memory_promotion_to_truth", "authority_grant"]
    if locality == "external":
        return base + ["private_finance_client_proof", "raw_ledger_workbook_or_email_bodies"]
    return base + ["proof_bundle_exposure_without_operator_approval"]


def local_runtime_candidates(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    runtime_rows = {str(row.get("runtime_ref")): row for row in _runtime_rows(read_model_root)}
    candidates: list[dict[str, Any]] = []
    for runtime_ref, display_name in LOCAL_RUNTIME_REFS.items():
        row = runtime_rows.get(runtime_ref, {})
        candidates.append(
            _base_candidate(
                candidate_ref=f"model_candidate:local_runtime:{runtime_ref}",
                provider_or_runtime=runtime_ref,
                model_or_harness_name=display_name,
                candidate_class="local_runtime_installed",
                locality="local",
                present=row.get("present", "unknown"),
                configured=True if row.get("present") is True else "unknown",
                running=row.get("already_running", "unknown"),
                model_family=display_name,
                privacy_risk=str(row.get("privacy_risk") or _default_privacy_risk("local")),
                missing_receipts=list(row.get("missing_receipts") or REQUIRED_MISSING_RECEIPTS),
                next_required_decision="select_model_for_review",
            )
        )
    return candidates


def sidecar_candidates(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    runtime_rows = {str(row.get("runtime_ref")): row for row in _runtime_rows(read_model_root)}
    candidates: list[dict[str, Any]] = []
    for runtime_ref, display_name in SIDECAR_REFS.items():
        row = runtime_rows.get(runtime_ref, {})
        next_decision = "stay_shadow_only" if runtime_ref == "local_llm_shadow_mode" else "select_model_for_review"
        candidates.append(
            _base_candidate(
                candidate_ref=f"model_candidate:sidecar:{runtime_ref}",
                provider_or_runtime=runtime_ref,
                model_or_harness_name=display_name,
                candidate_class="local_sidecar_harness",
                locality="sidecar",
                present=row.get("present", "unknown"),
                configured=True if row.get("present") is True else "unknown",
                running=row.get("already_running", "unknown"),
                model_family=display_name,
                privacy_risk=str(row.get("privacy_risk") or _default_privacy_risk("sidecar")),
                missing_receipts=list(row.get("missing_receipts") or REQUIRED_MISSING_RECEIPTS),
                next_required_decision=next_decision,
            )
        )
    return candidates


def operator_assist_candidates(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    runtime_rows = {str(row.get("runtime_ref")): row for row in _runtime_rows(read_model_root)}
    text = _provider_registry_text(read_model_root)
    candidates: list[dict[str, Any]] = []
    for ref, display_name, locality in OPERATOR_ASSIST_CANDIDATES:
        row = runtime_rows.get(ref, {})
        present: bool | str = row.get("present", "unknown")
        configured: bool | str = _configured_from_catalog_name(text, ref, display_name)
        if ref in {"mac_codex", "pc_codex"} and configured == "unknown":
            configured = True if "mac_codex_ui_worker" in text or "pc_codex_backend_worker" in text else "unknown"
        candidates.append(
            _base_candidate(
                candidate_ref=f"model_candidate:operator_assist:{ref}",
                provider_or_runtime=ref,
                model_or_harness_name=display_name,
                candidate_class="operator_assist_harness",
                locality=locality,
                present=present,
                configured=configured,
                running=row.get("already_running", "unknown"),
                model_family="Codex/operator-assist",
                privacy_risk=_default_privacy_risk("operator_assist"),
                missing_receipts=list(REQUIRED_MISSING_RECEIPTS) + ["operator_assist_scope_receipt"],
                next_required_decision="select_model_for_review",
            )
        )
    return candidates


def external_provider_candidates(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    text = _provider_registry_text(read_model_root)
    candidates: list[dict[str, Any]] = []
    aliases = {
        "openai": ("openai", "gpt", "codex"),
        "anthropic": ("anthropic", "claude"),
        "google": ("google", "gemini"),
        "mistral": ("mistral",),
        "groq": ("groq",),
        "together": ("together",),
        "openrouter": ("openrouter",),
        "nvidia_nim": ("nvidia", "nim"),
    }
    for ref, display_name, locality, family in EXTERNAL_PROVIDER_FAMILIES:
        configured = _configured_from_catalog_name(text, *aliases.get(ref, (ref,)))
        candidates.append(
            _base_candidate(
                candidate_ref=f"model_candidate:external_provider:{ref}",
                provider_or_runtime=ref,
                model_or_harness_name=display_name,
                candidate_class="external_provider_catalog",
                locality=locality,
                present="unknown",
                configured=configured,
                running="unknown",
                model_family=family,
                data_classes_allowed=[],
                data_classes_forbidden=_default_forbidden_classes("external"),
                privacy_risk=_default_privacy_risk("external"),
                best_fit_use_cases=["metadata_catalog_only", "future_non_private_or_redacted_work_after_exception_gate"],
                forbidden_use_cases=_default_forbidden_use_cases("external"),
                missing_receipts=list(REQUIRED_MISSING_RECEIPTS) + ["external_provider_exception_gate_receipt", "provider_privacy_policy_receipt"],
                next_required_decision="request_external_catalog_research",
            )
        )
    return candidates


def blocked_unknown_future_candidates() -> list[dict[str, Any]]:
    return [
        _base_candidate(
            candidate_ref=f"model_candidate:blocked_future:{ref}",
            provider_or_runtime=ref,
            model_or_harness_name=display_name,
            candidate_class="blocked_unknown_or_future",
            locality="unknown",
            present="unknown",
            configured=False,
            running="unknown",
            model_family="unknown",
            data_classes_allowed=[],
            data_classes_forbidden=_default_forbidden_classes("unknown"),
            privacy_risk=_default_privacy_risk("unknown"),
            best_fit_use_cases=[],
            forbidden_use_cases=["all_work_until_registered_and_receipted"],
            missing_receipts=list(REQUIRED_MISSING_RECEIPTS) + ["provider_registration_receipt", "privacy_policy_receipt"],
            next_required_decision="reject_for_now",
        )
        for ref, display_name in BLOCKED_UNKNOWN_FUTURE
    ]


def build_candidates(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    return [
        *local_runtime_candidates(read_model_root),
        *sidecar_candidates(read_model_root),
        *operator_assist_candidates(read_model_root),
        *external_provider_candidates(read_model_root),
        *blocked_unknown_future_candidates(),
    ]


def summary(candidates: list[Mapping[str, Any]]) -> dict[str, Any]:
    local_count = sum(1 for row in candidates if row.get("locality") in {"local", "sidecar", "operator_assist"})
    external_count = sum(1 for row in candidates if row.get("candidate_class") == "external_provider_catalog")
    return {
        "total_candidates": len(candidates),
        "local_candidates": local_count,
        "external_catalog_candidates": external_count,
        "candidates_currently_invocation_allowed": sum(1 for row in candidates if row.get("invocation_allowed") is True),
        "candidates_proof_bundle_allowed": sum(1 for row in candidates if row.get("proof_bundle_allowed") is True),
        "recommended_next_decision": "select_model_for_review",
        "recommended_decision_options": [
            "select_model_for_review",
            "request_external_catalog_research",
            "stay_shadow_only",
            "reject_for_now",
        ],
    }


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    candidates = build_candidates(read_model_root)
    candidate_summary = summary(candidates)
    all_ready = all(row.get("ready") is True for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Catalog known model and harness candidates without invoking models, connecting runtimes, or calling providers.",
        "policy": {
            "local_models_preferred_for_private_finance_client_proof": True,
            "external_providers_blocked_by_default_for_private_proof": True,
            "external_provider_catalog_metadata_only": True,
            "configured_provider_does_not_imply_approval": True,
            "powerful_model_does_not_imply_authority": True,
            "provider_choice_does_not_grant_tool_access": True,
            "inventory_does_not_approve_proof_exposure": True,
            "no_candidate_invocation_allowed": True,
        },
        "preconditions": preconditions,
        "model_candidates": candidates,
        "summary": candidate_summary,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "machine_proof": {
            "catalog_only": True,
            "model_invoked": False,
            "runtime_connected": False,
            "external_provider_connected": False,
            "provider_api_called": False,
            "prompt_sent": False,
            "proof_bundle_sent": False,
            "secret_read": False,
            "api_key_read": False,
            "worker_spawn_performed": False,
            "unsafe_true_grants_absent": True,
        },
        "source_refs": [
            "generated/read_models/local_lm_runtime_discovery.json",
            "generated/read_models/local_lm_harness_inventory_receipts.json",
            "generated/read_models/harness_provider_selection_registry.json",
            "generated/read_models/local_lm_proof_to_response_readiness_gate.json",
            "generated/read_models/local_lm_proof_response_pilot_approval_packet.json",
            "generated/read_models/proof_bundle_redaction_policy.json",
            "generated/read_models/proof_bundle_builder_redaction_status.json",
            "generated/read_models/goldilocks_gate_calibration.json",
        ],
        "source_content_hashes": {
            "preconditions": _content_hash(preconditions),
            "model_candidates": _content_hash(candidates),
            "summary": _content_hash(candidate_summary),
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
    summary_payload = read_model.get("summary") if isinstance(read_model.get("summary"), Mapping) else {}
    lines = [
        "# Model Catalog Inventory",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "This is catalog/discovery only. It does not invoke models, connect runtimes, call provider APIs, read secrets, send prompts, or expose proof bundles.",
        "",
        "## Summary",
        "",
        f"- Total candidates: `{summary_payload.get('total_candidates')}`",
        f"- Local candidates: `{summary_payload.get('local_candidates')}`",
        f"- External catalog candidates: `{summary_payload.get('external_catalog_candidates')}`",
        f"- Invocation allowed: `{summary_payload.get('candidates_currently_invocation_allowed')}`",
        f"- Proof bundle allowed: `{summary_payload.get('candidates_proof_bundle_allowed')}`",
        f"- Recommended next decision: `{summary_payload.get('recommended_next_decision')}`",
        "",
        "## Policy",
        "",
        "- Local models are preferred for private finance/client proof.",
        "- External providers are blocked by default for private proof.",
        "- External provider catalog entries are metadata only.",
        "- Configured provider does not imply approval.",
        "- Powerful model does not imply authority.",
        "- Provider choice does not grant tool access.",
        "- Inventory does not approve proof exposure.",
        "",
        "## Candidates",
        "",
    ]
    for row in read_model.get("model_candidates") or []:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"- `{row.get('candidate_ref')}` ({row.get('candidate_class')}): {row.get('model_or_harness_name')} "
            f"present `{row.get('present')}`, configured `{row.get('configured')}`, running `{row.get('running')}`, "
            f"invocation `{str(row.get('invocation_allowed')).lower()}`, proof `{str(row.get('proof_bundle_allowed')).lower()}`"
        )
    lines.append("")
    return "\n".join(lines)


def export_model_catalog_inventory(
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
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": wiki_path.as_posix(),
        "total_candidates": str(read_model["summary"]["total_candidates"]),
        "candidates_currently_invocation_allowed": str(read_model["summary"]["candidates_currently_invocation_allowed"]),
        "candidates_proof_bundle_allowed": str(read_model["summary"]["candidates_proof_bundle_allowed"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Model Catalog Inventory V0.")
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
    result = export_model_catalog_inventory(
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
