"""Tests that every comparison to a scripted reference names which reference it uses.

There are two scripted references: the pool-scope reference, which explores only viable candidates and is
never rejected, and the fair reference, which pays for rejections as the agents do. Every table that compares
to a scripted reference names its scope, and the bracket line reports both or says why it cannot.
"""
import json, os, re, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import analyse_grid as A  # noqa: E402

SRC = open(os.path.join(ROOT, "scripts", "analyse_grid.py")).read()


class ReferenceIsNamed(unittest.TestCase):

    def test_both_table_headers_name_the_scope(self):
        heads = re.findall(r'"(TABLE [13]\..*?)"', SRC)
        self.assertEqual(len(heads), 2, "expected the two tables that compare to a reference")
        for h in heads:
            nxt = SRC.split('"%s"' % h, 1)[1][:400]
            self.assertIn("Pool-scope scripted", nxt,
                          "the header after %r must say which reference the vs-k* column uses" % h[:28])
            self.assertIn("reference_bracket()", nxt,
                          "the header after %r must also print the bracket" % h[:28])

    def test_the_bracket_reports_both_scopes_with_their_rejection_costs(self):
        line = A.reference_bracket()
        self.assertIn("fair", line)
        self.assertIn("pool-scope", line)
        self.assertIn("rejections", line,
                      "the rejection count is what shows the fair reference plays the agents' game")
        d = json.load(open(os.path.join(ROOT, "results", A.FAIR_CURVE)))
        for scope in ("fair", "pool"):
            self.assertIn("%.2f" % d["curves"][scope]["1"]["distinct"], line,
                          "%s distinct variants at k=1 must appear verbatim" % scope)

    def test_a_missing_fair_curve_says_so_and_does_not_invent_a_number(self):
        real = A.FAIR_CURVE
        try:
            A.FAIR_CURVE = "no_such_curve_%d.json" % os.getpid()
            line = A.reference_bracket()
        finally:
            A.FAIR_CURVE = real
        self.assertIn("unavailable", line)
        self.assertNotIn("fair (", line)
        self.assertFalse(re.search(r"\d+\.\d\d", line),
                         "an absent reference must not be reported as a number")

    def test_the_dropped_claim_is_recorded_as_dropped(self):
        """The pre-registration records the below-k=0 claim as dropped, with both sides' rejections per campaign."""
        pre = open(os.path.join(ROOT, "spec", "GRID_PREREGISTRATION.md")).read()
        tail = pre.split("## 0ai.")[1]
        self.assertIn("DROPPED", tail,
                      "0ai must record that the below-k=0 claim was dropped")
        self.assertIn("16.75", tail, "0ai must record the agents' measured rejections per campaign")
        self.assertIn("97.6", tail, "0ai must record the fair reference's rejections per campaign")


if __name__ == "__main__":
    unittest.main()
