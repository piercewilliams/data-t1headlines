"""
Comprehensive platform format guide analysis
McClatchy T1 headline data: 2025 full year + 2026 Jan–Mar
"""

import re
import sys
import warnings
import pandas as pd
import numpy as np
from scipy import stats

warnings.filterwarnings("ignore")

# ── helpers ────────────────────────────────────────────────────────────────────

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
    if re.search(r"\b(trump|biden|congress|senate|white house|president|governor|election|vote|campaign|ballot|democrat|republican|gop|legislation|bill|policy|lawmaker|politician)\b", t): return "politics"
    if re.search(r"\b(school|student|teacher|education|college|university|city|county|state|local|community|neighborhood)\b", t): return "local_civic"
    if re.search(r"\b(restaurant|food|eat|chef|menu|recipe|bar|coffee|dining|hotel|travel|beach|park|festival|concert)\b", t): return "lifestyle"
    if re.search(r"\b(animal|creature|species|wildlife|shark|bear|alligator|snake|bird|dog|cat|pet)\b", t): return "nature_wildlife"
    return "other"

def rank_biserial_r(group1, group2):
    """Rank-biserial correlation as effect size for Mann-Whitney U."""
    u, _ = stats.mannwhitneyu(group1, group2, alternative="two-sided")
    n1, n2 = len(group1), len(group2)
    return 2 * u / (n1 * n2) - 1

def mw_test(focal, baseline, label="focal"):
    """Run Mann-Whitney U two-sided; return stat, p, r."""
    if len(focal) < 5 or len(baseline) < 5:
        return None, None, None
    u, p = stats.mannwhitneyu(focal, baseline, alternative="two-sided")
    r = rank_biserial_r(focal, baseline)
    return u, p, r

def sig_stars(p):
    if p is None: return "n/a"
    if p < 0.001: return "***"
    if p < 0.01:  return "**"
    if p < 0.05:  return "*"
    return "ns"

def zscore_normalize(series):
    mu, sd = series.mean(), series.std()
    if sd == 0: return series * 0
    return (series - mu) / sd

def section_header(title):
    print()
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)

def subsection(title):
    print()
    print(f"--- {title} ---")

# ── load data ─────────────────────────────────────────────────────────────────

DATA_2025 = "Top syndication content 2025.xlsx"
DATA_2026 = "Top Stories 2026 Syndication.xlsx"

print("Loading data files…")

an25  = pd.read_excel(DATA_2025, sheet_name="Apple News")
ann25 = pd.read_excel(DATA_2025, sheet_name="Apple News notifications")
sn25  = pd.read_excel(DATA_2025, sheet_name="SmartNews")

an26  = pd.read_excel(DATA_2026, sheet_name="Apple News")
ann26 = pd.read_excel(DATA_2026, sheet_name="Apple News Notifications")
sn26  = pd.read_excel(DATA_2026, sheet_name="SmartNews")

print(f"  Apple News 2025: {an25.shape}")
print(f"  Apple News 2026: {an26.shape}")
print(f"  AN Notifications 2025: {ann25.shape}")
print(f"  AN Notifications 2026: {ann26.shape}")
print(f"  SmartNews 2025: {sn25.shape}")
print(f"  SmartNews 2026: {sn26.shape}")

# ── normalised view columns ────────────────────────────────────────────────────

# Apple News: headline in "Article", views in "Total Views"
# Need to handle 2025 uses "Channel", 2026 uses "Brand"

an25 = an25.rename(columns={"Channel": "brand"})
an26 = an26.rename(columns={"Brand": "brand"})

# Combine Apple News; normalize within year
an25 = an25.copy()
an26 = an26.copy()
an25["year"] = 2025
an26["year"] = 2026

an25["views_norm"] = zscore_normalize(pd.to_numeric(an25["Total Views"], errors="coerce").dropna().reindex(an25.index))
an26["views_norm"] = zscore_normalize(pd.to_numeric(an26["Total Views"], errors="coerce").dropna().reindex(an26.index))

an_all = pd.concat([an25, an26], ignore_index=True)
an_all["headline"] = an_all["Article"].astype(str).str.strip()
an_all["char_len"] = an_all["headline"].str.len()
an_all["formula"]  = an_all["headline"].apply(classify_formula)
an_all["topic"]    = an_all["headline"].apply(tag_topic)
an_all["Total Views"] = pd.to_numeric(an_all["Total Views"], errors="coerce")
an_all = an_all.dropna(subset=["Total Views", "char_len"])

