from __future__ import annotations

from types import SimpleNamespace

from scripts import probe_semantic_vote_contract as probe


class _Receipt:
    def to_dict(self):
        return {
            "source": "semantic_vote",
            "label": "unresolved",
            "action": "pass_through",
            "reason": "uncertain_outside_session_fail_open",
            "semantic_vote_status": "error:TimeoutError",
        }


def test_probe_reports_contract_and_child_cleanup(monkeypatch):
    calls = []

    def fake_decide(text, **kwargs):
        calls.append((text, kwargs))
        return SimpleNamespace(
            label=SimpleNamespace(value="unresolved"),
            action=SimpleNamespace(value="pass_through"),
            receipt=_Receipt(),
        )

    child_sets = iter(
        [
            (),
            (SimpleNamespace(name="unrelated-child", pid=77),),
        ]
    )
    clocks = iter((10.0, 17.8))
    monkeypatch.setattr(
        probe,
        "clarification_for_vote_failure",
        lambda _decision: "The language model timed out honestly.",
    )
    monkeypatch.setattr(
        probe,
        "classify_vote_failure_kind",
        lambda _decision: SimpleNamespace(value="timeout"),
    )

    result = probe.run_probe(
        decide_fn=fake_decide,
        active_children_fn=lambda: next(child_sets),
        monotonic_fn=lambda: next(clocks),
    )

    assert result["passed"] is True
    assert result["model"] == "qwen3:8b-q4_K_M"
    assert result["num_ctx"] == 1024
    assert result["num_gpu"] == 999
    assert result["timeout_seconds"] == 8.0
    assert result["keep_alive"] == "10m"
    assert result["elapsed_seconds"] == 7.8
    assert result["remaining_vote_children"] == []
    assert result["failure_kind"] == "timeout"
    assert result["clarification"] == "The language model timed out honestly."
    assert calls[0][1]["semantic_vote_enabled"] is True
    assert calls[0][1]["semantic_timeout_seconds"] == 8.0


def test_probe_fails_when_semantic_vote_child_survives():
    def fake_decide(_text, **_kwargs):
        return SimpleNamespace(
            label=SimpleNamespace(value="status"),
            action=SimpleNamespace(value="direct_answer"),
            receipt=SimpleNamespace(
                to_dict=lambda: {"semantic_vote_status": "accepted"}
            ),
        )

    child_sets = iter(
        [
            (),
            (SimpleNamespace(name="contract-semantic-vote", pid=88),),
        ]
    )
    clocks = iter((10.0, 10.4))

    result = probe.run_probe(
        decide_fn=fake_decide,
        active_children_fn=lambda: next(child_sets),
        monotonic_fn=lambda: next(clocks),
    )

    assert result["passed"] is False
    assert result["remaining_vote_children"] == [88]
