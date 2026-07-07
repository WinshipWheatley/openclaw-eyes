#!/usr/bin/env python3
"""Auto-refresh mechanism for stale packet read-model sources.

This module is the follow-up to the read-only `read_model_freshness_audit.py`
utility. Where that script only *reports* rot, this one *repairs* it: it maps
every read-model source that packet builders consume to an explicit,
data-driven refresh disposition (a safe local regeneration command, or an
honest `refreshable: false` reason), then drives a bounded auto-refresh pass:

    audit -> for each stale+refreshable source, run its registered producer
    -> re-audit -> write a receipt.

Design constraints (see Operator/CODEX-FRESHNESS-AWARENESS-RESULT.md and the
Priority-3 build brief this module was written against):

- No silent omissions: every read-model name discovered by
  `discover_packet_read_models()` must have a registry entry.
- Failures are honest: a failed refresh action is recorded, never retried
  within a single run, and never disguised as success.
- No network sends. No writes outside the repo's own governed local state
  (its own SQLite ledger, its own generated/read_models tree) as part of the
  *automated* refresh path. A few real producers default to also mirroring
  output to a live Windows-bridge mount (`/mnt/e/openclaw/...`); those are
  either redirected to a local-only path via their own supported CLI flags
  (`--no-bridge`, `--bridge-export-root`) or marked non-refreshable when no
  safe local-only invocation exists.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from read_model_freshness_audit import (
    DEFAULT_STALE_AFTER_DAYS,
    audit_read_models,
    discover_packet_read_models,
)


DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_STATUS_FILENAME = "read_model_auto_refresh_status.json"
DEFAULT_TIMEOUT_SECONDS = 90
SCHEMA_VERSION = "read_model_auto_refresh_v0"

# Freshness statuses that mean "this source needs attention" (mirrors the
# problem-status set used by read_model_freshness_audit.audit_read_models).
_PROBLEM_STATUSES = frozenset({"stale", "missing_file", "missing_timestamp", "bad_json", "unknown"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def refresh_step(
    *args: str,
    generated_at_flag: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Build one command step for a registry entry.

    `args` is the argv for the step, starting with the script/module path
    (relative to the repo root) followed by its CLI flags. `generated_at_flag`
    is set for producers whose CLI accepts a `--generated-at` override; the
    runner appends `[flag, <fresh iso8601 timestamp>]` right before invoking
    so a "refresh" cannot silently no-op against a producer that hardcodes a
    frozen default timestamp (a real bug found in three producers below).
    """

    return {
        "args": list(args),
        "generated_at_flag": generated_at_flag,
        "timeout_seconds": timeout_seconds,
    }


# ---------------------------------------------------------------------------
# The refresh registry.
#
# Every name discovered by discover_packet_read_models() (25 sources as of
# the 2026-07-01 audit, including the currently-missing
# reynolds_gig_setup_status.json) must appear here with an explicit
# disposition. See the docstrings/reasons below for the safety judgment made
# for each source; nothing here silently guesses.
# ---------------------------------------------------------------------------

