#!/usr/bin/env python3
"""Verify a generated NK landscape against the NK pre-registration.

NK fitness lands in [0, 1], so each landscape is multiplied by a constant that puts its maximum at GB1's 8.762,
the units the noise floor of 0.0035 is defined in. This changes no ranking and no gap ratio.
"""
import collections, math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from repdef import campaign as C, policies as P, view as V
from repdef.nk import NKLandscape

CV, FLOOR, GB1_MAX = 0.073, (1/557)/(285/557), 8.762
TARGET, FALLBACK = 0.50, 0.35


class Scaled(object):
    """An NK landscape rescaled so its maximum matches GB1's, with the pipeline's interface."""
    def __init__(self, nk):
        m = max(nk.fitness.values())
        f = GB1_MAX / m
        self.name = nk.name
        self.fitness = {k: v * f for k, v in nk.fitness.items()}
        self.pool = nk.pool
        self.nk = nk


def sigma(f):
    return math.sqrt(FLOOR ** 2 + (abs(f) * CV) ** 2)


def informative_rate(ls, policy, n=300, seed0=5_000_000):
    """A campaign is informative when the shrinkage argmax and the max-single argmax differ.
    Shrinkage is the pre-registered comparator; max-mean ignores unequal replicate counts."""
    ps = tuple(sorted(ls.pool))
    vals = [ls.fitness[s] for s in ls.pool]
    prior = (st.mean(vals), st.variance(vals))
    dis, gaps, champs = 0, [], []
    for i in range(n):
        r = C.run(ls.fitness, ls.pool, policy, 0.0, seed0 + i, 0.15, pool_sorted=ps,
                  nomination="shrinkage", prior=prior,
                  noise_model="multiplicative", cv=CV, noise_floor=FLOOR)
        if r.nominated != r.ref_max:
            dis += 1
        tv = sorted((ls.fitness[s] for s in {h.seq for h in r.history if h.outcome == "ok"}),
                    reverse=True)
        if len(tv) >= 2:
            gaps.append(tv[0] - tv[1]); champs.append(tv[0])
    return (dis / n,
            st.median(gaps) if gaps else float("nan"),
            st.median(champs) if champs else float("nan"))


def main():
    print("PRE-REGISTERED VERIFICATION. primary target: informative rate >= %.0f%%\n" % (100*TARGET))
    print("  %-6s %-6s %8s %8s %10s %10s %8s" % ("K", "seed", "pool%", "autocorr", "informative",
                                                 "gap/sigma", "verdict"))
    best = None
    attempts = []
    for k in (1, 2, 3):
        nk = NKLandscape(k=k, seed=1)
        ls = Scaled(nk)
        ac = nk.autocorrelation(60000)
        pf = nk.pool_fraction()
        pol = P.GreedyWithReplication(1, 0, "pool", "fresh_pool")
        rate, gap, champ = informative_rate(ls, pol, n=250)
        gs = gap / sigma(champ) if champ == champ else float("nan")
        ok = (rate >= TARGET and 0.05 <= pf <= 0.10 and 0.25 <= ac <= 0.45 and gs < 1.5)
        attempts.append((k, rate, pf, ac, gs, ok))
        print("  %-6d %-6d %7.2f%% %8.3f %9.0f%% %10.2f %8s"
              % (k, 1, 100*pf, ac, 100*rate, gs, "PASS" if ok else "fail"))
        if ok and best is None:
            best = k
    print()
    if best is None:
        print("  NO K PASSED at seed 1. Per the pre-registered failure branch the next step is the")
        print("  35%% fallback, and the primary target is reported UNMET in the abstract.")
        near = max(attempts, key=lambda a: a[1])
        print("  best informative rate seen: K=%d at %.0f%% (fallback threshold %.0f%%)"
              % (near[0], 100*near[1], 100*FALLBACK))
    else:
        print("  K=%d passes at seed 1. Next: the 20-seed distribution and the IQR guard." % best)
    print()
    print("  REFERENCE, the landscape this replaces:")
    print("    GB1 informative rate under the same noise model: 14%%")


if __name__ == "__main__":
    main()
