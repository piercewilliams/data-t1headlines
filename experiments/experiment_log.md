# Experiment Suggestion Log

Auto-generated. Appended each analytics run. Never manually edited.
Each run records the full set of directional suggestions at that point in time.

---

## Run: 2026-04 (generated 2026-04-03T22:31:25)

_8 suggestion(s) this run_

### [↑ High · Bonferroni fail] SmartNews — “Here’s / Here are” Lift — Needs Confirmation

**Signal:** Articles using “Here’s / Here are” on SmartNews score a median percentile rank of 0.543 vs. 0.500 for the direct-declarative baseline (n=585, raw p=0.038). Direction is positive — opposite to question and “What to know” on the same platform.

**Gap:** Raw p=0.038 does not survive Bonferroni correction at k=5 formula families (threshold α/k = 0.010). All data is observational; no A/B comparison is available. Topic confounding (“Here’s” may correlate with better-performing story types) has not been controlled for.

**Question:** If T1 editors A/B tested “Here’s / Here are” against a direct-declarative version of the same story on SmartNews, would the formula version consistently outperform? Does the effect hold across topics (sports, crime, weather) or appear only in a topic subset?

**How to run it:** For 30–50 stories over 4–6 weeks, write two headline versions per story: (A) “Here’s / Here are” format and (B) a direct declarative covering the same facts. If the CMS supports A/B headline testing, use it; otherwise alternate formula by publication day or assign by outlet. Record SmartNews views at 7 days post-publish. Test: Mann-Whitney U on SmartNews views (A vs. B), rank-biserial r as effect size. Minimum n = 30 matched story pairs for reliable inference. Stratify by topic (sports/crime/weather vs. other) to check whether any interaction hides or drives the aggregate result. Do not use the same story on Apple News A/B — keep platforms separate to avoid contamination.

**What the result unlocks:** Confirmed: adds a positive SmartNews formula signal — currently all confirmed SmartNews guidance is avoidance-only. Editors could be told “Here’s works on SmartNews, unlike Apple News where WTK dominates featuring.”  Not confirmed: SmartNews playbook stays avoidance-only; the directional positive for “Here’s” is noise or topic-driven.

### [Medium · Underpowered] Apple News — Number Lead Specificity — Round vs. Exact Figures

**Signal:** Specific numbers (e.g. ‘$487M’, ‘13 deaths’) score a median rank of 0.405 vs. 0.277 for round numbers on Apple News (n = 165 specific, 21 round)

**Gap:** Groups too small for a reliable test: round n=21, specific n=165.

**Question:** Do Apple News headlines with precise numeric values (e.g. ‘$487 million,’ ‘13 officers’) consistently outperform rounded equivalents (‘$500 million,’ ‘10+ officers’) for views, controlling for topic and story type?

**How to run it:** When writing number-lead headlines, deliberately tag each as ‘round’ (e.g. ‘$500M,’ ‘10 people’) or ‘specific’ (e.g. ‘$487M,’ ‘13 people’) in a shared tracking sheet. Collect at least 30 Apple News articles per type before running the test. No CMS change needed — this is a tagging discipline applied during headline writing. Analysis: Mann-Whitney U on Apple News percentile rank at 7 days (specific vs. round), rank-biserial r as effect size. Stratify by topic (financial stories likely have more specificity variance than crime or sports). Existing pipeline: classify_number_lead() already extracts the numeric value — add a roundness tag to the tracking sheet and re-run once 30+ per group are tagged.

**What the result unlocks:** Confirmed: adds precision-number guidance to the style guide (“use exact figures in number leads, not rounded approximations”). Editors who default to rounded figures for readability would be asked to reverse that practice.  Not confirmed: round vs. specific distinction does not affect views; the number-lead signal is format-driven rather than specificity-driven.

### [↑ High · Underpowered] MSN — MSN Formula Groups — Insufficient Data for Confirmation

**Signal:** 1 formula group(s) show directional patterns on MSN but cannot be confirmed: Quoted lede. 113 total T1 news brand articles after filtering. Groups with n < 30: Quoted lede (n=18).

**Gap:** All flagged groups have n < 30, below the minimum for reliable inference (GOVERNOR.md Part 2). Only the quoted-lede group currently has enough data to test, and it is the one confirmed MSN finding. The MSN dataset grows approximately 100 rows/month; most formula groups should cross n=30 within 2–3 months of continued data collection.

**Question:** As MSN data accumulates, which formula groups consistently underperform the direct-declarative baseline? Is the underperformance pattern broad (all structured formulas hurt on MSN) or specific to certain formats?

**How to run it:** Natural experiment — no new data collection needed. The MSN dataset grows approximately 100 rows/month after the T1 brand filter. Re-run the Mann-Whitney formula analysis each monthly ingest; generate_site.py already does this automatically and the build report surfaces newly-significant groups. Threshold: treat any formula group as testable once it crosses n = 30. Expected timeline: most groups should reach n=30 within 2–3 monthly ingest cycles. Analysis: Mann-Whitney U (each formula group vs. untagged baseline), BH-FDR corrected across all tested groups simultaneously, rank-biserial r as effect size. Language tier: significant only if p_adj < 0.05; directional if p_adj < 0.10. Baseline key must be ‘untagged’ (not ‘other’) — see GOVERNOR.md Rigor Failures Log.

**What the result unlocks:** Confirmed broad pattern: extends the MSN rule from ‘avoid quoted lede’ to ‘avoid all structured formulas.’ Gives editors the strongest possible two-headline guidance: Apple News → use formulas; MSN → drop them entirely.  Confirmed specific subset: MSN avoidance list grows to the confirmed formula types while others remain neutral.  Not confirmed: MSN formula penalty is limited to quoted lede only.

### [↑ High · Untested] Apple News — Character Length × Formula Type Interaction

**Signal:** Character length (90–120 chars) and formula type independently predict Apple News views. Whether these signals interact — e.g., whether possessive named entity needs to be longer to achieve its lift, or whether “Here’s” works at any length — has not been tested.

**Gap:** Cross-tabulating formula buckets with length quartiles fragments an already-segmented dataset. Most formula × length cells will have n < 30, requiring aggregation trade-offs that risk obscuring the interaction signal. Analysis not yet run.

**Question:** Do specific formula types require specific length ranges to achieve their Apple News performance lift? E.g., does “Here’s / Here are” need 90+ chars to work, or does it lift at any length? Does possessive named entity perform best at shorter lengths where the name dominates the headline?

**How to run it:** Run on existing Apple News 2025+2026 data — no new collection needed. Cross-tabulate by formula type × length quartile. For each formula with n ≥30 total, split into Q1 (shortest) and Q4 (longest) length buckets and run Mann-Whitney U within each formula group vs. the untagged baseline at the same length. Compare the lift magnitude across length buckets. If any formula×length cell has n < 15, aggregate: fold Q1+Q2 into ‘short’ and Q3+Q4 into ‘long.’ Report as an interaction: does the formula’s lift increase, decrease, or stay flat as length increases? Plot as a 2×2 heatmap (formula × length bucket, colored by median rank). Apply BH-FDR correction across all formula×length cells tested. Bonferroni fallback: if more than 10 cells are tested, apply Bonferroni at k=10 as a secondary check.

**What the result unlocks:** Confirmed interaction: compound guidance (formula + length range) replaces two independent rules. Editors get: “Use Here’s at 90–110 chars; use possessive at 70–90 chars.” More actionable than current guidance.  No interaction: the two independent rules are stable and can be applied separately without worrying about their interaction.

### [↑ High · Untested] Notifications — Notification CTR × Character Length

**Signal:** Formula choice has a 2–5× effect on notification CTR (confirmed). Character length has been tested for Apple News views but not for notification CTR. Notifications truncate at ~80 chars on most devices, making length more likely to matter here than in feed headlines.

**Gap:** Character length vs. notification CTR has not been run. The notifications dataset covers 2025–2026 (1,050+ news brand pushes with CTR data) — sufficient for a Mann-Whitney test across length quartiles.

**Question:** Do shorter notifications (≤80 chars) outperform longer ones for CTR, controlling for formula type? Is there a character-count range where CTR peaks, or is the relationship monotonic (shorter = better)?

**How to run it:** Run on the existing notifications dataset (1,050+ news brand pushes with CTR). No new data collection needed. Bin notification headlines into four length quartiles. Run Kruskal-Wallis across quartiles first to check for any length–CTR association. If significant (p < 0.05), follow with Mann-Whitney U pairwise comparisons (Q1 vs. Q4 as primary), BH-FDR corrected. Control for formula type via stratification: run the length–CTR analysis separately within each formula group that has n ≥30 (attribution language, question, direct declarative). If length effect disappears within formula groups, length is a formula proxy, not an independent signal. Secondary analysis: Spearman correlation between character count and CTR (raw correlation, no quartiling). This gives a monotonicity check without binning artifacts. Implement in generate_site.py as an extension of the existing Q5 notification analysis block.

**What the result unlocks:** Confirmed: adds a second actionable lever for push copy editors beyond formula choice. Current guidance (“use attribution language”) would be extended with a specific character-count target.  Not confirmed: formula dominates; length doesn’t independently move CTR and editors can focus solely on formula selection for notifications.

### [Medium · Untested] Apple News — “What to Know” — Featured vs. Organic Stability by Year

**Signal:** Apple editors select “What to Know” at 1.8× the baseline rate for Featured placement. Organic (non-Featured) articles using WTK show no significant view lift (p<sub>adj</sub>=0.10). This editorial/algorithmic split is a key project finding — but whether it is stable across 2025 and 2026 separately is unknown.

**Gap:** The current analysis pools 2025 and 2026 Apple News data. If Apple has updated curation signals, or if T1 editors have changed how they use WTK, the featuring lift or organic penalty could be shifting — which would change whether the two-headline strategy is durable guidance.

**Question:** Is the WTK featuring lift consistent when 2025 and 2026 are analyzed separately? Has the gap between editorial selection rate and organic algorithmic performance been stable, or is it narrowing/widening over time?

**How to run it:** Run on existing Apple News data — no new collection needed. Split the Apple News dataset by year (2025 and 2026 separately). For each year, run: (1) Q2 chi-square or Fisher’s exact test for WTK featuring rate vs. all other formulas; (2) Q1 Mann-Whitney U for WTK organic view rank vs. untagged baseline (non-Featured articles only). Compare the featuring lift ratio (WTK featured rate / baseline featured rate) and the organic p-value across years. A narrowing featured rate ratio or a trending organic p-value signals platform behavior change. Implement as a year-stratified extension of the existing Q1 and Q2 analysis blocks in generate_site.py. Report: a 2×2 table of year×metric (featuring lift and organic p) alongside a directional trend flag. Note: Apple News 2026 covers Jan–Mar only; interpret with caution until Q3 2026 data is available.

**What the result unlocks:** Stable across years: confirms structural platform behavior. The “WTK for Featured campaigns, avoid for organic” rule is durable.  Shifting: guidance needs to evolve. If organic performance is catching up to editorial selection, the two-headline distinction may already be outdated.

### [Medium · Untested] Apple News — Possessive Named Entity — Topic Concentration

**Signal:** Possessive named entity headlines (n=95) show moderate overall performance on Apple News. The signal may be concentrated in sports and crime — topics where named individuals are central to the story — but aggregate analysis cannot confirm this.

**Gap:** Overall n=95 is small enough that splitting by topic reduces per-cell counts below the 30-article threshold for reliable inference. The aggregate analysis masks any strong within-topic signal.

**Question:** Do possessive named entity headlines specifically outperform in sports and crime topics on Apple News, where named individuals are central? Is the aggregate signal driven by a strong within-topic effect, or is it distributed broadly across all topics?

**How to run it:** Run on existing Apple News 2025+2026 data. Filter to possessive named entity headlines. Split by topic: sports+crime (the ‘high named-entity’ group) vs. all other topics. Run Mann-Whitney U (sports+crime PNE articles vs. untagged baseline within the same topics), rank-biserial r as effect size. Repeat for the ‘other topics’ group. Compare lift magnitudes: if the sports+crime lift is substantially larger (r ≥0.1 higher) than the other-topics lift, the signal is topic-concentrated. If lifts are similar, the rule applies broadly. If either per-topic cell has n < 20, flag as preliminary and hold until data grows. Do not split into individual topics at this sample size — aggregate sports+crime as one group. Implement as a topic-stratified extension of the Q1 analysis in generate_site.py.

**What the result unlocks:** Confirmed topic-specific: changes guidance from a broad rule to a targeted one (“use possessive named entity for sports/crime stories specifically”). Editors know exactly when to apply it.  Evenly distributed: the broad rule stands. Possessive named entity is generally useful, not vertically restricted.

### [Medium · Untested] SmartNews — Number Lead Type — Which Numbers Drive the SmartNews Signal?

**Signal:** Number leads show a positive directional trend on SmartNews (median rank 0.534 vs. 0.497 baseline; direction: above_dir). They are the only SmartNews formula with a positive directional signal. Whether count/list (‘3 ways’), dollar amounts (‘$2 billion’), or percentages (‘47%’) drive this has not been tested.

**Gap:** Number-type classification (classify_number_lead()) is implemented in the pipeline but per-type SmartNews performance has not been computed. SmartNews 2026 data is domain-aggregated (not article-level), limiting this analysis to the 2025 dataset (n=38,251 articles).

**Question:** Which number-lead subtype drives the SmartNews directional signal: count/list, dollar amounts, or percentages? Or is the effect evenly distributed across number types, suggesting format (any number in the lead) matters more than type?

**How to run it:** Run on SmartNews 2025 number-lead articles (n ≈342 total). classify_number_lead() already extracts ntype (‘count_list,’ ‘dollar_amount,’ ‘percentage,’ ‘other’). Group by ntype and run Mann-Whitney U for each group vs. the untagged baseline, BH-FDR corrected across the three tested types. Expected n per type: count_list is likely the largest (list articles are common); dollar_amount and percentage groups may be small. Flag any group with n < 20 as preliminary. If all subtypes have low n, aggregate and report directionally only: “counts/lists trend higher (n=X, p=Y)” without a significance claim. Implement by extending the existing number-lead deep-dive block (classify_number_lead() section) in generate_site.py to add a per-type Mann-Whitney analysis. Note: SmartNews 2026 is domain-aggregated and cannot contribute to this analysis — 2025 data only.

**What the result unlocks:** Confirmed specific type: editors can be told “count/list numbers work on SmartNews; dollar amounts and percentages are neutral.” More precise than the current directional number-lead guidance.  Equally distributed: the rule is format-driven (“any number in the lead is better than none”). Simpler and more broadly applicable.

---

## Run: 2026-04 (generated 2026-04-03T22:37:03)

_8 suggestion(s) this run_

### [↑ High · Bonferroni fail] SmartNews — “Here’s / Here are” Lift — Needs Confirmation

**Signal:** Articles using “Here’s / Here are” on SmartNews score a median percentile rank of 0.543 vs. 0.500 for the direct-declarative baseline (n=585, raw p=0.038). Direction is positive — opposite to question and “What to know” on the same platform.

**Gap:** Raw p=0.038 does not survive Bonferroni correction at k=5 formula families (threshold α/k = 0.010). All data is observational; no A/B comparison is available. Topic confounding (“Here’s” may correlate with better-performing story types) has not been controlled for.

**Question:** If T1 editors A/B tested “Here’s / Here are” against a direct-declarative version of the same story on SmartNews, would the formula version consistently outperform? Does the effect hold across topics (sports, crime, weather) or appear only in a topic subset?

**How to run it:** For 30–50 stories over 4–6 weeks, write two headline versions per story: (A) “Here’s / Here are” format and (B) a direct declarative covering the same facts. If the CMS supports A/B headline testing, use it; otherwise alternate formula by publication day or assign by outlet. Record SmartNews views at 7 days post-publish. Test: Mann-Whitney U on SmartNews views (A vs. B), rank-biserial r as effect size. Minimum n = 30 matched story pairs for reliable inference. Stratify by topic (sports/crime/weather vs. other) to check whether any interaction hides or drives the aggregate result. Do not use the same story on Apple News A/B — keep platforms separate to avoid contamination.

**What the result unlocks:** Confirmed: adds a positive SmartNews formula signal — currently all confirmed SmartNews guidance is avoidance-only. Editors could be told “Here’s works on SmartNews, unlike Apple News where WTK dominates featuring.”  Not confirmed: SmartNews playbook stays avoidance-only; the directional positive for “Here’s” is noise or topic-driven.

### [Medium · Underpowered] Apple News — Number Lead Specificity — Round vs. Exact Figures

**Signal:** Specific numbers (e.g. ‘$487M’, ‘13 deaths’) score a median rank of 0.405 vs. 0.277 for round numbers on Apple News (n = 165 specific, 21 round)

**Gap:** Groups too small for a reliable test: round n=21, specific n=165.

**Question:** Do Apple News headlines with precise numeric values (e.g. ‘$487 million,’ ‘13 officers’) consistently outperform rounded equivalents (‘$500 million,’ ‘10+ officers’) for views, controlling for topic and story type?

**How to run it:** When writing number-lead headlines, deliberately tag each as ‘round’ (e.g. ‘$500M,’ ‘10 people’) or ‘specific’ (e.g. ‘$487M,’ ‘13 people’) in a shared tracking sheet. Collect at least 30 Apple News articles per type before running the test. No CMS change needed — this is a tagging discipline applied during headline writing. Analysis: Mann-Whitney U on Apple News percentile rank at 7 days (specific vs. round), rank-biserial r as effect size. Stratify by topic (financial stories likely have more specificity variance than crime or sports). Existing pipeline: classify_number_lead() already extracts the numeric value — add a roundness tag to the tracking sheet and re-run once 30+ per group are tagged.

**What the result unlocks:** Confirmed: adds precision-number guidance to the style guide (“use exact figures in number leads, not rounded approximations”). Editors who default to rounded figures for readability would be asked to reverse that practice.  Not confirmed: round vs. specific distinction does not affect views; the number-lead signal is format-driven rather than specificity-driven.

### [↑ High · Underpowered] MSN — MSN Formula Groups — Insufficient Data for Confirmation

**Signal:** 1 formula group(s) show directional patterns on MSN but cannot be confirmed: Quoted lede. 113 total T1 news brand articles after filtering. Groups with n < 30: Quoted lede (n=18).

**Gap:** All flagged groups have n < 30, below the minimum for reliable inference (GOVERNOR.md Part 2). Only the quoted-lede group currently has enough data to test, and it is the one confirmed MSN finding. The MSN dataset grows approximately 100 rows/month; most formula groups should cross n=30 within 2–3 months of continued data collection.

**Question:** As MSN data accumulates, which formula groups consistently underperform the direct-declarative baseline? Is the underperformance pattern broad (all structured formulas hurt on MSN) or specific to certain formats?

**How to run it:** Natural experiment — no new data collection needed. The MSN dataset grows approximately 100 rows/month after the T1 brand filter. Re-run the Mann-Whitney formula analysis each monthly ingest; generate_site.py already does this automatically and the build report surfaces newly-significant groups. Threshold: treat any formula group as testable once it crosses n = 30. Expected timeline: most groups should reach n=30 within 2–3 monthly ingest cycles. Analysis: Mann-Whitney U (each formula group vs. untagged baseline), BH-FDR corrected across all tested groups simultaneously, rank-biserial r as effect size. Language tier: significant only if p_adj < 0.05; directional if p_adj < 0.10. Baseline key must be ‘untagged’ (not ‘other’) — see GOVERNOR.md Rigor Failures Log.

**What the result unlocks:** Confirmed broad pattern: extends the MSN rule from ‘avoid quoted lede’ to ‘avoid all structured formulas.’ Gives editors the strongest possible two-headline guidance: Apple News → use formulas; MSN → drop them entirely.  Confirmed specific subset: MSN avoidance list grows to the confirmed formula types while others remain neutral.  Not confirmed: MSN formula penalty is limited to quoted lede only.

### [↑ High · Untested] Apple News — Character Length × Formula Type Interaction

**Signal:** Character length (90–120 chars) and formula type independently predict Apple News views. Whether these signals interact — e.g., whether possessive named entity needs to be longer to achieve its lift, or whether “Here’s” works at any length — has not been tested.

**Gap:** Cross-tabulating formula buckets with length quartiles fragments an already-segmented dataset. Most formula × length cells will have n < 30, requiring aggregation trade-offs that risk obscuring the interaction signal. Analysis not yet run.

**Question:** Do specific formula types require specific length ranges to achieve their Apple News performance lift? E.g., does “Here’s / Here are” need 90+ chars to work, or does it lift at any length? Does possessive named entity perform best at shorter lengths where the name dominates the headline?

**How to run it:** Run on existing Apple News 2025+2026 data — no new collection needed. Cross-tabulate by formula type × length quartile. For each formula with n ≥30 total, split into Q1 (shortest) and Q4 (longest) length buckets and run Mann-Whitney U within each formula group vs. the untagged baseline at the same length. Compare the lift magnitude across length buckets. If any formula×length cell has n < 15, aggregate: fold Q1+Q2 into ‘short’ and Q3+Q4 into ‘long.’ Report as an interaction: does the formula’s lift increase, decrease, or stay flat as length increases? Plot as a 2×2 heatmap (formula × length bucket, colored by median rank). Apply BH-FDR correction across all formula×length cells tested. Bonferroni fallback: if more than 10 cells are tested, apply Bonferroni at k=10 as a secondary check.

**What the result unlocks:** Confirmed interaction: compound guidance (formula + length range) replaces two independent rules. Editors get: “Use Here’s at 90–110 chars; use possessive at 70–90 chars.” More actionable than current guidance.  No interaction: the two independent rules are stable and can be applied separately without worrying about their interaction.

### [↑ High · Untested] Notifications — Notification CTR × Character Length

**Signal:** Formula choice has a 2–5× effect on notification CTR (confirmed). Character length has been tested for Apple News views but not for notification CTR. Notifications truncate at ~80 chars on most devices, making length more likely to matter here than in feed headlines.

**Gap:** Character length vs. notification CTR has not been run. The notifications dataset covers 2025–2026 (1,050+ news brand pushes with CTR data) — sufficient for a Mann-Whitney test across length quartiles.

**Question:** Do shorter notifications (≤80 chars) outperform longer ones for CTR, controlling for formula type? Is there a character-count range where CTR peaks, or is the relationship monotonic (shorter = better)?

**How to run it:** Run on the existing notifications dataset (1,050+ news brand pushes with CTR). No new data collection needed. Bin notification headlines into four length quartiles. Run Kruskal-Wallis across quartiles first to check for any length–CTR association. If significant (p < 0.05), follow with Mann-Whitney U pairwise comparisons (Q1 vs. Q4 as primary), BH-FDR corrected. Control for formula type via stratification: run the length–CTR analysis separately within each formula group that has n ≥30 (attribution language, question, direct declarative). If length effect disappears within formula groups, length is a formula proxy, not an independent signal. Secondary analysis: Spearman correlation between character count and CTR (raw correlation, no quartiling). This gives a monotonicity check without binning artifacts. Implement in generate_site.py as an extension of the existing Q5 notification analysis block.

**What the result unlocks:** Confirmed: adds a second actionable lever for push copy editors beyond formula choice. Current guidance (“use attribution language”) would be extended with a specific character-count target.  Not confirmed: formula dominates; length doesn’t independently move CTR and editors can focus solely on formula selection for notifications.

### [Medium · Untested] Apple News — “What to Know” — Featured vs. Organic Stability by Year

**Signal:** Apple editors select “What to Know” at 1.8× the baseline rate for Featured placement. Organic (non-Featured) articles using WTK show no significant view lift (p<sub>adj</sub>=0.10). This editorial/algorithmic split is a key project finding — but whether it is stable across 2025 and 2026 separately is unknown.

**Gap:** The current analysis pools 2025 and 2026 Apple News data. If Apple has updated curation signals, or if T1 editors have changed how they use WTK, the featuring lift or organic penalty could be shifting — which would change whether the two-headline strategy is durable guidance.

**Question:** Is the WTK featuring lift consistent when 2025 and 2026 are analyzed separately? Has the gap between editorial selection rate and organic algorithmic performance been stable, or is it narrowing/widening over time?

**How to run it:** Run on existing Apple News data — no new collection needed. Split the Apple News dataset by year (2025 and 2026 separately). For each year, run: (1) Q2 chi-square or Fisher’s exact test for WTK featuring rate vs. all other formulas; (2) Q1 Mann-Whitney U for WTK organic view rank vs. untagged baseline (non-Featured articles only). Compare the featuring lift ratio (WTK featured rate / baseline featured rate) and the organic p-value across years. A narrowing featured rate ratio or a trending organic p-value signals platform behavior change. Implement as a year-stratified extension of the existing Q1 and Q2 analysis blocks in generate_site.py. Report: a 2×2 table of year×metric (featuring lift and organic p) alongside a directional trend flag. Note: Apple News 2026 covers Jan–Mar only; interpret with caution until Q3 2026 data is available.

**What the result unlocks:** Stable across years: confirms structural platform behavior. The “WTK for Featured campaigns, avoid for organic” rule is durable.  Shifting: guidance needs to evolve. If organic performance is catching up to editorial selection, the two-headline distinction may already be outdated.

### [Medium · Untested] Apple News — Possessive Named Entity — Topic Concentration

**Signal:** Possessive named entity headlines (n=95) show moderate overall performance on Apple News. The signal may be concentrated in sports and crime — topics where named individuals are central to the story — but aggregate analysis cannot confirm this.

**Gap:** Overall n=95 is small enough that splitting by topic reduces per-cell counts below the 30-article threshold for reliable inference. The aggregate analysis masks any strong within-topic signal.

**Question:** Do possessive named entity headlines specifically outperform in sports and crime topics on Apple News, where named individuals are central? Is the aggregate signal driven by a strong within-topic effect, or is it distributed broadly across all topics?

**How to run it:** Run on existing Apple News 2025+2026 data. Filter to possessive named entity headlines. Split by topic: sports+crime (the ‘high named-entity’ group) vs. all other topics. Run Mann-Whitney U (sports+crime PNE articles vs. untagged baseline within the same topics), rank-biserial r as effect size. Repeat for the ‘other topics’ group. Compare lift magnitudes: if the sports+crime lift is substantially larger (r ≥0.1 higher) than the other-topics lift, the signal is topic-concentrated. If lifts are similar, the rule applies broadly. If either per-topic cell has n < 20, flag as preliminary and hold until data grows. Do not split into individual topics at this sample size — aggregate sports+crime as one group. Implement as a topic-stratified extension of the Q1 analysis in generate_site.py.

**What the result unlocks:** Confirmed topic-specific: changes guidance from a broad rule to a targeted one (“use possessive named entity for sports/crime stories specifically”). Editors know exactly when to apply it.  Evenly distributed: the broad rule stands. Possessive named entity is generally useful, not vertically restricted.

### [Medium · Untested] SmartNews — Number Lead Type — Which Numbers Drive the SmartNews Signal?

**Signal:** Number leads show a positive directional trend on SmartNews (median rank 0.534 vs. 0.497 baseline; direction: above_dir). They are the only SmartNews formula with a positive directional signal. Whether count/list (‘3 ways’), dollar amounts (‘$2 billion’), or percentages (‘47%’) drive this has not been tested.

**Gap:** Number-type classification (classify_number_lead()) is implemented in the pipeline but per-type SmartNews performance has not been computed. SmartNews 2026 data is domain-aggregated (not article-level), limiting this analysis to the 2025 dataset (n=38,251 articles).

**Question:** Which number-lead subtype drives the SmartNews directional signal: count/list, dollar amounts, or percentages? Or is the effect evenly distributed across number types, suggesting format (any number in the lead) matters more than type?

**How to run it:** Run on SmartNews 2025 number-lead articles (n ≈342 total). classify_number_lead() already extracts ntype (‘count_list,’ ‘dollar_amount,’ ‘percentage,’ ‘other’). Group by ntype and run Mann-Whitney U for each group vs. the untagged baseline, BH-FDR corrected across the three tested types. Expected n per type: count_list is likely the largest (list articles are common); dollar_amount and percentage groups may be small. Flag any group with n < 20 as preliminary. If all subtypes have low n, aggregate and report directionally only: “counts/lists trend higher (n=X, p=Y)” without a significance claim. Implement by extending the existing number-lead deep-dive block (classify_number_lead() section) in generate_site.py to add a per-type Mann-Whitney analysis. Note: SmartNews 2026 is domain-aggregated and cannot contribute to this analysis — 2025 data only.

