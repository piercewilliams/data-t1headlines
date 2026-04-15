#!/usr/bin/env python3
"""generate_grader.py — Headline Grader

Reads Sara Vallone's live Tracker sheet, grades recent headlines against
defined criteria, and outputs docs/grader/index.html.

Usage:
    python3 generate_grader.py [--lookback N] [--skip-llm] [--dry-run]

Options:
    --lookback N    Days to look back (default: 1)
    --skip-llm      Skip Groq LLM eval (objective criteria only)
    --dry-run       Print results, do not write HTML

Env:
    GROQ_API_KEY                — required for LLM criteria
    GOOGLE_SERVICE_ACCOUNT_FILE — path to JSON key (default: ~/.credentials/pierce-tools.json)
"""

import argparse
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

# ── Config ────────────────────────────────────────────────────────────────────

SHEET_ID      = "14_0eK46g3IEj7L_yp9FIdWwvnuYI5f-vAuP7DDhSPg8"
SA_FILE       = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE",
                           str(Path.home() / ".credentials" / "pierce-tools.json"))
OUTPUT_PATH   = Path("docs/grader/index.html")
HISTORY_PATH  = Path("docs/grader/history.json")
HISTORY_MAX   = 30
DEFAULT_LOOKBACK = 1
GROQ_MODEL    = "llama-3.3-70b-versatile"
GROQ_FALLBACK = "llama3-8b-8192"

# ── Criterion registry ────────────────────────────────────────────────────────
# (key, display_name, tier, weight, method)
# weight=0 → informational/disabled (shown but not scored)
# method:  "obj" | "llm" | "info"

CRITERIA = [
    ("char_count",     "Character count (SN 70–90 / AN 90–120)", "structure", 1,  "obj"),
    ("subject_leads",  "Named entity leads",                      "structure", 1,  "obj"),
    ("no_articles",    "No article lead",                         "structure", 1,  "obj"),
    ("active_voice",   "Active voice",                            "structure", 1,  "llm"),
    ("no_lead_burial", "No lead burial",                          "structure", 2,  "llm"),
    ("formula",        "Formula present",                         "formula",   2,  "obj"),
    ("no_vague_wtk",   "No 'What to know' headline",               "formula",   1,  "obj"),
    ("keyword",        "Keyword present",                         "formula",   1,  "obj"),
    ("number",         "Number lead (SmartNews ↑ / Apple News ↓)","formula",   0,  "info"),
    ("no_dym",         "No 'Did you miss'",                       "quality",   2,  "obj"),
    ("no_questions",   "No question headline (organic reach)",    "quality",   1,  "obj"),
    ("no_allcaps",     "No all-caps words",                       "quality",   1,  "obj"),
    ("curiosity",      "Curiosity gap",                           "quality",   1,  "llm"),
    ("accurate",       "Factually accurate",                      "quality",   2,  "llm"),
    ("apple_heres",    "Here's/Here are (Apple News)",            "platform",  0,  "info"),
]

META = {k: {"name": n, "tier": t, "weight": w, "method": m}
        for k, n, t, w, m in CRITERIA}

TIER_LABELS = {
    "structure": "Structure & Length",
    "formula":   "Formula & Signal",
    "quality":   "Quality Flags",
    "platform":  "Platform-Specific (informational)",
}

# ── Author → Content Vertical mapping (confirmed by Sarah Price 2026-04-08) ───
AUTHOR_VERTICAL: dict[str, str] = {
    "Allison Palmer":       "Mind-Body",
    "Lauren J-G":           "Everyday Living",
    "Lauren Jarvis-Gibson": "Everyday Living",
    "Lauren Schuster":      "Experience",
    "Ryan Brennan":         "General/Discovery",
    "Hanna Wickes":         "General/Discovery",
    "Hanna WIckes":         "General/Discovery",
    "Samantha Agate":       "General/Discovery",
}

# Per-vertical headline tips shown in grader cards
VERTICAL_TIPS: dict[str, list[str]] = {
    "Mind-Body": [
        "Number leads and service-journalism framing work well ('5 ways to…', 'How to…')",
        "Avoid 'What to know' — worst-performing formula on SmartNews",
        "Target 90–120 chars for Apple News; 70–90 for SmartNews",
        "0% featuring rate on Apple News — optimize for organic reach, not featuring",
    ],
    "Everyday Living": [
        "List/number-lead format is the strongest signal for this vertical (home, décor, lifestyle)",
        "Avoid question format for SmartNews distribution",
        "Target 90–120 chars for Apple News; 70–90 for SmartNews",
        "0% featuring rate on Apple News — optimize for organic reach",
    ],
    "Experience": [
        "Service framing ('Here's how to…', 'Everything you need to know about…') works for travel/experiences",
        "Avoid 'What to know' and question format for SmartNews",
        "Financial experience headlines (retirement, HSA) perform well — specific numbers help",
        "0% featuring rate on Apple News — optimize for organic reach",
    ],
    "General/Discovery": [
        "Nature/wildlife/science: discovery framing ('Scientists found…', 'Never-before-seen…') drives highest ceiling",
        "Avoid question format for SmartNews (−0.08 pct_rank, p=3.4e-6)",
        "Number leads are trending upward — use when story allows",
        "High ceiling potential (53K+ views) for breaking science/wildlife stories — prioritize strong specificity",
    ],
}

