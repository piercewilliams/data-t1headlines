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

# ── Nav (matches _NAV_PAGES order in generate_site.py) ──────────────────────
_NAV_PAGES = [
    ("Current Analysis",    "../"),
    ("Editorial Playbooks", "../playbook/"),
    ("Author Playbooks",    "../author-playbooks/"),
    ("Style Guide",         ""),          # active page -- empty href
    ("Experiments",         "../experiments/"),
    ("Headline Grader",     "../grader/"),
]

def _build_nav() -> str:
    links = []
    for name, href in _NAV_PAGES:
        if href == "":
            links.append(f'    <a href="./" class="nav-active">{name}</a>')
        else:
            links.append(f'    <a href="{href}">{name}</a>')
    links_html = "\n".join(links)
    return (
        f'<nav>\n'
        f'  <span class="brand">McClatchy CSA</span>\n'
        f'  <div class="nav-links">\n'
        f'{links_html}\n'
        f'  </div>\n'
        f'  <div class="nav-meta">\n'
        f'    <button id="theme-toggle" class="theme-btn" onclick="toggleTheme()" '
        f'aria-label="Toggle dark mode">\U0001f319</button>\n'
        f'  </div>\n'
        f'</nav>'
    )


# ── Rules ─────────────────────────────────────────────────────────────────────
# Each rule: (confidence, rule_text, note, context)
# confidence: "Confirmed" | "Directional" | "Setup"
# context: plain-language explanation of what this guidance is about and why it exists.