print(f"\nCombined Apple News (clean): {an_all.shape[0]} rows")

# SmartNews 2025: headline in "title", views in "article_view"
sn25 = sn25.copy()
sn25["headline"]   = sn25["title"].astype(str).str.strip()
sn25["char_len"]   = sn25["headline"].str.len()
sn25["formula"]    = sn25["headline"].apply(classify_formula)
sn25["topic"]      = sn25["headline"].apply(tag_topic)
sn25["article_view"] = pd.to_numeric(sn25["article_view"], errors="coerce")
sn25 = sn25.dropna(subset=["article_view", "char_len"])
sn25["views_norm"] = zscore_normalize(sn25["article_view"])

print(f"SmartNews 2025 (clean): {sn25.shape[0]} rows")

# SmartNews 2026: also has title + article_view
sn26 = sn26.copy()
sn26["headline"]   = sn26["title"].astype(str).str.strip()
sn26["char_len"]   = sn26["headline"].str.len()
sn26["article_view"] = pd.to_numeric(sn26["article_view"], errors="coerce")
sn26 = sn26.dropna(subset=["article_view", "char_len"])
sn26["views_norm"] = zscore_normalize(sn26["article_view"])
print(f"SmartNews 2026 (clean): {sn26.shape[0]} rows")

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 1: Apple News — character count vs. views
# ══════════════════════════════════════════════════════════════════════════════
section_header("ANALYSIS 1: Apple News — Character Count vs. Views (2025+2026)")

print(f"\nData source: Apple News 2025 + 2026 combined, n={len(an_all)}")
print("Views normalized (z-score) within each year.")

bins  = [0, 59, 79, 110, 130, 9999]
labels = ["<60", "60–79", "80–110", "111–130", "131+"]
an_all["char_bin"] = pd.cut(an_all["char_len"], bins=bins, labels=labels)

bin_stats = (
    an_all.groupby("char_bin", observed=True)["views_norm"]
    .agg(n="count", median="median", mean="mean")
    .reset_index()
)
print()
print(f"{'Bin':<12} {'n':>6} {'Median norm views':>18} {'Mean norm views':>16}")
print("-" * 54)
for _, row in bin_stats.iterrows():
    print(f"{row['char_bin']:<12} {row['n']:>6} {row['median']:>18.4f} {row['mean']:>16.4f}")

# Tests
focal_bin   = an_all[an_all["char_bin"] == "80–110"]["views_norm"].dropna()
other_bins  = an_all[an_all["char_bin"] != "80–110"]["views_norm"].dropna()
short_bins  = an_all[an_all["char_len"] < 80]["views_norm"].dropna()
long_bins   = an_all[an_all["char_len"] > 110]["views_norm"].dropna()

subsection("Mann-Whitney U Tests: 80–110 bin vs. comparisons")
for label, compare in [("all other bins", other_bins), ("<80 chars", short_bins), (">110 chars", long_bins)]:
    u, p, r = mw_test(focal_bin, compare)
    direction = "higher" if focal_bin.median() > compare.median() else "lower"
    print(f"  80–110 vs {label}: U={u:.0f}, p={p:.4f} {sig_stars(p)}, r={r:.3f} ({direction})")

print()
print("VERDICT (guide claim: 80–110 chars recommended for Apple News):")
p_val = mw_test(focal_bin, other_bins)[1]
if p_val < 0.05:
    direction = "ABOVE" if focal_bin.median() > other_bins.median() else "BELOW"
    print(f"  SUPPORTED — 80–110 bin is statistically {direction} all others (p={p_val:.4f})")
else:
    print(f"  NOT SUPPORTED — 80–110 bin shows no significant difference from others (p={p_val:.4f})")

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 2: SmartNews — character count vs. views
# ══════════════════════════════════════════════════════════════════════════════
section_header("ANALYSIS 2: SmartNews 2025 — Character Count vs. Views")

print(f"\nData source: SmartNews 2025 article-level, n={len(sn25)}")
print("Views = article_view (normalized z-score within dataset)")

bins_sn  = [0, 59, 79, 99, 120, 9999]
labels_sn = ["<60", "60–79", "80–99", "100–120", "121+"]
sn25["char_bin"] = pd.cut(sn25["char_len"], bins=bins_sn, labels=labels_sn)

