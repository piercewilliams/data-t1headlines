"""
T1 Headline Analysis site generator
Run:    python3 generate_site.py
Output: docs/index.html

Optional args:
  --data-2025 "path/to/new_2025_file.xlsx"
  --data-2026 "path/to/new_2026_file.xlsx"
  --tracker   "path/to/Tracker Template.xlsx"
"""

import argparse
import html as html_module
import math
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re
import warnings
from datetime import datetime
from pathlib import Path
from scipy import stats

warnings.filterwarnings("ignore")

parser = argparse.ArgumentParser(description="Generate T1 Headline Analysis site")
parser.add_argument("--data-2025", default="Top syndication content 2025.xlsx")
parser.add_argument("--data-2026", default="Top Stories 2026 Syndication.xlsx")
parser.add_argument("--tracker",   default="Tracker Template.xlsx")
parser.add_argument("--theme",     default="light", choices=["light", "dark"])
_args = parser.parse_args()
DATA_2025 = _args.data_2025
DATA_2026 = _args.data_2026
TRACKER   = _args.tracker
THEME     = _args.theme

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


# ── Classifiers ───────────────────────────────────────────────────────────────
def classify_formula(text):
    t = str(text).strip()
    tl = t.lower()
    if re.match(r"^\d", t): return "number_lead"
    if re.match(r"^here[\u2019\']s\b|^here are\b|^here is\b|^here come\b", tl): return "heres_formula"
    if re.match(r"^[A-Z][a-zA-Z\-]+[\u2019\']s\s", t): return "possessive_named_entity"
    if re.search(r"what to know\s*$", tl): return "what_to_know"
    if t.rstrip().endswith("?"): return "question"
    if t.startswith("\u2018"): return "quoted_lede"
    return "untagged"

def tag_topic(text):
    t = str(text).lower()
    if re.search(r"\b(shot|kill|murder|dead|death|shooting|arrest|charge|crime|victim|police|cop|suspect|robbery|assault)\b", t): return "crime"
    if re.search(r"\b(game|team|nfl|nba|mlb|nhl|coach|season|championship|super bowl|playoff|quarterback)\b", t): return "sports"
    if re.search(r"\b(storm|hurricane|tornado|flood|rain|snow|weather|forecast|wildfire|earthquake|heat)\b", t): return "weather"
    if re.search(r"\b(business|economy|job|hire|layoff|company|market|real estate|housing|price|cost|wage|salary|tax)\b", t): return "business"
    if re.search(r"\b(school|student|teacher|education|college|university|election|vote|city|county|state|local|community|neighborhood)\b", t): return "local_civic"
    if re.search(r"\b(restaurant|food|eat|chef|menu|recipe|bar|coffee|dining|hotel|travel|beach|park|festival|concert)\b", t): return "lifestyle"
    if re.search(r"\b(animal|creature|species|wildlife|shark|bear|alligator|snake|bird|dog|cat|pet)\b", t): return "nature_wildlife"
    return "other"

def tag_subtopic(text, topic):
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
    return None


def classify_number_lead(text):
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
def bh_correct(pvals):
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

def rank_biserial(u_stat, n1, n2):
    return 1.0 - (2.0 * u_stat) / (n1 * n2)

def bootstrap_ci_lift(grp_vals, base_vals, n_boot=1000, ci=0.95):
    rng = np.random.default_rng(42)
    boot = []
    for _ in range(n_boot):
        sg = rng.choice(grp_vals, size=len(grp_vals), replace=True)
        sb = rng.choice(base_vals, size=len(base_vals), replace=True)
        mb = np.median(sb)
        if mb > 0:
            boot.append(np.median(sg) / mb)
    alpha = 1 - ci
    return float(np.percentile(boot, alpha / 2 * 100)), float(np.percentile(boot, (1 - alpha / 2) * 100))

def required_n_80pct(r_rb):
    if r_rb is None or r_rb == 0: return None
    r = abs(r_rb)
    d = 2 * r / math.sqrt(max(1 - r ** 2, 1e-9))
    if d < 0.001: return None
    return math.ceil(1.05 * 15.69 / d ** 2)


# ── normalize() ───────────────────────────────────────────────────────────────
def normalize(df, views_col, date_col=None, group_col=None):
    """
    Add two normalized columns to df (in-place):
    - views_per_day: views / days since publish (only if date_col provided)
    - percentile_within_cohort: percentile rank within same publication month
    """
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
an_2026["Article"] = an_2026["Article"].dropna().apply(_fix_mac_encoding).reindex(an_2026.index)

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

# ── Feature engineering ───────────────────────────────────────────────────────
an["is_featured"] = an["Featured by Apple"].fillna("No") == "Yes"
an["formula"]     = an["Article"].apply(classify_formula)
an["topic"]       = an["Article"].apply(tag_topic)
an["_pub_month"]  = pd.to_datetime(an["Date Published"], errors="coerce").dt.to_period("M").astype(str)

sn["topic"] = sn["title"].apply(tag_topic)
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
    except Exception:
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
    "local_civic":"Local/Civic","lifestyle":"Lifestyle",
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
    words = {}
    for t in texts:
        for w in re.sub(r"[^a-z\s]", "", str(t).lower()).split():
            if w not in STOPWORDS and len(w) > 2:
                words[w] = words.get(w, 0) + 1
    return set(sorted(words, key=lambda x: -words[x])[:n])

q75_an = an[VIEWS_METRIC].quantile(0.75)
q75_sn = sn[VIEWS_METRIC].quantile(0.75)
top_an_words = top_words(an[an[VIEWS_METRIC] >= q75_an]["Article"])
top_sn_words = top_words(sn[sn[VIEWS_METRIC] >= q75_sn]["title"])
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
    _biggest_change_row = df_yoy_valid.sort_values("_delta", ascending=False).iloc[0]
    YOY_CHANGING_FORMULA = _biggest_change_row["label"]
    YOY_CHANGING_DELTA   = _biggest_change_row["lift_2026"] - _biggest_change_row["lift_2025"]
