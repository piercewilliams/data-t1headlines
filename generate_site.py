"""
T1 Headline Analysis — Phase 2 site generator
Run: python3 generate_site.py
Output: docs/index.html
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import re
import warnings
from pathlib import Path
from scipy import stats

warnings.filterwarnings("ignore")

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
print("Loading data…")
an   = pd.read_excel("Top syndication content 2025.xlsx", sheet_name="Apple News")
sn   = pd.read_excel("Top syndication content 2025.xlsx", sheet_name="SmartNews")
notif = pd.read_excel("Top Stories 2026 Syndication.xlsx", sheet_name="Apple News Notifications")

an["is_featured"] = an["Featured by Apple"].fillna("No") == "Yes"
an["formula"] = an["Article"].apply(classify_formula)
an["topic"]   = an["Article"].apply(tag_topic)

CATS = ["Top","Entertainment","Lifestyle","U.S.","Business","World",
        "Technology","Science","Politics","Health","Local","Football","LGBTQ"]
for cat in CATS:
    sn[cat] = pd.to_numeric(sn[cat], errors="coerce").fillna(0)

notif = notif.dropna(subset=["CTR"]).copy()


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
    lift = med / overall_median_nf
    if f != "untagged" and len(grp) >= 5:
        _, p = stats.mannwhitneyu(grp, baseline, alternative="two-sided")
    else:
        p = None
    q1_rows.append(dict(formula=f, label=label, n=len(grp), median=med, lift=lift, p=p))

df_q1 = pd.DataFrame(q1_rows).sort_values("median")

# ── Q2: Featured rate per formula ─────────────────────────────────────────────
overall_feat_rate = an["is_featured"].mean()
q2_rows = []
for f, label in FORMULA_LABELS.items():
    grp = an[an["formula"] == f]
    if len(grp) == 0: continue
    feat_rate = grp["is_featured"].mean()
    q2_rows.append(dict(formula=f, label=label, n=len(grp),
                        featured_rate=feat_rate,
                        featured_lift=feat_rate / overall_feat_rate))

df_q2 = pd.DataFrame(q2_rows).sort_values("featured_rate")

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

# ── Q5: Notification CTR features ────────────────────────────────────────────
print("Computing Q5…")
def extract_features(text):
    t  = str(text).strip()
    tl = t.lower()
    return {
        "Full name present":      bool(re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", t)),
        "Possessive named entity":bool(re.match(r"^[A-Z][a-zA-Z\-]+[\u2019\']s\s", t)),
        "Contains number":        bool(re.search(r"\b\d+\b", t)),
        "Question format":        t.rstrip().endswith("?"),
        "Short (≤80 chars)":      len(t) <= 80,
        "'Exclusive' tag":        bool(re.search(r"\bexclusive\b", tl)),
        "Attribution (says/told)":bool(re.search(r"\bsays?\b|\btells?\b|\breports?\b", tl)),
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
sn["topic"] = sn["title"].apply(tag_topic)
sn_topic = sn.groupby("topic")["article_view"].median().reset_index()
sn_topic.columns = ["topic", "sn_median"]
topic_df = an_topic.merge(sn_topic, on="topic")
TOPIC_LABELS = {
    "weather":"Weather","sports":"Sports","crime":"Crime","business":"Business",
    "local_civic":"Local/Civic","lifestyle":"Lifestyle",
    "nature_wildlife":"Nature/Wildlife","other":"Other"
}
topic_df["label"] = topic_df["topic"].map(TOPIC_LABELS)
topic_df = topic_df.sort_values("an_median", ascending=True)

an_overall = an["Total Views"].median()
sn_overall = sn["article_view"].median()
topic_df["an_idx"] = (topic_df["an_median"] / an_overall).tolist()
topic_df["sn_idx"] = (topic_df["sn_median"] / sn_overall).tolist()

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


# ── Render charts to HTML strings ────────────────────────────────────────────
def chart_html(fig):
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"responsive": True})


c1 = chart_html(fig1)
c2 = chart_html(fig2)
c3 = chart_html(fig3)
c4 = chart_html(fig4)
c5 = chart_html(fig5)


# ── Key stats ─────────────────────────────────────────────────────────────────
N_AN        = 3039
N_SN        = 38251
N_NOTIF     = len(notif)
PLATFORMS   = 4
WTN_FEAT    = "62%"
LOCAL_LIFT  = "108×"
EXCL_LIFT   = "2.49×"


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
  </div>
  <span class="spacer"></span>
  <span class="date">Phase 2 · March 2026</span>
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
  <section id="formulas">
    <p class="section-label">Finding 1 · Apple News Formulas</p>
    <h2>Number leads and questions consistently underperform. "Here's" and possessive named entities lead — but sample sizes are small.</h2>
    <p>Across {len(nf):,} non-Featured articles, three formula types significantly underperform the baseline: number leads (0.70×, p&lt;0.001), question format (0.55×, p&lt;0.001), and quoted ledes (0.66×, p&lt;0.001). The better-performing formulas — "Here's / Here are" (3.20×) and possessive named entity (2.08×) — show strong directional signal but lack statistical significance at current sample sizes (n=16 and n=75 respectively).</p>
    <div class="chart-wrap">{c1}</div>
    <div class="callout">
      <strong>Production implication:</strong> Avoid number leads and question formats for standard Apple News headlines. "Here's how…" and "[City]'s [development]" constructions are worth testing more deliberately to build sample size.
    </div>
    <p class="caveat">Non-Featured articles only (n={len(nf):,}). Featured articles removed to isolate headline signal from editorial selection effect. Mann-Whitney U vs. untagged baseline. * p&lt;0.05  ** p&lt;0.01  *** p&lt;0.001</p>
  </section>

  <!-- FEATURING -->
  <section id="featuring">
    <p class="section-label">Finding 2 · Featured by Apple</p>
    <h2>"What to know" headlines get Featured at 62% — more than double the 27% baseline rate.</h2>
    <p>Among the {an["is_featured"].sum()} Featured articles in our dataset, "What to know" headlines are dramatically overrepresented: 13 of 21 (62%) were Featured. The overall Featured rate is 26.7%. This is the strongest statistically significant formula signal in the dataset (χ²=11.9, p=0.0006).</p>
    <p>Question-format headlines are also Featured more often than expected (37%, 1.39× lift, p=0.005) — but they significantly underperform other Featured articles once selected. Apple's editors favor questions; the format itself doesn't follow through on views.</p>
    <div class="chart-wrap">{c2}</div>
    <table class="findings">
      <thead><tr><th>Formula</th><th>n</th><th>Featured rate</th><th>Lift</th><th>Within-Featured median</th></tr></thead>
      <tbody>
        <tr><td><span class="tag tag-green">★</span>What to know</td><td>21</td><td>62%</td><td>2.32×</td><td>16,933 views (1.55× Featured avg)</td></tr>
        <tr><td>Quoted lede</td><td>187</td><td>33%</td><td>1.22×</td><td>17,608 views (1.61× Featured avg)</td></tr>
        <tr><td>Question</td><td>146</td><td>37%</td><td>1.39×</td><td>6,574 views (0.60× Featured avg)</td></tr>
        <tr><td>Number lead</td><td>175</td><td>18%</td><td>0.69×</td><td>11,410 views (1.05× Featured avg)</td></tr>
      </tbody>
    </table>
    <div class="callout">
      <strong>Production implication:</strong> "What to know" is the fastest path to Featured placement. Apply it to high-stakes local stories — health alerts, weather emergencies, civic events. The data shows Apple's editors strongly favor this format for surfacing to subscribers.
    </div>
    <p class="caveat">All 3,039 Apple News articles (2025). Chi-square test vs. all other formula types combined.</p>
  </section>

  <!-- SMARTNEWS -->
  <section id="smartnews">
    <p class="section-label">Finding 3 · SmartNews Allocation</p>
    <h2>SmartNews Local delivers 108× the views of average Top-feed articles. Entertainment gets 12× more articles and performs like average.</h2>
    <p>SmartNews category channel data reveals a severe allocation mismatch. Articles appearing in the Local channel have a median of 16,593 total views. Articles in the U.S. National channel: 11,153 views. The Top feed baseline: 153 views. Meanwhile, Entertainment — which accounts for 35.9% of all SmartNews articles — delivers only 224 views median, barely above baseline.</p>
    <div class="chart-wrap">{c3}</div>
    <table class="findings">
      <thead><tr><th>Channel</th><th>Article count</th><th>% of total</th><th>Median views</th><th>Lift vs. Top feed</th></tr></thead>
      <tbody>
        <tr><td><span class="tag tag-green">↑</span>Local</td><td>1,097</td><td>2.9%</td><td>16,593</td><td>108×</td></tr>
        <tr><td><span class="tag tag-green">↑</span>U.S. National</td><td>909</td><td>2.4%</td><td>11,153</td><td>73×</td></tr>
        <tr><td>Football</td><td>276</td><td>0.7%</td><td>1,934</td><td>12.6×</td></tr>
        <tr><td>Business</td><td>125</td><td>0.3%</td><td>1,933</td><td>12.6×</td></tr>
        <tr><td><span class="tag tag-red">↓</span>Entertainment</td><td>13,713</td><td>35.9%</td><td>224</td><td>1.46×</td></tr>
        <tr><td>Top feed (baseline)</td><td>34,006</td><td>88.9%</td><td>153</td><td>1.00×</td></tr>
      </tbody>
    </table>
    <div class="callout">
      <strong>Caveat:</strong> Articles appearing in Local and U.S. channels are likely high-quality breaking or civic news articles that would perform well regardless. The channel assignment partly reflects content type, not just headline formula. That said, the magnitude of the gap — 108× — and the scale of the Entertainment over-investment make this a clear reallocation signal.
    </div>
    <p class="caveat">SmartNews 2025 (n=38,251 article-channel rows). Category columns contain channel-specific view counts; non-zero = article appeared in that channel. 2026 export lacks category breakdown.</p>
  </section>

  <!-- NOTIFICATIONS -->
  <section id="notifications">
    <p class="section-label">Finding 4 · Push Notification CTR</p>
    <h2>"Exclusive" delivers 2.49× CTR lift. Questions in notifications hurt performance. Full names help.</h2>
    <p>Across {N_NOTIF} Apple News push notifications (Jan–Feb 2026, median CTR 1.68%), three features show statistically significant effects. The "exclusive" tag is the strongest signal at 2.49× lift — though it is partly confounded by the Savannah Guthrie story cluster, which drove some of the highest CTRs in the dataset. Even excluding the Guthrie stories, exclusive-tagged notifications consistently outperform. Full name presence (e.g., "Savannah Guthrie" vs. "TV anchor") adds 1.21× lift. Question-format notifications hurt CTR at 0.64× — consistent with the Apple News article finding.</p>
    <div class="chart-wrap">{c4}</div>
    <table class="findings">
      <thead><tr><th>Feature</th><th>n (present)</th><th>Median CTR (present)</th><th>Median CTR (absent)</th><th>Lift</th><th>p</th></tr></thead>
      <tbody>
        <tr><td><span class="tag tag-green">↑</span>'Exclusive' tag</td><td>16</td><td>4.01%</td><td>1.61%</td><td>2.49×</td><td>&lt;0.001 ***</td></tr>
        <tr><td><span class="tag tag-green">↑</span>Full name present</td><td>196</td><td>1.88%</td><td>1.55%</td><td>1.21×</td><td>0.001 ***</td></tr>
        <tr><td><span class="tag tag-red">↓</span>Question format</td><td>23</td><td>1.12%</td><td>1.75%</td><td>0.64×</td><td>&lt;0.001 ***</td></tr>
        <tr><td><span class="tag tag-red">↓</span>Short (≤80 chars)</td><td>217</td><td>1.50%</td><td>2.44%</td><td>0.61×</td><td>&lt;0.001 ***</td></tr>
      </tbody>
    </table>
    <div class="callout">
      <strong>Production implication:</strong> Use full names in notification copy. Write longer notifications (more detail = more context = more clicks). Reserve "exclusive" for actual exclusives — the tag carries genuine signal. Avoid question format in notification copy.
    </div>
    <p class="caveat">Apple News Notifications, Jan–Feb 2026 (n={N_NOTIF} with valid CTR). Mann-Whitney U. The Savannah Guthrie story cluster (n=17) drove outsized CTR; noted as a serial-installment content type distinct from formula effects.</p>
  </section>

  <!-- TOPICS -->
  <section id="topics">
    <p class="section-label">Finding 5 · Topic × Platform</p>
    <h2>Sports dominates Apple News. Local/Civic leads SmartNews. Zero keyword overlap between the two platforms.</h2>
    <p>Topic performance diverges sharply by platform. Weather and sports are the top performers on Apple News (median 5,094 and 4,726 views respectively). On SmartNews, local/civic content leads (median 273 views vs. platform median of 145), while sports ranks last at 78 views. These platforms are operating as distinct content ecosystems — a finding reinforced by zero overlap between Apple News top-quartile keywords and SmartNews top-quartile keywords.</p>
    <div class="chart-wrap">{c5}</div>
    <div class="callout">
      <strong>Production implication:</strong> Headline and variant strategies should be platform-specific, not cross-platform. A sports headline optimized for Apple News audience behavior is unlikely to perform on SmartNews — and vice versa. The zero keyword overlap confirms these audiences select for different content signals entirely.
    </div>
    <p class="caveat">Topic tagged via regex classifier applied to headline text. Index = median views / platform overall median. Apple News 2025 (n=3,039); SmartNews 2025 (n=38,251).</p>
  </section>

</div>

<footer>
  <p>McClatchy CSA · T1 Headline Performance Analysis · Phase 2 · March 2026</p>
  <p style="margin-top: 0.5rem;">
    <a href="v1/">Phase 1 findings</a> &nbsp;·&nbsp;
    Data: Tarrow T1 Headline Performance Sheet · Apple News, SmartNews, MSN, Yahoo
  </p>
</footer>

</body>
</html>"""

out = Path("docs/index.html")
out.write_text(html, encoding="utf-8")
print(f"✓ Site written to {out}  ({len(html):,} chars)")
