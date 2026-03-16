import json
import re
import urllib.request
import urllib.error

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:7b"


def ollama_call(prompt: str, timeout: int = 15) -> str:
    """Call Ollama and return raw text response. Returns '' on any error."""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "").strip()
    except Exception:
        return ""


def ollama_json(prompt: str, timeout: int = 15) -> dict:
    """Call Ollama and parse JSON from response. Returns {} on error or parse failure."""
    raw = ollama_call(prompt, timeout=timeout)
    if not raw:
        return {}
    text = raw.strip()
    # Strip markdown fences
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner)
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {}
