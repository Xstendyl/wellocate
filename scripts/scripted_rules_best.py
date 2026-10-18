#!/usr/bin/env python3
"""Table 1's scripted rows: the guessing, informed and model-guided rules, each at its best setting on each landscape.

A rule's best setting is the number of re-tests per round, k, with the highest mean true pick over the landscape's
1,500 reference campaigns. Each sweep is read from an existing results file; nothing is rerun.
  guessing, informed  k = 0 to 4: results/references_0an7.json (grid, scrambled GB1) and references_0an8.json (PhoQ).
  model-guided        k = 0 to 3 with confirmation: model_guided_0an4.json on the grid (pre-registered), and the
                      post-hoc start check (results/start_robustness.json, the paper's start) on GB1 and PhoQ.
The script aborts unless these sweeps agree with the existing reference results wherever they overlap.

Usage: python3 scripts/scripted_rules_best.py     (writes results/scripted_rules_best.json)
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
OUT = os.path.join(RES, "scripted_rules_best.json")
LANDS = (("grid", "grid", "grid"), ("GB1", "gb1_scrambled", "gb1_scrambled"), ("PhoQ", None, "phoq_scrambled"))


def load(name):
    return json.load(open(os.path.join(RES, name)))


def best(sweep, source):
    k = max(sweep, key=lambda k: sweep[k]["pick"])
    return dict(k=int(k), pick=sweep[k]["pick"], share_budget=sweep[k]["share_budget"], source=source,
                sweep={str(j): dict(pick=v["pick"], share_budget=v["share_budget"]) for j, v in sweep.items()})


def same(a, b, what):
    if abs(a - b) > 1e-9:
        raise SystemExit("ABORT: %s: %.9f against %.9f" % (what, a, b))


def main():
    r7, r8, sr = load("references_0an7.json"), load("references_0an8.json"), load("start_robustness.json")
    mg4, ls8 = load("model_guided_0an4.json"), load("landscapes_0an8.json")["references"]
    sc = load("wellocate_scorecard.json")["splits"]
    out = {}
    for land, k7, ksr in LANDS:
        rows = {}
        for rule in ("guessing", "informed"):
            if k7:
                sweep = {k: dict(pick=v["pick"], share_budget=v["share_budget"]) for k, v in r7[k7][rule]["curve"].items()}
                rows[rule] = best(sweep, "references_0an7.json")
            else:
                sweep = {str(k): r8["reference"]["%s k=%d" % (rule, k)] for k in range(5)}
                rows[rule] = best(sweep, "references_0an8.json")
        L = sr["landscapes"][ksr]
        mg = {k: dict(pick=v["pick"], share_budget=v["share_budget"])
              for k, v in L["by_start"][L["paper_start"]]["model-guided"]["settings"].items()}
        rows["model-guided"] = best(mg, "model_guided_0an4.json (registered)" if land == "grid" else
                                    "start_robustness.json, the paper's own start (post-hoc)")
        # consistency checks against the existing reference results
        g = ls8[land]["guessing"]
        same(rows["guessing"]["pick"], g["pick"], "%s guessing pick" % land)
        same(rows["guessing"]["share_budget"], g["share"], "%s guessing share" % land)
        if land == "grid":
            inf = sc["nk:paper"]["baselines"]["informed at k*"]
            same(rows["informed"]["pick"], inf["pick"]["mean"], "grid informed pick")
            same(rows["informed"]["share_budget"], inf["share_budget"]["mean"], "grid informed share")
            for k in range(4):
                ref = mg4["grid"]["confirm|k=%d" % k]
                same(mg[str(k)]["pick"], ref["shrinkage"], "grid model-guided k=%d pick" % k)
                same(mg[str(k)]["share_budget"], ref["share"], "grid model-guided k=%d share" % k)
        elif land == "GB1":
            ref = sc["gb1:paper"]["baselines"]["model-guided"]
            same(mg["1"]["pick"], ref["pick"]["mean"], "GB1 model-guided k=1 pick")
            same(mg["1"]["share_budget"], ref["share_budget"]["mean"], "GB1 model-guided k=1 share")
        else:
            ref = r8["reference"]["model-guided k=1 with confirmation"]
            same(mg["1"]["pick"], ref["pick"], "PhoQ model-guided k=1 pick")
            same(mg["1"]["share_budget"], ref["share_budget"], "PhoQ model-guided k=1 share")
        top = max(rows, key=lambda r: rows[r]["pick"])
        out[land] = dict(rules=rows, best_rule=top)
        print("%-5s " % land + " | ".join("%s k*=%d pick %.4f share %.2f%%" % (r, v["k"], v["pick"], v["share_budget"])
                                          for r, v in rows.items()) + " | best: %s" % top)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print("written %s" % os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
