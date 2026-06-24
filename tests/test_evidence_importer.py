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
    
    final_path = target_dir / actual_hash
    assert final_path.exists()
    assert final_path.read_bytes() == content
    
    # Check that temp files were cleaned up
    assert len(list(target_dir.iterdir())) == 1

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
    assert len(list(target_dir.iterdir())) == 1

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
        
    # The temp file should have been cleaned up in the except block
    assert len(list(target_dir.iterdir())) == 0

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
    assert len(list(target_dir.iterdir())) == 1
    final_path = target_dir / expected_hash
    assert final_path.exists()

def test_source_mutation_during_copy(workspace, monkeypatch):
    source_dir, target_dir = workspace
    src_file = source_dir / "mutating.txt"
    src_file.write_bytes(b"initial")
    
    # Mock Path.stat to return different sizes on subsequent calls
    original_stat = Path.stat
    call_count = 0
    
    def mock_stat(self, *args, **kwargs):
        nonlocal call_count
        st = original_stat(self, *args, **kwargs)
        if kwargs.get('follow_symlinks') is False or self != src_file:
            return st
        call_count += 1
        if call_count == 3: # Third call on src_file (stat_after)
            import os
            return os.stat_result((
                st.st_mode, st.st_ino, st.st_dev, st.st_nlink,
                st.st_uid, st.st_gid, st.st_size + 100,
                st.st_atime, st.st_mtime, st.st_ctime
            ))
        return st
        
    monkeypatch.setattr(Path, "stat", mock_stat)
    
    with pytest.raises(SourceChangedError, match="Source file was modified during copy"):
        import_evidence(src_file, target_dir)
        
    assert len(list(target_dir.iterdir())) == 0

def test_existing_corruption(workspace):
    source_dir, target_dir = workspace
    src_file = source_dir / "test.txt"
    content = b"Safe data"
    src_file.write_bytes(content)
    
    expected_hash = hashlib.sha256(content).hexdigest()
    
    # Forge a corrupted target file with the same name
    corrupted_path = target_dir / expected_hash
    corrupted_path.write_bytes(b"Tampered content")
    
    with pytest.raises(SecurityError, match="Existing file corrupted"):
        import_evidence(src_file, target_dir)
