#!/bin/bash
# run_grader.sh — Daily headline grader automation
# Called by cron at 8am America/New_York. Grades headlines, commits, pushes.
# Logs to /tmp/grader.log (rotated automatically, last 500 lines kept).

set -euo pipefail

REPO="/Users/pierce/Documents/github/data-t1headlines"
LOG="/tmp/grader.log"

echo "=== Grader run: $(date) ===" >> "$LOG"

# Load env vars (GROQ_API_KEY, GITHUB_TOKEN, GOOGLE_SERVICE_ACCOUNT_FILE)
source ~/.grader_env

cd "$REPO"

# Find python3 (Homebrew or system)
PYTHON=$(command -v python3 || echo "/usr/bin/python3")

# Run grader
"$PYTHON" generate_grader.py >> "$LOG" 2>&1

# Stage only the grader output (don't auto-commit other changes)
git add docs/grader/index.html docs/grader/history.json

# Commit only if there's something new
if git diff --cached --quiet; then
  echo "Nothing to commit (no change from prior run)" >> "$LOG"
else
  git commit -m "Auto: Headline Grader $(date '+%Y-%m-%d %H:%M %Z')" >> "$LOG" 2>&1
  git push "https://${GITHUB_TOKEN}@github.com/piercewilliams/data-t1headlines.git" main >> "$LOG" 2>&1
  echo "Pushed successfully" >> "$LOG"
fi

# Keep log to last 500 lines
tail -500 "$LOG" > "${LOG}.tmp" && mv "${LOG}.tmp" "$LOG"

echo "=== Done: $(date) ===" >> "$LOG"