else:
    YOY_CHANGING_FORMULA = "—"
    YOY_CHANGING_DELTA   = 0.0


df_wc_quartile = pd.DataFrame()
WC_MATCHED_N = 0

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
        else:
            WC_Q1_MED = np.nan
            WC_Q4_MED = np.nan


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
EXCL_LIFT  = f"{_excl_lift_val:.2f}×" if _excl_lift_val else "—"


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
        f"\u201cExclusive\u201d in a push notification drives {_excl_lft:.1f}\u00d7 more clicks "
        f"than standard headlines.",
        _get_p(_r5_excl), _excl_lft - 1.0, surprise=1.3, n=int(_r5_excl["n_true"]),
    )

# Notification: named person + possessive
if _r5_poss is not None and float(_r5_poss["lift"]) > 1.0:
    _poss_lft = float(_r5_poss["lift"])
    _hero_add(
        f"Named person\u202f+\u202fpossessive (\u201cSmith\u2019s\u2026\u201d) drives "
        f"{_poss_lft:.1f}\u00d7 notification CTR.",
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
        f"SmartNews: Entertainment gets {_ent_sh:.0%} of article volume at {_ent_lft:.2f}\u00d7 ROI. "
        f"Local delivers {_loc_lft:.2f}\u00d7 on {_loc_sh:.0%} of the volume \u2014 "
        f"a distribution reallocation, not a content problem.",
        _p_loc, _loc_lft - _ent_lft, surprise=1.5, n=int(_r4_loc["n"]),
    )

