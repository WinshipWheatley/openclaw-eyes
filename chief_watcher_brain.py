import csv
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

BILLING_ROOT = Path("/mnt/c/OpenClaw/billing")
BILLING_TRACKER_CSV = BILLING_ROOT / "tracker" / "invoice_tracker.csv"
ALBUM_STATE_CSV = Path("/mnt/c/OpenClaw/state/state.csv")

STATE_FILE = Path("/mnt/c/OpenClaw/logs/chief_watcher_state.json")
PENDING_APPROVAL_FILE = Path("/mnt/c/OpenClaw/logs/approval_pending.json")
CHECK_EVERY_SECONDS = 900  # 15 minutes
PENDING_REPLAY_AFTER_SECONDS = 120
PENDING_REPLAY_COOLDOWN_SECONDS = 600
PENDING_REPLAY_MAX_PER_ID = 3


def log_replay_event(reason_code: str, pending_id: str, **details):
    parts = [f"reason={reason_code}", f"id={pending_id or 'unknown'}"]
    for key, value in details.items():
        parts.append(f"{key}={value}")
    print("[approval_replay] " + " ".join(parts), flush=True)


def send_reply(text: str):
    subprocess.run(
        ["python3", str(Path.home() / "chief_sender.py"), text],
        check=False,
    )


def load_state():
    if STATE_FILE.exists():
        try:
            with STATE_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"sent_alert_keys": [], "approval_replay": {}}


