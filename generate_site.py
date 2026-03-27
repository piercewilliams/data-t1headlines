"""
T1 Headline Analysis — Phase 2 site generator
Run:    python3 generate_site.py
Output: docs/index.html

Optional args (for monthly ingests with new files):
  --data-2025 "path/to/new_2025_file.xlsx"
  --data-2026 "path/to/new_2026_file.xlsx"
"""

import argparse
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
parser.add_argument("--data-2025", default="Top syndication content 2025.xlsx",
                    help="Path to the 2025 data workbook")
parser.add_argument("--data-2026", default="Top Stories 2026 Syndication.xlsx",
                    help="Path to the 2026 data workbook")
_args = parser.parse_args()
DATA_2025 = _args.data_2025
DATA_2026 = _args.data_2026

# ── Palette (matches v1 site) ─────────────────────────────────────────────────
NAVY   = "#0f172a"
BLUE   = "#2563eb"
GREEN  = "#16a34a"
RED    = "#dc2626"
AMBER  = "#d97706"
GRAY   = "#64748b"
LIGHT  = "#f8fafc"
BORDER = "#e2e8f0"


# ── Helpers ───────────────────────────────────────────────────────────────────
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


# ── Load data ─────────────────────────────────────────────────────────────────
print(f"Loading data…  2025={DATA_2025}  2026={DATA_2026}")
an    = pd.read_excel(DATA_2025, sheet_name="Apple News")
sn    = pd.read_excel(DATA_2025, sheet_name="SmartNews")
msn   = pd.read_excel(DATA_2025, sheet_name="MSN")
yahoo = pd.read_excel(DATA_2025, sheet_name="Yahoo")
notif = pd.read_excel(DATA_2026, sheet_name="Apple News Notifications")

an["is_featured"] = an["Featured by Apple"].fillna("No") == "Yes"
an["formula"] = an["Article"].apply(classify_formula)
an["topic"]   = an["Article"].apply(tag_topic)

sn["topic"]   = sn["title"].apply(tag_topic)

CATS = ["Top","Entertainment","Lifestyle","U.S.","Business","World",
        "Technology","Science","Politics","Health","Local","Football","LGBTQ"]
for cat in CATS:
    sn[cat] = pd.to_numeric(sn[cat], errors="coerce").fillna(0)

notif = notif.dropna(subset=["CTR"]).copy()

# ── Platform exclusivity (exact normalised title match) ───────────────────────
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


# ── Q1: Formula → median views (non-Featured) ────────────────────────────────
print("Computing Q1/Q2…")
nf = an[~an["is_featured"]].copy()
overall_median_nf = nf["Total Views"].median()
baseline = nf[nf["formula"] == "untagged"]["Total Views"]

FORMULA_LABELS = {
    "what_to_know":            "What to know",
    "heres_formula":           "Here's / Here are",
    "possessive_named_entity": "Possessive named entity",
    "untagged":                "Untagged (baseline)",
    "quoted_lede":             "Quoted lede",
    "number_lead":             "Number lead",
    "question":                "Question",
}

q1_rows = []
for f, label in FORMULA_LABELS.items():
    grp = nf[nf["formula"] == f]["Total Views"]
    if len(grp) == 0: continue
    med  = grp.median()
    lift = med / baseline.median()
    if f != "untagged" and len(grp) >= 5:
        _, p = stats.mannwhitneyu(grp, baseline, alternative="two-sided")
    else:
        p = None
    q1_rows.append(dict(formula=f, label=label, n=len(grp), median=med, lift=lift, p=p))

df_q1 = pd.DataFrame(q1_rows).sort_values("median")

# ── Q2: Featured rate per formula ─────────────────────────────────────────────
overall_feat_rate = an["is_featured"].mean()
_tot_feat = int(an["is_featured"].sum())
q2_rows = []
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
    q2_rows.append(dict(formula=f, label=label, n=len(grp), feat_n=feat_n,
                        featured_rate=feat_rate, featured_lift=lift,
                        chi2=_chi2_f, p_chi=_p_chi_f))

df_q2 = pd.DataFrame(q2_rows).sort_values("featured_rate")

# Within-featured median views per formula
feat_an = an[an["is_featured"]].copy()
feat_avg_views = feat_an["Total Views"].median()
for _f in FORMULA_LABELS:
    _grp_feat = feat_an[feat_an["formula"] == _f]["Total Views"]
    _val = _grp_feat.median() if len(_grp_feat) >= 3 else np.nan
    df_q2.loc[df_q2["formula"] == _f, "feat_med_views"] = _val
df_q2["feat_views_lift"] = df_q2["feat_med_views"] / feat_avg_views

# ── Q4: SmartNews category ROI ────────────────────────────────────────────────
print("Computing Q4…")
top_median_sn = sn[sn["Top"] > 0]["article_view"].median()
SHOW_CATS = ["Local","U.S.","Football","Business","Health","Science",
             "Politics","World","Lifestyle","Entertainment","Top"]
q4_rows = []
for cat in SHOW_CATS:
    in_cat = sn[sn[cat] > 0]
    n = len(in_cat)
    med = in_cat["article_view"].median()
    q4_rows.append(dict(category=cat, n=n, median_views=med,
                        pct_share=n/len(sn)))
df_q4 = pd.DataFrame(q4_rows)
df_q4["lift"] = df_q4["median_views"] / top_median_sn

# ── Q5: Notification CTR features ────────────────────────────────────────────
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
notif_feats = pd.concat([notif[["CTR"]], feats], axis=1)
overall_ctr_med = notif["CTR"].median()

q5_rows = []
for feat in feats.columns:
    yes = notif_feats[notif_feats[feat] == True]["CTR"]
    no  = notif_feats[notif_feats[feat] == False]["CTR"]
    if len(yes) < 5 or len(no) < 5: continue
    med_yes = yes.median()
    med_no  = no.median()
    lift = med_yes / med_no if med_no > 0 else np.nan
    _, p = stats.mannwhitneyu(yes, no, alternative="two-sided")
    q5_rows.append(dict(feature=feat, n_true=len(yes), med_yes=med_yes,
                        med_no=med_no, lift=lift, p=p))

df_q5 = pd.DataFrame(q5_rows).sort_values("lift")


# ── Q6: Views vs. active time independence ────────────────────────────────────
print("Computing Q6…")
AT_COL  = "Avg. Active Time (in seconds)"
SAV_COL = "Saves"
LIK_COL = "Likes"
SHA_COL = "Article Shares"

