"""
harness_context.py

Centralized authority for OpenClaw harness and staging mode.
Governs path redirection, side-effect suppression, and clock injection.
"""

import json
import os
from datetime import datetime
from pathlib import Path

_HARNESS_VAR = "OPENCLAW_HARNESS"
_FIXTURE_VAR = "OPENCLAW_FIXTURE"
_PROFILE_VAR = "OPENCLAW_FIXTURE_PROFILE"
_REPLAY_TIME_VAR = "OPENCLAW_REPLAY_TIME"
_STAGING_ROOT = Path("/home/openclaw/staging")
_CONFIG_PATH = Path(__file__).parent / "harness_config.json"

_config_data = {}
try:
    if _CONFIG_PATH.exists():
        _config_data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    elif os.environ.get(_HARNESS_VAR) == "1":
        raise FileNotFoundError(f"Config file not found at {_CONFIG_PATH}")
except Exception as exc:
    msg = f"[harness] FATAL: failed to load harness_config.json: {exc}"
    if os.environ.get(_HARNESS_VAR) == "1":
        print(msg)
        raise RuntimeError(msg) from exc
    print(f"[harness] WARN: {msg} (Continuing in non-harness mode)")


def _get_config_section(key: str, default):
    return _config_data.get(key, default)


_fixture_data = None


def _validate_fixture(data: dict, profile_name: str):
    """
    Validate a fixture against a profile defined in harness_config.json.
    Fails fast with ValueError if incomplete.
    """
    profiles = _get_config_section("validation_profiles", {})
    profile = profiles.get(profile_name)
    if not profile:
        if os.environ.get(_HARNESS_VAR) == "1":
            raise ValueError(f"Validation profile '{profile_name}' not found in harness_config.json")
        return

    required_top = profile.get("required_top", [])
    required_inputs = profile.get("required_inputs", [])

    missing = [key for key in required_top if key not in data]
    if missing:
        raise ValueError(
            f"Fixture missing required top-level keys for profile '{profile_name}': {', '.join(missing)}"
        )

    if required_inputs:
        inputs = data.get("inputs", {})
        if not isinstance(inputs, dict):
            raise ValueError(f"Fixture 'inputs' must be a dictionary for profile '{profile_name}'")

        missing_inputs = [key for key in required_inputs if key not in inputs]
        if missing_inputs:
            raise ValueError(
                f"Fixture 'inputs' missing required keys for profile '{profile_name}': {', '.join(missing_inputs)}"
            )


def _load_fixture():
    global _fixture_data
    if _fixture_data is not None:
        return _fixture_data

    fixture_path = os.environ.get(_FIXTURE_VAR)
    if not fixture_path:
        _fixture_data = {}
        return _fixture_data

    path = Path(fixture_path)
    if not path.exists():
        msg = f"[harness] FATAL: fixture not found at {fixture_path}"
        print(msg)
        raise FileNotFoundError(msg)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        profile = os.environ.get(_PROFILE_VAR, "morning_brief")
        _validate_fixture(data, profile)
        _fixture_data = data
        print(f"[harness] loaded and validated fixture (profile: {profile}) from {fixture_path}")
    except Exception as exc:
        msg = f"[harness] FATAL: failed to load or validate fixture {fixture_path}: {exc}"
        print(msg)
        raise

    return _fixture_data


def is_harness_mode() -> bool:
    """Return True if the OpenClaw harness is explicitly enabled via environment."""
    return os.environ.get(_HARNESS_VAR) == "1"


def get_root(path: Path) -> Path:
    """Return a redirected path in harness mode, otherwise return the original path."""
    if not is_harness_mode():
        return path

    redirects = _get_config_section("redirects", {})
    abs_path = str(path.absolute())
    for src, dst in redirects.items():
        if abs_path.startswith(src):
            return Path(abs_path.replace(src, dst))

    return path


def now() -> datetime:
    """
    Return current system time, or a fixed replay time if configured.
    """
    replay_env = os.environ.get(_REPLAY_TIME_VAR)
    if replay_env:
        try:
            return datetime.fromisoformat(replay_env)
        except Exception:
            pass

    fixture = _load_fixture()
    fixture_now = fixture.get("now")
    if fixture_now:
        try:
            return datetime.fromisoformat(fixture_now)
        except Exception:
            pass

    return datetime.now()


def get_fixture(key: str, default=None):
    """Return a value from the loaded fixture, or default."""
    if not is_harness_mode():
        return default
    return _load_fixture().get(key, default)


def verify_golden(actual: str, golden_key: str = "text"):
    """
    Compare actual output against a golden result in the fixture.
    Reports PASS/FAIL to stdout.
    """
    if not is_harness_mode():
        return

    golden = get_fixture("golden")
    if not golden or not isinstance(golden, dict):
        print("[harness] SKIP: No 'golden' dictionary found in fixture for comparison.")
        return

    expected = golden.get(golden_key)
    if expected is None:
        print(f"[harness] SKIP: Golden key '{golden_key}' not found in fixture.")
        return

    actual_text = str(actual or "").strip()
    expected_text = str(expected or "").strip()

    if actual_text == expected_text:
        print(f"[harness] PASS: Output matches golden '{golden_key}'.")
        diff_path = _STAGING_ROOT / "golden_mismatch.json"
        if diff_path.exists():
            try:
                diff_path.unlink()
            except Exception:
                pass
        return

    print(f"[harness] FAIL: Output MISMATCH with golden '{golden_key}'.")
    print(f"[harness] EXPECTED: {expected_text[:100]}...")
    print(f"[harness] ACTUAL:   {actual_text[:100]}...")

    report = {
        "status": "mismatch",
        "golden_key": golden_key,
        "metadata": {
            "timestamp": now().isoformat(),
            "fixture": os.environ.get(_FIXTURE_VAR, "unknown"),
            "profile": os.environ.get(_PROFILE_VAR, "morning_brief"),
        },
        "expected": expected_text,
        "actual": actual_text,
    }

    _STAGING_ROOT.mkdir(parents=True, exist_ok=True)
    diff_path = _STAGING_ROOT / "golden_mismatch.json"
    try:
        diff_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"[harness] Mismatch artifact written to {diff_path}")
    except Exception as err:
        print(f"[harness] ERROR: failed to write mismatch artifact: {err}")
