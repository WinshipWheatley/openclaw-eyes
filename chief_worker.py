import time
from pathlib import Path

INPUT_LOG = Path("/mnt/c/OpenClaw/logs/chief_input.log")
QUEUE_LOG = Path("/mnt/c/OpenClaw/logs/chief_queue.log")

seen = set()

if QUEUE_LOG.exists():
    with QUEUE_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            seen.add(line.rstrip("\n"))

print("[chief_worker] starting...", flush=True)

_heartbeat_count = 0

while True:
    _heartbeat_count += 1
    if _heartbeat_count % 60 == 0:
        print(f"[chief_worker] heartbeat — loop #{_heartbeat_count}", flush=True)
    if INPUT_LOG.exists():
        with INPUT_LOG.open("r", encoding="utf-8") as f:
            for line in f:
                clean = line.rstrip("\n")
                if clean and clean not in seen:
                    with QUEUE_LOG.open("a", encoding="utf-8") as q:
                        q.write(clean + "\n")
                    print(f"Queued: {clean}")
                    seen.add(clean)
    time.sleep(2)
