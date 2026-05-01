#!/usr/bin/env python3
"""Thin staging/replay harness for the chief end-of-day review flow.

Mirrors the morning_brief_harness pattern: all writes go to the staging
root only. No live REVIEW_DIR writes. No approval-state mutations.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import chief_end_of_day_review as eod


@dataclass
class HarnessRoots:
    root: Path
    fixtures: Path
    runs: Path


def _default_roots() -> HarnessRoots:
    root = Path("/home/openclaw/staging/chief_eod_harness")
    return HarnessRoots(
        root=root,
        fixtures=root / "fixtures",
        runs=root / "runs",
    )


def _ensure_roots(roots: HarnessRoots) -> None:
    roots.fixtures.mkdir(parents=True, exist_ok=True)
    roots.runs.mkdir(parents=True, exist_ok=True)


def _reference_key(reference_time: str | None) -> str:
    if not reference_time:
        return datetime.now().strftime("%Y%m%dT%H%M%S")
    return reference_time.replace(":", "").replace("-", "")


def _allocate_run_dir(runs_root: Path, base_key: str) -> Path:
    run_dir = runs_root / base_key
    if not run_dir.exists():
        return run_dir
    idx = 1
    while True:
        candidate = runs_root / f"{base_key}-r{idx}"
        if not candidate.exists():
            return candidate
        idx += 1


def capture_fixture(name: str, roots: HarnessRoots, reference_time: str | None = None) -> Path:
    """Capture the current end-of-day review context as a fixture."""
    _ensure_roots(roots)
    context = eod.build_review_context()
    fixture = {
        "fixture_name": name,
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "reference_time": reference_time,
        "inputs": {"context": context},
    }
    path = roots.fixtures / f"{name}.json"
    path.write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    return path


def _load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_recorded_review(path: Path) -> dict[str, Any]:
    manifest_path = path / "manifest.json" if path.is_dir() else path
    recorded = json.loads(manifest_path.read_text(encoding="utf-8"))
    if isinstance(recorded.get("_review_meta"), dict):
        return recorded
    return {
        "summary": str(recorded.get("summary", "") or ""),
        "findings": recorded.get("findings") if isinstance(recorded.get("findings"), list) else [],
        "proposals": recorded.get("proposals") if isinstance(recorded.get("proposals"), list) else [],
        "_review_meta": {
            "structured_output_lane": recorded.get("structured_output_lane"),
            "fast_attempt_structured": recorded.get("fast_attempt_structured"),
            "strong_attempt_structured": recorded.get("strong_attempt_structured"),
            "empty_output_cause": recorded.get("empty_output_cause"),
        },
    }


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _evidence_counts(checks: list[dict[str, Any]]) -> dict[str, int]:
    passed = sum(1 for check in checks if check.get("passed") is True)
    total = len(checks)
    return {"passed": passed, "failed": total - passed, "total_cases": total}


def run_replay(
    fixture_path: Path,
    roots: HarnessRoots,
    reference_time: str | None = None,
    recorded_from: Path | None = None,
) -> Path:
    """Replay end-of-day review against a fixture. All writes go to staging only."""
    _ensure_roots(roots)
    fixture = _load_fixture(fixture_path)
    run_id = _reference_key(reference_time or fixture.get("reference_time"))
    run_dir = _allocate_run_dir(roots.runs, run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    context = fixture["inputs"]["context"]
    t0 = time.monotonic()
    inference_mode = "recorded" if recorded_from is not None else "live"
    recorded_source = None
    if recorded_from is not None:
        parsed = _load_recorded_review(recorded_from)
        recorded_source = str(recorded_from / "manifest.json" if recorded_from.is_dir() else recorded_from)
    else:
        parsed = eod._run_review_model(context)
    duration_ms = int((time.monotonic() - t0) * 1000)

    review_meta = parsed.get("_review_meta") if isinstance(parsed.get("_review_meta"), dict) else {}
    findings = [str(x).strip() for x in parsed.get("findings", []) if str(x).strip()]
    proposals = [p for p in parsed.get("proposals", []) if isinstance(p, dict)]
    summary = str(parsed.get("summary", "") or "").strip()
    lane = str(review_meta.get("structured_output_lane") or "unknown")
    checks = [
        _check("fixture_has_context", bool(str(context).strip()), "fixture context is present"),
        _check("summary_present", bool(summary), "review summary is present"),
        _check("structured_lane_recorded", lane != "unknown", f"structured_output_lane={lane}"),
        _check("proposals_are_objects", len(proposals) == len(parsed.get("proposals", []) or []), "proposal entries are objects"),
        _check("staging_only", str(run_dir).startswith(str(roots.runs)), "run artifacts are under the harness runs root"),
    ]

    manifest = {
        "harness_mode": True,
        "dry_run": True,
        "harness_name": "chief_eod_harness",
        "task_name": "chief_end_of_day_review",
        "flow": "chief_end_of_day_review",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inference_mode": inference_mode,
        "fixture_path": str(fixture_path),
        "staging_root": str(roots.root),
        "recorded_source": recorded_source,
        "reference_time": reference_time or fixture.get("reference_time"),
        "duration_ms": duration_ms,
        "summary": summary,
        "findings": findings,
        "proposals": proposals,
        "checks": checks,
        **_evidence_counts(checks),
        "structured_output_lane": lane,
        "fast_attempt_structured": bool(review_meta.get("fast_attempt_structured")),
        "strong_attempt_structured": bool(review_meta.get("strong_attempt_structured")),
        "empty_output_cause": review_meta.get("empty_output_cause"),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "review_output.txt").write_text(str(parsed.get("summary", "")), encoding="utf-8")
    (run_dir / "input_fixture_copy.json").write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Chief end-of-day review staging/replay harness")
    parser.add_argument("--capture-fixture", metavar="NAME", help="Capture an end-of-day review context fixture")
    parser.add_argument("--fixture", type=Path, help="Replay this fixture file")
    parser.add_argument("--recorded-from", type=Path, help="Reuse recorded review output from a prior manifest or run directory")
    parser.add_argument("--reference-time", help="Fixed reference time string recorded in harness artifacts")
    parser.add_argument("--staging-root", type=Path, help="Override staging root")
    args = parser.parse_args()

    roots = _default_roots()
    if args.staging_root:
        roots = HarnessRoots(
            root=args.staging_root,
            fixtures=args.staging_root / "fixtures",
            runs=args.staging_root / "runs",
        )

    if args.capture_fixture:
        path = capture_fixture(args.capture_fixture, roots, reference_time=args.reference_time)
        print(path)
        return

    fixture_path = args.fixture or (roots.fixtures / "sample_eod.json")
    run_dir = run_replay(
        fixture_path,
        roots,
        reference_time=args.reference_time,
        recorded_from=args.recorded_from,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
