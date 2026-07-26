"""When the packet does not cover the target, go learn it -- carefully.

Operator: "this thing is connected to the internet, if it does not know what
th-u is, then look it up, extract the dank af nectar."

Two hard rules:
  * only the unknown TERM is searched, never the raw assignment -- an
    assignment can carry client names, amounts and private context.
  * anything learned is marked web-sourced with its URL and retrieval time,
    never blended in as if it were the operator's own data.
"""

from __future__ import annotations

from typing import Any

import gap_research


def test_only_the_unknown_term_is_searched_never_the_assignment() -> None:
    seen: list[str] = []

    def fake_search(query: str, max_results: int = 4) -> list[dict[str, Any]]:
        seen.append(query)
        return [{"title": "TH-U", "body": "TH-U is a guitar amp simulator plugin.", "url": "https://x"}]

    gap_research.research_gap(
        target="prepare the LAMD invoice for Megan Rivas and explain TH-U",
        uncovered_terms=("thu",),
        search=fake_search,
    )

    joined = " ".join(seen).lower()
    assert "megan" not in joined
    assert "lamd" not in joined
    assert "invoice" not in joined


def test_learned_fact_carries_web_provenance_and_url() -> None:
    def fake_search(query: str, max_results: int = 4) -> list[dict[str, Any]]:
        return [
            {
                "title": "TH-U by Overloud",
                "body": "TH-U is a guitar amp and cabinet simulator plugin (AU/VST/AAX).",
                "url": "https://overloud.com/th-u",
            }
        ]

    fact = gap_research.research_gap(
        target="explain TH-U", uncovered_terms=("thu",), search=fake_search
    )

    assert fact is not None
    assert fact["provenance"] == "web_lookup"
    assert "overloud.com" in fact["source_ref"]
    assert "simulator" in fact["value"].lower()
    assert fact["freshness"]["retrieved_at"]


def test_no_results_returns_nothing_rather_than_inventing() -> None:
    assert (
        gap_research.research_gap(
            target="explain TH-U",
            uncovered_terms=("thu",),
            search=lambda q, max_results=4: [],
        )
        is None
    )


def test_search_failure_is_not_fatal() -> None:
    def boom(query: str, max_results: int = 4):
        raise RuntimeError("network down")

    assert (
        gap_research.research_gap(
            target="explain TH-U", uncovered_terms=("thu",), search=boom
        )
        is None
    )


def test_private_looking_terms_are_never_searched() -> None:
    seen: list[str] = []

    def fake_search(query: str, max_results: int = 4):
        seen.append(query)
        return []

    gap_research.research_gap(
        target="pay winshiplive@gmail.com $2000",
        uncovered_terms=("winshiplive@gmail.com", "2000"),
        search=fake_search,
    )

    assert seen == [], "contact details and amounts must never reach a search engine"
