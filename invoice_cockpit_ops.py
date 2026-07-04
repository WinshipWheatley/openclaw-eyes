"""IB-3 real integrations — the production ops the cockpit executor calls, plus a JSON session store.

Reuses the proven pieces: invoice PDF (invoice_generator), Clara draft (clara_invoice_email_draft_
package), attachment + test-mode send (google_access_broker + global_run_mode_context), Telegram
(the Maestro bot). TEST sends redirect to the operator inbox and are always safe; the REAL send is
refused while SEND_HOLD is active. Fails soft — an op error becomes {"ok": False, "error": ...},
never an exception that kills the listener.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

DEFAULT_SESSION_PATH = Path("/home/openclaw/state/invoice_cockpit/session.json")
_ALLOWLISTED_INBOX = "winshiplive@gmail.com"


class JsonSessionStore:
    """One active invoice-cockpit session persisted to JSON (single operator)."""

    def __init__(self, path: str | Path = DEFAULT_SESSION_PATH):
        self.path = Path(path)

    def load(self) -> dict | None:
        try:
            return json.loads(self.path.read_text()) if self.path.is_file() else None
        except Exception:
            return None

    def save(self, state: dict) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(state))
        except Exception:
            pass

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except Exception:
            pass


def _telegram(method: str, **kw):
    import requests
    from chief_guardian_sender import _chat_id  # reuse resolved chat
    tok = os.environ.get("MAESTRO_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID") or _chat_id()
    kw.setdefault("data", {})["chat_id"] = chat
    return requests.post(f"https://api.telegram.org/bot{tok}/{method}", timeout=30, **kw).json()


class RealCockpitOps:
    """Production ops. Instantiate under the agent runtime (env/creds loaded)."""

    def __init__(self, contact_name: str = ""):
        self.contact_name = contact_name

    # -- invoice preparation (fallback generator; Codex-Mac real invoice plugs in here later) --
    def prepare_invoice(self, client: str):
        os.environ.setdefault("OPENCLAW_INVOICES_DIR", "/home/openclaw/state/invoices")
        from invoice_generator import build_st_annes_invoice_data, generate_invoice_pdf, get_next_invoice_number
        data = build_st_annes_invoice_data()  # St Anne's fallback; other clients extend later
        data["invoice_number"] = get_next_invoice_number()
        pdf = generate_invoice_pdf(data)
        data["attachment_filename"] = Path(pdf).name
        digest = hashlib.sha256(Path(pdf).read_bytes()).hexdigest()
        os.environ["OPENCLAW_ATTACHMENT_ALLOWED_DIRS"] = str(Path(pdf).parent)
        return data, str(pdf), digest

    def telegram_pdf(self, pdf_path: str, caption: str):
        try:
            with open(pdf_path, "rb") as fh:
                return {"ok": bool(_telegram("sendDocument", data={"caption": caption},
                                             files={"document": (Path(pdf_path).name, fh, "application/pdf")}).get("ok"))}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def telegram_message(self, text: str):
        try:
            return {"ok": bool(_telegram("sendMessage", data={"text": text}).get("ok"))}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def clara_draft_and_guardian(self, client, invoice_data, pdf_path):
        try:
            from clara_invoice_email_draft_package import build_general_client_invoice_body
            body = build_general_client_invoice_body(invoice_data, {"name": self.contact_name})
            msg = ("Clara's draft to " + str((invoice_data or {}).get("client_email") or "the client") +
                   ":\n\n" + body + "\n\n— Reply 'approve' to run the TEST send to your inbox, or tell me what to change.")
            return self.telegram_message(msg)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def apply_edit(self, invoice_data, instruction):
        # Deterministic edit parsing lands via Codex task 20 (parse_invoice_edit); until then, ack + hold.
        try:
            from invoice_preview_format import parse_invoice_edit  # task 20 (optional)
            edit = parse_invoice_edit(instruction, invoice_data)
            return {"ok": True, "edit": edit}
        except Exception:
            return {"ok": True, "note": "edit noted; awaiting the structured edit parser (task 20)"}

    def send_email(self, *, to, attachment, attachment_sha256, invoice_data, mode):
        try:
            import global_run_mode_context as grmc
            import google_access_broker as broker
            from clara_invoice_email_draft_package import build_general_client_invoice_body
            subject = f"Invoice — {(invoice_data or {}).get('client_name','')}".strip()
            body = build_general_client_invoice_body(invoice_data, {"name": self.contact_name})
            params = {"to": to, "subject": subject, "body": body,
                      "attachments": [attachment], "attachment_sha256": [attachment_sha256]}
            if mode == "test":
                grmc.handle_run_mode_set_request(grmc.DEFAULT_SQLITE_PATH, {
                    "requested_run_mode": "test_live", "allowlisted_recipients": [grmc.ALLOWLISTED_TEST_EMAIL],
                    "test_execution_authority": {"schema_version": grmc.TEST_EXECUTION_AUTHORITY_SCHEMA,
                        "verifier_status": "VERIFIED_TEST_AUTHORITY", "live_external_effects_allowed": True}})
                try:
                    res = broker.call("cassandra", "google.gmail.send", params)
                finally:
                    grmc.handle_run_mode_set_request(grmc.DEFAULT_SQLITE_PATH, {"requested_run_mode": "production"})
                return res
            # REAL: refuse while SEND_HOLD is active — the operator lifts it deliberately to go live.
            from email_send_executor import DEFAULT_SEND_HOLD_PATH
            if Path(os.environ.get("OPENCLAW_SEND_HOLD_PATH") or DEFAULT_SEND_HOLD_PATH).is_file():
                return {"ok": False, "error": "SEND_HOLD is active — lift it to send this to the client for real."}
            return broker.call("cassandra", "google.gmail.send", params)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


__all__ = ["RealCockpitOps", "JsonSessionStore", "DEFAULT_SESSION_PATH"]
