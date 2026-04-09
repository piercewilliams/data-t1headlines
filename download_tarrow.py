#!/usr/bin/env python3
"""
download_tarrow.py — Download Chris Tarrow's 2026 Google Sheet as XLSX.

Uses the existing GOOGLE_SERVICE_ACCOUNT_FILE / GOOGLE_SERVICE_ACCOUNT_JSON
service account (the same one used by generate_grader.py) to authenticate
against the Google Drive API and export the sheet as Excel.

2025 data is complete and does not need to be re-downloaded.

Usage:
    python3 download_tarrow.py [--out FILE]

Environment:
    GOOGLE_SERVICE_ACCOUNT_FILE  — path to service account JSON file
    GOOGLE_SERVICE_ACCOUNT_JSON  — raw JSON string (fallback if FILE not set)
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ── Sheet IDs ──────────────────────────────────────────────────────────────────
SHEET_2026_ID = "1Va8hnBtaX8fEFU8FVPpFcAN82o5RDF9fJBaJvRzrN7s"

DRIVE_EXPORT_URL = (
    "https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
)

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

DEFAULT_OUT = "Top Stories 2026 Syndication.xlsx"


def _load_credentials():
    """Load service account credentials from env (file path or raw JSON)."""
    try:
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("Error: google-auth is not installed. Run: pip install google-auth")
        sys.exit(1)

    sa_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if sa_file and Path(sa_file).exists():
        return Credentials.from_service_account_file(sa_file, scopes=SCOPES)

    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        info = json.loads(sa_json)
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    print(
        "Error: no service account credentials found.\n"
        "Set GOOGLE_SERVICE_ACCOUNT_FILE (path) or GOOGLE_SERVICE_ACCOUNT_JSON (raw JSON)."
    )
    sys.exit(1)


def download_sheet(sheet_id: str, out_path: str, credentials) -> None:
    """Download a Google Sheet as XLSX via the Drive export endpoint."""
    try:
        import requests
    except ImportError:
        print("Error: requests is not installed. Run: pip install requests")
        sys.exit(1)

    from google.auth.transport.requests import Request as GoogleRequest

    # Refresh the token so we have a valid access_token
    credentials.refresh(GoogleRequest())
    token = credentials.token

    url = DRIVE_EXPORT_URL.format(sheet_id=sheet_id)
    headers = {"Authorization": f"Bearer {token}"}

    print(f"Downloading sheet {sheet_id}…")
    resp = requests.get(url, headers=headers, timeout=120)

    if resp.status_code != 200:
        print(f"Error: HTTP {resp.status_code} — {resp.text[:200]}")
        sys.exit(1)

    Path(out_path).write_bytes(resp.content)
    size_kb = len(resp.content) // 1024
    print(f"✓ Saved {out_path} ({size_kb} KB)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Tarrow 2026 sheet as XLSX")
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help=f"Output path for the XLSX file (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()

    credentials = _load_credentials()
    download_sheet(SHEET_2026_ID, args.out, credentials)
    return 0


if __name__ == "__main__":
    sys.exit(main())
