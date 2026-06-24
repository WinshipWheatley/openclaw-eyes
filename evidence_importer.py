import hashlib
import os
import shutil
import stat
import uuid
from pathlib import Path
from typing import Union

class SecurityError(Exception):
    pass

class ImporterError(Exception):
    pass

class SourceChangedError(ImporterError):
    pass

def import_evidence(source_path: Union[str, Path], target_dir: Union[str, Path]) -> str:
    """
    Atomically imports a file into governed content-addressed storage.
    
    Returns:
        The SHA-256 hex digest of the imported file.
    """
    source = Path(source_path)
    target_d = Path(target_dir).resolve()
    
    # 1. Reject symlinks, directories, and non-regular files
    if source.is_symlink():
        raise SecurityError(f"Symlinks are rejected: {source}")
    if not source.is_file():
        raise SecurityError(f"Must be a regular file: {source}")
    
    # Ensure target directory exists
    target_d.mkdir(parents=True, exist_ok=True)
    
    # 2. Open source and copy to a temporary file in the exact same directory
    temp_filename = f".import-{uuid.uuid4().hex}.tmp"
    temp_path = target_d / temp_filename
    
    sha256 = hashlib.sha256()
    
    # Use os.O_NOFOLLOW if available, otherwise 0
    o_nofollow = getattr(os, "O_NOFOLLOW", 0)
    
    try:
        src_fd = os.open(str(source), os.O_RDONLY | o_nofollow)
        try:
            stat_before = os.fstat(src_fd)
            import stat
            if not stat.S_ISREG(stat_before.st_mode):
                raise SecurityError(f"Must be a regular file: {source}")
                
            # Open temp file exclusively
            dst_fd = os.open(str(temp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
            try:
                with open(src_fd, 'rb', closefd=False) as src_file, open(dst_fd, 'wb', closefd=False) as dst_file:
                    while True:
                        chunk = src_file.read(65536)
                        if not chunk:
                            break
                        sha256.update(chunk)
                        dst_file.write(chunk)
                    
                    # Flush and fsync data
                    dst_file.flush()
                    os.fsync(dst_file.fileno())
            finally:
                os.close(dst_fd)
                
            stat_after = os.fstat(src_fd)
            if (stat_before.st_ino != stat_after.st_ino or 
                stat_before.st_size != stat_after.st_size or 
                stat_before.st_mtime != stat_after.st_mtime):
                raise SourceChangedError("Source file was modified during copy.")
        finally:
            os.close(src_fd)
            
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        if isinstance(e, SourceChangedError) or isinstance(e, SecurityError):
            raise
        raise ImporterError(f"Failed to copy source: {e}") from e

    file_hash = sha256.hexdigest()
    from ar_counterparty_contact_operations import object_path
    rel_path = object_path(file_hash)
    final_path = target_d / rel_path
    
    # Ensure shard directory exists
    final_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 3. Idempotent check
    if final_path.exists():
        temp_path.unlink(missing_ok=True)
        if not final_path.is_file() or final_path.is_symlink():
            raise SecurityError(f"Existing target is not a regular file: {final_path}")
            
        # Verify the bytes actually match the hash
        verify_sha256 = hashlib.sha256()
        with final_path.open('rb') as vf:
            while True:
                chunk = vf.read(65536)
                if not chunk:
                    break
                verify_sha256.update(chunk)
        if verify_sha256.hexdigest() != file_hash:
            raise SecurityError(f"Existing file corrupted: hash {verify_sha256.hexdigest()} does not match name {file_hash}")
            
        return file_hash
        
    # 4. Atomic replace
    try:
        os.replace(str(temp_path), str(final_path))
    except Exception as e:
        temp_path.unlink(missing_ok=True)
        raise ImporterError(f"Atomic replace failed: {e}") from e
        
    # 5. Parent directory fsync (POSIX)
    try:
        dir_fd = os.open(str(target_d), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        # Ignore dir fsync errors on platforms where it's unsupported
        pass
        
    return file_hash
