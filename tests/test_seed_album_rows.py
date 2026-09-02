from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import chief_album_io
from practice_loop import ALBUM_SONGS

ROOT = Path(__file__).resolve().parents[1]


def _load_script():
    spec = importlib.util.spec_from_file_location("seed_album_rows", ROOT / "scripts" / "seed_album_rows.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["seed_album_rows"] = module
    spec.loader.exec_module(module)
    return module


def _csv_with_three(tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / "album_work_log.csv"
    monkeypatch.setattr(chief_album_io, "CSV_PATH", path)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=chief_album_io.BASE_CSV_FIELDS)
        writer.writeheader()
        for title, pct in (("Blue Weather", "60"), ("Ten Fingers", "35"), ("The Future", "10")):
            writer.writerow({"song_title": title, "completion_pct": pct, "status": "in_progress"})
    return path


def _rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_dry_run_names_the_missing_nine_and_writes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    path = _csv_with_three(tmp_path, monkeypatch)
    before = path.read_bytes()
    seed = _load_script()
    assert seed.main([]) == 0
    out = capsys.readouterr().out
    assert "Would write 9 row(s)" in out
    assert "Dry run: nothing written" in out
    assert "- 1 In A Million" in out
    assert "Blue Weather" not in out.split("Would write")[1]
    assert path.read_bytes() == before


def test_apply_seeds_missing_rows_and_leaves_existing_alone(tmp_path: Path, monkeypatch, capsys) -> None:
    path = _csv_with_three(tmp_path, monkeypatch)
    seed = _load_script()
    assert seed.main(["--apply"]) == 0
    rows = _rows(path)
    assert len(rows) == len(ALBUM_SONGS) == 12
    by_title = {row["song_title"]: row for row in rows}
    assert by_title["Blue Weather"]["completion_pct"] == "60"
    assert by_title["Blue Weather"]["status"] == "in_progress"
    assert by_title["1 In A Million"]["status"] == "not_started"
    assert by_title["1 In A Million"]["completion_pct"] == "0"
    assert "Wrote 9 row(s)" in capsys.readouterr().out
    assert seed.main(["--apply"]) == 0
    assert len(_rows(path)) == 12
    assert "Nothing missing" in capsys.readouterr().out


def test_csv_flag_overrides_the_path(tmp_path: Path, monkeypatch, capsys) -> None:
    other = tmp_path / "elsewhere.csv"
    monkeypatch.setattr(chief_album_io, "CSV_PATH", tmp_path / "unused.csv")
    seed = _load_script()
    assert seed.main(["--csv", str(other), "--format", "json"]) == 0
    import json

    summary = json.loads(capsys.readouterr().out)
    assert summary["csv_path"] == str(other)
    assert summary["missing"] == list(ALBUM_SONGS)
    assert summary["applied"] is False
    assert other.exists()  # ensure_csv creates the header only
    assert _rows(other) == []
    assert not (tmp_path / "unused.csv").exists()
