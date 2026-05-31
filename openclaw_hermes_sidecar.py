"""OpenClaw Hermes sidecar v0.

Deterministic recommendation read-model for the existing Hermes sidecar layer.
It consumes current OpenClaw registries, summarizes posture and steel-thread
priority, and emits the next recommended package. It does not launch Hermes,
launch Chief, call LMs, start services, access external systems, read workbook
cells, export PDFs, mutate ledgers, mutate production state, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_SYSTEM_KNOWLEDGE_ROOT = Path("generated/system_knowledge")

SCHEMA_VERSION = "openclaw_hermes_sidecar_v0"
READ_MODEL_ID = "openclaw_hermes_sidecar"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
SQLITE_EXPORT_NAME = f"{READ_MODEL_ID}.sqlite"
SCHEMA_EXPORT_NAME = f"{READ_MODEL_ID}_SCHEMA.sql"
SEED_EXPORT_NAME = f"{READ_MODEL_ID}_SEED.sql"
CONTRACT_STATUS = "DETERMINISTIC_HERMES_SIDECAR_RECOMMENDATION_LAYER_NO_EXECUTION"
READINESS = "READY_FOR_RECOMMENDATION_NOT_EXECUTION"

REQUIRED_SQLITE_TABLES = (
    "hermes_sidecar_run",
    "hermes_source_ref",
    "hermes_material_change",
    "hermes_stale_surface",
    "hermes_authority_drift",
    "hermes_do_not_touch",
)

INPUT_SPECS = (
    ("hermes_mission_sentinel", "generated/read_models/hermes_mission_sentinel.json", False, "Existing Hermes mission sentinel."),
    ("hermes_gravity_controller", "generated/read_models/hermes_gravity_controller.json", False, "Existing Hermes gravity controller."),
    ("purpose_bound_automation_charter", "generated/read_models/purpose_bound_automation_charter.json", False, "Purpose-bound automation charter."),
    ("hermes_chief_build_handoff", "generated/read_models/hermes_chief_build_handoff.json", False, "Existing Hermes to Chief handoff."),
    ("change_sentinel", "generated/read_models/openclaw_change_sentinel.json", True, "Material change sentinel."),
    ("lane_capability_harvest", "generated/read_models/openclaw_lane_capability_harvest.json", True, "Lane capability harvest and Hermes recommendation."),
    ("business_object_audit", "generated/read_models/openclaw_business_object_layer_audit.json", True, "Business-object audit freshness and current object posture."),
    ("context_wiki_index", "generated/read_models/openclaw_context_wiki_index.json", True, "Context wiki index and freshness projection."),
    ("authority_semantics_registry", "generated/read_models/openclaw_authority_semantics_registry.json", True, "Authority semantics and drift registry."),
    ("lm_child_package_gate", "generated/read_models/openclaw_lm_child_package_gate.json", True, "LM child package gate contract."),
    ("estate_topology_registry", "generated/read_models/openclaw_estate_topology_registry.json", True, "Estate topology registry."),
    ("reference_resolver", "generated/read_models/openclaw_reference_resolver.json", True, "Reference resolver and drift posture."),
    ("service_keeper_status", "generated/read_models/openclaw_service_keeper_status.json", False, "Service supervision status read-model."),
)

BASE_DO_NOT_TOUCH = (
    "launch Hermes daemon",
    "launch Chief",
    "call LM",
    "start services",
    "send email",
    "access Gmail",
    "open browser",
    "access Coupa",
    "read workbook cells",
    "export PDFs",
    "mutate ledger",
    "mutate production state",
    "spawn child workers",
    "enable swarms",
    "push git",
)

CHIEF_FORBIDDEN_ACTIONS = (
    "launch Chief runtime",
    "call LMs",
    "start services",
    "send email",
    "access Gmail",
    "open browser",
    "access Coupa",
    "read workbook cells",
    "export PDFs",
    "post ledger entries",
    "mutate production state",
    "enable child spawning",
    "enable swarm mode",
    "push git",
)

LIVE_ACTION_TERMS = (
    "ledger",
    "email",
    "gmail",
    "browser",
    "coupa",
    "workbook",
    "pdf",
    "production",
    "service",
    "chief runtime",
    "lm call",
    "swarm",
)


@dataclass(frozen=True)
class HermesSidecarExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    sqlite_path: str
    schema_sql_path: str
    seed_sql_path: str
    recommended_next_package: str
    recommended_model_class: str
    confidence: str
    readiness: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _compact_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def _short_hash(*parts: object) -> str:
    return hashlib.sha256(_compact_json(parts).encode("utf-8")).hexdigest()[:20]


def _content_hash(payload: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(dict(payload)))
    machine = clone.get("machine_proof")
    if isinstance(machine, dict):
        machine.pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _rooted(path: str | Path, *, root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(root) / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _manifest_path(path_value: str, *, read_model_root: str | Path) -> Path:
    if path_value.startswith("generated/read_models/"):
        return _rooted(read_model_root) / path_value.removeprefix("generated/read_models/")
    return _rooted(path_value)


def _source_manifest(read_model_root: str | Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    manifest: list[dict[str, Any]] = []
    payloads: dict[str, dict[str, Any]] = {}
    for input_ref, path_value, required, purpose in INPUT_SPECS:
        path = _manifest_path(path_value, read_model_root=read_model_root)
        status = "PRESENT" if path.is_file() else ("MISSING" if required else "NOT_PRESENT")
        sha256 = ""
        schema_version = ""
        if path.is_file():
            sha256 = _sha256_file(path)
            payload = _read_json(path)
            payloads[input_ref] = payload
            schema_version = str(payload.get("schema_version", ""))
            if not payload:
                status = "BAD_JSON"
        manifest.append(
            {
                "input_ref": input_ref,
                "path": path_value,
                "resolved_path": _display_path(path),
                "required": required,
                "status": status,
                "schema_version": schema_version,
                "sha256": sha256,
                "purpose": purpose,
            }
        )
    return manifest, payloads


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return [stripped]
        return parsed if isinstance(parsed, list) else [parsed]
    return [value]


def _source_path(manifest: Sequence[Mapping[str, Any]], input_ref: str) -> str:
    for row in manifest:
        if row.get("input_ref") == input_ref:
            return str(row.get("path") or "")
    return ""


def _required_missing(manifest: Sequence[Mapping[str, Any]]) -> list[str]:
    return [
        str(row["input_ref"])
        for row in manifest
        if row.get("required") and row.get("status") != "PRESENT"
    ]


def _lane_statuses(lane_payload: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(row.get("lane_ref")): str(row.get("status"))
        for row in _as_list(lane_payload.get("lanes"))
        if isinstance(row, Mapping)
    }


def _invoice_lanes_all_proven(lane_payload: Mapping[str, Any]) -> bool:
    statuses = _lane_statuses(lane_payload)
    needed = (
        "live_arts_md_invoice_lane",
        "capital_hilton_invoice_lane",
        "st_annes_invoice_lane",
    )
    return all(statuses.get(ref) == "PROVEN" for ref in needed)


def _active_steel_thread(lane_payload: Mapping[str, Any], manifest: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rec = lane_payload.get("hermes_recommendation")
    rec = rec if isinstance(rec, Mapping) else {}
    statuses = _lane_statuses(lane_payload)
    all_proven = _invoice_lanes_all_proven(lane_payload)
    return {
        "steel_thread_ref": "invoice_steel_thread_sequence",
        "source_ref": _source_path(manifest, "lane_capability_harvest"),
        "lane_statuses": statuses,
        "all_three_invoice_lanes_proven": all_proven,
        "current_recommendation": str(rec.get("recommended_next_lane") or "finish_invoice_steel_thread_sequence"),
        "reason": str(rec.get("reason") or "Lane harvest is missing a reason; fail closed to invoice steel-thread sequence."),
        "chief_build_task_ref": str(rec.get("chief_build_task_ref") or "chief_build_task:finish_invoice_steel_thread_sequence"),
        "expected_new_capability": str(rec.get("expected_new_capability") or "completed reusable invoice steel-thread sequence"),
    }


def _material_changes(sentinel_payload: Mapping[str, Any], manifest: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    source = _source_path(manifest, "change_sentinel")
    changes: list[dict[str, Any]] = []
    for index, change in enumerate(_as_list(sentinel_payload.get("material_changes")), start=1):
        payload = change if isinstance(change, Mapping) else {"summary": str(change)}
        summary = str(payload.get("summary") or payload.get("change_summary") or payload.get("path") or payload)
        changes.append(
            {
                "change_ref": str(payload.get("change_ref") or payload.get("target_ref") or f"material_change:{index}"),
                "change_kind": str(payload.get("change_kind") or payload.get("change_type") or "MATERIAL_CHANGE"),
                "summary": summary,
                "source_ref": source,
                "payload": dict(payload),
            }
        )
    if not changes and int(sentinel_payload.get("material_change_count") or 0) > 0:
        changes.append(
            {
                "change_ref": "material_change:count_only",
                "change_kind": "MATERIAL_CHANGE",
                "summary": "Change Sentinel reports material changes without row detail.",
                "source_ref": source,
                "payload": {"material_change_count": int(sentinel_payload.get("material_change_count") or 0)},
            }
        )
    return changes


def _stale_surfaces(
    business_payload: Mapping[str, Any],
    wiki_payload: Mapping[str, Any],
    manifest: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    stale: list[dict[str, str]] = []
    business_status = str(business_payload.get("freshness_status") or business_payload.get("readiness") or "UNKNOWN")
    if business_status.upper() != "FRESH":
        stale.append(
            {
                "surface_ref": "business_object_audit",
                "status": business_status,
                "reason": "; ".join(str(item) for item in _as_list(business_payload.get("stale_reasons"))) or "Business-object audit is not fresh.",
                "source_ref": _source_path(manifest, "business_object_audit"),
            }
        )

    wiki_status = str(
        wiki_payload.get("business_object_audit_freshness_status")
        or (wiki_payload.get("business_object_audit_freshness") or {}).get("freshness_status")
        or "UNKNOWN"
    )
    wiki_missing = _as_list(wiki_payload.get("missing_inputs"))
    wiki_stale_reasons = _as_list(wiki_payload.get("business_object_audit_stale_reasons"))
    if wiki_status.upper() != "FRESH" or wiki_missing or wiki_stale_reasons:
        stale.append(
            {
                "surface_ref": "context_wiki_index",
                "status": wiki_status,
                "reason": "; ".join(str(item) for item in (wiki_stale_reasons or wiki_missing)) or "Context wiki projected freshness is not fresh.",
                "source_ref": _source_path(manifest, "context_wiki_index"),
            }
        )
    return stale


def _authority_drift(authority_payload: Mapping[str, Any], manifest: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    active = [
        dict(row)
        for row in _as_list(authority_payload.get("active_drift_signals"))
        if isinstance(row, Mapping)
    ]
    profiles = _as_list(authority_payload.get("authority_profiles"))
    profile = profiles[0] if profiles and isinstance(profiles[0], Mapping) else {}
    return {
        "source_ref": _source_path(manifest, "authority_semantics_registry"),
        "active_drift_count": len(active),
        "active_drift_signals": active,
        "dangerous_authorities": _as_list(profile.get("dangerous_authorities")),
        "blocked_actions": _as_list(profile.get("blocked_actions")),
        "authority_registry_present": bool(authority_payload),
        "drift_present": bool(active),
    }


def _service_supervision(service_payload: Mapping[str, Any], manifest: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    unit_results = [
        dict(row)
        for row in _as_list(service_payload.get("unit_results"))
        if isinstance(row, Mapping)
    ]
    return {
        "source_ref": _source_path(manifest, "service_keeper_status"),
        "status": str(service_payload.get("run_status") or "UNKNOWN"),
        "checked_units": _as_list(service_payload.get("checked_units")),
        "unit_count": len(unit_results),
        "units": [
            {
                "unit_name": str(row.get("unit_name") or ""),
                "status": str(row.get("status") or ""),
                "active_state_after": str(row.get("active_state_after") or ""),
                "started": bool(row.get("started")),
            }
            for row in unit_results
        ],
        "starts_arbitrary_services": bool(service_payload.get("starts_arbitrary_services")),
        "restarts_active_services": bool(service_payload.get("restarts_active_services")),
        "sidecar_started_services": False,
    }


def _confidence(base: str, *, missing_required: Sequence[str], stale_surfaces: Sequence[Mapping[str, Any]], material_changes: Sequence[Mapping[str, Any]], authority_drift_present: bool) -> str:
    levels = ["LOW", "MEDIUM", "MEDIUM_HIGH", "HIGH"]
    normalized = str(base or "MEDIUM").upper()
    if normalized not in levels:
        normalized = "MEDIUM"
    index = levels.index(normalized)
    if stale_surfaces:
        index = min(index, levels.index("MEDIUM"))
    if material_changes:
        index = min(index, levels.index("MEDIUM"))
    if authority_drift_present:
        index = min(index, levels.index("LOW"))
    if missing_required:
        index = 0
    return levels[index]


def _do_not_touch(lane_payload: Mapping[str, Any]) -> list[str]:
    items = [str(item) for item in _as_list(lane_payload.get("do_not_work_now"))]
    for item in BASE_DO_NOT_TOUCH:
        if item not in items:
            items.append(item)
    return items


def _recommended_package(
    *,
    lane_payload: Mapping[str, Any],
    material_changes: Sequence[Mapping[str, Any]],
    manifest: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if material_changes:
        return {
            "package_ref": "hermes_package:diagnose_material_change",
            "package_type": "diagnostic_package",
            "recommended_next_lane": "diagnose_material_change_before_feature_work",
            "reason": "Change Sentinel reports material change, so Hermes prioritizes diagnosis over new feature work.",
            "allowed_actions": ("inspect read-model diffs", "run bounded tests", "emit diagnostic package"),
            "forbidden_actions": CHIEF_FORBIDDEN_ACTIONS,
            "source_refs": (_source_path(manifest, "change_sentinel"),),
        }

    rec = lane_payload.get("hermes_recommendation")
    rec = rec if isinstance(rec, Mapping) else {}
    lane = str(rec.get("recommended_next_lane") or "finish_invoice_steel_thread_sequence")
    package_ref = str(rec.get("chief_build_task_ref") or f"chief_build_task:{lane}")
    return {
        "package_ref": package_ref,
        "package_type": "build_planning_package",
        "recommended_next_lane": lane,
        "reason": str(rec.get("reason") or "Lane harvest keeps Hermes on the active invoice steel-thread sequence."),
        "allowed_actions": ("prepare bounded implementation package", "run local tests", "emit receipts"),
        "forbidden_actions": CHIEF_FORBIDDEN_ACTIONS,
        "source_refs": tuple(
            ref
            for ref in (
                _source_path(manifest, "lane_capability_harvest"),
                _source_path(manifest, "authority_semantics_registry"),
                _source_path(manifest, "lm_child_package_gate"),
            )
            if ref
        ),
    }


def _model_class(recommended_package: Mapping[str, Any]) -> str:
    if str(recommended_package.get("package_type")) == "diagnostic_package":
        return "PC_CODEX_DETERMINISTIC_DIAGNOSTIC"
    return "PC_CODEX_DETERMINISTIC_PACKAGE_BUILDER"


def _chief_allowed(recommended_package: Mapping[str, Any]) -> list[str]:
    allowed = [str(item) for item in _as_list(recommended_package.get("allowed_actions"))]
    allowed.append(str(recommended_package.get("package_ref") or ""))
    return [item for item in allowed if item]


def build_hermes_sidecar(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    input_manifest, payloads = _source_manifest(read_model_root)
    missing_required = _required_missing(input_manifest)
    lane_payload = payloads.get("lane_capability_harvest", {})
    sentinel_payload = payloads.get("change_sentinel", {})
    business_payload = payloads.get("business_object_audit", {})
    wiki_payload = payloads.get("context_wiki_index", {})
    authority_payload = payloads.get("authority_semantics_registry", {})
    service_payload = payloads.get("service_keeper_status", {})

    steel_thread = _active_steel_thread(lane_payload, input_manifest)
    changes = _material_changes(sentinel_payload, input_manifest)
    stale = _stale_surfaces(business_payload, wiki_payload, input_manifest)
    authority = _authority_drift(authority_payload, input_manifest)
    service_summary = _service_supervision(service_payload, input_manifest)
    recommendation = _recommended_package(
        lane_payload=lane_payload,
        material_changes=changes,
        manifest=input_manifest,
    )
    confidence = _confidence(
        str((lane_payload.get("hermes_recommendation") or {}).get("confidence") or lane_payload.get("confidence") or "MEDIUM"),
        missing_required=missing_required,
        stale_surfaces=stale,
        material_changes=changes,
        authority_drift_present=bool(authority["drift_present"]),
    )
    do_not_touch = _do_not_touch(lane_payload)
    source_refs = [
        str(row["path"])
        for row in input_manifest
        if row.get("status") == "PRESENT"
    ]
    active_hermes_inputs = [
        row["input_ref"]
        for row in input_manifest
        if str(row.get("input_ref", "")).startswith("hermes_") and row.get("status") == "PRESENT"
    ]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated,
        "readiness": READINESS if not missing_required else "NOT_READY_MISSING_REQUIRED_INPUT",
        "current_posture": {
            "posture_ref": "hermes_sidecar_current_posture_v0",
            "status": "ACTIVE_RECOMMENDATION_LAYER_NOT_EXECUTOR",
            "existing_hermes_layers_present": active_hermes_inputs,
            "recommends_only": True,
            "executes": False,
            "launches_chief": False,
            "calls_lm": False,
            "material_change_priority_active": bool(changes),
            "stale_confidence_reduced": bool(stale),
            "missing_required_inputs": missing_required,
        },
        "active_steel_thread": steel_thread,
        "material_changes": changes,
        "stale_surfaces": stale,
        "authority_drift": authority,
        "service_supervision_summary": service_summary,
        "recommended_next_package": recommendation,
        "recommended_model_class": _model_class(recommendation),
        "do_not_touch": do_not_touch,
        "chief_allowed_to_build": _chief_allowed(recommendation),
        "chief_forbidden_actions": list(CHIEF_FORBIDDEN_ACTIONS),
        "guardian_required": True,
        "confidence": confidence,
        "source_refs": source_refs,
        "input_manifest": input_manifest,
        "machine_proof": {
            "read_model_only": True,
            "hermes_daemon_launched": False,
            "chief_launched": False,
            "lm_called": False,
            "services_started": False,
            "email_accessed": False,
            "gmail_accessed": False,
            "browser_accessed": False,
            "coupa_accessed": False,
            "workbook_cells_read": False,
            "pdf_exported": False,
            "ledger_mutated": False,
            "production_state_mutated": False,
            "git_push_performed": False,
            "live_action_recommended": False,
            "required_sqlite_tables": REQUIRED_SQLITE_TABLES,
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def operator_markdown(payload: Mapping[str, Any]) -> str:
    posture = payload.get("current_posture", {})
    steel = payload.get("active_steel_thread", {})
    rec = payload.get("recommended_next_package", {})
    source_refs = payload.get("source_refs", [])
    lines = [
        "# OpenClaw Hermes Sidecar",
        "",
        f"- Readiness: `{payload.get('readiness', 'UNKNOWN')}`",
        f"- Posture: `{posture.get('status', 'UNKNOWN')}`",
        f"- Active steel thread: `{steel.get('steel_thread_ref', 'UNKNOWN')}`",
        f"- Recommended next package: `{rec.get('package_ref', 'UNKNOWN')}`",
        f"- Recommended model class: `{payload.get('recommended_model_class', 'UNKNOWN')}`",
        f"- Confidence: `{payload.get('confidence', 'UNKNOWN')}`",
        f"- Guardian required: `{str(payload.get('guardian_required')).lower()}`",
        "",
        "## Recommendation",
        "",
        str(rec.get("reason") or ""),
        "",
        "## Do Not Touch",
        "",
    ]
    for item in payload.get("do_not_touch", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Source Refs", ""])
    for ref in source_refs:
        lines.append(f"- `{ref}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Hermes recommends only.",
            "- No Hermes daemon, Chief launch, LM call, service start, email/Gmail/browser/Coupa access, workbook cell read, PDF export, ledger mutation, production mutation, or push.",
            "",
        ]
    )
    return "\n".join(lines)


def sqlite_schema_sql() -> str:
    return """
