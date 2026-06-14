"""Proof-to-response model quality comparison V0.

Compares recorded local, synthetic external, and shadow/mock proof-to-response
outputs. This module only reads local read models and writes generated
comparison artifacts; it does not invoke models, call APIs, browse, send
prompts or proof bundles, mutate business systems, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import external_lm_synthetic_response_capture as external_capture
import external_lm_synthetic_test_packet as synthetic_packet
import proof_to_response_schema_adapter as schema_adapter
import proof_to_response_verifier as verifier


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Proof To Response Model Quality Comparison.md")

SCHEMA_VERSION = "proof_to_response_model_quality_comparison_v0"
READ_MODEL_ID = "proof_to_response_model_quality_comparison"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "PROOF_RESPONSE_MODEL_QUALITY_COMPARISON_READY"
NOT_READY_STATUS = "PROOF_RESPONSE_MODEL_QUALITY_COMPARISON_NOT_READY"

RECOMMENDED_NEXT_TEST = "retry_local_with_schema_adapter"
RECOMMENDED_NEXT_TEST_OPTIONS = (
    "retry_local_with_schema_adapter",
    "run_more_external_synthetic_samples",
    "approve_external_redacted_test_packet",
    "stay_shadow_only",
)

PRECONDITIONS = {
    "local_lm_proof_response_pilot_postmortem": {
        "filename": "local_lm_proof_response_pilot_postmortem.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_PILOT_POSTMORTEM_READY",),
    },
    "external_synthetic_fact_alignment": {
        "filename": "external_lm_synthetic_response_capture_contract.json",
        "accepted_statuses": ("EXTERNAL_SYNTHETIC_FACT_ALIGNMENT_READY", "EXTERNAL_LM_SYNTHETIC_RESPONSE_CAPTURE_READY"),
    },
    "external_lm_synthetic_response_capture": {
        "filename": "external_lm_synthetic_response_capture_contract.json",
        "accepted_statuses": ("EXTERNAL_LM_SYNTHETIC_RESPONSE_CAPTURE_READY",),
    },
    "proof_to_response_schema_adapter": {
        "filename": "proof_to_response_schema_adapter_contract.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_SCHEMA_ADAPTER_READY",),
    },
    "proof_to_response_runtime": {
        "filename": "proof_to_response_runtime_contract.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_RUNTIME_READY",),
    },
    "external_lm_synthetic_test_packet": {
        "filename": "external_lm_synthetic_test_packet.json",
        "accepted_statuses": ("EXTERNAL_LM_SYNTHETIC_TEST_PACKET_READY",),
    },
}

AUTHORITY_BOUNDARY = {
    "model_invocation_allowed": False,
    "external_api_allowed": False,
    "external_lm_allowed": False,
    "local_model_runtime_allowed": False,
    "prompt_send_allowed": False,
    "proof_bundle_send_allowed": False,
    "private_proof_allowed": False,
    "secret_read_allowed": False,
    "business_action_allowed": False,
    "authority_grant_allowed": False,
    "protected_actions_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "ledger_posting_allowed": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "worker_spawn_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "sent": False,
    "paid": False,
}

IMPLEMENTATION_BOUNDARY = {
    "external_api_called": False,
    "external_llm_invoked": False,
    "local_model_runtime_connected": False,
    "model_invocation_performed": False,
    "prompt_sent": False,
    "proof_bundle_sent": False,
    "secret_read_performed": False,
    "business_action_performed": False,
    "email_send_performed": False,
    "gmail_access_performed": False,
    "browser_access_performed": False,
    "coupa_access_performed": False,
    "portal_submit_performed": False,
    "ledger_mutation_performed": False,
    "ledger_posting_performed": False,
    "paid_marking_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "worker_spawn_performed": False,
    "git_push_performed": False,
    "merge_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(external_capture.UNSAFE_TRUE_KEYS)
    | set(schema_adapter.UNSAFE_TRUE_KEYS)
    | set(verifier.UNSAFE_TRUE_KEYS)
    | {
        "authority_granted",
        "truth_checks_loosened",
        "authority_checks_loosened",
        "private_proof_external_allowed",
        "business_execution_allowed",
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
    return str(payload.get("status") or payload.get("readiness_status") or payload.get("contract_status") or "")


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


def _score(metrics: Mapping[str, Any]) -> int:
    weighted = {
        "schema_compliance": 2,
        "verifier_pass": 3,
        "concision": 1,
        "human_usefulness": 1,
        "agent_voice_fit": 1,
        "next_step_clarity": 1,
        "unsupported_claims_absent": 2,
        "protected_action_safety": 2,
        "machine_jargon_absent": 1,
    }
    return sum(weight for key, weight in weighted.items() if metrics.get(key) is True)


def _metric_row(
    *,
    candidate_ref: str,
    candidate_kind: str,
    source_ref: str,
    model_or_source: str,
    metrics: Mapping[str, Any],
    evidence: Mapping[str, Any],
    notes: list[str],
) -> dict[str, Any]:
    payload = {
        "candidate_ref": candidate_ref,
        "candidate_kind": candidate_kind,
        "source_ref": source_ref,
        "model_or_source": model_or_source,
        "metrics": dict(metrics),
        "quality_score": _score(metrics),
        "max_quality_score": 15,
        "evidence": dict(evidence),
        "notes": notes,
    }
    payload["quality_class"] = (
        "strong" if payload["quality_score"] >= 13 else "usable_with_followup" if payload["quality_score"] >= 10 else "not_ready"
    )
    return payload


def _local_qwen_row(postmortem: Mapping[str, Any]) -> dict[str, Any]:
    analysis = postmortem.get("analysis") if isinstance(postmortem.get("analysis"), Mapping) else {}
    classification = analysis.get("failure_classification") if isinstance(analysis.get("failure_classification"), Mapping) else {}
    fallback = postmortem.get("fallback_publication") if isinstance(postmortem.get("fallback_publication"), Mapping) else {}
    errors = [str(error) for error in analysis.get("verification_errors") or []]
    metrics = {
        "schema_compliance": False,
        "verifier_pass": False,
        "concision": False,
        "human_usefulness": False,
        "agent_voice_fit": False,
        "next_step_clarity": False,
        "unsupported_claims_absent": not bool(classification.get("unsupported_paid_sent_submitted_executed_claims")),
        "protected_action_safety": not bool(classification.get("protected_action_promises")),
        "machine_jargon_absent": not bool(classification.get("machine_contract_jargon_terms")),
    }
    return _metric_row(
        candidate_ref="local_qwen_first_run",
        candidate_kind="local_lm_one_time_pilot",
        source_ref="generated/read_models/local_lm_proof_response_pilot_postmortem.json",
        model_or_source="ollama/qwen3:8b-q4_K_M",
        metrics=metrics,
        evidence={
            "failure_type": str((postmortem.get("answer_to_required_questions") or {}).get("failure_type") or ""),
            "verifier_status": str(analysis.get("verifier_status") or ""),
            "verification_errors": errors,
            "fallback_correctly_published": fallback.get("fallback_correctly_published") is True,
            "recommended_prompt_schema_change": str(
                (postmortem.get("answer_to_required_questions") or {}).get("recommended_prompt_schema_change") or ""
            ),
        },
        notes=[
            "First local run failed because the model did not return verifier-compatible JSON.",
            "The failure was structural, not a protected-action or unsupported-completion claim failure.",
            "Safe fallback was published.",
        ],
    )


def _external_synthetic_row(capture_status: Mapping[str, Any]) -> dict[str, Any]:
    sample_capture = capture_status.get("sample_capture") if isinstance(capture_status.get("sample_capture"), Mapping) else {}
    smoke = capture_status.get("smoke_result") if isinstance(capture_status.get("smoke_result"), Mapping) else {}
    if not smoke and isinstance(sample_capture.get("adapter_result"), Mapping):
        adapter_result = sample_capture["adapter_result"]
        verifier_result = adapter_result.get("verifier_result") if isinstance(adapter_result.get("verifier_result"), Mapping) else {}
        smoke = {
            "adapter_parse_status": adapter_result.get("parse_status"),
            "verifier_pass": sample_capture.get("verifier_pass") is True or verifier_result.get("publishable") is True,
            "verifier_status": "verifier_pass" if sample_capture.get("verifier_pass") is True or verifier_result.get("publishable") is True else "",
            "verification_errors": adapter_result.get("verifier_failure_reasons") or verifier_result.get("verification_errors") or [],
        }
    candidate = capture_status.get("manual_candidate") if isinstance(capture_status.get("manual_candidate"), Mapping) else {}
    if not candidate:
        adapted = sample_capture.get("adapted_candidate") if isinstance(sample_capture.get("adapted_candidate"), Mapping) else {}
        candidate = {
            "body": adapted.get("draft_body"),
            "next_step": adapted.get("draft_next_step"),
        }
    body = str(candidate.get("body") or "")
    next_step = str(candidate.get("next_step") or "")
    errors = [str(error) for error in smoke.get("verification_errors") or []]
    alignment = capture_status.get("alignment_decision") if isinstance(capture_status.get("alignment_decision"), Mapping) else {}
    if not alignment:
        bundle = capture_status.get("synthetic_verifier_proof_bundle") if isinstance(capture_status.get("synthetic_verifier_proof_bundle"), Mapping) else {}
        fact_ids = [str(fact.get("fact_id")) for fact in bundle.get("known_facts") or [] if isinstance(fact, Mapping) and str(fact.get("fact_id"))]
        alignment = {"canonical_fact_ids": fact_ids}
    metrics = {
        "schema_compliance": smoke.get("adapter_parse_status") == "PARSED",
        "verifier_pass": smoke.get("verifier_pass") is True,
        "concision": bool(body) and len(body) <= 280,
        "human_usefulness": "payment evidence" in body.lower() and "ledger" in body.lower(),
        "agent_voice_fit": True,
        "next_step_clarity": next_step == "Attach payment evidence.",
        "unsupported_claims_absent": not any("unsupported_completion_claim" in error for error in errors),
        "protected_action_safety": not any("protected_action_promise" in error for error in errors),
        "machine_jargon_absent": not any("machine_contract_jargon" in error for error in errors),
    }
    return _metric_row(
        candidate_ref="external_synthetic_manual_response",
        candidate_kind="manual_external_synthetic_capture",
        source_ref="generated/read_models/external_lm_synthetic_response_capture_status.json",
        model_or_source="manual_external_synthetic_response",
        metrics=metrics,
        evidence={
            "adapter_parse_status": str(smoke.get("adapter_parse_status") or ""),
            "verifier_status": str(smoke.get("verifier_status") or ""),
            "verification_errors": errors,
            "canonical_fact_ids": list(alignment.get("canonical_fact_ids") or []),
            "synthetic_only": True,
            "published_as_real_finance_truth": False,
        },
        notes=[
            "Manual synthetic external response passed after fact-id alignment.",
            "Result is quality evidence for synthetic data only.",
            "It does not authorize private proof exposure or external provider use.",
        ],
    )


def _shadow_baseline_row(shadow_pilot: Mapping[str, Any]) -> dict[str, Any]:
    runs = [run for run in shadow_pilot.get("pilot_runs") or [] if isinstance(run, Mapping)]
    finance_run = next((run for run in runs if run.get("scenario_id") == "finance_capital_hilton_payment_watch"), runs[0] if runs else {})
    candidate = finance_run.get("candidate_response") if isinstance(finance_run.get("candidate_response"), Mapping) else {}
    verifier_result = finance_run.get("verifier_result") if isinstance(finance_run.get("verifier_result"), Mapping) else {}
    body = str(candidate.get("draft_body") or "")
    next_step = str(candidate.get("draft_next_step") or "")
    errors = [str(error) for error in verifier_result.get("verification_errors") or []]
    metrics = {
        "schema_compliance": True,
        "verifier_pass": verifier_result.get("publishable") is True,
        "concision": bool(body) and len(body) <= 280,
        "human_usefulness": "payment evidence" in body.lower() and "ledger" in body.lower(),
        "agent_voice_fit": str(candidate.get("speaker_ref") or "") == "chief",
        "next_step_clarity": next_step == "Attach payment evidence.",
        "unsupported_claims_absent": not any("unsupported_completion_claim" in error for error in errors),
        "protected_action_safety": not any("protected_action_promise" in error for error in errors),
        "machine_jargon_absent": not any("machine_contract_jargon" in error for error in errors),
    }
    return _metric_row(
        candidate_ref="shadow_mock_baseline",
        candidate_kind="shadow_fixture_mock_lm_style_text",
        source_ref="generated/read_models/proof_to_response_lm_shadow_pilot.json",
        model_or_source="shadow_pilot_candidate",
        metrics=metrics,
        evidence={
            "scenario_id": str(finance_run.get("scenario_id") or ""),
            "verifier_status": str(verifier_result.get("status") or ""),
            "verification_errors": errors,
            "all_pilot_drafts_verified": bool((shadow_pilot.get("machine_proof") or {}).get("all_pilot_drafts_verified") is True),
            "pilot_run_count": int(shadow_pilot.get("pilot_run_count") or 0),
        },
        notes=[
            "Shadow/mock baseline remains the strongest deterministic control.",
            "It is not a live model quality sample.",
        ],
    )


def _source_hashes(read_model_root: Path, filenames: list[str]) -> dict[str, str]:
    root = _rooted(read_model_root)
    hashes: dict[str, str] = {}
    for filename in filenames:
        payload = _load_json(root / filename)
        hashes[f"generated/read_models/{filename}"] = _content_hash(payload) if payload else ""
    return hashes


def build_comparison_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    root = _rooted(read_model_root)
    postmortem = _load_json(root / "local_lm_proof_response_pilot_postmortem.json")
    capture_status = _load_json(root / "external_lm_synthetic_response_capture_contract.json")
    schema_status = _load_json(root / "proof_to_response_schema_adapter_contract.json")
    packet = _load_json(root / "external_lm_synthetic_test_packet.json")
    shadow_pilot = _load_json(root / "proof_to_response_lm_shadow_pilot.json")

    rows = [
        _local_qwen_row(postmortem),
        _external_synthetic_row(capture_status),
        _shadow_baseline_row(shadow_pilot),
    ]
    preconditions = precondition_rows(root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    recommended_reasons = [
        "The local qwen run failed primarily because it did not return JSON, not because it made unsafe business claims.",
        "The schema adapter and aligned synthetic external sample show that verifier-compatible JSON can pass without loosening rules.",
        "The shadow baseline remains clean, so the next local test should target schema compliance before expanding external samples.",
    ]
    source_filenames = [
        "local_lm_proof_response_pilot_postmortem.json",
        "external_lm_synthetic_response_capture_contract.json",
        "proof_to_response_schema_adapter_contract.json",
        "external_lm_synthetic_test_packet.json",
        "proof_to_response_lm_shadow_pilot.json",
    ]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Compare verifier-gated proof-to-response quality across local qwen, manually captured synthetic external response, and shadow/mock baseline.",
        "comparison_scope": {
            "local_qwen_first_run": "failed_non_json",
            "synthetic_external_response": "verifier_pass_after_fact_alignment",
            "shadow_mock_response_baseline": "verifier_clean_fixture",
            "private_proof_compared": False,
            "business_execution_compared": False,
        },
        "metrics": [
            "schema_compliance",
            "verifier_pass",
            "concision",
            "human_usefulness",
            "agent_voice_fit",
            "next_step_clarity",
            "unsupported_claims",
            "protected_action_safety",
            "machine_jargon_absence",
        ],
        "candidate_comparisons": rows,
        "ranking": sorted(
            [{"candidate_ref": row["candidate_ref"], "quality_score": row["quality_score"], "quality_class": row["quality_class"]} for row in rows],
            key=lambda row: row["quality_score"],
            reverse=True,
        ),
        "recommended_next_test": RECOMMENDED_NEXT_TEST,
        "recommended_next_test_options": list(RECOMMENDED_NEXT_TEST_OPTIONS),
        "reasons": recommended_reasons,
        "source_refs": [f"generated/read_models/{filename}" for filename in source_filenames],
        "source_content_hashes": _source_hashes(root, source_filenames),
        "preconditions": preconditions,
        "schema_adapter_summary": {
            "status": _status(schema_status),
            "adapter_ready": schema_status.get("adapter_ready") is True,
            "strict_schema_required_fields": list(schema_status.get("strict_schema_required_fields") or []),
        },
        "synthetic_packet_summary": {
            "status": _status(packet),
            "canonical_fact_ids": list(
                ((packet.get("copy_paste_packet") or {}).get("synthetic_proof_bundle") or {}).get("canonical_fact_ids") or []
            ),
            "synthetic_only": True,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"] = {
        "preconditions_ready": preconditions_ready,
        "model_invocation_performed": False,
        "external_api_called": False,
        "external_llm_invoked": False,
        "local_model_runtime_connected": False,
        "prompt_sent": False,
        "proof_bundle_sent": False,
        "business_action_performed": False,
        "private_proof_compared": False,
        "truth_checks_loosened": False,
        "authority_checks_loosened": False,
        "unsafe_true_grants": unsafe,
        "unsafe_true_grants_absent": not unsafe,
    }
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    payload["content_hash"] = _content_hash({k: v for k, v in payload.items() if k != "content_hash"})
    return payload


def build_wiki(model: Mapping[str, Any]) -> str:
    lines = [
        "# Proof To Response Model Quality Comparison",
        "",
        f"Status: `{model.get('status', NOT_READY_STATUS)}`",
        "",
        "This comparison uses recorded local read models only. It does not invoke models, call APIs, browse, send prompts, send proof bundles, mutate business systems, or push.",
        "",
        "## Summary",
        "",
    ]
    for row in model.get("candidate_comparisons", []):
        lines.append(
            f"- `{row['candidate_ref']}`: score `{row['quality_score']}/{row['max_quality_score']}`, class `{row['quality_class']}`"
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"Recommended next test: `{model.get('recommended_next_test')}`",
            "",
        ]
    )
    for reason in model.get("reasons", []):
        lines.append(f"- {reason}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Candidate text is not truth.",
            "- The verifier remains the publication gate.",
            "- Synthetic success is not real Finance truth.",
            "- Private proof and business execution remain blocked.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_comparison(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    model = build_comparison_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    _write_json(json_path, model)

    bridge_path = ""
    if bridge_root is not None:
        bridge_root = _rooted(bridge_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        target = bridge_root / JSON_EXPORT_NAME
        shutil.copy2(json_path, target)
        bridge_path = target.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(model), encoding="utf-8")
    return {
        "status": str(model["status"]),
        "json_path": json_path.as_posix(),
        "bridge_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export proof-to-response model quality comparison V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_comparison(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=None if args.no_bridge else Path(args.bridge_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
