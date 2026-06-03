"""Evidence Confidence Scoring V0.

Scores read-model facts so operator surfaces can distinguish proven receipts,
artifact hashes, generated summaries, inferred/stale/rejected/test-only facts,
and unknown truth that still needs operator evidence.
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
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Evidence Confidence Scoring.md")

SCHEMA_VERSION = "evidence_confidence_scoring_v0"
READ_MODEL_ID = "evidence_confidence_scoring"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
STATUS_READY = "EVIDENCE_CONFIDENCE_SCORING_READY"
STATUS_NOT_READY = "EVIDENCE_CONFIDENCE_SCORING_NOT_READY"

PRECONDITIONS = {
    "canonical_state_map": {
        "filename": "canonical_state_map.json",
        "accepted_statuses": ["CANONICAL_STATE_MAP_READY"],
    },
    "artifact_lineage_registry": {
        "filename": "artifact_lineage_registry.json",
        "accepted_statuses": ["ARTIFACT_LINEAGE_REGISTRY_READY"],
    },
    "package_event_index": {
        "filename": "package_event_index.json",
        "accepted_statuses": ["PACKAGE_EVENT_INDEX_READY"],
    },
}

CONFIDENCE_SCORES = {
    "proven_receipt": 0.95,
    "proven_artifact_hash": 0.9,
    "operator_reported": 0.75,
    "generated_summary": 0.55,
    "inferred": 0.4,
    "stale": 0.2,
    "rejected": 0.0,
    "test_only": 0.1,
    "unknown": 0.0,
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


def _fact(
    *,
    fact_ref: str,
    fact_summary: str,
    confidence_class: str,
    proof_refs: list[str],
    recommended_ui_label: str,
    should_show_primary: bool,
    should_require_operator_review: bool,
) -> dict[str, Any]:
    return {
        "fact_ref": fact_ref,
        "fact_summary": fact_summary,
        "confidence_class": confidence_class,
        "confidence_score": CONFIDENCE_SCORES[confidence_class],
        "proof_refs": proof_refs,
        "recommended_ui_label": recommended_ui_label,
        "should_show_primary": should_show_primary,
        "should_require_operator_review": should_require_operator_review,
    }


def _artifact_by_ref(lineage_payload: Mapping[str, Any], artifact_ref: str) -> dict[str, Any]:
    artifacts = lineage_payload.get("artifacts")
    if not isinstance(artifacts, list):
        return {}
    for artifact in artifacts:
        if isinstance(artifact, Mapping) and artifact.get("artifact_ref") == artifact_ref:
            return dict(artifact)
    return {}


def _facts(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    lineage = _load_json(root / "artifact_lineage_registry.json")
    st_pdf = _artifact_by_ref(lineage, "artifact:st_annes_operator_sent_invoice_pdf")
    st_receipt = _artifact_by_ref(lineage, "artifact:st_annes_manual_send_receipt")
    test_screenshot = next(
        (
            artifact
            for artifact in lineage.get("artifacts", [])
            if isinstance(artifact, Mapping) and artifact.get("lineage_status") == "test_only"
        ),
        {},
    )
    st_pdf_refs = list(st_pdf.get("proof_refs") or ["generated/read_models/st_annes_invoice_status.json"])
    st_receipt_refs = list(st_receipt.get("proof_refs") or ["generated/read_models/st_annes_invoice_status.json"])
    screenshot_refs = list(test_screenshot.get("proof_refs") or ["generated/read_models/workroom_review_packet_index.json"])
    return [
        _fact(
            fact_ref="fact:st_annes_invoice_pdf_hash",
            fact_summary="St. Anne's May invoice PDF has artifact hash evidence.",
            confidence_class="proven_artifact_hash",
            proof_refs=st_pdf_refs,
            recommended_ui_label="Proven artifact hash",
            should_show_primary=True,
            should_require_operator_review=False,
        ),
        _fact(
            fact_ref="fact:st_annes_manual_send_recorded",
            fact_summary="St. Anne's manual send is recorded as out-of-band evidence.",
            confidence_class="proven_receipt",
            proof_refs=st_receipt_refs,
            recommended_ui_label="Receipt-backed manual send",
            should_show_primary=True,
            should_require_operator_review=False,
        ),
        _fact(
            fact_ref="fact:capital_hilton_invoice_processing",
            fact_summary="Capital Hilton invoice was operator-assisted and reported as Coupa Processing.",
            confidence_class="operator_reported",
            proof_refs=[
                "generated/read_models/capital_hilton_invoice_operator_run_status.json",
                "generated/read_models/artifact_lineage_registry.json",
            ],
            recommended_ui_label="Operator-reported provider state",
            should_show_primary=True,
            should_require_operator_review=False,
        ),
        _fact(
            fact_ref="fact:package_event_index_summary",
            fact_summary="Package event index summarizes package/request/response/journal relationships.",
            confidence_class="generated_summary",
            proof_refs=["generated/read_models/package_event_index.json"],
            recommended_ui_label="Generated summary - Cannot override receipts",
            should_show_primary=False,
            should_require_operator_review=False,
        ),
        _fact(
            fact_ref="fact:capital_hilton_payment_watch_inferred",
            fact_summary="Capital Hilton remains on payment watch until payment proof appears.",
            confidence_class="inferred",
            proof_refs=[
                "generated/read_models/capital_hilton_invoice_operator_run_status.json",
                "generated/read_models/client_work_closeout_2026_06_01.json",
            ],
            recommended_ui_label="Inferred from no payment evidence",
            should_show_primary=False,
            should_require_operator_review=True,
        ),
        _fact(
            fact_ref="fact:openclaw_service_status_stale_guard",
            fact_summary="Service status readbacks can become stale and should not override current package receipts.",
            confidence_class="stale",
            proof_refs=["generated/read_models/openclaw_request_response_service_status.json"],
            recommended_ui_label="Stale unless refreshed",
            should_show_primary=False,
            should_require_operator_review=True,
        ),
        _fact(
            fact_ref="fact:unsafe_authority_request_rejected",
            fact_summary="Unsafe authority requests are rejected or routed to Guardian.",
            confidence_class="rejected",
            proof_refs=[
                "generated/read_models/gate_decision_ledger.json",
                "generated/read_models/dead_letter_queue.json",
            ],
            recommended_ui_label="Rejected protected action",
            should_show_primary=False,
            should_require_operator_review=True,
        ),
        _fact(
            fact_ref="fact:workroom_screenshot_fixture",
            fact_summary="Workroom screenshot proof may be fixture/test-only unless the artifact exists.",
            confidence_class="test_only",
            proof_refs=screenshot_refs,
            recommended_ui_label="Test-only evidence",
            should_show_primary=False,
            should_require_operator_review=False,
        ),
        _fact(
            fact_ref="fact:capital_hilton_paid_truth",
            fact_summary="Capital Hilton paid truth is unknown until separate payment evidence exists.",
            confidence_class="unknown",
            proof_refs=[
                "generated/read_models/capital_hilton_invoice_operator_run_status.json",
                "generated/read_models/gate_decision_ledger.json",
            ],
            recommended_ui_label="Needs payment proof",
            should_show_primary=False,
            should_require_operator_review=True,
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
    facts = _facts(read_model_root)
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": STATUS_READY if preconditions_ready else STATUS_NOT_READY,
        "generated_at": generated_at,
        "confidence_classes": list(CONFIDENCE_SCORES),
        "fact_count": len(facts),
        "facts": facts,
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "rules": [
            "Paid truth requires payment evidence.",
            "Send truth requires explicit sent/manual-send evidence.",
            "Test events cannot be primary truth.",
            "Generated summaries cannot override receipts.",
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
        "# Evidence Confidence Scoring",
        "",
        "Status: " + str(read_model["status"]),
        "",
        "paid truth requires payment evidence; sent truth requires explicit sent/manual-send evidence.",
        "",
        "## Classes",
    ]
    for class_ref in read_model["confidence_classes"]:
        lines.append(f"- {class_ref}: {CONFIDENCE_SCORES[class_ref]}")
    lines.extend(
        [
            "",
            "Generated summaries cannot override receipts. Test-only facts stay out of primary UI truth.",
            "",
        ]
    )
    return "\n".join(lines)


def export_evidence_confidence_scoring(
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
        "fact_count": str(read_model["fact_count"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Evidence Confidence Scoring V0.")
    parser.add_argument("--read-model-root", type=Path, default=DEFAULT_READ_MODEL_ROOT)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--bridge-export-root", type=Path, default=DEFAULT_BRIDGE_EXPORT_ROOT)
    parser.add_argument("--wiki-path", type=Path, default=DEFAULT_WIKI_PATH)
    args = parser.parse_args()
    result = export_evidence_confidence_scoring(
        read_model_root=args.read_model_root,
        export_root=args.export_root,
        bridge_export_root=args.bridge_export_root,
        wiki_path=args.wiki_path,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
