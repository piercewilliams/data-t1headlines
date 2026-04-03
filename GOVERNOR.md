# Analysis Governor
*Last updated: 2026-04-03 — Read at every analysis session and every ingest event.
Apply both parts without exception. Propose updates at the end of every session.*

---

## PART 1 — RELEVANCE

### Stakeholder Focus
*Replace this section after each meaningful stakeholder interaction.*

**Period:** 2026-04 (updated 2026-04-03)

**Primary — Sarah Price (content strategist, co-analyst)**
- Actionable headline formulas for Apple News and SmartNews editorial teams
- Character length specifics with data backing (precise numbers, not ranges)
- Formula avoidance rules (what NOT to do, stated directly)
- Cross-platform divergences (what works one place, hurts another)
- The team has paused syndication format variation — headline-only findings only
- Sarah reviews the site tiles and gives feedback on usefulness; her feedback is the primary calibration signal

**Secondary — Chris Palo / Chris Tarrow**
- High-level narrative: what are we learning, what should we test
- Long-term: variant allocation model (article type × platform → optimal variant count)
- Data quality and coverage improvements (Tarrow)

**Out of scope (do not analyze without explicit ask):**
- Thumbnail, image, video content (no data in pipeline)
- Platform structural/technical features (feed format, ad units, paywall) — not editorial's call
- Non-T1 outlet content
- SEO / Google Discover signals (separate workstream)

---

### Confirmed Interesting Patterns
*What has landed well — the type of insight, not just the specific finding.
Updated as Sarah gives tile feedback. Format: [date] | [type] | [why it landed] | [signal source]*

- 2026-04-03 | **Contradiction of conventional wisdom** | "What to Know" hurts on SmartNews — opposite of what the format guide assumed. Raw p=0.046; note that at k=7 tests the Bonferroni threshold is α/7=0.0071, so this is **directional** by strict multiple-comparisons standards, not significant. Still the strongest formula signal in the SmartNews data and directionally robust. Sarah reacted positively to format guide evidence report. | Inferred from Sarah's "fantastic" response to the analysis
- 2026-04-03 | **Platform-specific avoidance rule** | Questions hurt on both Apple News AND SmartNews. Directly actionable: stop doing this. | Inferred from format guide meeting
- 2026-04-03 | **Precise character count sweet spot** | "70–90 chars on SmartNews, 90–120 on Apple News" with actual top-performer medians. More specific than Apple's own published guidance. | Sarah confirmed character count is an editorial priority
- 2026-04-03 | **Notifications as the highest-signal channel** | Formula choice has 2–5× larger effect on notification CTR than on views. Direct editorial lever. | Inferred from Sarah's interest in push notifications guidance
- 2026-04-03 | **Editorial curation vs. organic algorithm divergence** | Apple editors over-index questions for featured; algorithm penalizes them. Nuanced and non-obvious. | Novel finding from format guide analysis

---

### Confirmed Low-Signal Areas
*Do not re-probe unless context changes. Reason logged so future sessions can make an informed override.*

| Area | Why low-signal | Override condition |
|------|---------------|-------------------|
| SmartNews 2026 formula analysis | Domain-aggregated only, not article-level — formula/length tests invalid | Tarrow provides article-level 2026 SN export |
| Yahoo formula/topic analysis | AOL split created data discontinuity; low n | Clean full-year Yahoo dataset |
| MSN formula analysis by type | n<30 per formula group after T1 filter (113 rows total) | MSN dataset grows to 500+ rows |
| Politics-specific findings | EXCLUDE_POLITICS=True; T1 team doesn't write politics | Team asks explicitly |
| Year-over-year trend analysis | Time series too gappy (Jan–Feb 2026 incomplete) until Q4 2026 | 9+ months of solid monthly data |
| Subtopic tables (sports/biz/pol) | Standing rigor warning — Mann-Whitney not yet implemented | MW tests added to generate_site.py |
| Tracker-only author analysis | Tracker data not always current; findings scope narrow | Tracker explicitly provided + confirmed current |
| Topic performance rankings without actionable hook | Sarah said topic rankings alone aren't useful without editorial action attached | Ranking clearly tied to a decision (e.g., "deprioritize this vertical for Apple News") |

