#!/usr/bin/env python3
"""generate_style_guide.py -- Editorial Headline Style Guide

Produces docs/style-guide/index.html: a clean, print-ready 1-pager with
Apple News and SmartNews headline rules drawn from confirmed findings.
No stats, no charts -- just the rules, ready to share with editorial leads.

Regenerated on every ingest run alongside the main site.
"""

import html
from pathlib import Path

OUTPUT_PATH = Path("docs/style-guide/index.html")

# ── Rules ─────────────────────────────────────────────────────────────────────
# Each rule: (confidence, rule_text, note)
# confidence: "Confirmed" | "Directional" | "Setup"

APPLE_NEWS_RULES = [
    ("Confirmed",
     "Tag every article with a non-Main section before publishing.",
     "Untagged articles land in the bottom 20% at 2.4x the baseline rate and almost"
     " never get featured."),
    ("Confirmed",
     "Use \u201cWhat to know\u201d only when intentionally targeting Featured placement.",
     "\u201cWhat to know\u201d is associated with higher featuring odds but trends lower"
     " for organic (non-featured) views. Don\u2019t use it as a general-purpose formula."),
    ("Confirmed",
     "Use \u201cHere\u2019s\u201d for Crime and Business headlines targeting Featured.",
     "Crime + \u201cHere\u2019s\u201d = 16% featuring rate (n=89). Business + \u201cHere\u2019s\u201d"
     " = 14% (n=72). The strongest editorially writable non-weather formulas."),
    ("Confirmed",
     "Don\u2019t rely on Apple News for Sports distribution.",
     "Sports content earns 0% featuring regardless of formula. SmartNews is the better channel for sports."),
    ("Confirmed",
     "Don\u2019t rely on Apple News for national wire content.",
     "Nation & World articles underperform local sections by 20+ percentile points."
     " Focus Apple News effort on local-angle stories."),
    ("Confirmed",
     "Target 90\u2013120 characters.",
     "Performance rises through 110\u2013119 chars. Below 70 and above 130 both underperform."),
    ("Confirmed",
     "Use question format only for intentional Featured targeting \u2014 never for organic reach.",
     "Apple editors over-select questions for featuring, but the algorithm penalizes them organically."),
    ("Directional",
     "Lean into number leads; reduce question-format headlines.",
     "Number leads are the only formula trending upward from Q1 2025 to Q1 2026. Questions are trending down."),
    ("Directional",
     "For Nature/Wildlife/Science: use discovery framing.",
     "\u201cScientists found\u2026\u201d, \u201cNever-before-seen\u2026\u201d, \u201cRare\u2026\u201d"
     " \u2014 this framing drives the highest-ceiling performance for General/Discovery content (53K+ views observed)."),
    ("Setup",
     "Mind-Body, Everyday Living, and Experience content: optimize for organic views, not featuring.",
     "These verticals currently earn 0% featuring rate on Apple News (Jan\u2013Feb 2026, n=355 articles)."
     " Featuring is not a lever for this content type."),
]

SMARTNEWS_RULES = [
    ("Confirmed",
     "Never use question format for SmartNews.",
     "Questions drop to 0.42 percentile rank \u2014 0.08 below baseline (p=3.4e-6, n=918)."
     " This is the strongest single avoidance rule in the dataset."),
    ("Confirmed",
     "Never use \u201cWhat to know\u201d for SmartNews.",
     "\u201cWhat to know\u201d is the worst-performing formula: 0.37 pct_rank (p=3.0e-6, n=213)."),
    ("Confirmed",
     "Target 70\u201390 characters.",
     "80\u201399 char optimal bin confirmed. The 100-char ceiling published in Apple\u2019s guidance"
     " has no statistical basis in SmartNews data (p=0.915)."),
    ("Confirmed",
     "Direct declarative headlines are the safe default.",
     "Subject-verb-object format is never penalized. Use as the fallback when no formula signal applies."),
    ("Directional",
     "Use \u201cHere\u2019s\u201d when writing one headline for both Apple News and SmartNews.",
     "\u201cHere\u2019s\u201d is directionally above baseline on SmartNews (p=0.038) and works for"
     " Apple News featuring. The only formula that doesn\u2019t hurt on either platform."
     " Note: doesn\u2019t survive strict Bonferroni correction at k=5."),
    ("Directional",
     "Use number leads when topic allows.",
     "Number leads are the only SmartNews formula with a positive performance trend."
     " Stronger for list-format stories."),
    ("Directional",
     "For Nature/Wildlife/Science: avoid question and \u201cWhat to know\u201d format.",
     "Apply the same discovery framing as Apple News."
     " High ceiling on SmartNews when not penalized by question format."),
]

NOTIFICATION_RULES = [
    ("Confirmed",
     "Use attribution language for news brand notifications.",
     "\u201cSays\u201d, \u201ctold\u201d, \u201creports\u201d, \u201creveals\u201d"
     " \u2014 1.18x CTR lift (p=0.020, n=59)."
     " The only consistent signal still lifting CTR against a declining baseline."),
    ("Confirmed",
     "Use crime/death outcome words when factually accurate.",
     "\u201cDead\u201d, \u201ckilled\u201d, \u201carrested\u201d, \u201ccharged\u201d, \u201cconvicted\u201d"
     " \u2014 1.26x CTR lift (p=0.0015, n=55). Strongest single notification signal."
     " Stack with attribution for maximum effect."),
    ("Confirmed",
     "Avoid question format in notifications.",
     "Consistently hurts CTR across both news brand and celebrity content types."),
    ("Confirmed",
     "For celebrity/entertainment notifications: use possessive named entity.",
     "\u201c[Celebrity]\u2019s [situation]\u201d outperforms other formats."
     " Numbers in the headline hurt CTR in entertainment context."),
    ("Directional",
     "Serial/escalating stories: frame each update as an installment.",
     "Possessive named entity + new development + escalating stakes"
     " is the highest-CTR notification structure for breaking stories."),
]

