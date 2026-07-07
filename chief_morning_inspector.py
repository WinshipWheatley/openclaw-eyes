import json
from pathlib import Path
from datetime import datetime, timedelta

_CHIEF_MORNING_SYNTHESIS = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Chief Morning Synthesis.md")
_MORNING_REFERENCE_CACHE = Path("/mnt/c/OpenClaw/logs/cassandra_briefings/morning_reference_cache.json")

def handle_morning_inspection(text: str) -> list[str]:
    t = text.lower().strip()
    
    if "morning raw" in t:
        if not _CHIEF_MORNING_SYNTHESIS.exists():
            return ["Chief Morning Synthesis artifact not found."]
        return [_CHIEF_MORNING_SYNTHESIS.read_text(encoding="utf-8")]
        
    if "morning cache" in t:
        if not _MORNING_REFERENCE_CACHE.exists():
            return ["Morning reference cache not found."]
        return [_MORNING_REFERENCE_CACHE.read_text(encoding="utf-8")]
        
    if "morning stale" in t:
        if not _MORNING_REFERENCE_CACHE.exists():
            return ["Morning reference cache not found."]
        try:
            cache = json.loads(_MORNING_REFERENCE_CACHE.read_text(encoding="utf-8"))
            gen = cache.get("generated_at", "unknown")
            fresh = cache.get("source_freshness", "unknown")
            return [f"Cache generated at: {gen}\nSource freshness: {fresh}"]
        except Exception as e:
            return [f"Failed to read cache: {e}"]
            
    if "morning blockers" in t or "morning actions" in t:
        if not _MORNING_REFERENCE_CACHE.exists():
            return ["Morning reference cache not found."]
        try:
            cache = json.loads(_MORNING_REFERENCE_CACHE.read_text(encoding="utf-8"))
            sections = cache.get("sections", {})
            if "morning actions" in t:
                # Top Priorities from morning synthesis section parsing
                pri = sections.get("Top Priorities", [])
                if isinstance(pri, list): pri = "\n".join(pri)
                return [f"Morning Actions/Priorities:\n\n{pri}"]
            else:
                blockers = sections.get("Blockers / Watchlist", [])
                if isinstance(blockers, list): blockers = "\n".join(blockers)
                return [f"Morning Blockers:\n\n{blockers}"]
        except Exception as e:
            return [f"Failed to extract sections: {e}"]
            
    if "morning sources" in t:
        if not _MORNING_REFERENCE_CACHE.exists():
            return ["Morning reference cache not found."]
        try:
            cache = json.loads(_MORNING_REFERENCE_CACHE.read_text(encoding="utf-8"))
            sections = cache.get("sections", {})
            src = sections.get("Upstream Artifacts Read", [])
            if isinstance(src, list): src = "\n".join(src)
            return [f"Morning Sources:\n\n{src}"]
        except Exception as e:
            return [f"Failed to extract sources: {e}"]
            
    return ["Unknown morning inspection command."]

def handle_morning_followup(text: str) -> list[str]:
    if not _MORNING_REFERENCE_CACHE.exists():
        return ["Morning context is missing. Try running the morning brief first."]

    try:
        cache = json.loads(_MORNING_REFERENCE_CACHE.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"Failed to read morning cache: {e}"]

    # Freshness check (6 hours)
    try:
        gen_str = cache.get("generated_at", "")
        if gen_str:
            gen_time = datetime.fromisoformat(gen_str)
            if datetime.now() - gen_time > timedelta(hours=6):
                return ["The morning context is stale, let me run a fresh check."]
    except Exception:
        pass

    sections = cache.get("sections", {})
    t = text.lower().strip()

    # Deterministic fallbacks for obvious queries
    if "blocker" in t or "watchlist" in t:
        b = sections.get("Blockers / Watchlist", [])
        if isinstance(b, list): b = "\n".join(b)
        if b: return [f"From the morning brief (Blockers / Watchlist):\n\n{b}"]
        
    if "priorit" in t or "action" in t:
        p = sections.get("Top Priorities", [])
        if isinstance(p, list): p = "\n".join(p)
        if p: return [f"From the morning brief (Top Priorities):\n\n{p}"]
        
    if "stale" in t:
        s = sections.get("Confidence / What May Be Stale", [])
        if isinstance(s, list): s = "\n".join(s)
        if s: return [f"From the morning brief (Stale items):\n\n{s}"]
        
    if "source" in t or "upstream" in t or "what did chief use" in t:
        s = sections.get("Upstream Artifacts Read", [])
        if isinstance(s, list): s = "\n".join(s)
        if s: return [f"From the morning brief (Sources):\n\n{s}"]

    if "directive" in t:
        s = sections.get("Directive", [])
        if isinstance(s, list): s = "\n".join(s)
        if s: return [f"From the morning brief (Directive):\n\n{s}"]

    # LLM fallback for general conversational queries
    from adaptive_model_call import adaptive_ollama_text
    flat_sections = []
    for k, v in sections.items():
        flat_sections.append(f"--- {k} ---")
        if isinstance(v, list):
            flat_sections.append("\n".join(v))
        else:
            flat_sections.append(str(v))
    
    context_str = "\n".join(flat_sections)
    
    prompt = f"""\
You are answering a question based strictly on the cached morning synthesis below.
Question: {text}

Morning Cache Sections:
{context_str}

Rules:
- Answer the question directly using ONLY the information from the cache.
- Keep it to 2-3 sentences.
- Do not mention the cache, JSON formatting, or "according to the brief" in your answer.
- If the answer is not in the cache, simply reply exactly: "I don't see the answer to that in the morning brief."
"""
    result = adaptive_ollama_text(prompt, timeout=30, task_class="chief_structured_plan").strip()
    if not result:
        return ["I couldn't generate an answer from the morning cache."]
    return [result]
