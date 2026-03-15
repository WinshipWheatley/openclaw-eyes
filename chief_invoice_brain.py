import csv
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

QUEUE_LOG = Path("/mnt/c/OpenClaw/logs/chief_queue.log")
REPLIED_LOG = Path("/mnt/c/OpenClaw/logs/chief_invoice_replied.log")
SESSION_FILE = Path("/mnt/c/OpenClaw/logs/chief_invoice_session.json")

BILLING_ROOT = Path("/mnt/c/OpenClaw/billing")
TRACKER_CSV = BILLING_ROOT / "tracker" / "invoice_tracker.csv"
COUNTER_FILE = BILLING_ROOT / "tracker" / "invoice_counter.txt"
INVOICES_DIR = BILLING_ROOT / "invoices"

seen = set()

if REPLIED_LOG.exists():
    with REPLIED_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            seen.add(line.rstrip("\n"))

if SESSION_FILE.exists():
    with SESSION_FILE.open("r", encoding="utf-8") as f:
        session = json.load(f)
else:
    session = {
        "active": False,
        "step": 0,
        "answers": {},
    }


QUESTIONS = [
    ("client_name", "Who is the invoice for?"),
    ("client_email", "What email should this invoice go to? If unknown, say unknown."),
    ("project_or_event", "What is this invoice for? Keep it short and clear."),
    ("service_date", "What is the service or event date? Use YYYY-MM-DD if possible."),
    ("issue_date", "What is the issue date? Use YYYY-MM-DD, or say today."),
    ("due_date", "What is the due date? Use YYYY-MM-DD, or say due on receipt."),
    ("amount_total", "What is the total amount? Numbers only, like 400 or 850."),
    ("deposit_amount", "What is the deposit amount? If none, say 0."),
    ("payment_method", "Preferred payment method for this invoice? Example: Venmo, Zelle, check, or any."),
    ("notes", "Any notes to include? If none, say none."),
]


def save_session():
    with SESSION_FILE.open("w", encoding="utf-8") as f:
        json.dump(session, f, indent=2)


def send_reply(text: str):
    subprocess.run(
        ["python", str(Path.home() / "chief_sender.py"), text],
        check=False,
    )


def ensure_tracker_header():
    if not TRACKER_CSV.exists():
        TRACKER_CSV.parent.mkdir(parents=True, exist_ok=True)
        with TRACKER_CSV.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "invoice_number", "client_name", "client_email", "project_or_event",
                    "service_date", "issue_date", "due_date", "amount_total",
                    "deposit_amount", "balance_amount", "payment_method",
                    "invoice_status", "payment_status", "follow_up_status",
                    "file_path", "notes", "updated_at"
                ],
            )
            writer.writeheader()


def next_invoice_number():
    COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not COUNTER_FILE.exists():
        COUNTER_FILE.write_text("1000", encoding="utf-8")

    current = COUNTER_FILE.read_text(encoding="utf-8").strip()
    try:
        num = int(current)
    except Exception:
        num = 1000

    next_num = num + 1
    COUNTER_FILE.write_text(str(next_num), encoding="utf-8")
    return f"WL-{num}"


def normalize_issue_date(text: str):
    if text.strip().lower() == "today":
        return datetime.now().strftime("%Y-%m-%d")
    return text.strip()


def make_invoice_text(a: dict, invoice_number: str, balance_amount: str):
    return f"""WINSHIP LIVE
H. Winship Wheatley IV
1009 Smithville St.
Annapolis, MD 21401
winshiplive@gmail.com
443-758-4913
winshiplivemusic.com

INVOICE

Invoice Number: {invoice_number}
Issue Date: {a['issue_date']}
Due Date: {a['due_date']}

Bill To:
{a['client_name']}
{a['client_email']}

Description:
{a['project_or_event']}

Service Date:
{a['service_date']}

Amount Total: ${a['amount_total']}
Deposit Amount: ${a['deposit_amount']}
Balance Amount: ${balance_amount}

Preferred Payment Method:
{a['payment_method']}

Accepted Payment Methods:
- Cash
- Check payable to Winship Wheatley
- Venmo: @Winship
- Zelle: 443-758-4913

Notes:
{a['notes']}

Thank you for your business.
"""


