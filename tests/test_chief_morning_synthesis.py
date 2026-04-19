from datetime import datetime, timedelta
import os
from pathlib import Path

import chief_morning_synthesis as cms


def _write(path: Path, text: str, when: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    ts = when.timestamp()
    os.utime(path, (ts, ts))


def test_build_synthesis_includes_required_metadata_and_sections(tmp_path):
    now = datetime(2026, 4, 19, 9, 0).astimezone()
    daily = tmp_path / "System" / "Daily Report.md"
    polish = tmp_path / "System" / "Nightly Polish Log.md"
    actions = tmp_path / "System" / "Ops Actions Context.md"
    calendar = tmp_path / "System" / "Ops Calendar Notes.md"
    qa = tmp_path / "Website" / "QA Log.md"

    _write(daily, "# Daily Report\n\nSystem health\n  - Errors detected - check listener.out\n", now)
    _write(polish, "# Nightly Polish\n\nQueue: 1 tasks ready for execution.\n", now)
    _write(actions, "# Ops Actions\n\n- [OPEN] Follow up on Capital Hilton Coupa verification.\n", now)
    _write(calendar, "# Ops Calendar Notes\n\n- [FACT] Golf with Dad was historical only.\n", now - timedelta(days=5))
    _write(qa, "# Website QA Log\n\nSTATUS: OFFLINE\n", now - timedelta(days=30))

    markdown = cms.build_chief_morning_synthesis_markdown(
        now=now,
        upstream_artifacts=(
            cms.UpstreamArtifact("System Health Report", daily),
            cms.UpstreamArtifact("Nightly Polish Log", polish),
            cms.UpstreamArtifact("Ops Actions Context", actions),
            cms.UpstreamArtifact("Ops Calendar Notes", calendar, required=False),
            cms.UpstreamArtifact("Website QA Log", qa, required=False),
        ),
    )

    assert "type: chief-morning-synthesis" in markdown
    assert "source_module: chief_morning_synthesis.py" in markdown
    assert "## Upstream Artifacts Read" in markdown
    assert "## Top Priorities" in markdown
    assert "## Blockers / Watchlist" in markdown
    assert "## System / Ops State" in markdown
    assert "## Schedule / QA" in markdown
    assert "## Confidence / What May Be Stale" in markdown
    assert "Capital Hilton Coupa verification" in markdown
    assert "stale: source last changed" in markdown


def test_write_synthesis_writes_output_artifact(tmp_path):
    now = datetime(2026, 4, 19, 9, 0).astimezone()
    source = tmp_path / "Daily Report.md"
    output = tmp_path / "Chief Morning Synthesis.md"
    _write(source, "# Daily Report\n\nWorkers\n  - 0 messages queued today\n", now)

    written = cms.write_chief_morning_synthesis(
        output_path=output,
        now=now,
        upstream_artifacts=(cms.UpstreamArtifact("System Health Report", source),),
    )

    assert written == output
    text = output.read_text(encoding="utf-8")
    assert "# Chief Morning Synthesis" in text
    assert "`chief_morning_synthesis.py`" in text
    assert "System Health Report" in text


def test_synthesis_reports_missing_required_source(tmp_path):
    now = datetime(2026, 4, 19, 9, 0).astimezone()
    markdown = cms.build_chief_morning_synthesis_markdown(
        now=now,
        upstream_artifacts=(cms.UpstreamArtifact("System Health Report", tmp_path / "missing.md"),),
    )

    assert "missing required source" in markdown
    assert "System Health Report" in markdown


def test_synthesis_bounds_large_upstream_content(tmp_path):
    now = datetime(2026, 4, 19, 9, 0).astimezone()
    source = tmp_path / "Ops Actions Context.md"
    _write(source, "# Ops Actions\n\n" + ("- [OPEN] Very long action line\n" * 500), now)

    markdown = cms.build_chief_morning_synthesis_markdown(
        now=now,
        upstream_artifacts=(cms.UpstreamArtifact("Ops Actions Context", source),),
    )

    assert len(markdown) < 10_000
    assert "deterministic excerpts capped" in markdown