# ── Google Sheets ─────────────────────────────────────────────────────────────

def fetch_records():
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds  = Credentials.from_service_account_file(SA_FILE, scopes=scopes)
    gc     = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID).sheet1.get_all_records()


def filter_recent(records, lookback_days):
    cutoff = datetime.date.today() - datetime.timedelta(days=lookback_days)
    out = []
    for r in records:
        h   = str(r.get("Headline", "")).strip()
        raw = str(r.get("Publication Date", "")).strip()
        if not h or not raw:
            continue
        d = None
        for fmt in ("%m/%d/%Y", "%m/%d/%y"):
            try:
                d = datetime.datetime.strptime(raw, fmt).date()
                break
            except ValueError:
                pass
        if d and d >= cutoff:
            out.append(r)
    return out

# ── Objective criteria ────────────────────────────────────────────────────────

_STOP = {"a","an","the","it","there","they","this","that","these","those",
         "he","she","we","you","i","here","in","at","on","after","when","if",
         "as","for","with","from","by"}

_ACRONYMS = {"FBI","CIA","NFL","NBA","MLB","NHL","GOP","NASA","CDC","FDA",
             "IRS","TSA","AOL","MSN","CNN","BBC","ABC","NBC","CBS","US","UK",
             "EU","UN","AI","CEO","CFO","COO","LGBTQ","LGBTQIA","NYPD","LAPD",
             "AP","UX","SEC","EPA","DOJ","FCC","FTC","FDIC","WHO","IMF","GDP",
             "NYT","NAACP","ACLU","NRA","DEA","ATF","ICE","DHS","DOD","NATO",
             "OPEC","IPO","NFT","ESG","DEI","HR","PR","LA","NYC","DC","TX",
             "HGTV","ESPN","HBO","PBS","NPR","BET","MTV","TMZ","ET","WSJ"}

_FORMULAS = [
    (r"^\d",                 "Number lead"),
    (r"\bwhat to know\b",    "'What to know'"),
    (r"\bhere\u2019?s\b|\bhere are\b", "'Here's/Here are'"),
    (r"\b\w+\u2019?s\b",     "Possessive"),
]


def _parse_platform(record):
    """Normalize the Tracker 'Syndication platform' value to an internal key."""
    raw = str(record.get("Syndication platform", "")).strip().lower()
    if "apple" in raw:
        return "apple_news"
    if "smart" in raw:
        return "smart_news"
    if "msn" in raw:
        return "msn"
    if "google" in raw:
        return "google_news"
    return "unknown"

_PLATFORM_LABELS = {
    "apple_news":  "Apple News",
    "smart_news":  "SmartNews",
    "msn":         "MSN",
    "google_news": "Google News",
    "unknown":     "",
}


def _char_count(h, platform="unknown"):
    n = len(h)
    if platform == "apple_news":
        ok = 90 <= n <= 120
        if n < 90:
            note = f"{n} chars — below Apple News target (90–120)"
        elif n > 120:
            note = f"{n} chars — above Apple News target (90–120)"
        else:
            note = f"{n} chars — Apple News range ✓"
    elif platform == "smart_news":
        ok = 70 <= n <= 90
        if n < 70:
            note = f"{n} chars — below SmartNews target (70–90)"
        elif n > 90:
            note = f"{n} chars — above SmartNews target (70–90)"
        else:
            note = f"{n} chars — SmartNews range ✓"
    else:
        # Unknown/other: pass if valid for at least one platform
        ok = 70 <= n <= 120
        if n < 70:
            note = f"{n} chars (too short for both platforms)"
        elif n > 120:
            note = f"{n} chars (too long for both platforms)"
        elif n <= 90:
            note = f"{n} chars (SmartNews range; short for Apple News)"
        else:
            note = f"{n} chars (Apple News range; long for SmartNews)"
    return ok, note


def _subject_leads(h):
    # strip leading punctuation/quotes
    first = re.split(r'[\s\u201c\u2018"\'(]', h.strip())[0].strip("\u2019\u2018\"'.,!?:;")
    fail  = first.lower() in _STOP
    return not fail, f"Leads with \u2018{first}\u2019"


def _no_articles(h):
    fail = bool(re.match(r"^(The|A|An)\s", h.strip(), re.I))
    return not fail, "Starts with article" if fail else "OK"


def _formula(h):
    hl = h.lower()
    for pat, label in _FORMULAS:
        if re.search(pat, hl):
            return True, label
    return False, "No recognized formula"


def _keyword(h, kw_str):
    if not kw_str:
        return False, "No keywords in sheet"
    keywords = [k.strip().lower() for k in str(kw_str).split(",") if k.strip()]
    hl = h.lower()
    found = [k for k in keywords if k in hl]
    if found:
        return True, f"Found: {', '.join(found)}"
    return False, f"Missing: {', '.join(keywords[:3])}"


def _number(h, platform="unknown"):
    has = bool(re.search(r"\d", h))
    if platform == "smart_news":
        note = ("Number detected — positive SmartNews signal" if has
                else "No number lead (consider for SmartNews)")
    elif platform == "apple_news":
        note = ("Number detected — caution: underperforms on Apple News" if has
                else "No number lead")
    else:
        note = "Number detected" if has else "No number"
    return has, note


