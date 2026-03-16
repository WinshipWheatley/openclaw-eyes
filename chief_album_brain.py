import json
import time
import subprocess
import csv
import shutil
import re
from pathlib import Path
from datetime import datetime

from chief_session_manager import (
    get_workflow_state,
    set_workflow_state,
    mark_complete,
)

QUEUE_LOG = Path("/mnt/c/OpenClaw/logs/chief_queue.log")
REPLIED_LOG = Path("/mnt/c/OpenClaw/logs/chief_album_replied.log")
STATE_CSV = Path("/mnt/c/OpenClaw/state/state.csv")
STATE_PREV_CSV = Path("/mnt/c/OpenClaw/state/state_prev.csv")
WORK_LOG_CSV = Path("/mnt/c/OpenClaw/logs/album_work_log.csv")

LANES = [
    ("writing_arrangement", "Writing / arrangement: start with one of done, needs work, needs review, needs re-record, not applicable, or unclear. Then add a short note if needed."),
    ("lyrics", "Lyrics: start with one of done, needs work, needs review, needs re-record, not applicable, or unclear. Then add a short note if needed."),
    ("drums", "Drums: start with one of done, needs work, needs review, needs re-record, not applicable, or unclear. Then add a short note if needed."),
    ("bass", "Bass: start with one of done, needs work, needs review, needs re-record, not applicable, or unclear. Then add a short note if needed."),
    ("guitars", "Guitars: start with one of done, needs work, needs review, needs re-record, not applicable, or unclear. Then add a short note if needed."),
    ("keys", "Keys: start with one of done, needs work, needs review, needs re-record, not applicable, or unclear. Then add a short note if needed."),
    ("lead_vocals", "Lead vocals: start with one of done, needs work, needs review, needs re-record, not applicable, or unclear. Then add a short note if needed."),
    ("backing_vocals", "Backing vocals / doubles / harmonies: start with one of done, needs work, needs review, needs re-record, not applicable, or unclear. Then add a short note if needed."),
    ("editing_cleanup", "Editing / cleanup: start with one of done, needs work, needs review, needs re-record, not applicable, or unclear. Then add a short note if needed."),
    ("mix_prep", "Mix prep: start with one of done, needs work, needs review, needs re-record, not applicable, or unclear. Then add a short note if needed."),
    ("mixing", "Mixing: start with one of done, needs work, needs review, needs re-record, not applicable, or unclear. Then add a short note if needed."),
]

TRACKER_FIELDS = [
    "item_name",
    "main_version_name",
    "main_version_path",
    "version_state",
    "version_choice_status",
    "decision_locked",
    "review_gate",
    "backup_status",
    "donor_versions",
    "writing_arrangement",
    "lyrics",
    "drums",
    "bass",
    "guitars",
    "keys",
    "lead_vocals",
    "backing_vocals",
    "editing_cleanup",
    "mix_prep",
    "mixing",
    "song_readiness_percent",
    "song_ship_confidence_percent",
    "derived_stage",
    "derived_bottleneck",
    "primary_blocker",
    "secondary_blocker",
    "highest_leverage_next_step",
    "next_action",
    "next_specialist",
    "notes",
    "updated_at",
    "raw_input",
]



_ALBUM_DEFAULT = {
    "active": False,
    "phase": "idle",
    "step": 0,
    "answers": {},
    "version_count": 0,
    "current_version_index": 0,
    "session_started_at": None,
    "test_mode": False,
}


def load_session() -> dict:
    state = get_workflow_state()
    if not state:
        return json.loads(json.dumps(_ALBUM_DEFAULT))
    return state


def save_session(session: dict) -> None:
    set_workflow_state(session)


def send_reply(text: str):
    subprocess.run(
        ["python3", str(Path.home() / "chief_sender.py"), text],
        check=False,
    )


def normalize_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def is_blankish(text: str) -> bool:
    t = normalize_text(text)
    return t in {"", "none", "n/a", "na", "unknown", "unclear", "i dont know", "i don't know", "none listed"}


def sanitize_name(text: str) -> str:
    cleaned = "".join(ch for ch in text if ch.isalnum() or ch in (" ", "_", "-")).strip()
    cleaned = "_".join(cleaned.split())
    return cleaned or "untitled"


def today_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def suggested_main_name(song_name: str) -> str:
    return f"{sanitize_name(song_name)}__main__{today_stamp()}"


def suggested_candidate_name(song_name: str, letter: str) -> str:
    return f"{sanitize_name(song_name)}__candidate_{letter}__{today_stamp()}"


def snapshot_state_csv():
    if STATE_CSV.exists():
        shutil.copy2(STATE_CSV, STATE_PREV_CSV)


