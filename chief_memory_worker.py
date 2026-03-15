import time
from pathlib import Path

QUEUE_LOG = Path("/mnt/c/OpenClaw/logs/chief_queue.log")
DECISION_LOG = Path("/mnt/c/OpenClaw/memory/decision_log.md")

seen = set()

if DECISION_LOG.exists():
    with DECISION_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("- Inbox: "):
                seen.add(line.replace("- Inbox: ", "").rstrip("\n"))

print("Chief memory worker online.")

while True:
    if QUEUE_LOG.exists():
        with QUEUE_LOG.open("r", encoding="utf-8") as f:
            for line in f:
                clean = line.rstrip("\n")
                if clean and clean not in seen:
                    with DECISION_LOG.open("a", encoding="utf-8") as d:
                        d.write(f"- Inbox: {clean}\n")
                    print(f"Logged to memory: {clean}")
                    seen.add(clean)
    time.sleep(2)
