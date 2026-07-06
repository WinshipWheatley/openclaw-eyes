from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_hot_swap_failure_rolls_back_and_retains_versions() -> None:
    import versioned_block_registry as blocks

    registry = blocks.new_block_registry()
    blocks.register_block_version(
        registry,
        block_id="packet_compiler",
        version="1.0.0",
        impl_ref="maestro_context_packet.py:build_maestro_context_packet",
        provenance={"source": "task_83_baseline"},
        metrics={"optimization_score": 0.64, "test_pass": True, "perf_ms": 180},
        created_at="2026-07-06T12:00:00+00:00",
    )
    blocks.register_block_version(
        registry,
        block_id="packet_compiler",
        version="2.0.0",
        impl_ref="maestro_context_packet.py:optimized_packet_compiler",
        provenance={"source": "task_84_polish"},
        metrics={"optimization_score": 0.91, "test_pass": True, "perf_ms": 120},
        created_at="2026-07-06T12:05:00+00:00",
    )

    assert blocks.resolve_active_block(registry, "packet_compiler")["version"] == "1.0.0"

    result = blocks.promote_block_version(
        registry,
        block_id="packet_compiler",
        version="2.0.0",
        health_check=lambda candidate: {
            "passed": False,
            "receipt_id": "pytest:v2_failure",
            "details": f"{candidate['version']} failed post-swap receipt",
        },
        swapped_by="codex-test",
    )

    assert result["status"] == "rolled_back"
    assert result["rolled_back_to"] == "1.0.0"
    assert blocks.resolve_active_block(registry, "packet_compiler")["version"] == "1.0.0"
    assert set(registry["blocks"]["packet_compiler"]["versions"]) == {"1.0.0", "2.0.0"}
    assert registry["blocks"]["packet_compiler"]["versions"]["2.0.0"]["health_status"] == "failed"
    assert [event["event_type"] for event in registry["events"][-3:]] == [
        "promote_active",
        "health_check_failed",
        "rollback_active",
    ]
    assert registry["blocks"]["packet_compiler"]["active_version"] == "1.0.0"
    assert registry["blocks"]["packet_compiler"]["last_known_good_version"] == "1.0.0"


def test_successful_pointer_swap_updates_second_copy_and_surfaces_drift() -> None:
    import versioned_block_registry as blocks

    registry = blocks.new_block_registry()
    blocks.register_block_version(
        registry,
        block_id="domain_intent_router",
        version="1.0.0",
        impl_ref="interpreter_lm.py:baseline_router",
        provenance={"source": "task_79_shared_seam"},
        metrics={"optimization_score": 0.7, "test_pass": True, "perf_ms": 95},
        created_at="2026-07-06T13:00:00+00:00",
    )
    blocks.register_block_copy(
        registry,
        copy_id="record_label.intent_router.copy",
        block_id="domain_intent_router",
        observed_version="1.0.0",
        location_ref="domain_module_registry.py:record_label",
    )
    blocks.register_block_version(
        registry,
        block_id="domain_intent_router",
        version="2.0.0",
        impl_ref="interpreter_lm.py:optimized_shared_router",
        provenance={"source": "task_84_polish"},
        metrics={"optimization_score": 0.93, "test_pass": True, "perf_ms": 61},
        created_at="2026-07-06T13:05:00+00:00",
    )

    swap = blocks.promote_block_version(
        registry,
        block_id="domain_intent_router",
        version="2.0.0",
        health_check=lambda candidate: {"passed": True, "receipt_id": "pytest:v2_pass"},
        swapped_by="codex-test",
    )

    assert swap["status"] == "active"
    assert blocks.resolve_block_for_copy(registry, "record_label.intent_router.copy")["version"] == "2.0.0"
    drift = blocks.block_drift_report(registry, "domain_intent_router")
    assert drift["copy_count"] == 1
    assert drift["copies_on_active_version"] == 0
    assert drift["out_of_date_copies"][0]["copy_id"] == "record_label.intent_router.copy"

    convergence = blocks.converge_block_copies(registry, "domain_intent_router", actor="codex-test")

    assert convergence["swapped_copy_count"] == 1
    assert registry["copies"]["record_label.intent_router.copy"]["observed_version"] == "2.0.0"
    assert blocks.block_drift_report(registry, "domain_intent_router")["copies_on_active_version"] == 1
    assert registry["events"][-1]["event_type"] == "copy_swapped"


def test_block_versions_are_immutable_once_registered() -> None:
    import versioned_block_registry as blocks

    registry = blocks.new_block_registry()
    blocks.register_block_version(
        registry,
        block_id="safe_extractor",
        version="1.0.0",
        impl_ref="context_selection.py:safe_extract",
        provenance={"source": "baseline"},
        metrics={"optimization_score": 0.5, "test_pass": True},
        created_at="2026-07-06T14:00:00+00:00",
    )

    with pytest.raises(ValueError, match="immutable"):
        blocks.register_block_version(
            registry,
            block_id="safe_extractor",
            version="1.0.0",
            impl_ref="context_selection.py:changed_impl",
            provenance={"source": "rewrite_attempt"},
            metrics={"optimization_score": 0.99, "test_pass": True},
            created_at="2026-07-06T14:01:00+00:00",
        )