# ── HTML generation ────────────────────────────────────────────────────────────

def _rules_html(rules: list) -> str:
    conf_colors = {
        "Confirmed":   "#16a34a",
        "Directional": "#f59e0b",
        "Setup":       "#3b82f6",
    }
    conf_symbols = {
        "Confirmed":   "\u2713 Confirmed",
        "Directional": "\u2192 Directional",
        "Setup":       "\u2691 Setup",
    }
    rows = ""
    for conf, rule, note in rules:
        color  = conf_colors.get(conf, "#64748b")
        label  = conf_symbols.get(conf, conf)
        rows += f"""
<div class="rule">
  <div class="rule-top">
    <span class="conf-badge" style="background:{color}">{html.escape(label)}</span>
    <strong class="rule-text">{html.escape(rule)}</strong>
  </div>
  <p class="rule-note">{html.escape(note)}</p>
</div>"""
    return rows


def generate() -> str:
    from datetime import date
    today = date.today().strftime("%B %d, %Y")

    an_html    = _rules_html(APPLE_NEWS_RULES)
    sn_html    = _rules_html(SMARTNEWS_RULES)
    notif_html = _rules_html(NOTIFICATION_RULES)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>McClatchy Headline Style Guide</title>
<style>
  :root {{
    --bg: #ffffff; --text: #0f172a; --text-muted: #64748b;
    --border: #e2e8f0; --surface: #f8fafc; --accent: #2563eb;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #0f172a; --text: #e2e8f0; --text-muted: #94a3b8;
             --border: #1e293b; --surface: #1e293b; }}
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: var(--bg); color: var(--text); line-height: 1.5; }}
  .page {{ max-width: 860px; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }}
  .header {{ border-bottom: 2px solid var(--accent); padding-bottom: 1rem; margin-bottom: 2rem; }}
  .header h1 {{ font-size: 1.6rem; font-weight: 800; }}
  .header .meta {{ font-size: .8rem; color: var(--text-muted); margin-top: .25rem; }}
  .platform-section {{ margin-bottom: 2.5rem; }}
  .platform-section h2 {{ font-size: 1rem; font-weight: 700; letter-spacing: .06em;
                           text-transform: uppercase; color: var(--accent);
                           border-bottom: 1px solid var(--border); padding-bottom: .4rem;
                           margin-bottom: 1rem; }}
  .rule {{ padding: .9rem 1rem; border-left: 3px solid var(--border);
           margin-bottom: .75rem; background: var(--surface); border-radius: 0 4px 4px 0; }}
  .rule-top {{ display: flex; align-items: flex-start; gap: .6rem;
               margin-bottom: .3rem; flex-wrap: wrap; }}
  .conf-badge {{ font-size: .7rem; font-weight: 700; color: #fff; padding: 1px 7px;
                 border-radius: 3px; white-space: nowrap; flex-shrink: 0; margin-top: 2px; }}
  .rule-text {{ font-size: .88rem; font-weight: 600; color: var(--text); }}
  .rule-note {{ font-size: .8rem; color: var(--text-muted); margin-top: .15rem;
                padding-left: calc(.7rem + .6rem + 2px); line-height: 1.45; }}
  .legend {{ display: flex; gap: 1rem; font-size: .75rem; color: var(--text-muted);
             margin-bottom: 1.5rem; flex-wrap: wrap; }}
  .legend span {{ display: flex; align-items: center; gap: .3rem; }}
  .legend .dot {{ width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }}
  .footer {{ font-size: .75rem; color: var(--text-muted); border-top: 1px solid var(--border);
             padding-top: 1rem; margin-top: 2rem; }}
  @media print {{
    .page {{ max-width: 100%; padding: 1rem; }}
    .rule {{ break-inside: avoid; }}
  }}
</style>
</head>
<body>
<div class="page">
  <div class="header">
    <h1>McClatchy Headline Style Guide</h1>
    <div class="meta">Generated {today} &middot; McClatchy CSA &middot; Based on T1 headline performance data 2025&ndash;2026</div>
  </div>

  <div class="legend">
    <span><span class="dot" style="background:#16a34a"></span> &#x2713; Confirmed (p&lt;0.05, sufficient n)</span>
    <span><span class="dot" style="background:#f59e0b"></span> &rarr; Directional (p&lt;0.10 or n-limited)</span>
    <span><span class="dot" style="background:#3b82f6"></span> &#x2691; Setup (structural / configuration guidance)</span>
  </div>

  <div class="platform-section">
    <h2>Apple News</h2>
    {an_html}
  </div>

  <div class="platform-section">
    <h2>SmartNews</h2>
    {sn_html}
  </div>

  <div class="platform-section">
    <h2>Push Notifications</h2>
    {notif_html}
  </div>

  <div class="footer">
    All rules are observational &mdash; based on historical performance correlations, not controlled experiments.
    Treat as starting configuration; validate against post-publication performance data.
    Full analysis: <a href="../" style="color:var(--accent)">McClatchy CSA headline analysis site</a>.
  </div>
</div>
</body>
</html>"""


if __name__ == "__main__":
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    html_out = generate()
    OUTPUT_PATH.write_text(html_out, encoding="utf-8")
    print(f"Style guide written to {OUTPUT_PATH}  ({len(html_out):,} chars)")
