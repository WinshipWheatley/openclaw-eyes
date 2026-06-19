"""Evidence + Truth Contract v0.

This read-model defines how OpenClaw should treat claims, receipts, gates, and
contradictions. It records truth posture only; it does not inspect private
artifacts, run tests, approve work, execute tools, send messages, or grant
runtime authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "evidence_truth_contract_v0"
JSON_EXPORT_NAME = "evidence_truth_contract.json"
OPERATOR_EXPORT_NAME = "evidence_truth_contract_OPERATOR.md"

NO_AUTHORITY_FLAGS = {
    "contract_only": True,
    "truth_claim_authority_added": False,
    "approval_authority_added": False,
    "execution_authority_added": False,
    "test_execution_authority_added": False,
    "raw_private_artifact_access_added": False,
    "credential_authority_added": False,
    "external_send_authority_added": False,
    "legal_discovery_authority_added": False,
    "runtime_authority_added": False,
}

CLAIM_TYPES = (
    "done_claim",
    "green_gate_claim",
    "finding_claim",
    "diagnosis_claim",
    "read_only_audit_claim",
    "blocked_claim",
)

EVIDENCE_REF_TYPES = (
    "commit_ref",
    "gate_receipt",
    "test_log",
    "file_line_ref",
    "orchestration_marker",
    "generated_read_model",
    "diff_summary",
    "diagnostic_error_line",
)

TRUTH_STATUSES = (
    "SUPPORTED",
    "EVIDENCE_MISSING",
    "GREEN_GATE_RECEIPT_REQUIRED",
    "CONTRADICTION_REQUIRES_DIAG",
    "STALE_REQUIRES_RECHECK",
    "UNKNOWN_FAIL_CLOSED",
)


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    path: str
    role: str


@dataclass(frozen=True)
class TruthRule:
    rule_id: str
    claim_type: str
    required_evidence_types: tuple[str, ...]
    fail_closed_status: str
    operator_copy: str


EVIDENCE_SOURCES = (
    EvidenceSource(
        "runtime_law",
        "OPENCLAW_RUNTIME.md",
        "proof-first runtime law and no-overclaiming posture",
    ),
    EvidenceSource(
        "operator_action_covenant",
        "operator_action_covenant.py",
        "local approval covenant; natural language alone is not authority",
    ),
    EvidenceSource(
        "protected_evidence_reference_receipt",
        "generated/read_models/protected_evidence_reference_receipt.json",
        "safe protected-reference receipt boundary",
    ),
    EvidenceSource(
        "agent_package_preview_contract",
        "generated/read_models/agent_package_preview_contract.json",
        "package preview proof and authority boundary",
    ),
)

TRUTH_RULES = (
    TruthRule(
        "done_claim_needs_artifact",
        "done_claim",
        ("commit_ref", "orchestration_marker"),
        "EVIDENCE_MISSING",
        "DONE must cite a commit, marker, receipt, or generated artifact.",
    ),
    TruthRule(
        "green_gate_needs_receipt",
        "green_gate_claim",
        ("gate_receipt", "test_log"),
        "GREEN_GATE_RECEIPT_REQUIRED",
        "GREEN means a receipt/log with pass result, not a remembered claim.",
    ),
    TruthRule(
        "finding_needs_falsifiable_pointer",
        "finding_claim",
        ("file_line_ref", "diagnostic_error_line", "test_log"),
        "EVIDENCE_MISSING",
        "Findings need file:line, repro, error, or equivalent falsifiable evidence.",
    ),
    TruthRule(
        "contradiction_forces_diag",
        "diagnosis_claim",
        ("diagnostic_error_line", "test_log", "orchestration_marker"),
        "CONTRADICTION_REQUIRES_DIAG",
        "Contradictory green/red evidence is diagnosed before fixing or claiming DONE.",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _source_record(source: EvidenceSource, *, repo_root: str | Path) -> dict[str, Any]:
    path = Path(repo_root) / source.path
    schema_version = None
    if path.suffix == ".json" and path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            schema_version = payload.get("schema_version") if isinstance(payload, dict) else None
        except (OSError, json.JSONDecodeError):
            schema_version = None
    return {
        "source_id": source.source_id,
        "path": source.path,
        "role": source.role,
        "present": path.is_file(),
        "schema_version": schema_version,
        "raw_private_body_imported": False,
        "authority_granted_by_source_presence": False,
    }


def _truth_rule_record(rule: TruthRule) -> dict[str, Any]:
    return {
        "rule_id": rule.rule_id,
        "claim_type": rule.claim_type,
        "required_evidence_types": list(rule.required_evidence_types),
        "fail_closed_status": rule.fail_closed_status,
        "operator_copy": rule.operator_copy,
    }


def _evidence_types(evidence_refs: Sequence[Mapping[str, Any]] | None) -> set[str]:
    if not evidence_refs:
        return set()
    return {
        str(ref.get("type") or ref.get("evidence_type") or "").strip()
        for ref in evidence_refs
        if str(ref.get("type") or ref.get("evidence_type") or "").strip()
    }


def _has_passing_gate_ref(evidence_refs: Sequence[Mapping[str, Any]] | None) -> bool:
    if not evidence_refs:
        return False
    for ref in evidence_refs:
        ref_type = str(ref.get("type") or ref.get("evidence_type") or "").strip()
        result = str(ref.get("result") or ref.get("status") or "").strip().lower()
        exit_code = ref.get("exit_code")
        if ref_type in {"gate_receipt", "test_log"} and result in {"green", "passed", "pass", "test succeeded", "exit_0"}:
            return True
        if ref_type == "gate_receipt" and exit_code == 0:
            return True
    return False


def evaluate_truth_claim(
    claim_type: str,
    evidence_refs: Sequence[Mapping[str, Any]] | None,
    *,
    contradiction_refs: Sequence[Mapping[str, Any]] | None = None,
    stale: bool = False,
) -> dict[str, Any]:
    """Classify a claim's proof posture; execute nothing."""
    normalized = str(claim_type or "").strip()
    evidence_types = _evidence_types(evidence_refs)
    contradiction_count = len(tuple(contradiction_refs or ()))
    reasons: list[str] = []

    if normalized not in CLAIM_TYPES:
        return {
            "claim_type": normalized,
            "truth_status": "UNKNOWN_FAIL_CLOSED",
            "supported": False,
            "blocking_reasons": ["unknown_claim_type"],
            "evidence_types_present": sorted(evidence_types),
            "contradiction_count": contradiction_count,
        }
    if contradiction_count:
        return {
            "claim_type": normalized,
            "truth_status": "CONTRADICTION_REQUIRES_DIAG",
            "supported": False,
            "blocking_reasons": ["contradictory_evidence_requires_diagnosis"],
            "evidence_types_present": sorted(evidence_types),
            "contradiction_count": contradiction_count,
        }
    if stale:
        return {
            "claim_type": normalized,
            "truth_status": "STALE_REQUIRES_RECHECK",
            "supported": False,
            "blocking_reasons": ["stale_evidence_requires_recheck"],
            "evidence_types_present": sorted(evidence_types),
            "contradiction_count": contradiction_count,
        }
    if normalized == "green_gate_claim" and not _has_passing_gate_ref(evidence_refs):
        return {
            "claim_type": normalized,
            "truth_status": "GREEN_GATE_RECEIPT_REQUIRED",
            "supported": False,
            "blocking_reasons": ["green_gate_claim_requires_passing_gate_receipt"],
            "evidence_types_present": sorted(evidence_types),
            "contradiction_count": contradiction_count,
        }
    matching_rules = [rule for rule in TRUTH_RULES if rule.claim_type == normalized]
    required = set(matching_rules[0].required_evidence_types) if matching_rules else {"orchestration_marker"}
    if not evidence_types.intersection(required):
        reasons.append("required_evidence_type_missing")
    status = "SUPPORTED" if not reasons else "EVIDENCE_MISSING"
    return {
        "claim_type": normalized,
        "truth_status": status,
        "supported": status == "SUPPORTED",
        "blocking_reasons": reasons,
        "required_evidence_types": sorted(required),
        "evidence_types_present": sorted(evidence_types),
        "contradiction_count": contradiction_count,
    }