bin_stats_sn = (
    sn25.groupby("char_bin", observed=True)["views_norm"]
    .agg(n="count", median="median", mean="mean")
    .reset_index()
)
print()
print(f"{'Bin':<12} {'n':>6} {'Median norm views':>18} {'Mean norm views':>16}")
print("-" * 54)
for _, row in bin_stats_sn.iterrows():
    print(f"{row['char_bin']:<12} {row['n']:>6} {row['median']:>18.4f} {row['mean']:>16.4f}")

# Test <100 vs 100+
under100  = sn25[sn25["char_len"] < 100]["views_norm"].dropna()
over100   = sn25[sn25["char_len"] >= 100]["views_norm"].dropna()

subsection("Mann-Whitney U Test: <100 chars vs. 100+ chars")
u, p, r = mw_test(under100, over100)
direction = "higher" if under100.median() > over100.median() else "lower"
print(f"  <100 vs 100+: U={u:.0f}, p={p:.4f} {sig_stars(p)}, r={r:.3f} (<100 is {direction})")

# Also bin-by-bin vs next
subsection("Pairwise adjacent bin tests (SmartNews)")
bin_order = labels_sn
for i in range(len(bin_order) - 1):
    a = sn25[sn25["char_bin"] == bin_order[i]]["views_norm"].dropna()
    b = sn25[sn25["char_bin"] == bin_order[i+1]]["views_norm"].dropna()
    u, p, r = mw_test(a, b)
    if p is not None:
        d = ">" if a.median() > b.median() else "<"
        print(f"  {bin_order[i]} vs {bin_order[i+1]}: U={u:.0f}, p={p:.4f} {sig_stars(p)}, r={r:.3f}  ({bin_order[i]} median {d} {bin_order[i+1]})")

print()
print("VERDICT (guide claim: SmartNews keep under 100 characters):")
if p < 0.05 and under100.median() > over100.median():
    print(f"  SUPPORTED — <100 chars outperforms 100+ (p={p:.4f})")
elif p < 0.05 and under100.median() < over100.median():
    print(f"  CONTRADICTED — 100+ chars actually outperforms <100 (p={p:.4f})")
else:
    print(f"  NOT SIGNIFICANT — no reliable difference at the 100-char threshold (p={p:.4f})")

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 3: SmartNews — Formula Performance (excl. politics)
# ══════════════════════════════════════════════════════════════════════════════
section_header("ANALYSIS 3: SmartNews 2025 — Formula Performance (excluding politics)")

sn25_np = sn25[sn25["topic"] != "politics"].copy()
print(f"\nData source: SmartNews 2025, n={len(sn25)} → after excl. politics: n={len(sn25_np)}")

baseline_sn = sn25_np[sn25_np["formula"] == "untagged"]["views_norm"].dropna()

formula_rows = []
for formula, grp in sn25_np.groupby("formula"):
    v = grp["views_norm"].dropna()
    u, p, r = mw_test(v, baseline_sn)
    formula_rows.append({
        "formula": formula,
        "n": len(v),
        "median_norm": v.median(),
        "mean_norm":   v.mean(),
        "U": u,
        "p": p,
        "r": r,
        "sig": sig_stars(p),
    })

formula_df = pd.DataFrame(formula_rows).sort_values("median_norm", ascending=False)
print()
print(f"{'Formula':<26} {'n':>5} {'Median':>8} {'Mean':>8} {'U':>10} {'p':>8} {'sig':>4} {'r':>7}")
print("-" * 80)
for _, row in formula_df.iterrows():
    u_str = f"{row['U']:.0f}" if row['U'] is not None else "—"
    p_str = f"{row['p']:.4f}" if row['p'] is not None else "—"
    r_str = f"{row['r']:.3f}" if row['r'] is not None else "—"
    print(f"{row['formula']:<26} {row['n']:>5} {row['median_norm']:>8.4f} {row['mean_norm']:>8.4f} {u_str:>10} {p_str:>8} {row['sig']:>4} {r_str:>7}")

print()
print("VERDICT (guide claim: 'How to'/'What to Know'/service formulas good for SmartNews):")
wtk = formula_df[formula_df["formula"] == "what_to_know"]
hf  = formula_df[formula_df["formula"] == "heres_formula"]
if not wtk.empty:
    row = wtk.iloc[0]
    direction = "ABOVE" if row["median_norm"] > baseline_sn.median() else "BELOW"
    p_str = f"{row['p']:.4f}" if row['p'] is not None else "n/a"
    print(f"  what_to_know: median_norm={row['median_norm']:.4f} — {direction} baseline (untagged), p={p_str} {row['sig']}")
