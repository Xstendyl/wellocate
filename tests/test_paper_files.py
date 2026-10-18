#!/usr/bin/env python3
"""Tests that the paper's file lists are read from main.tex and that a .tex file main.tex does not reach is an error.

On the real paper every file sits in exactly one part with no orphans. A scratch paper checks nested inputs
in reading order, an ignored commented-out input, a found orphan and a refused missing input. The verifier
must open no section file by name.
"""
import os, re, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import paper_files as PF                                          # noqa: E402


class ThePaperIsReadFromMainTex(unittest.TestCase):

    def test_real_paper(self):
        parts = PF.parts()
        every = [f for files in parts.values() for f in files]
        self.assertEqual(len(every), len(set(every)), "a file sits in two parts")
        self.assertEqual(parts["preamble"], ["sections/numbers.tex"])
        self.assertIn("sections/results.tex", parts["main"])
        for f in ("sections/appendix_b11.tex", "sections/table_b11.tex", "sections/table_models.tex"):
            self.assertIn(f, parts["appendix"])
        self.assertEqual(PF.orphans(), [])

    def test_scratch_paper(self):
        real = PF.PAPER
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "sections"))
            files = {"main.tex": "\\input{sections/numbers}\n\\begin{document}\n\\input{sections/a}\n"
                                 "% \\input{sections/old}\n\\appendix\n\\input{sections/b}\n\\end{document}\n",
                     "sections/numbers.tex": "", "sections/a.tex": "A\n",
                     "sections/b.tex": "B1 \\input{sections/t} B2 50\\% done\n", "sections/t.tex": "T\n",
                     "sections/old.tex": "cut\n"}
            for rel, body in files.items():
                with open(os.path.join(tmp, rel), "w") as f:
                    f.write(body)
            try:
                PF.PAPER = tmp
                self.assertEqual(PF.parts(), {"preamble": ["sections/numbers.tex"], "main": ["sections/a.tex"],
                                              "appendix": ["sections/b.tex", "sections/t.tex"]})
                self.assertEqual(PF.orphans(), ["sections/old.tex"])
                self.assertIn("T", PF.text("appendix"))
                os.remove(os.path.join(tmp, "sections", "t.tex"))
                with self.assertRaises(SystemExit):
                    PF.parts()
            finally:
                PF.PAPER = real

    def test_verifier_opens_no_section_by_name(self):
        src = open(os.path.join(ROOT, "scripts", "verify_paper_numbers.py")).read()
        self.assertIsNone(re.search(r"[\"'](appendix|results|benchmark|environment|introduction)[\w]*\.tex[\"']", src))


if __name__ == "__main__":
    unittest.main()
