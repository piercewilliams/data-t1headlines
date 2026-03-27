# Experiments

Each file in this directory is one experiment spec. Run:

```bash
python3 generate_experiment.py experiments/SLUG.md       # one experiment
python3 generate_experiment.py experiments/              # all experiments
```

Output goes to `docs/experiments/SLUG/index.html`. Linked from the main site footer.

---

## Spec format

```markdown
---
id: your-slug-here
title: "Human-readable experiment title"
experiment_type: temporal_cohort   # or: formula_comparison
platform: apple_news               # apple_news | smartnews | notifications
metric: views                      # views | featured_rate | active_time | ctr | smartnews_views

# For temporal_cohort — required:
before_start: 2025-01-01
before_end:   2025-06-30
after_start:  2025-07-01
after_end:    2025-12-31

# For formula_comparison — required:
formula_a: what_to_know
formula_b: untagged       # baseline to compare against

# Optional filters (both types):
filter_formula: what_to_know    # restrict to only this formula type (temporal_cohort)
filter_topic: crime             # restrict to a topic
filter_featured: "no"           # "yes" | "no" | null (all)

# Optional date window for formula_comparison:
date_start: 2025-01-01
date_end:   2025-12-31

hypothesis: "What we expect to see"
status: pending    # pending | active | complete
result: null       # fill in after running
---

Context paragraph explaining what changed and why we're testing this.
```

## Supported values

**platforms:** `apple_news`, `smartnews`, `notifications`

**metrics:**
| metric | platform | test | measures |
|--------|----------|------|---------|
| `views` | apple_news | Mann-Whitney | Total Views (median) |
| `featured_rate` | apple_news | Chi-square | Featured by Apple (rate) |
| `active_time` | apple_news | Mann-Whitney | Avg. Active Time in seconds |
| `ctr` | notifications | Mann-Whitney | Click-through rate (median) |
| `smartnews_views` | smartnews | Mann-Whitney | article_view (median) |

**formula values:** `what_to_know`, `heres_formula`, `possessive_named_entity`, `number_lead`, `question`, `quoted_lede`, `untagged`

**topic values:** `crime`, `sports`, `weather`, `business`, `local_civic`, `lifestyle`, `nature_wildlife`, `other`

## When to use each type

**Convention: formula_a = control/baseline, formula_b = treatment.** Lift is calculated as B÷A, so lift>1 means the treatment outperformed the baseline.

**`temporal_cohort`** — you made a change (editorial guidance, CSA prompt, distribution strategy) and want to measure whether performance shifted before vs. after. `before` = A (control), `after` = B (treatment). Requires enough data in both periods (aim for n≥50 each).

**`formula_comparison`** — you want to know if one headline formula outperforms another, without tying it to a specific intervention date. `formula_a` = baseline (usually `untagged`), `formula_b` = formula being tested. Uses all available data (or a date-filtered window).

**`variant_ab`** (coming when canon article IDs are available) — same article, different headlines, true A/B. Not yet buildable; needs CSA Cluster ID instrumentation.