def ensure_work_log_header():
    if not WORK_LOG_CSV.exists():
        with WORK_LOG_CSV.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp",
                    "item_name",
                    "main_version_name",
                    "main_version_path",
                    "version_state",
                    "version_choice_status",
                    "decision_locked",
                    "review_gate",
                    "song_readiness_percent",
                    "song_ship_confidence_percent",
                    "derived_stage",
                    "derived_bottleneck",
                    "primary_blocker",
                    "secondary_blocker",
                    "highest_leverage_next_step",
                    "next_action",
                    "next_specialist",
                    "backup_status",
                    "notes",
                    "duration_minutes",
                ],
            )
            writer.writeheader()


def yesish(text: str) -> bool:
    t = normalize_text(text)
    yes_tokens = {
        "yes", "y", "yeah", "yep", "yup", "sure", "settled", "locked",
        "pretty much", "basically yes", "closest thing to yes", "more or less yes"
    }
    return t in yes_tokens or t.startswith("yes ") or t.startswith("yeah ") or t.startswith("yep ")


def noish(text: str) -> bool:
    t = normalize_text(text)
    no_tokens = {
        "no", "n", "nope", "not yet", "not really", "still deciding", "not settled", "none yet"
    }
    return t in no_tokens or t.startswith("no ") or t.startswith("not yet")


def unsureish(text: str) -> bool:
    t = normalize_text(text)
    unsure_tokens = {
        "unsure", "not sure", "unclear", "review first", "skip", "for now skip",
        "kind of", "hard to say", "i dont know", "i don't know", "maybe", "provisional"
    }
    return t in unsure_tokens or "not sure" in t or "review first" in t or t.startswith("skip")


def parse_yes_no_unsure(text: str):
    if yesish(text):
        return "yes"
    if noish(text):
        return "no"
    if unsureish(text):
        return "unsure"
    return None


def parse_version_role(text: str):
    t = normalize_text(text).replace("-", " ")
    mapping = {
        "main": "main",
        "donor": "donor",
        "contender": "contender",
        "archive": "archive",
    }
    if t in mapping:
        return mapping[t]
    return None


def parse_backup_status(text: str):
    t = normalize_text(text)
    if t in {"backed up", "backed-up", "safe", "done", "complete"}:
        return "Backed up"
    if t in {"needs backup", "backup needed", "not backed up", "needs back up"}:
        return "Needs backup"
    if t in {"unsure", "not sure", "unknown"}:
        return "Unsure"
    return text.strip()


def looks_minor(note: str) -> bool:
    n = normalize_text(note)
    minor_flags = [
        "small", "slight", "little", "minor", "touch", "tighten", "could be shorter",
        "could use a little", "strong overall", "mostly strong", "overall strong",
        "overall good", "probably fine", "maybe", "might", "close"
    ]
    return any(flag in n for flag in minor_flags)


def split_status_and_note(text: str):
    raw = text.strip()
    lower = normalize_text(raw)
    compact = lower.replace("-", " ")

    alias_map = {
        "done": "done",
        "good": "done",
        "solid": "done",
        "keeper": "done",
        "locked": "done",
        "ship it": "done",
        "ship": "done",
        "needs work": "needs work",
        "work": "needs work",
        "needs fixing": "needs work",
        "not done": "needs work",
        "close but not done": "needs work",
        "needs review": "needs review",
        "review": "needs review",
        "review first": "needs review",
        "listen again": "needs review",
        "check it": "needs review",
        "needs re record": "needs re-record",
        "needs rerecord": "needs re-record",
        "re record": "needs re-record",
        "rerecord": "needs re-record",
        "redo": "needs re-record",
        "redo it": "needs re-record",
        "another take": "needs re-record",
        "not applicable": "not applicable",
        "n a": "not applicable",
        "na": "not applicable",
        "n/a": "not applicable",
        "none": "not applicable",
        "unclear": "unclear",
        "unsure": "unclear",
        "not sure": "unclear",
        "skip": "unclear",
    }

    if compact in alias_map:
        return alias_map[compact], ""

    canonical_prefixes = [
        ("needs re record", "needs re-record"),
        ("needs rerecord", "needs re-record"),
        ("needs re-record", "needs re-record"),
        ("re record", "needs re-record"),
        ("redo", "needs re-record"),
        ("needs review", "needs review"),
        ("review", "needs review"),
        ("review first", "needs review"),
        ("needs work", "needs work"),
        ("done", "done"),
        ("good", "done"),
        ("solid", "done"),
        ("keeper", "done"),
        ("locked", "done"),
        ("not applicable", "not applicable"),
        ("n/a", "not applicable"),
        ("na", "not applicable"),
        ("unclear", "unclear"),
        ("unsure", "unclear"),
        ("not sure", "unclear"),
        ("skip", "unclear"),
    ]

    for prefix, canonical in canonical_prefixes:
        if compact == prefix:
            return canonical, ""
        if compact.startswith(prefix + " "):
            original_words = raw.split()
            prefix_word_count = len(prefix.split())
            note = " ".join(original_words[prefix_word_count:]).strip(" -:;,")
            return canonical, note

    return None, raw


