# T1 Headline Analysis

Monthly analysis of headline and topic performance signals for McClatchy Tier 1 outlets across Apple News, SmartNews, MSN, and Yahoo. Data from Chris Tarrow's Google Sheet exports. Site generated programmatically — no manual HTML editing.

**Live site:** `docs/index.html` (GitHub Pages)
**Owners:** Pierce Williams (CSA ops lead), Sarah Price (content strategist)
**Full context:** [`REFERENCE.md`](REFERENCE.md) · [`CONTEXT.md`](CONTEXT.md)

---

## What the site does

| Page | Path | Purpose |
|------|------|---------|
| Main analysis | `docs/index.html` | 9 findings tiles with expandable detail panels, charts, and statistical tables |
| Editorial Playbooks | `docs/playbook/index.html` | Per-platform headline guidance synthesized from findings; auto-sorted by confidence level |
| Author Playbooks | `docs/author-playbooks/index.html` | Per-author formula profiles, performance percentiles, structured DO/TRY guidance (requires Tracker data) |
| Experiments | `docs/experiments/index.html` | Before/after formula tests tracked over time |
| Archive | `docs/archive/YYYY-MM/` | Full monthly snapshots; "Past analyses" link list on main page |

The main page surfaces findings as interactive tiles. Each tile has a confidence badge (`High confidence`, `Moderate`, `Directional`) derived from sample size, adjusted p-value, and replication across platforms. The hero headline is auto-selected each run by scoring every finding on effect size × significance × surprise factor — it always reflects the most statistically interesting result in the current data.

All charts include color legends. All table column headers show a plain-English tooltip on hover. Both dark and light modes are supported across all pages, with preference persisted across sessions via localStorage.

---

## Monthly update — the only command you need

Open Claude Code in this directory. Tell it the new file:

> "New Tarrow data is in my Downloads — update the site"

Claude reads `CLAUDE.md`, finds the file, runs the full pipeline, fixes any column/sheet issues autonomously, and tells you when it's ready to push. Then push from GitHub Desktop.

**If running manually:**
```bash
python3 ingest.py --data-2026 "path/to/new/file.xlsx"
# Add --release 2026-04 if processing a prior month's data late
# Add --data-2025 "path/to/file.xlsx" if the historical baseline changed
```

See [`PLAYBOOK.md`](PLAYBOOK.md) for scenario-specific guidance (new sheets, engagement columns, new platforms, experiments).

---

## Architecture

### Pipeline overview

```
ingest.py
  │
  ├─ 1. Profile data files (row counts, null rates, new columns)
  ├─ 2. Diff against last run's data_profile.json
  ├─ 3. Archive existing docs/index.html → docs/archive/{old-slug}/ (with banner)
  ├─ 4. python3 generate_site.py --data-2026 ... --release YYYY-MM --skip-main-archive
  │       │
  │       ├─ Sheet discovery: warn if new Tarrow sheets not in known list
  │       ├─ Column validation: friendly SystemExit if expected column missing
  │       ├─ normalize(): percentile_within_cohort per publication-month cohort
  │       ├─ 9+ analyses with BH-FDR, bootstrap CIs, rank-biserial r
  │       ├─ Hero scoring: picks top 2 findings by effect × significance × surprise
  │       ├─ Build report: row counts, tile confidence, rigor + audit + tooltip warnings
  │       ├─ meta.json: saved to docs/archive/{slug}/ for future delta comparison
  │       ├─ docs/index.html (main site)
  │       ├─ docs/playbook/index.html (playbooks, tiles sorted by confidence)
  │       └─ docs/author-playbooks/index.html (author profiles, requires Tracker)
  ├─ 4b. python3 generate_experiment.py <each experiments/*.md>
  │       └─ Regenerates all experiment pages + index (keeps nav/theme/export in sync)
  └─ 5. git commit (docs/)
```

### Key design decisions

