#!/usr/bin/env python3
"""
Experiment report generator for T1 Headline Analysis.

Reads an experiment spec from experiments/SLUG.md and writes a comparison
report to docs/experiments/SLUG/index.html.

Usage:
  python3 generate_experiment.py experiments/SLUG.md       # one experiment
  python3 generate_experiment.py experiments/              # all active/pending specs

Experiment types supported:
  temporal_cohort   — compare metric before vs. after a date
  formula_comparison — compare metric for formula A vs. formula B

See experiments/README.md for the spec format.
"""

import re
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy import stats


# ── Config ────────────────────────────────────────────────────────────────────

DATA_2025 = "Top syndication content 2025.xlsx"
DATA_2026 = "Top Stories 2026 Syndication.xlsx"

NAVY  = "#0f172a"
BLUE  = "#2563eb"
GREEN = "#16a34a"
RED   = "#dc2626"
GRAY  = "#64748b"
BORDER = "#e2e8f0"

METRICS = {
    "views": {
        "platform": "apple_news",
        "col": "Total Views",
        "test": "mann_whitney",
        "label": "Median views",
        "fmt": lambda x: f"{x:,.0f}",
    },
    "featured_rate": {
        "platform": "apple_news",
        "col": "is_featured",
        "test": "chi_square",
        "label": "Featured rate",
        "fmt": lambda x: f"{x:.1%}",
    },
    "active_time": {
        "platform": "apple_news",
        "col": "Avg. Active Time (in seconds)",
        "test": "mann_whitney",
        "label": "Median active time (s)",
        "fmt": lambda x: f"{x:.0f}s",
    },
    "ctr": {
        "platform": "notifications",
        "col": "CTR",
        "test": "mann_whitney",
        "label": "Median CTR",
        "fmt": lambda x: f"{x:.2%}",
    },
    "smartnews_views": {
        "platform": "smartnews",
        "col": "article_view",
        "test": "mann_whitney",
        "label": "Median article views",
        "fmt": lambda x: f"{x:,.0f}",
    },
}

