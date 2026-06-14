"""Context compaction and preview policy V0.

Defines how OpenClaw should pass scoped, high-signal context to agents without
dumping large logs, raw artifacts, full chat history, or stale context as truth.
This is contract/read-model/wiki work only; it does not invoke models, connect
runtimes, spawn workers, send email, open browser/Gmail/Coupa, mutate ledgers
or workbooks, export PDFs, mark paid, submit, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import context_freshness_decision_trace_gate as freshness_gate
import proof_to_response_runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Context Compaction Preview Policy.md")

SCHEMA_VERSION = "context_compaction_preview_policy_v0"
READ_MODEL_ID = "context_compaction_preview_policy"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "CONTEXT_COMPACTION_PREVIEW_POLICY_READY"
NOT_READY_STATUS = "CONTEXT_COMPACTION_PREVIEW_POLICY_NOT_READY"

CONTEXT_TIER_REFS = (
    "tier_0_operator_request",
    "tier_1_current_lane_summary",
    "tier_2_current_receipts_and_proof_meters",
    "tier_3_decision_trace_summary",
    "tier_4_preview_snippets",
    "tier_5_full_artifact_or_log_reference",
    "tier_6_developer_proof_only",
)

PRECONDITIONS = {
    "proof_bundle_redaction_hardening": {
        "filename": "proof_bundle_redaction_policy.json",
        "accepted_statuses": ("PROOF_BUNDLE_REDACTION_HARDENING_READY",),
    },
    "proof_bundle_freshness_trace_integration": {
        "filename": "proof_bundle_freshness_trace_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY",),
    },
    "context_freshness_decision_trace_gate": {
        "filename": freshness_gate.JSON_EXPORT_NAME,
        "accepted_statuses": (freshness_gate.READY_STATUS,),
    },
    "operator_session_timeline": {
        "filename": "operator_session_timeline.json",
        "accepted_statuses": ("OPERATOR_SESSION_TIMELINE_READY",),
    },
    "universal_receipt_envelope": {
        "filename": "universal_receipt_envelope_status.json",
        "accepted_statuses": ("UNIVERSAL_RECEIPT_ENVELOPE_READY",),
    },
    "agent_response_voice_modes": {
        "filename": "agent_response_voice_modes.json",
        "accepted_statuses": ("AGENT_RESPONSE_VOICE_MODES_READY",),
    },
    "retrospective_harness_learning_seed": {
        "filename": "retrospective_harness_learning_seed.json",
        "accepted_statuses": ("RETROSPECTIVE_HARNESS_LEARNING_SEED_READY",),
    },
}

AUTHORITY_BOUNDARY = {
    "protected_actions_allowed": False,
    "authority_granted": False,
    "authority_grant_allowed": False,
    "model_invocation_allowed": False,
    "worker_spawn_allowed": False,
    "tool_authority_allowed": False,
    "cleanup_authority_granted": False,
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
    "raw_artifact_text_allowed_by_default": False,
    "full_history_dump_allowed": False,
    "stale_context_current_truth_allowed": False,
}

IMPLEMENTATION_BOUNDARY = {
    "model_invoked": False,
    "runtime_connected": False,
    "local_model_runtime_connected": False,
    "external_provider_connected": False,
    "worker_spawn_performed": False,
    "email_send_performed": False,
    "gmail_opened": False,
    "browser_opened": False,
    "coupa_opened": False,
    "portal_submit_performed": False,
    "ledger_mutation_performed": False,
    "paid_marking_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "submit_performed": False,
    "git_push_performed": False,
    "merge_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(freshness_gate.UNSAFE_TRUE_KEYS)
    | set(proof_to_response_runtime.UNSAFE_TRUE_KEYS)
    | {
        "approved",
        "paid",
        "sent",
        "submitted",
        "executed",
        "full_dump_embedded",
        "raw_ocr_embedded",
        "full_chat_history_embedded",
        "stale_context_entered_as_current_truth",
        "private_finance_proof_included",
        "broad_temp_file_delete_authority",
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


def context_tiers() -> list[dict[str, Any]]:
    return [
        {
            "tier_ref": "tier_0_operator_request",
            "rank": 0,
            "purpose": "The current operator request, exact explicit constraints, and latest instruction priority.",
            "agent_visible_by_default": True,
            "full_body_policy": "current_request_only",
        },
        {
            "tier_ref": "tier_1_current_lane_summary",
            "rank": 1,
            "purpose": "Redacted summary of the active world/thread/objective and current known facts.",
            "agent_visible_by_default": True,
            "full_body_policy": "summary_only",
        },
        {
            "tier_ref": "tier_2_current_receipts_and_proof_meters",
            "rank": 2,
            "purpose": "Latest receipt refs, proof meter labels, freshness state, and missing input.",
            "agent_visible_by_default": True,
            "full_body_policy": "refs_and_labels_only",
        },
        {
            "tier_ref": "tier_3_decision_trace_summary",
            "rank": 3,
            "purpose": "Relevant attempted path, why it failed, what proof said, operator decision, and what changed.",
            "agent_visible_by_default": True,
            "full_body_policy": "decision_trace_summary",
        },
        {
            "tier_ref": "tier_4_preview_snippets",
            "rank": 4,
            "purpose": "Short, safe snippets from large logs/artifacts when a preview is needed.",
            "agent_visible_by_default": "when_relevant_and_safe",
            "full_body_policy": "bounded_preview_only",
        },
        {
            "tier_ref": "tier_5_full_artifact_or_log_reference",
            "rank": 5,
            "purpose": "Reference to full artifact/log with hash/path/ref, not embedded content.",
            "agent_visible_by_default": "reference_only",
            "full_body_policy": "never_embed_by_default",
        },
        {
            "tier_ref": "tier_6_developer_proof_only",
            "rank": 6,
            "purpose": "Raw proof, hidden machine contracts, raw logs, and developer-only details.",
            "agent_visible_by_default": False,
            "full_body_policy": "hidden_by_default",
        },
    ]


def preview_rules() -> list[str]:
    return [
        "Large logs, files, and artifacts are not dumped into model context.",
        "Provide a short preview or snippet first.",
        "The full artifact remains referenced, not embedded.",
        "The agent asks or digs only when needed and allowed.",
        "Raw OCR or artifact text is excluded unless explicitly approved.",
    ]


def compaction_rules() -> list[str]:
    return [
        "Old controller responses collapse into decision trace.",
        "Old tool outputs collapse into receipt and proof summaries.",
        "Stale summaries are demoted.",
        "Superseded receipts remain historical, not current truth.",
        "High-signal lessons are preserved.",
        "Low-signal chatter is archived.",
    ]


def agent_visible_context_policy() -> dict[str, Any]:
    return {
        "allowed": [
            "redacted_current_facts",
            "current_proof_meter_labels",
            "latest_receipt_refs",
            "relevant_decision_trace_summary",
            "missing_input",
            "blocked_action_summary",
            "allowed_next_controls",
            "preview_snippets_only_when_safe",
        ],
        "forbidden_by_default": [
            "full_logs",
            "raw_file_bodies",
            "raw_email_coupa_gmail_browser_content",
            "raw_ocr_artifact_text",
            "raw_workbook_ledger_bodies",
            "credentials_secrets",
            "operator_device_session_verification_material",
            "full_chat_history_dumps",
            "stale_context_as_current_truth",
        ],
    }


def required_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "scenario_ref": "large_server_error_log",
            "context_tiers_used": ["tier_4_preview_snippets", "tier_5_full_artifact_or_log_reference"],
            "agent_visible_summary": "Show a short error-window preview plus the log ref/hash.",
            "preview_policy": {
                "preview_first": True,
                "preview_max_lines": 20,
                "full_dump_embedded": False,
                "full_artifact_referenced": True,
                "developer_proof_hidden_by_default": True,
            },
            "forbidden_material_excluded": ["full_logs", "raw_file_bodies", "credentials_secrets"],
            "authority_boundary": {"cleanup_authority_granted": False, "tool_authority_allowed": False},
        },
        {
            "scenario_ref": "local_lm_non_json_postmortem",
            "context_tiers_used": ["tier_2_current_receipts_and_proof_meters", "tier_3_decision_trace_summary"],
            "agent_visible_summary": "Model draft failed JSON shape; fallback receipt published; truth/authority checks were not loosened.",
            "preview_policy": {
                "raw_stdout_embedded": False,
                "raw_stderr_embedded": False,
                "receipt_ref_visible": True,
                "decision_trace_summary_visible": True,
            },
            "forbidden_material_excluded": ["raw_model_dump", "full_prompt_dump", "full_log_body"],
            "authority_boundary": {"model_invocation_allowed": False, "authority_granted": False},
        },
        {
            "scenario_ref": "finance_payment_watch",
            "context_tiers_used": [
                "tier_1_current_lane_summary",
                "tier_2_current_receipts_and_proof_meters",
                "tier_3_decision_trace_summary",
            ],
            "agent_visible_summary": "Payment evidence missing; processor processing; ledger untouched; next safe control is attach proof.",
            "preview_policy": {
                "private_finance_proof_included": False,
                "raw_ledger_rows_embedded": False,
                "current_decision_trace_visible": True,
            },
            "forbidden_material_excluded": ["private_finance_proof", "bank_account_data", "raw_ledger_bodies"],
            "authority_boundary": {"paid_marking_allowed": False, "ledger_mutation_allowed": False},
        },
        {
            "scenario_ref": "build_review_history",
            "context_tiers_used": ["tier_3_decision_trace_summary"],
            "agent_visible_summary": "Resolved or informational Build review packets are historical support, not active ready-for-review context.",
            "preview_policy": {
                "active_context": False,
                "historical_summary_visible": True,
                "stale_context_entered_as_current_truth": False,
            },
            "forbidden_material_excluded": ["stale_context_as_current_truth", "full_chat_history_dumps"],
            "authority_boundary": {"merge_allowed": False, "git_push_allowed": False},
        },
        {
            "scenario_ref": "niles_creative_mapping",
            "context_tiers_used": ["tier_0_operator_request", "tier_1_current_lane_summary"],
            "agent_visible_summary": "Creative goal, controller/software target, and allowed mapping context are visible when supplied.",
            "preview_policy": {
                "creative_context_allowed": True,
                "unrelated_finance_proof_excluded": True,
                "private_finance_proof_included": False,
            },
            "forbidden_material_excluded": ["unrelated_finance_proof", "private_client_proof"],
            "authority_boundary": {"business_action_allowed": False, "authority_granted": False},
        },
        {
            "scenario_ref": "remote_desktop_trace_log_leak",
            "context_tiers_used": ["tier_3_decision_trace_summary", "tier_4_preview_snippets", "tier_6_developer_proof_only"],
            "agent_visible_summary": "Show resource/blocker summary and validation need; keep raw trace logs behind developer proof.",
            "preview_policy": {
                "resource_summary_visible": True,
                "raw_trace_log_embedded": False,
                "broad_temp_file_delete_authority": False,
                "developer_proof_hidden_by_default": True,
            },
            "forbidden_material_excluded": ["raw_trace_logs", "session_material", "broad_cleanup_authority"],
            "authority_boundary": {"cleanup_authority_granted": False, "tool_authority_allowed": False},
        },
    ]


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    tiers = context_tiers()
    scenarios = required_scenarios()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Define how OpenClaw compacts and previews context so agents receive high-signal scoped context instead of noisy dumps.",
        "preconditions": preconditions,
        "context_tiers": tiers,
        "preview_rules": preview_rules(),
        "compaction_rules": compaction_rules(),
        "agent_visible_context_policy": agent_visible_context_policy(),
        "required_scenarios": scenarios,
        "source_refs": [
            "generated/read_models/proof_bundle_redaction_policy.json",
            "generated/read_models/proof_bundle_freshness_trace_status.json",
            "generated/read_models/context_freshness_decision_trace_gate.json",
            "generated/read_models/operator_session_timeline.json",
            "generated/read_models/universal_receipt_envelope_status.json",
            "generated/read_models/agent_response_voice_modes.json",
            "generated/read_models/retrospective_harness_learning_seed.json",
        ],
        "authority_boundary": AUTHORITY_BOUNDARY,
        "implementation_boundary": IMPLEMENTATION_BOUNDARY,
        "machine_proof": {
            "contract_only": True,
            "model_invocation_absent": True,
            "large_artifacts_preview_only": True,
            "raw_ocr_artifact_text_excluded_by_default": True,
            "full_chat_history_excluded": True,
            "developer_proof_hidden_by_default": True,
            "resource_cleanup_authority_absent": True,
            "all_required_tiers_present": {tier["tier_ref"] for tier in tiers} == set(CONTEXT_TIER_REFS),
            "all_required_scenarios_present": len(scenarios) == 6,
            "unsafe_true_grants_absent": True,
        },
        "source_content_hashes": {
            row["precondition_ref"]: _content_hash(_load_json(_rooted(read_model_root) / str(PRECONDITIONS[row["precondition_ref"]]["filename"])))
            for row in preconditions
            if row["precondition_ref"] in PRECONDITIONS
        },
    }
    if not all(row.get("ready") is True for row in preconditions):
        payload["status"] = NOT_READY_STATUS
    unsafe = unsafe_true_grants(payload)
    payload["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    payload["content_hash"] = _content_hash({key: value for key, value in payload.items() if key != "content_hash"})
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Context Compaction Preview Policy",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "This policy keeps agent context scoped and high-signal. Large artifacts, raw logs, raw OCR, full history, and stale context are not dumped into agent context by default.",
        "",
        "## Context Tiers",
        "",
    ]
    for tier in read_model.get("context_tiers") or []:
        lines.append(f"- `{tier['tier_ref']}`: {tier['purpose']}")
    lines.extend(["", "## Preview Rules", ""])
    for rule in read_model.get("preview_rules") or []:
        lines.append(f"- {rule}")
    lines.extend(["", "## Compaction Rules", ""])
    for rule in read_model.get("compaction_rules") or []:
        lines.append(f"- {rule}")
    lines.extend(["", "## Agent-Visible Context", "", "Allowed:"])
    policy = read_model.get("agent_visible_context_policy") or {}
    for item in policy.get("allowed") or []:
        lines.append(f"- `{item}`")
    lines.append("")
    lines.append("Forbidden by default:")
    for item in policy.get("forbidden_by_default") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Required Scenarios", ""])
    for scenario in read_model.get("required_scenarios") or []:
        lines.append(f"- `{scenario['scenario_ref']}`: {scenario['agent_visible_summary']}")
    lines.append("")
    return "\n".join(lines)


def export_context_compaction_preview_policy(
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
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Context Compaction Preview Policy V0.")
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
    result = export_context_compaction_preview_policy(
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
