"""Shared Telegram listener identity and role-token integrity rails.

Tokens are deliberately never rendered into logs or exception messages.  A
listener must verify its public Telegram identity through ``getMe`` before
polling; the verified identity is then the namespace for durable update-id
claims in :mod:`telegram_agent_intake`.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import threading
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping


LogFunction = Callable[[str], None]


def _print_line(message: str) -> None:
    print(message, flush=True)


@dataclass(frozen=True)
class RoleBotTokenSpec:
    role: str
    canonical_env: str
    legacy_envs: tuple[str, ...] = ()


ROLE_BOT_TOKEN_SPECS: dict[str, RoleBotTokenSpec] = {
    "maestro": RoleBotTokenSpec("maestro", "MAESTRO_BOT_TOKEN"),
    "chief": RoleBotTokenSpec("chief", "CHIEF_BOT_TOKEN", ("TELEGRAM_BOT_TOKEN",)),
    "cassandra": RoleBotTokenSpec("cassandra", "CASSANDRA_BOT_TOKEN"),
    "guardian": RoleBotTokenSpec("guardian", "GUARDIAN_BOT_TOKEN"),
    "niles": RoleBotTokenSpec("niles", "NILES_BOT_TOKEN", ("PRODUCER_BOT_TOKEN",)),
    # The vendored Hermes adapter expects TELEGRAM_BOT_TOKEN.  The tracked
    # launcher verifies HERMES_BOT_TOKEN, then explicitly remaps it.
    "hermes": RoleBotTokenSpec("hermes", "HERMES_BOT_TOKEN"),
}
_LEGACY_WARNINGS_EMITTED: set[tuple[str, str]] = set()
_LEGACY_WARNINGS_LOCK = threading.RLock()


def _token_spec(role: str) -> RoleBotTokenSpec:
    normalized = str(role or "").strip().lower()
    try:
        return ROLE_BOT_TOKEN_SPECS[normalized]
    except KeyError as exc:
        raise ValueError(f"unknown Telegram bot role: {role!r}") from exc


def _warn_legacy_token(spec: RoleBotTokenSpec, legacy_env: str, warn: LogFunction) -> None:
    warning_key = (spec.role, legacy_env)
    with _LEGACY_WARNINGS_LOCK:
        if warning_key in _LEGACY_WARNINGS_EMITTED:
            return
        _LEGACY_WARNINGS_EMITTED.add(warning_key)
    warn(
        f"[{spec.role}_listener] LOUD WARNING: {legacy_env} is a legacy bot-token fallback; "
        f"configure {spec.canonical_env}. Role identity verification remains mandatory before polling."
    )


def clear_legacy_token_warnings_for_tests() -> None:
    with _LEGACY_WARNINGS_LOCK:
        _LEGACY_WARNINGS_EMITTED.clear()


def resolve_role_bot_token_env(
    role: str,
    *,
    environ: Mapping[str, str] | None = None,
    warn: LogFunction = _print_line,
) -> str:
    """Return the selected env-var name, preferring the role namespace.

    Legacy compatibility is explicit and loud.  Values are never included in
    output, including the missing-configuration error.
    """

    spec = _token_spec(role)
    values = os.environ if environ is None else environ
    if str(values.get(spec.canonical_env, "")).strip():
        return spec.canonical_env
    for legacy_env in spec.legacy_envs:
        if str(values.get(legacy_env, "")).strip():
            _warn_legacy_token(spec, legacy_env, warn)
            return legacy_env
    allowed = ", ".join((spec.canonical_env, *spec.legacy_envs))
    raise RuntimeError(f"{spec.canonical_env} is required for {spec.role}; checked: {allowed}.")


def resolve_role_bot_token(
    role: str,
    *,
    environ: Mapping[str, str] | None = None,
    warn: LogFunction = _print_line,
) -> str:
    values = os.environ if environ is None else environ
    env_name = resolve_role_bot_token_env(role, environ=values, warn=warn)
    return str(values[env_name]).strip()


def normalize_bot_username(value: object | None) -> str:
    return str(value or "").strip().lstrip("@").lower()


class BotIdentityVerificationError(RuntimeError):
    """Safe, token-free startup refusal."""


@dataclass(frozen=True)
class VerifiedTelegramBotIdentity:
    role: str
    expected_username: str
    actual_username: str
    actual_bot_id: int
    expected_bot_id: int | None = None

    @property
    def identity_key(self) -> str:
        # Telegram numeric bot id is stable across an operator-approved
        # username rename.  Usernames remain audited fields, not namespace.
        return f"telegram:bot_id:{self.actual_bot_id}"


_VERIFIED_IDENTITIES: dict[str, VerifiedTelegramBotIdentity] = {}
_VERIFIED_IDENTITIES_LOCK = threading.RLock()


def _expected_identity(
    role: str,
    environ: Mapping[str, str] | None,
) -> tuple[str, int | None]:
    normalized_role = str(role or "").strip().lower()
    values = os.environ if environ is None else environ
    username_env = f"{normalized_role.upper()}_EXPECTED_BOT_USERNAME"
    id_env = f"{normalized_role.upper()}_EXPECTED_BOT_ID"
    expected_username = normalize_bot_username(values.get(username_env))
    if not expected_username:
        raise BotIdentityVerificationError(
            f"{username_env} is required; refusing to start {normalized_role} Telegram polling."
        )
    raw_id = str(values.get(id_env, "")).strip()
    if not raw_id:
        return expected_username, None
    try:
        expected_bot_id = int(raw_id)
    except ValueError as exc:
        raise BotIdentityVerificationError(
            f"{id_env} must be a safe numeric Telegram bot id; refusing to start {normalized_role} polling."
        ) from exc
    if expected_bot_id <= 0:
        raise BotIdentityVerificationError(
            f"{id_env} must be a positive Telegram bot id; refusing to start {normalized_role} polling."
        )
    return expected_username, expected_bot_id


def _verified_identity_from_payload(
    *,
    role: str,
    payload: object,
    environ: Mapping[str, str] | None,
    log: LogFunction,
) -> VerifiedTelegramBotIdentity:
    normalized_role = str(role or "").strip().lower()
    try:
        expected_username, expected_bot_id = _expected_identity(normalized_role, environ)
    except BotIdentityVerificationError as exc:
        log(f"[{normalized_role}_listener] IDENTITY REFUSAL: {exc}")
        raise

    actual_username = normalize_bot_username(getattr(payload, "username", None))
    raw_actual_id = getattr(payload, "id", None)
    try:
        actual_bot_id = int(raw_actual_id)
    except (TypeError, ValueError):
        actual_bot_id = 0

    safe_expected = f"@{expected_username}"
    safe_actual = f"@{actual_username}" if actual_username else "<missing-username>"
    if not actual_username or actual_bot_id <= 0:
        log(
            f"[{normalized_role}_listener] IDENTITY REFUSAL: getMe was unverifiable; "
            f"role={normalized_role} expected={safe_expected} actual={safe_actual}; refusing to poll."
        )
        raise BotIdentityVerificationError(f"{normalized_role} getMe identity was unverifiable; refusing polling.")
    if actual_username != expected_username or (
        expected_bot_id is not None and actual_bot_id != expected_bot_id
    ):
        log(
            f"[{normalized_role}_listener] IDENTITY MISMATCH: role={normalized_role} "
            f"expected={safe_expected} expected_id={expected_bot_id or 'not-configured'} "
            f"actual={safe_actual} actual_id={actual_bot_id}; refusing to poll."
        )
        raise BotIdentityVerificationError(f"{normalized_role} Telegram bot identity mismatch; refusing polling.")

    verified = VerifiedTelegramBotIdentity(
        role=normalized_role,
        expected_username=expected_username,
        actual_username=actual_username,
        actual_bot_id=actual_bot_id,
        expected_bot_id=expected_bot_id,
    )
    with _VERIFIED_IDENTITIES_LOCK:
        _VERIFIED_IDENTITIES[normalized_role] = verified
    log(
        f"[{normalized_role}_listener] identity verified: role={normalized_role} "
        f"username=@{actual_username} bot_id={actual_bot_id}."
    )
    return verified


def get_verified_bot_identity(role: str) -> VerifiedTelegramBotIdentity | None:
    with _VERIFIED_IDENTITIES_LOCK:
        return _VERIFIED_IDENTITIES.get(str(role or "").strip().lower())


def clear_verified_bot_identities_for_tests() -> None:
    with _VERIFIED_IDENTITIES_LOCK:
        _VERIFIED_IDENTITIES.clear()


async def assert_bot_identity(
    bot: object,
    role: str,
    *,
    environ: Mapping[str, str] | None = None,
    log: LogFunction = _print_line,
) -> VerifiedTelegramBotIdentity:
    normalized_role = str(role or "").strip().lower()
    try:
        payload = await bot.get_me()  # type: ignore[attr-defined]
    except Exception as exc:
        # Exception text can contain the token-bearing getMe URL.  Log only the
        # class, which is sufficient and safe for diagnosis.
        log(
            f"[{normalized_role}_listener] IDENTITY REFUSAL: getMe failed "
            f"({exc.__class__.__name__}); refusing to poll."
        )
        raise BotIdentityVerificationError(
            f"{normalized_role} getMe failed ({exc.__class__.__name__}); refusing polling."
        ) from None
    return _verified_identity_from_payload(
        role=normalized_role,
        payload=payload,
        environ=environ,
        log=log,
    )


def install_identity_preflight(
    application: object,
    role: str,
    *,
    environ: Mapping[str, str] | None = None,
    log: LogFunction = _print_line,
) -> object:
    """Compose identity FIRST into PTB's post_init hook.

    PTB executes ``post_init`` after initialization and before polling.  Chief's
    existing queue hook is retained but cannot send until identity passes.
    """

    normalized_role = str(role or "").strip().lower()
    installed_role = getattr(application, "_openclaw_identity_preflight_role", None)
    if installed_role:
        if installed_role != normalized_role:
            raise RuntimeError("Telegram application already has a different role identity preflight.")
        return application

    original_post_init = getattr(application, "post_init", None)

    async def _identity_first_post_init(current_application: object) -> None:
        await assert_bot_identity(
            current_application.bot,  # type: ignore[attr-defined]
            normalized_role,
            environ=environ,
            log=log,
        )
        if original_post_init is not None:
            await original_post_init(current_application)

    application.post_init = _identity_first_post_init  # type: ignore[attr-defined]
    application._openclaw_identity_preflight_role = normalized_role  # type: ignore[attr-defined]
    return application


async def run_verified_polling(
    application: object,
    role: str,
    *,
    stop_event: asyncio.Event | None = None,
    environ: Mapping[str, str] | None = None,
    log: LogFunction = _print_line,
) -> None:
    """Run one PTB application with identity verified before start_polling."""

    install_identity_preflight(application, role, environ=environ, log=log)
    updater = application.updater  # type: ignore[attr-defined]
    if updater is None:
        raise RuntimeError(f"{role} listener application must have an updater.")

    loop = asyncio.get_running_loop()
    resolved_stop_event = stop_event or asyncio.Event()
    registered_signals: list[signal.Signals] = []
    polling_started = False
    app_started = False
    initialized = False

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, resolved_stop_event.set)
            registered_signals.append(sig)
        except (NotImplementedError, RuntimeError):
            pass

    try:
        await application.initialize()  # type: ignore[attr-defined]
        initialized = True
        if application.post_init:  # type: ignore[attr-defined]
            await application.post_init(application)  # type: ignore[attr-defined]
        await updater.start_polling()
        polling_started = True
        await application.start()  # type: ignore[attr-defined]
        app_started = True
        await resolved_stop_event.wait()
    finally:
        for sig in registered_signals:
            try:
                loop.remove_signal_handler(sig)
            except (NotImplementedError, RuntimeError):
                pass
        if polling_started:
            await updater.stop()
        if app_started and application.running:  # type: ignore[attr-defined]
            await application.stop()  # type: ignore[attr-defined]
        if initialized:
            await application.shutdown()  # type: ignore[attr-defined]


def preflight_bot_token_identity(
    token: str,
    role: str,
    *,
    environ: Mapping[str, str] | None = None,
    log: LogFunction = _print_line,
    fetch_json: Callable[[str], Mapping[str, Any]] | None = None,
) -> VerifiedTelegramBotIdentity:
    """Synchronous getMe preflight for launchers such as Hermes."""

    normalized_role = str(role or "").strip().lower()

    def _default_fetch(url: str) -> Mapping[str, Any]:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    fetch = fetch_json or _default_fetch
    try:
        payload = fetch(f"https://api.telegram.org/bot{token}/getMe")
    except Exception as exc:
        log(
            f"[{normalized_role}_listener] IDENTITY REFUSAL: getMe failed "
            f"({exc.__class__.__name__}); refusing startup."
        )
        raise BotIdentityVerificationError(
            f"{normalized_role} getMe failed ({exc.__class__.__name__}); refusing startup."
        ) from None
    if not payload.get("ok") or not isinstance(payload.get("result"), Mapping):
        log(f"[{normalized_role}_listener] IDENTITY REFUSAL: getMe returned no usable identity; refusing startup.")
        raise BotIdentityVerificationError(f"{normalized_role} getMe returned no usable identity.")
    result = payload["result"]
    return _verified_identity_from_payload(
        role=normalized_role,
        payload=type("TelegramGetMeResult", (), dict(result))(),
        environ=environ,
        log=log,
    )


__all__ = [
    "BotIdentityVerificationError",
    "ROLE_BOT_TOKEN_SPECS",
    "RoleBotTokenSpec",
    "VerifiedTelegramBotIdentity",
    "assert_bot_identity",
    "clear_legacy_token_warnings_for_tests",
    "clear_verified_bot_identities_for_tests",
    "get_verified_bot_identity",
    "install_identity_preflight",
    "normalize_bot_username",
    "preflight_bot_token_identity",
    "resolve_role_bot_token",
    "resolve_role_bot_token_env",
    "run_verified_polling",
]
