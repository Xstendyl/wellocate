#!/usr/bin/env python3
"""Which campaigns of the bio panel still have their calls, attributed cell by cell.

The call rows carry no cell field, so each row is attributed to a cell from its content:
  1. the noise sentence in the prompt marks `BioRoleNoisy`;
  2. otherwise `noise_model` separates `BioRoleExact` ("exact") from `BioRole` ("multiplicative");
  3. a nomination row has no `noise_model`, so it is attributed by whether its history's readings
     equal the true fitness. Only the exact cell measures without noise.

Usage: python3 scripts/bio_coverage.py
"""
import collections, glob, gzip, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from grid import landscape as grid_landscape                           # noqa: E402

HIST_ROW = re.compile(r"^\s*\d+\s+([A-T]{4})\s+(-?\d+\.\d+)\s*$", re.M)
CELLS = ["BioRole", "BioRoleNoisy", "BioRoleExact"]


def calls():
    rows = []
    for g in sorted(glob.glob(os.path.join(ROOT, "results", "grid_bioframing_calls", "*.jsonl.gz"))):
        with gzip.open(g, "rt") as f:
            rows += [json.loads(l) for l in f if l.strip()]
    return rows


def main():
    fit, _pool = grid_landscape()
    rows = calls()

    def cell_of(r):
        if "Assay readings can be noisy" in (r.get("prompt") or ""):
            return "BioRoleNoisy"
        nm = r.get("noise_model")
        if nm == "exact":
            return "BioRoleExact"
        if nm == "multiplicative":
            return "BioRole"
        # A nomination row. Exact readings equal the truth, and a noisy reading almost never does.
        pairs = HIST_ROW.findall(r.get("prompt") or "")
        if not pairs:
            return None
        exact = sum(1 for s, v in pairs if s in fit and abs(fit[s] - float(v)) < 5e-4)
        return "BioRoleExact" if exact == len(pairs) else "BioRole"

    per = collections.defaultdict(set)
    unattributed = 0
    for r in rows:
        c = cell_of(r)
        if c is None:
            unattributed += 1
            continue
        per[(c, r["model"])].add(r["campaign_seed"])

    camps = [json.loads(l) for l in
             open(os.path.join(ROOT, "results", "grid_bioframing_campaigns.jsonl")) if l.strip()]
    want = collections.defaultdict(set)
    for x in camps:
        want[(x["condition"], x["model"])].add(x["seed"])

    print("=" * 84)
    print("BIO PANEL CALL COVERAGE, cells recovered from content")
    print("=" * 84)
    print("  %-14s %-22s %9s %11s" % ("cell", "model", "on disk", "with calls"))
    tw = th = 0
    for c in CELLS:
        for m in sorted({x["model"] for x in camps}):
            w = len(want[(c, m)])
            h = len(want[(c, m)] & per[(c, m)])
            tw += w
            th += h
            print("  %-14s %-22s %9d %11d" % (c, m.split("/")[-1], w, h))
    print("  %-37s %9d %11d" % ("TOTAL", tw, th))
    print("\n  unattributable rows: %d" % unattributed)
    print("  an oracle audit of this panel can cover %d of %d campaigns" % (th, tw))
    json.dump(dict(total=tw, with_calls=th,
                   per_cell={"%s|%s" % (c, m): len(want[(c, m)] & per[(c, m)])
                             for c in CELLS for m in sorted({x["model"] for x in camps})}),
              open(os.path.join(ROOT, "results", "bio_coverage.json"), "w"), indent=1)
    print("  wrote results/bio_coverage.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
