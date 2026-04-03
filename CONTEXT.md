# T1 Headline Analysis — Working Context

**Phase:** Phase 2 active — 13 findings live, playbook (5 tiles), author-playbooks, experiments, full ingest pipeline
**Status:** Active — monthly Tarrow cadence + weekly ANP drops
**Last session:** 2026-04-03 (Pierce/Sarah alignment call; SEMrush access confirmed; formatting guide incoming; tile feedback requested)
**Session 2026-04-02b:** Bug fix — MSN · Formula Divergence tile populated; prose updated to reflect actual data

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

## Data Status (as of 2026-04-02)

| Source | Status | Notes |
|--------|--------|-------|
| Apple News 2025 | ✅ In repo | Full year, 3,039 rows |
| Apple News 2026 | ✅ In repo | Jan–Mar 2026, 1,569 rows (engagement columns populated) |
| Apple News Notifications 2025 | ✅ In repo | 1,443 rows; news brands from June, Us Weekly all year |
| Apple News Notifications 2026 | ✅ In repo | 503 rows, Jan–Mar |
| SmartNews 2025 | ✅ In repo | Full year, 38,251 rows |
| SmartNews 2026 | ✅ In repo | 514 rows; **monthly-aggregated by domain** (not article-level) |
| MSN 2026 | ✅ In repo | Jan–Mar, 354 rows raw (was 845 — CONTEXT.md was stale); 113 rows after T1 brand + politics filter |
| MSN video 2026 | ✅ In repo | 1,023 rows; wired into pipeline |
| Yahoo 2026 | ✅ In repo | 1,043 rows (Yahoo-only after AOL split) |
| Yahoo video 2026 | ✅ In repo | 163 rows; not yet wired |
| Apple News Publisher (ANP) | ✅ In anp_data/ | Jan–Feb 2026; 5 news pubs; 420K rows / 12,223 unique articles |

## Open Items

**Data:**
- [ ] ANP March drop — Tarrow said he'd add it to the Drive folder (2026-04-01); drop into `anp_data/` when it arrives
- [ ] Yahoo/AOL split — confirm with Tarrow whether AOL tab will appear in future exports
- [ ] SmartNews article-level 2026 data — current export is monthly-aggregated by domain; ask Tarrow if per-article export is available
- [ ] Retain April 2 Tarrow file in repo or update DATA_2026 path — current repo file is Feb build (old MSN sheet format)
- [ ] Tarot data holes — Sarah Price offered to co-approach Chris Tarot with Pierce; March is first solid data set; Jan/Feb had incomplete polls

**Analysis:**
- [ ] Add Mann-Whitney significance tests to sports/biz/pol subtopic tables (3 standing rigor warnings per build)
- [ ] O&O + syndication PV data layer (Chris Palo request; Amplitude access needed)
- [ ] Analyze Sara Voluone's SmartNews/Apple News formatting guide against existing findings — identify correlations + experimentation candidates (waiting on Sarah Price to send the doc)

**Stakeholder shares:**
- [x] ~~Share site with Sarah Price~~ — done. Sarah confirmed she has the link and is reviewing (Slack 2026-04-01 11:59 AM).
- [ ] Share formula × topic interaction finding → editorial leads (actionable: use "here's/question" specifically for weather/emergency)
- [ ] Share SmartNews formula trap (question/WTK hurt SN) → distribution team

**SEMrush:**
- [ ] Sarah Price to forward SEMrush API key + 250K credits to Pierce
- [ ] 3-way meeting (Pierce, Sarah Price, Sarah Voluone) next week (~2026-04-07–11) to align on what trends/signals to track and how to present them
- [ ] Build SEMrush layer on top of API — point-and-click signal tracking for Sarah without requiring her to touch the API directly

