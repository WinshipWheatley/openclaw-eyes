"""OpenClaw Evidence-Grounded Wiki Compiler v0.

This compiler creates generated Markdown understanding views from local
registry/read-model evidence only. It does not call language models, start
services, open browsers/accounts, read workbook cells, export PDFs, mutate
ledgers, or perform live automation.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_SYSTEM_KNOWLEDGE_ROOT = Path("generated/system_knowledge")
DEFAULT_EXTERNAL_REGISTRY_ROOT = Path("generated/external_registries")
DEFAULT_WIKI_ROOT = Path("generated/wiki/openclaw")

INDEX_JSON_NAME = "openclaw_context_wiki_index.json"
OPERATOR_INDEX_NAME = "openclaw_context_wiki_index_OPERATOR.md"

SCHEMA_VERSION = "openclaw_context_wiki_compiler_v0"
FOOTER = "Generated understanding view. Registry/read-models/receipts remain source of truth."
SOURCE_OF_TRUTH_WARNING = (
    "SQLite/read-models/receipts are source of truth; generated wiki pages are views."
)
BUSINESS_OBJECT_AUDIT_STALE_WARNING = (
    "This page is based on a stale business-object audit. Regenerate before using as planning source."
)

PAGE_OUTPUTS = (
    "README.md",
    "System Overview.md",
    "Evidence-Grounded Context Registry.md",
    "Estate Topology.md",
    "Reference Resolver.md",
    "Live Arts MD Invoice Automation.md",
    "Capital Hilton Invoice Workflow.md",
    "Hermes and Chief.md",
    "Mac Edge Workers.md",
    "Known Unknowns.md",
    "Build Order.md",
)

EXPECTED_SOURCE_SPECS = (
    ("estate_topology_registry_sqlite", "Estate topology SQLite registry", "generated/system_knowledge/openclaw_estate_topology_registry.sqlite", "sqlite_registry"),
    ("estate_topology_registry", "Estate topology read-model", "generated/read_models/openclaw_estate_topology_registry.json", "json_read_model"),
    ("reference_resolver_sqlite", "Reference resolver SQLite registry", "generated/system_knowledge/openclaw_reference_resolver.sqlite", "sqlite_registry"),
    ("reference_resolver", "Reference resolver read-model", "generated/read_models/openclaw_reference_resolver.json", "json_read_model"),
    ("external_system_knowledge_registry_index", "External system knowledge registry index", "generated/read_models/external_system_knowledge_registry_index.json", "json_read_model"),
    ("business_object_layer_audit", "Business-object implementation layer audit", "generated/read_models/openclaw_business_object_layer_audit.json", "json_read_model"),
    ("live_arts_md_invoice_review_bundle", "Live Arts MD invoice bundle", "generated/read_models/live_arts_md_invoice_review_bundle.json", "json_read_model"),
    ("invoice_review_bundle", "Capital Hilton invoice bundle", "generated/read_models/invoice_review_bundle.json", "json_read_model"),
    ("hermes_mission_sentinel", "Hermes mission sentinel", "generated/read_models/hermes_mission_sentinel.json", "json_read_model"),
    ("hermes_chief_build_handoff", "Hermes Chief build handoff", "generated/read_models/hermes_chief_build_handoff.json", "json_read_model"),
    ("purpose_bound_automation_charter", "Purpose-bound automation charter", "generated/read_models/purpose_bound_automation_charter.json", "json_read_model"),
    ("hermes_gravity_controller", "Hermes gravity controller", "generated/read_models/hermes_gravity_controller.json", "json_read_model"),
    ("chief_dynamic_workflow_deferred_build", "Chief dynamic workflow deferred build", "generated/read_models/chief_dynamic_workflow_deferred_build.json", "json_read_model"),
    ("openclaw_estate_node_registry", "OpenClaw estate node registry", "generated/read_models/openclaw_estate_node_registry.json", "json_read_model"),
    ("estate_topology", "Legacy estate topology read-model", "generated/read_models/estate_topology.json", "json_read_model"),
    ("build_now_vs_hold_queue_posture", "Build-now vs hold queue posture", "generated/read_models/build_now_vs_hold_queue_posture.json", "json_read_model"),
    ("work_terrain_build_cue_reconciliation_queue", "Work terrain build cue reconciliation queue", "generated/read_models/work_terrain_build_cue_reconciliation_queue.json", "json_read_model"),
)

AUTHORITY_BOUNDARY_FLAGS = {
    "compiler_generated_view_only": True,
    "live_automation_authority_added": False,
    "services_started": False,
    "services_modified": False,
    "external_lm_or_model_call_performed": False,
    "browser_accessed": False,
    "coupa_accessed": False,
    "email_or_gmail_accessed": False,
    "email_sent": False,
    "gmail_draft_created": False,
    "workbook_cells_read": False,
    "workbook_body_read": False,
    "pdf_generated_or_exported": False,
    "ledger_mutated": False,
    "production_state_mutated": False,
    "git_push_performed": False,
}

POSITIVE_STATUSES = {
    "CONFIRMED",
    "COMPLETE",
    "COMPLETED",
    "READY",
    "RESOLVED",
    "RESOLVED_LOCAL",
    "RESOLVED_REMOTE",
    "PRESENT",
    "PRESENT_ON_REVIEW_BRANCH",
    "VALID",
}

NEGATIVE_STATUSES = {
    "UNKNOWN",
    "MISSING",
    "UNREACHABLE",
    "LOCAL_PATH_UNREACHABLE",
    "REMOTE_UNAVAILABLE",
    "MAC_BRIDGE_UNAVAILABLE",
    "BLOCKED",
    "NOT_READY",
    "NOT_SENT",
    "PENDING",
    "PENDING_REVIEW",
    "INVALID_PLACEHOLDER",
    "DRIFT",
}


@dataclass(frozen=True)
class SourceInput:
    source_id: str
    label: str
    relative_path: str
    source_type: str
    exists: bool
    path: Path
    payload: Any = None
    error: str = ""
    sha256: str = ""
    sqlite_summary: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TensionSignal:
    title: str
    detail: str
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class WikiPage:
    title: str
    filename: str
    status: str
    summary: str
    confirmed_facts: tuple[str, ...]
    known_unknowns: tuple[str, ...]
    tensions: tuple[str, ...]
    next_actions: tuple[str, ...]
    what_not_to_do: tuple[str, ...]
    source_refs: tuple[str, ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def rooted(path: str | Path, *, repo_root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def display_path(path: str | Path, *, repo_root: str | Path = ROOT) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def clean_text(value: Any, *, limit: int = 260) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "unknown"
    if isinstance(value, (list, tuple, set)):
        text = ", ".join(clean_text(item, limit=80) for item in value)
    else:
        text = str(value)
    replacements = {
        "\u2014": "-",
        "\u2013": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def unique(items: Iterable[str], *, limit: int | None = None) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = clean_text(item)
        if not cleaned or cleaned == "unknown" or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
        if limit is not None and len(result) >= limit:
            break
    return tuple(result)


def bullet_lines(items: Iterable[str]) -> list[str]:
    values = unique(items)
    if not values:
        return ["- none"]
    return [f"- {item}" for item in values]


def get_path(payload: Any, dotted_path: str, default: Any = None) -> Any:
    current = payload
    for part in dotted_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        return default
    return current


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def source_ref(source: SourceInput, *, repo_root: str | Path = ROOT) -> str:
    if source.exists:
        return f"{source.relative_path} ({source.source_id})"
    return f"{source.relative_path} ({source.source_id}, missing)"


def source_refs(sources: dict[str, SourceInput], source_ids: Iterable[str]) -> tuple[str, ...]:
    return tuple(source_ref(sources[source_id]) for source_id in source_ids if source_id in sources)


def source_refs_with_prefixes(
    sources: dict[str, SourceInput],
    prefixes: Iterable[str],
) -> tuple[str, ...]:
    prefix_values = tuple(prefixes)
    return tuple(
        source_ref(source)
        for source_id, source in sources.items()
        if any(source_id.startswith(prefix) for prefix in prefix_values)
    )


def business_object_audit_freshness(sources: dict[str, SourceInput]) -> dict[str, Any]:
    source = sources.get("business_object_layer_audit")
    payload = source.payload if source else None
    if not source or not source.exists:
        return {
            "freshness_status": "MISSING",
            "generated_at": "",
            "inputs_tracked": 0,
            "missing_inputs": ["generated/read_models/openclaw_business_object_layer_audit.json"],
            "stale_reasons": ["Business-object audit read-model is missing."],
            "source_ref": "generated/read_models/openclaw_business_object_layer_audit.json (business_object_layer_audit, missing)",
            "is_fresh": False,
            "operator_line": BUSINESS_OBJECT_AUDIT_STALE_WARNING,
        }
    if not isinstance(payload, dict):
        return {
            "freshness_status": "UNKNOWN",
            "generated_at": "",
            "inputs_tracked": 0,
            "missing_inputs": [],
            "stale_reasons": ["Business-object audit read-model is not a JSON object."],
            "source_ref": source_ref(source),
            "is_fresh": False,
            "operator_line": BUSINESS_OBJECT_AUDIT_STALE_WARNING,
        }
    status = clean_text(payload.get("freshness_status") or "UNKNOWN").upper()
    missing_inputs = [clean_text(item) for item in as_list(payload.get("missing_inputs"))]
    stale_reasons = [clean_text(item, limit=360) for item in as_list(payload.get("stale_reasons"))]
    inputs_tracked = len(as_list(payload.get("input_manifest")))
    is_fresh = status == "FRESH"
    return {
        "freshness_status": status,
        "generated_at": clean_text(payload.get("generated_at")),
        "inputs_tracked": inputs_tracked,
        "missing_inputs": [item for item in missing_inputs if item and item != "unknown"],
        "stale_reasons": [item for item in stale_reasons if item and item != "unknown"],
        "source_ref": source_ref(source),
        "is_fresh": is_fresh,
        "operator_line": "Business-object audit freshness: FRESH."
        if is_fresh
        else BUSINESS_OBJECT_AUDIT_STALE_WARNING,
    }


def audit_freshness_facts(audit_freshness: dict[str, Any]) -> tuple[str, ...]:
    missing_inputs = audit_freshness.get("missing_inputs") or []
    stale_reasons = audit_freshness.get("stale_reasons") or []
    facts = [
        audit_freshness["operator_line"],
        f"Business-object audit generated_at: {audit_freshness.get('generated_at') or 'unknown'}.",
        f"Business-object audit inputs tracked: {audit_freshness.get('inputs_tracked', 0)}.",
        "Business-object audit missing inputs: "
        + (", ".join(missing_inputs) if missing_inputs else "none")
        + ".",
        "Business-object audit stale reasons: "
        + ("; ".join(stale_reasons) if stale_reasons else "none")
        + ".",
    ]
    return tuple(facts)


def load_json_payload(path: Path) -> tuple[Any, str]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle), ""
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def sqlite_metadata(path: Path) -> dict[str, Any]:
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return {"status": "ERROR", "error": str(exc), "tables": []}
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        tables = []
        for (table_name,) in rows:
            try:
                count = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
            except sqlite3.Error:
                count = None
            tables.append({"table": table_name, "row_count": count})
        return {"status": "READ_ONLY_METADATA", "tables": tables, "table_count": len(tables)}
    finally:
        conn.close()


def discover_system_knowledge_registry_files(
    *,
    repo_root: Path,
    system_knowledge_root: Path,
    read_model_root: Path,
    external_registry_root: Path,
) -> list[tuple[str, str, str, str]]:
    discovered: list[tuple[str, str, str, str]] = []
    search_roots = [repo_root, system_knowledge_root, read_model_root]
    seen: set[Path] = set()
    for base in search_roots:
        if not base.exists() or not base.is_dir():
            continue
        for path in sorted(base.glob("*openclaw_system_knowledge_registry*")):
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            rel = display_path(path, repo_root=repo_root)
            source_id = "openclaw_system_knowledge_registry_" + hashlib.sha1(rel.encode("utf-8")).hexdigest()[:10]
            source_type = "sqlite_registry" if path.suffix == ".sqlite" else "registry_file"
            discovered.append((source_id, "OpenClaw system knowledge registry file", rel, source_type))
    if external_registry_root.exists() and external_registry_root.is_dir():
        for path in sorted(external_registry_root.rglob("*openclaw_system_knowledge_registry*")):
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            rel = display_path(path, repo_root=repo_root)
            source_id = "openclaw_system_knowledge_registry_" + hashlib.sha1(rel.encode("utf-8")).hexdigest()[:10]
            source_type = "sqlite_registry" if path.suffix == ".sqlite" else "registry_file"
            discovered.append((source_id, "OpenClaw system knowledge registry external input", rel, source_type))
    return discovered


def load_sources(
    *,
    repo_root: str | Path = ROOT,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    system_knowledge_root: str | Path = DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
    external_registry_root: str | Path = DEFAULT_EXTERNAL_REGISTRY_ROOT,
) -> dict[str, SourceInput]:
    repo = Path(repo_root)
    read_root = rooted(read_model_root, repo_root=repo)
    system_root = rooted(system_knowledge_root, repo_root=repo)
    external_root = rooted(external_registry_root, repo_root=repo)
    specs = list(EXPECTED_SOURCE_SPECS)
    specs.extend(
        discover_system_knowledge_registry_files(
            repo_root=repo,
            system_knowledge_root=system_root,
            read_model_root=read_root,
            external_registry_root=external_root,
        )
    )
    if not any(spec[0].startswith("openclaw_system_knowledge_registry_") for spec in specs):
        specs.append(
            (
                "openclaw_system_knowledge_registry_files",
                "OpenClaw system knowledge registry files",
                "generated/system_knowledge/openclaw_system_knowledge_registry.*",
                "registry_file",
            )
        )

    sources: dict[str, SourceInput] = {}
    for source_id, label, rel_path, source_type in specs:
        path = rooted(rel_path, repo_root=repo)
        exists = path.exists() if "*" not in rel_path else False
        payload = None
        error = ""
        sqlite_summary: dict[str, Any] = {}
        digest = ""
        if exists and path.is_file():
            digest = sha256_file(path)
            if source_type == "json_read_model":
                payload, error = load_json_payload(path)
            elif source_type == "sqlite_registry":
                sqlite_summary = sqlite_metadata(path)
        sources[source_id] = SourceInput(
            source_id=source_id,
            label=label,
            relative_path=rel_path,
            source_type=source_type,
            exists=exists,
            path=path,
            payload=payload,
            error=error,
            sha256=digest,
            sqlite_summary=sqlite_summary,
        )
    return sources


def walk_json(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_json(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_json(child, (*path, str(index)))


def text_contains_ready(value: Any) -> bool:
    text = clean_text(value).upper()
    if not text or "READY" not in text:
        return False
    blocked_markers = ("NOT_READY", "NOT SEND READY", "NOT_SEND_READY", "BLOCKED", "DISABLED")
    return not any(marker in text for marker in blocked_markers)


def text_contains_false_or_missing(value: Any) -> bool:
    if value is False or value is None:
        return True
    text = clean_text(value).upper()
    return text in {"FALSE", "MISSING", "NOT_READY", "NOT SENT", "NOT_SENT", "PENDING", "UNKNOWN"}


def path_label(path: tuple[str, ...]) -> str:
    return ".".join(path) if path else "$"


def add_tension(
    tensions: list[TensionSignal],
    *,
    title: str,
    detail: str,
    source_refs_value: Iterable[str],
) -> None:
    signal = TensionSignal(
        title=clean_text(title),
        detail=clean_text(detail, limit=360),
        source_refs=tuple(source_refs_value),
    )
    marker = (signal.title, signal.detail, signal.source_refs)
    existing = {(item.title, item.detail, item.source_refs) for item in tensions}
    if marker not in existing:
        tensions.append(signal)


def detect_tensions(sources: dict[str, SourceInput]) -> tuple[TensionSignal, ...]:
    tensions: list[TensionSignal] = []

    for source in sources.values():
        if not source.exists:
            add_tension(
                tensions,
                title="Input source missing",
                detail=f"Expected generated wiki input is missing: {source.relative_path}.",
                source_refs_value=[source_ref(source)],
            )
        elif source.error:
            add_tension(
                tensions,
                title="Input source unreadable",
                detail=f"{source.relative_path} could not be parsed: {source.error}.",
                source_refs_value=[source_ref(source)],
            )

    resolver_source = sources.get("reference_resolver")
    resolver = resolver_source.payload if resolver_source else None
    resolver_ref = source_ref(resolver_source) if resolver_source else "reference_resolver missing"
    if isinstance(resolver, dict):
        drift_count = resolver.get("drift_count") or 0
        if drift_count:
            add_tension(
                tensions,
                title="Reference resolver drift reported",
                detail=f"Resolver reports drift_count={drift_count}.",
                source_refs_value=[resolver_ref],
            )
        for resolution in as_list(resolver.get("reference_resolutions")):
            if not isinstance(resolution, dict):
                continue
            if clean_text(resolution.get("resolved_status")).upper() == "DRIFT":
                add_tension(
                    tensions,
                    title="Reference resolution drift",
                    detail=f"{resolution.get('target_ref')} resolved as DRIFT.",
                    source_refs_value=[resolver_ref],
                )
            if clean_text(resolution.get("resolved_status")).upper() in {"MISSING", "LOCAL_PATH_UNREACHABLE", "MAC_BRIDGE_UNAVAILABLE"}:
                add_tension(
                    tensions,
                    title="Reference target unavailable",
                    detail=f"{resolution.get('target_ref')} resolved as {resolution.get('resolved_status')}.",
                    source_refs_value=[resolver_ref],
                )
        for branch_ref in as_list(resolver.get("git_branch_refs")):
            if not isinstance(branch_ref, dict):
                continue
            if clean_text(branch_ref.get("mac_mirror_status")).upper() == "LOCAL_PATH_UNREACHABLE":
                add_tension(
                    tensions,
                    title="Mac local path unreachable from PC",
                    detail=f"{branch_ref.get('mac_mirror_path')} is marked LOCAL_PATH_UNREACHABLE.",
                    source_refs_value=[resolver_ref],
                )
            if clean_text(branch_ref.get("mac_bridge_status")).upper() == "MAC_BRIDGE_UNAVAILABLE":
                add_tension(
                    tensions,
                    title="Mac bridge unavailable",
                    detail=f"{branch_ref.get('target_ref')} has mac_bridge_status=MAC_BRIDGE_UNAVAILABLE.",
                    source_refs_value=[resolver_ref],
                )

    topology_source = sources.get("estate_topology_registry")
    topology = topology_source.payload if topology_source else None
    topology_ref = source_ref(topology_source) if topology_source else "estate topology missing"
    if isinstance(topology, dict):
        for artifact in as_list(topology.get("codex_web_artifacts")):
            if not isinstance(artifact, dict):
                continue
            if clean_text(artifact.get("canonical_status") or artifact.get("status")).upper() == "UNREACHABLE":
                add_tension(
                    tensions,
                    title="Codex Web commit unreachable",
                    detail=f"{artifact.get('repo_name') or 'repo'} commit {artifact.get('commit_ref')} is recorded as unreachable.",
                    source_refs_value=[topology_ref],
                )

        present_repos = {
            clean_text(repo)
            for repo in as_list(topology.get("actual_repos"))
            if clean_text(repo) != "unknown"
        }
        missing_by_repo: dict[str, list[str]] = {}
        present_by_repo: dict[str, list[str]] = {repo: ["actual_repos"] for repo in present_repos}
        for item in as_list(topology.get("repo_working_copies")) + as_list(topology.get("registry_presence")):
            if not isinstance(item, dict):
                continue
            repo = clean_text(item.get("repo_key") or item.get("repo_name"))
            if not repo or repo == "unknown":
                continue
            statuses = [
                clean_text(item.get(key)).upper()
                for key in ("status", "canonical_status", "current_state", "evidence_status", "local_status")
                if item.get(key) is not None
            ]
            if any(status in {"MISSING", "UNREACHABLE"} for status in statuses):
                missing_by_repo.setdefault(repo, []).append(clean_text(item.get("display_name") or item.get("working_copy_id") or repo))
            if any(status in {"CONFIRMED", "PRESENT_ON_REVIEW_BRANCH"} for status in statuses):
                present_by_repo.setdefault(repo, []).append(clean_text(item.get("display_name") or item.get("working_copy_id") or repo))
        for repo, missing_refs in missing_by_repo.items():
            if repo in present_by_repo:
                add_tension(
                    tensions,
                    title="Repo status conflict",
                    detail=f"{repo} is marked missing/unreachable in {', '.join(missing_refs)} but present in {', '.join(present_by_repo[repo])}.",
                    source_refs_value=[topology_ref],
                )

    audit_summary = business_object_audit_freshness(sources)
    if not audit_summary["is_fresh"]:
        add_tension(
            tensions,
            title="Business-object audit stale",
            detail=BUSINESS_OBJECT_AUDIT_STALE_WARNING,
            source_refs_value=[str(audit_summary["source_ref"])],
        )

    live_arts_source = sources.get("live_arts_md_invoice_review_bundle")
    live_arts = live_arts_source.payload if live_arts_source else None
    live_arts_ref = source_ref(live_arts_source) if live_arts_source else "live arts missing"
    if isinstance(live_arts, dict):
        live_bundle = live_arts.get("live_arts_md_bundle", live_arts)
        machine_proof = live_bundle.get("machine_proof", {}) if isinstance(live_bundle, dict) else {}
        no_coupa = bool(machine_proof.get("live_arts_md_does_not_require_coupa")) or bool(
            machine_proof.get("live_arts_md_does_not_require_po")
        )
        if no_coupa:
            visible_blockers = [clean_text(item) for item in as_list(live_bundle.get("blockers"))]
            for item in as_list(live_bundle.get("actionable_blockers")):
                if isinstance(item, dict):
                    visible_blockers.append(clean_text(item.get("operator_summary")))
                else:
                    visible_blockers.append(clean_text(item))
            blocker_text = " ".join(visible_blockers)
            if any(marker in blocker_text.lower() for marker in ("coupa", "supplier portal", "purchase order", " po ")):
                add_tension(
                    tensions,
                    title="Live Arts supplier portal blocker unsupported",
                    detail="Live Arts is marked as not requiring Coupa/PO, but blocker text references a supplier portal or PO.",
                    source_refs_value=[live_arts_ref],
                )

    for source in sources.values():
        if source.payload is None:
            continue
        ref = source_ref(source)
        for path, value in walk_json(source.payload):
            if not isinstance(value, dict):
                continue

            status_values = {
                key: clean_text(value.get(key)).upper()
                for key in ("status", "canonical_status", "current_state", "resolved_status", "evidence_status")
                if value.get(key) is not None
            }
            if status_values:
                has_positive = any(status in POSITIVE_STATUSES for status in status_values.values())
                has_negative = any(status in NEGATIVE_STATUSES for status in status_values.values())
                if has_positive and has_negative:
                    add_tension(
                        tensions,
                        title="Status conflict in source fields",
                        detail=f"{path_label(path)} has mixed status fields: {status_values}.",
                        source_refs_value=[ref],
                    )

            readiness_keys = ("send_readiness", "send_ready", "workflow_ready", "approval_readiness_status")
            ready_values = [value.get(key) for key in readiness_keys if key in value]
            if any(text_contains_ready(item) for item in ready_values):
                if text_contains_false_or_missing(value.get("attachment_ready")) or text_contains_false_or_missing(value.get("approval_ready")):
                    add_tension(
                        tensions,
                        title="Workflow readiness conflicts with attachment or approval",
                        detail=f"{path_label(path)} says ready but attachment_ready or approval_ready is false/missing.",
                        source_refs_value=[ref],
                    )

            if "manual_send_proof" in path or path[-1:] == ("manual_send_proof",):
                proof_status = clean_text(value.get("proof_status") or value.get("manual_send_proof_status")).upper()
                proof_confirmed = (
                    "CONFIRMED" in proof_status
                    or "COMPLETE" in proof_status
                    or bool(value.get("manual_send_receipt_available"))
                    or bool(value.get("proof_capture_provided"))
                )
                if proof_confirmed and value.get("file_backed_proof") is False:
                    add_tension(
                        tensions,
                        title="Manual proof confirmation lacks file-backed proof",
                        detail=f"{path_label(path)} reports proof confirmation but file_backed_proof=false.",
                        source_refs_value=[ref],
                    )

            package_status = clean_text(value.get("status") or value.get("pdf_export_rail_status")).upper()
            if "PDF_EXPORT_PACKAGE_READY" in package_status:
                missing = [
                    key
                    for key in ("invoice_id", "selected_sheet_label", "output_bridge_path")
                    if not value.get(key)
                ]
                if missing:
                    add_tension(
                        tensions,
                        title="PDF export package missing required fields",
                        detail=f"{path_label(path)} is PDF export ready but missing: {', '.join(missing)}.",
                        source_refs_value=[ref],
                    )

            if clean_text(value.get("status")).upper() == "INVALID_PLACEHOLDER" or value.get("trusted_as_selected_invoice_artifact") is False:
                path_value = value.get("path") or value.get("pc_reference_path") or value.get("mac_path")
                if path_value:
                    add_tension(
                        tensions,
                        title="Artifact placeholder is not selected-invoice proof",
                        detail=f"{clean_text(path_value)} is marked {clean_text(value.get('status'))} and not trusted as selected invoice artifact.",
                        source_refs_value=[ref],
                    )

    return tuple(tensions)


def collect_known_unknowns(sources: dict[str, SourceInput]) -> tuple[str, ...]:
    unknowns: list[str] = []
    for source in sources.values():
        payload = source.payload
        if payload is None:
            continue
        ref = source_ref(source)
        for path, value in walk_json(payload):
            if isinstance(value, dict):
                if clean_text(value.get("status")).upper() == "UNKNOWN" or clean_text(value.get("canonical_status")).upper() == "UNKNOWN":
                    question = value.get("question") or value.get("unknown_id")
                    if not question and any("unknown" in part.lower() for part in path):
                        question = value.get("display_name") or value.get("title") or value.get("summary")
                    if question:
                        unknowns.append(f"{clean_text(question)} [{source.relative_path}]")
                for key in ("known_unknowns", "unknowns"):
                    if key in value and isinstance(value[key], list):
                        for item in value[key]:
                            if isinstance(item, dict):
                                question = item.get("question") or item.get("unknown_id") or item.get("title") or item.get("summary")
                                if question:
                                    unknowns.append(f"{question} [{source.relative_path}]")
                            else:
                                unknowns.append(f"{item} [{source.relative_path}]")
                if "known_unknowns_ledger" in value and isinstance(value["known_unknowns_ledger"], dict):
                    ledger = value["known_unknowns_ledger"]
                    for key in ("missing_proof", "capability_gaps", "operator_decisions_required", "required_facts", "unsafe_claims"):
                        for item in as_list(ledger.get(key)):
                            unknowns.append(f"{key}: {item} [{source.relative_path}]")
        if not source.exists:
            unknowns.append(f"Input missing: {ref}")
    return unique(unknowns, limit=80)


def collect_top_actions(sources: dict[str, SourceInput]) -> tuple[str, ...]:
    actions: list[str] = []
    topology = sources.get("estate_topology_registry")
    if topology and isinstance(topology.payload, dict):
        for item in sorted(as_list(topology.payload.get("recommended_actions")), key=lambda row: row.get("priority", 999) if isinstance(row, dict) else 999):
            if isinstance(item, dict):
                actions.append(f"{item.get('action')} ({item.get('status')}; owner {item.get('owner_hint')})")

    live = sources.get("live_arts_md_invoice_review_bundle")
    if live and isinstance(live.payload, dict):
        bundle = live.payload.get("live_arts_md_bundle", live.payload)
        if isinstance(bundle, dict):
            if bundle.get("next_safe_move"):
                actions.append(f"Live Arts MD: {bundle.get('next_safe_move')}")
            for blocker in as_list(bundle.get("blockers"))[:3]:
                actions.append(f"Live Arts MD blocker: {blocker}")

    capital = sources.get("invoice_review_bundle")
    if capital and isinstance(capital.payload, dict):
        bundle = capital.payload.get("capital_hilton_bundle", capital.payload)
        if isinstance(bundle, dict):
            for blocker in as_list(bundle.get("blockers"))[:4]:
                actions.append(f"Capital Hilton: {blocker}")
            safe_next = get_path(bundle, "guardian_approval_request.safe_next_move")
            if safe_next:
                actions.append(f"Capital Hilton: {safe_next}")

    handoff = sources.get("hermes_chief_build_handoff")
    if handoff and isinstance(handoff.payload, dict):
        for item in as_list(handoff.payload.get("recommended_chief_tasks")):
            if isinstance(item, dict) and item.get("priority") in {"CRITICAL", "HIGH"}:
                actions.append(f"Chief {item.get('priority')}: {item.get('title')}")

    terrain = sources.get("work_terrain_build_cue_reconciliation_queue")
    if terrain and isinstance(terrain.payload, dict):
        for item in as_list(terrain.payload.get("priority_assessments")) + as_list(terrain.payload.get("default_priority_assessments")):
            if isinstance(item, dict) and item.get("recommended_priority") == "BUILD_NOW":
                actions.append(f"Build cue: {item.get('priority_id')} - {item.get('priority_reason')}")
        for item in as_list(terrain.payload.get("default_candidates")):
            if isinstance(item, dict) and item.get("ready_to_build") is True:
                actions.append(f"Build cue: {item.get('title')} - {item.get('next_safe_move')}")

    return unique(actions, limit=12)


def page_status_from_sources(required_sources: Iterable[SourceInput], *, fallback: str = "PARTIAL") -> str:
    required = list(required_sources)
    if any(not source.exists or source.error for source in required):
        return "UNKNOWN"
    return fallback


def source_missing_unknowns(sources: dict[str, SourceInput], ids: Iterable[str]) -> tuple[str, ...]:
    items = []
    for source_id in ids:
        source = sources.get(source_id)
        if source and not source.exists:
            items.append(f"Missing input: {source.relative_path}")
        elif source and source.error:
            items.append(f"Unreadable input: {source.relative_path}: {source.error}")
    return tuple(items)


def tension_texts(tensions: Iterable[TensionSignal], source_id_hints: Iterable[str] = ()) -> tuple[str, ...]:
    hints = tuple(source_id_hints)
    values = []
    for tension in tensions:
        joined = " ".join(tension.source_refs)
        if not hints or any(hint in joined for hint in hints):
            values.append(f"{tension.title}: {tension.detail}")
    return unique(values, limit=12)


def render_page(page: WikiPage, generated_at: str) -> str:
    lines = [
        f"# {page.title}",
        "",
        f"Status: {page.status}",
        "",
        "## Short human summary",
        clean_text(page.summary, limit=600),
        "",
        "## Confirmed facts",
        *bullet_lines(page.confirmed_facts),
        "",
        "## Known unknowns",
        *bullet_lines(page.known_unknowns),
        "",
        "## Tension / contradiction signals",
        *bullet_lines(page.tensions),
        "",
        "## Next useful actions",
        *bullet_lines(page.next_actions),
        "",
        "## What not to do",
        *bullet_lines(page.what_not_to_do),
        "",
        "## Source refs / input read-model refs",
        *bullet_lines(page.source_refs),
        "",
        f"Last generated timestamp: {generated_at}",
        "",
        FOOTER,
        "",
    ]
    return "\n".join(lines)


def build_pages(
    *,
    sources: dict[str, SourceInput],
    tensions: tuple[TensionSignal, ...],
    known_unknowns: tuple[str, ...],
    generated_at: str,
) -> tuple[WikiPage, ...]:
    topology = sources.get("estate_topology_registry")
    topology_payload = topology.payload if topology else None
    resolver = sources.get("reference_resolver")
    resolver_payload = resolver.payload if resolver else None
    external_registry = sources.get("external_system_knowledge_registry_index")
    external_registry_payload = external_registry.payload if external_registry else None
    live_source = sources.get("live_arts_md_invoice_review_bundle")
    live_payload = live_source.payload if live_source else None
    live_bundle = live_payload.get("live_arts_md_bundle", live_payload) if isinstance(live_payload, dict) else {}
    capital_source = sources.get("invoice_review_bundle")
    capital_payload = capital_source.payload if capital_source else None
    capital_bundle = capital_payload.get("capital_hilton_bundle", capital_payload) if isinstance(capital_payload, dict) else {}
    hermes = sources.get("hermes_mission_sentinel")
    hermes_payload = hermes.payload if hermes else None
    handoff = sources.get("hermes_chief_build_handoff")
    handoff_payload = handoff.payload if handoff else None
    charter = sources.get("purpose_bound_automation_charter")
    gravity = sources.get("hermes_gravity_controller")
    deferred = sources.get("chief_dynamic_workflow_deferred_build")
    audit_freshness = business_object_audit_freshness(sources)
    audit_facts = audit_freshness_facts(audit_freshness)

    all_source_refs = tuple(source_ref(source) for source in sources.values() if source.exists)
    missing_source_unknowns = tuple(f"{source.relative_path} is missing" for source in sources.values() if not source.exists)
    top_actions = collect_top_actions(sources)

    pages: list[WikiPage] = []

    pages.append(
        WikiPage(
            title="OpenClaw Context Wiki",
            filename="README.md",
            status="CONFIRMED",
            summary="This is a generated, evidence-grounded Markdown view over local OpenClaw registries and read-models. It is for browsing and orientation only; registry/read-model/receipt sources win on every disagreement.",
            confirmed_facts=(
                SOURCE_OF_TRUTH_WARNING,
                "Regenerate with `python3 scripts/export_openclaw_context_wiki.py`.",
                "Compiler v0 does not use an LM and does not synthesize unsupported claims.",
                "The compiler writes generated wiki pages plus generated/read_models/openclaw_context_wiki_index.json and generated/read_models/openclaw_context_wiki_index_OPERATOR.md.",
                "The compiler boundary flags explicitly deny service starts, email, browser, Coupa, workbook reads, PDF export, ledger mutation, production mutation, and git publication.",
                f"Pages generated: {len(PAGE_OUTPUTS)}.",
                *audit_facts,
            ),
            known_unknowns=missing_source_unknowns,
            tensions=tension_texts(tensions),
            next_actions=(
                "Regenerate after upstream registries/read-models change.",
                "Fix upstream registries or read-models when the wiki disagrees with evidence.",
                "Review generated/read_models/openclaw_context_wiki_index_OPERATOR.md for a compact operator summary.",
            ),
            what_not_to_do=(
                "Do not manually edit generated wiki pages as source truth.",
                "Do not use the wiki to override SQLite registries, read-models, or receipts.",
                "Do not infer sent, paid, approved, exported, submitted, or reachable states without source evidence.",
                "Do not add live automation or LM calls to v0.",
            ),
            source_refs=all_source_refs,
        )
    )

    overview_facts: list[str] = []
    if isinstance(topology_payload, dict):
        summary = topology_payload.get("topology_summary", {})
        overview_facts.extend(
            [
                f"Current topology repos: {summary.get('actual_repos')}",
                f"PC backend working copy: {summary.get('pc_backend_working_copy')}",
                f"Mac app working copy: {summary.get('mac_app_working_copy')}",
                f"Bridge transport: {summary.get('bridge_transport')}",
                f"Codex Web artifacts are source truth: {summary.get('codex_web_artifacts_are_source_truth')}",
            ]
        )
        for item in as_list(topology_payload.get("repo_working_copies")):
            if isinstance(item, dict):
                overview_facts.append(
                    f"{item.get('working_copy_id')}: {item.get('repo_name')} on {item.get('machine_id')} as {item.get('classification')} ({item.get('worktree_status')}, remote {item.get('remote_status')})."
                )
        for artifact in as_list(topology_payload.get("codex_web_artifacts")):
            if isinstance(artifact, dict) and clean_text(artifact.get("canonical_status")).upper() == "UNREACHABLE":
                overview_facts.append(
                    f"Codex Web commit {artifact.get('commit_ref')} for {artifact.get('repo_name')} is UNREACHABLE and not installed source truth."
                )
    pages.append(
        WikiPage(
            title="System Overview",
            filename="System Overview.md",
            status=page_status_from_sources([sources["estate_topology_registry"]], fallback="PARTIAL"),
            summary="OpenClaw is currently described as a PC backend/read-model workspace plus Mac app, Mac edge/helper responsibilities, openclaw-eyes context, openclaw-runtime actor work, and a bridge transport layer.",
            confirmed_facts=tuple(overview_facts) + audit_facts,
            known_unknowns=tuple(item for item in known_unknowns if any(marker in item.lower() for marker in ("runtime", "mac", "codex", "repo", "bridge"))) + source_missing_unknowns(sources, ("estate_topology_registry",)),
            tensions=tension_texts(tensions, ("estate_topology_registry", "reference_resolver")),
            next_actions=top_actions[:5],
            what_not_to_do=(
                "Do not treat Codex Web unreachable commits as installed code.",
                "Do not route Swift app ownership into the PC backend by convenience.",
                "Do not collapse bridge transport into source truth.",
            ),
            source_refs=source_refs(sources, ("estate_topology_registry", "reference_resolver", "estate_topology", "openclaw_estate_node_registry", "business_object_layer_audit")),
        )
    )

    registry_facts = [
        "OpenClaw context v0 is deterministic registry/read-model/receipt work, not generic vector RAG.",
        "The generated wiki is a compiled view over those structures and does not become source truth.",
        *audit_facts,
    ]
    if isinstance(topology_payload, dict):
        for item in as_list(topology_payload.get("registry_presence")):
            if isinstance(item, dict) and item.get("registry_id") == "evidence_grounded_context_registry":
                registry_facts.append(
                    f"Evidence-Grounded Context Registry status: {item.get('status')} on {item.get('branch_name')} at {item.get('commit_ref')}."
                )
                registry_facts.append(f"Registry notes: {item.get('notes')}")
    if isinstance(external_registry_payload, dict):
        if clean_text(external_registry_payload.get("import_status")).upper() == "IMPORTED":
            registry_facts.append(
                "openclaw-eyes system knowledge registry imported as read-only external input."
            )
            registry_facts.append(
                f"External registry source: {external_registry_payload.get('source_repo')} main at {external_registry_payload.get('source_commit')}."
            )
        elif external_registry_payload.get("reason"):
            registry_facts.append(
                f"External registry import status: {external_registry_payload.get('import_status')} ({external_registry_payload.get('reason')})."
            )
    registry_source_refs = source_refs(
        sources,
        (
            "estate_topology_registry",
            "reference_resolver",
            "external_system_knowledge_registry_index",
            "business_object_layer_audit",
            "openclaw_system_knowledge_registry_files",
        ),
    ) + source_refs_with_prefixes(sources, ("openclaw_system_knowledge_registry_",))
    pages.append(
        WikiPage(
            title="Evidence-Grounded Context Registry",
            filename="Evidence-Grounded Context Registry.md",
            status="PARTIAL" if isinstance(topology_payload, dict) else "UNKNOWN",
            summary="The context layer is intended to stay deterministic: stable registries, SQLite/read-model exports, receipts, proof references, and compiled Markdown views.",
            confirmed_facts=tuple(registry_facts),
            known_unknowns=tuple(item for item in known_unknowns if any(marker in item.lower() for marker in ("registry", "context", "canonical", "codex"))),
            tensions=tension_texts(tensions, ("estate_topology_registry", "openclaw_system_knowledge_registry")),
            next_actions=(
                "Keep external registry imports read-only and regenerate after canonical source changes.",
                "Record new facts upstream in registries/read-models/receipts, then regenerate the wiki.",
            ),
            what_not_to_do=(
                "Do not introduce generic vector RAG or LM synthesis in v0.",
                "Do not hardcode volatile branch commits as source truth.",
                "Do not smooth over contradictory source statuses.",
            ),
            source_refs=registry_source_refs,
        )
    )

    estate_facts: list[str] = []
    if isinstance(topology_payload, dict):
        for item in as_list(topology_payload.get("machines")):
            if isinstance(item, dict):
                estate_facts.append(
                    f"Machine {item.get('machine_id')}: {item.get('display_name')} - {item.get('machine_role')} ({item.get('evidence_status')})."
                )
        for item in as_list(topology_payload.get("source_of_truth_areas")):
            if isinstance(item, dict):
                estate_facts.append(
                    f"{item.get('display_name')}: owner={item.get('owner_repo_key')} / {item.get('owner_classification')}; status={item.get('status')}; rule={item.get('ownership_rule')}"
                )
        for item in as_list(topology_payload.get("bridge_paths")):
            if isinstance(item, dict):
                estate_facts.append(
                    f"Bridge {item.get('bridge_id')}: {item.get('local_path')} on {item.get('machine_id')} status {item.get('access_status')}."
                )
    pages.append(
        WikiPage(
            title="Estate Topology",
            filename="Estate Topology.md",
            status=page_status_from_sources([sources["estate_topology_registry"]], fallback="PARTIAL"),
            summary="The estate topology page summarizes machines, working copies, ownership areas, bridge paths, and unresolved topology questions from the topology registry/read-model.",
            confirmed_facts=tuple(estate_facts),
            known_unknowns=tuple(item for item in known_unknowns if any(marker in item.lower() for marker in ("topology", "repo", "runtime", "mac", "bridge", "canonical"))),
            tensions=tension_texts(tensions, ("estate_topology_registry",)),
            next_actions=tuple(action for action in top_actions if any(marker in action.lower() for marker in ("topology", "mac", "registry", "bridge")))[:6],
            what_not_to_do=(
                "Do not duplicate source-of-truth ownership across PC and Mac without a registry rule.",
                "Do not treat mirror paths as canonical write locations.",
                "Do not build a cross-registry merge over unreachable registry state.",
            ),
            source_refs=source_refs(sources, ("estate_topology_registry_sqlite", "estate_topology_registry", "estate_topology", "openclaw_estate_node_registry")),
        )
    )

    resolver_facts: list[str] = []
    if isinstance(resolver_payload, dict):
        resolver_facts.extend(
            [
                f"Reference targets: {resolver_payload.get('target_count')}; resolutions: {resolver_payload.get('resolution_count')}; drift_count: {resolver_payload.get('drift_count')}.",
                "Stable refs live in canonical inputs; resolved volatile values live in generated read-models.",
            ]
        )
        for item in as_list(resolver_payload.get("git_branch_refs")):
            if isinstance(item, dict):
                resolver_facts.append(
                    f"{item.get('target_ref')}: branch={item.get('branch')}, head={item.get('current_head_commit')}, remote={item.get('remote_status')}, local={item.get('local_status')}, dirty={item.get('dirty_status')}, Mac mirror={item.get('mac_mirror_status')}."
                )
        for item in as_list(resolver_payload.get("reference_resolutions")):
            if isinstance(item, dict):
                resolver_facts.append(
                    f"Resolution {item.get('target_ref')}: status={item.get('resolved_status')}, value={item.get('resolved_value')}."
                )
        for rule in as_list(resolver_payload.get("rules")):
            resolver_facts.append(f"Rule: {rule}")
    pages.append(
        WikiPage(
            title="Reference Resolver",
            filename="Reference Resolver.md",
            status=page_status_from_sources([sources["reference_resolver"]], fallback="PARTIAL"),
            summary="The resolver separates stable references from volatile resolved values and records drift, unreachable paths, dirty working copies, and mirror status.",
            confirmed_facts=tuple(resolver_facts),
            known_unknowns=tuple(item for item in known_unknowns if any(marker in item.lower() for marker in ("resolver", "branch", "path", "mirror", "bridge"))),
            tensions=tension_texts(tensions, ("reference_resolver",)),
            next_actions=(
                "Resolve Mac bridge/mirror availability before trusting mirrored read-model state.",
                "Investigate any resolver drift before consuming resolved values downstream.",
                "Keep branch refs stable and resolve commits at export time.",
            ),
            what_not_to_do=(
                "Do not fetch, pull, push, or mutate repos from this wiki compiler.",
                "Do not copy dirty working-copy state as source truth.",
                "Do not manually hardcode resolved branch commits into canonical source fields.",
            ),
            source_refs=source_refs(sources, ("reference_resolver_sqlite", "reference_resolver", "estate_topology_registry")),
        )
    )

    live_facts: list[str] = []
    live_unknowns: list[str] = []
    if isinstance(live_bundle, dict):
        selected = get_path(live_bundle, "invoice_selection.selected_invoice_candidate") or get_path(
            live_bundle, "candidate_selection_rail.selected_invoice_candidates", [{}]
        )[0]
        if isinstance(selected, dict):
            live_facts.append(
                f"Selected invoice candidate: {selected.get('invoice_id')} / {selected.get('work_type')} / {selected.get('amount_display')} / sheet {selected.get('sheet_label')} / selection {selected.get('selection_status')}."
            )
            live_facts.append(
                "Selected invoice state: "
                f"sent={clean_text(selected.get('sent'))}, "
                f"paid={clean_text(selected.get('paid'))}, "
                f"submitted={clean_text(selected.get('submitted'))}, "
                f"ledger_posted={clean_text(selected.get('ledger_posted'))}, "
                f"receipt_status={selected.get('receipt_status')}."
            )
        proof = live_bundle.get("manual_send_proof") or get_path(live_bundle, "client_comms_thread.manual_send_proof")
        if isinstance(proof, dict):
            live_facts.append(
                f"Manual send metadata exists for invoice {proof.get('invoice_id')} at {proof.get('sent_timestamp')}; "
                f"proof_status={proof.get('proof_status')}; "
                f"file_backed_proof={clean_text(proof.get('file_backed_proof'))}; "
                f"receipt_received={clean_text(proof.get('receipt_received'))}."
            )
            for missing in as_list(proof.get("missing_required_fields")):
                live_unknowns.append(f"Manual send proof missing field: {missing}")
        payment = live_bundle.get("payment_watch")
        if isinstance(payment, dict):
            live_facts.append(
                f"Payment watch: {payment.get('payment_watch_status')}; "
                f"ledger_match_status={payment.get('ledger_match_status')}; "
                f"bank read performed={clean_text(payment.get('bank_ledger_read_performed'))}."
            )
        pdf_package = get_path(live_bundle, "invoice_artifact.pdf_export_package")
        if isinstance(pdf_package, dict):
            live_facts.append(
                f"PDF export package status: {pdf_package.get('status')}; "
                f"request_payload_ready={clean_text(pdf_package.get('request_payload_ready'))}; "
                f"execution_venue={pdf_package.get('execution_venue')}; "
                f"required_capability={pdf_package.get('required_capability')}."
            )
            live_facts.append(
                f"PDF output refs: Mac={pdf_package.get('output_mac_path')}; PC={pdf_package.get('output_pc_reference_path')}; source workbook={pdf_package.get('source_workbook_mac_path')}."
            )
        artifact = live_bundle.get("invoice_artifact")
        if isinstance(artifact, dict):
            live_facts.append(
                f"Invoice artifact: review_status={artifact.get('artifact_review_status')}; "
                f"attachment_ready={clean_text(artifact.get('attachment_ready'))}; "
                f"trusted selected artifact present={clean_text(get_path(artifact, 'known_artifact_guardrails.trusted_selected_invoice_artifact_present'))}."
            )
        for blocker in as_list(live_bundle.get("blockers")):
            live_unknowns.append(f"Blocker: {blocker}")
    pages.append(
        WikiPage(
            title="Live Arts MD Invoice Automation",
            filename="Live Arts MD Invoice Automation.md",
            status=page_status_from_sources([sources["live_arts_md_invoice_review_bundle"]], fallback="PARTIAL"),
            summary="Live Arts MD has selected-invoice and manual-send metadata, but source evidence keeps proof, attachment readiness, payment watch, and ledger state gated.",
            confirmed_facts=tuple(live_facts),
            known_unknowns=tuple(live_unknowns),
            tensions=tension_texts(tensions, ("live_arts_md_invoice_review_bundle",)),
            next_actions=(
                "Capture sent-email screenshot or sent-mail proof for invoice 2026-1001.",
                "Confirm recipient/contact evidence before claiming send readiness.",
                "Use the Mac Excel PDF edge path only as a scoped export package with operator review after export.",
                "Keep payment watch readiness-only until send/manual proof exists.",
            ),
            what_not_to_do=(
                "Do not claim OpenClaw sent the invoice.",
                "Do not claim file-backed manual-send proof exists while file_backed_proof=false.",
                "Do not claim PDF export completed just because a Mac package is ready.",
                "Do not mark paid, submitted, ledger-posted, or attachment-ready without receipts.",
                "Do not add Coupa/PO blockers to Live Arts unless a source read-model says the client requires them.",
            ),
            source_refs=source_refs(sources, ("live_arts_md_invoice_review_bundle", "hermes_mission_sentinel", "hermes_chief_build_handoff")),
        )
    )

    capital_facts: list[str] = []
    capital_unknowns: list[str] = []
    if isinstance(capital_bundle, dict):
        capital_facts.append(f"Bundle id: {capital_bundle.get('bundle_id')}; client_ref={capital_bundle.get('client_ref')}.")
        approval_footer = capital_bundle.get("approval_footer", {})
        if isinstance(approval_footer, dict):
            capital_facts.append(
                f"Approval ready: {approval_footer.get('approval_ready')}; disabled reasons: {approval_footer.get('approval_disabled_reasons')}."
            )
        coupa = capital_bundle.get("coupa_invoice_proof") or capital_bundle.get("supplier_portal_invoice_submission")
        if isinstance(coupa, dict):
            capital_facts.append(
                f"Supplier portal proof: provider={coupa.get('supplier_portal_provider')}; required={coupa.get('supplier_portal_required') or coupa.get('required')}; status={coupa.get('status') or coupa.get('portal_submission_proof_status')}."
            )
        artifact = capital_bundle.get("excel_invoice_artifact")
        if isinstance(artifact, dict):
            capital_facts.append(
                f"Excel invoice artifact: {artifact.get('display_name')}; attachment_ready={artifact.get('attachment_ready')}; proof_status={artifact.get('proof_status')}; linkage_status={artifact.get('linkage_status')}."
            )
            capital_facts.append(f"Artifact refs: Mac={artifact.get('mac_visible_ref')}; PC={artifact.get('pc_bridge_ref')}.")
        selection = capital_bundle.get("invoice_selection")
        if isinstance(selection, dict):
            capital_facts.append(
                f"Invoice selection: active_workbook_state={selection.get('active_workbook_state')}; operator_approval={get_path(selection, 'execution_boundary.operator_approval')}; portal execution={get_path(selection, 'workflow_progress.portal_submission_execution_status')}."
            )
        for blocker in as_list(capital_bundle.get("blockers")):
            capital_unknowns.append(f"Blocker: {blocker}")
    pages.append(
        WikiPage(
            title="Capital Hilton Invoice Workflow",
            filename="Capital Hilton Invoice Workflow.md",
            status="BLOCKED" if isinstance(capital_bundle, dict) else "UNKNOWN",
            summary="Capital Hilton remains a complex, proof-gated invoice workflow: Coupa/supplier portal proof, selected invoice/page evidence, artifact linkage, recipients, and approvals are not complete.",
            confirmed_facts=tuple(capital_facts),
            known_unknowns=tuple(capital_unknowns),
            tensions=tension_texts(tensions, ("invoice_review_bundle",)),
            next_actions=(
                "Select or confirm the current invoice page/period before treating the artifact as current.",
                "Capture supplier portal/Coupa proof as proof intake only; no portal submission authority is granted here.",
                "Link or regenerate artifact evidence only through metadata/proof receipts.",
                "Keep approval blocked until prerequisite receipts exist.",
            ),
            what_not_to_do=(
                "Do not claim Coupa submitted or supplier portal proof exists while proof status is missing/requested.",
                "Do not treat the candidate Excel artifact as attachment-ready without linkage receipts.",
                "Do not send email or mark approval based on draft text.",
                "Do not read workbook cells or mutate the workbook from this wiki layer.",
            ),
            source_refs=source_refs(sources, ("invoice_review_bundle",)),
        )
    )

    hermes_facts: list[str] = []
    hermes_unknowns: list[str] = []
    if isinstance(hermes_payload, dict):
        hermes_facts.append(
            f"Hermes mission status: {hermes_payload.get('contract_status')}; automation_ready_status={hermes_payload.get('automation_ready_status')}; urgent_goal={hermes_payload.get('urgent_goal')}."
        )
        for item in as_list(hermes_payload.get("critical_path")):
            if isinstance(item, dict):
                hermes_facts.append(f"Mission critical path: {item.get('title')} -> {item.get('status')} ({item.get('required_receipt')}).")
        for blocker in as_list(hermes_payload.get("current_blockers")):
            hermes_unknowns.append(f"Hermes blocker: {blocker}")
    if isinstance(handoff_payload, dict):
        hermes_facts.append(f"Chief handoff status: {handoff_payload.get('contract_status')}; handoff_ref={handoff_payload.get('handoff_ref')}.")
        for task in as_list(handoff_payload.get("recommended_chief_tasks"))[:6]:
            if isinstance(task, dict):
                hermes_facts.append(f"Chief task {task.get('priority')}: {task.get('title')} -> {task.get('target_repo')}.")
        for gap in as_list(handoff_payload.get("build_gaps")):
            hermes_unknowns.append(f"Chief build gap: {gap}")
    if charter and isinstance(charter.payload, dict):
        hermes_facts.append(f"Purpose-bound charter rows: {len(as_list(charter.payload.get('charter_rows')))}.")
    if gravity and isinstance(gravity.payload, dict):
        hermes_facts.append(f"Hermes gravity controller: {gravity.payload.get('contract_status')}; charter_count={get_path(gravity.payload, 'charter_lookup.charter_count')}.")
    if deferred and isinstance(deferred.payload, dict):
        hermes_facts.append(f"Deferred Chief dynamic workflow: {deferred.payload.get('status')}; preferred_model={deferred.payload.get('preferred_model')}.")
        for item in as_list(get_path(deferred.payload, "known_unknowns_ledger.missing_proof")):
            hermes_unknowns.append(f"Deferred missing proof: {item}")
    pages.append(
        WikiPage(
            title="Hermes and Chief",
            filename="Hermes and Chief.md",
            status="PARTIAL" if any(source.exists for source in (hermes or [], handoff or [])) else "UNKNOWN",
            summary="Hermes and Chief read-models currently describe deterministic mission focus, purpose-bound gravity, build handoff, and deferred workflow work without production authority.",
            confirmed_facts=tuple(hermes_facts) + audit_facts,
            known_unknowns=tuple(hermes_unknowns),
            tensions=tension_texts(tensions, ("hermes", "chief", "purpose_bound", "gravity")),
            next_actions=(
                "Use registry/wiki context to avoid duplicate work before Chief picks tasks.",
                "Keep Chief build work receipt/test focused and separated from production execution.",
                "Route unsafe or unclear work back to Hermes/Guardian/operator review.",
            ),
            what_not_to_do=(
                "Do not start live agents from the wiki.",
                "Do not let Chief handoff tasks imply email, Coupa, ledger, runtime, or workbook authority.",
                "Do not duplicate a deferred workflow build if a registry/read-model already owns it.",
            ),
            source_refs=source_refs(
                sources,
                (
                    "hermes_mission_sentinel",
                    "hermes_chief_build_handoff",
                    "purpose_bound_automation_charter",
                    "hermes_gravity_controller",
                    "chief_dynamic_workflow_deferred_build",
                    "business_object_layer_audit",
                ),
            ),
        )
    )

    mac_facts: list[str] = []
    mac_unknowns: list[str] = []
    if isinstance(topology_payload, dict):
        for area in as_list(topology_payload.get("source_of_truth_areas")):
            if isinstance(area, dict) and area.get("area_id") in {"mac_excel_edge_worker", "access_broker", "bridge_mirror_transport", "mission_control_app"}:
                mac_facts.append(
                    f"{area.get('display_name')}: owner={area.get('owner_repo_key')} / {area.get('owner_classification')}; status={area.get('status')}; rule={area.get('ownership_rule')}"
                )
                if area.get("status") != "CONFIRMED":
                    mac_unknowns.append(f"{area.get('display_name')} remains {area.get('status')}: {area.get('notes')}")
    if isinstance(live_bundle, dict):
        pdf_package = get_path(live_bundle, "invoice_artifact.pdf_export_package")
        if isinstance(pdf_package, dict):
            mac_facts.append(
                f"Mac Excel PDF edge worker package: required_capability={pdf_package.get('required_capability')}; execution_venue={pdf_package.get('execution_venue')}; no_workbook_cell_read={pdf_package.get('no_workbook_cell_read')}."
            )
        storage_policy = get_path(live_bundle, "developer_end_to_end_card.artifact_storage_policy")
        if isinstance(storage_policy, dict):
            mac_facts.append(
                f"Access requirements: {storage_policy.get('access_required')}; permission repair action={storage_policy.get('permission_repair_action')}."
            )
    pages.append(
        WikiPage(
            title="Mac Edge Workers",
            filename="Mac Edge Workers.md",
            status="PARTIAL" if mac_facts else "UNKNOWN",
            summary="Mac edge work is represented as scoped local execution/helper responsibility. PC emits safe packages/read-models; Mac owns Excel/PDF helper and app-side permission architecture.",
            confirmed_facts=tuple(mac_facts),
            known_unknowns=tuple(mac_unknowns) + tuple(item for item in known_unknowns if "mac" in item.lower()),
            tensions=tension_texts(tensions, ("reference_resolver", "estate_topology_registry", "live_arts_md_invoice_review_bundle")),
            next_actions=(
                "Resolve Access Broker/helper permission shape before retrying Mac Excel export.",
                "Keep Mac helper work local, scoped, and receipt-backed.",
                "Mirror generated read-models only after bridge access is verified.",
            ),
            what_not_to_do=(
                "Do not run Mac Excel/PDF export from the PC wiki compiler.",
                "Do not make Mac local paths reachable claims from PC when resolver marks them unreachable.",
                "Do not grant UI, helper, or file permissions implicitly.",
            ),
            source_refs=source_refs(sources, ("estate_topology_registry", "reference_resolver", "live_arts_md_invoice_review_bundle")),
        )
    )

    pages.append(
        WikiPage(
            title="Known Unknowns",
            filename="Known Unknowns.md",
            status="UNKNOWN" if known_unknowns else "CONFIRMED",
            summary="This page aggregates explicit unknowns, missing proof, unavailable inputs, and fail-closed states surfaced by the local registries/read-models.",
            confirmed_facts=(
                f"Known unknown count: {len(known_unknowns)}.",
                "Unknowns are not resolved by prose; upstream evidence must change.",
            ),
            known_unknowns=known_unknowns,
            tensions=tension_texts(tensions),
            next_actions=(
                "Resolve unknowns in the owning registry/read-model or receipt source.",
                "Prefer operator confirmation only when repo evidence says operator memory/review is required.",
                "Regenerate after upstream evidence changes.",
            ),
            what_not_to_do=(
                "Do not infer answers to unknowns in generated Markdown.",
                "Do not treat missing inputs as present.",
                "Do not erase contradictions for readability.",
            ),
            source_refs=all_source_refs,
        )
    )

    urgent: list[str] = []
    soon: list[str] = []
    later: list[str] = []
    do_not: list[str] = []
    if isinstance(handoff_payload, dict):
        for task in as_list(handoff_payload.get("recommended_chief_tasks")):
            if not isinstance(task, dict):
                continue
            line = f"{task.get('priority')}: {task.get('title')} - {task.get('why_it_matters')}"
            if task.get("priority") == "CRITICAL":
                urgent.append(line)
            elif task.get("priority") == "HIGH":
                soon.append(line)
            else:
                later.append(line)
    if isinstance(topology_payload, dict):
        for item in as_list(topology_payload.get("recommended_actions")):
            if not isinstance(item, dict):
                continue
            line = f"P{item.get('priority')}: {item.get('action')} - {item.get('reason')}"
            priority = item.get("priority", 99)
            if priority <= 2:
                urgent.append(line)
            elif priority <= 5:
                soon.append(line)
            else:
                later.append(line)
    terrain = sources.get("work_terrain_build_cue_reconciliation_queue")
    if terrain and isinstance(terrain.payload, dict):
        for item in as_list(terrain.payload.get("default_candidates")):
            if not isinstance(item, dict):
                continue
            line = f"{item.get('title')}: {item.get('next_safe_move')}"
            if item.get("ready_to_build") is True:
                soon.append(line)
            elif item.get("blocked_reason"):
                later.append(f"{line} (blocked: {item.get('blocked_reason')})")
    posture = sources.get("build_now_vs_hold_queue_posture")
    if posture and isinstance(posture.payload, dict):
        for item in as_list(posture.payload.get("classified_items")):
            if not isinstance(item, dict):
                continue
            category = item.get("posture_category")
            line = f"{category}: {item.get('title')} - {item.get('next_safe_move')}"
            if category == "BUILD_NOW_READY":
                soon.append(line)
            elif category in {"HOLD_FOR_RIGHT_TIME", "NEEDS_CONTEXT", "NEEDS_PROOF", "UNKNOWN_FAIL_CLOSED"}:
                later.append(line)
            elif category in {"BLOCKED_AUTHORITY", "BLOCKED_SECURITY_THRESHOLD"}:
                do_not.append(line)
    if isinstance(hermes_payload, dict):
        for item in as_list(hermes_payload.get("do_not_spend_time_on")):
            do_not.append(f"Hermes says do not spend time now: {item}")

    build_order_facts = [
        *audit_facts,
        "Urgent: " + " | ".join(unique(urgent, limit=6)),
        "Soon: " + " | ".join(unique(soon, limit=8)),
        "Later: " + " | ".join(unique(later, limit=8)),
        "Do not work now: " + " | ".join(unique(do_not, limit=8)),
    ]
    pages.append(
        WikiPage(
            title="Build Order",
            filename="Build Order.md",
            status="PLANNED",
            summary="Ranked next work is derived from registry recommended actions, Hermes/Chief handoff tasks, work terrain build cues, and build-now/hold posture read-models.",
            confirmed_facts=tuple(build_order_facts),
            known_unknowns=tuple(item for item in known_unknowns if any(marker in item.lower() for marker in ("build", "chief", "operator", "proof", "context"))),
            tensions=tension_texts(tensions, ("hermes", "build_now", "work_terrain", "estate_topology")),
            next_actions=unique(urgent + soon, limit=10),
            what_not_to_do=unique(do_not, limit=10)
            or (
                "Do not convert build order into auto-execution authority.",
                "Do not work blocked authority lanes before explicit approval and proof gates exist.",
            ),
            source_refs=source_refs(
                sources,
                (
                    "estate_topology_registry",
                    "hermes_mission_sentinel",
                    "hermes_chief_build_handoff",
                    "business_object_layer_audit",
                    "build_now_vs_hold_queue_posture",
                    "work_terrain_build_cue_reconciliation_queue",
                ),
            ),
        )
    )

    expected = {page.filename for page in pages}
    missing_pages = set(PAGE_OUTPUTS) - expected
    if missing_pages:
        raise ValueError(f"compiler did not build pages: {sorted(missing_pages)}")
    return tuple(pages)


def page_index_entry(page: WikiPage, tensions: tuple[TensionSignal, ...]) -> dict[str, Any]:
    return {
        "title": page.title,
        "path": f"generated/wiki/openclaw/{page.filename}",
        "status": page.status,
        "known_unknown_count": len(page.known_unknowns),
        "tension_count": len(page.tensions),
        "source_refs": list(page.source_refs),
        "next_actions": list(page.next_actions[:5]),
    }


def source_input_record(source: SourceInput) -> dict[str, Any]:
    record = {
        "source_id": source.source_id,
        "label": source.label,
        "path": source.relative_path,
        "source_type": source.source_type,
        "exists": source.exists,
        "sha256": source.sha256,
    }
    if source.error:
        record["error"] = source.error
    if source.sqlite_summary:
        record["sqlite_summary"] = source.sqlite_summary
    return record


def build_index(
    *,
    pages: tuple[WikiPage, ...],
    sources: dict[str, SourceInput],
    tensions: tuple[TensionSignal, ...],
    known_unknowns: tuple[str, ...],
    generated_at: str,
) -> dict[str, Any]:
    top_actions = collect_top_actions(sources)
    audit_freshness = business_object_audit_freshness(sources)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "business_object_audit_freshness_status": audit_freshness["freshness_status"],
        "business_object_audit_generated_at": audit_freshness["generated_at"],
        "business_object_audit_inputs_tracked": audit_freshness["inputs_tracked"],
        "business_object_audit_missing_inputs": audit_freshness["missing_inputs"],
        "business_object_audit_stale_reasons": audit_freshness["stale_reasons"],
        "business_object_audit_freshness": audit_freshness,
        "pages": [page_index_entry(page, tensions) for page in pages],
        "source_inputs": [source_input_record(source) for source in sources.values() if source.exists],
        "missing_inputs": [source_input_record(source) for source in sources.values() if not source.exists],
        "contradiction_count": len(tensions),
        "contradictions": [
            {
                "title": tension.title,
                "detail": tension.detail,
                "source_refs": list(tension.source_refs),
            }
            for tension in tensions
        ],
        "known_unknown_count": len(known_unknowns),
        "known_unknowns": list(known_unknowns),
        "top_next_actions": list(top_actions),
        "source_of_truth_warning": SOURCE_OF_TRUTH_WARNING,
        "footer": FOOTER,
        "boundary_flags": dict(AUTHORITY_BOUNDARY_FLAGS),
    }


def format_operator_index(index: dict[str, Any]) -> str:
    pages = index.get("pages", [])
    tensions = index.get("contradictions", [])
    unknowns = index.get("known_unknowns", [])
    actions = index.get("top_next_actions", [])
    lines = [
        "# OpenClaw Context Wiki Index",
        "",
        f"Generated at: {index.get('generated_at')}",
        "",
        "Warning:",
        f"- {index.get('source_of_truth_warning')}",
        "",
        "Pages generated:",
    ]
    lines.extend(f"- {page.get('title')} ({page.get('status')}) - {page.get('path')}" for page in pages)
    lines.extend(["", "Key findings:"])
    lines.extend(
        bullet_lines(
            [
                f"Business-object audit freshness: {index.get('business_object_audit_freshness_status')}.",
                f"{index.get('contradiction_count')} tension/contradiction signals detected.",
                f"{index.get('known_unknown_count')} known unknowns detected.",
                f"{len(index.get('missing_inputs', []))} expected inputs are missing.",
                "Compiler boundary remains generated-view only; no live automation authority is added.",
            ]
        )
    )
    lines.extend(["", "Top next actions:"])
    lines.extend(bullet_lines(actions[:8]))
    lines.extend(["", "Important unknowns:"])
    lines.extend(bullet_lines(unknowns[:8]))
    lines.extend(["", "Tension signals:"])
    lines.extend(bullet_lines([f"{item.get('title')}: {item.get('detail')}" for item in tensions[:8]]))
    lines.extend(
        [
            "",
            "How to regenerate:",
            "- `python3 scripts/export_openclaw_context_wiki.py`",
            "",
            FOOTER,
            "",
        ]
    )
    return "\n".join(lines)


def compile_openclaw_context_wiki(
    *,
    repo_root: str | Path = ROOT,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    system_knowledge_root: str | Path = DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
    external_registry_root: str | Path = DEFAULT_EXTERNAL_REGISTRY_ROOT,
    wiki_root: str | Path = DEFAULT_WIKI_ROOT,
    generated_at: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    repo = Path(repo_root)
    timestamp = generated_at or utc_now()
    sources = load_sources(
        repo_root=repo,
        read_model_root=read_model_root,
        system_knowledge_root=system_knowledge_root,
        external_registry_root=external_registry_root,
    )
    tensions = detect_tensions(sources)
    known_unknowns = collect_known_unknowns(sources)
    pages = build_pages(
        sources=sources,
        tensions=tensions,
        known_unknowns=known_unknowns,
        generated_at=timestamp,
    )
    index = build_index(
        pages=pages,
        sources=sources,
        tensions=tensions,
        known_unknowns=known_unknowns,
        generated_at=timestamp,
    )
    operator_summary = format_operator_index(index)

    if write:
        wiki_dir = rooted(wiki_root, repo_root=repo)
        read_dir = rooted(read_model_root, repo_root=repo)
        wiki_dir.mkdir(parents=True, exist_ok=True)
        read_dir.mkdir(parents=True, exist_ok=True)
        for page in pages:
            (wiki_dir / page.filename).write_text(render_page(page, timestamp), encoding="utf-8")
        (read_dir / INDEX_JSON_NAME).write_text(stable_json(index), encoding="utf-8")
        (read_dir / OPERATOR_INDEX_NAME).write_text(operator_summary, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": timestamp,
        "pages": [page.filename for page in pages],
        "page_count": len(pages),
        "source_inputs_used": [source.relative_path for source in sources.values() if source.exists],
        "missing_inputs": [source.relative_path for source in sources.values() if not source.exists],
        "contradiction_count": len(tensions),
        "known_unknown_count": len(known_unknowns),
        "top_next_actions": list(collect_top_actions(sources)),
        "index": index,
        "operator_summary": operator_summary,
        "boundary_flags": dict(AUTHORITY_BOUNDARY_FLAGS),
    }


__all__ = [
    "AUTHORITY_BOUNDARY_FLAGS",
    "DEFAULT_EXTERNAL_REGISTRY_ROOT",
    "FOOTER",
    "INDEX_JSON_NAME",
    "OPERATOR_INDEX_NAME",
    "PAGE_OUTPUTS",
    "SCHEMA_VERSION",
    "SOURCE_OF_TRUTH_WARNING",
    "compile_openclaw_context_wiki",
    "detect_tensions",
    "load_sources",
    "stable_json",
]
