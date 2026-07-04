from __future__ import annotations
from datetime import datetime, timedelta

def temporal_anchor_text(now: datetime | None = None) -> str:
    """Honest system-clock temporal anchor for EVERY agent packet — resolves relative dates. This is
    the SYSTEM CLOCK, not the ledger, so it never fakes ledger provenance. Local date (operator's days)."""
    now = now or datetime.now()
    d = now.date()
    def _mr(tw: int):  # most recent weekday incl. today; Mon=0..Sun=6
        return d - timedelta(days=(d.weekday() - tw) % 7)
    return (
        "TEMPORAL ANCHOR (source: system clock, NOT the ledger — use ONLY to resolve relative dates):\n"
        f"- Today is {d.isoformat()} ({d.strftime('%A')}).\n"
        f"- Yesterday was {(d - timedelta(days=1)).isoformat()}.\n"
        f"- Most recent weekend: Saturday {_mr(5).isoformat()}, Sunday {_mr(6).isoformat()}.\n"
        f"- Most recent Friday: {_mr(4).isoformat()}; Monday: {_mr(0).isoformat()}.\n"
        "Resolve phrases like 'last weekend', 'last Saturday', 'this past Friday' against these dates."
    )
