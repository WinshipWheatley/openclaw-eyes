"""Lane Graduation Criteria V0.

Defines how OpenClaw lanes graduate from developer mode to operator mode while
keeping unsafe actions gated and manual workarounds explicit.
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
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Lane Graduation Criteria.md")

SCHEMA_VERSION = "lane_graduation_criteria_v0"
READ_MODEL_ID = "lane_graduation_criteria"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
STATUS_READY = "LANE_GRADUATION_CRITERIA_READY"
STATUS_NOT_READY = "LANE_GRADUATION_CRITERIA_NOT_READY"

PRECONDITIONS = {
    "package_event_index": {
        "filename": "package_event_index.json",
        "accepted_statuses": ["PACKAGE_EVENT_INDEX_READY"],
    },
    "canonical_state_map": {
        "filename": "canonical_state_map.json",
        "accepted_statuses": ["CANONICAL_STATE_MAP_READY"],
    },
    "approval_request_queue": {
        "filename": "approval_request_queue.json",
        "accepted_statuses": ["APPROVAL_REQUEST_QUEUE_READY"],
    },
    "evidence_confidence_scoring": {
        "filename": "evidence_confidence_scoring.json",
        "accepted_statuses": ["EVIDENCE_CONFIDENCE_SCORING_READY"],
    },
}

CRITERIA = [
    ("read_model_exists", "A compact read model exists for the lane."),
    ("canonical_truth_source_known", "Canonical truth source is named and scoped."),
    ("package_path_works", "A package/request path exists and has been validated."),
    ("operator_display_exists", "Operator display copy or a human-readable surface exists."),
    ("proof_collapsed", "Proof stays collapsed by default."),
    ("permissions_known", "Required filesystem/provider permissions are known."),
    ("unsafe_actions_gated", "Send, Coupa, ledger, workbook, PDF, paid, and submit actions are gated."),
    ("test_smoke_hygiene_handled", "Smoke/test events are excluded from primary truth."),
    ("stale_surface_sentinel_clean", "Stale status surfaces are either clean or declared."),
    ("review_packet_path_exists_if_worker_needed", "Worker-needed lanes have a review packet path."),
    ("manual_workaround_declared", "Manual workaround is declared if still required."),
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


def _criteria() -> list[dict[str, Any]]:
    return [
        {
            "criterion_ref": ref,
            "description": description,
            "required_for_operator_mode": True,
        }
        for ref, description in CRITERIA
    ]


def _lane(
    *,
    lane_ref: str,
    display_name: str,
    graduation_status: str,
    canonical_truth_source: str,
    readiness_notes: list[str],
    blockers: list[str],
    next_safe_action: str,
    proof_refs: list[str],
) -> dict[str, Any]:
    return {
        "lane_ref": lane_ref,
        "display_name": display_name,
        "graduation_status": graduation_status,
        "canonical_truth_source": canonical_truth_source,
        "readiness_notes": readiness_notes,
        "blockers": blockers,
        "next_safe_action": next_safe_action,
        "business_action_allowed": False,
        "proof_collapsed_by_default": True,
        "unsafe_actions_gated": True,
        "proof_refs": proof_refs,
    }


def _lanes() -> list[dict[str, Any]]:
    return [
        _lane(
            lane_ref="st_annes_work_log_intake",
            display_name="St. Anne's work-log intake/review",
            graduation_status="near_operator_ready",
            canonical_truth_source="generated/read_models/st_annes_work_log_events.json",
            readiness_notes=[
                "Mark-as-test hygiene exists.",
                "Operator review surface exists.",
                "Month-end rollup remains separate.",
            ],
            blockers=[],
            next_safe_action="Use Helm review controls for pending work-log items.",
            proof_refs=[
                "generated/read_models/st_annes_work_log_events.json",
                "generated/read_models/helm_action_lifecycle_status.json",
            ],
        ),
        _lane(
            lane_ref="st_annes_month_end_invoice",
            display_name="St. Anne's month-end invoice",
            graduation_status="developer_mode",
            canonical_truth_source="generated/read_models/st_annes_invoice_status.json",
            readiness_notes=["Manual-send evidence exists; automated invoice generation is not operator-ready."],
            blockers=["Workbook/export helper permissions are unstable.", "PDF/export/send gates remain protected."],
            next_safe_action="Keep month-end invoice generation developer-mode until export and approval gates are stable.",
            proof_refs=[
                "generated/read_models/st_annes_invoice_status.json",
                "generated/read_models/artifact_lineage_registry.json",
            ],
        ),
        _lane(
            lane_ref="capital_hilton_invoice",
            display_name="Capital Hilton invoice",
            graduation_status="operator_assist_ready",
            canonical_truth_source="generated/read_models/capital_hilton_invoice_operator_run_status.json",
            readiness_notes=["Coupa Processing and Annette email evidence are recorded as operator-assisted truth."],
            blockers=["Unattended Coupa submit remains blocked.", "Ledger/payment truth requires separate proof."],
            next_safe_action="Watch for payment proof; do not post ledger.",
            proof_refs=[
                "generated/read_models/capital_hilton_invoice_operator_run_status.json",
                "generated/read_models/evidence_confidence_scoring.json",
            ],
        ),
        _lane(
            lane_ref="capital_hilton_proposal",
            display_name="Capital Hilton proposal",
            graduation_status="operator_assist_ready",
            canonical_truth_source="generated/read_models/capital_hilton_business_development_proposal.json",
            readiness_notes=["Proposal artifact and send receipt are captured for client-review follow-up."],
            blockers=["Follow-up send actions remain approval-gated."],
            next_safe_action="Track Lawrence/client review without sending new email.",
            proof_refs=[
                "generated/read_models/capital_hilton_business_development_proposal.json",
                "generated/read_models/artifact_lineage_registry.json",
            ],
        ),
        _lane(
            lane_ref="live_arts_invoice_pdf_approval",
            display_name="Live Arts invoice PDF approval",
            graduation_status="proven_artifact_path",
            canonical_truth_source="generated/read_models/artifact_lineage_registry.json",
            readiness_notes=["Corrected PDF artifact path is captured as lineage evidence."],
            blockers=["No send or ledger authority is attached."],
            next_safe_action="Use lineage evidence only; request approval for any further client action.",
            proof_refs=[
                "generated/read_models/artifact_lineage_registry.json",
                "generated/wiki/openclaw/Live Arts MD Invoice Automation.md",
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
    lanes = _lanes()
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": STATUS_READY if preconditions_ready else STATUS_NOT_READY,
        "generated_at": generated_at,
        "criteria": _criteria(),
        "lane_count": len(lanes),
        "lanes": lanes,
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "rules": [
            "A lane graduates only when truth source, package path, display, proof policy, permission posture, and gates are known.",
            "Manual workarounds must be declared.",
            "No lane grants business action authority from this registry.",
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
        "# Lane Graduation Criteria",
        "",
        "Status: " + str(read_model["status"]),
        "",
        "This defines what must be true before a lane moves from developer mode to operator mode.",
        "",
        "## Lanes",
    ]
    for lane in read_model["lanes"]:
        lines.append(f"- {lane['display_name']}: {lane['graduation_status']}")
    lines.extend(["", "Unsafe actions remain gated for every lane.", ""])
    return "\n".join(lines)


def export_lane_graduation_criteria(
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
        "lane_count": str(read_model["lane_count"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Lane Graduation Criteria V0.")
    parser.add_argument("--read-model-root", type=Path, default=DEFAULT_READ_MODEL_ROOT)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--bridge-export-root", type=Path, default=DEFAULT_BRIDGE_EXPORT_ROOT)
    parser.add_argument("--wiki-path", type=Path, default=DEFAULT_WIKI_PATH)
    args = parser.parse_args()
    result = export_lane_graduation_criteria(
        read_model_root=args.read_model_root,
        export_root=args.export_root,
        bridge_export_root=args.bridge_export_root,
        wiki_path=args.wiki_path,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
