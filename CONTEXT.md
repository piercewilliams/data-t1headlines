# T1 Headline Analysis — Working Context

**Phase:** Phase 2 active — 13 findings live, playbook (5 tiles), author-playbooks, experiments, full ingest pipeline
**Status:** Active — monthly Tarrow cadence + weekly ANP drops
**Last session:** 2026-04-02 (March data ingested; 5 new findings added; exhaustive cross-platform analysis complete)

For stable reference facts: see [REFERENCE.md](REFERENCE.md)
For session history: see [sessions/](sessions/)

---

## Current State

- **Site:** `docs/index.html` — 13 findings, interactive tiles, dark/light mode, sortable tables, PNG/PDF export
- **Playbook:** `docs/playbook/index.html` — 5 tiles (Featured Targeting, Push Notifications, Section Tagging, Local vs. National, MSN Formula)
- **Author Playbooks:** `docs/author-playbooks/index.html` — per-author profiles (requires Tracker)
- **Generator:** `generate_site.py` — run via `ingest.py`; `_build_nav()` / `_NAV_PAGES` single source of truth; `EXCLUDE_MSN = False`
- **Data in use:**
  - `Top syndication content 2025.xlsx` — 2025 baseline (Apple News, Notifications, SmartNews, MSN, Yahoo)
  - `Top Stories 2026 Syndication.xlsx` — 2026 Jan–Feb (Apple News, Notifications, SmartNews, Yahoo, MSN) — **NOTE: repo root file is Feb build; April 2 Tarrow drop (Mar data) was processed via ingest.py but file not retained in repo**
  - `Tracker Template.xlsx` — optional; author/team analysis
  - `anp_data/` — Apple News Publisher CSVs (weekly drops; gitignored). Jan–Feb 2026 loaded. `--anp-data <dir>` to override.

## Data Status (as of 2026-04-01)

| Source | Status | Notes |
|--------|--------|-------|
| Apple News 2025 | ✅ In repo | Full year |
| Apple News 2026 | ✅ In repo | Engagement columns populated |
| Apple News Notifications 2025 | ✅ In repo | 1,443 rows; news brands from June, Us Weekly all year |
| Apple News Notifications 2026 | ✅ In repo | 359 rows, Jan–Feb |
| SmartNews 2025 | ✅ In repo | Full year, 32 category columns |
| SmartNews 2026 | ✅ In repo | 30 cols; 11 common categories in Q4 combined analysis |
| MSN 2025 | ✅ In repo | Full year, 4,201 rows |
| MSN 2026 | ✅ In repo | Jan–Feb, 355 rows |
| Yahoo 2025 | ✅ In repo | Full year |
| Yahoo 2026 | ✅ In repo | 2,116 rows |
| MSN video 2026 | ✅ Known | 404 rows; not yet wired |
| Yahoo video 2026 | ✅ Known | 129 rows; not yet wired |
| Apple News Publisher (ANP) | ✅ In anp_data/ | Jan–Feb 2026; 8 publications; 420K rows / 80K articles; weekly cadence |

## Open Items

**Data:**
- [ ] ANP March drop — Tarrow said he'd add it to the Drive folder (2026-04-01); drop into `anp_data/` when it arrives
- [ ] Yahoo/AOL split — confirm with Tarrow whether AOL tab will appear in future exports
- [ ] SmartNews article-level 2026 data — current export is monthly-aggregated by domain; ask Tarrow if per-article export is available
- [ ] Retain April 2 Tarrow file in repo or update DATA_2026 path — current repo file is Feb build (old MSN sheet format)

**Analysis:**
- [ ] Add Mann-Whitney significance tests to sports/biz/pol subtopic tables (3 standing rigor warnings per build)
- [ ] O&O + syndication PV data layer (Chris Palo request; Amplitude access needed)

**Stakeholder shares:**
- [x] ~~Share site with Sarah Price~~ — done. Sarah confirmed she has the link and is reviewing (Slack 2026-04-01 11:59 AM).
- [ ] Share formula × topic interaction finding → editorial leads (actionable: use "here's/question" specifically for weather/emergency)
- [ ] Share SmartNews formula trap (question/WTK hurt SN) → distribution team

## Session Log

**2026-04-02: March ingest + exhaustive analysis (5 new findings)**

March Tarrow data ingested (Apple News +434 rows → 1,569 YTD; Notifications +144 → 503; MSN restructured 355→845 rows with clean sheet; SmartNews now monthly-aggregated; Yahoo/AOL split). Fixed SmartNews column rename (`date`→`month`). Re-enabled MSN (`EXCLUDE_MSN=False`).

Exhaustive analysis run across all platforms (~20 hypothesis classes). Five additions to the site:

1. **MSN Formula Divergence** — direct declarative headlines 4.84× better than any structured formula on T1 news MSN (p=2.9e-13). Questions/here's/explainers all significantly below baseline.
2. **Formula × Topic Interaction** — "here's" and question format lift Apple News featuring ONLY on weather content (heres×weather 70.6%, question×weather 56.7%). For all other topics, formula barely predicts featuring. Topic is the primary driver.
3. **SmartNews Cross-Platform Formula Trap** — question (0.423 rank, p=3.4e-6) and "what to know" (0.371, p=3.0e-6) actively hurt SmartNews performance. "Here's" is the only formula above baseline on both Apple News AND SmartNews.
4. **Notification outcome language** — crime/death outcome words (1.26× CTR, p_adj=0.0015) now strongest notification signal, stronger than attribution (1.18×, p_adj=0.020) after BH-FDR correction across 10 signals.
5. **Notification send-time** — evening (6-8pm) outperforms morning (9-11am), KW p=4.2e-5.

