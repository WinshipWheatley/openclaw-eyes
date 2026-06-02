"""Operator human readability surface V1.

This read-model generator publishes compact operator card copy for Mission
Control. It reads existing local read models only and does not perform business
actions, send messages, touch workbooks, export PDFs, submit portals, mutate
ledgers, or mark paid/sent.
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
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Operator Human Readability Surface.md")

SCHEMA_VERSION = "operator_human_readability_surface_v1"
READ_MODEL_ID = "operator_human_readability_surface"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
CONTRACT_STATUS = "OPERATOR_HUMAN_READABILITY_SURFACE_READY"

ST_ANNES_DISPLAY = "St. Anne\u2019s"

DISPLAY_RULES = {
    "primary_card_max_visible_facts": 3,
    "plain_summary_max_sentences": 1,
    "next_safe_action_max_sentences": 1,
    "proof_collapsed_by_default": True,
    "machine_refs_primary_visible": False,
}

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "workbook_mutation_allowed": False,
    "workbook_source_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
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
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _truth_ref(filename: str) -> str:
    return f"generated/read_models/{filename}"


def _proof_refs_from(payload: Mapping[str, Any], *keys: str) -> list[str]:
    refs: list[str] = []
    proof_refs = payload.get("proof_refs")
    if isinstance(proof_refs, Mapping):
        for key in keys:
            value = proof_refs.get(key)
            if isinstance(value, str) and value:
                refs.append(value)
    artifact_refs = payload.get("artifact_refs")
    if isinstance(artifact_refs, Mapping):
        for value in artifact_refs.values():
            if isinstance(value, Mapping):
                path = value.get("path")
                if isinstance(path, str) and path:
                    refs.append(path)
    return list(dict.fromkeys(refs))


def _thread_card(
    *,
    card_id: str,
    world_ref: str,
    thread_ref: str,
    headline: str,
    summary: str,
    status_label: str,
    next_safe_action: str,
    source_truth_ref: str,
    proof_refs: list[str] | None = None,
    route_note: str = "",
    source_truth: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    compact_fields = {
        "headline": headline,
        "summary": summary,
        "status_label": status_label,
        "next_safe_action": next_safe_action,
    }
    if route_note:
        compact_fields["route_note"] = route_note
    return {
        "card_id": card_id,
        "world_ref": world_ref,
        "thread_ref": thread_ref,
        "primary_visible": True,
        "compact_primary_view": compact_fields,
        "headline": headline,
        "summary": summary,
        "status_label": status_label,
        "next_safe_action": next_safe_action,
        "route_note": route_note,
        "proof_drawer": {
            "collapsed_by_default": True,
            "caption": "Proof available.",
            "source_truth_ref": source_truth_ref,
            "proof_refs": proof_refs or [],
        },
        "machine_refs_primary_visible": False,
        "primary_card_visible_fact_count": len(compact_fields),
        "source_truth_summary": dict(source_truth or {}),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _st_annes_invoice_card(st_annes_invoice: Mapping[str, Any]) -> dict[str, Any]:
    source_truth = {
        "invoice_status": st_annes_invoice.get("invoice_status"),
        "openclaw_send_performed": st_annes_invoice.get("openclaw_send_performed"),
        "paid": st_annes_invoice.get("paid"),
        "ledger_posting_allowed": st_annes_invoice.get("ledger_posting_allowed"),
        "manual_send_out_of_band_known": st_annes_invoice.get("manual_send_out_of_band_known"),
    }
    return _thread_card(
        card_id="finance.st_annes.invoice_may_2026",
        world_ref="finance",
        thread_ref="st_annes",
        headline=f"{ST_ANNES_DISPLAY} invoice sent",
        summary="May invoice was sent manually and recorded.",
        status_label="Sent outside OpenClaw",
        next_safe_action="Watch for payment.",
        source_truth_ref=_truth_ref("st_annes_invoice_status.json"),
        proof_refs=_proof_refs_from(st_annes_invoice, "receipt_ref", "pdf_ref"),
        source_truth=source_truth,
    )


def _capital_hilton_invoice_card(capital_invoice: Mapping[str, Any]) -> dict[str, Any]:
    source_truth = {
        "coupa_submission_recorded": capital_invoice.get("coupa_submission_recorded"),
        "coupa_status_observed": capital_invoice.get("coupa_status_observed"),
        "email_to_annette_recorded": capital_invoice.get("email_to_annette_recorded"),
        "ledger_mutation_performed": capital_invoice.get("ledger_mutation_performed"),
        "paid": capital_invoice.get("paid"),
        "autonomous_openclaw_coupa_submit": capital_invoice.get("autonomous_openclaw_coupa_submit"),
        "autonomous_openclaw_email_send": capital_invoice.get("autonomous_openclaw_email_send"),
    }
    return _thread_card(
        card_id="finance.capital_hilton.invoice_operator_run",
        world_ref="finance",
        thread_ref="capital_hilton",
        headline="Capital Hilton invoice submitted",
        summary="Coupa is processing, and Annette was emailed.",
        status_label="Submitted",
        next_safe_action="Watch Coupa and payment.",
        source_truth_ref=_truth_ref("capital_hilton_invoice_operator_run_status.json"),
        proof_refs=_proof_refs_from(capital_invoice, "receipt_ref", "run_report_ref", "pdf_ref"),
        source_truth=source_truth,
    )


def _capital_hilton_proposal_card(proposal: Mapping[str, Any]) -> dict[str, Any]:
    source_truth = {
        "proposal_status": proposal.get("proposal_status"),
        "proposal_accepted": proposal.get("proposal_accepted"),
        "finance_handoff_allowed": proposal.get("finance_handoff_allowed"),
        "paid": proposal.get("paid"),
        "proposal_sent_recorded": proposal.get("proposal_sent_recorded"),
    }
    return _thread_card(
        card_id="business_development.capital_hilton.fight_weekend_proposal",
        world_ref="business_development",
        thread_ref="capital_hilton",
        headline="Capital Hilton proposal sent",
        summary="Proposal is with Lawrence for review.",
        status_label="Client review",
        next_safe_action="Wait for response.",
        source_truth_ref=_truth_ref("capital_hilton_business_development_proposal.json"),
        proof_refs=_proof_refs_from(proposal, "proposal_send_receipt_ref", "proposal_pdf_ref"),
        source_truth=source_truth,
    )


def _st_annes_work_log_card(work_log: Mapping[str, Any]) -> dict[str, Any]:
    staged_events = work_log.get("staged_events")
    source_truth = {
        "staged_event_count": len(staged_events) if isinstance(staged_events, list) else 0,
        "operator_confirmation_required_before_invoice_inclusion": (
            work_log.get("rules", {}).get("operator_confirmation_required_before_invoice_inclusion")
            if isinstance(work_log.get("rules"), Mapping)
            else None
        ),
        "smoke_or_test_events_not_invoice_included": (
            work_log.get("rules", {}).get("smoke_or_test_events_not_invoice_included")
            if isinstance(work_log.get("rules"), Mapping)
            else None
        ),
    }
    return _thread_card(
        card_id="finance.st_annes.work_log_event_staging",
        world_ref="finance",
        thread_ref="st_annes",
        headline=f"{ST_ANNES_DISPLAY} work log captured",
        summary="Saved as a draft event until you confirm it.",
        status_label="Needs confirmation",
        next_safe_action="Confirm or discard.",
        source_truth_ref=_truth_ref("st_annes_work_log_events.json"),
        proof_refs=[],
        source_truth=source_truth,
    )


def _capital_hilton_provider_gate_card() -> dict[str, Any]:
    return _thread_card(
        card_id="finance.capital_hilton.invoice_provider_gate",
        world_ref="finance",
        thread_ref="capital_hilton",
        headline="Capital Hilton needs operator assist",
        summary="Coupa cannot run unattended.",
        status_label="Provider gate",
        next_safe_action="Stage an operator-assist packet.",
        source_truth_ref=_truth_ref("workflow_package_queue_contract.json"),
        proof_refs=[],
        source_truth={
            "workflow_ref": "capital_hilton_invoice_operator_assist",
            "package_status": "PROVIDER_GATE_REQUIRED",
            "coupa_action_ran": False,
        },
    )


def _stale_surface_overrides(
    *,
    st_annes_invoice: Mapping[str, Any],
    capital_invoice: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> list[dict[str, Any]]:
    overrides: list[dict[str, Any]] = []
    if capital_invoice.get("coupa_submission_recorded") or capital_invoice.get("coupa_submitted"):
        overrides.append(
            {
                "override_id": "capital_hilton_invoice_candidate_after_operator_submission",
                "stale_surface_ref": "legacy.capital_hilton.excel_invoice_candidate_not_confirmed",
                "newer_truth_ref": _truth_ref("capital_hilton_invoice_operator_run_status.json"),
                "condition": "coupa_submission_recorded=true or coupa_submitted=true",
                "action": "secondary_or_hidden",
                "reason": "Capital Hilton invoice was submitted through operator assist; legacy invoice candidate panels must not remain primary.",
                "replacement_card_id": "finance.capital_hilton.invoice_operator_run",
            }
        )
    if proposal.get("proposal_status") == "SENT_FOR_CLIENT_REVIEW":
        overrides.append(
            {
                "override_id": "capital_hilton_proposal_draft_after_send",
                "stale_surface_ref": "business_development.capital_hilton.proposal_draft_unsent",
                "newer_truth_ref": _truth_ref("capital_hilton_business_development_proposal.json"),
                "condition": "proposal_status=SENT_FOR_CLIENT_REVIEW",
                "action": "secondary_or_hidden",
                "reason": "The proposal has been sent for client review; draft-only cards must not look unsent.",
                "replacement_card_id": "business_development.capital_hilton.fight_weekend_proposal",
            }
        )
    if st_annes_invoice.get("invoice_status") == "MANUAL_SEND_OUT_OF_BAND_RECORDED":
        overrides.append(
            {
                "override_id": "st_annes_invoice_draft_after_manual_send",
                "stale_surface_ref": "finance.st_annes.invoice_draft_or_send_needed",
                "newer_truth_ref": _truth_ref("st_annes_invoice_status.json"),
                "condition": "invoice_status=MANUAL_SEND_OUT_OF_BAND_RECORDED",
                "action": "secondary_or_hidden",
                "reason": "St. Anne's May invoice was manually sent and recorded; do not show it as draft or send-needed.",
                "replacement_card_id": "finance.st_annes.invoice_may_2026",
            }
        )
    return overrides


def build_surface_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    read_model_root = _rooted(read_model_root)
    st_annes_invoice = _load_json(read_model_root / "st_annes_invoice_status.json")
    capital_invoice = _load_json(read_model_root / "capital_hilton_invoice_operator_run_status.json")
    proposal = _load_json(read_model_root / "capital_hilton_business_development_proposal.json")
    work_log = _load_json(read_model_root / "st_annes_work_log_events.json")

    thread_cards = [
        _st_annes_invoice_card(st_annes_invoice),
        _capital_hilton_invoice_card(capital_invoice),
        _capital_hilton_proposal_card(proposal),
        _st_annes_work_log_card(work_log),
        _capital_hilton_provider_gate_card(),
    ]
    stale_overrides = _stale_surface_overrides(
        st_annes_invoice=st_annes_invoice,
        capital_invoice=capital_invoice,
        proposal=proposal,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": CONTRACT_STATUS,
        "purpose": "Compact human-readable operator cards for Mission Control, with stale backend surfaces suppressed behind newer business truth.",
        "display_rules": dict(DISPLAY_RULES),
        "thread_cards": thread_cards,
        "helm_briefing": {
            "headline": "Client work is current",
            "summary": "Completed sends and submissions are recorded; follow-ups stay gated.",
            "status_label": "Ready",
            "next_safe_action": "Use compact cards first.",
            "proof_drawer": {
                "collapsed_by_default": True,
                "caption": "Proof available.",
                "source_truth_refs": [
                    _truth_ref("client_work_closeout_2026_06_01.json"),
                    _truth_ref("operator_conversation_journal.json"),
                ],
            },
            "machine_refs_primary_visible": False,
        },
        "stale_surface_overrides": stale_overrides,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "proof_collapsed_by_default": True,
            "machine_refs_primary_visible": False,
            "compact_primary_view_available": True,
            "thread_card_count": len(thread_cards),
            "stale_surface_override_count": len(stale_overrides),
            "authority_flags_all_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "email_send_performed": False,
            "ledger_mutation_performed": False,
            "browser_access_performed": False,
            "gmail_access_performed": False,
            "coupa_access_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "business_state_mutation_performed": False,
            "unsafe_true_grants_absent": True,
        },
    }


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Operator Human Readability Surface",
        "",
        f"Status: `{CONTRACT_STATUS}`",
        "",
        "This surface gives Mission Control compact primary card copy while keeping machine refs and proof behind collapsed details.",
        "",
        "## Display Rules",
        "",
    ]
    for key, value in read_model["display_rules"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Compact Cards", ""])
    for card in read_model["thread_cards"]:
        lines.append(
            f"- {card['headline']}: {card['summary']} Next: {card['next_safe_action']}"
        )
    lines.extend(["", "## Stale Surface Overrides", ""])
    for override in read_model["stale_surface_overrides"]:
        lines.append(
            f"- `{override['stale_surface_ref']}` -> `{override['action']}` because {override['reason']}"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No email, browser, Gmail, Coupa, portal submit, workbook, PDF, ledger, paid, or sent authority is granted.",
            "- This is a display/read-model contract only.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_surface_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_surface_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    local_path = export_root / JSON_EXPORT_NAME
    local_path.write_text(stable_json(read_model), encoding="utf-8")

    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_file = bridge_export_root / JSON_EXPORT_NAME
        bridge_file.write_text(stable_json(read_model), encoding="utf-8")
        bridge_path = bridge_file.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": CONTRACT_STATUS,
        "read_model_path": local_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Operator Human Readability Surface V1.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_surface_read_model(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
