# T1 Headline Analysis

Static GitHub Pages dashboard tracking headline and topic performance across Apple News, SmartNews, MSN, and Yahoo for McClatchy Tier 1 outlets. The site is generated fully programmatically from Tarrow's export data — no manual HTML editing.

**Live site:** `docs/index.html` (GitHub Pages)
**Owners:** Pierce Williams (CSA ops lead) · Sarah Price (content strategist)
**Full context:** [`REFERENCE.md`](REFERENCE.md) · [`CONTEXT.md`](CONTEXT.md) · [`PLAYBOOK.md`](PLAYBOOK.md)

> *"The narrative is being driven outside of us currently. We should be driving and documenting what we are testing and learning."* — Chris Tarrow, March 24, 2026

---

## Quickstart

### Weekly ingest (automatic)

The 2026 sheet auto-refreshes every **Monday at 8 PM CDT** via GitHub Actions (`.github/workflows/weekly_ingest.yml`). No local action required unless Tarrow has renamed columns or added sheets.

### Monthly deep ingest (manual, via Claude Code)

Open Claude Code in this directory and say:
> "New Tarrow data is in my Downloads — update the site"

Claude reads `CLAUDE.md`, locates the file, runs the full pipeline, fixes any column-rename or new-sheet warnings autonomously, and tells you when it's ready to push.

**Or manually:**
```bash
python3 ingest.py --data-2026 "path/to/new/file.xlsx"
# Add --release 2026-04 if ingesting a prior month's data late
```

### Running the grader locally

```bash
# Full run (last 24h, with Groq LLM):
GROQ_API_KEY=... GOOGLE_SERVICE_ACCOUNT_FILE=~/.credentials/pierce-tools.json python3 generate_grader.py

# Wider lookback:
python3 generate_grader.py --lookback 7

# Objective criteria only, no LLM calls:
python3 generate_grader.py --skip-llm

# Preview without writing files:
python3 generate_grader.py --dry-run
```

### Quality suite

Run before every push:
```bash
# Full test suite — must use python3.11 (CI runs 3.11, not local Python)
python3.11 -m pytest tests/ -v

# Linter
ruff check .

# Syntax check (catches 3.11 f-string restrictions)
python3.11 -m py_compile generate_site.py download_tarrow.py generate_grader.py update_snapshots.py ingest.py && echo "syntax OK"

# Grader smoke check (no API calls)
python3 generate_grader.py --skip-llm --dry-run
```

All checks must pass before committing. Always use `python3.11` — local Python may be 3.12+ and will not catch CI-breaking f-string syntax errors.

### Setup (new machine)

```bash
pip3 install -r requirements.txt
```

Optional packages that unlock additional analyses:
```bash
pip3 install statsmodels polars scikit-learn pingouin
```

---

## What this site shows

The pipeline delivers **13 findings** about headline patterns and platform performance:

| # | Finding |
|---|---------|
| 1 | Apple News headline formula lift (Mann-Whitney; BH-FDR) |
| 1b | Round vs. specific numbers in number-lead headlines |
| 2 | Featured placement by formula type |
| 3 | SmartNews category ROI vs. volume |
| 4 | Push notification CTR by headline feature |
| 5 | Topic × platform ranking inversion (Apple News vs. SmartNews) |
| 6 | Headline variance by topic |
| 7 | Views vs. reading depth independence |
| 8 | Formula lift trends over time |
| 9 | Team/author performance (requires Tracker data) |
| HL | Headline length quartile vs. views percentile |
| Video | MSN video completion by sports flag (data loaded; tile paused) |
| Snapshots | Longitudinal metric tracker (≥3 weeks to render trend lines) |

Each finding carries a confidence badge (`High confidence`, `Moderate`, or `Directional`) derived automatically from sample size, adjusted p-value, and platform replication.

**Note:** `SHOW_MSN_TILE = False` in `generate_site.py` — MSN data is loaded and computed (used for platform inversion and topic analyses) but the MSN tile is hidden per Sarah Price feedback (2026-04-08). Re-enable by flipping the flag.

### Headline Grader

A separate pipeline runs **daily at 10 AM CDT** via GitHub Actions (`.github/workflows/grader.yml`). It reads Sara Vallone's live Google Tracker, grades the last 24 hours of headlines against **15 criteria** in four tiers, and writes `docs/grader/index.html` with a 30-day rolling score history.