FORMULA_PATTERNS = {
    "number_lead":             lambda t: bool(re.match(r"^\d", str(t))),
    "heres_formula":           lambda t: bool(re.match(r"^here[\u2019\']s\b|^here are\b|^here is\b|^here come\b", str(t).lower())),
    "possessive_named_entity": lambda t: bool(re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", str(t)) and re.search(r"[\u2019\']s\b", str(t))),
    "what_to_know":            lambda t: bool(re.search(r"what to know\s*$", str(t).lower())),
    "question":                lambda t: str(t).rstrip().endswith("?"),
    "quoted_lede":             lambda t: str(t).startswith("\u2018"),
    "untagged":                lambda t: True,  # fallback
}

TOPIC_PATTERNS = {
    "crime":           r"\b(shot|kill|murder|dead|death|shooting|arrest|charge|crime|victim|police|cop|suspect|robbery|assault)\b",
    "sports":          r"\b(game|team|nfl|nba|mlb|nhl|coach|season|championship|super bowl|playoff|quarterback)\b",
    "weather":         r"\b(storm|hurricane|tornado|flood|rain|snow|weather|forecast|wildfire|earthquake|heat)\b",
    "business":        r"\b(business|economy|job|hire|layoff|company|market|real estate|housing|price|cost|wage|salary|tax)\b",
    "local_civic":     r"\b(school|student|teacher|education|college|university|election|vote|city|county|state|local|community|neighborhood)\b",
    "lifestyle":       r"\b(restaurant|food|eat|chef|menu|recipe|bar|coffee|dining|hotel|travel|beach|park|festival|concert)\b",
    "nature_wildlife": r"\b(animal|creature|species|wildlife|shark|bear|alligator|snake|bird|dog|cat|pet)\b",
}


# ── Spec parsing ──────────────────────────────────────────────────────────────

def parse_spec(path):
    """Parse YAML frontmatter + markdown body from an experiment spec file."""
    text = Path(path).read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n?(.*)", text, re.DOTALL)
    if not match:
        raise ValueError(f"No YAML frontmatter found in {path}")

    fm_text, body = match.group(1), match.group(2).strip()
    spec = {}
    for line in fm_text.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            val = val.strip().strip('"').strip("'")
            spec[key.strip()] = None if val in ("null", "~", "") else val

    spec["_body"] = body
    spec["_slug"] = Path(path).stem
    return spec


# ── Data loading ──────────────────────────────────────────────────────────────

_cache = {}

def load_platform(platform):
    if platform in _cache:
        return _cache[platform]
    if platform == "apple_news":
        df = pd.read_excel(DATA_2025, sheet_name="Apple News")
        df["is_featured"] = (df["Featured by Apple"].fillna("No") == "Yes").astype(int)
        df["formula"] = df["Article"].apply(_classify_formula)
        df["topic"]   = df["Article"].apply(_classify_topic)
        df["date"]    = pd.to_datetime(df["Date Published"])
    elif platform == "smartnews":
        df = pd.read_excel(DATA_2025, sheet_name="SmartNews")
        df["formula"] = df["title"].apply(_classify_formula)
        df["topic"]   = df["title"].apply(_classify_topic)
        df["date"]    = pd.to_datetime(df["date"], errors="coerce")
    elif platform == "notifications":
        df = pd.read_excel(DATA_2026, sheet_name="Apple News Notifications")
        df = df.dropna(subset=["CTR"])
        df["formula"] = df["Notification Text"].apply(_classify_formula)
        df["date"]    = pd.to_datetime(df["Sent At"], errors="coerce")
    else:
        raise ValueError(f"Unknown platform: {platform}")
    _cache[platform] = df
    return df


def _classify_formula(text):
    t = str(text).strip()
    tl = t.lower()
    if re.match(r"^\d", t): return "number_lead"
    if re.match(r"^here[\u2019\']s\b|^here are\b|^here is\b|^here come\b", tl): return "heres_formula"
    if re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", t) and re.search(r"[\u2019\']s\b", t): return "possessive_named_entity"
    if re.search(r"what to know\s*$", tl): return "what_to_know"
    if t.rstrip().endswith("?"): return "question"
    if t.startswith("\u2018"): return "quoted_lede"
    return "untagged"


def _classify_topic(text):
    t = str(text).lower()
    for topic, pattern in TOPIC_PATTERNS.items():
        if re.search(pattern, t):
            return topic
    return "other"


# ── Cohort splitting ──────────────────────────────────────────────────────────

def split_cohorts(df, spec, metric_info):
    exp_type = spec.get("experiment_type", "temporal_cohort")

    # Common filters
    if spec.get("filter_topic"):
        df = df[df["topic"] == spec["filter_topic"]]
    if spec.get("filter_featured") == "no":
        df = df[df.get("is_featured", pd.Series(0, index=df.index)) == 0]
    if spec.get("filter_featured") == "yes":
        df = df[df.get("is_featured", pd.Series(0, index=df.index)) == 1]

    col = metric_info["col"]

    if exp_type == "temporal_cohort":
        before_start = pd.to_datetime(spec["before_start"])
        before_end   = pd.to_datetime(spec["before_end"])
        after_start  = pd.to_datetime(spec["after_start"])
        after_end    = pd.to_datetime(spec["after_end"])

        if spec.get("filter_formula"):
            df = df[df["formula"] == spec["filter_formula"]]

        before = df[(df["date"] >= before_start) & (df["date"] <= before_end)][col].dropna()
        after  = df[(df["date"] >= after_start)  & (df["date"] <= after_end)][col].dropna()
        label_a, label_b = "Before", "After"

    elif exp_type == "formula_comparison":
        formula_a = spec.get("formula_a", "what_to_know")
        formula_b = spec.get("formula_b", "untagged")

        if spec.get("date_start"):
            start = pd.to_datetime(spec["date_start"])
            end   = pd.to_datetime(spec["date_end"]) if spec.get("date_end") else df["date"].max()
            df = df[(df["date"] >= start) & (df["date"] <= end)]

        before = df[df["formula"] == formula_a][col].dropna()
        after  = df[df["formula"] == formula_b][col].dropna()
        label_a = formula_a.replace("_", " ").title()
        label_b = formula_b.replace("_", " ").title()

    else:
        raise ValueError(f"Unknown experiment_type: {exp_type}")

    return before, after, label_a, label_b


# ── Statistical tests ─────────────────────────────────────────────────────────

def run_test(group_a, group_b, test_type):
    n_a, n_b = len(group_a), len(group_b)

    if n_a < 5 or n_b < 5:
        return dict(n_a=n_a, n_b=n_b, stat_a=None, stat_b=None,
                    lift=None, p=None, conclusion="insufficient_data")

    if test_type == "mann_whitney":
        stat_a = float(group_a.median())
        stat_b = float(group_b.median())
        _, p = stats.mannwhitneyu(group_a, group_b, alternative="two-sided")
        lift = stat_b / stat_a if stat_a > 0 else None
    elif test_type == "chi_square":
        # group_a / group_b are binary (0/1) series
        n_a_pos = int(group_a.sum()); n_a_neg = n_a - n_a_pos
        n_b_pos = int(group_b.sum()); n_b_neg = n_b - n_b_pos
        _, p, _, _ = stats.chi2_contingency([[n_a_pos, n_a_neg], [n_b_pos, n_b_neg]])
        stat_a = group_a.mean()
        stat_b = group_b.mean()
        lift = stat_b / stat_a if stat_a > 0 else None
    else:
        raise ValueError(f"Unknown test: {test_type}")

    conclusion = "significant" if p < 0.05 else "not_significant"
    return dict(n_a=n_a, n_b=n_b, stat_a=stat_a, stat_b=stat_b,
                lift=lift, p=float(p), conclusion=conclusion)


# ── Charts ────────────────────────────────────────────────────────────────────

def make_comparison_chart(group_a, group_b, label_a, label_b, metric_info, result):
    """Bar chart comparing median (or rate) for group A vs B, with n labels."""
    fmt = metric_info["fmt"]
    stat_a = result["stat_a"]
    stat_b = result["stat_b"]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[label_a, label_b],
        y=[stat_a, stat_b],
        marker_color=[BLUE, GREEN if (result["lift"] or 0) >= 1 else RED],
        text=[f"{fmt(stat_a)}<br>n={result['n_a']:,}", f"{fmt(stat_b)}<br>n={result['n_b']:,}"],
        textposition="outside",
        hovertemplate="%{x}: %{text}<extra></extra>",
        width=0.4,
    ))
    fig.update_layout(
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif",
                  size=13, color=NAVY),
        margin=dict(l=20, r=20, t=40, b=40),
        height=320,
        yaxis=dict(gridcolor=BORDER, zeroline=False,
                   title=metric_info["label"]),
        xaxis=dict(gridcolor="white"),
        showlegend=False,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def make_timeseries_chart(df, spec, metric_info):
    """Monthly time series with vertical line at intervention date, for temporal cohorts."""
    col = spec.get("filter_formula")  # used for filtering, not the chart col
    metric_col = metric_info["col"]
    test = metric_info["test"]

    df = df.copy()
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()

    if spec.get("filter_formula"):
        df = df[df["formula"] == spec["filter_formula"]]
    if spec.get("filter_topic"):
        df = df[df["topic"] == spec["filter_topic"]]

    if test == "chi_square":
        monthly = df.groupby("month")[metric_col].mean().reset_index()
    else:
        monthly = df.groupby("month")[metric_col].median().reset_index()

    monthly = monthly[monthly[metric_col].notna()]

    after_start = pd.to_datetime(spec["after_start"])
    before_end  = pd.to_datetime(spec["before_end"])
    midpoint    = before_end + (after_start - before_end) / 2

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly["month"].tolist(),
        y=monthly[metric_col].tolist(),
        mode="lines+markers",
        line=dict(color=BLUE, width=2),
        marker=dict(size=5),
        hovertemplate="%{x|%b %Y}: %{y:.2f}<extra></extra>",
    ))
    fig.add_vline(
        x=midpoint.timestamp() * 1000,
        line_dash="dash", line_color=RED, line_width=1.5,
        annotation_text="Change date", annotation_position="top right",
        annotation_font_color=RED,
    )
    fig.update_layout(
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif",
                  size=12, color=NAVY),
        margin=dict(l=20, r=20, t=40, b=40),
        height=300,
        yaxis=dict(gridcolor=BORDER, zeroline=False, title=metric_info["label"]),
        xaxis=dict(gridcolor=BORDER),
        showlegend=False,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


