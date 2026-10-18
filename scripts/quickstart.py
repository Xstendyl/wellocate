#!/usr/bin/env python3
"""Run the two scripted policies on one seed, so the environment can be seen working in one command.

  python3 scripts/quickstart.py            one seed, k = 0 and k = 1
  python3 scripts/quickstart.py --seed N   another seed

Nothing here calls an API and nothing is written to disk. It builds the same landscape the study used,
runs the scripted hill-climber at zero repeats and at one repeat per candidate, and prints what each
campaign spent its 60 measurements on. The paper's reference curves are the same policies over 1,500
seeds: `python3 scripts/fair_reference_curve.py`.
"""
import argparse, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from repdef import campaign as C, policies as P                        # noqa: E402
import fair_reference_curve as FRC                                     # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=FRC.SEED0)
    a = ap.parse_args()

    fit, pool = FRC.landscape()
    ps = sorted(pool, key=lambda s: -fit[s])
    anchor = FRC.anchor_of(fit, pool)
    space = sorted(fit)
    print("landscape: %d candidates, %d viable (%.2f%%), best %.4f, reference point %s at %.4f"
          % (len(fit), len(pool), 100.0 * len(pool) / len(fit), max(fit.values()), anchor, fit[anchor]))
    print("seed %d, 15 rounds of 4 measurements\n" % a.seed)
    print("  %-34s %8s %9s %11s %10s" % ("policy", "repeats", "distinct", "nominated", "vs best"))
    for k in (0, 1):
        pol = FRC.FairGreedyAlphabet(k, anchor, space, seed=0)
        r = C.run(fit, pool, pol, 0.0, a.seed, 0.15, pool_sorted=ps, nomination="shrinkage",
                  prior="empirical", noise_model="multiplicative", cv=FRC.CV, noise_floor=FRC.FLOOR)
        ok = [h for h in r.history if h.outcome == "ok"]
        distinct = len({h.seq for h in ok})
        print("  %-34s %8d %9d %11.4f %10.4f"
              % ("scripted, %d repeat%s per candidate" % (k, "" if k == 1 else "s"),
                 len(ok) - distinct, distinct, r.nominated_true, r.nominated_true - max(fit.values())))
    print("\nOne seed is one draw. The curves in the paper average 1,500.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
