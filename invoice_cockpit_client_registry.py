"""Shared client registry for invoice cockpit and Clara invoice flows.

Session routing consumes the dictionaries generically. Client-specific policy
belongs here so cockpit glue does not grow name branches.
"""

from __future__ import annotations

from typing import Any


DEFAULT_CLARA_INVOICE_CLIENT_REGISTRY: dict[str, dict[str, Any]] = {
    "capital_hilton": {
        "client_ref": "capital_hilton",
        "client_display_name": "Capital Hilton",
        "display_name": "Capital Hilton",
        "aliases": ("capital hilton", "capitol hilton", "hilton"),
        "send_state": "EXCEL_PATH",
        "supplier_portal_required": True,
        "supplier_portal_provider": "COUPA",
        "dual_path_note": (
            "Capital Hilton can go two ways: Coupa/PO when a PO is present, or Excel when "
            "the workbook path is approved. The 5-gig/$2000 trigger is noted; continuing "
            "on the Excel path."
        ),
    },
    "live_arts_md": {
        "client_ref": "live_arts_md",
        "client_display_name": "Live Arts MD",
        "display_name": "Live Arts MD",
        "aliases": ("live arts", "live arts md", "live arts maryland", "arts alive md"),
        "send_block": True,
        "send_state": "DO_NOT_SEND",
        "refusal_message": (
            "Live Arts MD is blocked - its numbers need reconciliation + payment terms; "
            "not sending."
        ),
    },
    "reynolds_tavern": {
        "client_ref": "reynolds_tavern",
        "client_display_name": "Reynolds Tavern",
        "display_name": "Reynolds Tavern",
        "aliases": ("reynolds", "reynolds tavern"),
        "status": "paid_no_invoice_sent",
        "refusal_message": "Reynolds is already paid; I'll invoice next time you play there.",
    },
    "st_annes": {
        "client_ref": "st_annes",
        "client_display_name": "St. Anne's",
        "display_name": "St. Anne's",
        "aliases": (
            "st annes",
            "st anne",
            "st anne's",
            "st. annes",
            "st. anne's",
            "saint annes",
            "saint anne",
            "church gig",
            "draper",
            "draper carter",
        ),
        "send_state": "NORMAL",
    },
}

DEFAULT_CLIENT_MODELS: tuple[dict[str, Any], ...] = tuple(
    dict(model) for model in DEFAULT_CLARA_INVOICE_CLIENT_REGISTRY.values()
)


__all__ = ["DEFAULT_CLARA_INVOICE_CLIENT_REGISTRY", "DEFAULT_CLIENT_MODELS"]