def parse_confidence(text: str, mode: str):
    t = normalize_text(text)

    num_match = re.search(r"\b(\d{1,3})\b", t)
    if num_match:
        num = int(num_match.group(1))
        num = max(0, min(100, num))
        return num

    mapping = [
        ({"ship it", "ship", "done done", "locked", "final", "100"}, 98 if mode == "ship" else 96),
        ({"very close", "almost there", "pretty much there", "super close"}, 88),
        ({"pretty good", "pretty good about it", "strong overall", "mostly there", "close"}, 78),
        ({"decent", "solid direction", "good start", "halfway"}, 60),
        ({"rough", "early", "not there", "far off"}, 30),
        ({"no idea", "unclear", "unsure", "not sure"}, 15),
    ]

    for phrases, value in mapping:
        if any(p in t for p in phrases):
            return value

    if mode == "ship":
        if any(p in t for p in ["not ship", "not final", "wouldnt ship", "wouldn't ship"]):
            return 20
    return None


def flatten_notes(answer_dict: dict):
    parts = []
    for key, value in answer_dict.items():
        if key.endswith("_note") and str(value).strip():
            parts.append(f"{key.replace('_note', '')}: {str(value).strip()}")
    if answer_dict.get("main_version_path", "").strip():
        parts.append(f"main_version_path: {answer_dict['main_version_path'].strip()}")
    if answer_dict.get("backup_status", "").strip():
        parts.append(f"backup_status: {answer_dict['backup_status'].strip()}")
    return " | ".join(parts)

