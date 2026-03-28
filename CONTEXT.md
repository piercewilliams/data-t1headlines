# T1 Headline Analysis — Working Context

**Phase:** Phase 2 complete — all 9 findings live, playbook, experiments, full ingest pipeline
**Status:** Active — monthly cadence; pipeline ready for next Tarrow drop
**Last session:** 2026-03-28 (code quality / refactor pass)

For stable reference facts: see [REFERENCE.md](REFERENCE.md)
For session history: see [sessions/](sessions/)

---

## Current State

- **Site:** `docs/index.html` — 9 findings, interactive tiles, dark/light mode, sortable tables
- **Playbook:** `docs/playbook/index.html` — 5 tiles sorted by confidence level
- **Generator:** `generate_site.py` — fully typed, documented, refactored; run via `ingest.py`
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
