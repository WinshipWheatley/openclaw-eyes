#!/usr/bin/env python3
"""Chief deletion gate harness.

This harness evaluates deletion candidates only. It never deletes files.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "chief_gate_verdicts_v0"
DEFAULT_NOTEBOOK = Path("CHIEF_DELETION_NOTEBOOK.md")
DEFAULT_OUTPUT = Path("chief_gate_verdicts.json")
QUARANTINE_ROOT = Path(".audit-quarantine")
VERDICTS = {"QUARANTINE-APPROVED", "KEEP", "NEEDS-WINSHIP"}

PROTECTED_LIVE_PATHS = {
    "polish_loop/orchestrator.py",
}

FORBIDDEN_PATH_PARTS = (
    ".chief.env",
    ".google-secrets",
    "OpenClawLegalPrivate",
    "LegalPrivate",
    "FinancePrivate",
    "MusicLawPrivate",
)

SKIP_DIR_NAMES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".audit-quarantine",
    ".mypy_cache",
    ".ruff_cache",
    "chief_env",
    ".venv",
    "node_modules",
}

NON_LIVE_PREFIXES = (
    "tests/",
    "docs/",
    "reports/",
    "artifacts/",
    "generated/audit_shards/",
    "generated/context_packs/",
    "generated/external_registries/",
    "generated/wiki/",
)

NON_LIVE_FILENAMES = {
    "CHIEF_DELETION_NOTEBOOK.md",
    ".gitignore",
    "chief_gate_harness.py",
    "chief_gate_verdicts.json",
}

RG_EXCLUDED_GLOBS = (
    "!.git/**",
    "!.chief.env",
    "!.google-secrets/**",
    "!*LegalPrivate/**",
    "!*FinancePrivate/**",
    "!*MusicLawPrivate/**",
    "!generated/audit_shards/**",
    "!generated/context_packs/**",
)


@dataclass(frozen=True)
class Candidate:
    target: str
    group_members: tuple[str, ...] = ()
    source: str = "manual"
    note: str = ""


@dataclass(frozen=True)
class EvaluationContext:
    repo_root: Path
    served: Mapping[str, Any]


def stable_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_rel_path(value: str | Path) -> str:
    text = str(value).strip()
    if not text:
        return ""
    text = text.replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def split_target(target: str) -> tuple[str, str | None]:
    text = normalize_rel_path(target)
    match = re.match(r"^(?P<path>.+?)(?::(?P<line>\d+(?:-\d+)?))?$", text)
    if not match:
        return text, None
    return normalize_rel_path(match.group("path")), match.group("line")


def is_forbidden_path(path: str) -> bool:
    lowered = path.lower()
    return any(part.lower() in lowered for part in FORBIDDEN_PATH_PARTS)


def iter_repo_files(root: Path, *, suffixes: tuple[str, ...] | None = None) -> Iterable[Path]:
    root = root.resolve()
    for path in root.rglob("*"):
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        parts = set(rel.parts)
        if parts & SKIP_DIR_NAMES:
            continue
        rel_text = rel.as_posix()
        if is_forbidden_path(rel_text):
            continue
        if not path.is_file():
            continue
        if suffixes and path.suffix not in suffixes:
            continue
        yield path


def module_name_for_path(path: str) -> str:
    rel, _line = split_target(path)
    if rel.endswith(".py"):
        rel = rel[:-3]
    return rel.replace("/", ".")


def candidate_search_terms(target: str) -> tuple[str, ...]:
    rel, _line = split_target(target)
    path = Path(rel)
    terms = [rel, path.name]
    if path.suffix == ".py":
        terms.extend([path.stem, module_name_for_path(rel)])
    return tuple(dict.fromkeys(term for term in terms if term))


def path_is_non_live_reference(rel_path: str) -> bool:
    rel = normalize_rel_path(rel_path)
    if rel in NON_LIVE_FILENAMES:
        return True
    return rel.startswith(NON_LIVE_PREFIXES)


def run_rg(root: Path, term: str, *, excluded_paths: set[str]) -> dict[str, Any]:
    if not term:
        return {"term": term, "hit_count": 0, "hits": []}
    cmd = ["rg", "--fixed-strings", "--line-number", "--hidden"]
    for glob in RG_EXCLUDED_GLOBS:
        cmd.extend(["--glob", glob])
    cmd.extend([term, "."])
    try:
        result = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return {"term": term, "hit_count": 0, "hits": [], "tool_error": "rg_not_found"}

    hits: list[dict[str, Any]] = []
    for raw in result.stdout.splitlines():
        match = re.match(r"^\./(?P<path>.*?):(?P<line>\d+):(?P<text>.*)$", raw)
        if not match:
            continue
        rel_path = normalize_rel_path(match.group("path"))
        if rel_path in excluded_paths or is_forbidden_path(rel_path):
            continue
        hits.append(
            {
                "path": rel_path,
                "line": int(match.group("line")),
                "text": match.group("text")[:240],
                "live_reference": not path_is_non_live_reference(rel_path),
            }
        )
    return {
        "term": term,
        "hit_count": len(hits),
        "hits": hits[:40],
        "truncated": len(hits) > 40,
    }


def parse_imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return set()
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def module_index(root: Path) -> dict[str, str]:
    index: dict[str, str] = {}
    for path in iter_repo_files(root, suffixes=(".py",)):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(("tests/", "docs/", "generated/")):
            continue
        module = module_name_for_path(rel)
        index.setdefault(module, rel)
        index.setdefault(Path(rel).stem, rel)
    return index


def local_import_graph(root: Path) -> dict[str, set[str]]:
    index = module_index(root)
    graph: dict[str, set[str]] = {}
    for path in iter_repo_files(root, suffixes=(".py",)):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(("tests/", "docs/", "generated/")):
            continue
        edges: set[str] = set()
        for module in parse_imports(path):
            parts = module.split(".")
            candidates = [module]
            if parts:
                candidates.append(parts[0])
                if len(parts) > 1:
                    candidates.append(".".join(parts[:2]))
            for candidate in candidates:
                target = index.get(candidate)
                if target and target != rel:
                    edges.add(target)
        graph[rel] = edges
    return graph


def systemd_entrypoints(root: Path) -> tuple[set[str], list[dict[str, Any]]]:
    service_dir = root / "systemd" / "user"
    entrypoints: set[str] = set()
    refs: list[dict[str, Any]] = []
    if not service_dir.exists():
        return entrypoints, refs
    pattern = re.compile(r"@REPO_ROOT@/(?P<path>[A-Za-z0-9_./-]+\.py)")
    for service in sorted(service_dir.glob("*.in")):
        text = service.read_text(encoding="utf-8", errors="ignore")
        for match in pattern.finditer(text):
            rel = normalize_rel_path(match.group("path"))
            entrypoints.add(rel)
            refs.append({"service": service.relative_to(root).as_posix(), "path": rel})
    return entrypoints, refs


def served_paths(root: Path) -> dict[str, Any]:
    entrypoints, refs = systemd_entrypoints(root)
    graph = local_import_graph(root)
    reachable: set[str] = set()
    stack = list(entrypoints)
    while stack:
        rel = normalize_rel_path(stack.pop())
        if rel in reachable:
            continue
        reachable.add(rel)
        stack.extend(sorted(graph.get(rel, ())))
    return {
        "entrypoints": sorted(entrypoints),
        "systemd_refs": refs,
        "reachable_paths": sorted(reachable),
    }


def build_evaluation_context(repo_root: str | Path) -> EvaluationContext:
    root = Path(repo_root).resolve()
    return EvaluationContext(repo_root=root, served=served_paths(root))


def systemd_refs_for_target(root: Path, target_rel: str) -> list[dict[str, Any]]:
    _entrypoints, refs = systemd_entrypoints(root)
    module = module_name_for_path(target_rel)
    names = {target_rel, Path(target_rel).name, module, Path(target_rel).stem}
    found: list[dict[str, Any]] = []
    for service in sorted((root / "systemd" / "user").glob("*.in")) if (root / "systemd" / "user").exists() else []:
        text = service.read_text(encoding="utf-8", errors="ignore")
        if any(name and name in text for name in names):
            found.append({"service": service.relative_to(root).as_posix()})
    found.extend(ref for ref in refs if ref["path"] == target_rel and ref not in found)
    return found


def read_model_runtime_readers(root: Path, target_rel: str) -> list[dict[str, Any]]:
    rel = normalize_rel_path(target_rel)
    if not rel.startswith("generated/read_models/") or not rel.endswith(".json"):
        return []
    filename = Path(rel).name
    readers: list[dict[str, Any]] = []
    generic_reader_terms = ("glob(", "rglob(", "iterdir(")
    for path in iter_repo_files(root, suffixes=(".py",)):
        rel_path = path.relative_to(root).as_posix()
        if path_is_non_live_reference(rel_path):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        for index, line in enumerate(lines, start=1):
            window = "\n".join(lines[max(index - 4, 0) : min(index + 4, len(lines))])
            exact = (filename in window or rel in window) and ".read_text(" in window
            generic = (
                "generated/read_models" in window
                and ".read_text(" in window
                and any(term in window for term in generic_reader_terms)
            )
            if exact or generic:
                readers.append(
                    {
                        "path": rel_path,
                        "line": index,
                        "kind": "exact_read_text" if exact else "generic_generated_read_models_reader",
                    }
                )
                break
    return readers


def tracked_status(root: Path, rel_path: str) -> str:
    if not (root / ".git").exists():
        return "not_git_repo"
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel_path],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return "tracked" if result.returncode == 0 else "untracked"


def quarantine_plan_for(root: Path, rel_path: str, verdict: str, generated_at: str) -> dict[str, Any]:
    track_state = tracked_status(root, rel_path)
    snapshot_first = track_state == "untracked"
    quarantine_target = QUARANTINE_ROOT / generated_at.replace(":", "").replace("+", "Z") / rel_path
    steps: list[str] = []
    if verdict == "QUARANTINE-APPROVED":
        if snapshot_first:
            steps.append(f"mkdir -p {quarantine_target.parent.as_posix()}")
            steps.append(f"cp -a {rel_path} {quarantine_target.as_posix()}")
        steps.append(f"move {rel_path} to {quarantine_target.as_posix()} in a recoverable quarantine commit")
        steps.append("run focused tests and green gate before any permanent deletion")
    return {
        "delete_performed": False,
        "tracked_status": track_state,
        "snapshot_first": snapshot_first,
        "quarantine_path": quarantine_target.as_posix() if verdict == "QUARANTINE-APPROVED" else "",
        "steps": steps,
    }


def evaluate_candidate(
    repo_root: str | Path,
    target: str,
    *,
    group_members: Sequence[str] | None = None,
    generated_at: str | None = None,
    context: EvaluationContext | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    if context is not None:
        root = context.repo_root
    generated = generated_at or utc_now()
    target_rel, line_ref = split_target(target)
    group = tuple(dict.fromkeys(normalize_rel_path(item) for item in (group_members or ()) if item))
    excluded_paths = {target_rel, "chief_gate_harness.py", "tests/test_chief_gate_harness.py", "chief_gate_verdicts.json"}
    excluded_paths.update(split_target(member)[0] for member in group)
    path = root / target_rel
    reasons: list[str] = []

    if is_forbidden_path(target_rel):
        reasons.append("vault_wall_refuse")

    exists = path.exists()
    existence_gate = {
        "target_path": target_rel,
        "line_ref": line_ref,
        "exists": exists,
        "path_type": "missing" if not exists else ("directory" if path.is_dir() else "file"),
    }

    search_terms = candidate_search_terms(target_rel)
    rg_checks = [run_rg(root, term, excluded_paths=excluded_paths) for term in search_terms]
    rg_hit_count = sum(check["hit_count"] for check in rg_checks)
    live_reference_hits = [
        hit
        for check in rg_checks
        for hit in check["hits"]
        if hit.get("live_reference") is True
    ]
    dynamic_reference_hits = [
        hit
        for hit in live_reference_hits
        if any(marker in hit["text"] for marker in ("importlib", "getattr", "__import__", repr(Path(target_rel).stem), f'"{Path(target_rel).stem}"'))
    ]

    served = context.served if context is not None else served_paths(root)
    reachable = set(served["reachable_paths"])
    is_served = target_rel in reachable
    systemd_refs = systemd_refs_for_target(root, target_rel)
    readers = read_model_runtime_readers(root, target_rel)
    track_state = tracked_status(root, target_rel)

    if target_rel in PROTECTED_LIVE_PATHS:
        reasons.append("protected_live_path")
    if not exists:
        reasons.append("candidate_missing_no_delete_action")
    if readers:
        reasons.append("read_model_runtime_reader_found")
    if systemd_refs:
        reasons.append("systemd_reference_found")
    if is_served:
        reasons.append("served_path_requires_operator_signoff")
    if live_reference_hits:
        reasons.append("live_reference_found")
    if dynamic_reference_hits:
        reasons.append("dynamic_reference_found")

    mechanism_gate = {
        "candidate_can_be_removed_by_mechanism": False,
        "delete_is_only_allowed_as_recoverable_quarantine": True,
        "delete_performed": False,
    }

    if "vault_wall_refuse" in reasons or is_served or systemd_refs:
        verdict = "NEEDS-WINSHIP"
    elif target_rel in PROTECTED_LIVE_PATHS or not exists or readers or live_reference_hits:
        verdict = "KEEP"
    else:
        verdict = "QUARANTINE-APPROVED"
        mechanism_gate["candidate_can_be_removed_by_mechanism"] = True
        reasons.append("fresh_verification_no_live_refs")

    assert verdict in VERDICTS
    return {
        "candidate": target,
        "target_path": target_rel,
        "verdict": verdict,
        "reasons": tuple(dict.fromkeys(reasons)),
        "existence_gate": existence_gate,
        "mechanism_gate": mechanism_gate,
        "verification": {
            "fresh_runtime_verification": True,
            "rg_terms": search_terms,
            "rg_hit_count": rg_hit_count,
            "rg_checks": rg_checks,
            "live_reference_hits": live_reference_hits[:40],
            "dynamic_reference_hits": dynamic_reference_hits[:40],
            "excluded_paths": sorted(excluded_paths),
            "excluded_globs": RG_EXCLUDED_GLOBS,
        },
        "systemd_refs": systemd_refs,
        "serving_path": {
            "is_served_path": is_served,
            "entrypoints": served["entrypoints"],
            "matched_path": target_rel if is_served else "",
        },
        "read_model_runtime_readers": readers,
        "tracked_status": track_state,
        "quarantine_plan": quarantine_plan_for(root, target_rel, verdict, generated),
    }


def extract_backticked_items(cell: str) -> list[str]:
    return re.findall(r"`([^`]+)`", cell)


def resolve_candidate_item(root: Path, item: str) -> list[str]:
    item = normalize_rel_path(item)
    if not item:
        return []
    if "*" in item:
        return sorted(path.relative_to(root).as_posix() for path in root.glob(item) if path.exists())
    if "/" in item or "." in Path(item).name or ":" in item:
        return [item]
    py_path = f"{item}.py"
    if (root / py_path).exists():
        return [py_path]
    if (root / item).exists():
        return [item]
    return [item]


def notebook_candidates(root: Path, notebook_path: Path = DEFAULT_NOTEBOOK) -> list[Candidate]:
    path = root / notebook_path
    if not path.exists():
        return []
    candidates: list[Candidate] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if "| " not in raw or "PENDING-GATE" not in raw:
            continue
        cells = [cell.strip() for cell in raw.strip().strip("|").split("|")]
        if not cells:
            continue
        candidate_cell = cells[0]
        items = extract_backticked_items(candidate_cell)
        if "planning-packet quad" in candidate_cell:
            items.extend(
                [
                    "docs/operations/OPENCLAW_REMAINING_WORK_STRATIFIER_READY_PACKET.json",
                    "docs/operations/OPENCLAW_CRITICAL_PATH_EXECUTION_PACKET_READY.json",
                    "tests/test_operator_planning_ready_packet_export.py",
                ]
            )
        resolved: list[str] = []
        for item in items:
            resolved.extend(resolve_candidate_item(root, item))
        group = tuple(dict.fromkeys(resolved))
        for item in group:
            candidates.append(
                Candidate(
                    target=item,
                    group_members=group,
                    source=notebook_path.as_posix(),
                    note=candidate_cell,
                )
            )
    return list({candidate.target: candidate for candidate in candidates}.values())


def build_verdict_report(
    repo_root: str | Path,
    *,
    candidates: Sequence[Candidate] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    generated = generated_at or utc_now()
    selected = list(candidates if candidates is not None else notebook_candidates(root))
    context = build_evaluation_context(root)
    verdicts = [
        {
            **evaluate_candidate(
                root,
                candidate.target,
                group_members=candidate.group_members,
                generated_at=generated,
                context=context,
            ),
            "source": candidate.source,
            "note": candidate.note,
        }
        for candidate in selected
    ]
    counts = {verdict: 0 for verdict in sorted(VERDICTS)}
    for item in verdicts:
        counts[item["verdict"]] += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated,
        "repo_root": root.as_posix(),
        "source_notebook": DEFAULT_NOTEBOOK.as_posix(),
        "delete_performed": False,
        "candidate_count": len(verdicts),
        "summary": counts,
        "verdicts": verdicts,
        "recoverable_quarantine_plan": {
            "delete_performed": False,
            "quarantine_root": QUARANTINE_ROOT.as_posix(),
            "rule": "Snapshot untracked candidates before any recoverable quarantine move; delete nothing in this harness.",
            "approved_candidates": [
                {
                    "candidate": item["candidate"],
                    "quarantine_path": item["quarantine_plan"]["quarantine_path"],
                    "snapshot_first": item["quarantine_plan"]["snapshot_first"],
                }
                for item in verdicts
                if item["verdict"] == "QUARANTINE-APPROVED"
            ],
        },
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Chief deletion candidates without deleting anything.")
    parser.add_argument("--repo-root", default=".", help="Repository root to evaluate.")
    parser.add_argument("--check", action="append", default=[], help="Evaluate one future candidate path. May repeat.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT.as_posix(), help="Verdict JSON output path.")
    parser.add_argument("--no-write", action="store_true", help="Print only; do not write verdict JSON.")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = Path(args.repo_root).resolve()
    candidates = (
        [Candidate(target=check, source="--check") for check in args.check]
        if args.check
        else notebook_candidates(root)
    )
    report = build_verdict_report(root, candidates=candidates)
    if not args.no_write:
        output = Path(args.output)
        output = output if output.is_absolute() else root / output
        output.write_text(stable_json(report), encoding="utf-8")
    if args.format == "json":
        print(stable_json(report), end="")
    else:
        print(
            f"{SCHEMA_VERSION}: {report['candidate_count']} candidates; "
            f"approved={report['summary']['QUARANTINE-APPROVED']} "
            f"keep={report['summary']['KEEP']} "
            f"needs_winship={report['summary']['NEEDS-WINSHIP']}; "
            f"delete_performed=false"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