APPLE_NEWS_RULES = [
    (
        "Setup",
        "Tag every article with a non-Main section before publishing.",
        "Untagged articles land in the bottom 20% of Apple News views at 2.4\u00d7 the "
        "baseline rate and are almost never featured. Section tags are how Apple News "
        "routes articles to relevant feeds \u2014 without one, the article is essentially "
        "invisible to the algorithm.",
        "Apple News uses section metadata to route articles to topic-specific feeds. "
        "\u201cMain\u201d is not a real section \u2014 it\u2019s the default fallback when no section "
        "is assigned. Articles with only a Main tag are treated as unclassified and "
        "deprioritized. This is a one-time configuration fix per article, not a headline "
        "decision \u2014 but it has a larger impact on distribution than any headline formula.",
    ),
    (
        "Confirmed",
        "Use \u201cWhat to know\u201d only when intentionally targeting Featured placement.",
        "\u201cWhat to know\u201d is associated with higher featuring odds (1.8\u00d7 baseline) but "
        "non-featured \u201cWhat to know\u201d articles trend lower in organic views. Don\u2019t use "
        "it as a general-purpose formula \u2014 it optimizes for one outcome at the expense "
        "of the other.",
        "Apple\u2019s editors appear to favor \u201cWhat to know\u201d when selecting stories for the "
        "Featured slot \u2014 possibly because it signals a comprehensive briefing article. "
        "But readers who encounter a non-featured \u201cWhat to know\u201d article in a regular feed "
        "may find the format less compelling. The formula works as a targeting signal for "
        "editorial curation, not as an organic traffic driver.",
    ),
    (
        "Confirmed",
        "Use \u201cHere\u2019s\u201d for Crime and Business headlines when targeting Featured.",
        "Crime + \u201cHere\u2019s\u201d = 16% featuring rate (n=89). Business + \u201cHere\u2019s\u201d = "
        "14% (n=72). These are the strongest editorially writable, non-weather formulas "
        "in the dataset \u2014 and unlike \u201cWhat to know,\u201d \u201cHere\u2019s\u201d is also "
        "directionally safe for SmartNews (p=0.038).",
        "\u201cHere\u2019s what we know\u201d and \u201cHere\u2019s what happened\u201d are explanatory "
        "frames that Apple editors consistently select for breaking and developing stories. "
        "The formula signals authoritative, organized coverage \u2014 something editors want "
        "foregrounded. The effect is topic-conditional: it works for Crime and Business "
        "because those are topics where Apple News featuring is achievable. Sports content "
        "earns 0% featuring regardless of formula used.",
    ),
    (
        "Confirmed",
        "Avoid Apple News for Sports distribution. Focus Apple News effort on Crime, "
        "Business, and local-angle stories.",
        "Sports content earns 0% featuring on Apple News regardless of formula. "
        "Nation & World articles underperform local-angle sections by 20+ percentile "
        "points. SmartNews is the stronger channel for sports.",
        "Apple News\u2019s editorial curation prioritizes local news and civic content over "
        "sports. The sports finding is not formula-dependent \u2014 no headline formula "
        "unlocks featuring for sports content. The platform\u2019s own section taxonomy "
        "treats Sports as a distinct feed that rarely enters the main Featured rotation. "
        "Wire/national content (Nation & World) similarly underperforms because Apple "
        "News favors local publishers writing about their own markets.",
    ),
    (
        "Confirmed",
        "Target 90\u2013120 characters for Apple News headlines.",
        "Performance rises through 110\u2013119 chars. Below 70 and above 130 both "
        "underperform. This is more specific than Apple\u2019s own published guidance "
        "and is derived from T1 outlet performance data.",
        "Apple News displays article previews with a truncated headline in the feed. "
        "Too-short headlines don\u2019t convey enough context to earn a click. Too-long "
        "headlines get cut off visually and may signal low-quality writing to the "
        "algorithm. The 90\u2013120 char range is where T1 McClatchy articles consistently "
        "perform above median. This is a different optimal range than SmartNews "
        "(70\u201390 chars) \u2014 the two platforms have different display formats and "
        "different algorithm signals.",
    ),
    (
        "Confirmed",
        "Use question format only when intentionally targeting Featured placement "
        "\u2014 never for organic reach.",
        "Apple editors over-select question-format headlines for featuring. But "
        "question-format articles that are not featured perform below median in "
        "organic views. The format optimizes for editorial curation, not algorithmic "
        "distribution.",
        "The question format creates a tension: Apple\u2019s human editors appear to like "
        "questions as featured stories (perhaps because a clear question implies a "
        "satisfying answer). But the Apple News algorithm does not reward question "
        "format for non-featured articles \u2014 organic distribution of question "
        "headlines underperforms the baseline. This is one of the clearest "
        "Featured vs. organic divergences in the dataset. If the goal is organic "
        "views, avoid questions. If the goal is specifically to pursue a Featured "
        "slot, questions are a viable targeting tool.",
    ),
    (
        "Directional",
        "Increase number leads; reduce question-format headlines in your formula mix.",
        "Number leads are the only formula trending upward from Q1 2025 to Q1 2026 "
        "\u2014 they started below baseline and crossed into above-baseline territory. "
        "Question format is trending down over the same period.",
        "This is a time-series observation across all T1 Apple News articles. The "
        "mechanism isn\u2019t confirmed, but the pattern is consistent: as the Apple News "
        "environment matures, list-structured and numeric headlines are gaining "
        "traction while question format loses it. This directional shift suggests "
        "leaning into number leads (\u201c5 things\u2026\u201d, \u201c3 reasons\u2026\u201d) and "
        "pulling back on question-format articles that aren\u2019t specifically targeting "
        "a Featured slot.",
    ),
    (
        "Directional",
        "For Nature/Wildlife/Science: use discovery framing.",
        "\u201cScientists found\u2026\u201d, \u201cNever-before-seen\u2026\u201d, \u201cRare\u2026\u201d "
        "\u2014 this framing drives the highest-ceiling performance for General/Discovery "
        "content (53K+ views observed on a single article). The discovery angle works "
        "because it signals novelty and scientific validation simultaneously.",
        "General/Discovery content (nature, wildlife, science) has the highest "
        "individual-article ceiling of any content type in the McClatchy T1 dataset \u2014 "
        "a single snake species article reached 53K views. The common thread across "
        "top performers in this vertical is a discovery frame: something new was found, "
        "something rare was seen, something never documented before was observed. "
        "The headline should foreground the novelty (\u201cNever-before-seen\u201d, "
        "\u201cRare footage\u201d, \u201cScientists discover\u201d) rather than burying it in the middle "
        "of the headline. This framing also works for SmartNews \u2014 apply it consistently "
        "across both platforms for this content type.",
    ),
    (
        "Setup",
        "Mind-Body, Everyday Living, and Experience content: optimize for organic views, "
        "not featuring.",
        "These verticals currently earn 0% featuring rate on Apple News (Jan\u2013Feb 2026, "
        "n=22 matched articles \u2014 preliminary). Featuring is not a lever for this content "
        "type. Formula guidance for these verticals comes from platform-wide rules, not "
        "vertical-specific signal (sample size is too small for vertical-specific analysis).",
        "The content produced by Sara Vallone\u2019s trendhunter team (Mind-Body, Everyday "
        "Living, Experience) has not received any Apple News Featured placements in the "
        "Jan\u2013Feb 2026 data window (vs. a 1.2% baseline across all ANP articles). This "
        "may reflect the content type, the topics, or the section tagging \u2014 the root "
        "cause is not yet established. Until the cause is identified, do not build "
        "strategy around Featured placement for this content. Focus on organic Apple News "
        "views and SmartNews distribution, where formula choices have a clearer effect.",
    ),
]

