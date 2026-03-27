---
id: possessive-formula-views
title: Possessive named entity formula — does it drive more Apple News views than baseline?
experiment_type: formula_comparison
platform: apple_news
metric: views
formula_a: untagged
formula_b: possessive_named_entity
filter_featured: "no"
hypothesis: "Non-Featured articles with possessive named entity framing (e.g. 'Savannah Guthrie's husband') have higher median views than untagged baseline headlines"
status: active
result: null
---

The main site reports 1.94× lift for possessive named entity (n=75, not yet significant).
This runs the formal significance test with the current dataset and documents the result.

When the Apple News dataset grows month-over-month, re-run this experiment to track
whether significance is reached at n≥100. The formula classifier matches headlines that
contain a full named person (two capitalized words) plus a possessive construction.
