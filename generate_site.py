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
_args = parser.parse_args()
DATA_2025 = _args.data_2025
DATA_2026 = _args.data_2026
TRACKER   = _args.tracker

REFERENCE_DATE = pd.Timestamp.today().normalize()

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY   = "#0f172a"
BLUE   = "#2563eb"
GREEN  = "#16a34a"
RED    = "#dc2626"
AMBER  = "#d97706"
GRAY   = "#64748b"
LIGHT  = "#f8fafc"
BORDER = "#e2e8f0"


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


# ── Longitudinal: monthly median percentile by formula ────────────────────────
print("Computing longitudinal…")
an["_pub_dt"] = pd.to_datetime(an["Date Published"], errors="coerce")
an["_month_str"] = an["_pub_dt"].dt.to_period("M").astype(str)

_LONG_FORMULAS = ["heres_formula", "what_to_know", "number_lead", "question", "possessive_named_entity"]
long_rows = []
for month in sorted(an["_month_str"].dropna().unique()):
    for f in _LONG_FORMULAS:
        sub = an[(an["_month_str"] == month) & (an["formula"] == f)][VIEWS_METRIC].dropna()
        if len(sub) >= 3:
            long_rows.append(dict(month=month, formula=f, med_pct=sub.median(), n=len(sub)))

df_long = pd.DataFrame(long_rows)


# ── YoY: Jan-Feb 2025 vs Jan-Feb 2026 ────────────────────────────────────────
print("Computing YoY…")
an_2025_jf = an_2025_norm[pd.to_datetime(an_2025_norm["Date Published"], errors="coerce").dt.month.isin([1, 2])].copy()
an_2026_jf = an_2026_norm.copy()

yoy_rows = []
for f, label in FORMULA_LABELS.items():
    g25 = an_2025_jf[an_2025_jf["formula"] == f]
    g26 = an_2026_jf[an_2026_jf["formula"] == f]
    yoy_rows.append(dict(
        formula=f, label=label,
        n_2025=len(g25), n_2026=len(g26),
        feat_2025=g25["is_featured"].mean() if len(g25) > 0 else np.nan,
        feat_2026=g26["is_featured"].mean() if len(g26) > 0 else np.nan,
        pct_2025=g25[VIEWS_METRIC].median() if len(g25) >= 3 else np.nan,
        pct_2026=g26[VIEWS_METRIC].median() if len(g26) >= 3 else np.nan,
    ))
df_yoy = pd.DataFrame(yoy_rows)

# Formula with biggest change YoY
df_yoy_valid = df_yoy.dropna(subset=["pct_2025", "pct_2026"])
if len(df_yoy_valid) > 0:
    df_yoy_valid = df_yoy_valid.copy()
    df_yoy_valid["_delta"] = (df_yoy_valid["pct_2026"] - df_yoy_valid["pct_2025"]).abs()
    _biggest_change_row = df_yoy_valid.sort_values("_delta", ascending=False).iloc[0]
    YOY_CHANGING_FORMULA = _biggest_change_row["label"]
    YOY_CHANGING_DELTA   = _biggest_change_row["pct_2026"] - _biggest_change_row["pct_2025"]
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
        pct25 = f"{r['pct_2025']:.0%}" if pd.notna(r['pct_2025']) else "—"
        pct26 = f"{r['pct_2026']:.0%}" if pd.notna(r['pct_2026']) else "—"
        fr25  = f"{r['feat_2025']:.0%}" if pd.notna(r['feat_2025']) else "—"
        fr26  = f"{r['feat_2026']:.0%}" if pd.notna(r['feat_2026']) else "—"
        html_out += (f"<tr><td>{r['label']}</td>"
                     f"<td>{int(r['n_2025'])}</td><td>{fr25}</td><td>{pct25}</td>"
                     f"<td>{int(r['n_2026'])}</td><td>{fr26}</td><td>{pct26}</td></tr>\n")
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
PLOTLY_LAYOUT = dict(
    paper_bgcolor="white",
    plot_bgcolor="white",
    font=dict(family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif",
              size=12, color=NAVY),
    margin=dict(l=20, r=120, t=50, b=40),
    height=CHART_H,
)

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
    hovertext=hover_q1,
    hoverinfo="y+text",
))
fig1.add_vline(x=1.0, line_dash="dash", line_color=GRAY,
               annotation_text="Baseline", annotation_position="top")
fig1.update_layout(
    **PLOTLY_LAYOUT,
    title=dict(text="Percentile-within-cohort lift vs. baseline by formula — non-Featured articles only",
               font=dict(size=13, color=NAVY), x=0),
    xaxis=dict(title="Median percentile rank relative to untagged baseline (1.0 = same as baseline)",
               gridcolor=BORDER, zeroline=False, range=[0, 4.5]),
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
    hovertext=[f"n={r['n']}" for _, r in df_q2.iterrows()],
    hoverinfo="y+x+text",
))
fig2.add_vline(x=overall_feat_rate * 100, line_dash="dash", line_color=GRAY,
               annotation_text=f"Baseline {overall_feat_rate:.0%}", annotation_position="top")