def read_json(path: Path):
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def parse_pending_time(text: str):
    text = (text or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def read_csv_rows(path: Path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def parse_date(text: str):
    text = (text or "").strip()
    if not text:
        return None

    for fmt in ("%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def clean_money(text: str):
    try:
        return float((text or "0").strip())
    except Exception:
        return 0.0


def build_key(prefix, parts):
    return prefix + "|" + "|".join((p or "").strip() for p in parts)


def normalize_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def is_blankish(text: str) -> bool:
    t = normalize_text(text)
    return t in {"", "none", "n/a", "na", "unknown", "unclear", "i dont know", "i don't know"}


def find_billing_alerts(rows):
    today = datetime.now().date()
    alerts = []

    for row in rows:
        invoice_number = row.get("invoice_number", "").strip()
        if not invoice_number:
            continue

        payment_status = row.get("payment_status", "").strip().lower()
        next_follow_up_date = parse_date(row.get("next_follow_up_date", ""))
        balance_amount = clean_money(row.get("balance_amount", "0"))
        invoice_status = row.get("invoice_status", "").strip().lower()

        if invoice_status not in {"sent", "drafted"}:
            continue

        if payment_status in {"paid", "closed"} or balance_amount <= 0:
            continue

        if next_follow_up_date and next_follow_up_date <= today:
            alerts.append({
                "type": "billing_followup_due",
                "key": build_key("billing", [
                    invoice_number,
                    row.get("next_follow_up_date", ""),
                    row.get("balance_amount", ""),
                    payment_status,
                ]),
                "invoice_number": invoice_number,
                "client_name": row.get("client_name", "").strip(),
                "balance_amount": f"{balance_amount:.2f}",
                "next_follow_up_date": row.get("next_follow_up_date", "").strip(),
                "payment_status": payment_status or "unpaid",
            })

    return alerts


def summarize_album_row(row):
    item_name = row.get("item_name", "").strip()
    stage = row.get("derived_stage", "").strip()
    bottleneck = row.get("derived_bottleneck", "").strip()
    next_action = row.get("next_action", "").strip()
    backup_status = row.get("backup_status", "").strip()
    next_specialist = row.get("next_specialist", "").strip()
    version_state = row.get("version_state", "").strip()

    alerts = []

    if not is_blankish(bottleneck):
        alerts.append({
            "type": "album_blocker",
            "priority": 1,
            "key": build_key("album_blocker", [item_name, bottleneck, next_action]),
            "item_name": item_name,
            "stage": stage or "unknown",
            "bottleneck": bottleneck,
            "next_action": next_action or "missing",
        })

    if is_blankish(next_action):
        alerts.append({
            "type": "album_next_action_missing",
            "priority": 2,
            "key": build_key("album_next_missing", [item_name, stage, bottleneck]),
            "item_name": item_name,
            "stage": stage or "unknown",
            "bottleneck": bottleneck or "not set",
        })

    if normalize_text(backup_status) in {"needs backup", "not backed up", "backup needed"}:
        alerts.append({
            "type": "album_backup_needed",
            "priority": 3,
            "key": build_key("album_backup", [item_name, backup_status]),
            "item_name": item_name,
            "backup_status": backup_status,
        })

    if not is_blankish(version_state) and normalize_text(version_state) not in {"yes", "locked", "main version selected"}:
        alerts.append({
            "type": "album_version_unsettled",
            "priority": 4,
            "key": build_key("album_version", [item_name, version_state]),
            "item_name": item_name,
            "version_state": version_state,
            "next_specialist": next_specialist or "not set",
        })

    return alerts


def find_album_alerts(rows):
    per_song = {}

    for row in rows:
        item_name = row.get("item_name", "").strip()
        if not item_name:
            continue

        song_alerts = summarize_album_row(row)
        if song_alerts:
            per_song[item_name] = sorted(song_alerts, key=lambda a: a["priority"])[0]

    return sorted(per_song.values(), key=lambda a: (a["priority"], a["item_name"]))[:5]


def format_alert_message(alerts):
    if not alerts:
        return None

    lines = ["Watcher alert:"]
    for alert in alerts:
        if alert["type"] == "billing_followup_due":
            lines.append(
                f"Billing follow-up due: {alert['invoice_number']} | "
                f"{alert['client_name']} | "
                f"balance ${alert['balance_amount']} | "
                f"scheduled {alert['next_follow_up_date']} | "
                f"status {alert['payment_status']}."
            )
        elif alert["type"] == "album_blocker":
            lines.append(
                f"Album blocker: {alert['item_name']} | "
                f"stage {alert['stage']} | "
                f"blocker {alert['bottleneck']} | "
                f"next action {alert['next_action']}."
            )
        elif alert["type"] == "album_next_action_missing":
            lines.append(
                f"Album next action missing: {alert['item_name']} | "
                f"stage {alert['stage']} | "
                f"bottleneck {alert['bottleneck']}."
            )
        elif alert["type"] == "album_backup_needed":
            lines.append(
                f"Album backup needed: {alert['item_name']} | "
                f"status {alert['backup_status']}."
            )
        elif alert["type"] == "album_version_unsettled":
            lines.append(
                f"Album version unsettled: {alert['item_name']} | "
                f"version state {alert['version_state']} | "
                f"next specialist {alert['next_specialist']}."
            )
    return "\n".join(lines)


def evaluate_pending_replay(pending: dict, replay_state: dict, now_ts: int | None = None):
    pending_id = str(pending.get("id") or "unknown").strip() or "unknown"

    if pending.get("status") != "pending":
        return {
            "pending_id": pending_id,
            "pending_age": 0,
            "reason_code": "no_pending",
            "should_replay": False,
            "cooldown_remaining": 0,
            "replay_count": int(replay_state.get("count", 0) or 0),
        }

    pending_dt = parse_pending_time(pending.get("requested_at", ""))
    pending_age = 0
    if pending_dt is not None:
        pending_age = max(0, int((datetime.now() - pending_dt).total_seconds()))

    replay_count = int(replay_state.get("count", 0) or 0)
    last_replay = int(replay_state.get("last_replay", 0) or 0)
    now_ts = int(time.time()) if now_ts is None else int(now_ts)
    elapsed_since_replay = now_ts - last_replay
    cooldown_remaining = max(0, PENDING_REPLAY_COOLDOWN_SECONDS - elapsed_since_replay)

    if pending_age < PENDING_REPLAY_AFTER_SECONDS:
        reason_code = "pending_too_young"
    elif replay_count >= PENDING_REPLAY_MAX_PER_ID:
        reason_code = "replay_cap_reached"
    elif elapsed_since_replay < PENDING_REPLAY_COOLDOWN_SECONDS:
        reason_code = "cooldown_active"
    else:
        reason_code = "replay_ready"

    return {
        "pending_id": pending_id,
        "pending_age": pending_age,
        "reason_code": reason_code,
        "should_replay": reason_code == "replay_ready",
        "cooldown_remaining": cooldown_remaining if reason_code == "cooldown_active" else 0,
        "replay_count": replay_count,
    }


def check_once(state):
    state.setdefault("approval_replay", {})

    # Keep approval flow alive without auto-deciding anything:
    # if a pending request sits for a while, re-send it on bounded cooldown.
    pending = read_json(PENDING_APPROVAL_FILE)
    if pending.get("status") == "pending":
        pending_id = (pending.get("id") or "unknown").strip() or "unknown"
        replay_state = state["approval_replay"].get(
            pending_id,
            {"last_replay": 0, "count": 0},
        )
        now_ts = int(time.time())
        replay_decision = evaluate_pending_replay(
            pending,
            replay_state,
            now_ts=now_ts,
        )
        log_replay_event(
            replay_decision["reason_code"],
            replay_decision["pending_id"],
            age_seconds=replay_decision["pending_age"],
            replay_count=replay_decision["replay_count"],
            cooldown_remaining=replay_decision["cooldown_remaining"],
        )
        if replay_decision["should_replay"]:
            result = subprocess.run(
                ["python3", str(Path.home() / "chief_approval_brain.py"), "--resend-pending"],
                capture_output=True,
                text=True,
                check=False,
            )
            replay_state["last_replay"] = now_ts
            if result.returncode == 0:
                replay_state["count"] = int(replay_state.get("count", 0)) + 1
                log_replay_event(
                    "resend_succeeded",
                    pending_id,
                    replay_count=replay_state["count"],
                )
            else:
                log_replay_event(
                    "resend_failed",
                    pending_id,
                    returncode=result.returncode,
                )
            state["approval_replay"][pending_id] = replay_state

    # Prune replay memory for resolved approval IDs.
    if pending.get("status") != "pending":
        state["approval_replay"] = {}

    billing_rows = read_csv_rows(BILLING_TRACKER_CSV)
    album_rows = read_csv_rows(ALBUM_STATE_CSV)

    alerts = []
    alerts.extend(find_billing_alerts(billing_rows))
    alerts.extend(find_album_alerts(album_rows))

    if not alerts:
        return state

    sent_keys = set(state.get("sent_alert_keys", []))
    unsent_alerts = []

    for alert in alerts:
        key = alert["key"]
        if key not in sent_keys:
            unsent_alerts.append(alert)
            sent_keys.add(key)

    if unsent_alerts:
        msg = format_alert_message(unsent_alerts)
        if msg:
            send_reply(msg)

    state["sent_alert_keys"] = sorted(sent_keys)
    return state


def main():
    print("Chief watcher brain online.")
    state = load_state()
    state = check_once(state)
    save_state(state)
    while True:
        time.sleep(CHECK_EVERY_SECONDS)
        state = load_state()
        state = check_once(state)
        save_state(state)


if __name__ == "__main__":
    main()
