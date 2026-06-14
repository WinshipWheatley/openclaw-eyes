"""
cassandra_pii_hooks.py

PII tokenization/detokenization hooks for the Cassandra request path.

Set CASSANDRA_PRESIDIO_PII_ENABLED=1 in the shell environment to activate the
Presidio-backed PIIVault. When unset or 0, the module falls back to the
regex-based redact_text / rehydrate_text already in pii_vault.
"""

import os


_PRESIDIO_ENABLED: bool = os.environ.get("CASSANDRA_PRESIDIO_PII_ENABLED", "0") == "1"

_vault_instance = None
_vault_init_failed: bool = False


def _get_vault():
    """Return the shared PIIVault instance. Returns None if unavailable."""
    global _vault_instance, _vault_init_failed
    if _vault_init_failed:
        return None
    if _vault_instance is None:
        try:
            from pii_vault import PIIVault

            _vault_instance = PIIVault()
        except Exception as exc:
            print(
                f"[pii_hooks] PIIVault init failed: {exc} - vault unavailable",
                flush=True,
            )
            _vault_init_failed = True
            return None
    return _vault_instance


class _OpaqueContext:
    """
    Carries token-map state between tokenize_prompt and rehydrate_reply.

    __repr__ intentionally hides vault contents to prevent log leakage.
    """

    __slots__ = ("_vault_mapping", "_regex_map", "_method")

    def __init__(self, vault_mapping=None, regex_map=None, method: str = "none") -> None:
        self._vault_mapping: dict = vault_mapping or {}
        self._regex_map = regex_map
        self._method: str = method

    @property
    def is_empty(self) -> bool:
        if self._method == "presidio":
            return len(self._vault_mapping) == 0
        if self._method == "regex" and self._regex_map is not None:
            return self._regex_map.is_empty()
        return True

    @property
    def token_count(self) -> int:
        if self._method == "presidio":
            return len(self._vault_mapping)
        if self._method == "regex" and self._regex_map is not None:
            return len(self._regex_map.tokens())
        return 0

    def __repr__(self) -> str:
        return f"_OpaqueContext(method={self._method!r}, tokens={self.token_count})"


def _audit_log(method: str, token_count: int) -> None:
    """Emit a single audit line. Never includes original values."""
    if token_count > 0:
        print(
            f"[pii_hooks] {method} tokenized {token_count} entity(ies) "
            f"| redacted=True no_originals=True",
            flush=True,
        )


def tokenize_prompt(prompt: str) -> tuple[str | None, "_OpaqueContext | None"]:
    """
    Tokenize PII in *prompt* before sending to any LLM.

    Returns (safe_prompt, ctx). Returns (None, None) only when all redaction
    paths have failed.
    """
    if _PRESIDIO_ENABLED:
        vault = _get_vault()
        if vault is not None:
            try:
                safe_prompt, mapping = vault.tokenize(prompt)
                ctx = _OpaqueContext(vault_mapping=mapping, method="presidio")
                _audit_log("presidio", ctx.token_count)
                return safe_prompt, ctx
            except Exception as exc:
                print(
                    f"[pii_hooks] presidio tokenize failed: {exc} - falling back to regex",
                    flush=True,
                )
        else:
            print(
                "[pii_hooks] presidio vault unavailable - falling back to regex",
                flush=True,
            )

    try:
        from pii_vault import redact_text

        safe_prompt, tok_map = redact_text(prompt)
        ctx = _OpaqueContext(regex_map=tok_map, method="regex")
        _audit_log("regex", ctx.token_count)
        return safe_prompt, ctx
    except Exception as exc:
        print(
            f"[pii_hooks] regex fallback failed: {exc} - blocking LLM send",
            flush=True,
        )

    return None, None


def rehydrate_reply(reply: str, ctx: "_OpaqueContext | None") -> str:
    """Restore token placeholders in an LLM reply using *ctx*."""
    if ctx is None or ctx.is_empty:
        return reply

    if ctx._method == "presidio":
        vault = _get_vault()
        if vault is None:
            print(
                "[pii_hooks] rehydrate: vault gone - tokens may remain in reply",
                flush=True,
            )
            return reply
        return vault.detokenize(reply)

    if ctx._method == "regex" and ctx._regex_map is not None:
        from pii_vault import rehydrate_text

        return rehydrate_text(reply, ctx._regex_map)

    return reply


def detokenize_for_dashboard(text: str, ctx: "_OpaqueContext | None") -> str:
    """
    Detokenize *text* for trusted local dashboard rendering.

    This must only be called from trusted, local-only render paths.
    """
    return rehydrate_reply(text, ctx)