def build_evidence_truth_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    evidence_sources = [_source_record(source, repo_root=repo_root) for source in EVIDENCE_SOURCES]
    examples = [
        evaluate_truth_claim("green_gate_claim", [{"type": "gate_receipt", "result": "green", "exit_code": 0}]),
        evaluate_truth_claim("green_gate_claim", [{"type": "orchestration_marker", "result": "claimed_green"}]),
        evaluate_truth_claim(
            "diagnosis_claim",
            [{"type": "test_log", "result": "green"}],
            contradiction_refs=[{"type": "test_log", "result": "red"}],
        ),
    ]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "evidence_truth_contract",
        "generated_at": generated_at,
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_evidence_truth_metadata_only",
        "operator_summary": (
            "OpenClaw truth claims are only as strong as their receipts. DONE, GREEN, READY, and findings must "
            "cite artifacts; contradictions trigger diagnosis before action."
        ),
        "truth_doctrine": {
            "natural_language_done_is_not_proof": True,
            "green_requires_current_gate_receipt": True,
            "red_requires_first_hard_error_or_repro": True,
            "contradiction_promotes_to_diagnosis": True,
            "stale_receipts_require_recheck_before_ready": True,
            "private_raw_sources_are_not_imported_for_truth_claims": True,
        },
        "claim_types": list(CLAIM_TYPES),
        "evidence_ref_types": list(EVIDENCE_REF_TYPES),
        "truth_statuses": list(TRUTH_STATUSES),
        "truth_rules": [_truth_rule_record(rule) for rule in TRUTH_RULES],
        "example_truth_decisions": examples,
        "evidence_sources": evidence_sources,
        "machine_proof": {
            "source_read_models_present": {source["source_id"]: source["present"] for source in evidence_sources},
            "truth_rule_count": len(TRUTH_RULES),
            "authority_added": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_evidence_truth_contract(payload: dict[str, Any]) -> str:
    lines = [
        "# Evidence + Truth Contract v0",
        "",
        "## Operator Summary",
        payload["operator_summary"],
        "",
        "## Truth Doctrine",
    ]
    for key, value in payload["truth_doctrine"].items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(["", "## Claim Types"])
    for item in payload["claim_types"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Truth Rules"])
    for rule in payload["truth_rules"]:
        lines.append(f"- `{rule['rule_id']}`: {rule['operator_copy']}")
    lines.extend(["", "## Authority Boundary"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    return "\n".join(lines).rstrip() + "\n"


@dataclass(frozen=True)
class EvidenceTruthExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    truth_rule_count: int
    execution_authority_added: bool
    truth_claim_authority_added: bool


def export_evidence_truth_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> EvidenceTruthExportResult:
    payload = build_evidence_truth_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_evidence_truth_contract(payload), encoding="utf-8")
    return EvidenceTruthExportResult(
        schema_version=payload["schema_version"],
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        truth_rule_count=len(payload["truth_rules"]),
        execution_authority_added=bool(payload["execution_authority_added"]),
        truth_claim_authority_added=bool(payload["truth_claim_authority_added"]),
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Evidence + Truth Contract read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_evidence_truth_contract(repo_root=args.repo_root, export_root=args.export_root)
    if args.format == "json":
        print(stable_json(build_evidence_truth_contract(repo_root=args.repo_root)), end="")
    elif args.format == "operator":
        payload = build_evidence_truth_contract(repo_root=args.repo_root)
        print(format_evidence_truth_contract(payload), end="")
    else:
        print(stable_json(result.__dict__), end="")
    return 0


__all__ = [
    "CLAIM_TYPES",
    "EVIDENCE_REF_TYPES",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "TRUTH_STATUSES",
    "build_evidence_truth_contract",
    "evaluate_truth_claim",
    "export_evidence_truth_contract",
    "format_evidence_truth_contract",
    "main",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
