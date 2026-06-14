"""Worker Package Staging V0.

Builds local worker package stubs from recorded agent handoff events without
spawning workers, executing tools, editing source code, creating review packets,
or granting any business authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Worker Package Staging.md")

SCHEMA_VERSION = "worker_package_staging_v0"
READ_MODEL_ID = "worker_package_staging_status"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
STATUS_READY = "WORKER_PACKAGE_STAGING_READY"
STATUS_NOT_READY = "WORKER_PACKAGE_STAGING_NOT_READY"
REVIEW_PACKET_INDEX_NAME = "workroom_review_packet_index.json"

PRECONDITION_FILES = {
    "agent_handoff_event_consumer": "agent_handoff_event_status.json",
    "spawned_worker_package_lifecycle": "spawned_worker_package_lifecycle.json",
    "workroom_review_packet_index": REVIEW_PACKET_INDEX_NAME,
}

PRECONDITION_STATUSES = {
    "agent_handoff_event_consumer": "AGENT_HANDOFF_EVENT_CONSUMER_READY",
    "spawned_worker_package_lifecycle": "SPAWNED_WORKER_PACKAGE_LIFECYCLE_READY",
    "workroom_review_packet_index": "WORKROOM_REVIEW_PACKET_INDEX_READY",
}

SUPPORTED_WORKERS = {"pc_codex", "mac_codex"}

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "worker_spawn_allowed": False,
    "worker_assignment_allowed": False,
    "worker_execution_allowed": False,
    "tool_execution_allowed": False,
    "external_llm_allowed": False,
    "local_model_runtime_allowed": False,
    "agent_loop_allowed": False,
    "git_push_allowed": False,
    "business_action_allowed": False,
    "sent": False,
    "paid": False,
}

BLOCKED_ACTIONS = [
    "send_email",
    "open_gmail",
    "open_browser",
    "open_coupa",
    "mutate_ledger",
    "mutate_workbook",
    "export_pdf",
    "mark_paid",
    "submit_portal",
    "push_git",
    "spawn_worker",
    "assign_worker",
    "run_worker",
    "run_child_agent",
    "launch_agent_loop",
    "call_external_llm",
    "connect_local_model_runtime",
    "run_live_provider",
    "edit_source_code_during_staging",
    "create_review_packet_before_worker_result",
]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
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


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _list(value) if str(item)]


def _append_unique(values: list[str], *items: str) -> list[str]:
    merged = list(values)
    merged.extend(item for item in items if item)
    return list(dict.fromkeys(merged))


def _short_hash(parts: list[str]) -> str:
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, filename in PRECONDITION_FILES.items():
        payload = _load_json(root / filename)
        observed = str(payload.get("status") or payload.get("contract_status") or "")
        required = PRECONDITION_STATUSES[ref]
        rows.append(
            {
                "precondition_ref": ref,
                "required_status": required,
                "observed_status": observed,
                "ready": observed == required,
                "source_ref": f"generated/read_models/{filename}",
            }
        )
    return rows


def _allowed_paths(worker_ref: str) -> list[str]:
    if worker_ref == "mac_codex":
        return [
            "generated/read_models/",
            "generated/wiki/openclaw/",
            "tests/",
            "mac_ui_artifacts/",
        ]
    return [
        "generated/read_models/",
        "generated/wiki/openclaw/",
        "tests/",
        "scripts/",
    ]


def _expected_outputs(worker_ref: str) -> list[str]:
    if worker_ref == "mac_codex":
        return [
            "result receipt read model",
            "screenshot or UI proof refs if UI changed",
            "focused validation summary",
        ]
    return [
        "result receipt read model",
        "focused pytest results",
        "py_compile or JSON parse results as relevant",
    ]


def _tests_required(worker_ref: str) -> list[str]:
    if worker_ref == "mac_codex":
        return [
            "focused UI smoke or screenshot proof if UI changes",
            "JSON parse for generated read models",
            "unsafe true-grant scan",
        ]
    return [
        "focused pytest for touched backend surface",
        "py_compile for changed Python files",
        "JSON parse for generated read models",
        "unsafe true-grant scan",
    ]


def _event_to_package_stub(event: Mapping[str, Any]) -> dict[str, Any] | None:
    if str(event.get("status") or "") != "HANDOFF_EVENT_RECORDED":
        return None
    worker_ref = str(event.get("to_agent_or_worker") or "").lower()
    if worker_ref not in SUPPORTED_WORKERS:
        return None
    event_id = str(event.get("event_id") or "")
    handoff_ref = str(event.get("handoff_ref") or "")
    channel_ref = str(event.get("channel_ref") or "")
    package_type = str(event.get("package_type") or "")
    package_id = f"worker_package_stub:{_short_hash([event_id, handoff_ref, worker_ref, channel_ref])}"
    return {
        "package_id": package_id,
        "worker_ref": worker_ref,
        "channel_ref": channel_ref,
        "source_handoff_ref": handoff_ref,
        "source_handoff_event_id": event_id,
        "source_package_type": package_type,
        "goal": str(event.get("reason") or f"Stage a bounded {worker_ref} package from {handoff_ref}."),
        "allowed_files_or_paths": _allowed_paths(worker_ref),
        "blocked_actions": list(BLOCKED_ACTIONS),
        "expected_outputs": _expected_outputs(worker_ref),
        "tests_required": _tests_required(worker_ref),
        "result_receipt_required": True,
        "status": "PACKAGE_STAGED",
        "business_action_allowed": False,
        "worker_inherits_speaker_authority": False,
        "operator_approval_required_before_execution": True,
        "review_packet_created": False,
        "worker_spawn_performed": False,
        "worker_assignment_performed": False,
        "worker_execution_performed": False,
        "tool_execution_performed": False,
        "git_push_allowed": False,
        "git_push_performed": False,
        "business_action_performed": False,
        "proof_refs": _append_unique(
            _strings(event.get("proof_refs")),
            "generated/read_models/agent_handoff_event_status.json",
            "generated/read_models/worker_package_staging_status.json",
        ),
        "proof_refs_collapsed": True,
    }


def _source_events(read_model_root: Path) -> list[dict[str, Any]]:
    payload = _load_json(_rooted(read_model_root) / "agent_handoff_event_status.json")
    return [dict(item) for item in _list(payload.get("event_history")) if isinstance(item, Mapping)]


def build_status_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(item["ready"] for item in preconditions)
    source_events = _source_events(read_model_root)
    staged_packages = []
    for event in source_events:
        stub = _event_to_package_stub(event)
        if stub is not None:
            staged_packages.append(stub)
    deduped: dict[str, dict[str, Any]] = {}
    for package in staged_packages:
        deduped[str(package["package_id"])] = package
    staged_packages = sorted(deduped.values(), key=lambda item: str(item["package_id"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": STATUS_READY if preconditions_ready else STATUS_NOT_READY,
        "purpose": "Stage worker package stubs from recorded handoff events without running workers.",
        "mode": "local_package_stub_generation_only_no_worker_execution",
        "preconditions": preconditions,
        "source_event_count": len(source_events),
        "staged_package_count": len(staged_packages),
        "staged_packages": staged_packages,
        "staging_policy": {
            "source_status_required": "HANDOFF_EVENT_RECORDED",
            "supported_workers": sorted(SUPPORTED_WORKERS),
            "result_receipt_required": True,
            "review_packet_created_by_staging": False,
            "worker_inherits_speaker_authority": False,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_refs": [
            "generated/read_models/agent_handoff_event_status.json",
            "generated/read_models/spawned_worker_package_lifecycle.json",
            "generated/read_models/workroom_review_packet_index.json",
        ],
        "machine_proof": {
            "local_only": True,
            "read_model_generation_only": True,
            "preconditions_ready": preconditions_ready,
            "worker_package_stub_count": len(staged_packages),
            "review_packet_created": False,
            "source_code_edited_by_staging": False,
            "worker_spawn_performed": False,
            "worker_assignment_performed": False,
            "worker_execution_performed": False,
            "child_agent_run_performed": False,
            "tool_execution_performed": False,
            "external_llm_called": False,
            "local_model_runtime_connected": False,
            "business_action_performed": False,
            "business_state_mutation_performed": False,
            "email_send_performed": False,
            "browser_access_performed": False,
            "gmail_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "git_push_performed": False,
            "unsafe_true_grants_absent": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def build_review_packet_index(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    staging_status: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    root = _rooted(read_model_root)
    existing = _load_json(root / REVIEW_PACKET_INDEX_NAME)
    if not existing:
        existing = {
            "schema_version": "workroom_review_packet_index_v0",
            "read_model_id": "workroom_review_packet_index",
            "status": "WORKROOM_REVIEW_PACKET_INDEX_READY",
            "packets": [],
            "source_refs": [],
            "machine_proof": {},
        }
    updated = json.loads(stable_json(existing))
    staging_status = staging_status or build_status_read_model(read_model_root=read_model_root, generated_at=generated_at)
    staged_packages = [
        dict(item)
        for item in _list(staging_status.get("staged_packages"))
        if isinstance(item, Mapping)
    ]
    staged_package_ids = [str(item.get("package_id") or "") for item in staged_packages if item.get("package_id")]
    machine_proof = dict(updated.get("machine_proof") if isinstance(updated.get("machine_proof"), Mapping) else {})
    machine_proof.update(
        {
            "worker_package_staging_applied": True,
            "worker_package_stub_count": len(staged_packages),
            "no_review_packet_created_from_staging": True,
            "worker_spawn_performed": False,
            "worker_assignment_performed": False,
            "worker_execution_performed": False,
            "tool_execution_performed": False,
            "business_action_performed": False,
            "business_state_mutation_performed": False,
            "git_push_performed": False,
            "unsafe_true_grants_absent": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        }
    )
    source_refs = _append_unique(
        _strings(updated.get("source_refs")),
        "generated/read_models/worker_package_staging_status.json",
    )
    updated.update(
        {
            "generated_at": generated_at,
            "worker_package_staging": {
                "applied": True,
                "status_ref": "generated/read_models/worker_package_staging_status.json",
                "staged_package_ids": staged_package_ids,
                "review_packet_created": False,
                "next_safe_action": "Wait for a worker result receipt before creating a real review packet.",
            },
            "source_refs": source_refs,
            "machine_proof": machine_proof,
        }
    )
    return updated


def build_wiki(status_read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Worker Package Staging",
        "",
        f"Status: `{status_read_model['status']}`",
        "",
        "This surface stages local worker package stubs from recorded handoff events.",
        "",
        f"Staged package count: `{status_read_model['staged_package_count']}`",
        "",
        "## Boundary",
        "",
        "- No worker is spawned or run.",
        "- No child agent or loop is launched.",
        "- No tools execute.",
        "- No source code is edited by this staging step.",
        "- No review packet is created until a worker result receipt exists.",
        "- Worker packages do not inherit speaker authority.",
        "- No send, submit, ledger, workbook, PDF, paid, browser, Gmail, Coupa, live provider, model runtime, or push authority.",
    ]
    return "\n".join(lines) + "\n"


def export_worker_package_staging(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    status = build_status_read_model(read_model_root=read_model_root, generated_at=generated_at)
    index = build_review_packet_index(read_model_root=read_model_root, staging_status=status, generated_at=generated_at)
    export_root = _rooted(export_root)
    status_path = export_root / JSON_EXPORT_NAME
    index_path = export_root / REVIEW_PACKET_INDEX_NAME
    _write_json(status_path, status)
    _write_json(index_path, index)

    bridge_status_path = ""
    bridge_index_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_status = bridge_export_root / JSON_EXPORT_NAME
        bridge_index = bridge_export_root / REVIEW_PACKET_INDEX_NAME
        _write_json(bridge_status, status)
        _write_json(bridge_index, index)
        bridge_status_path = bridge_status.as_posix()
        bridge_index_path = bridge_index.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(status), encoding="utf-8")
    return {
        "status": str(status["status"]),
        "read_model_path": status_path.as_posix(),
        "review_packet_index_path": index_path.as_posix(),
        "bridge_read_model_path": bridge_status_path,
        "bridge_review_packet_index_path": bridge_index_path,
        "wiki_path": wiki_path.as_posix(),
        "staged_package_count": str(status["staged_package_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Worker Package Staging V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_worker_package_staging(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == STATUS_READY else 2


if __name__ == "__main__":
    raise SystemExit(main())