def _no_dym(h):
    fail = bool(re.search(r"\bdid you miss\b", h, re.I))
    return not fail, "Contains \u2018Did you miss\u2019" if fail else "OK"


def _no_questions(h):
    """Question headlines underperform on both Apple News and SmartNews for organic reach."""
    fail = h.strip().endswith("?")
    return not fail, "Question headline \u2014 underperforms on both platforms" if fail else "OK"


def _no_wtk(h):
    """'What to Know' is the worst-performing SmartNews formula (pct_rank 0.37, p=3.0e-6, n=213).
    Avoid on all platforms for organic reach."""
    fail = bool(re.search(r"\bwhat to know\b", h, re.I))
    return not fail, "\u2018What to know\u2019 \u2014 worst SmartNews formula (p=3.0e\u22126, n=213)" if fail else "OK"


def _no_allcaps(h):
    bad = [w for w in re.findall(r"\b[A-Z]{3,}\b", h) if w not in _ACRONYMS]
    return len(bad) == 0, f"All-caps: {', '.join(bad)}" if bad else "OK"


def _apple_heres(h):
    has = bool(re.search(r"\bhere\u2019?s\b|\bhere are\b", h, re.I))
    return has, "Present" if has else "Not present"

# ── LLM evaluation ────────────────────────────────────────────────────────────

_LLM_PROMPT = """Evaluate this news headline against 4 criteria. Keep each reason under 8 words.

Headline: {headline}

Criteria:
1. active_voice — Uses active voice; fails on passive constructions like "was announced by" or "is being investigated".
2. no_lead_burial — Key news fact is in the first half of the headline.
3. curiosity — Creates a compelling click reason without being misleading.
4. accurate — Headline appears factually accurate and not sensationalized.

Return ONLY valid JSON, no extra text:
{{"active_voice":{{"pass":bool,"reason":"str"}},"no_lead_burial":{{"pass":bool,"reason":"str"}},"curiosity":{{"pass":bool,"reason":"str"}},"accurate":{{"pass":bool,"reason":"str"}}}}"""

_LLM_KEYS = ("active_voice", "no_lead_burial", "curiosity", "accurate")


def eval_llm(headline, client):
    if client is None:
        return {}
    for model in (GROQ_MODEL, GROQ_FALLBACK):
        for attempt in range(2):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user",
                               "content": _LLM_PROMPT.format(
                                   headline=json.dumps(headline))}],
                    temperature=0.1,
                    max_tokens=400,
                )
                raw = resp.choices[0].message.content.strip()
                m = re.search(r"\{.*\}", raw, re.DOTALL)
                if m:
                    return json.loads(m.group())
            except Exception as e:
                if attempt == 0:
                    time.sleep(2)
                else:
                    print(f"  LLM ({model}) error: {e}", file=sys.stderr)
    return {}

# ── Grade one record ──────────────────────────────────────────────────────────

def grade(record, llm_client):
    h        = str(record.get("Headline", "")).strip()
    kws      = str(record.get("Primary Keywords", ""))
    platform = _parse_platform(record)

    res = {}
    res["char_count"]     = _char_count(h, platform)
    res["subject_leads"]  = _subject_leads(h)
    res["no_articles"]    = _no_articles(h)
    res["formula"]        = _formula(h)
    res["no_vague_wtk"]   = _no_wtk(h)
    res["keyword"]        = _keyword(h, kws)
    res["number"]         = _number(h, platform)
    res["no_dym"]         = _no_dym(h)
    res["no_questions"]   = _no_questions(h)
    res["no_allcaps"]     = _no_allcaps(h)
    res["apple_heres"]    = _apple_heres(h)

    llm = eval_llm(h, llm_client)
    for key in _LLM_KEYS:
        if key in llm:
            res[key] = (llm[key]["pass"], llm[key]["reason"])
        else:
            res[key] = (None, "LLM eval unavailable")

    return res


def score(res):
    earned = total = 0
    for key, meta in META.items():
        w = meta["weight"]
        if w == 0:
            continue
        val = res.get(key, (None,))[0]
        if val is None:
            continue
        total  += w
        earned += w if val else 0
    return round(earned / total * 100) if total else 0

# ── Aggregate stats ───────────────────────────────────────────────────────────

def aggregate(graded):
    stats = {}
    for key, meta in META.items():
        if meta["weight"] == 0:
            continue
        passes = fails = 0
        for _, res, _ in graded:
            v = res.get(key, (None,))[0]
            if v is True:
                passes += 1
            elif v is False:
                fails += 1
        total = passes + fails
        stats[key] = {
            "passes": passes, "fails": fails, "total": total,
            "rate": round(passes / total * 100) if total else None,
        }
    return stats


def worst_criterion(agg):
    scored = [(k, v["rate"]) for k, v in agg.items()
              if v["rate"] is not None]
    if not scored:
        return "—", None
    k, r = min(scored, key=lambda x: x[1])
    return META[k]["name"], r

# ── 30-day history log ───────────────────────────────────────────────────────

