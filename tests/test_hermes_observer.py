from __future__ import annotations

import sys
from types import SimpleNamespace


def test_brain_quality_observer_preserves_class_scope_fields(monkeypatch) -> None:
    import hermes_observer

    monkeypatch.setitem(
        sys.modules,
        "self_monitor",
        SimpleNamespace(
            self_check=lambda: [
                {
                    "id": "frontdoor_empty_answer",
                    "problem": "front-door model returned empty answers",
                    "fix_goal": "Fix the frontdoor_empty_answer class across Cassandra and Maestro.",
                    "evidence": "cassandra receipt; maestro receipt",
                    "failure_class": "frontdoor_empty_answer",
                    "class_scope": "class",
                    "sibling_evidence": [
                        {"agent_id": "cassandra", "receipt_ref": "receipt:cassandra"},
                        {"agent_id": "maestro", "receipt_ref": "receipt:maestro"},
                    ],
                }
            ]
        ),
    )

    [suggestion] = hermes_observer._brain_quality_observer()

    assert suggestion["failure_class"] == "frontdoor_empty_answer"
    assert suggestion["class_scope"] == "class"
    assert {item["agent_id"] for item in suggestion["sibling_evidence"]} == {"cassandra", "maestro"}
