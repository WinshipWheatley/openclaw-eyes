"""Niles Stage 1 schema/contract read-model.

This contract publishes the first durable schema layer for Niles music work:
operator interview memory, practice ledger events, adaptive practice plans,
Logic note-update requests, Maestro handoff, and a separate future studio
control authority envelope. It is schema only. It does not interview the
operator, write ledgers, open Logic, scan private media, mutate DAW files,
send externally, call models/tools, or enable studio control.
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


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "niles_stage1_schema_contract_v0"
READ_MODEL_ID = "niles_stage1_schema_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "template_ready_schema_only_no_live_authority"

INSTRUMENTS = ("guitar", "piano", "drums", "voice", "tenor_sax")

REQUIRED_SCHEMA_FIELDS = (
    "schema_id",
    "stage",
    "purpose",
    "required_fields",
    "allowed_sources",
    "blocked_sources",
    "authority_boundary",
    "validation_rules",
    "next_consumer",
)

REFERENCE_DOCS = {
    "niles_music_subsystem_spec": "../orchestration/specs/niles-music/NILES-MUSIC-SUBSYSTEM.md",
    "paul_gilbert_progression": "../orchestration/specs/niles-music/PAUL_GILBERT_PROGRESSION.md",
    "lane_g_shadow_request_contract": "../orchestration/lane_g_architecture/contracts/niles_music_production_request_contract.json",
    "producer_rubric": "config/producer/producer_rubric.yaml",
    "producer_reference_map": "config/producer/producer_reference_map.yaml",
    "niles_album_metadata_intake_packet": "generated/read_models/niles_album_metadata_intake_packet.json",
}

NO_AUTHORITY_FLAGS = {
    "schema_only": True,
    "template_only": True,
    "runtime_authority_added": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "telegram_send_allowed": False,
    "external_send_allowed": False,
    "send_hold_bypass_allowed": False,
    "money_authority_allowed": False,
    "legal_discovery_allowed": False,
    "credential_access_allowed": False,
    "live_interview_allowed": False,
    "hidden_memory_capture_allowed": False,
    "practice_ledger_write_allowed": False,
    "logic_or_ableton_open_allowed": False,
    "daw_launch_allowed": False,
    "daw_session_read_allowed": False,
    "daw_automation_allowed": False,
    "session_media_mutation_allowed": False,
    "raw_audio_ingest_allowed": False,
    "broad_private_drive_scan_allowed": False,
    "studio_control_enabled": False,
    "audio_io_routing_enabled": False,
    "hardware_control_allowed": False,
    "mission_control_app_changed": False,
    "taste_calibration_complete": False,
}


@dataclass(frozen=True)
class NilesStage1SchemaExportResult:
    schema_version: str
    contract_status: str
    json_path: str
    operator_path: str
    schema_count: int
    stage_gate_count: int
    runtime_authority_added: bool
    studio_control_enabled: bool
    practice_ledger_write_allowed: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _contract_boundary(*, ledger_write: bool = False) -> dict[str, bool]:
    boundary = dict(NO_AUTHORITY_FLAGS)
    boundary["practice_ledger_write_allowed"] = ledger_write
    return boundary


def _schema_contracts() -> list[dict[str, Any]]:
    return [
        {
            "schema_id": "niles_operator_interview_memory_v0",
            "stage": "stage1_schema",
            "purpose": "Capture operator-supplied music profile data later, without hidden memory or inference.",
            "required_fields": [
                "operator_ref",
                "instrument_profiles",
                "gear_inventory_refs",
                "taste_profile_refs",
                "energy_constraints",
                "practice_preferences",
                "unknowns",
                "consent_and_scope_receipts",
            ],
            "instrument_profile_required_fields": [
                "instrument",
                "current_strengths",
                "known_weaknesses",
                "target_voice",
                "practice_constraints",
                "operator_supplied",
                "confidence",
            ],
            "covered_instruments": list(INSTRUMENTS),
            "allowed_sources": [
                "operator-supplied interview answers",
                "config/producer/producer_rubric.yaml",
                "config/producer/producer_reference_map.yaml",
                "explicit future protected refs approved by Guardian",
            ],
            "blocked_sources": [
                "hidden memory",
                "broad private media scan",
                "raw lyrics or raw audio without a later protected path",
                "credential or account data",
            ],
            "authority_boundary": _contract_boundary(),
            "validation_rules": [
                "unknowns must remain explicit",
                "operator-supplied facts are evidence, not final truth",
                "taste profile refs do not complete taste calibration",
                "tenor_sax goal may be recorded as operator intent, not proof of skill",
            ],
            "next_consumer": "future operator_interview memory writer after approval",
        },
        {
            "schema_id": "niles_practice_ledger_event_v0",
            "stage": "stage1_schema",
            "purpose": "Define a future feedback event shape for short daily practice and progression adjustment.",
            "required_fields": [
                "event_id",
                "operator_ref",
                "session_ref",
                "instrument",
                "exercise_ref",
                "bpm",
                "clean_execution_rate",
                "fatigue",
                "operator_feedback",
                "regression_rule_result",
                "next_plan_ref",
                "created_at",
            ],
            "allowed_sources": [
                "operator post-practice feedback",
                "future metronome/timer receipt",
                "specs/niles-music/PAUL_GILBERT_PROGRESSION.md",
            ],
            "blocked_sources": [
                "automatic raw audio scoring",
                "DAW session content",
                "private file timestamps as practice proof",
            ],
            "authority_boundary": _contract_boundary(),
            "validation_rules": [
                "instrument must be one of covered_instruments",
                "clean_execution_rate must be null or 0..1",
                "fatigue must be null, low, medium, or high",
                "ledger writes require a later authority envelope",
            ],
            "next_consumer": "future shared progression_tracker module",
        },
        {
            "schema_id": "niles_adaptive_practice_plan_v0",
            "stage": "stage1_schema",
            "purpose": "Define a short daily routine plan that can knit multiple instruments together.",
            "required_fields": [
                "plan_id",
                "operator_ref",
                "horizon",
                "instrument_mix",
                "daily_blocks",
                "progression_refs",
                "expected_feedback_prompts",
                "taste_notes_ref",
                "stop_conditions",
            ],
            "allowed_sources": [
                "niles_operator_interview_memory_v0",
                "niles_practice_ledger_event_v0",
                "config/producer/producer_rubric.yaml",
                "specs/niles-music/PAUL_GILBERT_PROGRESSION.md",
            ],
            "blocked_sources": [
                "model-generated taste as final truth",
                "unapproved calendar/health surveillance",
                "unapproved audio analysis",
            ],
            "authority_boundary": _contract_boundary(),
            "validation_rules": [
                "plan is advisory until approved",
                "daily_blocks must be short and finite",
                "stop_conditions must include fatigue or operator stop",
                "generic progression fields must not be Niles-only",
            ],
            "next_consumer": "future shared adaptive coach planner",
        },
        {
            "schema_id": "niles_logic_note_update_request_v0",
            "stage": "stage1_schema",
            "purpose": "Define a future dry-run request for writing practice notes into an existing Logic session.",
            "required_fields": [
                "request_id",
                "target_session_ref_label",
                "note_payload_markdown",
                "proof_refs",
                "dry_run_only",
                "required_operator_approval",
                "no_daw_launch",
                "no_session_media_mutation",
                "receipt_requirements",
            ],
            "allowed_sources": [
                "operator-approved practice plan",
                "existing stable session label",
                "future file-write receipt",
            ],
            "blocked_sources": [
                "opening Logic during Stage 1",
                "driving Logic UI",
                "mutating session media, stems, bounces, or artwork",
                "broad scanning Niles folders",
            ],
            "authority_boundary": _contract_boundary(),
            "validation_rules": [
                "dry_run_only must be true in Stage 1",
                "no_daw_launch must be true",
                "target_session_ref_label is a label, not permission to open the file",
                "receipt requirements must include before/after proof before any later write lane",
            ],
            "next_consumer": "future Mac local action bridge writeback lane after approval",
        },
        {
            "schema_id": "niles_studio_control_authority_envelope_v0",
            "stage": "stage1_schema",
            "purpose": "Keep DAW/MIDI/OSC/X32 control separate, gated, and disabled by default.",
            "required_fields": [
                "control_request_id",
                "device_or_daw_target",
                "action_kind",
                "operator_approval_receipt_ref",
                "preflight_state_ref",
                "rollback_plan_ref",
                "audit_log_ref",
                "denied_when_unapproved",
            ],
            "allowed_sources": [
                "future explicit operator control request",
                "future Guardian-approved hardware capability registry",
                "future preflight receipts",
            ],
            "blocked_sources": [
                "autonomous live control",
                "implicit authority from Niles persona",
                "ungated X32/DAW/MIDI/OSC action",
                "record-arm or gain changes without approval",
            ],
            "authority_boundary": _contract_boundary(),
            "validation_rules": [
                "studio_control_enabled must remain false",
                "hardware_control_allowed must remain false",
                "denied_when_unapproved must be true",
                "Niles persona never grants control authority",
            ],
            "next_consumer": "future Guardian-approved studio control lane",
        },
        {
            "schema_id": "maestro_to_niles_handoff_packet_v0",
            "stage": "stage1_schema",
            "purpose": "Define how Maestro can route music/art context to Niles without activating live tools.",
            "required_fields": [
                "conversation_ref",
                "route_reason",
                "operator_visible_summary",
                "current_task",
                "schema_refs",
                "blocked_authority",
                "handoff_receipt_ref",
            ],
            "allowed_sources": [
                "operator-visible conversation summary",
                "deterministic read-model refs",
                "approved package preview refs",
            ],
            "blocked_sources": [
                "raw hidden conversation bodies",
                "tool outputs without receipts",
                "agent self-assigned authority",
            ],
            "authority_boundary": _contract_boundary(),
            "validation_rules": [
                "handoff is routing metadata only",
                "Niles cannot activate tools from a handoff",
                "blocked_authority must include send, DAW control, and ledger write",
            ],
            "next_consumer": "future Maestro routing layer",
        },
    ]


def _stage_gates() -> list[dict[str, Any]]:
    return [
        {
            "gate_id": "stage1_schema_contracts_only",
            "status": "ready",
            "allows": ["read-model publication", "operator review", "future implementation planning"],
            "blocks": ["live interview", "ledger write", "Logic mutation", "studio control"],
        },
        {
            "gate_id": "stage2_interview_memory_writer",
            "status": "future_blocked",
            "requires": ["operator approval", "privacy boundary", "receipt logging"],
        },
        {
            "gate_id": "stage3_practice_ledger_and_adaptive_coach",
            "status": "future_blocked",
            "requires": ["ledger authority", "progression tracker implementation", "focused tests"],
        },
        {
            "gate_id": "stage4_logic_note_update_writeback",
            "status": "future_blocked",
            "requires": ["Mac local action approval", "before/after proof", "dry-run promotion"],
        },
        {
            "gate_id": "stage5_studio_control_lane",
            "status": "future_blocked",
            "requires": ["Guardian approval", "hardware registry", "operator live confirmation", "audit log"],
        },
    ]


def _operator_templates() -> dict[str, Any]:
    return {
        "interview_memory_template": {
            "template_label": "niles_operator_interview_memory_template_v0",
            "template_uses_placeholders_not_facts": True,
            "operator_ref": None,
            "instrument_profiles": [
                {
                    "instrument": instrument,
                    "current_strengths": [],
                    "known_weaknesses": [],
                    "target_voice": None,
                    "practice_constraints": [],
                    "operator_supplied": True,
                    "confidence": None,
                }
                for instrument in INSTRUMENTS
            ],
            "gear_inventory_refs": [],
            "taste_profile_refs": ["config/producer/producer_rubric.yaml", "config/producer/producer_reference_map.yaml"],
            "energy_constraints": [],
            "practice_preferences": [],
            "unknowns": [],
            "consent_and_scope_receipts": [],
        },
        "practice_ledger_event_template": {
            "template_label": "niles_practice_ledger_event_template_v0",
            "template_uses_placeholders_not_facts": True,
            "event_id": None,
            "operator_ref": None,
            "session_ref": None,
            "instrument": None,
            "exercise_ref": None,
            "bpm": None,
            "clean_execution_rate": None,
            "fatigue": None,
            "operator_feedback": None,
            "regression_rule_result": None,
            "next_plan_ref": None,
            "created_at": None,
        },
        "logic_note_update_request_template": {
            "template_label": "niles_logic_note_update_request_template_v0",
            "template_uses_placeholders_not_facts": True,
            "request_id": None,
            "target_session_ref_label": None,
            "note_payload_markdown": None,
            "proof_refs": [],
            "dry_run_only": True,
            "required_operator_approval": True,
            "no_daw_launch": True,
            "no_session_media_mutation": True,
            "receipt_requirements": ["scope receipt", "operator approval receipt", "before/after proof if later promoted"],
        },
    }


def _shared_primitives() -> list[dict[str, Any]]:
    return [
        {
            "primitive_id": "operator_interview_to_durable_memory",
            "niles_uses_it_for": "music profile, gear refs, taste refs, and practice constraints",
            "generic_consumers": ["Cassandra", "Chief", "Guardian", "Hermes", "future agents"],
            "niles_is_birthplace": False,
        },
        {
            "primitive_id": "progression_feedback_loop",
            "niles_uses_it_for": "practice metrics, regression rules, and next-plan generation",
            "generic_consumers": ["fitness", "workflow learning", "skill trackers"],
            "niles_is_birthplace": False,
        },
        {
            "primitive_id": "taste_timed_advice_engine",
            "niles_uses_it_for": "music coaching advice timing after Claude taste calibration",
            "generic_consumers": ["Cassandra messaging", "Chief planning", "Hermes advice"],
            "niles_is_birthplace": False,
        },
    ]


def _reference_docs(repo_root: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    orchestration_root = Path("/Volumes/openclaw_e/orchestration")
    for ref_id, path in REFERENCE_DOCS.items():
        if path.startswith("../orchestration/"):
            resolved = orchestration_root / path.removeprefix("../orchestration/")
        else:
            resolved = repo_root / path
        docs.append(
            {
                "ref_id": ref_id,
                "path": path,
                "exists": resolved.exists(),
                "used_as_contract_evidence": True,
                "raw_body_ingested": False,
            }
        )
    return docs


def _all_authority_flags_safe(boundary: dict[str, bool]) -> bool:
    return all(value is False for key, value in boundary.items() if key not in {"schema_only", "template_only"})


def build_niles_stage1_schema_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    schemas = _schema_contracts()
    boundary = dict(NO_AUTHORITY_FLAGS)
    proof = {
        "schema_count": len(schemas),
        "stage_gate_count": len(_stage_gates()),
        "covered_instruments": list(INSTRUMENTS),
        "all_required_schema_fields_present": all(set(REQUIRED_SCHEMA_FIELDS) <= set(schema) for schema in schemas),
        "all_authority_flags_safe": _all_authority_flags_safe(boundary),
        "studio_control_separate_and_blocked": any(
            schema["schema_id"] == "niles_studio_control_authority_envelope_v0"
            and schema["authority_boundary"]["studio_control_enabled"] is False
            for schema in schemas
        ),
        "logic_note_update_dry_run_only": _operator_templates()["logic_note_update_request_template"]["dry_run_only"] is True,
        "templates_use_placeholders_not_facts": all(
            template["template_uses_placeholders_not_facts"] for template in _operator_templates().values()
        ),
        "niles_uses_shared_primitives": all(item["niles_is_birthplace"] is False for item in _shared_primitives()),
        "taste_calibration_deferred": boundary["taste_calibration_complete"] is False,
        "send_hold_bypass_allowed": boundary["send_hold_bypass_allowed"],
        "raw_private_bodies_included": False,
        "credentials_or_secrets_included": False,
        "content_hash": None,
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "workflow_domain": "music_art",
        "agent_id": "niles",
        "north_star": "Niles Stage 1 defines durable music schemas before taste calibration or live studio control.",
        "stage1_scope": [
            "operator interview memory schema",
            "practice ledger event schema",
            "adaptive practice plan schema",
            "Logic note update request schema",
            "Maestro to Niles handoff packet",
            "separate future studio control authority envelope",
        ],
        "non_goals": [
            "no live interview execution",
            "no practice ledger mutation",
            "no Logic or Ableton launch",
            "no DAW session read",
            "no audio or session media mutation",
            "no studio hardware control",
            "no taste calibration completion",
        ],
        "covered_instruments": list(INSTRUMENTS),
        "schema_required_fields": list(REQUIRED_SCHEMA_FIELDS),
        "schema_contracts": schemas,
        "schema_contracts_by_id": {schema["schema_id"]: schema for schema in schemas},
        "stage_gates": _stage_gates(),
        "operator_input_templates": _operator_templates(),
        "shared_primitives": _shared_primitives(),
        "reference_docs": _reference_docs(root),
        "authority_boundary": boundary,
        "next_safe_operator_action": "Review the Stage 1 schemas, then let Claude/taste calibration fill interview prompts later.",
        "machine_proof": proof,
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_niles_stage1_schema_contract(payload: dict[str, Any]) -> str:
    proof = payload["machine_proof"]
    lines = [
        "# Niles Stage 1 Schema Contract v0",
        "",
        "Status:",
        f"- Contract status: `{payload['contract_status']}`.",
        f"- Schema count: `{proof['schema_count']}`.",
        f"- Stage gate count: `{proof['stage_gate_count']}`.",
        "- Runtime authority added: `false`.",
        "- Practice ledger write allowed: `false`.",
        "- Logic or Ableton open allowed: `false`.",
        "- DAW/session media mutation allowed: `false`.",
        "- Studio control enabled: `false`.",
        "- SEND_HOLD bypass allowed: `false`.",
        "- Taste calibration complete: `false`.",
        "",
        "## Schemas",
    ]
    for schema in payload["schema_contracts"]:
        lines.append(f"- `{schema['schema_id']}`: {schema['purpose']}")
    lines.extend(
        [
            "",
            "## Covered Instruments",
            "- " + ", ".join(payload["covered_instruments"]) + ".",
            "",
            "## Shared, Not Niles-Private",
        ]
    )
    for primitive in payload["shared_primitives"]:
        lines.append(f"- `{primitive['primitive_id']}`: Niles uses it for {primitive['niles_uses_it_for']}.")
    lines.extend(
        [
            "",
            "## Stage Gates",
        ]
    )
    for gate in payload["stage_gates"]:
        lines.append(f"- `{gate['gate_id']}`: `{gate['status']}`.")
    lines.extend(
        [
            "",
            "## Machine Proof",
            f"- All required schema fields present: `{str(proof['all_required_schema_fields_present']).lower()}`.",
            f"- All authority flags safe: `{str(proof['all_authority_flags_safe']).lower()}`.",
            f"- Studio control separate and blocked: `{str(proof['studio_control_separate_and_blocked']).lower()}`.",
            f"- Logic note update dry-run only: `{str(proof['logic_note_update_dry_run_only']).lower()}`.",
            f"- Templates use placeholders, not facts: `{str(proof['templates_use_placeholders_not_facts']).lower()}`.",
            f"- Niles uses shared primitives: `{str(proof['niles_uses_shared_primitives']).lower()}`.",
            f"- Content hash: `{proof['content_hash']}`.",
            "",
            "## Next Safe Operator Action",
            f"- {payload['next_safe_operator_action']}",
        ]
    )
    return "\n".join(lines) + "\n"


def export_niles_stage1_schema_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> NilesStage1SchemaExportResult:
    root = Path(repo_root)
    out_dir = root / export_root
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_niles_stage1_schema_contract(repo_root=root, generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_niles_stage1_schema_contract(payload), encoding="utf-8")
    return NilesStage1SchemaExportResult(
        schema_version=SCHEMA_VERSION,
        contract_status=payload["contract_status"],
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        schema_count=payload["machine_proof"]["schema_count"],
        stage_gate_count=payload["machine_proof"]["stage_gate_count"],
        runtime_authority_added=payload["authority_boundary"]["runtime_authority_added"],
        studio_control_enabled=payload["authority_boundary"]["studio_control_enabled"],
        practice_ledger_write_allowed=payload["authority_boundary"]["practice_ledger_write_allowed"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Niles Stage 1 schema contract.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root to write generated read-models.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Read-model export directory.")
    parser.add_argument("--format", choices=("json", "operator"), default="operator", help="Print result format.")
    parser.add_argument("--generated-at", default=None, help="Override generated_at for deterministic tests.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    result = export_niles_stage1_schema_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(
            f"Niles Stage 1 schema contract exported: {result.json_path} and {result.operator_path} "
            f"({result.contract_status}; schemas={result.schema_count})."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