SMARTNEWS_RULES = [
    (
        "Confirmed",
        "Never use question format for SmartNews.",
        "Question headlines drop to 0.42 percentile rank \u2014 0.08 below baseline "
        "(p=3.4e-6, n=918). This is the strongest single avoidance rule in the "
        "entire SmartNews dataset.",
        "SmartNews uses an algorithmic feed with no human editorial curation layer. "
        "The algorithm ranks articles by predicted engagement and completion rate. "
        "Question-format headlines perform significantly below baseline across all "
        "topics and publication types \u2014 this is one of the most statistically "
        "robust findings in the analysis (p=3.4e-6 on a dataset of 918 articles). "
        "The penalty is consistent enough that it should be treated as a hard rule, "
        "not a soft guideline. This is the opposite of the Apple News Featured dynamic, "
        "where editors occasionally favor questions.",
    ),
    (
        "Confirmed",
        "Never use \u201cWhat to know\u201d for SmartNews.",
        "\u201cWhat to know\u201d is the worst-performing formula on SmartNews: 0.37 percentile "
        "rank (p=3.0e-6, n=213). It underperforms the question penalty and is the "
        "single largest performance drag in the dataset.",
        "\u201cWhat to know\u201d combines two weak signals for SmartNews: it reads as a "
        "summary/briefing format (lower engagement prediction) and it doesn\u2019t "
        "front-load a specific concrete claim or fact. SmartNews rewards headlines "
        "that clearly signal what the reader will learn and why it\u2019s worth clicking. "
        "\u201cWhat to know\u201d signals \u201cgeneral overview\u201d rather than \u201cspecific revelation.\u201d "
        "The effect is statistically comparable to the question penalty \u2014 both are "
        "hard avoidance rules for SmartNews.",
    ),
    (
        "Confirmed",
        "Target 70\u201390 characters for SmartNews headlines.",
        "The 80\u201399 char range is the confirmed optimal bin. The 100-character ceiling "
        "published in Apple\u2019s own guidance has no statistical basis in SmartNews data "
        "(p=0.915 \u2014 not significant). SmartNews and Apple News have different optimal "
        "length ranges.",
        "SmartNews displays article headlines in a more compact format than Apple News. "
        "The shorter optimal length (70\u201390 vs. 90\u2013120 for Apple News) reflects "
        "differences in how each platform renders article previews. A headline that "
        "feels right-sized for Apple News may feel bloated in a SmartNews feed. When "
        "writing one headline for both platforms, prioritize the Apple News length and "
        "trim for SmartNews \u2014 or write two versions (see Platform Headline Pairs "
        "in the Editorial Playbooks).",
    ),
    (
        "Confirmed",
        "Direct declarative headlines are the safe SmartNews default.",
        "Subject-verb-object format (e.g., \u201c[Person] did [thing] at [place]\u201d) is "
        "never penalized on SmartNews. Use it as the fallback when no formula signal "
        "applies or when avoiding question/WTK format.",
        "SmartNews rewards clarity and specificity. A direct declarative headline "
        "tells the reader exactly what happened without requiring them to complete "
        "a mental question or fill in a gap. This format also avoids the question "
        "and WTK penalties. It\u2019s not a growth formula (it doesn\u2019t significantly "
        "lift above baseline) but it\u2019s the safest option when you don\u2019t have "
        "a strong formula signal for a particular story.",
    ),
    (
        "Directional",
        "Use \u201cHere\u2019s\u201d when writing one headline for both Apple News and SmartNews.",
        "\u201cHere\u2019s\u201d is directionally above baseline on SmartNews (p=0.038, does not "
        "survive strict Bonferroni correction at k=5) and works for Apple News "
        "featuring. It is the only formula that doesn\u2019t hurt on either platform.",
        "Most headline formulas create a platform trade-off: what works for Apple News "
        "hurts SmartNews, and vice versa. \u201cHere\u2019s what to know\u201d and \u201cWhat to know\u201d "
        "are dramatic examples of this tension. \u201cHere\u2019s\u201d (\u201cHere\u2019s what happened,\u201d "
        "\u201cHere\u2019s what this means\u201d) is the exception: it performs above baseline on "
        "SmartNews (directionally) while also being the strongest confirmed formula "
        "for Apple News Crime/Business featuring. When operational constraints mean "
        "publishing one headline to both platforms, \u201cHere\u2019s\u201d is the safest choice. "
        "The p=0.038 finding for SmartNews does not survive Bonferroni correction "
        "at k=5 tests, so treat it as directional guidance, not a confirmed finding.",
    ),
    (
        "Directional",
        "Use number leads when the topic allows.",
        "Number leads are the only SmartNews formula with a positive and growing "
        "performance trend across 2025\u20132026. Stronger for list-format stories "
        "(\u201c5 things to know,\u201d \u201c7 ways to\u2026\u201d) than for arbitrary counts.",
        "Number leads (\u201c5 things\u2026,\u201d \u201c3 reasons\u2026,\u201d \u201c10 ways\u2026\u201d) signal "
        "structured, scannable content \u2014 which SmartNews rewards because readers "
        "are more likely to engage with content that promises a clear, bounded payoff. "
        "The trend data shows number leads improving over time on both Apple News and "
        "SmartNews, making them a relatively safe investment in both channels. "
        "The effect is stronger when the number reflects the actual structure of the "
        "article (a genuine list) rather than being applied artificially to a narrative piece.",
    ),
    (
        "Directional",
        "For Nature/Wildlife/Science: apply the same discovery framing as Apple News, "
        "and avoid question format.",
        "The question penalty applies to science and nature content on SmartNews just "
        "as it does to other topics (p=3.4e-6). Discovery framing (\u201cScientists found,\u201d "
        "\u201cNever-before-seen,\u201d \u201cRare\u2026\u201d) works on both platforms for this content type.",
        "Nature/wildlife/science content has the highest individual-article ceiling "
        "in the dataset (53K+ views). The same discovery-frame headlines that work "
        "for Apple News also translate to SmartNews because the framing is driven by "
        "content novelty (a genuinely rare finding or observation), not by platform-specific "
        "algorithm preferences. The one SmartNews-specific addition: avoid question format "
        "even for science stories (\u201cIs this the rarest animal ever found?\u201d hurts on "
        "SmartNews). Use declarative discovery framing instead (\u201cScientists find "
        "never-before-seen species in [location]\u201d).",
    ),
]

