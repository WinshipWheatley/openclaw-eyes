"""
chief_output_utils.py

Shared output utilities for the OpenClaw stack.

Provides final-output normalization helpers used across Cassandra,
Chief, and any other surface that sends plain-text or TTS output.

Public API
----------
tts_clean(text)   -- strip markdown artifacts for TTS-safe, plain-text output
"""

import re


def tts_clean(text: str) -> str:
    """
    Strip markdown artifacts that TTS reads literally, or that appear as
    unwanted literal characters in plain-text Telegram output.
    No-op on already-clean output.
    """
    # Markdown URLs ([text](url) → text) — before underscore pass
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Double-underscore bold (__bold__ → bold) — before single-underscore pass
    text = re.sub(r'__([^_]+)__', r'\1', text)
    # Single-underscore italic (_italic_ → italic)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    # Horizontal rules (lines of only -, *, or _, 3+)
    text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)
    # Heading markers at line start
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Bold (**text**) — before single-asterisk pass
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    # Italics (*text*)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # Inline code (`text`)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Bullet markers at line start
    text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
    # Collapse excess blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
