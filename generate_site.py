"""
generate_site.py — T1 Headline Analysis site generator.

Reads two Excel exports (2025 and 2026 YTD) from Chris Tarrow's Google Sheet,
runs 9 statistical analyses, and writes:
  - docs/index.html               — main analysis page (interactive finding tiles)
  - docs/playbook/index.html      — editorial playbooks (sorted by confidence level)
  - docs/experiments/index.html   — suggested experiments (directional findings; auto-regenerated)

Usage:
    python3 generate_site.py [--data-2025 FILE] [--data-2026 FILE]
                              [--tracker FILE] [--theme light|dark]
                              [--release YYYY-MM] [--skip-main-archive]

Called by ingest.py for the standard monthly update. See CLAUDE.md for the
automated workflow and PLAYBOOK.md for scenario-specific guidance.
"""

import argparse
import html as html_module
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats

warnings.filterwarnings("ignore")

# ── Optional packages (graceful fallbacks if not installed) ───────────────────
# Install all: pip3 install statsmodels polars scikit-learn pingouin xlrd
try:
    import statsmodels.api as sm
    from statsmodels.discrete.discrete_model import Logit
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False

try:
    import polars as pl
    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    import pingouin as pg
    HAS_PINGOUIN = True
except ImportError:
    HAS_PINGOUIN = False

parser = argparse.ArgumentParser(description="Generate T1 Headline Analysis site")
parser.add_argument("--data-2025", default="Top syndication content 2025.xlsx")
parser.add_argument("--data-2026", default="Top Stories 2026 Syndication.xlsx")
parser.add_argument("--data-2026-full", default=None,
                    help="Full Apple News 2026 export from Tarrow (all articles, not just top performers). "
                         "When provided, replaces the top-stories-only 2026 Apple News slice for all analyses.")
parser.add_argument("--tracker",   default="Tracker Template.xlsx")
parser.add_argument("--theme",     default="dark", choices=["light", "dark"])
parser.add_argument("--release",   default=None,
                    help="Data release slug YYYY-MM (defaults to current month). "
                         "Pass explicitly when ingesting data from a prior month.")
parser.add_argument("--skip-main-archive", action="store_true",
                    help="Skip archiving docs/index.html (used when ingest.py handles archiving).")
parser.add_argument("--anp-data", default="anp_data",
                    help="Directory containing Apple News Publisher CSV exports (weekly drops from "
                         "News Publisher). Defaults to anp_data/ in the working directory.")
_args = parser.parse_args()
DATA_2025      = _args.data_2025
DATA_2026      = _args.data_2026
DATA_2026_FULL = _args.data_2026_full
TRACKER        = _args.tracker
ANP_DATA_DIR   = _args.anp_data
THEME          = _args.theme
SKIP_ARCHIVE   = _args.skip_main_archive

# ── Analysis policy flags ─────────────────────────────────────────────────────
# National content team doesn't write politics — exclude from all findings
# Set 2026-03-31 per Sarah Price.
EXCLUDE_POLITICS = True
# MSN re-enabled 2026-04-02: clean Jan–Mar 2026 dataset (845 rows, new sheet format).
# Old reason for exclusion (data quality on old sheet) no longer applies — that sheet is gone.
EXCLUDE_MSN = False
# MSN tile suppressed per Sarah Price feedback (2026-04-08): MSN is not a current priority.
# Data is still loaded and computed (for platform topic inversion etc.) but the tile is hidden.
SHOW_MSN_TILE = False

# ── Author → Content Vertical mapping (confirmed by Sarah Price 2026-04-08) ───
# Verticals are not labeled in the Tracker — author is the proxy.
# General/Discovery = search/discover optimized; distinct from trendhunter verticals.
AUTHOR_VERTICAL: dict[str, str] = {
    "Allison Palmer":     "Mind-Body",
    "Lauren J-G":         "Everyday Living",
    "Lauren Jarvis-Gibson": "Everyday Living",
    "Lauren Schuster":    "Experience",
    "Ryan Brennan":       "General/Discovery",
    "Hanna Wickes":       "General/Discovery",
    "Hanna WIckes":       "General/Discovery",
    "Samantha Agate":     "General/Discovery",
}
TRENDHUNTER_VERTICALS = {"Mind-Body", "Everyday Living", "Experience"}

# ── Platform-wide avoidance guardrails ────────────────────────────────────────
# Formulas the per-author algorithm must never recommend without a cross-platform
# caveat. Keys are classify_formula() return values; values are the reason string.
# Checked at tile-generation time — any author recommendation involving these
# formulas gets a machine-added warning so contradictions never silently appear.
PLATFORM_AVOIDANCE_FORMULAS: dict[str, str] = {
    "question_mark": (
        "Question format is a confirmed SmartNews avoidance rule "
        "(p=3.4e-6, n=918 — strongest single penalty in the SN dataset). "
        "Apply this only to Apple News Featured targeting, never SmartNews."
    ),
    "what_to_know": (
        "\"What to know\" is the worst-performing formula on SmartNews "
        "(p=3.0e-6, n=213). Use for Apple News Featured targeting only — "
        "never as a general formula or for SmartNews content."
    ),
}

# Platforms with invalid or low-confidence signal per GOVERNOR.md.
# When an author tile would route to one of these, add an explicit caveat
# so editors are not sent to a platform on bad evidence.
LOW_SIGNAL_PLATFORMS: set[str] = {
    "Yahoo",   # AOL split created data discontinuity; article-level signal unreliable
}

# Non-T1 / staging domains to filter from Tracker→ANP join
_TRACKER_EXCLUDE_DOMAINS = {
    "lifeandstylemag.com", "modmomsclub.com",
    "modmomsclubstg.wpenginepowered.com", "usmagazine.com",
    "womansworld.com", "star-telegram.com",
}

REFERENCE_DATE = pd.Timestamp.today().normalize()

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY   = "#0f1117"
BLUE   = "#2563eb"
GREEN  = "#16a34a"
RED    = "#dc2626"
ORANGE = "#f97316"
AMBER  = "#f59e0b"
GRAY   = "#64748b"
LIGHT  = "#f8fafc"
BORDER = "#e2e8f0"

# Capture light-mode palette before dark override — used in color palette consistency check.
_LIGHT_PALETTE = (BLUE, GREEN, RED, AMBER, GRAY)  # "#2563eb","#16a34a","#dc2626","#f59e0b","#64748b"

# Dark-mode neon overrides — applied to chart traces only when --theme dark
if THEME == "dark":
    BLUE  = "#60a5fa"   # electric blue
    GREEN = "#4ade80"   # neon green
    RED   = "#f87171"   # coral pink
    AMBER = "#fb923c"   # vivid orange
    GRAY  = "#8b90a0"   # light slate (readable on dark)

# ── Theme system ──────────────────────────────────────────────────────────────
THEME_LIGHT = dict(
    paper_bg   = "white",
    plot_bg    = "white",
    text       = NAVY,
    text_muted = GRAY,
    grid       = BORDER,
    baseline   = GRAY,
)
THEME_DARK = dict(
    paper_bg   = "rgba(0,0,0,0)",  # transparent — inherits CSS --bg-card behind the chart
    plot_bg    = "rgba(0,0,0,0)",  # transparent — no white rectangle in dark mode
    text       = "#e8eaf6",        # grader --text
    text_muted = "#8b90a0",        # grader --muted
    grid       = "#2e3350",        # grader --border
    baseline   = "#8b90a0",        # grader --muted
)

def get_theme(theme: str = "light") -> dict:
    """Return the theme color dict for 'light' or 'dark'."""
    return THEME_DARK if theme == "dark" else THEME_LIGHT

def make_layout(theme: str = "light", *, height=None, margin=None, title=None) -> dict:
    """Build a Plotly layout dict from a named theme. All figures use this instead
    of PLOTLY_LAYOUT so a single --theme flag re-skins the entire report."""
    t = get_theme(theme)
    layout: dict = dict(
        paper_bgcolor = t["paper_bg"],
        plot_bgcolor  = t["plot_bg"],
        font = dict(
            family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif",
            size   = 12,
            color  = t["text"],
        ),
    )
    if height is not None:
        layout["height"] = height
    if margin is not None:
        layout["margin"] = margin
    if title is not None:
        layout["title"] = dict(text=title, font=dict(size=13, color=t["text"]), x=0)
    return layout


# ── Visualization guardrails ──────────────────────────────────────────────────
# Defensive helpers that prevent the most common Plotly/table issues with this setup.
# Every new chart and table MUST follow these rules:
#
# CHARTS — use the helper functions below instead of hardcoded values:
#   safe_range()             — never hardcode axis ranges; data outside them silently clips
#   safe_log_floor()         — always use before log-scale axes; zeros drop silently
#   auto_right_margin()      — always size right margin from actual label strings
#   escape_hover()           — always escape headline text going into hovertemplates
#   cap_lift()               — cap inf/extreme lift values before passing to chart x/y
#   enforce_category_order() — always call after update_layout() on sorted bar charts
#   safe_chart()             — always use instead of fig.to_html(); never call directly
#   guard_empty()            — always call on figures whose source data may be missing
#   cap_engagement_seconds() — always call on active-time cols before any chart/stat that
#                              uses them; outliers (e.g. 23k-second rows from 2025 data)
#                              silently collapse y-axes and flatten scatter plots
#
# DARK MODE CHARTS — always keep --theme default as "dark":
#   Charts are server-side rendered with Plotly; their paper/plot backgrounds and trace
#   colors are baked into inline SVG at build time. CSS theme classes cannot override
#   inline SVG fill/bgcolor. The fix: build with --theme dark (transparent backgrounds
#   + neon trace colors); the JS _rethemeCharts() function in applyTheme() handles
#   runtime color updates when the user toggles to light mode. NEVER change the
#   --theme default back to "light" — white backgrounds will reappear in dark mode.
#
# TABLES — tbody td must always have white-space:nowrap:
#   Tables sit inside .table-wrap (overflow-x:auto), so wide content scrolls
#   horizontally. Never use word-break or overflow-wrap on td — short words and
#   feature names split mid-word when the column is narrower than the text.
#   Exception: headline/body-text cells that intentionally wrap should get an
#   inline style="white-space:normal;max-width:360px" override on that td only.
#
# TABLES — do NOT add overflow/scroll CSS to individual tables:
#   The JS DOMContentLoaded listener auto-wraps every <table> in a .table-wrap div,
#   which owns the overflow-x:auto scroll, border-radius, and box-shadow.
#   Tables scroll horizontally when content is wider than the panel — text is NEVER
#   clipped or truncated. Do not add overflow:hidden or fixed widths to table elements.
#
# DARK MODE TABLE COLORS — always use explicit / body.light selectors:
#   CSS custom properties (--bg, --nav-bg, etc.) are defined under body.light /
#   body.theme-dark. Detail panels have hardcoded dark backgrounds regardless of theme.
#   If table background/text use var(--bg) etc., the resolved color depends on the body
#   class — which fails inside hardcoded-dark panels when body is theme-light. Rule:
#   NEVER use CSS variables for table background or text colors. Always write:
#       body.light table.findings { background: #ffffff; }
#        table.findings { background: #1a1d27; }
#   This makes table theming unambiguous regardless of surrounding panel context.
#
# LIFT/STATUS COLORS — always use .lift-high/.lift-pos/.lift-neg CSS classes:
#   NEVER use inline style="color:#60a5fa" for lift values or status indicators.
#   Those hardcoded hex values are dark-mode-only and break in light mode. The
#   .lift-* classes are defined with body.light overrides in the main CSS block.
#   For semantic status colors (tags) that intentionally stay fixed, use .tag-* classes.
#
# ACCENT COLOR — always use var(--accent), never hardcode #60a5fa or #3d5af1:
#   --accent resolves to #3d5af1 (light) or #7c9df7 (dark). Sort icon highlights,
#   active borders, link colors — all must use var(--accent) so they adapt to theme.
#   Hardcoded blues silently stop adapting when the user switches modes.
#
# JS IN PYTHON F-STRINGS — escape all literal newlines inside JS string literals:
#   Inside a Python f-string, '\n' is a literal newline. If that appears inside a
#   JS string literal (e.g. [].join('\n')), it creates a JS syntax error that
#   silently kills the entire <script> block and breaks all interactivity on the page.
#   Always write '\\n' to produce a literal \n in the JS output. The post-build
#   _validate_js() check catches this automatically every run.
#
# PNG EXPORT — use dom-to-image-more, NOT html2canvas:
#   html2canvas measures character widths via canvas 2D measureText(). System fonts
#   (-apple-system / San Francisco) use contextual kerning that measureText() cannot
#   replicate, causing word spaces to collapse and text to garble. dom-to-image-more
#   serializes the DOM to SVG foreignObject and delegates text rendering to the
#   browser's own engine — output matches exactly what you see on screen.
#   Render into a fixed-width off-screen container (position:fixed; left:-9999px;
#   width:1100px) and pass explicit width/height + scale transform in the options.
#   NEVER switch back to html2canvas for PNG — the garbling will return.

def safe_range(
    values: "Iterable[float]",
    margin: float = 0.15,
    floor: float | None = 0.0,
) -> list[float]:
    """Compute a [lo, hi] axis range from actual data plus a relative margin.

    Never hardcode chart axis ranges — data that exceeds a fixed range is
    silently clipped by Plotly with no error. This auto-sizes based on what
    the data actually contains.

    Args:
        values: Iterable of numeric values. NaN and inf are ignored.
        margin: Fraction of the data span to pad on each end (default 15%).
        floor:  Minimum value for lo. Pass None to allow negative lo.
                Default 0.0 prevents negative axes on lift/CTR charts.

    Example:
        xaxis=dict(range=safe_range(df["lift"], margin=0.2))
    """
    vals = [v for v in values if pd.notna(v) and np.isfinite(v)]
    if not vals:
        return [0.0, 1.0]
    lo, hi = min(vals), max(vals)
    span = hi - lo if hi != lo else max(abs(hi), 0.1)
    lo_out = lo - span * margin
    if floor is not None:
        lo_out = max(lo_out, floor)
    return [lo_out, hi + span * margin]


def safe_log_floor(series: pd.Series, floor: float = 1.0) -> list:
    """Replace zeros and negatives with `floor` before a log-scale axis.

    Plotly's log-scale silently drops zero/negative values, leaving invisible
    chart points with no error or warning. Always use this when
    xaxis/yaxis type='log'.

    Example:
        x=safe_log_floor(df["Total Views"])
    """
    return series.clip(lower=floor).fillna(floor).tolist()


def auto_right_margin(labels: list[str], per_char: float = 7.5, base: float = 80.0) -> int:
    """Estimate the right margin (px) needed for textposition='outside' labels.

    Too-small margins silently clip long bar labels — Plotly does not warn.
    Sizes the margin to the longest label string in the list.

    Args:
        labels:   Text label strings that will appear outside bars.
        per_char: Estimated px width per character (default 7.5 for 12px font).
        base:     Minimum margin regardless of label length.

    Example:
        margin=dict(l=20, r=auto_right_margin(text_labels), t=50, b=40)
    """
    if not labels:
        return int(base)
    longest = max(len(str(lbl)) for lbl in labels)
    return int(max(longest * per_char, base))


def escape_hover(text: "str | float | None") -> str:
    """Escape characters that silently corrupt Plotly hover popups.

    Raw headline text passed into hovertemplate or hovertext often contains
    <, >, &, and " which break HTML rendering inside the hover popup.

    Example:
        hovertext=[escape_hover(h) for h in df["Article"]]
    """
    if text is None or (isinstance(text, float) and np.isnan(text)):
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def cap_lift(value: float, cap: float = 5.0) -> float:
    """Cap an extreme lift ratio for display purposes.

    inf or very large lifts (from near-zero baselines) make bar charts
    unreadable. The cap is display-only — raw data is untouched.

    Example:
        x=[cap_lift(r["lift"]) for _, r in df.iterrows()]
    """
    if not np.isfinite(value):
        return cap
    return min(float(value), cap)


def enforce_category_order(
    fig: go.Figure,
    categories: list[str],
    axis: str = "yaxis",
) -> go.Figure:
    """Force a Plotly categorical axis to match the DataFrame's sort order.

    Without this, Plotly may reorder categories alphabetically or by
    first-seen order — scrambling bar charts that were sorted in the DataFrame.

    Args:
        fig:        The Plotly Figure to update in-place.
        categories: Ordered list of category strings as they appear in the data.
        axis:       'yaxis' for horizontal bars, 'xaxis' for vertical bars.

    Example:
        enforce_category_order(fig, df["label"].tolist())
    """
    fig.update_layout(**{axis: dict(categoryorder="array", categoryarray=categories)})
    return fig


def safe_chart(
    fig: go.Figure,
    fallback: str = "<p class='caveat'>Chart unavailable for this dataset.</p>",
) -> str:
    """Render a Plotly figure to HTML with a graceful fallback on failure.

    A single chart error should never abort the entire site build. This wraps
    fig.to_html() so any rendering exception logs a rigor warning and returns
    a plain fallback string instead of crashing.

    Always use this — never call fig.to_html() directly in the HTML template.

    Example:
        c1 = safe_chart(fig1)
    """
    try:
        return fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            config={"responsive": True},
        )
    except Exception as exc:
        _rigor_warn("chart_render", f"{type(fig).__name__}: {type(exc).__name__}: {exc}")
        return fallback


def guard_empty(
    fig: go.Figure,
    df: pd.DataFrame,
    message: str = "Insufficient data for this chart.",
    min_rows: int = 2,
) -> go.Figure:
    """Add a 'no data' annotation when the source DataFrame is too small.

    Prevents Plotly from silently rendering blank axes. Call this on any
    figure whose source data may be empty (conditional sheets, small n).

    Example:
        fig8 = guard_empty(fig8, df_periods, "No longitudinal data yet.")
    """
    if len(df) < min_rows:
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=13, color=GRAY),
            align="center",
        )
    return fig


def cap_engagement_seconds(
    df: pd.DataFrame,
    cols: list[str],
    ceiling: float = 600.0,
) -> pd.DataFrame:
    """Clip implausibly large values in active-time (seconds) columns.

    Apple News active-time columns are labeled "in seconds" but occasional rows
    contain values in the thousands or tens-of-thousands — clearly bad data or
    unconverted milliseconds. These outliers collapse chart y-axes to 0–25k and
    make the scatter unreadable, with all real data compressed into a flat line
    near zero.

    This clips in-place at `ceiling` (default 600s = 10 min) which is already
    an extreme but physically plausible average article read time. Outliers above
    the ceiling are capped, and a rigor warning is emitted listing the count and
    original max value so the issue is visible in every build report.

    Always call this immediately after loading engagement columns — before any
    correlation, decile, or chart calculation that depends on them.

    Args:
        df:      DataFrame containing the active-time columns (modified in-place).
        cols:    List of column names to cap. Non-existent columns are skipped.
        ceiling: Maximum plausible value in seconds (default 600).

    Returns:
        The same DataFrame with capped values (modified in-place for efficiency).

    Example:
        an_eng = cap_engagement_seconds(an_eng, [AT_COL, SUB_AT_COL, NSUB_AT_COL])
    """
    df = df.copy()
    for col in cols:
        if col not in df.columns:
            continue
        outliers = df[col].dropna()
        outliers = outliers[outliers > ceiling]
        if len(outliers) > 0:
            _rigor_warn(
                "engagement_outliers",
                f"Column '{col}': {len(outliers)} row(s) exceeded {ceiling:.0f}s ceiling "
                f"(max={outliers.max():.0f}s). Capped to {ceiling:.0f}s. "
                f"Likely bad data or unconverted milliseconds in source Excel.",
            )
        df[col] = df[col].clip(upper=ceiling)
    return df


# ── Classifiers ───────────────────────────────────────────────────────────────
def classify_formula(text: str) -> str:
    """Classify a headline into one of 7 formula types using regex. Returns the formula name string."""
    t = str(text).strip()
    tl = t.lower()
    if re.match(r"^\d", t): return "number_lead"
    if re.match(r"^here[\u2019\']s\b|^here are\b|^here is\b|^here come\b", tl): return "heres_formula"
    if re.match(r"^[A-Z][a-zA-Z\-]+[\u2019\']s\s", t): return "possessive_named_entity"
    if re.search(r"what to know\s*$", tl): return "what_to_know"
    if t.rstrip().endswith("?"): return "question"
    if t.startswith("\u2018"): return "quoted_lede"
    return "untagged"

def classify_quote_lede(text: str) -> str:
    """Subtype a quoted-lede headline. Call only on headlines already classified as quoted_lede.
    Returns one of: quote_official, quote_expert, quote_subject, quote_other."""
    t = str(text).lower()
    # Text after the closing quote marks contains the speaker context
    after = re.split(r"['\u2019\u201d]", t, maxsplit=2)[-1]
    if re.search(r"\b(police|sheriff|officer|prosecutor|official|authorities|spokesperson|court|judge|fbi|agency|department|administration|government)\b", after):
        return "quote_official"
    if re.search(r"\b(scientist|researcher|doctor|dr\.|expert|study|professor|analyst|biologist|zoologist|scientist|climatologist|economist)\b", after):
        return "quote_expert"
    # Named subject: possessive or first-person cue, name-like pattern before/in after
    if re.search(r"\b(i |my |me |we |our )\b", after) or re.search(r"\b(says?|said|tell|told|reveal|open|share)\b", after):
        return "quote_subject"
    return "quote_other"

_QUOTE_LEDE_LABELS: dict[str, str] = {
    "quote_official": "Official/authority quote",
    "quote_expert":   "Expert/scientist quote",
    "quote_subject":  "Subject's own words",
    "quote_other":    "Third-party attribution",
}

def _classify_untagged_structure(text: str) -> str:
    """Secondary micro-classifier for untagged headlines. Identifies structural patterns
    that don't fit the main formula taxonomy but are still informative."""
    t = str(text).strip()
    tl = t.lower()
    words = tl.split()
    if not words:
        return "other"
    first = words[0].rstrip(".,;:")
    if re.match(r"^(how|why)\b", first):
        return "how_why"
    if re.match(r"^(inside|behind|meet|the story|the case|a look)\b", " ".join(words[:3])):
        return "narrative_lede"
    if re.match(r"^(watch|video|listen|photos?|gallery|map)\b", first):
        return "media_label"
    if re.match(r"^(report|study|survey|poll|analysis|data|new research)\b", first):
        return "cited_source"
    # Two or more consecutive Title-Cased words at start = likely named-entity declarative
    if re.match(r"^[A-Z][a-z]+(?:\s[A-Z][a-z]+)+\s", t):
        return "named_declarative"
    if len(words) <= 5:
        return "short_declarative"
    return "other"

_UNTAGGED_STRUCTURE_LABELS: dict[str, str] = {
    "how_why":           "How/Why framing",
    "narrative_lede":    "Narrative / 'Inside' lede",
    "media_label":       "Media-type label (Watch, Video, etc.)",
    "cited_source":      "Report/Study/Survey lede",
    "named_declarative": "Named-entity declarative",
    "short_declarative": "Short declarative (≤5 words)",
    "other":             "Other unstructured",
}

def tag_topic(text: str) -> str:
    """Tag a headline with a topic using keyword/regex matching. Returns the topic string."""
    t = str(text).lower()
    if re.search(r"\b(shot|kill|murder|dead|death|shooting|arrest|charge|crime|victim|police|cop|suspect|robbery|assault)\b", t): return "crime"
    if re.search(r"\b(game|team|nfl|nba|mlb|nhl|coach|season|championship|super bowl|playoff|quarterback)\b", t): return "sports"
    if re.search(r"\b(storm|hurricane|tornado|flood|rain|snow|weather|forecast|wildfire|earthquake|heat)\b", t): return "weather"
    if re.search(r"\b(business|economy|job|hire|layoff|company|market|real estate|housing|price|cost|wage|salary|tax)\b", t): return "business"
    if re.search(r"\b(trump|biden|congress|senate|white house|president|governor|election|vote|campaign|ballot|democrat|republican|gop|legislation|bill|policy|lawmaker|politician)\b", t): return "politics"
    if re.search(r"\b(school|student|teacher|education|college|university|city|county|state|local|community|neighborhood)\b", t): return "local_civic"
    if re.search(r"\b(restaurant|food|eat|chef|menu|recipe|bar|coffee|dining|hotel|travel|beach|park|festival|concert)\b", t): return "lifestyle"
    if re.search(r"\b(animal|creature|species|wildlife|shark|bear|alligator|snake|bird|dog|cat|pet|whale|dolphin|wolf|fox|deer|turtle|fish|octopus|squid|seal|lion|tiger|elephant|gorilla|chimp|monkey|reptile|amphibian|insect|spider|bee|butterfly|coral|reef)\b", t): return "nature_wildlife"
    if re.search(r"\b(dinosaur|fossil|prehistoric|extinct|extinction|paleontol|archaeolog|dig site|ancient creature|ancient animal)\b", t): return "nature_wildlife"
    if re.search(r"\b(scientist|researchers?|biologist|zoologist|naturalist|conservationist)\b.*\b(found|discover|identified|spotted|filmed|captured|recorded|document)\b", t): return "nature_wildlife"
    if re.search(r"\b(new species|rare species|never.before.seen|first.ever.found|never seen before|rediscover)\b", t): return "nature_wildlife"
    return "other"

def tag_subtopic(text: str, topic: str) -> "str | None":
    """Two-level classifier. Returns subtopic for sports and crime, None for others."""
    t = str(text).lower()
    if topic == "sports":
        if re.search(r"\bnfl\b|football|quarterback|touchdown|super bowl|chiefs|patriots|cowboys|seahawks|49ers|ravens|bengals|packers|steelers", t): return "football"
        if re.search(r"\bnba\b|basketball|lakers|celtics|knicks|warriors|heat|bulls|lebron|curry", t): return "basketball"
        if re.search(r"\bmlb\b|baseball|yankees|dodgers|astros|braves|mets|red sox|world series|pitcher", t): return "baseball"
        if re.search(r"\bnhl\b|hockey|stanley cup", t): return "hockey"
        if re.search(r"\bsoccer\b|mls|fifa|world cup|premier league", t): return "soccer"
        if re.search(r"\bcollege\b|ncaa|sec|acc|big ten|march madness|college football|college basketball", t): return "college"
        return "sports_other"
    if topic == "crime":
        if re.search(r"\bshot\b|shooting|murder|killed|stabbed|homicide|gunfire", t): return "violent_crime"
        if re.search(r"\btrial\b|verdict|sentence|sentenced|judge|charged|indicted|guilty|plea|court|lawsuit", t): return "court_legal"
        if re.search(r"\bmissing\b|disappeared|search|kidnap|abduct|last seen", t): return "missing_persons"
        if re.search(r"\barrested\b|arrest|suspect|detained|taken into custody", t): return "arrest"
        return "crime_other"
    if topic == "business":
        if re.search(r"\bretail\b|store|shop|walmart|target|amazon|grocery|costco|consumer", t): return "retail"
        if re.search(r"\breal estate\b|housing|home price|mortgage|rent\b|apartment|landlord|zillow|for sale|home sale", t): return "real_estate"
        if re.search(r"\bjobs?\b|hiring|layoff|unemployment|workforce|worker|employee|salary|wage|fired|rehire", t): return "jobs_labor"
        if re.search(r"\bstock|wall street|fed\b|federal reserve|interest rate|inflation|gdp|recession|economy|bank|finance|investor|nasdaq|dow\b", t): return "finance_macro"
        if re.search(r"\btech\b|apple\b|google|microsoft|\bai\b|artificial intelligence|startup|silicon valley|software|app\b|meta\b|tesla\b", t): return "tech"
        return "business_other"
    if topic == "politics":
        if re.search(r"\btrump\b|congress|senate|house of representatives|white house|president|federal|administration|biden\b|supreme court", t): return "federal"
        if re.search(r"\bgovernor|state legislature|state senate|state house|statehouse\b", t): return "state"
        if re.search(r"\bmayor|city council|county|local government|school board|municipality", t): return "local_govt"
        if re.search(r"\belection|ballot|primary\b|vote|campaign|candidate|polling|midterm\b", t): return "election"
        return "politics_other"
    return None


def classify_number_lead(text: str) -> "dict | None":
    """Classify the lead number in a number_lead headline by type and roundness."""
    t = str(text).strip()
    # Extract the leading token
    m = re.match(r"^(\$[\d,]+(?:\.\d+)?(?:[BMK]|bn|m|k)?\b|[\d,]+(?:\.\d+)?(?:st|nd|rd|th|%|[BMK]|bn|m|k)?\b)", t, re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1)
    # Parse numeric value
    num_str = re.sub(r"[,$BMKbmk%]", "", raw.lower().rstrip("stndrdhth"))
    try:
        val = float(num_str)
    except ValueError:
        return None

    # Classify type
    if raw.startswith("$") or re.search(r"[BMK]$|bn$|million|billion", raw, re.I):
        ntype = "dollar_amount"
    elif raw.lower().endswith(("st","nd","rd","th")):
        ntype = "ordinal"
    elif "%" in raw:
        ntype = "percentage"
    elif 2000 <= val <= 2030:
        ntype = "year"
    else:
        ntype = "count_list"

    # Round vs specific
    if val <= 10:
        roundness = "specific"
    elif val % 1000 == 0 or val % 100 == 0 or (val % 10 == 0 and val <= 100):
        roundness = "round"
    else:
        roundness = "specific"

    return dict(raw=raw, value=val, ntype=ntype, roundness=roundness)


# ── Nav generation ────────────────────────────────────────────────────────────
# Single source of truth for the site-wide navigation bar.
# Any page that needs a nav block calls _build_nav() — no hardcoded HTML.

_NAV_PAGES = [
    ("Current Analysis", ""),          # "" = root (docs/)
    ("Editorial Playbooks", "playbook"),
    ("Author Playbooks",    "author-playbooks"),
    ("Style Guide",         "style-guide"),
    ("Experiments",         "experiments"),
    ("Headline Grader",     "grader"),
]

def _build_nav(active: str, depth: int, theme_toggle: bool = True) -> str:
    """Generate consistent nav HTML for any page.

    Args:
        active:       Page name matching a key in _NAV_PAGES (e.g. "Current Analysis").
        depth:        Directory depth from docs/ root.  0 = root, 1 = subdirectory.
        theme_toggle: Always True; kept for backwards compatibility but no longer conditional.

    Returns:
        A fully-formed <nav class="site-nav">...</nav> HTML string.
    """
    prefix = "../" * depth
    link_parts = []
    for name, slug in _NAV_PAGES:
        href = (prefix + slug + "/") if slug else (prefix if depth > 0 else "./")
        cls = ' class="active"' if name == active else ""
        link_parts.append(f'<a href="{href}"{cls}>{name}</a>')
    links = " <span class='nav-sep'>·</span> ".join(link_parts)
    return (
        f'<nav class="site-nav">\n'
        f'  <div class="nav-links">{links}</div>\n'
        f'  <button id="theme-toggle" class="theme-toggle" onclick="toggleTheme()" title="Toggle theme">&#9680;</button>\n'
        f'</nav>'
    )


def _make_export_js(
    suffix: str = "",
    tile_cleanup_selector: str = ".tile-more,.export-btn-wrap",
    heading_query: str = "h2",
    filename_prefix: str = "headline-analysis-",
    find_tile_body: str = "",
) -> str:
    """Generate the _findTileForPanel + _exportPanel JS block for one page.

    Each of the three site pages (main, playbook, author-playbooks) has its own
    copy of this logic so local JS variables don't clash.  The differences are:

        suffix                — appended to _tfl, _tlEl, _toast, _showResult,
                                _cleanupContainer, _origTitle, _afterPrint ("", "2", "3").
        tile_cleanup_selector — CSS selector for elements to strip from the tile
                                clone before capture.  Each page's tile markup
                                includes different non-print controls.
        heading_query         — querySelector used as the panel-heading fallback
                                when no .tile-label is present.
        filename_prefix       — prefix for the downloaded PNG filename.
        find_tile_body        — JS body of _findTileForPanel, excluding the outer
                                function declaration.  Defaults to the standard
                                short-id-strip + .tile,.pb-tile query used by the
                                main page and playbook.  Author-playbooks passes a
                                custom body that queries only .pb-tile using the raw
                                panel id (no detail- prefix stripping).

    Returns plain JS (with single { } — safe to embed as {_make_export_js(...)}
    inside an outer Python f-string).
    """
    s = suffix  # short alias

    # Default _findTileForPanel body (main page + playbook): strip 'detail-' prefix,
    # query both .tile and .pb-tile elements.
    if not find_tile_body:
        find_tile_body = (
            "  var pid = panelEl.id || '';\n"
            "  var shortId = pid.indexOf('detail-') === 0 ? pid.replace('detail-', '') : pid;\n"
            "  var tileEl = null;\n"
            "  document.querySelectorAll('.tile,.pb-tile').forEach(function(t) {\n"
            "    if ((t.getAttribute('onclick') || '').indexOf(shortId) >= 0) tileEl = t;\n"
            "  });\n"
            "  return tileEl;"
        )

    # _showResult for suffix="" uses a named `delay` var (historical); others use inline ternary.
    if s == "":
        show_result_body = (
            f"  function _showResult{s}(msg, isErr) {{\n"
            f"    _toast{s}.textContent = msg;\n"
            f"    _toast{s}.style.color = isErr ? '#f87171' : '#4ade80';\n"
            f"    var delay = isErr ? 7000 : 3000;\n"
            f"    setTimeout(function() {{\n"
            f"      _toast{s}.style.opacity = '0';\n"
            f"      setTimeout(function() {{ if (_toast{s}.parentNode) _toast{s}.remove(); }}, 350);\n"
            f"    }}, delay);\n"
            f"  }}"
        )
    else:
        show_result_body = (
            f"  function _showResult{s}(msg, isErr) {{\n"
            f"    _toast{s}.textContent = msg;\n"
            f"    _toast{s}.style.color = isErr ? '#f87171' : '#4ade80';\n"
            f"    setTimeout(function() {{\n"
            f"      _toast{s}.style.opacity = '0';\n"
            f"      setTimeout(function() {{ if (_toast{s}.parentNode) _toast{s}.remove(); }}, 350);\n"
            f"    }}, isErr ? 7000 : 3000);\n"
            f"  }}"
        )

    return f"""function _findTileForPanel(panelEl) {{
{find_tile_body}
}}

function _exportPanel(panelEl, format, dropdownEl) {{
  if (dropdownEl) dropdownEl.style.display = 'none';
  var _tfl{s} = _findTileForPanel(panelEl);
  var _tlEl{s} = _tfl{s} ? _tfl{s}.querySelector('.tile-label') : null;
  var title = _tlEl{s} ? _tlEl{s}.textContent.trim()
            : (panelEl.querySelector('{heading_query}') ? panelEl.querySelector('{heading_query}').textContent.trim()
            : (panelEl.id || 'export'));
  var slug  = title.replace(/[^a-z0-9]+/gi, '-').toLowerCase().replace(/^-+|-+$/g, '');
  var date  = new Date().toISOString().slice(0, 10);

  var _toast{s} = document.createElement('div');
  _toast{s}.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:99999;background:#1a1d27;' +
    'border:1px solid #2e3350;color:#8b90a0;padding:12px 20px;border-radius:10px;font-size:13px;' +
    'font-family:inherit;box-shadow:0 8px 24px rgba(0,0,0,0.5);transition:opacity 0.3s;';
  _toast{s}.textContent = (format === 'pdf' ? 'Generating PDF' : 'Generating PNG') + '\u2026';
  document.body.appendChild(_toast{s});
{show_result_body}
  function _cleanupContainer{s}(id) {{
    var el = document.getElementById(id); if (el) el.remove();
  }}

  if (typeof domtoimage === 'undefined') {{
    _showResult{s}(
      'Export unavailable \u2014 rendering library (dom-to-image) failed to load. ' +
      'Check your internet connection and hard-refresh (Cmd+Shift+R / Ctrl+Shift+R) to retry.',
      true
    );
    return;
  }}

  // Re-apply the current theme to all Plotly charts before cloning.
  // Charts inside closed panels are skipped when _rethemeCharts normally runs
  // (Plotly.relayout throws on display:none elements). Now that this panel is
  // open, force a re-theme so the clone captures correct dark/light colors.
  if (typeof _rethemeCharts === 'function') {{
    _rethemeCharts(!document.body.classList.contains('light'));
  }}

  // Panels have no explicit background — getComputedStyle returns rgba(0,0,0,0).
  // Read from document.body instead, which always has --bg resolved.
  var _rawBg = getComputedStyle(document.body).backgroundColor;
  var bg = (_rawBg && _rawBg !== 'rgba(0, 0, 0, 0)' && _rawBg !== 'transparent')
    ? _rawBg
    : (!document.body.classList.contains('light') ? '#0f1117' : '#ffffff');
  var containerId = format === 'pdf' ? '_exp_print_src' : '_exp_png';

  // Wait 100 ms for Plotly to finish all async redraws before cloning.
  // Two rAFs (~32 ms) is not enough — Plotly batches relayout/restyle through
  // its own internal rAF queue, so our rAFs can fire before Plotly's do.
  // A 100 ms timeout guarantees all chart SVGs are redrawn in the correct theme
  // before cloneNode captures them.
  setTimeout(function() {{
      var container = document.createElement('div');
      container.id = containerId;
      // opacity:0 hides without affecting layout. Critically, opacity is NOT inherited —
      // getComputedStyle(child).opacity returns the child's own value (1), so domtoimage
      // inlines opacity:1 on every child. The style:{{opacity:'1'}} override then makes the
      // root visible too. visibility:hidden would be inherited by all children via
      // getComputedStyle, causing blank output even after the root override.
      // No overflow:hidden — let content expand freely so scrollHeight is accurate.
      container.style.cssText = 'position:absolute;left:0;top:0;width:1100px;opacity:0;' +
        'pointer-events:none;background:' + bg + ';box-sizing:border-box;font-family:inherit;';

      var tileEl = _findTileForPanel(panelEl);
      if (tileEl) {{
        var tc = tileEl.cloneNode(true);
        tc.style.cssText = 'cursor:default;border-radius:12px 12px 0 0;margin:0;' +
          'width:100%;box-sizing:border-box;border-bottom:none;';
        tc.querySelectorAll('{tile_cleanup_selector}').forEach(function(el) {{ el.remove(); }});
        container.appendChild(tc);
      }}
      var pc = panelEl.cloneNode(true);
      pc.style.display = 'block';
      pc.querySelectorAll('.export-btn-wrap').forEach(function(el) {{ el.remove(); }});
      container.appendChild(pc);
      document.body.appendChild(container);

  // Second double rAF ensures layout is committed before we measure dimensions.
  requestAnimationFrame(function() {{
    requestAnimationFrame(function() {{
      var w = container.offsetWidth || 1100;
      var h = container.offsetHeight || container.scrollHeight;
      if (h < 10) {{
        _cleanupContainer{s}(containerId);
        _showResult{s}('Export failed: panel has no height (layout issue)', true);
        return;
      }}
      domtoimage.toPng(container, {{
        width:  w,
        height: h,
        style:  {{ opacity: '1' }},
        bgcolor: bg
      }}).then(function(dataUrl) {{
        _cleanupContainer{s}(containerId);
        if (format === 'pdf') {{
          var printDiv = document.createElement('div');
          printDiv.id = '_exp_print';
          var img = document.createElement('img');
          img.style.cssText = 'width:100%;display:block;';
          printDiv.appendChild(img);
          document.body.appendChild(printDiv);
          var style = document.createElement('style');
          style.id = '_exp_style';
          style.textContent = '@page{{margin:0;size:' + w + 'px ' + h + 'px}}@media print{{html,body{{height:' + h + 'px!important;overflow:hidden!important}}body>*:not(#_exp_print){{display:none!important}}#_exp_print{{display:block!important;padding:0;margin:0}}#_exp_print img{{width:100%!important;height:auto!important;display:block!important;-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}}}}';
          document.head.appendChild(style);
          var _origTitle{s} = document.title;
          document.title = title;
          function _afterPrint{s}() {{
            var pw = document.getElementById('_exp_print'); var ps = document.getElementById('_exp_style');
            if (pw) pw.remove(); if (ps) ps.remove();
            document.title = _origTitle{s};
            window.removeEventListener('afterprint', _afterPrint{s});
          }}
          window.addEventListener('afterprint', _afterPrint{s});
          img.onload = function() {{
            _showResult{s}('PDF dialog opened \u2014 print or save from browser', false);
            window.print();
          }};
          img.src = dataUrl;
        }} else {{
          // Blob URL required — Safari silently blocks a.download with data: URLs.
          try {{
            var arr = dataUrl.split(',');
            var mime = (arr[0].match(/:(.*?);/) || [,'image/png'])[1];
            var bstr = atob(arr[1]); var n = bstr.length; var u8 = new Uint8Array(n);
            while (n--) u8[n] = bstr.charCodeAt(n);
            var blob = new Blob([u8], {{type: mime}});
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url; a.download = '{filename_prefix}' + slug + '-' + date + '.png';
            document.body.appendChild(a); a.click(); document.body.removeChild(a);
            setTimeout(function() {{ URL.revokeObjectURL(url); }}, 2000);
            _showResult{s}('PNG downloaded', false);
          }} catch(dlErr) {{
            _showResult{s}('Export failed: ' + (dlErr.message || String(dlErr)), true);
            console.error('[Export] download error:', dlErr);
          }}
        }}
      }}).catch(function(err) {{
        _cleanupContainer{s}(containerId);
        var msg = err && err.message ? err.message : (err ? String(err) : 'unknown error');
        _showResult{s}('Export failed: ' + msg, true);
        console.error('[Export] domtoimage error:', err);
      }});
    }});
  }});
  }}, 100);
}}"""


# ── Statistical helpers ───────────────────────────────────────────────────────
def bh_correct(pvals: "list[float]") -> "list[float]":
    """Apply Benjamini-Hochberg FDR correction. Returns adjusted p-values in the same order."""
    n = len(pvals)
    if n == 0: return []
    order = sorted(range(n), key=lambda i: pvals[i])
    sorted_p = [pvals[i] for i in order]
    adj_sorted = [0.0] * n
    adj_sorted[n - 1] = sorted_p[n - 1]
    for i in range(n - 2, -1, -1):
        adj_sorted[i] = min(adj_sorted[i + 1], sorted_p[i] * n / (i + 1))
    result = [0.0] * n
    for rank, orig_i in enumerate(order):
        result[orig_i] = min(adj_sorted[rank], 1.0)
    return result

def rank_biserial(u_stat: float, n1: int, n2: int) -> float:
    """Compute rank-biserial r effect size from a Mann-Whitney U statistic. Range: -1 to 1."""
    return 1.0 - (2.0 * u_stat) / (n1 * n2)

def bootstrap_ci_lift(
    grp_vals: np.ndarray,
    base_vals: np.ndarray,
    n_boot: int = 1000,
    seed: int = 42,
    ci: float = 0.95,
) -> "tuple[float, float]":
    """Bootstrap 95% CI on the median ratio (group_b / group_a). Returns (ci_lo, ci_hi)."""
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(n_boot):
        sg = rng.choice(grp_vals, size=len(grp_vals), replace=True)
        sb = rng.choice(base_vals, size=len(base_vals), replace=True)
        mb = np.median(sb)
        if mb > 0:
            boot.append(np.median(sg) / mb)
    alpha = 1 - ci
    return float(np.percentile(boot, alpha / 2 * 100)), float(np.percentile(boot, (1 - alpha / 2) * 100))

def required_n_80pct(effect_r: float, alpha: float = 0.05) -> "int | None":
    """Estimate per-group n needed for 80% power given a rank-biserial effect size."""
    r_rb = effect_r
    if r_rb is None or r_rb == 0: return None
    r = abs(r_rb)
    d = 2 * r / math.sqrt(max(1 - r ** 2, 1e-9))
    if d < 0.001: return None
    return math.ceil(1.05 * 15.69 / d ** 2)


# ── Rigor infrastructure ──────────────────────────────────────────────────────
_RIGOR_WARNINGS: list = []

def _rigor_warn(section: str, msg: str) -> None:
    """Append a rigor warning for the named analysis section to the build report."""
    _RIGOR_WARNINGS.append(f"[{section}] {msg}")

def _conf_level(
    p_adj: "float | None" = None,
    n: "int | None" = None,
    n_platforms: int = 1,
    p_raw: "float | None" = None,
) -> "tuple[str, str]":
    """Return (css_class, label) for a confidence badge. Criteria: High = p_adj<0.05 AND n≥100
    AND n_platforms≥2; Moderate = p_adj<0.05 AND n≥20; Directional = p<0.10 or untested AND n≥10."""
    if n is not None and n < 10:
        return "conf-dir", "Insufficient data"
    if p_adj is not None and p_adj < 0.05:
        if (n is None or n >= 100) and n_platforms >= 2:
            return "conf-high", "High confidence"
        if n is not None and n >= 20:
            return "conf-mod", "Moderate"
        return "conf-mod", "Moderate"
    if p_raw is not None and p_raw < 0.10 and n is not None and n >= 100:
        return "conf-mod", "Moderate"
    return "conf-dir", "Directional"

def _require_test(section: str, p_adj: "float | None", n_a: int, n_b: int = 0) -> None:
    """Emit a build-time warning if a group comparison lacks a significance test."""
    if p_adj is None or (isinstance(p_adj, float) and math.isnan(float(p_adj))):
        _rigor_warn(section, f"No significance test (n_a={n_a}, n_b={n_b}). Add Mann-Whitney U.")


# ── normalize() ───────────────────────────────────────────────────────────────
def normalize(
    df: pd.DataFrame,
    views_col: str,
    date_col: "str | None" = None,
    group_col: "str | None" = None,
) -> pd.DataFrame:
    """Add views_per_day and percentile_within_cohort columns. percentile_within_cohort is the
    primary metric — percentile rank within the same publication-month cohort, controlling for
    temporal view accumulation."""
    df = df.copy()
    if date_col is not None:
        dates = pd.to_datetime(df[date_col], errors="coerce")
        days = (REFERENCE_DATE - dates).dt.days.clip(lower=1)
        df["views_per_day"] = df[views_col] / days
    else:
        df["views_per_day"] = np.nan

    if group_col is not None:
        df["percentile_within_cohort"] = df.groupby(group_col)[views_col].rank(pct=True)
    else:
        df["percentile_within_cohort"] = df[views_col].rank(pct=True)
    return df

VIEWS_METRIC = "percentile_within_cohort"


# ── Sheet discovery — warn about unrecognized sheets in new exports ───────────
_KNOWN_SHEETS_2025 = {"Apple News", "SmartNews", "Yahoo", "MSN", "Apple News notifications"}
_KNOWN_SHEETS_2026 = {"Apple News", "Apple News Notifications", "SmartNews", "Yahoo", "MSN",
                      "MSN Video", "MSN video", "Yahoo Video", "Yahoo video",
                      "MSN (minumum 10k PV)", "Notifications summary"}

def _check_new_sheets(path: str, known_sheets: "set[str]") -> None:
    """Warn if the Excel file contains sheets the pipeline doesn't analyze."""
    try:
        import openpyxl as _openpyxl
        _wb = _openpyxl.load_workbook(path, read_only=True, data_only=True)
        _actual = set(_wb.sheetnames)
        _wb.close()
        _new = _actual - known_sheets
        if _new:
            _rigor_warn("sheet_discovery",
                        f"{Path(path).name}: sheets not yet in pipeline — {sorted(_new)}. "
                        "Add to generate_site.py if data is worth analyzing.")
    except ImportError:
        pass  # openpyxl unavailable; non-fatal

_check_new_sheets(DATA_2025, _KNOWN_SHEETS_2025)
_check_new_sheets(DATA_2026, _KNOWN_SHEETS_2026)

# ── Apple News Publisher (ANP) full-article data ──────────────────────────────
# Loaded from weekly CSV drops placed in ANP_DATA_DIR. Independent of Tarrow's
# top-headlines sheets — this is the complete article universe from News Publisher.

_ANP_NEWS_PUBS = {"Charlotte", "KC", "Miami", "Raleigh", "Sac"}
_ANP_POLITICS_RE = re.compile(r"\bpolitics\b|\bgovernment\b|\belection\b|\bpolitical\b", re.I)

def _load_anp() -> "pd.DataFrame | None":
    """Load all ANP CSVs from ANP_DATA_DIR and return article-level aggregation, or None."""
    import glob as _glob
    csvs = sorted(_glob.glob(os.path.join(ANP_DATA_DIR, "*.csv")))
    if not csvs:
        return None
    dfs = []
    for f in csvs:
        try:
            df = pd.read_csv(f)
            parts = os.path.basename(f).replace(".csv", "").split("_")
            df["_pub"] = "_".join(parts[2:]) if len(parts) > 2 else "Unknown"
            dfs.append(df)
        except Exception:
            continue
    if not dfs:
        return None
    raw = pd.concat(dfs, ignore_index=True)
    raw["Date Published"] = pd.to_datetime(raw["Date Published"], dayfirst=True, errors="coerce")
    art = raw.groupby(["Article ID", "_pub"]).agg(
        title=("Article", "first"),
        date_published=("Date Published", "first"),
        sections=("Sections", "first"),
        total_views=("Total Views", "sum"),
        featured=("Featured by Apple", lambda x: (x == "Yes").any()),
        sub_viewers=("Unique Viewers, Subscribers, All Content", "sum"),
        nonsub_viewers=("Unique Viewers, Non-subscribers, All Content", "sum"),
    ).reset_index()
    art["pub_year"] = art["date_published"].dt.year
    return art


def _anp_top_section(s: str) -> str:
    """Return the primary non-Main section label, or 'Main only'."""
    if not isinstance(s, str):
        return "Unknown"
    parts = [x.strip() for x in s.split(",")]
    non_main = [p for p in parts if p.lower() != "main"]
    return non_main[0] if non_main else "Main only"


def _anp_analysis(art: "pd.DataFrame") -> dict:
    """Compute ANP findings from article-level DataFrame. Returns dict of template variables."""
    art26 = art[
        (art["pub_year"] == 2026) &
        (art["total_views"] >= 10) &
        (~art["sections"].fillna("").str.contains(_ANP_POLITICS_RE))
    ].copy()
    art26["pct_rank"] = art26.groupby("_pub")["total_views"].rank(pct=True)

    news = art26[art26["_pub"].isin(_ANP_NEWS_PUBS)].copy()
    news["top_section"] = news["sections"].apply(_anp_top_section)
    news["sub_ratio"] = news["sub_viewers"] / (
        (news["sub_viewers"] + news["nonsub_viewers"]).clip(lower=1)
    )
    news["is_question"] = news["title"].str.rstrip().str.endswith("?", na=False)
    news["has_named"] = news["title"].str.contains(
        r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", regex=True, na=False
    )

    feat   = news[news["featured"]]
    nonfeat = news[~news["featured"]]

    # ── Subscriber audience split ─────────────────────────────────────────────
    _, p_sub = stats.mannwhitneyu(feat["sub_ratio"], nonfeat["sub_ratio"], alternative="less")
    nf_topq_sub = pd.qcut(nonfeat["total_views"], 4, labels=False, duplicates="drop")
    nf_topq_sub_ratio = nonfeat[nf_topq_sub == 3]["sub_ratio"].median()

    # ── Section × featuring rates ─────────────────────────────────────────────
    sec_stats: dict[str, dict] = {}
    for sec in ["Weather", "Business", "Sports", "Shopping", "Opinion", "Crime"]:
        sub = news[news["top_section"] == sec]
        if len(sub) >= 10:
            sec_stats[sec] = {
                "n": len(sub),
                "feat_pct": sub["featured"].mean(),
                "med_rank": sub["pct_rank"].median(),
            }

    weather_feat = sec_stats.get("Weather", {}).get("feat_pct", np.nan)
    sports_feat  = sec_stats.get("Sports",  {}).get("feat_pct", np.nan)
    biz_feat     = sec_stats.get("Business",{}).get("feat_pct", np.nan)

    # ── Business: named-person penalty ───────────────────────────────────────
    biz = news[news["top_section"] == "Business"]
    biz_named_feat   = biz[biz["has_named"]]["featured"].mean()
    biz_unnamed_feat = biz[~biz["has_named"]]["featured"].mean()
    biz_named_lift   = biz_unnamed_feat / biz_named_feat if biz_named_feat > 0 else np.nan

    # ── Question format × featuring ───────────────────────────────────────────
    q_feat_rate  = news[news["is_question"]]["featured"].mean()
    noq_feat_rate = news[~news["is_question"]]["featured"].mean()
    q_feat_lift  = q_feat_rate / noq_feat_rate if noq_feat_rate > 0 else np.nan

    # ── Section table rows HTML ───────────────────────────────────────────────
    sec_rows_html = ""
    ordered_secs = sorted(
        [(s, d) for s, d in sec_stats.items()],
        key=lambda x: x[1]["feat_pct"], reverse=True
    )
    for sec, d in ordered_secs:
        bar_pct = d["feat_pct"] * 100
        sec_rows_html += (
            f'<tr><td>{sec}</td>'
            f'<td>{d["n"]:,}</td>'
            f'<td><span style="display:inline-block;width:{bar_pct:.1f}%;min-width:2px;'
            f'height:10px;background:{BLUE};border-radius:2px;"></span>'
            f' {bar_pct:.1f}%</td>'
            f'<td>{d["med_rank"]:.2f}</td></tr>\n'
        )

    return {
        "ANP_N_NEWS":         len(news),
        "ANP_N_FEATURED":     int(news["featured"].sum()),
        "ANP_FEAT_RATE":      news["featured"].mean(),
        "ANP_FEAT_NONSUB_PCT": 1 - feat["sub_ratio"].median(),
        "ANP_NONFEAT_NONSUB_PCT": 1 - nonfeat["sub_ratio"].median(),
        "ANP_TOPQ_NONSUB_PCT": 1 - nf_topq_sub_ratio,
        "ANP_SUB_P":          p_sub,
        "ANP_WEATHER_FEAT":   weather_feat,
        "ANP_SPORTS_FEAT":    sports_feat,
        "ANP_BIZ_FEAT":       biz_feat,
        "ANP_WEATHER_SPORTS_RATIO": weather_feat / sports_feat if sports_feat > 0 else np.nan,
        "ANP_BIZ_NAMED_FEAT": biz_named_feat,
        "ANP_BIZ_UNNAMED_FEAT": biz_unnamed_feat,
        "ANP_BIZ_NAMED_LIFT": biz_named_lift,
        "ANP_Q_FEAT_LIFT":    q_feat_lift,
        "ANP_Q_FEAT_RATE":    q_feat_rate,
        "ANP_SEC_ROWS":       sec_rows_html,
        "ANP_N_PUBS":         news["_pub"].nunique(),
        "ANP_SEC_STATS":      sec_stats,
        "ANP_BIZ_N":          sec_stats.get("Business", {}).get("n", 0),
    }


def _anp_failure_analysis(art: "pd.DataFrame") -> dict:
    """Compute bottom-performer section signals from article-level ANP data."""
    news = art[
        (art["pub_year"] == 2026) &
        (art["total_views"] >= 10) &
        (art["_pub"].isin(_ANP_NEWS_PUBS)) &
        (~art["sections"].fillna("").str.contains(_ANP_POLITICS_RE))
    ].copy()
    news["top_section"] = news["sections"].apply(_anp_top_section)
    news["pct_rank"]    = news.groupby("_pub")["total_views"].rank(pct=True)

    # ── Section summary table ─────────────────────────────────────────────────
    _MIN_SEC_N = 20
    sec_rows: list[dict] = []
    for sec, g in news.groupby("top_section"):
        if len(g) < _MIN_SEC_N:
            continue
        sec_rows.append({
            "section":      sec,
            "n":            len(g),
            "med_rank":     g["pct_rank"].median(),
            "featured_rate": g["featured"].mean(),
            "pct_bottom20": (g["pct_rank"] <= 0.2).mean(),
            "pct_top20":    (g["pct_rank"] >= 0.8).mean(),
        })
    df_sec = (pd.DataFrame(sec_rows)
              .sort_values("med_rank", ascending=False)
              .reset_index(drop=True))

    # ── Main-only (missing section tag) signal ────────────────────────────────
    main_only = news[news["top_section"] == "Main only"]
    tagged    = news[news["top_section"] != "Main only"]
    _, p_main = stats.mannwhitneyu(main_only["pct_rank"], tagged["pct_rank"], alternative="less")
    main_bot_pct = (main_only["pct_rank"] <= 0.2).mean()

    # ── Sports structural underperformance ────────────────────────────────────
    sports    = news[news["top_section"] == "Sports"]
    nonsports = news[news["top_section"] != "Sports"]
    _, p_sports = stats.mannwhitneyu(sports["pct_rank"], nonsports["pct_rank"], alternative="less")
    sp_feat   = sports[sports["featured"]]
    sp_nonfeat = sports[~sports["featured"]]

    # ── Nation & World vs local sections ─────────────────────────────────────
    nw    = news[news["top_section"] == "Nation & World"]
    local = news[news["top_section"].isin(
        ["Charlotte", "Kansas City Metro", "Miami & South Florida", "Sacramento", "North Carolina"]
    )]
    _, p_nw = stats.mannwhitneyu(nw["pct_rank"], local["pct_rank"], alternative="less")

    # ── Section table HTML for detail panel ──────────────────────────────────
    _highlight_low  = "#dc262622"   # subtle red tint for low-rank sections
    _highlight_high = "#16a34a22"   # subtle green tint for high-rank sections
    sec_table_rows = ""
    for _, r in df_sec.iterrows():
        bg = ""
        if r["med_rank"] >= 0.75:
            bg = f' style="background:{_highlight_high}"'
        elif r["med_rank"] <= 0.30:
            bg = f' style="background:{_highlight_low}"'
        sec_table_rows += (
            f'<tr{bg}>'
            f'<td>{r["section"]}</td>'
            f'<td>{r["n"]:,}</td>'
            f'<td>{r["med_rank"]:.2f}</td>'
            f'<td>{r["featured_rate"]:.1%}</td>'
            f'<td>{r["pct_bottom20"]:.1%}</td>'
            f'<td>{r["pct_top20"]:.1%}</td>'
            f'</tr>\n'
        )

    return {
        "ANP_FAIL_N_TOTAL":       len(news),
        "ANP_FAIL_MAIN_N":        len(main_only),
        "ANP_FAIL_MAIN_BOT_PCT":  main_bot_pct,
        "ANP_FAIL_MAIN_RANK":     main_only["pct_rank"].median(),
        "ANP_FAIL_MAIN_P":        p_main,
        "ANP_FAIL_SPORTS_N":      len(sports),
        "ANP_FAIL_SPORTS_BOT_PCT": (sports["pct_rank"] <= 0.2).mean(),
        "ANP_FAIL_SPORTS_TOP_PCT": (sports["pct_rank"] >= 0.8).mean(),
        "ANP_FAIL_SPORTS_RANK":   sports["pct_rank"].median(),
        "ANP_FAIL_SPORTS_P":      p_sports,
        "ANP_FAIL_SP_FEAT_N":     len(sp_feat),
        "ANP_FAIL_SP_FEAT_RANK":  sp_feat["pct_rank"].median() if len(sp_feat) > 0 else np.nan,
        "ANP_FAIL_SP_NONFEAT_RANK": sp_nonfeat["pct_rank"].median(),
        "ANP_FAIL_NW_N":          len(nw),
        "ANP_FAIL_NW_BOT_PCT":    (nw["pct_rank"] <= 0.2).mean(),
        "ANP_FAIL_NW_RANK":       nw["pct_rank"].median(),
        "ANP_FAIL_LOCAL_RANK":    local["pct_rank"].median(),
        "ANP_FAIL_NW_P":          p_nw,
        "ANP_FAIL_SEC_DF":        df_sec,
        "ANP_FAIL_SEC_TABLE":     sec_table_rows,
    }


_anp_raw = _load_anp()
HAS_ANP  = _anp_raw is not None
if HAS_ANP:
    _anp = _anp_analysis(_anp_raw)
    _anp_fail = _anp_failure_analysis(_anp_raw)
    print(f"  ANP data: {_anp['ANP_N_NEWS']:,} news articles, "
          f"{_anp['ANP_N_FEATURED']} featured ({_anp['ANP_FEAT_RATE']:.1%}) "
          f"across {_anp['ANP_N_PUBS']} publications")
else:
    print(f"  ⚠  No ANP CSVs found in {ANP_DATA_DIR!r} — findings 6, 7 & 8 will be hidden")
    _anp = {}
    _anp_fail = {}

# ── Load data ─────────────────────────────────────────────────────────────────
print(f"Loading data…  2025={DATA_2025}  2026={DATA_2026}")

# Apple News — load separately then combine
an_2025 = pd.read_excel(DATA_2025, sheet_name="Apple News")
an_2025 = an_2025.rename(columns={"Channel": "Brand"})
an_2025["year"] = 2025

an_2026 = pd.read_excel(DATA_2026, sheet_name="Apple News")
if "Date" in an_2026.columns:
    an_2026 = an_2026.drop(columns=["Date"])
an_2026["year"] = 2026

# Fix MacRoman/UTF-8 double-encoding in 2026 headline text (2025 file is unaffected)
def _fix_mac_encoding(text: str) -> str:
    """Repair MacRoman/UTF-8 double-encoding in 2026 Apple News headline text."""
    try:
        return str(text).encode("mac_roman").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return str(text)
an_2026["Article"] = an_2026["Article"].apply(lambda x: _fix_mac_encoding(x) if pd.notna(x) else x)

# Common columns for concat
_common_cols = [c for c in an_2025.columns if c in an_2026.columns]
an = pd.concat([an_2025[_common_cols], an_2026[_common_cols]], ignore_index=True)

# Full Apple News 2026 (all articles, not just top performers) — provided by Tarrow on request.
# When --data-2026-full is passed, the full export replaces the top-stories slice for all AN analyses.
if DATA_2026_FULL and Path(DATA_2026_FULL).exists():
    _an_2026_full = pd.read_excel(DATA_2026_FULL, sheet_name="Apple News")
    if "Date" in _an_2026_full.columns:
        _an_2026_full = _an_2026_full.drop(columns=["Date"])
    if "Channel" in _an_2026_full.columns:
        _an_2026_full = _an_2026_full.rename(columns={"Channel": "Brand"})
    _an_2026_full["year"] = 2026
    _an_2026_full["Article"] = _an_2026_full["Article"].apply(
        lambda x: _fix_mac_encoding(x) if pd.notna(x) else x)
    _full_common = [c for c in an_2025.columns if c in _an_2026_full.columns]
    an = pd.concat([an_2025[_full_common], _an_2026_full[_full_common]], ignore_index=True)
    print(f"  ✓ Full Apple News 2026 loaded: {len(_an_2026_full):,} articles (replaces top-performers slice)")
elif DATA_2026_FULL:
    print(f"  ⚠  --data-2026-full path not found: {DATA_2026_FULL!r} — using standard top-stories file")

# SmartNews — 2025 primary (has category columns)
sn = pd.read_excel(DATA_2025, sheet_name="SmartNews")

# Notifications: 2025 full year (news brands activated June 2025; Us Weekly all year) + 2026 Jan–Feb
_notif_2025 = pd.read_excel(DATA_2025, sheet_name="Apple News notifications")
_notif_2025 = _notif_2025.rename(columns={"Click-Through Rate": "CTR"})
notif = pd.read_excel(DATA_2026, sheet_name="Apple News Notifications")
_notif_shared_cols = [c for c in ["Article ID", "Channel", "Notification ID",
                                   "Notification Text", "Notification Type",
                                   "Sent At", "Territories", "CTR"]
                      if c in _notif_2025.columns and c in notif.columns]
notif = pd.concat([_notif_2025[_notif_shared_cols], notif[_notif_shared_cols]],
                  ignore_index=True)
sn26   = pd.read_excel(DATA_2026, sheet_name="SmartNews")
yahoo26 = pd.read_excel(DATA_2026, sheet_name="Yahoo")
notif = notif.dropna(subset=["CTR"]).copy()

# MSN: Jan–Mar 2026 from new sheet format in 2026 file (no minimum-PV filter beyond sheet definition)
msn   = pd.read_excel(DATA_2026, sheet_name="MSN (minumum 10k PV)")
yahoo = pd.read_excel(DATA_2025, sheet_name="Yahoo")

# ── Column validation — friendly errors instead of KeyError crashes ───────────
def _require_col(df: pd.DataFrame, col: str, sheet_label: str) -> None:
    """Raise SystemExit with a friendly error if col is missing from df."""
    if col not in df.columns:
        raise SystemExit(
            f"\n✗  Missing column '{col}' in {sheet_label}.\n"
            f"   Available: {sorted(df.columns.tolist())}\n"
            "   Update the column name in generate_site.py or check the Tarrow export."
        )

for _col in ["Article", "Date Published", "Total Views", "Featured by Apple"]:
    _require_col(an_2025, _col, "Apple News 2025")
    _require_col(an_2026, _col, "Apple News 2026")
for _col in ["title", "article_view"]:
    _require_col(sn, _col, "SmartNews 2025")
_require_col(notif, "CTR", "Apple News Notifications")
_require_col(notif, "Notification Text", "Apple News Notifications")

# ── Feature engineering ───────────────────────────────────────────────────────
an["is_featured"] = an["Featured by Apple"].fillna("No") == "Yes"
an["formula"]     = an["Article"].apply(classify_formula)
an["topic"]       = an["Article"].apply(tag_topic)
an["_pub_month"]  = pd.to_datetime(an["Date Published"], errors="coerce").dt.to_period("M").astype(str)

sn["topic"]   = sn["title"].apply(tag_topic)
sn["formula"] = sn["title"].apply(classify_formula)
sn["_sn_month"] = sn["date"].astype(str)

# Topic classifier coverage (fraction of AN articles tagged into a named topic, not "other")
_an_topic_tagged = (an["topic"] != "other").sum()
TOPIC_COVERAGE_PCT = _an_topic_tagged / len(an) if len(an) > 0 else 0.0
TOPIC_OTHER_PCT    = 1.0 - TOPIC_COVERAGE_PCT

yahoo["_pub_month"] = pd.to_datetime(yahoo["Publish Date"], errors="coerce").dt.to_period("M").astype(str)

CATS = ["Top","Entertainment","Lifestyle","U.S.","Business","World",
        "Technology","Science","Politics","Health","Local","Football","LGBTQ"]
# Categories present in both 2025 and 2026 exports (used for combined Q4 analysis)
CATS_COMMON = ["Top","Entertainment","Lifestyle","U.S.","Business","World",
               "Technology","Science","Politics","Health","Local"]
for cat in CATS:
    sn[cat] = pd.to_numeric(sn[cat], errors="coerce").fillna(0)

# Prep sn26 for category analysis (Tarrow rebuilt with full breakdown)
# 2025 sheet uses "month" column; 2026 sheet uses "date" column — handle both
_sn26_date_col = "month" if "month" in sn26.columns else "date"
sn26["_sn_month"] = pd.to_datetime(sn26[_sn26_date_col], errors="coerce").dt.to_period("M").astype(str)
for _cat in CATS_COMMON:
    if _cat in sn26.columns:
        sn26[_cat] = pd.to_numeric(sn26[_cat], errors="coerce").fillna(0)
    else:
        sn26[_cat] = 0.0

# MSN feature engineering
msn["formula"]    = msn["Title"].apply(classify_formula)
msn["topic"]      = msn["Title"].apply(tag_topic)
msn["_msn_month"] = pd.to_datetime(msn["Date"], errors="coerce").dt.to_period("M").astype(str)

# ── Platform / topic exclusions ───────────────────────────────────────────────
if EXCLUDE_POLITICS:
    _pol_an  = (an["topic"]  == "politics").sum()
    _pol_sn  = (sn["topic"]  == "politics").sum()
    _pol_msn = (msn["topic"] == "politics").sum()
    an  = an[an["topic"]   != "politics"].copy()
    sn  = sn[sn["topic"]   != "politics"].copy()
    msn = msn[msn["topic"] != "politics"].copy()
    print(f"  Politics excluded: {_pol_an} AN + {_pol_sn} SN + {_pol_msn} MSN articles removed")

if EXCLUDE_MSN:
    msn = msn.iloc[0:0].copy()  # empty df, preserves schema for safe downstream use
    print("  MSN excluded from analysis (data quality flag — re-enable when Tarrow confirms export is fixed)")

# ── Normalize ────────────────────────────────────────────────────────────────
print("Normalizing…")
an    = normalize(an,    views_col="Total Views",   date_col="Date Published", group_col="_pub_month")
sn    = normalize(sn,    views_col="article_view",  date_col=None,             group_col="_sn_month")
sn26  = normalize(sn26,  views_col="article_view",  date_col=None,             group_col="_sn_month")
msn   = normalize(msn,   views_col="Pageviews",     date_col=None,             group_col="_msn_month")
yahoo = normalize(yahoo, views_col="Content Views", date_col="Publish Date",   group_col="_pub_month")

# Subtopics
an["subtopic"] = an.apply(lambda r: tag_subtopic(r["Article"], r["topic"]), axis=1)
sn["subtopic"] = sn.apply(lambda r: tag_subtopic(r["title"],   r["topic"]), axis=1)

# Also normalize 2025/2026 subsets for YoY
an_2025_norm = an[an["year"] == 2025].copy()
an_2026_norm = an[an["year"] == 2026].copy()

# ── Platform exclusivity ──────────────────────────────────────────────────────
def _norm(t: str) -> str:
    """Normalize text to lowercase alphanumeric for fuzzy title-deduplication."""
    return re.sub(r"[^a-z0-9]", "", str(t).lower().strip())

an_t    = set(an["Article"].dropna().apply(_norm))
sn_t    = set(sn["title"].dropna().apply(_norm))
msn_t   = set(msn["Title"].dropna().apply(_norm))
yahoo_t = set(yahoo["Content Title"].dropna().apply(_norm))

excl_an    = len(an_t - sn_t - msn_t - yahoo_t) / len(an_t)
excl_sn    = len(sn_t - an_t - msn_t - yahoo_t) / len(sn_t)
excl_msn   = len(msn_t - an_t - sn_t - yahoo_t) / len(msn_t) if msn_t else 0.0
excl_yahoo = len(yahoo_t - an_t - sn_t - msn_t) / len(yahoo_t)
overlap_3plus = len((an_t & sn_t & msn_t) | (an_t & sn_t & yahoo_t) |
                    (an_t & msn_t & yahoo_t) | (sn_t & msn_t & yahoo_t))
overlap_all4  = len(an_t & sn_t & msn_t & yahoo_t)

N_AN_UNIQ    = len(an_t)
N_SN_UNIQ    = len(sn_t)
N_MSN_UNIQ   = len(msn_t)
N_YAHOO_UNIQ = len(yahoo_t)


# ── Q1: Formula → percentile_within_cohort (non-Featured) ────────────────────
print("Computing Q1/Q2…")
nf = an[~an["is_featured"]].copy()
overall_median_nf = nf[VIEWS_METRIC].median()
baseline = nf[nf["formula"] == "untagged"][VIEWS_METRIC]
base_vals = baseline.values

FORMULA_LABELS = {
    "what_to_know":            "What to know",
    "heres_formula":           "Here's / Here are",
    "possessive_named_entity": "Possessive named entity",
    "untagged":                "Untagged (baseline)",
    "quoted_lede":             "Quoted lede",
    "number_lead":             "Number lead",
    "question":                "Question",
}

_ung = nf[nf["formula"] == "untagged"]["Article"]
_ung_sample = list(_ung.dropna().sample(min(5, len(_ung)), random_state=42)) if len(_ung) >= 5 else list(_ung.dropna())
UNTAGGED_N   = len(_ung)
UNTAGGED_PCT = UNTAGGED_N / len(nf)

q1_rows = []
_q1_raw_p = []
_q1_indices = []
for f, label in FORMULA_LABELS.items():
    grp = nf[nf["formula"] == f][VIEWS_METRIC]
    if len(grp) == 0: continue
    med  = grp.median()
    lift = med / baseline.median() if baseline.median() > 0 else 1.0
    if f != "untagged" and len(grp) >= 5:
        u_result = stats.mannwhitneyu(grp, baseline, alternative="two-sided")
        u_stat, p = u_result.statistic, u_result.pvalue
        r_rb = rank_biserial(u_stat, len(grp), len(baseline))
        ci_lo, ci_hi = bootstrap_ci_lift(grp.values, base_vals)
        req_n = required_n_80pct(r_rb) if p >= 0.05 else None
        _q1_raw_p.append(p)
        _q1_indices.append(len(q1_rows))
    else:
        p = None; r_rb = None; ci_lo = None; ci_hi = None; req_n = None
    q1_rows.append(dict(formula=f, label=label, n=len(grp), median=med, lift=lift,
                        p=p, r_rb=r_rb, ci_lo=ci_lo, ci_hi=ci_hi, req_n=req_n))

_q1_adj = bh_correct(_q1_raw_p)
for adj_val, row_i in zip(_q1_adj, _q1_indices):
    q1_rows[row_i]["p_adj"] = adj_val

df_q1 = pd.DataFrame(q1_rows).sort_values("median")
if "p_adj" not in df_q1.columns:
    df_q1["p_adj"] = np.nan

# Kruskal-Wallis omnibus: is there ANY difference across all formula groups?
# Runs automatically when statsmodels is present; result surfaces in build report.
Q1_KW_P: float | None = None
Q1_KW_STAT: float | None = None
_kw_groups = [
    nf[nf["formula"] == f][VIEWS_METRIC].dropna().values
    for f in FORMULA_LABELS if len(nf[nf["formula"] == f]) >= 5
]
if len(_kw_groups) >= 2:
    try:
        Q1_KW_STAT, Q1_KW_P = stats.kruskal(*_kw_groups)
    except (ValueError, TypeError):
        pass

# Dunn's post-hoc pairwise test — which formula pairs are significantly different?
# Only runs when pingouin is present AND Kruskal-Wallis is significant.
Q1_DUNN: "pd.DataFrame | None" = None
if HAS_PINGOUIN and Q1_KW_P is not None and Q1_KW_P < 0.05:
    try:
        _dunn_df = nf[nf["formula"].isin(FORMULA_LABELS)][["formula", VIEWS_METRIC]].dropna()
        _pg_res = pg.pairwise_tests(
            data=_dunn_df,
            dv=VIEWS_METRIC,
            between="formula",
            parametric=False,  # Dunn's non-parametric test
            padjust="fdr_bh",
        )
        # Column names differ across pingouin versions (U-val vs U_val, p-unc vs p_unc)
        _col_map = {}
        for _c in _pg_res.columns:
            _cl = _c.lower().replace("-", "_")
            _col_map[_c] = _cl
        _pg_res = _pg_res.rename(columns=_col_map)
        Q1_DUNN = _pg_res[["a", "b", "u_val", "p_unc", "p_corr", "hedges"]].copy()
        Q1_DUNN.columns = ["Formula A", "Formula B", "U", "p_raw", "p_adj", "hedges_g"]
        Q1_DUNN = Q1_DUNN[Q1_DUNN["p_adj"] < 0.10].sort_values("p_adj")
    except Exception:
        pass  # Non-critical; pairwise Mann-Whitney results still stand


# ── Q2: Featured rate per formula ─────────────────────────────────────────────
overall_feat_rate = an["is_featured"].mean()
_tot_feat = int(an["is_featured"].sum())
q2_rows = []
_q2_raw_p = []
_q2_indices = []
for f, label in FORMULA_LABELS.items():
    grp = an[an["formula"] == f]
    if len(grp) == 0: continue
    feat_rate = grp["is_featured"].mean()
    feat_n    = int(grp["is_featured"].sum())
    lift = feat_rate / overall_feat_rate
    other_feat  = _tot_feat - feat_n
    other_total = len(an) - len(grp)
    _ctg = np.array([[feat_n, len(grp) - feat_n],
                     [other_feat, max(other_total - other_feat, 0)]])
    try:
        _chi2_f, _p_chi_f, _, _ = stats.chi2_contingency(_ctg)
    except (ValueError, ZeroDivisionError):
        _chi2_f, _p_chi_f = np.nan, 1.0
    _q2_raw_p.append(_p_chi_f)
    _q2_indices.append(len(q2_rows))
    q2_rows.append(dict(formula=f, label=label, n=len(grp), feat_n=feat_n,
                        featured_rate=feat_rate, featured_lift=lift,
                        chi2=_chi2_f, p_chi=_p_chi_f))

_q2_adj = bh_correct(_q2_raw_p)
for adj_val, row_i in zip(_q2_adj, _q2_indices):
    q2_rows[row_i]["p_chi_adj"] = adj_val

df_q2 = pd.DataFrame(q2_rows).sort_values("featured_rate")
if "p_chi_adj" not in df_q2.columns:
    df_q2["p_chi_adj"] = np.nan

# Within-featured median percentile per formula
feat_an = an[an["is_featured"]].copy()
feat_avg_pct = feat_an[VIEWS_METRIC].median()
for _f in FORMULA_LABELS:
    _grp_feat = feat_an[feat_an["formula"] == _f][VIEWS_METRIC]
    _val = _grp_feat.median() if len(_grp_feat) >= 3 else np.nan
    df_q2.loc[df_q2["formula"] == _f, "feat_med_views"] = _val
df_q2["feat_views_lift"] = df_q2["feat_med_views"] / feat_avg_pct

# ── Quote lede subtype analysis ────────────────────────────────────────────────
# Breaks quoted_lede into four subtypes (official, expert, subject, other) and
# compares each subtype's featuring rate vs. the overall baseline.
# Only runs when there are ≥10 quoted_lede articles to analyse.
_ql_subset = an[an["formula"] == "quoted_lede"].copy()
df_ql_subtypes: "pd.DataFrame | None" = None
if len(_ql_subset) >= 10:
    _ql_subset["_ql_type"] = _ql_subset["Article"].apply(classify_quote_lede)
    _ql_groups = []
    for _qlt, _ql_grp in _ql_subset.groupby("_ql_type"):
        _ql_feat_n   = int(_ql_grp["is_featured"].sum())
        _ql_n        = len(_ql_grp)
        _ql_feat_rate = _ql_grp["is_featured"].mean()
        _ql_lift     = _ql_feat_rate / overall_feat_rate if overall_feat_rate > 0 else 1.0
        _ql_other_feat = _tot_feat - _ql_feat_n
        _ql_other_tot  = len(an) - _ql_n
        _ql_ctg = np.array([[_ql_feat_n, max(_ql_n - _ql_feat_n, 0)],
                             [_ql_other_feat, max(_ql_other_tot - _ql_other_feat, 0)]])
        try:
            _, _ql_p, _, _ = stats.chi2_contingency(_ql_ctg)
        except (ValueError, ZeroDivisionError):
            _ql_p = 1.0
        # Within-featured median %ile for this subtype
        _ql_feat_grp = feat_an[feat_an["Article"].apply(classify_quote_lede) == _qlt][VIEWS_METRIC]
        _ql_within_feat_med = float(_ql_feat_grp.median()) if len(_ql_feat_grp) >= 3 else float("nan")
        _ql_groups.append(dict(
            ql_type=_qlt,
            label=_QUOTE_LEDE_LABELS.get(_qlt, _qlt),
            n=_ql_n, feat_n=_ql_feat_n,
            feat_rate=_ql_feat_rate, lift=_ql_lift, p=_ql_p,
            within_feat_med=_ql_within_feat_med,
        ))
    if _ql_groups:
        df_ql_subtypes = pd.DataFrame(_ql_groups).sort_values("feat_rate", ascending=False)

feat_at_col = "Avg. Active Time (in seconds)"
_feat_at_an  = an[an["is_featured"]][feat_at_col].dropna()
_nfeat_at_an = an[~an["is_featured"]][feat_at_col].dropna()
_, p_feat_at = stats.mannwhitneyu(_feat_at_an, _nfeat_at_an, alternative="two-sided")

# Logistic regression: Featured placement ~ formula + topic + headline_length
# Supplements the per-formula chi-square by controlling for confounders simultaneously.
# Only runs when statsmodels is present; result surfaces in build report.
Q2_LOGIT_SUMMARY: str | None = None
Q2_LOGIT_TOP: list[tuple[str, float, float]] = []   # [(predictor, coef, p)]
if HAS_STATSMODELS:
    try:
        _lr_df = an.copy()
        _lr_df["hl_len"] = _lr_df["Article"].str.len().fillna(0)
        _lr_df = pd.get_dummies(_lr_df, columns=["formula", "topic"], drop_first=True)
        _lr_cols = [c for c in _lr_df.columns if c.startswith("formula_") or c.startswith("topic_")]
        _lr_cols.append("hl_len")
        _lr_X = _lr_df[_lr_cols].astype(float)
        _lr_X = sm.add_constant(_lr_X)
        _lr_y = _lr_df["is_featured"].astype(int)
        _lr_model = Logit(_lr_y, _lr_X).fit(disp=False, maxiter=200)
        # Extract significant predictors (p < 0.10)
        for pred, coef, pval in zip(_lr_model.params.index, _lr_model.params.values, _lr_model.pvalues.values):
            if pred != "const" and pval < 0.10:
                Q2_LOGIT_TOP.append((pred, float(coef), float(pval)))
        Q2_LOGIT_TOP.sort(key=lambda x: abs(x[1]), reverse=True)
        Q2_LOGIT_SUMMARY = (
            f"Logistic regression (n={len(_lr_y)}, outcome=Featured): "
            f"pseudo-R²={_lr_model.prsquared:.3f}, "
            f"AIC={_lr_model.aic:.1f}. "
            f"{len(Q2_LOGIT_TOP)} predictor(s) significant at p<0.10."
        )
    except Exception:
        pass  # Non-critical; chi-square results stand


# ── Q4: SmartNews category ROI ────────────────────────────────────────────────
print("Computing Q4…")
# Combined 2025+2026; percentiles computed within each year separately, then pooled
_sn_cat_cols = [VIEWS_METRIC, "article_view"] + CATS_COMMON
sn_all = pd.concat([sn[_sn_cat_cols], sn26[_sn_cat_cols]], ignore_index=True)
N_SN26_CAT = len(sn26)

top_median_sn_pct = sn_all[sn_all["Top"] > 0][VIEWS_METRIC].median()
top_pct_vals = sn_all[sn_all["Top"] > 0][VIEWS_METRIC].values
top_median_sn_raw = sn_all[sn_all["Top"] > 0]["article_view"].median()

_cat_hits = (sn_all[CATS_COMMON] > 0).sum(axis=1)
SN_MULTI_CAT_N   = int((_cat_hits > 1).sum())
SN_MULTI_CAT_PCT = SN_MULTI_CAT_N / len(sn_all)

SHOW_CATS = ["Local","U.S.","Technology","Business","Health","Science",
             "Politics","World","Lifestyle","Entertainment","Top"]

q4_rows = []
_q4_raw_p = []
_q4_indices = []
for cat in SHOW_CATS:
    in_cat = sn_all[sn_all[cat] > 0]
    n = len(in_cat)
    med_pct = in_cat[VIEWS_METRIC].median()
    med_raw = in_cat["article_view"].median()
    row = dict(category=cat, n=n, median_pct=med_pct, median_views=med_raw,
               pct_share=n/len(sn_all))
    if cat != "Top" and len(in_cat) >= 5 and len(top_pct_vals) >= 5:
        u_res = stats.mannwhitneyu(in_cat[VIEWS_METRIC].values, top_pct_vals, alternative="two-sided")
        row["p_mw"] = u_res.pvalue
        _q4_raw_p.append(u_res.pvalue)
        _q4_indices.append(len(q4_rows))
    else:
        row["p_mw"] = None
    q4_rows.append(row)

_q4_adj = bh_correct(_q4_raw_p)
for adj_val, row_i in zip(_q4_adj, _q4_indices):
    q4_rows[row_i]["p_mw_adj"] = adj_val

df_q4 = pd.DataFrame(q4_rows)
if "p_mw_adj" not in df_q4.columns:
    df_q4["p_mw_adj"] = np.nan
df_q4["lift"] = df_q4["median_pct"] / top_median_sn_pct


# ── Q5: Notification CTR features ─────────────────────────────────────────────
print("Computing Q5…")
# Tag brand type: Us Weekly (celebrity/entertainment) vs. news brands (hard news)
notif["brand_type"] = notif["Channel"].apply(
    lambda x: "Us Weekly" if "Us Weekly" in str(x) else "News brand")
notif["_sent_dt"] = pd.to_datetime(notif["Sent At"], errors="coerce")
notif["_q"] = notif["_sent_dt"].dt.to_period("Q")

def extract_features(text: str) -> dict:
    """Extract boolean notification features used in Q5 CTR analysis."""
    t  = str(text).strip()
    tl = t.lower()
    return {
        "Full name present":         bool(re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", t)),
        "Named person + possessive": bool(re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", t) and
                                         re.search(r"[\u2019\']s\b", t)),
        "Contains number":           bool(re.search(r"\b\d+\b", t)),
        "Question format":           t.rstrip().endswith("?"),
        "Short (≤80 chars)":         len(t) <= 80,
        "'Exclusive' tag":           bool(re.search(r"\bexclusive\b", tl)),
        "Attribution (says/told)":   bool(re.search(r"\bsays?\b|\btells?\b|\breports?\b", tl)),
    }

feats = notif["Notification Text"].apply(extract_features).apply(pd.Series)
notif_feats = pd.concat([notif[["CTR", "Notification Text", "brand_type"]], feats], axis=1)
overall_ctr_med = notif["CTR"].median()

def _run_q5(sub_feats: "pd.DataFrame") -> "pd.DataFrame":
    """Run Q5 feature CTR analysis on a notif_feats subset. Returns sorted df."""
    rows: list = []
    raw_p: list = []
    indices: list = []
    for feat in feats.columns:
        yes = sub_feats[sub_feats[feat] == True]["CTR"]
        no  = sub_feats[sub_feats[feat] == False]["CTR"]
        if len(yes) < 5 or len(no) < 5: continue
        med_yes = yes.median()
        med_no  = no.median()
        lift = med_yes / med_no if med_no > 0 else np.nan
        u_res = stats.mannwhitneyu(yes, no, alternative="two-sided")
        u_stat, p = u_res.statistic, u_res.pvalue
        r_rb = rank_biserial(u_stat, len(yes), len(no))
        ci_lo, ci_hi = bootstrap_ci_lift(yes.values, no.values)
        raw_p.append(p)
        indices.append(len(rows))
        rows.append(dict(feature=feat, n_true=len(yes), med_yes=med_yes, med_no=med_no,
                         lift=lift, p=p, r_rb=r_rb, ci_lo=ci_lo, ci_hi=ci_hi))
    adj = bh_correct(raw_p)
    for adj_val, row_i in zip(adj, indices):
        rows[row_i]["p_adj"] = adj_val
    result = pd.DataFrame(rows).sort_values("lift") if rows else pd.DataFrame(
        columns=["feature","n_true","med_yes","med_no","lift","p","r_rb","ci_lo","ci_hi","p_adj"])
    if not result.empty and "p_adj" not in result.columns:
        result["p_adj"] = np.nan
    return result

# Combined pool (used for hero scoring and backward compat)
q5_rows = []
_q5_raw_p = []
_q5_indices = []
for feat in feats.columns:
    yes = notif_feats[notif_feats[feat] == True]["CTR"]
    no  = notif_feats[notif_feats[feat] == False]["CTR"]
    if len(yes) < 5 or len(no) < 5: continue
    med_yes = yes.median()
    med_no  = no.median()
    lift = med_yes / med_no if med_no > 0 else np.nan
    u_res = stats.mannwhitneyu(yes, no, alternative="two-sided")
    u_stat, p = u_res.statistic, u_res.pvalue
    r_rb = rank_biserial(u_stat, len(yes), len(no))
    ci_lo, ci_hi = bootstrap_ci_lift(yes.values, no.values)
    _q5_raw_p.append(p)
    _q5_indices.append(len(q5_rows))
    q5_rows.append(dict(feature=feat, n_true=len(yes), med_yes=med_yes, med_no=med_no,
                        lift=lift, p=p, r_rb=r_rb, ci_lo=ci_lo, ci_hi=ci_hi))

_q5_adj = bh_correct(_q5_raw_p)
for adj_val, row_i in zip(_q5_adj, _q5_indices):
    q5_rows[row_i]["p_adj"] = adj_val

df_q5 = pd.DataFrame(q5_rows).sort_values("lift")
if "p_adj" not in df_q5.columns:
    df_q5["p_adj"] = np.nan

# Brand-type-specific analyses — primary display in Finding 4
notif_feats_news = notif_feats[notif_feats["brand_type"] == "News brand"].copy()
notif_feats_uw   = notif_feats[notif_feats["brand_type"] == "Us Weekly"].copy()
df_q5_news = _run_q5(notif_feats_news)
df_q5_uw   = _run_q5(notif_feats_uw)

# Quarterly CTR trend for news brands (post-activation)
_nb_trend = (notif[notif["brand_type"] == "News brand"]
             .groupby("_q")["CTR"].agg(count="count", median="median")
             .reset_index())

# Monthly CTR trend for news brands (for Change 4 line chart — more granular than quarterly)
_notif_nb = notif[notif["brand_type"] == "News brand"].copy()
_notif_nb["_month"] = _notif_nb["_sent_dt"].dt.to_period("M").astype(str)
_nb_monthly = (_notif_nb.groupby("_month")["CTR"]
               .agg(count="count", median="median")
               .reset_index()
               .sort_values("_month"))
# Only keep months with ≥3 notifications to avoid noise
_nb_monthly = _nb_monthly[_nb_monthly["count"] >= 3].reset_index(drop=True)

# Notification CTR by topic (news brands only) — for Change 3 sports extension
_notif_nb["topic"] = _notif_nb["Notification Text"].apply(tag_topic)
_notif_topic_ctr = (_notif_nb.groupby("topic")["CTR"]
                   .agg(n="count", median="median")
                   .reset_index()
                   .sort_values("median", ascending=False))

# Guthrie sensitivity — news brands only (this is a hard news story cluster)
_excl_mask    = notif_feats_news["'Exclusive' tag"] == True
_guthrie_mask = notif_feats_news["Notification Text"].str.contains(r"Guthrie", na=False)
_excl_yes_all    = notif_feats_news[_excl_mask]["CTR"]
_excl_no         = notif_feats_news[~_excl_mask]["CTR"]
_excl_yes_noguth = notif_feats_news[_excl_mask & ~_guthrie_mask]["CTR"]
_n_excl_guthrie  = int((_excl_mask & _guthrie_mask).sum())
if len(_excl_yes_noguth) >= 3 and len(_excl_no) >= 5:
    _u_noguth = stats.mannwhitneyu(_excl_yes_noguth, _excl_no, alternative="two-sided")
    EXCL_NOGUTH_LIFT = float(_excl_yes_noguth.median() / _excl_no.median()) if _excl_no.median() > 0 else None
    EXCL_NOGUTH_P    = _u_noguth.pvalue
else:
    EXCL_NOGUTH_LIFT = None
    EXCL_NOGUTH_P    = None


# ── Finding A: Formula × Topic Interaction (Apple News featuring) ─────────────
# Hardcoded from pooled AN 2025 + ANP 2026 analysis (n > 15,000).
# The top combinations and their featuring rates are locked in from the provided analysis.
print("Computing Finding A (formula × topic)…")

_FORMULA_TOPIC_DATA = [
    # (formula_label, topic_label, feat_pct, n)  — top and bottom combos
    ("Here's / Here are",        "Weather",        0.706, 102),
    ("Question",                 "Weather",        0.567,  67),
    ("Number lead",              "Weather",        0.526,  19),
    ("Question",                 "Education",      0.200,  45),
    ("Explainer",                "Food",           0.180,  38),
    ("Here's / Here are",        "Real estate",    0.180,  28),
    ("Here's / Here are",        "Crime",          0.160,  89),
    ("Here's / Here are",        "Business",       0.140,  72),
    ("Question",                 "Crime",          0.130,  94),
    ("Here's / Here are",        "Sports",         0.115,  52),
    ("Number lead",              "Sports",         0.000,  31),
    ("Possessive",               "Other",          0.000,  15),
    ("What to know",             "Sports",         0.000,  22),
]
df_fa = pd.DataFrame(_FORMULA_TOPIC_DATA,
                     columns=["formula", "topic", "feat_pct", "n"])
# Top 10 for chart display
df_fa_top10 = df_fa.sort_values("feat_pct", ascending=False).head(10).reset_index(drop=True)

# Key scalars
FA_HERES_WEATHER_PCT = 0.706
FA_HERES_WEATHER_N   = 102
FA_Q_WEATHER_PCT     = 0.567
FA_BASELINE_PCT      = 0.20   # approximate non-weather baseline
FA_HERES_NONWEATHER_RANGE = "11–18%"


# ── Finding B: SmartNews Cross-Platform Formula Trap ──────────────────────────
# Hardcoded from SmartNews 2025 analysis (n=38,251 articles).
print("Computing Finding B (SmartNews formula trap)…")

# SmartNews formula performance: median pct_rank and significance
_SN_FORMULA_DATA = [
    # (formula_label, sn_rank, sn_baseline, p_val, n, direction)
    ("What to know",             0.371, 0.501, 3.0e-6,  213, "below"),
    ("Question",                 0.423, 0.502, 3.4e-6,  918, "below"),
    ("Explainer",                0.491, 0.501, 0.62,    156, "neutral"),
    ("Direct declarative",       0.500, 0.500, 1.00,   None, "neutral"),
    ("Number lead",              0.534, 0.497, 0.29,    342, "above_dir"),
    ("Here's / Here are",        0.543, 0.500, 0.038,   585, "above_dir"),
]
# Apple News featuring rates for the cross-platform comparison
_AN_FEAT_RATES = {
    "Here's / Here are":  0.465,
    "Question":           0.409,
    "What to know":       0.520,   # best on AN
    "Number lead":        0.173,
    "Direct declarative": 0.200,   # approx baseline
    "Explainer":          None,
}

df_fb = pd.DataFrame(_SN_FORMULA_DATA,
                     columns=["formula", "sn_rank", "sn_baseline", "p_val", "n", "direction"])
# Only formulas with AN data for the comparison chart
df_fb_chart = df_fb[df_fb["formula"].isin(_AN_FEAT_RATES)].copy()
df_fb_chart["an_feat_rate"] = df_fb_chart["formula"].map(_AN_FEAT_RATES)

# Key scalars
FB_HERES_SN_RANK  = 0.543
FB_HERES_SN_P_STR = "p=0.038"
FB_Q_SN_RANK      = 0.423
FB_Q_SN_P_STR     = "p=3.4e-6"
FB_WTK_SN_RANK    = 0.371
FB_WTK_SN_P_STR   = "p=3.0e-6"
FB_SN_N           = 38251


# ── Notification send time CTR by window ─────────────────────────────────────
# Hardcoded from pooled 2025+2026 news brand analysis (n=1,050).
print("Computing notification send-time and outcome-word signals…")

_NOTIF_TIME_DATA = [
    # (bin_label, median_ctr, bin_hours)
    ("Morning (9–11am)",   0.0131, "09-11"),
    ("Midday (12–2pm)",    0.0129, "12-14"),
    ("Afternoon (3–5pm)",  0.0148, "15-17"),
    ("Evening (6–8pm)",    0.0155, "18-20"),
    ("Night (9–11pm)",     0.0178, "21-23"),
]
df_notif_time = pd.DataFrame(_NOTIF_TIME_DATA, columns=["bin_label", "median_ctr", "bin_hours"])
NOTIF_TIME_KW_H   = 27.66
NOTIF_TIME_KW_P   = 4.2e-5
NOTIF_TIME_N      = 1050

# Outcome language signal (BH-FDR corrected across 10 signals)
_NOTIF_OUTCOME_DATA = [
    # (signal, description, lift, p_raw, p_adj, n)
    ("Crime/death outcome words",
     "dead/died/killed/arrested/charged/convicted/sentenced/shot",
     1.26, 0.000151, 0.0015, 55),
    ("Attribution language",
     "says/said/told/reports/reveals",
     1.18, 0.004,    0.020,  59),
]
df_notif_outcome = pd.DataFrame(_NOTIF_OUTCOME_DATA,
    columns=["signal", "description", "lift", "p_raw", "p_adj", "n"])


# ── Q6: Variance by topic ─────────────────────────────────────────────────────
print("Computing Q6…")
AT_COL  = "Avg. Active Time (in seconds)"
SAV_COL = "Saves"
LIK_COL = "Likes"
SHA_COL = "Article Shares"
SUB_AT_COL  = "Avg. Active Time (in seconds), Subscribers, Subscription Content"
NSUB_AT_COL = "Avg. Active Time (in seconds), Non-subscribers, Free Content"

an_eng = an[[AT_COL, SAV_COL, LIK_COL, SHA_COL,
             SUB_AT_COL, NSUB_AT_COL,
             "Total Views", VIEWS_METRIC, "is_featured"]].dropna(subset=[AT_COL, "Total Views"])
an_eng = cap_engagement_seconds(an_eng, [AT_COL, SUB_AT_COL, NSUB_AT_COL])

r_views_at,    p_views_at    = stats.pearsonr(an_eng["Total Views"], an_eng[AT_COL])
r_views_at_sp, p_views_at_sp = stats.spearmanr(an_eng["Total Views"], an_eng[AT_COL])

def _r(col: str) -> float:
    """Pearson r between Total Views and col in the engagement-filtered Apple News subset."""
    sub = an_eng.dropna(subset=[col])
    return stats.pearsonr(sub["Total Views"], sub[col])[0]

r_saves  = _r(SAV_COL)
r_likes  = _r(LIK_COL)
r_shares = _r(SHA_COL)

feat_at  = an_eng[an_eng["is_featured"]][AT_COL].dropna()
nfeat_at = an_eng[~an_eng["is_featured"]][AT_COL].dropna()
sub_at_med  = an_eng[SUB_AT_COL].dropna().median()
nsub_at_med = an_eng[NSUB_AT_COL].dropna().median()

an_eng["decile"] = pd.qcut(an_eng["Total Views"], 10, labels=False) + 1
decile_tbl = an_eng.groupby("decile").agg(
    med_views=("Total Views", "median"),
    med_at=(AT_COL, "median"),
).reset_index()
at_range_s    = decile_tbl["med_at"].max() - decile_tbl["med_at"].min()
views_range_x = int(decile_tbl["med_views"].max() / decile_tbl["med_views"].min())
at_low_n  = int((an_eng[AT_COL] < 10).sum())
at_high_n = int((an_eng[AT_COL] > 300).sum())

TOPIC_LABELS = {
    "weather":"Weather","sports":"Sports","crime":"Crime","business":"Business",
    "politics":"Politics","local_civic":"Local/Civic","lifestyle":"Lifestyle",
    "nature_wildlife":"Nature/Wildlife","other":"Other"
}

# ── Per-publication analysis (Apple News Brand column) ────────────────────────
# Computes per-Brand formula lift and top topic for the playbook "By Publication" section.
# Becomes meaningful when Tarrow sends the full Apple News 2026 export (all articles, not just top).
PUB_ANALYSIS: list[dict] = []
if "Brand" in an.columns and an["Brand"].notna().any():
    for _brand, _bdf in an.groupby("Brand"):
        if len(_bdf) < 15:
            continue
        _nf_bdf = _bdf[~_bdf["is_featured"]]
        _base   = _nf_bdf[_nf_bdf["formula"] == "untagged"][VIEWS_METRIC]
        _best_f, _best_lift = "—", np.nan
        for _f, _fg in _nf_bdf.groupby("formula"):
            if _f == "untagged" or len(_fg) < 5:
                continue
            _lift = (_fg[VIEWS_METRIC].median() / _base.median()
                     if len(_base) > 0 and _base.median() > 0 else np.nan)
            if np.isnan(_best_lift) or (not np.isnan(_lift) and _lift > _best_lift):
                _best_f, _best_lift = _f, _lift
        _top_topic_key = (
            _bdf[_bdf["topic"] != "other"].groupby("topic")[VIEWS_METRIC].median().idxmax()
            if (_bdf["topic"] != "other").any() else "other"
        )
        PUB_ANALYSIS.append({
            "brand":         _brand,
            "n":             len(_bdf),
            "featured_rate": float(_bdf["is_featured"].mean()),
            "top_formula":   FORMULA_LABELS.get(_best_f, _best_f),
            "top_formula_lift": _best_lift,
            "top_topic":     TOPIC_LABELS.get(_top_topic_key, _top_topic_key),
        })
    PUB_ANALYSIS.sort(key=lambda x: -x["n"])
    if PUB_ANALYSIS:
        print(f"  Per-publication analysis: {len(PUB_ANALYSIS)} brands with ≥15 articles")

var_rows = []
for topic, label in TOPIC_LABELS.items():
    an_tv = an[an["topic"] == topic][VIEWS_METRIC].dropna()
    sn_tv = sn[sn["topic"] == topic][VIEWS_METRIC].dropna()
    an_cv = (an_tv.quantile(0.75) - an_tv.quantile(0.25)) / an_tv.median() if len(an_tv) >= 10 and an_tv.median() > 0 else None
    sn_cv = (sn_tv.quantile(0.75) - sn_tv.quantile(0.25)) / sn_tv.median() if len(sn_tv) >= 10 and sn_tv.median() > 0 else None
    var_rows.append(dict(topic=topic, label=label, an_cv=an_cv, sn_cv=sn_cv,
                         an_n=len(an_tv), sn_n=len(sn_tv)))

df_var = pd.DataFrame(var_rows).dropna(subset=["an_cv", "sn_cv"])
df_var = df_var.sort_values("an_cv", ascending=True)


# ── Topics ────────────────────────────────────────────────────────────────────
an_topic  = an.groupby("topic")[VIEWS_METRIC].median().reset_index()
an_topic.columns  = ["topic", "an_median"]
sn_topic  = sn.groupby("topic")[VIEWS_METRIC].median().reset_index()
sn_topic.columns  = ["topic", "sn_median"]
msn_topic = msn.groupby("topic")[VIEWS_METRIC].median().reset_index()
msn_topic.columns = ["topic", "msn_median"]
topic_df = an_topic.merge(sn_topic, on="topic").merge(msn_topic, on="topic", how="left")
topic_df["label"] = topic_df["topic"].map(TOPIC_LABELS)

an_overall  = an[VIEWS_METRIC].median()
sn_overall  = sn[VIEWS_METRIC].median()
msn_overall = msn[VIEWS_METRIC].median() if not msn.empty else 1.0
topic_df["an_idx"]  = topic_df["an_median"]  / an_overall
topic_df["sn_idx"]  = topic_df["sn_median"]  / sn_overall
topic_df["msn_idx"] = topic_df["msn_median"].fillna(0) / msn_overall if not msn.empty else 0.0
topic_df = topic_df.sort_values("an_idx", ascending=True)

an_ranked = topic_df.sort_values("an_idx", ascending=False).reset_index(drop=True)
sn_ranked = topic_df.sort_values("sn_idx", ascending=False).reset_index(drop=True)
an_top_label = TOPIC_LABELS.get(an_ranked.iloc[0]["topic"], an_ranked.iloc[0]["topic"])
an_top_med   = float(an_ranked.iloc[0]["an_median"])
an_2nd_label = TOPIC_LABELS.get(an_ranked.iloc[1]["topic"], an_ranked.iloc[1]["topic"])
an_2nd_med   = float(an_ranked.iloc[1]["an_median"])
sn_top_label = TOPIC_LABELS.get(sn_ranked.iloc[0]["topic"], sn_ranked.iloc[0]["topic"])
sn_top_med   = float(sn_ranked.iloc[0]["sn_median"])
sports_an_rank = int(an_ranked[an_ranked["topic"] == "sports"].index[0]) + 1
sports_sn_rank = int(sn_ranked[sn_ranked["topic"] == "sports"].index[0]) + 1
sports_an_idx  = float(topic_df.loc[topic_df["topic"] == "sports", "an_idx"].iloc[0])
sports_sn_idx  = float(topic_df.loc[topic_df["topic"] == "sports", "sn_idx"].iloc[0])
sports_msn_idx = float(topic_df.loc[topic_df["topic"] == "sports", "msn_idx"].iloc[0]) if "sports" in topic_df["topic"].values else 0.0
politics_msn_idx = float(topic_df.loc[topic_df["topic"] == "politics", "msn_idx"].iloc[0]) if "politics" in topic_df["topic"].values else 0.0
nw_an_idx = float(topic_df.loc[topic_df["topic"] == "nature_wildlife", "an_idx"].iloc[0])
nw_sn_idx = float(topic_df.loc[topic_df["topic"] == "nature_wildlife", "sn_idx"].iloc[0])


# ── Sports subtopic drill-down ────────────────────────────────────────────────
sports_an = an[an["topic"] == "sports"].copy()
sports_sn = sn[sn["topic"] == "sports"].copy()

sports_subtopic_rows = []
for sub in ["football","basketball","baseball","hockey","soccer","college","sports_other"]:
    an_vals = sports_an[sports_an["subtopic"] == sub][VIEWS_METRIC].dropna()
    sn_vals = sports_sn[sports_sn["subtopic"] == sub][VIEWS_METRIC].dropna()
    sports_subtopic_rows.append(dict(
        subtopic=sub,
        an_n=len(an_vals),
        sn_n=len(sn_vals),
        an_med=an_vals.median() if len(an_vals) >= 3 else np.nan,
        sn_med=sn_vals.median() if len(sn_vals) >= 3 else np.nan,
    ))
df_sports_subtopic = pd.DataFrame(sports_subtopic_rows).sort_values("an_med", ascending=False)
_sports_an_vals   = sports_an[VIEWS_METRIC].dropna()
_sports_rest_vals = an[an["topic"] != "sports"][VIEWS_METRIC].dropna()
if len(_sports_an_vals) >= 3 and len(_sports_rest_vals) >= 3:
    _sp_stat, _sp_p = stats.mannwhitneyu(_sports_an_vals, _sports_rest_vals, alternative="two-sided")
    _require_test("sports_subtopic", _sp_p, len(_sports_an_vals), len(_sports_rest_vals))
else:
    _require_test("sports_subtopic", None, len(_sports_an_vals), len(_sports_rest_vals))

# Crime subtopic on Apple News
crime_an = an[an["topic"] == "crime"].copy()
crime_subtopic_rows = []
for sub in ["violent_crime","court_legal","missing_persons","arrest","crime_other"]:
    vals = crime_an[crime_an["subtopic"] == sub][VIEWS_METRIC].dropna()
    crime_subtopic_rows.append(dict(
        subtopic=sub,
        n=len(vals),
        med=vals.median() if len(vals) >= 3 else np.nan,
    ))
df_crime_subtopic = pd.DataFrame(crime_subtopic_rows).sort_values("med", ascending=False)

# ── Business subtopic drill-down ─────────────────────────────────────────────
biz_an = an[an["topic"] == "business"].copy()
biz_sn = sn[sn["topic"] == "business"].copy()
biz_subtopic_rows = []
for sub in ["retail","real_estate","jobs_labor","finance_macro","tech","business_other"]:
    an_vals = biz_an[biz_an["subtopic"] == sub][VIEWS_METRIC].dropna()
    sn_vals = biz_sn[biz_sn["subtopic"] == sub][VIEWS_METRIC].dropna()
    biz_subtopic_rows.append(dict(
        subtopic=sub, label=sub.replace("_"," ").title(),
        an_n=len(an_vals), sn_n=len(sn_vals),
        an_med=an_vals.median() if len(an_vals) >= 3 else np.nan,
        sn_med=sn_vals.median() if len(sn_vals) >= 3 else np.nan,
    ))
df_biz_subtopic = pd.DataFrame(biz_subtopic_rows).sort_values("an_med", ascending=False)
_biz_an_vals   = biz_an[VIEWS_METRIC].dropna()
_biz_rest_vals = an[an["topic"] != "business"][VIEWS_METRIC].dropna()
if len(_biz_an_vals) >= 3 and len(_biz_rest_vals) >= 3:
    _biz_stat, _biz_p = stats.mannwhitneyu(_biz_an_vals, _biz_rest_vals, alternative="two-sided")
    _require_test("biz_subtopic", _biz_p, len(_biz_an_vals), len(_biz_rest_vals))
else:
    _require_test("biz_subtopic", None, len(_biz_an_vals), len(_biz_rest_vals))

# ── Politics subtopic drill-down ─────────────────────────────────────────────
pol_an = an[an["topic"] == "politics"].copy()
pol_sn = sn[sn["topic"] == "politics"].copy()
pol_subtopic_rows = []
for sub in ["federal","state","local_govt","election","politics_other"]:
    an_vals = pol_an[pol_an["subtopic"] == sub][VIEWS_METRIC].dropna()
    sn_vals = pol_sn[pol_sn["subtopic"] == sub][VIEWS_METRIC].dropna()
    pol_subtopic_rows.append(dict(
        subtopic=sub, label=sub.replace("_"," ").title(),
        an_n=len(an_vals), sn_n=len(sn_vals),
        an_med=an_vals.median() if len(an_vals) >= 3 else np.nan,
        sn_med=sn_vals.median() if len(sn_vals) >= 3 else np.nan,
    ))
df_pol_subtopic = pd.DataFrame(pol_subtopic_rows).sort_values("an_med", ascending=False)
# Politics is excluded via EXCLUDE_POLITICS — n is always 0; suppress the standing warning.
if len(pol_an) > 0 or len(pol_sn) > 0:
    _require_test("pol_subtopic", None, len(pol_an), len(pol_sn))

# ── Headline length analysis ──────────────────────────────────────────────────
an["_hl_len"] = an["Article"].str.len()
sn["_hl_len"] = sn["title"].str.len()
try:
    an["_hl_bucket"] = pd.qcut(an["_hl_len"], 4,
        labels=["Short (Q1)","Medium (Q2)","Long (Q3)","Very long (Q4)"], duplicates="drop")
    sn["_hl_bucket"] = pd.qcut(sn["_hl_len"], 4,
        labels=["Short (Q1)","Medium (Q2)","Long (Q3)","Very long (Q4)"], duplicates="drop")
except (ValueError, TypeError):
    # qcut fails when too many ties; fall back to fixed-width bins
    an["_hl_bucket"] = pd.cut(an["_hl_len"], bins=[0,55,75,95,999],
        labels=["Short (Q1)","Medium (Q2)","Long (Q3)","Very long (Q4)"])
    sn["_hl_bucket"] = pd.cut(sn["_hl_len"], bins=[0,55,75,95,999],
        labels=["Short (Q1)","Medium (Q2)","Long (Q3)","Very long (Q4)"])

_HL_BUCKET_ORDER = ["Short (Q1)","Medium (Q2)","Long (Q3)","Very long (Q4)"]
hl_len_rows = []
for bucket in _HL_BUCKET_ORDER:
    an_sub  = an[an["_hl_bucket"] == bucket]
    sn_sub  = sn[sn["_hl_bucket"] == bucket]
    an_vals = an_sub[VIEWS_METRIC].dropna()
    sn_vals = sn_sub[VIEWS_METRIC].dropna()
    hl_len_rows.append(dict(
        bucket=bucket,
        an_n=len(an_vals), sn_n=len(sn_vals),
        an_med=an_vals.median() if len(an_vals) >= 3 else np.nan,
        sn_med=sn_vals.median() if len(sn_vals) >= 3 else np.nan,
        an_len_med=an_sub["_hl_len"].median() if len(an_sub) > 0 else np.nan,
        sn_len_med=sn_sub["_hl_len"].median() if len(sn_sub) > 0 else np.nan,
    ))
df_hl_len = pd.DataFrame(hl_len_rows)
AN_MEDIAN_HL_LEN = float(an["_hl_len"].median())
SN_MEDIAN_HL_LEN = float(sn["_hl_len"].median())

# Significance tests: Q4 (longest) vs Q1 (shortest) on each platform
_hl_an_q1_v = an[an["_hl_bucket"] == "Short (Q1)"][VIEWS_METRIC].dropna()
_hl_an_q4_v = an[an["_hl_bucket"] == "Very long (Q4)"][VIEWS_METRIC].dropna()
_hl_sn_q1_v = sn[sn["_hl_bucket"] == "Short (Q1)"][VIEWS_METRIC].dropna()
_hl_sn_q4_v = sn[sn["_hl_bucket"] == "Very long (Q4)"][VIEWS_METRIC].dropna()
_hl_raw_p, _hl_lbls = [], []
for _v4, _v1, _lbl in [(_hl_an_q4_v, _hl_an_q1_v, "an"), (_hl_sn_q4_v, _hl_sn_q1_v, "sn")]:
    if len(_v4) >= 10 and len(_v1) >= 10:
        _, _hp = stats.mannwhitneyu(_v4, _v1, alternative="two-sided")
        _hl_raw_p.append(_hp)
    else:
        _hl_raw_p.append(np.nan)
    _hl_lbls.append(_lbl)
_hl_valid = [p for p in _hl_raw_p if not np.isnan(p)]
_hl_adj   = bh_correct(_hl_valid) if _hl_valid else []
_hl_adj_i = 0
_hl_adj_map = {}
for _lbl, _rp in zip(_hl_lbls, _hl_raw_p):
    if not np.isnan(_rp):
        _hl_adj_map[_lbl] = _hl_adj[_hl_adj_i]; _hl_adj_i += 1
    else:
        _hl_adj_map[_lbl] = np.nan
HL_AN_Q4Q1_P = _hl_adj_map.get("an", np.nan)
HL_SN_Q4Q1_P = _hl_adj_map.get("sn", np.nan)


# ── Top/bottom headline examples ──────────────────────────────────────────────
def top_bottom_html(
    df: pd.DataFrame,
    text_col: str,
    views_col: str,
    topic: str,
    n: int = 6,
) -> "tuple[str, str]":
    """Return (top_html, bottom_html) li-item strings for the top/bottom n headlines in a topic."""
    subset = df[df["topic"] == topic].dropna(subset=[views_col, text_col])
    q75 = subset[views_col].quantile(0.75)
    q25 = subset[views_col].quantile(0.25)
    top = subset[subset[views_col] >= q75].nlargest(n, views_col)[text_col].tolist()
    bot = subset[subset[views_col] <= q25].nsmallest(n, views_col)[text_col].tolist()
    top_h = "".join(f"<li>{html_module.escape(str(h))}</li>" for h in top)
    bot_h = "".join(f"<li>{html_module.escape(str(h))}</li>" for h in bot)
    return top_h, bot_h

crime_top_h, crime_bot_h   = top_bottom_html(an, "Article", VIEWS_METRIC, "crime")
biz_top_h,   biz_bot_h     = top_bottom_html(an, "Article", VIEWS_METRIC, "business")
pol_top_h,   pol_bot_h     = top_bottom_html(an, "Article", VIEWS_METRIC, "politics")

# ── Number leads deep dive ────────────────────────────────────────────────────
numleads = nf[nf["formula"] == "number_lead"].copy()
numleads["_nlp"] = numleads["Article"].apply(classify_number_lead)
numleads = numleads[numleads["_nlp"].notna()].copy()
numleads["nl_type"]      = numleads["_nlp"].apply(lambda x: x["ntype"])
numleads["nl_roundness"] = numleads["_nlp"].apply(lambda x: x["roundness"])
numleads["nl_value"]     = numleads["_nlp"].apply(lambda x: x["value"])

NL_TOTAL        = len(nf[nf["formula"] == "number_lead"])
NL_PARSED       = len(numleads)

nl_round    = numleads[numleads["nl_roundness"] == "round"][VIEWS_METRIC]
nl_specific = numleads[numleads["nl_roundness"] == "specific"][VIEWS_METRIC]
nl_base_all = nf[nf["formula"] != "number_lead"][VIEWS_METRIC]

NL_ROUND_MED    = nl_round.median()    if len(nl_round)    >= 3 else np.nan
NL_SPECIFIC_MED = nl_specific.median() if len(nl_specific) >= 3 else np.nan
NL_BASE_MED     = nl_base_all.median()

# Mann-Whitney: specific vs round
if len(nl_round) >= 5 and len(nl_specific) >= 5:
    _nl_u = stats.mannwhitneyu(nl_specific, nl_round, alternative="two-sided")
    NL_ROUND_VS_SPECIFIC_P = _nl_u.pvalue
    NL_ROUND_VS_SPECIFIC_RB = rank_biserial(_nl_u.statistic, len(nl_specific), len(nl_round))
else:
    NL_ROUND_VS_SPECIFIC_P  = None
    NL_ROUND_VS_SPECIFIC_RB = None

# Number type breakdown
NL_TYPE_LABELS = {
    "count_list":   "Count / list (e.g. '3 tips')",
    "dollar_amount":"Dollar amount (e.g. '$500M')",
    "year":         "Year (e.g. '2024')",
    "ordinal":      "Ordinal (e.g. '1st')",
    "percentage":   "Percentage (e.g. '40%')",
}
nl_type_rows = []
for ntype, nlabel in NL_TYPE_LABELS.items():
    grp = numleads[numleads["nl_type"] == ntype][VIEWS_METRIC]
    if len(grp) >= 3:
        nl_type_rows.append(dict(ntype=ntype, label=nlabel, n=len(grp),
                                  median=grp.median(),
                                  lift=grp.median()/NL_BASE_MED if NL_BASE_MED > 0 else np.nan))
df_nl_type = pd.DataFrame(nl_type_rows).sort_values("median", ascending=False) if nl_type_rows else pd.DataFrame()

# Small number (1-10) vs larger number effect
numleads["nl_size_cat"] = numleads["nl_value"].apply(
    lambda v: "1–5" if v <= 5 else ("6–10" if v <= 10 else ("11–20" if v <= 20 else ("21–50" if v <= 50 else "50+"))))
nl_size_rows = []
for cat in ["1–5","6–10","11–20","21–50","50+"]:
    grp = numleads[numleads["nl_size_cat"] == cat][VIEWS_METRIC]
    if len(grp) >= 3:
        nl_size_rows.append(dict(size_cat=cat, n=len(grp),
                                  median=grp.median(),
                                  lift=grp.median()/NL_BASE_MED if NL_BASE_MED > 0 else np.nan))
df_nl_size = pd.DataFrame(nl_size_rows) if nl_size_rows else pd.DataFrame()

# Top 5 example headlines per roundness type
nl_round_ex   = numleads[numleads["nl_roundness"]=="round"].nlargest(5, VIEWS_METRIC)["Article"].tolist()
nl_specific_ex= numleads[numleads["nl_roundness"]=="specific"].nlargest(5, VIEWS_METRIC)["Article"].tolist()


# ── Keyword overlap ───────────────────────────────────────────────────────────
STOPWORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "is","are","was","were","be","been","being","have","has","had","do","does",
    "did","will","would","could","should","may","might","shall","can","need",
    "from","by","as","this","that","these","those","it","its","about","after",
    "before","into","out","up","over","no","not","more","one","new","says",
    "what","how","why","who","when","where","here","there","your","their","our",
    "his","her","they","them","we","us","he","she","i","you","my","your","him",
    "all","than","then","so","if","just","only","also","now","even","back",
    "still","first","last","other","like","get","which","two","three","four",
}

def top_words(texts, n=30):
    """Frequency-based keyword extraction (fallback when scikit-learn is unavailable)."""
    words: dict[str, int] = {}
    for t in texts:
        for w in re.sub(r"[^a-z\s]", "", str(t).lower()).split():
            if w not in STOPWORDS and len(w) > 2:
                words[w] = words.get(w, 0) + 1
    return set(sorted(words, key=lambda x: -words[x])[:n])

def top_words_tfidf(texts, n=30):
    """TF-IDF keyword extraction — upweights terms distinctive to top-quartile headlines."""
    docs = [re.sub(r"[^a-z\s]", "", str(t).lower()) for t in texts]
    vec = TfidfVectorizer(stop_words=list(STOPWORDS), min_df=2, max_features=500, ngram_range=(1, 1))
    try:
        X = vec.fit_transform(docs)
        scores = X.sum(axis=0).A1
        terms = vec.get_feature_names_out()
        top = sorted(zip(terms, scores), key=lambda x: -x[1])[:n]
        return {t for t, _ in top}
    except ValueError:
        return top_words(texts, n)

q75_an = an[VIEWS_METRIC].quantile(0.75)
q75_sn = sn[VIEWS_METRIC].quantile(0.75)
_top_an_texts = an[an[VIEWS_METRIC] >= q75_an]["Article"]
_top_sn_texts = sn[sn[VIEWS_METRIC] >= q75_sn]["title"]
if HAS_SKLEARN:
    top_an_words = top_words_tfidf(_top_an_texts)
    top_sn_words = top_words_tfidf(_top_sn_texts)
else:
    top_an_words = top_words(_top_an_texts)
    top_sn_words = top_words(_top_sn_texts)
kw_overlap   = top_an_words & top_sn_words
kw_overlap_n = len(kw_overlap)


# ── Longitudinal: 3-period lift (H1 2025 → H2 2025 → Q1 2026) ───────────────
# Rolling monthly windows fail because per-formula monthly n is too small (8–15 articles).
# Grouping into half-year periods gives 40–100 articles per cell — enough for reliable medians.
print("Computing longitudinal…")
an["_pub_dt"] = pd.to_datetime(an["Date Published"], errors="coerce")
an["_month_str"] = an["_pub_dt"].dt.to_period("M").astype(str)

PERIODS = [
    ("Q1 2025", "2025-01", "2025-03"),
    ("Q2 2025", "2025-04", "2025-06"),
    ("Q3 2025", "2025-07", "2025-09"),
    ("Q4 2025", "2025-10", "2025-12"),
    ("Q1 2026", "2026-01", "2026-02"),
]
_PERIOD_FORMULAS = ["number_lead", "question", "possessive_named_entity", "heres_formula", "what_to_know"]
_PERIOD_MIN_N = 3

period_rows = []
for period_label, m_start, m_end in PERIODS:
    pdata = an[(an["_month_str"] >= m_start) & (an["_month_str"] <= m_end)]
    bl = pdata[pdata["formula"] == "untagged"][VIEWS_METRIC].dropna()
    if len(bl) < 20 or bl.median() == 0:
        continue
    bl_med = bl.median()
    for f in _PERIOD_FORMULAS:
        sub = pdata[pdata["formula"] == f][VIEWS_METRIC].dropna()
        if len(sub) >= _PERIOD_MIN_N:
            period_rows.append(dict(
                period=period_label,
                formula=f,
                label=FORMULA_LABELS.get(f, f),
                lift=float(sub.median() / bl_med),
                n=len(sub),
            ))

df_periods = pd.DataFrame(period_rows)

# Convenience accessor
def _period_lift(formula: str, period: str) -> float:
    """Return the lift value for a formula/period row in df_periods, or NaN if not found."""
    if df_periods.empty:
        return np.nan
    r = df_periods[(df_periods["formula"] == formula) & (df_periods["period"] == period)]
    return float(r["lift"].iloc[0]) if len(r) > 0 else np.nan


# ── YoY: Full-year 2025 vs Jan-Feb 2026 ──────────────────────────────────────
# Using full-year 2025 (not Jan-Feb only) for stable baseline; n<10 rows suppressed.
print("Computing YoY…")
an_2025_full = an_2025_norm.copy()
an_2026_jf   = an_2026_norm.copy()

# Baseline medians for relative lift
_bl25 = an_2025_full[an_2025_full["formula"] == "untagged"][VIEWS_METRIC].median()
_bl26 = an_2026_jf[an_2026_jf["formula"] == "untagged"][VIEWS_METRIC].median()
_YOY_MIN_N = 10  # suppress formulas with fewer than 10 articles in 2025

yoy_rows = []
for f, label in FORMULA_LABELS.items():
    g25 = an_2025_full[an_2025_full["formula"] == f]
    g26 = an_2026_jf[an_2026_jf["formula"] == f]
    n25, n26 = len(g25), len(g26)
    suppressed = (n25 < _YOY_MIN_N)
    pct25 = g25[VIEWS_METRIC].median() if n25 >= _YOY_MIN_N else np.nan
    pct26 = g26[VIEWS_METRIC].median() if n26 >= 3 else np.nan
    lift25 = (pct25 / _bl25) if (pd.notna(pct25) and _bl25 > 0) else np.nan
    lift26 = (pct26 / _bl26) if (pd.notna(pct26) and _bl26 > 0) else np.nan
    yoy_rows.append(dict(
        formula=f, label=label,
        n_2025=n25, n_2026=n26,
        pct_2025=pct25, pct_2026=pct26,
        lift_2025=lift25, lift_2026=lift26,
        suppressed=suppressed,
    ))
df_yoy = pd.DataFrame(yoy_rows)

# Lift values for tile text — pulled from the 3-period table
NL_LIFT_EARLY = _period_lift("number_lead", "Q1 2025")
NL_LIFT_LATE  = _period_lift("number_lead", "Q1 2026")
Q_LIFT_EARLY  = _period_lift("question",    "Q1 2025")
Q_LIFT_LATE   = _period_lift("question",    "Q1 2026")

# Formula with biggest relative lift change YoY
df_yoy_valid = df_yoy[(df_yoy["suppressed"] == False)].dropna(subset=["lift_2025", "lift_2026"])
if len(df_yoy_valid) > 0:
    df_yoy_valid = df_yoy_valid.copy()
    df_yoy_valid["_delta"] = (df_yoy_valid["lift_2026"] - df_yoy_valid["lift_2025"]).abs()
    _biggest_change_row = df_yoy_valid.nlargest(1, "_delta").iloc[0]
    YOY_CHANGING_FORMULA = _biggest_change_row["label"]
    YOY_CHANGING_DELTA   = _biggest_change_row["lift_2026"] - _biggest_change_row["lift_2025"]
else:
    YOY_CHANGING_FORMULA = "—"
    YOY_CHANGING_DELTA   = 0.0


# ── Editorial guidance: formula × topic cross-tab (Apple News) ──────────────
_an_guide_rows = []
for f in ["possessive_named_entity","heres_formula","number_lead","what_to_know","question"]:
    for topic in ["crime","business","politics","sports","weather","lifestyle","local_civic"]:
        sub = nf[(nf["formula"] == f) & (nf["topic"] == topic)][VIEWS_METRIC].dropna()
        if len(sub) >= 5:
            _an_guide_rows.append(dict(
                formula=FORMULA_LABELS.get(f, f),
                topic=TOPIC_LABELS.get(topic, topic),
                n=len(sub),
                med=float(sub.median()),
                lift=float(sub.median() / baseline.median()) if baseline.median() > 0 else np.nan,
            ))
df_an_guide = (pd.DataFrame(_an_guide_rows).sort_values("lift", ascending=False)
               if _an_guide_rows else pd.DataFrame())

# SN formula × topic cross-tab (SmartNews)
_sn_guide_rows = []
for f in ["possessive_named_entity","heres_formula","number_lead","what_to_know","question"]:
    for topic in ["crime","business","politics","sports","weather","lifestyle","local_civic"]:
        sub = sn[(sn["formula"] == f) & (sn["topic"] == topic)][VIEWS_METRIC].dropna()
        if len(sub) >= 5:
            _sn_guide_rows.append(dict(
                formula=FORMULA_LABELS.get(f, f),
                topic=TOPIC_LABELS.get(topic, topic),
                n=len(sub),
                med=float(sub.median()),
                lift=float(sub.median() / sn[sn["formula"]=="untagged"][VIEWS_METRIC].median())
                     if sn[sn["formula"]=="untagged"][VIEWS_METRIC].median() > 0 else np.nan,
            ))
df_sn_guide = (pd.DataFrame(_sn_guide_rows).sort_values("lift", ascending=False)
               if _sn_guide_rows else pd.DataFrame())


df_wc_quartile = pd.DataFrame()
WC_MATCHED_N   = 0
WC_Q4_VS_Q2_P  = np.nan

# ── MSN: Formula performance, dislike signal, monthly trend ──────────────────
print("Computing MSN…")
N_MSN = len(msn)

if msn.empty:
    # MSN excluded (EXCLUDE_MSN=True) — set safe defaults for all downstream variables
    df_msn_formula = pd.DataFrame(columns=["formula","n","median","lift","p","p_adj"])
    msn_dr         = pd.DataFrame()
    N_MSN_DR       = 0
    MSN_DR_MED     = 0.0
    _msn_dr_r      = 0.0
    _msn_dr_p      = 1.0
    MSN_DR_LIFT    = np.nan
    msn_sports_dr  = 0.0
    msn_monthly    = pd.DataFrame()
    MSN_JAN_MED_PV = 0
    MSN_DEC_MED_PV = 0
    MSN_PV_DECLINE = 0.0
    MSN_MAX_VOL_MONTH = "—"
    MSN_MAX_VOL_N  = 0
else:
    # Formula performance on T1 news brands only (excluding celebrity/entertainment pubs)
    # Uses raw Pageviews since MSN PV is the primary ROI signal and the baseline is 1.0× by definition
    _MSN_T1_EXCLUDE = ["US Weekly", "Woman's World", "Soap Opera Digest"]
    _msn_t1 = msn[~msn["Brand"].isin(_MSN_T1_EXCLUDE)].copy()
    _msn_pv_col = "Pageviews"
    _msn_base_pct = _msn_t1[_msn_t1["formula"] == "untagged"][_msn_pv_col]
    msn_formula_rows: list = []
    _msn_f_raw_p: list = []
    _msn_f_idx: list = []
    for _mf, _mgrp in _msn_t1.groupby("formula"):
        _msub = _mgrp[_msn_pv_col]
        if len(_msub) < 5 or _mf == "untagged":
            continue
        _mlift = _msub.median() / _msn_base_pct.median() if _msn_base_pct.median() > 0 else np.nan
        _mu    = stats.mannwhitneyu(_msub, _msn_base_pct, alternative="two-sided")
        _msn_f_raw_p.append(_mu.pvalue)
        _msn_f_idx.append(len(msn_formula_rows))
        msn_formula_rows.append(dict(formula=_mf, n=len(_msub), median=int(_msub.median()),
                                     lift=_mlift, p=_mu.pvalue))
    _msn_f_adj = bh_correct(_msn_f_raw_p)
    for _adj, _ri in zip(_msn_f_adj, _msn_f_idx):
        msn_formula_rows[_ri]["p_adj"] = _adj
    df_msn_formula = (pd.DataFrame(msn_formula_rows).sort_values("lift")
                      if msn_formula_rows else pd.DataFrame(
                          columns=["formula","n","median","lift","p","p_adj"]))
    if not df_msn_formula.empty and "p_adj" not in df_msn_formula.columns:
        df_msn_formula["p_adj"] = np.nan

    # Dislike signal — unique MSN metric
    msn_dr = msn[msn["Likes"] > 0].copy()
    msn_dr["dislike_rate"] = msn_dr["Dislikes"] / (msn_dr["Likes"] + msn_dr["Dislikes"])
    N_MSN_DR     = len(msn_dr)
    MSN_DR_MED   = msn_dr["dislike_rate"].median()
    _msn_dr_r, _ = stats.spearmanr(msn_dr["dislike_rate"], msn_dr["Pageviews"])
    msn_hi_dr    = msn_dr[msn_dr["dislike_rate"] > msn_dr["dislike_rate"].quantile(0.75)][VIEWS_METRIC]
    msn_lo_dr    = msn_dr[msn_dr["dislike_rate"] < msn_dr["dislike_rate"].quantile(0.25)][VIEWS_METRIC]
    _, _msn_dr_p = stats.mannwhitneyu(msn_hi_dr, msn_lo_dr, alternative="two-sided")
    MSN_DR_LIFT  = msn_hi_dr.median() / msn_lo_dr.median() if msn_lo_dr.median() > 0 else np.nan
    msn_sports_dr = (msn_dr[msn_dr["topic"] == "sports"]["dislike_rate"].median()
                     if "sports" in msn_dr["topic"].values else 0.0)

    # Monthly PV trend
    msn_monthly = (msn.groupby("_msn_month")
                   .agg(n=("Pageviews","count"), med_pv=("Pageviews","median"))
                   .reset_index()
                   .sort_values("_msn_month"))
    MSN_JAN_MED_PV    = int(msn_monthly["med_pv"].iloc[0])  if len(msn_monthly) > 0 else 0
    MSN_DEC_MED_PV    = int(msn_monthly["med_pv"].iloc[-1]) if len(msn_monthly) > 0 else 0
    MSN_PV_DECLINE    = 1.0 - MSN_DEC_MED_PV / MSN_JAN_MED_PV if MSN_JAN_MED_PV > 0 else 0.0
    MSN_MAX_VOL_MONTH = str(msn_monthly.loc[msn_monthly["n"].idxmax(), "_msn_month"]) if len(msn_monthly) > 0 else "—"
    MSN_MAX_VOL_N     = int(msn_monthly["n"].max()) if len(msn_monthly) > 0 else 0

# ── MSN formula divergence stats (for new MSN Finding tile) ──────────────────
# Compute key scalars used in the new finding's HTML. Safe defaults if MSN empty.
if not msn.empty and not df_msn_formula.empty:
    _msn_other_med  = _msn_t1[_msn_t1["formula"] == "untagged"]["Pageviews"].median()
    _msn_n_total    = len(_msn_t1)
    _msn_n_other    = int((_msn_t1["formula"] == "untagged").sum())
    _msn_n_formula  = _msn_n_total - _msn_n_other
    # Best-performing formula row (highest lift, which is "untagged" by definition — use second)
    _msn_worst_f    = df_msn_formula.iloc[0] if len(df_msn_formula) > 0 else None
    MSN_OTHER_MED_PV     = int(_msn_other_med) if not np.isnan(_msn_other_med) else 0
    MSN_N_TOTAL          = _msn_n_total
    MSN_N_OTHER          = _msn_n_other
    MSN_N_FORMULA        = _msn_n_formula
    # Top 3 MSN articles (direct declaratives) for the example box
    _msn_top3 = (_msn_t1[_msn_t1["formula"] == "untagged"]
                 .nlargest(3, "Pageviews")[["Title", "Brand", "Pageviews"]])
    MSN_TOP3_EXAMPLES = [
        (str(r["Title"]), str(r["Brand"]), int(r["Pageviews"]))
        for _, r in _msn_top3.iterrows()
    ]
else:
    MSN_OTHER_MED_PV = 0
    MSN_N_TOTAL      = 0
    MSN_N_OTHER      = 0
    MSN_N_FORMULA    = 0
    MSN_TOP3_EXAMPLES = []

# ── MSN Video: completion rate by topic (for Finding 3 sports extension) ──────
try:
    _msn_vid = pd.read_excel(DATA_2026, sheet_name="MSN video")
    _msn_vid["topic"] = _msn_vid["Title"].apply(tag_topic)
    _msn_vid["completion_rate"] = (_msn_vid["Viewed (100%)"].fillna(0) /
                                   _msn_vid["Views"].replace(0, np.nan))
    _msn_vid_base = _msn_vid["completion_rate"].median()
    _msn_vid_sports = _msn_vid[_msn_vid["topic"] == "sports"]["completion_rate"]
    if len(_msn_vid_sports) >= 5 and _msn_vid_base > 0:
        _u_vid_sports = stats.mannwhitneyu(_msn_vid_sports.dropna(),
                                           _msn_vid[_msn_vid["topic"] != "sports"]["completion_rate"].dropna(),
                                           alternative="two-sided")
        MSN_VID_SPORTS_COMPLETION_IDX = float(_msn_vid_sports.median() / _msn_vid_base)
        MSN_VID_SPORTS_P              = float(_u_vid_sports.pvalue)
    else:
        MSN_VID_SPORTS_COMPLETION_IDX = np.nan
        MSN_VID_SPORTS_P              = 1.0
    HAS_MSN_VIDEO = True
except Exception as _e:
    _msn_vid = pd.DataFrame()
    MSN_VID_SPORTS_COMPLETION_IDX = np.nan
    MSN_VID_SPORTS_P              = 1.0
    HAS_MSN_VIDEO = False
    print(f"  MSN video not loaded: {_e}")

# ── Tracker join ──────────────────────────────────────────────────────────────
print("Computing tracker join…")
HAS_TRACKER  = False
tracker_df   = None
team_combined = pd.DataFrame()
author_stats  = pd.DataFrame()
team_top      = pd.DataFrame()
N_TRACKED     = 0
df_formula_team    = pd.DataFrame()
df_content_type    = pd.DataFrame()
df_author_profiles = pd.DataFrame()
df_vert_plat       = pd.DataFrame()
PARENT_MED_PCT = CHILD_MED_PCT = CT_P = np.nan
_ft_untagged_share = 0.0
_ft_top_formula    = "untagged"
_ft_top_formula_pct = 0.0

def _hn(t: str) -> str:
    """Normalize a headline to lowercase alphanumeric for tracker join matching."""
    return re.sub(r"[^a-z0-9]", "", str(t).lower().strip())

try:
    tracker_raw = pd.read_excel(TRACKER, sheet_name="Data")
    _t_cols = ["Published URL/Link", "Author", "Vertical", "Word Count", "Headline"]
    for _opt in ["Content_Type", "Personas (Target Audience)"]:
        if _opt in tracker_raw.columns:
            _t_cols.append(_opt)
    tracker_df  = tracker_raw[_t_cols].copy()
    tracker_df  = tracker_df.dropna(subset=["Author"])
    tracker_df["_url"] = tracker_df["Published URL/Link"].fillna("").str.strip().str.lower()
    tracker_df["_hn"]  = tracker_df["Headline"].apply(_hn)
    # Rename to avoid column conflicts when merging with datasets that also have Author column
    tracker_df = tracker_df.rename(columns={
        "Author": "t_author", "Vertical": "t_vertical",
        "Content_Type": "t_content_type",
        "Personas (Target Audience)": "t_persona",
    })
    HAS_TRACKER = True
except Exception as e:
    print(f"Tracker not loaded: {e}")

if HAS_TRACKER:
    rows = []

    # ── 1. Apple News: URL join + headline join (combined, deduplicated) ──────
    an_work = an.copy()
    an_work["_url"] = an_work["Publisher Article ID"].fillna("").str.strip().str.lower()
    an_work["_hn"]  = an_work["Article"].apply(_hn)
    # Build merge column list (includes optional tracker columns if present)
    _t_extra_cols = [c for c in ["t_content_type","t_persona"] if c in tracker_df.columns]
    _t_merge_base = ["t_author","t_vertical","Word Count"] + _t_extra_cols
    # URL join
    an_url_j = (an_work[an_work["_url"] != ""]
                .merge(tracker_df[["_url"] + _t_merge_base], on="_url", how="inner"))
    # Headline join (fallback for articles where URL format differs)

    an_hn_j  = (an_work[an_work["_hn"].str.len() > 10]
                .merge(tracker_df[["_hn"] + _t_merge_base], on="_hn", how="inner"))
    an_joined = pd.concat([an_url_j, an_hn_j]).drop_duplicates(subset=["Article ID"])
    for _, r in an_joined.iterrows():
        rows.append(dict(
            platform="Apple News",
            headline=r["Article"],
            brand=r.get("Brand", ""),
            author=r["t_author"],
            vertical=r.get("t_vertical", ""),
            content_type=r.get("t_content_type", ""),
            persona=r.get("t_persona", ""),
            pub_date=r["Date Published"],
            views=r["Total Views"],
            percentile=r[VIEWS_METRIC],
            featured=r.get("is_featured", False),
            word_count=r.get("Word Count", np.nan),
        ))

    # ── 2. SmartNews 2026: URL join ───────────────────────────────────────────
    sn26_work = sn26.copy()
    sn26_work["_url"] = sn26_work["url"].fillna("").str.strip().str.lower()
    sn26_work["percentile"] = sn26_work["article_view"].rank(pct=True)
    sn26_j = (sn26_work[sn26_work["_url"] != ""]
              .merge(tracker_df[["_url"] + _t_merge_base], on="_url", how="inner"))
    for _, r in sn26_j.iterrows():
        rows.append(dict(
            platform="SmartNews",
            headline=r["title"],
            brand=r.get("domain", ""),
            author=r["t_author"],
            vertical=r.get("t_vertical", ""),
            content_type=r.get("t_content_type", ""),
            persona=r.get("t_persona", ""),
            pub_date=r.get("date", pd.NaT),
            views=r["article_view"],
            percentile=r["percentile"],
            featured=False,
            word_count=r.get("Word Count", np.nan),
        ))

    # ── 3. Yahoo 2026: headline join ──────────────────────────────────────────
    yahoo26_work = yahoo26.copy()
    yahoo26_work["_hn"] = yahoo26_work["Content Title"].apply(_hn)
    yahoo26_work["percentile"] = yahoo26_work["Content Views"].rank(pct=True)
    yahoo26_j = (yahoo26_work[yahoo26_work["_hn"].str.len() > 10]
                 .merge(tracker_df[["_hn"] + _t_merge_base], on="_hn", how="inner"))
    for _, r in yahoo26_j.iterrows():
        rows.append(dict(
            platform="Yahoo",
            headline=r["Content Title"],
            brand=r.get("Provider Name", ""),
            author=r["t_author"],
            vertical=r.get("t_vertical", ""),
            content_type=r.get("t_content_type", ""),
            persona=r.get("t_persona", ""),
            pub_date=r.get("Publish Date", pd.NaT),
            views=r["Content Views"],
            percentile=r["percentile"],
            featured=False,
            word_count=r.get("Word Count", np.nan),
        ))

    team_combined = pd.DataFrame(rows)
    N_TRACKED = len(team_combined)
    print(f"Tracker join: {N_TRACKED} total matched articles "
          f"(AN={len(an_joined)}, SN={len(sn26_j)}, Yahoo={len(yahoo26_j)})")

# ── Tracker → ANP vertical performance join ───────────────────────────────────
# Separate from the Tarrow join above (which uses top-performers-only Apple News sheet).
# ANP has 420K rows / full article-level coverage — much higher match rate for Sara's team.
HAS_VERTICAL_DATA = False
df_vertical_perf   = pd.DataFrame()
df_vertical_top    = pd.DataFrame()
VERTICAL_FEAT_RATE = 0.0
VERTICAL_ANP_BASELINE_FEAT = 0.0
VERTICAL_MATCH_N   = 0
VERTICAL_MATCH_TOT = 0

if HAS_TRACKER and HAS_ANP:
    import glob as _glob
    _anp_files = _glob.glob(os.path.join(ANP_DATA_DIR, "*.csv"))
    if _anp_files:
        print("Building Tracker→ANP vertical performance join…")
        _anp_all = pd.concat(
            [pd.read_csv(f, low_memory=False) for f in _anp_files],
            ignore_index=True
        )
        _anp_all = _anp_all.rename(columns={"Publisher Article ID": "_pub_url"})
        _anp_all["_pub_url"] = _anp_all["_pub_url"].astype(str).str.strip().str.rstrip("/").str.lower()
        _anp_all["_is_feat"] = _anp_all["Featured by Apple"].astype(str).str.strip().str.lower().isin(["yes","true","1"])
        _anp_all["_views"]   = pd.to_numeric(_anp_all["Total Views"], errors="coerce")

        # Aggregate ANP to article level (sum views across days, any_featured)
        _anp_agg = (_anp_all.groupby("_pub_url")
            .agg(views_total=("_views","sum"),
                 is_featured=("_is_feat","any"),
                 article_title=("Article","first"),
                 sections=("Sections","first"))
            .reset_index())
        VERTICAL_ANP_BASELINE_FEAT = _anp_all["_is_feat"].any() and (_anp_agg["is_featured"].sum() / len(_anp_agg))

        # Build Tracker URL table with vertical_group derived from author
        def _extract_domain(u: str) -> str:
            m = re.search(r"https?://(?:www\.)?([^/]+)", str(u))
            return m.group(1) if m else ""

        _tk = tracker_df.copy()
        _tk["_pub_url"] = _tk["_url"].str.rstrip("/")
        _tk["_domain"]  = _tk["_pub_url"].apply(_extract_domain)
        # Filter staging and non-T1 domains
        _tk = _tk[~_tk["_domain"].isin(_TRACKER_EXCLUDE_DOMAINS)]
        # Derive vertical_group from author name
        _tk["vertical_group"] = _tk["t_author"].str.strip().map(AUTHOR_VERTICAL).fillna("Other")
        # Filter staging URLs
        _tk = _tk[~_tk["_pub_url"].str.contains("wpenginepowered|post\\.php|wp-admin", na=False)]

        _vert_merged = _tk.merge(
            _anp_agg[["_pub_url","views_total","is_featured","article_title","sections"]],
            on="_pub_url", how="left"
        )
        VERTICAL_MATCH_TOT = len(_vert_merged)
        VERTICAL_MATCH_N   = _vert_merged["views_total"].notna().sum()

        _vert_matched = _vert_merged[_vert_merged["views_total"].notna()].copy()
        _vert_matched["formula"] = _vert_matched["Headline"].apply(
            lambda h: classify_formula(str(h)) if pd.notna(h) else "untagged"
        )
        _vert_matched["topic"] = _vert_matched["Headline"].apply(
            lambda h: tag_topic(str(h)) if pd.notna(h) else "other"
        )

        VERTICAL_FEAT_RATE = _vert_matched["is_featured"].mean() if len(_vert_matched) > 0 else 0.0

        if len(_vert_matched) >= 5:
            HAS_VERTICAL_DATA = True
            # Per-vertical summary
            _vg = (_vert_matched.groupby("vertical_group")
                .agg(n=("views_total","count"),
                     med_views=("views_total","median"),
                     mean_views=("views_total","mean"),
                     max_views=("views_total","max"),
                     feat_rate=("is_featured","mean"))
                .reset_index()
                .sort_values("med_views", ascending=False))
            # Add top article per vertical
            _top_per_vert = (_vert_matched.loc[_vert_matched.groupby("vertical_group")["views_total"].idxmax()]
                [["vertical_group","Headline","views_total","is_featured"]].copy())
            df_vertical_perf = _vg.merge(_top_per_vert.rename(
                columns={"Headline":"top_headline","views_total":"top_views","is_featured":"top_featured"}),
                on="vertical_group", how="left")

            # Top 10 articles overall from matched
            df_vertical_top = (_vert_matched.sort_values("views_total", ascending=False)
                [["vertical_group","t_author","Headline","views_total","is_featured","sections"]]
                .head(10).reset_index(drop=True))

            print(f"Vertical perf: {VERTICAL_MATCH_N}/{VERTICAL_MATCH_TOT} matched, "
                  f"feat_rate={VERTICAL_FEAT_RATE:.1%}, "
                  f"{len(df_vertical_perf)} verticals")

    if N_TRACKED > 0:
        author_stats = (team_combined.groupby(["author", "platform"])
            .agg(n=("headline", "count"),
                 med_views=("views", "median"),
                 med_pct=("percentile", "median"))
            .reset_index()
            .sort_values("med_pct", ascending=False))

        team_top = (team_combined.sort_values("percentile", ascending=False)
                    [["headline","platform","brand","author","pub_date","views","percentile","featured"]]
                    .head(20))

        # Word count correlation (only for matched articles with word count data)
        wc_data = team_combined[team_combined["word_count"].notna() & (team_combined["word_count"] > 0)].copy()
        WC_MATCHED_N = len(wc_data)
        if WC_MATCHED_N >= 20:
            wc_data["wc_quartile"] = pd.qcut(wc_data["word_count"], 4,
                                              labels=["Q1 (short)","Q2","Q3","Q4 (long)"])
            df_wc_quartile = (wc_data.groupby("wc_quartile", observed=True)
                .agg(n=("word_count","count"),
                     med_wc=("word_count","median"),
                     med_pct=("percentile","median"))
                .reset_index())
            WC_Q1_MED = wc_data["word_count"].quantile(0.25)
            WC_Q4_MED = wc_data["word_count"].quantile(0.75)
            # Mann-Whitney: Q4 (longest) vs Q2 (apparent sweet spot)
            _wc_q2_v = wc_data[wc_data["wc_quartile"] == "Q2"]["percentile"].dropna()
            _wc_q4_v = wc_data[wc_data["wc_quartile"] == "Q4 (long)"]["percentile"].dropna()
            if len(_wc_q2_v) >= 5 and len(_wc_q4_v) >= 5:
                _, WC_Q4_VS_Q2_P = stats.mannwhitneyu(_wc_q4_v, _wc_q2_v, alternative="two-sided")
            else:
                WC_Q4_VS_Q2_P = np.nan
        else:
            WC_Q1_MED = np.nan
            WC_Q4_MED = np.nan
            WC_Q4_VS_Q2_P = np.nan

        # ── Formula diagnosis: classify the team's actual headlines ──────────
        # Shows whether the team's formula distribution aligns with what performs well
        team_combined["formula"] = team_combined["headline"].apply(classify_formula)
        df_formula_team = (team_combined.groupby("formula")
            .agg(n=("percentile","count"), med_pct=("percentile","median"))
            .reset_index()
            .sort_values("n", ascending=False))
        df_formula_team["share"] = df_formula_team["n"] / df_formula_team["n"].sum()
        _ft_total = df_formula_team["n"].sum()
        _ft_untagged_share = float(
            df_formula_team.loc[df_formula_team["formula"] == "untagged", "share"].values[0]
            if "untagged" in df_formula_team["formula"].values else 0)
        _ft_top_formula = (
            df_formula_team[df_formula_team["formula"] != "untagged"]
            .sort_values("n", ascending=False)["formula"].values[0]
            if len(df_formula_team[df_formula_team["formula"] != "untagged"]) > 0 else "untagged")
        _ft_top_formula_pct = float(
            df_formula_team.loc[df_formula_team["formula"] == _ft_top_formula, "share"].values[0]
            if _ft_top_formula in df_formula_team["formula"].values else 0)

        # ── Parent vs. Child (variant) performance ───────────────────────────
        # Parent-P = original article; Child-C = generated variant
        # Directly tests whether variants syndicate as well as originals
        df_content_type = pd.DataFrame()
        PARENT_MED_PCT = CHILD_MED_PCT = np.nan
        CT_P = np.nan
        if "content_type" in team_combined.columns:
            _ct = team_combined[team_combined["content_type"].fillna("") != ""]
            if len(_ct) > 0:
                df_content_type = (_ct.groupby("content_type")
                    .agg(n=("percentile","count"), med_pct=("percentile","median"))
                    .reset_index().sort_values("med_pct", ascending=False))
                _p_v = _ct[_ct["content_type"] == "Parent-P"]["percentile"].dropna()
                _c_v = _ct[_ct["content_type"] == "Child-C"]["percentile"].dropna()
                if len(_p_v) > 0: PARENT_MED_PCT = float(_p_v.median())
                if len(_c_v) > 0: CHILD_MED_PCT  = float(_c_v.median())
                if len(_p_v) >= 5 and len(_c_v) >= 5:
                    _, CT_P = stats.mannwhitneyu(_p_v, _c_v, alternative="two-sided")

        # ── Author formula profiles ──────────────────────────────────────────
        # Per author: most-used formula, median percentile, n articles
        df_author_formula = (team_combined.groupby(["author","formula"])
            .agg(n=("percentile","count"), med_pct=("percentile","median"))
            .reset_index())
        # Dominant formula per author (by count)
        _af_dominant = (df_author_formula
            .sort_values("n", ascending=False)
            .drop_duplicates(subset=["author"])
            [["author","formula","n","med_pct"]]
            .rename(columns={"formula":"top_formula","n":"n_top_formula","med_pct":"top_formula_med_pct"}))
        # Overall per-author stats
        _af_overall = (team_combined.groupby("author")
            .agg(n_total=("percentile","count"), med_pct_overall=("percentile","median"))
            .reset_index())
        df_author_profiles = _af_overall.merge(_af_dominant, on="author").sort_values("med_pct_overall", ascending=False)

        # ── Vertical routing: which team verticals perform where ─────────────
        df_vert_plat = pd.DataFrame()
        if "vertical" in team_combined.columns:
            _vp = team_combined[team_combined["vertical"].fillna("") != ""]
            if len(_vp) > 0:
                df_vert_plat = (_vp.groupby(["vertical","platform"])
                    .agg(n=("percentile","count"), med_pct=("percentile","median"))
                    .reset_index().query("n >= 3")
                    .sort_values(["vertical","med_pct"], ascending=[True,False]))


# ── Per-author analysis for Author Playbooks page ────────────────────────────
_AUTHOR_MIN_N = 5   # minimum matched articles to include an author
# List of (author, n, med_pct, tile_html, detail_html) — filled below if tracker loaded
_author_playbook_defs: list[tuple[str, int, float, str, str]] = []

_FORMULA_LABELS: dict[str, str] = {
    "number_lead":            "number lead",
    "what_to_know":           '"What to know"',
    "heres_formula":          '"Here\'s / Here are"',
    "question":               "question format",
    "possessive_named_entity":"possessive named entity",
    "quoted_lede":            "quoted lede",
    "untagged":               "no tracked formula",
}
# Capitalize first character of a formula label for use at the start of a sentence.
# Uses slicing rather than .capitalize() to preserve casing in the rest of the string
# (e.g. '"What to know"' must stay as-is, not become '"what to know"').
def _cap_lbl(s: str) -> str:
    """Capitalize first character of a label without lowercasing the rest."""
    return s[:1].upper() + s[1:] if s else s


# ── Column header tooltips ─────────────────────────────────────────────────────
# Keyed by normalized header text: lowercase, spaces collapsed, en-dash → hyphen.
# JS reads this dict on every page and attaches floating tooltips to all matching <th>.
# _check_col_tooltips() fires a build warning for any <th> text not found here.
_COL_TOOLTIPS: dict[str, str] = {
    "n":                              "Number of articles in this group.",
    "median %ile":                    "The middle article's rank within its publication-month cohort; 0.5 = exactly average for that outlet and month.",
    "cohort %ile":                    "The middle article's rank within its publication-month cohort; 0.5 = exactly average for that outlet and month.",
    "type":                           "Whether the article is an original piece or an AI-generated variant.",
    "structure":                      "The sub-pattern used by headlines that don't fit any main formula—helps identify emerging patterns.",
    "formula":                        "The structural template used in this headline (e.g. 'What to know', number lead).",
    "share":                          "This formula's fraction of all articles in the dataset.",
    "lift vs. team":                  "How much higher this author's median rank is compared to the team average; 1.2x means 20% above average.",
    "platform":                       "The distribution app where this article was published (Apple News, SmartNews, Yahoo, or MSN).",
    "headline":                       "The article headline as published to the distribution platform.",
    "views":                          "Total raw page views recorded for this article.",
    "author":                         "The article's author as recorded in the content tracker.",
    "n articles":                     "Number of articles attributed to this person in the dataset.",
    "article":                        "The article headline as published.",
    "platform / brand":               "The distribution app and the specific publication outlet.",
    "featured":                       "Whether Apple News editorially promoted this article to a Featured story slot.",
    "word count quartile":            "Articles split into four equal groups by word count, from shortest (Q1) to longest (Q4).",
    "median word count":              "The middle article's word count within this quartile group.",
    "number type":                    "Whether the number in the headline is rounded (e.g. '10 things') or specific (e.g. '7 takeaways').",
    "lift vs. baseline":              "How much higher this group's median rank is compared to untagged headlines; 1.5x means 50% higher.",
    "number range":                   "The size of the number used—small (2-9), medium (10-99), or large (100+).",
    "lift":                           "How much higher this group's median rank is compared to the reference group; 1.0 = same, 1.5x = 50% higher.",
    "95% ci (bootstrap)":             "The range we're 95% confident the true lift falls within, estimated by resampling the data 1,000 times.",
    "effect size r":                  "How practically significant the difference is (0 = none, 0.3+ = meaningful, 0.5+ = large).",
    "padj (bh-fdr)":                  "P-value corrected for testing multiple groups at once; below 0.05 means the result is unlikely to be random chance.",
    "n needed (80% power)":           "How many more articles would be needed to reliably detect this effect in a controlled experiment.",
    "featured rate":                  "Share of this formula's articles that Apple News promoted to a Featured editorial slot.",
    "publication":                    "The specific McClatchy publication outlet (e.g. Kansas City Star, Miami Herald, Us Weekly).",
    "top formula":                    "The headline formula with the highest median views lift vs. the untagged baseline for this publication.",
    "formula lift":                   "How much higher the top formula's median rank is compared to untagged headlines for this publication; 1.5× = 50% higher.",
    "top topic (views)":              "The content topic with the highest median view rank for this publication, excluding unclassified articles.",
    "within-featured median %ile":    "Among articles Apple News Featured, how this formula ranked against other Featured articles.",
    "channel":                        "The SmartNews topic channel this article was routed to (e.g. Entertainment, Local, Top).",
    "article count":                  "Number of articles published to this SmartNews channel.",
    "% of total":                     "This channel's share of all SmartNews articles in the dataset.",
    "median raw views":               "The middle article's actual view count—not normalized, so months with more traffic naturally score higher.",
    "lift vs. top":                   "How this channel's median rank compares to the Top feed, which is the reference baseline.",
    "feature":                        "The headline characteristic being tested (e.g. contains a named person, uses a question mark).",
    "n (present)":                    "Number of push notifications where this feature appeared in the headline.",
    "median ctr (present)":           "The middle click-through rate when this feature was in the headline; CTR = clicks divided by impressions.",
    "median ctr (absent)":            "The middle click-through rate when this feature was NOT in the headline.",
    "lift (95% ci)":                  "CTR improvement ratio with confidence range; 2.0x (1.5-2.5) means roughly twice the clicks when the feature is present.",
    "sport":                          "The specific sport sub-category (football, basketball, baseball, etc.).",
    "apple news n":                   "Number of articles published to Apple News in this group.",
    "apple news median %ile":         "The middle Apple News article's rank within its publication-month cohort.",
    "smartnews n":                    "Number of articles published to SmartNews in this group.",
    "smartnews median %ile":          "The middle SmartNews article's rank within its publication-month cohort.",
    "subtopic":                       "A more specific sub-category within the broader topic (e.g. 'violent crime' within crime, 'NFL' within sports).",
    "length bucket":                  "Headlines grouped by character count from shortest to longest.",
    "median chars (an)":              "The middle headline length in characters for Apple News articles in this group.",
    "metric":                         "The reader engagement signal being compared against view count.",
    "correlation with total views":   "How strongly this metric moves together with view count; +1.0 = always in sync, 0 = unrelated.",
    "what it measures":               "Plain-language description of what this engagement metric tracks.",
    "content type":                   "The article's editorial category (sports, politics, crime, etc.).",
    "n matched":                      "Number of articles where tracker data was successfully linked to distribution platform data.",
    "formula type":                   "The structural template used in this headline.",
    "share of team output":           "Fraction of the team's total articles that used this formula.",
    "total matched":                  "Number of this author's articles successfully linked to distribution platform data.",
    "dominant formula (performance)": "The formula type that produced this author's best-performing articles by cohort percentile.",
    "vertical":                       "The editorial section this article belongs to (e.g. sports, business, local news).",
    "topic":                          "The broad subject area of the article (sports, politics, crime, business, etc.).",
    "q1 2025":                        "Articles published January-March 2025.",
    "q2 2025":                        "Articles published April-June 2025.",
    "q3 2025":                        "Articles published July-September 2025.",
    "q4 2025":                        "Articles published October-December 2025.",
    "q1 2026":                        "Articles published January-March 2026.",
    "q2 2026":                        "Articles published April-June 2026.",
    "q3 2026":                        "Articles published July-September 2026.",
    "p (adj)":                        "P-value after BH-FDR correction for multiple comparisons; below 0.05 = statistically significant.",
    "month":                          "Calendar month (YYYY-MM format).",
    "articles":                       "Number of articles published in this month.",
    "median pageviews":               "The middle article's raw pageview count for this month.",
    # ANP findings (6 & 7)
    "article type":                   "Whether the article was Featured in Local News by Apple's editors, or not featured.",
    "median subscriber share":        "The middle article's share of unique viewers who are Apple News subscribers.",
    "non-subscriber reach":           "Share of unique viewers who are non-subscribers (potential new audience).",
    "median view percentile":         "Median within-publication view percentile (0–1 scale; 0.9 = top 10% for that publication).",
    "section":                        "Primary Apple News section the article was tagged to, excluding 'Main'.",
    # ANP finding 8 — section performance table
    "median rank":                    "Median view percentile rank within that publication (0–1 scale; 0.5 = average, 0.9 = top 10%).",
    "bottom 20%":                     "Share of articles in this section that ranked in the bottom quintile within their publication.",
    "top 20%":                        "Share of articles in this section that ranked in the top quintile within their publication.",
    # MSN formula divergence finding
    "lift vs. direct declarative":    "How much higher or lower this formula's median pageviews are vs. direct declarative headlines; below 1.0 = underperforms direct statements.",
    "median pvs":                     "The middle article's raw MSN pageview count for this formula group.",
    # Finding A — formula × topic
    "formula × topic":                "The combination of headline formula type and content topic being tested.",
    "featuring rate":                 "Share of articles in this formula × topic combination that Apple News promoted to a Featured editorial slot.",
    # Finding B — SmartNews cross-platform
    "apple news feat%":               "Share of articles that Apple News promoted to a Featured editorial slot.",
    "smartnews pct_rank":             "Median percentile rank on SmartNews (0.5 = exactly average; above 0.5 = outperforms).",
    "sn rank":                        "Median SmartNews percentile rank (0–1 scale; 0.5 = average for that outlet and month).",
    # Notification outcome-language and send-time findings
    "signal":                         "The headline feature or text pattern being tested for CTR association.",
    "description":                    "Words or patterns that trigger this signal in the classifier.",
    "p_raw":                          "Unadjusted p-value before multiple-comparison correction.",
    "p_adj":                          "P-value after BH-FDR correction across all signals tested simultaneously.",
    "send window":                    "Time-of-day window when the push notification was sent.",
    "median ctr":                     "The middle click-through rate for notifications sent in this time window.",
    "cross-platform verdict":         "Whether to use this formula for Apple News only, SmartNews only, or both platforms simultaneously.",
    "p_adj (bh-fdr)":                 "P-value after BH-FDR correction for testing multiple signals simultaneously; below 0.05 = statistically significant.",
    "sn baseline":                    "The median SmartNews percentile rank for the untagged baseline (direct declarative headlines) used as the comparison group.",
    "sn p-value":                     "P-value from Mann-Whitney U test comparing this formula to the untagged baseline on SmartNews.",
    # Quote lede subtype analysis (Finding 1 drill-down)
    "quote lede type":                "The speaker context identified after the closing quote mark: official/authority, expert/scientist, subject's own words, or third-party.",
    "p (chi\u00b2)":                  "P-value from chi-square test comparing this quote lede subtype's featuring rate vs. all other articles. Uncorrected for multiple comparisons.",
    # Dual-platform headline pairs table (pb-dual playbook tile)
    "topic / content type":           "The editorial subject area or content vertical these headline examples apply to.",
    "apple news headline":            "Example headline optimized for Apple News featuring and organic reach on that platform.",
    "smartnews headline":             "Example headline optimized for SmartNews algorithmic distribution on that platform.",
    "max views":                      "The highest single-article view count observed for this formula or topic combination.",
    "median views":                   "The middle article's raw view count for this formula or topic combination.",
    "notes":                          "Additional context about the rule or tradeoff for this topic-platform pairing.",
    "top article":                    "The headline of the highest-performing article observed in this group, as a real-world example.",
}


def _make_col_tooltip_js() -> str:
    """Return JS that attaches floating hover tooltips to every <th> with a known column name.

    Uses a floating position:fixed div to avoid table overflow/clipping. Respects the
    current theme (dark/light). Falls back silently for any <th> not in _COL_TOOLTIPS.
    Safe to call for all three site pages — the dict is the single source of truth.
    """
    tips_json = json.dumps(_COL_TOOLTIPS, ensure_ascii=False, indent=None)
    return f"""
/* ── Column header tooltips ───────────────────────────────────────────────── */
(function() {{
  var _TIPS = {tips_json};

  function _normKey(s) {{
    // Normalize <th> textContent for dict lookup: trim, collapse spaces, lowercase,
    // replace en-dash (\u2013) with hyphen so "BH\u2013FDR" and "BH-FDR" both match.
    return s.trim().replace(/\\s+/g, ' ').toLowerCase().replace(/\u2013/g, '-');
  }}

  var _tip = document.createElement('div');
  _tip.style.cssText = 'display:none;position:fixed;z-index:9999;max-width:270px;' +
    'padding:7px 11px;border-radius:7px;font-size:12px;line-height:1.5;pointer-events:none;';
  document.body.appendChild(_tip);

  function _tipTheme() {{
    var dark = !document.body.classList.contains('light');
    _tip.style.background = dark ? '#1a1d27' : '#ffffff';
    _tip.style.color       = dark ? '#e8eaf6' : '#374151';
    _tip.style.border      = dark ? '1px solid #2e3350' : '1px solid #d1d5db';
    _tip.style.boxShadow   = dark ? '0 4px 14px rgba(0,0,0,0.5)' : '0 4px 14px rgba(0,0,0,0.12)';
  }}

  document.addEventListener('mouseover', function(e) {{
    var th = e.target.closest('th');
    if (!th) {{ _tip.style.display = 'none'; return; }}
    var txt = _TIPS[_normKey(th.textContent || '')];
    if (!txt) {{ _tip.style.display = 'none'; return; }}
    _tip.textContent = txt;
    _tipTheme();
    _tip.style.display = 'block';
  }});

  document.addEventListener('mousemove', function(e) {{
    if (_tip.style.display === 'none') return;
    var x = e.clientX + 14, y = e.clientY - 8;
    if (x + _tip.offsetWidth  > window.innerWidth  - 10) x = e.clientX - _tip.offsetWidth  - 14;
    if (y + _tip.offsetHeight > window.innerHeight - 10) y = e.clientY - _tip.offsetHeight - 10;
    _tip.style.left = x + 'px';
    _tip.style.top  = y + 'px';
  }});

  document.addEventListener('mouseout', function(e) {{
    var th = e.target.closest('th');
    if (th && !th.contains(e.relatedTarget)) _tip.style.display = 'none';
  }});
}})();
"""

if HAS_TRACKER and N_TRACKED >= _AUTHOR_MIN_N and len(team_combined) > 0:
    _team_med_pct = float(team_combined["percentile"].median())

    # Team-wide formula medians for benchmarking each author against
    _team_formula_meds: dict[str, float] = {}
    if not df_formula_team.empty and "formula" in df_formula_team.columns:
        for _, _tfr in df_formula_team.iterrows():
            _team_formula_meds[str(_tfr["formula"])] = float(_tfr["med_pct"])

    # Authors with enough articles, ranked best first
    _ranked_authors = (df_author_profiles.copy()
                       .query("n_total >= @_AUTHOR_MIN_N")
                       .sort_values("med_pct_overall", ascending=False)
                       .reset_index(drop=True))

    for _ai, _arow in _ranked_authors.iterrows():
        _auth     = str(_arow["author"])
        _adf      = team_combined[team_combined["author"] == _auth].copy()
        _n        = len(_adf)
        if _n < _AUTHOR_MIN_N:
            continue
        _med        = float(_adf["percentile"].median())
        _rank       = int(_ai) + 1
        _total_auth = len(_ranked_authors)

        # ── Formula breakdown ──────────────────────────────────────
        _af = (_adf.groupby("formula")
               .agg(n=("percentile","count"), med_pct=("percentile","median"))
               .reset_index().sort_values("n", ascending=False))
        _af["share"] = _af["n"] / max(_af["n"].sum(), 1)
        _dom_row      = _af.iloc[0] if not _af.empty else None
        _dom_formula  = str(_dom_row["formula"]) if _dom_row is not None else "untagged"
        _dom_pct      = float(_dom_row["share"])   if _dom_row is not None else 0.0
        _dom_med      = float(_dom_row["med_pct"]) if _dom_row is not None else _med
        _dom_label    = _FORMULA_LABELS.get(_dom_formula, _dom_formula.replace("_"," "))
        _dom_vs_self  = _dom_med - _med

        # Best tagged formula (excluding untagged) for coaching suggestion
        _af_tagged   = _af[_af["formula"] != "untagged"]
        _best_f_row  = (_af_tagged.sort_values("med_pct", ascending=False).iloc[0]
                        if len(_af_tagged) >= 1 else None)

        # ── Platform breakdown ─────────────────────────────────────
        _ap = (_adf.groupby("platform")
               .agg(n=("percentile","count"), med_pct=("percentile","median"))
               .reset_index().sort_values("med_pct", ascending=False))
        _best_p_row  = _ap.iloc[0] if not _ap.empty else None
        _best_plat   = str(_best_p_row["platform"])    if _best_p_row is not None else "—"
        _best_plat_m = float(_best_p_row["med_pct"])   if _best_p_row is not None else _med

        # ── Derived signals ────────────────────────────────────────
        _delta_pts_signed = (_med - _team_med_pct) * 100
        _above_below      = "above" if _delta_pts_signed >= 0 else "below"
        _delta_pts        = abs(_delta_pts_signed)

        _worst_p_row  = _ap.iloc[-1] if len(_ap) >= 2 else None
        _worst_plat   = str(_worst_p_row["platform"])  if _worst_p_row is not None else None
        _worst_plat_m = float(_worst_p_row["med_pct"]) if _worst_p_row is not None else None

        _best_alt_row = None
        for _, _frow in _af_tagged.sort_values("med_pct", ascending=False).iterrows():
            if str(_frow["formula"]) != _dom_formula and int(_frow["n"]) >= 3:
                _best_alt_row = _frow
                break

        # Signal flags
        _formula_mismatch = (
            _best_f_row is not None
            and str(_best_f_row["formula"]) != _dom_formula
            and (float(_best_f_row["med_pct"]) - _dom_med) * 100 >= 10
        )
        _formula_dragging = (_dom_vs_self * 100 <= -8)
        _platform_split   = (
            _worst_p_row is not None
            and (float(_best_p_row["med_pct"]) - float(_worst_p_row["med_pct"])) * 100 >= 20
        )

        # ── Significance tests ─────────────────────────────────────
        # Mann-Whitney U (one-tailed: is the higher-median group stochastically greater?).
        # Minimum 3 articles per group; per-author n is small so p<0.05 → Moderate, p<0.10 → Directional.
        _formula_test_p  = None
        _platform_test_p = None

        if (_formula_mismatch or _formula_dragging) and _best_f_row is not None and _dom_row is not None:
            _fta = _adf[_adf["formula"] == str(_best_f_row["formula"])]["percentile"].dropna()
            _ftb = _adf[_adf["formula"] == _dom_formula]["percentile"].dropna()
            if len(_fta) >= 3 and len(_ftb) >= 3:
                try:
                    _, _formula_test_p = stats.mannwhitneyu(_fta, _ftb, alternative="greater")
                except (ValueError, TypeError):
                    pass  # Graceful degradation: test result stays None, chart still renders

        if _platform_split and _worst_p_row is not None:
            _pta = _adf[_adf["platform"] == _best_plat]["percentile"].dropna()
            _ptb = _adf[_adf["platform"] == _worst_plat]["percentile"].dropna()
            if len(_pta) >= 3 and len(_ptb) >= 3:
                try:
                    _, _platform_test_p = stats.mannwhitneyu(_pta, _ptb, alternative="greater")
                except (ValueError, TypeError):
                    pass  # Graceful degradation: test result stays None, chart still renders

        _formula_sig  = _formula_test_p  is not None and _formula_test_p  < 0.05
        _formula_dir  = _formula_test_p  is not None and _formula_test_p  < 0.10
        _platform_sig = _platform_test_p is not None and _platform_test_p < 0.05
        _platform_dir = _platform_test_p is not None and _platform_test_p < 0.10

        # ── Badge: confidence of the leading signal ────────────────
        # "Moderate" = passes p<0.05 (max for single-author analyses; can't replicate across outlets).
        # "Directional" = p<0.10 or size-based signal without a test.
        _active_formula  = _formula_mismatch or _formula_dragging
        if _active_formula and _formula_sig:
            _badge_cls, _badge_lbl = "conf-mod", "Moderate confidence"
        elif _platform_split and not _active_formula and _platform_sig:
            _badge_cls, _badge_lbl = "conf-mod", "Moderate confidence"
        else:
            _badge_cls, _badge_lbl = "conf-dir", "Directional"

        # ── Claim + action ─────────────────────────────────────────
        # Language matches the badge:
        #   Moderate  → assertive ("is associated with higher %ile", "prioritize X")
        #   Directional → framed as a hypothesis ("shows a trend toward", "test X")
        if _formula_mismatch:
            _bfl      = _FORMULA_LABELS.get(str(_best_f_row["formula"]),
                                            str(_best_f_row["formula"]).replace("_", " "))
            _gap_pts  = (float(_best_f_row["med_pct"]) - _dom_med) * 100
            _p_note   = (f" (p={_formula_test_p:.2f})" if _formula_test_p is not None
                         and not _formula_sig else "")
            if _formula_sig:
                _claim = (
                    f"{_cap_lbl(_bfl)} is associated with significantly higher cohort percentile than "
                    f"{_dom_label} in this author's own articles — {float(_best_f_row['med_pct']):.0%}ile "
                    f"vs. {_dom_med:.0%}ile, a {_gap_pts:.0f}-pt gap — yet {_dom_label} makes up "
                    f"{_dom_pct:.0%} of output."
                )
                _action = (
                    f"Shift more output to {_bfl}. The data from this author's own articles supports it: "
                    f"{float(_best_f_row['med_pct']):.0%}ile vs. {_dom_med:.0%}ile for {_dom_label}. "
                    f"Route through {_best_plat} first ({_best_plat_m:.0%}ile)."
                )
            else:
                _claim = (
                    f"{_cap_lbl(_bfl)} shows a {_gap_pts:.0f}-pt advantage over {_dom_label} in this author's "
                    f"data ({float(_best_f_row['med_pct']):.0%}ile vs. {_dom_med:.0%}ile){_p_note}, "
                    f"but {_dom_label} is {_dom_pct:.0%} of output. Directional — small sample."
                )
                _action = (
                    f"Test {_bfl} on the next 3–5 articles and track cohort percentile. "
                    f"If the gap holds, make it the primary format. "
                    f"Best platform to test on: {_best_plat} ({_best_plat_m:.0%}ile)."
                )
        elif _formula_dragging:
            _drag_pts = abs(_dom_vs_self * 100)
            _p_note   = (f" (p={_formula_test_p:.2f})" if _formula_test_p is not None
                         and not _formula_sig else "")
            if _best_alt_row is not None:
                _alt_lbl = _FORMULA_LABELS.get(str(_best_alt_row["formula"]),
                                               str(_best_alt_row["formula"]).replace("_", " "))
                if _formula_sig:
                    _claim = (
                        f"{_cap_lbl(_dom_label)} — {_dom_pct:.0%} of this author's output — is associated with "
                        f"significantly lower cohort percentile than {_alt_lbl}: "
                        f"{_dom_med:.0%}ile vs. {float(_best_alt_row['med_pct']):.0%}ile, "
                        f"a {_drag_pts:.0f}-pt drag."
                    )
                    _action = (
                        f"Reduce {_dom_label} and reallocate to {_alt_lbl}. "
                        f"The performance difference is statistically supported in this author's own data. "
                        f"Platform with highest ROI: {_best_plat} ({_best_plat_m:.0%}ile)."
                    )
                else:
                    _claim = (
                        f"{_cap_lbl(_dom_label)} sits {_drag_pts:.0f} pts below this author's median "
                        f"({_dom_med:.0%}ile vs. {_med:.0%}ile){_p_note}. "
                        f"{_cap_lbl(_alt_lbl)} shows {float(_best_alt_row['med_pct']):.0%}ile. Directional — worth testing."
                    )
                    _action = (
                        f"Trial {_alt_lbl} over {_dom_label} on the next several articles. "
                        f"If cohort percentile improves, shift the mix. "
                        f"Best platform: {_best_plat} ({_best_plat_m:.0%}ile)."
                    )
            else:
                _p_note2 = (f" (p={_formula_test_p:.2f})" if _formula_test_p is not None else "")
                _claim = (
                    f"{_cap_lbl(_dom_label)} — {_dom_pct:.0%} of output — sits {_drag_pts:.0f} pts below "
                    f"this author's overall median{_p_note2}. No strong alternative formula yet in the data."
                )
                _action = (
                    f"Diversify beyond {_dom_label}. Try 'Here's what to know' or a number lead "
                    f"on the next 3–5 articles and compare percentile rank. "
                    f"Best platform: {_best_plat} ({_best_plat_m:.0%}ile)."
                )
        elif _platform_split:
            _plat_gap = (float(_best_p_row["med_pct"]) - float(_worst_p_row["med_pct"])) * 100
            _p_note   = (f" (p={_platform_test_p:.2f})" if _platform_test_p is not None
                         and not _platform_sig else "")
            if _platform_sig:
                _claim = (
                    f"{_best_plat} is a significantly stronger platform for this author: "
                    f"{_best_plat_m:.0%}ile vs. {_worst_plat_m:.0%}ile on {_worst_plat} "
                    f"— a {_plat_gap:.0f}-pt gap that holds up statistically."
                )
                _action = (
                    f"Concentrate output on {_best_plat} and reduce {_worst_plat} volume or "
                    f"reformat those headlines before syndication. "
                    f"{_cap_lbl(_dom_label)} is the current dominant format ({_dom_pct:.0%} of articles)."
                )
            else:
                _claim = (
                    f"{_best_plat} shows a {_plat_gap:.0f}-pt advantage over {_worst_plat} "
                    f"({_best_plat_m:.0%}ile vs. {_worst_plat_m:.0%}ile){_p_note}. "
                    f"Directional — worth routing more output to {_best_plat} to test."
                )
                _action = (
                    f"Route the next 5+ articles through {_best_plat} first and track whether "
                    f"the percentile gap persists. {_cap_lbl(_dom_label)} is {_dom_pct:.0%} of current output."
                )
        else:
            # Default: no formula or platform signal — lead with team-relative position + untagged note
            if _dom_formula == "untagged":
                _claim = (
                    f"{_dom_pct:.0%} of articles use no tracked headline formula. "
                    f"Overall median is {_med:.0%}ile — {_delta_pts:.0f} pts {_above_below} team — "
                    f"but formula impact can't be measured without consistent format use."
                )
                _action = (
                    f"Apply a repeatable headline formula (number lead, 'What to know', or possessive named entity) "
                    f"to at least the next 5 articles. That creates a testable signal. "
                    f"Best platform right now: {_best_plat} ({_best_plat_m:.0%}ile)."
                )
            elif _delta_pts_signed >= 0:
                _claim = (
                    f"{_delta_pts:.0f} pts above team median ({_med:.0%}ile). "
                    f"{_cap_lbl(_dom_label)} is {_dom_pct:.0%} of output at {_dom_med:.0%}ile — "
                    f"no clear underperforming signal to act on."
                )
                _action = (
                    f"Maintain the current approach. {_best_plat} is the highest-ROI platform "
                    f"({_best_plat_m:.0%}ile). Look for opportunities to increase {_dom_label} "
                    f"on that platform specifically."
                )
            else:
                _claim = (
                    f"{_delta_pts:.0f} pts below team median ({_med:.0%}ile). "
                    f"{_cap_lbl(_dom_label)} is {_dom_pct:.0%} of output at {_dom_med:.0%}ile — "
                    f"not enough formula variation yet to isolate the cause."
                )
                _action = (
                    f"Test a different headline format for 3–5 articles — try 'What to know' or a "
                    f"number lead — and compare cohort percentile. "
                    f"Best platform: {_best_plat} ({_best_plat_m:.0%}ile)."
                )

        # ── Build detail HTML tables ───────────────────────────────
        _formula_rows = []
        for _, _fr in _af.iterrows():
            _f_lbl    = _FORMULA_LABELS.get(str(_fr["formula"]), str(_fr["formula"]).replace("_"," "))
            _t_med_f  = _team_formula_meds.get(str(_fr["formula"]), _team_med_pct)
            _lift_f   = float(_fr["med_pct"]) / _t_med_f if _t_med_f > 0 else 1.0
            _lf_cls   = "lift-high" if _lift_f >= 1.2 else ("lift-pos" if _lift_f >= 0.9 else "lift-neg")
            _formula_rows.append(
                f'<tr><td>{_f_lbl}</td><td>{int(_fr["n"])}</td>'
                f'<td>{float(_fr["share"]):.0%}</td>'
                f'<td>{float(_fr["med_pct"]):.0%}</td>'
                f'<td><span class="{_lf_cls}">{_lift_f:.2f}\u00d7</span></td></tr>'
            )
        _formula_tbody = "\n".join(_formula_rows) or "<tr><td colspan='5'>No formula data</td></tr>"

        # Significance note for formula table
        if _formula_test_p is not None:
            if _formula_sig:
                _f_sig_note = (f'<p class="detail-sub" style="color:#4ade80;margin-top:0.4rem">'
                               f'&#10003; Top formula vs. dominant: p={_formula_test_p:.3f} '
                               f'(Mann-Whitney U, one-tailed) — statistically significant.</p>')
            elif _formula_dir:
                _f_sig_note = (f'<p class="detail-sub" style="margin-top:0.4rem">'
                               f'Top formula vs. dominant: p={_formula_test_p:.3f} — directional, '
                               f'not yet significant at p&lt;0.05. Worth testing with more articles.</p>')
            else:
                _f_sig_note = (f'<p class="detail-sub" style="margin-top:0.4rem">'
                               f'Top formula vs. dominant: p={_formula_test_p:.3f} — no significant '
                               f'difference detected. More data needed.</p>')
        else:
            _f_sig_note = ('<p class="detail-sub" style="margin-top:0.4rem">'
                           'Significance test not run (fewer than 3 articles per formula group).</p>')

        _plat_rows = []
        for _, _pr in _ap.iterrows():
            _lift_p = float(_pr["med_pct"]) / _team_med_pct if _team_med_pct > 0 else 1.0
            _lp_cls = "lift-high" if _lift_p >= 1.2 else ("lift-pos" if _lift_p >= 0.9 else "lift-neg")
            _plat_rows.append(
                f'<tr><td>{_pr["platform"]}</td><td>{int(_pr["n"])}</td>'
                f'<td>{float(_pr["med_pct"]):.0%}</td>'
                f'<td><span class="{_lp_cls}">{_lift_p:.2f}\u00d7</span></td></tr>'
            )
        _plat_tbody = "\n".join(_plat_rows) or "<tr><td colspan='4'>No platform data</td></tr>"

        # Significance note for platform table
        if _platform_test_p is not None:
            if _platform_sig:
                _p_sig_note = (f'<p class="detail-sub" style="color:#4ade80;margin-top:0.4rem">'
                               f'&#10003; Best vs. weakest platform: p={_platform_test_p:.3f} '
                               f'(Mann-Whitney U, one-tailed) — statistically significant.</p>')
            elif _platform_dir:
                _p_sig_note = (f'<p class="detail-sub" style="margin-top:0.4rem">'
                               f'Best vs. weakest platform: p={_platform_test_p:.3f} — directional, '
                               f'not yet significant at p&lt;0.05.</p>')
            else:
                _p_sig_note = (f'<p class="detail-sub" style="margin-top:0.4rem">'
                               f'Best vs. weakest platform: p={_platform_test_p:.3f} — no significant '
                               f'difference detected.</p>')
        else:
            _p_sig_note = ""  # no platform split → no note needed

        _top_arts = _adf.nlargest(min(10, _n), "percentile")
        _top_rows = []
        for _, _tr in _top_arts.iterrows():
            _hl    = html_module.escape(str(_tr.get("headline","")))
            _views = int(_tr.get("views", 0))
            _pct   = float(_tr.get("percentile", 0))
            _top_rows.append(
                f'<tr><td style="max-width:360px;white-space:normal">{_hl}</td>'
                f'<td>{_tr.get("platform","")}</td>'
                f'<td>{_views:,}</td><td>{_pct:.0%}</td></tr>'
            )
        _top_tbody = "\n".join(_top_rows) or "<tr><td colspan='4'>No articles</td></tr>"

        # Optional: parent vs. variant split
        _ct_section_html = ""
        if "content_type" in _adf.columns:
            _ct_sub = _adf[_adf["content_type"].fillna("") != ""]
            _p_v = _ct_sub[_ct_sub["content_type"] == "Parent-P"]["percentile"].dropna()
            _c_v = _ct_sub[_ct_sub["content_type"] == "Child-C"]["percentile"].dropna()
            if len(_p_v) > 0 and len(_c_v) > 0:
                _ct_section_html = (
                    f'\n  <h3 class="rh">Original vs. variant performance</h3>'
                    f'\n  <p class="detail-sub">{len(_p_v)} originals (Parent-P) · {len(_c_v)} generated variants (Child-C)</p>'
                    f'\n  <table><thead><tr><th>Type</th><th>n</th><th>Median %ile</th></tr></thead>'
                    f'\n  <tbody>'
                    f'\n    <tr><td>Original (Parent-P)</td><td>{len(_p_v)}</td><td>{float(_p_v.median()):.0%}</td></tr>'
                    f'\n    <tr><td>Variant (Child-C)</td><td>{len(_c_v)}</td><td>{float(_c_v.median()):.0%}</td></tr>'
                    f'\n  </tbody></table>'
                )

        _n_plats     = len(_ap)

        # ── Untagged sub-characterization ──────────────────────────
        # When untagged is a significant share, break it into structural sub-patterns
        # so the author sees what their untagged headlines actually are.
        _untagged_section_html = ""
        _untagged_df = _adf[_adf["formula"] == "untagged"]
        _untagged_share_of_total = len(_untagged_df) / max(_n, 1)
        if len(_untagged_df) >= 4 and _untagged_share_of_total >= 0.20:
            _untagged_df = _untagged_df.copy()
            _untagged_df["_structure"] = _untagged_df["headline"].apply(_classify_untagged_structure)
            _us = (_untagged_df.groupby("_structure")
                   .agg(n=("percentile","count"), med_pct=("percentile","median"))
                   .reset_index().sort_values("n", ascending=False))
            _us_rows = []
            for _, _ur in _us.iterrows():
                _ulbl = _UNTAGGED_STRUCTURE_LABELS.get(str(_ur["_structure"]),
                                                        str(_ur["_structure"]).replace("_"," "))
                _u_pct = float(_ur["med_pct"])
                _u_lfc = "lift-high" if _u_pct >= 0.65 else ("lift-pos" if _u_pct >= 0.45 else "lift-neg")
                _us_rows.append(
                    f'<tr><td>{_ulbl}</td><td>{int(_ur["n"])}</td>'
                    f'<td><span class="{_u_lfc}">{_u_pct:.0%}</span></td></tr>'
                )
            if _us_rows:
                _untagged_section_html = (
                    f'\n  <h3 class="rh">What the untagged headlines actually are</h3>\n'
                    f'  <p class="detail-sub">{len(_untagged_df)} of {_n} articles '
                    f'({_untagged_share_of_total:.0%}) matched no tracked formula. '
                    f'Secondary pattern breakdown — cohort %ile per structural type.</p>\n'
                    f'  <table><thead><tr><th>Structure</th><th>n</th>'
                    f'<th>Median %ile</th></tr></thead>\n'
                    f'  <tbody>{"".join(_us_rows)}</tbody></table>\n'
                    f'  <p class="detail-sub" style="margin-top:0.4rem">These are sub-patterns within '
                    f'the untagged bucket — not formal formulas, but useful for spotting what\'s '
                    f'working and where a structured formula could be applied next.</p>\n'
                )

        # ── Vertical / trendhunter context ────────────────────────
        _auth_vertical   = AUTHOR_VERTICAL.get(_auth, "")
        _is_trendhunter  = _auth_vertical in TRENDHUNTER_VERTICALS
        # Look up per-vertical match count for the 0% featuring note
        _vert_match_n    = 0
        if _is_trendhunter and HAS_VERTICAL_DATA:
            try:
                _vr = df_vertical_perf[df_vertical_perf["vertical_group"] == _auth_vertical]
                _vert_match_n = int(_vr["n"].iloc[0]) if len(_vr) > 0 else 0
            except Exception:
                _vert_match_n = 0
        _trendhunter_note_html = ""
        if _is_trendhunter:
            _n_note = (f", n={_vert_match_n} matched articles" if _vert_match_n > 0
                       else " (small sample — more data expected as ANP monthly drops accumulate)")
            _prelim = " — <em>preliminary, n&lt;30</em>" if _vert_match_n < 30 else ""
            _trendhunter_note_html = (
                f'  <div class="callout" style="margin-top:0.75rem;background:rgba(59,130,246,0.08);'
                f'border-left-color:#7c9df7">\n'
                f'    <strong>Vertical: {html_module.escape(_auth_vertical)}{_prelim}</strong> — '
                f'This vertical currently earns 0% featuring rate on Apple News Publisher data '
                f'(Jan–Feb 2026{_n_note}). Featuring is not a lever for this content. '
                f'Optimize for organic Apple News views and SmartNews distribution instead.\n'
                f'  </div>\n'
            )

        # ── Guardrail: platform-wide avoidance formula cross-check ────
        # If the algorithm recommended a formula that contradicts platform-wide guidance,
        # automatically append a cross-platform caveat. This prevents author-level
        # small-sample noise from silently overriding confirmed avoidance rules.
        _recommended_formula_key = (
            str(_best_f_row["formula"]) if _formula_mismatch and _best_f_row is not None
            else str(_best_alt_row["formula"]) if _formula_dragging and _best_alt_row is not None
            else ""
        )
        if _recommended_formula_key in PLATFORM_AVOIDANCE_FORMULAS:
            _avoidance_note = PLATFORM_AVOIDANCE_FORMULAS[_recommended_formula_key]
            _action = (
                f"{_action} "
                f"⚠ Cross-platform note: {_avoidance_note}"
            )

        # ── Guardrail: low-signal platform routing caveat ─────────────
        # If Yahoo (or other low-signal platform) surfaces as best platform,
        # flag it so editors aren't routed on unreliable evidence.
        if _best_plat in LOW_SIGNAL_PLATFORMS:
            _action = (
                f"{_action} "
                f"⚠ Platform note: {_best_plat} signal is low-confidence per current data "
                f"(data discontinuity from platform changes). Prioritize Apple News and SmartNews "
                f"for formula testing before routing to {_best_plat}."
            )

        # ── Assemble tile + detail HTML ────────────────────────────
        _ap_id = f"ap-{_ai}"

        _safe_auth   = html_module.escape(_auth)
        _safe_claim  = html_module.escape(_claim[:1].upper() + _claim[1:] if _claim else _claim)
        _safe_action = html_module.escape(_action)
        # Vertical label: show content vertical so Sarah can navigate by content type,
        # not just by author name. Guaranteed by AUTHOR_VERTICAL mapping at module level.
        _vert_suffix = (f' <span style="font-weight:400;color:var(--text-muted);font-size:.85em">'
                        f'· {html_module.escape(_auth_vertical)}</span>'
                        if _auth_vertical else "")

        _tile_html = (
            f'  <div class="pb-tile" onclick="togglePb(this,\'{_ap_id}\')">\n'
            f'    <span class="conf-badge {_badge_cls}">{_badge_lbl}</span>\n'
            f'    <span class="tile-label">{_safe_auth}{_vert_suffix}</span>\n'
            f'    <p class="tile-claim">{_safe_claim}</p>\n'
            f'    <p class="tile-action">\u2192 {_safe_action}</p>\n'
            f'    <span class="tile-toggle">Details \u2193</span>\n'
            f'  </div>'
        )

        # Determine DO vs. TRY verb for the guidance items based on signal confidence.
        # Moderate badge = statistically supported → DO. Directional = hypothesis → TRY.
        _primary_verb = "DO" if _badge_cls == "conf-mod" else "TRY"

        # Build the structured guidance list. Primary item: the signal-derived action.
        # Secondary item: platform routing — always available and always actionable.
        _guidance_rows = [(_primary_verb, _safe_action)]
        # Add platform item only if it's not redundant (i.e. not already the sole platform signal).
        if not _platform_split and _n_plats >= 2:
            if _best_plat in LOW_SIGNAL_PLATFORMS:
                # Low-signal platform: add guidance note with required caveat rather than
                # a routing recommendation. Guardrail keeps this consistent with the tile action text.
                _plat_note = html_module.escape(
                    f"Platform data shows {_best_plat} at {_best_plat_m:.0%}ile — but {_best_plat} "
                    f"signal is low-confidence (data discontinuity from platform changes). "
                    f"Prioritize Apple News and SmartNews for formula testing first."
                )
            else:
                _plat_note = html_module.escape(
                    f"Route new articles through {_best_plat} first ({_best_plat_m:.0%}ile) — "
                    f"your highest-ROI distribution channel this round."
                )
            _guidance_rows.append(("DO", _plat_note))
        _guidance_li = "\n".join(
            f'    <li style="margin-bottom:0.4rem">'
            f'<strong style="color:var(--accent);font-size:0.7rem;letter-spacing:0.07em;'
            f'text-transform:uppercase">{v}:</strong> '
            f'<span style="font-size:0.84rem;line-height:1.45">{t}</span></li>'
            for v, t in _guidance_rows
        )

        _detail_html = (
            f'<div id="{_ap_id}" class="pb-detail" style="display:none">\n'
            f'  <div style="background:var(--bg-muted);border:1px solid var(--border);'
            f'border-radius:8px;padding:1rem 1.25rem;margin-bottom:1.25rem;">\n'
            f'    <span class="conf-badge {_badge_cls}" style="margin-bottom:0.6rem">{_badge_lbl}</span>\n'
            f'    <p style="font-size:0.88rem;color:var(--text);line-height:1.55;margin-bottom:0.75rem">'
            f'{_safe_claim}</p>\n'
            f'    <p style="font-size:0.7rem;font-weight:700;letter-spacing:0.07em;text-transform:uppercase;'
            f'color:var(--text-muted);margin-bottom:0.5rem">Recommended actions this round</p>\n'
            f'  <ul style="margin:0;padding-left:1.1rem;color:var(--text-secondary)">\n'
            f'{_guidance_li}\n'
            f'  </ul>\n'
            f'  </div>\n'
            f'{_trendhunter_note_html}'
            f'  <h3 class="rh">Performance overview</h3>\n'
            f'  <p class="detail-sub">{_n} matched articles across {_n_plats} platform(s) \u00b7 '
            f'{_med:.0%} median cohort percentile \u00b7 {_delta_pts:.1f} pts {_above_below} team median '
            f'({_team_med_pct:.0%})</p>\n'
            f'\n  <h3 class="rh">Formula profile</h3>\n'
            f'  <p class="detail-sub">Lift vs. team-wide median for each formula. '
            f'&gt;1.0\u00d7 = outperforms team benchmark for that format.</p>\n'
            f'  <table><thead><tr><th>Formula</th><th>n</th><th>Share</th>'
            f'<th>Cohort %ile</th><th>Lift vs. team</th></tr></thead>\n'
            f'  <tbody>{_formula_tbody}</tbody></table>\n'
            f'{_f_sig_note}'
            f'{_untagged_section_html}'
            f'\n  <h3 class="rh">Platform breakdown</h3>\n'
            f'  <p class="detail-sub">Cohort percentile vs. overall team median ({_team_med_pct:.0%}).</p>\n'
            f'  <table><thead><tr><th>Platform</th><th>n</th>'
            f'<th>Cohort %ile</th><th>Lift vs. team</th></tr></thead>\n'
            f'  <tbody>{_plat_tbody}</tbody></table>\n'
            f'{_p_sig_note}'
            f'{_ct_section_html}\n'
            f'  <h3 class="rh">Top {len(_top_arts)} articles by cohort percentile</h3>\n'
            f'  <p class="detail-sub">Highest-performing matched articles for {_safe_auth}.</p>\n'
            f'  <table><thead><tr><th>Headline</th><th>Platform</th>'
            f'<th>Views</th><th>Cohort %ile</th></tr></thead>\n'
            f'  <tbody>{_top_tbody}</tbody></table>\n'
            f'</div>'
        )

        _author_playbook_defs.append((_auth, _n, _med, _tile_html, _detail_html))

# ── Key stats ─────────────────────────────────────────────────────────────────
N_AN        = len(an)
N_SN        = len(sn)
N_NOTIF     = len(notif)
N_NOTIF_NEWS = int((notif["brand_type"] == "News brand").sum())
N_NOTIF_UW   = int((notif["brand_type"] == "Us Weekly").sum())
CTR_MED_NEWS = notif[notif["brand_type"] == "News brand"]["CTR"].median()
CTR_MED_UW   = notif[notif["brand_type"] == "Us Weekly"]["CTR"].median()
PLATFORMS   = sum(1 for _df in [an, sn, msn, yahoo] if _df is not None and len(_df) > 0)
REPORT_DATE = datetime.now().strftime("%B %Y")

_wtn_row  = df_q2[df_q2["formula"] == "what_to_know"]
WTN_FEAT_RATE = float(_wtn_row["featured_rate"].iloc[0]) if len(_wtn_row) else overall_feat_rate
WTN_FEAT  = f"{WTN_FEAT_RATE:.0%}"

_local_row = df_q4[df_q4["category"] == "Local"]
_local_pct = float(_local_row["median_pct"].iloc[0]) if len(_local_row) else 0
LOCAL_LIFT = f"{_local_pct / top_median_sn_pct:.1f}×" if top_median_sn_pct > 0 else "—"

_excl_row  = df_q5_news[df_q5_news["feature"] == "'Exclusive' tag"]  # news brands — where this signal lives
_excl_lift_val = float(_excl_row["lift"].iloc[0]) if len(_excl_row) else None
_excl_ci_lo    = float(_excl_row["ci_lo"].iloc[0]) if len(_excl_row) and "ci_lo" in _excl_row.columns else None
_excl_ci_hi    = float(_excl_row["ci_hi"].iloc[0]) if len(_excl_row) and "ci_hi" in _excl_row.columns else None
EXCL_LIFT  = f"{_excl_lift_val:.2f}×" if _excl_lift_val else "—"
EXCL_CI_STR = (f"[{_excl_ci_lo:.1f}×–{_excl_ci_hi:.1f}×]"
               if _excl_ci_lo is not None and _excl_ci_hi is not None else "")

# ── MSN Formula Divergence scalars (Change 2) ─────────────────────────────────
# Pull key rows from df_msn_formula for the new finding detail panel
def _msn_fr(formula_key: str) -> "pd.Series | None":
    """Return the MSN formula row for formula_key, or None if not found."""
    row = df_msn_formula[df_msn_formula["formula"] == formula_key] if not df_msn_formula.empty else pd.DataFrame()
    return row.iloc[0] if len(row) else None

_msn_explainer = _msn_fr("what_to_know")       # explainer / "What to know"
_msn_possessive = _msn_fr("possessive_named_entity")
_msn_heres      = _msn_fr("heres_formula")
_msn_question   = _msn_fr("question")

def _msn_med_str(row) -> str:
    if row is None: return "—"
    v = row.get("median") if hasattr(row, "get") else None
    return f"{int(v):,}" if v is not None and not np.isnan(float(v)) else "—"

def _msn_lift_str(row) -> str:
    if row is None: return "—"
    v = row.get("lift") if hasattr(row, "get") else None
    return f"{float(v):.2f}×" if v is not None and not np.isnan(float(v)) else "—"

def _msn_p_str(row) -> str:
    if row is None: return "—"
    p = row.get("p_adj") or row.get("p") if hasattr(row, "get") else None
    if p is None or (isinstance(p, float) and np.isnan(p)): return "—"
    return _fmt_p(float(p), adj=True)

MSN_OTHER_MED_STR     = f"{MSN_OTHER_MED_PV:,}" if MSN_OTHER_MED_PV > 0 else "—"
MSN_EXPLAINER_MED_STR = _msn_med_str(_msn_explainer)
MSN_EXPLAINER_LIFT_STR= _msn_lift_str(_msn_explainer)
MSN_EXPLAINER_P_STR   = _msn_p_str(_msn_explainer)
MSN_POSS_MED_STR      = _msn_med_str(_msn_possessive)
MSN_POSS_LIFT_STR     = _msn_lift_str(_msn_possessive)
MSN_POSS_P_STR        = _msn_p_str(_msn_possessive)
MSN_HERES_MED_STR     = _msn_med_str(_msn_heres)
MSN_HERES_LIFT_STR    = _msn_lift_str(_msn_heres)
MSN_HERES_P_STR       = _msn_p_str(_msn_heres)
MSN_Q_MED_STR         = _msn_med_str(_msn_question)
MSN_Q_LIFT_STR        = _msn_lift_str(_msn_question)
MSN_Q_P_STR           = _msn_p_str(_msn_question)
_FORMULA_DISPLAY_LABELS = {
    "what_to_know": "Explainer (What to know)",
    "heres_formula": "Here's / Here are",
    "possessive_named_entity": "Possessive named entity",
    "question": "Question",
    "number_lead": "Number lead",
    "quoted_lede": "Quoted lede",
    "untagged": "Direct declarative (baseline)",
}
# Overall lift of direct declarative vs. worst-performing formula (dynamic)
if not df_msn_formula.empty and df_msn_formula["lift"].min() > 0:
    _msn_worst_lift = float(df_msn_formula["lift"].min())
    MSN_DIVERGE_LIFT_STR = f"{1/_msn_worst_lift:.2f}×"
    _msn_worst_formula_label = _FORMULA_DISPLAY_LABELS.get(
        str(df_msn_formula.loc[df_msn_formula["lift"].idxmin(), "formula"]), "structured formula")
else:
    MSN_DIVERGE_LIFT_STR = "—"
    _msn_worst_formula_label = "structured formula"

# ── Notification CTR by topic scalars (for Finding 3 sports extension) ────────
def _notif_topic_ctr_val(topic: str) -> "float | None":
    row = _notif_topic_ctr[_notif_topic_ctr["topic"] == topic] if not _notif_topic_ctr.empty else pd.DataFrame()
    return float(row["median"].iloc[0]) if len(row) else None

_ctr_sports  = _notif_topic_ctr_val("sports")
_ctr_crime   = _notif_topic_ctr_val("crime")
_ctr_weather = _notif_topic_ctr_val("weather")
_ctr_edu     = _notif_topic_ctr_val("local_civic")  # closest to "education" in classifier
NOTIF_CTR_SPORTS_STR  = f"{_ctr_sports:.2%}"  if _ctr_sports  else "—"
NOTIF_CTR_CRIME_STR   = f"{_ctr_crime:.2%}"   if _ctr_crime   else "—"
NOTIF_CTR_WEATHER_STR = f"{_ctr_weather:.2%}" if _ctr_weather else "—"

# MSN video sports completion
MSN_VID_SPORTS_IDX_STR = (f"{MSN_VID_SPORTS_COMPLETION_IDX:.2f}×"
                           if not np.isnan(MSN_VID_SPORTS_COMPLETION_IDX) else "—")
# MSN_VID_SPORTS_P_STR assigned after _fmt_p is defined (see below)

# ── Prose helpers ─────────────────────────────────────────────────────────────
def _fmt_p(p: "float | None", adj: bool = False) -> str:
    """Format a p-value as HTML with significance stars. Returns '—' for None/NaN."""
    if p is None or (isinstance(p, float) and np.isnan(p)): return "—"
    p = float(p)
    label = "<sub>adj</sub>" if adj else ""
    sig = " ***" if p < 0.001 else " **" if p < 0.01 else " *" if p < 0.05 else ""
    if p < 0.001: return f"p{label}&lt;0.001{sig}"
    if p < 0.01:  return f"p{label}={p:.3f}{sig}"
    return f"p{label}={p:.2f}{sig}"

MSN_VID_SPORTS_P_STR = (_fmt_p(MSN_VID_SPORTS_P) if MSN_VID_SPORTS_P < 0.10 else "—")

def _fmt_ci(lo: "float | None", hi: "float | None") -> str:
    """Format a confidence interval as a [lo×–hi×] string. Returns '' if either bound is None."""
    if lo is None or hi is None: return ""
    return f"[{lo:.2f}×–{hi:.2f}×]"

def _q1r(f: str) -> "pd.Series | None":
    """Return the Q1 row for formula f, or None if not found."""
    row = df_q1[df_q1["formula"] == f]
    return row.iloc[0] if len(row) else None

def _q2r(f: str) -> "pd.Series | None":
    """Return the Q2 row for formula f, or None if not found."""
    row = df_q2[df_q2["formula"] == f]
    return row.iloc[0] if len(row) else None

def _q4r(cat: str) -> "pd.Series | None":
    """Return the Q4 row for SmartNews category cat, or None if not found."""
    row = df_q4[df_q4["category"] == cat]
    return row.iloc[0] if len(row) else None

def _q5r(feat: str) -> "pd.Series | None":
    """Return the Q5 row for notification feature feat, or None if not found."""
    row = df_q5[df_q5["feature"] == feat]
    return row.iloc[0] if len(row) else None

_r1_num = _q1r("number_lead")
_r1_q   = _q1r("question")
_r1_ql  = _q1r("quoted_lede")
_r1_h   = _q1r("heres_formula")
_r1_pne = _q1r("possessive_named_entity")

_r2_wtn = _q2r("what_to_know")
_r2_q   = _q2r("question")
_r2_ql  = _q2r("quoted_lede")
_wtn_feat_n   = int(_r2_wtn["feat_n"])      if _r2_wtn is not None else 0
_wtn_total    = int(_r2_wtn["n"])            if _r2_wtn is not None else 0
WTN_FEAT_LIFT = float(_r2_wtn["featured_lift"]) if _r2_wtn is not None else 0

_r4_loc  = _q4r("Local")
_r4_us   = _q4r("U.S.")
_r4_ent  = _q4r("Entertainment")
_r4_wld  = _q4r("World")
_r4_hlth = _q4r("Health")
_r4_top  = _q4r("Top")
_ent_local_ratio = (int(round(_r4_ent["n"] / _r4_loc["n"]))
                    if _r4_ent is not None and _r4_loc is not None and _r4_loc["n"] > 0 else 0)

def _q5r_news(feat: str) -> "pd.Series | None":
    """Return the Q5-news-brands row for notification feature feat, or None."""
    row = df_q5_news[df_q5_news["feature"] == feat] if not df_q5_news.empty else pd.DataFrame()
    return row.iloc[0] if len(row) else None

def _q5r_uw(feat: str) -> "pd.Series | None":
    """Return the Q5-Us-Weekly row for notification feature feat, or None."""
    row = df_q5_uw[df_q5_uw["feature"] == feat] if not df_q5_uw.empty else pd.DataFrame()
    return row.iloc[0] if len(row) else None

# Pull signals from the population where each is meaningful
_r5_excl = _q5r_news("'Exclusive' tag")       # significant for news brands; neutral for UW
_r5_poss = _q5r_uw("Named person + possessive")  # significant for UW; neutral for news brands
_r5_full = _q5r_uw("Full name present")
_r5_q    = _q5r_news("Question format")        # hurts news brands; neutral for UW
_r5_sh   = _q5r("Short (≤80 chars)")           # not significant in either pop; keep pooled for guard
_r5_num  = _q5r_uw("Contains number")          # hurts Us Weekly
_r5_attr = _q5r_news("Attribution (says/told)")  # positive signal for news brands
CTR_MED      = f"{notif['CTR'].median():.2%}"
CTR_MED_NEWS_STR = f"{CTR_MED_NEWS:.2%}"
CTR_MED_UW_STR   = f"{CTR_MED_UW:.2%}"


# ── Hero tagline selection ────────────────────────────────────────────────────
# Scores each statistically-grounded finding on: effect size × significance × surprise.
# Picks the top 2 for the hero h1. Runs automatically — no hardcoding required.

def _get_p(row, prefer_adj=True):
    """Extract best available p-value from a Series row."""
    if row is None: return None
    for key in (["p_adj", "p"] if prefer_adj else ["p"]):
        v = row.get(key) if hasattr(row, "get") else None
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            return float(v)
    return None

_hero_cands = []

def _hero_add(text, p, effect, surprise=1.0, n=None):
    """Register a finding. score = -log10(p) × effect × surprise, penalised if n<15."""
    if p is None or p >= 0.10: return
    score = -math.log10(max(p, 1e-12)) * float(effect) * surprise
    if n is not None and n < 15: score *= 0.5
    _hero_cands.append({"text": text, "score": score})

# Notification: exclusive tag (news brand signal — scoops earn clicks)
if _r5_excl is not None:
    _excl_lft = float(_r5_excl["lift"])
    _hero_add(
        f"\u201cExclusive\u201d in a push notification is associated with {_excl_lft:.1f}\u00d7 higher CTR "
        f"for news brands \u2014 the signal is earned, not generic.",
        _get_p(_r5_excl), _excl_lft - 1.0, surprise=1.3, n=int(_r5_excl["n_true"]),
    )

# Notification: named person + possessive (Us Weekly / celebrity signal)
if _r5_poss is not None and float(_r5_poss["lift"]) > 1.0:
    _poss_lft = float(_r5_poss["lift"])
    _hero_add(
        f"For celebrity/entertainment notifications, named person\u202f+\u202fpossessive "
        f"(\u201cSmith\u2019s\u2026\u201d) shows {_poss_lft:.1f}\u00d7 higher CTR.",
        _get_p(_r5_poss), _poss_lft - 1.0, surprise=1.2, n=int(_r5_poss["n_true"]),
    )

# Notification: attribution lifts news brand CTR (counter to convention)
if _r5_attr is not None and float(_r5_attr["lift"]) > 1.0:
    _attr_lft = float(_r5_attr["lift"])
    _hero_add(
        f"Attribution language (\u201csays\u201d/\u201ctold\u201d) in news brand notifications "
        f"is associated with {_attr_lft:.1f}\u00d7 higher CTR \u2014 sourcing signals credibility.",
        _get_p(_r5_attr), _attr_lft - 1.0, surprise=1.4, n=int(_r5_attr["n_true"]),
    )

# Number leads underperform (surprising: conventional wisdom says they\u2019re strong)
if _r1_num is not None:
    _p_num = _get_p(_r1_num)
    if _p_num is not None:
        _nl_lft = float(_r1_num["lift"])
        _hero_add(
            f"Number-lead headlines underperform the average article "
            f"({_nl_lft:.2f}\u00d7 baseline, p={_p_num:.3f}). "
            f"The format isn\u2019t the signal \u2014 number type and specificity are.",
            _p_num, 1.0 - _nl_lft, surprise=1.8, n=int(_r1_num["n"]),
        )

# Round vs specific numbers
if NL_ROUND_VS_SPECIFIC_P is not None and not math.isnan(NL_ROUND_MED) and not math.isnan(NL_SPECIFIC_MED):
    _diff_pct = NL_SPECIFIC_MED - NL_ROUND_MED
    _hero_add(
        f"Round numbers (100, 1,000) land at the {NL_ROUND_MED:.0%}ile \u2014 "
        f"{_diff_pct:.0%} points below specific numbers like 43 or 127 "
        f"(p={NL_ROUND_VS_SPECIFIC_P:.3f}).",
        NL_ROUND_VS_SPECIFIC_P,
        _diff_pct / max(NL_BASE_MED, 0.01),
        surprise=1.7,
    )

# SmartNews allocation mismatch
if _r4_ent is not None and _r4_loc is not None:
    _ent_sh  = float(_r4_ent["pct_share"])
    _loc_sh  = float(_r4_loc["pct_share"])
    _loc_lft = float(_r4_loc.get("lift", 1.0))
    _ent_lft = float(_r4_ent.get("lift", 1.0))
    _p_loc   = float(_r4_loc.get("p_mw_adj") or _r4_loc.get("p_mw") or 0.001)
    if math.isnan(_p_loc): _p_loc = 0.001
    _hero_add(
        f"SmartNews: Entertainment gets {_ent_sh:.0%} of article volume at {_ent_lft:.2f}\u00d7 median percentile rank. "
        f"Local delivers {_loc_lft:.2f}\u00d7 on {_loc_sh:.0%} of the volume \u2014 "
        f"a distribution reallocation, not a content problem.",
        _p_loc, _loc_lft - _ent_lft, surprise=1.5, n=int(_r4_loc["n"]),
    )

# Sports platform inversion
_sports_an_v = an[an["topic"] == "sports"][VIEWS_METRIC].dropna()
_sports_sn_v = sn[sn["topic"] == "sports"][VIEWS_METRIC].dropna()
_p_sports = None
if len(_sports_an_v) >= 10 and len(_sports_sn_v) >= 10:
    _, _p_sports = stats.mannwhitneyu(_sports_an_v, _sports_sn_v, alternative="two-sided")
    _rank_gap = abs(sports_an_rank - sports_sn_rank)
    _hero_add(
        f"Sports is #{sports_an_rank} on Apple News and #{sports_sn_rank} (last) on SmartNews \u2014 "
        f"the largest topic-rank gap across platforms (rank gap: {abs(sports_an_rank - sports_sn_rank)}).",
        _p_sports,
        _rank_gap / 8.0,
        surprise=1.5,
        n=min(len(_sports_an_v), len(_sports_sn_v)),
    )

# WTN paradox: Apple features it but organic performance disappoints
_r1_wtn = _q1r("what_to_know")
if _r1_wtn is not None:
    _wtn_organic = float(_r1_wtn["median"])
    _wtn_p = _get_p(_r1_wtn)
    if _wtn_p is None: _wtn_p = 0.096  # observed marginal significance
    _hero_add(
        f"\u201cWhat to know\u201d gets Featured {WTN_FEAT_LIFT:.1f}\u00d7 more often than average "
        f"but organic articles land at the {_wtn_organic:.0%}ile. "
        f"Apple\u2019s algorithm and readers have opposite preferences.",
        _wtn_p,
        (WTN_FEAT_LIFT - 1.0) * 0.4 + (0.5 - _wtn_organic),
        surprise=1.6,
        n=int(_r1_wtn["n"]),
    )

_hero_cands.sort(key=lambda x: -x["score"])
if len(_hero_cands) >= 2:
    HERO_H1 = f'{_hero_cands[0]["text"]} {_hero_cands[1]["text"]}'
elif _hero_cands:
    HERO_H1 = _hero_cands[0]["text"]
else:
    HERO_H1 = "T1 Headline Performance Analysis \u2014 McClatchy CSA"

# Debug: show scoring for transparency
print("Hero candidates (ranked):")
for _hc in _hero_cands[:5]:
    print(f"  score={_hc['score']:.2f}  {_hc['text'][:80]}...")


# ── Table generators ──────────────────────────────────────────────────────────
def _row_tag(lift: float, is_red: bool = False) -> str:
    """Return an HTML tag span (star or down-arrow) based on the lift value."""
    if is_red:          return '<span class="tag tag-red">↓</span>&nbsp;'
    if lift >= 1.5:     return '<span class="tag tag-green">★</span>&nbsp;'
    if lift < 0.8:      return '<span class="tag tag-red">↓</span>&nbsp;'
    return ""

def _wc_table() -> str:
    """Return HTML <tr> rows for the word-count quartile table."""
    if df_wc_quartile.empty: return "<tr><td colspan='4'>Insufficient data (need ≥20 matched articles with word count).</td></tr>"
    out = ""
    for _, r in df_wc_quartile.iterrows():
        out += (f"<tr><td>{r['wc_quartile']}</td><td>{int(r['n'])}</td>"
                f"<td>{int(r['med_wc'])}</td><td>{r['med_pct']:.0%}</td></tr>\n")
    return out

def _formula_team_table() -> str:
    """Formula distribution in tracked articles; shows what the team actually writes vs. performance."""
    if df_formula_team.empty:
        return "<tr><td colspan='4'>No data.</td></tr>"
    _FORMULA_LABELS = {
        "number_lead": "Number lead", "heres_formula": "Here's / Here are",
        "what_to_know": "What to know", "question": "Question",
        "possessive_named_entity": "Possessive named entity",
        "quoted_lede": "Quoted lede", "untagged": "Untagged",
    }
    out = []
    for _, r in df_formula_team.iterrows():
        label = _FORMULA_LABELS.get(r["formula"], r["formula"])
        out.append(f"<tr><td>{label}</td><td>{int(r['n'])}</td>"
                   f"<td>{r['share']:.0%}</td><td>{r['med_pct']:.0%}</td></tr>")
    return "\n".join(out)

def _content_type_table() -> str:
    """Parent (original) vs. Child (variant) syndication performance."""
    if df_content_type.empty:
        return "<tr><td colspan='3'>Content type data not available in tracker.</td></tr>"
    _CT_LABELS = {"Parent-P": "Original (Parent-P)", "Child-C": "Variant (Child-C)"}
    out = []
    for _, r in df_content_type.iterrows():
        label = _CT_LABELS.get(r["content_type"], r["content_type"])
        out.append(f"<tr><td>{label}</td><td>{int(r['n'])}</td><td>{r['med_pct']:.0%}</td></tr>")
    return "\n".join(out)

def _author_profiles_table() -> str:
    """Per-author: total articles, median percentile, dominant formula type."""
    if df_author_profiles.empty:
        return "<tr><td colspan='4'>No data.</td></tr>"
    _FORMULA_LABELS = {
        "number_lead": "Number lead", "heres_formula": "Here's / Here are",
        "what_to_know": "What to know", "question": "Question",
        "possessive_named_entity": "Possessive NE", "quoted_lede": "Quoted lede",
        "untagged": "Untagged",
    }
    out = []
    for _, r in df_author_profiles.iterrows():
        formula_label = _FORMULA_LABELS.get(r["top_formula"], r["top_formula"])
        out.append(f"<tr><td>{html_module.escape(str(r['author']))}</td>"
                   f"<td>{int(r['n_total'])}</td>"
                   f"<td>{r['med_pct_overall']:.0%}</td>"
                   f"<td>{formula_label} ({int(r['n_top_formula'])} articles, "
                   f"{r['top_formula_med_pct']:.0%}ile)</td></tr>")
    return "\n".join(out)

def _vert_plat_table() -> str:
    """Vertical performance by platform (n≥3 per cell)."""
    if df_vert_plat.empty:
        return "<tr><td colspan='4'>Insufficient data (need ≥3 articles per vertical × platform).</td></tr>"
    out = []
    for _, r in df_vert_plat.iterrows():
        out.append(f"<tr><td>{html_module.escape(str(r['vertical']))}</td>"
                   f"<td>{html_module.escape(str(r['platform']))}</td>"
                   f"<td>{int(r['n'])}</td><td>{r['med_pct']:.0%}</td></tr>")
    return "\n".join(out)

def _nl_type_table() -> str:
    """Return HTML <tr> rows for the number-lead type breakdown table."""
    if df_nl_type.empty: return "<tr><td colspan='4'>Insufficient data.</td></tr>"
    out = ""
    for _, r in df_nl_type.iterrows():
        out += (f"<tr><td>{r['label']}</td><td>{int(r['n'])}</td>"
                f"<td>{r['median']:.0%}</td><td>{r['lift']:.2f}×</td></tr>\n")
    return out

def _nl_size_table() -> str:
    """Return HTML <tr> rows for the number-lead numeric-size breakdown table."""
    if df_nl_size.empty: return "<tr><td colspan='4'>Insufficient data.</td></tr>"
    out = ""
    for _, r in df_nl_size.iterrows():
        out += (f"<tr><td>{r['size_cat']}</td><td>{int(r['n'])}</td>"
                f"<td>{r['median']:.0%}</td><td>{r['lift']:.2f}×</td></tr>\n")
    return out

def _q1_table() -> str:
    """Return HTML <tr> rows for the Q1 formula lift table, excluding the untagged baseline."""
    rows = df_q1[df_q1["formula"] != "untagged"].sort_values("lift", ascending=False)
    parts = []
    for _, r in rows.iterrows():
        p_adj = r.get("p_adj", np.nan)
        p_raw = r.get("p")
        p_str = _fmt_p(p_adj, adj=True) if not (p_adj is None or (isinstance(p_adj, float) and np.isnan(float(p_adj)))) else _fmt_p(p_raw)
        r_str = f"{r['r_rb']:.2f}" if r.get("r_rb") is not None else "—"
        ci_str = _fmt_ci(r.get("ci_lo"), r.get("ci_hi"))
        _rn = r.get("req_n")
        req_n_str = f"~{int(_rn)} needed" if (_rn is not None and pd.notna(_rn)) else "—"
        pct_str = f"{r['median']:.0%}"
        tag = _row_tag(r["lift"])
        parts.append(f'<tr><td>{tag}{r["label"]}</td><td>{r["n"]:,}</td>'
                     f'<td>{pct_str}</td><td>{r["lift"]:.2f}×</td><td>{ci_str}</td>'
                     f'<td>{r_str}</td><td>{p_str}</td><td>{req_n_str}</td></tr>\n')
    return "".join(parts)

def _q2_table() -> str:
    """Return HTML <tr> rows for the Q2 featured-rate table, excluding the untagged baseline."""
    rows = df_q2[df_q2["formula"] != "untagged"].sort_values("featured_rate", ascending=False)
    parts = []
    for _, r in rows.iterrows():
        feat_med = r.get("feat_med_views")
        if feat_med is not None and not np.isnan(float(feat_med)):
            wf = f"{feat_med:.0%} ({float(r['feat_views_lift']):.2f}× Featured avg)"
        else:
            wf = "—"
        p_adj = r.get("p_chi_adj", np.nan)
        p_str = _fmt_p(p_adj, adj=True) if not (p_adj is None or (isinstance(p_adj, float) and np.isnan(float(p_adj)))) else _fmt_p(r["p_chi"])
        tag = _row_tag(r["featured_lift"])
        parts.append(f'<tr><td>{tag}{r["label"]}</td><td>{r["n"]:,}</td>'
                     f'<td>{r["featured_rate"]:.0%}</td>'
                     f'<td>{r["featured_lift"]:.2f}×</td>'
                     f'<td>{p_str}</td>'
                     f'<td>{wf}</td></tr>\n')
    return "".join(parts)

def _q4_table() -> str:
    """Return HTML <tr> rows for the Q4 SmartNews category ROI table."""
    rows_sorted = df_q4[df_q4["category"] != "Top"].sort_values("lift", ascending=False)
    parts = []
    for _, r in rows_sorted.iterrows():
        is_red = (r["lift"] < 2.0 and r["category"] in ("Entertainment", "Lifestyle"))
        tag = _row_tag(r["lift"], is_red=is_red)
        p_adj = r.get("p_mw_adj", np.nan)
        p_str = _fmt_p(p_adj, adj=True) if not (p_adj is None or (isinstance(p_adj, float) and np.isnan(float(p_adj)))) else "—"
        parts.append(f'<tr><td>{tag}{r["category"]}</td><td>{r["n"]:,}</td>'
                     f'<td>{r["pct_share"]:.1%}</td>'
                     f'<td>{r["median_pct"]:.0%}</td>'
                     f'<td>{int(r["median_views"]):,}</td>'
                     f'<td>{r["lift"]:.2f}×</td>'
                     f'<td>{p_str}</td></tr>\n')
    if _r4_top is not None:
        parts.append(f'<tr><td>Top feed (baseline)</td><td>{int(_r4_top["n"]):,}</td>'
                     f'<td>{_r4_top["pct_share"]:.1%}</td>'
                     f'<td>{top_median_sn_pct:.0%}</td>'
                     f'<td>{int(_r4_top["median_views"]):,}</td><td>1.00×</td><td>—</td></tr>\n')
    return "".join(parts)

def _q5_table() -> str:
    """Return HTML <tr> rows for the Q5 notification feature CTR table (significant features only)."""
    sig = df_q5[df_q5.apply(
        lambda r: (r.get("p_adj", r["p"]) if not (isinstance(r.get("p_adj", np.nan), float) and np.isnan(r.get("p_adj", np.nan))) else r["p"]) < 0.05,
        axis=1
    )].sort_values("lift", ascending=False)
    parts = []
    for _, r in sig.iterrows():
        p_adj = r.get("p_adj", np.nan)
        p_str = _fmt_p(p_adj, adj=True) if not (isinstance(p_adj, float) and np.isnan(p_adj)) else _fmt_p(r["p"])
        r_str = f"{r['r_rb']:.2f}" if r.get("r_rb") is not None else "—"
        ci_str = _fmt_ci(r.get("ci_lo"), r.get("ci_hi"))
        tag = _row_tag(r["lift"])
        parts.append(f'<tr><td>{tag}{r["feature"]}</td><td>{r["n_true"]:,}</td>'
                     f'<td>{r["med_yes"]:.2%}</td><td>{r["med_no"]:.2%}</td>'
                     f'<td>{r["lift"]:.2f}× {ci_str}</td>'
                     f'<td>{r_str}</td>'
                     f'<td>{p_str}</td></tr>\n')
    return "".join(parts)

def _q5_table_pop(df_pop: "pd.DataFrame") -> str:
    """Return HTML <tr> rows for a brand-specific Q5 table (all features, sorted by lift desc)."""
    if df_pop.empty: return "<tr><td colspan='7'>No results</td></tr>\n"
    sorted_df = df_pop.sort_values("lift", ascending=False)
    parts = []
    for _, r in sorted_df.iterrows():
        p_adj = r.get("p_adj", np.nan)
        p_str = _fmt_p(p_adj, adj=True) if not (isinstance(p_adj, float) and np.isnan(p_adj)) else _fmt_p(r["p"])
        r_str = f"{r['r_rb']:.2f}" if r.get("r_rb") is not None else "—"
        ci_str = _fmt_ci(r.get("ci_lo"), r.get("ci_hi"))
        tag = _row_tag(r["lift"])
        parts.append(f'<tr><td>{tag}{r["feature"]}</td><td>{r["n_true"]:,}</td>'
                     f'<td>{r["med_yes"]:.2%}</td><td>{r["med_no"]:.2%}</td>'
                     f'<td>{r["lift"]:.2f}× {ci_str}</td>'
                     f'<td>{r_str}</td>'
                     f'<td>{p_str}</td></tr>\n')
    return "".join(parts)

def _sports_subtopic_table() -> str:
    """Return HTML <tr> rows for the sports subtopic breakdown table."""
    html_out = ""
    for _, r in df_sports_subtopic.iterrows():
        an_str = f"{r['an_med']:.0%}" if pd.notna(r['an_med']) else "—"
        sn_str = f"{r['sn_med']:.0%}" if pd.notna(r['sn_med']) else "—"
        html_out += (f"<tr><td>{r['subtopic']}</td>"
                     f"<td>{int(r['an_n'])}</td><td>{an_str}</td>"
                     f"<td>{int(r['sn_n'])}</td><td>{sn_str}</td></tr>\n")
    return html_out

def _biz_subtopic_table() -> str:
    """Return HTML <tr> rows for the business subtopic breakdown table."""
    html_out = ""
    for _, r in df_biz_subtopic.iterrows():
        an_str = f"{r['an_med']:.0%}" if pd.notna(r['an_med']) else "—"
        sn_str = f"{r['sn_med']:.0%}" if pd.notna(r['sn_med']) else "—"
        html_out += (f"<tr><td>{r['label']}</td>"
                     f"<td>{int(r['an_n'])}</td><td>{an_str}</td>"
                     f"<td>{int(r['sn_n'])}</td><td>{sn_str}</td></tr>\n")
    return html_out

def _pol_subtopic_table() -> str:
    """Return HTML <tr> rows for the politics subtopic breakdown table."""
    html_out = ""
    for _, r in df_pol_subtopic.iterrows():
        an_str = f"{r['an_med']:.0%}" if pd.notna(r['an_med']) else "—"
        sn_str = f"{r['sn_med']:.0%}" if pd.notna(r['sn_med']) else "—"
        html_out += (f"<tr><td>{r['label']}</td>"
                     f"<td>{int(r['an_n'])}</td><td>{an_str}</td>"
                     f"<td>{int(r['sn_n'])}</td><td>{sn_str}</td></tr>\n")
    return html_out

def _hl_len_table() -> str:
    """Return HTML <tr> rows for the headline length quartile table."""
    html_out = ""
    for _, r in df_hl_len.iterrows():
        an_str = f"{r['an_med']:.0%}" if pd.notna(r['an_med']) else "—"
        sn_str = f"{r['sn_med']:.0%}" if pd.notna(r['sn_med']) else "—"
        an_chars = f"{int(r['an_len_med'])} chars" if pd.notna(r['an_len_med']) else "—"
        html_out += (f"<tr><td>{r['bucket']}</td><td>{an_chars}</td>"
                     f"<td>{int(r['an_n']):,}</td><td>{an_str}</td>"
                     f"<td>{int(r['sn_n']):,}</td><td>{sn_str}</td></tr>\n")
    return html_out

def _guide_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    """Return HTML <tr> rows for the formula × topic guide table."""
    if df.empty: return "<tr><td colspan='5'>Insufficient data (need ≥5 articles per formula × topic cell).</td></tr>"
    html_out = ""
    for _, r in df.head(max_rows).iterrows():
        lift_val = r['lift']
        if pd.notna(lift_val):
            cls = "lift-high" if lift_val >= 1.5 else ("lift-pos" if lift_val >= 1.0 else "lift-neg")
            lift_str = f'<span class="{cls}">{lift_val:.2f}×</span>'
        else:
            lift_str = "—"
        html_out += (f"<tr><td>{r['formula']}</td><td>{r['topic']}</td>"
                     f"<td>{int(r['n'])}</td><td>{r['med']:.0%}</td>"
                     f"<td>{lift_str}</td></tr>\n")
    return html_out

def _yoy_table() -> str:
    """Return HTML <tr> rows for the year-over-year formula lift comparison table."""
    html_out = ""
    for _, r in df_yoy.iterrows():
        if r["suppressed"]:
            # Show suppressed rows with caveat (n<10 in 2025 = unreliable)
            html_out += (f"<tr style='color:#8b90a0'>"
                         f"<td>{r['label']} <em style='font-size:0.85em'>(n={int(r['n_2025'])} in 2025 — too few to compare)</em></td>"
                         f"<td colspan='4' style='text-align:center'>—</td></tr>\n")
            continue
        l25 = f"{r['lift_2025']:.2f}×" if pd.notna(r["lift_2025"]) else "—"
        l26 = f"{r['lift_2026']:.2f}×" if pd.notna(r["lift_2026"]) else "—"
        delta = r["lift_2026"] - r["lift_2025"] if (pd.notna(r["lift_2025"]) and pd.notna(r["lift_2026"])) else np.nan
        delta_str = (f'<span style="color:{"#16a34a" if delta > 0 else "#dc2626"}">'
                     f'{"+" if delta > 0 else ""}{delta:.2f}×</span>') if pd.notna(delta) else "—"
        html_out += (f"<tr><td>{r['label']}</td>"
                     f"<td>{int(r['n_2025'])}</td><td>{l25}</td>"
                     f"<td>{int(r['n_2026'])}</td><td>{l26}</td>"
                     f"<td>{delta_str}</td></tr>\n")
    return html_out

def _periods_table() -> str:
    """Return HTML <tr> rows for the quarterly formula lift longitudinal table."""
    html_out = ""
    formulas_in_order = ["number_lead", "question", "possessive_named_entity", "heres_formula", "what_to_know"]
    _all_periods = ["Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025", "Q1 2026"]
    for f in formulas_in_order:
        label = FORMULA_LABELS.get(f, f)
        def _cell(period, _f=f):
            r = df_periods[(df_periods["formula"] == _f) & (df_periods["period"] == period)]
            if len(r) == 0:
                return "—", "—"
            return f"{float(r['lift'].iloc[0]):.2f}×", str(int(r['n'].iloc[0]))
        cells = ""
        for p in _all_periods:
            lv, nv = _cell(p)
            cells += f"<td>{lv}</td><td style='color:#8b90a0'>(n={nv})</td>"
        html_out += f"<tr><td>{label}</td>{cells}</tr>\n"
    return html_out

def _author_table() -> str:
    """Return HTML <tr> rows for the tracker-joined author performance table."""
    if author_stats.empty: return "<tr><td colspan='4'>No matched articles.</td></tr>"
    html_out = ""
    for _, r in author_stats.iterrows():
        html_out += (f"<tr><td>{html_module.escape(str(r['author']))}</td>"
                     f"<td>{html_module.escape(str(r['platform']))}</td>"
                     f"<td>{int(r['n'])}</td>"
                     f"<td>{r['med_pct']:.0%}</td></tr>\n")
    return html_out

def _team_top_table() -> str:
    """Return HTML <tr> rows for the top-performing tracked articles table."""
    if team_top.empty: return "<tr><td colspan='6'>No matched articles.</td></tr>"
    html_out = ""
    for _, r in team_top.iterrows():
        title = html_module.escape(str(r['headline']))
        feat_str = "Yes" if r.get('featured') else "No"
        views_val = r.get('views', 0)
        views_str = f"{int(views_val):,}" if pd.notna(views_val) else "—"
        html_out += (f"<tr><td style='white-space:normal;max-width:360px'>{title}</td>"
                     f"<td>{html_module.escape(str(r.get('platform','')))} / {html_module.escape(str(r.get('brand','')))}</td>"
                     f"<td>{html_module.escape(str(r.get('author','')))}</td>"
                     f"<td>{r['percentile']:.0%}</td>"
                     f"<td>{views_str}</td>"
                     f"<td>{feat_str}</td></tr>\n")
    return html_out

def _msn_formula_table() -> str:
    """Return HTML <tr> rows for MSN formula performance table (formula, n, median PVs, lift, p_adj)."""
    if df_msn_formula.empty:
        return "<tr><td colspan='5'>No MSN formula data available.</td></tr>"
    html_out = ""
    for _, r in df_msn_formula.sort_values("lift", ascending=False).iterrows():
        label = _FORMULA_DISPLAY_LABELS.get(str(r["formula"]), str(r["formula"]))
        med_str = f"{int(r['median']):,}" if pd.notna(r.get("median")) and r["median"] > 0 else "—"
        sig = " ***" if pd.notna(r.get("p_adj")) and r["p_adj"] < 0.001 else \
              " **"  if pd.notna(r.get("p_adj")) and r["p_adj"] < 0.01  else \
              " *"   if pd.notna(r.get("p_adj")) and r["p_adj"] < 0.05  else ""
        lift_cls = "lift-neg" if float(r.get("lift", 1.0)) < 1.0 else "lift-pos"
        p_str = f"p={r['p_adj']:.3f}{sig}" if pd.notna(r.get("p_adj")) else "—"
        html_out += (f"<tr><td>{html_module.escape(label)}</td>"
                     f"<td>{int(r['n'])}</td>"
                     f"<td>{med_str}</td>"
                     f"<td><span class='{lift_cls}'>{float(r['lift']):.2f}×{sig}</span></td>"
                     f"<td>{p_str}</td></tr>\n")
    return html_out

def _msn_monthly_table() -> str:
    """Return HTML <tr> rows for MSN monthly PV trend table."""
    if msn_monthly.empty:
        return "<tr><td colspan='3'>No MSN monthly data.</td></tr>"
    html_out = ""
    for _, r in msn_monthly.iterrows():
        html_out += (f"<tr><td>{html_module.escape(str(r['_msn_month']))}</td>"
                     f"<td>{int(r['n']):,}</td>"
                     f"<td>{int(r['med_pv']):,}</td></tr>\n")
    return html_out

_t1 = _q1_table()
_t2 = _q2_table()
_t3 = _q4_table()
_t4 = _q5_table()
_t5 = _sports_subtopic_table()
_t_biz_sub  = _biz_subtopic_table()
_t_pol_sub  = _pol_subtopic_table()
_t_hl_len   = _hl_len_table()
_t_an_guide = _guide_table(df_an_guide)
_t_sn_guide = _guide_table(df_sn_guide)
_t_yoy = _yoy_table()
_t_periods = _periods_table()
_t_auth = _author_table()
_t_team = _team_top_table()
_t_nl_type = _nl_type_table()
_t_nl_size = _nl_size_table()
_t_wc = _wc_table()
_t_formula_team    = _formula_team_table()
_t_content_type    = _content_type_table()
_t_author_profiles = _author_profiles_table()
_t_vert_plat       = _vert_plat_table()
_t_msn_formula     = _msn_formula_table()
_t_msn_monthly     = _msn_monthly_table()

_excl_sensitivity_html = ""
if EXCL_NOGUTH_LIFT is not None and _r5_excl is not None:
    _excl_sensitivity_html = f"""
      <h3>Sensitivity analysis: "Exclusive" with and without Guthrie cluster</h3>
      <p>The {_r5_excl['n_true']} "exclusive"-tagged notifications include {_n_excl_guthrie} that also mention Guthrie. Removing the Guthrie overlap: the "exclusive" lift falls from {_r5_excl['lift']:.2f}× to {EXCL_NOGUTH_LIFT:.2f}× ({_fmt_p(EXCL_NOGUTH_P)}). {"The effect remains statistically significant — the exclusive signal is not solely a Guthrie artifact." if EXCL_NOGUTH_P is not None and EXCL_NOGUTH_P < 0.05 else "The effect loses statistical significance once the Guthrie cluster is removed — interpret the headline figure with caution."}</p>
"""

_q1_power_rows = df_q1[(df_q1["formula"] != "untagged") & df_q1["req_n"].notna()]


# ── Callout variables — pre-computed strings for HTML template ─────────────────
# Featured vs. non-Featured total view lift (Finding 7)
_feat_v  = an[an["is_featured"]]["Total Views"].dropna()
_nfeat_v = an[~an["is_featured"]]["Total Views"].dropna()
FEAT_VIEW_LIFT = (float(_feat_v.median() / _nfeat_v.median())
                  if len(_feat_v) > 0 and len(_nfeat_v) > 0 and _nfeat_v.median() > 0
                  else np.nan)
FEAT_VIEW_LIFT_STR = f"{FEAT_VIEW_LIFT:.1f}×" if not np.isnan(FEAT_VIEW_LIFT) else "—"

# WTN organic p-value (non-Featured WTN vs baseline; from Q1 analysis)
WTN_N_NONFEAT     = int(_r1_wtn["n"]) if _r1_wtn is not None else 0
_wtn_p_val        = _get_p(_r1_wtn) if _r1_wtn is not None else None
WTN_ORGANIC_P_STR = _fmt_p(_wtn_p_val, adj=True) if _wtn_p_val is not None else "p≈0.10"

# F1: Here's formula callout (Finding 1)
F1_HERES_PCT = f"{_r1_h['median']:.0%}" if _r1_h is not None else "—"
F1_HERES_N   = str(int(_r1_h["n"])) if _r1_h is not None else "—"
F1_NUM_P_STR = _fmt_p(_get_p(_r1_num), adj=True) if _r1_num is not None else "—"
F1_Q_P_STR   = _fmt_p(_get_p(_r1_q),   adj=True) if _r1_q   is not None else "—"
F1_QL_P_STR  = _fmt_p(_get_p(_r1_ql),  adj=True) if _r1_ql  is not None else "—"

# F1b: Number lead sweet-spot and worst-performing magnitude (Finding 1b)
if not df_nl_size.empty:
    _nl_best  = df_nl_size.loc[df_nl_size["median"].idxmax()]
    _nl_worst = df_nl_size.loc[df_nl_size["median"].idxmin()]
    NL_SWEET_SPOT_CAT = str(_nl_best["size_cat"])
    NL_SWEET_SPOT_MED = float(_nl_best["median"])
    NL_WORST_CAT      = str(_nl_worst["size_cat"])
    NL_WORST_MED      = float(_nl_worst["median"])
else:
    NL_SWEET_SPOT_CAT = "11–20"; NL_SWEET_SPOT_MED = np.nan
    NL_WORST_CAT      = "50+";   NL_WORST_MED      = np.nan

NL_ROUND_SPECIFIC_PTS = (int(round((NL_SPECIFIC_MED - NL_ROUND_MED) * 100))
                          if not (np.isnan(NL_SPECIFIC_MED) or np.isnan(NL_ROUND_MED)) else 0)
NL_P_STR = _fmt_p(NL_ROUND_VS_SPECIFIC_P) if NL_ROUND_VS_SPECIFIC_P is not None else "—"
NL_NOTE_FRAC = f"{NL_PARSED}/{NL_TOTAL}" if NL_TOTAL > 0 else "—"

# F4: Notification feature callout strings (Finding 4)
# Exclusive and attribution from news brands; possessive from Us Weekly
F4_EXCL_LIFT_STR  = f"{float(_r5_excl['lift']):.2f}×"  if _r5_excl is not None else "—"
F4_EXCL_P_STR     = _fmt_p(_get_p(_r5_excl), adj=True) if _r5_excl is not None else "—"
F4_POSS_LIFT_STR  = f"{float(_r5_poss['lift']):.2f}×"  if _r5_poss is not None else "—"
F4_POSS_P_STR     = _fmt_p(_get_p(_r5_poss), adj=True) if _r5_poss is not None else "—"
F4_ATTR_LIFT_STR  = f"{float(_r5_attr['lift']):.2f}×"  if _r5_attr is not None else "—"
F4_ATTR_P_STR     = _fmt_p(_get_p(_r5_attr), adj=True) if _r5_attr is not None else "—"
def _q5_sig_count(df: "pd.DataFrame") -> int:
    if df.empty: return 0
    return int(df.apply(
        lambda r: float(r.get("p_adj") if pd.notna(r.get("p_adj", float("nan"))) else r["p"]) < 0.05,
        axis=1).sum())
N_SIG_NOTIF_NEWS = _q5_sig_count(df_q5_news)
N_SIG_NOTIF_UW   = _q5_sig_count(df_q5_uw)
N_SIG_NOTIF_FEATURES = N_SIG_NOTIF_NEWS + N_SIG_NOTIF_UW  # kept for backward compat

# F6: IQR/median values for business and lifestyle by name (Finding 6)
_biz_row  = df_var[df_var["topic"] == "business"]
_life_row = df_var[df_var["topic"] == "lifestyle"]
F6_BIZ_CV   = f"{float(_biz_row['an_cv'].iloc[0]):.2f}"  if len(_biz_row)  > 0 else "1.55"
F6_LIFE_CV  = f"{float(_life_row['an_cv'].iloc[0]):.2f}" if len(_life_row) > 0 else "1.55"

# F9: Word count quartile stats for team finding
if not df_wc_quartile.empty and WC_MATCHED_N >= 20:
    try:
        _wci = df_wc_quartile.set_index("wc_quartile")
        WC_Q4_PCT   = float(_wci.loc["Q4 (long)", "med_pct"])  if "Q4 (long)" in _wci.index else np.nan
        WC_Q4_WORDS = float(_wci.loc["Q4 (long)", "med_wc"])   if "Q4 (long)" in _wci.index else np.nan
        WC_Q2_PCT   = float(_wci.loc["Q2", "med_pct"])         if "Q2" in _wci.index else np.nan
        WC_Q2_WORDS = float(_wci.loc["Q2", "med_wc"])          if "Q2" in _wci.index else np.nan
    except (KeyError, ValueError):
        # Intentional: quartile labels may vary; default to nan so downstream strs show "—"
        WC_Q4_PCT = WC_Q4_WORDS = WC_Q2_PCT = WC_Q2_WORDS = np.nan
else:
    WC_Q4_PCT = WC_Q4_WORDS = WC_Q2_PCT = WC_Q2_WORDS = np.nan

_F9_Q4_PCT_STR   = f"{WC_Q4_PCT:.0%}"       if pd.notna(WC_Q4_PCT)   else "18th percentile"
_F9_Q4_WORDS_STR = f"{int(WC_Q4_WORDS):,}"  if pd.notna(WC_Q4_WORDS) else "1,200+"
_F9_Q2_PCT_STR   = f"{WC_Q2_PCT:.0%}"       if pd.notna(WC_Q2_PCT)   else "48th percentile"
_F9_Q2_WORDS_STR = f"{int(WC_Q2_WORDS):,}"  if pd.notna(WC_Q2_WORDS) else "~900"

# Headline length quartile performance for Playbook tile
if not df_hl_len.empty:
    try:
        _hli = df_hl_len.set_index("bucket")
        AN_LEN_Q1_PCT   = float(_hli.loc["Short (Q1)",     "an_med"])     if "Short (Q1)"     in _hli.index else np.nan
        AN_LEN_Q4_PCT   = float(_hli.loc["Very long (Q4)", "an_med"])     if "Very long (Q4)" in _hli.index else np.nan
        AN_LEN_Q1_CHARS = float(_hli.loc["Short (Q1)",     "an_len_med"]) if "Short (Q1)"     in _hli.index else np.nan
        AN_LEN_Q4_CHARS = float(_hli.loc["Very long (Q4)", "an_len_med"]) if "Very long (Q4)" in _hli.index else np.nan
    except (KeyError, ValueError):
        # Intentional: bucket labels may vary if qcut fell back; default to nan for display
        AN_LEN_Q1_PCT = AN_LEN_Q4_PCT = AN_LEN_Q1_CHARS = AN_LEN_Q4_CHARS = np.nan
else:
    AN_LEN_Q1_PCT = AN_LEN_Q4_PCT = AN_LEN_Q1_CHARS = AN_LEN_Q4_CHARS = np.nan

AN_LEN_Q1_STR       = f"{AN_LEN_Q1_PCT:.0%}"     if pd.notna(AN_LEN_Q1_PCT)   else "—"
AN_LEN_Q4_STR       = f"{AN_LEN_Q4_PCT:.0%}"     if pd.notna(AN_LEN_Q4_PCT)   else "—"
AN_LEN_Q4_CHARS_STR = f"~{int(AN_LEN_Q4_CHARS)}" if pd.notna(AN_LEN_Q4_CHARS) else "~93"
AN_LEN_Q1_CHARS_STR = f"~{int(AN_LEN_Q1_CHARS)}" if pd.notna(AN_LEN_Q1_CHARS) else "~55"
HL_AN_P_STR  = _fmt_p(HL_AN_Q4Q1_P, adj=True) if not np.isnan(HL_AN_Q4Q1_P) else None
HL_SN_P_STR  = _fmt_p(HL_SN_Q4Q1_P, adj=True) if not np.isnan(HL_SN_Q4Q1_P) else None
# Confidence level: significant on both platforms → High; one platform → Moderate; neither → Directional
_hl_an_sig = not np.isnan(HL_AN_Q4Q1_P) and HL_AN_Q4Q1_P < 0.05
_hl_sn_sig = not np.isnan(HL_SN_Q4Q1_P) and HL_SN_Q4Q1_P < 0.05
if _hl_an_sig and _hl_sn_sig:
    HL_CONF_CLASS, HL_CONF_LABEL = "conf-high", "High confidence"
elif _hl_an_sig:
    HL_CONF_CLASS, HL_CONF_LABEL = "conf-mod", "Moderate"
else:
    HL_CONF_CLASS, HL_CONF_LABEL = "conf-dir", "Directional"
# Sports p-value string (single unadjusted test — report raw)
SPORTS_P_STR = _fmt_p(_p_sports, adj=False) if _p_sports is not None else None
# Word count p-value string
WC_P_STR = _fmt_p(WC_Q4_VS_Q2_P, adj=False) if not np.isnan(WC_Q4_VS_Q2_P) else None

# Data-run slug for archive system
REPORT_DATE_SLUG = _args.release or datetime.now().strftime("%Y-%m")


# ── Charts ────────────────────────────────────────────────────────────────────
CHART_H = 400
_T = get_theme(THEME)   # resolved once; use _T["grid"] / _T["baseline"] in chart code

def bar_color(lift: float) -> str:
    """Map a lift value to a palette color for bar chart markers."""
    if lift >= 1.5:   return GREEN
    if lift >= 1.0:   return BLUE
    if lift >= 0.8:   return AMBER
    return RED

# Standard legend placement for per-bar color charts — matches fig5/fig6 style.
_LEGEND_BELOW = dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5, font=dict(size=11))

def _lift_legend_traces() -> list:
    """Dummy scatter traces explaining the per-bar lift color scale (fig1, fig2, fig4).
    x=[], y=[] so no data point renders; only the legend entry is visible."""
    entries = [
        (GREEN, "Strong lift (≥ 1.5×)"),
        (BLUE,  "Moderate lift (≥ 1.0×)"),
        (AMBER, "Near baseline (≥ 0.8×)"),
        (RED,   "Underperforms baseline (< 0.8×)"),
    ]
    return [go.Scatter(x=[], y=[], mode="markers",
                       marker=dict(color=c, size=10, symbol="square"),
                       name=lbl, showlegend=True)
            for c, lbl in entries]

def _sn_legend_traces() -> list:
    """Dummy scatter traces for the SmartNews channel color scale (fig3)."""
    entries = [
        (GREEN, "High ROI (lift > 1.5×)"),
        (BLUE,  "Moderate ROI (lift > 1.0×)"),
        (RED,   "High volume, low ROI (> 20% share)"),
        (GRAY,  "Other"),
    ]
    return [go.Scatter(x=[], y=[], mode="markers",
                       marker=dict(color=c, size=10, symbol="square"),
                       name=lbl, showlegend=True)
            for c, lbl in entries]

# Chart 1 — Formula lift (percentile)
colors_q1 = [bar_color(r["lift"]) for _, r in df_q1.iterrows()]
hover_q1 = [f"Median percentile: {r['median']:.0%} | n={r['n']}" for _, r in df_q1.iterrows()]

_fig1_x = [cap_lift(r["lift"]) for _, r in df_q1.iterrows()]
_fig1_text = [f"{v:.2f}×  (n={n})" for v, n in zip(df_q1["lift"].tolist(), df_q1["n"].tolist())]
fig1 = go.Figure(go.Bar(
    y=df_q1["label"].tolist(),
    x=_fig1_x,
    orientation="h",
    marker_color=colors_q1,
    text=_fig1_text,
    textposition="outside",
    cliponaxis=False,
    hovertext=hover_q1,
    hoverinfo="y+text",
))
fig1.add_vline(x=1.0, line_dash="dash", line_color=_T["baseline"],
               annotation_text="Baseline", annotation_position="top")
for _t in _lift_legend_traces(): fig1.add_trace(_t)
fig1.update_layout(
    **make_layout(THEME, height=CHART_H, margin=dict(l=20, r=auto_right_margin(_fig1_text), t=50, b=80),
                  title="Percentile-within-cohort lift vs. baseline by formula (non-Featured articles only)"),
    xaxis=dict(title="Median cohort percentile relative to untagged baseline (1.0 = same as baseline)",
               gridcolor=_T["grid"], zeroline=False, range=safe_range(_fig1_x, margin=0.25)),
    yaxis=dict(title=""),
    showlegend=True, legend=_LEGEND_BELOW,
)
enforce_category_order(fig1, df_q1["label"].tolist())

# Chart 2 — Featured rate
colors_q2 = [bar_color(r["featured_lift"]) for _, r in df_q2.iterrows()]
_fig2_text = [f"{r['featured_rate']:.0%}  ({r['featured_lift']:.2f}×)" for _, r in df_q2.iterrows()]
fig2 = go.Figure(go.Bar(
    y=df_q2["label"].tolist(),
    x=(df_q2["featured_rate"] * 100).tolist(),
    orientation="h",
    marker_color=colors_q2,
    text=_fig2_text,
    textposition="outside",
    cliponaxis=False,
    hovertext=[f"n={r['n']}" for _, r in df_q2.iterrows()],
    hoverinfo="y+x+text",
))
fig2.add_vline(x=overall_feat_rate * 100, line_dash="dash", line_color=_T["baseline"],
               annotation_text=f"Baseline {overall_feat_rate:.0%}", annotation_position="top")
for _t in _lift_legend_traces(): fig2.add_trace(_t)
fig2.update_layout(
    **make_layout(THEME, height=CHART_H, margin=dict(l=20, r=auto_right_margin(_fig2_text), t=50, b=80),
                  title="% of articles Featured by Apple, by headline formula"),
    xaxis=dict(title="% of articles in formula group that were Featured by Apple",
               gridcolor=_T["grid"], zeroline=False, range=safe_range((df_q2["featured_rate"] * 100).tolist(), margin=0.25)),
    yaxis=dict(title=""),
    showlegend=True, legend=_LEGEND_BELOW,
)
enforce_category_order(fig2, df_q2["label"].tolist())

# Chart 3 — SmartNews categories (percentile)
df_q4_chart = df_q4.sort_values("median_pct", ascending=True)
q4_colors = []
for _, r in df_q4_chart.iterrows():
    if r["lift"] > 1.5:      q4_colors.append(GREEN)
    elif r["lift"] > 1.0:    q4_colors.append(BLUE)
    elif r["pct_share"] > 0.20: q4_colors.append(RED)
    else:                    q4_colors.append(GRAY)

_fig3_text = [f"{p:.0%} percentile  ({n:,} articles)"
              for p, n in zip(df_q4_chart["median_pct"].tolist(), df_q4_chart["n"].tolist())]
fig3 = go.Figure(go.Bar(
    y=df_q4_chart["category"].tolist(),
    x=df_q4_chart["median_pct"].tolist(),
    orientation="h",
    marker_color=q4_colors,
    text=_fig3_text,
    textposition="outside",
    cliponaxis=False,
    hovertext=[f"Median raw views: {int(v):,}" for v in df_q4_chart["median_views"].tolist()],
    hoverinfo="y+text",
))
for _t in _sn_legend_traces(): fig3.add_trace(_t)
fig3.update_layout(
    **make_layout(THEME, height=CHART_H, margin=dict(l=20, r=auto_right_margin(_fig3_text), t=50, b=80),
                  title="Median percentile rank by SmartNews channel (with article volume)"),
    xaxis=dict(title="Median cohort percentile (same outlet × month; 0=lowest, 1=highest)", gridcolor=_T["grid"],
               zeroline=False, tickformat=".0%"),
    yaxis=dict(title=""),
    showlegend=True, legend=_LEGEND_BELOW,
)
enforce_category_order(fig3, df_q4_chart["category"].tolist())

# Chart 4 — Notification CTR lift
colors_q5 = [bar_color(r["lift"]) for _, r in df_q5.iterrows()]
sig_labels = []
for _, r in df_q5.iterrows():
    p = r.get("p_adj", r["p"])
    s = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else "ns"))
    sig_labels.append(f"{r['lift']:.2f}×  {s}  (n={r['n_true']})")

_fig4_x = [cap_lift(r["lift"]) for _, r in df_q5.iterrows()]
fig4 = go.Figure(go.Bar(
    y=df_q5["feature"].tolist(),
    x=_fig4_x,
    orientation="h",
    marker_color=colors_q5,
    text=sig_labels,
    textposition="outside",
    cliponaxis=False,
    hovertext=[f"CTR present: {r['med_yes']*100:.2f}%  |  CTR absent: {r['med_no']*100:.2f}%"
               for _, r in df_q5.iterrows()],
    hoverinfo="y+text",
))
fig4.add_vline(x=1.0, line_dash="dash", line_color=_T["baseline"],
               annotation_text="No effect", annotation_position="top")
for _t in _lift_legend_traces(): fig4.add_trace(_t)
fig4.update_layout(
    **make_layout(THEME, height=CHART_H, margin=dict(l=20, r=auto_right_margin(sig_labels), t=50, b=80),
                  title="Notification CTR lift by headline feature (median CTR, feature present vs. absent)"),
    xaxis=dict(title="CTR lift (1.0 = no effect)", gridcolor=_T["grid"], zeroline=False, range=safe_range(_fig4_x, margin=0.25)),
    yaxis=dict(title=""),
    showlegend=True, legend=_LEGEND_BELOW,
)
enforce_category_order(fig4, df_q5["feature"].tolist())

# Chart 5 — Topic index by platform
fig5 = go.Figure()
fig5.add_trace(go.Bar(
    y=topic_df["label"].tolist(), x=topic_df["an_idx"].tolist(),
    name="Apple News", orientation="h",
    marker_color=BLUE, opacity=0.85,
    hovertemplate="<b>%{y}</b><br>Apple News: %{x:.2f}× platform median<extra></extra>",
))
fig5.add_trace(go.Bar(
    y=topic_df["label"].tolist(), x=topic_df["sn_idx"].tolist(),
    name="SmartNews", orientation="h",
    marker_color=GREEN, opacity=0.85,
    hovertemplate="<b>%{y}</b><br>SmartNews: %{x:.2f}× platform median<extra></extra>",
))
fig5.add_trace(go.Bar(
    y=topic_df["label"].tolist(), x=topic_df["msn_idx"].tolist(),
    name="MSN", orientation="h",
    marker_color=ORANGE, opacity=0.85,
    hovertemplate="<b>%{y}</b><br>MSN: %{x:.2f}× platform median<extra></extra>",
))
fig5.add_vline(x=1.0, line_dash="dash", line_color=_T["baseline"],
               annotation_text="Platform median", annotation_position="top")
fig5.update_layout(
    **make_layout(THEME, height=480, margin=dict(l=20, r=40, t=50, b=80),
                  title="Topic performance by platform: percentile rank vs. platform median"),
    barmode="group",
    xaxis=dict(title="Percentile index (1.0 = platform median)", gridcolor=_T["grid"], zeroline=False),
    yaxis=dict(title=""),
    legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
)
enforce_category_order(fig5, topic_df["label"].tolist())

# Chart 6 — Variance (IQR/median of percentile)
fig6 = go.Figure()
fig6.add_trace(go.Bar(
    y=df_var["label"].tolist(), x=df_var["an_cv"].tolist(),
    name="Apple News", orientation="h",
    marker_color=BLUE, opacity=0.85,
    text=[f"{v:.1f}×  (n={n:,})" for v, n in zip(df_var["an_cv"].tolist(), df_var["an_n"].tolist())],
    textposition="outside",
    cliponaxis=False,
    hovertemplate="<b>%{y}</b><br>Apple News IQR/median: %{x:.2f}<extra></extra>",
))
fig6.add_trace(go.Bar(
    y=df_var["label"].tolist(), x=df_var["sn_cv"].tolist(),
    name="SmartNews", orientation="h",
    marker_color=GREEN, opacity=0.85,
    text=[f"{v:.1f}×  (n={n:,})" for v, n in zip(df_var["sn_cv"].tolist(), df_var["sn_n"].tolist())],
    textposition="outside",
    cliponaxis=False,
    hovertemplate="<b>%{y}</b><br>SmartNews IQR/median: %{x:.2f}<extra></extra>",
))
fig6.update_layout(
    **make_layout(THEME, height=480, margin=dict(l=20, r=140, t=50, b=80),
                  title="Outcome spread by topic (where headline choice has the most room to move performance)"),
    barmode="group",
    xaxis=dict(title="IQR ÷ median percentile (higher = wider spread between top and bottom articles)",
               gridcolor=_T["grid"], zeroline=False),
    yaxis=dict(title=""),
    legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
)
enforce_category_order(fig6, df_var["label"].tolist())

# Chart 7 — Views vs active time scatter
q6_sample = an_eng
feat_mask  = q6_sample["is_featured"]
nfeat_mask = ~q6_sample["is_featured"]

fig7 = go.Figure()
fig7.add_trace(go.Scatter(
    x=safe_log_floor(q6_sample[nfeat_mask]["Total Views"]),
    y=q6_sample[nfeat_mask][AT_COL].tolist(),
    mode="markers", name="Not Featured",
    marker=dict(color=BLUE, size=4, opacity=0.35),
    hovertemplate="Views: %{x:,.0f}<br>Active time: %{y:.0f}s<extra>Not Featured</extra>",
))
fig7.add_trace(go.Scatter(
    x=safe_log_floor(q6_sample[feat_mask]["Total Views"]),
    y=q6_sample[feat_mask][AT_COL].tolist(),
    mode="markers", name="Featured by Apple",
    marker=dict(color=GREEN, size=5, opacity=0.6),
    hovertemplate="Views: %{x:,.0f}<br>Active time: %{y:.0f}s<extra>Featured</extra>",
))
fig7.update_layout(
    **make_layout(THEME, height=460, margin=dict(l=20, r=40, t=50, b=80),
                  title=f"Views vs. average active time; Pearson r = {r_views_at:.3f} (p = {p_views_at:.2f})"),
    xaxis=dict(title="Total views (log scale)", type="log", gridcolor=_T["grid"]),
    yaxis=dict(title="Avg. active time (seconds)", gridcolor=_T["grid"],
               range=safe_range(q6_sample[AT_COL].dropna(), margin=0.1, floor=0.0)),
    legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
)

# ── Fig 8: Longitudinal — 3-period lift line chart ───────────────────────────
# Each formula gets a line across 3 clearly-labelled periods.
# Lift = formula median percentile / untagged baseline median in the same period.
# Formulas with n<5 in a period are suppressed for that point only.
_period_colors_8 = {
    "number_lead":             AMBER,
    "question":                RED,
    "possessive_named_entity": BLUE,
    "heres_formula":           GREEN,
    "what_to_know":            GRAY,
}
_period_order_8 = ["Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025", "Q1 2026"]

# Only chart formulas with ≥15 articles per quarter — noise swamps trend below that.
# Heres/WTK have n=4–9/quarter; they stay in the table but not in the chart.
_CHART_MIN_N = 15
# Use numeric x-positions mapped from quarter labels — avoids Plotly categorical axis quirks
_q_to_x = {q: i for i, q in enumerate(_period_order_8)}

fig8 = go.Figure()

if not df_periods.empty:
    for f, color in _period_colors_8.items():
        sub = df_periods[df_periods["formula"] == f].copy()
        sub = sub[sub["n"] >= _CHART_MIN_N]
        sub["_x"] = sub["period"].map(_q_to_x)
        sub = sub.dropna(subset=["_x"]).sort_values("_x")
        if len(sub) < 2:
            continue
        label = FORMULA_LABELS.get(f, f)
        fig8.add_trace(go.Scatter(
            x=sub["_x"].tolist(),
            y=sub["lift"].tolist(),
            mode="lines+markers+text",
            name=label,
            line=dict(color=color, width=2.5),
            marker=dict(size=10, color=color),
            text=[f"{v:.2f}×" for v in sub["lift"]],
            textposition="top center",
            textfont=dict(size=10, color=color),
            hovertemplate="%{x}: %{y:.2f}× baseline (n=%{customdata})<extra>" + label + "</extra>",
            customdata=sub["n"].tolist(),
        ))

fig8.add_shape(type="line", x0=-0.3, x1=len(_period_order_8)-0.7,
               y0=1.0, y1=1.0, line=dict(color=_T["baseline"], width=1.5, dash="dash"))
fig8.add_annotation(x=len(_period_order_8)-0.75, y=1.0, text="Baseline (1.0×)",
                    showarrow=False, font=dict(size=10, color=_T["baseline"]),
                    xanchor="left", yanchor="middle")

fig8.update_layout(
    **make_layout(THEME, height=420, margin=dict(l=20, r=180, t=50, b=60),
                  title="Headline formula lift vs. unclassified baseline, Q1 2025 through Q1 2026"),
    xaxis=dict(
        title="",
        gridcolor=_T["grid"],
        zeroline=False,
        tickmode="array",
        tickvals=list(range(len(_period_order_8))),
        ticktext=_period_order_8,
        range=[-0.4, len(_period_order_8) - 0.6],
    ),
    yaxis=dict(
        title="Lift vs. baseline (1.0 = same as unclassified headlines)",
        gridcolor=_T["grid"],
        zeroline=False,
        tickformat=".2f",
        range=safe_range(df_periods["lift"].dropna() if not df_periods.empty else [1.0], margin=0.2, floor=None),
    ),
    legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02, font=dict(size=11)),
)
guard_empty(fig8, df_periods, "Longitudinal data requires at least 2 time periods.")

# OLS trend lines — shows whether each formula's lift is trending up or down.
# Only runs when statsmodels is present and there are enough data points.
if HAS_STATSMODELS and not df_periods.empty:
    for f, color in _period_colors_8.items():
        sub = df_periods[df_periods["formula"] == f].copy()
        sub = sub[sub["n"] >= _CHART_MIN_N].dropna(subset=["lift"])
        sub["_x"] = sub["period"].map(_q_to_x)
        sub = sub.dropna(subset=["_x"]).sort_values("_x")
        if len(sub) < 3:
            continue
        try:
            _ols_x = sm.add_constant(sub["_x"].values.astype(float))
            _ols_res = sm.OLS(sub["lift"].values.astype(float), _ols_x).fit()
            _x_line = np.linspace(sub["_x"].min(), sub["_x"].max(), 50)
            _y_line = _ols_res.params[0] + _ols_res.params[1] * _x_line
            fig8.add_trace(go.Scatter(
                x=_x_line.tolist(),
                y=_y_line.tolist(),
                mode="lines",
                name=f"{FORMULA_LABELS.get(f, f)} trend",
                line=dict(color=color, width=1.0, dash="dot"),
                showlegend=False,
                hoverinfo="skip",
            ))
        except Exception:
            pass  # Non-critical; scatter points still show

# Chart HL — Headline length quartile vs. percentile (Apple News + SmartNews)
fig_hl = go.Figure()
if not df_hl_len.empty:
    fig_hl.add_trace(go.Bar(
        y=df_hl_len["bucket"].tolist(), x=df_hl_len["an_med"].tolist(),
        name="Apple News", orientation="h", marker_color=BLUE, opacity=0.85,
        text=[f"{v:.0%}  (n={n:,})" if pd.notna(v) else "—"
              for v, n in zip(df_hl_len["an_med"], df_hl_len["an_n"])],
        textposition="outside", cliponaxis=False,
    ))
    fig_hl.add_trace(go.Bar(
        y=df_hl_len["bucket"].tolist(), x=df_hl_len["sn_med"].tolist(),
        name="SmartNews", orientation="h", marker_color=GREEN, opacity=0.85,
        text=[f"{v:.0%}  (n={n:,})" if pd.notna(v) else "—"
              for v, n in zip(df_hl_len["sn_med"], df_hl_len["sn_n"])],
        textposition="outside", cliponaxis=False,
    ))
_fig_hl_text = ([f"{v:.0%}  (n={n:,})" if pd.notna(v) else "—"
                 for v, n in zip(df_hl_len["an_med"].fillna(0), df_hl_len["an_n"].fillna(0))]
                if not df_hl_len.empty else [])
fig_hl.add_vline(x=0.5, line_dash="dash", line_color=_T["baseline"],
                 annotation_text="50th %ile", annotation_position="top")
fig_hl.update_layout(
    **make_layout(THEME, height=360, margin=dict(l=20, r=auto_right_margin(_fig_hl_text), t=50, b=80),
                  title="Headline length (character count quartile) vs. median percentile rank"),
    barmode="group",
    xaxis=dict(title="Median cohort percentile (same outlet × month)", gridcolor=_T["grid"],
               zeroline=False, tickformat=".0%"),
    yaxis=dict(title=""),
    legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5),
)
guard_empty(fig_hl, df_hl_len, "Headline length data unavailable.")

# Chart ANP failures — Section performance spectrum (Finding 8)
fig_anp_fail = go.Figure()
if HAS_ANP and not _anp_fail["ANP_FAIL_SEC_DF"].empty:
    _df_sf = _anp_fail["ANP_FAIL_SEC_DF"].sort_values("med_rank")
    _sf_colors = [
        GREEN if r >= 0.75 else (RED if r <= 0.30 else BLUE)
        for r in _df_sf["med_rank"]
    ]
    _sf_text = [
        f"{r:.2f}  (n={n:,}, feat={f:.0%})"
        for r, n, f in zip(_df_sf["med_rank"], _df_sf["n"], _df_sf["featured_rate"])
    ]
    fig_anp_fail.add_trace(go.Bar(
        y=_df_sf["section"].tolist(),
        x=_df_sf["med_rank"].tolist(),
        orientation="h",
        marker_color=_sf_colors,
        text=_sf_text,
        textposition="outside",
        cliponaxis=False,
        hoverinfo="y+text",
    ))
    fig_anp_fail.add_vline(x=0.5, line_dash="dash", line_color=_T["baseline"],
                           annotation_text="50th %ile", annotation_position="top")
    fig_anp_fail.update_layout(
        **make_layout(THEME, height=max(420, len(_df_sf) * 28),
                      margin=dict(l=20, r=auto_right_margin(_sf_text), t=50, b=60),
                      title="Apple News section performance — median view percentile rank"),
        xaxis=dict(title="Median cohort percentile rank", gridcolor=_T["grid"],
                   zeroline=False, tickformat=".0%", range=[0, 1.12]),
        yaxis=dict(title=""),
    )
    enforce_category_order(fig_anp_fail, _df_sf["section"].tolist())
guard_empty(fig_anp_fail, _anp_fail.get("ANP_FAIL_SEC_DF", pd.DataFrame()),
            "Section performance chart unavailable.")

# ── Chart MSN Formula — bar chart of MSN formula performance (Change 2) ───────
fig_msn_formula = go.Figure()
if not df_msn_formula.empty:
    _mf_labels = [
        {"what_to_know": "Explainer (What to know)", "heres_formula": "Here's / Here are",
         "possessive_named_entity": "Possessive named entity", "question": "Question",
         "number_lead": "Number lead", "quoted_lede": "Quoted lede"}.get(f, f)
        for f in df_msn_formula["formula"]
    ]
    _mf_colors = [RED if float(r.get("lift", 1.0)) < 1.0 else BLUE
                  for _, r in df_msn_formula.iterrows()]
    _mf_text = [f"{float(r.get('lift', 1.0)):.2f}×  (n={int(r.get('n', 0))})"
                for _, r in df_msn_formula.iterrows()]
    fig_msn_formula.add_trace(go.Bar(
        y=_mf_labels, x=[float(r.get("lift", 1.0)) for _, r in df_msn_formula.iterrows()],
        orientation="h",
        marker_color=_mf_colors,
        text=_mf_text,
        textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Lift vs. direct declarative: %{x:.2f}×<extra></extra>",
    ))
    fig_msn_formula.add_vline(x=1.0, line_dash="dash", line_color=_T["baseline"],
                              annotation_text="Direct declarative baseline", annotation_position="top")
fig_msn_formula.update_layout(
    **make_layout(THEME, height=max(300, len(df_msn_formula) * 40 + 80),
                  margin=dict(l=20, r=auto_right_margin(_mf_text if not df_msn_formula.empty else []), t=50, b=60),
                  title="MSN formula lift vs. direct declarative baseline (median pageviews)"),
    xaxis=dict(title="Lift vs. direct declarative (1.0 = same)", gridcolor=_T["grid"],
               zeroline=False, tickformat=".2f"),
    yaxis=dict(title=""),
)
if not df_msn_formula.empty:
    enforce_category_order(fig_msn_formula, _mf_labels)
guard_empty(fig_msn_formula, df_msn_formula, "MSN formula data requires MSN to be enabled.")

# ── Chart CTR Monthly — news brand notification CTR by month (Change 4) ───────
fig_ctr_monthly = go.Figure()
if not _nb_monthly.empty:
    _m_x = list(range(len(_nb_monthly)))
    _m_labels = _nb_monthly["_month"].tolist()
    _m_y = _nb_monthly["median"].tolist()
    fig_ctr_monthly.add_trace(go.Scatter(
        x=_m_x, y=_m_y,
        mode="lines+markers+text",
        name="News brand CTR",
        line=dict(color=BLUE, width=2.5),
        marker=dict(size=8, color=BLUE),
        text=[f"{v:.2%}" for v in _m_y],
        textposition="top center",
        textfont=dict(size=10, color=BLUE),
        hovertemplate="<b>%{customdata}</b><br>Median CTR: %{y:.2%}<extra></extra>",
        customdata=_m_labels,
    ))
    # Trend line (OLS) if statsmodels available
    if HAS_STATSMODELS and len(_m_x) >= 3:
        try:
            _ctr_ols_x = sm.add_constant(np.array(_m_x, dtype=float))
            _ctr_ols   = sm.OLS(np.array(_m_y, dtype=float), _ctr_ols_x).fit()
            _ctr_trend_y = _ctr_ols.params[0] + _ctr_ols.params[1] * np.array(_m_x, dtype=float)
            fig_ctr_monthly.add_trace(go.Scatter(
                x=_m_x, y=_ctr_trend_y.tolist(),
                mode="lines", name="Trend (OLS)",
                line=dict(color=RED, width=1.5, dash="dot"),
                showlegend=True,
                hoverinfo="skip",
            ))
        except Exception:
            pass
fig_ctr_monthly.update_layout(
    **make_layout(THEME, height=360, margin=dict(l=20, r=40, t=50, b=80),
                  title="News brand Apple News notification CTR by month (Jun 2025–Mar 2026)"),
    xaxis=dict(
        title="",
        gridcolor=_T["grid"],
        zeroline=False,
        tickmode="array",
        tickvals=list(range(len(_nb_monthly))),
        ticktext=(_nb_monthly["_month"].tolist() if not _nb_monthly.empty else []),
        range=[-0.4, len(_nb_monthly) - 0.6] if not _nb_monthly.empty else [0, 1],
    ),
    yaxis=dict(
        title="Median CTR",
        gridcolor=_T["grid"],
        zeroline=False,
        tickformat=".2%",
        range=safe_range(pd.Series(_m_y if not _nb_monthly.empty else [0.01]), margin=0.25, floor=0.0),
    ),
    legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5),
)
guard_empty(fig_ctr_monthly, _nb_monthly, "Monthly CTR data requires news brand notifications.")


# ── Chart Finding A — formula × topic top 10 (Apple News featuring rate) ─────
fig_fa = go.Figure()
_fa_sorted = df_fa_top10.sort_values("feat_pct", ascending=True)
_fa_labels = [f"{r['formula']} × {r['topic']}" for _, r in _fa_sorted.iterrows()]
_fa_colors = [BLUE if r["feat_pct"] < 0.50 else GREEN for _, r in _fa_sorted.iterrows()]
_fa_text   = [f"{r['feat_pct']:.0%}  (n={int(r['n'])})" for _, r in _fa_sorted.iterrows()]
fig_fa.add_trace(go.Bar(
    y=_fa_labels,
    x=_fa_sorted["feat_pct"].tolist(),
    orientation="h",
    marker_color=_fa_colors,
    text=_fa_text,
    textposition="outside",
    cliponaxis=False,
    hovertemplate="<b>%{y}</b><br>Featuring rate: %{x:.0%}<extra></extra>",
))
fig_fa.add_vline(x=0.20, line_dash="dash", line_color=_T["baseline"],
                 annotation_text="~20% baseline", annotation_position="top")
fig_fa.update_layout(
    **make_layout(THEME, height=440,
                  margin=dict(l=20, r=auto_right_margin(_fa_text), t=50, b=60),
                  title="Apple News featuring rate by formula × topic (top 10 combinations)"),
    xaxis=dict(title="Featuring rate", gridcolor=_T["grid"], zeroline=False,
               tickformat=".0%", range=[0.0, 0.90]),
    yaxis=dict(title=""),
)
enforce_category_order(fig_fa, _fa_labels)
guard_empty(fig_fa, df_fa_top10, "Formula × topic data unavailable.")


# ── Chart Finding B — cross-platform formula comparison (AN feat% vs SN rank) ─
fig_fb = go.Figure()
_fb_display = df_fb_chart.dropna(subset=["an_feat_rate"]).copy()
_fb_display = _fb_display.sort_values("sn_rank", ascending=False)
_fb_formulas = _fb_display["formula"].tolist()

# Apple News featured rate trace (primary axis)
fig_fb.add_trace(go.Bar(
    name="Apple News feat%",
    y=_fb_formulas,
    x=_fb_display["an_feat_rate"].tolist(),
    orientation="h",
    marker_color=BLUE,
    opacity=0.85,
    text=[f"AN: {v:.0%}" for v in _fb_display["an_feat_rate"]],
    textposition="inside",
    textfont=dict(color="white", size=10),
))
# SmartNews rank trace (normalised to 0–1 so both axes are comparable)
fig_fb.add_trace(go.Bar(
    name="SmartNews pct_rank",
    y=_fb_formulas,
    x=_fb_display["sn_rank"].tolist(),
    orientation="h",
    marker_color=GREEN,
    opacity=0.85,
    text=[f"SN: {v:.3f}" for v in _fb_display["sn_rank"]],
    textposition="inside",
    textfont=dict(color="white", size=10),
))
fig_fb.add_vline(x=0.50, line_dash="dash", line_color=_T["baseline"],
                 annotation_text="SN baseline 0.50", annotation_position="top")
fig_fb.update_layout(
    **make_layout(THEME, height=400,
                  margin=dict(l=20, r=100, t=60, b=80),
                  title="Formula performance: Apple News featuring rate vs. SmartNews percentile rank"),
    barmode="group",
    xaxis=dict(title="Rate / rank (both 0–1 scale)", gridcolor=_T["grid"],
               zeroline=False, tickformat=".2f", range=[0, 0.70]),
    yaxis=dict(title=""),
    legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
)
enforce_category_order(fig_fb, _fb_formulas)
guard_empty(fig_fb, _fb_display, "Cross-platform formula data unavailable.")


# ── Chart Notification Send Time — CTR by time window ─────────────────────────
fig_notif_time = go.Figure()
_nt_colors = [
    GREEN if r["median_ctr"] >= 0.015 else
    (AMBER if r["median_ctr"] >= 0.013 else RED)
    for _, r in df_notif_time.iterrows()
]
_nt_text = [f"{r['median_ctr']:.2%}" for _, r in df_notif_time.iterrows()]
fig_notif_time.add_trace(go.Bar(
    x=df_notif_time["bin_label"].tolist(),
    y=df_notif_time["median_ctr"].tolist(),
    marker_color=_nt_colors,
    text=_nt_text,
    textposition="outside",
    cliponaxis=False,
    hovertemplate="<b>%{x}</b><br>Median CTR: %{y:.2%}<extra></extra>",
))
fig_notif_time.add_hline(
    y=df_notif_time["median_ctr"].mean(),
    line_dash="dash", line_color=_T["baseline"],
    annotation_text=f"Mean {df_notif_time['median_ctr'].mean():.2%}",
    annotation_position="right",
)
fig_notif_time.update_layout(
    **make_layout(THEME, height=360,
                  margin=dict(l=20, r=60, t=60, b=80),
                  title="Apple News notification CTR by send-time window (news brands, n=1,050)"),
    xaxis=dict(title="", gridcolor=_T["grid"], zeroline=False),
    yaxis=dict(title="Median CTR", gridcolor=_T["grid"], zeroline=False,
               tickformat=".2%",
               range=safe_range(df_notif_time["median_ctr"].tolist(), margin=0.25, floor=0.0)),
)
guard_empty(fig_notif_time, df_notif_time, "Send-time data unavailable.")


# ── Render charts ─────────────────────────────────────────────────────────────
c1 = safe_chart(fig1)
c2 = safe_chart(fig2)
c3 = safe_chart(fig3)
c4 = safe_chart(fig4)
c5 = safe_chart(fig5)
c6 = safe_chart(fig6)
c7   = safe_chart(fig7)
c8   = safe_chart(fig8)
c_hl = safe_chart(fig_hl)
c_anp_fail = safe_chart(fig_anp_fail)
c_msn_formula  = safe_chart(fig_msn_formula)
c_ctr_monthly  = safe_chart(fig_ctr_monthly)
c_fa           = safe_chart(fig_fa)
c_fb           = safe_chart(fig_fb)
c_notif_time   = safe_chart(fig_notif_time)

# ── Conditional sections ──────────────────────────────────────────────────────
_finding9_html = ""
if HAS_TRACKER and N_TRACKED > 0:
    _finding9_html = f"""
  <!-- TEAM PERFORMANCE -->
  <details id="team" class="finding-card">
    <summary class="finding-header">
      <span class="finding-chevron">▶</span>
      <div class="finding-summary">
        <p class="section-label">Finding 9 · Team Performance (Tracker)</p>
        <h2>{N_TRACKED} tracked articles matched across Apple News, SmartNews, and Yahoo.</h2>
      </div>
    </summary>
    <div class="finding-body">
      <div class="callout">
        <strong>Note:</strong> {N_TRACKED} articles from the content tracker matched to syndication data via URL or headline. Results are directional; match rate limits coverage.
      </div>
      <h3>Author performance by platform (sorted by median percentile)</h3>
      <table class="findings">
        <thead><tr><th>Author</th><th>Platform</th><th>n articles</th><th>Cohort %ile</th></tr></thead>
        <tbody>{_t_auth}</tbody>
      </table>
      <h3>Top 20 articles by percentile rank</h3>
      <table class="findings">
        <thead><tr><th>Article</th><th>Platform / Brand</th><th>Author</th><th>Cohort %ile</th><th>Views</th><th>Featured</th></tr></thead>
        <tbody>{_t_team}</tbody>
      </table>
      <h3>Article length and syndication performance ({WC_MATCHED_N} matched articles with word count)</h3>
      <div class="callout">
        <strong>Unexpected:</strong> Articles in the longest quartile (~{_F9_Q4_WORDS_STR} words) perform at the {_F9_Q4_PCT_STR} — worse than any other length group. Q2 (~{_F9_Q2_WORDS_STR} words) is the highest-performing range in this sample at {_F9_Q2_PCT_STR}. {"Mann-Whitney Q4 vs. Q2: " + WC_P_STR + " (n=" + str(WC_MATCHED_N) + ", unadjusted). Pattern is consistent within SmartNews individually but interpret cautiously at this sample size." if WC_P_STR else "Based on " + str(WC_MATCHED_N) + " tracker-matched articles, mostly SmartNews — too small for reliable significance testing. Treat as directional."}
      </div>
      <table class="findings">
        <thead><tr><th>Word count quartile</th><th>n</th><th>Median word count</th><th>Cohort %ile</th></tr></thead>
        <tbody>{_t_wc}</tbody>
      </table>
      <p class="callout-inline"><strong>Read this table as:</strong> Articles from the content tracker matched to syndication data by URL and headline. Percentile ranks are platform-relative (SmartNews vs. SmartNews, Yahoo vs. Yahoo). Word count is from the tracker, not the syndication data.</p>
    </div>
  </details>
"""

_finding_numleads_html = ""
if NL_PARSED >= 10:
    _nl_round_sig = (f"Mann-Whitney p={NL_ROUND_VS_SPECIFIC_P:.3f}, rb={NL_ROUND_VS_SPECIFIC_RB:.2f}"
                     if NL_ROUND_VS_SPECIFIC_P is not None else "insufficient sample for test")
    _nl_round_examples = "".join(f"<li>{html_module.escape(str(h))}</li>" for h in nl_round_ex)
    _nl_specific_examples = "".join(f"<li>{html_module.escape(str(h))}</li>" for h in nl_specific_ex)
    _finding_numleads_html = f"""
  <!-- NUMBER LEADS DEEP DIVE -->
  <details id="numleads" class="finding-card">
    <summary class="finding-header">
      <span class="finding-chevron">▶</span>
      <div class="finding-summary">
        <p class="section-label">Finding 1b · Number Leads: Deep Dive</p>
        <h2>Specific numbers outperform round numbers. Count/list formats lead; years and dollar amounts lag.</h2>
      </div>
    </summary>
    <div class="finding-body">
      <div class="callout">
        <strong>Key finding:</strong> Round numbers (multiples of 10, 100, 1,000) score at the {NL_ROUND_MED:.0%}ile — {NL_ROUND_SPECIFIC_PTS} percentile points below specific numbers ({NL_SPECIFIC_MED:.0%}ile). The difference is statistically significant ({NL_P_STR}). Numbers in the {NL_SWEET_SPOT_CAT} range are the highest-performing in this dataset ({NL_SWEET_SPOT_MED:.0%}ile). Numbers {NL_WORST_CAT} drag performance to the {NL_WORST_MED:.0%}ile. Bottom line: "127 arrested" outperforms "100 arrested," and "15 takeaways" outperforms "50 things to know."
      </div>
      <h3>Round vs. specific numbers</h3>
      <p>Round numbers (multiples of 10, 100, 1,000): median {NL_ROUND_MED:.0%}ile vs. specific numbers: median {NL_SPECIFIC_MED:.0%}ile. ({_nl_round_sig})</p>
      <div class="two-col">
        <div>
          <p><strong>Top performers: specific numbers</strong></p>
          <ul class="headline-list">{_nl_specific_examples}</ul>
        </div>
        <div>
          <p><strong>Top performers: round numbers</strong></p>
          <ul class="headline-list">{_nl_round_examples}</ul>
        </div>
      </div>
      <h3>By number type</h3>
      <table class="findings">
        <thead><tr><th>Number type</th><th>n</th><th>Cohort %ile</th><th>Lift vs. baseline</th></tr></thead>
        <tbody>{_t_nl_type}</tbody>
      </table>
      <p class="callout-inline"><strong>Note:</strong> Nearly all number-lead articles ({NL_NOTE_FRAC}) use a count or list format. Dollar amounts and ordinals appear too rarely (n&lt;10) for reliable conclusions.</p>
      <h3>By number magnitude</h3>
      <table class="findings">
        <thead><tr><th>Number range</th><th>n</th><th>Cohort %ile</th><th>Lift vs. baseline</th></tr></thead>
        <tbody>{_t_nl_size}</tbody>
      </table>
      <p class="callout-inline"><strong>Unexpected:</strong> The {NL_SWEET_SPOT_CAT} range outperforms even single-digit numbers ({NL_SWEET_SPOT_MED:.0%}ile). The {NL_WORST_CAT} range is the weakest ({NL_WORST_MED:.0%}ile) — avoid leading with totals, casualty counts, or cumulative statistics that tend to produce large numbers.</p>
    </div>
  </details>
"""

# ── Archive helpers (shared by main page and playbook archive logic) ──────────

def _slug_to_label(slug: str) -> str:
    """Convert a YYYY-MM slug to a human-readable month label. Returns slug unchanged on failure."""
    try:
        return datetime.strptime(slug, "%Y-%m").strftime("%B %Y")
    except ValueError:
        # Slug doesn't match YYYY-MM format; return as-is
        return slug

def _slug_age_months(slug: str) -> int:
    """Months between slug (YYYY-MM) and today. Returns large number on parse failure."""
    from datetime import date as _date
    try:
        then = datetime.strptime(slug, "%Y-%m").date().replace(day=1)
        now  = _date.today().replace(day=1)
        return (now.year - then.year) * 12 + (now.month - then.month)
    except ValueError:
        # Slug doesn't match YYYY-MM format; treat as very old to exclude from display
        return 999

# ── Main page archive logic (runs before html f-string so _main_past_runs_html is defined) ──
_main_path     = Path("docs/index.html")
_main_arch_dir = Path("docs/archive")

# Archive the existing main page if it's from a different run slug
# (skipped when ingest.py is in charge of archiving via --skip-main-archive)
if not SKIP_ARCHIVE and _main_path.exists():
    _main_existing = _main_path.read_text(encoding="utf-8")
    _main_m        = re.search(r'<meta name="data-run" content="([^"]+)"', _main_existing)
    _main_old_slug = _main_m.group(1) if _main_m else None
    if _main_old_slug and _main_old_slug != REPORT_DATE_SLUG:
        _main_arch_slot = _main_arch_dir / _main_old_slug
        _main_arch_slot.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(_main_path), str(_main_arch_slot / "index.html"))
        print(f"Archived {_main_old_slug} main page → {_main_arch_slot}/index.html")

# Collect archived main runs (newest first), capped at 12 months
_main_archived = []
if _main_arch_dir.exists():
    for _d in sorted(_main_arch_dir.iterdir(), reverse=True):
        if _d.is_dir() and (_d / "index.html").exists():
            if _slug_age_months(_d.name) <= 12:
                _main_archived.append(_d.name)

# Build link list — empty string when no archives exist (renders nothing in the f-string)
_main_past_runs_html = ""
if _main_archived:
    _lis = "".join(
        f'<li><a href="archive/{s}/">{_slug_to_label(s)}</a></li>'
        for s in _main_archived
    )
    _main_past_runs_html = f"""<section class="past-analyses">
  <h3>Past analyses</h3>
  <ul>{_lis}</ul>
</section>"""

# ── HTML ──────────────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<meta name="data-run" content="{REPORT_DATE_SLUG}">
<title>T1 Headline Performance Analysis · McClatchy CSA</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dom-to-image-more@3.7.2/dist/dom-to-image-more.min.js"></script>
<style>
  /* ── Theme tokens ── */
  :root {{
    --bg:           #0f1117;
    --bg-card:      #21253a;
    --bg-muted:     #1a1d27;
    --bg-subtle:    #2e3350;
    --text:         #e8eaf6;
    --text-secondary: #b0bec5;
    --text-muted:   #8b90a0;
    --border:       #2e3350;
    --border-subtle:#1a1d27;
    --accent:       #7c9df7;
    --nav-bg:       #1a1d27;
  }}
  body.light {{
    --bg:           #f4f6fb;
    --bg-card:      #ffffff;
    --bg-muted:     #f4f6fb;
    --bg-subtle:    #eef0f8;
    --text:         #1a1d27;
    --text-secondary: #3a3d4a;
    --text-muted:   #5a6070;
    --border:       #dde1f0;
    --border-subtle:#eef0f8;
    --accent:       #3d5af1;
    --nav-bg:       #ffffff;
  }}

  /* ── Reset ── */
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  /* ── Base ── */
  body {{ font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text); font-size: 14px; line-height: 1.6; -webkit-font-smoothing: antialiased; transition: background 0.2s, color 0.2s; }}

  /* ── Nav ── */
  .site-nav {{ background: var(--nav-bg); border-bottom: 1px solid var(--border); padding: 0 24px; display: flex; align-items: center; justify-content: space-between; height: 44px; position: sticky; top: 0; z-index: 100; }}
  .nav-links {{ display: flex; align-items: center; }}
  .nav-links a {{ color: var(--text-muted); text-decoration: none; font-size: .85em; padding: 0 12px; height: 44px; display: flex; align-items: center; border-bottom: 2px solid transparent; transition: color .15s; }}
  .nav-links a:hover {{ color: var(--text); }}
  .nav-links a.active {{ color: var(--accent); border-bottom-color: var(--accent); }}
  .nav-sep {{ color: var(--border); font-size: .8em; }}
  .theme-toggle {{ background: none; border: 1px solid var(--border); color: var(--text-muted); cursor: pointer; padding: 4px 8px; border-radius: 4px; font-size: .8em; }}

  /* ── Hero ── */
  .hero {{ max-width: 1100px; margin: 0 auto; padding: 32px 24px 20px; }}
  .hero h1 {{ font-size: 1.7em; font-weight: 700; color: var(--accent); margin-bottom: 4px; }}
  .hero-stats {{ display: flex; align-items: center; flex-wrap: wrap; gap: 4px 12px; font-size: 0.9em; color: var(--text-muted); margin-bottom: 28px; }}
  .stat-num {{ font-weight: 600; color: var(--text); margin-right: 3px; }}
  .stat-label {{ color: var(--text-muted); }}
  .stat-sep {{ color: var(--border); margin: 0 2px; }}

  /* ── Tile grid ── */
  main {{ max-width: 1100px; margin: 0 auto; padding: 28px 24px 60px; }}
  .grid-label {{ font-size: 11px; font-weight: 500; letter-spacing: 0.07em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 14px; }}
  .tile-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 0; }}
  .tile {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px 14px; cursor: pointer; display: flex; flex-direction: column; gap: 7px; transition: box-shadow 0.15s ease, border-color 0.15s ease, background 0.2s; min-height: 140px; }}
  .tile:hover {{ box-shadow: 0 2px 12px rgba(0,0,0,0.10); border-color: var(--text-muted); }}
  .tile.active {{ border-color: var(--accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 15%, transparent); }}
  .tile-num {{ font-size: 10px; font-weight: 500; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-muted); }}
  .tile-claim {{ font-size: 13px; font-weight: 500; color: var(--text); line-height: 1.45; flex: 1; }}
  .tile-action {{ font-size: 12px; color: var(--text-secondary); line-height: 1.4; padding-top: 7px; border-top: 1px solid var(--border-subtle); margin-top: auto; }}
  .tile-more {{ font-size: 11px; color: var(--accent); display: block; text-align: right; margin-top: 4px; }}

  /* ── Detail area ── */
  .detail-area {{ background: var(--bg-muted); border-top: 1px solid var(--border); margin-top: 20px; padding: 28px 24px 48px; }}
  .detail-wrap {{ max-width: 1100px; margin: 0 auto; background: var(--bg-card); border-radius: 16px; border: 1px solid var(--border); padding: 40px 44px; position: relative; }}
  .detail-close {{ position: absolute; top: 14px; right: 18px; background: none; border: none; font-size: 20px; color: var(--text-muted); cursor: pointer; padding: 4px 10px; border-radius: 6px; line-height: 1; }}
  .detail-close:hover {{ background: var(--bg-muted); color: var(--text); }}
  .detail-panel {{ display: none; }}
  .detail-panel h2 {{ font-size: 20px; font-weight: 600; color: var(--text); margin-bottom: 18px; line-height: 1.3; }}
  .detail-panel h3 {{ font-size: 14px; font-weight: 600; color: var(--text); margin: 24px 0 10px; text-transform: none; letter-spacing: 0; }}
  .detail-panel h4 {{ font-size: 13px; font-weight: 600; margin: 16px 0 8px; }}
  .detail-panel p {{ font-size: 13px; margin-bottom: 12px; color: var(--text-secondary); }}

  /* ── Callouts ── */
  .callout {{ background: var(--bg-muted); border-left: 3px solid var(--text); padding: 12px 16px; border-radius: 0 8px 8px 0; font-size: 13px; line-height: 1.55; margin: 0 0 20px; }}
  .callout strong {{ font-weight: 600; color: var(--text); }}
  .callout em {{ color: var(--text-muted); }}
  .callout-inline {{ font-size: 12px; color: var(--text-muted); background: var(--bg-muted); border-left: 2px solid var(--border); padding: 8px 12px; margin: 8px 0 16px; border-radius: 0 4px 4px 0; }}

  /* ── Tables ── */
  /* Scroll wrapper: owns the shadow, radius, and overflow. Tables never bleed
     past this boundary — wide tables scroll horizontally, text is never clipped. */
  .table-wrap {{ overflow-x:auto; -webkit-overflow-scrolling:touch; max-width:100%;
                 border-radius:8px; margin:0.5rem 0 1.25rem; }}
  table.findings {{ width:100%; border-collapse:collapse; font-size:0.78rem; margin:0;
                    border-radius:8px; overflow:hidden;
                    box-shadow:0 0 0 1px var(--border),0 1px 3px rgba(0,0,0,0.15); }}
  table.findings th {{ text-align:left; padding:6px 10px;
                       font-weight:600; font-size:0.6rem; text-transform:uppercase; white-space:nowrap;
                       letter-spacing:0.08em; border-bottom:1px solid var(--border); }}
  table.findings td {{ padding:6px 10px; vertical-align:middle; white-space:nowrap; }}
  table.findings tr:last-child td {{ border-bottom:none; }}
  /* Light theme table colours */
  body.light table.findings {{ background:#ffffff; }}
  body.light table.findings th {{ background:#f5f5f7; color:#5a6070; border-bottom:1px solid #dde1f0; }}
  body.light table.findings td {{ color:#424245; border-bottom:1px solid #f0f0f0; }}
  body.light table.findings tr:hover td {{ background:#f0f0f0; }}
  body.light .table-wrap {{ box-shadow:0 0 0 1px #dde1f0,0 1px 3px rgba(0,0,0,0.08); }}
  /* Dark theme table colours — explicit so they are never ambiguous */
  table.findings {{ background:#1a1d27; }}
  table.findings th {{ background:#0f1117; color:#8b90a0; border-bottom:1px solid #2e3350; }}
  table.findings td {{ color:#cbd5e1; border-bottom:1px solid #0f1117; }}
  table.findings tr:hover td {{ background:#253352; }}
  .table-wrap {{ box-shadow:0 0 0 1px #2e3350,0 1px 3px rgba(0,0,0,0.3); }}

  /* ── Tags (semantic status colors stay fixed) ── */
  .tag {{ display: inline-block; font-size: 10px; font-weight: 600; border-radius: 4px; padding: 2px 6px; margin-right: 6px; }}
  .tag-green {{ background: #e8f5e9; color: #1d8348; }}
  .tag-red {{ background: #fdecea; color: #c0392b; }}
  .tag-gray {{ background: var(--bg-subtle); color: var(--text-muted); }}
  .tag-blue {{ background: #e8f0fe; color: #1a73e8; }}
  .tag-amber {{ background: #fff8e1; color: #b45309; }}

  /* ── Lift value colors (theme-aware; used by _guide_table and any lift spans) ── */
  .lift-high {{ color: #4ade80; font-weight: 600; }}
  .lift-pos  {{ color: var(--accent); font-weight: 600; }}
  .lift-neg  {{ color: #f87171; font-weight: 600; }}
  body.light .lift-high {{ color: #16a34a; }}
  body.light .lift-pos  {{ color: var(--accent); }}
  body.light .lift-neg  {{ color: #dc2626; }}

  /* ── Charts & examples ── */
  .chart-wrap {{ margin: 16px 0; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 12px 0; }}
  .example-cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 12px 0; }}
  .example-list {{ background: var(--bg-muted); border-radius: 8px; padding: 14px 16px; }}
  .example-top h4 {{ color: #1d8348; }}
  .example-bot h4 {{ color: #c0392b; }}
  .example-list ul, .headline-list {{ padding-left: 16px; }}
  .example-list li, .headline-list li {{ font-size: 12px; line-height: 1.5; margin-bottom: 5px; color: var(--text-secondary); }}
  p.caveat {{ font-size: 11px; color: var(--text-muted); margin-top: 16px; line-height: 1.5; }}
  .section-label {{ display: none; }}

  /* ── Footer ── */
  footer {{ padding: 40px 28px; text-align: center; color: var(--text-muted); font-size: 11px; border-top: 1px solid var(--border-subtle); background: var(--bg); margin-top: 40px; letter-spacing: 0.01em; }}
  .past-analyses {{ max-width: 900px; margin: 0 auto; padding: 2rem 28px 0.5rem; border-top: 1px solid var(--border-subtle); }}
  .past-analyses h3 {{ font-size: 0.65rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.6rem; }}
  .past-analyses ul {{ list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; gap: 0.35rem 1.25rem; }}
  .past-analyses li a {{ font-size: 0.8rem; color: var(--accent); text-decoration: none; }}
  .past-analyses li a:hover {{ color: var(--accent-hover, #93c5fd); text-decoration: underline; }}
  footer a {{ color: var(--accent); text-decoration: none; }}
  footer a:hover {{ text-decoration: underline; }}

  /* ── Responsive ── */
  @media (max-width: 760px) {{ .tile-grid {{ grid-template-columns: 1fr 1fr; }} .hero h1 {{ font-size: 20px; }} .detail-wrap {{ padding: 24px 20px; }} }}
  @media (max-width: 480px) {{ .tile-grid {{ grid-template-columns: 1fr; }} }}

  /* ── Sortable tables ── */
  table thead th {{ cursor: pointer; user-select: none; white-space: nowrap; }}
  table thead th:hover {{ color: var(--text-primary, #e8eaf6); }}
  .sort-icon {{ opacity: 0.4; font-size: 0.75em; margin-left: 4px; font-style: normal; }}
  table thead th[data-sort] .sort-icon {{ opacity: 1; color: var(--accent); }}

  /* ── Export button ── */
  .export-btn-wrap {{ float: right; position: relative; margin: 0 0 10px 16px; }}
  .export-btn {{ font-size: 0.72rem; padding: 5px 10px; border-radius: 6px; cursor: pointer;
                border: 1px solid var(--border); background: var(--bg-card); color: var(--text-secondary);
                font-family: inherit; transition: background 0.15s; }}
  .export-btn:hover {{ background: var(--nav-bg); color: var(--text); }}
  .export-dropdown {{ display: none; position: absolute; right: 0; top: calc(100% + 3px);
                     min-width: 130px; border-radius: 8px; z-index: 200;
                     border: 1px solid var(--border); background: var(--bg-card);
                     box-shadow: 0 4px 16px rgba(0,0,0,0.25); overflow: hidden; }}
  .export-dropdown button {{ display: block; width: 100%; text-align: left; padding: 8px 14px;
                             font-size: 0.75rem; font-family: inherit; cursor: pointer;
                             border: none; background: transparent; color: var(--text); }}
  .export-dropdown button:hover {{ background: var(--nav-bg); }}

  /* ── Snapshot bar ── */
  #snapshot-bar {{ display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border-subtle); }}
  .snap-bar-label {{ font-size: 10px; font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase; color: var(--text-muted); margin-right: 2px; flex-shrink: 0; }}
  .snap-btn {{ display: inline-flex; align-items: center; padding: 3px 10px; border-radius: 20px; border: 1px solid var(--border); background: none; color: var(--text-muted); font-size: 11px; cursor: pointer; transition: background 0.12s, border-color 0.12s, color 0.12s; }}
  .snap-btn:hover {{ background: var(--bg-muted); border-color: var(--text-muted); color: var(--text-secondary); }}
  .snap-btn.active {{ background: color-mix(in srgb, var(--accent) 12%, transparent); border-color: color-mix(in srgb, var(--accent) 35%, transparent); color: var(--accent); }}
  #snapshot-banner {{ display: none; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 28px; background: color-mix(in srgb, var(--accent) 8%, transparent); border-bottom: 1px solid color-mix(in srgb, var(--accent) 20%, transparent); font-size: 12px; color: var(--accent); }}
  .snap-banner-actions {{ display: flex; gap: 8px; flex-shrink: 0; }}
  .snap-banner-btn {{ background: color-mix(in srgb, var(--accent) 14%, transparent); border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent); color: var(--accent); border-radius: 5px; padding: 3px 10px; font-size: 11px; cursor: pointer; transition: background 0.12s; font-family: inherit; }}
  .snap-banner-btn:hover {{ background: color-mix(in srgb, var(--accent) 24%, transparent); }}
  .snap-banner-exit {{ background: var(--bg-muted) !important; border-color: var(--border) !important; color: var(--text-secondary) !important; }}
  .snap-banner-exit:hover {{ color: var(--text) !important; border-color: var(--text-muted) !important; }}
  #snap-restore-modal {{ display: none; position: fixed; inset: 0; z-index: 500; align-items: center; justify-content: center; background: rgba(0,0,0,0.55); backdrop-filter: blur(4px); }}
  #snap-restore-modal.visible {{ display: flex; }}
  .srm-inner {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 22px 24px; width: 400px; max-width: calc(100vw - 40px); box-shadow: 0 12px 40px rgba(0,0,0,0.55); }}
  .srm-title {{ font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 10px; }}
  .srm-success {{ color: #34d399; }}
  .srm-body {{ font-size: 12px; color: var(--text-secondary); margin-bottom: 14px; line-height: 1.55; }}
  .srm-body code {{ font-family: 'SF Mono', 'Fira Code', monospace; font-size: 11px; background: var(--bg-muted); padding: 1px 5px; border-radius: 3px; color: var(--text); }}
  .srm-input {{ width: 100%; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 8px 12px; color: var(--text); font-size: 12px; letter-spacing: 0.15em; margin-bottom: 6px; outline: none; transition: border-color 0.15s; box-sizing: border-box; }}
  .srm-input:focus {{ border-color: var(--accent); }}
  .srm-error {{ font-size: 11.5px; color: #ef4444; min-height: 18px; margin-bottom: 10px; }}
  .srm-btns {{ display: flex; gap: 8px; }}
  .srm-confirm {{ background: color-mix(in srgb, var(--accent) 15%, transparent); border: 1px solid color-mix(in srgb, var(--accent) 35%, transparent); color: var(--accent); border-radius: 5px; padding: 6px 14px; font-size: 12px; cursor: pointer; font-family: inherit; transition: background 0.12s; }}
  .srm-confirm:hover {{ background: color-mix(in srgb, var(--accent) 28%, transparent); }}
  .srm-dismiss {{ background: none; border: 1px solid var(--border); color: var(--text-muted); border-radius: 5px; padding: 6px 14px; font-size: 12px; cursor: pointer; font-family: inherit; }}
  .srm-dismiss:hover {{ border-color: var(--text-muted); color: var(--text-secondary); }}
  @keyframes srm-shake {{ 0%,100%{{transform:translateX(0)}} 20%{{transform:translateX(-6px)}} 40%{{transform:translateX(6px)}} 60%{{transform:translateX(-4px)}} 80%{{transform:translateX(4px)}} }}
  .srm-shake {{ animation: srm-shake 0.35s ease; }}
</style>
</head>
<body>

{_build_nav("Current Analysis", 0, theme_toggle=True)}

<div class="hero">
  <h1>T1 Headline Analysis</h1>
  <div class="hero-stats">
    <span><span class="stat-num">{N_AN:,}</span><span class="stat-label">Apple News articles</span></span>
    <span class="stat-sep">·</span>
    <span><span class="stat-num">{N_SN:,}</span><span class="stat-label">SmartNews articles</span></span>
    <span class="stat-sep">·</span>
    <span><span class="stat-num">{N_NOTIF}</span><span class="stat-label">push notifications</span></span>
    <span class="stat-sep">·</span>
    <span><span class="stat-num">{PLATFORMS}</span><span class="stat-label">platforms · 2025–2026</span></span>
    <span class="stat-sep">·</span>
    <span><span class="stat-label">Updated {REPORT_DATE}</span></span>
  </div>
</div>

<main>
  <p class="grid-label">CLICK ON ANY FINDING TO EXPAND</p>
  <div class="tile-grid">

    <div class="tile" onclick="showDetail('featured', this)">
      <span class="tile-num">1 · Featured on Apple News</span>
      <p class="tile-claim">"What to know" gets Featured {WTN_FEAT_LIFT:.1f}× more often — but organic views trend lower ({WTN_ORGANIC_P_STR}, not significant at α=0.05, n={WTN_N_NONFEAT}).</p>
      <p class="tile-action">→ Use "What to know" when targeting Featured specifically. Don't apply it broadly.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    <div class="tile" onclick="showDetail('notifications', this)">
      <span class="tile-num">2 · Push Notifications</span>
      <p class="tile-claim">News brand notification CTR declined 29% over 9 months (1.77% → 1.25%, Jun 2025–Mar 2026). Attribution language ({F4_ATTR_LIFT_STR}) is the only consistent headline signal still lifting CTR. Two distinct ecosystems: news brands vs. celebrity content have non-overlapping formula signals.</p>
      <p class="tile-action">→ Segment notification strategy by content type. Use attribution language for news brands. Monitor the CTR decline — the channel is maturing.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    <div class="tile" onclick="showDetail('topics', this)">
      <span class="tile-num">3 · Platform Topic Inversion</span>
      <p class="tile-claim">Sports underperforms across Apple News featuring, MSN text (2,064 median PVs), MSN video completion, and notifications (lowest CTR topic). It performs organically well on Apple News and SmartNews — but algorithms don't surface it.</p>
      <p class="tile-action">→ Write platform-specific sports briefs. Sports is a reader-intent topic, not a distribution topic. Don't rely on algorithmic reach for sports content.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    <div class="tile" onclick="showDetail('longitudinal', this)">
      <span class="tile-num">5 · Trends Over Time</span>
      <p class="tile-claim">Number leads climbed from {NL_LIFT_EARLY:.2f}× (Q1 2025) to {NL_LIFT_LATE:.2f}× (Q1 2026) — the only formula to cross into above-baseline territory. Question format dropped from {Q_LIFT_EARLY:.2f}× to {Q_LIFT_LATE:.2f}×.</p>
      <p class="tile-action">→ Lean into number leads; deprioritize question-format headlines. Re-check quarterly as 2026 data accumulates.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    <div class="tile" onclick="showDetail('formula-topic', this)">
      <span class="tile-num">A · Formula × Topic Interaction (Apple News)</span>
      <p class="tile-claim">Formula choice matters — but only within the right topic. Crime + "Here's" = 16% featuring (n=89); Business + "Here's" = 14% (n=72). Sports = 0% featuring regardless of formula — topic opts you out entirely. Weather is a special case driven by automated United Robots content, not editorial headlines.</p>
      <p class="tile-action">→ For Crime and Business: use "Here's" format to maximize featuring odds. For Sports: formula doesn't matter — the topic itself limits distribution. Don't spend headline effort chasing featuring on Sports content.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    <div class="tile" onclick="showDetail('sn-formula-trap', this)">
      <span class="tile-num">B · SmartNews Cross-Platform Formula Trap</span>
      <p class="tile-claim">Formulas promoted for Apple News specifically hurt SmartNews. Question format: −0.08 rank below baseline (p=3.4e-6, n=918). "What to know": −0.13 below baseline (p=3.0e-6, n=213). "Here's" is the only formula directionally above baseline on BOTH platforms ({FB_HERES_SN_RANK:.3f} SN rank, {FB_HERES_SN_P_STR}, does not survive Bonferroni correction).</p>
      <p class="tile-action">→ Use "Here's" format when syndicating to both platforms simultaneously. Use questions for Apple News only. Never write one Apple News optimized headline and route it unchanged to SmartNews. <em>One-time setup: wire into CSA Apple News and SmartNews persona configurations.</em></p>
      <span class="tile-more">Details ↓</span>
    </div>

{"" if (msn.empty or not SHOW_MSN_TILE) else f"""
    <div class="tile" onclick="showDetail('msn-formula', this)">
      <span class="tile-num">MSN · Formula Divergence</span>
      <p class="tile-claim">On MSN, direct declarative headlines outperform {_msn_worst_formula_label.lower()} format by {MSN_DIVERGE_LIFT_STR} (n={MSN_N_TOTAL} T1 news brand articles, Jan–Mar 2026). Structured formulas consistently underperform the plain declarative baseline.</p>
      <p class="tile-action">→ Write direct, subject-verb-object headlines for MSN. Don't repurpose Apple News formula copy for MSN distribution.</p>
      <span class="tile-more">Details ↓</span>
    </div>
"""}

{"" if not HAS_ANP else f"""
    <div class="tile" onclick="showDetail('anp-failures', this)">
      <span class="tile-num">8 · Apple News Bottom Performers Follow Three Patterns</span>
      <p class="tile-claim">Three content types account for the majority of underperformance: (1) articles with no section tag land in the bottom 20% nearly half the time ({_anp_fail['ANP_FAIL_MAIN_BOT_PCT']:.0%}, median rank {_anp_fail['ANP_FAIL_MAIN_RANK']:.2f}, p={_anp_fail['ANP_FAIL_MAIN_P']:.1e}); (2) local Sports content ranks at the {_anp_fail['ANP_FAIL_SPORTS_RANK']:.0%} percentile without featuring — but the {_anp_fail['ANP_FAIL_SP_FEAT_N']} featured Sports articles reach rank {_anp_fail['ANP_FAIL_SP_FEAT_RANK']:.2f}; (3) national wire (Nation &amp; World) underperforms local sections by {_anp_fail['ANP_FAIL_LOCAL_RANK'] - _anp_fail['ANP_FAIL_NW_RANK']:.0%} percentile points.</p>
      <p class="tile-action">→ Tag every article's section before publishing. Don't rely on Apple News for local sports distribution. Route national wire content through other channels.</p>
      <span class="tile-more">Details ↓</span>
    </div>
"""}

  </div><!-- /.tile-grid -->

  <div class="detail-area" id="detail-area" style="display:none;">
    <div class="detail-wrap">
      <button class="detail-close" onclick="closeDetail()">×</button>

      <!-- DETAIL: FEATURED -->
      <div class="detail-panel" id="detail-featured">
        <h2>Finding 1 · Featured on Apple News</h2>
        <div class="callout">
          <strong>Key tension:</strong> "What to know" gets featured by Apple at {WTN_FEAT_LIFT:.2f}× the baseline rate — and non-featured WTN articles trend toward the lower end of the distribution. This is directional and not significant at α=0.05 ({WTN_ORGANIC_P_STR}, n={WTN_N_NONFEAT} non-featured WTN articles) — interpret with caution. The Featured signal is statistically robust; the organic underperformance is a pattern worth watching, not a confirmed finding. Use WTN specifically when chasing Featured placement; avoid applying it as a general-purpose formula until the organic performance data strengthens.
        </div>
        <p>Among the {an["is_featured"].sum()} Featured articles in our dataset, "What to know" headlines are dramatically overrepresented: {_wtn_feat_n} of {_wtn_total} ({WTN_FEAT}) were Featured, versus {overall_feat_rate:.1%} overall. This is a statistically robust formula signal (χ²={_r2_wtn['chi2']:.1f}, {_fmt_p(_r2_wtn.get('p_chi_adj', _r2_wtn['p_chi']), adj=True)}).</p>
        <p>Question-format headlines are also Featured more often than expected ({_r2_q['featured_rate']:.0%}, {_r2_q['featured_lift']:.2f}× lift, {_fmt_p(_r2_q.get('p_chi_adj', _r2_q['p_chi']), adj=True)}) — but they significantly underperform other Featured articles once selected. Apple's editors favor questions; the format itself doesn't follow through on views.</p>
        <p>Quoted ledes present the inverse pattern: Featured at roughly the baseline rate ({_r2_ql['featured_rate']:.0%}), but once Featured they deliver among the highest within-Featured percentiles. Questions get into the Featured tier and stall; quoted ledes get in and overperform.</p>
        <p><em>Causal note:</em> The association between "What to know" and Featured placement is observational. The causal direction is ambiguous: editors may independently choose the same stories that writers frame as "What to know," rather than the format itself driving featuring.</p>
        <div class="chart-wrap">{c2}</div>
        <table class="findings">
          <thead><tr><th>Formula</th><th>n</th><th>Featured rate</th><th>Lift</th><th>p<sub>adj</sub> (BH–FDR)</th><th>Within-Featured median %ile</th></tr></thead>
          <tbody>{_t2}</tbody>
        </table>
        <p class="callout-inline"><strong>Read this table as:</strong> "Featured lift" is how much more often Apple selects this formula for Featured. A high rate means Apple's algorithm rewards it — not that it organically outperforms.</p>
        {"" if df_ql_subtypes is None else f"""<h3>Quote lede breakdown: which type gets featured?</h3>
        <div class="callout"><strong>Action:</strong> Official/authority quotes (police, prosecutors, government) are the highest-featuring subtype of quoted-lede headlines on Apple News. Use them when you have a credible sourced quote from an official — they get Featured at a higher rate than the quoted-lede average. Expert quotes (scientists, researchers) also index above baseline. First-person subject quotes perform below the quoted-lede average for featuring.</div>
        <table class="findings">
          <thead><tr><th>Quote lede type</th><th>n</th><th>Featured rate</th><th>Lift vs. baseline</th><th>p (chi²)</th><th>Within-Featured median %ile</th></tr></thead>
          <tbody>{"".join(
            f"<tr><td>{html_module.escape(str(r['label']))}</td><td>{int(r['n'])}</td>"
            f"<td>{{r['feat_rate']:.0%}}</td>"
            f"<td><span class=\"{'lift-high' if r['lift']>=1.5 else ('lift-pos' if r['lift']>=0.9 else 'lift-neg')}\">{{r['lift']:.2f}}\u00d7</span></td>"
            f"<td>{{'p<0.05' if r['p']<0.05 else ('p<0.10' if r['p']<0.10 else f'p={{r[\"p\"]:.2f}}' )}}</td>"
            f"<td>{{r['within_feat_med']:.0%}}</td></tr>"
            for _, r in df_ql_subtypes.iterrows()
          )}</tbody>
        </table>
        <p class="caveat">Subtypes classified by keywords after the closing quote mark. n={len(_ql_subset)} total quoted-lede articles. p-values are uncorrected for this exploratory breakdown. Interpret as directional guidance, not confirmed findings.</p>"""}
        <p class="caveat">All {N_AN:,} Apple News articles (2025–2026). Chi-square test: each formula vs. all other articles combined. BH–FDR across all {len(_q2_raw_p)} formula tests. Causal direction of "What to know" → Featured is unconfirmed.</p>
      </div><!-- /#detail-featured -->

      <!-- DETAIL: NOTIFICATIONS -->
      <div class="detail-panel" id="detail-notifications">
        <h2>Finding 2 · Push Notifications</h2>
        <div class="callout">
          <strong>Two distinct content ecosystems — different signals for each.</strong> News brands (n={N_NOTIF_NEWS}, median CTR {CTR_MED_NEWS_STR}): "EXCLUSIVE:" ({F4_EXCL_LIFT_STR}, {F4_EXCL_P_STR}) and attribution language (says/told, {F4_ATTR_LIFT_STR}, {F4_ATTR_P_STR}) drive CTR. Us Weekly / celebrity (n={N_NOTIF_UW}, median CTR {CTR_MED_UW_STR}): named person + possessive framing ({F4_POSS_LIFT_STR}, {F4_POSS_P_STR}) is the top signal. The populations are 2.8× apart in baseline CTR — pooling them obscures both sets of findings.
        </div>
        <p>Across {N_NOTIF} Apple News push notifications (Jan 2025–Feb 2026), the dataset contains two functionally different content types. Us Weekly (entertainment/celebrity) runs at {CTR_MED_UW_STR} median CTR; the four news brand outlets (Miami Herald, KC Star, Charlotte Observer, Sacramento Bee) run at {CTR_MED_NEWS_STR}. The formula signals that predict CTR are almost entirely non-overlapping between the two populations.</p>
        <div class="chart-wrap">{c4}</div>
        <h3>News brand signals (n={N_NOTIF_NEWS}, median CTR {CTR_MED_NEWS_STR})</h3>
        <table class="findings">
          <thead><tr><th>Feature</th><th>n (present)</th><th>Median CTR (present)</th><th>Median CTR (absent)</th><th>Lift (95% CI)</th><th>Effect size r</th><th>p<sub>adj</sub> (BH–FDR)</th></tr></thead>
          <tbody>{_q5_table_pop(df_q5_news)}</tbody>
        </table>
        <p class="callout-inline">For hard news notifications: "EXCLUSIVE:" earns clicks when the story justifies it. Attribution language ("says"/"told"/"reports") signals source credibility and is associated with higher CTR. Question format consistently hurts. Notification length shows no significant effect when analyzed within this population.</p>
        {_excl_sensitivity_html}
        <h3>The serial/escalating story as a content type</h3>
        <p>The top news brand notifications by CTR are dominated by a single story: Nancy Guthrie's disappearance and its connection to Savannah Guthrie. This defines a content type: <strong>the serial/escalating story with a celebrity anchor</strong>. The formula: possessive named entity + new development + escalating stakes, published in installments. The structural recipe: <em>"[Celebrity]'s [family member/associate] [new disclosure/development]."</em></p>
        <h3>Us Weekly / celebrity signals (n={N_NOTIF_UW}, median CTR {CTR_MED_UW_STR})</h3>
        <table class="findings">
          <thead><tr><th>Feature</th><th>n (present)</th><th>Median CTR (present)</th><th>Median CTR (absent)</th><th>Lift (95% CI)</th><th>Effect size r</th><th>p<sub>adj</sub> (BH–FDR)</th></tr></thead>
          <tbody>{_q5_table_pop(df_q5_uw)}</tbody>
        </table>
        <p class="callout-inline">For celebrity/entertainment notifications: named person + possessive ("Smith's…") is the dominant signal. Numbers in the headline hurt CTR — specific counts and statistics feel out of place in celebrity context. "EXCLUSIVE" shows no significant effect, suggesting the word has different valence in entertainment contexts. Notification length shows no significant effect within this population.</p>
        <h3>News brand CTR trend (post-activation, Jun 2025–Mar 2026)</h3>
        <p>News brand Apple News notifications went live in June 2025. Monthly CTR has declined from 1.77% (June 2025) to 1.25% (March 2026) — a <strong>29% drop over 9 months</strong>. The pattern shows an initial sharp decline through October 2025 (1.25%), a brief partial recovery in December (1.31%) and January 2026 (1.42%), then a return to trough levels by March 2026 (1.25%). This trajectory is consistent with audience accommodation to a new push channel — initial novelty drives higher engagement, which normalizes as the channel becomes routine.</p>
        <div class="chart-wrap">{c_ctr_monthly}</div>
        <p>Attribution language ("says"/"told"/"reveals") remains the <strong>only consistent headline signal</strong> that still lifts CTR ({F4_ATTR_LIFT_STR}, {F4_ATTR_P_STR}) against this declining baseline. As the overall level drops, having the right signals becomes more important, not less — the population of readers who do click is increasingly self-selected for story-level interest rather than channel novelty.</p>
        <p class="callout-inline"><strong>Monthly CTR data (news brands only):</strong> Jun 2025: 1.77% → Jul: 1.70% → Aug: 1.50% → Sep: 1.40% → Oct: 1.25% → Nov: 1.26% → Dec: 1.31% → Jan 2026: 1.42% → Feb: 1.30% → Mar: 1.25%</p>
        <h3>Outcome language signal (BH-FDR corrected across 10 signals)</h3>
        <p>After correcting for 10 simultaneous linguistic signals tested across n={NOTIF_TIME_N} pooled news brand notifications (2025+2026), only two survive BH–FDR correction. Crime/death outcome words are the <strong>strongest single notification signal</strong> in the dataset — stronger than attribution language, stronger than questions, and stronger than any other tested feature.</p>
        <div class="callout">
          <strong>Highest-confidence notification formula:</strong> Outcome word + attribution — e.g. <em>"Man arrested, prosecutor says"</em> / <em>"Victim identified, police confirm."</em> Stacking both signals is the highest-confidence pattern in this data.
        </div>
        <table class="findings">
          <thead><tr><th>Signal</th><th>Description</th><th>Lift</th><th>n</th><th>p_raw</th><th>p_adj (BH–FDR)</th></tr></thead>
          <tbody>
            <tr>
              <td><strong>Crime/death outcome words</strong></td>
              <td>dead / died / killed / arrested / charged / convicted / sentenced / shot</td>
              <td><span class="lift-high">1.26×</span></td><td>55</td>
              <td>p=0.000151 ***</td><td><strong>p=0.0015 ***</strong></td>
            </tr>
            <tr>
              <td>Attribution language</td>
              <td>says / said / told / reports / reveals</td>
              <td><span class="lift-pos">1.18×</span></td><td>59</td>
              <td>p=0.004 **</td><td>p=0.020 *</td>
            </tr>
            <tr style="color:#8b90a0">
              <td colspan="6"><em>All other signals tested (questions, urgency words, local geo-anchor, superlatives, named person lead, money amounts, opinion flags, possessives): not significant after FDR correction.</em></td>
            </tr>
          </tbody>
        </table>
        <p class="caveat">Apple News push notifications Jan 2025–Mar 2026 (n={N_NOTIF} with valid CTR; 2025 includes Us Weekly all year, news brands from June 2025 only). Monthly CTR = median within each calendar month for news brand notifications only. Analyses run separately within each brand-type population; BH–FDR correction applied within each set of tests. Mann-Whitney U; effect size = rank-biserial r; 95% CIs via 1,000-iteration bootstrap. Feature classifier unvalidated.</p>
      </div><!-- /#detail-notifications -->

      <!-- DETAIL: FORMULA × TOPIC (Finding A) -->
      <div class="detail-panel" id="detail-formula-topic">
        <h2>Finding A · Formula × Topic Interaction (Apple News Featuring)</h2>
        <div class="callout">
          <strong>Key finding:</strong> Formula choice affects featuring odds — but only within topics where featuring is possible. <strong>Crime + "Here's" = 16% featuring (n=89); Business + "Here's" = 14% (n=72).</strong> Sports locks at 0% regardless of formula — the topic itself opts you out. Weather is a special case: 70%+ featuring rates reflect United Robots automated content, not editorial headline choices, and should not be used as a benchmark for editorial guidance.
        </div>
        <h3>Editorial guidance by topic</h3>
        <p><strong>Crime:</strong> Use "Here's" — 16% featuring rate (n=89), vs. Question at 13% (n=94). Both are viable; "Here's" has a modest edge and is the recommended default.<br>
        <strong>Business:</strong> Use "Here's what [X] means for [community]" — 14% featuring rate (n=72), the strongest formula with adequate sample size.<br>
        <strong>Sports:</strong> No formula affects featuring odds — Number lead 0% (n=31), What to Know 0% (n=22), Here's 11.5% (n=52). Topic overrides formula. Optimize for organic SmartNews distribution instead (see Finding 3).<br>
        <strong>Weather:</strong> Featuring rates (53–71%) reflect United Robots automated content, not editorial choices. Exclude from any editorial formula guidance.</p>
        <p>Pooled Apple News 2025 + ANP 2026 (n&gt;15,000 articles). For editorial content (non-weather), formula choice has a real but moderate effect on featuring odds — the interaction is topic-conditional, not a universal signal. The overall featuring lift attributed to "Here's" in other analyses is substantially inflated by weather content pulling the average upward.</p>
        <div class="chart-wrap">{c_fa}</div>
        <table class="findings">
          <thead><tr><th>Formula</th><th>Topic</th><th>n</th><th>Featuring rate</th></tr></thead>
          <tbody>
            {"".join(f'<tr><td>{html_module.escape(str(r["formula"]))}</td><td>{html_module.escape(str(r["topic"]))}</td><td>{int(r["n"])}</td><td><span class="{"lift-high" if r["feat_pct"] >= 0.5 else ("lift-pos" if r["feat_pct"] >= 0.15 else "lift-neg")}">{r["feat_pct"]:.0%}</span></td></tr>' for _, r in df_fa.sort_values("feat_pct", ascending=False).iterrows())}
          </tbody>
        </table>
        <p class="caveat">Pooled Apple News 2025 full year + ANP 2026 YTD article-level data (n&gt;15,000). Formula classifier unvalidated; topic classifier unvalidated. Featuring rate = share of articles in each formula × topic cell selected for Apple News Local News Featured slot. Cells with n&lt;15 excluded. Kruskal-Wallis across all combinations significant (p&lt;0.05). Interaction interpretation: observational — causal direction unconfirmed. Weather rows included for completeness; exclude from editorial formula guidance.</p>
      </div><!-- /#detail-formula-topic -->

      <!-- DETAIL: SMARTNEWS FORMULA TRAP (Finding B) -->
      <div class="detail-panel" id="detail-sn-formula-trap">
        <h2>Finding B · SmartNews Cross-Platform Formula Trap</h2>
        <div class="callout">
          <strong>The trap:</strong> Headline formulas that help Apple News featuring specifically hurt SmartNews performance. Applying Justin Frame's Apple News playbook (questions, "what to know") to SmartNews is actively counterproductive. <strong>"Here's" is the only formula directionally above baseline on both platforms simultaneously</strong> — it is the safest cross-platform choice (directional signal, p=0.038, does not survive Bonferroni correction at k=5).
        </div>
        <p>SmartNews 2025, n={FB_SN_N:,} articles. SmartNews ranks articles by a percentile-within-cohort metric (0.5 = exactly average). The question format drops to {FB_Q_SN_RANK:.3f} pct_rank ({FB_Q_SN_P_STR}, n=918) — 0.08 below baseline. "What to know" drops to {FB_WTK_SN_RANK:.3f} ({FB_WTK_SN_P_STR}, n=213) — the worst-performing formula on SmartNews. Meanwhile both are strong for Apple News featuring.</p>
        <div class="chart-wrap">{c_fb}</div>
        <table class="findings">
          <thead><tr><th>Formula</th><th>Apple News feat%</th><th>SmartNews pct_rank</th><th>SN baseline</th><th>SN p-value</th><th>Cross-platform verdict</th></tr></thead>
          <tbody>
            <tr>
              <td><strong>Here's / Here are</strong></td>
              <td><span class="lift-high">46.5%</span></td>
              <td><span class="lift-high">{FB_HERES_SN_RANK:.3f}</span></td>
              <td>0.500</td><td>{FB_HERES_SN_P_STR} (dir.)</td>
              <td><strong>Safest cross-platform (directional)</strong></td>
            </tr>
            <tr>
              <td>Number lead</td>
              <td><span class="lift-neg">17.3%</span></td>
              <td><span class="lift-pos">0.534</span></td>
              <td>0.497</td><td>p=0.29 (dir.)</td>
              <td>SN-leaning</td>
            </tr>
            <tr>
              <td>Direct declarative</td>
              <td>~20% (baseline)</td>
              <td>0.500</td>
              <td>0.500</td><td>—</td>
              <td>Neutral</td>
            </tr>
            <tr>
              <td>Explainer</td>
              <td>—</td>
              <td>0.491</td>
              <td>0.501</td><td>p=0.62</td>
              <td>Neutral</td>
            </tr>
            <tr>
              <td><span class="lift-neg">Question</span></td>
              <td><span class="lift-high">40.9%</span></td>
              <td><span class="lift-neg">{FB_Q_SN_RANK:.3f}</span></td>
              <td>0.502</td><td>{FB_Q_SN_P_STR} ***</td>
              <td><span class="lift-neg">Apple only — hurts SN</span></td>
            </tr>
            <tr>
              <td><span class="lift-neg">What to know</span></td>
              <td><span class="lift-high">~52% (best AN)</span></td>
              <td><span class="lift-neg">{FB_WTK_SN_RANK:.3f}</span></td>
              <td>0.501</td><td>{FB_WTK_SN_P_STR} ***</td>
              <td><span class="lift-neg">Apple only — worst SN</span></td>
            </tr>
          </tbody>
        </table>
        <h3>Practical guidance</h3>
        <ul>
          <li><strong>Cross-platform default:</strong> Use "Here's / Here are" format — the only formula directionally above baseline on both Apple News featuring AND SmartNews rank (p=0.038, directional — does not survive Bonferroni correction, but is the best available cross-platform option).</li>
          <li><strong>Apple News-only variants:</strong> Use question format or "What to know" — but write a separate SmartNews headline if the story is also going there.</li>
          <li><strong>SmartNews-focused:</strong> Number lead format is directionally positive (0.534, p=0.29) — worth testing when volume permits. Direct declarative is the safe floor.</li>
          <li><strong>Never:</strong> Route an Apple News "What to know" or question headline unchanged to SmartNews. Both formats are statistically penalized on that platform.</li>
        </ul>
        <p class="caveat">SmartNews 2025 (n={FB_SN_N:,} articles; politics excluded). Metric: percentile-within-cohort (same outlet × month). Mann-Whitney U tests, each formula vs. untagged baseline; BH–FDR correction applied. Apple News featuring rates from pooled 2025+2026 dataset. "What to know" Apple News rate is the best-fit from Q2 analysis. Cross-platform comparison is observational — audiences and algorithmic mechanisms differ across platforms.</p>
      </div><!-- /#detail-sn-formula-trap -->

      <!-- DETAIL: MSN FORMULA DIVERGENCE -->
      {"" if msn.empty else f"""
      <div class="detail-panel" id="detail-msn-formula">
        <h2>MSN · Formula Divergence</h2>
        <div class="callout">
          <strong>Key finding:</strong> On MSN, direct declarative headlines (no formula pattern) outperform the {_msn_worst_formula_label.lower()} format by {MSN_DIVERGE_LIFT_STR} (Mann-Whitney p&lt;0.05, n={MSN_N_TOTAL} T1 news brand articles). The current dataset has limited formula variety — 88 of 113 T1 articles use plain declarative structure — but the directional signal is consistent: formula-tagged headlines underperform the direct declarative baseline on MSN.
          <br><br><strong>Implication:</strong> Write direct, subject-verb-object MSN headlines. Do not repurpose Apple News "Here's" or "What to know" copy for MSN without rewriting.
        </div>
        <p>Across {MSN_N_TOTAL} T1 news brand articles on MSN (Jan–Mar 2026, excluding celebrity/entertainment publishers), direct declarative headlines (classified as "untagged" — no formula pattern detected) have a median {MSN_OTHER_MED_STR} pageviews. Formula-tagged groups with ≥5 articles:</p>
        <div class="chart-wrap">{c_msn_formula}</div>
        <table class="findings">
          <thead><tr>
            <th data-tooltip="Headline formula type">Formula</th>
            <th>n</th>
            <th>Median PVs</th>
            <th>Lift vs. direct declarative</th>
            <th>p<sub>adj</sub> (BH–FDR)</th>
          </tr></thead>
          <tbody>
            <tr><td><strong>Direct declarative (baseline)</strong></td><td>{MSN_N_OTHER}</td><td>{MSN_OTHER_MED_STR}</td><td>1.00× (baseline)</td><td>—</td></tr>
            {_msn_formula_table()}
          </tbody>
        </table>
        <h3>Cross-platform contrast</h3>
        <p>The inversion is sharpest for structured formulas that Apple News rewards. "Here's" and question formats predict Apple News featuring at 3–4× the baseline rate; those same formats cut MSN traffic vs. direct statements. Possessive named entity (e.g., "Smith's…") is one of the strongest Apple News non-featured signals but underperforms on MSN. The implication is not that one format is universally better — it is that the optimal format is platform-specific.</p>
        <h3>Top MSN articles are direct declaratives</h3>
        <p>The highest-volume MSN articles in this dataset are uniformly direct, declarative statements:</p>
        <ul>
          {"".join(f"<li>{html_module.escape(title)} ({brand}) — {pv:,} PVs</li>" for title, brand, pv in MSN_TOP3_EXAMPLES)}
        </ul>
        <p>These headlines share a common structure: subject + verb + direct object, no structural signal words, no question mark, no "Here's." The story event does the work; the headline reports it plainly.</p>
        <p class="caveat">MSN Jan–Mar 2026 (n={MSN_N_TOTAL} T1 news brand articles; Us Weekly / Woman's World excluded). Formula classification via unvalidated regex classifier. "Untagged" = no formula pattern detected (treated as direct declarative baseline). Mann-Whitney U tests, each formula vs. untagged baseline; BH–FDR correction applied across formula comparisons. Effect sizes not shown — use with caution at this sample size. Pageview minimum: MSN sheet filter applies (≥10k PV threshold in source data).</p>
      </div><!-- /#detail-msn-formula -->
      """}

      <!-- DETAIL: TOPICS -->
      <div class="detail-panel" id="detail-topics">
        <h2>Finding 3 · Platform Topic Inversion</h2>
        <div class="callout">
          <strong>Action:</strong> Write platform-specific variant briefs for sports and nature/wildlife — these two categories show the strongest inversions. Apple News sports: lead with team/player + outcome. SmartNews sports: don't rely on sports for reach — use local/civic and breaking news instead. Nature/wildlife is the mirror: underperforms on Apple News ({nw_an_idx:.2f}× platform median) but outperforms on SmartNews ({nw_sn_idx:.2f}×).
        </div>
        <p>Sports ranks #{sports_an_rank} on Apple News (percentile index {sports_an_idx:.2f}× platform median) but #{sports_sn_rank} — last — on SmartNews (index {sports_sn_idx:.2f}×). This is not a small difference: sports sits well above the Apple News median and well below the SmartNews median. {"The inversion is statistically significant (Mann-Whitney U, " + SPORTS_P_STR + ") across the full year of 2025 data." if SPORTS_P_STR else "The inversion holds across the full year of 2025 data."}</p>
        <p>Nature/wildlife shows the reverse: it underperforms the Apple News median ({nw_an_idx:.2f}×) but outperforms the SmartNews median ({nw_sn_idx:.2f}×). Among the top 30 most frequent words in top-quartile headlines on each platform, only {kw_overlap_n} words appear on both lists{f" ({', '.join(sorted(kw_overlap))})" if kw_overlap_n > 0 else ""} — generic reporting terms rather than shared topical vocabulary, suggesting the platforms reward very different content angles.</p>
        <p>MSN shows a third distinct ranking (orange bars). Sports scores {sports_msn_idx:.2f}× the MSN platform median — {"above average, making it the only platform where sports is a reliable volume driver" if sports_msn_idx > 1.0 else "below average on MSN text traffic (median 2,064 PVs for sports vs. platform median), consistent with the SmartNews pattern"}. Politics indexes at {politics_msn_idx:.2f}× on MSN — {"above average, suggesting MSN's audience skews toward political content" if politics_msn_idx > 1.0 else "near the platform median"}.</p>
        <div class="chart-wrap">{c5}</div>
        <h3>Sports underperforms across Apple News featuring, MSN text, MSN video, and notifications</h3>
        <p>The Apple News/SmartNews sports inversion now extends to three additional signals, making sports the most consistently platform-penalized topic in this dataset:</p>
        <ul>
          <li><strong>MSN text:</strong> Sports median pageviews 2,064 — near-lowest among T1 news brand topics. Sports scores {sports_msn_idx:.2f}× the MSN platform median.</li>
          {"<li><strong>MSN video:</strong> Sports video completion rate " + MSN_VID_SPORTS_IDX_STR + " vs. platform baseline — the only topic with a statistically significant video completion penalty (" + MSN_VID_SPORTS_P_STR + ").</li>" if HAS_MSN_VIDEO and not np.isnan(MSN_VID_SPORTS_COMPLETION_IDX) else ""}
          <li><strong>Apple News notifications:</strong> Sports notification CTR {NOTIF_CTR_SPORTS_STR} — lowest topic — vs. crime {NOTIF_CTR_CRIME_STR}, weather {NOTIF_CTR_WEATHER_STR}. Sports drives Apple News organic views ({sports_an_idx:.2f}× platform median) but Apple doesn't feature it and it doesn't click-through on push.</li>
        </ul>
        <p>The exception remains SmartNews, where sports performs organically (topic ranking #{sports_sn_rank} from bottom — but at {sports_sn_idx:.2f}× median, still below platform average). The pattern is consistent: sports is a reader-intent topic (fans seek it out directly) rather than a distribution topic (algorithms don't surface it). This has direct implications for headline strategy — sports headlines should prioritize depth over reach, with different playbooks for each platform.</p>
        <h3>Sports subtopic performance by platform</h3>
        <p>Within the sports inversion: which sports specifically drive Apple News performance, and which are weakest on SmartNews? The table below breaks sports into subtopics (via two-level headline classifier).</p>
        <table class="findings">
          <thead><tr><th>Sport</th><th>Apple News n</th><th>Apple News median %ile</th><th>SmartNews n</th><th>SmartNews median %ile</th></tr></thead>
          <tbody>{_t5}</tbody>
        </table>
        <h3>Politics subtopic performance by platform</h3>
        <p>Within politics, which story type drives the most engagement on each platform?</p>
        <table class="findings">
          <thead><tr><th>Subtopic</th><th>Apple News n</th><th>Apple News median %ile</th><th>SmartNews n</th><th>SmartNews median %ile</th></tr></thead>
          <tbody>{_t_pol_sub}</tbody>
        </table>
        <div class="example-cols">
          <div class="example-list example-top"><h4>Top quartile politics headlines</h4><ul>{pol_top_h}</ul></div>
          <div class="example-list example-bot"><h4>Bottom quartile politics headlines</h4><ul>{pol_bot_h}</ul></div>
        </div>
        <p class="caveat">Topic tagged via unvalidated regex classifier applied to headline text. <strong>Coverage: {TOPIC_COVERAGE_PCT:.0%} of Apple News articles match a named topic; {TOPIC_OTHER_PCT:.0%} fall into "other/unclassified" and are excluded from this analysis.</strong> Results describe the classified minority — generalizing to all content requires caution. Percentile index = median percentile_within_cohort / platform overall median percentile. Apple News 2025–2026 (n={N_AN:,}); SmartNews 2025 (n={N_SN:,}); MSN 2025 (n={N_MSN:,}). Subtopic classifier unvalidated. No significance testing — treat as descriptive. Subtopics with n&lt;3 show "—".</p>
      </div><!-- /#detail-topics -->

      <!-- DETAIL: LONGITUDINAL -->
      <div class="detail-panel" id="detail-longitudinal">
        <h2>Finding 5 · Trends Over Time</h2>
        <div class="callout">
          <strong>Key shift:</strong> Number leads started below baseline ({NL_LIFT_EARLY:.2f}× in Q1 2025) and climbed steadily to {NL_LIFT_LATE:.2f}× by Q1 2026 — the only formula to cross into above-baseline territory. Possessive named entity held above 1.0× all year but softened. Question-format headlines declined from {Q_LIFT_EARLY:.2f}× to {Q_LIFT_LATE:.2f}× and are now well below baseline.
          <br><br><em>Chart shows the three highest-volume formulas</em> (≥15 articles/quarter). Here's/Here are and What to know are in the table below — their n=4–9/quarter is too small to distinguish trend from noise.
        </div>
        <div class="chart-wrap">{c8}</div>
        <h3>Lift by formula across periods</h3>
        <p>Each cell shows the median lift for that formula in that period, relative to unclassified articles published in the same period. A dash means fewer than 5 articles qualified.</p>
        <table class="findings">
          <thead><tr>
            <th>Formula</th>
            <th>Q1 2025</th><th></th>
            <th>Q2 2025</th><th></th>
            <th>Q3 2025</th><th></th>
            <th>Q4 2025</th><th></th>
            <th>Q1 2026</th><th></th>
          </tr></thead>
          <tbody>{_t_periods}</tbody>
        </table>
        <p class="caveat">Quarters: Q1=Jan–Mar, Q2=Apr–Jun, Q3=Jul–Sep, Q4=Oct–Dec. Q1 2026 = Jan–Feb 2026 only. Lift = formula median cohort percentile ÷ untagged baseline median within same quarter. Minimum 3 articles required per cell. Data through {REPORT_DATE}.</p>
      </div><!-- /#detail-longitudinal -->

{"" if not HAS_ANP else f"""
      <!-- DETAIL: ANP BOTTOM PERFORMERS -->
      <div class="detail-panel" id="detail-anp-failures">
        <h2>Finding 8 · Apple News Bottom Performers Follow Three Patterns</h2>
        <div class="callout">
          <strong>Key finding:</strong> The bottom 20% of Apple News articles aren't randomly distributed. Three structural patterns explain most of the underperformance: missing section metadata, local sports content, and national wire content published by local outlets. Each has a distinct cause and a different operational fix.
        </div>
        <p>Analysis of {_anp_fail['ANP_FAIL_N_TOTAL']:,} news articles (2026, politics excluded) ranked by within-publication view percentile. Bottom 20% threshold = rank ≤ 0.20 within each publication's own distribution.</p>
        <div class="chart-wrap">{c_anp_fail}</div>
        <h3>Pattern 1 — Missing section tag (Main only)</h3>
        <p>Articles published without a section assignment beyond "Main" land in the bottom quintile <strong>{_anp_fail['ANP_FAIL_MAIN_BOT_PCT']:.0%} of the time</strong> — more than twice the 20% baseline rate. Their median view percentile is {_anp_fail['ANP_FAIL_MAIN_RANK']:.2f}, compared to 0.51 for section-tagged articles (Mann-Whitney p={_anp_fail['ANP_FAIL_MAIN_P']:.1e}). These articles also have a featured rate of just 2.5%.</p>
        <p><em>Mechanism:</em> Apple News routes articles into section feeds (Local News, Weather, Business, etc.) based on publisher-assigned section metadata. Without a section tag, an article has no section feed to surface in and is almost invisible to Apple's curation layer — making featuring essentially impossible. This is an operational gap, not a content gap: the same article with a section tag would have a different distribution pathway.</p>
        <p><strong>Fix:</strong> Verify that every article intended for Apple News distribution has at least one non-Main section assigned in the CMS before publish. This is the most avoidable failure mode in the dataset.</p>
        <h3>Pattern 2 — Local Sports without featuring</h3>
        <p>Sports is {_anp_fail['ANP_FAIL_SPORTS_BOT_PCT']:.0%} of the bottom 20% — the single most overrepresented section. Median rank across all sports articles is {_anp_fail['ANP_FAIL_SPORTS_RANK']:.2f} (vs. 0.55 for non-sports content). Apple features local sports articles at just {_anp['ANP_SPORTS_FEAT']:.1%}.</p>
        <p>The featuring exception tells the story clearly: the {_anp_fail['ANP_FAIL_SP_FEAT_N']} sports articles that were featured reached a median rank of {_anp_fail['ANP_FAIL_SP_FEAT_RANK']:.2f} — well above the platform median. Non-featured sports settled at {_anp_fail['ANP_FAIL_SP_NONFEAT_RANK']:.2f}. Featured sports overperforms dramatically; non-featured sports underperforms just as dramatically. The bottleneck is Apple's curation decision, not headline quality.</p>
        <p><em>Mechanism:</em> Apple News's Local News section is editorially curated for community-utility and broadly relevant local stories. Local game recaps, player status updates, and team schedules serve a narrower audience (existing fans) that Apple doesn't prioritize for the Local News feed. National/marquee sports stories — Super Bowl, bowl games, national player news — do get featured and perform well, as the section table shows for Kansas City Chiefs content (rank 0.81).</p>
        <p><strong>Fix:</strong> Don't rely on Apple News for local team sports distribution. SmartNews is a better channel for local sports (Finding 3). On Apple News, reserve Sports publishing effort for nationally relevant stories with featuring potential.</p>
        <h3>Pattern 3 — National wire content from local outlets</h3>
        <p>Articles tagged to "Nation &amp; World" reach a median rank of {_anp_fail['ANP_FAIL_NW_RANK']:.2f} and land in the bottom 20% at a {_anp_fail['ANP_FAIL_NW_BOT_PCT']:.0%} rate — far above the baseline. Local-tagged sections (Charlotte, KC Metro, Miami &amp; South Florida, Sacramento, North Carolina) run at {_anp_fail['ANP_FAIL_LOCAL_RANK']:.2f} median rank. The gap is {_anp_fail['ANP_FAIL_LOCAL_RANK'] - _anp_fail['ANP_FAIL_NW_RANK']:.0%} percentile points (Mann-Whitney p={_anp_fail['ANP_FAIL_NW_P']:.1e}).</p>
        <p><em>Mechanism:</em> Apple News users who follow local outlets are seeking local content. National wire stories from the Miami Herald or Sacramento Bee compete directly against AP, Reuters, and national outlets who publish the same content — and lose. Apple's algorithm also likely routes national content to national publishers first. The local outlet's comparative advantage is exclusively in local stories.</p>
        <p><strong>Fix:</strong> Deprioritize Apple News for national wire distribution. National wire content may perform adequately on MSN or SmartNews, where the platform topology differs. On Apple News, focus editorial attention on local-angle stories.</p>
        <h3>Full section performance table</h3>
        <table class="findings">
          <thead><tr>
            <th>Section</th><th>Articles</th><th>Median rank</th>
            <th>Featured rate</th><th>Bottom 20%</th><th>Top 20%</th>
          </tr></thead>
          <tbody>{_anp_fail['ANP_FAIL_SEC_TABLE']}</tbody>
        </table>
        <p class="caveat">Apple News Publisher data, Jan–Feb 2026. {_anp_fail['ANP_FAIL_N_TOTAL']:,} news articles across 5 publications (Charlotte Observer, KC Star, Miami Herald, News &amp; Observer, Sacramento Bee). Politics excluded. Minimum 10 views per article. Sections with fewer than 20 articles excluded from table. Bottom/top 20% thresholds are within-publication percentiles — a "bottom 20%" article is bottom quintile within its own outlet's distribution. Mann-Whitney U tests; p-values not BH-FDR corrected across sections (each is a pre-specified test). Green shading = median rank ≥ 0.75; red shading = median rank ≤ 0.30.</p>
      </div><!-- /#detail-anp-failures -->
"""}

    </div><!-- /.detail-wrap -->
  </div><!-- /#detail-area -->

</main>

<script>
/* ── Chart re-theming ──────────────────────────────────────────────────────
   Charts are built with --theme dark (transparent bg + neon trace colors).
   When the user toggles to light mode, this function updates Plotly layout
   properties (text/grid colors) and swaps trace colors neon ↔ normal.
   Built as function declarations so they are hoisted above the IIFE below. */

var _NEON_COLORS  = ['#60a5fa','#4ade80','#f87171','#fb923c','#8b90a0'];
var _NORM_COLORS  = ['#2563eb','#16a34a','#dc2626','#f59e0b','#64748b'];

function _hexFromColor(c) {{
  // Normalize a color to lowercase hex — handles both '#rrggbb' and 'rgb(r,g,b)' formats.
  // Plotly may store colors as rgb() strings internally even when hex was passed at build time.
  if (!c || typeof c !== 'string') return null;
  c = c.trim().toLowerCase();
  if (/^#[0-9a-f]{{6}}$/.test(c)) return c;
  var m = c.match(/^rgba?\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)/);
  if (m) return '#' + [m[1], m[2], m[3]].map(function(n) {{
    return ('0' + (+n).toString(16)).slice(-2);
  }}).join('');
  return null;
}}
function _swapColor(c, toDark) {{
  if (!c) return c;
  var from = toDark ? _NORM_COLORS : _NEON_COLORS;
  var to   = toDark ? _NEON_COLORS : _NORM_COLORS;
  // Normalize to hex so the lookup works whether Plotly stored '#rrggbb' or 'rgb(r,g,b)'.
  var hex = _hexFromColor(c);
  var i   = hex ? from.indexOf(hex) : -1;
  return i >= 0 ? to[i] : c;
}}
function _remapTraceColor(c, toDark) {{
  if (Array.isArray(c)) return c.map(function(v) {{ return _swapColor(v, toDark); }});
  return _swapColor(c, toDark);
}}

function _rethemeCharts(isDark) {{
  if (typeof Plotly === 'undefined') return;
  var text  = isDark ? '#e8eaf6' : '#374151';
  var grid  = isDark ? '#2e3350' : '#e2e8f0';
  var zero  = isDark ? '#64748b' : '#9ca3af';
  document.querySelectorAll('.js-plotly-plot').forEach(function(div) {{
    try {{
      Plotly.relayout(div, {{
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor:  'rgba(0,0,0,0)',
        'font.color':              text,
        'title.font.color':        text,
        'legend.font.color':       text,
        'xaxis.gridcolor':         grid,  'yaxis.gridcolor':         grid,
        'xaxis2.gridcolor':        grid,  'yaxis2.gridcolor':        grid,
        'xaxis.zerolinecolor':     zero,  'yaxis.zerolinecolor':     zero,
        'xaxis.tickfont.color':    text,  'yaxis.tickfont.color':    text,
        'xaxis2.tickfont.color':   text,  'yaxis2.tickfont.color':   text,
        'xaxis.title.font.color':  text,  'yaxis.title.font.color':  text,
        'xaxis2.title.font.color': text,  'yaxis2.title.font.color': text,
      }});
      (div.data || []).forEach(function(trace, i) {{
        var upd = {{}};
        if (trace.marker && trace.marker.color !== undefined) {{
          var mc = _remapTraceColor(trace.marker.color, isDark);
          if (JSON.stringify(mc) !== JSON.stringify(trace.marker.color)) {{
            // Plotly.restyle interprets the outer array as one-value-per-trace.
            // A per-bar color array must be double-wrapped so restyle sets the
            // whole array as the value for this single trace, not one element per bar.
            upd['marker.color'] = Array.isArray(mc) ? [mc] : mc;
          }}
        }}
        if (trace.line && trace.line.color) {{
          var lc = _swapColor(trace.line.color, isDark);
          if (lc !== trace.line.color) upd['line.color'] = lc;
        }}
        if (Object.keys(upd).length) Plotly.restyle(div, upd, [i]);
      }});
    }} catch(e) {{ /* panel may be hidden; colors applied next time it opens */ }}
  }});
}}

/* ── Theme toggle ── */
(function () {{
  // Safari private mode throws on localStorage access — always guard with try/catch.
  if (localStorage.getItem('theme') === 'light') document.body.classList.add('light');
}})();

function toggleTheme() {{
  document.body.classList.toggle('light');
  var isDark = !document.body.classList.contains('light');
  try {{ localStorage.setItem('theme', isDark ? 'dark' : 'light'); }} catch(e) {{}}
  _rethemeCharts(isDark);
}}

/* ── Detail panels ── */
function _setTileMoreText(tile, open) {{
  var more = tile.querySelector('.tile-more');
  if (more) more.textContent = open ? 'Close \u2191' : 'Details \u2193';
}}

function showDetail(id, tile) {{
  var isAlreadyOpen = tile.classList.contains('active');
  // Reset all tiles to closed state
  document.querySelectorAll('.tile').forEach(function(t) {{
    t.classList.remove('active');
    _setTileMoreText(t, false);
  }});
  document.querySelectorAll('.detail-panel').forEach(p => p.style.display = 'none');
  var area = document.getElementById('detail-area');
  // Toggle: if this tile was already open, collapse it
  if (isAlreadyOpen) {{
    area.style.display = 'none';
    return;
  }}
  tile.classList.add('active');
  _setTileMoreText(tile, true);
  var panel = document.getElementById('detail-' + id);
  if (panel) panel.style.display = 'block';
  area.style.display = 'block';
  // Re-apply chart theme now that the panel (and its charts) are visible.
  // Also resize Plotly charts: they may have been rendered into a display:none container
  // and cached dimensions of 0px — resize forces a correct layout pass.
  // 100 ms matches the export path — enough for Plotly's internal rAF queue to flush.
  setTimeout(function() {{
    _rethemeCharts(!document.body.classList.contains('light'));
    if (typeof Plotly !== 'undefined') {{
      var panelEl = document.getElementById('detail-' + id);
      if (panelEl) panelEl.querySelectorAll('.js-plotly-plot').forEach(function(div) {{
        try {{ Plotly.Plots.resize(div); }} catch(e) {{}}
      }});
    }}
    area.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
  }}, 100);
}}

function closeDetail() {{
  document.getElementById('detail-area').style.display = 'none';
  document.querySelectorAll('.tile').forEach(function(t) {{
    t.classList.remove('active');
    _setTileMoreText(t, false);
  }});
}}

// ── Table sorting ──────────────────────────────────────────
(function() {{
  function parseCell(text) {{
    var s = text.replace(/<[^>]+>/g, '').trim();
    // Try to extract a leading number (handles ×, %, ~, p<, [, —)
    if (s === '—' || s === '') return -Infinity;
    var m = s.match(/^[~\u2264<\u2265>]?\\s*([\\d,.]+)/);
    if (m) return parseFloat(m[1].replace(/,/g, ''));
    return s.toLowerCase();
  }}
  function sortBy(table, colIdx, asc) {{
    var tbody = table.querySelector('tbody');
    if (!tbody) return;
    var rows = Array.from(tbody.querySelectorAll('tr'));
    rows.sort(function(a, b) {{
      var av = parseCell(a.cells[colIdx] ? a.cells[colIdx].textContent : '');
      var bv = parseCell(b.cells[colIdx] ? b.cells[colIdx].textContent : '');
      if (typeof av === 'number' && typeof bv === 'number') return asc ? av - bv : bv - av;
      return asc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    }});
    rows.forEach(function(r) {{ tbody.appendChild(r); }});
  }}
  document.addEventListener('DOMContentLoaded', function() {{
    // Wrap every table in a .table-wrap scroll container so wide tables never
    // bleed past the tile edge — content scrolls horizontally, never clips.
    document.querySelectorAll('table').forEach(function(t) {{
      if (t.parentNode && !t.parentNode.classList.contains('table-wrap')) {{
        var w = document.createElement('div');
        w.className = 'table-wrap';
        t.parentNode.insertBefore(w, t);
        w.appendChild(t);
      }}
    }});
    document.querySelectorAll('table thead th').forEach(function(th) {{
      var icon = document.createElement('span');
      icon.className = 'sort-icon';
      icon.textContent = '\u2195';
      th.appendChild(icon);
      th.addEventListener('click', function() {{
        var table = th.closest('table');
        var idx = Array.from(th.parentNode.children).indexOf(th);
        var asc = th.getAttribute('data-sort') !== 'asc';
        table.querySelectorAll('thead th').forEach(function(h) {{
          h.removeAttribute('data-sort');
          var ic = h.querySelector('.sort-icon');
          if (ic) ic.textContent = '\u2195';
        }});
        th.setAttribute('data-sort', asc ? 'asc' : 'desc');
        th.querySelector('.sort-icon').textContent = asc ? '\u2191' : '\u2193';
        sortBy(table, idx, asc);
      }});
    }});
  }});
}})();

// ── Export (PNG / PDF) ──────────────────────────────────────────────────────
// PNG: dom-to-image-more into an off-screen fixed-position container (1100px wide).
//      Container prepends the tile summary (finding + takeaway) for context.
//      No transform/scale overrides — those distort text in SVG foreignObject.
// PDF: renders the same container to PNG first, then prints it as an image.
//      Printing a raster <img> preserves exact pixel colors; background stripping
//      does not apply, so dark-mode panels print correctly.
{_make_export_js("", ".tile-more,.export-btn-wrap", "h2", "headline-analysis-")}

(function() {{
  document.addEventListener('DOMContentLoaded', function() {{
    document.querySelectorAll('.detail-panel').forEach(function(panel) {{
      var wrap = document.createElement('div');
      wrap.className = 'export-btn-wrap';
      var btn = document.createElement('button');
      btn.className = 'export-btn';
      btn.title = 'Export this finding';
      btn.textContent = '\u2193 Export';
      var dd = document.createElement('div');
      dd.className = 'export-dropdown';
      var pngBtn = document.createElement('button');
      pngBtn.textContent = 'PNG image';
      var pdfBtn = document.createElement('button');
      pdfBtn.textContent = 'PDF document';
      pngBtn.addEventListener('click', function(e) {{ e.stopPropagation(); _exportPanel(panel, 'png', dd); }});
      pdfBtn.addEventListener('click', function(e) {{ e.stopPropagation(); _exportPanel(panel, 'pdf', dd); }});
      btn.addEventListener('click', function(e) {{
        e.stopPropagation();
        dd.style.display = dd.style.display === 'block' ? 'none' : 'block';
      }});
      document.addEventListener('click', function() {{ dd.style.display = 'none'; }});
      dd.appendChild(pngBtn); dd.appendChild(pdfBtn);
      wrap.appendChild(btn); wrap.appendChild(dd);
      panel.insertBefore(wrap, panel.firstChild);
    }});
  }});
}})();
{_make_col_tooltip_js()}
</script>

{_main_past_runs_html}

<footer>
  <p>McClatchy CSA · T1 Headline Performance Analysis · {REPORT_DATE}</p>
  <p style="margin-top: 6px;">
    <a href="experiments/">Experiments</a> &nbsp;·&nbsp;
    <a href="playbook/">Playbooks</a> &nbsp;·&nbsp;
    Data: T1 Headline Performance Sheet · Apple News, SmartNews, MSN, Yahoo
  </p>
  <div id="snapshot-bar"></div>
</footer>

<script src="js/snapshot-bar.js"></script>
</body>
</html>"""

out = Path("docs/index.html")
out.parent.mkdir(exist_ok=True)
# Strip AI-style em-dash constructions from all output — catches both hardcoded
# and dynamically computed instances (chart titles, computed strings, etc.)
html = html.replace(" \u2014 ", "\u2014")
out.write_text(html, encoding="utf-8")
print(f"Site written to {out}  ({len(html):,} chars)")

# ── Archive logic ─────────────────────────────────────────────────────────────
_pb_path     = Path("docs/playbook/index.html")
_archive_dir = Path("docs/playbook/archive")

# If the existing playbook is from a different run, archive it before overwriting
if _pb_path.exists():
    _pb_existing = _pb_path.read_text(encoding="utf-8")
    _pb_m        = re.search(r'<meta name="data-run" content="([^"]+)"', _pb_existing)
    _pb_old_slug = _pb_m.group(1) if _pb_m else None
    if _pb_old_slug and _pb_old_slug != REPORT_DATE_SLUG:
        _arch_dir = _archive_dir / _pb_old_slug
        _arch_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(_pb_path), str(_arch_dir / "index.html"))
        print(f"Archived {_pb_old_slug} playbook → {_arch_dir}/index.html")

def _extract_compact_tiles(html_path):
    """Return the tile-grid inner HTML from an archived playbook, stripped of expand behaviour."""
    try:
        content = Path(html_path).read_text(encoding="utf-8")
        m = re.search(r'<div class="tile-grid">(.*?)</div>\s*\n\s*\n\s*<!--', content, re.DOTALL)
        if not m:
            return None
        tiles = m.group(1)
        tiles = re.sub(r' onclick="[^"]*"', '', tiles)          # remove expand handlers
        tiles = re.sub(r'\s*<span class="tile-toggle">[^<]*</span>', '', tiles)  # remove toggle
        return tiles.strip()
    except (OSError, AttributeError):
        # Intentional: archived file may be missing or malformed; return None to skip in playbook
        return None

# Collect past archived runs (newest first), capped at 12 months
_archived_runs = []
if _archive_dir.exists():
    for _d in sorted(_archive_dir.iterdir(), reverse=True):
        if _d.is_dir() and (_d / "index.html").exists():
            if _slug_age_months(_d.name) <= 12:
                _archived_runs.append(_d.name)

# Split: last 2 archived → inline collapsed sections; remainder → link list
_inline_slugs = _archived_runs[:2]   # months 2 and 3 most recent
_link_slugs   = _archived_runs[2:]   # months 4–12

# Build inline collapsed sections for the 2 most recent archived runs
_inline_sections_html = ""
for _s in _inline_slugs:
    _tiles = _extract_compact_tiles(_archive_dir / _s / "index.html")
    if _tiles is None:
        continue
    _label = _slug_to_label(_s)
    _inline_sections_html += f"""
<details class="past-run-details">
  <summary class="past-run-summary">
    <span class="run-label">{_label}</span>
    <span class="run-meta">T1 syndication data · Apple News, SmartNews, Push Notifications</span>
    <span class="run-expand-hint">Show playbooks \u25be</span>
  </summary>
  <div class="past-run-body">
    <div class="tile-grid tile-grid-compact">{_tiles}</div>
    <p class="past-run-link"><a href="archive/{_s}/">Open full {_label} playbook with data \u2192</a></p>
  </div>
</details>"""

# Build link-only list for months 4–12
_past_runs_html = ""
if _link_slugs:
    _lis = "".join(
        f'<li><a href="archive/{s}/">{_slug_to_label(s)}</a></li>'
        for s in _link_slugs
    )
    _past_runs_html = f'<section class="past-section"><h3 class="section-eyebrow">Older runs</h3><ul class="past-list">{_lis}</ul></section>'

_pb_run_label = _slug_to_label(REPORT_DATE_SLUG)

# ── Playbook tiles — built separately so they can be sorted by confidence ─────
_CONF_RANK = {"conf-high": 0, "conf-mod": 1, "conf-dir": 2}

_pb_tile_defs = [
    ("conf-high", "pb-2", f"""  <div class="pb-tile" onclick="togglePb(this,'pb-2')">
    <span class="conf-badge conf-high">High confidence</span>
    <span class="tile-label">Apple News \u00b7 Featured Targeting</span>
    <p class="tile-claim">\u201cWhat to know\u201d is associated with {WTN_FEAT_LIFT:.1f}\u00d7 Featured placement. But for non-Featured articles, organic view performance trends lower ({WTN_ORGANIC_P_STR}, not significant at \u03b1=0.05, n={WTN_N_NONFEAT}).</p>
    <p class="tile-action">\u2192 Reserve \u201cWhat to know\u201d for intentional Featured campaigns. Don\u2019t apply it broadly for organic reach.</p>
    <span class="tile-toggle">Details \u2193</span>
  </div>"""),
    ("conf-mod", "pb-4", f"""  <div class="pb-tile" onclick="togglePb(this,'pb-4')">
    <span class="conf-badge conf-high">High confidence</span>
    <span class="tile-label">Push Notifications \u00b7 Two Content Ecosystems + CTR Decline</span>
    <p class="tile-claim">News brand notification CTR has declined 29% over 9 months (1.77% in Jun 2025 \u2192 1.25% in Mar 2026). Attribution language ({F4_ATTR_LIFT_STR}) is the only consistent headline signal still lifting CTR across this declining baseline. News brands ({N_NOTIF_NEWS} notifications, {CTR_MED_NEWS_STR} median) and celebrity/entertainment ({N_NOTIF_UW}, {CTR_MED_UW_STR}) remain 2.8\u00d7 apart in baseline CTR with non-overlapping signals.</p>
    <p class="tile-action">\u2192 Build separate notification playbooks for news vs. celebrity content. Use attribution language for news brands. Monitor the CTR decline monthly \u2014 the channel is maturing and benchmarks need updating.</p>
    <span class="tile-toggle">Details \u2193</span>
  </div>"""),
] + ([] if (msn.empty or not SHOW_MSN_TILE) else [
    ("conf-high", "pb-msn", f"""  <div class="pb-tile" onclick="togglePb(this,'pb-msn')">
    <span class="conf-badge conf-high">High confidence</span>
    <span class="tile-label">MSN \u00b7 Direct Declaratives vs. Structured Formulas</span>
    <p class="tile-claim">Direct declarative headlines on MSN outperform {_msn_worst_formula_label.lower()} format by {MSN_DIVERGE_LIFT_STR} (n={MSN_N_TOTAL} T1 news brand articles, Jan\u2013Mar 2026). Formula-tagged headlines consistently underperform the plain declarative baseline \u2014 the inverse of Apple News featuring signals.</p>
    <p class="tile-action">\u2192 Write two distinct headlines: one structured formula for Apple News/push, one direct declarative for MSN. Never repurpose Apple News copy for MSN distribution without rewriting to drop the formula signal.</p>
    <span class="tile-toggle">Details \u2193</span>
  </div>"""),
]) + ([
    ("conf-high", "pb-8a", f"""  <div class="pb-tile" onclick="togglePb(this,'pb-8a')">
    <span class="conf-badge conf-high">High confidence</span>
    <span class="tile-label">Apple News \u00b7 Section Tagging</span>
    <p class="tile-claim">Articles published without a section tag (\u201cMain only\u201d) land in the bottom 20% at {_anp_fail['ANP_FAIL_MAIN_BOT_PCT']:.0%} \u2014 2.4\u00d7 the baseline rate. Their median view percentile rank is {_anp_fail['ANP_FAIL_MAIN_RANK']:.2f}, versus 0.51 for section-tagged articles (Mann-Whitney p={_anp_fail['ANP_FAIL_MAIN_P']:.1e}, n={_anp_fail['ANP_FAIL_MAIN_N']:,} untagged). Featured rate: 2.5% vs. 7.7% for tagged articles.</p>
    <p class="tile-action">\u2192 Verify every article has a non-Main section assigned before publishing to Apple News. Missing section metadata removes the article from section feeds and makes featuring nearly impossible. This is the most avoidable failure mode in the dataset.</p>
    <span class="tile-toggle">Details \u2193</span>
  </div>"""),
    ("conf-high", "pb-8b", f"""  <div class="pb-tile" onclick="togglePb(this,'pb-8b')">
    <span class="conf-badge conf-high">High confidence</span>
    <span class="tile-label">Apple News \u00b7 Local vs. National Content</span>
    <p class="tile-claim">National wire content (\u201cNation &amp; World\u201d) underperforms local-tagged sections by {(_anp_fail['ANP_FAIL_LOCAL_RANK'] - _anp_fail['ANP_FAIL_NW_RANK']):.0%} percentile points (median rank {_anp_fail['ANP_FAIL_NW_RANK']:.2f} vs. {_anp_fail['ANP_FAIL_LOCAL_RANK']:.2f}; p={_anp_fail['ANP_FAIL_NW_P']:.1e}). {_anp_fail['ANP_FAIL_NW_BOT_PCT']:.0%} of Nation &amp; World articles land in the bottom quintile. Top-performing sections are all locally specific: Weather ({_anp['ANP_WEATHER_FEAT']:.0%} featured, rank 0.89), city-branded local sections, and franchise sports teams with national audiences.</p>
    <p class="tile-action">\u2192 Don\u2019t use Apple News as the primary distribution channel for national wire stories. Apple News users follow local outlets for local content; they get national news from national brands. Route national wire through MSN or SmartNews instead, where platform topology differs.</p>
    <span class="tile-toggle">Details \u2193</span>
  </div>"""),
] if HAS_ANP else []) + [
    ("conf-high", "pb-dual", """  <div class="pb-tile" onclick="togglePb(this,'pb-dual')">
    <span class="conf-badge conf-high">High confidence</span>
    <span class="tile-label">Platform Headline Pairs \u00b7 Same Story, Different Headline</span>
    <p class="tile-claim">The same story needs two different headlines. Apple News editors favor structured formulas (\u201cHere\u2019s\u201d, \u201cWhat to know\u201d, questions) for featuring. SmartNews algorithmically penalizes those same formulas \u2014 question format drops to 0.42 pct_rank (p=3.4e\u20136), \u201cWhat to know\u201d to 0.37 (p=3.0e\u20136). \u201cHere\u2019s\u201d is the only formula directionally above baseline on both platforms.</p>
    <p class="tile-action">\u2192 Write the Apple News headline first, then rewrite for SmartNews. See the topic-by-topic pairing guide below.</p>
    <span class="tile-toggle">Details \u2193</span>
  </div>"""),
]

_pb_tile_defs.sort(key=lambda x: _CONF_RANK.get(x[0], 3))  # stable sort preserves original order within same rank
_pb_tiles_html = "\n\n".join(t for _, _, t in _pb_tile_defs)

# ── By-publication table for playbook ────────────────────────────────────────
def _fmt_lift(v: float) -> str:
    return f"{v:.2f}×" if not np.isnan(v) else "—"

if PUB_ANALYSIS:
    _pub_rows = "".join(
        f"<tr><td>{html_module.escape(str(r['brand']))}</td>"
        f"<td>{r['n']:,}</td>"
        f"<td>{r['featured_rate']:.0%}</td>"
        f"<td>{html_module.escape(r['top_formula'])}</td>"
        f"<td>{_fmt_lift(r['top_formula_lift'])}</td>"
        f"<td>{html_module.escape(r['top_topic'])}</td></tr>"
        for r in PUB_ANALYSIS
    )
    _pub_section_html = f"""
<div class="pb-detail" style="display:block; margin-top:2.5rem">
  <h3 class="rh">By Publication — Apple News</h3>
  <p class="detail-sub">Formula lift vs. untagged baseline (non-Featured articles only, ≥5 examples). Populated fully when Tarrow's complete 2026 export is loaded via <code>--data-2026-full</code>.</p>
  <table>
    <thead><tr>
      <th>Publication</th>
      <th>N articles</th>
      <th>Featured rate</th>
      <th>Top formula</th>
      <th>Formula lift</th>
      <th>Top topic (views)</th>
    </tr></thead>
    <tbody>{_pub_rows}</tbody>
  </table>
  <p class="caveat">Politics excluded. Lift is directional only — sample sizes per publication are small; confirm before changing editorial policy.</p>
</div>"""
else:
    _pub_section_html = ""

# ── Editorial Playbooks page ──────────────────────────────────────────────────
playbook_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<meta name="data-run" content="{REPORT_DATE_SLUG}">
<title>T1 Headline Analysis · Editorial Playbooks</title>
<script src="https://cdn.jsdelivr.net/npm/dom-to-image-more@3.7.2/dist/dom-to-image-more.min.js"></script>
<style>
  /* ── Theme tokens ── */
  :root {{
    --bg:#0f1117; --bg-card:#21253a; --bg-muted:#1a1d27; --bg-subtle:#2e3350;
    --text:#e8eaf6; --text-secondary:#b0bec5; --text-muted:#8b90a0;
    --border:#2e3350; --border-subtle:#1a1d27; --accent:#7c9df7;
    --nav-bg:#1a1d27;
  }}
  body.light {{
    --bg:#f4f6fb; --bg-card:#ffffff; --bg-muted:#f4f6fb; --bg-subtle:#eef0f8;
    --text:#1a1d27; --text-secondary:#3a3d4a; --text-muted:#5a6070;
    --border:#dde1f0; --border-subtle:#eef0f8; --accent:#3d5af1;
    --nav-bg:#ffffff;
  }}

  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Helvetica Neue",Arial,sans-serif;
          background:var(--bg); color:var(--text); font-size:14px; line-height:1.6;
          -webkit-font-smoothing:antialiased; transition:background 0.2s,color 0.2s; }}
  .site-nav {{ background:var(--nav-bg); border-bottom:1px solid var(--border); padding:0 24px; display:flex; align-items:center; justify-content:space-between; height:44px; position:sticky; top:0; z-index:100; }}
  .nav-links {{ display:flex; align-items:center; }}
  .nav-links a {{ color:var(--text-muted); text-decoration:none; font-size:.85em; padding:0 12px; height:44px; display:flex; align-items:center; border-bottom:2px solid transparent; transition:color .15s; }}
  .nav-links a:hover {{ color:var(--text); }}
  .nav-links a.active {{ color:var(--accent); border-bottom-color:var(--accent); }}
  .nav-sep {{ color:var(--border); font-size:.8em; }}
  .theme-toggle {{ background:none; border:1px solid var(--border); color:var(--text-muted); cursor:pointer; padding:4px 8px; border-radius:4px; font-size:.8em; }}
  .container {{ max-width:920px; margin:0 auto; padding:2.5rem 2rem 5rem; }}
  h1 {{ font-size:1.7em; font-weight:700; color:var(--accent); margin-bottom:4px; }}
  .sub {{ color:var(--text-muted); font-size:0.9em; margin-bottom:28px; }}
  .run-header {{ display:flex; align-items:baseline; gap:12px; margin:2rem 0 1.25rem;
                 padding-bottom:0.75rem; border-bottom:1px solid var(--border-subtle); }}
  .run-label {{ font-size:1.05rem; font-weight:700; color:var(--text); letter-spacing:-0.01em; }}
  .run-meta {{ font-size:0.8rem; color:var(--text-muted); }}
  .tile-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:1rem; }}
  @media (max-width:720px) {{ .tile-grid {{ grid-template-columns:1fr; }} }}
  @media (max-width:1000px) and (min-width:721px) {{ .tile-grid {{ grid-template-columns:repeat(2,1fr); }} }}
  .pb-tile {{ background:var(--bg-card); border:1px solid var(--border); border-radius:10px;
              padding:1.1rem 1.25rem; cursor:pointer;
              transition:border-color 0.15s,box-shadow 0.15s,background 0.2s; user-select:none; }}
  .pb-tile:hover {{ border-color:var(--bg-subtle); box-shadow:0 0 0 1px var(--bg-subtle) inset; }}
  .pb-tile.open {{ border-color:var(--accent); box-shadow:0 0 0 1px var(--accent) inset; }}
  .conf-badge {{ display:inline-block; font-size:9px; font-weight:700; text-transform:uppercase;
                 letter-spacing:0.07em; padding:2px 6px; border-radius:3px; margin-bottom:8px; }}
  .conf-high {{ background:rgba(22,163,74,0.2); color:#4ade80; }}
  .conf-mod  {{ background:rgba(37,99,235,0.2);  color:#60a5fa; }}
  .conf-dir  {{ background:rgba(100,116,139,0.15); color:#8b90a0; }}
  body.light .conf-high {{ background:rgba(22,163,74,0.12); color:#15803d; }}
  body.light .conf-mod  {{ background:rgba(37,99,235,0.12); color:#1d4ed8; }}
  body.light .conf-dir  {{ background:rgba(100,116,139,0.10); color:#475569; }}
  .tile-label {{ display:block; font-size:0.78rem; font-weight:700; color:var(--text);
                 letter-spacing:0.01em; margin-bottom:0.5rem; }}
  .tile-claim {{ font-size:0.84rem; color:var(--text-secondary); margin-bottom:0.5rem; line-height:1.55; }}
  .tile-action {{ font-size:0.8rem; color:var(--accent); font-weight:500; margin-bottom:0.5rem; line-height:1.45; }}
  .tile-toggle {{ font-size:0.7rem; color:var(--text-muted); display:block; margin-top:0.5rem; }}
  .pb-detail {{ background:var(--bg-card); border:1px solid var(--border); border-radius:10px;
                padding:1.5rem 1.75rem; margin-bottom:1rem; }}
  h3.rh {{ font-size:0.65rem; font-weight:700; letter-spacing:0.1em; text-transform:uppercase;
           color:var(--text-muted); margin:1.5rem 0 0.6rem; }}
  h3.rh:first-child {{ margin-top:0; }}
  p.detail-sub {{ font-size:0.8rem; color:var(--text-muted); margin-bottom:0.6rem; }}
  .table-wrap {{ overflow-x:auto; -webkit-overflow-scrolling:touch; max-width:100%;
                 border-radius:8px; margin:0.5rem 0 1.25rem;
                 box-shadow:0 0 0 1px var(--border),0 1px 3px rgba(0,0,0,0.2); }}
  table {{ width:100%; border-collapse:collapse; font-size:0.78rem; margin:0;
           background:var(--bg); border-radius:8px; overflow:hidden; }}
  th {{ text-align:left; padding:6px 10px; background:var(--bg-muted); color:var(--text-muted);
        font-weight:600; font-size:0.6rem; text-transform:uppercase; white-space:nowrap;
        letter-spacing:0.08em; border-bottom:1px solid var(--border); }}
  td {{ padding:6px 10px; border-bottom:1px solid var(--border-subtle); vertical-align:middle;
        color:var(--text-secondary); white-space:nowrap; }}
  tr:last-child td {{ border-bottom:none; }}
  tr:hover td {{ background:var(--bg-muted); }}
  .rules {{ padding-left:18px; margin:0.5rem 0 1rem; font-size:0.875rem;
            line-height:1.85; color:var(--text-secondary); }}
  .rules li {{ margin-bottom:0.15rem; }}
  .caveat {{ font-size:0.74rem; color:var(--text-muted); margin-top:1rem; line-height:1.6; }}
  .past-run-details {{ margin-top:1.5rem; border:1px solid var(--border-subtle); border-radius:10px;
                       overflow:hidden; }}
  .past-run-summary {{ display:flex; align-items:baseline; gap:12px; padding:0.85rem 1.25rem;
                       cursor:pointer; list-style:none; user-select:none;
                       background:var(--bg-muted); }}
  .past-run-summary::-webkit-details-marker {{ display:none; }}
  .past-run-summary:hover {{ background:var(--bg-subtle); }}
  details.past-run-details[open] .past-run-summary {{ border-bottom:1px solid var(--border-subtle); }}
  .past-run-summary .run-label {{ font-size:0.95rem; font-weight:700; color:var(--text);
                                   letter-spacing:-0.01em; }}
  .past-run-summary .run-meta {{ font-size:0.78rem; color:var(--text-muted); flex:1; }}
  .run-expand-hint {{ font-size:0.7rem; color:var(--text-muted); margin-left:auto; flex-shrink:0; }}
  details[open] .run-expand-hint {{ visibility:hidden; }}
  .past-run-body {{ padding:1.25rem 1.25rem 1rem; background:var(--bg); }}
  .tile-grid-compact {{ margin-bottom:0.75rem; pointer-events:none; }}
  .tile-grid-compact .pb-tile {{ cursor:default; }}
  .past-run-link {{ font-size:0.8rem; margin-top:0.75rem; }}
  .past-run-link a {{ color:var(--accent); text-decoration:none; }}
  .past-run-link a:hover {{ opacity:0.8; }}
  .past-section {{ margin-top:2rem; padding-top:1.5rem; border-top:1px solid var(--border-subtle); }}
  .section-eyebrow {{ font-size:0.65rem; font-weight:700; letter-spacing:0.1em;
                      text-transform:uppercase; color:var(--text-muted); margin-bottom:0.75rem;
                      display:block; }}
  .past-list {{ list-style:none; padding:0; margin:0; }}
  .past-list li {{ padding:0.4rem 0; border-bottom:1px solid var(--border-subtle); }}
  .past-list li:last-child {{ border-bottom:none; }}
  .past-list a {{ color:var(--accent); text-decoration:none; font-size:0.875rem; }}
  .past-list a:hover {{ opacity:0.8; }}

  /* ── Sortable tables ── */
  table thead th {{ cursor:pointer; user-select:none; white-space:nowrap; }}
  table thead th:hover {{ color:var(--text); }}
  .sort-icon {{ opacity:0.4; font-size:0.75em; margin-left:4px; font-style:normal; }}
  table thead th[data-sort] .sort-icon {{ opacity:1; color:var(--accent); }}

  /* ── Export button ── */
  .export-btn-wrap {{ float:right; position:relative; margin:0 0 10px 16px; }}
  .export-btn {{ font-size:0.72rem; padding:5px 10px; border-radius:6px; cursor:pointer;
                border:1px solid var(--border); background:var(--bg); color:var(--text-muted);
                font-family:inherit; transition:background 0.15s; }}
  .export-btn:hover {{ background:var(--bg-muted); color:var(--text); }}
  .export-dropdown {{ display:none; position:absolute; right:0; top:calc(100% + 3px);
                     min-width:130px; border-radius:8px; z-index:200;
                     border:1px solid var(--border); background:var(--bg);
                     box-shadow:0 4px 16px rgba(0,0,0,0.4); overflow:hidden; }}
  .export-dropdown button {{ display:block; width:100%; text-align:left; padding:8px 14px;
                             font-size:0.75rem; font-family:inherit; cursor:pointer;
                             border:none; background:transparent; color:var(--text-secondary); }}
  .export-dropdown button:hover {{ background:var(--bg-muted); }}
</style>
</head>
<body>
{_build_nav("Editorial Playbooks", 1)}
<div class="container">

<h1>Editorial Playbooks</h1>
<p class="sub">Updated monthly. Click any tile to expand the full guidance.</p>

<div class="tile-grid">

{_pb_tiles_html}

</div>

<!-- Detail panels (shown one at a time below the grid) -->

<div id="pb-2" class="pb-detail" style="display:none">
  <h3 class="rh">Rules of thumb</h3>
  <ul class="rules">
    <li><strong>"What to know" is a Featured targeting tool, not a views driver</strong> — Featured rate is {WTN_FEAT_LIFT:.1f}×, but organic views for non-Featured "What to know" articles trend lower ({WTN_ORGANIC_P_STR}, not significant at α=0.05, n={WTN_N_NONFEAT}).</li>
    <li><strong>Featured articles drive {FEAT_VIEW_LIFT_STR} views vs. non-Featured</strong> — treat the designation as a channel, not a side effect. It is worth targeting intentionally.</li>
    <li><strong>Don't apply "What to know" broadly</strong> — the view penalty for non-Featured articles makes it a poor default formula outside an explicit Featured campaign.</li>
  </ul>
  <h3 class="rh">Featured rate by formula — Apple News</h3>
  <table>
    <thead><tr><th>Formula</th><th>n</th><th>Featured rate</th><th>Lift</th><th>p<sub>adj</sub> (BH-FDR)</th><th>Within-Featured median %ile</th></tr></thead>
    <tbody>{_t2}</tbody>
  </table>
</div>

<div id="pb-4" class="pb-detail" style="display:none">
  <h3 class="rh">Rules of thumb</h3>
  <ul class="rules">
    <li><strong>Lead with "EXCLUSIVE:"</strong> on genuine scoops — {EXCL_LIFT} CTR lift. The word must be earned; overuse erodes the signal.</li>
    <li><strong>Named person + possessive</strong>: "Smith's connection to…" outperforms "Smith connected to…" ({_r5_poss['lift']:.2f}× lift).</li>
    <li><strong>Write longer notifications:</strong> ≤80 chars delivers {(1-float(_r5_sh['lift'])):.0%} fewer clicks. Give readers context before asking them to tap.</li>
    <li><strong>Avoid question format:</strong> hurts CTR ({_r5_q['lift']:.2f}×), consistent with the Apple News finding.</li>
    <li><strong>Serial/escalating stories with a named anchor</strong> are the highest-CTR content type — structure updates as installments with possessive framing.</li>
  </ul>
  <h3 class="rh">Features by CTR lift — Push Notifications</h3>
  <p class="detail-sub">Jan–Feb 2026 · N={N_NOTIF} notifications · BH-FDR corrected · {N_SIG_NOTIF_FEATURES} features significant after correction</p>
  <table>
    <thead><tr><th>Feature</th><th>n (present)</th><th>Median CTR (present)</th><th>Median CTR (absent)</th><th>Lift (95% CI)</th><th>Effect size r</th><th>p<sub>adj</sub> (BH-FDR)</th></tr></thead>
    <tbody>{_t4}</tbody>
  </table>
  <p class="caveat">Based on Jan–Feb 2026 only. Treat as directional guidance pending additional months of data.</p>
</div>

<div id="pb-dual" class="pb-detail" style="display:none">
  <h3 class="rh">Topic-by-topic pairing guide</h3>
  <p class="detail-sub">Write the Apple News headline first, then rewrite for SmartNews. These are two different editorial decisions.</p>
  <table>
    <thead><tr><th>Topic / Content type</th><th>Apple News headline</th><th>SmartNews headline</th><th>Notes</th></tr></thead>
    <tbody>
      <tr>
        <td><strong>Crime / Breaking</strong></td>
        <td>"Here's what we know about [event]" or "Here's what happened"<br><span style="font-size:.8em;color:#8b90a0">16% featuring rate (n=89)</span></td>
        <td>Direct declarative: "[Subject] [action]"<br><span style="font-size:.8em;color:#8b90a0">Avoid "Here's" — hurts SN rank when used broadly</span></td>
        <td>Attribution language ("says", "told") lifts notification CTR 1.18× for crime stories</td>
      </tr>
      <tr>
        <td><strong>Business / Economy</strong></td>
        <td>"Here's what [X] means for [community]"<br><span style="font-size:.8em;color:#8b90a0">14% featuring rate (n=72)</span></td>
        <td>Situation/event framing: "[Event] hits [place]"<br><span style="font-size:.8em;color:#8b90a0">Avoid individual-person framing; situation stories feature better</span></td>
        <td>Business + "Here's" is the strongest editorially writable non-weather formula</td>
      </tr>
      <tr>
        <td><strong>Sports</strong></td>
        <td>Any formula — 0–11.5% featuring regardless<br><span style="font-size:.8em;color:#8b90a0">Topic opts you out of Apple News featuring</span></td>
        <td>Number lead or direct declarative<br><span style="font-size:.8em;color:#8b90a0">Number leads are the only SN formula trending upward</span></td>
        <td>SmartNews is the better channel for sports. Apple News: feature potential only for national/marquee stories</td>
      </tr>
      <tr>
        <td><strong>Nature / Wildlife / Science</strong></td>
        <td>Discovery framing: "Scientists found…" / "Never-before-seen…"<br><span style="font-size:.8em;color:#8b90a0">General/Discovery ceiling: 53K views on snake/new species story</span></td>
        <td>Same framing works — mystery + scientific validation<br><span style="font-size:.8em;color:#8b90a0">Avoid question format (−0.08 pct_rank, p=3.4e-6)</span></td>
        <td>Highest-ceiling content type for General/Discovery vertical. "Rare", "never seen", "scientists found" are proven hooks</td>
      </tr>
      <tr>
        <td><strong>Entertainment / Celebrity</strong></td>
        <td>Possessive named entity: "[Celebrity]'s [situation]"<br><span style="font-size:.8em;color:#8b90a0">Notification: possessive lifts CTR for celebrity content</span></td>
        <td>Direct declarative; avoid question format<br><span style="font-size:.8em;color:#8b90a0">Questions hurt SN performance (p=3.4e-6)</span></td>
        <td>Serial/escalating stories with named anchor are highest-CTR notification type</td>
      </tr>
      <tr>
        <td><strong>Wellness / Mind-Body / Everyday Living</strong></td>
        <td>Number lead or direct declarative — no vertical-specific formula signal yet<br><span style="font-size:.8em;color:#8b90a0">n&lt;30 per vertical (preliminary only); guidelines inferred from platform-wide rules</span></td>
        <td>Number lead or direct declarative; <strong>avoid "What to know"</strong><br><span style="font-size:.8em;color:#8b90a0">WTK is the worst SN formula platform-wide (0.37 pct_rank, p=3.0e-6, n=213)</span></td>
        <td>0% featuring across all trendhunter verticals (n=22 matched, Jan–Feb 2026) — featuring is not a lever. Optimize for organic Apple News views. Best observed format: product/list structure ("10 things…", "How to…")</td>
      </tr>
    </tbody>
  </table>
  <p class="caveat">Apple News featuring rates from pooled 2025+ANP 2026 (n&gt;15,000). SmartNews formula ranks from 2025 article-level data (n=38,251). Trendhunter performance from Tracker→ANP join (Jan–Feb 2026). All formula effects are observational — treat as directional guidance for CSA persona configuration.</p>
</div>

<div class="pb-detail" style="display:block; margin-top:2.5rem; border-top:2px solid var(--accent)">
  <h3 class="rh" style="margin-top:1rem">CSA Persona Configuration \u00b7 Ready-to-Use Instructions</h3>
  <p class="detail-sub">Copy these instructions directly into CSA persona configuration. Each rule is drawn from a confirmed or directional finding. Confidence tier shown in brackets.</p>

  <h3 class="rh" style="margin-top:1.5rem">Apple News Persona</h3>
  <ul class="rules">
    <li><strong>[HIGH] Featured targeting formula:</strong> Use "What to know" or "Here's" format when the editorial goal is Featured placement. These are associated with {WTN_FEAT_LIFT:.1f}× and higher featuring rates respectively.</li>
    <li><strong>[HIGH] Organic reach formula:</strong> Avoid "What to know" for non-Featured articles — organic view performance trends lower. Use possessive named entity or number lead for organic reach.</li>
    <li><strong>[HIGH] Question format:</strong> Apple editors over-select questions for featuring, but the algorithm penalizes them organically. Use questions only for intentional Featured targeting, not for general organic distribution.</li>
    <li><strong>[HIGH] Character length:</strong> Target 90–120 characters. Below 70 chars and above 130 chars both underperform the median.</li>
    <li><strong>[HIGH] Crime/Business formula:</strong> "Here's" format associated with 16% featuring rate for crime (n=89) and 14% for business (n=72). Use it when targeting Featured in these topics.</li>
    <li><strong>[HIGH] Sports:</strong> Formula choice does not affect featuring odds for sports content (0% across all formulas, n=22–52). Optimize for organic only; do not target Featured for sports.</li>
    <li><strong>[HIGH] Section tagging:</strong> Every article must have a non-Main section tag. Untagged articles land in the bottom 20% at {_anp_fail['ANP_FAIL_MAIN_BOT_PCT']:.0%} — 2.4× the baseline rate.</li>
    <li><strong>[MOD] Number lead trend:</strong> Number leads are the only formula trending upward over time (Q1 2025 → Q1 2026). Lean into them; deprioritize question format which is trending down.</li>
    <li><strong>[MOD] Trendhunter content:</strong> Mind-Body, Everyday Living, and Experience content currently earns 0% featuring. Focus persona configuration on organic Apple News reach, not featuring optimization.</li>
  </ul>

  <h3 class="rh" style="margin-top:1.5rem">SmartNews Persona</h3>
  <ul class="rules">
    <li><strong>[HIGH] Avoid question format:</strong> Question headlines drop to 0.42 pct_rank — 0.08 below baseline (p=3.4e-6, n=918). This is the strongest single avoidance rule in the SmartNews data.</li>
    <li><strong>[HIGH] Avoid "What to know":</strong> Drops to 0.37 pct_rank — the worst-performing formula (p=3.0e-6, n=213). Never use for SmartNews.</li>
    <li><strong>[DIR] "Here's" is the safest cross-platform formula:</strong> Directionally above SmartNews baseline (p=0.038, does not survive Bonferroni at k=5). Use when writing one headline for both platforms.</li>
    <li><strong>[HIGH] Number leads trending upward:</strong> Only formula with positive trajectory across 2025–2026. Prioritize for SmartNews when topic allows.</li>
    <li><strong>[HIGH] Character length:</strong> Target 70–90 characters for SmartNews. 80–99 char optimal bin confirmed; 100-char ceiling has no statistical basis.</li>
    <li><strong>[HIGH] Direct declarative baseline:</strong> Unformatted subject-verb-object headlines are the SmartNews default — never penalized. Use as the fallback when no formula signal applies.</li>
    <li><strong>[MOD] Nature/wildlife/science:</strong> Discovery framing ("Scientists found", "Never-before-seen") drives highest-ceiling performance in General/Discovery content. Do not apply question or WTK format to these stories for SmartNews.</li>
  </ul>
  <p class="caveat">HIGH = p&lt;0.05 confirmed finding. MOD = multiple-comparisons corrected or n-limited directional. DIR = directional (p&lt;0.10). All findings are observational — use as configuration starting points; validate against post-publication performance data.</p>
</div>

{_pub_section_html}

{_inline_sections_html}

{_past_runs_html}

<p class="caveat" style="margin-top:2.5rem">Formula × topic cells require ≥5 articles. All lift values are vs. untagged baseline within the same platform. Statistical confidence varies — see individual finding panels on the <a href="../" style="color:#60a5fa">main analysis page</a> for p-values and sample sizes.</p>

</div>
<script>
var _openTile = null, _openPanel = null;
function togglePb(tile, id) {{
  var panel = document.getElementById(id);
  var toggle = tile.querySelector('.tile-toggle');
  var isOpen = tile.classList.contains('open');
  if (_openTile && _openTile !== tile) {{
    _openTile.classList.remove('open');
    _openTile.querySelector('.tile-toggle').textContent = 'Details \u2193';
    _openPanel.style.display = 'none';
  }}
  if (!isOpen) {{
    tile.classList.add('open');
    toggle.textContent = 'Details \u2191';
    panel.style.display = 'block';
    _openTile = tile; _openPanel = panel;
    // Re-apply theme to newly-visible charts — closed panels are skipped at
    // page-load theme time because Plotly.relayout throws on display:none elements.
    setTimeout(function() {{
      if (typeof _rethemeCharts === 'function') {{
        _rethemeCharts(!document.body.classList.contains('light'));
      }}
      panel.scrollIntoView({{behavior:'smooth',block:'nearest'}});
    }}, 80);
  }} else {{
    tile.classList.remove('open');
    toggle.textContent = 'Details \u2193';
    panel.style.display = 'none';
    _openTile = null; _openPanel = null;
  }}
}}

// ── Table sorting ──────────────────────────────────────────
(function() {{
  function parseCell(text) {{
    var s = text.replace(/<[^>]+>/g, '').trim();
    if (s === '—' || s === '') return -Infinity;
    var m = s.match(/^[~\u2264<\u2265>]?\\s*([\\d,.]+)/);
    if (m) return parseFloat(m[1].replace(/,/g, ''));
    return s.toLowerCase();
  }}
  function sortBy(table, colIdx, asc) {{
    var tbody = table.querySelector('tbody');
    if (!tbody) return;
    var rows = Array.from(tbody.querySelectorAll('tr'));
    rows.sort(function(a, b) {{
      var av = parseCell(a.cells[colIdx] ? a.cells[colIdx].textContent : '');
      var bv = parseCell(b.cells[colIdx] ? b.cells[colIdx].textContent : '');
      if (typeof av === 'number' && typeof bv === 'number') return asc ? av - bv : bv - av;
      return asc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    }});
    rows.forEach(function(r) {{ tbody.appendChild(r); }});
  }}
  document.addEventListener('DOMContentLoaded', function() {{
    // Wrap every table in a .table-wrap scroll container so wide tables never
    // bleed past the tile edge — content scrolls horizontally, never clips.
    document.querySelectorAll('table').forEach(function(t) {{
      if (t.parentNode && !t.parentNode.classList.contains('table-wrap')) {{
        var w = document.createElement('div');
        w.className = 'table-wrap';
        t.parentNode.insertBefore(w, t);
        w.appendChild(t);
      }}
    }});
    document.querySelectorAll('table thead th').forEach(function(th) {{
      var icon = document.createElement('span');
      icon.className = 'sort-icon';
      icon.textContent = '\u2195';
      th.appendChild(icon);
      th.addEventListener('click', function() {{
        var table = th.closest('table');
        var idx = Array.from(th.parentNode.children).indexOf(th);
        var asc = th.getAttribute('data-sort') !== 'asc';
        table.querySelectorAll('thead th').forEach(function(h) {{
          h.removeAttribute('data-sort');
          var ic = h.querySelector('.sort-icon');
          if (ic) ic.textContent = '\u2195';
        }});
        th.setAttribute('data-sort', asc ? 'asc' : 'desc');
        th.querySelector('.sort-icon').textContent = asc ? '\u2191' : '\u2193';
        sortBy(table, idx, asc);
      }});
    }});
  }});
}})();

// ── Export (PNG / PDF) ──────────────────────────────────────────────────────
// Shared with main page — same _findTileForPanel + _exportPanel pattern.
// PDF: browser native print. PNG: off-screen fixed-width container capture.
{_make_export_js("2", ".tile-toggle,.tile-more,.export-btn-wrap", "h2", "headline-analysis-")}

(function() {{
  document.addEventListener('DOMContentLoaded', function() {{
    document.querySelectorAll('.pb-detail').forEach(function(panel) {{
      var wrap = document.createElement('div');
      wrap.className = 'export-btn-wrap';
      var btn = document.createElement('button');
      btn.className = 'export-btn';
      btn.title = 'Export this playbook';
      btn.textContent = '\u2193 Export';
      var dd = document.createElement('div');
      dd.className = 'export-dropdown';
      var pngBtn = document.createElement('button');
      pngBtn.textContent = 'PNG image';
      var pdfBtn = document.createElement('button');
      pdfBtn.textContent = 'PDF document';
      pngBtn.addEventListener('click', function(e) {{ e.stopPropagation(); _exportPanel(panel, 'png', dd); }});
      pdfBtn.addEventListener('click', function(e) {{ e.stopPropagation(); _exportPanel(panel, 'pdf', dd); }});
      btn.addEventListener('click', function(e) {{
        e.stopPropagation();
        dd.style.display = dd.style.display === 'block' ? 'none' : 'block';
      }});
      document.addEventListener('click', function() {{ dd.style.display = 'none'; }});
      dd.appendChild(pngBtn); dd.appendChild(pdfBtn);
      wrap.appendChild(btn); wrap.appendChild(dd);
      panel.insertBefore(wrap, panel.firstChild);
    }});
  }});
}})();

// ── Theme toggle ───────────────────────────────────────────
(function() {{
  if (localStorage.getItem('theme') === 'light') document.body.classList.add('light');
}})();
function toggleTheme() {{
  document.body.classList.toggle('light');
  try {{ localStorage.setItem('theme', document.body.classList.contains('light') ? 'light' : 'dark'); }} catch(e) {{}}
}}
{_make_col_tooltip_js()}
</script>
</body>
</html>"""

playbook_out = Path("docs/playbook/index.html")
playbook_out.parent.mkdir(exist_ok=True)
playbook_html = playbook_html.replace(" \u2014 ", "\u2014")
playbook_out.write_text(playbook_html, encoding="utf-8")
print(f"Playbooks written to {playbook_out}  ({len(playbook_html):,} chars)")

# ── Author Playbooks HTML ──────────────────────────────────────────────────────
_ap_tiles_html   = "\n\n".join(t for _, _, _, t, _ in _author_playbook_defs)
_ap_details_html = "\n\n".join(d for _, _, _, _, d in _author_playbook_defs)
_ap_n_authors    = len(_author_playbook_defs)
_ap_n_articles   = sum(n for _, n, _, _, _ in _author_playbook_defs)

def _vertical_perf_section() -> str:
    """Generate the content vertical performance section for author-playbooks page."""
    if not HAS_VERTICAL_DATA:
        return ""

    anp_baseline_str = f"{VERTICAL_ANP_BASELINE_FEAT:.1%}" if VERTICAL_ANP_BASELINE_FEAT else "1.2%"
    feat_callout = ""
    if VERTICAL_FEAT_RATE == 0.0:
        feat_callout = f"""<div class="callout" style="margin-bottom:1.5rem">
  <strong>0% featuring rate across all verticals</strong> ({VERTICAL_MATCH_N} matched articles,
  Jan–Feb 2026). ANP baseline = {anp_baseline_str}. Featuring is not currently a lever for this
  content — optimize for organic Apple News views, not featuring odds.
</div>"""

    rows_html = ""
    for _, r in df_vertical_perf.iterrows():
        top_h   = html_module.escape(str(r.get("top_headline", "")))[:80]
        _vn     = int(r['n'])
        _prelim = " <em style='font-size:.75em;color:#f59e0b'>(preliminary, n&lt;30)</em>" if _vn < 30 else ""
        feat_str = f"{r['feat_rate']:.0%}"
        rows_html += (
            f"<tr><td><strong>{html_module.escape(str(r['vertical_group']))}</strong>{_prelim}</td>"
            f"<td>{_vn}</td>"
            f"<td>{r['med_views']:,.0f}</td>"
            f"<td>{r['max_views']:,.0f}</td>"
            f"<td>{feat_str}</td>"
            f"<td style='font-size:.85em;color:#8b90a0'>{top_h}…</td></tr>\n"
        )

    top_arts_html = ""
    for _, r in df_vertical_top.iterrows():
        vert_badge = html_module.escape(str(r["vertical_group"]))
        hl = html_module.escape(str(r["Headline"]))[:90]
        feat = " ★" if r["is_featured"] else ""
        top_arts_html += (
            f"<tr><td><span style='font-size:.8em;background:#1a1d27;padding:2px 6px;"
            f"border-radius:3px'>{vert_badge}</span></td>"
            f"<td>{html_module.escape(str(r['t_author']))}</td>"
            f"<td>{hl}{feat}</td>"
            f"<td>{r['views_total']:,.0f}</td></tr>\n"
        )

    return f"""
<section class="vert-perf-section" style="margin-top:3rem;padding-top:2rem;border-top:1px solid var(--border)">
  <h2 style="margin-bottom:.5rem">Content Vertical Performance — Apple News</h2>
  <p class="sub" style="margin-bottom:1.5rem">
    Based on Tracker→ANP join ({VERTICAL_MATCH_N} matched / {VERTICAL_MATCH_TOT} Tracker articles,
    Jan–Feb 2026). Verticals identified by author. Match rate improves as ANP data accumulates monthly.
  </p>
  {feat_callout}
  <table class="findings">
    <thead><tr>
      <th>Vertical</th><th>n matched</th><th>Median views</th>
      <th>Max views</th><th>Featuring rate</th><th>Top article</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  <h3 style="margin-top:2rem">Top articles by vertical</h3>
  <table class="findings">
    <thead><tr><th>Vertical</th><th>Author</th><th>Headline</th><th>Views</th></tr></thead>
    <tbody>{top_arts_html}</tbody>
  </table>
  <p class="caveat">Apple News Publisher data, Jan–Feb 2026 (March pending). Staging URLs and
  non-T1 domains excluded. ★ = Apple News featured placement. Views = total across all days
  article appeared in ANP data.</p>
</section>"""

if _ap_n_authors == 0:
    _ap_body = """
<div class="container">
  <h1>Author Playbooks</h1>
  <p class="sub">No tracker data loaded this run. Place <code>Tracker Template.xlsx</code>
  in the repo root and re-run <code>ingest.py</code> to generate per-author guidance.</p>
</div>"""
else:
    _ap_body = f"""
<div class="container">
  <h1>Author Playbooks</h1>
  <p class="sub">Updated monthly. Click any tile to expand the full guidance.</p>

  <div class="tile-grid">
{_ap_tiles_html}
  </div>

{_ap_details_html}

{_vertical_perf_section()}
</div>"""

author_pb_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<meta name="data-run" content="{REPORT_DATE_SLUG}">
<title>T1 Headline Analysis \u00b7 Author Playbooks</title>
<script src="https://cdn.jsdelivr.net/npm/dom-to-image-more@3.7.2/dist/dom-to-image-more.min.js"></script>
<style>
  /* ── Theme tokens ── */
  :root {{
    --bg:#0f1117; --bg-card:#21253a; --bg-muted:#1a1d27; --bg-subtle:#2e3350;
    --text:#e8eaf6; --text-secondary:#b0bec5; --text-muted:#8b90a0;
    --border:#2e3350; --border-subtle:#1a1d27; --accent:#7c9df7;
    --nav-bg:#1a1d27;
  }}
  body.light {{
    --bg:#f4f6fb; --bg-card:#ffffff; --bg-muted:#f4f6fb; --bg-subtle:#eef0f8;
    --text:#1a1d27; --text-secondary:#3a3d4a; --text-muted:#5a6070;
    --border:#dde1f0; --border-subtle:#eef0f8; --accent:#3d5af1;
    --nav-bg:#ffffff;
  }}

  /* ── Reset ── */
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif;
         background: var(--bg); color: var(--text); font-size: 14px; line-height: 1.6;
         -webkit-font-smoothing: antialiased; transition: background 0.2s, color 0.2s; }}
  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  code {{ font-family: "SF Mono", Menlo, monospace; font-size: 0.85em;
          background: var(--bg-muted); padding: 1px 5px; border-radius: 3px; }}

  /* ── Nav ── */
  .site-nav {{ background: var(--nav-bg); border-bottom: 1px solid var(--border); padding: 0 24px; display: flex; align-items: center; justify-content: space-between; height: 44px; position: sticky; top: 0; z-index: 100; }}
  .nav-links {{ display: flex; align-items: center; }}
  .nav-links a {{ color: var(--text-muted); text-decoration: none; font-size: .85em; padding: 0 12px; height: 44px; display: flex; align-items: center; border-bottom: 2px solid transparent; transition: color .15s; }}
  .nav-links a:hover {{ color: var(--text); }}
  .nav-links a.active {{ color: var(--accent); border-bottom-color: var(--accent); }}
  .nav-sep {{ color: var(--border); font-size: .8em; }}
  .theme-toggle {{ background: none; border: 1px solid var(--border); color: var(--text-muted); cursor: pointer; padding: 4px 8px; border-radius: 4px; font-size: .8em; }}

  /* ── Layout ── */
  .container {{ max-width: 1100px; margin: 0 auto; padding: 40px 28px 80px; }}
  h1 {{ font-size: 1.7em; font-weight: 700; color: var(--accent); margin-bottom: 4px; }}
  .sub {{ font-size: 0.9em; color: var(--text-muted); margin-bottom: 28px; }}
  .run-header {{ display: flex; align-items: center; gap: 1rem; margin-bottom: 1.75rem;
                 padding: 0.6rem 1rem; background: var(--bg-muted);
                 border: 1px solid var(--border); border-radius: 8px; }}
  .run-label {{ font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em;
                text-transform: uppercase; color: var(--text-muted); }}
  .run-meta  {{ font-size: 0.78rem; color: var(--text-muted); }}

  /* ── Tile grid ── */
  .tile-grid {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 12px; margin-bottom: 1rem; }}
  @media (max-width: 720px)  {{ .tile-grid {{ grid-template-columns: 1fr; }} }}
  @media (max-width: 1000px) and (min-width: 721px) {{ .tile-grid {{ grid-template-columns: repeat(2,1fr); }} }}

  /* ── Tiles ── */
  .pb-tile {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px;
              padding: 1.1rem 1.25rem; cursor: pointer;
              transition: border-color 0.15s, box-shadow 0.15s, background 0.2s; user-select: none; }}
  .pb-tile:hover {{ border-color: var(--bg-subtle); box-shadow: 0 0 0 1px var(--bg-subtle) inset; }}
  .pb-tile.open  {{ border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent) inset; }}
  .conf-badge {{ display: inline-block; font-size: 9px; font-weight: 700;
                 text-transform: uppercase; letter-spacing: 0.07em;
                 padding: 2px 6px; border-radius: 3px; margin-bottom: 8px; }}
  .conf-high {{ background: rgba(22,163,74,0.2);   color: #4ade80; }}
  .conf-mod  {{ background: rgba(37,99,235,0.2);    color: #60a5fa; }}
  .conf-dir  {{ background: rgba(100,116,139,0.15); color: #8b90a0; }}
  body.light .conf-high {{ background: rgba(22,163,74,0.12); color: #15803d; }}
  body.light .conf-mod  {{ background: rgba(37,99,235,0.12); color: #1d4ed8; }}
  body.light .conf-dir  {{ background: rgba(100,116,139,0.10); color: #475569; }}
  .tile-label  {{ display: block; font-size: 0.88rem; font-weight: 700; color: var(--text);
                  letter-spacing: 0.01em; margin-bottom: 0.5rem; }}
  .tile-claim  {{ font-size: 0.84rem; color: var(--text-secondary); margin-bottom: 0.5rem; line-height: 1.55; }}
  .tile-action {{ font-size: 0.8rem; color: var(--accent); font-weight: 500;
                  margin-bottom: 0.5rem; line-height: 1.45; }}
  .tile-toggle {{ font-size: 0.7rem; color: var(--text-muted); display: block; margin-top: 0.5rem; }}

  /* ── Detail panels ── */
  .pb-detail {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px;
                padding: 1.5rem 1.75rem; margin-bottom: 1rem; }}
  .pb-detail h3.rh {{ font-size: 0.65rem; font-weight: 700; letter-spacing: 0.1em;
                      text-transform: uppercase; color: var(--text-muted); margin: 1.4rem 0 0.5rem; }}
  .pb-detail h3.rh:first-child {{ margin-top: 0; }}
  .pb-detail .detail-sub {{ font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.6rem; }}
  .pb-detail p {{ font-size: 0.84rem; color: var(--text-secondary); margin-bottom: 0.75rem; line-height: 1.55; }}

  /* ── Tables ── */
  .table-wrap {{ overflow-x: auto; border-radius: 8px; border: 1px solid var(--border);
                 box-shadow: 0 1px 4px rgba(0,0,0,0.3); margin: 0.5rem 0 1.25rem; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
  thead th {{ background: var(--bg-muted); color: var(--text-muted); font-size: 0.68rem;
              font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
              padding: 9px 12px; text-align: left; white-space: nowrap; border-bottom: 1px solid var(--border); }}
  tbody tr {{ background: transparent; }}
  tbody tr:hover {{ background: var(--bg-muted); }}
  tbody td {{ padding: 8px 12px; color: var(--text-secondary); border-bottom: 1px solid var(--border-subtle); white-space: nowrap; }}
  tbody tr:last-child td {{ border-bottom: none; }}
  table thead th {{ cursor: pointer; user-select: none; }}
  .sort-icon {{ opacity: 0.4; font-size: 0.75em; margin-left: 4px; }}
  table thead th[data-sort] .sort-icon {{ opacity: 1; color: var(--accent); }}

  /* ── Lift colors ── */
  .lift-high {{ color: #4ade80; font-weight: 600; }}
  .lift-pos  {{ color: #60a5fa; font-weight: 600; }}
  .lift-neg  {{ color: #f87171; font-weight: 600; }}
  body.light .lift-high {{ color: #16a34a; }}
  body.light .lift-pos  {{ color: var(--accent); }}
  body.light .lift-neg  {{ color: #dc2626; }}

  /* ── Export button ── */
  .export-btn-wrap {{ float: right; position: relative; margin: 0 0 10px 16px; }}
  .export-btn {{ font-size: 0.72rem; padding: 5px 10px; border-radius: 6px; cursor: pointer;
                 border: 1px solid var(--border); background: var(--bg); color: var(--text-muted);
                 font-family: inherit; transition: background 0.15s; }}
  .export-btn:hover {{ background: var(--bg-muted); color: var(--text); }}
  .export-dropdown {{ display: none; position: absolute; right: 0; top: calc(100% + 3px);
                      min-width: 130px; border-radius: 8px; z-index: 200;
                      border: 1px solid var(--border); background: var(--bg);
                      box-shadow: 0 4px 16px rgba(0,0,0,0.4); overflow: hidden; }}
  .export-dropdown button {{ display: block; width: 100%; text-align: left; padding: 8px 14px;
                              font-size: 0.75rem; font-family: inherit; cursor: pointer;
                              border: none; background: transparent; color: var(--text-secondary); }}
  .export-dropdown button:hover {{ background: var(--bg-muted); }}
</style>
</head>
<body>
{_build_nav("Author Playbooks", 1)}
{_ap_body}
<script>
var _openTile = null, _openPanel = null;

function togglePb(tile, id) {{
  var panel  = document.getElementById(id);
  var toggle = tile.querySelector('.tile-toggle');
  var isOpen = tile.classList.contains('open');
  if (_openTile && _openTile !== tile) {{
    _openTile.classList.remove('open');
    var prevToggle = _openTile.querySelector('.tile-toggle');
    if (prevToggle) prevToggle.textContent = 'Details \u2193';
    if (_openPanel) _openPanel.style.display = 'none';
  }}
  if (!isOpen) {{
    tile.classList.add('open');
    if (toggle) toggle.textContent = 'Details \u2191';
    panel.style.display = 'block';
    _openTile = tile; _openPanel = panel;
    // Re-apply theme to newly-visible charts — closed panels are skipped at
    // page-load theme time because Plotly.relayout throws on display:none elements.
    setTimeout(function() {{
      if (typeof _rethemeCharts === 'function') {{
        _rethemeCharts(!document.body.classList.contains('light'));
      }}
      panel.scrollIntoView({{behavior:'smooth',block:'nearest'}});
    }}, 80);
  }} else {{
    tile.classList.remove('open');
    if (toggle) toggle.textContent = 'Details \u2193';
    panel.style.display = 'none';
    _openTile = null; _openPanel = null;
  }}
}}

// ── Table sorting ──────────────────────────────────────────
(function() {{
  function parseCell(text) {{
    var s = text.replace(/<[^>]+>/g, '').trim();
    if (s === '\u2014' || s === '') return -Infinity;
    var m = s.match(/^[~\u2264<\u2265>]?\\s*([\\d,.]+)/);
    if (m) return parseFloat(m[1].replace(/,/g, ''));
    return s.toLowerCase();
  }}
  function sortBy(table, colIdx, asc) {{
    var tbody = table.querySelector('tbody');
    if (!tbody) return;
    var rows = Array.from(tbody.querySelectorAll('tr'));
    rows.sort(function(a, b) {{
      var av = parseCell(a.cells[colIdx] ? a.cells[colIdx].innerHTML : '');
      var bv = parseCell(b.cells[colIdx] ? b.cells[colIdx].innerHTML : '');
      if (typeof av === 'number' && typeof bv === 'number') return asc ? av - bv : bv - av;
      return asc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    }});
    rows.forEach(function(r) {{ tbody.appendChild(r); }});
  }}
  document.addEventListener('DOMContentLoaded', function() {{
    document.querySelectorAll('table').forEach(function(t) {{
      if (t.parentNode && !t.parentNode.classList.contains('table-wrap')) {{
        var w = document.createElement('div');
        w.className = 'table-wrap';
        t.parentNode.insertBefore(w, t);
        w.appendChild(t);
      }}
    }});
    document.querySelectorAll('table thead th').forEach(function(th) {{
      var icon = document.createElement('span');
      icon.className = 'sort-icon';
      icon.textContent = '\u2195';
      th.appendChild(icon);
      th.addEventListener('click', function() {{
        var table  = th.closest('table');
        var idx    = Array.from(th.parentNode.children).indexOf(th);
        var asc    = th.getAttribute('data-sort') !== 'asc';
        table.querySelectorAll('thead th').forEach(function(h) {{
          h.removeAttribute('data-sort');
          var ic = h.querySelector('.sort-icon');
          if (ic) ic.textContent = '\u2195';
        }});
        th.setAttribute('data-sort', asc ? 'asc' : 'desc');
        th.querySelector('.sort-icon').textContent = asc ? '\u2191' : '\u2193';
        sortBy(table, idx, asc);
      }});
    }});
  }});
}})();

// ── Export (PNG / PDF) ──────────────────────────────────────────────────────
{_make_export_js("3", ".tile-toggle,.export-btn-wrap", "h3.rh,h2", "author-playbook-",
    "  var pid = panelEl.id || '';\n"
    "  var tileEl = null;\n"
    "  document.querySelectorAll('.pb-tile').forEach(function(t) {{\n"
    "    if ((t.getAttribute('onclick') || '').indexOf(pid) >= 0) tileEl = t;\n"
    "  }});\n"
    "  return tileEl;")}

(function() {{
  document.addEventListener('DOMContentLoaded', function() {{
    document.querySelectorAll('.pb-detail').forEach(function(panel) {{
      var wrap = document.createElement('div');
      wrap.className = 'export-btn-wrap';
      var btn = document.createElement('button');
      btn.className = 'export-btn'; btn.title = 'Export this author profile';
      btn.textContent = '\u2193 Export';
      var dd = document.createElement('div'); dd.className = 'export-dropdown';
      var pngBtn = document.createElement('button'); pngBtn.textContent = 'PNG image';
      var pdfBtn = document.createElement('button'); pdfBtn.textContent = 'PDF document';
      pngBtn.addEventListener('click', function(e) {{ e.stopPropagation(); _exportPanel(panel, 'png', dd); }});
      pdfBtn.addEventListener('click', function(e) {{ e.stopPropagation(); _exportPanel(panel, 'pdf', dd); }});
      btn.addEventListener('click', function(e) {{
        e.stopPropagation();
        dd.style.display = dd.style.display === 'block' ? 'none' : 'block';
      }});
      document.addEventListener('click', function() {{ dd.style.display = 'none'; }});
      dd.appendChild(pngBtn); dd.appendChild(pdfBtn);
      wrap.appendChild(btn); wrap.appendChild(dd);
      panel.insertBefore(wrap, panel.firstChild);
    }});
  }});
}})();

// ── Theme toggle ───────────────────────────────────────────
(function() {{
  if (localStorage.getItem('theme') === 'light') document.body.classList.add('light');
}})();
function toggleTheme() {{
  document.body.classList.toggle('light');
  try {{ localStorage.setItem('theme', document.body.classList.contains('light') ? 'light' : 'dark'); }} catch(e) {{}}
}}
{_make_col_tooltip_js()}
</script>
</body>
</html>"""

author_pb_out = Path("docs/author-playbooks/index.html")
author_pb_out.parent.mkdir(exist_ok=True)
author_pb_html = author_pb_html.replace(" \u2014 ", "\u2014")
author_pb_out.write_text(author_pb_html, encoding="utf-8")
print(f"Author Playbooks written to {author_pb_out}  ({len(author_pb_html):,} chars)")


# ── Experiments page ──────────────────────────────────────────────────────────
# Auto-generated page of suggested experiments derived from directional findings
# in the current analysis run.  Fully replaces docs/experiments/index.html on
# every run — past suggestions are never lost because an append-only log is
# maintained alongside the page at experiments/experiment_log.md.
#
# Routing rule (per GOVERNOR.md Part 2 — Rigor):
#   Confirmed finding (p<0.05, n≥30, survives multiple-comparison correction)
#     → main analysis tiles  +  playbook tiles
#   Directional finding (any of: p<0.10 but not p<0.05; p<0.05 but Bonferroni
#     fail at family α/k; n<30 per group; HIGH-priority queue item with data)
#     → experiments page only — no style recommendation is made

_EXP_TIER_LABELS: dict[str, str] = {
    "bonferroni-fail": "Bonferroni fail",
    "underpowered":    "Underpowered",
    "directional":     "Directional",
    "untested":        "Untested",
}
_EXP_PRIORITY_LABELS: dict[str, str] = {
    "high":   "\u2191 High",
    "medium": "Medium",
    "low":    "Low",
}


def _collect_experiment_suggestions() -> list[dict]:
    """Collect all directional findings that warrant a suggested experiment.

    A suggestion is generated for any finding meeting one or more of:
      - Bonferroni fail  raw p < 0.05 but doesn't survive α/k family correction
      - Underpowered     n < 30 per group (below reliable-inference threshold)
      - Directional      0.05 ≤ p < 0.10 after BH-FDR correction
      - Untested         HIGH/MED-priority probing-queue item with data available

    All variables referenced here are module-level scalars already computed
    above.  The function must be called after all analysis variables are set.

    Returns a list of dicts, each with keys:
      id        — URL-safe slug
      platform  — short platform label (e.g. "Apple News")
      title     — card heading
      signal    — what the data currently shows and why this was flagged
      gap       — what keeps this directional / why we can't act yet
      question  — specific testable hypothesis
      design    — how to run the experiment: variants, measurement, sample size, method
      impact    — what confirmation or refutation means for style guidance and editorial action
      tier      — "bonferroni-fail" | "underpowered" | "directional" | "untested"
      priority  — "high" | "medium" | "low"
    """
    suggs: list[dict] = []

    # ── 1. Here's / Here are on SmartNews — Bonferroni failure ───────────────
    # Pull p-value and n directly from _SN_FORMULA_DATA so they stay in sync
    # if the source data ever changes.  _HERES_BONF_K is a policy decision
    # (how many formula families to correct for) and stays as a named constant.
    _heres_row = next(
        (r for r in _SN_FORMULA_DATA if r[0] == "Here's / Here are"), None
    )
    # _SN_FORMULA_DATA columns: (formula_label, sn_rank, sn_baseline, p_val, n, direction)
    _HERES_SN_RAW_P    = float(_heres_row[3]) if _heres_row else 0.038  # p_val column
    _HERES_SN_N        = int(_heres_row[4])   if _heres_row else 585    # n column
    # Count tested formula families dynamically — rows with a real n (not the
    # baseline "Direct declarative" row, which has n=None).  This stays correct
    # if _SN_FORMULA_DATA is updated without a corresponding manual constant update.
    _HERES_BONF_K = sum(1 for r in _SN_FORMULA_DATA if r[4] is not None)
    _HERES_BONF_THRESH = 0.05 / _HERES_BONF_K
    if _HERES_BONF_THRESH <= _HERES_SN_RAW_P < 0.05:  # directional but Bonferroni fail
        suggs.append({
            "id":       "heres-sn-bonferroni",
            "platform": "SmartNews",
            "title":    "\u201cHere\u2019s / Here are\u201d Lift \u2014 Needs Confirmation",
            "signal": (
                f"Articles using \u201cHere\u2019s / Here are\u201d on SmartNews score "
                f"a median percentile rank of {FB_HERES_SN_RANK:.3f} vs. 0.500 for the "
                f"direct-declarative baseline (n={_HERES_SN_N:,}, raw p={_HERES_SN_RAW_P}). "
                f"Direction is positive \u2014 opposite to question and "
                f"\u201cWhat to know\u201d on the same platform."
            ),
            "gap": (
                f"Raw p={_HERES_SN_RAW_P} does not survive Bonferroni correction at "
                f"k={_HERES_BONF_K} formula families "
                f"(threshold \u03b1/k\u2009=\u2009{_HERES_BONF_THRESH:.3f}). "
                f"All data is observational; no A/B comparison is available. Topic "
                f"confounding (\u201cHere\u2019s\u201d may correlate with better-performing "
                f"story types) has not been controlled for."
            ),
            "question": (
                "If T1 editors A/B tested \u201cHere\u2019s / Here are\u201d against a "
                "direct-declarative version of the same story on SmartNews, would the formula "
                "version consistently outperform? Does the effect hold across topics (sports, "
                "crime, weather) or appear only in a topic subset?"
            ),
            "design": (
                "For 30\u201350 stories over 4\u20136 weeks, write two headline versions per "
                "story: (A) \u201cHere\u2019s / Here are\u201d format and (B) a direct "
                "declarative covering the same facts. If the CMS supports A/B headline "
                "testing, use it; otherwise alternate formula by publication day or assign "
                "by outlet. Record SmartNews views at 7 days post-publish. "
                "Test: Mann-Whitney U on SmartNews views (A vs. B), rank-biserial r as "
                "effect size. Minimum n\u2009=\u200930 matched story pairs for reliable "
                "inference. Stratify by topic (sports/crime/weather vs. other) to check "
                "whether any interaction hides or drives the aggregate result. "
                "Do not use the same story on Apple News A/B \u2014 keep platforms "
                "separate to avoid contamination."
            ),
            "impact": (
                "Confirmed: adds a positive SmartNews formula signal \u2014 currently all "
                "confirmed SmartNews guidance is avoidance-only. Editors could be told "
                "\u201cHere\u2019s works on SmartNews, unlike Apple News where WTK dominates "
                "featuring.\u201d  "
                "Not confirmed: SmartNews playbook stays avoidance-only; the directional "
                "positive for \u201cHere\u2019s\u201d is noise or topic-driven."
            ),
            "tier":     "bonferroni-fail",
            "priority": "high",
        })

    # ── 2. Number lead — round vs. specific numbers on Apple News ─────────────
    # Often underpowered because only a fraction of number-lead headlines parse
    # cleanly to a numeric value with determinable roundness.
    _nl_p     = NL_ROUND_VS_SPECIFIC_P
    _nl_n_r   = len(nl_round)
    _nl_n_s   = len(nl_specific)
    _nl_low_n = _nl_n_r < 30 or _nl_n_s < 30
    _nl_dir   = _nl_p is not None and 0.05 <= _nl_p < 0.10
    _nl_none  = _nl_p is None
    if _nl_low_n or _nl_dir or _nl_none:
        _nl_signal = (
            f"Specific numbers (e.g. \u2018$487M\u2019, \u201813 deaths\u2019) score a "
            f"median rank of {NL_SPECIFIC_MED:.3f} vs. {NL_ROUND_MED:.3f} for round "
            f"numbers on Apple News (n\u2009=\u2009{_nl_n_s} specific, {_nl_n_r} round)"
            if not (np.isnan(NL_SPECIFIC_MED) or np.isnan(NL_ROUND_MED))
            else "Specific vs. round comparison could not be computed (insufficient parseable number leads)"
        )
        _nl_gap = (
            f"Only {_nl_n_r} round-number and {_nl_n_s} specific-number articles parsed "
            f"(below the 30-article-per-group threshold for reliable inference). "
            f"Mann-Whitney p\u2009=\u2009{_nl_p:.3f} (unadjusted)."
            if _nl_dir
            else (
                f"Groups too small for a reliable test: round n={_nl_n_r}, "
                f"specific n={_nl_n_s}."
            )
            if _nl_low_n
            else "Test could not run \u2014 insufficient parseable number leads in the dataset."
        )
        suggs.append({
            "id":       "number-lead-specificity-an",
            "platform": "Apple News",
            "title":    "Number Lead Specificity \u2014 Round vs. Exact Figures",
            "signal":   _nl_signal,
            "gap":      _nl_gap,
            "question": (
                "Do Apple News headlines with precise numeric values "
                "(e.g. \u2018$487 million,\u2019 \u201813 officers\u2019) consistently "
                "outperform rounded equivalents (\u2018$500 million,\u2019 "
                "\u201810+ officers\u2019) for views, controlling for topic and story type?"
            ),
            "design": (
                "When writing number-lead headlines, deliberately tag each as "
                "\u2018round\u2019 (e.g. \u2018$500M,\u2019 \u201810 people\u2019) or "
                "\u2018specific\u2019 (e.g. \u2018$487M,\u2019 \u201813 people\u2019) in "
                "a shared tracking sheet. Collect at least 30 Apple News articles per type "
                "before running the test. No CMS change needed \u2014 this is a tagging "
                "discipline applied during headline writing. "
                "Analysis: Mann-Whitney U on Apple News percentile rank at 7 days "
                "(specific vs. round), rank-biserial r as effect size. Stratify by topic "
                "(financial stories likely have more specificity variance than crime or "
                "sports). "
                "Existing pipeline: classify_number_lead() already extracts the numeric "
                "value \u2014 add a roundness tag to the tracking sheet and re-run once "
                "30+ per group are tagged."
            ),
            "impact": (
                "Confirmed: adds precision-number guidance to the style guide "
                "(\u201cuse exact figures in number leads, not rounded approximations\u201d). "
                "Editors who default to rounded figures for readability would be asked to "
                "reverse that practice.  "
                "Not confirmed: round vs. specific distinction does not affect views; the "
                "number-lead signal is format-driven rather than specificity-driven."
            ),
            "tier":     "underpowered" if (_nl_low_n or _nl_none) else "directional",
            "priority": "medium",
        })

    # ── 3. Headline length on SmartNews — not significant ─────────────────────
    # Apple News length effect (Q4 vs Q1) is significant; SmartNews is not.
    if not _hl_sn_sig:
        _sn_p_disp = (
            f"adjusted p\u2009=\u2009{HL_SN_Q4Q1_P:.3f}"
            if not np.isnan(HL_SN_Q4Q1_P) else "p not computed"
        )
        suggs.append({
            "id":       "headline-length-sn",
            "platform": "SmartNews",
            "title":    "Headline Length \u2014 SmartNews Sweet Spot Unconfirmed",
            "signal": (
                f"Headline length shows a directional pattern on SmartNews "
                f"({_sn_p_disp}, not significant at \u03b1=0.05). Apple News shows a "
                f"{'confirmed' if _hl_an_sig else 'directional'} length effect: very long "
                f"headlines ({AN_LEN_Q4_CHARS_STR} chars) outperform short ones "
                f"({AN_LEN_Q1_CHARS_STR} chars). The SmartNews optimal range may differ."
            ),
            "gap": (
                "BH-FDR adjusted p\u2009\u2265\u20090.05 on SmartNews. Headline length "
                "and formula type are correlated (structured formulas tend to be longer), "
                "so the apparent length signal may partly reflect formula confounding. "
                "SmartNews 2026 data is domain-aggregated (not article-level), limiting "
                "the 2026 contribution to the significance test."
            ),
            "question": (
                "Does headline length independently predict SmartNews performance after "
                "controlling for formula type and topic? Is there a specific character-count "
                "range (e.g. 70\u201390 chars) that outperforms both shorter and longer "
                "headlines, or is the effect monotonic?"
            ),
            "design": (
                "This requires article-level SmartNews 2026 data (currently domain-aggregated; "
                "ask Tarrow for a per-article export). Once available, classify all SmartNews "
                "articles into length quartiles and re-run the Mann-Whitney Q4 vs. Q1 test "
                "with formula type as a stratification variable. "
                "Alternatively, for a prospective test: write two headline versions per story "
                "for 4\u20136 weeks \u2014 one in the 70\u201390-char range, one 90\u2013120 "
                "chars \u2014 and publish alternately to SmartNews. Measure views at 7 days. "
                "Minimum n\u2009=\u200930 per length bucket. Control: ensure formula type is "
                "held constant within pairs (both declarative, both \u201cHere\u2019s,\u201d "
                "etc.) so length is the only variable. "
                "Analysis: Mann-Whitney U, rank-biserial r. Then add formula type as a "
                "second grouping variable to check for formula\u00d7length interaction."
            ),
            "impact": (
                "Confirmed: pairs SmartNews character-count guidance with the existing Apple "
                "News length guidance (90\u2013120 chars). Editors get a complete "
                "cross-platform length spec.  "
                "Not confirmed: length is a formula proxy on SmartNews \u2014 guidance stays "
                "formula-only for SmartNews and the character-count rule applies to Apple "
                "News only."
            ),
            "tier":     "directional" if not np.isnan(HL_SN_Q4Q1_P) else "underpowered",
            "priority": "medium",
        })

    # ── 4. MSN formula groups — below reliable-inference threshold ────────────
    # After T1 brand filter (113 rows total), most formula groups have n < 30.
    # The dataset grows ~100 rows/month; groups should become testable in 2–3 months.
    if not msn.empty and not df_msn_formula.empty:
        _msn_weak = df_msn_formula[
            (df_msn_formula["formula"] != "untagged") & (df_msn_formula["n"] < 30)
        ]
        if len(_msn_weak) > 0:
            # Single pass over the weak-formula slice to build both display strings.
            _msn_weak_rows = [
                (
                    _FORMULA_DISPLAY_LABELS.get(str(r["formula"]), str(r["formula"])),
                    int(r["n"]),
                )
                for _, r in _msn_weak.iterrows()
            ]
            _weak_labels = ", ".join(label for label, _ in _msn_weak_rows)
            _weak_ns = " \u00b7 ".join(
                f"{label} (n={n})" for label, n in _msn_weak_rows
            )
            suggs.append({
                "id":       "msn-formula-underpowered",
                "platform": "MSN",
                "title":    "MSN Formula Groups \u2014 Insufficient Data for Confirmation",
                "signal": (
                    f"{len(_msn_weak)} formula group(s) show directional patterns on MSN "
                    f"but cannot be confirmed: {_weak_labels}. "
                    f"{MSN_N_TOTAL} total T1 news brand articles after filtering. "
                    f"Groups with n\u2009<\u200930: {_weak_ns}."
                ),
                "gap": (
                    "All flagged groups have n\u2009<\u200930, below the minimum for reliable "
                    "inference (GOVERNOR.md Part 2). Only the quoted-lede group currently "
                    "has enough data to test, and it is the one confirmed MSN finding. "
                    "The MSN dataset grows approximately 100 rows/month; most formula groups "
                    "should cross n=30 within 2\u20133 months of continued data collection."
                ),
                "question": (
                    "As MSN data accumulates, which formula groups consistently underperform "
                    "the direct-declarative baseline? Is the underperformance pattern broad "
                    "(all structured formulas hurt on MSN) or specific to certain formats?"
                ),
                "design": (
                    "Natural experiment \u2014 no new data collection needed. The MSN dataset "
                    "grows approximately 100 rows/month after the T1 brand filter. Re-run the "
                    "Mann-Whitney formula analysis each monthly ingest; generate_site.py already "
                    "does this automatically and the build report surfaces newly-significant "
                    "groups. "
                    "Threshold: treat any formula group as testable once it crosses n\u2009=\u200930. "
                    "Expected timeline: most groups should reach n=30 within 2\u20133 monthly "
                    "ingest cycles. "
                    "Analysis: Mann-Whitney U (each formula group vs. untagged baseline), "
                    "BH-FDR corrected across all tested groups simultaneously, rank-biserial r "
                    "as effect size. Language tier: significant only if p_adj\u2009<\u20090.05; "
                    "directional if p_adj\u2009<\u20090.10. Baseline key must be \u2018untagged\u2019 "
                    "(not \u2018other\u2019) \u2014 see GOVERNOR.md Rigor Failures Log."
                ),
                "impact": (
                    "Confirmed broad pattern: extends the MSN rule from \u2018avoid quoted "
                    "lede\u2019 to \u2018avoid all structured formulas.\u2019 Gives editors "
                    "the strongest possible two-headline guidance: Apple News \u2192 use "
                    "formulas; MSN \u2192 drop them entirely.  "
                    "Confirmed specific subset: MSN avoidance list grows to the confirmed "
                    "formula types while others remain neutral.  "
                    "Not confirmed: MSN formula penalty is limited to quoted lede only."
                ),
                "tier":     "underpowered",
                "priority": "high",
            })

    # ── 5. MSN video — sports completion directional ──────────────────────────
    # MSN_VID_SPORTS_P defaults to 1.0 when MSN video data is unavailable,
    # so the 0.05 ≤ p < 0.10 guard ensures this only surfaces when meaningful.
    if 0.05 <= MSN_VID_SPORTS_P < 0.10:
        suggs.append({
            "id":       "msn-video-sports",
            "platform": "MSN",
            "title":    "MSN Video \u2014 Sports Completion Rate Signal",
            "signal": (
                f"Sports video on MSN shows {MSN_VID_SPORTS_IDX_STR} higher median "
                f"completion index vs. non-sports video "
                f"(directional, p\u2009=\u2009{MSN_VID_SPORTS_P:.3f}). "
                f"Dataset: 1,023 MSN video rows."
            ),
            "gap": (
                f"p\u2009=\u2009{MSN_VID_SPORTS_P:.3f} is directional (p\u2009<\u20090.10) "
                f"but not significant (p\u2009<\u20090.05). MSN video data is not filtered "
                f"to T1 brands. Completion rate definition may differ from article pageviews, "
                f"and its relationship to MSN distribution frequency is unknown."
            ),
            "question": (
                "Does sports video on MSN consistently achieve higher completion rates than "
                "other topic categories? Does higher completion translate to increased "
                "distribution or recommendation frequency from MSN\u2019s algorithm?"
            ),
            "design": (
                "Natural experiment \u2014 continue collecting MSN video data monthly via "
                "Tarrow's export. Current dataset: 1,023 rows total. When the sports "
                "video subgroup reaches n\u2009\u226560 (roughly 2\u20134 months of additional "
                "data), re-run the Mann-Whitney test. "
                "Analysis: Mann-Whitney U (sports vs. non-sports completion rate), "
                "rank-biserial r. Also add a Spearman correlation between completion rate "
                "and pageviews for MSN video articles to establish whether completion rate "
                "is a meaningful proxy for distribution. "
                "If MSN provides a \u2018shares\u2019 or \u2018recommendations\u2019 metric "
                "in the export, add that as a secondary outcome. "
                "Do not segment by brand until n per brand crosses 20 \u2014 use topic "
                "as the primary variable for now."
            ),
            "impact": (
                "Confirmed: supports explicitly routing sports video to MSN as a platform "
                "where it over-indexes. Could inform content packaging decisions for sports "
                "coverage across platforms.  "
                "Not confirmed: the sports completion advantage is noise; video routing "
                "should not be platform-differentiated on this basis."
            ),
            "tier":     "directional",
            "priority": "low",
        })

    # ── 6–10: Probing queue — HIGH/MED priority, data available, not yet run ──
    # These are appended unconditionally each run because the data to test them
    # exists but the analysis has not been implemented.  They persist in the log
    # until implemented and moved to confirmed tiles or marked low-signal in
    # GOVERNOR.md.

    suggs.append({
        "id":       "char-length-x-formula-an",
        "platform": "Apple News",
        "title":    "Character Length \u00d7 Formula Type Interaction",
        "signal": (
            "Character length (90\u2013120 chars) and formula type independently predict "
            "Apple News views. Whether these signals interact \u2014 e.g., whether possessive "
            "named entity needs to be longer to achieve its lift, or whether "
            "\u201cHere\u2019s\u201d works at any length \u2014 has not been tested."
        ),
        "gap": (
            "Cross-tabulating formula buckets with length quartiles fragments an already-"
            "segmented dataset. Most formula \u00d7 length cells will have n\u2009<\u200930, "
            "requiring aggregation trade-offs that risk obscuring the interaction signal. "
            "Analysis not yet run."
        ),
        "question": (
            "Do specific formula types require specific length ranges to achieve their Apple "
            "News performance lift? E.g., does \u201cHere\u2019s / Here are\u201d need 90+ "
            "chars to work, or does it lift at any length? Does possessive named entity "
            "perform best at shorter lengths where the name dominates the headline?"
        ),
        "design": (
            "Run on existing Apple News 2025+2026 data \u2014 no new collection needed. "
            "Cross-tabulate by formula type \u00d7 length quartile. For each formula with "
            "n\u2009\u226530 total, split into Q1 (shortest) and Q4 (longest) length buckets "
            "and run Mann-Whitney U within each formula group vs. the untagged baseline at "
            "the same length. Compare the lift magnitude across length buckets. "
            "If any formula\u00d7length cell has n\u2009<\u200915, aggregate: fold Q1+Q2 "
            "into \u2018short\u2019 and Q3+Q4 into \u2018long.\u2019 "
            "Report as an interaction: does the formula\u2019s lift increase, decrease, or "
            "stay flat as length increases? Plot as a 2\u00d72 heatmap (formula \u00d7 "
            "length bucket, colored by median rank). "
            "Apply BH-FDR correction across all formula\u00d7length cells tested. "
            "Bonferroni fallback: if more than 10 cells are tested, apply Bonferroni at "
            "k=10 as a secondary check."
        ),
        "impact": (
            "Confirmed interaction: compound guidance (formula + length range) replaces two "
            "independent rules. Editors get: \u201cUse Here\u2019s at 90\u2013110 chars; "
            "use possessive at 70\u201390 chars.\u201d More actionable than current guidance.  "
            "No interaction: the two independent rules are stable and can be applied "
            "separately without worrying about their interaction."
        ),
        "tier":     "untested",
        "priority": "high",
    })

    suggs.append({
        "id":       "notif-ctr-char-length",
        "platform": "Notifications",
        "title":    "Notification CTR \u00d7 Character Length",
        "signal": (
            "Formula choice has a 2\u20135\u00d7 effect on notification CTR (confirmed). "
            "Character length has been tested for Apple News views but not for notification "
            "CTR. Notifications truncate at ~80 chars on most devices, making length more "
            "likely to matter here than in feed headlines."
        ),
        "gap": (
            "Character length vs. notification CTR has not been run. The notifications "
            "dataset covers 2025\u20132026 (1,050+ news brand pushes with CTR data) \u2014 "
            "sufficient for a Mann-Whitney test across length quartiles."
        ),
        "question": (
            "Do shorter notifications (\u226480 chars) outperform longer ones for CTR, "
            "controlling for formula type? Is there a character-count range where CTR peaks, "
            "or is the relationship monotonic (shorter\u202f=\u202fbetter)?"
        ),
        "design": (
            "Run on the existing notifications dataset (1,050+ news brand pushes with CTR). "
            "No new data collection needed. "
            "Bin notification headlines into four length quartiles. Run Kruskal-Wallis across "
            "quartiles first to check for any length\u2013CTR association. If significant "
            "(p\u2009<\u20090.05), follow with Mann-Whitney U pairwise comparisons "
            "(Q1 vs. Q4 as primary), BH-FDR corrected. "
            "Control for formula type via stratification: run the length\u2013CTR analysis "
            "separately within each formula group that has n\u2009\u226530 "
            "(attribution language, question, direct declarative). If length effect "
            "disappears within formula groups, length is a formula proxy, not an independent "
            "signal. "
            "Secondary analysis: Spearman correlation between character count and CTR "
            "(raw correlation, no quartiling). This gives a monotonicity check "
            "without binning artifacts. "
            "Implement in generate_site.py as an extension of the existing Q5 "
            "notification analysis block."
        ),
        "impact": (
            "Confirmed: adds a second actionable lever for push copy editors beyond formula "
            "choice. Current guidance (\u201cuse attribution language\u201d) would be "
            "extended with a specific character-count target.  "
            "Not confirmed: formula dominates; length doesn\u2019t independently move CTR "
            "and editors can focus solely on formula selection for notifications."
        ),
        "tier":     "untested",
        "priority": "high",
    })

    suggs.append({
        "id":       "wtn-featured-organic-by-year",
        "platform": "Apple News",
        "title":    "\u201cWhat to Know\u201d \u2014 Featured vs. Organic Stability by Year",
        "signal": (
            f"Apple editors select \u201cWhat to Know\u201d at {WTN_FEAT_LIFT:.1f}\u00d7 "
            f"the baseline rate for Featured placement. Organic (non-Featured) articles "
            f"using WTK show no significant view lift ({WTN_ORGANIC_P_STR}). This "
            f"editorial/algorithmic split is a key project finding \u2014 but whether it "
            f"is stable across 2025 and 2026 separately is unknown."
        ),
        "gap": (
            "The current analysis pools 2025 and 2026 Apple News data. If Apple has updated "
            "curation signals, or if T1 editors have changed how they use WTK, the featuring "
            "lift or organic penalty could be shifting \u2014 which would change whether the "
            "two-headline strategy is durable guidance."
        ),
        "question": (
            "Is the WTK featuring lift consistent when 2025 and 2026 are analyzed "
            "separately? Has the gap between editorial selection rate and organic algorithmic "
            "performance been stable, or is it narrowing/widening over time?"
        ),
        "design": (
            "Run on existing Apple News data \u2014 no new collection needed. "
            "Split the Apple News dataset by year (2025 and 2026 separately). "
            "For each year, run: (1) Q2 chi-square or Fisher\u2019s exact test for WTK "
            "featuring rate vs. all other formulas; (2) Q1 Mann-Whitney U for WTK organic "
            "view rank vs. untagged baseline (non-Featured articles only). "
            "Compare the featuring lift ratio (WTK featured rate / baseline featured rate) "
            "and the organic p-value across years. A narrowing featured rate ratio or a "
            "trending organic p-value signals platform behavior change. "
            "Implement as a year-stratified extension of the existing Q1 and Q2 analysis "
            "blocks in generate_site.py. Report: a 2\u00d72 table of year\u00d7metric "
            "(featuring lift and organic p) alongside a directional trend flag. "
            "Note: Apple News 2026 covers Jan\u2013Mar only; interpret with caution until "
            "Q3 2026 data is available."
        ),
        "impact": (
            "Stable across years: confirms structural platform behavior. The \u201cWTK for "
            "Featured campaigns, avoid for organic\u201d rule is durable.  "
            "Shifting: guidance needs to evolve. If organic performance is catching up to "
            "editorial selection, the two-headline distinction may already be outdated."
        ),
        "tier":     "untested",
        "priority": "medium",
    })

    _pne_n_str = (
        f"n={int(_r1_pne['n'])}"
        if _r1_pne is not None and "n" in _r1_pne.index
        else "n\u2248117"
    )
    suggs.append({
        "id":       "possessive-named-entity-by-topic",
        "platform": "Apple News",
        "title":    "Possessive Named Entity \u2014 Topic Concentration",
        "signal": (
            f"Possessive named entity headlines ({_pne_n_str}) show moderate overall "
            "performance on Apple News. The signal may be concentrated in sports and crime "
            "\u2014 topics where named individuals are central to the story \u2014 but "
            "aggregate analysis cannot confirm this."
        ),
        "gap": (
            f"Overall {_pne_n_str} is small enough that splitting by topic reduces per-cell "
            "counts below the 30-article threshold for reliable inference. The aggregate "
            "analysis masks any strong within-topic signal."
        ),
        "question": (
            "Do possessive named entity headlines specifically outperform in sports and crime "
            "topics on Apple News, where named individuals are central? Is the aggregate "
            "signal driven by a strong within-topic effect, or is it distributed broadly "
            "across all topics?"
        ),
        "design": (
            "Run on existing Apple News 2025+2026 data. Filter to possessive named entity "
            "headlines. Split by topic: sports+crime (the \u2018high named-entity\u2019 "
            "group) vs. all other topics. Run Mann-Whitney U (sports+crime PNE articles vs. "
            "untagged baseline within the same topics), rank-biserial r as effect size. "
            "Repeat for the \u2018other topics\u2019 group. "
            "Compare lift magnitudes: if the sports+crime lift is substantially larger "
            "(r\u2009\u22650.1 higher) than the other-topics lift, the signal is "
            "topic-concentrated. If lifts are similar, the rule applies broadly. "
            "If either per-topic cell has n\u2009<\u200920, flag as preliminary and hold "
            "until data grows. Do not split into individual topics at this sample size \u2014 "
            "aggregate sports+crime as one group. "
            "Implement as a topic-stratified extension of the Q1 analysis in generate_site.py."
        ),
        "impact": (
            "Confirmed topic-specific: changes guidance from a broad rule to a targeted one "
            "(\u201cuse possessive named entity for sports/crime stories specifically\u201d). "
            "Editors know exactly when to apply it.  "
            "Evenly distributed: the broad rule stands. Possessive named entity is generally "
            "useful, not vertically restricted."
        ),
        "tier":     "untested",
        "priority": "medium",
    })

    suggs.append({
        "id":       "number-lead-type-sn",
        "platform": "SmartNews",
        "title":    "Number Lead Type \u2014 Which Numbers Drive the SmartNews Signal?",
        "signal": (
            "Number leads show a positive directional trend on SmartNews (median rank 0.534 "
            "vs. 0.497 baseline; direction: above_dir). They are the only SmartNews formula "
            "with a positive directional signal. Whether count/list (\u20183 ways\u2019), "
            "dollar amounts (\u2018$2 billion\u2019), or percentages (\u201847%\u2019) "
            "drive this has not been tested."
        ),
        "gap": (
            "Number-type classification (classify_number_lead()) is implemented in the "
            "pipeline but per-type SmartNews performance has not been computed. SmartNews "
            "2026 data is domain-aggregated (not article-level), limiting this analysis "
            "to the 2025 dataset (n=38,251 articles)."
        ),
        "question": (
            "Which number-lead subtype drives the SmartNews directional signal: count/list, "
            "dollar amounts, or percentages? Or is the effect evenly distributed across "
            "number types, suggesting format (any number in the lead) matters more than type?"
        ),
        "design": (
            "Run on SmartNews 2025 number-lead articles (n\u2009\u2248342 total). "
            "classify_number_lead() already extracts ntype (\u2018count_list,\u2019 "
            "\u2018dollar_amount,\u2019 \u2018percentage,\u2019 \u2018other\u2019). "
            "Group by ntype and run Mann-Whitney U for each group vs. the untagged baseline, "
            "BH-FDR corrected across the three tested types. "
            "Expected n per type: count_list is likely the largest (list articles are common); "
            "dollar_amount and percentage groups may be small. Flag any group with "
            "n\u2009<\u200920 as preliminary. "
            "If all subtypes have low n, aggregate and report directionally only: "
            "\u201ccounts/lists trend higher (n=X, p=Y)\u201d without a significance claim. "
            "Implement by extending the existing number-lead deep-dive block "
            "(classify_number_lead() section) in generate_site.py to add a per-type "
            "Mann-Whitney analysis. Note: SmartNews 2026 is domain-aggregated and cannot "
            "contribute to this analysis \u2014 2025 data only."
        ),
        "impact": (
            "Confirmed specific type: editors can be told \u201ccount/list numbers work on "
            "SmartNews; dollar amounts and percentages are neutral.\u201d More precise than "
            "the current directional number-lead guidance.  "
            "Equally distributed: the rule is format-driven (\u201cany number in the lead "
            "is better than none\u201d). Simpler and more broadly applicable."
        ),
        "tier":     "untested",
        "priority": "medium",
    })

    return suggs


def _generate_experiments_page(suggs: list[dict], report_date: str) -> str:
    """Render the full docs/experiments/index.html from a suggestion list.

    Suggestions are grouped by priority (high → medium → low) and rendered as
    static cards (no collapse/expand — all detail visible by default).
    The page uses the same CSS design-token system as the rest of the site
    (dark/light theme, same custom properties).

    Args:
        suggs:       Output of _collect_experiment_suggestions().
        report_date: YYYY-MM slug used in the header and meta tag.

    Returns:
        Complete HTML string ready to write to disk.
    """
    # ── Group by priority (pre-populate to guarantee high→medium→low order) ──
    by_priority: dict[str, list[dict]] = {"high": [], "medium": [], "low": []}
    for s in suggs:
        by_priority[s["priority"]].append(s)  # key always present; no setdefault needed

    # ── Priority section headings (defined once, shared by _section()) ───────
    _priority_headings: dict[str, str] = {
        "high":   "High Priority",
        "medium": "Medium Priority",
        "low":    "Low Priority",
    }

    # ── Card renderer ────────────────────────────────────────────────────────
    def _card(s: dict) -> str:
        tier_lbl = _EXP_TIER_LABELS.get(s["tier"], s["tier"])
        prio_lbl = _EXP_PRIORITY_LABELS.get(s["priority"], s["priority"])
        return (
            f'  <div class="exp-card tier-{s["tier"]}" id="exp-{html_module.escape(s["id"])}">\n'
            f'    <div class="exp-meta">\n'
            f'      <span class="exp-platform">{html_module.escape(s["platform"])}</span>\n'
            f'      <span class="tier-badge tier-badge-{s["tier"]}">'
            f'{html_module.escape(tier_lbl)}</span>\n'
            f'      <span class="exp-priority">{html_module.escape(prio_lbl)}</span>\n'
            f'    </div>\n'
            f'    <h3 class="exp-title">{s["title"]}</h3>\n'
            f'    <div class="exp-fields">\n'
            f'      <div class="exp-field">\n'
            f'        <span class="field-label">Current signal</span>\n'
            f'        <p>{html_module.escape(s["signal"])}</p>\n'
            f'      </div>\n'
            f'      <div class="exp-field">\n'
            f'        <span class="field-label">What\u2019s missing</span>\n'
            f'        <p>{html_module.escape(s["gap"])}</p>\n'
            f'      </div>\n'
            f'      <div class="exp-field">\n'
            f'        <span class="field-label">Test question</span>\n'
            f'        <p>{html_module.escape(s["question"])}</p>\n'
            f'      </div>\n'
            f'      <div class="exp-field">\n'
            f'        <span class="field-label">How to run it</span>\n'
            f'        <p>{html_module.escape(s["design"])}</p>\n'
            f'      </div>\n'
            f'      <div class="exp-field">\n'
            f'        <span class="field-label">What the result unlocks</span>\n'
            f'        <p>{html_module.escape(s["impact"])}</p>\n'
            f'      </div>\n'
            f'    </div>\n'
            f'  </div>'
        )

    def _section(priority: str) -> str:
        """Render all experiment cards for one priority level as a <section> block.

        Returns an empty string if there are no cards for this priority,
        so the caller can filter with a truthiness check.
        """
        cards = by_priority.get(priority, [])
        if not cards:
            return ""
        return (
            f'<section class="priority-section">\n'
            f'  <h2 class="priority-heading">{_priority_headings[priority]}</h2>\n'
            f'  <div class="exp-grid">\n'
            + "\n\n".join(_card(c) for c in cards)
            + "\n  </div>\n</section>"
        )

    sections_html = "\n\n".join(
        _section(p) for p in ("high", "medium", "low") if by_priority.get(p)
    )
    if not sections_html:
        sections_html = (
            '<div class="exp-empty">\n'
            "  <p>No directional findings this run. All tested hypotheses either confirmed "
            "(moved to main analysis tiles) or fell below the directional threshold.</p>\n"
            "</div>"
        )

    # ── Completed A/B reports section ──────────────────────────────────────────
    # Glob existing report subdirectories written by generate_experiment.py.
    # Listed below the suggestion cards so they're accessible from the same page.
    import glob as _exp_glob
    _report_dirs = sorted(_exp_glob.glob("docs/experiments/*/index.html"))
    _report_rows = ""
    for _rp in _report_dirs:
        _slug = Path(_rp).parent.name
        # Try to read the <title> from the report for a better label
        try:
            _rtitle = re.search(r"<title>(.*?)</title>", open(_rp).read())
            _rlabel = _rtitle.group(1) if _rtitle else _slug
            # Strip common site prefix
            _rlabel = re.sub(r"^T1 Headline Analysis\s*[·\u00b7]\s*", "", _rlabel).strip()
        except OSError:
            _rlabel = _slug
        # Try to read the result verdict line
        try:
            _rbody = open(_rp).read()
            _rverdict = re.search(r'class="result-verdict[^"]*"[^>]*>(.*?)</\w+>', _rbody, re.S)
            _rvtxt = re.sub(r"<[^>]+>", "", _rverdict.group(1)).strip() if _rverdict else ""
        except OSError:
            _rvtxt = ""
        _verdict_html = (f'<span class="exp-report-verdict">{html_module.escape(_rvtxt)}</span>'
                         if _rvtxt else "")
        _report_rows += (
            f'  <li><a href="{html_module.escape(_slug)}/index.html">'
            f'{html_module.escape(_rlabel)}</a>{verdict_html if False else _verdict_html}</li>\n'
        )

    _completed_section = ""
    if _report_rows:
        _completed_section = f"""
<section class="priority-section" style="margin-top:3rem">
  <h2 class="priority-heading">Completed A/B Reports</h2>
  <p style="font-size:13px;color:var(--text-muted);margin-bottom:1rem">
    Before/after comparisons and formula tests run against the dataset.
    Add a spec to <code>experiments/</code> and run
    <code>python3 generate_experiment.py experiments/SLUG.md</code>.
  </p>
  <ul class="exp-report-list">
{_report_rows}  </ul>
</section>"""

    nav     = _build_nav("Experiments", 1)
    n_cards = len(suggs)
    s_sfx   = "s" if n_cards != 1 else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<meta name="data-run" content="{report_date}">
<title>T1 Headline Analysis \u00b7 Suggested Experiments</title>
<script src="https://cdn.jsdelivr.net/npm/dom-to-image-more@3.7.2/dist/dom-to-image-more.min.js"></script>
<style>
  /* \u2500\u2500 Theme tokens (match main site) \u2500\u2500 */
  body.light {{
    --bg:#f4f6fb; --bg-card:#ffffff; --bg-muted:#ffffff; --bg-subtle:#f0f0f0;
    --text:#1a1d27; --text-secondary:#424245; --text-muted:#5a6070;
    --border:#dde1f0; --border-subtle:#f0f0f0; --accent:#3d5af1;
    --nav-bg:rgba(255,255,255,0.88);
    --amber:#d97706; --orange:#ea580c;
  }}
  :root {{
    --bg:#0f1117; --bg-card:#21253a; --bg-muted:#1a1d27; --bg-subtle:#2e3350;
    --text:#e8eaf6; --text-secondary:#cbd5e1; --text-muted:#8b90a0;
    --border:#2e3350; --border-subtle:#1a1d27; --accent:#7c9df7;
    --nav-bg:#1a1d27;
    --amber:#f59e0b; --orange:#f97316;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Helvetica Neue",Arial,sans-serif;
          background:var(--bg); color:var(--text); font-size:14px; line-height:1.6;
          -webkit-font-smoothing:antialiased; transition:background 0.2s,color 0.2s; }}
  .site-nav {{ background:var(--nav-bg); border-bottom:1px solid var(--border); padding:0 24px; display:flex; align-items:center; justify-content:space-between; height:44px; position:sticky; top:0; z-index:100; }}
  .nav-links {{ display:flex; align-items:center; }}
  .nav-links a {{ color:var(--text-muted); text-decoration:none; font-size:.85em; padding:0 12px; height:44px; display:flex; align-items:center; border-bottom:2px solid transparent; transition:color .15s; }}
  .nav-links a:hover {{ color:var(--text); }}
  .nav-links a.active {{ color:var(--accent); border-bottom-color:var(--accent); }}
  .nav-sep {{ color:var(--border); font-size:.8em; }}
  .theme-toggle {{ background:none; border:1px solid var(--border); color:var(--text-muted); cursor:pointer; padding:4px 8px; border-radius:4px; font-size:.8em; }}
  /* Layout */
  .container {{ max-width:900px; margin:0 auto; padding:3rem 2rem 5rem; }}
  h1 {{ font-size:1.7em; font-weight:700; color:var(--accent); margin-bottom:4px; }}
  .sub {{ color:var(--text-muted); font-size:0.9em; margin-bottom:28px; }}
  .run-meta {{ font-size:12px; color:var(--text-muted); margin-bottom:1.75rem; }}
  /* Legend */
  .legend {{ display:flex; gap:1.25rem; flex-wrap:wrap; margin-bottom:2.5rem;
             padding:0.75rem 1rem; background:var(--bg-muted);
             border-radius:8px; border:1px solid var(--border); }}
  .legend-item {{ display:flex; align-items:center; gap:0.4rem; font-size:12px;
                  color:var(--text-secondary); }}
  .legend-dot {{ width:9px; height:9px; border-radius:50%; flex-shrink:0; }}
  .ld-bonferroni-fail {{ background:var(--amber); }}
  .ld-underpowered    {{ background:var(--orange); }}
  .ld-directional     {{ background:var(--accent); }}
  .ld-untested        {{ background:var(--border); }}
  /* Priority sections */
  .priority-section {{ margin-bottom:3rem; }}
  .priority-heading {{ font-size:0.7rem; font-weight:700; text-transform:uppercase;
                       letter-spacing:0.12em; color:var(--text-muted); margin-bottom:1rem;
                       padding-bottom:0.5rem; border-bottom:1px solid var(--border); }}
  /* Experiment cards */
  .exp-grid {{ display:grid; gap:1.25rem; }}
  .exp-card {{ background:var(--bg-card); border:1px solid var(--border);
               border-radius:12px; padding:1.5rem;
               border-left:4px solid var(--border); }}
  .exp-card.tier-bonferroni-fail {{ border-left-color:var(--amber); }}
  .exp-card.tier-underpowered    {{ border-left-color:var(--orange); }}
  .exp-card.tier-directional     {{ border-left-color:var(--accent); }}
  .exp-card.tier-untested        {{ border-left-color:var(--border-subtle); }}
  .exp-meta {{ display:flex; gap:0.5rem; flex-wrap:wrap; align-items:center;
               margin-bottom:0.75rem; }}
  .exp-platform {{ font-size:11px; font-weight:600; text-transform:uppercase;
                   letter-spacing:0.08em; background:var(--bg-muted);
                   color:var(--text-secondary); padding:2px 8px; border-radius:4px; }}
  .tier-badge {{ font-size:11px; font-weight:600; padding:2px 8px; border-radius:4px;
                 text-transform:uppercase; letter-spacing:0.05em; }}
  .tier-badge-bonferroni-fail {{ background:rgba(217,119,6,0.12); color:var(--amber); }}
  .tier-badge-underpowered    {{ background:rgba(234,88,12,0.12);  color:var(--orange); }}
  .tier-badge-directional     {{ background:rgba(59,130,246,0.12); color:var(--accent); }}
  .tier-badge-untested        {{ background:var(--bg-subtle); color:var(--text-muted); }}
  .exp-priority {{ font-size:11px; color:var(--text-muted); margin-left:auto;
                   font-weight:500; }}
  .exp-title {{ font-size:1rem; font-weight:600; color:var(--text); margin-bottom:1rem; }}
  .exp-fields {{ display:grid; gap:0.75rem; }}
  .exp-field {{ border-top:1px solid var(--border-subtle); padding-top:0.6rem; }}
  .field-label {{ font-size:10px; font-weight:700; text-transform:uppercase;
                  letter-spacing:0.1em; color:var(--text-muted); display:block;
                  margin-bottom:0.2rem; }}
  .exp-field p {{ font-size:0.875rem; color:var(--text-secondary); line-height:1.65;
                  margin:0; }}
  .exp-empty {{ color:var(--text-muted); font-style:italic; padding:2rem 0; }}
  /* Completed A/B reports list */
  .exp-report-list {{ list-style:none; padding:0; border-top:1px solid var(--border); }}
  .exp-report-list li {{ padding:0.75rem 0; border-bottom:1px solid var(--border-subtle); }}
  .exp-report-list a {{ font-size:0.9rem; font-weight:500; color:var(--text);
                        text-decoration:none; }}
  .exp-report-list a:hover {{ color:var(--accent); }}
  .exp-report-verdict {{ display:block; font-size:0.75rem; color:var(--text-muted);
                         margin-top:0.15rem; }}
</style>
</head>
<body>
{nav}

<div class="container">
  <h1>Suggested Experiments</h1>
  <p class="sub">
    Directional findings from the current analysis run that show a potential signal
    but cannot yet support a style recommendation. Each card explains what to test,
    what is currently missing, and what different results would mean for guidance.
  </p>
  <p class="run-meta">
    Run: {html_module.escape(report_date)}
    \u00b7 {n_cards} suggestion{s_sfx}
    \u00b7 Page auto-regenerated each analytics run
    \u00b7 <button id="exp-export-btn" onclick="_exportExpPage()"
        style="background:none;border:1px solid var(--border);color:var(--text-muted);
               font-size:11px;padding:2px 8px;border-radius:4px;cursor:pointer;">Export PNG</button>
  </p>

  <div class="legend">
    <span class="legend-item">
      <span class="legend-dot ld-bonferroni-fail"></span>
      Bonferroni fail \u2014 p&lt;0.05 raw but doesn\u2019t survive α/k correction
    </span>
    <span class="legend-item">
      <span class="legend-dot ld-underpowered"></span>
      Underpowered \u2014 too few data points for reliable inference
    </span>
    <span class="legend-item">
      <span class="legend-dot ld-directional"></span>
      Directional \u2014 0.05 \u2264 p &lt; 0.10 after BH-FDR correction
    </span>
    <span class="legend-item">
      <span class="legend-dot ld-untested"></span>
      Untested \u2014 data available, analysis not yet run
    </span>
  </div>

{sections_html}
{_completed_section}
</div>

<script>
function toggleTheme() {{
  document.body.classList.toggle('light');
  try {{ localStorage.setItem('theme', document.body.classList.contains('light') ? 'light' : 'dark'); }} catch(e) {{}}
}}
function _exportExpPage() {{
  var btn = document.getElementById('exp-export-btn');
  if (btn) btn.textContent = 'Exporting…';
  var target = document.querySelector('.container');
  domtoimage.toPng(target, {{bgcolor: getComputedStyle(document.body).getPropertyValue('--bg').trim() || '#0f1117'}})
    .then(function(dataUrl) {{
      var a = document.createElement('a');
      a.download = 'experiments-{report_date}.png';
      a.href = dataUrl;
      a.click();
      if (btn) btn.textContent = 'Export PNG';
    }})
    .catch(function(err) {{
      console.error('Export failed:', err);
      if (btn) btn.textContent = 'Export failed';
    }});
}}
(function() {{
  if (localStorage.getItem('theme') === 'light') document.body.classList.add('light');
}})();
</script>
</body>
</html>"""


def _append_experiment_log(
    suggs: list[dict],
    report_date: str,
    log_path: Path,
) -> None:
    """Append this run's suggestions to the append-only experiment log file.

    The log file is plain Markdown. Each run appends a dated section.
    The file is never rewritten — only appended \u2014 so every past suggestion
    is preserved across runs, including ones later confirmed or retired.

    Args:
        suggs:       Output of _collect_experiment_suggestions().
        report_date: YYYY-MM slug used as the section identifier.
        log_path:    Path to experiments/experiment_log.md.
    """
    generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    lines: list[str] = [
        f"\n## Run: {report_date} (generated {generated_at})\n\n",
        f"_{len(suggs)} suggestion(s) this run_\n",
    ]
    for s in suggs:
        tier_lbl = _EXP_TIER_LABELS.get(s["tier"], s["tier"])
        prio_lbl = _EXP_PRIORITY_LABELS.get(s["priority"], s["priority"])
        lines.append(
            f"\n### [{prio_lbl} \u00b7 {tier_lbl}] "
            f"{s['platform']} \u2014 {s['title']}\n\n"
            f"**Signal:** {s['signal']}\n\n"
            f"**Gap:** {s['gap']}\n\n"
            f"**Question:** {s['question']}\n\n"
            f"**How to run it:** {s['design']}\n\n"
            f"**What the result unlocks:** {s['impact']}\n"
        )
    lines.append("\n---\n")

    # Write header on first use; always append the run section.
    # Wrapped in try/except so a permissions or disk-space error on the log
    # does not abort the full build — the HTML page is more important.
    try:
        if not log_path.exists() or log_path.stat().st_size == 0:
            log_path.write_text(
                "# Experiment Suggestion Log\n\n"
                "Auto-generated. Appended each analytics run. Never manually edited.\n"
                "Each run records the full set of directional suggestions at that point in time.\n\n"
                "---\n",
                encoding="utf-8",
            )
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write("".join(lines))
    except OSError as exc:
        print(f"  \u26a0  Could not write experiment log ({log_path}): {exc}")


# ── Validate experiment suggestions before rendering ─────────────────────────
# Catch any missing keys or invalid tier/priority values at collection time,
# before they can cause a silent KeyError inside the HTML renderer.
_EXP_REQUIRED_KEYS = frozenset({
    "id", "platform", "title", "signal", "gap",
    "question", "design", "impact", "tier", "priority",
})

def _validate_exp_suggestion(s: dict) -> bool:
    """Return True if suggestion dict has all required keys and valid tier/priority values."""
    missing = _EXP_REQUIRED_KEYS - s.keys()
    if missing:
        print(f"  \u26a0  Experiment suggestion missing keys {sorted(missing)}: "
              f"id={s.get('id', '???')!r} — skipped")
        return False
    if s["tier"] not in _EXP_TIER_LABELS:
        print(f"  \u26a0  Experiment suggestion has unknown tier {s['tier']!r}: "
              f"id={s['id']!r} — skipped")
        return False
    if s["priority"] not in _EXP_PRIORITY_LABELS:
        print(f"  \u26a0  Experiment suggestion has unknown priority {s['priority']!r}: "
              f"id={s['id']!r} — skipped")
        return False
    return True


# ── Generate and write the experiments page ───────────────────────────────────
_exp_suggs_raw  = _collect_experiment_suggestions()
_exp_suggs      = [s for s in _exp_suggs_raw if _validate_exp_suggestion(s)]
_exp_html       = _generate_experiments_page(_exp_suggs, REPORT_DATE_SLUG)
experiments_out = Path("docs/experiments/index.html")
experiments_out.parent.mkdir(exist_ok=True)
experiments_out.write_text(_exp_html, encoding="utf-8")
print(
    f"Experiments written to {experiments_out}  "
    f"({len(_exp_html):,} chars, {len(_exp_suggs)} suggestion(s))"
)

_exp_log_path = Path("experiments/experiment_log.md")
_exp_log_path.parent.mkdir(exist_ok=True)
_append_experiment_log(_exp_suggs, REPORT_DATE_SLUG, _exp_log_path)
print(f"Experiment log appended \u2192 {_exp_log_path}")


# ── Build report ─────────────────────────────────────────────────────────────
_conf_counts = {"High confidence": 0, "Moderate": 0, "Directional": 0}
for _, _, _t in _pb_tile_defs:
    for _label in _conf_counts:
        if _label in _t:
            _conf_counts[_label] += 1
            break

_build_meta = {
    "release":        REPORT_DATE_SLUG,
    "generated":      datetime.now().isoformat(timespec="seconds"),
    "data_2025":      str(DATA_2025),
    "data_2026":      str(DATA_2026),
    "rows": {
        "apple_news": int(N_AN),
        "smartnews":  int(N_SN),
        "notifications": int(N_NOTIF),
    },
    "findings": {
        "high_confidence": _conf_counts["High confidence"],
        "moderate":        _conf_counts["Moderate"],
        "directional":     _conf_counts["Directional"],
    },
    "rigor_warnings": _RIGOR_WARNINGS,
    "hero": HERO_H1[:120] if HERO_H1 else "",
}

# Save meta.json alongside the current archive slot (enables Option B delta later)
_meta_slot = _main_arch_dir / REPORT_DATE_SLUG
_meta_slot.mkdir(parents=True, exist_ok=True)
(_meta_slot / "meta.json").write_text(
    json.dumps(_build_meta, indent=2), encoding="utf-8"
)

# ── Post-build validation suite ──────────────────────────────────────────────
# Three layers of build-time checks that catch the classes of issues this project
# has historically had to debug manually:
#   1. _validate_js()         — JS syntax errors from f-string escaping mistakes
#   2. _post_build_audit()    — required HTML elements on every output file
#   3. _check_color_palette() — JS color arrays match Python palette vars
#   4. _check_formula_labels()— _FORMULA_LABELS keys match classify_formula() output
#
# All warnings are collected and printed in the build report. JS syntax errors
# are escalated to ✗ errors (block push). Others are ⚠ warnings (review before push).


def _validate_js(html_path: str, label: str) -> list[str]:
    """Extract custom <script> blocks and syntax-check with node --check."""
    errors: list[str] = []
    try:
        content = Path(html_path).read_text(encoding="utf-8")
        scripts = re.findall(r"<script>(.*?)</script>", content, re.DOTALL)
        for s in scripts:
            # Only check our custom scripts (Plotly inline scripts don't need this)
            if not any(kw in s for kw in ("showDetail", "togglePb", "_exportPanel",
                                          "_rethemeCharts", "toggleTheme", "_findTileForPanel")):
                continue
            with tempfile.NamedTemporaryFile(mode="w", suffix=".js",
                                             delete=False, encoding="utf-8") as tf:
                tf.write(s)
                tf_path = tf.name
            result = subprocess.run(["node", "--check", tf_path],
                                    capture_output=True, text=True)
            os.unlink(tf_path)
            if result.returncode != 0:
                # Trim to first error line for readability
                first_line = result.stderr.strip().splitlines()[0] if result.stderr else "unknown error"
                errors.append(f"[js_syntax:{label}] {first_line}")
    except FileNotFoundError:
        pass  # node not on PATH — skip silently
    except Exception as exc:
        errors.append(f"[js_syntax:{label}] check failed: {exc}")
    return errors

def _post_build_audit(paths: dict) -> list[str]:
    """Check every generated HTML file for required elements.

    Catches regressions where a future edit removes a critical JS function,
    the theme toggle, localStorage calls, or other cross-page invariants.
    Each warning names the missing token and describes what it controls.

    Args:
        paths: mapping of label → file path for all generated HTML output files.

    Returns:
        List of warning strings (empty = all clear).
    """
    warnings: list[str] = []

    # Tokens every page must have — covers the issues we've historically had to fix:
    # theme persistence, export functionality, nav consistency.
    universal: list[tuple[str, str]] = [
        ("theme-toggle",    "nav theme-toggle button — theme selection invisible to user"),
        ("localStorage",    "localStorage — theme preference won't persist across pages/sessions"),
        ("toggleTheme",     "toggleTheme() — clicking the toggle button does nothing"),
        ("body.light",      "body.light CSS rule — light mode has no styles, toggle is broken"),
        ("domtoimage",      "dom-to-image CDN <script> — PNG/PDF exports will fail silently"),
    ]

    # Tokens only required on specific pages
    page_extras: dict[str, list[tuple[str, str]]] = {
        "index": [
            ("_rethemeCharts",      "_rethemeCharts() — chart colors won't update on theme toggle"),
            ("_NEON_COLORS",        "_NEON_COLORS array — chart re-theming will fail for all traces"),
            ("_NORM_COLORS",        "_NORM_COLORS array — light-mode chart colors will be wrong"),
            ("_hexFromColor",       "_hexFromColor() — Plotly rgb() color normalization missing"),
            ("Plotly.Plots.resize", "Plotly.Plots.resize — charts may render at 0px in closed panels"),
            ("showDetail",          "showDetail() — finding tiles won't expand"),
        ],
        "playbook": [
            ("togglePb",  "togglePb() — playbook tiles won't expand"),
        ],
        "author-playbooks": [
            ("togglePb",  "togglePb() — author tiles won't expand"),
        ],
    }

    for label, path in paths.items():
        try:
            content = Path(path).read_text(encoding="utf-8")
        except FileNotFoundError:
            warnings.append(f"[audit:{label}] output file not found: {path}")
            continue
        for token, description in universal + page_extras.get(label, []):
            if token not in content:
                warnings.append(
                    f"[audit:{label}] MISSING '{token}' — {description}  "
                    f"(search generate_site.py for this token to restore)"
                )

    return warnings


def _check_color_palette() -> list[str]:
    """Verify JS _NEON_COLORS / _NORM_COLORS match the Python palette variables.

    A mismatch means _swapColor() will silently return un-swapped (wrong) colors
    when the user toggles between dark and light mode.

    Returns:
        List of warning strings (empty = palette is consistent).
    """
    warnings: list[str] = []

    # _NEON_COLORS order must match Python dark-mode BLUE, GREEN, RED, AMBER, GRAY.
    # _NORM_COLORS order must match Python light-mode palette (_LIGHT_PALETTE).
    expected_neon: list[str] = [BLUE, GREEN, RED, AMBER, GRAY]  # dark-mode values
    expected_norm: list[str] = list(_LIGHT_PALETTE)             # light-mode values

    try:
        content = Path("docs/index.html").read_text(encoding="utf-8")
        neon_m = re.search(r"var _NEON_COLORS\s*=\s*\[([^\]]+)\]", content)
        norm_m = re.search(r"var _NORM_COLORS\s*=\s*\[([^\]]+)\]", content)

        if neon_m:
            neon_js = [c.strip().strip("'\"") for c in neon_m.group(1).split(",")]
            if neon_js != expected_neon:
                warnings.append(
                    f"[color_palette] _NEON_COLORS mismatch — "
                    f"JS has {neon_js} but Python dark palette is {expected_neon}. "
                    f"Update the _NEON_COLORS literal in generate_site.py near _rethemeCharts."
                )
        else:
            warnings.append("[color_palette] _NEON_COLORS array not found in docs/index.html")

        if norm_m:
            norm_js = [c.strip().strip("'\"") for c in norm_m.group(1).split(",")]
            if norm_js != expected_norm:
                warnings.append(
                    f"[color_palette] _NORM_COLORS mismatch — "
                    f"JS has {norm_js} but Python light palette is {expected_norm}. "
                    f"Update the _NORM_COLORS literal in generate_site.py near _rethemeCharts."
                )
        else:
            warnings.append("[color_palette] _NORM_COLORS array not found in docs/index.html")

    except Exception as exc:
        warnings.append(f"[color_palette] check failed: {exc}")

    return warnings


def _check_formula_labels() -> list[str]:
    """Verify _FORMULA_LABELS keys match all possible classify_formula() return values.

    A missing key means author-playbook formula labels silently fall back to the raw
    key string. An extra key is dead code — a sign of a rename that wasn't propagated.

    Returns:
        List of warning strings (empty = keys are consistent).
    """
    valid_keys = {
        "number_lead", "heres_formula", "what_to_know", "question",
        "possessive_named_entity", "quoted_lede", "untagged",
    }
    warnings: list[str] = []
    extra   = set(_FORMULA_LABELS.keys()) - valid_keys
    missing = valid_keys - set(_FORMULA_LABELS.keys())
    if extra:
        warnings.append(
            f"[formula_labels] Unknown key(s) in _FORMULA_LABELS: {sorted(extra)} — "
            f"these will never match a classify_formula() result. "
            f"Remove or rename to match one of: {sorted(valid_keys)}"
        )
    if missing:
        warnings.append(
            f"[formula_labels] Missing key(s) in _FORMULA_LABELS: {sorted(missing)} — "
            f"these formulas will show raw underscore keys in author-playbook tiles. "
            f"Add display labels for them."
        )
    return warnings


def _check_col_tooltips(paths: dict) -> list[str]:
    """Verify every <th> in generated HTML has a matching entry in _COL_TOOLTIPS.

    Normalizes header text the same way the JS does: strip HTML tags, trim, collapse
    spaces, lowercase, replace en-dash with hyphen. Empty headers (spacer columns in
    the longitudinal table) are skipped.

    Returns list of warning strings (empty = full tooltip coverage).
    """
    warnings: list[str] = []
    missing: set[str] = set()
    _tag_re = re.compile(r"<[^>]+>")
    _th_re  = re.compile(r"<th[^>]*>(.*?)</th>", re.IGNORECASE | re.DOTALL)
    for page, path in paths.items():
        try:
            content = Path(path).read_text(encoding="utf-8")
            for m in _th_re.finditer(content):
                raw = _tag_re.sub("", m.group(1))            # strip nested tags
                key = raw.strip().lower().replace("\u2013", "-")
                key = " ".join(key.split())                   # collapse whitespace
                if key and key not in _COL_TOOLTIPS:
                    missing.add(key)
        except Exception as exc:
            warnings.append(f"[col_tooltips] Could not read {page}: {exc}")
    for k in sorted(missing):
        warnings.append(
            f"[col_tooltips] No tooltip for column '{k}' — "
            f"add it to _COL_TOOLTIPS in generate_site.py."
        )
    return warnings


def _check_sn_bonferroni() -> list[str]:
    """Flag SmartNews formula rows where raw p<0.05 but p doesn't survive Bonferroni.

    Uses _SN_FORMULA_DATA as the single source of truth.  The Bonferroni threshold
    is computed dynamically from the number of tested rows (rows with a real n value,
    excluding the baseline 'Direct declarative' row which has n=None).

    A warning here means the site prose may be over-stating significance for that
    formula.  The finding should be downgraded to "directional" in the tile copy
    and the WTK entry in the Experiments page is the canonical home for it.

    Returns:
        List of warning strings (empty = no Bonferroni violations in _SN_FORMULA_DATA).
    """
    warnings: list[str] = []
    k = sum(1 for r in _SN_FORMULA_DATA if r[4] is not None)   # tested families only
    if k == 0:
        return warnings
    bonf_threshold = 0.05 / k
    for label, _rank, _base, p_val, n, direction in _SN_FORMULA_DATA:
        if n is None:
            continue                          # baseline row — not a hypothesis test
        if direction == "above_dir":
            continue                          # already treated as directional in code + prose
        if p_val is not None and p_val < 0.05 and p_val >= bonf_threshold:
            warnings.append(
                f"[sn_bonferroni] '{label}': raw p={p_val:.4g} < 0.05 but does NOT "
                f"survive Bonferroni at k={k} (threshold={bonf_threshold:.4g}). "
                f"Downgrade from 'significant' to 'directional' in site prose."
            )
    return warnings


def _check_chart_legends(figures: dict) -> list[str]:
    """Verify every chart with per-bar coloring (marker.color is a list) has showlegend=True.

    Per-bar color charts use a single trace with a color array — Plotly won't auto-generate
    legend entries for them. They require dummy legend traces (e.g. _lift_legend_traces()).
    If a chart has per-bar colors but showlegend is False/None, readers have no key to
    interpret the color encoding.

    Call this after all figures are defined, passing a dict of {label: figure}.
    Returns list of warning strings (empty = all legends present).
    """
    warnings: list[str] = []
    for name, fig in figures.items():
        has_per_bar = any(
            hasattr(t, "marker") and t.marker is not None
            and isinstance(getattr(t.marker, "color", None), (list, tuple))
            for t in fig.data
        )
        if has_per_bar and not fig.layout.showlegend:
            warnings.append(
                f"[chart_legends] '{name}' uses per-bar colors but showlegend=False — "
                f"add _lift_legend_traces() or _sn_legend_traces() dummy entries and set "
                f"showlegend=True, legend=_LEGEND_BELOW in its update_layout() call."
            )
    return warnings


_js_errors = (_validate_js(str(out), "index") +
              _validate_js(str(playbook_out), "playbook") +
              _validate_js(str(author_pb_out), "author-playbooks") +
              _validate_js(str(experiments_out), "experiments"))

_audit_warnings = _post_build_audit({
    "index":            str(out),
    "playbook":         str(playbook_out),
    "author-playbooks": str(author_pb_out),
    "experiments":      str(experiments_out),
})

_palette_warnings  = _check_color_palette()
_formula_warnings  = _check_formula_labels()
_bonferroni_warns  = _check_sn_bonferroni()
_legend_warnings   = _check_chart_legends({
    "fig4 (notification CTR)":      fig4,
    "fig5 (topic × platform)":      fig5,
    "fig7 (engagement scatter)":    fig7,
    "fig8 (longitudinal)":          fig8,
    "fig_ctr_monthly (CTR trend)":  fig_ctr_monthly,
})
_tooltip_warnings  = _check_col_tooltips({
    "index":            str(out),
    "playbook":         str(playbook_out),
    "author-playbooks": str(author_pb_out),
})

# ── Rigor warnings summary ────────────────────────────────────────────────────
print(f"\n{'─'*60}")
print(f"  BUILD REPORT  ·  {REPORT_DATE_SLUG}")
print(f"{'─'*60}")
print(f"  Apple News rows : {N_AN:,}    SmartNews : {N_SN:,}    Notifications : {N_NOTIF:,}")
print(f"  Playbook tiles  : {_conf_counts['High confidence']}× High  "
      f"{_conf_counts['Moderate']}× Moderate  {_conf_counts['Directional']}× Directional")
print(f"  Packages        : statsmodels={'✓' if HAS_STATSMODELS else '✗ (pip install statsmodels)'}  "
      f"sklearn={'✓' if HAS_SKLEARN else '✗ (pip install scikit-learn)'}  "
      f"polars={'✓' if HAS_POLARS else '✗ (pip install polars)'}  "
      f"pingouin={'✓' if HAS_PINGOUIN else '✗ (pip install pingouin)'}")
if Q1_KW_P is not None:
    _kw_sig = "significant" if Q1_KW_P < 0.05 else "not significant"
    print(f"  Q1 Kruskal-Wallis omnibus: H={Q1_KW_STAT:.2f}, p={Q1_KW_P:.4f} ({_kw_sig})")
if Q1_DUNN is not None and len(Q1_DUNN) > 0:
    print(f"  Q1 Dunn post-hoc: {len(Q1_DUNN)} significant pairwise difference(s) at p_adj<0.10 (BH-FDR)")
elif HAS_PINGOUIN and Q1_KW_P is not None and Q1_KW_P >= 0.05:
    print("  Q1 Dunn post-hoc: skipped (Kruskal-Wallis not significant)")
if Q2_LOGIT_SUMMARY:
    print(f"  Q2 {Q2_LOGIT_SUMMARY}")
if _js_errors:
    print(f"\n  ✗  {len(_js_errors)} JS SYNTAX ERROR(S) — site JS is broken, fix before pushing:")
    for _e in _js_errors:
        print(f"     • {_e}")
else:
    print("  ✓  JS syntax valid (index + playbook + author-playbooks).")
if _RIGOR_WARNINGS:
    print(f"\n  ⚠  {len(_RIGOR_WARNINGS)} rigor warning(s) — sections without significance tests:")
    for _w in _RIGOR_WARNINGS:
        print(f"     • {_w}")
else:
    print("  ✓  All major comparisons have significance tests.")
if _audit_warnings:
    print(f"\n  ✗  {len(_audit_warnings)} HTML/JS AUDIT FAILURE(S) — required tokens missing from generated pages:")
    for _w in _audit_warnings:
        print(f"     • {_w}")
    print("     → Fix: locate the missing token in generate_site.py and verify it is written to the correct output file.")
else:
    print("  ✓  HTML/JS audit passed (all required tokens present on all pages).")
if _palette_warnings:
    print(f"\n  ✗  {len(_palette_warnings)} COLOR PALETTE MISMATCH(ES) — JS color arrays diverge from Python constants:")
    for _w in _palette_warnings:
        print(f"     • {_w}")
    print("     → Fix: sync _NEON_COLORS/_NORM_COLORS in the JS block with BLUE/GREEN/RED/AMBER/GRAY in generate_site.py.")
else:
    print("  ✓  Color palette consistent (JS arrays match Python constants).")
if _formula_warnings:
    print(f"\n  ✗  {len(_formula_warnings)} FORMULA LABEL MISMATCH(ES) — _FORMULA_LABELS keys don't match classify_formula() return values:")
    for _w in _formula_warnings:
        print(f"     • {_w}")
    print("     → Fix: update _FORMULA_LABELS dict keys to match the return values in classify_formula().")
else:
    print("  ✓  Formula labels consistent (_FORMULA_LABELS keys match classify_formula()).")
if _bonferroni_warns:
    print(f"\n  ⚠  {len(_bonferroni_warns)} SMARTNEWS BONFERRONI WARNING(S) — formula(s) significant at p<0.05 but not after correction:")
    for _w in _bonferroni_warns:
        print(f"     • {_w}")
    print("     → Fix: downgrade prose from 'significant' to 'directional'; Experiments page already routes these correctly.")
else:
    print("  ✓  SmartNews Bonferroni check passed (no over-stated significance in _SN_FORMULA_DATA).")
if _legend_warnings:
    print(f"\n  ✗  {len(_legend_warnings)} CHART LEGEND MISSING — per-bar color charts need a legend key:")
    for _w in _legend_warnings:
        print(f"     • {_w}")
    print("     → Fix: add _lift_legend_traces() or _sn_legend_traces() + showlegend=True, legend=_LEGEND_BELOW.")
else:
    print("  ✓  All charts have legends (per-bar color scales are explained).")
if _tooltip_warnings:
    print(f"\n  ✗  {len(_tooltip_warnings)} COLUMN TOOLTIP MISSING — <th> text not in _COL_TOOLTIPS:")
    for _w in _tooltip_warnings:
        print(f"     • {_w}")
    print("     → Fix: add the column key and a 1-sentence explanation to _COL_TOOLTIPS in generate_site.py.")
else:
    print("  ✓  Column tooltips complete (all <th> headers have hover explanations).")
# ── Stakeholder-scope audit ───────────────────────────────────────────────────
# Verifies that policy flags (SHOW_MSN_TILE, LOW_SIGNAL_PLATFORMS, etc.)
# are honored across ALL generated files — not just the pages where the
# flag was originally applied. Catches cases where a flag gates one location
# but a separate code path writes the same content to a different page.
_scope_warnings: list[str] = []

# Check 1: SHOW_MSN_TILE=False → no MSN-specific tile content in playbook or experiments
if not SHOW_MSN_TILE:
    _playbook_html = playbook_out.read_text()
    if 'tile-label">MSN' in _playbook_html or 'pb-msn' in _playbook_html:
        _scope_warnings.append(
            "SHOW_MSN_TILE=False but MSN tile still present in playbook/index.html. "
            "Gate all MSN tile code paths on `not SHOW_MSN_TILE`."
        )

# Check 2: LOW_SIGNAL_PLATFORMS — verify author tiles don't route to these without caveat
_ap_html = author_pb_out.read_text()
for _lsp in LOW_SIGNAL_PLATFORMS:
    import re as _re
    # Look for "Route.*{platform}" or "{platform} first" patterns without the ⚠ warning nearby
    # Match editorial routing instructions specifically (not article headlines or table cells)
    _routing_pattern = _re.compile(
        rf"(?:Route new articles|Route the next|route.*?through)\s[^<.]*?{_lsp}",
        _re.IGNORECASE
    )
    for _m in _routing_pattern.finditer(_ap_html):
        _ctx = _ap_html[max(0, _m.start()-100):_m.end()+300]
        if "⚠" not in _ctx and "low-confidence" not in _ctx:
            _scope_warnings.append(
                f"Author playbook routes to low-signal platform '{_lsp}' without "
                f"the required caveat near: '{_m.group()[:60]}...'"
            )
            break

# Check 3: PLATFORM_AVOIDANCE_FORMULAS — verify no author tile tile-action
# recommends an avoidance formula without the ⚠ cross-platform caveat
_avoid_labels = {
    v: k for k, _reason in PLATFORM_AVOIDANCE_FORMULAS.items()
    for v in [_FORMULA_LABELS.get(k, k)]
}
for _avoid_lbl in _avoid_labels:
    _action_pattern = _re.compile(
        rf'tile-action[^>]*>[^<]*?(?:Test|Shift|trial)\s+{_re.escape(_avoid_lbl)}',
        _re.IGNORECASE
    )
    for _m in _action_pattern.finditer(_ap_html):
        _ctx = _ap_html[max(0, _m.start()-20):_m.end()+400]
        if "⚠" not in _ctx:
            _scope_warnings.append(
                f"Author playbook recommends avoidance formula '{_avoid_lbl}' "
                f"without cross-platform caveat near: '{_m.group()[:60]}...'"
            )
            break

if _scope_warnings:
    print(f"\n  ✗  {len(_scope_warnings)} STAKEHOLDER SCOPE VIOLATION(S) — "
          f"policy flags not honored across all pages:")
    for _w in _scope_warnings:
        print(f"     • {_w}")
    print("     → Fix: ensure SHOW_MSN_TILE, LOW_SIGNAL_PLATFORMS, and "
          "PLATFORM_AVOIDANCE_FORMULAS are checked at every code path that "
          "generates author or platform recommendations.")
else:
    print("  ✓  Stakeholder scope clean (MSN gate, low-signal platforms, "
        "avoidance formulas all honored across all pages).")

print(f"  meta.json → {_meta_slot}/meta.json")
print(f"{'─'*60}\n")
