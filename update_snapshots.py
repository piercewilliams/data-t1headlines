#!/usr/bin/env python3
"""
update_snapshots.py — Append the latest build metrics to data/weekly_snapshots.json.

Reads data/build_summary.json (written by generate_site.py at the end of every run),
stamps it with today's ISO date, and appends it to the longitudinal snapshot log at
data/weekly_snapshots.json.

Each entry in weekly_snapshots.json is:
  {
    "date": "2026-04-14",
    "fb_wtk_sn_rank": 0.371,
    "fb_q_sn_rank": 0.423,
    "fb_sn_n": 38251,
    "notif_len_best_ctr": 0.0145,
    "sn_top_share": 0.072,
    "an_median_hl_len": 97.0,
    "sn_median_hl_len": 81.0,
    "sn_channel_rows": 12453,
    ...
  }

Usage:
    python3 update_snapshots.py
"""

import json
import sys
from datetime import date
from pathlib import Path

BUILD_SUMMARY = Path("data/build_summary.json")
SNAPSHOTS_FILE = Path("data/weekly_snapshots.json")


def main() -> int:
    if not BUILD_SUMMARY.exists():
        print(f"Error: {BUILD_SUMMARY} not found — run generate_site.py first.")
        return 1

    try:
        summary = json.loads(BUILD_SUMMARY.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: could not parse {BUILD_SUMMARY}: {e}")
        return 1

    # Load existing snapshot log (or start fresh)
    snapshots: list[dict] = []
    if SNAPSHOTS_FILE.exists():
        try:
            snapshots = json.loads(SNAPSHOTS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"Warning: {SNAPSHOTS_FILE} was malformed — starting fresh.")
            snapshots = []

    today = date.today().isoformat()

    # Replace any entry from today (idempotent re-runs)
    snapshots = [s for s in snapshots if s.get("date") != today]
    snapshots.append({"date": today, **summary})

    # Keep chronological order
    snapshots.sort(key=lambda s: s.get("date", ""))

    SNAPSHOTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOTS_FILE.write_text(json.dumps(snapshots, indent=2), encoding="utf-8")
    print(f"✓ Snapshot appended to {SNAPSHOTS_FILE} ({len(snapshots)} total entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
