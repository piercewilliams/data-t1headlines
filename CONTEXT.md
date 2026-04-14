# T1 Headline Analysis — Working Context

**Phase:** Phase 2 active — findings live, playbook, author-playbooks, experiments, daily Headline Grader, weekly auto-ingest
**Status:** Active
**Last session:** 2026-04-14 — SN channel × formula analyzed (2025 data, 38k rows); callout added to formula trap panel; longitudinal AN featuring rates replace hardcoded SN constants in build_summary.json; Hanna Wickes author normalization added; weekly snapshots surfaced on main page

For stable reference facts: see [REFERENCE.md](REFERENCE.md)
For session history: see [sessions/](sessions/)

---

## Current State

- **Site:** `docs/index.html` — 13 findings, interactive tiles, dark/light mode, sortable tables, PNG/PDF export
- **Playbook:** `docs/playbook/index.html` — 5 tiles (Featured Targeting, Push Notifications, Section Tagging, Local vs. National, MSN Formula)
- **Author Playbooks:** `docs/author-playbooks/index.html` — per-author profiles (requires Tracker)
- **Experiments:** `docs/experiments/index.html` — auto-generated each run; directional findings routed here; append-only log at `experiments/experiment_log.md`
- **Headline Grader:** `docs/grader/index.html` — 15 criteria (rule-based + Groq LLM); 30-day history; daily at 10am CDT via GitHub Actions; Run Now button (passcode 8812, fine-grained PAT in localStorage); service account key as base64 in `GOOGLE_SERVICE_ACCOUNT_JSON` secret (use `~/.credentials/pierce-tools.json`); **platform-aware scoring** — reads `Syndication platform` (col H) from Tracker; char count scored against platform-specific target (AN: 90–120, SN: 70–90); number lead note is platform-aware; platform badge shown on each card
- **Weekly ingest:** `.github/workflows/weekly_ingest.yml` — Monday 8pm CDT; downloads 2026 sheet via `download_tarrow.py`, regenerates site if data changed, appends to `data/weekly_snapshots.json` via `update_snapshots.py`; sheet shared with service account ✅ (confirmed 2026-04-09)
- **Generator:** `generate_site.py` — run via `ingest.py`; `SHOW_MSN_TILE = False` (MSN data present, tile paused); `PENDING_HIGH_ANALYSES = []` (build-time scope guardrail); writes `data/build_summary.json` at end of every run for longitudinal tracking

## Data Status (as of 2026-04-08)

| Source | Status | Notes |
|--------|--------|-------|
| Apple News 2025 | ✅ In repo | Full year, 3,039 rows |
| Apple News 2026 | ✅ In repo | Jan–Mar, 4,283 rows (engagement columns populated) |
| Apple News Notifications 2025 | ✅ In repo | 1,443 rows |
| Apple News Notifications 2026 | ✅ In repo | 1,923 rows |
| SmartNews 2025 | ✅ In repo | Full year, 38,251 rows |
| SmartNews 2026 | ✅ In repo | Article-level, 28 columns, per-channel views |
| MSN 2026 | ✅ In repo | 113 rows after T1 + politics filter |
| Yahoo 2026 | ✅ In repo | 1,043 rows |
| 2026 XLSX | 🔄 Auto-refreshed | Weekly via GitHub Actions — Tarrow share confirmed ✅ |

## Open Items

**Data:**
- [ ] ANP March drop — drop into `anp_data/` when it arrives from Tarrow's Drive folder
- [ ] Yahoo/AOL split — confirm with Tarrow whether AOL tab will appear in future exports
- [ ] Active time outliers in source Excel (3 rows up to 23,496s); pipeline caps at 600s; notify Tarrow
- [ ] Wire Tracker→ANP join into pipeline; blocked on March ANP drop for Allison Palmer data
- [ ] Lauren Jarvis-Gibson + Samantha Agate — 0 matched articles; author playbooks populate when content appears
- [x] ~~"Hanna Wickes" / "Hanna WIckes" typo splits author rows~~ FIXED 2026-04-14: name normalization added to generate_site.py (`_AUTHOR_ALIASES`) — merges both spellings into "Hanna Wickes" before any tracker processing. Source spreadsheet still has the typo but pipeline handles it.

**Analysis:**
- [ ] O&O + syndication PV data layer (Chris Palo; Amplitude access needed)
- [ ] Automate Sarah Price's Amplitude → Tracker join (manual monthly export; matching on title/URL/author)
- [x] ~~SN channel × formula~~ DONE 2026-04-14: analyzed on 2025 full-year data (38,251 rows). Question underperforms in Top, Entertainment, Lifestyle (p<0.0001, p=0.012, p=0.027). WTK underperforms in Top (p=0.008). Number lead has large U.S.-channel penalty (Δ=−0.245, p<0.0001, n=83). Callout added to formula trap panel; experiment suggestion added for 2026 per-article replication. Message to Tarrow about 2025 data attribution pending.
- [ ] Trendhunter notification vertical breakdown — blocked until Tarrow adds author attribution to notification export
- [x] ~~`data/weekly_snapshots.json` — longitudinal store built; not yet surfaced on the site~~ DONE 2026-04-14: section now renders on main page (docs/index.html) and experiments page. Placeholder shows until ≥3 snapshots; trend table auto-renders after 2 more weekly runs.

