"""
hitl_flowchart_gen.py

Generates a Mermaid flowchart of the current HITL (Human-in-the-Loop) approval
architecture from live code metadata.

Reads tier classification counts and module paths dynamically so the diagram
updates automatically when the architecture changes — run it again after edits.

Usage:
    python3 /home/openclaw/hitl_flowchart_gen.py
    python3 /home/openclaw/hitl_flowchart_gen.py --output /path/to/diagram.md
    python3 /home/openclaw/hitl_flowchart_gen.py --mermaid-only
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

BASE = Path(__file__).parent


# ── Metadata loaders ──────────────────────────────────────────────────────────

def _load_policy_meta() -> dict:
    """Import chief_approval_policy and extract live tier metadata."""
    meta: dict = {
        "t0_count": 0,
        "t1_count": 0,
        "t2_count": 0,
        "openshell_active": False,
        "focus_mode_label": "Focus Mode: off",
    }
    policy_path = BASE / "chief_approval_policy.py"
    if not policy_path.exists():
        print(
            f"[hitl_flowchart_gen] WARNING: {policy_path} not found — counts will be 0",
            file=sys.stderr,
        )
        return meta
    try:
        spec = importlib.util.spec_from_file_location("chief_approval_policy", policy_path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        meta["t0_count"] = len(getattr(mod, "_T0_PATTERNS", []))
        meta["t1_count"] = len(getattr(mod, "_T1_PATTERNS", []))
        meta["t2_count"] = len(getattr(mod, "_ALWAYS_T2", []))
        active = getattr(mod, "OPENSHELL_ACTIVE", False)
        meta["openshell_active"] = active
        focus = getattr(mod, "_focus_mode_active", lambda: False)()
        meta["focus_mode_label"] = "Focus Mode: ON (10h)" if focus else "Focus Mode: off"
    except Exception as exc:
        print(
            f"[hitl_flowchart_gen] WARNING: could not load policy module: {exc}",
            file=sys.stderr,
        )
    return meta


def _load_module_paths() -> dict[str, str]:
    """Return canonical HITL module paths, annotating missing files."""
    candidates = {
        "approval_brain": BASE / "chief_approval_brain.py",
        "approval_policy": BASE / "chief_approval_policy.py",
        "approval_bridge": BASE / "chief_approval_bridge.py",
        "guardian_sender": BASE / "chief_guardian_sender.py",
        "guardian_listener": BASE / "chief_guardian_listener.py",
    }
    return {
        name: str(path) if path.exists() else f"{path} [MISSING]"
        for name, path in candidates.items()
    }


def _load_key_paths() -> dict[str, str]:
    """Return canonical state and log file paths used by the HITL system."""
    return {
        "pending_queue": "/mnt/c/OpenClaw/logs/approval_pending.json",
        "audit_log": "/mnt/c/OpenClawShared/openclaw-vault/System/Approval Log.md",
        "guardian_token": "GUARDIAN_BOT_TOKEN (env) → plain-status fallback: CHIEF_BOT_TOKEN",
    }


# ── Mermaid generation ────────────────────────────────────────────────────────

def generate_mermaid(policy_meta: dict, module_paths: dict, key_paths: dict) -> str:
    """
    Build and return a valid Mermaid flowchart string.

    Covers all HITL nodes required by the task spec:
      Intake → Approval Gate → Pending Queue → Execution → Audit Log

    Edge labels embed live tier counts so the diagram reflects actual policy
    rule counts whenever regenerated.
    """
    t0 = policy_meta["t0_count"]
    t1 = policy_meta["t1_count"]
    t2 = policy_meta["t2_count"]
    openshell = "OpenShell: active" if policy_meta["openshell_active"] else "OpenShell: inactive"
    focus = policy_meta["focus_mode_label"]

    # Edge labels must be single-line strings in Mermaid; counts go in node label.
    rules_label = (
        f"Policy Rules<br>"
        f"T0 pass-through: {t0} patterns<br>"
        f"T1 terminal: {t1} patterns<br>"
        f"T2 hard rules: {t2}<br>"
        f"{openshell} | {focus}"
    )

    diagram = f"""\
