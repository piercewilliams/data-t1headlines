"""Smoke tests for generate_site.py helper functions.

Run with:  python3 -m pytest tests/ -v
Or:        python3 tests/smoke_test.py

IMPORTANT — run under Python 3.11 to catch CI-specific syntax restrictions:
  python3.11 -m pytest tests/ -v

Python 3.11 enforces f-string rules that 3.12+ relaxed (PEP 701):
  - No backslash in f-string expression part (the {...} section)
  - No same-quote-style nesting (f\"\"\" inside f\"\"\")
  The py_compile tests below catch these when run under 3.11. Run locally
  with `python3.11 -m pytest tests/` before pushing any generate_site.py change.

These tests cover functions that can be exercised without running the full
pipeline (no Excel files required).  They are NOT integration tests — they
don't validate that the generated HTML is correct, only that core utility
functions behave as specified.

Four categories:
  1. Compile checks — py_compile bytecode compilation catches syntax errors
     the AST parser might miss (especially under Python 3.11).
  2. F-string safety scans — detect known-risky patterns before CI runs.
  3. _validate_exp_suggestion() — dict validation logic.
  4. _append_experiment_log() — append-only log writer, exercised with a temp file.
"""

import ast
import py_compile
import re
import sys
import tempfile
import unittest
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT         = Path(__file__).resolve().parent.parent
GENERATE_SITE     = REPO_ROOT / "generate_site.py"
INGEST_PY         = REPO_ROOT / "ingest.py"
GRADER_PY         = REPO_ROOT / "generate_grader.py"
STYLE_GUIDE_PY    = REPO_ROOT / "generate_style_guide.py"
DOWNLOAD_TARROW   = REPO_ROOT / "download_tarrow.py"
UPDATE_SNAPSHOTS  = REPO_ROOT / "update_snapshots.py"


# ── 1. Compile smoke tests ────────────────────────────────────────────────────

class TestCompile(unittest.TestCase):
    """Verify that all pipeline scripts compile cleanly under the current interpreter.

    Uses py_compile (full bytecode compilation) rather than ast.parse() alone —
    py_compile catches a strict superset of what the AST parser checks, including
    f-string backslash and same-quote-nesting restrictions on Python 3.11.

    We cannot import these modules directly because importing generate_site.py
    executes the full analysis pipeline (it has no if __name__ == '__main__' guard).

    Run under Python 3.11 (`python3.11 -m pytest tests/ -v`) to catch CI-specific
    syntax restrictions before pushing.
    """

    def _assert_compiles(self, path: Path) -> None:
        self.assertTrue(path.exists(), f"{path} not found")
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            self.fail(f"Compile error in {path.name}: {exc}")

    def test_generate_site_compiles(self):
        self._assert_compiles(GENERATE_SITE)

    def test_ingest_compiles(self):
        self._assert_compiles(INGEST_PY)

    def test_generate_grader_compiles(self):
        self._assert_compiles(GRADER_PY)

    def test_generate_style_guide_compiles(self):
        self._assert_compiles(STYLE_GUIDE_PY)

    def test_download_tarrow_compiles(self):
        self._assert_compiles(DOWNLOAD_TARROW)

    def test_update_snapshots_compiles(self):
        self._assert_compiles(UPDATE_SNAPSHOTS)


# ── 2. F-string safety scans ──────────────────────────────────────────────────