def load_history():
    if HISTORY_PATH.exists():
        try:
            data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  ⚠  Could not load history ({HISTORY_PATH}): {exc} — starting fresh", file=sys.stderr)
    return []


def update_history(history, entry):
    """Upsert today's entry (same-day reruns overwrite), trim to HISTORY_MAX."""
    history = [e for e in history if e.get("date") != entry["date"]]
    history.append(entry)
    history.sort(key=lambda e: e["date"])
    return history[-HISTORY_MAX:]


def save_history(history):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")


# ── HTML helpers ──────────────────────────────────────────────────────────────

def _score_color(s):
    if s is None:
        return "#607d8b"
    if s >= 80:
        return "#4caf50"
    if s >= 60:
        return "#ff9800"
    return "#ef5350"


def _badge(key, val, reason):
    meta   = META[key]
    method = meta["method"]
    name   = meta["name"]
    tip    = _esc(reason)

    if method == "info":
        cls = "cr-info-on" if val else "cr-info-off"
        return f'<span class="cr-badge {cls}" title="{tip}">{name}</span>'
    if val is None:
        return f'<span class="cr-badge cr-pending" title="{tip}">? {name}</span>'
    cls = "cr-pass" if val else "cr-fail"
    mark = "✓" if val else "✗"
    return f'<span class="cr-badge {cls}" title="{tip}">{mark} {name}</span>'


def _esc(s):
    """Minimal HTML-escape for attribute and text contexts."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _headline_card(record, res, sc):
    h      = str(record.get("Headline", "")).strip()
    author_raw = str(record.get("Author", "")).strip()
    author = _esc(author_raw)
    brand  = _esc(record.get("Brand Type", ""))
    date   = _esc(record.get("Publication Date", ""))
    url    = record.get("Published URL/Link", "") or record.get("Draft URL/Link", "")
    color  = _score_color(sc)

    h_esc  = _esc(h)
    hl_html = (f'<a href="{url}" target="_blank" rel="noopener" class="hl-link" onclick="event.stopPropagation()">{h_esc}</a>'
               if url else h_esc)

    # Platform + Vertical badges
    platform     = _parse_platform(record)
    plat_label   = _PLATFORM_LABELS.get(platform, "")
    plat_badge_html = ""
    if plat_label:
        plat_badge_html = (
            f'<span class="vert-badge" style="font-size:.72em;background:#1a2e1a;color:#86efac;'
            f'padding:1px 7px;border-radius:3px;margin-left:6px">{_esc(plat_label)}</span>'
        )

    vertical = AUTHOR_VERTICAL.get(author_raw, "")
    vert_badge_html = ""
    vert_tips_html  = ""
    if vertical:
        vert_badge_html = (
            f'<span class="vert-badge" style="font-size:.72em;background:#1e3a5f;color:#93c5fd;'
            f'padding:1px 7px;border-radius:3px;margin-left:6px">{_esc(vertical)}</span>'
        )
        tips = VERTICAL_TIPS.get(vertical, [])
        if tips:
            tips_li = "".join(f"<li>{_esc(t)}</li>" for t in tips)
            vert_tips_html = (
                f'<div class="vert-tips" style="font-size:.78em;color:#94a3b8;'
                f'margin-top:.5rem;padding:.5rem .75rem;background:#0f172a;'
                f'border-left:2px solid #2563eb;border-radius:0 3px 3px 0">'
                f'<strong style="color:#60a5fa">{_esc(vertical)} tips:</strong>'
                f'<ul style="margin:.25rem 0 0 1rem;padding:0">{tips_li}</ul></div>'
            )

    tiers_html = ""
    for tier, label in TIER_LABELS.items():
        badges = " ".join(
            _badge(k, res.get(k, (None, ""))[0], res.get(k, (None, ""))[1])
            for k, m in META.items() if m["tier"] == tier
        )
        tiers_html += (f'<div class="tier-row">'
                       f'<span class="tier-lbl">{label}</span>'
                       f'<div class="badges">{badges}</div></div>')

    return f"""<div class="hcard" onclick="this.classList.toggle('expanded')">
  <div class="hcard-top">
    <span class="hcard-meta">{author}{vert_badge_html}{plat_badge_html} · {brand} · {date}</span>
    <span style="display:flex;align-items:center">
      <span class="hcard-score" style="color:{color}">{sc}%</span>
      <span class="hcard-toggle">▸</span>
    </span>
  </div>
  <div class="hcard-hl">{hl_html}</div>
  <div class="hcard-criteria">{tiers_html}{vert_tips_html}</div>
</div>"""


def _criterion_table(agg):
    rows = ""
    for tier, label in TIER_LABELS.items():
        header_added = False
        for key, meta in META.items():
            if meta["tier"] != tier or meta["weight"] == 0:
                continue
            s = agg.get(key)
            if not s or s["total"] == 0:
                continue
            if not header_added:
                rows += f'<tr class="tier-hdr"><td colspan="4">{label}</td></tr>'
                header_added = True
            rate = s["rate"]
            color = _score_color(rate)
            bar_w = rate if rate is not None else 0
            rate_str = f"{rate}%" if rate is not None else "—"
            method_badge = (f'<span class="method-badge method-{meta["method"]}">'
                            f'{"LLM" if meta["method"]=="llm" else "rule-based"}</span>')
            rows += f"""<tr>
  <td>{meta["name"]} {method_badge}</td>
  <td><div class="pass-bar"><div class="pass-fill" style="width:{bar_w}%;background:{color}"></div></div></td>
  <td style="color:{color};font-family:monospace;font-weight:600">{rate_str}</td>
  <td class="cnt-cell"><span style="color:#4caf50">{s["passes"]}✓</span> <span style="color:#ef5350">{s["fails"]}✗</span></td>
