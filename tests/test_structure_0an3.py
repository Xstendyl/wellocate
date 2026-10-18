"""Tests for the landscape-structure paragraph: it states measured facts about the grid's landscape and nothing else.

It must reach every prompt kind when the option is on and none when it is off, say nothing about measurement,
noise or re-testing, and grid.py must refuse to start if any of its numbers stops matching the measurement.
"""
import os, re, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from repdef import prompts                                                  # noqa: E402

KW = dict(parent="GDIF", example="ADIF", landscape="abstract", noise_model="multiplicative", cv=0.073,
          noise_floor=0.0035, anchor_reading="6.87")
S = prompts.STRUCTURE_GRID


class Paragraph(unittest.TestCase):

    def test_it_reaches_every_prompt_kind_only_when_on(self):
        for p in (prompts.build("blind", [], 1, 15, 4, 60, 0.0, structure_text=S, **KW),
                  prompts.build("blind", [], 1, 15, 1, 60, 0.0, structure_text=S, **KW),
                  prompts.build_nomination("blind", [], 15, 4, 0.0, structure_text=S, **KW)):
            self.assertIn(S, p)
        self.assertNotIn("STRUCTURE", prompts.build("blind", [], 1, 15, 4, 60, 0.0, **KW))
        self.assertNotIn("STRUCTURE", prompts.build_nomination("blind", [], 15, 4, 0.0, **KW))

    def test_off_leaves_the_blind_prompt_as_it_was(self):
        on = prompts.build("blind", [], 1, 15, 4, 60, 0.0, structure_text=S, **KW)
        off = prompts.build("blind", [], 1, 15, 4, 60, 0.0, **KW)
        self.assertEqual(on.replace(S + "\n", ""), off)

    def test_it_says_nothing_about_measurement_or_re_testing(self):
        words = ("noise", "noisy", "error", "repeat", "again", "reading", "readings", "confirm", "uncertain",
                 "sure", "true", "exact", "exactly", "yardstick")
        stems = ("re-test", "retest", "replicat", "measur")
        for w in words:
            self.assertIsNone(re.search(r"\b%s\b" % re.escape(w), S.lower()), w)
        for w in stems:
            self.assertIsNone(re.search(r"\b%s" % re.escape(w), S.lower()), w)

    def test_grid_refuses_a_number_the_measurement_does_not_give(self):
        import grid
        fit, pool = grid.landscape()
        grid.check_the_structure_paragraph(fit, pool)
        real = prompts.STRUCTURE_GRID
        try:
            prompts.STRUCTURE_GRID = real.replace("26% are viable", "27% are viable")
            with self.assertRaises(SystemExit):
                grid.check_the_structure_paragraph(fit, pool)
        finally:
            prompts.STRUCTURE_GRID = real


if __name__ == "__main__":
    unittest.main()
