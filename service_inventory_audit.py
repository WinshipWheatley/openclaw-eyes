from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable


SERVICE_FREEZE_RELATIVE_PATH = Path("docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md")
SYSTEMD_USER_RELATIVE_PATH = Path("systemd/user")

SERVICE_INVENTORY_AUDIT_TYPE = "openclaw.service_inventory_audit"
SERVICE_INVENTORY_AUDIT_SCHEMA_VERSION = 1

DRIFT_CONTROL_SCHEDULER_ID = "drift-control-scan"
DRIFT_CONTROL_SCHEDULER_CLASSIFICATIONS = (
    "canonical_scheduler_owner",
    "disabled_deprecated_scheduler_path",
    "frozen_pending_owner_decision",
    "unknown_unowned_finding",
)
DRIFT_CONTROL_SCHEDULER_PATHS = (
    ("installed_systemd_timer", "openclaw-drift-control-scan.timer"),
    ("installed_systemd_service", "openclaw-drift-control-scan.service"),
    ("dashboard_cron_jobs_json", "dashboard_gen.py"),
)
LEGACY_OWNERSHIP_DISPOSITION_CLASSES = (
    "retired_dead_entrypoint",
    "frozen_pending_owner_decision",
    "replaced_by_systemd_owned_path",
    "retained_manual_only_refusal_or_dry_run",
    "unknown_unowned_finding",
)


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.find(marker)
    if start < 0:
        return ""
    next_heading = text.find("\n## ", start + len(marker))
    if next_heading < 0:
        return text[start:]
    return text[start:next_heading]


def _bullet_lines(section_text: str) -> list[str]:
    return [
        line[2:].strip()
        for line in section_text.splitlines()
        if line.startswith("- ") and line[2:].strip()
    ]


def _code_spans(text: str) -> list[str]:
    return [item.strip() for item in re.findall(r"`([^`]+)`", text) if item.strip()]


def _inventory_items(section_text: str) -> list[str]:
    items: list[str] = []
    for line in _bullet_lines(section_text):
        spans = _code_spans(line)
        if spans:
            items.extend(spans)
        else:
            items.append(line.rstrip("."))
    return list(dict.fromkeys(items))


def _cleanup_slice_order(section_text: str) -> list[dict[str, Any]]:
    order: list[dict[str, Any]] = []
    for line in section_text.splitlines():
        match = re.match(r"^\d+\.\s+Slice\s+(\d+):\s+(.+?)\s*$", line)
        if match:
            order.append({"slice": int(match.group(1)), "description": match.group(2)})
    return order


