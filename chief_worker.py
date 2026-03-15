import time
from pathlib import Path

INPUT_LOG = Path("/mnt/c/OpenClaw/logs/chief_input.log")
QUEUE_LOG = Path("/mnt/c/OpenClaw/logs/chief_queue.log")

seen = set()

if QUEUE_LOG.exists():
    with QUEUE_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            seen.add(line.rstrip("\n"))

print("Chief worker online.")

while True:
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
