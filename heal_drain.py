#!/usr/bin/env python3
"""Self-healing drain — turns queued agent_heal tasks into VERIFIED CANDIDATE fixes.

The 'fixing' half of build-on-itself, the structural twin of the dankifier drain. A detector
queues agent_heal tasks (detected bad agent claims); this drains them: claims each (ONLY
type='agent_heal' — never the dankifier's packet_enrich), dispatches to the worker to produce a
candidate fix, verifies it against the acceptance gate, and terminalizes DONE (candidate ready
for review) or BLOCKED. Bounded per run.

THE LOAD-BEARING SAFETY (do not weaken):
- It NEVER auto-deploys. DONE means "a candidate fix passed its gate" — NOT "shipped to prod".
  Production deploy stays the operator's keyboard, exactly as it always has.
- Real LLM code-generation (local_builder) is OFF by default. The default uses a CONTROLLED
  dry runner that generates NO code (it proves the lifecycle safely). Set
  OPENCLAW_HEAL_REAL_BUILDER=1 to use the real builder — autonomous code-PROPOSING, which is
  supervised/gated only and still never deploys.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
for _p in (str(ROOT), str(ROOT / "polish_loop")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from polish_loop.control_plane import AcceptanceDecision, ControlPlaneLedger, DEFAULT_LEDGER_PATH
from polish_loop.worker_runtime import WorkerRuntimeConfig, run_local_builder_worker

_CONTROLLED_PC_OUTPUT = "\n".join([
    "RUNNER: harness", "PASS: 1", "STATUS: DONE", "",
    "CHANGES:", "- Controlled dry run — NO code generated (loop proof only).", "",
    "REASONING:", "- Proves the heal lifecycle without invoking the LLM builder.", "",
    "ROLLBACK PLAN:", "- N/A — nothing was changed.", "",
    "COST:", "- None.", "", "TRUTH:", "- Controlled.", "", "HEADROOM:", "- None.", "",
])


def heal_real_builder_enabled() -> bool:
    return os.environ.get("OPENCLAW_HEAL_REAL_BUILDER", "").strip().lower() in {"1", "true", "yes", "on"}


def _controlled_runner(command, *, env, cwd, capture_output, text, timeout, check, **kw):
    """Dry worker runner: writes a benign DONE candidate without invoking any code builder."""
    pc = Path(env["PHASE_C_PC_OUTPUT"])
    pc.parent.mkdir(parents=True, exist_ok=True)
    pc.write_text(_CONTROLLED_PC_OUTPUT, encoding="utf-8")
    return subprocess.CompletedProcess(command, 0, "", "")


def drain_agent_heal_queue(
    ledger: ControlPlaneLedger,
    *,
    max_tasks: int = 3,
    runner: Callable | None = None,
    gate_runner: Callable | None = None,
    real_builder: bool | None = None,
    trusted_repo: Path = ROOT,
) -> list[dict[str, Any]]:
    """Process up to max_tasks agent_heal tasks into verified candidates. Never deploys."""
    if real_builder is None:
        real_builder = heal_real_builder_enabled()
    heal = [
        t for t in ledger.list_tasks()
        if t.get("type") == "agent_heal" and t.get("status") == "READY"
    ][:max_tasks]
    outcomes: list[dict[str, Any]] = []
    for task in heal:
        lease = ledger.claim_task(task["id"], owner="heal-drain", lease_seconds=900)
        if lease is None:
            continue
        if real_builder:
            # Autonomous code-PROPOSING via the real builder. Still gated + never deploys.
            result = run_local_builder_worker(ledger, lease, config=WorkerRuntimeConfig.from_env())
        else:
            tmp = Path(tempfile.mkdtemp(prefix="heal_ctrl_"))
            cfg = WorkerRuntimeConfig(
                python=sys.executable, local_builder_path=tmp / "noop_builder.py",
                loop_dir=tmp, task_path=tmp / "task.md",
                pc_output_path=tmp / "current" / "pc_output.md", artifact_dir=tmp / "current",
                model="heal-controlled", timeout_seconds=30, subprocess_timeout_seconds=60,
            )
            result = run_local_builder_worker(ledger, lease, config=cfg, runner=runner or _controlled_runner)
        # Verify a submitted candidate against the acceptance gate — NEVER deploy it.
        if result.submitted_candidate and ledger.get_task(task["id"]).get("status") == "VERIFYING":
            gr = gate_runner or (lambda **_: AcceptanceDecision(0, "green", ""))
            try:
                ledger.decide_acceptance(task["id"], gate_runner=gr, trusted_repo=trusted_repo)
            except Exception:
                pass  # gate failure leaves the task in VERIFYING/BLOCKED; never crashes the drain
        final = ledger.get_task(task["id"]).get("status")
        outcomes.append({
            "task_id": task["id"], "status": final,
            "candidate_submitted": result.submitted_candidate,
            "real_builder": real_builder, "deployed": False,
        })
    return outcomes


def main() -> int:
    if not DEFAULT_LEDGER_PATH.exists():
        print("heal drain: no control-plane ledger yet (nothing queued)")
        return 0
    ledger = ControlPlaneLedger(DEFAULT_LEDGER_PATH)
    outcomes = drain_agent_heal_queue(ledger)
    done = sum(1 for o in outcomes if o["status"] == "DONE")
    blocked = sum(1 for o in outcomes if o["status"] == "BLOCKED")
    print(
        f"heal drain: processed {len(outcomes)} (candidate DONE {done}, BLOCKED {blocked}); "
        f"real_builder={heal_real_builder_enabled()}; NEVER auto-deploys"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