**What the result unlocks:** Confirmed specific type: editors can be told “count/list numbers work on SmartNews; dollar amounts and percentages are neutral.” More precise than the current directional number-lead guidance.  Equally distributed: the rule is format-driven (“any number in the lead is better than none”). Simpler and more broadly applicable.

---

## Run: 2026-04 (generated 2026-04-03T22:38:05)

_8 suggestion(s) this run_

### [↑ High · Bonferroni fail] SmartNews — “Here’s / Here are” Lift — Needs Confirmation

**Signal:** Articles using “Here’s / Here are” on SmartNews score a median percentile rank of 0.543 vs. 0.500 for the direct-declarative baseline (n=585, raw p=0.038). Direction is positive — opposite to question and “What to know” on the same platform.

**Gap:** Raw p=0.038 does not survive Bonferroni correction at k=5 formula families (threshold α/k = 0.010). All data is observational; no A/B comparison is available. Topic confounding (“Here’s” may correlate with better-performing story types) has not been controlled for.

**Question:** If T1 editors A/B tested “Here’s / Here are” against a direct-declarative version of the same story on SmartNews, would the formula version consistently outperform? Does the effect hold across topics (sports, crime, weather) or appear only in a topic subset?

**How to run it:** For 30–50 stories over 4–6 weeks, write two headline versions per story: (A) “Here’s / Here are” format and (B) a direct declarative covering the same facts. If the CMS supports A/B headline testing, use it; otherwise alternate formula by publication day or assign by outlet. Record SmartNews views at 7 days post-publish. Test: Mann-Whitney U on SmartNews views (A vs. B), rank-biserial r as effect size. Minimum n = 30 matched story pairs for reliable inference. Stratify by topic (sports/crime/weather vs. other) to check whether any interaction hides or drives the aggregate result. Do not use the same story on Apple News A/B — keep platforms separate to avoid contamination.

**What the result unlocks:** Confirmed: adds a positive SmartNews formula signal — currently all confirmed SmartNews guidance is avoidance-only. Editors could be told “Here’s works on SmartNews, unlike Apple News where WTK dominates featuring.”  Not confirmed: SmartNews playbook stays avoidance-only; the directional positive for “Here’s” is noise or topic-driven.

### [Medium · Underpowered] Apple News — Number Lead Specificity — Round vs. Exact Figures

**Signal:** Specific numbers (e.g. ‘$487M’, ‘13 deaths’) score a median rank of 0.405 vs. 0.277 for round numbers on Apple News (n = 165 specific, 21 round)

**Gap:** Groups too small for a reliable test: round n=21, specific n=165.

**Question:** Do Apple News headlines with precise numeric values (e.g. ‘$487 million,’ ‘13 officers’) consistently outperform rounded equivalents (‘$500 million,’ ‘10+ officers’) for views, controlling for topic and story type?

**How to run it:** When writing number-lead headlines, deliberately tag each as ‘round’ (e.g. ‘$500M,’ ‘10 people’) or ‘specific’ (e.g. ‘$487M,’ ‘13 people’) in a shared tracking sheet. Collect at least 30 Apple News articles per type before running the test. No CMS change needed — this is a tagging discipline applied during headline writing. Analysis: Mann-Whitney U on Apple News percentile rank at 7 days (specific vs. round), rank-biserial r as effect size. Stratify by topic (financial stories likely have more specificity variance than crime or sports). Existing pipeline: classify_number_lead() already extracts the numeric value — add a roundness tag to the tracking sheet and re-run once 30+ per group are tagged.

**What the result unlocks:** Confirmed: adds precision-number guidance to the style guide (“use exact figures in number leads, not rounded approximations”). Editors who default to rounded figures for readability would be asked to reverse that practice.  Not confirmed: round vs. specific distinction does not affect views; the number-lead signal is format-driven rather than specificity-driven.

### [↑ High · Underpowered] MSN — MSN Formula Groups — Insufficient Data for Confirmation

**Signal:** 1 formula group(s) show directional patterns on MSN but cannot be confirmed: Quoted lede. 113 total T1 news brand articles after filtering. Groups with n < 30: Quoted lede (n=18).

**Gap:** All flagged groups have n < 30, below the minimum for reliable inference (GOVERNOR.md Part 2). Only the quoted-lede group currently has enough data to test, and it is the one confirmed MSN finding. The MSN dataset grows approximately 100 rows/month; most formula groups should cross n=30 within 2–3 months of continued data collection.

**Question:** As MSN data accumulates, which formula groups consistently underperform the direct-declarative baseline? Is the underperformance pattern broad (all structured formulas hurt on MSN) or specific to certain formats?

**How to run it:** Natural experiment — no new data collection needed. The MSN dataset grows approximately 100 rows/month after the T1 brand filter. Re-run the Mann-Whitney formula analysis each monthly ingest; generate_site.py already does this automatically and the build report surfaces newly-significant groups. Threshold: treat any formula group as testable once it crosses n = 30. Expected timeline: most groups should reach n=30 within 2–3 monthly ingest cycles. Analysis: Mann-Whitney U (each formula group vs. untagged baseline), BH-FDR corrected across all tested groups simultaneously, rank-biserial r as effect size. Language tier: significant only if p_adj < 0.05; directional if p_adj < 0.10. Baseline key must be ‘untagged’ (not ‘other’) — see GOVERNOR.md Rigor Failures Log.

**What the result unlocks:** Confirmed broad pattern: extends the MSN rule from ‘avoid quoted lede’ to ‘avoid all structured formulas.’ Gives editors the strongest possible two-headline guidance: Apple News → use formulas; MSN → drop them entirely.  Confirmed specific subset: MSN avoidance list grows to the confirmed formula types while others remain neutral.  Not confirmed: MSN formula penalty is limited to quoted lede only.

### [↑ High · Untested] Apple News — Character Length × Formula Type Interaction

**Signal:** Character length (90–120 chars) and formula type independently predict Apple News views. Whether these signals interact — e.g., whether possessive named entity needs to be longer to achieve its lift, or whether “Here’s” works at any length — has not been tested.

**Gap:** Cross-tabulating formula buckets with length quartiles fragments an already-segmented dataset. Most formula × length cells will have n < 30, requiring aggregation trade-offs that risk obscuring the interaction signal. Analysis not yet run.

**Question:** Do specific formula types require specific length ranges to achieve their Apple News performance lift? E.g., does “Here’s / Here are” need 90+ chars to work, or does it lift at any length? Does possessive named entity perform best at shorter lengths where the name dominates the headline?

**How to run it:** Run on existing Apple News 2025+2026 data — no new collection needed. Cross-tabulate by formula type × length quartile. For each formula with n ≥30 total, split into Q1 (shortest) and Q4 (longest) length buckets and run Mann-Whitney U within each formula group vs. the untagged baseline at the same length. Compare the lift magnitude across length buckets. If any formula×length cell has n < 15, aggregate: fold Q1+Q2 into ‘short’ and Q3+Q4 into ‘long.’ Report as an interaction: does the formula’s lift increase, decrease, or stay flat as length increases? Plot as a 2×2 heatmap (formula × length bucket, colored by median rank). Apply BH-FDR correction across all formula×length cells tested. Bonferroni fallback: if more than 10 cells are tested, apply Bonferroni at k=10 as a secondary check.

**What the result unlocks:** Confirmed interaction: compound guidance (formula + length range) replaces two independent rules. Editors get: “Use Here’s at 90–110 chars; use possessive at 70–90 chars.” More actionable than current guidance.  No interaction: the two independent rules are stable and can be applied separately without worrying about their interaction.

### [↑ High · Untested] Notifications — Notification CTR × Character Length

**Signal:** Formula choice has a 2–5× effect on notification CTR (confirmed). Character length has been tested for Apple News views but not for notification CTR. Notifications truncate at ~80 chars on most devices, making length more likely to matter here than in feed headlines.

**Gap:** Character length vs. notification CTR has not been run. The notifications dataset covers 2025–2026 (1,050+ news brand pushes with CTR data) — sufficient for a Mann-Whitney test across length quartiles.

**Question:** Do shorter notifications (≤80 chars) outperform longer ones for CTR, controlling for formula type? Is there a character-count range where CTR peaks, or is the relationship monotonic (shorter = better)?

**How to run it:** Run on the existing notifications dataset (1,050+ news brand pushes with CTR). No new data collection needed. Bin notification headlines into four length quartiles. Run Kruskal-Wallis across quartiles first to check for any length–CTR association. If significant (p < 0.05), follow with Mann-Whitney U pairwise comparisons (Q1 vs. Q4 as primary), BH-FDR corrected. Control for formula type via stratification: run the length–CTR analysis separately within each formula group that has n ≥30 (attribution language, question, direct declarative). If length effect disappears within formula groups, length is a formula proxy, not an independent signal. Secondary analysis: Spearman correlation between character count and CTR (raw correlation, no quartiling). This gives a monotonicity check without binning artifacts. Implement in generate_site.py as an extension of the existing Q5 notification analysis block.

**What the result unlocks:** Confirmed: adds a second actionable lever for push copy editors beyond formula choice. Current guidance (“use attribution language”) would be extended with a specific character-count target.  Not confirmed: formula dominates; length doesn’t independently move CTR and editors can focus solely on formula selection for notifications.

### [Medium · Untested] Apple News — “What to Know” — Featured vs. Organic Stability by Year

**Signal:** Apple editors select “What to Know” at 1.8× the baseline rate for Featured placement. Organic (non-Featured) articles using WTK show no significant view lift (p<sub>adj</sub>=0.10). This editorial/algorithmic split is a key project finding — but whether it is stable across 2025 and 2026 separately is unknown.

**Gap:** The current analysis pools 2025 and 2026 Apple News data. If Apple has updated curation signals, or if T1 editors have changed how they use WTK, the featuring lift or organic penalty could be shifting — which would change whether the two-headline strategy is durable guidance.

**Question:** Is the WTK featuring lift consistent when 2025 and 2026 are analyzed separately? Has the gap between editorial selection rate and organic algorithmic performance been stable, or is it narrowing/widening over time?

**How to run it:** Run on existing Apple News data — no new collection needed. Split the Apple News dataset by year (2025 and 2026 separately). For each year, run: (1) Q2 chi-square or Fisher’s exact test for WTK featuring rate vs. all other formulas; (2) Q1 Mann-Whitney U for WTK organic view rank vs. untagged baseline (non-Featured articles only). Compare the featuring lift ratio (WTK featured rate / baseline featured rate) and the organic p-value across years. A narrowing featured rate ratio or a trending organic p-value signals platform behavior change. Implement as a year-stratified extension of the existing Q1 and Q2 analysis blocks in generate_site.py. Report: a 2×2 table of year×metric (featuring lift and organic p) alongside a directional trend flag. Note: Apple News 2026 covers Jan–Mar only; interpret with caution until Q3 2026 data is available.

**What the result unlocks:** Stable across years: confirms structural platform behavior. The “WTK for Featured campaigns, avoid for organic” rule is durable.  Shifting: guidance needs to evolve. If organic performance is catching up to editorial selection, the two-headline distinction may already be outdated.

### [Medium · Untested] Apple News — Possessive Named Entity — Topic Concentration

**Signal:** Possessive named entity headlines (n=95) show moderate overall performance on Apple News. The signal may be concentrated in sports and crime — topics where named individuals are central to the story — but aggregate analysis cannot confirm this.

**Gap:** Overall n=95 is small enough that splitting by topic reduces per-cell counts below the 30-article threshold for reliable inference. The aggregate analysis masks any strong within-topic signal.

**Question:** Do possessive named entity headlines specifically outperform in sports and crime topics on Apple News, where named individuals are central? Is the aggregate signal driven by a strong within-topic effect, or is it distributed broadly across all topics?

**How to run it:** Run on existing Apple News 2025+2026 data. Filter to possessive named entity headlines. Split by topic: sports+crime (the ‘high named-entity’ group) vs. all other topics. Run Mann-Whitney U (sports+crime PNE articles vs. untagged baseline within the same topics), rank-biserial r as effect size. Repeat for the ‘other topics’ group. Compare lift magnitudes: if the sports+crime lift is substantially larger (r ≥0.1 higher) than the other-topics lift, the signal is topic-concentrated. If lifts are similar, the rule applies broadly. If either per-topic cell has n < 20, flag as preliminary and hold until data grows. Do not split into individual topics at this sample size — aggregate sports+crime as one group. Implement as a topic-stratified extension of the Q1 analysis in generate_site.py.

**What the result unlocks:** Confirmed topic-specific: changes guidance from a broad rule to a targeted one (“use possessive named entity for sports/crime stories specifically”). Editors know exactly when to apply it.  Evenly distributed: the broad rule stands. Possessive named entity is generally useful, not vertically restricted.

### [Medium · Untested] SmartNews — Number Lead Type — Which Numbers Drive the SmartNews Signal?

**Signal:** Number leads show a positive directional trend on SmartNews (median rank 0.534 vs. 0.497 baseline; direction: above_dir). They are the only SmartNews formula with a positive directional signal. Whether count/list (‘3 ways’), dollar amounts (‘$2 billion’), or percentages (‘47%’) drive this has not been tested.

**Gap:** Number-type classification (classify_number_lead()) is implemented in the pipeline but per-type SmartNews performance has not been computed. SmartNews 2026 data is domain-aggregated (not article-level), limiting this analysis to the 2025 dataset (n=38,251 articles).

**Question:** Which number-lead subtype drives the SmartNews directional signal: count/list, dollar amounts, or percentages? Or is the effect evenly distributed across number types, suggesting format (any number in the lead) matters more than type?

**How to run it:** Run on SmartNews 2025 number-lead articles (n ≈342 total). classify_number_lead() already extracts ntype (‘count_list,’ ‘dollar_amount,’ ‘percentage,’ ‘other’). Group by ntype and run Mann-Whitney U for each group vs. the untagged baseline, BH-FDR corrected across the three tested types. Expected n per type: count_list is likely the largest (list articles are common); dollar_amount and percentage groups may be small. Flag any group with n < 20 as preliminary. If all subtypes have low n, aggregate and report directionally only: “counts/lists trend higher (n=X, p=Y)” without a significance claim. Implement by extending the existing number-lead deep-dive block (classify_number_lead() section) in generate_site.py to add a per-type Mann-Whitney analysis. Note: SmartNews 2026 is domain-aggregated and cannot contribute to this analysis — 2025 data only.

**What the result unlocks:** Confirmed specific type: editors can be told “count/list numbers work on SmartNews; dollar amounts and percentages are neutral.” More precise than the current directional number-lead guidance.  Equally distributed: the rule is format-driven (“any number in the lead is better than none”). Simpler and more broadly applicable.

---

## Run: 2026-04 (generated 2026-04-06T19:46:42)

_8 suggestion(s) this run_

### [↑ High · Bonferroni fail] SmartNews — “Here’s / Here are” Lift — Needs Confirmation

**Signal:** Articles using “Here’s / Here are” on SmartNews score a median percentile rank of 0.543 vs. 0.500 for the direct-declarative baseline (n=585, raw p=0.038). Direction is positive — opposite to question and “What to know” on the same platform.

**Gap:** Raw p=0.038 does not survive Bonferroni correction at k=5 formula families (threshold α/k = 0.010). All data is observational; no A/B comparison is available. Topic confounding (“Here’s” may correlate with better-performing story types) has not been controlled for.

**Question:** If T1 editors A/B tested “Here’s / Here are” against a direct-declarative version of the same story on SmartNews, would the formula version consistently outperform? Does the effect hold across topics (sports, crime, weather) or appear only in a topic subset?

**How to run it:** For 30–50 stories over 4–6 weeks, write two headline versions per story: (A) “Here’s / Here are” format and (B) a direct declarative covering the same facts. If the CMS supports A/B headline testing, use it; otherwise alternate formula by publication day or assign by outlet. Record SmartNews views at 7 days post-publish. Test: Mann-Whitney U on SmartNews views (A vs. B), rank-biserial r as effect size. Minimum n = 30 matched story pairs for reliable inference. Stratify by topic (sports/crime/weather vs. other) to check whether any interaction hides or drives the aggregate result. Do not use the same story on Apple News A/B — keep platforms separate to avoid contamination.

**What the result unlocks:** Confirmed: adds a positive SmartNews formula signal — currently all confirmed SmartNews guidance is avoidance-only. Editors could be told “Here’s works on SmartNews, unlike Apple News where WTK dominates featuring.”  Not confirmed: SmartNews playbook stays avoidance-only; the directional positive for “Here’s” is noise or topic-driven.

### [Medium · Underpowered] Apple News — Number Lead Specificity — Round vs. Exact Figures

**Signal:** Specific numbers (e.g. ‘$487M’, ‘13 deaths’) score a median rank of 0.405 vs. 0.277 for round numbers on Apple News (n = 165 specific, 21 round)

**Gap:** Groups too small for a reliable test: round n=21, specific n=165.

**Question:** Do Apple News headlines with precise numeric values (e.g. ‘$487 million,’ ‘13 officers’) consistently outperform rounded equivalents (‘$500 million,’ ‘10+ officers’) for views, controlling for topic and story type?

**How to run it:** When writing number-lead headlines, deliberately tag each as ‘round’ (e.g. ‘$500M,’ ‘10 people’) or ‘specific’ (e.g. ‘$487M,’ ‘13 people’) in a shared tracking sheet. Collect at least 30 Apple News articles per type before running the test. No CMS change needed — this is a tagging discipline applied during headline writing. Analysis: Mann-Whitney U on Apple News percentile rank at 7 days (specific vs. round), rank-biserial r as effect size. Stratify by topic (financial stories likely have more specificity variance than crime or sports). Existing pipeline: classify_number_lead() already extracts the numeric value — add a roundness tag to the tracking sheet and re-run once 30+ per group are tagged.

**What the result unlocks:** Confirmed: adds precision-number guidance to the style guide (“use exact figures in number leads, not rounded approximations”). Editors who default to rounded figures for readability would be asked to reverse that practice.  Not confirmed: round vs. specific distinction does not affect views; the number-lead signal is format-driven rather than specificity-driven.

### [↑ High · Underpowered] MSN — MSN Formula Groups — Insufficient Data for Confirmation

**Signal:** 1 formula group(s) show directional patterns on MSN but cannot be confirmed: Quoted lede. 113 total T1 news brand articles after filtering. Groups with n < 30: Quoted lede (n=18).

**Gap:** All flagged groups have n < 30, below the minimum for reliable inference (GOVERNOR.md Part 2). Only the quoted-lede group currently has enough data to test, and it is the one confirmed MSN finding. The MSN dataset grows approximately 100 rows/month; most formula groups should cross n=30 within 2–3 months of continued data collection.

**Question:** As MSN data accumulates, which formula groups consistently underperform the direct-declarative baseline? Is the underperformance pattern broad (all structured formulas hurt on MSN) or specific to certain formats?

**How to run it:** Natural experiment — no new data collection needed. The MSN dataset grows approximately 100 rows/month after the T1 brand filter. Re-run the Mann-Whitney formula analysis each monthly ingest; generate_site.py already does this automatically and the build report surfaces newly-significant groups. Threshold: treat any formula group as testable once it crosses n = 30. Expected timeline: most groups should reach n=30 within 2–3 monthly ingest cycles. Analysis: Mann-Whitney U (each formula group vs. untagged baseline), BH-FDR corrected across all tested groups simultaneously, rank-biserial r as effect size. Language tier: significant only if p_adj < 0.05; directional if p_adj < 0.10. Baseline key must be ‘untagged’ (not ‘other’) — see GOVERNOR.md Rigor Failures Log.

**What the result unlocks:** Confirmed broad pattern: extends the MSN rule from ‘avoid quoted lede’ to ‘avoid all structured formulas.’ Gives editors the strongest possible two-headline guidance: Apple News → use formulas; MSN → drop them entirely.  Confirmed specific subset: MSN avoidance list grows to the confirmed formula types while others remain neutral.  Not confirmed: MSN formula penalty is limited to quoted lede only.

### [↑ High · Untested] Apple News — Character Length × Formula Type Interaction

**Signal:** Character length (90–120 chars) and formula type independently predict Apple News views. Whether these signals interact — e.g., whether possessive named entity needs to be longer to achieve its lift, or whether “Here’s” works at any length — has not been tested.

**Gap:** Cross-tabulating formula buckets with length quartiles fragments an already-segmented dataset. Most formula × length cells will have n < 30, requiring aggregation trade-offs that risk obscuring the interaction signal. Analysis not yet run.

**Question:** Do specific formula types require specific length ranges to achieve their Apple News performance lift? E.g., does “Here’s / Here are” need 90+ chars to work, or does it lift at any length? Does possessive named entity perform best at shorter lengths where the name dominates the headline?

**How to run it:** Run on existing Apple News 2025+2026 data — no new collection needed. Cross-tabulate by formula type × length quartile. For each formula with n ≥30 total, split into Q1 (shortest) and Q4 (longest) length buckets and run Mann-Whitney U within each formula group vs. the untagged baseline at the same length. Compare the lift magnitude across length buckets. If any formula×length cell has n < 15, aggregate: fold Q1+Q2 into ‘short’ and Q3+Q4 into ‘long.’ Report as an interaction: does the formula’s lift increase, decrease, or stay flat as length increases? Plot as a 2×2 heatmap (formula × length bucket, colored by median rank). Apply BH-FDR correction across all formula×length cells tested. Bonferroni fallback: if more than 10 cells are tested, apply Bonferroni at k=10 as a secondary check.

**What the result unlocks:** Confirmed interaction: compound guidance (formula + length range) replaces two independent rules. Editors get: “Use Here’s at 90–110 chars; use possessive at 70–90 chars.” More actionable than current guidance.  No interaction: the two independent rules are stable and can be applied separately without worrying about their interaction.

### [↑ High · Untested] Notifications — Notification CTR × Character Length

**Signal:** Formula choice has a 2–5× effect on notification CTR (confirmed). Character length has been tested for Apple News views but not for notification CTR. Notifications truncate at ~80 chars on most devices, making length more likely to matter here than in feed headlines.

**Gap:** Character length vs. notification CTR has not been run. The notifications dataset covers 2025–2026 (1,050+ news brand pushes with CTR data) — sufficient for a Mann-Whitney test across length quartiles.

**Question:** Do shorter notifications (≤80 chars) outperform longer ones for CTR, controlling for formula type? Is there a character-count range where CTR peaks, or is the relationship monotonic (shorter = better)?

**How to run it:** Run on the existing notifications dataset (1,050+ news brand pushes with CTR). No new data collection needed. Bin notification headlines into four length quartiles. Run Kruskal-Wallis across quartiles first to check for any length–CTR association. If significant (p < 0.05), follow with Mann-Whitney U pairwise comparisons (Q1 vs. Q4 as primary), BH-FDR corrected. Control for formula type via stratification: run the length–CTR analysis separately within each formula group that has n ≥30 (attribution language, question, direct declarative). If length effect disappears within formula groups, length is a formula proxy, not an independent signal. Secondary analysis: Spearman correlation between character count and CTR (raw correlation, no quartiling). This gives a monotonicity check without binning artifacts. Implement in generate_site.py as an extension of the existing Q5 notification analysis block.

**What the result unlocks:** Confirmed: adds a second actionable lever for push copy editors beyond formula choice. Current guidance (“use attribution language”) would be extended with a specific character-count target.  Not confirmed: formula dominates; length doesn’t independently move CTR and editors can focus solely on formula selection for notifications.

### [Medium · Untested] Apple News — “What to Know” — Featured vs. Organic Stability by Year

**Signal:** Apple editors select “What to Know” at 1.8× the baseline rate for Featured placement. Organic (non-Featured) articles using WTK show no significant view lift (p<sub>adj</sub>=0.10). This editorial/algorithmic split is a key project finding — but whether it is stable across 2025 and 2026 separately is unknown.

**Gap:** The current analysis pools 2025 and 2026 Apple News data. If Apple has updated curation signals, or if T1 editors have changed how they use WTK, the featuring lift or organic penalty could be shifting — which would change whether the two-headline strategy is durable guidance.

**Question:** Is the WTK featuring lift consistent when 2025 and 2026 are analyzed separately? Has the gap between editorial selection rate and organic algorithmic performance been stable, or is it narrowing/widening over time?

**How to run it:** Run on existing Apple News data — no new collection needed. Split the Apple News dataset by year (2025 and 2026 separately). For each year, run: (1) Q2 chi-square or Fisher’s exact test for WTK featuring rate vs. all other formulas; (2) Q1 Mann-Whitney U for WTK organic view rank vs. untagged baseline (non-Featured articles only). Compare the featuring lift ratio (WTK featured rate / baseline featured rate) and the organic p-value across years. A narrowing featured rate ratio or a trending organic p-value signals platform behavior change. Implement as a year-stratified extension of the existing Q1 and Q2 analysis blocks in generate_site.py. Report: a 2×2 table of year×metric (featuring lift and organic p) alongside a directional trend flag. Note: Apple News 2026 covers Jan–Mar only; interpret with caution until Q3 2026 data is available.

**What the result unlocks:** Stable across years: confirms structural platform behavior. The “WTK for Featured campaigns, avoid for organic” rule is durable.  Shifting: guidance needs to evolve. If organic performance is catching up to editorial selection, the two-headline distinction may already be outdated.

### [Medium · Untested] Apple News — Possessive Named Entity — Topic Concentration

**Signal:** Possessive named entity headlines (n=95) show moderate overall performance on Apple News. The signal may be concentrated in sports and crime — topics where named individuals are central to the story — but aggregate analysis cannot confirm this.

**Gap:** Overall n=95 is small enough that splitting by topic reduces per-cell counts below the 30-article threshold for reliable inference. The aggregate analysis masks any strong within-topic signal.

**Question:** Do possessive named entity headlines specifically outperform in sports and crime topics on Apple News, where named individuals are central? Is the aggregate signal driven by a strong within-topic effect, or is it distributed broadly across all topics?

**How to run it:** Run on existing Apple News 2025+2026 data. Filter to possessive named entity headlines. Split by topic: sports+crime (the ‘high named-entity’ group) vs. all other topics. Run Mann-Whitney U (sports+crime PNE articles vs. untagged baseline within the same topics), rank-biserial r as effect size. Repeat for the ‘other topics’ group. Compare lift magnitudes: if the sports+crime lift is substantially larger (r ≥0.1 higher) than the other-topics lift, the signal is topic-concentrated. If lifts are similar, the rule applies broadly. If either per-topic cell has n < 20, flag as preliminary and hold until data grows. Do not split into individual topics at this sample size — aggregate sports+crime as one group. Implement as a topic-stratified extension of the Q1 analysis in generate_site.py.

**What the result unlocks:** Confirmed topic-specific: changes guidance from a broad rule to a targeted one (“use possessive named entity for sports/crime stories specifically”). Editors know exactly when to apply it.  Evenly distributed: the broad rule stands. Possessive named entity is generally useful, not vertically restricted.

### [Medium · Untested] SmartNews — Number Lead Type — Which Numbers Drive the SmartNews Signal?

**Signal:** Number leads show a positive directional trend on SmartNews (median rank 0.534 vs. 0.497 baseline; direction: above_dir). They are the only SmartNews formula with a positive directional signal. Whether count/list (‘3 ways’), dollar amounts (‘$2 billion’), or percentages (‘47%’) drive this has not been tested.

**Gap:** Number-type classification (classify_number_lead()) is implemented in the pipeline but per-type SmartNews performance has not been computed. SmartNews 2026 data is domain-aggregated (not article-level), limiting this analysis to the 2025 dataset (n=38,251 articles).

**Question:** Which number-lead subtype drives the SmartNews directional signal: count/list, dollar amounts, or percentages? Or is the effect evenly distributed across number types, suggesting format (any number in the lead) matters more than type?

**How to run it:** Run on SmartNews 2025 number-lead articles (n ≈342 total). classify_number_lead() already extracts ntype (‘count_list,’ ‘dollar_amount,’ ‘percentage,’ ‘other’). Group by ntype and run Mann-Whitney U for each group vs. the untagged baseline, BH-FDR corrected across the three tested types. Expected n per type: count_list is likely the largest (list articles are common); dollar_amount and percentage groups may be small. Flag any group with n < 20 as preliminary. If all subtypes have low n, aggregate and report directionally only: “counts/lists trend higher (n=X, p=Y)” without a significance claim. Implement by extending the existing number-lead deep-dive block (classify_number_lead() section) in generate_site.py to add a per-type Mann-Whitney analysis. Note: SmartNews 2026 is domain-aggregated and cannot contribute to this analysis — 2025 data only.

