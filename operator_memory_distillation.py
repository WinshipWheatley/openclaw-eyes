"""Operator Memory Distillation V0.

Distills compact, privacy-safe candidate memories from recent OpenClaw work.
The output is candidate memory only; it does not promote canonical context or
create business truth.
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
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Operator Memory Distillation.md")

SCHEMA_VERSION = "operator_memory_distillation_v0"
READ_MODEL_ID = "operator_memory_distillation"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
STATUS_READY = "OPERATOR_MEMORY_DISTILLATION_READY"
STATUS_NOT_READY = "OPERATOR_MEMORY_DISTILLATION_NOT_READY"

PRECONDITIONS = {
    "operator_conversation_journal": {
        "filename": "operator_conversation_journal.json",
        "accepted_statuses": ["OPERATOR_CONVERSATION_JOURNAL_READY"],
    },
    "package_event_index": {
        "filename": "package_event_index.json",
        "accepted_statuses": ["PACKAGE_EVENT_INDEX_READY"],
    },
    "artifact_lineage_registry": {
        "filename": "artifact_lineage_registry.json",
        "accepted_statuses": ["ARTIFACT_LINEAGE_REGISTRY_READY"],
    },
}

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "business_action_allowed": False,
    "sent": False,
    "paid": False,
}

MEMORY_TEMPLATES = [
    {
        "category": "client_preferences",
        "distilled_summary": "Finance / St. Anne's should use a dedicated thread so work-log intake and month-end invoice questions do not blur together.",
        "privacy_class": "client_ref_only",
        "allowed_usage": "Use as routing guidance for St. Anne's work-log and invoice surfaces.",
        "proof_refs": [
            "generated/read_models/st_annes_work_log_events.json",
            "generated/read_models/package_event_index.json",
        ],
    },
    {
        "category": "workflow_lessons",
        "distilled_summary": "Helm should be action desk, not proof wall; show one current action and keep proof collapsed unless asked.",
        "privacy_class": "operator_workflow_preference",
        "allowed_usage": "Use in Helm surface layout and operator next-decision summaries.",
        "proof_refs": [
            "generated/read_models/helm_action_lifecycle_status.json",
            "generated/read_models/operator_next_decision.json",
        ],
    },
    {
        "category": "provider_failure_modes",
        "distilled_summary": "Capital Hilton Coupa invoice numbers cannot use hyphen; Coupa normalized 2026-1006 into 2026 1006.",
        "privacy_class": "client_ref_only",
        "allowed_usage": "Use as provider warning text before future Coupa-assisted invoice packets.",
        "proof_refs": [
            "generated/read_models/capital_hilton_invoice_operator_run_status.json",
            "generated/read_models/artifact_lineage_registry.json",
        ],
    },
    {
        "category": "voice_taste_preferences",
        "distilled_summary": "Cassandra can lead homecoming-style briefings in plain language, with short Chief/Hermes/Guardian inserts.",
        "privacy_class": "operator_taste_preference",
        "allowed_usage": "Use for briefing tone and speaker routing only.",
        "proof_refs": [
            "generated/read_models/homecoming_brief.json",
            "generated/read_models/agent_voice_profiles.json",
        ],
    },
    {
        "category": "lane_order_preferences",
        "distilled_summary": "When competing safe next moves exist, prefer active unresolved review items, then Capital Hilton payment watch, then workboard review.",
        "privacy_class": "operator_workflow_preference",
        "allowed_usage": "Use for next-decision ranking.",
        "proof_refs": [
            "generated/read_models/operator_next_decision.json",
            "generated/read_models/helm_action_lifecycle_status.json",
        ],
    },
    {
        "category": "payment_followup_facts",
        "distilled_summary": "Capital Hilton is a payment-watch lane after Coupa Processing; ledger remains untouched until payment proof arrives.",
        "privacy_class": "client_ref_only",
        "allowed_usage": "Use as follow-up reminder, not as payment truth.",
        "proof_refs": [
            "generated/read_models/capital_hilton_invoice_operator_run_status.json",
            "generated/read_models/evidence_confidence_scoring.json",
        ],
    },
    {
        "category": "do_not_repeat",
        "distilled_summary": "Mac Excel helper permissions are unstable for St. Anne's; do not rely on helper OPEN_WORKBOOK as the only export path.",
        "privacy_class": "workflow_lesson",
        "allowed_usage": "Use as a caution in future workbook/export planning.",
        "proof_refs": [
            "generated/read_models/artifact_lineage_registry.json",
            "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_full_automation_report_20260601T222036Z.md",
        ],
    },
    {
        "category": "unresolved_questions",
        "distilled_summary": "Proof should be collapsed unless asked; decide later which proof details become operator-visible by default.",
        "privacy_class": "operator_workflow_preference",
        "allowed_usage": "Use as a pending UX question for Helm and Workrooms.",
        "proof_refs": [
            "generated/read_models/operator_human_readability_surface.json",
            "generated/read_models/helm_composer_contract.json",
        ],
    },
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


def _memory_ref(category: str, summary: str) -> str:
    digest = hashlib.sha256(f"{category}:{summary}".encode("utf-8")).hexdigest()[:16]
    return f"memory_candidate:{digest}"


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, contract in PRECONDITIONS.items():
        payload = _load_json(root / str(contract["filename"]))
        observed = str(payload.get("status") or payload.get("contract_status") or "")
        accepted = [str(status) for status in contract["accepted_statuses"]]
        rows.append(
            {
                "precondition_ref": ref,
                "observed_status": observed,
                "accepted_statuses": accepted,
                "ready": observed in accepted,
                "source_ref": f"generated/read_models/{contract['filename']}",
            }
        )
    return rows


def _memory_candidates(generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for template in MEMORY_TEMPLATES:
        summary = str(template["distilled_summary"])
        category = str(template["category"])
        rows.append(
            {
                "memory_ref": _memory_ref(category, summary),
                "category": category,
                "distilled_summary": summary,
                "privacy_class": str(template["privacy_class"]),
                "allowed_usage": str(template["allowed_usage"]),
                "forbidden_usage": [
                    "create_business_truth",
                    "grant_business_authority",
                    "store_raw_prompt_body",
                    "store_secret",
                    "override_receipts",
                ],
                "proof_refs": list(template["proof_refs"]),
                "promotion_status": "candidate",
                "raw_prompt_stored": False,
                "secret_stored": False,
                "business_truth_created": False,
                "created_at": generated_at,
            }
        )
    return rows


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    candidates = _memory_candidates(generated_at)
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": STATUS_READY if preconditions_ready else STATUS_NOT_READY,
        "generated_at": generated_at,
        "memory_candidate_count": len(candidates),
        "memory_categories": [template["category"] for template in MEMORY_TEMPLATES],
        "memory_candidates": candidates,
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "rules": [
            "No raw long prompt dumps.",
            "No secrets.",
            "No client PII beyond approved refs.",
            "Memories cite proof refs.",
            "Distilled memory does not create business truth.",
            "Operator can later approve or promote memory.",
        ],
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "raw_prompt_stored": False,
            "secret_stored": False,
            "business_truth_created": False,
            "business_action_performed": False,
            "email_sent": False,
            "gmail_opened": False,
            "browser_or_coupa_opened": False,
            "ledger_mutated": False,
            "workbook_mutated": False,
            "pdf_exported": False,
            "paid_marked": False,
            "submitted": False,
            "pushed": False,
        },
    }


def _wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Operator Memory Distillation",
        "",
        "Status: " + str(read_model["status"]),
        "",
        "No raw long prompt dumps. These are candidate memories only and require promotion before canonical use.",
        "",
        "## Candidates",
    ]
    for candidate in read_model["memory_candidates"]:
        lines.append(f"- {candidate['category']}: {candidate['distilled_summary']}")
    lines.extend(
        [
            "",
            "No secrets, no business truth, and no authority is created by this distillation.",
            "",
        ]
    )
    return "\n".join(lines)


def export_operator_memory_distillation(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_path = _rooted(export_root) / JSON_EXPORT_NAME
    bridge_path = _rooted(bridge_export_root) / JSON_EXPORT_NAME
    wiki_path = _rooted(wiki_path)
    _write_json(export_path, read_model)
    _write_json(bridge_path, read_model)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model["status"]),
        "read_model_path": str(export_path),
        "bridge_read_model_path": str(bridge_path),
        "wiki_path": str(wiki_path),
        "memory_candidate_count": str(read_model["memory_candidate_count"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Operator Memory Distillation V0.")
    parser.add_argument("--read-model-root", type=Path, default=DEFAULT_READ_MODEL_ROOT)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--bridge-export-root", type=Path, default=DEFAULT_BRIDGE_EXPORT_ROOT)
    parser.add_argument("--wiki-path", type=Path, default=DEFAULT_WIKI_PATH)
    args = parser.parse_args()
    result = export_operator_memory_distillation(
        read_model_root=args.read_model_root,
        export_root=args.export_root,
        bridge_export_root=args.bridge_export_root,
        wiki_path=args.wiki_path,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
