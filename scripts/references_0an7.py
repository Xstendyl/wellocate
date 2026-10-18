#!/usr/bin/env python3
"""Scripted reference policies under the same rules as the agents, with re-testing share counted two ways.

For the grid's landscape and scrambled GB1, on the references' 1,500 seeds (8,200,000 onward):
  guessing   FairGreedyAlphabet (yardsticks_0am.py) at each k in 0..4, the k* with the highest mean pick reported;
  informed   PoolGreedyAlphabet (fair_reference_curve.py), which knows the viable set, at each k, k* reported.
Per k: mean final pick (shrinkage nomination) with its standard error, re-testing share over the budget
(replication_count / slots_used) and over slots not lost (replication_count / (slots_used -
lost slots)), and lost slots. A campaign with fewer than two measured candidates is counted as collapsed and left
out, the references' convention.

Usage: python3 scripts/references_0an7.py      (writes results/references_0an7.json)
"""
import json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from repdef import campaign as C, envs as EV, policies as P                # noqa: E402
import fair_reference_curve as FRC                                         # noqa: E402
import yardsticks_0am as Y                                                 # noqa: E402


def lands():
    fit, pool = FRC.landscape()
    yield "grid", fit, pool, FRC.anchor_of(fit, pool), None
    e = EV.env_for("gb1_scrambled")
    yield "gb1_scrambled", e.fit, e.pool, e.anchor, e.rng_key


def run(name, fit, pool, anchor, rng_key, policy, k):
    ps, space = tuple(sorted(pool)), tuple(sorted(fit))
    alpha = P.alphabet_of(space)
    rows, collapsed = [], 0
    for i in range(FRC.N):
        pol = (Y.FairGreedyAlphabet(k, anchor, space, alpha, seed=0) if policy == "guessing"
               else FRC.PoolGreedyAlphabet(k, space))
        try:
            r = C.run(fit, pool, pol, 0.0, FRC.SEED0 + i, 0.15, pool_sorted=ps, nomination="shrinkage",
                      prior="empirical", noise_model="multiplicative", cv=FRC.CV, noise_floor=FRC.FLOOR, rng_key=rng_key)
        except C.UnusableSigma:
            collapsed += 1
            continue
        lost = sum(1 for h in r.history if h.outcome in ("abandoned", "round_lost", "cap_lost"))
        used = r.slots_used
        rows.append((r.nominated_true, 100.0 * r.replication_count / used if used else 0.0,
                     100.0 * r.replication_count / (used - lost) if used - lost > 0 else 0.0, lost))
    picks = [x[0] for x in rows]
    return dict(n=len(rows), collapsed=collapsed, pick=st.mean(picks), pick_se=st.stdev(picks) / math.sqrt(len(picks)),
                share_budget=st.mean(x[1] for x in rows), share_nonlost=st.mean(x[2] for x in rows),
                lost=st.mean(x[3] for x in rows))


def main():
    out = {}
    for name, fit, pool, anchor, key in lands():
        out[name] = {}
        for policy in ("guessing", "informed"):
            curve = {str(k): run(name, fit, pool, anchor, key, policy, k) for k in FRC.KS}
            ks = max(curve, key=lambda k: curve[k]["pick"])
            out[name][policy] = dict(curve=curve, kstar=int(ks), at_kstar=curve[ks])
            a = curve[ks]
            print("%-14s %-9s k*=%s pick %.4f (SE %.4f) share %.2f%% over the budget, %.2f%% over slots not lost, lost %.2f"
                  % (name, policy, ks, a["pick"], a["pick_se"], a["share_budget"], a["share_nonlost"], a["lost"]), flush=True)
    json.dump(out, open(os.path.join(ROOT, "results", "references_0an7.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