**PRD / Product:**
- [ ] Update PRD with backlinking use case rationale: borrow "flare or credibility" from well-performing evergreen pieces (clarified by Sarah Price 2026-04-03)
- [ ] Evergreen backlinking experiment: track ~25 URLs; measure improvement after adding backlinks to high-performing evergreen article (~800 views/day)
- [ ] Experiments tab: wire directional findings → suggested experiment stubs (per Sarah Price's vision: "analyze data → come back and say test this")
- [ ] PRD currently slim on Sarah Price's and Sara Voluone's processes — add their workflow detail

**Snowflake / Sigma:**
- [ ] Sarah to reach out to Dearra/Dedra (2026-04-06) to schedule meeting with Chad re: Snowflake navigation
- [ ] Pierce added to Snowflake but doesn't know where to start — need Chad session

**Sarah Price ask (ongoing):**
- [ ] Sarah to review site tiles (1–13), flag which are useful/not and which parts within useful tiles matter — no rush, feeds report tuning over time

## Session Log

**2026-04-03: Pierce/Sarah alignment call (~25 min)**

Key outcomes: (1) Sarah confirmed her primary use case is actionable headline formulas for editorial teams — team has paused syndication format variation, so headline-only is the right focus. (2) Sarah Voluone putting together a SmartNews/Apple News formatting guide; Sarah Price will send to Pierce for analysis against existing findings. (3) Sarah offered to co-approach Chris Tarot about data holes; March confirmed as first solid dataset. (4) SEMrush API key + 250K credits confirmed — Sarah Price will share; 3-way meeting planned next week with Sarah Voluone. (5) Evergreen backlinking strategy clarified: flag articles to link back to proven evergreen piece (~800 views/day), track ~25 URLs. (6) PRD backlinking rationale gap filled: borrow "flare or credibility" from well-performing pieces. (7) Cluster tags: 15 of 18 product tickets now in code review. (8) Sarah's ask: review tiles and give feedback on usefulness at her convenience. (9) CSA testing module (separate from CSA, feeds back in) confirmed as longer-term goal per Chris + Sarah + Sara Voluone discussion.

**2026-04-02b: MSN · Formula Divergence bug fix**

Three bugs in the MSN formula analysis, all causing the detail table to render empty: (1) `classify_formula()` returns `"untagged"` but baseline lookup used `"other"` — baseline was always empty; (2) `VIEWS_METRIC` (`percentile_within_cohort`, range 0–1) was used instead of raw `"Pageviews"` — median showed as "—"; (3) four hardcoded `_msn_fr()` row lookups targeted formula keys (`what_to_know`, `heres_formula`, etc.) that don't exist in the current MSN data.

Fixes: baseline changed to `"untagged"`; T1 brand filter applied (`_MSN_T1_EXCLUDE` excludes US Weekly, Woman's World, Soap Opera Digest); switched to raw `"Pageviews"` for MSN formula analysis; replaced four hardcoded rows with dynamic `_msn_formula_table()`. MSN raw sheet has 354 rows (US Weekly dominant at 160); after T1 filter + politics = 113 rows. Only `quoted_lede` (n=18) has enough data to test — 0.60×, p=0.037. `MSN_DIVERGE_LIFT_STR` now computed dynamically (was hardcoded "4.84×"). All prose (tile, callout, playbook) updated to reflect actual data: 1.67× lift of direct declarative over quoted lede.

**2026-04-02: March ingest + exhaustive analysis — see `sessions/2026-04.md`**

March Tarrow data ingested. Re-enabled MSN. Exhaustive analysis (~20 hypothesis classes) across all platforms. Five findings added (8 → 13 total): MSN Formula Divergence, Formula × Topic Interaction, SmartNews Cross-Platform Formula Trap, Notification Outcome Language, Notification Send-Time. Extended Finding 4 (CTR trend) and Finding 5 (sports cross-platform).

**2026-04-01: ANP data integration + Findings 6–8 — see `sessions/2026-04.md`**

**Earlier sessions — see `sessions/2026-03.md`**

---

*This file follows the Tiered Context Architecture. Budget: ≤150 lines.*
*Current count: ~145 lines*
