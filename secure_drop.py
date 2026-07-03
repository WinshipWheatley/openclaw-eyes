"""Secure-drop — paste a sensitive value into the vault with zero exposure.

Operator ask (2026-07-02): "anytime the system needs me to drop data that may be
sensitive, have a terminal pop up where all I gotta do is copy and paste into that
slot." This is that slot.

Invariants (the whole point):
- The secret is read via getpass — no terminal echo, never from argv or env.
- It is written atomically to the target env file, preserving every other line,
  and the file is chmod'd owner-only.
- The value NEVER touches stdout, a log, an exception message, an LLM, or the
  process argument list. Confirmations show a character COUNT, never the value.
- Only pre-registered secret SLOTS may be written (no arbitrary file paths).

Usage (operator, in a terminal):
    python3 secure_drop.py maestro_bot_token
    # -> "Paste MAESTRO_BOT_TOKEN (input hidden): " -> paste -> Enter
    # -> "Wrote MAESTRO_BOT_TOKEN to /home/openclaw/.chief.env (42 chars). Restart: maestro-listener"

A slot is requested programmatically by the system when it needs sensitive input;
the operator runs the one command it names. The pop-up launcher (Windows Terminal
on WSL) is secure_drop_popup.sh.
"""

from __future__ import annotations

import argparse
import getpass
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class SecretSlot:
    key: str                       # env var name, e.g. MAESTRO_BOT_TOKEN
    env_file: Path                 # destination env file, e.g. ~/.chief.env
    label: str = ""                # human description shown in the prompt
    restart_services: tuple[str, ...] = field(default_factory=tuple)  # systemctl --user units


DEFAULT_ENV_FILE = Path("/home/openclaw/.chief.env")


def default_slots() -> dict[str, SecretSlot]:
    """The registry of known sensitive-input slots. Extend as the system grows;
    a slot must exist here before secure_drop will write it."""
    return {
        "maestro_bot_token": SecretSlot(
            key="TELEGRAM_BOT_TOKEN", env_file=DEFAULT_ENV_FILE,
            label="Maestro / billing-brain Telegram bot token (the one that leaked; rotate via BotFather)",
            restart_services=("maestro-listener", "openclaw-request-response",
                              "chief-worker", "chief-watcher-brain"),
        ),
        "cassandra_bot_token": SecretSlot(
            key="CASSANDRA_BOT_TOKEN", env_file=DEFAULT_ENV_FILE,
            label="Cassandra Telegram bot token", restart_services=("cassandra-listener",),
        ),
        "guardian_bot_token": SecretSlot(
            key="GUARDIAN_BOT_TOKEN", env_file=DEFAULT_ENV_FILE,
            label="Guardian Telegram bot token", restart_services=("chief-guardian-listener",),
        ),
        "niles_bot_token": SecretSlot(
            key="PRODUCER_BOT_TOKEN", env_file=DEFAULT_ENV_FILE,
            label="Niles / producer Telegram bot token", restart_services=("niles-listener",),
        ),
        "openrouter_api_key": SecretSlot(
            key="OPENROUTER_API_KEY", env_file=DEFAULT_ENV_FILE,
            label="OpenRouter prepaid API key (external model ladder — only if you opt in)",
        ),
    }


def _read_secret(prompt: str) -> str:
    """Hidden input via getpass. Separated so tests can inject without a TTY."""
    return getpass.getpass(prompt)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".secure_drop_", suffix=".tmp")
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _upsert_env_line(existing: str, key: str, value: str) -> str:
    """Return env-file text with key=value, replacing an existing KEY= line in place
    (preserving order and every other line) or appending if absent. Handles an
    optional leading `export `."""
    lines = existing.splitlines()
    out: list[str] = []
    replaced = False
    for line in lines:
        stripped = line.lstrip()
        prefix = "export " if stripped.startswith("export ") else ""
        bare = stripped[len(prefix):]
        if bare.split("=", 1)[0].strip() == key and "=" in bare:
            out.append(f"{prefix}{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{key}={value}")
    return "\n".join(out) + "\n"


def drop_secret(
    slot_name: str,
    *,
    slots: Mapping[str, SecretSlot] | None = None,
    announce: bool = False,
) -> dict[str, object]:
    """Prompt (hidden) for a secret and write it to its slot's env file. Returns a
    receipt that NEVER contains the value."""
    registry = dict(slots) if slots is not None else default_slots()
    if slot_name not in registry:
        raise KeyError(f"unknown secret slot: {slot_name!r} (known: {sorted(registry)})")
    slot = registry[slot_name]
    label = slot.label or slot.key
    value = _read_secret(f"Paste {slot.key} — {label}\n(input hidden; paste + Enter): ")
    value = value.strip()
    if not value:
        if announce:
            print("No input received — nothing changed.")
        return {"status": "empty_no_change", "key": slot.key, "chars": 0}

    env_file = Path(slot.env_file)
    existing = env_file.read_text(encoding="utf-8") if env_file.exists() else ""
    updated = _upsert_env_line(existing, slot.key, value)
    _atomic_write(env_file, updated)

    chars = len(value)
    del value  # drop the plaintext from memory promptly
    receipt = {
        "status": "written",
        "key": slot.key,
        "env_file": str(env_file),
        "chars": chars,
        "restart_services": list(slot.restart_services),
    }
    if announce:
        print(f"Wrote {slot.key} to {env_file} ({chars} chars). The value was not shown or logged.")
        if slot.restart_services:
            print("Now restart: systemctl --user restart " + " ".join(slot.restart_services))
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Securely paste a sensitive value into the OpenClaw vault (hidden input; never logged)."
    )
    parser.add_argument("slot", nargs="?", help="which secret slot to fill")
    parser.add_argument("--list", action="store_true", help="list known secret slots")
    args = parser.parse_args(argv)

    registry = default_slots()
    if args.list or not args.slot:
        print("Known secret slots (run: python3 secure_drop.py <slot>):")
        for name, slot in registry.items():
            print(f"  {name:22s} -> {slot.key}  ({slot.label})")
        return 0
    try:
        drop_secret(args.slot, announce=True)
    except KeyError as exc:
        print(str(exc))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