def derive_decision_fields(a: dict):
    version_state = normalize_text(a.get("version_state", ""))
    backup_status = normalize_text(a.get("backup_status", ""))
    lane_order = [
        "writing_arrangement",
        "lyrics",
        "drums",
        "bass",
        "guitars",
        "keys",
        "lead_vocals",
        "backing_vocals",
        "editing_cleanup",
        "mix_prep",
        "mixing",
    ]

    lane_to_stage = {
        "writing_arrangement": "writing",
        "lyrics": "writing",
        "drums": "recording",
        "bass": "recording",
        "guitars": "recording",
        "keys": "recording",
        "lead_vocals": "recording",
        "backing_vocals": "recording",
        "editing_cleanup": "editing",
        "mix_prep": "mix prep",
        "mixing": "mixing",
    }

    lane_to_specialist = {
        "writing_arrangement": "producer",
        "lyrics": "producer",
        "drums": "arrangement / producer",
        "bass": "arrangement / producer",
        "guitars": "arrangement / producer",
        "keys": "arrangement / producer",
        "lead_vocals": "producer / vocal tracking",
        "backing_vocals": "producer / vocal tracking",
        "editing_cleanup": "editing",
        "mix_prep": "technical metering coach",
        "mixing": "mix brain",
    }

    version_choice_status = "locked" if version_state == "yes" else ("unsettled" if version_state in {"no", "unsure"} else "unknown")
    decision_locked = "yes" if version_choice_status == "locked" else "no"

    primary_blocker = "none"
    secondary_blocker = "none"
    derived_stage = "done"
    derived_bottleneck = "none"
    next_specialist = "none"
    highest_leverage_next_step = "song appears ready for the next higher-level decision pass"
    review_gate = "no"

    if version_choice_status != "locked":
        primary_blocker = "version_choice"
        derived_stage = "review"
        derived_bottleneck = "version_choice"
        next_specialist = "producer"
        highest_leverage_next_step = "settle the main version and donor roles before deeper work"
        review_gate = "yes"

        if normalize_text(a.get("lead_vocals", "")) == "needs re-record":
            secondary_blocker = "lead_vocals"
        elif normalize_text(a.get("writing_arrangement", "")) in {"needs work", "needs review", "unclear"}:
            secondary_blocker = "writing_arrangement"
        else:
            for lane in lane_order:
                if normalize_text(a.get(lane, "")) in {"needs re-record", "needs review", "needs work", "unclear"}:
                    secondary_blocker = lane
                    break

        return {
            "version_choice_status": version_choice_status,
            "decision_locked": decision_locked,
            "review_gate": review_gate,
            "derived_stage": derived_stage,
            "derived_bottleneck": derived_bottleneck,
            "primary_blocker": primary_blocker,
            "secondary_blocker": secondary_blocker,
            "highest_leverage_next_step": highest_leverage_next_step,
            "next_specialist": next_specialist,
        }

    backup_gate = backup_status in {"needs backup", "backup needed", "not backed up", "needs back up"}

    lane_priority = []
    for lane in lane_order:
        status = normalize_text(a.get(lane, ""))
        note = a.get(f"{lane}_note", "")

        if status == "needs re-record":
            score = 4
        elif status == "unclear":
            score = 3
        elif status == "needs review":
            score = 2
        elif status == "needs work":
            score = 1
        else:
            continue

        if lane in {"writing_arrangement", "lyrics"} and status == "needs work" and looks_minor(note):
            score = 0

        lane_priority.append((score, lane, note))

    lead_status = normalize_text(a.get("lead_vocals", ""))

    chosen_lane = None
    chosen_score = -1

    if lead_status == "needs re-record":
        chosen_lane = "lead_vocals"
        chosen_score = 4
    else:
        for score, lane, _note in lane_priority:
            if score > chosen_score:
                chosen_lane = lane
                chosen_score = score

    if chosen_lane is None:
        if backup_gate:
            primary_blocker = "backup"
            derived_stage = "ops"
            derived_bottleneck = "backup"
            next_specialist = "producer"
            highest_leverage_next_step = "make a fresh backup before deeper changes"
        return {
            "version_choice_status": version_choice_status,
            "decision_locked": decision_locked,
            "review_gate": review_gate,
            "derived_stage": derived_stage,
            "derived_bottleneck": derived_bottleneck,
            "primary_blocker": primary_blocker,
            "secondary_blocker": secondary_blocker,
            "highest_leverage_next_step": highest_leverage_next_step,
            "next_specialist": next_specialist,
        }

    primary_blocker = chosen_lane
    derived_stage = lane_to_stage[chosen_lane]
    derived_bottleneck = chosen_lane
    next_specialist = lane_to_specialist[chosen_lane]

    next_map = {
        "writing_arrangement": "review and tighten the song structure and arrangement",
        "lyrics": "review and tighten the lyric direction",
        "drums": "review and finish the drum path",
        "bass": "review and finish the bass path",
        "guitars": "review and finish the guitar path",
        "keys": "review and finish the key parts",
        "lead_vocals": "re-record or review lead vocals",
        "backing_vocals": "re-record or review backing vocals",
        "editing_cleanup": "finish editing and cleanup before mix decisions",
        "mix_prep": "prepare the session for serious mixing",
        "mixing": "start focused mix decisions from the prepared session",
    }
    highest_leverage_next_step = next_map[chosen_lane]

    if chosen_lane == "mix_prep":
        notes = flatten_notes(a).lower()
        if any(x in notes for x in ["ballistic", "vu", "rms", "peak", "meter"]):
            highest_leverage_next_step = "reset ballistics and establish objective mix center"

    if normalize_text(a.get(chosen_lane, "")) in {"unclear", "needs review"}:
        review_gate = "yes"

    for score, lane, _note in sorted(lane_priority, key=lambda x: x[0], reverse=True):
        if lane != primary_blocker and score > 0:
            secondary_blocker = lane
            break

    if backup_gate and secondary_blocker == "none":
        secondary_blocker = "backup"

    return {
        "version_choice_status": version_choice_status,
        "decision_locked": decision_locked,
        "review_gate": review_gate,
        "derived_stage": derived_stage,
        "derived_bottleneck": derived_bottleneck,
        "primary_blocker": primary_blocker,
        "secondary_blocker": secondary_blocker,
        "highest_leverage_next_step": highest_leverage_next_step,
        "next_specialist": next_specialist,
    }


def derive_next_specialist(a: dict):
    return derive_decision_fields(a)["next_specialist"]


def derive_next_action(a: dict):
    return derive_decision_fields(a)["highest_leverage_next_step"]


def infer_overall_readiness(a: dict):
    explicit = a.get("song_readiness_percent")
    if explicit not in ("", None):
        try:
            return int(explicit)
        except Exception:
            pass

    score = 100
    penalties = {
        "needs re-record": 28,
        "unclear": 24,
        "needs review": 16,
        "needs work": 10,
    }

    for lane, _prompt in LANES:
        status = normalize_text(a.get(lane, ""))
        score -= penalties.get(status, 0)

    if normalize_text(a.get("version_state", "")) in {"no", "unsure"}:
        score = min(score, 45)

    if normalize_text(a.get("backup_status", "")) in {"needs backup", "backup needed", "not backed up"}:
        score = min(score, 80)

    return max(0, min(100, score))


