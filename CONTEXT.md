# T1 Headline Analysis — Working Context

**Phase:** Phase 1 complete — findings packaged, GitHub Pages site built
**Status:** Active — awaiting Tarrow data requests + GitHub Pages publish
**Last session:** 2026-03-25

For stable reference facts: see [REFERENCE.md](REFERENCE.md)
For session history: see [sessions/](sessions/)

---

## Current State

- **Data:** Both Tarrow sheets fully analyzed (2025 full year + 2026 Jan–Feb)
- **Platforms covered:** Apple News, SmartNews, MSN, Yahoo
- **Charts:** 4 executive PNGs in `charts/` and `docs/charts/`
- **GitHub Pages site:** Built at `docs/index.html` — enable Pages in repo settings to publish
- **Key finding confirmed:** Views and active reading time are statistically independent (r=−0.01, p=0.44)
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

## Recent Session: 2026-03-25

Full inaugural analysis session. Profiled both Tarrow sheets (excel-analysis skill). Ran investigative signal detection (data-sleuth): headline CTR by formula, platform ROI by topic, engagement depth vs. views, cross-platform overlap, temporal trends, absence signals. Packaged 4 executive charts (data-analysis skill). Built GitHub Pages presentation site at docs/index.html — includes Frame deck comparison, active time deep dive with full statistical backing (r=−0.01, decile table, Kruskal-Wallis, subscriber split), SmartNews category ROI, push CTR signals, platform isolation, data gaps, and 7 ordered action items.

Key finding: active reading time is statistically independent of view count. Featured by Apple produces 6.7× more views and slightly shorter read times. Saves scale strongly with views (r=0.82); depth does not (r=−0.01). The Frame deck's implicit "clicks = quality" framing is not supported by the depth data.

---

*This file follows the Tiered Context Architecture. Budget: ≤150 lines.*
*Current count: ~60 lines*