**What the result unlocks:** Confirmed specific type: editors can be told “count/list numbers work on SmartNews; dollar amounts and percentages are neutral.” More precise than the current directional number-lead guidance.  Equally distributed: the rule is format-driven (“any number in the lead is better than none”). Simpler and more broadly applicable.

---

## Run: 2026-04 (generated 2026-04-08T13:01:05)

_8 suggestion(s) this run_

### [↑ High · Bonferroni fail] SmartNews — “Here’s / Here are” Lift — Needs Confirmation

**Signal:** Articles using “Here’s / Here are” on SmartNews score a median percentile rank of 0.543 vs. 0.500 for the direct-declarative baseline (n=585, raw p=0.038). Direction is positive — opposite to question and “What to know” on the same platform.

**Gap:** Raw p=0.038 does not survive Bonferroni correction at k=5 formula families (threshold α/k = 0.010). All data is observational; no A/B comparison is available. Topic confounding (“Here’s” may correlate with better-performing story types) has not been controlled for.

**Question:** If T1 editors A/B tested “Here’s / Here are” against a direct-declarative version of the same story on SmartNews, would the formula version consistently outperform? Does the effect hold across topics (sports, crime, weather) or appear only in a topic subset?

**How to run it:** For 30–50 stories over 4–6 weeks, write two headline versions per story: (A) “Here’s / Here are” format and (B) a direct declarative covering the same facts. If the CMS supports A/B headline testing, use it; otherwise alternate formula by publication day or assign by outlet. Record SmartNews views at 7 days post-publish. Test: Mann-Whitney U on SmartNews views (A vs. B), rank-biserial r as effect size. Minimum n = 30 matched story pairs for reliable inference. Stratify by topic (sports/crime/weather vs. other) to check whether any interaction hides or drives the aggregate result. Do not use the same story on Apple News A/B — keep platforms separate to avoid contamination.

**What the result unlocks:** Confirmed: adds a positive SmartNews formula signal — currently all confirmed SmartNews guidance is avoidance-only. Editors could be told “Here’s works on SmartNews, unlike Apple News where WTK dominates featuring.”  Not confirmed: SmartNews playbook stays avoidance-only; the directional positive for “Here’s” is noise or topic-driven.

### [Medium · Underpowered] Apple News — Number Lead Specificity — Round vs. Exact Figures

**Signal:** Specific numbers (e.g. ‘$487M’, ‘13 deaths’) score a median rank of 0.405 vs. 0.277 for round numbers on Apple News (n = 165 specific, 21 round)

**Gap:** Groups too small for a reliable test: round n=21, specific n=165.

**Question:** Do Apple News headlines with precise numeric values (e.g. ‘$487 million,’ ‘13 officers’) consistently outperform rounded equivalents (‘$500 million,’ ‘10+ officers’) for views, controlling for topic and story type?

**How to run it:** When writing number-lead headlines, deliberately tag each as ‘round’ (e.g. ‘$500M,’ ‘10 people’) or ‘specific’ (e.g. ‘$487M,’ ‘13 people’) in a shared tracking sheet. Collect at least 30 Apple News articles per type before running the test. No CMS change needed — this is a tagging discipline applied during headline writing. Analysis: Mann-Whitney U on Apple News percentile rank at 7 days (specific vs. round), rank-biserial r as effect size. Stratify by topic (financial stories likely have more specificity variance than crime or sports). Existing pipeline: classify_number_lead() already extracts the numeric value — add a roundness tag to the tracking sheet and re-run once 30+ per group are tagged.

**What the result unlocks:** Confirmed: adds precision-number guidance to the style guide (“use exact figures in number leads, not rounded approximations”). Editors who default to rounded figures for readability would be asked to reverse that practice.  Not confirmed: round vs. specific distinction does not affect views; the number-lead signal is format-driven rather than specificity-driven.

### [↑ High · Underpowered] MSN — MSN Formula Groups — Insufficient Data for Confirmation

**Signal:** 1 formula group(s) show directional patterns on MSN but cannot be confirmed: Quoted lede. 113 total T1 news brand articles after filtering. Groups with n < 30: Quoted lede (n=18).

**Gap:** All flagged groups have n < 30, below the minimum for reliable inference (GOVERNOR.md Part 2). Only the quoted-lede group currently has enough data to test, and it is the one confirmed MSN finding. The MSN dataset grows approximately 100 rows/month; most formula groups should cross n=30 within 2–3 months of continued data collection.

**Question:** As MSN data accumulates, which formula groups consistently underperform the direct-declarative baseline? Is the underperformance pattern broad (all structured formulas hurt on MSN) or specific to certain formats?

**How to run it:** Natural experiment — no new data collection needed. The MSN dataset grows approximately 100 rows/month after the T1 brand filter. Re-run the Mann-Whitney formula analysis each monthly ingest; generate_site.py already does this automatically and the build report surfaces newly-significant groups. Threshold: treat any formula group as testable once it crosses n = 30. Expected timeline: most groups should reach n=30 within 2–3 monthly ingest cycles. Analysis: Mann-Whitney U (each formula group vs. untagged baseline), BH-FDR corrected across all tested groups simultaneously, rank-biserial r as effect size. Language tier: significant only if p_adj < 0.05; directional if p_adj < 0.10. Baseline key must be ‘untagged’ (not ‘other’) — see GOVERNOR.md Rigor Failures Log.

**What the result unlocks:** Confirmed broad pattern: extends the MSN rule from ‘avoid quoted lede’ to ‘avoid all structured formulas.’ Gives editors the strongest possible two-headline guidance: Apple News → use formulas; MSN → drop them entirely.  Confirmed specific subset: MSN avoidance list grows to the confirmed formula types while others remain neutral.  Not confirmed: MSN formula penalty is limited to quoted lede only.

### [↑ High · Untested] Apple News — Character Length × Formula Type Interaction

**Signal:** Character length (90–120 chars) and formula type independently predict Apple News views. Whether these signals interact — e.g., whether possessive named entity needs to be longer to achieve its lift, or whether “Here’s” works at any length — has not been tested.

**Gap:** Cross-tabulating formula buckets with length quartiles fragments an already-segmented dataset. Most formula × length cells will have n < 30, requiring aggregation trade-offs that risk obscuring the interaction signal. Analysis not yet run.

**Question:** Do specific formula types require specific length ranges to achieve their Apple News performance lift? E.g., does “Here’s / Here are” need 90+ chars to work, or does it lift at any length? Does possessive named entity perform best at shorter lengths where the name dominates the headline?

**How to run it:** Run on existing Apple News 2025+2026 data — no new collection needed. Cross-tabulate by formula type × length quartile. For each formula with n ≥30 total, split into Q1 (shortest) and Q4 (longest) length buckets and run Mann-Whitney U within each formula group vs. the untagged baseline at the same length. Compare the lift magnitude across length buckets. If any formula×length cell has n < 15, aggregate: fold Q1+Q2 into ‘short’ and Q3+Q4 into ‘long.’ Report as an interaction: does the formula’s lift increase, decrease, or stay flat as length increases? Plot as a 2×2 heatmap (formula × length bucket, colored by median rank). Apply BH-FDR correction across all formula×length cells tested. Bonferroni fallback: if more than 10 cells are tested, apply Bonferroni at k=10 as a secondary check.

**What the result unlocks:** Confirmed interaction: compound guidance (formula + length range) replaces two independent rules. Editors get: “Use Here’s at 90–110 chars; use possessive at 70–90 chars.” More actionable than current guidance.  No interaction: the two independent rules are stable and can be applied separately without worrying about their interaction.

### [↑ High · Untested] Notifications — Notification CTR × Character Length

**Signal:** Formula choice has a 2–5× effect on notification CTR (confirmed). Character length has been tested for Apple News views but not for notification CTR. Notifications truncate at ~80 chars on most devices, making length more likely to matter here than in feed headlines.

**Gap:** Character length vs. notification CTR has not been run. The notifications dataset covers 2025–2026 (1,050+ news brand pushes with CTR data) — sufficient for a Mann-Whitney test across length quartiles.

**Question:** Do shorter notifications (≤80 chars) outperform longer ones for CTR, controlling for formula type? Is there a character-count range where CTR peaks, or is the relationship monotonic (shorter = better)?

**How to run it:** Run on the existing notifications dataset (1,050+ news brand pushes with CTR). No new data collection needed. Bin notification headlines into four length quartiles. Run Kruskal-Wallis across quartiles first to check for any length–CTR association. If significant (p < 0.05), follow with Mann-Whitney U pairwise comparisons (Q1 vs. Q4 as primary), BH-FDR corrected. Control for formula type via stratification: run the length–CTR analysis separately within each formula group that has n ≥30 (attribution language, question, direct declarative). If length effect disappears within formula groups, length is a formula proxy, not an independent signal. Secondary analysis: Spearman correlation between character count and CTR (raw correlation, no quartiling). This gives a monotonicity check without binning artifacts. Implement in generate_site.py as an extension of the existing Q5 notification analysis block.

**What the result unlocks:** Confirmed: adds a second actionable lever for push copy editors beyond formula choice. Current guidance (“use attribution language”) would be extended with a specific character-count target.  Not confirmed: formula dominates; length doesn’t independently move CTR and editors can focus solely on formula selection for notifications.

### [Medium · Untested] Apple News — “What to Know” — Featured vs. Organic Stability by Year

**Signal:** Apple editors select “What to Know” at 1.8× the baseline rate for Featured placement. Organic (non-Featured) articles using WTK show no significant view lift (p<sub>adj</sub>=0.10). This editorial/algorithmic split is a key project finding — but whether it is stable across 2025 and 2026 separately is unknown.

**Gap:** The current analysis pools 2025 and 2026 Apple News data. If Apple has updated curation signals, or if T1 editors have changed how they use WTK, the featuring lift or organic penalty could be shifting — which would change whether the two-headline strategy is durable guidance.

**Question:** Is the WTK featuring lift consistent when 2025 and 2026 are analyzed separately? Has the gap between editorial selection rate and organic algorithmic performance been stable, or is it narrowing/widening over time?

**How to run it:** Run on existing Apple News data — no new collection needed. Split the Apple News dataset by year (2025 and 2026 separately). For each year, run: (1) Q2 chi-square or Fisher’s exact test for WTK featuring rate vs. all other formulas; (2) Q1 Mann-Whitney U for WTK organic view rank vs. untagged baseline (non-Featured articles only). Compare the featuring lift ratio (WTK featured rate / baseline featured rate) and the organic p-value across years. A narrowing featured rate ratio or a trending organic p-value signals platform behavior change. Implement as a year-stratified extension of the existing Q1 and Q2 analysis blocks in generate_site.py. Report: a 2×2 table of year×metric (featuring lift and organic p) alongside a directional trend flag. Note: Apple News 2026 covers Jan–Mar only; interpret with caution until Q3 2026 data is available.

**What the result unlocks:** Stable across years: confirms structural platform behavior. The “WTK for Featured campaigns, avoid for organic” rule is durable.  Shifting: guidance needs to evolve. If organic performance is catching up to editorial selection, the two-headline distinction may already be outdated.

### [Medium · Untested] Apple News — Possessive Named Entity — Topic Concentration

**Signal:** Possessive named entity headlines (n=95) show moderate overall performance on Apple News. The signal may be concentrated in sports and crime — topics where named individuals are central to the story — but aggregate analysis cannot confirm this.

**Gap:** Overall n=95 is small enough that splitting by topic reduces per-cell counts below the 30-article threshold for reliable inference. The aggregate analysis masks any strong within-topic signal.

**Question:** Do possessive named entity headlines specifically outperform in sports and crime topics on Apple News, where named individuals are central? Is the aggregate signal driven by a strong within-topic effect, or is it distributed broadly across all topics?

**How to run it:** Run on existing Apple News 2025+2026 data. Filter to possessive named entity headlines. Split by topic: sports+crime (the ‘high named-entity’ group) vs. all other topics. Run Mann-Whitney U (sports+crime PNE articles vs. untagged baseline within the same topics), rank-biserial r as effect size. Repeat for the ‘other topics’ group. Compare lift magnitudes: if the sports+crime lift is substantially larger (r ≥0.1 higher) than the other-topics lift, the signal is topic-concentrated. If lifts are similar, the rule applies broadly. If either per-topic cell has n < 20, flag as preliminary and hold until data grows. Do not split into individual topics at this sample size — aggregate sports+crime as one group. Implement as a topic-stratified extension of the Q1 analysis in generate_site.py.

**What the result unlocks:** Confirmed topic-specific: changes guidance from a broad rule to a targeted one (“use possessive named entity for sports/crime stories specifically”). Editors know exactly when to apply it.  Evenly distributed: the broad rule stands. Possessive named entity is generally useful, not vertically restricted.

### [Medium · Untested] SmartNews — Number Lead Type — Which Numbers Drive the SmartNews Signal?

**Signal:** Number leads show a positive directional trend on SmartNews (median rank 0.534 vs. 0.497 baseline; direction: above_dir). They are the only SmartNews formula with a positive directional signal. Whether count/list (‘3 ways’), dollar amounts (‘$2 billion’), or percentages (‘47%’) drive this has not been tested.

**Gap:** Number-type classification (classify_number_lead()) is implemented in the pipeline but per-type SmartNews performance has not been computed. SmartNews 2026 data is domain-aggregated (not article-level), limiting this analysis to the 2025 dataset (n=38,251 articles).

**Question:** Which number-lead subtype drives the SmartNews directional signal: count/list, dollar amounts, or percentages? Or is the effect evenly distributed across number types, suggesting format (any number in the lead) matters more than type?

**How to run it:** Run on SmartNews 2025 number-lead articles (n ≈342 total). classify_number_lead() already extracts ntype (‘count_list,’ ‘dollar_amount,’ ‘percentage,’ ‘other’). Group by ntype and run Mann-Whitney U for each group vs. the untagged baseline, BH-FDR corrected across the three tested types. Expected n per type: count_list is likely the largest (list articles are common); dollar_amount and percentage groups may be small. Flag any group with n < 20 as preliminary. If all subtypes have low n, aggregate and report directionally only: “counts/lists trend higher (n=X, p=Y)” without a significance claim. Implement by extending the existing number-lead deep-dive block (classify_number_lead() section) in generate_site.py to add a per-type Mann-Whitney analysis. Note: SmartNews 2026 is domain-aggregated and cannot contribute to this analysis — 2025 data only.

**What the result unlocks:** Confirmed specific type: editors can be told “count/list numbers work on SmartNews; dollar amounts and percentages are neutral.” More precise than the current directional number-lead guidance.  Equally distributed: the rule is format-driven (“any number in the lead is better than none”). Simpler and more broadly applicable.

---

## Run: 2026-04 (generated 2026-04-08T13:02:55)

_8 suggestion(s) this run_

### [↑ High · Bonferroni fail] SmartNews — “Here’s / Here are” Lift — Needs Confirmation

**Signal:** Articles using “Here’s / Here are” on SmartNews score a median percentile rank of 0.543 vs. 0.500 for the direct-declarative baseline (n=585, raw p=0.038). Direction is positive — opposite to question and “What to know” on the same platform.

**Gap:** Raw p=0.038 does not survive Bonferroni correction at k=5 formula families (threshold α/k = 0.010). All data is observational; no A/B comparison is available. Topic confounding (“Here’s” may correlate with better-performing story types) has not been controlled for.

**Question:** If T1 editors A/B tested “Here’s / Here are” against a direct-declarative version of the same story on SmartNews, would the formula version consistently outperform? Does the effect hold across topics (sports, crime, weather) or appear only in a topic subset?

**How to run it:** For 30–50 stories over 4–6 weeks, write two headline versions per story: (A) “Here’s / Here are” format and (B) a direct declarative covering the same facts. If the CMS supports A/B headline testing, use it; otherwise alternate formula by publication day or assign by outlet. Record SmartNews views at 7 days post-publish. Test: Mann-Whitney U on SmartNews views (A vs. B), rank-biserial r as effect size. Minimum n = 30 matched story pairs for reliable inference. Stratify by topic (sports/crime/weather vs. other) to check whether any interaction hides or drives the aggregate result. Do not use the same story on Apple News A/B — keep platforms separate to avoid contamination.

**What the result unlocks:** Confirmed: adds a positive SmartNews formula signal — currently all confirmed SmartNews guidance is avoidance-only. Editors could be told “Here’s works on SmartNews, unlike Apple News where WTK dominates featuring.”  Not confirmed: SmartNews playbook stays avoidance-only; the directional positive for “Here’s” is noise or topic-driven.

### [Medium · Underpowered] Apple News — Number Lead Specificity — Round vs. Exact Figures

**Signal:** Specific numbers (e.g. ‘$487M’, ‘13 deaths’) score a median rank of 0.405 vs. 0.277 for round numbers on Apple News (n = 165 specific, 21 round)

**Gap:** Groups too small for a reliable test: round n=21, specific n=165.

**Question:** Do Apple News headlines with precise numeric values (e.g. ‘$487 million,’ ‘13 officers’) consistently outperform rounded equivalents (‘$500 million,’ ‘10+ officers’) for views, controlling for topic and story type?

**How to run it:** When writing number-lead headlines, deliberately tag each as ‘round’ (e.g. ‘$500M,’ ‘10 people’) or ‘specific’ (e.g. ‘$487M,’ ‘13 people’) in a shared tracking sheet. Collect at least 30 Apple News articles per type before running the test. No CMS change needed — this is a tagging discipline applied during headline writing. Analysis: Mann-Whitney U on Apple News percentile rank at 7 days (specific vs. round), rank-biserial r as effect size. Stratify by topic (financial stories likely have more specificity variance than crime or sports). Existing pipeline: classify_number_lead() already extracts the numeric value — add a roundness tag to the tracking sheet and re-run once 30+ per group are tagged.

**What the result unlocks:** Confirmed: adds precision-number guidance to the style guide (“use exact figures in number leads, not rounded approximations”). Editors who default to rounded figures for readability would be asked to reverse that practice.  Not confirmed: round vs. specific distinction does not affect views; the number-lead signal is format-driven rather than specificity-driven.

### [↑ High · Underpowered] MSN — MSN Formula Groups — Insufficient Data for Confirmation

**Signal:** 1 formula group(s) show directional patterns on MSN but cannot be confirmed: Quoted lede. 113 total T1 news brand articles after filtering. Groups with n < 30: Quoted lede (n=18).

**Gap:** All flagged groups have n < 30, below the minimum for reliable inference (GOVERNOR.md Part 2). Only the quoted-lede group currently has enough data to test, and it is the one confirmed MSN finding. The MSN dataset grows approximately 100 rows/month; most formula groups should cross n=30 within 2–3 months of continued data collection.

**Question:** As MSN data accumulates, which formula groups consistently underperform the direct-declarative baseline? Is the underperformance pattern broad (all structured formulas hurt on MSN) or specific to certain formats?

**How to run it:** Natural experiment — no new data collection needed. The MSN dataset grows approximately 100 rows/month after the T1 brand filter. Re-run the Mann-Whitney formula analysis each monthly ingest; generate_site.py already does this automatically and the build report surfaces newly-significant groups. Threshold: treat any formula group as testable once it crosses n = 30. Expected timeline: most groups should reach n=30 within 2–3 monthly ingest cycles. Analysis: Mann-Whitney U (each formula group vs. untagged baseline), BH-FDR corrected across all tested groups simultaneously, rank-biserial r as effect size. Language tier: significant only if p_adj < 0.05; directional if p_adj < 0.10. Baseline key must be ‘untagged’ (not ‘other’) — see GOVERNOR.md Rigor Failures Log.

**What the result unlocks:** Confirmed broad pattern: extends the MSN rule from ‘avoid quoted lede’ to ‘avoid all structured formulas.’ Gives editors the strongest possible two-headline guidance: Apple News → use formulas; MSN → drop them entirely.  Confirmed specific subset: MSN avoidance list grows to the confirmed formula types while others remain neutral.  Not confirmed: MSN formula penalty is limited to quoted lede only.

### [↑ High · Untested] Apple News — Character Length × Formula Type Interaction

**Signal:** Character length (90–120 chars) and formula type independently predict Apple News views. Whether these signals interact — e.g., whether possessive named entity needs to be longer to achieve its lift, or whether “Here’s” works at any length — has not been tested.

**Gap:** Cross-tabulating formula buckets with length quartiles fragments an already-segmented dataset. Most formula × length cells will have n < 30, requiring aggregation trade-offs that risk obscuring the interaction signal. Analysis not yet run.

**Question:** Do specific formula types require specific length ranges to achieve their Apple News performance lift? E.g., does “Here’s / Here are” need 90+ chars to work, or does it lift at any length? Does possessive named entity perform best at shorter lengths where the name dominates the headline?

**How to run it:** Run on existing Apple News 2025+2026 data — no new collection needed. Cross-tabulate by formula type × length quartile. For each formula with n ≥30 total, split into Q1 (shortest) and Q4 (longest) length buckets and run Mann-Whitney U within each formula group vs. the untagged baseline at the same length. Compare the lift magnitude across length buckets. If any formula×length cell has n < 15, aggregate: fold Q1+Q2 into ‘short’ and Q3+Q4 into ‘long.’ Report as an interaction: does the formula’s lift increase, decrease, or stay flat as length increases? Plot as a 2×2 heatmap (formula × length bucket, colored by median rank). Apply BH-FDR correction across all formula×length cells tested. Bonferroni fallback: if more than 10 cells are tested, apply Bonferroni at k=10 as a secondary check.

**What the result unlocks:** Confirmed interaction: compound guidance (formula + length range) replaces two independent rules. Editors get: “Use Here’s at 90–110 chars; use possessive at 70–90 chars.” More actionable than current guidance.  No interaction: the two independent rules are stable and can be applied separately without worrying about their interaction.

### [↑ High · Untested] Notifications — Notification CTR × Character Length

**Signal:** Formula choice has a 2–5× effect on notification CTR (confirmed). Character length has been tested for Apple News views but not for notification CTR. Notifications truncate at ~80 chars on most devices, making length more likely to matter here than in feed headlines.

**Gap:** Character length vs. notification CTR has not been run. The notifications dataset covers 2025–2026 (1,050+ news brand pushes with CTR data) — sufficient for a Mann-Whitney test across length quartiles.

**Question:** Do shorter notifications (≤80 chars) outperform longer ones for CTR, controlling for formula type? Is there a character-count range where CTR peaks, or is the relationship monotonic (shorter = better)?

**How to run it:** Run on the existing notifications dataset (1,050+ news brand pushes with CTR). No new data collection needed. Bin notification headlines into four length quartiles. Run Kruskal-Wallis across quartiles first to check for any length–CTR association. If significant (p < 0.05), follow with Mann-Whitney U pairwise comparisons (Q1 vs. Q4 as primary), BH-FDR corrected. Control for formula type via stratification: run the length–CTR analysis separately within each formula group that has n ≥30 (attribution language, question, direct declarative). If length effect disappears within formula groups, length is a formula proxy, not an independent signal. Secondary analysis: Spearman correlation between character count and CTR (raw correlation, no quartiling). This gives a monotonicity check without binning artifacts. Implement in generate_site.py as an extension of the existing Q5 notification analysis block.

**What the result unlocks:** Confirmed: adds a second actionable lever for push copy editors beyond formula choice. Current guidance (“use attribution language”) would be extended with a specific character-count target.  Not confirmed: formula dominates; length doesn’t independently move CTR and editors can focus solely on formula selection for notifications.

### [Medium · Untested] Apple News — “What to Know” — Featured vs. Organic Stability by Year

**Signal:** Apple editors select “What to Know” at 1.8× the baseline rate for Featured placement. Organic (non-Featured) articles using WTK show no significant view lift (p<sub>adj</sub>=0.10). This editorial/algorithmic split is a key project finding — but whether it is stable across 2025 and 2026 separately is unknown.

**Gap:** The current analysis pools 2025 and 2026 Apple News data. If Apple has updated curation signals, or if T1 editors have changed how they use WTK, the featuring lift or organic penalty could be shifting — which would change whether the two-headline strategy is durable guidance.

**Question:** Is the WTK featuring lift consistent when 2025 and 2026 are analyzed separately? Has the gap between editorial selection rate and organic algorithmic performance been stable, or is it narrowing/widening over time?

**How to run it:** Run on existing Apple News data — no new collection needed. Split the Apple News dataset by year (2025 and 2026 separately). For each year, run: (1) Q2 chi-square or Fisher’s exact test for WTK featuring rate vs. all other formulas; (2) Q1 Mann-Whitney U for WTK organic view rank vs. untagged baseline (non-Featured articles only). Compare the featuring lift ratio (WTK featured rate / baseline featured rate) and the organic p-value across years. A narrowing featured rate ratio or a trending organic p-value signals platform behavior change. Implement as a year-stratified extension of the existing Q1 and Q2 analysis blocks in generate_site.py. Report: a 2×2 table of year×metric (featuring lift and organic p) alongside a directional trend flag. Note: Apple News 2026 covers Jan–Mar only; interpret with caution until Q3 2026 data is available.

**What the result unlocks:** Stable across years: confirms structural platform behavior. The “WTK for Featured campaigns, avoid for organic” rule is durable.  Shifting: guidance needs to evolve. If organic performance is catching up to editorial selection, the two-headline distinction may already be outdated.

### [Medium · Untested] Apple News — Possessive Named Entity — Topic Concentration

**Signal:** Possessive named entity headlines (n=95) show moderate overall performance on Apple News. The signal may be concentrated in sports and crime — topics where named individuals are central to the story — but aggregate analysis cannot confirm this.

**Gap:** Overall n=95 is small enough that splitting by topic reduces per-cell counts below the 30-article threshold for reliable inference. The aggregate analysis masks any strong within-topic signal.

**Question:** Do possessive named entity headlines specifically outperform in sports and crime topics on Apple News, where named individuals are central? Is the aggregate signal driven by a strong within-topic effect, or is it distributed broadly across all topics?

**How to run it:** Run on existing Apple News 2025+2026 data. Filter to possessive named entity headlines. Split by topic: sports+crime (the ‘high named-entity’ group) vs. all other topics. Run Mann-Whitney U (sports+crime PNE articles vs. untagged baseline within the same topics), rank-biserial r as effect size. Repeat for the ‘other topics’ group. Compare lift magnitudes: if the sports+crime lift is substantially larger (r ≥0.1 higher) than the other-topics lift, the signal is topic-concentrated. If lifts are similar, the rule applies broadly. If either per-topic cell has n < 20, flag as preliminary and hold until data grows. Do not split into individual topics at this sample size — aggregate sports+crime as one group. Implement as a topic-stratified extension of the Q1 analysis in generate_site.py.

**What the result unlocks:** Confirmed topic-specific: changes guidance from a broad rule to a targeted one (“use possessive named entity for sports/crime stories specifically”). Editors know exactly when to apply it.  Evenly distributed: the broad rule stands. Possessive named entity is generally useful, not vertically restricted.

### [Medium · Untested] SmartNews — Number Lead Type — Which Numbers Drive the SmartNews Signal?

**Signal:** Number leads show a positive directional trend on SmartNews (median rank 0.534 vs. 0.497 baseline; direction: above_dir). They are the only SmartNews formula with a positive directional signal. Whether count/list (‘3 ways’), dollar amounts (‘$2 billion’), or percentages (‘47%’) drive this has not been tested.

**Gap:** Number-type classification (classify_number_lead()) is implemented in the pipeline but per-type SmartNews performance has not been computed. SmartNews 2026 data is domain-aggregated (not article-level), limiting this analysis to the 2025 dataset (n=38,251 articles).

**Question:** Which number-lead subtype drives the SmartNews directional signal: count/list, dollar amounts, or percentages? Or is the effect evenly distributed across number types, suggesting format (any number in the lead) matters more than type?

**How to run it:** Run on SmartNews 2025 number-lead articles (n ≈342 total). classify_number_lead() already extracts ntype (‘count_list,’ ‘dollar_amount,’ ‘percentage,’ ‘other’). Group by ntype and run Mann-Whitney U for each group vs. the untagged baseline, BH-FDR corrected across the three tested types. Expected n per type: count_list is likely the largest (list articles are common); dollar_amount and percentage groups may be small. Flag any group with n < 20 as preliminary. If all subtypes have low n, aggregate and report directionally only: “counts/lists trend higher (n=X, p=Y)” without a significance claim. Implement by extending the existing number-lead deep-dive block (classify_number_lead() section) in generate_site.py to add a per-type Mann-Whitney analysis. Note: SmartNews 2026 is domain-aggregated and cannot contribute to this analysis — 2025 data only.

**What the result unlocks:** Confirmed specific type: editors can be told “count/list numbers work on SmartNews; dollar amounts and percentages are neutral.” More precise than the current directional number-lead guidance.  Equally distributed: the rule is format-driven (“any number in the lead is better than none”). Simpler and more broadly applicable.