def infer_ship_confidence(a: dict):
    explicit = a.get("song_ship_confidence_percent")
    if explicit not in ("", None):
        try:
            return int(explicit)
        except Exception:
            pass

    readiness = infer_overall_readiness(a)
    ship = readiness

    if normalize_text(a.get("version_state", "")) in {"no", "unsure"}:
        ship = min(ship, 20)

    if normalize_text(a.get("lead_vocals", "")) == "needs re-record":
        ship = min(ship, 35)

    if normalize_text(a.get("mixing", "")) in {"needs work", "needs review", "unclear"}:
        ship = min(ship, 70)

    if normalize_text(a.get("mix_prep", "")) in {"needs work", "needs review", "unclear"}:
        ship = min(ship, 75)

    return max(0, min(100, ship))


def log_work_entry(a: dict, session: dict) -> None:
    ensure_work_log_header()

    started = session.get("session_started_at")
    duration_minutes = ""
    if started:
        try:
            started_dt = datetime.fromisoformat(started)
            duration_minutes = int((datetime.now() - started_dt).total_seconds() // 60)
        except Exception:
            duration_minutes = ""

    decision = derive_decision_fields(a)

    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "item_name": a.get("item_name", "").strip(),
        "main_version_name": a.get("main_version_name", "").strip(),
        "main_version_path": a.get("main_version_path", "").strip(),
        "version_state": a.get("version_state", "").strip(),
        "version_choice_status": decision["version_choice_status"],
        "decision_locked": decision["decision_locked"],
        "review_gate": decision["review_gate"],
        "song_readiness_percent": infer_overall_readiness(a),
        "song_ship_confidence_percent": infer_ship_confidence(a),
        "derived_stage": decision["derived_stage"],
        "derived_bottleneck": decision["derived_bottleneck"],
        "primary_blocker": decision["primary_blocker"],
        "secondary_blocker": decision["secondary_blocker"],
        "highest_leverage_next_step": decision["highest_leverage_next_step"],
        "next_action": decision["highest_leverage_next_step"],
        "next_specialist": decision["next_specialist"],
        "backup_status": a.get("backup_status", "").strip(),
        "notes": flatten_notes(a),
        "duration_minutes": duration_minutes,
    }

    with WORK_LOG_CSV.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp",
                "item_name",
                "main_version_name",
                "main_version_path",
                "version_state",
                "version_choice_status",
                "decision_locked",
                "review_gate",
                "song_readiness_percent",
                "song_ship_confidence_percent",
                "derived_stage",
                "derived_bottleneck",
                "primary_blocker",
                "secondary_blocker",
                "highest_leverage_next_step",
                "next_action",
                "next_specialist",
                "backup_status",
                "notes",
                "duration_minutes",
            ],
        )
        writer.writerow(row)


def write_state_row(a: dict, session: dict = None):
    decision = derive_decision_fields(a)

    row = {
        "item_name": a.get("item_name", "").strip(),
        "main_version_name": a.get("main_version_name", "").strip(),
        "main_version_path": a.get("main_version_path", "").strip(),
        "version_state": a.get("version_state", "").strip(),
        "version_choice_status": decision["version_choice_status"],
        "decision_locked": decision["decision_locked"],
        "review_gate": decision["review_gate"],
        "backup_status": a.get("backup_status", "").strip(),
        "donor_versions": a.get("donor_versions", "").strip(),
        "writing_arrangement": a.get("writing_arrangement", "").strip(),
        "lyrics": a.get("lyrics", "").strip(),
        "drums": a.get("drums", "").strip(),
        "bass": a.get("bass", "").strip(),
        "guitars": a.get("guitars", "").strip(),
        "keys": a.get("keys", "").strip(),
        "lead_vocals": a.get("lead_vocals", "").strip(),
        "backing_vocals": a.get("backing_vocals", "").strip(),
        "editing_cleanup": a.get("editing_cleanup", "").strip(),
        "mix_prep": a.get("mix_prep", "").strip(),
        "mixing": a.get("mixing", "").strip(),
        "song_readiness_percent": infer_overall_readiness(a),
        "song_ship_confidence_percent": infer_ship_confidence(a),
        "derived_stage": decision["derived_stage"],
        "derived_bottleneck": decision["derived_bottleneck"],
        "primary_blocker": decision["primary_blocker"],
        "secondary_blocker": decision["secondary_blocker"],
        "highest_leverage_next_step": decision["highest_leverage_next_step"],
        "next_action": decision["highest_leverage_next_step"],
        "next_specialist": decision["next_specialist"],
        "notes": flatten_notes(a),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "raw_input": json.dumps(a, ensure_ascii=False),
    }

    rows = []
    found = False

    if STATE_CSV.exists():
        with STATE_CSV.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for existing in reader:
                if existing.get("item_name", "") == row["item_name"]:
                    rows.append(row)
                    found = True
                else:
                    clean_existing = {field: existing.get(field, "") for field in TRACKER_FIELDS}
                    rows.append(clean_existing)

    if not found:
        rows.append(row)

    snapshot_state_csv()

    with STATE_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    log_work_entry(a, session or {})


