#!/usr/bin/env python3
"""Where the agents lose against the scripted policy that must guess, split into exploration and selection.

  python3 scripts/loss_vs_guessing.py

Exploration shortfall = global best - best true value measured; selection shortfall = best true value
measured - true value nominated. For each cell, the agents' extra exploration shortfall and their selection
change are taken against the guessing policy, and they sum to the gap in nominated fitness.

The guessing policy (FairGreedyAlphabet at k=1, 1,500 seeds from 8,200,000) is rerun here, and the script
refuses unless its mean nomination matches results/reference_curve_alphabet.json and the two parts sum to
the whole.

Writes results/loss_vs_guessing.json.
"""
import json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from repdef import campaign as C                                       # noqa: E402
import fair_reference_curve as FRC                                     # noqa: E402


def guessing_policy():
    fit, pool = FRC.landscape()
    ps = sorted(pool, key=lambda s: -fit[s])
    anchor, space, gb = FRC.anchor_of(fit, pool), sorted(fit), max(fit.values())
    nom, best, dead = [], [], 0
    for i in range(FRC.N):
        pol = FRC.FairGreedyAlphabet(1, anchor, space, seed=0)
        try:
            r = C.run(fit, pool, pol, 0.0, FRC.SEED0 + i, 0.15, pool_sorted=ps, nomination="shrinkage",
                      prior="empirical", noise_model="multiplicative", cv=FRC.CV, noise_floor=FRC.FLOOR)
        except C.UnusableSigma:
            dead += 1
            continue
        nom.append(r.nominated_true)
        best.append(r.best_true_measured)
    return dict(n=len(nom), collapsed=dead, global_best=gb, nominated=st.mean(nom),
                exploration=st.mean(gb - b for b in best),
                selection=st.mean(b - n for b, n in zip(best, nom)))


def main():
    g = guessing_policy()
    ref = json.load(open(FRC.CORRECTED))["curves"]["fair"]["1"]
    if abs(g["nominated"] - ref["mean"]) > 1e-9 or g["n"] != ref["n"]:
        print("REFUSED: this run's guessing policy (n=%d, mean %.6f) is not the committed one (n=%d, mean %.6f)"
              % (g["n"], g["nominated"], ref["n"], ref["mean"]))
        return 1
    cells = json.load(open(os.path.join(ROOT, "results", "analysis_final", "grid", "summary.json")))["cells_detail"]
    out, bad = [], []
    for x in cells:
        extra = x["exploration_shortfall"] - g["exploration"]
        sel = x["selection_shortfall"] - g["selection"]
        net = extra + sel
        if abs(net - (g["nominated"] - x["mean"])) > 1e-9:
            bad.append("%s %s: parts %.6f, nominated gap %.6f" % (x["model"], x["condition"], net, g["nominated"] - x["mean"]))
        out.append(dict(model=x["model"], condition=x["condition"], extra_exploration=extra,
                        selection_change=sel, net=net))
    if bad:
        print("REFUSED: the two parts do not sum to the nominated-fitness gap:")
        for b in bad:
            print("  " + b)
        return 1
    json.dump(dict(guessing=g, cells=out), open(os.path.join(ROOT, "results", "loss_vs_guessing.json"), "w"), indent=1)
    print("guessing policy at k=1: n=%d, nominated %.4f, exploration shortfall %.4f, selection shortfall %.4f"
          % (g["n"], g["nominated"], g["exploration"], g["selection"]))
    print("  matches the committed fair k=1 mean exactly; parts sum to the whole in all %d cells\n" % len(out))
    print("  %-20s %-14s %10s %10s %8s" % ("model", "condition", "extra expl", "sel change", "net"))
    for r in out:
        print("  %-20s %-14s %+10.4f %+10.4f %+8.4f" % (r["model"], r["condition"], r["extra_exploration"],
                                                       r["selection_change"], r["net"]))
    ex = [r["extra_exploration"] for r in out]; se = [r["selection_change"] for r in out]; ne = [r["net"] for r in out]
    print("\n  extra exploration  %+.4f to %+.4f   (larger in %d of %d)" % (min(ex), max(ex), sum(e > 0 for e in ex), len(ex)))
    print("  selection change   %+.4f to %+.4f   (smaller in %d of %d)" % (min(se), max(se), sum(s < 0 for s in se), len(se)))
    print("  net deficit        %+.4f to %+.4f   (behind in %d of %d)" % (min(ne), max(ne), sum(n > 0 for n in ne), len(ne)))
    print("  exploration deficit exceeds selection gain in %d of %d cells" % (sum(e > -s for e, s in zip(ex, se)), len(ex)))
    print("  wrote results/loss_vs_guessing.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
