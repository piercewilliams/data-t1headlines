# T1 Headline Analysis — Working Context

**Phase:** Phase 2 complete — analysis, site, experiment framework, and tooling all live
**Status:** Active — new data in hand; pipeline changes needed per stakeholder feedback
**Last session:** 2026-03-27 (four sessions)

For stable reference facts: see [REFERENCE.md](REFERENCE.md)
For session history: see [sessions/](sessions/)

---

## Current State

- **Site:** `docs/index.html` — Phase 2 live; Phase 1 preserved at `docs/v1/`
- **Generator:** `generate_site.py` — run to regenerate site from raw Excel; reads two files:
  - `Top syndication content 2025.xlsx` — 2025 data (Apple News, SmartNews, MSN Dec-only, Yahoo)
  - `Top Stories 2026 Syndication.xlsx` — 2026 data (currently only Notifications used by pipeline)
- **Skills installed:** `polars`, `interactive-report-generator`, `code-data-analysis-scaffolds`

## Data Status (as of 2026-03-27)

| Source | Status | Notes |
|--------|--------|-------|
| Apple News 2025 | ✅ In repo | Full year, all columns |
| Apple News 2026 | ✅ New file in Downloads | Engagement columns now populated (1,136 rows) |
| Apple News Notifications 2026 | ✅ In repo | Jan–Feb 2026, 360 rows |
| SmartNews 2025 | ✅ In repo | Full year, 32 category columns |
| SmartNews 2026 | ✅ New file in Downloads | 3,633 rows; 7 cols only (no category breakdown); has URL + title |
| MSN 2025 full year | ⚠️ Needs re-export | Tarrow updated Google Sheet; current repo file = Dec only |
| MSN 2026 | ✅ New file in Downloads | Jan–Feb only, 355 rows |
| MSN video 2026 | ✅ New (404 rows) | Not previously in pipeline |
| Yahoo 2025 | ✅ In repo | Full year |
| Yahoo 2026 | ✅ New file in Downloads | 2,116 rows |
| Yahoo video 2026 | ✅ New (129 rows) | Not previously in pipeline |
| Apple News Notifications 2025 | ❓ May not exist | Tarrow: "I just gave you all data points available" |
| SmartNews 2026 category breakdown | ❌ Unavailable | Only 7 cols in 2026 export |

**Action needed:** Re-export 2025 sheet from Tarrow's Google Sheet (URL unknown — ask Tarrow/Sarah). Move `Top Stories 2026 Syndication.xlsx` from Downloads to repo root.

## Hard Directives (from Chris, 2026-03-27)

1. **Normalize all data before every analysis run** — mandatory preprocessing step, not optional. Bake into `generate_site.py` as a `normalize()` function called before any analysis.
2. **"Different platforms are different" is not a finding** — obvious table stakes. The bar is: *what specifically works, and why* — especially when non-obvious. Reframe or cut Q3/Topics cross-platform isolation section.

## Stakeholder Feedback (2026-03-27)

**Chris Palo** (saw the report):
- Wants O&O + syndication PV data layered together (Amplitude now in Claude)
- Number leads: subject-first instinct in journalism — round numbers feel fake; type of number matters. "There's a there, there." → deepen this finding.
- Channel-specific category guidance for Sara is the next editorial action item.
- Caution: longitudinal view essential — platforms shift week to week; bias toward newer data.

**Sarah Price** — standing research questions (the recurring core):
- ✅ Headline formats × platform
- ✅ Content categories × platform
- 🔲 Sub-category drill-down (e.g., sports → which sport specifically)
- 🔲 Top vs. bottom headline comparison within a category + specific improvement guidance (expand crime/business high-variance finding)
- 🔲 Timeline view — when do changes happen (aligns with Chris Palo)
- 🔲 Team performance — their writers' top performers (tracker join, see below)
- Character count: no data in Tarrow's sheet; ≤80 char finding is notification-specific, not general

## Tracker Join (new capability)

Content tracker at `~/Downloads/Tracker Template.xlsx` — `Data` sheet (1,997 rows) has:
- `Published URL/Link` — join key to Apple News (`Publisher Article ID`) and SmartNews (`url`)
- `Author`, `Vertical`, `Syndication platform`, `Publication Date`
- `Word Count` — available for joined articles; proxy for Sarah's character count question
- `APPLE REWRITE CALENDAR` sheet — articles selected for rewrites with original view counts + rewrite scores; directly relevant to variant allocation model

MSN and Yahoo lack URL columns; title-matching fallback needed.

## What's Next — Prioritized

**Pipeline changes (this session):**
1. [ ] Add mandatory `normalize()` preprocessing to `generate_site.py`
2. [ ] Expand pipeline to use Apple News 2026 engagement columns (currently unused)
3. [ ] Add SmartNews 2026 to pipeline (URL + title enables headline analysis)
4. [ ] Add MSN video + Yahoo video sheets (new data types)
5. [ ] Reframe Q3/Topics — remove "platforms are different" as a finding; replace with what specifically works and why
6. [ ] Deepen number leads analysis (Chris Palo request)
7. [ ] Add sub-category drill-down (Sarah request)
8. [ ] Add top vs. bottom headline comparison within category (Sarah request)
9. [ ] Add longitudinal/timeline view (both stakeholders)
10. [ ] Add team performance view via tracker join (Sarah request)

**Data:**
11. [ ] Get 2025 sheet URL and re-export (for full-year MSN)
12. [ ] Move new 2026 file from Downloads to repo root

**Stakeholder shares (still pending):**
13. [ ] Share Phase 2 site with Sarah Price
14. [ ] SmartNews Entertainment over-index → distribution team
15. [ ] "What to know" Featured rate → editorial leads

## Session: 2026-03-27c (Academic rigor audit)

Full statistical rigor pass: BH-FDR multiple comparison correction, rank-biserial effect sizes, bootstrap 95% CIs on lift ratios, power analysis for underpowered formulas, "Exclusive" sensitivity analysis (Guthrie cluster), untagged baseline characterization, multi-category independence warning. New helpers: `bh_correct()`, `rank_biserial()`, `bootstrap_ci_lift()`, `required_n_80pct()`.

## Session: 2026-03-27b (UX redesign)

Full CSS overhaul: off-white background, glass-blur nav, diagonal gradient hero, frosted stat card, shadow-bordered charts, card-style tables with hover rows. Hero h1 rewritten for executive audience.

## Session: 2026-03-27a (Infrastructure)

Accordion UI (`<details>`/`<summary>`), monthly archive pipeline (`ingest.py`), experiment framework (`generate_experiment.py`), hardcoding audit. Two active experiments live (WTN Featured rate, possessive formula views); one pending (notification CTR H2 2026).

---

*This file follows the Tiered Context Architecture. Budget: ≤150 lines.*
*Current count: ~140 lines*