---

## Run: 2026-04 (generated 2026-04-08T13:04:33)

_8 suggestion(s) this run_

### [↑ High · Bonferroni fail] SmartNews — “Here’s / Here are” Lift — Needs Confirmation

**Signal:** Articles using “Here’s / Here are” on SmartNews score a median percentile rank of 0.543 vs. 0.500 for the direct-declarative baseline (n=585, raw p=0.038). Direction is positive — opposite to question and “What to know” on the same platform.

**Gap:** Raw p=0.038 does not survive Bonferroni correction at k=5 formula families (threshold α/k = 0.010). All data is observational; no A/B comparison is available. Topic confounding (“Here’s” may correlate with better-performing story types) has not been controlled for.

**Question:** If T1 editors A/B tested “Here’s / Here are” against a direct-declarative version of the same story on SmartNews, would the formula version consistently outperform? Does the effect hold across topics (sports, crime, weather) or appear only in a topic subset?

**How to run it:** For 30–50 stories over 4–6 weeks, write two headline versions per story: (A) “Here’s / Here are” format and (B) a direct declarative covering the same facts. If the CMS supports A/B headline testing, use it; otherwise alternate formula by publication day or assign by outlet. Record SmartNews views at 7 days post-publish. Test: Mann-Whitney U on SmartNews views (A vs. B), rank-biserial r as effect size. Minimum n = 30 matched story pairs for reliable inference. Stratify by topic (sports/crime/weather vs. other) to check whether any interaction hides or drives the aggregate result. Do not use the same story on Apple News A/B — keep platforms separate to avoid contamination.

**What the result unlocks:** Confirmed: adds a positive SmartNews formula signal — currently all confirmed SmartNews guidance is avoidance-only. Editors could be told “Here’s works on SmartNews, unlike Apple News where WTK dominates featuring.”  Not confirmed: SmartNews playbook stays avoidance-only; the directional positive for “Here’s” is noise or topic-driven.

### [Medium · Underpowered] Apple News — Number Lead Specificity — Round vs. Exact Figures

**Signal:** Specific numbers (e.g. ‘$487M’, ‘13 deaths’) score a median rank of 0.405 vs. 0.277 for round numbers on Apple News (n = 165 specific, 21 round)

**Gap:** Groups too small for a reliable test: round n=21, specific n=165.

**Question:** Do Apple News headlines with precise numeric values (e.g. ‘$487 million,’ ‘13 officers’) consistently outperform rounded equivalents (‘$500 million,’ ‘10+ officers’) for views, controlling for topic and story type?

**How to run it:** When writing number-lead headlines, deliberately tag each as ‘round’ (e.g. ‘$500M,’ ‘10 people’) or ‘specific’ (e.g. ‘$487M,’ ‘13 people’) in a shared tracking sheet. Collect at least 30 Apple News articles per type before running the test. No CMS change needed — this is a tagging discipline applied during headline writing. Analysis: Mann-Whitney U on Apple News percentile rank at 7 days (specific vs. round), rank-biserial r as effect size. Stratify by topic (financial stories likely have more specificity variance than crime or sports). Existing pipeline: classify_number_lead() already extracts the numeric value — add a roundness tag to the tracking sheet and re-run once 30+ per group are tagged.

**What the result unlocks:** Confirmed: adds precision-number guidance to the style guide (“use exact figures in number leads, not rounded approximations”). Editors who default to rounded figures for readability would be asked to reverse that practice.  Not confirmed: round vs. specific distinction does not affect views; the number-lead signal is format-driven rather than specificity-driven.

### [↑ High · Underpowered] MSN — MSN Formula Groups — Insufficient Data for Confirmation

**Signal:** 1 formula group(s) show directional patterns on MSN but cannot be confirmed: Quoted lede. 113 total T1 news brand articles after filtering. Groups with n < 30: Quoted lede (n=18).

**Gap:** All flagged groups have n < 30, below the minimum for reliable inference (GOVERNOR.md Part 2). Only the quoted-lede group currently has enough data to test, and it is the one confirmed MSN finding. The MSN dataset grows approximately 100 rows/month; most formula groups should cross n=30 within 2–3 months of continued data collection.

**Question:** As MSN data accumulates, which formula groups consistently underperform the direct-declarative baseline? Is the underperformance pattern broad (all structured formulas hurt on MSN) or specific to certain formats?

**How to run it:** Natural experiment — no new data collection needed. The MSN dataset grows approximately 100 rows/month after the T1 brand filter. Re-run the Mann-Whitney formula analysis each monthly ingest; generate_site.py already does this automatically and the build report surfaces newly-significant groups. Threshold: treat any formula group as testable once it crosses n = 30. Expected timeline: most groups should reach n=30 within 2–3 monthly ingest cycles. Analysis: Mann-Whitney U (each formula group vs. untagged baseline), BH-FDR corrected across all tested groups simultaneously, rank-biserial r as effect size. Language tier: significant only if p_adj < 0.05; directional if p_adj < 0.10. Baseline key must be ‘untagged’ (not ‘other’) — see GOVERNOR.md Rigor Failures Log.

**What the result unlocks:** Confirmed broad pattern: extends the MSN rule from ‘avoid quoted lede’ to ‘avoid all structured formulas.’ Gives editors the strongest possible two-headline guidance: Apple News → use formulas; MSN → drop them entirely.  Confirmed specific subset: MSN avoidance list grows to the confirmed formula types while others remain neutral.  Not confirmed: MSN formula penalty is limited to quoted lede only.

### [↑ High · Untested] Apple News — Character Length × Formula Type Interaction

**Signal:** Character length (90–120 chars) and formula type independently predict Apple News views. Whether these signals interact — e.g., whether possessive named entity needs to be longer to achieve its lift, or whether “Here’s” works at any length — has not been tested.

**Gap:** Cross-tabulating formula buckets with length quartiles fragments an already-segmented dataset. Most formula × length cells will have n < 30, requiring aggregation trade-offs that risk obscuring the interaction signal. Analysis not yet run.

**Question:** Do specific formula types require specific length ranges to achieve their Apple News performance lift? E.g., does “Here’s / Here are” need 90+ chars to work, or does it lift at any length? Does possessive named entity perform best at shorter lengths where the name dominates the headline?

**How to run it:** Run on existing Apple News 2025+2026 data — no new collection needed. Cross-tabulate by formula type × length quartile. For each formula with n ≥30 total, split into Q1 (shortest) and Q4 (longest) length buckets and run Mann-Whitney U within each formula group vs. the untagged baseline at the same length. Compare the lift magnitude across length buckets. If any formula×length cell has n < 15, aggregate: fold Q1+Q2 into ‘short’ and Q3+Q4 into ‘long.’ Report as an interaction: does the formula’s lift increase, decrease, or stay flat as length increases? Plot as a 2×2 heatmap (formula × length bucket, colored by median rank). Apply BH-FDR correction across all formula×length cells tested. Bonferroni fallback: if more than 10 cells are tested, apply Bonferroni at k=10 as a secondary check.

**What the result unlocks:** Confirmed interaction: compound guidance (formula + length range) replaces two independent rules. Editors get: “Use Here’s at 90–110 chars; use possessive at 70–90 chars.” More actionable than current guidance.  No interaction: the two independent rules are stable and can be applied separately without worrying about their interaction.

### [↑ High · Untested] Notifications — Notification CTR × Character Length

**Signal:** Formula choice has a 2–5× effect on notification CTR (confirmed). Character length has been tested for Apple News views but not for notification CTR. Notifications truncate at ~80 chars on most devices, making length more likely to matter here than in feed headlines.

**Gap:** Character length vs. notification CTR has not been run. The notifications dataset covers 2025–2026 (1,050+ news brand pushes with CTR data) — sufficient for a Mann-Whitney test across length quartiles.

**Question:** Do shorter notifications (≤80 chars) outperform longer ones for CTR, controlling for formula type? Is there a character-count range where CTR peaks, or is the relationship monotonic (shorter = better)?

**How to run it:** Run on the existing notifications dataset (1,050+ news brand pushes with CTR). No new data collection needed. Bin notification headlines into four length quartiles. Run Kruskal-Wallis across quartiles first to check for any length–CTR association. If significant (p < 0.05), follow with Mann-Whitney U pairwise comparisons (Q1 vs. Q4 as primary), BH-FDR corrected. Control for formula type via stratification: run the length–CTR analysis separately within each formula group that has n ≥30 (attribution language, question, direct declarative). If length effect disappears within formula groups, length is a formula proxy, not an independent signal. Secondary analysis: Spearman correlation between character count and CTR (raw correlation, no quartiling). This gives a monotonicity check without binning artifacts. Implement in generate_site.py as an extension of the existing Q5 notification analysis block.

**What the result unlocks:** Confirmed: adds a second actionable lever for push copy editors beyond formula choice. Current guidance (“use attribution language”) would be extended with a specific character-count target.  Not confirmed: formula dominates; length doesn’t independently move CTR and editors can focus solely on formula selection for notifications.

### [Medium · Untested] Apple News — “What to Know” — Featured vs. Organic Stability by Year

**Signal:** Apple editors select “What to Know” at 1.8× the baseline rate for Featured placement. Organic (non-Featured) articles using WTK show no significant view lift (p<sub>adj</sub>=0.10). This editorial/algorithmic split is a key project finding — but whether it is stable across 2025 and 2026 separately is unknown.

**Gap:** The current analysis pools 2025 and 2026 Apple News data. If Apple has updated curation signals, or if T1 editors have changed how they use WTK, the featuring lift or organic penalty could be shifting — which would change whether the two-headline strategy is durable guidance.

**Question:** Is the WTK featuring lift consistent when 2025 and 2026 are analyzed separately? Has the gap between editorial selection rate and organic algorithmic performance been stable, or is it narrowing/widening over time?

**How to run it:** Run on existing Apple News data — no new collection needed. Split the Apple News dataset by year (2025 and 2026 separately). For each year, run: (1) Q2 chi-square or Fisher’s exact test for WTK featuring rate vs. all other formulas; (2) Q1 Mann-Whitney U for WTK organic view rank vs. untagged baseline (non-Featured articles only). Compare the featuring lift ratio (WTK featured rate / baseline featured rate) and the organic p-value across years. A narrowing featured rate ratio or a trending organic p-value signals platform behavior change. Implement as a year-stratified extension of the existing Q1 and Q2 analysis blocks in generate_site.py. Report: a 2×2 table of year×metric (featuring lift and organic p) alongside a directional trend flag. Note: Apple News 2026 covers Jan–Mar only; interpret with caution until Q3 2026 data is available.

**What the result unlocks:** Stable across years: confirms structural platform behavior. The “WTK for Featured campaigns, avoid for organic” rule is durable.  Shifting: guidance needs to evolve. If organic performance is catching up to editorial selection, the two-headline distinction may already be outdated.

### [Medium · Untested] Apple News — Possessive Named Entity — Topic Concentration

**Signal:** Possessive named entity headlines (n=95) show moderate overall performance on Apple News. The signal may be concentrated in sports and crime — topics where named individuals are central to the story — but aggregate analysis cannot confirm this.

**Gap:** Overall n=95 is small enough that splitting by topic reduces per-cell counts below the 30-article threshold for reliable inference. The aggregate analysis masks any strong within-topic signal.

**Question:** Do possessive named entity headlines specifically outperform in sports and crime topics on Apple News, where named individuals are central? Is the aggregate signal driven by a strong within-topic effect, or is it distributed broadly across all topics?

**How to run it:** Run on existing Apple News 2025+2026 data. Filter to possessive named entity headlines. Split by topic: sports+crime (the ‘high named-entity’ group) vs. all other topics. Run Mann-Whitney U (sports+crime PNE articles vs. untagged baseline within the same topics), rank-biserial r as effect size. Repeat for the ‘other topics’ group. Compare lift magnitudes: if the sports+crime lift is substantially larger (r ≥0.1 higher) than the other-topics lift, the signal is topic-concentrated. If lifts are similar, the rule applies broadly. If either per-topic cell has n < 20, flag as preliminary and hold until data grows. Do not split into individual topics at this sample size — aggregate sports+crime as one group. Implement as a topic-stratified extension of the Q1 analysis in generate_site.py.

**What the result unlocks:** Confirmed topic-specific: changes guidance from a broad rule to a targeted one (“use possessive named entity for sports/crime stories specifically”). Editors know exactly when to apply it.  Evenly distributed: the broad rule stands. Possessive named entity is generally useful, not vertically restricted.

### [Medium · Untested] SmartNews — Number Lead Type — Which Numbers Drive the SmartNews Signal?

**Signal:** Number leads show a positive directional trend on SmartNews (median rank 0.534 vs. 0.497 baseline; direction: above_dir). They are the only SmartNews formula with a positive directional signal. Whether count/list (‘3 ways’), dollar amounts (‘$2 billion’), or percentages (‘47%’) drive this has not been tested.

**Gap:** Number-type classification (classify_number_lead()) is implemented in the pipeline but per-type SmartNews performance has not been computed. SmartNews 2026 data is domain-aggregated (not article-level), limiting this analysis to the 2025 dataset (n=38,251 articles).

**Question:** Which number-lead subtype drives the SmartNews directional signal: count/list, dollar amounts, or percentages? Or is the effect evenly distributed across number types, suggesting format (any number in the lead) matters more than type?

**How to run it:** Run on SmartNews 2025 number-lead articles (n ≈342 total). classify_number_lead() already extracts ntype (‘count_list,’ ‘dollar_amount,’ ‘percentage,’ ‘other’). Group by ntype and run Mann-Whitney U for each group vs. the untagged baseline, BH-FDR corrected across the three tested types. Expected n per type: count_list is likely the largest (list articles are common); dollar_amount and percentage groups may be small. Flag any group with n < 20 as preliminary. If all subtypes have low n, aggregate and report directionally only: “counts/lists trend higher (n=X, p=Y)” without a significance claim. Implement by extending the existing number-lead deep-dive block (classify_number_lead() section) in generate_site.py to add a per-type Mann-Whitney analysis. Note: SmartNews 2026 is domain-aggregated and cannot contribute to this analysis — 2025 data only.

**What the result unlocks:** Confirmed specific type: editors can be told “count/list numbers work on SmartNews; dollar amounts and percentages are neutral.” More precise than the current directional number-lead guidance.  Equally distributed: the rule is format-driven (“any number in the lead is better than none”). Simpler and more broadly applicable.

---

## Run: 2026-04 (generated 2026-04-08T13:36:54)

_8 suggestion(s) this run_

### [↑ High · Bonferroni fail] SmartNews — “Here’s / Here are” Lift — Needs Confirmation

**Signal:** Articles using “Here’s / Here are” on SmartNews score a median percentile rank of 0.543 vs. 0.500 for the direct-declarative baseline (n=585, raw p=0.038). Direction is positive — opposite to question and “What to know” on the same platform.

**Gap:** Raw p=0.038 does not survive Bonferroni correction at k=5 formula families (threshold α/k = 0.010). All data is observational; no A/B comparison is available. Topic confounding (“Here’s” may correlate with better-performing story types) has not been controlled for.

**Question:** If T1 editors A/B tested “Here’s / Here are” against a direct-declarative version of the same story on SmartNews, would the formula version consistently outperform? Does the effect hold across topics (sports, crime, weather) or appear only in a topic subset?

**How to run it:** For 30–50 stories over 4–6 weeks, write two headline versions per story: (A) “Here’s / Here are” format and (B) a direct declarative covering the same facts. If the CMS supports A/B headline testing, use it; otherwise alternate formula by publication day or assign by outlet. Record SmartNews views at 7 days post-publish. Test: Mann-Whitney U on SmartNews views (A vs. B), rank-biserial r as effect size. Minimum n = 30 matched story pairs for reliable inference. Stratify by topic (sports/crime/weather vs. other) to check whether any interaction hides or drives the aggregate result. Do not use the same story on Apple News A/B — keep platforms separate to avoid contamination.

**What the result unlocks:** Confirmed: adds a positive SmartNews formula signal — currently all confirmed SmartNews guidance is avoidance-only. Editors could be told “Here’s works on SmartNews, unlike Apple News where WTK dominates featuring.”  Not confirmed: SmartNews playbook stays avoidance-only; the directional positive for “Here’s” is noise or topic-driven.

### [Medium · Underpowered] Apple News — Number Lead Specificity — Round vs. Exact Figures

**Signal:** Specific numbers (e.g. ‘$487M’, ‘13 deaths’) score a median rank of 0.405 vs. 0.277 for round numbers on Apple News (n = 165 specific, 21 round)

**Gap:** Groups too small for a reliable test: round n=21, specific n=165.

**Question:** Do Apple News headlines with precise numeric values (e.g. ‘$487 million,’ ‘13 officers’) consistently outperform rounded equivalents (‘$500 million,’ ‘10+ officers’) for views, controlling for topic and story type?

**How to run it:** When writing number-lead headlines, deliberately tag each as ‘round’ (e.g. ‘$500M,’ ‘10 people’) or ‘specific’ (e.g. ‘$487M,’ ‘13 people’) in a shared tracking sheet. Collect at least 30 Apple News articles per type before running the test. No CMS change needed — this is a tagging discipline applied during headline writing. Analysis: Mann-Whitney U on Apple News percentile rank at 7 days (specific vs. round), rank-biserial r as effect size. Stratify by topic (financial stories likely have more specificity variance than crime or sports). Existing pipeline: classify_number_lead() already extracts the numeric value — add a roundness tag to the tracking sheet and re-run once 30+ per group are tagged.

**What the result unlocks:** Confirmed: adds precision-number guidance to the style guide (“use exact figures in number leads, not rounded approximations”). Editors who default to rounded figures for readability would be asked to reverse that practice.  Not confirmed: round vs. specific distinction does not affect views; the number-lead signal is format-driven rather than specificity-driven.

### [↑ High · Underpowered] MSN — MSN Formula Groups — Insufficient Data for Confirmation

**Signal:** 1 formula group(s) show directional patterns on MSN but cannot be confirmed: Quoted lede. 113 total T1 news brand articles after filtering. Groups with n < 30: Quoted lede (n=18).

**Gap:** All flagged groups have n < 30, below the minimum for reliable inference (GOVERNOR.md Part 2). Only the quoted-lede group currently has enough data to test, and it is the one confirmed MSN finding. The MSN dataset grows approximately 100 rows/month; most formula groups should cross n=30 within 2–3 months of continued data collection.

**Question:** As MSN data accumulates, which formula groups consistently underperform the direct-declarative baseline? Is the underperformance pattern broad (all structured formulas hurt on MSN) or specific to certain formats?

**How to run it:** Natural experiment — no new data collection needed. The MSN dataset grows approximately 100 rows/month after the T1 brand filter. Re-run the Mann-Whitney formula analysis each monthly ingest; generate_site.py already does this automatically and the build report surfaces newly-significant groups. Threshold: treat any formula group as testable once it crosses n = 30. Expected timeline: most groups should reach n=30 within 2–3 monthly ingest cycles. Analysis: Mann-Whitney U (each formula group vs. untagged baseline), BH-FDR corrected across all tested groups simultaneously, rank-biserial r as effect size. Language tier: significant only if p_adj < 0.05; directional if p_adj < 0.10. Baseline key must be ‘untagged’ (not ‘other’) — see GOVERNOR.md Rigor Failures Log.

**What the result unlocks:** Confirmed broad pattern: extends the MSN rule from ‘avoid quoted lede’ to ‘avoid all structured formulas.’ Gives editors the strongest possible two-headline guidance: Apple News → use formulas; MSN → drop them entirely.  Confirmed specific subset: MSN avoidance list grows to the confirmed formula types while others remain neutral.  Not confirmed: MSN formula penalty is limited to quoted lede only.

### [↑ High · Untested] Apple News — Character Length × Formula Type Interaction

**Signal:** Character length (90–120 chars) and formula type independently predict Apple News views. Whether these signals interact — e.g., whether possessive named entity needs to be longer to achieve its lift, or whether “Here’s” works at any length — has not been tested.

**Gap:** Cross-tabulating formula buckets with length quartiles fragments an already-segmented dataset. Most formula × length cells will have n < 30, requiring aggregation trade-offs that risk obscuring the interaction signal. Analysis not yet run.

**Question:** Do specific formula types require specific length ranges to achieve their Apple News performance lift? E.g., does “Here’s / Here are” need 90+ chars to work, or does it lift at any length? Does possessive named entity perform best at shorter lengths where the name dominates the headline?

**How to run it:** Run on existing Apple News 2025+2026 data — no new collection needed. Cross-tabulate by formula type × length quartile. For each formula with n ≥30 total, split into Q1 (shortest) and Q4 (longest) length buckets and run Mann-Whitney U within each formula group vs. the untagged baseline at the same length. Compare the lift magnitude across length buckets. If any formula×length cell has n < 15, aggregate: fold Q1+Q2 into ‘short’ and Q3+Q4 into ‘long.’ Report as an interaction: does the formula’s lift increase, decrease, or stay flat as length increases? Plot as a 2×2 heatmap (formula × length bucket, colored by median rank). Apply BH-FDR correction across all formula×length cells tested. Bonferroni fallback: if more than 10 cells are tested, apply Bonferroni at k=10 as a secondary check.

**What the result unlocks:** Confirmed interaction: compound guidance (formula + length range) replaces two independent rules. Editors get: “Use Here’s at 90–110 chars; use possessive at 70–90 chars.” More actionable than current guidance.  No interaction: the two independent rules are stable and can be applied separately without worrying about their interaction.

### [↑ High · Untested] Notifications — Notification CTR × Character Length

**Signal:** Formula choice has a 2–5× effect on notification CTR (confirmed). Character length has been tested for Apple News views but not for notification CTR. Notifications truncate at ~80 chars on most devices, making length more likely to matter here than in feed headlines.

**Gap:** Character length vs. notification CTR has not been run. The notifications dataset covers 2025–2026 (1,050+ news brand pushes with CTR data) — sufficient for a Mann-Whitney test across length quartiles.

**Question:** Do shorter notifications (≤80 chars) outperform longer ones for CTR, controlling for formula type? Is there a character-count range where CTR peaks, or is the relationship monotonic (shorter = better)?

**How to run it:** Run on the existing notifications dataset (1,050+ news brand pushes with CTR). No new data collection needed. Bin notification headlines into four length quartiles. Run Kruskal-Wallis across quartiles first to check for any length–CTR association. If significant (p < 0.05), follow with Mann-Whitney U pairwise comparisons (Q1 vs. Q4 as primary), BH-FDR corrected. Control for formula type via stratification: run the length–CTR analysis separately within each formula group that has n ≥30 (attribution language, question, direct declarative). If length effect disappears within formula groups, length is a formula proxy, not an independent signal. Secondary analysis: Spearman correlation between character count and CTR (raw correlation, no quartiling). This gives a monotonicity check without binning artifacts. Implement in generate_site.py as an extension of the existing Q5 notification analysis block.

**What the result unlocks:** Confirmed: adds a second actionable lever for push copy editors beyond formula choice. Current guidance (“use attribution language”) would be extended with a specific character-count target.  Not confirmed: formula dominates; length doesn’t independently move CTR and editors can focus solely on formula selection for notifications.

### [Medium · Untested] Apple News — “What to Know” — Featured vs. Organic Stability by Year

**Signal:** Apple editors select “What to Know” at 1.8× the baseline rate for Featured placement. Organic (non-Featured) articles using WTK show no significant view lift (p<sub>adj</sub>=0.10). This editorial/algorithmic split is a key project finding — but whether it is stable across 2025 and 2026 separately is unknown.

**Gap:** The current analysis pools 2025 and 2026 Apple News data. If Apple has updated curation signals, or if T1 editors have changed how they use WTK, the featuring lift or organic penalty could be shifting — which would change whether the two-headline strategy is durable guidance.

**Question:** Is the WTK featuring lift consistent when 2025 and 2026 are analyzed separately? Has the gap between editorial selection rate and organic algorithmic performance been stable, or is it narrowing/widening over time?

**How to run it:** Run on existing Apple News data — no new collection needed. Split the Apple News dataset by year (2025 and 2026 separately). For each year, run: (1) Q2 chi-square or Fisher’s exact test for WTK featuring rate vs. all other formulas; (2) Q1 Mann-Whitney U for WTK organic view rank vs. untagged baseline (non-Featured articles only). Compare the featuring lift ratio (WTK featured rate / baseline featured rate) and the organic p-value across years. A narrowing featured rate ratio or a trending organic p-value signals platform behavior change. Implement as a year-stratified extension of the existing Q1 and Q2 analysis blocks in generate_site.py. Report: a 2×2 table of year×metric (featuring lift and organic p) alongside a directional trend flag. Note: Apple News 2026 covers Jan–Mar only; interpret with caution until Q3 2026 data is available.

**What the result unlocks:** Stable across years: confirms structural platform behavior. The “WTK for Featured campaigns, avoid for organic” rule is durable.  Shifting: guidance needs to evolve. If organic performance is catching up to editorial selection, the two-headline distinction may already be outdated.

### [Medium · Untested] Apple News — Possessive Named Entity — Topic Concentration

**Signal:** Possessive named entity headlines (n=95) show moderate overall performance on Apple News. The signal may be concentrated in sports and crime — topics where named individuals are central to the story — but aggregate analysis cannot confirm this.

**Gap:** Overall n=95 is small enough that splitting by topic reduces per-cell counts below the 30-article threshold for reliable inference. The aggregate analysis masks any strong within-topic signal.

**Question:** Do possessive named entity headlines specifically outperform in sports and crime topics on Apple News, where named individuals are central? Is the aggregate signal driven by a strong within-topic effect, or is it distributed broadly across all topics?

**How to run it:** Run on existing Apple News 2025+2026 data. Filter to possessive named entity headlines. Split by topic: sports+crime (the ‘high named-entity’ group) vs. all other topics. Run Mann-Whitney U (sports+crime PNE articles vs. untagged baseline within the same topics), rank-biserial r as effect size. Repeat for the ‘other topics’ group. Compare lift magnitudes: if the sports+crime lift is substantially larger (r ≥0.1 higher) than the other-topics lift, the signal is topic-concentrated. If lifts are similar, the rule applies broadly. If either per-topic cell has n < 20, flag as preliminary and hold until data grows. Do not split into individual topics at this sample size — aggregate sports+crime as one group. Implement as a topic-stratified extension of the Q1 analysis in generate_site.py.

**What the result unlocks:** Confirmed topic-specific: changes guidance from a broad rule to a targeted one (“use possessive named entity for sports/crime stories specifically”). Editors know exactly when to apply it.  Evenly distributed: the broad rule stands. Possessive named entity is generally useful, not vertically restricted.

### [Medium · Untested] SmartNews — Number Lead Type — Which Numbers Drive the SmartNews Signal?

**Signal:** Number leads show a positive directional trend on SmartNews (median rank 0.534 vs. 0.497 baseline; direction: above_dir). They are the only SmartNews formula with a positive directional signal. Whether count/list (‘3 ways’), dollar amounts (‘$2 billion’), or percentages (‘47%’) drive this has not been tested.

**Gap:** Number-type classification (classify_number_lead()) is implemented in the pipeline but per-type SmartNews performance has not been computed. SmartNews 2026 data is domain-aggregated (not article-level), limiting this analysis to the 2025 dataset (n=38,251 articles).

**Question:** Which number-lead subtype drives the SmartNews directional signal: count/list, dollar amounts, or percentages? Or is the effect evenly distributed across number types, suggesting format (any number in the lead) matters more than type?

**How to run it:** Run on SmartNews 2025 number-lead articles (n ≈342 total). classify_number_lead() already extracts ntype (‘count_list,’ ‘dollar_amount,’ ‘percentage,’ ‘other’). Group by ntype and run Mann-Whitney U for each group vs. the untagged baseline, BH-FDR corrected across the three tested types. Expected n per type: count_list is likely the largest (list articles are common); dollar_amount and percentage groups may be small. Flag any group with n < 20 as preliminary. If all subtypes have low n, aggregate and report directionally only: “counts/lists trend higher (n=X, p=Y)” without a significance claim. Implement by extending the existing number-lead deep-dive block (classify_number_lead() section) in generate_site.py to add a per-type Mann-Whitney analysis. Note: SmartNews 2026 is domain-aggregated and cannot contribute to this analysis — 2025 data only.

**What the result unlocks:** Confirmed specific type: editors can be told “count/list numbers work on SmartNews; dollar amounts and percentages are neutral.” More precise than the current directional number-lead guidance.  Equally distributed: the rule is format-driven (“any number in the lead is better than none”). Simpler and more broadly applicable.

