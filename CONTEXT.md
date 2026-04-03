# T1 Headline Analysis — Working Context

**Phase:** Phase 2 active — 13 findings live, playbook (5 tiles), author-playbooks, experiments, full ingest pipeline
**Status:** Active — monthly Tarrow cadence + weekly ANP drops
**Last session:** 2026-04-02 (March data ingested; 5 new findings added; exhaustive cross-platform analysis complete)
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

**Analysis:**
- [ ] Add Mann-Whitney significance tests to sports/biz/pol subtopic tables (3 standing rigor warnings per build)
- [ ] O&O + syndication PV data layer (Chris Palo request; Amplitude access needed)

**Stakeholder shares:**
- [x] ~~Share site with Sarah Price~~ — done. Sarah confirmed she has the link and is reviewing (Slack 2026-04-01 11:59 AM).
- [ ] Share formula × topic interaction finding → editorial leads (actionable: use "here's/question" specifically for weather/emergency)
- [ ] Share SmartNews formula trap (question/WTK hurt SN) → distribution team

## Session Log

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
