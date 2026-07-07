import csv
import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from chief_file_io import load_json, save_json
from adaptive_model_call import adaptive_ollama_text

ollama_call = adaptive_ollama_text

def _local_model_call(*args, **kwargs):
    return globals()["ollama_call"](*args, **kwargs)

from chief_session_manager import (
    get_workflow_state,
    set_workflow_state,
    mark_complete,
)

INPUT_LOG = Path("/mnt/c/OpenClaw/logs/chief_input.log")
STATE_FILE = Path("/mnt/c/OpenClaw/logs/chief_replied.log")
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



_BILLING_DEFAULT = {
    "active": False,
    "mode": None,
    "step": 0,
    "answers": {},
    "last_field": None,
    "last_prompt": None,
}


def load_session() -> dict:
    state = get_workflow_state()
    if not state:
        return json.loads(json.dumps(_BILLING_DEFAULT))
    return state


def save_session(session: dict) -> None:
    set_workflow_state(session)


def reset_session() -> None:
    set_workflow_state(json.loads(json.dumps(_BILLING_DEFAULT)))
    mark_complete()


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


_NORMALIZE_PROMPT = """\
Normalize this billing field value into a clean, standard format.

Field: {field}
Raw input: {raw}
Today's date: {today}

Rules:
- Amount fields (amount_total, deposit_amount, payment_amount, amount_received): return digits and decimal only, no currency symbols or words (e.g. "500", "1500.00").
- Date fields (service_date, due_date, payment_date, next_follow_up_date): return YYYY-MM-DD. Resolve relative dates (e.g. "next friday", "tomorrow") using today's date.
- Name, email, event, notes fields: fix capitalization only. Return as-is if already clean.
- Return ONLY the normalized value, no explanation.

Normalized value:"""

_AMOUNT_FIELDS = {"amount_total", "deposit_amount", "payment_amount", "amount_received"}
_DATE_FIELDS = {"service_date", "due_date", "payment_date", "next_follow_up_date"}


def _llm_normalize_billing_answer(field: str, raw: str) -> str:
    """Use LLM to normalize natural-language billing answers. Falls back to raw on failure."""
    if field not in _AMOUNT_FIELDS and field not in _DATE_FIELDS:
        return raw  # No normalization needed for text fields
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = _NORMALIZE_PROMPT.format(field=field, raw=raw, today=today)
    result = _local_model_call(prompt, timeout=10).strip()
    # Sanity-check: for amounts, ensure result looks numeric
    if field in _AMOUNT_FIELDS:
        cleaned = re.sub(r"[^\d.]", "", result)
        return cleaned if cleaned else raw
    # For dates, accept anything that looks like a date (YYYY-MM-DD or free text)
    return result if result else raw


def handle(text: str) -> list[str]:
    """Process a billing answer directly.
    Returns reply strings to send. Returns [] if no active session.
    Does not call send_reply() — caller is responsible for delivery.
    """
    session = load_session()
    if not session.get("active"):
        return []

    questions = get_questions(session["mode"])
    step = session.get("step", 0)
    replies = []

    if looks_like_correction(text):
        last_field = session.get("last_field")
        replacement = extract_replacement_value(text)
        if last_field and replacement:
            session["answers"][last_field] = replacement
            save_session(session)
            current_prompt = ordinal_prompt(session["mode"], step)
            replies.append(f"Updated {last_field} to {replacement}.")
            replies.append(current_prompt if current_prompt else "Correction saved.")
        elif last_field:
            current_value = session["answers"].get(last_field, "")
            replies.append(
                f"Okay. What should {last_field} be instead? Current value: {current_value}"
            )
        else:
            replies.append("Correction noted, but I could not identify the last field to change.")
        return replies

    if step < len(questions):
        field, _prompt = questions[step]
        normalized = _llm_normalize_billing_answer(field, text)
        session["answers"][field] = normalized
        session["last_field"] = field
        session["last_prompt"] = _prompt
        session["step"] = step + 1
        # Skip any steps already pre-filled from the trigger message
        while session["step"] < len(questions) and questions[session["step"]][0] in session["answers"]:
            session["step"] += 1
        save_session(session)
        if session["step"] < len(questions):
            replies.append(questions[session["step"]][1])
        else:
            record = build_record(session)
            save_record(record)
            replies.append(
                f"{session['mode'].title()} capture complete. "
                f"Saved {record.get('invoice_number', 'record')} to billing records."
            )
            reset_session()
            clear_listener_billing_session()

    return replies


if __name__ == "__main__":
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
