# T1 Headline Analysis — Working Context

**Phase:** Phase 2 complete — analysis, site, experiment framework, and tooling all live
**Status:** Active — awaiting Tarrow data; experiment framework ready to run when data grows
**Last session:** 2026-03-27 (two sessions)

For stable reference facts: see [REFERENCE.md](REFERENCE.md)
For session history: see [sessions/](sessions/)

---

## Current State

- **Data:** Both Tarrow sheets analyzed (2025 full year + 2026 Jan–Feb); Phase 2 analysis complete
- **Site:** `docs/index.html` — Phase 2 live; Phase 1 preserved at `docs/v1/`
- **Generator:** `generate_site.py` — run to regenerate site from raw Excel; fully reproducible
- **Skills installed:** `polars`, `interactive-report-generator`, `code-data-analysis-scaffolds` added to `~/.claude/skills/`
- **CSA dashboard:** Separate repo; not touched by this project

## Phase 2 Key Findings (2026-03-26)

**Formulas (Apple News, non-Featured, n=2,229):**
- "Here's/Here are" (2.97×) and possessive named entity (1.94×) lead — directional, not yet sig (n too small)
- Number leads (0.65×, p<0.001), questions (0.51×, p<0.001), quoted ledes (0.61×, p<0.001) significantly underperform

**Featuring (Q2):**
- "What to know" = 62% Featured rate vs. 27% baseline — strongest signal in dataset (p=0.0006)
- Questions Featured at 37% but underperform within Featured (0.60× vs. Featured avg)

**SmartNews allocation (Q4):**
- Local channel: 108× views lift vs. Top feed, only 2.9% of article volume
- U.S. National: 73× lift, 2.4% of volume
- Entertainment: 35.9% of volume, 1.46× lift — severely over-indexed

**Notifications (Q5, n=351):**
- "Exclusive" tag: 2.49× CTR lift (partly confounded by Guthrie serial story cluster)
- Full name present: 1.21× lift (p<0.001)
- Questions: 0.64× (p<0.001) — hurt CTR
- Short (≤80 chars): 0.61× — longer notifications perform better

**Topics (Q3/cross-platform):**
- Zero keyword overlap between Apple News and SmartNews top performers
- Weather + sports lead Apple News; local/civic leads SmartNews
- Platforms need separate content strategies

## CSA Instrumentation Status (as of 2026-03-26)

- **Cluster ID (= canon_article_id):** Actively being scoped in CSA. String format: cluster + persona + article type, dash-separated, passed as Q metadata.
- **Diff tool (#1 CSA priority):** Cosine similarity pairwise comparison (Jim Robinson + Marcelo). Phase 1 = measurement; Phase 2 = generation-time gating.
- **Reporting pressure:** Paul Barry (data science / Sigma dashboards) left — temporary air cover — but Britney/Justin's team pressure re-emerging.
- **Personas ticket:** "Fetch audience target definitions" not yet picked up by engineers.

## What's Next — Prioritized

**Awaiting Tarrow data (confirmed "asap" 2026-03-26):**
1. [ ] MSN full year 2025 — filter: <10k article views excluded
2. [ ] Apple News 2026 engagement columns (17 empty)
3. [ ] Apple News Notifications 2025 (full-year CTR — would validate Q5 findings)
4. [ ] SmartNews 2026 category breakdown (32 cols → 7)
5. [ ] Jan 1–now 2026 pull

**When data arrives:**
6. [ ] Re-run `generate_site.py` with fuller notification dataset to validate CTR findings
7. [ ] Add MSN full-year to topic × platform analysis (currently Dec only)
8. [ ] Test possessive named entity formula more deliberately — build sample (currently n=75)

**Share with stakeholders:**
9. [ ] Share Phase 2 site with Sarah Price — aligned workstream
10. [ ] SmartNews allocation finding (Entertainment over-index) → flag to distribution team
11. [ ] "What to know" Featured rate finding → share with editorial leads

**Build (instrumentation):**
12. [ ] Add canon_article_id + variant_count to distribution pipeline (track via Jira "National CSA" label)

## Session: 2026-03-27b (UX redesign + hero headline)

Full CSS redesign of `generate_site.py`: off-white body background, glass-blur nav, diagonal gradient hero, stat numbers grouped in a frosted bordered card, callout converted to light-blue card (no left-border accent), charts use shadow instead of border, tables card-style with rounded corners and hover rows, typography tightened (15px body, sans-serif h2, small-caps h3). Hero h1 rewritten from jargon ("Formula is a signal…") to: *"One headline phrase doubles your chance of being Featured on Apple News. The wrong SmartNews channel cuts your reach by 100×."*

## Session: 2026-03-27a (Infrastructure — accordion UI, archive pipeline, experiment framework, audit)

Four workstreams:

**Accordion UI:** Converted site from flat sections to `<details>`/`<summary>` cards. Executives see only action headlines; click to expand charts + data. "Expand all" toggle in nav. Hash-based auto-open for direct links. Phase 1 link removed from footer (kept in repo at `docs/v1/`).

**Monthly archive pipeline:** `ingest.py` — snapshots current site to `docs/archive/YYYY-MM/`, saves `data_profile.json`, diffs row counts against prior run, fires analysis suggestions from an opportunity map, calls `generate_site.py`, then prints commit instructions. Archive index uses the site's hero h1 as link text (not a date label). `PLAYBOOK.md` — universal 5-step checklist + 7 scenario sections with exact Claude prompts.

**Experiment framework:** `generate_experiment.py` reads YAML+markdown spec files from `experiments/` and produces self-contained HTML reports. Two runnable types: `formula_comparison` (Mann-Whitney or chi-square, A=control/baseline, B=treatment) and `temporal_cohort` (before/after date split with time-series chart). Pending experiments skip cleanly. Two active experiments committed: WTN Featured rate (significant, 2.11× lift) and possessive formula views (1.39×, not yet significant). One pending: notification CTR H2 2026 (awaiting data).

**Audit:** Eliminated all hardcoded stats that would diverge on next ingest. Hero numbers, h2 headlines, action callout figures, prose stats, and all 3 data tables now computed from data on every run. Nav/footer date uses `datetime.now()`. `PLATFORMS` counts loaded sheets. Added chi-square per formula + within-Featured median to Q2. Experiment index: pending experiments show as greyed text (no broken link). Formula comparison statistics table shows formula names, not "before/after".

## Session: 2026-03-26 (Phase 2 — full analysis)

Housekeeping first: versioned Phase 1 to `docs/v1/`, installed 3 new skills (`polars`, `interactive-report-generator`, `code-data-analysis-scaffolds`), updated REFERENCE.md with Phase 2 pipeline. Then ran full analysis across all 6 questions using scaffold → excel-analysis → polars → interactive-report-generator pipeline. Key data notes: Notifications = 359 rows (not 55 as assumed), SmartNews categories are view-count columns (not binary flags), MSN 2025 is December only. All findings grounded in raw Excel; site regenerates from `generate_site.py`.

---

*This file follows the Tiered Context Architecture. Budget: ≤150 lines.*
*Current count: ~103 lines*