fig2.update_layout(
    **PLOTLY_LAYOUT,
    title=dict(text="% of articles Featured by Apple, by headline formula",
               font=dict(size=13, color=NAVY), x=0),
    xaxis=dict(title="% of articles in formula group that were Featured by Apple",
               gridcolor=BORDER, zeroline=False, range=[0, 85]),
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
    hovertext=[f"Median raw views: {int(v):,}" for v in df_q4_chart["median_views"].tolist()],
    hoverinfo="y+text",
))
fig3.update_layout(
    **{k: v for k, v in PLOTLY_LAYOUT.items() if k != "margin"},
    title=dict(text="Median percentile rank by SmartNews channel — with article volume",
               font=dict(size=13, color=NAVY), x=0),
    xaxis=dict(title="Median percentile within monthly cohort (0=lowest, 1=highest)", gridcolor=BORDER,
               zeroline=False, tickformat=".0%"),
    yaxis=dict(title=""),
    showlegend=False,
    margin=dict(l=20, r=280, t=50, b=40),
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
    hovertext=[f"CTR present: {r['med_yes']*100:.2f}%  |  CTR absent: {r['med_no']*100:.2f}%"
               for _, r in df_q5.iterrows()],
    hoverinfo="y+text",
))
fig4.add_vline(x=1.0, line_dash="dash", line_color=GRAY,
               annotation_text="No effect", annotation_position="top")