if not hf.empty:
    row = hf.iloc[0]
    direction = "ABOVE" if row["median_norm"] > baseline_sn.median() else "BELOW"
    p_str = f"{row['p']:.4f}" if row['p'] is not None else "n/a"
    print(f"  heres_formula: median_norm={row['median_norm']:.4f} — {direction} baseline (untagged), p={p_str} {row['sig']}")

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 4: Apple News — Formula Performance (2025+2026)
# ══════════════════════════════════════════════════════════════════════════════
section_header("ANALYSIS 4: Apple News — Formula Performance (2025+2026 combined)")

print(f"\nData source: Apple News 2025 + 2026 combined, n={len(an_all)}")
print("Views normalized z-score within each year; formulas vs. 'untagged' baseline")

baseline_an = an_all[an_all["formula"] == "untagged"]["views_norm"].dropna()

an_formula_rows = []
for formula, grp in an_all.groupby("formula"):
    v = grp["views_norm"].dropna()
    u, p, r = mw_test(v, baseline_an)
    an_formula_rows.append({
        "formula": formula,
        "n": len(v),
        "median_norm": v.median(),
        "mean_norm":   v.mean(),
        "U": u,
        "p": p,
        "r": r,
        "sig": sig_stars(p),
    })

an_formula_df = pd.DataFrame(an_formula_rows).sort_values("median_norm", ascending=False)
print()
print(f"{'Formula':<26} {'n':>5} {'Median':>8} {'Mean':>8} {'U':>10} {'p':>8} {'sig':>4} {'r':>7}")
print("-" * 80)
for _, row in an_formula_df.iterrows():
    u_str = f"{row['U']:.0f}" if row['U'] is not None else "—"
    p_str = f"{row['p']:.4f}" if row['p'] is not None else "—"
    r_str = f"{row['r']:.3f}" if row['r'] is not None else "—"
    print(f"{row['formula']:<26} {row['n']:>5} {row['median_norm']:>8.4f} {row['mean_norm']:>8.4f} {u_str:>10} {p_str:>8} {row['sig']:>4} {r_str:>7}")

sig_above = an_formula_df[(an_formula_df["sig"].isin(["*","**","***"])) & (an_formula_df["median_norm"] > baseline_an.median())]
sig_below = an_formula_df[(an_formula_df["sig"].isin(["*","**","***"])) & (an_formula_df["median_norm"] < baseline_an.median())]
print()
print(f"Significantly ABOVE baseline on Apple News: {sig_above['formula'].tolist()}")
print(f"Significantly BELOW baseline on Apple News: {sig_below['formula'].tolist()}")

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 5: Apple News — Featured picks formula distribution
# ══════════════════════════════════════════════════════════════════════════════
section_header("ANALYSIS 5: Apple News — Featured Picks Formula Distribution")

print("\nColumn for featured flag: 'Featured by Apple'")
print(f"Unique values in 'Featured by Apple': {an_all['Featured by Apple'].dropna().unique()[:20].tolist()}")

featured = an_all[an_all["Featured by Apple"].notna() & (an_all["Featured by Apple"].astype(str).str.strip() != "") & (an_all["Featured by Apple"].astype(str).str.lower() != "nan")]
print(f"\nFeatured rows: {len(featured)} / {len(an_all)} total ({100*len(featured)/len(an_all):.1f}%)")

if len(featured) > 10:
    print("\nFormula distribution — Featured vs. All articles:")
    feat_formula = featured["formula"].value_counts(normalize=True).rename("featured_%")
    all_formula  = an_all["formula"].value_counts(normalize=True).rename("all_%")
    comp = pd.concat([feat_formula, all_formula], axis=1).fillna(0)
    comp["lift"] = comp["featured_%"] / comp["all_%"].replace(0, np.nan)
    comp = comp.sort_values("lift", ascending=False)
    print()
    print(f"{'Formula':<26} {'Featured %':>12} {'Overall %':>12} {'Lift':>8}")
    print("-" * 62)
    for formula, row in comp.iterrows():
        print(f"{formula:<26} {row['featured_%']*100:>11.1f}% {row['all_%']*100:>11.1f}% {row['lift']:>8.2f}")

    print()
    print("VERDICT (guide claim: human curation favors quality/originality):")
    top_lifted = comp.head(2).index.tolist()
    print(f"  Apple editors over-index on: {top_lifted}")
    print(f"  (Lift > 1.0 means featured rate exceeds overall population rate)")
