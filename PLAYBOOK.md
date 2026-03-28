# T1 Headline Analysis — Monthly Analysis Playbook

Scenario-specific guidance for when specific data conditions change. For the standard monthly update workflow, see [`README.md`](README.md). For Claude Code automation, see [`CLAUDE.md`](CLAUDE.md).

---

## Every time new data arrives — standard flow

**The fast path:** Open Claude Code in this directory, tell it the new file. It handles everything automatically (find file → run ingest → fix any column/sheet issues → commit). You push.

**If running manually:**
```bash
python3 ingest.py --data-2026 "New file.xlsx" --note "brief description"
# Add --release YYYY-MM if processing a prior month's data late
# Add --data-2025 "file.xlsx" if the historical baseline changed
```

**After the build completes, read the build report and check these 5 things:**

Open `docs/index.html` in a browser:

1. **Hero numbers** — do the three stat boxes still read sensibly?
   - "What to know" Featured rate should be near 62% unless editorial behavior changed
   - SmartNews Local lift should be near 108× (stable unless data structure changed)
   - "Exclusive" CTR lift should be near 2.49× (may drift as Guthrie story ages out)

2. **Formula chart (Finding 1)** — are all 7 formula types still visible? If a formula dropped
   to n=0 in the new data, it disappears silently.

3. **Platform separation (Finding 5)** — does Sports still lead Apple News? Does Local/Civic
   still lead SmartNews? These rankings can shift month-to-month. If they flip materially,
   note it — the hero headline auto-updates but a session to assess the shift may be warranted.

4. **Variance chart (Finding 6)** — do the IQR/median values look in the same ballpark? Extreme
   outliers (cv > 50 on Apple News) suggest a data anomaly, not a real finding.

5. **Caveat row counts** — scan the grey caveat lines at the bottom of each finding.
   Do the n= numbers match the build report?

**If build report shows scenario warnings** (new sheets, columns newly populated, row count jumps): follow the relevant scenario section below, then re-verify before pushing.

**When everything looks clean:** push from GitHub Desktop.

---

## Scenario 1: Standard monthly update

**What changed:** Same file structure, more rows. No new columns or sheets.
Ingest will say "No structural changes detected."

**What updates automatically:** Everything. All 7 findings recompute from the new data.

**Additional checks beyond the universal Step 3:**
- Check if Here's/possessive formula sample sizes crossed n≥30 or n≥100 (see thresholds table)
- If n crossed a threshold, run: *"Re-run Q1 formula lift analysis. Flag whether Here's or
  possessive named entity now have statistical significance."* Skills: `polars`

---

## Scenario 2: Apple News notification dataset grows

**What changed:** More rows in the Notifications sheet. Possibly 2025 full-year added.

**Why it matters:** Q5 CTR findings (possessive 1.86×, exclusive 2.49×) are based on Jan–Feb
2026 only (n=351). More data can validate or shift these findings — especially whether the
Guthrie serial story cluster still dominates the top CTR decile.

**Analysis steps:**
1. Run ingest — site auto-updates with new n
2. In a new Claude Code session, paste:
   > "Re-run Q5 notification CTR analysis with the updated dataset. Check: (1) does the
   > possessive named entity lift (target: 1.86×) hold? (2) does exclusive tag lift (target:
   > 2.49×) hold or is it now lower with diluted Guthrie effect? (3) what's the new Guthrie
   > cluster share of top-10 CTR articles? Use polars for the analysis."
3. If findings shift materially, update the site prose and regenerate

**Skills:** `polars` → `data-analysis` → `interactive-report-generator`

---

## Scenario 3: Engagement columns newly populated (Apple News 2026 or Notifications)

**What changed:** Columns that were >50% null are now populated. Ingest will flag these.

**Why it matters:** The views ↔ active time independence finding (Finding 7) is currently
2025-only. If 2026 engagement columns are filled, we can extend it to 2026 and check whether
the r≈0 relationship holds across news cycles.

**Analysis steps:**
1. Run `excel-analysis` skill on the new file to profile the newly populated columns:
   > "Profile the Apple News 2026 sheet. List all columns that now have <10% nulls that
   > previously had >50% nulls. What do these columns measure?"
2. Then extend Finding 7:
   > "Extend the views vs. active time analysis to Apple News 2026 data. Does the
   > independence finding (Pearson r≈0) replicate? Are subscriber/non-subscriber active
   > time patterns consistent with 2025?"
3. If confirmed, update generate_site.py to include 2026 engagement data in Finding 7

**Skills:** `excel-analysis` → `polars` → `data-analysis`

---

## Scenario 4: SmartNews 2026 category columns restored

**What changed:** 2026 SmartNews export goes from 7 columns back to 32 category columns.

**Why it matters:** Finding 3 (Local 108× lift) is 2025-only because the 2026 export
lacked category breakdown. With it restored, we can check whether the channel allocation
mismatch persists in 2026 and track whether the Entertainment over-index is improving.

