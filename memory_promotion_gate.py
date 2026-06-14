"""Memory Promotion Gate V0.

Creates a promotion gate for distilled operator memories. It never promotes
memories automatically and does not create canonical context or business truth.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import dynamic_card_packet


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Memory Promotion Gate.md")

SCHEMA_VERSION = "memory_promotion_gate_v0"
READ_MODEL_ID = "memory_promotion_gate"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
STATUS_READY = "MEMORY_PROMOTION_GATE_READY"
STATUS_NOT_READY = "MEMORY_PROMOTION_GATE_NOT_READY"

PRECONDITIONS = {
    "operator_memory_distillation": {
        "filename": "operator_memory_distillation.json",
        "accepted_statuses": ["OPERATOR_MEMORY_DISTILLATION_READY"],
    },
    "gate_decision_ledger": {
        "filename": "gate_decision_ledger.json",
        "accepted_statuses": ["GATE_DECISION_LEDGER_READY"],
    },
}

MEMORY_STATES = [
    "candidate",
    "operator_approved",
    "rejected",
    "stale",
    "needs_more_proof",
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


def _operator_approval_required(privacy_class: str, category: str) -> bool:
    if privacy_class in {"client_ref_only", "sensitive_client_fact"}:
        return True
    if category in {"payment_followup_facts", "provider_failure_modes"}:
        return True
    return False


def _promotion_entries(read_model_root: Path, generated_at: str) -> list[dict[str, Any]]:
    payload = _load_json(read_model_root / "operator_memory_distillation.json")
    candidates = payload.get("memory_candidates")
    if not isinstance(candidates, list):
        return []
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        category = str(candidate.get("category") or "")
        privacy_class = str(candidate.get("privacy_class") or "unknown")
        rows.append(
            {
                "memory_ref": str(candidate.get("memory_ref") or ""),
                "candidate_summary": str(candidate.get("distilled_summary") or ""),
                "proof_refs": list(candidate.get("proof_refs") or []),
                "privacy_class": privacy_class,
                "promotion_status": "candidate",
                "allowed_usage": str(candidate.get("allowed_usage") or ""),
                "forbidden_usage": [
                    "canonical_use_without_operator_approval",
                    "store_raw_prompt_body",
                    "store_secret",
                    "create_business_truth",
                    "grant_business_authority",
                ],
                "operator_approval_required": _operator_approval_required(privacy_class, category),
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
    entries = _promotion_entries(_rooted(read_model_root), generated_at)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": STATUS_READY if preconditions_ready else STATUS_NOT_READY,
        "generated_at": generated_at,
        "memory_states": list(MEMORY_STATES),
        "promotion_entry_count": len(entries),
        "promotion_entries": entries,
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "rules": [
            "No automatic promotion.",
            "Sensitive/client facts require operator approval.",
            "Taste and workflow preferences may be promoted with lower risk, but still remain candidates here.",
            "No raw prompt bodies.",
            "No secrets.",
            "No business action truth.",
        ],
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "automatic_promotion_performed": False,
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
    return dynamic_card_packet.add_rail_card_packet(
        payload,
        "memory_promotion_gate",
        read_model_root=read_model_root,
        generated_at=generated_at,
    )


def _wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Memory Promotion Gate",
        "",
        "Status: " + str(read_model["status"]),
        "",
        "No automatic promotion. Distilled memories remain candidates until an operator-approved promotion path records otherwise.",
        "",
        "## Entries",
    ]
    for entry in read_model["promotion_entries"]:
        lines.append(
            f"- {entry['memory_ref']}: {entry['promotion_status']} - approval required: {str(entry['operator_approval_required']).lower()}"
        )
    lines.extend(["", "No raw prompts, secrets, or business truth are created here.", ""])
    return "\n".join(lines)


def export_memory_promotion_gate(
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
        "promotion_entry_count": str(read_model["promotion_entry_count"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Memory Promotion Gate V0.")
    parser.add_argument("--read-model-root", type=Path, default=DEFAULT_READ_MODEL_ROOT)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--bridge-export-root", type=Path, default=DEFAULT_BRIDGE_EXPORT_ROOT)
    parser.add_argument("--wiki-path", type=Path, default=DEFAULT_WIKI_PATH)
    args = parser.parse_args()
    result = export_memory_promotion_gate(
        read_model_root=args.read_model_root,
        export_root=args.export_root,
        bridge_export_root=args.bridge_export_root,
        wiki_path=args.wiki_path,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
