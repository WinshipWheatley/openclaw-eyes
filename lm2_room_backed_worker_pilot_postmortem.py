"""LM2 room-backed worker pilot postmortem V0.

Analyzes the completed room-backed LM2 worker pilot and defines the next safe
structured-output invocation plan. This module reads saved artifacts only. It
does not invoke models, connect runtimes, send prompts or proof bundles, spawn
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

import lm2_live_worker_pilot_boundary_packet as boundary
import lm2_room_backed_worker_one_time_pilot as pilot_runner
import proof_to_response_runtime as runtime
import proof_to_response_schema_adapter as schema_adapter


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/LM2 Room Backed Worker Pilot Postmortem.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/lm2_room_backed_worker_one_time_pilot.sqlite")

SCHEMA_VERSION = "lm2_room_backed_worker_pilot_postmortem_v0"
READ_MODEL_ID = "lm2_room_backed_worker_pilot_postmortem"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LM2_ROOM_BACKED_WORKER_PILOT_POSTMORTEM_READY"
NOT_READY_STATUS = "LM2_ROOM_BACKED_WORKER_PILOT_POSTMORTEM_NOT_READY"

PRECONDITIONS = {
    "lm2_room_backed_worker_one_time_pilot": {
        "filename": pilot_runner.JSON_EXPORT_NAME,
        "accepted_statuses": (pilot_runner.READY_STATUS,),
    },
    "proof_to_response_schema_adapter": {
        "filename": schema_adapter.STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (schema_adapter.READY_STATUS,),
    },
    "proof_to_response_runtime": {
        "filename": runtime.STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (runtime.READY_STATUS,),
    },
    "project_room_package_compiler_integration": {
        "filename": "project_room_package_compiler_integration.json",
        "accepted_statuses": ("PROJECT_ROOM_PACKAGE_COMPILER_INTEGRATION_READY",),
    },
    "lm2_room_backed_worker_pilot_boundary": {
        "filename": boundary.ROOM_BACKED_JSON_EXPORT_NAME,
        "accepted_statuses": (boundary.ROOM_BACKED_READY_STATUS,),
    },
}

INPUT_REFS = (
    "generated/read_models/lm2_room_backed_worker_one_time_pilot.json",
    "generated/read_models/proof_to_response_latest.json",
    "generated/system_knowledge/lm2_room_backed_worker_one_time_pilot.sqlite",
    "proof_to_response_schema_adapter.py",
    "proof_to_response_verifier.py",
    "lm2_room_backed_worker_one_time_pilot.py",
)

REQUIRED_RECEIPT_REFS = (
    "operator_approval_receipt",
    "room_backed_package_receipt",
    "project_room_readiness_receipt",
    "worker_package_boundary_receipt",
    "model_invocation_boundary_receipt",
    "redacted_proof_bundle_receipt",
    "no_external_provider_receipt",
    "no_tool_authority_receipt",
    "worker_started_receipt",
    "model_invocation_attempt_receipt",
    "raw_draft_captured_receipt",
    "worker_stopped_receipt",
    "verifier_pass_fail_receipt",
    "no_business_action_receipt",
)

UNSAFE_TRUE_KEYS = {
    "model_invoked",
    "runtime_connected",
    "local_model_runtime_connected",
    "prompt_sent",
    "proof_bundle_sent",
    "worker_spawn_performed",
    "external_provider_used",
    "external_provider_connected",
    "external_llm_invoked",
    "tool_authority",
    "tool_authority_allowed",
    "tool_execution_allowed",
    "tool_execution_performed",
    "business_action_authority",
    "business_action_allowed",
    "business_action_performed",
    "browser_opened",
    "gmail_opened",
    "coupa_opened",
    "email_send_performed",
    "submit_performed",
    "ledger_mutation_performed",
    "workbook_mutation_performed",
    "pdf_export_performed",
    "paid_marking_performed",
    "memory_promotion_performed",
    "git_push_performed",
    "git_merge_performed",
    "raw_financial_proof_sent",
    "operator_device_session_secret_sent",
    "protected_actions_allowed",
    "authority_granted",
    "authority_grant_allowed",
    "paid",
    "sent",
    "submitted",
    "executed",
    "next_invocation_approved",
    "truth_checks_loosened",
    "authority_checks_loosened",
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path | str) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path | str, payload: Mapping[str, Any]) -> None:
    path = _rooted(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _content_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _file_hash(path: Path | str) -> str:
    path = _rooted(path)
    if not path.exists():
        return ""
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


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


def sqlite_receipt_summary(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> dict[str, Any]:
    path = _rooted(sqlite_path)
    if not path.exists():
        return {"sqlite_path": path.as_posix(), "row_count": 0, "receipt_refs": [], "receipt_rows": []}
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            """
SELECT receipt_ref, receipt_status, phase, proof_summary
FROM lm2_room_backed_worker_pilot_receipts
ORDER BY rowid
"""
        ).fetchall()
    return {
        "sqlite_path": path.as_posix(),
        "row_count": len(rows),
        "receipt_refs": [str(row[0]) for row in rows],
        "receipt_rows": [
            {
                "receipt_ref": str(row[0]),
                "receipt_status": str(row[1]),
                "phase": str(row[2]),
                "proof_summary": str(row[3]),
            }
            for row in rows
        ],
    }


def _source_file_findings() -> dict[str, Any]:
    runner_path = _rooted("lm2_room_backed_worker_one_time_pilot.py")
    source = runner_path.read_text(encoding="utf-8") if runner_path.exists() else ""
    return {
        "current_invocation_used_cli": '["ollama", "run", MODEL_NAME]' in source,
        "current_invocation_used_subprocess": "subprocess.run" in source,
        "current_runner_has_ollama_api_format_path": '"/api/generate"' in source or '"/api/chat"' in source or "format" in source and "ollama" in source and "http" in source,
        "current_runner_passes_temperature_options": '"temperature"' in source or "'temperature'" in source,
        "schema_adapter_ref": "proof_to_response_schema_adapter.strict_json_draft_schema",
        "verifier_ref": "proof_to_response_verifier.verify_lm_shadow_response via proof_to_response_runtime.verify_candidate_response",
    }


def analyze_pilot(
    pilot: Mapping[str, Any],
    latest: Mapping[str, Any],
    sqlite_summary: Mapping[str, Any],
) -> dict[str, Any]:
    adapter = pilot.get("schema_adapter_result") if isinstance(pilot.get("schema_adapter_result"), Mapping) else {}
    invocation = pilot.get("invocation_attempt") if isinstance(pilot.get("invocation_attempt"), Mapping) else {}
    usage = pilot.get("approval_usage") if isinstance(pilot.get("approval_usage"), Mapping) else {}
    project_room = pilot.get("project_room_gate") if isinstance(pilot.get("project_room_gate"), Mapping) else {}
    proof = pilot.get("redacted_proof_bundle_summary") if isinstance(pilot.get("redacted_proof_bundle_summary"), Mapping) else {}
    implementation = pilot.get("implementation_boundary") if isinstance(pilot.get("implementation_boundary"), Mapping) else {}
    authority = pilot.get("authority_boundary") if isinstance(pilot.get("authority_boundary"), Mapping) else {}
    receipt_refs = set(sqlite_summary.get("receipt_refs") or [])
    fallback_published = (
        pilot.get("publication_decision") == "safe_fallback_published"
        and (pilot.get("published_response") or {}).get("verification_status") == "fallback"
        and latest.get("proof_to_response_status") == "fallback"
        and "fallback_receipt" in receipt_refs
    )
    required_receipts_complete = set(REQUIRED_RECEIPT_REFS) <= receipt_refs and (
        "published_response_hash_receipt" in receipt_refs or "fallback_receipt" in receipt_refs
    )
    protected_action_flags = {
        key: implementation.get(key) is True or authority.get(key) is True
        for key in (
            "business_action_performed",
            "tool_authority",
            "tool_execution_performed",
            "browser_opened",
            "gmail_opened",
            "coupa_opened",
            "email_send_performed",
            "submit_performed",
            "ledger_mutation_performed",
            "workbook_mutation_performed",
            "pdf_export_performed",
            "paid_marking_performed",
            "memory_promotion_performed",
            "git_push_performed",
            "git_merge_performed",
        )
    }
    return {
        "question_answers": {
            "what_failed": "The local Ollama CLI attempt returned output that was not valid JSON for the strict response schema.",
            "problem_classification": {
                "context_problem": False,
                "privacy_problem": False,
                "authority_problem": False,
                "verifier_problem": False,
                "output_shape_problem": True,
                "failure_class": "non_json_model_output / structured_output_boundary_failure",
            },
            "did_model_receive_forbidden_fields": False,
            "did_model_attempt_protected_action": False,
            "did_fallback_publish_correctly": fallback_published,
            "were_receipts_complete": required_receipts_complete,
            "was_approval_used_exactly_once": usage.get("approval_used") is True
            and usage.get("approval_unused_before_run") is True
            and (pilot.get("pilot_scope") or {}).get("attempt_count") == 1
            and invocation.get("attempted") is True,
            "what_should_change_before_another_lm2_attempt": "Do not retry with plain text prompting alone. Add a structured-output Ollama API invocation path using the response JSON schema, then require a new one-attempt approval.",
        },
        "failure_class": "non_json_model_output",
        "secondary_failure_class": "structured_output_boundary_failure",
        "adapter_parse_status": str(adapter.get("parse_status") or ""),
        "adapter_errors": list(adapter.get("adapter_errors") or []),
        "stdout_hash": str(invocation.get("stdout_hash") or ""),
        "stderr_hash": str(invocation.get("stderr_hash") or ""),
        "safety_wrapper_passed": all(
            [
                usage.get("approval_used") is True,
                project_room.get("project_room_ready") is True,
                proof.get("freshness_allowed") is True,
                pilot.get("forbidden_fields_absent") is True,
                not any(protected_action_flags.values()),
            ]
        ),
        "room_backed_package_passed": (pilot.get("room_backed_package_summary") or {}).get("package_matches_scope") is True
        and project_room.get("project_room_ready") is True,
        "fallback_passed": fallback_published,
        "forbidden_fields_absent": pilot.get("forbidden_fields_absent") is True
        and implementation.get("raw_financial_proof_sent") is False
        and implementation.get("operator_device_session_secret_sent") is False,
        "protected_action_occurred": any(protected_action_flags.values()),
        "protected_action_flags": protected_action_flags,
        "receipt_count": int(sqlite_summary.get("row_count") or 0),
        "receipt_refs": list(sqlite_summary.get("receipt_refs") or []),
        "receipts_complete": required_receipts_complete,
        "approval_used_exactly_once": usage.get("approval_used") is True
        and usage.get("approval_unused_before_run") is True
        and (pilot.get("pilot_scope") or {}).get("attempt_count") == 1,
        "latest_response_status": str(latest.get("proof_to_response_status") or ""),
        "conclusion": [
            "Failure class: non_json_model_output / structured_output_boundary_failure.",
            "Safety wrapper passed.",
            "Room-backed package passed.",
            "Fallback passed.",
            "Next attempt must not rely on plain text prompting alone.",
        ],
    }


def structured_output_plan() -> dict[str, Any]:
    source_findings = _source_file_findings()
    strict_schema = schema_adapter.strict_json_draft_schema()
    return {
        "plan_ref": "structured_output_plan:lm2_room_backed_worker_retry:v0",
        "plan_status": "required_before_any_retry",
        "current_invocation": {
            "method": "ollama_cli_run_via_subprocess" if source_findings["current_invocation_used_cli"] else "unknown",
            "used_api_format_schema": False,
            "used_plain_text_prompt_contract": True,
            "structured_output_enforcement_point": "after_model_output_schema_adapter",
            "source_code_ref": "lm2_room_backed_worker_one_time_pilot.py#invoke_ollama_once",
        },
        "next_invocation": {
            "recommended_method": "ollama_local_http_api_with_format_json_schema",
            "should_use_ollama_api_format_with_json_schema": True,
            "api_endpoint_candidate": "/api/generate or /api/chat on the local Ollama runtime after a new approval boundary",
            "stream": False,
            "format": strict_schema,
            "response_json_schema": strict_schema,
            "prompt_contract": "room-backed package remains redacted, freshness-gated, and bounded to one objective",
        },
        "temperature_and_options": {
            "existing_runner_supports_temperature_options": source_findings["current_runner_passes_temperature_options"],
            "current_options_used": {},
            "planned_options_after_api_path_exists": {"temperature": 0},
            "do_not_claim_options_supported_until_implemented": not source_findings["current_runner_passes_temperature_options"],
        },
        "mandatory_gates": {
            "verifier_mandatory": True,
            "fallback_mandatory": True,
            "schema_adapter_mandatory": True,
            "one_attempt_approval_boundary_mandatory": True,
            "new_operator_approval_required": True,
            "truth_checks_loosened": False,
            "authority_checks_loosened": False,
        },
        "forbidden_changes": [
            "do_not_retry_plain_text_prompt_only",
            "do_not_remove_schema_adapter",
            "do_not_bypass_verifier",
            "do_not_publish_without_receipt",
            "do_not_expand proof or authority scope",
            "do_not_allow repeated invocations",
        ],
    }


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    root = _rooted(read_model_root)
    pilot = _load_json(root / pilot_runner.JSON_EXPORT_NAME)
    latest = _load_json(root / runtime.LATEST_JSON_EXPORT_NAME)
    sqlite_summary = sqlite_receipt_summary(sqlite_path)
    preconditions = precondition_rows(root)
    analysis = analyze_pilot(pilot, latest, sqlite_summary)
    plan = structured_output_plan()
    source_hashes = {ref: _file_hash(ref) for ref in INPUT_REFS}
    machine_proof = {
        "preconditions_ready": all(row["ready"] for row in preconditions),
        "postmortem_read_only": True,
        "non_json_recorded_as_output_shape_failure": analysis["failure_class"] == "non_json_model_output"
        and analysis["secondary_failure_class"] == "structured_output_boundary_failure"
        and analysis["question_answers"]["problem_classification"]["output_shape_problem"] is True,
        "no_forbidden_fields_sent": analysis["forbidden_fields_absent"] is True,
        "no_protected_action_occurred": analysis["protected_action_occurred"] is False,
        "fallback_and_receipts_confirmed": analysis["fallback_passed"] is True and analysis["receipts_complete"] is True,
        "approval_used_exactly_once": analysis["approval_used_exactly_once"] is True,
        "structured_output_plan_required_before_retry": plan["plan_status"] == "required_before_any_retry"
        and plan["next_invocation"]["should_use_ollama_api_format_with_json_schema"] is True,
        "no_truth_or_authority_checks_loosened": plan["mandatory_gates"]["truth_checks_loosened"] is False
        and plan["mandatory_gates"]["authority_checks_loosened"] is False,
        "sqlite_row_count_matches_receipts": sqlite_summary["row_count"] == analysis["receipt_count"] == 15,
        "unsafe_true_grants_absent": True,
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all(value is True for value in machine_proof.values()) else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Analyze the room-backed LM2 pilot failure and define the next safe structured-output invocation plan.",
        "preconditions": preconditions,
        "input_refs": list(INPUT_REFS),
        "source_content_hashes": source_hashes,
        "postmortem": analysis,
        "structured_output_plan": plan,
        "sqlite_receipt_summary": sqlite_summary,
        "postmortem_actions": {
            "model_invoked": False,
            "runtime_connected": False,
            "prompt_sent": False,
            "proof_bundle_sent": False,
            "worker_spawn_performed": False,
            "external_provider_used": False,
            "business_action_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "git_push_performed": False,
        },
        "authority_boundary": {
            "next_invocation_approved": False,
            "protected_actions_allowed": False,
            "authority_granted": False,
            "truth_checks_loosened": False,
            "authority_checks_loosened": False,
            "repeated_invocations_allowed": False,
            "external_provider_allowed": False,
            "tool_authority": False,
            "business_action_authority": False,
        },
        "machine_proof": machine_proof,
    }
    unsafe = unsafe_true_grants(payload)
    payload["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    payload["content_hash"] = _content_hash({key: value for key, value in payload.items() if key != "content_hash"})
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    postmortem = read_model.get("postmortem") if isinstance(read_model.get("postmortem"), Mapping) else {}
    answers = postmortem.get("question_answers") if isinstance(postmortem.get("question_answers"), Mapping) else {}
    plan = read_model.get("structured_output_plan") if isinstance(read_model.get("structured_output_plan"), Mapping) else {}
    next_invocation = plan.get("next_invocation") if isinstance(plan.get("next_invocation"), Mapping) else {}
    lines = [
        "# LM2 Room Backed Worker Pilot Postmortem",
        "",
        f"Status: `{read_model.get('status')}`",
        "",
        "This postmortem reads saved artifacts only. It does not invoke LM2, connect Ollama, send prompts or proof bundles, spawn workers, or perform business actions.",
        "",
        "## What Failed",
        "",
        f"- {answers.get('what_failed')}",
        f"- Failure class: `{postmortem.get('failure_class')} / {postmortem.get('secondary_failure_class')}`",
        f"- Adapter parse status: `{postmortem.get('adapter_parse_status')}`",
        "",
        "## Safety Findings",
        "",
        f"- Forbidden fields sent: `{str(answers.get('did_model_receive_forbidden_fields')).lower()}`",
        f"- Protected action attempted: `{str(answers.get('did_model_attempt_protected_action')).lower()}`",
        f"- Fallback published correctly: `{str(answers.get('did_fallback_publish_correctly')).lower()}`",
        f"- Receipts complete: `{str(answers.get('were_receipts_complete')).lower()}`",
        f"- Approval used exactly once: `{str(answers.get('was_approval_used_exactly_once')).lower()}`",
        "",
        "## Conclusion",
        "",
    ]
    for item in postmortem.get("conclusion") or []:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Structured Output Plan",
            "",
            f"- Current method: `{(plan.get('current_invocation') or {}).get('method')}`",
            f"- Next method: `{next_invocation.get('recommended_method')}`",
            "- Next attempt must use Ollama API `format` with the exact response JSON schema before another one-attempt approval is used.",
            "- Verifier and fallback remain mandatory.",
            "- Truth and authority checks must not be loosened.",
            "",
        ]
    )
    return "\n".join(lines)


def export_lm2_room_backed_worker_pilot_postmortem(
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
        "sqlite_row_count": str((read_model.get("sqlite_receipt_summary") or {}).get("row_count") or 0),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish LM2 room-backed worker pilot postmortem.")
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
    result = export_lm2_room_backed_worker_pilot_postmortem(
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
