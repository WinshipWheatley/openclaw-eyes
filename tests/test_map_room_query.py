import sqlite3

import pytest
from map_room_query import lookup_file_territory, map_room_query_status, query_map_room


def _registry_db(tmp_path):
    db_path = tmp_path / "registry.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        create table system_component (
            component_id text primary key,
            display_name text not null,
            component_type text not null,
            evidence_status text not null,
            evidence_paths_json text not null,
            summary text not null,
            authority_boundary text not null
        );
        create table capability (
            capability_id text primary key,
            component_id text not null,
            capability_name text not null,
            evidence_status text not null,
            evidence_basis text not null,
            boundary text not null
        );
        create table known_unknown (
            unknown_id text primary key,
            subject text not null,
            unknown_status text not null,
            reason text not null,
            next_safe_check text not null
        );
        """
    )
    conn.execute(
        "insert into system_component values (?,?,?,?,?,?,?)",
        (
            "cassandra",
            "Cassandra",
            "operator_agent",
            "CONFIRMED_LOCAL",
            '["cassandra_listener.py"]',
            "Operator communications and guided review.",
            "No send without gates.",
        ),
    )
    conn.execute(
        "insert into capability values (?,?,?,?,?,?)",
        (
            "cap_map_room_query",
            "cassandra",
            "Map Room Query",
            "CONFIRMED_LOCAL",
            "tests fixture",
            "read-only",
        ),
    )
    conn.execute(
        "insert into known_unknown values (?,?,?,?,?)",
        (
            "unknown_live_ledger_shape",
            "Business ledger shape",
            "EXPECTED_TABLES_MISSING",
            "The live ledger table coverage is incomplete in this fixture.",
            "Check the live registry read-only.",
        ),
    )
    conn.commit()
    conn.close()
    return db_path


def test_query_map_room_components_from_tmp_sqlite_registry(tmp_path):
    answer = query_map_room("what components exist?", sqlite_path=_registry_db(tmp_path))

    assert answer["status"] == "ok"
    assert answer["answer_type"] == "components"
    assert answer["authority_boundary"]["read_only"] is True
    assert answer["authority_boundary"]["runtime_mutation"] is False
    assert answer["items"] == [
        {
            "component_id": "cassandra",
            "display_name": "Cassandra",
            "component_type": "operator_agent",
            "evidence_status": "CONFIRMED_LOCAL",
            "summary": "Operator communications and guided review.",
            "authority_boundary": "No send without gates.",
        }
    ]


def test_query_map_room_known_unknowns_from_tmp_sqlite_registry(tmp_path):
    answer = query_map_room("what known unknowns are recorded?", sqlite_path=_registry_db(tmp_path))

    assert answer["status"] == "ok"
    assert answer["answer_type"] == "known_unknowns"
    assert answer["items"][0]["unknown_id"] == "unknown_live_ledger_shape"
    assert "incomplete" in answer["items"][0]["reason"]


def test_query_map_room_missing_or_empty_registry_fails_closed(tmp_path):
    empty_db = tmp_path / "empty.sqlite"
    sqlite3.connect(empty_db).close()

    answer = query_map_room("what components exist?", sqlite_path=empty_db)

    assert answer["status"] == "unavailable"
    assert answer["items"] == []
    assert "unavailable" in answer["summary"].lower()

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
