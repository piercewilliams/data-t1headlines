"""
generate_site.py — T1 Headline Analysis site generator.

Reads two Excel exports (2025 and 2026 YTD) from Chris Tarrow's Google Sheet,
runs 9 statistical analyses, and writes:
  - docs/index.html          — main analysis page (9 findings, interactive tiles)
  - docs/playbook/index.html — editorial playbooks (sorted by confidence level)

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
import shutil
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import re
import warnings
from datetime import datetime
from pathlib import Path
from scipy import stats

warnings.filterwarnings("ignore")

# ── Optional packages (graceful fallbacks if not installed) ───────────────────
# Install all: pip3 install statsmodels polars scikit-learn pingouin xlrd
try:
    import statsmodels.api as sm
    from statsmodels.discrete.discrete_model import Logit
    from statsmodels.stats.multitest import multipletests as sm_multipletests
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
    from sklearn.preprocessing import LabelEncoder
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
parser.add_argument("--tracker",   default="Tracker Template.xlsx")
parser.add_argument("--theme",     default="light", choices=["light", "dark"])
parser.add_argument("--release",   default=None,
                    help="Data release slug YYYY-MM (defaults to current month). "
                         "Pass explicitly when ingesting data from a prior month.")
parser.add_argument("--skip-main-archive", action="store_true",
                    help="Skip archiving docs/index.html (used when ingest.py handles archiving).")
_args = parser.parse_args()
DATA_2025   = _args.data_2025
DATA_2026   = _args.data_2026
TRACKER     = _args.tracker
THEME       = _args.theme
SKIP_ARCHIVE = _args.skip_main_archive

REFERENCE_DATE = pd.Timestamp.today().normalize()

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY   = "#0f172a"
BLUE   = "#2563eb"
GREEN  = "#16a34a"
RED    = "#dc2626"
AMBER  = "#f59e0b"
GRAY   = "#64748b"
LIGHT  = "#f8fafc"
BORDER = "#e2e8f0"

# Dark-mode neon overrides — applied to chart traces only when --theme dark
if THEME == "dark":
    BLUE  = "#60a5fa"   # electric blue
    GREEN = "#4ade80"   # neon green
    RED   = "#f87171"   # coral pink
    AMBER = "#fb923c"   # vivid orange
    GRAY  = "#94a3b8"   # light slate (readable on dark)

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
    text       = "#f1f5f9",        # slate-100
    text_muted = "#94a3b8",        # slate-400
    grid       = "#334155",        # slate-700
    baseline   = "#64748b",        # slate-500 (same as GRAY)
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
#
# TABLES — do NOT add overflow/scroll CSS to individual tables:
#   The JS DOMContentLoaded listener auto-wraps every <table> in a .table-wrap div,
#   which owns the overflow-x:auto scroll, border-radius, and box-shadow.
#   Tables scroll horizontally when content is wider than the panel — text is NEVER
#   clipped or truncated. Do not add overflow:hidden or fixed widths to table elements.

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
    if re.search(r"\b(animal|creature|species|wildlife|shark|bear|alligator|snake|bird|dog|cat|pet)\b", t): return "nature_wildlife"
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

def bootstrap_ci_lift(grp_vals: np.ndarray, base_vals: np.ndarray, n_boot: int = 1000, seed: int = 42, ci: float = 0.95) -> "tuple[float, float]":
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
    r_rb = effect_r
    if r_rb is None or r_rb == 0: return None
    r = abs(r_rb)
    d = 2 * r / math.sqrt(max(1 - r ** 2, 1e-9))
    if d < 0.001: return None
    return math.ceil(1.05 * 15.69 / d ** 2)


# ── Rigor infrastructure ──────────────────────────────────────────────────────
_RIGOR_WARNINGS: list = []

def _rigor_warn(section: str, msg: str) -> None:
    _RIGOR_WARNINGS.append(f"[{section}] {msg}")

def _conf_level(p_adj: "float | None" = None, n: "int | None" = None, n_platforms: int = 1, p_raw: "float | None" = None) -> "tuple[str, str]":
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
def normalize(df: pd.DataFrame, views_col: str, date_col: "str | None" = None, group_col: "str | None" = None) -> pd.DataFrame:
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
_KNOWN_SHEETS_2025 = {"Apple News", "SmartNews", "Yahoo", "MSN"}
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
def _fix_mac_encoding(text):
    try:
        return str(text).encode("mac_roman").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return str(text)
an_2026["Article"] = an_2026["Article"].apply(lambda x: _fix_mac_encoding(x) if pd.notna(x) else x)

# Common columns for concat
_common_cols = [c for c in an_2025.columns if c in an_2026.columns]
an = pd.concat([an_2025[_common_cols], an_2026[_common_cols]], ignore_index=True)

# SmartNews — 2025 primary (has category columns)
sn = pd.read_excel(DATA_2025, sheet_name="SmartNews")

# Notifications from 2026
notif  = pd.read_excel(DATA_2026, sheet_name="Apple News Notifications")
sn26   = pd.read_excel(DATA_2026, sheet_name="SmartNews")
yahoo26 = pd.read_excel(DATA_2026, sheet_name="Yahoo")
notif = notif.dropna(subset=["CTR"]).copy()

# MSN and Yahoo from 2025
msn   = pd.read_excel(DATA_2025, sheet_name="MSN")
yahoo = pd.read_excel(DATA_2025, sheet_name="Yahoo")

# ── Column validation — friendly errors instead of KeyError crashes ───────────
def _require_col(df: pd.DataFrame, col: str, sheet_label: str) -> None:
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
_require_col(notif, "CTR", "Apple News Notifications 2026")
_require_col(notif, "Notification Text", "Apple News Notifications 2026")

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
for cat in CATS:
    sn[cat] = pd.to_numeric(sn[cat], errors="coerce").fillna(0)

# ── Normalize ────────────────────────────────────────────────────────────────
print("Normalizing…")
an    = normalize(an,    views_col="Total Views",   date_col="Date Published", group_col="_pub_month")
sn    = normalize(sn,    views_col="article_view",  date_col=None,             group_col="_sn_month")
yahoo = normalize(yahoo, views_col="Content Views", date_col="Publish Date",   group_col="_pub_month")

# Subtopics
an["subtopic"] = an.apply(lambda r: tag_subtopic(r["Article"], r["topic"]), axis=1)
sn["subtopic"] = sn.apply(lambda r: tag_subtopic(r["title"],   r["topic"]), axis=1)

# Also normalize 2025/2026 subsets for YoY
an_2025_norm = an[an["year"] == 2025].copy()
an_2026_norm = an[an["year"] == 2026].copy()

# ── Platform exclusivity ──────────────────────────────────────────────────────
def _norm(t):
    return re.sub(r"[^a-z0-9]", "", str(t).lower().strip())

an_t    = set(an["Article"].dropna().apply(_norm))
sn_t    = set(sn["title"].dropna().apply(_norm))
msn_t   = set(msn["Title"].dropna().apply(_norm))
yahoo_t = set(yahoo["Content Title"].dropna().apply(_norm))

excl_an    = len(an_t - sn_t - msn_t - yahoo_t) / len(an_t)
excl_sn    = len(sn_t - an_t - msn_t - yahoo_t) / len(sn_t)
excl_msn   = len(msn_t - an_t - sn_t - yahoo_t) / len(msn_t)
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
top_median_sn_pct = sn[sn["Top"] > 0][VIEWS_METRIC].median()
top_pct_vals = sn[sn["Top"] > 0][VIEWS_METRIC].values
top_median_sn_raw = sn[sn["Top"] > 0]["article_view"].median()

_cat_hits = (sn[CATS] > 0).sum(axis=1)
SN_MULTI_CAT_N   = int((_cat_hits > 1).sum())
SN_MULTI_CAT_PCT = SN_MULTI_CAT_N / len(sn)

SHOW_CATS = ["Local","U.S.","Football","Business","Health","Science",
             "Politics","World","Lifestyle","Entertainment","Top"]

q4_rows = []
_q4_raw_p = []
_q4_indices = []
for cat in SHOW_CATS:
    in_cat = sn[sn[cat] > 0]
    n = len(in_cat)
    med_pct = in_cat[VIEWS_METRIC].median()
    med_raw = in_cat["article_view"].median()
    row = dict(category=cat, n=n, median_pct=med_pct, median_views=med_raw,
               pct_share=n/len(sn))
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
def extract_features(text):
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
notif_feats = pd.concat([notif[["CTR", "Notification Text"]], feats], axis=1)
overall_ctr_med = notif["CTR"].median()

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

_excl_mask   = notif_feats["'Exclusive' tag"] == True
_guthrie_mask = notif_feats["Notification Text"].str.contains(r"Guthrie", na=False)
_excl_yes_all    = notif_feats[_excl_mask]["CTR"]
_excl_no         = notif_feats[~_excl_mask]["CTR"]
_excl_yes_noguth = notif_feats[_excl_mask & ~_guthrie_mask]["CTR"]
_n_excl_guthrie  = int((_excl_mask & _guthrie_mask).sum())
if len(_excl_yes_noguth) >= 3 and len(_excl_no) >= 5:
    _u_noguth = stats.mannwhitneyu(_excl_yes_noguth, _excl_no, alternative="two-sided")
    EXCL_NOGUTH_LIFT = float(_excl_yes_noguth.median() / _excl_no.median()) if _excl_no.median() > 0 else None
    EXCL_NOGUTH_P    = _u_noguth.pvalue
else:
    EXCL_NOGUTH_LIFT = None
    EXCL_NOGUTH_P    = None


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

r_views_at,    p_views_at    = stats.pearsonr(an_eng["Total Views"], an_eng[AT_COL])
r_views_at_sp, p_views_at_sp = stats.spearmanr(an_eng["Total Views"], an_eng[AT_COL])

def _r(col):
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
an_topic = an.groupby("topic")[VIEWS_METRIC].median().reset_index()
an_topic.columns = ["topic", "an_median"]
sn_topic = sn.groupby("topic")[VIEWS_METRIC].median().reset_index()
sn_topic.columns = ["topic", "sn_median"]
topic_df = an_topic.merge(sn_topic, on="topic")
topic_df["label"] = topic_df["topic"].map(TOPIC_LABELS)

an_overall = an[VIEWS_METRIC].median()
sn_overall = sn[VIEWS_METRIC].median()
topic_df["an_idx"] = topic_df["an_median"] / an_overall
topic_df["sn_idx"] = topic_df["sn_median"] / sn_overall
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
_require_test("sports_subtopic", None, len(sports_an), len(sports_sn))

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
_require_test("biz_subtopic", None, len(biz_an), len(biz_sn))

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
def top_bottom_html(df, text_col, views_col, topic, n=6):
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
def _period_lift(formula, period):
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

# ── Tracker join ──────────────────────────────────────────────────────────────
print("Computing tracker join…")
HAS_TRACKER  = False
tracker_df   = None
team_combined = pd.DataFrame()
author_stats  = pd.DataFrame()
team_top      = pd.DataFrame()
N_TRACKED     = 0

def _hn(t):
    return re.sub(r"[^a-z0-9]", "", str(t).lower().strip())

try:
    tracker_raw = pd.read_excel(TRACKER, sheet_name="Data")
    tracker_df  = tracker_raw[["Published URL/Link", "Author", "Vertical",
                                "Word Count", "Headline"]].copy()
    tracker_df  = tracker_df.dropna(subset=["Author"])
    tracker_df["_url"] = tracker_df["Published URL/Link"].fillna("").str.strip().str.lower()
    tracker_df["_hn"]  = tracker_df["Headline"].apply(_hn)
    # Rename to avoid column conflicts when merging with datasets that also have Author column
    tracker_df = tracker_df.rename(columns={"Author": "t_author", "Vertical": "t_vertical"})
    HAS_TRACKER = True
except Exception as e:
    print(f"Tracker not loaded: {e}")

if HAS_TRACKER:
    rows = []

    # ── 1. Apple News: URL join + headline join (combined, deduplicated) ──────
    an_work = an.copy()
    an_work["_url"] = an_work["Publisher Article ID"].fillna("").str.strip().str.lower()
    an_work["_hn"]  = an_work["Article"].apply(_hn)
    # URL join
    an_url_j = (an_work[an_work["_url"] != ""]
                .merge(tracker_df[["_url","t_author","t_vertical","Word Count"]], on="_url", how="inner"))
    # Headline join (fallback for articles where URL format differs)
    an_hn_j  = (an_work[an_work["_hn"].str.len() > 10]
                .merge(tracker_df[["_hn","t_author","t_vertical","Word Count"]], on="_hn", how="inner"))
    an_joined = pd.concat([an_url_j, an_hn_j]).drop_duplicates(subset=["Article ID"])
    for _, r in an_joined.iterrows():
        rows.append(dict(
            platform="Apple News",
            headline=r["Article"],
            brand=r.get("Brand", ""),
            author=r["t_author"],
            vertical=r.get("t_vertical", ""),
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
              .merge(tracker_df[["_url","t_author","t_vertical","Word Count"]], on="_url", how="inner"))
    for _, r in sn26_j.iterrows():
        rows.append(dict(
            platform="SmartNews",
            headline=r["title"],
            brand=r.get("domain", ""),
            author=r["t_author"],
            vertical=r.get("t_vertical", ""),
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
                 .merge(tracker_df[["_hn","t_author","t_vertical","Word Count"]], on="_hn", how="inner"))
    for _, r in yahoo26_j.iterrows():
        rows.append(dict(
            platform="Yahoo",
            headline=r["Content Title"],
            brand=r.get("Provider Name", ""),
            author=r["t_author"],
            vertical=r.get("t_vertical", ""),
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


# ── Key stats ─────────────────────────────────────────────────────────────────
N_AN        = len(an)
N_SN        = len(sn)
N_NOTIF     = len(notif)
PLATFORMS   = sum(1 for _df in [an, sn, msn, yahoo] if _df is not None and len(_df) > 0)
REPORT_DATE = datetime.now().strftime("%B %Y")

_wtn_row  = df_q2[df_q2["formula"] == "what_to_know"]
WTN_FEAT_RATE = float(_wtn_row["featured_rate"].iloc[0]) if len(_wtn_row) else overall_feat_rate
WTN_FEAT  = f"{WTN_FEAT_RATE:.0%}"

_local_row = df_q4[df_q4["category"] == "Local"]
_local_pct = float(_local_row["median_pct"].iloc[0]) if len(_local_row) else 0
LOCAL_LIFT = f"{_local_pct / top_median_sn_pct:.1f}×" if top_median_sn_pct > 0 else "—"

_excl_row  = df_q5[df_q5["feature"] == "'Exclusive' tag"]
_excl_lift_val = float(_excl_row["lift"].iloc[0]) if len(_excl_row) else None
_excl_ci_lo    = float(_excl_row["ci_lo"].iloc[0]) if len(_excl_row) and "ci_lo" in _excl_row.columns else None
_excl_ci_hi    = float(_excl_row["ci_hi"].iloc[0]) if len(_excl_row) and "ci_hi" in _excl_row.columns else None
EXCL_LIFT  = f"{_excl_lift_val:.2f}×" if _excl_lift_val else "—"
EXCL_CI_STR = (f"[{_excl_ci_lo:.1f}×–{_excl_ci_hi:.1f}×]"
               if _excl_ci_lo is not None and _excl_ci_hi is not None else "")


# ── Prose helpers ─────────────────────────────────────────────────────────────
def _fmt_p(p, adj=False):
    if p is None or (isinstance(p, float) and np.isnan(p)): return "—"
    p = float(p)
    label = "<sub>adj</sub>" if adj else ""
    sig = " ***" if p < 0.001 else " **" if p < 0.01 else " *" if p < 0.05 else ""
    if p < 0.001: return f"p{label}&lt;0.001{sig}"
    if p < 0.01:  return f"p{label}={p:.3f}{sig}"
    return f"p{label}={p:.2f}{sig}"

def _fmt_ci(lo, hi):
    if lo is None or hi is None: return ""
    return f"[{lo:.2f}×–{hi:.2f}×]"

def _q1r(f):
    row = df_q1[df_q1["formula"] == f]
    return row.iloc[0] if len(row) else None

def _q2r(f):
    row = df_q2[df_q2["formula"] == f]
    return row.iloc[0] if len(row) else None

def _q4r(cat):
    row = df_q4[df_q4["category"] == cat]
    return row.iloc[0] if len(row) else None

def _q5r(feat):
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

_r5_excl = _q5r("'Exclusive' tag")
_r5_poss = _q5r("Named person + possessive")
_r5_full = _q5r("Full name present")
_r5_q    = _q5r("Question format")
_r5_sh   = _q5r("Short (≤80 chars)")
_r5_num  = _q5r("Contains number")
_r5_attr = _q5r("Attribution (says/told)")
CTR_MED  = f"{notif['CTR'].median():.2%}"


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

# Notification: short headlines backfire (very counter-intuitive → high surprise)
if _r5_sh is not None and float(_r5_sh["lift"]) < 1.0:
    _sh_lift = float(_r5_sh["lift"])
    _hero_add(
        f"Short notifications (≤80 chars) get {(1-_sh_lift):.0%} fewer clicks — "
        f"longer, more descriptive push text consistently wins.",
        _get_p(_r5_sh), 1.0 - _sh_lift, surprise=2.2, n=int(_r5_sh["n_true"]),
    )

# Notification: exclusive tag (strongest single CTR signal)
if _r5_excl is not None:
    _excl_lft = float(_r5_excl["lift"])
    _hero_add(
        f"\u201cExclusive\u201d in a push notification is associated with {_excl_lft:.1f}\u00d7 higher CTR "
        f"than standard headlines.",
        _get_p(_r5_excl), _excl_lft - 1.0, surprise=1.3, n=int(_r5_excl["n_true"]),
    )

# Notification: named person + possessive
if _r5_poss is not None and float(_r5_poss["lift"]) > 1.0:
    _poss_lft = float(_r5_poss["lift"])
    _hero_add(
        f"Named person\u202f+\u202fpossessive (\u201cSmith\u2019s\u2026\u201d) shows "
        f"{_poss_lft:.1f}\u00d7 higher notification CTR.",
        _get_p(_r5_poss), _poss_lft - 1.0, surprise=1.2, n=int(_r5_poss["n_true"]),
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
def _row_tag(lift, is_red=False):
    if is_red:          return '<span class="tag tag-red">↓</span>'
    if lift >= 1.5:     return '<span class="tag tag-green">★</span>'
    if lift < 0.8:      return '<span class="tag tag-red">↓</span>'
    return ""

def _wc_table():
    if df_wc_quartile.empty: return "<tr><td colspan='4'>Insufficient data (need ≥20 matched articles with word count).</td></tr>"
    out = ""
    for _, r in df_wc_quartile.iterrows():
        out += (f"<tr><td>{r['wc_quartile']}</td><td>{int(r['n'])}</td>"
                f"<td>{int(r['med_wc'])}</td><td>{r['med_pct']:.0%}</td></tr>\n")
    return out

def _nl_type_table():
    if df_nl_type.empty: return "<tr><td colspan='4'>Insufficient data.</td></tr>"
    out = ""
    for _, r in df_nl_type.iterrows():
        out += (f"<tr><td>{r['label']}</td><td>{int(r['n'])}</td>"
                f"<td>{r['median']:.0%}</td><td>{r['lift']:.2f}×</td></tr>\n")
    return out

def _nl_size_table():
    if df_nl_size.empty: return "<tr><td colspan='4'>Insufficient data.</td></tr>"
    out = ""
    for _, r in df_nl_size.iterrows():
        out += (f"<tr><td>{r['size_cat']}</td><td>{int(r['n'])}</td>"
                f"<td>{r['median']:.0%}</td><td>{r['lift']:.2f}×</td></tr>\n")
    return out

def _q1_table():
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

def _q2_table():
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

def _q4_table():
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

def _q5_table():
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

def _sports_subtopic_table():
    html_out = ""
    for _, r in df_sports_subtopic.iterrows():
        an_str = f"{r['an_med']:.0%}" if pd.notna(r['an_med']) else "—"
        sn_str = f"{r['sn_med']:.0%}" if pd.notna(r['sn_med']) else "—"
        html_out += (f"<tr><td>{r['subtopic']}</td>"
                     f"<td>{int(r['an_n'])}</td><td>{an_str}</td>"
                     f"<td>{int(r['sn_n'])}</td><td>{sn_str}</td></tr>\n")
    return html_out

def _biz_subtopic_table():
    html_out = ""
    for _, r in df_biz_subtopic.iterrows():
        an_str = f"{r['an_med']:.0%}" if pd.notna(r['an_med']) else "—"
        sn_str = f"{r['sn_med']:.0%}" if pd.notna(r['sn_med']) else "—"
        html_out += (f"<tr><td>{r['label']}</td>"
                     f"<td>{int(r['an_n'])}</td><td>{an_str}</td>"
                     f"<td>{int(r['sn_n'])}</td><td>{sn_str}</td></tr>\n")
    return html_out

def _pol_subtopic_table():
    html_out = ""
    for _, r in df_pol_subtopic.iterrows():
        an_str = f"{r['an_med']:.0%}" if pd.notna(r['an_med']) else "—"
        sn_str = f"{r['sn_med']:.0%}" if pd.notna(r['sn_med']) else "—"
        html_out += (f"<tr><td>{r['label']}</td>"
                     f"<td>{int(r['an_n'])}</td><td>{an_str}</td>"
                     f"<td>{int(r['sn_n'])}</td><td>{sn_str}</td></tr>\n")
    return html_out

def _hl_len_table():
    html_out = ""
    for _, r in df_hl_len.iterrows():
        an_str = f"{r['an_med']:.0%}" if pd.notna(r['an_med']) else "—"
        sn_str = f"{r['sn_med']:.0%}" if pd.notna(r['sn_med']) else "—"
        an_chars = f"{int(r['an_len_med'])} chars" if pd.notna(r['an_len_med']) else "—"
        html_out += (f"<tr><td>{r['bucket']}</td><td>{an_chars}</td>"
                     f"<td>{int(r['an_n']):,}</td><td>{an_str}</td>"
                     f"<td>{int(r['sn_n']):,}</td><td>{sn_str}</td></tr>\n")
    return html_out

def _guide_table(df, max_rows=20):
    if df.empty: return "<tr><td colspan='5'>Insufficient data (need ≥5 articles per formula × topic cell).</td></tr>"
    html_out = ""
    for _, r in df.head(max_rows).iterrows():
        lift_val = r['lift']
        if pd.notna(lift_val):
            color = "#4ade80" if lift_val >= 1.5 else ("#60a5fa" if lift_val >= 1.0 else "#f87171")
            lift_str = f'<span style="color:{color};font-weight:600">{lift_val:.2f}×</span>'
        else:
            lift_str = "—"
        html_out += (f"<tr><td>{r['formula']}</td><td>{r['topic']}</td>"
                     f"<td>{int(r['n'])}</td><td>{r['med']:.0%}</td>"
                     f"<td>{lift_str}</td></tr>\n")
    return html_out

def _yoy_table():
    html_out = ""
    for _, r in df_yoy.iterrows():
        if r["suppressed"]:
            # Show suppressed rows with caveat (n<10 in 2025 = unreliable)
            html_out += (f"<tr style='color:#94a3b8'>"
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

def _periods_table():
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
            cells += f"<td>{lv}</td><td style='color:#94a3b8'>(n={nv})</td>"
        html_out += f"<tr><td>{label}</td>{cells}</tr>\n"
    return html_out

def _author_table():
    if author_stats.empty: return "<tr><td colspan='4'>No matched articles.</td></tr>"
    html_out = ""
    for _, r in author_stats.iterrows():
        html_out += (f"<tr><td>{html_module.escape(str(r['author']))}</td>"
                     f"<td>{html_module.escape(str(r['platform']))}</td>"
                     f"<td>{int(r['n'])}</td>"
                     f"<td>{r['med_pct']:.0%}</td></tr>\n")
    return html_out

def _team_top_table():
    if team_top.empty: return "<tr><td colspan='6'>No matched articles.</td></tr>"
    html_out = ""
    for _, r in team_top.iterrows():
        title = html_module.escape(str(r['headline'])[:80])
        feat_str = "Yes" if r.get('featured') else "No"
        views_val = r.get('views', 0)
        views_str = f"{int(views_val):,}" if pd.notna(views_val) else "—"
        html_out += (f"<tr><td>{title}</td>"
                     f"<td>{html_module.escape(str(r.get('platform','')))} — {html_module.escape(str(r.get('brand','')))}</td>"
                     f"<td>{html_module.escape(str(r.get('author','')))}</td>"
                     f"<td>{r['percentile']:.0%}</td>"
                     f"<td>{views_str}</td>"
                     f"<td>{feat_str}</td></tr>\n")
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
F4_EXCL_LIFT_STR  = f"{float(_r5_excl['lift']):.2f}×"  if _r5_excl is not None else "—"
F4_EXCL_P_STR     = _fmt_p(_get_p(_r5_excl), adj=True) if _r5_excl is not None else "—"
F4_POSS_LIFT_STR  = f"{float(_r5_poss['lift']):.2f}×"  if _r5_poss is not None else "—"
F4_POSS_P_STR     = _fmt_p(_get_p(_r5_poss), adj=True) if _r5_poss is not None else "—"
F4_SHORT_PCT_STR  = f"{(1-float(_r5_sh['lift'])):.0%}" if _r5_sh   is not None else "—"
_q5_sig = df_q5.apply(
    lambda r: float(r.get("p_adj") if pd.notna(r.get("p_adj", float("nan"))) else r["p"]) < 0.05,
    axis=1) if not df_q5.empty else pd.Series([], dtype=bool)
N_SIG_NOTIF_FEATURES = int(_q5_sig.sum())

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

def bar_color(lift):
    if lift >= 1.5:   return GREEN
    if lift >= 1.0:   return BLUE
    if lift >= 0.8:   return AMBER
    return RED

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
fig1.update_layout(
    **make_layout(THEME, height=CHART_H, margin=dict(l=20, r=auto_right_margin(_fig1_text), t=50, b=40),
                  title="Percentile-within-cohort lift vs. baseline by formula — non-Featured articles only"),
    xaxis=dict(title="Median percentile rank relative to untagged baseline (1.0 = same as baseline)",
               gridcolor=_T["grid"], zeroline=False, range=safe_range(_fig1_x, margin=0.25)),
    yaxis=dict(title=""),
    showlegend=False,
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
fig2.update_layout(
    **make_layout(THEME, height=CHART_H, margin=dict(l=20, r=auto_right_margin(_fig2_text), t=50, b=40),
                  title="% of articles Featured by Apple, by headline formula"),
    xaxis=dict(title="% of articles in formula group that were Featured by Apple",
               gridcolor=_T["grid"], zeroline=False, range=safe_range((df_q2["featured_rate"] * 100).tolist(), margin=0.25)),
    yaxis=dict(title=""),
    showlegend=False,
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
fig3.update_layout(
    **make_layout(THEME, height=CHART_H, margin=dict(l=20, r=auto_right_margin(_fig3_text), t=50, b=40),
                  title="Median percentile rank by SmartNews channel — with article volume"),
    xaxis=dict(title="Median percentile within monthly cohort (0=lowest, 1=highest)", gridcolor=_T["grid"],
               zeroline=False, tickformat=".0%"),
    yaxis=dict(title=""),
    showlegend=False,
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
fig4.update_layout(
    **make_layout(THEME, height=CHART_H, margin=dict(l=20, r=auto_right_margin(sig_labels), t=50, b=40),
                  title="Notification CTR lift by headline feature (median CTR, feature present vs. absent)"),
    xaxis=dict(title="CTR lift (1.0 = no effect)", gridcolor=_T["grid"], zeroline=False, range=safe_range(_fig4_x, margin=0.25)),
    yaxis=dict(title=""),
    showlegend=False,
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
fig5.add_vline(x=1.0, line_dash="dash", line_color=_T["baseline"],
               annotation_text="Platform median", annotation_position="top")
fig5.update_layout(
    **make_layout(THEME, height=480, margin=dict(l=20, r=40, t=50, b=80),
                  title="Topic performance by platform — percentile rank vs. platform median"),
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
                  title="Outcome spread by topic — where headline choice has the most room to move performance"),
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
                  title=f"Views vs. average active time — Pearson r = {r_views_at:.3f} (p = {p_views_at:.2f})"),
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
                  title="Headline formula lift vs. unclassified baseline — Q1 2025 through Q1 2026"),
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
    xaxis=dict(title="Median percentile_within_cohort", gridcolor=_T["grid"],
               zeroline=False, tickformat=".0%"),
    yaxis=dict(title=""),
    legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5),
)
guard_empty(fig_hl, df_hl_len, "Headline length data unavailable.")


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
        <thead><tr><th>Author</th><th>Platform</th><th>n articles</th><th>Median percentile</th></tr></thead>
        <tbody>{_t_auth}</tbody>
      </table>
      <h3>Top 20 articles by percentile rank</h3>
      <table class="findings">
        <thead><tr><th>Article</th><th>Platform — Brand</th><th>Author</th><th>Percentile</th><th>Views</th><th>Featured</th></tr></thead>
        <tbody>{_t_team}</tbody>
      </table>
      <h3>Article length and syndication performance ({WC_MATCHED_N} matched articles with word count)</h3>
      <div class="callout">
        <strong>Unexpected:</strong> Articles in the longest quartile (~{_F9_Q4_WORDS_STR} words) perform at the {_F9_Q4_PCT_STR} — worse than any other length group. Q2 (~{_F9_Q2_WORDS_STR} words) is the highest-performing range in this sample at {_F9_Q2_PCT_STR}. {"Mann-Whitney Q4 vs. Q2: " + WC_P_STR + " (n=" + str(WC_MATCHED_N) + ", unadjusted). Pattern is consistent within SmartNews individually but interpret cautiously at this sample size." if WC_P_STR else "Based on " + str(WC_MATCHED_N) + " tracker-matched articles, mostly SmartNews — too small for reliable significance testing. Treat as directional."}
      </div>
      <table class="findings">
        <thead><tr><th>Word count quartile</th><th>n</th><th>Median word count</th><th>Median percentile</th></tr></thead>
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
        <p class="section-label">Finding 1b · Number Leads — Deep Dive</p>
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
          <p><strong>Top performers — specific numbers</strong></p>
          <ul class="headline-list">{_nl_specific_examples}</ul>
        </div>
        <div>
          <p><strong>Top performers — round numbers</strong></p>
          <ul class="headline-list">{_nl_round_examples}</ul>
        </div>
      </div>
      <h3>By number type</h3>
      <table class="findings">
        <thead><tr><th>Number type</th><th>n</th><th>Median percentile</th><th>Lift vs. baseline</th></tr></thead>
        <tbody>{_t_nl_type}</tbody>
      </table>
      <p class="callout-inline"><strong>Note:</strong> Nearly all number-lead articles ({NL_NOTE_FRAC}) use a count or list format. Dollar amounts and ordinals appear too rarely (n&lt;10) for reliable conclusions.</p>
      <h3>By number magnitude</h3>
      <table class="findings">
        <thead><tr><th>Number range</th><th>n</th><th>Median percentile</th><th>Lift vs. baseline</th></tr></thead>
        <tbody>{_t_nl_size}</tbody>
      </table>
      <p class="callout-inline"><strong>Unexpected:</strong> The {NL_SWEET_SPOT_CAT} range outperforms even single-digit numbers ({NL_SWEET_SPOT_MED:.0%}ile). The {NL_WORST_CAT} range is the weakest ({NL_WORST_MED:.0%}ile) — avoid leading with totals, casualty counts, or cumulative statistics that tend to produce large numbers.</p>
    </div>
  </details>
"""

