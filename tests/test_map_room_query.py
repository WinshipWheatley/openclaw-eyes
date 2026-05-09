import pytest
from map_room_query import lookup_file_territory, map_room_query_status

def test_status_report_read_only():
    status = map_room_query_status()
    assert status["status"] == "active"
    assert status["read_only"] is True
    assert status["cleanup_authority_granted"] is False
    assert status["cassandra_integration"] is False
    assert status["system_walk_enabled"] is False
    assert status["mcp_enabled"] is False
    assert len(status["durable_truth_sources"]) > 0

def test_known_unsafe_surfaces():
    res1 = lookup_file_territory("mac_eyes")
    assert "unsafe to move" in res1.classification_buckets
    assert "active dependency owner" in res1.classification_buckets
    assert res1.move_safety_posture == "unsafe to move"
    assert res1.dependency_posture == "active dependency owner"
    assert res1.cleanup_allowed is False
    assert res1.next_safe_step == "dependency decoupling or manual review"

    res2 = lookup_file_territory("Launchers")
    assert "unsafe to move" in res2.classification_buckets
    assert res2.cleanup_allowed is False

def test_private_root_sensitive_surfaces():
    res1 = lookup_file_territory("OpenClawLegalPrivate")
    assert "unknown/manual review" in res1.classification_buckets
    assert res1.move_safety_posture in ["private-root off-limits", "unknown/manual review"]
    assert res1.manual_review_required is True
    assert res1.cleanup_allowed is False

    res2 = lookup_file_territory("/mnt/c/OpenClaw")
    # In JSON it might be historical_archive_reference, source_authority_reference
    # Let's ensure it doesn't give a "safe candidate"
    assert "safe candidate after validation" not in res2.classification_buckets
    assert res2.cleanup_allowed is False

def test_generated_report_index_candidate_only():
    res1 = lookup_file_territory("reports/mac_watch_index")
    assert "generated-output reference" in res1.classification_buckets
    assert "safe candidate after validation" in res1.classification_buckets
    assert res1.move_safety_posture == "candidate-only after validation"
    assert res1.cleanup_allowed is False
    assert res1.next_safe_step == "await explicit authorization"

    res2 = lookup_file_territory("MAC_WATCH_MARKDOWN_INDEX")
    assert "generated-output reference" in res2.classification_buckets
    assert res2.cleanup_allowed is False

def test_generated_output_plus_active_dependency():
    res = lookup_file_territory("Right now.md")
    assert res.dependency_posture == "generated-output plus active dependency owner"
    assert res.move_safety_posture == "unsafe to move"
    assert res.cleanup_allowed is False

def test_unknown_terms_not_optimistic():
    res = lookup_file_territory("some_random_file_123.py")
    assert "not found" in res.classification_buckets
    assert res.move_safety_posture == "unknown/manual review"
    assert res.manual_review_required is True
    assert res.cleanup_allowed is False
