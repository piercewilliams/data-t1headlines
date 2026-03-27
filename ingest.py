"""
Monthly data ingest for T1 Headline Analysis.

What it does:
  1. Snapshots docs/index.html → docs/archive/YYYY-MM/index.html (with archive banner)
  2. Updates docs/archive/index.html (the timeline index)
  3. Runs generate_site.py with the specified data files
  4. Commits the snapshot + regenerated site

Usage:
  python ingest.py                                          # same files, new snapshot
  python ingest.py --data-2026 "New 2026 file.xlsx"        # drop in new 2026 data
  python ingest.py --data-2025 "a.xlsx" --data-2026 "b.xlsx"
  python ingest.py --note "Added MSN full year"            # add a note to the archive entry
  python ingest.py --no-commit                             # dry run, no git commit
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_2025 = "Top syndication content 2025.xlsx"
DEFAULT_2026 = "Top Stories 2026 Syndication.xlsx"


def main():
    parser = argparse.ArgumentParser(description="Ingest new T1 data and archive current site")
    parser.add_argument("--data-2025", default=DEFAULT_2025,
                        help="Path to 2025 data workbook (default: current file)")
    parser.add_argument("--data-2026", default=DEFAULT_2026,
                        help="Path to 2026 data workbook (default: current file)")
    parser.add_argument("--note", default="",
                        help="Human-readable note for this run, shown in archive index")
    parser.add_argument("--no-commit", action="store_true",
                        help="Skip git commit (for testing)")
    args = parser.parse_args()

    now = datetime.now()
    period = now.strftime("%Y-%m")           # e.g. "2026-03"
    period_label = now.strftime("%B %Y")     # e.g. "March 2026"
    generated_date = now.strftime("%Y-%m-%d")

    # 1. Snapshot current site
    current_site = Path("docs/index.html")
    archive_dir = Path("docs/archive") / period
    archive_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = archive_dir / "index.html"

    hero_headline = ""
    if current_site.exists():
        content = current_site.read_text(encoding="utf-8")

        # Extract hero h1 to use as the link text in the archive index
        hero_match = re.search(r'class="hero".*?<h1>(.*?)</h1>', content, re.DOTALL)
        if hero_match:
            hero_headline = re.sub(r"<[^>]+>", "", hero_match.group(1)).strip()

        banner = (
            f'<div style="background:#b45309;color:#fff;padding:0.75rem 1.5rem;'
            f'text-align:center;font-size:0.85rem;font-family:system-ui,sans-serif;">'
            f'Archived snapshot — {period_label}. '
            f'<a href="../../index.html" style="color:#fde68a;text-decoration:underline;">'
            f'View current analysis →</a></div>'
        )
        content = content.replace("<body>", f"<body>\n{banner}", 1)
        snapshot_path.write_text(content, encoding="utf-8")
        print(f"✓ Archived → {snapshot_path}")
    else:
        print("⚠  No existing docs/index.html to archive — skipping snapshot step")

    # 2. Update archive index
    _update_archive_index(period, period_label, generated_date, hero_headline, args)

    # 3. Regenerate site with new data files
    cmd = [
        "python3", "generate_site.py",
        "--data-2025", args.data_2025,
        "--data-2026", args.data_2026,
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("✗ generate_site.py failed — archive preserved, current site not updated")
        return 1

    # 4. Commit
    if not args.no_commit:
        note_suffix = f" — {args.note}" if args.note else ""
        msg = (
            f"Monthly ingest {period_label}{note_suffix}\n\n"
            f"Archive: docs/archive/{period}/\n"
            f"Data 2025: {args.data_2025}\n"
            f"Data 2026: {args.data_2026}\n"
            f"Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
        )
        subprocess.run(["git", "add", "docs/"])
        subprocess.run(["git", "commit", "-m", msg])
        print(f"✓ Committed")

    return 0


def _update_archive_index(period, period_label, generated_date, hero_headline, args):
    archive_index = Path("docs/archive/index.html")

    # Read existing entries from embedded JSON comment
    entries = []
    if archive_index.exists():
        content = archive_index.read_text(encoding="utf-8")
        match = re.search(r"<!--ENTRIES:(.*?)-->", content, re.DOTALL)
        if match:
            try:
                entries = json.loads(match.group(1))
            except json.JSONDecodeError:
                entries = []

    # Upsert entry for this period
    entry = {
        "period": period,
        "label": period_label,
        "generated": generated_date,
        "headline": hero_headline,
        "data_2025": args.data_2025,
        "data_2026": args.data_2026,
        "note": args.note,
    }
    entries = [e for e in entries if e["period"] != period]
    entries.insert(0, entry)

    # Build edition list HTML — link text = hero headline, metadata below
    items = ""
    for e in entries:
        headline = e.get("headline") or e["label"]
        meta_parts = [e["label"], e["generated"]]
        if e.get("note"):
            meta_parts.append(e["note"])
        meta = " · ".join(meta_parts)
        items += (
            f'<li>'
            f'<a href="{e["period"]}/index.html">{headline}</a>'
            f'<span class="meta">{meta}</span>'
            f'</li>\n'
        )

    entries_json = json.dumps(entries)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>T1 Headline Analysis · Past Editions</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
          max-width: 760px; margin: 3rem auto; padding: 0 1.5rem; color: #0f172a;
          line-height: 1.6; }}
  h1 {{ font-family: Georgia, serif; font-size: 1.5rem; margin-bottom: 0.4rem; }}
  .back {{ color: #2563eb; text-decoration: none; font-size: 0.85rem;
           display: block; margin-bottom: 2rem; }}
  p.sub {{ color: #64748b; font-size: 0.88rem; margin-bottom: 2rem; }}
  ul {{ list-style: none; padding: 0; margin: 0; }}
  li {{ padding: 1.1rem 0; border-bottom: 1px solid #e2e8f0; }}
  li:last-child {{ border-bottom: none; }}
  li a {{ font-family: Georgia, serif; font-size: 1.05rem; color: #0f172a;
          text-decoration: none; display: block; margin-bottom: 0.2rem; }}
  li a:hover {{ color: #2563eb; }}
  .meta {{ display: block; font-size: 0.78rem; color: #94a3b8; }}
</style>
</head>
<body>
<!--ENTRIES:{entries_json}-->
<a class="back" href="../index.html">← Current analysis</a>
<h1>Past Editions</h1>
<p class="sub">Each snapshot is the full site as it existed when that data was ingested.</p>
<ul>
{items}</ul>
</body>
</html>"""

    archive_index.write_text(html, encoding="utf-8")
    print(f"✓ Updated archive index → {archive_index}")


if __name__ == "__main__":
    sys.exit(main())