NOTIFICATION_RULES = [
    (
        "Confirmed",
        "Use attribution language for news brand notifications.",
        "\u201cSays,\u201d \u201ctold,\u201d \u201creports,\u201d \u201creveals\u201d \u2014 associated with "
        "1.18\u00d7 CTR lift (p=0.020, n=59). The only consistent signal still lifting "
        "notification CTR against a declining overall baseline.",
        "Push notifications from news brands compete with dozens of other apps for "
        "the same lock screen. Attribution language (\u201cSheriff says\u2026,\u201d "
        "\u201cWitness told reporters\u2026\u201d) signals that the story has a specific, "
        "sourced claim \u2014 something a reader can\u2019t get from a social post or "
        "a headline from a competitor. It also signals credibility: the outlet has "
        "a named source, not just a rumor or rewrite. This effect is consistent across "
        "news brand notifications (Miami Herald, KC Star, Charlotte Observer, "
        "Sacramento Bee) and is the most reliable positive signal in the notification dataset.",
    ),
    (
        "Confirmed",
        "Use crime/death outcome words when factually accurate.",
        "\u201cDead,\u201d \u201ckilled,\u201d \u201carrested,\u201d \u201ccharged,\u201d \u201cconvicted\u201d "
        "\u2014 1.26\u00d7 CTR lift (p=0.0015, n=55). Strongest single notification signal. "
        "Stack with attribution language for maximum effect (\u201cSuspect charged, "
        "sheriff says\u201d).",
        "Outcome language tells readers the story has reached a definitive state. "
        "Crime stories with pending or uncertain status generate less urgency than "
        "stories where something has been resolved \u2014 an arrest was made, charges "
        "were filed, a verdict was reached. Readers have learned to treat breaking "
        "crime coverage with skepticism until confirmed outcomes appear. Outcome "
        "words signal that the story has cleared that threshold. The combination "
        "of outcome word + attribution (\u201c[Name] convicted, prosecutor says\u201d) "
        "stacks both signals and produces the highest CTR in the dataset.",
    ),
    (
        "Confirmed",
        "Avoid question format in push notifications.",
        "Question format consistently hurts CTR across both news brand and celebrity "
        "content types in the notification dataset. The penalty applies regardless "
        "of topic or publication.",
        "Push notifications compete on attention in a context where the reader hasn\u2019t "
        "chosen to engage \u2014 they\u2019ve been interrupted. A question headline in a "
        "notification creates friction: the reader has to hold the question in mind "
        "and decide whether the answer is worth tapping. A declarative headline with "
        "specific information removes that friction. The question format also has the "
        "lowest perceived credibility signal of any formula \u2014 it reads more like "
        "clickbait than breaking news. This rule applies universally to notifications; "
        "the Apple News Featured exception (where editors favor questions) does not "
        "transfer to the notification surface.",
    ),
    (
        "Confirmed",
        "For celebrity/entertainment notifications: use possessive named entity.",
        "\u201c[Celebrity]\u2019s [situation]\u201d outperforms other formats for entertainment "
        "notifications. Numbers in the headline hurt CTR in entertainment context "
        "(opposite of the news brand pattern). The celebrity\u2019s name and a relational "
        "hook are the two key elements.",
        "Entertainment readers follow people, not topics. The possessive structure "
        "(\u201cTaylor Swift\u2019s tour cancellation,\u201d \u201cBeyonc\u00e9\u2019s statement,\u201d "
        "\u201cTom Hanks\u2019 diagnosis\u201d) signals a personal development for someone "
        "the reader tracks. The named entity provides identification; the possessive "
        "signals intimacy and personal stakes. This is a different engagement model "
        "than news brand notifications, which reward credibility and outcome signals. "
        "Numbers in entertainment headlines (\u201c5 things about [celebrity]\u2019s drama\u201d) "
        "underperform because they signal listicle format in a context where readers "
        "want the specific personal development, not a curated list about it.",
    ),
    (
        "Directional",
        "For serial/escalating stories: frame each notification as an installment.",
        "Possessive named entity + new development + escalating stakes is the "
        "highest-CTR notification structure for breaking stories with a named anchor. "
        "Each update should function as a chapter, not a re-introduction.",
        "The top-performing news brand notification series in the dataset followed a "
        "single developing story \u2014 a disappearance with a celebrity connection \u2014 "
        "across multiple updates. Each notification built on the last rather than "
        "re-establishing the full context. Readers who engaged with earlier installments "
        "already have the context; the notification should deliver the new development "
        "(\u201cGuthrie family attorney speaks out,\u201d \u201cSecond suspect named\u201d) rather than "
        "re-summarizing. This structure rewards loyal notification subscribers while "
        "maintaining enough context to be comprehensible to first-time engagers.",
    ),
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
    for conf, rule, note, context in rules:
        color   = conf_colors.get(conf, "#64748b")
        label   = conf_symbols.get(conf, conf)
        ctx_id  = f"ctx-{abs(hash(rule)) % 100000}"
        rows += f"""
<div class="rule">
  <div class="rule-top">
    <span class="conf-badge" style="background:{color}">{html.escape(label)}</span>
    <strong class="rule-text">{html.escape(rule)}</strong>
  </div>
  <p class="rule-note">{html.escape(note)}</p>
  <details class="rule-context">
    <summary>Why this rule exists</summary>
    <p class="rule-context-body">{html.escape(context)}</p>
  </details>
</div>"""
    return rows


def generate() -> str:
    from datetime import date
    today = date.today().strftime("%B %d, %Y")

    nav_html   = _build_nav()
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
  body.theme-light {{
    --bg: #ffffff; --bg-muted: #f5f5f7; --text: #1d1d1f; --text-muted: #6e6e73;
    --border: #d2d2d7; --surface: #f8fafc; --accent: #0071e3;
    --nav-bg: rgba(255,255,255,0.88);
  }}
  body.theme-dark {{
    --bg: #0f172a; --bg-muted: #1e293b; --text: #f1f5f9; --text-muted: #b0bec5;
    --border: #334155; --surface: #1e293b; --accent: #3b82f6;
    --nav-bg: rgba(15,23,42,0.88);
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: var(--bg); color: var(--text); line-height: 1.5; }}

  /* ── Canonical nav (identical to all other site pages) ── */
  nav {{ position:sticky; top:0; z-index:100; background:var(--nav-bg);
         backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px);
         border-bottom:1px solid var(--border); height:44px;
         display:flex; align-items:center; gap:0; padding:0 28px; }}
  .brand {{ font-size:11px; font-weight:600; letter-spacing:0.07em;
            text-transform:uppercase; color:var(--text); flex-shrink:0; }}
  .nav-links {{ display:flex; align-items:center; gap:16px; margin-left:24px; flex:1; }}
  .nav-links a {{ font-size:12px; color:var(--text-muted); text-decoration:none;
                  transition:color 0.15s; }}
  .nav-links a:hover {{ color:var(--text); }}
  .nav-links a.nav-active {{ color:var(--text); font-weight:600; }}
  .nav-meta {{ display:flex; align-items:center; gap:8px; margin-left:auto;
               padding-left:20px; border-left:1px solid var(--border); }}
  .theme-btn {{ background:none; border:1px solid var(--border); color:var(--text-muted);
                font-size:13px; line-height:1; cursor:pointer; border-radius:6px;
                padding:3px 9px; transition:background 0.15s,color 0.15s,border-color 0.15s; }}
  .theme-btn:hover {{ background:var(--bg-muted); color:var(--text); border-color:var(--text-muted); }}

  /* ── Page layout ─────────────────────────────────────────────── */
  .page {{ max-width: 860px; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }}
  .header {{ border-bottom: 2px solid var(--accent); padding-bottom: 1rem; margin-bottom: 2rem; }}
  .header h1 {{ font-size: 1.6rem; font-weight: 800; }}
  .header .meta {{ font-size: .8rem; color: var(--text-muted); margin-top: .25rem; }}
  .intro {{ background: var(--surface); border-left: 3px solid var(--accent);
            padding: .9rem 1rem; margin-bottom: 2rem; font-size: .88rem;
            line-height: 1.55; border-radius: 0 4px 4px 0; }}
  .intro p + p {{ margin-top: .6rem; }}
  .platform-section {{ margin-bottom: 2.5rem; }}
  .platform-section h2 {{ font-size: 1rem; font-weight: 700; letter-spacing: .06em;
                           text-transform: uppercase; color: var(--accent);
                           border-bottom: 1px solid var(--border); padding-bottom: .4rem;
                           margin-bottom: .5rem; }}
  .platform-intro {{ font-size: .82rem; color: var(--text-muted); margin-bottom: 1rem;
                     line-height: 1.5; }}
  .rule {{ padding: .9rem 1rem; border-left: 3px solid var(--border);
           margin-bottom: .75rem; background: var(--surface); border-radius: 0 4px 4px 0; }}
  .rule-top {{ display: flex; align-items: flex-start; gap: .6rem;
               margin-bottom: .3rem; flex-wrap: wrap; }}
  .conf-badge {{ font-size: .7rem; font-weight: 700; color: #fff; padding: 1px 7px;
                 border-radius: 3px; white-space: nowrap; flex-shrink: 0; margin-top: 2px; }}
  .rule-text {{ font-size: .88rem; font-weight: 600; color: var(--text); }}
  .rule-note {{ font-size: .8rem; color: var(--text-muted); margin-top: .15rem;
                line-height: 1.45; }}
  .rule-context {{ margin-top: .5rem; }}
  .rule-context summary {{
    font-size: .72rem; font-weight: 600; color: var(--accent);
    cursor: pointer; letter-spacing: .02em; user-select: none;
    display: inline-block;
  }}
  .rule-context summary:hover {{ text-decoration: underline; }}
  .rule-context-body {{
    font-size: .78rem; color: var(--text-muted); margin-top: .4rem;
    padding: .6rem .8rem; background: var(--bg); border-radius: 4px;
    border: 1px solid var(--border); line-height: 1.55;
  }}
  .legend {{ display: flex; gap: 1rem; font-size: .75rem; color: var(--text-muted);
             margin-bottom: 1.5rem; flex-wrap: wrap; }}
  .legend span {{ display: flex; align-items: center; gap: .3rem; }}
  .legend .dot {{ width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }}
  .footer {{ font-size: .75rem; color: var(--text-muted); border-top: 1px solid var(--border);
             padding-top: 1rem; margin-top: 2rem; }}
  @media print {{
    nav {{ display: none; }}
    .page {{ max-width: 100%; padding: 1rem; }}
    .rule {{ break-inside: avoid; }}
    .rule-context summary {{ display: none; }}
    .rule-context-body {{ display: block !important; border: none; padding: .3rem 0; }}
  }}