CREATE TABLE hermes_sidecar_run (
  run_ref TEXT PRIMARY KEY,
  generated_at TEXT NOT NULL,
  current_posture TEXT NOT NULL,
  active_steel_thread TEXT NOT NULL,
  recommended_next_package TEXT NOT NULL,
  recommended_model_class TEXT NOT NULL,
  confidence TEXT NOT NULL,
  guardian_required INTEGER NOT NULL CHECK(guardian_required IN (0, 1)),
  payload_json TEXT NOT NULL
);

CREATE TABLE hermes_source_ref (
  source_ref TEXT PRIMARY KEY,
  input_ref TEXT NOT NULL,
  path TEXT NOT NULL,
  status TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  required INTEGER NOT NULL CHECK(required IN (0, 1))
);

CREATE TABLE hermes_material_change (
  change_ref TEXT PRIMARY KEY,
  change_kind TEXT NOT NULL,
  summary TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE hermes_stale_surface (
  surface_ref TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  reason TEXT NOT NULL,
  source_ref TEXT NOT NULL
);

CREATE TABLE hermes_authority_drift (
  drift_ref TEXT PRIMARY KEY,
  drift_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE hermes_do_not_touch (
  item_ref TEXT PRIMARY KEY,
  item TEXT NOT NULL,
  source_ref TEXT NOT NULL
);
""".lstrip()


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (list, tuple, dict)):
        value = _compact_json(value)
    return "'" + str(value).replace("'", "''") + "'"


def _sqlite_value(value: Any) -> Any:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (list, tuple, dict)):
        return _compact_json(value)
    return value


def _rows_by_table(payload: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    run_ref = f"hermes_sidecar_run:{_short_hash(payload.get('generated_at'), payload.get('recommended_next_package'))}"
    source_rows = [
        {
            "source_ref": f"source:{row['input_ref']}",
            "input_ref": row["input_ref"],
            "path": row["path"],
            "status": row["status"],
            "schema_version": row.get("schema_version", ""),
            "sha256": row.get("sha256", ""),
            "required": bool(row.get("required")),
        }
        for row in payload.get("input_manifest", [])
    ]
    material_rows = [
        {
            "change_ref": row["change_ref"],
            "change_kind": row["change_kind"],
            "summary": row["summary"],
            "source_ref": row["source_ref"],
            "payload_json": row.get("payload", {}),
        }
        for row in payload.get("material_changes", [])
    ]
    stale_rows = [dict(row) for row in payload.get("stale_surfaces", [])]
    authority_rows = [
        {
            "drift_ref": str(row.get("drift_ref") or f"authority_drift:{_short_hash(row)}"),
            "drift_type": str(row.get("drift_type") or "ACTIVE_AUTHORITY_DRIFT"),
            "severity": str(row.get("severity") or "UNKNOWN"),
            "source_ref": str(payload.get("authority_drift", {}).get("source_ref") or ""),
            "payload_json": dict(row),
        }
        for row in payload.get("authority_drift", {}).get("active_drift_signals", [])
    ]
    do_not_touch_rows = [
        {
            "item_ref": f"do_not_touch:{_short_hash(index, item)}",
            "item": str(item),
            "source_ref": "openclaw_hermes_sidecar.py",
        }
        for index, item in enumerate(payload.get("do_not_touch", []), start=1)
    ]
    return {
        "hermes_sidecar_run": [
            {
                "run_ref": run_ref,
                "generated_at": payload["generated_at"],
                "current_posture": payload["current_posture"],
                "active_steel_thread": payload["active_steel_thread"],
                "recommended_next_package": payload["recommended_next_package"],
                "recommended_model_class": payload["recommended_model_class"],
                "confidence": payload["confidence"],
                "guardian_required": bool(payload["guardian_required"]),
                "payload_json": dict(payload),
            }
        ],
        "hermes_source_ref": source_rows,
        "hermes_material_change": material_rows,
        "hermes_stale_surface": stale_rows,
        "hermes_authority_drift": authority_rows,
        "hermes_do_not_touch": do_not_touch_rows,
    }


def sqlite_seed_sql(payload: Mapping[str, Any]) -> str:
    statements: list[str] = []
    rows_by_table = _rows_by_table(payload)
    for table in REQUIRED_SQLITE_TABLES:
        for row in rows_by_table[table]:
            columns = list(row)
            statements.append(
                f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({', '.join(_sql_literal(row[column]) for column in columns)});"
            )
    return "\n".join(statements) + "\n"


def create_sqlite_registry(payload: Mapping[str, Any], sqlite_path: str | Path) -> None:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    rows_by_table = _rows_by_table(payload)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(sqlite_schema_sql())
        for table in REQUIRED_SQLITE_TABLES:
            for row in rows_by_table[table]:
                columns = list(row)
                placeholders = ", ".join("?" for _ in columns)
                connection.execute(
                    f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                    [_sqlite_value(row[column]) for column in columns],
                )
        connection.commit()
    finally:
        connection.close()


def export_openclaw_hermes_sidecar(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    system_knowledge_root: str | Path = DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
    generated_at: str | None = None,
) -> HermesSidecarExportResult:
    read_root = _rooted(read_model_root)
    system_root = _rooted(system_knowledge_root)
    payload = build_hermes_sidecar(read_model_root=read_model_root, generated_at=generated_at)
    json_path = read_root / JSON_EXPORT_NAME
    operator_path = read_root / OPERATOR_EXPORT_NAME
    sqlite_path = system_root / SQLITE_EXPORT_NAME
    schema_path = system_root / SCHEMA_EXPORT_NAME
    seed_path = system_root / SEED_EXPORT_NAME
    _atomic_write_text(json_path, stable_json(payload))
    _atomic_write_text(operator_path, operator_markdown(payload))
    _atomic_write_text(schema_path, sqlite_schema_sql())
    _atomic_write_text(seed_path, sqlite_seed_sql(payload))
    create_sqlite_registry(payload, sqlite_path)
    rec = payload["recommended_next_package"]
    return HermesSidecarExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        sqlite_path=_display_path(sqlite_path),
        schema_sql_path=_display_path(schema_path),
        seed_sql_path=_display_path(seed_path),
        recommended_next_package=str(rec["package_ref"]),
        recommended_model_class=str(payload["recommended_model_class"]),
        confidence=str(payload["confidence"]),
        readiness=str(payload["readiness"]),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export OpenClaw Hermes sidecar read-model.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--system-knowledge-root", default=str(DEFAULT_SYSTEM_KNOWLEDGE_ROOT))
    parser.add_argument("--generated-at", default="")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)
    result = export_openclaw_hermes_sidecar(
        read_model_root=args.read_model_root,
        system_knowledge_root=args.system_knowledge_root,
        generated_at=args.generated_at or None,
    )
    if args.format == "json":
        print(stable_json(asdict(result)), end="")
    else:
        print(f"json={result.json_path}")
        print(f"operator={result.operator_path}")
        print(f"sqlite={result.sqlite_path}")
        print(f"schema={result.schema_sql_path}")
        print(f"seed={result.seed_sql_path}")
        print(f"recommended_next_package={result.recommended_next_package}")
        print(f"recommended_model_class={result.recommended_model_class}")
        print(f"confidence={result.confidence}")
        print(f"readiness={result.readiness}")
    return 0 if result.readiness.startswith("READY") else 2


__all__ = [
    "BASE_DO_NOT_TOUCH",
    "CHIEF_FORBIDDEN_ACTIONS",
    "CONTRACT_STATUS",
    "DEFAULT_READ_MODEL_ROOT",
    "DEFAULT_SYSTEM_KNOWLEDGE_ROOT",
    "INPUT_SPECS",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "READINESS",
    "READ_MODEL_ID",
    "REQUIRED_SQLITE_TABLES",
    "SCHEMA_EXPORT_NAME",
    "SCHEMA_VERSION",
    "SEED_EXPORT_NAME",
    "SQLITE_EXPORT_NAME",
    "HermesSidecarExportResult",
    "build_hermes_sidecar",
    "create_sqlite_registry",
    "export_openclaw_hermes_sidecar",
    "operator_markdown",
    "sqlite_schema_sql",
    "sqlite_seed_sql",
    "stable_json",
    "utc_now",
]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
