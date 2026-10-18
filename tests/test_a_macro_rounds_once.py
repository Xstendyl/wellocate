"""Tests that every paper macro is its raw value rounded once.

Rounding an already rounded value again can move it across a tie. Each macro is resolved to the raw number
behind its findings headline (a path into an analysis JSON, or a value scripts/verify_paper_numbers.py
recomputes), and its text must equal that number formatted once.
"""
import json, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


class AMacroRoundsOnce(unittest.TestCase):

    def test_every_macro_equals_its_raw_value_rounded_once(self):
        import findings as FD
        import make_paper_numbers as MPN
        import verify_paper_numbers as VP
        comp = VP.computed()
        specs = {s["id"]: {h[0]: h for h in s["headline"]} for s in FD.ROWS}
        rows = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "results", "findings.json")))["rows"]}
        bad = []
        for macro, rid, name, part, f in MACROS_OF(MPN):
            h = specs[rid][name]
            if part == "ci":
                src = h[2]
                raw = FD.get(json.load(open(os.path.join(ROOT, "results", src[1]))), src[2])
                once = "[%s, %s]" % (MPN.fmt(raw[0], f), MPN.fmt(raw[1], f))
                shown = "[%s, %s]" % tuple(MPN.fmt(x, f) for x in MPN.lookup(rows, rid, name)["ci"])
            else:
                src = h[1]
                raw = comp[src[1]][1] if src[0] == "verifier" else \
                    FD.get(json.load(open(os.path.join(ROOT, "results", src[1]))), src[2])
                once = MPN.fmt(float(raw), f)
                shown = MPN.fmt(MPN.lookup(rows, rid, name)["value"], f)
            if once != shown:
                bad.append("%s: raw %r prints %s once, but the findings value prints %s" % (macro, raw, once, shown))
        self.assertEqual(bad, [])


def MACROS_OF(MPN):
    return [m for m in MPN.MACROS]


if __name__ == "__main__":
    unittest.main()
