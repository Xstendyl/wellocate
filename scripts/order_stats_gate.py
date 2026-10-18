#!/usr/bin/env python3
"""Order-statistics check: does the noise-obscured regime exist by construction on GB1 and PhoQ?

Part A: for m from 10,000 down to 10, the typical adjacent-rank gap among the top-m variants by true fitness,
with the published GB1 noise floor overlaid. Part B: a 60-measurement campaign holds at most 60 candidates, so
it reports the top1-top2 gap among 60 candidates drawn from the top-X of the pool, from random (X = whole
pool) to the oracle limit (X = 60).

The GB1 noise floor is sigma = 0.364, from the Wu et al. 2016 read depth (557 input and 285 selected reads per
variant, CV 7.3%, multiplicative, at the champion level f = 5.00).
"""
import os
import random
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from repdef import landscape as L

SIGMA_GB1 = 0.364
MS = (10000, 5000, 2000, 1000, 500, 200, 100, 60, 30, 10)
XS = (None, 5000, 2000, 1000, 500, 200, 100, 60)
N_DRAWS = 4000


def main():
    for name in ("gb1", "phoq"):
        ls = L.load(name)
        v = sorted((ls.fitness[s] for s in ls.pool), reverse=True)
        sigma = SIGMA_GB1 if name == "gb1" else None
        print("=" * 104)
        print("%s   pool %d   max %.4f   median %.4f%s"
              % (name.upper(), len(v), v[0], st.median(v),
                 "   published noise floor sigma = %.3f" % sigma if sigma else
                 "   NO published per-variant noise"))
        print("=" * 104)

        print("\n  PART A: adjacent-rank gaps among the top-m by true fitness")
        print("    %7s %12s %12s %12s %10s" % ("m", "median gap", "mean gap", "top1-top2", "vs sigma"))
        for m in MS:
            if m > len(v):
                continue
            gaps = [v[i] - v[i + 1] for i in range(m - 1)]
            med, mean = st.median(gaps), st.mean(gaps)
            rel = ("%6.2f x sigma" % (med / sigma)) if sigma else "n/a"
            print("    %7d %12.5f %12.5f %12.5f %10s" % (m, med, mean, v[0] - v[1], rel))

        print("\n  PART B: top1-top2 gap for a 60-candidate campaign drawn from the top-X of the pool")
        print("    (X = whole pool is random exploration; X = 60 is the oracle limit)")
        print("    %10s %14s %14s %16s" % ("X", "median gap", "mean gap", "ratio = sigma/gap"))
        rnd = random.Random(11)
        for X in XS:
            sub = v if X is None else v[:X]
            if len(sub) < 60:
                continue
            tops = []
            for _ in range(N_DRAWS):
                pick = rnd.sample(range(len(sub)), 60)
                pick.sort()
                tops.append(sub[pick[0]] - sub[pick[1]])
            med, mean = st.median(tops), st.mean(tops)
            r = ("%14.2f" % (sigma / med)) if (sigma and med > 0) else "n/a"
            print("    %10s %14.5f %14.5f %16s"
                  % ("whole pool" if X is None else X, med, mean, r))
        if sigma:
            print("\n    PRE-COMMITTED THRESHOLD: I said before running that if the oracle-limit gap")
            print("    is at or below 0.09, the effective ratio at convergence exceeds 4.0 and the")
            print("    reframe wins.")
        print()


if __name__ == "__main__":
    main()
