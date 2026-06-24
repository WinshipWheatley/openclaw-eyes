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
    
    try:
        with source.open('rb') as src_file:
            # Open temp file exclusively
            fd = os.open(str(temp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
            with open(fd, 'wb') as dst_file:
                while True:
                    chunk = src_file.read(65536)
                    if not chunk:
                        break
                    sha256.update(chunk)
                    dst_file.write(chunk)
                
                # Flush and fsync data
                dst_file.flush()
                os.fsync(dst_file.fileno())
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise ImporterError(f"Failed to copy source: {e}") from e

    file_hash = sha256.hexdigest()
    final_path = target_d / file_hash
    
    # 3. Idempotent check
    if final_path.exists():
        # Already imported
        temp_path.unlink(missing_ok=True)
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
