"""
pii_vault.py

Two capabilities:

1. Encrypted local store for sensitive personal data (SSN, tax info, etc.).
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

2. In-memory tokenization for LLM calls.
   Redacts emails, phone numbers, account numbers, SSNs, and credit-card
   numbers from text before prompt assembly.  Tokens ([SECRET_n]) can be
   rehydrated from the returned TokenMap after the LLM responds.

   redact_text(text)               -> (redacted_str, TokenMap)
   rehydrate_text(text, token_map) -> str
"""

import json
import os
import re
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


# ── In-memory tokenization ───────────────────────────────────────────────────
#
# Patterns are ordered most-specific first so that a 16-digit credit-card
# number is captured before the generic bare-digits fallback.

_REDACT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # Credit card – 4×4 groups separated by space or dash
    ("cc", re.compile(r"\b(?:\d{4}[-\s]){3}\d{4}\b")),
    # SSN – ddd-dd-dddd
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # Email
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    # Phone – common US formats, optional +1 prefix
    ("phone", re.compile(
        r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b"
    )),
    # Generic account-like numbers: 8–20 consecutive digits
    ("acct", re.compile(r"\b\d{8,20}\b")),
]


class TokenMap:
    """
    Maps token placeholders ('[SECRET_n]') back to their original values.

    __repr__ and __str__ deliberately omit values to prevent accidental log
    leakage.  Use .reveal(token) for controlled access.
    """

    def __init__(self) -> None:
        self._map: dict[str, str] = {}
        self._counter: int = 0

    def _add(self, value: str) -> str:
        """Return existing token if value already seen, else allocate a new one."""
        for token, stored in self._map.items():
            if stored == value:
                return token
        self._counter += 1
        token = f"[SECRET_{self._counter}]"
        self._map[token] = value
        return token

    def reveal(self, token: str) -> str | None:
        """Return original value for *token*, or None if unknown."""
        return self._map.get(token)

    def tokens(self) -> list[str]:
        return list(self._map.keys())

    def is_empty(self) -> bool:
        return len(self._map) == 0

    def __repr__(self) -> str:
        return f"TokenMap(<{len(self._map)} secret(s) redacted>)"

    def __str__(self) -> str:
        return repr(self)


def redact_text(text: str) -> tuple[str, "TokenMap"]:
    """
    Scan *text* for PII patterns and replace each match with a stable token.

    Returns (redacted_text, token_map).  If no PII is found the text is
    returned unchanged and token_map.is_empty() will be True.

    Example
    -------
    >>> redacted, tok = redact_text("email a@b.com acct 1234567890")
    >>> "[SECRET_" in redacted
    True
    >>> "a@b.com" not in redacted
    True
    """
    token_map = TokenMap()
    for _label, pattern in _REDACT_PATTERNS:
        def _replace(m: re.Match, _tm: TokenMap = token_map) -> str:
            return _tm._add(m.group(0))
        text = pattern.sub(_replace, text)
    return text, token_map


def rehydrate_text(text: str, token_map: "TokenMap") -> str:
    """
    Replace any [SECRET_n] tokens in *text* with their original values from
    *token_map*.  Unknown tokens are left in place.

    Safe to call when token_map is empty.
    """
    if token_map.is_empty():
        return text
    for token in token_map.tokens():
        original = token_map.reveal(token)
        if original is not None:
            text = text.replace(token, original)
    return text


# ── Presidio-backed PIIVault class ───────────────────────────────────────────


class PIIVault:
    """
    Tokenize and de-tokenize sensitive text using Presidio NLP analysis.

    Supported entities: PERSON, EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, LOCATION

    Usage
    -----
    v = PIIVault()
    tokenized, mapping = v.tokenize("Call John at 555-123-4567")
    # tokenized  -> "Call <PERSON_1> at <PHONE_NUMBER_2>"
    # mapping    -> {"<PERSON_1>": "John", "<PHONE_NUMBER_2>": "555-123-4567"}
    original = v.detokenize(tokenized)
    # original   -> "Call John at 555-123-4567"

    The in-memory vault (self._vault) is never emitted to logs; __repr__ hides it.
    """

    _ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "LOCATION"]

    def __init__(self) -> None:
        self._vault: dict[str, str] = {}
        self._analyzer = None  # lazy-init to keep import side-effect free
        self._counters: dict[str, int] = {}

    def _get_analyzer(self):
        if self._analyzer is None:
            try:
                from presidio_analyzer import AnalyzerEngine
                self._analyzer = AnalyzerEngine()
            except ImportError as exc:
                raise RuntimeError(
                    "presidio-analyzer is required for PIIVault. "
                    "Install with: pip install presidio-analyzer presidio-anonymizer "
                    "and run: python -m spacy download en_core_web_lg"
                ) from exc
        return self._analyzer

    def tokenize(self, text: str) -> tuple[str, dict]:
        """
        Detect PII entities in *text* and replace each with a unique placeholder.

        Returns (tokenized_text, vault_mapping).
        Placeholders have the form <ENTITY_TYPE_N> e.g. <PERSON_1>.
        Vault mapping is also stored on self._vault for use by detokenize().
        """
        analyzer = self._get_analyzer()
        results = analyzer.analyze(text=text, entities=self._ENTITIES, language="en")
        # Sort longest span first so replacements don't shift offsets
        results = sorted(results, key=lambda r: r.start - r.end)

        # Build per-call counters so numbering is deterministic within one call
        call_counters: dict[str, int] = {}
        replacements: list[tuple[int, int, str]] = []

        for result in results:
            entity = result.entity_type
            call_counters[entity] = call_counters.get(entity, 0) + 1
            # Global counter so vault tokens never collide across calls
            self._counters[entity] = self._counters.get(entity, 0) + 1
            token = f"<{entity}_{self._counters[entity]}>"
            original = text[result.start:result.end]
            self._vault[token] = original
            replacements.append((result.start, result.end, token))

        # Apply replacements in reverse order to preserve positions
        replacements.sort(key=lambda r: r[0], reverse=True)
        chars = list(text)
        for start, end, token in replacements:
            chars[start:end] = list(token)
        tokenized = "".join(chars)

        mapping = {t: self._vault[t] for _, _, t in replacements}
        return tokenized, mapping

    def detokenize(self, text: str) -> str:
        """
        Replace any <ENTITY_TYPE_N> tokens in *text* with their original values.
        Unknown tokens are left in place.
        """
        for token, original in self._vault.items():
            text = text.replace(token, original)
        return text

    def clear(self) -> None:
        """Wipe the in-memory vault. Call between sessions if desired."""
        self._vault.clear()
        self._counters.clear()

    def __repr__(self) -> str:
        return f"PIIVault(<{len(self._vault)} token(s) — vault hidden>)"

    def __str__(self) -> str:
        return repr(self)


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