**`percentile_within_cohort` as the primary metric**
Raw views accumulate over time — an article from January always looks better than one from December. All views are normalized to percentile rank within the same publication-month cohort. A lift of 1.5× means that formula's median article falls in a 1.5× higher monthly cohort percentile than baseline.

**BH-FDR multiple comparison correction**
Each analysis tests multiple groups simultaneously (6 formula types, 8 SmartNews channels, etc.). Without correction, some would appear significant by chance. Benjamini-Hochberg FDR is applied within each analysis group.

**Hero scoring**
Rather than hardcoding which findings appear in the hero headline, each finding is scored: `effect_size × (1 / p_value) × surprise_factor`. The top 2 are used. The score auto-adapts as data changes — if a formula type becomes highly significant with more data, it surfaces automatically.

**Rigor infrastructure**
Four functions maintain analytical discipline at build time:
- `_conf_level(p_adj, n, n_platforms)` → consistent badge criteria across all findings
- `_require_test(section, p_adj, n_a, n_b)` → emits a build-time warning if a comparison lacks a significance test
- `_RIGOR_WARNINGS` → collected and printed in the build report every run
- `_check_chart_legends(figures)` → fires if any per-bar-color chart lacks a legend

**Build-time audit suite**
Five checks run automatically on every build and print to the build report:
1. `_validate_js()` — JS syntax valid on all three pages
2. `_post_build_audit()` — all required tokens (theme toggle, rethemeCharts, etc.) present on all pages
3. `_check_color_palette()` — JS `_NEON_COLORS`/`_NORM_COLORS` arrays match Python palette constants
4. `_check_formula_labels()` — `_FORMULA_LABELS` keys match `classify_formula()` return values
5. `_check_chart_legends()` — all per-bar-color charts have a legend
6. `_check_col_tooltips()` — all `<th>` column headers have a hover tooltip in `_COL_TOOLTIPS`

**Chart color theming**
Charts are built at generate time with dark-mode (neon) colors. The JS `_rethemeCharts(isDark)` function swaps colors at runtime using `_NEON_COLORS`/`_NORM_COLORS` lookup tables. Per-bar color arrays require double-wrapping in `Plotly.restyle` (`[mc]` not `mc`) — this is intentional and correct.

**Playbook tile sorting**
Playbook tiles are built as `(conf_class, panel_id, html)` tuples and sorted by `_CONF_RANK = {"conf-high": 0, "conf-mod": 1, "conf-dir": 2}` before the page renders. As confidence levels change with more data, the tile order updates automatically.