SUB_AT_COL  = "Avg. Active Time (in seconds), Subscribers, Subscription Content"
NSUB_AT_COL = "Avg. Active Time (in seconds), Non-subscribers, Free Content"

an_eng = an[[AT_COL, SAV_COL, LIK_COL, SHA_COL,
             SUB_AT_COL, NSUB_AT_COL,
             "Total Views", "is_featured"]].dropna(subset=[AT_COL, "Total Views"])

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
_, p_feat_at = stats.mannwhitneyu(feat_at, nfeat_at, alternative="two-sided")

# Subscriber vs non-subscriber active time
sub_at_med  = an_eng[SUB_AT_COL].dropna().median()
nsub_at_med = an_eng[NSUB_AT_COL].dropna().median()

# Decile table
an_eng["decile"] = pd.qcut(an_eng["Total Views"], 10, labels=False) + 1
decile_tbl = an_eng.groupby("decile").agg(
    med_views=("Total Views", "median"),
    med_at=(   AT_COL,        "median"),
).reset_index()
at_range_s = decile_tbl["med_at"].max() - decile_tbl["med_at"].min()
views_range_x = int(decile_tbl["med_views"].max() / decile_tbl["med_views"].min())

# Active time outliers for caveat
at_low_n  = int((an_eng[AT_COL] < 10).sum())
at_high_n = int((an_eng[AT_COL] > 300).sum())

# Chart 6 scatter — views vs active time (log x), coloured by Featured (all points)
q6_sample = an_eng


# ── Chart builder ─────────────────────────────────────────────────────────────
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


# Chart 1 — Q1: Formula lift vs baseline (diverging from 1.0)
# Show lift ratio directly — cleaner than raw view counts
colors_q1 = [bar_color(r["lift"]) for _, r in df_q1.iterrows()]
hover_q1 = [f"Median: {int(r['median']):,} views | n={r['n']}" for _, r in df_q1.iterrows()]

fig1 = go.Figure(go.Bar(
    y=df_q1["label"].tolist(),
    x=df_q1["lift"].tolist(),
    orientation="h",
    marker_color=colors_q1,
    text=[f"{v:.2f}x  (n={n})" for v, n in zip(df_q1["lift"].tolist(), df_q1["n"].tolist())],
    textposition="outside",
    hovertext=hover_q1,
    hoverinfo="y+text",
))
fig1.add_vline(x=1.0, line_dash="dash", line_color=GRAY,
               annotation_text="Baseline", annotation_position="top")
fig1.update_layout(
    **PLOTLY_LAYOUT,
    title=dict(text="Views lift vs. baseline by formula type — non-Featured articles only",
               font=dict(size=13, color=NAVY), x=0),
    xaxis=dict(title="Median views relative to untagged baseline (1.0 = same as baseline)",
               gridcolor=BORDER, zeroline=False, range=[0, 4.5]),
    yaxis=dict(title=""),
    showlegend=False,
)

# Chart 2 — Q2: Featured rate per formula
colors_q2 = [bar_color(r["featured_lift"]) for _, r in df_q2.iterrows()]
fig2 = go.Figure(go.Bar(
    y=df_q2["label"].tolist(),
    x=(df_q2["featured_rate"] * 100).tolist(),
    orientation="h",
    marker_color=colors_q2,
    text=[f"{r['featured_rate']:.0%}  ({r['featured_lift']:.2f}x)" for _, r in df_q2.iterrows()],
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

# Chart 3 — Q4: SmartNews — bar chart sorted by median views, annotated with volume
# Sort by median views descending for the chart
df_q4_chart = df_q4.sort_values("median_views", ascending=True)
q4_colors = []
for _, r in df_q4_chart.iterrows():
    if r["median_views"] > 5000:    q4_colors.append(GREEN)
    elif r["median_views"] > 500:   q4_colors.append(BLUE)
    elif r["pct_share"] > 0.20:     q4_colors.append(RED)
    else:                           q4_colors.append(GRAY)

fig3 = go.Figure(go.Bar(
    y=df_q4_chart["category"].tolist(),
    x=df_q4_chart["median_views"].tolist(),
    orientation="h",
    marker_color=q4_colors,
    text=[f"{int(v):,} views  ({p:.0%} of articles)"
          for v, p in zip(df_q4_chart["median_views"].tolist(),
                          df_q4_chart["pct_share"].tolist())],
    textposition="outside",
    hovertext=[f"n={n:,} articles" for n in df_q4_chart["n"].tolist()],
    hoverinfo="y+x+text",
))
fig3.update_layout(
    **{k: v for k, v in PLOTLY_LAYOUT.items() if k != "margin"},
    title=dict(text="Median article views by SmartNews channel — with share of total article volume",
               font=dict(size=13, color=NAVY), x=0),
    xaxis=dict(title="Median total article views", gridcolor=BORDER, zeroline=False,
               range=[0, 21000]),
    yaxis=dict(title=""),
    showlegend=False,
    margin=dict(l=20, r=280, t=50, b=40),
)

# Chart 4 — Q5: Notification CTR lift
colors_q5 = [bar_color(r["lift"]) for _, r in df_q5.iterrows()]
sig_labels = []
for _, r in df_q5.iterrows():
    p = r["p"]
    s = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else "ns"))
    sig_labels.append(f"{r['lift']:.2f}x  {s}  (n={r['n_true']})")

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
    xaxis=dict(title="CTR lift (1.0 = no effect)", gridcolor=BORDER, zeroline=False,
               range=[0, 3.8]),
    yaxis=dict(title=""),
    showlegend=False,
    margin=dict(l=20, r=220, t=50, b=40),
)

# Chart 5 — Topic performance Apple News vs SmartNews
an_topic = an.groupby("topic")["Total Views"].median().reset_index()
an_topic.columns = ["topic", "an_median"]
sn_topic = sn.groupby("topic")["article_view"].median().reset_index()
sn_topic.columns = ["topic", "sn_median"]
topic_df = an_topic.merge(sn_topic, on="topic")
TOPIC_LABELS = {
    "weather":"Weather","sports":"Sports","crime":"Crime","business":"Business",
    "local_civic":"Local/Civic","lifestyle":"Lifestyle",
    "nature_wildlife":"Nature/Wildlife","other":"Other"
}
topic_df["label"] = topic_df["topic"].map(TOPIC_LABELS)