def _table_rows(section_text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 5 or cells[0].lower() == "service/process":
            continue
        item_spans = _code_spans(cells[0])
        rows.append({
            "item": item_spans[0] if item_spans else cells[0],
            "current_owner": cells[1],
            "allowed_control_path": cells[2],
            "forbidden_control_path": cells[3],
            "cleanup_status": cells[4],
        })
    return rows


def _legacy_disposition_rows(section_text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 8 or cells[0].lower() == "surface":
            continue
        surface_spans = _code_spans(cells[0])
        rows.append({
            "surface": surface_spans[0] if surface_spans else cells[0],
            "disposition_class": cells[1],
            "source_evidence": cells[2],
            "allowed_control_path": cells[3],
            "forbidden_control_path": cells[4],
            "runtime_mutation_allowed": cells[5].lower(),
            "live_inspection_required": cells[6].lower(),
            "next_action": cells[7],
        })
    return rows


def _is_script_surface(item: str) -> bool:
    normalized = item.strip()
    return normalized.endswith(".sh") or normalized.startswith("scripts/")


def _legacy_disposition_findings(
    rows: list[dict[str, str]],
    legacy_manual: Iterable[str],
    deprecated_frozen_controls: Iterable[str],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    valid_classes = set(LEGACY_OWNERSHIP_DISPOSITION_CLASSES)
    seen: set[str] = set()

    for row in rows:
        surface = row["surface"]
        if surface in seen:
            findings.append({
                "severity": "error",
                "finding": "duplicate_legacy_disposition_surface",
                "surface": surface,
            })
        seen.add(surface)

        disposition_class = row["disposition_class"]
        if disposition_class not in valid_classes:
            findings.append({
                "severity": "error",
                "finding": "invalid_legacy_disposition_class",
                "surface": surface,
                "disposition_class": disposition_class,
            })

        if row["runtime_mutation_allowed"] != "false":
            findings.append({
                "severity": "error",
                "finding": "legacy_runtime_mutation_allowed",
                "surface": surface,
                "runtime_mutation_allowed": row["runtime_mutation_allowed"],
            })

        if row["live_inspection_required"] != "false":
            findings.append({
                "severity": "error",
                "finding": "legacy_live_inspection_required",
                "surface": surface,
                "live_inspection_required": row["live_inspection_required"],
            })

        if disposition_class == "unknown_unowned_finding":
            findings.append({
                "severity": "warning",
                "finding": "legacy_unknown_unowned_finding",
                "surface": surface,
            })

    dispositioned = {row["surface"] for row in rows}
    for item in legacy_manual:
        if item not in dispositioned:
            findings.append({
                "severity": "error",
                "finding": "undispositioned_legacy_manual_surface",
                "surface": item,
            })

    for item in deprecated_frozen_controls:
        if _is_script_surface(item) and item not in dispositioned:
            findings.append({
                "severity": "error",
                "finding": "undispositioned_deprecated_script_surface",
                "surface": item,
            })

    return findings


def _template_unit_names(template_filenames: Iterable[str] | None) -> set[str]:
    names: set[str] = set()
    for filename in template_filenames or ():
        name = Path(str(filename)).name
        if name.endswith(".in"):
            name = name[:-3]
        if name:
            names.add(name)
    return names


def _repo_template_filenames(repo_root: Path) -> list[str]:
    template_dir = repo_root / SYSTEMD_USER_RELATIVE_PATH
    if not template_dir.is_dir():
        return []
    return sorted(path.name for path in template_dir.iterdir() if path.is_file())


def _pending_template_findings(
    rows: list[dict[str, str]],
    template_filenames: Iterable[str] | None,
) -> list[dict[str, Any]]:
    classifications = {
        item["item"]: item
        for item in _owner_classifications(rows, template_filenames)
    }
    findings: list[dict[str, Any]] = []
    for row in rows:
        row_text = " ".join(str(value) for value in row.values()).lower()
        if "without repo template" not in row_text and "no repo template" not in row_text:
            continue
        item = row["item"]
        classification = classifications[item]
        findings.append({
            "severity": "warning",
            "finding": "documented_installed_unit_without_repo_template",
            "item": item,
            "repo_template_present": classification["repo_template_present"],
            "documented_external_owner": classification["documented_external_owner"],
            "frozen_pending_template_decision": classification["frozen_pending_template_decision"],
            "unknown_unowned": classification["unknown_unowned"],
            "cleanup_status": row["cleanup_status"],
        })
    return findings


def _has_documented_external_owner(row_text: str) -> bool:
    if "pending documented external owner" in row_text:
        return False
    return "documented external owner:" in row_text or "external owner:" in row_text


def _owner_classifications(
    rows: list[dict[str, str]],
    template_filenames: Iterable[str] | None,
) -> list[dict[str, Any]]:
    template_units = _template_unit_names(template_filenames)
    classifications: list[dict[str, Any]] = []
    for row in rows:
        item = row["item"]
        row_text = " ".join(str(value) for value in row.values()).lower()
        repo_template_present = item in template_units
        missing_repo_template = "without repo template" in row_text or "no repo template" in row_text
        documented_external_owner = _has_documented_external_owner(row_text)
        frozen_pending_template_decision = missing_repo_template and (
            "frozen pending" in row_text
            or "pending a repo template" in row_text
            or "pending template/owner" in row_text
        )
        unknown_unowned = (
            not repo_template_present
            and not documented_external_owner
            and not frozen_pending_template_decision
        )
        classifications.append({
            "item": item,
            "repo_template_present": repo_template_present,
            "documented_external_owner": documented_external_owner,
            "frozen_pending_template_decision": frozen_pending_template_decision,
            "unknown_unowned": unknown_unowned,
            "cleanup_status": row["cleanup_status"],
        })
    return classifications


def _scheduler_path_classification(row_text: str) -> str:
    normalized = row_text.lower()
    if "disabled_deprecated_scheduler_path" in normalized or "disabled deprecated scheduler path" in normalized:
        return "disabled_deprecated_scheduler_path"
    if "canonical_scheduler_owner" in normalized and "none" not in normalized:
        return "canonical_scheduler_owner"
    if "frozen" in normalized or "pending" in normalized or "no canonical scheduler owner" in normalized:
        return "frozen_pending_owner_decision"
    return "unknown_unowned_finding"


def _drift_control_scheduler_classification(rows: list[dict[str, str]]) -> dict[str, Any]:
    rows_by_item = {row["item"]: row for row in rows}
    combined_row_text = "\n".join(" ".join(str(value) for value in row.values()) for row in rows).lower()
    paths: list[dict[str, Any]] = []

    for path_id, item in DRIFT_CONTROL_SCHEDULER_PATHS:
        row = rows_by_item.get(item)
        row_text = " ".join(str(value) for value in row.values()) if row else ""
        paths.append({
            "path": path_id,
            "item": item,
            "classification": _scheduler_path_classification(row_text),
            "cleanup_status": row["cleanup_status"] if row else "",
        })

    dual_scheduler_risk = (
        "running both drift-control cron and timer scheduling paths" in combined_row_text
        or (
            "drift-control" in combined_row_text
            and "running both" in combined_row_text
            and "cron" in combined_row_text
            and "timer" in combined_row_text
        )
    )

    return {
        "scheduler_id": DRIFT_CONTROL_SCHEDULER_ID,
        "canonical_scheduler_owner": None,
        "classification_values": list(DRIFT_CONTROL_SCHEDULER_CLASSIFICATIONS),
        "paths": paths,
        "dual_scheduler_risk": dual_scheduler_risk,
        "live_scheduler_inspection_allowed": False,
        "scheduler_mutation_allowed": False,
    }


def build_service_inventory_audit(
    *,
    freeze_text: str | None = None,
    repo_root: str | Path | None = None,
    template_filenames: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic advisory service inventory audit from explicit inputs."""
    source = "explicit_text"
    resolved_root: Path | None = None
    if repo_root is not None:
        resolved_root = Path(repo_root)

    if freeze_text is None:
        if resolved_root is None:
            raise ValueError("freeze_text or repo_root is required")
        freeze_path = resolved_root / SERVICE_FREEZE_RELATIVE_PATH
        freeze_text = freeze_path.read_text(encoding="utf-8")
        source = str(SERVICE_FREEZE_RELATIVE_PATH)

    if template_filenames is None and resolved_root is not None:
        template_filenames = _repo_template_filenames(resolved_root)

    systemd_section = _section(freeze_text, "Systemd-Owned Services")
    legacy_section = _section(freeze_text, "Legacy/Manual-Owned Processes")
    deprecated_section = _section(freeze_text, "Deprecated/Frozen Controls")
    table_section = _section(freeze_text, "Source-Of-Truth Table")
    legacy_disposition_section = _section(freeze_text, "Legacy Ownership Disposition Contract")
    cleanup_section = _section(freeze_text, "Cleanup Slice Order")
    runtime_section = _section(freeze_text, "Runtime-Neutral Rule")

    source_rows = _table_rows(table_section)
    legacy_manual = _inventory_items(legacy_section)
    deprecated_frozen_controls = _inventory_items(deprecated_section)
    legacy_dispositions = _legacy_disposition_rows(legacy_disposition_section)
    return {
        "audit_type": SERVICE_INVENTORY_AUDIT_TYPE,
        "schema_version": SERVICE_INVENTORY_AUDIT_SCHEMA_VERSION,
        "source": source,
        "runtime_neutral": "does not authorize new runtime behavior" in freeze_text,
        "live_service_inspection_allowed": False,
        "service_mutation_allowed": False,
        "systemd_owned": _inventory_items(systemd_section),
        "legacy_manual": legacy_manual,
        "deprecated_frozen_controls": deprecated_frozen_controls,
        "cleanup_slice_order": _cleanup_slice_order(cleanup_section),
        "source_of_truth_rows": source_rows,
        "owner_classifications": _owner_classifications(source_rows, template_filenames),
        "drift_control_scheduler": _drift_control_scheduler_classification(source_rows),
        "legacy_ownership_disposition_classes": list(LEGACY_OWNERSHIP_DISPOSITION_CLASSES),
        "legacy_ownership_dispositions": legacy_dispositions,
        "legacy_ownership_disposition_findings": _legacy_disposition_findings(
            legacy_dispositions,
            legacy_manual,
            deprecated_frozen_controls,
        ),
        "findings": _pending_template_findings(source_rows, template_filenames),
        "runtime_neutral_rule_present": "Any future service operation" in runtime_section,
    }