# ── Report HTML ───────────────────────────────────────────────────────────────

def render_report(spec, result, metric_info, chart_html, timeseries_html=None):
    fmt = metric_info["fmt"]
    slug = spec["_slug"]
    title = spec.get("title", slug)
    hypothesis = spec.get("hypothesis", "")
    context = spec.get("_body", "")
    status = spec.get("status", "pending")

    # Conclusion callout
    if result["conclusion"] == "insufficient_data":
        conclusion_text = "Insufficient data — fewer than 5 observations in one group. Check date ranges or filters."
        callout_color = "#b45309"
        callout_bg = "#fef3c7"
    elif result["conclusion"] == "significant":
        lift = result["lift"]
        direction = "increased" if lift >= 1 else "decreased"
        callout_text = f"{fmt(result['stat_b'])} vs. {fmt(result['stat_a'])} — {lift:.2f}× lift, p={result['p']:.3f}"
        conclusion_text = f"Result is statistically significant. The metric {direction} ({callout_text})."
        callout_color = GREEN if lift >= 1 else RED
        callout_bg = "#dcfce7" if lift >= 1 else "#fee2e2"
    else:
        conclusion_text = (
            f"Not statistically significant (p={result['p']:.3f}). "
            f"Observed lift: {result['lift']:.2f}× — but could be noise at current sample sizes "
            f"(n={result['n_a']:,} before, n={result['n_b']:,} after)."
        )
        callout_color = GRAY
        callout_bg = "#f1f5f9"

    ts_block = ""
    if timeseries_html:
        ts_block = f"""
    <h3 style="font-size:0.95rem;font-weight:600;margin:1.5rem 0 0.5rem;">Monthly trend</h3>
    <div class="chart-wrap">{timeseries_html}</div>"""

    p_str = f"{result['p']:.4f}" if result['p'] is not None else "—"
    lift_str = f"{result['lift']:.2f}×" if result['lift'] is not None else "—"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} · T1 Experiment</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  :root {{ --navy:{NAVY}; --blue:{BLUE}; --green:{GREEN}; --red:{RED}; --gray:{GRAY}; --border:{BORDER}; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
          color:var(--navy); background:#fff; font-size:16px; line-height:1.65; }}
  nav {{ background:var(--navy); padding:0 1.5rem; display:flex; align-items:center;
         gap:1.25rem; height:52px; }}
  nav a {{ color:rgba(255,255,255,0.55); text-decoration:none; font-size:0.8rem; }}
  nav a:hover {{ color:#fff; }}
  nav .brand {{ color:#fff; font-weight:600; font-size:0.82rem; opacity:0.9; }}
  .container {{ max-width:820px; margin:0 auto; padding:2.5rem 1.75rem 4rem; }}
  .eyebrow {{ text-transform:uppercase; letter-spacing:0.1em; font-size:0.67rem;
              color:var(--blue); font-weight:600; margin-bottom:0.5rem; }}
  h1 {{ font-family:Georgia,serif; font-size:1.65rem; line-height:1.3;
        margin-bottom:0.6rem; letter-spacing:-0.01em; }}
  .meta {{ font-size:0.82rem; color:var(--gray); margin-bottom:2rem; }}
  .callout {{ padding:1rem 1.25rem; border-radius:6px; margin:1.5rem 0;
              font-size:0.92rem; border-left:3px solid; }}
  h3 {{ font-size:1rem; font-weight:600; margin:1.75rem 0 0.5rem; }}
  p {{ color:#475569; margin-bottom:1rem; font-size:0.95rem; }}
  .chart-wrap {{ margin:1.25rem 0; border:1px solid var(--border);
                 border-radius:8px; overflow:hidden; padding:1rem; }}
  table {{ width:100%; border-collapse:collapse; font-size:0.88rem; margin:1.25rem 0; }}
  th {{ text-align:left; padding:6px 10px; border-bottom:2px solid var(--border);
        color:var(--gray); font-weight:600; font-size:0.72rem; text-transform:uppercase;
        letter-spacing:0.06em; }}
  td {{ padding:7px 10px; border-bottom:1px solid var(--border); vertical-align:top; }}
  .caveat {{ font-size:0.78rem; color:var(--gray); font-style:italic; margin-top:1.5rem; }}
  .status {{ display:inline-block; font-size:0.67rem; font-weight:600;
             text-transform:uppercase; letter-spacing:0.07em; padding:2px 8px;
             border-radius:2px; margin-left:0.5rem; }}
  .status-complete {{ background:#dcfce7; color:#15803d; }}
  .status-active   {{ background:#dbeafe; color:#1d4ed8; }}
  .status-pending  {{ background:#f1f5f9; color:#64748b; }}
</style>
</head>
<body>
<nav>
  <span class="brand">McClatchy CSA · T1 Headlines</span>
  <a href="../../index.html">← Current analysis</a>
  <a href="../index.html">All experiments</a>
</nav>
<div class="container">
  <p class="eyebrow">Experiment · {spec.get('platform','').replace('_',' ').title()} · {spec.get('metric','').replace('_',' ').title()}</p>
  <h1>{title}<span class="status status-{status}">{status}</span></h1>
  <p class="meta">
    Type: {spec.get('experiment_type','').replace('_',' ')} &nbsp;·&nbsp;
    Generated: {datetime.now().strftime('%Y-%m-%d')}
    {f"&nbsp;·&nbsp; Before: {spec.get('before_start')} – {spec.get('before_end')}" if spec.get("before_start") else ""}
    {f"&nbsp;·&nbsp; After: {spec.get('after_start')} – {spec.get('after_end')}" if spec.get("after_start") else ""}
  </p>

  <div class="callout" style="background:{callout_bg};border-color:{callout_color};color:{callout_color};">
    <strong>Result:</strong> {conclusion_text}
  </div>

  {"<p><strong>Hypothesis:</strong> " + hypothesis + "</p>" if hypothesis else ""}
  {("<div>" + context + "</div>") if context else ""}

  <h3>Comparison</h3>
  <div class="chart-wrap">{chart_html}</div>
  {ts_block}

  <h3>Statistics</h3>
  <table>
    <thead><tr><th>Group</th><th>n</th><th>{metric_info['label']}</th><th>Lift</th><th>p-value</th><th>Significant?</th></tr></thead>
    <tbody>
      <tr><td>A (before / formula A)</td><td>{result['n_a']:,}</td><td>{fmt(result['stat_a']) if result['stat_a'] is not None else '—'}</td><td>—</td><td rowspan="2" style="vertical-align:middle">{p_str}</td><td rowspan="2" style="vertical-align:middle">{'Yes ✓' if result['conclusion'] == 'significant' else 'No' if result['conclusion'] == 'not_significant' else '—'}</td></tr>
      <tr><td>B (after / formula B)</td><td>{result['n_b']:,}</td><td>{fmt(result['stat_b']) if result['stat_b'] is not None else '—'}</td><td>{lift_str}</td></tr>
    </tbody>
  </table>

  <p class="caveat">
    Test: {'Mann-Whitney U (non-parametric)' if metric_info['test'] == 'mann_whitney' else 'Chi-square'}.
    Platform: {spec.get('platform','')}.
    {f"Formula filter: {spec.get('filter_formula')}." if spec.get('filter_formula') else ""}
    {f"Topic filter: {spec.get('filter_topic')}." if spec.get('filter_topic') else ""}
    α = 0.05.
  </p>
</div>
</body>
</html>"""


# ── Experiment index ──────────────────────────────────────────────────────────

def update_experiment_index(specs):
    """Regenerate docs/experiments/index.html listing all experiments."""
    rows = ""
    for spec in sorted(specs, key=lambda s: s.get("status", "z")):
        slug = spec["_slug"]
        title = spec.get("title", slug)
        status = spec.get("status", "pending")
        platform = spec.get("platform", "").replace("_", " ").title()
        metric = spec.get("metric", "").replace("_", " ")
        rows += (
            f'<li>'
            f'<a href="{slug}/index.html">{title}</a>'
            f'<span class="meta">{platform} · {metric} · '
            f'<span class="status status-{status}">{status}</span></span>'
            f'</li>\n'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>T1 Headline Analysis · Experiments</title>
<style>
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
          max-width:760px; margin:3rem auto; padding:0 1.5rem; color:#0f172a; line-height:1.6; }}
  h1 {{ font-family:Georgia,serif; font-size:1.5rem; margin-bottom:0.4rem; }}
  .back {{ color:#2563eb; text-decoration:none; font-size:0.85rem; display:block; margin-bottom:2rem; }}
  p.sub {{ color:#64748b; font-size:0.88rem; margin-bottom:2rem; }}
  ul {{ list-style:none; padding:0; margin:0; }}
  li {{ padding:1rem 0; border-bottom:1px solid #e2e8f0; }}
  li:last-child {{ border-bottom:none; }}
  li a {{ font-family:Georgia,serif; font-size:1.05rem; color:#0f172a;
          text-decoration:none; display:block; margin-bottom:0.2rem; }}
  li a:hover {{ color:#2563eb; }}
  .meta {{ display:block; font-size:0.78rem; color:#94a3b8; }}
  .status {{ display:inline-block; font-size:0.67rem; font-weight:600; text-transform:uppercase;
             letter-spacing:0.06em; padding:1px 6px; border-radius:2px; }}
  .status-complete {{ background:#dcfce7; color:#15803d; }}
  .status-active   {{ background:#dbeafe; color:#1d4ed8; }}
  .status-pending  {{ background:#f1f5f9; color:#64748b; }}
</style>
</head>
<body>
<a class="back" href="../index.html">← Current analysis</a>
<h1>Experiments</h1>
<p class="sub">Before/after comparisons and formula tests. Add a spec to <code>experiments/</code>
  and run <code>python3 generate_experiment.py experiments/SLUG.md</code>.</p>
<ul>
{rows}</ul>
</body>
</html>"""

    out = Path("docs/experiments/index.html")
    out.write_text(html, encoding="utf-8")
    print(f"✓ Updated experiments index → {out}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run_experiment(spec_path):
    spec = parse_spec(spec_path)
    slug = spec["_slug"]
    status = spec.get("status", "pending")

    if status == "pending":
        print(f"  Skipping {slug} (status: pending — no data yet)")
        return spec
    if status not in ("active", "complete"):
        print(f"  Skipping {slug} (status: {status})")
        return None

    metric_key = spec.get("metric")
    if metric_key not in METRICS:
        print(f"  ✗ Unknown metric '{metric_key}' in {slug}")
        return spec

    metric_info = METRICS[metric_key]
    platform = metric_info["platform"]

    print(f"  Running {slug}…  platform={platform} metric={metric_key}")
    df = load_platform(platform)

    try:
        group_a, group_b, label_a, label_b = split_cohorts(df, spec, metric_info)
    except Exception as e:
        print(f"  ✗ Failed to split cohorts: {e}")
        return spec

    result = run_test(group_a, group_b, metric_info["test"])
    chart_html = make_comparison_chart(group_a, group_b, label_a, label_b, metric_info, result)

    # Time series for temporal cohorts only
    ts_html = None
    if spec.get("experiment_type") == "temporal_cohort":
        try:
            ts_html = make_timeseries_chart(df, spec, metric_info)
        except Exception:
            ts_html = None

    report = render_report(spec, result, metric_info, chart_html, ts_html)

    out_dir = Path("docs/experiments") / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(report, encoding="utf-8")
    print(f"  ✓ Report → {out_dir}/index.html  ({result['conclusion']}, lift={result.get('lift','—')})")
    return spec


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_experiment.py experiments/SLUG.md")
        print("       python3 generate_experiment.py experiments/")
        sys.exit(1)

    target = Path(sys.argv[1])
    if target.is_dir():
        spec_files = sorted(target.glob("*.md"))
        spec_files = [f for f in spec_files if f.name != "README.md"]
    else:
        spec_files = [target]

    all_specs = []
    for sf in spec_files:
        print(f"\n{sf.name}")
        spec = run_experiment(sf)
        if spec:
            all_specs.append(spec)

    if all_specs:
        update_experiment_index(all_specs)


if __name__ == "__main__":
    main()
