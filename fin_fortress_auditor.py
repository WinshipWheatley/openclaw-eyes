"""Fail-safe Financial Fortress auditor surface for Chief router imports.

This module intentionally does not provide tax advice, deduction conclusions,
external calls, file writes, or business-system mutations. It keeps the router
importable in clean checkouts and returns a manual-review response.
"""

from __future__ import annotations


def handle(text: str = "") -> list[str]:
    """Return a safe manual-review response for financial audit requests."""

    return [
        "I can stage a local financial review queue, but I cannot give tax advice or claim deductions.",
        "Treat any classification as candidate-only until you review it with a qualified professional.",
    ]
