"""Tests for the Niles track-registry read-model generator.

Verifies grounding (real CSV source), anti-confabulation gap-flagging,
metadata-only posture, and authority boundary.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import export_niles_track_registry_read_model as registry_mod


FIXED_NOW = "2026-06-22T00:00:00+00:00"

REAL_CSV_CONTENT = """\
track_id,title,status,owner,next_step,est_hours,target_week
T01,Song 01,idea,unknown,unknown,0,TBD
T02,Song 02,idea,unknown,unknown,0,TBD
T03,Song 03,tracking,winship,record_guitar,8,2026-W28
"""


def _write_csv(tmp_path: Path, content: str) -> Path:
    """Write a fake CSV into the expected location under tmp_path."""
    csv_dir = tmp_path / ".openclaw" / "agents" / "chief" / "album"
    csv_dir.mkdir(parents=True, exist_ok=True)
    csv_file = csv_dir / "track-registry.csv"
    csv_file.write_text(content, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# GROUNDING: real CSV source traced with source_ref
# ---------------------------------------------------------------------------

def test_grounding_source_ref_and_schema_version(tmp_path):
    repo_root = _write_csv(tmp_path, REAL_CSV_CONTENT)
    payload = registry_mod.build_niles_track_registry(repo_root=repo_root, generated_at=FIXED_NOW)

    assert payload["schema_version"] == registry_mod.SCHEMA_VERSION
    assert payload["source_id"] == "niles_track_registry"
    assert payload["source_path"] == ".openclaw/agents/chief/album/track-registry.csv"
    assert payload["source_present"] is True
    assert payload["source_ref"] is not None


def test_grounding_tracks_parsed_from_csv(tmp_path):
    repo_root = _write_csv(tmp_path, REAL_CSV_CONTENT)
    payload = registry_mod.build_niles_track_registry(repo_root=repo_root, generated_at=FIXED_NOW)

    assert payload["track_count"] == 3
    assert len(payload["tracks"]) == 3
    tracks_by_id = {t["track_id"]: t for t in payload["tracks"]}
    assert "T01" in tracks_by_id
    assert tracks_by_id["T01"]["title"] == "Song 01"
    assert tracks_by_id["T01"]["status"] == "idea"
    assert tracks_by_id["T03"]["status"] == "tracking"
    assert tracks_by_id["T03"]["next_step"] == "record_guitar"


def test_grounding_status_summary(tmp_path):
    repo_root = _write_csv(tmp_path, REAL_CSV_CONTENT)
    payload = registry_mod.build_niles_track_registry(repo_root=repo_root, generated_at=FIXED_NOW)

    assert payload["status_summary"] == {"idea": 2, "tracking": 1}


def test_grounding_real_live_csv_integration():
    """Integration test: live .openclaw CSV must be present and readable."""
    payload = registry_mod.build_niles_track_registry(generated_at=FIXED_NOW)

    if not payload["source_present"]:
        pytest.skip("Live track-registry CSV not available in this environment.")

    assert payload["track_count"] > 0
    assert payload["schema_version"] == registry_mod.SCHEMA_VERSION
    assert payload["source_path"] == ".openclaw/agents/chief/album/track-registry.csv"
    for track in payload["tracks"]:
        assert track["metadata_only"] is True
        assert track["raw_audio_stored"] is False
        assert track["daw_session_contents_stored"] is False
        assert track["file_opened_or_scanned"] is False
        assert track["album_state_confirmed"] is False


# ---------------------------------------------------------------------------
# ANTI-CONFABULATION: missing source must be flagged, not fabricated
# ---------------------------------------------------------------------------

def test_anti_confabulation_missing_csv_is_flagged_not_fabricated(tmp_path):
    """If CSV is absent, gap is explicitly flagged. No tracks invented."""
    payload = registry_mod.build_niles_track_registry(repo_root=tmp_path, generated_at=FIXED_NOW)

    assert payload["source_present"] is False
    assert payload["track_count"] == 0
    assert payload["tracks"] == []
    assert payload["source_missing_gap"] is not None
    assert "not found" in (payload["source_missing_gap"] or "").lower()
    assert payload["real_track_roster_available"] is False


# ---------------------------------------------------------------------------
# METADATA-ONLY / AUTHORITY BOUNDARY
# ---------------------------------------------------------------------------

def test_metadata_only_posture_on_all_track_rows(tmp_path):
    repo_root = _write_csv(tmp_path, REAL_CSV_CONTENT)
    payload = registry_mod.build_niles_track_registry(repo_root=repo_root, generated_at=FIXED_NOW)

    for track in payload["tracks"]:
        assert track["metadata_only"] is True
        assert track["raw_audio_stored"] is False
        assert track["daw_session_contents_stored"] is False
        assert track["file_opened_or_scanned"] is False
        assert track["album_state_confirmed"] is False


def test_authority_boundary_no_execution_or_send(tmp_path):
    repo_root = _write_csv(tmp_path, REAL_CSV_CONTENT)
    payload = registry_mod.build_niles_track_registry(repo_root=repo_root, generated_at=FIXED_NOW)

    assert payload["raw_audio_ingested"] is False
    assert payload["daw_session_content_ingested"] is False
    assert payload["broad_private_drive_scan_triggered"] is False
    assert payload["runtime_authority_added"] is False
    assert payload["send_or_submit_authority_added"] is False
    assert payload["truth_status"] == "governed_operator_metadata_evidence_not_final_audio_truth"
    assert payload["source_promoted_to_truth"] is False


# ---------------------------------------------------------------------------
# DETERMINISM
# ---------------------------------------------------------------------------

def test_output_is_deterministic(tmp_path):
    repo_root = _write_csv(tmp_path, REAL_CSV_CONTENT)
    first = registry_mod.build_niles_track_registry(repo_root=repo_root, generated_at=FIXED_NOW)
    second = registry_mod.build_niles_track_registry(repo_root=repo_root, generated_at=FIXED_NOW)

    assert registry_mod.stable_json(first) == registry_mod.stable_json(second)


# ---------------------------------------------------------------------------
# WIRING: track_registry_posture in niles_album_review_packet
# ---------------------------------------------------------------------------

def test_track_registry_wired_into_review_packet(tmp_path):
    """Track posture must surface in the review packet when registry is present."""
    import niles_album_review_packet as rp

    repo_root = _write_csv(tmp_path, REAL_CSV_CONTENT)
    # Write the track registry read-model into the expected path
    rm_dir = tmp_path / "generated" / "read_models"
    rm_dir.mkdir(parents=True, exist_ok=True)
    reg_payload = registry_mod.build_niles_track_registry(repo_root=repo_root, generated_at=FIXED_NOW)
    (rm_dir / "niles_track_registry.json").write_text(
        registry_mod.stable_json(reg_payload), encoding="utf-8"
    )

    packet = rp.build_niles_album_review_packet(repo_root=repo_root, generated_at=FIXED_NOW)

    posture = packet["track_registry_posture"]
    assert posture["source_present"] is True
    assert posture["real_track_roster_available"] is True
    assert posture["track_count"] == 3
    assert posture["album_state_confirmed"] is False
    assert posture["raw_audio_ingested"] is False
    # Status should reflect partial data, not blocked
    assert packet["packet_status"] == "blocked_needs_governed_album_evidence"
    # Track roster item should appear in confirmed evidence
    assert any(
        item["item_id"] == "track_registry_roster_available"
        for item in packet["confirmed_governed_evidence"]
    )


def test_track_registry_gap_flagged_in_review_packet_when_missing(tmp_path):
    """If registry is absent, gap item appears in confirmed_governed_evidence."""
    import niles_album_review_packet as rp

    (tmp_path / "generated" / "read_models").mkdir(parents=True, exist_ok=True)
    packet = rp.build_niles_album_review_packet(repo_root=tmp_path, generated_at=FIXED_NOW)

    posture = packet["track_registry_posture"]
    assert posture["source_present"] is False
    assert posture["real_track_roster_available"] is False
    assert packet["packet_status"] == "blocked_needs_governed_album_evidence"
    assert any(
        item["item_id"] == "track_registry_source_missing"
        for item in packet["confirmed_governed_evidence"]
    )


def test_operator_markdown_includes_track_roster(tmp_path):
    """Operator-facing markdown must surface track IDs and statuses."""
    import niles_album_review_packet as rp

    repo_root = _write_csv(tmp_path, REAL_CSV_CONTENT)
    rm_dir = tmp_path / "generated" / "read_models"
    rm_dir.mkdir(parents=True, exist_ok=True)
    reg_payload = registry_mod.build_niles_track_registry(repo_root=repo_root, generated_at=FIXED_NOW)
    (rm_dir / "niles_track_registry.json").write_text(
        registry_mod.stable_json(reg_payload), encoding="utf-8"
    )

    packet = rp.build_niles_album_review_packet(repo_root=repo_root, generated_at=FIXED_NOW)
    rendered = rp.format_niles_album_review_packet(packet)

    assert "Track Roster" in rendered
    assert "T01" in rendered
    assert "T03" in rendered
    assert "idea" in rendered
    assert "tracking" in rendered
    # Safety: must not claim this is confirmed truth
    assert "Album state confirmed: `false`" in rendered


def test_export_writes_read_model(tmp_path):
    repo_root = _write_csv(tmp_path, REAL_CSV_CONTENT)
    export_root = tmp_path / "out"

    result = registry_mod.export_niles_track_registry(
        repo_root=repo_root, export_root=export_root, generated_at=FIXED_NOW
    )
    out_json = Path(result.json_path)

    assert out_json.exists()
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["track_count"] == 3
    assert result.track_count == 3
    assert result.source_present is True
    assert result.schema_version == registry_mod.SCHEMA_VERSION
