"""Tests that a generator writes into paper/ only with --write-paper; any other invocation leaves paper/ byte-identical.

Each generator runs as a subprocess with --help, with no flag, with an unknown flag and with --out inside
paper/, and paper/ must be unchanged afterwards; the last two must fail. --write-paper and --out are checked
in process on a redirected target, so the test never touches the real paper/.
"""
import hashlib, importlib, io, os, subprocess, sys, tempfile, unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
GENERATORS = ("make_paper_numbers", "make_table_basins", "make_table_cells", "make_table_fixes", "make_table_models",
              "make_table_prompt", "make_table_splits", "make_table_landscapes", "make_table_b11", "make_bib")


def paper_state():
    out = {}
    for d, _s, files in os.walk(os.path.join(ROOT, "paper")):
        for f in files:
            p = os.path.join(d, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, ROOT)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def run(gen, *args):
    return subprocess.run([sys.executable, "-B", os.path.join(ROOT, "scripts", gen + ".py")] + list(args),
                          cwd=ROOT, capture_output=True, text=True, timeout=600)


class AGeneratorWritesPaperOnlyWhenTold(unittest.TestCase):

    def test_no_invocation_but_write_paper_touches_paper(self):
        before = paper_state()
        for gen in GENERATORS:
            for args, must_fail in ((["--help"], False), ([], False), (["--bogus"], True),
                                    (["--out", os.path.join("paper", "sections", "x.tex")], True)):
                r = run(gen, *args)
                self.assertEqual(r.returncode != 0, must_fail, "%s %s: exit %d\n%s" % (gen, args, r.returncode,
                                                                                         r.stderr[-800:]))
        self.assertEqual(paper_state(), before, "a generator changed paper/ without --write-paper")

    def test_list_prints_macro_names_and_writes_nothing(self):
        before = paper_state()
        r = run("make_paper_numbers", "--list")
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        self.assertIn("\\nShareOpus", r.stdout)
        self.assertEqual(paper_state(), before)

    def test_write_paper_and_out_write_where_told(self):
        for gen in ("make_paper_numbers", "make_table_models"):
            m = importlib.import_module(gen)
            real = m.DST
            with tempfile.TemporaryDirectory() as tmp:
                try:
                    m.DST = os.path.join(tmp, "target.tex")
                    with redirect_stdout(io.StringIO()):
                        self.assertEqual(m.main(["--write-paper"]), 0)
                        self.assertEqual(open(m.DST).read(), m.render())
                        other = os.path.join(tmp, "elsewhere.tex")
                        self.assertEqual(m.main(["--out", other]), 0)
                        self.assertEqual(open(other).read(), m.render())
                finally:
                    m.DST = real


if __name__ == "__main__":
    unittest.main()