def finalize_song(a: dict, session: dict):
    decision = derive_decision_fields(a)
    readiness = infer_overall_readiness(a)
    ship_confidence = infer_ship_confidence(a)
    notes = flatten_notes(a)

    summary = (
        f"Logged song: {a.get('item_name', '')}\n"
        f"Main version: {a.get('main_version_name', '')}\n"
        f"Main version path: {a.get('main_version_path', '')}\n"
        f"Version state: {a.get('version_state', '')}\n"
        f"Version choice status: {decision['version_choice_status']}\n"
        f"Decision locked: {decision['decision_locked']}\n"
        f"Review gate: {decision['review_gate']}\n"
        f"Backup status: {a.get('backup_status', '')}\n"
        f"Donor versions: {a.get('donor_versions', '')}\n"
        f"Song readiness percent: {readiness}\n"
        f"Song ship confidence percent: {ship_confidence}\n"
        f"Derived stage: {decision['derived_stage']}\n"
        f"Derived bottleneck: {decision['derived_bottleneck']}\n"
        f"Primary blocker: {decision['primary_blocker']}\n"
        f"Secondary blocker: {decision['secondary_blocker']}\n"
        f"Highest leverage next step: {decision['highest_leverage_next_step']}\n"
        f"Next specialist: {decision['next_specialist']}\n"
        f"Notes: {notes}\n\n"
        f"Recommendation: {decision['highest_leverage_next_step']}."
    )
    send_reply(summary)
    write_state_row(a, session)


def reset_session() -> None:
    set_workflow_state(json.loads(json.dumps(_ALBUM_DEFAULT)))
    mark_complete()


def run_self_test():
    results = []

    yes_tests = {
        "yes": "yes",
        "Yeah": "yes",
        "pretty much": "yes",
        "not yet": "no",
        "Nope": "no",
        "review first": "unsure",
        "not sure": "unsure",
    }
    for text, expected in yes_tests.items():
        got = parse_yes_no_unsure(text)
        results.append(("YESNO", text, expected, got, expected == got))

    lane_tests = {
        "Done": "done",
        "solid": "done",
        "Needs review": "needs review",
        "review first": "needs review",
        "Needs re record": "needs re-record",
        "redo vocals": "needs re-record",
        "N/A": "not applicable",
        "skip": "unclear",
    }
    for text, expected in lane_tests.items():
        got, _note = split_status_and_note(text)
        results.append(("LANE", text, expected, got, expected == got))

    conf_tests = {
        "pretty good about it": 78,
        "ship it": 98,
        "not sure": 15,
        "72": 72,
    }
    for text, expected in conf_tests.items():
        got = parse_confidence(text, "readiness")
        results.append(("CONF", text, expected, got, expected == got))

    passed = sum(1 for r in results if r[4])
    total = len(results)

    lines = [f"TEST mode results: {passed}/{total} passed."]
    for kind, text, expected, got, ok in results:
        mark = "PASS" if ok else "FAIL"
        lines.append(f"{mark} | {kind} | '{text}' -> {got} | expected {expected}")

    lines.append("\nTEST mode complete.")
    send_reply("\n".join(lines))


