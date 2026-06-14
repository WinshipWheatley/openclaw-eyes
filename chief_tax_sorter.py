"""Fail-safe local tax sorter surface for Chief router imports.

This module intentionally does not provide tax advice, call external services,
or mutate files. It gives Chief a stable import target and returns a local-only
manual-review response when the tax sorter lane is invoked.
"""

from __future__ import annotations


def handle(text: str = "") -> list[str]:
    """Return a safe manual-review response for tax-sorter requests."""

    return [
        "I can stage a local transaction classification review, but I cannot give tax advice.",
        "Use this as a manual review queue only; confirm classifications with a qualified professional.",
    ]


def get_vault_report() -> str:
    """Return a non-authoritative report body for Mac-side review surfaces."""

    return (
        "# Tax Classification Review\n\n"
        "No tax advice is provided. This is a placeholder for manual review notes only.\n"
    )
