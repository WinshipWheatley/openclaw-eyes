"""Operator Mode Cutover Board V0.

Shows which OpenClaw workflows are ready for operator use, which are
operator-assist, which remain developer-mode, and which are blocked.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Operator Mode Cutover Board.md")

SCHEMA_VERSION = "operator_mode_cutover_board_v0"
READ_MODEL_ID = "operator_mode_cutover_board"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
STATUS_READY = "OPERATOR_MODE_CUTOVER_BOARD_READY"
STATUS_NOT_READY = "OPERATOR_MODE_CUTOVER_BOARD_NOT_READY"

PRECONDITIONS = {
    "lane_graduation_criteria": {
        "filename": "lane_graduation_criteria.json",
        "accepted_statuses": ["LANE_GRADUATION_CRITERIA_READY"],
    },
    "operator_next_decision": {
        "filename": "operator_next_decision.json",
        "accepted_statuses": ["OPERATOR_NEXT_DECISION_READY", "READY"],
    },
    "automation_permission_registry": {
        "filename": "automation_permission_registry.json",
        "accepted_statuses": ["AUTOMATION_PERMISSION_REGISTRY_READY"],
    },
}

CUTOVER_STATUSES = [
    "operator_ready",
    "operator_assist_ready",
    "developer_mode",
    "blocked",
    "retired_manual_only",
]

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


def _workflow(
    *,
    workflow_ref: str,
    display_name: str,
    cutover_status: str,
    owner_speaker_ref: str,
    plain_summary: str,
    next_safe_action: str,
    proof_refs: list[str],
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "workflow_ref": workflow_ref,
        "display_name": display_name,
        "cutover_status": cutover_status,
        "owner_speaker_ref": owner_speaker_ref,
        "plain_summary": plain_summary,
        "next_safe_action": next_safe_action,
        "blockers": blockers or [],
        "business_action_allowed": False,
        "proof_collapsed_by_default": True,
        "proof_refs": proof_refs,
    }


def _workflows() -> list[dict[str, Any]]:
    return [
        _workflow(
            workflow_ref="helm_composer",
            display_name="Helm Composer",
            cutover_status="operator_ready",
            owner_speaker_ref="openclaw",
            plain_summary="Ready for calm question/task entry backed by package queue surfaces.",
            next_safe_action="Use Helm for safe questions and staged operator packages.",
            proof_refs=[
                "generated/read_models/helm_composer_contract.json",
                "generated/read_models/helm_composer_status.json",
            ],
        ),
        _workflow(
            workflow_ref="system_question_answering",
            display_name="System question answering",
            cutover_status="operator_ready",
            owner_speaker_ref="hermes",
            plain_summary="Ready for local-only OpenClaw system questions with speaker-shaped answers.",
            next_safe_action="Ask system questions from Helm or Mission Control.",
            proof_refs=[
                "generated/read_models/system_question_answer_contract.json",
                "generated/read_models/package_event_index.json",
            ],
        ),
        _workflow(
            workflow_ref="st_annes_work_log_intake_review",
            display_name="St. Anne's work-log intake/review",
            cutover_status="operator_ready",
            owner_speaker_ref="cassandra",
            plain_summary="Ready for operator review with confirm, discard, edit, and mark-as-test paths.",
            next_safe_action="Open St. Anne's review when pending items appear.",
            proof_refs=[
                "generated/read_models/st_annes_work_log_events.json",
                "generated/read_models/helm_action_lifecycle_status.json",
            ],
        ),
        _workflow(
            workflow_ref="capital_hilton_invoice",
            display_name="Capital Hilton invoice",
            cutover_status="operator_assist_ready",
            owner_speaker_ref="chief",
            plain_summary="Operator-assisted lane is ready; provider and ledger actions remain gated.",
            next_safe_action="Watch payment proof; do not submit or post ledger unattended.",
            proof_refs=[
                "generated/read_models/capital_hilton_invoice_operator_run_status.json",
                "generated/read_models/lane_graduation_criteria.json",
            ],
        ),
        _workflow(
            workflow_ref="capital_hilton_proposal",
            display_name="Capital Hilton proposal",
            cutover_status="operator_assist_ready",
            owner_speaker_ref="cassandra",
            plain_summary="Business-development proposal is ready for follow-up tracking, with sends gated.",
            next_safe_action="Track client review status without sending new email.",
            proof_refs=[
                "generated/read_models/capital_hilton_business_development_proposal.json",
                "generated/read_models/artifact_lineage_registry.json",
            ],
        ),
        _workflow(
            workflow_ref="st_annes_invoice_generation",
            display_name="St. Anne's invoice generation",
            cutover_status="developer_mode",
            owner_speaker_ref="chief",
            plain_summary="Invoice generation remains developer-mode because workbook/export gates still need hardening.",
            next_safe_action="Keep month-end invoice generation behind explicit approval and developer validation.",
            blockers=["Excel/helper permissions unstable", "PDF/export/send gates remain protected"],
            proof_refs=[
                "generated/read_models/st_annes_invoice_status.json",
                "generated/read_models/lane_graduation_criteria.json",
            ],
        ),
        _workflow(
            workflow_ref="coupa_unattended_submit",
            display_name="Coupa unattended submit",
            cutover_status="blocked",
            owner_speaker_ref="guardian",
            plain_summary="Blocked: Coupa submit is a protected provider action and cannot run unattended.",
            next_safe_action="Use operator-assisted provider gates only.",
            blockers=["Protected provider action", "Operator approval required"],
            proof_refs=[
                "generated/read_models/gate_decision_ledger.json",
                "generated/read_models/approval_request_queue.json",
            ],
        ),
        _workflow(
            workflow_ref="ledger_posting",
            display_name="Ledger posting",
            cutover_status="blocked",
            owner_speaker_ref="guardian",
            plain_summary="Blocked: ledger posting requires separate accounting/payment evidence and approval.",
            next_safe_action="Wait for payment proof and explicit ledger gate.",
            blockers=["Payment proof missing", "Ledger mutation protected"],
            proof_refs=[
                "generated/read_models/gate_decision_ledger.json",
                "generated/read_models/evidence_confidence_scoring.json",
            ],
        ),
        _workflow(
            workflow_ref="excel_source_workbook_mutation",
            display_name="Excel source workbook mutation",
            cutover_status="blocked",
            owner_speaker_ref="guardian",
            plain_summary="Blocked: source workbook mutation is protected and Excel helper permissions are unstable.",
            next_safe_action="Keep workbook mutation behind operator approval and artifact-lineage proof.",
            blockers=["Source-data mutation", "Permission instability"],
            proof_refs=[
                "generated/read_models/approval_request_queue.json",
                "generated/read_models/operator_memory_distillation.json",
            ],
        ),
    ]


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    workflows = _workflows()
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": STATUS_READY if preconditions_ready else STATUS_NOT_READY,
        "generated_at": generated_at,
        "cutover_statuses": list(CUTOVER_STATUSES),
        "workflow_count": len(workflows),
        "workflows": workflows,
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "rules": [
            "Operator-ready means safe local/read-model/package surfaces, not business action authority.",
            "Operator-assist means the operator remains in the loop for protected actions.",
            "Blocked means the board may explain the path but cannot execute it.",
        ],
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
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
        "# Operator Mode Cutover Board",
        "",
        "Status: " + str(read_model["status"]),
        "",
        "This board shows what is ready for operator use, what remains developer-only, and what is blocked.",
        "",
        "## Workflows",
    ]
    for item in read_model["workflows"]:
        lines.append(f"- {item['display_name']}: {item['cutover_status']}")
    lines.extend(["", "Blocked items remain non-executing and Guardian-owned.", ""])
    return "\n".join(lines)


def export_operator_mode_cutover_board(
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
        "workflow_count": str(read_model["workflow_count"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Operator Mode Cutover Board V0.")
    parser.add_argument("--read-model-root", type=Path, default=DEFAULT_READ_MODEL_ROOT)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--bridge-export-root", type=Path, default=DEFAULT_BRIDGE_EXPORT_ROOT)
    parser.add_argument("--wiki-path", type=Path, default=DEFAULT_WIKI_PATH)
    args = parser.parse_args()
    result = export_operator_mode_cutover_board(
        read_model_root=args.read_model_root,
        export_root=args.export_root,
        bridge_export_root=args.bridge_export_root,
        wiki_path=args.wiki_path,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