READ_MODEL_REFRESH_REGISTRY: dict[str, dict[str, Any]] = {
    # -- currently-fresh sources (still registered so they don't silently
    #    drift once they do go stale) -----------------------------------
    "agent_presence.json": {
        "refreshable": True,
        "reason": "Pure local export from the governed business-ops SQLite ledger; no network, no external mount.",
        "steps": [refresh_step("scripts/export_agent_presence_read_model.py", "--format", "json")],
    },
    "niles_track_registry.json": {
        "refreshable": True,
        "reason": "Reads a governed local CSV (.openclaw/agents/chief/album/track-registry.csv) and writes only to generated/read_models.",
        "steps": [refresh_step("scripts/export_niles_track_registry_read_model.py")],
    },
    "openclaw_capability_index.json": {
        "refreshable": True,
        "reason": "Pure local export; generated_at defaults to None (fresh utc_now internally), no frozen-timestamp trap.",
        "steps": [refresh_step("scripts/export_openclaw_capability_index.py", "--format", "json")],
    },
    "openclaw_change_sentinel.json": {
        "refreshable": True,
        "reason": "Pure local export to generated/read_models and generated/system_knowledge; no network.",
        "steps": [refresh_step("scripts/export_openclaw_change_sentinel.py", "--format", "json")],
    },
    "orchestration_progress.json": {
        "refreshable": True,
        "reason": "Derives shipped milestones from local read-only `git log`; writes only generated/read_models/orchestration_progress.json.",
        "steps": [refresh_step("scripts/export_orchestration_progress_read_model.py")],
    },
    "sync_health.json": {
        "refreshable": True,
        "reason": "Pure local export from the governed business-ops SQLite ledger; no network, no external mount.",
        "steps": [refresh_step("scripts/export_sync_health_read_model.py", "--format", "json")],
    },
    "client_invoice_workflow_framework.json": {
        "refreshable": True,
        "reason": "Pure local export of the curated client invoice-workflow framework (which clients use Coupa/PO vs not); no network, no external mount. Added when task 88 wired it as a freeform-brain packet source.",
        "steps": [refresh_step("scripts/export_client_invoice_workflow_framework.py")],
    },
    # -- the 18 sources the real audit found stale -----------------------
    "capital_hilton_invoice_operator_readback.json": {
        "refreshable": True,
        "reason": (
            "Pure local export (no external mount dependency). The module hardcodes "
            "DEFAULT_GENERATED_AT to a frozen historical timestamp (2026-05-25), so a bare "
            "re-run would keep rewriting the same stale date forever; the registry injects a "
            "fresh --generated-at at refresh time to make the refresh real, not cosmetic."
        ),
        "steps": [
            refresh_step(
                "scripts/export_capital_hilton_invoice_operator_readback.py",
                "--format",
                "json",
                generated_at_flag="--generated-at",
            )
        ],
    },
    "capital_hilton_invoice_operator_run_status.json": {
        "refreshable": False,
        "reason": (
            "Producer (capital_hilton_invoice_operator_run_status.py) unconditionally mirrors "
            "its output to the live Windows-bridge mount /mnt/e/openclaw/generated/read_models "
            "with no --no-bridge escape hatch (unlike the hermes_* producers), and its content "
            "is driven by discrete operator-dropped receipt files under "
            "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton rather than internal "
            "system state. An unattended cron re-run either fails (no new receipt) or restates "
            "old data under a new timestamp without any new ground truth. Needs an "
            "operator-supervised run, not a blind auto-refresh."
        ),
    },
    "cassandra_draft_review_packet.json": {
        "refreshable": True,
        "reason": "Pure local export from generated read-model inputs; no network, no external mount.",
        "steps": [refresh_step("scripts/export_cassandra_draft_review_packet.py", "--format", "json")],
    },
    "cassandra_email_calendar_delta_detangle.json": {
        "refreshable": True,
        "reason": "Pure local export; no network, no external mount.",
        "steps": [refresh_step("scripts/export_cassandra_email_calendar_delta_detangle.py", "--format", "json")],
    },
    "cassandra_governed_review_packet_request_proof.json": {
        "refreshable": True,
        "reason": "Pure local export from the governed business-ops SQLite ledger; no network.",
        "steps": [refresh_step("scripts/export_cassandra_governed_review_packet_request_proof.py", "--format", "json")],
    },
    "cassandra_listener_governed_intake_synthetic_proof.json": {
        "refreshable": True,
        "reason": (
            "Writes a synthetic (non-live) Telegram-intake proof row to the local governed "
            "ledger (telegram_api_called stays False); no real Telegram API call is made."
        ),
        "steps": [refresh_step("scripts/export_cassandra_listener_governed_intake_synthetic_proof.py", "--format", "json")],
    },
    "cassandra_runtime_wiring_audit.json": {
        "refreshable": True,
        "reason": (
            "Two-step build+export pair. Both steps are local-only: `build` shells out to "
            "read-only `git` commands and `systemctl --user show` (status query, not a "
            "mutation) to refresh the local ledger row; `export` serializes that row to json."
        ),
        "steps": [
            refresh_step("scripts/build_cassandra_runtime_wiring_audit.py", "--format", "json"),
            refresh_step("scripts/export_cassandra_runtime_wiring_audit_read_model.py", "--format", "json"),
        ],
    },
    "cassandra_send_status_dry_run.json": {
        "refreshable": True,
        "reason": "Self-contained dry-run status generator; telegram_delivery_blocked stays True, no real send.",
        "steps": [refresh_step("scripts/export_cassandra_send_status_dry_run_read_model.py", "--format", "json")],
    },
    "chief_status_rail.json": {
        "refreshable": True,
        "reason": "Pure local export; generated_at defaults to utc_now() internally, no frozen-timestamp trap.",
        "steps": [refresh_step("scripts/export_chief_status_rail.py", "--format", "json")],
    },
    "finance_invoice_reconciliation.json": {
        "refreshable": True,
        "reason": (
            "Two-step build+export pair. `build` scans a local quarantined repo checkout "
            "(/home/openclaw_external/openclaw-runtime) read-only via `git` metadata calls "
            "and writes only to the local governed ledger/Work Board; `export` serializes the "
            "latest row to json. No network, no send, no bank access (asserted by its own "
            "boundary check on the scanned source text)."
        ),
        "steps": [
            refresh_step("scripts/build_finance_invoice_reconciliation.py", "--format", "json"),
            refresh_step("scripts/export_finance_invoice_reconciliation_read_model.py", "--format", "json"),
        ],
    },
    "hermes_chief_build_handoff.json": {
        "refreshable": True,
        "reason": (
            "Local export supports --no-bridge, used here so the unattended refresh loop never "
            "mutates the live /mnt/e/openclaw Windows-bridge mount. Also hardcodes a frozen "
            "DEFAULT_GENERATED_AT, so the registry injects a fresh --generated-at."
        ),
        "steps": [
            refresh_step(
                "scripts/export_hermes_chief_build_handoff.py",
                "--no-bridge",
                generated_at_flag="--generated-at",
            )
        ],
    },
    "hermes_gravity_controller.json": {
        "refreshable": True,
        "reason": (
            "Pure local export (no bridge mirror in this producer). Hardcodes a frozen "
            "DEFAULT_GENERATED_AT, so the registry injects a fresh --generated-at."
        ),
        "steps": [
            refresh_step(
                "scripts/export_hermes_gravity_controller.py",
                "--format",
                "json",
                generated_at_flag="--generated-at",
            )
        ],
    },
    "hermes_mission_sentinel.json": {
        "refreshable": True,
        "reason": (
            "Local export supports --no-bridge, used here so the unattended refresh loop never "
            "mutates the live /mnt/e/openclaw Windows-bridge mount. Also hardcodes a frozen "
            "DEFAULT_GENERATED_AT, so the registry injects a fresh --generated-at."
        ),
        "steps": [
            refresh_step(
                "scripts/export_hermes_mission_sentinel.py",
                "--no-bridge",
                generated_at_flag="--generated-at",
            )
        ],
    },
    "niles_album_matrix_review.json": {
        "refreshable": True,
        "reason": "Pure local export; no network, no external mount.",
        "steps": [refresh_step("scripts/export_niles_album_matrix_review.py", "--format", "json")],
    },
    "niles_album_metadata_intake_packet.json": {
        "refreshable": True,
        "reason": "Pure local export; no network, no external mount.",
        "steps": [refresh_step("scripts/export_niles_album_metadata_intake_packet.py", "--format", "json")],
    },
    "niles_album_review_packet.json": {
        "refreshable": True,
        "reason": "Pure local export; no network, no external mount.",
        "steps": [refresh_step("scripts/export_niles_album_review_packet.py", "--format", "json")],
    },
    "openclaw_hermes_sidecar.json": {
        "refreshable": True,
        "reason": "Pure local export (json/operator/sqlite all written under the repo); no network.",
        "steps": [refresh_step("scripts/export_openclaw_hermes_sidecar.py", "--format", "json")],
    },
    "work_board.json": {
        "refreshable": True,
        "reason": "Pure local export from the governed business-ops SQLite ledger; no network, no external mount.",
        "steps": [refresh_step("scripts/export_work_board_read_model.py", "--format", "json")],
    },
    # -- the 1 source the real audit found missing -----------------------
    "reynolds_gig_setup_status.json": {
        "refreshable": True,
        "reason": (
            "Producer module reynolds_gig_setup_status.py exists on the live host (it defines "
            "build_reynolds_gig_setup_status(), export_read_model(), and a CLI main()) but, like "
            "capital_hilton_agency_status.py, is untracked/gitignored because it may carry real "
            "client gig data; conftest.py installs a redacted stub for tests. It reads a static "
            "captured fixture (/mnt/e/openclaw/orchestration/artifacts/reynolds/gig_facts.json, "
            "read-only) and writes only to generated/read_models -- no bridge mirror, no ledger "
            "write, no send. This entry point is valid for production runs only; it cannot be "
            "exercised from this worktree or from the test suite."
        ),
        "steps": [refresh_step("reynolds_gig_setup_status.py", "--export-root", "generated/read_models")],
    },
}


