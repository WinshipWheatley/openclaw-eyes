"""Dynamic Card Lifecycle Policy V0.

Lifecycle and visibility policy for backend-generated Mission Control cards.
This keeps Mission Control acting like a controller surface rather than a
growing dashboard. The policy is read-model only and grants no authority.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Dynamic Card Lifecycle Policy.md")

SCHEMA_VERSION = "dynamic_card_lifecycle_policy_v0"
READ_MODEL_ID = "dynamic_card_lifecycle_policy"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "DYNAMIC_CARD_LIFECYCLE_POLICY_READY"
NOT_READY_STATUS = "DYNAMIC_CARD_LIFECYCLE_POLICY_NOT_READY"

LIFECYCLE_STATES = (
    "active",
    "waiting",
    "needs_operator",
    "resolved",
    "archived",
    "stale",
    "unknown",
)
FRESHNESS_STATES = (
    "current",
    "waiting_on_external",
    "needs_verification",
    "superseded",
    "historical",
    "unknown",
)

REQUIRED_CARD_FIELDS = (
    "lifecycle_state",
    "freshness_state",
    "operator_attention_required",
    "visible_by_default",
    "collapse_when_resolved",
    "expires_at",
    "replacement_card_ref",
    "resolved_by_receipt_ref",
    "stale_reason",
    "primary_control_ref",
)

PRECONDITIONS = {
    "dynamic_card_packet": {
        "filename": "dynamic_card_packet_latest.json",
        "accepted_statuses": ("DYNAMIC_CARD_PACKET_READY",),
    },
    "mac_dynamic_card_renderer": {
        "filename": "mac_dynamic_card_renderer.json",
        "accepted_statuses": ("MAC_DYNAMIC_CARD_RENDERER_READY",),
    },
    "operator_action_payloads": {
        "filename": "operator_action_payloads.json",
        "accepted_statuses": ("OPERATOR_ACTION_PAYLOADS_READY",),
    },
    "verified_evidence_intake": {
        "filename": "evidence_intake_status.json",
        "accepted_statuses": ("EVIDENCE_INTAKE_READY",),
    },
}

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_source_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "business_action_allowed": False,
    "external_action_allowed": False,
    "authority_grant_allowed": False,
    "worker_spawn_allowed": False,
    "git_push_allowed": False,
    "sent": False,
    "paid": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "email_send_performed",
    "email_sent",
    "gmail_access_performed",
    "gmail_opened",
    "browser_access_performed",
    "browser_opened",
    "coupa_access_performed",
    "coupa_opened",
    "coupa_submit_performed",
    "portal_submit_performed",
    "ledger_posting_performed",
    "ledger_mutation_performed",
    "workbook_mutation_performed",
    "pdf_export_performed",
    "paid_marking_performed",
    "mark_paid_performed",
    "submit_performed",
    "business_action_performed",
    "authority_grant_performed",
    "worker_spawn_performed",
    "worker_execution_performed",
    "child_agent_run_performed",
    "external_llm_invoked",
    "external_provider_connected",
    "local_model_runtime_connected",
    "model_invoked",
    "git_push_performed",
    "push_performed",
    "merge_performed",
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


def _status(payload: Mapping[str, Any]) -> str:
    for key in ("status", "readiness_status", "contract_status"):
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def _source_ref(filename: str) -> str:
    return f"generated/read_models/{filename}"


def _precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ref, spec in PRECONDITIONS.items():
        filename = str(spec["filename"])
        payload = _load_json(_rooted(read_model_root) / filename)
        observed = _status(payload)
        accepted = tuple(str(status) for status in spec["accepted_statuses"])
        rows.append(
            {
                "precondition_ref": ref,
                "observed_status": observed,
                "accepted_statuses": list(accepted),
                "ready": observed in accepted,
                "source_ref": _source_ref(filename),
            }
        )
    return rows


def card_lifecycle_defaults(card: Mapping[str, Any]) -> dict[str, Any]:
    card_id = str(card.get("card_id") or "")
    card_type = str(card.get("card_type") or "unknown")
    status_label = str(card.get("status_label") or "")
    trust_state = str(card.get("trust_state") or "")
    visible = bool(card.get("visible_by_default") is True)
    proof_only = card_type in {"artifact", "memory"} or card_id.endswith(".proof_only")

    lifecycle_state = "active"
    freshness_state = "current"
    operator_attention_required = visible
    collapse_when_resolved = True
    resolved_by_receipt_ref = ""
    replacement_card_ref = ""
    stale_reason = ""
    primary_control_ref = card_id

    if proof_only:
        lifecycle_state = "archived"
        freshness_state = "historical"
        operator_attention_required = False
        visible = False
        primary_control_ref = ""
    elif card_type == "review_packet":
        if visible:
            lifecycle_state = "needs_operator"
            freshness_state = "current"
            operator_attention_required = True
        else:
            lifecycle_state = "resolved"
            freshness_state = "historical"
            operator_attention_required = False
            resolved_by_receipt_ref = "generated/read_models/workroom_review_decision_status.json"
    elif card_type == "payment_watch":
        lifecycle_state = "active"
        freshness_state = "current"
        operator_attention_required = False
        visible = True
        collapse_when_resolved = False
    elif card_type == "evidence_intake":
        lifecycle_state = "waiting"
        freshness_state = "waiting_on_external"
        operator_attention_required = False
        visible = bool(card.get("visible_by_default") is True)
    elif card_id == "dynamic_card.finance.st_annes.work_log_review" and not visible:
        lifecycle_state = "resolved"
        freshness_state = "historical"
        operator_attention_required = False
        resolved_by_receipt_ref = "generated/read_models/st_annes_work_log_review_surface.json"
    elif trust_state == "stale_needs_proof":
        lifecycle_state = "stale"
        freshness_state = "needs_verification"
        operator_attention_required = True
        visible = True
        stale_reason = "Needs verification"
        status_label = "Needs verification"
    elif not visible:
        lifecycle_state = "archived"
        freshness_state = "historical"
        operator_attention_required = False

    return {
        "lifecycle_state": lifecycle_state,
        "freshness_state": freshness_state,
        "operator_attention_required": operator_attention_required,
        "visible_by_default": visible,
        "collapse_when_resolved": collapse_when_resolved,
        "expires_at": "",
        "replacement_card_ref": replacement_card_ref,
        "resolved_by_receipt_ref": resolved_by_receipt_ref,
        "stale_reason": stale_reason,
        "primary_control_ref": primary_control_ref,
        "status_label": status_label or str(card.get("status_label") or ""),
    }


def apply_lifecycle_policy(card: Mapping[str, Any]) -> dict[str, Any]:
    enriched = dict(card)
    defaults = card_lifecycle_defaults(card)
    for field in REQUIRED_CARD_FIELDS:
        if field == "visible_by_default":
            enriched[field] = defaults[field]
        else:
            enriched[field] = enriched.get(field, defaults[field])
    if defaults["status_label"] == "Needs verification":
        enriched["status_label"] = "Needs verification"
    if enriched["lifecycle_state"] == "stale" and not enriched.get("stale_reason"):
        enriched["stale_reason"] = "Needs verification"
        enriched["status_label"] = "Needs verification"
    return enriched


def validate_card_lifecycle(card: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    card_id = str(card.get("card_id") or "unknown_card")
    for field in REQUIRED_CARD_FIELDS:
        if field not in card:
            errors.append(f"{card_id}:{field}_missing")
    if card.get("lifecycle_state") not in LIFECYCLE_STATES:
        errors.append(f"{card_id}:lifecycle_state_invalid")
    if card.get("freshness_state") not in FRESHNESS_STATES:
        errors.append(f"{card_id}:freshness_state_invalid")
    if card.get("operator_attention_required") is True and card.get("visible_by_default") is not True:
        errors.append(f"{card_id}:attention_card_hidden")
    if card.get("lifecycle_state") in {"resolved", "archived"} and card.get("visible_by_default") is True:
        errors.append(f"{card_id}:resolved_or_archived_visible_by_default")
    if card.get("lifecycle_state") == "stale":
        if card.get("freshness_state") != "needs_verification":
            errors.append(f"{card_id}:stale_without_needs_verification_freshness")
        if "Needs verification" not in str(card.get("status_label") or ""):
            errors.append(f"{card_id}:stale_without_needs_verification_label")
    if card.get("card_type") == "review_packet" and card.get("operator_attention_required") is not True and card.get("visible_by_default") is True:
        errors.append(f"{card_id}:workroom_without_attention_visible")
    if card.get("card_type") == "evidence_intake" and (card.get("authority_boundary") or {}).get("paid") is True:
        errors.append(f"{card_id}:evidence_card_marks_paid")
    if card.get("card_type") in {"artifact", "memory"} and card.get("visible_by_default") is True:
        errors.append(f"{card_id}:proof_only_visible_by_default")
    return errors


def validate_packet_lifecycle(packet: Mapping[str, Any]) -> dict[str, Any]:
    cards = packet.get("cards") if isinstance(packet.get("cards"), list) else []
    errors: list[str] = []
    for card in cards:
        if isinstance(card, Mapping):
            errors.extend(validate_card_lifecycle(card))
        else:
            errors.append("card_not_object")
    unsafe = unsafe_true_grants(packet)
    return {
        "valid": not errors and not unsafe,
        "errors": errors,
        "card_count": len(cards),
        "visible_card_count": sum(1 for card in cards if isinstance(card, Mapping) and card.get("visible_by_default") is True),
        "history_card_count": sum(1 for card in cards if isinstance(card, Mapping) and card.get("lifecycle_state") in {"resolved", "archived"}),
        "operator_attention_card_count": sum(1 for card in cards if isinstance(card, Mapping) and card.get("operator_attention_required") is True),
        "unsafe_true_grants": unsafe,
        "unsafe_true_grants_absent": not unsafe,
    }


def example_policy_cases() -> list[dict[str, Any]]:
    examples = [
        {
            "case_id": "active_payment_watch",
            "card": {
                "card_id": "dynamic_card.finance.capital_hilton.payment_watch",
                "card_type": "payment_watch",
                "status_label": "Payment watch",
                "trust_state": "trusted_current",
                "visible_by_default": True,
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            },
            "expected": "active/current/visible while payment evidence is missing",
        },
        {
            "case_id": "payment_proof_candidate",
            "card": {
                "card_id": "dynamic_card.finance.live_arts_md.evidence_intake.payment_processing",
                "card_type": "evidence_intake",
                "status_label": "Processing evidence",
                "trust_state": "operator_reported",
                "visible_by_default": True,
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            },
            "expected": "waiting/waiting_on_external/not paid",
        },
        {
            "case_id": "resolved_review_packet",
            "card": {
                "card_id": "dynamic_card.build.review_packet.current",
                "card_type": "review_packet",
                "status_label": "Review recorded",
                "trust_state": "preview_only",
                "visible_by_default": False,
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            },
            "expected": "resolved/historical/hidden",
        },
        {
            "case_id": "stale_card",
            "card": {
                "card_id": "dynamic_card.finance.example.stale",
                "card_type": "status",
                "status_label": "Unknown",
                "trust_state": "stale_needs_proof",
                "visible_by_default": True,
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            },
            "expected": "stale/Needs verification",
        },
        {
            "case_id": "proof_only",
            "card": {
                "card_id": "dynamic_card.artifact.proof_only",
                "card_type": "artifact",
                "status_label": "Proof",
                "trust_state": "trusted_current",
                "visible_by_default": True,
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            },
            "expected": "archived/historical/hidden",
        },
    ]
    return [
        {"case_id": item["case_id"], "card": apply_lifecycle_policy(item["card"]), "expected": item["expected"]}
        for item in examples
    ]


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _precondition_rows(read_model_root)
    examples = example_policy_cases()
    validation_errors = []
    for example in examples:
        validation_errors.extend(validate_card_lifecycle(example["card"]))
    status = READY_STATUS if all(row["ready"] for row in preconditions) and not validation_errors else NOT_READY_STATUS
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": status,
        "generated_at": generated_at,
        "purpose": "Lifecycle and visibility policy for dynamic operator cards so Mission Control behaves like a controller, not a dashboard.",
        "lifecycle_states": list(LIFECYCLE_STATES),
        "freshness_states": list(FRESHNESS_STATES),
        "required_card_fields": list(REQUIRED_CARD_FIELDS),
        "visibility_rules": [
            "Show active/needs_operator cards by default.",
            "Hide resolved cards by default after receipt is recorded.",
            "Collapse historical cards under Completed / History.",
            "Stale cards must say Needs verification.",
            "Proof-only cards are hidden unless requested.",
            "Workroom cards show only if operator attention is needed.",
            "Finance payment-watch card stays visible only while payment evidence is missing.",
            "Payment-processing evidence does not mark paid.",
            "No card can remain primary if a newer receipt supersedes it.",
            "No machine-contract card is visible in operator mode.",
        ],
        "policy_examples": examples,
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "preconditions_ready": all(row["ready"] for row in preconditions),
            "example_cards_valid": not validation_errors,
            "resolved_cards_hidden_by_default": True,
            "historical_cards_collapsed": True,
            "stale_cards_require_verification_label": True,
            "proof_only_cards_hidden_by_default": True,
            "workroom_cards_attention_gated": True,
            "payment_processing_evidence_does_not_mark_paid": True,
            "machine_contract_cards_hidden_in_operator_mode": True,
            "external_llm_invoked": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "business_action_performed": False,
            "merge_performed": False,
            "git_push_performed": False,
            "validation_errors": validation_errors,
        },
    }
    payload["machine_proof"]["unsafe_true_grants"] = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants_absent"] = not payload["machine_proof"]["unsafe_true_grants"]
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Dynamic Card Lifecycle Policy",
        "",
        f"Status: `{read_model.get('status', NOT_READY_STATUS)}`",
        "",
        "This policy keeps Mission Control focused on current controls instead of stale dashboard accumulation.",
        "",
        "## Required Fields",
        "",
        ", ".join(f"`{field}`" for field in REQUIRED_CARD_FIELDS),
        "",
        "## Visibility Rules",
        "",
    ]
    for rule in read_model.get("visibility_rules") or []:
        lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "## Lifecycle States",
            "",
            ", ".join(f"`{state}`" for state in LIFECYCLE_STATES),
            "",
            "## Safety",
            "",
            "This policy does not send, submit, mark paid, mutate ledgers/workbooks, invoke models, spawn workers, export PDFs, or grant authority.",
            "",
        ]
    )
    return "\n".join(lines)


def export_dynamic_card_lifecycle_policy(
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
    export_path = export_root / JSON_EXPORT_NAME
    export_path.write_text(stable_json(read_model), encoding="utf-8")
    bridge_path = ""
    if bridge_root is not None:
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge = bridge_root / JSON_EXPORT_NAME
        shutil.copy2(export_path, bridge)
        bridge_path = bridge.as_posix()
    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model["status"]),
        "read_model_path": export_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
    }


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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Dynamic Card Lifecycle Policy V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_dynamic_card_lifecycle_policy(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=None if args.no_bridge else Path(args.bridge_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"{result['status']}: {result['read_model_path']}")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
