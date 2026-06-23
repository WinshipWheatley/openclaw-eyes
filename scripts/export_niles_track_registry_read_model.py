#!/usr/bin/env python3
"""Export Niles track-registry read-model from chief album CSV.

Reads .openclaw/agents/chief/album/track-registry.csv and publishes a
deterministic, source-tagged read-model at
generated/read_models/niles_track_registry.json.

SAFETY: Read-only. Touches only the governed CSV metadata file and
generated/read_models/. Does NOT open DAWs, scan audio, mutate session
files, scan private drive, or grant runtime/send authority.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "niles_track_registry_v0"
JSON_EXPORT_NAME = "niles_track_registry.json"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

# Canonical governed CSV source — metadata only, not private audio
TRACK_REGISTRY_CSV_PATH = Path(".openclaw/agents/chief/album/track-registry.csv")

EXPECTED_FIELDS = frozenset(
    {"track_id", "title", "status", "owner", "next_step", "est_hours", "target_week"}
)


@dataclass(frozen=True)
class NilesTrackRegistryResult:
    schema_version: str
    source_path: str
    track_count: int
    statuses: list[str]
    source_present: bool
    json_path: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rooted(path: str | Path, repo_root: Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def _read_tracks(csv_path: Path) -> list[dict[str, Any]]:
    """Read track-registry.csv rows as governed metadata dicts."""
    if not csv_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # Normalise; store only metadata fields we expect
            track: dict[str, Any] = {}
            for key in EXPECTED_FIELDS:
                value = (row.get(key) or "").strip()
                if key == "est_hours":
                    try:
                        track[key] = int(value)
                    except ValueError:
                        track[key] = None
                else:
                    track[key] = value or None
            # Evidence posture flags — not fabricated
            track["metadata_only"] = True
            track["raw_audio_stored"] = False
            track["daw_session_contents_stored"] = False
            track["file_opened_or_scanned"] = False
            track["album_state_confirmed"] = False
            rows.append(track)
    return rows


def _status_summary(tracks: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for t in tracks:
        status = t.get("status") or "unknown"
        summary[status] = summary.get(status, 0) + 1
    return summary


def build_niles_track_registry(
    *, repo_root: str | Path = ROOT, generated_at: str | None = None
) -> dict[str, Any]:
    root = Path(repo_root)
    csv_path = _rooted(TRACK_REGISTRY_CSV_PATH, root)
    source_present = csv_path.exists()
    tracks = _read_tracks(csv_path)
    status_summary = _status_summary(tracks)

    real_track_roster_available = source_present and len(tracks) > 0
    source_missing_gap = (
        None
        if source_present
        else (
            "Track-registry CSV not found at "
            + TRACK_REGISTRY_CSV_PATH.as_posix()
            + ". Gap: no governed track roster available."
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "source_id": "niles_track_registry",
        "source_path": TRACK_REGISTRY_CSV_PATH.as_posix(),
        "source_ref": "generated/read_models/niles_track_registry.json",
        "source_present": source_present,
        "source_role": "governed chief album track-registry CSV metadata",
        "truth_status": "governed_operator_metadata_evidence_not_final_audio_truth",
        "source_promoted_to_truth": False,
        "track_count": len(tracks),
        "tracks": tracks,
        "status_summary": status_summary,
        "real_track_roster_available": real_track_roster_available,
        # Anti-confabulation: if source is missing, say so explicitly
        "source_missing_gap": source_missing_gap,
        "metadata_only": True,
        "raw_audio_ingested": False,
        "daw_session_content_ingested": False,
        "broad_private_drive_scan_triggered": False,
        "runtime_authority_added": False,
        "send_or_submit_authority_added": False,
    }


def export_niles_track_registry(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> NilesTrackRegistryResult:
    root = Path(repo_root)
    out_dir = (
        Path(export_root)
        if Path(export_root).is_absolute()
        else root / export_root
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_niles_track_registry(repo_root=root, generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    return NilesTrackRegistryResult(
        schema_version=SCHEMA_VERSION,
        source_path=TRACK_REGISTRY_CSV_PATH.as_posix(),
        track_count=payload["track_count"],
        statuses=list(payload["status_summary"].keys()),
        source_present=payload["source_present"],
        json_path=json_path.as_posix(),
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Niles track-registry read-model.")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_niles_track_registry(repo_root=args.repo_root, export_root=args.export_root)
    if result.source_present:
        print(
            f"niles_track_registry exported: {result.json_path} "
            f"({result.track_count} tracks; statuses={result.statuses})"
        )
    else:
        print(
            f"GAP: track-registry CSV missing at {result.source_path}. "
            f"Read-model written with source_missing_gap flag."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
