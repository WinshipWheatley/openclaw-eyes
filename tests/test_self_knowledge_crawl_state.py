from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from self_knowledge_crawl_state import (  # noqa: E402
    CrawlStateStore,
    crawl_filesystem_incremental,
)


def _make_tree(root: Path) -> None:
    root.mkdir()
    (root / "a.py").write_text("# a\n")
    (root / "b.py").write_text("# b\n")
    sub = root / "sub"
    sub.mkdir()
    (sub / "c.py").write_text("# c\n")


def test_first_crawl_visits_all_files(tmp_path):
    root = tmp_path / "repo"
    _make_tree(root)
    state_db = tmp_path / "state" / "crawl_state.sqlite"

    crumbs = crawl_filesystem_incremental(root, state_db)

    assert sorted(c["relative_path"] for c in crumbs) == ["a.py", "b.py", "sub/c.py"]
    assert state_db.exists()


def test_second_crawl_with_no_changes_visits_nothing(tmp_path):
    root = tmp_path / "repo"
    _make_tree(root)
    state_db = tmp_path / "state" / "crawl_state.sqlite"

    first = crawl_filesystem_incremental(root, state_db)
    assert len(first) == 3

    second = crawl_filesystem_incremental(root, state_db)
    assert second == []


def test_touching_one_file_only_recrawls_its_subtree(tmp_path):
    root = tmp_path / "repo"
    _make_tree(root)
    state_db = tmp_path / "state" / "crawl_state.sqlite"

    first = crawl_filesystem_incremental(root, state_db)
    assert len(first) == 3

    # Advance mtime distinctly (avoid same-second flakiness) on a file in `sub/`.
    target = root / "sub" / "c.py"
    future = time.time() + 120
    os.utime(target, (future, future))

    second = crawl_filesystem_incremental(root, state_db)

    assert [c["relative_path"] for c in second] == ["sub/c.py"]


def test_new_file_in_new_subdirectory_is_picked_up(tmp_path):
    root = tmp_path / "repo"
    _make_tree(root)
    state_db = tmp_path / "state" / "crawl_state.sqlite"

    crawl_filesystem_incremental(root, state_db)

    new_dir = root / "sub2"
    new_dir.mkdir()
    (new_dir / "d.py").write_text("# d\n")

    second = crawl_filesystem_incremental(root, state_db)

    assert [c["relative_path"] for c in second] == ["sub2/d.py"]


def test_state_store_records_and_reads_signature(tmp_path):
    db_path = tmp_path / "crawl_state.sqlite"
    store = CrawlStateStore(db_path)

    assert store.get_signature("/some/dir") is None
    store.record("/some/dir", "a.py:123.5:10")
    assert store.get_signature("/some/dir") == "a.py:123.5:10"

    # Re-recording (upsert) updates the value rather than raising.
    store.record("/some/dir", "a.py:456.75:12")
    assert store.get_signature("/some/dir") == "a.py:456.75:12"
