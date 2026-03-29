"""
pii_vault.py

Encrypted local store for sensitive personal data (SSN, tax info, etc.).
Uses Fernet symmetric encryption (cryptography package).

Key management
--------------
Key is stored in /home/openclaw/.chief.env as:
  PII_VAULT_KEY=<base64-fernet-key>

To generate a new key (first-time setup):
  python3 pii_vault.py --generate-key

Vault file: /home/openclaw/.pii_vault.enc
Format on disk: Fernet-encrypted JSON blob  →  {"field": "value", ...}

Cassandra access: read_pii(field) only. No write access from Cassandra.
Admin write access: python3 pii_vault.py --write field value
"""

import json
import os
import sys
from pathlib import Path

VAULT_PATH = Path("/home/openclaw/.pii_vault.enc")
ENV_FILE   = Path("/home/openclaw/.chief.env")
KEY_VAR    = "PII_VAULT_KEY"


def _load_key() -> bytes:
    """Load Fernet key from environment. Raises RuntimeError if not set."""
    key = os.environ.get(KEY_VAR, "")
    if not key:
        # Try loading from .chief.env directly (for CLI / subprocess contexts)
        if ENV_FILE.exists():
            for line in ENV_FILE.read_text().splitlines():
                line = line.strip()
                if line.startswith(f"{KEY_VAR}="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        raise RuntimeError(
            f"{KEY_VAR} not set. Run: python3 pii_vault.py --generate-key "
            f"and add the result to {ENV_FILE} as {KEY_VAR}=<key>"
        )
    return key.encode()


def _read_vault(key_bytes: bytes) -> dict:
    """Decrypt and return vault contents. Returns {} if vault does not exist."""
    from cryptography.fernet import Fernet
    if not VAULT_PATH.exists():
        return {}
    try:
        f = Fernet(key_bytes)
        raw = f.decrypt(VAULT_PATH.read_bytes())
        return json.loads(raw.decode())
    except Exception as e:
        raise RuntimeError(f"Failed to decrypt vault: {e}") from e


def _write_vault(data: dict, key_bytes: bytes) -> None:
    """Encrypt and write vault to disk."""
    from cryptography.fernet import Fernet
    f = Fernet(key_bytes)
    encrypted = f.encrypt(json.dumps(data).encode())
    VAULT_PATH.write_bytes(encrypted)
    VAULT_PATH.chmod(0o600)


def read_pii(field: str) -> str:
    """Read a single PII field. Returns '' if field not set or vault unavailable."""
    try:
        key_bytes = _load_key()
        data = _read_vault(key_bytes)
        return data.get(field, "")
    except Exception:
        return ""


def write_pii(field: str, value: str) -> None:
    """Write a PII field. Admin use only — not exposed to Cassandra."""
    key_bytes = _load_key()
    data = _read_vault(key_bytes)
    data[field] = value
    _write_vault(data, key_bytes)


def list_pii_fields() -> list:
    """Return list of field names (not values) stored in vault."""
    try:
        key_bytes = _load_key()
        data = _read_vault(key_bytes)
        return sorted(data.keys())
    except Exception:
        return []


def generate_key() -> str:
    """Generate a new Fernet key. Print to stdout for Winship to add to .chief.env."""
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


# ── CLI interface ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] == "--help":
        print(__doc__)
        sys.exit(0)

    if args[0] == "--generate-key":
        key = generate_key()
        print(f"New Fernet key (add to {ENV_FILE} as {KEY_VAR}=<key>):")
        print(key)
        sys.exit(0)

    if args[0] == "--write" and len(args) == 3:
        _, field, value = args
        write_pii(field, value)
        print(f"Written: {field}")
        sys.exit(0)

    if args[0] == "--read" and len(args) == 2:
        _, field = args
        val = read_pii(field)
        if val:
            print(f"{field}: [REDACTED — {len(val)} chars]")
        else:
            print(f"{field}: (not set)")
        sys.exit(0)

    if args[0] == "--list":
        fields = list_pii_fields()
        if fields:
            print("Stored fields:")
            for f in fields:
                print(f"  {f}")
        else:
            print("Vault is empty or not initialized.")
        sys.exit(0)

    print(f"Unknown command: {args[0]}")
    print("Usage: python3 pii_vault.py [--generate-key | --write field value | --read field | --list | --help]")
    sys.exit(1)
