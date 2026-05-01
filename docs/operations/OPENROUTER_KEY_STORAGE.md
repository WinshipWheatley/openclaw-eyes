# OpenRouter Key Storage

Do not use `cat`, `sed`, `grep`, `head`, `tail`, `echo`, command substitution, or any command output to display the secret file. Agents should locate the key file and verify metadata or presence only; they must not reveal the key value in chat, logs, terminal output, diffs, or commits.

## Architecture Boundary

OpenRouter support exists only as guarded optional backend plumbing. It is provider metadata and a possible future expert-lane option, not a default model, not a standing runner, and not an authorization to perform live external execution.

Documentation alone does not authorize OpenRouter calls. External providers may only be used for sanitized, non-sensitive work after explicit operator approval, policy checks, and the relevant runtime guards. Sensitive or private work remains local-only by default.

This document does not authorize Kimi, Codex, Gemini, OpenRouter, or other external runner wiring. It also does not authorize service, timer, scheduler, Legal-lane, Hermes, Gmail, or Telegram changes.

## Secret Location

The OpenRouter API key is stored outside the repository at:

```text
~/.config/openclaw/secrets/openrouter.env
```

Expected permissions:

```text
~/.config/openclaw                 700
~/.config/openclaw/secrets         700
~/.config/openclaw/secrets/openrouter.env 600
```

## Helper Commands

Use this to save or replace the key through a hidden prompt:

```bash
save-openrouter-key
```

Use this wrapper only inside a separately approved, policy-checked session where OpenClaw should run with the OpenRouter key available:

```bash
openclaw-or
```

The wrapper sources the env file, then executes:

```bash
openclaw "$@"
```

This setup does not change OpenClaw's default model. Do not run `openclaw models set`, provider live calls, or runner wiring as part of key storage or verification.

## Safe Agent Request

Use language like this when asking an agent to find the key location without seeing the key:

```text
Find where OpenClaw stores my OpenRouter API key, but do not reveal the key.
Do not cat, sed, grep, head, tail, print, echo, or display the secret file contents.
Only report whether this file exists and its permissions:
~/.config/openclaw/secrets/openrouter.env

If you need to verify the key is present, source it only inside a subshell and print pass/fail only.
Do not print OPENROUTER_API_KEY or include it in command output.
```

Safe verification commands are limited to metadata and non-printing presence checks:

```bash
ls -ld "$HOME/.config/openclaw" "$HOME/.config/openclaw/secrets"
ls -l "$HOME/.config/openclaw/secrets/openrouter.env"
( source "$HOME/.config/openclaw/secrets/openrouter.env" && test -n "${OPENROUTER_API_KEY:-}" )
```
