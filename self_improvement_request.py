"""Self-improvement loop — close the circle: the agent recommends a REAL gap in conversation;
if the operator agrees, it files that gap's build_goal as a build request through the
agent-request factory (admit_with_safety_check -> PROPOSED + Guardian approval). When Guardian
approves, the factory builds it, and the agent actually gets better.

Grounded by construction: only the curated gaps in self_knowledge can be filed (never a
model-invented "improvement"). Everything is keyed by conversation_id and fail-open.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Optional

_DEFAULT_STORE = Path("/home/openclaw/.openclaw/self_improvement_recommendations.json")
_CHIEF_ENV = Path("/home/openclaw/.chief.env")
_SAFE_TASK_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_TERMINAL_TASK_STATUSES = {"DONE", "BLOCKED", "DEAD"}
_TASK_PACKAGE_REQUIRED_PAYLOAD_FIELDS = (
    "goal",
    "success_criteria",
    "tests_to_run",
    "allowed_files",
    "forbidden_actions",
    "stop_conditions",
)


class SelfImprovementPackageError(ValueError):
    """Raised when a self-improvement gap has no bounded builder package profile."""


def _ensure_chief_env(*, path: Path = _CHIEF_ENV) -> None:
    """Load the canonical secrets file into os.environ for any keys that are ABSENT, so the
    Guardian build-approval send works even from a minimal (cron) environment. The live env
    always wins; missing/malformed file is silently ignored. Mirrors master_voice.sh's own
    `source .chief.env`, so the autonomous loops can actually reach the operator."""
    import os

    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except Exception:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val

# Operator agreement to "want me to get that built?". Kept tight so a stray "yeah" mid-other-
# topic doesn't fire — but generous enough for natural yeses.
_AGREEMENT_MARKERS = (
    "yeah do it", "yes do it", "do it", "go for it", "go ahead", "build it", "request it",
    "make it happen", "let's do it", "lets do it", "yes please", "yep", "sounds good",
    "sure", "please do", "make it so", "ship it",
)
_AGREEMENT_EXACT = {"yes", "yeah", "yep", "yup", "ok", "okay", "do it"}


def is_agreement(message: str) -> bool:
    low = f" {str(message or '').lower().strip()} "
    if low.strip() in _AGREEMENT_EXACT:
        return True
    return any(a in low for a in _AGREEMENT_MARKERS)


# ── recommendation store (keyed by conversation_id) ───────────────────────────
def _load(store: Path) -> dict:
    try:
        return json.loads(Path(store).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(store: Path, data: dict) -> None:
    p = Path(store)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")


def record_recommendation(conversation_id: str, gap_id: str, *, store: Path = _DEFAULT_STORE) -> None:
    if not conversation_id or not gap_id:
        return
    data = _load(store)
    data[conversation_id] = gap_id
    _save(store, data)


def get_pending_recommendation(conversation_id: str, *, store: Path = _DEFAULT_STORE) -> Optional[str]:
    return _load(store).get(conversation_id)


def clear_recommendation(conversation_id: str, *, store: Path = _DEFAULT_STORE) -> None:
    data = _load(store)
    if conversation_id in data:
        del data[conversation_id]
        _save(store, data)


# ── filing the real request ────────────────────────────────────────────────────
_COMMON_ALLOWED_ACTIONS = [
    "Inspect and edit only the files listed in allowed_files.",
    "Run the listed pytest commands and lightweight local inspections needed to explain the change.",
    "Leave unrelated dirty work in the repository untouched.",
]

_COMMON_FORBIDDEN_ACTIONS = [
    "Do not send external messages, emails, texts, webhooks, or API calls.",
    "Do not spend money, initiate payments, move funds, or touch banking workflows.",
    "Do not read, print, create, or modify secrets, credentials, token vaults, or .env files.",
    "Do not edit crontab, systemd units, production service state, or restart production.",
    "Do not widen allowed_files; stop and ask for a new bounded package if more files are required.",
]

_COMMON_STOP_CONDITIONS = [
    "Stop if the fix requires files outside allowed_files.",
    "Stop if verification requires live external services, real sends, money movement, or production restarts.",
    "Stop if tests expose an unrelated failure that would require broad refactoring.",
    "Stop if the observed metric no longer reproduces and document the non-repro instead of changing code.",
]

_SELF_IMPROVEMENT_PACKAGE_PROFILES: dict[str, dict[str, Any]] = {
    "high_fallback": {
        "scope": [
            "Use self_monitor evidence and protected_generate/front-door receipts to identify why the brain falls back.",
            "Fix the front-door generation, validation, timeout, or receipt classification path inside the listed files only.",
            "Keep fallback receipts truthful; do not hide a fallback by relabeling telemetry.",
        ],
        "allowed_files": [
            "protected_generate.py",
            "frontdoor_prompt.py",
            "chief_llm.py",
            "maestro_cassandra_responder.py",
            "self_monitor.py",
            "tests/test_frontdoor_model_profile.py",
            "tests/test_maestro_cassandra_responder.py",
            "tests/test_self_monitor.py",
        ],
        "success_criteria": [
            "The top measured fallback reason is addressed or a narrower blocked finding is documented with evidence.",
            "Model-ok, timeout, empty-output, validation-failed, and no-fitting-model receipts remain accurately classified.",
            "The deterministic fallback path still fails closed for grounded factual answers when no packet supports the answer.",
            "The self-monitor finding has a clear way to re-measure whether fallback rate improved on the next cycle.",
        ],
        "tests_to_run": [
            "/home/openclaw/chief_env/bin/python -m pytest -q tests/test_frontdoor_model_profile.py tests/test_maestro_cassandra_responder.py tests/test_self_monitor.py",
        ],
    },
    "agent_voices_cross_board": {
        "scope": [
            "Trace the conversational reply surfaces that already call the front-door brain.",
            "Pass the correct agent id into existing voice/profile-aware prompt or generation calls.",
            "Keep each agent inside its current authority boundary; this is voice/routing, not new authority.",
        ],
        "allowed_files": [
            "frontdoor_prompt.py",
            "protected_generate.py",
            "maestro_cassandra_responder.py",
            "agent_voice_profiles.py",
            "agent_kokoro_voice.py",
            "cassandra_brain.py",
            "cassandra_listener.py",
            "chief_listener.py",
            "niles_memory_worker.py",
            "tests/test_agent_voice_delivery_contracts.py",
            "tests/test_maestro_cassandra_responder.py",
            "tests/test_synthetic_agent_response_e2e.py",
            "tests/test_cassandra_status_wiring.py",
        ],
        "success_criteria": [
            "Cassandra, Niles, Chief, Hermes, Guardian, and Maestro retain distinct stable voice/profile identities.",
            "Reply surfaces that already use the conversational brain pass an explicit agent id where supported.",
            "No agent gains send, ledger, calendar, repo, or payment authority from the voice change.",
        ],
        "tests_to_run": [
            "/home/openclaw/chief_env/bin/python -m pytest -q tests/test_agent_voice_delivery_contracts.py tests/test_maestro_cassandra_responder.py tests/test_synthetic_agent_response_e2e.py tests/test_cassandra_status_wiring.py",
        ],
    },
    "predictive_on_it": {
        "scope": [
            "Make the fast acknowledgment depend on request shape and expected response cost instead of only a fixed delay.",
            "Keep casual/short replies quiet when they are expected to answer quickly.",
            "Keep the acknowledgment short, conversational, and separate from task-completion framing.",
        ],
        "allowed_files": [
            "maestro_listener.py",
            "tests/test_maestro_fast_ack.py",
        ],
        "success_criteria": [
            "Fast ack remains enabled by default but only fires for requests predicted to exceed the configured threshold.",
            "Casual short messages do not get unnecessary proactive acknowledgments.",
            "Existing text override behavior and ack phrasing tests continue to pass.",
        ],
        "tests_to_run": [
            "/home/openclaw/chief_env/bin/python -m pytest -q tests/test_maestro_fast_ack.py",
        ],
    },
    "email_after_proof": {
        "scope": [
            "Extend only the self-test/proof accounting for email autonomy readiness.",
            "Do not enable real external sends in this package; produce the next Guardian-gated proof boundary only.",
            "Preserve Gmail intent denials for generic or explicitly no-Gmail prompts.",
        ],
        "allowed_files": [
            "agent_email_loopback.py",
            "cassandra_brain.py",
            "tests/test_agent_email_loopback.py",
            "tests/test_gmail_intent_gate.py",
        ],
        "success_criteria": [
            "Self-test loops can be counted or evaluated without sending to anyone except the configured self-test address.",
            "No real external send path is enabled by this build package.",
            "Gmail polling and send-adjacent behavior remains denied for generic and explicit no-Gmail prompts.",
        ],
        "tests_to_run": [
            "/home/openclaw/chief_env/bin/python -m pytest -q tests/test_agent_email_loopback.py tests/test_gmail_intent_gate.py",
        ],
        "forbidden_actions": [
            "Do not enable or perform real external email sends; only self-test proof accounting is in scope.",
        ],
    },
    "no_response_maestro": {
        "scope": [
            "Use no_response_watchdog evidence to join deposited bridge requests against response receipts by source_request_filename/source_request_id.",
            "Diagnose listener/processor service state read-only; do not auto-restart production services.",
            "Keep any recovery proposal Guardian-gated and preserve per-agent lane attribution.",
        ],
        "allowed_files": [
            "no_response_watchdog.py",
            "hermes_observer.py",
            "self_improvement_request.py",
            "maestro_listener.py",
            "openclaw_request_processor.py",
            "tests/test_no_response_watchdog.py",
            "tests/test_hermes_observer.py",
        ],
        "success_criteria": [
            "Old unanswered requests emit one grounded suggestion per affected agent/lane.",
            "Requests with a matching terminal response or processing marker do not fire.",
            "The Hermes fleet loop routes the suggestion through the existing Chief/Guardian gate without auto-restart.",
        ],
        "tests_to_run": [
            "/home/openclaw/chief_env/bin/python -m pytest -q tests/test_no_response_watchdog.py tests/test_hermes_observer.py",
        ],
    },
}


def _nonempty_package_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, (list, tuple, set)):
        return any(_nonempty_package_value(item) for item in value)
    return value is not None


def _safe_task_id_fragment(value: str) -> str:
    safe = _SAFE_TASK_ID_RE.sub("_", str(value or "")).strip("._")
    return safe or "gap"


def _list_profile_value(profile: dict[str, Any], key: str) -> list[str]:
    value = profile.get(key) or []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(item).strip() for item in value if str(item).strip()]


def compile_self_improvement_package(gap: dict, *, agent: str = "maestro") -> dict:
    """Turn a known self-improvement gap into a bounded builder package.

    The worker refuses incomplete packages. This compiler refuses unknown gap ids instead
    of inventing broad file scope, so autonomous detection can be powerful without becoming
    a vague "go modify the system" task.
    """
    gap_id = str(gap.get("id") or "").strip()
    if not gap_id:
        raise SelfImprovementPackageError("self-improvement gap is missing id")
    profile = _SELF_IMPROVEMENT_PACKAGE_PROFILES.get(gap_id)
    if profile is None:
        raise SelfImprovementPackageError(f"no bounded package profile for gap {gap_id!r}")
    goal = str(gap.get("build_goal") or "").strip()
    if not goal:
        raise SelfImprovementPackageError(f"gap {gap_id!r} is missing build_goal")

    forbidden_actions = _COMMON_FORBIDDEN_ACTIONS + _list_profile_value(profile, "forbidden_actions")
    payload = {
        "title": str(gap.get("say") or gap_id).strip(),
        "goal": goal,
        "source": "agent_self_improvement",
        "requested_by": str(agent or "maestro"),
        "self_improvement_gap_id": gap_id,
        "self_improvement_agent": str(agent or "maestro"),
        "evidence": str(gap.get("evidence") or "").strip(),
        "scope": _list_profile_value(profile, "scope"),
        "success_criteria": _list_profile_value(profile, "success_criteria"),
        "tests_to_run": _list_profile_value(profile, "tests_to_run"),
        "allowed_files": _list_profile_value(profile, "allowed_files"),
        "forbidden_files": [
            ".chief.env",
            ".env",
            "token_vault*",
            "polish_loop/control_plane.sqlite3",
            "/mnt/c/OpenClaw/logs/*",
        ],
        "allowed_actions": list(_COMMON_ALLOWED_ACTIONS),
        "forbidden_actions": forbidden_actions,
        "stop_conditions": list(_COMMON_STOP_CONDITIONS),
        "output_contract": [
            "Explain the root cause, files changed, tests run, and any remaining blocked scope.",
            "Include before/after reasoning for how the next self-monitor cycle can measure improvement.",
        ],
        "help_or_escalation_route": [
            "If scope is too narrow, stop and ask Guardian/Chief for a new bounded package.",
        ],
        "rollback_expectation": [
            "Keep edits small enough to revert by file if the focused tests regress.",
        ],
        "production_prohibitions": [
            "No production restarts, cron edits, systemd edits, real sends, money movement, or secret access.",
        ],
        "package_compiler": "self_improvement_request.compile_self_improvement_package",
        "package_profile": gap_id,
    }
    missing = [
        field for field in _TASK_PACKAGE_REQUIRED_PAYLOAD_FIELDS
        if not _nonempty_package_value(payload.get(field))
    ]
    if missing:
        raise SelfImprovementPackageError(
            f"gap {gap_id!r} package is missing required fields: {', '.join(missing)}"
        )
    return payload


def _base_task_id_for_gap(gap: dict) -> str:
    gap_id = _safe_task_id_fragment(str(gap.get("id") or "gap"))
    digest = hashlib.sha256(str(gap.get("build_goal") or "").encode()).hexdigest()[:8]
    return f"self_improve_{gap_id}_{digest}"


def _task_id_revision(base: str, attempt: int) -> str:
    return base if attempt == 1 else f"{base}_r{attempt}"


def _latest_self_improvement_task_for_gap(gap: dict, ledger: Any) -> dict | None:
    """Return the latest contiguous self-improvement task row for this gap."""
    base = _base_task_id_for_gap(gap)
    latest: dict | None = None
    for attempt in range(1, 100):
        task_id = _task_id_revision(base, attempt)
        try:
            latest = ledger.get_task(task_id)
        except KeyError:
            return latest
    return latest


def requested_self_improvement_terminal(gap: dict, *, ledger: Any | None = None) -> bool:
    """True when the latest filed task for ``gap`` is already terminal.

    The lifecycle state is intentionally coarse ("requested"). This read-only ledger check
    lets autonomous loops retry immediately after a task is BLOCKED/DEAD/DONE, instead of
    waiting for the blind grace timer.
    """
    if ledger is None:
        from polish_loop.control_plane import ControlPlaneLedger

        ledger = ControlPlaneLedger()
    latest = _latest_self_improvement_task_for_gap(gap, ledger)
    if latest is None:
        return False
    return str(latest.get("status") or "").upper() in _TERMINAL_TASK_STATUSES


def _task_id_for_gap(gap: dict, ledger: Any) -> str:
    """Return an id that dedupes active work but can retry after terminal failures."""
    base = _base_task_id_for_gap(gap)
    for attempt in range(1, 100):
        task_id = _task_id_revision(base, attempt)
        try:
            existing = ledger.get_task(task_id)
        except KeyError:
            return task_id
        status = str((existing or {}).get("status") or "").upper()
        if status not in _TERMINAL_TASK_STATUSES:
            return task_id
    raise SelfImprovementPackageError(f"too many terminal retries for {base}")


def _default_file_fn(gap: dict, agent: str) -> dict:
    """File the gap's build_goal via the agent-request factory (PROPOSED + Guardian)."""
    _ensure_chief_env()  # so the Guardian approval sends even from a minimal cron env

    from polish_loop.control_plane import ControlPlaneLedger
    from polish_loop.build_request_intake import admit_with_safety_check, BuildRequest

    ledger = ControlPlaneLedger()
    payload = compile_self_improvement_package(gap, agent=agent)
    task_id = _task_id_for_gap(gap, ledger)
    req = BuildRequest(
        task_id=task_id,
        requester=str(agent or "maestro"),
        task_type="self_improvement",
        description=str(payload.get("title") or gap.get("say") or gap.get("id") or ""),
        payload=payload,
    )

    def _approval_sender(request, tid):
        # Reuse the build-approval Guardian send (BUILDOK/BUILDNO). If delivery fails,
        # fail the filing so the gap remains open for retry instead of disappearing.
        from polish_loop.build_request_intake import build_approval_callback_data
        from chief_guardian_sender import send_approval

        ok = build_approval_callback_data(tid, approve=True)
        no = build_approval_callback_data(tid, approve=False)
        msg = (
            f"{request.requester} wants to improve itself:\n{payload.get('title', '')}\n\n"
            f"Bounded package: {len(payload['allowed_files'])} allowed files, "
            f"{len(payload['tests_to_run'])} test command(s).\n\n"
            f"Build it? ({payload['goal'][:160]})"
        )
        send_approval(msg, reply_markup={"inline_keyboard": [[
            {"text": "Build it", "callback_data": ok},
            {"text": "Not now", "callback_data": no},
        ]]})

    return admit_with_safety_check(req, ledger=ledger, approval_sender=_approval_sender)


def maybe_file_on_agreement(
    conversation_id: str,
    message: str,
    *,
    agent: str = "maestro",
    store: Path = _DEFAULT_STORE,
    file_fn: Optional[Callable[[dict, str], Any]] = None,
) -> Optional[dict]:
    """If the operator agreed AND a recommendation is pending for this conversation, file the
    gap's build_goal as a build request and clear the recommendation. Returns a result dict or
    None. Fail-open: any error returns None (never breaks the reply)."""
    try:
        if not is_agreement(message):
            return None
        gap_id = get_pending_recommendation(conversation_id, store=store)
        if not gap_id:
            return None
        from self_knowledge import gap_by_id

        gap = gap_by_id(gap_id)
        if not gap:
            clear_recommendation(conversation_id, store=store)
            return None
        fn = file_fn or _default_file_fn
        result = fn(gap, agent)
        clear_recommendation(conversation_id, store=store)
        # Mark the gap requested so it's never recommended again (until it's closed/reopened).
        try:
            from self_knowledge import mark_gap
            mark_gap(gap_id, "requested")
        except Exception:
            pass
        return {"filed": True, "gap": gap, "result": result}
    except Exception:
        return None
