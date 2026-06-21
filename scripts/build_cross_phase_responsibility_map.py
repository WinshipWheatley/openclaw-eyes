#!/usr/bin/env python3
"""Build a read-only cross-phase responsibility map and price-truth audit."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "cross_phase_price_truth_audit_v0"
DEFAULT_SCAN_ROOTS = ("generated", "finance", "operator")
DEFAULT_JSON_OUTPUT = Path("generated/read_models/cross_phase_price_truth_audit.json")
DEFAULT_MARKDOWN_OUTPUT = Path("artifacts/040_price_truth_and_cross_phase_audit.md")
TEXT_SUFFIXES = {".json", ".md", ".txt", ".csv", ".yaml", ".yml"}
DENY_PATH_PARTS = {".git", ".venv", "__pycache__", "vault", "secrets", "node_modules"}
DENY_FILENAMES = {".chief.env", ".env", ".env.local"}

PRICE_TERMS = (
    "amount",
    "balance",
    "budget",
    "change order",
    "cost",
    "deposit",
    "fee",
    "invoice",
    "labor",
    "payment",
    "price",
    "quote",
    "rate",
    "scope",
    "total",
)
DEFENSIVE_TERMS = ("apolog", "cheap", "discount", "hope that's okay", "just", "sorry")
UNCLEAR_TERMS = ("estimate?", "missing", "needs confirmation", "tbd", "unknown", "verify")
REQUIRED_PRICE_DIMENSIONS = {
    "labor": ("labor", "hours", "hourly", "time"),
    "cost": ("cost", "expense", "materials", "rental"),
    "scope": ("scope", "deliverable", "included", "excludes", "change order"),
    "approval": ("approval", "approved", "signoff", "operator review", "client approval"),
}

AGENT_PHASE_OWNERS = {
    "chief": "Source of Truth / Price Truth",
    "guardian": "Safety, Ethics, Pricing Integrity",
    "hermes": "Architecture and Least-Complex-Sufficient System",
    "niles": "Creative Sufficiency and Value Translation",
    "maestro": "Internal Concierge / Operator Composure",
    "clara": "External Concierge / Client Price Presentation",
}

PHASE_PRINCIPLES: tuple[dict[str, str], ...] = (
    {"phase": "I", "principle": "Velvet brief over steel proof", "primary_owner": "maestro", "secondary_reviewer": "chief"},
    {"phase": "I", "principle": "Severity integrity", "primary_owner": "guardian", "secondary_reviewer": "chief"},
    {"phase": "I", "principle": "System carries complexity; Winship receives orientation", "primary_owner": "maestro", "secondary_reviewer": "hermes"},
    {"phase": "II", "principle": "Counsel before commerce", "primary_owner": "chief", "secondary_reviewer": "guardian"},
    {"phase": "II", "principle": "Trusted restraint before persuasion", "primary_owner": "guardian", "secondary_reviewer": "clara"},
    {"phase": "III", "principle": "Recognition without surveillance", "primary_owner": "maestro", "secondary_reviewer": "guardian"},
    {"phase": "III", "principle": "Permission before intimacy", "primary_owner": "guardian", "secondary_reviewer": "chief"},
    {"phase": "III", "principle": "Service memory before personal memory", "primary_owner": "hermes", "secondary_reviewer": "maestro"},
    {"phase": "IV", "principle": "Price should signal an earned reality", "primary_owner": "chief", "secondary_reviewer": "guardian"},
    {"phase": "IV", "principle": "Calm price, complete truth", "primary_owner": "clara", "secondary_reviewer": "chief"},
    {"phase": "IV", "principle": "Creative value translation", "primary_owner": "niles", "secondary_reviewer": "chief"},
    {"phase": "IV", "principle": "Value without the feature dump", "primary_owner": "clara", "secondary_reviewer": "niles"},
    {"phase": "IV", "principle": "Scope may change; dignity does not", "primary_owner": "guardian", "secondary_reviewer": "hermes"},
    {"phase": "IV", "principle": "Personalization must not alter price fairness", "primary_owner": "guardian", "secondary_reviewer": "maestro"},
)


@dataclass(frozen=True)
class PriceSurface:
    path: str
    matched_terms: tuple[str, ...]
    missing_dimensions: tuple[str, ...]
    defensive: bool
    unclear: bool
    incomplete: bool
    amount_mentions: tuple[str, ...]
    redacted_sample: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _is_denied(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    return bool(parts & DENY_PATH_PARTS) or path.name.lower() in DENY_FILENAMES


def _candidate_files(root: Path, scan_roots: Sequence[str]) -> Iterable[Path]:
    for rel in scan_roots:
        base = root / rel
        if not base.exists() or _is_denied(base):
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES and not _is_denied(path):
                yield path


def _read_text(path: Path, max_bytes: int) -> str:
    try:
        return path.read_bytes()[:max_bytes].decode("utf-8", errors="ignore")
    except OSError:
        return ""


def _redact(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", "[EMAIL]", text)
    text = re.sub(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b", "[PHONE]", text)
    return " ".join(text.split())[:280]


def _amount_mentions(text: str) -> tuple[str, ...]:
    amounts = re.findall(r"\$\s?\d[\d,]*(?:\.\d+)?|\b\d+(?:\.\d+)?\s?(?:usd|dollars|/hr|per hour)\b", text, re.I)
    return tuple(dict.fromkeys(amount.strip() for amount in amounts[:8]))


def _price_surface(root: Path, path: Path, text: str) -> PriceSurface | None:
    lowered = f"{path.as_posix()} {text}".lower()
    matched = tuple(term for term in PRICE_TERMS if term in lowered)
    amounts = _amount_mentions(text)
    if not matched and not amounts:
        return None
    missing = tuple(
        dimension
        for dimension, terms in REQUIRED_PRICE_DIMENSIONS.items()
        if not any(term in lowered for term in terms)
    )
    defensive = any(term in lowered for term in DEFENSIVE_TERMS)
    unclear = any(term in lowered for term in UNCLEAR_TERMS)
    return PriceSurface(
        path=path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix(),
        matched_terms=matched,
        missing_dimensions=missing,
        defensive=defensive,
        unclear=unclear,
        incomplete=bool(missing),
        amount_mentions=amounts,
        redacted_sample=_redact(text),
    )


def _responsibility_matrix() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in PHASE_PRINCIPLES:
        primary = item["primary_owner"]
        secondary = item["secondary_reviewer"]
        rows.append(
            {
                **item,
                "primary_owner_role": AGENT_PHASE_OWNERS[primary],
                "secondary_reviewer_role": AGENT_PHASE_OWNERS[secondary],
                "overlap_or_conflict": _overlap_note(item["phase"], primary, secondary),
            }
        )
    return rows


def _overlap_note(phase: str, primary: str, secondary: str) -> str:
    if phase == "IV" and {primary, secondary} & {"chief", "guardian"}:
        return "Price truth and integrity must agree before client-facing presentation."
    if primary == "clara":
        return "Client presentation must preserve Chief truth and Guardian boundaries."
    if primary == "maestro":
        return "Operator brevity must not hide severity, price, approval, or scope facts."
    return "No conflict if source facts, authority, and approval boundaries stay explicit."


def build_audit(
    *,
    root: str | Path = ".",
    scan_roots: Sequence[str] = DEFAULT_SCAN_ROOTS,
    max_files: int = 2000,
    max_bytes_per_file: int = 16000,
) -> dict[str, Any]:
    base = Path(root)
    surfaces: list[PriceSurface] = []
    scanned = 0
    skipped_after_limit = False
    for path in _candidate_files(base, scan_roots):
        if scanned >= max_files:
            skipped_after_limit = True
            break
        scanned += 1
        surface = _price_surface(base, path, _read_text(path, max_bytes_per_file))
        if surface:
            surfaces.append(surface)
    missing_counts = Counter(dim for surface in surfaces for dim in surface.missing_dimensions)
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "cross_phase_price_truth_audit",
        "generated_at": _utc_now(),
        "status": "READY",
        "responsibility_matrix": _responsibility_matrix(),
        "agent_phase_owners": AGENT_PHASE_OWNERS,
        "scan_roots": list(scan_roots),
        "files_scanned": scanned,
        "max_files": max_files,
        "skipped_after_limit": skipped_after_limit,
        "price_surface_count": len(surfaces),
        "defensive_surface_count": sum(1 for surface in surfaces if surface.defensive),
        "unclear_surface_count": sum(1 for surface in surfaces if surface.unclear),
        "incomplete_surface_count": sum(1 for surface in surfaces if surface.incomplete),
        "missing_dimension_counts": dict(sorted(missing_counts.items())),
        "price_surfaces": [asdict(surface) for surface in surfaces[:500]],
        "machine_proof": {
            "read_only": True,
            "prompts_mutated": False,
            "live_pricing_changed": False,
            "send_or_money_performed": False,
            "samples_redacted": True,
        },
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Cross-Phase Agent Integration And Price-Truth Audit",
        "",
        f"- Status: {payload.get('status')}",
        f"- Files scanned: {payload.get('files_scanned')}",
        f"- Price surfaces: {payload.get('price_surface_count')}",
        f"- Defensive surfaces: {payload.get('defensive_surface_count')}",
        f"- Unclear surfaces: {payload.get('unclear_surface_count')}",
        f"- Incomplete surfaces: {payload.get('incomplete_surface_count')}",
        "",
        "## Cross-Phase Responsibility Matrix",
    ]
    for row in payload.get("responsibility_matrix", ()):
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"- Phase {row.get('phase')}: {row.get('principle')} -> "
            f"{row.get('primary_owner')} primary, {row.get('secondary_reviewer')} review. "
            f"{row.get('overlap_or_conflict')}"
        )
    lines.extend(["", "## Missing Price Dimensions"])
    missing = payload.get("missing_dimension_counts") if isinstance(payload.get("missing_dimension_counts"), Mapping) else {}
    if not missing:
        lines.append("- None in bounded scan.")
    for dimension, count in sorted(missing.items()):
        lines.append(f"- {dimension}: missing from {count} price surfaces")
    lines.extend(["", "## Price Surface Findings"])
    for row in payload.get("price_surfaces", ())[:60]:
        if not isinstance(row, Mapping):
            continue
        flags = []
        if row.get("defensive"):
            flags.append("defensive")
        if row.get("unclear"):
            flags.append("unclear")
        if row.get("incomplete"):
            flags.append("incomplete")
        lines.append(
            f"- `{row.get('path')}` [{', '.join(flags) if flags else 'reviewed'}; "
            f"missing={', '.join(row.get('missing_dimensions') or ()) or 'none'}; "
            f"amounts={', '.join(row.get('amount_mentions') or ()) or 'none'}]: {row.get('redacted_sample')}"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "- Audit only: no prompt mutation, live pricing change, send, money movement, deploy, or restart.",
            "- Price should signal earned reality: labor, cost, scope, and approval need explicit evidence before quote confidence.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def write_outputs(payload: Mapping[str, Any], *, json_output: Path, markdown_output: Path) -> None:
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(stable_json(dict(payload)), encoding="utf-8")
    markdown_output.write_text(render_markdown(payload), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build cross-phase responsibility map and price-truth audit.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--scan-root", action="append", default=[])
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT.as_posix())
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT.as_posix())
    parser.add_argument("--max-files", type=int, default=2000)
    parser.add_argument("--max-bytes-per-file", type=int, default=16000)
    args = parser.parse_args(list(argv) if argv is not None else None)

    payload = build_audit(
        root=args.root,
        scan_roots=tuple(args.scan_root) if args.scan_root else DEFAULT_SCAN_ROOTS,
        max_files=max(1, args.max_files),
        max_bytes_per_file=max(1000, args.max_bytes_per_file),
    )
    write_outputs(payload, json_output=Path(args.json_output), markdown_output=Path(args.markdown_output))
    print(stable_json({"status": payload["status"], "price_surface_count": payload["price_surface_count"]}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
