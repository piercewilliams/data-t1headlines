#!/usr/bin/env python3
"""
ingest.py — Monthly data ingest entry point.

Profiles new data against the previous run, archives the current site,
regenerates all pages via generate_site.py, and commits the result.

Usage:
    python3 ingest.py [--data-2026 FILE] [--data-2025 FILE]
                      [--release YYYY-MM] [--note TEXT] [--no-commit]

See CLAUDE.md for the automated Claude Code workflow.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

GOVERNOR_FILE = Path("GOVERNOR.md")


DEFAULT_2025 = "Top syndication content 2025.xlsx"
DEFAULT_2026 = "Top Stories 2026 Syndication.xlsx"


# ── Analysis opportunity map ──────────────────────────────────────────────────
# Each entry: condition (sheet key, metric, threshold) → analysis suggestion
# Checked during diff; matching entries are printed as suggested next steps.

OPPORTUNITY_MAP = [
    {
        "id": "notifications_rows",
        "description": "Apple News Notifications dataset grew",
        "check": lambda old, new: (
            new.get("2026/Apple News Notifications", {}).get("rows", 0) >
            old.get("2026/Apple News Notifications", {}).get("rows", 0) * 1.2
        ),
        "suggestion": (
            "Larger notification dataset → re-validate Q5 CTR findings with more data.\n"
            "  Skills: polars → data-analysis → interactive-report-generator\n"
            '  Prompt: "Re-run Q5 notification CTR analysis on updated dataset. '
            "Validate whether possessive named entity lift and 'exclusive' tag lift hold.\""
        ),
    },
    {
        "id": "notifications_engagement",
        "description": "Notification engagement columns newly populated",
        "check": lambda old, new: _cols_newly_populated(
            old.get("2026/Apple News Notifications", {}),
            new.get("2026/Apple News Notifications", {}),
        ),
        "suggestion": (
            "Notification engagement depth now available.\n"
            "  Skills: excel-analysis → polars → data-analysis\n"
            '  Prompt: "Profile the newly populated notification engagement columns. '
            "What do active time / saves / shares tell us about high-CTR notifications beyond the click?\""
        ),
    },
    {
        "id": "apple_news_engagement",
        "description": "Apple News engagement columns newly populated (2026)",
        "check": lambda old, new: _cols_newly_populated(
            old.get("2026/Apple News", {}),
            new.get("2026/Apple News", {}),
        ),
        "suggestion": (
            "Apple News 2026 engagement depth now available (was empty at last run).\n"
            "  Skills: excel-analysis → polars → data-analysis\n"
            '  Prompt: "Profile Apple News 2026 engagement columns. '
            "Extend Finding 7 (views vs. active time) to 2026 data and check if the independence finding holds.\""
        ),
    },
    {
        "id": "smartnews_categories",
        "description": "SmartNews category columns restored (7 → 32+)",
        "check": lambda old, new: (
            new.get("2026/SmartNews", {}).get("cols", 0) >
            old.get("2026/SmartNews", {}).get("cols", 0) + 10
        ),
        "suggestion": (
            "SmartNews 2026 category breakdown restored.\n"
            "  Skills: polars → data-analysis → interactive-report-generator\n"
            '  Prompt: "Re-run Q4 SmartNews channel ROI analysis on 2026 data. '
            "Does the Local 108× lift replicate? Has Entertainment over-indexing improved?\""
        ),
    },
    {
        "id": "msn_volume",
        "description": "MSN dataset grew significantly (possible full-year data)",
        "check": lambda old, new: (
            new.get("2025/MSN", {}).get("rows", 0) >
            old.get("2025/MSN", {}).get("rows", 0) * 2
        ),
        "suggestion": (
            "MSN dataset is significantly larger — may now have full-year data.\n"
            "  Skills: excel-analysis → polars → data-analysis\n"
            '  Prompt: "Profile new MSN dataset. If full-year, add MSN to the Q3 topic × platform '
            "analysis. Compare MSN topic performance index to Apple News and SmartNews.\""
        ),
    },
    {
        "id": "apple_news_rows",
        "description": "Apple News dataset grew",
        "check": lambda old, new: (
            new.get("2025/Apple News", {}).get("rows", 0) >
            old.get("2025/Apple News", {}).get("rows", 0) + 100
        ),
        "suggestion": (
            "Apple News dataset has more rows.\n"
            "  Standard re-run covers this automatically.\n"
            "  If sample sizes for Here's/possessive now exceed n=100, run significance test:\n"
            '  Prompt: "Re-run Q1 formula lift analysis. '
            "Flag if Here's/possessive formula types now have n≥100 — re-test significance.\""
        ),
    },
    {
        "id": "new_sheets",
        "description": "New sheets detected in data files",
        "check": lambda old, new: bool(_new_sheets(old, new)),
        "suggestion": (
            "New data sheets detected — run excel-analysis to profile them.\n"
            "  Skills: excel-analysis → code-data-analysis-scaffolds\n"
            '  Prompt: "Profile the new sheets in the updated data file. '
            "What platform/metric do they cover? What analysis questions do they unlock?\""
        ),
    },
]


# Maximum number of Primary focus lines to print in the governor briefing.
# The Primary block is typically 6–8 bullets; cap prevents runaway output if
# the section grows but keeps the briefing scannable at a glance.
_GOVERNOR_MAX_FOCUS_LINES: int = 10

# Column index (0-based, after splitting on "|" and stripping empties) for the
# "Question" column in the Active Probing Queue table.
# Table format: | Priority | Question | Rationale | Data available? |
#               ^parts[0]  ^parts[1]  ^parts[2]   ^parts[3]
_GOVERNOR_QUEUE_PRIORITY_COL: int = 0
_GOVERNOR_QUEUE_QUESTION_COL: int = 1


def _print_governor_briefing() -> None:
    """Read GOVERNOR.md and print a concise session briefing to stdout.

    Emits three blocks:
      1. Primary stakeholder focus (up to _GOVERNOR_MAX_FOCUS_LINES lines)
      2. HIGH-priority items from the Active Probing Queue — these should be
         run during the current ingest even if not explicitly requested
      3. Count of documented Known Data Quirks as a reminder to check them

    Safe to call unconditionally: silently returns if GOVERNOR.md is absent
    or unreadable, and wraps all parsing in a broad try/except so a malformed
    governor file never blocks an ingest run.

    The governor file path is controlled by the module-level GOVERNOR_FILE
    constant (default: Path("GOVERNOR.md"), relative to CWD). ingest.py is
    always invoked from the repo root, so this resolves correctly in practice.
    """
    SEP = "─" * 60

    if not GOVERNOR_FILE.exists():
        # Silently skip — GOVERNOR.md is optional infrastructure, not a hard
        # dependency.  A missing file should never block data ingestion.
        return

    try:
        text = GOVERNOR_FILE.read_text(encoding="utf-8")
    except OSError as exc:
        # Unreadable file (permissions, I/O error, etc.) — warn and continue.
        print(f"  ⚠  Could not read {GOVERNOR_FILE}: {exc}")
        return

    def _extract_section(header: str) -> str:
        """Return the body of the markdown section whose heading exactly matches
        *header*, stripping leading/trailing whitespace.

        Captures content from the line after *header* up to — but not including
        — the next markdown heading at any level (``#`` through ``######``) or
        the end of the file.  Uses ``re.DOTALL`` so ``.`` matches newlines,
        enabling multi-line section bodies.

        Returns an empty string if the heading is not found.

        Args:
            header: The full heading text including ``#`` characters and
                    trailing space, e.g. ``"### Active Probing Queue"``.
        """
        # (?:^|\n)   — heading must start at beginning of string or after a newline
        # re.escape  — treat header text literally (handles special chars in titles)
        # #+\s       — stop at ANY heading depth (1–6 hashes) followed by a space,
        #              not just h1–h3; prevents bleeding into deep subsections
        # \Z         — also stop at end-of-string
        pattern = rf"(?:^|\n){re.escape(header)}\n(.*?)(?=\n#+ |\Z)"
        m = re.search(pattern, text, re.DOTALL)
        return m.group(1).strip() if m else ""

    try:
        print(f"\n{SEP}")
        print("GOVERNOR BRIEFING")
        print(SEP)

        # ── 1. Primary stakeholder focus ──────────────────────────────────────
        # Print only the "**Primary" block so the briefing stays compact.
        # The Secondary and Out-of-scope blocks are useful reference but
        # don't need to appear at every ingest.
        focus_raw = _extract_section("### Stakeholder Focus")
        if focus_raw:
            focus_lines = [ln for ln in focus_raw.splitlines() if ln.strip()]
            in_primary = False
            printed = 0
            for ln in focus_lines:
                stripped = ln.strip()
                # Start printing when we hit the Primary heading.
                if stripped.startswith("**Primary"):
                    in_primary = True
                # Stop when we reach the next bold heading (Secondary / Out of scope)
                # so we don't bleed into unrelated focus blocks.
                elif in_primary and stripped.startswith("**") and not stripped.startswith("**Primary"):
                    break
                if in_primary:
                    print(f"  {stripped}")
                    printed += 1
                    if printed >= _GOVERNOR_MAX_FOCUS_LINES:
                        print(f"  … (see GOVERNOR.md for full focus)")
                        break

        # ── 2. HIGH-priority probing queue ────────────────────────────────────
        # Items marked HIGH should be run on every ingest even without an
        # explicit user request.  Extract only those rows.
        #
        # Expected table format (column order must match these indices):
        #   | Priority | Question | Rationale | Data available? |
        # _GOVERNOR_QUEUE_PRIORITY_COL = 0  → "HIGH" / "MED" / "LOW"
        # _GOVERNOR_QUEUE_QUESTION_COL = 1  → the question text to display
        queue_raw = _extract_section("### Active Probing Queue")
        high_items: list[str] = []
        if queue_raw:
            for ln in queue_raw.splitlines():
                stripped = ln.strip()
                # Only process pipe-delimited table rows; skip headers and
                # separator rows (which contain "---").
                if not stripped.startswith("|") or "---" in stripped:
                    continue
                parts = [p.strip() for p in stripped.split("|") if p.strip()]
                # Guard: need at least Priority + Question columns.
                if len(parts) <= _GOVERNOR_QUEUE_QUESTION_COL:
                    continue
                priority = parts[_GOVERNOR_QUEUE_PRIORITY_COL]
                # Match exactly "HIGH" in the Priority cell — avoids false
                # positives if a question text happens to contain the word.
                if priority == "HIGH":
                    high_items.append(parts[_GOVERNOR_QUEUE_QUESTION_COL])

        if high_items:
            print(f"\n  HIGH-PRIORITY PROBING QUEUE (run on this ingest):")
            for item in high_items:
                print(f"    → {item}")

        # ── 3. Known data quirks count ────────────────────────────────────────
        # Print the count as a prompt to read the full list before analysis.
        # Count only genuine data rows: pipe-delimited lines that are not
        # the header row (first pipe row) or the separator row ("---").
        quirks_raw = _extract_section("### Known Data Quirks")
        quirk_count = 0
        if quirks_raw:
            header_seen = False
            for ln in quirks_raw.splitlines():
                stripped = ln.strip()
                if not stripped.startswith("|"):
                    continue
                if "---" in stripped:
                    # Separator row — marks that we're past the header
                    header_seen = True
                    continue
                if header_seen:
                    # Every pipe row after the separator is a data row
                    quirk_count += 1
        if quirk_count:
            print(
                f"\n  {quirk_count} known data quirk(s) documented — "
                f"read GOVERNOR.md § Known Data Quirks before any analysis."
            )

        print(f"\n  After analysis: propose governor updates (queue, signals, quirks, log).")
        print(f"{SEP}\n")

    except Exception as exc:  # noqa: BLE001
        # Parsing errors in a malformed governor file must never crash an
        # ingest run.  Print a warning and continue — the build is more
        # important than the briefing.
        print(f"  ⚠  Governor briefing failed (malformed GOVERNOR.md?): {exc}")
        print(f"{SEP}\n")


def _cols_newly_populated(old_sheet, new_sheet, threshold=0.5):
    """True if any column went from >50% null to <10% null."""
    old_nulls = old_sheet.get("null_rates", {})
    new_nulls = new_sheet.get("null_rates", {})
    for col, old_rate in old_nulls.items():
        if old_rate > threshold and new_nulls.get(col, old_rate) < 0.1:
            return True
    return False


def _new_sheets(old: dict, new: dict) -> set:
    """Return sheet keys present in new profile but not in old."""
    return set(new.keys()) - set(old.keys())


# ── Profiling ─────────────────────────────────────────────────────────────────

def _profile_data(path_2025: str, path_2026: str) -> dict:
    """Snapshot key stats from both data files. Returns flat dict keyed by 'YEAR/Sheet'."""
    try:
        import pandas as pd
    except ImportError:
        print("Error: pandas is required for data profiling but is not installed.")
        return {}

    profile = {}
    for year_label, path in [("2025", path_2025), ("2026", path_2026)]:
        try:
            xf = pd.ExcelFile(path)
            for sheet in xf.sheet_names:
                df = pd.read_excel(xf, sheet_name=sheet)
                key = f"{year_label}/{sheet}"
                null_rates = {
                    col: round(float(df[col].isna().mean()), 3)
                    for col in df.columns
                    if df[col].isna().mean() > 0.05
                }
                profile[key] = {
                    "rows": len(df),
                    "cols": len(df.columns),
                    "null_rates": null_rates,
                }
        except FileNotFoundError:
            print(f"Error: data file not found — {path}")
            profile[f"{year_label}/_error"] = {"error": f"FileNotFoundError: {path}"}
        except ValueError as e:
            print(f"Error reading {path}: {e}")
            profile[f"{year_label}/_error"] = {"error": str(e)}
    return profile


def _load_prev_profile() -> "tuple[dict | None, str | None]":
    """Find the most recent archived data_profile.json and load it."""
    archive_dirs = sorted(
        [d for d in Path("docs/archive").glob("*/data_profile.json") if d.is_file()],
        reverse=True,
    )
    if not archive_dirs:
        return None, None
    path = archive_dirs[0]
    try:
        data = json.loads(path.read_text())
        period = path.parent.name
        return data, period
    except (json.JSONDecodeError, OSError):
        return None, None


def _print_diff(old_profile: "dict | None", old_period: "str | None", new_profile: dict) -> None:
    """Print a data change summary and analysis suggestions."""
    SEP = "─" * 60

    print(f"\n{SEP}")
    print("DATA CHANGE SUMMARY" + (f"  (vs. {old_period})" if old_period else "  (first run)"))
    print(SEP)

    if not old_profile:
        print("  No previous profile found — this is the baseline run.")
    else:
        # Row count changes
        all_keys = sorted(set(list(old_profile.keys()) + list(new_profile.keys())))
        for key in all_keys:
            if key.endswith("/_error"):
                continue
            old_rows = old_profile.get(key, {}).get("rows")
            new_rows = new_profile.get(key, {}).get("rows")
            if old_rows is None and new_rows is not None:
                print(f"  {key:<40}  NEW  ({new_rows:,} rows)")
            elif old_rows is not None and new_rows is None:
                print(f"  {key:<40}  REMOVED")
            elif old_rows != new_rows:
                delta = new_rows - old_rows
                pct = delta / old_rows * 100
                flag = " ←" if abs(pct) > 5 else ""
                print(f"  {key:<40}  {old_rows:,} → {new_rows:,}  ({delta:+,}, {pct:+.0f}%){flag}")
            else:
                print(f"  {key:<40}  {new_rows:,} rows  (no change)")

        # Null rate changes (columns that flipped from mostly-null to mostly-populated)
        newly_unlocked = []
        for key in all_keys:
            old_nulls = old_profile.get(key, {}).get("null_rates", {})
            new_nulls = new_profile.get(key, {}).get("null_rates", {})
            for col, old_rate in old_nulls.items():
                new_rate = new_nulls.get(col, 0.0)
                if old_rate > 0.5 and new_rate < 0.1:
                    newly_unlocked.append(f"    {key} · {col}  ({old_rate:.0%} null → {new_rate:.0%} null)")
        if newly_unlocked:
            print(f"\n  Columns newly populated:")
            for line in newly_unlocked:
                print(line)

    # Analysis suggestions — only meaningful when there's a real previous profile
    triggered = []
    if old_profile:
        for opp in OPPORTUNITY_MAP:
            try:
                if opp["check"](old_profile, new_profile):
                    triggered.append(opp)
            except Exception:
                pass

    print(f"\n{SEP}")
    if triggered:
        print("SUGGESTED ANALYSIS  (see PLAYBOOK.md for full guidance)")
        print(SEP)
        for opp in triggered:
            print(f"\n  [{opp['description']}]")
            for line in opp["suggestion"].splitlines():
                print(f"  {line}")
    else:
        print("SUGGESTED ANALYSIS")
        print(SEP)
        print("  No structural changes detected.")
        print("  All findings update automatically from generate_site.py.")
        print("  See PLAYBOOK.md → 'Standard monthly update' for what to verify.")

    print(f"\n{SEP}\n")


# ── Archive index ─────────────────────────────────────────────────────────────

def _update_archive_index(
    period: str,
    period_label: str,
    generated_date: str,
    hero_headline: str,
    args: "argparse.Namespace",
) -> None:
    """Rebuild docs/archive/index.html with the current run prepended to the entry list."""
    archive_index = Path("docs/archive/index.html")

    entries = []
    if archive_index.exists():
        content = archive_index.read_text(encoding="utf-8")
        match = re.search(r"<!--ENTRIES:(.*?)-->", content, re.DOTALL)
        if match:
            try:
                entries = json.loads(match.group(1))
            except json.JSONDecodeError:
                entries = []

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
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Helvetica Neue",Arial,sans-serif;
          background:#f8fafc; color:#0f172a; font-size:15px; line-height:1.7;
          -webkit-font-smoothing:antialiased; }}
  nav {{ background:rgba(15,23,42,0.96); backdrop-filter:blur(10px);
         -webkit-backdrop-filter:blur(10px); padding:0 2rem;
         display:flex; align-items:center; gap:1.5rem; height:46px;
         border-bottom:1px solid rgba(255,255,255,0.04); }}
  nav .brand {{ color:#fff; font-weight:700; font-size:0.72rem;
                letter-spacing:0.1em; text-transform:uppercase; flex-shrink:0; }}
  nav a {{ color:rgba(255,255,255,0.45); text-decoration:none;
           font-size:0.73rem; transition:color 0.15s; }}
  nav a:hover {{ color:rgba(255,255,255,0.85); }}
  .container {{ max-width:700px; margin:0 auto; padding:3rem 2rem 5rem; }}
  h1 {{ font-size:1.6rem; font-weight:700; letter-spacing:-0.02em;
        margin-bottom:0.4rem; line-height:1.25; }}
  .sub {{ color:#64748b; font-size:0.875rem; margin-bottom:2.5rem; }}
  ul {{ list-style:none; padding:0; margin:0; border-top:1px solid #e2e8f0; }}
  li {{ padding:1.1rem 0; border-bottom:1px solid #e2e8f0; }}
  li a {{ font-size:0.9375rem; font-weight:500; color:#0f172a;
          text-decoration:none; display:block; margin-bottom:0.2rem;
          transition:color 0.15s; }}
  li a:hover {{ color:#2563eb; }}
  .meta {{ display:block; font-size:0.74rem; color:#94a3b8; letter-spacing:0.01em; }}
</style>
</head>
<body>
<nav>
  <span class="brand">McClatchy CSA</span>
  <a href="../index.html">← Current analysis</a>
</nav>
<!--ENTRIES:{entries_json}-->
<div class="container">
<h1>Past Editions</h1>
<p class="sub">Each snapshot is the full site as it existed when that data was ingested.</p>
<ul>
{items}</ul>
</div>
</body>
</html>"""

    archive_index.write_text(html, encoding="utf-8")
    print(f"✓ Updated archive index → {archive_index}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    """Run the full ingest pipeline: profile, archive, regenerate, commit."""
    parser = argparse.ArgumentParser(description="Ingest new T1 data and archive current site")
    parser.add_argument("--data-2025", default=DEFAULT_2025)
    parser.add_argument("--data-2026", default=DEFAULT_2026)
    parser.add_argument("--release",   default=None,
                        help="Release slug YYYY-MM (defaults to current month). "
                             "Pass explicitly when ingesting data from a prior month.")
    parser.add_argument("--note", default="")
    parser.add_argument("--no-commit", action="store_true")
    args = parser.parse_args()

    now = datetime.now()
    period = args.release or now.strftime("%Y-%m")
    period_label = datetime.strptime(period, "%Y-%m").strftime("%B %Y")
    generated_date = now.strftime("%Y-%m-%d")

    # 0. Governor briefing — print before any analysis output
    _print_governor_briefing()

    # 1. Profile new data + diff against previous run
    print("Profiling data files…")
    new_profile = _profile_data(args.data_2025, args.data_2026)
    prev_profile, prev_period = _load_prev_profile()
    _print_diff(prev_profile, prev_period, new_profile)

    # 2. Snapshot current site — archive the EXISTING page under its own slug,
    #    not the incoming period slug (avoids mis-labeling March analysis as April)
    current_site = Path("docs/index.html")
    old_slug = None
    hero_headline = ""

    if current_site.exists():
        content = current_site.read_text(encoding="utf-8")
        # Read data-run from existing file to get the correct archive label
        slug_match = re.search(r'<meta name="data-run" content="([^"]+)"', content)
        old_slug = slug_match.group(1) if slug_match else period
        hero_match = re.search(r'class="hero".*?<h1>(.*?)</h1>', content, re.DOTALL)
        if hero_match:
            hero_headline = re.sub(r"<[^>]+>", "", hero_match.group(1)).strip()

        archive_dir = Path("docs/archive") / old_slug
        archive_dir.mkdir(parents=True, exist_ok=True)

        old_label = datetime.strptime(old_slug, "%Y-%m").strftime("%B %Y") if re.match(r"\d{4}-\d{2}", old_slug) else old_slug
        banner = (
            f'<div style="background:#b45309;color:#fff;padding:0.75rem 1.5rem;'
            f'text-align:center;font-size:0.85rem;font-family:system-ui,sans-serif;">'
            f'Archived snapshot — {old_label}. '
            f'<a href="../../index.html" style="color:#fde68a;text-decoration:underline;">'
            f'View current analysis →</a></div>'
        )
        content = content.replace("<body>", f"<body>\n{banner}", 1)
        (archive_dir / "index.html").write_text(content, encoding="utf-8")
        print(f"✓ Archived {old_label} → docs/archive/{old_slug}/index.html")

        # Save data profile alongside snapshot for future diffs and Option B delta
        (archive_dir / "data_profile.json").write_text(
            json.dumps(new_profile, indent=2), encoding="utf-8"
        )
    else:
        print("⚠  No existing docs/index.html to archive")
        archive_dir = Path("docs/archive") / period
        archive_dir.mkdir(parents=True, exist_ok=True)

    # 3. Update archive index
    _update_archive_index(old_slug or period, period_label, generated_date, hero_headline, args)

    # 4. Regenerate site — pass --release so the new page carries the correct slug,
    #    and --skip-main-archive so generate_site.py doesn't double-archive
    cmd = [
        "python3", "generate_site.py",
        "--data-2025", args.data_2025,
        "--data-2026", args.data_2026,
        "--release",   period,
        "--skip-main-archive",
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("✗ generate_site.py failed — archive preserved, current site not updated")
        return 1

    # 4b. Regenerate all experiment pages so nav, theme, and export JS stay in sync.
    #     generate_experiment.py with no slug argument regenerates the index only.
    #     Each individual experiment page is regenerated by passing its spec file.
    _exp_specs = sorted(Path("experiments").glob("*.md")) if Path("experiments").exists() else []
    _exp_failures: list[str] = []
    for _spec in _exp_specs:
        _exp_result = subprocess.run(["python3", "generate_experiment.py", str(_spec)])
        if _exp_result.returncode != 0:
            _exp_failures.append(_spec.name)
    if _exp_failures:
        print(f"⚠ generate_experiment.py failed for: {', '.join(_exp_failures)} — experiment pages may be stale")
    elif _exp_specs:
        print(f"✓ Regenerated {len(_exp_specs)} experiment page(s)")

    # 5. Commit
    if not args.no_commit:
        note_suffix = f" — {args.note}" if args.note else ""
        msg = (
            f"Monthly ingest {period_label}{note_suffix}\n\n"
            f"Release: {period}\n"
            f"Archive: docs/archive/{old_slug or period}/\n"
            f"Data 2025: {args.data_2025}\n"
            f"Data 2026: {args.data_2026}\n"
            f"Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
        )
        subprocess.run(["git", "add", "docs/"])
        subprocess.run(["git", "commit", "-m", msg])
        print("✓ Committed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