---

## Run: 2026-04 (generated 2026-04-08T13:37:51)

_8 suggestion(s) this run_

### [↑ High · Bonferroni fail] SmartNews — “Here’s / Here are” Lift — Needs Confirmation

**Signal:** Articles using “Here’s / Here are” on SmartNews score a median percentile rank of 0.543 vs. 0.500 for the direct-declarative baseline (n=585, raw p=0.038). Direction is positive — opposite to question and “What to know” on the same platform.

**Gap:** Raw p=0.038 does not survive Bonferroni correction at k=5 formula families (threshold α/k = 0.010). All data is observational; no A/B comparison is available. Topic confounding (“Here’s” may correlate with better-performing story types) has not been controlled for.

**Question:** If T1 editors A/B tested “Here’s / Here are” against a direct-declarative version of the same story on SmartNews, would the formula version consistently outperform? Does the effect hold across topics (sports, crime, weather) or appear only in a topic subset?

**How to run it:** For 30–50 stories over 4–6 weeks, write two headline versions per story: (A) “Here’s / Here are” format and (B) a direct declarative covering the same facts. If the CMS supports A/B headline testing, use it; otherwise alternate formula by publication day or assign by outlet. Record SmartNews views at 7 days post-publish. Test: Mann-Whitney U on SmartNews views (A vs. B), rank-biserial r as effect size. Minimum n = 30 matched story pairs for reliable inference. Stratify by topic (sports/crime/weather vs. other) to check whether any interaction hides or drives the aggregate result. Do not use the same story on Apple News A/B — keep platforms separate to avoid contamination.

**What the result unlocks:** Confirmed: adds a positive SmartNews formula signal — currently all confirmed SmartNews guidance is avoidance-only. Editors could be told “Here’s works on SmartNews, unlike Apple News where WTK dominates featuring.”  Not confirmed: SmartNews playbook stays avoidance-only; the directional positive for “Here’s” is noise or topic-driven.

### [Medium · Underpowered] Apple News — Number Lead Specificity — Round vs. Exact Figures

**Signal:** Specific numbers (e.g. ‘$487M’, ‘13 deaths’) score a median rank of 0.405 vs. 0.277 for round numbers on Apple News (n = 165 specific, 21 round)

**Gap:** Groups too small for a reliable test: round n=21, specific n=165.

**Question:** Do Apple News headlines with precise numeric values (e.g. ‘$487 million,’ ‘13 officers’) consistently outperform rounded equivalents (‘$500 million,’ ‘10+ officers’) for views, controlling for topic and story type?

**How to run it:** When writing number-lead headlines, deliberately tag each as ‘round’ (e.g. ‘$500M,’ ‘10 people’) or ‘specific’ (e.g. ‘$487M,’ ‘13 people’) in a shared tracking sheet. Collect at least 30 Apple News articles per type before running the test. No CMS change needed — this is a tagging discipline applied during headline writing. Analysis: Mann-Whitney U on Apple News percentile rank at 7 days (specific vs. round), rank-biserial r as effect size. Stratify by topic (financial stories likely have more specificity variance than crime or sports). Existing pipeline: classify_number_lead() already extracts the numeric value — add a roundness tag to the tracking sheet and re-run once 30+ per group are tagged.

**What the result unlocks:** Confirmed: adds precision-number guidance to the style guide (“use exact figures in number leads, not rounded approximations”). Editors who default to rounded figures for readability would be asked to reverse that practice.  Not confirmed: round vs. specific distinction does not affect views; the number-lead signal is format-driven rather than specificity-driven.

### [↑ High · Underpowered] MSN — MSN Formula Groups — Insufficient Data for Confirmation

**Signal:** 1 formula group(s) show directional patterns on MSN but cannot be confirmed: Quoted lede. 113 total T1 news brand articles after filtering. Groups with n < 30: Quoted lede (n=18).

**Gap:** All flagged groups have n < 30, below the minimum for reliable inference (GOVERNOR.md Part 2). Only the quoted-lede group currently has enough data to test, and it is the one confirmed MSN finding. The MSN dataset grows approximately 100 rows/month; most formula groups should cross n=30 within 2–3 months of continued data collection.

**Question:** As MSN data accumulates, which formula groups consistently underperform the direct-declarative baseline? Is the underperformance pattern broad (all structured formulas hurt on MSN) or specific to certain formats?

**How to run it:** Natural experiment — no new data collection needed. The MSN dataset grows approximately 100 rows/month after the T1 brand filter. Re-run the Mann-Whitney formula analysis each monthly ingest; generate_site.py already does this automatically and the build report surfaces newly-significant groups. Threshold: treat any formula group as testable once it crosses n = 30. Expected timeline: most groups should reach n=30 within 2–3 monthly ingest cycles. Analysis: Mann-Whitney U (each formula group vs. untagged baseline), BH-FDR corrected across all tested groups simultaneously, rank-biserial r as effect size. Language tier: significant only if p_adj < 0.05; directional if p_adj < 0.10. Baseline key must be ‘untagged’ (not ‘other’) — see GOVERNOR.md Rigor Failures Log.

**What the result unlocks:** Confirmed broad pattern: extends the MSN rule from ‘avoid quoted lede’ to ‘avoid all structured formulas.’ Gives editors the strongest possible two-headline guidance: Apple News → use formulas; MSN → drop them entirely.  Confirmed specific subset: MSN avoidance list grows to the confirmed formula types while others remain neutral.  Not confirmed: MSN formula penalty is limited to quoted lede only.

### [↑ High · Untested] Apple News — Character Length × Formula Type Interaction

**Signal:** Character length (90–120 chars) and formula type independently predict Apple News views. Whether these signals interact — e.g., whether possessive named entity needs to be longer to achieve its lift, or whether “Here’s” works at any length — has not been tested.

**Gap:** Cross-tabulating formula buckets with length quartiles fragments an already-segmented dataset. Most formula × length cells will have n < 30, requiring aggregation trade-offs that risk obscuring the interaction signal. Analysis not yet run.

**Question:** Do specific formula types require specific length ranges to achieve their Apple News performance lift? E.g., does “Here’s / Here are” need 90+ chars to work, or does it lift at any length? Does possessive named entity perform best at shorter lengths where the name dominates the headline?

**How to run it:** Run on existing Apple News 2025+2026 data — no new collection needed. Cross-tabulate by formula type × length quartile. For each formula with n ≥30 total, split into Q1 (shortest) and Q4 (longest) length buckets and run Mann-Whitney U within each formula group vs. the untagged baseline at the same length. Compare the lift magnitude across length buckets. If any formula×length cell has n < 15, aggregate: fold Q1+Q2 into ‘short’ and Q3+Q4 into ‘long.’ Report as an interaction: does the formula’s lift increase, decrease, or stay flat as length increases? Plot as a 2×2 heatmap (formula × length bucket, colored by median rank). Apply BH-FDR correction across all formula×length cells tested. Bonferroni fallback: if more than 10 cells are tested, apply Bonferroni at k=10 as a secondary check.

**What the result unlocks:** Confirmed interaction: compound guidance (formula + length range) replaces two independent rules. Editors get: “Use Here’s at 90–110 chars; use possessive at 70–90 chars.” More actionable than current guidance.  No interaction: the two independent rules are stable and can be applied separately without worrying about their interaction.

### [↑ High · Untested] Notifications — Notification CTR × Character Length

**Signal:** Formula choice has a 2–5× effect on notification CTR (confirmed). Character length has been tested for Apple News views but not for notification CTR. Notifications truncate at ~80 chars on most devices, making length more likely to matter here than in feed headlines.

**Gap:** Character length vs. notification CTR has not been run. The notifications dataset covers 2025–2026 (1,050+ news brand pushes with CTR data) — sufficient for a Mann-Whitney test across length quartiles.

**Question:** Do shorter notifications (≤80 chars) outperform longer ones for CTR, controlling for formula type? Is there a character-count range where CTR peaks, or is the relationship monotonic (shorter = better)?

**How to run it:** Run on the existing notifications dataset (1,050+ news brand pushes with CTR). No new data collection needed. Bin notification headlines into four length quartiles. Run Kruskal-Wallis across quartiles first to check for any length–CTR association. If significant (p < 0.05), follow with Mann-Whitney U pairwise comparisons (Q1 vs. Q4 as primary), BH-FDR corrected. Control for formula type via stratification: run the length–CTR analysis separately within each formula group that has n ≥30 (attribution language, question, direct declarative). If length effect disappears within formula groups, length is a formula proxy, not an independent signal. Secondary analysis: Spearman correlation between character count and CTR (raw correlation, no quartiling). This gives a monotonicity check without binning artifacts. Implement in generate_site.py as an extension of the existing Q5 notification analysis block.

**What the result unlocks:** Confirmed: adds a second actionable lever for push copy editors beyond formula choice. Current guidance (“use attribution language”) would be extended with a specific character-count target.  Not confirmed: formula dominates; length doesn’t independently move CTR and editors can focus solely on formula selection for notifications.

### [Medium · Untested] Apple News — “What to Know” — Featured vs. Organic Stability by Year

**Signal:** Apple editors select “What to Know” at 1.8× the baseline rate for Featured placement. Organic (non-Featured) articles using WTK show no significant view lift (p<sub>adj</sub>=0.10). This editorial/algorithmic split is a key project finding — but whether it is stable across 2025 and 2026 separately is unknown.

**Gap:** The current analysis pools 2025 and 2026 Apple News data. If Apple has updated curation signals, or if T1 editors have changed how they use WTK, the featuring lift or organic penalty could be shifting — which would change whether the two-headline strategy is durable guidance.

**Question:** Is the WTK featuring lift consistent when 2025 and 2026 are analyzed separately? Has the gap between editorial selection rate and organic algorithmic performance been stable, or is it narrowing/widening over time?

**How to run it:** Run on existing Apple News data — no new collection needed. Split the Apple News dataset by year (2025 and 2026 separately). For each year, run: (1) Q2 chi-square or Fisher’s exact test for WTK featuring rate vs. all other formulas; (2) Q1 Mann-Whitney U for WTK organic view rank vs. untagged baseline (non-Featured articles only). Compare the featuring lift ratio (WTK featured rate / baseline featured rate) and the organic p-value across years. A narrowing featured rate ratio or a trending organic p-value signals platform behavior change. Implement as a year-stratified extension of the existing Q1 and Q2 analysis blocks in generate_site.py. Report: a 2×2 table of year×metric (featuring lift and organic p) alongside a directional trend flag. Note: Apple News 2026 covers Jan–Mar only; interpret with caution until Q3 2026 data is available.

**What the result unlocks:** Stable across years: confirms structural platform behavior. The “WTK for Featured campaigns, avoid for organic” rule is durable.  Shifting: guidance needs to evolve. If organic performance is catching up to editorial selection, the two-headline distinction may already be outdated.

### [Medium · Untested] Apple News — Possessive Named Entity — Topic Concentration

**Signal:** Possessive named entity headlines (n=95) show moderate overall performance on Apple News. The signal may be concentrated in sports and crime — topics where named individuals are central to the story — but aggregate analysis cannot confirm this.

**Gap:** Overall n=95 is small enough that splitting by topic reduces per-cell counts below the 30-article threshold for reliable inference. The aggregate analysis masks any strong within-topic signal.

**Question:** Do possessive named entity headlines specifically outperform in sports and crime topics on Apple News, where named individuals are central? Is the aggregate signal driven by a strong within-topic effect, or is it distributed broadly across all topics?

**How to run it:** Run on existing Apple News 2025+2026 data. Filter to possessive named entity headlines. Split by topic: sports+crime (the ‘high named-entity’ group) vs. all other topics. Run Mann-Whitney U (sports+crime PNE articles vs. untagged baseline within the same topics), rank-biserial r as effect size. Repeat for the ‘other topics’ group. Compare lift magnitudes: if the sports+crime lift is substantially larger (r ≥0.1 higher) than the other-topics lift, the signal is topic-concentrated. If lifts are similar, the rule applies broadly. If either per-topic cell has n < 20, flag as preliminary and hold until data grows. Do not split into individual topics at this sample size — aggregate sports+crime as one group. Implement as a topic-stratified extension of the Q1 analysis in generate_site.py.

**What the result unlocks:** Confirmed topic-specific: changes guidance from a broad rule to a targeted one (“use possessive named entity for sports/crime stories specifically”). Editors know exactly when to apply it.  Evenly distributed: the broad rule stands. Possessive named entity is generally useful, not vertically restricted.

### [Medium · Untested] SmartNews — Number Lead Type — Which Numbers Drive the SmartNews Signal?

**Signal:** Number leads show a positive directional trend on SmartNews (median rank 0.534 vs. 0.497 baseline; direction: above_dir). They are the only SmartNews formula with a positive directional signal. Whether count/list (‘3 ways’), dollar amounts (‘$2 billion’), or percentages (‘47%’) drive this has not been tested.

**Gap:** Number-type classification (classify_number_lead()) is implemented in the pipeline but per-type SmartNews performance has not been computed. SmartNews 2026 data is domain-aggregated (not article-level), limiting this analysis to the 2025 dataset (n=38,251 articles).

**Question:** Which number-lead subtype drives the SmartNews directional signal: count/list, dollar amounts, or percentages? Or is the effect evenly distributed across number types, suggesting format (any number in the lead) matters more than type?

**How to run it:** Run on SmartNews 2025 number-lead articles (n ≈342 total). classify_number_lead() already extracts ntype (‘count_list,’ ‘dollar_amount,’ ‘percentage,’ ‘other’). Group by ntype and run Mann-Whitney U for each group vs. the untagged baseline, BH-FDR corrected across the three tested types. Expected n per type: count_list is likely the largest (list articles are common); dollar_amount and percentage groups may be small. Flag any group with n < 20 as preliminary. If all subtypes have low n, aggregate and report directionally only: “counts/lists trend higher (n=X, p=Y)” without a significance claim. Implement by extending the existing number-lead deep-dive block (classify_number_lead() section) in generate_site.py to add a per-type Mann-Whitney analysis. Note: SmartNews 2026 is domain-aggregated and cannot contribute to this analysis — 2025 data only.

**What the result unlocks:** Confirmed specific type: editors can be told “count/list numbers work on SmartNews; dollar amounts and percentages are neutral.” More precise than the current directional number-lead guidance.  Equally distributed: the rule is format-driven (“any number in the lead is better than none”). Simpler and more broadly applicable.

---

## Run: 2026-04 (generated 2026-04-08T13:38:54)

_8 suggestion(s) this run_

### [↑ High · Bonferroni fail] SmartNews — “Here’s / Here are” Lift — Needs Confirmation

**Signal:** Articles using “Here’s / Here are” on SmartNews score a median percentile rank of 0.543 vs. 0.500 for the direct-declarative baseline (n=585, raw p=0.038). Direction is positive — opposite to question and “What to know” on the same platform.

**Gap:** Raw p=0.038 does not survive Bonferroni correction at k=5 formula families (threshold α/k = 0.010). All data is observational; no A/B comparison is available. Topic confounding (“Here’s” may correlate with better-performing story types) has not been controlled for.

**Question:** If T1 editors A/B tested “Here’s / Here are” against a direct-declarative version of the same story on SmartNews, would the formula version consistently outperform? Does the effect hold across topics (sports, crime, weather) or appear only in a topic subset?

**How to run it:** For 30–50 stories over 4–6 weeks, write two headline versions per story: (A) “Here’s / Here are” format and (B) a direct declarative covering the same facts. If the CMS supports A/B headline testing, use it; otherwise alternate formula by publication day or assign by outlet. Record SmartNews views at 7 days post-publish. Test: Mann-Whitney U on SmartNews views (A vs. B), rank-biserial r as effect size. Minimum n = 30 matched story pairs for reliable inference. Stratify by topic (sports/crime/weather vs. other) to check whether any interaction hides or drives the aggregate result. Do not use the same story on Apple News A/B — keep platforms separate to avoid contamination.

**What the result unlocks:** Confirmed: adds a positive SmartNews formula signal — currently all confirmed SmartNews guidance is avoidance-only. Editors could be told “Here’s works on SmartNews, unlike Apple News where WTK dominates featuring.”  Not confirmed: SmartNews playbook stays avoidance-only; the directional positive for “Here’s” is noise or topic-driven.

### [Medium · Underpowered] Apple News — Number Lead Specificity — Round vs. Exact Figures

**Signal:** Specific numbers (e.g. ‘$487M’, ‘13 deaths’) score a median rank of 0.405 vs. 0.277 for round numbers on Apple News (n = 165 specific, 21 round)

**Gap:** Groups too small for a reliable test: round n=21, specific n=165.

**Question:** Do Apple News headlines with precise numeric values (e.g. ‘$487 million,’ ‘13 officers’) consistently outperform rounded equivalents (‘$500 million,’ ‘10+ officers’) for views, controlling for topic and story type?

**How to run it:** When writing number-lead headlines, deliberately tag each as ‘round’ (e.g. ‘$500M,’ ‘10 people’) or ‘specific’ (e.g. ‘$487M,’ ‘13 people’) in a shared tracking sheet. Collect at least 30 Apple News articles per type before running the test. No CMS change needed — this is a tagging discipline applied during headline writing. Analysis: Mann-Whitney U on Apple News percentile rank at 7 days (specific vs. round), rank-biserial r as effect size. Stratify by topic (financial stories likely have more specificity variance than crime or sports). Existing pipeline: classify_number_lead() already extracts the numeric value — add a roundness tag to the tracking sheet and re-run once 30+ per group are tagged.

**What the result unlocks:** Confirmed: adds precision-number guidance to the style guide (“use exact figures in number leads, not rounded approximations”). Editors who default to rounded figures for readability would be asked to reverse that practice.  Not confirmed: round vs. specific distinction does not affect views; the number-lead signal is format-driven rather than specificity-driven.

### [↑ High · Underpowered] MSN — MSN Formula Groups — Insufficient Data for Confirmation

**Signal:** 1 formula group(s) show directional patterns on MSN but cannot be confirmed: Quoted lede. 113 total T1 news brand articles after filtering. Groups with n < 30: Quoted lede (n=18).

**Gap:** All flagged groups have n < 30, below the minimum for reliable inference (GOVERNOR.md Part 2). Only the quoted-lede group currently has enough data to test, and it is the one confirmed MSN finding. The MSN dataset grows approximately 100 rows/month; most formula groups should cross n=30 within 2–3 months of continued data collection.

**Question:** As MSN data accumulates, which formula groups consistently underperform the direct-declarative baseline? Is the underperformance pattern broad (all structured formulas hurt on MSN) or specific to certain formats?

**How to run it:** Natural experiment — no new data collection needed. The MSN dataset grows approximately 100 rows/month after the T1 brand filter. Re-run the Mann-Whitney formula analysis each monthly ingest; generate_site.py already does this automatically and the build report surfaces newly-significant groups. Threshold: treat any formula group as testable once it crosses n = 30. Expected timeline: most groups should reach n=30 within 2–3 monthly ingest cycles. Analysis: Mann-Whitney U (each formula group vs. untagged baseline), BH-FDR corrected across all tested groups simultaneously, rank-biserial r as effect size. Language tier: significant only if p_adj < 0.05; directional if p_adj < 0.10. Baseline key must be ‘untagged’ (not ‘other’) — see GOVERNOR.md Rigor Failures Log.

**What the result unlocks:** Confirmed broad pattern: extends the MSN rule from ‘avoid quoted lede’ to ‘avoid all structured formulas.’ Gives editors the strongest possible two-headline guidance: Apple News → use formulas; MSN → drop them entirely.  Confirmed specific subset: MSN avoidance list grows to the confirmed formula types while others remain neutral.  Not confirmed: MSN formula penalty is limited to quoted lede only.

### [↑ High · Untested] Apple News — Character Length × Formula Type Interaction

**Signal:** Character length (90–120 chars) and formula type independently predict Apple News views. Whether these signals interact — e.g., whether possessive named entity needs to be longer to achieve its lift, or whether “Here’s” works at any length — has not been tested.

**Gap:** Cross-tabulating formula buckets with length quartiles fragments an already-segmented dataset. Most formula × length cells will have n < 30, requiring aggregation trade-offs that risk obscuring the interaction signal. Analysis not yet run.

**Question:** Do specific formula types require specific length ranges to achieve their Apple News performance lift? E.g., does “Here’s / Here are” need 90+ chars to work, or does it lift at any length? Does possessive named entity perform best at shorter lengths where the name dominates the headline?

**How to run it:** Run on existing Apple News 2025+2026 data — no new collection needed. Cross-tabulate by formula type × length quartile. For each formula with n ≥30 total, split into Q1 (shortest) and Q4 (longest) length buckets and run Mann-Whitney U within each formula group vs. the untagged baseline at the same length. Compare the lift magnitude across length buckets. If any formula×length cell has n < 15, aggregate: fold Q1+Q2 into ‘short’ and Q3+Q4 into ‘long.’ Report as an interaction: does the formula’s lift increase, decrease, or stay flat as length increases? Plot as a 2×2 heatmap (formula × length bucket, colored by median rank). Apply BH-FDR correction across all formula×length cells tested. Bonferroni fallback: if more than 10 cells are tested, apply Bonferroni at k=10 as a secondary check.

**What the result unlocks:** Confirmed interaction: compound guidance (formula + length range) replaces two independent rules. Editors get: “Use Here’s at 90–110 chars; use possessive at 70–90 chars.” More actionable than current guidance.  No interaction: the two independent rules are stable and can be applied separately without worrying about their interaction.

### [↑ High · Untested] Notifications — Notification CTR × Character Length

**Signal:** Formula choice has a 2–5× effect on notification CTR (confirmed). Character length has been tested for Apple News views but not for notification CTR. Notifications truncate at ~80 chars on most devices, making length more likely to matter here than in feed headlines.

**Gap:** Character length vs. notification CTR has not been run. The notifications dataset covers 2025–2026 (1,050+ news brand pushes with CTR data) — sufficient for a Mann-Whitney test across length quartiles.

**Question:** Do shorter notifications (≤80 chars) outperform longer ones for CTR, controlling for formula type? Is there a character-count range where CTR peaks, or is the relationship monotonic (shorter = better)?

**How to run it:** Run on the existing notifications dataset (1,050+ news brand pushes with CTR). No new data collection needed. Bin notification headlines into four length quartiles. Run Kruskal-Wallis across quartiles first to check for any length–CTR association. If significant (p < 0.05), follow with Mann-Whitney U pairwise comparisons (Q1 vs. Q4 as primary), BH-FDR corrected. Control for formula type via stratification: run the length–CTR analysis separately within each formula group that has n ≥30 (attribution language, question, direct declarative). If length effect disappears within formula groups, length is a formula proxy, not an independent signal. Secondary analysis: Spearman correlation between character count and CTR (raw correlation, no quartiling). This gives a monotonicity check without binning artifacts. Implement in generate_site.py as an extension of the existing Q5 notification analysis block.

**What the result unlocks:** Confirmed: adds a second actionable lever for push copy editors beyond formula choice. Current guidance (“use attribution language”) would be extended with a specific character-count target.  Not confirmed: formula dominates; length doesn’t independently move CTR and editors can focus solely on formula selection for notifications.

### [Medium · Untested] Apple News — “What to Know” — Featured vs. Organic Stability by Year

**Signal:** Apple editors select “What to Know” at 1.8× the baseline rate for Featured placement. Organic (non-Featured) articles using WTK show no significant view lift (p<sub>adj</sub>=0.10). This editorial/algorithmic split is a key project finding — but whether it is stable across 2025 and 2026 separately is unknown.

**Gap:** The current analysis pools 2025 and 2026 Apple News data. If Apple has updated curation signals, or if T1 editors have changed how they use WTK, the featuring lift or organic penalty could be shifting — which would change whether the two-headline strategy is durable guidance.

**Question:** Is the WTK featuring lift consistent when 2025 and 2026 are analyzed separately? Has the gap between editorial selection rate and organic algorithmic performance been stable, or is it narrowing/widening over time?

**How to run it:** Run on existing Apple News data — no new collection needed. Split the Apple News dataset by year (2025 and 2026 separately). For each year, run: (1) Q2 chi-square or Fisher’s exact test for WTK featuring rate vs. all other formulas; (2) Q1 Mann-Whitney U for WTK organic view rank vs. untagged baseline (non-Featured articles only). Compare the featuring lift ratio (WTK featured rate / baseline featured rate) and the organic p-value across years. A narrowing featured rate ratio or a trending organic p-value signals platform behavior change. Implement as a year-stratified extension of the existing Q1 and Q2 analysis blocks in generate_site.py. Report: a 2×2 table of year×metric (featuring lift and organic p) alongside a directional trend flag. Note: Apple News 2026 covers Jan–Mar only; interpret with caution until Q3 2026 data is available.

**What the result unlocks:** Stable across years: confirms structural platform behavior. The “WTK for Featured campaigns, avoid for organic” rule is durable.  Shifting: guidance needs to evolve. If organic performance is catching up to editorial selection, the two-headline distinction may already be outdated.

### [Medium · Untested] Apple News — Possessive Named Entity — Topic Concentration

**Signal:** Possessive named entity headlines (n=95) show moderate overall performance on Apple News. The signal may be concentrated in sports and crime — topics where named individuals are central to the story — but aggregate analysis cannot confirm this.

**Gap:** Overall n=95 is small enough that splitting by topic reduces per-cell counts below the 30-article threshold for reliable inference. The aggregate analysis masks any strong within-topic signal.

**Question:** Do possessive named entity headlines specifically outperform in sports and crime topics on Apple News, where named individuals are central? Is the aggregate signal driven by a strong within-topic effect, or is it distributed broadly across all topics?

**How to run it:** Run on existing Apple News 2025+2026 data. Filter to possessive named entity headlines. Split by topic: sports+crime (the ‘high named-entity’ group) vs. all other topics. Run Mann-Whitney U (sports+crime PNE articles vs. untagged baseline within the same topics), rank-biserial r as effect size. Repeat for the ‘other topics’ group. Compare lift magnitudes: if the sports+crime lift is substantially larger (r ≥0.1 higher) than the other-topics lift, the signal is topic-concentrated. If lifts are similar, the rule applies broadly. If either per-topic cell has n < 20, flag as preliminary and hold until data grows. Do not split into individual topics at this sample size — aggregate sports+crime as one group. Implement as a topic-stratified extension of the Q1 analysis in generate_site.py.

**What the result unlocks:** Confirmed topic-specific: changes guidance from a broad rule to a targeted one (“use possessive named entity for sports/crime stories specifically”). Editors know exactly when to apply it.  Evenly distributed: the broad rule stands. Possessive named entity is generally useful, not vertically restricted.

### [Medium · Untested] SmartNews — Number Lead Type — Which Numbers Drive the SmartNews Signal?

**Signal:** Number leads show a positive directional trend on SmartNews (median rank 0.534 vs. 0.497 baseline; direction: above_dir). They are the only SmartNews formula with a positive directional signal. Whether count/list (‘3 ways’), dollar amounts (‘$2 billion’), or percentages (‘47%’) drive this has not been tested.

**Gap:** Number-type classification (classify_number_lead()) is implemented in the pipeline but per-type SmartNews performance has not been computed. SmartNews 2026 data is domain-aggregated (not article-level), limiting this analysis to the 2025 dataset (n=38,251 articles).

**Question:** Which number-lead subtype drives the SmartNews directional signal: count/list, dollar amounts, or percentages? Or is the effect evenly distributed across number types, suggesting format (any number in the lead) matters more than type?

**How to run it:** Run on SmartNews 2025 number-lead articles (n ≈342 total). classify_number_lead() already extracts ntype (‘count_list,’ ‘dollar_amount,’ ‘percentage,’ ‘other’). Group by ntype and run Mann-Whitney U for each group vs. the untagged baseline, BH-FDR corrected across the three tested types. Expected n per type: count_list is likely the largest (list articles are common); dollar_amount and percentage groups may be small. Flag any group with n < 20 as preliminary. If all subtypes have low n, aggregate and report directionally only: “counts/lists trend higher (n=X, p=Y)” without a significance claim. Implement by extending the existing number-lead deep-dive block (classify_number_lead() section) in generate_site.py to add a per-type Mann-Whitney analysis. Note: SmartNews 2026 is domain-aggregated and cannot contribute to this analysis — 2025 data only.

**What the result unlocks:** Confirmed specific type: editors can be told “count/list numbers work on SmartNews; dollar amounts and percentages are neutral.” More precise than the current directional number-lead guidance.  Equally distributed: the rule is format-driven (“any number in the lead is better than none”). Simpler and more broadly applicable.