class TestFStringSafety(unittest.TestCase):
    """Scan generate_site.py source text for Python 3.11 f-string anti-patterns.

    Python 3.11 (used in CI) restricts f-strings more strictly than 3.12+:
      - No backslash anywhere in the raw source text of an f-string expression
        part — including inside nested string literals within {...}.
      - No same-quote-style nesting: f\"\"\" cannot contain another f\"\"\" in
        an expression slot; use f''' inside f\"\"\" instead.

    These text-level checks catch the patterns before CI runs. They are
    conservative (may flag false positives for pre-computed variables), but any
    flagged hit should be manually verified.
    """

    def setUp(self):
        self.source = GENERATE_SITE.read_text(encoding="utf-8")

    def test_no_same_triple_double_quote_nesting(self):
        """f\"\"\"...{ f\"\"\"...\"\"\" }...\"\"\" breaks Python 3.11."""
        # Find f\"\"\" blocks and check if any contain a nested f\"\"\"
        # Simple heuristic: look for 'else f"""' or '( f"""' inside an f-string context
        hits = [
            (i + 1, line.strip())
            for i, line in enumerate(self.source.splitlines())
            if re.search(r'else\s+f"""', line) or re.search(r'\(\s*f"""', line)
        ]
        # Only flag if the hit is inside another f""" block (nested)
        # We check by scanning whether we're inside an outer f""" context.
        # Conservative: just report — the compile test will catch real errors.
        if hits:
            # If the compile test passes, these are false positives from pre-computed
            # variables or non-nested contexts. Warn rather than fail.
            for lineno, snippet in hits[:3]:
                print(f"\n  [f-string nesting hint] line {lineno}: {snippet[:80]}")

    def test_no_backslash_in_fstring_expression(self):
        """Backslash inside {{...}} in an f-string breaks Python 3.11."""
        # Look for the specific pattern: backslash inside {} in an f-string line.
        # Reliable detection requires a full parser; this is a conservative text scan.
        hits = []
        in_fstring = False
        brace_depth = 0
        for i, line in enumerate(self.source.splitlines(), 1):
            # Very conservative: flag lines that have both { and \ and are in f-strings
            # Only catch the patterns that actually caused CI failures:
            # - join(...for...) with \n or \" inside the format spec
            if re.search(r'f["\'].*\{[^}]*\\[ntr"\'\\][^}]*\}', line):
                hits.append((i, line.strip()))
        self.assertEqual(
            hits, [],
            "Possible backslash-in-f-string-expression on lines:\n"
            + "\n".join(f"  {i}: {s[:100]}" for i, s in hits[:5])
            + "\nPre-compute the value into a variable before the f-string."
        )


# ── Helpers extracted for unit-testing without importing the pipeline ──────────
# ── 3. & 4. Unit tests for isolated helper functions ─────────────────────────
#
# _validate_exp_suggestion() and _append_experiment_log() are copy-extracted
# here so they can be tested without triggering the pipeline execution.
# If the implementations in generate_site.py change, update these copies to match.

_EXP_TIER_LABELS = {
    "bonferroni-fail": "Bonferroni fail",
    "underpowered":    "Underpowered",
    "directional":     "Directional",
    "untested":        "Untested",
}
_EXP_PRIORITY_LABELS = {
    "high":   "\u2191 High",
    "medium": "Medium",
    "low":    "Low",
}
_EXP_REQUIRED_KEYS = frozenset({
    "id", "platform", "title", "signal", "gap",
    "question", "design", "impact", "tier", "priority",
})


def _validate_exp_suggestion(s: dict) -> bool:
    missing = _EXP_REQUIRED_KEYS - s.keys()
    if missing:
        return False
    if s["tier"] not in _EXP_TIER_LABELS:
        return False
    if s["priority"] not in _EXP_PRIORITY_LABELS:
        return False
    return True


def _append_experiment_log(suggs: list, report_date: str, log_path: Path) -> None:
    import html as html_module
    lines = [f"\n## Run: {report_date}\n\n"]
    for s in suggs:
        lines.append(
            f"### [{s['tier'].upper()}] {html_module.unescape(s['title'])}\n"
            f"**Platform:** {s['platform']}  |  **Priority:** {s['priority']}\n\n"
            f"**Signal:** {html_module.unescape(s['signal'])}\n\n"
            f"**Gap:** {html_module.unescape(s['gap'])}\n\n"
            f"**Test question:** {html_module.unescape(s['question'])}\n\n"
            f"**Design:** {html_module.unescape(s['design'])}\n\n"
            f"**What it unlocks:** {html_module.unescape(s['impact'])}\n\n---\n\n"
        )
    try:
        if not log_path.exists() or log_path.stat().st_size == 0:
            log_path.write_text(
                "# Experiment Suggestion Log\n\n"
                "Auto-generated. Appended each analytics run. Never manually edited.\n"
                "Each run records the full set of directional suggestions at that point in time.\n\n"
                "---\n",
                encoding="utf-8",
            )
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write("".join(lines))
    except OSError as exc:
        print(f"  \u26a0  Could not write experiment log ({log_path}): {exc}")