if __name__ == "__main__":
    seen = set()
    if REPLIED_LOG.exists():
        with REPLIED_LOG.open("r", encoding="utf-8") as f:
            for line in f:
                seen.add(line.rstrip("\n"))

    print("Chief album brain online.")

    while True:
        session = load_session()
        if QUEUE_LOG.exists():
            with QUEUE_LOG.open("r", encoding="utf-8") as f:
                for line in f:
                    clean = line.rstrip("\n")
                    if not clean or clean in seen:
                        continue

                    message_text = clean.split("] ", 1)[1] if "] " in clean else clean
                    msg = message_text.strip()
                    upper = msg.upper()

                    if upper == "TEST":
                        run_self_test()
                        seen.add(clean)
                        with REPLIED_LOG.open("a", encoding="utf-8") as r:
                            r.write(clean + "\n")
                        continue

                    if upper == "ALBUM":
                        session["active"] = True
                        session["phase"] = "song_name"
                        session["step"] = 0
                        session["answers"] = {}
                        session["version_count"] = 0
                        session["current_version_index"] = 0
                        session["session_started_at"] = datetime.now().isoformat()
                        send_reply(
                            "Album review mode started. First settle the version. Then we do lane-by-lane diagnosis. "
                            "For each lane, start with one of: done, needs work, needs review, needs re-record, not applicable, or unclear. "
                            "You can also use normal phrases like review first, redo, solid, n/a, skip, or not sure. "
                            "The CSV row writes after the full song review is complete.\n\n"
                            "What song are we assessing?"
                        )
                        save_session(session)
                        seen.add(clean)
                        with REPLIED_LOG.open("a", encoding="utf-8") as r:
                            r.write(clean + "\n")
                        continue

                    if not session["active"]:
                        seen.add(clean)
                        with REPLIED_LOG.open("a", encoding="utf-8") as r:
                            r.write(clean + "\n")
                        continue

                    phase = session.get("phase", "idle")

                    if phase == "song_name":
                        session["answers"]["item_name"] = msg
                        session["phase"] = "version_gate"
                        send_reply("Have you settled on a main version to finish from? Reply yes, no, or unsure.")
                        save_session(session)

                    elif phase == "version_gate":
                        parsed = parse_yes_no_unsure(msg)
                        if parsed is None:
                            send_reply("Reply yes, no, or unsure.")
                            save_session(session)
                            seen.add(clean)
                            with REPLIED_LOG.open("a", encoding="utf-8") as r:
                                r.write(clean + "\n")
                            continue

                        session["answers"]["version_state"] = parsed

                        if parsed == "yes":
                            suggested = suggested_main_name(session["answers"]["item_name"])
                            session["phase"] = "main_version_name"
                            send_reply(f"Use this as the main version name: {suggested}. Reply with that exact name or your preferred variation.")
                        else:
                            session["phase"] = "version_count"
                            send_reply("How many active versions do you want to classify right now? Reply with a number.")
                        save_session(session)

                    elif phase == "main_version_name":
                        session["answers"]["main_version_name"] = msg
                        session["phase"] = "main_version_path"
                        send_reply("What is the main version path? Keep it short, like WorkDrive/Album/Song/Main version.")
                        save_session(session)

                    elif phase == "main_version_path":
                        session["answers"]["main_version_path"] = msg
                        session["phase"] = "backup_status"
                        send_reply("What is the backup status? Reply with something short like backed up, needs backup, or unsure.")
                        save_session(session)

                    elif phase == "backup_status":
                        session["answers"]["backup_status"] = parse_backup_status(msg)
                        session["phase"] = "donor_gate"
                        send_reply("Are there donor versions worth keeping in play? Reply yes, no, or unsure.")
                        save_session(session)

                    elif phase == "version_count":
                        try:
                            count = int(re.search(r"\d+", msg).group(0))
                            if count < 1:
                                raise ValueError
                        except Exception:
                            send_reply("Reply with a number like 1, 2, or 3.")
                            save_session(session)
                            seen.add(clean)
                            with REPLIED_LOG.open("a", encoding="utf-8") as r:
                                r.write(clean + "\n")
                            continue

                        session["version_count"] = count
                        session["current_version_index"] = 1
                        session["phase"] = "classify_version_name"
                        song = session["answers"]["item_name"]
                        suggested = suggested_candidate_name(song, "A")
                        send_reply(f"Version 1 of {count}: use this working name: {suggested}. Reply with that exact name or your preferred variation.")
                        save_session(session)

                    elif phase == "classify_version_name":
                        session["answers"][f"version_{session['current_version_index']}_name"] = msg
                        session["phase"] = "classify_version_role"
                        send_reply("What is this version's role? Reply with one of: main, donor, contender, archive.")
                        save_session(session)

                    elif phase == "classify_version_role":
                        role = parse_version_role(msg)
                        if role is None:
                            send_reply("Reply with one of: main, donor, contender, archive.")
                            save_session(session)
                            seen.add(clean)
                            with REPLIED_LOG.open("a", encoding="utf-8") as r:
                                r.write(clean + "\n")
                            continue

                        idx = session["current_version_index"]
                        session["answers"][f"version_{idx}_role"] = role

                        if role == "main":
                            session["answers"]["main_version_name"] = session["answers"].get(f"version_{idx}_name", "")
                        elif role == "donor":
                            donors = session["answers"].get("donor_versions", "")
                            donor_name = session["answers"].get(f"version_{idx}_name", "")
                            session["answers"]["donor_versions"] = (donors + " | " if donors else "") + donor_name

                        if idx < session["version_count"]:
                            session["current_version_index"] += 1
                            letter = chr(64 + session["current_version_index"])
                            song = session["answers"]["item_name"]
                            suggested = suggested_candidate_name(song, letter)
                            session["phase"] = "classify_version_name"
                            send_reply(f"Version {session['current_version_index']} of {session['version_count']}: use this working name: {suggested}. Reply with that exact name or your preferred variation.")
                        else:
                            if not session["answers"].get("main_version_name"):
                                session["phase"] = "pick_main_after_versions"
                                send_reply("Which of those versions is the main one to finish from? Reply with the exact version name, or say unsure.")
                            else:
                                session["phase"] = "main_version_path"
                                send_reply("What is the main version path? Keep it short, like WorkDrive/Album/Song/Main version.")
                        save_session(session)

                    elif phase == "pick_main_after_versions":
                        if unsureish(msg):
                            session["answers"]["main_version_name"] = ""
                        else:
                            session["answers"]["main_version_name"] = msg
                        session["phase"] = "main_version_path"
                        send_reply("What is the main version path? Keep it short, like WorkDrive/Album/Song/Main version.")
                        save_session(session)

                    elif phase == "donor_gate":
                        parsed = parse_yes_no_unsure(msg)
                        if parsed is None:
                            send_reply("Reply yes, no, or unsure.")
                            save_session(session)
                            seen.add(clean)
                            with REPLIED_LOG.open("a", encoding="utf-8") as r:
                                r.write(clean + "\n")
                            continue

                        if parsed in ("yes", "unsure"):
                            session["phase"] = "donor_notes"
                            send_reply("List the donor versions and what they may donate. Example: intro version has best groove, version B has key texture. You can also say unsure right now.")
                        else:
                            if not session["answers"].get("donor_versions"):
                                session["answers"]["donor_versions"] = ""
                            session["phase"] = "lanes"
                            session["step"] = 0
                            send_reply(LANES[0][1])
                        save_session(session)

                    elif phase == "donor_notes":
                        existing = session["answers"].get("donor_versions", "")
                        session["answers"]["donor_versions"] = (existing + " | " if existing else "") + msg
                        session["phase"] = "lanes"
                        session["step"] = 0
                        send_reply(LANES[0][1])
                        save_session(session)

                    elif phase == "lanes":
                        lane_index = session["step"]
                        field, _prompt = LANES[lane_index]
                        status, note = split_status_and_note(msg)

                        if status is None:
                            send_reply(
                                "Use one of these lane statuses first: done, needs work, needs review, needs re-record, not applicable, or unclear. "
                                "Natural variants like solid, review first, redo, n/a, skip, or not sure also work."
                            )
                            save_session(session)
                            seen.add(clean)
                            with REPLIED_LOG.open("a", encoding="utf-8") as r:
                                r.write(clean + "\n")
                            continue

                        session["answers"][field] = status
                        session["answers"][f"{field}_note"] = note
                        session["step"] += 1

                        if session["step"] < len(LANES):
                            send_reply(LANES[session["step"]][1])
                        else:
                            session["phase"] = "song_readiness"
                            send_reply("Overall, how far along does this song feel? You can answer like 70, pretty good, mostly there, close, rough, or ship it.")
                        save_session(session)

                    elif phase == "song_readiness":
                        value = parse_confidence(msg, "readiness")
                        if value is None:
                            send_reply("Reply with a number like 70 or a phrase like pretty good, close, rough, or mostly there.")
                            save_session(session)
                            seen.add(clean)
                            with REPLIED_LOG.open("a", encoding="utf-8") as r:
                                r.write(clean + "\n")
                            continue

                        session["answers"]["song_readiness_percent"] = value
                        session["phase"] = "ship_confidence"
                        send_reply("How close is this to ship-it final? You can answer like 25, 60, 90, not final, close, or ship it.")
                        save_session(session)

                    elif phase == "ship_confidence":
                        value = parse_confidence(msg, "ship")
                        if value is None:
                            send_reply("Reply with a number like 25 or 90, or a phrase like not final, close, or ship it.")
                            save_session(session)
                            seen.add(clean)
                            with REPLIED_LOG.open("a", encoding="utf-8") as r:
                                r.write(clean + "\n")
                            continue

                        session["answers"]["song_ship_confidence_percent"] = value
                        finalize_song(session["answers"], session)
                        reset_session()
                        save_session(session)

                    seen.add(clean)
                    with REPLIED_LOG.open("a", encoding="utf-8") as r:
                        r.write(clean + "\n")

        time.sleep(2)