Also extended Finding 5 (sports universal underperformance across Apple/MSN/notifications) and Finding 4 (notification CTR declining 29% over 9 months, Jun 2025→Mar 2026).

Key analytical notes:
- Apple News 2026 "featured view lift" appears reversed (featured < non-featured median views) due to composition: Us Weekly celebrity articles dominate the non-featured high-view pool. Within-topic, featuring still helps (weather: 2.92× lift).
- "What to know" 0% featuring in 2026 (vs 54% in 2025) — formula is applied to celebrity profiles in 2026 vs weather/emergency in 2025. Formula isn't the driver; content type is.
- ANP March data not yet arrived. SmartNews 2026 is monthly-aggregated (can't do article-level analysis).

**2026-04-01: Finding 8 — ANP bottom-performer analysis (Sarah Price request)**

Sarah Price asked: "what are the worst performers and what could be the causes?" Ran bottom-quintile analysis on 10,929 ANP news articles.

Three structural failure patterns identified, all BH-FDR or Mann-Whitney significant:
- **Missing section tag (Main only):** 47.5% land in bottom 20%, median rank 0.22 (p=9.9e-36, n=318). Apple News routes by section; no tag = no routing = no featuring. Operational fix: ensure every article has a section before publish.
- **Local Sports without featuring:** 27.2% of sports articles bottom out, median rank 0.37 (p=5.4e-102). Featured sports performs extremely well (37 articles, median rank 0.91) but Apple features sports at 1.4%. Use SmartNews for local sports instead.
- **National wire (Nation & World):** 35.5% bottom, median rank 0.33 vs. 0.59 for local sections (p=5.3e-19). Local outlets lose to national brands on national content.

Finding 8 tile + detail panel added to main page. Two new High-confidence playbook tiles: "Section Tagging" and "Local vs. National Content." Playbook now at 4 tiles.

**2026-04-01: ANP data integration + rigor verification**

Sarah Price surfaced need for full Apple News universe data (not just top headlines) to compare what went wrong vs. right. Chris Tarrow set up weekly automated exports from Apple News Publisher; first drop (Jan–Feb 2026, 8 publications) arrived same day.

**Exploratory analysis (8 angles):** profiled 420K daily rows → 80K unique articles → 10,929 2026-published news-pub articles. Ran featured vs. non-featured headline signals (BH-FDR), section × featuring rates, top-decile views signals, notification traffic amplification, subscriber ratio by section, Us Weekly signals, cross-pub topic performance, and active time vs. views.

**Two findings wired into main page (6 & 7):**
- **Finding 6 — Featuring Reaches Non-Subscribers:** Featured articles: 47% non-subscriber audience; non-featured: 3%, even among top-quartile performers (5%). Featuring is audience acquisition, not a traffic boost. p = 6.6e-277. Mechanism is behavioral (non-subscribers can technically access non-featured articles — 67% have at least one non-sub view — but almost never do without a featured placement to surface them).
- **Finding 7 — Topic Predicts Featuring More Than Formula:** Weather featured at 41%, Sports 1.4% (28× gap), Shopping/Opinion 0%. Business: situation/event stories 2× more featured than individual-person stories (χ²=5.47, p=0.019, labeled directional — not BH-FDR corrected). Question format: 2× featuring lift (χ²=28.6, p=8.78e-08).

**Rigor verification pass (same session):** Confirmed subscriber ratio data quality (no nulls, 100% coverage), verified behavioral vs. structural mechanism, ran Business named-person chi-squared (missing from initial build), verified question format significance, confirmed double-counting across daily rows doesn't distort the ratio (sub+nonsub/total_unique ≈ 1.0 at article level). Detail panels updated with mechanism note and directional caveat.

**Infrastructure:**
- `anp_data/` directory created (gitignored); drop new weekly CSVs there — pipeline accumulates all
- `_load_anp()` + `_anp_analysis()` in `generate_site.py`; `--anp-data` CLI arg added
- `.gitignore` created (was missing from repo)
- 5 new `_COL_TOOLTIPS` entries added (all audits pass, no new warnings)

**Not wired in (below findings bar):** Us Weekly — 100% named-person rate makes formula comparison impossible; section is the only signal (Style & Beauty > Entertainment) but not actionable for the news team. Notification traffic — selection vs. amplification ambiguous from cumulative data; only 2/1,726 notif articles had majority traffic from notifications.

**2026-03-31: Findings cull — 10 → 5, renumbered**
Removed F1 (Apple News Formulas — null result), F1b (Number Leads), F3 (SmartNews categories), F6 (Variance by topic), F9 (Team Performance), F10 (MSN). Kept and renumbered 1–5: Featured Targeting, Push Notifications, Platform Topic Inversion, Views vs. Engagement, Formula Trends. Playbook dropped from 6 to 2 tiles. HTML surgery only — Python analysis retained. Also: ad-hoc `national_team_deep_dive.xlsx` exploration (not wired in).

**2026-03-30: MSN wiring, Tarrow data drop, Finding 4 rewrite, snapshot bar**
Full-year MSN 2025 wired (later culled from site). Tarrow added Notifications 2025 + SmartNews 2026 category columns. Finding 4 (Notifications) rewritten after pooling artifact discovered — Us Weekly and news brands are separate populations (2.8× CTR gap, non-overlapping signals). Snapshot version bar added to all pages.

**2026-03-27–28: Infrastructure, pipeline, rigor, UX**
`ingest.py` entry point, BH-FDR, bootstrap CIs, hero scoring, playbook, archive, `CLAUDE.md` autonomous workflow, README, `_COL_TOOLTIPS`, `_build_nav()` / `_make_export_js()` DRY refactors, type hints.

---

*This file follows the Tiered Context Architecture. Budget: ≤150 lines.*
*Current count: ~145 lines*
