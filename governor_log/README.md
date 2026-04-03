# Governor Log

Chronological session-by-session record. Append only — never rewrite.

Each file covers one calendar month. Within a file, entries are dated and timestamped.

## Entry format

```
### YYYY-MM-DD — [session type: ingest / ad-hoc analysis / stakeholder meeting / tile feedback]

**Data / context:** [what data was in play, or what meeting/interaction this captures]

**Signals observed:**
- [finding or interaction] → [what it implies for the governor]

**Governor updates proposed:**
- [ ] [update to propose] → [which section of GOVERNOR.md]

**Applied:** [yes / no — did the user approve and apply the proposed updates?]
```

## Tile feedback entry format (for Sarah's reviews)

```
### YYYY-MM-DD — tile feedback from Sarah Price

| Tile | Rating | Sarah's comment | Governor implication |
|------|--------|-----------------|---------------------|
| Finding N: [title] | useful / partial / skip | [verbatim or close paraphrase] | [update to Confirmed Interesting or Low-Signal] |
```
