"""Tests that the findings table (results/findings.json) still matches its sources.

scripts/findings.py --check rebuilds every row from the analysis files and the paper's verifier, and fails if
a headline number, an n per cell or a paper status has moved, or if an analysis file or campaign tag belongs
to no row.
"""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


class Findings(unittest.TestCase):

    def test_the_table_matches_its_sources(self):
        import findings
        self.assertEqual(findings.check(), [])


if __name__ == "__main__":
    unittest.main()


class PaperCandidates(unittest.TestCase):

    def test_the_candidates_file_is_what_findings_json_generates(self):
        import paper_candidates
        path = paper_candidates.OUT
        self.assertEqual(open(path).read(), paper_candidates.build())

