def escalate_to_operator(diagnosis: str, reason: str, primary_cmd: str, context_cmd: str | None = None) -> str:
    """
    Format a strict 4-line operator-assist escalation message.
    Used when Chief is blocked on a task and requires manual intervention.
    """
    lines = [
        "",
        "============== OPERATOR ASSIST REQUIRED ==============",
        f"Diagnosis : {diagnosis}",
        f"Reason    : {reason}",
        f"Fix Cmd   : {primary_cmd}"
    ]
    if context_cmd:
        lines.append(f"Context   : {context_cmd}")
    lines.extend([
        "======================================================",
        ""
    ])
    return "\n".join(lines)
