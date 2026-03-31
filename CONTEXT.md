# T1 Headline Analysis — Working Context

**Phase:** Phase 2 complete — all 10 findings live, playbook (6 tiles), author-playbooks, experiments, full ingest pipeline
**Status:** Active — monthly cadence; pipeline ready for next Tarrow drop
**Last session:** 2026-03-30 (MSN wiring — Finding 10, chart c5 updated, playbook tile pb-6)

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
| MSN 2025 | ✅ In repo | Full year, Jan–Dec, 4,201 rows |
| MSN 2026 | ✅ In repo | Jan–Feb, 355 rows |
| MSN video 2026 | ✅ Known (404 rows) | In known-sheets list; not yet wired into analysis |
| Yahoo 2025 | ✅ In repo | Full year |
| Yahoo 2026 | ✅ In repo | 2,116 rows |
| Yahoo video 2026 | ✅ Known (129 rows) | In known-sheets list; not yet wired into analysis |
| SmartNews 2026 category breakdown | ✅ In repo | Tarrow rebuilt; 30 cols, 11 categories common with 2025; now in Q4 |

## Open Items

**Data:**
- [x] ~~Get full-year 2025 MSN re-export from Tarrow~~ — already in repo (4,201 rows, Jan–Dec)

**Analysis (future sessions):**
- [ ] Wire MSN video + Yahoo video into pipeline when sample size warrants
- [x] ~~Add SmartNews 2026 category breakdown~~ — done 2026-03-30; 11 common cats now in Q4
- [x] ~~Wire full-year MSN 2025 into pipeline~~ — done 2026-03-30; Finding 10 live (formula, dislike signal, monthly trend); chart c5 updated with MSN trace; playbook tile pb-6 added
- [ ] Add Mann-Whitney significance tests to sports/biz/pol subtopic tables (3 standing rigor warnings per build)
- [ ] O&O + syndication PV data layer (Chris Palo request; Amplitude access needed)

**Stakeholder shares (still pending):**
- [ ] Share site with Sarah Price
- [ ] SmartNews Entertainment over-index → distribution team
- [ ] "What to know" Featured rate → editorial leads

## Session Log

**2026-03-30: MSN wiring — Finding 10 + chart c5 + playbook tile pb-6**

Full-year MSN 2025 (4,201 rows) wired into analysis pipeline. Changes:

- **Finding 10 added** (main page tile + detail panel): formula lift vs. baseline (BH-FDR corrected Mann-Whitney), dislike signal analysis (unique MSN metric — hi-dislike articles score {MSN_DR_LIFT}× views of lo-dislike; sports highest dislike rate), monthly PV trend showing decline across 2025.
- **Chart c5 updated**: MSN added as third bar trace (orange) to the topic × platform chart; `ORANGE = "#f97316"` color constant added.
- **Playbook tile pb-6 added** (Moderate confidence): MSN platform trajectory and dislike signal guidance. Detail panel added with formula table + monthly trend.
- **Finding 5 caveat updated**: now includes MSN in sample size reference; MSN paragraph added to detail panel pointing readers to Finding 10.
- **`_msn_formula_table()` and `_msn_monthly_table()`** helper functions added.
- **`_COL_TOOLTIPS`** extended with "p (adj)", "month", "articles", "median pageviews".
- **2025 data file updated** in repo root: `Top syndication content 2025.xlsx` replaced with the Tarrow drop that includes the "Apple News notifications" sheet (was missing from the prior file).
- Build: all audits pass; 6 rigor warnings (3 standing + 3 engagement outlier cap notices).

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
