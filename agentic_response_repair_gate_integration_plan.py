"""Agentic Response + Repair + Gate Integration Plan V0.

Planning/read-model/wiki synthesis only. This module does not invoke LMs,
connect runtimes, spawn workers, mutate business state, or execute protected
actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Agentic Response Repair Gate Integration Plan.md")

SCHEMA_VERSION = "agentic_response_repair_gate_integration_plan_v0"
READ_MODEL_ID = "agentic_response_repair_gate_integration_plan"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "AGENTIC_RESPONSE_REPAIR_GATE_INTEGRATION_PLAN_READY"
NOT_READY_STATUS = "AGENTIC_RESPONSE_REPAIR_GATE_INTEGRATION_PLAN_NOT_READY"

REQUIRED_OUTPUT_SECTIONS = (
    "executive summary",
    "integrated chain",
    "deterministic vs agentic split",
    "self-heal flow",
    "gate calibration summary",
    "next build recommendation",
    "tests required before live LM",
    "risks",
    "final recommendation",
)

PRECONDITIONS = {
    "proof_to_response_lm_shadow_harness": {
        "filename": "proof_to_response_lm_shadow_status.json",
        "accepted_statuses": ["PROOF_TO_RESPONSE_LM_SHADOW_HARNESS_READY"],
    },
    "self_heal_repair_doctrine": {
        "filename": "self_heal_repair_doctrine.json",
        "accepted_statuses": ["SELF_HEAL_REPAIR_DOCTRINE_READY"],
    },
    "goldilocks_gate_calibration": {
        "filename": "goldilocks_gate_calibration.json",
        "accepted_statuses": ["GOLDILOCKS_GATE_CALIBRATION_READY"],
    },
    "proof_to_response_tdd_spec": {
        "filename": "proof_to_response_tdd_spec.json",
        "accepted_statuses": ["PROOF_TO_RESPONSE_TDD_SPEC_READY"],
    },
    "objective_advancement_controller_route": {
        "filename": "objective_advancement_protocol.json",
        "accepted_statuses": ["OBJECTIVE_ADVANCEMENT_CONTROLLER_ROUTE_READY", "OBJECTIVE_ADVANCEMENT_PROTOCOL_READY"],
    },
    "operator_controller_protocol": {
        "filename": "operator_controller_protocol.json",
        "accepted_statuses": ["OPERATOR_CONTROLLER_PROTOCOL_READY"],
    },
    "dynamic_card_packet_v1": {
        "filename": "dynamic_card_packet_latest.json",
        "accepted_statuses": ["DYNAMIC_CARD_PACKET_V1_READY", "DYNAMIC_CARD_PACKET_READY"],
    },
    "universal_receipt_envelope": {
        "filename": "universal_receipt_envelope_status.json",
        "accepted_statuses": ["UNIVERSAL_RECEIPT_ENVELOPE_READY"],
    },
}

INPUT_REFS = {
    "proof_to_response_lm_shadow_status": "generated/read_models/proof_to_response_lm_shadow_status.json",
    "proof_to_response_lm_shadow_contract": "generated/read_models/proof_to_response_lm_shadow_contract.json",
    "self_heal_repair_doctrine": "generated/read_models/self_heal_repair_doctrine.json",
    "goldilocks_gate_calibration": "generated/read_models/goldilocks_gate_calibration.json",
    "proof_to_response_tdd_spec": "generated/read_models/proof_to_response_tdd_spec.json",
    "objective_advancement_protocol": "generated/read_models/objective_advancement_protocol.json",
    "operator_controller_protocol": "generated/read_models/operator_controller_protocol.json",
    "harness_provider_selection_registry": "generated/read_models/harness_provider_selection_registry.json",
    "dynamic_card_packet_latest": "generated/read_models/dynamic_card_packet_latest.json",
    "universal_receipt_envelope_status": "generated/read_models/universal_receipt_envelope_status.json",
    "proof_meter_normalization": "generated/read_models/proof_meter_normalization.json",
    "operator_session_timeline": "generated/read_models/operator_session_timeline.json",
}

AUTHORITY_BOUNDARY = {
    "model_invocation_allowed": False,
    "external_provider_connect_allowed": False,
    "local_model_runtime_allowed": False,
    "worker_spawn_allowed": False,
    "worker_execution_allowed": False,
    "tool_execution_allowed": False,
    "business_action_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "ledger_posting_allowed": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "workbook_source_mutation_allowed": False,
    "pdf_export_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "protected_actions_allowed": False,
    "authority_grant_allowed": False,
    "memory_truth_promotion_allowed": False,
    "paid": False,
    "sent": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "model_invoked",
    "external_provider_connected",
    "local_model_runtime_connected",
    "worker_spawn_performed",
    "worker_execution_performed",
    "business_action_performed",
    "email_send_performed",
    "gmail_access_performed",
    "browser_access_performed",
    "coupa_access_performed",
    "coupa_submit_performed",
    "portal_submit_performed",
    "ledger_mutation_performed",
    "ledger_posting_performed",
    "paid_marking_performed",
    "workbook_mutation_performed",
    "workbook_source_mutation_performed",
    "pdf_export_performed",
    "git_push_performed",
    "merge_performed",
    "protected_action_performed",
    "authority_granted",
    "incoming_authority_granted_accepted",
}

DETERMINISTIC_ITEMS = [
    "truth",
    "receipts",
    "authority",
    "gate decisions",
    "proof refs",
    "lifecycle",
    "protected action blocks",
    "source hashes",
    "verification status",
]

AGENTIC_ITEMS = [
    "phrasing",
    "prioritization",
    "diagnosis",
    "repair proposal",
    "next-step explanation",
    "missing-proof explanation",
    "contextual helpfulness",
    "what can be done now reasoning",
]

BLOCKED_ACTIONS = [
    "email send",
    "Gmail/browser/Coupa access",
    "portal submit",
    "ledger mutation/posting",
    "paid marking",
    "workbook source mutation",
    "PDF export/send",
    "git push/merge",
    "worker spawn",
    "external provider call",
    "live model/runtime expansion",
]


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
    return rows


def _source_payloads(read_model_root: Path) -> dict[str, dict[str, Any]]:
    root = _rooted(read_model_root)
    payloads: dict[str, dict[str, Any]] = {}
    for ref, source_ref in INPUT_REFS.items():
        filename = source_ref.split("generated/read_models/", 1)[1]
        payloads[ref] = _load_json(root / filename)
    return payloads


def _repair_paths(self_heal: Mapping[str, Any]) -> list[dict[str, Any]]:
    paths: list[dict[str, Any]] = []
    for package in self_heal.get("repair_packages") or []:
        if not isinstance(package, Mapping):
            continue
        copy = package.get("dynamic_response_copy") if isinstance(package.get("dynamic_response_copy"), Mapping) else {}
        paths.append(
            {
                "repair_ref": str(package.get("repair_ref") or copy.get("repair_package_ref") or ""),
                "name_blocker": str(package.get("blocker_summary") or ""),
                "proof_refs": list(package.get("proof_refs") or []),
                "what_can_be_done_now": list(copy.get("what_i_can_do_now") or package.get("safe_internal_actions") or []),
                "what_cannot_be_done_yet": list(copy.get("what_i_cannot_do_yet") or package.get("forbidden_actions") or []),
                "smallest_operator_step": str(package.get("required_operator_action") or copy.get("required_operator_action") or ""),
                "stage_repair_package": str(copy.get("next_step") or package.get("next_step") or "Stage repair package"),
                "validation": list(package.get("validation_plan") or ["focused validation required before repair success claim"]),
                "receipt_required": str(package.get("receipt_requirement") or "validation_receipt_required"),
                "authority_boundary": {"protected_actions_allowed": False},
            }
        )
    return paths


def _gate_summary(goldilocks: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_ref": INPUT_REFS["goldilocks_gate_calibration"],
        "goldilocks_zone": goldilocks.get("goldilocks_zone") or {},
        "agents_may": [
            "inspect local proof",
            "draft",
            "stage",
            "patch code",
            "run safe tests",
            "prepare approval package",
            "prepare review packet",
            "explain next step",
        ],
        "agents_may_not": [
            "execute protected external action",
            "invent truth",
            "grant authority",
            "bypass Guardian",
            "promote memory to truth",
            "submit/send/post/mark paid/push",
        ],
        "recommended_gate_level_for_next_build": "safe_internal_work for local repo integration; stage/prepare_approval for business surfaces",
    }


def build_plan(source_payloads: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    self_heal = source_payloads.get("self_heal_repair_doctrine") or {}
    goldilocks = source_payloads.get("goldilocks_gate_calibration") or {}
    shadow_status = source_payloads.get("proof_to_response_lm_shadow_status") or {}
    shadow_contract = source_payloads.get("proof_to_response_lm_shadow_contract") or {}
    return {
        "next_safe_runtime_build": {
            "choice": "verifier-only response harness",
            "why": "It puts proof bundles and deterministic verification in the response path before any live LM/runtime expansion, so Mission Control can receive concise agent text while truth and authority stay deterministic.",
            "not_chosen_yet": [
                "local LM shadow response pilot",
                "self-heal repair package route",
                "Goldilocks gate-level integration as live authority",
            ],
        },
        "integrated_chain": [
            "controller event or objective advance",
            "bounded proof bundle from receipts/cards/gates/meters/session timeline",
            "draft response from deterministic oracle now; future LM phrasing later",
            "deterministic verifier blocks unsupported facts, authority, protected promises, jargon, and overlong text",
            "self-heal repair proposal when blocker is repairable",
            "Goldilocks gate level determines readback, plan, stage, safe internal work, or approval preparation",
            "Mission Control renders concise agent response first, one control, meters, and collapsed details",
            "receipt records response/verifier/repair outcome",
        ],
        "deterministic_vs_agentic_split": {
            "stays_deterministic": list(DETERMINISTIC_ITEMS),
            "becomes_agentic": list(AGENTIC_ITEMS),
        },
        "blocked_actions": list(BLOCKED_ACTIONS),
        "self_heal_flow": {
            "doctrine": "no_black_box_repairs",
            "steps": [
                "name blocker",
                "cite proof",
                "state what can be done now",
                "state what cannot be done yet",
                "ask for the smallest manual operator step if required",
                "stage repair package",
                "validate",
                "record receipt",
            ],
            "repair_paths": _repair_paths(self_heal),
        },
        "gate_calibration_summary": _gate_summary(goldilocks),
        "mac_app_surface": {
            "primary_surface": "concise agent response first",
            "one_next_control": True,
            "proof_meters": True,
            "details_collapsed": True,
            "dynamic_card_role": "support/display",
            "card_deck_primary_response": False,
        },
        "first_implementation_sequence": [
            {
                "step": "Integrate proof bundle builder into controller responses",
                "validation_required": ["bundle redaction", "proof refs present", "no verification tokens"],
            },
            {
                "step": "Run verifier-only response harness for deterministic drafts",
                "validation_required": ["publish/block tests", "concision", "allowed controls"],
            },
            {
                "step": "Render response-first Mac payload beside existing dynamic card packet",
                "validation_required": ["one next control", "proof meters visible", "details collapsed"],
            },
            {
                "step": "Attach self-heal repair package proposals to verified blocker responses",
                "validation_required": ["blocker named", "proof cited", "repair receipt requirement present"],
            },
            {
                "step": "Calibrate gate labels and regression tests before any live LM pilot",
                "validation_required": ["Goldilocks gate tests", "unsafe true-grant scan", "no live runtime expansion"],
            },
        ],
        "tests_required_before_live_lm": [
            "proof bundle redaction tests",
            "verifier publish/block tests",
            "self-heal no-black-box repair tests",
            "Goldilocks gate regression tests",
            "Mac response-first rendering smoke",
            "unsafe true-grant scan",
            "receipt and source-hash grounding tests",
            "protected action negative tests",
        ],
        "risks": [
            "A polished response can sound like truth unless every factual claim remains verifier-backed.",
            "Repair proposals can be mistaken for repair success unless validation and receipts are visible.",
            "Gate labels that are too strict make agents useless; labels that are too loose imply protected authority.",
            "Mac UI may regress into card-deck-first rendering unless response-first tests exist.",
            "Live LM/runtime expansion before verifier parity would create truth and authority ambiguity.",
        ],
        "source_rollup": {
            "shadow_run_count": shadow_status.get("shadow_run_count"),
            "shadow_all_verified": (shadow_status.get("machine_proof") or {}).get("all_shadow_drafts_verified"),
            "shadow_verifier_contract": (shadow_contract.get("contract") or {}),
            "self_heal_repair_package_count": len(self_heal.get("repair_packages") or []),
            "goldilocks_gate_level_count": goldilocks.get("gate_level_count"),
        },
    }


def _sections(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "executive summary": {
            "summary": "The next build should integrate a verifier-only response harness. It lets OpenClaw speak in concise agent text while receipts, proof bundles, gates, and verifier outcomes remain the source of truth.",
            "next_safe_build": plan["next_safe_runtime_build"]["choice"],
        },
        "integrated chain": plan["integrated_chain"],
        "deterministic vs agentic split": plan["deterministic_vs_agentic_split"],
        "self-heal flow": plan["self_heal_flow"],
        "gate calibration summary": plan["gate_calibration_summary"],
        "next build recommendation": plan["next_safe_runtime_build"],
        "tests required before live LM": plan["tests_required_before_live_lm"],
        "risks": plan["risks"],
        "final recommendation": {
            "recommendation": "Ship the verifier-only response harness before local LM shadow response pilot or repair-route execution.",
            "reason": "It preserves deterministic truth and authority while making the operator experience response-first and agentic.",
        },
    }


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    source_payloads = _source_payloads(read_model_root)
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    plan = build_plan(source_payloads)
    sections = _sections(plan)
    missing_sections = [section for section in REQUIRED_OUTPUT_SECTIONS if not sections.get(section)]
    source_hashes = {ref: _content_hash(payload) for ref, payload in source_payloads.items()}
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready and not missing_sections else NOT_READY_STATUS,
        "generated_at": generated_at,
        "source_refs": dict(INPUT_REFS),
        "source_content_hashes": source_hashes,
        "preconditions": preconditions,
        "sections": sections,
        "required_output_sections": list(REQUIRED_OUTPUT_SECTIONS),
        "next_safe_runtime_build": plan["next_safe_runtime_build"],
        "integrated_chain": plan["integrated_chain"],
        "deterministic_vs_agentic_split": plan["deterministic_vs_agentic_split"],
        "blocked_actions": plan["blocked_actions"],
        "self_heal_flow": plan["self_heal_flow"],
        "gate_calibration_summary": plan["gate_calibration_summary"],
        "mac_app_surface": plan["mac_app_surface"],
        "first_implementation_sequence": plan["first_implementation_sequence"],
        "tests_required_before_live_lm": plan["tests_required_before_live_lm"],
        "risks": plan["risks"],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": {
            "external_llm_invoked": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "coupa_submit_performed": False,
            "portal_submit_performed": False,
            "ledger_mutation_performed": False,
            "ledger_posting_performed": False,
            "paid_marking_performed": False,
            "workbook_mutation_performed": False,
            "workbook_source_mutation_performed": False,
            "pdf_export_performed": False,
            "git_push_performed": False,
            "merge_performed": False,
            "business_action_performed": False,
        },
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "missing_required_sections": missing_sections,
            "selected_next_build_is_safe": plan["next_safe_runtime_build"]["choice"] == "verifier-only response harness",
            "first_sequence_step_count": len(plan["first_implementation_sequence"]),
            "self_heal_paths_have_receipts": all(path.get("receipt_required") for path in plan["self_heal_flow"]["repair_paths"]),
            "mac_response_first": plan["mac_app_surface"]["primary_surface"] == "concise agent response first",
            "blocked_actions_present": all(action in plan["blocked_actions"] for action in BLOCKED_ACTIONS),
            "business_action_performed": False,
            "email_send_performed": False,
            "coupa_submit_performed": False,
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
            "worker_spawn_performed": False,
            "external_llm_invoked": False,
            "local_model_runtime_connected": False,
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Agentic Response Repair Gate Integration Plan",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "This plan integrates the proof-to-response LM shadow harness, self-heal repair doctrine, and Goldilocks gate calibration into the next safe OpenClaw runtime build.",
        "",
    ]
    sections = read_model.get("sections") if isinstance(read_model.get("sections"), Mapping) else {}
    for section in REQUIRED_OUTPUT_SECTIONS:
        title = " ".join(word.capitalize() for word in section.split())
        lines.extend([f"## {title}", ""])
        value = sections.get(section)
        if isinstance(value, str):
            lines.extend([value, ""])
        elif isinstance(value, list):
            for item in value:
                lines.append(f"- {item}")
            lines.append("")
        elif isinstance(value, Mapping):
            for key, item in value.items():
                label = str(key).replace("_", " ")
                if isinstance(item, list):
                    lines.append(f"- {label}: " + ", ".join(str(x) for x in item))
                elif isinstance(item, Mapping):
                    lines.append(f"- {label}: " + json.dumps(item, sort_keys=True))
                else:
                    lines.append(f"- {label}: {item}")
            lines.append("")
    proof = read_model.get("machine_proof") if isinstance(read_model.get("machine_proof"), Mapping) else {}
    lines.extend(
        [
            "## Proof",
            "",
            f"- Preconditions ready: `{str(proof.get('preconditions_ready')).lower()}`",
            f"- Unsafe true grants absent: `{str(proof.get('unsafe_true_grants_absent')).lower()}`",
            f"- First sequence step count: `{proof.get('first_sequence_step_count')}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_agentic_response_repair_gate_integration_plan(
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
    export_path = export_root / JSON_EXPORT_NAME
    _write_json(export_path, read_model)

    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge = bridge_export_root / JSON_EXPORT_NAME
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
        "next_safe_runtime_build": str(read_model["next_safe_runtime_build"]["choice"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Agentic Response Repair Gate Integration Plan V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_agentic_response_repair_gate_integration_plan(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
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