---

## Run: 2026-04 (generated 2026-04-08T13:48:39)

_8 suggestion(s) this run_

### [↑ High · Bonferroni fail] SmartNews — “Here’s / Here are” Lift — Needs Confirmation

**Signal:** Articles using “Here’s / Here are” on SmartNews score a median percentile rank of 0.543 vs. 0.500 for the direct-declarative baseline (n=585, raw p=0.038). Direction is positive — opposite to question and “What to know” on the same platform.

**Gap:** Raw p=0.038 does not survive Bonferroni correction at k=5 formula families (threshold α/k = 0.010). All data is observational; no A/B comparison is available. Topic confounding (“Here’s” may correlate with better-performing story types) has not been controlled for.

**Question:** If T1 editors A/B tested “Here’s / Here are” against a direct-declarative version of the same story on SmartNews, would the formula version consistently outperform? Does the effect hold across topics (sports, crime, weather) or appear only in a topic subset?

**How to run it:** For 30–50 stories over 4–6 weeks, write two headline versions per story: (A) “Here’s / Here are” format and (B) a direct declarative covering the same facts. If the CMS supports A/B headline testing, use it; otherwise alternate formula by publication day or assign by outlet. Record SmartNews views at 7 days post-publish. Test: Mann-Whitney U on SmartNews views (A vs. B), rank-biserial r as effect size. Minimum n = 30 matched story pairs for reliable inference. Stratify by topic (sports/crime/weather vs. other) to check whether any interaction hides or drives the aggregate result. Do not use the same story on Apple News A/B — keep platforms separate to avoid contamination.

**What the result unlocks:** Confirmed: adds a positive SmartNews formula signal — currently all confirmed SmartNews guidance is avoidance-only. Editors could be told “Here’s works on SmartNews, unlike Apple News where WTK dominates featuring.”  Not confirmed: SmartNews playbook stays avoidance-only; the directional positive for “Here’s” is noise or topic-driven.

### [Medium · Underpowered] Apple News — Number Lead Specificity — Round vs. Exact Figures

**Signal:** Specific numbers (e.g. ‘$487M’, ‘13 deaths’) score a median rank of 0.405 vs. 0.277 for round numbers on Apple News (n = 165 specific, 21 round)

**Gap:** Groups too small for a reliable test: round n=21, specific n=165.

**Question:** Do Apple News headlines with precise numeric values (e.g. ‘$487 million,’ ‘13 officers’) consistently outperform rounded equivalents (‘$500 million,’ ‘10+ officers’) for views, controlling for topic and story type?

**How to run it:** When writing number-lead headlines, deliberately tag each as ‘round’ (e.g. ‘$500M,’ ‘10 people’) or ‘specific’ (e.g. ‘$487M,’ ‘13 people’) in a shared tracking sheet. Collect at least 30 Apple News articles per type before running the test. No CMS change needed — this is a tagging discipline applied during headline writing. Analysis: Mann-Whitney U on Apple News percentile rank at 7 days (specific vs. round), rank-biserial r as effect size. Stratify by topic (financial stories likely have more specificity variance than crime or sports). Existing pipeline: classify_number_lead() already extracts the numeric value — add a roundness tag to the tracking sheet and re-run once 30+ per group are tagged.

**What the result unlocks:** Confirmed: adds precision-number guidance to the style guide (“use exact figures in number leads, not rounded approximations”). Editors who default to rounded figures for readability would be asked to reverse that practice.  Not confirmed: round vs. specific distinction does not affect views; the number-lead signal is format-driven rather than specificity-driven.

### [↑ High · Underpowered] MSN — MSN Formula Groups — Insufficient Data for Confirmation

**Signal:** 1 formula group(s) show directional patterns on MSN but cannot be confirmed: Quoted lede. 113 total T1 news brand articles after filtering. Groups with n < 30: Quoted lede (n=18).

**Gap:** All flagged groups have n < 30, below the minimum for reliable inference (GOVERNOR.md Part 2). Only the quoted-lede group currently has enough data to test, and it is the one confirmed MSN finding. The MSN dataset grows approximately 100 rows/month; most formula groups should cross n=30 within 2–3 months of continued data collection.

**Question:** As MSN data accumulates, which formula groups consistently underperform the direct-declarative baseline? Is the underperformance pattern broad (all structured formulas hurt on MSN) or specific to certain formats?

**How to run it:** Natural experiment — no new data collection needed. The MSN dataset grows approximately 100 rows/month after the T1 brand filter. Re-run the Mann-Whitney formula analysis each monthly ingest; generate_site.py already does this automatically and the build report surfaces newly-significant groups. Threshold: treat any formula group as testable once it crosses n = 30. Expected timeline: most groups should reach n=30 within 2–3 monthly ingest cycles. Analysis: Mann-Whitney U (each formula group vs. untagged baseline), BH-FDR corrected across all tested groups simultaneously, rank-biserial r as effect size. Language tier: significant only if p_adj < 0.05; directional if p_adj < 0.10. Baseline key must be ‘untagged’ (not ‘other’) — see GOVERNOR.md Rigor Failures Log.

**What the result unlocks:** Confirmed broad pattern: extends the MSN rule from ‘avoid quoted lede’ to ‘avoid all structured formulas.’ Gives editors the strongest possible two-headline guidance: Apple News → use formulas; MSN → drop them entirely.  Confirmed specific subset: MSN avoidance list grows to the confirmed formula types while others remain neutral.  Not confirmed: MSN formula penalty is limited to quoted lede only.

### [↑ High · Untested] Apple News — Character Length × Formula Type Interaction

**Signal:** Character length (90–120 chars) and formula type independently predict Apple News views. Whether these signals interact — e.g., whether possessive named entity needs to be longer to achieve its lift, or whether “Here’s” works at any length — has not been tested.

**Gap:** Cross-tabulating formula buckets with length quartiles fragments an already-segmented dataset. Most formula × length cells will have n < 30, requiring aggregation trade-offs that risk obscuring the interaction signal. Analysis not yet run.

**Question:** Do specific formula types require specific length ranges to achieve their Apple News performance lift? E.g., does “Here’s / Here are” need 90+ chars to work, or does it lift at any length? Does possessive named entity perform best at shorter lengths where the name dominates the headline?

**How to run it:** Run on existing Apple News 2025+2026 data — no new collection needed. Cross-tabulate by formula type × length quartile. For each formula with n ≥30 total, split into Q1 (shortest) and Q4 (longest) length buckets and run Mann-Whitney U within each formula group vs. the untagged baseline at the same length. Compare the lift magnitude across length buckets. If any formula×length cell has n < 15, aggregate: fold Q1+Q2 into ‘short’ and Q3+Q4 into ‘long.’ Report as an interaction: does the formula’s lift increase, decrease, or stay flat as length increases? Plot as a 2×2 heatmap (formula × length bucket, colored by median rank). Apply BH-FDR correction across all formula×length cells tested. Bonferroni fallback: if more than 10 cells are tested, apply Bonferroni at k=10 as a secondary check.

**What the result unlocks:** Confirmed interaction: compound guidance (formula + length range) replaces two independent rules. Editors get: “Use Here’s at 90–110 chars; use possessive at 70–90 chars.” More actionable than current guidance.  No interaction: the two independent rules are stable and can be applied separately without worrying about their interaction.

### [↑ High · Untested] Notifications — Notification CTR × Character Length

**Signal:** Formula choice has a 2–5× effect on notification CTR (confirmed). Character length has been tested for Apple News views but not for notification CTR. Notifications truncate at ~80 chars on most devices, making length more likely to matter here than in feed headlines.

**Gap:** Character length vs. notification CTR has not been run. The notifications dataset covers 2025–2026 (1,050+ news brand pushes with CTR data) — sufficient for a Mann-Whitney test across length quartiles.

**Question:** Do shorter notifications (≤80 chars) outperform longer ones for CTR, controlling for formula type? Is there a character-count range where CTR peaks, or is the relationship monotonic (shorter = better)?

**How to run it:** Run on the existing notifications dataset (1,050+ news brand pushes with CTR). No new data collection needed. Bin notification headlines into four length quartiles. Run Kruskal-Wallis across quartiles first to check for any length–CTR association. If significant (p < 0.05), follow with Mann-Whitney U pairwise comparisons (Q1 vs. Q4 as primary), BH-FDR corrected. Control for formula type via stratification: run the length–CTR analysis separately within each formula group that has n ≥30 (attribution language, question, direct declarative). If length effect disappears within formula groups, length is a formula proxy, not an independent signal. Secondary analysis: Spearman correlation between character count and CTR (raw correlation, no quartiling). This gives a monotonicity check without binning artifacts. Implement in generate_site.py as an extension of the existing Q5 notification analysis block.

**What the result unlocks:** Confirmed: adds a second actionable lever for push copy editors beyond formula choice. Current guidance (“use attribution language”) would be extended with a specific character-count target.  Not confirmed: formula dominates; length doesn’t independently move CTR and editors can focus solely on formula selection for notifications.

### [Medium · Untested] Apple News — “What to Know” — Featured vs. Organic Stability by Year

**Signal:** Apple editors select “What to Know” at 1.8× the baseline rate for Featured placement. Organic (non-Featured) articles using WTK show no significant view lift (p<sub>adj</sub>=0.10). This editorial/algorithmic split is a key project finding — but whether it is stable across 2025 and 2026 separately is unknown.

**Gap:** The current analysis pools 2025 and 2026 Apple News data. If Apple has updated curation signals, or if T1 editors have changed how they use WTK, the featuring lift or organic penalty could be shifting — which would change whether the two-headline strategy is durable guidance.

**Question:** Is the WTK featuring lift consistent when 2025 and 2026 are analyzed separately? Has the gap between editorial selection rate and organic algorithmic performance been stable, or is it narrowing/widening over time?

**How to run it:** Run on existing Apple News data — no new collection needed. Split the Apple News dataset by year (2025 and 2026 separately). For each year, run: (1) Q2 chi-square or Fisher’s exact test for WTK featuring rate vs. all other formulas; (2) Q1 Mann-Whitney U for WTK organic view rank vs. untagged baseline (non-Featured articles only). Compare the featuring lift ratio (WTK featured rate / baseline featured rate) and the organic p-value across years. A narrowing featured rate ratio or a trending organic p-value signals platform behavior change. Implement as a year-stratified extension of the existing Q1 and Q2 analysis blocks in generate_site.py. Report: a 2×2 table of year×metric (featuring lift and organic p) alongside a directional trend flag. Note: Apple News 2026 covers Jan–Mar only; interpret with caution until Q3 2026 data is available.

**What the result unlocks:** Stable across years: confirms structural platform behavior. The “WTK for Featured campaigns, avoid for organic” rule is durable.  Shifting: guidance needs to evolve. If organic performance is catching up to editorial selection, the two-headline distinction may already be outdated.

### [Medium · Untested] Apple News — Possessive Named Entity — Topic Concentration

**Signal:** Possessive named entity headlines (n=95) show moderate overall performance on Apple News. The signal may be concentrated in sports and crime — topics where named individuals are central to the story — but aggregate analysis cannot confirm this.

**Gap:** Overall n=95 is small enough that splitting by topic reduces per-cell counts below the 30-article threshold for reliable inference. The aggregate analysis masks any strong within-topic signal.

**Question:** Do possessive named entity headlines specifically outperform in sports and crime topics on Apple News, where named individuals are central? Is the aggregate signal driven by a strong within-topic effect, or is it distributed broadly across all topics?

**How to run it:** Run on existing Apple News 2025+2026 data. Filter to possessive named entity headlines. Split by topic: sports+crime (the ‘high named-entity’ group) vs. all other topics. Run Mann-Whitney U (sports+crime PNE articles vs. untagged baseline within the same topics), rank-biserial r as effect size. Repeat for the ‘other topics’ group. Compare lift magnitudes: if the sports+crime lift is substantially larger (r ≥0.1 higher) than the other-topics lift, the signal is topic-concentrated. If lifts are similar, the rule applies broadly. If either per-topic cell has n < 20, flag as preliminary and hold until data grows. Do not split into individual topics at this sample size — aggregate sports+crime as one group. Implement as a topic-stratified extension of the Q1 analysis in generate_site.py.

**What the result unlocks:** Confirmed topic-specific: changes guidance from a broad rule to a targeted one (“use possessive named entity for sports/crime stories specifically”). Editors know exactly when to apply it.  Evenly distributed: the broad rule stands. Possessive named entity is generally useful, not vertically restricted.

### [Medium · Untested] SmartNews — Number Lead Type — Which Numbers Drive the SmartNews Signal?

**Signal:** Number leads show a positive directional trend on SmartNews (median rank 0.534 vs. 0.497 baseline; direction: above_dir). They are the only SmartNews formula with a positive directional signal. Whether count/list (‘3 ways’), dollar amounts (‘$2 billion’), or percentages (‘47%’) drive this has not been tested.

**Gap:** Number-type classification (classify_number_lead()) is implemented in the pipeline but per-type SmartNews performance has not been computed. SmartNews 2026 data is domain-aggregated (not article-level), limiting this analysis to the 2025 dataset (n=38,251 articles).

**Question:** Which number-lead subtype drives the SmartNews directional signal: count/list, dollar amounts, or percentages? Or is the effect evenly distributed across number types, suggesting format (any number in the lead) matters more than type?

**How to run it:** Run on SmartNews 2025 number-lead articles (n ≈342 total). classify_number_lead() already extracts ntype (‘count_list,’ ‘dollar_amount,’ ‘percentage,’ ‘other’). Group by ntype and run Mann-Whitney U for each group vs. the untagged baseline, BH-FDR corrected across the three tested types. Expected n per type: count_list is likely the largest (list articles are common); dollar_amount and percentage groups may be small. Flag any group with n < 20 as preliminary. If all subtypes have low n, aggregate and report directionally only: “counts/lists trend higher (n=X, p=Y)” without a significance claim. Implement by extending the existing number-lead deep-dive block (classify_number_lead() section) in generate_site.py to add a per-type Mann-Whitney analysis. Note: SmartNews 2026 is domain-aggregated and cannot contribute to this analysis — 2025 data only.

**What the result unlocks:** Confirmed specific type: editors can be told “count/list numbers work on SmartNews; dollar amounts and percentages are neutral.” More precise than the current directional number-lead guidance.  Equally distributed: the rule is format-driven (“any number in the lead is better than none”). Simpler and more broadly applicable.

---

## Run: 2026-04 (generated 2026-04-08T13:53:20)

_8 suggestion(s) this run_

### [↑ High · Bonferroni fail] SmartNews — “Here’s / Here are” Lift — Needs Confirmation

**Signal:** Articles using “Here’s / Here are” on SmartNews score a median percentile rank of 0.543 vs. 0.500 for the direct-declarative baseline (n=585, raw p=0.038). Direction is positive — opposite to question and “What to know” on the same platform.

**Gap:** Raw p=0.038 does not survive Bonferroni correction at k=5 formula families (threshold α/k = 0.010). All data is observational; no A/B comparison is available. Topic confounding (“Here’s” may correlate with better-performing story types) has not been controlled for.

**Question:** If T1 editors A/B tested “Here’s / Here are” against a direct-declarative version of the same story on SmartNews, would the formula version consistently outperform? Does the effect hold across topics (sports, crime, weather) or appear only in a topic subset?

**How to run it:** For 30–50 stories over 4–6 weeks, write two headline versions per story: (A) “Here’s / Here are” format and (B) a direct declarative covering the same facts. If the CMS supports A/B headline testing, use it; otherwise alternate formula by publication day or assign by outlet. Record SmartNews views at 7 days post-publish. Test: Mann-Whitney U on SmartNews views (A vs. B), rank-biserial r as effect size. Minimum n = 30 matched story pairs for reliable inference. Stratify by topic (sports/crime/weather vs. other) to check whether any interaction hides or drives the aggregate result. Do not use the same story on Apple News A/B — keep platforms separate to avoid contamination.

**What the result unlocks:** Confirmed: adds a positive SmartNews formula signal — currently all confirmed SmartNews guidance is avoidance-only. Editors could be told “Here’s works on SmartNews, unlike Apple News where WTK dominates featuring.”  Not confirmed: SmartNews playbook stays avoidance-only; the directional positive for “Here’s” is noise or topic-driven.

### [Medium · Underpowered] Apple News — Number Lead Specificity — Round vs. Exact Figures

**Signal:** Specific numbers (e.g. ‘$487M’, ‘13 deaths’) score a median rank of 0.405 vs. 0.277 for round numbers on Apple News (n = 165 specific, 21 round)

**Gap:** Groups too small for a reliable test: round n=21, specific n=165.

**Question:** Do Apple News headlines with precise numeric values (e.g. ‘$487 million,’ ‘13 officers’) consistently outperform rounded equivalents (‘$500 million,’ ‘10+ officers’) for views, controlling for topic and story type?

**How to run it:** When writing number-lead headlines, deliberately tag each as ‘round’ (e.g. ‘$500M,’ ‘10 people’) or ‘specific’ (e.g. ‘$487M,’ ‘13 people’) in a shared tracking sheet. Collect at least 30 Apple News articles per type before running the test. No CMS change needed — this is a tagging discipline applied during headline writing. Analysis: Mann-Whitney U on Apple News percentile rank at 7 days (specific vs. round), rank-biserial r as effect size. Stratify by topic (financial stories likely have more specificity variance than crime or sports). Existing pipeline: classify_number_lead() already extracts the numeric value — add a roundness tag to the tracking sheet and re-run once 30+ per group are tagged.

**What the result unlocks:** Confirmed: adds precision-number guidance to the style guide (“use exact figures in number leads, not rounded approximations”). Editors who default to rounded figures for readability would be asked to reverse that practice.  Not confirmed: round vs. specific distinction does not affect views; the number-lead signal is format-driven rather than specificity-driven.

### [↑ High · Underpowered] MSN — MSN Formula Groups — Insufficient Data for Confirmation

**Signal:** 1 formula group(s) show directional patterns on MSN but cannot be confirmed: Quoted lede. 113 total T1 news brand articles after filtering. Groups with n < 30: Quoted lede (n=18).

**Gap:** All flagged groups have n < 30, below the minimum for reliable inference (GOVERNOR.md Part 2). Only the quoted-lede group currently has enough data to test, and it is the one confirmed MSN finding. The MSN dataset grows approximately 100 rows/month; most formula groups should cross n=30 within 2–3 months of continued data collection.

**Question:** As MSN data accumulates, which formula groups consistently underperform the direct-declarative baseline? Is the underperformance pattern broad (all structured formulas hurt on MSN) or specific to certain formats?

**How to run it:** Natural experiment — no new data collection needed. The MSN dataset grows approximately 100 rows/month after the T1 brand filter. Re-run the Mann-Whitney formula analysis each monthly ingest; generate_site.py already does this automatically and the build report surfaces newly-significant groups. Threshold: treat any formula group as testable once it crosses n = 30. Expected timeline: most groups should reach n=30 within 2–3 monthly ingest cycles. Analysis: Mann-Whitney U (each formula group vs. untagged baseline), BH-FDR corrected across all tested groups simultaneously, rank-biserial r as effect size. Language tier: significant only if p_adj < 0.05; directional if p_adj < 0.10. Baseline key must be ‘untagged’ (not ‘other’) — see GOVERNOR.md Rigor Failures Log.

**What the result unlocks:** Confirmed broad pattern: extends the MSN rule from ‘avoid quoted lede’ to ‘avoid all structured formulas.’ Gives editors the strongest possible two-headline guidance: Apple News → use formulas; MSN → drop them entirely.  Confirmed specific subset: MSN avoidance list grows to the confirmed formula types while others remain neutral.  Not confirmed: MSN formula penalty is limited to quoted lede only.

### [↑ High · Untested] Apple News — Character Length × Formula Type Interaction

**Signal:** Character length (90–120 chars) and formula type independently predict Apple News views. Whether these signals interact — e.g., whether possessive named entity needs to be longer to achieve its lift, or whether “Here’s” works at any length — has not been tested.

**Gap:** Cross-tabulating formula buckets with length quartiles fragments an already-segmented dataset. Most formula × length cells will have n < 30, requiring aggregation trade-offs that risk obscuring the interaction signal. Analysis not yet run.

**Question:** Do specific formula types require specific length ranges to achieve their Apple News performance lift? E.g., does “Here’s / Here are” need 90+ chars to work, or does it lift at any length? Does possessive named entity perform best at shorter lengths where the name dominates the headline?

**How to run it:** Run on existing Apple News 2025+2026 data — no new collection needed. Cross-tabulate by formula type × length quartile. For each formula with n ≥30 total, split into Q1 (shortest) and Q4 (longest) length buckets and run Mann-Whitney U within each formula group vs. the untagged baseline at the same length. Compare the lift magnitude across length buckets. If any formula×length cell has n < 15, aggregate: fold Q1+Q2 into ‘short’ and Q3+Q4 into ‘long.’ Report as an interaction: does the formula’s lift increase, decrease, or stay flat as length increases? Plot as a 2×2 heatmap (formula × length bucket, colored by median rank). Apply BH-FDR correction across all formula×length cells tested. Bonferroni fallback: if more than 10 cells are tested, apply Bonferroni at k=10 as a secondary check.

**What the result unlocks:** Confirmed interaction: compound guidance (formula + length range) replaces two independent rules. Editors get: “Use Here’s at 90–110 chars; use possessive at 70–90 chars.” More actionable than current guidance.  No interaction: the two independent rules are stable and can be applied separately without worrying about their interaction.

### [↑ High · Untested] Notifications — Notification CTR × Character Length

**Signal:** Formula choice has a 2–5× effect on notification CTR (confirmed). Character length has been tested for Apple News views but not for notification CTR. Notifications truncate at ~80 chars on most devices, making length more likely to matter here than in feed headlines.

**Gap:** Character length vs. notification CTR has not been run. The notifications dataset covers 2025–2026 (1,050+ news brand pushes with CTR data) — sufficient for a Mann-Whitney test across length quartiles.

**Question:** Do shorter notifications (≤80 chars) outperform longer ones for CTR, controlling for formula type? Is there a character-count range where CTR peaks, or is the relationship monotonic (shorter = better)?

**How to run it:** Run on the existing notifications dataset (1,050+ news brand pushes with CTR). No new data collection needed. Bin notification headlines into four length quartiles. Run Kruskal-Wallis across quartiles first to check for any length–CTR association. If significant (p < 0.05), follow with Mann-Whitney U pairwise comparisons (Q1 vs. Q4 as primary), BH-FDR corrected. Control for formula type via stratification: run the length–CTR analysis separately within each formula group that has n ≥30 (attribution language, question, direct declarative). If length effect disappears within formula groups, length is a formula proxy, not an independent signal. Secondary analysis: Spearman correlation between character count and CTR (raw correlation, no quartiling). This gives a monotonicity check without binning artifacts. Implement in generate_site.py as an extension of the existing Q5 notification analysis block.

**What the result unlocks:** Confirmed: adds a second actionable lever for push copy editors beyond formula choice. Current guidance (“use attribution language”) would be extended with a specific character-count target.  Not confirmed: formula dominates; length doesn’t independently move CTR and editors can focus solely on formula selection for notifications.

### [Medium · Untested] Apple News — “What to Know” — Featured vs. Organic Stability by Year

**Signal:** Apple editors select “What to Know” at 1.8× the baseline rate for Featured placement. Organic (non-Featured) articles using WTK show no significant view lift (p<sub>adj</sub>=0.10). This editorial/algorithmic split is a key project finding — but whether it is stable across 2025 and 2026 separately is unknown.

**Gap:** The current analysis pools 2025 and 2026 Apple News data. If Apple has updated curation signals, or if T1 editors have changed how they use WTK, the featuring lift or organic penalty could be shifting — which would change whether the two-headline strategy is durable guidance.

**Question:** Is the WTK featuring lift consistent when 2025 and 2026 are analyzed separately? Has the gap between editorial selection rate and organic algorithmic performance been stable, or is it narrowing/widening over time?

**How to run it:** Run on existing Apple News data — no new collection needed. Split the Apple News dataset by year (2025 and 2026 separately). For each year, run: (1) Q2 chi-square or Fisher’s exact test for WTK featuring rate vs. all other formulas; (2) Q1 Mann-Whitney U for WTK organic view rank vs. untagged baseline (non-Featured articles only). Compare the featuring lift ratio (WTK featured rate / baseline featured rate) and the organic p-value across years. A narrowing featured rate ratio or a trending organic p-value signals platform behavior change. Implement as a year-stratified extension of the existing Q1 and Q2 analysis blocks in generate_site.py. Report: a 2×2 table of year×metric (featuring lift and organic p) alongside a directional trend flag. Note: Apple News 2026 covers Jan–Mar only; interpret with caution until Q3 2026 data is available.

**What the result unlocks:** Stable across years: confirms structural platform behavior. The “WTK for Featured campaigns, avoid for organic” rule is durable.  Shifting: guidance needs to evolve. If organic performance is catching up to editorial selection, the two-headline distinction may already be outdated.

### [Medium · Untested] Apple News — Possessive Named Entity — Topic Concentration

**Signal:** Possessive named entity headlines (n=95) show moderate overall performance on Apple News. The signal may be concentrated in sports and crime — topics where named individuals are central to the story — but aggregate analysis cannot confirm this.

**Gap:** Overall n=95 is small enough that splitting by topic reduces per-cell counts below the 30-article threshold for reliable inference. The aggregate analysis masks any strong within-topic signal.

**Question:** Do possessive named entity headlines specifically outperform in sports and crime topics on Apple News, where named individuals are central? Is the aggregate signal driven by a strong within-topic effect, or is it distributed broadly across all topics?

**How to run it:** Run on existing Apple News 2025+2026 data. Filter to possessive named entity headlines. Split by topic: sports+crime (the ‘high named-entity’ group) vs. all other topics. Run Mann-Whitney U (sports+crime PNE articles vs. untagged baseline within the same topics), rank-biserial r as effect size. Repeat for the ‘other topics’ group. Compare lift magnitudes: if the sports+crime lift is substantially larger (r ≥0.1 higher) than the other-topics lift, the signal is topic-concentrated. If lifts are similar, the rule applies broadly. If either per-topic cell has n < 20, flag as preliminary and hold until data grows. Do not split into individual topics at this sample size — aggregate sports+crime as one group. Implement as a topic-stratified extension of the Q1 analysis in generate_site.py.

**What the result unlocks:** Confirmed topic-specific: changes guidance from a broad rule to a targeted one (“use possessive named entity for sports/crime stories specifically”). Editors know exactly when to apply it.  Evenly distributed: the broad rule stands. Possessive named entity is generally useful, not vertically restricted.

### [Medium · Untested] SmartNews — Number Lead Type — Which Numbers Drive the SmartNews Signal?

**Signal:** Number leads show a positive directional trend on SmartNews (median rank 0.534 vs. 0.497 baseline; direction: above_dir). They are the only SmartNews formula with a positive directional signal. Whether count/list (‘3 ways’), dollar amounts (‘$2 billion’), or percentages (‘47%’) drive this has not been tested.

**Gap:** Number-type classification (classify_number_lead()) is implemented in the pipeline but per-type SmartNews performance has not been computed. SmartNews 2026 data is domain-aggregated (not article-level), limiting this analysis to the 2025 dataset (n=38,251 articles).

**Question:** Which number-lead subtype drives the SmartNews directional signal: count/list, dollar amounts, or percentages? Or is the effect evenly distributed across number types, suggesting format (any number in the lead) matters more than type?

**How to run it:** Run on SmartNews 2025 number-lead articles (n ≈342 total). classify_number_lead() already extracts ntype (‘count_list,’ ‘dollar_amount,’ ‘percentage,’ ‘other’). Group by ntype and run Mann-Whitney U for each group vs. the untagged baseline, BH-FDR corrected across the three tested types. Expected n per type: count_list is likely the largest (list articles are common); dollar_amount and percentage groups may be small. Flag any group with n < 20 as preliminary. If all subtypes have low n, aggregate and report directionally only: “counts/lists trend higher (n=X, p=Y)” without a significance claim. Implement by extending the existing number-lead deep-dive block (classify_number_lead() section) in generate_site.py to add a per-type Mann-Whitney analysis. Note: SmartNews 2026 is domain-aggregated and cannot contribute to this analysis — 2025 data only.

**What the result unlocks:** Confirmed specific type: editors can be told “count/list numbers work on SmartNews; dollar amounts and percentages are neutral.” More precise than the current directional number-lead guidance.  Equally distributed: the rule is format-driven (“any number in the lead is better than none”). Simpler and more broadly applicable.