---

### Active Probing Queue
*Questions to explore on the next analysis run even if not explicitly asked.
Priority: HIGH = run next ingest; MED = run when data supports; LOW = backlog.*

| Priority | Question | Rationale | Data available? |
|----------|----------|-----------|-----------------|
| HIGH | Does character length interact with formula type on Apple News? (e.g., does possessive named entity need to be longer to work?) | If yes, gives editors compound guidance: formula + length together | Yes — Apple News 2025+2026, formula classified, char count computable |
| HIGH | What is the notification CTR sweet spot for character length? | We tested formula vs CTR but not length vs CTR for notifications | Yes — Notifications 2025+2026 with CTR |
| MED | Is the Apple News featured/organic tension (editors favor questions, algorithm doesn't) stable across 2025 vs. 2026 separately? | If it's shifting, the guide guidance needs to shift too | Yes — can split by year |
| MED | Do possessive named entity headlines perform differently by topic on Apple News? | Low overall n (117) but if clustered in sports/crime it may be masking a strong within-topic signal | Yes — Apple News 2025+2026, topic-tagged |
| MED | Does number-lead headline performance on SmartNews vary by number type? (count-list vs. dollar amount vs. percentage) | Number leads are the only SN formula with positive trend — knowing which type helps | Yes — classify_number_lead() already in generate_site.py |
| LOW | Notification CTR by send hour — is there a time-of-day pattern beyond the existing Finding 12? | Sarah's team controls send timing; actionable if effect is large | Yes — Notifications 2025+2026 have send time |
| LOW | Character count vs. CTR interaction: do longer notifications hurt more than short ones, or does formula account for all of it? | If length effect exists independently of formula, adds a second actionable lever | Yes |

---

### What "Interesting" Means for This Audience
*The calibration standard. Updated as feedback accumulates. More durable than a list of specific findings.*

**Sarah responds well to:**
1. Rules that are directly writable into a style guide ("do X", "avoid Y on platform Z")
2. Findings that contradict what someone would assume (especially contradictions of published platform guidance)
3. Numbers precise enough to put in a document (not "longer is better" — "90–120 chars")
4. Cross-platform divergences where the same action has opposite effects
5. Findings about what to *avoid* — more immediately actionable than lift findings

**Sarah does not respond to:**
1. Topic performance rankings without a directly attached editorial action
2. Findings that require data we don't have yet (variant tracking, Amplitude PV data)
3. Trend analysis when the time series is too short to be reliable
4. Findings scoped to platforms/verticals her team doesn't control or write for

**Chris responds well to:**
1. Narrative framing: what story does the data tell about what we should be doing differently
2. Validation that the analysis is building toward the variant allocation model
3. Evidence that findings are specific and non-obvious (not "platforms differ")

---

## PART 2 — RIGOR

### Required Fields for Every Reported Finding
*A finding that cannot fill in all fields below is not ready to present.
Report it as "incomplete / cannot fully test" — never paper over gaps with inference.*

```
Source:        [sheet name] + [column name] + [filters applied] + [n after all filters]
Test:          [which statistical test] + [why appropriate for this data type]
Result:        [test statistic U or t] + [exact p-value] + [effect size r or Cohen's d] + [CI if available]
Baseline:      [comparison group name] + [that group's n] + [that group's median]
Language tier: [significant (p<0.05) / directional (p<0.10) / no detectable difference (p≥0.10)]
Scope:         [what platform, year range, outlet scope this does and does not cover]
```

Every number that appears in prose must trace to one of these fields. If it can't, it doesn't appear.

---

### Statistical Method Requirements

**Test selection:**
- Views, CTR, and engagement data are right-skewed — **always Mann-Whitney U**, never t-test, unless normality is explicitly tested and confirmed (print Shapiro-Wilk result if claiming normality)
- For proportions (e.g., % featured): chi-squared or Fisher's exact depending on cell counts
- For correlation between two continuous variables: Spearman (not Pearson) unless normality confirmed
- For logistic outcomes (featured vs. not): logistic regression when controlling for confounders

**Reporting requirements:**
- Always report median as the primary statistic for skewed distributions; mean may be included as secondary with explicit note that distribution is skewed
- Always report both the test statistic (U) and the exact p-value — not just "p<0.05"
- Always report rank-biserial correlation r as effect size for Mann-Whitney results
- Effect size language: r<0.1 = "negligible", r=0.1–0.3 = "small", r=0.3–0.5 = "medium", r>0.5 = "large"
- n<30 per group: flag as "preliminary — interpret cautiously" and do not present as a confirmed finding
- Multiple comparisons: when running ≥5 tests in a family (e.g., 7 formula types vs. baseline), report raw p-values AND note the Bonferroni-corrected threshold α/k in the finding

**Normalization:**
- Always normalize views within cohort (year × sheet) before any cross-cohort comparison
- Skipping normalization is a protocol violation — do not compare raw 2025 Apple News views to raw 2026 Apple News views
- State the normalization method used (z-score or percentile rank) in the Source field

---

### Language Precision Standards

| Word/phrase | Permitted when | Prohibited when |
|-------------|---------------|-----------------|
| "significantly" | p<0.05 (stated) | p≥0.05 |
| "directionally" / "trends toward" | p<0.10 | p≥0.10 |
| "no detectable difference" | p≥0.10 | Never say "performs similarly" — that implies equivalence we haven't tested |
| "confirms" | Hypothesis stated before analysis ran | Post-hoc finding — use "suggests" |
| "causes" / "leads to" / "drives" | Never — observational data only | Always — use "associated with" or "correlates with" |
| "the data shows X" | X is a direct read from a computed output | X is an inference not backed by a run test |
| "Apple News" | Findings from the Apple News views sheet | Findings from the Apple News Notifications sheet — these are different surfaces |

**Featured pick findings require this explicit distinction:**
> "Apple's editorial team selected these articles for featured placement at X× the baseline rate. This does not mean the formula generates higher organic views — the featured boost inflates view counts for selected articles. Organic algorithmic performance and editorial curation are reported separately."

---

### Anti-Hallucination Rules

1. **Never report a specific number without having computed it in the current session.** Prior-session numbers from the site, CONTEXT.md, or memory may be cited as context but must be labeled "from prior run — may reflect different data" and not re-reported as fresh computation.

2. **SmartNews 2026 is domain-aggregated, not article-level.** Formula, character-length, and topic analysis on SmartNews 2026 is invalid. If asked, report "cannot test at article level on 2026 SmartNews data — article-level analysis uses 2025 only (n=38,213)."

3. **Verify baseline key before any formula comparison.** `classify_formula()` returns `"untagged"` (not `"other"`, not `"none"`, not `"standard"`). A mismatch silently empties the baseline group. Always confirm baseline group has the expected n before running tests.

4. **Verify metric column before MSN analysis.** MSN analysis uses raw `"Pageviews"` column, not the normalized `percentile_within_cohort` column (range 0–1). Using the wrong column produces medians near zero that look like failures.

5. **Data holes affect date ranges.** Jan–Feb 2026 Tarrow data had incomplete polls. The effective solid date range for 2026 longitudinal analysis is March 2026 onward. When citing "2026 data," report the actual row distribution across months.

6. **Apple News engagement columns are 2026-only.** Active time, saves, and shares are not populated in the 2025 Apple News sheet. Do not run combined 2025+2026 engagement analysis — use 2026 Apple News only and note the limited time range.

7. **ANP data scope.** Apple News Publisher (ANP) data covers Jan–Feb 2026 only (March pending). Do not extrapolate ANP findings to 2025 behavior.

8. **T1 scope.** All findings scope to McClatchy T1 outlets only. Never generalize to "publishers," "news organizations," or "Apple News performance" in the abstract.

9. **Notifications ≠ Apple News.** Notification CTR findings do not transfer to Apple News views findings. These are different user actions on different surfaces with different mechanics. Always name the surface explicitly.

---

### Known Data Quirks
*Specific anomalies and edge cases discovered in this dataset. Updated as new quirks surface.*

| Quirk | Sheet | Effect if ignored | Fix |
|-------|-------|------------------|-----|
| `classify_formula()` returns `"untagged"` not `"other"` | All | Baseline group empty; all formula comparisons silently invalid | Verify baseline group n before running tests |
| MSN raw sheet: US Weekly dominates (160 of 354 rows) | 2026 MSN | Formula analysis inflated by single publisher | Apply `_MSN_T1_EXCLUDE` brand filter; confirm 113 rows after filter |
| Apple News 2026 has engagement columns; 2025 does not | Apple News | Mixed-year engagement analysis produces mostly-null results | Engagement analysis: 2026 only |
| Notification CTR is raw (not normalized) | Notifications | Direct cross-year comparison inflated if CTR baselines shifted | Normalize within year before cross-year notification analysis |
| Apple News views column name has changed historically | Apple News | Column not found; analysis silently fails | Always print column names first; confirm views column before analysis |
| SmartNews 2025 has a small number of extreme-view outliers (politics) | 2025 SmartNews | Mean views misleadingly high; skews formula lift if not excluded | Use median; confirm `EXCLUDE_POLITICS=True` is applied |
| Yahoo 2026: 82% null on Content Viewers column | 2026 Yahoo | Unique reach metric unusable | Skip Content Viewers analysis for 2026 Yahoo |

---

### Rigor Failures Log
*Cases where analysis was later found to be underspecified, wrong test, or wrong column.
Never rewritten — append only. The most valuable calibration record for the rigor standards.*

- **2026-04-02 | MSN baseline key mismatch** — MSN Formula Divergence tile used `"other"` as baseline key. `classify_formula()` returns `"untagged"`. Baseline group was always empty; table rendered blank for 2+ months. **Rule added:** Always verify baseline key matches `classify_formula()` output before running formula comparisons.

- **2026-04-02 | MSN wrong metric column** — `VIEWS_METRIC` (`percentile_within_cohort`, range 0–1) used instead of raw `"Pageviews"` for MSN formula analysis. Medians showed as "—" (near-zero values looked like missing data). **Rule added:** MSN analysis uses raw `"Pageviews"` column, not the normalized metric.

- **2026-04-02 | MSN hardcoded row lookups** — Four `_msn_fr()` row lookups targeted formula keys (`what_to_know`, `heres_formula`, etc.) that don't exist in current MSN data. Table rendered empty. **Rule added:** Never hardcode formula key lookups — always use dynamic table generation that checks available keys against actual data.

---

## GOVERNOR MAINTENANCE PROTOCOL

### At every session start
1. Read this file in full
2. Check Active Probing Queue — are any HIGH priority items applicable to today's data?
3. Check Known Data Quirks — are any relevant to today's analysis?
4. Apply Stakeholder Focus to filter what gets surfaced to the user

### At every session end
Propose the following (user approves before writing):
1. **Probing Queue updates** — add any new adjacent questions the data surfaced; mark completed items
2. **Confirmed Interesting / Low-Signal updates** — based on any stakeholder reactions observed
3. **Known Data Quirks updates** — any new anomalies encountered
4. **Rigor Failures Log entry** — if any finding was revised or found to be underspecified

### After Sarah provides tile feedback
1. Log each tile signal in `governor_log/` (format in that directory's README)
2. Update Confirmed Interesting / Low-Signal sections based on patterns across tiles
3. Update "What Interesting Means" section if new pattern emerges
4. Retire or reprioritize Probing Queue items whose answers were in a dismissed tile

*Budget: this file should stay under 300 lines. When it grows past 250, move older Confirmed Interesting / Low-Signal entries to `governor_log/archive.md`.*