Grading uses Groq (`llama-3.3-70b-versatile`) for LLM criteria and regex for rule-based criteria. Platform-aware length scoring: AN 90–120 chars, SN 70–90 chars.

A **Run Now** button in the grader UI triggers a manual run. First use requires a fine-grained GitHub PAT (actions:write scope). Passcode: **8812**.

### Author playbooks

`docs/author-playbooks/index.html` shows per-author formula profiles, performance percentiles, and structured DO/TRY guidance. Populated when `Tracker Template.xlsx` is present (requires a content tracker join). Author→vertical mapping in `generate_grader.py::AUTHOR_VERTICAL`.

### Experiments

`docs/experiments/index.html` lists before/after formula experiments. Each experiment has a spec file at `experiments/{slug}.md`. All experiment pages are regenerated on every ingest to keep nav/theme/export JS in sync.

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
  │       ├─ 13 analyses with BH-FDR, bootstrap CIs, rank-biserial r
  │       ├─ Hero scoring: top 2 findings by effect × significance × surprise
  │       ├─ Build report: row counts, tile confidence, all audit + rigor warnings
  │       ├─ docs/index.html (main site)
  │       ├─ docs/playbook/index.html (editorial playbooks, sorted by confidence)
  │       └─ docs/author-playbooks/index.html (author profiles, requires Tracker)
  ├─ 4b. python3 generate_experiment.py <each experiments/*.md>
  ├─ 4c. python3 generate_style_guide.py
  └─ 5. git commit (docs/)
```

### Key design decisions

**`percentile_within_cohort` normalization** — Raw views accumulate over time. All metrics are normalized to percentile rank within the same publication-month cohort before comparison.

**BH-FDR multiple comparison correction** — Applied within each analysis group (6 formula types, 8 SmartNews channels, etc.).

**Hero scoring** — `effect_size × (1 / p_value) × surprise_factor`. Top 2 findings surface automatically as data grows.

**Build-time audit suite** — Six checks on every build: JS syntax, required page tokens, color palette consistency, formula label consistency, chart legends, and column tooltip coverage. Warnings printed in the build report.

**OPPORTUNITY_MAP** — `ingest.py` diffs the new data profile against the previous run and emits suggested analyses when structural changes are detected (new sheets, unlocked columns, dataset growth).

**Archive coordination** — `ingest.py` is the archiving authority. It reads the `data-run` meta tag from the existing `docs/index.html` to determine the correct archive slot. `generate_site.py` gets `--skip-main-archive` to prevent double-archiving.

### GitHub Actions

| Workflow | File | Schedule | What it does |
|----------|------|----------|--------------|
| Weekly Site Refresh | `weekly_ingest.yml` | Monday 8 PM CDT | Downloads 2026 sheet, runs `generate_site.py`, updates snapshots, commits |
| Headline Grader | `grader.yml` | Daily 10 AM CDT | Runs `generate_grader.py`, commits `docs/grader/` |

Both workflows use Python 3.11 and run the smoke test suite before any data work.

**Required GitHub Actions secrets:**

| Secret | Purpose |
|--------|---------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Base64-encoded service account JSON. Encode: `base64 -i ~/.credentials/pierce-tools.json \| pbcopy` |
| `GROQ_API_KEY` | Groq API key for LLM headline evaluation |

### File reference

| File | Purpose |
|------|---------|
| `ingest.py` | Monthly entry point. Profiles, diffs, archives, regenerates, commits. |
| `generate_site.py` | Full analysis pipeline + site generator. Writes three HTML outputs + `data/build_summary.json`. |
| `generate_grader.py` | Daily headline grader. Reads Google Tracker, grades headlines, writes `docs/grader/`. |
| `download_tarrow.py` | Downloads 2026 Google Sheet as XLSX via Drive API. Called by `weekly_ingest.yml`. |
| `generate_experiment.py` | Generates individual experiment pages from `experiments/*.md` spec files. |
| `generate_style_guide.py` | Generates `docs/style-guide/index.html` — shareable confirmed-rules 1-pager. |
| `update_snapshots.py` | Appends latest build metrics to `data/weekly_snapshots.json` for longitudinal tracking. |
| `tests/smoke_test.py` | 21 tests: compile checks, f-string safety scan, helper function unit tests. |
| `requirements.txt` | All Python dependencies. |
| `CLAUDE.md` | Autonomous workflow instructions for Claude Code. |
| `PLAYBOOK.md` | Scenario guide: what to do when data conditions change. |
| `GOVERNOR.md` | Stakeholder focus, active probing queue, known data quirks — briefed at every ingest. |

### Generated outputs

| Path | Contents |
|------|---------|
| `docs/index.html` | Live main analysis page. |
| `docs/playbook/index.html` | Editorial playbooks, sorted by confidence. |
| `docs/author-playbooks/index.html` | Per-author formula profiles and DO/TRY guidance. |
| `docs/experiments/index.html` | Experiment index. |
| `docs/grader/index.html` | Daily headline grader. |
| `docs/grader/history.json` | 30-day rolling score log. |
| `docs/archive/YYYY-MM/` | Monthly snapshots with archived banner. |
| `data/build_summary.json` | Key metrics from the most recent run (overwritten each run). |
| `data/weekly_snapshots.json` | Longitudinal metric log — one entry per week, append-only. |

---

## Post-build verification checklist

After every build, verify these five things before pushing:

1. **Hero numbers** — "What to know" Featured rate: expect ~62%; SmartNews Local lift: ~108×; "Exclusive" CTR lift: ~2.49×.
2. **Formula chart (Finding 1)** — all 7 formula types visible? A formula at n=0 disappears silently.
3. **Platform separation (Finding 5)** — Sports still leading Apple News? Local/Civic still leading SmartNews?
4. **Variance chart (Finding 6)** — IQR/median values in same ballpark? Extreme cv > 50 on Apple News suggests a data anomaly.
5. **Caveat row counts** — scan grey caveat lines at the bottom of each finding. n= numbers should match the build report.

---

## Triage guide

**`✗ Missing column 'X'`** — Tarrow renamed a column. The error lists available columns. Update the column name in `generate_site.py` in the relevant load section.

**`[sheet_discovery]` warning** — A new sheet appeared. If >50 rows and recognizable metrics, note for future work; add to `_KNOWN_SHEETS_2026` to suppress.

**`[col_tooltips]` warning** — A table column has no tooltip. Add to `_COL_TOOLTIPS` in `generate_site.py`. Key: lowercase, spaces preserved, en-dash → hyphen.

**`[chart_legends]` warning** — A per-bar-color chart has no legend. Add `_lift_legend_traces()` or `_sn_legend_traces()` traces with `showlegend=True`.

**Row counts lower than last run** — Export may be truncated. Check `docs/archive/*/meta.json` for prior counts before committing.

**Grader not running daily** — Check GitHub Actions → `grader.yml` for last run status. Common causes: expired `GROQ_API_KEY` or `GOOGLE_SERVICE_ACCOUNT_JSON` secret; workflow syntax error.

**`? Criterion` (yellow badge) in grader** — Transient Groq rate-limit. Rerun `python3 generate_grader.py --lookback 1`.

**Archive went to wrong month folder** — Pass `--release YYYY-MM` explicitly to `ingest.py`.

---

## Roadmap

### Near-term (no new data required)

- NLP topic classifier on headline text — removes dependency on upstream category tagging
- Serial installment story detector — this is a distinct high-CTR category worth separating
- Outlet-level performance segmentation by T1 publication (Miami Herald vs. Charlotte Observer vs. others)
- Headline formula classifier extension — auto-classify all push notification text

### Data gaps to close (ask Tarrow)

| Priority | Gap | Why it matters |
|----------|-----|---------------|
| High | MSN full-year 2025 (currently Dec only) | Can't do temporal MSN analysis |
| Medium | Apple News Notifications 2025 | Would validate CTR lift findings across full news cycle |
| Low | Yahoo Content Viewers 2026 (82% null) | Unique reach metric currently unusable |

### Snowflake integration (blocked)

**Author playbook upgrade** — The current author playbook joins Tracker data to syndication performance by URL/headline fuzzy match. A Snowflake join via canonical article ID would be dramatically cleaner and unlock variant-count → ROI correlation.

**Blocker:** Chad Bruton is setting up the GitHub → Snowflake connection. No action needed until that pipeline is live. Once available: replace the Tracker join in `generate_site.py` with a Snowflake query keyed on Cluster ID, and expose variant count as the dependent variable in the allocation model.

### Variant allocation model (long-term)

> Canon article type × Distribution platform → Historical ROI → Optimal variant count

The current pipeline establishes the historical ROI baseline per article type × platform. Closing the loop requires: (1) Snowflake join for canonical article IDs, (2) variant count per canon article, (3) article type tag at publish time. The instrumentation work is tracked in `REFERENCE.md`.
