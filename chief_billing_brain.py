import csv
import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

INPUT_LOG = Path("/mnt/c/OpenClaw/logs/chief_input.log")
STATE_FILE = Path("/mnt/c/OpenClaw/logs/chief_replied.log")
SESSION_FILE = Path("/home/openclaw/chief_billing_session.json")
LISTENER_SESSION_FILE = Path("/home/openclaw/chief_billing_listener_session.json")

EXPORT_DIR = Path("/home/openclaw/OpenClaw/exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

BILLING_CSV = EXPORT_DIR / "billing_records.csv"
BILLING_JSONL = EXPORT_DIR / "billing_records.jsonl"

BILLING_FIELDS = [
    "timestamp",
    "mode",
    "client_name",
    "client_email",
    "project_or_event",
    "service_date",
    "amount_total",
    "deposit_amount",
    "due_date",
    "payment_method",
    "notes",
    "invoice_number",
    "payment_amount",
    "payment_date",
    "amount_received",
    "next_follow_up_date",
]

CREATE_INVOICE_QUESTIONS = [
    ("client_name", "Who is the client?"),
    ("client_email", "What is the client email?"),
    ("project_or_event", "What is the project or event name?"),
    ("service_date", "What is the service date?"),
    ("amount_total", "What is the total amount?"),
    ("deposit_amount", "What is the deposit amount?"),
    ("due_date", "What is the due date?"),
    ("payment_method", "What payment method should be listed?"),
    ("notes", "Any notes to include? If none, say none."),
]

PAYMENT_UPDATE_QUESTIONS = [
    ("invoice_number", "What is the invoice number?"),
    ("payment_amount", "How much was paid?"),
    ("payment_date", "What date was it paid?"),
    ("notes", "Any notes to attach? If none, say none."),
]

FOLLOW_UP_QUESTIONS = [
    ("client_name", "Which client is this follow-up for?"),
    ("invoice_number", "What invoice number, if any? If none, say none."),
    ("next_follow_up_date", "When should the next follow-up happen?"),
    ("notes", "What should the follow-up note say?"),
]

RECEIPT_QUESTIONS = [
    ("client_name", "Who is the receipt for?"),
    ("invoice_number", "What is the invoice number?"),
    ("amount_received", "How much was received?"),
    ("payment_date", "What date was it received?"),
    ("notes", "Any notes for the receipt? If none, say none."),
]


def send_reply(text: str) -> None:
    subprocess.run(
        ["python", str(Path.home() / "chief_sender.py"), text],
        check=False,
    )


def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_session() -> dict:
    return load_json(
        SESSION_FILE,
        {
            "active": False,
            "mode": None,
            "step": 0,
            "answers": {},
            "last_field": None,
            "last_prompt": None,
        },
    )


def save_session(session: dict) -> None:
    save_json(SESSION_FILE, session)


def reset_session() -> None:
    save_session(
        {
            "active": False,
            "mode": None,
            "step": 0,
            "answers": {},
            "last_field": None,
            "last_prompt": None,
        }
    )


def clear_listener_billing_session() -> None:
    save_json(LISTENER_SESSION_FILE, {"active": False, "mode": None})


def get_questions(mode: str):
    if mode == "INVOICE":
        return CREATE_INVOICE_QUESTIONS
    if mode == "PAYMENT":
        return PAYMENT_UPDATE_QUESTIONS
    if mode == "FOLLOWUP":
        return FOLLOW_UP_QUESTIONS
    if mode == "RECEIPT":
        return RECEIPT_QUESTIONS
    return []


def normalize_payload(line: str) -> str:
    if "] " in line:
        return line.split("] ", 1)[1].strip()
    return line.strip()


def looks_like_correction(text: str) -> bool:
    t = text.lower().strip()
    phrases = [
        "hold up",
        "that was wrong",
        "the last thing was wrong",
        "i messed that up",
        "i messed up",
        "shit i totally messed that last one up",
        "totally messed that last one up",
        "oops i messed up the last one",
        "correction",
        "change that",
        "go back",
        "undo that",
        "wait",
    ]
    return any(p in t for p in phrases)


def extract_replacement_value(text: str) -> str | None:
    patterns = [
        r"make it\s+(.+)$",
        r"change it to\s+(.+)$",
        r"change that to\s+(.+)$",
        r"it should be\s+(.+)$",
        r"should be\s+(.+)$",
        r"use\s+(.+)$",
        r"actually\s+(.+)$",
        r"its\s+(.+)$",
        r"it's\s+(.+)$",
    ]
    for pattern in patterns:
        m = re.search(pattern, text.strip(), flags=re.IGNORECASE)
        if m:
            return m.group(1).strip(" .")
    return None


def ordinal_prompt(mode: str, step_index: int) -> str | None:
    questions = get_questions(mode)
    if 0 <= step_index < len(questions):
        return questions[step_index][1]
    return None


def ensure_csv_header() -> None:
    if not BILLING_CSV.exists():
        with BILLING_CSV.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=BILLING_FIELDS)
            writer.writeheader()