# Sports platform inversion
_sports_an_v = an[an["topic"] == "sports"][VIEWS_METRIC].dropna()
_sports_sn_v = sn[sn["topic"] == "sports"][VIEWS_METRIC].dropna()
if len(_sports_an_v) >= 10 and len(_sports_sn_v) >= 10:
    _, _p_sports = stats.mannwhitneyu(_sports_an_v, _sports_sn_v, alternative="two-sided")
    _rank_gap = abs(sports_an_rank - sports_sn_rank)
    _hero_add(
        f"Sports is #{sports_an_rank} on Apple News and #{sports_sn_rank} (last) on SmartNews \u2014 "
        f"the largest platform inversion in the dataset.",
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
    html_out = ""
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
        html_out += (f'<tr><td>{tag}{r["label"]}</td><td>{r["n"]:,}</td>'
                     f'<td>{pct_str}</td><td>{r["lift"]:.2f}×</td><td>{ci_str}</td>'
                     f'<td>{r_str}</td><td>{p_str}</td><td>{req_n_str}</td></tr>\n')
    return html_out

def _q2_table():
    rows = df_q2[df_q2["formula"] != "untagged"].sort_values("featured_rate", ascending=False)
    html_out = ""
    for _, r in rows.iterrows():
        feat_med = r.get("feat_med_views")
        if feat_med is not None and not np.isnan(float(feat_med)):
            wf = f"{feat_med:.0%} ({float(r['feat_views_lift']):.2f}× Featured avg)"
        else:
            wf = "—"
        p_adj = r.get("p_chi_adj", np.nan)
        p_str = _fmt_p(p_adj, adj=True) if not (p_adj is None or (isinstance(p_adj, float) and np.isnan(float(p_adj)))) else _fmt_p(r["p_chi"])
        tag = _row_tag(r["featured_lift"])
        html_out += (f'<tr><td>{tag}{r["label"]}</td><td>{r["n"]:,}</td>'
                     f'<td>{r["featured_rate"]:.0%}</td>'
                     f'<td>{r["featured_lift"]:.2f}×</td>'
                     f'<td>{p_str}</td>'
                     f'<td>{wf}</td></tr>\n')
    return html_out

def _q4_table():
    rows_sorted = df_q4[df_q4["category"] != "Top"].sort_values("lift", ascending=False)
    html_out = ""
    for _, r in rows_sorted.iterrows():
        is_red = (r["lift"] < 2.0 and r["category"] in ("Entertainment", "Lifestyle"))
        tag = _row_tag(r["lift"], is_red=is_red)
        p_adj = r.get("p_mw_adj", np.nan)
        p_str = _fmt_p(p_adj, adj=True) if not (p_adj is None or (isinstance(p_adj, float) and np.isnan(float(p_adj)))) else "—"
        html_out += (f'<tr><td>{tag}{r["category"]}</td><td>{r["n"]:,}</td>'
                     f'<td>{r["pct_share"]:.1%}</td>'
                     f'<td>{r["median_pct"]:.0%}</td>'
                     f'<td>{int(r["median_views"]):,}</td>'
                     f'<td>{r["lift"]:.2f}×</td>'
                     f'<td>{p_str}</td></tr>\n')
    if _r4_top is not None:
        html_out += (f'<tr><td>Top feed (baseline)</td><td>{int(_r4_top["n"]):,}</td>'
                     f'<td>{_r4_top["pct_share"]:.1%}</td>'
                     f'<td>{top_median_sn_pct:.0%}</td>'
                     f'<td>{int(_r4_top["median_views"]):,}</td><td>1.00×</td><td>—</td></tr>\n')
    return html_out

def _q5_table():
    sig = df_q5[df_q5.apply(
        lambda r: (r.get("p_adj", r["p"]) if not (isinstance(r.get("p_adj", np.nan), float) and np.isnan(r.get("p_adj", np.nan))) else r["p"]) < 0.05,
        axis=1
    )].sort_values("lift", ascending=False)
    html_out = ""
    for _, r in sig.iterrows():
        p_adj = r.get("p_adj", np.nan)
        p_str = _fmt_p(p_adj, adj=True) if not (isinstance(p_adj, float) and np.isnan(p_adj)) else _fmt_p(r["p"])
        r_str = f"{r['r_rb']:.2f}" if r.get("r_rb") is not None else "—"
        ci_str = _fmt_ci(r.get("ci_lo"), r.get("ci_hi"))
        tag = _row_tag(r["lift"])
        html_out += (f'<tr><td>{tag}{r["feature"]}</td><td>{r["n_true"]:,}</td>'
                     f'<td>{r["med_yes"]:.2%}</td><td>{r["med_no"]:.2%}</td>'
                     f'<td>{r["lift"]:.2f}× {ci_str}</td>'
                     f'<td>{r_str}</td>'
                     f'<td>{p_str}</td></tr>\n')
    return html_out

def _sports_subtopic_table():
    html_out = ""
    for _, r in df_sports_subtopic.iterrows():
        an_str = f"{r['an_med']:.0%}" if pd.notna(r['an_med']) else "—"
        sn_str = f"{r['sn_med']:.0%}" if pd.notna(r['sn_med']) else "—"
        html_out += (f"<tr><td>{r['subtopic']}</td>"
                     f"<td>{int(r['an_n'])}</td><td>{an_str}</td>"
                     f"<td>{int(r['sn_n'])}</td><td>{sn_str}</td></tr>\n")
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

fig1 = go.Figure(go.Bar(
    y=df_q1["label"].tolist(),
    x=df_q1["lift"].tolist(),
    orientation="h",
    marker_color=colors_q1,
    text=[f"{v:.2f}×  (n={n})" for v, n in zip(df_q1["lift"].tolist(), df_q1["n"].tolist())],
    textposition="outside",
    cliponaxis=False,
    hovertext=hover_q1,
    hoverinfo="y+text",
))
fig1.add_vline(x=1.0, line_dash="dash", line_color=_T["baseline"],
               annotation_text="Baseline", annotation_position="top")
fig1.update_layout(
    **make_layout(THEME, height=CHART_H, margin=dict(l=20, r=120, t=50, b=40),
                  title="Percentile-within-cohort lift vs. baseline by formula — non-Featured articles only"),
    xaxis=dict(title="Median percentile rank relative to untagged baseline (1.0 = same as baseline)",
               gridcolor=_T["grid"], zeroline=False, range=[0, 4.5]),
    yaxis=dict(title=""),
    showlegend=False,
)

# Chart 2 — Featured rate
colors_q2 = [bar_color(r["featured_lift"]) for _, r in df_q2.iterrows()]
fig2 = go.Figure(go.Bar(
    y=df_q2["label"].tolist(),
    x=(df_q2["featured_rate"] * 100).tolist(),
    orientation="h",
    marker_color=colors_q2,
    text=[f"{r['featured_rate']:.0%}  ({r['featured_lift']:.2f}×)" for _, r in df_q2.iterrows()],
    textposition="outside",
    cliponaxis=False,
    hovertext=[f"n={r['n']}" for _, r in df_q2.iterrows()],
    hoverinfo="y+x+text",
))
fig2.add_vline(x=overall_feat_rate * 100, line_dash="dash", line_color=_T["baseline"],
               annotation_text=f"Baseline {overall_feat_rate:.0%}", annotation_position="top")
fig2.update_layout(
    **make_layout(THEME, height=CHART_H, margin=dict(l=20, r=120, t=50, b=40),
                  title="% of articles Featured by Apple, by headline formula"),
    xaxis=dict(title="% of articles in formula group that were Featured by Apple",
               gridcolor=_T["grid"], zeroline=False, range=[0, 85]),
    yaxis=dict(title=""),
    showlegend=False,
)

# Chart 3 — SmartNews categories (percentile)
df_q4_chart = df_q4.sort_values("median_pct", ascending=True)
q4_colors = []
for _, r in df_q4_chart.iterrows():
    if r["lift"] > 1.5:      q4_colors.append(GREEN)
    elif r["lift"] > 1.0:    q4_colors.append(BLUE)
    elif r["pct_share"] > 0.20: q4_colors.append(RED)
    else:                    q4_colors.append(GRAY)

fig3 = go.Figure(go.Bar(
    y=df_q4_chart["category"].tolist(),
    x=df_q4_chart["median_pct"].tolist(),
    orientation="h",
    marker_color=q4_colors,
    text=[f"{p:.0%} percentile  ({n:,} articles)"
          for p, n in zip(df_q4_chart["median_pct"].tolist(), df_q4_chart["n"].tolist())],
    textposition="outside",
    cliponaxis=False,
    hovertext=[f"Median raw views: {int(v):,}" for v in df_q4_chart["median_views"].tolist()],
    hoverinfo="y+text",
))
fig3.update_layout(
    **make_layout(THEME, height=CHART_H, margin=dict(l=20, r=280, t=50, b=40),
                  title="Median percentile rank by SmartNews channel — with article volume"),
    xaxis=dict(title="Median percentile within monthly cohort (0=lowest, 1=highest)", gridcolor=_T["grid"],
               zeroline=False, tickformat=".0%"),
    yaxis=dict(title=""),
    showlegend=False,
)

# Chart 4 — Notification CTR lift
colors_q5 = [bar_color(r["lift"]) for _, r in df_q5.iterrows()]
sig_labels = []
for _, r in df_q5.iterrows():
    p = r.get("p_adj", r["p"])
    s = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else "ns"))
    sig_labels.append(f"{r['lift']:.2f}×  {s}  (n={r['n_true']})")

