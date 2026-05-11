def extract_producer_payload(text: str) -> str | None:
    """Extracts payload from /producer <text> or producer: <text>."""
    lower = text.lower()
    if lower.startswith("/producer "):
        return text[len("/producer "):].strip()
    if lower.startswith("producer: "):
        return text[len("producer: "):].strip()
    return None

def truncate_producer_output(text: str, max_chars: int = 3500) -> str:
    """Truncates producer output if it exceeds max_chars."""
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n(Truncated to 3500 chars)"
    return text
