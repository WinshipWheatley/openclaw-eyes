#!/usr/bin/env python3
"""Cron/systemd-timer entry point for the perpetual self-knowledge engine's
scheduled incremental crawl.

Arbiter-aware: defers honestly instead of running when an interactive GPU
lease is active (see `self_knowledge_scheduler.run_scheduled_crawl`). This
script only crawls and reports; it never writes ledger state itself — gated
ledger writes are a separate, explicit step via
`self_knowledge_ledger_gap_writer.write_gaps_to_ledger(..., confirm=True)`.

This is the template's ExecStart target for
`systemd/user/self-knowledge-crawl.service.in` /
`self-knowledge-crawl.timer.in`. Those unit templates are NOT installed or
enabled by this change — see the templates for the install convention used
by every other `*.service.in` in this repo (`scripts/install_openclaw_stack.sh`
/ `scripts/manage_openclaw_local_services.py`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from self_knowledge_scheduler import run_scheduled_crawl  # noqa: E402

# Placeholder, self-knowledge-engine-scoped lease/state DB locations. The
# fleet-wide GPU arbiter lease path (if/when interactive sessions actually
# write leases here) is owned by a different workstream — point
# --lease-db-path at that path once it exists so this crawl truly yields to
# interactive use; until then this defaults to its own isolated file, which
# GPUArbiter creates empty (no lease => never defers).
DEFAULT_LEASE_DB = ROOT / ".openclaw" / "self_knowledge" / "gpu_leases.sqlite"
DEFAULT_STATE_DB = ROOT / ".openclaw" / "self_knowledge" / "crawl_state.sqlite"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Run one arbiter-aware scheduled self-knowledge crawl pass."
    )
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--lease-db-path", default=str(DEFAULT_LEASE_DB))
    ap.add_argument("--state-db-path", default=str(DEFAULT_STATE_DB))
    ap.add_argument("--max-files", type=int, default=None)
    args = ap.parse_args(argv)

    result = run_scheduled_crawl(
        args.root,
        lease_db_path=args.lease_db_path,
        state_db_path=args.state_db_path,
        max_files=args.max_files,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
