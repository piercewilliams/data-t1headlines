# T1 Headline Analysis — Working Context

**Phase:** Phase 2 complete — all 9 findings live, playbook, author-playbooks, experiments, full ingest pipeline
**Status:** Active — monthly cadence; pipeline ready for next Tarrow drop
**Last session:** 2026-03-30 (Tarrow data drop — notifications 2025, SmartNews 2026 categories, Finding 4 brand-type rewrite)

For stable reference facts: see [REFERENCE.md](REFERENCE.md)
For session history: see [sessions/](sessions/)

---

## Current State

- **Site:** `docs/index.html` — 9 findings, interactive tiles, dark/light mode, sortable tables, PNG/PDF export
- **Playbook:** `docs/playbook/index.html` — 5 tiles sorted by confidence level, PNG/PDF export
- **Author Playbooks:** `docs/author-playbooks/index.html` — per-author profiles (requires Tracker), PNG/PDF export
- **Generator:** `generate_site.py` — fully typed, documented, DRY; run via `ingest.py`
  - Nav: `_build_nav()` / `_NAV_PAGES` — single source of truth, all 3 pages
  - Export JS: `_make_export_js()` — parameterized, all 3 pages
- **Data in use:**
  - `Top syndication content 2025.xlsx` — 2025 baseline (Apple News, SmartNews, MSN Dec, Yahoo)
  - `Top Stories 2026 Syndication.xlsx` — 2026 YTD (Apple News, Notifications, SmartNews, Yahoo, MSN)
  - `Tracker Template.xlsx` — optional; enables Finding 9 (team performance)

## Data Status (as of 2026-03-28)

| Source | Status | Notes |
|--------|--------|-------|
| Apple News 2025 | ✅ In repo | Full year, all columns |
| Apple News 2026 | ✅ In repo | Engagement columns populated (Finding 7 uses them) |
| Apple News Notifications 2025 | ✅ In repo | Full year; news brands from June, Us Weekly all year; 1,443 rows |
| Apple News Notifications 2026 | ✅ In repo | Jan–Feb 2026, 359 rows |
| SmartNews 2025 | ✅ In repo | Full year, 32 category columns |
| SmartNews 2026 | ✅ In repo | 30 cols; category breakdown restored by Tarrow; 11 common cats in Q4 |
| MSN 2025 | ⚠️ Dec-only | Full-year re-export still pending from Tarrow |
| MSN 2026 | ✅ In repo | Jan–Feb, 355 rows |
| MSN video 2026 | ✅ Known (404 rows) | In known-sheets list; not yet wired into analysis |
| Yahoo 2025 | ✅ In repo | Full year |
| Yahoo 2026 | ✅ In repo | 2,116 rows |
| Yahoo video 2026 | ✅ Known (129 rows) | In known-sheets list; not yet wired into analysis |
| SmartNews 2026 category breakdown | ✅ In repo | Tarrow rebuilt; 30 cols, 11 categories common with 2025; now in Q4 |

## Open Items

**Data:**
- [ ] Get full-year 2025 MSN re-export from Tarrow (current = Dec only)

**Analysis (future sessions):**
- [ ] Wire MSN video + Yahoo video into pipeline when sample size warrants
- [x] ~~Add SmartNews 2026 category breakdown~~ — done 2026-03-30; 11 common cats now in Q4
- [ ] Add Mann-Whitney significance tests to sports/biz/pol subtopic tables (3 standing rigor warnings per build)
- [ ] O&O + syndication PV data layer (Chris Palo request; Amplitude access needed)

**Stakeholder shares (still pending):**
- [ ] Share site with Sarah Price
- [ ] SmartNews Entertainment over-index → distribution team
- [ ] "What to know" Featured rate → editorial leads

## Session Log

**2026-03-30: Tarrow data drop + Finding 4 brand-type rewrite**

