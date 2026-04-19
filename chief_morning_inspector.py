import json
from pathlib import Path
from datetime import datetime

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