def write_invoice_file(a: dict, invoice_number: str):
    INVOICES_DIR.mkdir(parents=True, exist_ok=True)
    safe_client = "".join(ch for ch in a["client_name"] if ch.isalnum() or ch in (" ", "_", "-")).strip()
    safe_client = "_".join(safe_client.split()) or "Client"
    filename = f"{invoice_number}__{safe_client}.txt"
    file_path = INVOICES_DIR / filename

    total = float(a["amount_total"])
    deposit = float(a["deposit_amount"])
    balance = f"{max(total - deposit, 0):.2f}"

    invoice_text = make_invoice_text(a, invoice_number, balance)
    file_path.write_text(invoice_text, encoding="utf-8")

    return file_path, balance


def append_tracker_row(a: dict, invoice_number: str, file_path: Path, balance_amount: str):
    ensure_tracker_header()

    row = {
        "invoice_number": invoice_number,
        "client_name": a["client_name"],
        "client_email": a["client_email"],
        "project_or_event": a["project_or_event"],
        "service_date": a["service_date"],
        "issue_date": a["issue_date"],
        "due_date": a["due_date"],
        "amount_total": a["amount_total"],
        "deposit_amount": a["deposit_amount"],
        "balance_amount": balance_amount,
        "payment_method": a["payment_method"],
        "invoice_status": "drafted",
        "payment_status": "unpaid",
        "follow_up_status": "not sent",
        "file_path": str(file_path),
        "notes": a["notes"],
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    with TRACKER_CSV.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "invoice_number", "client_name", "client_email", "project_or_event",
                "service_date", "issue_date", "due_date", "amount_total",
                "deposit_amount", "balance_amount", "payment_method",
                "invoice_status", "payment_status", "follow_up_status",
                "file_path", "notes", "updated_at"
            ],
        )
        writer.writerow(row)


def finalize_invoice(a: dict):
    a["issue_date"] = normalize_issue_date(a["issue_date"])
    invoice_number = next_invoice_number()
    file_path, balance_amount = write_invoice_file(a, invoice_number)
    append_tracker_row(a, invoice_number, file_path, balance_amount)

    send_reply(
        f"Invoice drafted.\n"
        f"Invoice number: {invoice_number}\n"
        f"Client: {a['client_name']}\n"
        f"Total: ${a['amount_total']}\n"
        f"Deposit: ${a['deposit_amount']}\n"
        f"Balance: ${balance_amount}\n"
        f"Saved to: {file_path}"
    )


def reset_session():
    session["active"] = False
    session["step"] = 0
    session["answers"] = {}
    save_session()


print("Chief invoice brain online.")

while True:
    if QUEUE_LOG.exists():
        with QUEUE_LOG.open("r", encoding="utf-8") as f:
            for line in f:
                clean = line.rstrip("\n")
                if not clean or clean in seen:
                    continue

                message_text = clean.split("] ", 1)[1] if "] " in clean else clean
                msg = message_text.strip()

                if msg.upper() == "INVOICE":
                    session["active"] = True
                    session["step"] = 0
                    session["answers"] = {}
                    send_reply("Invoice mode started. Who is the invoice for?")
                    save_session()

                    seen.add(clean)
                    with REPLIED_LOG.open("a", encoding="utf-8") as r:
                        r.write(clean + "\n")
                    continue

                if not session["active"]:
                    seen.add(clean)
                    with REPLIED_LOG.open("a", encoding="utf-8") as r:
                        r.write(clean + "\n")
                    continue

                field, _prompt = QUESTIONS[session["step"]]
                session["answers"][field] = msg
                session["step"] += 1

                if session["step"] < len(QUESTIONS):
                    next_field, next_prompt = QUESTIONS[session["step"]]
                    send_reply(next_prompt)
                else:
                    finalize_invoice(session["answers"])
                    reset_session()

                save_session()

                seen.add(clean)
                with REPLIED_LOG.open("a", encoding="utf-8") as r:
                    r.write(clean + "\n")

    time.sleep(2)
