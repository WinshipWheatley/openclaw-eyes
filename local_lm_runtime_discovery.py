"""Local LM runtime discovery V0.

Discovery-only read model for local proof-to-response harness candidates. This
module only inspects repo/config path presence, binary presence, and sanitized
process-list matches. It does not invoke models, connect to runtimes, start
services, send prompts, call endpoints, read secrets, mutate business data, or
push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import local_lm_harness_inventory_receipts as harness_inventory
import local_lm_pilot_harness_selection_packet as selection_packet
import proof_to_response_runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Local LM Runtime Discovery.md")

SCHEMA_VERSION = "local_lm_runtime_discovery_v0"
READ_MODEL_ID = "local_lm_runtime_discovery"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LOCAL_LM_RUNTIME_DISCOVERY_READY"
NOT_READY_STATUS = "LOCAL_LM_RUNTIME_DISCOVERY_NOT_READY"

PRECONDITIONS = {
    "local_lm_pilot_harness_selection_packet": {
        "filename": "local_lm_pilot_harness_selection_packet.json",
        "accepted_statuses": ("LOCAL_LM_PILOT_HARNESS_SELECTION_PACKET_READY",),
    },
    "local_lm_harness_inventory_receipts": {
        "filename": "local_lm_harness_inventory_receipts.json",
        "accepted_statuses": ("LOCAL_LM_HARNESS_INVENTORY_RECEIPTS_READY",),
    },
    "local_lm_proof_response_readiness_gate": {
        "filename": "local_lm_proof_to_response_readiness_gate.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_READINESS_GATE_READY",),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": "proof_bundle_builder_redaction_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY",),
    },
}

REQUIRED_RECEIPTS_BEFORE_PILOT = (
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

RUNTIME_SPECS = {
    "ollama": {
        "binary_names": ("ollama",),
        "process_terms": ("ollama",),
        "repo_paths": ("chief_llm.py", "local_shadow_lm_runner.py", "live_lm_shadow_trial.py"),
        "privacy_risk": "local_model_may_hold_sensitive_context_if_unredacted; proof bundle not allowed yet",
        "notes": "Binary/process discovery only. ollama list/run/API calls are not used because they can touch runtime/model state.",
    },
    "llama_cpp_or_llama_server": {
        "binary_names": ("llama-server", "llama-cli", "llama.cpp"),
        "process_terms": ("llama-server", "llama.cpp", "llama-cli"),
        "repo_paths": ("sidecars/llama.cpp", "third_party/llama.cpp"),
        "privacy_risk": "local_server_boundary_unknown_until receipts exist",
        "notes": "Presence does not imply proof-to-response approval.",
    },
    "lm_studio": {
        "binary_names": ("lms", "lmstudio", "lm-studio"),
        "process_terms": ("lmstudio", "lm-studio", "lms"),
        "repo_paths": ("sidecars/lmstudio", "config/lmstudio"),
        "privacy_risk": "desktop app/server may expose broader local state unless tightly receipted",
        "notes": "No LM Studio endpoint or CLI command is called.",
    },
    "local_openai_compatible_server_configs": {
        "binary_names": ("vllm", "litellm", "text-generation-webui", "oobabooga"),
        "process_terms": ("vllm", "litellm", "text-generation-webui", "oobabooga", "openai-compatible"),
        "repo_paths": ("live_lm_shadow_trial.py", "provider_policy_registry.py", "generated/read_models/live_lm_readiness_gate.json"),
        "privacy_risk": "OpenAI-compatible shape can still be external or tool-adjacent without receipts",
        "notes": "Config/code references only; no HTTP endpoint is called.",
    },
    "hermes_sidecar": {
        "binary_names": (),
        "process_terms": ("hermes", "openclaw_hermes_sidecar"),
        "repo_paths": ("openclaw_hermes_sidecar.py", "generated/read_models/openclaw_hermes_sidecar.json", "sidecars/hermes"),
        "privacy_risk": "blocked unless separately registered and receipted for proof-to-response",
        "notes": "Hermes remains blocked without explicit registration and receipt trail.",
    },
    "local_llm_shadow_mode": {
        "binary_names": (),
        "process_terms": (),
        "repo_paths": (
            "proof_to_response_lm_shadow_pilot.py",
            "proof_to_response_runtime.py",
            "generated/read_models/proof_to_response_lm_shadow_pilot.json",
        ),
        "privacy_risk": "fixture/mock-only harness; still no live proof bundle invocation authority",
        "notes": "Current review candidate; not a live runtime.",
    },
    "codex_desktop_operator_assist": {
        "binary_names": ("codex",),
        "process_terms": ("codex",),
        "repo_paths": ("generated/read_models/harness_provider_selection_registry.json",),
        "privacy_risk": "operator-assist path requires explicit scope gate; not selected for live proof bundle invocation",
        "notes": "Blocked unless explicitly approved and scoped.",
    },
    "future_local_open_model": {
        "binary_names": (),
        "process_terms": (),
        "repo_paths": ("generated/read_models/local_lm_proof_to_response_pilot_plan.json",),
        "privacy_risk": "model identity absent; privacy boundary unknown",
        "notes": "Future placeholder, not an installed runtime.",
    },
    "external_llm_blocked_by_default": {
        "binary_names": (),
        "process_terms": (),
        "repo_paths": ("generated/read_models/local_lm_proof_to_response_readiness_gate.json",),
        "privacy_risk": "external provider blocked for private/local proof bundles",
        "notes": "External providers remain blocked by default.",
    },
}

AUTHORITY_BOUNDARY = {
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
    "prompt_sent_to_model": False,
    "proof_bundle_sent_to_model": False,
    "http_endpoint_called": False,
    "model_weights_loaded": False,
    "secret_read": False,
    "api_key_read": False,
    "config_altered": False,
    "tool_execution_performed": False,
    "business_action_performed": False,
    "ledger_mutation_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "paid_marking_performed": False,
    "git_push_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(harness_inventory.UNSAFE_TRUE_KEYS)
    | set(selection_packet.UNSAFE_TRUE_KEYS)
    | set(proof_to_response_runtime.UNSAFE_TRUE_KEYS)
    | {
        "ready_for_pilot",
        "external_provider_used",
        "proof_bundle_visible_to_model",
        "tool_access",
        "memory_write_access",
        "business_action_authority",
        "approved",
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


def _rooted(path: Path | str, *, root: Path = ROOT) -> Path:
    path = Path(path)
    return path if path.is_absolute() else root / path


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


def binary_presence(binary_names: Iterable[str], *, which=shutil.which) -> dict[str, str]:
    found: dict[str, str] = {}
    for name in binary_names:
        path = which(str(name))
        if path:
            found[str(name)] = path
    return found


def sanitized_process_snapshot() -> list[dict[str, str]]:
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid=,comm=,args="],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    rows: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 2:
            continue
        pid, command = parts[0], parts[1]
        args = parts[2] if len(parts) > 2 else ""
        rows.append({"pid": pid, "command": command, "search_text": f"{command} {args}".lower()})
    return rows


def matching_processes(process_terms: Iterable[str], process_rows: Iterable[Mapping[str, str]]) -> list[dict[str, str]]:
    terms = [str(term).lower() for term in process_terms if str(term)]
    matches: list[dict[str, str]] = []
    for row in process_rows:
        text = str(row.get("search_text") or "").lower()
        matched = [term for term in terms if term in text]
        if matched:
            matches.append(
                {
                    "pid": str(row.get("pid") or ""),
                    "command": str(row.get("command") or ""),
                    "matched_terms": ",".join(sorted(set(matched))),
                }
            )
    return matches


def repo_path_presence(repo_paths: Iterable[str], *, repo_root: Path = ROOT) -> dict[str, bool]:
    root = _rooted(repo_root)
    return {str(path): (root / str(path)).exists() for path in repo_paths}


def _present_from_evidence(
    *,
    binaries: Mapping[str, str],
    path_presence: Mapping[str, bool],
    runtime_ref: str,
) -> bool | str:
    if runtime_ref == "external_llm_blocked_by_default":
        return "unknown"
    if binaries or any(path_presence.values()):
        return True
    if runtime_ref in {"local_llm_shadow_mode", "future_local_open_model"}:
        return "unknown"
    return False


def runtime_candidates(
    *,
    repo_root: Path = ROOT,
    which=shutil.which,
    process_rows: list[Mapping[str, str]] | None = None,
) -> list[dict[str, Any]]:
    rows = process_rows if process_rows is not None else sanitized_process_snapshot()
    candidates: list[dict[str, Any]] = []
    for runtime_ref, spec in RUNTIME_SPECS.items():
        binaries = binary_presence(spec["binary_names"], which=which)
        paths = repo_path_presence(spec["repo_paths"], repo_root=repo_root)
        processes = matching_processes(spec["process_terms"], rows)
        present = _present_from_evidence(binaries=binaries, path_presence=paths, runtime_ref=runtime_ref)
        already_running: bool | str = bool(processes) if spec["process_terms"] else "unknown"
        if runtime_ref == "external_llm_blocked_by_default":
            already_running = "unknown"
        missing_receipts = list(REQUIRED_RECEIPTS_BEFORE_PILOT)
        if runtime_ref == "hermes_sidecar":
            missing_receipts.append("explicit_hermes_proof_to_response_registration_receipt")
        if runtime_ref == "future_local_open_model":
            missing_receipts.append("approved_local_model_identity_receipt")
        if runtime_ref == "codex_desktop_operator_assist":
            missing_receipts.append("codex_desktop_operator_assist_scope_receipt")
        if runtime_ref == "external_llm_blocked_by_default":
            missing_receipts.append("external_provider_exception_gate_receipt")
        candidates.append(
            {
                "runtime_ref": runtime_ref,
                "present": present,
                "already_running": already_running,
                "invocation_allowed": False,
                "proof_response_pilot_allowed": False,
                "discovery_method": {
                    "binary_path_check": sorted(binaries),
                    "repo_path_presence": paths,
                    "process_list_match_only": bool(spec["process_terms"]),
                    "version_command_run": False,
                    "http_endpoint_called": False,
                    "model_command_run": False,
                    "secret_files_read": False,
                },
                "binary_paths": binaries,
                "process_matches": processes,
                "missing_receipts": list(dict.fromkeys(missing_receipts)),
                "privacy_risk": str(spec["privacy_risk"]),
                "notes": str(spec["notes"]),
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            }
        )
    return candidates


def recommended_candidate(candidates: list[Mapping[str, Any]]) -> str:
    for candidate in candidates:
        if candidate.get("runtime_ref") == "local_llm_shadow_mode":
            return "local_llm_shadow_mode"
    return "none"


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    repo_root: Path = ROOT,
    generated_at: str | None = None,
    process_rows: list[Mapping[str, str]] | None = None,
    which=shutil.which,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    candidates = runtime_candidates(repo_root=repo_root, which=which, process_rows=process_rows)
    all_ready = all(row.get("ready") is True for row in preconditions)
    recommended = recommended_candidate(candidates)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Discover local LM runtimes/harnesses for a future proof-to-response pilot without invoking or connecting to them.",
        "preconditions": preconditions,
        "runtime_candidates": candidates,
        "recommended_candidate_ref": recommended,
        "ready_for_pilot": False,
        "next_safe_action": "Collect missing receipts and operator approval before any local runtime sees a redacted proof bundle.",
        "rules": [
            "External LLM remains blocked.",
            "Hermes sidecar remains blocked unless separately registered and receipted.",
            "Local runtime presence does not imply invocation approval.",
            "No model can see proof bundles yet.",
            "No tool authority.",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "machine_proof": {
            "discovery_only": True,
            "repo_files_inspected": True,
            "known_config_paths_inspected_by_presence_only": True,
            "process_list_inspected_sanitized": True,
            "secrets_read": False,
            "api_keys_read": False,
            "model_invoked": False,
            "runtime_connected": False,
            "service_started": False,
            "worker_spawn_performed": False,
            "prompt_sent_to_model": False,
            "proof_bundle_sent_to_model": False,
            "http_endpoint_called": False,
            "model_weights_loaded": False,
            "unsafe_true_grants_absent": True,
        },
        "source_content_hashes": {
            "preconditions": _content_hash(preconditions),
            "runtime_candidates": _content_hash(candidates),
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
        "# Local LM Runtime Discovery",
        "",
        f"Status: {read_model.get('status')}",
        f"Ready for pilot: `{str(read_model.get('ready_for_pilot')).lower()}`",
        f"Recommended candidate: `{read_model.get('recommended_candidate_ref')}`",
        "",
        "This is discovery only. It does not invoke a model, connect a runtime, start a service, call an endpoint, send a prompt, or expose a proof bundle.",
        "",
        "## Candidates",
        "",
    ]
    for row in read_model.get("runtime_candidates") or []:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"- `{row.get('runtime_ref')}`: present `{row.get('present')}`, running `{row.get('already_running')}`, "
            f"invocation `{str(row.get('invocation_allowed')).lower()}`, pilot `{str(row.get('proof_response_pilot_allowed')).lower()}`"
        )
    lines.extend(
        [
            "",
            "## Missing Receipts",
            "",
        ]
    )
    recommended = str(read_model.get("recommended_candidate_ref") or "")
    for row in read_model.get("runtime_candidates") or []:
        if isinstance(row, Mapping) and row.get("runtime_ref") == recommended:
            for receipt in row.get("missing_receipts") or []:
                lines.append(f"- `{receipt}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Runtime presence is not invocation approval.",
            "- External providers remain blocked.",
            "- Hermes remains blocked unless separately registered and receipted.",
            "- No model can see proof bundles yet.",
            "- Tool authority remains false.",
            "",
            "## Next Safe Action",
            "",
            str(read_model.get("next_safe_action") or ""),
            "",
        ]
    )
    return "\n".join(lines)


def export_local_lm_runtime_discovery(
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
        "recommended_candidate_ref": str(read_model.get("recommended_candidate_ref") or ""),
        "ready_for_pilot": str(read_model.get("ready_for_pilot")).lower(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Local LM Runtime Discovery V0.")
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
    result = export_local_lm_runtime_discovery(
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
