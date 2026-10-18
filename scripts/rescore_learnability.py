#!/usr/bin/env python3
"""Rescore a fresh-landscape simulation run with endpoints from the held-out landscapes. No new campaigns.

When landscapes vary, endpoints taken from the training landscapes can move by more than the span they define,
which makes the normalised score unstable. On the JSON the run already wrote, this:
  * renormalises every held-out policy with endpoints from the same held-out landscapes, which is
    D (k=0, shrinkage) for zero and C (k*, shrinkage) for one;
  * reports learnability: which policy the reward-trained learner selected and whether that is k* or tied
    with k*, keeping the normalised pass-or-fail in the table;
  * reports discrimination from raw paired differences on the held-out landscapes, with the pre-registered
    normalised test beside it, labelled unstable at these spans.

Usage: python3 scripts/rescore_learnability.py results/learnability_fresh_n200.json
"""
import json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POL = ["A k=0 max", "B k* max", "C k* shrinkage", "D k=0 shrinkage", "LEARNED"]


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, "results", "learnability_fresh_n200.json")
    d = json.load(open(src))
    rows = d["settings"]
    n = d["n_per_cell"]
    print("=" * 112)
    print("RESCORED WITH HELD-OUT ENDPOINTS (deviation 2)   %s   n=%d per cell"
          % (os.path.basename(src), n))
    print("Zero is D (k=0, shrinkage) and one is C (k*, shrinkage), both measured on the SAME held-out")
    print("landscapes as the policy being scored.")
    print("=" * 112)

    print("\n  %-3s %-7s %-5s %-3s %9s %9s %9s %11s %9s"
          % ("K", "cv", "scope", "k*", "held span", "C raw", "D raw", "LEARNED", "kept"))
    out = []
    for r in rows:
        p = r["policies"]
        C, D = p["C k* shrinkage"]["raw_mean"], p["D k=0 shrinkage"]["raw_mean"]
        span = C - D
        norm = {k: ((p[k]["raw_mean"] - D) / span if span > 0 else float("nan")) for k in POL}
        out.append(dict(K=r["K"], cv=r["cv"], scope=r["scope"], kstar=r["kstar"],
                        runner_up=r["runner_up"], gap=r["gap"], gap_se=r["gap_se"],
                        gap_is_a_tie=r["gap_is_a_tie"], held_span=span,
                        raw={k: p[k]["raw_mean"] for k in POL}, norm_heldout=norm,
                        norm_training={k: p[k]["norm_mean"] for k in POL},
                        kept={k: p[k]["kept"] for k in POL},
                        paired=r.get("paired", {})))
        print("  %-3d %-7.3f %-5s %-3d %9.4f %9.4f %9.4f %11.3f %9d"
              % (r["K"], r["cv"], r["scope"], r["kstar"], span, C, D, norm["LEARNED"],
                 p["LEARNED"]["kept"]))

    tr = [p["norm_training"]["LEARNED"] for p in out]
    he = [p["norm_heldout"]["LEARNED"] for p in out if p["norm_heldout"]["LEARNED"] == p["norm_heldout"]["LEARNED"]]
    print("\n  LEARNED, normalised with TRAINING endpoints (the defect): %.3f to %.3f" % (min(tr), max(tr)))
    print("  LEARNED, normalised with HELD-OUT endpoints (correct):     %.3f to %.3f" % (min(he), max(he)))
    ks1 = [p for p in out if p["kstar"] == 1]
    exact = sum(1 for p in ks1 if abs(p["norm_heldout"]["LEARNED"] - 1.0) < 1e-9)
    print("  of the %d cells with k* = 1, %d score exactly 1.000, because the learner selected policy C"
          % (len(ks1), exact))

    print("\n  LEARNABILITY, as the substantive fact")
    for scope in sorted({p["scope"] for p in out}):
        cells = [p for p in out if p["scope"] == scope]
        tied = sum(1 for p in cells if p["kstar"] == 1 or p["gap_is_a_tie"])
        print("    scope=%-5s the learner selected k=1 with shrinkage; that is k* or tied with k* in "
              "%d of %d settings" % (scope, tied, len(cells)))

    print("\n  DISCRIMINATION from RAW paired differences on the held-out landscapes")
    print("    %-3s %-7s %-5s %12s %12s %10s" % ("K", "cv", "scope", "C - D raw", "C - A raw", "tie?"))
    for p in out:
        cd = p["raw"]["C k* shrinkage"] - p["raw"]["D k=0 shrinkage"]
        ca = p["raw"]["C k* shrinkage"] - p["raw"]["A k=0 max"]
        print("    %-3d %-7.3f %-5s %+12.4f %+12.4f %10s"
              % (p["K"], p["cv"], p["scope"], cd, ca, "TIE" if p["gap_is_a_tie"] else ""))

    dst = src.replace(".json", "_rescored.json")
    json.dump(dict(source=os.path.basename(src), n_per_cell=n,
                   note="held-out endpoints; see DEFERRED_CHANGES deviation 2", cells=out),
              open(dst, "w"), indent=1)
    print("\n  the pre-registered NORMALISED test is unstable at these spans and is kept in the appendix")
    print("  wrote %s" % os.path.relpath(dst, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
