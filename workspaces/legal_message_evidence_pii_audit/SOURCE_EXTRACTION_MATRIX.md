# Source Extraction Matrix

**Candidate Platforms & Methods:**
1. **Apple iOS (iTunes Backup / Finder Backup) -> sms.db**
   - **Completeness:** High (full database of iMessage/SMS).
   - **Identifiers:** Preserves raw numbers, email addresses, and internal UUIDs.
   - **Timestamps:** Mac absolute time (preserves precise timestamps, ordering, read/delivery state).
   - **Attachments:** Retained in Backup folder structure.
   - **Verdict:** Highly recommended for defensible legal evidence. Needs a dedicated SQLite parser (not yet built in OpenClaw).

2. **Android SMS/MMS Databases (ADB Backup or third-party forenics)**
   - **Completeness:** High.
   - **Identifiers:** Full preservation.
   - **Timestamps:** Epoch timestamps (timezone offset requires care).
   - **Verdict:** Highly recommended, but parser required.

3. **Cloud Exports (Google Takeout, Carrier CSVs)**
   - **Completeness:** Variable (attachments often missing or disconnected).
   - **Verdict:** Good for informal review, less defensible for attachments or edited messages.

4. **Screenshots / OCR**
   - **Completeness:** Very low (metadata destroyed).
   - **Verdict:** Avoid for primary preservation.

**Unknown Operator Questions for Source Selection:**
- What is the phone's operating system?
- Are messages still present on the physical phone?
- Do you have an unencrypted local backup (Mac/PC)?
- Which messaging application was primarily used (native vs. WhatsApp/Signal)?
- Do attachments (photos/documents) matter to the legal case?
- What is the date range?
- Are the two opposing phone numbers in a single group thread or two separate 1:1 threads?
- Is this for informal review, formal discovery, or court filing?
