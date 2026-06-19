"""Niles Stage 1 schema/contract readiness v0.

Composes the existing Niles album boundary, metadata intake packet, review
packet, and matrix review into a single Stage 1 contract. This is a deterministic
read-model only; it does not inspect private music content, call models, run
Repo B, calibrate taste, release music, send anything, or grant runtime/tool
authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import niles_album_evidence_intake_boundary as evidence_boundary
import niles_album_matrix_review as matrix_review
import niles_album_metadata_intake_packet as metadata_packet
import niles_album_review_packet as review_packet


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "niles_stage1_contract_v0"
JSON_EXPORT_NAME = "niles_stage1_contract.json"
OPERATOR_EXPORT_NAME = "niles_stage1_contract_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

NO_AUTHORITY_FLAGS = {
    "stage_1_contract_only": True,
    "schema_contracts_ready": True,
    "metadata_only": True,
    "read_model_only": True,
    "taste_calibration_included": False,
    "master_taste_calibration_required_later": True,
    "real_album_metadata_recorded": False,
    "album_state_confirmed": False,
    "raw_audio_ingest_allowed": False,
    "daw_session_content_ingest_allowed": False,
    "broad_private_drive_scan_allowed": False,
    "daw_automation_allowed": False,
    "audio_file_mutation_allowed": False,
    "finder_file_operation_allowed": False,
    "repo_b_authority_allowed": False,
    "release_or_publish_authority_added": False,
    "runtime_authority_added": False,
    "tool_execution_authority_added": False,
    "model_execution_authority_added": False,
    "send_or_submit_authority_added": False,
    "approval_authority_added": False,
    "money_or_payment_authority_added": False,
    "mission_control_app_changed": False,
}

BLOCKED_BOUNDARIES = (
    "raw_audio",
    "daw_session_contents",
    "stems_mixes_masters",
    "broad_folder_scans",
    "private_drive_crawl",
    "audio_or_session_file_mutation",
    "logic_or_ableton_automation",
    "repo_b_runtime_execution",
    "model_or_tool_runtime_execution",
    "external_send_or_submit",
    "release_or_publish_action",
    "money_or_payment_action",
)

EXISTING_CONTRACT_SPECS = (
    {
        "source_id": "niles_album_evidence_intake_boundary",
        "source_path": "generated/read_models/niles_album_evidence_intake_boundary.json",
        "module_path": "niles_album_evidence_intake_boundary.py",
        "schema_version": evidence_boundary.SCHEMA_VERSION,
        "role": "metadata-only evidence boundary and forbidden input contract",
    },
    {
        "source_id": "niles_album_metadata_intake_packet",
        "source_path": "generated/read_models/niles_album_metadata_intake_packet.json",
        "module_path": "niles_album_metadata_intake_packet.py",
        "schema_version": metadata_packet.SCHEMA_VERSION,
        "role": "operator-facing metadata placeholder packet",
    },
    {
        "source_id": "niles_album_review_packet",
        "source_path": "generated/read_models/niles_album_review_packet.json",
        "module_path": "niles_album_review_packet.py",
        "schema_version": review_packet.SCHEMA_VERSION,
        "role": "review-only packet from governed evidence",
    },
    {
        "source_id": "niles_album_matrix_review",
        "source_path": "generated/read_models/niles_album_matrix_review.json",
        "module_path": "niles_album_matrix_review.py",
        "schema_version": matrix_review.SCHEMA_VERSION,
        "role": "metadata-only album matrix review read-model",
    },
)

STAGE_GATES = (
    {
        "stage_id": "stage_1_schema_contracts",
        "stage_label": "Stage 1: schemas and contracts",
        "status": "ready",
        "owner": "codex_builder",
        "allowed_now": True,
        "required_evidence": [
            "Niles evidence intake boundary",
            "Niles metadata intake packet",
            "Niles review packet",
            "Niles matrix review",
        ],
        "authority": "read_model_contract_only",
    },
    {
        "stage_id": "stage_2_operator_metadata_fill",
        "stage_label": "Stage 2: operator metadata fill",
        "status": "future_operator_input_needed",
        "owner": "operator",
        "allowed_now": False,
        "required_evidence": ["explicit governed operator metadata labels"],
        "authority": "operator_metadata_only_no_raw_content",
    },
    {
        "stage_id": "stage_3_review_matrix",
        "stage_label": "Stage 3: review matrix from governed metadata",
        "status": "future_ready_after_stage_2",
        "owner": "niles_review_lane",
        "allowed_now": False,
        "required_evidence": ["Stage 2 governed metadata read-model"],
        "authority": "review_only_no_truth_promotion",
    },
    {
        "stage_id": "stage_4_taste_calibration_master_only",
        "stage_label": "Stage 4: taste calibration",
        "status": "blocked_until_master_calibration",
        "owner": "master",
        "allowed_now": False,
        "required_evidence": ["master taste calibration packet"],
        "authority": "master_only_no_runtime_or_release_authority",
    },
    {
        "stage_id": "stage_5_release_publish_future_gate",
        "stage_label": "Stage 5: release or publish",
        "status": "blocked_future_gate",
        "owner": "master_and_operator",
        "allowed_now": False,
        "required_evidence": ["future explicit release/publish authorization"],
        "authority": "no_release_or_publish_authority_added",
    },
)


@dataclass(frozen=True)
class NilesStage1TransitionDecision:
    stage_id: str
    decision: str
    allowed: bool
    reason: str
    authority_added: bool


@dataclass(frozen=True)
class NilesStage1ContractResult:
    schema_version: str
    contract_status: str
    json_path: str
    operator_path: str
    source_contract_count: int
    missing_source_contract_count: int
    blocked_boundary_count: int
    stage_1_ready: bool
    taste_calibration_included: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool
    release_or_publish_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _source_contract_status(repo_root: str | Path, spec: dict[str, str]) -> dict[str, Any]:
    root = Path(repo_root)
    read_model_path = root / spec["source_path"]
    module_path = root / spec["module_path"]
    return {
        **spec,
        "read_model_present": read_model_path.exists(),
        "module_present": module_path.exists(),
        "truth_status": "contract_evidence_not_album_truth",
        "authority_status": "read_model_only_no_runtime_authority",
        "promoted_to_album_truth": False,
    }


def _content_hash(payload: dict[str, Any]) -> str:
    proof_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"generated_at", "machine_proof"}
    }
    return hashlib.sha256(stable_json(proof_payload).encode("utf-8")).hexdigest()


def evaluate_niles_stage1_transition(
    stage_id: str,
    *,
    source_contracts_present: bool = True,
    master_taste_calibration_present: bool = False,
    release_authority_requested: bool = False,
    runtime_authority_requested: bool = False,
    external_send_requested: bool = False,
) -> NilesStage1TransitionDecision:
    if runtime_authority_requested:
        return NilesStage1TransitionDecision(
            stage_id=stage_id,
            decision="blocked_runtime_authority_request",
            allowed=False,
            reason="Niles Stage 1 is a read-model contract and grants no runtime/tool/model authority.",
            authority_added=False,
        )
    if external_send_requested:
        return NilesStage1TransitionDecision(
            stage_id=stage_id,
            decision="blocked_external_send_request",
            allowed=False,
            reason="SEND_HOLD remains absolute; Stage 1 grants no external send/submit authority.",
            authority_added=False,
        )
    if release_authority_requested:
        return NilesStage1TransitionDecision(
            stage_id=stage_id,
            decision="blocked_release_or_publish_request",
            allowed=False,
            reason="Release/publish is a future explicit gate, not part of Stage 1.",
            authority_added=False,
        )
    if stage_id == "stage_1_schema_contracts":
        if source_contracts_present:
            return NilesStage1TransitionDecision(
                stage_id=stage_id,
                decision="ready_schema_contracts_only",
                allowed=True,
                reason="All existing Niles schema/contract read-models are present.",
                authority_added=False,
            )
        return NilesStage1TransitionDecision(
            stage_id=stage_id,
            decision="blocked_missing_source_contracts",
            allowed=False,
            reason="Stage 1 needs all four existing Niles source contracts present.",
            authority_added=False,
        )
    if stage_id == "stage_4_taste_calibration_master_only":
        return NilesStage1TransitionDecision(
            stage_id=stage_id,
            decision="held_for_master_taste_calibration"
            if master_taste_calibration_present
            else "blocked_missing_master_taste_calibration",
            allowed=False,
            reason="Taste calibration belongs to the master later; this Stage 1 contract only records the gate.",
            authority_added=False,
        )
    if stage_id == "stage_5_release_publish_future_gate":
        return NilesStage1TransitionDecision(
            stage_id=stage_id,
            decision="blocked_future_release_publish_gate",
            allowed=False,
            reason="Release/publish requires future explicit authorization outside this contract.",
            authority_added=False,
        )
    if stage_id in {"stage_2_operator_metadata_fill", "stage_3_review_matrix"}:
        return NilesStage1TransitionDecision(
            stage_id=stage_id,
            decision="future_stage_not_started",
            allowed=False,
            reason="This contract only completes Stage 1 and names the future gate.",
            authority_added=False,
        )
    return NilesStage1TransitionDecision(
        stage_id=stage_id,
        decision="unknown_stage_fail_closed",
        allowed=False,
        reason="Unknown Niles stage identifiers fail closed.",
        authority_added=False,
    )


def build_niles_stage1_contract(*, repo_root: str | Path = ROOT, generated_at: str | None = None) -> dict[str, Any]:
    source_contracts = [_source_contract_status(repo_root, spec) for spec in EXISTING_CONTRACT_SPECS]
    missing_source_contracts = [
        source
        for source in source_contracts
        if not source["read_model_present"] or not source["module_present"]
    ]
    all_source_contracts_present = not missing_source_contracts
    stage_1_decision = evaluate_niles_stage1_transition(
        "stage_1_schema_contracts",
        source_contracts_present=all_source_contracts_present,
    )
    stage_4_decision = evaluate_niles_stage1_transition("stage_4_taste_calibration_master_only")
    stage_5_decision = evaluate_niles_stage1_transition(
        "stage_5_release_publish_future_gate",
        release_authority_requested=True,
    )
    contract_status = (
        "stage_1_schema_contracts_ready_metadata_only"
        if stage_1_decision.allowed
        else "blocked_missing_stage_1_source_contracts"
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "contract_id": "niles_stage1_contract",
        "workflow_domain": "music_art",
        "workflow_name": "Niles album progress review",
        "contract_status": contract_status,
        "stage_1_ready": stage_1_decision.allowed,
        "stage_1_scope": {
            "summary": "schemas/contracts only",
            "allowed_now": [
                "read existing Niles generated read-models",
                "show Stage 1 readiness",
                "route future operator metadata fill to governed metadata-only packet",
            ],
            "not_in_scope": [
                "taste calibration",
                "raw audio or DAW session inspection",
                "broad private drive scans",
                "audio/session mutation",
                "release or publish actions",
                "external sends or submits",
                "runtime/tool/model authority",
            ],
        },
        "existing_contracts": source_contracts,
        "stage_gates": list(STAGE_GATES),
        "stage_decisions": {
            "stage_1_schema_contracts": stage_1_decision.__dict__,
            "stage_4_taste_calibration_master_only": stage_4_decision.__dict__,
            "stage_5_release_publish_future_gate": stage_5_decision.__dict__,
        },
        "master_taste_calibration": {
            "included_now": False,
            "required_later": True,
            "owner": "master",
            "status": "blocked_until_master_calibration",
            "stage_1_claims_taste_ready": False,
            "stage_1_claims_release_ready": False,
        },
        "blocked_boundaries": list(BLOCKED_BOUNDARIES),
        "forbidden_boundaries": {
            "raw_audio_ingest": "forbidden",
            "daw_session_content_ingest": "forbidden",
            "broad_private_drive_scan": "forbidden",
            "audio_or_session_file_mutation": "forbidden",
            "logic_or_ableton_automation": "forbidden",
            "repo_b_runtime_execution": "forbidden",
            "model_or_tool_runtime_execution": "forbidden",
            "external_send_or_submit": "forbidden",
            "release_or_publish_action": "forbidden",
            "money_or_payment_action": "forbidden",
        },
        "operator_next_safe_move": (
            "Use the existing Niles metadata intake packet to supply governed metadata labels later; "
            "do not provide raw audio, DAW/session contents, or private-drive crawl requests."
        ),
        "receipt_proof_status": {
            "read_model_written": True,
            "operator_packet_written": True,
            "external_action_taken": False,
            "taste_calibration_performed": False,
            "release_or_publish_action_taken": False,
            "runtime_authority_added": False,
            "send_or_submit_authority_added": False,
            "mission_control_app_changed": False,
        },
        "canonical_generated_read_model_expected_files": [
            f"generated/read_models/{JSON_EXPORT_NAME}",
            f"generated/read_models/{OPERATOR_EXPORT_NAME}",
        ],
        "authority_boundary": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }
    payload["machine_proof"] = {
        "content_hash_sha256": _content_hash(payload),
        "source_contract_count": len(source_contracts),
        "missing_source_contract_count": len(missing_source_contracts),
        "blocked_boundary_count": len(BLOCKED_BOUNDARIES),
    }
    return payload


def format_niles_stage1_contract(payload: dict[str, Any]) -> str:
    lines = [
        "# Niles Stage 1 Contract v0",
        "",
        "Status:",
        f"- Contract status: `{payload['contract_status']}`.",
        f"- Stage 1 ready: `{str(payload['stage_1_ready']).lower()}`.",
        "- Scope: schemas/contracts only.",
        "- Metadata only: `true`.",
        "- Taste calibration included: `false`.",
        "- Master taste calibration required later: `true`.",
        "- Raw audio ingest allowed: `false`.",
        "- DAW session content ingest allowed: `false`.",
        "- Broad private drive scan allowed: `false`.",
        "- Audio/session mutation allowed: `false`.",
        "- Release/publish authority added: `false`.",
        "- Runtime/tool/model authority added: `false`.",
        "- Send/submit authority added: `false`.",
        "- Money/payment authority added: `false`.",
        "",
        "## Existing Contracts",
    ]
    for source in payload["existing_contracts"]:
        lines.append(
            f"- `{source['source_id']}` schema=`{source['schema_version']}` "
            f"module_present=`{str(source['module_present']).lower()}` "
            f"read_model_present=`{str(source['read_model_present']).lower()}` "
            f"role={source['role']}."
        )
    lines.extend(["", "## Stage Gates"])
    for gate in payload["stage_gates"]:
        lines.append(
            f"- `{gate['stage_id']}` status=`{gate['status']}` owner=`{gate['owner']}` "
            f"allowed_now=`{str(gate['allowed_now']).lower()}`."
        )
    lines.extend(
        [
            "",
            "## Master Taste Calibration",
            "- Taste calibration is not performed in Stage 1.",
            "- The master owns taste calibration later before any taste-sensitive or release-sensitive claims.",
            "",
            "## Blocked Boundaries",
        ]
    )
    for boundary in payload["blocked_boundaries"]:
        lines.append(f"- `{boundary}` remains blocked.")
    lines.extend(
        [
            "",
            "## Next Safe Move",
            f"- {payload['operator_next_safe_move']}",
            "",
            "## Machine Proof",
            f"- Content hash: `{payload['machine_proof']['content_hash_sha256']}`.",
            f"- Source contracts: `{payload['machine_proof']['source_contract_count']}`.",
            f"- Missing source contracts: `{payload['machine_proof']['missing_source_contract_count']}`.",
            f"- Blocked boundaries: `{payload['machine_proof']['blocked_boundary_count']}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_niles_stage1_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> NilesStage1ContractResult:
    root = Path(repo_root)
    out_dir = root / export_root
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_niles_stage1_contract(repo_root=root, generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_niles_stage1_contract(payload), encoding="utf-8")
    return NilesStage1ContractResult(
        schema_version=SCHEMA_VERSION,
        contract_status=payload["contract_status"],
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        source_contract_count=payload["machine_proof"]["source_contract_count"],
        missing_source_contract_count=payload["machine_proof"]["missing_source_contract_count"],
        blocked_boundary_count=payload["machine_proof"]["blocked_boundary_count"],
        stage_1_ready=payload["stage_1_ready"],
        taste_calibration_included=payload["taste_calibration_included"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
        release_or_publish_authority_added=payload["release_or_publish_authority_added"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Niles Stage 1 schema/contract readiness.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root to read generated evidence from.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Read-model export directory.")
    parser.add_argument("--format", choices=("json", "operator"), default="operator", help="Print result format.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    result = export_niles_stage1_contract(repo_root=args.repo_root, export_root=args.export_root)
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(
            f"Niles Stage 1 contract exported: {result.json_path} and {result.operator_path} "
            f"({result.contract_status}; source_contracts={result.source_contract_count})."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
