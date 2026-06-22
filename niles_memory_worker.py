"""niles_memory_worker.py — Niles persistent-memory daemon (creative/music lane).

Mirrors chief_memory_worker.py: tails a per-agent queue log and appends new,
de-duplicated lines to a durable memory log. This is the same proven mechanism
that gives Chief its persistent "deep memory" — scoped here to Niles.

Niles's memory scope is already contracted in agent_memory_scope_contract.py
(actor_id="niles"); this worker is the active accrual side of it.

Constraints (Niles is trust-tier-1): this worker only READS a local queue and
WRITES a local memory log. No model calls, no network, no sends, no DAW/hardware,
no secrets — pure deterministic storage/recall. Safe to keep alive.
"""

import time
from pathlib import Path

QUEUE_LOG = Path("/mnt/c/OpenClaw/logs/niles_queue.log")
MEMORY_LOG = Path("/mnt/c/OpenClaw/memory/niles_memory_log.md")

seen: set[str] = set()

# Load already-recorded memory so restarts don't duplicate (same dedup as Chief).
if MEMORY_LOG.exists():
    with MEMORY_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("- Intake: "):
                seen.add(line.replace("- Intake: ", "").rstrip("\n"))

print("[niles_memory_worker] starting...", flush=True)

_heartbeat_count = 0

while True:
    _heartbeat_count += 1
    if _heartbeat_count % 60 == 0:
        print(f"[niles_memory_worker] heartbeat — loop #{_heartbeat_count}", flush=True)
    if QUEUE_LOG.exists():
        with QUEUE_LOG.open("r", encoding="utf-8") as f:
            for line in f:
                clean = line.rstrip("\n")
                if clean and clean not in seen:
                    MEMORY_LOG.parent.mkdir(parents=True, exist_ok=True)
                    with MEMORY_LOG.open("a", encoding="utf-8") as d:
                        d.write(f"- Intake: {clean}\n")
                    print(f"Logged to niles memory: {clean}", flush=True)
                    seen.add(clean)
    time.sleep(2)
