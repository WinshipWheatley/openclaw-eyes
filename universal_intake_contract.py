"""Universal Intake Contract v0.

Generic "drop file + vague note" interpretation contract. It infers safe
candidate intake metadata only; it never reads file bodies, parses workbooks,
or mutates production workflow state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "universal_intake_contract_v0"
READ_MODEL_ID = "universal_intake_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "UNIVERSAL_INTAKE_METADATA_ONLY_NO_BODY_READ"

AUTHORITY_BOUNDARY = {
    "file_body_read_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "ocr_allowed": False,
    "model_call_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "pdf_generation_allowed": False,
    "ledger_posting_allowed": False,
    "production_state_mutation_allowed": False,
}


@dataclass(frozen=True)
class UniversalIntakeInput:
    intake_id: str
    file_display_name: str
    file_extension: str
    file_type: str
    user_note: str
    current_world_ref: str
    source_request_id: str


@dataclass(frozen=True)
class UniversalIntakeCandidate:
    candidate_id: str
    source_request_id: str
    world_ref: str
    client_ref: str
    workflow_ref: str
    artifact_kind: str
    intended_use: str
    confidence: str
    operator_headline: str
    operator_message: str
    clarification_question: str
    next_safe_action: str
    submitted: bool
    paid: bool
    ledger_posted: bool
    final: bool
    proposed_facts_only: bool
    backend_paths_exposed: bool
    authority_boundary: dict[str, bool]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _is_spreadsheet(extension: str, file_type: str) -> bool:
    ext = extension.lower().lstrip(".")
    return ext in {"xlsx", "xls", "xlsm", "csv"} or "spreadsheet" in file_type.lower() or "excel" in file_type.lower()


def _capital_hilton_signal(text: str) -> bool:
    lowered = text.lower()
    return "capital hilton" in lowered or "capitol hilton" in lowered or "hilton" in lowered


def infer_universal_intake(input_data: UniversalIntakeInput | Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(input_data, UniversalIntakeInput):
        input_data = UniversalIntakeInput(
            intake_id=str(input_data.get("intake_id") or "universal_intake_request"),
            file_display_name=str(input_data.get("file_display_name") or ""),
            file_extension=str(input_data.get("file_extension") or ""),
            file_type=str(input_data.get("file_type") or ""),
            user_note=str(input_data.get("user_note") or ""),
            current_world_ref=str(input_data.get("current_world_ref") or ""),
            source_request_id=str(input_data.get("source_request_id") or "unknown_source_request"),
        )
    text = " ".join((input_data.file_display_name, input_data.user_note, input_data.current_world_ref))
    spreadsheet = _is_spreadsheet(input_data.file_extension or Path(input_data.file_display_name).suffix, input_data.file_type)
    finance = input_data.current_world_ref.lower() == "finance" or "invoice" in text.lower()
    capital_hilton = _capital_hilton_signal(text)

    if spreadsheet and finance and capital_hilton and "running" in text.lower() and "invoice" in text.lower():
        candidate = UniversalIntakeCandidate(
            candidate_id=f"universal_intake_candidate:{_short_hash(input_data.source_request_id, input_data.file_display_name)}",
            source_request_id=input_data.source_request_id,
            world_ref="finance",
            client_ref="capital_hilton",
            workflow_ref="capital_hilton_invoice_workflow",
            artifact_kind="running_draft_invoice_workbook",
            intended_use="register_or_resolve_invoice_workbook_artifact",
            confidence="HIGH",
            operator_headline="Capital Hilton workbook recognized",
            operator_message="OpenClaw recognized this as a likely Capital Hilton running invoice workbook. It is still a draft/source workbook, not proof that anything was sent or paid.",
            clarification_question="",
            next_safe_action="Propose metadata-only workbook intake, then ask before any audit, send, PDF, or ledger step.",
            submitted=False,
            paid=False,
            ledger_posted=False,
            final=False,
            proposed_facts_only=True,
            backend_paths_exposed=False,
            authority_boundary=dict(AUTHORITY_BOUNDARY),
        )
        return asdict(candidate)

    if spreadsheet and finance and "invoice" in text.lower():
        candidate = UniversalIntakeCandidate(
            candidate_id=f"universal_intake_candidate:{_short_hash(input_data.source_request_id, input_data.file_display_name, 'ambiguous_invoice')}",
            source_request_id=input_data.source_request_id,
            world_ref="finance",
            client_ref="unknown",
            workflow_ref="unknown",
            artifact_kind="possible_invoice_workbook",
            intended_use="needs_client_workflow_clarification",
            confidence="MEDIUM",
            operator_headline="Which client is this for?",
            operator_message="OpenClaw sees an invoice workbook candidate, but needs the client or workflow before using it.",
            clarification_question="Which client or workflow should this workbook belong to?",
            next_safe_action="Ask one clarification question; do not read the workbook.",
            submitted=False,
            paid=False,
            ledger_posted=False,
            final=False,
            proposed_facts_only=True,
            backend_paths_exposed=False,
            authority_boundary=dict(AUTHORITY_BOUNDARY),
        )
        return asdict(candidate)

    candidate = UniversalIntakeCandidate(
        candidate_id=f"universal_intake_candidate:{_short_hash(input_data.source_request_id, input_data.file_display_name, 'unclear')}",
        source_request_id=input_data.source_request_id,
        world_ref=input_data.current_world_ref or "unknown",
        client_ref="unknown",
        workflow_ref="unknown",
        artifact_kind="unknown_file_reference",
        intended_use="needs_clarification",
        confidence="LOW",
        operator_headline="What should OpenClaw do with this?",
        operator_message="OpenClaw received the file reference, but needs a little more context before using it.",
        clarification_question="What workflow should this file support?",
        next_safe_action="Ask one clarification question; do not read the file body.",
        submitted=False,
        paid=False,
        ledger_posted=False,
        final=False,
        proposed_facts_only=True,
        backend_paths_exposed=False,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
    )
    return asdict(candidate)


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    examples = {
        "capital_hilton_running_workbook": infer_universal_intake(
            {
                "intake_id": "universal_intake_fixture_capital_hilton",
                "source_request_id": "universal_intake_fixture_capital_hilton_request",
                "file_display_name": "Invoice Capitol Hilton Running.xlsx",
                "file_extension": ".xlsx",
                "file_type": "spreadsheet",
                "user_note": "this is the real Capital Hilton workbook",
                "current_world_ref": "finance",
            }
        ),
        "ambiguous_invoice_workbook": infer_universal_intake(
            {
                "intake_id": "universal_intake_fixture_ambiguous",
                "source_request_id": "universal_intake_fixture_ambiguous_request",
                "file_display_name": "Invoice Running.xlsx",
                "file_extension": ".xlsx",
                "file_type": "spreadsheet",
                "user_note": "use this",
                "current_world_ref": "finance",
            }
        ),
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "examples": examples,
        "connects_to_chain": {
            "gate_1": "Consumes safe metadata-only file references and notes.",
            "lm1": "Can provide structured candidate context before LM1 proposal or deterministic intake.",
            "gate_2": "High-confidence candidates still need normal intent/capability validation before action.",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "capital_hilton_fixture_inferred": examples["capital_hilton_running_workbook"]["client_ref"] == "capital_hilton",
            "ambiguous_fixture_asks_clarification": bool(examples["ambiguous_invoice_workbook"]["clarification_question"]),
            "fixture_submitted_false": examples["capital_hilton_running_workbook"]["submitted"] is False,
            "fixture_paid_false": examples["capital_hilton_running_workbook"]["paid"] is False,
            "fixture_ledger_posted_false": examples["capital_hilton_running_workbook"]["ledger_posted"] is False,
            "fixture_final_false": examples["capital_hilton_running_workbook"]["final"] is False,
            "workbook_body_read_performed": False,
            "backend_paths_exposed": False,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def write_exports(payload: Mapping[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    proof = payload.get("machine_proof", {})
    lines = [
        "# Universal Intake Contract",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"Capital Hilton fixture inferred: {str(proof.get('capital_hilton_fixture_inferred')).lower()}",
        f"Ambiguous fixture asks clarification: {str(proof.get('ambiguous_fixture_asks_clarification')).lower()}",
        "",
        "Drop-file interpretation is metadata-only. Running invoice workbooks remain draft/source workbooks until audited and approved.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export universal intake contract read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)

    payload = build_payload(generated_at=args.generated_at)
    json_path, operator_path = write_exports(payload, args.export_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(
            stable_json(
                {
                    "read_model_id": READ_MODEL_ID,
                    "json_path": json_path.as_posix(),
                    "operator_path": operator_path.as_posix(),
                    "capital_hilton_fixture_inferred": payload["machine_proof"]["capital_hilton_fixture_inferred"],
                    "ambiguous_fixture_asks_clarification": payload["machine_proof"]["ambiguous_fixture_asks_clarification"],
                    "workbook_body_read_performed": payload["machine_proof"]["workbook_body_read_performed"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
