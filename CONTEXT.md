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

## Recent Session: 2026-03-26

Replaced all 4 static PNG charts with interactive Chart.js visualizations matching site palette. Then ran full data verification — recomputed every chart value from raw Excel files. Corrected:
- Chart 3 saves quartiles: fabricated [12,48,215,1140] → actual [3,6,19,67]
- Chart 1 CTR lifts: added serial/escalating story (+289%); removed confounded "long headline +131%" (actual +8% ex-serial); corrected question −33%→−18%, local biz −35%→−23%
- Chart 4 platform exclusivity: Apple News 98.9%→85.9% (it shares more with SmartNews/Yahoo than originally computed); all four platforms recomputed from exact title match
- Correlation: r=−0.01, p=0.44 → r=−0.007, p=0.70 (using correct full n=3,039 dataset)
- Overlap counts: AN∩MSN 35→25, SN∩MSN 510→202, SN∩Yahoo 346→309, 3+ platforms 32→24

Key finding unchanged: active reading time statistically independent of views. Featured by Apple: 6.74× lift confirmed (11,180 vs 1,619 median views), active time 51s vs 57s (p<0.0001).

---

*This file follows the Tiered Context Architecture. Budget: ≤150 lines.*
*Current count: ~65 lines*
