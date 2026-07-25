"""Tests for the read-model demand index (progressive disclosure).

The index is the small always-loaded layer; the read-models themselves stay lazy.
"""

from __future__ import annotations

import json
from pathlib import Path

import read_model_demand_index as demand_index


def _write_read_model(root: Path, name: str, payload: dict) -> Path:
    path = root / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_index_has_one_row_per_json_read_model_with_key_fields(tmp_path: Path) -> None:
    root = tmp_path / "read_models"
    root.mkdir()
    _write_read_model(
        root,
        "capital_hilton_invoice_status.json",
        {"invoice_number": "2026-1006", "amount_due": 2000, "as_of": "2026-07-20"},
    )
    _write_read_model(root, "niles_track_registry.json", {"tracks": []})

    rows = demand_index.build_demand_index(root, repo_root=tmp_path)

    by_id = {row.id: row for row in rows}
    assert set(by_id) == {"capital_hilton_invoice_status", "niles_track_registry"}
    hilton = by_id["capital_hilton_invoice_status"]
    assert hilton.key_fields == ("amount_due", "as_of", "invoice_number")
    assert hilton.relative_path == "capital_hilton_invoice_status.json"
    assert hilton.size_bytes > 0


def test_selection_returns_only_relevant_rows_not_the_whole_library(
    tmp_path: Path,
) -> None:
    root = tmp_path / "read_models"
    root.mkdir()
    _write_read_model(
        root,
        "capital_hilton_invoice_status.json",
        {"invoice_number": "2026-1006", "amount_due": 2000},
    )
    _write_read_model(root, "niles_track_registry.json", {"tracks": []})
    _write_read_model(root, "agent_presence.json", {"agents": []})
    rows = demand_index.build_demand_index(root, repo_root=tmp_path)

    selected = demand_index.select_read_models(rows, "what is the hilton invoice amount")

    assert [row.id for row in selected] == ["capital_hilton_invoice_status"]


def test_selection_returns_nothing_rather_than_guessing_when_unrelated(
    tmp_path: Path,
) -> None:
    root = tmp_path / "read_models"
    root.mkdir()
    _write_read_model(root, "niles_track_registry.json", {"tracks": []})
    rows = demand_index.build_demand_index(root, repo_root=tmp_path)

    assert demand_index.select_read_models(rows, "weather in paris tomorrow") == ()


def test_selection_respects_a_byte_budget_so_packets_are_not_bloated(
    tmp_path: Path,
) -> None:
    root = tmp_path / "read_models"
    root.mkdir()
    _write_read_model(
        root, "invoice_small.json", {"invoice": "a", "amount": 1}
    )
    _write_read_model(
        root, "invoice_huge.json", {"invoice": "b", "filler": "x" * 5000}
    )
    rows = demand_index.build_demand_index(root, repo_root=tmp_path)

    selected = demand_index.select_read_models(rows, "invoice", max_bytes=1000)

    assert [row.id for row in selected] == ["invoice_small"]
    assert sum(row.size_bytes for row in selected) <= 1000


def test_index_artifacts_are_not_themselves_indexed(tmp_path: Path) -> None:
    root = tmp_path / "read_models"
    root.mkdir()
    _write_read_model(root, "niles_track_registry.json", {"tracks": []})
    _write_read_model(root, "_INDEX.json", {"rows": []})

    rows = demand_index.build_demand_index(root, repo_root=tmp_path)

    assert [row.id for row in rows] == ["niles_track_registry"]


def test_index_is_cached_so_packet_builds_do_not_rescan_the_library(
    tmp_path: Path,
) -> None:
    root = tmp_path / "read_models"
    root.mkdir()
    _write_read_model(root, "niles_track_registry.json", {"tracks": []})

    first = demand_index.build_demand_index(root, repo_root=tmp_path)
    second = demand_index.build_demand_index(root, repo_root=tmp_path)

    assert first is second


def test_cache_invalidates_when_a_read_model_is_added(tmp_path: Path) -> None:
    root = tmp_path / "read_models"
    root.mkdir()
    _write_read_model(root, "niles_track_registry.json", {"tracks": []})
    first = demand_index.build_demand_index(root, repo_root=tmp_path)
    assert len(first) == 1

    _write_read_model(root, "agent_presence.json", {"agents": []})
    second = demand_index.build_demand_index(root, repo_root=tmp_path)

    assert len(second) == 2


def test_shared_selector_resolves_nested_relative_roots(
    tmp_path: Path, monkeypatch
) -> None:
    """Every agent gets the resolve fix for free — none can repeat it."""

    root = tmp_path / "generated" / "read_models"
    root.mkdir(parents=True)
    _write_read_model(root, "st_annes_invoice_status.json", {"status": "sent"})
    monkeypatch.chdir(tmp_path)

    selection = demand_index.select_demand_read_models(
        Path("generated/read_models"), question="st annes invoice status"
    )

    assert [row.id for row in selection.rows] == ["st_annes_invoice_status"]
    assert selection.error is None


def test_shared_selector_reports_failure_instead_of_faking_no_match(
    tmp_path: Path,
) -> None:
    selection = demand_index.select_demand_read_models(
        tmp_path / "missing", question="anything at all"
    )

    assert selection.rows == ()
    assert selection.error


def test_shared_selector_skips_already_loaded_read_models(tmp_path: Path) -> None:
    root = tmp_path / "read_models"
    root.mkdir()
    _write_read_model(root, "agent_presence.json", {"agents": []})
    _write_read_model(root, "agent_presence_history.json", {"agents": []})

    selection = demand_index.select_demand_read_models(
        root, question="agent presence", already_loaded={"agent_presence.json"}
    )

    assert [row.id for row in selection.rows] == ["agent_presence_history"]


def test_spine_is_the_small_always_loaded_layer(tmp_path: Path) -> None:
    root = tmp_path / "read_models"
    root.mkdir()
    _write_read_model(
        root,
        "capital_hilton_invoice_status.json",
        {"invoice_number": "x", "amount_due": 1, "as_of": "2026-07-20"},
    )
    rows = demand_index.build_demand_index(root, repo_root=tmp_path)

    spine = demand_index.index_spine(rows)

    assert spine[0]["id"] == "capital_hilton_invoice_status"
    assert "key_fields" not in spine[0]
    assert len(json.dumps(spine)) < len(json.dumps(demand_index.index_rows_json(rows)))
