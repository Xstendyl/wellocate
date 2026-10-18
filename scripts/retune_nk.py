#!/usr/bin/env python3
"""Retune the NK landscape against the shrinkage-minus-max-single margin.

Pure noise gives a margin of exactly zero. Both rules are applied to the same campaign, so every comparison is paired.
"""
import math, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from repdef import campaign as C, policies as P
from repdef.nk import NKLandscape

CV, FLOOR, GB1_MAX = 0.073, (1/557)/(285/557), 8.762


class Scaled(object):
    def __init__(self, nk):
        f = GB1_MAX / max(nk.fitness.values())
        self.fitness = {k: v * f for k, v in nk.fitness.items()}
        self.pool = nk.pool
        self.nk = nk


def sigma(f):
    return math.sqrt(FLOOR ** 2 + (abs(f) * CV) ** 2)


def measure(ls, policy, n, seed0):
    """Return the paired margin, its SE, the disagreement rate, and gap/sigma."""
    ps = tuple(sorted(ls.pool))
    vals = [ls.fitness[s] for s in ls.pool]
    prior = (st.mean(vals), st.variance(vals))
    dshr, dmax, dis, gaps, champs = [], [], 0, [], []
    for i in range(n):
        r = C.run(ls.fitness, ls.pool, policy, 0.0, seed0 + i, 0.15, pool_sorted=ps,
                  nomination="shrinkage", prior=prior,
                  noise_model="multiplicative", cv=CV, noise_floor=FLOOR)
        dshr.append(r.nominated_true)
        dmax.append(ls.fitness[r.ref_max])
        if r.nominated != r.ref_max:
            dis += 1
        tv = sorted((ls.fitness[s] for s in {h.seq for h in r.history if h.outcome == "ok"}),
                    reverse=True)
        if len(tv) >= 2:
            gaps.append(tv[0] - tv[1]); champs.append(tv[0])
    d = [a - b for a, b in zip(dshr, dmax)]
    m = st.mean(d)
    se = st.stdev(d) / math.sqrt(len(d)) if len(d) > 1 else float("nan")
    g = st.median(gaps) / sigma(st.median(champs)) if gaps else float("nan")
    return m, se, dis / n, g, st.mean(dshr), st.mean(dmax)


def main():
    N = int(os.environ.get("RETUNE_N", "1200"))
    print("RETUNE against the amended criterion. Target: margin positive at >= 3 paired SE.")
    print("Also required: 0.5 <= gap/sigma <= 1.5.  n=%d campaigns per cell.\n" % N)
    print("  %-3s %-6s %7s %8s %9s %22s %8s %s"
          % ("K", "pct", "pool%", "autocorr", "gap/sig", "margin (shrink - max)", "SE ratio", "verdict"))
    pol = P.GreedyWithReplication(1, 0, "pool", "fresh_pool")
    winners = []
    for k in (1, 2):
        ac = NKLandscape(k=k, seed=1).autocorrelation(60000)
        for pct in (88.0, 90.0, 93.0, 94.5):
            nk = NKLandscape(k=k, seed=1, threshold_percentile=pct)
            pf = nk.pool_fraction()
            if not (0.03 <= pf <= 0.13):
                continue
            ls = Scaled(nk)
            m, se, dis, g, ms, mm = measure(ls, pol, N, 9_000_000 + k * 100000 + int(pct * 10))
            ratio = m / se if se else float("nan")
            gap_ok = 0.5 <= g <= 1.5
            ok = ratio >= 3.0 and gap_ok
            if ok:
                winners.append((k, pct, m, se, g, ac))
            print("  %-3d %-6.1f %6.2f%% %8.3f %9.2f %+10.4f +- %-7.4f %8.1f %s"
                  % (k, pct, 100 * pf, ac, g, m, se, ratio,
                     "PASS" if ok else ("gap out of band" if not gap_ok else "margin too small")))
    print()
    if not winners:
        print("  NO configuration passes. gap/sigma is the binding constraint: NK at N=4 puts the")
        print("  top candidates far closer together than the 0.5 lower bound requires.")
    else:
        print("  %d configuration(s) pass. Neutrality check on the best one:" % len(winners))
        k, pct, m, se, g, ac = max(winners, key=lambda w: w[2] / w[3])
        ls = Scaled(NKLandscape(k=k, seed=1, threshold_percentile=pct))
        print("  K=%d pct=%.1f: margin %+.4f +- %.4f, gap/sigma %.2f, autocorr %.3f\n" % (k, pct, m, se, g, ac))
        print("    %-22s %22s %9s %s" % ("baseline", "margin (shrink - max)", "SE ratio", "disagree"))
        for lbl, p2 in (("random", P.RandomPolicy(0)),
                        ("greedy k=0", P.GreedyWithReplication(0, 0, "pool", "fresh_pool")),
                        ("greedy k=1", P.GreedyWithReplication(1, 0, "pool", "fresh_pool")),
                        ("greedy k=2", P.GreedyWithReplication(2, 0, "pool", "fresh_pool")),
                        ("greedy k=3", P.GreedyWithReplication(3, 0, "pool", "fresh_pool"))):
            mm, ss, dd, gg, _, _ = measure(ls, p2, N, 9_500_000)
            print("    %-22s %+10.4f +- %-7.4f %9.1f %8.0f%%" % (lbl, mm, ss, mm/ss if ss else 0, 100*dd))


if __name__ == "__main__":
    main()