---

## Run: 2026-04 (generated 2026-04-08T14:00:16)

_8 suggestion(s) this run_

### [↑ High · Bonferroni fail] SmartNews — “Here’s / Here are” Lift — Needs Confirmation

**Signal:** Articles using “Here’s / Here are” on SmartNews score a median percentile rank of 0.543 vs. 0.500 for the direct-declarative baseline (n=585, raw p=0.038). Direction is positive — opposite to question and “What to know” on the same platform.

**Gap:** Raw p=0.038 does not survive Bonferroni correction at k=5 formula families (threshold α/k = 0.010). All data is observational; no A/B comparison is available. Topic confounding (“Here’s” may correlate with better-performing story types) has not been controlled for.

**Question:** If T1 editors A/B tested “Here’s / Here are” against a direct-declarative version of the same story on SmartNews, would the formula version consistently outperform? Does the effect hold across topics (sports, crime, weather) or appear only in a topic subset?

**How to run it:** For 30–50 stories over 4–6 weeks, write two headline versions per story: (A) “Here’s / Here are” format and (B) a direct declarative covering the same facts. If the CMS supports A/B headline testing, use it; otherwise alternate formula by publication day or assign by outlet. Record SmartNews views at 7 days post-publish. Test: Mann-Whitney U on SmartNews views (A vs. B), rank-biserial r as effect size. Minimum n = 30 matched story pairs for reliable inference. Stratify by topic (sports/crime/weather vs. other) to check whether any interaction hides or drives the aggregate result. Do not use the same story on Apple News A/B — keep platforms separate to avoid contamination.

**What the result unlocks:** Confirmed: adds a positive SmartNews formula signal — currently all confirmed SmartNews guidance is avoidance-only. Editors could be told “Here’s works on SmartNews, unlike Apple News where WTK dominates featuring.”  Not confirmed: SmartNews playbook stays avoidance-only; the directional positive for “Here’s” is noise or topic-driven.

### [Medium · Underpowered] Apple News — Number Lead Specificity — Round vs. Exact Figures

**Signal:** Specific numbers (e.g. ‘$487M’, ‘13 deaths’) score a median rank of 0.405 vs. 0.277 for round numbers on Apple News (n = 165 specific, 21 round)

**Gap:** Groups too small for a reliable test: round n=21, specific n=165.

**Question:** Do Apple News headlines with precise numeric values (e.g. ‘$487 million,’ ‘13 officers’) consistently outperform rounded equivalents (‘$500 million,’ ‘10+ officers’) for views, controlling for topic and story type?

**How to run it:** When writing number-lead headlines, deliberately tag each as ‘round’ (e.g. ‘$500M,’ ‘10 people’) or ‘specific’ (e.g. ‘$487M,’ ‘13 people’) in a shared tracking sheet. Collect at least 30 Apple News articles per type before running the test. No CMS change needed — this is a tagging discipline applied during headline writing. Analysis: Mann-Whitney U on Apple News percentile rank at 7 days (specific vs. round), rank-biserial r as effect size. Stratify by topic (financial stories likely have more specificity variance than crime or sports). Existing pipeline: classify_number_lead() already extracts the numeric value — add a roundness tag to the tracking sheet and re-run once 30+ per group are tagged.

**What the result unlocks:** Confirmed: adds precision-number guidance to the style guide (“use exact figures in number leads, not rounded approximations”). Editors who default to rounded figures for readability would be asked to reverse that practice.  Not confirmed: round vs. specific distinction does not affect views; the number-lead signal is format-driven rather than specificity-driven.

### [↑ High · Underpowered] MSN — MSN Formula Groups — Insufficient Data for Confirmation

**Signal:** 1 formula group(s) show directional patterns on MSN but cannot be confirmed: Quoted lede. 113 total T1 news brand articles after filtering. Groups with n < 30: Quoted lede (n=18).

**Gap:** All flagged groups have n < 30, below the minimum for reliable inference (GOVERNOR.md Part 2). Only the quoted-lede group currently has enough data to test, and it is the one confirmed MSN finding. The MSN dataset grows approximately 100 rows/month; most formula groups should cross n=30 within 2–3 months of continued data collection.

**Question:** As MSN data accumulates, which formula groups consistently underperform the direct-declarative baseline? Is the underperformance pattern broad (all structured formulas hurt on MSN) or specific to certain formats?

**How to run it:** Natural experiment — no new data collection needed. The MSN dataset grows approximately 100 rows/month after the T1 brand filter. Re-run the Mann-Whitney formula analysis each monthly ingest; generate_site.py already does this automatically and the build report surfaces newly-significant groups. Threshold: treat any formula group as testable once it crosses n = 30. Expected timeline: most groups should reach n=30 within 2–3 monthly ingest cycles. Analysis: Mann-Whitney U (each formula group vs. untagged baseline), BH-FDR corrected across all tested groups simultaneously, rank-biserial r as effect size. Language tier: significant only if p_adj < 0.05; directional if p_adj < 0.10. Baseline key must be ‘untagged’ (not ‘other’) — see GOVERNOR.md Rigor Failures Log.

**What the result unlocks:** Confirmed broad pattern: extends the MSN rule from ‘avoid quoted lede’ to ‘avoid all structured formulas.’ Gives editors the strongest possible two-headline guidance: Apple News → use formulas; MSN → drop them entirely.  Confirmed specific subset: MSN avoidance list grows to the confirmed formula types while others remain neutral.  Not confirmed: MSN formula penalty is limited to quoted lede only.

### [↑ High · Untested] Apple News — Character Length × Formula Type Interaction

**Signal:** Character length (90–120 chars) and formula type independently predict Apple News views. Whether these signals interact — e.g., whether possessive named entity needs to be longer to achieve its lift, or whether “Here’s” works at any length — has not been tested.

**Gap:** Cross-tabulating formula buckets with length quartiles fragments an already-segmented dataset. Most formula × length cells will have n < 30, requiring aggregation trade-offs that risk obscuring the interaction signal. Analysis not yet run.

**Question:** Do specific formula types require specific length ranges to achieve their Apple News performance lift? E.g., does “Here’s / Here are” need 90+ chars to work, or does it lift at any length? Does possessive named entity perform best at shorter lengths where the name dominates the headline?

**How to run it:** Run on existing Apple News 2025+2026 data — no new collection needed. Cross-tabulate by formula type × length quartile. For each formula with n ≥30 total, split into Q1 (shortest) and Q4 (longest) length buckets and run Mann-Whitney U within each formula group vs. the untagged baseline at the same length. Compare the lift magnitude across length buckets. If any formula×length cell has n < 15, aggregate: fold Q1+Q2 into ‘short’ and Q3+Q4 into ‘long.’ Report as an interaction: does the formula’s lift increase, decrease, or stay flat as length increases? Plot as a 2×2 heatmap (formula × length bucket, colored by median rank). Apply BH-FDR correction across all formula×length cells tested. Bonferroni fallback: if more than 10 cells are tested, apply Bonferroni at k=10 as a secondary check.

**What the result unlocks:** Confirmed interaction: compound guidance (formula + length range) replaces two independent rules. Editors get: “Use Here’s at 90–110 chars; use possessive at 70–90 chars.” More actionable than current guidance.  No interaction: the two independent rules are stable and can be applied separately without worrying about their interaction.

### [↑ High · Untested] Notifications — Notification CTR × Character Length

**Signal:** Formula choice has a 2–5× effect on notification CTR (confirmed). Character length has been tested for Apple News views but not for notification CTR. Notifications truncate at ~80 chars on most devices, making length more likely to matter here than in feed headlines.

**Gap:** Character length vs. notification CTR has not been run. The notifications dataset covers 2025–2026 (1,050+ news brand pushes with CTR data) — sufficient for a Mann-Whitney test across length quartiles.

**Question:** Do shorter notifications (≤80 chars) outperform longer ones for CTR, controlling for formula type? Is there a character-count range where CTR peaks, or is the relationship monotonic (shorter = better)?

**How to run it:** Run on the existing notifications dataset (1,050+ news brand pushes with CTR). No new data collection needed. Bin notification headlines into four length quartiles. Run Kruskal-Wallis across quartiles first to check for any length–CTR association. If significant (p < 0.05), follow with Mann-Whitney U pairwise comparisons (Q1 vs. Q4 as primary), BH-FDR corrected. Control for formula type via stratification: run the length–CTR analysis separately within each formula group that has n ≥30 (attribution language, question, direct declarative). If length effect disappears within formula groups, length is a formula proxy, not an independent signal. Secondary analysis: Spearman correlation between character count and CTR (raw correlation, no quartiling). This gives a monotonicity check without binning artifacts. Implement in generate_site.py as an extension of the existing Q5 notification analysis block.

**What the result unlocks:** Confirmed: adds a second actionable lever for push copy editors beyond formula choice. Current guidance (“use attribution language”) would be extended with a specific character-count target.  Not confirmed: formula dominates; length doesn’t independently move CTR and editors can focus solely on formula selection for notifications.

### [Medium · Untested] Apple News — “What to Know” — Featured vs. Organic Stability by Year

**Signal:** Apple editors select “What to Know” at 1.8× the baseline rate for Featured placement. Organic (non-Featured) articles using WTK show no significant view lift (p<sub>adj</sub>=0.10). This editorial/algorithmic split is a key project finding — but whether it is stable across 2025 and 2026 separately is unknown.

**Gap:** The current analysis pools 2025 and 2026 Apple News data. If Apple has updated curation signals, or if T1 editors have changed how they use WTK, the featuring lift or organic penalty could be shifting — which would change whether the two-headline strategy is durable guidance.

**Question:** Is the WTK featuring lift consistent when 2025 and 2026 are analyzed separately? Has the gap between editorial selection rate and organic algorithmic performance been stable, or is it narrowing/widening over time?

**How to run it:** Run on existing Apple News data — no new collection needed. Split the Apple News dataset by year (2025 and 2026 separately). For each year, run: (1) Q2 chi-square or Fisher’s exact test for WTK featuring rate vs. all other formulas; (2) Q1 Mann-Whitney U for WTK organic view rank vs. untagged baseline (non-Featured articles only). Compare the featuring lift ratio (WTK featured rate / baseline featured rate) and the organic p-value across years. A narrowing featured rate ratio or a trending organic p-value signals platform behavior change. Implement as a year-stratified extension of the existing Q1 and Q2 analysis blocks in generate_site.py. Report: a 2×2 table of year×metric (featuring lift and organic p) alongside a directional trend flag. Note: Apple News 2026 covers Jan–Mar only; interpret with caution until Q3 2026 data is available.

**What the result unlocks:** Stable across years: confirms structural platform behavior. The “WTK for Featured campaigns, avoid for organic” rule is durable.  Shifting: guidance needs to evolve. If organic performance is catching up to editorial selection, the two-headline distinction may already be outdated.

### [Medium · Untested] Apple News — Possessive Named Entity — Topic Concentration

**Signal:** Possessive named entity headlines (n=95) show moderate overall performance on Apple News. The signal may be concentrated in sports and crime — topics where named individuals are central to the story — but aggregate analysis cannot confirm this.

**Gap:** Overall n=95 is small enough that splitting by topic reduces per-cell counts below the 30-article threshold for reliable inference. The aggregate analysis masks any strong within-topic signal.

**Question:** Do possessive named entity headlines specifically outperform in sports and crime topics on Apple News, where named individuals are central? Is the aggregate signal driven by a strong within-topic effect, or is it distributed broadly across all topics?

**How to run it:** Run on existing Apple News 2025+2026 data. Filter to possessive named entity headlines. Split by topic: sports+crime (the ‘high named-entity’ group) vs. all other topics. Run Mann-Whitney U (sports+crime PNE articles vs. untagged baseline within the same topics), rank-biserial r as effect size. Repeat for the ‘other topics’ group. Compare lift magnitudes: if the sports+crime lift is substantially larger (r ≥0.1 higher) than the other-topics lift, the signal is topic-concentrated. If lifts are similar, the rule applies broadly. If either per-topic cell has n < 20, flag as preliminary and hold until data grows. Do not split into individual topics at this sample size — aggregate sports+crime as one group. Implement as a topic-stratified extension of the Q1 analysis in generate_site.py.

**What the result unlocks:** Confirmed topic-specific: changes guidance from a broad rule to a targeted one (“use possessive named entity for sports/crime stories specifically”). Editors know exactly when to apply it.  Evenly distributed: the broad rule stands. Possessive named entity is generally useful, not vertically restricted.

### [Medium · Untested] SmartNews — Number Lead Type — Which Numbers Drive the SmartNews Signal?

**Signal:** Number leads show a positive directional trend on SmartNews (median rank 0.534 vs. 0.497 baseline; direction: above_dir). They are the only SmartNews formula with a positive directional signal. Whether count/list (‘3 ways’), dollar amounts (‘$2 billion’), or percentages (‘47%’) drive this has not been tested.

**Gap:** Number-type classification (classify_number_lead()) is implemented in the pipeline but per-type SmartNews performance has not been computed. SmartNews 2026 data is domain-aggregated (not article-level), limiting this analysis to the 2025 dataset (n=38,251 articles).

**Question:** Which number-lead subtype drives the SmartNews directional signal: count/list, dollar amounts, or percentages? Or is the effect evenly distributed across number types, suggesting format (any number in the lead) matters more than type?

**How to run it:** Run on SmartNews 2025 number-lead articles (n ≈342 total). classify_number_lead() already extracts ntype (‘count_list,’ ‘dollar_amount,’ ‘percentage,’ ‘other’). Group by ntype and run Mann-Whitney U for each group vs. the untagged baseline, BH-FDR corrected across the three tested types. Expected n per type: count_list is likely the largest (list articles are common); dollar_amount and percentage groups may be small. Flag any group with n < 20 as preliminary. If all subtypes have low n, aggregate and report directionally only: “counts/lists trend higher (n=X, p=Y)” without a significance claim. Implement by extending the existing number-lead deep-dive block (classify_number_lead() section) in generate_site.py to add a per-type Mann-Whitney analysis. Note: SmartNews 2026 is domain-aggregated and cannot contribute to this analysis — 2025 data only.

**What the result unlocks:** Confirmed specific type: editors can be told “count/list numbers work on SmartNews; dollar amounts and percentages are neutral.” More precise than the current directional number-lead guidance.  Equally distributed: the rule is format-driven (“any number in the lead is better than none”). Simpler and more broadly applicable.

---

## Run: 2026-04 (generated 2026-04-08T14:07:51)

_8 suggestion(s) this run_

### [↑ High · Bonferroni fail] SmartNews — “Here’s / Here are” Lift — Needs Confirmation

**Signal:** Articles using “Here’s / Here are” on SmartNews score a median percentile rank of 0.543 vs. 0.500 for the direct-declarative baseline (n=585, raw p=0.038). Direction is positive — opposite to question and “What to know” on the same platform.

**Gap:** Raw p=0.038 does not survive Bonferroni correction at k=5 formula families (threshold α/k = 0.010). All data is observational; no A/B comparison is available. Topic confounding (“Here’s” may correlate with better-performing story types) has not been controlled for.

**Question:** If T1 editors A/B tested “Here’s / Here are” against a direct-declarative version of the same story on SmartNews, would the formula version consistently outperform? Does the effect hold across topics (sports, crime, weather) or appear only in a topic subset?

**How to run it:** For 30–50 stories over 4–6 weeks, write two headline versions per story: (A) “Here’s / Here are” format and (B) a direct declarative covering the same facts. If the CMS supports A/B headline testing, use it; otherwise alternate formula by publication day or assign by outlet. Record SmartNews views at 7 days post-publish. Test: Mann-Whitney U on SmartNews views (A vs. B), rank-biserial r as effect size. Minimum n = 30 matched story pairs for reliable inference. Stratify by topic (sports/crime/weather vs. other) to check whether any interaction hides or drives the aggregate result. Do not use the same story on Apple News A/B — keep platforms separate to avoid contamination.

**What the result unlocks:** Confirmed: adds a positive SmartNews formula signal — currently all confirmed SmartNews guidance is avoidance-only. Editors could be told “Here’s works on SmartNews, unlike Apple News where WTK dominates featuring.”  Not confirmed: SmartNews playbook stays avoidance-only; the directional positive for “Here’s” is noise or topic-driven.

### [Medium · Underpowered] Apple News — Number Lead Specificity — Round vs. Exact Figures

**Signal:** Specific numbers (e.g. ‘$487M’, ‘13 deaths’) score a median rank of 0.405 vs. 0.277 for round numbers on Apple News (n = 165 specific, 21 round)

**Gap:** Groups too small for a reliable test: round n=21, specific n=165.

**Question:** Do Apple News headlines with precise numeric values (e.g. ‘$487 million,’ ‘13 officers’) consistently outperform rounded equivalents (‘$500 million,’ ‘10+ officers’) for views, controlling for topic and story type?

**How to run it:** When writing number-lead headlines, deliberately tag each as ‘round’ (e.g. ‘$500M,’ ‘10 people’) or ‘specific’ (e.g. ‘$487M,’ ‘13 people’) in a shared tracking sheet. Collect at least 30 Apple News articles per type before running the test. No CMS change needed — this is a tagging discipline applied during headline writing. Analysis: Mann-Whitney U on Apple News percentile rank at 7 days (specific vs. round), rank-biserial r as effect size. Stratify by topic (financial stories likely have more specificity variance than crime or sports). Existing pipeline: classify_number_lead() already extracts the numeric value — add a roundness tag to the tracking sheet and re-run once 30+ per group are tagged.

**What the result unlocks:** Confirmed: adds precision-number guidance to the style guide (“use exact figures in number leads, not rounded approximations”). Editors who default to rounded figures for readability would be asked to reverse that practice.  Not confirmed: round vs. specific distinction does not affect views; the number-lead signal is format-driven rather than specificity-driven.

### [↑ High · Underpowered] MSN — MSN Formula Groups — Insufficient Data for Confirmation

**Signal:** 1 formula group(s) show directional patterns on MSN but cannot be confirmed: Quoted lede. 113 total T1 news brand articles after filtering. Groups with n < 30: Quoted lede (n=18).

**Gap:** All flagged groups have n < 30, below the minimum for reliable inference (GOVERNOR.md Part 2). Only the quoted-lede group currently has enough data to test, and it is the one confirmed MSN finding. The MSN dataset grows approximately 100 rows/month; most formula groups should cross n=30 within 2–3 months of continued data collection.

**Question:** As MSN data accumulates, which formula groups consistently underperform the direct-declarative baseline? Is the underperformance pattern broad (all structured formulas hurt on MSN) or specific to certain formats?

**How to run it:** Natural experiment — no new data collection needed. The MSN dataset grows approximately 100 rows/month after the T1 brand filter. Re-run the Mann-Whitney formula analysis each monthly ingest; generate_site.py already does this automatically and the build report surfaces newly-significant groups. Threshold: treat any formula group as testable once it crosses n = 30. Expected timeline: most groups should reach n=30 within 2–3 monthly ingest cycles. Analysis: Mann-Whitney U (each formula group vs. untagged baseline), BH-FDR corrected across all tested groups simultaneously, rank-biserial r as effect size. Language tier: significant only if p_adj < 0.05; directional if p_adj < 0.10. Baseline key must be ‘untagged’ (not ‘other’) — see GOVERNOR.md Rigor Failures Log.

**What the result unlocks:** Confirmed broad pattern: extends the MSN rule from ‘avoid quoted lede’ to ‘avoid all structured formulas.’ Gives editors the strongest possible two-headline guidance: Apple News → use formulas; MSN → drop them entirely.  Confirmed specific subset: MSN avoidance list grows to the confirmed formula types while others remain neutral.  Not confirmed: MSN formula penalty is limited to quoted lede only.

### [↑ High · Untested] Apple News — Character Length × Formula Type Interaction

**Signal:** Character length (90–120 chars) and formula type independently predict Apple News views. Whether these signals interact — e.g., whether possessive named entity needs to be longer to achieve its lift, or whether “Here’s” works at any length — has not been tested.

**Gap:** Cross-tabulating formula buckets with length quartiles fragments an already-segmented dataset. Most formula × length cells will have n < 30, requiring aggregation trade-offs that risk obscuring the interaction signal. Analysis not yet run.

**Question:** Do specific formula types require specific length ranges to achieve their Apple News performance lift? E.g., does “Here’s / Here are” need 90+ chars to work, or does it lift at any length? Does possessive named entity perform best at shorter lengths where the name dominates the headline?

**How to run it:** Run on existing Apple News 2025+2026 data — no new collection needed. Cross-tabulate by formula type × length quartile. For each formula with n ≥30 total, split into Q1 (shortest) and Q4 (longest) length buckets and run Mann-Whitney U within each formula group vs. the untagged baseline at the same length. Compare the lift magnitude across length buckets. If any formula×length cell has n < 15, aggregate: fold Q1+Q2 into ‘short’ and Q3+Q4 into ‘long.’ Report as an interaction: does the formula’s lift increase, decrease, or stay flat as length increases? Plot as a 2×2 heatmap (formula × length bucket, colored by median rank). Apply BH-FDR correction across all formula×length cells tested. Bonferroni fallback: if more than 10 cells are tested, apply Bonferroni at k=10 as a secondary check.

**What the result unlocks:** Confirmed interaction: compound guidance (formula + length range) replaces two independent rules. Editors get: “Use Here’s at 90–110 chars; use possessive at 70–90 chars.” More actionable than current guidance.  No interaction: the two independent rules are stable and can be applied separately without worrying about their interaction.

### [↑ High · Untested] Notifications — Notification CTR × Character Length

**Signal:** Formula choice has a 2–5× effect on notification CTR (confirmed). Character length has been tested for Apple News views but not for notification CTR. Notifications truncate at ~80 chars on most devices, making length more likely to matter here than in feed headlines.

**Gap:** Character length vs. notification CTR has not been run. The notifications dataset covers 2025–2026 (1,050+ news brand pushes with CTR data) — sufficient for a Mann-Whitney test across length quartiles.

**Question:** Do shorter notifications (≤80 chars) outperform longer ones for CTR, controlling for formula type? Is there a character-count range where CTR peaks, or is the relationship monotonic (shorter = better)?

**How to run it:** Run on the existing notifications dataset (1,050+ news brand pushes with CTR). No new data collection needed. Bin notification headlines into four length quartiles. Run Kruskal-Wallis across quartiles first to check for any length–CTR association. If significant (p < 0.05), follow with Mann-Whitney U pairwise comparisons (Q1 vs. Q4 as primary), BH-FDR corrected. Control for formula type via stratification: run the length–CTR analysis separately within each formula group that has n ≥30 (attribution language, question, direct declarative). If length effect disappears within formula groups, length is a formula proxy, not an independent signal. Secondary analysis: Spearman correlation between character count and CTR (raw correlation, no quartiling). This gives a monotonicity check without binning artifacts. Implement in generate_site.py as an extension of the existing Q5 notification analysis block.

**What the result unlocks:** Confirmed: adds a second actionable lever for push copy editors beyond formula choice. Current guidance (“use attribution language”) would be extended with a specific character-count target.  Not confirmed: formula dominates; length doesn’t independently move CTR and editors can focus solely on formula selection for notifications.

### [Medium · Untested] Apple News — “What to Know” — Featured vs. Organic Stability by Year

**Signal:** Apple editors select “What to Know” at 1.8× the baseline rate for Featured placement. Organic (non-Featured) articles using WTK show no significant view lift (p<sub>adj</sub>=0.10). This editorial/algorithmic split is a key project finding — but whether it is stable across 2025 and 2026 separately is unknown.

**Gap:** The current analysis pools 2025 and 2026 Apple News data. If Apple has updated curation signals, or if T1 editors have changed how they use WTK, the featuring lift or organic penalty could be shifting — which would change whether the two-headline strategy is durable guidance.

**Question:** Is the WTK featuring lift consistent when 2025 and 2026 are analyzed separately? Has the gap between editorial selection rate and organic algorithmic performance been stable, or is it narrowing/widening over time?

**How to run it:** Run on existing Apple News data — no new collection needed. Split the Apple News dataset by year (2025 and 2026 separately). For each year, run: (1) Q2 chi-square or Fisher’s exact test for WTK featuring rate vs. all other formulas; (2) Q1 Mann-Whitney U for WTK organic view rank vs. untagged baseline (non-Featured articles only). Compare the featuring lift ratio (WTK featured rate / baseline featured rate) and the organic p-value across years. A narrowing featured rate ratio or a trending organic p-value signals platform behavior change. Implement as a year-stratified extension of the existing Q1 and Q2 analysis blocks in generate_site.py. Report: a 2×2 table of year×metric (featuring lift and organic p) alongside a directional trend flag. Note: Apple News 2026 covers Jan–Mar only; interpret with caution until Q3 2026 data is available.

**What the result unlocks:** Stable across years: confirms structural platform behavior. The “WTK for Featured campaigns, avoid for organic” rule is durable.  Shifting: guidance needs to evolve. If organic performance is catching up to editorial selection, the two-headline distinction may already be outdated.

### [Medium · Untested] Apple News — Possessive Named Entity — Topic Concentration

**Signal:** Possessive named entity headlines (n=95) show moderate overall performance on Apple News. The signal may be concentrated in sports and crime — topics where named individuals are central to the story — but aggregate analysis cannot confirm this.

**Gap:** Overall n=95 is small enough that splitting by topic reduces per-cell counts below the 30-article threshold for reliable inference. The aggregate analysis masks any strong within-topic signal.

**Question:** Do possessive named entity headlines specifically outperform in sports and crime topics on Apple News, where named individuals are central? Is the aggregate signal driven by a strong within-topic effect, or is it distributed broadly across all topics?

**How to run it:** Run on existing Apple News 2025+2026 data. Filter to possessive named entity headlines. Split by topic: sports+crime (the ‘high named-entity’ group) vs. all other topics. Run Mann-Whitney U (sports+crime PNE articles vs. untagged baseline within the same topics), rank-biserial r as effect size. Repeat for the ‘other topics’ group. Compare lift magnitudes: if the sports+crime lift is substantially larger (r ≥0.1 higher) than the other-topics lift, the signal is topic-concentrated. If lifts are similar, the rule applies broadly. If either per-topic cell has n < 20, flag as preliminary and hold until data grows. Do not split into individual topics at this sample size — aggregate sports+crime as one group. Implement as a topic-stratified extension of the Q1 analysis in generate_site.py.

**What the result unlocks:** Confirmed topic-specific: changes guidance from a broad rule to a targeted one (“use possessive named entity for sports/crime stories specifically”). Editors know exactly when to apply it.  Evenly distributed: the broad rule stands. Possessive named entity is generally useful, not vertically restricted.

### [Medium · Untested] SmartNews — Number Lead Type — Which Numbers Drive the SmartNews Signal?

**Signal:** Number leads show a positive directional trend on SmartNews (median rank 0.534 vs. 0.497 baseline; direction: above_dir). They are the only SmartNews formula with a positive directional signal. Whether count/list (‘3 ways’), dollar amounts (‘$2 billion’), or percentages (‘47%’) drive this has not been tested.

**Gap:** Number-type classification (classify_number_lead()) is implemented in the pipeline but per-type SmartNews performance has not been computed. SmartNews 2026 data is domain-aggregated (not article-level), limiting this analysis to the 2025 dataset (n=38,251 articles).

**Question:** Which number-lead subtype drives the SmartNews directional signal: count/list, dollar amounts, or percentages? Or is the effect evenly distributed across number types, suggesting format (any number in the lead) matters more than type?

**How to run it:** Run on SmartNews 2025 number-lead articles (n ≈342 total). classify_number_lead() already extracts ntype (‘count_list,’ ‘dollar_amount,’ ‘percentage,’ ‘other’). Group by ntype and run Mann-Whitney U for each group vs. the untagged baseline, BH-FDR corrected across the three tested types. Expected n per type: count_list is likely the largest (list articles are common); dollar_amount and percentage groups may be small. Flag any group with n < 20 as preliminary. If all subtypes have low n, aggregate and report directionally only: “counts/lists trend higher (n=X, p=Y)” without a significance claim. Implement by extending the existing number-lead deep-dive block (classify_number_lead() section) in generate_site.py to add a per-type Mann-Whitney analysis. Note: SmartNews 2026 is domain-aggregated and cannot contribute to this analysis — 2025 data only.

**What the result unlocks:** Confirmed specific type: editors can be told “count/list numbers work on SmartNews; dollar amounts and percentages are neutral.” More precise than the current directional number-lead guidance.  Equally distributed: the rule is format-driven (“any number in the lead is better than none”). Simpler and more broadly applicable.