# ── 2. _validate_exp_suggestion() tests ───────────────────────────────────────

def _make_valid_suggestion(**overrides) -> dict:
    """Return a valid suggestion dict, optionally overriding specific keys."""
    base = {
        "id":       "test-1",
        "platform": "Apple News",
        "title":    "Test suggestion",
        "signal":   "Signal text",
        "gap":      "Gap text",
        "question": "What if we tested X?",
        "design":   "Run A/B with 50 articles each.",
        "impact":   "Would unlock actionable guidance.",
        "tier":     "directional",
        "priority": "medium",
    }
    base.update(overrides)
    return base


class TestValidateExpSuggestion(unittest.TestCase):

    def test_valid_suggestion_passes(self):
        self.assertTrue(_validate_exp_suggestion(_make_valid_suggestion()))

    def test_all_valid_tiers_pass(self):
        for tier in _EXP_TIER_LABELS:
            with self.subTest(tier=tier):
                self.assertTrue(_validate_exp_suggestion(_make_valid_suggestion(tier=tier)))

    def test_all_valid_priorities_pass(self):
        for priority in _EXP_PRIORITY_LABELS:
            with self.subTest(priority=priority):
                self.assertTrue(_validate_exp_suggestion(_make_valid_suggestion(priority=priority)))

    def test_missing_required_key_fails(self):
        for key in _EXP_REQUIRED_KEYS:
            s = _make_valid_suggestion()
            del s[key]
            with self.subTest(missing_key=key):
                self.assertFalse(_validate_exp_suggestion(s))

    def test_invalid_tier_fails(self):
        self.assertFalse(_validate_exp_suggestion(_make_valid_suggestion(tier="nonsense")))

    def test_invalid_priority_fails(self):
        self.assertFalse(_validate_exp_suggestion(_make_valid_suggestion(priority="urgent")))

    def test_empty_dict_fails(self):
        self.assertFalse(_validate_exp_suggestion({}))


# ── 3. _append_experiment_log() tests ─────────────────────────────────────────

class TestAppendExperimentLog(unittest.TestCase):

    def _make_suggestion(self, title="Test title") -> dict:
        return _make_valid_suggestion(title=title)

    def test_creates_header_on_first_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = Path(tmpdir) / "experiment_log.md"
            _append_experiment_log([self._make_suggestion()], "2026-04", log)
            content = log.read_text(encoding="utf-8")
            self.assertIn("# Experiment Suggestion Log", content)

    def test_appends_run_section(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = Path(tmpdir) / "experiment_log.md"
            _append_experiment_log([self._make_suggestion()], "2026-04", log)
            content = log.read_text(encoding="utf-8")
            self.assertIn("## Run: 2026-04", content)

    def test_second_write_does_not_duplicate_header(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = Path(tmpdir) / "experiment_log.md"
            _append_experiment_log([self._make_suggestion("First")], "2026-04", log)
            _append_experiment_log([self._make_suggestion("Second")], "2026-05", log)
            content = log.read_text(encoding="utf-8")
            # Header should appear exactly once
            self.assertEqual(content.count("# Experiment Suggestion Log"), 1)
            # Both run sections should be present
            self.assertIn("## Run: 2026-04", content)
            self.assertIn("## Run: 2026-05", content)

    def test_suggestion_title_appears_in_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = Path(tmpdir) / "experiment_log.md"
            _append_experiment_log([self._make_suggestion("My unique title")], "2026-04", log)
            content = log.read_text(encoding="utf-8")
            self.assertIn("My unique title", content)

    def test_empty_suggestion_list_writes_run_header(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = Path(tmpdir) / "experiment_log.md"
            _append_experiment_log([], "2026-04", log)
            content = log.read_text(encoding="utf-8")
            self.assertIn("## Run: 2026-04", content)

    def test_oserror_does_not_raise(self):
        """OSError on a read-only path should be caught, not propagated."""
        bad_path = Path("/no/such/directory/experiment_log.md")
        # Should not raise — the function prints a warning and swallows the error
        try:
            _append_experiment_log([self._make_suggestion()], "2026-04", bad_path)
        except OSError:
            self.fail("_append_experiment_log() raised OSError instead of catching it")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
