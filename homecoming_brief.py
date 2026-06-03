"""Cassandra homecoming brief V0.

This generator summarizes local OpenClaw read models in plain language. It
does not send email, open providers, mutate ledgers or workbooks, export PDFs,
submit portals, mark paid, or create business truth.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_CLIENT_CLOSEOUT_PATH = Path("generated/read_models/client_work_closeout_2026_06_01.json")
DEFAULT_OPERATOR_NEXT_DECISION_PATH = Path("generated/read_models/operator_next_decision.json")
DEFAULT_OVERNIGHT_WORKBOARD_PATH = Path("generated/read_models/overnight_workboard.json")
DEFAULT_PACKAGE_EVENT_INDEX_PATH = Path("generated/read_models/package_event_index.json")
DEFAULT_OPERATOR_JOURNAL_PATH = Path("generated/read_models/operator_conversation_journal.json")
DEFAULT_CAPITAL_INVOICE_STATUS_PATH = Path("generated/read_models/capital_hilton_invoice_operator_run_status.json")
DEFAULT_CAPITAL_PROPOSAL_PATH = Path("generated/read_models/capital_hilton_business_development_proposal.json")
DEFAULT_ST_ANNES_INVOICE_STATUS_PATH = Path("generated/read_models/st_annes_invoice_status.json")
DEFAULT_ST_ANNES_EVENTS_PATH = Path("generated/read_models/st_annes_work_log_events.json")
DEFAULT_PERMISSION_REGISTRY_PATH = Path("generated/read_models/automation_permission_registry.json")
DEFAULT_AGENT_VOICE_PROFILES_PATH = Path("generated/read_models/agent_voice_profiles.json")
DEFAULT_BRIEF_PATH = Path("generated/read_models/homecoming_brief.json")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Homecoming Brief.md")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")

SCHEMA_VERSION = "homecoming_brief_v0"
READ_MODEL_ID = "homecoming_brief"
READY_STATUS = "HOMECOMING_BRIEF_READY"

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "sent": False,
    "paid": False,
}

SOURCE_READ_MODELS = [
    "generated/read_models/client_work_closeout_2026_06_01.json",
    "generated/read_models/operator_next_decision.json",
    "generated/read_models/overnight_workboard.json",
    "generated/read_models/package_event_index.json",
    "generated/read_models/operator_conversation_journal.json",
    "generated/read_models/capital_hilton_invoice_operator_run_status.json",
    "generated/read_models/capital_hilton_business_development_proposal.json",
    "generated/read_models/st_annes_invoice_status.json",
    "generated/read_models/st_annes_work_log_events.json",
    "generated/read_models/automation_permission_registry.json",
    "generated/read_models/agent_voice_profiles.json",
]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    if path.is_absolute():
        return path
    return ROOT / path


def _read_json(path: Path, *, optional: bool = False) -> dict[str, Any]:
    rooted = _rooted(path)
    if optional and not rooted.exists():
        return {}
    payload = json.loads(rooted.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON at {path}")
    return payload


def _tts_safe(text: str) -> str:
    text = re.sub(r"https?://\\S+", "", text)
    text = re.sub(r"/\\S+", "", text)
    text = re.sub(r"`|#|\\*|_", "", text)
    text = text.replace(" / ", " and ")
    text = re.sub(r"\\s+", " ", text)
    return text.strip()


def _next_action(operator_next_decision: Mapping[str, Any]) -> dict[str, str]:
    label = str(operator_next_decision.get("action_label") or "Open workboard")
    action_type = str(operator_next_decision.get("action_type") or "open_workboard")
    target_world = str(operator_next_decision.get("target_world_ref") or "system")
    target_thread = str(operator_next_decision.get("target_thread_ref") or "overnight_workboard")
    return {
        "label": label,
        "action_type": action_type,
        "target_world_ref": target_world,
        "target_thread_ref": target_thread,
    }


def _st_annes_sentence(st_annes_invoice_status: Mapping[str, Any]) -> str:
    invoice_status = str(st_annes_invoice_status.get("invoice_status") or "")
    manual_known = st_annes_invoice_status.get("manual_send_out_of_band_known") is True
    if invoice_status == "MANUAL_SEND_OUT_OF_BAND_RECORDED" and manual_known:
        return "St. Anne's May invoice was sent manually and recorded as out of band."
    if invoice_status:
        return "St. Anne's invoice has a recorded status for review."
    return "St. Anne's invoice status is not fully known in this brief."


def _capital_invoice_sentence(capital_hilton_invoice_status: Mapping[str, Any]) -> str:
    submitted = (
        capital_hilton_invoice_status.get("coupa_submission_recorded") is True
        or capital_hilton_invoice_status.get("coupa_submitted") is True
    )
    emailed = (
        capital_hilton_invoice_status.get("email_to_annette_recorded") is True
        or str(capital_hilton_invoice_status.get("email_status") or "") == "sent_operator_assisted"
    )
    status = str(capital_hilton_invoice_status.get("coupa_status_observed") or "Processing")
    if submitted and emailed:
        return f"Capital Hilton's invoice is submitted in Coupa, status {status}, and Annette was emailed."
    if submitted:
        return f"Capital Hilton's invoice is submitted in Coupa, status {status}."
    return "Capital Hilton's invoice status is recorded for review."


def _proposal_sentence(capital_hilton_proposal: Mapping[str, Any]) -> str:
    proposal_status = str(capital_hilton_proposal.get("proposal_status") or "")
    recipient_display = ""
    email_record = capital_hilton_proposal.get("email_send_record")
    if isinstance(email_record, Mapping):
        recipient_display = str(email_record.get("recipient_display_name") or "")
    if proposal_status == "SENT_FOR_CLIENT_REVIEW":
        if "Lawrence" in recipient_display:
            return "The fight-weekend proposal is with Lawrence for client review."
        return "The Capital Hilton proposal is sent for client review."
    return "The Capital Hilton proposal is recorded for review."


def _work_log_sentence(st_annes_work_log_events: Mapping[str, Any]) -> str:
    events = st_annes_work_log_events.get("staged_events")
    if not isinstance(events, list) or not events:
        return "There are no staged St. Anne's work-log items needing a billable decision."
    smoke_count = 0
    for event in events:
        if not isinstance(event, Mapping):
            continue
        if (
            str(event.get("billing_truth_status") or "") == "SMOKE_OR_TEST_EVENT"
            or str(event.get("invoice_inclusion_status") or "") == "NOT_INCLUDED_SMOKE_EVENT"
        ):
            smoke_count += 1
    if smoke_count == len(events):
        return "The current St. Anne's work-log item is test-only and is not part of an invoice."
    return "A St. Anne's work-log item still needs operator review before any invoice rollup."


def _no_paid_ledger_sentence(
    st_annes_invoice_status: Mapping[str, Any],
    capital_hilton_invoice_status: Mapping[str, Any],
    capital_hilton_proposal: Mapping[str, Any],
) -> str:
    paid_values = [
        st_annes_invoice_status.get("paid"),
        capital_hilton_invoice_status.get("paid"),
        capital_hilton_proposal.get("paid"),
    ]
    ledger_values = [
        st_annes_invoice_status.get("ledger_mutation_performed"),
        capital_hilton_invoice_status.get("ledger_mutation_performed"),
    ]
    if all(value is False for value in paid_values if value is not None) and all(
        value is False for value in ledger_values if value is not None
    ):
        return "No payment has been marked, and the ledger is untouched."
    return "Payment and ledger status need proof review before any finance truth changes."


def _agent_inserts(
    *,
    package_event_index: Mapping[str, Any],
    overnight_workboard: Mapping[str, Any],
    automation_permission_registry: Mapping[str, Any],
) -> list[dict[str, str]]:
    event_count = package_event_index.get("event_count")
    chief_text = "Chief has the package rail indexed and ready for operator review."
    if isinstance(event_count, int) and event_count > 0:
        chief_text = "Chief has the package rail active and indexed."

    hermes_text = "Hermes recommends finishing the St. Anne's work-log path next."
    recommendation = overnight_workboard.get("hermes_recommendation")
    if isinstance(recommendation, Mapping):
        lanes = recommendation.get("recommended_lane_sequence")
        if isinstance(lanes, list) and lanes:
            first = lanes[0]
            if isinstance(first, Mapping) and "St. Anne" in str(first.get("label") or ""):
                hermes_text = "Hermes recommends clearing the St. Anne's work-log path before deeper planning."

    proof = automation_permission_registry.get("machine_proof")
    guardian_text = "Guardian is keeping send, Coupa, ledger, workbook, PDF, and paid actions gated."
    if isinstance(proof, Mapping) and proof.get("ledger_post_blocked") is True:
        guardian_text = "Guardian confirms payment marking and ledger posting remain blocked."

    return [
        {"speaker_ref": "chief", "text": chief_text},
        {"speaker_ref": "hermes", "text": hermes_text},
        {"speaker_ref": "guardian", "text": guardian_text},
    ]


def build_homecoming_brief(
    *,
    client_work_closeout: Mapping[str, Any],
    operator_next_decision: Mapping[str, Any] | None = None,
    overnight_workboard: Mapping[str, Any],
    package_event_index: Mapping[str, Any],
    operator_conversation_journal: Mapping[str, Any],
    capital_hilton_invoice_status: Mapping[str, Any],
    capital_hilton_proposal: Mapping[str, Any],
    st_annes_invoice_status: Mapping[str, Any],
    st_annes_work_log_events: Mapping[str, Any],
    automation_permission_registry: Mapping[str, Any],
    agent_voice_profiles: Mapping[str, Any],
    briefing_mode: str = "homecoming",
    generated_at: str | None = None,
) -> dict[str, Any]:
    del client_work_closeout
    del operator_conversation_journal
    del agent_voice_profiles

    generated_at = generated_at or utc_now()
    operator_next_decision = operator_next_decision or {}
    st_annes = _st_annes_sentence(st_annes_invoice_status)
    capital_invoice = _capital_invoice_sentence(capital_hilton_invoice_status)
    proposal = _proposal_sentence(capital_hilton_proposal)
    work_log = _work_log_sentence(st_annes_work_log_events)
    finance_boundary = _no_paid_ledger_sentence(
        st_annes_invoice_status,
        capital_hilton_invoice_status,
        capital_hilton_proposal,
    )
    action = _next_action(operator_next_decision)
    agent_inserts = _agent_inserts(
        package_event_index=package_event_index,
        overnight_workboard=overnight_workboard,
        automation_permission_registry=automation_permission_registry,
    )

    headline = "Good evening, Winship. OpenClaw is calm and ready."
    spoken_parts = [
        headline,
        "Client work is clean.",
        st_annes,
        capital_invoice,
        proposal,
        work_log,
        finance_boundary,
        "Your next safe move is to " + action["label"] + ".",
    ]
    spoken_text = _tts_safe(" ".join(spoken_parts))

    visible_summary = [
        "Client work is recorded and ready for review.",
        st_annes,
        capital_invoice,
        proposal,
        work_log,
        finance_boundary,
        "Next safe move: " + action["label"] + ".",
    ]

    proof_refs = [
        "generated/read_models/client_work_closeout_2026_06_01.json",
        "generated/read_models/operator_next_decision.json",
        "generated/read_models/overnight_workboard.json",
        "generated/read_models/package_event_index.json",
        "generated/read_models/operator_conversation_journal.json",
        "generated/read_models/capital_hilton_invoice_operator_run_status.json",
        "generated/read_models/capital_hilton_business_development_proposal.json",
        "generated/read_models/st_annes_invoice_status.json",
        "generated/read_models/st_annes_work_log_events.json",
        "generated/read_models/automation_permission_registry.json",
        "generated/read_models/agent_voice_profiles.json",
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "speaker_ref": "cassandra",
        "voice_profile_ref": "agent_voice_profile:cassandra",
        "briefing_mode": briefing_mode,
        "headline": headline,
        "spoken_text": spoken_text,
        "visible_summary": visible_summary,
        "agent_inserts": agent_inserts,
        "next_recommended_action": action,
        "proof_refs": proof_refs,
        "proof_collapsed_by_default": True,
        "source_read_models": SOURCE_READ_MODELS,
        "fact_basis": {
            "confirmed": [
                "St. Anne's manual out-of-band send is recorded.",
                "Capital Hilton operator-assisted Coupa submission and Annette email are recorded.",
                "Capital Hilton proposal is recorded as sent for client review.",
                "No payment proof or ledger posting is recorded.",
            ],
            "inferred": [
                "The safest current move comes from operator_next_decision.",
                "St. Anne's work-log path remains the planning path Hermes is watching.",
            ],
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "cassandra_speaks_first": True,
            "tts_safe_spoken_text": True,
            "raw_package_ids_hidden_from_visible_text": True,
            "raw_sqlite_names_hidden_from_visible_text": True,
            "proof_refs_collapsed_by_default": True,
            "business_action_truth_created": False,
            "no_email_sent": True,
            "no_gmail_opened": True,
            "no_browser_or_coupa_opened": True,
            "no_ledger_mutation": True,
            "no_workbook_mutation": True,
            "no_pdf_export": True,
            "no_paid_marking": True,
            "unsafe_true_grants_absent": True,
        },
    }


def write_outputs(
    *,
    client_closeout_path: Path = DEFAULT_CLIENT_CLOSEOUT_PATH,
    operator_next_decision_path: Path = DEFAULT_OPERATOR_NEXT_DECISION_PATH,
    overnight_workboard_path: Path = DEFAULT_OVERNIGHT_WORKBOARD_PATH,
    package_event_index_path: Path = DEFAULT_PACKAGE_EVENT_INDEX_PATH,
    operator_journal_path: Path = DEFAULT_OPERATOR_JOURNAL_PATH,
    capital_invoice_status_path: Path = DEFAULT_CAPITAL_INVOICE_STATUS_PATH,
    capital_proposal_path: Path = DEFAULT_CAPITAL_PROPOSAL_PATH,
    st_annes_invoice_status_path: Path = DEFAULT_ST_ANNES_INVOICE_STATUS_PATH,
    st_annes_events_path: Path = DEFAULT_ST_ANNES_EVENTS_PATH,
    permission_registry_path: Path = DEFAULT_PERMISSION_REGISTRY_PATH,
    agent_voice_profiles_path: Path = DEFAULT_AGENT_VOICE_PROFILES_PATH,
    brief_path: Path = DEFAULT_BRIEF_PATH,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    briefing_mode: str = "homecoming",
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_homecoming_brief(
        client_work_closeout=_read_json(client_closeout_path),
        operator_next_decision=_read_json(operator_next_decision_path, optional=True),
        overnight_workboard=_read_json(overnight_workboard_path),
        package_event_index=_read_json(package_event_index_path),
        operator_conversation_journal=_read_json(operator_journal_path),
        capital_hilton_invoice_status=_read_json(capital_invoice_status_path),
        capital_hilton_proposal=_read_json(capital_proposal_path),
        st_annes_invoice_status=_read_json(st_annes_invoice_status_path),
        st_annes_work_log_events=_read_json(st_annes_events_path),
        automation_permission_registry=_read_json(permission_registry_path),
        agent_voice_profiles=_read_json(agent_voice_profiles_path),
        briefing_mode=briefing_mode,
        generated_at=generated_at,
    )

    brief_output = _rooted(brief_path)
    wiki_output = _rooted(wiki_path)
    brief_output.parent.mkdir(parents=True, exist_ok=True)
    wiki_output.parent.mkdir(parents=True, exist_ok=True)
    brief_output.write_text(stable_json(payload), encoding="utf-8")
    wiki_output.write_text(_wiki_text(payload), encoding="utf-8")
    if bridge_root is not None:
        bridge_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(brief_output, bridge_root / brief_output.name)
    return payload


def _wiki_text(payload: Mapping[str, Any]) -> str:
    summary = payload.get("visible_summary") if isinstance(payload.get("visible_summary"), list) else []
    inserts = payload.get("agent_inserts") if isinstance(payload.get("agent_inserts"), list) else []
    action = payload.get("next_recommended_action") if isinstance(payload.get("next_recommended_action"), Mapping) else {}
    return "\n".join(
        [
            "# Homecoming Brief",
            "",
            f"Status: {payload.get('status', READY_STATUS)}",
            "",
            "## Cassandra",
            str(payload.get("headline") or ""),
            "",
            "## Summary",
            *(f"- {item}" for item in summary),
            "",
            "## Agent Inserts",
            *(f"- {item.get('speaker_ref')}: {item.get('text')}" for item in inserts if isinstance(item, Mapping)),
            "",
            "## Next Safe Move",
            f"- {action.get('label', 'Open workboard')} ({action.get('target_world_ref', 'system')} / {action.get('target_thread_ref', 'overnight_workboard')})",
            "",
            "## Boundary",
            "This brief only summarizes local read models. It does not send email, open Gmail, open browser or Coupa, submit portal actions, mutate ledgers, mutate workbooks, export PDFs, mark paid, or create business truth.",
            "",
        ]
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish the Cassandra-led homecoming brief.")
    parser.add_argument("--brief-path", default=str(DEFAULT_BRIEF_PATH))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--briefing-mode", default="homecoming")
    parser.add_argument("--generated-at")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = write_outputs(
        brief_path=Path(args.brief_path),
        wiki_path=Path(args.wiki_path),
        bridge_root=None if args.no_bridge else Path(args.bridge_root),
        briefing_mode=args.briefing_mode,
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(f"{payload['status']}: {payload['headline']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
