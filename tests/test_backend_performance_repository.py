import pytest
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_sqlite_repository import (
    PerformanceSession,
    Setlist,
    SetlistItem,
    SongCue,
    SectionCue,
    PerformanceActionReceipt,
    ManualOverrideEvent,
    HighlightMarker,
    write_performance_session,
    read_performance_session,
    read_performance_sessions_by_tenant_id,
    read_performance_sessions_by_status,
    write_setlist,
    read_setlist,
    read_setlists_by_performance_session_id,
    write_setlist_item,
    read_setlist_item,
    read_setlist_items_by_setlist_id,
    write_song_cue,
    read_song_cue,
    read_song_cues_by_setlist_item_id,
    write_section_cue,
    read_section_cue,
    read_section_cues_by_song_cue_id,
    write_performance_action_receipt,
    read_performance_action_receipt,
    read_performance_action_receipts_by_performance_session_id,
    write_manual_override_event,
    read_manual_override_event,
    read_manual_override_events_by_performance_session_id,
    write_highlight_marker,
    read_highlight_marker,
    read_highlight_markers_by_performance_session_id,
)
from backend_sqlite_schema import sqlite_physical_schema_sql_definitions

def create_in_memory_connection() -> Any:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    for sql in sqlite_physical_schema_sql_definitions():
        connection.execute(sql)
    return connection

def sample_performance_session(session_id: str = "session-1", tenant_id: str = "tenant-1") -> PerformanceSession:
    return PerformanceSession(
        performance_session_id=session_id,
        tenant_id=tenant_id,
        session_name="Test Session",
        session_type="live_show",
        planned_start="2026-05-06T20:00:00Z",
        actual_start="",
        actual_end="",
        status="planned",
        operator_approval_ref="receipt-1",
        source_context_ref="context-1",
        runtime_context_ref="runtime-1",
        created_at="2026-05-06T12:00:00Z",
    )

def sample_setlist(setlist_id: str = "setlist-1", session_id: str = "session-1", tenant_id: str = "tenant-1") -> Setlist:
    return Setlist(
        setlist_id=setlist_id,
        tenant_id=tenant_id,
        performance_session_id=session_id,
        setlist_name="Test Setlist",
        status="active",
        created_at="2026-05-06T12:00:00Z",
    )

def sample_setlist_item(item_id: str = "item-1", setlist_id: str = "setlist-1", tenant_id: str = "tenant-1") -> SetlistItem:
    return SetlistItem(
        setlist_item_id=item_id,
        tenant_id=tenant_id,
        setlist_id=setlist_id,
        item_order=1,
        item_type="song",
        title="Test Song",
        semantic_record_id="record-1",
        status="planned",
    )

def sample_song_cue(cue_id: str = "cue-1", item_id: str = "item-1", tenant_id: str = "tenant-1") -> SongCue:
    return SongCue(
        song_cue_id=cue_id,
        tenant_id=tenant_id,
        setlist_item_id=item_id,
        cue_name="Intro",
        cue_type="intro",
        cue_order=1,
        expected_tempo="120",
        status="planned",
    )

def sample_section_cue(section_id: str = "section-1", cue_id: str = "cue-1", tenant_id: str = "tenant-1") -> SectionCue:
    return SectionCue(
        section_cue_id=section_id,
        tenant_id=tenant_id,
        song_cue_id=cue_id,
        section_name="Drums Only",
        section_type="vamp",
        section_order=1,
        expected_duration=30,
        safe_baseline_scene_ref="scene-1",
        status="planned",
    )

def sample_performance_action_receipt(receipt_id: str = "receipt-1", session_id: str = "session-1", tenant_id: str = "tenant-1") -> PerformanceActionReceipt:
    return PerformanceActionReceipt(
        performance_action_receipt_id=receipt_id,
        tenant_id=tenant_id,
        performance_session_id=session_id,
        action_type="cue_trigger",
        action_target="lighting",
        action_tier="visual_safe",
        requested_by="system",
        approved_by="operator",
        status="executed",
        receipt_payload="{}",
        created_at="2026-05-06T20:05:00Z",
    )

def sample_manual_override_event(event_id: str = "event-1", session_id: str = "session-1", tenant_id: str = "tenant-1") -> ManualOverrideEvent:
    return ManualOverrideEvent(
        manual_override_event_id=event_id,
        tenant_id=tenant_id,
        performance_session_id=session_id,
        override_type="manual_override",
        override_reason="vamp extended",
        affected_target="lighting",
        status="logged",
        created_at="2026-05-06T20:10:00Z",
    )

def sample_highlight_marker(marker_id: str = "marker-1", session_id: str = "session-1", item_id: str = "item-1", tenant_id: str = "tenant-1") -> HighlightMarker:
    return HighlightMarker(
        highlight_marker_id=marker_id,
        tenant_id=tenant_id,
        performance_session_id=session_id,
        setlist_item_id=item_id,
        marker_time="00:15:30",
        marker_label="Great Solo",
        marker_source="operator",
        notes="Double time here next time",
        status="logged",
    )

def test_performance_session_write_read():
    connection = create_in_memory_connection()
    try:
        session = sample_performance_session()
        write_performance_session(connection, session)

        read_back = read_performance_session(connection, session.performance_session_id)
        assert read_back is not None
        assert read_back["session_name"] == "Test Session"
        assert read_back["tenant_id"] == "tenant-1"

        sessions = read_performance_sessions_by_tenant_id(connection, "tenant-1")
        assert len(sessions) == 1
        assert sessions[0]["performance_session_id"] == session.performance_session_id

        active_sessions = read_performance_sessions_by_status(connection, "tenant-1", "planned")
        assert len(active_sessions) == 1
    finally:
        connection.close()