**Archive coordination**
`ingest.py` is the archiving authority. It reads the `data-run` meta tag from the existing `docs/index.html` to determine the correct archive slot (the old page's own slug, not the current month). `generate_site.py` gets `--skip-main-archive` to prevent double-archiving. A `meta.json` is saved per run for future delta comparison.

**Column header tooltips**
`_COL_TOOLTIPS` in `generate_site.py` is the single source of truth for all table column explanations. `_make_col_tooltip_js()` serializes it to JSON and injects it into every page. `_check_col_tooltips()` fires a build warning for any `<th>` text not covered. To add a tooltip for a new column: add one entry to `_COL_TOOLTIPS`.

**Per-author guidance**
Author playbook tiles show a structured "Recommended actions this round" callout with explicit **DO:** / **TRY:** labels. DO = statistically supported signal (Moderate badge); TRY = directional signal. Platform routing is always included as a second item when formula is the primary signal.

---

## File reference

| File | Purpose |
|------|---------|
| `generate_site.py` | Full analysis pipeline + site generator. Reads Excel files, runs all analyses, writes three HTML outputs (main, playbook, author-playbooks). Nav via `_build_nav()`, export JS via `_make_export_js()`, tooltips via `_make_col_tooltip_js()` — all single sources of truth. |
| `ingest.py` | Monthly entry point. Profiles data, diffs against last run, archives old site, calls generator, regenerates all experiment pages, commits. |
| `generate_experiment.py` | Generates individual experiment report pages from `experiments/*.md` spec files AND regenerates the experiments index page. Uses the same `_build_nav()` / `_NAV_PAGES` pattern for consistent nav across all experiment pages. |
| `requirements.txt` | All Python dependencies. `pip3 install -r requirements.txt` to set up a new machine. |
| `CLAUDE.md` | Instructions for Claude Code — enables fully autonomous ingest when invoked via Claude. |
| `PLAYBOOK.md` | Scenario guide: what to do when specific data conditions change (new sheets, columns, platforms, experiments). |
| `REFERENCE.md` | Stable project facts: team, data sources, validated formulas, data roadmap. Updated in place. |
| `CONTEXT.md` | Current working state: phase, data status, open tasks. Updated each session. |
| `experiments/` | Experiment spec files (`.md`) and generated report pages. |
| `sessions/` | Session notes from major analysis work. |
| `docs/index.html` | Live main analysis page. Regenerated on each run. Tiles have PNG/PDF export buttons. |
| `docs/playbook/index.html` | Live editorial playbook page. Regenerated on each run. Tiles have PNG/PDF export buttons. |
| `docs/author-playbooks/index.html` | Live author playbook page. Regenerated on each run (requires Tracker data). Tiles have PNG/PDF export buttons. |
| `docs/archive/YYYY-MM/` | Monthly snapshot. Contains `index.html` (with orange archived banner), `data_profile.json`, `meta.json`. |
| `docs/experiments/index.html` | Experiment index page. Regenerated on every ingest. |

**Data files** (in repo root):

| Default filename | Contents |
|-----------------|---------|
| `Top syndication content 2025.xlsx` | Full-year 2025: Apple News, SmartNews, MSN (Dec only), Yahoo |
| `Top Stories 2026 Syndication.xlsx` | 2026 YTD: Apple News, Apple News Notifications, SmartNews, Yahoo, MSN |
| `Tracker Template.xlsx` | Content tracker with Author, Vertical, Word Count, Published URL (optional — enables Finding 9) |

---

## How the analyses work

### Findings at a glance

| # | Finding | Data | Primary test |
|---|---------|------|-------------|
| 1 | Apple News formula lift | Apple News 2025–2026 (non-Featured) | Mann-Whitney U vs. untagged baseline; BH-FDR |
| 1b | Number leads deep dive | Subset of Finding 1 | Mann-Whitney round vs. specific |
| 2 | Featured placement by formula | Apple News all | Chi-square; BH-FDR |
| 3 | SmartNews channel allocation | SmartNews 2025 (has category columns) | Mann-Whitney vs. Top feed; BH-FDR |
| 4 | Push notification CTR features | Apple News Notifications 2026 | Mann-Whitney present vs. absent; BH-FDR |
| 5 | Platform topic inversion | Apple News + SmartNews 2025 | Mann-Whitney for sports inversion; rest descriptive |
| 6 | Headline variance by topic | Apple News + SmartNews | IQR/median (descriptive) |
| 7 | Views vs. reading depth | Apple News 2025–2026 (engagement cols) | Pearson r, Spearman ρ |
| 8 | Trends over time | Apple News 2025–2026 quarterly | Longitudinal (descriptive) |
| 9 | Team performance | Tracker join → Apple News + SmartNews | Descriptive; Mann-Whitney WC Q4 vs. Q2 |

### Classifiers (all regex-based, unvalidated)

**Formula classifier** (`classify_formula()`) — assigns each headline to: `number_lead`, `what_to_know`, `heres_formula`, `question`, `possessive_named_entity`, `quoted_lede`, or `untagged`. Defined near the top of `generate_site.py`.

**Untagged structure classifier** (`_classify_untagged_structure()`) — secondary micro-classifier applied only to `untagged` headlines. Identifies structural sub-patterns (`how_why`, `narrative_lede`, `media_label`, `cited_source`, `named_declarative`, `short_declarative`, `other`) that don't fit the main taxonomy but remain informative for editorial guidance.

**Topic classifier** (`tag_topic()`) — assigns: `sports`, `crime`, `politics`, `business`, `lifestyle`, `nature_wildlife`, `weather`, or `other`.

**Subtopic classifier** (`tag_subtopic()`) — two-level: sports → `football/basketball/baseball/etc`; crime → `violent_crime/court_legal/arrest/etc`.

To add a new formula pattern: add a regex case to `classify_formula()`. To add a new topic: add to `tag_topic()`. Analysis re-runs automatically on next ingest.

---

## Adding a new analysis

1. **Write the computation** — add it in `generate_site.py` in the appropriate Q-section. Use `bh_correct()`, `rank_biserial()`, `bootstrap_ci_lift()` for statistical rigor. Call `_require_test()` to register it with the build-time warning system.
2. **Assign a confidence badge** — use `_conf_level(p_adj, n, n_platforms)` to get the right `(css_class, label)`. Never hardcode badge levels.
3. **Add a main page tile** — add a tile `<div>` to the tile-grid section of the `html` f-string.
4. **Add a playbook tile** — add a `(conf_class, panel_id, html)` tuple to `_pb_tile_defs`. It will sort into position automatically.
5. **Add detail panels** — add both a `<div class="detail-panel">` (main page) and a `<div id="pb-N" class="pb-detail">` (playbook) with table, chart, and caveat text.
6. **Add column tooltips** — for any new `<th>` text, add an entry to `_COL_TOOLTIPS` in `generate_site.py`. The build will warn if any column is missing.
7. **Add chart legends** — if the chart uses per-bar coloring (marker.color is a list), call `_lift_legend_traces()` or `_sn_legend_traces()` and set `showlegend=True`. The build will warn if any per-bar chart lacks a legend.
8. **Run and verify the build report** — all six audit checks must pass green.

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

The experiment appears at `docs/experiments/my-slug/index.html` and is added to the experiments index automatically. On every subsequent ingest, all experiment pages are regenerated automatically.

---

## Triage guide

### `✗ Missing column 'X'` on startup
Tarrow renamed a column in the export. The error lists all available columns. Find the closest match and update the column name in `generate_site.py` in the relevant load section. Re-run.

### Build report shows `[sheet_discovery]` warning
A sheet appeared in the export that isn't in the known list. Two options:
- **Worth analyzing** (>50 rows, recognizable metrics): note for Claude Code to wire into the pipeline in a future session.
- **Summary/pivot sheet** (few rows): add to `_KNOWN_SHEETS_2025` or `_KNOWN_SHEETS_2026` near the top of `generate_site.py` to suppress the warning.

### Build report shows `[col_tooltips]` warning
A table column header has no tooltip. Add the missing key and a 1-sentence plain-English explanation to `_COL_TOOLTIPS` in `generate_site.py`. The key is the normalized header text (lowercase, spaces collapsed, en-dash → hyphen).

### Build report shows `[chart_legends]` warning
A chart uses per-bar coloring but has no legend. Add `_lift_legend_traces()` or `_sn_legend_traces()` dummy traces and set `showlegend=True, legend=_LEGEND_BELOW` in the chart's `update_layout()` call.

### Row counts are lower than the last run
The export may be truncated. Check `docs/archive/*/meta.json` for prior counts. Investigate the source sheet before committing.

### Charts render blank in an archived page
Charts depend on `https://cdn.plot.ly/plotly-2.27.0.min.js`. Archives require internet to render charts. Tables render offline. Known limitation.

### Charts show wrong colors in light mode
`_rethemeCharts` swaps neon ↔ normal colors at runtime. If all bars are the same color, the `Plotly.restyle` call may be passing a flat array instead of a wrapped one — per-bar color arrays must be passed as `[mc]` not `mc`. The `_check_color_palette()` build check will catch any palette mismatch.

### Export PNG/PDF shows white charts in dark mode
The export container reads its background from `document.body` (not the panel element, which is transparent). If exports show white, check that `_rawBg` in `_exportPanel` is resolving correctly from `getComputedStyle(document.body)`.

### Playbook tile order changed unexpectedly
Expected — tiles sort by `_CONF_RANK` on every build. If a finding's sample size grew enough to change its confidence level, its tile moves. The build report shows the current tile breakdown.

### Hero headline changed
Expected — hero scoring auto-selects the top 2 findings by `effect × significance × surprise`. As data changes, different findings surface. If a specific finding should be more prominent, check its `surprise` weight in the `_hero_add()` call.

### Archive went to the wrong month folder
Pass `--release YYYY-MM` explicitly to `ingest.py`. The default is the current calendar month, which is wrong if you're ingesting a prior month's data late.

### `ingest.py` committed but the site looks broken
The old site is preserved at `docs/archive/{slug}/index.html`. Run `generate_site.py` directly to debug, fix the issue, then commit again. The archive is always safe.

### A finding's confidence badge seems wrong
Check the `_conf_level()` call for that finding. The criteria are: **High** = p_adj < 0.05, n ≥ 100, ≥ 2 platforms; **Moderate** = p_adj < 0.05, n ≥ 20; **Directional** = p < 0.10 or untested, n ≥ 10. If the badge doesn't match the data, the `_conf_level()` call is likely missing an argument or using `p_raw` instead of `p_adj`.

---

## Statistical standards

All group comparisons use **Mann-Whitney U** (non-parametric; appropriate for skewed views distributions). Multiple comparisons are corrected using **Benjamini-Hochberg FDR** within each analysis group. Effect sizes are **rank-biserial r**. Confidence intervals are **1,000-iteration bootstrap on median ratio** (seed=42 for reproducibility).

When `statsmodels` is installed (included in `requirements.txt`), the pipeline automatically runs two additional tests each build: a **Kruskal-Wallis omnibus** on formula groups before the pairwise Mann-Whitney tests (confirming there is real signal before decomposing it), and a **logistic regression** for Featured placement controlling for formula, topic, and headline length simultaneously. Results appear in the build report. When `scikit-learn` is installed, keyword extraction upgrades from raw frequency to **TF-IDF** (upweights terms distinctive to top-quartile headlines). All extended analyses degrade gracefully to baseline methods if optional packages are absent.

**Confidence badge criteria** (enforced by `_conf_level()`):

| Badge | Criteria |
|-------|---------|
| High confidence | p_adj < 0.05, n ≥ 100, replicated on ≥ 2 platforms |
| Moderate | p_adj < 0.05, n ≥ 20; OR p_raw < 0.10, n ≥ 100 |
| Directional | p < 0.10 or untested, n ≥ 10 |

**Language standards:** Observational findings use "is associated with," "shows," or "predicts" — never causal language like "drives." Directional findings always report the actual p-value and n — not just "directional only." The build-time rigor infrastructure enforces this at the code level; see `_rigor_warn()` calls throughout `generate_site.py`.

---

## Why this project exists

Justin Frame (SVP) produced a headline performance analysis on March 24, 2026. Chris Tarrow's directive: *"The narrative is being driven outside of us currently. We should be driving and documenting what we are testing and learning."* This project is the internal response — and the analytical foundation for a variant allocation model: how many AI-generated headline variants to produce per article type, by platform.

The long-term goal: `Canon article type × Distribution platform → Historical ROI → Optimal variant count`. The current work establishes the historical ROI baseline. Variant tracking instrumentation is being scoped separately to close the loop.

See [`REFERENCE.md`](REFERENCE.md) for the full data roadmap, team roster, and Justin Frame's validated formulas.
