import csv
import time
from pathlib import Path

QUEUE_LOG = Path("/mnt/c/OpenClaw/logs/chief_queue.log")
STATE_CSV = Path("/mnt/c/OpenClaw/state/state.csv")

seen = set()

if STATE_CSV.exists():
    with STATE_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = row.get("raw_input", "")
            if raw:
                seen.add(raw)

print("Chief state worker online.")

while True:
    if QUEUE_LOG.exists():
        with QUEUE_LOG.open("r", encoding="utf-8") as f:
            for line in f:
                clean = line.rstrip("\n")
                if not clean or clean in seen:
                    continue

                if "STATE|" not in clean:
                    continue

                payload = clean.split("STATE|", 1)[1]
                parts = [p.strip() for p in payload.split("|")]

                if len(parts) < 6:
                    print(f"Skipped malformed STATE line: {clean}")
                    seen.add(clean)
                    continue

                item_name = parts[0]
                status = parts[1]
                last_action = parts[2]
                next_action = parts[3]
                blockers = parts[4]
                notes = parts[5] if len(parts) > 5 else ""

                rows = []
                found = False

                if STATE_CSV.exists():
                    with STATE_CSV.open("r", encoding="utf-8", newline="") as sf:
                        reader = csv.DictReader(sf)
                        for row in reader:
                            if row["item_name"] == item_name:
                                row["status"] = status
                                row["last_action"] = last_action
                                row["next_action"] = next_action
                                row["blockers"] = blockers
                                row["updated_at"] = time.strftime("%Y-%m-%d %H:%M")
                                row["notes"] = notes
                                row["raw_input"] = clean
                                found = True
                            rows.append(row)

                if not found:
                    rows.append({
                        "item_name": item_name,
                        "status": status,
                        "last_action": last_action,
                        "next_action": next_action,
                        "blockers": blockers,
                        "updated_at": time.strftime("%Y-%m-%d %H:%M"),
                        "notes": notes,
                        "raw_input": clean,
                    })

                with STATE_CSV.open("w", encoding="utf-8", newline="") as sf:
                    fieldnames = [
                        "item_name",
                        "status",
                        "last_action",
                        "next_action",
                        "blockers",
                        "updated_at",
                        "notes",
                        "raw_input",
                    ]
                    writer = csv.DictWriter(sf, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)

                print(f"State updated: {item_name}")
                seen.add(clean)

    time.sleep(2)
