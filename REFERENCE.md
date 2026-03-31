# T1 Headline Analysis — Reference

Stable facts for this project. Updated in place when facts change — not a log.

---

## Project Overview

**What it is:** Data analysis of headline and topic performance signals from app-based distribution (Apple News, SmartNews, MSN, Yahoo) for McClatchy Tier 1 outlets.

**Ultimate goal (Chris's directive):** Build a **variant allocation model** — calibrate how many AI-generated article variants to produce per canon article, by article type and platform, based on historical ROI. For some article types, 2 variants is optimal; for others, 12. The answer depends on which article type × platform combinations historically drive the best return.

**The model being built:**
> Canon article type/features × Distribution platform → Historical ROI → Optimal variant count

**Why it exists:** Justin Frame (SVP, external to this team) produced a headline performance analysis on Mar 24, 2026 before the internal team did. Chris directed this workstream as the internal response — and framed it as the foundation for ongoing content testing calibration.

**Scope:** Headline-only — no thumbnails, video, content length, or article body data. T1 outlets only.

**Known data gap:** Current Tarrow sheet data shows ROI (views, CTR, engagement) but does not track variant count or whether articles are AI-generated variants vs. originals. This analysis establishes the historical ROI baseline; variant tracking instrumentation will need to be built separately to close the loop.

**Not:** A CSA dashboard project. Not Semrush. Not Google Discover. Findings that belong in the dashboard get communicated back separately.

---

## Quick Reference

| Resource | Value |
|----------|-------|
| GitHub repo | https://github.com/piercewilliams/data-t1headlines |
| CSA dashboard repo | https://github.com/piercewilliams/csa-dashboard |
| Branch | main |
| Dashboard register entries | `rq-apple-news-monitoring`, `rq-content-learning-loop`, `rq-headline-tool`, `rq-title-options` |
| Tarrow 2026 Google Sheet | https://docs.google.com/spreadsheets/d/1Va8hnBtaX8fEFU8FVPpFcAN82o5RDF9fJBaJvRzrN7s/edit?gid=0#gid=0 |
| Tarrow 2025 Google Sheet | https://docs.google.com/spreadsheets/d/1LlVmW7KTRRpFWXD07wJXDHJhvLTd-1g88Y9cm5D_9o4/edit?gid=0#gid=0 |
| Content tracker | `~/Downloads/Tracker Template.xlsx` — Data sheet has Published URL/Link, Author, Vertical, Pub Date |

---

## Team

| Person | Role | Relevance |
|--------|------|-----------|
| Pierce Williams | CSA ops lead | Running this analysis |
| Sarah Price | Content strategist | Co-analyst; has access to Tarrow's sheet; aligned on Apple News work |
| Chris Tarrow | Distribution / platforms | Maintains the T1 headline performance Google Sheet; gave go-ahead Mar 25 |
| Justin Frame | SVP (external) | Produced Mar 24 headline performance analysis — this project is the response |
| Sara Vallone | Content team lead | Parallel persona work; loop in if persona data ever crosses headline data |
| Susannah | Product (CSA vendor) | Relevant if findings generate product requests; not a direct collaborator |
| Chris Palo | McClatchy leadership | Owns Semrush scope conversation; separate from this headline work |

---

## Primary Data Asset

**Tarrow's T1 Headline Performance Sheet**
- Maintained by Chris Tarrow; live Google Sheet updated at the start of every month
- Coverage: Apple News, SmartNews, MSN
- Outlets: Tier 1 only
- Time range: full 2025 + Jan 1, 2026–present
- Scope: headline-only (no thumbnails, video, content length, article body)
- Access: Pierce Williams + Sarah Price (as of Mar 25, 2026)

---

## Justin Frame's Analysis — Validated Formulas (Mar 24, 2026)

Source: 1,034 stories, 3.37M PVs, 18 newsrooms

| Formula | Signal | Notes |
|---------|--------|-------|
| `[Named entity + concrete action] + [Named place]` + `. Here are X takeaways` or `. What to know` | **Winning formula** | Works across business, breaking news, crime, food/retail |
| `Here are X takeaways` | Avg 2,299 PVs; 24 data points | Highest-yield replicable format |
| Lead with number (`4 businesses closing...`) | Avg 4,934 PVs | Highest signal when story is inherently a list |
| `Here's a look` | Avg 5,214 PVs | Underused; outperforms "What to know" on positive/community stories |
| `What to know` | Variable | Named entity + concrete action = performs; vague subject = flatlines |
| `Did you miss these 3 stories?` | Ceiling ~65 PVs across 31 stories | Format problem, not headline problem — replace with original content |
| Commons/Discover: `rare + unexpected + scientific validation + mystery framing` | — | "Never Seen Before," "New Species," "Scientists Found" |

These formulas are already logged in the CSA dashboard under `rq-headline-tool` and `rq-title-options`.

---

## Adjacent Context (Inform, Don't Conflate)

**Persona work (parallel track — Sara Vallone + Sarah Price)**
- 350+ unique personas in CSA history; massive long-tail making analysis noisy
- Top performers by usage: General Audience (283), Trend Hunter (82), TH B2C (73)
- Plan: consolidate TH/TH B2C variants, pin a controlled set via Susannah
- Pierce requested top 15 persona texts from Susannah Mar 25
- Relevant to T1 analysis only IF persona data is ever crossed with headline data

**Keyword compliance (separate — Sara Vallone's pain point)**
- `rq-keyword-compliance` — keywords not reliably incorporated by CSA into headlines/H2s
- Not a data analysis task; it's a product fix

**Semrush (separate — Chris Palo)**
- Three use cases scoped, not yet committed
- Confirmed: no bearing on app-based distribution headline analysis

---

## Data Enrichment Roadmap

Things to get or build to make the variant allocation model more powerful. Priority-ordered.

### Ask Tarrow for (blocking or high-value gaps in current data)

| Priority | What to ask for | Why it matters |
|----------|----------------|---------------|
| ✅ Resolved | **MSN full year 2025** — full year in repo (Jan–Dec, 4,201 rows); was already present, CONTEXT.md was stale | — |
| ✅ Resolved | **Apple News 2026 engagement columns** — now populated; active time, saves, shares, subscriber splits all in use in Finding 7 | — |
| ✅ Resolved | **SmartNews 2026 category channel breakdown** — Tarrow rebuilt; 11 common cats now in Q4 combined analysis | — |
| ✅ Resolved | **Apple News Notifications 2025** — full year in repo (news brands from June, Us Weekly all year); combined 2025+2026 pool = 1,783 rows in Finding 4 | — |
| 🟢 Nice to have | **Yahoo Content Viewers 2026** — 82% null in current export | Unique reach metric is unusable for Yahoo 2026 |

### Instrument going forward (to enable the variant allocation model)

| Priority | What to build | Why it matters |
|----------|--------------|---------------|
| 🔴 High | **Canon article ID field** — a stable ID linking every variant back to its source article. CSA calls this "Cluster ID" (string: cluster+persona+article type, dash-separated, passed as Q metadata). Actively being scoped as of 2026-03-26. | Without this, variant count → ROI correlation is impossible. This is the single most important field for the model. |
| 🔴 High | **Variant count per canon article** — how many variants were generated and distributed per article. Diff tool (cosine similarity pairwise comparison) is #1 CSA engineering priority as of 2026-03-26; Phase 1 = measurement, Phase 2 = generation-time gating. | The dependent variable in the allocation model |
| 🟡 Medium | **Article type / topic tag at publish time** — content category label applied upstream (e.g., crime, politics, local business, weather, sports) | Currently must be inferred by regex from headlines; upstream tagging is cleaner and more consistent |
| 🟡 Medium | **Headline formula tag at generation time** — which template/formula was used (number lead, "What to know", possessive named entity, etc.) | Currently inferred post-hoc; tagging at generation makes formula → CTR analysis systematic |
| 🟡 Medium | **Platform-targeted variant flag** — was this variant written for Apple News, MSN, SmartNews, or Yahoo specifically? | Platforms operate as separate content ecosystems (94–99% exclusive content); platform-specific variants will outperform generic ones |
| 🟢 Nice to have | **Outlet/T1 filter field** — explicit flag for T1 vs. non-T1 articles in the distribution data | Apple News and SmartNews mix T1 and non-T1 content; need clean T1 segmentation |

### Analytical enrichments (can do ourselves without new data)

| What | How |
|------|-----|
| NLP topic classifier on headline text | Train or prompt-based classifier to auto-tag article type from headline; removes dependency on upstream tagging |
| Serial installment story detector | Flag articles that are part of an ongoing news event (e.g., Savannah Guthrie story cluster) — these are a distinct CTR category |
| Outlet-level performance segmentation | Use existing Brand/Channel/domain columns to break down ROI by T1 outlet (Miami Herald vs. Charlotte Observer vs. others) |
| Headline formula classifier | Regex-based tagger that auto-classifies notification text into formula types for systematic CTR comparison |

---

## Output Files

All charts are interactive Plotly figures embedded in the generated HTML — not static files.

| Output | Location | Contents |
|--------|----------|----------|
| Main analysis | `docs/index.html` | 9 findings, interactive tiles, 9 Plotly charts |
| Editorial playbooks | `docs/playbook/index.html` | 5 platform-specific playbook tiles, sortable tables |
| Monthly archive | `docs/archive/YYYY-MM/index.html` | Full snapshot of each prior run |
| Experiments | `docs/experiments/index.html` | Before/after experiment index |

---

## Chris's Directive (Mar 24, 2026)

> "The narrative is being driven outside of us currently. We should be driving and documenting what we are testing and learning."

---

## Analysis Pipeline (live)

The site is fully automated. `ingest.py` is the only entry point needed. See `README.md` for architecture and `PLAYBOOK.md` for scenario guidance.

The pipeline answers these 9 questions on every run:

| Finding | Question |
|---------|----------|
| 1 | Which headline formula types are associated with higher Apple News views? |
| 1b | Do round vs. specific numbers in number-lead headlines differ in performance? |
| 2 | Do Featured picks favor certain formula types? |
| 3 | Which SmartNews categories have the best ROI vs. volume? |
| 4 | Which notification headline features predict higher CTR? |
| 5 | How do topic × platform rankings differ (Apple News vs. SmartNews)? |
| 6 | Where does headline choice matter most? (variance by topic) |
| 7 | Are views and reading depth independent? |
| 8 | How have formula lift patterns changed over time? |
| 9 | How do team/author performance metrics look via tracker join? |

### Ad-hoc analysis skills (for Claude Code sessions)

For deeper or exploratory analysis beyond the standing pipeline, use these skills:

| Skill | Role |
|-------|------|
| `excel-analysis` | Profile a new or unfamiliar data file |
| `code-data-analysis-scaffolds` | Plan an analysis before writing code |
| `data-sleuth` | Detect non-obvious patterns and anomalies |
| `polars` | Fast DataFrames for group comparisons, classifiers, cross-tabs |
| `data-analysis` | McKinsey-quality Plotly charts |
| `interactive-report-generator` | Add a new finding to the site |
| `data-analysis-sql` | Heavy joins/aggregations (DuckDB fallback) |

### Python environment

All dependencies are in `requirements.txt`. Core: pandas, numpy, scipy, plotly, openpyxl. Extended: statsmodels (logistic regression, Kruskal-Wallis), scikit-learn (TF-IDF), polars (ad-hoc sessions), pingouin (richer stats), xlrd (legacy .xls). Pipeline degrades gracefully if extended packages are absent.

### Reproducibility

`generate_site.py` is the single source of truth. Every number on the site is computed from the raw Excel files on each run — no manual HTML editing. Numbers are always grounded in the source DataFrames.

## Synthesis Skills (Available in This Claude Code Environment)

- **synthesis-thinking-framework** — structure the analysis approach (four-mode reasoning)
- **synthesis-tree-of-thought** — interpret ambiguous performance signals from Tarrow's sheet
- **synthesis-content-framing** — package and publish findings internally
- **synthesis-fact-checking** — verify claims from external analyses before relying on them
