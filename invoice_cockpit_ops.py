"""IB-3 real integrations — the production ops the cockpit executor calls, plus a JSON session store.

Reuses the proven pieces: invoice PDF (invoice_generator), Clara draft (clara_invoice_email_draft_
package), and attachment + test-mode send (google_access_broker + global_run_mode_context).
Telegram-facing methods return origin-bound transport intents; this module never chooses a bot or
chat. TEST sends redirect to the operator inbox and are always safe; the REAL send is refused while
SEND_HOLD is active. Fails soft — an op error becomes {"ok": False, "error": ...}, never an
exception that kills the listener.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from origin_bound_output import (
    GENERIC_SAFE_FAILURE,
    OriginBoundOutput,
    OutputOrigin,
    receipt_pointer,
)
from final_output_boundary import OutputBoundaryContext

DEFAULT_SESSION_PATH = Path("/home/openclaw/state/invoice_cockpit/session.json")
DEFAULT_REAL_INVOICE_INCOMING_DIR = Path("/home/openclaw/state/invoice_cockpit/incoming")
DEFAULT_FINALIZED_INVOICE_DIR = Path("/home/openclaw/state/invoices")
REAL_INVOICE_SCHEMA_VERSION = "ST_ANNES_JUNE_INVOICE_V0"
_ALLOWLISTED_INBOX = "winshiplive@gmail.com"
_FINALIZED_INVOICE_RE = re.compile(
    r"^WL-(?P<year>\d{4})-(?P<sequence>\d{4,})__(?P<client>.+)\.pdf$",
    re.IGNORECASE,
)


def _client_slug(value: str) -> str:
    text = str(value or "").lower().replace("'", "")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _incoming_dir() -> Path:
    return Path(os.environ.get("OPENCLAW_INVOICE_COCKPIT_INCOMING_DIR") or DEFAULT_REAL_INVOICE_INCOMING_DIR)


def _finalized_invoice_dir() -> Path:
    return Path(os.environ.get("OPENCLAW_INVOICES_DIR") or DEFAULT_FINALIZED_INVOICE_DIR)


def _finalized_pdf_issue_period(path: Path) -> tuple[str, str] | None:
    """Return (`YYYY-MM`, `YYYY-MM-DD`) from the artifact's printed Issue Date.

    Month-bound review requests fail closed if the finalized PDF cannot prove
    its own issue month; a higher WL sequence alone is not temporal evidence.
    """

    try:
        import pdfplumber

        with pdfplumber.open(path) as document:
            text = "\n".join((page.extract_text() or "") for page in document.pages[:2])
    except Exception:
        return None
    match = re.search(r"\bIssue\s+Date\s+(?P<date>20\d{2}-\d{2}-\d{2})\b", text, re.IGNORECASE)
    if match is None:
        return None
    issue_date = match.group("date")
    return issue_date[:7], issue_date


def _finalized_invoice_candidates(
    client: Any,
    *,
    requested_period: str | None = None,
) -> list[tuple[int, int, Path, str]]:
    """Return canonical finalized artifacts without consulting draft receipts.

    Only `WL-YYYY-NNNN__Client.pdf` names inside the configured invoice
    directory qualify.  The June incoming receipt/PDF and any DRAFT filename
    are therefore outside this lookup by construction.
    """

    root = _finalized_invoice_dir()
    if not root.is_dir():
        return []
    try:
        resolved_root = root.resolve(strict=True)
    except OSError:
        return []
    wanted_clients = set(_client_slug_candidates(client))
    explicit_year_match = re.match(r"^(?P<year>\d{4})-(?:0[1-9]|1[0-2])$", str(requested_period or ""))
    explicit_year = int(explicit_year_match.group("year")) if explicit_year_match else None
    candidates: list[tuple[int, int, Path, str]] = []
    for path in root.iterdir():
        match = _FINALIZED_INVOICE_RE.fullmatch(path.name)
        if match is None or "draft" in path.name.casefold() or not path.is_file():
            continue
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            continue
        if resolved.parent != resolved_root:
            continue
        year = int(match.group("year"))
        if explicit_year is not None and year != explicit_year:
            continue
        artifact_client = _registry_client_slug(match.group("client"))
        if wanted_clients and artifact_client not in wanted_clients:
            continue
        issue_period = _finalized_pdf_issue_period(resolved)
        if requested_period:
            if issue_period is None or issue_period[0] != requested_period:
                continue
        issue_date = issue_period[1] if issue_period is not None else ""
        candidates.append((year, int(match.group("sequence")), resolved, issue_date))
    return sorted(candidates, key=lambda row: (row[0], row[1]), reverse=True)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _receipt_matches_client(receipt: dict[str, Any], *, client: str, receipt_path: Path) -> bool:
    wanted = _client_slug(client)
    candidates = (
        receipt_path.stem,
        receipt.get("client_ref"),
        receipt.get("client"),
        receipt.get("client_name"),
        receipt.get("customer_name"),
    )
    return wanted in {_client_slug(str(candidate or "")) for candidate in candidates}


def _receipt_candidates(client: str) -> list[Path]:
    incoming = _incoming_dir()
    if not incoming.is_dir():
        return []
    slug = _client_slug(client)
    candidates: list[Path] = []
    direct = incoming / f"{slug}.json"
    if direct.is_file():
        candidates.append(direct)
    for path in sorted(incoming.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        if path not in candidates:
            candidates.append(path)
    return candidates


def _first_present(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, "", []):
            return value
    return None


def _amount_units(receipt: dict[str, Any]) -> str:
    units = str(receipt.get("amount_units") or receipt.get("currency_units") or "dollars").strip().lower()
    if units in {"cent", "cents", "minor", "minor_unit", "minor_units"}:
        return "cents"
    return "dollars"


def _coerce_amount(value: Any, *, amount_units: str) -> int | float:
    if value is None or isinstance(value, bool):
        return 0
    if amount_units == "cents":
        return int(round(float(value)))
    numeric = float(value)
    return int(numeric) if numeric.is_integer() else numeric


def _line_items_from_receipt(receipt: dict[str, Any], *, amount_units: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    raw_items = receipt.get("line_items") or receipt.get("items") or []
    if not isinstance(raw_items, list):
        return items
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        if amount_units == "cents":
            amount = _first_present(raw, "amount_minor_units", "amount_cents", "amount")
        else:
            amount = _first_present(raw, "amount", "amount_dollars", "total", "line_total")
        items.append(
            {
                "description": str(
                    _first_present(raw, "description", "service_label", "event", "label")
                    or "Invoice line item"
                ),
                "service_date": str(_first_present(raw, "service_date", "date") or ""),
                "amount": _coerce_amount(amount, amount_units=amount_units),
            }
        )
    return items


def _total_from_receipt(
    receipt: dict[str, Any],
    line_items: list[dict[str, Any]],
    *,
    amount_units: str,
) -> int | float:
    if amount_units == "cents":
        total = _first_present(receipt, "total_minor_units", "total_cents", "total", "amount_total")
    else:
        total = _first_present(receipt, "total", "amount_total", "invoice_total", "total_amount", "amount_due")
    if total is not None:
        return _coerce_amount(total, amount_units=amount_units)
    return sum(item["amount"] for item in line_items)


def _pdf_path_from_receipt(receipt: dict[str, Any], receipt_path: Path) -> Path | None:
    raw_path = _first_present(
        receipt,
        "rendered_pdf_path",
        "pdf_path",
        "rendered_pdf",
        "source_pdf_path",
    )
    if raw_path:
        pdf_path = Path(str(raw_path))
        if not pdf_path.is_absolute():
            pdf_path = receipt_path.parent / pdf_path
        if pdf_path.is_file():
            return pdf_path
    same_stem = receipt_path.with_suffix(".pdf")
    return same_stem if same_stem.is_file() else None


def _real_invoice_from_receipt(
    *,
    client: str,
    receipt: dict[str, Any],
    receipt_path: Path,
    pdf_path: Path,
) -> dict[str, Any]:
    amount_units = _amount_units(receipt)
    line_items = _line_items_from_receipt(receipt, amount_units=amount_units)
    amount_total = _total_from_receipt(receipt, line_items, amount_units=amount_units)
    deposit_paid = _coerce_amount(
        _first_present(receipt, "deposit_paid", "deposit", "deposit_amount") or 0,
        amount_units=amount_units,
    )
    balance_due = _first_present(receipt, "balance_due", "amount_due")
    balance_due = (
        _coerce_amount(balance_due, amount_units=amount_units)
        if balance_due is not None
        else max(amount_total - deposit_paid, 0)
    )
    project_desc = str(
        _first_present(receipt, "project_desc", "description", "invoice_period_label")
        or "; ".join(item["description"] for item in line_items)
        or f"{client} invoice"
    )
    service_date = str(
        _first_present(receipt, "service_date", "invoice_period")
        or (line_items[0]["service_date"] if line_items else "")
    )
    return {
        "invoice_number": str(_first_present(receipt, "invoice_number", "invoice_id") or ""),
        "client_name": str(_first_present(receipt, "client_name", "customer_name") or client),
        "client_email": str(_first_present(receipt, "client_email", "email") or "unknown"),
        "project_desc": project_desc,
        "service_date": service_date,
        "issue_date": str(_first_present(receipt, "issue_date", "issue_date_iso", "invoice_date") or ""),
        "net_terms": str(_first_present(receipt, "net_terms", "terms") or "Due on Receipt"),
        "amount_total": amount_total,
        "deposit_paid": deposit_paid,
        "balance_due": balance_due,
        "line_items": line_items,
        "amount_units": amount_units,
        "line_item_source": "codex_mac_invoice_receipt",
        "real_invoice_receipt_path": str(receipt_path),
        "rendered_pdf_path": str(pdf_path),
        "source_schema_version": str(receipt.get("schema_version") or ""),
    }


def _load_real_invoice_receipt(client: str) -> tuple[dict[str, Any], Path] | None:
    for receipt_path in _receipt_candidates(client):
        receipt = _read_json(receipt_path)
        if receipt is None:
            continue
        if receipt.get("schema_version") != REAL_INVOICE_SCHEMA_VERSION:
            continue
        if not _receipt_matches_client(receipt, client=client, receipt_path=receipt_path):
            continue
        pdf_path = _pdf_path_from_receipt(receipt, receipt_path)
        if pdf_path is None:
            continue
        data = _real_invoice_from_receipt(
            client=client,
            receipt=receipt,
            receipt_path=receipt_path,
            pdf_path=pdf_path,
        )
        if data["invoice_number"]:
            return data, pdf_path
    return None


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


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _registry_client_slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _clean_text(value).lower()).strip("-")


def _dict_first(source: Any, *keys: str) -> Any:
    if not isinstance(source, dict):
        return None
    for key in keys:
        value = source.get(key)
        if value not in (None, "", []):
            return value
    return None


def _client_slug_candidates(*sources: Any) -> tuple[str, ...]:
    candidates: list[str] = []
    for source in sources:
        if isinstance(source, dict):
            values = (
                _dict_first(source, "client_ref", "slug", "client_slug", "client"),
                _dict_first(source, "client_name", "client_display_name", "display_name", "customer_name"),
            )
        else:
            values = (source,)
        for value in values:
            slug = _registry_client_slug(value)
            if slug and slug not in candidates:
                candidates.append(slug)
    return tuple(candidates)


def _contact_emails(contact: dict[str, Any]) -> tuple[str, ...]:
    emails = contact.get("emails")
    if isinstance(emails, (list, tuple)):
        values = tuple(str(email).strip().lower() for email in emails if str(email).strip())
    else:
        values = ()
    primary = str(contact.get("email") or "").strip().lower()
    if primary and primary not in values:
        values = (primary, *values)
    return values


def _contact_role_rank(contact: dict[str, Any]) -> int:
    text = f"{contact.get('id', '')} {contact.get('role', '')}".casefold()
    preferences = (
        "primary_invoice_contact",
        "primary invoice",
        "billing",
        "accounts payable",
        "ap-lead",
        "ap",
        "finance",
        "intermediary",
        "treasurer",
        "accountant",
    )
    for index, token in enumerate(preferences):
        if token in text:
            return index
    return len(preferences)


def _select_contact_for_client(
    contacts: list[dict[str, Any]],
    *,
    invoice_data: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not contacts:
        return None
    email = str(_dict_first(invoice_data or {}, "client_email", "recipient_email", "to_email") or "").strip().lower()
    if email:
        for contact in contacts:
            if email in _contact_emails(contact):
                return contact
    return sorted(
        contacts,
        key=lambda contact: (_contact_role_rank(contact), str(contact.get("name") or ""), str(contact.get("id") or "")),
    )[0]


def _is_intermediary_contact(contact: dict[str, Any]) -> bool:
    role = str(contact.get("role") or "").casefold()
    return "intermediary" in role or "forward" in role


def _forward_to_contact_name(contacts: list[dict[str, Any]], selected: dict[str, Any]) -> str:
    selected_id = str(selected.get("id") or "")
    for contact in contacts:
        if str(contact.get("id") or "") == selected_id:
            continue
        role = str(contact.get("role") or "").casefold()
        if "forward-to" in role or "treasurer" in role:
            name = _clean_text(contact.get("name"))
            if name:
                return name.split()[0]
    return ""


def _recipient_from_contact(contact: dict[str, Any], *, email: str = "", contacts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    recipient = {
        "name": contact.get("name") or "",
        "email": contact.get("email") or email,
        "role": contact.get("role") or "",
    }
    if _is_intermediary_contact(contact):
        forward_to = _forward_to_contact_name(list(contacts or []), contact)
        if forward_to:
            recipient["role"] = "intermediary"
            recipient["forward_to"] = forward_to
    return recipient


def _needs_issued_invoice_pdf(invoice_data: dict[str, Any] | None, attachment: str | None) -> bool:
    data = invoice_data or {}
    status_text = " ".join(
        str(_dict_first(data, "invoice_status", "lifecycle_state", "status") or "").split()
    ).casefold()
    number_text = str(data.get("invoice_number") or "").casefold()
    attachment_name = Path(str(attachment or "")).name.casefold()
    return (
        "draft" in status_text
        or "draft" in number_text
        or "draft" in attachment_name
    )


class RealCockpitOps:
    """Production ops. Instantiate under the agent runtime (env/creds loaded)."""

    def __init__(
        self,
        contact_name: str = "",
        contacts_db_path: str | None = None,
        *,
        origin: OutputOrigin | None = None,
        source_request: str = "",
        output_boundary_context: OutputBoundaryContext | None = None,
    ):
        self.contact_name = contact_name
        self.contacts_db_path = contacts_db_path or os.environ.get("OPENCLAW_CONTACTS_DB_PATH")
        self.origin = origin
        self.output_boundary_context = (
            output_boundary_context
            or OutputBoundaryContext.from_source_request(source_request)
        )
        self._origin_output_sequence = 0

    def _origin_text_output(
        self,
        text: str,
        *,
        purpose: str,
        reply_markup: dict[str, Any] | None = None,
        internal: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.origin is None:
            raise RuntimeError("origin output requested without an origin binding")
        self._origin_output_sequence += 1
        receipt = receipt_pointer(
            "invoice-cockpit",
            self.origin,
            salt=f"{purpose}:{self._origin_output_sequence}",
        )
        output = OriginBoundOutput.guarded_text(
            origin=self.origin,
            delivery_id=receipt,
            receipt_pointer=receipt,
            operator_text=text,
            generic_text=GENERIC_SAFE_FAILURE,
            reply_markup=reply_markup,
            boundary_context=self.output_boundary_context,
            advertise_receipt_lookup=True,
            internal=internal,
        )
        return {"ok": True, "origin_output": output}

    def _origin_document_output(
        self,
        pdf_path: str,
        caption: str,
        *,
        document_sha256: str = "",
    ) -> dict[str, Any]:
        if self.origin is None:
            raise RuntimeError("origin output requested without an origin binding")
        self._origin_output_sequence += 1
        delivery_id = receipt_pointer(
            "invoice-cockpit",
            self.origin,
            salt=f"document:{self._origin_output_sequence}",
        )
        digest = str(document_sha256 or "").strip().casefold()
        provider_receipt = (
            f"invoice-artifact-{digest}"
            if digest
            else delivery_id
        )
        internal = {"document_path": str(pdf_path or "")}
        if digest:
            internal["document_sha256"] = digest
        output = OriginBoundOutput.guarded_document(
            origin=self.origin,
            delivery_id=delivery_id,
            receipt_pointer=provider_receipt,
            document_path=pdf_path,
            caption=caption,
            generic_text=GENERIC_SAFE_FAILURE,
            boundary_context=self.output_boundary_context,
            advertise_receipt_lookup=True,
            internal=internal,
        )
        return {"ok": True, "origin_output": output}

    def _registry(self):
        from contacts_registry import ContactsRegistry, DEFAULT_CONTACTS_DB_PATH

        return ContactsRegistry(self.contacts_db_path or DEFAULT_CONTACTS_DB_PATH, seed=True)

    def _recipient_for_invoice(self, *, client=None, invoice_data=None) -> dict[str, Any]:
        if _clean_text(self.contact_name):
            return {"name": _clean_text(self.contact_name)}

        data = invoice_data if isinstance(invoice_data, dict) else {}
        registry = self._registry()

        email = str(_dict_first(data, "client_email", "recipient_email", "to_email") or "").strip()

        for slug in _client_slug_candidates(client, data):
            contacts = registry.get_contacts_for_client(slug)
            contact = _select_contact_for_client(contacts, invoice_data=data)
            if contact:
                return _recipient_from_contact(contact, email=email, contacts=contacts)

        if email and "@" in email:
            contact = registry.get_contact(email)
            if contact:
                return _recipient_from_contact(contact, email=email)
        return {"name": "", "email": email}

    def _issued_invoice_payload(
        self, invoice_data: dict[str, Any] | None, *, stage: str = "finalized"
    ) -> dict[str, Any]:
        data = dict(invoice_data or {})
        # Task 134: "test" stage is a workflow-test-mode REVIEW, not a real issuance -- keep
        # the status distinct so it can never be mistaken for an actual send, and never
        # consume the real invoice-number counter.
        data["invoice_status"] = "issued" if stage == "finalized" else "test_reviewed"
        data["lifecycle_state"] = "issued" if stage == "finalized" else "test_reviewed"
        data["invoice_stage"] = stage
        invoice_number = str(data.get("invoice_number") or "")
        if "draft" in invoice_number.casefold() or not invoice_number.strip():
            import invoice_generator

            invoice_generator.TRACKER_DIR = Path(
                os.environ.get("OPENCLAW_INVOICE_TRACKER_DIR", str(invoice_generator.TRACKER_DIR))
            )
            data["invoice_number"] = invoice_generator.get_next_invoice_number(preview=(stage != "finalized"))
        return data

    def _finalized_real_attachment(
        self,
        *,
        attachment: str,
        attachment_sha256: str,
        invoice_data: dict[str, Any] | None,
        stage: str = "finalized",
    ) -> tuple[dict[str, Any], str, str]:
        issued_data = self._issued_invoice_payload(invoice_data, stage=stage)
        # "test" stage always regenerates so the TEST watermark + draft scrub apply -- never
        # trust a pre-existing attachment (e.g. a real Mac-Codex receipt PDF) for that stage.
        if stage == "finalized" and not _needs_issued_invoice_pdf(invoice_data, attachment):
            return issued_data, attachment, attachment_sha256

        import invoice_generator

        invoice_generator.INVOICES_DIR = Path(os.environ.get("OPENCLAW_INVOICES_DIR", str(invoice_generator.INVOICES_DIR)))
        invoice_generator.TRACKER_DIR = Path(
            os.environ.get("OPENCLAW_INVOICE_TRACKER_DIR", str(invoice_generator.TRACKER_DIR))
        )
        pdf = invoice_generator.generate_invoice_pdf(issued_data)
        issued_data["attachment_filename"] = Path(pdf).name
        digest = hashlib.sha256(Path(pdf).read_bytes()).hexdigest()
        os.environ["OPENCLAW_ATTACHMENT_ALLOWED_DIRS"] = str(Path(pdf).parent)
        return issued_data, str(pdf), digest

    def finalized_review_attachment(
        self,
        *,
        attachment: str,
        attachment_sha256: str,
        invoice_data: dict[str, Any] | None,
        stage: str = "finalized",
    ) -> tuple[dict[str, Any], str, str]:
        return self._finalized_real_attachment(
            attachment=attachment,
            attachment_sha256=attachment_sha256,
            invoice_data=invoice_data if isinstance(invoice_data, dict) else {},
            stage=stage,
        )

    def prepare_existing_finalized_invoice(
        self,
        client: Any,
        *,
        requested_period: str | None = None,
    ) -> tuple[dict[str, Any], str, str]:
        """Surface the newest matching finalized artifact, read-only.

        This is intentionally separate from :meth:`prepare_invoice`: review
        requests must never hydrate the legacy June receipt, allocate an
        invoice number, regenerate a PDF, draft copy, invoke a broker, or send.
        """

        candidates = _finalized_invoice_candidates(client, requested_period=requested_period)
        if not candidates:
            display = _clean_text(
                _dict_first(client, "display_name", "client_name", "client_ref")
                if isinstance(client, dict)
                else client
            ) or "requested client"
            raise FileNotFoundError(f"no finalized invoice artifact found for {display}")
        year, sequence, pdf, issue_date = candidates[0]
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        display_name = _clean_text(
            _dict_first(client, "display_name", "client_name", "client_display_name", "client_ref")
            if isinstance(client, dict)
            else client
        )
        data = {
            "invoice_number": f"WL-{year:04d}-{sequence:04d}",
            "client_name": display_name or pdf.stem.split("__", 1)[-1].replace("_", " "),
            "client_ref": (
                str(_dict_first(client, "client_ref", "slug") or "")
                if isinstance(client, dict)
                else _client_slug(str(client or ""))
            ),
            "invoice_status": "issued",
            "lifecycle_state": "issued",
            "invoice_stage": "existing_finalized_artifact",
            "requested_period": requested_period,
            "issue_date": issue_date,
            "attachment_filename": pdf.name,
            "rendered_pdf_path": str(pdf),
            "source": "existing_finalized_artifact",
        }
        return data, str(pdf), digest

    # -- invoice preparation: real Codex-Mac receipt first, fallback generator second --
    def prepare_invoice(self, client: str):
        real_invoice = _load_real_invoice_receipt(client)
        if real_invoice is not None:
            data, pdf = real_invoice
            data["attachment_filename"] = pdf.name
            digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
            os.environ["OPENCLAW_ATTACHMENT_ALLOWED_DIRS"] = str(pdf.parent)
            return data, str(pdf), digest

        os.environ.setdefault("OPENCLAW_INVOICES_DIR", "/home/openclaw/state/invoices")
        import invoice_generator
        invoice_generator.INVOICES_DIR = Path(os.environ["OPENCLAW_INVOICES_DIR"])
        invoice_generator.TRACKER_DIR = Path(
            os.environ.get("OPENCLAW_INVOICE_TRACKER_DIR", str(invoice_generator.TRACKER_DIR))
        )
        data = invoice_generator.build_st_annes_invoice_data()  # St Anne's fallback; other clients extend later
        data["invoice_number"] = invoice_generator.get_next_invoice_number()
        pdf = invoice_generator.generate_invoice_pdf(data)
        data["attachment_filename"] = Path(pdf).name
        digest = hashlib.sha256(Path(pdf).read_bytes()).hexdigest()
        os.environ["OPENCLAW_ATTACHMENT_ALLOWED_DIRS"] = str(Path(pdf).parent)
        return data, str(pdf), digest

    def telegram_pdf(self, pdf_path: str, caption: str):
        if self.origin is not None:
            return self._origin_document_output(pdf_path, caption)
        return {"ok": False, "error": "origin binding required for Telegram document output"}

    def telegram_pdf_verified(self, pdf_path: str, caption: str, document_sha256: str):
        """Stage a document with immutable identity bound for adapter recheck."""

        if self.origin is not None:
            return self._origin_document_output(
                pdf_path,
                caption,
                document_sha256=document_sha256,
            )
        return {"ok": False, "error": "origin binding required for Telegram document output"}

    def telegram_message(self, text: str):
        if self.origin is not None:
            return self._origin_text_output(text, purpose="message")
        return {"ok": False, "error": "origin binding required for Telegram text output"}

    def clara_draft_and_guardian(self, client, invoice_data, pdf_path):
        try:
            from clara_invoice_email_draft_package import build_general_client_invoice_body
            recipient = self._recipient_for_invoice(client=client, invoice_data=invoice_data)
            body = build_general_client_invoice_body(invoice_data, recipient)
            msg = ("Clara's draft to " + str((invoice_data or {}).get("client_email") or "the client") +
                   ":\n\n" + body + "\n\n— Review the body above; the send stays behind the cockpit approval gate.")
            return self.telegram_message(msg)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def guardian_approval_board(self, approval: dict[str, Any]):
        if self.origin is not None:
            try:
                from guardian_approval_board import _buttons
                from guardian_approval_humanizer import humanize_approval, render_operator_message

                human = humanize_approval(approval)
                text = render_operator_message(human)
                approval_id = str(approval.get("id") or approval.get("approval_id") or "")
                buttons = _buttons(approval_id, kind=human.get("kind", "generic"))
                return self._origin_text_output(
                    text,
                    purpose="guardian_approval",
                    reply_markup=buttons,
                    internal={"approval": dict(approval)},
                )
            except Exception as exc:
                return {"ok": False, "error": str(exc)}
        return {"ok": False, "error": "origin binding required for Guardian approval output"}

    def apply_edit(self, invoice_data, instruction):
        try:
            os.environ.setdefault("OPENCLAW_INVOICES_DIR", "/home/openclaw/state/invoices")
            import invoice_generator
            from invoice_line_edit import apply_invoice_edit

            invoice_generator.INVOICES_DIR = Path(os.environ["OPENCLAW_INVOICES_DIR"])
            invoice_generator.TRACKER_DIR = Path(
                os.environ.get("OPENCLAW_INVOICE_TRACKER_DIR", str(invoice_generator.TRACKER_DIR))
            )
            edited = apply_invoice_edit(invoice_data or {}, instruction)
            edit_meta = edited.get("invoice_edit") or {}
            if edit_meta.get("status") != "applied":
                return {
                    "ok": True,
                    "changed": False,
                    "invoice_data": invoice_data,
                    "note": edit_meta.get("note") or "Couldn't parse that invoice edit.",
                }
            pdf = invoice_generator.generate_invoice_pdf(edited)
            edited["attachment_filename"] = Path(pdf).name
            digest = hashlib.sha256(Path(pdf).read_bytes()).hexdigest()
            os.environ["OPENCLAW_ATTACHMENT_ALLOWED_DIRS"] = str(Path(pdf).parent)
            return {
                "ok": True,
                "changed": True,
                "invoice_data": edited,
                "pdf_path": str(pdf),
                "attachment_sha256": digest,
                "edit": edit_meta,
            }
        except Exception as exc:
            return {"ok": False, "changed": False, "error": str(exc)}

    def send_email(self, *, to, attachment, attachment_sha256, invoice_data, mode):
        try:
            import global_run_mode_context as grmc
            import google_access_broker as broker
            from clara_invoice_email_draft_package import build_general_client_invoice_body
            if mode == "test":
                # Task 134: test-mode sends are recipient-locked but must still show the
                # operator the TRUE final copy -- finalized rendering (no "draft" wording)
                # with a TEST watermark, previewing the number without consuming the real
                # counter.
                issued_data, issued_attachment, issued_digest = self._finalized_real_attachment(
                    attachment=attachment,
                    attachment_sha256=attachment_sha256,
                    invoice_data=invoice_data if isinstance(invoice_data, dict) else {},
                    stage="test",
                )
                recipient = self._recipient_for_invoice(invoice_data=issued_data)
                subject = f"Invoice — {issued_data.get('client_name','')}".strip()
                body = build_general_client_invoice_body(issued_data, recipient)
                params = {"to": to, "subject": subject, "body": body,
                          "attachments": [issued_attachment], "attachment_sha256": [issued_digest]}
                grmc.handle_run_mode_set_request(grmc.DEFAULT_SQLITE_PATH, {
                    "requested_run_mode": "test_live", "allowlisted_recipients": [grmc.ALLOWLISTED_TEST_EMAIL],
                    "test_execution_authority": {"schema_version": grmc.TEST_EXECUTION_AUTHORITY_SCHEMA,
                        "verifier_status": "VERIFIED_TEST_AUTHORITY", "live_external_effects_allowed": True}})
                try:
                    res = broker.call("cassandra", "google.gmail.send", params)
                finally:
                    grmc.handle_run_mode_set_request(grmc.DEFAULT_SQLITE_PATH, {"requested_run_mode": "production"})
                if isinstance(invoice_data, dict) and isinstance(res, dict) and res.get("ok") is not False:
                    invoice_data.update(issued_data)
                return res
            # REAL: refuse while SEND_HOLD is active — the operator lifts it deliberately to go live.
            from email_send_executor import DEFAULT_SEND_HOLD_PATH
            if Path(os.environ.get("OPENCLAW_SEND_HOLD_PATH") or DEFAULT_SEND_HOLD_PATH).is_file():
                return {"ok": False, "error": "SEND_HOLD is active — lift it to send this to the client for real."}
            issued_data, issued_attachment, issued_digest = self._finalized_real_attachment(
                attachment=attachment,
                attachment_sha256=attachment_sha256,
                invoice_data=invoice_data if isinstance(invoice_data, dict) else {},
            )
            recipient = self._recipient_for_invoice(invoice_data=issued_data)
            subject = f"Invoice — {issued_data.get('client_name','')}".strip()
            body = build_general_client_invoice_body(issued_data, recipient)
            params = {"to": to, "subject": subject, "body": body,
                      "attachments": [issued_attachment], "attachment_sha256": [issued_digest]}
            res = broker.call("cassandra", "google.gmail.send", params)
            if isinstance(invoice_data, dict) and isinstance(res, dict) and res.get("ok") is not False:
                invoice_data.update(issued_data)
            return res
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


__all__ = [
    "DEFAULT_REAL_INVOICE_INCOMING_DIR",
    "DEFAULT_SESSION_PATH",
    "JsonSessionStore",
    "REAL_INVOICE_SCHEMA_VERSION",
    "RealCockpitOps",
]