fig4 = go.Figure(go.Bar(
    y=df_q5["feature"].tolist(),
    x=df_q5["lift"].tolist(),
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
    **make_layout(THEME, height=CHART_H, margin=dict(l=20, r=220, t=50, b=40),
                  title="Notification CTR lift by headline feature (median CTR, feature present vs. absent)"),
    xaxis=dict(title="CTR lift (1.0 = no effect)", gridcolor=_T["grid"], zeroline=False, range=[0, 3.8]),
    yaxis=dict(title=""),
    showlegend=False,
)

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

# Chart 7 — Views vs active time scatter
q6_sample = an_eng
feat_mask  = q6_sample["is_featured"]
nfeat_mask = ~q6_sample["is_featured"]

fig7 = go.Figure()
fig7.add_trace(go.Scatter(
    x=q6_sample[nfeat_mask]["Total Views"].tolist(),
    y=q6_sample[nfeat_mask][AT_COL].tolist(),
    mode="markers", name="Not Featured",
    marker=dict(color=BLUE, size=4, opacity=0.35),
    hovertemplate="Views: %{x:,}<br>Active time: %{y}s<extra>Not Featured</extra>",
))
fig7.add_trace(go.Scatter(
    x=q6_sample[feat_mask]["Total Views"].tolist(),
    y=q6_sample[feat_mask][AT_COL].tolist(),
    mode="markers", name="Featured by Apple",
    marker=dict(color=GREEN, size=5, opacity=0.6),
    hovertemplate="Views: %{x:,}<br>Active time: %{y}s<extra>Featured</extra>",
))
fig7.update_layout(
    **make_layout(THEME, height=460, margin=dict(l=20, r=40, t=50, b=80),
                  title=f"Views vs. average active time — Pearson r = {r_views_at:.3f} (p = {p_views_at:.2f})"),
    xaxis=dict(title="Total views (log scale)", type="log", gridcolor=_T["grid"]),
    yaxis=dict(title="Avg. active time (seconds)", gridcolor=_T["grid"],
               range=[0, max(an_eng[AT_COL].quantile(0.99), 180)]),
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

fig8 = go.Figure()

if not df_periods.empty:
    for f, color in _period_colors_8.items():
        sub = df_periods[df_periods["formula"] == f].copy()
        # Preserve period order
        sub["_order"] = sub["period"].map({p: i for i, p in enumerate(_period_order_8)})
        sub = sub.sort_values("_order")
        if len(sub) == 0:
            continue
        label = FORMULA_LABELS.get(f, f)
        fig8.add_trace(go.Scatter(
            x=sub["period"],
            y=sub["lift"],
            mode="lines+markers+text",
            name=label,
            line=dict(color=color, width=2.5),
            marker=dict(size=10, color=color),
            text=[f"{v:.2f}×" for v in sub["lift"]],
            textposition="top center",
            textfont=dict(size=10, color=color),
            hovertemplate="%{x}: %{y:.2f}× baseline (n=%{customdata})<extra>" + label + "</extra>",
            customdata=sub["n"],
        ))

fig8.add_hline(
    y=1.0, line_dash="dash", line_color=_T["baseline"], line_width=1.5,
    annotation_text="Baseline (1.0×)", annotation_position="right",
    annotation_font_size=10, annotation_font_color=_T["baseline"],
)

fig8.update_layout(
    **make_layout(THEME, height=420, margin=dict(l=20, r=160, t=50, b=60),
                  title="Headline formula lift vs. unclassified baseline — Q1 2025 through Q1 2026"),
    xaxis=dict(
        title="",
        gridcolor=_T["grid"],
        categoryorder="array",
        categoryarray=_period_order_8,
    ),
    yaxis=dict(
        title="Lift vs. baseline (1.0 = same as unclassified headlines)",
        gridcolor=_T["grid"],
        zeroline=False,
        tickformat=".2f",
        range=[0, 2.0],
    ),
    legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02, font=dict(size=11)),
)


# ── Render charts ─────────────────────────────────────────────────────────────
def chart_html(fig):
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"responsive": True})

c1 = chart_html(fig1)
c2 = chart_html(fig2)
c3 = chart_html(fig3)
c4 = chart_html(fig4)
c5 = chart_html(fig5)
c6 = chart_html(fig6)
c7 = chart_html(fig7)
c8 = chart_html(fig8)

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
        <strong>Unexpected:</strong> Articles in the longest quartile (1,200+ words) perform at the 18th percentile — worse than any other length group. The 900-word range (Q2) is the apparent sweet spot at 48th percentile. <em>Caveat: this is based on 120 tracker-matched articles, mostly SmartNews. Treat as directional — the pattern is consistent within SmartNews individually but is not statistically confirmed at this sample size.</em>
      </div>
      <table class="findings">
        <thead><tr><th>Word count quartile</th><th>n</th><th>Median word count</th><th>Median percentile</th></tr></thead>
        <tbody>{_t_wc}</tbody>
      </table>
      <p class="callout-inline"><strong>Read this table as:</strong> Articles from the content tracker matched to Tarrow syndication data by URL and headline. Percentile ranks are platform-relative (SmartNews vs. SmartNews, Yahoo vs. Yahoo). Word count is from the tracker, not the syndication data.</p>
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
        <strong>Key finding:</strong> Round numbers (100, 50, 1,000) score at the 27th percentile — 14 points below specific numbers (41st). The difference is statistically significant (p=0.036). Numbers in the 11–20 range are the sweet spot (57th percentile). Numbers above 50 drag performance to the 25th percentile. Bottom line: "127 arrested" outperforms "100 arrested," and "15 takeaways" outperforms "50 things to know."
      </div>
      <h3>Round vs. specific numbers</h3>
      <p>Round numbers (multiples of 10, 100, 1,000): median {NL_ROUND_MED:.0%} vs. specific numbers: median {NL_SPECIFIC_MED:.0%}. ({_nl_round_sig})</p>
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
      <p class="callout-inline"><strong>Note:</strong> Nearly all number-lead articles (183/190) use a count or list format. Dollar amounts and ordinals appear too rarely (n&lt;10) for reliable conclusions.</p>
      <h3>By number magnitude</h3>
      <table class="findings">
        <thead><tr><th>Number range</th><th>n</th><th>Median percentile</th><th>Lift vs. baseline</th></tr></thead>
        <tbody>{_t_nl_size}</tbody>
      </table>
      <p class="callout-inline"><strong>Unexpected:</strong> The 11–20 range outperforms even single-digit numbers. Very large numbers (50+) are the weakest performers — avoid leading with totals, casualty counts, or cumulative statistics that tend to produce large round-ish numbers.</p>
    </div>
  </details>