fig4.update_layout(
    **{k: v for k, v in PLOTLY_LAYOUT.items() if k != "margin"},
    title=dict(text="Notification CTR lift by headline feature (median CTR, feature present vs. absent)",
               font=dict(size=13, color=NAVY), x=0),
    xaxis=dict(title="CTR lift (1.0 = no effect)", gridcolor=BORDER, zeroline=False, range=[0, 3.8]),
    yaxis=dict(title=""),
    showlegend=False,
    margin=dict(l=20, r=220, t=50, b=40),
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
fig5.add_vline(x=1.0, line_dash="dash", line_color=GRAY,
               annotation_text="Platform median", annotation_position="top")
fig5.update_layout(
    **{k: v for k, v in PLOTLY_LAYOUT.items() if k not in ("height", "margin")},
    title=dict(text="Topic performance by platform — percentile rank vs. platform median",
               font=dict(size=13, color=NAVY), x=0),
    barmode="group",
    xaxis=dict(title="Percentile index (1.0 = platform median)", gridcolor=BORDER, zeroline=False),
    yaxis=dict(title=""),
    legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
    height=480,
    margin=dict(l=20, r=40, t=50, b=80),
)

# Chart 6 — Variance (IQR/median of percentile)
fig6 = go.Figure()
fig6.add_trace(go.Bar(
    y=df_var["label"].tolist(), x=df_var["an_cv"].tolist(),
    name="Apple News", orientation="h",
    marker_color=BLUE, opacity=0.85,
    text=[f"{v:.1f}×  (n={n:,})" for v, n in zip(df_var["an_cv"].tolist(), df_var["an_n"].tolist())],
    textposition="outside",
    hovertemplate="<b>%{y}</b><br>Apple News IQR/median: %{x:.2f}<extra></extra>",
))
fig6.add_trace(go.Bar(
    y=df_var["label"].tolist(), x=df_var["sn_cv"].tolist(),
    name="SmartNews", orientation="h",
    marker_color=GREEN, opacity=0.85,
    text=[f"{v:.1f}×  (n={n:,})" for v, n in zip(df_var["sn_cv"].tolist(), df_var["sn_n"].tolist())],
    textposition="outside",
    hovertemplate="<b>%{y}</b><br>SmartNews IQR/median: %{x:.2f}<extra></extra>",
))
fig6.update_layout(
    **{k: v for k, v in PLOTLY_LAYOUT.items() if k not in ("height", "margin")},
    title=dict(text="Outcome spread by topic — where headline choice has the most room to move performance",
               font=dict(size=13, color=NAVY), x=0),
    barmode="group",
    xaxis=dict(title="IQR ÷ median percentile (higher = wider spread between top and bottom articles)",
               gridcolor=BORDER, zeroline=False),
    yaxis=dict(title=""),
    legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
    height=480,
    margin=dict(l=20, r=140, t=50, b=80),
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
    **{k: v for k, v in PLOTLY_LAYOUT.items() if k not in ("height", "margin")},
    title=dict(text=f"Views vs. average active time — Pearson r = {r_views_at:.3f} (p = {p_views_at:.2f})",
               font=dict(size=13, color=NAVY), x=0),
    xaxis=dict(title="Total views (log scale)", type="log", gridcolor=BORDER),
    yaxis=dict(title="Avg. active time (seconds)", gridcolor=BORDER,
               range=[0, max(an_eng[AT_COL].quantile(0.99), 180)]),
    legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
    height=460,
    margin=dict(l=20, r=40, t=50, b=80),
)

# Chart 8 — Longitudinal: monthly median percentile by formula
FORMULA_COLORS = {
    "heres_formula":           BLUE,
    "what_to_know":            GREEN,
    "number_lead":             RED,
    "question":                AMBER,
    "possessive_named_entity": NAVY,
}
FORMULA_DISPLAY = {
    "heres_formula":           "Here's / Here are",
    "what_to_know":            "What to know",
    "number_lead":             "Number lead",
    "question":                "Question",
    "possessive_named_entity": "Possessive named entity",
}

# ── Fig 8: Longitudinal — monthly formula trend ────────────────────────────────
fig8 = go.Figure()
_long_colors = {
    "heres_formula":           BLUE,
    "what_to_know":            GREEN,
    "number_lead":             AMBER,
    "question":                RED,
    "possessive_named_entity": NAVY,
}

if not df_long.empty:
    df_long_sorted = df_long.sort_values("month")
    # Split at year boundary
    df_long_2025 = df_long_sorted[df_long_sorted["month"] < "2026"].copy()
    df_long_2026 = df_long_sorted[df_long_sorted["month"] >= "2026"].copy()

    for f, color in _long_colors.items():
        label = FORMULA_LABELS.get(f, f)
        d25 = df_long_2025[df_long_2025["formula"] == f].sort_values("month")
        d26 = df_long_2026[df_long_2026["formula"] == f].sort_values("month")

        if len(d25) == 0 and len(d26) == 0:
            continue

        # 2025 trace — solid line
        if len(d25) > 0:
            fig8.add_trace(go.Scatter(
                x=d25["month"], y=d25["med_pct"],
                mode="lines+markers",
                name=label,
                line=dict(color=color, width=2.5),
                marker=dict(size=7, color=color),
                legendgroup=f,
                hovertemplate="%{x}: %{y:.0%} (%{customdata} articles)<extra>" + label + "</extra>",
                customdata=d25["n"],
            ))

        # 2026 trace — dotted thicker line; connect from last 2025 point
        if len(d26) > 0:
            # Include last 2025 point as bridge if it exists
            bridge_rows = d25.tail(1) if len(d25) > 0 else pd.DataFrame()
            d26_ext = pd.concat([bridge_rows, d26]).sort_values("month")
            fig8.add_trace(go.Scatter(
                x=d26_ext["month"], y=d26_ext["med_pct"],
                mode="lines+markers",
                name=label + " (2026)",
                line=dict(color=color, width=3.5, dash="dot"),
                marker=dict(size=9, color=color, symbol="circle-open"),
                legendgroup=f,
                showlegend=False,
                hovertemplate="%{x}: %{y:.0%} (%{customdata} articles)<extra>" + label + " 2026</extra>",
                customdata=d26_ext["n"],
            ))

    # Shade 2026 region
    _first_2026 = df_long_sorted[df_long_sorted["month"] >= "2026"]["month"].min() if not df_long_2026.empty else None
    if _first_2026:
        fig8.add_vrect(
            x0=_first_2026, x1=df_long_sorted["month"].max(),
            fillcolor="rgba(37,99,235,0.06)", line_width=0,
            annotation_text="2026 (dotted)", annotation_position="top left",
            annotation_font_size=10, annotation_font_color=BLUE,
        )

fig8.update_layout(
    title=dict(text="Formula performance trend — monthly percentile rank", font=dict(size=15, color=NAVY), x=0.01, xanchor="left"),
    xaxis=dict(title="", gridcolor=BORDER, tickangle=-30),
    yaxis=dict(title="Percentile vs. same-month articles", tickformat=".0%", range=[0,1]),
    legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5, font=dict(size=11)),
    height=500,
    margin=dict(l=20, r=40, t=50, b=110),
    plot_bgcolor=LIGHT, paper_bgcolor="white",
    font=dict(color=NAVY),
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
      <table class="findings">
        <thead><tr><th>Word count quartile</th><th>n</th><th>Median word count</th><th>Median percentile</th></tr></thead>
        <tbody>{_t_wc}</tbody>
      </table>
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
        <strong>Context:</strong> {NL_PARSED} of {NL_TOTAL} number-lead headlines parsed. Baseline = all non-number-lead Apple News articles (n={len(nl_base_all):,}).
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
      <h3>By number magnitude</h3>
      <table class="findings">
        <thead><tr><th>Number range</th><th>n</th><th>Median percentile</th><th>Lift vs. baseline</th></tr></thead>
        <tbody>{_t_nl_size}</tbody>
      </table>
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
  :root {{
    --navy:   {NAVY};
    --blue:   {BLUE};
    --green:  {GREEN};
    --red:    {RED};
    --amber:  {AMBER};
    --gray:   {GRAY};
    --light:  {LIGHT};
    --border: #e2e8f0;
    --text:   {NAVY};
    --sub:    #4b5563;
    --bg:     #f8fafc;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    color: var(--text); background: var(--bg); font-size: 15px; line-height: 1.7;
    -webkit-font-smoothing: antialiased;
  }}

  /* NAV */
  nav {{
    position: sticky; top: 0; z-index: 100;
    background: rgba(15,23,42,0.96);
    backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
    padding: 0 2rem;
    display: flex; align-items: center; gap: 1.5rem; height: 46px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    overflow-x: auto;
  }}
  nav::-webkit-scrollbar {{ display: none; }}
  nav .brand {{
    color: #fff; font-weight: 700; font-size: 0.72rem;
    letter-spacing: 0.1em; text-transform: uppercase;
    white-space: nowrap; flex-shrink: 0;
  }}
  nav .nav-links {{ display: flex; gap: 1rem; align-items: center; }}
  nav a {{
    color: rgba(255,255,255,0.38); text-decoration: none;
    font-size: 0.73rem; white-space: nowrap;
    transition: color 0.15s; letter-spacing: 0.01em;
  }}
  nav a:hover {{ color: rgba(255,255,255,0.82); }}
  nav .spacer {{ flex: 1; min-width: 1rem; }}
  nav .date {{
    color: rgba(255,255,255,0.22); font-size: 0.68rem;
    white-space: nowrap; flex-shrink: 0; letter-spacing: 0.02em;
  }}

  /* HERO */
  .hero {{
    background: linear-gradient(150deg, #0f172a 0%, #1a2744 100%);
    color: #fff; padding: 5.5rem 2rem 5rem; text-align: center;
  }}
  .hero .eyebrow {{
    text-transform: uppercase; letter-spacing: 0.16em; font-size: 0.6rem;
    color: rgba(255,255,255,0.28); margin-bottom: 1.4rem; font-weight: 600;
  }}
  .hero h1 {{
    font-family: Georgia, "Times New Roman", serif;
    font-size: 2.35rem; font-weight: 700; line-height: 1.22;
    max-width: 700px; margin: 0 auto 1rem; letter-spacing: -0.015em;
  }}
  .hero .sub {{
    font-size: 0.85rem; color: rgba(255,255,255,0.32);
    max-width: 540px; margin: 0 auto 3.5rem; letter-spacing: 0.01em;
  }}
  .hero .meta {{
    display: inline-flex; flex-wrap: wrap; justify-content: center;
    border: 1px solid rgba(255,255,255,0.1); border-radius: 12px;
    overflow: hidden; background: rgba(255,255,255,0.03);
  }}
  .hero .meta-item {{
    text-align: center; padding: 1.4rem 2.5rem;
    border-right: 1px solid rgba(255,255,255,0.08);
  }}
  .hero .meta-item:last-child {{ border-right: none; }}
  .hero .meta-item .num {{
    font-size: 2.4rem; font-weight: 700; color: #fff;
    display: block; letter-spacing: -0.035em; line-height: 1;
    margin-bottom: 0.45rem;
  }}
  .hero .meta-item .label {{
    font-size: 0.6rem; color: rgba(255,255,255,0.28);
    text-transform: uppercase; letter-spacing: 0.1em; display: block; line-height: 1.5;
  }}

  /* LAYOUT */
  .container {{ max-width: 840px; margin: 0 auto; padding: 0 2rem; }}

  /* TYPOGRAPHY */
  .section-label {{
    text-transform: uppercase; letter-spacing: 0.14em; font-size: 0.6rem;
    color: var(--blue); font-weight: 700; margin-bottom: 0.5rem; display: block;
  }}
  h2 {{
    font-size: 1.45rem; font-weight: 700; line-height: 1.3;
    letter-spacing: -0.02em; color: var(--text);
  }}
  h3 {{
    font-size: 0.65rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--gray); margin: 2rem 0 0.6rem;
  }}
  p {{ color: var(--sub); margin-bottom: 0.9rem; font-size: 0.9375rem; }}
  p:last-child {{ margin-bottom: 0; }}

  /* CHART */
  .chart-wrap {{
    margin: 1.5rem 0; border-radius: 10px; overflow: hidden;
    background: #fff; padding: 0.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.05);
  }}

  /* CALLOUT */
  .callout {{
    background: #eff6ff; border: 1px solid #bfdbfe;
    padding: 1rem 1.25rem; border-radius: 8px;
    margin: 1.5rem 0; font-size: 0.875rem; color: var(--text); line-height: 1.65;
  }}
  .callout strong {{ color: #1e40af; }}
  .callout em {{ color: var(--sub); }}

  /* TAGS */
  .tag {{
    display: inline-block; font-size: 0.6rem; font-weight: 700;
    padding: 1px 5px; border-radius: 3px; margin-right: 5px; vertical-align: middle;
  }}
  .tag-blue  {{ background: #eff6ff; color: #1d4ed8; }}
  .tag-green {{ background: #f0fdf4; color: #15803d; }}
  .tag-red   {{ background: #fff1f2; color: #be123c; }}
  .tag-amber {{ background: #fffbeb; color: #b45309; }}

  /* FINDINGS TABLE */
  .findings {{
    width: 100%; border-collapse: collapse; font-size: 0.84rem; margin: 1.25rem 0;
    background: #fff; border-radius: 8px; overflow: hidden;
    box-shadow: 0 0 0 1px var(--border), 0 1px 3px rgba(0,0,0,0.04);
  }}
  .findings th {{
    text-align: left; padding: 8px 12px; background: #f8fafc;
    color: var(--gray); font-weight: 600; font-size: 0.62rem;
    text-transform: uppercase; letter-spacing: 0.08em;
    border-bottom: 1px solid var(--border);
  }}
  .findings td {{
    padding: 8px 12px; border-bottom: 1px solid #f1f5f9;
    vertical-align: top; color: var(--sub);
  }}
  .findings tr:last-child td {{ border-bottom: none; }}
  .findings tr:hover td {{ background: #fafbfd; }}
  .findings td:nth-child(n+2) {{ font-variant-numeric: tabular-nums; }}

  /* CAVEAT */
  .caveat {{ font-size: 0.74rem; color: #94a3b8; margin-top: 0.75rem; line-height: 1.6; }}

  /* FINDING CARDS */
  .finding-card {{ border-bottom: 1px solid var(--border); }}
  .finding-card:first-of-type {{ border-top: 1px solid var(--border); margin-top: 2.5rem; }}
  .finding-card:last-of-type {{ border-bottom: 1px solid var(--border); margin-bottom: 3rem; }}
  .finding-card > summary {{
    list-style: none; cursor: pointer;
    padding: 1.75rem 0;
    display: grid; grid-template-columns: 1.1rem 1fr;
    gap: 0 0.85rem; align-items: start; user-select: none;
  }}
  .finding-card > summary::-webkit-details-marker {{ display: none; }}
  .finding-card > summary::marker {{ display: none; }}
  .finding-chevron {{
    margin-top: 0.4rem; color: #cbd5e1; font-size: 0.55rem;
    transition: transform 0.2s ease, color 0.15s; display: inline-block;
  }}
  .finding-card[open] > summary .finding-chevron {{
    transform: rotate(90deg); color: var(--blue);
  }}
  .finding-card > summary:hover .finding-chevron {{ color: var(--blue); }}
  .finding-card > summary h2 {{ transition: color 0.15s; }}
  .finding-card > summary:hover h2 {{ color: var(--blue); }}
  .finding-body {{ padding: 0 0 2.5rem 1.95rem; }}
  .finding-body > .callout:first-child {{ margin-top: 0; }}

  /* NAV TOGGLE */
  .nav-toggle {{
    background: transparent; border: 1px solid rgba(255,255,255,0.16);
    color: rgba(255,255,255,0.42); border-radius: 4px;
    padding: 3px 10px; font-size: 0.66rem; cursor: pointer;
    white-space: nowrap; flex-shrink: 0; font-family: inherit;
    letter-spacing: 0.04em; transition: all 0.15s;
  }}
  .nav-toggle:hover {{ border-color: rgba(255,255,255,0.35); color: rgba(255,255,255,0.8); }}

  /* EXAMPLE LISTS */
  .example-cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin: 1rem 0; }}
  .example-list {{ background: #fff; border-radius: 8px; padding: 0.75rem 1rem;
    box-shadow: 0 0 0 1px var(--border); }}
  .example-list h4 {{ font-size: 0.6rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.08em; color: var(--gray); margin-bottom: 0.5rem; }}
  .example-list ul {{ padding-left: 1.2rem; font-size: 0.82rem; color: var(--sub); }}
  .example-list li {{ margin-bottom: 0.35rem; }}
  .example-top h4 {{ color: #15803d; }}
  .example-bot h4 {{ color: #be123c; }}

  /* FOOTER */
  footer {{
    padding: 3.5rem 0; text-align: center; color: #94a3b8;
    font-size: 0.75rem; border-top: 1px solid var(--border);
    background: #fff; margin-top: 1rem;
    letter-spacing: 0.01em;
  }}
  footer a {{ color: var(--blue); text-decoration: none; }}
  footer a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>

<nav>
  <span class="brand">McClatchy CSA · T1 Headlines</span>
  <div class="nav-links">
    <a href="#formulas">Formulas</a>
    <a href="#featuring">Featuring</a>
    <a href="#smartnews">SmartNews</a>
    <a href="#notifications">Notifications</a>
    <a href="#topics">Topics</a>
    <a href="#allocation">Allocation</a>
    <a href="#engagement">Engagement</a>
    <a href="#trends">Trends</a>
    {"<a href='#numleads'>Number leads</a>" if NL_PARSED >= 10 else ""}
    {"<a href='#team'>Team</a>" if HAS_TRACKER and N_TRACKED > 0 else ""}
  </div>
  <span class="spacer"></span>
  <button class="nav-toggle" id="expand-btn" onclick="toggleAll()">Expand all</button>
  <span class="date">{REPORT_DATE}</span>
</nav>

<div class="hero">
  <p class="eyebrow">T1 Headline Performance Analysis · McClatchy CSA</p>
  <h1>One headline phrase doubles your chance of being Featured on Apple News. Sports is top-3 on Apple News and dead last on SmartNews.</h1>
  <p class="sub">{N_AN:,} Apple News articles · {N_SN:,} SmartNews articles · {N_NOTIF} push notifications · {PLATFORMS} platforms · 2025–2026</p>
  <div class="meta">
    <div class="meta-item"><span class="num">{WTN_FEAT}</span><span class="label">Featured rate for "What to know" headlines</span></div>
    <div class="meta-item"><span class="num">{LOCAL_LIFT}</span><span class="label">SmartNews Local percentile lift vs. Top feed</span></div>
    <div class="meta-item"><span class="num">{EXCL_LIFT}</span><span class="label">CTR lift for "exclusive" in push notifications</span></div>
  </div>
</div>

<div class="container">

  <!-- FORMULAS -->
  <details id="formulas" class="finding-card" open>
    <summary class="finding-header">
      <span class="finding-chevron">▶</span>
      <div class="finding-summary">
        <p class="section-label">Finding 1 · Apple News Formulas</p>
        <h2>Number leads and questions consistently underperform. "Here's" and possessive named entities lead — but sample sizes are small.</h2>
      </div>
    </summary>
    <div class="finding-body">
      <div class="callout">
        <strong>Action:</strong> Avoid number leads and question formats for standard Apple News headlines. "Here's how…" and "[City]'s [development]" constructions are worth testing more deliberately to build sample size.
      </div>
      <p>Across {len(nf):,} non-Featured articles, three formula types significantly underperform the baseline: number leads ({_r1_num['lift']:.2f}×), question format ({_r1_q['lift']:.2f}×), and quoted ledes ({_r1_ql['lift']:.2f}×) — all with FDR-adjusted p&lt;0.001. The better-performing formulas — "Here's / Here are" ({_r1_h['lift']:.2f}×) and possessive named entity ({_r1_pne['lift']:.2f}×) — show strong directional signal but lack statistical significance at current sample sizes (n={_r1_h['n']} and n={_r1_pne['n']} respectively).</p>
      <p>These lifts are now expressed as percentile ratios: a lift of {_r1_h['lift']:.2f}× means the "Here's" group's median article falls in a {_r1_h['lift']:.2f}× higher monthly cohort percentile than untagged articles. Number leads fall to the {_r1_num['median']:.0%}ile of their monthly cohort, versus {baseline.median():.0%}ile for untagged articles.</p>
      <div class="chart-wrap">{c1}</div>
      <table class="findings">
        <thead><tr><th>Formula</th><th>n</th><th>Median %ile</th><th>Lift</th><th>95% CI (bootstrap)</th><th>Effect size r</th><th>p<sub>adj</sub> (BH–FDR)</th><th>n needed (80% power)</th></tr></thead>
        <tbody>
          {_t1}
        </tbody>
      </table>
      <h3>Untagged baseline characterisation</h3>
      <p>The "untagged" baseline ({UNTAGGED_N:,} articles, {UNTAGGED_PCT:.0%} of non-Featured) comprises headlines that do not match any formula regex — typically mid-sentence constructions, declarative statements, and soft-news ledes. Sample (random): <em>{' / '.join([str(x)[:80] for x in _ung_sample])}</em>.</p>
      <p class="caveat">Non-Featured articles only (n={len(nf):,}). Primary metric: percentile_within_cohort — percentile rank within same publication month, controlling for temporal view accumulation bias. Mann-Whitney U vs. untagged baseline; effect size = rank-biserial r. 95% CIs: 1,000-iteration bootstrap on median ratio (seed=42). BH–FDR applied across all {len(_q1_raw_p)} formula tests. Stars: * p&lt;0.05 ** p&lt;0.01 *** p&lt;0.001. "n needed" = estimated per-group sample for 80% power (α=0.05). Formula classifier: unvalidated regex.</p>
    </div>
  </details>

  <!-- FEATURING -->
  <details id="featuring" class="finding-card">
    <summary class="finding-header">
      <span class="finding-chevron">▶</span>
      <div class="finding-summary">
        <p class="section-label">Finding 2 · Featured by Apple</p>
        <h2>"What to know" headlines get Featured at {WTN_FEAT} — {WTN_FEAT_LIFT:.1f}× the {overall_feat_rate:.0%} baseline rate.</h2>
      </div>
    </summary>
    <div class="finding-body">
      <div class="callout">
        <strong>Action:</strong> Use "What to know" on high-stakes local stories — health alerts, weather emergencies, civic events. It is the fastest path to Featured placement. Apple's editors strongly favor this format for surfacing to subscribers.
      </div>
      <p>Among the {an["is_featured"].sum()} Featured articles in our dataset, "What to know" headlines are dramatically overrepresented: {_wtn_feat_n} of {_wtn_total} ({WTN_FEAT}) were Featured, versus {overall_feat_rate:.1%} overall. This is the strongest statistically significant formula signal in the dataset (χ²={_r2_wtn['chi2']:.1f}, {_fmt_p(_r2_wtn.get('p_chi_adj', _r2_wtn['p_chi']), adj=True)}).</p>
      <p>Question-format headlines are also Featured more often than expected ({_r2_q['featured_rate']:.0%}, {_r2_q['featured_lift']:.2f}× lift, {_fmt_p(_r2_q.get('p_chi_adj', _r2_q['p_chi']), adj=True)}) — but they significantly underperform other Featured articles once selected. Apple's editors favor questions; the format itself doesn't follow through on views.</p>
      <p>Quoted ledes present the inverse pattern: Featured at roughly the baseline rate ({_r2_ql['featured_rate']:.0%}), but once Featured they deliver among the highest within-Featured percentiles. Questions get into the Featured tier and stall; quoted ledes get in and overperform.</p>
      <p><em>Causal note:</em> The association between "What to know" and Featured placement is observational. The causal direction is ambiguous: editors may independently choose the same stories that writers frame as "What to know," rather than the format itself driving featuring.</p>
      <div class="chart-wrap">{c2}</div>
      <table class="findings">
        <thead><tr><th>Formula</th><th>n</th><th>Featured rate</th><th>Lift</th><th>p<sub>adj</sub> (BH–FDR)</th><th>Within-Featured median %ile</th></tr></thead>
        <tbody>
          {_t2}
        </tbody>
      </table>
      <h3>Featured placement drives reach — not reading depth</h3>
      <p>Featured articles average {_feat_at_an.median():.0f} seconds of active reading time versus {_nfeat_at_an.median():.0f} seconds for non-Featured. The difference is statistically significant (Mann-Whitney p&lt;0.0001). Apple's editorial promotion drives discovery; readers who find an article because the algorithm surfaced it are slightly less engaged than readers who sought it out.</p>
      <p class="caveat">All {N_AN:,} Apple News articles (2025–2026). Chi-square test: each formula vs. all other articles combined. BH–FDR across all {len(_q2_raw_p)} formula tests. Causal direction of "What to know" → Featured is unconfirmed.</p>
    </div>
  </details>

  <!-- SMARTNEWS -->
  <details id="smartnews" class="finding-card">
    <summary class="finding-header">
      <span class="finding-chevron">▶</span>
      <div class="finding-summary">
        <p class="section-label">Finding 3 · SmartNews Allocation</p>
        <h2>SmartNews Local delivers {LOCAL_LIFT} the percentile rank of average Top-feed articles. Entertainment gets {_ent_local_ratio}× more articles and performs like average.</h2>
      </div>
    </summary>
    <div class="finding-body">
      <div class="callout">
        <strong>Action:</strong> Flag this finding to the distribution team. Entertainment is consuming {_r4_ent['pct_share']:.1%} of SmartNews article volume at barely-above-baseline ROI. Local and U.S. National channels deliver dramatically higher percentile ranks at a fraction of the volume — this is a reallocation opportunity, not a content quality problem.
        <br><br><em>Caveat:</em> Articles in Local and U.S. channels are likely higher-quality breaking/civic stories that would perform well regardless of channel. Channel assignment partly reflects content type.
      </div>
      <p>SmartNews category channel data reveals a severe allocation mismatch. Articles appearing in the Local channel sit at the {_r4_loc['median_pct']:.0%}ile of their monthly cohort ({_r4_loc['median_views']:,.0f} median raw views). The U.S. National channel: {_r4_us['median_pct']:.0%}ile. The Top feed baseline: {top_median_sn_pct:.0%}ile. Meanwhile, Entertainment — which accounts for {_r4_ent['pct_share']:.1%} of all SmartNews articles — sits at only the {_r4_ent['median_pct']:.0%}ile.</p>
      <div class="chart-wrap">{c3}</div>
      <table class="findings">
        <thead><tr><th>Channel</th><th>Article count</th><th>% of total</th><th>Median %ile</th><th>Median raw views</th><th>Lift vs. Top</th><th>p<sub>adj</sub> (BH–FDR)</th></tr></thead>
        <tbody>
          {_t3}
        </tbody>
      </table>
      <p class="caveat">SmartNews 2025 (n={N_SN:,} articles). Category columns contain channel-specific view counts; non-zero = article appeared in that channel. Lift = median percentile vs. Top feed median percentile. Mann-Whitney U: each channel vs. Top feed; BH–FDR correction applied across {len(_q4_raw_p)} tests. Independence caveat: {SN_MULTI_CAT_N:,} articles ({SN_MULTI_CAT_PCT:.0%}) appear in more than one category. 2026 export lacks category breakdown — 2025 data only.</p>
    </div>
  </details>

  <!-- NOTIFICATIONS -->
  <details id="notifications" class="finding-card">
    <summary class="finding-header">
      <span class="finding-chevron">▶</span>
      <div class="finding-summary">
        <p class="section-label">Finding 4 · Push Notification CTR</p>
        <h2>"Exclusive" delivers {EXCL_LIFT} CTR lift. Possessive framing on a full name adds {_r5_poss['lift']:.2f}×. Questions hurt.</h2>
      </div>
    </summary>
    <div class="finding-body">
      <div class="callout">
        <strong>Action:</strong> The highest-leverage notification formula is: <em>[Person's] [relationship/role] [reaction/new development]</em> — e.g., "Savannah Guthrie's husband breaks silence…" Use full names. Reserve "exclusive" for actual exclusives. Avoid question format.
      </div>
      <p>Across {N_NOTIF} Apple News push notifications (Jan–Feb 2026, median CTR {CTR_MED}), four features show statistically significant positive effects after FDR correction. The "exclusive" tag is the strongest at {EXCL_LIFT} lift. The possessive framing signal: notifications with a full named person AND a possessive construction drive {_r5_poss['lift']:.2f}× CTR vs. {_r5_full['lift']:.2f}× for merely naming someone. Question format hurts at {_r5_q['lift']:.2f}×, consistent with the Apple News article finding.</p>
      <div class="chart-wrap">{c4}</div>
      <table class="findings">
        <thead><tr><th>Feature</th><th>n (present)</th><th>Median CTR (present)</th><th>Median CTR (absent)</th><th>Lift (95% CI)</th><th>Effect size r</th><th>p<sub>adj</sub> (BH–FDR)</th></tr></thead>
        <tbody>
          {_t4}
        </tbody>
      </table>
      {_excl_sensitivity_html}
      <h3>The serial/escalating story as a content type</h3>
      <p>The top 10 notifications by CTR are dominated by a single ongoing story: Nancy Guthrie's disappearance and its connection to Savannah Guthrie. This defines a content type: <strong>the serial/escalating story with a celebrity anchor</strong>. The formula: possessive named entity + new development + escalating stakes, published in installments. The structural recipe: <em>"[Celebrity]'s [family member/associate] [new disclosure/development]."</em></p>
      <p>What doesn't move the needle: neither "contains a number" (n={_r5_num['n_true']}, {_r5_num['lift']:.2f}×) nor "attribution" — says/told/reports (n={_r5_attr['n_true']}, {_r5_attr['lift']:.2f}×) — survive FDR correction.</p>
      <p class="caveat">Apple News Notifications, Jan–Feb 2026 (n={N_NOTIF} with valid CTR). Mann-Whitney U; effect size = rank-biserial r; 95% CIs via 1,000-iteration bootstrap. BH–FDR across all {len(_q5_raw_p)} feature tests. N=2 months only — findings are directional. Feature classifier unvalidated.</p>
    </div>
  </details>

  <!-- TOPICS -->
  <details id="topics" class="finding-card">
    <summary class="finding-header">
      <span class="finding-chevron">▶</span>
      <div class="finding-summary">
        <p class="section-label">Finding 5 · Platform Topic Inversion</p>
        <h2>Sports is top-3 on Apple News and dead last on SmartNews. You cannot use the same sports content strategy across platforms — the magnitude of the inversion is the surprise.</h2>
      </div>
    </summary>
    <div class="finding-body">
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

      <p class="caveat">Topic tagged via unvalidated regex classifier applied to headline text. Percentile index = median percentile_within_cohort / platform overall median percentile. Apple News 2025–2026 (n={N_AN:,}); SmartNews 2025 (n={N_SN:,}). Subtopic classifier unvalidated. No significance testing — treat as descriptive. Sports subtopics with n&lt;3 show "—".</p>
    </div>
  </details>

  <!-- ALLOCATION / VARIANCE -->
  <details id="allocation" class="finding-card">
    <summary class="finding-header">
      <span class="finding-chevron">▶</span>
      <div class="finding-summary">
        <p class="section-label">Finding 6 · Headline Variance by Topic</p>
        <h2>Crime shows the widest outcome spread on both platforms. On Apple News, business is second. Headline choice moves the needle most in these two categories.</h2>
      </div>
    </summary>
    <div class="finding-body">
      <div class="callout">
        <strong>Action:</strong> Concentrate variant production on high-variance topic combinations — where headline optimization has the most room to move performance. For Apple News: crime and business. For SmartNews: local/civic (where channel placement bimodality is the driver). Low-variance topics — nature/wildlife on Apple News — have less to gain from headline optimization.
      </div>
      <p>The chart below shows IQR ÷ median of percentile_within_cohort for each topic × platform. A ratio of 3.0 means the difference between the 25th and 75th percentile articles in that topic is 3× the median percentile — i.e., the top half significantly outperforms the bottom half. Where this ratio is high, headline optimization has the most room to lift performance.</p>
      <div class="chart-wrap">{c6}</div>

      <h3>Crime: top vs. bottom quartile headlines on Apple News</h3>
      <div class="example-cols">
        <div class="example-list example-top"><h4>Top quartile crime headlines</h4><ul>{crime_top_h}</ul></div>
        <div class="example-list example-bot"><h4>Bottom quartile crime headlines</h4><ul>{crime_bot_h}</ul></div>
      </div>

      <h3>Business: top vs. bottom quartile headlines on Apple News</h3>
      <div class="example-cols">
        <div class="example-list example-top"><h4>Top quartile business headlines</h4><ul>{biz_top_h}</ul></div>
        <div class="example-list example-bot"><h4>Bottom quartile business headlines</h4><ul>{biz_bot_h}</ul></div>
      </div>

      <p class="caveat">IQR = interquartile range (75th percentile minus 25th percentile) of percentile_within_cohort. IQR/median is a scale-free spread measure. Topic tagged via regex classifier. Apple News 2025–2026; SmartNews 2025. Topics with fewer than 10 articles excluded. High IQR/median on SmartNews local/civic is substantially explained by channel-placement bimodality (Finding 3).</p>
    </div>
  </details>

  <!-- ENGAGEMENT -->
  <details id="engagement" class="finding-card">
    <summary class="finding-header">
      <span class="finding-chevron">▶</span>
      <div class="finding-summary">
        <p class="section-label">Finding 7 · Views vs. Reading Depth</p>
        <h2>Views and reading time are statistically independent. Optimizing for clicks and optimizing for reading are different problems.</h2>
      </div>
    </summary>
    <div class="finding-body">
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
    </div>
  </details>

  <!-- TRENDS -->
  <details id="trends" class="finding-card">
    <summary class="finding-header">
      <span class="finding-chevron">▶</span>
      <div class="finding-summary">
        <p class="section-label">Finding 8 · Longitudinal Trends &amp; Year-over-Year</p>
        <h2>The formula lift patterns from 2025 are holding in 2026 — with one exception: {YOY_CHANGING_FORMULA} shows the largest shift ({YOY_CHANGING_DELTA:+.0%}ile).</h2>
      </div>
    </summary>
    <div class="finding-body">
      <div class="callout">
        <strong>Action:</strong> The core formula rankings are stable across seasons. The longitudinal chart below shows whether the underperformance of number leads and questions has been consistent, or whether it is driven by a specific period. Monitor the changing formula ({YOY_CHANGING_FORMULA}) as 2026 data accumulates.
        <br><br><em>Caveat:</em> 2026 data covers only Jan–Feb. Seasonal effects (e.g., peak news cycles, sports seasons) are not controlled. YoY comparison is directional only.
      </div>
      <div class="chart-wrap">{c8}</div>

      <h3>Year-over-Year: Jan–Feb 2025 vs. Jan–Feb 2026</h3>
      <p>Comparing the same two-month window across years controls for seasonal effects. The table shows formula distribution, Featured rate, and median percentile rank for each formula.</p>
      <table class="findings">
        <thead><tr>
          <th>Formula</th>
          <th>2025 n</th><th>2025 Featured</th><th>2025 Median %ile</th>
          <th>2026 n</th><th>2026 Featured</th><th>2026 Median %ile</th>
        </tr></thead>
        <tbody>{_t_yoy}</tbody>
      </table>
      <p class="caveat">Longitudinal chart: only formula-months with n≥3 articles plotted. YoY comparison: 2025 Jan–Feb vs. all of 2026 (Jan–Feb only). Percentile ranks are computed within each year separately — cross-year percentile comparisons are directional. 2026 data through {REPORT_DATE}.</p>
    </div>
  </details>

  {_finding_numleads_html}

  {_finding9_html}

</div>

<script>
function toggleAll() {{
  const cards = document.querySelectorAll('.finding-card');
  const anyOpen = Array.from(cards).some(d => d.open);
  cards.forEach(d => d.open = !anyOpen);
  document.getElementById('expand-btn').textContent = anyOpen ? 'Expand all' : 'Collapse all';
}}

function openByHash() {{
  const hash = window.location.hash;
  if (!hash) return;
  const target = document.querySelector(hash);
  if (target && target.tagName === 'DETAILS') {{
    target.open = true;
    setTimeout(() => target.scrollIntoView({{behavior: 'smooth', block: 'start'}}), 50);
  }}
}}
window.addEventListener('hashchange', openByHash);
document.addEventListener('DOMContentLoaded', openByHash);
</script>

<footer>
  <p>McClatchy CSA · T1 Headline Performance Analysis · {REPORT_DATE}</p>
  <p style="margin-top: 0.5rem;">
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
