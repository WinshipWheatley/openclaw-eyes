# Operator Communication

This doctrine formalizes how agents communicate with the human operator, specifically regarding escalations and assistance.

## 1. Standard Escalation Format
When an agent is blocked and requires manual intervention, it MUST use the strict 4-line **OPERATOR ASSIST REQUIRED** block.

```text
============== OPERATOR ASSIST REQUIRED ==============
Diagnosis : [Short, technical description of the block]
Reason    : [Why manual intervention is required]
Fix Cmd   : [The exact bash command for the operator to run]
Context   : [Optional: command to view relevant logs/state]
======================================================
```

## 2. Escalation Boundaries
Agents MUST escalate when:
- An external API returns an authentication or credential error (401, 403).
- A critical file-system operation fails due to missing permissions.
- A "Tier 2" hard rule requires out-of-band approval.
- Deterministic logic identifies a contradiction in `CANONICAL REALITY` that it cannot resolve.

## 3. Fallback vs. Escalation
- **Deterministic Fallbacks**: Agents should use pre-defined fallback text (e.g., "LLM offline") for transient, non-consequence-bearing failures (like a single LLM timeout).
- **Hard Stops**: Agents must NOT attempt to "guess" or "hallucinate" a path forward when a structural dependency is broken.

## 4. Communication Style
- **Concise**: Use minimal prose. 
- **Command-First**: Always provide a "Fix Cmd" when possible.
- **Evidence-Grounded**: Reference the specific log or file that triggered the escalation.
