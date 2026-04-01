title: hitl-004-file-integrity-verify
profile: surgical
goal: Implement FILE_VERIFY integrity utility using SHA-256 so uploaded/logged files can be checked for tamper.
scope:
- Add utility module for sha256_file(path) and verify_file_hash(path, expected_hash).
- Add safe handling for missing files and unreadable files.
- Add optional metadata helper to store file hash alongside log entries.
- Integrate verification call into relevant Cassandra/Chief file-check flow.
- Add tests in /home/openclaw/tests for positive/negative hash checks.
success:
- System can produce and verify SHA-256 hashes for tracked files.
- Verification result is explicit pass/fail/error and logged.
verification: |
  python3 -c "import hashlib,tempfile,os; p=tempfile.NamedTemporaryFile(delete=False); p.write(b'x'); p.close(); h=hashlib.sha256(open(p.name,'rb').read()).hexdigest(); print(h); os.unlink(p.name)"
notes: |
  Keep implementation generic for PDF and non-PDF files.