def normalize_answer(value: str | None) -> str:
    if value is None:
        return ""
    t = value.strip()
    if t.lower() in {"none", "nope", "n/a", "na"}:
        return ""
    return t


def next_invoice_number() -> str:
    counter_file = EXPORT_DIR / "invoice_counter.txt"
    current = 1000
    if counter_file.exists():
        try:
            current = int(counter_file.read_text(encoding="utf-8").strip())
        except Exception:
            current = 1000
    current += 1
    counter_file.write_text(str(current), encoding="utf-8")
    return f"INV-{current}"


def build_record(session: dict) -> dict:
    answers = session.get("answers", {})
    mode = session.get("mode", "") or ""
    record = {field: "" for field in BILLING_FIELDS}
    record["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record["mode"] = mode

    for k, v in answers.items():
        if k in record:
            record[k] = normalize_answer(v)

    if mode == "INVOICE" and not record["invoice_number"]:
        record["invoice_number"] = next_invoice_number()

    return record


def save_record(record: dict) -> None:
    ensure_csv_header()
    with BILLING_CSV.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BILLING_FIELDS)
        writer.writerow(record)

    with BILLING_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


state = load_json(STATE_FILE, {"last_index": 0})
last_index = int(state.get("last_index", 0))

print("Chief billing brain online.")

while True:
    session = load_session()

    if INPUT_LOG.exists():
        lines = INPUT_LOG.read_text(encoding="utf-8").splitlines()

        while last_index < len(lines):
            clean = lines[last_index].rstrip("\n")
            payload = normalize_payload(clean)
            upper = payload.upper().strip()

            last_index += 1
            save_json(STATE_FILE, {"last_index": last_index})

            if not payload:
                continue

            if session.get("active"):
                questions = get_questions(session["mode"])
                step = session.get("step", 0)

                if looks_like_correction(payload):
                    last_field = session.get("last_field")
                    replacement = extract_replacement_value(payload)

                    if last_field and replacement:
                        session["answers"][last_field] = replacement
                        save_session(session)

                        current_prompt = ordinal_prompt(session["mode"], step)
                        send_reply(f"Updated {last_field} to {replacement}.")
                        if current_prompt:
                            send_reply(current_prompt)
                        else:
                            send_reply("Correction saved.")
                    elif last_field:
                        current_value = session["answers"].get(last_field, "")
                        send_reply(
                            f"Okay. What should {last_field} be instead? Current value: {current_value}"
                        )
                    else:
                        send_reply("Correction noted, but I could not identify the last field to change.")
                    break

                if step < len(questions):
                    field, prompt = questions[step]
                    session["answers"][field] = payload
                    session["last_field"] = field
                    session["last_prompt"] = prompt
                    session["step"] = step + 1
                    save_session(session)

                    if session["step"] < len(questions):
                        next_prompt = questions[session["step"]][1]
                        send_reply(next_prompt)
                    else:
                        record = build_record(session)
                        save_record(record)
                        send_reply(
                            f"{session['mode'].title()} capture complete. Saved {record.get('invoice_number', 'record')} to billing records."
                        )
                        reset_session()
                        clear_listener_billing_session()
                break

            if upper == "INVOICE":
                session = {
                    "active": True,
                    "mode": "INVOICE",
                    "step": 0,
                    "answers": {},
                    "last_field": None,
                    "last_prompt": None,
                }
                save_session(session)
                send_reply(CREATE_INVOICE_QUESTIONS[0][1])
                break

            if upper == "PAYMENT":
                session = {
                    "active": True,
                    "mode": "PAYMENT",
                    "step": 0,
                    "answers": {},
                    "last_field": None,
                    "last_prompt": None,
                }
                save_session(session)
                send_reply(PAYMENT_UPDATE_QUESTIONS[0][1])
                break

            if upper == "FOLLOWUP":
                session = {
                    "active": True,
                    "mode": "FOLLOWUP",
                    "step": 0,
                    "answers": {},
                    "last_field": None,
                    "last_prompt": None,
                }
                save_session(session)
                send_reply(FOLLOW_UP_QUESTIONS[0][1])
                break

            if upper == "RECEIPT":
                session = {
                    "active": True,
                    "mode": "RECEIPT",
                    "step": 0,
                    "answers": {},
                    "last_field": None,
                    "last_prompt": None,
                }
                save_session(session)
                send_reply(RECEIPT_QUESTIONS[0][1])
                break

    time.sleep(2)
