import time
import subprocess
from pathlib import Path

QUEUE_LOG = Path("/mnt/c/OpenClaw/logs/chief_queue.log")
REPLIED_LOG = Path("/mnt/c/OpenClaw/logs/chief_replied.log")

seen = set()

if REPLIED_LOG.exists():
    with REPLIED_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            seen.add(line.rstrip("\n"))

print("Chief reply worker online.")

while True:
    if QUEUE_LOG.exists():
        with QUEUE_LOG.open("r", encoding="utf-8") as f:
            for line in f:
                clean = line.rstrip("\n")
                if not clean or clean in seen:
                    continue

                reply = f"Chief received your message: {clean}"

                subprocess.run(
                    ["python", str(Path.home() / "chief_sender.py"), reply],
                    check=False,
                )

                with REPLIED_LOG.open("a", encoding="utf-8") as r:
                    r.write(clean + "\n")

                print(f"Replied to: {clean}")
                seen.add(clean)

    time.sleep(2)
