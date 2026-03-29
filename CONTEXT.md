# T1 Headline Analysis — Working Context

**Phase:** Phase 2 complete — all 9 findings live, playbook, author-playbooks, experiments, full ingest pipeline
**Status:** Active — monthly cadence; pipeline ready for next Tarrow drop
**Last session:** 2026-03-28 (README rewrite — priority-ordered structure, full roadmap coverage, non-technical entry path)

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
| Apple News Notifications 2026 | ✅ In repo | Jan–Feb 2026, 351 rows |
| SmartNews 2025 | ✅ In repo | Full year, 32 category columns |
| SmartNews 2026 | ✅ In repo | 7 cols (no category breakdown); headline analysis active |
| MSN 2025 | ⚠️ Dec-only | Full-year re-export still pending from Tarrow |
| MSN 2026 | ✅ In repo | Jan–Feb, 355 rows |
| MSN video 2026 | ✅ Known (404 rows) | In known-sheets list; not yet wired into analysis |
| Yahoo 2025 | ✅ In repo | Full year |
| Yahoo 2026 | ✅ In repo | 2,116 rows |
| Yahoo video 2026 | ✅ Known (129 rows) | In known-sheets list; not yet wired into analysis |
| SmartNews 2026 category breakdown | ❌ Unavailable | Only 7 cols in 2026 export |

## Open Items

**Data:**
- [ ] Get full-year 2025 MSN re-export from Tarrow (current = Dec only)

**Analysis (future sessions):**
- [ ] Wire MSN video + Yahoo video into pipeline when sample size warrants
- [ ] Add SmartNews 2026 category breakdown if/when Tarrow export restores it (Scenario 4 in PLAYBOOK.md)
- [ ] Add Mann-Whitney significance tests to sports/biz/pol subtopic tables (3 standing rigor warnings per build)
- [ ] O&O + syndication PV data layer (Chris Palo request; Amplitude access needed)

**Stakeholder shares (still pending):**
- [ ] Share site with Sarah Price
- [ ] SmartNews Entertainment over-index → distribution team
- [ ] "What to know" Featured rate → editorial leads

## Session Log

**2026-03-28: README rewrite**
- Full rewrite of README.md for clarity, completeness, and priority-ordered structure
- Added table of contents with 10 sections; moved "Why this exists" + variant allocation model to section 2 (was last)
- Added post-build verification checklist (5 checks with expected values) — previously only in PLAYBOOK.md
- Added key thresholds to watch table (where findings will shift significance as data grows) — previously only in PLAYBOOK.md
- Expanded future roadmap: full data gaps table (with priorities), instrumentation roadmap (canon article ID, variant count, formula/platform tags), and analytical enrichments we can do now
- Architecture and design decisions moved behind operational sections — non-technical stakeholders now have a clean entry path

**2026-03-28: Charts, tooltips, author tiles, finding framing, experiment automation**
- Wired build report display for `_audit_warnings`, `_palette_warnings`, `_formula_warnings`
- Fixed Plotly.restyle double-wrap bug: per-bar color arrays must be passed as `[mc]` not `mc` (all bars were rendering as the first color in light mode)
- Fixed export background: read from `document.body` instead of panel element (panels have `rgba(0,0,0,0)` — dark mode exported as white)
- Added color legends to fig1–fig4: `_lift_legend_traces()`, `_sn_legend_traces()`, `_LEGEND_BELOW` shared constant; dummy `go.Scatter` traces generate legend entries for single-trace per-bar-color charts
- Added `_check_chart_legends()` build guardrail — fails if any chart uses per-bar colors without `showlegend=True`
- Added `_COL_TOOLTIPS` dict (~70 entries) + `_make_col_tooltip_js()` — hovering any `<th>` shows a floating plain-English tooltip; injected into all 3 pages
- Added `_check_col_tooltips()` build guardrail — fails if any rendered `<th>` has no matching tooltip
- Reframed F4 tile: leads with short-notification counter-finding (≤80 chars = 39% fewer clicks) rather than obvious EXCLUSIVE lift
- Reframed F7 tile: Apple News-specific two-strategy framing (reach vs. depth) rather than generic correlation statement
- Fixed author tile callout: replaced hardcoded dark hex values with CSS variables; added "Recommended actions this round" header; structured DO/TRY list driven by confidence badge
- Added step 4b to `ingest.py`: discovers and regenerates all `experiments/*.md` spec files so nav/theme/export JS stay in sync on every ingest
- README fully updated: pipeline diagram, audit suite, tooltip/legend design decisions, experiment automation, triage table

**2026-03-28: DRY refactor (nav + export JS)**
- Added `_NAV_PAGES` + `_build_nav()` to `generate_site.py` — replaced 3 hardcoded nav blocks (~40 lines each → 1 call each)
- Added `_make_export_js()` to `generate_site.py` — replaced 3 hardcoded `_findTileForPanel` + `_exportPanel` blocks (~120 lines each → 1 call each)
- Copied `_NAV_PAGES` + adapted `_build_nav()` into `generate_experiment.py` — replaced 2 hardcoded nav blocks
- Verified formula label keys consistent between `FORMULA_LABELS` and `_FORMULA_LABELS` (both 7 keys, display strings intentionally differ)
- Confirmed cache-control meta tags present on all 3 main pages
- All 5 page types pass nav consistency audit (4 links each, correct active link, correct hrefs)
- Build: JS syntax valid, 6 expected rigor warnings, row counts unchanged (AN=4174, SN=38251, Notif=351)

**2026-03-28: Code quality / refactor**
Full refactor pass on all three Python scripts:
- Fixed data loss bug: `_fix_mac_encoding` was discarded via `.reindex()` after `.dropna()`
- Fixed invalid `\s` escape sequences in JS f-strings (suppressed SyntaxWarnings)
- Fixed `__import__("json")` → `json` (already imported)
- Removed unused import (`make_subplots`) and dead code (`col = spec.get(...)` in generate_experiment.py)
- Added type hints to all public functions across generate_site.py, ingest.py, generate_experiment.py
- Added docstrings to all statistical helpers and key functions
- Added module-level docstrings to all three scripts
- Tightened exception handling (bare `except Exception` → specific types with messages)
- Converted table generator string accumulation to list-join pattern
- Added column-sortable tables to all pages (JS + CSS, zero-dependency, auto-attaches on load)

**2026-03-27: Infrastructure, rigor, UX, pipeline**
Full pipeline: `ingest.py` entry point, BH-FDR, bootstrap CIs, rank-biserial, power analysis, hero scoring, playbook tile sorting, main-page versioning/archive, `CLAUDE.md` autonomous workflow, documentation overhaul.

---

*This file follows the Tiered Context Architecture. Budget: ≤150 lines.*
*Current count: ~90 lines*