Tarrow provided: (1) Apple News Notifications 2025 added to 2025 workbook; (2) SmartNews 2026 rebuilt with full category columns.

**SmartNews 2026 categories wired into Q4:** Added `_sn_month`, numeric CATS_COMMON columns, and `normalize()` to `sn26`. Created `sn_all` (2025 + 2026 combined, 11 common categories) for Q4 analysis. Football/LGBTQ are 2025-only, excluded from combined analysis; Technology added to SHOW_CATS. "2026 export lacks category breakdown" caveat retired.

**Notifications 2025 wired into Q5:** Combined 1,443 rows (2025) + 359 rows (2026) = 1,783-row pool. Renamed `Click-Through Rate` → `CTR`. Added `Apple News notifications` to `_KNOWN_SHEETS_2025`.

**Finding 4 brand-type rewrite (major analytical change):** The larger 2025 dataset revealed the previous pooled analysis was mixing two incompatible content populations. Us Weekly (celebrity/entertainment, 4.01% median CTR) and news brands (hard news, 1.41% CTR) are 2.8× apart at baseline with almost entirely non-overlapping formula signals. The "short notification penalty" (−39%) was a pooling artifact — length shows no significant effect within either population separately.

Q5 now runs separately per brand type (`df_q5_news`, `df_q5_uw`, via `_run_q5()` helper). Display in Finding 4 shows two tables. Signals by population:
- **News brands:** "EXCLUSIVE:" positive; attribution (says/told) positive; question format negative
- **Us Weekly:** Named person + possessive positive; numbers negative; "EXCLUSIVE" neutral
- CTR declining trend for news brands documented: Q2 2025 (1.77%) → Q4 2025 (1.26%) → Q1 2026 (1.37%)

Playbook tile pb-4 upgraded from Moderate to High confidence. Hero candidates updated; "short notifications backfire" hero retired.

**2026-03-30: Snapshot version bar**
Added version history system to `docs/index.html`. Weekly trigger (Mon 8am Dallas) copies `docs/index.html` → `docs/snapshots/snap-NNN.html` (snapshot bar script tag stripped). Clicking a pill opens the full historical page in a new tab. Passkey `8812` gates restore (downloads snapshot HTML + pruned `index.json`). Max 5 snapshots. URL guard in `snapshot-bar.js` prevents the bar from rendering inside snapshot files. `generate_site.py` updated with same snapshot bar so all future generated pages include it.

Files changed: `docs/index.html` (bar div + script tag + CSS), `docs/js/snapshot-bar.js` (new), `docs/snapshots/index.json` (scaffold), `generate_site.py` (snapshot bar injected into template).

**Known pre-existing warning:** `generate_site.py` emits a `SyntaxWarning: "\(" is an invalid escape sequence` at build time (Python 3.14) due to a JS regex pattern embedded in the HTML f-string at line 4524. This is pre-existing, does not affect output, and does not affect our snapshot code.

**Trigger:** `trig_01Qze9PVrNErCEYa1fMXxF2U` — shared with csa-dashboard and csa-content-standards. Details in ops-hub REFERENCE.md.

**2026-03-28: README rewrite, charts/tooltips, DRY refactor, code quality**
Multiple sessions: README rewritten (priority-ordered, non-technical entry path, full roadmap); Plotly color/export bugs fixed; color legends and `_COL_TOOLTIPS` (~70 entries) added; `_build_nav()` / `_make_export_js()` DRY refactors; full type hint + docstring pass; column-sortable tables added. See git log for details.

**2026-03-27: Infrastructure, rigor, UX, pipeline**
Full pipeline: `ingest.py` entry point, BH-FDR, bootstrap CIs, rank-biserial, power analysis, hero scoring, playbook tile sorting, main-page versioning/archive, `CLAUDE.md` autonomous workflow, documentation overhaul.

---

*This file follows the Tiered Context Architecture. Budget: ≤150 lines.*
*Current count: ~90 lines*