flowchart TD

    %% ── Intake ─────────────────────────────────────────────────────────
    A([\"Action Request<br>(Claude Code / Brain / Telegram)\"])
    A --> B[\"Intake<br>chief_approval_brain.py\"]
    B --> GATE{{\"Approval Gate<br>chief_approval_policy.classify()\"}};

    %% Policy rule counts node — auto-updated each generation
    GATE -.-> RULES[\"{rules_label}\"]

    %% ── Tier branches ────────────────────────────────────────────────────
    GATE -- \"L0: clearly safe\" --> L0[\"No Gate<br>Proceed immediately\"]
    GATE -- \"L1: medium risk\" --> L1[\"Terminal Prompt\"]
    GATE -- \"L2: high risk / hard rule\" --> PEND

    %% ── L0 path ──────────────────────────────────────────────────────────
    L0 --> EXEC[\"Execute Action\"]

    %% ── L1 path ──────────────────────────────────────────────────────────
    L1 --> TTY{{\"TTY available?\"}};
    TTY -- \"Yes\" --> PROMPT[\"y/N Prompt\"]
    TTY -- \"No (escalate)\" --> PEND
    PROMPT -- \"y\" --> EXEC
    PROMPT -- \"N\" --> DENY[\"Action Denied\"]

    %% ── L2 path — Pending Queue ──────────────────────────────────────────
    PEND[(\"Pending Queue<br>approval_pending.json\")]
    PEND --> GSEND[\"Guardian Bot<br>chief_guardian_sender.py\"]
    GSEND --> WIN{{\"Winship Decision<br>(Telegram)\"}};
    WIN -- \"Approve\" --> EXEC
    WIN -- \"Approve All\" --> EXEC
    WIN -- \"Deny\" --> DENY
    WIN -- \"Delay 5m\" --> GSEND
    WIN -- \"Timeout / no response\" --> DENY

    %% ── Execution & Audit ────────────────────────────────────────────────
    EXEC --> AUDIT[(\"Audit Log<br>Approval Log.md\")]
    DENY --> AUDIT

    %% ── Styling ──────────────────────────────────────────────────────────
    classDef gate    fill:#f9a825,stroke:#e65100,color:#000
    classDef phone   fill:#6a1b9a,stroke:#4a148c,color:#fff
    classDef exec    fill:#2e7d32,stroke:#1b5e20,color:#fff
    classDef deny    fill:#c62828,stroke:#b71c1c,color:#fff
    classDef store   fill:#1565c0,stroke:#0d47a1,color:#fff
    classDef info    fill:#37474f,stroke:#263238,color:#cfd8dc

    class GATE,TTY,WIN gate
    class GSEND phone
    class EXEC exec
    class DENY deny
    class AUDIT,PEND store
    class RULES info
"""
    return diagram.strip()


# ── Output builder ────────────────────────────────────────────────────────────

def build_output(
    mermaid: str,
    policy_meta: dict,
    module_paths: dict,
    key_paths: dict,
    wrap_md: bool = True,
) -> str:
    """Wrap Mermaid in a markdown document with live metadata annotations."""
    if not wrap_md:
        return mermaid

    openshell_flag = "**active**" if policy_meta["openshell_active"] else "inactive"
    lines = [
        "# HITL Architecture Flowchart",
        "",
        "_Generated by `hitl_flowchart_gen.py` from live code metadata._",
        "_Regenerate this file after architecture changes to keep it current._",
        "",
        "## Policy Summary",
        "",
        f"| Tier | Label | Rule Count |",
        f"|------|-------|------------|",
        f"| L0   | pass-through (no gate) | {policy_meta['t0_count']} patterns |",
        f"| L1   | terminal prompt        | {policy_meta['t1_count']} patterns |",
        f"| L2   | phone approval (hard)  | {policy_meta['t2_count']} hard rules |",
        "",
        f"- OpenShell enforcement: {openshell_flag}",
        f"- {policy_meta['focus_mode_label']}",
        "",
        "## Module Sources",
        "",
    ]
    for name, path in module_paths.items():
        tag = " ⚠ MISSING" if "[MISSING]" in path else ""
        lines.append(f"- `{name}`: `{path}`{tag}")

    lines += [
        "",
        "## State Files",
        "",
    ]
    for name, path in key_paths.items():
        lines.append(f"- `{name}`: `{path}`")

    lines += [
        "",
        "## Flowchart",
        "",
        "```mermaid",
        mermaid,
        "```",
        "",
    ]
    return "\n".join(lines)


# ── CLI entry point ───────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate HITL Mermaid flowchart from live OpenClaw architecture metadata"
    )
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Write output to FILE instead of stdout",
    )
    parser.add_argument(
        "--mermaid-only",
        action="store_true",
        help="Output raw Mermaid syntax only (no markdown wrapper)",
    )
    args = parser.parse_args(argv)

    policy_meta = _load_policy_meta()
    module_paths = _load_module_paths()
    key_paths = _load_key_paths()

    mermaid = generate_mermaid(policy_meta, module_paths, key_paths)
    output = build_output(
        mermaid, policy_meta, module_paths, key_paths,
        wrap_md=not args.mermaid_only,
    )

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output, encoding="utf-8")
        print(f"[hitl_flowchart_gen] Written to {out_path}", file=sys.stderr)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
