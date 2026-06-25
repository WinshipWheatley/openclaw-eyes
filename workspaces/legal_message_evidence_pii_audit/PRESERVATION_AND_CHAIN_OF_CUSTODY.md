# Preservation and Chain of Custody Workflow

**Immediate Operator Action (Manual):**
1. **Acquisition:** Perform a full device backup or authorized database export (e.g., `sms.db`) locally. 
2. **Hash & Preserve:** Compute SHA-256 on the exact export artifacts immediately.
3. **Store:** Place the original files in encrypted, read-only legal hold storage. DO NOT open them in applications (like SQLite browser) that might alter file timestamps or journal files.

**Future OpenClaw Workflow:**
1. **Preserved Original:** The untouched source artifact with verifiable provenance.
2. **Verified Working Copy:** An immutable representation of the database imported into the OpenClaw Evidence Registry.
3. **Tokenized Analysis Copy:** A subset of the evidence where all identities (`PERSON_A`, `PHONE_A1`) are replaced securely.
4. **Human-Readable Review / Attorney Output:** Generated purely from the Tokenized Analysis Copy, with authorized Detokenization applied ONLY at the final rendering boundary.

**Required Acquisition Metadata:**
- Matter or case identifier
- Source device identifier / Source account identifier
- Operator ownership or lawful-access basis
- Phone number / account associated with the device
- Device operating system and version
- Messaging application
- Extraction application and version
- Extraction date, time, and timezone
- Export format, original file names, byte sizes, and cryptographic hashes
- Any errors or omissions
