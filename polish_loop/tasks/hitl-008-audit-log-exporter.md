title: hitl-008-audit-log-exporter
goal: Build a Python exporter that writes daily PendingActions history to CSV.

Description:
Create a utility script that reads PendingActions records and produces a date-partitioned CSV export for audit and reporting use. Include stable columns for action id, actor, status, created time, completed time, and decision metadata.

Verification:
- Running the exporter for a sample day creates exactly one CSV file in the configured output folder.
- CSV includes header row and expected fields for each action.
- Export handles empty-day input gracefully by writing an empty report with headers.