def _entry_command(python_executable: str, step: Mapping[str, Any], *, generated_at_iso: str) -> list[str]:
    args = list(step["args"])
    flag = step.get("generated_at_flag")
    if flag:
        args = [*args, flag, generated_at_iso]
    return [python_executable, *args]


def _stdout_tail(text: str, limit: int = 2000) -> str:
    text = text or ""
    return text[-limit:]


def _run_steps(
    steps: Sequence[Mapping[str, Any]],
    *,
    python_executable: str,
    repo_root: Path,
    generated_at_iso: str,
    runner: Callable[..., Any],
) -> dict[str, Any]:
    """Run each step in order; stop at the first failure. Never retries."""

    executed: list[dict[str, Any]] = []
    for step in steps:
        cmd = _entry_command(python_executable, step, generated_at_iso=generated_at_iso)
        timeout = int(step.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
        record: dict[str, Any] = {"cmd": cmd, "timeout_seconds": timeout}
        try:
            completed = runner(cmd, cwd=repo_root, capture_output=True, text=True, timeout=timeout)
            record["returncode"] = completed.returncode
            record["stdout_tail"] = _stdout_tail(getattr(completed, "stdout", "") or "")
            record["stderr_tail"] = _stdout_tail(getattr(completed, "stderr", "") or "")
            record["timed_out"] = False
            record["ok"] = completed.returncode == 0
        except subprocess.TimeoutExpired as exc:
            record["returncode"] = None
            record["stdout_tail"] = _stdout_tail(str(exc.stdout or ""))
            record["stderr_tail"] = _stdout_tail(str(exc.stderr or "") or f"timed out after {timeout}s")
            record["timed_out"] = True
            record["ok"] = False
        except OSError as exc:
            record["returncode"] = None
            record["stdout_tail"] = ""
            record["stderr_tail"] = f"{type(exc).__name__}: {exc}"
            record["timed_out"] = False
            record["ok"] = False
        executed.append(record)
        if not record["ok"]:
            break
    return {
        "steps": executed,
        "ok": bool(executed) and all(step["ok"] for step in executed),
    }


def run_auto_refresh(
    threshold_days: int = DEFAULT_STALE_AFTER_DAYS,
    *,
    names: Iterable[str] | None = None,
    registry: Mapping[str, Mapping[str, Any]] | None = None,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    repo_root: str | Path = Path("."),
    dry_run: bool = False,
    write_receipt: bool = True,
    status_filename: str = DEFAULT_STATUS_FILENAME,
    python_executable: str | None = None,
    runner: Callable[..., Any] = subprocess.run,
    now: Callable[[], datetime] = _utc_now,
) -> dict[str, Any]:
    """Audit read-model freshness and refresh whatever is stale+refreshable.

    Never raises on a generator failure; every outcome (refreshed, failed,
    not_refreshable, no_registry_entry, skipped_fresh,
    still_stale_after_refresh) is recorded honestly in the returned receipt.
    A generator is invoked at most once per source per call -- failures are
    never retried in a loop within a single run.
    """

    repo_root_path = Path(repo_root)
    read_model_root_path = Path(read_model_root)
    reg: Mapping[str, Mapping[str, Any]] = registry if registry is not None else READ_MODEL_REFRESH_REGISTRY
    resolved_names = sorted({str(n).strip() for n in (names if names is not None else discover_packet_read_models()) if str(n).strip()})
    resolved_python = python_executable or sys.executable

    moment = now()
    today: date = moment.date()
    generated_at_iso = moment.isoformat()

    before = audit_read_models(
        resolved_names,
        read_model_root=read_model_root_path,
        repo_root=repo_root_path,
        today=today,
        stale_after_days=threshold_days,
    )
    before_by_name = {item["name"]: item for item in before["items"]}

    items: list[dict[str, Any]] = []
    executed_any = False

    for name in resolved_names:
        before_item = before_by_name.get(name, {"name": name, "freshness_status": "missing_file", "timestamp": "", "age_days": None})
        entry = reg.get(name)
        record: dict[str, Any] = {
            "name": name,
            "path": before_item.get("path", (read_model_root_path / name).as_posix()),
            "before_status": before_item.get("freshness_status"),
            "before_timestamp": before_item.get("timestamp", ""),
            "before_age_days": before_item.get("age_days"),
        }

        needs_refresh = before_item.get("freshness_status") in _PROBLEM_STATUSES

        if not needs_refresh:
            record.update(
                {
                    "refreshable": bool(entry.get("refreshable")) if entry else None,
                    "action_attempted": False,
                    "result": "skipped_fresh",
                    "reason": "already fresh; no action needed",
                    "after_status": before_item.get("freshness_status"),
                    "after_timestamp": before_item.get("timestamp", ""),
                    "after_age_days": before_item.get("age_days"),
                }
            )
            items.append(record)
            continue

        if entry is None:
            record.update(
                {
                    "refreshable": None,
                    "action_attempted": False,
                    "result": "no_registry_entry",
                    "reason": "read-model discovered by packet builders but absent from the refresh registry",
                    "after_status": before_item.get("freshness_status"),
                    "after_timestamp": before_item.get("timestamp", ""),
                    "after_age_days": before_item.get("age_days"),
                }
            )
            items.append(record)
            continue

        if not entry.get("refreshable"):
            record.update(
                {
                    "refreshable": False,
                    "action_attempted": False,
                    "result": "not_refreshable",
                    "reason": entry.get("reason", ""),
                    "after_status": before_item.get("freshness_status"),
                    "after_timestamp": before_item.get("timestamp", ""),
                    "after_age_days": before_item.get("age_days"),
                }
            )
            items.append(record)
            continue

        steps = entry.get("steps") or []
        planned_commands = [
            _entry_command(resolved_python, step, generated_at_iso=generated_at_iso) for step in steps
        ]

        if dry_run:
            record.update(
                {
                    "refreshable": True,
                    "action_attempted": False,
                    "result": "planned",
                    "reason": entry.get("reason", ""),
                    "planned_commands": planned_commands,
                    "after_status": before_item.get("freshness_status"),
                    "after_timestamp": before_item.get("timestamp", ""),
                    "after_age_days": before_item.get("age_days"),
                }
            )
            items.append(record)
            continue

        action = _run_steps(
            steps,
            python_executable=resolved_python,
            repo_root=repo_root_path,
            generated_at_iso=generated_at_iso,
            runner=runner,
        )
        executed_any = True
        record["action_attempted"] = True
        record["action"] = {
            "steps": action["steps"],
            "stdout_tail": _stdout_tail("\n".join(s.get("stdout_tail", "") for s in action["steps"])),
            "stderr_tail": _stdout_tail("\n".join(s.get("stderr_tail", "") for s in action["steps"])),
        }
        record["refreshable"] = True
        record["reason"] = entry.get("reason", "")

        if not action["ok"]:
            record["result"] = "failed"
            record["after_status"] = before_item.get("freshness_status")
            record["after_timestamp"] = before_item.get("timestamp", "")
            record["after_age_days"] = before_item.get("age_days")
        else:
            # Deferred: filled in after the post-refresh audit below.
            record["result"] = "_pending_after_audit"
        items.append(record)

    if executed_any and not dry_run:
        after = audit_read_models(
            resolved_names,
            read_model_root=read_model_root_path,
            repo_root=repo_root_path,
            today=today,
            stale_after_days=threshold_days,
        )
        after_by_name = {item["name"]: item for item in after["items"]}
        for record in items:
            if record.get("result") != "_pending_after_audit":
                continue
            after_item = after_by_name.get(record["name"], {})
            record["after_status"] = after_item.get("freshness_status")
            record["after_timestamp"] = after_item.get("timestamp", "")
            record["after_age_days"] = after_item.get("age_days")
            if after_item.get("freshness_status") == "fresh":
                record["result"] = "refreshed"
            else:
                record["result"] = "still_stale_after_refresh"

    summary_keys = (
        "refreshed",
        "failed",
        "not_refreshable",
        "no_registry_entry",
        "skipped_fresh",
        "still_stale_after_refresh",
        "planned",
    )
    counts = {key: 0 for key in summary_keys}
    for record in items:
        result = record["result"]
        if result in counts:
            counts[result] += 1

    summary = {
        "source_count": len(resolved_names),
        **{f"{key}_count": value for key, value in counts.items()},
        "threshold_days": threshold_days,
        "today": today.isoformat(),
    }

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at_iso,
        "dry_run": dry_run,
        "threshold_days": threshold_days,
        "repo_root": repo_root_path.as_posix(),
        "read_model_root": read_model_root_path.as_posix(),
        "summary": summary,
        "items": items,
    }

    if write_receipt and not dry_run:
        read_model_root_path.mkdir(parents=True, exist_ok=True)
        status_path = read_model_root_path / status_filename
        status_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        receipt["status_path"] = status_path.as_posix()

    return receipt


