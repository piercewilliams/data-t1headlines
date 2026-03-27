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

## CSA Instrumentation Status (as of 2026-03-26)

- **Cluster ID (= canon_article_id):** Actively being scoped in CSA. Plan is to pass as metadata through Q (not necessarily exposed in UI). String format: cluster + persona + article type separated by dashes. Proactive assignment is ideal; retroactive acceptable.
- **Diff tool (#1 CSA priority):** Cosine similarity pairwise comparison between variants, being built now (Jim Robinson + Marcelo). Phase 1 = automated measurement exposed in tool. Phase 2 = CSA auto-detects and gates variant differentiation during generation.
- **Reporting pressure:** Paul Barry (data science / Sigma dashboards) has left — temporary air cover — but Britney/Justin's team pressure on CSA content reporting is re-emerging. Variant tracking need is not going away.
- **Personas ticket:** "Fetch audience target definitions" not yet picked up by engineers.

## What's Next — Prioritized

**Awaiting Tarrow data (confirmed "asap" 2026-03-26):**
1. [ ] MSN full year 2025 — Tarrow confirmed; filter: <10k article views excluded (Pierce approved)
2. [ ] Apple News 2026 engagement columns (17 empty) — confirmed
3. [ ] Apple News Notifications 2025 (full-year CTR) — confirmed
4. [ ] SmartNews 2026 category channel breakdown (32 cols → 7) — confirmed
5. [ ] Jan 1–now 2026 pull to complement 2025 sheet — confirmed

**High (do next session):**
6. [ ] Run focused headline + keyword analysis for Sarah Price joint session — 6 questions scoped (formulas, Featured lift by formula, keyword lift table, SmartNews category ROI, notification CTR features, allocation model variance)
7. [ ] Run possessive named entity headline test across next 20 Apple News push notifications
8. [ ] Shift SmartNews variant effort toward Local/U.S. National, away from Entertainment

**Medium:**
7. [ ] Add active time + saves to ROI definition alongside views
8. [ ] Design platform-specific variant briefs per platform audience signal
9. [ ] Publish GitHub Pages site (repo Settings → Pages → Source: docs/)

**Build (instrumentation):**
10. [ ] Add canon_article_id + variant_count fields to distribution pipeline — CSA calling this "Cluster ID"; actively being scoped (track via Jira "National CSA" label)

## Session: 2026-03-26 (fourth pass — stakeholder sync + next phase scoping)

Reviewed conversations from CSA weekly meeting, Jira walkthrough, and Slack threads. Key updates: Cluster ID (= canon_article_id) actively being scoped in CSA; diff tool (cosine similarity) confirmed as #1 CSA priority; Paul Barry left (Sigma dashboards gap). Site shared publicly with team — Pierce described it as "a possible place to start" and noted data is patchy. Aligned with Sarah Price: headline analysis (Tarrow) and Semrush are separate workstreams. Scoped 6 focused questions for joint headline analysis session with Sarah (formulas, Featured lift by formula, keyword lift table, SmartNews category ROI, notification CTR features, allocation model variance). Tarrow confirmed all 4 data requests + 2026 Jan-now pull; MSN will exclude <10k article views.

## Recent Session: 2026-03-26 (third pass — final verification)

Pulled Featured by Apple median views directly from raw Excel (`Top syndication content 2025.xlsx`, Apple News sheet) via Python. Confirmed: **10,911** featured median views (n=810), **1,619** non-featured (n=2,229), **6.74×** lift, **51s vs 57s** active time. Session notes had 11,180 — confirmed typo; site was correct all along. Updated h3 heading from "6.7×" → "6.74×" for precision. Corrected 11,180 → 10,911 everywhere in CONTEXT.md and sessions/2026-03.md. Site is fully verified; every stat traceable to raw data.

## Prior Session: 2026-03-26 (second pass — exec prep)

CSS-only design refresh + content audit. Palette `#003366` → `#0f172a`; hero gradient removed; cards white + top-border accent; tables no zebra; tags square; chart JS colors updated. Content fixes: n=3,037→3,039; comparison table row 6 strawman removed; "Frame deck" name removed from action 5. See sessions/2026-03.md for detail.

## Prior Session: 2026-03-26 (first pass)

Interactive Chart.js charts built; full data verification against raw Excel. See sessions/2026-03.md for detail.

---

*This file follows the Tiered Context Architecture. Budget: ≤150 lines.*
*Current count: ~65 lines*