</tr>"""
    return (f'<table class="agg-tbl"><thead><tr>'
            f'<th>Criterion</th><th>Pass Rate</th><th></th><th>Counts</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>')


def _history_strip(history):
    if not history:
        return ""
    days_html = ""
    for entry in reversed(history):  # most recent first
        avg  = entry.get("avg", 0)
        n    = entry.get("n", 0)
        issue = entry.get("top_issue", "—")
        date  = entry.get("date", "")
        # Short date label: "Apr 6"
        try:
            d = datetime.date.fromisoformat(date)
            label = d.strftime("%-m/%-d")
        except ValueError:
            label = date
        color = _score_color(avg)
        tip = _esc(f"{date}: {n} headlines, avg {avg}%, top issue: {issue}")
        issue_esc = _esc(issue)
        days_html += (
            f'<div class="hist-day" title="{tip}" onclick="this.classList.toggle(\'expanded\')">'
            f'<div class="hist-date">{label}</div>'
            f'<div class="hist-avg" style="color:{color}">{avg}%</div>'
            f'<div class="hist-expand">▸ details</div>'
            f'<div class="hist-details">'
            f'<div class="hist-n">{n} hdls</div>'
            f'<div class="hist-issue">{issue_esc}</div>'
            f'</div>'
            f'</div>'
        )
    return (
        f'<div class="hist-section">'
        f'<h2>30-Day History</h2>'
        f'<p class="hist-hint">Click a tile to expand</p>'
        f'<div class="hist-strip">{days_html}</div>'
        f'</div>'
    )


def _nav():
    pages = [
        ("Current Analysis",   "../"),
        ("Editorial Playbooks","../playbook/"),
        ("Author Playbooks",   "../author-playbooks/"),
        ("Style Guide",        "../style-guide/"),
        ("Experiments",        "../experiments/"),
        ("Headline Grader",    ""),
    ]
    link_parts = []
    for name, href in pages:
        cls = ' class="active"' if name == "Headline Grader" else ""
        link_parts.append(f'<a href="{href}"{cls}>{name}</a>')
    links = " <span class='nav-sep'>·</span> ".join(link_parts)
    return f"""<nav class="site-nav">
  <div class="nav-links">{links}</div>
  <button class="theme-toggle" onclick="toggleTheme()" title="Toggle theme">◐</button>