</style>
</head>
<body class="theme-dark">
{nav_html}
<div class="page">
  <div class="header">
    <h1>McClatchy Headline Style Guide</h1>
    <div class="meta">Generated {today} &middot; McClatchy CSA &middot; Based on T1 headline performance data 2025&ndash;2026</div>
  </div>

  <div class="intro">
    <p>These rules are drawn directly from statistical analysis of McClatchy T1 headline performance
    across Apple News, SmartNews, and push notifications. Each rule is observational &mdash; based
    on correlation with views, featuring rate, or CTR &mdash; not from controlled experiments.</p>
    <p><strong>How to use this guide:</strong> Apply Confirmed rules without hesitation &mdash; they
    meet the p&lt;0.05 threshold with sufficient sample size. Apply Directional rules as strong
    defaults &mdash; they show a real pattern but with less statistical certainty. Setup rules
    are structural/operational &mdash; they work regardless of headline formula and should be
    treated as mandatory configuration, not optional guidance.</p>
    <p>Expand &ldquo;Why this rule exists&rdquo; under any rule for the full context: what the data
    showed, why the platform behaves this way, and when to apply (or override) the rule.</p>
  </div>

  <div class="legend">
    <span><span class="dot" style="background:#16a34a"></span> &#x2713; Confirmed (p&lt;0.05, sufficient n)</span>
    <span><span class="dot" style="background:#f59e0b"></span> &rarr; Directional (p&lt;0.10 or n-limited)</span>
    <span><span class="dot" style="background:#3b82f6"></span> &#x2691; Setup (structural / configuration guidance)</span>
  </div>

  <div class="platform-section">
    <h2>Apple News</h2>
    <p class="platform-intro">Apple News features a two-tier distribution model: editorial
    curation (Featured slot) and organic algorithmic distribution. These are different outcomes
    driven by different signals. Several rules below apply specifically to one tier &mdash;
    read each note carefully. Character length target: <strong>90&ndash;120 chars</strong>.</p>
    {an_html}
  </div>

  <div class="platform-section">
    <h2>SmartNews</h2>
    <p class="platform-intro">SmartNews is fully algorithmic &mdash; no editorial curation layer.
    Formula effects are measured against a percentile rank baseline (0.5 = average for that
    outlet and month). The avoidance rules here are the most statistically robust findings
    in the entire analysis. Character length target: <strong>70&ndash;90 chars</strong>.</p>
    {sn_html}
  </div>

  <div class="platform-section">
    <h2>Push Notifications</h2>
    <p class="platform-intro">Push notification CTR is measured differently from views &mdash;
    it reflects the share of people who received the notification and tapped it. The formula
    effects on notifications are 2&ndash;5&times; larger than formula effects on article views,
    making this the highest-leverage editorial surface in the analysis. News brand and
    celebrity/entertainment notifications follow different signal patterns &mdash;
    rules below apply to news brand content unless otherwise noted.</p>
    {notif_html}
  </div>

  <div class="footer">
    All rules are observational &mdash; based on historical performance correlations, not controlled experiments.
    Treat as starting configuration; validate against post-publication performance data.
    Full analysis: <a href="../" style="color:var(--accent)">McClatchy CSA headline analysis site</a>.
  </div>
</div>

<script>
function applyTheme(t) {{
  document.body.className = 'theme-' + t;
  try {{ localStorage.setItem('theme', t); }} catch(e) {{}}
  var btn = document.getElementById('theme-toggle');
  if (btn) btn.textContent = t === 'dark' ? '\u2600\ufe0f' : '\U0001f319';
}}
function toggleTheme() {{
  applyTheme(document.body.classList.contains('theme-dark') ? 'light' : 'dark');
}}
window.addEventListener('DOMContentLoaded', function() {{
  var stored = localStorage.getItem('theme') || 'dark';
  applyTheme(stored);
}});
</script>
</body>
</html>"""


if __name__ == "__main__":
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    html_out = generate()
    OUTPUT_PATH.write_text(html_out, encoding="utf-8")
    print(f"Style guide written to {OUTPUT_PATH}  ({len(html_out):,} chars)")