def format_operator_summary(receipt: Mapping[str, Any]) -> str:
    summary = receipt["summary"]
    lines = [
        "Read-Model Auto-Refresh v0",
        "",
        f"Sources audited: {summary['source_count']} (threshold {summary['threshold_days']}d, as of {summary['today']})",
        f"Refreshed: {summary['refreshed_count']}",
        f"Already fresh: {summary['skipped_fresh_count']}",
        f"Not refreshable (documented reason): {summary['not_refreshable_count']}",
        f"Planned (dry run): {summary['planned_count']}",
        f"Failed: {summary['failed_count']}",
        f"Still stale after refresh attempt: {summary['still_stale_after_refresh_count']}",
        f"No registry entry (gap): {summary['no_registry_entry_count']}",
    ]
    if receipt.get("status_path"):
        lines.append("")
        lines.append(f"Receipt: `{receipt['status_path']}`")
    return "\n".join(lines)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit and auto-refresh stale packet read-model sources."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        required=True,
        help="Run exactly one audit+refresh pass. Suitable for cron/systemd timers.",
    )
    parser.add_argument("--threshold-days", type=int, default=DEFAULT_STALE_AFTER_DAYS)
    parser.add_argument("--dry-run", action="store_true", help="Print the refresh plan; execute nothing.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--status-filename", default=DEFAULT_STATUS_FILENAME)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    receipt = run_auto_refresh(
        args.threshold_days,
        read_model_root=Path(args.read_model_root),
        repo_root=Path(args.repo_root),
        dry_run=args.dry_run,
        status_filename=args.status_filename,
    )

    if args.format == "json":
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(format_operator_summary(receipt))

    if args.dry_run:
        return 0
    summary = receipt["summary"]
    if summary["failed_count"] or summary["no_registry_entry_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