an_overall = an["Total Views"].median()
sn_overall = sn["article_view"].median()
topic_df["an_idx"] = (topic_df["an_median"] / an_overall).tolist()
topic_df["sn_idx"] = (topic_df["sn_median"] / sn_overall).tolist()

# Sort by Apple News index descending — makes platform inversions visually obvious
topic_df = topic_df.sort_values("an_idx", ascending=True)

# Key stats for prose (all dynamic)
an_ranked = topic_df.sort_values("an_idx", ascending=False).reset_index(drop=True)
sn_ranked = topic_df.sort_values("sn_idx", ascending=False).reset_index(drop=True)
an_top_label = TOPIC_LABELS.get(an_ranked.iloc[0]["topic"], an_ranked.iloc[0]["topic"])
an_top_med   = int(an_ranked.iloc[0]["an_median"])
an_2nd_label = TOPIC_LABELS.get(an_ranked.iloc[1]["topic"], an_ranked.iloc[1]["topic"])
an_2nd_med   = int(an_ranked.iloc[1]["an_median"])
sn_top_label = TOPIC_LABELS.get(sn_ranked.iloc[0]["topic"], sn_ranked.iloc[0]["topic"])
sn_top_med   = int(sn_ranked.iloc[0]["sn_median"])
# Sports rank and values on each platform
sports_an_rank = int(an_ranked[an_ranked["topic"] == "sports"].index[0]) + 1
sports_sn_rank = int(sn_ranked[sn_ranked["topic"] == "sports"].index[0]) + 1
sports_an_med  = int(topic_df.loc[topic_df["topic"] == "sports", "an_median"].iloc[0])
sports_sn_med  = int(topic_df.loc[topic_df["topic"] == "sports", "sn_median"].iloc[0])
sports_an_idx  = float(topic_df.loc[topic_df["topic"] == "sports", "an_idx"].iloc[0])
sports_sn_idx  = float(topic_df.loc[topic_df["topic"] == "sports", "sn_idx"].iloc[0])
# Nature/wildlife inversion
nw_an_idx = float(topic_df.loc[topic_df["topic"] == "nature_wildlife", "an_idx"].iloc[0])
nw_sn_idx = float(topic_df.loc[topic_df["topic"] == "nature_wildlife", "sn_idx"].iloc[0])

fig5 = go.Figure()
fig5.add_trace(go.Bar(
    y=topic_df["label"].tolist(), x=topic_df["an_idx"],
    name="Apple News", orientation="h",
    marker_color=BLUE, opacity=0.85,
    hovertemplate="<b>%{y}</b><br>Apple News: %{x:.2f}x platform median<extra></extra>",
))
fig5.add_trace(go.Bar(
    y=topic_df["label"].tolist(), x=topic_df["sn_idx"],
    name="SmartNews", orientation="h",
    marker_color=GREEN, opacity=0.85,
    hovertemplate="<b>%{y}</b><br>SmartNews: %{x:.2f}x platform median<extra></extra>",
))
fig5.add_vline(x=1.0, line_dash="dash", line_color=GRAY,
               annotation_text="Platform median", annotation_position="top")
fig5.update_layout(
    **{k: v for k, v in PLOTLY_LAYOUT.items() if k not in ("height", "margin")},
    title=dict(text="Topic performance index by platform (1.0 = platform median views)",
               font=dict(size=13, color=NAVY), x=0),
    barmode="group",
    xaxis=dict(title="Views index vs. platform median", gridcolor=BORDER, zeroline=False),
    yaxis=dict(title=""),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=450,
    margin=dict(l=20, r=40, t=70, b=40),
)


# Chart 6 — Q6 variance: IQR/median by topic × platform
var_rows = []
for topic, label in TOPIC_LABELS.items():
    an_t = an[an["topic"] == topic]["Total Views"].dropna()
    sn_t = sn[sn["topic"] == topic]["article_view"].dropna()
    if len(an_t) >= 10 and an_t.median() > 0:
        an_cv = (an_t.quantile(0.75) - an_t.quantile(0.25)) / an_t.median()
    else:
        an_cv = None
    if len(sn_t) >= 10 and sn_t.median() > 0:
        sn_cv = (sn_t.quantile(0.75) - sn_t.quantile(0.25)) / sn_t.median()
    else:
        sn_cv = None
    var_rows.append(dict(topic=topic, label=label, an_cv=an_cv, sn_cv=sn_cv,
                         an_n=len(an_t), sn_n=len(sn_t)))

df_var = pd.DataFrame(var_rows).dropna(subset=["an_cv", "sn_cv"])
df_var = df_var.sort_values("an_cv", ascending=True)

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
    title=dict(text="Views spread by topic (IQR ÷ median) — where headline choice moves the needle most",
               font=dict(size=13, color=NAVY), x=0),
    barmode="group",
    xaxis=dict(title="IQR / median views (higher = wider spread, more headline lift potential)",
               gridcolor=BORDER, zeroline=False),
    yaxis=dict(title=""),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=450,
    margin=dict(l=20, r=140, t=70, b=40),
)


# Chart 7 — Views vs. active time scatter (log x)
feat_mask  = q6_sample["is_featured"]
nfeat_mask = ~q6_sample["is_featured"]

fig7 = go.Figure()
fig7.add_trace(go.Scatter(
    x=q6_sample[nfeat_mask]["Total Views"].tolist(),
    y=q6_sample[nfeat_mask][AT_COL].tolist(),
    mode="markers",
    name="Not Featured",
    marker=dict(color=BLUE, size=4, opacity=0.35),
    hovertemplate="Views: %{x:,}<br>Active time: %{y}s<extra>Not Featured</extra>",
))
fig7.add_trace(go.Scatter(
    x=q6_sample[feat_mask]["Total Views"].tolist(),
    y=q6_sample[feat_mask][AT_COL].tolist(),
    mode="markers",
    name="Featured by Apple",
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
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=420,
    margin=dict(l=20, r=40, t=60, b=40),
)


# ── Render charts to HTML strings ────────────────────────────────────────────
def chart_html(fig):
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"responsive": True})


c1 = chart_html(fig1)
c2 = chart_html(fig2)
c3 = chart_html(fig3)
c4 = chart_html(fig4)
c5 = chart_html(fig5)
c6 = chart_html(fig6)
c7 = chart_html(fig7)


# ── Keyword overlap (top quartile Apple News vs SmartNews) ───────────────────
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