else:
    print("  Not enough featured-pick data to analyze formula distribution.")

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 6: Apple News — Topic Performance
# ══════════════════════════════════════════════════════════════════════════════
section_header("ANALYSIS 6: Apple News — Topic Performance (2025+2026)")

topic_stats_an = (
    an_all.groupby("topic")["views_norm"]
    .agg(n="count", median="median", mean="mean")
    .sort_values("median", ascending=False)
    .reset_index()
)
print()
print(f"{'Topic':<20} {'n':>6} {'Median norm views':>18} {'Mean norm views':>16}")
print("-" * 62)
for _, row in topic_stats_an.iterrows():
    print(f"{row['topic']:<20} {row['n']:>6} {row['median']:>18.4f} {row['mean']:>16.4f}")

# Test top 3 topics vs. median topic (other)
subsection("Mann-Whitney tests: top topics vs. 'other' category")
baseline_topic_an = an_all[an_all["topic"] == "other"]["views_norm"].dropna()
for topic in topic_stats_an.head(5)["topic"]:
    grp = an_all[an_all["topic"] == topic]["views_norm"].dropna()
    u, p, r = mw_test(grp, baseline_topic_an)
    if p is not None:
        d = ">" if grp.median() > baseline_topic_an.median() else "<"
        print(f"  {topic:<20}: U={u:.0f}, p={p:.4f} {sig_stars(p)}, r={r:.3f}  (median {d} 'other')")

print()
print("VERDICT (guide claim: consistent category targeting aids Apple News discoverability):")
top_topics = topic_stats_an.head(3)["topic"].tolist()
print(f"  Top performing topics by median views: {top_topics}")
print(f"  These appear to be naturally high-performing categories on Apple News.")

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 7: SmartNews — Topic Performance (2025)
# ══════════════════════════════════════════════════════════════════════════════
section_header("ANALYSIS 7: SmartNews 2025 — Topic Performance")

topic_stats_sn = (
    sn25.groupby("topic")["views_norm"]
    .agg(n="count", median="median", mean="mean")
    .sort_values("median", ascending=False)
    .reset_index()
)
print()
print(f"{'Topic':<20} {'n':>6} {'Median norm views':>18} {'Mean norm views':>16}")
print("-" * 62)
for _, row in topic_stats_sn.iterrows():
    print(f"{row['topic']:<20} {row['n']:>6} {row['median']:>18.4f} {row['mean']:>16.4f}")

subsection("Service journalism vs. hard news: SmartNews")
service_topics = ["lifestyle", "nature_wildlife"]
hardnews_topics = ["crime", "politics", "sports"]

service_views = sn25[sn25["topic"].isin(service_topics)]["views_norm"].dropna()
hardnews_views = sn25[sn25["topic"].isin(hardnews_topics)]["views_norm"].dropna()

u, p, r = mw_test(service_views, hardnews_views)
direction = "higher" if service_views.median() > hardnews_views.median() else "lower"
print(f"  Service journalism ({service_topics}) median: {service_views.median():.4f}")
print(f"  Hard news ({hardnews_topics}) median:         {hardnews_views.median():.4f}")
print(f"  MW test: U={u:.0f}, p={p:.4f} {sig_stars(p)}, r={r:.3f} (service is {direction} than hard news)")

print()
print("VERDICT (guide claim: service journalism verticals perform well on SmartNews):")
if p < 0.05 and service_views.median() > hardnews_views.median():
    print("  SUPPORTED — service journalism topics significantly outperform hard news on SmartNews")
elif p < 0.05 and service_views.median() < hardnews_views.median():
    print("  CONTRADICTED — hard news outperforms service journalism on SmartNews")
else:
    print(f"  NOT SIGNIFICANT — no reliable topic-type difference (p={p:.4f})")

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 8: Cross-platform formula comparison
# ══════════════════════════════════════════════════════════════════════════════
section_header("ANALYSIS 8: Cross-Platform Formula Comparison (Apple News vs. SmartNews)")

print("\nComparing formula direction vs. untagged baseline on each platform")
print("Direction: + = above baseline, - = below baseline, ~ = not significant")

