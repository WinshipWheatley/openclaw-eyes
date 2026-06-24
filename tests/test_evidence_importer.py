import hashlib
import os
import shutil
import stat
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from evidence_importer import import_evidence, SecurityError, ImporterError

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
    
    # To simulate mutation, we will monkeypatch hashlib.sha256 to sleep halfway
    # so we can append to the file while it's being read.
    # However, since the read loop copies exactly what is read, the final file
    # will exactly match the computed hash of the *copied bytes*.
    # That is the expected behavior: the digest matches exactly what landed in target.
    
    original_read = getattr(open, "read", None)
    
    # We'll just run it in a thread and mutate
    def mutator():
        time.sleep(0.01)
        with src_file.open('ab') as f:
            f.write(b"appended")
            
    t = threading.Thread(target=mutator)
    t.start()
    
    # we make the source file large enough so the mutator has time
    src_file.write_bytes(b"0" * 1024 * 1024 * 10) # 10 MB
    
    file_hash = import_evidence(src_file, target_dir)
    t.join()
    
    final_path = target_dir / file_hash
    assert final_path.exists()
    
    # The crucial security property: The hash matches the actual data resting in the target_dir.
    with final_path.open('rb') as f:
        actual_content = f.read()
        assert hashlib.sha256(actual_content).hexdigest() == file_hash
