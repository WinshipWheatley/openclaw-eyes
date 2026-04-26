#!/usr/bin/env python3
"""Read-only drift check for Cassandra capability doctrine surfaces.

Compares the live Cassandra runtime authority against the cross-agent registry
answer surface. This script only reports drift; it does not change behavior.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path("/home/openclaw")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CAPABILITY_FILE = ROOT / "cassandra_capability.py"
BRAIN_FILE = ROOT / "cassandra_brain.py"


CHECKS = [
    {
        "label": "future_exec",
        "registry_name": "future_exec",
        "runtime_flag": "FUTURE_ACTION_CONNECTED",
        "note_markers": (),
    },
    {
        "label": "payment_verify",
        "registry_name": "payment_verify",
        "runtime_flag": "PAYMENT_METADATA_CONNECTED",
        "note_markers": (),
    },
    {
        "label": "file_verify",
        "registry_name": "file_verify",
        "runtime_flag": "FILE_VERIFY_CONNECTED",
        "note_markers": (
            "If asked whether a specific file or path exists, say only that you can't verify it from here.",
            "I can't verify file or path existence from here.",
        ),
    },
    {
        "label": "email_draft",
        "registry_name": "email_draft",
        "runtime_flag": "EMAIL_DRAFT_CONNECTED",
        "note_markers": (),
    },
    {
        "label": "email_send",
        "registry_name": "email_send",
        "runtime_flag": "EMAIL_SEND_CONNECTED",
        "note_markers": (),
    },
    {
        "label": "calendar",
        "registry_name": "calendar_read",
        "runtime_flag": "CALENDAR_CONNECTED",
        "note_markers": (),
    },
]


def _load_runtime_flags() -> dict[str, bool]:
    import cassandra_capability as capability

    flags = {}
    for name in dir(capability):
        if not name.endswith("_CONNECTED"):
            continue
        value = getattr(capability, name)
        if isinstance(value, bool):
            flags[name] = value
    return flags


def _load_registry_caps() -> dict[str, object]:
    import capability_registry

    actor = capability_registry.get_actor("cassandra")
    if actor is None:
        return {}
    return {cap.name: cap for cap in actor.capabilities}


def _load_capability_note() -> str:
    tree = ast.parse(BRAIN_FILE.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "_CAPABILITY_NOTE" for t in node.targets):
            continue
        value = ast.literal_eval(node.value)
        return value if isinstance(value, str) else ""
    return ""


def _status(value: bool | None) -> str:
    if value is True:
        return "CONNECTED"
    if value is False:
        return "NOT CONNECTED"
    return "MISSING"


def main() -> int:
    runtime_flags = _load_runtime_flags()
    registry_caps = _load_registry_caps()
    capability_note = _load_capability_note()

    mapped_runtime_flags = {check["runtime_flag"] for check in CHECKS}
    mapped_registry_caps = {check["registry_name"] for check in CHECKS}

    contradictions: list[str] = []

    print("RUNTIME AUTHORITY")
    print(f"  source: {CAPABILITY_FILE}")
    for check in CHECKS:
        flag = check["runtime_flag"]
        print(f"  {check['label']}: {flag} = {_status(runtime_flags.get(flag))}")

    print()
    print("REGISTRY ANSWER SURFACE")
    print(f"  source: {ROOT / 'capability_registry.py'}")
    for check in CHECKS:
        cap = registry_caps.get(check["registry_name"])
        status = _status(cap.connected if cap is not None else None)
        caveat = f" ({cap.caveats})" if cap is not None and cap.caveats else ""
        print(f"  {check['label']}: {check['registry_name']} = {status}{caveat}")

    print()
    print("CONTRADICTIONS")
    for check in CHECKS:
        cap = registry_caps.get(check["registry_name"])
        runtime_value = runtime_flags.get(check["runtime_flag"])
        registry_value = cap.connected if cap is not None else None
        if runtime_value is None or registry_value is None:
            continue
        if runtime_value != registry_value:
            contradictions.append(
                f"{check['label']}: runtime {check['runtime_flag']} is {_status(runtime_value)}; "
                f"registry {check['registry_name']} is {_status(registry_value)}"
            )
        if runtime_value is True:
            for marker in check["note_markers"]:
                if marker in capability_note:
                    contradictions.append(
                        f"{check['label']}: runtime {check['runtime_flag']} is CONNECTED; "
                        f"cassandra_brain._CAPABILITY_NOTE still says: {marker}"
                    )

    if contradictions:
        for item in contradictions:
            print(f"  - {item}")
    else:
        print("  none")

    runtime_missing_registry = sorted(set(runtime_flags) - mapped_runtime_flags)
    registry_missing_runtime = sorted(set(registry_caps) - mapped_registry_caps)

    print()
    print("MISSING COVERAGE")
    if runtime_missing_registry:
        print("  runtime flags with no Cassandra registry mapping:")
        for name in runtime_missing_registry:
            print(f"  - {name} = {_status(runtime_flags[name])}")
    else:
        print("  runtime flags with no Cassandra registry mapping: none")

    if registry_missing_runtime:
        print("  registry capabilities with no runtime flag mapping:")
        for name in registry_missing_runtime:
            cap = registry_caps[name]
            print(f"  - {name} = {_status(cap.connected)}")
    else:
        print("  registry capabilities with no runtime flag mapping: none")

    has_missing = bool(runtime_missing_registry or registry_missing_runtime)
    return 1 if contradictions or has_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
