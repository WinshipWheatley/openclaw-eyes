import hashlib
import os
import shutil
import stat
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from evidence_importer import import_evidence, SecurityError, ImporterError, SourceChangedError

@pytest.fixture
def workspace(tmp_path):
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()
    return source_dir, target_dir

def test_atomic_import_success(workspace):
    source_dir, target_dir = workspace
    src_file = source_dir / "test.txt"
    content = b"Hello world! This is evidence."
    src_file.write_bytes(content)
    
    expected_hash = hashlib.sha256(content).hexdigest()
    
    actual_hash = import_evidence(src_file, target_dir)
    assert actual_hash == expected_hash
    
    final_path = target_dir / actual_hash[:2] / actual_hash[2:]
    assert final_path.exists()
    assert final_path.read_bytes() == content
    
    # temp files cleaned up
    assert len(list(target_dir.rglob("*.tmp"))) == 0

def test_idempotent_import(workspace):
    source_dir, target_dir = workspace
    src_file = source_dir / "test.txt"
    content = b"Idempotent data"
    src_file.write_bytes(content)
    
    # First import
    h1 = import_evidence(src_file, target_dir)
    # Second import
    h2 = import_evidence(src_file, target_dir)
    
    assert h1 == h2
    assert len(list(target_dir.rglob("*.tmp"))) == 0

def test_reject_symlink(workspace):
    source_dir, target_dir = workspace
    target_file = source_dir / "real.txt"
    target_file.write_text("real")
    
    sym_file = source_dir / "link.txt"
    sym_file.symlink_to(target_file)
    
    with pytest.raises(SecurityError, match="Symlinks are rejected"):
        import_evidence(sym_file, target_dir)

def test_reject_directory(workspace):
    source_dir, target_dir = workspace
    with pytest.raises(SecurityError, match="Must be a regular file"):
        import_evidence(source_dir, target_dir)

def test_interruption_cleanup(workspace, monkeypatch):
    source_dir, target_dir = workspace
    src_file = source_dir / "test.txt"
    src_file.write_bytes(b"some data")
    
    # Simulate a crash right before os.replace
    original_replace = os.replace
    def fake_replace(src, dst):
        raise OSError("Simulated crash")
        
    monkeypatch.setattr(os, "replace", fake_replace)
    
    with pytest.raises(ImporterError, match="Atomic replace failed"):
        import_evidence(src_file, target_dir)
        
    assert len(list(target_dir.rglob("*.tmp"))) == 0

def test_concurrent_imports(workspace):
    source_dir, target_dir = workspace
    src_file = source_dir / "concurrent.txt"
    content = b"A" * 1024 * 1024 * 10  # 10 MB to ensure they overlap
    src_file.write_bytes(content)
    expected_hash = hashlib.sha256(content).hexdigest()
    
    # Run 5 imports concurrently
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(import_evidence, src_file, target_dir) for _ in range(5)]
        for f in futures:
            results.append(f.result())
            
    assert all(r == expected_hash for r in results)
    
    # Should only be one finalized file, no temp files leftover
    assert len(list(target_dir.rglob("*.tmp"))) == 0
    final_path = target_dir / expected_hash[:2] / expected_hash[2:]
    assert final_path.exists()

def test_source_mutation_during_copy(workspace, monkeypatch):
    source_dir, target_dir = workspace
    src_file = source_dir / "mutating.txt"
    src_file.write_bytes(b"initial")
    
    original_fstat = os.fstat
    call_count = 0
    
    def mock_fstat(fd):
        nonlocal call_count
        st = original_fstat(fd)
        try:
            path = Path(os.readlink(f"/proc/self/fd/{fd}"))
        except OSError:
            path = None
        if path != src_file.resolve():
            return st
        call_count += 1
        if call_count == 2: # Second call on src_file (stat_after)
            return os.stat_result((
                st.st_mode, st.st_ino, st.st_dev, st.st_nlink,
                st.st_uid, st.st_gid, st.st_size + 100,
                st.st_atime, st.st_mtime, st.st_ctime
            ))
        return st
        
    monkeypatch.setattr(os, "fstat", mock_fstat)
    
    with pytest.raises(SourceChangedError, match="Source file was modified during copy"):
        import_evidence(src_file, target_dir)
        
    assert len(list(target_dir.rglob("*.tmp"))) == 0

def test_existing_corruption(workspace):
    source_dir, target_dir = workspace
    src_file = source_dir / "test.txt"
    content = b"Safe data"
    src_file.write_bytes(content)
    
    expected_hash = hashlib.sha256(content).hexdigest()
    
    # Forge a corrupted target file with the same name
    corrupted_path = target_dir / expected_hash[:2] / expected_hash[2:]
    corrupted_path.parent.mkdir(parents=True, exist_ok=True)
    corrupted_path.write_bytes(b"Tampered content")
    
    with pytest.raises(SecurityError, match="Existing file corrupted"):
        import_evidence(src_file, target_dir)