q75_an = an["Total Views"].quantile(0.75)
q75_sn = sn["article_view"].quantile(0.75)
top_an_words = top_words(an[an["Total Views"] >= q75_an]["Article"])
top_sn_words = top_words(sn[sn["article_view"] >= q75_sn]["title"])
kw_overlap   = top_an_words & top_sn_words
kw_overlap_n = len(kw_overlap)


# ── Key stats ─────────────────────────────────────────────────────────────────
N_AN        = len(an)
N_SN        = len(sn)
N_NOTIF     = len(notif)
PLATFORMS   = sum(1 for _df in [an, sn, msn, yahoo] if _df is not None and len(_df) > 0)
REPORT_DATE = datetime.now().strftime("%B %Y")

# Hero numbers — computed from data, not hardcoded
_wtn_row  = df_q2[df_q2["formula"] == "what_to_know"]
WTN_FEAT_RATE = float(_wtn_row["featured_rate"].iloc[0]) if len(_wtn_row) else overall_feat_rate
WTN_FEAT  = f"{WTN_FEAT_RATE:.0%}"

_local_row = df_q4[df_q4["category"] == "Local"]
_local_med = float(_local_row["median_views"].iloc[0]) if len(_local_row) else 0
LOCAL_LIFT = f"{_local_med / top_median_sn:.0f}×" if top_median_sn > 0 else "—"

_excl_row  = df_q5[df_q5["feature"] == "'Exclusive' tag"]
_excl_lift_val = float(_excl_row["lift"].iloc[0]) if len(_excl_row) else None
EXCL_LIFT  = f"{_excl_lift_val:.2f}×" if _excl_lift_val else "—"


# ── Prose helpers ─────────────────────────────────────────────────────────────
def _fmt_p(p):
    """Format p-value with stars for HTML."""
    if p is None or (isinstance(p, float) and np.isnan(p)): return "—"
    p = float(p)
    sig = " ***" if p < 0.001 else " **" if p < 0.01 else " *" if p < 0.05 else ""
    if p < 0.001: return "&lt;0.001" + sig
    if p < 0.01:  return f"{p:.3f}" + sig
    return f"{p:.2f}" + sig

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

# Finding 1 helpers
_r1_num = _q1r("number_lead")
_r1_q   = _q1r("question")
_r1_ql  = _q1r("quoted_lede")
_r1_h   = _q1r("heres_formula")
_r1_pne = _q1r("possessive_named_entity")

# Finding 2 helpers
_r2_wtn = _q2r("what_to_know")
_r2_q   = _q2r("question")
_r2_ql  = _q2r("quoted_lede")
_wtn_feat_n   = int(_r2_wtn["feat_n"])      if _r2_wtn is not None else 0
_wtn_total    = int(_r2_wtn["n"])            if _r2_wtn is not None else 0
WTN_FEAT_LIFT = float(_r2_wtn["featured_lift"]) if _r2_wtn is not None else 0

# Finding 3 helpers
_r4_loc  = _q4r("Local")
_r4_us   = _q4r("U.S.")
_r4_ent  = _q4r("Entertainment")
_r4_wld  = _q4r("World")
_r4_hlth = _q4r("Health")
_r4_top  = _q4r("Top")
_ent_local_ratio = (int(round(_r4_ent["n"] / _r4_loc["n"]))
                    if _r4_ent is not None and _r4_loc is not None and _r4_loc["n"] > 0 else 0)

# Finding 4 helpers
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

def _q2_table():
    rows = df_q2[df_q2["formula"] != "untagged"].sort_values("featured_rate", ascending=False)
    html = ""
    for _, r in rows.iterrows():
        feat_med = r.get("feat_med_views")
        if feat_med is not None and not np.isnan(float(feat_med)):
            wf = f"{feat_med:,.0f} views ({float(r['feat_views_lift']):.2f}× Featured avg)"
        else:
            wf = "—"
        sig = " ***" if r["p_chi"] < 0.001 else " **" if r["p_chi"] < 0.01 else " *" if r["p_chi"] < 0.05 else ""
        tag = _row_tag(r["featured_lift"])
        html += (f'<tr><td>{tag}{r["label"]}</td><td>{r["n"]:,}</td>'
                 f'<td>{r["featured_rate"]:.0%}</td>'
                 f'<td>{r["featured_lift"]:.2f}×{sig}</td>'
                 f'<td>{wf}</td></tr>\n')
    return html

def _q4_table():
    rows_sorted = df_q4[df_q4["category"] != "Top"].sort_values("lift", ascending=False)
    html = ""
    for _, r in rows_sorted.iterrows():
        is_red = (r["lift"] < 2.0 and r["category"] in ("Entertainment", "Lifestyle"))
        tag = _row_tag(r["lift"], is_red=is_red)
        html += (f'<tr><td>{tag}{r["category"]}</td><td>{r["n"]:,}</td>'
                 f'<td>{r["pct_share"]:.1%}</td>'
                 f'<td>{r["median_views"]:,.0f}</td>'
                 f'<td>{r["lift"]:.1f}×</td></tr>\n')
    if _r4_top is not None:
        html += (f'<tr><td>Top feed (baseline)</td><td>{int(_r4_top["n"]):,}</td>'
                 f'<td>{_r4_top["pct_share"]:.1%}</td>'
                 f'<td>{_r4_top["median_views"]:,.0f}</td><td>1.00×</td></tr>\n')
    return html

def _q5_table():
    sig = df_q5[df_q5["p"] < 0.05].sort_values("lift", ascending=False)
    html = ""
    for _, r in sig.iterrows():
        tag = _row_tag(r["lift"])
        html += (f'<tr><td>{tag}{r["feature"]}</td><td>{r["n_true"]:,}</td>'
                 f'<td>{r["med_yes"]:.2%}</td><td>{r["med_no"]:.2%}</td>'
                 f'<td>{r["lift"]:.2f}×</td><td>{_fmt_p(r["p"])}</td></tr>\n')
    return html

_t2 = _q2_table()
_t3 = _q4_table()
_t4 = _q5_table()


