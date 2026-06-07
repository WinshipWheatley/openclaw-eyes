"""Read-only local model list inventory V0.

Lists installed local model candidates without inference. This module may run
the operator-approved non-inference `ollama list` command, and may read existing
generated read models. It does not run models, send prompts, send proof bundles,
call providers, read secrets/API keys, start or stop services, spawn workers,
mutate business state, export PDFs, mark paid, submit, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import local_lm_model_selection_review_packet as selection_review
import local_lm_runtime_discovery
import model_catalog_inventory


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Local Model List Inventory.md")

SCHEMA_VERSION = "local_model_list_inventory_v0"
READ_MODEL_ID = "local_model_list_inventory"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LOCAL_MODEL_LIST_INVENTORY_READY"
NOT_READY_STATUS = "LOCAL_MODEL_LIST_INVENTORY_NOT_READY"
OPERATOR_DECISION = "approve_read_only_local_model_list"

PRECONDITIONS = {
    "model_catalog_inventory": {
        "filename": "model_catalog_inventory.json",
        "accepted_statuses": ("MODEL_CATALOG_INVENTORY_READY",),
    },
    "local_lm_runtime_discovery": {
        "filename": "local_lm_runtime_discovery.json",
        "accepted_statuses": ("LOCAL_LM_RUNTIME_DISCOVERY_READY",),
    },
    "local_lm_model_selection_review": {
        "filename": "local_lm_model_selection_review_packet.json",
        "accepted_statuses": ("LOCAL_LM_MODEL_SELECTION_REVIEW_READY",),
    },
    "local_lm_proof_response_preflight_receipts": {
        "filename": "local_lm_proof_response_preflight_receipts.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_PREFLIGHT_RECEIPTS_READY",),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": "proof_bundle_builder_redaction_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY",),
    },
}

MISSING_RECEIPTS_BEFORE_MODEL_USE = (
    "operator_approval_receipt",
    "model_invocation_boundary_receipt",
    "verifier_pass_fail_receipt",
    "published_response_hash_receipt",
)

RECOMMENDED_NEXT_DECISIONS = (
    "select_one_local_model_for_pilot_review",
    "request_more_detail",
    "reject_for_now",
)

AUTHORITY_BOUNDARY = {
    "listing_models_is_invocation_approval": False,
    "presence_grants_proof_bundle_permission": False,
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
    "http_generation_endpoint_called": False,
    "http_chat_endpoint_called": False,
    "model_weights_loaded_for_inference": False,
    "tool_execution_performed": False,
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
    | set(local_lm_runtime_discovery.UNSAFE_TRUE_KEYS)
    | set(model_catalog_inventory.UNSAFE_TRUE_KEYS)
    | set(selection_review.UNSAFE_TRUE_KEYS)
    | {
        "selected_for_pilot",
        "approved",
        "operator_approved",
        "invocation_approved",
        "proof_bundle_exposure_approved",
        "ready_for_live_invocation",
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


def parse_ollama_list(output: str, *, source: str = "ollama list") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("name "):
            continue
        parts = stripped.split()
        if len(parts) < 4:
            continue
        model_name = parts[0]
        model_id = parts[1]
        size = " ".join(parts[2:4])
        modified = " ".join(parts[4:]) if len(parts) > 4 else ""
        rows.append(
            {
                "model_ref": f"local_model:ollama:{_slug(model_name)}",
                "runtime_ref": "ollama",
                "model_name": model_name,
                "model_family": model_family(model_name),
                "size_or_parameters": size_or_parameters(model_name, size),
                "local_only": True,
                "present": True,
                "invocation_allowed": False,
                "proof_bundle_allowed": False,
                "selected_for_pilot": False,
                "source": source,
                "source_model_id": model_id,
                "modified": modified,
                "missing_receipts": list(MISSING_RECEIPTS_BEFORE_MODEL_USE),
                "notes": "Discovered by non-inference local model listing. Presence is not invocation approval or proof-bundle permission.",
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            }
        )
    return rows


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value.replace(":", "_").replace("/", "_"))
    return slug.strip("_").lower() or "unknown"


def model_family(model_name: str) -> str:
    base = model_name.split(":", 1)[0]
    return base or model_name


def size_or_parameters(model_name: str, size: str) -> str:
    parameter_match = re.search(r"(?<![a-zA-Z0-9])(\d+(?:\.\d+)?[bB])", model_name)
    if parameter_match:
        return f"{size}; parameters {parameter_match.group(1).lower()}"
    return size


def run_ollama_list(*, timeout_seconds: int = 15) -> dict[str, Any]:
    binary = shutil.which("ollama")
    if not binary:
        return {
            "runtime_ref": "ollama",
            "command": "ollama list",
            "list_command_ran": False,
            "returncode": None,
            "stdout": "",
            "stderr": "ollama binary not found",
            "discovery_source_available": False,
        }
    try:
        completed = subprocess.run(
            [binary, "list"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "runtime_ref": "ollama",
            "command": "ollama list",
            "list_command_ran": True,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": f"ollama list timed out after {timeout_seconds} seconds",
            "discovery_source_available": False,
        }
    return {
        "runtime_ref": "ollama",
        "command": "ollama list",
        "list_command_ran": True,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "discovery_source_available": completed.returncode == 0,
    }


def discover_models(*, run_local_commands: bool = True, ollama_list_output: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    command_results: list[dict[str, Any]] = []
    if ollama_list_output is not None:
        command_results.append(
            {
                "runtime_ref": "ollama",
                "command": "ollama list",
                "list_command_ran": False,
                "returncode": 0,
                "stdout": ollama_list_output,
                "stderr": "",
                "discovery_source_available": True,
                "fixture_input": True,
            }
        )
        return parse_ollama_list(ollama_list_output), command_results
    if not run_local_commands:
        command_results.append(
            {
                "runtime_ref": "ollama",
                "command": "ollama list",
                "list_command_ran": False,
                "returncode": None,
                "stdout": "",
                "stderr": "local command execution disabled",
                "discovery_source_available": False,
            }
        )
        return [], command_results
    result = run_ollama_list()
    command_results.append({key: value for key, value in result.items() if key not in {"stdout"}})
    if result.get("returncode") == 0:
        return parse_ollama_list(str(result.get("stdout") or "")), command_results
    return [], command_results


def recommended_next_decision(models_found_count: int) -> str:
    return "select_one_local_model_for_pilot_review" if models_found_count > 0 else "request_more_detail"


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
    run_local_commands: bool = True,
    ollama_list_output: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    models, command_results = discover_models(run_local_commands=run_local_commands, ollama_list_output=ollama_list_output)
    models_found_count = len(models)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all(row.get("ready") is True for row in preconditions) else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "List installed local model names using read-only model inventory, without inference or proof-bundle exposure.",
        "operator_decision": OPERATOR_DECISION,
        "allowed_discovery_used": ["generated_read_models", "ollama list"],
        "forbidden_discovery_not_used": [
            "ollama run",
            "ollama pull",
            "ollama serve",
            "http_generation_or_chat_endpoint",
            "model_weight_loading_for_inference",
            "prompt_or_proof_bundle_transmission",
            "external_provider_api_call",
            "api_key_or_secret_read",
        ],
        "model_invocation_performed": False,
        "prompt_sent": False,
        "proof_bundle_sent": False,
        "external_provider_used": False,
        "secrets_read": False,
        "models_found_count": models_found_count,
        "recommended_next_decision": recommended_next_decision(models_found_count),
        "recommended_next_decision_options": list(RECOMMENDED_NEXT_DECISIONS),
        "discovered_models": models,
        "command_results": command_results,
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "machine_proof": {
            "read_only_inventory": True,
            "model_invocation_performed": False,
            "prompt_sent": False,
            "proof_bundle_sent": False,
            "external_provider_used": False,
            "secrets_read": False,
            "all_models_invocation_blocked": all(row.get("invocation_allowed") is False for row in models),
            "all_models_proof_bundle_blocked": all(row.get("proof_bundle_allowed") is False for row in models),
            "unsafe_true_grants_absent": True,
        },
        "source_refs": [
            "generated/read_models/model_catalog_inventory.json",
            "generated/read_models/local_lm_runtime_discovery.json",
            "generated/read_models/local_lm_model_selection_review_packet.json",
            "generated/read_models/local_lm_proof_response_preflight_receipts.json",
            "generated/read_models/proof_bundle_builder_redaction_status.json",
        ],
        "source_content_hashes": {
            "preconditions": _content_hash(preconditions),
            "discovered_models": _content_hash(models),
            "command_results": _content_hash(command_results),
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
    lines = [
        "# Local Model List Inventory",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "This is read-only local model inventory. It does not invoke a model, send a prompt, send a proof bundle, call an external provider, read secrets, or grant authority.",
        "",
        "## Summary",
        "",
        f"- Models found: `{read_model.get('models_found_count')}`",
        f"- Model invocation performed: `{str(read_model.get('model_invocation_performed')).lower()}`",
        f"- Prompt sent: `{str(read_model.get('prompt_sent')).lower()}`",
        f"- Proof bundle sent: `{str(read_model.get('proof_bundle_sent')).lower()}`",
        f"- External provider used: `{str(read_model.get('external_provider_used')).lower()}`",
        f"- Secrets read: `{str(read_model.get('secrets_read')).lower()}`",
        f"- Recommended next decision: `{read_model.get('recommended_next_decision')}`",
        "",
        "## Models",
        "",
    ]
    for model in read_model.get("discovered_models") or []:
        if not isinstance(model, Mapping):
            continue
        lines.append(
            f"- `{model.get('model_name')}` ({model.get('runtime_ref')}): {model.get('size_or_parameters')}; "
            f"invocation `{str(model.get('invocation_allowed')).lower()}`, proof bundle `{str(model.get('proof_bundle_allowed')).lower()}`"
        )
    lines.extend(["", "## Rules", ""])
    lines.extend(
        [
            "- Listing models is not approval to invoke.",
            "- Presence is not proof-bundle permission.",
            "- No discovered model is selected for the pilot.",
            "- External providers remain blocked.",
            "",
        ]
    )
    return "\n".join(lines)


def export_local_model_list_inventory(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
    run_local_commands: bool = True,
    ollama_list_output: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(
        read_model_root=read_model_root,
        generated_at=generated_at,
        run_local_commands=run_local_commands,
        ollama_list_output=ollama_list_output,
    )
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
        "models_found_count": str(read_model.get("models_found_count") or 0),
        "model_invocation_performed": str(read_model.get("model_invocation_performed")).lower(),
        "prompt_sent": str(read_model.get("prompt_sent")).lower(),
        "proof_bundle_sent": str(read_model.get("proof_bundle_sent")).lower(),
        "external_provider_used": str(read_model.get("external_provider_used")).lower(),
        "secrets_read": str(read_model.get("secrets_read")).lower(),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Read-Only Local Model List Inventory V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--skip-local-commands", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    bridge_root = Path(args.bridge_root) if args.bridge_root else None
    result = export_local_model_list_inventory(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=bridge_root,
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
        run_local_commands=not args.skip_local_commands,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
