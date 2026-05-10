#!/usr/bin/env python3
"""
Business Ops Ledger Inspection CLI
Read-only tool for auditing the OpenClaw SQLite ledger.
"""

import sqlite3
import json
import argparse
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = ".openclaw/business_ops/ledger.sqlite"

def get_connection(db_path: str):
    try:
        # Use uri=True and mode=ro for read-only if supported, 
        # but standard sqlite3.connect is fine for simple reads.
        # We'll just be careful not to execute any writes.
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        # Fallback if URI mode is not supported or file doesn't exist
        return sqlite3.connect(db_path)

def truncate(text: Any, length: int = 50) -> str:
    s = str(text)
    return (s[:length] + '...') if len(s) > length else s

def get_summary(conn: sqlite3.Connection) -> Dict[str, Any]:
    summary = {"tables": {}, "event_types": {}}
    cursor = conn.cursor()
    
    # Table counts
    tables = [
        "events", "packets", "capability_decisions", 
        "retrieval_receipts", "side_effects", "operator_explanations"
    ]
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            summary["tables"][table] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            summary["tables"][table] = "Table not found"

    # Event type counts
    try:
        cursor.execute("SELECT event_type, COUNT(*) FROM events GROUP BY event_type")
        for row in cursor.fetchall():
            summary["event_types"][row[0]] = row[1]
    except sqlite3.OperationalError:
        pass
        
    return summary

def get_latest_events(conn: sqlite3.Connection, limit: int, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    query = "SELECT event_id, ts, event_type, actor, operator_visible_summary FROM events"
    params = []
    if event_type:
        query += " WHERE event_type = ?"
        params.append(event_type)
    query += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    columns = [col[0] for col in cursor.description]
    results = []
    for row in cursor.fetchall():
        results.append(dict(zip(columns, row)))
    return results

def print_summary(summary: Dict[str, Any]):
    print("=== Business Ops Ledger Summary (Read-Only) ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("\n[Table Row Counts]")
    for table, count in summary["tables"].items():
        print(f"  {table:25}: {count}")
    
    print("\n[Event Type Distribution]")
    for etype, count in summary["event_types"].items():
        print(f"  {etype:25}: {count}")
    print("=" * 47)

def print_latest(events: List[Dict[str, Any]]):
    if not events:
        print("No events found.")
        return

    print(f"=== Latest {len(events)} Events ===")
    header = f"{'ID':<12} {'Timestamp':<20} {'Type':<25} {'Actor':<10} {'Summary'}"
    print(header)
    print("-" * len(header))
    for ev in events:
        eid = truncate(ev['event_id'], 10)
        ts = ev['ts'][:19] # Truncate microseconds
        etype = truncate(ev['event_type'], 23)
        actor = truncate(ev['actor'], 8)
        summ = truncate(ev['operator_visible_summary'], 40) if ev['operator_visible_summary'] else ""
        print(f"{eid:<12} {ts:<20} {etype:<25} {actor:<10} {summ}")
    print("=" * (len(header)))

def main():
    parser = argparse.ArgumentParser(description="Inspect Business Ops Ledger")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to the ledger database")
    parser.add_argument("--summary", action="store_true", help="Show summary of ledger contents")
    parser.add_argument("--latest", type=int, metavar="N", help="Show latest N events")
    parser.add_argument("--event-type", help="Filter latest events by type")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    args = parser.parse_args()

    conn = get_connection(args.db)
    
    output_data = {}

    try:
        if args.summary:
            summary = get_summary(conn)
            if args.json:
                output_data["summary"] = summary
            else:
                print_summary(summary)
                
        if args.latest:
            events = get_latest_events(conn, args.latest, args.event_type)
            if args.json:
                output_data["latest_events"] = events
            else:
                print_latest(events)

        if not args.summary and not args.latest:
            # Default to summary if no args provided
            summary = get_summary(conn)
            if args.json:
                output_data["summary"] = summary
            else:
                print_summary(summary)

        if args.json:
            print(json.dumps(output_data, indent=2))

    except Exception as e:
        print(f"Error inspecting ledger: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