**Analysis steps:**
1. Run ingest — Finding 3 site data is still 2025; this is new analysis
2. In Claude Code:
   > "Run Q4 SmartNews channel ROI analysis on the 2026 SmartNews data. Compare:
   > (1) Local vs. Top feed lift — does 108× replicate or change?
   > (2) Entertainment % of volume — has it come down from 35.9%?
   > (3) Any new channels or structural changes vs. 2025?
   > Use polars. If findings are materially different from 2025, add a '2025 vs. 2026'
   > comparison section to the site."
3. Update generate_site.py to load 2026 SmartNews categories if analysis warrants it

**Skills:** `excel-analysis` → `polars` → `data-analysis` → `interactive-report-generator`

---

## Scenario 5: MSN full-year data arrives

**What changed:** MSN sheet row count more than doubles (currently December only, n≈1,200).

**Why it matters:** Finding 5 (platform separation) currently excludes MSN from the
topic performance index because December-only data is seasonally skewed. Full-year MSN
unlocks a three-platform topic comparison and validates the keyword overlap finding.

**Analysis steps:**
1. Run ingest — ingest.py will flag the row count jump
2. Profile the new MSN data:
   > "Profile the updated MSN sheet. Confirm it's now full-year. What's the date range?
   > What are the key performance columns? Run the topic classifier and show topic
   > distribution vs. Apple News and SmartNews."
3. Extend Finding 5:
   > "Add MSN to the Q3 topic × platform analysis. Compute topic performance index for
   > MSN (median views / MSN overall median). Add MSN bars to the platform separation
   > chart. Does MSN align more with Apple News or SmartNews in topic preference?"
4. Add MSN to the exclusivity table with full-year data

**Skills:** `excel-analysis` → `polars` → `data-analysis` → `interactive-report-generator`

---

## Scenario 6: Deliberate experiment — before/after cohort

**What changed:** You deliberately changed something (formula guidance, editorial brief,
CSA prompt) and want to measure whether it worked.

**What you need:**
- A clear change date (e.g., "we told editors to use 'What to know' starting April 1")
- The metric to measure (Featured rate, CTR, median views)
- Enough post-change data (ideally 4+ weeks, n≥50 in both periods)

**Analysis steps:**
1. Define the experiment in `experiments/` (see below)
2. In Claude Code:
   > "Run a before/after cohort comparison for [experiment name]. Before period:
   > [date range]. After period: [date range]. Metric: [Featured rate / CTR / median views].
   > Filter to [formula type / platform / topic if relevant]. Use Mann-Whitney U for
   > significance. Report: n before/after, median before/after, lift, p-value, and
   > whether sample size is adequate for a reliable conclusion."
3. If significant, document in the site as a new finding with a date label

**Skills:** `code-data-analysis-scaffolds` (design) → `polars` (analysis) → `data-analysis` (chart)

**Experiment spec format** (`experiments/SLUG.md`):
```
# Experiment: [Name]
Start date: YYYY-MM-DD
Change: [What was changed]
Hypothesis: [What we expect to see]
Metric: [Primary metric]
Platform: [Apple News / SmartNews / Notifications]
Filter: [formula type / topic / outlet if applicable]
Status: active / complete
Result: [filled in after analysis]
```

---

## Scenario 7: New platform data appears

**What changed:** A new sheet or workbook contains data from a platform not yet analyzed
(e.g., Yahoo full engagement data, Google Discover, MSN broken out further).

**Analysis steps:**
1. Run `excel-analysis` skill to profile the new sheet:
   > "Profile the new [platform] sheet. What columns are present? What are the key
   > performance metrics? What's the date range and n? How does it compare structurally
   > to the Apple News and SmartNews sheets we already analyze?"
2. Run `code-data-analysis-scaffolds` to plan the analysis:
   > "Design an EDA scaffold for [platform] data. Questions to answer: (1) topic
   > distribution, (2) performance spread, (3) headline formula distribution,
   > (4) how it fits into the platform separation finding."
3. Add to generate_site.py if it warrants a new finding

**Skills:** `excel-analysis` → `code-data-analysis-scaffolds` → `polars` → `data-analysis`

---

## Skill pipeline quick reference

| Task | Skills (in order) |
|------|-------------------|
| Profile a new data file | `excel-analysis` |
| Plan a new analysis | `code-data-analysis-scaffolds` |
| Detect non-obvious signals | `data-sleuth` |
| Run group comparisons, classifiers, cross-tabs | `polars` |
| Build McKinsey-quality charts | `data-analysis` |
| Generate/update the site | `interactive-report-generator` |
| Heavy joins or aggregations | `data-analysis-sql` (fallback) |

## Key thresholds to watch

| Finding | Current value | Watch for |
|---------|--------------|-----------|
| Here's formula lift | 2.97× (n=16, not sig) | Sig when n≥30 |
| Possessive formula lift | 1.94× (n=75, not sig) | Sig when n≥100 |
| WTN Featured rate | 62% (n=21) | Shifts if editorial guidance changes |
| Exclusive CTR lift | 2.49× (n=16) | May dilute as Guthrie story ages |
| Sports #1 Apple News | 2.13× | Check each month — topic ranking can shift |
| Local/Civic #1 SmartNews | 1.99× | Check each month |