# ── HTML ──────────────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>T1 Headline Performance Analysis · Phase 2 · McClatchy CSA</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  :root {{
    --navy: {NAVY};
    --blue: {BLUE};
    --green: {GREEN};
    --red: {RED};
    --amber: {AMBER};
    --gray: {GRAY};
    --light: {LIGHT};
    --border: {BORDER};
    --text: {NAVY};
    --subtext: #475569;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
    color: var(--text); background: #fff; font-size: 16px; line-height: 1.65;
  }}

  /* NAV */
  nav {{
    position: sticky; top: 0; z-index: 100;
    background: var(--navy); padding: 0 1.5rem;
    display: flex; align-items: center; gap: 1.5rem; height: 52px;
    border-bottom: 1px solid rgba(255,255,255,0.07); overflow-x: auto;
  }}
  nav::-webkit-scrollbar {{ display: none; }}
  nav .brand {{ color: #fff; font-weight: 600; font-size: 0.82rem; letter-spacing: 0.04em; white-space: nowrap; flex-shrink: 0; opacity: 0.9; }}
  nav .nav-links {{ display: flex; gap: 1.25rem; align-items: center; }}
  nav a {{ color: rgba(255,255,255,0.5); text-decoration: none; font-size: 0.78rem; white-space: nowrap; padding: 4px 0; border-bottom: 2px solid transparent; transition: color 0.2s, border-color 0.2s; }}
  nav a:hover {{ color: rgba(255,255,255,0.9); }}
  nav .spacer {{ flex: 1; min-width: 1rem; }}
  nav .date {{ color: rgba(255,255,255,0.35); font-size: 0.72rem; white-space: nowrap; flex-shrink: 0; letter-spacing: 0.02em; }}

  /* HERO */
  .hero {{ background: var(--navy); color: #fff; padding: 4.5rem 2rem 4rem; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.06); }}
  .hero .eyebrow {{ text-transform: uppercase; letter-spacing: 0.1em; font-size: 0.67rem; color: rgba(255,255,255,0.38); margin-bottom: 1rem; font-weight: 500; }}
  .hero h1 {{ font-family: Georgia, serif; font-size: 2.1rem; font-weight: 700; line-height: 1.28; max-width: 720px; margin: 0 auto 1.1rem; letter-spacing: -0.01em; }}
  .hero .sub {{ font-size: 0.96rem; color: rgba(255,255,255,0.5); max-width: 600px; margin: 0 auto 2.5rem; line-height: 1.7; }}
  .hero .meta {{ display: flex; justify-content: center; gap: 3rem; flex-wrap: wrap; }}
  .hero .meta-item {{ text-align: center; }}
  .hero .meta-item .num {{ font-size: 1.8rem; font-weight: 700; color: #fff; display: block; letter-spacing: -0.02em; }}
  .hero .meta-item .label {{ font-size: 0.67rem; color: rgba(255,255,255,0.38); text-transform: uppercase; letter-spacing: 0.08em; margin-top: 2px; display: block; }}

  /* LAYOUT */
  .container {{ max-width: 880px; margin: 0 auto; padding: 0 1.75rem; }}
  section {{ padding: 3.5rem 0; border-bottom: 1px solid var(--border); }}
  section:last-of-type {{ border-bottom: none; }}

  /* SECTION LABELS */
  .section-label {{ text-transform: uppercase; letter-spacing: 0.1em; font-size: 0.67rem; color: var(--blue); font-weight: 600; margin-bottom: 0.5rem; }}
  h2 {{ font-family: Georgia, serif; font-size: 1.55rem; font-weight: 700; line-height: 1.3; margin-bottom: 0.75rem; letter-spacing: -0.01em; }}
  h3 {{ font-size: 1rem; font-weight: 600; margin: 1.75rem 0 0.5rem; }}
  p {{ color: var(--subtext); margin-bottom: 1rem; font-size: 0.95rem; }}
  p:last-child {{ margin-bottom: 0; }}

  /* CHART */
  .chart-wrap {{ margin: 1.75rem 0; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; padding: 1rem; }}

  /* CALLOUT */
  .callout {{ background: var(--light); border-left: 3px solid var(--blue); padding: 1rem 1.25rem; border-radius: 0 6px 6px 0; margin: 1.25rem 0; font-size: 0.9rem; color: var(--text); }}
  .callout strong {{ color: var(--navy); }}

  /* TAG */
  .tag {{ display: inline-block; font-size: 0.67rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.07em; padding: 2px 7px; border-radius: 2px; margin-right: 6px; }}
  .tag-blue  {{ background: #dbeafe; color: #1d4ed8; }}
  .tag-green {{ background: #dcfce7; color: #15803d; }}
  .tag-red   {{ background: #fee2e2; color: #b91c1c; }}
  .tag-amber {{ background: #fef3c7; color: #b45309; }}

  /* FINDINGS TABLE */
  .findings {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; margin: 1.25rem 0; }}
  .findings th {{ text-align: left; padding: 6px 10px; border-bottom: 2px solid var(--border); color: var(--gray); font-weight: 600; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; }}
  .findings td {{ padding: 7px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }}
  .findings tr:last-child td {{ border-bottom: none; }}

  /* CAVEAT */
  .caveat {{ font-size: 0.78rem; color: var(--gray); margin-top: 0.5rem; font-style: italic; }}

  /* FINDING CARDS (accordion) */
  .finding-card {{
    border-bottom: 1px solid var(--border);
  }}
  .finding-card:last-of-type {{
    border-bottom: none;
  }}
  .finding-card > summary {{
    list-style: none;
    cursor: pointer;
    padding: 2.25rem 0 2.25rem 0;
    display: grid;
    grid-template-columns: 1.5rem 1fr;
    gap: 0 0.6rem;
    align-items: start;
    user-select: none;
  }}
  .finding-card > summary::-webkit-details-marker {{ display: none; }}
  .finding-card > summary::marker {{ display: none; }}
  .finding-chevron {{
    margin-top: 0.3rem;
    color: var(--blue);
    font-size: 0.7rem;
    transition: transform 0.18s ease;
    display: inline-block;
    flex-shrink: 0;
  }}
  .finding-card[open] > summary .finding-chevron {{
    transform: rotate(90deg);
  }}
  .finding-card > summary:hover h2 {{
    color: var(--blue);
    transition: color 0.15s;
  }}
  .finding-card > summary h2 {{
    transition: color 0.15s;
  }}
  .finding-body {{
    padding: 0 0 3rem 2.1rem;
  }}
  .finding-body > .callout:first-child {{
    margin-top: 0;
  }}

  /* NAV TOGGLE BUTTON */
  .nav-toggle {{
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.2);
    color: rgba(255,255,255,0.65);
    border-radius: 4px;
    padding: 3px 10px;
    font-size: 0.72rem;
    cursor: pointer;
    white-space: nowrap;
    flex-shrink: 0;
    font-family: inherit;
  }}
  .nav-toggle:hover {{
    background: rgba(255,255,255,0.18);
    color: #fff;
  }}

  /* FOOTER */
  footer {{ padding: 3rem 0; text-align: center; color: var(--gray); font-size: 0.8rem; }}
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
  </div>
  <span class="spacer"></span>
  <button class="nav-toggle" id="expand-btn" onclick="toggleAll()">Expand all</button>
  <span class="date">Phase 2 · {REPORT_DATE}</span>
</nav>

<div class="hero">
  <p class="eyebrow">T1 Headline Performance Analysis · Phase 2</p>
  <h1>Formula is a signal to Apple's editors. Platform allocation is where the money is.</h1>
  <p class="sub">{N_AN:,} Apple News articles · {N_SN:,} SmartNews articles · {N_NOTIF} push notifications · {PLATFORMS} platforms · 2025–2026</p>
  <div class="meta">
    <div class="meta-item"><span class="num">{WTN_FEAT}</span><span class="label">Featured rate for "What to know" headlines</span></div>
    <div class="meta-item"><span class="num">{LOCAL_LIFT}</span><span class="label">Views lift for SmartNews Local vs. Top feed</span></div>
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
      <p>Across {len(nf):,} non-Featured articles, three formula types significantly underperform the baseline: number leads ({_r1_num['lift']:.2f}×, p{_fmt_p(_r1_num['p']).replace('&lt;','<')}), question format ({_r1_q['lift']:.2f}×, p{_fmt_p(_r1_q['p']).replace('&lt;','<')}), and quoted ledes ({_r1_ql['lift']:.2f}×, p{_fmt_p(_r1_ql['p']).replace('&lt;','<')}). The better-performing formulas — "Here's / Here are" ({_r1_h['lift']:.2f}×) and possessive named entity ({_r1_pne['lift']:.2f}×) — show strong directional signal but lack statistical significance at current sample sizes (n={_r1_h['n']} and n={_r1_pne['n']} respectively).</p>
      <div class="chart-wrap">{c1}</div>
      <p class="caveat">Non-Featured articles only (n={len(nf):,}). Featured articles removed to isolate headline signal from editorial selection effect. Mann-Whitney U vs. untagged baseline. * p&lt;0.05  ** p&lt;0.01  *** p&lt;0.001</p>
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
      <p>Among the {an["is_featured"].sum()} Featured articles in our dataset, "What to know" headlines are dramatically overrepresented: {_wtn_feat_n} of {_wtn_total} ({WTN_FEAT}) were Featured. The overall Featured rate is {overall_feat_rate:.1%}. This is the strongest statistically significant formula signal in the dataset (χ²={_r2_wtn['chi2']:.1f}, p={_r2_wtn['p_chi']:.4f}).</p>
      <p>Question-format headlines are also Featured more often than expected ({_r2_q['featured_rate']:.0%}, {_r2_q['featured_lift']:.2f}× lift, p={_r2_q['p_chi']:.3f}) — but they significantly underperform other Featured articles once selected. Apple's editors favor questions; the format itself doesn't follow through on views.</p>
      <p>Quoted ledes present the inverse pattern: Featured at roughly the baseline rate ({_r2_ql['featured_rate']:.0%}), but once Featured they deliver among the highest within-Featured medians — {_r2_ql['feat_med_views']:,.0f} views, {_r2_ql['feat_views_lift']:.2f}× the Featured average. Questions get into the Featured tier and stall; quoted ledes get in and overperform.</p>
      <div class="chart-wrap">{c2}</div>
      <table class="findings">
        <thead><tr><th>Formula</th><th>n</th><th>Featured rate</th><th>Lift</th><th>Within-Featured median</th></tr></thead>
        <tbody>
          {_t2}
        </tbody>
      </table>
      <h3>Featured placement drives reach — not reading depth</h3>
      <p>Featured articles average {feat_at.median():.0f} seconds of active reading time versus {nfeat_at.median():.0f} seconds for non-Featured articles. The difference is statistically significant (Mann-Whitney p&lt;0.0001). Apple's editorial promotion drives discovery; readers who find an article because the algorithm surfaced it are slightly less engaged than readers who sought it out. For the variant allocation model, Featured status is a reach signal — not a content depth signal.</p>
      <p class="caveat">All {N_AN:,} Apple News articles (2025). Chi-square test vs. all other formula types combined. Active time: n={len(an_eng):,} articles with valid active time data.</p>
    </div>
  </details>

  <!-- SMARTNEWS -->
  <details id="smartnews" class="finding-card">
    <summary class="finding-header">
      <span class="finding-chevron">▶</span>
      <div class="finding-summary">
        <p class="section-label">Finding 3 · SmartNews Allocation</p>
        <h2>SmartNews Local delivers {LOCAL_LIFT} the views of average Top-feed articles. Entertainment gets {_ent_local_ratio}× more articles and performs like average.</h2>
      </div>
    </summary>
    <div class="finding-body">
      <div class="callout">
        <strong>Action:</strong> Flag this finding to the distribution team. Entertainment is consuming {_r4_ent['pct_share']:.1%} of SmartNews article volume at barely-above-baseline ROI. Local and U.S. National channels deliver {_r4_loc['lift']:.0f}× and {_r4_us['lift']:.0f}× the views at a fraction of the volume — this is a reallocation opportunity, not a content quality problem.
        <br><br><em>Caveat:</em> Articles in Local and U.S. channels are likely higher-quality breaking/civic stories that would perform well regardless of channel. Channel assignment partly reflects content type.
      </div>
      <p>SmartNews category channel data reveals a severe allocation mismatch. Articles appearing in the Local channel have a median of {_r4_loc['median_views']:,.0f} total views. Articles in the U.S. National channel: {_r4_us['median_views']:,.0f} views. The Top feed baseline: {_r4_top['median_views']:,.0f} views. World ({_r4_wld['lift']:.1f}×) and Health ({_r4_hlth['lift']:.1f}×) channels also punch well above baseline at modest volume. Meanwhile, Entertainment — which accounts for {_r4_ent['pct_share']:.1%} of all SmartNews articles — delivers only {_r4_ent['median_views']:,.0f} views median, barely above baseline.</p>
      <div class="chart-wrap">{c3}</div>
      <table class="findings">
        <thead><tr><th>Channel</th><th>Article count</th><th>% of total</th><th>Median views</th><th>Lift vs. Top feed</th></tr></thead>
        <tbody>
          {_t3}
        </tbody>
      </table>
      <p class="caveat">SmartNews 2025 (n=38,251 article-channel rows). Category columns contain channel-specific view counts; non-zero = article appeared in that channel. 2026 export lacks category breakdown.</p>
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
        <strong>Action:</strong> The highest-leverage notification formula is: <em>[Person's] [relationship/role] [reaction/new development]</em> — e.g., "Savannah Guthrie's husband breaks silence…", "Mike Tomlin's wife was frantic in 911 call." Use full names. Write longer notifications (more context = more clicks). Reserve "exclusive" for actual exclusives. Avoid question format.
      </div>
      <p>Across {N_NOTIF} Apple News push notifications (Jan–Feb 2026, median CTR {CTR_MED}), four features show statistically significant positive effects. The "exclusive" tag is the strongest at {EXCL_LIFT} lift — and it is not primarily a Savannah Guthrie effect: only 4 of {_r5_excl['n_true']} exclusive-tagged notifications mention Guthrie. The possessive framing signal is the most actionable new finding: notifications that contain a full named person AND a possessive construction ("Savannah Guthrie's husband breaks silence", "Bill Cosby's longtime rep 'blindsided'", "Mike Tomlin's wife was frantic") drive {_r5_poss['lift']:.2f}× CTR vs. {_r5_full['lift']:.2f}× for merely naming someone. The possessive signals insider access and relational proximity — not just name recognition. Question format hurts at {_r5_q['lift']:.2f}×, consistent with the Apple News article finding.</p>
      <div class="chart-wrap">{c4}</div>
      <table class="findings">
        <thead><tr><th>Feature</th><th>n (present)</th><th>Median CTR (present)</th><th>Median CTR (absent)</th><th>Lift</th><th>p</th></tr></thead>
        <tbody>
          {_t4}
        </tbody>
      </table>
      <h3>The serial/escalating story as a content type</h3>
      <p>The top 10 notifications in the dataset by CTR (ranging 6.5–9.6%) are dominated by a single ongoing story: Nancy Guthrie's disappearance and its connection to Savannah Guthrie. This isn't just a confound — it defines a content type worth naming: <strong>the serial/escalating story with a celebrity anchor</strong>. The formula is: possessive named entity + new development + escalating stakes, published in installments. Each installment compounds prior audience investment.</p>
      <p>The structural recipe: <em>"[Celebrity]'s [family member/associate] [new disclosure/development]."</em> Each piece should signal what's new ("breaks silence", "reveals", "first interview") rather than restating what's known. Readers who clicked one installment return for the next at elevated rates — this is the closest thing in the notification data to a repeatable high-CTR format.</p>
      <p><em>Signal interference caveat:</em> The Guthrie cluster accounts for the most extreme CTRs in the dataset (n=16 notifications, many above 5%). It's not possible to fully separate the formula from the underlying story interest — a different serial story using identical framing might not replicate these exact numbers. The possessive + full name signal (1.86× lift, p&lt;0.001) holds across non-Guthrie stories, but the very top of the distribution is Guthrie-driven.</p>
      <h3>What doesn't move the needle in notifications</h3>
      <p>Neither "contains a number" (n={_r5_num['n_true']}, {_r5_num['lift']:.2f}×, p={_r5_num['p']:.2f}) nor "attribution" — says/told/reports (n={_r5_attr['n_true']}, {_r5_attr['lift']:.2f}×, p={_r5_attr['p']:.2f}) — significantly affect notification CTR. Notably, numbers in notifications are neutral, while number leads in Apple News articles significantly underperform. The same signal doesn't carry across contexts.</p>
      <p class="caveat">Apple News Notifications, Jan–Feb 2026 (n={N_NOTIF} with valid CTR). Mann-Whitney U. The Savannah Guthrie story cluster (n=16) drove outsized CTR; noted as a serial-installment content type distinct from formula effects. Only 4 of 16 exclusive-tagged notifications overlap with the Guthrie cluster.</p>
    </div>
  </details>

  <!-- TOPICS -->
  <details id="topics" class="finding-card">
    <summary class="finding-header">
      <span class="finding-chevron">▶</span>
      <div class="finding-summary">
        <p class="section-label">Finding 5 · Platform Separation</p>
        <h2>{an_top_label} leads Apple News. {sn_top_label} leads SmartNews. Sports ranks #{sports_an_rank} on Apple News and last on SmartNews — the starkest evidence that these platforms serve different audiences entirely.</h2>
      </div>
    </summary>
    <div class="finding-body">
      <div class="callout">
        <strong>Action:</strong> Write platform-specific variant briefs — not generic copy deployed everywhere. Apple News: sports, weather, serial/escalating framing. SmartNews: local/civic, nature/wildlife, business. These platforms are not seeing the same articles ({excl_sn:.0%} of SmartNews content appears nowhere else), and their audiences are not the same readers.
      </div>
      <p>Topic performance diverges sharply — and in many cases inverts — by platform. {an_top_label} leads Apple News ({an_top_med:,} median views), followed by {an_2nd_label} ({an_2nd_med:,}). On SmartNews, {sn_top_label.lower()} leads ({sn_top_med} median views), while sports ranks last at {sports_sn_med} views — the same sports content that ranks #{sports_an_rank} on Apple News ({sports_an_med:,} median views) performs worst on SmartNews ({sports_sn_idx:.2f}x platform median). Nature/wildlife shows the same inversion in reverse: bottom of Apple News ({nw_an_idx:.2f}x) but near the top of SmartNews ({nw_sn_idx:.2f}x). Among the top 30 most frequent words in top-quartile headlines on each platform, only {kw_overlap_n} appear on both lists{f" ({', '.join(sorted(kw_overlap))})" if kw_overlap_n > 0 else ""} — generic reporting terms, not topical overlap.</p>
      <div class="chart-wrap">{c5}</div>
      <h3>Platforms are drawing from separate content pools</h3>
      <p>Exact title matching across all four platforms confirms: {overlap_all4} articles appear on all four simultaneously. Only {overlap_3plus} appear on three or more. Each platform operates on largely independent content.</p>
      <table class="findings">
        <thead><tr><th>Platform</th><th>Unique titles</th><th>Exclusive to this platform</th><th>Note</th></tr></thead>
        <tbody>
          <tr><td>SmartNews</td><td>{N_SN_UNIQ:,}</td><td>{excl_sn:.0%}</td><td>Highest exclusivity — nearly closed ecosystem</td></tr>
          <tr><td>MSN</td><td>{N_MSN_UNIQ:,}</td><td>{excl_msn:.0%}</td><td>December only; seasonal news cycle increases overlap</td></tr>
          <tr><td>Apple News</td><td>{N_AN_UNIQ:,}</td><td>{excl_an:.0%}</td><td>Small amount of title sharing with Yahoo/SmartNews</td></tr>
          <tr><td>Yahoo</td><td>{N_YAHOO_UNIQ:,}</td><td>{excl_yahoo:.0%}</td><td>Some overlap with Apple News and SmartNews</td></tr>
        </tbody>
      </table>
      <p class="caveat">Topic tagged via regex classifier applied to headline text. Index = median views / platform overall median. Apple News 2025 (n={N_AN:,}); SmartNews 2025 (n={N_SN:,}). Platform exclusivity: exact normalised title match across all four 2025 datasets. MSN data is December 2025 only. Keyword overlap: top 30 words by frequency in top-quartile articles per platform, after English stopword removal.</p>
    </div>
  </details>

  <!-- ALLOCATION -->
  <details id="allocation" class="finding-card">
    <summary class="finding-header">
      <span class="finding-chevron">▶</span>
      <div class="finding-summary">
        <p class="section-label">Finding 6 · Headline Variance by Topic</p>
        <h2>Crime shows the widest outcome spread on both platforms. On Apple News, business is second. On SmartNews, local/civic variance reflects the channel placement effect.</h2>
      </div>
    </summary>
    <div class="finding-body">
      <div class="callout">
        <strong>Action:</strong> Concentrate variant production on high-median × high-variance topic combinations — where headline optimization has the most room to move performance. For Apple News: crime and business. For SmartNews: crime and local/civic (where framing that signals geographic/civic relevance may influence channel placement). Low-variance topics — nature/wildlife on Apple News, weather on SmartNews — have less to gain from headline optimization; the story drives performance more than the headline does.
      </div>
      <p>The chart below shows the IQR ÷ median ratio (a robust spread measure) for each topic × platform combination. A ratio of 3.0 means the difference between the 25th and 75th percentile articles in that topic is 3× the median — i.e., the top half significantly outperforms the bottom half. Where this ratio is high, headline optimization has the most room to lift performance. Where it is low, outcomes are similar regardless of how the headline is written.</p>
      <div class="chart-wrap">{c6}</div>
      <p>On Apple News, crime (cv=3.9) and business (cv=3.8) show the highest spread — a wide gap between underperforming and outperforming headlines within those topics. Nature/wildlife (cv=2.2) is the most consistent: these stories perform similarly regardless of headline, suggesting story quality drives more of the variance than framing does. On SmartNews, local/civic (cv=31) and business (cv=14) show extreme variance — driven by the channel allocation effect identified in Finding 3. Most local/civic articles on SmartNews get very few views, but the small fraction that land in the Local channel reach 16,000+ median views. The variance reflects the value of channel placement, not just headline quality.</p>
      <p class="caveat">IQR = interquartile range (75th percentile minus 25th percentile). IQR/median is a scale-free spread measure robust to the skewed views distribution. Topic tagged via regex classifier. Apple News 2025; SmartNews 2025. Topics with fewer than 10 articles on either platform excluded.</p>
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
      <p>The Apple News 2025 dataset includes both Total Views and average active time per article — a rare combination that makes it possible to test the "clicks = quality" assumption directly. The result: Pearson r = {r_views_at:.3f} (p = {p_views_at:.2f}), Spearman r = {r_views_at_sp:.3f} (p = {p_views_at_sp:.2f}). Both methods agree: across {len(an_eng):,} articles, views and reading time are statistically independent. The view count spans a {views_range_x:,}× range across deciles; active time moves only {at_range_s:.0f} seconds (51–60s).</p>
      <div class="chart-wrap">{c7}</div>
      <table class="findings">
        <thead><tr><th>Metric</th><th>Correlation with Total Views</th><th>What it measures</th></tr></thead>
        <tbody>
          <tr><td>Avg. active time</td><td>r = {r_views_at:.3f} (p = {p_views_at:.2f}, not significant)</td><td>Depth of the current read</td></tr>
          <tr><td>Saves</td><td>r = {r_saves:.2f} (strong)</td><td>Intent to return / bookmark behavior</td></tr>
          <tr><td>Likes</td><td>r = {r_likes:.2f} (strong)</td><td>Affirmation / social signal</td></tr>
          <tr><td>Article shares</td><td>r = {r_shares:.2f} (strong)</td><td>Distribution / word of mouth</td></tr>
        </tbody>
      </table>
      <p>Saves, likes, and shares all scale strongly with views — they measure the same dimension (reach and engagement breadth). Active time measures an orthogonal dimension: whether the reader who clicked actually read. High-view articles are not better-read articles. The two signals are statistically uncoupled.</p>
      <p>Featured articles illustrate this split directly: 6.74× median view lift, but {feat_at.median():.0f}s active time vs. {nfeat_at.median():.0f}s for non-Featured (p&lt;0.0001). And subscribers read for less time on average ({sub_at_med:.0f}s) than non-subscribers ({nsub_at_med:.0f}s) — subscribers are likely efficient, high-frequency readers who scan and move on, not a quality problem but a behavioral difference that matters when comparing paywalled vs. free article metrics.</p>
      <p class="caveat">Apple News 2025 (n={len(an_eng):,} articles with valid active time). {at_low_n} articles have active time &lt;10s (likely tracker bounces); {at_high_n} have &gt;300s (likely left-open tabs) — these are not filtered and represent ~{(at_low_n+at_high_n)/len(an_eng):.0%} of records. Saves/likes/shares n excludes rows missing that metric.</p>
    </div>
  </details>

</div>

<script>
function toggleAll() {{
  const cards = document.querySelectorAll('.finding-card');
  const anyOpen = Array.from(cards).some(d => d.open);
  cards.forEach(d => d.open = !anyOpen);
  document.getElementById('expand-btn').textContent = anyOpen ? 'Expand all' : 'Collapse all';
}}

// Auto-open finding when navigating via nav link or hash
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
  <p>McClatchy CSA · T1 Headline Performance Analysis · Phase 2 · {REPORT_DATE}</p>
  <p style="margin-top: 0.5rem;">
    <a href="archive/">Past runs</a> &nbsp;·&nbsp;
    Data: Tarrow T1 Headline Performance Sheet · Apple News, SmartNews, MSN, Yahoo
  </p>
</footer>

</body>
</html>"""

out = Path("docs/index.html")
out.write_text(html, encoding="utf-8")
print(f"✓ Site written to {out}  ({len(html):,} chars)")
