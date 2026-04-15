# T1 Headline Analysis

Analysis of headline and topic performance across Apple News, SmartNews, MSN, and Yahoo for McClatchy Tier 1 outlets. The site is generated fully programmatically from Tarrow's export data — no manual HTML editing. Full pipeline runs monthly; the 2026 sheet auto-refreshes weekly every Monday at 8 PM CDT via GitHub Actions.

> *"The narrative is being driven outside of us currently. We should be driving and documenting what we are testing and learning."* — Chris Tarrow, March 24, 2026

**Live site:** `docs/index.html` (GitHub Pages)
**Owners:** Pierce Williams (CSA ops lead) · Sarah Price (content strategist)
**Full context:** [`REFERENCE.md`](REFERENCE.md) · [`CONTEXT.md`](CONTEXT.md) · [`PLAYBOOK.md`](PLAYBOOK.md)

---

## Contents

1. [What this site shows](#what-this-site-shows)
2. [Where we're headed — the variant allocation model](#where-were-headed--the-variant-allocation-model)
3. [Monthly update — the only command you need](#monthly-update--the-only-command-you-need)
4. [Daily headline grader](#daily-headline-grader)
5. [Version history and rollback](#version-history-and-rollback)
6. [Site structure](#site-structure)
7. [The analyses](#the-analyses)
8. [Statistical standards](#statistical-standards)
9. [Architecture](#architecture)
10. [Developer: adding analyses and experiments](#developer-adding-analyses-and-experiments)
11. [File reference](#file-reference)
12. [Triage guide](#triage-guide)

---

## What this site shows

Each month, the pipeline answers 9 questions about what headline patterns actually perform:

| # | Question |
|---|---------|
| 1 | Which headline formula types are associated with higher Apple News views? |
| 1b | Do round vs. specific numbers in number-lead headlines differ in performance? |
| 2 | Do Featured picks favor certain formula types? |
| 3 | Which SmartNews categories have the best ROI vs. volume? |
| 4 | Which push notification headline features predict higher CTR? |
| 5 | How do topic × platform rankings differ (Apple News vs. SmartNews)? |
| 6 | Where does headline choice matter most? (variance by topic) |
| 7 | Are views and reading depth independent? |
| 8 | How have formula lift patterns changed over time? |
| 9 | How do team/author performance metrics look? (requires Tracker data) |

Results are surfaced as interactive tiles with expandable detail panels, charts, and statistical tables. Each finding carries a **confidence badge** — `High confidence`, `Moderate`, or `Directional` — derived automatically from sample size, adjusted p-value, and replication across platforms. The hero headline at the top of the main page is auto-selected each run by scoring every finding on effect size × significance × surprise factor; it always reflects the most statistically interesting result in the current data.

All views data is **normalized to percentile rank within publication-month cohort** before any comparison. This is essential: raw views accumulate over time, so January articles always look better than December ones. Normalization makes every number a fair comparison — a lift of 1.5× means that formula type's median article lands in a 1.5× higher cohort percentile than baseline.

---

## Where we're headed — the variant allocation model

This analysis is the foundation for a longer-term model:

> **Canon article type × Distribution platform → Historical ROI → Optimal variant count**

For some article types, 2 AI-generated variants is optimal. For others, it may be 12. The answer depends on which article type × platform combinations historically drive the best return — exactly what this pipeline measures.

The current work establishes the historical ROI baseline. Two additional pieces need to be built to close the loop:

**Data gaps being addressed (ask Tarrow):**

| Priority | Gap | Why it matters |
|----------|-----|---------------|
| High | MSN full-year 2025 (currently Dec only) | Can't do any MSN temporal analysis |
| Medium | ~~SmartNews 2026 category breakdown~~ | ✅ Resolved — April 8 export is article-level with 28 channel columns |
| Medium | Apple News Notifications 2025 | Would validate CTR lift findings across full news cycle |
| Low | Yahoo Content Viewers 2026 (82% null) | Unique reach metric currently unusable |

**Instrumentation being scoped (build internally):**

| Priority | What | Why |
|----------|------|-----|
| High | Canon article ID — a stable ID linking every variant to its source (CSA "Cluster ID") | Without this, variant count → ROI correlation is impossible |
| High | Variant count per canon article — how many variants were distributed | The dependent variable in the allocation model |
| Medium | Article type tag at publish time | Currently inferred by regex; upstream tagging is cleaner |
| Medium | Headline formula tag at generation time | Enables systematic formula → CTR tracking |
| Medium | Platform-targeted variant flag | Platforms are 94–99% exclusive; platform-specific variants outperform generic |

**Analytical enrichments we can do now (no new data needed):**

- NLP topic classifier on headline text — removes dependency on upstream tagging
- Serial installment story detector — these are a distinct high-CTR category
- Outlet-level performance segmentation by T1 outlet (Miami Herald vs. Charlotte Observer vs. others)
- Headline formula classifier — extends regex tagger to auto-classify all notification text

---

## Monthly update — the only command you need

**Via Claude Code (recommended):**

Open Claude Code in this directory and say:
> "New Tarrow data is in my Downloads — update the site"

Claude reads `CLAUDE.md`, locates the file, runs the full pipeline, fixes any column-rename or new-sheet warnings autonomously, and tells you when it's ready to push. Push from GitHub Desktop.

**Manually:**
```bash
python3 ingest.py --data-2026 "path/to/new/file.xlsx"
# Add --release 2026-04 if ingesting a prior month's data late
# Add --data-2025 "path/to/file.xlsx" if the historical baseline changed
```

**After every build — verify these 5 things** before pushing:

1. **Hero numbers** — do the three stat boxes still read sensibly?
   - "What to know" Featured rate: expect ~62% unless editorial behavior changed
   - SmartNews Local lift: expect ~108× unless data structure changed
   - "Exclusive" CTR lift: expect ~2.49× (may drift as Guthrie serial story ages out)

2. **Formula chart (Finding 1)** — are all 7 formula types visible? A formula that dropped to n=0 disappears silently.

3. **Platform separation (Finding 5)** — does Sports still lead Apple News? Does Local/Civic still lead SmartNews? These can shift month-to-month — material flips warrant a session to assess.

4. **Variance chart (Finding 6)** — do IQR/median values look in the same ballpark? Extreme outliers (cv > 50 on Apple News) suggest a data anomaly.

5. **Caveat row counts** — scan the grey caveat lines at the bottom of each finding. Do the n= numbers match the build report?

For scenario-specific guidance (new sheets, engagement columns, MSN full year, SmartNews category restore, experiments): see [`PLAYBOOK.md`](PLAYBOOK.md).

---

## Daily headline grader

A separate, fully automated pipeline grades the last 24 hours of headlines from Sara Vallone's live Google Tracker sheet every day at **10 AM Chicago time**. Results appear at `docs/grader/index.html` (Headline Grader tab in the site nav).

### What it grades

Each headline is evaluated against 14 criteria in four tiers:

| Tier | Criteria | Method |
|------|----------|--------|
| Structure & Length | Character count (SN 70–90 / AN 90–120), named entity leads, no article lead, active voice, no lead burial | Rule-based + LLM |
| Formula & Signal | Formula present, no "What to know" headline, keyword present, no question headline | Rule-based |
| Quality Flags | No "Did you miss," no all-caps, curiosity gap, factually accurate | Rule-based + LLM |
| Platform (informational) | Here's/Here are (Apple News signal) | Rule-based |

LLM evaluation uses **Groq** (free tier, `llama-3.3-70b-versatile`). Rule-based criteria use regex. Each headline receives a weighted score (0–100%). The page shows scores worst-first and a 30-day rolling history strip at the top.

### How it runs

The grader runs daily via **GitHub Actions** (`.github/workflows/grader.yml`) — no local machine required. The workflow triggers at 10 AM CDT (`schedule` cron), runs `generate_grader.py`, and commits updated HTML + history JSON via the built-in `GITHUB_TOKEN`.

Required GitHub Actions secrets: `GROQ_API_KEY` and `GOOGLE_SERVICE_ACCOUNT_JSON` (base64-encoded service account JSON — use `~/.credentials/pierce-tools.json`; encode with `base64 -i ~/.credentials/pierce-tools.json | pbcopy`).

A **Run Now** button in the grader UI lets you trigger a manual run without touching the command line. First use requires entering a fine-grained GitHub PAT (actions:write scope); it's stored in `localStorage` after first entry. Passcode: **8812**.

### Running manually

```bash
# Full run (last 24 hours, with LLM):
GROQ_API_KEY=... GOOGLE_SERVICE_ACCOUNT_FILE=~/.credentials/pierce-tools.json python3 generate_grader.py

# Wider lookback for initial run or catch-up:
python3 generate_grader.py --lookback 7

# Objective criteria only, no LLM calls:
python3 generate_grader.py --skip-llm

# Preview without writing files:
python3 generate_grader.py --dry-run
```

### Required credentials

| Credential | Where to set | Purpose |
|-----------|--------------|---------|
| `GROQ_API_KEY` | GitHub Actions secret | LLM headline evaluation |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | GitHub Actions secret (base64) | Google Sheets read access |

Service account JSON: `~/.credentials/pierce-tools.json` (outside the repo — never commit). The Tracker sheet must be shared with the service account email. To encode: `base64 -i ~/.credentials/pierce-tools.json | pbcopy`.

**Key thresholds to watch month-to-month:**

| Finding | Current value | Significance threshold |
|---------|--------------|----------------------|
| "Here's a look" lift | 2.97× (n=16, not sig) | Watch for significance at n≥30 |
| Possessive named entity lift | 1.94× (n=75, not sig) | Watch for significance at n≥100 |
| "What to know" Featured rate | 62% (n=21) | Shifts if editorial guidance changes |
| Exclusive CTR lift | 2.49× (n=16) | May dilute as Guthrie story ages |
| Sports #1 Apple News | 2.13× | Check monthly — topic ranking can shift |
| Local/Civic #1 SmartNews | 1.99× | Check monthly |

---

## Version history and rollback

A row of version pills appears in the footer of the main page. Each pill represents a complete snapshot of `docs/index.html` — the full rendered site, frozen exactly as it was — taken automatically every Monday at 8 AM.

### Browsing a past version

1. Scroll to the footer of the main page and click a version pill (e.g. "Mar 31, 2026").
2. The complete historical page opens in a **new browser tab** — every chart, table, finding, and annotation exactly as it existed at that point in time.
3. Browse freely. The snapshot is a self-contained HTML file.
4. Close the tab to return to the live site.

> Snapshot pages do not show their own snapshot bar, so there is no confusion about which version you are viewing.

### Restoring a past version to the live site

Use this only if the current `docs/index.html` is corrupted, broken, or was incorrectly rebuilt and needs to be rolled back to a known-good state.

1. Open the version you want to restore (step 1–2 above).
2. In the footer of the live page (not the snapshot tab), click the same version pill to activate it, then click **Restore this version** in the banner that appears.
3. A modal appears. Enter the passkey: **8812**
4. Click **Download & Restore** — two files download automatically:
   - `index.html` — the complete historical page. Place it at `docs/index.html`, replacing the current file.
   - `snapshots-index.json` — rename to `index.json` and place at `docs/snapshots/index.json`.
5. Push via GitHub Desktop.

> **Note:** Restoring removes snapshot history newer than the version you restored to. The modal tells you how many versions will be removed.
>
> **Important:** Restoring replaces the live site with the snapshot page. Any data updates made since that snapshot — new Tarrow exports, new analyses, new findings — will not be present. Only restore if the current version is genuinely broken and needs to be replaced.

### How snapshots are maintained

- Snapshots are taken automatically. You do not need to do anything.
- The trigger runs every **Monday at 8 AM Dallas time**.
- A maximum of **5 snapshots** are kept. When a 6th is taken, the oldest is deleted automatically.
- The snapshot bar does **not** appear inside snapshot files — only on the live `docs/index.html`.
- If the snapshot bar shows no pills, the trigger has not yet run — check [claude.ai/code/scheduled](https://claude.ai/code/scheduled) and look for "Weekly Snapshots - All Sites."

---

## Site structure

| Page | Path | Purpose |
|------|------|---------|
| Main analysis | `docs/index.html` | 9 findings tiles, expandable detail panels, Plotly charts, sortable tables |
| Editorial Playbooks | `docs/playbook/index.html` | Per-platform headline guidance synthesized from findings; auto-sorted by confidence level |
| Author Playbooks | `docs/author-playbooks/index.html` | Per-author formula profiles, performance percentiles, structured DO/TRY guidance (requires Tracker data) |
| Experiments | `docs/experiments/index.html` | Before/after formula test index; individual reports at `docs/experiments/{slug}/index.html` |
| Headline Grader | `docs/grader/index.html` | Daily auto-graded headlines from Sara Vallone's Tracker; 30-day score history strip |
| Archive | `docs/archive/YYYY-MM/` | Full monthly snapshot with orange "archived" banner; renders charts online, tables offline |

**Site-wide features:**
- Dark/light mode — persisted across sessions via `localStorage`; chart colors swap at runtime via `_rethemeCharts(isDark)`
- Color legends on all charts that use per-bar coloring
- Plain-English tooltips on hover for all table column headers (defined in `_COL_TOOLTIPS`; ~70 entries)
- PNG/PDF export button on every tile (all pages); export reads background from `document.body` so dark mode exports correctly
- Sortable columns on all tables

**Nav and export are fully programmatic — never hardcoded.** All four page types share nav from `_NAV_PAGES` / `_build_nav()`. All export blocks are generated by `_make_export_js()`. To add a new nav page: update `_NAV_PAGES` in `generate_site.py`, re-run.

---

## The analyses

### Findings overview

| # | Finding | Data source | Primary statistical test |
|---|---------|-------------|--------------------------|
| 1 | Apple News headline formula lift | Apple News 2025–2026 (non-Featured only) | Mann-Whitney U vs. untagged baseline; BH-FDR |
| 1b | Round vs. specific numbers | Subset of Finding 1 | Mann-Whitney round vs. specific |
| 2 | Featured placement by formula | Apple News all | Chi-square; BH-FDR |
| 3 | SmartNews channel ROI vs. volume | SmartNews 2025 (has 32 category columns) | Mann-Whitney vs. Top feed; BH-FDR |
| 4 | Push notification CTR features | Apple News Notifications 2026 (n=351) | Mann-Whitney present vs. absent; BH-FDR |
| 5 | Topic × platform inversion | Apple News + SmartNews 2025 | Mann-Whitney for sports inversion; rest descriptive |
| 6 | Headline variance by topic | Apple News + SmartNews | IQR/median (descriptive) |
| 7 | Views vs. reading depth independence | Apple News 2025–2026 (engagement columns) | Pearson r, Spearman ρ |
| 8 | Formula lift trends over time | Apple News 2025–2026 quarterly | Longitudinal descriptive |
| 9 | Team/author performance | Tracker join → Apple News + SmartNews | Descriptive; Mann-Whitney word count Q4 vs. Q2 |

### Headline classifiers (regex-based)

All classification is done at run time — no labels are stored in the data files.

**Formula classifier** (`classify_formula()`) — assigns each headline to one of 7 types:
`number_lead` · `what_to_know` · `heres_formula` · `question` · `possessive_named_entity` · `quoted_lede` · `untagged`

**Untagged structure classifier** (`_classify_untagged_structure()`) — secondary classifier applied only to `untagged` headlines. Identifies structural sub-patterns (`how_why`, `narrative_lede`, `media_label`, `cited_source`, `named_declarative`, `short_declarative`, `other`) that don't fit the main taxonomy.

**Topic classifier** (`tag_topic()`) — assigns: `sports` · `crime` · `politics` · `business` · `lifestyle` · `nature_wildlife` · `weather` · `other`

**Subtopic classifier** (`tag_subtopic()`) — two-level: sports → football/basketball/baseball/etc; crime → violent_crime/court_legal/arrest/etc

To add a new formula pattern: add a regex case to `classify_formula()`. To add a new topic: add to `tag_topic()`. Analysis re-runs automatically on the next ingest.

---

## Statistical standards

All group comparisons use **Mann-Whitney U** (non-parametric; appropriate for skewed views distributions). Multiple comparisons are corrected with **Benjamini-Hochberg FDR** within each analysis group. Effect sizes are **rank-biserial r**. Confidence intervals are **1,000-iteration bootstrap on median ratio** (seed=42 for reproducibility).

When `statsmodels` is installed, the pipeline also runs a **Kruskal-Wallis omnibus** test on formula groups before pairwise Mann-Whitney (confirms real signal before decomposing it) and a **logistic regression** for Featured placement controlling for formula, topic, and headline length simultaneously. When `scikit-learn` is installed, keyword extraction upgrades from raw frequency to **TF-IDF**. Both degrade gracefully to baseline methods if packages are absent.

**Confidence badge criteria** (enforced by `_conf_level()`; never hardcoded manually):

| Badge | Criteria |
|-------|---------|
| High confidence | p_adj < 0.05, n ≥ 100, replicated on ≥ 2 platforms |
| Moderate | p_adj < 0.05, n ≥ 20 — OR — p_raw < 0.10, n ≥ 100 |
| Directional | p < 0.10 or untested, n ≥ 10 |

**Language standards:** Observational findings use "is associated with," "shows," or "predicts" — never causal language like "drives." Directional findings always report the actual p-value and n. Build-time rigor infrastructure enforces this at the code level via `_rigor_warn()` calls throughout `generate_site.py`.

---

## Architecture

### Pipeline

```
ingest.py
  │
  ├─ 1. Profile data files (row counts, null rates, new/dropped columns)
  ├─ 2. Diff against last run's data_profile.json — report structural changes
  ├─ 3. Archive existing docs/index.html → docs/archive/{old-slug}/ (with banner)
  ├─ 4. python3 generate_site.py --data-2026 ... --release YYYY-MM --skip-main-archive
  │       │
  │       ├─ Sheet discovery: warn if new Tarrow sheets not in known list
  │       ├─ Column validation: friendly SystemExit if expected column missing
  │       ├─ normalize(): percentile_within_cohort per publication-month cohort
  │       ├─ 9+ analyses with BH-FDR, bootstrap CIs, rank-biserial r
  │       ├─ Hero scoring: top 2 findings by effect × significance × surprise
  │       ├─ Build report: row counts, tile confidence, all audit + rigor warnings
  │       ├─ meta.json: saved to docs/archive/{slug}/ for future delta comparison
  │       ├─ docs/index.html (main site)
  │       ├─ docs/playbook/index.html (playbooks, tiles sorted by confidence)
  │       └─ docs/author-playbooks/index.html (author profiles, requires Tracker)
  ├─ 4b. python3 generate_experiment.py <each experiments/*.md>
  │       └─ Regenerates all experiment pages + index (keeps nav/theme/export in sync)
  └─ 5. git commit (docs/)
```

### Key design decisions

**`percentile_within_cohort` normalization**
Raw views accumulate over time — an article from January always outperforms one from December. All performance metrics are normalized to percentile rank within the same publication-month cohort before any comparison. A lift of 1.5× means that formula type's median article falls in a 1.5× higher monthly percentile than baseline.

**BH-FDR multiple comparison correction**
Each analysis tests multiple groups simultaneously (6 formula types, 8 SmartNews channels, etc.). Without correction, some groups would appear significant by chance. Benjamini-Hochberg FDR is applied within each analysis group.

**Hero scoring**
Rather than hardcoding which finding appears in the hero headline, each finding is scored: `effect_size × (1 / p_value) × surprise_factor`. The top 2 are used. As data grows, more powerful findings surface automatically.

**Build-time audit suite**
Six checks run on every build and print to the build report:
1. `_validate_js()` — JS syntax valid on all pages
2. `_post_build_audit()` — all required tokens (theme toggle, rethemeCharts, etc.) present on all pages
3. `_check_color_palette()` — JS `_NEON_COLORS`/`_NORM_COLORS` arrays match Python palette constants
4. `_check_formula_labels()` — `_FORMULA_LABELS` keys match `classify_formula()` return values
5. `_check_chart_legends()` — all per-bar-color charts have a legend
6. `_check_col_tooltips()` — all `<th>` column headers have a hover tooltip in `_COL_TOOLTIPS`

**Rigor infrastructure**
Four functions maintain analytical discipline at build time:
- `_conf_level(p_adj, n, n_platforms)` → consistent badge criteria across all findings
- `_require_test(section, p_adj, n_a, n_b)` → emits a build warning if a comparison lacks a significance test
- `_RIGOR_WARNINGS` → collected and printed in the build report every run
- `_check_chart_legends(figures)` → fires if any per-bar-color chart lacks a legend

**Archive coordination**
`ingest.py` is the archiving authority. It reads the `data-run` meta tag from the existing `docs/index.html` to determine the correct archive slot (the old page's own slug, not the current month). `generate_site.py` gets `--skip-main-archive` to prevent double-archiving. A `meta.json` is saved per run for future delta comparison.

**Chart color theming**
Charts are built at generate time with dark-mode (neon) colors. `_rethemeCharts(isDark)` swaps colors at runtime using `_NEON_COLORS`/`_NORM_COLORS` lookup tables. Per-bar color arrays require double-wrapping in `Plotly.restyle` (`[mc]` not `mc`) — this is intentional and correct.

**Playbook tile sorting**
Playbook tiles are built as `(conf_class, panel_id, html)` tuples and sorted by `_CONF_RANK = {"conf-high": 0, "conf-mod": 1, "conf-dir": 2}`. As confidence levels change with more data, tile order updates automatically.

**Column header tooltips**
`_COL_TOOLTIPS` in `generate_site.py` is the single source of truth for all column explanations (~70 entries). `_make_col_tooltip_js()` serializes it to JSON and injects it into every page. To add a tooltip for a new column: add one entry to `_COL_TOOLTIPS`.

**Per-author guidance**
Author playbook tiles show a "Recommended actions this round" callout with **DO:** / **TRY:** labels driven by confidence badge. DO = statistically supported (Moderate badge); TRY = directional signal. Platform routing is always included as a second item when formula is the primary signal.

---

## Developer: adding analyses and experiments

### Adding a new analysis

1. **Write the computation** — add it in `generate_site.py` in the appropriate Q-section. Use `bh_correct()`, `rank_biserial()`, `bootstrap_ci_lift()` for statistical rigor. Call `_require_test()` to register with the build-time warning system.
2. **Assign a confidence badge** — use `_conf_level(p_adj, n, n_platforms)`. Never hardcode badge levels.
3. **Add a main page tile** — add a tile `<div>` to the tile-grid section of the HTML f-string.
4. **Add a playbook tile** — add a `(conf_class, panel_id, html)` tuple to `_pb_tile_defs`. It will sort into position automatically.
5. **Add detail panels** — add both a `<div class="detail-panel">` (main page) and a `<div id="pb-N" class="pb-detail">` (playbook) with table, chart, and caveat text.
6. **Add column tooltips** — for any new `<th>` text, add an entry to `_COL_TOOLTIPS`. The build will warn if any column is missing.
7. **Add chart legends** — if the chart uses per-bar coloring, call `_lift_legend_traces()` or `_sn_legend_traces()` and set `showlegend=True`. The build will warn if missing.
8. **Run and verify** — all six audit checks must pass green in the build report.

### Adding an experiment

Create a spec file and generate the page:
```bash
python3 generate_experiment.py experiments/my-slug.md
```

Spec file format (`experiments/my-slug.md`):
```
title: Does X improve Y?
platform: Apple News
metric: views
hypothesis: ...
start_date: 2026-04-01
status: active
```

The experiment appears at `docs/experiments/my-slug/index.html` and is added to the index automatically. On every subsequent ingest, all experiment pages are regenerated to keep nav/theme/export JS in sync.

---

## File reference

### Scripts

| File | Purpose |
|------|---------|
| `ingest.py` | Monthly entry point. Profiles data, diffs against last run, archives old site, calls generator, regenerates all experiment pages, commits. |
| `generate_site.py` | Full analysis pipeline + site generator. Reads Excel files, runs all analyses, writes three HTML outputs (main, playbook, author-playbooks). Writes `data/build_summary.json` at end of every run. |
| `generate_experiment.py` | Generates individual experiment pages from `experiments/*.md` spec files and regenerates the experiment index. |
| `generate_grader.py` | Daily headline grader. Reads Sara Vallone's Google Tracker, grades last 24h of headlines via rule-based and LLM criteria, writes `docs/grader/index.html` and `docs/grader/history.json`. |
| `download_tarrow.py` | Downloads the live 2026 Google Sheet from Google Drive as XLSX using the existing service account. Called by `weekly_ingest.yml` every Monday. |
| `update_snapshots.py` | Reads `data/build_summary.json` and appends a date-stamped entry to `data/weekly_snapshots.json` for longitudinal metric tracking. |
| `run_grader.sh` | Local shell wrapper for `generate_grader.py` (legacy; Actions is now the primary runner). |
| `requirements.txt` | All Python dependencies. `pip3 install -r requirements.txt` to set up a new machine. |

### Documentation

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Autonomous workflow instructions for Claude Code — enables hands-off ingest. |
| `PLAYBOOK.md` | Scenario guide: what to do when specific data conditions change (new sheets, columns, platforms, experiments, full MSN export). |
| `REFERENCE.md` | Stable project facts: team, data sources, validated formulas, data enrichment roadmap. Updated in place. |
| `CONTEXT.md` | Current working state: phase, data status, open tasks. Updated each session. |

### Generated outputs

| Path | Contents |
|------|---------|
| `docs/index.html` | Live main analysis page. Regenerated on each run. |
| `docs/playbook/index.html` | Live editorial playbook page. Regenerated on each run. |
| `docs/author-playbooks/index.html` | Live author playbook page. Regenerated on each run (requires Tracker data). |
| `docs/experiments/index.html` | Experiment index. Regenerated on every ingest. |
| `docs/experiments/{slug}/index.html` | Individual experiment report pages. |
| `docs/grader/index.html` | Daily headline grader page. Regenerated each cron run. |
| `docs/grader/history.json` | 30-day rolling score log (date, n, avg score, top issue per day). |
| `docs/archive/YYYY-MM/` | Monthly snapshot: `index.html` (with archived banner), `data_profile.json`, `meta.json`. |
| `data/build_summary.json` | Key metric snapshot from the most recent `generate_site.py` run (8 tracked metrics). Overwritten on each run. |
| `data/weekly_snapshots.json` | Longitudinal metric log — one entry per week, date-stamped. Append-only; idempotent on same-day reruns. |

### Data files (in repo root)

| Default filename | Contents | Update cadence |
|-----------------|---------|----------------|
| `Top syndication content 2025.xlsx` | Full-year 2025: Apple News, SmartNews, MSN, Yahoo | Static — complete year |
| `Top Stories 2026 Syndication.xlsx` | 2026 YTD: Apple News, Apple News Notifications, SmartNews, Yahoo, MSN | Auto-refreshed weekly (Monday EOD) via `download_tarrow.py` |
| `Tracker Template.xlsx` | Content tracker: Author, Vertical, Word Count, Published URL — optional; enables Finding 9 | Manual |

---

## Triage guide

### `✗ Missing column 'X'` on startup
Tarrow renamed a column in the export. The error lists all available columns. Find the closest match, update the column name in `generate_site.py` in the relevant load section, re-run.

### Build report: `[sheet_discovery]` warning
A sheet appeared in the export that isn't in the known list.
- **Worth analyzing** (>50 rows, recognizable metrics): note for future pipeline work; add to `_KNOWN_SHEETS_2026` to suppress the warning.
- **Summary/pivot** (few rows): just add to `_KNOWN_SHEETS_2025` or `_KNOWN_SHEETS_2026`.

### Build report: `[col_tooltips]` warning
A table column header has no tooltip. Add the missing key and a one-sentence plain-English explanation to `_COL_TOOLTIPS` in `generate_site.py`. Key format: lowercase, spaces collapsed, en-dash → hyphen.

### Build report: `[chart_legends]` warning
A chart uses per-bar coloring but has no legend. Add `_lift_legend_traces()` or `_sn_legend_traces()` dummy traces and set `showlegend=True, legend=_LEGEND_BELOW` in the chart's `update_layout()` call.

### Row counts are lower than the last run
The export may be truncated. Check `docs/archive/*/meta.json` for prior counts. Investigate the source sheet before committing.

### Charts render blank in an archived page
Charts depend on `https://cdn.plot.ly/plotly-2.27.0.min.js`. Archives require internet to render charts. Tables render offline. Known limitation.

### Charts show wrong colors in light mode
`_rethemeCharts` swaps neon ↔ normal colors at runtime. If all bars are the same color, the `Plotly.restyle` call is likely passing a flat array — per-bar color arrays must be `[mc]` not `mc`. The `_check_color_palette()` build check catches palette mismatches.

### Export PNG/PDF shows white charts in dark mode
The export reads its background from `document.body` (not the panel element, which is transparent). If exports show white, check that `_rawBg` in `_exportPanel` is resolving correctly from `getComputedStyle(document.body)`.

### Playbook tile order changed unexpectedly
Expected — tiles sort by `_CONF_RANK` on every build. If a finding's sample size grew enough to shift its confidence level, its tile moves. The build report shows the current tile breakdown.

### Hero headline changed
Expected — hero scoring auto-selects the top 2 findings by `effect × significance × surprise`. If a specific finding should be more prominent, check its `surprise` weight in the `_hero_add()` call.

### Archive went to the wrong month folder
Pass `--release YYYY-MM` explicitly to `ingest.py`. The default is the current calendar month, which is wrong if processing a prior month's data late.

### Headline Grader shows `? Criterion` (yellow pending badge)
The LLM call returned no result for that criterion. Usually a transient Groq rate-limit or network issue. Rerun `python3 generate_grader.py --lookback 1` — pending badges typically resolve on retry.

### Headline Grader shows no 30-day history strip
`docs/grader/history.json` is missing or empty (expected on first run). The strip populates automatically after the first successful daily run commits the file.

### Grader not running daily
Check the GitHub Actions tab → `grader.yml` workflow for the last run status. Common causes: `GROQ_API_KEY` or `GOOGLE_SERVICE_ACCOUNT_JSON` secret missing/expired; workflow file has a syntax error. Use the Run Now button in the grader UI for a manual trigger.

---

## Quality suite

Run this before any push:
```bash
# Full test suite (must use python3.11 — CI runs 3.11, not local Python):
python3.11 -m pytest tests/ -v

# Grader smoke check (objective criteria only, no API calls):
python3 generate_grader.py --skip-llm --dry-run

# Syntax check via bytecode compilation (catches 3.11 f-string restrictions):
python3.11 -m py_compile generate_site.py download_tarrow.py generate_grader.py update_snapshots.py ingest.py && echo "syntax OK"
```

All three must pass before committing. Always use `python3.11` — the local Python may be 3.14+ and will not catch 3.11 f-string syntax errors that break CI.

---

### `ingest.py` committed but the site looks broken
The old site is preserved at `docs/archive/{slug}/index.html`. Run `generate_site.py` directly to debug, fix the issue, then commit again. The archive is always safe.

### A finding's confidence badge seems wrong
Check the `_conf_level()` call for that finding. Criteria: **High** = p_adj < 0.05, n ≥ 100, ≥ 2 platforms; **Moderate** = p_adj < 0.05, n ≥ 20; **Directional** = p < 0.10 or untested, n ≥ 10. If the badge doesn't match the data, the `_conf_level()` call is likely missing an argument or using `p_raw` instead of `p_adj`.
