"""Retired legacy invoice brain tombstone.

This module used to run a polling loop that wrote invoice files and called the
legacy sender directly. That path is retired because invoice authority now flows
through the gated billing/invoice executor stack.
"""

from __future__ import annotations


RETIRED = True
DISPOSITION = "retired"
RETIREMENT_REASON = (
    "chief_invoice_brain.py was an orphaned legacy poller with direct file and "
    "sender side effects. Invoice work must use the gated billing/invoice "
    "executor path instead."
)
SUPERSEDED_BY = (
    "chief_billing_brain.py",
    "invoice_send_executor.py",
    "chief_compose.py",
)


def status() -> dict[str, object]:
    """Return machine-readable retirement metadata for inventory checks."""
    return {
        "retired": RETIRED,
        "disposition": DISPOSITION,
        "reason": RETIREMENT_REASON,
        "superseded_by": list(SUPERSEDED_BY),
        "send_performed": False,
        "polling_loop_active": False,
    }


def handle(_text: str) -> list[str]:
    """Fail closed if a stale caller reaches the retired brain."""
    return [
        "chief_invoice_brain.py is retired. Use the gated billing/invoice executor path."
    ]


def get_questions(_mode: str | None = None) -> list[tuple[str, str]]:
    """Legacy compatibility shim; invoice questions live in chief_billing_brain."""
    return []


def main() -> int:
    print(handle("")[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