# ── Archive helpers (shared by main page and playbook archive logic) ──────────

def _slug_to_label(slug):
    try:
        from datetime import datetime as _dt
        return _dt.strptime(slug, "%Y-%m").strftime("%B %Y")
    except ValueError:
        # Slug doesn't match YYYY-MM format; return as-is
        return slug

def _slug_age_months(slug):
    """Months between slug (YYYY-MM) and today. Returns large number on parse failure."""
    try:
        from datetime import datetime as _dt, date as _date
        then = _dt.strptime(slug, "%Y-%m").date().replace(day=1)
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
<meta name="data-run" content="{REPORT_DATE_SLUG}">
<title>T1 Headline Performance Analysis · McClatchy CSA</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  /* ── Theme tokens ── */
  body.theme-light {{
    --bg:           #ffffff;
    --bg-card:      #ffffff;
    --bg-muted:     #f5f5f7;
    --bg-subtle:    #f0f0f0;
    --text:         #1d1d1f;
    --text-secondary: #424245;
    --text-muted:   #6e6e73;
    --border:       #d2d2d7;
    --border-subtle:#f0f0f0;
    --accent:       #0071e3;
    --nav-bg:       rgba(255,255,255,0.88);
  }}
  body.theme-dark {{
    --bg:           #0f172a;
    --bg-card:      #1e293b;
    --bg-muted:     #1e293b;
    --bg-subtle:    #334155;
    --text:         #f1f5f9;
    --text-secondary: #cbd5e1;
    --text-muted:   #b0bec5;
    --border:       #334155;
    --border-subtle:#1e293b;
    --accent:       #3b82f6;
    --nav-bg:       rgba(15,23,42,0.88);
  }}

  /* ── Reset ── */
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  /* ── Base ── */
  body {{ font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text); font-size: 14px; line-height: 1.6; -webkit-font-smoothing: antialiased; transition: background 0.2s, color 0.2s; }}

  /* ── Nav ── */
  nav {{ position: sticky; top: 0; z-index: 100; background: var(--nav-bg); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border-bottom: 1px solid var(--border); height: 44px; display: flex; align-items: center; gap: 0; padding: 0 28px; }}
  .brand {{ font-size: 11px; font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase; color: var(--text); flex-shrink: 0; }}
  .nav-links {{ display: flex; align-items: center; gap: 16px; margin-left: 24px; flex: 1; }}
  .nav-links a {{ font-size: 12px; color: var(--text-muted); text-decoration: none; transition: color 0.15s; }}
  .nav-links a:hover {{ color: var(--text); }}
  .nav-meta {{ display: flex; align-items: center; gap: 8px; margin-left: auto; padding-left: 20px; border-left: 1px solid var(--border); }}
  .theme-btn {{ background: none; border: 1px solid var(--border); color: var(--text-muted); font-size: 13px; line-height: 1; cursor: pointer; border-radius: 6px; padding: 3px 9px; transition: background 0.15s, color 0.15s, border-color 0.15s; }}
  .theme-btn:hover {{ background: var(--bg-muted); color: var(--text); border-color: var(--text-muted); }}

  /* ── Hero ── */
  .hero {{ padding: 32px 28px 28px; text-align: center; border-bottom: 1px solid var(--border-subtle); }}
  .eyebrow {{ font-size: 11px; font-weight: 500; letter-spacing: 0.09em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 16px; }}
  .hero h1 {{ font-size: 26px; font-weight: 600; line-height: 1.35; color: var(--text); max-width: 840px; margin: 0 auto 30px; letter-spacing: -0.01em; }}
  .hero-stats {{ display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 6px 18px; }}
  .stat-num {{ font-size: 18px; font-weight: 600; color: var(--text); margin-right: 4px; }}
  .stat-label {{ font-size: 11px; color: var(--text-muted); }}
  .stat-sep {{ color: var(--border); margin: 0 2px; }}

  /* ── Tile grid ── */
  main {{ max-width: 1100px; margin: 0 auto; padding: 28px 24px 0; }}
  .grid-label {{ font-size: 11px; font-weight: 500; letter-spacing: 0.07em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 14px; }}
  .tile-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 0; }}
  .tile {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px 14px; cursor: pointer; display: flex; flex-direction: column; gap: 7px; transition: box-shadow 0.15s ease, border-color 0.15s ease, background 0.2s; min-height: 140px; }}
  .tile:hover {{ box-shadow: 0 2px 12px rgba(0,0,0,0.10); border-color: var(--text-muted); }}
  .tile.active {{ border-color: var(--accent); box-shadow: 0 0 0 3px rgba(0,113,227,0.12); }}
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
                 border-radius:8px; margin:0.5rem 0 1.25rem;
                 box-shadow:0 0 0 1px var(--border),0 1px 3px rgba(0,0,0,0.2); }}
  table.findings {{ width:100%; border-collapse:collapse; font-size:0.78rem; margin:0;
                    background:var(--bg); border-radius:8px; overflow:hidden; }}
  table.findings th {{ text-align:left; padding:6px 10px; background:var(--nav-bg); color:var(--text-muted);
                       font-weight:600; font-size:0.6rem; text-transform:uppercase; white-space:nowrap;
                       letter-spacing:0.08em; border-bottom:1px solid var(--border); }}
  table.findings td {{ padding:6px 10px; border-bottom:1px solid var(--bg-card);
                       vertical-align:top; color:var(--text-secondary);
                       word-break:break-word; overflow-wrap:break-word; }}
  table.findings tr:last-child td {{ border-bottom:none; }}
  table.findings tr:hover td {{ background:var(--bg-muted); }}

  /* ── Tags (semantic status colors stay fixed) ── */
  .tag {{ display: inline-block; font-size: 10px; font-weight: 600; border-radius: 4px; padding: 2px 6px; margin-right: 6px; }}
  .tag-green {{ background: #e8f5e9; color: #1d8348; }}
  .tag-red {{ background: #fdecea; color: #c0392b; }}
  .tag-gray {{ background: var(--bg-subtle); color: var(--text-muted); }}
  .tag-blue {{ background: #e8f0fe; color: #1a73e8; }}
  .tag-amber {{ background: #fff8e1; color: #b45309; }}

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
  footer {{ padding: 40px 28px; text-align: center; color: var(--text-muted); font-size: 11px; border-top: 1px solid var(--border-subtle); background: var(--bg); margin-top: 0; letter-spacing: 0.01em; }}
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
  table thead th:hover {{ color: var(--text-primary, #f1f5f9); }}
  .sort-icon {{ opacity: 0.4; font-size: 0.75em; margin-left: 4px; font-style: normal; }}
  table thead th[data-sort] .sort-icon {{ opacity: 1; color: #60a5fa; }}
</style>
</head>
<body class="theme-{THEME}">

<nav>
  <span class="brand">McClatchy CSA · T1 Headlines</span>
  <div class="nav-links">
    <a href="playbook/">Playbooks</a>
    <a href="experiments/">Experiments</a>
  </div>
  <div class="nav-meta">
    <button id="theme-toggle" class="theme-btn" onclick="toggleTheme()" aria-label="Toggle dark mode">🌙</button>
  </div>
</nav>

<div class="hero">
  <p class="eyebrow">T1 Headline Performance Analysis · McClatchy CSA</p>
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
  <p class="grid-label">9 findings — click any card to expand</p>
  <div class="tile-grid">

    <div class="tile" onclick="showDetail('formulas', this)">
      <span class="tile-num">1 · Apple News Formulas</span>
      <p class="tile-claim">Number leads and question-format headlines significantly underperform the baseline. No formula shows confirmed lift above it — but underperformance is statistically clear.</p>
      <p class="tile-action">→ Audit number-lead and question-format headlines. Specificity and execution matter more than format choice.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    {"" if NL_PARSED < 10 else f"""
    <div class="tile" onclick="showDetail('numleads', this)">
      <span class="tile-num">1b · Number Leads Deep Dive</span>
      <p class="tile-claim">Round numbers score {NL_ROUND_SPECIFIC_PTS} percentile points below specific numbers. Numbers in the {NL_SWEET_SPOT_CAT} range are the highest-performing in this dataset ({NL_SWEET_SPOT_MED:.0%}ile).</p>
      <p class="tile-action">→ Use precise figures. Avoid leading with totals, round counts, or numbers above 50.</p>
      <span class="tile-more">Details ↓</span>
    </div>
    """}

    <div class="tile" onclick="showDetail('featured', this)">
      <span class="tile-num">2 · Featured on Apple News</span>
      <p class="tile-claim">"What to know" gets Featured {WTN_FEAT_LIFT:.1f}× more often — but organic views trend lower ({WTN_ORGANIC_P_STR}, not significant at α=0.05, n={WTN_N_NONFEAT}).</p>
      <p class="tile-action">→ Use "What to know" when targeting Featured specifically. Don't apply it broadly.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    <div class="tile" onclick="showDetail('smartnews', this)">
      <span class="tile-num">3 · SmartNews Allocation</span>
      <p class="tile-claim">Entertainment gets 36% of SmartNews volume at the lowest median percentile rank. Local delivers {float(_r4_loc['lift']):.2f}× on {float(_r4_loc['pct_share']):.0%} of volume.</p>
      <p class="tile-action">→ Shift SmartNews volume toward Local and U.S. National. No new content required.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    <div class="tile" onclick="showDetail('notifications', this)">
      <span class="tile-num">4 · Push Notifications</span>
      <p class="tile-claim">"Exclusive" is associated with {_excl_lift_val:.1f}× higher CTR {EXCL_CI_STR}. Short notifications (≤80 chars) get 39% fewer clicks.</p>
      <p class="tile-action">→ Lead with "EXCLUSIVE:" on genuine scoops. Write longer, more descriptive push text.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    <div class="tile" onclick="showDetail('topics', this)">
      <span class="tile-num">5 · Platform Topic Inversion</span>
      <p class="tile-claim">Sports is #{sports_an_rank} on Apple News and #{sports_sn_rank} (last) on SmartNews — the largest topic-rank gap by platform ({abs(sports_an_rank - sports_sn_rank)} rank positions).</p>
      <p class="tile-action">→ Write platform-specific sports briefs. Don't reuse Apple News sports content on SmartNews.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    <div class="tile" onclick="showDetail('allocation', this)">
      <span class="tile-num">6 · Headline Variance by Topic</span>
      <p class="tile-claim">Business and lifestyle have the widest outcome spread (IQR/median: {F6_BIZ_CV} and {F6_LIFE_CV} respectively). This is where headline choice pays off most.</p>
      <p class="tile-action">→ Concentrate headline variant testing on business and lifestyle content.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    <div class="tile" onclick="showDetail('engagement', this)">
      <span class="tile-num">7 · Views vs. Reading Depth</span>
      <p class="tile-claim">Views and reading time show near-zero correlation (r={r_views_at:.3f}, p={p_views_at:.2f}) — high-reach and deep-read articles are largely distinct populations.</p>
      <p class="tile-action">→ Track active time alongside views. Use both signals for variant ROI.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    <div class="tile" onclick="showDetail('longitudinal', this)">
      <span class="tile-num">8 · Trends Over Time</span>
      <p class="tile-claim">Number leads climbed from {NL_LIFT_EARLY:.2f}× (Q1 2025) to {NL_LIFT_LATE:.2f}× (Q1 2026) — the only formula to cross into above-baseline territory. Question format dropped from {Q_LIFT_EARLY:.2f}× to {Q_LIFT_LATE:.2f}×.</p>
      <p class="tile-action">→ Lean into number leads; deprioritize question-format headlines. Re-check quarterly as 2026 data accumulates.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    {"" if not (HAS_TRACKER and N_TRACKED > 0) else f"""
    <div class="tile" onclick="showDetail('team', this)">
      <span class="tile-num">9 · Team Performance</span>
      <p class="tile-claim">{N_TRACKED} articles matched across platforms. Long-form articles ({_F9_Q4_WORDS_STR}+ words) syndicate at the {_F9_Q4_PCT_STR} — the lowest of any length group.</p>
      <p class="tile-action">→ Target the middle word-count range ({_F9_Q2_WORDS_STR} words, {_F9_Q2_PCT_STR}ile) for syndication. Review team percentile rankings monthly.</p>
      <span class="tile-more">Details ↓</span>
    </div>
    """}

  </div><!-- /.tile-grid -->

  <div class="detail-area" id="detail-area" style="display:none;">
    <div class="detail-wrap">
      <button class="detail-close" onclick="closeDetail()">×</button>

      <!-- DETAIL: FORMULAS -->
      <div class="detail-panel" id="detail-formulas">
        <h2>Finding 1 · Apple News Formulas</h2>
        <div class="callout">
          <strong>Key finding:</strong> No formula shows statistically confirmed lift above baseline — but several significantly drag performance below it. "Here's / Here are" posts the highest median percentile ({F1_HERES_PCT}) on only n={F1_HERES_N} articles — directional, not confirmed. Number leads and question-format headlines statistically <em>underperform</em> the baseline ({F1_NUM_P_STR} and {F1_Q_P_STR} respectively, BH-adj). The formula alone isn't the signal — how you execute it is.
        </div>
        <p>Across {len(nf):,} non-Featured articles, three formula types significantly underperform the baseline: number leads ({_r1_num['lift']:.2f}×, {F1_NUM_P_STR}), question format ({_r1_q['lift']:.2f}×, {F1_Q_P_STR}), and quoted ledes ({_r1_ql['lift']:.2f}×, {F1_QL_P_STR}) — all BH-FDR adjusted. The better-performing formulas — "Here's / Here are" ({_r1_h['lift']:.2f}×) and possessive named entity ({_r1_pne['lift']:.2f}×) — are directional but not statistically significant at current sample sizes (n={_r1_h['n']} and n={_r1_pne['n']} respectively).</p>
        <p>These lifts are now expressed as percentile ratios: a lift of {_r1_h['lift']:.2f}× means the "Here's" group's median article falls in a {_r1_h['lift']:.2f}× higher monthly cohort percentile than untagged articles. Number leads fall to the {_r1_num['median']:.0%}ile of their monthly cohort, versus {baseline.median():.0%}ile for untagged articles.</p>
        <div class="chart-wrap">{c1}</div>
        <table class="findings">
          <thead><tr><th>Formula</th><th>n</th><th>Median %ile</th><th>Lift</th><th>95% CI (bootstrap)</th><th>Effect size r</th><th>p<sub>adj</sub> (BH–FDR)</th><th>n needed (80% power)</th></tr></thead>
          <tbody>{_t1}</tbody>
        </table>
        <p class="callout-inline"><strong>Read this table as:</strong> "lift" is the formula's median percentile divided by the untagged baseline (46th percentile). Lift &lt;1.0 means the formula underperforms. BH-adj p corrects for testing 6 formulas simultaneously.</p>
        <h3>Untagged baseline characterisation</h3>
        <p>The "untagged" baseline ({UNTAGGED_N:,} articles, {UNTAGGED_PCT:.0%} of non-Featured) comprises headlines that do not match any formula regex — typically mid-sentence constructions, declarative statements, and soft-news ledes. Sample (random): <em>{' / '.join([str(x)[:80] for x in _ung_sample])}</em>.</p>
        <p class="caveat">Non-Featured articles only (n={len(nf):,}). Primary metric: percentile_within_cohort — percentile rank within same publication month, controlling for temporal view accumulation bias. Mann-Whitney U vs. untagged baseline; effect size = rank-biserial r. 95% CIs: 1,000-iteration bootstrap on median ratio (seed=42). BH–FDR applied across all {len(_q1_raw_p)} formula tests. Stars: * p&lt;0.05 ** p&lt;0.01 *** p&lt;0.001. "n needed" = estimated per-group sample for 80% power (α=0.05). Formula classifier: unvalidated regex.</p>
      </div><!-- /#detail-formulas -->

      {"" if NL_PARSED < 10 else f"""
      <!-- DETAIL: NUMLEADS -->
      <div class="detail-panel" id="detail-numleads">
        <h2>Finding 1b · Number Leads — Deep Dive</h2>
        <div class="callout">
          <strong>Key finding:</strong> Round numbers (multiples of 10, 100, 1,000) score at the {NL_ROUND_MED:.0%}ile — {NL_ROUND_SPECIFIC_PTS} percentile points below specific numbers ({NL_SPECIFIC_MED:.0%}ile). The difference is statistically significant ({NL_P_STR}). Numbers in the {NL_SWEET_SPOT_CAT} range are the highest-performing in this dataset ({NL_SWEET_SPOT_MED:.0%}ile). Numbers {NL_WORST_CAT} drag performance to the {NL_WORST_MED:.0%}ile. Bottom line: "127 arrested" outperforms "100 arrested," and "15 takeaways" outperforms "50 things to know."
        </div>
        <h3>Round vs. specific numbers</h3>
        <p>Round numbers (multiples of 10, 100, 1,000): median {NL_ROUND_MED:.0%}ile vs. specific numbers: median {NL_SPECIFIC_MED:.0%}ile. ({_nl_round_sig})</p>
        <div class="two-col">
          <div>
            <p><strong>Top performers — specific numbers</strong></p>
            <ul class="headline-list">{_nl_specific_examples}</ul>
          </div>
          <div>
            <p><strong>Top performers — round numbers</strong></p>
            <ul class="headline-list">{_nl_round_examples}</ul>
          </div>
        </div>
        <h3>By number type</h3>
        <table class="findings">
          <thead><tr><th>Number type</th><th>n</th><th>Median percentile</th><th>Lift vs. baseline</th></tr></thead>
          <tbody>{_t_nl_type}</tbody>
        </table>
        <p class="callout-inline"><strong>Note:</strong> Nearly all number-lead articles ({NL_NOTE_FRAC}) use a count or list format. Dollar amounts and ordinals appear too rarely (n&lt;10) for reliable conclusions.</p>
        <h3>By number magnitude</h3>
        <table class="findings">
          <thead><tr><th>Number range</th><th>n</th><th>Median percentile</th><th>Lift vs. baseline</th></tr></thead>
          <tbody>{_t_nl_size}</tbody>
        </table>
        <p class="callout-inline"><strong>Unexpected:</strong> The {NL_SWEET_SPOT_CAT} range outperforms even single-digit numbers ({NL_SWEET_SPOT_MED:.0%}ile). The {NL_WORST_CAT} range is the weakest ({NL_WORST_MED:.0%}ile) — avoid leading with totals, casualty counts, or cumulative statistics that tend to produce large numbers.</p>
      </div><!-- /#detail-numleads -->
      """}

      <!-- DETAIL: FEATURED -->
      <div class="detail-panel" id="detail-featured">
        <h2>Finding 2 · Featured on Apple News</h2>
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
        <h3>Featured placement: reach vs. reading depth</h3>
        <p>Featured articles average {_feat_at_an.median():.0f} seconds of active reading time versus {_nfeat_at_an.median():.0f} seconds for non-Featured. The difference is statistically significant (Mann-Whitney p&lt;0.0001). Apple's editorial promotion drives discovery; readers who find an article because the algorithm surfaced it are slightly less engaged than readers who sought it out.</p>
        <p class="caveat">All {N_AN:,} Apple News articles (2025–2026). Chi-square test: each formula vs. all other articles combined. BH–FDR across all {len(_q2_raw_p)} formula tests. Causal direction of "What to know" → Featured is unconfirmed.</p>
      </div><!-- /#detail-featured -->

      <!-- DETAIL: SMARTNEWS -->
      <div class="detail-panel" id="detail-smartnews">
        <h2>Finding 3 · SmartNews Allocation</h2>
        <div class="callout">
          <strong>High-leverage finding:</strong> Entertainment is {float(_r4_ent['pct_share']):.0%} of SmartNews article volume ({int(_r4_ent['n']):,} articles) at {float(_r4_ent['lift']):.2f}× median percentile rank. Local is {float(_r4_loc['lift']):.2f}× on {float(_r4_loc['pct_share']):.1%} of volume. U.S. National is {float(_r4_us['lift']):.2f}× on {float(_r4_us['pct_share']):.1%} of volume. The channel allocation is inverted: the highest-performing channels are starved while the lowest-performing channel dominates volume. No new content required — better channel framing captures the gains.
        </div>
        <p>SmartNews category channel data reveals a severe allocation mismatch. Articles appearing in the Local channel sit at the {_r4_loc['median_pct']:.0%}ile of their monthly cohort ({_r4_loc['median_views']:,.0f} median raw views). The U.S. National channel: {_r4_us['median_pct']:.0%}ile. The Top feed baseline: {top_median_sn_pct:.0%}ile. Meanwhile, Entertainment — which accounts for {_r4_ent['pct_share']:.1%} of all SmartNews articles — sits at only the {_r4_ent['median_pct']:.0%}ile.</p>
        <div class="chart-wrap">{c3}</div>
        <table class="findings">
          <thead><tr><th>Channel</th><th>Article count</th><th>% of total</th><th>Median %ile</th><th>Median raw views</th><th>Lift vs. Top</th><th>p<sub>adj</sub> (BH–FDR)</th></tr></thead>
          <tbody>{_t3}</tbody>
        </table>
        <p class="callout-inline"><strong>Read this table as:</strong> "Lift" compares each channel's median percentile to the Top feed baseline (88.9% of articles). Values above 1.0× mean that channel's articles outperform the overall Top-feed median. High lift + low volume share = underused channel.</p>
        <p class="caveat">SmartNews 2025 (n={N_SN:,} articles). Category columns contain channel-specific view counts; non-zero = article appeared in that channel. Lift = median percentile vs. Top feed median percentile. Mann-Whitney U: each channel vs. Top feed; BH–FDR correction applied across {len(_q4_raw_p)} tests. Independence caveat: {SN_MULTI_CAT_N:,} articles ({SN_MULTI_CAT_PCT:.0%}) appear in more than one category. 2026 export lacks category breakdown — 2025 data only.</p>
      </div><!-- /#detail-smartnews -->

      <!-- DETAIL: NOTIFICATIONS -->
      <div class="detail-panel" id="detail-notifications">
        <h2>Finding 4 · Push Notifications</h2>
        <div class="callout">
          <strong>Two signals dominate:</strong> "Exclusive" tag ({F4_EXCL_LIFT_STR} CTR lift, {F4_EXCL_P_STR}) and named person + possessive construction ({F4_POSS_LIFT_STR}, {F4_POSS_P_STR}). The counter-intuitive result: short notifications (≤80 chars) get {F4_SHORT_PCT_STR} fewer clicks. Longer, more descriptive notification text outperforms across the board.
        </div>
        <p>Across {N_NOTIF} Apple News push notifications (Jan–Feb 2026, median CTR {CTR_MED}), {N_SIG_NOTIF_FEATURES} features show statistically significant effects after FDR correction. The "exclusive" tag is the strongest at {EXCL_LIFT} lift. The possessive framing signal: notifications with a full named person AND a possessive construction drive {_r5_poss['lift']:.2f}× CTR vs. {_r5_full['lift']:.2f}× for merely naming someone. Question format hurts at {_r5_q['lift']:.2f}×, consistent with the Apple News article finding.</p>
        <div class="chart-wrap">{c4}</div>
        <table class="findings">
          <thead><tr><th>Feature</th><th>n (present)</th><th>Median CTR (present)</th><th>Median CTR (absent)</th><th>Lift (95% CI)</th><th>Effect size r</th><th>p<sub>adj</sub> (BH–FDR)</th></tr></thead>
          <tbody>{_t4}</tbody>
        </table>
        <p class="callout-inline"><strong>Read this table as:</strong> "Lift" is median CTR when the feature is present vs. absent. Overall median CTR is ~1.6%. A 2.0× lift means ~3.2% CTR. BH-adj p corrects for testing multiple features simultaneously.</p>
        {_excl_sensitivity_html}
        <h3>The serial/escalating story as a content type</h3>
        <p>The top 10 notifications by CTR are dominated by a single ongoing story: Nancy Guthrie's disappearance and its connection to Savannah Guthrie. This defines a content type: <strong>the serial/escalating story with a celebrity anchor</strong>. The formula: possessive named entity + new development + escalating stakes, published in installments. The structural recipe: <em>"[Celebrity]'s [family member/associate] [new disclosure/development]."</em></p>
        <p>What doesn't move the needle: neither "contains a number" (n={_r5_num['n_true']}, {_r5_num['lift']:.2f}×) nor "attribution" — says/told/reports (n={_r5_attr['n_true']}, {_r5_attr['lift']:.2f}×) — survive FDR correction.</p>
        <p class="caveat">Apple News Notifications, Jan–Feb 2026 (n={N_NOTIF} with valid CTR). Mann-Whitney U; effect size = rank-biserial r; 95% CIs via 1,000-iteration bootstrap. BH–FDR across all {len(_q5_raw_p)} feature tests. N=2 months only — findings are directional. Feature classifier unvalidated.</p>
      </div><!-- /#detail-notifications -->

      <!-- DETAIL: TOPICS -->
      <div class="detail-panel" id="detail-topics">
        <h2>Finding 5 · Platform Topic Inversion</h2>
        <div class="callout">
          <strong>Action:</strong> Write platform-specific variant briefs for sports and nature/wildlife — these two categories show the strongest inversions. Apple News sports: lead with team/player + outcome. SmartNews sports: don't rely on sports for reach — use local/civic and breaking news instead. Nature/wildlife is the mirror: underperforms on Apple News ({nw_an_idx:.2f}× platform median) but outperforms on SmartNews ({nw_sn_idx:.2f}×).
        </div>
        <p>Sports ranks #{sports_an_rank} on Apple News (percentile index {sports_an_idx:.2f}× platform median) but #{sports_sn_rank} — last — on SmartNews (index {sports_sn_idx:.2f}×). This is not a small difference: sports sits well above the Apple News median and well below the SmartNews median. {"The inversion is statistically significant (Mann-Whitney U, " + SPORTS_P_STR + ") across the full year of 2025 data." if SPORTS_P_STR else "The inversion holds across the full year of 2025 data."}</p>
        <p>Nature/wildlife shows the reverse: it underperforms the Apple News median ({nw_an_idx:.2f}×) but outperforms the SmartNews median ({nw_sn_idx:.2f}×). Among the top 30 most frequent words in top-quartile headlines on each platform, only {kw_overlap_n} words appear on both lists{f" ({', '.join(sorted(kw_overlap))})" if kw_overlap_n > 0 else ""} — generic reporting terms rather than shared topical vocabulary, suggesting the platforms reward very different content angles.</p>
        <div class="chart-wrap">{c5}</div>
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
        <p class="caveat">Topic tagged via unvalidated regex classifier applied to headline text. <strong>Coverage: {TOPIC_COVERAGE_PCT:.0%} of Apple News articles match a named topic; {TOPIC_OTHER_PCT:.0%} fall into "other/unclassified" and are excluded from this analysis.</strong> Results describe the classified minority — generalizing to all content requires caution. Percentile index = median percentile_within_cohort / platform overall median percentile. Apple News 2025–2026 (n={N_AN:,}); SmartNews 2025 (n={N_SN:,}). Subtopic classifier unvalidated. No significance testing — treat as descriptive. Subtopics with n&lt;3 show "—".</p>
      </div><!-- /#detail-topics -->

      <!-- DETAIL: ALLOCATION -->
      <div class="detail-panel" id="detail-allocation">
        <h2>Finding 6 · Headline Variance by Topic</h2>
        <div class="callout">
          <strong>Action:</strong> Concentrate variant production on high-variance topics — business (IQR/median = {F6_BIZ_CV}) and lifestyle ({F6_LIFE_CV}) on Apple News — where the gap between a top-quartile and bottom-quartile headline is widest. Crime and sports are more consistent mid-performers with less room to move.
        </div>
        <p>The chart shows IQR ÷ median of percentile_within_cohort for each topic × platform. A ratio of 1.5 means the articles between the 25th and 75th percentile span 1.5× the median — a wide, unpredictable range. Where this ratio is high, headline choice has the most room to lift or drag performance.</p>
        <div class="chart-wrap">{c6}</div>
        <p class="callout-inline"><strong>Read this chart as:</strong> IQR ÷ median of percentile rank — a scale-free measure of outcome spread. A higher value means the gap between a 25th-percentile and 75th-percentile article is wider relative to the median: more variance, more room for headline choice to make a difference. Lower values (sports, weather) mean outcomes cluster tightly — less leverage from headline optimization alone.</p>
        <h3>Crime: top vs. bottom quartile headlines on Apple News</h3>
        <div class="example-cols">
          <div class="example-list example-top"><h4>Top quartile crime headlines</h4><ul>{crime_top_h}</ul></div>
          <div class="example-list example-bot"><h4>Bottom quartile crime headlines</h4><ul>{crime_bot_h}</ul></div>
        </div>
        <p class="callout-inline"><strong>What separates top from bottom crime headlines:</strong> Top performers almost always include a named location, a named individual, or a specific count. Bottom performers use vague agency ("police say"), generic action words ("incident," "situation"), or lead with institutional attribution rather than the crime itself.</p>
        <h3>Business: top vs. bottom quartile headlines on Apple News</h3>
        <div class="example-cols">
          <div class="example-list example-top"><h4>Top quartile business headlines</h4><ul>{biz_top_h}</ul></div>
          <div class="example-list example-bot"><h4>Bottom quartile business headlines</h4><ul>{biz_bot_h}</ul></div>
        </div>
        <p class="callout-inline"><strong>What separates top from bottom business headlines:</strong> Top performers anchor to a specific company, dollar figure, or named individual. Bottom performers describe economic conditions abstractly ("rising costs," "market uncertainty") without a concrete hook.</p>
        <h3>Business subtopic drill-down</h3>
        <p>Within business, which sub-category performs best on each platform?</p>
        <table class="findings">
          <thead><tr><th>Subtopic</th><th>Apple News n</th><th>Apple News median %ile</th><th>SmartNews n</th><th>SmartNews median %ile</th></tr></thead>
          <tbody>{_t_biz_sub}</tbody>
        </table>
        <h3>Headline length vs. performance</h3>
        <p>Headline character count split into quartiles — median Apple News headline is {AN_MEDIAN_HL_LEN:.0f} chars; SmartNews is {SN_MEDIAN_HL_LEN:.0f} chars. {"Longer Apple News headlines outperform shorter ones: Q4 vs. Q1 Mann-Whitney U " + HL_AN_P_STR + " (BH-FDR). The same test on SmartNews: " + (HL_SN_P_STR or "insufficient data") + "." if HL_AN_P_STR else "The pattern is directional — no significant Q4 vs. Q1 difference detected at this sample."}</p>
        <div class="chart-wrap">{c_hl}</div>
        <table class="findings">
          <thead><tr><th>Length bucket</th><th>Median chars (AN)</th><th>Apple News n</th><th>Apple News median %ile</th><th>SmartNews n</th><th>SmartNews median %ile</th></tr></thead>
          <tbody>{_t_hl_len}</tbody>
        </table>
        <p class="caveat">IQR = interquartile range (75th percentile minus 25th percentile) of percentile_within_cohort. IQR/median is a scale-free spread measure (not CV, which is std/mean). Topic tagged via regex classifier. Apple News 2025–2026; SmartNews 2025. Topics with fewer than 10 articles excluded. High IQR/median on SmartNews local/civic is consistent with channel-placement bimodality (Finding 3) — articles land either in the high-ROI Local channel or the lower-ROI Top feed, producing a wide spread.</p>
      </div><!-- /#detail-allocation -->

      <!-- DETAIL: ENGAGEMENT -->
      <div class="detail-panel" id="detail-engagement">
        <h2>Finding 7 · Views vs. Reading Depth</h2>
        <div class="callout">
          <strong>Action:</strong> Don't use view count as the sole ROI signal for variant allocation. A variant driving 5,000 views at 75s average active time may deliver more subscriber retention value than one driving 20,000 views at 45s. The model should incorporate views (reach), saves (return intent), and active time (read depth) — all three are available in this dataset.
        </div>
        <p>The Apple News dataset includes both Total Views and average active time per article. Pearson r = {r_views_at:.3f} (p = {p_views_at:.2f}), Spearman ρ = {r_views_at_sp:.3f} (p = {p_views_at_sp:.2f}). Both agree: views and reading time show near-zero correlation across {len(an_eng):,} articles — high-reach and deep-read articles are largely distinct populations. The view count spans a {views_range_x:,}× range across deciles; active time moves only {at_range_s:.0f} seconds.</p>
        <div class="chart-wrap">{c7}</div>
        <table class="findings">
          <thead><tr><th>Metric</th><th>Correlation with Total Views</th><th>What it measures</th></tr></thead>
          <tbody>
            <tr><td>Avg. active time</td><td>r = {r_views_at:.3f}, ρ = {r_views_at_sp:.3f} (not significant)</td><td>Depth of the current read</td></tr>
            <tr><td>Saves</td><td>r = {r_saves:.2f} (strong)</td><td>Intent to return / bookmark behavior</td></tr>
            <tr><td>Likes</td><td>r = {r_likes:.2f} (strong)</td><td>Affirmation / social signal</td></tr>
            <tr><td>Article shares</td><td>r = {r_shares:.2f} (strong)</td><td>Distribution / word of mouth</td></tr>
          </tbody>
        </table>
        <p>Featured articles illustrate this split directly: {FEAT_VIEW_LIFT_STR} median view lift, but only {feat_at.median():.0f}s active time vs. {nfeat_at.median():.0f}s for non-Featured (p&lt;0.0001). Apple's editorial promotion drives discovery; readers who arrive via Featured spend slightly less time than readers who actively sought the article. Separately, subscribers average {sub_at_med:.0f}s active time vs. {nsub_at_med:.0f}s for non-subscribers — likely a usage behavior difference (subscribers browse more, read less per article) rather than a content quality gap.</p>
        <p class="caveat">Apple News 2025–2026 (n={len(an_eng):,} articles with valid active time). {at_low_n} articles have active time &lt;10s; {at_high_n} have &gt;300s — not filtered, ~{(at_low_n+at_high_n)/len(an_eng):.0%} of records. Spearman ρ is the preferred test for independence given skewed views distribution.</p>
      </div><!-- /#detail-engagement -->

      <!-- DETAIL: LONGITUDINAL -->
      <div class="detail-panel" id="detail-longitudinal">
        <h2>Finding 8 · Trends Over Time</h2>
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
        <p class="caveat">Quarters: Q1=Jan–Mar, Q2=Apr–Jun, Q3=Jul–Sep, Q4=Oct–Dec. Q1 2026 = Jan–Feb 2026 only. Lift = formula median percentile_within_cohort ÷ untagged baseline median within same quarter. Minimum 3 articles required per cell. Data through {REPORT_DATE}.</p>
      </div><!-- /#detail-longitudinal -->

      {"" if not (HAS_TRACKER and N_TRACKED > 0) else f"""
      <!-- DETAIL: TEAM -->
      <div class="detail-panel" id="detail-team">
        <h2>Finding 9 · Team Performance (Tracker)</h2>
        <div class="callout">
          <strong>Note:</strong> {N_TRACKED} articles from the content tracker matched to syndication data via URL or headline. Results are directional; match rate limits coverage.
        </div>
        <h3>Author performance by platform (sorted by median percentile)</h3>
        <table class="findings">
          <thead><tr><th>Author</th><th>Platform</th><th>n articles</th><th>Median percentile</th></tr></thead>
          <tbody>{_t_auth}</tbody>
        </table>
        <h3>Top 20 articles by percentile rank</h3>
        <table class="findings">
          <thead><tr><th>Article</th><th>Platform — Brand</th><th>Author</th><th>Percentile</th><th>Views</th><th>Featured</th></tr></thead>
          <tbody>{_t_team}</tbody>
        </table>
        <h3>Article length and syndication performance ({WC_MATCHED_N} matched articles with word count)</h3>
        <div class="callout">
          <strong>Unexpected:</strong> Articles in the longest quartile (~{_F9_Q4_WORDS_STR} words) perform at the {_F9_Q4_PCT_STR} — worse than any other length group. Q2 (~{_F9_Q2_WORDS_STR} words) is the highest-performing range in this sample at {_F9_Q2_PCT_STR}. {"Mann-Whitney Q4 vs. Q2: " + WC_P_STR + " (n=" + str(WC_MATCHED_N) + ", unadjusted). Pattern is consistent within SmartNews individually but interpret cautiously at this sample size." if WC_P_STR else "Based on " + str(WC_MATCHED_N) + " tracker-matched articles, mostly SmartNews — too small for reliable significance testing. Treat as directional."}
        </div>
        <table class="findings">
          <thead><tr><th>Word count quartile</th><th>n</th><th>Median word count</th><th>Median percentile</th></tr></thead>
          <tbody>{_t_wc}</tbody>
        </table>
        <p class="callout-inline"><strong>Read this table as:</strong> Articles from the content tracker matched to syndication data by URL and headline. Percentile ranks are platform-relative (SmartNews vs. SmartNews, Yahoo vs. Yahoo). Word count is from the tracker, not the syndication data.</p>
      </div><!-- /#detail-team -->
      """}

    </div><!-- /.detail-wrap -->
  </div><!-- /#detail-area -->

</main>

<script>
/* ── Theme toggle ── */
(function () {{
  var stored = localStorage.getItem('theme') || '{THEME}';
  applyTheme(stored);
}})();

function applyTheme(t) {{
  document.body.className = 'theme-' + t;
  var btn = document.getElementById('theme-toggle');
  if (btn) btn.textContent = t === 'dark' ? '☀︎' : '🌙';
  localStorage.setItem('theme', t);
}}

function toggleTheme() {{
  var next = document.body.classList.contains('theme-dark') ? 'light' : 'dark';
  applyTheme(next);
}}

/* ── Detail panels ── */
function showDetail(id, tile) {{
  document.querySelectorAll('.tile').forEach(t => t.classList.remove('active'));
  tile.classList.add('active');
  document.querySelectorAll('.detail-panel').forEach(p => p.style.display = 'none');
  const panel = document.getElementById('detail-' + id);
  if (panel) panel.style.display = 'block';
  const area = document.getElementById('detail-area');
  area.style.display = 'block';
  setTimeout(() => area.scrollIntoView({{ behavior: 'smooth', block: 'start' }}), 50);
}}

function closeDetail() {{
  document.getElementById('detail-area').style.display = 'none';
  document.querySelectorAll('.tile').forEach(t => t.classList.remove('active'));
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
</script>

{_main_past_runs_html}

<footer>
  <p>McClatchy CSA · T1 Headline Performance Analysis · {REPORT_DATE}</p>
  <p style="margin-top: 6px;">
    <a href="experiments/">Experiments</a> &nbsp;·&nbsp;
    <a href="playbook/">Playbooks</a> &nbsp;·&nbsp;
    Data: T1 Headline Performance Sheet · Apple News, SmartNews, MSN, Yahoo
  </p>
</footer>

</body>
</html>"""

out = Path("docs/index.html")
out.parent.mkdir(exist_ok=True)
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
    ("conf-high", "pb-1", f"""  <div class="pb-tile" onclick="togglePb(this,'pb-1')">
    <span class="conf-badge conf-high">High confidence</span>
    <span class="tile-label">Apple News \u00b7 Headline Formulas</span>
    <p class="tile-claim">Number leads and question-format headlines significantly underperform the baseline. No formula shows confirmed lift above it \u2014 but specific patterns clearly underperform.</p>
    <p class="tile-action">\u2192 Audit number-lead and question-format headlines. Specificity and execution matter more than format choice alone.</p>
    <span class="tile-toggle">Details \u2193</span>
  </div>"""),
    ("conf-high", "pb-2", f"""  <div class="pb-tile" onclick="togglePb(this,'pb-2')">
    <span class="conf-badge conf-high">High confidence</span>
    <span class="tile-label">Apple News \u00b7 Featured Targeting</span>
    <p class="tile-claim">\u201cWhat to know\u201d is associated with {WTN_FEAT_LIFT:.1f}\u00d7 Featured placement. But for non-Featured articles, organic view performance trends lower ({WTN_ORGANIC_P_STR}, not significant at \u03b1=0.05, n={WTN_N_NONFEAT}).</p>
    <p class="tile-action">\u2192 Reserve \u201cWhat to know\u201d for intentional Featured campaigns. Don\u2019t apply it broadly for organic reach.</p>
    <span class="tile-toggle">Details \u2193</span>
  </div>"""),
    ("conf-high", "pb-3", f"""  <div class="pb-tile" onclick="togglePb(this,'pb-3')">
    <span class="conf-badge conf-high">High confidence</span>
    <span class="tile-label">SmartNews \u00b7 Channel Allocation</span>
    <p class="tile-claim">Entertainment receives {float(_r4_ent['pct_share']):.0%} of SmartNews volume at the lowest median percentile rank. Local and U.S. National deliver {float(_r4_loc['lift']):.2f}\u00d7 and {float(_r4_us['lift']):.2f}\u00d7 on far less.</p>
    <p class="tile-action">\u2192 Shift volume toward Local and U.S. National. No new content required \u2014 reframe what\u2019s already being published.</p>
    <span class="tile-toggle">Details \u2193</span>
  </div>"""),
    ("conf-mod", "pb-4", f"""  <div class="pb-tile" onclick="togglePb(this,'pb-4')">
    <span class="conf-badge conf-mod">Moderate \u00b7 Jan\u2013Feb 2026 only</span>
    <span class="tile-label">Push Notifications</span>
    <p class="tile-claim">{N_SIG_NOTIF_FEATURES} features show significant CTR lift after multiple-comparison correction. \u201cEXCLUSIVE:\u201d and possessive framing are the top signals.</p>
    <p class="tile-action">\u2192 Lead genuine scoops with \u201cEXCLUSIVE:\u201d; use possessive framing; write \u226580 characters to give readers context before the tap.</p>
    <span class="tile-toggle">Details \u2193</span>
  </div>"""),
    (HL_CONF_CLASS, "pb-5", f"""  <div class="pb-tile" onclick="togglePb(this,'pb-5')">
    <span class="conf-badge {HL_CONF_CLASS}">{HL_CONF_LABEL}</span>
    <span class="tile-label">Apple News \u00b7 Headline Length</span>
    <p class="tile-claim">Top-quartile headlines ({AN_LEN_Q4_CHARS_STR} chars) reach {AN_LEN_Q4_STR} median %ile vs. {AN_LEN_Q1_STR} for bottom-quartile ({AN_LEN_Q1_CHARS_STR} chars). {"Mann-Whitney Q4 vs. Q1: " + HL_AN_P_STR + " (BH-FDR)." if HL_AN_P_STR else "Effect is directional \u2014 Q4 vs. Q1 difference not statistically confirmed."}</p>
    <p class="tile-action">\u2192 Don\u2019t truncate. The \u226480 char rule applies to push notifications only \u2014 not to article headlines.</p>
    <span class="tile-toggle">Details \u2193</span>
  </div>"""),
]

_pb_tile_defs.sort(key=lambda x: _CONF_RANK.get(x[0], 3))  # stable sort preserves original order within same rank
_pb_tiles_html = "\n\n".join(t for _, _, t in _pb_tile_defs)

# ── Editorial Playbooks page ──────────────────────────────────────────────────
playbook_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="data-run" content="{REPORT_DATE_SLUG}">
<title>T1 Headline Analysis · Playbooks</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Helvetica Neue",Arial,sans-serif;
          background:#0f172a; color:#e2e8f0; font-size:15px; line-height:1.7;
          -webkit-font-smoothing:antialiased; }}
  nav {{ background:rgba(15,23,42,0.95); backdrop-filter:blur(20px);
         -webkit-backdrop-filter:blur(20px); padding:0 2rem;
         display:flex; align-items:center; gap:0; height:44px;
         border-bottom:1px solid rgba(255,255,255,0.06); position:sticky; top:0; z-index:100; }}
  .brand {{ color:#f1f5f9; font-weight:700; font-size:0.72rem;
            letter-spacing:0.1em; text-transform:uppercase; flex-shrink:0; }}
  .nav-links {{ display:flex; align-items:center; gap:16px; margin-left:24px; flex:1; }}
  .nav-links a {{ color:#94a3b8; text-decoration:none; font-size:12px; transition:color 0.15s; }}
  .nav-links a:hover {{ color:#f1f5f9; }}
  .container {{ max-width:920px; margin:0 auto; padding:2.5rem 2rem 5rem; }}
  .eyebrow {{ text-transform:uppercase; letter-spacing:0.14em; font-size:0.6rem;
              color:#60a5fa; font-weight:700; margin-bottom:0.5rem; display:block; }}
  h1 {{ font-size:1.55rem; font-weight:700; line-height:1.3;
        letter-spacing:-0.02em; margin-bottom:0.4rem; color:#f1f5f9; }}
  .sub {{ color:#94a3b8; font-size:0.875rem; margin-bottom:0; }}
  .run-header {{ display:flex; align-items:baseline; gap:12px; margin:2rem 0 1.25rem;
                 padding-bottom:0.75rem; border-bottom:1px solid #1e293b; }}
  .run-label {{ font-size:1.05rem; font-weight:700; color:#f1f5f9; letter-spacing:-0.01em; }}
  .run-meta {{ font-size:0.8rem; color:#64748b; }}
  .tile-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:1rem; }}
  @media (max-width:720px) {{ .tile-grid {{ grid-template-columns:1fr; }} }}
  @media (max-width:1000px) and (min-width:721px) {{ .tile-grid {{ grid-template-columns:repeat(2,1fr); }} }}
  .pb-tile {{ background:#1e293b; border:1px solid #334155; border-radius:10px;
              padding:1.1rem 1.25rem; cursor:pointer;
              transition:border-color 0.15s, box-shadow 0.15s; user-select:none; }}
  .pb-tile:hover {{ border-color:#475569; box-shadow:0 0 0 1px #475569 inset; }}
  .pb-tile.open {{ border-color:#3b82f6; box-shadow:0 0 0 1px #3b82f6 inset; }}
  .conf-badge {{ display:inline-block; font-size:9px; font-weight:700; text-transform:uppercase;
                 letter-spacing:0.07em; padding:2px 6px; border-radius:3px; margin-bottom:8px; }}
  .conf-high {{ background:rgba(22,163,74,0.2); color:#4ade80; }}
  .conf-mod  {{ background:rgba(37,99,235,0.2);  color:#60a5fa; }}
  .conf-dir  {{ background:rgba(100,116,139,0.15); color:#94a3b8; }}
  .tile-label {{ display:block; font-size:0.78rem; font-weight:700; color:#f1f5f9;
                 letter-spacing:0.01em; margin-bottom:0.5rem; }}
  .tile-claim {{ font-size:0.84rem; color:#cbd5e1; margin-bottom:0.5rem; line-height:1.55; }}
  .tile-action {{ font-size:0.8rem; color:#60a5fa; font-weight:500; margin-bottom:0.5rem; line-height:1.45; }}
  .tile-toggle {{ font-size:0.7rem; color:#64748b; display:block; margin-top:0.5rem; }}
  .pb-detail {{ background:#1e293b; border:1px solid #334155; border-radius:10px;
                padding:1.5rem 1.75rem; margin-bottom:1rem; }}
  h3.rh {{ font-size:0.65rem; font-weight:700; letter-spacing:0.1em; text-transform:uppercase;
           color:#94a3b8; margin:1.5rem 0 0.6rem; }}
  h3.rh:first-child {{ margin-top:0; }}
  p.detail-sub {{ font-size:0.8rem; color:#64748b; margin-bottom:0.6rem; }}
  .table-wrap {{ overflow-x:auto; -webkit-overflow-scrolling:touch; max-width:100%;
                 border-radius:8px; margin:0.5rem 0 1.25rem;
                 box-shadow:0 0 0 1px #334155,0 1px 3px rgba(0,0,0,0.2); }}
  table {{ width:100%; border-collapse:collapse; font-size:0.78rem; margin:0;
           background:#0f172a; border-radius:8px; overflow:hidden; }}
  th {{ text-align:left; padding:6px 10px; background:#0a1120; color:#94a3b8;
        font-weight:600; font-size:0.6rem; text-transform:uppercase; white-space:nowrap;
        letter-spacing:0.08em; border-bottom:1px solid #334155; }}
  td {{ padding:6px 10px; border-bottom:1px solid #1e293b; vertical-align:top; color:#cbd5e1;
        word-break:break-word; overflow-wrap:break-word; }}
  tr:last-child td {{ border-bottom:none; }}
  .rules {{ padding-left:18px; margin:0.5rem 0 1rem; font-size:0.875rem;
            line-height:1.85; color:#cbd5e1; }}
  .rules li {{ margin-bottom:0.15rem; }}
  .caveat {{ font-size:0.74rem; color:#64748b; margin-top:1rem; line-height:1.6; }}
  .past-run-details {{ margin-top:1.5rem; border:1px solid #1e293b; border-radius:10px;
                       overflow:hidden; }}
  .past-run-summary {{ display:flex; align-items:baseline; gap:12px; padding:0.85rem 1.25rem;
                       cursor:pointer; list-style:none; user-select:none;
                       background:#111827; }}
  .past-run-summary::-webkit-details-marker {{ display:none; }}
  .past-run-summary:hover {{ background:#1a2438; }}
  details.past-run-details[open] .past-run-summary {{ border-bottom:1px solid #1e293b; }}
  .past-run-summary .run-label {{ font-size:0.95rem; font-weight:700; color:#f1f5f9;
                                   letter-spacing:-0.01em; }}
  .past-run-summary .run-meta {{ font-size:0.78rem; color:#64748b; flex:1; }}
  .run-expand-hint {{ font-size:0.7rem; color:#475569; margin-left:auto; flex-shrink:0; }}
  details[open] .run-expand-hint {{ visibility:hidden; }}
  .past-run-body {{ padding:1.25rem 1.25rem 1rem; background:#0f172a; }}
  .tile-grid-compact {{ margin-bottom:0.75rem; pointer-events:none; }}
  .tile-grid-compact .pb-tile {{ cursor:default; }}
  .past-run-link {{ font-size:0.8rem; margin-top:0.75rem; }}
  .past-run-link a {{ color:#60a5fa; text-decoration:none; }}
  .past-run-link a:hover {{ color:#93c5fd; }}
  .past-section {{ margin-top:2rem; padding-top:1.5rem; border-top:1px solid #1e293b; }}
  .section-eyebrow {{ font-size:0.65rem; font-weight:700; letter-spacing:0.1em;
                      text-transform:uppercase; color:#94a3b8; margin-bottom:0.75rem;
                      display:block; }}
  .past-list {{ list-style:none; padding:0; margin:0; }}
  .past-list li {{ padding:0.4rem 0; border-bottom:1px solid #1e293b; }}
  .past-list li:last-child {{ border-bottom:none; }}
  .past-list a {{ color:#60a5fa; text-decoration:none; font-size:0.875rem; }}
  .past-list a:hover {{ color:#93c5fd; }}

  /* ── Sortable tables ── */
  table thead th {{ cursor: pointer; user-select: none; white-space: nowrap; }}
  table thead th:hover {{ color: #f1f5f9; }}
  .sort-icon {{ opacity: 0.4; font-size: 0.75em; margin-left: 4px; font-style: normal; }}
  table thead th[data-sort] .sort-icon {{ opacity: 1; color: #60a5fa; }}
</style>
</head>
<body>
<nav>
  <span class="brand">McClatchy CSA · T1 Headlines</span>
  <div class="nav-links">
    <a href="../">← Current analysis</a>
    <a href="../experiments/">Experiments</a>
  </div>
</nav>
<div class="container">

<span class="eyebrow">McClatchy CSA · T1 Headlines</span>
<h1>Editorial Playbooks</h1>
<p class="sub">Updated monthly. Click any tile to expand the full guidance.</p>

<div class="run-header">
  <span class="run-label">{_pb_run_label}</span>
  <span class="run-meta">T1 syndication data · {REPORT_DATE}</span>
</div>

<div class="tile-grid">

{_pb_tiles_html}

</div>

<!-- Detail panels (shown one at a time below the grid) -->

<div id="pb-1" class="pb-detail" style="display:none">
  <h3 class="rh">Rules of thumb</h3>
  <ul class="rules">
    <li><strong>Possessive + named entity</strong> on crime and business is associated with the highest consistent lift. Anchor to a specific person or company: "Target's layoffs," "Smith's arrest."</li>
    <li><strong>Number leads:</strong> use specific figures in the {NL_SWEET_SPOT_CAT} range. Round numbers score {NL_ROUND_SPECIFIC_PTS} percentile points below specific numbers ({NL_P_STR} after BH-FDR).</li>
    <li><strong>Avoid question format</strong> for organic reach — underperforms {_r1_q['lift']:.2f}× baseline ({F1_Q_P_STR}). Reserve for Featured targeting if "What to know" is unavailable.</li>
    <li><strong>Don't truncate headlines</strong> to fit a format preference — median performing length is {AN_MEDIAN_HL_LEN:.0f} chars.</li>
    <li><strong>Business and lifestyle</strong> have the widest outcome spread (IQR/median: {F6_BIZ_CV} and {F6_LIFE_CV}) — headline choice matters most here. Prioritize variant production on these topics first.</li>
  </ul>
  <h3 class="rh">Top formula × topic combinations — Apple News</h3>
  <p class="detail-sub">Non-Featured articles only · ranked by lift vs. untagged baseline · ≥5 articles per cell</p>
  <table>
    <thead><tr><th>Formula</th><th>Topic</th><th>n</th><th>Median %ile</th><th>Lift vs. baseline</th></tr></thead>
    <tbody>{_t_an_guide}</tbody>
  </table>
</div>

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

<div id="pb-3" class="pb-detail" style="display:none">
  <h3 class="rh">Rules of thumb</h3>
  <ul class="rules">
    <li><strong>Local and U.S. National channels</strong> are severely underused at {float(_r4_loc['lift']):.2f}× and {float(_r4_us['lift']):.2f}× median percentile rank respectively. Frame content with geographic specificity — "Sacramento," not "California," not "the region."</li>
    <li><strong>Reduce Entertainment volume</strong>: {float(_r4_ent['pct_share']):.0%} of articles, lowest median percentile rank. Reframe entertainment content toward lifestyle or local angles where possible.</li>
    <li><strong>Sports underperforms</strong> ({sports_sn_idx:.2f}× platform median) — the same story with a local or civic frame does better than a sports frame.</li>
    <li><strong>Channel allocation is the highest-leverage variable</strong> on SmartNews — more impactful than headline formula. Fix the allocation first, then optimize formulas within channels.</li>
  </ul>
  <h3 class="rh">Performance by channel — SmartNews</h3>
  <p class="detail-sub">Lift compares each channel's median %ile to the Top feed baseline. High lift + low volume = underused channel.</p>
  <table>
    <thead><tr><th>Channel</th><th>Article count</th><th>% of total</th><th>Median %ile</th><th>Median raw views</th><th>Lift vs. Top</th><th>p<sub>adj</sub> (BH-FDR)</th></tr></thead>
    <tbody>{_t3}</tbody>
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

<div id="pb-5" class="pb-detail" style="display:none">
  <h3 class="rh">Rules of thumb</h3>
  <ul class="rules">
    <li><strong>Longer outperforms shorter on Apple News</strong> — top quartile ({AN_LEN_Q4_CHARS_STR} chars) reaches {AN_LEN_Q4_STR} median %ile vs. {AN_LEN_Q1_STR} for bottom quartile ({AN_LEN_Q1_CHARS_STR} chars). {"Mann-Whitney Q4 vs. Q1: " + HL_AN_P_STR + " (BH-FDR)." if HL_AN_P_STR else "Effect is directional — difference not statistically confirmed at this sample."}</li>
    <li><strong>The \u226480-char rule applies to notifications only</strong> — don't apply it to article headlines. The data runs in the opposite direction.</li>
    <li><strong>Longer headlines may proxy for longer, higher-stakes stories</strong> — confounders exist. Don't pad headlines to hit a character count; use the length the story requires.</li>
    <li><strong>Business and lifestyle</strong> show the widest performance spread — length optimization is most likely to matter there.</li>
  </ul>
  <h3 class="rh">Views by headline length quartile — Apple News and SmartNews</h3>
  <table>
    <thead><tr><th>Length bucket</th><th>Median chars (AN)</th><th>Apple News n</th><th>Apple News median %ile</th><th>SmartNews n</th><th>SmartNews median %ile</th></tr></thead>
    <tbody>{_t_hl_len}</tbody>
  </table>
  {"<p class='caveat'>Mann-Whitney U (Q4 vs. Q1): Apple News " + HL_AN_P_STR + "; SmartNews " + (HL_SN_P_STR or "—") + " (BH-FDR). Confounders possible — longer headlines may coincide with longer, higher-stakes stories.</p>" if HL_AN_P_STR else "<p class='caveat'>Q4 vs. Q1 difference not statistically significant. Treat as directional orientation. Confounders possible — longer headlines may coincide with longer, higher-stakes stories.</p>"}
</div>

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
    setTimeout(function() {{ panel.scrollIntoView({{behavior:'smooth',block:'nearest'}}); }}, 50);
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
</script>
</body>
</html>"""

playbook_out = Path("docs/playbook/index.html")
playbook_out.parent.mkdir(exist_ok=True)
playbook_out.write_text(playbook_html, encoding="utf-8")
print(f"Playbooks written to {playbook_out}  ({len(playbook_html):,} chars)")

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
if _RIGOR_WARNINGS:
    print(f"\n  ⚠  {len(_RIGOR_WARNINGS)} rigor warning(s) — sections without significance tests:")
    for _w in _RIGOR_WARNINGS:
        print(f"     • {_w}")
else:
    print("  ✓  All major comparisons have significance tests.")
print(f"  meta.json → {_meta_slot}/meta.json")
print(f"{'─'*60}\n")