# Merge formula results
an_dir = {}
for _, row in an_formula_df.iterrows():
    if row["p"] is not None and row["p"] < 0.05:
        an_dir[row["formula"]] = "+" if row["median_norm"] > baseline_an.median() else "-"
    else:
        an_dir[row["formula"]] = "~"

sn_dir = {}
baseline_sn_all = sn25[sn25["formula"] == "untagged"]["views_norm"].dropna()
sn_formula_rows_all = []
for formula, grp in sn25.groupby("formula"):
    v = grp["views_norm"].dropna()
    u, p, r = mw_test(v, baseline_sn_all)
    sn_formula_rows_all.append({"formula": formula, "n": len(v), "median_norm": v.median(), "p": p, "r": r})
    if p is not None and p < 0.05:
        sn_dir[formula] = "+" if v.median() > baseline_sn_all.median() else "-"
    else:
        sn_dir[formula] = "~"

all_formulas = sorted(set(list(an_dir.keys()) + list(sn_dir.keys())))

print()
print(f"{'Formula':<26} {'Apple News':>12} {'SmartNews':>12} {'Pattern':>14}")
print("-" * 66)
for formula in all_formulas:
    a = an_dir.get(formula, "—")
    s = sn_dir.get(formula, "—")
    if a == "+" and s == "+":    pattern = "WORKS BOTH"
    elif a == "-" and s == "-":  pattern = "FAILS BOTH"
    elif a == "+" and s == "-":  pattern = "AN only"
    elif a == "-" and s == "+":  pattern = "SN only"
    elif a == "+" and s == "~":  pattern = "AN only (SN ns)"
    elif a == "~" and s == "+":  pattern = "SN only (AN ns)"
    elif a == "-" and s == "~":  pattern = "AN hurts (SN ns)"
    elif a == "~" and s == "-":  pattern = "SN hurts (AN ns)"
    else:                         pattern = "neither"
    print(f"{formula:<26} {a:>12} {s:>12} {pattern:>14}")

print()
print("THE TRAP — formulas where platforms diverge:")
trap_formulas = [f for f in all_formulas if an_dir.get(f,"~") == "+" and sn_dir.get(f,"~") == "-"]
trap_formulas += [f for f in all_formulas if an_dir.get(f,"~") == "-" and sn_dir.get(f,"~") == "+"]
if trap_formulas:
    for f in trap_formulas:
        print(f"  {f}: Apple={an_dir.get(f,'—')} SmartNews={sn_dir.get(f,'—')}")
else:
    print("  No formula shows statistically divergent direction across both platforms.")

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 9: Apple News Notifications — Formula vs. CTR
# ══════════════════════════════════════════════════════════════════════════════
section_header("ANALYSIS 9: Apple News Notifications — Formula vs. CTR")

print("\nColumn names — 2025 notifications:")
print(f"  {ann25.columns.tolist()}")
print("\nColumn names — 2026 notifications:")
print(f"  {ann26.columns.tolist()}")

# 2025: CTR column = "Click-Through Rate"; text = "Notification Text"
# 2026: CTR column = "CTR"; text = "Notification Text"
ann25 = ann25.copy()
ann25["ctr_val"] = pd.to_numeric(ann25["Click-Through Rate"], errors="coerce")
ann25["headline"] = ann25["Notification Text"].astype(str).str.strip()

ann26 = ann26.copy()
ann26["ctr_val"] = pd.to_numeric(ann26["CTR"], errors="coerce")
ann26["headline"] = ann26["Notification Text"].astype(str).str.strip()

# Normalize CTR within year
ann25["ctr_norm"] = zscore_normalize(ann25["ctr_val"].dropna().reindex(ann25.index))
ann26["ctr_norm"] = zscore_normalize(ann26["ctr_val"].dropna().reindex(ann26.index))
ann25["year"] = 2025
ann26["year"] = 2026

ann_all = pd.concat([ann25, ann26], ignore_index=True)
ann_all["formula"]  = ann_all["headline"].apply(classify_formula)
ann_all["char_len"] = ann_all["headline"].str.len()
ann_all = ann_all.dropna(subset=["ctr_val"])
ann_all["ctr_norm"] = pd.to_numeric(ann_all["ctr_norm"], errors="coerce")

print(f"\nCombined notifications (clean): {len(ann_all)} rows")
print(f"CTR range: {ann_all['ctr_val'].min():.4f} – {ann_all['ctr_val'].max():.4f}")
print(f"CTR median: {ann_all['ctr_val'].median():.4f}")

