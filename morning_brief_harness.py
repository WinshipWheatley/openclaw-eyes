#!/usr/bin/env python3
"""Thin staging/replay harness for the morning briefing stack."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import cassandra_briefing_brain as briefing


@dataclass
class HarnessRoots:
    root: Path
    fixtures: Path
    runs: Path


def _default_roots() -> HarnessRoots:
    root = Path("/home/openclaw/staging/morning_brief_harness")
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
    _ensure_roots(roots)
    bundle = briefing._build_morning_stack_inputs()
    fixture = {
        "fixture_name": name,
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "reference_time": reference_time,
        "inputs": bundle,
    }
    path = roots.fixtures / f"{name}.json"
    path.write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    return path


def _load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _evidence_counts(checks: list[dict[str, Any]]) -> dict[str, int]:
    passed = sum(1 for check in checks if check.get("passed") is True)
    total = len(checks)
    return {"passed": passed, "failed": total - passed, "total_cases": total}


def _normalize_recorded_stage(stage: dict[str, Any]) -> dict[str, Any]:
    out = dict(stage)
    out["inference_mode"] = "recorded"
    out["timing_basis"] = "recorded_stage_output_reuse"
    out["source_duration_ms"] = stage.get("duration_ms")
    out["source_started_at"] = stage.get("started_at")
    out["source_finished_at"] = stage.get("finished_at")
    return out


def _stage_outputs_dir(run_dir: Path) -> Path:
    return run_dir / "stage_outputs"


def _write_stage_outputs(run_dir: Path, stages: list[dict[str, Any]]) -> None:
    out_dir = _stage_outputs_dir(run_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for stage in stages:
        name = str(stage.get("name", "")).strip()
        if not name:
            continue
        (out_dir / f"{name}.txt").write_text(str(stage.get("text", "")), encoding="utf-8")


def _hydrate_stage_texts(run_dir: Path, stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out_dir = _stage_outputs_dir(run_dir)
    hydrated: list[dict[str, Any]] = []
    for stage in stages:
        current = dict(stage)
        name = str(current.get("name", "")).strip()
        if name:
            path = out_dir / f"{name}.txt"
            if path.exists():
                current["text"] = path.read_text(encoding="utf-8")
        hydrated.append(current)
    return hydrated


def _load_recorded_stages(path: Path) -> list[dict[str, Any]]:
    if path.is_dir():
        recorded_path = path / "recorded_stage_outputs.json"
        if recorded_path.exists():
            data = json.loads(recorded_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return _hydrate_stage_texts(path, data)
        manifest_path = path / "manifest.json"
    else:
        manifest_path = path
        if path.name == "manifest.json":
            sibling = path.parent / "recorded_stage_outputs.json"
            if sibling.exists():
                data = json.loads(sibling.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return _hydrate_stage_texts(path.parent, data)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stages = manifest.get("stages", [])
    return _hydrate_stage_texts(manifest_path.parent, stages if isinstance(stages, list) else [])


def _run_with_recorded_stage_outputs(recorded_stages: list[dict[str, Any]], fixture_inputs: dict[str, Any]) -> dict:
    original_inputs = briefing._build_morning_stack_inputs
    original_stage = briefing._run_briefing_stage
    queue = [_normalize_recorded_stage(stage) for stage in recorded_stages]

    def _fake_stage(
        name: str,
        role: str,
        prompt: str,
        lane: str,
        timeout: int,
        fallback_prompt: str | None = None,
    ) -> dict:
        if not queue:
            raise RuntimeError("recorded stage queue exhausted")
        source = queue.pop(0)
        if source.get("name") != name:
            raise RuntimeError(f"recorded stage mismatch: expected {name}, got {source.get('name')}")
        started = datetime.now()
        t0 = time.monotonic()
        finished = datetime.now()
        return {
            **source,
            "role": role,
            "lane": source.get("lane", lane),
            "prompt_words": len(prompt.split()),
            "prompt_preview": prompt[:240],
            "timeout_seconds": timeout,
            "max_internal_attempts": 0,
            "started_at": started.isoformat(timespec="milliseconds"),
            "finished_at": finished.isoformat(timespec="milliseconds"),
            "duration_ms": int((time.monotonic() - t0) * 1000),
        }

    try:
        briefing._build_morning_stack_inputs = lambda: dict(fixture_inputs)
        briefing._run_briefing_stage = _fake_stage
        return briefing.generate_briefing_bundle("morning")
    finally:
        briefing._build_morning_stack_inputs = original_inputs
        briefing._run_briefing_stage = original_stage


def run_replay(
    fixture_path: Path,
    roots: HarnessRoots,
    reference_time: str | None = None,
    recorded_from: Path | None = None,
) -> Path:
    _ensure_roots(roots)
    fixture = _load_fixture(fixture_path)
    run_id = _reference_key(reference_time or fixture.get("reference_time"))
    run_dir = _allocate_run_dir(roots.runs, run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    fixture_inputs = fixture["inputs"]
    inference_mode = "live"
    recorded_source = None

    if recorded_from is not None:
        manifest_path = recorded_from / "manifest.json" if recorded_from.is_dir() else recorded_from
        bundle = _run_with_recorded_stage_outputs(
            _load_recorded_stages(recorded_from),
            fixture_inputs,
        )
        inference_mode = "recorded"
        recorded_source = str(manifest_path)
    else:
        original = briefing._build_morning_stack_inputs
        try:
            briefing._build_morning_stack_inputs = lambda: dict(fixture_inputs)
            bundle = briefing.generate_briefing_bundle("morning")
        finally:
            briefing._build_morning_stack_inputs = original

    text = str(bundle.get("text", "") or "")
    generation = bundle.get("generation", {}) if isinstance(bundle.get("generation"), dict) else {}
    stages = generation.get("stages", []) if isinstance(generation.get("stages"), list) else []
    generation_path = generation.get("path")
    stage_names = [str(stage.get("name", "") or "").strip() for stage in stages if isinstance(stage, dict)]
    checks = [
        _check("fixture_has_inputs", bool(fixture_inputs), "fixture inputs are present"),
        _check("brief_text_present", bool(text.strip()), "generated brief text is present"),
        _check("generation_path_present", bool(str(generation_path or "").strip()), "generation path is recorded"),
        _check("stages_present", bool(stages), f"stage_count={len(stages)}"),
        _check("stage_names_present", len(stage_names) == len(stages) and all(stage_names), "all stages have names"),
        _check("staging_only", str(run_dir).startswith(str(roots.runs)), "run artifacts are under the harness runs root"),
    ]

    manifest = {
        "harness_mode": True,
        "dry_run": True,
        "harness_name": "morning_brief_harness",
        "task_name": "morning_brief",
        "flow": "morning_brief",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inference_mode": inference_mode,
        "reference_time": reference_time or fixture.get("reference_time"),
        "fixture_path": str(fixture_path),
        "staging_root": str(roots.root),
        "recorded_source": recorded_source,
        "generation_path": generation_path,
        "stages": stages,
        "checks": checks,
        **_evidence_counts(checks),
    }
    _write_stage_outputs(run_dir, manifest["stages"])
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "generated_brief.txt").write_text(text, encoding="utf-8")
    (run_dir / "input_fixture_copy.json").write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    (run_dir / "recorded_stage_outputs.json").write_text(
        json.dumps(bundle.get("generation", {}).get("stages", []), indent=2),
        encoding="utf-8",
    )
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Morning briefing staging/replay harness")
    parser.add_argument("--capture-fixture", metavar="NAME", help="Capture a morning-brief input bundle fixture")
    parser.add_argument("--fixture", type=Path, help="Replay this fixture file")
    parser.add_argument("--recorded-from", type=Path, help="Reuse recorded stage outputs from a prior run manifest or run directory")
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

    fixture_path = args.fixture or (roots.fixtures / "sample_morning.json")
    run_dir = run_replay(
        fixture_path,
        roots,
        reference_time=args.reference_time,
        recorded_from=args.recorded_from,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