**Stakeholder:**
- [ ] Share formula × topic interaction finding → editorial leads (weather/emergency = "here's/question"; all other topics = formula doesn't matter)
- [ ] Share SmartNews formula trap (question/WTK hurt SN) → distribution team
- [ ] Sara Vallone + Sarah Price: criteria refinement feedback for grader; individual per-author breakdown in grader (committed at C&P Weekly)
- [ ] Sarah Price: review tiles 1–13, flag usefulness (no rush; feeds report tuning)

**Architecture — adapter pattern (Chris Palo directive, 2026-04-09):**
- [ ] Split `GOVERNOR.md` → `GOVERNOR_CORE.md` (Part 2 rigor, universal) + `GOVERNOR_SARAH.md` (Part 1 relevance, Sarah-specific)
- [ ] Create `ADAPTER_TEMPLATE.md` — 6-section starter file each team member copies and fills in (use case, stakeholder focus, scope filters, probing queue, what "interesting" means, output preferences)
- [ ] Update `CLAUDE.md` — adapter loading logic: if `ADAPTER.md` present, load `GOVERNOR_CORE.md` + `ADAPTER.md`; else load `GOVERNOR.md` as-is
- [ ] Create `README_ADAPTER.md` — explains the pattern, documents three output modes (interactive session / narrative memo / site tile), uses Sarah's adapter as the worked example
- Goal: each team member clones repo, copies template → `ADAPTER.md`, fills it in; rigor floor is inviolable regardless of adapter

## Recent Session: 2026-04-10

**Cluster/variant production section:** `_cluster_production_section()` added to `generate_site.py` and wired into author-playbooks page after the performance-join variant section. Shows: total clusters (422), share with ≥2 articles (94%), mean/median/max cluster size, distribution table (1–4 bins + 5+), author breakdown by cluster count and mean variants/cluster. Runs on `tracker_raw` directly — no performance join required.

**cluster_id propagation** (carried from prior session): `_cluster_id` computed from `tracker_raw` alongside `_cluster_size`, propagated through `_t_cols` → `_t_extra_cols` → all three platform join `rows.append` dicts.

**Actionable findings assessment:** None. Production section is operational inventory (Ryan Brennan 154 clusters/3.15 mean, Hanna Wickes 144/3.15; Lauren Schuster 47/2.21, Lauren J-G 40/2.0, Allison Palmer 19/1.95). Performance join: Mann-Whitney p=0.635, no detectable difference between originals and variants (n=37 total — underpowered). **Data quality flag:** "Hanna Wickes" and "Hanna WIckes" (capital I) appear as separate authors in Tracker — 148 clusters split across two rows. Worth fixing in source data.

**Three new `_COL_TOOLTIPS` entries added** for cluster section column headers. 19/19 tests pass, all build checks clean.

## Recent Session: 2026-04-09 (session 2)

**Grader platform-aware scoring:** `generate_grader.py` updated to read `Syndication platform` (Tracker col H) per article. `_parse_platform()` added; `_char_count()` now scores against platform-specific target (AN: 90–120, SN: 70–90, unknown: 70–120 fallback); `_number()` note is platform-aware ("positive SmartNews signal" / "caution: underperforms on Apple News"). Platform badge shown on each headline card. 19/19 tests pass. Also confirmed: `Primary Keywords` (col H→R) and `Headline` (col I) were already being read correctly — no gap there.

**Adapter pattern planned (Chris Palo directive):** Full architecture documented in CONTEXT.md open items and memory. Four files to build off-hours: `GOVERNOR_CORE.md`, `GOVERNOR_SARAH.md`, `ADAPTER_TEMPLATE.md`, `README_ADAPTER.md`. CLAUDE.md adapter-loading logic defined. No code changes needed.

**Stakeholder documentation produced:** Three "one-sheet dummies guides" written for Chris Palo — how each artifact works, how to build one, what the guardrails are, how outputs are prioritized by stakeholder interest. Analytics pipeline doc includes full Governor explanation (Part 1 relevance / Part 2 rigor / continuous improvement loop).

## Recent Session: 2026-04-09 (session 1)

**Grader hardening:** CRITERIA updated — char count label corrected to SN 70–90 / AN 90–120 range; `no_questions` added as scored criterion; `no_vague_wtk` moved from LLM → regex (p=3.0e-6 badge); `_ACRONYMS` expanded ~30→55; LLM prompt reduced to 4 criteria. Stale LLM warning text corrected. 19/19 tests pass.

**Headline standards cross-repo audit:** WTK p-value resolved (more recent run p=3.0e-6 takes precedence, survives Bonferroni). Featured placement exception removed from all three csa-content-standards locations — no data support.

**Weekly auto-ingest pipeline built and pushed:**
- `download_tarrow.py` — Drive API download of 2026 sheet; reuses existing service account
- `.github/workflows/weekly_ingest.yml` — Monday 8pm CDT; change-detection skips regeneration if data unchanged; commits xlsx + docs/ + data/ when changed
- `generate_site.py` — writes `data/build_summary.json` with 8 tracked metrics at end of each run
- `update_snapshots.py` — appends build_summary to `data/weekly_snapshots.json` (longitudinal store)

**Integrity pass:** xlsx-not-committed bug fixed (change-detection would re-fire every week); `google-auth-httplib2` removed (unused); `requests` added to requirements.txt; README and REFERENCE.md updated; smoke tests extended to 19.

---

*This file follows the Tiered Context Architecture. Budget: ≤150 lines.*
*Current: ~90 lines*