baseline_ann = ann_all[ann_all["formula"] == "untagged"]["ctr_norm"].dropna()

ann_formula_rows = []
for formula, grp in ann_all.groupby("formula"):
    v = grp["ctr_norm"].dropna()
    u, p, r = mw_test(v, baseline_ann)
    ann_formula_rows.append({
        "formula": formula,
        "n": len(v),
        "median_ctr_norm": v.median(),
        "mean_ctr_norm": v.mean(),
        "median_ctr_raw": grp["ctr_val"].median(),
        "U": u, "p": p, "r": r, "sig": sig_stars(p),
    })

ann_formula_df = pd.DataFrame(ann_formula_rows).sort_values("median_ctr_norm", ascending=False)
print()
print(f"{'Formula':<26} {'n':>5} {'Med CTR(norm)':>14} {'Med CTR(raw)':>13} {'p':>8} {'sig':>4} {'r':>7}")
print("-" * 80)
for _, row in ann_formula_df.iterrows():
    p_str = f"{row['p']:.4f}" if row['p'] is not None else "—"
    r_str = f"{row['r']:.3f}" if row['r'] is not None else "—"
    print(f"{row['formula']:<26} {row['n']:>5} {row['median_ctr_norm']:>14.4f} {row['median_ctr_raw']:>13.4f} {p_str:>8} {row['sig']:>4} {r_str:>7}")

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 10: Title length distribution — top vs. bottom quartile
# ══════════════════════════════════════════════════════════════════════════════
section_header("ANALYSIS 10: Actual Character Counts of Top vs. Bottom Performers")

print("\nApple News 2025+2026:")
q75_an = an_all["Total Views"].quantile(0.75)
q25_an = an_all["Total Views"].quantile(0.25)
top_an    = an_all[an_all["Total Views"] >= q75_an]
bottom_an = an_all[an_all["Total Views"] <= q25_an]

print(f"  Top quartile (n={len(top_an)}): median char count = {top_an['char_len'].median():.0f}")
print(f"  Bottom quartile (n={len(bottom_an)}): median char count = {bottom_an['char_len'].median():.0f}")
print(f"  Overall median char count: {an_all['char_len'].median():.0f}")
print(f"  Top Q distribution (percentiles): "
      f"P10={top_an['char_len'].quantile(0.10):.0f}, "
      f"P25={top_an['char_len'].quantile(0.25):.0f}, "
      f"P50={top_an['char_len'].quantile(0.50):.0f}, "
      f"P75={top_an['char_len'].quantile(0.75):.0f}, "
      f"P90={top_an['char_len'].quantile(0.90):.0f}")

u_len, p_len, r_len = mw_test(top_an["char_len"].dropna(), bottom_an["char_len"].dropna())
print(f"  MW test (top vs. bottom quartile char len): U={u_len:.0f}, p={p_len:.4f} {sig_stars(p_len)}, r={r_len:.3f}")

print()
print("SmartNews 2025:")
q75_sn = sn25["article_view"].quantile(0.75)
q25_sn = sn25["article_view"].quantile(0.25)
top_sn    = sn25[sn25["article_view"] >= q75_sn]
bottom_sn = sn25[sn25["article_view"] <= q25_sn]

print(f"  Top quartile (n={len(top_sn)}): median char count = {top_sn['char_len'].median():.0f}")
print(f"  Bottom quartile (n={len(bottom_sn)}): median char count = {bottom_sn['char_len'].median():.0f}")
print(f"  Overall median char count: {sn25['char_len'].median():.0f}")
print(f"  Top Q distribution (percentiles): "
      f"P10={top_sn['char_len'].quantile(0.10):.0f}, "
      f"P25={top_sn['char_len'].quantile(0.25):.0f}, "
      f"P50={top_sn['char_len'].quantile(0.50):.0f}, "
      f"P75={top_sn['char_len'].quantile(0.75):.0f}, "
      f"P90={top_sn['char_len'].quantile(0.90):.0f}")

u_sn, p_sn, r_sn = mw_test(top_sn["char_len"].dropna(), bottom_sn["char_len"].dropna())
print(f"  MW test (top vs. bottom quartile char len): U={u_sn:.0f}, p={p_sn:.4f} {sig_stars(p_sn)}, r={r_sn:.3f}")

