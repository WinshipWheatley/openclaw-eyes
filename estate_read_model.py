"""Estate Topology read-model v0.

This module builds a metadata-only topology view over existing OpenClaw
primitives. It creates no estate registry schema and grants no runtime,
deployment, send, network, repo-creation, or private-data authority.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend_sqlite_schema import sqlite_physical_schema_table
from business_ops_ledger import DEFAULT_DB_PATH
from corpus_atlas import query_report_section
from generated_read_model_files import (
    CRITICAL_GENERATED_READ_MODEL_FILES,
    DEFAULT_GENERATED_READ_MODEL_ROOT,
    canonical_generated_read_model_records,
)
from mac_mirror_atlas import query_mac_mirror_report_section
from module_registry import build_approved_module_registry_read_model
from project_capsule import build_project_capsule_report, get_project_capsule


ESTATE_TOPOLOGY_VERSION = "estate_topology_v0"
READ_MODEL_VERSION = ESTATE_TOPOLOGY_VERSION
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "estate_topology.json"
OPERATOR_EXPORT_NAME = "estate_topology_OPERATOR.md"
SELF_EXPORT_FILES = {JSON_EXPORT_NAME, OPERATOR_EXPORT_NAME}

NODE_SCHEMA_TABLES = (
    "openclaw_nodes",
    "runtime_components",
    "component_capabilities",
    "node_heartbeats",
    "component_heartbeats",
)

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "estate_registry_schema_created": False,
    "new_estate_schema_created": False,
    "deployment_allowed": False,
    "repo_creation_allowed": False,
    "repo_split_allowed": False,
    "network_authority": False,
    "send_allowed": False,
    "raw_data_visibility": False,
    "raw_client_content_required": False,
    "client_private_contents_exported": False,
    "private_data_accessed": False,
    "mission_control_modified": False,
    "runtime_activation_allowed": False,
    "arbitrary_shell_allowed": False,
}

CLAIMS_NOT_MADE = (
    "new_estate_registry_schema",
    "runtime_authority",
    "deployment_authority",
    "repo_split",
    "repo_creation",
    "network_or_send_path",
    "private_data_access",
    "raw_client_content_export",
    "mission_control_ui_change",
    "chief_tenant_awareness",
    "repo_b_execution",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parent / path


def _display_path(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(Path(__file__).resolve().parent).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _hash_text(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _bool(value: Any) -> bool:
    return bool(value)


def _schema_table_payload(table_name: str) -> dict[str, Any]:
    table = sqlite_physical_schema_table(table_name)
    if table is None:
        return {"table_name": table_name, "available": False, "columns": []}
    return {
        "table_name": table.table_name,
        "available": True,
        "related_schema_contract_surface": table.related_schema_contract_surface,
        "retrieval_structure_fields": sorted(table.retrieval_structure_fields),
        "columns": [
            {
                "name": column.name,
                "storage_type": column.storage_type,
                "conceptual_field": column.conceptual_field,
                "required": column.required,
                "purpose": column.purpose,
            }
            for column in table.columns
        ],
    }


def _build_backend_node_schema() -> dict[str, Any]:
    tables = [_schema_table_payload(table_name) for table_name in NODE_SCHEMA_TABLES]
    return {
        "source": "backend_sqlite_schema.py",
        "node_data_source": "static_backend_schema_only",
        "openclaw_nodes_schema_available": any(
            item["table_name"] == "openclaw_nodes" and item["available"] for item in tables
        ),
        "node_records_proven": False,
        "tables": tables,
    }


def _should_redact_root_path(root: dict[str, Any]) -> bool:
    owner_scope = str(root.get("owner_scope") or "")
    root_kind = str(root.get("root_kind") or "")
    host_kind = str(root.get("host_kind") or "")
    absolute_root = str(root.get("absolute_root") or "")
    if owner_scope.startswith("client") or root_kind.startswith("client"):
        return True
    if root.get("client_id") or root.get("instance_id"):
        return True
    if host_kind == "mac" and absolute_root.startswith("/"):
        return True
    return any(part in absolute_root.lower() for part in ("/private/", "/client/", "/customer/"))


def _safe_root(root: dict[str, Any]) -> dict[str, Any]:
    absolute_root = str(root.get("absolute_root") or "")
    redacted = _should_redact_root_path(root)
    return {
        "root_id": root.get("root_id"),
        "root_kind": root.get("root_kind"),
        "host_kind": root.get("host_kind"),
        "owner_scope": root.get("owner_scope"),
        "project_id": root.get("project_id"),
        "client_id": root.get("client_id"),
        "instance_id": root.get("instance_id"),
        "root_label": root.get("root_label"),
        "status": root.get("status"),
        "canonical_status": root.get("canonical_status"),
        "import_status": root.get("import_status"),
        "mirror_of_root_id": root.get("mirror_of_root_id"),
        "lineage_source": root.get("lineage_source"),
        "path_display": f"redacted://{root.get('root_id')}" if redacted else absolute_root,
        "path_redacted": redacted,
        "path_hash": _hash_text(absolute_root),
    }


def _build_corpus_roots(db_path: str | Path) -> dict[str, Any]:
    section = query_report_section(db_path=db_path, section="multi-root")
    if section.get("status") == "no_runs":
        return {
            "source": "corpus_atlas.py:query_report_section(multi-root)",
            "status": "no_runs",
            "root_count": 0,
            "roots": [],
        }
    roots = [_safe_root(item) for item in section.get("items", [])]
    return {
        "source": "corpus_atlas.py:query_report_section(multi-root)",
        "status": "ok",
        "root_count": len(roots),
        "roots": roots,
    }


def _safe_module_selection(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "module_id": item.get("module_id"),
        "selection_status": item.get("selection_status"),
        "activation_status": item.get("activation_status"),
        "authority_posture": item.get("authority_posture"),
        "runtime_authority": _bool(item.get("runtime_authority")),
        "operator_review_required": _bool(item.get("operator_review_required")),
        "source_basis": item.get("source_basis"),
    }


def _safe_capsule(capsule: dict[str, Any]) -> dict[str, Any]:
    boundaries = [
        {
            "data_class": item.get("data_class"),
            "boundary_kind": item.get("boundary_kind"),
            "authority_status": item.get("authority_status"),
        }
        for item in capsule.get("boundaries", [])
        if item.get("authority_status") in {"blocked", "forbidden"}
        or item.get("boundary_kind") in {"blocked", "forbidden"}
    ]
    return {
        "project_id": capsule.get("project_id"),
        "client_id": capsule.get("client_id"),
        "project_name": capsule.get("project_name"),
        "owner_scope": capsule.get("owner_scope"),
        "status": capsule.get("status"),
        "approval_status": capsule.get("approval_status"),
        "runtime_authority": _bool(capsule.get("runtime_authority")),
        "deployment_authority": _bool(capsule.get("deployment_authority")),
        "client_data_access": _bool(capsule.get("client_data_access")),
        "agent_activation_allowed": _bool(capsule.get("agent_activation_allowed")),
        "tool_execution_allowed": _bool(capsule.get("tool_execution_allowed")),
        "network_authority": _bool(capsule.get("network_authority")),
        "next_safe_move": capsule.get("next_safe_move"),
        "selected_worlds": [item.get("world_id") for item in capsule.get("worlds", [])],
        "selected_modules": [_safe_module_selection(item) for item in capsule.get("modules", [])],
        "blocked_boundaries": boundaries,
    }


def _build_project_capsules(db_path: str | Path) -> dict[str, Any]:
    report = build_project_capsule_report(db_path=db_path)
    if report.get("status") == "no_runs":
        return {
            "source": "project_capsule.py",
            "status": "no_runs",
            "capsule_count": 0,
            "capsules": [],
        }
    capsules = []
    for item in report.get("capsules") or []:
        detail = get_project_capsule(db_path=db_path, project_id=item["project_id"])
        if detail is not None:
            capsules.append(_safe_capsule(detail))
    return {
        "source": "project_capsule.py",
        "status": "ok",
        "latest_project_capsule_run_id": report.get("run_id"),
        "capsule_count": len(capsules),
        "counts": report.get("counts", {}),
        "capsules": capsules,
    }


def _build_module_registry(db_path: str | Path) -> dict[str, Any]:
    read_model = build_approved_module_registry_read_model(db_path=db_path)
    modules = [
        {
            "module_id": item["module_id"],
            "status": item["status"],
            "allowed_authority_level": item["allowed_authority_level"],
            "client_safe": item["client_safe"],
            "core_only": item["core_only"],
            "runtime_authority": item["runtime_authority"],
            "report_bridge_summary_allowed": item["report_bridge_summary_allowed"],
        }
        for item in read_model.get("modules", [])
    ]
    return {
        "source": "module_registry.py",
        "status": "ok",
        "module_count": len(modules),
        "counts": read_model.get("counts", {}),
        "modules": modules,
    }


def _build_generated_read_models(generated_read_model_root: str | Path) -> dict[str, Any]:
    records = [
        {
            "relative_path": record["relative_path"],
            "size_bytes": record["size_bytes"],
            "sha256": record["sha256"],
            "hash_algorithm": record["hash_algorithm"],
        }
        for record in canonical_generated_read_model_records(source_root=generated_read_model_root)
        if record["relative_path"] not in SELF_EXPORT_FILES
    ]
    return {
        "source": "generated_read_model_files.py",
        "safe_file_count": len(records),
        "critical_files": list(CRITICAL_GENERATED_READ_MODEL_FILES),
        "self_export_files_excluded": sorted(SELF_EXPORT_FILES),
        "files": records,
    }


def _without_self_files(items: list[str] | tuple[str, ...] | None) -> list[str]:
    return [item for item in (items or []) if item not in SELF_EXPORT_FILES]


def _safe_mac_root(item: dict[str, Any]) -> dict[str, Any]:
    return _safe_root(
        {
            "root_id": item.get("root_id"),
            "root_kind": item.get("root_kind"),
            "host_kind": item.get("host_kind"),
            "owner_scope": item.get("owner_scope"),
            "absolute_root": item.get("absolute_root"),
            "root_label": item.get("root_id"),
            "status": item.get("status"),
            "canonical_status": item.get("canonical_status"),
            "import_status": item.get("import_status"),
            "mirror_of_root_id": item.get("mirror_of_root_id"),
            "lineage_source": item.get("lineage_source"),
        }
    )


def _build_mac_mirror(db_path: str | Path, generated_read_model_root: str | Path) -> dict[str, Any]:
    mirror = query_mac_mirror_report_section(
        db_path=db_path,
        section="generated-read-model-mirror",
        canonical_read_model_root=generated_read_model_root,
    )
    mac_roots = query_mac_mirror_report_section(db_path=db_path, section="mac-roots")
    mirrors = query_mac_mirror_report_section(db_path=db_path, section="mirrors")
    expected_files = _without_self_files(mirror.get("expected_files"))
    missing_expected = _without_self_files(mirror.get("missing_expected_files"))
    extra_files = _without_self_files(mirror.get("extra_files"))
    hash_mismatch_files = _without_self_files(mirror.get("hash_mismatch_files"))
    return {
        "source": "mac_mirror_atlas.py",
        "generated_read_model_mirror": {
            "status": "ok",
            "expected_source": mirror.get("expected_source"),
            "expected_file_count": len(expected_files),
            "observed_count": len(
                [
                    item
                    for item in mirror.get("items", [])
                    if item.get("relative_path") not in SELF_EXPORT_FILES
                ]
            ),
            "critical_files": mirror.get("critical_files", []),
            "critical_missing_files": _without_self_files(mirror.get("critical_missing_files")),
            "missing_expected_files": missing_expected,
            "extra_files": extra_files,
            "hash_mismatch_files": hash_mismatch_files,
        },
        "mac_roots": [_safe_mac_root(item) for item in mac_roots.get("items", [])],
        "mirror_counts": mirrors.get("counts", {}),
        "missing_expected_files": missing_expected,
        "extra_files": extra_files,
        "hash_mismatch_files": hash_mismatch_files,
    }


def _gaps(read_model: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    if not read_model["backend_node_schema"]["node_records_proven"]:
        gaps.append("openclaw_nodes live row helper is not proven; estate view uses static schema metadata only")
    if read_model["corpus_roots"]["status"] == "no_runs":
        gaps.append("corpus_roots have no recorded Corpus Atlas run in the selected ledger")
    if read_model["project_capsules"]["status"] == "no_runs":
        gaps.append("project_capsules have no recorded Project Capsule run in the selected ledger")
    if read_model["mac_mirror"]["missing_expected_files"]:
        gaps.append("Mac generated read-model mirror is missing expected generated read-model files")
    return gaps


def build_estate_read_model(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    generated_read_model_root: str | Path = DEFAULT_GENERATED_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    backend_node_schema = _build_backend_node_schema()
    corpus_roots = _build_corpus_roots(db_path)
    project_capsules = _build_project_capsules(db_path)
    module_registry = _build_module_registry(db_path)
    generated_read_models = _build_generated_read_models(generated_read_model_root)
    mac_mirror = _build_mac_mirror(db_path, generated_read_model_root)
    read_model = {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "generated_at": generated_at or utc_now(),
        "mode": "metadata_only_estate_topology",
        "source_basis": "existing_repo_a_primitives_only",
        "source_ledger_namespaces": [
            "backend_sqlite_schema_static",
            "corpus_*",
            "project_capsule_*",
            "module_registry_*",
            "generated/read_models",
            "mac_mirror_atlas",
        ],
        "openclaw_core": {
            "canonical_repo": "/home/openclaw",
            "estate_hub": True,
            "repo_b_reference_only": True,
        },
        "backend_node_schema": backend_node_schema,
        "corpus_roots": corpus_roots,
        "project_capsules": project_capsules,
        "module_registry": module_registry,
        "generated_read_models": generated_read_models,
        "mac_mirror": mac_mirror,
        "counts": {
            "backend_node_schema_tables": len(backend_node_schema["tables"]),
            "corpus_roots": corpus_roots["root_count"],
            "project_capsules": project_capsules["capsule_count"],
            "modules": module_registry["module_count"],
            "safe_generated_read_models": generated_read_models["safe_file_count"],
            "mac_roots": len(mac_mirror["mac_roots"]),
        },
        "gaps": [],
        "recommended_next_lane": "Mission Control module/bundle visibility",
        "claims_not_made": list(CLAIMS_NOT_MADE),
        "authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }
    read_model["gaps"] = _gaps(read_model)
    return read_model


def _count_line(counts: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"


def format_estate_read_model(read_model: dict[str, Any]) -> str:
    counts = read_model["counts"]
    backend = read_model["backend_node_schema"]
    corpus = read_model["corpus_roots"]
    capsules = read_model["project_capsules"]
    modules = read_model["module_registry"]
    generated = read_model["generated_read_models"]
    mac = read_model["mac_mirror"]
    lines = [
        "# Estate Read-Model v0",
        "",
        "What this is:",
        "- Metadata-only topology visibility over existing OpenClaw Core primitives.",
        "",
        "What this is not:",
        "- It is not a new Estate Registry schema, runtime authority, deployment authority, repo split, send path, private-data export, or Mission Control UI change.",
        "",
        "Core / Node Schema:",
        f"- Static node schema available: `{str(backend['openclaw_nodes_schema_available']).lower()}`.",
        f"- Live node records proven: `{str(backend['node_records_proven']).lower()}`.",
        f"- Schema tables summarized: {counts['backend_node_schema_tables']}.",
        "",
        "Corpus Roots:",
        f"- Status: `{corpus['status']}`.",
        f"- Roots: {counts['corpus_roots']}.",
        "",
        "Project Capsules:",
        f"- Status: `{capsules['status']}`.",
        f"- Capsules: {counts['project_capsules']}.",
        "",
        "Modules:",
        f"- Modules: {counts['modules']}.",
        f"- Status counts: {_count_line(modules.get('counts', {}).get('status', {}))}.",
        "",
        "Generated Read-Models:",
        f"- Safe files: {generated['safe_file_count']}.",
        "- Self export files are excluded from generated read-model inventory to avoid self-invalidating output.",
        "",
        "Mac Mirror:",
        f"- Mac roots: {counts['mac_roots']}.",
        f"- Missing expected generated read-model files: {len(mac['missing_expected_files'])}.",
        f"- Hash mismatches: {len(mac['hash_mismatch_files'])}.",
        "",
        "Gaps:",
    ]
    lines.extend(f"- {gap}" for gap in read_model["gaps"]) if read_model["gaps"] else lines.append("- none")
    lines.extend(
        [
            "",
            "Authority Boundary:",
            "- `estate_registry_schema_created=false`; `runtime_authority=false`; `repo_split_allowed=false`.",
            "- `raw_data_visibility=false`; `client_private_contents_exported=false`; `send_allowed=false`.",
            "- This is read-model visibility only, not authority.",
            "",
            "Next Safe Move:",
            f"- {read_model['recommended_next_lane']}.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_estate_read_model(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_read_model_root: str | Path = DEFAULT_GENERATED_READ_MODEL_ROOT,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_estate_read_model(
        db_path=db_path,
        generated_read_model_root=generated_read_model_root,
    )
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_estate_read_model(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "counts": read_model["counts"],
        **NO_AUTHORITY_FLAGS,
    }


__all__ = [
    "DEFAULT_EXPORT_ROOT",
    "ESTATE_TOPOLOGY_VERSION",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_VERSION",
    "build_estate_read_model",
    "export_estate_read_model",
    "format_estate_read_model",
    "stable_json",
]
