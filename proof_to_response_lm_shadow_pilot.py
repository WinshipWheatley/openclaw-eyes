"""Proof-to-response LM shadow pilot.

This pilot simulates the future LM response path with fixture/mock text only:
bounded proof bundle -> agent-style draft -> deterministic verifier -> concise
published response or safe fallback. It does not invoke models, providers,
workers, tools, or business executors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import proof_to_response_runtime as runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Proof To Response LM Shadow Pilot.md")

SCHEMA_VERSION = "proof_to_response_lm_shadow_pilot_v0"
READ_MODEL_ID = "proof_to_response_lm_shadow_pilot"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "PROOF_TO_RESPONSE_LM_SHADOW_PILOT_READY"
NOT_READY_STATUS = "PROOF_TO_RESPONSE_LM_SHADOW_PILOT_NOT_READY"

PILOT_SCENARIOS = (
    "finance_capital_hilton_payment_watch",
    "business_development_capital_hilton_followup",
    "finance_live_arts_payment_evidence",
    "build_review_packet",
    "protected_coupa_ledger_email_request",
    "self_heal_missing_proof_for_payment",
)

DOCTRINE = (
    "LM-style text is not truth.",
    "Proof bundles, receipts, gates, hashes, and read models define truth.",
    "The mock LM draft may phrase, prioritize, diagnose, and explain next steps.",
    "The deterministic verifier decides publishability.",
    "Rejected drafts publish safe fallback text, not the unsafe draft.",
    "Dynamic cards remain support/display and details stay collapsed.",
)

AUTHORITY_BOUNDARY = {
    "live_lm_invocation_allowed": False,
    "external_provider_connect_allowed": False,
    "local_model_runtime_allowed": False,
    "worker_spawn_allowed": False,
    "tool_execution_allowed": False,
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
    "authority_grant_allowed": False,
    "protected_actions_allowed": False,
}

PERFORMED_FLAGS = {
    "live_lm_invoked": False,
    "external_provider_connected": False,
    "local_model_runtime_connected": False,
    "worker_spawn_performed": False,
    "tool_execution_performed": False,
    "business_action_performed": False,
    "email_send_performed": False,
    "coupa_submit_performed": False,
    "portal_submit_performed": False,
    "ledger_mutation_performed": False,
    "paid_marking_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "git_push_performed": False,
    "merge_performed": False,
    "incoming_authority_granted_accepted": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | set(PERFORMED_FLAGS) | set(runtime.UNSAFE_TRUE_KEYS) | {
    "paid",
    "sent",
    "submitted",
    "executed",
    "authority_granted",
}

PRECONDITIONS = {
    "proof_to_response_runtime": {
        "filename": "proof_to_response_runtime_status.json",
        "accepted_statuses": ["PROOF_TO_RESPONSE_RUNTIME_READY"],
    },
    "proof_to_response_lm_shadow_harness": {
        "filename": "proof_to_response_lm_shadow_status.json",
        "accepted_statuses": ["PROOF_TO_RESPONSE_LM_SHADOW_HARNESS_READY"],
    },
    "goldilocks_gate_calibration": {
        "filename": "goldilocks_gate_calibration.json",
        "accepted_statuses": ["GOLDILOCKS_GATE_CALIBRATION_READY"],
    },
    "self_heal_repair_doctrine": {
        "filename": "self_heal_repair_doctrine.json",
        "accepted_statuses": ["SELF_HEAL_REPAIR_DOCTRINE_READY"],
    },
    "objective_advancement_controller_route": {
        "filename": "objective_advancement_protocol.json",
        "accepted_statuses": ["OBJECTIVE_ADVANCEMENT_CONTROLLER_ROUTE_READY", "OBJECTIVE_ADVANCEMENT_PROTOCOL_READY"],
    },
}


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


def _observed_status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or payload.get("contract_status") or payload.get("readiness_status") or "")


def _scoped_response_status(read_model_root: Path) -> dict[str, Any]:
    latest = _load_json(_rooted(read_model_root) / runtime.LATEST_JSON_EXPORT_NAME)
    ready = all(
        [
            latest.get("status") == runtime.READY_STATUS,
            bool(latest.get("source_request_id")),
            bool(latest.get("world_ref")),
            bool(latest.get("thread_ref")),
            latest.get("stale_if_context_mismatch") is True,
        ]
    )
    return {
        "precondition_ref": "proof_to_response_scoped_responses",
        "source_ref": f"generated/read_models/{runtime.LATEST_JSON_EXPORT_NAME}",
        "observed_status": READY_STATUS.replace("LM_SHADOW_PILOT", "SCOPED_RESPONSES") if ready else "PROOF_TO_RESPONSE_SCOPED_RESPONSES_NOT_READY",
        "accepted_statuses": ["PROOF_TO_RESPONSE_SCOPED_RESPONSES_READY"],
        "ready": ready,
    }


def _controller_integration_status(read_model_root: Path) -> dict[str, Any]:
    status = _load_json(_rooted(read_model_root) / runtime.STATUS_JSON_EXPORT_NAME)
    ready = (
        status.get("status") == runtime.READY_STATUS
        and status.get("controller_integration_status") == "PROOF_TO_RESPONSE_CONTROLLER_INTEGRATION_ACTIVE"
    )
    return {
        "precondition_ref": "proof_to_response_controller_integration",
        "source_ref": f"generated/read_models/{runtime.STATUS_JSON_EXPORT_NAME}",
        "observed_status": "PROOF_TO_RESPONSE_CONTROLLER_INTEGRATION_READY" if ready else "PROOF_TO_RESPONSE_CONTROLLER_INTEGRATION_NOT_READY",
        "accepted_statuses": ["PROOF_TO_RESPONSE_CONTROLLER_INTEGRATION_READY"],
        "ready": ready,
    }


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, spec in PRECONDITIONS.items():
        filename = str(spec["filename"])
        payload = _load_json(root / filename)
        observed = _observed_status(payload)
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
    rows.append(_controller_integration_status(root))
    rows.append(_scoped_response_status(root))
    return rows


def build_pilot_proof_bundle(
    scenario_id: str,
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
) -> dict[str, Any]:
    if scenario_id not in PILOT_SCENARIOS:
        raise ValueError(f"unknown_pilot_scenario:{scenario_id}")
    return runtime.build_or_load_proof_bundle(scenario_id, read_model_root=read_model_root)


def _candidate_common(proof_bundle: Mapping[str, Any]) -> dict[str, Any]:
    scenario_id = str(proof_bundle.get("scenario_id") or "")
    return {
        "response_id": f"lm_shadow_pilot_candidate:{scenario_id}",
        "proof_bundle_id": str(proof_bundle.get("proof_bundle_id") or ""),
        "speaker_ref": str(proof_bundle.get("response_speaker_ref") or "openclaw"),
        "implied_actions": [],
        "uncertainty_notes": [],
    }


def mock_lm_style_candidate_response(proof_bundle: Mapping[str, Any]) -> dict[str, Any]:
    scenario_id = str(proof_bundle.get("scenario_id") or "")
    common = _candidate_common(proof_bundle)
    if scenario_id == "finance_capital_hilton_payment_watch":
        return {
            **common,
            "draft_headline": "Payment evidence needed",
            "draft_body": "Coupa is processing. I can't mark this paid until payment evidence is attached. The ledger stays untouched.",
            "draft_next_step": "Attach payment evidence.",
            "claimed_facts": ["payment_evidence_missing", "coupa_processing", "ledger_untouched"],
            "requested_controls": ["Attach payment evidence"],
        }
    if scenario_id == "business_development_capital_hilton_followup":
        return {
            **common,
            "draft_headline": "Follow-up can be staged",
            "draft_body": "I can stage a follow-up draft. I will not send it.",
            "draft_next_step": "Stage follow-up",
            "claimed_facts": ["followup_stageable", "no_email_send"],
            "requested_controls": ["Stage follow-up"],
        }
    if scenario_id == "finance_live_arts_payment_evidence":
        return {
            **common,
            "draft_headline": "Evidence recorded",
            "draft_body": "This is candidate payment-processing evidence. It does not mark the invoice paid.",
            "draft_next_step": "Verify arrival or attach stronger proof",
            "claimed_facts": ["candidate_evidence_recorded", "not_paid_truth"],
            "requested_controls": ["Verify arrival or attach stronger proof"],
        }
    if scenario_id == "build_review_packet":
        return {
            **common,
            "draft_headline": "Review packet is informational",
            "draft_body": "This review packet is informational. No merge and no push were performed.",
            "draft_next_step": "Review packet",
            "claimed_facts": ["review_packet_informational", "no_merge_or_push"],
            "requested_controls": ["Review packet"],
        }
    if scenario_id == "protected_coupa_ledger_email_request":
        return {
            **common,
            "draft_headline": "Blocked until proof and approval",
            "draft_body": "Protected finance action is blocked until proof and approval. No execution will happen.",
            "draft_next_step": "Prepare approval",
            "claimed_facts": ["protected_action_blocked", "proof_and_approval_required", "no_execution"],
            "requested_controls": ["Prepare approval"],
        }
    if scenario_id == "self_heal_missing_proof_for_payment":
        return {
            **common,
            "draft_headline": "Payment evidence is missing",
            "draft_body": "Blocker: payment evidence is missing. Proof: payment watch refs do not prove paid state; I can hold the watch, but cannot mark paid or touch the ledger.",
            "draft_next_step": "Attach payment proof",
            "claimed_facts": [
                "repair_blocker_named",
                "repair_proof_cited",
                "can_do_now_named",
                "cannot_do_yet_named",
                "smallest_manual_step_named",
            ],
            "requested_controls": ["Attach payment proof"],
        }
    raise ValueError(f"unknown_pilot_scenario:{scenario_id}")


def _publish_candidate(
    candidate_response: Mapping[str, Any],
    proof_bundle: Mapping[str, Any],
    *,
    generated_at: str,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    verifier_result = runtime.verify_candidate_response(candidate_response, proof_bundle)
    if verifier_result.get("publishable") is True:
        published = runtime._published_response_from_candidate(
            candidate_response,
            proof_bundle,
            generated_at=generated_at,
            verification_status="publishable",
        )
        return dict(verifier_result), published, ""

    fallback = verifier_result.get("safe_fallback_response")
    if not isinstance(fallback, Mapping):
        fallback = runtime._safe_fallback_candidate(
            proof_bundle,
            reason="; ".join(str(error) for error in verifier_result.get("verification_errors") or []),
        )
    fallback_reason = "; ".join(str(error) for error in verifier_result.get("verification_errors") or [])
    published = runtime._published_response_from_candidate(
        fallback,
        proof_bundle,
        generated_at=generated_at,
        verification_status="fallback",
        fallback_reason=fallback_reason,
    )
    return dict(verifier_result), published, fallback_reason


def run_pilot_scenario(
    scenario_id: str,
    candidate_response: Mapping[str, Any] | None = None,
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    proof_bundle = build_pilot_proof_bundle(scenario_id, read_model_root=read_model_root)
    candidate = dict(candidate_response or mock_lm_style_candidate_response(proof_bundle))
    verifier_result, published_response, fallback_reason = _publish_candidate(
        candidate,
        proof_bundle,
        generated_at=generated_at,
    )
    publishable = verifier_result.get("publishable") is True
    run = {
        "scenario_id": scenario_id,
        "agent_voice": {
            "speaker_ref": str(published_response.get("speaker_ref") or proof_bundle.get("response_speaker_ref") or ""),
            "voice_mode": str(published_response.get("voice_mode") or proof_bundle.get("response_voice_mode") or ""),
        },
        "proof_bundle": proof_bundle,
        "candidate_response": candidate,
        "verifier_result": verifier_result,
        "verifier_failure_reasons": list(verifier_result.get("verification_errors") or []),
        "publication_decision": "verified_text_published" if publishable else "safe_fallback_published",
        "published_response": published_response,
        "fallback_reason": fallback_reason,
        "candidate_text_published": publishable,
        "primary_response_kind": "proof_to_response_text",
        "dynamic_card_role": "support_display",
        "dynamic_card_support": {
            "selected_card_ref": str(proof_bundle.get("selected_card_ref") or ""),
            "details_collapsed": True,
            "proof_meters_available": bool(proof_bundle.get("proof_meters")),
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(PERFORMED_FLAGS),
    }
    unsafe = unsafe_true_grants(run)
    run["unsafe_true_grants"] = unsafe
    return run


def build_pilot_runs(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    generated_at = generated_at or utc_now()
    return [
        run_pilot_scenario(scenario_id, read_model_root=read_model_root, generated_at=generated_at)
        for scenario_id in PILOT_SCENARIOS
    ]


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    pilot_runs = build_pilot_runs(read_model_root=read_model_root, generated_at=generated_at)
    all_verified = all(run.get("verifier_result", {}).get("publishable") is True for run in pilot_runs)
    dynamic_support = all(run.get("dynamic_card_role") == "support_display" for run in pilot_runs)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all(row["ready"] for row in preconditions) and all_verified else NOT_READY_STATUS,
        "generated_at": generated_at,
        "doctrine": list(DOCTRINE),
        "pilot_mode": "fixture_mock_lm_style_text_verifier_gated",
        "pilot_scenarios": list(PILOT_SCENARIOS),
        "pilot_run_count": len(pilot_runs),
        "pilot_runs": pilot_runs,
        "dynamic_cards": {
            "role": "support_display",
            "primary_response": "concise_agent_text",
            "details_collapsed": True,
        },
        "preconditions": preconditions,
        "source_refs": [
            "generated/read_models/proof_to_response_runtime_status.json",
            "generated/read_models/proof_to_response_lm_shadow_status.json",
            "generated/read_models/goldilocks_gate_calibration.json",
            "generated/read_models/self_heal_repair_doctrine.json",
            "generated/read_models/objective_advancement_protocol.json",
            "generated/read_models/proof_to_response_latest.json",
        ],
        "source_content_hashes": {
            "pilot_runs": _content_hash(pilot_runs),
            "preconditions": _content_hash(preconditions),
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(PERFORMED_FLAGS),
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"] = {
        "preconditions_ready": all(row["ready"] for row in preconditions),
        "all_pilot_drafts_verified": all_verified,
        "pilot_run_count_matches_required_scenarios": len(pilot_runs) == len(PILOT_SCENARIOS),
        "dynamic_cards_support_not_primary": dynamic_support,
        "candidate_text_is_not_truth": True,
        "verifier_gates_publication": True,
        "details_collapsed": True,
        "unsafe_true_grants": unsafe,
        "unsafe_true_grants_absent": not unsafe,
        **PERFORMED_FLAGS,
    }
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Proof To Response LM Shadow Pilot",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "This pilot simulates the future proof-to-response path with fixture/mock LM-style text only. No model runtime, provider, worker, tool, or business executor is invoked.",
        "",
        "## Doctrine",
        "",
    ]
    for rule in read_model.get("doctrine") or []:
        lines.append(f"- {rule}")
    lines.extend(["", "## Pilot Chain", ""])
    lines.extend(
        [
            "1. Build a bounded proof bundle.",
            "2. Generate an agent-style mock draft.",
            "3. Run deterministic verification.",
            "4. Publish concise text only if verified; otherwise publish safe fallback.",
            "5. Keep dynamic cards as support and details collapsed.",
            "",
            "## Scenarios",
            "",
        ]
    )
    for run in read_model.get("pilot_runs") or []:
        response = run.get("published_response") if isinstance(run.get("published_response"), Mapping) else {}
        verifier = run.get("verifier_result") if isinstance(run.get("verifier_result"), Mapping) else {}
        lines.append(
            f"- `{run.get('scenario_id')}`: {response.get('speaker_ref')} / {response.get('headline')} -> `{verifier.get('status')}`"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No external LM invocation.",
            "- No unapproved local model runtime connection.",
            "- No worker spawn.",
            "- No email, Gmail, browser, Coupa, portal submit, ledger mutation, workbook mutation, PDF export, paid marking, merge, push, or business execution.",
            "",
            "## Proof",
            "",
            f"- Pilot run count: `{read_model.get('pilot_run_count')}`",
            f"- All pilot drafts verified: `{str((read_model.get('machine_proof') or {}).get('all_pilot_drafts_verified')).lower()}`",
            f"- Dynamic cards support only: `{str((read_model.get('machine_proof') or {}).get('dynamic_cards_support_not_primary')).lower()}`",
            f"- Unsafe true grants absent: `{str((read_model.get('machine_proof') or {}).get('unsafe_true_grants_absent')).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_proof_to_response_lm_shadow_pilot(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    _write_json(read_model_path, read_model)

    bridge_read_model_path = ""
    if bridge_export_root is not None:
        bridge_root = _rooted(bridge_export_root)
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
        "pilot_run_count": str(read_model.get("pilot_run_count") or 0),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Proof-to-Response LM Shadow Pilot V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    bridge_root = Path(args.bridge_export_root) if args.bridge_export_root else None
    result = export_proof_to_response_lm_shadow_pilot(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=bridge_root,
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