def test_performance_sessions_tenant_isolation():
    connection = create_in_memory_connection()
    try:
        write_performance_session(connection, sample_performance_session("s1", "t1"))
        write_performance_session(connection, sample_performance_session("s2", "t2"))

        assert len(read_performance_sessions_by_tenant_id(connection, "t1")) == 1
        assert len(read_performance_sessions_by_tenant_id(connection, "t2")) == 1
    finally:
        connection.close()

def test_setlist_hierarchy_write_read():
    connection = create_in_memory_connection()
    try:
        session = sample_performance_session()
        write_performance_session(connection, session)

        setlist = sample_setlist()
        write_setlist(connection, setlist)

        read_back = read_setlist(connection, setlist.setlist_id)
        assert read_back is not None
        assert read_back["performance_session_id"] == session.performance_session_id

        setlists = read_setlists_by_performance_session_id(connection, session.performance_session_id)
        assert len(setlists) == 1

        item = sample_setlist_item()
        write_setlist_item(connection, item)

        items = read_setlist_items_by_setlist_id(connection, setlist.setlist_id)
        assert len(items) == 1
        assert items[0]["title"] == "Test Song"

        cue = sample_song_cue()
        write_song_cue(connection, cue)

        cues = read_song_cues_by_setlist_item_id(connection, item.setlist_item_id)
        assert len(cues) == 1

        section = sample_section_cue()
        write_section_cue(connection, section)

        sections = read_section_cues_by_song_cue_id(connection, cue.song_cue_id)
        assert len(sections) == 1
    finally:
        connection.close()

def test_ordering_is_deterministic():
    connection = create_in_memory_connection()
    try:
        write_performance_session(connection, sample_performance_session())
        write_setlist(connection, sample_setlist())

        # Items out of order
        write_setlist_item(connection, {**sample_setlist_item("i2").__dict__, "item_order": 2})
        write_setlist_item(connection, {**sample_setlist_item("i1").__dict__, "item_order": 1})

        items = read_setlist_items_by_setlist_id(connection, "setlist-1")
        assert items[0]["item_order"] == 1
        assert items[1]["item_order"] == 2

        # Cues
        write_song_cue(connection, {**sample_song_cue("c2", item_id="i1").__dict__, "cue_order": 2})
        write_song_cue(connection, {**sample_song_cue("c1", item_id="i1").__dict__, "cue_order": 1})

        cues = read_song_cues_by_setlist_item_id(connection, "i1")
        assert cues[0]["cue_order"] == 1
        assert cues[1]["cue_order"] == 2

        # Sections
        write_section_cue(connection, {**sample_section_cue("sc2", cue_id="c1").__dict__, "section_order": 2})
        write_section_cue(connection, {**sample_section_cue("sc1", cue_id="c1").__dict__, "section_order": 1})

        sections = read_section_cues_by_song_cue_id(connection, "c1")
        assert sections[0]["section_order"] == 1
        assert sections[1]["section_order"] == 2
    finally:
        connection.close()

def test_receipts_overrides_markers_write_read():
    connection = create_in_memory_connection()
    try:
        write_performance_session(connection, sample_performance_session())
        write_setlist(connection, sample_setlist())
        write_setlist_item(connection, sample_setlist_item())

        receipt = sample_performance_action_receipt()
        write_performance_action_receipt(connection, receipt)
        assert len(read_performance_action_receipts_by_performance_session_id(connection, "session-1")) == 1

        override = sample_manual_override_event()
        write_manual_override_event(connection, override)
        assert len(read_manual_override_events_by_performance_session_id(connection, "session-1")) == 1

        marker = sample_highlight_marker()
        write_highlight_marker(connection, marker)
        assert len(read_highlight_markers_by_performance_session_id(connection, "session-1")) == 1
    finally:
        connection.close()

def test_performance_repository_fails_closed_on_missing_references():
    connection = create_in_memory_connection()
    try:
        # Missing session
        with pytest.raises(ValueError):
            write_setlist(connection, sample_setlist())

        # Missing setlist
        write_performance_session(connection, sample_performance_session())
        with pytest.raises(ValueError):
            write_setlist_item(connection, sample_setlist_item())

        # Missing item
        write_setlist(connection, sample_setlist())
        with pytest.raises(ValueError):
            write_song_cue(connection, sample_song_cue())

        # Missing cue
        write_setlist_item(connection, sample_setlist_item())
        with pytest.raises(ValueError):
            write_section_cue(connection, sample_section_cue())
    finally:
        connection.close()

def test_performance_repository_numeric_validation():
    connection = create_in_memory_connection()
    try:
        write_performance_session(connection, sample_performance_session())
        write_setlist(connection, sample_setlist())

        # Bool instead of int for order
        with pytest.raises(ValueError):
            write_setlist_item(connection, {**sample_setlist_item().__dict__, "item_order": True})

        # String instead of int for duration
        write_setlist_item(connection, sample_setlist_item())
        write_song_cue(connection, sample_song_cue())
        with pytest.raises(ValueError):
            write_section_cue(connection, {**sample_section_cue().__dict__, "expected_duration": "30"})
    finally:
        connection.close()
