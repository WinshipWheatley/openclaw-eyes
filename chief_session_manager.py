import fcntl
import json
from pathlib import Path
from typing import Any


STATE_DIR = Path("/home/openclaw/OpenClaw/state")
STATE_DIR.mkdir(parents=True, exist_ok=True)

SESSION_FILE = STATE_DIR / "chief_session.json"


DEFAULT_SESSION = {
    "active_workflow": None,
    "active_mode": None,
    "step": 0,
    "fields": {},
    "workflow_state": {},
    "history": [],
    "last_user_message": None,
    "last_question": None,
    "status": "idle",
}


def _deep_copy_default() -> dict:
    return json.loads(json.dumps(DEFAULT_SESSION))


def load_session() -> dict:
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_SH)
            try:
                return json.load(fh)
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return _deep_copy_default()


def save_session(session: dict) -> None:
    SESSION_FILE.touch(exist_ok=True)
    with open(SESSION_FILE, "r+", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.seek(0)
            fh.write(json.dumps(session, indent=2))
            fh.truncate()
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def reset_session() -> dict:
    session = _deep_copy_default()
    save_session(session)
    return session


def set_workflow(workflow: str, mode: str | None = None) -> dict:
    session = load_session()
    session["active_workflow"] = workflow
    session["active_mode"] = mode
    session["step"] = 0
    session["fields"] = {}
    session["workflow_state"] = {}
    session["history"] = []
    session["last_user_message"] = None
    session["last_question"] = None
    session["status"] = "active"
    save_session(session)
    return session


def get_workflow_state() -> dict:
    return load_session().get("workflow_state", {})


def set_workflow_state(data: dict) -> None:
    session = load_session()
    session["workflow_state"] = data
    save_session(session)


def append_history(role: str, text: str) -> dict:
    session = load_session()
    session["history"].append({"role": role, "text": text})
    if role == "user":
        session["last_user_message"] = text
    save_session(session)
    return session


def set_last_question(text: str) -> dict:
    session = load_session()
    session["last_question"] = text
    save_session(session)
    return session


def set_step(step: int) -> dict:
    session = load_session()
    session["step"] = step
    save_session(session)
    return session


def update_field(name: str, value: Any) -> dict:
    session = load_session()
    session["fields"][name] = value
    save_session(session)
    return session


def get_field(name: str, default: Any = None) -> Any:
    session = load_session()
    return session["fields"].get(name, default)


def mark_complete() -> dict:
    session = load_session()
    session["status"] = "complete"
    save_session(session)
    return session


def mark_cancelled() -> dict:
    session = load_session()
    session["status"] = "cancelled"
    save_session(session)
    return session


def is_active() -> bool:
    session = load_session()
    return session.get("status") == "active"


if __name__ == "__main__":
    print(json.dumps(load_session(), indent=2))
