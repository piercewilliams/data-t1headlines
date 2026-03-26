# T1 Headline Analysis — Working Context

**Phase:** Phase 1 complete — findings packaged, GitHub Pages site built
**Status:** Active — awaiting Tarrow data requests + GitHub Pages publish
**Last session:** 2026-03-26

For stable reference facts: see [REFERENCE.md](REFERENCE.md)
For session history: see [sessions/](sessions/)

---

## Current State

- **Data:** Both Tarrow sheets fully analyzed (2025 full year + 2026 Jan–Feb)
- **Platforms covered:** Apple News, SmartNews, MSN, Yahoo
- **Charts:** 4 interactive Chart.js visualizations in `docs/index.html` (static PNGs in `charts/` retained as backup)
- **GitHub Pages site:** Built at `docs/index.html` — enable Pages in repo settings to publish
- **Key finding confirmed:** Views and active reading time are statistically independent (r=−0.007, p=0.70, n=3,039)
- **All chart data verified:** Recomputed from raw Excel in session 2026-03-26; all values grounded in actual data
- **CSA dashboard:** Separate repo; not touched by this project

## What's Next — Prioritized

**High (ask Tarrow — blocking):**
1. [ ] Request MSN full year 2025 — current export is December only
2. [ ] Request Apple News 2026 with engagement columns populated (17 are empty)
3. [ ] Request Apple News Notifications 2025 (full-year CTR data, not just Jan–Feb 2026)
4. [ ] Request SmartNews 2026 category channel breakdown (32 cols in 2025 → 7 in 2026)

**High (test now):**
5. [ ] Run possessive named entity headline test across next 20 Apple News push notifications
6. [ ] Shift SmartNews variant effort toward Local/U.S. National, away from Entertainment

**Medium:**
7. [ ] Add active time + saves to ROI definition alongside views
8. [ ] Design platform-specific variant briefs per platform audience signal
9. [ ] Publish GitHub Pages site (repo Settings → Pages → Source: docs/)

**Build (instrumentation):**
10. [ ] Add canon_article_id + variant_count fields to distribution pipeline

## Recent Session: 2026-03-26 (second pass — exec prep)

Design refresh and pre-presentation audit of `docs/index.html`. CSS-only visual overhaul (no content touched): palette shifted from flat navy `#003366` to slate `#0f172a`; hero gradient removed; finding cards changed from colored backgrounds to white + colored top-border accent; table zebra striping removed; tags changed from pill to square-corner; chart JS color constants updated to match. Three factual fixes:
- n=3,037 → **3,039** in active-time section text
- Comparison table row 6: removed strawman framing ("page views signal content quality") → replaced with fair characterization ("page views are the primary ROI signal") with same Incomplete verdict
- Action 5: removed "the Frame deck" name attribution; point stands without the call-out

**Verified against raw Excel:** Featured by Apple median views = 10,911 (n=810 featured, 2,229 non-featured). 6.74× lift confirmed. Non-featured median 1,619. Active time 51s vs 57s. Session notes had a typo (11,180); site values are correct.

## Prior Session: 2026-03-26 (first pass)

Replaced all 4 static PNG charts with interactive Chart.js visualizations. Ran full data verification — recomputed every chart value from raw Excel. Corrected saves quartiles, CTR lifts, platform exclusivity, correlation values, and overlap counts. See sessions/2026-03.md for detail.

---

*This file follows the Tiered Context Architecture. Budget: ≤150 lines.*
*Current count: ~65 lines*
