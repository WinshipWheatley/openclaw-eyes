"""Dry-run Data Room confirmed-reference loader.

This module plans canonical_facts writes only. It does not mutate the
business-ops ledger; optional DB access is read-only conflict detection.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIRMED_REFERENCE_PATH = Path(
    "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md"
)
DEFAULT_LOAD_PLAN_PATH = Path("artifacts/dataroom/load_plan.md")
TARGET_TABLE = "canonical_facts"
SOURCE_ID = "dataroom_confirmed_reference"
SOURCE_DESCRIPTION = "Winship confirmed Data Room reference dry-run source"
DOC_CATEGORY = "business_config"
TEMPORAL_OR_DOCTRINE = "declared_reference"
TRUTH_STATUS = "declared"
VERIFICATION_REQUIRED = 1

PUBLIC_ACTORS = ("cassandra", "chief", "guardian", "hermes")
OPERATIONAL_ACTORS = ("cassandra", "chief", "guardian")


@dataclass(frozen=True)
class ConfirmedReferenceItem:
    section_heading: str
    section_slug: str
    key: str
    value: str
    source_line: int


@dataclass(frozen=True)
class PlannedCanonicalWrite:
    key: str
    value: str
    target_table: str
    canonical_fields: dict[str, Any]

    @property
    def fact_id(self) -> str:
        return str(self.canonical_fields["fact_id"])

    @property
    def content_hash(self) -> str:
        return str(self.canonical_fields["content_hash"])


@dataclass(frozen=True)
class LoadConflict:
    key: str
    fact_id: str
    existing_content_hash: str
    planned_content_hash: str
    existing_fact_text: str
    planned_fact_text: str


@dataclass(frozen=True)
class LoadGap:
    key: str
    section_heading: str
    value: str
    reason: str


@dataclass(frozen=True)
class DataRoomLoadPlan:
    source_path: str
    source_hash: str
    source_commit: str
    dry_run_only: bool
    db_path: str | None
    db_check_status: str
    planned_writes: tuple[PlannedCanonicalWrite, ...]
    conflicts: tuple[LoadConflict, ...]
    idempotent_existing: tuple[str, ...]
    gaps: tuple[LoadGap, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "source_hash": self.source_hash,
            "source_commit": self.source_commit,
            "dry_run_only": self.dry_run_only,
            "db_path": self.db_path,
            "db_check_status": self.db_check_status,
            "planned_writes": [
                {
                    "key": write.key,
                    "value": write.value,
                    "target_table": write.target_table,
                    "canonical_fields": write.canonical_fields,
                }
                for write in self.planned_writes
            ],
            "conflicts": [conflict.__dict__ for conflict in self.conflicts],
            "idempotent_existing": list(self.idempotent_existing),
            "gaps": [gap.__dict__ for gap in self.gaps],
        }


def build_load_plan(
    source_path: str | Path = DEFAULT_CONFIRMED_REFERENCE_PATH,
    *,
    db_path: str | Path | None = None,
    source_commit: str | None = None,
) -> DataRoomLoadPlan:
    path = Path(source_path)
    source_bytes = path.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    markdown = source_bytes.decode("utf-8")
    source_commit = source_commit or f"source_sha256:{source_hash[:16]}"

    items = parse_confirmed_reference(markdown)
    planned_writes = tuple(
        _planned_write(item, path.as_posix(), source_commit) for item in items
    )
    gaps = tuple(_detect_gaps(items))

    conflicts: tuple[LoadConflict, ...] = ()
    idempotent_existing: tuple[str, ...] = ()
    db_check_status = "not_checked"
    db_path_text = str(db_path) if db_path is not None else None
    if db_path is not None:
        conflicts, idempotent_existing, db_check_status = _read_only_conflict_check(
            planned_writes,
            Path(db_path),
        )

    return DataRoomLoadPlan(
        source_path=path.as_posix(),
        source_hash=source_hash,
        source_commit=source_commit,
        dry_run_only=True,
        db_path=db_path_text,
        db_check_status=db_check_status,
        planned_writes=planned_writes,
        conflicts=conflicts,
        idempotent_existing=idempotent_existing,
        gaps=gaps,
    )


def parse_confirmed_reference(markdown: str) -> tuple[ConfirmedReferenceItem, ...]:
    current_heading = ""
    current_slug = ""
    seen: dict[str, int] = {}
    items: list[ConfirmedReferenceItem] = []

    for line_number, raw_line in enumerate(markdown.splitlines(), start=1):
        heading = _match_heading(raw_line)
        if heading:
            current_heading = heading
            current_slug = _slugify(heading)
            continue

        value = _match_item(raw_line)
        if not value or not current_heading:
            continue

        anchor = _anchor_for_value(value)
        key_base = f"business_config.{current_slug}.{_slugify(anchor)}"
        count = seen.get(key_base, 0) + 1
        seen[key_base] = count
        key = key_base if count == 1 else f"{key_base}_{count}"
        items.append(
            ConfirmedReferenceItem(
                section_heading=current_heading,
                section_slug=current_slug,
                key=key,
                value=value,
                source_line=line_number,
            )
        )

    return tuple(items)


def render_load_plan_markdown(plan: DataRoomLoadPlan) -> str:
    lines: list[str] = [
        "# Data Room Clean Load Dry Run Plan",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Source | `{_escape_table(plan.source_path)}` |",
        f"| Source hash | `{plan.source_hash}` |",
        f"| Source revision for planned rows | `{plan.source_commit}` |",
        f"| Target table | `{TARGET_TABLE}` |",
        f"| Dry run only | `{str(plan.dry_run_only).lower()}` |",
        f"| Planned writes | `{len(plan.planned_writes)}` |",
        f"| DB check | `{plan.db_check_status}` |",
        "",
        "## Planned Key Value Writes",
        "",
        "| Key | Value | Fact ID | Hash | Sensitivity | Actors |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for write in plan.planned_writes:
        fields = write.canonical_fields
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{_escape_table(write.key)}`",
                    _escape_table(write.value),
                    f"`{_escape_table(str(fields['fact_id']))}`",
                    f"`{str(fields['content_hash'])[:12]}`",
                    f"`{_escape_table(str(fields['sensitivity_class']))}`",
                    f"`{_escape_table(str(fields['allowed_actors']))}`",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Exact canonical_facts Rows",
            "",
            "These are the exact fields the reviewed live load would write.",
            "",
            "```json",
            json.dumps(
                [write.canonical_fields for write in plan.planned_writes],
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "## Conflicts",
            "",
        ]
    )

    if plan.db_check_status == "not_checked":
        lines.append("- Not checked; no ledger DB path was provided.")
    elif not plan.conflicts:
        lines.append("- None found.")
    else:
        lines.extend(
            [
                "| Key | Fact ID | Existing hash | Planned hash |",
                "| --- | --- | --- | --- |",
            ]
        )
        for conflict in plan.conflicts:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{_escape_table(conflict.key)}`",
                        f"`{_escape_table(conflict.fact_id)}`",
                        f"`{_escape_table(conflict.existing_content_hash)}`",
                        f"`{_escape_table(conflict.planned_content_hash)}`",
                    ]
                )
                + " |"
            )

    lines.extend(["", "## Idempotent Existing Rows", ""])
    if plan.idempotent_existing:
        for fact_id in plan.idempotent_existing:
            lines.append(f"- `{_escape_table(fact_id)}` already matches the plan.")
    elif plan.db_check_status == "checked":
        lines.append("- None.")
    else:
        lines.append("- Not checked.")

    lines.extend(["", "## Gaps And Ambiguities", ""])
    if not plan.gaps:
        lines.append("- None detected.")
    else:
        lines.extend(["| Key | Section | Reason | Value |", "| --- | --- | --- | --- |"])
        for gap in plan.gaps:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{_escape_table(gap.key)}`",
                        _escape_table(gap.section_heading),
                        _escape_table(gap.reason),
                        _escape_table(gap.value),
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## Safety Notes",
            "",
            "- This plan does not write the live ledger.",
            "- DB access, when requested, is read-only conflict detection.",
            "- Trust-gated payment and home-address policy facts remain policy references only; no bank details or home address values are present in the staged source.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_load_plan(
    output_path: str | Path = DEFAULT_LOAD_PLAN_PATH,
    *,
    source_path: str | Path = DEFAULT_CONFIRMED_REFERENCE_PATH,
    db_path: str | Path | None = None,
    source_commit: str | None = None,
) -> DataRoomLoadPlan:
    plan = build_load_plan(source_path, db_path=db_path, source_commit=source_commit)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_load_plan_markdown(plan), encoding="utf-8")
    return plan


def _planned_write(
    item: ConfirmedReferenceItem,
    source_file: str,
    source_commit: str,
) -> PlannedCanonicalWrite:
    sensitivity = _sensitivity_for(item)
    allowed_actors = (
        OPERATIONAL_ACTORS if sensitivity == "operational_canonical" else PUBLIC_ACTORS
    )
    content_hash = hashlib.sha256(item.value.encode("utf-8")).hexdigest()
    fact_id = item.key.replace("business_config.", f"{SOURCE_ID}:").replace(".", ":")
    fields = {
        "fact_id": fact_id,
        "source_file": source_file,
        "section_heading": item.section_heading,
        "source_commit": source_commit,
        "content_hash": content_hash,
        "fact_text": item.value,
        "sensitivity_class": sensitivity,
        "allowed_actors": json.dumps(list(allowed_actors), separators=(",", ":")),
        "doc_category": DOC_CATEGORY,
        "temporal_or_doctrine": TEMPORAL_OR_DOCTRINE,
        "source_description": SOURCE_DESCRIPTION,
        "truth_source_id": SOURCE_ID,
        "truth_status": TRUTH_STATUS,
        "verification_required": VERIFICATION_REQUIRED,
        "verification_evidence_id": None,
    }
    return PlannedCanonicalWrite(
        key=item.key,
        value=item.value,
        target_table=TARGET_TABLE,
        canonical_fields=fields,
    )


def _read_only_conflict_check(
    planned_writes: tuple[PlannedCanonicalWrite, ...],
    db_path: Path,
) -> tuple[tuple[LoadConflict, ...], tuple[str, ...], str]:
    if not db_path.exists():
        return (), (), "db_missing"

    conflicts: list[LoadConflict] = []
    idempotent_existing: list[str] = []
    uri = f"file:{db_path.as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        for write in planned_writes:
            row = conn.execute(
                "SELECT fact_id, content_hash, fact_text FROM canonical_facts WHERE fact_id = ?",
                (write.fact_id,),
            ).fetchone()
            if row is None:
                continue
            if row["content_hash"] == write.content_hash and row["fact_text"] == write.value:
                idempotent_existing.append(write.fact_id)
                continue
            conflicts.append(
                LoadConflict(
                    key=write.key,
                    fact_id=write.fact_id,
                    existing_content_hash=str(row["content_hash"] or ""),
                    planned_content_hash=write.content_hash,
                    existing_fact_text=str(row["fact_text"] or ""),
                    planned_fact_text=write.value,
                )
            )
        conn.close()
    except sqlite3.Error as exc:
        return (), (), f"db_check_failed:{exc.__class__.__name__}"

    return tuple(conflicts), tuple(idempotent_existing), "checked"


def _detect_gaps(items: tuple[ConfirmedReferenceItem, ...]) -> list[LoadGap]:
    gaps: list[LoadGap] = []
    patterns = (
        ("tbd", "TBD value needs Winship or source confirmation."),
        ("pending", "Pending external source before live load."),
        ("lookup", "Lookup required before live load."),
        ("confirm", "Confirmation required before live load."),
        ("decide", "Decision required before live load."),
        ("not done yet", "Source ingestion is not complete."),
        ("state terms", "Payment terms need to be decided before live load."),
        ("proposed rule", "Proposed rule needs review before live load."),
    )
    for item in items:
        lower_value = item.value.lower()
        reason = ""
        if item.section_slug == "open_items_actions":
            reason = "Open action item; keep out of final business config until resolved or explicitly accepted."
        else:
            for needle, message in patterns:
                if needle in lower_value:
                    reason = message
                    break
        if reason:
            gaps.append(
                LoadGap(
                    key=item.key,
                    section_heading=item.section_heading,
                    value=item.value,
                    reason=reason,
                )
            )
    return gaps


def _sensitivity_for(item: ConfirmedReferenceItem) -> str:
    text = f"{item.section_heading} {item.value}".lower()
    operational_tokens = (
        "accountant",
        "annette",
        "bank",
        "check",
        "chyna",
        "contact",
        "coupa",
        "direct deposit",
        "draper",
        "email",
        "finance",
        "glenn",
        "home address",
        "invoice",
        "payer",
        "payment",
        "remit",
        "reservations@",
        "terms",
        "trust",
        "zelle",
    )
    if any(token in text for token in operational_tokens):
        return "operational_canonical"
    return "public_canonical"


def _match_heading(line: str) -> str:
    match = re.match(r"^##\s+(.+?)\s*$", line)
    if not match:
        return ""
    return _plain_text(match.group(1)).strip()


def _match_item(line: str) -> str:
    match = re.match(r"^\s*(?:[-*]\s+|\d+\.\s+)(.+?)\s*$", line)
    if not match:
        return ""
    return _plain_text(match.group(1)).strip()


def _anchor_for_value(value: str) -> str:
    if value.lower().startswith("time-sensitive - "):
        delimiter_order = (":",)
    else:
        candidates = [
            (value.find(delimiter), delimiter)
            for delimiter in (" = ", " - ", ":")
            if delimiter in value
        ]
        delimiter_order = tuple(
            delimiter for _, delimiter in sorted(candidates, key=lambda item: item[0])
        )
    for delimiter in delimiter_order:
        prefix = value.split(delimiter, 1)[0].strip()
        if prefix.lower().startswith("tech work"):
            return "Tech work"
        if prefix:
            return prefix
    value_without_parenthetical = re.sub(r"\s*\([^)]*\)", "", value).strip()
    if value_without_parenthetical:
        return value_without_parenthetical
    words = value.split()
    return " ".join(words[:8])


def _plain_text(value: str) -> str:
    text = value
    replacements = {
        "\u2014": "-",
        "\u2013": "-",
        "\u2192": "->",
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\u2026": "...",
        "\u23f0": "",
    }
    for needle, replacement in replacements.items():
        text = text.replace(needle, replacement)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = text.replace("`", "")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text).strip()


def _slugify(value: str) -> str:
    text = _plain_text(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "item"


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