print()
print("VERDICT (guide claim: 50–70 chars for SmartNews, 80–110 for Apple News):")
an_top_med = top_an["char_len"].median()
sn_top_med = top_sn["char_len"].median()
an_claim_ok = 80 <= an_top_med <= 110
sn_claim_ok = 50 <= sn_top_med <= 100
print(f"  Apple News top-quartile median: {an_top_med:.0f} chars — {'within 80–110 range' if an_claim_ok else 'OUTSIDE 80–110 range'}")
print(f"  SmartNews top-quartile median:  {sn_top_med:.0f} chars — {'within <100 range' if sn_claim_ok else 'OUTSIDE <100 range'}")

# ══════════════════════════════════════════════════════════════════════════════
# BONUS: Char count distribution detail for Apple News
# ══════════════════════════════════════════════════════════════════════════════
section_header("BONUS: Apple News — Char count performance detail by fine bins")

fine_bins  = list(range(30, 170, 10)) + [9999]
fine_labels = [f"{fine_bins[i]}–{fine_bins[i+1]-1}" for i in range(len(fine_bins)-2)] + ["160+"]
an_all["char_fine_bin"] = pd.cut(an_all["char_len"], bins=fine_bins, labels=fine_labels)

fine_stats = (
    an_all.groupby("char_fine_bin", observed=True)["views_norm"]
    .agg(n="count", median="median", mean="mean")
    .reset_index()
)
print()
print(f"{'Char range':<14} {'n':>5} {'Median norm views':>18}")
print("-" * 40)
for _, row in fine_stats.iterrows():
    bar = "█" * max(0, int((row["median"] + 0.5) * 20))
    print(f"{str(row['char_fine_bin']):<14} {row['n']:>5} {row['median']:>18.4f}  {bar}")

# ══════════════════════════════════════════════════════════════════════════════
# BONUS 2: SmartNews — 2026 char count check
# ══════════════════════════════════════════════════════════════════════════════
section_header("BONUS: SmartNews 2026 — Char count vs. views (validation)")

sn26["formula"]  = sn26["headline"].apply(classify_formula)
sn26["char_bin"] = pd.cut(sn26["char_len"], bins=bins_sn, labels=labels_sn)

bin_stats_sn26 = (
    sn26.groupby("char_bin", observed=True)["views_norm"]
    .agg(n="count", median="median", mean="mean")
    .reset_index()
)
print(f"\nSmartNews 2026 (n={len(sn26)}) — char bins:")
print()
print(f"{'Bin':<12} {'n':>6} {'Median norm views':>18} {'Mean norm views':>16}")
print("-" * 54)
for _, row in bin_stats_sn26.iterrows():
    print(f"{row['char_bin']:<12} {row['n']:>6} {row['median']:>18.4f} {row['mean']:>16.4f}")

under100_26 = sn26[sn26["char_len"] < 100]["views_norm"].dropna()
over100_26  = sn26[sn26["char_len"] >= 100]["views_norm"].dropna()
u26, p26, r26 = mw_test(under100_26, over100_26)
direction26 = "higher" if under100_26.median() > over100_26.median() else "lower"
print(f"\n  2026 <100 vs 100+: U={u26:.0f}, p={p26:.4f} {sig_stars(p26)}, r={r26:.3f} (<100 is {direction26})")

# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY TABLE
# ══════════════════════════════════════════════════════════════════════════════
section_header("SUMMARY: Guide Claims — Evidence Assessment")

print("""
Guide Claim                                             Evidence Assessment
────────────────────────────────────────────────────────────────────────────
1. SmartNews: 'How to'/'What to Know' = good for       See Analysis 3 verdicts above
   service journalism

2. SmartNews: Keep under 100 characters                 See Analysis 2 verdict above

3. Apple News: 80–110 chars recommended                 See Analysis 1 verdict above

4. Apple News: Human curation favors quality/           See Analysis 5 (featured lift table)
   originality (formula distribution of featured picks)

5. SmartNews: Clear/direct/keyword-forward > clever     Indirectly tested via formula perf.
   (number_lead, untagged proxy for direct)

6. Apple News: Consistent category targeting helps      See Analysis 6 (topic rankings)
   discoverability

7. Write 2 variants: 50–70 SEO/SN, 80–110 AN           See Analysis 10 (actual top-Q medians)
────────────────────────────────────────────────────────────────────────────
""")

print("Analysis complete.")
