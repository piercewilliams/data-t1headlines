"""Smoke tests for generate_site.py helper functions.

Run with:  python3 -m pytest tests/ -v
Or:        python3 tests/smoke_test.py

These tests cover functions that can be exercised without running the full
pipeline (no Excel files required).  They are NOT integration tests — they
don't validate that the generated HTML is correct, only that core utility
functions behave as specified.

Three categories:
  1. AST-parse checks — catch syntax regressions without importing the module
     (importing generate_site.py executes the full pipeline at import time).
  2. _validate_exp_suggestion() — dict validation logic.
  3. _append_experiment_log() — append-only log writer, exercised with a temp file.
"""

import ast
import sys
import tempfile
import unittest
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATE_SITE = REPO_ROOT / "generate_site.py"
INGEST_PY     = REPO_ROOT / "ingest.py"


# ── 1. AST-parse smoke tests ──────────────────────────────────────────────────

class TestAstParse(unittest.TestCase):
    """Verify that generate_site.py and ingest.py are syntactically valid Python.

    We cannot import these modules directly because importing generate_site.py
    executes the full analysis pipeline (it has no if __name__ == '__main__' guard).
    AST parsing catches SyntaxErrors and encoding issues without running any code.
    """

    def _assert_parses(self, path: Path) -> None:
        self.assertTrue(path.exists(), f"{path} not found")
        source = path.read_text(encoding="utf-8")
        try:
            ast.parse(source)
        except SyntaxError as exc:
            self.fail(f"SyntaxError in {path.name}: {exc}")

    def test_generate_site_parses(self):
        self._assert_parses(GENERATE_SITE)

    def test_ingest_parses(self):
        self._assert_parses(INGEST_PY)


# ── Helpers extracted for unit-testing without importing the pipeline ──────────
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
