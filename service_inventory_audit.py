from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable


SERVICE_FREEZE_RELATIVE_PATH = Path("docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md")
SYSTEMD_USER_RELATIVE_PATH = Path("systemd/user")

SERVICE_INVENTORY_AUDIT_TYPE = "openclaw.service_inventory_audit"
SERVICE_INVENTORY_AUDIT_SCHEMA_VERSION = 1


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
    cleanup_section = _section(freeze_text, "Cleanup Slice Order")
    runtime_section = _section(freeze_text, "Runtime-Neutral Rule")

    source_rows = _table_rows(table_section)
    return {
        "audit_type": SERVICE_INVENTORY_AUDIT_TYPE,
        "schema_version": SERVICE_INVENTORY_AUDIT_SCHEMA_VERSION,
        "source": source,
        "runtime_neutral": "does not authorize new runtime behavior" in freeze_text,
        "live_service_inspection_allowed": False,
        "service_mutation_allowed": False,
        "systemd_owned": _inventory_items(systemd_section),
        "legacy_manual": _inventory_items(legacy_section),
        "deprecated_frozen_controls": _inventory_items(deprecated_section),
        "cleanup_slice_order": _cleanup_slice_order(cleanup_section),
        "source_of_truth_rows": source_rows,
        "owner_classifications": _owner_classifications(source_rows, template_filenames),
        "findings": _pending_template_findings(source_rows, template_filenames),
        "runtime_neutral_rule_present": "Any future service operation" in runtime_section,
    }