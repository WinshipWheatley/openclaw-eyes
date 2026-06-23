#!/usr/bin/env python3
"""Export the Chief agent fleet-health read-model.

Sources: agent_presence.json, sync_health.json, git log.
Pure read-only — no agent activation, no repair, no sends.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chief_agent_fleet_health import export_chief_agent_fleet_health, DEFAULT_EXPORT_ROOT


def main() -> int:
    summary = export_chief_agent_fleet_health(
        repo_root=ROOT,
        export_root=DEFAULT_EXPORT_ROOT,
    )
    print(f"wrote {summary['json_path']} :: {summary['grounded_fact_count']} grounded facts")
    print(f"  agent_health_available: {summary['agent_health_available']}")
    print(f"  sync_health_available:  {summary['sync_health_available']}")
    print(f"  git_milestones_available: {summary['git_milestones_available']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
