"""
chief_env.py

Centralized .chief.env loader for the OpenClaw stack.
Standardizes how environment variables are parsed and injected into os.environ.
"""

import os
from pathlib import Path

ENV_PATH = Path("/home/openclaw/.chief.env")

def load_env() -> None:
    """
    Read .chief.env and inject values into os.environ if they are not already set.
    Supports 'export KEY=VALUE' and 'KEY=VALUE' formats.
    """
    if not ENV_PATH.exists():
        return
    try:
        with open(ENV_PATH, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].strip()
                key, value = line.split("=", 1)
                key = key.strip()
                # Remove surrounding quotes
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass

# Automatically load on import to support legacy module-level constant assignments.
load_env()