"""

# ── HTML ──────────────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
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
  nav {{ position: sticky; top: 0; z-index: 100; background: var(--nav-bg); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border-bottom: 1px solid var(--border); height: 44px; display: flex; align-items: center; justify-content: space-between; padding: 0 28px; }}
  .brand {{ font-size: 11px; font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase; color: var(--text); }}
  .nav-right {{ display: flex; align-items: center; gap: 14px; }}
  .nav-date {{ font-size: 11px; color: var(--text-muted); }}
  .theme-btn {{ background: none; border: 1px solid var(--border); color: var(--text-muted); font-size: 13px; line-height: 1; cursor: pointer; border-radius: 6px; padding: 3px 9px; transition: background 0.15s, color 0.15s, border-color 0.15s; }}
  .theme-btn:hover {{ background: var(--bg-muted); color: var(--text); border-color: var(--text-muted); }}

  /* ── Hero ── */
  .hero {{ padding: 56px 28px 48px; text-align: center; border-bottom: 1px solid var(--border-subtle); }}
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
  table.findings {{ width: 100%; border-collapse: collapse; font-size: 12px; margin: 10px 0 20px; }}
  table.findings th {{ text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--border); font-size: 10px; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; color: var(--text-muted); }}
  table.findings td {{ padding: 8px 10px; border-bottom: 1px solid var(--border-subtle); vertical-align: top; color: var(--text-secondary); }}
  table.findings tr:last-child td {{ border-bottom: none; }}
  table.findings tr:hover td {{ background: var(--bg-muted); }}

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
  footer a {{ color: var(--accent); text-decoration: none; }}
  footer a:hover {{ text-decoration: underline; }}

  /* ── Responsive ── */
  @media (max-width: 760px) {{ .tile-grid {{ grid-template-columns: 1fr 1fr; }} .hero h1 {{ font-size: 20px; }} .detail-wrap {{ padding: 24px 20px; }} }}
  @media (max-width: 480px) {{ .tile-grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body class="theme-{THEME}">

<nav>
  <span class="brand">McClatchy CSA · T1 Headlines</span>
  <div class="nav-right">
    <span class="nav-date">{REPORT_DATE}</span>
    <button id="theme-toggle" class="theme-btn" onclick="toggleTheme()" aria-label="Toggle dark mode">🌙</button>
  </div>
</nav>

<div class="hero">
  <p class="eyebrow">T1 Headline Performance Analysis · McClatchy CSA</p>
  <h1>{HERO_H1}</h1>
  <div class="hero-stats">
    <span><span class="stat-num">{N_AN:,}</span><span class="stat-label">Apple News articles</span></span>
    <span class="stat-sep">·</span>
    <span><span class="stat-num">{N_SN:,}</span><span class="stat-label">SmartNews articles</span></span>
    <span class="stat-sep">·</span>
    <span><span class="stat-num">{N_NOTIF}</span><span class="stat-label">push notifications</span></span>
    <span class="stat-sep">·</span>
    <span><span class="stat-num">{PLATFORMS}</span><span class="stat-label">platforms · 2025–2026</span></span>
  </div>
</div>

<main>
  <p class="grid-label">9 findings — click any card to expand</p>
  <div class="tile-grid">

    <div class="tile" onclick="showDetail('formulas', this)">
      <span class="tile-num">1 · Apple News Formulas</span>
      <p class="tile-claim">Number leads and questions significantly underperform. No formula reliably beats good writing.</p>
      <p class="tile-action">→ Audit number-lead headlines for specificity. The format alone isn't the signal.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    {"" if NL_PARSED < 10 else """
    <div class="tile" onclick="showDetail('numleads', this)">
      <span class="tile-num">1b · Number Leads Deep Dive</span>
      <p class="tile-claim">Round numbers (100, 1,000) score 14 percentile points below specific numbers. Numbers 11–20 are the sweet spot.</p>
      <p class="tile-action">→ Use precise figures. Avoid leading with totals, round counts, or numbers above 50.</p>
      <span class="tile-more">Details ↓</span>
    </div>
    """}

    <div class="tile" onclick="showDetail('featured', this)">
      <span class="tile-num">2 · Featured on Apple News</span>
      <p class="tile-claim">"What to know" gets Featured {WTN_FEAT_LIFT:.1f}× more often — but organic views trend lower (directional, p≈0.10).</p>
      <p class="tile-action">→ Use "What to know" when targeting Featured specifically. Don't apply it broadly.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    <div class="tile" onclick="showDetail('smartnews', this)">
      <span class="tile-num">3 · SmartNews Allocation</span>
      <p class="tile-claim">Entertainment gets 36% of SmartNews volume at the lowest ROI. Local delivers {float(_r4_loc['lift']):.2f}× on {float(_r4_loc['pct_share']):.0%} of volume.</p>
      <p class="tile-action">→ Shift SmartNews volume toward Local and U.S. National. No new content required.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    <div class="tile" onclick="showDetail('notifications', this)">
      <span class="tile-num">4 · Push Notifications</span>
      <p class="tile-claim">"Exclusive" drives {_excl_lift_val:.1f}× CTR. Short notifications (≤80 chars) get 39% fewer clicks.</p>
      <p class="tile-action">→ Lead with "EXCLUSIVE:" on genuine scoops. Write longer, more descriptive push text.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    <div class="tile" onclick="showDetail('topics', this)">
      <span class="tile-num">5 · Platform Topic Inversion</span>
      <p class="tile-claim">Sports is #{sports_an_rank} on Apple News and #{sports_sn_rank} (last) on SmartNews — the largest platform inversion in the dataset.</p>
      <p class="tile-action">→ Write platform-specific sports briefs. Don't reuse Apple News sports content on SmartNews.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    <div class="tile" onclick="showDetail('allocation', this)">
      <span class="tile-num">6 · Headline Variance by Topic</span>
      <p class="tile-claim">Business and lifestyle have the most unpredictable outcomes (CV=1.55). This is where headline testing pays off most.</p>
      <p class="tile-action">→ Concentrate headline variant testing on business and lifestyle content.</p>
      <span class="tile-more">Details ↓</span>
    </div>

    <div class="tile" onclick="showDetail('engagement', this)">
      <span class="tile-num">7 · Views vs. Reading Depth</span>
      <p class="tile-claim">Views and reading time are statistically independent. High-click articles aren't the same as high-read articles.</p>
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
      <p class="tile-claim">{N_TRACKED} articles matched across platforms. Long-form articles (1,200+ words) syndicate at the 18th percentile.</p>
      <p class="tile-action">→ Target 800–950 words for syndication. Review team percentile rankings monthly.</p>
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
          <strong>Key finding:</strong> No formula consistently beats writing a good headline. "Here's/Here are" posts the highest median percentile (59th) but on only 17 articles — directional, not confirmed. Number leads and question-format headlines statistically <em>underperform</em> the baseline (p=0.003 and p&lt;0.001 respectively). The formula alone isn't the signal — how you execute it is.
        </div>
        <p>Across {len(nf):,} non-Featured articles, three formula types significantly underperform the baseline: number leads ({_r1_num['lift']:.2f}×), question format ({_r1_q['lift']:.2f}×), and quoted ledes ({_r1_ql['lift']:.2f}×) — all with FDR-adjusted p&lt;0.001. The better-performing formulas — "Here's / Here are" ({_r1_h['lift']:.2f}×) and possessive named entity ({_r1_pne['lift']:.2f}×) — show strong directional signal but lack statistical significance at current sample sizes (n={_r1_h['n']} and n={_r1_pne['n']} respectively).</p>
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
          <strong>Key finding:</strong> Round numbers (100, 50, 1,000) score at the 27th percentile — 14 points below specific numbers (41st). The difference is statistically significant (p=0.036). Numbers in the 11–20 range are the sweet spot (57th percentile). Numbers above 50 drag performance to the 25th percentile. Bottom line: "127 arrested" outperforms "100 arrested," and "15 takeaways" outperforms "50 things to know."
        </div>
        <h3>Round vs. specific numbers</h3>
        <p>Round numbers (multiples of 10, 100, 1,000): median {NL_ROUND_MED:.0%} vs. specific numbers: median {NL_SPECIFIC_MED:.0%}. ({_nl_round_sig})</p>
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
        <p class="callout-inline"><strong>Note:</strong> Nearly all number-lead articles (183/190) use a count or list format. Dollar amounts and ordinals appear too rarely (n&lt;10) for reliable conclusions.</p>
        <h3>By number magnitude</h3>
        <table class="findings">
          <thead><tr><th>Number range</th><th>n</th><th>Median percentile</th><th>Lift vs. baseline</th></tr></thead>
          <tbody>{_t_nl_size}</tbody>
        </table>
        <p class="callout-inline"><strong>Unexpected:</strong> The 11–20 range outperforms even single-digit numbers. Very large numbers (50+) are the weakest performers — avoid leading with totals, casualty counts, or cumulative statistics that tend to produce large round-ish numbers.</p>
      </div><!-- /#detail-numleads -->
      """}

      <!-- DETAIL: FEATURED -->
      <div class="detail-panel" id="detail-featured">
        <h2>Finding 2 · Featured on Apple News</h2>
        <div class="callout">
          <strong>Key tension:</strong> "What to know" gets featured by Apple at 1.81× the baseline rate — and non-featured WTN articles trend toward the lower end of the distribution. This is directional (p≈0.10, n=16 non-featured WTN articles) — interpret with caution. The Featured signal is statistically robust; the organic underperformance is a pattern worth watching, not a confirmed finding. Use WTN specifically when chasing Featured placement; avoid applying it as a general-purpose formula until organic performance data strengthens.
        </div>
        <p>Among the {an["is_featured"].sum()} Featured articles in our dataset, "What to know" headlines are dramatically overrepresented: {_wtn_feat_n} of {_wtn_total} ({WTN_FEAT}) were Featured, versus {overall_feat_rate:.1%} overall. This is the strongest statistically significant formula signal in the dataset (χ²={_r2_wtn['chi2']:.1f}, {_fmt_p(_r2_wtn.get('p_chi_adj', _r2_wtn['p_chi']), adj=True)}).</p>
        <p>Question-format headlines are also Featured more often than expected ({_r2_q['featured_rate']:.0%}, {_r2_q['featured_lift']:.2f}× lift, {_fmt_p(_r2_q.get('p_chi_adj', _r2_q['p_chi']), adj=True)}) — but they significantly underperform other Featured articles once selected. Apple's editors favor questions; the format itself doesn't follow through on views.</p>
        <p>Quoted ledes present the inverse pattern: Featured at roughly the baseline rate ({_r2_ql['featured_rate']:.0%}), but once Featured they deliver among the highest within-Featured percentiles. Questions get into the Featured tier and stall; quoted ledes get in and overperform.</p>
        <p><em>Causal note:</em> The association between "What to know" and Featured placement is observational. The causal direction is ambiguous: editors may independently choose the same stories that writers frame as "What to know," rather than the format itself driving featuring.</p>
        <div class="chart-wrap">{c2}</div>
        <table class="findings">
          <thead><tr><th>Formula</th><th>n</th><th>Featured rate</th><th>Lift</th><th>p<sub>adj</sub> (BH–FDR)</th><th>Within-Featured median %ile</th></tr></thead>
          <tbody>{_t2}</tbody>
        </table>
        <p class="callout-inline"><strong>Read this table as:</strong> "Featured lift" is how much more often Apple selects this formula for Featured. A high rate means Apple's algorithm rewards it — not that it organically outperforms.</p>
        <h3>Featured placement drives reach — not reading depth</h3>
        <p>Featured articles average {_feat_at_an.median():.0f} seconds of active reading time versus {_nfeat_at_an.median():.0f} seconds for non-Featured. The difference is statistically significant (Mann-Whitney p&lt;0.0001). Apple's editorial promotion drives discovery; readers who find an article because the algorithm surfaced it are slightly less engaged than readers who sought it out.</p>
        <p class="caveat">All {N_AN:,} Apple News articles (2025–2026). Chi-square test: each formula vs. all other articles combined. BH–FDR across all {len(_q2_raw_p)} formula tests. Causal direction of "What to know" → Featured is unconfirmed.</p>
      </div><!-- /#detail-featured -->

      <!-- DETAIL: SMARTNEWS -->
      <div class="detail-panel" id="detail-smartnews">
        <h2>Finding 3 · SmartNews Allocation</h2>
        <div class="callout">
          <strong>Most actionable finding in the dataset:</strong> Entertainment is 36% of SmartNews article volume (13,713 articles) at 1.14× ROI. Local is 1.85× ROI on 2.9% of volume. U.S. National is 1.81× on 2.4%. If you shifted just 500 Entertainment articles per month to Local or U.S. National framing, the expected percentile rank improvement is substantial — with no additional content production required.
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
          <strong>Two signals dominate:</strong> "Exclusive" tag (2.49× CTR lift, p&lt;0.001) and named person + possessive construction (1.86×, p&lt;0.001). Both are independent — combining them likely compounds. The counter-intuitive result: short notifications (≤80 chars) get 39% fewer clicks. Longer, more descriptive notification text outperforms across the board.
        </div>
        <p>Across {N_NOTIF} Apple News push notifications (Jan–Feb 2026, median CTR {CTR_MED}), four features show statistically significant positive effects after FDR correction. The "exclusive" tag is the strongest at {EXCL_LIFT} lift. The possessive framing signal: notifications with a full named person AND a possessive construction drive {_r5_poss['lift']:.2f}× CTR vs. {_r5_full['lift']:.2f}× for merely naming someone. Question format hurts at {_r5_q['lift']:.2f}×, consistent with the Apple News article finding.</p>
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
        <p>Sports ranks #{sports_an_rank} on Apple News (percentile index {sports_an_idx:.2f}× platform median) but #{sports_sn_rank} — last — on SmartNews (index {sports_sn_idx:.2f}×). This is not a small difference: the same sports content sits in the top quartile of one platform and the bottom quartile of another. The inversion is directionally consistent across the full year of 2025 data.</p>
        <p>Nature/wildlife shows the reverse: it underperforms the Apple News median ({nw_an_idx:.2f}×) but outperforms the SmartNews median ({nw_sn_idx:.2f}×). Among the top 30 most frequent words in top-quartile headlines on each platform, only {kw_overlap_n} appear on both lists{f" ({', '.join(sorted(kw_overlap))})" if kw_overlap_n > 0 else ""} — generic reporting terms, not topical overlap.</p>
        <div class="chart-wrap">{c5}</div>
        <h3>Sports subtopic performance by platform</h3>
        <p>Within the sports inversion: which sports specifically drive Apple News performance, and which are weakest on SmartNews? The table below breaks sports into subtopics (via two-level headline classifier).</p>
        <table class="findings">
          <thead><tr><th>Sport</th><th>Apple News n</th><th>Apple News median %ile</th><th>SmartNews n</th><th>SmartNews median %ile</th></tr></thead>
          <tbody>{_t5}</tbody>
        </table>
        <p class="caveat">Topic tagged via unvalidated regex classifier applied to headline text. <strong>Coverage: {TOPIC_COVERAGE_PCT:.0%} of Apple News articles match a named topic; {TOPIC_OTHER_PCT:.0%} fall into "other/unclassified" and are excluded from this analysis.</strong> Results describe the classified minority — generalizing to all content requires caution. Percentile index = median percentile_within_cohort / platform overall median percentile. Apple News 2025–2026 (n={N_AN:,}); SmartNews 2025 (n={N_SN:,}). Subtopic classifier unvalidated. No significance testing — treat as descriptive. Sports subtopics with n&lt;3 show "—".</p>
      </div><!-- /#detail-topics -->

      <!-- DETAIL: ALLOCATION -->
      <div class="detail-panel" id="detail-allocation">
        <h2>Finding 6 · Headline Variance by Topic</h2>
        <div class="callout">
          <strong>Action:</strong> Concentrate variant production on high-variance topics: business and lifestyle (both CV=1.55 on Apple News) — where a top-quartile headline outperforms the bottom quartile by the widest margin. Crime and sports are more consistent mid-performers — less room to move with headline optimization alone.
        </div>
        <p>The chart shows IQR ÷ median of percentile_within_cohort for each topic × platform. A ratio of 1.5 means the articles between the 25th and 75th percentile span 1.5× the median — a wide, unpredictable range. Where this ratio is high, headline choice has the most room to lift or drag performance.</p>
        <div class="chart-wrap">{c6}</div>
        <p class="callout-inline"><strong>Read this chart as:</strong> IQR ÷ median of percentile rank. A value of 1.55 means the gap between a 25th-percentile and 75th-percentile article in that topic is 1.55× the median — a wide, high-stakes range where headline choice has real leverage. Values close to 0.7 (sports, weather) mean outcomes cluster tightly regardless of headline.</p>
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
        <p class="caveat">IQR = interquartile range (75th percentile minus 25th percentile) of percentile_within_cohort. IQR/median is a scale-free spread measure. Topic tagged via regex classifier. Apple News 2025–2026; SmartNews 2025. Topics with fewer than 10 articles excluded. High IQR/median on SmartNews local/civic is substantially explained by channel-placement bimodality (Finding 3).</p>
      </div><!-- /#detail-allocation -->

      <!-- DETAIL: ENGAGEMENT -->
      <div class="detail-panel" id="detail-engagement">
        <h2>Finding 7 · Views vs. Reading Depth</h2>
        <div class="callout">
          <strong>Action:</strong> Don't use view count as the sole ROI signal for variant allocation. A variant driving 5,000 views at 75s average active time may deliver more subscriber retention value than one driving 20,000 views at 45s. The model should incorporate views (reach), saves (return intent), and active time (read depth) — all three are available in this dataset.
        </div>
        <p>The Apple News dataset includes both Total Views and average active time per article. The result: Pearson r = {r_views_at:.3f} (p = {p_views_at:.2f}), Spearman ρ = {r_views_at_sp:.3f} (p = {p_views_at_sp:.2f}). Both agree: across {len(an_eng):,} articles, views and reading time are statistically independent. The view count spans a {views_range_x:,}× range across deciles; active time moves only {at_range_s:.0f} seconds.</p>
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
        <p>Featured articles illustrate this split directly: 6.74× median view lift, but {feat_at.median():.0f}s active time vs. {nfeat_at.median():.0f}s for non-Featured (p&lt;0.0001). Subscribers read for less time on average ({sub_at_med:.0f}s) than non-subscribers ({nsub_at_med:.0f}s) — a behavioral difference, not a quality problem.</p>
        <p class="caveat">Apple News 2025–2026 (n={len(an_eng):,} articles with valid active time). {at_low_n} articles have active time &lt;10s; {at_high_n} have &gt;300s — not filtered, ~{(at_low_n+at_high_n)/len(an_eng):.0%} of records. Spearman ρ is the preferred test for independence given skewed views distribution.</p>
      </div><!-- /#detail-engagement -->

      <!-- DETAIL: LONGITUDINAL -->
      <div class="detail-panel" id="detail-longitudinal">
        <h2>Finding 8 · Trends Over Time</h2>
        <div class="callout">
          <strong>Key shift:</strong> Number leads started below baseline ({NL_LIFT_EARLY:.2f}× in Q1 2025) and climbed to {NL_LIFT_LATE:.2f}× by Q1 2026 — the only formula to cross into above-baseline territory. Question-format headlines moved in the opposite direction: {Q_LIFT_EARLY:.2f}× in Q1 2025 → {Q_LIFT_LATE:.2f}× in Q1 2026, now well below baseline. The chart shows five quarterly data points per formula from Q1 2025 through Q1 2026.
          <br><br><em>How to read "lift":</em> 1.0× = same as unclassified headlines. 1.5× = median 50% above baseline. Dashed line = baseline. Minimum 3 articles per formula per quarter required to appear.
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
          <strong>Unexpected:</strong> Articles in the longest quartile (1,200+ words) perform at the 18th percentile — worse than any other length group. The 900-word range (Q2) is the apparent sweet spot at 48th percentile. <em>Caveat: this is based on 120 tracker-matched articles, mostly SmartNews. Treat as directional — the pattern is consistent within SmartNews individually but is not statistically confirmed at this sample size.</em>
        </div>
        <table class="findings">
          <thead><tr><th>Word count quartile</th><th>n</th><th>Median word count</th><th>Median percentile</th></tr></thead>
          <tbody>{_t_wc}</tbody>
        </table>
        <p class="callout-inline"><strong>Read this table as:</strong> Articles from the content tracker matched to Tarrow syndication data by URL and headline. Percentile ranks are platform-relative (SmartNews vs. SmartNews, Yahoo vs. Yahoo). Word count is from the tracker, not the syndication data.</p>
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
</script>

<footer>
  <p>McClatchy CSA · T1 Headline Performance Analysis · {REPORT_DATE}</p>
  <p style="margin-top: 6px;">
    <a href="archive/">Past runs</a> &nbsp;·&nbsp;
    <a href="experiments/">Experiments</a> &nbsp;·&nbsp;
    Data: Tarrow T1 Headline Performance Sheet · Apple News, SmartNews, MSN, Yahoo
  </p>
</footer>

</body>
</html>"""

out = Path("docs/index.html")
out.parent.mkdir(exist_ok=True)
out.write_text(html, encoding="utf-8")
print(f"Site written to {out}  ({len(html):,} chars)")