---

## Run: 2026-04 (generated 2026-04-08T14:18:50)

_8 suggestion(s) this run_

### [↑ High · Bonferroni fail] SmartNews — “Here’s / Here are” Lift — Needs Confirmation

**Signal:** Articles using “Here’s / Here are” on SmartNews score a median percentile rank of 0.543 vs. 0.500 for the direct-declarative baseline (n=585, raw p=0.038). Direction is positive — opposite to question and “What to know” on the same platform.

**Gap:** Raw p=0.038 does not survive Bonferroni correction at k=5 formula families (threshold α/k = 0.010). All data is observational; no A/B comparison is available. Topic confounding (“Here’s” may correlate with better-performing story types) has not been controlled for.

**Question:** If T1 editors A/B tested “Here’s / Here are” against a direct-declarative version of the same story on SmartNews, would the formula version consistently outperform? Does the effect hold across topics (sports, crime, weather) or appear only in a topic subset?

**How to run it:** For 30–50 stories over 4–6 weeks, write two headline versions per story: (A) “Here’s / Here are” format and (B) a direct declarative covering the same facts. If the CMS supports A/B headline testing, use it; otherwise alternate formula by publication day or assign by outlet. Record SmartNews views at 7 days post-publish. Test: Mann-Whitney U on SmartNews views (A vs. B), rank-biserial r as effect size. Minimum n = 30 matched story pairs for reliable inference. Stratify by topic (sports/crime/weather vs. other) to check whether any interaction hides or drives the aggregate result. Do not use the same story on Apple News A/B — keep platforms separate to avoid contamination.

**What the result unlocks:** Confirmed: adds a positive SmartNews formula signal — currently all confirmed SmartNews guidance is avoidance-only. Editors could be told “Here’s works on SmartNews, unlike Apple News where WTK dominates featuring.”  Not confirmed: SmartNews playbook stays avoidance-only; the directional positive for “Here’s” is noise or topic-driven.

### [Medium · Underpowered] Apple News — Number Lead Specificity — Round vs. Exact Figures

**Signal:** Specific numbers (e.g. ‘$487M’, ‘13 deaths’) score a median rank of 0.405 vs. 0.277 for round numbers on Apple News (n = 165 specific, 21 round)

**Gap:** Groups too small for a reliable test: round n=21, specific n=165.

**Question:** Do Apple News headlines with precise numeric values (e.g. ‘$487 million,’ ‘13 officers’) consistently outperform rounded equivalents (‘$500 million,’ ‘10+ officers’) for views, controlling for topic and story type?

**How to run it:** When writing number-lead headlines, deliberately tag each as ‘round’ (e.g. ‘$500M,’ ‘10 people’) or ‘specific’ (e.g. ‘$487M,’ ‘13 people’) in a shared tracking sheet. Collect at least 30 Apple News articles per type before running the test. No CMS change needed — this is a tagging discipline applied during headline writing. Analysis: Mann-Whitney U on Apple News percentile rank at 7 days (specific vs. round), rank-biserial r as effect size. Stratify by topic (financial stories likely have more specificity variance than crime or sports). Existing pipeline: classify_number_lead() already extracts the numeric value — add a roundness tag to the tracking sheet and re-run once 30+ per group are tagged.

**What the result unlocks:** Confirmed: adds precision-number guidance to the style guide (“use exact figures in number leads, not rounded approximations”). Editors who default to rounded figures for readability would be asked to reverse that practice.  Not confirmed: round vs. specific distinction does not affect views; the number-lead signal is format-driven rather than specificity-driven.

### [↑ High · Underpowered] MSN — MSN Formula Groups — Insufficient Data for Confirmation

**Signal:** 1 formula group(s) show directional patterns on MSN but cannot be confirmed: Quoted lede. 113 total T1 news brand articles after filtering. Groups with n < 30: Quoted lede (n=18).

**Gap:** All flagged groups have n < 30, below the minimum for reliable inference (GOVERNOR.md Part 2). Only the quoted-lede group currently has enough data to test, and it is the one confirmed MSN finding. The MSN dataset grows approximately 100 rows/month; most formula groups should cross n=30 within 2–3 months of continued data collection.

**Question:** As MSN data accumulates, which formula groups consistently underperform the direct-declarative baseline? Is the underperformance pattern broad (all structured formulas hurt on MSN) or specific to certain formats?

**How to run it:** Natural experiment — no new data collection needed. The MSN dataset grows approximately 100 rows/month after the T1 brand filter. Re-run the Mann-Whitney formula analysis each monthly ingest; generate_site.py already does this automatically and the build report surfaces newly-significant groups. Threshold: treat any formula group as testable once it crosses n = 30. Expected timeline: most groups should reach n=30 within 2–3 monthly ingest cycles. Analysis: Mann-Whitney U (each formula group vs. untagged baseline), BH-FDR corrected across all tested groups simultaneously, rank-biserial r as effect size. Language tier: significant only if p_adj < 0.05; directional if p_adj < 0.10. Baseline key must be ‘untagged’ (not ‘other’) — see GOVERNOR.md Rigor Failures Log.

**What the result unlocks:** Confirmed broad pattern: extends the MSN rule from ‘avoid quoted lede’ to ‘avoid all structured formulas.’ Gives editors the strongest possible two-headline guidance: Apple News → use formulas; MSN → drop them entirely.  Confirmed specific subset: MSN avoidance list grows to the confirmed formula types while others remain neutral.  Not confirmed: MSN formula penalty is limited to quoted lede only.

### [↑ High · Untested] Apple News — Character Length × Formula Type Interaction

**Signal:** Character length (90–120 chars) and formula type independently predict Apple News views. Whether these signals interact — e.g., whether possessive named entity needs to be longer to achieve its lift, or whether “Here’s” works at any length — has not been tested.

**Gap:** Cross-tabulating formula buckets with length quartiles fragments an already-segmented dataset. Most formula × length cells will have n < 30, requiring aggregation trade-offs that risk obscuring the interaction signal. Analysis not yet run.

**Question:** Do specific formula types require specific length ranges to achieve their Apple News performance lift? E.g., does “Here’s / Here are” need 90+ chars to work, or does it lift at any length? Does possessive named entity perform best at shorter lengths where the name dominates the headline?

**How to run it:** Run on existing Apple News 2025+2026 data — no new collection needed. Cross-tabulate by formula type × length quartile. For each formula with n ≥30 total, split into Q1 (shortest) and Q4 (longest) length buckets and run Mann-Whitney U within each formula group vs. the untagged baseline at the same length. Compare the lift magnitude across length buckets. If any formula×length cell has n < 15, aggregate: fold Q1+Q2 into ‘short’ and Q3+Q4 into ‘long.’ Report as an interaction: does the formula’s lift increase, decrease, or stay flat as length increases? Plot as a 2×2 heatmap (formula × length bucket, colored by median rank). Apply BH-FDR correction across all formula×length cells tested. Bonferroni fallback: if more than 10 cells are tested, apply Bonferroni at k=10 as a secondary check.

**What the result unlocks:** Confirmed interaction: compound guidance (formula + length range) replaces two independent rules. Editors get: “Use Here’s at 90–110 chars; use possessive at 70–90 chars.” More actionable than current guidance.  No interaction: the two independent rules are stable and can be applied separately without worrying about their interaction.

### [↑ High · Untested] Notifications — Notification CTR × Character Length

**Signal:** Formula choice has a 2–5× effect on notification CTR (confirmed). Character length has been tested for Apple News views but not for notification CTR. Notifications truncate at ~80 chars on most devices, making length more likely to matter here than in feed headlines.

**Gap:** Character length vs. notification CTR has not been run. The notifications dataset covers 2025–2026 (1,050+ news brand pushes with CTR data) — sufficient for a Mann-Whitney test across length quartiles.

**Question:** Do shorter notifications (≤80 chars) outperform longer ones for CTR, controlling for formula type? Is there a character-count range where CTR peaks, or is the relationship monotonic (shorter = better)?

**How to run it:** Run on the existing notifications dataset (1,050+ news brand pushes with CTR). No new data collection needed. Bin notification headlines into four length quartiles. Run Kruskal-Wallis across quartiles first to check for any length–CTR association. If significant (p < 0.05), follow with Mann-Whitney U pairwise comparisons (Q1 vs. Q4 as primary), BH-FDR corrected. Control for formula type via stratification: run the length–CTR analysis separately within each formula group that has n ≥30 (attribution language, question, direct declarative). If length effect disappears within formula groups, length is a formula proxy, not an independent signal. Secondary analysis: Spearman correlation between character count and CTR (raw correlation, no quartiling). This gives a monotonicity check without binning artifacts. Implement in generate_site.py as an extension of the existing Q5 notification analysis block.

**What the result unlocks:** Confirmed: adds a second actionable lever for push copy editors beyond formula choice. Current guidance (“use attribution language”) would be extended with a specific character-count target.  Not confirmed: formula dominates; length doesn’t independently move CTR and editors can focus solely on formula selection for notifications.

### [Medium · Untested] Apple News — “What to Know” — Featured vs. Organic Stability by Year

**Signal:** Apple editors select “What to Know” at 1.8× the baseline rate for Featured placement. Organic (non-Featured) articles using WTK show no significant view lift (p<sub>adj</sub>=0.10). This editorial/algorithmic split is a key project finding — but whether it is stable across 2025 and 2026 separately is unknown.

**Gap:** The current analysis pools 2025 and 2026 Apple News data. If Apple has updated curation signals, or if T1 editors have changed how they use WTK, the featuring lift or organic penalty could be shifting — which would change whether the two-headline strategy is durable guidance.

**Question:** Is the WTK featuring lift consistent when 2025 and 2026 are analyzed separately? Has the gap between editorial selection rate and organic algorithmic performance been stable, or is it narrowing/widening over time?

**How to run it:** Run on existing Apple News data — no new collection needed. Split the Apple News dataset by year (2025 and 2026 separately). For each year, run: (1) Q2 chi-square or Fisher’s exact test for WTK featuring rate vs. all other formulas; (2) Q1 Mann-Whitney U for WTK organic view rank vs. untagged baseline (non-Featured articles only). Compare the featuring lift ratio (WTK featured rate / baseline featured rate) and the organic p-value across years. A narrowing featured rate ratio or a trending organic p-value signals platform behavior change. Implement as a year-stratified extension of the existing Q1 and Q2 analysis blocks in generate_site.py. Report: a 2×2 table of year×metric (featuring lift and organic p) alongside a directional trend flag. Note: Apple News 2026 covers Jan–Mar only; interpret with caution until Q3 2026 data is available.

**What the result unlocks:** Stable across years: confirms structural platform behavior. The “WTK for Featured campaigns, avoid for organic” rule is durable.  Shifting: guidance needs to evolve. If organic performance is catching up to editorial selection, the two-headline distinction may already be outdated.

### [Medium · Untested] Apple News — Possessive Named Entity — Topic Concentration

**Signal:** Possessive named entity headlines (n=95) show moderate overall performance on Apple News. The signal may be concentrated in sports and crime — topics where named individuals are central to the story — but aggregate analysis cannot confirm this.

**Gap:** Overall n=95 is small enough that splitting by topic reduces per-cell counts below the 30-article threshold for reliable inference. The aggregate analysis masks any strong within-topic signal.

**Question:** Do possessive named entity headlines specifically outperform in sports and crime topics on Apple News, where named individuals are central? Is the aggregate signal driven by a strong within-topic effect, or is it distributed broadly across all topics?

**How to run it:** Run on existing Apple News 2025+2026 data. Filter to possessive named entity headlines. Split by topic: sports+crime (the ‘high named-entity’ group) vs. all other topics. Run Mann-Whitney U (sports+crime PNE articles vs. untagged baseline within the same topics), rank-biserial r as effect size. Repeat for the ‘other topics’ group. Compare lift magnitudes: if the sports+crime lift is substantially larger (r ≥0.1 higher) than the other-topics lift, the signal is topic-concentrated. If lifts are similar, the rule applies broadly. If either per-topic cell has n < 20, flag as preliminary and hold until data grows. Do not split into individual topics at this sample size — aggregate sports+crime as one group. Implement as a topic-stratified extension of the Q1 analysis in generate_site.py.

**What the result unlocks:** Confirmed topic-specific: changes guidance from a broad rule to a targeted one (“use possessive named entity for sports/crime stories specifically”). Editors know exactly when to apply it.  Evenly distributed: the broad rule stands. Possessive named entity is generally useful, not vertically restricted.

### [Medium · Untested] SmartNews — Number Lead Type — Which Numbers Drive the SmartNews Signal?

**Signal:** Number leads show a positive directional trend on SmartNews (median rank 0.534 vs. 0.497 baseline; direction: above_dir). They are the only SmartNews formula with a positive directional signal. Whether count/list (‘3 ways’), dollar amounts (‘$2 billion’), or percentages (‘47%’) drive this has not been tested.

**Gap:** Number-type classification (classify_number_lead()) is implemented in the pipeline but per-type SmartNews performance has not been computed. SmartNews 2026 data is domain-aggregated (not article-level), limiting this analysis to the 2025 dataset (n=38,251 articles).

**Question:** Which number-lead subtype drives the SmartNews directional signal: count/list, dollar amounts, or percentages? Or is the effect evenly distributed across number types, suggesting format (any number in the lead) matters more than type?

**How to run it:** Run on SmartNews 2025 number-lead articles (n ≈342 total). classify_number_lead() already extracts ntype (‘count_list,’ ‘dollar_amount,’ ‘percentage,’ ‘other’). Group by ntype and run Mann-Whitney U for each group vs. the untagged baseline, BH-FDR corrected across the three tested types. Expected n per type: count_list is likely the largest (list articles are common); dollar_amount and percentage groups may be small. Flag any group with n < 20 as preliminary. If all subtypes have low n, aggregate and report directionally only: “counts/lists trend higher (n=X, p=Y)” without a significance claim. Implement by extending the existing number-lead deep-dive block (classify_number_lead() section) in generate_site.py to add a per-type Mann-Whitney analysis. Note: SmartNews 2026 is domain-aggregated and cannot contribute to this analysis — 2025 data only.

**What the result unlocks:** Confirmed specific type: editors can be told “count/list numbers work on SmartNews; dollar amounts and percentages are neutral.” More precise than the current directional number-lead guidance.  Equally distributed: the rule is format-driven (“any number in the lead is better than none”). Simpler and more broadly applicable.

---

## Run: 2026-04 (generated 2026-04-08T14:27:50)

_8 suggestion(s) this run_

### [↑ High · Bonferroni fail] SmartNews — “Here’s / Here are” Lift — Needs Confirmation

**Signal:** Articles using “Here’s / Here are” on SmartNews score a median percentile rank of 0.543 vs. 0.500 for the direct-declarative baseline (n=585, raw p=0.038). Direction is positive — opposite to question and “What to know” on the same platform.

**Gap:** Raw p=0.038 does not survive Bonferroni correction at k=5 formula families (threshold α/k = 0.010). All data is observational; no A/B comparison is available. Topic confounding (“Here’s” may correlate with better-performing story types) has not been controlled for.

**Question:** If T1 editors A/B tested “Here’s / Here are” against a direct-declarative version of the same story on SmartNews, would the formula version consistently outperform? Does the effect hold across topics (sports, crime, weather) or appear only in a topic subset?

**How to run it:** For 30–50 stories over 4–6 weeks, write two headline versions per story: (A) “Here’s / Here are” format and (B) a direct declarative covering the same facts. If the CMS supports A/B headline testing, use it; otherwise alternate formula by publication day or assign by outlet. Record SmartNews views at 7 days post-publish. Test: Mann-Whitney U on SmartNews views (A vs. B), rank-biserial r as effect size. Minimum n = 30 matched story pairs for reliable inference. Stratify by topic (sports/crime/weather vs. other) to check whether any interaction hides or drives the aggregate result. Do not use the same story on Apple News A/B — keep platforms separate to avoid contamination.

**What the result unlocks:** Confirmed: adds a positive SmartNews formula signal — currently all confirmed SmartNews guidance is avoidance-only. Editors could be told “Here’s works on SmartNews, unlike Apple News where WTK dominates featuring.”  Not confirmed: SmartNews playbook stays avoidance-only; the directional positive for “Here’s” is noise or topic-driven.

### [Medium · Underpowered] Apple News — Number Lead Specificity — Round vs. Exact Figures

**Signal:** Specific numbers (e.g. ‘$487M’, ‘13 deaths’) score a median rank of 0.405 vs. 0.277 for round numbers on Apple News (n = 165 specific, 21 round)

**Gap:** Groups too small for a reliable test: round n=21, specific n=165.

**Question:** Do Apple News headlines with precise numeric values (e.g. ‘$487 million,’ ‘13 officers’) consistently outperform rounded equivalents (‘$500 million,’ ‘10+ officers’) for views, controlling for topic and story type?

**How to run it:** When writing number-lead headlines, deliberately tag each as ‘round’ (e.g. ‘$500M,’ ‘10 people’) or ‘specific’ (e.g. ‘$487M,’ ‘13 people’) in a shared tracking sheet. Collect at least 30 Apple News articles per type before running the test. No CMS change needed — this is a tagging discipline applied during headline writing. Analysis: Mann-Whitney U on Apple News percentile rank at 7 days (specific vs. round), rank-biserial r as effect size. Stratify by topic (financial stories likely have more specificity variance than crime or sports). Existing pipeline: classify_number_lead() already extracts the numeric value — add a roundness tag to the tracking sheet and re-run once 30+ per group are tagged.

**What the result unlocks:** Confirmed: adds precision-number guidance to the style guide (“use exact figures in number leads, not rounded approximations”). Editors who default to rounded figures for readability would be asked to reverse that practice.  Not confirmed: round vs. specific distinction does not affect views; the number-lead signal is format-driven rather than specificity-driven.

### [↑ High · Underpowered] MSN — MSN Formula Groups — Insufficient Data for Confirmation

**Signal:** 1 formula group(s) show directional patterns on MSN but cannot be confirmed: Quoted lede. 113 total T1 news brand articles after filtering. Groups with n < 30: Quoted lede (n=18).

**Gap:** All flagged groups have n < 30, below the minimum for reliable inference (GOVERNOR.md Part 2). Only the quoted-lede group currently has enough data to test, and it is the one confirmed MSN finding. The MSN dataset grows approximately 100 rows/month; most formula groups should cross n=30 within 2–3 months of continued data collection.

**Question:** As MSN data accumulates, which formula groups consistently underperform the direct-declarative baseline? Is the underperformance pattern broad (all structured formulas hurt on MSN) or specific to certain formats?

**How to run it:** Natural experiment — no new data collection needed. The MSN dataset grows approximately 100 rows/month after the T1 brand filter. Re-run the Mann-Whitney formula analysis each monthly ingest; generate_site.py already does this automatically and the build report surfaces newly-significant groups. Threshold: treat any formula group as testable once it crosses n = 30. Expected timeline: most groups should reach n=30 within 2–3 monthly ingest cycles. Analysis: Mann-Whitney U (each formula group vs. untagged baseline), BH-FDR corrected across all tested groups simultaneously, rank-biserial r as effect size. Language tier: significant only if p_adj < 0.05; directional if p_adj < 0.10. Baseline key must be ‘untagged’ (not ‘other’) — see GOVERNOR.md Rigor Failures Log.

**What the result unlocks:** Confirmed broad pattern: extends the MSN rule from ‘avoid quoted lede’ to ‘avoid all structured formulas.’ Gives editors the strongest possible two-headline guidance: Apple News → use formulas; MSN → drop them entirely.  Confirmed specific subset: MSN avoidance list grows to the confirmed formula types while others remain neutral.  Not confirmed: MSN formula penalty is limited to quoted lede only.

### [↑ High · Untested] Apple News — Character Length × Formula Type Interaction

**Signal:** Character length (90–120 chars) and formula type independently predict Apple News views. Whether these signals interact — e.g., whether possessive named entity needs to be longer to achieve its lift, or whether “Here’s” works at any length — has not been tested.

**Gap:** Cross-tabulating formula buckets with length quartiles fragments an already-segmented dataset. Most formula × length cells will have n < 30, requiring aggregation trade-offs that risk obscuring the interaction signal. Analysis not yet run.

**Question:** Do specific formula types require specific length ranges to achieve their Apple News performance lift? E.g., does “Here’s / Here are” need 90+ chars to work, or does it lift at any length? Does possessive named entity perform best at shorter lengths where the name dominates the headline?

**How to run it:** Run on existing Apple News 2025+2026 data — no new collection needed. Cross-tabulate by formula type × length quartile. For each formula with n ≥30 total, split into Q1 (shortest) and Q4 (longest) length buckets and run Mann-Whitney U within each formula group vs. the untagged baseline at the same length. Compare the lift magnitude across length buckets. If any formula×length cell has n < 15, aggregate: fold Q1+Q2 into ‘short’ and Q3+Q4 into ‘long.’ Report as an interaction: does the formula’s lift increase, decrease, or stay flat as length increases? Plot as a 2×2 heatmap (formula × length bucket, colored by median rank). Apply BH-FDR correction across all formula×length cells tested. Bonferroni fallback: if more than 10 cells are tested, apply Bonferroni at k=10 as a secondary check.

**What the result unlocks:** Confirmed interaction: compound guidance (formula + length range) replaces two independent rules. Editors get: “Use Here’s at 90–110 chars; use possessive at 70–90 chars.” More actionable than current guidance.  No interaction: the two independent rules are stable and can be applied separately without worrying about their interaction.

### [↑ High · Untested] Notifications — Notification CTR × Character Length

**Signal:** Formula choice has a 2–5× effect on notification CTR (confirmed). Character length has been tested for Apple News views but not for notification CTR. Notifications truncate at ~80 chars on most devices, making length more likely to matter here than in feed headlines.

**Gap:** Character length vs. notification CTR has not been run. The notifications dataset covers 2025–2026 (1,050+ news brand pushes with CTR data) — sufficient for a Mann-Whitney test across length quartiles.

**Question:** Do shorter notifications (≤80 chars) outperform longer ones for CTR, controlling for formula type? Is there a character-count range where CTR peaks, or is the relationship monotonic (shorter = better)?

**How to run it:** Run on the existing notifications dataset (1,050+ news brand pushes with CTR). No new data collection needed. Bin notification headlines into four length quartiles. Run Kruskal-Wallis across quartiles first to check for any length–CTR association. If significant (p < 0.05), follow with Mann-Whitney U pairwise comparisons (Q1 vs. Q4 as primary), BH-FDR corrected. Control for formula type via stratification: run the length–CTR analysis separately within each formula group that has n ≥30 (attribution language, question, direct declarative). If length effect disappears within formula groups, length is a formula proxy, not an independent signal. Secondary analysis: Spearman correlation between character count and CTR (raw correlation, no quartiling). This gives a monotonicity check without binning artifacts. Implement in generate_site.py as an extension of the existing Q5 notification analysis block.

**What the result unlocks:** Confirmed: adds a second actionable lever for push copy editors beyond formula choice. Current guidance (“use attribution language”) would be extended with a specific character-count target.  Not confirmed: formula dominates; length doesn’t independently move CTR and editors can focus solely on formula selection for notifications.

### [Medium · Untested] Apple News — “What to Know” — Featured vs. Organic Stability by Year

**Signal:** Apple editors select “What to Know” at 1.8× the baseline rate for Featured placement. Organic (non-Featured) articles using WTK show no significant view lift (p<sub>adj</sub>=0.10). This editorial/algorithmic split is a key project finding — but whether it is stable across 2025 and 2026 separately is unknown.

**Gap:** The current analysis pools 2025 and 2026 Apple News data. If Apple has updated curation signals, or if T1 editors have changed how they use WTK, the featuring lift or organic penalty could be shifting — which would change whether the two-headline strategy is durable guidance.

**Question:** Is the WTK featuring lift consistent when 2025 and 2026 are analyzed separately? Has the gap between editorial selection rate and organic algorithmic performance been stable, or is it narrowing/widening over time?

**How to run it:** Run on existing Apple News data — no new collection needed. Split the Apple News dataset by year (2025 and 2026 separately). For each year, run: (1) Q2 chi-square or Fisher’s exact test for WTK featuring rate vs. all other formulas; (2) Q1 Mann-Whitney U for WTK organic view rank vs. untagged baseline (non-Featured articles only). Compare the featuring lift ratio (WTK featured rate / baseline featured rate) and the organic p-value across years. A narrowing featured rate ratio or a trending organic p-value signals platform behavior change. Implement as a year-stratified extension of the existing Q1 and Q2 analysis blocks in generate_site.py. Report: a 2×2 table of year×metric (featuring lift and organic p) alongside a directional trend flag. Note: Apple News 2026 covers Jan–Mar only; interpret with caution until Q3 2026 data is available.

**What the result unlocks:** Stable across years: confirms structural platform behavior. The “WTK for Featured campaigns, avoid for organic” rule is durable.  Shifting: guidance needs to evolve. If organic performance is catching up to editorial selection, the two-headline distinction may already be outdated.

### [Medium · Untested] Apple News — Possessive Named Entity — Topic Concentration

**Signal:** Possessive named entity headlines (n=95) show moderate overall performance on Apple News. The signal may be concentrated in sports and crime — topics where named individuals are central to the story — but aggregate analysis cannot confirm this.

**Gap:** Overall n=95 is small enough that splitting by topic reduces per-cell counts below the 30-article threshold for reliable inference. The aggregate analysis masks any strong within-topic signal.

**Question:** Do possessive named entity headlines specifically outperform in sports and crime topics on Apple News, where named individuals are central? Is the aggregate signal driven by a strong within-topic effect, or is it distributed broadly across all topics?

**How to run it:** Run on existing Apple News 2025+2026 data. Filter to possessive named entity headlines. Split by topic: sports+crime (the ‘high named-entity’ group) vs. all other topics. Run Mann-Whitney U (sports+crime PNE articles vs. untagged baseline within the same topics), rank-biserial r as effect size. Repeat for the ‘other topics’ group. Compare lift magnitudes: if the sports+crime lift is substantially larger (r ≥0.1 higher) than the other-topics lift, the signal is topic-concentrated. If lifts are similar, the rule applies broadly. If either per-topic cell has n < 20, flag as preliminary and hold until data grows. Do not split into individual topics at this sample size — aggregate sports+crime as one group. Implement as a topic-stratified extension of the Q1 analysis in generate_site.py.

**What the result unlocks:** Confirmed topic-specific: changes guidance from a broad rule to a targeted one (“use possessive named entity for sports/crime stories specifically”). Editors know exactly when to apply it.  Evenly distributed: the broad rule stands. Possessive named entity is generally useful, not vertically restricted.

### [Medium · Untested] SmartNews — Number Lead Type — Which Numbers Drive the SmartNews Signal?

**Signal:** Number leads show a positive directional trend on SmartNews (median rank 0.534 vs. 0.497 baseline; direction: above_dir). They are the only SmartNews formula with a positive directional signal. Whether count/list (‘3 ways’), dollar amounts (‘$2 billion’), or percentages (‘47%’) drive this has not been tested.

**Gap:** Number-type classification (classify_number_lead()) is implemented in the pipeline but per-type SmartNews performance has not been computed. SmartNews 2026 data is domain-aggregated (not article-level), limiting this analysis to the 2025 dataset (n=38,251 articles).

**Question:** Which number-lead subtype drives the SmartNews directional signal: count/list, dollar amounts, or percentages? Or is the effect evenly distributed across number types, suggesting format (any number in the lead) matters more than type?

**How to run it:** Run on SmartNews 2025 number-lead articles (n ≈342 total). classify_number_lead() already extracts ntype (‘count_list,’ ‘dollar_amount,’ ‘percentage,’ ‘other’). Group by ntype and run Mann-Whitney U for each group vs. the untagged baseline, BH-FDR corrected across the three tested types. Expected n per type: count_list is likely the largest (list articles are common); dollar_amount and percentage groups may be small. Flag any group with n < 20 as preliminary. If all subtypes have low n, aggregate and report directionally only: “counts/lists trend higher (n=X, p=Y)” without a significance claim. Implement by extending the existing number-lead deep-dive block (classify_number_lead() section) in generate_site.py to add a per-type Mann-Whitney analysis. Note: SmartNews 2026 is domain-aggregated and cannot contribute to this analysis — 2025 data only.

**What the result unlocks:** Confirmed specific type: editors can be told “count/list numbers work on SmartNews; dollar amounts and percentages are neutral.” More precise than the current directional number-lead guidance.  Equally distributed: the rule is format-driven (“any number in the lead is better than none”). Simpler and more broadly applicable.

---
