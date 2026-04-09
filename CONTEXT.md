# T1 Headline Analysis — Working Context

**Phase:** Phase 2 active — findings live, playbook, author-playbooks, experiments, daily Headline Grader, weekly auto-ingest
**Status:** Active
**Last session:** 2026-04-09 — Grader hardening + weekly auto-ingest pipeline built

For stable reference facts: see [REFERENCE.md](REFERENCE.md)
For session history: see [sessions/](sessions/)

---

## Current State

- **Site:** `docs/index.html` — 13 findings, interactive tiles, dark/light mode, sortable tables, PNG/PDF export
- **Playbook:** `docs/playbook/index.html` — 5 tiles (Featured Targeting, Push Notifications, Section Tagging, Local vs. National, MSN Formula)
- **Author Playbooks:** `docs/author-playbooks/index.html` — per-author profiles (requires Tracker)
- **Experiments:** `docs/experiments/index.html` — auto-generated each run; directional findings routed here; append-only log at `experiments/experiment_log.md`
- **Headline Grader:** `docs/grader/index.html` — 15 criteria (rule-based + Groq LLM); 30-day history; daily at 10am CDT via GitHub Actions; Run Now button (passcode 8812, fine-grained PAT in localStorage); service account key as base64 in `GOOGLE_SERVICE_ACCOUNT_JSON` secret (use `~/.credentials/pierce-tools.json`)
- **Weekly ingest:** `.github/workflows/weekly_ingest.yml` — Monday 8pm CDT; downloads 2026 sheet via `download_tarrow.py`, regenerates site if data changed, appends to `data/weekly_snapshots.json` via `update_snapshots.py`; **pending: Tarrow must share sheet with `pierce-tools-service-account@pierce-tools.iam.gserviceaccount.com`** (message sent 2026-04-09)
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
| 2026 XLSX | 🔄 Auto-refreshed | Weekly via GitHub Actions — active once Tarrow shares sheet |

## Open Items

**Data:**
- [ ] ANP March drop — drop into `anp_data/` when it arrives from Tarrow's Drive folder
- [ ] Yahoo/AOL split — confirm with Tarrow whether AOL tab will appear in future exports
- [ ] Active time outliers in source Excel (3 rows up to 23,496s); pipeline caps at 600s; notify Tarrow
- [ ] Wire Tracker→ANP join into pipeline; blocked on March ANP drop for Allison Palmer data
- [ ] Lauren Jarvis-Gibson + Samantha Agate — 0 matched articles; author playbooks populate when content appears

**Analysis:**
- [ ] O&O + syndication PV data layer (Chris Palo; Amplitude access needed)
- [ ] Automate Sarah Price's Amplitude → Tracker join (manual monthly export; matching on title/URL/author)
- [ ] SN channel × formula — does formula vary by channel? (MED probing queue; enabled by April 8 article-level SN data)
- [ ] Trendhunter notification vertical breakdown — blocked until Tarrow adds author attribution to notification export
- [ ] `data/weekly_snapshots.json` — longitudinal store built; not yet surfaced on the site (future session)

**Stakeholder:**
- [ ] Share formula × topic interaction finding → editorial leads (weather/emergency = "here's/question"; all other topics = formula doesn't matter)
- [ ] Share SmartNews formula trap (question/WTK hurt SN) → distribution team
- [ ] Sara Vallone + Sarah Price: criteria refinement feedback for grader; individual per-author breakdown in grader (committed at C&P Weekly)
- [ ] Sarah Price: review tiles 1–13, flag usefulness (no rush; feeds report tuning)

## Recent Session: 2026-04-09

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
