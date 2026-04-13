#!/usr/bin/env python3
"""
Pure validation harness for Guardian approval input schema.

No Telegram, no network, no live approval writes.
All I/O goes to the staging root only.

Mirrors the morning_brief_harness / chief_eod_harness pattern:
  --fixture     replay against a given fixture file
  --staging-root  override staging root
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

STAGING_DEFAULT = Path("/home/openclaw/staging/guardian_schema_harness")
LIVE_PENDING    = Path("/mnt/c/OpenClaw/logs/approval_pending.json")


@dataclass
class HarnessRoots:
    root: Path
    fixtures: Path
    runs: Path


def _default_roots() -> HarnessRoots:
    root = STAGING_DEFAULT
    return HarnessRoots(root=root, fixtures=root / "fixtures", runs=root / "runs")


def _ensure_roots(roots: HarnessRoots) -> None:
    roots.fixtures.mkdir(parents=True, exist_ok=True)
    roots.runs.mkdir(parents=True, exist_ok=True)


def _allocate_run_dir(runs_root: Path) -> Path:
    base = datetime.now().strftime("%Y%m%dT%H%M%S")
    candidate = runs_root / base
    if not candidate.exists():
        return candidate
    idx = 1
    while True:
        c = runs_root / f"{base}-r{idx}"
        if not c.exists():
            return c
        idx += 1


def _load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Test case runners
# ---------------------------------------------------------------------------

def _run_parse_reply_code(
    case: dict[str, Any],
    cab: Any,
    pending_file: Path,
    pending_state: dict[str, Any],
    run_options: int,
) -> dict[str, Any]:
    """Run one parse_reply_code test case."""
    options = case.get("options", run_options)
    # Write fresh pending state with the case's option count
    state = dict(pending_state)
    state["options"] = options
    pending_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    decision, error = cab.parse_reply_code(
        case["text"],
        case["pending_id"],
        options=options,
    )

    result: dict[str, Any] = {
        "desc": case["desc"],
        "fn": "parse_reply_code",
        "input": {"text": case["text"], "pending_id": case["pending_id"], "options": options},
        "got_decision": decision,
        "got_error": error,
        "pass": False,
        "fail_reason": "",
    }

    expect_decision  = case.get("expect_decision", "")
    expect_error     = case.get("expect_error", None)
    expect_error_has = case.get("expect_error_contains", "")

    if decision != expect_decision:
        result["fail_reason"] = f"decision: expected={expect_decision!r} got={decision!r}"
    elif expect_error is not None and error != expect_error:
        result["fail_reason"] = f"error: expected={expect_error!r} got={error!r}"
    elif expect_error_has and expect_error_has.lower() not in error.lower():
        result["fail_reason"] = f"error missing substring {expect_error_has!r}: got={error!r}"
    else:
        result["pass"] = True

    return result


def _run_record_decision(
    case: dict[str, Any],
    cab: Any,
    pending_file: Path,
    pending_state: dict[str, Any],
) -> dict[str, Any]:
    """Run one record_decision test case."""
    options = case.get("options", 2)
    # Write fresh pending state for each record_decision call
    state = dict(pending_state)
    state["options"] = options
    pending_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    reply = cab.record_decision(case["decision"], expected_id=case.get("expected_id", ""))

    result: dict[str, Any] = {
        "desc": case["desc"],
        "fn": "record_decision",
        "input": {"decision": case["decision"], "expected_id": case.get("expected_id", ""), "options": options},
        "got_reply": reply,
        "pass": False,
        "fail_reason": "",
    }

    expect_reply     = case.get("expect_reply", None)
    expect_reply_has = case.get("expect_reply_contains", "")

    if expect_reply is not None and reply != expect_reply:
        result["fail_reason"] = f"reply: expected={expect_reply!r} got={reply!r}"
    elif expect_reply_has and expect_reply_has.lower() not in reply.lower():
        result["fail_reason"] = f"reply missing substring {expect_reply_has!r}: got={reply!r}"
    else:
        result["pass"] = True

    return result


# ---------------------------------------------------------------------------
# Main replay entry
# ---------------------------------------------------------------------------

def run_replay(fixture_path: Path, roots: HarnessRoots) -> Path:
    """
    Run all test cases in the fixture.
    All file writes go to run_dir only — never to LIVE_PENDING.
    """
    _ensure_roots(roots)
    fixture = _load_fixture(fixture_path)
    run_dir = _allocate_run_dir(roots.runs)
    run_dir.mkdir(parents=True, exist_ok=True)

    # Staging-only pending file — patch the module-level constant before any calls
    staging_pending = run_dir / "pending_state.json"

    import chief_approval_brain as cab
    original_pending = cab.PENDING_FILE
    cab.PENDING_FILE = staging_pending
    try:
        pending_state = fixture["pending_state"]
        test_cases    = fixture.get("test_cases", [])
        results: list[dict[str, Any]] = []

        for case in test_cases:
            fn = case.get("fn", "parse_reply_code")
            if fn == "record_decision":
                r = _run_record_decision(case, cab, staging_pending, pending_state)
            else:
                r = _run_parse_reply_code(case, cab, staging_pending, pending_state, 2)
            results.append(r)
    finally:
        # Always restore the original path — never leave live path patched out
        cab.PENDING_FILE = original_pending

    passed = sum(1 for r in results if r["pass"])
    failed = len(results) - passed

    manifest = {
        "harness_mode": True,
        "dry_run": True,
        "flow": "guardian_schema_retest",
        "fixture_path": str(fixture_path),
        "staging_root": str(roots.root),
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "total_cases": len(results),
        "passed": passed,
        "failed": failed,
        "live_pending_touched": False,
        "results": results,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "input_fixture_copy.json").write_text(
        json.dumps(fixture, indent=2), encoding="utf-8"
    )

    # Confirm live pending was never written
    _guard_live_not_written()

    return run_dir


def _guard_live_not_written() -> None:
    """Fail loudly if the live approval_pending.json was mutated by this harness."""
    # The live path should either not exist, or have pre-existing content.
    # Since we patched PENDING_FILE away, this should never be an issue —
    # but we assert it explicitly as a damage gate.
    if LIVE_PENDING.exists():
        content = LIVE_PENDING.read_text(encoding="utf-8", errors="replace")
        if '"guardian_schema_harness"' in content:
            raise RuntimeError(
                f"DAMAGE GATE: live approval pending file contains harness requester. "
                f"Harness write leaked to {LIVE_PENDING}. Aborting."
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Guardian approval schema validation harness")
    parser.add_argument("--fixture", type=Path, help="Fixture file to replay")
    parser.add_argument("--staging-root", type=Path, help="Override staging root")
    args = parser.parse_args()

    roots = _default_roots()
    if args.staging_root:
        roots = HarnessRoots(
            root=args.staging_root,
            fixtures=args.staging_root / "fixtures",
            runs=args.staging_root / "runs",
        )

    fixture_path = args.fixture or (roots.fixtures / "guardian_validation.json")
    if not fixture_path.exists():
        print(f"ERROR: fixture not found: {fixture_path}", file=sys.stderr)
        sys.exit(1)

    run_dir = run_replay(fixture_path, roots)

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    print(run_dir)
    print(f"passed={manifest['passed']} failed={manifest['failed']} total={manifest['total_cases']}")

    if manifest["failed"] > 0:
        print("FAILED CASES:", file=sys.stderr)
        for r in manifest["results"]:
            if not r["pass"]:
                print(f"  [{r['fn']}] {r['desc']}: {r['fail_reason']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
