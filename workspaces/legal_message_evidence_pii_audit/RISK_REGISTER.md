# Risk Register

1. **Privacy & Agent Leakage Risk (HIGH):**
   - *Risk:* Agents with bash/SQLite access can simply read the raw `.db` file or print variables, leaking Tier 4 PII into model prompts or system logs.
   - *Mitigation:* Strong OS boundaries. Agents operate in restricted containers or users. Raw evidence lives in paths strictly `chmod 600` for a specific Legal operator user.

2. **Identity Conflation Risk (HIGH):**
   - *Risk:* Automatically merging two phone numbers into `Person_A` without retaining the raw endpoint, legally invalidating the evidence if it turns out the person shared a phone.
   - *Mitigation:* Explicit separation of `endpoint_id` vs. `person_entity_id`.

3. **Model Hallucination / Evidence Integrity Risk (CRITICAL):**
   - *Risk:* A language model paraphrases a threat ("I will kill you") into ("I'm going to hurt you") during a semantic search, and presents it as a quote.
   - *Mitigation:* The LLM may only return `message_id` references. The system retrieves the `message_body_exact` directly from the immutable database.

4. **Chain-of-Custody Risk (MEDIUM):**
   - *Risk:* Original source artifacts are mutated by SQLite browser or timestamp-altering software.
   - *Mitigation:* Operator strictly follows the Preservation-First manual workflow. OpenClaw computes and verifies SHA-256 hashes on ingestion.
