"""Local LM proof-to-response pilot postmortem V0.

Analyzes the completed one-time local LM proof-to-response pilot artifacts. This
module reads saved read models and receipt SQLite only. It does not invoke a
model, connect runtimes, send prompts or proof bundles, call providers, spawn
workers, send email, open browser/Gmail/Coupa, mutate ledgers/workbooks, export
PDFs, mark paid, submit, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import proof_to_response_runtime
import proof_to_response_verifier


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Local LM Proof Response Pilot Postmortem.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/local_lm_proof_response_one_time_pilot.sqlite")

SCHEMA_VERSION = "local_lm_proof_response_pilot_postmortem_v0"
READ_MODEL_ID = "local_lm_proof_response_pilot_postmortem"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_PILOT_POSTMORTEM_READY"
NOT_READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_PILOT_POSTMORTEM_NOT_READY"

PRECONDITIONS = {
    "local_lm_proof_response_one_time_pilot": {
        "filename": "local_lm_proof_response_one_time_pilot.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_ONE_TIME_PILOT_READY",),
    },
    "proof_to_response_runtime": {
        "filename": proof_to_response_runtime.STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (proof_to_response_runtime.READY_STATUS,),
    },
    "proof_bundle_freshness_trace_integration": {
        "filename": "proof_bundle_freshness_trace_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY",),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": "proof_bundle_builder_redaction_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY",),
    },
}

UNSAFE_TRUE_KEYS = (
    set(proof_to_response_runtime.UNSAFE_TRUE_KEYS)
    | set(proof_to_response_verifier.UNSAFE_TRUE_KEYS)
    | {
        "pilot_successful",
        "draft_successful",
        "verifier_passed",
        "truth_checks_loosened",
        "authority_checks_loosened",
        "protected_gate_loosened",
        "next_invocation_approved",
        "model_invoked",
        "runtime_connected",
        "prompt_sent",
        "proof_bundle_sent",
        "external_provider_used",
        "business_action_performed",
        "paid",
        "sent",
        "submitted",
        "executed",
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
    return str(payload.get("readiness_status") or payload.get("status") or payload.get("contract_status") or "")


def _shadow_runtime_row(read_model_root: Path) -> dict[str, Any]:
    root = _rooted(read_model_root)
    status = _load_json(root / proof_to_response_runtime.STATUS_JSON_EXPORT_NAME)
    active = str(status.get("active_candidate_source") or "")
    ready = status.get("status") == proof_to_response_runtime.READY_STATUS and active == proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT
    return {
        "precondition_ref": "proof_to_response_shadow_pilot_runtime",
        "source_ref": f"generated/read_models/{proof_to_response_runtime.STATUS_JSON_EXPORT_NAME}",
        "observed_status": "PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_READY" if ready else "PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_NOT_READY",
        "accepted_statuses": ["PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_READY"],
        "observed_active_candidate_source": active,
        "accepted_active_candidate_source": proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
        "ready": ready,
    }


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
    rows.append(_shadow_runtime_row(root))
    return rows


def sqlite_receipt_summary(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> dict[str, Any]:
    path = _rooted(sqlite_path)
    if not path.exists():
        return {"sqlite_path": path.as_posix(), "row_count": 0, "receipt_refs": []}
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            "SELECT receipt_ref, receipt_status, proof_summary FROM local_lm_pilot_receipts ORDER BY receipt_ref"
        ).fetchall()
    return {
        "sqlite_path": path.as_posix(),
        "row_count": len(rows),
        "receipt_refs": [str(row[0]) for row in rows],
        "receipt_rows": [
            {
                "receipt_ref": str(row[0]),
                "receipt_status": str(row[1]),
                "proof_summary": str(row[2]),
            }
            for row in rows
        ],
    }


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def analyze_failure(pilot: Mapping[str, Any]) -> dict[str, Any]:
    parse = pilot.get("model_output_parse") if isinstance(pilot.get("model_output_parse"), Mapping) else {}
    candidate = pilot.get("candidate_response") if isinstance(pilot.get("candidate_response"), Mapping) else {}
    verifier = pilot.get("verifier_result") if isinstance(pilot.get("verifier_result"), Mapping) else {}
    published = pilot.get("published_response") if isinstance(pilot.get("published_response"), Mapping) else {}
    errors = [str(error) for error in verifier.get("verification_errors") or []]
    candidate_text = " ".join(
        str(candidate.get(field) or "")
        for field in ("draft_headline", "draft_body", "draft_next_step")
    )
    unsupported_claims = [
        error.removeprefix("unsupported_completion_claim:")
        for error in errors
        if error.startswith("unsupported_completion_claim:")
    ]
    protected_promises = [
        error.removeprefix("protected_action_promise:")
        for error in errors
        if error.startswith("protected_action_promise:")
    ]
    jargon = [
        error.removeprefix("machine_contract_jargon:")
        for error in errors
        if error.startswith("machine_contract_jargon:")
    ]
    parse_failed = parse.get("json_parse_succeeded") is False
    classification = {
        "structurally_invalid": parse_failed or not candidate_text.strip(),
        "non_json": parse_failed,
        "too_verbose": "response_not_concise" in errors and not candidate_text.strip() is False,
        "empty_candidate_after_parse_failure": not candidate_text.strip(),
        "factually_unsafe": bool(unsupported_claims or protected_promises),
        "unsupported_paid_sent_submitted_executed_claims": unsupported_claims,
        "protected_action_promises": protected_promises,
        "machine_contract_jargon_terms": jargon,
    }
    return {
        "what_failed": "Model output did not parse as the required JSON response, so the verifier received an empty candidate.",
        "verifier_status": str(verifier.get("status") or ""),
        "verifier_publishable": verifier.get("publishable") is True,
        "verification_errors": errors,
        "failure_classification": classification,
        "candidate_response_id": str(candidate.get("response_id") or ""),
        "raw_stdout_sha256": str(parse.get("raw_stdout_sha256") or ""),
        "raw_stderr_sha256": str(parse.get("raw_stderr_sha256") or ""),
        "draft_included_unsupported_completion_claims": bool(unsupported_claims),
        "draft_included_protected_action_promises": bool(protected_promises),
        "draft_included_machine_contract_jargon": bool(jargon),
        "candidate_text_empty": not candidate_text.strip(),
        "fallback_correctly_published": (
            pilot.get("publication_decision") == "safe_fallback_published"
            and published.get("verification_status") == "fallback"
            and str(published.get("headline") or "") == "Needs verification"
        ),
    }


def recommendations(analysis: Mapping[str, Any]) -> dict[str, Any]:
    parse_failed = (analysis.get("failure_classification") or {}).get("non_json") is True
    return {
        "prompt_schema_change": [
            "Require JSON-only output with no prose outside the JSON object." if parse_failed else "Keep JSON response schema explicit.",
            "Include one valid example JSON response in the prompt.",
            "Repeat the allowed keys: headline, body, next_step, missing_input, can_do_now, cannot_do_yet, requested_controls, claimed_facts.",
            "Add a short local schema-adapter test before another model invocation.",
        ],
        "verifier_policy": [
            "Keep verifier mandatory.",
            "Keep fallback mandatory.",
            "Do not loosen truth or authority checks to make the model pass.",
            "Do not loosen protected gates.",
        ],
        "next_test_recommendation": "schema_adapter_test",
        "next_test_rationale": (
            "The failure was structural/non-JSON rather than an unsafe factual claim. Test parsing and schema adaptation with saved or synthetic outputs before any new model invocation."
        ),
        "next_invocation_requires_operator_approval": True,
        "local_retry_recommended_now": False,
        "external_synthetic_test_recommended_now": False,
    }


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    pilot = _load_json(_rooted(read_model_root) / "local_lm_proof_response_one_time_pilot.json")
    latest = _load_json(_rooted(read_model_root) / proof_to_response_runtime.LATEST_JSON_EXPORT_NAME)
    preconditions = precondition_rows(read_model_root)
    analysis = analyze_failure(pilot)
    recs = recommendations(analysis)
    receipts = sqlite_receipt_summary(sqlite_path)
    fallback_receipt_present = "fallback_receipt" in receipts["receipt_refs"]
    pilot_draft_successful = analysis["verifier_publishable"] is True
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all(row.get("ready") is True for row in preconditions) and analysis["fallback_correctly_published"] else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Analyze why the one-time local LM proof-to-response pilot failed deterministic verification.",
        "source_pilot_ref": "generated/read_models/local_lm_proof_response_one_time_pilot.json",
        "source_latest_ref": "generated/read_models/proof_to_response_latest.json",
        "pilot_status": str(pilot.get("status") or ""),
        "pilot_publication_decision": str(pilot.get("publication_decision") or ""),
        "pilot_draft_successful": pilot_draft_successful,
        "pilot_attempt_successful": False,
        "analysis": analysis,
        "fallback_publication": {
            "fallback_correctly_published": analysis["fallback_correctly_published"],
            "fallback_receipt_present": fallback_receipt_present,
            "latest_response_status": str(latest.get("proof_to_response_status") or ""),
            "latest_candidate_source": str(latest.get("candidate_source") or ""),
            "latest_headline": str((latest.get("latest_response") or {}).get("headline") or ""),
        },
        "recommendations": recs,
        "answer_to_required_questions": {
            "what_exactly_failed": analysis["what_failed"],
            "failure_type": "non_json_structurally_invalid_empty_candidate",
            "unsupported_completion_claims_present": analysis["draft_included_unsupported_completion_claims"],
            "protected_action_promises_present": analysis["draft_included_protected_action_promises"],
            "machine_contract_jargon_present": analysis["draft_included_machine_contract_jargon"],
            "fallback_correctly_published": analysis["fallback_correctly_published"],
            "recommended_prompt_schema_change": "JSON-only response schema with one valid example and a schema-adapter test.",
            "recommended_next_test": recs["next_test_recommendation"],
        },
        "receipt_summary": receipts,
        "preconditions": preconditions,
        "source_refs": [
            "generated/read_models/local_lm_proof_response_one_time_pilot.json",
            "generated/read_models/proof_to_response_latest.json",
            "generated/system_knowledge/local_lm_proof_response_one_time_pilot.sqlite",
            "proof_to_response_runtime.py",
            "proof_to_response_verifier.py",
        ],
        "source_content_hashes": {
            "pilot": _content_hash(pilot),
            "latest": _content_hash(latest),
            "analysis": _content_hash(analysis),
            "recommendations": _content_hash(recs),
            "receipts": _content_hash(receipts),
        },
        "authority_boundary": {
            "truth_checks_loosened": False,
            "authority_checks_loosened": False,
            "protected_gate_loosened": False,
            "next_invocation_approved": False,
            "protected_actions_allowed": False,
            "authority_granted": False,
        },
        "implementation_boundary": {
            "model_invoked": False,
            "runtime_connected": False,
            "prompt_sent": False,
            "proof_bundle_sent": False,
            "external_provider_used": False,
            "worker_spawn_performed": False,
            "business_action_performed": False,
        },
        "machine_proof": {
            "postmortem_only": True,
            "verifier_failure_reason_recorded": bool(analysis["verification_errors"]),
            "fallback_published": analysis["fallback_correctly_published"],
            "pilot_draft_successful": pilot_draft_successful,
            "does_not_mark_pilot_successful_if_draft_failed": not pilot_draft_successful,
            "recommendations_keep_protected_gates": True,
            "unsafe_true_grants_absent": True,
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    payload["content_hash"] = _content_hash({key: value for key, value in payload.items() if key != "content_hash"})
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    analysis = read_model.get("analysis") if isinstance(read_model.get("analysis"), Mapping) else {}
    classification = analysis.get("failure_classification") if isinstance(analysis.get("failure_classification"), Mapping) else {}
    recs = read_model.get("recommendations") if isinstance(read_model.get("recommendations"), Mapping) else {}
    lines = [
        "# Local LM Proof Response Pilot Postmortem",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "This postmortem analyzes saved pilot artifacts only. It does not invoke a model, connect runtimes, send prompts, or send proof bundles.",
        "",
        "## What Failed",
        "",
        f"- {analysis.get('what_failed')}",
        f"- Verifier status: `{analysis.get('verifier_status')}`",
        f"- Verification errors: `{', '.join(analysis.get('verification_errors') or [])}`",
        "",
        "## Classification",
        "",
        f"- Non-JSON: `{str(classification.get('non_json')).lower()}`",
        f"- Structurally invalid: `{str(classification.get('structurally_invalid')).lower()}`",
        f"- Empty candidate after parse failure: `{str(classification.get('empty_candidate_after_parse_failure')).lower()}`",
        f"- Factually unsafe: `{str(classification.get('factually_unsafe')).lower()}`",
        f"- Unsupported completion claims: `{str(analysis.get('draft_included_unsupported_completion_claims')).lower()}`",
        f"- Protected action promises: `{str(analysis.get('draft_included_protected_action_promises')).lower()}`",
        f"- Machine-contract jargon: `{str(analysis.get('draft_included_machine_contract_jargon')).lower()}`",
        "",
        "## Fallback",
        "",
        f"- Correctly published: `{str(analysis.get('fallback_correctly_published')).lower()}`",
        f"- Latest headline: {((read_model.get('fallback_publication') or {}).get('latest_headline'))}",
        "",
        "## Recommendations",
        "",
    ]
    for item in recs.get("prompt_schema_change") or []:
        lines.append(f"- {item}")
    for item in recs.get("verifier_policy") or []:
        lines.append(f"- {item}")
    lines.extend(
        [
            f"- Recommended next test: `{recs.get('next_test_recommendation')}`",
            "- Do not rerun a model until the operator approves the next invocation.",
            "",
        ]
    )
    return "\n".join(lines)


def export_postmortem(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, sqlite_path=sqlite_path, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    _write_json(read_model_path, read_model)

    bridge_read_model_path = ""
    if bridge_root is not None:
        bridge_root = _rooted(bridge_root)
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
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Local LM Proof Response Pilot Postmortem V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--generated-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    bridge_root = Path(args.bridge_root) if args.bridge_root else None
    result = export_postmortem(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=bridge_root,
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
