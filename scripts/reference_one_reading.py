#!/usr/bin/env python3
"""Table 1's reference rows, one more column: the share of campaigns whose final pick had exactly one reading.

For each landscape's best scripted rule and guessing rule, the policies results/landscapes_0an8.json names, on the
1,500 reference seeds of the landscape's paper split (nk:paper, gb1:paper, phoq:paper), through Wellocate's
scorecard, which records the nominee's number of readings. A collapsed episode is left out, the references'
convention.

Checks, each aborting on failure: every rerun reproduces the pick and the re-testing share that landscapes_0an8.json prints
for its row, and on PhoQ the share equals references_0an8.json's own nominee_one_reading for that policy.

Usage: python3 scripts/reference_one_reading.py     (writes results/reference_one_reading.json)
"""
import json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from wellocate import baselines as B                          # noqa: E402
from wellocate import scorecard as SC                         # noqa: E402
from wellocate import splits as SP                            # noqa: E402

RES = os.path.join(ROOT, "results")
OUT = os.path.join(RES, "reference_one_reading.json")
SPLITS = {"grid": "nk:paper", "GB1": "gb1:paper", "PhoQ": "phoq:paper"}


def factory(policy):
    rule, k = policy.split(" k=")
    return {"guessing": B.guessing, "informed": B.informed}[rule](int(k))


def run(policy, split):
    rows = [SC.run_episode(factory(policy), inst, s, "assay") for inst, s in SP.episodes(split)]
    ok = [r for r in rows if r is not None]
    return dict(policy=policy, n=len(ok), collapsed=len(rows) - len(ok), pick=st.mean(r["pick"] for r in ok),
                share_budget=st.mean(r["share_budget"] for r in ok),
                one_reading_pct=100.0 * st.mean(1.0 if r["nominee_readings"] == 1 else 0.0 for r in ok))


def main():
    refs = json.load(open(os.path.join(RES, "landscapes_0an8.json")))["references"]
    r8 = json.load(open(os.path.join(RES, "references_0an8.json")))["reference"]
    out = {}
    for land, split in SPLITS.items():
        best, guess = refs[land]["best"], refs[land]["guessing"]
        rows = {"best scripted": (best["policy"], best["pick"], best["share_budget"]),
                "guessing rule": ("guessing k=%d" % guess["k"], guess["pick"], guess["share"])}
        out[land] = {}
        for row, (policy, pick, share) in rows.items():
            r = run(policy, split)
            if abs(r["pick"] - pick) > 1e-9 or abs(r["share_budget"] - share) > 1e-9:
                raise SystemExit("ABORT: %s %s (%s): pick %.9f share %.9f, table %.9f %.9f"
                                 % (land, row, policy, r["pick"], r["share_budget"], pick, share))
            if land == "PhoQ" and abs(r["one_reading_pct"] - r8[policy]["nominee_one_reading"]) > 1e-9:
                raise SystemExit("ABORT: PhoQ %s: %.9f here, %.9f in references_0an8.json"
                                 % (policy, r["one_reading_pct"], r8[policy]["nominee_one_reading"]))
            out[land][row] = dict(r, split=split)
            print("%-5s %-14s %-13s n=%d pick %.4f share %.2f%% one reading %.2f%%"
                  % (land, row, policy, r["n"], r["pick"], r["share_budget"], r["one_reading_pct"]))
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print("written %s" % os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