</nav>"""

# ── Full HTML page ────────────────────────────────────────────────────────────

_CSS = """
  :root{--bg:#0f1117;--surface:#1a1d27;--card:#21253a;--border:#2e3350;
        --text:#e8eaf6;--muted:#8b90a0;--accent:#7c9df7;--red:#ef5350;
        --gold:#ffd54f;--sig:#4caf50;--dir:#ff9800;--none:#607d8b}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:14px;line-height:1.6}
  .container{max-width:1100px;margin:0 auto;padding:32px 24px}
  h1{font-size:1.7em;font-weight:700;color:var(--accent);margin-bottom:4px}
  .subtitle{color:var(--muted);font-size:.9em;margin-bottom:28px}
  h2{font-size:1.05em;font-weight:700;color:var(--accent);margin:32px 0 12px;
     border-bottom:1px solid var(--border);padding-bottom:6px;
     text-transform:uppercase;letter-spacing:.04em}
  .site-nav{background:var(--surface);border-bottom:1px solid var(--border);
             padding:0 24px;display:flex;align-items:center;
             justify-content:space-between;height:44px;position:sticky;top:0;z-index:100}
  .nav-links{display:flex;align-items:center}
  .nav-links a{color:var(--muted);text-decoration:none;font-size:.85em;padding:0 12px;
               height:44px;display:flex;align-items:center;
               border-bottom:2px solid transparent;transition:color .15s}
  .nav-links a:hover{color:var(--text)}
  .nav-links a.active{color:var(--accent);border-bottom-color:var(--accent)}
  .nav-sep{color:var(--border);font-size:.8em}
  .theme-toggle{background:none;border:1px solid var(--border);color:var(--muted);
                cursor:pointer;padding:4px 8px;border-radius:4px;font-size:.8em}
  .chips{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}
  .chip{background:var(--card);border:1px solid var(--border);border-radius:8px;
        padding:10px 18px;min-width:160px}
  .chip-val{font-size:1.45em;font-weight:700;font-family:monospace}
  .chip-lbl{font-size:.72em;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
  .agg-tbl{width:100%;border-collapse:collapse;font-size:.82em;margin-bottom:8px}
  .agg-tbl th{background:var(--surface);color:var(--muted);font-weight:600;
               text-align:left;padding:7px 10px;border-bottom:2px solid var(--border);
               text-transform:uppercase;font-size:.75em;letter-spacing:.05em}
  .agg-tbl td{padding:6px 10px;border-bottom:1px solid var(--border);vertical-align:middle}
  .agg-tbl tr.tier-hdr td{background:var(--surface);color:var(--accent);font-weight:700;
                            font-size:.75em;text-transform:uppercase;letter-spacing:.06em;
                            padding:9px 10px 4px}
  .pass-bar{display:inline-block;width:140px;height:6px;background:var(--border);
             border-radius:3px;vertical-align:middle;margin-right:6px}
  .pass-fill{height:100%;border-radius:3px}
  .cnt-cell{font-family:monospace;font-size:.8em}
  .method-badge{font-size:.65em;padding:1px 5px;border-radius:8px;
                vertical-align:middle;margin-left:4px;font-weight:600}
  .method-obj{background:rgba(76,175,80,.12);color:#4caf50;border:1px solid rgba(76,175,80,.25)}
  .method-llm{background:rgba(124,157,247,.12);color:#7c9df7;border:1px solid rgba(124,157,247,.25)}
  .hcard{background:var(--card);border:1px solid var(--border);border-radius:10px;
         padding:16px 18px;margin-bottom:14px}
  .hcard-top{display:flex;justify-content:space-between;align-items:baseline;
             margin-bottom:5px;cursor:pointer;user-select:none}
  .hcard-meta{font-size:.78em;color:var(--muted)}
  .hcard-score{font-size:1.1em;font-weight:700;font-family:monospace}
  .hcard-toggle{font-size:.65em;color:var(--muted);margin-left:8px;flex-shrink:0;
                align-self:center}
  .hcard-hl{font-size:.95em;font-weight:600;margin-bottom:0;line-height:1.4;
            cursor:pointer;user-select:none}
  .hl-link{color:var(--text);text-decoration:none}
  .hl-link:hover{color:var(--accent);text-decoration:underline}
  .hcard-criteria{display:none;flex-direction:column;gap:5px;
                  margin-top:10px;padding-top:10px;border-top:1px solid var(--border)}
  .hcard.expanded .hcard-criteria{display:flex}
  .hcard.expanded .hcard-toggle{transform:rotate(90deg)}
  .hcard.expanded .hcard-hl{margin-bottom:0}
  .hl-link{pointer-events:auto}
  .tier-row{display:flex;align-items:flex-start;gap:8px;flex-wrap:wrap}
  .tier-lbl{font-size:.68em;color:var(--muted);text-transform:uppercase;
             letter-spacing:.05em;white-space:nowrap;padding-top:3px;min-width:130px}
  .badges{display:flex;flex-wrap:wrap;gap:4px}
  .cr-badge{font-size:.72em;padding:2px 7px;border-radius:10px;
             white-space:nowrap;cursor:default;border:1px solid transparent}
  .cr-pass{background:rgba(76,175,80,.15);color:#4caf50;border-color:rgba(76,175,80,.3)}
  .cr-fail{background:rgba(239,83,80,.15);color:#ef5350;border-color:rgba(239,83,80,.3)}
  .cr-pending{background:rgba(255,152,0,.1);color:#ff9800;border-color:rgba(255,152,0,.25)}
  .cr-info-on{background:rgba(124,157,247,.12);color:#7c9df7;border-color:rgba(124,157,247,.25)}
  .cr-info-off{background:rgba(96,125,139,.08);color:#607d8b;border-color:rgba(96,125,139,.2)}
  .warn{background:rgba(255,152,0,.07);border:1px solid rgba(255,152,0,.25);
        border-radius:6px;padding:8px 14px;font-size:.8em;color:var(--dir);margin-top:10px}
  .footer{margin-top:48px;padding-top:20px;border-top:1px solid var(--border);
          color:var(--muted);font-size:.75em}
  /* 30-day history strip */
  .hist-section{margin:28px 0 8px}
  .hist-section h2{margin-bottom:6px}
  .hist-hint{font-size:.72em;color:var(--muted);margin-bottom:10px}
  .hist-strip{display:flex;gap:6px;flex-wrap:wrap}
  .hist-day{display:flex;flex-direction:column;align-items:center;gap:3px;
            background:var(--surface);border:1px solid var(--border);
            border-radius:8px;padding:8px 10px;min-width:72px;cursor:pointer;
            transition:border-color .15s;user-select:none}
  .hist-day:hover{border-color:var(--accent)}
  .hist-date{font-size:.65em;color:var(--muted);letter-spacing:.02em;white-space:nowrap}
  .hist-avg{font-size:1.05em;font-weight:700}
  .hist-expand{font-size:.58em;color:var(--muted)}
  .hist-details{display:none;flex-direction:column;align-items:center;
                gap:3px;margin-top:4px;padding-top:4px;
                border-top:1px solid var(--border);width:100%}
  .hist-day.expanded .hist-details{display:flex}
  .hist-day.expanded .hist-expand{display:none}
  .hist-n{font-size:.65em;color:var(--accent);font-weight:600}
  .hist-issue{font-size:.62em;color:var(--red);text-align:center;word-break:break-word}
  body.light{--bg:#f4f6fb;--surface:#fff;--card:#fff;--border:#dde1f0;
              --text:#1a1d27;--muted:#5a6070;--accent:#3d5af1}
  @media(max-width:640px){.chips{flex-direction:column}.tier-lbl{min-width:90px}
    .hist-strip{gap:4px}.hist-day{min-width:60px;padding:6px 7px}}
  .run-btn{background:none;border:1px solid var(--border);color:var(--muted);
           cursor:pointer;padding:3px 10px;border-radius:4px;font-size:.8em;
           margin-left:10px;vertical-align:middle;transition:border-color .15s,color .15s}
  .run-btn:hover{border-color:var(--accent);color:var(--accent)}
  .grader-modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);
                z-index:1000;align-items:center;justify-content:center}
  .grader-modal.open{display:flex}
  .grader-box{background:var(--surface);border:1px solid var(--border);border-radius:10px;
              padding:28px 32px;min-width:320px;max-width:420px;width:100%}
  .grader-box h3{font-size:1em;font-weight:700;color:var(--accent);margin-bottom:6px}
  .grader-box p{font-size:.85em;color:var(--muted);margin-bottom:16px;line-height:1.5}
  .pat-group{display:flex;flex-direction:column;gap:6px;margin-bottom:16px}
  .pat-group label{font-size:.8em;color:var(--muted)}
  .pat-group input{background:var(--card);border:1px solid var(--border);color:var(--text);
                   border-radius:4px;padding:7px 10px;font-size:.85em;width:100%}
  .pat-group input:focus{outline:none;border-color:var(--accent)}
  .modal-actions{display:flex;gap:10px;justify-content:flex-end}
  .modal-actions button{padding:7px 18px;border-radius:5px;font-size:.85em;cursor:pointer;border:none}
  .btn-cancel{background:var(--card);color:var(--muted)}
  .btn-cancel:hover{color:var(--text)}
  .btn-run{background:var(--accent);color:#0f1117;font-weight:700}
  .btn-run:hover{opacity:.85}
  .run-status{font-size:.82em;margin-top:10px;min-height:18px;color:var(--sig)}
"""

_JS = """
function toggleTheme(){
  document.body.classList.toggle('light');
  localStorage.setItem('theme', document.body.classList.contains('light') ? 'light' : 'dark');
}
window.addEventListener('DOMContentLoaded', () => {
  if (localStorage.getItem('theme') === 'light') document.body.classList.add('light');
});

function openRunModal(){
  const modal = document.getElementById('run-modal');
  const inp = document.getElementById('run-passcode');
  inp.value = '';
  document.getElementById('run-status').textContent = '';
  modal.classList.add('open');
  setTimeout(() => inp.focus(), 50);
}
function closeRunModal(){
  document.getElementById('run-modal').classList.remove('open');
}
async function submitRun(){
  const code = document.getElementById('run-passcode').value.trim();
  const status = document.getElementById('run-status');
  if (code !== '8812') { status.style.color='var(--red)'; status.textContent='Wrong passcode.'; return; }

  let pat = localStorage.getItem('grader_pat') || '';
  if (!pat) {
    pat = prompt('Enter your GitHub PAT (saved locally for future use):');
    if (!pat) return;
    localStorage.setItem('grader_pat', pat);
  }

  status.style.color='var(--muted)'; status.textContent='Triggering…';
  try {
    const r = await fetch(
      'https://api.github.com/repos/piercewilliams/data-headlines/actions/workflows/grader.yml/dispatches',
      { method:'POST',
        headers:{'Authorization':'Bearer '+pat,'Accept':'application/vnd.github+json','Content-Type':'application/json'},
        body: JSON.stringify({ref:'main'}) }
    );
    if (r.status === 204) {
      status.style.color='var(--sig)';
      status.textContent='Triggered! Results will appear in ~2 min after the Action completes.';
    } else if (r.status === 401) {
      localStorage.removeItem('grader_pat');
      status.style.color='var(--red)';
      status.textContent='PAT rejected (401). Cleared — try again.';
    } else {
      status.style.color='var(--red)';
      status.textContent='Error '+r.status+'. Check PAT permissions (actions: write).';
    }
  } catch(e) {
    status.style.color='var(--red)'; status.textContent='Network error: '+e.message;
  }
}
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeRunModal();
  if (e.key === 'Enter' && document.getElementById('run-modal').classList.contains('open')) submitRun();
});
"""


def build_html(graded, lookback_days, run_ts, history=None):
    n      = len(graded)
    avg_sc = round(sum(sc for _, _, sc in graded) / n) if n else 0
    agg    = aggregate(graded)
    worst_name, worst_rate = worst_criterion(agg)
    worst_str = f"{worst_rate}%" if worst_rate is not None else "—"

    today  = datetime.date.today()
    start  = (today - datetime.timedelta(days=lookback_days)).strftime("%-m/%-d/%Y")
    end    = today.strftime("%-m/%-d/%Y")

    sorted_graded = sorted(graded, key=lambda x: x[2])  # worst first
    cards = "\n".join(_headline_card(r, res, sc) for r, res, sc in sorted_graded)
    hist_html = _history_strip(history or [])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Headline Grader — {end}</title>
<style>{_CSS}</style>
<script>{_JS}</script>
</head>
<body>
{_nav()}
<div class="container">

<h1>Headline Grader</h1>
<div class="subtitle">
  Sara Vallone's Tracker &nbsp;·&nbsp; {start}–{end} &nbsp;·&nbsp;
  {n} headlines graded &nbsp;·&nbsp; Run {run_ts}
  <button class="run-btn" onclick="openRunModal()">Run now</button>
</div>

<div class="chips">
  <div class="chip">
    <div class="chip-val" style="color:var(--accent)">{n}</div>
    <div class="chip-lbl">Headlines graded</div>
  </div>
  <div class="chip">
    <div class="chip-val" style="color:{_score_color(avg_sc)}">{avg_sc}%</div>
    <div class="chip-lbl">Average score</div>
  </div>
  <div class="chip">
    <div class="chip-val" style="color:var(--red)">{worst_str}</div>
    <div class="chip-lbl">Top issue: {worst_name}</div>
  </div>
</div>

{hist_html}

<h2>Pass Rates by Criterion</h2>
{_criterion_table(agg)}
<div class="warn">
  LLM criteria (active voice, lead burial, curiosity gap, accuracy) use
  Groq {GROQ_MODEL}. 'What to Know' avoidance is rule-based (regex, not LLM).
  Keyword criterion checks Primary Keywords from the Tracker against the headline.
  Character count scoring uses the platform-specific target range when Syndication
  Platform is set in the Tracker (Apple News: 90–120 chars; SmartNews: 70–90 chars;
  unknown: passes if valid for either). Number lead note is also platform-aware.
  Hover any badge for details.
</div>

<h2>Recent Headlines — worst scores first</h2>
{cards}

<div class="footer">
  Run: {run_ts} &nbsp;·&nbsp; Lookback: {lookback_days}d &nbsp;·&nbsp;
  Source: Sara Vallone's Tracker (live Google Sheets) &nbsp;·&nbsp;
  LLM: Groq {GROQ_MODEL} &nbsp;·&nbsp; Objective: rule-based Python
</div>

</div>

<div id="run-modal" class="grader-modal" onclick="if(event.target===this)closeRunModal()">
  <div class="grader-box">
    <h3>Run Headline Grader</h3>
    <p>This triggers a fresh grader run via GitHub Actions. Results will appear on this page in about 2 minutes.</p>
    <div class="pat-group">
      <label for="run-passcode">Passcode</label>
      <input id="run-passcode" type="password" placeholder="••••" autocomplete="off">
    </div>
    <div class="modal-actions">
      <button class="btn-cancel" onclick="closeRunModal()">Cancel</button>
      <button class="btn-run" onclick="submitRun()">Run</button>
    </div>
    <div id="run-status" class="run-status"></div>
  </div>
</div>

</body>
</html>"""

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lookback", type=int, default=DEFAULT_LOOKBACK)
    ap.add_argument("--skip-llm", action="store_true")
    ap.add_argument("--dry-run",  action="store_true")
    args = ap.parse_args()

    # Groq client
    groq_client = None
    if not args.skip_llm:
        groq_key = os.getenv("GROQ_API_KEY", "")
        if groq_key:
            from groq import Groq
            groq_client = Groq(api_key=groq_key)
            print(f"LLM eval: Groq {GROQ_MODEL}")
        else:
            print("GROQ_API_KEY not set — LLM criteria will show as pending", file=sys.stderr)
    else:
        print("LLM eval: skipped (--skip-llm)")

    print("Fetching Tracker…")
    records = fetch_records()
    recent  = filter_recent(records, args.lookback)
    print(f"  {len(records)} total rows → {len(recent)} in last {args.lookback}d")

    if not recent:
        print(f"No headlines in last {args.lookback} days. Try --lookback 7.")
        sys.exit(0)

    print("Grading…")
    graded = []
    for i, r in enumerate(recent, 1):
        h = str(r.get("Headline", "")).strip()
        print(f"  [{i}/{len(recent)}] {h[:70]}")
        res = grade(r, groq_client)
        sc  = score(res)
        graded.append((r, res, sc))
        if groq_client and i < len(recent):
            time.sleep(0.4)   # respect Groq free-tier rate limit

    run_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    scores  = [sc for _, _, sc in graded]
    avg_sc  = round(sum(scores) / len(scores)) if scores else 0
    agg     = aggregate(graded)
    worst_name, _ = worst_criterion(agg)

    # Build today's history entry
    today_entry = {
        "date":      datetime.date.today().isoformat(),
        "n":         len(graded),
        "avg":       avg_sc,
        "top_issue": worst_name,
    }

    history = load_history()
    history = update_history(history, today_entry)

    html = build_html(graded, args.lookback, run_ts, history=history)

    if args.dry_run:
        print(f"\nDry run — would write {len(html):,} chars to {OUTPUT_PATH}")
        print(f"Scores: min={min(scores)} avg={avg_sc} max={max(scores)}")
        print(f"History entry: {today_entry}")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    save_history(history)
    print(f"\n✓ Written to {OUTPUT_PATH}")
    print(f"  Scores: min={min(scores)}  avg={avg_sc}  max={max(scores)}")
    print(f"  History: {len(history)} days logged")


if __name__ == "__main__":
    main()
